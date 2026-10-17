"""Small offline cross-platform acceptance artifact; never the full catalog."""
import json
from pathlib import Path
from .common import fingerprint
from .config import ROOT
from .e_validation import save, workload
from .e_overlays import run as overlay_run


def main():
    root = ROOT.parent / "config/package-e-ci"
    posters = workload(root / "posters", categories=["Based", "Decade"], workers=2)
    overlays = overlay_run(root / "overlays", workers=2)
    selected = {}
    for scope, folder, pattern in (("posters", root / "posters", "verified-output-ledger.json"),
                                   ("overlays", root / "overlays", "output-ledger.json")):
        for item in json.loads((folder / pattern).read_text()):
            selected[scope + "/" + item["path"]] = item["sha256"]
    summary = {"posters": posters, "overlays": overlays, "output_hashes": selected,
               "full_catalog_run": False, "published": 0, "approved": 0,
               "scope": "35 English posters including dependencies plus bounded overlay samples; not a production batch"}
    summary["sha256"] = fingerprint(summary)
    save(root / "ci-evidence.json", summary)


if __name__ == "__main__":
    main()
