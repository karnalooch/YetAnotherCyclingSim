from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required")
class BuildIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "ci" / "Project.uproject"

    def check(self, command, succeeds):
        script = Path(__file__).with_name("Assert-YacsBuildIsolation.ps1")
        code = f"$ErrorActionPreference='Stop'; . '{script}'; Assert-YacsBuildIsolation -ProjectPath '{self.project}' -EditorProcesses @([pscustomobject]@{{CommandLine='{command}'}})"
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", code], capture_output=True, text=True
        )
        self.assertEqual(result.returncode == 0, succeeds, result.stderr)

    def test_same_checkout_is_rejected(self):
        self.check(f'editor.exe "{self.project}"', False)

    def test_separate_authoring_checkout_is_allowed(self):
        self.check(f'editor.exe "{self.root / "authoring" / "Project.uproject"}"', True)

    def test_unknown_project_is_rejected(self):
        self.check("editor.exe", False)

    def test_auto_discovery_filters_stale_cim_records_by_native_pid(self):
        script = (
            Path(__file__)
            .with_name("Assert-YacsBuildIsolation.ps1")
            .read_text(encoding="utf-8")
        )
        self.assertIn("$AutoDiscovered", script)
        self.assertIn("Get-Process -Id ([int]$_.ProcessId)", script)
        self.assertIn("'UnrealEditor-Cmd'", script)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction_alias_of_open_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "project"
            target.mkdir()
            alias = root / "old-project"
            project = target / "Project.uproject"
            project.write_text("{}")
            script = Path(__file__).with_name("Assert-YacsBuildIsolation.ps1")
            code = f"""
$ErrorActionPreference = 'Stop'
New-Item -ItemType Junction -Path '{alias}' -Target '{target}' | Out-Null
. '{script}'
try {{
    Assert-YacsBuildIsolation -ProjectPath '{project}' -EditorProcesses @([pscustomobject]@{{CommandLine='editor.exe "{alias / "Project.uproject"}"'}})
    exit 2
}} catch {{
    if ($_.Exception.Message -notlike 'Close the editor*') {{ throw }}
    exit 0
}}
"""
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-Command", code], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
