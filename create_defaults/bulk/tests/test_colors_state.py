from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from create_defaults.bulk.color_math import contrast, delta_e_2000, lab
from create_defaults.bulk.colors import ColorPolicy, ColorRegistry, palette, suggest_colors
from create_defaults.bulk.common import BulkError, Conflict, atomic_bytes
from create_defaults.bulk.state import MIGRATIONS, Store
from create_defaults.bulk.workspaces import Workspaces


@pytest.fixture
def registry(tmp_path):
    return ColorRegistry(Store(tmp_path / "state.sqlite"), ColorPolicy("test-explicit-v1", 5, 4.5), authorized_reviewers=["maintainer"])


def approve(registry, poster, category, color, **kwargs):
    claim = registry.reserve(poster, category, color, owner="operator", **kwargs)
    return registry.approve(claim["id"], owner="operator", reviewer="maintainer", reason="Explicit test approval")


def test_historical_import_preserves_every_color_and_duplicate(registry):
    path = Path(__file__).resolve().parents[2] / "phase2/evidence/historical-colors.json"
    audit = json.loads(path.read_text())
    count = registry.import_historical(audit)
    assert count == len(audit["assignments"]) + len(audit["generated_assignments"])
    assert registry.import_historical(audit) == count
    rows = registry.assignments()
    assert all(row["origin"] == "historical" for row in rows)
    assert all(row["policy"] == "legacy-preserved-not-exception" for row in rows)
    expected = {(item["category"], item["hex"]) for item in [*audit["assignments"], *audit["generated_assignments"]]}
    assert {(item["category"], item["hex"]) for item in rows} == expected
    first = rows[0]
    assert not registry.evaluate("new.unrelated", first["category"], first["hex"])["allowed"]


def test_normalized_category_collision_cross_category_info_and_near_warning(registry):
    approve(registry, "first", "Genre", "#aabbcc")
    assert not registry.evaluate("second", "Genre", " #AABBCC ")["allowed"]
    cross = registry.evaluate("third", "Studio", "#AABBCC")
    assert cross["allowed"] and {d["severity"] for d in cross["diagnostics"]} == {"info"}
    near = registry.evaluate("second", "Genre", "#AABBCA")
    assert near["allowed"] and any(d["code"] == "similar_color" for d in near["diagnostics"])
    assert registry.evaluate("first", "Genre", "#AABBCC")["allowed"]


def test_related_reuse_requires_every_conflicting_owner(registry):
    approve(registry, "first", "Genre", "#123456")
    registry.relationship("family", ["first", "second"], reviewer="maintainer", reason="Explicit family")
    result = registry.evaluate("second", "Genre", "#123456", relationship="family")
    assert result["allowed"] and not result["diagnostics"]
    approve(registry, "second", "Genre", "#123456", relationship="family")
    registry.relationship("other", ["first", "third"], reviewer="maintainer", reason="Only one owner related")
    assert not registry.evaluate("third", "Genre", "#123456", relationship="other")["allowed"]


def test_authorized_named_exceptions_revalidate_revisions_and_audit_identity(registry):
    approve(registry, "first", "Genre", "#123456")
    with pytest.raises(BulkError):
        registry.exception("override", category="Genre", color="#123456", affected_ids=["first", "second"], reviewer="stranger", reason="Not authorized")
    registry.exception("override", category="Genre", color="#123456", affected_ids=["first", "second"], reviewer="maintainer", reason="Branding")
    claim = registry.reserve("second", "Genre", "#123456", owner="operator", exception="override")
    assert claim["allowed"]
    assert any(d["code"] == "approved_exception" for d in claim["diagnostics"])
    registry.exception("override", category="Genre", color="#123456", affected_ids=["first", "second"], reviewer="maintainer", reason="Revoked", expected_version=0, active=False)
    with pytest.raises(Conflict):
        registry.approve(claim["id"], owner="operator", reviewer="maintainer", reason="Stale permission")


def test_concurrent_exact_reservations_and_similar_colors(registry):
    def attempt(index):
        try:
            return registry.reserve(f"poster-{index}", "Genre", "#ABCDEF", owner=str(index))["allowed"]
        except BulkError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(attempt, (1, 2))) == 1
    assert registry.reserve("nearby", "Genre", "#ABCDEE", owner="third")["allowed"]


def test_reservation_expiry_recovery_and_wrong_owner(registry):
    now = [1000]
    registry.store.clock = lambda: now[0]
    claim = registry.reserve("one", "Genre", "#123456", owner="owner", lease_seconds=10)
    with pytest.raises(Conflict):
        registry.approve(claim["id"], owner="other", reviewer="maintainer", reason="Wrong owner")
    now[0] += 11
    assert registry.store.recover()["colors"] == 1
    assert registry.reserve("two", "Genre", "#123456", owner="owner")["allowed"]


def test_palette_ignores_hidden_rgb_and_proposals_are_unapproved_deterministic(registry, tmp_path):
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    image = Image.new("RGBA", (8, 8), (255, 0, 0, 0))
    image.putpixel((1, 1), (20, 180, 80, 255))
    image.save(first)
    image = Image.new("RGBA", (8, 8), (0, 0, 255, 0))
    image.putpixel((1, 1), (20, 180, 80, 255))
    image.save(second)
    assert palette(first) == palette(second)
    one = suggest_colors(first, registry, "new", "Genre")
    two = suggest_colors(first, registry, "new", "Genre")
    assert one == two and one["status"] == "suggested" and one["approved"] is False
    assert all(not item["approved"] for item in one["candidates"])
    assert registry.assignments() == []


