# adobe_express_cleanup.py
"""
Delete Adobe Express generated files/projects to free account storage.

This is intentionally separate from sel_remove_bg.py. The normal poster
pipeline should not delete remote Adobe files as a side effect.
"""
from __future__ import annotations

import argparse
import json
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
DEFAULT_SELECT_XS = "166,150,180,130,200"
DEFAULT_ROW_WAIT_SEC = "45"
LOG_FILE = LOGS_DIR / "adobe_express_cleanup.log"
DEBUG_DIR = CONFIG_DIR / "adobe_express_cleanup_debug"


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_select_xs(raw: str) -> list[int]:
    xs: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(float(part))
        except ValueError:
            continue
        if value > 0:
            xs.append(value)
    return xs


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


def write_debug_dump(driver, query: str, select_xs: list[int], label: str) -> Path | None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label).strip("_") or "dump"
    base = DEBUG_DIR / f"{stamp}_{safe_label}"
    png_path = base.with_suffix(".png")
    json_path = base.with_suffix(".json")

    script = r"""
    const query = String(arguments[0] || '').toLowerCase();
    const selectXs = (arguments[1] || []).map(Number).filter(x => Number.isFinite(x) && x > 0);

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

    function attrs(el){
      const out = {};
      if (!el || !el.getAttribute) return out;
      for (const name of ['id', 'class', 'role', 'aria-label', 'aria-checked', 'aria-selected', 'title', 'data-testid', 'type']) {
        const val = el.getAttribute(name);
        if (val !== null && val !== '') out[name] = String(val).slice(0, 240);
      }
      return out;
    }

    function desc(el){
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return {
        tag: (el.tagName || '').toLowerCase(),
        attrs: attrs(el),
        text: textOf(el).slice(0, 240),
        rect: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          w: Math.round(rect.width),
          h: Math.round(rect.height),
          top: Math.round(rect.top),
          left: Math.round(rect.left)
        }
      };
    }

    function looksLikeRow(el){
      const role = (el.getAttribute && String(el.getAttribute('role') || '').toLowerCase()) || '';
      const tag = (el.tagName || '').toLowerCase();
      const rect = el.getBoundingClientRect();
      return role === 'row' ||
             role === 'listitem' ||
             tag === 'tr' ||
             tag === 'li' ||
             (rect.width > window.innerWidth * 0.45 && rect.height >= 40 && rect.height <= 180);
    }

    function rowKey(row){
      const rect = row.getBoundingClientRect();
      return `${Math.round(rect.top / 4) * 4}:${Math.round(rect.height / 4) * 4}`;
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
    const rows = new Map();
    const controls = [];
    const controlSelector = [
      'input',
      'button',
      'a',
      '[role="button"]',
      '[role="checkbox"]',
      'sp-button',
      'sp-table-checkbox-cell[label]',
      'sp-checkbox',
      '[aria-label]',
      '[title]'
    ].join(',');

    for (const root of roots){
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!visible(n)) continue;
        const text = textOf(n);
        if (text && (!query || text.toLowerCase().includes(query)) && looksLikeRow(n)) {
          const key = rowKey(n);
          if (!rows.has(key)) rows.set(key, desc(n));
        }
      }

      const hits = root.querySelectorAll ? root.querySelectorAll(controlSelector) : [];
      for (const hit of hits){
        if (!visible(hit)) continue;
        controls.push(desc(hit));
        if (controls.length >= 250) break;
      }
    }

    const pointProbe = [];
    for (const row of Array.from(rows.values()).slice(0, 20)){
      const y = row.rect.y + Math.max(8, Math.floor(row.rect.h / 2));
      for (const x of selectXs){
        const el = document.elementFromPoint(x, y);
        pointProbe.push({x, y, rowText: row.text, hit: desc(el)});
      }
    }

    return {
      url: location.href,
      title: document.title || '',
      readyState: document.readyState,
      viewport: {w: window.innerWidth, h: window.innerHeight},
      scroll: {
        y: Math.round(window.scrollY || document.documentElement.scrollTop || 0),
        height: Math.round(document.documentElement.scrollHeight || 0)
      },
      query,
      selectXs,
      rowCount: rows.size,
      rows: Array.from(rows.values()).slice(0, 80),
      controlCount: controls.length,
      controls: controls.slice(0, 250),
      pointProbe,
      bodyTextSample: textOf(document.body || document).slice(0, 1500)
    };
    """
    try:
        data = driver.execute_script(script, query, select_xs) or {}
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            driver.save_screenshot(str(png_path))
        except Exception as exc:
            data["screenshot_error"] = str(exc)
            json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"[debug] wrote live Adobe dump: {json_path}")
        if png_path.exists():
            log(f"[debug] wrote screenshot: {png_path}")
        return json_path
    except Exception as exc:
        log(f"[debug] failed to write live Adobe dump: {exc}")
        return None


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
    const hasCheckboxes = !!document.querySelector('sp-table-checkbox-cell[label], input[type="checkbox"], [role="checkbox"], sp-checkbox');
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

    function looksLikeRow(el){
      const role = (el.getAttribute && String(el.getAttribute('role') || '').toLowerCase()) || '';
      const tag = (el.tagName || '').toLowerCase();
      const rect = el.getBoundingClientRect();
      return role === 'row' ||
             role === 'listitem' ||
             tag === 'tr' ||
             tag === 'li' ||
             (rect.width > window.innerWidth * 0.45 && rect.height >= 40 && rect.height <= 160);
    }

    function rowKey(row){
      const rect = row.getBoundingClientRect();
      return `${Math.round(rect.top / 4) * 4}:${Math.round(rect.height / 4) * 4}`;
    }

    function rowFor(el){
      let cur = el;
      for (let i = 0; cur && i < 14; i++){
        const text = textOf(cur);
        const queryMatch = !query || text.toLowerCase().includes(query);
        if (text && queryMatch && looksLikeRow(cur)) return cur;
        cur = rootParent(cur);
      }
      return null;
    }

    function collectCandidateRows(root, rowMap){
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!visible(n)) continue;
        const text = textOf(n);
        if (!text || (query && !text.toLowerCase().includes(query))) continue;
        if (!looksLikeRow(n)) continue;
        const key = rowKey(n);
        if (!rowMap.has(key)) rowMap.set(key, {row: n, box: null, text, selected: false});
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

    const rowMap = new Map();
    let checkboxLikeCount = 0;
    let selectLabelCount = 0;
    for (const root of roots){
      collectCandidateRows(root, rowMap);
      const boxes = root.querySelectorAll
        ? root.querySelectorAll('sp-table-checkbox-cell[label], input[type="checkbox"], [role="checkbox"], sp-checkbox')
        : [];
      checkboxLikeCount += boxes.length;
      if (root.querySelectorAll) {
        selectLabelCount += root.querySelectorAll('[aria-label*="Select"], [title*="Select"]').length;
      }
      for (const box of boxes){
        if (!visible(box)) continue;
        const row = rowFor(box);
        if (!row || !visible(row)) continue;
        const text = textOf(row);
        if (query && !text.toLowerCase().includes(query)) continue;
        const key = rowKey(row);
        if (!rowMap.has(key)) rowMap.set(key, {row, box, text, selected: checked(box)});
      }
    }

    const rows = Array.from(rowMap.values());
    const selected = rows.filter(item => item.selected).length;
    const textSample = roots.map(root => textOf(root)).filter(Boolean).join(' ').replace(/\s+/g, ' ').slice(0, 500);
    return {
      url: location.href,
      y: Math.round(window.scrollY || document.documentElement.scrollTop || 0),
      height: Math.round(document.documentElement.scrollHeight || 0),
      viewport: Math.round(window.innerHeight || 0),
      matching: rows.length,
      selected,
      checkboxBacked: rows.filter(item => !!item.box).length,
      checkboxLikeCount,
      selectLabelCount,
      textSample,
      samples: rows.slice(0, limit).map(item => item.text.slice(0, 180))
    };
    """
    return driver.execute_script(script, query, limit) or {}


def wait_for_matching_rows(driver, query: str, timeout: float) -> dict[str, Any]:
    end = time.time() + max(0.0, timeout)
    last_state: dict[str, Any] = {}
    last_log = 0.0
    while True:
        state = page_state(driver, query)
        last_state = state
        if int(state.get("matching", 0) or 0) > 0:
            return state

        now = time.time()
        if now >= end:
            return last_state
        if now - last_log >= 5:
            log(
                "[wait] file-list shell is ready; waiting for matching asset rows "
                f"({state.get('matching', 0)} visible, "
                f"{state.get('checkboxLikeCount', 0)} checkbox-like controls)"
            )
            last_log = now
        time.sleep(0.75)


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

    function looksLikeRow(el){
      const role = (el.getAttribute && String(el.getAttribute('role') || '').toLowerCase()) || '';
      const tag = (el.tagName || '').toLowerCase();
      const rect = el.getBoundingClientRect();
      return role === 'row' ||
             role === 'listitem' ||
             tag === 'tr' ||
             tag === 'li' ||
             (rect.width > window.innerWidth * 0.45 && rect.height >= 40 && rect.height <= 160);
    }

    function rowKey(row){
      const rect = row.getBoundingClientRect();
      return `${Math.round(rect.top / 4) * 4}:${Math.round(rect.height / 4) * 4}`;
    }

    function rowFor(el){
      let cur = el;
      for (let i = 0; cur && i < 14; i++){
        const text = textOf(cur);
        const queryMatch = !query || text.toLowerCase().includes(query);
        if (text && queryMatch && looksLikeRow(cur)) return cur;
        cur = rootParent(cur);
      }
      return null;
    }

    function collectCandidateRows(root, rowMap){
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!visible(n)) continue;
        const text = textOf(n);
        if (!text || (query && !text.toLowerCase().includes(query))) continue;
        if (!looksLikeRow(n)) continue;
        const key = rowKey(n);
        if (!rowMap.has(key)) rowMap.set(key, {row: n, box: null, text});
      }
    }

    function deepClickableCheckbox(root){
      const selectors = [
        'input[type="checkbox"]',
        'sp-checkbox',
        '[role="checkbox"]'
      ];
      for (const sel of selectors){
        const hit = root.querySelector && root.querySelector(sel);
        if (hit) {
          if (hit.shadowRoot) {
            const nested = deepClickableCheckbox(hit.shadowRoot);
            if (nested) return nested;
          }
          return hit;
        }
      }
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) {
          const hit = deepClickableCheckbox(n.shadowRoot);
          if (hit) return hit;
        }
      }
      return null;
    }

    function clickCheckboxControl(el){
      const inner = el && el.shadowRoot ? deepClickableCheckbox(el.shadowRoot) : null;
      const target = inner || el;
      if (!target) return false;
      try {
        target.scrollIntoView({block: 'center', inline: 'nearest'});
        target.click();
        return true;
      } catch(e) {
        return false;
      }
    }

    function selectableFor(row){
      const selectors = [
        'sp-table-checkbox-cell[label]',
        'input[type="checkbox"]',
        '[role="checkbox"]',
        'sp-checkbox',
        '[aria-label*="Select"]',
        '[title*="Select"]'
      ];
      for (const sel of selectors){
        const hits = row.querySelectorAll ? Array.from(row.querySelectorAll(sel)) : [];
        for (const hit of hits){
          if (visible(hit) && !checked(hit)) return hit;
        }
      }
      return null;
    }

    function clickRowSelect(row){
      const rect = row.getBoundingClientRect();
      const y = Math.min(window.innerHeight - 5, Math.max(5, rect.top + rect.height / 2));
      const xCandidates = [
        Math.max(5, rect.left + 24),
        Math.max(5, rect.left + 36),
        Math.max(5, rect.left + 52)
      ];
      for (const x of xCandidates){
        const el = document.elementFromPoint(x, y);
        if (!el) continue;
        try {
          el.click();
          return true;
        } catch(e) {}
      }
      return false;
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
      collectCandidateRows(root, rowMap);
      const boxes = root.querySelectorAll
        ? root.querySelectorAll('sp-table-checkbox-cell[label], input[type="checkbox"], [role="checkbox"], sp-checkbox')
        : [];
      for (const box of boxes){
        if (!visible(box) || checked(box)) continue;
        const row = rowFor(box);
        if (!row || !visible(row)) continue;
        const text = textOf(row);
        if (query && !text.toLowerCase().includes(query)) continue;
        const key = rowKey(row);
        if (!rowMap.has(key)) rowMap.set(key, {row, box, text});
      }
    }

    const rows = Array.from(rowMap.values()).slice(0, limit);
    const clicked = [];
    for (const item of rows){
      try {
        item.row.scrollIntoView({block: 'center', inline: 'nearest'});
        const target = item.box || selectableFor(item.row);
        if (target) {
          if (clickCheckboxControl(target)) {
            clicked.push(item.text.slice(0, 180));
            continue;
          }
        }
        if (clickRowSelect(item.row)) clicked.push(item.text.slice(0, 180));
      } catch(e) {}
    }
    return {clicked: clicked.length, samples: clicked};
    """
    return driver.execute_script(script, query, limit) or {"clicked": 0, "samples": []}


