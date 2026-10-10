"""Road asphalt GPU host policy regression; independent native capture is required."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1"
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"
ATTRIBUTES = ROOT / ".gitattributes"


class RoadAsphaltGpuHostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = HOST.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_gpu_review_follows_saved_and_fresh_reopened_native_consumer(self):
        order = (
            "Stage verified consumer and read native baseline",
            "Run isolated reversible road asphalt canary",
            "Save and fresh-reopen the isolated road asphalt consumer",
            "Capture native road-facing lit GPU review",
            "Retain native inventory and owned-process evidence",
        )
        positions = [self.workflow.index(stage) for stage in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Invoke-YacsRoadAsphaltRender.ps1", self.workflow)

    def test_bounded_pinned_windows_host_and_gui_rhi(self):
        for key in (
            "Require-ExactSource",
            "Require-IdleHost",
            "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS",
            "Get-YacsUnrealHostState.ps1",
            "UnrealEditor-Cmd.exe",
            "UnrealEditor.exe",
            "-RenderOffscreen",
            "-ScriptErrorsAreFatal",
            "Unreal GPU review process",
            "WaitForExit(200)",
            "480",
            "readHost.value.proof_files",
            "road-asphalt-lit-review.json",
            "road-asphalt-gpu-host-receipt.json",
            "ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS",
            "File-Identity",
            "Write-ExclusiveReceipt",
            "Get-FileHash",
            "saved_derived_consumer",
        ):
            with self.subTest(key=key):
                self.assertIn(key, self.host)
        self.assertNotIn("'-NullRHI'", self.host)
        self.assertNotIn("save_map(", self.host)
        self.assertNotIn("Start-Job", self.host)

    def test_flags_never_admit_owner_visual_performance_or_shader_benchmark(self):
        for key in (
            "PENDING_FINAL_M3",
            "DEFERRED_AFTER_M3",
            "gpu_shader_compilation_admitted = $false",
            "road_pixel_visibility_admitted = $false",
            "native_lit_frames_retained",
            "verified_frame_count",
            "owner_visual_status",
            "performance_pass = $false",
        ):
            self.assertIn(key, self.host)

    def test_gpu_wrapper_bytes_and_workflow_triggers_are_explicit(self):
        attributes = ATTRIBUTES.read_text(encoding="utf-8")
        self.assertIn(
            "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1 text eol=lf",
            attributes,
        )
        self.assertNotIn(b"\r", HOST.read_bytes())
        trigger = self.workflow.split("permissions:", 1)[0]
        for name in (
            "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1",
            "scripts/ue/road_asphalt_gpu_review.py",
            "scripts/ue/test_road_asphalt_gpu_review.py",
        ):
            self.assertIn("- '" + name + "'", trigger)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_real_powershell_parser_accepts_native_gpu_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "check.ps1"
            path.write_text(
                """param([string] $Script)
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $Script, [ref] $tokens, [ref] $errors
) | Out-Null
if ($errors.Count) { throw ($errors.Message -join "; ") }
""",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(path), str(HOST)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
