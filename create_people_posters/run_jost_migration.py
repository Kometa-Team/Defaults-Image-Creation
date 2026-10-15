"""Explicitly approved, standalone full Jost rollout. No AI API or agent loop."""

import argparse
import html
import json
import os
from pathlib import Path
import sys
import time
import traceback

from dotenv import load_dotenv

from create_people_poster import FONTS, label_name, resource_dirs
from jost_migration import DEFAULT_ROOT, STYLES, BRANCH, Migration, MigrationTransport, json_hash
from people_github import GitHubError
from people_workspaces import atomic_json, reject_links, process_alive
from poster_fonts import FontMetrics


def checkpoint(job, state, **values):
    if values.get("status") in {"running","completed","completed_with_exceptions"}:
        state.pop("error",None)
    state.update(values, pid=os.getpid(), updated=time.time())
    atomic_json(job.root / "state/rollout.json", state)
    print(json.dumps({k:v for k,v in state.items() if k != "approval"},ensure_ascii=True),flush=True)


def problem_report(job, mid):
    manifest = job.load(mid,current=False)
    problems, warnings, sections = [], [], []
    for row in job.items(mid,manifest):
        if not row["selected"]:
            continue
        notes = json.loads(row["metrics"]).get("warnings",[])
        if row["status"] in {"failed","conflict","review_required","publication_problem","skipped"}:
            links = []
            for style in STYLES:
                target = job.target(mid,row,style)
                if target.is_file():
                    links.append('<a href="'+html.escape(target.as_uri(),quote=True)+'">'+style+'</a>')
            detail = {"number":row["number"],"name":row["name"],"status":row["status"],"error":row["error"],"warnings":notes}
            problems.append(detail)
            sections.append('<tr><td>'+html.escape(row["name"])+ '</td><td>'+html.escape(row["status"])
                            +'</td><td>'+html.escape(row["error"] or "")+'</td><td>'+" | ".join(links)+'</td></tr>')
        elif notes:
            warnings.append({"name":row["name"],"warnings":notes})
    result = {"migration":mid,"problems":problems,"missing_sources":manifest["missing_sources"],"published_warnings":warnings,
              "quarantined_units":[dict(r) for r in job.db.execute("SELECT * FROM jost_quarantines WHERE mid=?",(mid,))],
              "readme_problems":[dict(r) for r in job.db.execute("""SELECT r.* FROM readmes r JOIN jost_units u ON u.id=r.batch
                  WHERE u.mid=? AND r.status IN ('pending','failed','warning') AND EXISTS
                  (SELECT 1 FROM publications p WHERE p.batch=r.batch AND p.repo=r.repo AND p.status='published')""",(mid,))]}
    directory = job.root / "reports" / mid
    atomic_json(directory / "problems.json",result)
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Rebuild problems</title>'
                '<style>body{font:15px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}pre{white-space:pre-wrap}</style>'
                '<h1>Rebuild problems</h1><p>'+html.escape(mid)+'</p><p>'+str(len(problems))+' held or failed people. '
                +'No automatic source edits, font substitutions or conflict overwrites.</p><table><tr><th>Person</th><th>Status</th><th>Reason</th><th>Generated posters</th></tr>'
                +''.join(sections)+'</table><h2>Missing local sources</h2><pre>'
                +html.escape(json.dumps(manifest["missing_sources"],indent=2,ensure_ascii=False))
                +'</pre><h2>README workflow problems</h2><pre>'+html.escape(json.dumps(result["readme_problems"],indent=2))
                +'</pre><details><summary>Warnings on published images</summary><pre>'
                +html.escape(json.dumps(warnings,indent=2,ensure_ascii=False))+'</pre></details></html>')
    target = directory / "problems.html"
    reject_links(target)
    target.write_text(document,encoding="utf-8")
    return str(target)


