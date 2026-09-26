from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "scripts" / "ue" / "Invoke-YacsProof.ps1"
CI_WRAPPER = ROOT / "scripts" / "ci" / "Invoke-YacsUnrealCi.ps1"
PREFLIGHT = ROOT / "scripts" / "ue" / "Preflight-YacsProof.ps1"


class UnrealCiBuildProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = PROOF.read_text(encoding="utf-8")
        cls.ci_wrapper = CI_WRAPPER.read_text(encoding="utf-8")
        cls.preflight = PREFLIGHT.read_text(encoding="utf-8")

    def test_ci_wrapper_always_uses_conservative_build_profile(self):
        self.assertIn("ConservativeBuild = $true", self.ci_wrapper)
        self.assertIn("$ProofArgs", self.ci_wrapper)

    def test_conservative_profile_is_project_local_and_ephemeral(self):
        self.assertIn("Saved/UnrealBuildTool", self.proof)
        self.assertIn("BuildConfiguration.xml", self.proof)
        self.assertNotIn("AppData\\Roaming\\Unreal Engine", self.proof)

    def test_conservative_profile_disables_uba(self):
        self.assertIn("<bAllowUBAExecutor>false</bAllowUBAExecutor>", self.proof)
        self.assertIn(
            "<bAllowUBALocalExecutor>false</bAllowUBALocalExecutor>",
            self.proof,
        )

    def test_conservative_profile_limits_parallel_actions(self):
        self.assertIn("<MaxParallelActions>2</MaxParallelActions>", self.proof)

    def test_preflight_records_memory_and_pagefile_headroom(self):
        for token in (
            "FreePhysicalMemory",
            "TotalVirtualMemorySize",
            "FreeVirtualMemory",
            "Win32_PageFileUsage",
            "Memory headroom",
            "Page file",
        ):
            self.assertIn(token, self.preflight)


if __name__ == "__main__":
    unittest.main()
