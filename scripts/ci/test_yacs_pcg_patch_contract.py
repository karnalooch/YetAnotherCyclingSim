from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class YacsPcgPatchContractTest(unittest.TestCase):
    def test_generic_patch_node_is_route_agnostic(self) -> None:
        header = read(
            "Source/YetAnotherCyclingSimEditor/Public/PCG/"
            "YacsPatchCandidatesSettings.h"
        )
        cpp = read(
            "Source/YetAnotherCyclingSimEditor/Private/PCG/"
            "YacsPatchCandidatesSettings.cpp"
        )

        self.assertIn("UYacsPatchCandidatesSettings", header)
        self.assertIn("FYacsPatchRectExclusion", header)
        for field in (
            "PatchCenterCm",
            "SizeXM",
            "SizeYM",
            "PatchYawDeg",
            "PointCount",
            "ClusterCount",
            "MinSpacingM",
            "EdgeMarginM",
            "MinUniformScale",
            "MaxUniformScale",
            "Irregularity",
            "GenerationSeed",
            "Exclusions",
        ):
            self.assertIn(field, header)

        self.assertIn('TEXT("YACSPatchCandidates")', cpp)
        self.assertIn("FRandomStream Random(Settings->GenerationSeed)", cpp)
        self.assertIn("UPCGBasePointData", cpp)
        self.assertIn("EPCGPointNativeProperties::Transform", cpp)
        self.assertIn("EPCGPointNativeProperties::Seed", cpp)
        self.assertIn("MinSpacingSq", cpp)
        self.assertIn("IsInsideExclusion", cpp)
        self.assertNotIn("FRouteGeometryProfile", cpp)
        self.assertNotIn("TryBuildAlpineJourneyRouteGeometry", cpp)
        self.assertNotIn("FSimulationState", cpp)

    def test_scene_composer_uses_real_pcg_backend(self) -> None:
        composer = read("scripts/ue/yacs_scene_composer.py")
        self.assertIn("def begin_pcg_forest_patch(", composer)
        self.assertIn("unreal.YacsPatchCandidatesSettings", composer)
        self.assertIn("unreal.PCGStaticMeshSpawnerSettings", composer)
        self.assertIn("unreal.PCGVolume", composer)
        self.assertIn("set_graph_local", composer)
        self.assertIn("generate_local", composer)
        self.assertIn('"backend": "pcg_patch_adapter_v1"', composer)
        self.assertIn('"execution_backend": "pcg_patch_adapter_v1"', composer)
        self.assertIn("def count_pcg_instances(", composer)

        capture = read("scripts/ue/stage3g_capture_passo_giau_roadside_house.py")
        self.assertIn("begin_pcg_forest_patch(", capture)
        self.assertIn("_pcg_component.is_generating()", capture)
        self.assertIn('get_editor_property("generated")', capture)
        self.assertIn("count_pcg_instances", capture)
        self.assertIn('_capture_phase = "scheduling_screenshot"', capture)
        self.assertIn('if _capture_phase == "scheduling_screenshot":', capture)
        self.assertIn('_capture_phase = "waiting_screenshot"', capture)
        self.assertNotIn(
            "yacs_scene_composer.spawn_transient_forest_patch(",
            capture,
        )

    def test_proof_fails_closed_without_generated_pcg_instances(self) -> None:
        wrapper = read("scripts/ue/Invoke-YacsPassoGiauRoadsideHouseProof.ps1")
        self.assertIn("pcg_patch_adapter_v1", wrapper)
        self.assertIn("instanced_mesh_instances", wrapper)
        self.assertIn("generic_candidate_node", wrapper)

        workflow = read(
            ".github/workflows/passo-giau-r4-1-roadside-house.yml"
        )
        self.assertIn(
            "Source/YetAnotherCyclingSimEditor/Public/PCG/"
            "YacsPatchCandidatesSettings.h",
            workflow,
        )
        self.assertIn(
            "Source/YetAnotherCyclingSimEditor/Private/PCG/"
            "YacsPatchCandidatesSettings.cpp",
            workflow,
        )
        self.assertIn("test_yacs_pcg_patch_contract.py", workflow)


if __name__ == "__main__":
    unittest.main()
