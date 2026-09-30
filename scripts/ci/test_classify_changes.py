from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
        self.assertEqual(result.ci_cost_class, "light")

    def test_python_change_routes_python_security_only(self):
        result = cc.classify_paths(["physics_reference/src/cycling_physics/model.py"])
        self.assertTrue(result.python)
        self.assertTrue(result.security_base)
        self.assertFalse(result.cpp)
        self.assertFalse(result.assets)
        self.assertFalse(result.ue_code)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_cpp_routes_cpp_and_code_only_unreal(self):
        result = cc.classify_paths(
            ["Source/YetAnotherCyclingSim/Private/CyclingForces.cpp"]
        )
        self.assertTrue(result.cpp)
        self.assertTrue(result.ue_code)
        self.assertTrue(result.security_base)
        self.assertEqual(result.ci_cost_class, "heavy")

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
        self.assertEqual(result.ci_cost_class, "heavy")

    def test_regular_asset_does_not_force_full_unreal(self):
        result = cc.classify_paths(
            ["Content/Prototype/Routes/BP_StraightTestRoute.uasset"]
        )
        self.assertTrue(result.assets)
        self.assertTrue(result.asset_only)
        self.assertFalse(result.asset_full)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_yacs_worldgen_pcg_asset_forces_full_validation(self):
        result = cc.classify_paths(["Content/YACS/WorldGen/PCG/PCG_Valley.uasset"])
        self.assertTrue(result.assets)
        self.assertTrue(result.asset_only)
        self.assertTrue(result.asset_full)

    def test_stage3g_source_and_tooling_force_full_validation(self):
        for path in (
            "Source/YetAnotherCyclingSim/Private/Cycling/Stage3PrototypeTerrainActor.cpp",
            "scripts/ue/Invoke-YacsStage3GAuthoring.ps1",
            "worldgen/specs/stage3g_alpine_reference.worldspec.yml",
            ".github/workflows/reusable-stage3g-full.yml",
        ):
            with self.subTest(path=path):
                self.assertTrue(cc.classify_paths([path]).asset_full)

    def test_asset_full_ue_tooling_is_heavy_without_code_build(self):
        result = cc.classify_paths(["scripts/ue/Invoke-YacsStage3GAuthoring.ps1"])
        self.assertTrue(result.ue_tooling)
        self.assertTrue(result.asset_full)
        self.assertFalse(result.ue_code)
        self.assertEqual(result.ci_cost_class, "heavy")

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

    def test_plugin_cpp_routes_cpp_and_unreal(self):
        result = cc.classify_paths(
            ["Plugins/YacsTools/Source/YacsTools/Private/YacsTools.cpp"]
        )
        self.assertTrue(result.cpp)
        self.assertTrue(result.ue_code)
        self.assertEqual(result.ci_cost_class, "heavy")

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

    def test_proof_only_ue_script_routes_tooling_without_unreal_build(self):
        result = cc.classify_paths(
            ["scripts/ue/Invoke-YacsPassoGiauHairpinCorridorProof.ps1"]
        )
        self.assertTrue(result.ue_tooling)
        self.assertTrue(result.ci)
        self.assertFalse(result.ue_code)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_editor_authoring_python_routes_python_and_tooling_without_unreal_build(
        self,
    ):
        result = cc.classify_paths(["scripts/ue/stage3g_capture_passo_giau_road.py"])
        self.assertTrue(result.python)
        self.assertTrue(result.ci)
        self.assertTrue(result.ue_tooling)
        self.assertFalse(result.ue_code)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_code_build_proof_wrapper_still_routes_unreal(self):
        for path in (
            "scripts/ue/Invoke-YacsProof.ps1",
            "scripts/ue/Preflight-YacsProof.ps1",
            "scripts/ci/Invoke-YacsUnrealCi.ps1",
            "scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1",
            "scripts/ci/Test-YacsCodeOnlyCheckout.ps1",
            ".github/workflows/reusable-unreal.yml",
        ):
            with self.subTest(path=path):
                result = cc.classify_paths([path])
                self.assertTrue(result.ue_code)
                self.assertEqual(result.ci_cost_class, "heavy")

    def test_manual_unreal_workflow_is_ci_not_automatic_code_build(self):
        result = cc.classify_paths([".github/workflows/manual-unreal.yml"])
        self.assertTrue(result.ci)
        self.assertFalse(result.ue_code)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_unknown_path_is_explicit_and_security_conservative(self):
        result = cc.classify_paths(["Experimental/new-format.xyz"])
        self.assertTrue(result.unknown)
        self.assertTrue(result.security_base)
        self.assertFalse(result.ue_code)
        self.assertFalse(result.docs_only)
        self.assertFalse(result.asset_only)
        self.assertEqual(result.ci_cost_class, "standard")

    def test_unknown_runtime_sensitive_path_fails_closed_to_unreal(self):
        result = cc.classify_paths(["Plugins/YacsTools/Resources/runtime.payload"])
        self.assertTrue(result.unknown)
        self.assertTrue(result.ue_code)
        self.assertTrue(result.security_base)
        self.assertEqual(result.ci_cost_class, "heavy")

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

    def test_main_emits_github_outputs_for_worldgen_pcg(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths_file = root / "paths.txt"
            output_file = root / "github-output.txt"
            paths_file.write_text(
                "Content/YACS/WorldGen/PCG/PCG_Valley.uasset\n",
                encoding="utf-8",
            )

            result = cc.main(
                [
                    "--paths-file",
                    str(paths_file),
                    "--github-output",
                    str(output_file),
                ]
            )

            self.assertEqual(result, 0)
            emitted = output_file.read_text(encoding="utf-8")
            self.assertIn("assets=true\n", emitted)
            self.assertIn("asset_full=true\n", emitted)
            self.assertIn("ue_tooling=false\n", emitted)
            self.assertIn("ci_cost_class=heavy\n", emitted)
            self.assertIn("base_sha=PATHS_FILE\n", emitted)
            self.assertIn("head_sha=PATHS_FILE\n", emitted)


if __name__ == "__main__":
    unittest.main()
