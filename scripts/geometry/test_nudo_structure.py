"""Protect the opening, structural depth and owner-bounded replacement receipt."""

import unittest

from scripts.geometry.network_pavement import shoulder_sections
from scripts.geometry.nudo_structure import build_nudo_support, inspect_underpass


class NudoStructureTests(unittest.TestCase):
    def geometry(self, deck=7.5):
        rows = [
            [[x / 4, j * 5 / 24 - 2.5, deck] for j in range(25)] for x in range(-40, 41)
        ]
        design = {
            "center_xy_m": [0, 0],
            "lower_direction_xy": [0, 1],
            "opening_half_width_m": 3.5,
            "lower_height_m": 0,
            "spring_height_m": 2.5,
            "arch_rise_m": 3.5,
            "upper_domain_station_m": 80,
        }
        return shoulder_sections(rows), design

    def test_actual_mesh_leaves_full_road_width_open(self):
        rows, design = self.geometry()
        v, t, proof = build_nudo_support(rows, [[0, 0]] * len(rows), 0, design)
        clearance = inspect_underpass(v, t, design)
        self.assertGreater(clearance["minimum_clearance_m"], 4.9)
        self.assertGreater(proof["arch_soffit_triangle_count"], 0)
        self.assertGreater(proof["minimum_arch_depth_m"], 1.4)

    def test_insufficient_structural_depth_fails(self):
        rows, design = self.geometry(6.2)
        with self.assertRaisesRegex(ValueError, "structural depth"):
            build_nudo_support(rows, [[0, 0]] * len(rows), 0, design)

    def test_solid_support_cannot_masquerade_as_an_open_arch(self):
        rows, design = self.geometry()
        v, t, _ = build_nudo_support(rows, [[0, 0]] * len(rows), 100, design)
        # A solid transverse wall across the opening blocks the low envelope.
        start = len(v)
        v.extend([[-3, -2, 2], [3, -2, 2], [3, 2, 2], [-3, 2, 2]])
        t.extend([(start, start + 1, start + 2), (start, start + 2, start + 3)])
        with self.assertRaisesRegex(ValueError, "clearance failed"):
            inspect_underpass(v, t, design)


if __name__ == "__main__":
    unittest.main()
