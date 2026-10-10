"""Synthetic Git checkout regressions for exact-byte Unreal cache repair."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.ci import materialize_unreal_cache_inputs as gate


class UnrealCacheMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            ["git", "config", "core.autocrlf", "true"], cwd=self.root, check=True
        )
        self.attr = self.root / ".gitattributes"
        self.attr.write_bytes(
            b"*.cs text eol=lf\nscripts/ci/Invoke-YacsUnrealCi.ps1 text eol=lf\n"
        )
        self.cs = self.root / "Source/Unit.Build.cs"
        self.cs.parent.mkdir(parents=True)
        self.cs.write_bytes(b"first\nsecond\n")
        self.ps = self.root / "scripts/ci/Invoke-YacsUnrealCi.ps1"
        self.ps.parent.mkdir(parents=True)
        self.ps.write_bytes(b"Write-Host 'test'\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=yacs@example.invalid",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "pinned sources",
            ],
            cwd=self.root,
            check=True,
        )
        self.paths = ["Source/Unit.Build.cs", "scripts/ci/Invoke-YacsUnrealCi.ps1"]
        self.initial_head = gate.git(self.root, "rev-parse", "HEAD")
        self.dll = self.root / "Binaries/Win64/build.dll"
        self.dll.parent.mkdir(parents=True)
        self.dll.write_bytes(b"immutable binary")
        self.state = self.root / "Saved/BuildCache/UnrealCi/state.json"
        self.state.parent.mkdir(parents=True)
        self.state.write_bytes(b"immutable green proof state")

    def test_only_crlf_drift_is_materialized_from_original_index(self):
        self.cs.write_bytes(b"first\r\nsecond\r\n")
        self.ps.write_bytes(b"Write-Host 'test'\r\n")
        result = gate.materialize(self.root, self.paths)
        self.assertEqual(result["checked"], 2)
        self.assertEqual(result["restored"], 2)
        self.assertEqual(self.cs.read_bytes(), b"first\nsecond\n")
        self.assertEqual(self.ps.read_bytes(), b"Write-Host 'test'\n")
        self.assertEqual(self.initial_head, gate.git(self.root, "rev-parse", "HEAD"))
        self.assertEqual(self.dll.read_bytes(), b"immutable binary")
        self.assertEqual(self.state.read_bytes(), b"immutable green proof state")
        self.assertFalse(list(self.root.rglob(".yacs-unreal-eol-*")))
        self.assertEqual(gate.materialize(self.root, self.paths)["restored"], 0)

    def test_unexpected_edit_fails_without_overwriting_source(self):
        self.cs.write_bytes(b"malicious bytes\n")
        with self.assertRaisesRegex(ValueError, "tracked source modifications|non-EOL"):
            gate.materialize(self.root, self.paths)
        self.assertEqual(self.cs.read_bytes(), b"malicious bytes\n")
        self.assertEqual(self.dll.read_bytes(), b"immutable binary")

    def test_missing_eol_attribute_fails_before_change(self):
        self.cs.write_bytes(b"first\r\nsecond\r\n")
        self.attr.write_bytes(b"*.cs text=auto\n")
        with self.assertRaisesRegex(
            ValueError, "tracked source modifications|pinned LF"
        ):
            gate.materialize(self.root, self.paths)
        self.assertEqual(self.cs.read_bytes(), b"first\r\nsecond\r\n")

    def test_symlink_fails_closed(self):
        self.cs.unlink()
        try:
            self.cs.symlink_to(self.ps)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "link/junction"):
            gate.validate_target(self.root, self.paths[0])

    def test_different_committed_blob_is_not_reinterpreted(self):
        self.cs.write_bytes(b"first\r\nwrong\r\n")
        with self.assertRaisesRegex(ValueError, "tracked source modifications|non-EOL"):
            gate.materialize(self.root, self.paths)
        self.assertEqual(self.state.read_bytes(), b"immutable green proof state")


if __name__ == "__main__":
    unittest.main()
