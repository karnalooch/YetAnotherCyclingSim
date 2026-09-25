from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".circleci" / "config.yml"
SCRIPT = ROOT / "scripts" / "ci" / "Invoke-CircleCiWindowsProbe.ps1"


class CircleCiWindowsProbeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = CONFIG.read_text(encoding="utf-8")
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_probe_is_disabled_by_default(self):
        self.assertIn("windows_probe:", self.config)
        self.assertIn("default: false", self.config)
        self.assertIn("when: << pipeline.parameters.windows_probe >>", self.config)

    def test_probe_uses_windows_2022_medium(self):
        self.assertIn("resource_class: windows.medium", self.config)
        self.assertIn("image: windows-server-2022-gui:current", self.config)

    def test_probe_does_not_install_or_build_unreal(self):
        forbidden = (
            "Setup.bat",
            "GenerateProjectFiles",
            "Build.bat",
            "RunUAT",
            "UnrealEditor",
        )
        for token in forbidden:
            self.assertNotIn(token, self.config)

    def test_probe_records_required_host_contract(self):
        for token in (
            "Win32_OperatingSystem",
            "Win32_ComputerSystem",
            "Win32_Processor",
            "git lfs version",
            "vswhere.exe",
            "UE_5.8",
            "windows_probe.json",
        ):
            self.assertIn(token, self.script)


if __name__ == "__main__":
    unittest.main()
