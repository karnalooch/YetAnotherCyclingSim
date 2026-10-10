"""Pure frozen-source contracts; these tests do not claim a native scene PASS."""

from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.proof.sa_calobra_tpp_survey import FROZEN_SHA
from scripts.ue import road_shoulder_sources as sources


def pavement(count=3, *, x_offset=0, crossfall=0.0, grade=0.0):
    return [[(x_offset + j * 0.2, -float(i), 0.08 + j * 0.2 * crossfall + i * grade)
             for j in range(25)] for i in range(count)]


def frozen_windows():
    ordinary = [{"id": f"window-{i:04d}", "sections": pavement(x_offset=i * 10)}
                for i in range(181)]
    nudo = [{"id": f"nudo-{i}", "sections": pavement(x_offset=2000 + i * 10),
             "nudo_structure": True, "station_start_m": i * 100.0}
            for i in range(3)]
    return ordinary + nudo + [{"id": "accepted-hairpin", "sections": pavement(x_offset=3000)}]


class FrozenWitnessTests(unittest.TestCase):
    def test_outer_strips_have_exact_ids_and_oriented_top_coordinates(self):
        window = {"id": "window-0112", "sections": pavement(110)}
        sections = sources._support_top_witnesses(window["sections"])
        owner = sources._owner(window, 112, sections, "ordinary")
        triangles = dict(sources.iter_expected_triangles(owner))
        self.assertEqual(len(triangles), 5668)
        self.assertEqual(triangles[0], ((-50.0, 0.0, 0.0), (0.0, 0.0, 0.0), (-50.0, -100.0, 0.0)))
        self.assertEqual(triangles[1], ((0.0, 0.0, 0.0), (0.0, -100.0, 0.0), (-50.0, -100.0, 0.0)))
        self.assertEqual(len(owner["selected_triangle_ids"]), 436)
        self.assertEqual(owner["selected_triangle_ids"][:4], (0, 1, 50, 51))
        self.assertEqual(owner["selected_triangle_ids"][-4:], (5616, 5617, 5666, 5667))
        self.assertTrue(all(tid % 52 in (0, 1, 50, 51) for tid in owner["selected_triangle_ids"]))
        self.assertEqual(owner["original_material_path"], sources.SUPPORT_MATERIAL)

    def test_nudo_uses_same_top_prefix_without_extending_into_soffit(self):
        window = {"id": "nudo", "sections": pavement(5)}
        sections = sources._support_top_witnesses(window["sections"])
        owner = sources._owner(window, 182, sections, "nudo")
        self.assertEqual(owner["top_triangle_count"], 208)
        self.assertEqual(len(owner["selected_triangle_ids"]), 16)
        self.assertEqual(max(owner["selected_triangle_ids"]), 207)
        self.assertEqual(len(list(sources.iter_expected_triangles(owner))), 208)

    def test_all_186_labels_follow_source_order_and_exclude_only_source_parapet(self):
        owners = sources._plan_owners({"windows": frozen_windows()}, {"upper_domain_station_m": 2.0})
        self.assertEqual([row["support_label"] for row in owners],
                         [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(186)])
        self.assertEqual([row["kind"] for row in owners], ["ordinary"] * 181 + ["parapet", "nudo", "nudo", "nudo", "hairpin"])
        self.assertEqual(owners[181]["window_id"], "nudo-0")
        self.assertEqual(owners[182]["window_id"], "nudo-0")
        self.assertEqual(sum(row["material_target"] for row in owners), 185)
        self.assertEqual(owners[181]["selected_triangle_ids"], ())
        self.assertEqual(owners[181]["original_material_path"], sources.PARAPET_MATERIAL)
        self.assertEqual(owners[-1]["window_id"], "accepted-hairpin")

    def test_count_or_flag_cannot_replace_source_inventory_identity(self):
        good = frozen_windows()
        cases = []
        duplicate = deepcopy(good)
        duplicate[1]["id"] = duplicate[0]["id"]
        cases.append(duplicate)
        missing = good[:-1]
        cases.append(missing)
        reordered = good[-1:] + good[:-1]
        cases.append(reordered)
        missing_parapet = deepcopy(good)
        missing_parapet[181]["nudo_structure"] = False
        cases.append(missing_parapet)
        second_parapet = deepcopy(good)
        second_parapet[182]["station_start_m"] = 0.0
        cases.append(second_parapet)
        truthy_flag = deepcopy(good)
        truthy_flag[181]["nudo_structure"] = "true"
        cases.append(truthy_flag)
        for windows in cases:
            with self.subTest(ids=[row["id"] for row in windows[-4:]]):
                with self.assertRaises(ValueError):
                    sources._plan_owners({"windows": windows}, {"upper_domain_station_m": 2.0})

    def test_existing_parapet_is_fully_witnessed_and_has_no_gravel_ids(self):
        window = {"id": "nudo", "sections": pavement(3)}
        sections = sources._support_top_witnesses(window["sections"])
        rows = sources._parapet_rows(sections, 0.0, {"upper_domain_station_m": 2.0})
        owner = sources._owner(window, 181, sections, "parapet", parapet_rows=rows)
        self.assertEqual(len(owner["parapet_vertices_cm"]), 300)
        self.assertEqual(owner["expected_triangle_count"], 592)
        self.assertEqual(owner["top_triangle_count"], 0)
        self.assertFalse(owner["material_target"])
        triangles = dict(sources.iter_expected_triangles(owner))
        self.assertEqual(triangles[0], ((-50.0, 0.0, 65.0), (-48.75, 0.0, 65.0), (-50.0, -100.0, 65.0)))
        self.assertAlmostEqual(triangles[2][0][2], 0.0)
        self.assertAlmostEqual(triangles[296][0][0], 500.0)
        self.assertEqual(len(triangles), 592)
        identity = sources.owner_identity(owner)
        self.assertEqual(identity["expected_witness_triangle_count"], 592)
        self.assertEqual(identity["selected_triangle_count"], 0)
        self.assertIn("preserved_without_material_assignment", identity["exclusion"])
        self.assertNotIn("parapet_vertices_cm", identity)

    def test_bridge_domain_is_inclusive_and_requires_three_actual_source_rows(self):
        sections = sources._support_top_witnesses(pavement(4))
        self.assertEqual(len(sources._parapet_rows(sections, 10.0, {"upper_domain_station_m": 12.0})), 3)
        self.assertEqual(sources._parapet_rows(sections, 10.0, {"upper_domain_station_m": 11.999}), [])
        self.assertEqual(sources._parapet_rows(sections, 100.0, {"upper_domain_station_m": 12.0}), [])

    def test_hairpin_taper_reproduces_source_shoulder_only_and_preserves_all_25_road_points(self):
        rows = [[((0.3 + j * 0.2) * math.cos(-i * math.pi / 6),
                  (0.3 + j * 0.2) * math.sin(-i * math.pi / 6), 0.08)
                 for j in range(25)] for i in range(7)]
        before = deepcopy(rows)
        with self.assertRaisesRegex(ValueError, "folds"):
            sources._support_top_witnesses(rows)
        sections = sources._support_top_witnesses(rows, hairpin=True)
        self.assertEqual(rows, before)
        for original, actual in zip(rows, sections, strict=True):
            self.assertEqual(actual[1:26], tuple((x, y, z - 0.08) for x, y, z in original))
        self.assertLess(min(math.dist(row[0][:2], row[1][:2]) for row in sections), 0.3)
        for _, triangle in sources.iter_expected_triangles(sources._owner(
                {"id": "accepted-hairpin", "sections": rows}, 185, sections, "hairpin")):
            self.assertLess(sources._area(*triangle), 0)

    def test_same_counts_and_labels_with_changed_coordinates_change_identity(self):
        window = {"id": "window-0112", "sections": pavement(3)}
        original = sources._owner(window, 112, sources._support_top_witnesses(window["sections"]), "ordinary")
        changed_window = deepcopy(window)
        x, y, z = changed_window["sections"][1][12]
        changed_window["sections"][1][12] = (x, y, z + 0.01)
        changed = sources._owner(changed_window, 112, sources._support_top_witnesses(changed_window["sections"]), "ordinary")
        a, b = sources.owner_identity(original), sources.owner_identity(changed)
        self.assertEqual(a["selected_triangle_ids"], b["selected_triangle_ids"])
        self.assertEqual(a["top_triangle_count"], b["top_triangle_count"])
        self.assertNotEqual(a["expected_oriented_triangles_sha256"], b["expected_oriented_triangles_sha256"])

    def test_profile_reports_signed_frozen_crossfall_and_grade_without_real_road_claim(self):
        window = {"id": "accepted-hairpin", "sections": pavement(3, crossfall=-0.04, grade=0.02)}
        result = sources.profile_diagnostic(window)
        self.assertAlmostEqual(result["edge_width_xy_m"]["min"], 4.8)
        self.assertAlmostEqual(result["edge_height_difference_m"]["first"], -0.192)
        self.assertAlmostEqual(result["signed_crossfall_ratio"]["first"], -0.04)
        self.assertAlmostEqual(result["signed_grade_ratio"]["first"], 0.02)
        self.assertEqual(result["local_xy_length_m"], 2.0)
        self.assertFalse(result["real_road_match_validated"])
        self.assertFalse(result["geometry_authored"])
        self.assertIn("source_point_24_height_minus", result["crossfall_sign"])
        lifted = deepcopy(window)
        lifted["sections"] = [[(x, y, z + 0.04) for x, y, z in row] for row in window["sections"]]
        lifted_result = sources.profile_diagnostic(lifted)
        self.assertAlmostEqual(lifted_result["signed_crossfall_ratio"]["first"], -0.04)
        self.assertAlmostEqual(lifted_result["signed_grade_ratio"]["first"], 0.02)

    def test_nonfinite_shape_direction_and_oversized_sources_fail_closed(self):
        for value in (True, "1", math.nan, math.inf):
            rows = pavement()
            rows[0][0] = (value, 0, 0)
            with self.subTest(value=value), self.assertRaises(ValueError):
                sources._support_top_witnesses(rows)
        with self.assertRaises(ValueError):
            sources._support_top_witnesses([pavement()[0]] * (sources.MAX_SECTIONS + 1))
        with self.assertRaises(ValueError):
            sources._support_top_witnesses([row[:24] for row in pavement()])
        with self.assertRaises(ValueError):
            sources._support_top_witnesses([pavement()[0]] * 3)


