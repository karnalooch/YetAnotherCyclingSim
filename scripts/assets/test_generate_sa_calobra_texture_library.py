"""Regression checks for nested Slate callbacks during blocking UE operations."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class CallbackTests(unittest.TestCase):
    def setUp(self):
        self.engine = types.SimpleNamespace(
            unregister_slate_post_tick_callback=Mock(), log=Mock(), log_error=Mock()
        )
        spec = importlib.util.spec_from_file_location(
            "surface_batch",
            Path(__file__).with_name("generate_sa_calobra_texture_library_ue.py"),
        )
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, unreal=self.engine):
            spec.loader.exec_module(self.module)
        self.batch = self.module.Batch.__new__(self.module.Batch)
        self.batch.in_tick = False
        self.batch.phase = "next"
        self.batch.index = 0
        self.batch.items = [{}]

    def test_import_pumping_slate_does_not_reenter_import(self):
        calls = []

        def importer():
            calls.append("import")
            self.batch.tick(0)
            self.batch.phase = "rendering"

        self.batch.begin_item = importer
        self.batch.tick(0)
        self.assertEqual(calls, ["import"])
        self.assertFalse(self.batch.in_tick)

    def test_import_failure_releases_callback_guard(self):
        self.batch.begin_item = Mock(side_effect=RuntimeError("import failed"))
        self.batch.finish = Mock()
        self.batch.tick(0)
        self.batch.finish.assert_called_once_with("import failed")
        self.assertFalse(self.batch.in_tick)

    def test_finished_callback_and_repeated_finish_are_noops(self):
        self.batch.phase = "finished"
        self.batch.begin_item = Mock()
        self.batch.tick(0)
        self.batch.finish("late nested failure")
        self.batch.begin_item.assert_not_called()
        self.engine.unregister_slate_post_tick_callback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
