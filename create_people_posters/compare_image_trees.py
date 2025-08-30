# compare_image_trees.py
#
# Compares file names (without extensions) across 7 directories (with subfolders).
# Six folders are .jpg; one folder is .png (except explicit .jpg whitelist).
# Only .jpg/.png are considered; all other file types are ignored (not flagged).
# Optional: validate that every .jpg/.png is exactly REQUIRED_WIDTH x REQUIRED_HEIGHT.
# Outputs console summary + presence matrix CSV and, if enabled, a dimension issues CSV,
# all saved under ./config/. All messages are logged to ./config/logs/<script>.log
#
# Usage (examples):
#   py compare_image_trees.py
#   py compare_image_trees.py --repo-root "D:/Kometa-People-Images"
#   py compare_image_trees.py --dirs "/data/PI/bw" "/data/PI/diiivoy" "/data/PI/diiivoycolor" "/data/PI/rainier" "/data/PI/original" "/data/PI/signature" "/data/PI/transparent"
#   py compare_image_trees.py --no-dimensions --case-insensitive
#   py compare_image_trees.py --required-size 2000x3000 --jpg-whitelist grid,poster-grid

import os
import sys
import csv
import argparse
import logging
from pathlib import Path
from timeit import default_timer as timer
from typing import Optional, List, Tuple

from dotenv import load_dotenv
from alive_progress import alive_bar

# ========= PATHS & LOGGING =========
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


setup_logging()

# Also pick up process env if .env missing
load_dotenv(CONFIG_DIR / ".env")

# ========= DEFAULTS =========
DEFAULT_CATEGORIES = [
    "bw",
    "diiivoy",
    "diiivoycolor",
    "rainier",
    "original",
    "signature",
    "transparent",
]


def parse_bool_env(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_required_size(s: Optional[str], default_w: int, default_h: int) -> tuple[int, int]:
    if not s:
        return default_w, default_h
    s = s.lower().replace(" ", "")
    if "x" not in s:
        raise ValueError(f"--required-size must look like 2000x3000, got: {s}")
    w, h = s.split("x", 1)
    return int(w), int(h)


def detect_png_dir_index(dirs) -> Optional[int]:
    """Pick the one whose folder name contains 'transparent' (case-insensitive)."""
    for i, d in enumerate(dirs):
        if "transparent" in Path(d).name.lower():
            return i
    return None


def normalize_case(s: str, case_sensitive: bool) -> str:
    return s if case_sensitive else s.lower()


def normalize_stem(rel_path: Path, case_sensitive: bool) -> str:
    """Return relative path without extension, POSIX style, applying case rule."""
    stem_path = rel_path.with_suffix("")  # strip extension
    as_posix = stem_path.as_posix()
    return normalize_case(as_posix, case_sensitive)


def check_image_dimensions_lazy(CHECK_DIMENSIONS: bool):
    """
    Return a function check(path)->(w,h,err) depending on CHECK_DIMENSIONS.
    - If disabled: returns (None, None, None) quickly without importing Pillow.
    - If enabled: imports Pillow lazily and performs real checks.
    """
    if not CHECK_DIMENSIONS:
        def _noop(_path: Path):
            return None, None, None

        return _noop

    try:
        from PIL import Image  # lazy import only when enabled
    except Exception as e:
        logging.warning("Dimension checking enabled but Pillow is unavailable: %s", e)
        logging.warning("Install with: pip install pillow")

        def _fail(_path: Path):
            return None, None, "Pillow not installed"

        return _fail

    def _check(path: Path):
        try:
            with Image.open(path) as im:
                return im.width, im.height, None
        except Exception as e:
            return None, None, str(e)

    return _check


def iter_image_files(base_dir: Path):
    """Yield jpg/png file Paths under base_dir (recursive)."""
    if not base_dir.exists():
        return
    for p in base_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".jpg", ".png"}:
            yield p


def rel_clean(rel: Path) -> str:
    """Clean relative path for pretty output and logs."""
    return rel.as_posix().lstrip("./\\")


