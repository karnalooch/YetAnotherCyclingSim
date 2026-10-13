"""Real Git conservation fixtures and host-boundary tests; no live host writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.runner import maintain_git_packs as m


class PackMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "_blender-mf-reference"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "gc.auto", "0")
        self.guards = 0

    def git(self, *args, data=None):
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args], input=data, stderr=subprocess.PIPE
        )

    def guard(self):
        self.guards += 1

    def maintain(self, root, guard):
        return m.maintain_target(root, guard, journal=self.root / "journal")

    def packs(self):
        for i in range(8):
            (self.repo / "file.txt").write_text(f"revision {i}\n")
            self.git("add", "file.txt")
            self.git("commit", "-qm", f"fixture {i}")
            self.git("repack")

    def test_repack_preserves_unreachable_objects_refs_and_worktree(self):
        self.packs()
        orphan = self.git(
            "hash-object", "-w", "--stdin", data=b"unreachable evidence\n"
        ).strip()
        (self.repo / "evidence.json").write_text('{"retain":true}')
        (self.repo / "file.txt").write_text("unsaved local changes\n")
        before = m.object_inventory(self.repo)
        result = self.maintain(self.repo, self.guard)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["packs_before"], 8)
        self.assertEqual(result["packs_after"], 1)
        self.assertEqual(before, m.object_inventory(self.repo))
        self.assertEqual(
            self.git("cat-file", "-p", orphan.decode()), b"unreachable evidence\n"
        )
        self.assertEqual(
            (self.repo / "file.txt").read_text(), "unsaved local changes\n"
        )
        self.assertTrue((self.repo / "evidence.json").exists())
        self.assertEqual(self.guards, 2)
        self.assertEqual(
            self.maintain(self.repo, self.guard)["status"], "BELOW_THRESHOLD"
        )

    def test_no_work_when_below_threshold_or_absent(self):
        self.assertEqual(
            self.maintain(self.repo, self.guard)["status"], "BELOW_THRESHOLD"
        )
        self.assertEqual(
            self.maintain(self.root / "missing", self.guard)["status"], "ABSENT"
        )
        self.assertEqual(self.guards, 0)

    def test_already_packed_unreachable_object_is_retained(self):
        self.packs()
        orphan = self.git(
            "hash-object", "-w", "--stdin", data=b"packed orphan\n"
        ).strip()
        self.git("pack-objects", ".git/objects/pack/pack", data=orphan + b"\n")
        self.git("prune-packed")  # Fixture only: orphan now exists solely in a pack.
        oid = orphan.decode()
        self.assertFalse((self.repo / ".git/objects" / oid[:2] / oid[2:]).exists())
        result = self.maintain(self.repo, self.guard)
        self.assertEqual(result["packs_before"], 9)
        self.assertEqual(result["packs_after"], 1)
        self.assertEqual(self.git("cat-file", "-p", oid), b"packed orphan\n")

    def test_failed_verification_latches_even_below_threshold(self):
        self.packs()
        before = m.object_inventory(self.repo)
        with patch.object(m, "object_inventory", side_effect=[before, b"mismatch"]):
            with self.assertRaisesRegex(RuntimeError, "conservation failed"):
                self.maintain(self.repo, self.guard)
        self.assertEqual(len(list((self.repo / ".git/objects/pack").glob("*.pack"))), 1)
        pending = self.root / "journal/PENDING.json"
        proof = json.loads(pending.read_text())
        self.assertEqual(Path(proof["inventory"]).read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "previous mutation"):
            self.maintain(self.repo, self.guard)
        self.assertTrue(pending.exists())

    def test_busy_maintenance_is_deferred_without_mutation(self):
        self.packs()
        for checkpoint in (1, 2):
            self.guards = 0

            def busy():
                self.guards += 1
                if self.guards == checkpoint:
                    raise m.MaintenanceBusy("another Git process")

            result = self.maintain(self.repo, busy)
            self.assertEqual(result["status"], "DEFERRED_BUSY")
            self.assertEqual(
                len(list((self.repo / ".git/objects/pack").glob("*.pack"))), 8
            )
            self.assertFalse((self.root / "journal/PENDING.json").exists())

    def test_shared_storage_rejected(self):
        path = self.repo / ".git/objects/info/alternates"
        path.write_text(str(self.root))
        with self.assertRaisesRegex(ValueError, "Shared Git"):
            self.maintain(self.repo, self.guard)

    def test_lock_and_partial_store_rejected(self):
        for name in (
            "index.lock",
            "objects/pack/fixture.promisor",
            "objects/pack/fixture.keep",
        ):
            path = self.repo / ".git" / name
            path.touch()
            with self.assertRaisesRegex(ValueError, "Locked, kept or partial"):
                self.maintain(self.repo, self.guard)
            path.unlink()

    def test_linked_worktree_refused(self):
        other = self.root / "linked"
        other.mkdir()
        (other / ".git").write_text("gitdir: ../_blender-mf-reference/.git")
        with self.assertRaisesRegex(ValueError, "Independent"):
            self.maintain(other, self.guard)

    def test_low_reserve_stops_before_repack(self):
        self.packs()
        before = m.object_inventory(self.repo)
        with patch.object(
            m.shutil, "disk_usage", return_value=type("Disk", (), {"free": 4 * m.GIB})()
        ):
            with self.assertRaisesRegex(ValueError, "reserve"):
                self.maintain(self.repo, self.guard)
        self.assertEqual(before, m.object_inventory(self.repo))
        self.assertEqual(len(list((self.repo / ".git/objects/pack").glob("*.pack"))), 8)

    def test_busy_guard_prevents_mutation(self):
        self.packs()

        def busy():
            raise ValueError("busy")

        with self.assertRaisesRegex(ValueError, "busy"):
            self.maintain(self.repo, busy)
        self.assertEqual(len(list((self.repo / ".git/objects/pack").glob("*.pack"))), 8)

    def test_second_guard_rechecks_racing_process(self):
        self.packs()

        def changed():
            self.guards += 1
            if self.guards == 2:
                raise ValueError("new process")

        with self.assertRaisesRegex(ValueError, "new process"):
            self.maintain(self.repo, changed)
        self.assertEqual(len(list((self.repo / ".git/objects/pack").glob("*.pack"))), 8)

    def test_exclusive_lock_never_removes_foreign_lock(self):
        lock = self.root / "maintenance.lock"
        with m.exclusive_lock(lock):
            with self.assertRaises(FileExistsError):
                with m.exclusive_lock(lock):
                    self.fail("foreign lock acquired")
            self.assertTrue(lock.exists())
        self.assertFalse(lock.exists())

    def test_timeout_is_failure(self):
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            m.command([sys.executable, "-c", "import time;time.sleep(30)"], timeout=1)

    def test_configuration_rejects_traversal(self):
        cfg = self.root / "workspace.json"
        for runner in ("../runner", "other", str(self.root), None):
            cfg.write_text(json.dumps({"schema_version": 1, "runner": runner}))
            with self.assertRaises(ValueError):
                m.workspace_paths(cfg)


class ProcessOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.runner = Path("/fixture/runner")
        self.target = Path("/fixture/runner/_work/_blender-mf-reference")
        self.processes = [
            {"ProcessId": 1, "ParentProcessId": 2, "Name": "python.exe"},
            {"ProcessId": 2, "ParentProcessId": 3, "Name": "pwsh.exe"},
            {
                "ProcessId": 3,
                "ParentProcessId": 4,
                "Name": "Runner.Worker.exe",
                "ExecutablePath": str(self.runner / "bin/Runner.Worker.exe"),
            },
            {
                "ProcessId": 5,
                "ParentProcessId": 6,
                "Name": "UnrealEditor.exe",
                "CommandLine": "editor /unrelated/live/project",
            },
        ]

    def check(self):
        m.assert_processes(self.processes, 1, self.runner, [self.target])

    def test_unrelated_open_editor_allowed(self):
        self.check()

    def test_foreign_worker_rejected(self):
        self.processes.append(
            {"ProcessId": 10, "ParentProcessId": 11, "Name": "Runner.Worker.exe"}
        )
        with self.assertRaisesRegex(ValueError, "ancestor Worker"):
            self.check()

    def test_wrong_worker_path_rejected(self):
        self.processes[2]["ExecutablePath"] = "/foreign/Runner.Worker.exe"
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_ancestry_rejected(self):
        self.processes[0]["ParentProcessId"] = 999
        with self.assertRaisesRegex(ValueError, "ancestry"):
            self.check()

    def test_active_git_rejected(self):
        self.processes.append({"ProcessId": 9, "ParentProcessId": 6, "Name": "git.exe"})
        with self.assertRaisesRegex(ValueError, "Git process"):
            self.check()

    def test_noop_checks_worker_but_ignores_unrelated_git(self):
        self.processes.append({"ProcessId": 9, "ParentProcessId": 6, "Name": "git.exe"})
        m.assert_processes(self.processes, 1, self.runner, [])
        self.processes[2]["ExecutablePath"] = "/foreign/Runner.Worker.exe"
        with self.assertRaisesRegex(ValueError, "ancestor Worker"):
            m.assert_processes(self.processes, 1, self.runner, [])

    def test_editor_using_target_rejected(self):
        self.processes[3]["CommandLine"] = f"editor {self.target}/scene.uproject"
        with self.assertRaisesRegex(ValueError, "active process"):
            self.check()

    def test_unreadable_editor_rejected(self):
        self.processes[3]["CommandLine"] = None
        with self.assertRaisesRegex(ValueError, "Unreadable"):
            self.check()


@unittest.skipUnless(
    shutil.which("pwsh"), "PowerShell 7 required for installer fixtures"
)
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "runner").mkdir()
        self.config = self.root / "workspace.json"
        self.config.write_text('{"schema_version":1,"runner":"runner"}')
        self.env = self.root / "runner/.env"
        self.original = (
            "OTHER_SETTING=retain\r\nACTIONS_RUNNER_HOOK_JOB_STARTED=old-hook.ps1\r\n"
            "ACTIONS_RUNNER_HOOK_JOB_COMPLETED=keep-completion.ps1\r\n"
        )
        self.env.write_bytes(self.original.encode())
        self.installer = Path(__file__).with_name("Install-YacsGitPackMaintenance.ps1")

    def install(self, *, apply=False, busy=False):
        # Stub process enumeration only in this fixture subprocess. All writes
        # remain under its temporary workspace; no real runner state is changed.
        body = "[pscustomobject]@{Id=999}" if busy else ""
        script = (
            f"function Get-Process {{ {body} }}; & '{str(self.installer).replace(chr(39), chr(39) * 2)}' "
            f"-WorkspaceConfig '{str(self.config).replace(chr(39), chr(39) * 2)}'"
        )
        if apply:
            script += " -Apply"
        return subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_preview_no_write_and_apply_preserves_completion_and_hashes(self):
        preview = self.install()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.env.read_bytes(), self.original.encode())
        self.assertFalse((self.root / "tools").exists())
        result = self.install(apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        updated = self.env.read_bytes().decode()
        self.assertEqual(
            updated.replace(
                "ACTIONS_RUNNER_HOOK_JOB_STARTED=" + receipt["entrypoint"],
                "ACTIONS_RUNNER_HOOK_JOB_STARTED=old-hook.ps1",
            ),
            self.original,
        )
        self.assertEqual(self.install(apply=True).returncode, 0)
        (Path(receipt["bundle"]) / "maintain_git_packs.py").write_text("tampered")
        refusal = self.install(apply=True)
        self.assertNotEqual(refusal.returncode, 0)
        self.assertIn("bundle drift", refusal.stderr)

    def test_active_runner_prevents_installation(self):
        result = self.install(apply=True, busy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.env.read_bytes(), self.original.encode())
        self.assertFalse((self.root / "tools").exists())


if __name__ == "__main__":
    unittest.main()
