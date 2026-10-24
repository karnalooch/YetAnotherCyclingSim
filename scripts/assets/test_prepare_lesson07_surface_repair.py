"""Verify source identity, scalar ranges and the fixed offline PBR contract."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts.assets import prepare_lesson07_surface_repair as packer


class SurfaceRepairPackingTests(unittest.TestCase):
    def test_exact_png_roundtrips_pixels_and_crosses_deflate_block_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = np.arange(256 * 256 * 4, dtype=np.uint32).astype(np.uint8).reshape(256, 256, 4)
            with patch.object(packer, "SIZE", (256, 256)):
                packer.save_png_exact(root / "one.png", values)
                packer.save_png_exact(root / "two.png", values)
            with Image.open(root / "one.png") as image:
                np.testing.assert_array_equal(np.asarray(image), values)
            self.assertEqual((root / "one.png").read_bytes(), (root / "two.png").read_bytes())
            with patch.object(packer, "SIZE", (256, 256)):
                with self.assertRaises(FileExistsError):
                    packer.save_png_exact(root / "one.png", values)

    def test_grayscale16_preserves_full_range_instead_of_clipping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "height.png"
            source = np.array([[0, 257], [32768, 65535]], dtype=np.uint16)
            Image.fromarray(source).save(path)
            with patch.object(packer, "SIZE", (2, 2)):
                actual = packer.scalar_u8(path)
            np.testing.assert_array_equal(actual, [[0, 1], [128, 255]])

    def test_linear_neutralization_preserves_grey_and_alpha(self):
        source = np.array([[[0, 0, 0, 255], [64, 64, 64, 255], [255, 255, 255, 255],
                            [180, 90, 30, 255]]], dtype=np.uint8)
        actual = packer.neutral_albedo(source)
        np.testing.assert_array_equal(actual[:, :3], source[:, :3])
        np.testing.assert_array_equal(actual[:, :, 0], actual[:, :, 1])
        np.testing.assert_array_equal(actual[:, :, 0], actual[:, :, 2])
        # Independent scalar calculation of the source's linear luminance.
        channels = [(v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4)
                    for v in (180, 90, 30)]
        luminance = sum(v * weight for v, weight in zip(channels, (.2126, .7152, .0722)))
        expected = round((1.055 * luminance ** (1 / 2.4) - .055) * 255)
        self.assertEqual(int(actual[0, 3, 0]), expected)
        self.assertEqual(int(actual[0, 3, 3]), 255)

    def test_bad_grass_identity_stops_before_download_or_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            grass = root / "grass"
            grass.mkdir()
            (grass / "slice_0_grass_normal.png").write_bytes(b"changed source")
            output = root / "package"
            with patch.object(packer, "acquire") as acquire:
                with self.assertRaisesRegex(ValueError, "identity"):
                    packer.prepare(output, root / "cache", grass, download=True)
                acquire.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_package_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "package"
            output.mkdir()
            marker = output / "owner-file"
            marker.write_bytes(b"retain")
            with self.assertRaises(FileExistsError):
                packer.prepare(output, root / "cache", root / "grass")
            self.assertEqual(marker.read_bytes(), b"retain")

    def test_fixed_source_records_are_complete_and_same_family(self):
        records = packer.source_records()
        self.assertEqual(set(records), {"diff", "nor_dx", "ao", "rough", "disp"})
        for name, row in records.items():
            self.assertEqual(row["url"],
                             f"https://dl.polyhaven.org/file/ph-assets/Textures/png/2k/dark_rock_02/dark_rock_02_{name}_2k.png")
            self.assertEqual(len(row["sha256"]), 64)
        manifest = packer.make_manifest({})
        self.assertEqual(manifest["masks_channels"], {"R": "AO", "G": "Roughness", "B": "Height"})
        self.assertTrue(manifest["provenance"]["grass_colour_unchanged"])
        self.assertFalse(manifest["provenance"]["runtime_displacement_enabled"])
        self.assertFalse(manifest["classification_changed"])


if __name__ == "__main__":
    unittest.main()
