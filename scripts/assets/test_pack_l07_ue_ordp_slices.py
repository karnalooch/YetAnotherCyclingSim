"""Unit tests for 5-slot 2K CC0 ORDp slice packer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MOD_PATH = Path(__file__).with_name("pack_l07_ue_ordp_slices.py")
spec = importlib.util.spec_from_file_location("pack_l07_ue_ordp_slices", MOD_PATH)
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)


class PackOrdpSlicesTests(unittest.TestCase):
    def test_expected_slot_order_matches_owner_selection(self):
        self.assertEqual(
            packer.EXPECTED_SLOTS,
            (
                (0, "mossy_rock"),
                (1, "sparse_grass"),
                (2, "gravel_floor_02"),
                (3, "dark_rock_02"),
                (4, "coast_sand_rocks_02"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
