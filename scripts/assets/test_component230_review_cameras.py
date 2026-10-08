"""Camera samples must come from source pavement, never invented positions."""
import unittest
import numpy as np
from scripts.assets.prepare_sa_calobra_component230_cliff_visual import review_cameras


class ReviewCameraTests(unittest.TestCase):
    def test_anchors_are_source_pavement_and_focus_is_admitted(self):
        reasons = np.zeros((100, 150), dtype=np.uint8)
        reasons[10, 10:140] = 1
        reasons[11, 10:140] = 2  # shoulders cannot become pavement anchors
        plan = {'skin_cells': [{'row0': 20, 'row1': 22, 'col0': 30, 'col1': 32}]}
        views = review_cameras(reasons, plan)
        self.assertEqual([v['name'] for v in views], ['close', 'middle', 'distant'])
        for v in views:
            row, col = v['pavement_source_rc']
            self.assertEqual(int(reasons[row, col]) & 1, 1)
            self.assertEqual(v['eye_xy_m'], [col * .5, row * .5])
            self.assertEqual(v['target_xy_m'], [15.5, 10.5])
        self.assertEqual(views, review_cameras(reasons.copy(), plan))

    def test_missing_pavement_cannot_fabricate_review(self):
        with self.assertRaises(ValueError):
            review_cameras(np.full((5, 5), 2, dtype=np.uint8),
                           {'skin_cells': [{'row0': 0, 'row1': 2, 'col0': 0, 'col1': 2}]})
