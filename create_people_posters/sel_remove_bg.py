# sel_remove_bg.py
import argparse
import json
import os, time, shutil, subprocess, sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

from alive_progress import alive_bar

from PIL import Image, ImageOps

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
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


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "y")


# Chrome profile (keeps you signed in)
HEADLESS = env_bool("SEL_HEADLESS", "false")
URL = os.getenv("SEL_TOOL_URL", "https://new.express.adobe.com/tools/remove-background")
HEADED_USER_DATA_DIR = os.getenv("SEL_USER_DATA_DIR", str(CONFIG_DIR / "chrome-profile"))
HEADED_PROFILE_DIR = os.getenv("SEL_PROFILE_DIR", "Profile 1")
HEADLESS_USER_DATA_DIR = os.getenv("SEL_HEADLESS_USER_DATA_DIR", str(CONFIG_DIR / "chrome-profile-headless"))
HEADLESS_PROFILE_DIR = os.getenv("SEL_HEADLESS_PROFILE_DIR", "Default")
USER_DATA_DIR = HEADLESS_USER_DATA_DIR if HEADLESS else HEADED_USER_DATA_DIR
PROFILE_DIR = HEADLESS_PROFILE_DIR if HEADLESS else HEADED_PROFILE_DIR
HEADLESS_REMOTE_DEBUGGING_PIPE = env_bool("SEL_HEADLESS_REMOTE_DEBUGGING_PIPE", "true")
HEADLESS_FALLBACK_TO_HEADED = env_bool("SEL_HEADLESS_FALLBACK_TO_HEADED", "true")
HEADLESS_FALLBACK_TO_USER_PROFILE = env_bool("SEL_HEADLESS_FALLBACK_TO_USER_PROFILE", "true")
HEADLESS_FALLBACK_TO_HEADED_PROFILE = env_bool("SEL_HEADLESS_FALLBACK_TO_HEADED_PROFILE", "true")

# Normalize to absolute paths even if .env uses relative paths
SRC_DIR = Path(os.getenv("SEL_SRC_DIR", str(Path.cwd()))).resolve()
ORIG_DIR = Path(os.getenv("SEL_ORIG_DIR", str(Path.cwd() / "original"))).resolve()
DOWNLOAD_DIR = Path(os.getenv("SEL_DOWNLOAD_DIR", str(Path.cwd() / "sel_downloads"))).resolve()

# Flow & patience knobs
MAX_WAIT_READY_SEC = int(os.getenv("SEL_MAX_WAIT_READY_SEC", "120"))
PROC_TIMEOUT = int(os.getenv("SEL_PROC_TIMEOUT", "120"))  # wait for processing (Download visible)
DISABLED_DOWNLOAD_STALL_SEC = max(0, int(os.getenv("SEL_DISABLED_DOWNLOAD_STALL_SEC", "45")))
NO_DOWNLOAD_CONTROL_STALL_SEC = max(0, int(os.getenv("SEL_NO_DOWNLOAD_CONTROL_STALL_SEC", "75")))
MAX_WAIT_DL_SEC = int(os.getenv("SEL_MAX_WAIT_DL_SEC", "240"))  # wait for file to appear
DL_BTN_TIMEOUT = int(os.getenv("SEL_DL_BUTTON_TIMEOUT", "20"))  # how long to wait for button to be found
FAST_DL_CHECK_SEC = max(2, int(os.getenv("SEL_FAST_DL_CHECK_SEC", "6")))
RELOAD_EACH_FILE = env_bool("SEL_RELOAD_EACH_FILE", "true")
RESTART_BROWSER_EACH_FILE = env_bool("SEL_RESTART_BROWSER_EACH_FILE", "true")
MAX_FILE_ATTEMPTS = max(1, int(os.getenv("SEL_MAX_FILE_ATTEMPTS", "2")))
PROMPT_FOR_LOGIN = env_bool("SEL_PROMPT_FOR_LOGIN", "true")
LOGIN_WAIT_SEC = max(30, int(os.getenv("SEL_LOGIN_WAIT_SEC", "900")))
DISABLE_CHROME_RESTORE = env_bool("SEL_DISABLE_CHROME_RESTORE", "true")
MAX_TOOL_READY_RESTARTS = max(1, int(os.getenv("SEL_MAX_TOOL_READY_RESTARTS", "5")))

# Size enforcement
EXPECT_W = int(os.getenv("SEL_EXPECT_WIDTH", "2000"))
EXPECT_H = int(os.getenv("SEL_EXPECT_HEIGHT", "3000"))
ENFORCE_SIZE = env_bool("SEL_ENFORCE_SIZE", "true")

# Make sure folders exist
SRC_DIR.mkdir(parents=True, exist_ok=True)
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
ORIG_DIR.mkdir(parents=True, exist_ok=True)


# ===============================
# Tiny logging helpers
# ===============================
def now_ts() -> str:
    return time.strftime("%H:%M:%S")


LOG_FILE = LOGS_DIR / "sel_remove_bg.log"
CHROMEDRIVER_LOG_FILE = LOGS_DIR / "chromedriver.log"
EFFECTIVE_USER_DATA_DIR = Path(USER_DATA_DIR).resolve()
EFFECTIVE_PROFILE_DIR = PROFILE_DIR
EFFECTIVE_HEADLESS = HEADLESS
ACTIVE_STARTUP_OVERRIDE: Optional[tuple[str, str, bool]] = None


def parse_window_size(raw: str) -> tuple[int, int]:
    try:
        w_raw, h_raw = raw.lower().replace("x", ",").split(",", 1)
        w = max(800, int(w_raw.strip()))
        h = max(600, int(h_raw.strip()))
        return w, h
    except Exception:
        return 1400, 1000


WINDOW_W, WINDOW_H = parse_window_size(os.getenv("SEL_WINDOW_SIZE", "1400,1000"))


