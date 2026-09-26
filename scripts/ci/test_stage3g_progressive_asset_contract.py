from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUTHORING = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GAuthoring.ps1"
IMPORTER = ROOT / "scripts" / "ue" / "stage3g_import_source_assets.py"
MATERIALS = ROOT / "scripts" / "ue" / "stage3g_author_materials.py"
PROJECT = ROOT / "YetAnotherCyclingSim.uproject"


class Stage3GProgressiveAssetContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authoring = AUTHORING.read_text(encoding="utf-8")
        cls.importer = IMPORTER.read_text(encoding="utf-8")
        cls.materials = MATERIALS.read_text(encoding="utf-8")
        cls.project = PROJECT.read_text(encoding="utf-8")

    def test_required_editor_plugins_are_explicit(self):
        for plugin in ("PCG", "EditorScriptingUtilities", "GeometryScripting"):
            self.assertIn(f'\"Name\": \"{plugin}\"', self.project)
        self.assertNotIn('\"Name\": \"PCGGeometryScriptInterop\"', self.project)

    def test_authoring_downloads_only_r1_curated_assets(self):
        for asset_id in (
            "sparse_grass",
            "forrest_ground_03",
            "rocky_terrain",
            "boulder_01",
        ):
            self.assertIn(asset_id, self.authoring)
        self.assertNotIn("fir_tree_01", self.authoring)
        self.assertNotIn("mountainside", self.authoring)

    def test_import_proof_is_fail_closed(self):
        self.assertIn("stage3g_asset_import_proof.json", self.authoring)
        self.assertIn("imported_count -ne 13", self.authoring)
        self.assertIn("Stage 3G source-asset import proof is incomplete.", self.authoring)
        self.assertIn("SM_Stage3G_Boulder.uasset", self.authoring)

    def test_importer_uses_project_owned_canonical_paths(self):
        self.assertIn(
            "/Game/Prototype/Environment/Stage3G/Imported", self.importer
        )
        for name in (
            "T_Stage3G_Meadow_BaseColor",
            "T_Stage3G_ForestGround_BaseColor",
            "T_Stage3G_HighAlpine_BaseColor",
            "T_Stage3G_Boulder_BaseColor",
            "SM_Stage3G_Boulder",
        ):
            self.assertIn(name, self.importer)
        self.assertIn("download-index.json", self.importer)
        self.assertIn("source_md5", self.importer)

    def test_materials_consume_imported_textures(self):
        for name in (
            "T_Stage3G_Meadow_BaseColor",
            "T_Stage3G_ForestGround_BaseColor",
            "T_Stage3G_HighAlpine_BaseColor",
            "T_Stage3G_Boulder_BaseColor",
        ):
            self.assertIn(name, self.materials)
        self.assertIn("MaterialExpressionTextureSample", self.materials)
        self.assertIn("MaterialExpressionTextureCoordinate", self.materials)

    def test_real_rock_layer_is_part_of_deterministic_authoring_contract(self):
        self.assertIn("rock_props=40", self.authoring)


if __name__ == "__main__":
    unittest.main()
