"""Explicit read-only M6 audit; isolated reports, no approval or activation."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from ...common import BulkError,canonical
from ..expanded.__main__ import write_report
from .evidence import capture
from .release import Implementation,RELEASE_SHA256
from .audit import audit


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-sha256",required=True)
    parser.add_argument("--object-root",type=Path,help="Explicit immutable M2 object cache, never live state")
    parser.add_argument("--dependency-snapshot",type=Path,help="Explicit immutable accepted M5 graph; sources/definitions are still rechecked")
    parser.add_argument("--dependency-sha256")
    parser.add_argument("--category",action="append",default=[])
    parser.add_argument("--report",type=Path)
    args=parser.parse_args(argv)
    try:
        began=perf_counter()
        implementation=Implementation.load(expected_sha256=args.release_sha256)
        registry,records,resolution,graph,sources=capture(args.object_root,dependency_snapshot=args.dependency_snapshot,
            dependency_sha256=args.dependency_sha256)
        report=audit(implementation,registry,records,resolution,graph,categories=args.category)
        report.update({"capture_and_audit_seconds":perf_counter()-began,"actual_inputs_verified":len(sources)})
        if args.report:write_report(args.report,canonical(report))
        print(json.dumps(report,indent=2,ensure_ascii=True))
        return 0
    except (BulkError,OSError,ValueError) as error:
        print(json.dumps({"error":str(error),"production_enforcement":False,"publication_authorized":False}))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
