from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ROUTE_HEADER = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Public"
    / "Cycling"
    / "Stage3GRouteExclusion.h"
)
ROUTE_CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Cycling"
    / "Stage3GRouteExclusion.cpp"
)
TERRAIN_CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Cycling"
    / "Stage3PrototypeTerrainActor.cpp"
)
PCG_CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSimEditor"
    / "Private"
    / "PCG"
    / "Stage3GBiomeCandidatesSettings.cpp"
)
FOREST_PCG_CPP = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSimEditor"
    / "Private"
    / "PCG"
    / "Stage3GForestCandidatesSettings.cpp"
)
TERRAIN_SPEC = (
    ROOT
    / "Source"
    / "YetAnotherCyclingSim"
    / "Private"
    / "Tests"
    / "Stage3PrototypeTerrain.spec.cpp"
)
HARNESS = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR4TerrainCoherence.ps1"
RETIRED_WORKFLOW = (
    ROOT / ".github" / "workflows" / "stage3g-r4-terrain-coherence-author.yml"
)


class Stage3GR4TerrainCoherenceContract(unittest.TestCase):
    def test_surface_contract_is_shared_and_presentation_only(self):
        header = ROUTE_HEADER.read_text(encoding="utf-8")
        cpp = ROUTE_CPP.read_text(encoding="utf-8")

        self.assertIn("FRoutePresentationSurfaceResult", header)
        self.assertIn("TryEvaluateRoutePresentationSurface", header)
        self.assertIn("presentation-only", header)
        self.assertIn("PresentationCorridorHalfWidthM = 8.0", cpp)
        self.assertIn("return {110.0, 10.0};", cpp)
        self.assertIn("return {60.0, 8.0};", cpp)
        self.assertIn("return {220.0, 28.0};", cpp)
        self.assertIn("Alpha * Alpha * (3.0 - 2.0 * Alpha)", cpp)

    def test_runtime_terrain_uses_seven_route_aware_bands(self):
        text = TERRAIN_CPP.read_text(encoding="utf-8")
        spec = TERRAIN_SPEC.read_text(encoding="utf-8")

        self.assertIn("TerrainShoulderBandsPerSide = 3", text)
        self.assertIn(
            "TerrainBandsPerSlice = 1 + TerrainShoulderBandsPerSide * 2", text
        )
        self.assertIn("TryMakeTerrainShoulderTransform", text)
        self.assertIn("TryEvaluateRoutePresentationSurface", text)
        self.assertIn("SurfaceRiseM", text)
        self.assertIn("GetTerrainInstanceCount(), 1400", spec)

    def test_pcg_candidates_use_same_surface_rise(self):
        text = PCG_CPP.read_text(encoding="utf-8")
        self.assertIn('#include "Cycling/Stage3GRouteExclusion.h"', text)
        self.assertIn("TryEvaluateRoutePresentationSurface", text)
        self.assertIn("CandidateM.Z += Surface.SurfaceRiseM", text)
        self.assertNotIn("GetActorTransform", text)

    def test_target_density_forest_candidates_use_same_surface_rise(self):
        text = FOREST_PCG_CPP.read_text(encoding="utf-8")
        self.assertIn('#include "Cycling/Stage3GRouteExclusion.h"', text)
        self.assertIn("TryEvaluateRoutePresentationSurface", text)
        self.assertIn("Candidate.SignedLateralOffsetM", text)
        self.assertIn("PositionM.Z += Surface.SurfaceRiseM", text)

    def test_authoring_harness_remains_fail_closed_after_workflow_retirement(self):
        harness = HARNESS.read_text(encoding="utf-8")

        self.assertIn("ExpectedHead", harness)
        self.assertIn("git -C $RepoRoot lfs fsck", harness)
        self.assertIn("CyclingStage3World", harness)
        self.assertIn("-run=CyclingStage3RouteSetup", harness)
        self.assertIn("Content/Prototype/Maps/L_CyclingTest.umap", harness)
        self.assertIn("Unexpected tracked mutations", harness)
        self.assertFalse(RETIRED_WORKFLOW.exists())


if __name__ == "__main__":
    unittest.main()
