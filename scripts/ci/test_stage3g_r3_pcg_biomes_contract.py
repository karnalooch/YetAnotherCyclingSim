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
    / "Stage3GBiomeCandidatesSettings.h"
)
CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSimEditor"
    / "Private"
    / "PCG"
    / "Stage3GBiomeCandidatesSettings.cpp"
)
AUTHOR = ROOT / "scripts" / "ue" / "stage3g_author_pcg_biomes.py"
RUNNER = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR3PCGBiomes.ps1"
WORLDSPEC = ROOT / "worldgen" / "specs" / "stage3g_alpine_reference.worldspec.yml"


class Stage3GR3PCGBiomesContractTests(unittest.TestCase):
    def test_generic_candidate_node_consumes_canonical_route_geometry(self):
        header = HEADER.read_text(encoding="utf-8")
        cpp = CPP.read_text(encoding="utf-8")
        self.assertIn("UStage3GBiomeCandidatesSettings", header)
        self.assertIn("StartDistanceM = 0.0", header)
        self.assertIn("EndDistanceM = 3700.0", header)
        self.assertIn("Density = 0.10", header)
        self.assertIn("GenerationSeed = 42017", header)
        self.assertIn("TryBuildAlpineJourneyRouteGeometry", cpp)
        self.assertIn("TrySamplePosition", cpp)
        self.assertNotIn("RoadTiles", cpp)
        self.assertNotIn("GetActorTransform", cpp)

    def test_worldspec_drives_valley_and_high_alpine_intent(self):
        author = AUTHOR.read_text(encoding="utf-8")
        worldspec = WORLDSPEC.read_text(encoding="utf-8")
        self.assertIn('"worldspec_id": "valley_meadow"', author)
        self.assertIn('"worldspec_id": "high_alpine"', author)
        self.assertIn('stripped.startswith("rocks_density:")', author)
        self.assertIn("route_clearance_m", author)
        self.assertIn("generation_seed", author)
        self.assertIn("- id: valley_meadow", worldspec)
        self.assertIn("rocks_density: 0.10", worldspec)
        self.assertIn("- id: high_alpine", worldspec)
        self.assertIn("rocks_density: 0.65", worldspec)
        self.assertIn("route_clearance_m: 4.0", worldspec)

    def test_graphs_use_route_exclusion_and_validated_boulder_mesh(self):
        author = AUTHOR.read_text(encoding="utf-8")
        self.assertIn('"asset_name": "PCG_Valley"', author)
        self.assertIn('"asset_name": "PCG_HighAlpine"', author)
        self.assertIn("Stage3GBiomeCandidatesSettings", author)
        self.assertIn("Stage3GRouteExclusionSettings", author)
        self.assertIn("PCGStaticMeshSpawnerSettings", author)
        self.assertIn("PCGMeshSelectorWeighted", author)
        self.assertIn("SM_Stage3G_Boulder", author)
        self.assertIn("BOULDER_MESH_OBJECT_PATH", author)
        self.assertIn("get_path_name_for_loaded_asset", author)
        self.assertIn('"route_truth": "FRouteGeometryProfile"', author)

    def test_runner_is_fail_closed_to_exact_two_generated_assets(self):
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn("PCG_Valley.uasset", runner)
        self.assertIn("PCG_HighAlpine.uasset", runner)
        self.assertIn("ExpectedAuthoredPaths", runner)
        self.assertIn("ChangedPaths", runner)
        self.assertIn("SM_Stage3G_Boulder", runner)
        self.assertIn("PCG_VALLEY + PCG_HIGHALPINE GRAPH AUTHORING OK.", runner)


if __name__ == "__main__":
    unittest.main()
