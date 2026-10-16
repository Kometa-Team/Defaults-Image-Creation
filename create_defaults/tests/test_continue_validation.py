from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from create_defaults import continue_validation as continuation
from create_defaults import validation_batch as batch
from create_defaults.create_poster import ROOT, digest


class CheckpointContinuationTests(unittest.TestCase):
    def fixture(self, root):
        source = root / "old"
        snapshot = source / "source-snapshot"
        snapshot.mkdir(parents=True)
        (source / "STOP").write_text("stopped")
        for name in ("validation_manifest.py", "compare_poster_renderers.py"):
            shutil.copyfile(ROOT / name, snapshot / name)
        bulk = (ROOT / "create_default_posters.ps1").read_text(encoding="utf-8-sig")
        (snapshot / "create_default_posters.ps1").write_text(bulk.replace(
            "951C4CEA65FFEDE784A7C9672FEEC5D329A7E1E12216C42D53ECF36C90D04DEA",
            "1565B395F454D5C2642D0F411030051E7342FBAF6D5BFC5DA5899C47ECD3511E"), encoding="utf-8")
        metadata = {"run_key": "new", "published": {"commit": "same"}, "versions": {"python": "same"}}
        batch.atomic_json(source / "run.json", {**metadata, "run_key": "old"})
        job = {"id": "tiny", "sha256": "unchanged", "category": "Genre", "font": {"family": ["Test"]}}
        frozen = {"sha256": "manifest", "jobs": [job], "source_text_hashes": {"create_poster.py": "same"}}
        directory = source / "cases/tiny"
        directory.mkdir(parents=True)
        (directory / "evidence.bin").write_bytes(b"unchanged original evidence")
        result = {"id": "tiny", "category": "Genre", "font": job["font"], "job_sha256": job["sha256"],
                  "run_key": "old", "complete": True, "status": "warning", "notes": [],
                  "images": {"legacy": {}, "python": {}}, "retained_artifacts": {"evidence.bin": digest(directory / "evidence.bin")},
                  "comparisons": {"A-legacy-python": {"comparable": True, "flag_for_review": True}},
                  "measurements": {engine: {"returncode": 0, "timed_out": False} for engine in ("legacy", "python")}}
        batch.atomic_json(directory / "result.json", result)
        return source, frozen, metadata, result

    def run_import(self, source, destination, frozen, metadata):
        with patch.object(continuation, "load_manifest", return_value=frozen), \
             patch.object(continuation, "validate_manifest"), \
             patch.object(continuation.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024 ** 3)), \
             patch.object(batch, "published_state", return_value=metadata["published"]), \
             patch.object(batch, "dashboard"):
            return continuation.copy_checkpoint(source, destination, frozen, metadata, None, workers=2)

    def test_copies_verified_evidence_without_changing_metrics_or_originals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, frozen, metadata, result = self.fixture(root)
            original_sha = digest(source / "cases/tiny/result.json")
            audit = self.run_import(source, root / "new", frozen, metadata)
            revised = json.loads((root / "new/cases/tiny/result.json").read_text())
            self.assertTrue(audit["complete"])
            self.assertEqual(audit["imported_jobs"], 1)
            for key in ("comparisons", "measurements", "status", "images"):
                self.assertEqual(revised[key], result[key])
            self.assertEqual(revised["run_key"], "new")
            self.assertEqual(digest(source / "cases/tiny/result.json"), original_sha)
            self.assertEqual(revised["checkpoint_origin"]["record_sha256"], original_sha)
            self.assertTrue((source / "STOP").exists())

    def test_rejects_tampered_evidence_and_changed_completed_inputs(self):
        for changed in ("artifact", "job"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, frozen, metadata, _ = self.fixture(root)
                if changed == "artifact":
                    (source / "cases/tiny/evidence.bin").write_bytes(b"tampered")
                else:
                    path = source / "cases/tiny/result.json"
                    value = json.loads(path.read_text())
                    value["job_sha256"] = "different"
                    batch.atomic_json(path, value)
                with self.assertRaises(ValueError):
                    self.run_import(source, root / "new", frozen, metadata)
                self.assertFalse((root / "new/run.json").exists())

    def test_rejects_metric_changes_and_overlapping_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, frozen, metadata, _ = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "disjoint"):
                self.run_import(source, source / "nested", frozen, metadata)
            with (source / "source-snapshot/compare_poster_renderers.py").open("a") as stream:
                stream.write("\ndef compare_images():\n    return 'changed'\n")
            with self.assertRaisesRegex(ValueError, "metric helpers changed"):
                self.run_import(source, root / "new", frozen, metadata)


if __name__ == "__main__":
    unittest.main()
