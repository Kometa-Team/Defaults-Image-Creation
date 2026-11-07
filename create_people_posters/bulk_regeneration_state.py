"""Durable local regeneration state; status uses read-only SQLite and JSON."""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager, closing
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from urllib.parse import quote

STYLES = ("bw", "diiivoy", "diiivoycolor", "rainier", "signature")
MARKER = "kometa-standalone-people-v1"
STATE = ".bulk"
TERMINAL = {"completed", "failed", "skipped"}


def reject_links(path):
    # The normal workflow's helper is deliberately lazy: --status imports no renderer.
    for part in (Path(path).absolute(), *Path(path).absolute().parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Symlink/reparse path is not permitted: {part}")


def sha(path):
    reject_links(path)
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    # Reuse the established migration's fsync + atomic-replace primitive.
    from people_workspaces import atomic_json as existing_atomic_json
    existing_atomic_json(path, value)
    sync_parent(path)


def sync_parent(path):
    if os.name=='posix':
        descriptor=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)


def read_json(path):
    reject_links(path)
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def process_identity(pid):
    """Creation identity, not PID existence; None is dead and '?' is unverifiable."""
    if not isinstance(pid, int) or pid < 1:
        return None
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None if ctypes.get_last_error() == 87 else "?"
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return "?"
            if code.value != 259:
                return None
            creation, exit_time, cpu_kernel, cpu_user = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                          ctypes.byref(cpu_kernel), ctypes.byref(cpu_user)):
                return "?"
            return str((creation.dwHighDateTime << 32) | creation.dwLowDateTime)
        finally:
            kernel.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return boot + ":" + fields[19] if fields[0] != "Z" else None
    except FileNotFoundError:
        return None
    except OSError:
        return "?"


def database(root, readonly=False):
    path = Path(root) / STATE / "checkpoint.sqlite3"
    reject_links(path)
    if readonly:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=.05)
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path, timeout=5)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
    connection.row_factory = sqlite3.Row
    return connection


def require_durable_local_state(root):
    """Container deployments keep SQLite off network/FUSE/ephemeral mounts."""
    if os.name!='posix':raise ValueError('Durable container state requires Linux')
    target=(Path(root)/STATE).absolute()
    ancestor=target
    while not ancestor.exists():ancestor=ancestor.parent
    matches=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1)
        mount=left.split()[4]
        for encoded,decoded in (('\\040',' '),('\\011','\t'),('\\134','\\')):mount=mount.replace(encoded,decoded)
        path=Path(mount)
        if ancestor==path or path in ancestor.parents:matches.append((len(path.parts),right.split()[0]))
    if not matches or max(matches)[1] not in {'zfs','ext4','xfs','btrfs'}:
        raise ValueError('Checkpoint needs a persistent native local filesystem; network, FUSE, overlay and tmpfs state are rejected')


def metadata(db):
    return {row["key"]: json.loads(row["value"]) for row in db.execute("SELECT key,value FROM meta WHERE key != 'manifest'")}


def set_meta(db, **values):
    db.executemany("INSERT OR REPLACE INTO meta VALUES(?,?)",
                   [(key, json.dumps(value, ensure_ascii=True)) for key, value in values.items()])


def counts(db):
    per_style = {s: dict(planned=0, completed=0, skipped=0, failed=0, remaining=0, in_progress=0)
                 for s in STYLES}
    translations = {"pending": "remaining", "running": "in_progress"}
    for row in db.execute("SELECT style,status,count(*) n FROM outputs GROUP BY style,status"):
        if row["style"] not in per_style or row["status"] not in {"pending", "running", *TERMINAL}:
            raise ValueError("Unknown checkpoint style/state")
        per_style[row["style"]]["planned"] += row["n"]
        per_style[row["style"]][translations.get(row["status"], row["status"])] += row["n"]
    overall = {key: sum(style[key] for style in per_style.values()) for key in next(iter(per_style.values()))}
    processed = db.execute("""SELECT count(*) FROM inputs i WHERE selected=1 AND NOT EXISTS
        (SELECT 1 FROM outputs o WHERE o.number=i.number AND o.status IN ('pending','running'))""").fetchone()[0]
    active = [row[0] for row in db.execute("""SELECT DISTINCT i.relative FROM inputs i JOIN outputs o
        ON o.number=i.number WHERE o.status='running' ORDER BY i.number""")]
    return dict(per_style=per_style, **overall, processed_inputs=processed, current_images=active)


