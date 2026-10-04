"""Keep historical area shares distinct from current pixel classification."""

import unittest

import numpy as np

from scripts.assets.prepare_sa_calobra_land_cover_baseline import (
    NODATA,
    cover_lookup,
    indexed_weights,
)


class LandCoverBaselineTests(unittest.TestCase):
    def setUp(self):
        self.features = [
            {
                "properties": {
                    "OBJECTID": 42,
                    "SUP_HA": 10,
                    "MATORRAL": "5.5",
                    "FRONDOSAS_PERENNIFOLIAS": "4",
                    "AFLORA_ROCOSO_Y_ROQUEDO": "0.5",
                }
            }
        ]

    def test_full_provider_area_and_mixed_components_preserved(self):
        lookup = cover_lookup(self.features)
        np.testing.assert_allclose(lookup[:, 1], [0.4, 0, 0.55, 0, 0.05, 0])

    def test_unknown_and_conflict_never_become_zero_cover(self):
        index = np.array([[0, 1, 65535]], dtype=np.uint16)
        values = indexed_weights(index, cover_lookup(self.features), 2)
        np.testing.assert_allclose(values, [[NODATA, 0.55, NODATA]])

    def test_unrecognized_index_rejected(self):
        with self.assertRaises(ValueError):
            indexed_weights(np.array([[2]]), cover_lookup(self.features), 0)

    def test_duplicate_or_unsorted_identity_rejected(self):
        with self.assertRaises(ValueError):
            cover_lookup(self.features * 2)

    def test_invalid_area_rejected(self):
        for total, component in [(0, 1), (10, -1), (10, 11), (10, "nan")]:
            with self.subTest(total=total, component=component):
                self.features[0]["properties"].update(SUP_HA=total, MATORRAL=component)
                with self.assertRaises(ValueError):
                    cover_lookup(self.features)
