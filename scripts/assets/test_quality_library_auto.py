"""Verify serial admission and fail-stop behavior without Unreal."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class DriverTests(unittest.TestCase):
    def setUp(self):
        self.engine = types.SimpleNamespace(log_error=Mock())
        spec = importlib.util.spec_from_file_location(
            "quality_auto",
            Path(__file__).parents[1] / "ue/generate_sa_calobra_quality_library_all.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, unreal=self.engine):
            spec.loader.exec_module(self.module)
        self.driver = self.module.Driver.__new__(self.module.Driver)
        self.driver.running = False
        self.driver.finished = False
        self.driver.last_check = 0
        self.driver.quality = {"main": Mock()}
        self.driver.write = Mock()
        self.driver.finish = Mock()
        self.batch = types.SimpleNamespace(
            in_tick=False, phase="awaiting_next_role", finish=Mock()
        )
        self.engine._yacs_quality_library = self.batch

    def test_does_not_admit_next_role_during_native_callback(self):
        self.batch.in_tick = True
        self.driver.tick(0)
        self.driver.quality["main"].assert_not_called()

    def test_low_memory_or_scene_guard_failure_stops_queue(self):
        self.driver.quality["main"].side_effect = RuntimeError("memory guard")
        self.driver.tick(0)
        self.batch.finish.assert_called_once_with("memory guard")
        self.driver.finish.assert_called_once_with("STOPPED_ON_ERROR", "memory guard")

    def test_failed_native_receipt_never_admits_another_role(self):
        with tempfile.TemporaryDirectory() as folder:
            self.batch.phase = "finished"
            self.batch.out = Path(folder)
            (self.batch.out / "result.json").write_text(
                json.dumps({"status": "failed", "error": "render failed"})
            )
            self.driver.tick(0)
        self.driver.quality["main"].assert_not_called()
        self.driver.finish.assert_called_once_with("STOPPED_ON_ERROR", "render failed")


if __name__ == "__main__":
    unittest.main()
