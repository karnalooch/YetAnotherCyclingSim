import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
HARNESS = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GEnvironmentPerformance.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "stage3g-environment-performance.yml"
CPP = ROOT / "Source" / "YetAnotherCyclingSim" / "Private" / "Tests" / "CyclingStage3GEnvironmentPerformanceProof.spec.cpp"


class Stage3GEnvironmentPerformanceContract(unittest.TestCase):
    def test_harness_keeps_60fps_fail_closed_budget(self):
        text = HARNESS.read_text(encoding="utf-8")
        self.assertIn("[double] $TargetFps = 60.0", text)
        self.assertIn("$FrameBudgetMs = 1000.0 / $TargetFps", text)
        self.assertIn("$FrameP95 -le $FrameBudgetMs", text)
        self.assertIn("$GpuP95 -le $FrameBudgetMs", text)
        self.assertIn("[double] $AllowedOverBudgetRatio = 0.05", text)
        self.assertIn("$OverBudgetRatio -le $AllowedOverBudgetRatio", text)
        self.assertIn("RTX\\s*2070.*SUPER", text)
        self.assertIn("$Proc.ExitCode -ne 0", text)
        self.assertIn("exit 1", text)

    def test_sampler_covers_all_visual_history_sectors(self):
        text = CPP.read_text(encoding="utf-8")
        self.assertIn("1200.0", text)
        self.assertIn("4900.0", text)
        self.assertIn("8000.0", text)
        self.assertIn("FApp::GetDeltaTime()", text)
        self.assertIn("GetAverageUnitTimes", text)
        self.assertIn("GGPUFrameTime", text)
        self.assertIn("EngineGlobals.h", text)
        self.assertIn("YACS_STAGE3G_PERF_CSV", text)

    def test_workflow_is_trusted_self_hosted_and_publishes_failure_evidence(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
        self.assertIn("perf/stage3g-environment-gate", text)\n        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("Invoke-YacsStage3GEnvironmentPerformance.ps1", text)
        self.assertIn("if: $" + "{{ always() }}", text)
        self.assertIn("stage3g-environment-performance-", text)
        self.assertIn("retention-days: 14", text)


if __name__ == "__main__":
    unittest.main()