class NetworkProfileReportTests(unittest.TestCase):
    @staticmethod
    def owner(rows):
        window = {"id": "profile-fixture", "sections": rows}
        return sources._owner(window, 0, sources._support_top_witnesses(rows), "ordinary")

    @staticmethod
    def plan(windows=None):
        return {"source_identity": {"accepted_road_sha": FROZEN_SHA, "synthetic_fixture_only": True},
                "owners": sources._plan_owners({"windows": windows or frozen_windows()},
                                                {"upper_domain_station_m": 3.0})}

    @staticmethod
    def records(owner):
        return [dict(zip(sources.PROFILE_COLUMNS, row, strict=True)) for row in sources._profile_rows(owner)]

    def test_original_pavement_xyz_is_retained_without_reversing_support_lowering(self):
        rows = pavement(4, crossfall=0.035, grade=0.021)
        owner = self.owner(rows)
        before = deepcopy(owner)
        identity = sources.owner_identity(owner)
        actual = self.records(owner)
        self.assertEqual(owner, before)
        self.assertEqual(sources.owner_identity(owner), identity)
        self.assertNotIn("pavement_sections_m", identity)
        for index, record in enumerate(actual):
            for name, column in (("edge0_xyz_m", 0), ("center12_xyz_m", 12), ("edge24_xyz_m", 24)):
                self.assertEqual(record[name], rows[index][column])
                expected_z = (rows[index][column][2] - 0.08) * 100
                self.assertEqual(owner["sections_cm"][index][column + 1][2], expected_z)
        # Retained source snapshots cannot change through the original window.
        rows[0][0] = (100, 100, 100)
        self.assertEqual(owner, before)

    def test_each_edge_grade_uses_its_own_height_path_and_reverses_consistently(self):
        rows = [[((j - 12) * 0.2, -float(i), 100 + 0.1 * i + 0.02 * i * (j - 12) * 0.2)
                 for j in range(25)] for i in range(5)]
        original = self.records(self.owner(rows))
        reverse = self.records(self.owner([list(reversed(row)) for row in reversed(rows)]))
        for i, row in enumerate(original):
            self.assertAlmostEqual(row["edge0_grade_ratio"], 0.052)
            self.assertAlmostEqual(row["center_grade_ratio"], 0.1)
            self.assertAlmostEqual(row["edge24_grade_ratio"], 0.148)
            self.assertAlmostEqual(row["signed_crossfall_ratio"], 0.02 * i)
            self.assertEqual(row["local_station_xy_m"], float(i))
            self.assertIsNone(row["bend_support_ratio"])
            other = reverse[len(rows) - i - 1]
            self.assertAlmostEqual(other["edge0_grade_ratio"], -row["edge24_grade_ratio"])
            self.assertAlmostEqual(other["center_grade_ratio"], -row["center_grade_ratio"])
            self.assertAlmostEqual(other["edge24_grade_ratio"], -row["edge0_grade_ratio"])

    def test_curvature_sign_change_changes_bank_support_and_straight_is_undefined(self):
        rows = [[(t**3 + (j - 12) * 0.2, -t * 10.0, 100 + 0.03 * (j - 12) * 0.2)
                 for j in range(25)] for t in (-2, -1, 0, 1, 2)]
        result = self.records(self.owner(rows))
        self.assertLess(result[1]["signed_curvature_inv_m"], 0)
        self.assertGreater(result[3]["signed_curvature_inv_m"], 0)
        self.assertAlmostEqual(result[1]["bend_support_ratio"], 0.03)
        self.assertAlmostEqual(result[3]["bend_support_ratio"], -0.03)
        self.assertEqual(result[2]["signed_curvature_inv_m"], 0)
        self.assertIsNone(result[2]["bend_support_ratio"])
        self.assertIsNone(result[0]["signed_curvature_inv_m"])
        self.assertIsNone(result[-1]["signed_curvature_inv_m"])

    def test_circle_curvature_and_bank_support_survive_travel_and_edge_reversal(self):
        rows = [[((10 + j * 0.2) * math.cos(-i * 0.1),
                  (10 + j * 0.2) * math.sin(-i * 0.1), 100 + 0.2 * i + 0.03 * (j - 12) * 0.2)
                 for j in range(25)] for i in range(7)]
        original = self.records(self.owner(rows))
        reverse = self.records(self.owner([list(reversed(row)) for row in reversed(rows)]))
        for i in range(1, len(rows) - 1):
            self.assertAlmostEqual(original[i]["signed_curvature_inv_m"], -1 / 12.4)
            other = reverse[len(rows) - i - 1]
            self.assertAlmostEqual(other["signed_curvature_inv_m"], 1 / 12.4)
            self.assertAlmostEqual(other["signed_crossfall_ratio"], -original[i]["signed_crossfall_ratio"])
            self.assertAlmostEqual(other["bend_support_ratio"], original[i]["bend_support_ratio"])
            self.assertAlmostEqual(original[i]["bend_support_ratio"], 0.03)
            for name, radius in (("edge0_grade_ratio", 10), ("center_grade_ratio", 12.4),
                                 ("edge24_grade_ratio", 14.8)):
                self.assertAlmostEqual(original[i][name], 0.2 / (2 * radius * math.sin(0.05)))

    def test_full_report_covers_185_targets_excludes_parapet_and_preserves_identity_api(self):
        plan = self.plan()
        expected = [sources.owner_identity(owner) for owner in plan["owners"]]
        with patch.object(sources, "PROFILE_PAVEMENT_ROW_COUNT", 555):
            report = sources.network_profile_report(plan)
        self.assertEqual(report["material_target_count"], 185)
        self.assertEqual(report["section_count"], 555)
        self.assertEqual(report["excluded_parapet_count"], 1)
        self.assertFalse(report["real_road_match_validated"])
        self.assertFalse(report["native_geometry_observed"])
        self.assertFalse(report["authoritative_physics"])
        self.assertFalse(report["geometry_authored"])
        self.assertTrue(report["source_only"])
        self.assertNotIn("YACS_PERSIST_SUPPORT_181", [row["support_label"] for row in report["owners"]])
        for record, identity in zip(report["owners"], [row for row in expected if row["material_target"]], strict=True):
            raw = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            self.assertEqual(record["source_owner_identity_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(len(record["rows"]), record["section_count"])
        self.assertEqual(expected, [sources.owner_identity(owner) for owner in plan["owners"]])

    def test_report_rejects_missing_rows_owners_and_pavement_support_disagreement(self):
        plan = self.plan()
        with self.assertRaisesRegex(ValueError, "exact accepted road buffers"):
            sources.network_profile_report(plan)
        with patch.object(sources, "PROFILE_PAVEMENT_ROW_COUNT", 555):
            missing = deepcopy(plan)
            missing["owners"].pop()
            with self.assertRaisesRegex(ValueError, "coverage"):
                sources.network_profile_report(missing)
            changed = deepcopy(plan)
            points = [list(row) for row in changed["owners"][0]["pavement_sections_m"]]
            x, y, z = points[1][12]
            points[1][12] = (x, y, z + 0.001)
            changed["owners"][0]["pavement_sections_m"] = points
            with self.assertRaisesRegex(ValueError, "support interior"):
                sources.network_profile_report(changed)
            with patch.object(sources, "PROFILE_REPORT_MAX_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "compact serialization budget"):
                    sources.network_profile_report(plan)

    def test_exact_17125_row_inventory_fits_the_eight_mib_compact_budget(self):
        windows = frozen_windows()
        for index, window in enumerate(windows):
            count = 2401 if index == 184 else 84 if index == 0 else 80
            # Long float representations and curved, varying profiles exercise
            # the actual row budget. These remain synthetic source fixtures.
            window["sections"] = [[
                (index * 10 + i + 0.123456789 * math.sin(i * 0.123) + j * 0.2,
                 -float(i), 100.123456789 + 0.013456789 * i + 0.027654321 * j * 0.2)
                for j in range(25)] for i in range(count)]
        report = sources.network_profile_report(self.plan(windows))
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.assertEqual(sum(len(row["rows"]) for row in report["owners"]), 17125)
        self.assertLessEqual(len(encoded), 8 * 1024 * 1024)


class AuthenticatedLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.data = self.root / "data"
        self.frozen = self.data / "frozen"
        self.frozen.mkdir(parents=True)
        windows = frozen_windows()
        network = {"exact_sha": FROZEN_SHA, "approved": windows[:181], "owner_reviewed": [],
                   "nudo": {"windows": windows[181:184], "structure": {"upper_domain_station_m": 2.0}}}
        native = {"exact_sha": FROZEN_SHA, "construction_window_count": 184,
                  "windows": [{"id": row["id"]} for row in windows[:-1]]}
        profile = {"exact_sha": FROZEN_SHA, "stations": [
            {"xy_local_m": [[x, y] for x, y, _ in row], "candidate_ground_m": [z - 0.04 for _, _, z in row]}
            for row in windows[-1]["sections"]]}
        inputs = []
        for name, document in (("Network/network.json", network), ("network-native-proof.json", native),
                               ("ma2141-profile-candidate.json", profile)):
            raw = json.dumps(document, allow_nan=False).encode()
            path = self.frozen / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            inputs.append({"path": name, **self.identity(raw)})
        recipe = {"accepted_sha": FROZEN_SHA, "owner_artifact_exception": True,
                  "source_run_id": 37170332840, "inputs": inputs}
        self.recipe = self.repo / sources.RECIPE
        self.recipe.parent.mkdir(parents=True)
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")
        # Fixture identities authorize these inert test bytes only. The real
        # production constants stay pinned to the two frozen source files.
        self.producer_pins = {}
        for name in sources.PRODUCERS:
            raw = b'raise RuntimeError("ARCHIVED PRODUCER MUST NEVER EXECUTE")\n'
            path = self.frozen / "support-consumers" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            self.producer_pins[name] = self.identity(raw)
        stack = self.enterContext(ExitStack())
        stack.enter_context(patch.object(sources.session, "ROOT", self.repo))
        stack.enter_context(patch.object(sources.session, "PROFILE_RELATIVE", "frozen/ma2141-profile-candidate.json"))
        stack.enter_context(patch.object(sources, "load_workspace", return_value={"data": str(self.data)}))
        stack.enter_context(patch.object(sources, "PRODUCERS", self.producer_pins))

    @staticmethod
    def identity(raw):
        return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

    def test_real_shared_loader_and_byte_snapshot_checks_authenticate_all_186_without_executing_consumers(self):
        plan = sources.load_sources()
        self.assertEqual(len(plan["owners"]), 186)
        self.assertEqual(plan["source_identity"]["material_target_count"], 185)
        self.assertEqual(plan["source_identity"]["excluded_parapet_count"], 1)
        self.assertEqual(plan["source_identity"]["recipe_sha256"], self.identity(self.recipe.read_bytes())["sha256"])
        self.assertEqual(plan["source_identity"]["verified_input_count"], 3)
        self.assertEqual(plan["source_identity"]["producer_files"]["support-consumers/nudo_structure.py"],
                         self.producer_pins["nudo_structure.py"])
        self.assertFalse(plan["source_identity"]["geometry_consumers_executed"])
        self.assertFalse(plan["source_identity"]["geometry_authored"])

    def test_same_length_frozen_json_tampering_fails(self):
        path = self.frozen / "Network/network.json"
        raw = path.read_bytes()
        changed = raw.replace(b'"window-0000"', b'"window-9999"', 1)
        self.assertEqual(len(changed), len(raw))
        self.assertNotEqual(changed, raw)
        path.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
            sources.load_sources()

    def test_separately_pinned_inert_producer_tampering_fails(self):
        path = self.frozen / "support-consumers/nudo_structure.py"
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"NEVER", b"ALWAY", 1))
        with self.assertRaisesRegex(ValueError, "producer bytes changed"):
            sources.load_sources()

    def test_loader_geometry_cannot_borrow_identity_from_later_correct_file_hash(self):
        loader = sources.load_frozen_windows

        def altered_snapshot(*args, **kwargs):
            result = loader(*args, **kwargs)
            result["windows"][0]["sections"][0][0][2] += 0.01
            return result

        with patch.object(sources, "load_frozen_windows", side_effect=altered_snapshot):
            with self.assertRaisesRegex(ValueError, "differ from authenticated byte snapshots"):
                sources.load_sources()

    def test_checked_read_rejects_escape_bounds_and_changed_exact_bytes(self):
        raw = b'{"value":1}'
        (self.frozen / "small.json").write_bytes(raw)
        pin = self.identity(raw)
        self.assertEqual(sources._read_checked_json(self.frozen, "small.json", pin), {"value": 1})
        for size in (True, 0, sources.MAX_DOCUMENT_BYTES + 1):
            with self.assertRaises(ValueError):
                sources._read_checked_json(self.frozen, "small.json", {**pin, "size_bytes": size})
        with self.assertRaises(ValueError):
            sources._read_checked_json(self.frozen, "../small.json", pin)
        (self.frozen / "small.json").write_bytes(b'{"value":2}')
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            sources._read_checked_json(self.frozen, "small.json", pin)


if __name__ == "__main__":
    unittest.main()
