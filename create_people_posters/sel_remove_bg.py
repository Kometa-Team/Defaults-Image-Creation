# sel_remove_bg.py
import os, time, shutil, subprocess, sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

from alive_progress import alive_bar

from PIL import Image, ImageOps

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains

from dotenv import load_dotenv

# ===============================
# Load env + constants
# ===============================
# --- Resolve script + config dirs first ---
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR   = CONFIG_DIR / "logs"
for d in (CONFIG_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Bootstrap .env in ./config if missing, then exit with instructions ---
ENV_FILE = CONFIG_DIR / ".env"
if not ENV_FILE.exists():
    # Try to copy a template .env.example (repo root or next to script)
    candidates = [
        SCRIPT_DIR / ".env.example",
        SCRIPT_DIR.parent / ".env.example",
    ]
    copied = False
    for ex in candidates:
        if ex.is_file():
            shutil.copy2(ex, ENV_FILE)
            copied = True
            break
    if not copied:
        # Create a minimal stub if no example is present
        ENV_FILE.write_text(
            "TMDB_KEY=\n"
            "# Add any other settings here. This file lives in ./config/.env\n",
            encoding="utf-8",
        )

    msg = (
        f"Missing ./config/.env — created one at: {ENV_FILE}\n"
        "Please open it and set at least TMDB_KEY before re-running."
    )
    # Print to stderr and also drop a line in a log file, if desired
    print(msg, file=sys.stderr)
    try:
        (LOGS_DIR / f"{Path(__file__).stem}.log").write_text(msg + "\n", encoding="utf-8")
    except Exception:
        pass
    sys.exit(1)

# --- Only load from ./config/.env (no fallback to CWD) ---
load_dotenv(ENV_FILE)

# Chrome profile (keeps you signed in)
URL = os.getenv("SEL_TOOL_URL", "https://new.express.adobe.com/tools/remove-background")
USER_DATA_DIR = os.getenv("SEL_USER_DATA_DIR", str(Path.cwd() / "chrome-profile"))
PROFILE_DIR = os.getenv("SEL_PROFILE_DIR", "Profile 1")

# Normalize to absolute paths even if .env uses relative paths
SRC_DIR = Path(os.getenv("SEL_SRC_DIR", str(Path.cwd()))).resolve()
ORIG_DIR = Path(os.getenv("SEL_ORIG_DIR", str(Path.cwd() / "original"))).resolve()
DOWNLOAD_DIR = Path(os.getenv("SEL_DOWNLOAD_DIR", str(Path.cwd() / "sel_downloads"))).resolve()

# Flow & patience knobs
MAX_WAIT_READY_SEC = int(os.getenv("SEL_MAX_WAIT_READY_SEC", "120"))
PROC_TIMEOUT = int(os.getenv("SEL_PROC_TIMEOUT", "120"))  # wait for processing (Download visible)
MAX_WAIT_DL_SEC = int(os.getenv("SEL_MAX_WAIT_DL_SEC", "240"))  # wait for file to appear
DL_BTN_TIMEOUT = int(os.getenv("SEL_DL_BUTTON_TIMEOUT", "20"))  # how long to wait for button to be found
RELOAD_EACH_FILE = os.getenv("SEL_RELOAD_EACH_FILE", "true").lower() in ("1", "true", "yes", "y")
RESTART_BROWSER_EACH_FILE = os.getenv("SEL_RESTART_BROWSER_EACH_FILE", "true").lower() in ("1", "true", "yes", "y")
MAX_FILE_ATTEMPTS = max(1, int(os.getenv("SEL_MAX_FILE_ATTEMPTS", "2")))

# Size enforcement
EXPECT_W = int(os.getenv("SEL_EXPECT_WIDTH", "2000"))
EXPECT_H = int(os.getenv("SEL_EXPECT_HEIGHT", "3000"))
ENFORCE_SIZE = os.getenv("SEL_ENFORCE_SIZE", "true").lower() in ("1", "true", "yes", "y")

# Make sure folders exist
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
ORIG_DIR.mkdir(parents=True, exist_ok=True)


# ===============================
# Tiny logging helpers
# ===============================
def now_ts() -> str:
    return time.strftime("%H:%M:%S")


LOG_FILE = LOGS_DIR / "sel_remove_bg.log"


def log(msg: str) -> None:
    line = f"[{now_ts()}] {msg}"
    print(line)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class StepTimer:
    def __init__(self, label: str):
        self.label = label
        self.t0 = time.perf_counter()

    def done(self, extra: str = "") -> float:
        dt = time.perf_counter() - self.t0
        if extra:
            log(f"{self.label} — {dt:.2f}s ({extra})")
        else:
            log(f"{self.label} — {dt:.2f}s")
        return dt


@dataclass
class FileResult:
    name: str
    status: str
    detail: str = ""
    sec_total: float = 0.0
    sec_upload: float = 0.0
    sec_process: float = 0.0
    sec_download: float = 0.0


# ===============================
# Driver
# ===============================
def build_driver():
    # Ensure the profile root exists (fresh machines / first run)
    Path(USER_DATA_DIR).mkdir(parents=True, exist_ok=True)

    opts = Options()
    opts.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    opts.add_argument(f"--profile-directory={PROFILE_DIR}")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-features=PrivacySandboxAdsAPIs")
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(DOWNLOAD_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
    })
    service = Service(log_output=subprocess.DEVNULL)
    driver = webdriver.Chrome(options=opts, service=service)
    try:
        driver.maximize_window()
    except Exception:
        driver.set_window_size(1400, 1000)

    # Force download path via CDP (helps SPA downloads)
    try:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": str(DOWNLOAD_DIR)
        })
    except Exception:
        pass
    return driver


