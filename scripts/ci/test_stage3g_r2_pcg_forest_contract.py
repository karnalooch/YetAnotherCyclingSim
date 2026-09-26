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
        self.assertIn("vegetation_density", author)
        self.assertIn("route_clearance_m", author)
        self.assertIn("seed", author)
        self.assertIn("- id: alpine_forest", worldspec)
        self.assertIn("vegetation_density: 0.72", worldspec)
        self.assertIn("route_clearance_m: 4.0", worldspec)

    def test_graph_is_fail_closed_until_optimized_fir_exists(self):
        author = AUTHOR.read_text(encoding="utf-8")
        self.assertIn('ASSET_NAME = "PCG_Forest"', author)
        self.assertIn("Stage3GForestCandidatesSettings", author)
        self.assertIn("Stage3GRouteExclusionSettings", author)
        self.assertIn('"pending_optimized_fir"', author)
        self.assertNotIn("PCGStaticMeshSpawnerSettings", author)


if __name__ == "__main__":
    unittest.main()
