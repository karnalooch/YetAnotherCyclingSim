from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-probe.yml"
SCRIPT = ROOT / "scripts" / "ci" / "Invoke-YacsWindowsProbe.ps1"


class WindowsProbeWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_probe_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("push:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)

    def test_probe_uses_github_hosted_windows_without_lfs_payloads(self):
        self.assertIn("runs-on: windows-latest", self.workflow)
        self.assertIn('GIT_LFS_SKIP_SMUDGE: "1"', self.workflow)
        self.assertIn("lfs: false", self.workflow)
        self.assertIn("Invoke-YacsWindowsProbe.ps1", self.workflow)

    def test_probe_does_not_install_or_build_unreal(self):
        for token in (
            "Setup.bat",
            "GenerateProjectFiles",
            "Build.bat",
            "RunUAT",
            "UnrealEditor",
        ):
            self.assertNotIn(token, self.workflow)

    def test_probe_uploads_only_small_evidence(self):
        self.assertIn("GitHub-Windows-Probe/**/*.json", self.workflow)
        self.assertIn("GitHub-Windows-Probe/**/*.txt", self.workflow)
        self.assertNotIn("*.zip", self.workflow)
        self.assertNotIn("Content/**", self.workflow)
        self.assertNotIn("Engine/**", self.workflow)

    def test_probe_records_github_and_host_contract(self):
        for token in (
            "GitHubActions",
            "GITHUB_RUN_ID",
            "GITHUB_WORKFLOW",
            "Win32_OperatingSystem",
            "Win32_ComputerSystem",
            "Win32_Processor",
            "git lfs version",
            "vswhere.exe",
            "UE_5.8",
            "windows_probe.json",
            "GITHUB WINDOWS PROBE PASSED",
        ):
            self.assertIn(token, self.script)


if __name__ == "__main__":
    unittest.main()
