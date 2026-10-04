"""Check that uncertain heights cannot become shrub or planting authorization."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from scripts.assets.prepare_sa_calobra_vegetation_domains import domains, prepare


class VegetationDomainTests(unittest.TestCase):
    def test_mixed_high_and_low_keep_both_classes_and_height_review(self):
        counts = np.zeros((6, 1, 4), dtype=np.uint32)
        counts[1, 0, :2] = 1
        counts[3, 0, 1] = 2
        counts[4, 0, 1] = 1
        counts[0, 0, 2] = 1
        presence, flags, audit = domains(
            counts, np.array([[1, 3, 0, 0]], dtype=np.uint8)
        )
        np.testing.assert_array_equal(presence[:, 0, 1], [1, 0, 1])
        np.testing.assert_array_equal(presence[:, 0, 2], [0, 0, 0])
        np.testing.assert_array_equal(presence[:, 0, 3], [255, 255, 255])
        np.testing.assert_array_equal(flags, [[1, 7, 0, 255]])
        self.assertEqual(sum(audit["height_review_partition"].values()), 2)
        self.assertEqual(audit["height_review_partition"]["with_high"], 1)
        self.assertEqual(audit["height_review_low_overlap"], 2)

    def test_unknown_flags_are_not_counted_as_valid_review_samples(self):
        presence, flags, audit = domains(
            np.zeros((6, 1, 1), dtype=np.uint32), np.array([[255]], dtype=np.uint8)
        )
        self.assertTrue((presence == 255).all())
        self.assertEqual(flags[0, 0], 255)
        self.assertEqual(audit["height_review_cells"], 0)

    def test_retained_directory_refused_before_input_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):
                prepare(Path(folder) / "missing.json", Path(folder))


if __name__ == "__main__":
    unittest.main()
