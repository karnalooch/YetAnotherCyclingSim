from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "yacs-editor-command.yml"
WRAPPER = ROOT / "scripts" / "ue" / "Invoke-YacsRemoteEditorCommand.ps1"
SMOKE = ROOT / "scripts" / "ue" / "remote_editor_smoke.py"


class RemoteEditorCommandContractTests(unittest.TestCase):
    def test_workflow_is_owner_only_and_issue_228_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("issue_comment:", text)
        self.assertIn("github.event.issue.number == 228", text)
        self.assertIn("github.event.comment.user.login == github.repository_owner", text)
        self.assertIn("github.event.comment.body == '/yacs-editor smoke-cube'", text)
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("${{ github.event.comment.body }}", text)

    def test_branch_canary_is_narrow(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("feat/85-remote-editor-command-bridge", text)
        self.assertIn("github.actor == github.repository_owner", text)
        self.assertNotIn("pull_request_target", text)

    def test_wrapper_accepts_only_named_command(self) -> None:
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("[ValidateSet('smoke-cube')]", text)
        self.assertIn("-ExecutePythonScript=$SmokeScript", text)
        self.assertNotIn("Invoke-Expression", text)
        self.assertNotIn("github.event.comment.body", text)

    def test_smoke_actor_is_transient_and_removed(self) -> None:
        text = SMOKE.read_text(encoding="utf-8")
        self.assertIn("transient=True", text)
        self.assertIn("destroy_actor(actor)", text)
        self.assertIn('"map_saved": False', text)
        self.assertIn('"persistent_asset_created": False', text)
        self.assertNotIn("save_level", text.lower())
        self.assertNotIn("save_asset", text.lower())


if __name__ == "__main__":
    unittest.main()
