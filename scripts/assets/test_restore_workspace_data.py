import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.assets.restore_workspace_data import restore


class RestoreCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "data"
        self.payload = b"frozen source\x00\xff"
        self.item = {
            "path": "source/data.bin",
            "size_bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
            "storage": {
                "release": "test",
                "asset": "data.zip",
                "member": "source/data.bin",
            },
        }
        self.manifest = {"schema_version": 1, "files": [self.item]}
        with zipfile.ZipFile(self.root / "data.zip", "w") as archive:
            archive.writestr("source/data.bin", self.payload)

    def test_roundtrip_and_verified_repeat(self):
        self.assertEqual(
            restore(self.manifest, self.root, self.target)["status"], "MISSING"
        )
        self.assertFalse(self.target.exists())
        self.assertEqual(
            restore(self.manifest, self.root, self.target, True)["restored"], 1
        )
        self.assertEqual((self.target / self.item["path"]).read_bytes(), self.payload)
        self.assertEqual(
            restore(self.manifest, self.root, self.target, True)["existing_verified"], 1
        )

    def test_corrupt_payload_does_not_create_destination(self):
        self.item["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "mismatch"):
            restore(self.manifest, self.root, self.target, True)
        self.assertFalse((self.target / self.item["path"]).exists())

    def test_existing_owner_file_is_never_replaced(self):
        target = self.target / self.item["path"]
        target.parent.mkdir(parents=True)
        target.write_bytes(b"owner work")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            restore(self.manifest, self.root, self.target, True)
        self.assertEqual(target.read_bytes(), b"owner work")

    def test_escaping_paths_are_rejected(self):
        for relative in ("../other", "/other", "C:/other", "source\\other"):
            self.item["path"] = relative
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                restore(self.manifest, self.root, self.target, True)


if __name__ == "__main__":
    unittest.main()
