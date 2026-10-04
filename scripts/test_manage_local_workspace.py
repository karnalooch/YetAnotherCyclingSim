"""Reject workspace configurations that could target a different project."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.manage_local_workspace import load_workspace


class WorkspaceConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "workspace.json"
        self.config = {
            "schema_version": 1,
            **{key: key for key in ("project", "data", "cache", "checkpoints", "work")},
        }

    def load(self):
        self.path.write_text(json.dumps(self.config))
        return load_workspace(self.path)

    def test_relative_paths_resolve_from_config_not_current_directory(self):
        result = self.load()
        self.assertEqual(Path(result["project"]), self.path.parent / "project")

    def test_parent_traversal_is_rejected(self):
        self.config["data"] = "../runner"
        with self.assertRaisesRegex(ValueError, "below its root"):
            self.load()

    def test_absolute_workspace_path_is_rejected(self):
        self.config["project"] = str(self.path.parent)
        with self.assertRaisesRegex(ValueError, "below its root"):
            self.load()

    def test_unknown_schema_is_rejected(self):
        self.config["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema"):
            self.load()


if __name__ == "__main__":
    unittest.main()
