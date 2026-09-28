"""Unit tests for deterministic YACS scene layout planning."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "worldgen" / "yacs_scene_layout.py"

SPEC = importlib.util.spec_from_file_location("yacs_scene_layout", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load yacs_scene_layout")
LAYOUT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAYOUT
SPEC.loader.exec_module(LAYOUT)


class YacsSceneLayoutTests(unittest.TestCase):
    def test_grove_is_deterministic(self) -> None:
        kwargs = {
            "size_x_m": 10.0,
            "size_y_m": 10.0,
            "tree_count": 14,
            "seed": 42017,
            "irregularity": 0.82,
        }
        first = LAYOUT.plan_clustered_forest_patch(**kwargs)
        second = LAYOUT.plan_clustered_forest_patch(**kwargs)
        self.assertEqual(first, second)

    def test_grove_stays_inside_bounds_and_spacing(self) -> None:
        placements = LAYOUT.plan_clustered_forest_patch(
            size_x_m=10.0,
            size_y_m=10.0,
            tree_count=16,
            seed=42,
            min_spacing_m=0.85,
            edge_margin_m=0.35,
        )

        self.assertEqual(len(placements), 16)
        for item in placements:
            self.assertLessEqual(abs(item.x_m), 4.65)
            self.assertLessEqual(abs(item.y_m), 4.65)
            self.assertGreaterEqual(item.uniform_scale, 0.82)
            self.assertLessEqual(item.uniform_scale, 1.22)

        self.assertGreaterEqual(
            LAYOUT.minimum_pair_distance_m(placements),
            0.85 - 1e-6,
        )

    def test_view_corridor_exclusion_is_respected(self) -> None:
        exclusion = LAYOUT.RectExclusion(
            center_x_m=0.0,
            center_y_m=-2.0,
            width_m=3.0,
            height_m=3.0,
        )
        placements = LAYOUT.plan_clustered_forest_patch(
            size_x_m=10.0,
            size_y_m=10.0,
            tree_count=12,
            seed=123,
            exclusions=[exclusion],
        )
        self.assertFalse(
            any(exclusion.contains(item.x_m, item.y_m) for item in placements)
        )

    def test_different_seed_changes_layout(self) -> None:
        first = LAYOUT.plan_clustered_forest_patch(
            size_x_m=10.0,
            size_y_m=10.0,
            tree_count=12,
            seed=1,
        )
        second = LAYOUT.plan_clustered_forest_patch(
            size_x_m=10.0,
            size_y_m=10.0,
            tree_count=12,
            seed=2,
        )
        self.assertNotEqual(first, second)

    def test_invalid_patch_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LAYOUT.plan_clustered_forest_patch(
                size_x_m=1.0,
                size_y_m=1.0,
                tree_count=12,
                seed=1,
                edge_margin_m=0.6,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
