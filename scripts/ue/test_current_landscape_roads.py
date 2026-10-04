"""Exercise full-context native orchestration without an Unreal installation."""

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from scripts.geometry.network_visual_preview import validate_full_preview


def network_fixture():
    preview = {
        "schema_version": 1,
        "role": "VISUAL_REVIEW_ONLY",
        "road_admitted": False,
        "height_change_applied": False,
        "terrain_change_applied": False,
        "source_markers": [
            {
                "id": "source",
                "xy_local_m": [[0, 0], [1, 0], [2, 0]],
                "ground_m": [0, 0, 0],
                "length_m": 2,
            }
        ],
        "rejected_surfaces": [
            {
                "id": "conflict",
                "reason": "CUT > 1 m",
                "road_admitted": False,
                "sections": [[[x, j / 5, 1.5] for j in range(25)] for x in (0, 1, 2)],
            }
        ],
    }
    return {
        "full_preview": preview,
        "source_clipped_length_m": 2,
        "full_preview_proof": validate_full_preview(preview, 2),
    }


class NativeFullContextTests(unittest.TestCase):
    def load_consumer(self):
        spawn = Mock(side_effect=lambda *args: (Mock(), Mock()))
        spec = importlib.util.spec_from_file_location(
            "_network_preview_consumer",
            Path(__file__).with_name("current_landscape_roads.py"),
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules,
            {
                "unreal": SimpleNamespace(LinearColor=lambda *args: args),
                "scripts.ue.ma2141_road_preview": SimpleNamespace(
                    spawn_pavement_mesh=spawn
                ),
            },
        ):
            spec.loader.exec_module(module)
        return module, spawn

    def test_full_context_preserves_rejected_height_and_retraces_marker_ground(self):
        module, spawn = self.load_consumer()
        network = network_fixture()
        original = copy.deepcopy(network)
        module.trace = Mock(return_value=-0.5)
        module.build_vertical_support = Mock(
            side_effect=AssertionError("Rejected context must not construct supports")
        )
        kept, proof = module.spawn_full_visual_context(object(), network)
        self.assertEqual(network, original)
        self.assertEqual(len(kept), 2)
        self.assertEqual(spawn.call_count, 2)
        # Exact rejected slab top remains at 1.5 m; only annotation gets the 0.2 m offset.
        self.assertEqual(spawn.call_args_list[0].args[1][0][2], 1.5)
        self.assertAlmostEqual(spawn.call_args_list[1].args[1][0][2], -0.3)
        self.assertEqual(module.trace.call_count, 3)
        self.assertEqual(proof["rendered_source_marker_count"], 1)
        self.assertEqual(proof["rendered_rejected_surface_count"], 1)
        self.assertFalse(proof["road_admitted"])
        self.assertFalse(proof["collision_admitted"])
        self.assertFalse(proof["terrain_change_applied"])

    def test_stale_receipt_fails_before_spawning_or_tracing(self):
        module, spawn = self.load_consumer()
        network = network_fixture()
        network["full_preview"]["rejected_surfaces"][0]["sections"][0][0][2] += 0.1
        module.trace = Mock()
        with self.assertRaisesRegex(RuntimeError, "geometry changed"):
            module.spawn_full_visual_context(object(), network)
        spawn.assert_not_called()
        module.trace.assert_not_called()

    def test_missing_native_ground_fails_instead_of_reporting_render_complete(self):
        module, spawn = self.load_consumer()
        module.trace = Mock(side_effect=RuntimeError("Network Landscape trace missed"))
        with self.assertRaisesRegex(RuntimeError, "trace missed"):
            module.spawn_full_visual_context(object(), network_fixture())
        self.assertEqual(spawn.call_count, 1)

    def test_adopted_context_does_not_overlay_red_or_shifted_diagnostic_slabs(self):
        module, spawn = self.load_consumer()
        network = network_fixture()
        network["owner_reviewed"] = [{"id": "reviewed-conflict"}]
        module.trace = Mock(return_value=0)
        # Receipt validation is tested independently with altered coordinates.
        module.construction_windows = Mock(return_value=network["owner_reviewed"])
        kept, proof = module.spawn_full_visual_context(object(), network)
        self.assertEqual(len(kept), 1)  # The source-location annotation only.
        self.assertEqual(proof["rendered_rejected_surface_count"], 0)
        self.assertEqual(proof["rendered_reviewed_surface_count"], 1)
        self.assertEqual(proof["material"], "ASPHALT")
        self.assertTrue(proof["terrain_change_applied"])
        self.assertEqual(module.spawn_extreme_cut_diagnostic(object(), network), [])
        self.assertEqual(spawn.call_count, 1)


if __name__ == "__main__":
    unittest.main()
