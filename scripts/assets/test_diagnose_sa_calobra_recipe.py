"""Fail-closed source-catalogue replay contract for owner review."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.assets import diagnose_sa_calobra_recipe as diagnostic
from scripts.ue import sa_calobra_whole_map_prep as prep


class RecipeDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proof = self.root / "proof"
        self.proof.mkdir()
        self.catalogue = self.root / "worldgen/materials/sa_calobra_texture_library_v2_20261005.json"
        self.catalogue.parent.mkdir(parents=True)
        self.original = b'{\n  "sample": "unchanged"\n}\n'
        self.catalogue.write_bytes(self.original)
        self.manifest = self.proof / "whole-map-prep/surface-prep-manifest.json"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_bytes(b"immutable-source-manifest")
        self.recipe = {
            "source_catalogue": self.catalogue.relative_to(self.root).as_posix(),
            "source_catalogue_sha256": diagnostic.sha256(self.original),
            "stable": "same",
        }
        self.master = {
            "status": "WHOLE_MAP_FIXED_MASTER_SAVED",
            "exact_sha": "a" * 40,
            "rendering_recipe": self.recipe,
            "rendering_recipe_sha256": diagnostic.sha256(prep.canonical(self.recipe)),
            "prep_manifest_sha256": diagnostic.sha256(self.manifest.read_bytes()),
        }
        (self.proof / "whole-map-master-receipt.json").write_text(json.dumps(self.master))
        patcher = patch.object(prep, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        recipe = patch.object(prep, "rendering_recipe", side_effect=self.current_recipe)
        recipe.start()
        self.addCleanup(recipe.stop)
        self.backup = self.root / "backups"

    def current_recipe(self):
        return {
            **self.recipe,
            "source_catalogue_sha256": diagnostic.sha256(self.catalogue.read_bytes()),
        }

    def test_matching_original_never_writes(self):
        diagnostic.check(self.proof, self.backup, normalize_lf=True)
        self.assertEqual(self.catalogue.read_bytes(), self.original)
        self.assertFalse(self.backup.exists())

    def test_crlf_needs_explicit_normalization_with_verified_backup(self):
        windows = self.original.replace(b"\n", b"\r\n")
        self.catalogue.write_bytes(windows)
        with self.assertRaisesRegex(ValueError, "ONLY in CRLF"):
            diagnostic.check(self.proof, self.backup)
        self.assertEqual(self.catalogue.read_bytes(), windows)
        diagnostic.check(self.proof, self.backup, normalize_lf=True)
        self.assertEqual(self.catalogue.read_bytes(), self.original)
        backups = list(self.backup.glob("*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), windows)

    def test_semantically_modified_catalogue_does_not_get_overwritten(self):
        changed = self.original.replace(b"unchanged", b"changed")
        self.catalogue.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "not just CRLF"):
            diagnostic.check(self.proof, self.backup, normalize_lf=True)
        self.assertEqual(self.catalogue.read_bytes(), changed)
        self.assertFalse(self.backup.exists())

    def test_tampered_manifest_is_rejected(self):
        self.manifest.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "manifest differs"):
            diagnostic.check(self.proof, self.backup, normalize_lf=True)
        self.assertEqual(self.catalogue.read_bytes(), self.original)

    def test_other_recipe_field_mismatch_fails_closed(self):
        with patch.object(prep, "rendering_recipe", return_value={**self.recipe, "stable": "other"}):
            with self.assertRaisesRegex(ValueError, "fields=.*stable"):
                diagnostic.check(self.proof, self.backup, normalize_lf=True)


if __name__ == "__main__":
    unittest.main()