def log(msg: str) -> None:
    line = f"[{now_ts()}] {msg}"
    print(line)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_console_line_if_available(buffer: List[str]) -> Optional[str]:
    """
    Non-blocking console line read.

    input() cannot enforce LOGIN_WAIT_SEC because it blocks until Enter. This
    helper lets the login loop keep checking Adobe and the timeout deadline.
    """
    if os.name == "nt":
        try:
            import msvcrt
        except Exception:
            return None

        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                print()
                response = "".join(buffer).strip().lower()
                buffer.clear()
                return response
            if ch == "\003":
                raise KeyboardInterrupt
            if ch == "\b":
                if buffer:
                    buffer.pop()
                    print("\b \b", end="", flush=True)
                continue
            if ch in ("\x00", "\xe0"):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                continue
            buffer.append(ch)
            print(ch, end="", flush=True)
        return None

    try:
        import select
        readable, _, _ = select.select([sys.stdin], [], [], 0)
    except Exception:
        return None

    if not readable:
        return None
    line = sys.stdin.readline()
    if line == "":
        return None
    return line.strip().lower()


def resolve_profile_directory(user_data_dir: Path, requested_profile: str) -> Optional[str]:
    requested_profile = (requested_profile or "").strip()
    if not requested_profile:
        return None

    requested_path = user_data_dir / requested_profile
    if requested_path.is_dir():
        return requested_profile

    fallback_candidates: List[str] = []
    if (user_data_dir / "Default").is_dir():
        fallback_candidates.append("Default")

    for child in sorted(user_data_dir.iterdir()):
        if child.is_dir() and child.name.startswith("Profile "):
            fallback_candidates.append(child.name)

    for candidate in fallback_candidates:
        if candidate != requested_profile:
            log(
                f"[chrome] requested profile '{requested_profile}' not found in "
                f"{user_data_dir}; falling back to '{candidate}'"
            )
            return candidate

    log(
        f"[chrome] requested profile '{requested_profile}' not found in "
        f"{user_data_dir}; starting without --profile-directory"
    )
    return None


def cleanup_profile_locks(user_data_dir: Path, profile_dir: Optional[str]) -> None:
    """
    Remove stale Chrome lock files from this dedicated automation profile.
    """
    candidates = [
        user_data_dir / "SingletonLock",
        user_data_dir / "SingletonCookie",
        user_data_dir / "SingletonSocket",
        user_data_dir / "lockfile",
    ]
    if profile_dir:
        candidates.extend([
            user_data_dir / profile_dir / "LOCK",
            user_data_dir / profile_dir / ".org.chromium.Chromium.*",
        ])

    removed = []
    for candidate in candidates:
        if "*" in candidate.name:
            for match in candidate.parent.glob(candidate.name):
                try:
                    if match.exists():
                        match.unlink()
                        removed.append(str(match))
                except Exception:
                    pass
            continue
        try:
            if candidate.exists():
                candidate.unlink()
                removed.append(str(candidate))
        except Exception:
            pass

    if removed:
        log(f"[chrome] removed stale profile lock file(s): {', '.join(removed)}")


def mark_profile_clean_exit(user_data_dir: Path, profile_dir: Optional[str]) -> None:
    """
    Suppress Chrome's crash/session restore bubble for this automation profile.
    This preserves cookies and login state; it only clears the dirty-exit flags.
    """
    paths = [user_data_dir / "Local State"]
    if profile_dir:
        paths.append(user_data_dir / profile_dir / "Preferences")

    updated = []
    for pref_path in paths:
        if not pref_path.is_file():
            continue
        try:
            data = json.loads(pref_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log(f"[chrome] could not read clean-exit prefs from {pref_path}: {exc}")
            continue

        changed = False
        profile = data.setdefault("profile", {})
        if profile.get("exit_type") != "Normal":
            profile["exit_type"] = "Normal"
            changed = True
        if profile.get("exited_cleanly") is not True:
            profile["exited_cleanly"] = True
            changed = True

        if not changed:
            continue

        try:
            pref_path.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            updated.append(str(pref_path))
        except Exception as exc:
            log(f"[chrome] could not write clean-exit prefs to {pref_path}: {exc}")

    if updated:
        log(f"[chrome] marked profile clean to suppress restore bubble: {', '.join(updated)}")


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


class AdobeLoginRequiredError(RuntimeError):
    """Raised when Adobe blocks download until the user logs in."""


class StaleAdobeProjectStateError(RuntimeError):
    """Raised when Adobe opens a reused project chooser instead of the fresh upload page."""


# ===============================
# Driver
# ===============================
def build_chrome_options(user_data_dir: Path, profile_dir: Optional[str], *, headless: bool, use_pipe: bool) -> Options:
    opts = Options()
    opts.add_argument(f"--user-data-dir={user_data_dir}")
    if profile_dir:
        opts.add_argument(f"--profile-directory={profile_dir}")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-features=PrivacySandboxAdsAPIs")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    if DISABLE_CHROME_RESTORE:
        opts.add_argument("--hide-crash-restore-bubble")
        opts.add_argument("--disable-session-crashed-bubble")
        opts.add_argument("--restore-last-session=false")
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        if use_pipe:
            opts.add_argument("--remote-debugging-pipe")
        else:
            opts.add_argument("--remote-debugging-port=0")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument(f"--window-size={WINDOW_W},{WINDOW_H}")
    else:
        opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(DOWNLOAD_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.exit_type": "Normal",
        "profile.exited_cleanly": True,
    })
    return opts


