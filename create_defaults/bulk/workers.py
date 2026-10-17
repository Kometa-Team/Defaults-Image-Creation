"""Bounded persistent spawn workers and durable, dependency-aware scheduling.

The default worker calls the approved composer API directly. The explicit probe
renderer exercises orchestration without claiming poster parity or performance.
Network services and SQLite writes stay in the long-running parent process.
"""

from dataclasses import asdict, dataclass
from itertools import islice
import gc
from hashlib import sha256 as bytes_sha256
import inspect
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import time
import uuid

import psutil

from .common import BulkError, Conflict, atomic_bytes, canonical, confined, fingerprint, path_key, sha256
from .config import Config
from .workspaces import Workspaces


def _check_inputs(payload, config):
    from .planner import renderer_identity
    expected = renderer_identity()
    if payload.get("kind") == "overlay":
        from .overlays import identity
        expected = identity()
    if payload["renderer"] != expected:
        raise BulkError("changed_renderer", "Composer implementation/environment changed after planning")
    for item in payload["inputs"]:
        root = config.output_dir if item.get("generated") else config.asset_dir
        if sha256(confined(root, item["path"], must_exist=True)) != item["sha256"]:
            raise BulkError("changed_input", "Rendering input changed after planning")


@dataclass(frozen=True)
class WorkerLimits:
    workers: int = 2
    timeout_seconds: float = 120
    retries: int = 1
    recycle_after: int = 200
    worker_memory_bytes: int = 512 * 1024 * 1024
    total_worker_memory_bytes: int = 1024 * 1024 * 1024
    max_jobs: int = 100000
    max_artifact_bytes: int = 30_000_000
    max_metadata_bytes: int = 64 * 1024 * 1024

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in (self.workers, self.recycle_after, self.worker_memory_bytes, self.total_worker_memory_bytes, self.max_jobs, self.max_artifact_bytes, self.max_metadata_bytes)) or self.workers > 32 or type(self.retries) is not int or self.retries < 0 or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise BulkError("invalid_worker_limits", "Invalid bounded worker/resource limits")
        if self.workers * self.worker_memory_bytes > self.total_worker_memory_bytes:
            raise BulkError("invalid_worker_limits", "Configured workers exceed the total worker RSS budget")


@dataclass(frozen=True)
class RenderTask:
    id: str
    render_fingerprint: str
    local_relative: str
    payload: dict
    dependencies: tuple[str, ...] = ()

    def spec(self):
        value = asdict(self)
        if len(canonical(value)) > 1_000_000:
            raise BulkError("oversize_task", "Worker tasks must contain bounded JSON metadata, not image buffers")
        path_key(self.local_relative)
        if not self.id or len(self.id) > 200 or len(self.render_fingerprint) != 64 or any(c not in "0123456789abcdef" for c in self.render_fingerprint):
            raise BulkError("invalid_task", "Task identity/fingerprint is invalid")
        return value


def compose(task, target, resources):
    """Direct validated API call; no CLI, PowerShell, ImageMagick or network."""
    from create_defaults.create_poster import PosterOptions, create_poster
    config = resources["config"]
    payload = task["payload"]
    _check_inputs(payload, config)
    if payload.get("kind") == "overlay":
        from .overlays import render
        source = confined(config.asset_dir, payload["parameters"]["input"], must_exist=True)
        render(payload["parameters"], source, target)
        return
    parameters = dict(payload["parameters"])
    for item in payload["inputs"]:
        root = config.output_dir if item.get("generated") else config.asset_dir
        path = confined(root, item["path"], must_exist=True)
        if sha256(path) != item["sha256"]:
            raise BulkError("changed_input", "Rendering input changed after planning")
        if item["role"] in {"logo", "avg_color_image", "font"}:
            parameters[item["role"]] = str(path)
    create_poster(PosterOptions(**parameters), output_path=target, asset_dir=config.asset_dir, font_dir=config.asset_dir / "fonts")


