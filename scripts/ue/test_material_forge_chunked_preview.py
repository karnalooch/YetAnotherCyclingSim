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

    def test_compile_work_is_drained_before_landscape_assignment(self):
        self.assertIn(
            "YacsTextureAuditLibrary.finish_texture_compilation",
            self.source,
        )
        self.assertIn(
            "drain_asset_compilation_and_collect_garbage",
            self.source,
        )
        self.assertIn("remaining_after", self.source)
        self.assertIn("shader_jobs_after", self.source)
        self.assertIn('"stage": "weight_texture_imported"', self.source)
        self.assertIn('"stage": f"{key}_textures_imported"', self.source)
        self.assertIn('("rock", ROCK', self.source)
        self.assertIn('("soil", SOIL', self.source)
        self.assertIn('"stage": "material_graph_built"', self.source)
        self.assertIn('"stage": "material_recompile_returned"', self.source)
        self.assertIn('"stage": "asset_shader_compilation_drained"', self.source)
        self.assertLess(
            self.source.index("drain_asset_compilation_and_collect_garbage"),
            self.source.index("def prepare()"),
        )

    def test_fixed_master_path_bypasses_live_graph_authoring(self):
        self.assertIn("YACS_MF_FIXED_MASTER_PATH", self.source)
        self.assertIn("_create_fixed_master_instance", self.source)
        self.assertIn('"fixed_master_instance"', self.source)
        self.assertIn('"material_instance_updated"', self.source)
        self.assertIn('"fixed_master_instance_drained"', self.source)

    def test_fixed_master_uses_ue58_compatible_weight_sampler(self):
        builder = (
            ROOT / "scripts/ue/build_material_forge_landscape_master.py"
        ).read_text(encoding="utf-8")
        self.assertIn("MaterialExpressionTextureSampleParameter2D", builder)
        self.assertIn('parameter_name="WeightTex"', builder)
        self.assertNotIn("TextureSample lacks TextureObject input", builder)
        self.assertNotIn('_link(weight_object, "", sample, "TextureObject")', builder)

    def test_refinement_c_uses_detail_mask_macro_contract(self):
        self.assertIn('"refined_c"', self.source)
        self.assertIn('"DetailMasks"', self.source)
        self.assertIn('"RockMacroTileSizeCm"', self.source)
        self.assertIn('"SoilMacroTileSizeCm"', self.source)
        self.assertIn('"RockMacroStrength"', self.source)
        self.assertIn("8.0 <= macro_tile_metres <= 30.0", self.source)
        self.assertIn('landscape_profile.get("macro_tile_metres", 16.0)', self.source)
        self.assertIn('landscape_profile.get("macro_strength", 0.0)', self.source)

    def test_visual_capture_has_three_way_cliff_diagnostics(self):
        capture_source = (
            ROOT / "scripts/ue/capture_material_forge_landscape.py"
        ).read_text(encoding="utf-8")
        self.assertIsInstance(ast.parse(capture_source), ast.Module)
        self.assertIn('"viewmode": "unlit"', capture_source)
        self.assertIn('"viewmode": "lightingonly"', capture_source)
        self.assertIn('"viewmode": "lit_detaillighting"', capture_source)
        self.assertIn("VMI_UNLIT", capture_source)
        self.assertIn("VMI_LIGHTING_ONLY", capture_source)
        self.assertIn("VMI_LIT_DETAIL_LIGHTING", capture_source)
        self.assertIn('"diagnostic_count"', capture_source)
        self.assertIn('"capture_count"', capture_source)
        self.assertIn("unreal.SkyAtmosphere", capture_source)
        self.assertIn("recapture_sky()", capture_source)
        self.assertIn("set_intensity(1.35)", capture_source)
        self.assertIn('"skylight_recaptured": True', capture_source)

    def test_fixed_master_orm_defaults_use_mask_compatible_placeholder(self):
        builder = (
            ROOT / "scripts/ue/build_material_forge_landscape_master.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ORM_PLACEHOLDER_NAME", builder)
        self.assertIn("TC_MASKS", builder)
        self.assertIn("finish_texture_compilation([placeholder])", builder)
        self.assertIn("texture=orm_placeholder", builder)
        self.assertNotIn('"SoilORMTex": "/Game/Prototype', builder)
        self.assertNotIn('"RockORMTex": "/Game/Prototype', builder)

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