def js(driver, script, *args):
    return driver.execute_script(script, *args)


def is_browser_crash(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = (
        "tab crashed",
        "session deleted because of page crash",
        "target frame detached",
        "invalid session id",
        "chrome not reachable",
        "disconnected: not connected to devtools",
    )
    return any(marker in msg for marker in markers)


def restart_driver(driver, reason: str = ""):
    detail = reason.strip().splitlines()[0] if reason else "unknown browser failure"
    log(f"[browser] restarting Chrome ({detail})")
    try:
        driver.quit()
    except Exception:
        pass
    return build_driver()


# ===============================
# Deep selectors (shadow DOM + iframes)
# ===============================
def deep_query_text_iframes(driver, pattern, tag_filter="*"):
    """Find by innerText regex across shadow DOM and same-origin iframes."""
    script = r"""
    const [reSrc, tag] = arguments;
    const re = new RegExp(reSrc, 'i');

    function findIn(root){
      const nodes = root.querySelectorAll ? root.querySelectorAll(tag) : [];
      for (const n of nodes){
        let t = '';
        try { t = (n.innerText || n.textContent || '').trim(); } catch(e){}
        if (t && re.test(t)) return n;
        if (n.shadowRoot){
          const hit = findIn(n.shadowRoot);
          if (hit) return hit;
        }
      }
      return null;
    }

    let hit = findIn(document);
    if (hit) return hit;

    for (const f of document.querySelectorAll('iframe')){
      try{
        const d = f.contentDocument || f.contentWindow?.document;
        if (!d) continue;
        hit = findIn(d);
        if (hit) return hit;
      }catch(e){}
    }
    return null;
    """
    return driver.execute_script(script, pattern, tag_filter)


def deep_query_iframes_one(driver, selector, timeout=0):
    """querySelector across shadow DOM and iframes. If timeout>0, poll until found."""
    script = r"""
    const sel = arguments[0];
    function q1(root, sel){ try{ return root.querySelector(sel); }catch(e){ return null; } }
    function findIn(root){
      const hit = q1(root, sel);
      if (hit) return hit;
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){ if (n.shadowRoot){ const h=findIn(n.shadowRoot); if(h) return h; } }
      return null;
    }
    const topHit = findIn(document);
    if (topHit) return topHit;
    const ifr = Array.from(document.querySelectorAll('iframe'));
    for (const f of ifr){
      try {
        const d = f.contentDocument || f.contentWindow?.document;
        if (!d) continue;
        const hit = findIn(d);
        if (hit) return hit;
      } catch(e) {}
    }
    return null;"""
    end = time.time() + max(0, timeout)
    while True:
        el = driver.execute_script(script, selector)
        if el or timeout <= 0 or time.time() >= end:
            return el
        time.sleep(0.3)


def deep_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    driver.execute_script("arguments[0].click();", el)


def describe_control_state(driver, el):
    """Return a small state snapshot for buttons/controls, including shadow-host buttons."""
    try:
        return driver.execute_script("""
            const el = arguments[0];
            if (!el || !el.isConnected) return {connected:false, visible:false, enabled:false, text:''};

            const inner = (el.shadowRoot && el.shadowRoot.querySelector('button')) || el;
            const style = getComputedStyle(inner);
            const rect = inner.getBoundingClientRect();
            const attr = (node, name) => (node && node.getAttribute ? node.getAttribute(name) : null);
            const hasDisabledClass = (node) => {
              const cls = ((node && node.className) || '').toString().toLowerCase();
              return cls.includes('disabled') || cls.includes('is-disabled');
            };

            const disabled =
              !!inner.disabled ||
              attr(inner, 'disabled') !== null ||
              attr(inner, 'aria-disabled') === 'true' ||
              attr(el, 'disabled') !== null ||
              attr(el, 'aria-disabled') === 'true' ||
              hasDisabledClass(inner) ||
              hasDisabledClass(el) ||
              style.pointerEvents === 'none';

            const visible =
              style.display !== 'none' &&
              style.visibility !== 'hidden' &&
              rect.width > 0 &&
              rect.height > 0;

            const text = ((inner.innerText || inner.textContent || el.innerText || el.textContent || '') + '').trim();
            return {
              connected: true,
              visible,
              enabled: visible && !disabled,
              disabled,
              text
            };
        """, el)
    except Exception:
        return {"connected": False, "visible": False, "enabled": False, "text": ""}


def wait_for_uploaded_file(driver, expected_name: str, timeout: float = 5.0):
    """Look across the page/shadow DOM/iframes for a file input holding expected_name."""
    script = r"""
    const expected = arguments[0].toLowerCase();

    function scanRoot(root){
      const out = [];
      const all = root.querySelectorAll ? root.querySelectorAll('input[type="file"]') : [];
      for (const el of all){
        try{
          const files = el.files || [];
          const first = files[0];
          out.push({
            count: files.length || 0,
            name: first && first.name ? String(first.name) : ''
          });
        }catch(e){}
      }

      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (n.shadowRoot) out.push(...scanRoot(n.shadowRoot));
      }
      return out;
    }

    let found = scanRoot(document);
    for (const f of document.querySelectorAll('iframe')){
      try{
        const d = f.contentDocument || f.contentWindow?.document;
        if (d) found.push(...scanRoot(d));
      }catch(e){}
    }

    for (const item of found){
      if (item.count > 0 && item.name.toLowerCase() === expected){
        return {matched: true, count: item.count, name: item.name};
      }
    }

    return found[0] || {matched: false, count: 0, name: ''};
    """
    end = time.time() + timeout
    last_state = {"matched": False, "count": 0, "name": ""}
    while time.time() < end:
        try:
            state = driver.execute_script(script, expected_name)
        except Exception:
            state = {"matched": False, "count": 0, "name": ""}
        if state.get("matched"):
            return state
        last_state = state
        time.sleep(0.25)
    return last_state


def send_keys_and_confirm(driver, inp, path_str: str) -> bool:
    expected_name = Path(path_str).name
    inp.send_keys(path_str)
    state = wait_for_uploaded_file(driver, expected_name, timeout=5.0)
    if state.get("matched"):
        log(f"[upload] confirmed file input holds: {state.get('name', '')}")
        return True
    log(f"[upload] send_keys did not bind expected file: expected={expected_name!r} seen={state.get('name', '')!r} count={state.get('count', 0)}")
    return False


# ===============================
# Route / consent / promos
# ===============================
def pin_tool_route(driver):
    js(driver, """
    (function(TARGET){
      if(window.__pinRoute)return;
      window.__pinRoute=setInterval(()=>{
        if(!location.href.includes('/tools/remove-background')){
          try{history.replaceState(null,'',TARGET);}catch(e){}
          location.href=TARGET;
        }
      },500);
    })(arguments[0]);
    """, URL)


def remove_promos(driver):
    js(driver, """
      for(const sel of ["a[href*='tiktok']","a[href*='/create/']","a[href*='quick-actions']"])
        document.querySelectorAll(sel).forEach(a=>a.remove());
    """)


def reassert_route(driver):
    if "/tools/remove-background" not in driver.current_url:
        driver.get(URL)
        pin_tool_route(driver)
        remove_promos(driver)


def hide_onetrust(driver):
    js(driver, """
      const o=document.querySelector('#onetrust-consent-sdk');
      if(o){o.style.display='none';o.style.visibility='hidden';o.style.pointerEvents='none';}
    """)


def prepare_tool(driver):
    driver.get(URL)
    pin_tool_route(driver)
    remove_promos(driver)
    hide_onetrust(driver)
    wait_until_ready(driver)


# ===============================
# Upload flow
# ===============================
def wait_until_ready(driver, timeout=MAX_WAIT_READY_SEC):
    t = StepTimer("wait_until_ready")
    end = time.time() + timeout
    while time.time() < end:
        if deep_query_iframes_one(driver, "input[type='file']"):
            t.done("file input present")
            return True
        if deep_query_text_iframes(driver, r"(tap to upload|upload image|drag.*drop|upload)", "*"):
            t.done("upload CTA present")
            return True
        time.sleep(0.3)
    t.done("TIMEOUT")
    raise TimeoutError("Tool not ready")


def find_file_input_deep(driver, timeout=20):
    candidates = [
        "input#file-input",
        "[data-testid='qa-file-input'] input[type='file']",
        "sp-file-drop input[type='file']",
        "input[type='file'][accept*='image']",
        "input[type='file']",
    ]
    end = time.time() + timeout
    while time.time() < end:
        for sel in candidates:
            el = deep_query_iframes_one(driver, sel, timeout=0)
            if el:
                log(f"[upload] found file input via selector: {sel}")
                return el
        time.sleep(0.3)
    return None


def upload_file(driver, path_str):
    reassert_route(driver)
    hide_onetrust(driver)

    # 0) if input is already present, use it
    inp = find_file_input_deep(driver, timeout=3)
    if inp:
        log("[upload] using live input (attempt 1)")
        if send_keys_and_confirm(driver, inp, path_str):
            return
        log("[upload] live input did not accept file; trying alternate activation paths")

    log("[upload] clicking drop-zone container…")
    # 1) click the big container (not just the icon)
    for sel in [
        ".dropzone-content",
        ".dropzone-illustration",
        ".dropzone-icon",
        "h4.default-title",
        "h4.drop-title",
    ]:
        el = deep_query_iframes_one(driver, sel, timeout=0)
        if el:
            deep_click(driver, el)
            time.sleep(0.6)
            inp = find_file_input_deep(driver, timeout=3)
            if inp:
                log("[upload] input exposed after drop-zone click")
                if send_keys_and_confirm(driver, inp, path_str):
                    return

    # 2) click obvious upload CTAs
    for (regex, tag) in [
        (r"(tap to upload|upload image|drag.*drop|upload)", "*"),
        (r"\bupload\b", "button,sp-button,label,a,div,span,[role='button']")
    ]:
        hit = deep_query_text_iframes(driver, regex, tag)
        if hit:
            deep_click(driver, hit)
            time.sleep(0.6)
            inp = find_file_input_deep(driver, timeout=3)
            if inp:
                log("[upload] input exposed after CTA click")
                if send_keys_and_confirm(driver, inp, path_str):
                    return

    # 3) structural hooks
    for sel in [
        "label[for='file-input']",
        "[data-testid='qa-file-input']",
        "sp-file-drop",
        "#file-input",
    ]:
        el = deep_query_iframes_one(driver, sel, timeout=0)
        if el:
            deep_click(driver, el)
            time.sleep(0.6)
            inp = find_file_input_deep(driver, timeout=3)
            if inp:
                log("[upload] input exposed from structural hook")
                if send_keys_and_confirm(driver, inp, path_str):
                    return

    # 4) last try: re-click container and poll for input
    el = deep_query_iframes_one(driver, ".dropzone-content", timeout=0)
    if el:
        deep_click(driver, el)
        inp = find_file_input_deep(driver, timeout=8)
        if inp:
            log("[upload] input exposed after re-click")
            if send_keys_and_confirm(driver, inp, path_str):
                return

    raise RuntimeError(f"Upload did not bind expected file: {Path(path_str).name}")


# ===============================
# Processing / Download
# ===============================
def wait_until_processed_controls(driver, timeout=PROC_TIMEOUT):
    """
    Consider 'processed' when we can see either:
      - a Download button (by selector OR text), or
      - an Export control (selector OR text).
    Emits a heartbeat every ~2s so we know it's alive.
    """
    selectors = [
        "sp-button#downloadExportOption",
        "sp-button[data-testid='qa-download-export-button']",
        "sp-button[data-export-target='Download']",
        "[data-testid='qa-download-export-button']",
        "#downloadExportOption",
        "[data-export-target='Download']",
        "[data-export-option-id='downloadExportOption']",
        # Export entry points as well:
        "sp-button#export", "sp-action-group [role='menuitem']",
    ]

    t = StepTimer("process")
    log("[wait] waiting for processing to finish (Download/Export)…")
    end = time.time() + timeout
    next_beep = 0.0
    while time.time() < end:
        # 1) selectors first
        for sel in selectors:
            el = deep_query_iframes_one(driver, sel, timeout=0)
            if el:
                state = describe_control_state(driver, el)
                if state.get("enabled"):
                    log(f"[wait] controls ready by selector: {sel}")
                    t.done()
                    return True
                log(f"[wait] control seen but not ready: {sel} disabled={state.get('disabled')} text={state.get('text', '')!r}")

        if time.time() >= next_beep:
            log("[wait] still processing…")
            next_beep = time.time() + 2
        time.sleep(0.25)

    log("[wait] gave up – no Download/Export detected before timeout")
    t.done("TIMEOUT")
    return False


def _inner_button(driver, el):
    """If el is a Spectrum <sp-button>, return its inner <button> in shadow DOM; else el."""
    try:
        btn = js(driver, "return arguments[0].shadowRoot && arguments[0].shadowRoot.querySelector('button');", el)
        return btn or el
    except Exception:
        return el


def _find_download_button_with_frames(driver, timeout=DL_BTN_TIMEOUT):
    """
    Return (host_sp_button, inner_html_button, frame_chain) or (None, None, [])
    frame_chain is a list of iframe elements from top -> deepest that contain the button.
    """
    sels = [
        "sp-button#downloadExportOption",
        "sp-button[data-testid='qa-download-export-button']",
        "sp-button[data-export-target='Download']",
        "[data-testid='qa-download-export-button']",
        "#downloadExportOption",
        "[data-export-option-id='downloadExportOption']",
    ]
    end = time.time() + timeout
    while time.time() < end:
        host = None
        for sel in sels:
            host = deep_query_iframes_one(driver, sel, timeout=0)
            if host:
                break
        if not host:
            host = deep_query_text_iframes(driver, r"^\s*download\s*$", "*")
        if host:
            state = describe_control_state(driver, host)
            if not state.get("enabled"):
                time.sleep(0.25)
                continue
            inner = _inner_button(driver, host)
            frame_chain = driver.execute_script("""
                const el = arguments[0];
                function framesFor(node){
                  const chain=[];
                  let d = node && node.ownerDocument;
                  while (d && d.defaultView && d.defaultView.frameElement){
                    const fe = d.defaultView.frameElement;
                    chain.push(fe);
                    d = fe.ownerDocument;
                  }
                  return chain.reverse();
                }
                return framesFor(el);
            """, host)
            return host, inner, frame_chain or []
        time.sleep(0.25)
    return None, None, []


def _switch_into_frame_chain(driver, chain):
    driver.switch_to.default_content()
    for iframe_el in chain:
        try:
            driver.switch_to.frame(iframe_el)
        except Exception:
            driver.switch_to.default_content()
            return False
    return True


def click_js_then_native(driver, wait_new):
    """Try a few fast JS clicks; if nothing lands, fallback to native click."""
    # --- Stage A: up to 5 quick JS clicks (fast path) ---
    for attempt in range(1, 6):
        host, inner, _ = _find_download_button_with_frames(driver, timeout=DL_BTN_TIMEOUT)
        if not host:
            log(f"[dl] no download button found (attempt {attempt})")
            time.sleep(0.5)
            continue

        try:
            js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
            log(f"[dl] JS click attempt {attempt}")
        except Exception as e:
            log(f"[dl] JS click failed on attempt {attempt}: {e}")
            time.sleep(0.5)
            continue

        # Give each attempt a short window to land a file
        new_file = wait_new(timeout=2.0)
        if new_file:
            return new_file
        time.sleep(0.5)

    # --- Stage B: fallback to your existing native click (slower, but trusted) ---
    log("[dl] JS click attempts exhausted; falling back to native click")
    clicked = click_download_NATIVE(driver, post_click_wait_secs=1.0)
    return wait_new(timeout=MAX_WAIT_DL_SEC) if clicked else None


def click_download_NATIVE(driver, post_click_wait_secs=1.2) -> bool:
    """
    Use Selenium's native click *inside the owning iframe* so it's a trusted gesture.
    Robust to re-renders: re-finds the button inside the iframe a few times.
    Returns True if we sent a (native or JS) click.
    """
    reassert_route(driver);
    hide_onetrust(driver);
    _disable_overlays_temporarily(driver)

    # Locate the download host + iframe chain from top-level context
    host, inner, chain = _find_download_button_with_frames(driver, timeout=DL_BTN_TIMEOUT)
    if not host:
        log("[dl] download button not found for native click")
        return False

    # Try to switch into the iframe chain; if that fails, fall back to JS clicking the host
    if not _switch_into_frame_chain(driver, chain):
        log("[dl] failed to switch into iframe chain; falling back to JS click on host")
        try:
            driver.switch_to.default_content()
            js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
            time.sleep(post_click_wait_secs)
            return True
        except Exception:
            return False

    # Inside the correct iframe now — re-find & click a few times to ride out re-renders
    try:
        sels = [
            "sp-button#downloadExportOption",
            "sp-button[data-testid='qa-download-export-button']",
            "sp-button[data-export-target='Download']",
            "#downloadExportOption",
            "[data-export-option-id='downloadExportOption']",
            "[data-testid='qa-download-export-button']",
        ]

        def find_host_in_this_frame():
            # prefer explicit selectors
            for sel in sels:
                try:
                    el = driver.execute_script("return document.querySelector(arguments[0]);", sel)
                    if el:
                        return el
                except Exception:
                    pass
            # fallback: by visible text "Download", then walk up to sp-button if possible
            hit = None
            try:
                hit = driver.execute_script("""
                  const re=/^\\s*download\\s*$/i;
                  function findByText(root){
                    const all = root.querySelectorAll('*');
                    for(const n of all){
                      let t = '';
                      try{ t=(n.innerText||n.textContent||'').trim(); }catch(e){}
                      if(t && re.test(t)) return n;
                      if(n.shadowRoot){
                        const h = findByText(n.shadowRoot);
                        if(h) return h;
                      }
                    }
                    return null;
                  }
                  return findByText(document);
                """)
            except Exception:
                hit = None
            if hit:
                try:
                    return driver.execute_script("""
                      let n=arguments[0];
                      while(n){
                        if(n.tagName && n.tagName.toLowerCase()==='sp-button') return n;
                        n=n.parentNode||n.host;
                      }
                      return arguments[0];
                    """, hit)
                except Exception:
                    return hit
            return None

        def inner_button_of(host_el):
            try:
                b = driver.execute_script(
                    "return arguments[0] && arguments[0].shadowRoot && arguments[0].shadowRoot.querySelector('button');",
                    host_el
                )
                return b or host_el
            except Exception:
                return host_el

        attempts = 8
        for i in range(1, attempts + 1):
            # re-find the host each attempt (handles re-renders)
            try:
                host_here = find_host_in_this_frame()
            except Exception:
                host_here = None

            if not host_here:
                time.sleep(0.25)
                continue

            target = inner_button_of(host_here)

            try:
                # native pointer click
                ActionChains(driver).move_to_element(target).pause(0.05).click().perform()
                time.sleep(post_click_wait_secs)
                return True
            except Exception:
                # Try a direct element.click as a second swing this attempt
                try:
                    target.click()
                    time.sleep(post_click_wait_secs)
                    return True
                except Exception:
                    # small wait and retry (element may be mid re-render)
                    time.sleep(0.3)

        # Out of attempts inside iframe; fall back to JS host click in top doc
        log("[dl] native click attempts exhausted; falling back to JS host click")
        try:
            driver.switch_to.default_content()
            js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
            time.sleep(post_click_wait_secs)
            return True
        except Exception:
            return False

    finally:
        # Always revert to top-level context
        try:
            driver.switch_to.default_content()
        except Exception:
            pass


def _disable_overlays_temporarily(driver):
    js(driver, """
      const hide=(el)=>{ if(!el) return; el.__pe=el.style.pointerEvents; el.style.pointerEvents='none'; };
      const sels=[
        '#onetrust-consent-sdk','#onetrust-banner-sdk',
        '[aria-modal="true"]','[role="dialog"]',
        '[data-nosnippet="true"]','sp-toast'
      ];
      for(const sel of sels){ document.querySelectorAll(sel).forEach(hide); }
    """)


def wait_for_new_download():
    def snapshot():
        snap = {}
        for p in Path(DOWNLOAD_DIR).glob("*"):
            try:
                stat = p.stat()
                snap[p] = (stat.st_mtime_ns, stat.st_size)
            except FileNotFoundError:
                continue
        return snap

    before = snapshot()

    def wait_new(timeout=MAX_WAIT_DL_SEC):
        t = StepTimer("wait_for_download")
        end = time.time() + timeout
        last_print = 0
        while time.time() < end:
            after = snapshot()
            changed = []
            for p, meta in after.items():
                prev = before.get(p)
                if prev is None or prev != meta:
                    changed.append((p, meta))

            if changed:
                changed.sort(key=lambda item: item[1][0], reverse=True)
                for f, (_, size) in changed:
                    # handle Chrome .crdownload completing alongside an existing final name
                    if f.suffix.lower() == ".crdownload":
                        final = f.with_suffix("")
                        try:
                            if final.exists() and final.stat().st_size > 0:
                                log(f"[dl] detected completed: {final.name}")
                                t.done()
                                return final
                        except FileNotFoundError:
                            pass
                        continue

                    if size > 0:
                        log(f"[dl] detected: {f.name}")
                        t.done()
                        return f

            # Detect a final file materializing after a transient .crdownload vanished.
            removed_temp = [p for p in before if p.suffix.lower() == ".crdownload" and p not in after]
            if removed_temp:
                candidates = sorted(
                    (
                        p for p, (_, size) in after.items()
                        if p.suffix.lower() != ".crdownload" and size > 0
                    ),
                    key=lambda p: after[p][0],
                    reverse=True,
                )
                if candidates:
                    log(f"[dl] detected finalized file: {candidates[0].name}")
                    t.done()
                    return candidates[0]

            if time.time() - last_print > 2:
                log("[dl] waiting for file …")
                last_print = time.time()
            time.sleep(0.3)
        log("[dl] no file detected before timeout")
        t.done("TIMEOUT")
        return None

    return wait_new


def resize_in_place(jpg_path: Path, expect_w: int, expect_h: int) -> bool:
    """
    Resize the JPG at jpg_path to expect_w x expect_h *in place* (same filename).
    Returns True if resized, False if already the right size.
    Uses a short-lived .tmp.jpg in the same folder for safe replacement.
    """
    jpg_path = Path(jpg_path)
    with Image.open(jpg_path) as im:
        im = ImageOps.exif_transpose(im)  # honor EXIF orientation
        w, h = im.size
        if (w, h) == (expect_w, expect_h):
            return False
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        resized = im.resize((expect_w, expect_h), Image.LANCZOS)

    tmp_path = jpg_path.with_suffix(".tmp.jpg")
    # good quality, no chroma subsampling; tweak if you prefer smaller files
    resized.save(tmp_path, format="JPEG", quality=95, subsampling=0, optimize=True)
    tmp_path.replace(jpg_path)  # atomic-ish on the same volume
    return True


# ===============================
# Main
# ===============================
def main():
    session_t0 = time.perf_counter()
    results: List[FileResult] = []

    driver = build_driver()
    try:
        files = sorted(list(SRC_DIR.glob("*.jpg")))
        if not files:
            log(f"No JPGs found in {SRC_DIR}")
            return

        log(f"Found {len(files)} .jpg file(s) in {SRC_DIR}")

        with alive_bar(len(files), dual_line=True, title="Remove BG") as bar:
            for idx, jpg in enumerate(files, 1):
                per_t0 = time.perf_counter()
                fr = FileResult(name=jpg.name, status="")
                bar.text = f"→ {jpg.name}"
                log(f"[proc {idx}/{len(files)}] {jpg}")
                for attempt in range(1, MAX_FILE_ATTEMPTS + 1):
                    try:
                        # Navigate / get ready
                        if RELOAD_EACH_FILE or idx == 1 or attempt > 1:
                            bar.text = f"→ {jpg.name} : opening tool"
                            prepare_tool(driver)

                        # --- Size enforcement (pre-upload) ---
                        upload_path = str(jpg)  # stays the same (no temp filename to upload)
                        if ENFORCE_SIZE and (EXPECT_W > 0 and EXPECT_H > 0):
                            try:
                                t_rs = StepTimer("resize_in_place")
                                changed = resize_in_place(jpg, EXPECT_W, EXPECT_H)
                                t_rs.done("resized" if changed else "already 2000x3000")
                            except Exception as e:
                                fr.status = "SKIPPED"
                                fr.detail = f"size check/resize failed: {e}"
                                break

                        # Upload
                        bar.text = f"→ {jpg.name} : upload"
                        t_up = StepTimer("upload")
                        upload_file(driver, upload_path)
                        fr.sec_upload = t_up.done()

                        # Wait for controls
                        bar.text = f"→ {jpg.name} : processing"
                        t_proc = StepTimer("processing")
                        ok = wait_until_processed_controls(driver, timeout=PROC_TIMEOUT)
                        fr.sec_process = t_proc.done()
                        if not ok:
                            fr.status = "ERROR"
                            fr.detail = "Processing did not expose controls in time"
                            break

                        # Small pause before first download attempt
                        time.sleep(2.5)

                        # Download
                        bar.text = f"→ {jpg.name} : download"
                        t_dl = StepTimer("download")
                        wait_new = wait_for_new_download()
                        new_file = click_js_then_native(driver, wait_new)

                        # One quick JS host click as fallback (no canvas fallback)
                        if not new_file:
                            log("[dl] native click produced no file; retrying once with JS host click")
                            try:
                                host, inner, _ = _find_download_button_with_frames(driver, timeout=6)
                                if host:
                                    js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
                                    new_file = wait_new()
                            except Exception:
                                pass

                        if not new_file:
                            fr.status = "ERROR"
                            fr.detail = "No file downloaded (timed out)"
                            fr.sec_download = t_dl.done("TIMEOUT")
                            break

                        fr.sec_download = t_dl.done()

                        # Place final & move original
                        target = SRC_DIR / f"{jpg.stem}.png"
                        if target.exists():
                            target.unlink()
                        shutil.move(str(new_file), str(target))

                        dest_jpg = ORIG_DIR / jpg.name
                        if dest_jpg.exists():
                            dest_jpg.unlink()
                        shutil.move(str(jpg), str(dest_jpg))

                        fr.status = "OK"
                        fr.detail = f"{target.name}"
                        log(f"[done] {jpg.name} -> {target.name}")
                        break
                    except WebDriverException as e:
                        if is_browser_crash(e):
                            if attempt < MAX_FILE_ATTEMPTS:
                                log(f"[warn] browser crash while processing {jpg.name}; retrying (attempt {attempt + 1}/{MAX_FILE_ATTEMPTS})")
                                driver = restart_driver(driver, str(e))
                                continue
                            driver = restart_driver(driver, str(e))
                        fr.status = "ERROR"
                        fr.detail = f"Selenium failure: {str(e).splitlines()[0]}"
                        break
                    except Exception as e:
                        fr.status = "ERROR"
                        fr.detail = str(e).splitlines()[0] if str(e) else e.__class__.__name__
                        break

                fr.sec_total = time.perf_counter() - per_t0
                results.append(fr)
                if fr.status == "SKIPPED":
                    log(f"[skip] {jpg.name} – {fr.detail}")
                elif fr.status == "ERROR":
                    log(f"[error] {jpg.name} – {fr.detail}")
                bar()  # advance after finishing the file

                if idx < len(files) and RESTART_BROWSER_EACH_FILE:
                    driver = restart_driver(driver, f"recycling session after {jpg.name}")

        log("All done.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # ====== SUMMARY ======
    total_sec = time.perf_counter() - session_t0
    ok = sum(1 for r in results if r.status == "OK")
    skipped = sum(1 for r in results if r.status == "SKIPPED")
    err = sum(1 for r in results if r.status == "ERROR")
    log("====== SUMMARY ======")
    log(f"Files processed: {len(results)}  (OK: {ok}  Skipped: {skipped}  Errors: {err})")
    avg_ok = (sum(r.sec_total for r in results if r.status == 'OK') / max(1, ok))
    log(f"Total time: {total_sec:.2f}s  (avg per OK: {avg_ok:.2f}s )")


# Entrypoint
if __name__ == "__main__":
    main()