def test_state_migrations_transactions_events_and_stale_job_versions(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    store.add_job("job", {"spec": 1})
    assert store.job("job")["version"] == 0
    store.transition("job", 0, "running", owner="worker")
    with pytest.raises(Conflict):
        store.transition("job", 0, "running", owner="other")
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM events")
    with pytest.raises(RuntimeError):
        with store.transaction() as db:
            db.execute("UPDATE jobs SET status='failed'")
            raise RuntimeError("Interrupted transaction")
    assert store.job("job")["status"] == "running"


def test_owned_workspaces_receipts_corruption_retention_and_exclusive_writes(tmp_path):
    store = Store(tmp_path / "state.sqlite")
    manager = Workspaces(store, tmp_path / "workspaces")
    handle = manager.create()
    path = manager.owned(handle["identity"], handle["token"])
    store.add_job("job", {"spec": 1})
    atomic_bytes(path / "artifact.bin", b"verified bytes")
    receipt = manager.receipt(**handle, job_id="job", relative_artifact="artifact.bin")
    assert manager.verify_receipt(**handle, receipt=receipt) == receipt
    with pytest.raises(FileExistsError):
        atomic_bytes(path / "artifact.bin", b"overwrite")
    with pytest.raises(BulkError):
        manager.owned(handle["identity"], "wrong-token")
    (path / "artifact.bin").write_bytes(b"corrupt")
    with pytest.raises(BulkError):
        manager.verify_receipt(**handle, receipt=receipt)
    with pytest.raises(Conflict):
        manager.cleanup(**handle, retain_seconds=1000)
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep")
    manager.cleanup(**handle, retain_seconds=0)
    assert not path.exists() and unrelated.read_text() == "keep"


def test_job_lease_recovery_and_corrupt_state(tmp_path):
    now = [100]
    store = Store(tmp_path / "state.sqlite", clock=lambda: now[0])
    store.add_job("job", {"a": 1})
    store.transition("job", 0, "running", owner="worker", lease_seconds=10)
    now[0] += 11
    assert store.recover()["jobs"] == 1
    assert store.job("job")["status"] == "interrupted"
    with store.connection() as db:
        db.execute("UPDATE jobs SET spec='{}'")
    with pytest.raises(BulkError):
        store.job("job")
    (tmp_path / "broken.sqlite").write_bytes(b"not sqlite")
    with pytest.raises(BulkError):
        Store(tmp_path / "broken.sqlite")


def test_lab_and_contrast_reference_values():
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21)
    assert lab("#FFFFFF") == pytest.approx((100, 0, 0), abs=.001)


def test_cleanup_retries_interruption_but_does_not_remove_live_job_workspace(tmp_path, monkeypatch):
    import shutil
    store = Store(tmp_path / "state.sqlite")
    manager = Workspaces(store, tmp_path / "work")
    handle = manager.create()
    store.add_job("job", {"spec": 1})
    manager.bind_job(**handle, job_id="job")
    store.transition("job", 0, "running", owner="worker")
    with pytest.raises(Conflict, match="active job"):
        manager.cleanup(**handle, retain_seconds=0)
    store.transition("job", 1, "failed", owner="worker")
    original = shutil.rmtree
    monkeypatch.setattr("create_defaults.bulk.workspaces.shutil.rmtree", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("interrupted")))
    with pytest.raises(OSError):
        manager.cleanup(**handle, retain_seconds=0)
    assert manager.recover_cleanup()["pending"] == [handle["identity"]]
    monkeypatch.setattr("create_defaults.bulk.workspaces.shutil.rmtree", original)
    manager.cleanup(**handle, retain_seconds=0)
    assert not (manager.root / handle["identity"]).exists()


def test_historical_logical_mapping_does_not_change_color_or_break_idempotent_import(registry):
    audit = {"assignments": [{"audit_id": "row-1", "category": "Genre", "hex": "#123456"}], "generated_assignments": []}
    registry.import_historical(audit)
    registry.link_historical("historical:row-1", "genre.existing")
    registry.import_historical(audit)
    assert registry.assignments()[0]["poster"] == "genre.existing"
    assert registry.evaluate("genre.existing", "Genre", "#123456")["allowed"]


def test_inherited_origin_requires_parent_and_explicit_relation(registry):
    parent = approve(registry, "parent", "Genre", "#123456")
    with pytest.raises(BulkError, match="collision"):
        registry.reserve("child", "Genre", "#123456", owner="owner", origin="inherited", parent=parent)
    registry.relationship("family", ["parent", "child"], reviewer="maintainer", reason="Explicit inheritance")
    claim = registry.reserve("child", "Genre", "#123456", owner="owner", origin="inherited", parent=parent, relationship="family")
    assert claim["allowed"] and not claim["diagnostics"]


def test_ciede2000_all_author_reference_pairs():
    path = Path(__file__).parent / "data/ciede2000-reference.txt"
    rows = [list(map(float, line.split())) for line in path.read_text().splitlines()]
    assert len(rows) == 34
    for row in rows:
        assert delta_e_2000(row[:3], row[3:6]) == pytest.approx(row[6], abs=.00005)
        assert delta_e_2000(row[3:6], row[:3]) == pytest.approx(row[6], abs=.00005)
