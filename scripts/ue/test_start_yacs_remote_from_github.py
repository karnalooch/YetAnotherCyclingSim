"""Run the operator launcher against a fake gh boundary, without network writes."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("Start-YacsRemoteFromGitHub.ps1")
RUNNER = r"""
param([string]$Launcher, [string]$Scenario)
$ErrorActionPreference = 'Stop'
$global:YacsLauncherFixture = @{
    Calls = [Collections.Generic.List[object]]::new()
    RefReads = 0
    Head = 'a' * 40
    Tree = 'b' * 40
    Checkpoint = 'c' * 40
    Scenario = $Scenario
}
function gh {
    $arguments = @($args)
    $body = ($input | Out-String).Trim()
    $method = 'GET'
    if ($arguments -contains '--method') { $method = $arguments[[Array]::IndexOf($arguments, '--method') + 1] }
    $endpoint = @($arguments | Where-Object { $_ -eq 'user' -or $_ -like 'repos/*' })[0]
    $global:YacsLauncherFixture.Calls.Add(@{method=$method; endpoint=$endpoint; body=$body})
    $global:LASTEXITCODE = 0
    $response = switch -Wildcard ($endpoint) {
        'user' { @{login=$(if ($global:YacsLauncherFixture.Scenario -eq 'wrong-owner') {'other'} else {'karnalooch'})}; break }
        '*/pulls/470' { @{state='open';head=@{sha=$global:YacsLauncherFixture.head;ref='codex/364-road-surface-materials';repo=@{full_name='karnalooch/YetAnotherCyclingSim'}}}; break }
        '*/actions/workflows/*' { @{state='active';path='.github/workflows/level-editor-review.yml'}; break }
        '*/git/commits/*' { @{sha=$global:YacsLauncherFixture.head;tree=@{sha=$global:YacsLauncherFixture.tree}}; break }
        '*/git/ref/heads/*' {
            $global:YacsLauncherFixture.RefReads++
            @{object=@{sha=$(if ($global:YacsLauncherFixture.Scenario -eq 'branch-race' -and $global:YacsLauncherFixture.RefReads -eq 2) {'d'*40} else {$global:YacsLauncherFixture.head})}}
            break
        }
        '*/git/commits' {
            if ($global:YacsLauncherFixture.Scenario -eq 'uncertain-create') { $global:LASTEXITCODE=1; return }
            @{sha=$global:YacsLauncherFixture.checkpoint;tree=@{sha=$(if ($global:YacsLauncherFixture.Scenario -eq 'wrong-tree') {'e'*40} else {$global:YacsLauncherFixture.tree})};parents=@(@{sha=$global:YacsLauncherFixture.head})}
            break
        }
        '*/git/refs/heads/*' {
            if ($global:YacsLauncherFixture.Scenario -eq 'update-rejected') { $global:LASTEXITCODE=1; return }
            @{object=@{sha=$global:YacsLauncherFixture.checkpoint}}; break
        }
        default { throw "Unexpected endpoint $endpoint" }
    }
    $response | ConvertTo-Json -Depth 10 -Compress
}
$errorText = $null
try {
    if ($Scenario -eq 'check-only') { & $Launcher -CheckOnly 6>$null }
    else { & $Launcher 6>$null }
}
catch { $errorText = $_.Exception.Message }
@{calls=@($global:YacsLauncherFixture.Calls);error=$errorText} | ConvertTo-Json -Depth 12 -Compress
"""


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required")
class RemoteLauncherTests(unittest.TestCase):
    def run_scenario(self, scenario):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Path(temporary) / "fake-gh.ps1"
            runner.write_text(RUNNER, encoding="utf-8")
            result = subprocess.run(
                [
                    shutil.which("pwsh"),
                    "-NoProfile",
                    "-NonInteractive",
                    "-File",
                    str(runner),
                    str(SCRIPT),
                    scenario,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def writes(self, result):
        return [call for call in result["calls"] if call["method"] != "GET"]

    def test_check_only_never_writes(self):
        result = self.run_scenario("check-only")
        self.assertIsNone(result["error"])
        self.assertEqual(self.writes(result), [])

    def test_wrong_owner_cannot_create_checkpoint(self):
        result = self.run_scenario("wrong-owner")
        self.assertIn("repository owner", result["error"])
        self.assertEqual(self.writes(result), [])

    def test_branch_race_leaves_checkpoint_unattached(self):
        result = self.run_scenario("branch-race")
        self.assertIn("remains unattached", result["error"])
        self.assertEqual([call["method"] for call in self.writes(result)], ["POST"])

    def test_wrong_created_tree_prevents_branch_update(self):
        result = self.run_scenario("wrong-tree")
        self.assertIn("tree/parent", result["error"])
        self.assertEqual([call["method"] for call in self.writes(result)], ["POST"])

    def test_uncertain_create_is_not_retried(self):
        result = self.run_scenario("uncertain-create")
        self.assertIn("uncertain", result["error"])
        self.assertEqual([call["method"] for call in self.writes(result)], ["POST"])

    def test_rejected_ref_update_is_not_retried_or_forced(self):
        result = self.run_scenario("update-rejected")
        self.assertIn("uncertain", result["error"])
        writes = self.writes(result)
        self.assertEqual([call["method"] for call in writes], ["POST", "PATCH"])
        self.assertIs(json.loads(writes[-1]["body"])["force"], False)

    def test_success_preserves_tree_and_parent(self):
        result = self.run_scenario("success")
        self.assertIsNone(result["error"])
        writes = self.writes(result)
        self.assertEqual([call["method"] for call in writes], ["POST", "PATCH"])
        create = json.loads(writes[0]["body"])
        self.assertEqual(create["tree"], "b" * 40)
        self.assertEqual(create["parents"], ["a" * 40])
        self.assertEqual(
            json.loads(writes[1]["body"]), {"sha": "c" * 40, "force": False}
        )


if __name__ == "__main__":
    unittest.main()
