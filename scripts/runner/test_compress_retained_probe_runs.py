"""Temporary retention fixtures only; never prunes the real runner or retained proofs."""

import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest import mock

from scripts.runner import compress_retained_probe_runs as tool


class CompressionTests(unittest.TestCase):
    def setUp(self):
        saved = Path(__file__).resolve().parents[2] / "Saved"
        saved.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=saved)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "retained-proof"
        self.source.mkdir()
        (self.source / "empty").mkdir()
        (self.source / "proof.json").write_bytes(b'{"evidence":true}\n')
        (self.source / "binary").write_bytes(bytes(range(256)))
        self.receipt = self.root / "abc.verified.json"
        self.receipt.write_text(
            json.dumps(
                {
                    "status": "QUARANTINED_VERIFIED_NO_BYTES_DELETED",
                    "destination": str(self.source),
                    "bytes_deleted": 0,
                    "inventory": tool.inventory(self.source),
                }
            )
        )
        past = time.time() - 48 * 3600
        for path in [*self.source.rglob("*"), self.source]:
            os.utime(path, (past, past))

    def tearDown(self):
        self.temp.cleanup()

    def archive(self):
        return tool.archive_retained(
            self.receipt, tool.sha(self.receipt), self.root, guard=lambda: None
        )

    def test_default_preview_has_no_writes(self):
        before = sorted(p.name for p in self.root.iterdir())
        result = tool.preview(self.root)
        self.assertEqual(len(result["entries"]), 1)
        self.assertFalse(result["writes"])
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))

    def test_full_archive_and_explicit_prune_preserve_bytes_empty_dirs(self):
        result = self.archive()
        self.assertTrue(self.source.exists())
        tool.verify_archive(
            result["archive"], tool.inventory(self.source), result["archive_sha256"]
        )
        summary = tool.prune_retained(
            result["receipt"], result["receipt_sha256"], self.root, guard=lambda: None
        )
        self.assertFalse(self.source.exists())
        self.assertFalse(summary["original_work_mutated"])
        with tarfile.open(result["archive"], "r:gz") as archive:
            self.assertTrue(archive.getmember("empty").isdir())
            self.assertEqual(
                archive.extractfile("proof.json").read(), b'{"evidence":true}\n'
            )
            self.assertEqual(archive.extractfile("binary").read(), bytes(range(256)))

    def test_host_becomes_busy_during_final_verification_prevents_prune(self):
        result = self.archive()
        calls = 0

        def guard():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("Host became busy during final verification")

        with self.assertRaisesRegex(ValueError, "became busy"):
            tool.prune_retained(
                result["receipt"], result["receipt_sha256"], self.root, guard=guard
            )
        self.assertEqual(calls, 2)
        self.assertTrue(self.source.is_dir())
        self.assertTrue(Path(result["archive"]).is_file())
        self.assertFalse(list(self.root.glob("*.pruned.json")))

    def test_corrupt_archive_never_prunes(self):
        result = self.archive()
        path = Path(result["archive"])
        path.write_bytes(path.read_bytes()[:-12])
        with self.assertRaises((ValueError, EOFError, OSError)):
            tool.prune_retained(
                result["receipt"],
                result["receipt_sha256"],
                self.root,
                guard=lambda: None,
            )
        self.assertTrue(self.source.exists())

    def test_source_or_receipt_drift_never_prunes(self):
        result = self.archive()
        (self.source / "proof.json").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            tool.prune_retained(
                result["receipt"],
                result["receipt_sha256"],
                self.root,
                guard=lambda: None,
            )
        self.assertTrue(self.source.exists())
        Path(result["receipt"]).write_text("{}")
        with self.assertRaises(ValueError):
            tool.prune_retained(
                result["receipt"],
                result["receipt_sha256"],
                self.root,
                guard=lambda: None,
            )
        self.assertTrue(self.source.exists())

    def test_tar_duplicates_links_and_escape_rejected(self):
        for names in (("same", "same"), ("../escape",), ("linked",)):
            path = self.root / "malformed.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                for name in names:
                    info = tarfile.TarInfo(name)
                    if name == "linked":
                        info.type = tarfile.SYMTYPE
                        info.linkname = "outside"
                        archive.addfile(info)
                    else:
                        info.size = 1
                        archive.addfile(info, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                tool.verify_archive(path, [])

    def test_explicit_fresh_age_and_free_space_guard(self):
        os.utime(self.source, None)
        with mock.patch.object(
            tool.shutil, "disk_usage", return_value=type("Usage", (), {"free": 0})()
        ):
            with self.assertRaisesRegex(ValueError, "Insufficient free space"):
                tool.archive_retained(
                    self.receipt,
                    tool.sha(self.receipt),
                    self.root,
                    guard=lambda: None,
                    minimum_age_hours=0,
                )
        self.assertTrue(self.source.exists())
        self.assertFalse(list(self.root.glob("*.tar.gz")))
        result = tool.archive_retained(
            self.receipt,
            tool.sha(self.receipt),
            self.root,
            guard=lambda: None,
            minimum_age_hours=0,
        )
        self.assertEqual(result["minimum_age_hours"], 0)

    @unittest.skipUnless(os.name == "nt", "NTFS stream fixture requires Windows")
    def test_nonempty_ads_blocks_archive_and_prune(self):
        stream = str(self.source / "proof.json") + ":retained-evidence"
        try:
            with open(stream, "wb") as output:
                output.write(b"must-not-be-lost")
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "ADS"):
            self.archive()
        self.assertTrue(self.source.exists())
        self.assertFalse(list(self.root.glob("*.tar.gz")))

    def test_path_escape_and_new_quarantine_rejected(self):
        with self.assertRaises(ValueError):
            tool.confined(self.root.parent, self.root)
        os.utime(self.source, None)
        with self.assertRaises(ValueError):
            self.archive()
        self.assertTrue(self.source.exists())


if __name__ == "__main__":
    unittest.main()
