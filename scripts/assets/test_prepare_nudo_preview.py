"""Real-source Nudo joins retain exact reviewed endpoints and constant width."""

import json
import math
import unittest

from pyproj import Transformer
from shapely.geometry import box

from scripts.assets.prepare_current_landscape_roads import (
    SOURCE,
    build_full_source_markers,
)
from scripts.assets.prepare_nudo_preview import design


def interpolate_row(a, b):
    return [[x + (y - x) * j / 24 for x, y in zip(a, b)] for j in range(25)]


class NudoDesignTests(unittest.TestCase):
    def fixture(self):
        # Reviewed presentation endpoints from b9042db; these are not source Z.
        upper = [
            interpolate_row(a, b)
            for a, b in [
                (
                    [1282.3325059560573, 423.55900904334845, 676.7797070803101],
                    [1287.2128827266881, 422.471846416744, 676.7958517508928],
                ),
                (
                    [1282.2237988117347, 423.0710122996627, 676.7445186368172],
                    [1287.1041755822291, 421.9838496724458, 676.7611313574557],
                ),
            ]
        ]
        lower = [
            interpolate_row(a, b)
            for a, b in [
                (
                    [1242.7903973797713, 401.0980221794584, 665.6747139143387],
                    [1238.6626728699864, 398.2763399912379, 665.6929782822687],
                ),
                (
                    [1242.5105595453358, 401.507379852459, 665.6340206799343],
                    [1238.3782928895955, 398.69235369168206, 665.6529229782743],
                ),
            ]
        ]
        origin = [483000.25, 4409516.25]
        markers = build_full_source_markers(
            json.loads(SOURCE.read_text()),
            box(origin[0] + 10, origin[1] - 2006, origin[0] + 2006, origin[1] - 10),
            Transformer.from_crs(4326, 25831, always_xy=True).transform,
            origin,
        )
        return {
            "approved": [
                {"id": "VIAL_TR70190001287", "sections": upper},
                {"id": "VIAL_TR70190001272", "sections": lower},
            ],
            "owner_reviewed": [],
            "full_preview": {"source_markers": markers},
        }

    def test_direction_blend_cannot_shrink_width_or_move_endpoints(self):
        network = self.fixture()
        rows, structure = design(network)
        self.assertEqual(rows[0], network["approved"][0]["sections"][-1])
        self.assertEqual(rows[-1], network["approved"][1]["sections"][0])
        self.assertLess(
            max(abs(math.dist(r[0][:2], r[-1][:2]) - 5) for r in rows), 1e-8
        )
        self.assertTrue(
            all(250 < angle < 280 for angle in structure["main_bend_heading_deg"])
        )

    def test_large_width_deviation_is_reported_without_blocking_geometry(self):
        network = self.fixture()
        network["approved"][0]["sections"][-1][0][0] -= 0.4
        rows, structure = design(network)
        self.assertGreater(len(rows), 3)
        self.assertTrue(
            any("5%" in reason for reason in structure["visual_review_reasons"])
        )


if __name__ == "__main__":
    unittest.main()
