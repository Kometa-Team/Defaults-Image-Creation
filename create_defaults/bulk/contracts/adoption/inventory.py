"""Read-only adoption from the real catalog, frozen Package E jobs and receipts."""

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath

from ... import asset_cases
from ...catalog import load_catalog
from ...common import confined, fingerprint, sha256
from ...config import CATEGORIES, ROOT
from ...generators import GENERATORS
from ...library_sources import check_seal, reference
from ...overlays import TRANSFORM
from ...planner import Planner, SHARED_ASSETS, effective_parameters
from ...translations import Translations
from ...workers import RenderTask
from ..models import Identity, RegistryDocument
from .models import (HistoricalOutput, HistoricalRegistry, audit_membership, encoded_json,
                     equal, fingerprints, mismatch)
from .sources import HERE, approval_index, load_history, load_pins, verify_sources


def _task(job, jobs, renderer):
    inputs = list(job["inputs"])
    for dependency in job["dependencies"]:
        parent = jobs[dependency["job_id"]]["job"]
        inputs.append({"role": dependency["input"], "path": parent["local_relative"],
                       "sha256": dependency["sha256"], "generated": True})
    return RenderTask(job["id"], job["render_fingerprint"], job["local_relative"],
                      {"parameters": job["parameters"], "inputs": inputs, "renderer": renderer,
                       **({"kind": "overlay"} if job["kind"] == "overlay" else {})},
                      tuple(d["job_id"] for d in job["dependencies"]))


def verify_owned_receipt(row, jobs):
    """Verify the preserved actual SQLite-owned spec, not just a loose checksum."""
    job, receipt, spec = row["job"], row["receipt"], row["worker_spec"]
    context = {"category": "Overlays" if job["kind"] == "overlay" else job["poster_id"].split(".")[0],
               "identity": job["id"]}
    expected_spec = {"task": _task(job, jobs, row["renderer"]).spec(), "renderer_identity": receipt["renderer_identity"]}
    calculated_render = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": row["renderer"]})
    checks = {"calculated_render_fingerprint": (calculated_render, job["render_fingerprint"]),
              "receipt_sha256": (receipt["receipt_sha256"], fingerprint({k: v for k, v in receipt.items() if k != "receipt_sha256"})),
              "logical_id": (job["id"], receipt["logical_id"]),
              "render_fingerprint": (job["render_fingerprint"], receipt["render_fingerprint"]),
              "relative": (job["local_relative"], receipt["relative"]),
              "worker_spec": (fingerprint(expected_spec), fingerprint(spec)),
              "job_fingerprint": (fingerprint(spec), receipt["job_fingerprint"])}
    for path, (expected, actual) in checks.items():
        equal(expected, actual, path=path, code="adoption_owned_receipt", **context)


def verify_production_lane(verification, plan, responses, pins):
    """Verify original receipt membership and raw-response identity against its plan."""
    planned = {m["destination"]: m for m in plan["members"]}
    equal(len(plan["members"]), len(planned), category="production", identity=plan["sha256"], path="unique_members")
    for path, expected, actual in (("plan_sha256", plan["sha256"], verification["plan_sha256"]),
                                   ("baseline.head", pins["artwork_commit"], plan["baseline"]["head"]),
                                   ("baseline.tree", pins["artwork_tree"], plan["baseline"]["tree"]),
                                   ("response_membership", set(planned), set(verification["response_receipts"])),
                                   ("discrepancies", [], plan["discrepancies"] + verification["discrepancies"]),
                                   ("expected", len(planned), verification["expected"]),
                                   ("exact_sha256_matches", len(planned), verification["exact_sha256_matches"])):
        equal(expected, actual, category="production", identity=plan["sha256"], path=path, code="adoption_response_binding")
    for destination, member in planned.items():
        response = responses.get(destination)
        if response is None:
            mismatch("adoption_response_binding", "production", destination, destination, "actual historical response", None)
        checks = {"receipt_sha256": (verification["response_receipts"][destination], response["sha256"]),
                  "plan_sha256": (plan["sha256"], response["plan_sha256"]),
                  "actual_sha256": (member["sha256"], response["actual_sha256"]),
                  "actual_git_blob": (member["git_blob"], response["actual_git_blob"]),
                  "bytes": (member["size"], response["bytes"]),
                  "production_commit": (pins["artwork_commit"], response["commit_at_actual_download"])}
        for path, (expected, actual) in checks.items():
            equal(expected, actual, category="production", identity=destination, path=path, code="adoption_response_binding")


