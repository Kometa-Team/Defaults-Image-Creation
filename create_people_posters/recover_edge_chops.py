"""Retry chopped transparent portraits using alternate TMDB profile images.

This runs after create_people_poster.ps1. It scans the local cloned People image
repos for warning targets, then finds alternate TMDB profile images.

Default mode writes one viable alternate per person into the normal Downloads
input folder, then runs orchestrator.py from remove_bg so the Selenium/poster
batch and checkpoint resume behavior stay centralized. Inline mode is reserved
for the orchestrator's internal post-poster recovery step or direct debugging.

If no candidate passes the configured retry edges or local prechecks, the person
is reported as exhausted. Exhausted names are skipped on future runs until
removed from the exhausted-name file.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageOps

from edge_chop import detect_edge_chops, has_any_issue, issue_summary, parse_edges
from face_crop import (
    detect_face_crop_issues,
    face_crop_summary,
)


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
PEOPLE_ROOT = CONFIG_DIR / "people_dirs"
DOWNLOADS_DIR = PEOPLE_ROOT / "Downloads"
TRANSPARENT_ROOT = PEOPLE_ROOT / "transparent"
ORIGINAL_ROOT = PEOPLE_ROOT / "original"
OUT_ROOT = CONFIG_DIR / "edge_chop_recovery"
EXHAUSTED_NAMES_FILE = OUT_ROOT / "exhausted_names.txt"
ATTEMPTED_CANDIDATES_FILE = OUT_ROOT / "attempted_candidates.csv"
REMBG_HOME = CONFIG_DIR / "models" / "rembg"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TARGET_SIZE = (2000, 3000)
SAME_IMAGE_HASH_DISTANCE = 8
SAME_IMAGE_MEAN_DELTA = 6.0
RECOVERY_WARNING_CHOICES = {
    "headchop",
    "grayscale",
    "face-chin",
    "face-left",
    "face-right",
}
STYLE_EXTS = {
    "bw": ".jpg",
    "diiivoy": ".jpg",
    "diiivoycolor": ".jpg",
    "original": ".jpg",
    "rainier": ".jpg",
    "signature": ".jpg",
    "transparent": ".png",
}


def env_path(key: str) -> Path | None:
    value = os.getenv(key, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def default_people_root() -> Path:
    explicit = env_path("EDGE_CHOP_PEOPLE_ROOT")
    if explicit:
        return explicit

    repo_root = env_path("PEOPLE_IMAGES_DIR")
    if repo_root:
        return repo_root

    return PEOPLE_ROOT


def default_transparent_root(people_root: Path) -> Path:
    explicit = env_path("EDGE_CHOP_TRANSPARENT_ROOT")
    if explicit:
        return explicit
    return people_root / "transparent"


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


@dataclass(frozen=True)
class ProfileCandidate:
    label: str
    url: str
    file_path: str
    width: int
    height: int
    vote_average: float
    vote_count: int


@dataclass
class RecoveryRow:
    name: str
    status: str
    attempts: int = 0
    grayscale_colorized: int = 0
    grayscale_rejected: int = 0
    precheck_rejected: int = 0
    chosen_label: str = ""
    chosen_url: str = ""
    initial_issues: str = ""
    final_issues: str = ""
    note: str = ""


@dataclass(frozen=True)
class AttemptedCandidate:
    name: str
    file_path: str
    url: str
    label: str
    status: str
    note: str = ""


def log(message: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    line = message.rstrip()
    print(line)
    with (LOGS_DIR / "recover_edge_chops.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def safe_name(name: str) -> str:
    bad = '<>:"/\\|?*\x00'
    cleaned = "".join("_" if ch in bad else ch for ch in name).strip()
    return cleaned or "unknown"


def parse_recover_warnings(value: str | Iterable[str] | None) -> tuple[str, ...]:
    raw = "headchop" if value is None else value
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.split(",")]
    else:
        items = [str(item).strip().lower() for item in raw]

    selected: list[str] = []
    for item in items:
        if item in {"", "none", "false", "off", "0"}:
            continue
        if item in {"all", "*"}:
            for warning in ("headchop", "grayscale", "face-chin", "face-left", "face-right"):
                if warning not in selected:
                    selected.append(warning)
            continue
        if item in {"top", "edge-top", "head", "head-chop", "head_chop"}:
            item = "headchop"
        elif item in {"bw", "b/w", "black-and-white", "black_white", "noncolor", "non-color"}:
            item = "grayscale"
        elif item in {"chin", "bottom-face", "face-bottom"}:
            item = "face-chin"
        elif item in {"left", "left-face"}:
            item = "face-left"
        elif item in {"right", "right-face"}:
            item = "face-right"
        elif item in {"side", "sides", "face-side", "face-sides"}:
            for side in ("face-left", "face-right"):
                if side not in selected:
                    selected.append(side)
            continue
        elif item.startswith("face_"):
            item = item.replace("_", "-")

        if item not in RECOVERY_WARNING_CHOICES:
            raise ValueError(
                f"unknown recover warning '{item}'. Valid values: "
                "headchop, grayscale, face-chin, face-left, face-right, face-side, all"
            )
        if item not in selected:
            selected.append(item)
    return tuple(selected or ["headchop"])


def iter_transparents(root: Path) -> Iterable[Path]:
    if not path_exists(root):
        return
    try:
        walker = os.walk(root)
    except OSError as exc:
        log(f"[warn] transparent scan root is not readable: {root}; {exc}")
        return
    for dirpath, dirnames, filenames in walker:
        dirnames.sort(key=str.casefold)
        if Path(dirpath).name.lower() != "images":
            continue
        for filename in sorted(filenames, key=str.casefold):
            path = Path(dirpath) / filename
            try:
                if path.is_file() and path.suffix.lower() == ".png":
                    yield path
            except OSError:
                continue


def selected_face_checks(recover_warnings: Iterable[str]) -> tuple[str, ...]:
    checks: list[str] = []
    selected = set(recover_warnings)
    if "face-chin" in selected:
        checks.append("chin")
    if "face-left" in selected:
        checks.append("left")
    if "face-right" in selected:
        checks.append("right")
    return tuple(checks)


def transparent_target_issues(path: Path, args: argparse.Namespace) -> list[str]:
    issues: list[str] = []
    selected = set(args.recover_warnings)
    if "headchop" in selected:
        result = detect_edge_chops(path, threshold=args.threshold, edges=args.report_edges)
        summary = issue_summary(result)
        if result.error:
            issues.append(f"edge check error: {summary}")
        elif has_any_issue(result, args.retry_edges):
            issues.append(summary)

    face_checks = selected_face_checks(args.recover_warnings)
    if face_checks:
        result = detect_face_crop_issues(
            path,
            checks=face_checks,
            side_margin_threshold=args.face_crop_side_margin,
            chin_margin_threshold=args.face_crop_chin_margin,
        )
        summary = face_crop_summary(result)
        if result.error:
            issues.append(f"face crop check error: {result.error}")
        elif summary:
            issues.append(summary)
    return issues


def candidate_target_issues(path: Path, args: argparse.Namespace) -> list[str]:
    issues = transparent_target_issues(path, args)
    if "grayscale" in set(args.recover_warnings):
        noncolor = noncolor_summary(
            path,
            sat_threshold=args.grayscale_sat_threshold,
            sat_quantile=args.grayscale_sat_quantile,
            colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
        )
        if noncolor:
            issues.append(f"non-color output: {noncolor}")
    return issues


def find_recovery_targets(
    args: argparse.Namespace,
    exhausted_names: set[str] | None = None,
    modified_since: float | None = None,
    max_matches: int = 0,
) -> tuple[list[tuple[str, Path, str]], int]:
    selected = set(args.recover_warnings)
    targets: dict[str, tuple[str, Path, list[str]]] = {}
    skipped_exhausted = 0
    exhausted_names = exhausted_names or set()
    scan_started = time.time()
    last_progress = scan_started
    transparent_warning_scan = bool(selected.intersection({"headchop", "grayscale", "face-chin", "face-left", "face-right"}))

    def progress(kind: str, scanned: int, current: Path | None = None, force: bool = False) -> None:
        nonlocal last_progress
        every = max(0, int(getattr(args, "scan_progress_every", 0) or 0))
        seconds = max(0.0, float(getattr(args, "scan_progress_seconds", 0.0) or 0.0))
        if every == 0 and seconds == 0 and not force:
            return

        now = time.time()
        if not force:
            by_count = every > 0 and scanned > 0 and scanned % every == 0
            by_time = seconds > 0 and now - last_progress >= seconds
            if not (by_count or by_time):
                return

        elapsed = now - scan_started
        location = f"; current={current}" if current else ""
        limit_text = f"/{max_matches}" if max_matches else ""
        log(
            f"[scan] {kind}: inspected={scanned}; targets={len(targets)}{limit_text}; "
            f"skipped_exhausted={skipped_exhausted}; elapsed={elapsed:.1f}s{location}"
        )
        last_progress = now

    def add_target(name: str, path: Path, issue: str) -> bool:
        nonlocal skipped_exhausted
        key = name.casefold()
        if key in exhausted_names:
            skipped_exhausted += 1
            return False
        if modified_since is not None:
            try:
                if path.stat().st_mtime < modified_since:
                    return False
            except OSError:
                return False
        if key not in targets:
            targets[key] = (name, path, [])
        targets[key][2].append(issue)
        return max_matches > 0 and len(targets) >= max_matches

    if transparent_warning_scan:
        scanned = 0
        progress("transparent", scanned, force=True)
        for path in iter_transparents(args.transparent_root):
            scanned += 1
            progress("transparent", scanned, path)
            name = path.stem
            issues = candidate_target_issues(path, args)
            if issues and add_target(name, path, "; ".join(issues)):
                progress("transparent", scanned, path, force=True)
                return [
                    (name, path, "; ".join(issues))
                    for name, path, issues in targets.values()
                ], skipped_exhausted
        if scanned:
            progress("transparent", scanned, force=True)

    return [
        (name, path, "; ".join(issues))
        for name, path, issues in targets.values()
    ], skipped_exhausted


def load_exhausted_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    names: set[str] = set()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            name = line.strip()
            if name and not name.startswith("#"):
                names.add(name.casefold())
    return names


def append_exhausted_names(path: Path, names: Iterable[str]) -> int:
    unique_names = sorted({name.strip() for name in names if name.strip()}, key=str.casefold)
    if not unique_names:
        return 0

    existing = load_exhausted_names(path)
    to_add = [name for name in unique_names if name.casefold() not in existing]
    if not to_add:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for name in to_add:
            fh.write(name + "\n")
    return len(to_add)


def attempted_key(name: str, file_path: str) -> tuple[str, str]:
    return name.casefold(), file_path


def load_attempted_candidates(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    attempted: set[tuple[str, str]] = set()
    with path.open("r", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("name") or "").strip()
            file_path = (row.get("file_path") or "").strip()
            if name and file_path:
                attempted.add(attempted_key(name, file_path))
    return attempted


def append_attempted_candidates(path: Path, records: Iterable[AttemptedCandidate]) -> int:
    records = list(records)
    if not records:
        return 0

    existing = load_attempted_candidates(path)
    to_add = [record for record in records if attempted_key(record.name, record.file_path) not in existing]
    if not to_add:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["at", "name", "file_path", "url", "label", "status", "note"],
        )
        if write_header:
            writer.writeheader()
        at = str(int(time.time()))
        for record in to_add:
            writer.writerow(
                {
                    "at": at,
                    "name": record.name,
                    "file_path": record.file_path,
                    "url": record.url,
                    "label": record.label,
                    "status": record.status,
                    "note": record.note,
                }
            )
    return len(to_add)


def tmdb_person(session: requests.Session, api_key: str, name: str) -> dict | None:
    response = session.get(
        TMDB_SEARCH_URL,
        params={"api_key": api_key, "query": name, "include_adult": "false", "language": "en-US", "page": "1"},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    exact = [item for item in results if str(item.get("name", "")).casefold() == name.casefold()]
    return next((item for item in (exact or results) if item.get("id")), None)


def tmdb_candidates(session: requests.Session, api_key: str, name: str, limit: int) -> list[ProfileCandidate]:
    person = tmdb_person(session, api_key, name)
    if not person:
        return []
    person_id = int(person["id"])
    response = session.get(f"https://api.themoviedb.org/3/person/{person_id}/images", params={"api_key": api_key}, timeout=30)
    response.raise_for_status()
    profiles = response.json().get("profiles", [])
    profiles = sorted(
        profiles,
        key=lambda item: (
            float(item.get("vote_average") or 0),
            int(item.get("vote_count") or 0),
            int(item.get("width") or 0) * int(item.get("height") or 0),
        ),
        reverse=True,
    )
    out: list[ProfileCandidate] = []
    for idx, item in enumerate(profiles[:limit], start=1):
        file_path = str(item.get("file_path") or "")
        if not file_path:
            continue
        out.append(
            ProfileCandidate(
                label=f"{idx:03d}",
                url=f"{TMDB_IMAGE_BASE}{file_path}",
                file_path=file_path,
                width=int(item.get("width") or 0),
                height=int(item.get("height") or 0),
                vote_average=float(item.get("vote_average") or 0),
                vote_count=int(item.get("vote_count") or 0),
            )
        )
    return out


def download_candidate(session: requests.Session, candidate: ProfileCandidate, target: Path) -> None:
    response = session.get(candidate.url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    with Image.open(target) as img:
        img.verify()


def normalize_to_download(candidate_path: Path, download_path: Path) -> None:
    download_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(candidate_path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        fitted = ImageOps.fit(img, TARGET_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(download_path, "JPEG", quality=95, subsampling=0, optimize=True)


def original_source_paths(people_root: Path, name: str) -> list[Path]:
    first = (name[:1] or "_").upper()
    return [
        people_root / "original" / first / "Images" / f"{name}.jpg",
        people_root / "original" / f"{name}.jpg",
    ]


def image_compare_arrays(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with Image.open(path) as img:
        rgb = ImageOps.exif_transpose(img).convert("RGB")
        fitted = ImageOps.fit(rgb, TARGET_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        gray_small = np.asarray(
            fitted.resize((16, 24), Image.Resampling.LANCZOS).convert("L"),
            dtype=np.float32,
        )
        gray_detail = np.asarray(
            fitted.resize((64, 96), Image.Resampling.LANCZOS).convert("L"),
            dtype=np.float32,
        )
    bits = gray_small >= float(gray_small.mean())
    return bits, gray_detail


def same_image_summary(candidate_path: Path, existing_path: Path) -> str:
    try:
        candidate_bits, candidate_detail = image_compare_arrays(candidate_path)
        existing_bits, existing_detail = image_compare_arrays(existing_path)
    except Exception as exc:
        return f"same-image comparison failed for {existing_path}: {exc}"

    hash_distance = int(np.count_nonzero(candidate_bits != existing_bits))
    mean_delta = float(np.mean(np.abs(candidate_detail - existing_detail)))
    if hash_distance <= SAME_IMAGE_HASH_DISTANCE and mean_delta <= SAME_IMAGE_MEAN_DELTA:
        return (
            f"same as current original {existing_path} "
            f"(hash_distance={hash_distance}, mean_delta={mean_delta:.2f})"
        )
    return ""


def same_as_current_original(candidate_path: Path, people_root: Path, name: str) -> str:
    for existing_path in original_source_paths(people_root, name):
        if not existing_path.exists():
            continue
        summary = same_image_summary(candidate_path, existing_path)
        if summary.startswith("same as current original"):
            return summary
        if summary.startswith("same-image comparison failed"):
            log(f"[warn] {name}: {summary}")
    return ""


def noncolor_summary(
    path: Path,
    sat_threshold: int = 35,
    sat_quantile: float = 0.95,
    colorfulness_cutoff: float = 12.0,
) -> str:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("1", "L", "LA"):
            return f"grayscale mode {img.mode}"

        if "A" in img.getbands():
            rgba = img.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            rgb = Image.alpha_composite(bg, rgba).convert("RGB")
        else:
            rgb = img.convert("RGB")
        r, g, b = rgb.split()
        exact_gray = (
            ImageChops.difference(r, g).getbbox() is None
            and ImageChops.difference(g, b).getbbox() is None
        )
        if exact_gray:
            return "RGB channels are equal"

        sample = ImageOps.contain(rgb, (500, 750), method=Image.Resampling.LANCZOS)
        sat = np.asarray(sample.convert("HSV"))[..., 1].astype(np.uint8)
        sat_q = float(np.quantile(sat, sat_quantile))

        arr = np.asarray(sample, dtype=np.float32)
        red, green, blue = arr[..., 0], arr[..., 1], arr[..., 2]
        rg = red - green
        yb = 0.5 * (red + green) - blue
        colorfulness = float(
            np.hypot(rg.std(), yb.std())
            + 0.3 * np.hypot(np.abs(rg).mean(), np.abs(yb).mean())
        )

        if sat_q <= sat_threshold or colorfulness < colorfulness_cutoff:
            return (
                f"near-grayscale sat_q{sat_quantile:.2f}={sat_q:.1f} <= {sat_threshold} "
                f"or colorfulness={colorfulness:.1f} < {colorfulness_cutoff:.1f}"
            )
    return ""


def colorize_python_candidates() -> list[list[str]]:
    configured = os.getenv("COLORIZE_PYTHON", "").strip().strip("\"'")
    local_venv = SCRIPT_DIR / ".venv-colorize" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    candidates: list[list[str]] = []
    if configured:
        candidates.append([configured])
    candidates.append([str(local_venv)])
    if sys.platform.startswith("win"):
        candidates.append(["py", "-3.10"])
    candidates.append(["python3.10"])

    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def deoldify_candidate(staged_jpg: Path, work_root: Path) -> tuple[bool, str]:
    color_in = work_root / "colorize_other"
    color_out = work_root / "colorize_color"
    color_in.mkdir(parents=True, exist_ok=True)
    color_out.mkdir(parents=True, exist_ok=True)

    input_path = color_in / staged_jpg.name
    output_path = color_out / staged_jpg.name
    for folder in (color_in, color_out):
        for old_file in folder.glob("*"):
            if old_file.is_file():
                old_file.unlink()

    shutil.copy2(staged_jpg, input_path)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["COLORIZE_INPUT_OTHER"] = str(color_in)
    env["COLORIZE_OUTPUT_COLOR"] = str(color_out)

    failures: list[str] = []
    for argv_prefix in colorize_python_candidates():
        try:
            cp = subprocess.run(
                argv_prefix + ["colorize_noncolor.py"],
                cwd=SCRIPT_DIR,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=900,
            )
        except FileNotFoundError as exc:
            failures.append(f"{' '.join(argv_prefix)}: {exc}")
            continue
        except Exception as exc:
            failures.append(f"{' '.join(argv_prefix)}: {exc}")
            continue

        output = (cp.stdout or "").strip()
        if cp.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            normalize_to_download(output_path, staged_jpg)
            return True, f"DeOldify colorized with {' '.join(argv_prefix)}"

        tail = "\n".join(output.splitlines()[-6:])
        failures.append(f"{' '.join(argv_prefix)} exit {cp.returncode}: {tail}")

    return False, "DeOldify failed: " + " | ".join(failures)


def build_rembg_session(model: str):
    try:
        from rembg import new_session
    except ImportError as exc:
        raise RuntimeError("rembg is not installed; run pip install -r requirements.txt") from exc

    return new_session(model)


def rembg_precheck_candidate(args: argparse.Namespace, staged_jpg: Path, precheck_png: Path) -> tuple[bool, str]:
    try:
        from rembg import remove

        with Image.open(staged_jpg) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            output = remove(
                img,
                session=args.rembg_session,
                alpha_matting=args.rembg_alpha_matting,
                post_process_mask=args.rembg_post_process_mask,
            )
        precheck_png.parent.mkdir(parents=True, exist_ok=True)
        if output.mode != "RGBA":
            output = output.convert("RGBA")
        output.save(precheck_png)
    except Exception as exc:
        raise RuntimeError(f"rembg precheck failed for {staged_jpg}: {exc}") from exc

    try:
        issues = candidate_target_issues(precheck_png, args)
    except Exception as exc:
        raise RuntimeError(f"rembg precheck could not audit {precheck_png}: {exc}") from exc
    if issues:
        return False, "; ".join(issues)
    return True, "selected recovery warnings cleared"


def style_file_paths(people_root: Path, name: str) -> list[Path]:
    first = (name[:1] or "_").upper()
    paths: list[Path] = []
    for style, ext in STYLE_EXTS.items():
        root = people_root / style
        paths.append(root / first / "Images" / f"{name}{ext}")
        paths.append(root / f"{name}{ext}")
    paths.extend(
        [
            people_root / "Downloads" / f"{name}.jpg",
            people_root / "Downloads" / f"{name}.png",
            people_root / "tmppeople" / f"{name}.png",
            people_root / "tmppeople" / f"{name}_pushed.png",
        ]
    )
    return paths


def backup_existing(paths: Iterable[Path], backup_root: Path, people_root: Path) -> list[tuple[Path, Path]]:
    backups: list[tuple[Path, Path]] = []
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        rel = path.resolve().relative_to(people_root.resolve())
        backup_path = backup_root / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
        backups.append((path, backup_path))
    return backups


def remove_style_outputs(paths: Iterable[Path]) -> None:
    for path in paths:
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass


def restore_backups(backups: list[tuple[Path, Path]], paths: Iterable[Path]) -> None:
    remove_style_outputs(paths)
    for target, backup in backups:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, target)


def ps_exe() -> str | None:
    candidates = ["pwsh"]
    if sys.platform.startswith("win"):
        candidates += ["powershell", "powershell.exe"]
    for exe in candidates:
        try:
            cp = subprocess.run(
                [exe, "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.Major"],
                cwd=SCRIPT_DIR,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            if cp.returncode == 0:
                return exe
        except Exception:
            continue
    return None


def run_step(title: str, argv: list[str], env: dict[str, str]) -> int:
    log(f"=== {title} ===")
    log("-> " + " ".join(argv))
    cp = subprocess.run(argv, cwd=SCRIPT_DIR, env=env)
    log(f"{title} exit code: {cp.returncode}")
    return cp.returncode


def run_orchestrator_from_remove_bg(stop_after: str | None = None) -> int:
    argv = [sys.executable, "orchestrator.py", "--redo", "remove_bg", "--no-recover-edge-chops"]
    if stop_after:
        argv.extend(["--stop-after", stop_after])
    return run_step("orchestrator recovery batch", argv, os.environ.copy())


def run_orchestrator_from_update() -> int:
    argv = [sys.executable, "orchestrator.py", "--redo", "update", "--no-recover-edge-chops"]
    return run_step("orchestrator recovery sync/push", argv, os.environ.copy())


def final_transparent_path(people_root: Path, name: str) -> Path:
    return people_root / "transparent" / (name[:1] or "_").upper() / "Images" / f"{name}.png"


def postcheck_staged_outputs(rows: list[RecoveryRow], args: argparse.Namespace) -> int:
    checked = 0
    for row in rows:
        if row.status != "staged" or not row.name:
            continue

        checked += 1
        transparent = final_transparent_path(args.people_root, row.name)
        if not transparent.exists():
            row.status = "unresolved"
            row.final_issues = f"final transparent output missing: {transparent}"
            row.note += "; post-orchestrator check failed; rerun recovery after fixing the pipeline output"
            log(f"[postcheck] {row.name}: {row.final_issues}")
            continue

        try:
            issues = candidate_target_issues(transparent, args)
        except Exception as exc:
            row.status = "unresolved"
            row.final_issues = f"final selected-warning check failed: {exc}"
            row.note += "; post-orchestrator check failed; rerun recovery after fixing the QA error"
            log(f"[postcheck] {row.name}: {row.final_issues}")
            continue

        if issues:
            row.status = "unresolved"
            row.final_issues = "; ".join(issues)
            row.note += "; post-orchestrator final output still has selected warning(s); rerun recovery to try the next TMDB candidate"
            log(f"[postcheck] {row.name}: final output still has selected warning(s): {row.final_issues}")
        else:
            row.status = "recovered"
            row.final_issues = ""
            row.note += "; post-orchestrator final QA passed"
            log(f"[postcheck] {row.name}: final selected-warning QA passed")
    return checked


def remove_unresolved_work_outputs(rows: list[RecoveryRow], people_root: Path) -> int:
    removed = 0
    for row in rows:
        if row.status != "unresolved" or not row.name or not row.chosen_url:
            continue
        for path in style_file_paths(people_root, row.name):
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    removed += 1
            except OSError:
                pass
    if removed:
        log(f"[postcheck] removed {removed} unresolved generated work output(s) before sync")
    return removed


def log_status_counts(rows: list[RecoveryRow], prefix: str = "") -> None:
    label = f"{prefix} " if prefix else ""
    log(f"{label}Recovered: {sum(1 for row in rows if row.status == 'recovered')}")
    log(f"{label}Staged: {sum(1 for row in rows if row.status == 'staged')}")
    log(f"{label}Unresolved: {sum(1 for row in rows if row.status == 'unresolved')}")
    log(f"{label}Exhausted: {sum(1 for row in rows if row.status == 'exhausted')}")


def downloads_pngs_are_clear(name: str, downloads_dir: Path) -> bool:
    allowed = {f"{name}.png"}
    for path in downloads_dir.glob("*"):
        if path.is_file() and path.suffix.lower() == ".png" and path.name not in allowed:
            return False
    return True


def recover_one(args: argparse.Namespace, session: requests.Session, api_key: str, name: str, initial_issues: str) -> RecoveryRow:
    row = RecoveryRow(name=name, status="unresolved", initial_issues=initial_issues)
    paths = style_file_paths(args.people_root, name)
    with tempfile.TemporaryDirectory(prefix=f"edge_chop_{safe_name(name)}_") as tmp:
        backup_root = Path(tmp) / "backup"
        backups = backup_existing(paths, backup_root, args.people_root)

        try:
            candidates = tmdb_candidates(session, api_key, name, args.tmdb_limit)
        except Exception as exc:
            row.note = f"TMDB lookup failed: {exc}"
            return row

        if not candidates:
            row.status = "exhausted"
            row.note = "no TMDB profile candidates"
            return row

        if not downloads_pngs_are_clear(name, args.downloads_dir):
            row.note = f"downloads folder has unrelated PNGs; skipped to avoid poster generation processing the wrong files: {args.downloads_dir}"
            return row

        sel_src_dir = Path(tmp) / "sel_src"
        sel_orig_dir = Path(tmp) / "sel_original"
        sel_download_dir = Path(tmp) / "sel_downloads"
        for work_dir in (sel_src_dir, sel_orig_dir, sel_download_dir, args.downloads_dir):
            work_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["SEL_SRC_DIR"] = str(sel_src_dir)
        env["SEL_ORIG_DIR"] = str(sel_orig_dir)
        env["SEL_DOWNLOAD_DIR"] = str(sel_download_dir)

        ps = ps_exe()
        if not ps:
            row.note = "PowerShell is unavailable"
            return row

        candidate_dir = args.out_root / "candidates" / safe_name(name)
        for candidate in candidates:
            row.attempts += 1
            raw_path = candidate_dir / f"{candidate.label}{Path(candidate.file_path).suffix or '.jpg'}"
            staged_jpg = sel_src_dir / f"{name}.jpg"
            generated_png = sel_src_dir / f"{name}.png"
            staged_png = args.downloads_dir / f"{name}.png"
            try:
                remove_style_outputs(paths)
                for old_file in sel_src_dir.glob("*"):
                    if old_file.is_file():
                        old_file.unlink()
                download_candidate(session, candidate, raw_path)
                normalize_to_download(raw_path, staged_jpg)
            except Exception as exc:
                log(f"[warn] {name} {candidate.label}: candidate download/normalize failed: {exc}")
                continue

            if args.reject_grayscale:
                try:
                    noncolor = noncolor_summary(
                        staged_jpg,
                        sat_threshold=args.grayscale_sat_threshold,
                        sat_quantile=args.grayscale_sat_quantile,
                        colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
                    )
                except Exception as exc:
                    restore_backups(backups, paths)
                    raise RuntimeError(f"{name} {candidate.label}: grayscale candidate check failed: {exc}") from exc
                if noncolor:
                    if args.colorize_grayscale:
                        log(f"[candidate] {name} {candidate.label}: non-color candidate; trying DeOldify: {noncolor}")
                        ok, note = deoldify_candidate(staged_jpg, Path(tmp) / "deoldify")
                        if ok:
                            try:
                                noncolor = noncolor_summary(
                                    staged_jpg,
                                    sat_threshold=args.grayscale_sat_threshold,
                                    sat_quantile=args.grayscale_sat_quantile,
                                    colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
                                )
                            except Exception as exc:
                                restore_backups(backups, paths)
                                raise RuntimeError(f"{name} {candidate.label}: grayscale candidate recheck failed: {exc}") from exc
                            if not noncolor:
                                row.grayscale_colorized += 1
                                log(f"[candidate] {name} {candidate.label}: {note}")
                            else:
                                row.grayscale_rejected += 1
                                log(f"[candidate] {name} {candidate.label}: DeOldify output still non-color; skipped before rembg/Adobe: {noncolor}")
                                continue
                        else:
                            row.grayscale_rejected += 1
                            log(f"[candidate] {name} {candidate.label}: non-color candidate skipped before rembg/Adobe; {note}")
                            continue
                    else:
                        row.grayscale_rejected += 1
                        log(f"[candidate] {name} {candidate.label}: non-color candidate skipped before rembg/Adobe: {noncolor}")
                        continue

            if args.precheck_rembg:
                precheck_png = candidate_dir / f"{candidate.label}.rembg.png"
                try:
                    should_try, precheck_summary = rembg_precheck_candidate(args, staged_jpg, precheck_png)
                except RuntimeError as exc:
                    restore_backups(backups, paths)
                    raise RuntimeError(f"{name} {candidate.label}: {exc}") from exc
                if not should_try:
                    row.precheck_rejected += 1
                    log(f"[precheck] {name} {candidate.label}: rembg still has selected warning(s): {precheck_summary}")
                    continue
                if precheck_summary:
                    log(f"[precheck] {name} {candidate.label}: rembg cleared selected warning(s); {precheck_summary}")

            rc = run_step(f"remove-bg retry {name} {candidate.label}", [sys.executable, "sel_remove_bg.py"], env)
            if rc != 0:
                log(f"[warn] {name} {candidate.label}: remove-bg failed")
                continue
            if not generated_png.exists():
                log(f"[warn] {name} {candidate.label}: remove-bg did not produce {generated_png}")
                continue

            shutil.copy2(generated_png, staged_png)

            rc = run_step(
                f"poster retry {name} {candidate.label}",
                [ps, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT_DIR / "create_people_poster.ps1")],
                env,
            )
            if rc != 0:
                log(f"[warn] {name} {candidate.label}: poster generation failed")
                continue

            transparent = final_transparent_path(args.people_root, name)
            if args.reject_grayscale:
                try:
                    final_noncolor = noncolor_summary(
                        transparent,
                        sat_threshold=args.grayscale_sat_threshold,
                        sat_quantile=args.grayscale_sat_quantile,
                        colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
                    )
                except Exception as exc:
                    restore_backups(backups, paths)
                    raise RuntimeError(f"{name} {candidate.label}: grayscale final check failed: {exc}") from exc
                if final_noncolor:
                    row.grayscale_rejected += 1
                    log(f"[retry] {name} {candidate.label}: final transparent is non-color; trying next candidate: {final_noncolor}")
                    continue

            try:
                final_issues = candidate_target_issues(transparent, args)
            except Exception as exc:
                restore_backups(backups, paths)
                raise RuntimeError(f"{name} {candidate.label}: final selected-warning check failed: {exc}") from exc

            if not final_issues:
                row.status = "recovered"
                row.chosen_label = candidate.label
                row.chosen_url = candidate.url
                row.final_issues = ""
                row.note = "accepted TMDB alternate"
                if row.grayscale_colorized:
                    row.note += f"; DeOldify colorized {row.grayscale_colorized} candidates"
                if row.grayscale_rejected:
                    row.note += f"; non-color checks rejected {row.grayscale_rejected} candidates"
                if row.precheck_rejected:
                    row.note += f"; rembg precheck rejected {row.precheck_rejected} earlier candidates"
                return row

            log(f"[retry] {name} {candidate.label} still has selected warning(s): {'; '.join(final_issues)}")

        restore_backups(backups, paths)
        current = final_transparent_path(args.people_root, name)
        row.final_issues = "; ".join(candidate_target_issues(current, args)) if current.exists() else ""
        row.status = "exhausted"
        row.note = "no TMDB alternate cleared selected recovery warnings; restored previous local outputs"
        if row.grayscale_colorized:
            row.note += f"; DeOldify colorized {row.grayscale_colorized} candidates"
        if row.grayscale_rejected:
            row.note += f"; non-color checks rejected {row.grayscale_rejected} candidates"
        if row.precheck_rejected:
            row.note += f"; rembg precheck rejected {row.precheck_rejected} candidates before Adobe"
        return row


def stage_one_for_orchestrator(
    args: argparse.Namespace,
    session: requests.Session,
    api_key: str,
    name: str,
    initial_issues: str,
    attempted_candidates: set[tuple[str, str]],
    attempted_records: list[AttemptedCandidate],
) -> RecoveryRow:
    row = RecoveryRow(name=name, status="unresolved", initial_issues=initial_issues)
    try:
        candidates = tmdb_candidates(session, api_key, name, args.tmdb_limit)
    except Exception as exc:
        row.note = f"TMDB lookup failed: {exc}"
        return row

    if not candidates:
        row.status = "exhausted"
        row.note = "no TMDB profile candidates"
        return row

    candidate_dir = args.out_root / "candidates" / safe_name(name)
    with tempfile.TemporaryDirectory(prefix=f"edge_chop_stage_{safe_name(name)}_") as tmp:
        staged_jpg = Path(tmp) / f"{name}.jpg"
        for candidate in candidates:
            key = attempted_key(name, candidate.file_path)
            if key in attempted_candidates:
                continue

            row.attempts += 1
            raw_path = candidate_dir / f"{candidate.label}{Path(candidate.file_path).suffix or '.jpg'}"

            def record_attempt(status: str, note: str = "") -> None:
                attempted_candidates.add(key)
                attempted_records.append(
                    AttemptedCandidate(
                        name=name,
                        file_path=candidate.file_path,
                        url=candidate.url,
                        label=candidate.label,
                        status=status,
                        note=note,
                    )
                )

            try:
                download_candidate(session, candidate, raw_path)
                normalize_to_download(raw_path, staged_jpg)
            except Exception as exc:
                note = f"candidate download/normalize failed: {exc}"
                log(f"[warn] {name} {candidate.label}: {note}")
                record_attempt("download_failed", note)
                continue

            same_source = same_as_current_original(staged_jpg, args.people_root, name)
            if same_source:
                note = f"skipped before staging; {same_source}"
                log(f"[candidate] {name} {candidate.label}: {note}")
                record_attempt("same_as_current_original", note)
                continue

            if args.reject_grayscale:
                try:
                    noncolor = noncolor_summary(
                        staged_jpg,
                        sat_threshold=args.grayscale_sat_threshold,
                        sat_quantile=args.grayscale_sat_quantile,
                        colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
                    )
                except Exception as exc:
                    raise RuntimeError(f"{name} {candidate.label}: grayscale candidate check failed: {exc}") from exc
                if noncolor:
                    if args.colorize_grayscale:
                        log(f"[candidate] {name} {candidate.label}: non-color candidate; trying DeOldify: {noncolor}")
                        ok, note = deoldify_candidate(staged_jpg, Path(tmp) / "deoldify")
                        if ok:
                            try:
                                noncolor = noncolor_summary(
                                    staged_jpg,
                                    sat_threshold=args.grayscale_sat_threshold,
                                    sat_quantile=args.grayscale_sat_quantile,
                                    colorfulness_cutoff=args.grayscale_colorfulness_cutoff,
                                )
                            except Exception as exc:
                                raise RuntimeError(f"{name} {candidate.label}: grayscale candidate recheck failed: {exc}") from exc
                            if not noncolor:
                                row.grayscale_colorized += 1
                                log(f"[candidate] {name} {candidate.label}: {note}")
                            else:
                                row.grayscale_rejected += 1
                                note = f"DeOldify output still non-color: {noncolor}"
                                log(f"[candidate] {name} {candidate.label}: {note}")
                                record_attempt("grayscale_rejected", note)
                                continue
                        else:
                            row.grayscale_rejected += 1
                            log(f"[candidate] {name} {candidate.label}: non-color candidate skipped before staging; {note}")
                            record_attempt("grayscale_rejected", note)
                            continue
                    else:
                        row.grayscale_rejected += 1
                        log(f"[candidate] {name} {candidate.label}: non-color candidate skipped before staging: {noncolor}")
                        record_attempt("grayscale_rejected", noncolor)
                        continue

            if args.precheck_rembg:
                precheck_png = candidate_dir / f"{candidate.label}.rembg.png"
                try:
                    should_try, precheck_summary = rembg_precheck_candidate(args, staged_jpg, precheck_png)
                except RuntimeError as exc:
                    raise RuntimeError(f"{name} {candidate.label}: {exc}") from exc
                if not should_try:
                    row.precheck_rejected += 1
                    log(f"[precheck] {name} {candidate.label}: rembg still has selected warning(s): {precheck_summary}")
                    record_attempt("precheck_rejected", precheck_summary)
                    continue
                if precheck_summary:
                    log(f"[precheck] {name} {candidate.label}: rembg cleared selected warning(s); {precheck_summary}")

            target = args.downloads_dir / f"{name}.jpg"
            args.downloads_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_jpg, target)
            row.status = "staged"
            row.chosen_label = candidate.label
            row.chosen_url = candidate.url
            row.note = f"staged for orchestrator remove_bg: {target}"
            record_attempt("staged", row.note)
            return row

    row.status = "exhausted"
    row.note = "no untried TMDB alternate cleared selected local recovery prechecks"
    if row.grayscale_colorized:
        row.note += f"; DeOldify colorized {row.grayscale_colorized} candidates"
    if row.grayscale_rejected:
        row.note += f"; non-color checks rejected {row.grayscale_rejected} candidates"
    if row.precheck_rejected:
        row.note += f"; rembg precheck rejected {row.precheck_rejected} candidates before Adobe"
    return row


def write_report(out_root: Path, rows: list[RecoveryRow]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    path = out_root / "edge_chop_recovery.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "name",
                "status",
                "attempts",
                "grayscale_colorized",
                "grayscale_rejected",
                "precheck_rejected",
                "chosen_label",
                "chosen_url",
                "initial_issues",
                "final_issues",
                "note",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "name": row.name,
                    "status": row.status,
                    "attempts": row.attempts,
                    "grayscale_colorized": row.grayscale_colorized,
                    "grayscale_rejected": row.grayscale_rejected,
                    "precheck_rejected": row.precheck_rejected,
                    "chosen_label": row.chosen_label,
                    "chosen_url": row.chosen_url,
                    "initial_issues": row.initial_issues,
                    "final_issues": row.final_issues,
                    "note": row.note,
                }
            )
    log(f"Report: {path}")


def parser() -> argparse.ArgumentParser:
    load_dotenv(CONFIG_DIR / ".env")
    people_root = default_people_root()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--people-root",
        type=Path,
        default=people_root,
        help="Root containing local cloned People image repos; defaults to EDGE_CHOP_PEOPLE_ROOT, then PEOPLE_IMAGES_DIR.",
    )
    ap.add_argument(
        "--transparent-root",
        type=Path,
        default=default_transparent_root(people_root),
        help="Transparent style repo/tree to audit; defaults to EDGE_CHOP_TRANSPARENT_ROOT, then people-root/transparent.",
    )
    ap.add_argument("--downloads-dir", type=Path, default=Path(os.getenv("EDGE_CHOP_DOWNLOADS_DIR") or DOWNLOADS_DIR))
    ap.add_argument("--out-root", type=Path, default=Path(os.getenv("EDGE_CHOP_OUT_ROOT") or OUT_ROOT))
    ap.add_argument(
        "--exhausted-file",
        type=Path,
        default=Path(os.getenv("EDGE_CHOP_EXHAUSTED_FILE") or EXHAUSTED_NAMES_FILE),
        help="Names listed here are skipped on future recovery runs until removed from the file.",
    )
    ap.add_argument(
        "--attempted-file",
        type=Path,
        default=Path(os.getenv("EDGE_CHOP_ATTEMPTED_FILE") or ATTEMPTED_CANDIDATES_FILE),
        help="TMDB candidate attempts already staged or rejected by local prechecks.",
    )
    ap.add_argument("--threshold", type=float, default=float(os.getenv("EDGE_CHOP_THRESHOLD", "0.06")))
    ap.add_argument(
        "--recover-warnings",
        default=os.getenv("EDGE_CHOP_RECOVER_WARNINGS", "headchop"),
        help="Comma list of warnings to recover: headchop, grayscale, face-chin, face-left, face-right, face-side, all.",
    )
    ap.add_argument("--report-edges", default=os.getenv("EDGE_CHOP_REPORT_EDGES", "top"))
    ap.add_argument("--retry-edges", default=os.getenv("EDGE_CHOP_RETRY_EDGES", "top"))
    ap.add_argument("--tmdb-limit", type=int, default=int(os.getenv("EDGE_CHOP_TMDB_LIMIT", "12")))
    ap.add_argument("--precheck-rembg", dest="precheck_rembg", action="store_true", default=env_bool("EDGE_CHOP_PRECHECK_REMBG", True))
    ap.add_argument("--no-precheck-rembg", dest="precheck_rembg", action="store_false")
    ap.add_argument("--rembg-model", default=os.getenv("EDGE_CHOP_REMBG_MODEL", "u2net"))
    ap.add_argument("--rembg-home", type=Path, default=Path(os.getenv("REMBG_HOME") or REMBG_HOME))
    ap.add_argument("--rembg-alpha-matting", action="store_true", default=env_bool("EDGE_CHOP_REMBG_ALPHA_MATTING", False))
    ap.add_argument("--rembg-post-process-mask", dest="rembg_post_process_mask", action="store_true", default=env_bool("EDGE_CHOP_REMBG_POST_PROCESS_MASK", True))
    ap.add_argument("--no-rembg-post-process-mask", dest="rembg_post_process_mask", action="store_false")
    ap.add_argument("--reject-grayscale", dest="reject_grayscale", action="store_true", default=env_bool("EDGE_CHOP_REJECT_GRAYSCALE", True))
    ap.add_argument("--allow-grayscale", dest="reject_grayscale", action="store_false")
    ap.add_argument("--colorize-grayscale", dest="colorize_grayscale", action="store_true", default=env_bool("EDGE_CHOP_COLORIZE_GRAYSCALE", True))
    ap.add_argument("--no-colorize-grayscale", dest="colorize_grayscale", action="store_false")
    ap.add_argument("--grayscale-sat-threshold", type=int, default=int(os.getenv("EDGE_CHOP_GRAYSCALE_SAT_THRESHOLD", "35")))
    ap.add_argument("--grayscale-sat-quantile", type=float, default=float(os.getenv("EDGE_CHOP_GRAYSCALE_SAT_QUANTILE", "0.95")))
    ap.add_argument("--grayscale-colorfulness-cutoff", type=float, default=float(os.getenv("EDGE_CHOP_GRAYSCALE_COLORFULNESS_CUTOFF", "12.0")))
    ap.add_argument("--face-crop-side-margin", type=float, default=float(os.getenv("EDGE_CHOP_FACE_CROP_SIDE_MARGIN", os.getenv("IMAGE_CHECK_FACE_CROP_SIDE_MARGIN", "0.02"))))
    ap.add_argument("--face-crop-chin-margin", type=float, default=float(os.getenv("EDGE_CHOP_FACE_CROP_CHIN_MARGIN", os.getenv("IMAGE_CHECK_FACE_CROP_CHIN_MARGIN", "0.015"))))
    ap.add_argument("--limit", type=int, default=0, help="Maximum chopped people to attempt; 0 means all")
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--modified-since", type=float, help="Only retry transparent PNGs modified at/after this Unix timestamp")
    ap.add_argument("--modified-within-hours", type=float, default=0.0, help="Only retry transparent PNGs modified within this many hours")
    ap.add_argument(
        "--scan-progress-every",
        type=int,
        default=int(os.getenv("EDGE_CHOP_SCAN_PROGRESS_EVERY", "500")),
        help="Log target-discovery progress every N inspected files; 0 disables count-based progress.",
    )
    ap.add_argument(
        "--scan-progress-seconds",
        type=float,
        default=float(os.getenv("EDGE_CHOP_SCAN_PROGRESS_SECONDS", "30")),
        help="Log target-discovery progress at least every N seconds; 0 disables time-based progress.",
    )
    ap.add_argument("--all", action="store_true", help="Allow whole-tree recovery attempts")
    ap.add_argument("--audit-only", action="store_true", help="Scan and report matching edge chops without retrying")
    ap.add_argument(
        "--inline",
        action="store_true",
        default=env_bool("EDGE_CHOP_INLINE", False),
        help="Advanced/internal: run the direct retry loop instead of staging candidates and handing off to orchestrator.",
    )
    ap.add_argument(
        "--stage-only",
        action="store_true",
        default=env_bool("EDGE_CHOP_STAGE_ONLY", False),
        help="Stage viable candidates but do not run orchestrator automatically.",
    )
    ap.add_argument("--stage-for-orchestrator", action="store_true", default=False, help=argparse.SUPPRESS)
    ap.add_argument("--run-orchestrator", action="store_true", default=False, help=argparse.SUPPRESS)
    return ap


def main() -> int:
    args = parser().parse_args()
    args.people_root = args.people_root.resolve()
    args.transparent_root = args.transparent_root.resolve()
    args.downloads_dir = args.downloads_dir.resolve()
    args.out_root = args.out_root.resolve()
    args.exhausted_file = args.exhausted_file.resolve()
    args.attempted_file = args.attempted_file.resolve()
    args.rembg_home = args.rembg_home.resolve()
    try:
        args.recover_warnings = parse_recover_warnings(args.recover_warnings)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    args.report_edges = parse_edges(args.report_edges, ("top",))
    args.retry_edges = parse_edges(args.retry_edges, ("top",))
    args.rembg_session = None
    raw_stage_for_orchestrator = args.stage_for_orchestrator
    raw_run_orchestrator = args.run_orchestrator
    legacy_stage_only = args.stage_for_orchestrator and not args.run_orchestrator

    log("#### START recover_edge_chops ####")
    if args.inline and (args.stage_only or raw_stage_for_orchestrator or raw_run_orchestrator):
        rows = [
            RecoveryRow(
                name="",
                status="error",
                note="--inline cannot be combined with orchestrator staging flags",
            )
        ]
        write_report(args.out_root, rows)
        log("[error] --inline cannot be combined with orchestrator staging flags")
        return 2
    if args.inline:
        args.stage_for_orchestrator = False
        args.run_orchestrator = False
    else:
        args.stage_for_orchestrator = True
        args.run_orchestrator = not (args.stage_only or legacy_stage_only)
        if args.run_orchestrator:
            args.stage_only = False

    api_key = os.getenv("TMDB_KEY", "").strip()
    if not api_key:
        rows = [RecoveryRow(name="", status="skipped", note="TMDB_KEY missing")]
        write_report(args.out_root, rows)
        log("[warn] TMDB_KEY missing; edge-chop recovery skipped.")
        return 0

    modified_since = args.modified_since
    if args.modified_within_hours > 0:
        import time

        modified_since = max(modified_since or 0.0, time.time() - (args.modified_within_hours * 3600.0))

    if not (args.all or args.names or modified_since is not None):
        rows = [
            RecoveryRow(
                name="",
                status="skipped",
                note=(
                    "no recovery scope provided; pass --all, --names, "
                    "--modified-since, or --modified-within-hours"
                ),
            )
        ]
        write_report(args.out_root, rows)
        log("[info] Whole-tree recovery skipped without scanning to avoid large Adobe retry runs.")
        return 0

    exhausted_names = load_exhausted_names(args.exhausted_file)
    if exhausted_names:
        log(f"[info] skipping {len(exhausted_names)} exhausted name(s) from {args.exhausted_file}")
    log(f"[info] recover warnings: {', '.join(args.recover_warnings)}")
    log(f"[info] scan people root: {args.people_root}")
    log(f"[info] scan transparent root: {args.transparent_root}")
    if selected_face_checks(args.recover_warnings) or "headchop" in set(args.recover_warnings):
        if not path_exists(args.transparent_root):
            log(
                "[warn] transparent scan root does not exist; no transparent "
                f"head/face-crop targets can be found or read: {args.transparent_root}"
            )

    scan_limit = 0 if args.names else args.limit
    chopped, skipped_exhausted = find_recovery_targets(
        args,
        exhausted_names=exhausted_names,
        modified_since=modified_since,
        max_matches=scan_limit,
    )
    if skipped_exhausted:
        log(f"[info] skipped {skipped_exhausted} recovery target(s) already listed as exhausted")
    if args.names:
        wanted = {name.casefold() for name in args.names}
        chopped = [item for item in chopped if item[0].casefold() in wanted]
        requested_exhausted = [name for name in args.names if name.casefold() in exhausted_names]
        for name in requested_exhausted:
            log(f"[info] {name}: skipped because it is listed in {args.exhausted_file}")

    log(f"Recovery targets needing retry: {len(chopped)}")
    if args.audit_only:
        rows = [
            RecoveryRow(name=name, status="audit", initial_issues=issues, note=str(path))
            for name, path, issues in chopped
        ]
        write_report(args.out_root, rows)
        return 0

    if not chopped:
        write_report(args.out_root, [])
        return 0

    if args.stage_for_orchestrator:
        existing_inputs = sorted(
            path for path in args.downloads_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ) if args.downloads_dir.exists() else []
        if existing_inputs:
            rows = [
                RecoveryRow(
                    name="",
                    status="error",
                    note=(
                        "downloads folder is not empty; run the pending orchestrator batch "
                        f"or clear this folder before staging recovery inputs: {args.downloads_dir}"
                    ),
                )
            ]
            write_report(args.out_root, rows)
            log(f"[error] downloads folder is not empty: {args.downloads_dir}")
            for path in existing_inputs[:20]:
                log(f"[error] existing input: {path}")
            if len(existing_inputs) > 20:
                log(f"[error] existing input count truncated: {len(existing_inputs)} total")
            log("[next] These files are already staged for the normal pipeline.")
            log("[next] Run: python orchestrator.py --redo remove_bg --no-recover-edge-chops")
            log("[next] After that finishes, rerun this recovery command for the next batch.")
            log("[next] Only clear Downloads manually if you intentionally want to discard those staged inputs.")
            return 2

    if args.precheck_rembg:
        args.rembg_home.mkdir(parents=True, exist_ok=True)
        os.environ["REMBG_HOME"] = str(args.rembg_home)
        try:
            args.rembg_session = build_rembg_session(args.rembg_model)
        except RuntimeError as exc:
            log(f"[error] {exc}")
            return 2
        except Exception as exc:
            log(f"[error] rembg precheck could not initialize model {args.rembg_model}: {exc}")
            return 2
        log(f"[info] rembg precheck enabled with model: {args.rembg_model}; home: {args.rembg_home}")
    else:
        log("[info] rembg precheck disabled")
    if args.reject_grayscale:
        log(
            "[info] non-color recovery candidates rejected "
            f"(sat q{args.grayscale_sat_quantile:.2f}<={args.grayscale_sat_threshold}, "
            f"colorfulness<{args.grayscale_colorfulness_cutoff:.1f})"
        )
        if args.colorize_grayscale:
            log("[info] non-color recovery candidates are sent through DeOldify before rejection")
    else:
        log("[info] non-color recovery candidates allowed")

    rows: list[RecoveryRow] = []
    attempted_candidates = load_attempted_candidates(args.attempted_file)
    attempted_records: list[AttemptedCandidate] = []
    if args.stage_for_orchestrator and attempted_candidates:
        log(f"[info] skipping {len(attempted_candidates)} attempted TMDB candidate(s) from {args.attempted_file}")
    session = requests.Session()
    exit_code = 0
    for idx, (name, path, issues) in enumerate(chopped, start=1):
        log(f"[{idx}/{len(chopped)}] {name}: {issues}")
        try:
            if args.stage_for_orchestrator:
                row = stage_one_for_orchestrator(
                    args,
                    session,
                    api_key,
                    name,
                    issues,
                    attempted_candidates,
                    attempted_records,
                )
            else:
                row = recover_one(args, session, api_key, name, issues)
        except RuntimeError as exc:
            row = RecoveryRow(name=name, status="error", initial_issues=issues, note=str(exc))
            exit_code = 2
            rows.append(row)
            log(f"{name}: error; {row.note}")
            break
        rows.append(row)
        log(f"{name}: {row.status}; attempts={row.attempts}; {row.note}")

    write_report(args.out_root, rows)
    added_attempted = append_attempted_candidates(args.attempted_file, attempted_records)
    added_exhausted = append_exhausted_names(
        args.exhausted_file,
        (row.name for row in rows if row.status == "exhausted"),
    )
    log_status_counts(rows)
    if added_attempted:
        log(f"Added attempted TMDB candidates: {added_attempted} -> {args.attempted_file}")
    if added_exhausted:
        log(f"Added exhausted names: {added_exhausted} -> {args.exhausted_file}")
    staged = sum(1 for row in rows if row.status == "staged")
    if args.stage_for_orchestrator and staged:
        command = "python orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1"
        continue_command = "python orchestrator.py --redo update --no-recover-edge-chops"
        if args.run_orchestrator:
            log(f"Running next command: {command}")
            exit_code = run_orchestrator_from_remove_bg(stop_after="poster_ps1")
            if exit_code == 4:
                log("[auth] Adobe login stopped the orchestrator recovery batch.")
                log("[next] Run: python sel_remove_bg.py --login-only")
                log("[next] Then resume: python orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1")
            elif exit_code == 0:
                checked = postcheck_staged_outputs(rows, args)
                if checked:
                    write_report(args.out_root, rows)
                    log_status_counts(rows, prefix="Postcheck")
                    unresolved_after = sum(1 for row in rows if row.status == "unresolved")
                    if unresolved_after:
                        remove_unresolved_work_outputs(rows, args.people_root)
                        write_report(args.out_root, rows)
                        log("[next] Some staged candidates still failed selected warning QA after Adobe.")
                        log("[next] Removed unresolved generated work outputs before repo sync.")
                        log("[next] Rerun this recovery command later to skip those attempted TMDB images and try the next candidates.")
                    recovered_after = sum(1 for row in rows if row.status == "recovered")
                    if recovered_after:
                        log(f"Running next command: {continue_command}")
                        exit_code = run_orchestrator_from_update()
                    else:
                        log("[next] No recovered staged candidates to sync/push.")
                else:
                    log(f"Running next command: {continue_command}")
                    exit_code = run_orchestrator_from_update()
            else:
                log("[next] Orchestrator did not finish cleanly; resolve the logged failure, then resume:")
                log("[next] python orchestrator.py --redo remove_bg --no-recover-edge-chops --stop-after poster_ps1")
        else:
            log(f"Next command: {command}")
    elif args.stage_for_orchestrator:
        log("Next command: no staged candidates; remove names from the exhausted/attempted files only if you want to retry them.")
    else:
        log("Next command: python orchestrator.py --redo update")
    log("#### END recover_edge_chops ####")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
