"""Run the production offline staging writer on temporary files, never Unreal."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from scripts.ue import lesson07_wingman_client as client


class SurfaceStageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        patch = mock.patch.object(client, "SURFACE_ROOT", self.root / "stages")
        patch.start()
        self.addCleanup(patch.stop)
        self.token = "123-1"
        self.target = client.surface_stage(self.token) / client.SURFACE_IMPORT_FILE
        self.target.parent.mkdir(parents=True)
        self.template = Path(__file__).with_name(client.SURFACE_IMPORT_FILE).read_bytes()
        self.source = self.root / "source.py"
        self.source.write_bytes(self.template)
        stage = Path(__file__).with_name("Stage-Lesson07SurfaceRepair.ps1").read_text()
        writer = stage.split("$renderSource = @'\n", 1)[1].split("\n'@\n", 1)[0]
        self.writer = compile(writer, "Stage-Lesson07SurfaceRepair.ps1:renderSource", "exec")

    def run_writer(self, target=None):
        output = io.StringIO()
        argv = ["-c", self.token, str(self.source), str(target or self.target)]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            # This is only the fixed offline staging writer extracted above.
            # It writes importer source as bytes and never executes that source.
            exec(self.writer, {"__name__": "__main__"})
        return output.getvalue()

    def test_full_template_and_hash_receipt_are_preserved_without_overwrite(self):
        output = self.run_writer()
        rendered = self.target.read_bytes()
        self.assertEqual(rendered, client.surface_source_prefix(self.token) + self.template)
        proof = json.loads(output.removeprefix("SURFACE_STAGE_SOURCE "))
        self.assertEqual(proof, {
            "template_sha256": client.SURFACE_IMPORT_SHA256,
            "rendered_sha256": hashlib.sha256(rendered).hexdigest(),
        })
        compile(b"import sys\n" + rendered, "wrapped-file-source", "exec")
        with self.assertRaises(FileExistsError):
            self.run_writer()
        self.assertEqual(self.target.read_bytes(), rendered)
        self.assertEqual(self.source.read_bytes(), self.template)

    def test_wrong_destination_or_changed_template_fail_before_write(self):
        wrong_target = self.target.with_name("other.py")
        with self.assertRaisesRegex(client.ProbeError, "SURFACE_STAGE_TARGET"):
            self.run_writer(wrong_target)
        self.assertFalse(wrong_target.exists())
        self.assertFalse(self.target.exists())
        self.source.write_bytes(self.template + b"\n")
        with self.assertRaisesRegex(client.ProbeError, "SURFACE_IMPORT_SOURCE_HASH"):
            self.run_writer()
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
