#!/usr/bin/env python3
"""Download alternate TMDB profile images for selected people and review them."""

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
DEFAULT_OUT_ROOT = CONFIG_DIR / "review_original_candidates" / "tmdb_alternates"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
DEFAULT_NAMES = [
    "Andrew Garfield",
    "Daniel Radcliffe",
    "Elizabeth Olsen",
    "Emily Blunt",
    "Emma Watson",
    "Sydney Sweeney",
    "Zendaya",
    "Zoe Saldaña",
]


def safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()


def iter_style_images(style_dir: Path) -> Iterable[Path]:
    for path in sorted(style_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            if path.parent.name.lower() == "images":
                yield path


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


def draw_text(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], font: ImageFont.ImageFont) -> None:
    draw.text(xy, text, fill=(20, 20, 20), font=font)


def search_person(session: requests.Session, api_key: str, name: str) -> dict:
    response = session.get(
        TMDB_SEARCH_URL,
        params={"api_key": api_key, "query": name, "include_adult": "false", "language": "en-US", "page": "1"},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise RuntimeError(f"No TMDB search results for {name}")
    exact = [item for item in results if str(item.get("name", "")).casefold() == name.casefold()]
    return (exact or results)[0]


def get_profiles(session: requests.Session, api_key: str, person_id: int) -> list[dict]:
    response = session.get(
        f"https://api.themoviedb.org/3/person/{person_id}/images",
        params={"api_key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    profiles = response.json().get("profiles", [])
    return sorted(
        profiles,
        key=lambda item: (
            float(item.get("vote_average") or 0),
            int(item.get("vote_count") or 0),
            int(item.get("width") or 0) * int(item.get("height") or 0),
        ),
        reverse=True,
    )


def download_image(session: requests.Session, file_path: str, out_path: Path) -> None:
    response = session.get(f"{TMDB_IMAGE_BASE}{file_path}", timeout=60)
    response.raise_for_status()
    out_path.write_bytes(response.content)


def make_person_sheet(
    name: str,
    style_paths: dict[str, Path],
    candidate_paths: list[Path],
    out_path: Path,
    styles: list[str],
) -> None:
    cell_w = 230
    img_h = 345
    label_h = 52
    gutter = 16
    columns = 4
    references = [("transparent", style_paths.get("transparent")), ("rainier", style_paths.get("rainier"))]
    items: list[tuple[str, Path | None, bool]] = [
        (label, path, bool(path and path.suffix.lower() == ".png")) for label, path in references if label in styles
    ]
    items.extend((f"candidate {idx:02d}", path, False) for idx, path in enumerate(candidate_paths, start=1))

    title_font = load_font(22)
    small_font = load_font(13)
    rows = (len(items) + columns - 1) // columns
    width = gutter + columns * (cell_w + gutter)
    height = gutter + 32 + rows * (label_h + img_h + gutter)
    sheet = Image.new("RGB", (width, height), (244, 244, 244))
    draw = ImageDraw.Draw(sheet)
    draw_text(draw, name, (gutter, gutter), title_font)

    y0 = gutter + 32
    for idx, (label, path, checker) in enumerate(items):
        row = idx // columns
        col = idx % columns
        x = gutter + col * (cell_w + gutter)
        y = y0 + row * (label_h + img_h + gutter)
        draw_text(draw, label, (x, y), small_font)
        top = y + label_h
        if path and path.exists():
            try:
                panel = fit_image(path, (cell_w, img_h), checker=checker)
            except Exception:
                panel = Image.new("RGB", (cell_w, img_h), (255, 235, 235))
        else:
            panel = Image.new("RGB", (cell_w, img_h), (238, 238, 238))
            ImageDraw.Draw(panel).text((16, 16), "missing", fill=(120, 0, 0), font=small_font)
        sheet.paste(panel, (x, top))
        draw.rectangle((x, top, x + cell_w - 1, top + img_h - 1), outline=(185, 185, 185))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-root", type=Path, default=DEFAULT_IMPORT_ROOT)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--names", nargs="*", default=DEFAULT_NAMES)
    parser.add_argument("--daniel-only", action="store_true", help="Convenience mode for shell-safe Daniel Radcliffe reruns.")
    parser.add_argument("--styles", default="transparent,rainier")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    if args.daniel_only:
        args.names = ["Daniel Radcliffe"]

    api_key = os.getenv("TMDB_KEY", "").strip()
    if not api_key:
        print("[ERROR] TMDB_KEY missing from environment or create_people_posters/config/.env", file=sys.stderr)
        return 2

    styles = [style.strip() for style in args.styles.split(",") if style.strip()]
    style_paths_by_name: dict[str, dict[str, Path]] = {name: {} for name in args.names}
    for style in styles:
        for path in iter_style_images(args.import_root / style):
            if path.stem in style_paths_by_name:
                style_paths_by_name[path.stem][style] = path

    args.out_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_root / "manifest.csv"
    rows: list[dict[str, str]] = []
    session = requests.Session()

    for person_index, name in enumerate(args.names, start=1):
        print(f"[{person_index:02d}/{len(args.names):02d}] {name}")
        person = search_person(session, api_key, name)
        person_id = int(person["id"])
        profiles = get_profiles(session, api_key, person_id)[: args.limit]
        person_dir = args.out_root / "candidates" / safe_name(name)
        person_dir.mkdir(parents=True, exist_ok=True)
        candidate_paths: list[Path] = []
        for profile_index, profile in enumerate(profiles, start=1):
            file_path = profile["file_path"]
            out_path = person_dir / f"{profile_index:02d}{Path(file_path).suffix or '.jpg'}"
            download_image(session, file_path, out_path)
            candidate_paths.append(out_path)
            rows.append(
                {
                    "name": name,
                    "tmdb_id": str(person_id),
                    "tmdb_name": str(person.get("name", "")),
                    "candidate": f"{profile_index:02d}",
                    "file_path": str(file_path),
                    "width": str(profile.get("width", "")),
                    "height": str(profile.get("height", "")),
                    "vote_average": str(profile.get("vote_average", "")),
                    "vote_count": str(profile.get("vote_count", "")),
                }
            )
        make_person_sheet(
            name,
            style_paths_by_name.get(name, {}),
            candidate_paths,
            args.out_root / "sheets" / f"{safe_name(name)}.jpg",
            styles,
        )

    with manifest_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "name",
                "tmdb_id",
                "tmdb_name",
                "candidate",
                "file_path",
                "width",
                "height",
                "vote_average",
                "vote_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"People: {len(args.names)}")
    print(f"Candidates per person: up to {args.limit}")
    print(f"Manifest: {manifest_path}")
    print(f"Review sheets: {args.out_root / 'sheets'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