def gather_stems_and_exts(
    base_dir: Path,
    allowed_exts: set[str],
    case_sensitive: bool,
    jpg_whitelist: Optional[set[str]] = None,
    treat_png_folder: bool = False,
    dim_checker=None,
    required_w: int = 2000,
    required_h: int = 3000,
    check_dimensions: bool = True,
    progress=None,
):
    """
    Walk base_dir recursively and collect:
      - stems: set of relative stems (without extension) that pass the rules
      - ext_mismatches: list of jpg/png files present but disallowed by the folder rules
      - whitelist_hits: list of .jpg files accepted due to whitelist in PNG folder
      - dim_issues: list of (rel_path, width, height, error) if enabled and not REQUIRED_WxH
                    or failed to open (error != None)

    Only .jpg/.png are considered; all other extensions are ignored silently.
    """
    stems = set()
    ext_mismatches: List[Tuple[str, str]] = []  # (rel_path, reason)
    whitelist_hits: List[str] = []  # (rel_path)
    dim_issues: List[Tuple[str, Optional[int], Optional[int], Optional[str]]] = []

    if not base_dir.exists():
        logging.warning("Directory does not exist: %s", base_dir)
        return stems, ext_mismatches, whitelist_hits, dim_issues

    wl_cmp = {normalize_case(x, case_sensitive) for x in (jpg_whitelist or set())}

    for p in iter_image_files(base_dir):
        if progress:
            progress.text = f"-> scanning: {base_dir.name}/{p.relative_to(base_dir).as_posix()}"

        rel = p.relative_to(base_dir)
        rel_posix = rel_clean(rel)
        ext_cmp = p.suffix.lower()
        basename_cmp = normalize_case(rel.stem, case_sensitive)

        # --- Dimension check (with whitelist exemption in PNG folder) ---
        if dim_checker is not None and check_dimensions:
            skip_dim = False
            if treat_png_folder and ext_cmp == ".jpg":
                # If this is a whitelist JPG in the PNG folder, skip dimension checking
                if basename_cmp in wl_cmp:
                    skip_dim = True
            if not skip_dim:
                w, h, err = dim_checker(p)
                if err is not None or w != required_w or h != required_h:
                    dim_issues.append((rel_posix, w, h, err))

        # --- Presence/mismatch logic ---
        if ext_cmp in allowed_exts:
            # Allowed here (.jpg for jpg-folders, .png for png-folder)
            stems.add(normalize_stem(rel, case_sensitive))

        elif treat_png_folder and ext_cmp == ".jpg":
            # PNG folder: allow .jpg ONLY if whitelisted
            if basename_cmp in wl_cmp:
                stems.add(normalize_stem(rel, case_sensitive))
                whitelist_hits.append(rel_posix)
            else:
                ext_mismatches.append((rel_posix, "Unexpected .jpg in PNG folder (not whitelisted)"))

        else:
            # Wrong of the two relevant extensions
            reason = "Unexpected .png in JPG folder" if ext_cmp == ".png" else "Unexpected .jpg in PNG folder"
            ext_mismatches.append((rel_posix, reason))

        if progress:
            progress()  # tick

    return stems, ext_mismatches, whitelist_hits, dim_issues


def build_dirs_from_args_env(args: argparse.Namespace) -> list[Path]:
    """
    Priority:
      1) --dirs (7 explicit directories)
      2) --repo-root (+ optional --categories)
      3) PEOPLE_IMAGES_DIR env (+ COMPARE_CATEGORIES env or defaults)
    """
    if args.dirs:
        dirs = [Path(d).expanduser().resolve() for d in args.dirs]
    else:
        repo_root = Path(
            (args.repo_root or os.getenv("PEOPLE_IMAGES_DIR", "./Kometa-People-Images"))
        ).expanduser().resolve()

        cats = args.categories
        if not cats:
            env_cats = os.getenv("COMPARE_CATEGORIES")
            cats = [c.strip() for c in env_cats.split(",")] if env_cats else DEFAULT_CATEGORIES

        dirs = [repo_root / c for c in cats]

    return dirs


