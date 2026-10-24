"""Fixture-only tests for exact-current-run quarantine; never touches the real runner."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "scripts/runner/Invoke-YacsJobCompleted.ps1"
PWSH = shutil.which("pwsh")


@unittest.skipUnless(PWSH, "PowerShell 7 required")
class RetentionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "Saved").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "Saved")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def ps(self, code):
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        script = (
            "$ErrorActionPreference='Stop'; . "
            + quote(HOOK)
            + "; $fixture="
            + quote(self.root)
            + "; "
            + code
        )
        result = subprocess.run(
            [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_confinement_rejects_sibling(self):
        self.ps(
            "$rejected=$false; try { Assert-RetentionPath ($fixture+'-sibling/child') $fixture } catch { $rejected=$true }; if(-not $rejected){throw 'Escape accepted'}"
        )

    def test_inventory_detects_same_size_drift_and_empty_dirs(self):
        (self.root / "empty").mkdir()
        (self.root / "data").write_bytes(b"abc")
        self.ps(
            "$a=Get-RetentionInventory $fixture; [IO.File]::WriteAllText((Join-Path $fixture 'data'),'def'); $b=Get-RetentionInventory $fixture; if($a.files[0].sha256 -eq $b.files[0].sha256 -or $a.directories -notcontains 'empty'){throw 'Inventory failed'}"
        )

    def test_unreadable_native_process_blocks(self):
        self.ps(
            "function Get-CimInstance { [pscustomobject]@{Name='UnrealEditor.exe';ProcessId=42;CommandLine=$null} }; $blocked=$false; try {Assert-RetentionProcesses $fixture} catch {$blocked=$true}; if(-not $blocked){throw 'Unreadable process accepted'}"
        )

    def test_protected_main_and_matching_tag_head(self):
        (self.root / ".git").mkdir()
        self.ps(
            "function Invoke-RetentionGit {param($Path,$Arguments) if($Arguments[0] -eq 'rev-parse' -and $Arguments[1] -eq '--abbrev-ref') {return 'main'}; return ('a'*40)}; $blocked=$false; try {Assert-RetentionGitProtection $fixture $fixture} catch {$blocked=$true}; if(-not $blocked){throw 'Main accepted'}; function Invoke-RetentionGit {param($Path,$Arguments) if($Arguments[0] -eq 'rev-parse' -and $Arguments[1] -eq '--abbrev-ref') {return 'HEAD'}; return ('a'*40)}; $blocked=$false; try {Assert-RetentionGitProtection $fixture $fixture} catch {$blocked=$true}; if(-not $blocked){throw 'Protected head accepted'}"
        )

    def test_shared_or_nested_linked_git_metadata_refused(self):
        nested = self.root / "plugin"
        nested.mkdir()
        (nested / ".git").write_text("gitdir: elsewhere")
        self.ps(
            "$blocked=$false; try {Get-RetentionInventory $fixture} catch {$blocked=$true}; if(-not $blocked){throw 'Nested linked git accepted'}"
        )
        (nested / ".git").unlink()
        shared = nested / ".git/worktrees/linked"
        shared.mkdir(parents=True)
        self.ps(
            "$blocked=$false; try {Get-RetentionInventory $fixture} catch {$blocked=$true}; if(-not $blocked){throw 'Common git owner accepted'}"
        )

    @unittest.skipUnless(os.name == "nt", "Current-job retention is Windows-only")
    def test_current_run_only_retains_all_bytes(self):
        run = "123-2"
        work = self.root / "runner/_work"
        repo = work / "YetAnotherCyclingSim/YetAnotherCyclingSim"
        specs = [work / "s384" / run, work / "b384" / (run + "-session-project")]
        specs += [
            repo / (prefix + run)
            for prefix in (
                "_official-mcp-source-probe-",
                "_road-material-source-proof-",
                "_road-material-native-",
                "rm-",
            )
        ]
        for item in specs:
            item.mkdir(parents=True)
            (item / "payload").write_bytes(b"retained-original")
        unrelated = repo / "rm-999-1"
        unrelated.mkdir()
        (unrelated / "payload").write_bytes(b"unrelated")
        config = self.root / "workspace.json"
        config.write_text(json.dumps({"schema_version": 1, "runner": "runner"}))
        self.ps(
            "function Get-CimInstance { @() }; $env:GITHUB_ACTIONS='true'; $env:GITHUB_RUN_ID='123'; $env:GITHUB_RUN_ATTEMPT='2'; Invoke-YacsCurrentJobRetention (Join-Path $fixture 'workspace.json')"
        )
        self.assertTrue(unrelated.is_dir())
        self.assertTrue(all(not item.exists() for item in specs))
        receipt = json.loads(
            (
                self.root / "work/runner-retention" / run / "retention-receipt.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(receipt["bytes_deleted"], 0)
        self.assertEqual(receipt["status"], "COMPLETED_NO_BYTES_DELETED")
        self.assertEqual(len(receipt["entries"]), 6)
        for entry in receipt["entries"]:
            self.assertEqual(entry["inventory"], entry["after_inventory"])
            self.assertEqual(
                (Path(entry["destination"]) / "payload").read_bytes(),
                b"retained-original",
            )


if __name__ == "__main__":
    unittest.main()
