"""Offline real-Git regression fixtures; only copied-script immutable identities differ."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("Bootstrap-YacsPcgEx.ps1")
TARGET = "Source/PCGExElementsClipper2/Private/Clipper2Lib/clipper.triangulation.cpp"


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plugin = self.root / "plugin"
        self.plugin.mkdir()
        self.git("init")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git(
            "remote", "add", "origin", "https://github.com/PCGEx/PCGExtendedToolkit.git"
        )
        self.target = self.plugin / TARGET
        self.target.parent.mkdir(parents=True)
        self.target.write_text("before\n")
        (self.plugin / "LICENSE").write_text("MIT License\n")
        (self.plugin / "PCGExtendedToolkit.uplugin").write_text(
            json.dumps({"VersionName": "0.79", "EngineVersion": "5.8.0"})
        )
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.head = self.git("rev-parse", "HEAD").strip()
        self.target.write_text("after\n")
        patch = self.git("diff", "--no-ext-diff").replace("\r\n", "\n")
        self.target.write_text("before\n")
        patch_path = (
            self.root
            / "scripts/worldgen/patches/pcgex-0.79-triangulate-holes-flat-union.patch"
        )
        patch_path.parent.mkdir(parents=True)
        patch_path.write_text(patch, newline="\n")
        source = SCRIPT.read_text().replace(
            "39a8f1bdc65b2c4613a1e87b71d93b4576db0a66", self.head
        )
        source = source.replace(
            "8182824990670e560d1a1f0d052288cc8a98dc5cdb370bdbf63f2666f9593d89",
            hashlib.sha256(patch.encode()).hexdigest(),
        )
        source = source.replace(
            "68614ae15d6bb03f2e58b0fb1dfa33e8eeebbfd31da08bd94ebfb378aeb63977",
            hashlib.sha256(b"after\n").hexdigest(),
        )
        self.script = self.root / "bootstrap.ps1"
        self.script.write_text(source)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.plugin), *args], text=True, stderr=subprocess.STDOUT
        )

    def run_script(self, mode="Validate", success=True, report=None):
        result = subprocess.run(
            [
                shutil.which("pwsh"),
                "-NoProfile",
                "-File",
                str(self.script),
                "-Mode",
                mode,
                "-RepoRoot",
                str(self.root),
                "-PluginRoot",
                str(self.plugin),
                "-ReportPath",
                str(report or self.root / "report.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def git_metadata(self):
        return {
            str(p.relative_to(self.plugin)): p.read_bytes()
            for p in (self.plugin / ".git").rglob("*")
            if p.is_file()
        }

    def snapshot(self):
        return {
            str(p.relative_to(self.plugin)): p.read_bytes()
            for p in self.plugin.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(self.plugin).parts
        }

    def test_validate_upstream_install_repeat_validate_readonly(self):
        before = self.snapshot()
        metadata = self.git_metadata()
        self.run_script()
        self.assertEqual(metadata, self.git_metadata())
        self.assertEqual(before, self.snapshot())
        self.run_script("Install")
        after = self.snapshot()
        self.assertEqual(self.target.read_text(), "after\n")
        self.run_script("Install")
        metadata = self.git_metadata()
        self.run_script()
        self.run_script()
        self.assertEqual(metadata, self.git_metadata())
        self.assertEqual(after, self.snapshot())
        report = json.loads((self.root / "report.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(report["compatibility_patch_state"], "applied")

    def test_drift_rejected_without_changes(self):
        for mode in ["Validate", "Install"]:
            self.target.write_text("user work\n")
            before = self.snapshot()
            self.run_script(mode, False)
            self.assertEqual(before, self.snapshot())

    def test_untracked_and_extra_tracked_rejected(self):
        self.run_script("Install")
        (self.plugin / "user.txt").write_text("keep me")
        before = self.snapshot()
        self.run_script("Install", False)
        self.run_script(success=False)
        self.assertEqual(before, self.snapshot())

    def test_extra_tracked_change_rejected(self):
        self.run_script("Install")
        (self.plugin / "LICENSE").write_text("MIT License\nuser work\n")
        before = self.snapshot()
        self.run_script("Install", False)
        self.run_script(success=False)
        self.assertEqual(before, self.snapshot())

    def test_patch_hash_drift_rejected_before_write(self):
        patch = (
            self.root
            / "scripts/worldgen/patches/pcgex-0.79-triangulate-holes-flat-union.patch"
        )
        patch.write_text(patch.read_text() + "\n")
        before = self.snapshot()
        self.run_script("Install", False)
        self.assertEqual(before, self.snapshot())

    def test_assume_unchanged_and_skip_worktree_rejected(self):
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.git("update-index", "--" + flag, "LICENSE")
                (self.plugin / "LICENSE").write_text("MIT License\nhidden user work\n")
                before = self.snapshot()
                self.run_script("Install", False)
                self.run_script(success=False)
                self.assertEqual(before, self.snapshot())
                self.assertEqual(self.target.read_text(), "before\n")
                self.git("update-index", "--no-" + flag, "LICENSE")
                (self.plugin / "LICENSE").write_text("MIT License\n")

    def test_staged_change_rejected(self):
        self.git("add", "LICENSE")
        (self.plugin / "LICENSE").write_text("MIT License\nchanged\n")
        self.git("add", "LICENSE")
        (self.plugin / "LICENSE").write_text("MIT License\n")
        self.run_script("Install", False)
        self.assertEqual(self.target.read_text(), "before\n")

    def test_wrong_pin_origin_and_report_path_rejected(self):
        self.git("remote", "set-url", "origin", "https://example.invalid/wrong.git")
        self.run_script("Install", False)
        self.assertEqual(self.target.read_text(), "before\n")
        self.git(
            "remote",
            "set-url",
            "origin",
            "https://github.com/PCGEx/PCGExtendedToolkit.git",
        )
        self.run_script(report=self.plugin / "bad-report.json", success=False)
        self.assertFalse((self.plugin / "bad-report.json").exists())
        self.git("commit", "--allow-empty", "-m", "wrong pin")
        self.run_script("Install", False)
        self.assertEqual(self.target.read_text(), "before\n")


if __name__ == "__main__":
    unittest.main()