def quarantine_conflicts(job, mid):
    held = 0
    for unit in job.db.execute("""SELECT * FROM jost_units u WHERE mid=? AND verified IS NULL
            AND NOT EXISTS(SELECT 1 FROM jost_quarantines q WHERE q.unit=u.id)""",(mid,)).fetchall():
        receipts = job.ledger.rows(unit["id"])
        if not any(r["status"] == "conflict" for r in receipts):
            continue
        error = "; ".join(sorted({r["error"] for r in receipts if r["error"]}))
        with job.db:
            job.db.execute("INSERT INTO jost_quarantines VALUES(?,?,?,?)",(mid,unit["id"],error,time.time()))
            job.db.executemany("UPDATE jost_items SET status='publication_problem',error=? WHERE mid=? AND number=?",
                               [(error,mid,n) for n in json.loads(unit["numbers"])])
        # Partial successes still need their normal README refresh, but never cleanup.
        for repo in {r["repo"] for r in receipts if r["status"] == "published"}:
            try:
                MigrationTransport(job.remote().client.client,writes=True).request("POST",f"/repos/{repo}/actions/workflows/readme.yml/dispatches",{"ref":BRANCH})
                job.ledger.readme(unit["id"],repo,"dispatched")
            except GitHubError as failure:
                job.ledger.readme(unit["id"],repo,"failed",str(failure))
        held += 1
        print("[QUARANTINED UNIT] " + unit["id"] + ": " + error,flush=True)
    return held