def probe_renderer(task, target, resources):
    """Small deterministic byte-output proof, never production poster artwork."""
    atomic_bytes(target, canonical(task["payload"]))
    # Mutation stays inside one unpickled request, not a reusable image/option object.
    task["payload"]["proof_mutation"] = True


def tasks_from_manifest(manifest):
    from .planner import validate_manifest
    validate_manifest(manifest)
    by_id = {job["id"]: job for job in manifest["jobs"]}
    for job in manifest["jobs"]:
        if not job["render_ready"]:
            raise BulkError("unsupported_worker_job", "Only preflight-ready contracts can use rendering workers")
        inputs = list(job["inputs"])
        for dependency in job["dependencies"]:
            inputs.append({"role": dependency["input"], "path": by_id[dependency["job_id"]]["local_relative"], "sha256": dependency["sha256"], "generated": True})
        yield RenderTask(job["id"], job["render_fingerprint"], job["local_relative"],
                         {"parameters": job["parameters"], "inputs": inputs, "renderer": manifest["renderer"], **({"kind": "overlay"} if job["kind"] == "overlay" else {})},
                         tuple(item["job_id"] for item in job["dependencies"]))


def _worker_main(inbox, results, config, limits, renderer):
    resources = {"config": config, "initialized": 1}
    process = psutil.Process()
    count = 0
    while True:
        request = inbox.get()
        if request is None:
            return
        response = {"id": request["id"], "attempt": request["attempt"], "pid": os.getpid()}
        try:
            target = confined(config.workspace_dir, request["staged_relative"])
            target.parent.mkdir(parents=True, exist_ok=True)
            renderer(request, target, resources)
            if not target.is_file() or target.stat().st_size > limits.max_artifact_bytes:
                raise BulkError("invalid_artifact", "Worker artifact absent or over byte limit")
            response.update(status="rendered", sha256=sha256(target), size=target.stat().st_size)
        except Exception as error:
            response.update(status="error", error=getattr(error, "code", type(error).__name__))
        count += 1
        gc.collect()
        memory = process.memory_info().rss
        io = process.io_counters()
        response.update(rss=memory, read_bytes=io.read_bytes, write_bytes=io.write_bytes,
                        retire=count >= limits.recycle_after or memory > limits.worker_memory_bytes)
        results.send(response)
        if response["retire"]:
            return


def _check_image(path, task=None):
    from PIL import Image
    with Image.open(path) as image:
        if task is not None and task.payload.get("kind") == "overlay":
            box = task.payload["parameters"]["box"]
            if image.format != "PNG" or image.mode != "RGBA" or not (1 <= image.width <= box[0] and 1 <= image.height <= box[1]):
                raise BulkError("invalid_artifact", "Overlay artifact violates its PNG/RGBA bounds")
            image.load()
            return
        if image.format != "JPEG" or image.mode != "RGB" or image.size != (2000, 3000):
            raise BulkError("invalid_artifact", "Composer artifact is not the approved RGB JPEG canvas")
        image.load()


