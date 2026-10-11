"""Reject workspace configurations that could target a different project."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.manage_local_workspace import load_workspace

RUNNER = Path(__file__).resolve().parent / "runner/Start-YacsRunner.ps1"


class WorkspaceConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "workspace.json"
        self.config = {
            "schema_version": 1,
            **{key: key for key in ("project", "data", "cache", "checkpoints", "work")},
        }

    def load(self):
        self.path.write_text(json.dumps(self.config))
        return load_workspace(self.path)

    def test_relative_paths_resolve_from_config_not_current_directory(self):
        result = self.load()
        self.assertEqual(Path(result["project"]), self.path.parent / "project")

    def test_parent_traversal_is_rejected(self):
        self.config["data"] = "../runner"
        with self.assertRaisesRegex(ValueError, "below its root"):
            self.load()

    def test_absolute_workspace_path_is_rejected(self):
        self.config["project"] = str(self.path.parent)
        with self.assertRaisesRegex(ValueError, "below its root"):
            self.load()

    def test_unknown_schema_is_rejected(self):
        self.config["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema"):
            self.load()

    def runner_cache_result(self):
        self.path.write_text(json.dumps(self.config))
        harness = self.path.parent / "resolve-runner-cache.ps1"
        harness.write_text(
            r"""param([string]$Launcher, [string]$ConfigPath)
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $Launcher, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$functions = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Resolve-YacsRunnerZenDataPath'
}, $false))
if ($functions.Count -ne 1) { throw 'Expected one runner cache resolver.' }
. ([scriptblock]::Create($functions[0].Extent.Text))
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$resolved = Resolve-YacsRunnerZenDataPath -WorkspaceRoot (
    Split-Path -Parent $ConfigPath) -Config $config
$resolved | ConvertTo-Json -Compress
""",
            encoding="utf-8",
        )
        return subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(harness),
                str(RUNNER),
                str(self.path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
    def test_runner_and_editor_share_configured_cache_without_creating_it(self):
        for relative in ("cache", "shared/cache with spaces", "."):
            with self.subTest(cache=relative):
                self.config["cache"] = relative
                expected = Path(self.load()["cache"]) / "Zen"
                result = self.runner_cache_result()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(Path(json.loads(result.stdout)), expected)
                self.assertFalse(expected.exists())

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
    def test_runner_rejects_absolute_and_parent_cache_paths(self):
        for relative in ("../outside", "cache/../../outside", str(self.path.parent)):
            with self.subTest(cache=relative):
                self.config["cache"] = relative
                result = self.runner_cache_result()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("below the workspace root", result.stderr)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
    def test_runner_rejects_non_string_cache_path(self):
        self.config["cache"] = ["cache"]
        result = self.runner_cache_result()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cache path must be a string", result.stderr)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
    def test_runner_rejects_cache_link_escape_before_creating_cache(self):
        with tempfile.TemporaryDirectory() as outside:
            link = self.path.parent / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlink creation is unavailable: {error}")
            self.config["cache"] = "linked/cache"
            with self.assertRaisesRegex(ValueError, "escapes through a link"):
                self.load()
            result = self.runner_cache_result()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cannot traverse a link or junction", result.stderr)
            self.assertFalse((Path(outside) / "cache").exists())


if __name__ == "__main__":
    unittest.main()
