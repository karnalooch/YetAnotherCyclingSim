"""Focused CPU regressions for the L07 source-family/packed-channel repair."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from scripts import assemble_surface_slices as assembler


class SurfaceSourceRepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.output = self.root / "candidate"
        self.size = (4, 4)
        self.expected = {}
        self.hashes = {}
        tex_dir = self.project / "worldgen/houdini/sa_calobra/inputs/textures"
        # These are the actual independently traced source families. No legacy
        # Meadow/Boulder input or other class source exists in the fixture.
        families = (
            ("Grass", "SaCalobra_Grass", ("worldgen/materials/scanned_refinement/source/"
             "aerial_grass_rock_nor_dx_4k.png")),
            ("Cliffs", "SaCalobra_PaleLimestone", ("worldgen/materials/material_maker/"
             "surface_set/scree/export/SaCalobra_PaleLimestone_Normal_DX.png")),
        )
        for index, (name, stem, normal_path) in enumerate(families):
            grid = np.arange(16, dtype=np.uint8).reshape(4, 4)
            colour = np.stack((grid + 10, grid + 60, grid + 100,
                               np.full_like(grid, 255)), axis=-1)
            normal = np.stack((grid + 90 + index * 20, grid + 120, grid + 220,
                               np.full_like(grid, 255)), axis=-1)
            # Deliberately distinct AO, roughness and metallic catch luminance
            # conversion and accidental metallic-as-height regressions.
            packed = np.stack((grid + 5, grid + 180, grid + 40,
                               np.full_like(grid, 255)), axis=-1)
            paths = {"colour": tex_dir / f"{stem}_BaseColor.png",
                     "normal": self.project / normal_path,
                     "packed": tex_dir / f"{stem}_Roughness.png"}
            self.expected[name] = {"colour": colour, "normal": normal,
                                   "packed": packed, "paths": paths}
            self.hashes[name] = {}
            for role in ("colour", "normal", "packed"):
                path = paths[role]
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(self.expected[name][role]).save(path)
                self.hashes[name][role] = hashlib.sha256(path.read_bytes()).hexdigest()

    def assemble(self, classes=("Grass", "Cliffs")):
        with (patch.object(assembler, "TARGET_SIZE", self.size),
              patch.object(assembler, "MATCHED_SOURCE_SHA256", self.hashes)):
            return assembler.assemble(self.output, classes, project_dir=self.project)

    def test_selected_classes_keep_colour_use_matching_normals_and_pack_only_g(self):
        before = {p: p.read_bytes() for p in self.project.rglob("*.png")}
        receipt = self.assemble()
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob("*.png")})
        self.assertEqual({p.name for p in self.output.glob("*.png")}, {
            f"slice_{slot}_{name}_{channel}.png"
            for slot, name in ((0, "grass"), (3, "cliffs"))
            for channel in ("colour", "normal", "masks")
        })
        for slot, name in ((0, "Grass"), (3, "Cliffs")):
            for channel in ("colour", "normal"):
                with Image.open(self.output / f"slice_{slot}_{name.lower()}_{channel}.png") as im:
                    np.testing.assert_array_equal(np.asarray(im), self.expected[name][channel])
            with Image.open(self.output / f"slice_{slot}_{name.lower()}_masks.png") as im:
                masks = np.asarray(im)
                self.assertEqual(im.mode, "RGBA")
            np.testing.assert_array_equal(masks[:, :, 1], self.expected[name]["packed"][:, :, 1])
            np.testing.assert_array_equal(masks[:, :, 0], 255)
            np.testing.assert_array_equal(masks[:, :, 2], 128)
            np.testing.assert_array_equal(masks[:, :, 3], 255)
        self.assertEqual(receipt["classes"], ["Grass", "Cliffs"])
        self.assertFalse(receipt["native_ue_verified"])
        self.assertFalse(receipt["classification_changed"])
        self.assertFalse(receipt["terrain_changed"])
        for path, identity in receipt["inputs"].items():
            self.assertEqual(identity["sha256"], hashlib.sha256(before[Path(path)]).hexdigest())
        self.assertEqual(json.loads((self.output / "assembly-receipt.json").read_text()), receipt)

    def test_packed_g_is_independent_of_other_channels_even_after_resize(self):
        path = self.expected["Grass"]["paths"]["packed"]
        first = assembler.load_l(path, (2, 2), channel="G")
        changed = self.expected["Grass"]["packed"].copy()
        changed[:, :, 0] = 255
        changed[:, :, 2] = 0
        Image.fromarray(changed).save(path)
        second = assembler.load_l(path, (2, 2), channel="G")
        np.testing.assert_array_equal(np.asarray(first), np.asarray(second))
        self.assertFalse(np.array_equal(np.asarray(second), np.asarray(assembler.load_l(path, (2, 2)))))

    def test_drifted_matching_source_is_rejected_before_any_output(self):
        self.expected["Cliffs"]["paths"]["normal"].write_bytes(b"wrong surface family")
        with self.assertRaisesRegex(ValueError, "Source hash differs"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "keep.txt"
        sentinel.write_bytes(b"existing accepted package")
        with self.assertRaises(FileExistsError):
            self.assemble()
        self.assertEqual(sentinel.read_bytes(), b"existing accepted package")

    def test_packed_input_cannot_silently_be_grayscale(self):
        path = self.root / "unexpected.png"
        Image.new("L", (4, 4), 100).save(path)
        with self.assertRaisesRegex(ValueError, "Packed G input must be RGB or RGBA"):
            assembler.load_l(path, (4, 4), channel="G")

    def test_class_selection_is_explicit_and_production_size_stays_2k(self):
        self.assertEqual(assembler.TARGET_SIZE, (2048, 2048))
        for classes in ((), ("Grass", "Grass"), ("Unknown",)):
            with self.subTest(classes=classes), self.assertRaises(ValueError):
                self.assemble(classes)
            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
