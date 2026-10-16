"""Explicit local planning/rendering CLI; never publishes or activates production."""

import argparse
import json
import os
from pathlib import Path

from .assets import discover_assets, historical_asset_usage
from .colors import ColorPolicy, ColorRegistry, suggest_colors
from .common import BulkError, atomic_bytes, canonical
from .config import ALIASES, CATEGORIES, Config, LANGUAGES
from .definitions import load_definitions
from .planner import Planner
from .remote import GitHubError, ReadOnlyGitHub, RemoteInventory
from .state import Store
from .translations import Translations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cache-dir", "workspace-dir", "output-dir", "asset-dir", "translation-dir"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--config-file", type=Path)
    parser.add_argument("--offline", action="store_true", default=None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-categories")
    commands.add_parser("list-languages")
    for command in ("validate-definitions", "plan", "discover-assets", "generate"):
        sub = commands.add_parser(command)
        sub.add_argument("--definitions", nargs="+", type=Path, required=command not in {"discover-assets", "generate"})
        sub.add_argument("--profiles", type=Path)
        if command in {"plan", "generate"}:
            sub.add_argument("--category", action="append", default=[])
            sub.add_argument("--poster", action="append", default=[])
            sub.add_argument("--language", action="append", default=[])
            if command == "plan":
                sub.add_argument("--manifest", type=Path)
            else:
                sub.add_argument("--workers", type=int, default=2)
                sub.add_argument("--timeout", type=float, default=120)
                sub.add_argument("--retries", type=int, default=1)
                sub.add_argument("--recycle-after", type=int, default=200)
                sub.add_argument("--retry-failed", action="store_true")
                sub.add_argument("--report", type=Path)
        elif command == "discover-assets":
            sub.add_argument("--directory", action="append", required=True)
            sub.add_argument("--legacy-baseline", type=Path)
    sub = commands.add_parser("audit-colors")
    sub.add_argument("--audit", type=Path)
    sub = commands.add_parser("suggest-colors")
    sub.add_argument("--policy", type=Path, required=True)
    sub.add_argument("--logo", type=Path, required=True)
    sub.add_argument("--poster", required=True)
    sub.add_argument("--category", required=True)
    sub = commands.add_parser("remote-inventory")
    sub.add_argument("--refresh", action="store_true")
    sub.add_argument("--path")
    sub.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = Config.load(file=args.config_file, **{name: getattr(args, name) for name in
            ("cache_dir", "workspace_dir", "output_dir", "asset_dir", "translation_dir", "offline")})
        if args.command == "list-categories":
            result = {"categories": CATEGORIES, "aliases": ALIASES}
        elif args.command == "list-languages":
            result = {"languages": [{"code": language, "available": (config.translation_dir / (language + ".yml")).is_file(),
                                      "rendering_validated": False} for language in LANGUAGES]}
        elif args.command in {"validate-definitions", "plan", "discover-assets", "generate"}:
            if args.command == "generate" and not args.definitions:
                from .catalog import load_catalog
                definitions = load_catalog(args.category)
            else:
                definitions = load_definitions(args.definitions or (), profiles_path=args.profiles)
            if args.command == "validate-definitions":
                result = {"definitions": [{"id": item.id, "fingerprint": item.fingerprint} for item in definitions]}
            elif args.command in {"plan", "generate"}:
                languages = args.language or ["en"]
                sources = {language: config.translation_dir / (language + ".yml") for language in languages
                           if (config.translation_dir / (language + ".yml")).is_file()}
                from .generators import GENERATORS
                if args.command == "plan":
                    result = Planner(config, generators=GENERATORS).plan(definitions, Translations(sources), categories=args.category, posters=args.poster, languages=languages)
                    if args.manifest:
                        atomic_bytes(args.manifest, canonical(result) + b"\n")
                else:
                    from .generation import generate
                    from .workers import WorkerLimits
                    limits = WorkerLimits(workers=args.workers, timeout_seconds=args.timeout, retries=args.retries, recycle_after=args.recycle_after,
                                          total_worker_memory_bytes=max(1024 * 1024 * 1024, args.workers * 512 * 1024 * 1024))
                    result = generate(definitions, Translations(sources), config=config, limits=limits, generators=GENERATORS,
                                      categories=args.category, posters=args.poster, languages=languages, retry_failed=args.retry_failed)
                    if args.report:
                        atomic_bytes(args.report, canonical(result) + b"\n")
                    result = {"status": result["status"], "stages": [{"depth": stage["depth"], "manifest_sha256": stage["manifest"]["sha256"],
                              "jobs": len(stage["manifest"]["jobs"]), "metrics": stage["execution"]["metrics"]} for stage in result["stages"]]}
            else:
                from create_defaults.validation_manifest import load_manifest
                baseline = args.legacy_baseline or Path(__file__).resolve().parent / "baselines/effective-jobs-en-current.json.gz"
                capture = load_manifest(baseline)
                structure = json.loads((Path(__file__).resolve().parents[1] / "phase2/evidence/current-source-audit.json").read_text(encoding="utf-8"))
                overlays = {path for operation in structure["overlays"] for path in operation["inputs"]}
                result = discover_assets(config.asset_dir, args.directory, definitions, overlay_inputs=overlays, historical_assignments=historical_asset_usage(capture))
        elif args.command in {"audit-colors", "suggest-colors"}:
            audit_path = getattr(args, "audit", None) or Path(__file__).resolve().parents[1] / "phase2/evidence/historical-colors.json"
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            if args.command == "audit-colors":
                result = {"summary": audit["summary"], "duplicate_groups": audit["duplicate_groups"],
                          "policy": "D01 preserves historical duplicates without creating approved exceptions"}
            else:
                policy = ColorPolicy(**json.loads(args.policy.read_text(encoding="utf-8")))
                registry = ColorRegistry(Store(config.cache_dir / "state.sqlite"), policy)
                registry.import_historical(audit)
                result = suggest_colors(args.logo, registry, args.poster, args.category)
        else:
            if config.offline and args.refresh:
                raise BulkError("invalid_config", "Offline mode cannot refresh remote metadata")
            client = ReadOnlyGitHub(config.github_repository, token=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"), max_bytes=config.max_blob_bytes * 2) if args.refresh or (args.download and not config.offline) else None
            inventory = RemoteInventory(Store(config.cache_dir / "remote.sqlite"), config, client)
            result = inventory.refresh() if args.refresh else {"snapshot": inventory.snapshot()}
            if args.path:
                result["lookup"] = inventory.lookup(args.path)
            if args.download:
                if not args.path:
                    raise BulkError("invalid_selection", "Download requires an explicit remote path")
                result["download"] = inventory.fetch_image(args.path).relative_to(config.cache_dir).as_posix()
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
        return 3 if args.command == "generate" and result["status"] != "verified" else 0
    except BulkError as error:
        parser.exit(5 if error.code == "stale_version" else 2, f"{error.code}: {error}\n")
    except GitHubError as error:
        parser.exit(4, f"remote_error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