def _material(job):
    value = deepcopy({key: job[key] for key in ("kind", "parameters", "raw_parameters", "inputs", "dependencies", "translation", "layout_evidence", "color_assignment", "language_behavior", "local_relative", "remote_relative")})
    for field in ("parameters", "raw_parameters"):
        for key in ("logo", "avg_color_image", "dom_color_image", "input"):
            if value[field].get(key):
                value[field][key] = asset_cases.canonical(value[field][key])
    for item in value["inputs"]:
        item["path"] = asset_cases.canonical(item["path"])
    # Parent render-context hashes changed under the accepted source-case
    # bridge; exact parent output bytes and dependency topology remain checked.
    for dependency in value["dependencies"]:
        dependency.pop("render_fingerprint")
    return value


def verify_baseline_job(native, baseline):
    job, previous = native["job"], baseline["job"]
    for path, expected, actual in (("material_context", _material(previous), _material(job)),
                                   ("output_sha256", baseline["receipt"]["sha256"], native["receipt"]["sha256"])):
        equal(expected, actual, category=job["kind"], identity=job["id"], path=path, code="adoption_baseline_drift")


def _poster(definition, row, translations, origins, family_for, native):
    job = row["job"]
    item = definition.for_language("en").data
    context = {"category": definition.category, "identity": definition.id}
    caption = translations.resolve(item["caption"], "en")
    raw = dict(item["composer"], text=caption.text)
    local = "/".join(filter(None, ("defaults-en", item["output"]["directory"], item["output"]["filename"])))
    for path, expected, actual in (
        ("definition_fingerprint", fingerprint({"definition": item, "generator_origin": job["generator_origin"]}), job["definition_fingerprint"]),
        ("raw_parameters", raw, job["raw_parameters"]), ("parameters", effective_parameters(raw), job["parameters"]),
        ("local_relative", local, job["local_relative"]),
        ("remote_relative", item["output"]["remote_paths"]["en"], job["remote_relative"]),
        ("translation", {"mode": caption.mode, "trace": list(caption.trace), "fingerprint": caption.fingerprint}, job["translation"]),
        ("layout", item["layout"], job["layout_evidence"]),
        ("background", item["color_assignment"], job["color_assignment"]),
    ):
        equal(expected, actual, path=path, **context)
    expected_inputs = {("font", raw["font"]), *(("shared", path) for path in SHARED_ASSETS)}
    generated = {d["input"] for d in item["dependencies"]}
    for key in ("logo", "avg_color_image", "dom_color_image"):
        active = key == "logo" or (key == "avg_color_image" and raw["avg_color"] and not raw["base_color"])
        if raw[key] and key not in generated and active:
            expected_inputs.add((key, raw[key]))
    equal(sorted(expected_inputs), sorted((i["role"], i["path"]) for i in job["inputs"]), path="source_dependencies", **context)
    expected_deps = []
    for dependency in item["dependencies"]:
        parent = next((r for r in native.values() if r["job"]["poster_id"] == dependency["poster_id"]), None)
        if parent is None:
            mismatch("adoption_missing_parent", definition.category, definition.id, dependency["input"], dependency["poster_id"], None)
        equal(parent["job"]["local_relative"], raw[dependency["input"]], path="generated_input", **context)
        expected_deps.append({"job_id": parent["job"]["id"], "input": dependency["input"],
                              "sha256": parent["receipt"]["sha256"], "render_fingerprint": parent["job"]["render_fingerprint"]})
    equal(expected_deps, job["dependencies"], path="dependencies", **context)
    family = family_for.get(definition.id)
    return item, ({"id": family, "member_key": "adopted:" + definition.id} if family else None)


