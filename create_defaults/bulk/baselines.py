"""Keep historical Phase 1 validation distinct from the corrected current source.

Historical source reconstruction accepts only the exact, hash-bound 2011/2911
row correction. All other source, input, font and manifest checks remain active.
"""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile

from create_defaults.create_poster import ROOT
from create_defaults.validation_manifest import load_manifest, text_digest, validate_manifest
from .common import BulkError


BASE = Path(__file__).resolve().parent / "baselines"


@contextmanager
def historical_sources(assets=ROOT):
    proof = json.loads((BASE / "source-delta.json").read_text(encoding="utf-8"))
    source = Path(assets) / "create_default_posters.ps1"
    if text_digest(source) != proof["current_source_text_sha256"]:
        raise BulkError("baseline_source_changed", "Current source differs from the separately audited correction")
    lines = source.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    position = proof["line"] - 1
    if lines[position].rstrip("\n") != proof["current_line"]:
        raise BulkError("baseline_source_changed", "Correction source row no longer matches its audit")
    lines[position] = proof["historical_line"] + ("\n" if lines[position].endswith("\n") else "")
    with tempfile.TemporaryDirectory(prefix="defaults-historical-source-") as directory:
        root = Path(directory)
        for name in ("create_default_posters.ps1", "create_poster.ps1", "create_poster.py", "poster_text.py"):
            text = "".join(lines) if name == "create_default_posters.ps1" else (Path(assets) / name).read_text(encoding="utf-8-sig")
            (root / name).write_text(text, encoding="utf-8", newline="\n")
        if text_digest(root / source.name) != proof["historical_source_text_sha256"]:
            raise BulkError("baseline_source_changed", "Reconstructed historical source fails its original hash")
        yield root


def verify_historical(manifest=None, assets=ROOT):
    manifest = manifest or load_manifest(ROOT / "fixtures/effective-jobs-en-cmap-compat.json.gz")
    with historical_sources(assets) as source_root:
        return validate_manifest(manifest, assets=assets, source_root=source_root)


def verify_current(assets=ROOT):
    value = load_manifest(BASE / "effective-jobs-en-current.json.gz")
    validate_manifest(value, assets=assets)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-historical", action="store_true")
    args = parser.parse_args(argv)
    if args.check_historical:
        verify_historical()
        print("Historical Phase 1 baseline verified against its exact reconstructed source identity; no historical fixture changed")
    else:
        value = verify_current()
        print(f"Corrected current-source capture verified: {len(value['jobs'])} legacy jobs; not new rendering evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
