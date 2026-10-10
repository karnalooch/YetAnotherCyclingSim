"""Contract for exact-HEAD native saved road consumer execution and evidence."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"
WRAPPER = ROOT / "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1"
SCRIPT = ROOT / "scripts/ue/road_asphalt_saved_consumer.py"


class RoadSavedHostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.host = WRAPPER.read_text(encoding="utf-8")

    def test_reader_then_canary_then_saved_reopen_order(self):
        steps = (
            "Stage verified consumer and read native baseline",
            "Run isolated reversible road asphalt canary",
            "Save and fresh-reopen the isolated road asphalt consumer",
            "Retain native inventory and owned-process evidence",
        )
        offsets = [self.workflow.index(step) for step in steps]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("Invoke-YacsRoadSavedConsumer.ps1", self.workflow)
        self.assertIn("    concurrency:", self.workflow)
        self.assertIn("    needs: await_ci", self.workflow)

    def test_exact_git_and_predecessor_proofs_gate_both_editors(self):
        for field in (
            "Require-ExactSource",
            "Require-IdleHost",
            "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE",
            "ROAD_ASPHALT_TRANSIENT_HOST_PASS",
            "native_baseline.sha256",
            "native_canary.sha256",
            "source_scene_mutated",
            "Editor executable",
            "Assert-Identity",
            "Native save code/config differs from Git HEAD",
            "Invoke-OwnedEditor 'prepare'",
            "Invoke-OwnedEditor 'reload'",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.host)

    def test_scoped_native_reopened_result_never_claims_gpu_owner_or_fps(self):
        for field in (
            "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS",
            "road-asphalt-saved-prepared.json",
            "road-asphalt-saved-reloaded.json",
            "saved-road-host-receipt.json",
            "PENDING_FINAL_M3",
            "DEFERRED_AFTER_M3",
            "-NullRHI",
            "420",
            "Get-ClosedLog",
            "CreateNew",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.host)
        self.assertNotIn("save_asset(", self.host)
        self.assertNotIn("clean -fd", self.host)

    def test_exact_power_shell_lf_and_native_workflow_triggers(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(
            "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1 text eol=lf",
            attributes,
        )
        self.assertNotIn(b"\r", WRAPPER.read_bytes())
        triggers = self.workflow.split("permissions:", 1)[0]
        for path in (
            "scripts/ue/road_asphalt_saved_consumer.py",
            "scripts/ue/test_road_asphalt_saved_consumer.py",
            "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1",
        ):
            self.assertIn(f"- '{path}'", triggers)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_real_powershell_parser_accepts_owned_host_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "parse.ps1"
            fixture.write_text(
                """
param([string] $Script)
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $Script, [ref] $tokens, [ref] $errors
) | Out-Null
if ($errors.Count) { throw ($errors.Message -join "\u0060n") }
""",
                encoding="utf-8",
            )
            process = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(fixture), str(WRAPPER)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)

    def test_frozen_recipe_checkout_preserves_raw_bytes_with_windows_autocrlf(self):
        relative = "worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json"
        source = (ROOT / relative).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*arguments):
                result = subprocess.run(["git", "-C", str(root), *arguments],
                    capture_output=True, timeout=30, check=False)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                return result.stdout
            git("init", "-q")
            git("config", "core.autocrlf", "true")
            git("config", "core.safecrlf", "false")
            (root / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(source)
            control = root / "unmatched.json"
            control.write_bytes(b'{"control": true}\n')
            git("add", ".gitattributes", relative, "unmatched.json")
            path.unlink()
            control.unlink()
            git("checkout-index", "--", relative, "unmatched.json")
            self.assertIn(b"\r\n", control.read_bytes())
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(git("hash-object", "--no-filters", relative).strip(),
                             git("rev-parse", ":" + relative).strip())


if __name__ == "__main__":
    unittest.main()