def prepare_chrome_profile(user_data_dir_raw: str, profile_dir_raw: str) -> tuple[Path, Optional[str]]:
    user_data_dir = Path(user_data_dir_raw).resolve()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    profile_dir = resolve_profile_directory(user_data_dir, profile_dir_raw)
    cleanup_profile_locks(user_data_dir, profile_dir)
    if DISABLE_CHROME_RESTORE:
        mark_profile_clean_exit(user_data_dir, profile_dir)
    return user_data_dir, profile_dir


def build_driver(force_headed: bool = False):
    global EFFECTIVE_USER_DATA_DIR, EFFECTIVE_PROFILE_DIR, EFFECTIVE_HEADLESS, ACTIVE_STARTUP_OVERRIDE
    if ACTIVE_STARTUP_OVERRIDE and not force_headed:
        startup_user_data_dir, startup_profile_dir, startup_headless = ACTIVE_STARTUP_OVERRIDE
    else:
        startup_user_data_dir = USER_DATA_DIR
        startup_profile_dir = PROFILE_DIR
        startup_headless = HEADLESS

    configured_headless = startup_headless and not force_headed
    primary_user_data_dir, primary_profile_dir = prepare_chrome_profile(startup_user_data_dir, startup_profile_dir)
    EFFECTIVE_USER_DATA_DIR = primary_user_data_dir
    EFFECTIVE_PROFILE_DIR = primary_profile_dir or "<none>"

    attempts = []
    if configured_headless:
        attempts.append(("headless", primary_user_data_dir, primary_profile_dir, True, HEADLESS_REMOTE_DEBUGGING_PIPE))
        if HEADLESS_REMOTE_DEBUGGING_PIPE:
            attempts.append(("headless", primary_user_data_dir, primary_profile_dir, True, False))
        headed_user_data_dir, headed_profile_dir = prepare_chrome_profile(HEADED_USER_DATA_DIR, HEADED_PROFILE_DIR)
        if HEADLESS_FALLBACK_TO_USER_PROFILE and headed_user_data_dir != primary_user_data_dir:
            attempts.append(("headless user profile fallback", headed_user_data_dir, headed_profile_dir, True, HEADLESS_REMOTE_DEBUGGING_PIPE))
            if HEADLESS_REMOTE_DEBUGGING_PIPE:
                attempts.append(("headless user profile fallback", headed_user_data_dir, headed_profile_dir, True, False))
        if HEADLESS_FALLBACK_TO_HEADED:
            attempts.append(("headed fallback", primary_user_data_dir, primary_profile_dir, False, False))
            if (
                HEADLESS_FALLBACK_TO_HEADED_PROFILE
                and headed_user_data_dir != primary_user_data_dir
            ):
                attempts.append(("headed profile fallback", headed_user_data_dir, headed_profile_dir, False, False))
    else:
        attempts.append(("headed", primary_user_data_dir, primary_profile_dir, False, False))

    try:
        CHROMEDRIVER_LOG_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    errors = []
    driver = None
    driver_headless = False
    driver_user_data_dir = primary_user_data_dir
    driver_profile_dir = primary_profile_dir
    for label, attempt_user_data_dir, attempt_profile_dir, headless_mode, use_pipe in attempts:
        opts = build_chrome_options(
            attempt_user_data_dir,
            attempt_profile_dir,
            headless=headless_mode,
            use_pipe=use_pipe,
        )
        service = Service(log_output=str(CHROMEDRIVER_LOG_FILE))
        try:
            driver = webdriver.Chrome(options=opts, service=service)
            driver_headless = headless_mode
            if label == "headed fallback":
                log("[chrome] headless startup failed; using headed fallback with the same automation profile")
            elif label == "headless user profile fallback":
                log("[chrome] headless profile startup failed; using normal automation profile in headless mode")
            elif label == "headed profile fallback":
                log("[chrome] headless profile startup failed; using normal headed automation profile")
            driver_user_data_dir = attempt_user_data_dir
            driver_profile_dir = attempt_profile_dir
            if (
                configured_headless
                and (
                    not headless_mode
                    or attempt_user_data_dir != primary_user_data_dir
                    or attempt_profile_dir != primary_profile_dir
                )
            ):
                ACTIVE_STARTUP_OVERRIDE = (
                    str(attempt_user_data_dir),
                    attempt_profile_dir or "",
                    headless_mode,
                )
                log("[chrome] reusing this fallback mode for future browser restarts in this run")
            break
        except Exception as exc:
            detail = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            pipe_detail = "pipe" if use_pipe else "port"
            errors.append(f"{label}/{pipe_detail} [{attempt_user_data_dir}]: {detail}")
            if (label, attempt_user_data_dir, attempt_profile_dir, headless_mode, use_pipe) != attempts[-1]:
                log(f"[chrome] startup failed for {label} ({pipe_detail}); trying next mode")

    if driver is None:
        mode = "headless" if configured_headless else "headed"
        profile_hint = (
            " For headless mode, run `python sel_remove_bg.py --login-only` once to sign into the separate "
            "headless profile in a visible browser, set SEL_HEADLESS=false, or use a fresh SEL_HEADLESS_USER_DATA_DIR."
            if configured_headless else
            " Close any Chrome windows using this automation profile and retry."
        )
        detail = (
            f"Chrome failed to start in {mode} mode with user-data dir '{primary_user_data_dir}'"
            + (f" and profile '{primary_profile_dir}'" if primary_profile_dir else "")
            + f". Attempts: {'; '.join(errors)}.{profile_hint} "
            + f"ChromeDriver log: {CHROMEDRIVER_LOG_FILE.resolve()}"
        )
        raise RuntimeError(detail)

    EFFECTIVE_USER_DATA_DIR = driver_user_data_dir
    EFFECTIVE_PROFILE_DIR = driver_profile_dir or "<none>"
    EFFECTIVE_HEADLESS = driver_headless
    if driver_headless:
        driver.set_window_size(WINDOW_W, WINDOW_H)
    else:
        try:
            driver.maximize_window()
        except Exception:
            driver.set_window_size(WINDOW_W, WINDOW_H)

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


