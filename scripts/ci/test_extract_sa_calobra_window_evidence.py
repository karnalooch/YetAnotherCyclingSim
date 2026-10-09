"""Negative tests for the read-only native image selector; no external packages."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from scripts.ci import extract_sa_calobra_window_evidence as subject


class WindowEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "input.zip"
        self.index = self.root / "index.csv"
        self.out = self.root / "out"
        self.png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR"
        self.png += struct.pack(">II", 1280, 720) + bytes(9)
        self.rows = [
            {
                "frame_id": identity,
                "window_id": subject.WINDOW_ID,
                "direction": identity.split("-")[2],
                "file": f"frames/{identity}.png",
                "size_bytes": str(len(self.png)),
                "sha256": hashlib.sha256(self.png).hexdigest(),
                "width_px": "1280",
                "height_px": "720",
                "native_readiness_status": "NATIVE_LOADING_AND_MIPS_READY",
            }
            for identity in subject.FRAME_IDS
        ]
        with ZipFile(self.archive, "w") as bundle:
            for row in self.rows:
                bundle.writestr(subject.PREFIX + row["file"], self.png)
        self.write_index()
        for name, value in (
            ("ARCHIVE_BYTES", self.archive.stat().st_size),
            ("ARCHIVE_SHA256", hashlib.sha256(self.archive.read_bytes()).hexdigest()),
            ("INDEX_BLOB_SHA", subject.git_blob_sha(self.index.read_bytes())),
        ):
            guard = patch.object(subject, name, value)
            guard.start()
            self.addCleanup(guard.stop)

    def write_index(self):
        data = io.StringIO()
        writer = csv.DictWriter(data, fieldnames=list(self.rows[0]))
        writer.writeheader()
        writer.writerows(self.rows)
        self.index.write_bytes(data.getvalue().encode())

    def run_extract(self):
        return subject.extract(self.archive, self.index, self.out)

    def test_copies_eight_byte_identical_images_without_admission(self):
        report = self.run_extract()
        self.assertEqual(report["frame_count"], 8)
        self.assertFalse(report["new_native_capture"])
        self.assertFalse(report["ai_generated_images"])
        for identity in subject.FRAME_IDS:
            self.assertEqual((self.out / f"{identity}.png").read_bytes(), self.png)
        self.assertEqual(
            json.loads((self.out / "receipt.json").read_text())["window_id"],
            subject.WINDOW_ID,
        )

    def test_archive_tampering_rejected(self):
        self.archive.write_bytes(self.archive.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "byte count"):
            self.run_extract()
        self.assertFalse(self.out.exists())

    def test_existing_evidence_is_not_overwritten(self):
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError, "Preserve"):
            self.run_extract()

    def test_index_tampering_rejected(self):
        self.index.write_bytes(self.index.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "index identity"):
            self.run_extract()

    def test_duplicate_frame_fails(self):
        self.rows[-1] = dict(self.rows[-2])
        self.write_index()
        blob = subject.git_blob_sha(self.index.read_bytes())
        with patch.object(subject, "INDEX_BLOB_SHA", blob):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.run_extract()

    def test_unsafe_path_and_wrong_dimensions_fail(self):
        for field, value, expected in (
            ("file", "../wrong.png", "Unsafe"),
            ("width_px", "2560", "dimensions"),
            ("sha256", "f" * 64, "PNG SHA256"),
        ):
            with self.subTest(field=field):
                original = self.rows[0][field]
                self.rows[0][field] = value
                self.write_index()
                blob = subject.git_blob_sha(self.index.read_bytes())
                with patch.object(subject, "INDEX_BLOB_SHA", blob):
                    with self.assertRaisesRegex(ValueError, expected):
                        self.run_extract()
                self.rows[0][field] = original
                self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
