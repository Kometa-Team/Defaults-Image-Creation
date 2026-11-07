"""Standalone staging-only People regeneration. No acquisition or publication."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, ExitStack
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

sys.dont_write_bytecode = True

from bulk_regeneration_state import (STYLES, STATE, MARKER, atomic_json, canonical, counts,
    database, evidence, human, inspect, log, metadata, process_identity, read_json,
    reject_links, set_meta, sha, writer_lock, resource_usage, read_inventory, sync_parent,require_durable_local_state)

VERSION = "3-unicode-inter-v1"
_local = threading.local()


def _renderer():
    from create_people_poster import Renderer
    if not hasattr(_local, "renderer"):
        _local.renderer = Renderer()
    return _local.renderer


def receipt_path(root, relative):
    return Path(root)/STATE/"receipts"/(relative+".json")


def validated_receipt(root, item, style, renderer_id, batch_id):
    from create_people_poster import output_path, SIZE
    target = output_path(Path(root), style, item["name"])
    relative = target.relative_to(root).as_posix()
    try:
        receipt = read_json(receipt_path(root, relative))
        expected = dict(batch_id=batch_id, renderer_id=renderer_id, source_sha256=item["source_hash"],
                        source=item["relative"], output=relative, style=style)
        if any(receipt.get(k) != v for k, v in expected.items()) or sha(target) != receipt["sha256"]:
            return None
        from unicode_labels import POLICY_SHA256
        label=receipt.get('label_resolution',{})
        if (label.get('policy_sha256') != POLICY_SHA256 or label.get('style') != style
                or label.get('original_name') != item['name'] or label.get('filename') != item['name']
                or label.get('resolution_method') not in {'original','normalized','substituted','fallback-font'}
                or canonical(label) != receipt.get('label_resolution_sha256')):
            return None
        from PIL import Image
        with Image.open(target) as image:
            if image.format != "JPEG" or image.mode != ("L" if style == "bw" else "RGB") or image.size != SIZE:
                return None
        return receipt
    except (OSError, ValueError, KeyError):
        return None


def atomic_poster(image, target, style=None):
    from PIL import Image
    from create_people_poster import SIZE
    target = Path(target)
    reject_links(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    reject_links(target)
    temporary = None
    try:
        encoded = BytesIO()
        tick = time.perf_counter()
        image.save(encoded, "JPEG", quality=100, subsampling=0)
        encode_seconds = time.perf_counter()-tick
        tick = time.perf_counter()
        with tempfile.NamedTemporaryFile(prefix=".bulk-", suffix=".jpg", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded.getvalue())
            handle.flush(); os.fsync(handle.fileno())
        write_seconds = time.perf_counter()-tick
        encoded.close()
        with Image.open(temporary) as check:
            check.load()
            if check.format != "JPEG" or check.mode != ("L" if style == "bw" else "RGB") or check.size != SIZE:
                raise ValueError("Generated poster has an unexpected JPEG mode or size")
        tick = time.perf_counter()
        result = dict(sha256=sha(temporary), bytes=temporary.stat().st_size)
        hash_seconds = time.perf_counter()-tick
        tick = time.perf_counter()
        os.replace(temporary, target)
        sync_parent(target)
        write_seconds += time.perf_counter()-tick
        result['output_timings'] = dict(jpeg_encoding_seconds=encode_seconds,
            output_write_seconds=write_seconds,output_hash_seconds=hash_seconds)
        return result
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def render_one(root, source, item, styles, renderer_id, batch_id):
    """One source at a time per worker; only explicitly pending outputs are written."""
    from PIL import Image
    from create_people_poster import output_path
    source_path = Path(source)/item["relative"]
    reject_links(source_path)
    tick = time.perf_counter()
    if sha(source_path) != item["source_hash"]:
        raise ValueError("Source changed since the durable inventory")
    timings = dict(source_hash_before_seconds=time.perf_counter()-tick)
    outputs = {}
    try:
        tick = time.perf_counter()
        source_bytes = source_path.read_bytes()
        timings['input_read_seconds'] = time.perf_counter()-tick
        tick = time.perf_counter()
        with Image.open(BytesIO(source_bytes)) as image:
            image.load()
            timings['input_decode_seconds'] = time.perf_counter()-tick
            tick = time.perf_counter()
            renderer = _renderer()
            timings['renderer_initialization_seconds'] = time.perf_counter()-tick
            collection_calls = {}
            original_collection = renderer.render_collection
            original_label = getattr(renderer, 'label', None)
            font_seconds = 0
            def timed_label(*args, **kwargs):
                nonlocal font_seconds
                tick = time.perf_counter()
                try:
                    return original_label(*args, **kwargs)
                finally:
                    font_seconds += time.perf_counter()-tick
            def collection(poster, style):
                nonlocal font_seconds
                collection_calls[style] = collection_calls.get(style, 0)+1
                tick = time.perf_counter()
                try:
                    return original_collection(poster, style)
                finally:
                    font_seconds += time.perf_counter()-tick
            renderer.render_collection = collection
            renderer.label = timed_label
            # Resolve and render only pending styles, with independent failures.
            try:
                tick = time.perf_counter()
                rendered = renderer.render_independent(image,item['name'],styles,filename=item['name'])
                outputs, warnings = rendered['outputs'],rendered['warnings']
                timings['render_seconds'] = time.perf_counter()-tick
                timings['font_render_seconds'] = font_seconds
                timings['compositing_and_geometry_seconds'] = max(0,timings['render_seconds']-font_seconds)
            finally:
                renderer.render_collection = original_collection
                if original_label is None:
                    del renderer.label
                else:
                    renderer.label = original_label
            for style in tuple(outputs):
                if collection_calls.get(style,0) != (0 if style == 'bw' else 1):
                    outputs.pop(style).close()
                    rendered['errors'][style] = dict(style=style,error='Unexpected COLLECTION count')
        del source_bytes
        tick = time.perf_counter()
        if sha(source_path) != item["source_hash"]:
            raise ValueError("Source changed during rendering")
        timings['source_hash_after_seconds'] = time.perf_counter()-tick
        receipts = []
        errors = dict(rendered['errors'])
        for style in outputs:
            target = output_path(Path(root), style, item["name"])
            relative = target.relative_to(root).as_posix()
            try:
                resolution=rendered['labels'][style]
                receipt = dict(batch_id=batch_id, renderer_id=renderer_id, source=item["relative"],
                               source_sha256=item["source_hash"], output=relative, style=style,
                               completed_at=time.time(), warnings=warnings, collection_calls=collection_calls,
                               label_resolution=resolution,label_resolution_sha256=canonical(resolution),
                               timings=timings,**atomic_poster(outputs[style],target,style))
                path = receipt_path(root, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_json(path, receipt)
                receipts.append(receipt)
            except (OSError,ValueError) as error:
                errors[style]=dict(error=str(error),style=style)
        if errors:
            from unicode_review import write_review
            from unicode_labels import STYLE_FONTS
            for style,record in errors.items():
                record=dict(record,original_name=item['name'],filename=item['name'],style=style,
                            font=record.get('font',STYLE_FONTS[style]))
                write_review(Path(root)/STATE/'unicode-review'/str(item['number'])/style,record,renderer)
            raise StyleFailures(errors)
        return receipts
    finally:
        for image in outputs.values():
            image.close()


class StyleFailures(ValueError):
    def __init__(self, errors):
        self.errors=errors
        super().__init__('Independent poster styles require review: '+json.dumps(errors,ensure_ascii=False))


def _schema(db):
    db.executescript("""
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE inputs(number INTEGER PRIMARY KEY,relative TEXT UNIQUE,name TEXT,source_hash TEXT,
            selected INTEGER,eligible INTEGER,error TEXT);
        CREATE TABLE outputs(number INTEGER,style TEXT,path TEXT UNIQUE,status TEXT,sha256 TEXT,
            bytes INTEGER,error TEXT,attempts INTEGER NOT NULL DEFAULT0,updated REAL,
            PRIMARY KEY(number,style));
    """.replace("DEFAULT0", "DEFAULT 0"))


def _memory_budget(workers):
    if not 1 <= workers <= 8:
        raise ValueError("--workers must be 1 through 8")
    if os.name=='posix' and Path('/proc/meminfo').exists():
        values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if ':' in line}
        available=values['MemAvailable']
        limit=Path('/sys/fs/cgroup/memory.max')
        current=Path('/sys/fs/cgroup/memory.current')
        if limit.exists() and current.exists() and limit.read_text().strip()!='max':
            available=min(available,max(0,int(limit.read_text())-int(current.read_text())))
        if available<(workers*1.5+1)*1024**3:
            raise ValueError('Insufficient available/cgroup RAM; reduce workers or increase the memory limit')
        return dict(workers=workers,approximate_worker_bytes=1536*1024**2,available_bytes=available)
    if os.name == "nt":
        import ctypes
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        *[(n, ctypes.c_ulonglong) for n in ("total", "available", "page_total", "page_available",
                                                           "virtual_total", "virtual_available", "extended")]]
        value = Memory(); value.length = ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            if value.available < (workers*1.5+1)*1024**3:
                raise ValueError("Insufficient available RAM for the requested workers; reduce --workers")
            return dict(workers=workers, approximate_worker_bytes=1536*1024**2, available_bytes=value.available)
    return dict(workers=workers, approximate_worker_bytes=1536*1024**2)


def _initial(root, source, styles, renderer, source_git, canary, workers, input_total, source_pin=None, canary_paths=None):
    batch_id = uuid.uuid4().hex
    manifest = dict(managed_by=MARKER, version=VERSION, batch_id=batch_id,
                    output=str(root), source=str(source), styles=list(styles), canary=canary,
                    renderer=renderer, source_git=source_git, input_total=input_total,
                    created=time.time(), inventory_complete=False, source_pin=source_pin, canary_paths=canary_paths)
    root.mkdir(parents=True, exist_ok=True)
    (root/STATE).mkdir(exist_ok=True)
    db = database(root)
    _schema(db)
    atomic_json(root/STATE/"manifest.json", manifest)
    with db:
        set_meta(db, managed_by=MARKER, output=str(root), batch_id=batch_id, version=VERSION,
                 state="running", phase="inventory", manifest_hash=canonical(manifest), manifest=manifest,
                 started=time.time(), updated=time.time(), pid=os.getpid(), process_identity=process_identity(os.getpid()),
                 stale_after_seconds=60, input_total=input_total, eligible_image_count=0,
                 selected_input_total=0, source_git=source_git, renderer_id=canonical(renderer),
                 renderer=renderer, workers=workers, last_error=None, last_successful_image=None)
    evidence(root, db, [])
    return db, manifest


def _commit_inventory(root, db, manifest, rows, summary, storage):
    from create_people_poster import output_path
    # Preserve the existing guarded writer limit at every collection level.
    atomic_json(root/STATE/"inventory.json", dict(version=1, count=len(rows),
                chunks=[rows[i:i+2048] for i in range(0,len(rows),2048)]))
    manifest = dict(manifest, inventory_complete=True, inventory_sha256=canonical(rows), inventory=summary, storage=storage)
    with db:
        for row in rows:
            db.execute("INSERT INTO inputs VALUES(?,?,?,?,?,?,?)",
                       (row["number"], row["relative"], row["name"], row["source_hash"],
                        int(row["selected"]), int(row["eligible"]), row["issue"]))
            if row["selected"]:
                for style in manifest["styles"]:
                    path = output_path(root, style, row["name"]).relative_to(root).as_posix()
                    state = ("skipped" if row["issue_kind"] == "collision" else "failed") if row["issue"] else "pending"
                    db.execute("INSERT INTO outputs VALUES(?,?,?,?,?,?,?,?,?)",
                               (row["number"], style, path, state, None, 0, row["issue"], 0, time.time()))
        problems = [r for r in rows if r["selected"] and r["issue"]]
        if problems:
            set_meta(db, last_error=dict(image=problems[-1]["relative"], summary=problems[-1]["issue"], time=time.time()))
        set_meta(db, manifest_hash=canonical(manifest), manifest=manifest, **{k:summary[k] for k in
                 ("input_total", "eligible_image_count", "selected_input_total")}, phase="rendering", storage=storage)
    atomic_json(root/STATE/"manifest.json", manifest)
    return dict(manifest, items=rows)


def _planning_progress(root, db, checked, total, current):
    with db:
        set_meta(db, updated=time.time(), inventory_validated=checked,
                 inventory_total=total, current_inventory_image=current,
                 phase='source_hashing' if current.startswith('[hash] ') else 'inventory_validation')
    evidence(root, db, [])
    if checked % 500 == 0 or checked == total:
        print(f"[CHECK] {checked}/{total} PNG containers; current={current}", flush=True)


def _completed(db, number, receipts):
    with db:
        for receipt in receipts:
            db.execute("""UPDATE outputs SET status='completed',sha256=?,bytes=?,error='',updated=?
                WHERE number=? AND style=?""",
                (receipt["sha256"], receipt["bytes"], time.time(), number, receipt["style"]))


def _resume_reconcile(root, db, manifest, retry_failed, progress=None):
    """Accept content-bound receipts, never filename existence."""
    renderer_id, batch_id = canonical(manifest["renderer"]), manifest["batch_id"]
    reused = 0
    items = [item for item in manifest["items"] if item["selected"] and item["eligible"]]
    for checked, item in enumerate(items):
        if progress is not None:
            progress(checked, len(items), item["relative"])
        if sha(Path(manifest["source"])/item["relative"]) != item["source_hash"]:
            raise ValueError("Source fingerprint changed: "+item["relative"]+"; preserve this batch and plan a new one")
        receipts = []
        for style in manifest["styles"]:
            row = db.execute("SELECT * FROM outputs WHERE number=? AND style=?", (item["number"], style)).fetchone()
            receipt = validated_receipt(root, item, style, renderer_id, batch_id)
            if receipt:
                # Verified content does not require another durable write when
                # its checkpoint already records the same completion.
                if not (row["status"] == "completed" and row["sha256"] == receipt["sha256"]
                        and row["bytes"] == receipt["bytes"] and not row["error"]):
                    receipts.append(receipt)
                reused += 1
            elif ((row["status"] in {"running", "completed", "pending"} or retry_failed)
                  and not (row["status"] == "pending" and row["error"] == "")):
                with db:
                    db.execute("UPDATE outputs SET status='pending',error='',updated=? WHERE number=? AND style=?",
                               (time.time(), item["number"], style))
        _completed(db, item["number"], receipts)
    if progress is not None:
        progress(len(items), len(items), None)
    with db:
        set_meta(db, reused_validated_outputs=reused)
    return reused


def _resume_progress(root, db, interval):
    """Expose validation before rendering; keep transactions outside file I/O."""
    last = None
    def report(checked, total, current):
        nonlocal last
        now = time.monotonic()
        if last is not None and checked != total and now-last < interval:
            return
        with db:
            set_meta(db, state="running", phase="resume_validation", updated=time.time(),
                     pid=os.getpid(), process_identity=process_identity(os.getpid()),
                     resume_checked=checked, resume_total=total, current_resume_image=current)
        evidence(root, db, [])
        message = f"[RESUME] {checked}/{total} source/receipt checks; current={current or '-'}"
        print(message, flush=True)
        log(root, message)
        last = now
    return report


def _progress_line(value):
    rate = value.get("recent_outputs_per_second") or 0
    eta = value.get("approximate_eta_seconds")
    styles = " ".join(s+"="+str(value["per_style"][s]["completed"]) for s in STYLES)
    current = ", ".join(value.get("current_images", [])) or "-"
    return (f"{value['completion_percent']:.1f}% inputs={value['processed_inputs']}/{value['selected_input_total']} "
            f"remaining={value['remaining']+value['in_progress']} {styles} failed={value['failed']} skipped={value['skipped']} "
            f"rate={rate*60:.1f}/min elapsed={value['elapsed_seconds']/3600:.2f}h "
            f"ETA~{eta/3600:.2f}h current={current}" if eta is not None else
            f"{value['completion_percent']:.1f}% inputs={value['processed_inputs']}/{value['selected_input_total']} "
            f"remaining={value['remaining']+value['in_progress']} {styles} failed={value['failed']} skipped={value['skipped']} "
            f"rate={rate*60:.1f}/min elapsed={value['elapsed_seconds']/3600:.2f}h ETA~unknown current={current}")


def run_batch(root, db, manifest, workers=1, progress_seconds=15, stop=None, worker=render_one):
    from bulk_regeneration_plan import require_space, RESERVE
    stop = stop or threading.Event()
    history, active, index = [], {}, 0
    items = [row for row in manifest["items"] if row["selected"] and row["eligible"]]
    renderer_id = canonical(manifest["renderer"])
    handlers = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, getattr(signal, "SIGBREAK", signal.SIGINT), signal.SIGTERM):
            if sig not in handlers:
                handlers[sig] = signal.signal(sig, lambda *_: stop.set())
    with db:
        set_meta(db, state="running", phase="rendering", pid=os.getpid(), process_identity=process_identity(os.getpid()),
                 workers=workers, updated=time.time())
    last_progress = 0
    fatal = None
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="people-staging") as pool:
            while active or index < len(items):
                while not stop.is_set() and len(active) < workers and index < len(items):
                    item = items[index]; index += 1
                    styles = tuple(r[0] for r in db.execute("SELECT style FROM outputs WHERE number=? AND status='pending'", (item["number"],)))
                    if not styles:
                        continue
                    try:
                        # Admission is checked repeatedly; never fill the disk
                        # merely because the original estimate was optimistic.
                        per_image = sum(manifest["storage"]["per_style"][s]["estimated_bytes_per_output"] for s in styles)
                        require_space(root, RESERVE+per_image*workers)
                    except ValueError as error:
                        fatal = str(error); stop.set(); break
                    with db:
                        db.executemany("UPDATE outputs SET status='running',attempts=attempts+1,updated=? WHERE number=? AND style=?",
                                       [(time.time(), item["number"], s) for s in styles])
                    future = pool.submit(worker, root, manifest["source"], item, styles, renderer_id, manifest["batch_id"])
                    active[future] = (item, styles)
                if not active:
                    break
                done, _ = wait(active, timeout=.25, return_when=FIRST_COMPLETED)
                for future in done:
                    item, styles = active.pop(future)
                    try:
                        receipts = future.result()
                        _completed(db, item["number"], receipts)
                        with db:
                            set_meta(db, last_successful_image=item["relative"])
                    except Exception as error:
                        error_text = f"{type(error).__name__}: {error}"[:2000]
                        for style in styles:
                            receipt = validated_receipt(root, item, style, renderer_id, manifest["batch_id"])
                            if receipt:
                                _completed(db, item["number"], [receipt])
                            else:
                                with db:
                                    db.execute("UPDATE outputs SET status='failed',error=?,updated=? WHERE number=? AND style=?",
                                               (json.dumps(error.errors.get(style,{}),ensure_ascii=False)[:2000] if isinstance(error,StyleFailures) else error_text, time.time(), item["number"], style))
                        with db:
                            set_meta(db, last_error=dict(image=item["relative"], summary=error_text, time=time.time()))
                        log(root, "Input failed: "+item["relative"], dict(error=error_text))
                    else:
                        log(root, "Input completed", dict(image=item["relative"], outputs=len(receipts)))
                now = time.time()
                if now-last_progress >= progress_seconds:
                    with db:
                        set_meta(db, updated=now)
                    value = evidence(root, db, history)
                    line = _progress_line(value)
                    print(line, flush=True); log(root, line)
                    last_progress = now
            final_counts = counts(db)
            state = "failed" if fatal else "interrupted" if stop.is_set() else "failed" if final_counts["failed"] else "completed"
            with db:
                set_meta(db, state=state, phase="finished" if state=="completed" else state,
                         updated=time.time(), stopped=time.time(), resource_usage=resource_usage(),
                         **({"last_error":dict(summary=fatal, time=time.time())} if fatal else {}))
            value = evidence(root, db, history)
            log(root, "Batch "+state, dict(counts={k:value[k] for k in ("completed","failed","skipped","remaining","in_progress")}))
            print(human(value), flush=True)
            if manifest.get("canary"):
                try:
                    from bulk_regeneration_report import canary_report
                    canary_report(root, manifest)
                except Exception as error:
                    log(root, "Canary comparison report failed", dict(error=str(error)))
                    print("WARNING: comparison report unavailable: "+str(error), file=sys.stderr)
            return 130 if state=="interrupted" else 1 if state=="failed" else 0
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    modes = result.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="Read only; never starts a renderer")
    modes.add_argument("--validate", action="store_true", help="Read-only completed-batch receipt, JPEG and checkpoint validation")
    modes.add_argument("--dry-run", action="store_true", help="Read-only inventory/container validation and disk estimate")
    modes.add_argument("--resume", action="store_true", help="Resume this exact batch after validating its receipts")
    result.add_argument("--source", type=Path)
    result.add_argument('--source-pin',type=Path,help='Persistent registered source pin, mounted with the source')
    result.add_argument('--require-readonly-source',action='store_true',help='Require a registered pin and a read-only Linux source mount')
    result.add_argument("--output", type=Path, required=True, help="Explicit staging batch workspace, outside every Git repository")
    result.add_argument("--styles", nargs="+", help="bw diiivoy diiivoycolor rainier signature; commas also accepted")
    result.add_argument("--canary", type=int, help="Render only this many representative people (1-100)")
    result.add_argument('--canary-selection',type=Path,help='Explicit JSON items[].relative for reproducible bounded canaries; requires --canary')
    result.add_argument("--workers", type=int, default=2)
    result.add_argument("--progress-seconds", type=float, default=15)
    result.add_argument("--retry-failed", action="store_true", help="With --resume, retry failed outputs whose planned source bytes remain unchanged")
    result.add_argument("--existing-root", type=Path, help="Read-only parent of existing style repositories; defaults to source parent")
    result.add_argument("--estimate-from", type=Path, help="Read completed canary sizes to refine the full staging estimate")
    result.add_argument("--deep-validate", action="store_true", help="With --dry-run, hash and CRC-check every source payload (slow)")
    result.add_argument("--json", action="store_true", help="JSON status or dry-run output")
    return result


@contextmanager
def _held_writer(root, locks):
    # Keep ownership through exception reporting and db.close(), not only the
    # happy-path body. A competing writer must never overlap failure evidence.
    locks.enter_context(writer_lock(root))
    yield


def _main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if callable(getattr(stream, "reconfigure", None)):
            stream.reconfigure(encoding="utf8", errors="backslashreplace")
    args = parser().parse_args(argv)
    if args.styles:
        args.styles = [style for value in args.styles for style in value.split(',')]
        if any(style not in STYLES for style in args.styles):
            parser().error('Unsupported bulk style')
    if args.validate:
        if args.source or args.styles or args.canary or args.canary_selection or args.retry_failed:
            parser().error('--validate takes only --output and optional --json')
        from bulk_validate import validate
        value = validate(args.output)
        print(json.dumps(value, indent=2, ensure_ascii=True) if args.json else
              f"Validation {value['state']}: {value['verified']}/{value['planned']} posters; " +
              "; ".join(value['errors']))
        return 2 if value['state']=='unavailable' else 0 if value['valid'] else 1
    if args.status:
        if args.source or args.styles or args.canary or args.canary_selection or args.retry_failed:
            parser().error("--status takes only --output and optional --json")
        value = inspect(args.output)
        print(json.dumps(value, indent=2, ensure_ascii=True) if args.json else human(value))
        return 2 if value["state"]=="unavailable" else 0
    from bulk_regeneration_plan import (check_paths, estimate_storage, existing_sizes,
                                       git_state, inventory, renderer_version, require_space)
    db = None
    locks = ExitStack()
    try:
        if args.deep_validate and not args.dry_run:
            raise ValueError("--deep-validate requires --dry-run")
        if args.progress_seconds < .1:
            raise ValueError("--progress-seconds must be at least0.1")
        if args.retry_failed and not args.resume:
            raise ValueError("--retry-failed requires --resume")
        if args.canary is not None and (args.resume or not 1 <= args.canary <= 100):
            raise ValueError("Use --canary1..100 for a new batch; resume preserves its original selection")
        canary_paths=None
        if args.canary_selection:
            if not args.canary or args.resume:
                raise ValueError('--canary-selection requires a new bounded --canary batch')
            selected=read_json(args.canary_selection)
            canary_paths=[row['relative'] for row in selected['items']]
            from bulk_source import path_key
            if len(canary_paths)!=args.canary or len({path_key(p) for p in canary_paths})!=args.canary:
                raise ValueError('Explicit canary selection must contain exactly --canary distinct safe paths')
        _memory_budget(args.workers)
        if args.require_readonly_source:
            require_durable_local_state(args.output)
        if args.resume:
            root = args.output.expanduser().absolute().resolve()
            reject_links(args.output)
            # The checkpoint owns its compact manifest. This also recovers a
            # crash after its transaction commits but before JSON replacement.
            from contextlib import closing
            with closing(database(root, readonly=True)) as check:
                stored = check.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()
                if not stored:
                    raise ValueError("No durable batch manifest")
                manifest = json.loads(stored[0])
            if manifest.get("managed_by") != MARKER or Path(manifest["output"]).resolve() != root:
                raise ValueError("Not this exact standalone batch workspace")
            source, root = check_paths(args.source or manifest["source"], root)
            if manifest.get('source_pin') or args.require_readonly_source:
                if not manifest.get('source_pin'):
                    raise ValueError('This batch has no registered source pin; preserve it and start a new pinned batch')
                from bulk_source import validate_pin
                pin_path=args.source_pin or Path(manifest['source_pin']['path'])
                pin=validate_pin(source,pin_path,args.require_readonly_source)
                if dict(pin,path=str(pin_path))!=manifest.get('source_pin'):
                    raise ValueError('Source pin changed since batch creation')
            if str(source) != manifest["source"] or args.styles and list(args.styles) != manifest["styles"]:
                raise ValueError("Resume source/styles differ from the recorded batch")
            with _held_writer(root, locks):
                db = database(root)
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Checkpoint database integrity check failed")
                if metadata(db)["manifest_hash"] != canonical(manifest):
                    raise ValueError("Manifest/checkpoint digest mismatch")
                if manifest["renderer"] != renderer_version():
                    raise ValueError("Renderer, workflow, dependencies or resources changed; plan a separate batch")
                if manifest["source_git"] != git_state(source):
                    raise ValueError("Source Git state changed; plan a separate batch")
                atomic_json(root/STATE/"manifest.json", manifest)
                if not manifest.get("inventory_complete"):
                    rows, summary = inventory(source, manifest["styles"], manifest["canary"], progress=lambda n,t,c:_planning_progress(root,db,n,t,c),canary_paths=manifest.get('canary_paths'))
                    sizes = existing_sizes(args.existing_root or source.parent)
                    storage = estimate_storage(rows, manifest["styles"], sizes, args.estimate_from)
                    require_space(root, storage["required_free_bytes"])
                    manifest = _commit_inventory(root, db, manifest, rows, summary, storage)
                else:
                    rows = read_inventory(root)
                    if canonical(rows) != manifest["inventory_sha256"]:
                        raise ValueError("Frozen inventory digest mismatch")
                    manifest = dict(manifest, items=rows)
                reused = _resume_reconcile(root, db, manifest, args.retry_failed,
                                           progress=_resume_progress(root, db, args.progress_seconds))
                log(root, "Resume verified", dict(reused_validated_outputs=reused))
                pending = counts(db)["remaining"]
                worst = max(r["estimated_bytes_per_output"] for r in manifest["storage"]["per_style"].values())
                from bulk_regeneration_plan import RESERVE
                if pending:
                    require_space(root, pending*worst+RESERVE)
                return run_batch(root, db, manifest, args.workers, args.progress_seconds)
        if not args.source:
            raise ValueError("--source is required for a new batch")
        source, root = check_paths(args.source, args.output, new=True)
        source_pin=None
        if args.source_pin or args.require_readonly_source:
            if args.source_pin is None:
                raise ValueError('Container rendering requires --source-pin')
            from bulk_source import validate_pin
            source_pin=dict(validate_pin(source,args.source_pin,args.require_readonly_source),path=str(args.source_pin))
        styles = tuple(args.styles or STYLES)
        if len(set(styles)) != len(styles):
            raise ValueError("Duplicate styles")
        source_git, renderer = git_state(source), renderer_version()
        if source_git["status"]:
            raise ValueError("Source repository has local changes; preserve and reconcile before freezing a batch")
        if args.dry_run:
            rows, summary = inventory(source, styles, args.canary, deep=args.deep_validate,canary_paths=canary_paths)
            sizes = existing_sizes(args.existing_root or source.parent)
            storage = estimate_storage(rows, styles, sizes, args.estimate_from)
            import shutil
            ancestor = root
            while not ancestor.exists():
                ancestor = ancestor.parent
            free = shutil.disk_usage(ancestor).free
            result = dict(read_only=True, source=str(source), output=str(root), source_git=source_git,
                          renderer=renderer, styles=styles, **summary, existing_posters=sizes, storage=storage,
                          free_bytes=free, disk_space_sufficient=free >= storage["required_free_bytes"],
                          issues=[dict(path=r["relative"],reason=r["issue"]) for r in rows if r["issue"]])
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0
        # Refuse obvious full-run disk shortfalls before the73GB hashing pass.
        quick_total = sum(1 for p in source.glob("*/Images/*") if p.is_file() and p.suffix.lower()==".png")
        preliminary = min(args.canary, quick_total) if args.canary else quick_total
        from bulk_regeneration_plan import RESERVE
        require_space(root, preliminary*len(styles)*int(2.5*1024**2)+RESERVE)
        db, manifest = _initial(root, source, styles, renderer, source_git, args.canary, args.workers, quick_total,source_pin,canary_paths)
        with _held_writer(root, locks):
            rows, summary = inventory(source, styles, args.canary, progress=lambda n,t,c:_planning_progress(root,db,n,t,c),canary_paths=canary_paths)
            sizes = existing_sizes(args.existing_root or source.parent)
            storage = estimate_storage(rows, styles, sizes, args.estimate_from)
            require_space(root, storage["required_free_bytes"])
            if git_state(source) != source_git:
                raise ValueError("Source Git state changed during planning")
            manifest = _commit_inventory(root, db, manifest, rows, summary, storage)
            log(root, "Inventory frozen", dict(inputs=summary["input_total"],planned_outputs=summary["planned_outputs"],
                                              source_commit=source_git["head"],renderer_id=canonical(renderer)))
            return run_batch(root, db, manifest, args.workers, args.progress_seconds)
    except KeyboardInterrupt:
        if db is not None:
            with db:
                set_meta(db, state="interrupted", phase="interrupted", updated=time.time())
            evidence(args.output, db, [])
            log(args.output, "Interrupted during preflight; resume will restart inventory without rendering completed outputs")
        return 130
    except (OSError, ValueError, sqlite3.Error) as error:
        if db is not None:
            with db:
                set_meta(db, state="failed", phase="preflight_failed", last_error=dict(summary=str(error),time=time.time()), updated=time.time())
            evidence(args.output, db, [])
            log(args.output, "Batch failed", dict(error=str(error)))
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        try:
            if db is not None:
                db.close()
        finally:
            locks.close()


def main(argv=None):
    """Docker SIGTERM is graceful during preflight as well as rendering."""
    handlers={}
    def interrupt(*_):
        raise KeyboardInterrupt
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, 'SIGBREAK', signal.SIGINT)):
            if sig not in handlers:
                handlers[sig]=signal.signal(sig,interrupt)
    try:
        return _main(argv)
    except KeyboardInterrupt:
        return 130
    finally:
        for sig,handler in handlers.items():
            signal.signal(sig,handler)


if __name__ == "__main__":
    raise SystemExit(main())
