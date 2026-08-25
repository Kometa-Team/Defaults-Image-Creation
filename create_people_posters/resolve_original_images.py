#!/usr/bin/env python3
"""Resolve original 2000x3000 portraits from existing transparent/rainier outputs.

The resolver compares local styled outputs against TMDB profile images first. If
no candidate scores above the match threshold, it can fall back to Google Custom
Search image results when GOOGLE_API_KEY and GOOGLE_CSE_ID are configured.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
DEFAULT_SOURCE_ROOT = CONFIG_DIR / "people_dirs"
DEFAULT_OUT_ROOT = CONFIG_DIR / "original_resolver"
DEFAULT_ORIGINAL_ROOT = CONFIG_DIR / "people_dirs" / "original"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
GOOGLE_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
TARGET_ORIGINAL_SIZE = (2000, 3000)
FEATURE_SIZE = (96, 144)


@dataclass(frozen=True)
class Candidate:
    provider: str
    label: str
    url: str
    path: Path
    metadata: dict[str, str]


@dataclass(frozen=True)
class MatchResult:
    name: str
    status: str
    provider: str = ""
    label: str = ""
    score: float = 0.0
    url: str = ""
    candidate_path: str = ""
    copied_to: str = ""
    note: str = ""


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()


def parse_styles(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def iter_style_images(style_dir: Path) -> Iterable[Path]:
    if not style_dir.exists():
        return
    for path in sorted(style_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"} and path.parent.name.lower() == "images":
            yield path


def image_paths_by_stem(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path in iter_style_images(root):
        paths[path.stem] = path
    return paths


def collect_reference_paths(source_root: Path, styles: list[str]) -> dict[str, dict[str, Path]]:
    refs: dict[str, dict[str, Path]] = {}
    for style in styles:
        for path in iter_style_images(source_root / style):
            refs.setdefault(path.stem, {})[style] = path
    return refs


def read_names(args: argparse.Namespace, refs: dict[str, dict[str, Path]]) -> list[str]:
    names: set[str] = set(args.names or [])
    if args.names_file:
        with args.names_file.open("r", encoding="utf-8") as fh:
            names.update(line.strip() for line in fh if line.strip() and not line.lstrip().startswith("#"))

    if not names:
        names.update(refs)

    if args.only_missing_originals:
        originals = set(image_paths_by_stem(args.original_root))
        names = {name for name in names if name not in originals}

    ordered = sorted(name for name in names if name in refs)
    if args.limit > 0:
        ordered = ordered[: args.limit]
    return ordered


def centered_rgba(path: Path, crop_alpha: bool) -> Image.Image:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        rgba = img.convert("RGBA")
        if crop_alpha and "A" in rgba.getbands():
            bbox = rgba.getchannel("A").getbbox()
            if bbox:
                left, top, right, bottom = bbox
                pad_x = max((right - left) // 20, 4)
                pad_y = max((bottom - top) // 20, 4)
                left = max(left - pad_x, 0)
                top = max(top - pad_y, 0)
                right = min(right + pad_x, rgba.width)
                bottom = min(bottom + pad_y, rgba.height)
                rgba = rgba.crop((left, top, right, bottom))

        canvas = Image.new("RGBA", TARGET_ORIGINAL_SIZE, (0, 0, 0, 0))
        fitted = ImageOps.contain(rgba, TARGET_ORIGINAL_SIZE, method=Image.Resampling.LANCZOS)
        x = (TARGET_ORIGINAL_SIZE[0] - fitted.width) // 2
        y = (TARGET_ORIGINAL_SIZE[1] - fitted.height) // 2
        canvas.alpha_composite(fitted, (x, y))
        return canvas


def feature_image(path: Path, crop_alpha: bool) -> Image.Image:
    rgba = centered_rgba(path, crop_alpha=crop_alpha)
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    white.alpha_composite(rgba)
    return ImageOps.fit(white.convert("RGB"), FEATURE_SIZE, method=Image.Resampling.LANCZOS).convert("L")


def average_hash(img: Image.Image, size: int = 32) -> tuple[int, ...]:
    small = img.resize((size, size), Image.Resampling.LANCZOS)
    pixels = list(image_pixels(small))
    avg = sum(pixels) / len(pixels)
    return tuple(1 if pixel >= avg else 0 for pixel in pixels)


def difference_hash(img: Image.Image, width: int = 17, height: int = 16) -> tuple[int, ...]:
    small = img.resize((width, height), Image.Resampling.LANCZOS)
    pixels = list(image_pixels(small))
    bits: list[int] = []
    for y in range(height):
        offset = y * width
        for x in range(width - 1):
            bits.append(1 if pixels[offset + x] > pixels[offset + x + 1] else 0)
    return tuple(bits)


def image_pixels(img: Image.Image):
    get_flattened_data = getattr(img, "get_flattened_data", None)
    if get_flattened_data:
        return get_flattened_data()
    return img.getdata()


def histogram(img: Image.Image) -> list[float]:
    hist = img.histogram()
    total = float(sum(hist)) or 1.0
    return [value / total for value in hist]


def hamming_similarity(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    same = sum(1 for a, b in zip(left, right) if a == b)
    return same / len(left)


def histogram_similarity(left: list[float], right: list[float]) -> float:
    return sum(min(a, b) for a, b in zip(left, right))


def features(path: Path, crop_alpha: bool) -> tuple[tuple[int, ...], tuple[int, ...], list[float]]:
    img = feature_image(path, crop_alpha=crop_alpha)
    return average_hash(img), difference_hash(img), histogram(img)


def score_features(
    candidate_features: tuple[tuple[int, ...], tuple[int, ...], list[float]],
    reference_features: tuple[tuple[int, ...], tuple[int, ...], list[float]],
) -> float:
    avg_hash, diff_hash, hist = candidate_features
    ref_avg_hash, ref_diff_hash, ref_hist = reference_features
    return (
        hamming_similarity(avg_hash, ref_avg_hash) * 0.45
        + hamming_similarity(diff_hash, ref_diff_hash) * 0.35
        + histogram_similarity(hist, ref_hist) * 0.20
    )


def reference_features(paths: dict[str, Path]) -> dict[str, tuple[tuple[int, ...], tuple[int, ...], list[float]]]:
    refs: dict[str, tuple[tuple[int, ...], tuple[int, ...], list[float]]] = {}
    for style, path in paths.items():
        try:
            refs[style] = features(path, crop_alpha=(path.suffix.lower() == ".png"))
        except (OSError, UnidentifiedImageError) as exc:
            logging_note = f"Skipping unreadable reference {style}: {path} ({exc})"
            print(logging_note, file=sys.stderr)
    return refs


def candidate_score(candidate_path: Path, refs: dict[str, tuple[tuple[int, ...], tuple[int, ...], list[float]]]) -> float:
    cand = features(candidate_path, crop_alpha=False)
    scores = [score_features(cand, ref) for ref in refs.values()]
    return max(scores) if scores else 0.0


def extension_from_response(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"


def download_url(session: requests.Session, url: str, out_path: Path) -> bool:
    response = session.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code >= 400:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(response.content)
    try:
        with Image.open(out_path) as img:
            img.verify()
    except Exception:
        out_path.unlink(missing_ok=True)
        return False
    return True


def tmdb_person(session: requests.Session, api_key: str, name: str) -> dict | None:
    response = session.get(
        TMDB_SEARCH_URL,
        params={"api_key": api_key, "query": name, "include_adult": "false", "language": "en-US", "page": "1"},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    exact = [item for item in results if str(item.get("name", "")).casefold() == name.casefold()]
    picked = next((item for item in (exact or results) if item.get("id")), None)
    return picked


def tmdb_candidates(session: requests.Session, api_key: str, name: str, out_dir: Path, limit: int) -> list[Candidate]:
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

    candidates: list[Candidate] = []
    for index, profile in enumerate(profiles[:limit], start=1):
        file_path = str(profile.get("file_path") or "")
        if not file_path:
            continue
        url = f"{TMDB_IMAGE_BASE}{file_path}"
        suffix = Path(file_path).suffix or ".jpg"
        out_path = out_dir / "tmdb" / f"{index:03d}{suffix}"
        if download_url(session, url, out_path):
            candidates.append(
                Candidate(
                    provider="tmdb",
                    label=f"{index:03d}",
                    url=url,
                    path=out_path,
                    metadata={
                        "tmdb_id": str(person_id),
                        "tmdb_name": str(person.get("name", "")),
                        "width": str(profile.get("width", "")),
                        "height": str(profile.get("height", "")),
                        "vote_average": str(profile.get("vote_average", "")),
                        "vote_count": str(profile.get("vote_count", "")),
                    },
                )
            )
    return candidates


def google_image_urls(session: requests.Session, api_key: str, cse_id: str, query: str, limit: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    start = 1
    while len(urls) < limit and start <= 91:
        num = min(10, limit - len(urls))
        response = session.get(
            GOOGLE_SEARCH_URL,
            params={"key": api_key, "cx": cse_id, "q": query, "searchType": "image", "num": num, "start": start, "safe": "active"},
            timeout=30,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            break
        for item in items:
            url = str(item.get("link") or "")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        start += len(items)
    return urls


def google_candidates(
    session: requests.Session,
    api_key: str,
    cse_id: str,
    name: str,
    out_dir: Path,
    limit: int,
) -> list[Candidate]:
    query = f'"{name}" headshot portrait'
    urls = google_image_urls(session, api_key, cse_id, query, limit)
    candidates: list[Candidate] = []
    for index, url in enumerate(urls, start=1):
        try:
            head = session.head(url, timeout=15, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            content_type = head.headers.get("content-type", "")
        except Exception:
            content_type = ""
        suffix = extension_from_response(url, content_type)
        out_path = out_dir / "google" / f"{index:03d}{suffix}"
        if download_url(session, url, out_path):
            candidates.append(Candidate(provider="google", label=f"{index:03d}", url=url, path=out_path, metadata={"query": query}))
    return candidates


def save_original(candidate_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(candidate_path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        normalized = ImageOps.fit(img, TARGET_ORIGINAL_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        normalized.save(target_path, "JPEG", quality=95, subsampling=0, optimize=True)


def make_sheet(name: str, refs: dict[str, Path], scored: list[tuple[Candidate, float]], out_path: Path) -> None:
    cell_w = 230
    img_h = 345
    label_h = 54
    gutter = 16
    columns = 4
    items: list[tuple[str, Path, bool]] = [(f"ref {style}", path, path.suffix.lower() == ".png") for style, path in refs.items()]
    items.extend((f"{candidate.provider} {candidate.label} {score:.3f}", candidate.path, False) for candidate, score in scored[:18])
    rows = max(1, (len(items) + columns - 1) // columns)
    sheet = Image.new("RGB", (gutter + columns * (cell_w + gutter), gutter + 32 + rows * (label_h + img_h + gutter)), (244, 244, 244))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(22)
    small_font = load_font(13)
    draw.text((gutter, gutter), name, fill=(20, 20, 20), font=title_font)
    for idx, (label, path, checker) in enumerate(items):
        row, col = divmod(idx, columns)
        x = gutter + col * (cell_w + gutter)
        y = gutter + 32 + row * (label_h + img_h + gutter)
        draw.text((x, y), label, fill=(45, 45, 45), font=small_font)
        panel = Image.new("RGB", (cell_w, img_h), "white")
        if checker:
            panel_draw = ImageDraw.Draw(panel)
            tile = 24
            for yy in range(0, img_h, tile):
                for xx in range(0, cell_w, tile):
                    fill = (226, 226, 226) if (xx // tile + yy // tile) % 2 else (250, 250, 250)
                    panel_draw.rectangle((xx, yy, xx + tile, yy + tile), fill=fill)
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img).convert("RGBA")
                img.thumbnail((cell_w, img_h), Image.Resampling.LANCZOS)
                panel.paste(img, ((cell_w - img.width) // 2, (img_h - img.height) // 2), img)
        except Exception:
            ImageDraw.Draw(panel).text((12, 12), "unreadable", fill=(120, 0, 0), font=small_font)
        top = y + label_h
        sheet.paste(panel, (x, top))
        draw.rectangle((x, top, x + cell_w - 1, top + img_h - 1), outline=(185, 185, 185))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def best_match(candidates: list[Candidate], refs: dict[str, tuple[tuple[int, ...], tuple[int, ...], list[float]]]) -> tuple[Candidate | None, float, list[tuple[Candidate, float]]]:
    scored: list[tuple[Candidate, float]] = []
    for candidate in candidates:
        try:
            scored.append((candidate, candidate_score(candidate.path, refs)))
        except Exception as exc:
            print(f"Skipping unreadable candidate {candidate.path}: {exc}", file=sys.stderr)
    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return None, 0.0, []
    return scored[0][0], scored[0][1], scored


def resolve_name(args: argparse.Namespace, session: requests.Session, name: str, ref_paths: dict[str, Path]) -> MatchResult:
    refs = reference_features(ref_paths)
    if not refs:
        return MatchResult(name=name, status="unresolved", note="no readable reference images")

    person_out = args.out_root / safe_name(name)
    all_scored: list[tuple[Candidate, float]] = []

    tmdb_key = os.getenv("TMDB_KEY", "").strip()
    if tmdb_key:
        candidates = tmdb_candidates(session, tmdb_key, name, person_out, args.tmdb_limit)
        candidate, score, scored = best_match(candidates, refs)
        all_scored.extend(scored)
        if candidate and score >= args.threshold:
            return finish_match(args, name, candidate, score, ref_paths, all_scored)
    else:
        print("TMDB_KEY is not configured; skipping TMDB lookup", file=sys.stderr)

    google_key = os.getenv("GOOGLE_API_KEY", os.getenv("GOOGLE_SEARCH_KEY", "")).strip()
    google_cse = os.getenv("GOOGLE_CSE_ID", os.getenv("GOOGLE_SEARCH_CX", "")).strip()
    if not args.no_google and google_key and google_cse:
        candidates = google_candidates(session, google_key, google_cse, name, person_out, args.google_limit)
        candidate, score, scored = best_match(candidates, refs)
        all_scored.extend(scored)
        all_scored.sort(key=lambda item: item[1], reverse=True)
        if candidate and score >= args.threshold:
            return finish_match(args, name, candidate, score, ref_paths, all_scored)
        note = "no TMDB or Google candidate reached threshold"
    elif args.no_google:
        note = "no TMDB candidate reached threshold; Google disabled"
    else:
        note = "no TMDB candidate reached threshold; Google Custom Search not configured"

    make_sheet(name, ref_paths, all_scored, person_out / "review.jpg")
    return MatchResult(
        name=name,
        status="unresolved",
        score=all_scored[0][1] if all_scored else 0.0,
        provider=all_scored[0][0].provider if all_scored else "",
        label=all_scored[0][0].label if all_scored else "",
        url=all_scored[0][0].url if all_scored else "",
        candidate_path=str(all_scored[0][0].path) if all_scored else "",
        note=note,
    )


def finish_match(
    args: argparse.Namespace,
    name: str,
    candidate: Candidate,
    score: float,
    ref_paths: dict[str, Path],
    scored: list[tuple[Candidate, float]],
) -> MatchResult:
    make_sheet(name, ref_paths, scored, args.out_root / safe_name(name) / "review.jpg")
    target_path = args.original_root / name[:1].upper() / "Images" / f"{name}.jpg"
    copied_to = ""
    if args.apply:
        if target_path.exists() and not args.force:
            return MatchResult(
                name=name,
                status="matched_not_copied",
                provider=candidate.provider,
                label=candidate.label,
                score=score,
                url=candidate.url,
                candidate_path=str(candidate.path),
                copied_to=str(target_path),
                note="target exists; pass --force to overwrite",
            )
        save_original(candidate.path, target_path)
        copied_to = str(target_path)
    return MatchResult(
        name=name,
        status="matched",
        provider=candidate.provider,
        label=candidate.label,
        score=score,
        url=candidate.url,
        candidate_path=str(candidate.path),
        copied_to=copied_to,
        note="" if args.apply else "dry run; pass --apply to copy into original",
    )


def write_results(out_root: Path, rows: list[MatchResult]) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    manifest = out_root / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["name", "status", "provider", "label", "score", "url", "candidate_path", "copied_to", "note"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "name": row.name,
                    "status": row.status,
                    "provider": row.provider,
                    "label": row.label,
                    "score": f"{row.score:.4f}" if row.score else "",
                    "url": row.url,
                    "candidate_path": row.candidate_path,
                    "copied_to": row.copied_to,
                    "note": row.note,
                }
            )

    unresolved = [row for row in rows if row.status.startswith("unresolved")]
    with (out_root / "unresolved.txt").open("w", encoding="utf-8") as fh:
        for row in unresolved:
            fh.write(f"{row.name}\t{row.note}\tbest={row.score:.4f}\n")


def parser() -> argparse.ArgumentParser:
    load_dotenv(CONFIG_DIR / ".env")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, default=Path(os.getenv("PEOPLE_IMPORT_DIR") or DEFAULT_SOURCE_ROOT))
    ap.add_argument("--styles", default=os.getenv("ORIGINAL_RESOLVER_STYLES", "transparent,rainier"))
    ap.add_argument("--original-root", type=Path, default=Path(os.getenv("ORIGINAL_RESOLVER_ORIGINAL_ROOT") or DEFAULT_ORIGINAL_ROOT))
    ap.add_argument("--out-root", type=Path, default=Path(os.getenv("ORIGINAL_RESOLVER_OUT_ROOT") or DEFAULT_OUT_ROOT))
    ap.add_argument("--names", nargs="*", default=[])
    ap.add_argument("--names-file", type=Path)
    ap.add_argument("--only-missing-originals", action="store_true", default=True)
    ap.add_argument("--all", action="store_true", help="Process all names with references, not only names missing originals.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threshold", type=float, default=float(os.getenv("ORIGINAL_RESOLVER_THRESHOLD", "0.82")))
    ap.add_argument("--tmdb-limit", type=int, default=int(os.getenv("ORIGINAL_RESOLVER_TMDB_LIMIT", "50")))
    ap.add_argument("--google-limit", type=int, default=int(os.getenv("ORIGINAL_RESOLVER_GOOGLE_LIMIT", "30")))
    ap.add_argument("--no-google", action="store_true")
    ap.add_argument("--apply", action="store_true", help="Copy matched candidates into config/people_dirs/original.")
    ap.add_argument("--force", action="store_true", help="Allow --apply to overwrite an existing original.")
    return ap


def main() -> int:
    args = parser().parse_args()
    if args.all:
        args.only_missing_originals = False

    styles = parse_styles(args.styles)
    refs = collect_reference_paths(args.source_root, styles)
    names = read_names(args, refs)
    if not names:
        print("No names to resolve.")
        return 0

    results: list[MatchResult] = []
    session = requests.Session()
    for index, name in enumerate(names, start=1):
        print(f"[{index:03d}/{len(names):03d}] {name}")
        try:
            result = resolve_name(args, session, name, refs[name])
        except Exception as exc:
            result = MatchResult(name=name, status="unresolved", note=f"error: {exc}")
        print(f"  {result.status} {result.provider} {result.label} score={result.score:.4f} {result.note}".rstrip())
        results.append(result)

    write_results(args.out_root, results)
    matched = sum(1 for row in results if row.status.startswith("matched"))
    unresolved = sum(1 for row in results if row.status.startswith("unresolved"))
    print(f"Matched: {matched}")
    print(f"Unresolved: {unresolved}")
    print(f"Manifest: {args.out_root / 'manifest.csv'}")
    if unresolved:
        print(f"Unresolved report: {args.out_root / 'unresolved.txt'}")
    return 0 if unresolved == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
