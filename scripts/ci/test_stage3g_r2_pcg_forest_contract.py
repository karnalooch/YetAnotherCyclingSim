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
AUTHOR = ROOT / "scripts" / "ue" / "stage3g_author_pcg_forest.py"
WORLDSPEC = ROOT / "worldgen" / "specs" / "stage3g_alpine_reference.worldspec.yml"


class Stage3GR2PCGForestContractTests(unittest.TestCase):
    def test_candidate_node_consumes_canonical_route_geometry(self):
        header = HEADER.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        self.assertIn("StartDistanceM = 3700.0", header)
        self.assertIn("EndDistanceM = 6200.0", header)
        self.assertIn("Density = 0.72", header)
        self.assertIn("GenerationSeed = 42017", header)
        self.assertIn("TryBuildAlpineJourneyRouteGeometry", cpp)
        self.assertIn("TrySamplePosition", cpp)
        self.assertNotIn("RoadTiles", cpp)
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
        self.assertIn("vegetation_density: 0.72", worldspec)
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
        self.assertIn('"validated_mass_forest_asset"', author)
        self.assertIn('"aggressive"', author)
        self.assertIn('"spawner_weight"', author)


if __name__ == "__main__":
    unittest.main()