def selection_toolbar_state(driver) -> dict[str, Any]:
    script = r"""
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

    function collectRoots(root, out){
      out.push(root);
      const all = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of all){
        if (n.shadowRoot) collectRoots(n.shadowRoot, out);
      }
    }

    const roots = [];
    collectRoots(document, roots);
    let selected = 0;
    let deleteVisible = false;
    for (const root of roots){
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!visible(n)) continue;
        const text = textOf(n);
        const match = text.match(/\b(\d+)\s+selected\b/i);
        if (match) selected = Math.max(selected, Number(match[1] || 0));
        if (/^\s*Delete\s*$/i.test(text)) {
          deleteVisible = true;
        }
      }
    }
    return {selected, deleteVisible};
    """
    try:
        return driver.execute_script(script) or {"selected": 0, "deleteVisible": False}
    except Exception:
        return {"selected": 0, "deleteVisible": False}


def matching_row_targets(driver, query: str, limit: int, select_xs: list[int]) -> list[dict[str, Any]]:
    script = r"""
    const query = String(arguments[0] || '').toLowerCase();
    const limit = Number(arguments[1] || 25);
    const configuredXs = (arguments[2] || []).map(Number).filter(x => Number.isFinite(x) && x > 0);

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

    function looksLikeRow(el){
      const role = (el.getAttribute && String(el.getAttribute('role') || '').toLowerCase()) || '';
      const tag = (el.tagName || '').toLowerCase();
      const rect = el.getBoundingClientRect();
      return role === 'row' ||
             role === 'listitem' ||
             tag === 'tr' ||
             tag === 'li' ||
             (rect.width > window.innerWidth * 0.45 && rect.height >= 40 && rect.height <= 160);
    }

    function rowKey(row){
      const rect = row.getBoundingClientRect();
      return `${Math.round(rect.top / 4) * 4}:${Math.round(rect.height / 4) * 4}`;
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
      const nodes = root.querySelectorAll ? root.querySelectorAll('*') : [];
      for (const n of nodes){
        if (!visible(n) || !looksLikeRow(n)) continue;
        const text = textOf(n);
        if (!text || (query && !text.toLowerCase().includes(query))) continue;
        const rect = n.getBoundingClientRect();
        const key = rowKey(n);
        if (!rowMap.has(key)) {
          const localXs = [
            rect.left + 34,
            rect.left + 50,
            rect.left + 70,
            rect.left - 155,
            rect.left - 135,
            rect.left - 115
          ];
          const xs = configuredXs.concat(localXs)
            .map(x => Math.min(window.innerWidth - 5, Math.max(5, x)))
            .filter((x, idx, arr) => arr.findIndex(v => Math.abs(v - x) < 3) === idx);
          rowMap.set(key, {
            text: text.slice(0, 180),
            y: Math.min(window.innerHeight - 5, Math.max(5, rect.top + rect.height / 2)),
            xs,
            top: rect.top
          });
        }
      }
    }

    return Array.from(rowMap.values())
      .sort((a, b) => a.top - b.top)
      .slice(0, limit);
    """
    try:
        return driver.execute_script(script, query, limit, select_xs) or []
    except Exception:
        return []


