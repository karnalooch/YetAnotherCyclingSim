from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import rasterio
from rasterio.transform import from_origin

from prepare_region_terrain import (
    DEFAULT_PROFILE,
    encode_heights,
    load_profile,
    prepare,
    read_native_window,
    sha256,
)


class RegionTerrainTests(unittest.TestCase):
    def test_profile_contains_coll_and_native_grid(self):
        profile = load_profile(DEFAULT_PROFILE)
        west, south, east, north = profile["baseline_bounds_m"]
        self.assertLess(west, 484435.405)
        self.assertGreater(east, 484435.405)
        self.assertLess(south, 4408629.130)
        self.assertGreater(north, 4408629.130)
        self.assertEqual(profile["source_crs"], "EPSG:25831")

    def test_nodata_and_nonfinite_fail_before_encoding(self):
        for heights in (
            np.ma.array([[1.0, 2.0]], mask=[[0, 1]]),
            np.ma.array([[1.0, np.nan]]),
            np.ma.array([[1.0, np.inf]]),
        ):
            with self.subTest(heights=heights), self.assertRaises(ValueError):
                encode_heights(heights)

    def test_legacy_converter_cannot_fill_missing_ground_with_median(self):
        from prepare_passo_giau_heightmap import fill_masked_nearest_reasonable

        with self.assertRaisesRegex(ValueError, "NoData"):
            fill_masked_nearest_reasonable(
                np.ma.array([[10.0, 20.0]], mask=[[0, 1]]), 15.0
            )
        with self.assertRaisesRegex(ValueError, "non-finite"):
            fill_masked_nearest_reasonable(np.ma.array([[10.0, np.nan]]), 15.0)

    def test_exact_unreal_inverse_preserves_sea_level_and_extrema(self):
        values = np.ma.array([[-1.3, 0.0, 15.06], [724.19, 1000.0, 1437.158]])
        encoded, manifest = encode_heights(values)
        decoded = (encoded.astype(float) - 32768.0) / 128.0 * manifest[
            "scale_z"
        ] / 100.0 + manifest["location_z_cm"] / 100.0
        self.assertTrue(
            np.allclose(
                decoded,
                values,
                rtol=0,
                atol=manifest["max_quantization_error_m"] + 1e-9,
            )
        )
        self.assertAlmostEqual(decoded.min(), values.min())
        self.assertAlmostEqual(decoded.max(), values.max())

    def test_constant_and_implausible_terrain_fail(self):
        for values in ([[1.0, 1.0]], [[-32767.0, 15.0]], [[0.0, 10000.0]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                encode_heights(np.ma.array(values))

    def test_native_geotiff_preparation_and_fail_closed_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic.tif"
            data = np.tile(np.linspace(10.0, 800.0, 4033, dtype=np.float32), (4033, 1))
            with rasterio.open(
                source,
                "w",
                driver="GTiff",
                width=4033,
                height=4033,
                count=1,
                dtype="float32",
                crs="EPSG:25831",
                transform=from_origin(483000.0, 4409516.5, 0.5, 0.5),
                nodata=-32767.0,
            ) as dataset:
                dataset.write(data, 1)
            profile = load_profile(DEFAULT_PROFILE)
            profile.update(
                source="synthetic.tif",
                source_sha256=sha256(source),
                source_size_bytes=source.stat().st_size,
                source_bounds_m=list(profile["baseline_bounds_m"]),
            )
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile))
            output = root / "Prepared"
            manifest = prepare(profile_path, output, root)
            self.assertEqual(manifest["heightmap_bytes"], 4033 * 4033 * 2)
            self.assertEqual(manifest["origin_epsg_m"], [483000.25, 4409516.25])
            self.assertEqual(manifest["nodata_sample_count"], 0)
            self.assertFalse(manifest["resampled"])
            self.assertEqual(
                sha256(output / "terrain.r16"), manifest["heightmap_sha256"]
            )
            with self.assertRaises(FileExistsError):
                prepare(profile_path, output, root)
            with rasterio.open(source) as dataset:
                wrong = copy.deepcopy(profile)
                wrong["source_crs"] = "EPSG:32632"
                with self.assertRaisesRegex(ValueError, "CRS mismatch"):
                    read_native_window(dataset, wrong)
                wrong = copy.deepcopy(profile)
                wrong["source_nodata"] = -9999.0
                with self.assertRaisesRegex(ValueError, "NoData sentinel"):
                    read_native_window(dataset, wrong)
                wrong = copy.deepcopy(profile)
                wrong["baseline_bounds_m"][0] += 0.25
                with self.assertRaisesRegex(ValueError, "aligned"):
                    read_native_window(dataset, wrong)
            profile["source_sha256"] = "0" * 64
            profile_path.write_text(json.dumps(profile))
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                prepare(profile_path, root / "Bad", root)
            self.assertFalse((root / "Bad").exists())


if __name__ == "__main__":
    unittest.main()