def wait_for_upload_acceptance(driver, expected_name: str, timeout: float = 8.0):
    """
    Confirm the upload was accepted.

    Adobe Express now re-renders the file input immediately after send_keys(),
    so the old "input still contains the file name" check is no longer reliable.
    We accept any of these as success:
      - a live file input still reports the expected file
      - an upload/progress indicator appears
      - the Download control appears (even if disabled while processing)
      - the page title changes to the per-project title
    """
    script = r"""
    const expected = arguments[0].toLowerCase();

    function scanRoot(root){
      const out = {
        inputs: [],
        hasProgress: false,
        hasDownloadControl: false,
        downloadDisabled: false
      };

      const all = root.querySelectorAll ? root.querySelectorAll('input[type="file"]') : [];
      for (const el of all){
        try{
          const files = el.files || [];
          const first = files[0];
          out.inputs.push({
            count: files.length || 0,
            name: first && first.name ? String(first.name) : ''
          });
        }catch(e){}
      }

      const progressSel = [
        '[role="progressbar"]',
        'sp-progress-circle',
        'sp-progressbar',
        'qa-progress'
      ];
      for (const sel of progressSel){
        try{
          if (root.querySelector && root.querySelector(sel)){
            out.hasProgress = true;
            break;
          }
        }catch(e){}
      }

      const downloadSel = [
        'sp-button#downloadExportOption',
        'sp-button[data-testid="qa-download-export-button"]',
        'sp-button[data-export-target="Download"]',
        '[data-testid="qa-download-export-button"]',
        '#downloadExportOption',
        '[data-export-target="Download"]',
        '[data-export-option-id="downloadExportOption"]'
      ];
      for (const sel of downloadSel){
        try{
          const btn = root.querySelector && root.querySelector(sel);
          if (!btn) continue;
          out.hasDownloadControl = true;
          const disabled =
            !!btn.disabled ||
            btn.getAttribute('disabled') !== null ||
            btn.getAttribute('aria-disabled') === 'true';
          out.downloadDisabled = out.downloadDisabled || disabled;
          break;
        }catch(e){}
      }

      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!n.shadowRoot) continue;
        const child = scanRoot(n.shadowRoot);
        out.inputs.push(...child.inputs);
        out.hasProgress = out.hasProgress || child.hasProgress;
        out.hasDownloadControl = out.hasDownloadControl || child.hasDownloadControl;
        out.downloadDisabled = out.downloadDisabled || child.downloadDisabled;
      }
      return out;
    }

    let found = scanRoot(document);
    for (const f of document.querySelectorAll('iframe')){
      try{
        const d = f.contentDocument || f.contentWindow?.document;
        if (!d) continue;
        const child = scanRoot(d);
        found.inputs.push(...child.inputs);
        found.hasProgress = found.hasProgress || child.hasProgress;
        found.hasDownloadControl = found.hasDownloadControl || child.hasDownloadControl;
        found.downloadDisabled = found.downloadDisabled || child.downloadDisabled;
      }catch(e){}
    }

    for (const item of found.inputs){
      if (item.count > 0 && item.name.toLowerCase() === expected){
        return {
          accepted: true,
          matched: true,
          count: item.count,
          name: item.name,
          hasProgress: found.hasProgress,
          hasDownloadControl: found.hasDownloadControl,
          downloadDisabled: found.downloadDisabled,
          title: document.title || ''
        };
      }
    }

    const title = String(document.title || '');
    const titleLooksUploaded = /remove background project/i.test(title);
    const accepted = !!(found.hasProgress || found.hasDownloadControl || titleLooksUploaded);
    const first = found.inputs[0] || {count: 0, name: ''};

    return {
      accepted,
      matched: false,
      count: first.count || 0,
      name: first.name || '',
      hasProgress: found.hasProgress,
      hasDownloadControl: found.hasDownloadControl,
      downloadDisabled: found.downloadDisabled,
      title
    };
    """
    end = time.time() + timeout
    last_state = {"accepted": False, "matched": False, "count": 0, "name": ""}
    while time.time() < end:
        try:
            state = driver.execute_script(script, expected_name)
        except Exception:
            state = {"accepted": False, "matched": False, "count": 0, "name": ""}
        if state.get("accepted"):
            return state
        last_state = state
        time.sleep(0.25)
    return last_state


def send_keys_and_confirm(driver, inp, path_str: str) -> bool:
    expected_name = Path(path_str).name
    try:
        inp.send_keys(path_str)
    except StaleElementReferenceException:
        log("[upload] file input re-rendered during send_keys; checking for processing state")
    state = wait_for_upload_acceptance(driver, expected_name, timeout=8.0)
    if state.get("matched"):
        log(f"[upload] confirmed file input holds: {state.get('name', '')}")
        return True
    if state.get("accepted"):
        signals = []
        if state.get("hasProgress"):
            signals.append("progress visible")
        if state.get("hasDownloadControl"):
            if state.get("downloadDisabled"):
                signals.append("download control visible (disabled while processing)")
            else:
                signals.append("download control visible")
        title = state.get("title", "")
        if title:
            signals.append(f"title={title!r}")
        log(f"[upload] upload accepted via UI transition: {', '.join(signals)}")
        return True
    log(
        f"[upload] send_keys did not bind expected file: expected={expected_name!r} "
        f"seen={state.get('name', '')!r} count={state.get('count', 0)} "
        f"progress={state.get('hasProgress', False)} download={state.get('hasDownloadControl', False)} "
        f"title={state.get('title', '')!r}"
    )
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


