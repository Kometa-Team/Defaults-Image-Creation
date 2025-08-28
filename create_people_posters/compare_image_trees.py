# compare_image_trees.py
#
# Compares file names (without extensions) across 7 directories (with subfolders).
# Six folders are .jpg; one folder is .png (except explicit .jpg whitelist).
# Only .jpg/.png are considered; all other file types are ignored (not flagged).
# Validates that every .jpg/.png is exactly REQUIRED_WIDTH x REQUIRED_HEIGHT.
# Outputs console summary + presence matrix CSV (compare_image_trees.csv)
# and a dimension issues CSV (image_dimension_issues.csv).
#
# Usage (Windows):  py compare_image_trees.py

from pathlib import Path
import csv
from typing import Optional, List, Tuple
from PIL import Image  # pip install pillow

# ========= CONFIG =========
DIRS = [
    r"D:\bullmoose20\Kometa-People-Images\bw",
    r"D:\bullmoose20\Kometa-People-Images\diiivoy",
    r"D:\bullmoose20\Kometa-People-Images\diiivoycolor",
    r"D:\bullmoose20\Kometa-People-Images\rainier",
    r"D:\bullmoose20\Kometa-People-Images\original",
    r"D:\bullmoose20\Kometa-People-Images\signature",
    r"D:\bullmoose20\Kometa-People-Images\transparent",
]

# Auto-detect PNG folder by name containing "transparent"; or force an index 0..6
PNG_DIR_INDEX: Optional[int] = None

# In the PNG folder, allow .jpg ONLY for these basenames (stems). (grid.jpg etc.)
# Case-insensitive unless CASE_SENSITIVE=True.
JPG_WHITELIST = {"grid"}

# Case sensitivity for comparing stems (relative path without extension)
CASE_SENSITIVE = True

# Required image dimensions
REQUIRED_WIDTH = 2000
REQUIRED_HEIGHT = 3000

# CSV output paths (written in current working directory)
OUTPUT_CSV = Path.cwd() / "compare_image_trees.csv"
DIM_ISSUES_CSV = Path.cwd() / "image_dimension_issues.csv"

# How many lines to print in each section (None for unlimited)
PRINT_LIMIT = 100


# ========= END CONFIG =====


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


