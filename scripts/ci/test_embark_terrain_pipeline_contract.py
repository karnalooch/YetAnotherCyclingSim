from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class EmbarkTerrainPipelineContractTests(unittest.TestCase):
    def test_owner_embark_directive_is_full_pattern_not_shortcut(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("### Explicit Embark-mode directive", agents)
        self.assertIn("production-proven Embark pattern end-to-end", agents)
        self.assertIn("Do not silently down-scope", agents)
        self.assertIn("do **not** invent its node graph", agents)

    def test_world_bible_selects_full_dcc_escalation_after_native_failure(self) -> None:
        bible = (ROOT / "docs/WORLD_BUILDING_BIBLE.md").read_text(encoding="utf-8")
        self.assertIn(
            "Passo Giau Embark escalation — selected after native visual failure", bible
        )
        for token in (
            "HOUDINI PDG",
            "GAEA BRIDGE",
            "HOUDINI HEIGHTFIELD",
            "HOUDINI ENGINE",
            "Base_DTM",
            "Road_Earthworks",
            "World Partition",
            "RVT",
            "custom NumPy blur",
        ):
            self.assertIn(token, bible)

    def test_pipeline_config_preserves_authority_and_full_stage_chain(self) -> None:
        config = json.loads(
            (ROOT / "worldgen/embark/passo_giau_terrain_pipeline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["pipeline_id"], "passo-giau-embark-landscape-v1")
        self.assertEqual(config["spatial_contract"]["crs"], "EPSG:32632")
        self.assertEqual(config["spatial_contract"]["unreal_landscape_vertices"], 4033)
        self.assertLessEqual(
            config["spatial_contract"]["max_conditioned_source_cell_m"], 2.0
        )
        self.assertEqual(config["gaea"]["seed"], 0)
        self.assertTrue(config["invariants"]["preserve_route_xy"])
        self.assertTrue(config["invariants"]["preserve_physics_authority"])
        self.assertTrue(config["invariants"]["preserve_source_provenance"])
        self.assertTrue(config["invariants"]["require_32bit_intermediate_heightfields"])
        self.assertTrue(config["invariants"]["forbid_guessed_embark_internal_nodes"])
        self.assertTrue(config["recipes"]["houdini_hip"].endswith(".hiplc"))
        self.assertTrue(config["recipes"]["gaea_terrain"].endswith(".terrain"))
        self.assertTrue(config["recipes"]["houdini_heightfield_hda"].endswith(".hdalc"))
        self.assertEqual(
            config["recipes"]["houdini_gaea_processor_node"],
            "/obj/yacs_passo_giau_gaea/GAEA_PROCESSOR",
        )
        self.assertEqual(
            config["recipes"]["houdini_gaea_bridge_node"],
            "/obj/yacs_passo_giau_gaea/OUT_GAEA",
        )
        self.assertEqual(
            config["recipes"]["houdini_preprocess_top"],
            "/tasks/yacs_passo_giau_preprocess",
        )
        self.assertEqual(
            config["recipes"]["houdini_finalize_top"],
            "/tasks/yacs_passo_giau_finalize",
        )

    def test_orchestrator_uses_documented_dcc_boundaries(self) -> None:
        source = (ROOT / "scripts/worldgen/embark_terrain_pipeline.py").read_text(
            encoding="utf-8"
        )
        for token in (
            "cook_top_network.py",
            "houdini_pdg_preprocess",
            "gaea2houdini_shape",
            "houdini_heightfield_finalize",
            "finalize_unreal_heightfield",
            "unreal_author_and_rider_proof",
            "validate_embark_recipe.py",
            "cook_houdini_node.py",
            "houdini_gaea_bridge_node",
            "houdini_heightfield_hda",
            '"-PreparedTerrainRoot"',
            '"-SkipTerrainPreparation"',
        ):
            self.assertIn(token, source)
        for forbidden in (
            "gaussian_filter",
            "uniform_filter",
            "median_filter",
            "cv2.GaussianBlur",
            "np.convolve",
        ):
            self.assertNotIn(forbidden, source)

    def test_finalizer_is_validation_and_encoding_not_secret_smoothing(self) -> None:
        source = (
            ROOT / "scripts/assets/finalize_passo_giau_embark_heightfield.py"
        ).read_text(encoding="utf-8")
        for token in (
            'TARGET_CRS = "EPSG:32632"',
            "LANDSCAPE_SIZE = 4033",
            "MAX_SOURCE_CELL_M = 2.0",
            '"passo-giau-embark-landscape-v1"',
            "conditioned_source",
            "pipeline_run_manifest_sha256",
        ):
            self.assertIn(token, source)
        for forbidden in (
            "gaussian_filter",
            "uniform_filter",
            "median_filter",
            "cv2.GaussianBlur",
            "np.convolve",
        ):
            self.assertNotIn(forbidden, source)

    def test_unreal_wrapper_accepts_only_proven_external_conditioned_terrain(
        self,
    ) -> None:
        wrapper = (
            ROOT / "scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1"
        ).read_text(encoding="utf-8")
        for token in (
            "[string] $PreparedTerrainRoot",
            "[switch] $SkipTerrainPreparation",
            "passo-giau-embark-landscape-v1",
            "conditioned_source.pipeline_run_manifest_sha256",
            "conditioned_source.sha256",
            "Base_DTM",
            "Road_Earthworks",
        ):
            self.assertIn(token, wrapper)

    def test_dcc_binary_recipes_are_lfs_and_not_faked_as_text(self) -> None:
        attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.hiplc filter=lfs", attrs)
        self.assertIn("*.terrain filter=lfs", attrs)

        recipes = ROOT / "worldgen/embark/recipes"
        self.assertTrue((recipes / "README.md").is_file())
        # Until a real licensed DCC authoring pass produces them, these files
        # must be absent rather than generated as fake textual stand-ins.
        for filename in (
            "passo_giau_landscape.hiplc",
            "yacs_passo_giau_heightfield.hdalc",
            "passo_giau_landscape.terrain",
        ):
            path = recipes / filename
            if path.exists():
                header = path.read_bytes()[:128]
                self.assertNotIn(b"placeholder", header.lower())
                self.assertNotIn(b"fake", header.lower())


if __name__ == "__main__":
    unittest.main()