def detect_start_from_image_modal(driver) -> bool:
    script = r"""
    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    }
    function textOf(el){
      try { return String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); } catch(e) { return ''; }
    }
    function scan(root){
      const dialogs = root.querySelectorAll ? root.querySelectorAll('[aria-modal="true"], [role="dialog"], sp-dialog[open], .modal, [class*="modal"], [class*="dialog"]') : [];
      for (const dialog of dialogs){
        if (!visible(dialog)) continue;
        const text = textOf(dialog);
        if (/start from your image/i.test(text) && /remove background/i.test(text))
          return true;
      }
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!n.shadowRoot) continue;
        if (scan(n.shadowRoot)) return true;
      }
      return false;
    }
    if (scan(document)) return true;
    for (const f of document.querySelectorAll('iframe')){
      try {
        const d = f.contentDocument || f.contentWindow?.document;
        if (d && scan(d)) return true;
      } catch(e) {}
    }
    return false;
    """
    try:
        return bool(driver.execute_script(script))
    except Exception:
        return False


def dismiss_stale_modals(driver) -> int:
    """
    Handle non-auth Adobe overlays that can block the upload/remove-background
    surface after a previous file. Auth modals are left alone so the login
    handler can report them accurately. The "Start from your image" chooser is
    treated as stale state and handled by restarting the browser.
    """
    if detect_start_from_image_modal(driver):
        raise StaleAdobeProjectStateError(
            "Adobe opened the stale 'Start from your image' chooser instead of the fresh Remove background upload page"
        )

    script = r"""
    const clicked = [];
    const authRe = /sign up for free to download your file|sign in|download your file/i;
    const skipButtonRe = /^(close|dismiss|not now|maybe later|cancel|start over|start again|replace|replace image|new file|new image|upload new|try another)$/i;

    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    }
    function textOf(el){
      try { return String(el.innerText || el.textContent || '').trim(); } catch(e) { return ''; }
    }
    function clickTarget(el){
      if (!el) return false;
      try {
        const inner = el.shadowRoot && el.shadowRoot.querySelector('button');
        (inner || el).click();
        return true;
      } catch(e) {
        return false;
      }
    }
    function clickableAncestor(el, stopAt){
      let node = el;
      while (node && node !== stopAt){
        try {
          const tag = String(node.tagName || '').toLowerCase();
          const role = String(node.getAttribute?.('role') || '').toLowerCase();
          const style = getComputedStyle(node);
          if (
            tag === 'button' || tag === 'sp-button' || tag === 'a' ||
            role === 'button' || node.tabIndex >= 0 || !!node.onclick ||
            style.cursor === 'pointer'
          ){
            return node;
          }
        } catch(e) {}
        node = node.parentElement || node.getRootNode?.().host || null;
      }
      return el;
    }
    function scan(root){
      const dialogs = root.querySelectorAll ? root.querySelectorAll('[aria-modal="true"], [role="dialog"], sp-dialog[open], qa-error-modal, .modal, [class*="modal"], [class*="dialog"]') : [];
      for (const dialog of dialogs){
        if (!visible(dialog)) continue;
        const text = textOf(dialog);
        if (authRe.test(text)) continue;
        if (/start from your image/i.test(text) && /remove background/i.test(text)) continue;

        const buttons = dialog.querySelectorAll ? Array.from(dialog.querySelectorAll('button, sp-button, [role="button"], a')) : [];
        for (const btn of buttons){
          const label = textOf(btn) || btn.getAttribute?.('aria-label') || btn.getAttribute?.('title') || '';
          if (skipButtonRe.test(String(label).trim()) || btn.getAttribute?.('aria-label') === 'Close'){
            if (clickTarget(btn)){
              clicked.push(label || 'close');
              return;
            }
          }
        }

        const close = dialog.querySelector && dialog.querySelector('[aria-label="Close"], [aria-label="close"], button[title="Close"], sp-button[title="Close"]');
        if (close){
          if (clickTarget(close)){
            clicked.push('close');
            return;
          }
        }
      }

      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (n.shadowRoot) scan(n.shadowRoot);
      }
    }

    scan(document);
    for (const f of document.querySelectorAll('iframe')){
      try {
        const d = f.contentDocument || f.contentWindow?.document;
        if (d) scan(d);
      } catch(e) {}
    }
    return clicked;
    """
    try:
        clicked = driver.execute_script(script) or []
    except Exception:
        return 0
    if clicked:
        labels = ", ".join(str(item) for item in clicked[:5])
        log(f"[modal] handled Adobe modal control(s): {labels}")
    return len(clicked)


def prepare_tool(driver):
    driver.get(URL)
    pin_tool_route(driver)
    remove_promos(driver)
    hide_onetrust(driver)
    dismiss_stale_modals(driver)
    wait_until_ready(driver)


def prepare_fresh_tool(driver):
    for restart_idx in range(0, MAX_TOOL_READY_RESTARTS + 1):
        try:
            prepare_tool(driver)
            return driver
        except StaleAdobeProjectStateError as exc:
            if restart_idx >= MAX_TOOL_READY_RESTARTS:
                raise
            log(
                f"[browser] stale Adobe project chooser detected; restarting Chrome "
                f"({restart_idx + 1}/{MAX_TOOL_READY_RESTARTS}): {exc}"
            )
            driver = restart_driver(driver, "stale Adobe project chooser")
    return driver