def check_image_dimensions(path: Path) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Return (width, height, error) for the image at path.
    If unreadable, returns (None, None, str(error_message)).
    """
    try:
        # Pillow usually reads size without decoding full image
        with Image.open(path) as im:
            return im.width, im.height, None
    except Exception as e:
        return None, None, str(e)


def gather_stems_and_exts(
        base_dir: Path,
        allowed_exts: set[str],
        case_sensitive: bool,
        jpg_whitelist: Optional[set[str]] = None,
        treat_png_folder: bool = False,
):
    """
    Walk base_dir recursively and collect:
      - stems: set of relative stems (without extension) that pass the rules
      - ext_mismatches: list of jpg/png files present but disallowed by the folder rules
      - whitelist_hits: list of .jpg files accepted due to whitelist in PNG folder
      - dim_issues: list of (rel_path, width, height, error) where image is not REQUIRED_WxH
                    or failed to open (error != None)

    Only .jpg/.png are considered; all other extensions are ignored silently.
    """
    stems = set()
    ext_mismatches: List[Tuple[str, str]] = []  # (rel_path, reason)
    whitelist_hits: List[str] = []  # (rel_path)
    dim_issues: List[Tuple[str, Optional[int], Optional[int], Optional[str]]] = []

    if not base_dir.exists():
        print(f"WARNING: directory does not exist: {base_dir}")
        return stems, ext_mismatches, whitelist_hits, dim_issues

    # Prepare once for comparisons
    wl_cmp = {normalize_case(x, case_sensitive) for x in (jpg_whitelist or set())}

    for p in base_dir.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(base_dir)
        rel_posix = rel.as_posix()
        ext_actual = p.suffix  # keep original case
        ext_cmp = ext_actual.lower()  # extension comparison is case-insensitive

        # Ignore non-image files entirely
        if ext_cmp not in {".jpg", ".png"}:
            continue

        # Validate dimensions for any jpg/png encountered (regardless of folder rule)
        w, h, err = check_image_dimensions(p)
        if err is not None or w != REQUIRED_WIDTH or h != REQUIRED_HEIGHT:
            dim_issues.append((rel_posix, w, h, err))

        basename = rel.stem
        basename_cmp = normalize_case(basename, case_sensitive)

        if ext_cmp in allowed_exts:
            # Allowed here (.jpg for jpg-folders, .png for png-folder)
            stems.add(normalize_stem(rel, case_sensitive))

        elif treat_png_folder and ext_cmp == ".jpg":
            # PNG folder: allow .jpg ONLY if whitelisted
            if basename_cmp in wl_cmp:
                stems.add(normalize_stem(rel, case_sensitive))
                whitelist_hits.append(rel_posix)
            else:
                # It's a jpg in PNG folder and not whitelisted -> mismatch
                ext_mismatches.append((rel_posix, "Unexpected .jpg in PNG folder (not whitelisted)"))

        else:
            # It's the wrong of the two relevant extensions
            reason = "Unexpected .png in JPG folder" if ext_cmp == ".png" else "Unexpected .jpg in PNG folder"
            ext_mismatches.append((rel_posix, reason))

    return stems, ext_mismatches, whitelist_hits, dim_issues


def main():
    if len(DIRS) != 7:
        raise SystemExit(f"Expected 7 directories in DIRS, found {len(DIRS)}")

    png_idx = PNG_DIR_INDEX if PNG_DIR_INDEX is not None else detect_png_dir_index(DIRS)
    if png_idx is None:
        png_idx = 6  # fallback: last directory

    # Per-directory rules
    per_dir_allowed_exts: list[set[str]] = []
    per_dir_is_png: list[bool] = []
    for i, _ in enumerate(DIRS):
        is_png_folder = (i == png_idx)
        per_dir_is_png.append(is_png_folder)
        per_dir_allowed_exts.append({".png"} if is_png_folder else {".jpg"})

    # Collect sets + issues
    dir_to_stems: dict[str, set[str]] = {}
    dir_to_mismatches: dict[str, List[Tuple[str, str]]] = {}
    dir_to_wl_hits: dict[str, List[str]] = {}
    dir_to_dim_issues: dict[str, List[Tuple[str, Optional[int], Optional[int], Optional[str]]]] = {}

    for i, d in enumerate(DIRS):
        base = Path(d)
        stems, mismatches, wl_hits, dim_issues = gather_stems_and_exts(
            base_dir=base,
            allowed_exts=per_dir_allowed_exts[i],
            case_sensitive=CASE_SENSITIVE,
            jpg_whitelist=JPG_WHITELIST if per_dir_is_png[i] else None,
            treat_png_folder=per_dir_is_png[i],
        )
        dir_to_stems[d] = stems
        dir_to_mismatches[d] = mismatches
        dir_to_wl_hits[d] = wl_hits
        dir_to_dim_issues[d] = dim_issues

    # Union of all stems
    all_stems = set().union(*dir_to_stems.values()) if dir_to_stems else set()

    # --- Console Summary ---
    print("\n=== Settings ===")
    print(f"PNG directory index: {png_idx} -> {DIRS[png_idx]}")
    print(f"CASE_SENSITIVE: {CASE_SENSITIVE}")
    print(f"PNG-folder JPG whitelist: {sorted(JPG_WHITELIST) if JPG_WHITELIST else '(none)'}")
    print(f"Required dimensions: {REQUIRED_WIDTH}x{REQUIRED_HEIGHT}")

    print("\n=== Directory Stats (included .jpg/.png files only) ===")
    for d in DIRS:
        print(f"{d} :: {len(dir_to_stems[d])} items")

    print("\n=== Missing counts per directory ===")
    total = len(all_stems)
    for d in DIRS:
        missing = total - len(dir_to_stems[d])
        print(f"{Path(d).name:>15}: missing {missing} of {total}")

    # Unique to each directory
    print("\n=== Items only in each directory (relative stem) ===")
    for d in DIRS:
        others_union = set().union(*[dir_to_stems[o] for o in DIRS if o != d])
        only_in_d = sorted(dir_to_stems[d] - others_union)
        print(f"\n[{Path(d).name}] unique count: {len(only_in_d)}")
        to_show = only_in_d if PRINT_LIMIT is None else only_in_d[:PRINT_LIMIT]
        for s in to_show:
            print("  " + s)
        if PRINT_LIMIT is not None and len(only_in_d) > PRINT_LIMIT:
            print(f"  ... (+{len(only_in_d) - PRINT_LIMIT} more)")

    # Stems missing in any directory
    print("\n=== Stems missing in at least one directory ===")
    missing_any = []
    for stem in sorted(all_stems):
        missing_dirs = [Path(d).name for d in DIRS if stem not in dir_to_stems[d]]
        if missing_dirs:
            missing_any.append((stem, missing_dirs))
    print(f"Total stems with at least one missing: {len(missing_any)}")
    to_show = missing_any if PRINT_LIMIT is None else missing_any[:PRINT_LIMIT]
    for stem, md in to_show:
        print(f"- {stem} :: missing in {', '.join(md)}")
    if PRINT_LIMIT is not None and len(missing_any) > PRINT_LIMIT:
        print(f"... (+{len(missing_any) - PRINT_LIMIT} more)")

    # Extension mismatches (jpg/png in the wrong place only)
    print("\n=== Extension mismatches by directory (jpg/png present but disallowed) ===")
    total_mismatch = 0
    for d in DIRS:
        mismatches = dir_to_mismatches[d]
        print(f"\n[{Path(d).name}] mismatches: {len(mismatches)}")
        total_mismatch += len(mismatches)
        to_show = mismatches if PRINT_LIMIT is None else mismatches[:PRINT_LIMIT]
        for rel, reason in to_show:
            print(f"  {rel}  ->  {reason}")
        if PRINT_LIMIT is not None and len(mismatches) > PRINT_LIMIT:
            print(f"  ... (+{len(mismatches) - PRINT_LIMIT} more)")
    print(f"\nTotal mismatches: {total_mismatch}")

    # Whitelist hits
    print("\n=== Whitelist hits in PNG folder (accepted .jpg) ===")
    wl_total = 0
    for i, d in enumerate(DIRS):
        if not per_dir_is_png[i]:
            continue
        hits = dir_to_wl_hits[d]
        wl_total += len(hits)
        print(f"\n[{Path(d).name}] whitelist .jpg accepted: {len(hits)}")
        to_show = hits if PRINT_LIMIT is None else hits[:PRINT_LIMIT]
        for rel in to_show:
            print(f"  {rel}")
        if PRINT_LIMIT is not None and len(hits) > PRINT_LIMIT:
            print(f"  ... (+{len(hits) - PRINT_LIMIT} more)")
    if wl_total == 0:
        print("(none)")

    # --- Dimension issues ---
    print("\n=== Dimension issues (any .jpg/.png not "
          f"{REQUIRED_WIDTH}x{REQUIRED_HEIGHT} or unreadable) ===")
    dim_total = 0
    for d in DIRS:
        issues = dir_to_dim_issues[d]
        dim_total += len(issues)
        print(f"\n[{Path(d).name}] dimension issues: {len(issues)}")
        to_show = issues if PRINT_LIMIT is None else issues[:PRINT_LIMIT]
        for rel, w, h, err in to_show:
            if err:
                print(f"  {rel}  ->  ERROR: {err}")
            else:
                print(f"  {rel}  ->  {w}x{h}")
        if PRINT_LIMIT is not None and len(issues) > PRINT_LIMIT:
            print(f"  ... (+{len(issues) - PRINT_LIMIT} more)")
    print(f"\nTotal dimension issues: {dim_total}")

    # --- CSV Matrix ---
    header = ["stem"] + [Path(d).name for d in DIRS]
    rows = []
    for stem in sorted(all_stems):
        row = {"stem": stem}
        for d in DIRS:
            row[Path(d).name] = "Y" if stem in dir_to_stems[d] else ""
        rows.append(row)

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV written: {OUTPUT_CSV.resolve()}")

    # --- Dimension Issues CSV ---
    if dim_total > 0:
        with DIM_ISSUES_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["directory", "relative_path", "width", "height", "error"]
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
        print(f"Dimension issues CSV written: {DIM_ISSUES_CSV.resolve()}")
    else:
        print("No dimension issues found.")


if __name__ == "__main__":
    main()
