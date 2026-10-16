"""Inactive production entry point: staged plans and a single persistent pool."""

from .common import BulkError, confined, fingerprint, path_key, sha256
from .config import Config, select_categories
from .planner import Planner, validate_manifest
from .state import Store
from .workers import PersistentWorkers, WorkerLimits, tasks_from_manifest


def generate(definitions, translations, *, config=None, limits=None, generators=None,
             categories=(), posters=(), languages=("en",), cancel=None, retry_failed=False):
    config = config or Config()
    planner = Planner(config, generators=generators, scope="Package C local poster plan; overlays, multilingual approval and publication are not included")
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
            value = catalog[identity].for_language(language).data
            if value["applicability"].get(language, {}).get("status") == "not_applicable":
                continue
            local = "/".join(filter(None, ("defaults-" + language, value["output"]["directory"], value["output"]["filename"])))
            key = path_key(local)
            remote = value["output"]["remote_paths"].get(language)
            if key in destinations or (remote is not None and path_key(remote) in remote_destinations):
                raise BulkError("output_collision", "Conflicting active output paths across dependency stages")
            destinations.add(key)
            if remote is not None:
                remote_destinations.add(path_key(remote))
    artifacts, stages, combined_jobs = {}, [], {}
    store = Store(config.cache_dir / "state.sqlite")
    with PersistentWorkers(store, config, limits or WorkerLimits()) as pool:
        for depth in sorted(set(depths.values())):
            ready = sorted(identity for identity in ordered if depths[identity] == depth)
            # plan() includes ancestors and verifies their current bytes. It
            # cannot plan children until the preceding stage has succeeded.
            manifest = planner.plan(definitions, translations, posters=ready, languages=languages, dependency_artifacts=artifacts)
            result = pool.run(tasks_from_manifest(manifest), cancel=cancel, retry_failed=retry_failed)
            stages.append({"depth": depth, "manifest": manifest, "execution": result})
            if any(item["status"] not in {"rendered", "cache_reuse", "dedup_reuse"} for item in result["jobs"].values()):
                return {"status": "incomplete", "stages": stages}
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
    return {"status": "verified", "stages": stages, "manifest": combined,
            "scope": "Local English migration execution; no publication, reviewer approval, overlays or production cutover"}
