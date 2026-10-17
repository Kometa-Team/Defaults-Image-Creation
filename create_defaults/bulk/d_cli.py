"""Package D commands on the existing bulk CLI, with distinct exit outcomes."""

import json
import os
from pathlib import Path

from .common import BulkError, atomic_bytes, canonical


COMMANDS = {"refresh-translations", "preflight", "preview", "translation-delta", "overlays", "review", "propose-layout"}
EXITS = {"verified": 0, "complete": 0, "audited": 0, "partial": 3, "strict_blocked": 6, "incomplete": 7}


def register(commands):
    sub = commands.add_parser("refresh-translations")
    sub.add_argument("--token-env", default="GH_TOKEN")
    for name in ("preflight", "preview", "propose-layout"):
        sub = commands.add_parser(name)
        sub.add_argument("--definitions", nargs="+", type=Path)
        sub.add_argument("--profiles", type=Path)
        sub.add_argument("--poster", action="append", default=[])
        sub.add_argument("--category", action="append", default=[])
        sub.add_argument("--language", action="append", default=[])
        sub.add_argument("--snapshot", type=Path)
        sub.add_argument("--policy", choices=["partial", "strict", "audit", "review"], default="audit" if name == "preflight" else "review")
        sub.add_argument("--report", type=Path)
        if name == "preview":
            sub.add_argument("--variant", action="append", default=[])
            sub.add_argument("--high-risk", action="store_true")
            sub.add_argument("--representatives", type=int, default=0)
            sub.add_argument("--workers", type=int, default=2)
    sub = commands.add_parser("translation-delta")
    sub.add_argument("--before", type=Path, required=True)
    sub.add_argument("--after", type=Path, required=True)
    sub.add_argument("--preflight", type=Path)
    sub.add_argument("--invalidate", action="store_true")
    sub.add_argument("--generate", action="store_true")
    sub.add_argument("--workers", type=int, default=2)
    sub = commands.add_parser("overlays")
    sub.add_argument("--group", action="append", default=[])
    sub.add_argument("--size", action="append", choices=["standard", "bigger"])
    sub.add_argument("--source", action="append", default=[])
    sub.add_argument("--audit", action="store_true")
    sub.add_argument("--workers", type=int, default=2)
    sub.add_argument("--report", type=Path)
    sub.add_argument("--review", action="store_true")
    sub = commands.add_parser("review")
    sub.add_argument("action", choices=["ingest", "list", "batch", "approve", "reject", "comment", "reopen", "approve-group", "export"])
    sub.add_argument("--preflight", type=Path)
    sub.add_argument("--id", action="append", default=[])
    sub.add_argument("--state", action="append", default=[])
    sub.add_argument("--inspected", action="append", default=[])
    sub.add_argument("--scope", default="explicit CLI selection")
    sub.add_argument("--version", type=int)
    sub.add_argument("--reviewer")
    sub.add_argument("--comment", default="")
    sub.add_argument("--accept-warning", action="append", default=[])
    sub.add_argument("--membership")
    sub.add_argument("--report", type=Path)


def source(config, snapshot_path=None, *, languages=None, definitions=()):
    from .languages import LanguageSnapshot, local_snapshot, translations_from_snapshot
    from .translations import Translations
    sources = None if snapshot_path else {p.stem: p for p in config.translation_dir.glob("*.yml")}
    registry = LanguageSnapshot.load(snapshot_path) if snapshot_path else local_snapshot(sources)
    if languages is not None:
        selected = set(registry.select(languages or ["all"]))
        if registry.record("en"):
            selected.add("en")
        for definition in definitions:
            value = definition.data
            captions = [value["caption"]] + [o["changes"].get("caption", {}) for o in value["overrides"]]
            for caption in captions:
                fallback = caption.get("fallback")
                if fallback and fallback.get("language") and registry.record(fallback["language"]):
                    selected.add(fallback["language"])
    else:
        selected = None
    if snapshot_path:
        return registry, translations_from_snapshot(registry, config.cache_dir / "translations", languages=sorted(selected) if selected is not None else None)
    return registry, Translations({code: path for code, path in sources.items() if selected is None or code in selected}, tolerant=True)


