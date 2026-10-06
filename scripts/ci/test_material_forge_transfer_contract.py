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

    def test_single_editor_process_runs_both_ue_subproofs(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("Start-Process -FilePath $engine.UnrealEditorPath"),
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

        unified = (
            ROOT / "scripts/ue/run_material_forge_unified_proof.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"execution_mode": execution_mode', unified)
        self.assertIn('"after_gc": memory_after_gc', unified)

    def test_transfer_metrics_are_preserved(self):
        text = CANARY.read_text(encoding="utf-8")
        self.assertIn("proof-transfer-metrics.json", text)
        self.assertIn("lfs-cache-metrics.json", text)
        self.assertIn("cache_hits_before_fetch", text)
        self.assertIn("cache_misses_before_fetch", text)


if __name__ == "__main__":
    unittest.main()