def evidence(root, db, history, last_error=None):
    meta = metadata(db)
    value = {**meta, **counts(db), "updated": time.time(), "checkpoint_available": True}
    if last_error is not None:
        value["last_error"] = last_error
    now = time.time()
    history[:] = [(stamp, n) for stamp, n in history if now-stamp <= 300]
    history.append((now, value["completed"]))
    elapsed = max(0, now-meta.get("started", now))
    value["elapsed_seconds"] = elapsed
    recent_seconds = history[-1][0]-history[0][0]
    value["recent_outputs_per_second"] = ((history[-1][1]-history[0][1])/recent_seconds
                                          if recent_seconds >= 1 else None)
    if not value["recent_outputs_per_second"] and value["completed"] and 0 < elapsed < 30:
        value["recent_outputs_per_second"] = value["completed"]/elapsed
    rate = value["recent_outputs_per_second"]
    value["approximate_eta_seconds"] = ((value["remaining"]+value["in_progress"])/rate if rate else None)
    value["completion_percent"] = (100*(value["completed"]+value["failed"]+value["skipped"])/value["planned"]
                                     if value["planned"] else 0)
    value["log_paths"] = [str(Path(root)/STATE/"run.log"), str(Path(root)/STATE/"events.jsonl")]
    atomic_json(Path(root)/STATE/"progress.json", value)
    return value


def inspect(root):
    """No mkdir, logging handler, lock, PRAGMA journal change, Git call or renderer import."""
    root = Path(root).expanduser().absolute()
    try:
        reject_links(root)
    except (OSError, ValueError) as error:
        return dict(state="unavailable", output=str(root), warnings=[str(error)], read_only=True)
    warnings = []
    manifest = None
    try:
        manifest = read_json(root/STATE/"manifest.json")
        if not isinstance(manifest, dict):
            raise ValueError("Batch manifest is not an object")
        if manifest.get("managed_by") != MARKER or Path(manifest["output"]).resolve() != root.resolve():
            raise ValueError("Batch manifest does not identify this exact workspace")
    except (OSError, ValueError, KeyError) as error:
        warnings.append(f"Manifest unavailable: {error}")
    snapshot = {}
    try:
        snapshot = read_json(root/STATE/"progress.json")
        if not isinstance(snapshot, dict):
            snapshot = {}
            raise ValueError("Progress snapshot is not an object")
    except (OSError, ValueError) as error:
        warnings.append(f"Progress snapshot unavailable: {error}")
    value = dict(snapshot)
    try:
        with closing(database(root, readonly=True)) as db:
            db.execute("BEGIN")
            meta = metadata(db)
            if meta.get("managed_by") != MARKER or str(root.resolve()) != meta.get("output"):
                raise ValueError("Checkpoint belongs to a different batch/workspace")
            if manifest is not None and meta["manifest_hash"] != canonical(manifest):
                warnings.append("Manifest snapshot differs from durable checkpoint; resume can reconcile it")
            value.update(meta, **counts(db), checkpoint_available=True)
    except (OSError, sqlite3.Error, ValueError, KeyError) as error:
        warnings.append(f"Read-only checkpoint unavailable (snapshot fallback): {error}")
        value["checkpoint_available"] = False
    if value.get("managed_by") != MARKER or value.get("output") != str(root.resolve()):
        return dict(state="unavailable", output=str(root), warnings=warnings, read_only=True)
    verified = process_identity(value.get("pid"))
    value["process_verified"] = bool(verified not in (None, "?") and verified == value.get("process_identity"))
    updated = value.get("updated", 0)
    value["progress_age_seconds"] = max(0, time.time()-updated)
    value["stale_progress"] = value["progress_age_seconds"] > value.get("stale_after_seconds", 60)
    if value.get("state") == "running" and not value["process_verified"]:
        value["state"] = "interrupted"
        warnings.append("Potential interruption: recorded process identity cannot be verified"
                        if verified == "?" else "Recorded process exited or its PID was reused")
    value["active_workers"] = len(value.get("current_images", []))
    value["checkpoint_path"] = str(root/STATE/"checkpoint.sqlite3")
    if value["stale_progress"] and value.get("state") == "running":
        warnings.append("Process identity is verified but progress is stale; it may be blocked in I/O")
    value["completion_percent"] = (100*(value.get("completed", 0)+value.get("failed", 0)+value.get("skipped", 0))/value["planned"]
                                     if value.get("planned") else 0)
    end = value.get("stopped", time.time()) if value.get("state") in {"completed", "failed", "interrupted"} else time.time()
    value["elapsed_seconds"] = max(0, end-value.get("started", end))
    rate = snapshot.get("recent_outputs_per_second") if not value["stale_progress"] else None
    value["recent_outputs_per_second"] = rate
    value["approximate_eta_seconds"] = ((value.get("remaining", 0)+value.get("in_progress", 0))/rate if rate else None)
    value["eta_is_approximate"] = True
    value["warnings"] = warnings
    value["read_only"] = True
    return value


