"""Read-only discovery by default; explicit persistence uses isolated M1 state."""

import argparse
import json
import sys
from pathlib import Path

from ...common import BulkError, atomic_bytes, canonical, reject_links
from ...config import Config
from .inventory import discover
from .models import read_canonical
from .storage import AdoptionArchive


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="Optional new local JSON audit file")
    parser.add_argument("--persist", type=Path, help="Explicit isolated M1 state root; omitted for dry-run")
    parser.add_argument("--inspect", action="store_true", help="Read an existing committed snapshot; requires --persist and --sha256")
    parser.add_argument("--sha256", help="Exact registry pin for inspection")
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            if args.persist is None or args.sha256 is None:
                parser.error("--inspect requires --persist and --sha256")
            if not (args.persist / "state.sqlite3").is_file():
                raise BulkError("missing_adoption", "Inspection requires an existing isolated adoption database")
            registry, records = AdoptionArchive(args.persist).load("historical-defaults-m2", "1.0.0", expected_sha256=args.sha256)
        else:
            registry, records = discover(progress=lambda stage: print(stage, file=sys.stderr, flush=True))
            if args.persist:
                AdoptionArchive(args.persist).commit(registry, records)
        report = read_canonical(registry.to_dict()["audit_json"]) | {"registry_sha256": registry.sha256,
            "mode": "inspect" if args.inspect else "persist" if args.persist else "dry-run"}
        if args.report:
            report_path = reject_links(args.report).resolve()
            config = Config()
            for root in (config.asset_dir, config.cache_dir, config.workspace_dir, config.output_dir):
                if report_path.is_relative_to(root.resolve()):
                    raise BulkError("adoption_report_isolation", "Audit reports must remain outside production roots")
            encoded = canonical(report) + b"\n"
            try:
                atomic_bytes(report_path, encoded)
            except FileExistsError:
                if report_path.read_bytes() != encoded:
                    raise BulkError("immutable_adoption_report", "Existing report differs; choose a new report path")
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (BulkError, OSError) as error:
        print(json.dumps({"status": "blocked", "code": getattr(error, "code", "adoption_io"),
                          "diagnostic": getattr(error, "details", str(error))}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
