import unittest
import numpy as np
from build_sa_calobra_route_visibility import ray_visibility


class VisibilityTests(unittest.TestCase):
    def test_ridge_hides_lower_ground(self):
        z = np.array([[0.0, 5.0, 0.0, 0.0]])
        visible = ray_visibility(z, np.array([[1.0, 2.0, 3.0, 4.0]]), 1.0)
        self.assertEqual(visible.tolist(), [[True, True, False, False]])

    def test_raised_form_can_emerge_without_marking_ground_visible(self):
        z = np.array([[0.0, 2.0, 0.0]])
        d = np.array([[1.0, 2.0, 3.0]])
        self.assertFalse(ray_visibility(z, d, 1.0)[0, 2])
        self.assertTrue(ray_visibility(z, d, 1.0, lift=3.0)[0, 2])

    def test_nodata_blocks_unknown_ray(self):
        z = np.array([[0.0, np.nan, 100.0]])
        self.assertEqual(
            ray_visibility(z, np.array([[1.0, 2.0, 3.0]]), 1.0).tolist(),
            [[True, False, False]],
        )

    def test_flat_terrain_visible_from_elevated_eye(self):
        z = np.zeros((2, 4))
        self.assertTrue(ray_visibility(z, np.array([[1.0, 2.0, 3.0, 4.0]]), 1.6).all())

    def test_each_azimuth_has_independent_horizon(self):
        z = np.array([[0.0, 5.0, 0.0], [0.0, 0.0, 0.0]])
        result = ray_visibility(z, np.array([[1.0, 2.0, 3.0]]), 1.0)
        self.assertFalse(result[0, 2])
        self.assertTrue(result[1, 2])


if __name__ == "__main__":
    unittest.main()
