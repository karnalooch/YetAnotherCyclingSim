from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "manual-unreal.yml",
    ROOT / ".github" / "workflows" / "asset-full.yml",
    ROOT / ".github" / "workflows" / "reusable-unreal.yml",
)
PERSISTENT_CODE_ONLY_WORKFLOWS = (ROOT / ".github" / "workflows" / "manual-unreal.yml",)
ISOLATED_CODE_ONLY_WORKFLOWS = (ROOT / ".github" / "workflows" / "reusable-unreal.yml",)


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

    def test_persistent_code_only_workflows_normalize_lfs_before_checkout(self):
        for path in PERSISTENT_CODE_ONLY_WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                normalize = text.index(
                    "Normalize stale LFS payloads before code-only checkout"
                )
                self.assertIn("git lfs ls-files --name-only", text)
                self.assertIn("Remove-Item -LiteralPath $path -Force", text)
                self.assertIn("lfs: false", text)
                checkout = text.index("without LFS payloads")
                self.assertLess(normalize, checkout)

    def test_reusable_code_only_workflows_use_isolated_worktree(self):
        for path in ISOLATED_CODE_ONLY_WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertIn(
                    "YACS_UNREAL_WORKTREE: _unreal-worktree-${{ github.run_id }}-${{ github.run_attempt }}",
                    text,
                )
                self.assertIn("path: ${{ env.YACS_UNREAL_WORKTREE }}", text)
                self.assertIn(
                    "working-directory: ${{ env.YACS_UNREAL_WORKTREE }}", text
                )
                self.assertIn("lfs: false", text)
                self.assertIn("clean: true", text)
                self.assertNotIn(
                    "Normalize stale LFS payloads before code-only checkout",
                    text,
                )


if __name__ == "__main__":
    unittest.main()
