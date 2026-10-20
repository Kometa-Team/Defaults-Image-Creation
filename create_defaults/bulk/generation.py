"""Inactive production entry point: staged plans and a single persistent pool."""

from .common import BulkError, confined, fingerprint, path_key, sha256
from .config import Config, select_categories
from .planner import Planner, validate_manifest
from .state import Store
from .workers import PersistentWorkers, WorkerLimits, tasks_from_manifest


def generate(definitions, translations, *, config=None, limits=None, generators=None,
             categories=(), posters=(), languages=("en",), cancel=None, retry_failed=False,
             policy="partial", registry=None, color_registry=None, preview_ids=None, variant_ids=None, preview_selection=None,
             cache_only=False):
    config = config or Config()
    planner = Planner(config, generators=generators, scope="Package D preflight-validated local output; rendering is not approval or publication")
    if registry is not None:
        languages = registry.select(languages)
        translations = translations.pinned_for(registry)
    catalog, families, _ = planner.expand(definitions)
    categories = select_categories(categories)
    wanted = set()
    for identity in posters:
        if identity in families:
            wanted.update(families[identity])
        elif identity in catalog:
            wanted.add(identity)
        else:
            raise BulkError("invalid_selection", "Unknown logical poster identity")
    selected = {identity for identity, item in catalog.items() if (not categories or item.category in categories) and (not posters or identity in wanted)}
    if not selected or not (categories or posters):
        raise BulkError("empty_selection", "Select categories or posters explicitly")
    ordered, visiting, depths = [], set(), {}
    def visit(identity):
        if identity in visiting:
            raise BulkError("dependency_cycle", "Cyclic generated-input dependency")
        if identity in depths:
            return depths[identity]
        if identity not in catalog:
            raise BulkError("missing_dependency", "Missing generated-input parent")
        visiting.add(identity)
        parents = catalog[identity].data["dependencies"]
        depth = max((visit(item["poster_id"]) + 1 for item in parents), default=0)
        visiting.remove(identity)
        depths[identity] = depth
        ordered.append(identity)
        return depth
    for identity in sorted(selected):
        visit(identity)
    destinations, remote_destinations = set(), set()
    for identity in ordered:
        for language in languages:
            from .preflight import effective_language
            value = effective_language(catalog[identity], language)
            if value["applicability"].get(language, {}).get("status") == "not_applicable":
                continue
            local = "/".join(filter(None, ("defaults-" + language, value["output"]["directory"], value["output"]["filename"])))
            key = path_key(local)
            remote = value["output"]["remote_paths"].get(language)
            if key in destinations or (remote is not None and path_key(remote) in remote_destinations):
                from .common import atomic_bytes, canonical
                report = {"status": "invalid_input", "code": "output_collision", "message": "Conflicting active output paths across dependency stages", "poster_id": identity, "language": language}
                path = config.workspace_dir / "preflight-errors" / (fingerprint(report) + ".json")
                if not path.exists():
                    atomic_bytes(path, canonical(report) + b"\n")
                raise BulkError("output_collision", report["message"])
            destinations.add(key)
            if remote is not None:
                remote_destinations.add(path_key(remote))
    from .preflight import ELIGIBLE, incomplete, preflight
    report, effective = preflight(definitions, translations, config=config, generators=generators, categories=categories,
        posters=posters, languages=languages, registry=registry, policy=policy, color_registry=color_registry, variant_ids=variant_ids)
    if policy == "audit" or report["status"] == "strict_blocked":
        return {"status": ("partial" if incomplete(report["coverage"]) else "audited") if policy == "audit" else "strict_blocked", "preflight": report, "stages": []}
    if preview_selection is not None:
        from .preflight import select_previews
        preview_ids = select_previews(report, **preview_selection)
        if not preview_ids:
            if incomplete(report["coverage"]):
                return {"status": "partial", "preflight": report, "stages": []}
            raise BulkError("empty_preview", "No eligible variants match the explicit preview selection; retained preflight lists blockers")
    eligible = {v["id"] for v in report["variants"] if v["status"] in ELIGIBLE}
    by_variant = {v["id"]: v for v in report["variants"]}
    needed = set()
    def include_ready(identity):
        if identity in needed:
            return
        needed.add(identity)
        for parent in by_variant[identity]["dependencies"]:
            include_ready(parent)
    for variant in report["variants"]:
        if variant["selected"] and variant["id"] in eligible:
            include_ready(variant["id"])
    eligible &= needed
    if preview_ids is not None:
        if set(preview_ids) - eligible:
            raise BulkError("blocked_preview", "Preview selection includes blocked/obsolete variants")
        selected_previews = set(preview_ids)
        by_id = {v["id"]: v for v in report["variants"]}
        def parents(identity):
            for parent in by_id[identity]["dependencies"]:
                if parent not in selected_previews:
                    selected_previews.add(parent)
                    parents(parent)
        for identity in list(selected_previews):
            parents(identity)
        eligible &= selected_previews
    if not eligible:
        return {"status": "partial" if incomplete(report["coverage"]) else "verified", "preflight": report, "stages": []}
    artifacts, stages, combined_jobs = {}, [], {}
    store = Store(config.cache_dir / "state.sqlite")
    with PersistentWorkers(store, config, limits or WorkerLimits()) as pool:
        for depth in sorted(set(depths.values())):
            for language in report["languages"]:
                from .preflight import variant_id
                ready = sorted(identity for identity in ordered if depths[identity] == depth and variant_id(identity, language) in eligible)
                if not ready:
                    continue
                scoped = tuple(value for (identity, lang), value in effective.items() if lang == language and variant_id(identity, lang) in eligible)
                # Parents are planned only after their bytes have been verified.
                manifest = planner.plan(scoped, translations, posters=ready, languages=[language], dependency_artifacts=artifacts)
                result = pool.run(tasks_from_manifest(manifest), cancel=cancel, retry_failed=retry_failed, cache_only=cache_only)
                stages.append({"depth": depth, "manifest": manifest, "execution": result})
                if any(item["status"] not in {"rendered", "cache_reuse", "dedup_reuse"} for item in result["jobs"].values()):
                    return {"status": "incomplete", "stages": stages, "preflight": report}
                for job in manifest["jobs"]:
                    previous = combined_jobs.get(job["id"])
                    if previous and previous["render_fingerprint"] != job["render_fingerprint"]:
                        raise BulkError("changed_input", "Rendering graph changed between dependency stages")
                    combined_jobs[job["id"]] = job
                    checksum = result["jobs"][job["id"]]["sha256"]
                    if sha256(confined(config.output_dir, job["local_relative"], must_exist=True)) != checksum:
                        raise BulkError("corrupt_artifact", "Parent bytes changed after verified execution")
                    artifacts[job["id"]] = checksum
    pool.workspaces.cleanup(**pool.workspace, retain_seconds=0)
    combined = dict(stages[-1]["manifest"], jobs=list(combined_jobs.values()),
                    selection={"categories": list(categories), "posters": sorted(posters), "languages": list(languages)})
    combined.pop("sha256")
    combined["sha256"] = fingerprint(combined)
    validate_manifest(combined)
    return {"status": "partial" if incomplete(report["coverage"]) else "verified", "stages": stages, "manifest": combined,
            "preflight": report, "scope": "Local validated rendering; no publication, automatic reviewer approval or production cutover"}
