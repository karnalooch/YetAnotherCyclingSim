"""Static host boundary regression; no actual Unreal Editor is started."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/ue/Invoke-YacsRoadAsphaltNativeCanary.ps1"
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"


class NativeAsphaltHostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = WRAPPER.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_baseline_always_precedes_native_transient_canary(self):
        self.assertLess(
            self.workflow.index("Stage verified consumer and read native baseline"),
            self.workflow.index("Run isolated reversible road asphalt canary"),
        )
        self.assertIn("Invoke-YacsRoadAsphaltNativeCanary.ps1", self.workflow)
        self.assertIn("-ExpectedHead $env:GITHUB_SHA", self.workflow)

    def test_original_green_baseline_and_modules_are_authentication_gates(self):
        for token in (
            "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE",
            "host.proof_files.native_baseline.sha256",
            "owned_editor_exit_code -ne 0",
            "Get-Identity $row.copied_identity.path 512MB",
            "Require-IdleHost",
            "Require-Source",
        ):
            self.assertIn(token, self.host)

    def test_transient_scope_is_unambiguous_and_failure_stops(self):
        for token in (
            "-NullRHI",
            "-ScriptErrorsAreFatal",
            "road-asphalt-canary.json",
            "native_material_bind_and_rollback_verified",
            "saved_consumer_verified",
            "shader_gpu_compilation_verified",
            "asphalt-host-receipt.json",
            "ROAD_ASPHALT_TRANSIENT_HOST_PASS",
            "deadline_seconds = 420",
            "Get-ClosedLogIdentity",
            "Write-ExclusiveJson",
        ):
            self.assertIn(token, self.host)
        self.assertNotIn("save_asset(", self.host)


if __name__ == "__main__":
    unittest.main()
