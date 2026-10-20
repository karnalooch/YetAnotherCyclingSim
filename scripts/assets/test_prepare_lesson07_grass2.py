"""CPU contract tests; injected EXR pixels are not native rendering evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts.assets import prepare_lesson07_grass2 as packer
from scripts.assets.test_material_forge import _variant_fixture, forge


class Grass2PackingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.variant = self.root / "variant"
        self.output = self.root / "package"
        self.size = 64
        _variant_fixture(self.variant, size=self.size)
        graph = self.variant / "Material.ptex"
        graph.write_bytes(b"synthetic graph fixture; not a native render")
        provenance_path = self.variant / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance.update(
            family=packer.FAMILY, variant=packer.VARIANT,
            graph=graph.name, graph_sha256=forge.sha256_path(graph),
        )
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        forge.check_variant(self.variant, expected_resolution=self.size)
        self.height = np.linspace(0, 1, self.size * self.size, dtype=np.float32).reshape(
            self.size, self.size
        )

    def prepare(self, height=None):
        with (
            patch.object(packer, "RESOLUTION", self.size),
            patch.object(packer, "read_height_exr", return_value=self.height if height is None else height),
        ):
            return packer.prepare(self.variant, self.output)

    def test_pack_preserves_input_bytes_and_source_receipts(self):
        before = {p.relative_to(self.variant): p.read_bytes()
                  for p in self.variant.rglob("*") if p.is_file()}
        receipt = self.prepare()
        after = {p.relative_to(self.variant): p.read_bytes()
                 for p in self.variant.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        for target, source in (("Colour", "BaseColor"), ("Normal", "Normal_DX")):
            self.assertEqual(
                (self.output / receipt["maps"][target]["file"]).read_bytes(),
                before[Path("export") / f"{packer.PREFIX}_{source}.png"],
            )
        self.assertEqual(receipt["slot"], 1)
        self.assertEqual(receipt["id_code"], 64)
        self.assertFalse(receipt["classification_changed"])
        self.assertFalse(receipt["terrain_changed"])
        self.assertFalse(receipt["native_ue_verified"])
        with Image.open(self.output / "T_Grass2_Masks.png") as image:
            masks = np.asarray(image)
            self.assertEqual(image.mode, "RGBA")
        with Image.open(self.variant / "export/YACS_Material_ORM.png") as image:
            orm = np.asarray(image)
        np.testing.assert_array_equal(masks[:, :, 0], orm[:, :, 0])
        np.testing.assert_array_equal(masks[:, :, 1], orm[:, :, 1])
        np.testing.assert_array_equal(masks[:, :, 3], orm[:, :, 0])
        np.testing.assert_array_equal(
            masks[:, :, 2], np.rint(self.height.astype(np.float64) * 255).astype(np.uint8)
        )
        for entry in receipt["maps"].values():
            self.assertEqual(entry["sha256"], forge.sha256_path(self.output / entry["file"]))
        self.assertEqual(
            json.loads((self.output / "grass2-package.json").read_text(encoding="utf-8")), receipt
        )

    def test_metallic_never_becomes_height_and_rows_are_not_flipped(self):
        orm = np.zeros((2, 2, 3), dtype=np.uint8)
        orm[:, :, 0] = [[5, 6], [7, 8]]
        orm[:, :, 1] = [[15, 16], [17, 18]]
        height = np.array([[0.0, 0.5], [1.0, 0.25]])
        with patch.object(packer, "RESOLUTION", 2):
            first = packer.pack_masks(orm, height)
            orm[:, :, 2] = 255
            second = packer.pack_masks(orm, height)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_array_equal(first[:, :, 2], [[0, 128], [255, 64]])
        np.testing.assert_array_equal(first[:, :, 0], [[5, 6], [7, 8]])

    def test_rejects_nonfinite_unnormalized_or_wrong_sized_height(self):
        for value in (np.nan, np.inf, -0.00001, 1.00001):
            with self.subTest(value=value):
                height = self.height.copy()
                height[0, 0] = value
                with self.assertRaises(ValueError):
                    self.prepare(height)
                self.assertFalse(self.output.exists())
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.prepare(self.height[:-1])

    def test_rejects_wrong_dimensions_without_resizing(self):
        self.assertEqual(packer.RESOLUTION, 2048)
        with patch.object(packer, "read_height_exr") as reader:
            with self.assertRaisesRegex(ValueError, "resolution"):
                packer.prepare(self.variant, self.output)
            reader.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_never_overwritten(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_bytes(b"owner data")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(sentinel.read_bytes(), b"owner data")

    def test_wrong_identity_missing_or_tampered_receipt_rejected(self):
        path = self.variant / "validation.json"
        original = path.read_bytes()
        for change in (
            {"family": "regional_limestone"},
            {"variant": "limestone_scree_v1"},
            {"status": "PASS"},
            {"normal_length_error_p99": 0.0},
        ):
            with self.subTest(change=change):
                record = json.loads(original)
                record.update(change)
                path.write_text(json.dumps(record), encoding="utf-8")
                tampered = path.read_bytes()
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertEqual(path.read_bytes(), tampered)
                self.assertFalse(self.output.exists())
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_modified_map_with_stale_native_receipt_rejected(self):
        height = self.variant / "export/YACS_Material_Height.exr"
        height.write_bytes(height.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "Native decode hash mismatch"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_missing_native_receipt_rejected(self):
        (self.variant / "export/YACS_Material_native-check.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_modified_original_graph_rejected(self):
        (self.variant / "Material.ptex").write_bytes(b"changed graph")
        with self.assertRaisesRegex(ValueError, "graph hash"):
            self.prepare()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
