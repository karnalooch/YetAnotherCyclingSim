from __future__ import annotations

import unittest

import classify_changes as cc


class ChangeClassifierTests(unittest.TestCase):
    def test_docs_only_is_lightweight(self):
        result = cc.classify_paths(["README.md", "docs/ci/PROJECT_WORKFLOW.md"])
        self.assertTrue(result.docs_only)
        self.assertTrue(result.docs)
        self.assertFalse(result.python)
        self.assertFalse(result.cpp)
        self.assertFalse(result.assets)
        self.assertFalse(result.ue_code)
        self.assertFalse(result.security_base)
        self.assertFalse(result.asset_full)

    def test_python_change_routes_python_security_only(self):
        result = cc.classify_paths(["physics_reference/src/cycling_physics/model.py"])
        self.assertTrue(result.python)
        self.assertTrue(result.security_base)
        self.assertFalse(result.cpp)
        self.assertFalse(result.assets)
        self.assertFalse(result.ue_code)

    def test_cpp_routes_cpp_and_code_only_unreal(self):
        result = cc.classify_paths(
            ["Source/YetAnotherCyclingSim/Private/CyclingForces.cpp"]
        )
        self.assertTrue(result.cpp)
        self.assertTrue(result.ue_code)
        self.assertTrue(result.security_base)

    def test_build_cs_and_target_cs_route_unreal(self):
        result = cc.classify_paths(
            [
                "Source/YetAnotherCyclingSim/YetAnotherCyclingSim.Build.cs",
                "Source/YetAnotherCyclingSimEditor.Target.cs",
            ]
        )
        self.assertTrue(result.cpp)
        self.assertTrue(result.ue_code)

    def test_critical_config_routes_unreal(self):
        result = cc.classify_paths(["Config/DefaultEngine.ini"])
        self.assertTrue(result.ue_code)
        self.assertFalse(result.assets)

    def test_uproject_routes_unreal(self):
        result = cc.classify_paths(["YetAnotherCyclingSim.uproject"])
        self.assertTrue(result.ue_code)

    def test_asset_only_stays_out_of_cpp_and_python(self):
        result = cc.classify_paths(
            [
                "Content/Prototype/Maps/L_CyclingTest.umap",
                "Content/Prototype/Routes/BP_StraightTestRoute.uasset",
            ]
        )
        self.assertTrue(result.assets)
        self.assertTrue(result.asset_only)
        self.assertFalse(result.cpp)
        self.assertFalse(result.python)
        self.assertFalse(result.ue_code)
        self.assertFalse(result.security_base)
        self.assertTrue(result.asset_full)

    def test_regular_asset_does_not_force_full_unreal(self):
        result = cc.classify_paths(["Content/Prototype/Routes/BP_StraightTestRoute.uasset"])
        self.assertTrue(result.assets)
        self.assertTrue(result.asset_only)
        self.assertFalse(result.asset_full)

    def test_stage3g_source_and_tooling_force_full_validation(self):
        for path in (
            "Source/YetAnotherCyclingSim/Private/Cycling/Stage3PrototypeTerrainActor.cpp",
            "scripts/ue/Invoke-YacsStage3GAuthoring.ps1",
            "worldgen/specs/stage3g_alpine_reference.worldspec.yml",
            ".github/workflows/reusable-stage3g-full.yml",
        ):
            with self.subTest(path=path):
                self.assertTrue(cc.classify_paths([path]).asset_full)

    def test_code_plus_assets_routes_both(self):
        result = cc.classify_paths(
            [
                "Source/YetAnotherCyclingSim/Private/CyclingForces.cpp",
                "Content/Prototype/Maps/L_CyclingTest.umap",
            ]
        )
        self.assertTrue(result.cpp)
        self.assertTrue(result.ue_code)
        self.assertTrue(result.assets)
        self.assertFalse(result.asset_only)

    def test_circleci_config_routes_ci_and_unreal(self):
        result = cc.classify_paths([".circleci/config.yml"])
        self.assertTrue(result.ci)
        self.assertTrue(result.ue_code)
        self.assertTrue(result.security_base)

    def test_github_workflow_routes_ci_without_unreal_by_default(self):
        result = cc.classify_paths([".github/workflows/scorecard.yml"])
        self.assertTrue(result.ci)
        self.assertFalse(result.ue_code)

    def test_reusable_unreal_workflow_routes_unreal(self):
        result = cc.classify_paths([".github/workflows/reusable-unreal.yml"])
        self.assertTrue(result.ci)
        self.assertTrue(result.ue_code)

    def test_ci_python_script_routes_python_and_ci(self):
        result = cc.classify_paths(["scripts/ci/project_automation.py"])
        self.assertTrue(result.python)
        self.assertTrue(result.ci)

    def test_ue_script_routes_unreal_and_ci(self):
        result = cc.classify_paths(["scripts/ue/Invoke-YacsProof.ps1"])
        self.assertTrue(result.ue_code)
        self.assertTrue(result.ci)

    def test_unknown_path_is_explicit_and_security_conservative(self):
        result = cc.classify_paths(["Experimental/new-format.xyz"])
        self.assertTrue(result.unknown)
        self.assertTrue(result.security_base)
        self.assertFalse(result.docs_only)
        self.assertFalse(result.asset_only)

    def test_empty_change_set_fails_closed_as_unknown(self):
        result = cc.classify_paths([])
        self.assertTrue(result.unknown)
        self.assertTrue(result.security_base)

    def test_full_static_does_not_auto_schedule_unreal(self):
        result = cc.full_static_classification()
        self.assertTrue(result.python)
        self.assertTrue(result.cpp)
        self.assertFalse(result.assets)
        self.assertTrue(result.ci)
        self.assertFalse(result.ue_code)
        self.assertFalse(result.asset_full)


if __name__ == "__main__":
    unittest.main()