def run_batches(migration, mid, sample, token, batch_size, state):
    manifest = migration.load(mid)
    migration.review(mid,token,sample)
    approval = {"manifest_hash":json_hash(manifest),"sample":sample,"review_sha256":token,
                "batch_size":batch_size,"retention_days":0}
    if state.get("approval") and state["approval"] != approval:
        raise ValueError("Rollout approval/settings changed; preserve state for reconciliation")
    checkpoint(migration,state,migration=mid,approval=approval,phase="preflight",status="running")
    _,fonts = resource_dirs()
    metrics = FontMetrics(fonts / FONTS[2])
    for row in migration.items(mid,manifest):
        if row["selected"] and row["status"] == "discovered":
            try:
                metrics.glyphs(label_name(row["name"].replace("_ccexpress", "")).upper())
            except ValueError as error:
                with migration.db:
                    migration.db.execute("UPDATE jost_items SET status='skipped',error=? WHERE mid=? AND number=?",
                                         (str(error),mid,row["number"]))
                for style in STYLES:
                    migration.update_output(mid,row["number"],style,state="skipped",error=str(error))
                print("[SKIPPED FONT] " + row["name"],flush=True)
    # The approved sample's permanent report copies remain available after cleanup.
    migration.cleanup(sample,False,0)
    while True:
        stop = migration.root / "state/rollout.stop"
        reject_links(stop)
        if stop.exists():
            checkpoint(migration,state,status="stopped",phase="between_batches")
            return state
        rows = [r for r in migration.items(mid) if r["selected"]]
        pending = migration.db.execute("""SELECT 1 FROM jost_units u WHERE mid=? AND verified IS NULL
            AND NOT EXISTS(SELECT 1 FROM jost_quarantines q WHERE q.unit=u.id)""",(mid,)).fetchone()
        ready = any(r["status"] == "validated" for r in rows)
        if not pending and not ready:
            if not any(r["status"] == "discovered" for r in rows):
                result = migration.export(mid)
                exceptions = any(result["statuses"].get(s,0) for s in ("failed","skipped","review_required","conflict","publication_problem")) or bool(manifest["missing_sources"])
                checkpoint(migration,state,status="completed_with_exceptions" if exceptions else "completed",
                           phase="finished",counts=result["statuses"],missing_local_destinations=len(manifest["missing_sources"]),
                           problem_report=problem_report(migration,mid))
                return state
            checkpoint(migration,state,phase="rendering")
            migration.render(mid,batch_size,retry_failed=False)
        for row in migration.items(mid):
            if row["selected"] and row["status"] == "validated" and json.loads(row["metrics"]).get("requires_individual_review",True):
                with migration.db:
                    migration.db.execute("UPDATE jost_items SET status='review_required',error=? WHERE mid=? AND number=?",
                        ("Noncanonical input needs its own visual approval; not published by unattended rollout",mid,row["number"]))
        checkpoint(migration,state,phase="publishing")
        for attempt in range(5):
            try:
                migration.publish(mid,batch_size,batch_size,False,mid,token,approved_sample=sample)
                break
            except GitHubError:
                if quarantine_conflicts(migration,mid):
                    break
                if attempt == 4:
                    raise
                checkpoint(migration,state,phase="retry_wait",retry=attempt+1)
                time.sleep(min(900,60*2**attempt))
        migration.cleanup(mid,False,0)
        result = migration.export(mid)
        checkpoint(migration,state,phase="batch_verified",counts=result["statuses"],workspace_bytes=result["workspace_bytes"])
        time.sleep(2)


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if callable(getattr(stream,"reconfigure",None)):
            stream.reconfigure(encoding="utf-8",errors="backslashreplace")
    load_dotenv(Path(__file__).resolve().parent / "config/.env")
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("start","resume","status","stop"):
        modes.add_argument("--"+mode,action="store_true")
    parser.add_argument("--approved-sample")
    parser.add_argument("--reviewed")
    parser.add_argument("--confirm-full-rollout",action="store_true")
    parser.add_argument("--workspace",type=Path,default=DEFAULT_ROOT)
    parser.add_argument("--batch-size",type=int,default=50)
    args = parser.parse_args(argv)
    root = args.workspace.expanduser().absolute()
    reject_links(root)
    path = root / "state/rollout.json"
    stop = root / "state/rollout.stop"
    reject_links(path)
    reject_links(stop)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if args.status:
        print(json.dumps(dict(state,process_alive=bool(state.get("pid") and process_alive(state["pid"]))),indent=2))
        return 0
    if args.stop:
        if not state:
            parser.error("No rollout exists")
        atomic_json(stop,{"requested":time.time()})
        print("Stop requested; the current batch will finish and verify first.")
        return 0
    if not args.confirm_full_rollout or not 1 <= args.batch_size <= 100:
        parser.error("Explicit --confirm-full-rollout and batch size 1-100 are required")
    if args.resume:
        if not state.get("migration"):
            parser.error("No completed scan to resume; explicitly --start again if the initial scan was interrupted")
        sample = state.get("approval",{}).get("sample",state.get("approved_sample"))
        token = state.get("approval",{}).get("review_sha256",state.get("review_sha256"))
    else:
        if not args.approved_sample or not args.reviewed:
            parser.error("--start requires --approved-sample and --reviewed")
        if state.get("migration"):
            parser.error("A rollout manifest already exists; use --resume, not a new scan")
        sample,token = args.approved_sample,args.reviewed
    migration = None
    owned = False
    try:
        migration = Migration(root)
        with migration.lock():
            owned = True
            if args.resume:
                stop.unlink(missing_ok=True)
                mid = state["migration"]
            else:
                migration.review(sample,token)
                checkpoint(migration,state,status="running",phase="scanning",started=time.time(),
                           approved_sample=sample,review_sha256=token)
                mid = migration.scan(os.getenv("JOST_MIGRATION_TRANSPARENT_DIR"),exclude_ambiguous=True)
                checkpoint(migration,state,migration=mid,phase="scan_complete")
            run_batches(migration,mid,sample,token,args.batch_size,state)
        return 0
    except Exception as error:
        if migration and owned:
            report = None
            if state.get("migration"):
                try:
                    report = problem_report(migration,state["migration"])
                except Exception:
                    traceback.print_exc()
            checkpoint(migration,state,status="failed",error=str(error),problem_report=report)
        print("[ERROR] " + str(error),file=sys.stderr,flush=True)
        traceback.print_exc()
        return 1
    finally:
        if migration:
            migration.close()


if __name__ == "__main__":
    raise SystemExit(main())