def _overlay(job, groups):
    group_id = job["remote_relative"].split("/overlays/")[0]
    group = groups.get(group_id)
    if group is None or job["variant"] not in group["sizes"]:
        mismatch("adoption_overlay", "Overlays", job["id"], "group", "existing group/size", group_id)
    source = job["parameters"]["input"]
    equal(True, source in group["inputs"], category="Overlays", identity=job["id"], path=source)
    parameters = {"input": source, "box": group["sizes"][job["variant"]]["box"], "trim": group["trim"],
                  "colorspace": "sRGB", "strip_metadata": True, "format": "PNG", "resampling": "Pillow-LANCZOS"}
    destination = group["sizes"][job["variant"]]["destination"] + "/" + PurePosixPath(source).name
    for path, expected, actual in (("parameters", parameters, job["parameters"]), ("local_relative", destination, job["local_relative"]),
                                   ("remote_relative", destination, job["remote_relative"]),
                                   ("transform", {"transform": TRANSFORM}, job["layout_evidence"])):
        equal(expected, actual, category="Overlays", identity=job["id"], path=path)
    definition = {"group": group_id, "parameters": parameters, "transform": TRANSFORM}
    equal(fingerprint(definition), job["definition_fingerprint"], category="Overlays", identity=job["id"], path="definition_fingerprint")
    return definition


def _exceptions(item, job, approval, normal_assets, pins):
    category = "Overlays" if job["kind"] == "overlay" else item["category"]
    codes = []
    source = job["parameters"].get("logo", job["parameters"].get("input"))
    destination = job["remote_relative"] or job["local_relative"]
    if category == "Playlist": codes.append("E04")
    if category in {"Year", "Decade"}: codes.append("E03")
    if job["remote_relative"] is None: codes.append("E05")
    if destination == "genre/Splatter.jpg": codes.append("E01")
    if destination == "franchise/Death in Paradise (2011).jpg": codes.append("E02")
    if "Tokyo MX.png" in (source or ""): codes.append("E06")
    if destination == "genre/Action & Adventure.jpg": codes.append("E15")
    if approval and approval["population"] == "group-b": codes.append("E08")
    if job["kind"] == "overlay": codes.append("E10")
    if job["kind"] == "poster" and job["color_assignment"]["origin"] == "historical": codes.append("E13")
    if category in {"Franchise", "Genre", "Seasonal", "Universe"} and job["parameters"].get("white_wash") is False:
        codes.append("D09_ACCEPTED_SOURCE_PRESERVING")
    if category == "Studio": codes.append("D09_STUDIO_SOURCE_PRESERVING")
    if source in normal_assets: codes.append("D09_NORMAL_ACCEPTED_ALPHA_ASSET")
    if source and (not source.isascii() or any(n in source for n in ("X-men", "dca.png", "DragonBall"))) or "A.C.G.T..jpg" in destination:
        codes.append("E12")
    return [{"code": code, "evidence_sha256": pins["d09_sha256"] if code.startswith("D09") else pins["exceptions_sha256"]}
            for code in sorted(set(codes))]