# ===============================
# Upload flow
# ===============================
def wait_until_ready(driver, timeout=MAX_WAIT_READY_SEC):
    t = StepTimer("wait_until_ready")
    end = time.time() + timeout
    while time.time() < end:
        if detect_start_from_image_modal(driver):
            raise StaleAdobeProjectStateError(
                "Adobe opened the stale 'Start from your image' chooser while waiting for the upload page"
            )
        if deep_query_iframes_one(driver, "input[type='file']"):
            if not deep_query_text_iframes(driver, r"\bremove background\b", "*"):
                time.sleep(0.3)
                continue
            t.done("file input present")
            return True
        if (
            deep_query_text_iframes(driver, r"(tap to upload|upload image|drag.*drop|upload)", "*")
            and deep_query_text_iframes(driver, r"\bremove background\b", "*")
        ):
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
    dismiss_stale_modals(driver)

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
    disabled_since = None
    last_disabled = None
    no_control_since = time.time()
    while time.time() < end:
        dismiss_stale_modals(driver)
        disabled_seen = None
        # 1) selectors first
        for sel in selectors:
            el = deep_query_iframes_one(driver, sel, timeout=0)
            if el:
                state = describe_control_state(driver, el)
                if state.get("enabled"):
                    log(f"[wait] controls ready by selector: {sel}")
                    t.done()
                    return True
                disabled_seen = (sel, state)
                last_disabled = disabled_seen

        now = time.time()
        if disabled_seen:
            no_control_since = now
            if disabled_since is None:
                disabled_since = now
            disabled_for = now - disabled_since
            if DISABLED_DOWNLOAD_STALL_SEC and disabled_for >= DISABLED_DOWNLOAD_STALL_SEC:
                sel, state = disabled_seen
                log(
                    f"[wait] Download/Export stayed disabled for {disabled_for:.1f}s "
                    f"({sel} text={state.get('text', '')!r}); treating as retryable processing stall"
                )
                t.done("DISABLED_STALL")
                return False
        else:
            disabled_since = None
            no_control_for = now - no_control_since
            if NO_DOWNLOAD_CONTROL_STALL_SEC and no_control_for >= NO_DOWNLOAD_CONTROL_STALL_SEC:
                log(
                    f"[wait] no Download/Export control appeared for {no_control_for:.1f}s; "
                    "treating as retryable processing stall"
                )
                t.done("NO_CONTROL_STALL")
                return False

        if now >= next_beep:
            if disabled_since is not None and last_disabled:
                sel, state = last_disabled
                log(
                    f"[wait] Download/Export visible but disabled for {now - disabled_since:.1f}s: "
                    f"{sel} text={state.get('text', '')!r}"
                )
            else:
                log(f"[wait] still processing; no Download/Export control for {now - no_control_since:.1f}s")
            next_beep = now + 2
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
        new_file = wait_new(timeout=FAST_DL_CHECK_SEC)
        if new_file:
            return new_file
        if resolve_download_blocker(driver):
            continue
        time.sleep(0.5)

    # --- Stage B: fallback to your existing native click (slower, but trusted) ---
    log("[dl] JS click attempts exhausted; falling back to native click")
    clicked = click_download_NATIVE(driver, post_click_wait_secs=1.0)
    if not clicked:
        return None
    new_file = wait_new(timeout=MAX_WAIT_DL_SEC)
    if new_file:
        return new_file
    if resolve_download_blocker(driver):
        return click_js_then_native(driver, wait_new)
    return None


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


def download_button_still_ready(driver) -> bool:
    """
    Return True when the page still shows an enabled Download control.
    This helps ignore stale auth components that remain mounted in the DOM.
    """
    sels = [
        "sp-button#downloadExportOption",
        "sp-button[data-testid='qa-download-export-button']",
        "sp-button[data-export-target='Download']",
        "[data-testid='qa-download-export-button']",
        "#downloadExportOption",
        "[data-export-option-id='downloadExportOption']",
    ]
    try:
        host = None
        for sel in sels:
            host = deep_query_iframes_one(driver, sel, timeout=0)
            if host:
                break
        if not host:
            host = deep_query_text_iframes(driver, r"^\s*download\s*$", "*")
        if not host:
            return False
        state = describe_control_state(driver, host)
        return bool(state.get("enabled"))
    except Exception:
        return False


def detect_download_blocker(driver) -> str:
    """
    Return a human-readable Adobe blocker message if download is gated.
    """
    script = r"""
    function isVisible(el){
      try{
        if (!el) return false;
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (
          style.display !== 'none' &&
          style.visibility !== 'hidden' &&
          style.opacity !== '0' &&
          rect.width > 0 &&
          rect.height > 0
        );
      }catch(e){
        return false;
      }
    }

    function textOf(el){
      try{
        return ((el.innerText || el.textContent || '') + '').replace(/\s+/g, ' ').trim();
      }catch(e){
        return '';
      }
    }

    function scanRoot(root){
      const checks = [
        ['qa-authentication-modal', 'auth'],
        ['qa-error-modal', 'error'],
      ];

      for (const [sel, kind] of checks){
        let nodes = [];
        try{
          nodes = Array.from(root.querySelectorAll(sel));
        }catch(e){}
        for (const node of nodes){
          const dialog =
            (node.shadowRoot && node.shadowRoot.querySelector('sp-dialog[open], [role="dialog"]')) ||
            (node.querySelector && node.querySelector('sp-dialog[open], [role="dialog"]')) ||
            node;
          if (!isVisible(dialog) && !isVisible(node))
            continue;

          const text = textOf(dialog) || textOf(node);
          if (!text)
            continue;

          if (kind === 'auth' && /sign up for free to download your file|sign in|download your file/i.test(text)){
            return { kind, text };
          }
          if (kind === 'error' && /unknown error|please try again|error/i.test(text)){
            return { kind, text };
          }
        }
      }

      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!n.shadowRoot) continue;
        const hit = scanRoot(n.shadowRoot);
        if (hit) return hit;
      }
      return null;
    }

    return scanRoot(document);
    """
    try:
        hit = driver.execute_script(script)
    except Exception:
        return ""

    if not hit:
        return ""

    text = (hit.get("text") or "").strip()
    kind = (hit.get("kind") or "").strip().lower()
    if kind == "auth":
        return f"Adobe login required before download: {text}"
    if kind == "error":
        return f"Adobe reported a download error: {text}"
    return text


