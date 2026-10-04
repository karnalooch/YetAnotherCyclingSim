"""Verify point-grid boundaries and return-density evidence without requiring LAZ CI."""

import unittest
import tempfile
import json
from pathlib import Path
import numpy as np
from scripts.assets.prepare_sa_calobra_lidar_masks import (
    grid_indices,
    return_fraction,
    block_return_fraction,
    NODATA,
    prepare,
)
from scripts.assets.verify_sa_calobra_lidar_masks import verify


class LidarMaskTests(unittest.TestCase):
    def test_retained_output_refused_before_decoder_or_input_access(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            sentinel = path / "retained.json"
            sentinel.write_text("retained", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare(path / "missing.json", path, path)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "retained")

    def test_reader_rejects_stale_fingerprint_before_reading_rasters(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "status": "LIDAR_EVIDENCE_CANDIDATE",
                        "geometry_mutation": False,
                        "fingerprint": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Stale"):
                verify(path)

    def test_half_open_grid_boundaries_and_nonfinite_coordinates(self):
        grid = {
            "transform": [0.5, 0, 10, 0, -0.5, 20],
            "pixel_size_m": 0.5,
            "width": 2,
            "height": 2,
        }
        valid, indices = grid_indices(
            np.array([10, 10.5, 11, 10, 10, np.nan]),
            np.array([20, 19.5, 20, 19, 20.1, 20]),
            grid,
        )
        np.testing.assert_array_equal(valid, [True, True, False, False, False, False])
        np.testing.assert_array_equal(indices, [0, 3])

    def test_no_first_returns_is_unknown_not_zero_vegetation(self):
        np.testing.assert_array_equal(
            return_fraction(np.array([0, 0, 2]), np.array([0, 4, 4])), [NODATA, 0, 0.5]
        )

    def test_block_density_is_count_weighted_not_mean_of_pixel_fractions(self):
        vegetation = np.array([1, 0, 0, 0])
        first = np.array([1, 9, 0, 0])
        np.testing.assert_allclose(
            block_return_fraction(vegetation, first, (2, 2), 2), [0.1] * 4
        )

    def test_partial_edge_blocks_keep_grid_and_unknown(self):
        vegetation = np.array([1, 0, 2])
        first = np.array([1, 0, 2])
        np.testing.assert_array_equal(
            block_return_fraction(vegetation, first, (1, 3), 2), [1, 1, 1]
        )
        np.testing.assert_array_equal(
            block_return_fraction(np.zeros(3), np.zeros(3), (1, 3), 2), [NODATA] * 3
        )


if __name__ == "__main__":
    unittest.main()
