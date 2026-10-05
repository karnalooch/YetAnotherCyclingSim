import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from restore_texture_prep_checkpoint import verify_or_restore


class TexturePrepCheckpointRestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "texture-prep-checkpoint.zip"
        self.manifest = self.root / "restore-manifest.json"
        self.destination = self.root / "restored"

    def write_fixture(self, members: dict[str, bytes], *, manifest_paths=None):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_STORED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        archive_bytes = self.archive.read_bytes()
        paths = list(members) if manifest_paths is None else manifest_paths
        files = []
        for name in paths:
            payload = members.get(name, b"")
            files.append(
                {
                    "path": name,
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "fixture",
                    "files": files,
                    "archive": {
                        "name": self.archive.name,
                        "size": len(archive_bytes),
                        "sha256": hashlib.sha256(archive_bytes).hexdigest(),
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_verified_restore_to_empty_directory(self):
        members = {
            "project/a.txt": b"alpha",
            "evidence/b.json": b'{"ok": true}',
        }
        self.write_fixture(members)
        self.destination.mkdir()
        report = verify_or_restore(
            self.manifest, self.archive, self.destination, apply=True
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["verified_files"], 2)
        self.assertEqual(report["restored_files"], 2)
        self.assertEqual((self.destination / "project/a.txt").read_bytes(), b"alpha")

    def test_extra_archive_member_rejected(self):
        members = {"project/a.txt": b"alpha", "extra.txt": b"unexpected"}
        self.write_fixture(members, manifest_paths=["project/a.txt"])
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            verify_or_restore(self.manifest, self.archive, self.destination)

    def test_unsafe_manifest_path_rejected(self):
        self.write_fixture({"../escape.txt": b"bad"})
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            verify_or_restore(self.manifest, self.archive, self.destination)

    def test_member_hash_mismatch_leaves_destination_unpublished(self):
        self.write_fixture({"project/a.txt": b"alpha"})
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["files"][0]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verify_or_restore(
                self.manifest, self.archive, self.destination, apply=True
            )
        self.assertFalse(self.destination.exists())

    def test_non_empty_destination_rejected(self):
        self.write_fixture({"project/a.txt": b"alpha"})
        self.destination.mkdir()
        (self.destination / "owner.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must be empty"):
            verify_or_restore(
                self.manifest, self.archive, self.destination, apply=True
            )
        self.assertEqual(
            (self.destination / "owner.txt").read_text(encoding="utf-8"), "keep"
        )

    def test_symlink_member_rejected(self):
        target = b"project/a.txt"
        info = zipfile.ZipInfo("project/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("project/a.txt", b"alpha")
            archive.writestr(info, target)
        archive_bytes = self.archive.read_bytes()
        files = [
            {
                "path": "project/a.txt",
                "size": 5,
                "sha256": hashlib.sha256(b"alpha").hexdigest(),
            },
            {
                "path": "project/link",
                "size": len(target),
                "sha256": hashlib.sha256(target).hexdigest(),
            },
        ]
        self.manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "files": files,
                    "archive": {
                        "name": self.archive.name,
                        "size": len(archive_bytes),
                        "sha256": hashlib.sha256(archive_bytes).hexdigest(),
                    },
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Symlink"):
            verify_or_restore(self.manifest, self.archive, self.destination)


if __name__ == "__main__":
    unittest.main()
