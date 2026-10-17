"""English-only local canary preparation. No publication API or workflow dispatch."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
from html import escape
import json
from pathlib import Path
import subprocess
import time

from PIL import Image, ImageChops, ImageStat

from .catalog import load_catalog
from .common import BulkError, canonical, fingerprint, reject_links, sha256
from .config import ROOT
from .e_validation import configuration, ResourceGuard, save, summarize, verify
from .generation import generate
from .generators import GENERATORS
from .planner import Planner
from .preflight import preflight
from .translations import Translations
from .workers import WorkerLimits

APPROVED_COMMIT = "83ed3d1b11576f8e258aed08a3ae7ff13bf4791c"
SELECTION = {
    "based.based-book.217e49bd": "based/Book.jpg",
    "decade.decade-2020.6b12c5db": "decade/2020.jpg",
    "franchise.franchise-death-in-paradise-2011.e5339def": "franchise/Death in Paradise (2011).jpg",
    "genre.genre-action-adventure.96dd0142": "genre/Action & Adventure.jpg",
    "genre.genre-splatter.d3e4161c": "genre/Splatter.jpg",
    "year.year-2020.83bfe96a": "year/2020.jpg",
    "year.year-best-2020.85b6933b": "year/best/2020.jpg",
}
EVIDENCE = ROOT / "bulk/evidence/package-e"


def validate_scope(jobs):
    """Reject extra/missing artwork, aliases and any language or destination drift."""
    if len(jobs) != len(SELECTION) or {j["poster_id"] for j in jobs} != set(SELECTION):
        raise BulkError("canary_scope", "Canary must contain exactly the seven enumerated posters")
    destinations = set()
    for job in jobs:
        if job["kind"] != "poster" or job["language"] != "en" or job["remote_relative"] != SELECTION[job["poster_id"]]:
            raise BulkError("canary_scope", "English-only exact destination allowlist mismatch")
        if job["remote_relative"] in destinations or not job["local_relative"].startswith("defaults-en/"):
            raise BulkError("canary_scope", "Unsafe, duplicate or private canary destination")
        destinations.add(job["remote_relative"])
    child = next(j for j in jobs if j["poster_id"] == "year.year-best-2020.85b6933b")
    parent = next(j for j in jobs if j["poster_id"] == "year.year-2020.83bfe96a")
    if not child["dependencies"] or not any(d.get("job_id") == parent["id"] and d.get("sha256") for d in child["dependencies"]):
        raise BulkError("canary_dependency", "The generated Year parent/child chain is required")


def reference_rows():
    index = json.loads((EVIDENCE / "full-ledger-index.json").read_text(encoding="utf-8"))
    binding = index["evidence"]["english"]
    path = EVIDENCE / binding["path"]
    if sha256(path) != binding["file_sha256"]:
        raise BulkError("canary_reference", "Full-run reference compressed bytes changed")
    ledger = json.loads(gzip.decompress(path.read_bytes()))
    if fingerprint(ledger) != binding["payload_sha256"]:
        raise BulkError("canary_reference", "Full-run reference payload changed")
    return {r["job"]["poster_id"]: r for r in ledger["rows"] if r["job"]["poster_id"] in SELECTION}


def compare_published(root, config, rows):
    # Existing transport refuses all non-GET calls and bounds repo, bytes and time.
    from .e_network import BudgetSession, token
    from .remote import ReadOnlyGitHub, RemoteInventory
    from .state import Store
    session = BudgetSession(config.github_repository, maximum=250)
    client = ReadOnlyGitHub(config.github_repository, token=token(), session=session)
    inventory = RemoteInventory(Store(config.cache_dir / "state.sqlite"), config, client)
    refreshed = inventory.refresh()
    if refreshed["status"] != "complete":
        raise BulkError("canary_inventory", "Current published inventory must be complete")
    snapshot = refreshed["snapshot"]
    for row in rows:
        lookup = inventory.lookup(row["destination"])
        if lookup["status"] != "found":
            raise BulkError("canary_destination", "Exact existing destination required: " + row["destination"])
        current = inventory.fetch_image(row["destination"])
        with Image.open(config.output_dir / row["local_relative"]) as proposed, Image.open(current) as published:
            proposed.load(); published.load()
            if proposed.size != published.size:
                raise BulkError("canary_dimensions", "Published dimensions differ; stop for review")
            diff = ImageChops.difference(proposed.convert("RGB"), published.convert("RGB"))
            metrics = ImageStat.Stat(diff)
            row["published"] = {"git_blob": lookup["entry"]["sha"], "sha256": sha256(current),
                "bytes": current.stat().st_size, "path": row["destination"], "mode": lookup["entry"]["mode"],
                "same_bytes": sha256(current) == row["sha256"], "same_decoded_pixels": diff.getbbox() is None,
                "rgb_mae": sum(metrics.mean) / 3, "max_rgb_difference": max(e[1] for e in diff.getextrema()),
                "local_verified_backup": str(current.relative_to(root)).replace("\\", "/")}
            row["publication_decision"] = "pending_explicit_canary_artifact_acceptance"
    if client.head(config.github_branch) != (snapshot["head"], snapshot["tree"]):
        raise BulkError("canary_head_drift", "Published branch changed during comparison; prepare a fresh proposal")
    return {"repository": config.github_repository, "branch": config.github_branch, "head": snapshot["head"],
        "tree": snapshot["tree"], "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "requests": session.observations, "all_requests_get_only": True,
        "exact_existing_paths": len(rows), "missing": 0, "case_conflicts": 0}


def prepare(root, *, published=False):
    root = reject_links(root).resolve()
    allowed = (ROOT.parent / "config/english-canary").resolve()
    if not root.is_relative_to(allowed) or root == allowed or root.exists():
        raise BulkError("canary_root", "Use a fresh child of config/english-canary; previous evidence is never overwritten")
    root.mkdir(parents=True)
    config = configuration(root)
    definitions = load_catalog(posters=tuple(SELECTION))
    translations = Translations({"en": ROOT / "fixtures/english/en.yml"})
    # Verify executable/catalog inputs still come from the explicitly approved commit.
    protected = ["create_defaults/create_poster.py", "create_defaults/poster_text.py", "create_defaults/fixtures/english/en.yml"]
    protected += [str(p.relative_to(ROOT.parent)).replace("\\", "/") for p in sorted((ROOT / "bulk").glob("*.py")) if p.name != "e_canary.py"]
    protected += [str(p.relative_to(ROOT.parent)).replace("\\", "/") for p in sorted((ROOT / "bulk/catalog").glob("*")) if p.is_file()]
    for path in protected:
        old = subprocess.check_output(["git", "show", APPROVED_COMMIT + ":" + path], cwd=ROOT.parent)
        # Text checkout line endings do not alter source identity.
        if (ROOT.parent / path).read_bytes().replace(b"\r\n", b"\n") != old.replace(b"\r\n", b"\n"):
            raise BulkError("canary_source", "Approved executable/catalog input changed: " + path)
    report, _ = preflight(definitions, translations, config=config, generators=GENERATORS, posters=tuple(SELECTION), languages=("en",), policy="strict")
    if report["status"] == "strict_blocked" or len(report["variants"]) != 7:
        raise BulkError("canary_preflight", "Strict English preflight must pass for exactly seven variants")
    limits = WorkerLimits(workers=2, timeout_seconds=120, retries=1, max_jobs=7)
    observations = {}
    with ResourceGuard(root, seconds=900, min_free=2 * 1024**3, max_output=64 * 1024**2, max_process_rss=2 * 1024**3) as guard:
        for phase in ("cold", "warm"):
            started = time.monotonic()
            result = generate(definitions, translations, config=config, generators=GENERATORS, posters=tuple(SELECTION), languages=("en",), policy="strict", limits=limits, cancel=guard)
            save(root / (phase + "-result.json"), result)
            if result["status"] != "verified":
                raise BulkError("canary_render", "Incomplete local preparation; retain evidence and stop")
            validate_scope(result["manifest"]["jobs"])
            observations[phase] = summarize(result, time.monotonic() - started)
            verify(result, config, decode=True)
            if phase == "cold": cold = result
            elif observations[phase]["executed"] or observations[phase]["worker_starts"] or result["manifest"]["sha256"] != cold["manifest"]["sha256"]:
                raise BulkError("canary_cache", "Unchanged warm run must reuse the exact cold manifest with no rendering")
    if guard.reason:
        raise BulkError("canary_resource", "Preparation resource guard stopped the run: " + guard.reason)
    references = reference_rows()
    verified = {r["id"]: r for r in json.loads((root / "verified-output-ledger.json").read_text(encoding="utf-8"))}
    variants = {v["id"]: v for v in cold["preflight"]["variants"]}
    categories = {d.id: d.category for d in Planner(generators=GENERATORS).expand(definitions)[0].values()}
    rows = []
    for job in cold["manifest"]["jobs"]:
        actual, previous = verified[job["id"]], references[job["poster_id"]]
        if actual["sha256"] != previous["receipt"]["sha256"] or job["render_fingerprint"] != previous["job"]["render_fingerprint"]:
            raise BulkError("canary_parity", "Canary must exactly match the validated full English rendering")
        rows.append({"id":job["id"],"poster_id":job["poster_id"],"category":categories[job["poster_id"]],
            "destination":job["remote_relative"],"local_relative":job["local_relative"],"sha256":actual["sha256"],"bytes":actual["bytes"],
            "render_fingerprint":job["render_fingerprint"],"validation_fingerprint":variants[job["id"]]["validation_fingerprint"],
            "dependencies":job["dependencies"],"inputs":job["inputs"],"parameters":job["parameters"],"layout_evidence":job["layout_evidence"],
            "diagnostics":variants[job["id"]]["diagnostics"],"reference_receipt_sha256":previous["receipt"]["receipt_sha256"],
            "exact_validated_full_run_match":True,"visual_approval_transferred":False})
    snapshot = compare_published(root, config, rows) if published else None
    value = {"schema_version":1,"kind":"english-canary-preparation-only","gate_e_approved_commit":APPROVED_COMMIT,
        "preparation_source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT.parent,text=True).strip(),
        "preparation_module_sha256":sha256(Path(__file__)),"renderer":cold["manifest"]["renderer"],"validation_policy":cold["preflight"]["policy"],
        "selection":SELECTION,"manifest_sha256":cold["manifest"]["sha256"],"preflight_sha256":cold["preflight"]["sha256"],
        "runs":observations,"rows":rows,"published_snapshot":snapshot,"guard_samples":guard.samples,
        "english_only":True,"overlays":0,"private_outputs":0,"publication_authorized":False,"production_changes":0,
        "readiness":"prepared_pending_exact_artwork_and_execution_approval" if published else "local_only_published_comparison_pending"}
    value["sha256"] = fingerprint(value); save(root/"preparation.json",value)
    cards=[]
    for row in rows:
        proposed="output/"+row["local_relative"]
        old=row.get("published",{}).get("local_verified_backup")
        images='<div><p>Proposed exact canary output</p><a href="'+escape(proposed,quote=True)+'"><img src="'+escape(proposed,quote=True)+'"></a></div>'
        if old: images+='<div><p>Current published</p><a href="'+escape(old,quote=True)+'"><img src="'+escape(old,quote=True)+'"></a></div>'
        cards.append('<article><h2>'+escape(row['destination'])+'</h2><p>Proposed SHA-256: <code>'+row['sha256']+'</code></p><p>Pending explicit inspection/acceptance; no approval transferred.</p><section>'+images+'</section></article>')
    html='<!doctype html><meta charset="utf-8"><title>English canary review — preparation only</title><style>body{font:16px system-ui;max-width:1100px;margin:24px auto}section{display:flex;gap:24px}section div{flex:1}img{width:100%}code{overflow-wrap:anywhere}article{border-top:1px solid #aaa;padding:24px}</style><h1>English canary — not published</h1><p>Seven exact English outputs. Left proposed; right pinned published bytes. Inspection does not authorize publication.</p>'+''.join(cards)
    (root/'review.html').write_text(html,encoding='utf-8')
    print(json.dumps({"root":str(root),"outputs":len(rows),"categories":dict(Counter(r['category'] for r in rows)),"preparation_sha256":value['sha256'],"published_head":snapshot['head'] if snapshot else None,"same_published_bytes":sum(r.get('published',{}).get('same_bytes',False) for r in rows),"publication_authorized":False}),flush=True)
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--compare-published',action='store_true',help='Explicit bounded GET-only snapshot/blob comparison; never writes remotely')
    args=parser.parse_args(argv)
    prepare(args.root,published=args.compare_published)


if __name__ == '__main__':
    main()
