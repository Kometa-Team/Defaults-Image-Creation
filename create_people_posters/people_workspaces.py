"""Isolated, resumable jobs. Only verified publications become deletion candidates."""

# A single canonical diagnostic registry is shared by CLI and imported callers.
import sys as _security_sys
from pathlib import Path as _SecurityPath
_security_root = _SecurityPath(__file__).resolve().parents[1]
if (_security_root / "create_people_posters").is_dir() and str(_security_root) not in _security_sys.path:
    _security_sys.path.insert(0, str(_security_root))
from create_people_posters.people_diagnostics import (protect_cli, safe_exception, sanitize_text,
                                                     sanitize_data, secure_handler, register_environment)
from create_people_posters.people_process import guard_cli
if __name__ == "__main__":
    guard_cli()


import json
import os
import re
import shutil
import sqlite3
import stat
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent / "config"
ID_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{12}\Z")


def atomic_json(path, data):
    if json.dumps(sanitize_data(data), sort_keys=True) != json.dumps(data, sort_keys=True):
        raise ValueError("Sensitive data cannot be persisted in job metadata")
    path = Path(path)
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    reject_links(temporary)
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def reject_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"Symlink/reparse point is not a managed workspace: {part}")


def process_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


class Workspaces:
    def __init__(self, config=ROOT, jobs=None, state=None):
        from people_github import sandbox_storage
        isolated = sandbox_storage()
        if isolated:
            for value, key in ((jobs, "PEOPLE_JOBS_DIR"), (state, "PEOPLE_STATE_DIR")):
                if value and Path(value).resolve() != isolated[key].resolve():
                    raise ValueError("Sandbox cannot share production job/publication state")
            jobs, state = isolated["PEOPLE_JOBS_DIR"], isolated["PEOPLE_STATE_DIR"]
        self.config = Path(config).absolute()
        self.jobs = Path(jobs or os.getenv("PEOPLE_JOBS_DIR") or self.config / "jobs").absolute()
        self.state = Path(state or os.getenv("PEOPLE_STATE_DIR") or self.config / "state").absolute()
        reject_links(self.jobs)
        reject_links(self.state)
        self.jobs = self.jobs.resolve()
        self.state = self.state.resolve()
        if self.jobs == self.state or self.jobs in self.state.parents or self.state in self.jobs.parents:
            raise ValueError("Persistent state and jobs must be separate directory trees")
        self.jobs.mkdir(parents=True, exist_ok=True)
        self.state.mkdir(parents=True, exist_ok=True)
        reject_links(self.state / "publication_state.db")
        self.db = sqlite3.connect(self.state / "publication_state.db", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, status TEXT, created REAL, updated REAL, published REAL, error TEXT)""")
        self.db.commit()

    def close(self):
        self.db.close()

    def path(self, batch):
        if not ID_PATTERN.fullmatch(batch):
            raise ValueError("Invalid batch identifier")
        path = self.jobs / batch
        reject_links(path)
        if path.resolve().parent != self.jobs.resolve():
            raise ValueError("Batch outside managed jobs root")
        return path

    def record(self, batch):
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (batch,)).fetchone()
        if row is None:
            raise ValueError("Unknown managed batch")
        manifest = self.path(batch) / "manifest.json"
        reject_links(manifest)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("id") != batch or data.get("managed_by") != "kometa-people-v1":
            raise ValueError("Unrecognized workspace manifest")
        return dict(row), data

    def create(self, people_list=None, cleanup=True):
        if cleanup and os.getenv("PEOPLE_AUTO_CLEANUP", "true").strip().lower() in {"1", "true", "yes", "on"}:
            for batch, outcome in self.cleanup(dry_run=False):
                print(f"[CLEANUP] {batch}: {outcome}")
        self.check_budget()
        batch = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:12]
        path = self.path(batch)
        path.mkdir()
        for name in ("input", "posters", "Downloads/color", "Downloads/other", "people_dirs/Downloads", "logs"):
            (path / name).mkdir(parents=True, exist_ok=True)
        source = Path(people_list or self.config / "people_list.txt").absolute()
        inputs = [(source, path / "people_list.txt")]
        if people_list is None:
            inputs.append((self.config / "people_overrides.txt", path / "people_overrides.txt"))
        for src, dst in inputs:
            if src.is_file():
                shutil.copy2(src, dst)
                shutil.copy2(src, path / "input" / dst.name)
        now = time.time()
        data = {"id": batch, "managed_by": "kometa-people-v1", "status": "pending", "created": now,
                "people_list_source": str(source), "explicit_people_list": people_list is not None}
        atomic_json(path / "manifest.json", data)
        with self.db:
            self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)", (batch, "pending", now, now, None, ""))
        return batch

    def select(self, batch=None, new=False, people_list=None, cleanup=True):
        if batch:
            record, _ = self.record(batch)
            if record["status"] in {"complete", "cleanup_eligible", "validation_only"}:
                raise ValueError("Published/cleaned/validation-only batch cannot be regenerated; use --new-batch")
            return batch
        if not new:
            row = self.db.execute("SELECT id FROM jobs WHERE status NOT IN ('complete','cleanup_eligible','published','no_work','validation_only') ORDER BY created DESC LIMIT 1").fetchone()
            if row:
                _, manifest = self.record(row["id"])
                if people_list and Path(manifest["people_list_source"]) != Path(people_list).absolute():
                    raise ValueError("Another unfinished batch exists; use --new-batch or --batch-id")
                return row["id"]
        return self.create(people_list, cleanup=cleanup)

    def set_status(self, batch, status, error=""):
        error = sanitize_text(error) if type(error) is str else safe_exception(error)
        _, manifest = self.record(batch)
        manifest.update(status=status, updated=time.time(), error=error)
        with self.db:
            self.db.execute("UPDATE jobs SET status=?,updated=?,error=? WHERE id=?", (status, time.time(), error, batch))
        atomic_json(self.path(batch) / "manifest.json", manifest)

    def activate(self, batch):
        path = self.path(batch)
        lease = path / ".active"
        if lease.exists():
            pid = int(lease.read_text(encoding="ascii"))
            if process_alive(pid):
                raise ValueError("Batch already active in another process")
            lease.unlink()
        descriptor = os.open(lease, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(str(os.getpid()))

    def deactivate(self, batch):
        lease = self.path(batch) / ".active"
        if lease.exists() and lease.read_text(encoding="ascii") == str(os.getpid()):
            lease.unlink()

    def configure(self, batch):
        self.record(batch)
        path = self.path(batch)
        os.environ.update({
            "PEOPLE_CONFIG_DIR": str(path), "PEOPLE_BATCH_ID": batch, "PEOPLE_STATE_DIR": str(self.state),
            "PEOPLE_LIST": str(path / "people_list.txt"), "PEOPLE_OVERRIDE_LIST": str(path / "people_overrides.txt"),
            "POSTER_DIR": str(path / "posters"), "POSTERS_INPUT_DIR": str(path / "posters"),
            "SEL_SRC_DIR": str(path / "people_dirs" / "Downloads"), "SEL_ORIG_DIR": str(path / "people_dirs" / "original"),
            "SEL_DOWNLOAD_DIR": str(path / "sel_downloads"),
            "COLORIZE_INPUT_OTHER": str(path / "Downloads" / "other"), "COLORIZE_OUTPUT_COLOR": str(path / "Downloads" / "color"),
            "EDGE_CHOP_PEOPLE_ROOT": str(path / "people_dirs"), "EDGE_CHOP_TRANSPARENT_ROOT": str(path / "people_dirs" / "transparent"),
            "EDGE_CHOP_DOWNLOADS_DIR": str(path / "people_dirs" / "Downloads"), "EDGE_CHOP_OUT_ROOT": str(path / "edge_chop_recovery"),
        })
        for key, default in {
            "REMBG_HOME": self.config / "models" / "rembg", "TORCH_HOME": self.config / "models" / "torch-cache",
            "HF_HOME": self.config / "models" / "ddcolor" / "hf-home",
            "COLORIZE_VENDOR_DIR": self.config / "vendor", "COLORIZE_DDCOLOR_VENDOR_DIR": self.config / "vendor" / "DDColor",
            "COLORIZE_DDCOLOR_MODELS_DIR": self.config / "models" / "ddcolor",
            "EDGE_CHOP_EXHAUSTED_FILE": self.state / "edge_chop_exhausted.txt",
            "EDGE_CHOP_ATTEMPTED_FILE": self.state / "edge_chop_attempts.csv",
            "SEL_USER_DATA_DIR": self.config / "chrome-profile", "SEL_HEADLESS_USER_DATA_DIR": self.config / "chrome-profile-headless",
        }.items():
            os.environ.setdefault(key, str(default))
            persistent = Path(os.environ[key]).expanduser().resolve()
            if persistent == self.jobs or self.jobs in persistent.parents:
                raise ValueError(f"{key} must be outside managed temporary jobs")
        return path

    def check_budget(self):
        limit = float(os.getenv("PEOPLE_JOBS_MAX_GIB", "20")) * 1024 ** 3
        used = 0
        for root, dirs, files in os.walk(self.jobs, followlinks=False):
            for name in dirs + files:
                reject_links(Path(root) / name)
            used += sum((Path(root) / name).stat().st_size for name in files)
        if limit > 0 and used >= limit:
            raise ValueError("Managed jobs storage budget exceeded; retry/inspect retained failed jobs or raise PEOPLE_JOBS_MAX_GIB")
        if shutil.disk_usage(self.jobs).free < 256 * 1024 ** 2:
            raise ValueError("Insufficient free disk space for another processing step")

    def confirm_published(self, batch, ledger):
        if not ledger.verified(batch):
            raise ValueError("Batch is not fully verified; unpublished files must be retained")
        from publish_people_github import file_hash
        from people_remote_inventory import IMAGE_SUFFIXES
        _, manifest = self.record(batch)
        path = self.path(batch)
        catalog = {}
        for root, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                reject_links(Path(root) / name)
            for name in files:
                image = Path(root) / name
                if image.suffix.lower() in IMAGE_SUFFIXES:
                    catalog[image.relative_to(path).as_posix()] = file_hash(image)
        manifest["cleanup_files"] = catalog
        atomic_json(path / "manifest.json", manifest)
        self.set_status(batch, "published")
        with self.db:
            self.db.execute("UPDATE jobs SET published=? WHERE id=?", (time.time(), batch))
        ledger.export(batch)
        self.set_status(batch, "cleanup_eligible")

    def cleanup(self, dry_run=True, now=None):
        enrollment = self.state / "verified-retention" / "enrollment.json"
        reject_links(enrollment)
        if enrollment.exists():
            from create_people_posters.people_verified_cleanup import cleanup_managed_jobs
            return cleanup_managed_jobs(self, dry_run=dry_run, now=now)
        now = time.time() if now is None else now
        self.last_cleanup_counts = None
        rows = self.db.execute("SELECT * FROM jobs").fetchall()
        self.last_cleanup_counts = {"eligible": 0, "deleted": 0,
                                    "retained": sum(row["status"] != "complete" for row in rows)}
        retention = float(os.getenv("PEOPLE_BATCH_RETENTION_DAYS", "3"))
        failed_retention = float(os.getenv("PEOPLE_FAILED_BATCH_RETENTION_DAYS", "14"))
        if retention < 0 or failed_retention < 0:
            raise ValueError("Retention days cannot be negative")
        results = []
        for row in rows:
            batch = row["id"]
            _, manifest = self.record(batch)
            path = self.path(batch)
            if (path / ".active").exists():
                continue
            if row["status"] not in {"published", "cleanup_eligible"} or row["published"] is None:
                if row["status"] != "complete" and now - row["updated"] > failed_retention * 86400:
                    results.append((batch, "retained: unpublished; manual recovery required"))
                continue
            if now - row["published"] < retention * 86400:
                continue
            from people_publication_state import PublicationState
            ledger = PublicationState(self.state)
            try:
                if not ledger.verified(batch):
                    results.append((batch, "retained: publication receipts incomplete"))
                    continue
                for root, dirs, files in os.walk(path, followlinks=False):
                    for name in dirs + files:
                        reject_links(Path(root) / name)
                from publish_people_github import file_hash
                from people_remote_inventory import IMAGE_SUFFIXES
                catalog = manifest.get("cleanup_files")
                if catalog is None:
                    results.append((batch, "retained: cleanup image catalog missing"))
                    continue
                changed = any(image.suffix.lower() in IMAGE_SUFFIXES
                              and catalog.get(image.relative_to(path).as_posix()) != file_hash(image)
                              for image in path.rglob("*") if image.is_file())
                for receipt in ledger.rows(batch):
                    for key, digest in (("prepared", "published_hash"), ("source", "source_hash")):
                        image = Path(receipt[key])
                        if image.exists() and file_hash(image) != receipt[digest]:
                            changed = True
                if changed:
                    results.append((batch, "retained: local image changed after publication"))
                    continue
                self.last_cleanup_counts["eligible"] += 1
                results.append((batch, "eligible" if dry_run else "cleaned"))
                if dry_run:
                    continue
                ledger.export(batch)
                # Keep durable manifest and compact logs; a crash can safely resume this pass.
                for child in path.iterdir():
                    reject_links(child)
                    if child.name in {"manifest.json", "logs"}:
                        continue
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                for log in (path / "logs").rglob("*"):
                    if log.is_file() and log.stat().st_size > 32768:
                        with log.open("rb") as handle:
                            handle.seek(-32768, 2)
                            tail = handle.read()
                        log.write_bytes(tail)
                self.set_status(batch, "complete")
                self.last_cleanup_counts["deleted"] += 1
                self.last_cleanup_counts["retained"] -= 1
            finally:
                ledger.close()
        return results


def main():
    import argparse
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    register_environment()
    parser = argparse.ArgumentParser(description="Clean only verified, retained batch workspaces")
    parser.add_argument("--apply", action="store_true", help="Default is cleanup dry-run")
    args = parser.parse_args()
    manager = Workspaces()
    try:
        for batch, status in manager.cleanup(dry_run=not args.apply):
            print(batch, status)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
