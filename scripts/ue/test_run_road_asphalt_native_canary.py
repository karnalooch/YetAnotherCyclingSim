"""Pure boundary tests for #364 native canary, never substitute for a real UE run."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ue import run_road_asphalt_native_canary as native


class NativeCanaryBoundaryTests(unittest.TestCase):
    def test_owned_run_token_and_exclusive_proof_leaf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = native.ROOT
            try:
                native.ROOT = root
                proof = root / "Saved/RuntimeProof/RoadMaterialBaseline/123456-1"
                proof.mkdir(parents=True)
                with patch.object(native.session, "_safe_path", side_effect=lambda r, p: r / p):
                    target = native.output_path(str(proof))
                    self.assertEqual(target.name, "road-asphalt-canary.json")
                    target.write_text("already used")
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        native.output_path(str(proof))
                    with self.assertRaises(ValueError):
                        native.output_path(str(root / "Saved/RuntimeProof/Other/123456-1"))
            finally:
                native.ROOT = original

    def test_native_entry_source_requires_matching_exact_head_blob(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "scripts/ue/run_road_asphalt_native_canary.py"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"original")
            with (
                patch.object(native, "ROOT", root),
                patch.object(native.session, "_safe_path", side_effect=lambda r, p: r / p),
                patch(
                    "scripts.committed_git_blobs._read_exact_blobs",
                    return_value={"scripts/ue/run_road_asphalt_native_canary.py": b"original"},
                ),
            ):
                native.assert_pinned_entry_source("a" * 40)
                source.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "differs"):
                    native.assert_pinned_entry_source("a" * 40)


if __name__ == "__main__":
    unittest.main()
