"""Independent synthetic regressions for bounded shoulder-only endpoint repair."""

import copy
import math
import unittest

from scripts.geometry.network_shoulder_joints import (
    MAX_MOVE_M, fingerprint, repair_shoulder_joints,
)


def curved_window(name, angles):
    rows = []
    for t in angles:
        c = [20 * math.sin(t), 20 * (1 - math.cos(t))]
        normal = [-math.sin(t), math.cos(t)]
        row = []
        for j in range(25):
            u = (j - 12) * 5 / 24
            row.append([c[0] + u * normal[0], c[1] + u * normal[1], 100 + .02 * u])
        rows.append(row)
    return {"id": name, "sections": rows}


def independent_support(rows):
    """Analytic fixture, not a copy of the repair's miter computation."""
    result = []
    for i, row in enumerate(rows):
        section = [None, *[[x, y, z - .08] for x, y, z in row], None]
        for side in (0, -1):
            p = row[side]
            adjacent = rows[1 if i == 0 else i - 1][side]
            dx, dy = adjacent[0] - p[0], adjacent[1] - p[1]
            normal = [-dy, dx]
            if normal[0] * (p[0] - row[12][0]) + normal[1] * (p[1] - row[12][1]) < 0:
                normal = [-n for n in normal]
            d = math.hypot(*normal)
            xy = [p[k] + .5 * normal[k] / d for k in (0, 1)]
            a, b = row[0], row[-1]
            vx, vy = b[0] - a[0], b[1] - a[1]
            u = ((xy[0] - a[0]) * vx + (xy[1] - a[1]) * vy) / (vx * vx + vy * vy)
            section[side] = [*xy, a[2] + u * (b[2] - a[2]) - .08]
        result.append(section)
    return result


class ShoulderJointTests(unittest.TestCase):
    def setUp(self):
        self.windows = [curved_window("a", [-.04, -.02, 0]),
                        curved_window("b", [0, .02, .04])]
        self.supports = {w["id"]: independent_support(w["sections"])
                         for w in self.windows}

    def run_repair(self, **kwargs):
        return repair_shoulder_joints(self.windows, self.supports, **kwargs)

    def test_real_offset_discontinuity_repaired_without_moving_pavement(self):
        w, s = copy.deepcopy(self.windows), copy.deepcopy(self.supports)
        out, report = self.run_repair()
        joint = report["joints"][0]
        self.assertGreater(joint["before_gap_max_m"], .005)
        self.assertEqual(joint["status"], "CANDIDATE_REPAIRED")
        self.assertEqual(joint["after_gap_max_m"], 0)
        self.assertLess(joint["max_move_m"], MAX_MOVE_M)
        self.assertEqual(w, self.windows)
        self.assertEqual(s, self.supports)
        for name in out:
            for old, new in zip(s[name], out[name]):
                self.assertEqual(old[1:-1], new[1:-1])
        self.assertEqual(out["a"][-1][0], out["b"][0][0])
        self.assertEqual(out["a"][-1][-1], out["b"][0][-1])
        self.assertFalse(report["native_contact_verified"])

    def test_idempotent_and_input_order_independent(self):
        out, report = self.run_repair()
        again, _ = repair_shoulder_joints(self.windows, out)
        swapped, _ = repair_shoulder_joints(self.windows[::-1], self.supports)
        self.assertEqual(fingerprint(out), fingerprint(again))
        self.assertEqual(fingerprint(out), fingerprint(swapped))

    def test_protected_boundary_is_never_repaired(self):
        out, report = self.run_repair(protected_ids=["a"])
        self.assertEqual(out, self.supports)
        self.assertEqual(report["joints"][0]["status"], "PROTECTED_UNCHANGED")

    def test_nearby_but_distinct_or_grade_separated_endpoints_not_joined(self):
        for offset in ([.01, 0, 0], [0, 0, 3]):
            windows = copy.deepcopy(self.windows)
            for row in windows[1]["sections"]:
                for p in row:
                    for k in range(3):
                        p[k] += offset[k]
            supports = {w["id"]: independent_support(w["sections"]) for w in windows}
            out, report = repair_shoulder_joints(windows, supports)
            self.assertEqual(report["joint_count"], 0)
            self.assertEqual(out, supports)

    def test_same_center_different_width_not_a_join(self):
        windows = copy.deepcopy(self.windows)
        for row in windows[1]["sections"]:
            for p in row:
                p[1] = row[12][1] + 1.1 * (p[1] - row[12][1])
        supports = {w["id"]: independent_support(w["sections"]) for w in windows}
        _, report = repair_shoulder_joints(windows, supports)
        self.assertEqual(report["joint_count"], 0)

    def test_reversed_digitization_uses_corresponding_physical_edge(self):
        self.windows[1]["sections"] = [r[::-1] for r in self.windows[1]["sections"][::-1]]
        self.supports["b"] = independent_support(self.windows[1]["sections"])
        out, report = self.run_repair()
        j = report["joints"][0]
        self.assertTrue(j["reversed_cross_section"])
        self.assertEqual(j["status"], "CANDIDATE_REPAIRED")
        self.assertEqual(out["a"][-1][0], out["b"][-1][-1])

    def test_sharp_corner_is_reported_not_welded_beyond_budget(self):
        self.windows[1] = curved_window("b", [0, .3, .6])
        self.supports["b"] = independent_support(self.windows[1]["sections"])
        out, report = self.run_repair()
        self.assertEqual(out, self.supports)
        self.assertEqual(report["joints"][0]["status"], "REVIEW_REQUIRED")

    def test_ambiguous_three_way_junction_not_welded(self):
        extra = copy.deepcopy(self.windows[1])
        extra["id"] = "c"
        self.windows.append(extra)
        self.supports["c"] = copy.deepcopy(self.supports["b"])
        out, report = self.run_repair()
        self.assertEqual(out, self.supports)
        self.assertTrue(all(j["status"] == "REVIEW_REQUIRED" for j in report["joints"]))

    def test_duplicate_missing_support_and_unknown_protected_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            repair_shoulder_joints(self.windows + self.windows[:1], self.supports)
        with self.assertRaisesRegex(ValueError, "identity"):
            repair_shoulder_joints(self.windows, {"a": self.supports["a"]})
        with self.assertRaisesRegex(ValueError, "protected"):
            self.run_repair(protected_ids=["not-on-this-road"])

    def test_nonfinite_or_incorrect_interior_rejected(self):
        for value in (float("nan"), float("inf"), True):
            bad = copy.deepcopy(self.supports)
            bad["a"][0][0][0] = value
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                repair_shoulder_joints(self.windows, bad)
        bad = copy.deepcopy(self.supports)
        bad["a"][0][10][0] += .01
        with self.assertRaisesRegex(ValueError, "interior"):
            repair_shoulder_joints(self.windows, bad)

    def test_zero_width_and_malformed_sections_rejected(self):
        w = copy.deepcopy(self.windows)
        w[0]["sections"][0] = w[0]["sections"][0][:-1]
        with self.assertRaisesRegex(ValueError, "shape"):
            repair_shoulder_joints(w, self.supports)

    def test_changed_candidate_does_not_modify_independent_other_window(self):
        extra = curved_window("distant", [.3, .32, .34])
        self.windows.append(extra)
        self.supports["distant"] = independent_support(extra["sections"])
        out, _ = self.run_repair()
        self.assertEqual(out["distant"], self.supports["distant"])


if __name__ == "__main__":
    unittest.main()
