"""Reject corrupted candidate maps before they can enter the UE preview."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.assets.check_material_maker_limestone import check


def fixture(root):
    export = root / "export"
    export.mkdir()
    x = np.arange(2048, dtype=np.float32) / 2048
    wave = np.sin(x * 2 * np.pi * 8)
    color = np.broadcast_to((0.7 + 0.025 * wave)[None, :, None], (2048, 2048, 3))
    nx = np.broadcast_to(0.1 * wave, (2048, 2048))
    normal = (np.stack((nx, np.zeros_like(nx), np.sqrt(1 - nx * nx)), axis=2) + 1) / 2
    orm = np.broadcast_to(np.array([0.95, 0.8, 0]), (2048, 2048, 3))
    for channel, data in (("BaseColor", color), ("Normal_DX", normal), ("ORM", orm)):
        Image.fromarray(np.uint8(data * 255)).save(
            export / ("SaCalobra_PaleLimestone_" + channel + ".png")
        )


class CandidateGuards(unittest.TestCase):
    def test_dark_tile_border_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            image = root / "export/SaCalobra_PaleLimestone_BaseColor.png"
            data = np.array(Image.open(image))
            data[:, 0, :3] = 0
            Image.fromarray(data).save(image)
            with self.assertRaisesRegex(ValueError, "wrap boundary"):
                check(root)
            self.assertFalse((root / "validation.json").exists())

    def test_metallic_limestone_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            image = root / "export/SaCalobra_PaleLimestone_ORM.png"
            data = np.array(Image.open(image))
            data[..., 2] = 128
            Image.fromarray(data).save(image)
            with self.assertRaisesRegex(ValueError, "not be metallic"):
                check(root)
            self.assertFalse((root / "validation.json").exists())


if __name__ == "__main__":
    unittest.main()