def cdp_click(driver, x: float, y: float) -> None:
    for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
        payload: dict[str, Any] = {"type": event_type, "x": float(x), "y": float(y)}
        if event_type != "mouseMoved":
            payload.update({"button": "left", "clickCount": 1})
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", payload)


def select_matching_rows_with_cdp(driver, query: str, limit: int, select_xs: list[int]) -> dict[str, Any]:
    targets = matching_row_targets(driver, query, limit, select_xs)
    if not targets:
        return {"clicked": 0, "samples": []}

    clicked: list[str] = []
    for target in targets:
        before = selection_toolbar_state(driver)
        before_count = int(before.get("selected", 0) or 0)
        selected = False
        for x in target.get("xs", []):
            try:
                cdp_click(driver, float(x), float(target["y"]))
            except Exception:
                continue
            time.sleep(0.25)
            after = selection_toolbar_state(driver)
            after_count = int(after.get("selected", 0) or 0)
            if after_count > before_count or after.get("deleteVisible"):
                selected = True
                break
        if selected:
            clicked.append(str(target.get("text", "")))

    final_state = selection_toolbar_state(driver)
    return {
        "clicked": len(clicked),
        "samples": clicked,
        "toolbarSelected": final_state.get("selected", 0),
        "deleteVisible": final_state.get("deleteVisible", False),
    }


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