def prompt_for_adobe_login(driver) -> bool:
    """
    Keep the browser open and let the user complete Adobe login in-place.
    Returns True once the auth gate disappears, else False.
    """
    blocker = detect_download_blocker(driver)
    if "Adobe login required before download:" not in blocker:
        return True

    log("[auth] Adobe login is required before files can be downloaded.")
    log(f"[auth] Browser profile: {EFFECTIVE_USER_DATA_DIR} [{EFFECTIVE_PROFILE_DIR}]")

    if HEADLESS:
        log("[auth] Headless mode is active, so interactive Adobe login cannot be completed in this run.")
        return False

    log("[auth] Finish the Adobe sign-in/sign-up in the open Chrome window.")

    if not PROMPT_FOR_LOGIN:
        log("[auth] Interactive login prompting is disabled by SEL_PROMPT_FOR_LOGIN=false.")
        return False

    if not sys.stdin or not sys.stdin.isatty():
        log("[auth] No interactive terminal is attached, so login cannot be confirmed automatically.")
        return False

    deadline = time.time() + LOGIN_WAIT_SEC
    typed: List[str] = []
    log(
        "[auth] Press Enter here after login to retry download, "
        "or type 'skip' to stop."
    )
    log("[auth] The script will also resume automatically if the Adobe login gate clears.")
    next_beep = 0.0
    while time.time() < deadline:
        remaining = max(1, int(deadline - time.time()))
        if time.time() >= next_beep:
            log(f"[auth] Waiting for Adobe login; {remaining}s remaining.")
            next_beep = time.time() + 30

        response = read_console_line_if_available(typed)
        if response is None:
            try:
                current_url = driver.current_url
            except Exception:
                current_url = ""
            if "/tools/remove-background" in current_url:
                hide_onetrust(driver)
                blocker = detect_download_blocker(driver)
                if "Adobe login required before download:" not in blocker:
                    log("[auth] Adobe login gate cleared; retrying download.")
                    return True
            time.sleep(2.0)
            continue

        if response in {"skip", "s", "quit", "q", "stop"}:
            return False

        # Give the page a few seconds to settle after login/redirects.
        settle_deadline = time.time() + 10
        while time.time() < settle_deadline:
            reassert_route(driver)
            hide_onetrust(driver)
            blocker = detect_download_blocker(driver)
            if "Adobe login required before download:" not in blocker:
                log("[auth] Adobe login gate cleared; retrying download.")
                return True
            time.sleep(1.0)

        log("[auth] Adobe still reports that login is required. Complete login in the browser and try again.")

    log("[auth] Timed out waiting for Adobe login.")
    return False


def resolve_download_blocker(driver) -> bool:
    """
    Handle Adobe blockers. Returns True if the caller should retry the click.
    Raises on non-interactive or unresolved blockers.
    """
    blocker = detect_download_blocker(driver)
    if not blocker:
        return False

    if blocker.startswith("Adobe login required before download:"):
        if prompt_for_adobe_login(driver):
            return True
        raise AdobeLoginRequiredError(blocker)

    raise RuntimeError(blocker)


