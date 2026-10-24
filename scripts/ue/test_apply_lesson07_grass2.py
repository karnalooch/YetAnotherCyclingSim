"""Fail-closed package admission checks; these do not claim an Unreal import."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from scripts.ue.apply_lesson07_grass2 import validate_package


class PackageAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"family": "mediterranean_soil", "variant": "limestone_grass2_v1", "slot": 1, "id_code": 64, "maps": {}}
        for channel in ("Colour", "Normal", "Masks"):
            path = self.root / f"T_Grass2_{channel}.png"
            Image.new("RGB", (2048, 2048), (100, 110, 80)).save(path)
            self.manifest["maps"][channel] = {
                "file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        self.write_manifest()

    def write_manifest(self):
        (self.root / "grass2-package.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_valid_package_is_read_without_mutating_files(self):
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        self.assertEqual(validate_package(self.root), self.manifest)
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_wrong_class_target_is_rejected(self):
        self.manifest["slot"] = 3
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "existing Grass2"):
            validate_package(self.root)

    def test_texture_tamper_is_rejected(self):
        with (self.root / "T_Grass2_Colour.png").open("ab") as stream:
            stream.write(b"changed after validation")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_package(self.root)

    def test_missing_map_and_path_escape_are_rejected(self):
        del self.manifest["maps"]["Masks"]
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Exactly"):
            validate_package(self.root)
        self.manifest["maps"]["Masks"] = {"file": "../another.png", "sha256": "0" * 64}
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "file name"):
            validate_package(self.root)

    def test_rehashed_wrong_dimensions_are_rejected(self):
        path = self.root / "T_Grass2_Normal.png"
        Image.new("RGB", (1024, 1024)).save(path)
        self.manifest["maps"]["Normal"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "2048"):
            validate_package(self.root)


if __name__ == "__main__":
    unittest.main()
