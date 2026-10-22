"""Build a proposed dependency state from actual, contract-checked Playlist jobs."""

from ...common import BulkError, fingerprint
from ..playlist.validation import VARIANT
from .graph import Snapshot, node_id
from .validation import validate_candidate, boundary


def graph_for_candidate(resolution,manifest,identity,translations,*,baseline=None,authority=None,fixture_only=False,
                        config=None,content=None,assigned_identity=None):
    """Patch selected output facts into a complete previous snapshot, read-only.

    This calls the real resolver/planner validation, not a caller's approval
    dictionary. Changed shared asset nodes also affect unselected dependents.
    Missing old scope is explicit; a scoped graph cannot claim library coverage.
    Historical receipts and prior snapshots remain unchanged.
    """
    reports = {}
    for key in {j["poster_id"] for j in manifest["jobs"]}:
        reports[key] = validate_candidate(resolution,manifest,key,translations,authority=authority,
            fixture_only=fixture_only,config=config,content=content if key == identity else None,
            assigned_identity=assigned_identity if key == identity else None)
    if identity not in reports:
        raise BulkError("m5_membership","Requested candidate is absent from the final manifest")
    value = baseline.data() if baseline else {"schema_version":1,"kind":"m5-dependency-snapshot",
        "basis":fingerprint({"manifest":manifest["sha256"],"contract":reports[identity]["contract_sha256"]}),
        "nodes":{},"outputs":{},"unresolved":["Scoped candidate graph; complete library baseline was not supplied"]}
    nodes,outputs=value["nodes"],value["outputs"]
    resolved=resolution.data()
    reference=boundary()
    def put(kind,key,checksum,deps=()):
        name=node_id(kind,key)
        nodes[name]={"kind":kind,"identity":key,"sha256":checksum,"dependencies":sorted(set(deps))}
        return name
    for job in manifest["jobs"]:
        key=job["poster_id"]
        definition=resolution.definition(key)
        if baseline is not None and key not in outputs:
            # M5 may describe a prospective item, never accept a lifecycle ADD.
            if assigned_identity is None or assigned_identity.to_dict()["id"] != key:
                raise BulkError("m5_identity","New output needs externally assigned stable identity")
        deps=[put("asset",a["path"],a["sha256"]) for a in job["inputs"]]
        if job["dependencies"]:
            raise BulkError("m5_unsupported_dependency","Playlist v1 has no generated-parent variant")
        provenance=resolved["provenance"][key]
        origins=[put("row",provenance["file"]+"#"+key,provenance["row_sha256"])]
        if provenance["profile"]:
            origins.append(put("profile",provenance["profile_file"]+"#"+provenance["profile"]+"#"+key,provenance["inherited_sha256"]))
        deps.append(put("definition",key,fingerprint(definition),origins))
        deps.append(put("transform","poster",fingerprint(manifest["renderer"])))
        deps.append(put("rules","Playlist/"+VARIANT+"/review-only",reports[key]["contract_sha256"]))
        deps.append(put("background",key,fingerprint({"color":job["parameters"]["base_color"],"assignment":job["color_assignment"]})))
        for trace in job["translation"]["trace"]:
            deps.append(put("caption",trace["language"]+"/"+trace["key"],fingerprint(trace)))
        # Existing individually accepted departures stay exact per M3. New
        # exception application is deliberately not inferred from metadata.
        existing=reference.record(key).to_dict() if key in {r.to_dict()["identity"]["id"] for r in reference.records} else None
        exceptions=existing["historical_exceptions"] if existing else []
        for exception in exceptions:
            deps.append(put("exception",key+"/"+exception["code"],exception["evidence_sha256"]))
        item=existing["identity"] if existing else assigned_identity.to_dict()
        context=fingerprint({"identity":item,"definition":definition,"job":job,
            "exceptions":exceptions,"renderer":fingerprint(manifest["renderer"])})
        node=put("output",key,context,deps)
        prior=outputs.get(key)
        # Preserve prior evidence as references needing comparison/re-review;
        # never manufacture approvals for the new context.
        evidence=prior["evidence"] if prior else {f:[] for f in ("previews","confirmations","decisions","receipts")}
        outputs[key]={"node":node,"category":"Playlist","kind":"poster","variant":job["variant"],
            "local_path":job["local_relative"],"public_path":job["remote_relative"],"companions":[],
            "context_sha256":context,"evidence":evidence}
    return Snapshot.create(value),reports