def main():
    start = timer()

    parser = argparse.ArgumentParser(description="Compare image stems across 7 style directories")
    parser.add_argument("--repo-root", help="Root of Kometa-People-Images (fallback: PEOPLE_IMAGES_DIR env)")
    parser.add_argument(
        "--categories",
        nargs="+",
        help="7 style folders under repo-root (default: bw diiivoy diiivoycolor rainier original signature transparent)",
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        help="Explicit 7 absolute/relative directories (bypasses repo-root/categories)",
    )
    parser.add_argument("--png-dir-index", type=int, help="Index (0..6) of the PNG folder; default: auto-detect by name contains 'transparent'")
    parser.add_argument("--case-insensitive", dest="case_sensitive", action="store_false", help="Case-insensitive stem comparison")
    parser.add_argument("--case-sensitive", dest="case_sensitive", action="store_true", help="Case-sensitive stem comparison")
    parser.set_defaults(case_sensitive=parse_bool_env("COMPTREE_CASE_SENSITIVE", True))

    parser.add_argument("--no-dimensions", dest="check_dimensions", action="store_false", help="Disable dimension checks")
    parser.add_argument("--dimensions", dest="check_dimensions", action="store_true", help="Enable dimension checks")
    parser.set_defaults(check_dimensions=parse_bool_env("COMPTREE_CHECK_DIMENSIONS", True))

    parser.add_argument("--required-size", help="WxH e.g. 2000x3000 (env: COMPTREE_REQUIRED_SIZE)")
    parser.add_argument("--jpg-whitelist", help="Comma list of basenames allowed as .jpg in PNG folder (env: COMPTREE_JPG_WHITELIST; default: grid)")

    args = parser.parse_args()

    # Required size
    req_size_env = os.getenv("COMPTREE_REQUIRED_SIZE")
    REQUIRED_WIDTH, REQUIRED_HEIGHT = parse_required_size(
        args.required_size or req_size_env, default_w=2000, default_h=3000
    )

    # Whitelist (defaults to "grid")
    if args.jpg_whitelist is not None:
        JPG_WHITELIST = {x.strip() for x in args.jpg_whitelist.split(",") if x.strip()}
    else:
        wl_env = os.getenv("COMPTREE_JPG_WHITELIST", "grid")
        JPG_WHITELIST = {x.strip() for x in wl_env.split(",") if x.strip()}

    # Build DIRS
    DIRS = [str(p) for p in build_dirs_from_args_env(args)]
    if len(DIRS) != 7:
        raise SystemExit(f"Expected 7 directories, got {len(DIRS)}. Use --dirs or --categories to provide exactly seven.")

    # PNG index
    png_idx_env = os.getenv("COMPTREE_PNG_INDEX")
    png_idx = None
    if args.png_dir_index is not None:
        png_idx = args.png_dir_index
    elif png_idx_env is not None and png_idx_env.strip() != "":
        try:
            png_idx = int(png_idx_env)
        except ValueError:
            raise SystemExit(f"Invalid COMPTREE_PNG_INDEX: {png_idx_env}")

    if png_idx is None:
        png_idx = detect_png_dir_index(DIRS)
    if png_idx is None:
        png_idx = 6  # fallback: last directory

    # Per-directory rules
    per_dir_allowed_exts: list[set[str]] = []
    per_dir_is_png: list[bool] = []
    for i, _ in enumerate(DIRS):
        is_png_folder = (i == png_idx)
        per_dir_is_png.append(is_png_folder)
        per_dir_allowed_exts.append({".png"} if is_png_folder else {".jpg"})

    # Prepare dimension checker (lazy/no-op if disabled)
    dim_checker = check_image_dimensions_lazy(args.check_dimensions)

    # CSV outputs go under ./config/
    OUTPUT_CSV = CONFIG_DIR / "compare_image_trees.csv"
    DIM_ISSUES_CSV = CONFIG_DIR / "image_dimension_issues.csv"

    # How many lines to show in each section (None for unlimited)
    PRINT_LIMIT = 100

    # Case sensitivity
    CASE_SENSITIVE = args.case_sensitive

    # --- Pre-count files for a nice progress bar ---
    totals = []
    grand_total = 0
    for d in DIRS:
        base = Path(d)
        count = sum(1 for _ in iter_image_files(base))
        totals.append(count)
        grand_total += count
    logging.info("Planned scan: %d image files across 7 directories", grand_total)

    # Collect sets + issues with progress bar
    dir_to_stems: dict[str, set[str]] = {}
    dir_to_mismatches: dict[str, List[Tuple[str, str]]] = {}
    dir_to_wl_hits: dict[str, List[str]] = {}
    dir_to_dim_issues: dict[str, List[Tuple[str, Optional[int], Optional[int], Optional[str]]]] = {}

    with alive_bar(grand_total or 1, dual_line=True, title="Scanning images") as bar:
        for i, d in enumerate(DIRS):
            base = Path(d)
            stems, mismatches, wl_hits, dim_issues = gather_stems_and_exts(
                base_dir=base,
                allowed_exts=per_dir_allowed_exts[i],
                case_sensitive=CASE_SENSITIVE,
                jpg_whitelist=JPG_WHITELIST if per_dir_is_png[i] else None,
                treat_png_folder=per_dir_is_png[i],
                dim_checker=dim_checker,
                required_w=REQUIRED_WIDTH,
                required_h=REQUIRED_HEIGHT,
                check_dimensions=args.check_dimensions,
                progress=bar,
            )
            dir_to_stems[d] = stems
            dir_to_mismatches[d] = mismatches
            dir_to_wl_hits[d] = wl_hits
            dir_to_dim_issues[d] = dim_issues

    # Union of all stems
    all_stems = set().union(*dir_to_stems.values()) if dir_to_stems else set()

    # --- Summary (LOGGED) ---
    logging.info("=== Settings ===")
    logging.info("PNG directory index: %d -> %s", png_idx, DIRS[png_idx])
    logging.info("CASE_SENSITIVE: %s", CASE_SENSITIVE)
    logging.info("PNG-folder JPG whitelist: %s", sorted(JPG_WHITELIST) if JPG_WHITELIST else "(none)")
    logging.info("Check dimensions: %s (required %dx%d)", args.check_dimensions, REQUIRED_WIDTH, REQUIRED_HEIGHT)
    logging.info("Outputs: %s and %s", OUTPUT_CSV, (DIM_ISSUES_CSV if args.check_dimensions else "(dimension CSV skipped)"))

    logging.info("=== Directory Stats (included .jpg/.png files only) ===")
    for d in DIRS:
        logging.info("%s :: %d items", d, len(dir_to_stems[d]))

    logging.info("=== Missing counts per directory ===")
    total = len(all_stems)
    for d in DIRS:
        missing = total - len(dir_to_stems[d])
        logging.info("%15s: missing %d of %d", Path(d).name, missing, total)

    # Unique to each directory
    logging.info("=== Items only in each directory (relative stem) ===")
    for d in DIRS:
        others_union = set().union(*[dir_to_stems[o] for o in DIRS if o != d])
        only_in_d = sorted(dir_to_stems[d] - others_union)
        logging.info("[%s] unique count: %d", Path(d).name, len(only_in_d))
        to_show = only_in_d if PRINT_LIMIT is None else only_in_d[:PRINT_LIMIT]
        for s in to_show:
            logging.info("  %s", s)
        if PRINT_LIMIT is not None and len(only_in_d) > PRINT_LIMIT:
            logging.info("  ... (+%d more)", len(only_in_d) - PRINT_LIMIT)

    # Stems missing in any directory
    logging.info("=== Stems missing in at least one directory ===")
    missing_any = []
    for stem in sorted(all_stems):
        missing_dirs = [Path(d).name for d in DIRS if stem not in dir_to_stems[d]]
        if missing_dirs:
            missing_any.append((stem, missing_dirs))
    logging.info("Total stems with at least one missing: %d", len(missing_any))
    to_show = missing_any if PRINT_LIMIT is None else missing_any[:PRINT_LIMIT]
    for stem, md in to_show:
        logging.info("- %s :: missing in %s", stem, ", ".join(md))
    if PRINT_LIMIT is not None and len(missing_any) > PRINT_LIMIT:
        logging.info("... (+%d more)", len(missing_any) - PRINT_LIMIT)

    # Extension mismatches (jpg/png in the wrong place only)
    logging.info("=== Extension mismatches by directory (jpg/png present but disallowed) ===")
    total_mismatch = 0
    for d in DIRS:
        mismatches = dir_to_mismatches[d]
        logging.info("[%s] mismatches: %d", Path(d).name, len(mismatches))
        total_mismatch += len(mismatches)
        to_show = mismatches if PRINT_LIMIT is None else mismatches[:PRINT_LIMIT]
        for rel, reason in to_show:
            logging.info("  %s  ->  %s", rel, reason)
        if PRINT_LIMIT is not None and len(mismatches) > PRINT_LIMIT:
            logging.info("  ... (+%d more)", len(mismatches) - PRINT_LIMIT)
    logging.info("Total mismatches: %d", total_mismatch)

    # Whitelist hits
    logging.info("=== Whitelist hits in PNG folder (accepted .jpg) ===")
    wl_total = 0
    for i, d in enumerate(DIRS):
        is_png = (i == png_idx)
        if not is_png:
            continue
        hits = dir_to_wl_hits[d]
        wl_total += len(hits)
        logging.info("[%s] whitelist .jpg accepted: %d", Path(d).name, len(hits))
        to_show = hits if PRINT_LIMIT is None else hits[:PRINT_LIMIT]
        for rel in to_show:
            logging.info("  %s", rel)
        if PRINT_LIMIT is not None and len(hits) > PRINT_LIMIT:
            logging.info("  ... (+%d more)", len(hits) - PRINT_LIMIT)
    if wl_total == 0:
        logging.info("(none)")

    # --- CSV Matrix ---
    header = ["stem"] + [Path(d).name for d in DIRS]
    rows = []
    for stem in sorted(all_stems):
        row = {"stem": stem}
        for d in DIRS:
            row[Path(d).name] = "Y" if stem in dir_to_stems[d] else ""
        rows.append(row)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    logging.info("CSV written: %s", OUTPUT_CSV.resolve())

    # --- Dimension Issues CSV (only if enabled) ---
    if args.check_dimensions:
        dim_total = sum(len(v) for v in dir_to_dim_issues.values())
        logging.info("=== Dimension issues ===")
        for d in DIRS:
            issues = dir_to_dim_issues[d]
            logging.info("[%s] dimension issues: %d", Path(d).name, len(issues))
            to_show = issues if PRINT_LIMIT is None else issues[:PRINT_LIMIT]
            for rel, w, h, err in to_show:
                if err:
                    logging.info("  %s  ->  ERROR: %s", rel, err)
                else:
                    logging.info("  %s  ->  %dx%d", rel, (w or 0), (h or 0))
            if PRINT_LIMIT is not None and len(issues) > PRINT_LIMIT:
                logging.info("  ... (+%d more)", len(issues) - PRINT_LIMIT)

        DIM_ISSUES_CSV.parent.mkdir(parents=True, exist_ok=True)
        if dim_total > 0:
            with DIM_ISSUES_CSV.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["directory", "relative_path", "width", "height", "error"]
                )
                writer.writeheader()
                for d in DIRS:
                    for rel, w, h, err in dir_to_dim_issues[d]:
                        writer.writerow({
                            "directory": str(d),
                            "relative_path": rel,
                            "width": w if w is not None else "",
                            "height": h if h is not None else "",
                            "error": err if err else "",
                        })
            logging.info("Dimension issues CSV written: %s", DIM_ISSUES_CSV.resolve())
        else:
            logging.info("No dimension issues found.")

    elapsed = timer() - start
    logging.info("Done in %.2fs", elapsed)


if __name__ == "__main__":
    main()
