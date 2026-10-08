"""Persistent retention must preserve captured bytes and fail before admission."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ci import test_package_sa_calobra_tpp_survey as package_fixture
from scripts.proof.package_sa_calobra_tpp_survey import digest, package
from scripts.proof.retain_sa_calobra_tpp_survey import (
    inventory,
    publish_no_replace,
    retain,
)

SHA = package_fixture.SHA


class SurveyRetentionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = package_fixture.SurveyPackageTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        base = Path(self.fixture.temp.name)
        self.source = base / "downloaded-artifact"
        self.survey = self.source / "terrain-erosion-mesh/tpp-survey"
        self.survey.parent.mkdir(parents=True)
        self.fixture.root.rename(self.survey)
        package(self.survey, SHA)
        (self.source / "checkout-restoration.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "PASS",
                    "exact_sha": SHA,
                    "tracked_changes": [],
                }
            ),
            encoding="utf-8",
        )
        (self.source / "native-control.log").write_bytes(b"control diagnostic bytes\n")
        (self.source / "empty-diagnostic-directory").mkdir()
        self.home = base / "persistent-workspace"
        self.home.mkdir()
        self.config = self.home / "workspace.json"
        self.config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "project": "project",
                    "data": "data",
                    "cache": "cache",
                    "checkpoints": "checkpoints",
                    "work": "work",
                }
            ),
            encoding="utf-8",
        )
        self.destination = self.home / "work/proofs/sa-calobra-tpp" / SHA / "42-1"

    def retain(self):
        return retain(self.source, SHA, 42, 1, self.config)

    def test_whole_artifact_is_verified_retained_and_source_is_unchanged(self):
        before = inventory(self.source)
        receipt = self.retain()
        self.assertEqual(receipt["status"], "LOCAL_RETAINED")
        self.assertEqual(receipt["remote_backup"], "UNVERIFIED")
        self.assertEqual(receipt["visual_acceptance"], "PENDING_REVIEW")
        self.assertEqual(receipt["performance_acceptance"], "NOT_MEASURED")
        self.assertTrue(receipt["source_preserved"])
        self.assertTrue(receipt["destination_verified"])
        self.assertEqual(Path(receipt["destination"]), self.destination)
        self.assertEqual(inventory(self.source), before)
        self.assertEqual(inventory(self.destination, exclude_metadata=True), before)
        self.assertEqual(receipt["files_verified"], before["file_count"])
        self.assertEqual(receipt["bytes_verified"], before["size_bytes"])
        manifest_path = Path(receipt["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["inventory"], before)
        self.assertEqual(manifest["status"], "LOCAL_RETAINED")
        self.assertEqual(receipt["manifest_sha256"], digest(manifest_path))
        self.assertTrue((self.destination / "empty-diagnostic-directory").is_dir())
        self.assertEqual(
            (self.destination / "native-control.log").read_bytes(),
            b"control diagnostic bytes\n",
        )

    def test_collision_preserves_existing_archive_and_source(self):
        self.retain()
        archive_before = inventory(self.destination, exclude_metadata=True)
        source_before = inventory(self.source)
        marker = self.destination / "owner-note.txt"
        marker.write_text("keep this archive", encoding="utf-8")
        with self.assertRaisesRegex(FileExistsError, "never overwrite"):
            self.retain()
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep this archive")
        self.assertEqual(inventory(self.source), source_before)
        self.assertTrue(
            all(
                (self.destination / row["path"]).stat().st_size == row["size_bytes"]
                and digest(self.destination / row["path"]) == row["sha256"]
                for row in archive_before["files"]
            )
        )

    def test_failed_checkout_restoration_is_not_published(self):
        path = self.source / "checkout-restoration.json"
        path.write_text(
            json.dumps(
                {
                    "status": "FAIL",
                    "exact_sha": SHA,
                    "tracked_changes": ["modified map"],
                }
            ),
            encoding="utf-8",
        )
        before = inventory(self.source)
        with self.assertRaisesRegex(ValueError, "Checkout restoration"):
            self.retain()
        self.assertFalse(self.destination.exists())
        self.assertEqual(inventory(self.source), before)

    def test_corrupt_primary_frame_and_modified_review_aid_are_rejected(self):
        frame = self.survey / self.fixture.report["frames"][0]["file"]
        original = frame.read_bytes()
        frame.write_bytes(b"tampered image")
        with self.assertRaisesRegex(ValueError, "PNG"):
            self.retain()
        self.assertFalse(self.destination.exists())
        frame.write_bytes(original)
        guide = self.survey / "review/review-guide.txt"
        guide.write_text("changed after package verification", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "derived-file hash/size"):
            self.retain()
        self.assertFalse(self.destination.exists())

    def test_source_change_during_copy_cannot_be_admitted(self):
        from scripts.proof import retain_sa_calobra_tpp_survey as module

        original_copy = module.copy_file
        changed = False

        def copy_then_mutate(source, target):
            nonlocal changed
            original_copy(source, target)
            if not changed:
                changed = True
                (self.source / "native-control.log").write_bytes(b"changed during copy")

        with (
            patch.object(module, "copy_file", side_effect=copy_then_mutate),
            self.assertRaisesRegex(ValueError, "changed|mismatch"),
        ):
            self.retain()
        self.assertFalse(self.destination.exists())
        failures = list(
            self.destination.parent.glob(
                ".42-1.staging-*/.yacs-retention/manifest.json"
            )
        )
        self.assertEqual(len(failures), 1)
        failed = json.loads(failures[0].read_text(encoding="utf-8"))
        self.assertEqual(failed["status"], "RETENTION_FAILED")
        self.assertFalse(failed["destination_verified"])

    def test_workspace_escape_and_invalid_ids_fail_before_copy(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["work"] = "../other-workspace"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "below its root"):
            self.retain()
        with self.assertRaisesRegex(ValueError, "positive integers"):
            retain(self.source, SHA, -1, 1, self.config)
        self.assertFalse(self.destination.exists())

    def test_atomic_publication_cannot_replace_even_an_empty_destination(self):
        staging = self.home / "staging"
        staging.mkdir()
        (staging / "evidence.bin").write_bytes(b"verified bytes")
        target = self.home / "already-created"
        target.mkdir()
        with self.assertRaises(OSError):
            publish_no_replace(staging, target)
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual((staging / "evidence.bin").read_bytes(), b"verified bytes")


if __name__ == "__main__":
    unittest.main()
