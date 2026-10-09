"""Run the actual native-consumer function bodies with a CPU-only trace double."""

import ast
import copy
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.geometry.test_network_shoulder_joints import curved_window


def functions(path, names, globals_dict):
    tree = ast.parse(path.read_text())
    bodies = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in bodies} != set(names):
        raise AssertionError("Native consumer function inventory changed")
    exec(compile(ast.Module(body=bodies, type_ignores=[]), str(path), "exec"), globals_dict)
    return globals_dict


class NativeJointConsumerTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2]
        self.calls = []
        self.built = []
        self.windows = [curved_window("a", [-.04, -.02, 0]),
                        curved_window("b", [0, .02, .04])]
        for w in self.windows:
            w.update(length_m=1.0, surface_inspection={"status": "PASS"})
        self.network = {"construction": self.windows}

        def trace(world, point):
            self.calls.append(list(point))
            return point[2] - .1

        def build(support, ground):
            self.built.append(copy.deepcopy(support))
            return [], [], {"min_shoulder_extent_m": .5, "max_shoulder_extent_m": .501,
                            "max_wall_height_m": .1}

        g = {"math": math, "trace": trace, "build_vertical_support": build,
             "construction_windows": lambda n: n["construction"],
             "validate_slab": lambda sections: None,
             "review_surface": lambda sections: {"status": "PASS"},
             "width_review": lambda sections, connection: {"status": "PASS"},
             "PREVIEW_SUPPORT_CAP_M": 7.0,
             "pavement_slab": lambda sections: ([], []),
             "spawn_pavement_mesh": lambda *args: (Mock(), Mock()),
             "unreal": SimpleNamespace(LinearColor=lambda *values: values)}
        functions(root / "scripts/geometry/network_pavement.py", ["shoulder_sections"], g)
        self.g = functions(root / "scripts/ue/current_landscape_roads.py",
                           ["prepare_shared_shoulders", "selected_shoulder_sections", "render_window"], g)

    def test_native_loop_traces_changed_points_before_wall_construction(self):
        self.g["prepare_shared_shoulders"](self.network)
        expected = copy.deepcopy(self.network["shared_shoulder_sections"]["a"])
        _, report = self.g["render_window"](object(), self.windows[0], self.network)
        self.assertEqual(self.built, [expected])
        self.assertEqual(self.calls[-6:], [p for r in expected for p in (r[0], r[-1])])
        self.assertEqual(report["trace_miss_count"], 0)
        self.assertEqual(report["shoulder_penetration_count"], 0)
        self.assertEqual(report["trace_count"], 3 * 27)
        self.assertFalse(self.network["shoulder_joint_repair"]["native_contact_verified"])

    def test_stale_pavement_is_rejected(self):
        self.g["prepare_shared_shoulders"](self.network)
        self.windows[0]["sections"][0][12][2] += .01
        with self.assertRaisesRegex(RuntimeError, "source changed"):
            self.g["selected_shoulder_sections"](self.windows[0], self.network)

    def test_tampered_support_is_rejected(self):
        self.g["prepare_shared_shoulders"](self.network)
        self.network["shared_shoulder_sections"]["a"][-1][0][0] += .01
        with self.assertRaisesRegex(RuntimeError, "geometry changed"):
            self.g["selected_shoulder_sections"](self.windows[0], self.network)

    def test_missing_plan_keeps_existing_single_window_behavior(self):
        result = self.g["selected_shoulder_sections"](self.windows[0], {})
        self.assertEqual(result, self.g["shoulder_sections"](self.windows[0]["sections"]))

    def test_protected_nudo_keeps_both_sides_unchanged(self):
        self.windows[1]["nudo_structure"] = True
        original = {w["id"]: self.g["shoulder_sections"](w["sections"]) for w in self.windows}
        self.g["prepare_shared_shoulders"](self.network)
        self.assertEqual(original, self.network["shared_shoulder_sections"])

    def test_native_penetration_remains_red_review(self):
        self.g["prepare_shared_shoulders"](self.network)
        new_outer = self.network["shared_shoulder_sections"]["a"][-1][0]
        self.g["trace"] = lambda world, p: p[2] + (.02 if list(p) == new_outer else -.1)
        _, report = self.g["render_window"](object(), self.windows[0], self.network)
        self.assertEqual(report["shoulder_penetration_count"], 1)
        self.assertTrue(report["visual_review_required"])
        self.assertEqual(report["pavement_material"], "REVIEW_RED")

    def test_rejected_support_retains_original_review_path(self):
        original = self.g["shoulder_sections"]
        self.g["shoulder_sections"] = Mock(side_effect=ValueError("Shoulder miter unbounded"))
        self.g["prepare_shared_shoulders"](self.network)
        self.assertEqual(self.network["shared_shoulder_sections"], {})
        self.assertEqual(set(self.network["shoulder_joint_repair"]["excluded_window_reasons"]), {"a", "b"})
        self.g["shoulder_sections"] = original


if __name__ == "__main__":
    unittest.main()
