"""Bounded recovery decisions without installing packages or touching a host."""

from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.assets import restore_sa_calobra_lidar_decoder as recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "base/python.exe"
        self.base.parent.mkdir()
        self.base.write_bytes(b"original base fixture")
        self.identity = {"size_bytes": self.base.stat().st_size,
                         "sha256": hashlib.sha256(self.base.read_bytes()).hexdigest()}
        self.workspace = {"project": str(self.root / "project")}
        Path(self.workspace["project"]).mkdir()
        self.proof = self.root / "proof"
        self.proof.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(recovery, "BASE_IDENTITY", self.identity).start()
        patch.object(recovery.sys, "platform", "win32").start()
        self.environment = {
            "status": "GIS_ENVIRONMENT_UNAVAILABLE", "selected": None,
            "read_only": True, "installation_performed": False, "source_read": False,
            "configured_project": self.workspace["project"],
            "candidates": [{
                "origin": "registered_path_python", "path": str(self.base), "exit_code": 2,
                "probe": {
                    "executable": str(self.base), "python_version": [3, 12, 10],
                    "implementation": "cpython", "pointer_bits": 64,
                    "prefix": str(self.base.parent), "base_prefix": str(self.base.parent),
                    "decoder_versions": {"laspy": None, "lazrs": None,
                                         "numpy": "2.3.5", "pyproj": "3.8.0"},
                    "executable_identity": self.identity,
                },
            }],
        }

    def test_only_actual_missing_two_package_base_is_admitted(self):
        self.assertEqual(recovery.recovery_base(self.environment, self.workspace), self.base)
        for changes in ({"python_version": [3, 14, 8]}, {"pointer_bits": 32},
                        {"decoder_versions": {"laspy": None, "lazrs": None,
                                              "numpy": "2.3.5", "pyproj": None}}):
            other = deepcopy(self.environment)
            other["candidates"][0]["probe"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                recovery.recovery_base(other, self.workspace)

    def test_changed_base_bytes_stop_before_any_environment_creation(self):
        self.base.write_bytes(b"changed base")
        with patch.object(recovery, "run_owned") as run:
            report = recovery.restore(self.workspace, self.environment, self.proof)
        run.assert_not_called()
        self.assertEqual(report["status"], "FAILED")
        self.assertFalse(report["created_new_environment"])
        self.assertFalse(report["base_interpreter_unchanged_verified"])

    def test_existing_venv_and_unique_files_are_preserved(self):
        target = Path(self.workspace["project"]) / ".venv"
        target.mkdir()
        sentinel = target / "keep.txt"
        sentinel.write_bytes(b"existing user bytes")
        with patch.object(recovery, "run_owned") as run, \
             patch.object(recovery.urllib.request, "urlopen") as network:
            report = recovery.restore(self.workspace, self.environment, self.proof)
        run.assert_not_called()
        network.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"existing user bytes")
        self.assertFalse(report["created_new_environment"])
        self.assertIn("Existing project venv is preserved", report["error"])

    def test_wrong_wheel_hash_is_rejected_even_with_expected_name(self):
        expected = recovery.WHEELS["laspy"]
        path = self.proof / expected["file"]
        path.write_bytes(b"unapproved package bytes")
        with self.assertRaisesRegex(ValueError, "Downloaded approved wheel differs"):
            recovery.verify_wheel(path, expected)

    def test_download_redirect_cannot_change_the_named_public_origin(self):
        class Response(io.BytesIO):
            def geturl(self):
                return "https://different.invalid/package.whl"
        with patch.object(recovery.urllib.request, "urlopen", return_value=Response(b"x")), \
             patch.object(recovery, "run_owned") as run:
            report = recovery.restore(self.workspace, self.environment, self.proof)
        run.assert_not_called()
        self.assertFalse(report["created_new_environment"])
        self.assertIn("changed origin", report["error"])

    def test_install_is_offline_hashed_and_confined_to_the_new_venv(self):
        wheels = deepcopy(recovery.WHEELS)
        payloads = {row["url"]: name.encode() for name, row in wheels.items()}
        for row in wheels.values():
            row["sha256"] = hashlib.sha256(payloads[row["url"]]).hexdigest()
        calls = []
        target = Path(self.workspace["project"]) / ".venv"
        python = target / "Scripts/python.exe"

        class Response(io.BytesIO):
            def __init__(self, url):
                super().__init__(payloads[url])
                self.url = url

            def geturl(self):
                return self.url

        def run(argv, label, proof, report, timeout):
            calls.append((argv, label, timeout))
            if label == "create-venv":
                python.parent.mkdir()
                python.write_bytes(b"new venv fixture")

        with patch.object(recovery, "WHEELS", wheels), \
             patch.object(recovery.urllib.request, "urlopen", side_effect=lambda url, **kw: Response(url)), \
             patch.object(recovery, "run_owned", side_effect=run), \
             patch.object(recovery.reader, "resolve_existing_decoder", return_value={
                 "selected": {"path": str(python)}}):
            report = recovery.restore(self.workspace, self.environment, self.proof)
        self.assertEqual(report["status"], "APPROVED_LAZ_ENVIRONMENT_RESTORED")
        self.assertTrue(report["base_interpreter_unchanged_verified"])
        self.assertEqual(len(calls), 2)
        create, install = calls[0][0], calls[1][0]
        self.assertEqual(create[0], str(self.base))
        self.assertIn("--system-site-packages", create)
        self.assertIn("--copies", create)
        self.assertNotIn("--clear", create)
        self.assertNotIn("--upgrade", create)
        self.assertEqual(install[0], str(python))
        for flag in ("--no-index", "--no-deps", "--require-hashes", "--only-binary=:all:"):
            self.assertIn(flag, install)
        self.assertTrue(all(timeout <= 60 for _, _, timeout in calls))
        self.assertEqual(json.loads((self.proof / "decoder-restoration.json").read_text())["status"],
                         report["status"])


