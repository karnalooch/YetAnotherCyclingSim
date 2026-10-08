"""Whole-map material readiness must preserve evidence, registration and scope."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine

from scripts.assets import prepare_sa_calobra_whole_map_surface_prep as prep
from scripts.assets.sa_calobra_material_weights import compose_weights


def pixels():
    weights = np.array(
        [
            [[40, 80, 100, 16], [160, 0, 0, 0], [0, 0, 0, 73], [0, 0, 0, 0]],
            [[0, 0, 0, 0], [0, 25, 60, 80], [85, 85, 85, 255], [0, 0, 0, 0]],
            [[0, 0, 0, 0], [0, 255, 0, 0], [128, 0, 0, 0], [0, 0, 255, 64]],
        ],
        dtype=np.uint8,
    )
    available = np.full((3, 4), 255, dtype=np.uint8)
    available[0, 1:3] = 0
    available[1, 0] = 0
    reasons = np.array(
        [[0, 128, 128, 1], [128 | 8, 4 | 16, 32 | 64, 8], [2, 0, 4, 16]],
        dtype=np.uint16,
    )
    inference = np.array([[0, 1, 2, 3], [3, 0, 0, 3], [0, 0, 0, 0]], dtype=np.uint8)
    return weights, available, inference, reasons


class PixelContractTests(unittest.TestCase):
    def test_five_roles_match_existing_contract_without_rounding(self):
        weights, *_ = pixels()
        actual = prep.role_weight_numerators(weights)
        expected = np.zeros(5)
        for rgba in weights.reshape(-1, 4):
            expected += list(compose_weights(rgba.astype(float) / 255).values())
        np.testing.assert_allclose(
            list(actual.values()), expected * prep.ROLE_DENOMINATOR, atol=1e-8
        )
        self.assertEqual(sum(actual.values()), 12 * prep.ROLE_DENOMINATOR)

    def test_unknown_inferred_appearance_is_preserved_but_not_observed(self):
        values = pixels()
        originals = [array.copy() for array in values]
        prep.validate_pixel_block(*values)
        coverage = prep.block_coverage(*values)
        self.assertEqual(coverage["unknown_samples"], 3)
        self.assertEqual(coverage["inference_cells"]["neighbor_fill"], 1)
        self.assertGreater(
            coverage["role_weight_numerators"]["low_vegetation_appearance"], 0
        )
        for array, original in zip(values, originals, strict=True):
            np.testing.assert_array_equal(array, original)

    def test_water_bob_and_shoulders_keep_independent_appearance_and_holdbacks(self):
        values = pixels()
        prep.validate_pixel_block(*values)
        coverage = prep.block_coverage(*values)
        self.assertEqual(coverage["exclusion_bit_cells"]["mapped_water_holdback"], 2)
        self.assertEqual(coverage["exclusion_bit_cells"]["bob_affected_domain"], 2)
        self.assertEqual(coverage["exclusion_bit_cells"]["shoulder_envelope"], 1)
        self.assertGreater(
            coverage["role_weight_numerators"]["dry_channel_appearance"], 0
        )

    def test_protected_shared_evidence_cannot_receive_appearance(self):
        for bit in (1, 8):
            with self.subTest(bit=bit):
                weights = np.array([[[0, 0, 0, 1]]], dtype=np.uint8)
                with self.assertRaisesRegex(ValueError, "leaks"):
                    prep.validate_pixel_block(
                        weights,
                        np.array([[255]], dtype=np.uint8),
                        np.array([[3]], dtype=np.uint8),
                        np.array([[bit]], dtype=np.uint16),
                    )

    def test_invalid_unknown_inference_and_fallback_fail(self):
        for mutation, expected in (
            (lambda w, a, i, r: a.__setitem__((0, 1), 255), "unknown bit"),
            (lambda w, a, i, r: i.__setitem__((0, 1), 0), "Observed inference"),
            (lambda w, a, i, r: i.__setitem__((0, 3), 0), "Protected inference"),
            (lambda w, a, i, r: w.__setitem__((0, 2, 0), 1), "invents"),
        ):
            with self.subTest(expected=expected):
                values = pixels()
                mutation(*values)
                with self.assertRaisesRegex(ValueError, expected):
                    prep.validate_pixel_block(*values)

    def test_invalid_data_ranges_and_registration_fail(self):
        for mutation, expected in (
            (lambda w, a, i, r: r.__setitem__((0, 0), 65535), "NoData"),
            (lambda w, a, i, r: r.__setitem__((0, 0), 256), "undeclared"),
            (lambda w, a, i, r: a.__setitem__((0, 0), 127), "availability"),
            (lambda w, a, i, r: i.__setitem__((0, 0), 4), "inference kind"),
            (lambda w, a, i, r: w.__setitem__((0, 0), [100, 100, 100, 0]), "coverage"),
        ):
            with self.subTest(expected=expected):
                values = pixels()
                mutation(*values)
                with self.assertRaisesRegex(ValueError, expected):
                    prep.validate_pixel_block(*values)
        weights, available, inference, reasons = pixels()
        with self.assertRaisesRegex(ValueError, "registered"):
            prep.validate_pixel_block(weights[:, :-1], available, inference, reasons)

    def test_sector_sum_is_exact_and_invariant_to_partition(self):
        values = pixels()
        expected = prep.block_coverage(*values)
        actual = {}
        for row in range(3):
            for start, end in ((0, 3), (3, 4)):
                prep.add_coverage(
                    actual,
                    prep.block_coverage(
                        *(array[row : row + 1, start:end] for array in values)
                    ),
                )
        self.assertEqual(actual, expected)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.placement = self.root / "placement"
        self.source.mkdir()
        self.placement.mkdir()
        self.values = pixels()
        self.grid = {**prep.GRID, "height": 3, "width": 4}
        self.products = copy.deepcopy(prep.SOURCE_PRODUCTS)
        for (key, row), array in zip(
            self.products.items(), self.values[:3], strict=True
        ):
            path = self.source / row["path"]
            Image.fromarray(array).save(path)
            row.update(prep.output_row(path))
        self.reason_path = self.placement / prep.EXCLUSION_REASONS["path"]
        self.write_reasons(Affine(*self.grid["transform"]))
        self.install_manifests()

    def write_reasons(self, transform):
        with rasterio.open(
            self.reason_path,
            "w",
            driver="GTiff",
            width=4,
            height=3,
            count=1,
            dtype="uint16",
            nodata=65535,
            crs=self.grid["crs"],
            transform=transform,
        ) as dataset:
            dataset.write(self.values[3], 1)

    def install_manifests(self):
        reason = prep.output_row(self.reason_path)
        counts = prep.block_coverage(*self.values)
        placement = {
            "geometry_mutation": False,
            "status": "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS",
            "grid": self.grid,
            "world_mapping": prep.WORLD_MAPPING,
            "outputs": [
                {
                    **reason,
                    "logical_sha256": prep.sha(self.values[3].astype("<u2").tobytes()),
                }
            ],
            "counts": {
                "unknown_sample_cells": counts["unknown_samples"],
                "excluded_cells": counts["any_exclusion_cells"],
                "water_holdback_cells": counts["exclusion_bit_cells"][
                    "mapped_water_holdback"
                ],
            },
        }
        placement["fingerprint"] = prep.fingerprint(placement)
        placement_path = self.placement / prep.PLACEMENT_MANIFEST["path"]
        placement_path.write_bytes(prep.json_bytes(placement))
        placement_pin = {
            **prep.output_row(placement_path),
            "fingerprint": placement["fingerprint"],
        }
        source = {
            "geometry_mutation": False,
            "status": "PRESENTATION_VISUAL_FILL_CANDIDATE",
            "current_cover_admitted": False,
            "grid": self.grid,
            "world_mapping": prep.WORLD_MAPPING,
            "outputs": [
                {k: v for k, v in row.items() if k != "mode"}
                for row in self.products.values()
            ],
            "counts": {
                "original_unknown": counts["unknown_samples"],
                "observed": counts["inference_cells"]["observed"],
                "neighbor_filled": counts["inference_cells"]["neighbor_fill"],
                "neutral_fallback": counts["inference_cells"]["neutral_fallback"],
                "protected_road_building": counts["inference_cells"][
                    "protected_road_building"
                ],
            },
        }
        source["fingerprint"] = prep.fingerprint(source)
        (self.source / "material-input-manifest.json").write_bytes(
            prep.json_bytes(source)
        )
        self.pins = {
            "GRID": self.grid,
            "SOURCE_FINGERPRINT": source["fingerprint"],
            "SOURCE_PRODUCTS": self.products,
            "PLACEMENT_MANIFEST": placement_pin,
            "EXCLUSION_REASONS": reason,
            "SECTOR_PIXELS": 2,
        }

    def prepare(self, name="bundle"):
        # Only fixtures replace production pins; the CLI exposes no override.
        with patch.multiple(prep, **self.pins):
            return prep.prepare(self.source, self.placement, self.root / name)

    def test_complete_bundle_preserves_original_bytes_and_self_contained_inventory(
        self,
    ):
        report = self.prepare()
        bundle = self.root / "bundle"
        self.assertEqual(report["coverage"]["cells"], 12)
        self.assertEqual(report["coverage_sector_count"], 4)
        self.assertEqual(report["expected_landscape_component_count"], 1024)
        self.assertFalse(report["geometry_mutation"])
        self.assertEqual(report["demand_registration"]["whole_grid"], "U_UNREVIEWED")
        self.assertFalse(report["demand_registration"]["raster_demand_mask_generated"])
        for row in self.products.values():
            self.assertEqual(
                (bundle / row["path"]).read_bytes(),
                (self.source / row["path"]).read_bytes(),
            )
        self.assertEqual(
            (bundle / "exclusion-reasons.tif").read_bytes(),
            self.reason_path.read_bytes(),
        )
        np.testing.assert_array_equal(
            np.array(Image.open(bundle / "exclusion-reasons.png")), self.values[3]
        )
        for row in report["outputs"]:
            self.assertEqual(row, prep.output_row(bundle / row["path"]))
        self.assertEqual(
            report["fingerprint"],
            prep.fingerprint({k: v for k, v in report.items() if k != "fingerprint"}),
        )
        self.assertEqual(report["recipe_sha256"], prep.fingerprint(report["recipe"]))
        self.assertEqual(len(report["outputs"]), 9)
        self.assertEqual(
            {key for key in report["sources"]},
            {
                "material_manifest",
                "material_weights",
                "sample_availability",
                "inference_kind",
                "placement_manifest",
                "exclusion_reasons",
                "component230_mask",
            },
        )

    def test_repeated_prepare_and_source_line_endings_are_identical(self):
        first = self.prepare("first")
        path = self.source / "material-input-manifest.json"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        second = self.prepare("second")
        self.assertEqual(first, second)
        for source in sorted((self.root / "first").iterdir()):
            self.assertEqual(
                source.read_bytes(), (self.root / "second" / source.name).read_bytes()
            )

    def test_sector_footprints_preserve_half_texel_and_short_final_row(self):
        self.prepare()
        coverage = json.loads(
            (self.root / "bundle" / "sector-coverage.json").read_bytes()
        )
        self.assertEqual(coverage["sectors_across"], 2)
        self.assertEqual(coverage["sectors_down"], 2)
        self.assertEqual(
            [row["pixel_window"] for row in coverage["sectors"]],
            [[0, 0, 2, 2], [2, 0, 2, 2], [0, 2, 2, 1], [2, 2, 2, 1]],
        )
        self.assertEqual(
            coverage["sectors"][0]["world_footprint_cm"], [-25, -25, 75, 75]
        )
        self.assertEqual(
            coverage["sectors"][-1]["world_footprint_cm"], [75, 75, 175, 125]
        )
        self.assertEqual(sum(row["cells"] for row in coverage["sectors"]), 12)

    def test_existing_output_is_not_overwritten(self):
        output = self.root / "bundle"
        output.mkdir()
        (output / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual((output / "keep.txt").read_text(), "keep")

    def test_stale_image_fails_before_output_creation(self):
        path = self.source / "material-weights.png"
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.prepare()
        self.assertFalse((self.root / "bundle").exists())

    def test_missing_mandatory_placement_fails(self):
        self.reason_path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.prepare()
        self.assertFalse((self.root / "bundle").exists())

    def test_shifted_geotiff_fails_even_with_rebound_fixture_file_hash(self):
        transform = list(self.grid["transform"])
        transform[2] += 0.25
        self.write_reasons(Affine(*transform))
        self.install_manifests()
        with self.assertRaisesRegex(ValueError, "registration"):
            self.prepare()

    def test_manifest_with_recomputed_but_unpinned_fingerprint_fails(self):
        path = self.source / "material-input-manifest.json"
        value = json.loads(path.read_text())
        value["current_cover_admitted"] = True
        value["fingerprint"] = prep.fingerprint(
            {k: v for k, v in value.items() if k != "fingerprint"}
        )
        path.write_bytes(prep.json_bytes(value))
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.prepare()

    def test_manifest_record_cannot_redirect_to_unpinned_pixels(self):
        path = self.source / "material-input-manifest.json"
        value = json.loads(path.read_text())
        value["outputs"][0]["path"] = "../escape.png"
        value["fingerprint"] = prep.fingerprint(
            {k: v for k, v in value.items() if k != "fingerprint"}
        )
        path.write_bytes(prep.json_bytes(value))
        self.pins["SOURCE_FINGERPRINT"] = value["fingerprint"]
        with self.assertRaisesRegex(ValueError, "pin"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
