#!/usr/bin/env python3
"""Stage TMDB original candidates and build visual review sheets.

This intentionally does not copy anything into config/people_dirs/original.
It downloads candidate TMDB profile images based on names from an imported
style folder, then creates contact sheets so the source portrait can be
compared against supplied styled outputs before syncing.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
load_dotenv(CONFIG_DIR / ".env")
DEFAULT_IMPORT_ROOT = Path(os.getenv("PEOPLE_IMPORT_DIR") or (CONFIG_DIR / "people_dirs"))
DEFAULT_OUT_ROOT = CONFIG_DIR / "review_original_candidates"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"


def iter_style_images(style_dir: Path) -> Iterable[Path]:
    for path in sorted(style_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            if path.parent.name.lower() == "images":
                yield path


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()


def load_font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def fit_image(path: Path, box: tuple[int, int], checker: bool = False) -> Image.Image:
    width, height = box
    canvas = Image.new("RGB", box, "white")
    if checker:
        draw = ImageDraw.Draw(canvas)
        tile = 24
        for y in range(0, height, tile):
            for x in range(0, width, tile):
                fill = (226, 226, 226) if (x // tile + y // tile) % 2 else (250, 250, 250)
                draw.rectangle((x, y, x + tile, y + tile), fill=fill)

    with Image.open(path) as im:
        im = im.convert("RGBA")
        im.thumbnail(box, Image.Resampling.LANCZOS)
        x = (width - im.width) // 2
        y = (height - im.height) // 2
        canvas.paste(im, (x, y), im)
    return canvas


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font: ImageFont.ImageFont, max_width: int) -> None:
    x, y = xy
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    for line in lines[:3]:
        draw.text((x, y), line, fill=(20, 20, 20), font=font)
        y += 18


def download_candidate(session: requests.Session, api_key: str, name: str, out_path: Path) -> dict[str, str]:
    params = {"api_key": api_key, "query": name, "include_adult": "false", "language": "en-US", "page": "1"}
    response = session.get(TMDB_SEARCH_URL, params=params, timeout=30)
    response.raise_for_status()
    results = response.json().get("results", [])
    picked = next((item for item in results if item.get("profile_path")), None)
    if not picked:
        return {"status": "no_profile", "tmdb_id": "", "tmdb_name": "", "profile_path": ""}

    image_url = f"{TMDB_IMAGE_BASE}{picked['profile_path']}"
    image_response = session.get(image_url, timeout=60)
    image_response.raise_for_status()
    out_path.write_bytes(image_response.content)
    return {
        "status": "downloaded",
        "tmdb_id": str(picked.get("id", "")),
        "tmdb_name": str(picked.get("name", "")),
        "profile_path": str(picked.get("profile_path", "")),
    }


def make_contact_sheets(
    names: list[str],
    candidates_dir: Path,
    style_paths_by_name: dict[str, dict[str, Path]],
    out_dir: Path,
    styles: list[str],
) -> None:
    sheet_dir = out_dir / "sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)

    cell_w = 260
    image_h = 390
    label_h = 74
    gutter = 18
    row_h = label_h + image_h + gutter
    columns = ["tmdb_original", *styles]
    sheet_w = gutter + len(columns) * (cell_w + gutter)
    rows_per_sheet = 6
    title_font = load_font(18)
    small_font = load_font(13)

    for sheet_index, start in enumerate(range(0, len(names), rows_per_sheet), start=1):
        subset = names[start : start + rows_per_sheet]
        sheet_h = gutter + len(subset) * row_h
        sheet = Image.new("RGB", (sheet_w, sheet_h), (244, 244, 244))
        draw = ImageDraw.Draw(sheet)

        for row_index, name in enumerate(subset):
            y = gutter + row_index * row_h
            draw_wrapped(draw, name, (gutter, y), title_font, cell_w)
            for col_index, column in enumerate(columns):
                x = gutter + col_index * (cell_w + gutter)
                draw.text((x, y + 52), column, fill=(60, 60, 60), font=small_font)
                if column == "tmdb_original":
                    path = candidates_dir / f"{safe_name(name)}.jpg"
                    checker = False
                else:
                    path = style_paths_by_name.get(name, {}).get(column)
                    checker = path is not None and path.suffix.lower() == ".png"

                box_top = y + label_h
                if path and path.exists():
                    try:
                        panel = fit_image(path, (cell_w, image_h), checker=checker)
                    except Exception:
                        panel = Image.new("RGB", (cell_w, image_h), (255, 235, 235))
                else:
                    panel = Image.new("RGB", (cell_w, image_h), (238, 238, 238))
                    panel_draw = ImageDraw.Draw(panel)
                    panel_draw.text((16, 16), "missing", fill=(120, 0, 0), font=small_font)
                sheet.paste(panel, (x, box_top))
                draw.rectangle((x, box_top, x + cell_w - 1, box_top + image_h - 1), outline=(185, 185, 185))

        sheet.save(sheet_dir / f"original_candidate_review_{sheet_index:02d}.jpg", quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-root", type=Path, default=DEFAULT_IMPORT_ROOT)
    parser.add_argument("--name-style", default="transparent", help="Style folder used to derive the name list.")
    parser.add_argument("--compare-styles", default="transparent,rainier", help="Comma-separated style folders shown beside TMDB original.")
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick testing.")
    args = parser.parse_args()

    api_key = os.getenv("TMDB_KEY", "").strip()
    if not api_key:
        print("[ERROR] TMDB_KEY missing from environment or create_people_posters/config/.env", file=sys.stderr)
        return 2

    name_style_dir = args.import_root / args.name_style
    if not name_style_dir.exists():
        print(f"[ERROR] Name source does not exist: {name_style_dir}", file=sys.stderr)
        return 2

    names = sorted({path.stem for path in iter_style_images(name_style_dir)})
    if args.limit > 0:
        names = names[: args.limit]
    if not names:
        print(f"[ERROR] No images found under {name_style_dir}", file=sys.stderr)
        return 2

    out_root = args.out_root
    candidates_dir = out_root / "tmdb_originals"
    out_root.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    styles = [style.strip() for style in args.compare_styles.split(",") if style.strip()]
    style_paths_by_name: dict[str, dict[str, Path]] = {name: {} for name in names}
    for style in styles:
        style_dir = args.import_root / style
        for path in iter_style_images(style_dir):
            if path.stem in style_paths_by_name:
                style_paths_by_name[path.stem][style] = path

    manifest_path = out_root / "manifest.csv"
    session = requests.Session()
    rows: list[dict[str, str]] = []
    for index, name in enumerate(names, start=1):
        out_path = candidates_dir / f"{safe_name(name)}.jpg"
        print(f"[{index:02d}/{len(names):02d}] {name}")
        try:
            info = download_candidate(session, api_key, name, out_path)
        except Exception as exc:
            info = {"status": f"error: {exc}", "tmdb_id": "", "tmdb_name": "", "profile_path": ""}
        rows.append({"name": name, **info})

    with manifest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["name", "status", "tmdb_id", "tmdb_name", "profile_path"])
        writer.writeheader()
        writer.writerows(rows)

    make_contact_sheets(names, candidates_dir, style_paths_by_name, out_root, styles)
    downloaded = sum(1 for row in rows if row["status"] == "downloaded")
    print(f"Names: {len(names)}")
    print(f"Downloaded candidates: {downloaded}")
    print(f"Manifest: {manifest_path}")
    print(f"Review sheets: {out_root / 'sheets'}")
    return 0 if downloaded == len(names) else 1


if __name__ == "__main__":
    raise SystemExit(main())
