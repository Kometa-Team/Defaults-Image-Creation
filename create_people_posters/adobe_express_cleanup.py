# adobe_express_cleanup.py
"""
Delete Adobe Express generated files/projects to free account storage.

This is intentionally separate from sel_remove_bg.py. The normal poster
pipeline should not delete remote Adobe files as a side effect.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from selenium.common.exceptions import WebDriverException


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = CONFIG_DIR / ".env"
load_dotenv(ENV_FILE)

from sel_remove_bg import build_driver, hide_onetrust, js  # noqa: E402


DEFAULT_URL = "https://new.express.adobe.com/your-stuff/files?view=list"
DEFAULT_QUERY = "Remove background project"
LOG_FILE = LOGS_DIR / "adobe_express_cleanup.log"


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def now_ts() -> str:
    return time.strftime("%H:%M:%S")


def log(message: str) -> None:
    line = f"[{now_ts()}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def wait_for_page(driver, timeout: float = 45.0) -> bool:
    script = r"""
    function textOf(el){
      try { return String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); }
      catch(e) { return ''; }
    }

    function scanText(root, out){
      const text = textOf(root);
      if (text) out.push(text);
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) scanText(n.shadowRoot, out);
      }
    }

    const chunks = [];
    scanText(document, chunks);
    for (const f of document.querySelectorAll('iframe')){
      try {
        const d = f.contentDocument || f.contentWindow?.document;
        if (d) scanText(d, chunks);
      } catch(e) {}
    }

    const text = chunks.join(' ').replace(/\s+/g, ' ').trim();
    const hasFileListText = /Your stuff|Search Files|Remove background project/i.test(text);
    const hasCheckboxes = !!document.querySelector('input[type="checkbox"], [role="checkbox"], sp-checkbox');
    return {
      readyState: document.readyState,
      title: document.title || '',
      url: location.href,
      hasFileListText,
      hasCheckboxes,
      sample: text.slice(0, 400)
    };
    """
    end = time.time() + timeout
    last_state = {}
    while time.time() < end:
        try:
            hide_onetrust(driver)
            state = driver.execute_script(script) or {}
            last_state = state
            if state.get("hasFileListText") or (
                state.get("hasCheckboxes") and state.get("readyState") == "complete"
            ):
                return True
        except WebDriverException:
            raise
        except Exception:
            pass
        time.sleep(0.5)
    log(
        "[ready] timed out; "
        f"url={last_state.get('url', '')!r}; "
        f"title={last_state.get('title', '')!r}; "
        f"readyState={last_state.get('readyState', '')!r}; "
        f"hasCheckboxes={last_state.get('hasCheckboxes', False)}"
    )
    sample = str(last_state.get("sample", "")).strip()
    if sample:
        log(f"[ready] text sample: {sample}")
    return False


def page_state(driver, query: str, limit: int = 10) -> dict[str, Any]:
    script = r"""
    const query = String(arguments[0] || '').toLowerCase();
    const limit = Number(arguments[1] || 10);

    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' &&
             style.visibility !== 'hidden' &&
             rect.width > 0 &&
             rect.height > 0 &&
             rect.bottom >= 0 &&
             rect.top <= window.innerHeight;
    }

    function textOf(el){
      try { return String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); }
      catch(e) { return ''; }
    }

    function rootParent(el){
      if (!el) return null;
      if (el.parentElement) return el.parentElement;
      const root = el.getRootNode && el.getRootNode();
      return root && root.host ? root.host.parentElement : null;
    }

    function checked(el){
      try {
        if (el.checked === true) return true;
        if (el.getAttribute && el.getAttribute('aria-checked') === 'true') return true;
        if (el.matches && el.matches('[checked]')) return true;
      } catch(e) {}
      return false;
    }

    function rowFor(el){
      let cur = el;
      for (let i = 0; cur && i < 14; i++){
        const role = (cur.getAttribute && String(cur.getAttribute('role') || '').toLowerCase()) || '';
        const tag = (cur.tagName || '').toLowerCase();
        const text = textOf(cur);
        const rowish = role === 'row' || role === 'listitem' || tag === 'tr' || tag === 'li';
        const queryMatch = !query || text.toLowerCase().includes(query);
        if (text && queryMatch && (rowish || text.length > 30)) return cur;
        cur = rootParent(cur);
      }
      return null;
    }

    function collectRoots(root, out){
      out.push(root);
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) collectRoots(n.shadowRoot, out);
      }
    }

    const roots = [];
    collectRoots(document, roots);

    const rowMap = new Map();
    for (const root of roots){
      const boxes = root.querySelectorAll
        ? root.querySelectorAll('input[type="checkbox"], [role="checkbox"], sp-checkbox')
        : [];
      for (const box of boxes){
        if (!visible(box)) continue;
        const row = rowFor(box);
        if (!row || !visible(row)) continue;
        const text = textOf(row);
        if (query && !text.toLowerCase().includes(query)) continue;
        if (!rowMap.has(row)) rowMap.set(row, {row, box, text, selected: checked(box)});
      }
    }

    const rows = Array.from(rowMap.values());
    const selected = rows.filter(item => item.selected).length;
    return {
      url: location.href,
      y: Math.round(window.scrollY || document.documentElement.scrollTop || 0),
      height: Math.round(document.documentElement.scrollHeight || 0),
      viewport: Math.round(window.innerHeight || 0),
      matching: rows.length,
      selected,
      samples: rows.slice(0, limit).map(item => item.text.slice(0, 180))
    };
    """
    return driver.execute_script(script, query, limit) or {}


def select_matching_rows(driver, query: str, limit: int) -> dict[str, Any]:
    script = r"""
    const query = String(arguments[0] || '').toLowerCase();
    const limit = Number(arguments[1] || 25);

    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' &&
             style.visibility !== 'hidden' &&
             rect.width > 0 &&
             rect.height > 0 &&
             rect.bottom >= 0 &&
             rect.top <= window.innerHeight;
    }

    function textOf(el){
      try { return String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); }
      catch(e) { return ''; }
    }

    function rootParent(el){
      if (!el) return null;
      if (el.parentElement) return el.parentElement;
      const root = el.getRootNode && el.getRootNode();
      return root && root.host ? root.host.parentElement : null;
    }

    function checked(el){
      try {
        if (el.checked === true) return true;
        if (el.getAttribute && el.getAttribute('aria-checked') === 'true') return true;
        if (el.matches && el.matches('[checked]')) return true;
      } catch(e) {}
      return false;
    }

    function rowFor(el){
      let cur = el;
      for (let i = 0; cur && i < 14; i++){
        const role = (cur.getAttribute && String(cur.getAttribute('role') || '').toLowerCase()) || '';
        const tag = (cur.tagName || '').toLowerCase();
        const text = textOf(cur);
        const rowish = role === 'row' || role === 'listitem' || tag === 'tr' || tag === 'li';
        const queryMatch = !query || text.toLowerCase().includes(query);
        if (text && queryMatch && (rowish || text.length > 30)) return cur;
        cur = rootParent(cur);
      }
      return null;
    }

    function collectRoots(root, out){
      out.push(root);
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) collectRoots(n.shadowRoot, out);
      }
    }

    const roots = [];
    collectRoots(document, roots);

    const rowMap = new Map();
    for (const root of roots){
      const boxes = root.querySelectorAll
        ? root.querySelectorAll('input[type="checkbox"], [role="checkbox"], sp-checkbox')
        : [];
      for (const box of boxes){
        if (!visible(box) || checked(box)) continue;
        const row = rowFor(box);
        if (!row || !visible(row)) continue;
        const text = textOf(row);
        if (query && !text.toLowerCase().includes(query)) continue;
        if (!rowMap.has(row)) rowMap.set(row, {row, box, text});
      }
    }

    const rows = Array.from(rowMap.values()).slice(0, limit);
    const clicked = [];
    for (const item of rows){
      try {
        item.box.scrollIntoView({block: 'center', inline: 'nearest'});
        item.box.click();
        clicked.push(item.text.slice(0, 180));
      } catch(e) {}
    }
    return {clicked: clicked.length, samples: clicked};
    """
    return driver.execute_script(script, query, limit) or {"clicked": 0, "samples": []}


def click_button_by_text(driver, pattern: str, label: str, timeout: float = 15.0) -> bool:
    script = r"""
    const pattern = new RegExp(arguments[0], 'i');

    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' &&
             style.visibility !== 'hidden' &&
             rect.width > 0 &&
             rect.height > 0;
    }

    function textOf(el){
      try { return String(el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim(); }
      catch(e) { return ''; }
    }

    function disabled(el){
      try {
        const inner = (el.shadowRoot && el.shadowRoot.querySelector('button')) || el;
        const style = getComputedStyle(inner);
        return !!inner.disabled ||
               inner.getAttribute('disabled') !== null ||
               inner.getAttribute('aria-disabled') === 'true' ||
               el.getAttribute('disabled') !== null ||
               el.getAttribute('aria-disabled') === 'true' ||
               style.pointerEvents === 'none';
      } catch(e) {
        return false;
      }
    }

    function collectRoots(root, out){
      out.push(root);
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) collectRoots(n.shadowRoot, out);
      }
    }

    const roots = [];
    collectRoots(document, roots);
    const hits = [];
    for (const root of roots){
      const nodes = root.querySelectorAll
        ? root.querySelectorAll('button, [role="button"], sp-button, a')
        : [];
      for (const n of nodes){
        const text = textOf(n);
        if (!text || !pattern.test(text) || !visible(n) || disabled(n)) continue;
        hits.push(n);
      }
    }
    const hit = hits[hits.length - 1];
    if (!hit) return false;
    hit.scrollIntoView({block: 'center', inline: 'nearest'});
    hit.click();
    return true;
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            hide_onetrust(driver)
            if driver.execute_script(script, pattern):
                log(f"[click] {label}")
                return True
        except WebDriverException:
            raise
        except Exception:
            pass
        time.sleep(0.4)
    return False


