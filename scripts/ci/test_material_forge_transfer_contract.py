"""Static contracts for Material Forge proof-transfer optimization."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MALLORCA = ROOT / ".github/workflows/material-forge-mallorca-proof.yml"
CANARY = ROOT / ".github/workflows/material-forge-ue-canary.yml"


class MaterialForgeTransferContractTests(unittest.TestCase):
    def test_full_and_slim_artifacts_are_both_retained(self):
        text = MALLORCA.read_text(encoding="utf-8")
        self.assertIn("Upload slim UE canary input", text)
        self.assertIn(
            "material-forge-canary-input-${{ github.sha }}-${{ github.run_attempt }}",
            text,
        )
        self.assertIn("Upload complete render proof", text)
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
        self.assertIn('"scripts/ue/capture_material_forge_landscape.py"', mallorca)
        self.assertIn("CAPTURE_RESOLUTION = [3840, 2160]", visual)
        self.assertIn("whole_landscape_components", visual)
        self.assertIn("MF_LANDSCAPE_VISUAL_PROOF_PASS", visual)
        self.assertIn("rollback_complete", visual)
        self.assertIn('human_visual_status": "PENDING_OWNER"', visual)
        self.assertIn("set_keep_python_script_alive(True)", visual)
        self.assertIn("take_high_res_screenshot", visual)

    def test_refinement_b_pair_and_cliff_diagnostics_are_pinned(self):
        mallorca = MALLORCA.read_text(encoding="utf-8")
        canary = CANARY.read_text(encoding="utf-8")

        for token in (
            "regional_limestone\\refined_b",
            "mediterranean_soil\\refined_b",
            "regional_limestone/refined_b",
            "mediterranean_soil/refined_b",
        ):
            self.assertIn(token, mallorca)

        self.assertIn("regional_limestone\\refined_b", canary)
        self.assertIn("mediterranean_soil\\refined_b", canary)
        self.assertIn("[int]$receipt.capture_count -ne 4", canary)
        self.assertIn("[int]$receipt.diagnostic_count -ne 3", canary)
        self.assertIn("$diagnosticModes -notcontains 'unlit'", canary)
        self.assertIn("$diagnosticModes -notcontains 'lightingonly'", canary)
        self.assertIn("$diagnosticModes -notcontains 'lit_detaillighting'", canary)

    def test_transfer_metrics_are_preserved(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertIn("proof-transfer-metrics.json", text)
        self.assertIn("lfs-cache-metrics.json", text)
        self.assertIn("cache_hits_before_fetch", text)
        self.assertIn("cache_misses_before_fetch", text)


if __name__ == "__main__":
    unittest.main()
