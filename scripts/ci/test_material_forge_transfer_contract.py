"""Static contracts for Material Forge proof-transfer optimization."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MALLORCA = ROOT / ".github/workflows/material-forge-mallorca-proof.yml"
CANARY = ROOT / ".github/workflows/material-forge-ue-canary.yml"
FAST = ROOT / ".github/workflows/material-forge-fast-visual.yml"


class MaterialForgeTransferContractTests(unittest.TestCase):
    def test_full_and_slim_artifacts_are_both_retained(self):
        text = MALLORCA.read_text(encoding="utf-8")
        self.assertIn("Upload slim UE canary input", text)
        self.assertIn(
            "material-forge-canary-input-${{ github.sha }}-${{ github.run_attempt }}",
            text,
        )
        self.assertIn("Upload compact render proof evidence", text)
        self.assertIn(
            "material-forge-mallorca-${{ github.sha }}-${{ github.run_attempt }}",
            text,
        )

    def test_ue_canary_consumes_slim_artifact(self):
        text = MALLORCA.read_text(encoding="utf-8")
        self.assertIn(
            "proof_artifact_name: "
            "material-forge-canary-input-${{ github.sha }}-${{ github.run_attempt }}",
            text,
        )

    def test_fixed_master_builder_change_triggers_material_forge_proof(self):
        text = MALLORCA.read_text(encoding="utf-8")
        self.assertIn(
            '"scripts/ue/build_material_forge_landscape_master.py"',
            text,
        )

    def test_persistent_lfs_cache_is_on_workspace_drive(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertIn(
            r"YACS_LFS_CACHE_ROOT: 'D:\yacs\cache\git-lfs\YetAnotherCyclingSim'",
            text,
        )
        self.assertIn(
            "git config --local lfs.storage $env:YACS_LFS_CACHE_ROOT",
            text,
        )
        self.assertNotIn("YACS_LFS_CACHE_ROOT: 'C:\\", text)

    def test_fixed_master_bootstrap_isolated_from_canary_process(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("Start-Process -FilePath $engine.UnrealEditorPath"),
            3,
        )
        self.assertIn("build_material_forge_landscape_master.py", text)
        self.assertIn("YACS_MF_TEMPLATE_BUILDER_PROCESS_COUNT=1", text)
        self.assertIn("Refusing to delete tracked fixed-master bootstrap asset", text)
        self.assertIn("M_MaterialForgeLandscapeBlend", text)
        self.assertIn("T_MF_ORMPlaceholder", text)

    def test_single_editor_process_runs_both_ue_subproofs(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("run_material_forge_unified_proof.py"),
            1,
        )
        self.assertIn("run_material_forge_unified_proof.py", text)

        unified = (ROOT / "scripts/ue/run_material_forge_unified_proof.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("chunked.main(load_map=True)", unified)
        self.assertIn("unreal.collect_garbage()", unified)
        self.assertIn("canary.main(load_map=False)", unified)
        self.assertIn('"editor_process_count": 1', unified)
        self.assertIn('"map_load_count": 1', unified)

    def test_offscreen_ue_canary_has_no_window_contract(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertIn("'-RenderOffscreen'", text)
        self.assertIn("'-NoSound'", text)
        self.assertNotIn("'-windowed'", text)
        self.assertNotIn("'-ResX=1920'", text)
        self.assertNotIn("'-ResY=1080'", text)
        self.assertIn("YACS_UE_EXECUTION_MODE = 'RenderOffscreen'", text)

        unified = (ROOT / "scripts/ue/run_material_forge_unified_proof.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"execution_mode": execution_mode', unified)
        self.assertIn('"after_gc": memory_after_gc', unified)

    def test_owner_visual_capture_is_whole_landscape_and_rollback_safe(self):
        canary = CANARY.read_text(encoding="utf-8")
        mallorca = MALLORCA.read_text(encoding="utf-8")
        visual = (ROOT / "scripts/ue/capture_material_forge_landscape.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Capture production Landscape visual proof", canary)
        self.assertIn("material-forge-landscape-visual-", canary)
        self.assertNotIn('"scripts/ue/capture_material_forge_landscape.py"', mallorca)
        self.assertIn("FULL_CAPTURE_RESOLUTION = [3840, 2160]", visual)
        self.assertIn("whole_landscape_components", visual)
        self.assertIn("MF_LANDSCAPE_VISUAL_PROOF_PASS", visual)
        self.assertIn("rollback_complete", visual)
        self.assertIn('"PENDING_OWNER"', visual)
        self.assertIn('"FAST_REVIEW_ONLY"', visual)
        self.assertIn("set_keep_python_script_alive(True)", visual)
        self.assertIn("take_high_res_screenshot", visual)

    def test_refinement_c_pair_and_cliff_diagnostics_are_pinned(self):
        mallorca = MALLORCA.read_text(encoding="utf-8")
        canary = CANARY.read_text(encoding="utf-8")

        for token in (
            "regional_limestone\\refined_c",
            "mediterranean_soil\\refined_c",
            "regional_limestone/refined_c",
            "mediterranean_soil/refined_c",
        ):
            self.assertIn(token, mallorca)

        self.assertIn("regional_limestone\\refined_c", canary)
        self.assertIn("mediterranean_soil\\refined_c", canary)
        self.assertIn("[int]$receipt.capture_count -ne 4", canary)
        self.assertIn("[int]$receipt.diagnostic_count -ne 3", canary)
        self.assertIn("$diagnosticModes -notcontains 'unlit'", canary)
        self.assertIn("$diagnosticModes -notcontains 'lightingonly'", canary)
        self.assertIn("$diagnosticModes -notcontains 'lit_detaillighting'", canary)

    def test_canary_identity_follows_exact_variant_provenance(self):
        runner = (ROOT / "scripts/ue/run_material_forge_canary_proof.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('variant_dir / "provenance.json"', runner)
        self.assertIn('expected_family != "regional_limestone"', runner)
        self.assertIn('imported.get("variant") != expected_variant', runner)
        self.assertIn('f"{expected_family}/{expected_variant}"', runner)
        self.assertNotIn('"regional_limestone/refined_a"', runner)
        self.assertNotIn('imported.get("variant") != "refined_a"', runner)

    def test_compact_full_evidence_drops_duplicate_raw_runs(self):
        text = MALLORCA.read_text(encoding="utf-8")
        self.assertIn("Prepare compact render evidence", text)
        self.assertIn("raw_run_payloads_retained = $false", text)
        self.assertIn("Compact Material Forge evidence exceeded 200 MiB", text)
        self.assertIn("compact-evidence-receipt.json", text)
        self.assertIn("compression-level: 6", text)

    def test_fast_visual_loop_is_non_production_and_fail_closed(self):
        fast = FAST.read_text(encoding="utf-8")
        visual = (ROOT / "scripts/ue/capture_material_forge_landscape.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Material Forge FAST cliff visual", fast)
        self.assertIn("plan-rebuild", fast)
        self.assertIn("FAST_VISUAL_WARM_CACHE_REQUIRED", fast)
        self.assertIn(".gumball/workflow-lifecycle.json", fast)
        self.assertIn("YACS_MF_FAST_VISUAL=1", fast)
        self.assertIn("material-forge-canary-input-", fast)
        self.assertIn("NON_PRODUCTION_FAST_VISUAL", visual)
        self.assertIn("full_production_proof_required", visual)
        self.assertIn("FAST_CAPTURE_RESOLUTION = [1920, 1080]", visual)
        self.assertIn("[int]$receipt.capture_count -ne 1", fast)
        self.assertIn("[int]$receipt.diagnostic_count -ne 5", fast)
        self.assertIn("$diagnosticModes -notcontains $requiredMode", fast)
        self.assertIn('"fast-cliff-unlit"', visual)
        self.assertIn('"fast-cliff-lighting-only"', visual)
        self.assertIn('"fast-cliff-lighting-no-dynamic-shadows"', visual)
        self.assertIn('"fast-cliff-detail-lighting"', visual)
        self.assertIn('"showflag.DynamicShadows 0"', visual)
        self.assertGreaterEqual(visual.count('"showflag.DynamicShadows 1"'), 2)
        self.assertIn("dynamic_shadows", visual)
        self.assertIn("FAST dynamic-shadow isolation probe contract failed.", fast)
        self.assertIn('"fast-cliff-lighting-slope-bias-1"', visual)
        self.assertIn("set_shadow_slope_bias", visual)
        self.assertIn("directional_shadow_bias", visual)
        self.assertIn("requested_shadow_slope_bias", visual)
        self.assertIn("FAST shadow-slope-bias probe frame contract failed.", fast)
        self.assertIn("FAST ShadowSlopeBias=1.0 readback failed.", fast)
        self.assertIn("def _canonical_component_bounds():", visual)
        self.assertIn(
            '"canonical_component_bounds": _canonical_component_bounds()', visual
        )
        self.assertIn("FAST canonical component bounds receipt contract failed.", fast)
        self.assertIn(
            "FAST shadow-slope-bias probe was a no-op at the current baseline.", fast
        )

    def test_fast_color_grade_controls_are_neutral_bounded_and_recorded(self):
        builder = (
            ROOT / "scripts/ue/build_material_forge_landscape_master.py"
        ).read_text(encoding="utf-8")
        preview = (
            ROOT / "scripts/ue/preview_material_forge_chunked_landscape.py"
        ).read_text(encoding="utf-8")
        visual = (ROOT / "scripts/ue/capture_material_forge_landscape.py").read_text(
            encoding="utf-8"
        )
        fast = FAST.read_text(encoding="utf-8")
        mallorca = MALLORCA.read_text(encoding="utf-8")

        self.assertIn('parameter_name=prefix + "ColorGain"', builder)
        self.assertIn('"RockColorGain"', builder)
        self.assertIn('"SoilColorGain"', builder)
        self.assertIn('"color_gain_defaults"', builder)
        self.assertIn("get_vector_parameter_names(instance)", preview)
        self.assertIn("Fixed-master vector parameter contract missing", preview)
        self.assertIn("Fixed-master vector readback failed", preview)
        self.assertIn("color_gain_values=None", preview)
        self.assertIn("vector_values = dict(color_gain_values)", preview)
        self.assertIn("COLOR_GAIN_MIN = 0.65", visual)
        self.assertIn("COLOR_GAIN_MAX = 1.35", visual)
        self.assertIn("YACS_MF_ROCK_COLOR_GAIN", visual)
        self.assertIn("YACS_MF_SOIL_COLOR_GAIN", visual)
        self.assertIn("Fixed-master color gain readback failed", visual)
        self.assertIn("color_gain_values=requested_color_gains", visual)
        self.assertIn(
            "_verify_color_gain_readback(_instance, requested_color_gains)", visual
        )
        self.assertNotIn("LIB.update_material_instance(instance)", visual)
        self.assertIn('"color_gains": _color_gains', visual)
        self.assertIn("rock_color_gain:", fast)
        self.assertIn("soil_color_gain:", fast)
        self.assertIn("FAST color-gain receipt contract failed.", fast)
        self.assertIn(
            '"scripts/ue/preview_material_forge_chunked_landscape.py"', mallorca
        )
        self.assertIn('"scripts/ue/build_material_forge_landscape_master.py"', mallorca)

    def test_transfer_metrics_are_preserved(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertIn("proof-transfer-metrics.json", text)
        self.assertIn("lfs-cache-metrics.json", text)
        self.assertIn("cache_hits_before_fetch", text)
        self.assertIn("cache_misses_before_fetch", text)


if __name__ == "__main__":
    unittest.main()