def scroll_next_page(driver) -> bool:
    script = r"""
    const before = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
    window.scrollBy(0, Math.max(500, Math.floor(window.innerHeight * 0.85)));
    const after = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
    return after > before;
    """
    try:
        return bool(driver.execute_script(script))
    except WebDriverException:
        raise
    except Exception:
        return False


def delete_selected_batch(driver) -> bool:
    if not click_button_by_text(driver, r"^\s*Delete\s*$", "Delete action", timeout=10):
        return False
    time.sleep(0.8)
    return click_button_by_text(
        driver,
        r"^\s*(Delete|Permanently delete|Move to trash)\s*$",
        "Delete confirmation",
        timeout=15,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete Adobe Express files/projects from Your Stuff to free storage."
    )
    parser.add_argument(
        "--url",
        default=os.getenv("ADOBE_CLEANUP_URL", DEFAULT_URL),
        help="Adobe Express file-list URL.",
    )
    parser.add_argument(
        "--query",
        default=os.getenv("ADOBE_CLEANUP_QUERY", DEFAULT_QUERY),
        help="Only select rows whose visible text contains this value. Default targets remove-background projects.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=max(1, int(os.getenv("ADOBE_CLEANUP_BATCH_SIZE", "25"))),
        help="Maximum visible matching rows to select before each delete.",
    )
    parser.add_argument(
        "--max-delete",
        type=int,
        default=max(0, int(os.getenv("ADOBE_CLEANUP_MAX_DELETE", "0"))),
        help="Maximum rows to delete this run. 0 means no cap.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete selected Adobe files. Without this, the script only reports visible matches.",
    )
    parser.add_argument(
        "--allow-all",
        action="store_true",
        help="Allow an empty --query, which can delete any visible Adobe file row.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=env_bool("ADOBE_CLEANUP_HEADLESS", "false"),
        help="Allow headless Chrome. Headed mode is the default for visual safety.",
    )
    parser.add_argument(
        "--pause-sec",
        type=float,
        default=max(0.1, float(os.getenv("ADOBE_CLEANUP_PAUSE_SEC", "1.5"))),
        help="Pause after selection/delete/scroll actions.",
    )
    parser.add_argument(
        "--max-empty-scrolls",
        type=int,
        default=max(1, int(os.getenv("ADOBE_CLEANUP_MAX_EMPTY_SCROLLS", "5"))),
        help="Stop after this many scrolls with no matching visible rows.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query = (args.query or "").strip()
    if not query and not args.allow_all:
        log("[error] Refusing empty --query unless --allow-all is also set.")
        return 2

    LOG_FILE.write_text("", encoding="utf-8")
    log(f"Log file: {LOG_FILE.resolve()}")
    log(f"URL: {args.url}")
    log(f"Query: {query!r}" if query else "Query: <all visible rows>")
    log(f"Mode: {'apply/delete' if args.apply else 'dry-run/report only'}")
    log(f"Batch size: {args.batch_size}; max delete: {args.max_delete or 'unlimited'}")

    driver = build_driver(force_headed=not args.headless)
    deleted = 0
    selected_total = 0
    empty_scrolls = 0

    try:
        driver.get(args.url)
        if not wait_for_page(driver):
            log("[error] Adobe file list did not become ready. Check login or page layout.")
            return 3

        state = page_state(driver, query)
        log(
            "[state] visible matching rows: "
            f"{state.get('matching', 0)}; selected: {state.get('selected', 0)}; "
            f"scroll={state.get('y', 0)}/{state.get('height', 0)}"
        )
        for sample in state.get("samples", [])[:5]:
            log(f"[sample] {sample}")

        if not args.apply:
            log("[dry-run] No remote files were deleted. Re-run with --apply to delete.")
            return 0

        while True:
            remaining_cap = args.max_delete - deleted if args.max_delete else args.batch_size
            if args.max_delete and remaining_cap <= 0:
                log("[done] Reached --max-delete cap.")
                break

            batch_limit = min(args.batch_size, remaining_cap) if args.max_delete else args.batch_size
            selected = select_matching_rows(driver, query, batch_limit)
            clicked = int(selected.get("clicked", 0) or 0)

            if clicked <= 0:
                moved = scroll_next_page(driver)
                empty_scrolls += 1
                log(
                    f"[scan] no matching visible rows selected; "
                    f"scroll moved={moved}; empty scrolls={empty_scrolls}/{args.max_empty_scrolls}"
                )
                if not moved or empty_scrolls >= args.max_empty_scrolls:
                    break
                time.sleep(args.pause_sec)
                continue

            empty_scrolls = 0
            selected_total += clicked
            for sample in selected.get("samples", [])[:3]:
                log(f"[selected] {sample}")
            time.sleep(args.pause_sec)

            if not delete_selected_batch(driver):
                log("[error] Could not click Delete and confirmation. Leaving selected rows untouched.")
                return 4

            deleted += clicked
            log(f"[deleted] batch={clicked}; total={deleted}")
            time.sleep(args.pause_sec)
            driver.refresh()
            if not wait_for_page(driver):
                log("[warn] Page did not fully report ready after refresh; continuing scan.")

        log("====== SUMMARY ======")
        log(f"Selected rows: {selected_total}")
        log(f"Deleted rows: {deleted}")
        log(f"Query: {query!r}" if query else "Query: <all visible rows>")
        return 0
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