def scroll_next_page(driver) -> dict[str, Any]:
    script = r"""
    const amount = Math.max(500, Math.floor(window.innerHeight * 0.85));

    function visible(el){
      if (!el) return false;
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.display !== 'none' &&
             style.visibility !== 'hidden' &&
             rect.width > 0 &&
             rect.height > 0;
    }

    const winBefore = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
    window.scrollBy(0, amount);
    const winAfter = Math.round(window.scrollY || document.documentElement.scrollTop || 0);
    if (winAfter > winBefore) {
      return {moved: true, target: 'window', before: winBefore, after: winAfter};
    }

    const candidates = [];
    for (const el of document.querySelectorAll('*')){
      if (!visible(el)) continue;
      if (el.scrollHeight <= el.clientHeight + 20) continue;
      const rect = el.getBoundingClientRect();
      candidates.push({
        el,
        area: rect.width * rect.height,
        before: Math.round(el.scrollTop),
        max: Math.round(el.scrollHeight - el.clientHeight),
        tag: (el.tagName || '').toLowerCase(),
        role: el.getAttribute ? String(el.getAttribute('role') || '') : ''
      });
    }
    candidates.sort((a, b) => b.area - a.area);
    for (const item of candidates.slice(0, 12)){
      if (item.before >= item.max) continue;
      item.el.scrollTop = Math.min(item.max, item.before + amount);
      const after = Math.round(item.el.scrollTop);
      if (after > item.before) {
        return {
          moved: true,
          target: `${item.tag}${item.role ? `[role=${item.role}]` : ''}`,
          before: item.before,
          after
        };
      }
    }

    return {moved: false, target: 'none', before: winBefore, after: winAfter};
    """
    try:
        return driver.execute_script(script) or {"moved": False, "target": "unknown"}
    except WebDriverException:
        raise
    except Exception:
        return {"moved": False, "target": "error"}


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
        "--select-xs",
        default=os.getenv("ADOBE_CLEANUP_SELECT_XS", DEFAULT_SELECT_XS),
        help=(
            "Comma-list of viewport X coordinates to try for row checkbox clicks. "
            "Default matches Adobe's left select column in list view."
        ),
    )
    parser.add_argument(
        "--debug-dump",
        action="store_true",
        default=env_bool("ADOBE_CLEANUP_DEBUG_DUMP", "false"),
        help="Write live Adobe DOM/control/point-probe JSON plus screenshot, then continue normally.",
    )
    parser.add_argument(
        "--row-wait-sec",
        type=float,
        default=max(0.0, float(os.getenv("ADOBE_CLEANUP_ROW_WAIT_SEC", DEFAULT_ROW_WAIT_SEC))),
        help="Seconds to wait for the virtualized Adobe asset rows after the page shell loads.",
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
    select_xs = parse_select_xs(args.select_xs)
    log(f"Select X coordinates: {select_xs or '<row-relative only>'}")

    driver = build_driver(force_headed=not args.headless)
    deleted = 0
    selected_total = 0
    empty_scrolls = 0

    try:
        driver.get(args.url)
        if not wait_for_page(driver):
            log("[error] Adobe file list did not become ready. Check login or page layout.")
            return 3

        state = wait_for_matching_rows(driver, query, args.row_wait_sec)
        log(
            "[state] visible matching rows: "
            f"{state.get('matching', 0)}; selected: {state.get('selected', 0)}; "
            f"checkbox-backed: {state.get('checkboxBacked', 0)}; "
            f"scroll={state.get('y', 0)}/{state.get('height', 0)}"
        )
        for sample in state.get("samples", [])[:5]:
            log(f"[sample] {sample}")
        if int(state.get("matching", 0) or 0) == 0:
            log(
                "[state] no matching rows; "
                f"checkbox-like controls: {state.get('checkboxLikeCount', 0)}; "
                f"select labels: {state.get('selectLabelCount', 0)}"
            )
            text_sample = str(state.get("textSample", "")).strip()
            if text_sample:
                log(f"[state] page text sample: {text_sample}")
            write_debug_dump(driver, query, select_xs, "zero_matches")

        if args.debug_dump:
            write_debug_dump(driver, query, select_xs, "manual")

        if not args.apply:
            log("[dry-run] No remote files were deleted. Re-run with --apply to delete.")
            return 0

        while True:
            remaining_cap = args.max_delete - deleted if args.max_delete else args.batch_size
            if args.max_delete and remaining_cap <= 0:
                log("[done] Reached --max-delete cap.")
                break

            batch_limit = min(args.batch_size, remaining_cap) if args.max_delete else args.batch_size
            selected = select_matching_rows_with_cdp(driver, query, batch_limit, select_xs)
            clicked = int(selected.get("clicked", 0) or 0)

            if clicked <= 0:
                scroll = scroll_next_page(driver)
                moved = bool(scroll.get("moved"))
                empty_scrolls += 1
                log(
                    f"[scan] no matching visible rows selected; "
                    f"scroll moved={moved} target={scroll.get('target', 'unknown')} "
                    f"{scroll.get('before', '')}->{scroll.get('after', '')}; "
                    f"empty scrolls={empty_scrolls}/{args.max_empty_scrolls}"
                )
                if not moved or empty_scrolls >= args.max_empty_scrolls:
                    break
                time.sleep(args.pause_sec)
                state = page_state(driver, query, limit=3)
                log(
                    "[scan] after scroll visible matching rows: "
                    f"{state.get('matching', 0)}; "
                    f"checkbox-backed: {state.get('checkboxBacked', 0)}"
                )
                continue

            empty_scrolls = 0
            selected_total += clicked
            for sample in selected.get("samples", [])[:3]:
                log(f"[selected] {sample}")
            log(
                "[selected] toolbar: "
                f"{selected.get('toolbarSelected', 0)} selected; "
                f"delete visible={selected.get('deleteVisible', False)}"
            )
            time.sleep(args.pause_sec)

            if not selected.get("deleteVisible"):
                log("[error] Rows were clicked, but Adobe did not expose the Delete toolbar.")
                write_debug_dump(driver, query, select_xs, "selection_failed")
                return 4

            if not delete_selected_batch(driver):
                log("[error] Could not click Delete and confirmation. Leaving selected rows untouched.")
                write_debug_dump(driver, query, select_xs, "delete_failed")
                return 4

            deleted += clicked
            log(f"[deleted] batch={clicked}; total={deleted}")
            time.sleep(args.pause_sec)
            driver.refresh()
            if not wait_for_page(driver):
                log("[warn] Page did not fully report ready after refresh; continuing scan.")
            else:
                state = page_state(driver, query, limit=3)
                log(
                    "[scan] after refresh visible matching rows: "
                    f"{state.get('matching', 0)}; "
                    f"checkbox-backed: {state.get('checkboxBacked', 0)}"
                )

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
