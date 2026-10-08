"""Repository inspection evidence must stay bound to its original captured ZIP."""

from __future__ import annotations

import json
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path

from scripts.ci import test_retain_sa_calobra_tpp_survey as retention_fixture
from scripts.proof.export_sa_calobra_tpp_survey_docs import (
    ARCHIVE_DIRECTORY,
    DOCS_PATH,
    LFS_RULE,
    ExportIdentity,
    export_docs,
)
from scripts.proof.package_sa_calobra_tpp_survey import digest
from scripts.proof.retain_sa_calobra_tpp_survey import inventory


class SurveyDocsExportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = retention_fixture.SurveyRetentionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source = self.fixture.source
        base = self.source.parent
        self.repo = base / "repository-export"
        self.repo.mkdir()
        (self.repo / ".gitattributes").write_text(LFS_RULE + "\n", encoding="utf-8")
        self.zip = base / "original-artifact.zip"
        self.make_zip()
        self.identity = ExportIdentity(
            retention_fixture.SHA,
            42,
            1,
            digest(self.zip),
            self.zip.stat().st_size,
            self.fixture.fixture.report["frame_count"],
            2,
            self.fixture.fixture.report["frame_count"] // 2,
        )
        self.docs = self.repo / DOCS_PATH
        self.archive = self.repo / ARCHIVE_DIRECTORY / "retained-42.zip"

    def make_zip(self, extra=None, skip=None):
        with zipfile.ZipFile(
            self.zip, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for item in inventory(self.source, exclude_metadata=True)["files"]:
                if item["path"] != skip:
                    archive.write(self.source / item["path"], item["path"])
            if extra:
                archive.writestr(extra, b"unexpected bytes")

    def export(self):
        return export_docs(self.source, self.zip, self.repo, self.identity)

    def test_repo_contains_actual_paired_images_and_exact_original_zip(self):
        source_before = inventory(self.source)
        zip_before = digest(self.zip)
        receipt = self.export()
        self.assertEqual(receipt["status"], "DOCS_EXPORTED")
        self.assertTrue(receipt["source_preserved"])
        self.assertTrue(receipt["outputs_verified"])
        self.assertEqual(receipt["visual_acceptance"], "PENDING_REVIEW")
        self.assertEqual(receipt["performance_acceptance"], "NOT_MEASURED")
        self.assertEqual(digest(self.archive), zip_before)
        self.assertEqual(inventory(self.source), source_before)
        self.assertEqual(digest(self.zip), zip_before)
        manifest = json.loads((self.docs / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["archive"]["sha256"], zip_before)
        self.assertFalse(manifest["geometry_modified"])
        self.assertFalse(manifest["visual_classifications_assigned"])
        for item in manifest["copied_viewing_aids"]:
            self.assertEqual(digest(self.docs / item["path"]), item["sha256"])
            self.assertEqual(
                digest(self.fixture.survey / "review" / item["path"]), item["sha256"]
            )
        page = (self.docs / "windows/window-0000.md").read_text(encoding="utf-8")
        self.assertIn("Forward | Reverse", page)
        self.assertIn("window-0000-forward-00000.jpg", page)
        self.assertIn("window-0000-reverse-00002.jpg", page)
        readme = (self.docs / "README.md").read_text(encoding="utf-8")
        self.assertIn("no fabricated BEFORE/AFTER", readme)
        self.assertIn("PENDING_REVIEW", readme)
        self.assertIn("terrain-erosion-mesh/tpp-survey/review/index.html", readme)
        self.assertFalse(list(self.docs.parent.glob(".tpp-docs-staging-*")))
        self.assertFalse(list(self.archive.parent.glob(".tpp-archive-staging-*")))

    def test_exact_idempotent_export_and_different_owner_notes_are_preserved(self):
        self.export()
        before = inventory(self.docs)
        self.assertTrue(self.export()["idempotent_reuse"])
        self.assertEqual(inventory(self.docs), before)
        readme = self.docs / "README.md"
        readme.write_text("owner annotations\n", encoding="utf-8")
        with self.assertRaisesRegex(FileExistsError, "never overwrite"):
            self.export()
        self.assertEqual(readme.read_text(encoding="utf-8"), "owner annotations\n")

    def test_persistent_retention_metadata_is_not_claimed_as_original_zip_content(self):
        receipt = self.fixture.retain()
        self.source = Path(receipt["destination"])
        self.assertEqual(self.export()["status"], "DOCS_EXPORTED")
        manifest = json.loads((self.docs / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(
            all(
                not row["path"].startswith(".yacs-retention/")
                for row in manifest["donor_files"]
            )
        )

    def test_wrong_artifact_hash_or_count_cannot_create_docs(self):
        self.identity = replace(self.identity, archive_sha256="b" * 64)
        with self.assertRaisesRegex(ValueError, "ZIP hash/size"):
            self.export()
        self.assertFalse(self.docs.exists())
        self.identity = replace(
            self.identity, archive_sha256=digest(self.zip), frame_count=999
        )
        with self.assertRaisesRegex(ValueError, "survey counts"):
            self.export()
        self.assertFalse(self.docs.exists())

    def test_even_a_correctly_hashed_zip_must_match_the_donor_files(self):
        self.make_zip(extra="extra.png")
        self.identity = replace(
            self.identity,
            archive_sha256=digest(self.zip),
            archive_size_bytes=self.zip.stat().st_size,
        )
        with self.assertRaisesRegex(ValueError, "file inventory"):
            self.export()
        self.assertFalse(self.docs.exists())
        self.make_zip(skip="native-control.log")
        self.identity = replace(
            self.identity,
            archive_sha256=digest(self.zip),
            archive_size_bytes=self.zip.stat().st_size,
        )
        with self.assertRaisesRegex(ValueError, "missing donor"):
            self.export()
        self.assertFalse(self.docs.exists())

    def test_existing_different_archive_cannot_be_replaced(self):
        self.archive.parent.mkdir(parents=True)
        self.archive.write_bytes(b"owner archive")
        with self.assertRaisesRegex(FileExistsError, "never overwrite"):
            self.export()
        self.assertEqual(self.archive.read_bytes(), b"owner archive")
        self.assertFalse(self.docs.exists())

    def test_missing_lfs_rule_prevents_large_zip_publication(self):
        (self.repo / ".gitattributes").write_text("*.md text\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "LFS rule"):
            self.export()
        self.assertFalse(self.archive.exists())
        self.assertFalse(self.docs.exists())


if __name__ == "__main__":
    unittest.main()