class OwnedProcessTests(unittest.TestCase):
    def exercise_failed_taskkill(self, *, hangs, child_kill_denied=False):
        """Run real children; replace only the Windows command with a fixture."""
        real_popen = subprocess.Popen
        children, original_kills, taskkill_arguments = [], {}, []
        primary = [sys.executable, "-I", "-B", "-c", "import time; time.sleep(30)"]

        def start(argv, **kwargs):
            is_taskkill = argv[0] == "taskkill.exe"
            if is_taskkill:
                taskkill_arguments.append(list(argv))
                code = ("import time; print('owned taskkill fixture', flush=True); time.sleep(30)"
                        if hangs else "import sys; print('owned taskkill refused', flush=True); sys.exit(7)")
                argv = [sys.executable, "-I", "-B", "-c", code]
            process = real_popen(argv, **kwargs)
            children.append(process)
            original_kills[process.pid] = process.kill
            if not is_taskkill and child_kill_denied:
                def denied():
                    raise PermissionError("deliberate owned stop failure")
                process.kill = denied
            return process

        with tempfile.TemporaryDirectory() as directory:
            proof, report = Path(directory), {"processes": []}
            try:
                with patch.object(recovery.subprocess, "Popen", side_effect=start), \
                     patch.object(recovery, "STOP_TIMEOUT_SECONDS", 2), \
                     self.assertRaisesRegex(ValueError, "Owned decoder recovery step failed"):
                    recovery.run_owned(primary, "owned-fixture", proof, report, 0.1)
                row, = report["processes"]
                self.assertEqual(len(children), 2)
                main, helper = children
                self.assertEqual(taskkill_arguments, [["taskkill.exe", "/PID", str(main.pid), "/T", "/F"]])
                self.assertEqual(row["owned_pid"], main.pid)
                self.assertEqual(row["owned_tree_cleanup_pid"], helper.pid)
                self.assertTrue(row["timed_out"])
                self.assertIn("TimeoutExpired", row["error"])
                self.assertEqual(row["owned_tree_cleanup_timed_out"], hangs)
                self.assertEqual(row["taskkill_fallback_kill_attempted"], hangs)
                self.assertTrue(row["child_fallback_kill_attempted"])
                self.assertFalse(row["owned_tree_cleanup_succeeded"])
                self.assertIsNotNone(helper.poll())
                self.assertEqual(row["owned_tree_cleanup_exit"], helper.returncode)
                self.assertEqual(row["exit_code"], main.poll())
                self.assertEqual(row["exit_code_observed"], not child_kill_denied)
                self.assertEqual(row["log"]["final"], not child_kill_denied)
                if child_kill_denied:
                    self.assertIsNone(row["exit_code"])
                    self.assertTrue(any("PermissionError" in e for e in row["cleanup_errors"]))
                else:
                    self.assertIsNotNone(main.poll())
                if not hangs:
                    self.assertEqual(helper.returncode, 7)
                raw = (proof / row["log"]["file"]).read_bytes()
                self.assertTrue(raw)
                self.assertEqual(row["log"]["size_bytes"], len(raw))
                self.assertEqual(row["log"]["sha256"], hashlib.sha256(raw).hexdigest())
            finally:
                # Even the deliberately denied-stop subcase owns no process
                # after this test. Never select processes by image/name.
                for process in children:
                    if process.poll() is None:
                        original_kills[process.pid]()
                    process.wait(timeout=2)

    def test_taskkill_timeout_reaps_the_helper_and_child_and_retains_actual_log_and_exit(self):
        self.exercise_failed_taskkill(hangs=True)

    def test_taskkill_nonzero_still_stops_child_and_failed_fallback_keeps_failure_evidence(self):
        for denied in (False, True):
            with self.subTest(child_kill_denied=denied):
                self.exercise_failed_taskkill(hangs=False, child_kill_denied=denied)


if __name__ == "__main__":
    unittest.main()
