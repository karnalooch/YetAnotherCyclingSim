"""Synthetic Git checkout regressions for exact-byte Unreal cache repair."""

from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci import materialize_unreal_cache_inputs as gate
from scripts.ci import unreal_ci_workspace as workspace_gate


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

    def track_inventory(self, total):
        """Build a real committed inventory, including an optional plugin's inputs."""
        existing = set(gate.fingerprint_paths(self.root))
        self.assertGreater(total, len(existing))
        self.attr.write_bytes(self.attr.read_bytes() + b"*.cpp text eol=lf\n")
        added = set()
        for index in range(total - len(existing)):
            folder = (
                "Plugins/Runtime/HoudiniEngine/Source/Fixture/Private"
                if index % 2 == 0
                else "Source/Fixture"
            )
            relative = f"{folder}/Input{index:04d}.cpp"
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"// native input {index}\n".encode("ascii"))
            added.add(relative)
        subprocess.run(
            ["git", "add", "--", ".gitattributes", "Source", "Plugins"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=yacs@example.invalid",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "large tracked inventory",
            ],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        return existing | added

    def test_large_tracked_inventory_checks_all_inputs_and_detects_late_drift(self):
        expected = self.track_inventory(670)
        actual = gate.fingerprint_paths(self.root)
        self.assertEqual(len(actual), 670)
        self.assertEqual(set(actual), expected)
        self.assertIsNone(gate.raw_fingerprint_source_drift(self.root))

        # Raw drift beyond the old limit must be detected even when Git's text
        # conversion reports a clean checkout.
        relative = max(name for name in expected if name.endswith(".cpp"))
        self.assertGreater(actual.index(relative), 512)
        path = self.root / relative
        changed = path.read_bytes().replace(b"\n", b"\r\n")
        head = gate.git(self.root, "rev-parse", "HEAD")
        path.write_bytes(changed)
        self.assertEqual(gate.git(self.root, "diff", "--name-only", "-z", "HEAD"), b"")
        self.assertEqual(gate.raw_fingerprint_source_drift(self.root), relative)
        self.assertEqual(path.read_bytes(), changed)
        self.assertEqual(gate.git(self.root, "rev-parse", "HEAD"), head)
        self.assertEqual(self.dll.read_bytes(), b"immutable binary")
        self.assertEqual(self.state.read_bytes(), b"immutable green proof state")

    def test_inventory_bound_remains_finite_and_workspace_preserves_error_detail(self):
        expected = self.track_inventory(gate.MAX_FINGERPRINT_INPUTS)
        self.assertEqual(set(gate.fingerprint_paths(self.root)), expected)
        extra = self.root / "Source/Overflow.cpp"
        extra.write_bytes(b"// one input over the supported inventory\n")
        subprocess.run(
            ["git", "add", "--", "Source/Overflow.cpp"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=yacs@example.invalid",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "overflow tracked inventory",
            ],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        message = (
            "Fingerprint input inventory is out of bounds: "
            f"count={gate.MAX_FINGERPRINT_INPUTS + 1}; "
            f"allowed=1..{gate.MAX_FINGERPRINT_INPUTS}"
        )
        with self.assertRaises(ValueError) as raised:
            gate.raw_fingerprint_source_drift(self.root)
        self.assertEqual(str(raised.exception), message)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertTrue(workspace_gate.has_untrusted_source_checkout(self.root))
        self.assertIn(
            "preserve active cache: ValueError: " + message, output.getvalue()
        )
        self.assertEqual(self.dll.read_bytes(), b"immutable binary")
        self.assertEqual(self.state.read_bytes(), b"immutable green proof state")

    def test_noncritical_config_raw_drift_is_detected(self):
        config = self.root / "Config/DefaultGame.ini"
        config.parent.mkdir(parents=True)
        config.write_bytes(b"[Game]\nTest=1\n")
        subprocess.run(
            ["git", "add", "Config/DefaultGame.ini"], cwd=self.root, check=True
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=yacs@example.invalid",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "config input",
            ],
            cwd=self.root,
            check=True,
        )
        with patch.object(
            gate, "fingerprint_paths", return_value=["Config/DefaultGame.ini"]
        ):
            self.assertIsNone(gate.raw_fingerprint_source_drift(self.root))
            config.write_bytes(b"[Game]\r\nTest=1\r\n")
            self.assertEqual(
                gate.raw_fingerprint_source_drift(self.root),
                "Config/DefaultGame.ini",
            )

    def test_manifest_is_included_in_fingerprint_audit(self):
        path = self.root / "YetAnotherCyclingSim.uproject"
        path.write_bytes(b'{"FileVersion":3}\n')
        subprocess.run(
            ["git", "add", "YetAnotherCyclingSim.uproject"],
            cwd=self.root,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=yacs@example.invalid",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "project input",
            ],
            cwd=self.root,
            check=True,
        )
        # Fixture omits other production-specific named helpers. The canonical
        # required manifest must still be discoverable.
        with (
            patch.object(gate, "UNREAL_COMPILE_TOOLING_EXACT", set()),
            patch.object(gate, "UNREAL_PROOF_EXACT", set()),
            patch.object(gate, "UE_CRITICAL_CONFIG", set()),
        ):
            got = gate.fingerprint_paths(self.root)
        self.assertIn("YetAnotherCyclingSim.uproject", got)

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