def human(value):
    if value.get("state") == "unavailable":
        return "Status unavailable: " + "; ".join(value.get("warnings", []))
    eta = value.get("approximate_eta_seconds")
    elapsed = value.get("elapsed_seconds", 0)
    rate = value.get("recent_outputs_per_second") or 0
    lines = [f"Batch {value.get('batch_id')} | {value.get('state')} | {value.get('phase')}",
             f"Inputs: {value.get('processed_inputs',0)}/{value.get('selected_input_total',0)} selected; "
             f"{value.get('input_total',0)} discovered; {value.get('eligible_image_count',0)} eligible",
             f"Outputs: {value.get('completed',0)} completed, {value.get('skipped',0)} skipped, "
             f"{value.get('failed',0)} failed, {value.get('remaining',0)} pending, "
             f"{value.get('in_progress',0)} in progress / {value.get('planned',0)} planned",
             f"Progress {value.get('completion_percent',0):.1f}% | elapsed {elapsed/3600:.2f}h | "
             f"recent {rate*60:.2f} outputs/min | approximate ETA {eta/3600:.2f}h" if eta is not None else
             f"Progress {value.get('completion_percent',0):.1f}% | elapsed {elapsed/3600:.2f}h | approximate ETA unavailable"]
    for style in STYLES:
        row = value.get("per_style", {}).get(style, {})
        lines.append(f"  {style}: {row.get('completed',0)}/{row.get('planned',0)} completed; "
                     f"{row.get('failed',0)} failed; {row.get('skipped',0)} skipped; "
                     f"{row.get('remaining',0)} pending; {row.get('in_progress',0)} active")
    lines.extend(["Current: " + ", ".join(value.get("current_images", [])),
                  "Last completed: " + str(value.get("last_successful_image")),
                  "Source commit: " + str(value.get("source_git", {}).get("head")),
                  "Renderer: " + str(value.get("renderer_id")),
                  "Latest error: " + str(value.get("last_error")),
                  "Logs: " + ", ".join(value.get("log_paths", []))])
    lines.extend("WARNING: "+w for w in value.get("warnings", []))
    return "\n".join(lines)


@contextmanager
def writer_lock(root):
    path = Path(root)/STATE/"runner.lock"
    reject_links(path)
    handle = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            handle.write(b"0"); handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("Another renderer owns this batch; use --status") from error
        yield
    finally:
        handle.close()


def log(root, message, event=None):
    stamp = datetime.now(timezone.utc).isoformat()
    with (Path(root)/STATE/"run.log").open("a", encoding="utf8") as handle:
        handle.write(stamp+" "+message+"\n")
    with (Path(root)/STATE/"events.jsonl").open("a", encoding="utf8") as handle:
        handle.write(json.dumps(dict(time=stamp, message=message, **(event or {})), ensure_ascii=True)+"\n")

def resource_usage():
    """Record observed process peak working set without an extra dependency."""
    value = dict(process_cpu_seconds=time.process_time())
    if os.name=='posix':
        import resource
        value['peak_working_set_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    if os.name == "nt":
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb",wintypes.DWORD),("faults",wintypes.DWORD),
                        *[(n,ctypes.c_size_t) for n in ("peak","current","pool_peak","pool",
                             "nonpool_peak","nonpool","page","page_peak","private")]]
        counters = Counters(); counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32")
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            value["peak_working_set_bytes"] = counters.peak
    return value

def read_inventory(root):
    value = read_json(Path(root)/STATE/"inventory.json")
    if not isinstance(value,dict) or value.get("version") != 1 or not isinstance(value.get("chunks"),list):
        raise ValueError("Unsupported frozen inventory format")
    if any(not isinstance(chunk,list) or len(chunk)>2048 for chunk in value["chunks"]):
        raise ValueError("Invalid frozen inventory chunk")
    rows = [row for chunk in value["chunks"] for row in chunk]
    if len(rows) != value.get("count") or any(not isinstance(row,dict) for row in rows):
        raise ValueError("Frozen inventory count/type mismatch")
    return rows