def run_login_only() -> int:
    """
    Open Adobe Express in the Selenium profile so the user can log in once.
    """
    driver = build_driver(force_headed=True)
    try:
        prepare_tool(driver)
        log(f"Adobe login prep using browser profile: {EFFECTIVE_USER_DATA_DIR} [{EFFECTIVE_PROFILE_DIR}]")
        log("Complete Adobe sign-in/sign-up in the open Chrome window for this profile.")
        if sys.stdin and sys.stdin.isatty():
            try:
                input("[auth] Press Enter here after you finish Adobe login. ")
            except EOFError:
                pass
        else:
            log("[auth] No interactive terminal detected; close the browser when you're done logging in.")
            time.sleep(30)
        return 0
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def accept_downloaded_image(path: Path) -> bool:
    """
    Accept only real Adobe PNG outputs. Headless Adobe can return downloads.htm
    for auth/download gates; never let that get renamed to a person PNG.
    """
    path = Path(path)
    if path.suffix.lower() != ".png":
        log(f"[dl] rejected non-PNG download: {path.name}")
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    try:
        with Image.open(path) as im:
            if im.format != "PNG":
                raise ValueError(f"format={im.format!r}")
            im.verify()
    except Exception as exc:
        log(f"[dl] rejected invalid PNG download: {path.name} ({exc})")
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    return True


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
                                if not accept_downloaded_image(final):
                                    continue
                                log(f"[dl] detected completed: {final.name} @ {final}")
                                t.done()
                                return final
                        except FileNotFoundError:
                            pass
                        continue

                    if size > 0:
                        if not accept_downloaded_image(f):
                            continue
                        log(f"[dl] detected: {f.name} @ {f}")
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
                    if not accept_downloaded_image(candidates[0]):
                        time.sleep(0.3)
                        continue
                    log(f"[dl] detected finalized file: {candidates[0].name} @ {candidates[0]}")
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
def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove image backgrounds with Adobe Express via Selenium.")
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Open Adobe Express with the configured Selenium profile so you can sign in once, then exit.",
    )
    args = parser.parse_args(argv)

    if args.login_only:
        return run_login_only()

    session_t0 = time.perf_counter()
    results: List[FileResult] = []
    abort_run = False
    exit_code = 0

    driver = build_driver()
    try:
        log(f"Script: {Path(__file__).resolve()}")
        log(f"Source JPG dir: {SRC_DIR}")
        log(f"Adobe download dir: {DOWNLOAD_DIR}")
        log(f"Archive original dir: {ORIG_DIR}")
        log(f"Chrome profile dir: {EFFECTIVE_USER_DATA_DIR} [{EFFECTIVE_PROFILE_DIR}]")
        log(f"Chrome mode: {'headless' if EFFECTIVE_HEADLESS else 'headed'} ({WINDOW_W}x{WINDOW_H})")
        log("[auth] Preflight: this run will reuse the Chrome profile above for Adobe Express.")
        log("[auth] If Adobe download auth is missing, the run will pause and ask you to finish login in that browser window.")
        log(f"Run log file: {LOG_FILE.resolve()}")
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
                attempt = 1
                stale_project_restarts = 0
                force_prepare = False
                while attempt <= MAX_FILE_ATTEMPTS:
                    try:
                        # Navigate / get ready
                        if force_prepare or RELOAD_EACH_FILE or idx == 1 or attempt > 1:
                            bar.text = f"→ {jpg.name} : opening tool"
                            driver = prepare_fresh_tool(driver)
                            force_prepare = False

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
                            if attempt < MAX_FILE_ATTEMPTS:
                                log(
                                    f"[retry] processing timed out for {jpg.name}; restarting Chrome "
                                    f"and retrying same file (attempt {attempt + 1}/{MAX_FILE_ATTEMPTS})"
                                )
                                attempt += 1
                                driver = restart_driver(driver, f"processing timeout for {jpg.name}")
                                force_prepare = True
                                continue
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
                                    if resolve_download_blocker(driver):
                                        host, inner, _ = _find_download_button_with_frames(driver, timeout=6)
                                        if host:
                                            js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
                                    new_file = wait_new()
                                    if not new_file and resolve_download_blocker(driver):
                                        host, inner, _ = _find_download_button_with_frames(driver, timeout=6)
                                        if host:
                                            js(driver, "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", host)
                                            new_file = wait_new()
                            except RuntimeError:
                                raise
                            except Exception:
                                pass

                        if not new_file:
                            if attempt < MAX_FILE_ATTEMPTS:
                                fr.sec_download = t_dl.done("TIMEOUT")
                                log(
                                    f"[retry] download timed out for {jpg.name}; restarting Chrome "
                                    f"and retrying same file (attempt {attempt + 1}/{MAX_FILE_ATTEMPTS})"
                                )
                                attempt += 1
                                driver = restart_driver(driver, f"download timeout for {jpg.name}")
                                force_prepare = True
                                continue
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
                        log(f"[move] downloaded PNG -> {target}")

                        dest_jpg = ORIG_DIR / jpg.name
                        if dest_jpg.exists():
                            dest_jpg.unlink()
                        shutil.move(str(jpg), str(dest_jpg))
                        log(f"[move] original JPG -> {dest_jpg}")

                        fr.status = "OK"
                        fr.detail = f"{target.name}"
                        log(f"[done] {jpg.name} -> {target.name}")
                        break
                    except WebDriverException as e:
                        if is_browser_crash(e):
                            if attempt < MAX_FILE_ATTEMPTS:
                                log(f"[warn] browser crash while processing {jpg.name}; retrying (attempt {attempt + 1}/{MAX_FILE_ATTEMPTS})")
                                attempt += 1
                                driver = restart_driver(driver, str(e))
                                force_prepare = True
                                continue
                            driver = restart_driver(driver, str(e))
                        fr.status = "ERROR"
                        fr.detail = f"Selenium failure: {str(e).splitlines()[0]}"
                        break
                    except StaleAdobeProjectStateError as e:
                        if stale_project_restarts < MAX_TOOL_READY_RESTARTS:
                            stale_project_restarts += 1
                            log(
                                f"[retry] stale Adobe project state while processing {jpg.name}; restarting Chrome "
                                f"and retrying same file (stale restart {stale_project_restarts}/{MAX_TOOL_READY_RESTARTS}; "
                                f"file attempt {attempt}/{MAX_FILE_ATTEMPTS})"
                            )
                            driver = restart_driver(driver, str(e))
                            force_prepare = True
                            continue
                        fr.status = "ERROR"
                        fr.detail = str(e).splitlines()[0] if str(e) else "Stale Adobe project state"
                        break
                    except AdobeLoginRequiredError as e:
                        if attempt < MAX_FILE_ATTEMPTS:
                            log(
                                f"[retry] Adobe auth/modal blocker while processing {jpg.name}; restarting Chrome "
                                f"and retrying same file (attempt {attempt + 1}/{MAX_FILE_ATTEMPTS})"
                            )
                            attempt += 1
                            driver = restart_driver(driver, f"Adobe blocker for {jpg.name}")
                            force_prepare = True
                            continue
                        fr.status = "ERROR"
                        fr.detail = str(e).splitlines()[0] if str(e) else "Adobe login required before download"
                        abort_run = True
                        exit_code = 4
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

                if abort_run:
                    log("[auth] Stopping the batch because Adobe login is still required. Finish login in this profile, then rerun.")
                    log("[next] Run: python sel_remove_bg.py --login-only")
                    log("[next] Then resume: python orchestrator.py --redo remove_bg --no-recover-edge-chops")
                    break

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
    if err:
        remaining_jpgs = sorted(p.name for p in SRC_DIR.glob("*.jpg"))
        if remaining_jpgs:
            log(f"[warn] Remaining JPGs left for retry: {', '.join(remaining_jpgs)}")
        if exit_code == 4:
            log("[auth] No completed work was rolled back; remaining JPGs are still in the source folder.")
            log("[next] Run: python sel_remove_bg.py --login-only")
            log("[next] Then resume: python orchestrator.py --redo remove_bg --no-recover-edge-chops")

    if exit_code:
        return exit_code

    if err and ok:
        log("[warn] Background removal completed with partial failures; continuing so downstream steps can use the successful PNGs.")
        return 0

    return 1 if err else 0


# Entrypoint
if __name__ == "__main__":
    sys.exit(main())
