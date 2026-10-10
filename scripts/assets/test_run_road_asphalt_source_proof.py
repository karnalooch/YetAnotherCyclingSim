"""Synthetic producer input-gate tests; never native render evidence."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assets import run_road_asphalt_source_proof as proof
from scripts.assets import road_material_contract as contract

METADATA = """[remap]
importer="texture"
type="CompressedTexture2D"
path="res://.godot/imported/arrow.svg-123.ctex"
metadata={
"vram_texture": false
}
[deps]
source_file="res://addons/flexible_layout/arrow.svg"
dest_files=["res://.godot/imported/arrow.svg-123.ctex"]
[params]
compress/mode=0
"""
ICON = "addons/flexible_layout/arrow.svg.import"


class PrimedSourceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.path = self.source / ICON
        self.path.parent.mkdir(parents=True)
        self.path.write_text(METADATA, encoding="utf-8")

    def check(self, change="M\t" + ICON, *, staged="", head=proof.MM_SOURCE_SHA):
        def git(_root, *args):
            if args == ("rev-parse", "HEAD"):
                return head
            if args == ("diff", "--cached", "--name-only", "HEAD"):
                return staged
            if args == ("diff", "--name-status", "--no-renames", "HEAD"):
                return change
            if args == ("rev-parse", "HEAD:" + ICON):
                return "f" * 40
            self.fail("Unexpected Git command")

        with patch.object(proof, "git", side_effect=git):
            return proof.primed_source_identity(self.source)

    def test_only_recorded_primed_icon_metadata_is_admitted_and_hashed(self):
        before = self.path.read_bytes()
        result = self.check()
        self.assertTrue(result["program_inputs_unchanged"])
        self.assertEqual(
            result["primed_icon_imports"][ICON]["sha256"], proof.sha(self.path)
        )
        self.assertEqual(result, self.check())
        self.assertEqual(before, self.path.read_bytes())

    def test_unmodified_pinned_source_is_admitted(self):
        self.assertEqual(self.check("")["primed_icon_imports"], {})

    def test_changed_programs_unlisted_icons_and_nonmodification_status_reject(self):
        for change in (
            "M\tmm.gd",
            "M\tother.svg.import",
            "D\t" + ICON,
            "A\t" + ICON,
            "R100\tx\t" + ICON,
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(change)

    def test_staged_changes_and_wrong_revision_reject(self):
        with self.assertRaises(ValueError):
            self.check(staged=ICON)
        with self.assertRaises(ValueError):
            self.check(head="a" * 40)

    def test_native_constructor_expressions_and_duplicate_assignments_reject(self):
        for value in ('Object(Shader,"code": "x")', 'Resource("res://other.gd")'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                proof.import_metadata(METADATA + "unsafe=" + value)
        with self.assertRaises(ValueError):
            proof.import_metadata(METADATA + "compress/mode=1")

    def test_wrong_importer_source_and_every_cache_destination_reject(self):
        for old, new in (
            ('importer="texture"', 'importer="script"'),
            ("res://addons/flexible_layout/arrow.svg", "res://other.svg"),
            ("res://.godot/imported/arrow.svg-123.ctex", "res://../other.ctex"),
        ):
            self.path.write_text(METADATA.replace(old, new), encoding="utf-8")
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.check()
        self.path.write_text(
            METADATA.replace("[deps]", 'path.extra="res://other.ctex"\n[deps]'),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            self.check()

    def test_pinned_svg_import_type_is_supported_as_literal_metadata(self):
        self.path.write_text(
            METADATA.replace('"texture"', '"svg"')
            .replace('"CompressedTexture2D"', '"DPITexture"')
            .replace(".ctex", ".dpitex"),
            encoding="utf-8",
        )
        self.assertIn(ICON, self.check()["primed_icon_imports"])


class RoadRecipeSelectionTests(unittest.TestCase):
    def test_only_dry_varied_is_selected_with_the_existing_five_map_contract(self):
        catalog = json.loads(contract.DEFAULT_CATALOG.read_bytes())
        family, variant = proof.source_recipe(catalog)
        self.assertEqual((family["id"], variant["id"]), (contract.FAMILY, "dry_varied"))
        self.assertEqual(variant["seed"], 101)
        self.assertEqual(variant["roughness"], 0.94)
        self.assertEqual(variant["normal_strength"], 0.24)
        self.assertEqual(family["tile_metres"], 4)
        self.assertEqual(len(proof.CHANNELS), 5)

    def test_legacy_fallback_or_modified_dry_recipe_fails_before_authoring(self):
        for failure in ("missing", "duplicate", "glossy"):
            catalog = json.loads(contract.DEFAULT_CATALOG.read_bytes())
            family, variant = proof.source_recipe(catalog)
            if failure == "missing":
                family["variants"].remove(variant)
            elif failure == "duplicate":
                family["variants"].append(dict(variant))
            else:
                variant["roughness"] = 0.82
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                proof.source_recipe(catalog)


if __name__ == "__main__":
    unittest.main()