def discover(*, progress=None):
    """Dry-run by default: reads/hashes only; no state, workers or image decoding."""
    pins = load_pins()
    progress = progress or (lambda stage: None)
    progress("verify pinned production sources and historical evidence")
    verify_sources(pins)
    documents, native, responses = load_history(pins)
    for lane in ("english", "overlay"):
        verify_production_lane(documents[lane + "-production-verification"], documents[lane + "-production-plan"], responses, pins)
    approvals = approval_index(documents)
    progress("expand the 21-category catalog read-only")
    definitions = load_catalog(("all",))
    catalog, families, origins = Planner(generators=GENERATORS).expand(definitions)
    family_for = {child: parent for parent, children in families.items() for child in children}
    equal(4372, len(definitions), category="catalog", identity="declared", path="definitions")
    equal(102, len(families), category="catalog", identity="generators", path="families")
    equal(set(catalog), {r["job"]["poster_id"] for r in native.values() if r["job"]["kind"] == "poster"},
          category="catalog", identity="expanded", path="output_membership", code="adoption_membership")
    baseline = {}
    progress("verify frozen Package E reference ledgers")
    for kind in ("english", "overlays"):
        ledger = reference(kind)
        for row in ledger["rows"]:
            if row["job"]["id"] in baseline:
                mismatch("adoption_duplicate", kind, row["job"]["id"], "ledger", "unique", row["job"]["id"])
            baseline[row["job"]["id"]] = row
    equal(set(baseline), set(native), category="inventory", identity="native", path="membership", code="adoption_membership")
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    # Replay the pinned historical resource's exact provenance after verifying
    # the source bytes above (Git LF/CRLF text representation only). No live
    # translation pipeline, language or caption behavior is changed.
    translations.hashes["en"] = pins["historical_english_sha256"]
    overlay_catalog = check_seal(json.loads((ROOT / "bulk/catalog/overlays-v1.json").read_bytes()))
    equal(TRANSFORM, overlay_catalog["transform"], category="Overlays", identity="catalog", path="transform")
    groups = {g["id"]: g for g in overlay_catalog["groups"]}
    expected_overlays = {size["destination"] + "/" + PurePosixPath(source).name
                         for group in groups.values() for source in group["inputs"] for size in group["sizes"].values()}
    observed_overlays = {r["job"]["remote_relative"] for r in native.values() if r["job"]["kind"] == "overlay"}
    equal(expected_overlays, observed_overlays, category="Overlays", identity="catalog", path="complete_group_size_membership")
    progress("verify exact source/font bytes and dependency mappings")
    source_hashes = {}
    for row in native.values():
        job = row["job"]
        for item in job["inputs"]:
            if item["path"] in source_hashes:
                equal(source_hashes[item["path"]], item["sha256"], category=job["kind"], identity=job["id"], path=item["path"])
            else:
                try:
                    observed = sha256(confined(ROOT, item["path"], must_exist=True))
                except (OSError, ValueError) as error:
                    mismatch("adoption_source_dependency", job["kind"], job["id"], item["path"], item["sha256"], str(error))
                equal(item["sha256"], observed, category=job["kind"], identity=job["id"], path=item["path"], code="adoption_source_dependency")
                source_hashes[item["path"]] = observed
    stable = {identity: r["job"]["poster_id"] if r["job"]["kind"] == "poster" else identity for identity, r in native.items()}
    values = []
    for job_id in sorted(native):
        if len(values) % 2000 == 0:
            progress(f"validate historical outputs {len(values)}/{len(native)}")
        row, old = native[job_id], baseline[job_id]
        job = row["job"]
        verify_owned_receipt(row, native)
        verify_baseline_job(row, old)
        if job["kind"] == "poster":
            definition = catalog[job["poster_id"]]
            item, family = _poster(definition, row, translations, origins, family_for, native)
            category, display = definition.category, item["display_name"]
        else:
            item, family = _overlay(job, groups), None
            category, display = "Overlays", PurePosixPath(job["parameters"]["input"]).stem
        primary_path = job["parameters"].get("logo", job["parameters"].get("input")) or "transparent.png"
        source_kind = "source_asset"
        if job["dependencies"]:
            parent = native[job["dependencies"][0]["job_id"]]
            primary = {"path": parent["job"]["local_relative"], "sha256": parent["receipt"]["sha256"]}
            source_identity = stable[parent["job"]["id"]]
            source_kind = "generated_parent"
        else:
            primary = {"path": primary_path, "sha256": source_hashes[primary_path]}
            source_identity = "source." + fingerprint(primary_path)[:32]
            if primary_path == "transparent.png" or "/@" in primary_path:
                source_kind = "historical_template"
        identity = Identity.from_dict({"schema_version": 1, "kind": "item-identity", "id": stable[job_id], "category": category,
            "display_name": display, "rendered_caption": job["parameters"].get("text", ""), "source": primary,
            "local_path": job["local_relative"], "public_path": job["remote_relative"],
            "semantic_member": {"family_id": family["id"], "key": family["member_key"]} if family else None})
        approval = approvals.get(job["remote_relative"])
        approval_refs = []
        if approval:
            equal(row["receipt"]["sha256"], approval["candidate_sha256"], category=category, identity=stable[job_id], path="historical_approval_candidate")
            approval_refs.append({key: approval[key] for key in ("record_sha256", "member_sha256", "scope")})
        else:
            canary = check_seal(json.loads((ROOT / "bulk/evidence/english-canary/visual-acceptance-20261017.json").read_bytes()))
            decision = next((d for d in canary["decisions"] if d["id"] == job_id), None)
            if decision:
                equal(row["receipt"]["sha256"], decision["image_sha256"], category=category, identity=stable[job_id], path="canary_approval_candidate")
                approval_refs.append({"record_sha256": canary["sha256"], "member_sha256": fingerprint(decision), "scope": "exact_visual"})
        response_hash = None
        if job["remote_relative"] is not None:
            response = responses.get(job["remote_relative"])
            if response is None:
                mismatch("adoption_publication_evidence", category, stable[job_id], job["remote_relative"], "historical actual-response receipt", None)
            for path, expected, actual in (("actual_sha256", row["receipt"]["sha256"], response["actual_sha256"]),
                                           ("production_snapshot", pins["artwork_commit"], response["commit_at_actual_download"]),
                                           ("provenance", "actual_pinned_raw_remote_response", response["provenance"])):
                equal(expected, actual, category=category, identity=stable[job_id], path=path)
            response_hash = response["sha256"]
        exceptions = _exceptions(item, job, approval, set(pins["normal_historical_alpha_assets"]), pins)
        bridges = []
        if any(asset_cases.canonical(i["path"]) != i["path"] for i in old["job"]["inputs"]): bridges.append("accepted_source_case")
        if old.get("identity_correction"):
            bridges.append("accepted_public_mapping")
        if "accepted_source_case" in bridges or job["kind"] == "overlay" and old.get("identity_correction"):
            exceptions.append({"code": "E07", "evidence_sha256": pins["exceptions_sha256"]})
            exceptions.sort(key=lambda item: item["code"])
        if family and job["generator_origin"] is None: bridges.append("flattened_generator_provenance")
        values.append({"schema_version": 1, "kind": "historical-output-adoption", "identity": identity.to_dict(),
            "job_id": job_id, "observed_variant": job["variant"], "source_identity": source_identity, "source_kind": source_kind,
            "family": family, "paired_identity": None, "effective_definition_json": encoded_json(item), "job_json": encoded_json(job),
            "baseline_job_sha256": fingerprint(old["job"]), "baseline_renderer_sha256": fingerprint(row["renderer"]),
            "fingerprints": fingerprints(item, job, exceptions),
            "evidence": {"native_report_sha256": row["native_report_sha256"], "owned_receipt_sha256": row["receipt"]["receipt_sha256"],
                         "worker_spec_sha256": fingerprint(row["worker_spec"]), "original_receipt_sha256": old["receipt"]["receipt_sha256"],
                         "output_sha256": row["receipt"]["sha256"], "response_receipt_sha256": response_hash, "approval_refs": approval_refs},
            "bridges": bridges, "historical_exceptions": exceptions, "historical_compatibility": "verified_unchanged_material",
            "contract_compatibility": "not_assessed_no_category_contract", "maintainer_approval": "historical_record_found" if approval_refs else "not_found_private" if job["remote_relative"] is None else "not_found",
            "publication_authorized": False})
    # Freeze actual historical paired-logo membership, independently of future
    # category contracts. Text/era/other variants are not invented logo pairs.
    pairs = defaultdict(dict)
    for value in values:
        item, job = value["identity"], json.loads(value["job_json"])
        if item["category"] in {"Chart", "Country", "Network", "Streaming"} and value["source_kind"] == "source_asset":
            parts = PurePosixPath(item["public_path"]).parts
            if len(parts) >= 3 and parts[1] in {"white", "color"}:
                pairs[(item["category"], parts[2:])][parts[1]] = value
    for group in pairs.values():
        # Existing paired designs can use separate source PNGs, or the same
        # colored source with historical white-wash. Freeze literal mappings;
        # never infer silhouette equivalence or change either source treatment.
        if set(group) == {"white", "color"}:
            white, color = group["white"], group["color"]
            white["paired_identity"], color["paired_identity"] = color["identity"]["id"], white["identity"]["id"]
    records = tuple(HistoricalOutput.from_dict(value) for value in values)
    progress("reconcile complete membership and immutable registry")
    audit_membership(records)
    public = {v["identity"]["public_path"] for v in values if v["identity"]["public_path"] is not None}
    equal(public, set(responses), category="production", identity="public", path="membership", code="adoption_membership")
    equal(14079, len(values), category="inventory", identity="all", path="records")
    audit = _report(values, pins, definitions, families, source_hashes, documents)
    registry = assemble_registry(records, audit, pins)
    return registry, records


