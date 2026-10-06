"""Static contract for the portable PowerShell runner toolchain."""

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PortablePowerShellContractTests(unittest.TestCase):
    def test_manifest_pins_exact_official_release(self):
        manifest = json.loads(
            (ROOT / "scripts/runner/powershell-toolchain.json").read_text()
        )
        self.assertEqual(manifest["version"], "7.6.6")
        self.assertEqual(
            manifest["workspace_directory"],
            "tools/powershell-7.6.6-win-x64",
        )
        self.assertEqual(
            manifest["sha256"],
            "02fe458be20493fbdf43f61ea20610b811ee6c738ab1676c61b9cfcd1a33c860",
        )
        self.assertEqual(
            manifest["download_url"],
            "https://github.com/PowerShell/PowerShell/releases/download/v7.6.6/"
            "PowerShell-7.6.6-win-x64.zip",
        )

    def test_installer_is_windows_powershell_compatible_and_hash_gated(self):
        text = (ROOT / "scripts/runner/Install-YacsPortablePowerShell.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("#requires -Version 5.1", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("Expand-Archive", text)
        self.assertIn("Test-PinnedPowerShell", text)
        self.assertIn("archive\\toolchains", text)
        self.assertNotIn("Program Files", text)

    def test_bootstrap_workflow_does_not_require_pwsh_to_install_pwsh(self):
        text = (ROOT / ".github/workflows/portable-powershell.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("shell: powershell", text)
        self.assertIn("Install-YacsPortablePowerShell.ps1", text)
        self.assertIn("$env:GITHUB_PATH", text)
        self.assertIn("shell: pwsh", text)
        install = text.index("shell: powershell")
        verify = text.index("shell: pwsh")
        self.assertLess(install, verify)

    def test_runner_startup_prefers_portable_toolchain(self):
        text = (ROOT / "scripts/runner/Start-YacsRunner.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Install-YacsPortablePowerShell.ps1", text)
        self.assertIn("powershell-7.6.6-win-x64", text)
        self.assertIn("$env:PATH", text)


if __name__ == "__main__":
    unittest.main()