class PersistentWorkers:
    def __init__(self, store, config=None, limits=None, *, renderer=compose):
        self.store, self.config, self.limits = store, config or Config(), limits or WorkerLimits()
        self.renderer = renderer
        self.renderer_identity = fingerprint(inspect.getsource(renderer))
        self.context = mp.get_context("spawn")
        self.owner = uuid.uuid4().hex
        self.slots, self.active = {}, False
        self.starts, self.recycles, self.pids = 0, 0, []

    def __enter__(self):
        if self.active:
            raise BulkError("active_pool", "Worker pool is already active")
        self.active = True
        self.workspaces = Workspaces(self.store, self.config.workspace_dir)
        self.workspace = self.workspaces.create()
        self.work_root = self.workspaces.owned(**self.workspace)
        return self

    def _start(self, index):
        inbox = self.context.Queue(maxsize=1)
        receiver, sender = self.context.Pipe(duplex=False)
        process = self.context.Process(target=_worker_main, args=(inbox, sender, self.config, self.limits, self.renderer), name=f"defaults-render-{index}")
        process.start()
        sender.close()
        self.slots[index] = {"process": process, "inbox": inbox, "results": receiver, "request": None}
        self.starts += 1
        self.pids.append(process.pid)

    def _stop(self, index, *, terminate=False):
        slot = self.slots.pop(index)
        process = slot["process"]
        if terminate:
            process.terminate()
        elif process.is_alive():
            slot["inbox"].put(None)
        process.join(timeout=3)
        if process.is_alive():
            process.kill()
            process.join(timeout=3)
        slot["inbox"].cancel_join_thread()
        slot["inbox"].close()
        slot["results"].close()
        process.close()

    def __exit__(self, *error):
        for index in list(self.slots):
            self._stop(index, terminate=self.slots[index]["request"] is not None)
        self.active = False

    def _state_id(self, task):
        return "render." + fingerprint({"id": task.id, "render": task.render_fingerprint, "root": fingerprint(str(self.config.output_dir)), "path": task.local_relative, "worker_renderer": self.renderer_identity})

    def _receipt_path(self, state_id):
        return confined(self.config.cache_dir, "worker-receipts/" + fingerprint(state_id) + ".json")

    def _cached(self, task, state_id, *, expected_renderer=None):
        path = self._receipt_path(state_id)
        target = confined(self.config.output_dir, task.local_relative)
        if not path.is_file() or not target.is_file():
            return None
        if path.stat().st_size > 1_000_000:
            raise BulkError("corrupt_receipt", "Receipt exceeds the bounded metadata limit")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return None
        payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if value.get("job_id") != state_id or value.get("render_fingerprint") != task.render_fingerprint or value.get("renderer_identity") != (expected_renderer or self.renderer_identity) or value.get("relative") != task.local_relative or value.get("receipt_sha256") != fingerprint(payload) or value.get("size") != target.stat().st_size or value.get("sha256") != sha256(target):
            return None
        if self.renderer is compose:
            _check_image(target, task)
        return value

    def _publish(self, task, state_id, source, checksum):
        if self.renderer is compose:
            _check_inputs(task.payload, self.config)
        target = confined(self.config.output_dir, task.local_relative)
        with source.open("rb") as stream:
            data = stream.read(self.limits.max_artifact_bytes + 1)
        if len(data) > self.limits.max_artifact_bytes or bytes_sha256(data).hexdigest() != checksum:
            raise BulkError("corrupt_artifact", "Staged/deduplicated bytes changed before output promotion")
        if self.renderer is compose:
            _check_image(source, task)
        # The same SQLite writer lock serializes reservation and promotion. A
        # replacement can only consume the exact bytes verified at reservation.
        with self.store.transaction() as db:
            claim = db.execute("SELECT * FROM output_claims WHERE root=? AND path_key=?",
                               (fingerprint(str(self.config.output_dir)), path_key(task.local_relative))).fetchone()
            state = db.execute("SELECT * FROM jobs WHERE id=?", (state_id,)).fetchone()
            if not claim or claim["state_id"] != state_id or state["status"] != "running" or state["owner"] != self.owner or state["expires"] <= self.store.clock():
                raise Conflict("Output promotion no longer owns its reservation and live lease")
            if target.exists():
                current = sha256(target)
                if current != checksum:
                    if current != claim["previous_sha256"]:
                        raise BulkError("output_collision", "Output differs from the verified replacement precondition")
                    atomic_bytes(target, data, replace=True)
                    self.store.event(db, "output_replaced", state_id,
                                     {"previous_state_id": claim["previous_state_id"], "previous_sha256": current, "sha256": checksum})
            elif claim["previous_sha256"] is not None:
                raise BulkError("corrupt_artifact", "Previously verified output disappeared before replacement")
            else:
                atomic_bytes(target, data)
        row = self.store.job(state_id)
        receipt = {"schema_version": 1, "job_id": state_id, "logical_id": task.id, "job_fingerprint": row["fingerprint"],
                   "render_fingerprint": task.render_fingerprint, "renderer_identity": self.renderer_identity,
                   "relative": task.local_relative, "sha256": checksum, "size": target.stat().st_size}
        receipt["receipt_sha256"] = fingerprint(receipt)
        path = self._receipt_path(state_id)
        if path.exists():
            if path.read_bytes() != canonical(receipt):
                raise BulkError("corrupt_receipt", "Output receipt conflicts with retained evidence")
        else:
            atomic_bytes(path, canonical(receipt))
        self.store.transition(state_id, row["version"], "verified", owner=self.owner, receipt=receipt)
        return receipt

    def run(self, tasks, *, cancel=None, retry_failed=False):
        # Keep WAL open across short transactions; the last-close checkpoint must
        # not be repeated for every receipt on Windows. No transaction is held.
        with self.store.connection() as anchor:
            anchor.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return self._run(tasks, cancel=cancel, retry_failed=retry_failed)

    def _run(self, tasks, *, cancel=None, retry_failed=False):
        if not self.active:
            raise BulkError("inactive_pool", "Use PersistentWorkers as a context manager")
        started, initial_starts = time.monotonic(), self.starts
        initial_recycles = self.recycles
        self.pids = [slot["process"].pid for slot in self.slots.values()]
        catalog, destinations, materials, metadata_bytes = {}, set(), {}, 0
        for task in tasks:
            encoded = canonical(task.spec())
            metadata_bytes += len(encoded)
            if metadata_bytes > self.limits.max_metadata_bytes:
                raise BulkError("oversize_plan", "Task metadata exceeds the configured bounded catalog budget")
            frozen = json.loads(encoded)
            task = RenderTask(frozen["id"], frozen["render_fingerprint"], frozen["local_relative"], frozen["payload"], tuple(frozen["dependencies"]))
            if len(catalog) >= self.limits.max_jobs or task.id in catalog or path_key(task.local_relative) in destinations:
                raise BulkError("output_collision", "Duplicate task/output or configured job-count limit exceeded")
            material = fingerprint(task.payload)
            if task.render_fingerprint in materials and materials[task.render_fingerprint] != material:
                raise BulkError("fingerprint_collision", "Different rendering payloads cannot share a deduplication fingerprint")
            materials[task.render_fingerprint] = material
            catalog[task.id] = task
            destinations.add(path_key(task.local_relative))
        visiting, visited = set(), set()
        def visit(identity):
            if identity in visiting or identity not in catalog:
                raise BulkError("invalid_dependency", "Missing/cyclic dependency in worker plan")
            if identity in visited:
                return
            visiting.add(identity)
            for parent in catalog[identity].dependencies:
                visit(parent)
            visiting.remove(identity)
            visited.add(identity)
        for identity in catalog:
            visit(identity)
        completed, attempts, waiting, running_fingerprints, receipts = {}, {}, set(catalog), set(), {}
        metrics = {"executed": 0, "cache_hits": 0, "dedup_reuses": 0, "max_inflight": 0, "peak_worker_rss": 0,
                   "peak_workers_rss_sum": 0, "peak_parent_rss": 0, "read_bytes": 0, "write_bytes": 0}
        io_samples = {}
        initial_io = {}
        for slot in self.slots.values():
            try:
                counters = psutil.Process(slot["process"].pid).io_counters()
                initial_io[slot["process"].pid] = (counters.read_bytes, counters.write_bytes)
            except psutil.Error:
                pass
        self.store.recover()
        root_id = fingerprint(str(self.config.output_dir))
        states = {}
        pending = iter(catalog.values())
        while page := list(islice(pending, 64)):
            with self.store.transaction() as db:
                workspace = db.execute("SELECT * FROM workspaces WHERE id=?", (self.workspace["identity"],)).fetchone()
                if workspace["token"] != self.workspace["token"] or workspace["status"] != "active":
                    raise Conflict("Workspace cleanup began before scheduling")
                for task in page:
                    state_id = self._state_id(task)
                    target = confined(self.config.output_dir, task.local_relative)
                    claim = db.execute("SELECT * FROM output_claims WHERE root=? AND path_key=?", (root_id, path_key(task.local_relative))).fetchone()
                    if claim is not None and claim["state_id"] != state_id:
                        bound = db.execute("SELECT * FROM jobs WHERE id=?", (claim["state_id"],)).fetchone()
                        bound_spec = json.loads(bound["spec"]) if bound else {}
                        expected_spec = {"task": task.spec(), "renderer_identity": self.renderer_identity}
                        if bound and canonical(bound_spec) == canonical(expected_spec):
                            state_id = claim["state_id"]
                        elif db.execute("SELECT 1 FROM jobs WHERE id=?", (state_id,)).fetchone():
                            # A return to an older fingerprint is a new output
                            # generation, not mutation of its terminal receipt.
                            state_id = "render." + fingerprint({"base": state_id, "previous": claim["state_id"]})
                    states[task.id] = state_id
                    if claim is None:
                        if target.exists():
                            raise BulkError("output_collision", "Refusing to adopt an unowned existing output")
                        db.execute("INSERT INTO output_claims(root,path_key,relative,state_id,fingerprint) VALUES (?,?,?,?,?)", (root_id, path_key(task.local_relative), task.local_relative, state_id, task.render_fingerprint))
                    elif claim["state_id"] != state_id:
                        old = db.execute("SELECT * FROM jobs WHERE id=?", (claim["state_id"],)).fetchone()
                        old_spec = json.loads(old["spec"]) if old else {}
                        if not old or old["status"] != "verified" or fingerprint(old_spec) != old["fingerprint"] or old_spec["task"]["id"] != task.id or claim["relative"] != task.local_relative:
                            raise BulkError("output_collision", "Output is reserved by another job or unfinished replacement")
                        previous = RenderTask(**old_spec["task"])
                        receipt = self._cached(previous, claim["state_id"], expected_renderer=old_spec["renderer_identity"])
                        if receipt is None or old["receipt"] != canonical(receipt).decode():
                            raise BulkError("corrupt_artifact", "Cannot replace an unverified or corrupted owned output")
                        db.execute("UPDATE output_claims SET state_id=?,fingerprint=?,previous_sha256=?,previous_state_id=? WHERE root=? AND path_key=?",
                                   (state_id, task.render_fingerprint, receipt["sha256"], claim["state_id"], root_id, path_key(task.local_relative)))
                        self.store.event(db, "output_replacement_reserved", state_id,
                                         {"previous_state_id": claim["state_id"], "previous_sha256": receipt["sha256"]})
                    self.store.add_job_in_transaction(db, state_id, {"task": task.spec(), "renderer_identity": self.renderer_identity})
                    db.execute("INSERT OR IGNORE INTO workspace_jobs VALUES (?,?)", (self.workspace["identity"], state_id))
                    self.store.event(db, "workspace_job_bound", self.workspace["identity"], {"job": state_id})

        def claim_job(identity):
            state = self.store.job(states[identity])
            if state["status"] == "running":
                raise Conflict("A live orchestrator already owns this job")
            return self.store.transition(states[identity], state["version"], "running", owner=self.owner,
                                         lease_seconds=max(60, math.ceil(self.limits.timeout_seconds * 3 + 30)))

        def failure(index, reason):
            request = self.slots[index]["request"]
            identity = request["id"]
            running_fingerprints.discard(catalog[identity].render_fingerprint)
            row = self.store.job(states[identity])
            self.store.transition(states[identity], row["version"], "failed", owner=self.owner)
            self._stop(index, terminate=True)
            if attempts[identity] <= self.limits.retries:
                waiting.add(identity)
            else:
                completed[identity] = {"status": "failed", "reason": reason}

        try:
            while waiting or any(slot["request"] for slot in self.slots.values()):
                if cancel is not None and cancel.is_set():
                    for index in list(self.slots):
                        request = self.slots[index]["request"]
                        if request:
                            row = self.store.job(states[request["id"]])
                            self.store.transition(states[request["id"]], row["version"], "interrupted", owner=self.owner)
                            completed[request["id"]] = {"status": "interrupted"}
                        self._stop(index, terminate=True)
                    completed.update({identity: {"status": "cancelled_pending"} for identity in waiting})
                    waiting.clear()
                    break
                for identity in sorted(list(waiting)):
                    task = catalog[identity]
                    parents = [completed.get(parent) for parent in task.dependencies]
                    if any(parent and parent["status"] not in {"rendered", "cache_reuse", "dedup_reuse"} for parent in parents):
                        completed[identity] = {"status": "blocked_dependency"}
                        waiting.remove(identity)
                        continue
                    if any(parent is None for parent in parents):
                        continue
                    if self.renderer is compose:
                        _check_inputs(task.payload, self.config)
                    state = self.store.job(states[identity])
                    cached = self._cached(task, states[identity])
                    if cached is not None and state["status"] == "verified":
                        if state["receipt"] != canonical(cached).decode():
                            raise BulkError("corrupt_receipt", "Receipt differs from the finalized database evidence")
                        receipts[task.render_fingerprint] = cached
                        completed[identity] = {"status": "cache_reuse", "sha256": cached["sha256"]}
                        metrics["cache_hits"] += 1
                        waiting.remove(identity)
                        continue
                    if state["status"] == "verified":
                        raise BulkError("corrupt_artifact", "Verified output/receipt is absent or corrupt; repair requires explicit action")
                    if state["status"] == "failed" and not retry_failed and identity not in attempts:
                        completed[identity] = {"status": "failed_not_retried"}
                        waiting.remove(identity)
                        continue
                    existing = receipts.get(task.render_fingerprint)
                    if existing:
                        claim_job(identity)
                        source = confined(self.config.output_dir, existing["relative"], must_exist=True)
                        receipt = self._publish(task, states[identity], source, existing["sha256"])
                        completed[identity] = {"status": "dedup_reuse", "sha256": receipt["sha256"]}
                        metrics["dedup_reuses"] += 1
                        waiting.remove(identity)
                        continue
                    if task.render_fingerprint in running_fingerprints:
                        continue
                    idle = next((index for index, slot in self.slots.items() if slot["request"] is None), None)
                    if idle is None and len(self.slots) < self.limits.workers:
                        idle = next(index for index in range(self.limits.workers) if index not in self.slots)
                        self._start(idle)
                    if idle is None:
                        break
                    claim_job(identity)
                    attempts[identity] = attempts.get(identity, 0) + 1
                    relative = self.work_root.relative_to(self.config.workspace_dir).as_posix() + "/jobs/" + fingerprint(identity) + f"/attempt-{attempts[identity]}-{uuid.uuid4().hex}/artifact" + (".jpg" if self.renderer is compose else ".bin")
                    request = {**task.spec(), "attempt": attempts[identity], "staged_relative": relative}
                    self.slots[idle].update(request=request, started=time.monotonic())
                    self.slots[idle]["inbox"].put(request)
                    running_fingerprints.add(task.render_fingerprint)
                    waiting.remove(identity)
                    metrics["executed"] += 1
                    metrics["max_inflight"] = max(metrics["max_inflight"], sum(slot["request"] is not None for slot in self.slots.values()))
                response = None
                for slot in self.slots.values():
                    try:
                        if slot["results"].poll():
                            response = slot["results"].recv()
                    except (EOFError, OSError):
                        # Windows poll itself raises BrokenPipeError after a
                        # hard worker exit; the owned-process check recovers it.
                        pass
                    if response is not None:
                        break
                if response is None:
                    time.sleep(.01)
                if response is not None:
                    index = next((index for index, slot in self.slots.items() if slot["request"] and slot["request"]["id"] == response["id"] and slot["request"]["attempt"] == response["attempt"] and slot["process"].pid == response["pid"]), None)
                    if index is not None:
                        metrics["peak_worker_rss"] = max(metrics["peak_worker_rss"], response["rss"])
                        io_samples[response["pid"]] = (response["read_bytes"], response["write_bytes"])
                        if response["status"] == "error":
                            failure(index, response["error"])
                        else:
                            request = self.slots[index]["request"]
                            task = catalog[request["id"]]
                            source = confined(self.config.workspace_dir, request["staged_relative"], must_exist=True)
                            receipt = self._publish(task, states[task.id], source, response["sha256"])
                            completed[task.id] = {"status": "rendered", "sha256": receipt["sha256"], "pid": response["pid"]}
                            receipts[task.render_fingerprint] = receipt
                            running_fingerprints.discard(task.render_fingerprint)
                            self.slots[index]["request"] = None
                            if response["retire"]:
                                self.recycles += 1
                                self._stop(index)
                total_rss = 0
                for index in list(self.slots):
                    slot = self.slots[index]
                    request = slot["request"]
                    if not slot["process"].is_alive():
                        if request:
                            failure(index, "worker_exit")
                        else:
                            self._stop(index)
                        continue
                    try:
                        rss = psutil.Process(slot["process"].pid).memory_info().rss
                    except psutil.Error:
                        continue
                    total_rss += rss
                    metrics["peak_worker_rss"] = max(metrics["peak_worker_rss"], rss)
                    if request and (rss > self.limits.worker_memory_bytes or time.monotonic() - slot["started"] > self.limits.timeout_seconds):
                        failure(index, "memory_limit" if rss > self.limits.worker_memory_bytes else "timeout")
                    elif not request and rss > self.limits.worker_memory_bytes:
                        self.recycles += 1
                        self._stop(index)
                metrics["peak_workers_rss_sum"] = max(metrics["peak_workers_rss_sum"], total_rss)
                metrics["peak_parent_rss"] = max(metrics["peak_parent_rss"], psutil.Process().memory_info().rss)
        except BaseException:
            for index in list(self.slots):
                request = self.slots[index]["request"]
                if request:
                    row = self.store.job(states[request["id"]])
                    if row["status"] == "running" and row["owner"] == self.owner:
                        self.store.transition(states[request["id"]], row["version"], "interrupted", owner=self.owner)
                self._stop(index, terminate=True)
            raise
        metrics.update(wall_seconds=time.monotonic() - started, worker_starts=self.starts - initial_starts,
                       worker_pids=list(self.pids), worker_recycles=self.recycles - initial_recycles, process_start="spawn",
                       read_bytes=sum(max(0, value[0] - initial_io.get(pid, (0, 0))[0]) for pid, value in io_samples.items()),
                       write_bytes=sum(max(0, value[1] - initial_io.get(pid, (0, 0))[1]) for pid, value in io_samples.items()))
        metrics["jobs_per_second"] = len(completed) / metrics["wall_seconds"] if metrics["wall_seconds"] else 0
        metrics["cache_hit_rate"] = metrics["cache_hits"] / len(catalog) if catalog else 0
        metrics["retry_attempts"] = sum(max(0, count - 1) for count in attempts.values())
        metrics["failures"] = sum(item["status"] in {"failed", "failed_not_retried", "blocked_dependency"} for item in completed.values())
        return {"jobs": completed, "metrics": metrics, "scope": "infrastructure execution; not publication approval or production benchmark"}
