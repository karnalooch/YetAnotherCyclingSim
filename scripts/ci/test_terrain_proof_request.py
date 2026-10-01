from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/terrain_proof_request.py"
SPEC = importlib.util.spec_from_file_location("terrain_proof_request", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TerrainProofRequestTests(unittest.TestCase):
    def environment(self, event: str = "workflow_dispatch") -> dict[str, str]:
        return {
            "GITHUB_REPOSITORY": MODULE.REPOSITORY,
            "GITHUB_EVENT_NAME": event,
            "GITHUB_SHA": "a" * 40,
            "YACS_REQUESTED_SHA": "b" * 40,
            "YACS_REQUEST_ID": "gumball-m3-terrain-292-" + "b" * 40,
        }

    def test_push_never_admits_heavy_work_even_with_request_fields(self) -> None:
        result = MODULE.resolve_request(self.environment("push"))
        self.assertFalse(result.execute_proof)
        self.assertEqual(result.source_sha, "a" * 40)
        self.assertEqual(result.request_id, "")

    def test_explicit_request_uses_target_not_workflow_definition_sha(self) -> None:
        result = MODULE.resolve_request(self.environment())
        self.assertTrue(result.execute_proof)
        self.assertEqual(result.source_sha, "b" * 40)

    def test_fork_is_rejected_for_both_supported_events(self) -> None:
        for event in ("push", "workflow_dispatch"):
            with self.subTest(event=event):
                env = self.environment(event)
                env["GITHUB_REPOSITORY"] = "other/YetAnotherCyclingSim"
                with self.assertRaisesRegex(ValueError, "canonical"):
                    MODULE.resolve_request(env)

    def test_pr_and_comment_events_cannot_admit_target_execution(self) -> None:
        for event in (
            "pull_request",
            "pull_request_target",
            "issue_comment",
            "",
            "schedule",
        ):
            with (
                self.subTest(event=event),
                self.assertRaisesRegex(ValueError, "unsupported"),
            ):
                MODULE.resolve_request(self.environment(event))

    def test_bad_target_shas_fail_closed(self) -> None:
        for sha in (
            "",
            "main",
            "b" * 39,
            "b" * 41,
            "B" * 40,
            "z" * 40,
            "b" * 40 + "\n",
            "$(exit 0)",
        ):
            with self.subTest(sha=sha):
                env = self.environment()
                env["YACS_REQUESTED_SHA"] = sha
                with self.assertRaisesRegex(ValueError, "exact_sha"):
                    MODULE.resolve_request(env)

    def test_malformed_platform_sha_is_rejected(self) -> None:
        for event in ("push", "workflow_dispatch"):
            env = self.environment(event)
            env["GITHUB_SHA"] = "main"
            with self.assertRaisesRegex(ValueError, "workflow SHA"):
                MODULE.resolve_request(env)

    def test_bad_request_ids_cannot_inject_outputs_or_paths(self) -> None:
        for request_id in (
            "",
            "../target",
            "x\nexecute_proof=true",
            "x\rsource_sha=bad",
            "$(id)",
            "a" * 201,
        ):
            with self.subTest(request_id=request_id):
                env = self.environment()
                env["YACS_REQUEST_ID"] = request_id
                with self.assertRaisesRegex(ValueError, "request_id"):
                    MODULE.resolve_request(env)

    def test_cli_outputs_validated_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--github-output", str(output)],
                env={**os.environ, **self.environment()},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("source_sha=" + "b" * 40 + "\n", output.read_text())
            self.assertIn("execute_proof=true\n", output.read_text())

    def test_cli_failure_does_not_publish_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            env = self.environment()
            env["YACS_REQUESTED_SHA"] = "main"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--github-output", str(output)],
                env={**os.environ, **env},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
