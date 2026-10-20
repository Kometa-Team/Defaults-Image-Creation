"""Development-only export of four real examples and the corrected capture baseline.

Never renders or invokes PowerShell. Not a category migration tool.
"""

import argparse
import hashlib
import json
from pathlib import Path

import yaml

from create_defaults.create_poster import ROOT
from create_defaults.validation_manifest import load_manifest, validate_manifest
from .common import canonical, fingerprint


def write_once(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError("Refusing to overwrite changed baseline/example evidence")
    else:
        with path.open("xb") as stream:
            stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    args = parser.parse_args(argv)
    capture = load_manifest(args.capture)
    validate_manifest(capture)
    historical = load_manifest(ROOT / "fixtures/effective-jobs-en-cmap-compat.json.gz")
    text = (ROOT / "create_default_posters.ps1").read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    current_line = lines[4492].rstrip("\n")
    if current_line.count("| Death in Paradise (2011)|") != 1:
        raise ValueError("Unexpected current correction row")
    historical_line = current_line.replace("| Death in Paradise (2011)|", "| Death in Paradise (2911)|")
    lines[4492] = historical_line + "\n"
    if hashlib.sha256("".join(lines).encode()).hexdigest() != historical["source_text_hashes"]["create_default_posters.ps1"]:
        raise ValueError("Current correction does not reconstruct the exact historical source")
    base = Path(__file__).resolve().parent
    proof = {"schema_version": 1, "line": 4493, "current_line": current_line, "historical_line": historical_line,
             "historical_source_text_sha256": historical["source_text_hashes"]["create_default_posters.ps1"],
             "current_source_text_sha256": capture["source_text_hashes"]["create_default_posters.ps1"],
             "historical_manifest_sha256": historical["sha256"], "current_manifest_sha256": capture["sha256"],
             "scope": "Source/capture identity only; no new rendered artwork or transferred approvals"}
    (base / "baselines").mkdir(exist_ok=True)
    write_once(base / "baselines/source-delta.json", canonical(proof) + b"\n")
    write_once(base / "baselines/approved-fonts.json", canonical({"schema_version": 1,
        "source_manifest_sha256": historical["sha256"], "scope": "Exact active bundled Phase 1 font identities; retain existing license notices/provenance",
        "fonts": {path: value["sha256"] for path, value in historical["fonts"].items()}}) + b"\n")
    write_once(base / "baselines/effective-jobs-en-current.json.gz", args.capture.read_bytes())
    examples = json.loads((ROOT / "phase2/evidence/sample-manifest.json").read_text(encoding="utf-8"))
    (base / "examples").mkdir(exist_ok=True)
    for sample in examples["jobs"]:
        job = next(job for job in capture["jobs"] if job["id"] == sample["legacy_job_id"])
        parameters = dict(job["parameters"], font=job["font"]["path"], text="")
        for field in ("font_size", "logo_resize"):
            if field in job["raw_parameters"]:
                parameters[field] = int(job["raw_parameters"][field])
        key = job["source_row"]["key_name"]
        mode = "none" if not job["text"] else "shared" if job["category"] == "Year" else "translation"
        measurement = None
        if job["fitting"] and job["text"]:
            fitting = job["fitting"]
            measurement = {"text": job["text"], "font_sha256": job["font"]["sha256"], "point_size": fitting["point_size"],
                           "box": fitting["box"], "minimum": fitting["minimum"], "maximum": fitting["maximum"], "evidence_sha256": job["sha256"]}
        value = {"id": sample["poster_id"], "category": job["category"], "display_name": job["name"],
                 "source": {"path": "create_default_posters.ps1", "line": job["source"]["definition_line"], "row_sha256": fingerprint(job["source_row"])},
                 "composer": parameters,
                 "caption": {"mode": mode, "key": "key_names." + key if mode == "translation" else None, "template_key": None,
                             "text": job["text"] if mode == "shared" else "", "case": "upper", "direction": "auto", "fallback": None},
                 "layout": {"kind": "captured_fit" if measurement else "fixed", "measurement": measurement},
                 "languages": ["en"], "applicability": {"en": {"status": "applicable", "reason": "Representative English infrastructure example only"}},
                 "output": {"directory": str(Path(job["published_relatives"][0]).parent).replace("\\", "/"),
                            "filename": Path(job["published_relatives"][0]).name, "remote_paths": {"en": job["published_relatives"][0]}},
                 "color_assignment": {"id": sample["poster_id"] + ".background", "origin": "historical", "parent": None, "relationship": None, "exception": None},
                 "dependencies": [], "overrides": [], "generator": None}
        document = {"schema_version": 1, "category": job["category"], "definitions": [value]}
        write_once(base / "examples" / (job["category"].lower() + ".yml"), yaml.safe_dump(document, sort_keys=False, allow_unicode=False).encode("utf-8"))
    write_once(base / "examples/profiles.yml", b"schema_version: 1\nprofiles: {}\n")
    print("Exported four representative definition files and a separate current-source capture baseline; no artwork rendered")


if __name__ == "__main__":
    main()
