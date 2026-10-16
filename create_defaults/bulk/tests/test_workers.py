from dataclasses import replace
import os
import time

import pytest

from create_defaults.bulk.common import BulkError, atomic_bytes, canonical, fingerprint, sha256
from create_defaults.bulk.config import Config
from create_defaults.bulk.state import Store
from create_defaults.bulk.workers import PersistentWorkers, RenderTask, WorkerLimits, compose, probe_renderer


def fault_renderer(task, target, resources):
    payload = task["payload"]
    if payload.get("crash_first") and task["attempt"] == 1:
        os._exit(73)
    if payload.get("error_first") and task["attempt"] == 1:
        raise RuntimeError("Deliberate recovery proof")
    if payload.get("slow_first") and task["attempt"] == 1:
        time.sleep(10)
    if payload.get("dependency"):
        parent = resources["config"].output_dir / payload["dependency"]
        assert parent.is_file()
    assert resources["initialized"] == 1
    assert "proof_mutation" not in payload
    probe_renderer(task, target, resources)


@pytest.fixture
def setup(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    config = Config(asset_dir=assets, cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work", output_dir=tmp_path / "out")
    return Store(config.cache_dir / "state.sqlite"), config


def task(index, payload=None, dependencies=()):
    payload = {"number": index} if payload is None else payload
    return RenderTask(f"proof.{index}", fingerprint(payload), f"proof/{index}.bin", payload, dependencies)


def test_hundreds_fixed_workers_cache_dedup_and_no_state_leak(setup, monkeypatch):
    import subprocess
    store, config = setup
    def forbidden(*args, **kwargs):
        raise AssertionError("A renderer must not launch a CLI subprocess")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    jobs = [task(index) for index in range(300)]
    jobs.append(task("duplicate", {"number": 0}))
    limits = WorkerLimits(workers=2, recycle_after=1000)
    with PersistentWorkers(store, config, limits, renderer=probe_renderer) as pool:
        report = pool.run(iter(jobs))
        cached = pool.run(jobs)
    metrics = report["metrics"]
    assert len(report["jobs"]) == 301
    assert metrics["executed"] == 300 and metrics["dedup_reuses"] == 1
    assert metrics["worker_starts"] == 2 and len(metrics["worker_pids"]) == 2
    assert metrics["max_inflight"] == 2 and metrics["process_start"] == "spawn"
    assert metrics["peak_workers_rss_sum"] <= limits.total_worker_memory_bytes
    assert metrics["peak_parent_rss"] < 512 * 1024 * 1024
    assert cached["metrics"]["executed"] == 0 and cached["metrics"]["cache_hits"] == 301
    assert all("proof_mutation" not in item.payload for item in jobs)
    assert (config.output_dir / "proof/0.bin").read_bytes() == canonical({"number": 0})
    assert (config.output_dir / "proof/duplicate.bin").read_bytes() == canonical({"number": 0})
    assert all(not slot for slot in pool.slots.values())
    # Retained only in pytest's temporary evidence; this is not a poster benchmark.
    atomic_bytes(config.cache_dir / "synthetic-worker-proof.json", canonical(report))


@pytest.mark.parametrize("fault", ["crash_first", "error_first", "slow_first"])
def test_worker_recovery_and_timeout(setup, fault):
    store, config = setup
    limits = WorkerLimits(workers=1, timeout_seconds=3, retries=1)
    with PersistentWorkers(store, config, limits, renderer=fault_renderer) as pool:
        result = pool.run([task(1, {fault: True})])
    assert result["jobs"]["proof.1"]["status"] == "rendered"
    assert result["metrics"]["executed"] == 2 and result["metrics"]["worker_starts"] == 2


def test_cancel_resume_dependency_and_recycling(setup):
    store, config = setup
    class CancelAfterDispatch:
        def is_set(self):
            with store.connection() as db:
                return bool(db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone())
    jobs = [task(0, {"slow_first": True}), task(1, {"dependency": "proof/0.bin"}, ("proof.0",))]
    with PersistentWorkers(store, config, WorkerLimits(workers=1, recycle_after=1), renderer=fault_renderer) as pool:
        interrupted = pool.run(jobs, cancel=CancelAfterDispatch())
    assert interrupted["jobs"]["proof.0"]["status"] == "interrupted"
    assert interrupted["jobs"]["proof.1"]["status"] == "cancelled_pending"
    assert not (config.output_dir / "proof/0.bin").exists()
    # Resume uses a fresh pool, not an in-memory task/result shortcut.
    with PersistentWorkers(store, config, WorkerLimits(workers=1, recycle_after=1, timeout_seconds=3), renderer=fault_renderer) as pool:
        resumed = pool.run(jobs)
    assert all(item["status"] == "rendered" for item in resumed["jobs"].values())
    assert resumed["metrics"]["worker_recycles"] == 2


def test_collisions_cycles_and_corruption_fail_closed(setup):
    store, config = setup
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        for jobs in ([task(1), replace(task(2), local_relative="proof/1.bin")],
                     [task(1, dependencies=("proof.2",)), task(2, dependencies=("proof.1",))],
                     [task(1), replace(task(2), render_fingerprint=task(1).render_fingerprint)]):
            with pytest.raises(BulkError):
                pool.run(jobs)
        assert pool.starts == 0
        pool.run([task(1)])
        (config.output_dir / "proof/1.bin").write_bytes(b"corrupt")
        with pytest.raises(BulkError, match="corrupt"):
            pool.run([task(1)])
        with pytest.raises(BulkError):
            pool.run([replace(task(2), local_relative="proof/1.bin")])


def test_worker_count_does_not_change_bytes_or_overwrite_unowned_output(setup):
    store, config = setup
    jobs = [task(i) for i in range(6)]
    with PersistentWorkers(store, config, WorkerLimits(workers=1), renderer=probe_renderer) as pool:
        one = pool.run(jobs)
    other = replace(config, output_dir=config.output_dir.parent / "other")
    with PersistentWorkers(store, other, WorkerLimits(workers=3, total_worker_memory_bytes=1536 * 1024 * 1024), renderer=probe_renderer) as pool:
        three = pool.run(jobs)
        atomic_bytes(other.output_dir / "proof/unowned.bin", b"preexisting")
        with pytest.raises(BulkError, match="unowned"):
            pool.run([task("unowned")])
    assert {key: item["sha256"] for key, item in one["jobs"].items()} == {key: item["sha256"] for key, item in three["jobs"].items()}


def test_composer_adapter_calls_api_without_subprocess_and_rechecks_cache(setup, monkeypatch):
    from create_defaults import create_poster
    from create_defaults.bulk.planner import renderer_identity
    store, config = setup
    source = config.asset_dir / "input.bin"
    source.write_bytes(b"original")
    payload = {"parameters": {}, "inputs": [{"role": "shared", "path": "input.bin", "sha256": sha256(source)}], "renderer": renderer_identity()}
    called = []
    monkeypatch.setattr(create_poster, "create_poster", lambda options, **kwargs: called.append(kwargs))
    compose({"payload": payload}, config.workspace_dir / "output.jpg", {"config": config})
    assert len(called) == 1
    source.write_bytes(b"changed")
    with PersistentWorkers(store, config, renderer=compose) as pool:
        with pytest.raises(BulkError, match="input changed"):
            pool.run([task(1, payload)])
        assert pool.starts == 0


def test_resource_limits_and_explicit_failed_retry(setup):
    store, config = setup
    with pytest.raises(BulkError):
        WorkerLimits(workers=3)
    jobs = [task(1, {"error_first": True})]
    with PersistentWorkers(store, config, WorkerLimits(workers=1, retries=0), renderer=fault_renderer) as pool:
        first = pool.run(jobs)
        assert first["jobs"]["proof.1"]["status"] == "failed"
        assert pool.run(jobs)["jobs"]["proof.1"]["status"] == "failed_not_retried"
        retried = pool.run(jobs, retry_failed=True)
        # Explicit retry starts a new attempt sequence; retries=0 still fails once.
        assert retried["jobs"]["proof.1"]["status"] == "failed"


def test_interrupted_promotion_resumes_matching_owned_bytes(setup, monkeypatch):
    store, config = setup
    transition = store.transition
    def stop_before_verification(identity, version, status, **kwargs):
        if status == "verified":
            raise RuntimeError("Interruption after atomic output and receipt promotion")
        return transition(identity, version, status, **kwargs)
    monkeypatch.setattr(store, "transition", stop_before_verification)
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        with pytest.raises(RuntimeError, match="Interruption"):
            pool.run([task(1)])
    original = sha256(config.output_dir / "proof/1.bin")
    monkeypatch.setattr(store, "transition", transition)
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        resumed = pool.run([task(1)])
    assert resumed["jobs"]["proof.1"]["status"] == "rendered"
    assert resumed["jobs"]["proof.1"]["sha256"] == original


def test_memory_and_metadata_limits_are_enforced(setup):
    store, config = setup
    with PersistentWorkers(store, config, WorkerLimits(workers=1, worker_memory_bytes=1, retries=0), renderer=probe_renderer) as pool:
        result = pool.run([task(1, {"slow_first": True})])
        assert result["jobs"]["proof.1"]["status"] == "failed"
        assert result["jobs"]["proof.1"]["reason"] == "memory_limit"
    with PersistentWorkers(store, config, WorkerLimits(max_metadata_bytes=1), renderer=probe_renderer) as pool:
        with pytest.raises(BulkError, match="metadata"):
            pool.run([task(2)])
        assert pool.starts == 0


def test_changed_owned_output_is_replaced_and_unchanged_output_is_cached(setup):
    store, config = setup
    before = [task(0), task(1)]
    after = [task(0, {"number": 42}), task(1)]
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        pool.run(before)
        changed = pool.run(after)
        warm = pool.run(after)
        restored = pool.run(before)
        restored_warm = pool.run(before)
    assert changed["metrics"]["executed"] == 1
    assert changed["metrics"]["cache_hits"] == 1
    assert warm["metrics"]["cache_hits"] == 2
    assert restored["metrics"]["executed"] == 1
    assert restored_warm["metrics"]["cache_hits"] == 2
    assert (config.output_dir / "proof/0.bin").read_bytes() == canonical({"number": 0})
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind='output_replaced'").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM jobs WHERE status='verified'").fetchone()[0] == 4


def test_replacement_rejects_changed_bytes_and_other_logical_owner(setup):
    store, config = setup
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        pool.run([task(0)])
        with pytest.raises(BulkError, match="another job"):
            pool.run([replace(task(1), local_relative="proof/0.bin")])
        (config.output_dir / "proof/0.bin").write_bytes(b"external edit")
        with pytest.raises(BulkError, match="corrupt"):
            pool.run([task(0, {"number": 42})])


def test_interrupted_replacement_resumes_without_adopting_external_bytes(setup, monkeypatch):
    store, config = setup
    before, after = task(0), task(0, {"number": 42})
    transition = store.transition
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        pool.run([before])
        def interrupt(identity, version, status, **kwargs):
            if status == "verified":
                raise RuntimeError("replacement interrupted after promotion")
            return transition(identity, version, status, **kwargs)
        monkeypatch.setattr(store, "transition", interrupt)
        with pytest.raises(RuntimeError, match="interrupted"):
            pool.run([after])
    monkeypatch.setattr(store, "transition", transition)
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        result = pool.run([after])
    assert result["jobs"][after.id]["status"] == "rendered"
    assert (config.output_dir / after.local_relative).read_bytes() == canonical(after.payload)
