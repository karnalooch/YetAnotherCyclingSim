from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "manual-unreal.yml",
    ROOT / ".github" / "workflows" / "asset-full.yml",
    ROOT / ".github" / "workflows" / "reusable-unreal.yml",
)


class SelfHostedGitIsolationTests(unittest.TestCase):
    def test_every_self_hosted_unreal_workflow_isolates_global_git_config(self):
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
                self.assertNotIn("${{ runner.temp }}", text)
                self.assertIn("Isolate self-hosted Git configuration", text)
                self.assertIn(
                    "$isolated = Join-Path $env:RUNNER_TEMP 'yacs-global.gitconfig'",
                    text,
                )
                self.assertIn(
                    "Set-Content -LiteralPath $isolated -Value '' -Encoding ascii",
                    text,
                )
                self.assertIn("$env:GIT_CONFIG_GLOBAL = $isolated", text)
                self.assertIn("$env:GIT_CONFIG_NOSYSTEM = '1'", text)
                self.assertIn(
                    '"GIT_CONFIG_GLOBAL=$isolated" >> $env:GITHUB_ENV',
                    text,
                )
                self.assertIn('"GIT_CONFIG_NOSYSTEM=1" >> $env:GITHUB_ENV', text)
                self.assertIn("git config --global --list --show-origin", text)


if __name__ == "__main__":
    unittest.main()
