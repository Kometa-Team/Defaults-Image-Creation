#!/usr/bin/env python3
"""
auto_readme.py — Generate per-letter README.md files and a top-level README with links and a grid image,
with unified logging and progress output.

Behavior mirrors the original script but adds:
- Console + file logging (./config/logs/auto_readme.log)
- Progress bars using alive_progress
- Safer directory filtering (letters must be subdirectories)
- Font fallback if Arial is missing
- Optional Git repo auto-detection to build raw.githubusercontent.com URLs
- CLI flags for owner/repo/branch overrides
- Dry-run and verbose modes

Typical usage (run from your local style directory or pass --directory):
  python auto_readme.py --style transparent --directory ./transparent
  python auto_readme.py --directory ./bw --verbose
  python auto_readme.py --directory ./original --owner Kometa-Team --repo People-Images --branch master
"""
import argparse
import logging
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from timeit import default_timer as timer
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont

try:
    from dotenv import load_dotenv  # optional
except Exception:
    load_dotenv = None

try:
    from alive_progress import alive_bar  # optional progress
    HAVE_ALIVE = True
except Exception:
    HAVE_ALIVE = False

# ---------- paths + logging ----------
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
CONFIG_DIR = SCRIPT_DIR / "config"
LOGS_DIR = CONFIG_DIR / "logs"
for d in (CONFIG_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)


def setup_logging(level=logging.INFO, console=True):
    log_file = LOGS_DIR / f"{SCRIPT_PATH.stem}.log"
    handlers = [logging.FileHandler(log_file, encoding="utf-8", mode="w")]
    if console:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.info("Logging → %s", log_file)
    return log_file


def load_env_if_present(override: bool = False):
    if load_dotenv is None:
        return
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=override)


FRIENDLY_NAMES = {
    "bw": "Black & White",
    "diiivoy": "DIIIVOY",
    "diiivoycolor": "DIIIVOY Color",
}


