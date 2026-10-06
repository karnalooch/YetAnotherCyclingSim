from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "scripts/ue/preview_material_forge_chunked_landscape.py"


class MaterialForgeChunkedPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TARGET.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_script_parses(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_scope_is_hard_capped(self):
        self.assertIn("MAX_COMPONENTS = 9", self.source)
        self.assertIn("sorted(components, key=center_distance)[:MAX_COMPONENTS]", self.source)

    def test_appearance_sampling_is_bilinear(self):
        self.assertIn("unreal.TextureFilter.TF_BILINEAR", self.source)
        self.assertNotIn("unreal.TextureFilter.TF_NEAREST", self.source)

    def test_world_aligned_projection_is_required(self):
        self.assertIn("WorldAlignedTexture + WorldAlignedNormal", self.source)
        self.assertIn('import_material_forge_variant.py', self.source)

    def test_preview_never_saves_or_changes_global_landscape_material(self):
        self.assertIn('"save": False', self.source)
        self.assertNotIn("save_asset(", self.source)
        self.assertNotIn("save_loaded_asset(", self.source)
        self.assertNotIn('set_editor_property("landscape_material"', self.source)

    def test_memory_gates_and_rollback_exist(self):
        for token in (
            "PREPARE_FREE_PHYSICAL_GB = 8",
            "PREPARE_FREE_COMMIT_GB = 12",
            "APPLY_FREE_PHYSICAL_GB = 6",
            "APPLY_FREE_COMMIT_GB = 8",
            'if action == "restore"',
            'if action == "status"',
        ):
            self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()
