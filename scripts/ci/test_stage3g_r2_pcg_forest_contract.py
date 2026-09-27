from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HEADER = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSimEditor"
    / "Public"
    / "PCG"
    / "Stage3GForestCandidatesSettings.h"
)
CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSimEditor"
    / "Private"
    / "PCG"
    / "Stage3GForestCandidatesSettings.cpp"
)
LAYOUT_HEADER = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Public"
    / "Cycling"
    / "Stage3GForestLayout.h"
)
LAYOUT_CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Cycling"
    / "Stage3GForestLayout.cpp"
)
TERRAIN = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Cycling"
    / "Stage3PrototypeTerrainActor.cpp"
)
TERRAIN_SPEC = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Tests"
    / "Stage3PrototypeTerrain.spec.cpp"
)
AUTHOR = ROOT / "scripts" / "ue" / "stage3g_author_pcg_forest.py"
WORLDSPEC = ROOT / "worldgen" / "specs" / "stage3g_alpine_reference.worldspec.yml"


class Stage3GR2PCGForestContractTests(unittest.TestCase):
    def test_candidate_node_consumes_shared_canonical_forest_layout(self):
        header = HEADER.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        layout_header = LAYOUT_HEADER.read_text(encoding="utf-8")
        layout_cpp = LAYOUT_CPP.read_text(encoding="utf-8")
        terrain = TERRAIN.read_text(encoding="utf-8")
        terrain_spec = TERRAIN_SPEC.read_text(encoding="utf-8")
        self.assertIn("StartDistanceM = 3700.0", header)
        self.assertIn("EndDistanceM = 6200.0", header)
        self.assertIn("Density = 0.84", header)
        self.assertIn("GenerationSeed = 42017", header)
        self.assertIn("LayerProfileVersion = 2", header)
        self.assertNotIn("RoadTiles", cpp)
        self.assertIn("MakeTargetDensityForestConfig", cpp)
        self.assertIn("TryGenerateForestLayout", cpp)
        self.assertIn("FStage3GForestCandidate", layout_header)
        self.assertIn("EStage3GForestLayer::Primary", layout_cpp)
        self.assertIn("EStage3GForestLayer::Background", layout_cpp)
        self.assertIn("EStage3GForestLayer::Understory", layout_cpp)
        self.assertIn("26.0", layout_cpp)
        self.assertIn("0.95", layout_cpp)
        self.assertIn("16.0", layout_cpp)
        self.assertIn("0.68", layout_cpp)
        self.assertIn("101", layout_cpp)
        self.assertIn("211", layout_cpp)
        self.assertIn("ExpectedCandidateMean", layout_cpp)
        self.assertIn("ExpectedCandidateMean * 0.65", layout_cpp)
        self.assertIn("ExpectedCandidateMean * 1.35", layout_cpp)
        self.assertIn("TryGenerateForestLayout", terrain)
        self.assertIn(
            "PersistedForestInstances < 1700 || PersistedForestInstances > 2300",
            terrain,
        )
        self.assertIn("outside [1700, 2300]", terrain)
        self.assertIn(
            "TargetDensityForestCount < 1700 || TargetDensityForestCount > 2300",
            terrain,
        )
        self.assertIn("outside [1700, 2300]", terrain)
        self.assertIn("TargetDensityForestCount >= 1700", terrain_spec)
        self.assertIn("TargetDensityForestCount <= 2300", terrain_spec)
        self.assertNotIn("TargetDensityForestCount >= 800", terrain_spec)
        self.assertNotIn("TargetDensityForestCount <= 1300", terrain_spec)
        self.assertNotIn("outside [800, 1300]", terrain)
        self.assertNotIn("GetActorTransform", cpp)

    def test_worldspec_drives_forest_intent(self):
        author = AUTHOR.read_text(encoding="utf-8")
        worldspec = WORLDSPEC.read_text(encoding="utf-8")
        self.assertIn('current_biome == "alpine_forest"', author)
        self.assertIn('stripped.startswith("vegetation_density:")', author)
        self.assertNotIn("re.search(", author)
        self.assertIn("route_clearance_m", author)
        self.assertIn("seed", author)
        self.assertIn("- id: alpine_forest", worldspec)
        self.assertIn("vegetation_density: 0.84", worldspec)
        self.assertIn("route_clearance_m: 4.0", worldspec)

    def test_graph_uses_stock_spawner_with_validated_mass_forest_mesh(self):
        author = AUTHOR.read_text(encoding="utf-8")
        self.assertIn('ASSET_NAME = "PCG_Forest"', author)
        self.assertIn("Stage3GForestCandidatesSettings", author)
        self.assertIn("Stage3GRouteExclusionSettings", author)
        self.assertIn("PCGStaticMeshSpawnerSettings", author)
        self.assertIn("PCGMeshSelectorWeighted", author)
        self.assertIn("PCGMeshSelectorWeightedEntry", author)
        self.assertIn("SM_Stage3G_FirSaplingMedium", author)
        self.assertIn("FOREST_MESH_OBJECT_PATH", author)
        self.assertIn("get_path_name_for_loaded_asset", author)
        self.assertIn('"validated_mass_forest_asset"', author)
        self.assertIn('"aggressive"', author)
        self.assertIn('"spawner_weight"', author)
        self.assertIn('FOREST_LAYER_PROFILE = "target_density_v2"', author)
        self.assertIn('"layer_profile_version"', author)
        self.assertIn('"layer_contract"', author)
        self.assertIn('"configured_expected_candidate_mean"', author)
        self.assertIn("math.ceil(forest_span_m / 20.0)", author)


if __name__ == "__main__":
    unittest.main()
