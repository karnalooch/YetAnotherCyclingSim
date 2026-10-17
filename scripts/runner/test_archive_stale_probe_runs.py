"""Offline safety regressions; no real runner paths or processes are mutated."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "cleanup", Path(__file__).with_name("archive_stale_probe_runs.py")
)
cleanup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cleanup)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=Path(__file__).parent, prefix="cleanup-test-"
        )
        self.addCleanup(self.cleanup_temp)
        base = Path(self.temp.name).resolve()
        self.root = base / "work"
        self.root.mkdir()
        self.archive = base / "archives"
        self.archive.mkdir()
        self.target = self.root / "s384/123-1"
        self.target.mkdir(parents=True)
        (self.target / "evidence.json").write_text("nonreproducible evidence")
        (self.target / "empty").mkdir()
        canonical = self.root / cleanup.REPO
        canonical.mkdir(parents=True)
        self.make_git(canonical, "main", "canonical")
        subprocess.run(
            ["git", "-C", str(canonical), "tag", "v0.3.1"],
            check=True,
            capture_output=True,
        )
        old = time.time() - 172800
        for p in [*self.target.rglob("*"), self.target]:
            os.utime(p, (old, old))

    def cleanup_temp(self):
        # Windows may briefly retain Git process handles after subprocess exit.
        for attempt in range(20):
            try:
                self.temp.cleanup()
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)

    def make_git(self, path, branch, message):
        def git(*args):
            return subprocess.run(
                [
                    "git",
                    "-C",
                    str(path),
                    "-c",
                    "maintenance.auto=false",
                    "-c",
                    "gc.auto=0",
                    *args,
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

        git("init", "-b", branch)
        (path / "fixture.txt").write_text(message)
        git("add", "fixture.txt")
        git(
            "-c",
            "user.name=Cleanup Test",
            "-c",
            "user.email=cleanup@example.invalid",
            "commit",
            "-m",
            message,
        )
        return git("rev-parse", "HEAD")

    def plan(self):
        return cleanup.preview(self.root)

    def apply(self, plan, idle=lambda: None):
        return cleanup.quarantine(plan, self.archive, idle, self.root)

    def test_unknown_and_escape_rejected(self):
        for name in [
            "main",
            "v0.3.1",
            "s384/../other",
            "s384/current",
            "b384/123-1-unknown",
        ]:
            self.assertFalse(cleanup.eligible(name))
        for name in [
            "b384/123-1-session-project",
            str(cleanup.REPO / "rm-123-1"),
            str(cleanup.REPO / "_road-material-source-proof-123-1"),
        ]:
            self.assertTrue(cleanup.eligible(name))

    def test_active_blocks_before_archive(self):
        def busy():
            raise ValueError("Worker active")

        with self.assertRaisesRegex(ValueError, "Worker active"):
            self.apply(self.plan(), busy)
        self.assertTrue(self.target.exists())
        self.assertEqual(list(self.archive.iterdir()), [])

    def test_change_since_review_blocks(self):
        plan = self.plan()
        (self.target / "evidence.json").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.apply(plan)
        self.assertTrue(self.target.exists())

    def test_activity_rechecked_before_delete(self):
        def busy_after_receipt():
            if list(self.archive.glob("*.json")):
                raise ValueError("became active")

        with self.assertRaisesRegex(ValueError, "became active"):
            self.apply(self.plan(), busy_after_receipt)
        self.assertTrue((self.target / "evidence.json").exists())

    def test_git_checkout_is_blocked(self):
        (self.target / ".git").write_text("gitdir: protected")
        plan = self.plan()
        self.assertFalse(plan["candidates"])
        self.assertIn("Git file/worktree", plan["blocked"][0]["reason"])

    def test_current_run_is_protected(self):
        with patch.dict(
            os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        ):
            self.assertFalse(self.plan()["candidates"])

    def test_path_escape_tampered_plan(self):
        plan = self.plan()
        plan["candidates"][0]["relative"] = "s384/../../outside"
        with self.assertRaises(ValueError):
            self.apply(plan)

    def test_reparse_refused(self):

        class Info:
            st_mode = 0o40755
            st_file_attributes = 0x400

        with patch.object(Path, "lstat", return_value=Info()):
            with self.assertRaisesRegex(ValueError, "Reparse"):
                cleanup.no_links(self.target)

    def test_quarantine_preserves_all_bytes(self):
        rows = self.plan()["candidates"][0]["inventory"]
        result = cleanup.quarantine(self.plan(), self.archive, lambda: None, self.root)
        self.assertFalse(self.target.exists())
        self.assertEqual(cleanup.inventory(Path(result[0]["destination"])), rows)
        self.assertEqual(result[0]["bytes_deleted"], 0)

    def test_quarantine_activity_blocks(self):
        def busy():
            raise ValueError("Listener active")

        with self.assertRaises(ValueError):
            cleanup.quarantine(self.plan(), self.archive, busy, self.root)
        self.assertTrue(self.target.exists())

    def test_standalone_detached_git_preserved(self):
        commit = self.make_git(self.target, "diagnostic", "candidate")
        subprocess.run(
            ["git", "-C", str(self.target), "checkout", "--detach"],
            check=True,
            capture_output=True,
        )
        old = time.time() - 172800
        for item in [*self.target.rglob("*"), self.target]:
            os.utime(item, (old, old))
        result = self.apply(self.plan())
        self.assertEqual(
            (Path(result[0]["destination"]) / ".git/HEAD").read_text().strip(), commit
        )

    def test_detached_protected_commit_rejected(self):
        self.make_git(self.target, "diagnostic", "candidate")
        protected_id = cleanup.git_commit(self.root / cleanup.REPO, "refs/tags/v0.3.1")
        with patch.object(cleanup, "git_commit", return_value=protected_id):
            self.assertFalse(self.plan()["candidates"])

    def test_active_pointer_invalid_or_missing_rejected(self):
        pointer = self.root / cleanup.REPO / "_yacs-unreal-ci/active.json"
        pointer.parent.mkdir()
        for name in ["../../outside", "_unreal-build-123-1"]:
            pointer.write_text(json.dumps({"schema_version": 1, "worktree": name}))
            self.assertFalse(self.plan()["candidates"])

    def test_main_branch_is_blocked(self):
        metadata = self.target / ".git"
        metadata.mkdir()
        (metadata / "HEAD").write_text("ref: refs/heads/main")
        self.assertFalse(self.plan()["candidates"])

    def test_nested_standalone_plugin_main_preserved(self):
        plugin = self.target / "Plugins/Example"
        plugin.mkdir(parents=True)
        self.make_git(plugin, "main", "plugin")
        old = time.time() - 172800
        for item in [*self.target.rglob("*"), self.target]:
            os.utime(item, (old, old))
        result = self.apply(self.plan(), idle=lambda: time.sleep(0.1))
        self.assertTrue(
            (Path(result[0]["destination"]) / "Plugins/Example/.git/HEAD").exists()
        )

    def test_nested_gitfile_is_protected(self):
        plugin = self.target / "Plugins/Example"
        plugin.mkdir(parents=True)
        (plugin / ".git").write_text("gitdir: D:/external")
        self.assertFalse(self.plan()["candidates"])
        self.assertIn(str(plugin / ".git"), self.plan()["blocked"][0]["reason"])

    def test_registered_worktree_common_owner_protected(self):
        self.make_git(self.target, "diagnostic", "common-owner")
        registry = self.target / ".git/worktrees/retained-child"
        registry.mkdir(parents=True)
        (registry / "gitdir").write_text("D:/retained/s384/123-1/.git")
        plan = self.plan()
        self.assertFalse(plan["candidates"])
        self.assertIn("registered worktrees", plan["blocked"][0]["reason"])

    def test_registry_added_after_review_blocks_move(self):
        self.make_git(self.target, "diagnostic", "common-owner")
        old = time.time() - 172800
        for item in [*self.target.rglob("*"), self.target]:
            os.utime(item, (old, old))
        plan = self.plan()
        (self.target / ".git/worktrees/retained-child").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "registered worktrees"):
            self.apply(plan)
        self.assertTrue(self.target.exists())

    def test_parallel_inventory_equals_serial(self):
        for index in range(40):
            child = self.target / "many" / str(index % 3)
            child.mkdir(parents=True, exist_ok=True)
            (child / f"{index}.bin").write_bytes(bytes([index]) * 4096)
        self.assertEqual(
            cleanup.inventory(self.target, workers=1),
            cleanup.inventory(self.target, workers=4),
        )

    def test_parallel_file_change_during_hash_rejected(self):
        original_sha = cleanup.sha

        def mutate(path):
            result = original_sha(path)
            if Path(path).name == "evidence.json":
                Path(path).write_text("changed during hash")
            return result

        with patch.object(cleanup, "sha", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "File changed while hashing"):
                cleanup.inventory(self.target, workers=4)

    def make_unborn_probe(self):
        destination = self.root / cleanup.REPO / "_official-mcp-source-probe-123-1"
        self.target.rename(destination)
        self.target = destination
        subprocess.run(
            ["git", "-C", str(destination), "init", "-b", "master"],
            check=True,
            capture_output=True,
        )
        old = time.time() - 172800
        for item in [*destination.rglob("*"), destination]:
            os.utime(item, (old, old))

    def test_unborn_default_blocked_optin_quarantines(self):
        self.make_unborn_probe()
        self.assertFalse(self.plan()["candidates"])
        plan = cleanup.preview(self.root, include_unborn_probes=True)
        self.assertEqual(len(plan["candidates"]), 1)
        result = self.apply(plan)
        self.assertTrue((Path(result[0]["destination"]) / ".git/HEAD").exists())

    def test_unborn_ref_present_blocks_optin(self):
        self.make_unborn_probe()
        (self.target / ".git/refs/heads/other").write_text("a" * 40)
        self.assertFalse(
            cleanup.preview(self.root, include_unborn_probes=True)["candidates"]
        )

    def test_unborn_shared_registry_blocks_optin(self):
        self.make_unborn_probe()
        (self.target / ".git/worktrees/required-child").mkdir(parents=True)
        self.assertFalse(
            cleanup.preview(self.root, include_unborn_probes=True)["candidates"]
        )

    def test_reviewed_remnant_names_optin_only(self):
        names = [
            "b384/123-1-session-plugin",
            "b384/123-1-input-boundary",
            "b384/123-1-input-boundary-plugin",
            str(cleanup.REPO / "_unreal-build-37639995352-1"),
            str(cleanup.REPO / "_portable-powershell-bootstrap"),
        ]
        for name in names:
            self.assertFalse(cleanup.eligible(name))
            self.assertTrue(cleanup.eligible(name, include_reviewed_remnants=True))
        self.assertFalse(
            cleanup.eligible(str(cleanup.REPO / "_unreal-build-999-1"), True)
        )

    def test_reviewed_old_build_active_pointer_blocks(self):
        old_build = self.root / cleanup.REPO / "_unreal-build-37639995352-1"
        old_build.mkdir()
        (old_build / ".git").write_text("gitdir: protected")
        pointer = self.root / cleanup.REPO / "_yacs-unreal-ci/active.json"
        pointer.parent.mkdir()
        pointer.write_text(
            json.dumps({"schema_version": 1, "worktree": old_build.name})
        )
        with self.assertRaisesRegex(ValueError, "Active cache is protected"):
            cleanup.protected(
                self.root,
                old_build.relative_to(self.root),
                include_reviewed_remnants=True,
            )

    def test_reviewed_remnant_shared_git_blocked(self):
        target = self.root / "b384/123-1-session-plugin"
        target.mkdir(parents=True)
        (target / ".git").write_text("gitdir: D:/shared-owner")
        plan = cleanup.preview(
            self.root, minimum_age_hours=0, include_reviewed_remnants=True
        )
        self.assertTrue(
            any(
                r["relative"].endswith("session-plugin")
                and "Git file/worktree" in r["reason"]
                for r in plan["blocked"]
            )
        )

    def test_reviewed_old_build_main_blocked(self):
        target = self.root / cleanup.REPO / "_unreal-build-37639995352-1"
        target.mkdir()
        self.make_git(target, "main", "protected build")
        plan = cleanup.preview(
            self.root, minimum_age_hours=0, include_reviewed_remnants=True
        )
        self.assertTrue(
            any(
                r["relative"].endswith(target.name) and "protected" in r["reason"]
                for r in plan["blocked"]
            )
        )

    def test_queue_no_runner_mutation(self):
        with patch.dict(
            os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        ):
            result = cleanup.queue_owned_run(self.archive)
        self.assertFalse(result["deletion_performed"])
        self.assertTrue(self.target.exists())
        self.assertEqual(
            json.loads(next(self.archive.glob("owned-run-*.json")).read_text())[
                "run_id"
            ],
            "123",
        )


if __name__ == "__main__":
    unittest.main()