def execute(args, config):
    from .state import Store
    from .review import Reviews
    from .workers import WorkerLimits
    command = args.command
    if command == "refresh-translations":
        from .languages import REPOSITORY, refresh
        from .remote import ReadOnlyGitHub
        if config.offline:
            raise BulkError("invalid_config", "Explicit refresh is unavailable in offline mode")
        registry, metrics = refresh(config.cache_dir / "translations", ReadOnlyGitHub(REPOSITORY, token=os.getenv(args.token_env)))
        result = {"registry": registry.data, "metrics": metrics}
    elif command in {"preflight", "preview", "propose-layout"}:
        from .catalog import load_catalog
        from .definitions import load_definitions
        from .generators import GENERATORS
        from .preflight import preflight
        definitions = load_definitions(args.definitions, profiles_path=args.profiles) if args.definitions else load_catalog(args.category, posters=args.poster)
        registry, translations = source(config, args.snapshot, languages=args.language or ["all"], definitions=definitions)
        options = dict(config=config, generators=GENERATORS, categories=args.category, posters=args.poster, languages=args.language or ["all"], registry=registry)
        if command == "preflight":
            result, _ = preflight(definitions, translations, policy=args.policy, **options)
        elif command == "propose-layout":
            from .services import propose_layout
            if len(definitions) != 1 or len(args.language) != 1:
                raise BulkError("invalid_selection", "Layout proposal requires one definition and one language")
            result = propose_layout(definitions[0], translations, args.language[0], config)
        else:
            from .services import preview
            result = preview(definitions, translations, reviews=Reviews(Store(config.cache_dir / "state.sqlite"), config), explicit=args.variant,
                             high_risk=args.high_risk, representatives=args.representatives, limits=WorkerLimits(workers=args.workers), **options)
    elif command == "translation-delta":
        from .delta import affected_variants, translation_delta
        before, old = source(config, args.before)
        after, new = source(config, args.after)
        result = translation_delta(old, new, old_registry=before, new_registry=after)
        if args.preflight:
            result["affected"] = affected_variants(result, json.loads(args.preflight.read_text(encoding="utf-8")))
        if args.invalidate:
            reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
            result["invalidated"] = reviews.invalidate_keys([(c["language"], c["key"]) for c in result["changes"]], reason=result["sha256"], languages=result["removed_languages"] + result["mapping_changes"], resources=result["availability_changes"])
        if args.generate:
            from .catalog import load_catalog
            from .delta import regenerate
            from .generators import GENERATORS
            if not args.preflight:
                raise BulkError("invalid_selection", "Selective generation requires the previous pinned preflight report")
            previous = json.loads(args.preflight.read_text(encoding="utf-8"))
            identities = sorted({v["poster_id"] for v in previous["variants"]})
            result["generation"] = regenerate(result, previous, load_catalog(posters=identities), new, registry=after,
                reviews=Reviews(Store(config.cache_dir / "state.sqlite"), config), config=config, generators=GENERATORS, limits=WorkerLimits(workers=args.workers))
            result["status"] = result["generation"]["status"]
    elif command == "overlays":
        from .overlays import generate
        result = generate(config, groups=args.group, sizes=args.size or ("standard", "bigger"), sources=args.source, limits=WorkerLimits(workers=args.workers), audit=args.audit)
        if args.review:
            Reviews(Store(config.cache_dir / "state.sqlite"), config).attach(result)
    else:
        reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
        if args.preflight:
            report = json.loads(args.preflight.read_text(encoding="utf-8"))
            reviews.ingest(report)
        if args.action == "ingest":
            if not args.preflight:
                raise BulkError("invalid_selection", "Review ingest requires preflight report")
            result = {"ingested": len(report["variants"])}
        elif args.action == "list":
            result = reviews.query(args.state)
        elif args.action == "batch":
            result = reviews.batch(args.id, scope=args.scope, inspected=args.inspected)
        elif args.action == "export":
            result = reviews.export()
        else:
            if len(args.id) != 1 or not args.reviewer:
                raise BulkError("invalid_selection", "One exact item/batch ID and reviewer required")
            if args.action == "approve-group":
                result = reviews.approve_group(args.id[0], membership=args.membership, reviewer=args.reviewer, comment=args.comment)
            else:
                if args.version is None:
                    raise BulkError("invalid_selection", "Expected version is mandatory for concurrent decisions")
                result = reviews.decide(args.id[0], expected_version=args.version, reviewer=args.reviewer, action=args.action, accepted_warnings=args.accept_warning, comment=args.comment)
    if getattr(args, "report", None):
        atomic_bytes(args.report, canonical(result) + b"\n")
    return result, EXITS.get(result.get("status"), 0) if isinstance(result, dict) else 0
