"""Shared renderer selection, checkpoint identity and bounded input restaging."""

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from people_workspaces import atomic_json, reject_links

DEFAULT_ENGINE = "python"
SCRIPT_DIR = Path(__file__).resolve().parent


def poster_engine():
    engine = os.getenv("POSTER_ENGINE", DEFAULT_ENGINE).strip().lower() or DEFAULT_ENGINE
    if engine not in {"python", "powershell"}:
        raise ValueError("Unknown POSTER_ENGINE; select python (Pillow) or powershell (PowerShell + ImageMagick)")
    return engine


def poster_fingerprint(script_dir=SCRIPT_DIR):
    engine = poster_engine()
    if engine == "python":
        try:
            from create_people_poster import renderer_fingerprint
        except ImportError as error:
            raise ValueError("Python poster dependencies missing; install requirements.txt in the orchestrator venv and requirements-rembg.txt in the recovery venv. No PowerShell fallback was attempted.") from error
        return renderer_fingerprint()
    script = Path(script_dir) / "create_people_poster.ps1"
    fonts = Path(script_dir) / "fonts"
    files = [script, *sorted(fonts.glob("*.ttf"))]
    return {"engine": engine, "files": {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "missing" for p in files}}


def checkpoint_changed(state_dir, fingerprint):
    if (state_dir / "poster_ps1.pending.json").exists():
        return True
    marker = state_dir / "poster_ps1.done.json"
    if not marker.is_file():
        return False
    try:
        previous = json.loads(marker.read_text(encoding="utf-8")).get("poster_fingerprint")
        if previous is None:
            return fingerprint["engine"] != "powershell"
        return previous != fingerprint
    except (OSError, ValueError, AttributeError):
        return True


def prepare_inputs(config, require_retained=False):
    root = config / "people_dirs"
    record = config / ".orch" / "poster-inputs.json"
    inputs = []
    for directory in (root / "Downloads", root / "tmppeople"):
        if directory.is_dir():
            inputs.extend(p.name for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".png" and not p.stem.endswith("_pushed"))
    if inputs:
        atomic_json(record, {"names": sorted(set(inputs))})
        return
    names = []
    if record.is_file():
        names = json.loads(record.read_text(encoding="utf-8"))["names"]
    elif require_retained:
        log = config / "logs" / "create_people_poster.log"
        if log.is_file():
            names = [match + ".png" for match in re.findall(r" ~ Name\s+: ([^\r\n]+)", log.read_text(encoding="utf-8-sig", errors="replace"))]
    for filename in sorted(set(names)):
        if Path(filename).name != filename or "/" in filename or "\\" in filename or Path(filename).suffix.lower() != ".png":
            raise ValueError("Invalid retained poster input filename")
        # Prefer the accepted cutout: recovery may have superseded the raw download.
        source = root / "transparent" / filename[0].upper() / "Images" / filename
        if not source.is_file():
            source = config / "sel_downloads" / filename
        if not source.is_file():
            raise ValueError(f"Retained cutout missing: {filename}. Restage that PNG in people_dirs/Downloads; upstream model steps were not invalidated.")
        target = root / "Downloads" / filename
        reject_links(source)
        reject_links(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if require_retained and not names:
        raise ValueError("Renderer changed but no retained batch cutouts were identified. Restage the desired PNGs in people_dirs/Downloads and retry --redo poster_ps1; do not regenerate unrelated upstream steps.")


def renderer_command(python, script_dir=SCRIPT_DIR, find_powershell=None):
    if poster_engine() == "python":
        return [python, str(Path(script_dir) / "create_people_poster.py")]
    ps = find_powershell() if find_powershell else shutil.which("pwsh")
    if not ps:
        raise ValueError("POSTER_ENGINE=powershell requires PowerShell and ImageMagick; install them or select POSTER_ENGINE=python")
    return [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(Path(script_dir) / "create_people_poster.ps1")]