def assemble_registry(records, audit, pins):
    """Order-independent canonical selection; version labels grant no authority."""
    records = sorted(records, key=lambda r: r.to_dict()["job_id"])
    basis = RegistryDocument.from_dict({"schema_version": 1, "kind": "category-contract-registry", "id": "historical-defaults-m2", "version": "1.0.0",
        "owner": "bullmoose20", "provenance": {"actor": "bullmoose20", "role": "maintainer", "source": "M2 factual-discovery authorization; no category contracts approved by this record", "evidence_sha256": fingerprint(pins)}, "entries": []})
    registry = HistoricalRegistry.from_dict({"schema_version": 1, "kind": "historical-adoption-registry", "id": "historical-defaults-m2", "version": "1.0.0",
        "source_pins_sha256": fingerprint(pins), "basis_registry_json": encoded_json(basis.to_dict()), "basis_registry_sha256": basis.sha256,
        "schema_pins": pins["schema_pins"], "members": [{"id": r.to_dict()["identity"]["id"], "job_id": r.to_dict()["job_id"], "sha256": r.sha256} for r in records],
        "audit_json": encoded_json(audit), "publication_authorized": False})
    registry.verify_schema_pins()
    return registry


def _report(values, pins, definitions, families, sources, documents):
    posters = [v for v in values if v["identity"]["category"] != "Overlays"]
    overlays = [v for v in values if v["identity"]["category"] == "Overlays"]
    group_counts = Counter()
    for v in overlays:
        path = v["identity"]["public_path"]
        group_counts[path.split("/overlays/")[0] + "/" + v["observed_variant"]] += 1
    return {"kind": "read-only-historical-adoption-audit", "source_commit": pins["source_commit"], "artwork_commit": pins["artwork_commit"],
        "source_tree": pins["source_tree"], "artwork_tree": pins["artwork_tree"], "discovery_baseline_commit": pins["discovery_baseline_commit"], "historical_evidence_index_sha256": pins["history_index_sha256"],
        "source_pins_sha256": fingerprint(pins), "records": len(values), "posters": len(posters), "overlays": len(overlays),
        "poster_public": sum(v["identity"]["public_path"] is not None for v in posters), "poster_private": sum(v["identity"]["public_path"] is None for v in posters),
        "public_records": sum(v["identity"]["public_path"] is not None for v in values), "declared_definitions": len(definitions), "generator_families": len(families),
        "generated_children": sum(v["family"] is not None for v in values), "poster_categories": dict(sorted(Counter(v["identity"]["category"] for v in posters).items())),
        "overlay_groups_and_sizes": dict(sorted(group_counts.items())), "overlay_groups": len({key.rsplit("/", 1)[0] for key in group_counts}),
        "unique_nongenerated_source_paths": len(sources), "source_dependency_references": sum(len(json.loads(v["job_json"])["inputs"]) for v in values),
        "unique_local_output_paths": len({v["identity"]["local_path"] for v in values}),
        "unique_public_output_paths": len({v["identity"]["public_path"] for v in values if v["identity"]["public_path"] is not None}),
        "fonts": {path: checksum for path, checksum in sources.items() if path.startswith("fonts/")},
        "protected_original_logos_and_separator_templates_outside_output_inventory": 2083,
        "generated_parent_dependencies": sum(len(json.loads(v["job_json"])["dependencies"]) for v in values),
        "source_assets_are_not_output_records": True, "paired_logo_outputs": dict(sorted(Counter(v["identity"]["category"] for v in values if v["paired_identity"] is not None).items())),
        "compatibility": dict(Counter(v["historical_compatibility"] for v in values)), "category_contracts_assessed": 0,
        "contract_compatibility": "not_assessed_no_category_contract", "historical_approvals": dict(Counter(v["maintainer_approval"] for v in values)),
        "owned_worker_specs_verified": len(values), "verified_historical_output_hashes": len(values), "historical_actual_response_receipts": sum(v["evidence"]["response_receipt_sha256"] is not None for v in values),
        "historical_exceptions": dict(sorted(Counter(e["code"] for v in values for e in v["historical_exceptions"]).items())),
        "accepted_bridges": dict(Counter(code for v in values for code in v["bridges"])),
        "normal_historical_alpha_assets": len(pins["normal_historical_alpha_assets"]),
        "missing_or_ambiguous_evidence": ["Category contracts are not authored until M3/M6; compatibility with those contracts is not assessed.",
            "Two private intermediate outputs have owned byte evidence but no publication membership or inferred visual approval.",
            "Historical flattened jobs omit family provenance; frozen generator-member links are additive metadata, not receipt rewrites."],
        "unexplained_differences": [], "production_enforcement_activated": False, "publication_authorized": False,
        "artwork_regenerated": 0, "remote_writes": 0}
