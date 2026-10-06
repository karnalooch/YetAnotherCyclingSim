"""Static tests for the pinned Blender headless execution contract."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts.blender import run_headless


class BlenderHeadlessContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.repo = self.workspace / "project"
        self.repo.mkdir()
        self.script = self.repo / "job.py"
        self.script.write_text("print('ok')\n", encoding="utf-8")
        self.executable = (
            self.workspace
            / "tools"
            / "blender-4.5.9-windows-x64"
            / "blender.exe"
        )
        self.executable.parent.mkdir(parents=True)
        self.executable.write_bytes(b"fake")
        self.contract = {
            "schema_version": 1,
            "version": "4.5.9",
            "workspace_executable": "tools/blender-4.5.9-windows-x64/blender.exe",
            "python_exit_code": 20,
        }

    def test_resolves_canonical_workspace_executable(self):
        resolved = run_headless.resolve_blender_executable(
            self.workspace,
            self.contract,
        )
        self.assertEqual(resolved, self.executable.resolve())

    def test_rejects_executable_outside_workspace(self):
        outside = self.root / "outside.exe"
        outside.write_bytes(b"fake")
        with self.assertRaisesRegex(ValueError, "workspace root"):
            run_headless.resolve_blender_executable(
                self.workspace,
                self.contract,
                outside,
            )

    def test_requires_exact_blender_version(self):
        completed = subprocess.CompletedProcess(
            [str(self.executable), "--version"],
            0,
            stdout="Blender 4.5.8\n",
            stderr="",
        )
        with mock.patch.object(
            run_headless.subprocess,
            "run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(RuntimeError, "expected 4.5.9"):
                run_headless.require_exact_version(self.executable, "4.5.9")

    def test_command_is_headless_and_preserves_script_argument_boundary(self):
        command = run_headless.build_command(
            self.executable,
            self.script,
            python_exit_code=20,
            job_args=["--report", "proof.json", "--value", "42"],
        )
        self.assertIn("--background", command)
        self.assertIn("--factory-startup", command)
        self.assertIn("--disable-autoexec", command)
        self.assertEqual(
            command[command.index("--python-exit-code") + 1],
            "20",
        )
        boundary = command.index("--")
        self.assertEqual(
            command[boundary + 1 :],
            ["--report", "proof.json", "--value", "42"],
        )
        self.assertLess(command.index("--python"), boundary)

    def test_repo_script_must_stay_in_repo(self):
        outside = self.workspace / "outside.py"
        outside.write_text("print('no')\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "repository-owned"):
            run_headless.resolve_repo_script(outside, repo_root=self.repo)

    def test_atomic_receipt_round_trip(self):
        receipt = self.workspace / "work" / "blender" / "receipt.json"
        payload = {"schema_version": 1, "status": "PASS"}
        run_headless.write_json_atomic(receipt, payload)
        self.assertEqual(
            json.loads(receipt.read_text(encoding="utf-8")),
            payload,
        )
        self.assertFalse(receipt.with_name("receipt.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
