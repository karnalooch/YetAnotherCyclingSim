"""Exercise the actual bootstrap failure receipt with a synthetic UE surface."""

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


class BootstrapCompletionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.review_root = Path(temporary.name).resolve()
        self.destination = self.review_root / "b9fddea3f602-synthetic-bootstrap"
        self.destination.mkdir()
        self.map_bytes = b"synthetic unchanged saved map"
        self.alive = mock.Mock()
        self.api = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(self.destination)),
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=self.alive
            ),
            UnrealEditorSubsystem=object(),
            Vector=lambda x, y, z: SimpleNamespace(x=x, y=y, z=z),
            MathLibrary=SimpleNamespace(
                find_look_at_rotation=lambda *_args: SimpleNamespace(
                    pitch=0.0, yaw=0.0, roll=0.0
                )
            ),
            SystemLibrary=SimpleNamespace(
                get_console_variable_string_value=lambda _name: "LevelEditorViewport",
                get_console_variable_int_value=lambda name: (
                    1 if name == "PixelStreaming2.Editor.StartOnLaunch" else 0
                ),
                get_engine_version=lambda: "synthetic-engine",
            ),
            log=mock.Mock(),
        )
        spec = importlib.util.spec_from_file_location(
            "level_editor_bootstrap_test_subject",
            Path(__file__).with_name("bootstrap_level_editor_stream.py"),
        )
        self.bootstrap = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"unreal": self.api}):
            spec.loader.exec_module(self.bootstrap)
        subject = self.bootstrap
        self.map_path = self.destination / (
            "Content/" + subject.MAP_PACKAGE.removeprefix("/Game/") + ".umap"
        )
        self.map_path.parent.mkdir(parents=True)
        self.map_path.write_bytes(self.map_bytes)
        subject.MAP_SHA256 = hashlib.sha256(self.map_bytes).hexdigest()
        editor = SimpleNamespace(
            get_editor_world=lambda: SimpleNamespace(
                get_path_name=lambda: subject.MAP_PACKAGE + ".World"
            ),
            set_level_viewport_camera_info=mock.Mock(),
            get_level_viewport_camera_info=lambda: (
                self.api.Vector(*subject.CAMERA),
                SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0),
            ),
        )
        self.api.get_editor_subsystem = lambda _class: editor
        self.preparation = {
            "status": "READY_FOR_EDITOR_LAUNCH",
            "runtime_source_sha": subject.RUNTIME_SHA,
            "launcher_sha": "a" * 40,
        }
        prep_raw = json.dumps(self.preparation).encode()
        (self.destination / "level-editor-review-preparation.json").write_bytes(
            prep_raw
        )
        self.environment = {
            "YACS_LEVEL_EDITOR_REVIEW_ROOT": str(self.destination),
            "YACS_LEVEL_EDITOR_LAUNCHER_SHA": "a" * 40,
            "YACS_LEVEL_EDITOR_PREPARATION_SHA256": hashlib.sha256(
                prep_raw
            ).hexdigest(),
        }
        self.output = self.destination / "Saved/LevelEditorStream/scene.json"
        self.bridge = SimpleNamespace(
            READY_RELATIVE="Saved/LevelEditorStream/material-bridge-ready.json",
            install=mock.Mock(
                return_value={
                    "editor_start_filetime_utc": "123456789",
                    "status": "MATERIAL_BRIDGE_READY",
                }
            ),
        )

    def run_bootstrap(self):
        def local_path(value):
            if str(value) == r"D:\yacs\work\level-editor-review":
                return self.review_root
            return Path(value)

        with (
            mock.patch.object(self.bootstrap, "Path", side_effect=local_path),
            mock.patch.dict(os.environ, self.environment),
            mock.patch.dict(sys.modules, {"level_editor_material_bridge": self.bridge}),
            mock.patch.object(sys, "path", list(sys.path)),
        ):
            self.bootstrap.main()

    def test_install_failure_is_blocked_without_uncaught_fatal_python_error(self):
        self.bridge.install.side_effect = RuntimeError(
            "synthetic settings property is unavailable"
        )
        self.run_bootstrap()
        receipt = json.loads(self.output.read_text())
        self.assertEqual(receipt["status"], "BLOCKED")
        self.assertIn("synthetic settings property is unavailable", receipt["error"])
        self.assertEqual(receipt["map_package"], self.bootstrap.MAP_PACKAGE)
        self.assertFalse(receipt["map_or_assets_saved"])
        self.assertFalse(receipt["received_browser_frame"])
        self.assertNotIn("material_bridge_status", receipt)
        self.alive.assert_not_called()
        self.assertEqual(self.map_path.read_bytes(), self.map_bytes)

    def test_success_requires_bridge_installation_before_retaining_editor(self):
        self.run_bootstrap()
        receipt = json.loads(self.output.read_text())
        self.assertEqual(receipt["status"], "VIEWPORT_SCENE_READY")
        self.assertEqual(receipt["material_bridge_status"], "MATERIAL_BRIDGE_READY")
        self.assertFalse(receipt["official_mcp_transport_verified"])
        self.bridge.install.assert_called_once()
        self.alive.assert_called_once_with(True)
        self.assertEqual(self.map_path.read_bytes(), self.map_bytes)

    def test_failed_receipt_publication_still_raises_and_never_reports_ready(self):
        self.bridge.install.side_effect = RuntimeError("synthetic installation failure")
        temporary = self.output.with_suffix(".json.tmp")
        temporary.parent.mkdir(parents=True)
        temporary.write_bytes(b"existing receipt must not be overwritten")
        with self.assertRaises(FileExistsError):
            self.run_bootstrap()
        self.assertFalse(self.output.exists())
        self.assertEqual(
            temporary.read_bytes(), b"existing receipt must not be overwritten"
        )
        self.alive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
