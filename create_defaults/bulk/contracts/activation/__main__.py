"""M7 isolated operator tools; default is read-only inventory, never activation."""

import argparse
import json
import sqlite3
from pathlib import Path

from ...common import BulkError, canonical
from ..categories.release import Implementation, RELEASE_SHA256
from ..expanded.__main__ import write_report
from ..models import read_json_bytes
from .models import Proposal
from .readiness import inventory, dossier


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",nargs="?",default="inspect",choices=["inspect","missing-approvals","validate-proposal","audit","state","simulate"])
    parser.add_argument("--proposal",type=Path)
    parser.add_argument("--proposal-sha256")
    parser.add_argument("--state-root",type=Path)
    parser.add_argument("--identity")
    parser.add_argument("--object-root",type=Path)
    parser.add_argument("--dependency-snapshot",type=Path)
    parser.add_argument("--dependency-sha256")
    parser.add_argument("--report",type=Path)
    args = parser.parse_args(argv)
    try:
        implementation = Implementation.load(expected_sha256=RELEASE_SHA256) if args.command not in {"state","simulate"} else None
        if args.command in {"inspect","missing-approvals"}:
            report = inventory(implementation)
        elif args.command == "validate-proposal":
            if args.proposal is None or args.proposal_sha256 is None:
                raise BulkError("activation_proposal", "Proposal file and externally selected exact SHA are both required")
            proposal = Proposal.from_bytes(read_json_bytes(args.proposal))
            if proposal.sha256 != args.proposal_sha256:
                raise BulkError("activation_proposal_pin", "Proposal differs from selected hash")
            p = proposal.to_dict();package = implementation.select(p["package"]["category"])
            from ..registry import package_reference
            expected_id="defaults."+p["package"]["category"].lower()+"."+p["package"]["kind"]
            if p["namespace"] != "isolated" or p["package"] != package_reference(package.contract) or p["id"] != expected_id:
                raise BulkError("activation_proposal_pin", "Proposal does not select the exact implemented package")
            report = {"proposal_sha256":proposal.sha256,"structurally_valid":True,"activation_eligible":False,
                "pins":{"contract":"verified_exact_implementation","source_commit":"not_authenticated_or_reconciled",
                    "registry":"missing_authenticated_selection","adoption":"not_freshly_validated",
                    "graph":"not_freshly_validated","material":"not_freshly_validated","compatibility":"not_freshly_validated"},
                "blockers":["authenticated_intake_unavailable","fresh_compatibility_and_registry_approval_required","independent_operator_decision_missing"],
                "production_enforcement":False,"publication_authorized":False}
        elif args.command == "audit":
            from ..categories.evidence import capture
            report = dossier(implementation,*capture(args.object_root,dependency_snapshot=args.dependency_snapshot,dependency_sha256=args.dependency_sha256))
        elif args.command == "state":
            from .storage import Archive
            if args.state_root is None or not args.identity:
                raise BulkError("activation_state", "Explicit isolated root and identity required")
            history = Archive.inspect_readonly(args.state_root,args.identity)
            recorded=history[-1].to_dict()["state"] if history else "IMPLEMENTED"
            report = {"history":[r.to_dict() for r in history],"effective_state":recorded if recorded in {"IMPLEMENTED","SUSPENDED","REVOKED"} else "SUSPENDED",
                "reason":"read-only restart inspection grants no authority; ACTIVE snapshots require fresh operator authorization",
                "production_enforcement":False,"publication_authorized":False}
        else:
            from .simulation import demo
            if args.state_root is None:
                raise BulkError("activation_simulation", "Explicit empty isolated --state-root required")
            report = demo(args.state_root)
        if args.report:
            write_report(args.report,canonical(report))
        print(json.dumps(report,indent=2,ensure_ascii=True))
        return 0
    except (BulkError,OSError,ValueError,sqlite3.DatabaseError) as error:
        print(json.dumps({"error":str(error),"code":getattr(error,"code","activation_input"),"production_enforcement":False,"publication_authorized":False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
