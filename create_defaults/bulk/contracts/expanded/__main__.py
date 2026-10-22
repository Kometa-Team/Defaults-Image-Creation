"""Opt-in M5 reports. No state creation, workers, remote access or enforcement."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

from ...common import BulkError, atomic_bytes, canonical, reject_links
from ...config import Config
from .graph import Snapshot, MAX_BYTES, compare
from .historical import capture
from .resolution import resolve
from .validation import boundary, validate_existing


def read_snapshot(path, checksum):
    path = reject_links(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES+1)
    return Snapshot.load(raw,expected_sha256=checksum)


def write_report(path, raw):
    path = reject_links(path).resolve()
    config = Config()
    for protected in (config.asset_dir,config.cache_dir,config.workspace_dir,config.output_dir):
        if path.is_relative_to(protected):
            raise BulkError("m5_report_isolation", "Reports cannot overwrite production data/state/output")
    try:
        atomic_bytes(path,raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise BulkError("m5_immutable_report", "Existing report differs; choose a new path")


def summary(graph):
    value = graph.data()
    return {"snapshot_sha256":graph.sha256,"bytes":len(graph.encoded),"outputs":len(value["outputs"]),
        "public_outputs":sum(o["public_path"] is not None for o in value["outputs"].values()),
        "nodes":len(value["nodes"]),"unresolved":value["unresolved"],
        "production_enforcement":False,"publication_authorized":False,"merge_authorized":False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command",required=True)
    audit = commands.add_parser("audit",help="Recheck all 14,079 M2 records without rendering")
    audit.add_argument("--snapshot-out",type=Path)
    audit.add_argument("--report",type=Path)
    commands.add_parser("resolve",help="Inspect actual loader/expander membership without assets/state")
    validation = commands.add_parser("validate-playlist",help="Read-only contract compatibility; not contract approval")
    validation.add_argument("--fixture-only",action="store_true",help="Explicitly audit the unapproved M3 contract")
    for name in ("inspect","impact","compare"):
        command = commands.add_parser(name)
        command.add_argument("snapshot",type=Path)
        command.add_argument("--sha256",required=True)
        if name == "impact":
            command.add_argument("--changed",action="append",required=True)
        if name == "compare":
            command.add_argument("proposed",type=Path)
            command.add_argument("--proposed-sha256",required=True)
    args = parser.parse_args(argv)
    try:
        start = perf_counter()
        if args.command == "audit":
            registry,records,resolution,graph = capture(progress=lambda s:print(s,file=sys.stderr,flush=True))
            report = summary(graph) | {"M2_registry_sha256":registry.sha256,"declared_definitions":len(resolution.data()["declared"]),
                "generator_families":len(resolution.data()["families"]),"historical_compatibility":"verified_unchanged_material",
                "contract_authority":"not_granted_by_historical_audit","seconds":perf_counter()-start}
            if args.snapshot_out:
                write_report(args.snapshot_out,graph.encoded)
            if args.report:
                write_report(args.report,canonical(report))
        elif args.command == "resolve":
            value = resolve().data()
            report = {"declared":len(value["declared"]),"expanded":len(value["expanded"]),"families":len(value["families"]),
                "production_enforcement":False}
        elif args.command == "validate-playlist":
            if not args.fixture_only:
                raise BulkError("m5_unapproved_contract","No actual exact-package approval is bundled. Operational API requires external M1 decision attribution")
            current, reference = resolve(), boundary()
            report = {"items":[validate_existing(r,current,fixture_only=True) for r in reference.records],
                "fixture_only":True,"publication_authorized":False,"production_enforcement":False}
        else:
            graph = read_snapshot(args.snapshot,args.sha256)
            if args.command == "inspect":
                report = summary(graph)
            elif args.command == "impact":
                report = graph.index().impact(args.changed)
            else:
                report = compare(graph,read_snapshot(args.proposed,args.proposed_sha256))
        print(json.dumps(report,sort_keys=True,ensure_ascii=True,indent=2))
        return 0 if not report.get("unresolved") else 1
    except (BulkError,OSError) as error:
        print(json.dumps({"status":"blocked","code":getattr(error,"code","m5_io"),"diagnostic":str(error)},ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
