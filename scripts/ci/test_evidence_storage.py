"""Negative tests for receipt integrity, path safety and the raw JSON budget."""
from __future__ import annotations

import gzip
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_evidence_storage as storage
from test_final_architecture_contract import verify_world_authority


class ReceiptStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = b'{\r\n  "status": "REJECTED", "performance_pass": false\r\n}\r\n'
        self.packed = gzip.compress(self.raw, mtime=0)
        (self.root / "receipt.json.gz").write_bytes(self.packed)
        self.entry = {
            "original": "receipt.json", "gzip": "receipt.json.gz",
            "original_bytes": len(self.raw),
            "original_sha256": hashlib.sha256(self.raw).hexdigest(),
            "gzip_bytes": len(self.packed),
            "gzip_sha256": hashlib.sha256(self.packed).hexdigest(),
        }

    def test_crlf_and_rejected_status_preserved_byte_for_byte(self):
        self.assertEqual(storage.verify_entry(self.root, self.entry, storage.git_blob(self.raw)), self.raw)

    def test_compressed_tamper_rejected(self):
        (self.root / "receipt.json.gz").write_bytes(self.packed[:-1] + b"x")
        with self.assertRaises(ValueError):
            storage.verify_entry(self.root, self.entry)

    def test_original_hash_tamper_rejected(self):
        self.entry["original_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            storage.verify_entry(self.root, self.entry)

    def test_original_git_blob_tamper_rejected(self):
        with self.assertRaises(ValueError):
            storage.verify_entry(self.root, self.entry, "0" * 40)

    def test_declared_original_size_rejected(self):
        self.entry["original_bytes"] -= 1
        with self.assertRaises(ValueError):
            storage.verify_entry(self.root, self.entry)

    def test_path_traversal_rejected(self):
        for name in ("../receipt.json", "..\\receipt.json", "/receipt.json", "C:receipt.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                storage.verify_entry(self.root, {**self.entry, "original": name})

    def test_new_large_json_rejected(self):
        with self.assertRaises(ValueError):
            storage.verify_raw("docs/new-receipt.json", b"x" * (storage.LIMIT + 1))

    def test_exact_exception_allowed_but_growth_rejected(self):
        raw = b"x" * (storage.LIMIT + 1)
        path = "docs/replay-manifest.json"
        with patch.dict(storage.RETAINED_BLOBS, {path: storage.git_blob(raw)}, clear=True):
            storage.verify_raw(path, raw)
            with self.assertRaises(ValueError):
                storage.verify_raw(path, raw + b"x")

    def test_small_json_allowed(self):
        storage.verify_raw("docs/new.json", self.raw)


class HoudiniAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.bible = "\n".join((
            "## Current executor decision — Houdini / SideFX, 2026-10-16",
            "**Houdini is the primary procedural world-authoring executor.**",
            "original supplied SideFX HIP/HDA and exact tutorial steps",
            "Real relief/elevations and route geometry take precedence",
            "separate reversible Houdini layer",
            "source/physics authority and proof requirements",
            "tooling/sidefx/README.md",
            "## Historical evidence",
        ))
        self.agents = ("HOUDINI_SIDEFX_PRIMARY_20261016\n"
                       "Unreal is the consumer/runtime; PCG/PCGEx and Blender are supporting")

    def test_current_houdini_contract_admitted(self):
        verify_world_authority(self.bible, self.agents)

    def test_historical_phrase_cannot_replace_current_authority(self):
        marker = "**Houdini is the primary procedural world-authoring executor.**"
        mutated = self.bible.replace(marker, "") + "\n" + marker
        with self.assertRaises(AssertionError):
            verify_world_authority(mutated, self.agents)

    def test_each_safety_boundary_required(self):
        for marker in ("Real relief/elevations and route geometry take precedence",
                       "separate reversible Houdini layer",
                       "source/physics authority and proof requirements"):
            with self.subTest(marker=marker), self.assertRaises(AssertionError):
                verify_world_authority(self.bible.replace(marker, ""), self.agents)

    def test_owner_decision_required(self):
        with self.assertRaises(AssertionError):
            verify_world_authority(self.bible, self.agents.replace("HOUDINI_SIDEFX_PRIMARY_20261016", ""))

    def test_supporting_tool_boundary_required(self):
        with self.assertRaises(AssertionError):
            verify_world_authority(self.bible, "HOUDINI_SIDEFX_PRIMARY_20261016")

    def test_superseded_admission_rejected(self):
        mutated = self.bible.replace("## Historical evidence", "Embark production-pattern review first\n## Historical evidence")
        with self.assertRaises(AssertionError):
            verify_world_authority(mutated, self.agents)


if __name__ == "__main__":
    unittest.main()
