"""Reject malformed MVT and preserve polygon holes and cursor semantics."""

import unittest

from scripts.assets.prepare_sa_calobra_context_exclusions import (
    decode_geometry,
    packed_varints,
)


class ContextExclusionTests(unittest.TestCase):
    def test_lines_use_persistent_cursor_and_signed_deltas(self):
        lines = decode_geometry([9, 20, 20, 18, 10, 0, 0, 10, 9, 9, 9, 10, 2, 0], 2)
        self.assertEqual(list(lines.geoms[0].coords), [(10, 10), (15, 10), (15, 15)])
        self.assertEqual(list(lines.geoms[1].coords), [(10, 10), (11, 10)])

    def test_holes_remain_unmapped(self):
        # Positive exterior area in tile Y-down coordinates, negative hole.
        commands = [
            9,
            0,
            0,
            26,
            20,
            0,
            0,
            20,
            19,
            0,
            15,
            9,
            4,
            15,
            26,
            0,
            12,
            12,
            0,
            0,
            11,
            15,
        ]
        polygon = decode_geometry(commands, 3)
        self.assertAlmostEqual(polygon.area, 64)
        self.assertEqual(len(polygon.geoms[0].interiors), 1)

    def test_incomplete_commands_and_unknown_types_fail_closed(self):
        for commands, kind in [
            ([9, 2], 2),
            ([9, 0, 0, 10, 2, 0], 3),
            ([0], 2),
            ([9, 0, 0], 0),
        ]:
            with self.assertRaises(ValueError):
                decode_geometry(commands, kind)

    def test_truncated_and_oversized_varints_fail_closed(self):
        for data in [b"\x80", b"\xff\xff\xff\xff\xff\x01"]:
            with self.assertRaises(ValueError):
                packed_varints(data)


if __name__ == "__main__":
    unittest.main()
