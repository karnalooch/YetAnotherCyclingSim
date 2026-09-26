from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CIRCLECI = ROOT / ".circleci" / "config.yml"
GITHUB_WORKFLOWS = ROOT / ".github" / "workflows"

LEGACY_CIRCLECI_PATHS = (
    "docs/ci/CIRCLECI_WINDOWS_UE_PHASE_B.md",
    "docs/ci/CIRCLECI_WINDOWS_UE_SPIKE.md",
    "scripts/ci/Configure-YacsCircleCiRunnerHost.ps1",
    "scripts/ci/Invoke-CircleCiWindowsProbe.ps1",
    "scripts/ci/Prepare-YacsUe58Seed.ps1",
    "scripts/ci/Restore-YacsUe58Seed.ps1",
    "scripts/ci/Test-YacsUe58SeedPayload.ps1",
    "scripts/ci/test_circleci_windows_phase_b.py",
    "scripts/ci/test_circleci_windows_probe.py",
)


class CiPlatformContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.circleci = CIRCLECI.read_text(encoding="utf-8")

    def test_circleci_is_zero_workload_tombstone(self):
        self.assertIn("YACS CI migrated to GitHub Actions", self.circleci)
        self.assertIn("retired_noop:", self.circleci)
        self.assertIn("default: false", self.circleci)
        self.assertIn("when: << pipeline.parameters.retired_noop >>", self.circleci)

    def test_circleci_tombstone_has_no_project_or_storage_work(self):
        for forbidden in (
            "checkout:",
            "machine:",
            "windows.",
            "persist_to_workspace:",
            "attach_workspace:",
            "save_cache:",
            "restore_cache:",
            "store_artifacts:",
            "UE58Seed",
            "Unreal",
            "git lfs",
        ):
            self.assertNotIn(forbidden, self.circleci)

    def test_legacy_circleci_helpers_are_removed(self):
        for relative in LEGACY_CIRCLECI_PATHS:
            self.assertFalse(
                (ROOT / relative).exists(),
                f"legacy CircleCI path must be removed: {relative}",
            )

    def test_github_actions_owns_all_active_ci_entry_points(self):
        for name in (
            "ci.yml",
            "manual-unreal.yml",
            "asset-full.yml",
            "windows-probe.yml",
            "reusable-unreal.yml",
        ):
            self.assertTrue(
                (GITHUB_WORKFLOWS / name).is_file(),
                f"missing GitHub Actions workflow: {name}",
            )

    def test_no_circleci_named_active_workflow_exists(self):
        workflow_names = {path.name for path in GITHUB_WORKFLOWS.glob("*.yml")}
        self.assertFalse(any("circleci" in name.lower() for name in workflow_names))


if __name__ == "__main__":
    unittest.main()
