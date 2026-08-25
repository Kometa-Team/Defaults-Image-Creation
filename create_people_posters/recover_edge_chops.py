"""Retry chopped transparent portraits using alternate TMDB profile images.

This runs after create_people_poster.ps1. It scans the local transparent style
tree for edge contact, then tries TMDB profile alternates one at a time through
the normal remove-bg and poster-generation pipeline. If no candidate passes the
configured retry edges, the original local style outputs are restored and the
person is reported as unresolved.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageOps

from edge_chop import detect_edge_chops, has_any_issue, issue_summary, parse_edges


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
PEOPLE_ROOT = CONFIG_DIR / "people_dirs"
DOWNLOADS_DIR = PEOPLE_ROOT / "Downloads"
TRANSPARENT_ROOT = PEOPLE_ROOT / "transparent"
ORIGINAL_ROOT = PEOPLE_ROOT / "original"
OUT_ROOT = CONFIG_DIR / "edge_chop_recovery"
REMBG_HOME = CONFIG_DIR / "models" / "rembg"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
TARGET_SIZE = (2000, 3000)
STYLE_EXTS = {
    "bw": ".jpg",
    "diiivoy": ".jpg",
    "diiivoycolor": ".jpg",
    "original": ".jpg",
    "rainier": ".jpg",
    "signature": ".jpg",
    "transparent": ".png",
}


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


def iter_transparents(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*.png")):
        if path.is_file() and path.parent.name.lower() == "images":
            yield path


def find_chopped(
    root: Path,
    threshold: float,
    report_edges: tuple[str, ...],
    retry_edges: tuple[str, ...],
    modified_since: float | None = None,
    max_matches: int = 0,
) -> list[tuple[str, Path, str]]:
    chopped: list[tuple[str, Path, str]] = []
    for path in iter_transparents(root):
        if modified_since is not None:
            try:
                if path.stat().st_mtime < modified_since:
                    continue
            except OSError:
                continue
        result = detect_edge_chops(path, threshold=threshold, edges=report_edges)
        if result.error:
            chopped.append((path.stem, path, issue_summary(result)))
            continue
        if has_any_issue(result, retry_edges):
            chopped.append((path.stem, path, issue_summary(result)))
            if max_matches > 0 and len(chopped) >= max_matches:
                break
    return chopped


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

    result = detect_edge_chops(precheck_png, threshold=args.threshold, edges=args.report_edges)
    summary = issue_summary(result) or result.error
    if result.error:
        raise RuntimeError(f"rembg precheck could not audit {precheck_png}: {summary}")
    if has_any_issue(result, args.retry_edges):
        return False, summary
    return True, summary


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


def final_transparent_path(people_root: Path, name: str) -> Path:
    return people_root / "transparent" / (name[:1] or "_").upper() / "Images" / f"{name}.png"


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
                    log(f"[precheck] {name} {candidate.label}: rembg still has edge issue: {precheck_summary}")
                    continue
                if precheck_summary:
                    log(f"[precheck] {name} {candidate.label}: rembg cleared retry edges; {precheck_summary}")

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
            result = detect_edge_chops(transparent, threshold=args.threshold, edges=args.report_edges)
            summary = issue_summary(result)
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

            if not has_any_issue(result, args.retry_edges) and not result.error:
                row.status = "recovered"
                row.chosen_label = candidate.label
                row.chosen_url = candidate.url
                row.final_issues = summary
                row.note = "accepted TMDB alternate"
                if row.grayscale_colorized:
                    row.note += f"; DeOldify colorized {row.grayscale_colorized} candidates"
                if row.grayscale_rejected:
                    row.note += f"; non-color checks rejected {row.grayscale_rejected} candidates"
                if row.precheck_rejected:
                    row.note += f"; rembg precheck rejected {row.precheck_rejected} earlier candidates"
                return row

            log(f"[retry] {name} {candidate.label} still has edge issue: {summary or result.error}")

        restore_backups(backups, paths)
        current = final_transparent_path(args.people_root, name)
        row.final_issues = issue_summary(detect_edge_chops(current, threshold=args.threshold, edges=args.report_edges)) if current.exists() else ""
        row.note = "no TMDB alternate cleared retry edges; restored previous local outputs"
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--people-root", type=Path, default=Path(os.getenv("EDGE_CHOP_PEOPLE_ROOT") or PEOPLE_ROOT))
    ap.add_argument("--transparent-root", type=Path, default=Path(os.getenv("EDGE_CHOP_TRANSPARENT_ROOT") or TRANSPARENT_ROOT))
    ap.add_argument("--downloads-dir", type=Path, default=Path(os.getenv("EDGE_CHOP_DOWNLOADS_DIR") or DOWNLOADS_DIR))
    ap.add_argument("--out-root", type=Path, default=Path(os.getenv("EDGE_CHOP_OUT_ROOT") or OUT_ROOT))
    ap.add_argument("--threshold", type=float, default=float(os.getenv("EDGE_CHOP_THRESHOLD", "0.06")))
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
    ap.add_argument("--limit", type=int, default=0, help="Maximum chopped people to attempt; 0 means all")
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--modified-since", type=float, help="Only retry transparent PNGs modified at/after this Unix timestamp")
    ap.add_argument("--modified-within-hours", type=float, default=0.0, help="Only retry transparent PNGs modified within this many hours")
    ap.add_argument("--all", action="store_true", help="Allow whole-tree recovery attempts")
    ap.add_argument("--audit-only", action="store_true", help="Scan and report matching edge chops without retrying")
    return ap


def main() -> int:
    args = parser().parse_args()
    args.people_root = args.people_root.resolve()
    args.transparent_root = args.transparent_root.resolve()
    args.downloads_dir = args.downloads_dir.resolve()
    args.out_root = args.out_root.resolve()
    args.rembg_home = args.rembg_home.resolve()
    args.report_edges = parse_edges(args.report_edges, ("top",))
    args.retry_edges = parse_edges(args.retry_edges, ("top",))
    args.rembg_session = None

    log("#### START recover_edge_chops ####")
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

    scan_limit = 0 if args.names else args.limit
    chopped = find_chopped(
        args.transparent_root,
        args.threshold,
        args.report_edges,
        args.retry_edges,
        modified_since=modified_since,
        max_matches=scan_limit,
    )
    if args.names:
        wanted = {name.casefold() for name in args.names}
        chopped = [item for item in chopped if item[0].casefold() in wanted]

    log(f"Chopped transparent images needing retry: {len(chopped)}")
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
    session = requests.Session()
    exit_code = 0
    for idx, (name, path, issues) in enumerate(chopped, start=1):
        log(f"[{idx}/{len(chopped)}] {name}: {issues}")
        try:
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
    recovered = sum(1 for row in rows if row.status == "recovered")
    unresolved = sum(1 for row in rows if row.status == "unresolved")
    log(f"Recovered: {recovered}")
    log(f"Unresolved: {unresolved}")
    log("#### END recover_edge_chops ####")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
