"""Lightweight CPU tests for YACS Material Forge contracts."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FORGE_PATH = ROOT / "scripts/assets/material_forge.py"


def _load_forge():
    spec = importlib.util.spec_from_file_location("yacs_material_forge_tested", FORGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Material Forge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


forge = _load_forge()


def _png(path: Path, array: np.ndarray) -> None:
    Image.fromarray(np.asarray(array, dtype=np.uint8)).save(path)


def _variant_fixture(root: Path, size: int = 64) -> None:
    export = root / "export"
    export.mkdir(parents=True)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    phase = 2 * np.pi * (xx / size * 4 + yy / size * 3)
    color_scalar = 0.45 + 0.06 * np.sin(phase)
    color = np.stack(
        [color_scalar * 0.97, color_scalar * 0.985, color_scalar], axis=2
    )
    nx = 0.08 * np.sin(phase)
    ny = 0.08 * np.cos(phase)
    nz = np.sqrt(np.maximum(0, 1 - nx * nx - ny * ny))
    normal = (np.stack([nx, ny, nz], axis=2) + 1) * 0.5
    rough = 0.82 + 0.03 * np.sin(phase)
    orm = np.stack([np.full_like(rough, 0.95), rough, np.zeros_like(rough)], axis=2)
    detail = np.stack(
        [
            0.5 + 0.5 * np.sin(phase),
            0.5 + 0.5 * np.cos(phase * 2.0),
            0.5 + 0.5 * np.sin(phase * 3.0),
        ],
        axis=2,
    )
    for name, array in (
        ("BaseColor", color),
        ("Normal_DX", normal),
        ("ORM", orm),
        ("DetailMasks", detail),
    ):
        _png(export / f"{forge.EXPORT_PREFIX}_{name}.png", np.clip(array * 255, 0, 255))
    (export / f"{forge.EXPORT_PREFIX}_Height.exr").write_bytes(b"\x76\x2f\x31\x01fixture")
    # Stub the external decoder at its JSON boundary; this is not a real EXR render.
    suffixes = (
        "BaseColor.png",
        "Normal_DX.png",
        "ORM.png",
        "Height.exr",
        "DetailMasks.png",
    )
    (export / f"{forge.EXPORT_PREFIX}_native-check.json").write_text(
        json.dumps(
            {
                "valid": True,
                "images": {
                    suffix: {
                        "width": size,
                        "height": size,
                        "sha256": forge.sha256_path(
                            export / f"{forge.EXPORT_PREFIX}_{suffix}"
                        ),
                    }
                    for suffix in suffixes
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "provenance.json").write_text(
        json.dumps(
            {
                "family": "aged_mountain_asphalt",
                "variant": "base",
                "semantic_owner": forge.SEMANTIC_OWNER,
                "world_semantics_generated": False,
                "normal_convention": "DirectX",
                "local_mask_channels": {"R": "cracks", "G": "patches", "B": "variation"},
            }
        ),
        encoding="utf-8",
    )


class MaterialForgeContractTests(unittest.TestCase):
    def test_asphalt_shader_avoids_reserved_glsl_patch_identifier(self):
        self.assertNotIn("float patch =", forge.ASPHALT_FUNCTION)
        self.assertNotIn("float active =", forge.ASPHALT_FUNCTION)
        self.assertIn("float patch_mask =", forge.ASPHALT_FUNCTION)
        self.assertIn("float cell_gate =", forge.ASPHALT_FUNCTION)
        self.assertNotIn("0.012*patch;", forge.ASPHALT_FUNCTION)
        self.assertNotIn("clamp(patch,0.0,1.0)", forge.ASPHALT_FUNCTION)

    def test_visual_v3_uses_family_specific_surface_structures(self):
        self.assertEqual(forge.GENERATOR_VERSION, 3)
        self.assertIn("yacs_rect_patch", forge.ASPHALT_FUNCTION)
        self.assertIn("yacs_contour_crack", forge.ASPHALT_FUNCTION)
        self.assertNotIn("coarse_cells = yacs_cells(q,23.0", forge.ASPHALT_FUNCTION)
        self.assertIn("karst_channel", forge.LIMESTONE_FUNCTION)
        self.assertIn("pore_mask", forge.LIMESTONE_FUNCTION)
        self.assertIn("coarse_pebble", forge.SOIL_FUNCTION)
        self.assertIn("crust_crack", forge.SOIL_FUNCTION)

    def test_visual_v2_variants_are_physically_distinct(self):
        catalog = forge.load_catalog()
        by_id = {family["id"]: family for family in catalog["families"]}
        self.assertEqual(by_id["aged_mountain_asphalt"]["tile_metres"], 4.0)
        self.assertEqual(by_id["regional_limestone"]["tile_metres"], 4.0)
        self.assertEqual(by_id["mediterranean_soil"]["tile_metres"], 4.0)
        asphalt = {v["id"]: v for v in by_id["aged_mountain_asphalt"]["variants"]}
        self.assertGreater(asphalt["worn"]["surface_a"], asphalt["base"]["surface_a"])
        self.assertGreater(asphalt["repaired"]["surface_b"], asphalt["base"]["surface_b"])
        soil = {v["id"]: v for v in by_id["mediterranean_soil"]["variants"]}
        self.assertGreater(soil["stony"]["surface_a"], soil["fine"]["surface_a"])
        self.assertGreater(soil["dry_crusted"]["surface_b"], soil["fine"]["surface_b"])

        limestone = {v["id"]: v for v in by_id["regional_limestone"]["variants"]}
        self.assertIn("refined_a", limestone)
        self.assertIn("refined_a", soil)
        self.assertLess(limestone["refined_a"]["brightness"], limestone["base"]["brightness"])
        self.assertGreater(limestone["refined_a"]["surface_a"], limestone["base"]["surface_a"])
        self.assertGreater(soil["refined_a"]["surface_a"], soil["fine"]["surface_a"])
        self.assertGreater(soil["refined_a"]["surface_b"], soil["fine"]["surface_b"])
        self.assertLess(soil["refined_a"]["refinement"]["variation_scale"], 1.0)
        self.assertGreater(limestone["refined_a"]["refinement"]["crack_color_scale"], 1.0)
        self.assertNotEqual(
            forge._color_code("regional_limestone", limestone["base"]),
            forge._color_code("regional_limestone", limestone["refined_a"]),
        )
        self.assertNotEqual(
            forge._color_code("mediterranean_soil", soil["fine"]),
            forge._color_code("mediterranean_soil", soil["refined_a"]),
        )

    def test_catalog_has_three_families_and_three_variants_each(self):
        catalog = forge.load_catalog()
        self.assertEqual(len(catalog["families"]), 3)
        self.assertTrue(all(len(f["variants"]) >= 3 for f in catalog["families"]))

    def test_validator_accepts_periodic_nonmetallic_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _variant_fixture(root)
            result = forge.check_variant(root, expected_resolution=64)
            self.assertEqual(result["status"], "MAP_CHECKS_PASS_UE_REVIEW_PENDING")
            self.assertEqual(result["semantic_owner"], "PCG/PCGEx")
            self.assertFalse(result["world_semantics_generated"])

    def test_validator_requires_native_decode_evidence(self):
        for failure in ("missing", "invalid", "missing_height", "wrong_height_size"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _variant_fixture(root)
                native = root / "export" / f"{forge.EXPORT_PREFIX}_native-check.json"
                receipt = json.loads(native.read_text())
                if failure == "missing":
                    native.unlink()
                else:
                    if failure == "invalid":
                        receipt["valid"] = "true"
                    elif failure == "missing_height":
                        del receipt["images"]["Height.exr"]
                    else:
                        receipt["images"]["Height.exr"]["width"] = 32
                    native.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    forge.check_variant(root, expected_resolution=64)
                self.assertFalse((root / "validation.json").exists())

    def test_validator_rejects_stale_native_decode_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _variant_fixture(root)
            height = root / "export" / f"{forge.EXPORT_PREFIX}_Height.exr"
            height.write_bytes(height.read_bytes() + b"changed-after-native-decode")
            with self.assertRaisesRegex(ValueError, "Native decode hash mismatch"):
                forge.check_variant(root, expected_resolution=64)
            self.assertFalse((root / "validation.json").exists())

    def test_validator_rejects_semantic_ownership_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _variant_fixture(root)
            provenance = json.loads((root / "provenance.json").read_text())
            provenance["semantic_owner"] = "Material Forge"
            (root / "provenance.json").write_text(json.dumps(provenance))
            with self.assertRaisesRegex(ValueError, "world semantics"):
                forge.check_variant(root, expected_resolution=64)

    def test_world_mask_packer_preserves_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {"R": 11, "G": 77, "B": 143, "A": 231}
            channels = {}
            for channel, value in values.items():
                path = root / f"{channel}.png"
                _png(path, np.full((8, 8), value, dtype=np.uint8))
                channels[channel] = {"name": f"Mask{channel}", "path": str(path)}
            spec = root / "spec.json"
            spec.write_text(
                json.dumps(
                    {
                        "semantic_owner": "PCG/PCGEx",
                        "operation": "pack_only",
                        "channels": channels,
                    }
                )
            )
            output = root / "packed.png"
            manifest = root / "packed.json"
            result = forge.pack_world_masks(spec, output, manifest)
            rgba = np.asarray(Image.open(output).convert("RGBA"))
            for index, channel in enumerate(("R", "G", "B", "A")):
                self.assertTrue(np.all(rgba[..., index] == values[channel]))
            self.assertFalse(result["classification_changed"])

    def test_world_mask_packer_rejects_reclassification_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "R.png"
            _png(path, np.zeros((4, 4), dtype=np.uint8))
            spec = root / "spec.json"
            spec.write_text(
                json.dumps(
                    {
                        "semantic_owner": "Material Forge",
                        "operation": "pack_only",
                        "channels": {
                            "R": {"name": "Rock", "path": str(path)},
                            "G": {"name": "Rock", "path": str(path)},
                            "B": {"name": "Rock", "path": str(path)},
                            "A": {"name": "Rock", "path": str(path)},
                        },
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "PCG/PCGEx"):
                forge.pack_world_masks(spec, root / "packed.png", root / "manifest.json")

    def test_compare_detects_output_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.json"
            right = root / "right.json"
            common = {
                "variants": [
                    {
                        "family": "regional_limestone",
                        "variant": "base",
                        "graph_sha256": "a",
                        "fingerprint": "b",
                    }
                ],
                "validations": [
                    {
                        "family": "regional_limestone",
                        "variant": "base",
                        "maps": {"BaseColor": "c"},
                    }
                ],
            }
            left.write_text(json.dumps(common))
            changed = json.loads(json.dumps(common))
            changed["validations"][0]["maps"]["BaseColor"] = "d"
            right.write_text(json.dumps(changed))
            result = forge.compare_run_manifests(left, right)
            self.assertFalse(result["deterministic"])
            self.assertEqual(len(result["mismatches"]), 1)

    def test_derived_material_mask_is_gated_by_authoritative_world_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            world = root / "world.png"
            detail = root / "detail.png"
            world_data = np.zeros((4, 4), dtype=np.uint8)
            world_data[:, 2:] = 255
            detail_data = np.full((4, 4, 3), 200, dtype=np.uint8)
            _png(world, world_data)
            _png(detail, detail_data)
            spec = root / "derive.json"
            spec.write_text(
                json.dumps(
                    {
                        "semantic_owner": "PCG/PCGEx",
                        "operation": "modulate_detail_only",
                        "world_mask": {"name": "Road", "path": str(world)},
                        "detail_mask": {"path": str(detail)},
                    }
                )
            )
            output = root / "derived.png"
            manifest = root / "derived.json"
            result = forge.derive_material_mask(spec, output, manifest)
            derived = np.asarray(Image.open(output).convert("RGB"))
            self.assertTrue(np.all(derived[:, :2] == 0))
            self.assertTrue(np.all(derived[:, 2:] == 200))
            self.assertFalse(result["classification_changed"])

    def test_rebuild_plan_is_stable_when_source_fingerprint_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fingerprint = forge.source_fingerprint()
            (root / "run-manifest.json").write_text(
                json.dumps({"source_fingerprint": fingerprint})
            )
            result = forge.plan_rebuild(root)
            self.assertFalse(result["rebuild_required"])
            self.assertEqual(result["reason"], "unchanged")


if __name__ == "__main__":
    unittest.main()
