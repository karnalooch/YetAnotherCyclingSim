"""Tests for BOB's study-only construction knowledge library."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.worldgen.bob_construction_knowledge import (
    DEFAULT_LIBRARY_PATH,
    LIBRARY_ID,
    ROLE,
    construction_study_manifest,
    load_construction_knowledge,
)


class BobConstructionKnowledgeTests(unittest.TestCase):
    def test_real_library_is_valid_and_separate_from_verified_memory(self):
        data, digest = load_construction_knowledge()
        self.assertEqual(data["library_id"], LIBRARY_ID)
        self.assertEqual(data["role"], ROLE)
        self.assertEqual(len(digest), 64)
        self.assertEqual(
            data["memory_boundary"]["verified_case_memory"],
            "worldgen/terrain/verified_terrain_cases.json",
        )
        self.assertTrue(all(entry["authority"] == "REFERENCE_ONLY" for entry in data["entries"]))

    def test_lesson_manifest_records_books_without_promoting_them_to_experience(self):
        manifest = construction_study_manifest(
            (
                "unreal_spline_application",
                "unreal_spline_edit_layers",
                "mountain_road_earthworks",
            )
        )
        self.assertEqual(manifest["role"], ROLE)
        self.assertGreaterEqual(len(manifest["knowledge_entry_ids"]), 3)
        self.assertTrue(all(url.startswith("https://") for url in manifest["source_urls"]))
        self.assertFalse(manifest["verified_case_memory_modified"])
        self.assertFalse(manifest["knowledge_can_grant_admission"])
        self.assertFalse(manifest["knowledge_can_grant_learning_admission"])

    def test_reference_cannot_disguise_itself_as_verified_authority(self):
        data = json.loads(DEFAULT_LIBRARY_PATH.read_text(encoding="utf-8"))
        data["entries"][0]["authority"] = "VERIFIED_CASE"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "knowledge.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "verified authority"):
                load_construction_knowledge(path)

    def test_missing_required_domain_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing domains"):
            construction_study_manifest(("definitely_not_a_real_domain",))


if __name__ == "__main__":
    unittest.main()