def detect_git_repo_info(start_dir: Path) -> dict | None:
    """
    Return {'owner','repo','branch'} if start_dir (or its parent) is a git work tree.
    Owner/repo parsed from 'origin' URL. Branch from HEAD.
    """
    def _git(args, cwd):
        p = subprocess.run(["git", *args], cwd=cwd, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            return None
        return p.stdout.strip()

    for candidate in (start_dir, start_dir.parent):
        out = _git(["rev-parse", "--is-inside-work-tree"], candidate)
        if out != "true":
            continue
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], candidate) or "master"
        remote = _git(["remote", "get-url", "origin"], candidate) or ""
        m = (re.match(r".*[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
             or re.match(r"https?://[^/]+/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote))
        if not m:
            break
        return {"owner": m.group("owner"), "repo": m.group("repo"), "branch": branch}
    return None


def load_font(preferred: str = "arial.ttf", size: int = 12) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(preferred, size=size)
    except Exception:
        # try a common cross-platform font
        for fallback in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(fallback, size=size)
            except Exception:
                continue
        # last resort
        logging.warning("Falling back to default PIL bitmap font (limited glyphs).")
        return ImageFont.load_default()


def compute_columns(n: int) -> int:
    return max(1, int(math.sqrt(max(1, n))))


def make_grid_image(files: list[str], images_folder: Path, out_path: Path,
                    thumb_size=(200, 200), text_color=(255, 255, 255)):
    if not files:
        return
    cols = compute_columns(len(files))
    rows = len(files) // cols + (len(files) % cols > 0)
    grid_w = cols * thumb_size[0]
    grid_h = rows * (thumb_size[1] + 20) + 20
    grid_image = Image.new("RGB", (grid_w, grid_h), (0, 0, 0))
    draw = ImageDraw.Draw(grid_image)
    font = load_font(size=12)

    for i, file in enumerate(files):
        image_path = images_folder / file
        try:
            image = Image.open(image_path)
            image.thumbnail(thumb_size, Image.LANCZOS)
        except Exception as e:
            logging.warning("Failed to open %s: %s", image_path, e)
            continue

        col = i % cols
        row = i // cols
        x = col * thumb_size[0]
        y = row * (thumb_size[1] + 20) + 20
        x_off = (thumb_size[0] - image.size[0]) // 2
        y_off = (thumb_size[1] - image.size[1]) // 2
        filename = Path(file).stem

        # text size + background box
        try:
            bbox = font.getbbox(filename)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = font.getsize(filename)
        text_x = x + (thumb_size[0] - tw - 20) // 2 + 10
        text_y = y + thumb_size[1] + 5
        box_w = thumb_size[0] - 20
        box_h = th

        grid_image.paste(image, (x + x_off, y + y_off))
        draw.rectangle((x + 10, text_y - 2, x + 10 + box_w, text_y + box_h + 2), fill=(0, 0, 0))
        draw.text((text_x, text_y), filename, font=font, fill=text_color)

    # grid lines
    for i in range(cols + 1):
        x = i * thumb_size[0]
        draw.line((x, 0, x, grid_h), fill=(0, 0, 0))
    for i in range(rows + 1):
        y = i * (thumb_size[1] + 20) + 20
        draw.line((0, y, grid_w, y), fill=(0, 0, 0))

    try:
        grid_image.save(out_path)
        logging.info("Saved grid image: %s", out_path)
    except Exception as e:
        logging.error("Failed to save grid image %s: %s", out_path, e)


def main():
    setup_logging()
    load_env_if_present()

    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--name", dest="name", help="Display name", type=str, default="")
    ap.add_argument("-s", "--style", dest="style", help="Style key (bw, diiivoy, diiivoycolor, etc.)", type=str, default="")
    ap.add_argument("-d", "--directory", dest="directory", help="Local directory to scan", type=str, default="")
    ap.add_argument("--owner", help="Override GitHub owner/org", type=str, default="")
    ap.add_argument("--repo", help="Override GitHub repo name", type=str, default="")
    ap.add_argument("--branch", help="Override Git branch", type=str, default="")
    ap.add_argument("--no-grid", dest="grid", action="store_false", help="Disable grid image generation")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Resolve name and directory
    if args.name:
        name = args.name
    elif args.style:
        name = FRIENDLY_NAMES.get(args.style, args.style.capitalize())
    else:
        name = "Original"

    if args.directory:
        directory = args.directory
    elif args.style:
        directory = args.style
    else:
        directory = "original"

    directory = Path(directory).resolve()
    logging.info("Style=%r  Name=%r  Directory=%s", args.style, name, directory)

    repo_title = f"Kometa People Images - {name}{f' ({args.style})' if args.style else ''}"

    # Detect repo info (owner/repo/branch) from git if possible
    info = detect_git_repo_info(directory)
    owner = args.owner or (info["owner"] if info else "Kometa-Team")
    repo = args.repo or (info["repo"] if info else f"People-Images{('-' + args.style) if args.style else ''}")
    branch = args.branch or (info["branch"] if info else "master")
    logging.info("Git raw base: owner=%s repo=%s branch=%s", owner, repo, branch)

    # Collect letters (directories only)
    excludes = {".git", ".github", ".idea", "README.md"}
    if not directory.exists() or not directory.is_dir():
        logging.error("Directory does not exist or is not a directory: %s", directory)
        return 2
    letters = sorted([lt for lt in os.listdir(directory)
                      if lt not in excludes and (directory / lt).is_dir()],
                     key=lambda s: s.lower())

    total_data: list[str] = []
    total = 0
    start = timer()

    if HAVE_ALIVE:
        mgr = alive_bar(len(letters), title="build READMEs", dual_line=True)
    else:
        class _Dummy:
            def __enter__(self): return lambda *a, **k: None
            def __exit__(self, *a): return False
        mgr = _Dummy()

    with mgr as bar:
        for letter in letters:
            letter_folder = directory / letter
            images_folder = letter_folder / "Images"
            if not images_folder.exists():
                logging.warning("Images folder missing: %s", images_folder)
                bar()
                continue

            base_letter_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{letter}/Images/"
            files = sorted(os.listdir(images_folder))
            # filter to image-like files? Keep original behavior (all files)
            data = [f"\n* [{Path(f).stem}]({base_letter_url}{quote(str(f))})" for f in files]

            if files:
                total_data.append(f'\n<details><summary><a href="{letter}">{letter} ({len(files)} Images)</a></summary>')
                total_data.append("\n")
                total_data.extend(data)
                total_data.append("\n</details>")
                total += len(files)

                if args.grid and not args.dry_run:
                    grid_path = letter_folder / "grid.jpg"
                    make_grid_image(files, images_folder, grid_path)

            # Write letter README
            letter_md = [f"# {repo_title} - {letter} ({len(files)} Images)", "\n"]
            if files:
                letter_md.append("![Grid](grid.jpg)\n")
                letter_md.extend(data)
            if not args.dry_run:
                out_md = letter_folder / "README.md"
                out_md.write_text("".join(letter_md), encoding="utf-8")
                logging.debug("Wrote %s", out_md)

            if HAVE_ALIVE:
                bar.text = f"-> {letter}: {len(files)} image(s)"
            bar()

    # Write top-level README
    top_md = [f"# {repo_title} ({total} Images)", "\n"] + total_data
    if not args.dry_run:
        (directory / "README.md").write_text("".join(top_md), encoding="utf-8")
        logging.info("Wrote %s", directory / "README.md")

    elapsed = timer() - start
    logging.info("Done in %.2fs (letters=%d, total images=%d)", elapsed, len(letters), total)
    print(f"Done in {elapsed:.2f}s — letters={len(letters)}, images={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
