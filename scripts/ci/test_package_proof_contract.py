from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ue" / "Invoke-YacsPackageProof.ps1"


class PackageProofContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_uses_buildcookrun_with_explicit_prototype_map(self):
        self.assertIn("'BuildCookRun'", self.script)
        self.assertIn("'/Game/Prototype/Maps/L_CyclingTest'", self.script)

    def test_buildcookrun_covers_build_cook_stage_and_archive(self):
        for token in (
            "'-build'",
            "'-cook'",
            "'-stage'",
            "'-pak'",
            "'-archive'",
            "'-platform=Win64'",
        ):
            self.assertIn(token, self.script)

    def test_supports_only_explicit_development_or_shipping(self):
        self.assertIn(
            "[ValidateSet('Development', 'Shipping')]",
            self.script,
        )
        self.assertIn("clientconfig=", self.script)

    def test_package_must_contain_game_executable(self):
        self.assertIn("YetAnotherCyclingSim.exe", self.script)
        self.assertIn("ExecutableCount", self.script)

    def test_package_must_contain_cooked_container(self):
        self.assertIn("*.pak", self.script)
        self.assertIn("*.utoc", self.script)
        self.assertIn("*.ucas", self.script)
        self.assertIn("No packaged content container", self.script)

    def test_package_log_must_reference_requested_map(self):
        self.assertIn("BuildCookRun log does not mention required map", self.script)

    def test_package_output_stays_under_saved_runtime_proof(self):
        self.assertIn("Saved/RuntimeProof/CI/Package", self.script)
        self.assertNotIn("git push", self.script)
        self.assertNotIn("gh release", self.script)

    def test_summary_is_machine_readable(self):
        self.assertIn("package_summary.json", self.script)
        self.assertIn("ArchiveBytes", self.script)
        self.assertIn("HasIoStore", self.script)


if __name__ == "__main__":
    unittest.main()
