"""Package E integration proofs. Synthetic review decisions stay in pytest tmp dirs."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sqlite3

from PIL import Image
import pytest
import yaml

from create_defaults.bulk.catalog import load_catalog
from create_defaults.bulk.common import BulkError, Conflict, fingerprint, sha256
from create_defaults.bulk.config import Config, ROOT
from create_defaults.bulk.definitions import Definition
from create_defaults.bulk.delta import validation_delta
from create_defaults.bulk.e_network import BudgetSession
from create_defaults.bulk.e_validation import ResourceGuard
from create_defaults.bulk.generation import generate
from create_defaults.bulk.planner import Planner, SHARED_ASSETS
from create_defaults.bulk.preflight import preflight, variant_id
from create_defaults.bulk.review import Reviews
from create_defaults.bulk.state import Store
from create_defaults.bulk.translations import Translations
from create_defaults.bulk.workers import WorkerLimits


@pytest.fixture
def synthetic_pair(tmp_path):
    assets = tmp_path / "assets"
    paths = {*SHARED_ASSETS, "fonts/Comfortaa-Medium.ttf", "fonts/Barlow-Regular.ttf"}
    for relative in paths:
        target = assets / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    Image.new("RGBA", (120, 120), (255, 0, 0, 150)).save(assets / "one-logo.png")
    definitions = []
    source = {"key_names": {}}
    for index, item in enumerate(load_catalog(["Based"])[:2]):
        value = item.data
        value["layout"] = {"kind": "fixed", "measurement": None}
        value["composer"]["font_size"] = 100
        value["composer"]["logo"] = "one-logo.png" if index == 0 else "transparent.png"
        source["key_names"][value["caption"]["key"].split(".")[-1]] = "Synthetic " + str(index)
        definitions.append(Definition.create(value))
    file = tmp_path / "en.yml"
    file.write_text(yaml.safe_dump(source), encoding="utf-8")
    config = Config(asset_dir=assets, cache_dir=tmp_path / "cache",
                    output_dir=tmp_path / "output", workspace_dir=tmp_path / "work")
    return definitions, file, config


@pytest.mark.parametrize("change", ["definition", "logo", "color", "font", "caption"])
def test_exact_invalidation_and_actual_rerender_set(synthetic_pair, change):
    definitions, source, config = synthetic_pair
    options = dict(config=config, categories=["Based"], limits=WorkerLimits(workers=1))
    translated = Translations({"en": source})
    first = generate(definitions, translated, **options)
    assert first["status"] == "verified"
    expected = {variant_id(definitions[0].id, "en")}  # Calculated before mutation/execution.
    unrelated = variant_id(definitions[1].id, "en")
    old_jobs = {j["id"]: j for j in first["manifest"]["jobs"]}
    untouched = config.output_dir / old_jobs[unrelated]["local_relative"]
    untouched_sha = sha256(untouched)
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    reviews.attach(first)
    for variant in first["preflight"]["variants"]:
        item = reviews.item(variant["id"])
        warnings = [d["code"] for d in variant["diagnostics"] if d["severity"] == "warning"]
        reviews.decide(variant["id"], expected_version=item["version"], action="approve",
            reviewer="synthetic-regression-test-only", accepted_warnings=warnings,
            comment="Ephemeral synthetic review mechanics; no maintainer artwork acceptance.")

    value = definitions[0].data
    if change == "definition":
        value["composer"]["gradient"] = 2
    elif change == "color":
        value["composer"]["base_color"] = "#123456"
    elif change == "font":
        value["composer"]["font"] = "fonts/Barlow-Regular.ttf"
    elif change == "logo":
        with Image.open(config.asset_dir / "one-logo.png") as image:
            image.putpixel((60, 60), (0, 255, 0, 255))
            image.save(config.asset_dir / "one-logo.png")
    else:
        data = yaml.safe_load(source.read_text())
        data["key_names"][value["caption"]["key"].split(".")[-1]] = "Changed synthetic"
        source.write_text(yaml.safe_dump(data), encoding="utf-8")
    changed = (Definition.create(value), definitions[1])
    updated_translated = Translations({"en": source})
    predicted = Planner(config).plan(changed, updated_translated, categories=["Based"])
    observed_plan = {j["id"] for j in predicted["jobs"]
                     if j["render_fingerprint"] != old_jobs[j["id"]]["render_fingerprint"]}
    assert observed_plan == expected
    report, _ = preflight(changed, updated_translated, config=config, categories=["Based"])
    assert set(validation_delta(first["preflight"], report)["changed"]) == expected
    reviews.ingest(report)
    assert {item["id"] for item in reviews.query(["stale"])} == expected
    assert reviews.item(unrelated)["state"] in {"approved", "approved_with_accepted_warnings"}
    result = generate(changed, updated_translated, **options)
    rendered = {identity for stage in result["stages"] for identity, row in stage["execution"]["jobs"].items() if row["status"] == "rendered"}
    assert rendered == expected
    assert sha256(untouched) == untouched_sha
    warm = generate(changed, updated_translated, **options)
    assert all(stage["execution"]["metrics"]["executed"] == stage["execution"]["metrics"]["worker_starts"] == 0 for stage in warm["stages"])


def test_source_change_with_same_size_and_mtime_is_not_hidden(synthetic_pair):
    definitions, source, config = synthetic_pair
    translated = Translations({"en": source})
    options = dict(config=config, categories=["Based"], limits=WorkerLimits(workers=1))
    first = generate(definitions, translated, **options)
    path = config.output_dir / first["manifest"]["jobs"][0]["local_relative"]
    before = path.stat()
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 1
    path.write_bytes(data)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(BulkError, match="corrupt"):
        generate(definitions, translated, **options)


def test_unapproved_changed_font_blocks_without_overwriting_verified_output(synthetic_pair):
    definitions, source, config = synthetic_pair
    translated = Translations({"en": source})
    first = generate(definitions, translated, config=config, categories=["Based"], limits=WorkerLimits(workers=1))
    before = {p: sha256(p) for p in config.output_dir.rglob("*.jpg")}
    path = config.asset_dir / "fonts/Comfortaa-Medium.ttf"
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    result = generate(definitions, translated, config=config, categories=["Based"], policy="strict")
    assert result["status"] == "strict_blocked" and not result["stages"]
    assert before == {p: sha256(p) for p in config.output_dir.rglob("*.jpg")}
    assert any(d["code"] == "unapproved_font" for v in result["preflight"]["variants"] for d in v["diagnostics"])


@pytest.mark.parametrize("reason", ["free_disk_floor", "output_byte_limit", "wall_time_limit", "explicit_stop_file"])
def test_acceptance_guard_enforces_bounds(tmp_path, reason):
    (tmp_path / "output").mkdir()
    (tmp_path / "output/example").write_bytes(b"x")
    guard = ResourceGuard(tmp_path, min_free=0, max_output=100, seconds=100)
    if reason == "free_disk_floor":
        guard.min_free = shutil.disk_usage(tmp_path).total + 1
    elif reason == "output_byte_limit":
        guard.max_output = 0
    elif reason == "wall_time_limit":
        guard.seconds = -1
    else:
        (tmp_path / "STOP").touch()
    guard._sample()
    assert guard.reason == reason and guard.is_set()


@pytest.mark.parametrize("method,url", [
    ("POST", "https://api.github.com/repos/Kometa-Team/Default-Images/git/refs"),
    ("GET", "https://api.github.com/repos/another/repository/git/trees/abc"),
    ("GET", "https://example.org/repos/Kometa-Team/Default-Images/file"),
])
def test_acceptance_network_rejects_mutations_and_other_repositories(method, url):
    session = BudgetSession("Kometa-Team/Default-Images")
    with pytest.raises(BulkError, match="Only GET"):
        session.request(method, url)
    assert not session.observations


def test_package_d_maintainer_acceptance_stays_four_exact_external_samples():
    root = ROOT / "bulk/evidence/package-d"
    decision = json.loads((root / "maintainer-visual-acceptance-20261017.json").read_text())
    events = json.loads((root / "maintainer-visual-acceptance-20261017-events.json").read_text())
    for value in (decision, events):
        assert fingerprint({k: v for k, v in value.items() if k != "sha256"}) == value["sha256"]
    assert len(decision["decisions"]) == len(events["events"]) == 4
    assert events["acceptance_record_sha256"] == decision["sha256"]
    assert events["runtime_approvals_created"] == 0
    assert {d["artifact_image"] for d in decision["decisions"]} == {
        "output/defaults-en/based/Book.jpg", "output/defaults-fr/based/Book.jpg",
        "output/genre/overlays/standard/Experimental.png",
        "output/genre/overlays/bigger/Experimental.png",
    }
    assert {d["decision_id"] for d in decision["decisions"]} == {e["subject"] for e in events["events"]}
    assert all(d["runtime_review_state_changed"] is False for d in decision["decisions"])
    assert decision["french_proposal"]["activated"] is False
    assert decision["pending_variants"][0]["language"] == "ar"
    historical = decision["historical_pixel_difference_evidence"]
    assert sha256(ROOT.parent / historical["path"]) == historical["file_sha256"]



def test_cached_posters_recheck_hashes_and_headers_without_redecoding(synthetic_pair, monkeypatch):
    import create_defaults.bulk.workers as module
    definitions, source, config = synthetic_pair
    translated = Translations({"en": source})
    options = dict(config=config, categories=["Based"], limits=WorkerLimits(workers=1))
    first = generate(definitions, translated, **options)
    original = module._check_image
    calls = []
    def checked(path, task=None, *, decode=True):
        calls.append(decode)
        return original(path, task, decode=decode)
    monkeypatch.setattr(module, "_check_image", checked)
    warm = generate(definitions, translated, **options)
    assert calls and not any(calls)
    assert warm["manifest"] == first["manifest"]
    assert all(s["execution"]["metrics"]["executed"] == 0 for s in warm["stages"])
    # A hash-valid-looking receipt cannot supersede finalized database evidence.
    store = Store(config.cache_dir / "state.sqlite")
    with store.connection() as db:
        state_id = db.execute("SELECT id FROM jobs WHERE status='verified' LIMIT 1").fetchone()[0]
    with module.PersistentWorkers(store, config) as pool:
        path = pool._receipt_path(state_id)
    value = json.loads(path.read_text())
    value["unexpected"] = "external receipt edit"
    value["receipt_sha256"] = fingerprint({k: v for k, v in value.items() if k != "receipt_sha256"})
    path.write_text(json.dumps(value))
    with pytest.raises(BulkError, match="Receipt differs"):
        generate(definitions, translated, **options)


def test_library_metadata_cache_is_immutable_but_source_changes_are_rechecked(monkeypatch):
    import create_defaults.bulk.planner as module
    real_version, read_text = module.version, Path.read_text
    calls = []
    def read_version(name):
        calls.append(name)
        return real_version(name)
    module._loaded_library_versions.cache_clear()
    monkeypatch.setattr(module, "version", read_version)
    try:
        first = module.renderer_identity()
        first["libraries"]["Pillow"] = "caller mutation"
        second = module.renderer_identity()
        assert second["libraries"]["Pillow"] != "caller mutation"
        assert len(calls) == 4
        def changed_text(self, *args, **kwargs):
            text = read_text(self, *args, **kwargs)
            return text + "\n# simulated source update\n" if self == ROOT / "poster_text.py" else text
        monkeypatch.setattr(Path, "read_text", changed_text)
        changed = module.renderer_identity()
        assert changed["sources"] != second["sources"]
        assert len(calls) == 4
    finally:
        module._loaded_library_versions.cache_clear()


def test_overlay_api_cancellation_preserves_verified_outputs_and_resumes(tmp_path):
    from create_defaults.bulk.overlays import generate as overlays
    config = Config(cache_dir=tmp_path / "cache", workspace_dir=tmp_path / "work",
                    output_dir=tmp_path / "output")
    class CancelOnDispatch:
        def is_set(self):
            with sqlite3.connect(config.cache_dir / "state.sqlite") as db:
                return bool(db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone())
    options = dict(config=config, groups=["genre"], sources=["logos_genre/Experimental.png"],
                   limits=WorkerLimits(workers=1))
    interrupted = overlays(cancel=CancelOnDispatch(), **options)
    assert interrupted["status"] == "incomplete"
    retained = {p: sha256(p) for p in config.output_dir.rglob("*.png")}
    resumed = overlays(**options)
    assert resumed["status"] == "verified"
    assert all(sha256(p) == value for p, value in retained.items())
    warm = overlays(**options)
    assert warm["execution"]["metrics"]["worker_starts"] == 0
    assert warm["execution"]["metrics"]["executed"] == 0



def test_parent_abrupt_exit_keeps_verified_output_and_expired_lease_resumes(tmp_path):
    import subprocess
    import sys
    from create_defaults.bulk.workers import PersistentWorkers, RenderTask, probe_renderer
    root = tmp_path / "restart"
    script = tmp_path / "parent.py"
    script.write_text(
        "import os,sys\nfrom pathlib import Path\n"
        + "sys.path.insert(0," + repr(str(ROOT.parent)) + ")\n"
        + "from create_defaults.bulk.config import Config\n"
        + "from create_defaults.bulk.common import fingerprint\n"
        + "from create_defaults.bulk.state import Store\n"
        + "from create_defaults.bulk.workers import PersistentWorkers,RenderTask,probe_renderer\n"
        + "if __name__ == '__main__':\n"
        + " root=Path(sys.argv[1]);assets=root/'assets';assets.mkdir(parents=True)\n"
        + " config=Config(asset_dir=assets,cache_dir=root/'cache',workspace_dir=root/'work',output_dir=root/'output')\n"
        + " store=Store(config.cache_dir/'state.sqlite',clock=lambda:0)\n"
        + " task=RenderTask('restart.completed',fingerprint({'value':1}),'completed.bin',{'value':1})\n"
        + " with PersistentWorkers(store,config,renderer=probe_renderer) as pool: pool.run([task])\n"
        + " store.add_job('restart.unfinished',{'unfinished':True})\n"
        + " store.transition('restart.unfinished',0,'running',owner='exited-parent',lease_seconds=1)\n"
        + " os._exit(37)\n",
        encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(root)], timeout=60, capture_output=True)
    assert result.returncode == 37, result.stderr.decode(errors="replace")
    config = Config(asset_dir=root / "assets", cache_dir=root / "cache",
                    workspace_dir=root / "work", output_dir=root / "output")
    before = sha256(config.output_dir / "completed.bin")
    store = Store(config.cache_dir / "state.sqlite", clock=lambda: 2)
    assert store.recover()["jobs"] == 1
    assert store.job("restart.unfinished")["status"] == "interrupted"
    task = RenderTask("restart.completed", fingerprint({"value": 1}), "completed.bin", {"value": 1})
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        resumed = pool.run([task])
    assert resumed["metrics"]["executed"] == 0 and resumed["metrics"]["worker_starts"] == 0
    assert sha256(config.output_dir / "completed.bin") == before
    with store.connection() as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT count(*) FROM events WHERE kind='job_lease_expired'").fetchone()[0] == 1


def test_corrupt_sqlite_fails_closed_without_adopting_outputs(tmp_path):
    path = tmp_path / "cache/state.sqlite"
    path.parent.mkdir()
    path.write_bytes(b"corrupted SQLite metadata")
    with pytest.raises(BulkError, match="valid SQLite"):
        Store(path)
    assert not (tmp_path / "output").exists()


def test_changed_database_job_spec_cannot_reuse_verified_artifact(tmp_path):
    from create_defaults.bulk.workers import PersistentWorkers, RenderTask, probe_renderer
    assets = tmp_path / "assets"
    assets.mkdir()
    config = Config(asset_dir=assets, cache_dir=tmp_path / "cache",
                    workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    store = Store(config.cache_dir / "state.sqlite")
    task = RenderTask("corrupt.spec", fingerprint({"value": 1}), "output.bin", {"value": 1})
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        pool.run([task])
    original = sha256(config.output_dir / "output.bin")
    with store.transaction() as db:
        db.execute("UPDATE jobs SET spec='{}' WHERE status='verified'")
    with PersistentWorkers(store, config, renderer=probe_renderer) as pool:
        with pytest.raises(BulkError):
            pool.run([task])
        assert pool.starts == 0
    assert sha256(config.output_dir / "output.bin") == original



@pytest.mark.parametrize("changed", [False, True])
def test_full_comparison_does_not_mask_unexplained_root_changes(tmp_path, changed, monkeypatch):
    from create_defaults.bulk import e_comparison
    from create_defaults.bulk.e_comparison import compare
    from create_defaults.bulk.e_validation import save
    # Isolate semantic classification here; malformed manifests are separately
    # rejected by the production validator and the security regression below.
    monkeypatch.setattr(e_comparison, "validate_manifest", lambda value: value)
    root, generated = tmp_path / "references", tmp_path / "generated"
    output = generated / "output/defaults-en/test.jpg"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"synthetic encoded bytes")
    current = sha256(output)
    reference = [{"path": "defaults-en/test.jpg", "python_sha256": "a" * 64 if changed else current,
                  "legacy_sha256": "b" * 64, "reference_result_sha256": "c" * 64,
                  "previous_status": "pass", "previous_classification": "historical_difference",
                  "dependencies": {}}]
    save(root / "phase1-reference-ledger.json", reference)
    save(root / "phase1-reference-summary.json", {"ledger_sha256": fingerprint(reference)})
    save(generated / "verified-output-ledger.json", [{"id": "synthetic.root", "path": "defaults-en/test.jpg", "sha256": current}])
    save(generated / "cold-result.json", {"manifest": {"jobs": [{"id": "synthetic.root", "local_relative": "defaults-en/test.jpg", "dependencies": []}]}})
    summary = compare(root, generated)
    assert summary["passed"] is (not changed)
    assert summary["new_visual_approvals"] == 0
    if changed:
        assert summary["classifications"] == {"unexplained_difference": 1}


def test_reference_correction_rejects_other_changes():
    from create_defaults.bulk.e_comparison import historical_job
    before = {"id": "franchise-06945-682bdad094e1", "parameters": {"out_name": "Death in Paradise (2911)", "base_color": "#9034AF"},
              "source": {"line": 4493}, "assets": {"logo": "same"}, "font": {"sha256": "a" * 64},
              "published_relatives": ["franchise/Death in Paradise (2911).jpg"]}
    after = deepcopy(before)
    after["id"] = "franchise-06945-8e8134ef709a"
    after["parameters"]["out_name"] = "Death in Paradise (2011)"
    after["published_relatives"] = ["franchise/Death in Paradise (2011).jpg"]
    original, exception = historical_job(after, {before["id"]: before})
    assert original == before and exception.startswith("D08:")
    after["parameters"]["base_color"] = "#000000"
    with pytest.raises(BulkError, match="Unknown change"):
        historical_job(after, {before["id"]: before})



@pytest.mark.parametrize("prefix", ["../escape", "a/b", "C:/outside", "x\\y", "a\nb", "..", " "])
def test_record_label_cannot_escape_acceptance_workspace(tmp_path, prefix):
    from create_defaults.bulk.e_validation import workload
    with pytest.raises(BulkError, match="not a path"):
        workload(tmp_path / "new", categories=["Based"], workers=1, record_prefix=prefix)
    assert not (tmp_path / "new").exists()


def test_acceptance_configuration_rejects_production_source_root():
    from create_defaults.bulk.e_validation import configuration
    with pytest.raises(BulkError, match="separate from source"):
        configuration(ROOT)


def test_acceptance_root_checks_alias_before_resolving_it(tmp_path):
    from create_defaults.bulk.e_validation import configuration
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Account cannot create directory symlinks; native junction safety is covered separately")
    with pytest.raises(BulkError, match="reparse|Symlink"):
        configuration(alias)
    assert not (target / "cache").exists()


def test_external_comparison_rejects_malformed_manifest_before_reference_writes(tmp_path):
    from create_defaults.bulk.e_comparison import compare
    from create_defaults.bulk.e_validation import save
    root, generated = tmp_path / "refs", tmp_path / "generated"
    reference = []
    save(root / "phase1-reference-ledger.json", reference)
    save(root / "phase1-reference-summary.json", {"ledger_sha256": fingerprint(reference)})
    save(generated / "verified-output-ledger.json", [])
    save(generated / "cold-result.json", {"manifest": {"jobs": [{"id": "../escape"}]}})
    with pytest.raises(BulkError):
        compare(root, generated)
    assert not (root / "fresh-parent-references").exists()


def test_isolated_evaluator_gets_only_exact_pinned_translation_bytes(tmp_path):
    from types import SimpleNamespace
    from create_defaults.bulk.e_languages import copy_pinned_resources
    from create_people_posters.github_inventory_core import blob_sha
    data = b'key_names:\n  book: Book\n'
    source, target = tmp_path / 'source', tmp_path / 'target'
    file = source / 'blobs' / (blob_sha(data) + '.yml')
    file.parent.mkdir(parents=True)
    file.write_bytes(data)
    snapshot = SimpleNamespace(data={'languages': [{'availability': 'available', 'components': ['defaults'],
        'git_blob': blob_sha(data), 'sha256': sha256(file), 'size': len(data)}]})
    assert copy_pinned_resources(snapshot, source, target) == 1
    assert (target / 'blobs' / file.name).read_bytes() == data
    assert copy_pinned_resources(snapshot, source, target) == 1
    file.write_bytes(b'changed')
    with pytest.raises(BulkError, match='changed before'):
        copy_pinned_resources(snapshot, source, target)


def test_all_recycling_workers_keep_buffered_success_responses(tmp_path, monkeypatch):
    """All children exit after sending; unread success must not become a crash."""
    from create_defaults.bulk.workers import PersistentWorkers, RenderTask, WorkerLimits, probe_renderer
    assets = tmp_path / "assets"
    assets.mkdir()
    config = Config(asset_dir=assets, cache_dir=tmp_path / "cache",
                    workspace_dir=tmp_path / "work", output_dir=tmp_path / "output")
    store = Store(config.cache_dir / "state.sqlite")
    jobs = [RenderTask("retire." + str(i), fingerprint({"i": i}), str(i) + ".bin", {"i": i}) for i in range(4)]
    limits = WorkerLimits(workers=4, total_worker_memory_bytes=4 * 512 * 1024 ** 2,
                          recycle_after=1, retries=0)
    with PersistentWorkers(store, config, limits, renderer=probe_renderer) as pool:
        start = pool._start
        def start_and_control(index):
            start(index)
            slot = pool.slots[index]
            put = slot["inbox"].put
            def send(request, *args, **kwargs):
                put(request, *args, **kwargs)
                if request is not None and len(pool.slots) == 4 and all(s["request"] for s in pool.slots.values()):
                    # Deterministic parent-side barrier, not a timing assumption:
                    # every child's success message is buffered before polling.
                    for worker in pool.slots.values():
                        worker["process"].join(timeout=15)
                        assert not worker["process"].is_alive()
            slot["inbox"].put = send
        monkeypatch.setattr(pool, "_start", start_and_control)
        result = pool.run(jobs)
    assert all(row["status"] == "rendered" for row in result["jobs"].values())
    assert result["metrics"]["executed"] == result["metrics"]["worker_starts"] == 4
    assert result["metrics"]["worker_recycles"] == 4
    assert result["metrics"]["failures"] == result["metrics"]["retry_attempts"] == 0

