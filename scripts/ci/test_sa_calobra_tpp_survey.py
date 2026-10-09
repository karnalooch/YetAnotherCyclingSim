"""Frozen-road identity, coverage and bidirectional TPP camera contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
import unittest
from itertools import pairwise
from pathlib import Path

from scripts.proof.sa_calobra_tpp_survey import (
    FROZEN_SHA,
    SurveyConfig,
    build_survey_plan,
    load_frozen_windows,
)

SHA = "a" * 40


def section(x, y=0, z=0):
    return [[x, y + offset, z] for offset in (-2, -1, 0, 1, 2)]


def window(name="road-a", points=((0, 0, 0), (45, 0, 0))):
    return {"id": name, "sections": [section(*point) for point in points]}


def fixture(root, *, network_ids=("road-a", "road-b"), native_ids=None):
    native_ids = network_ids if native_ids is None else native_ids
    documents = {
        "Network/network.json": {
            "exact_sha": FROZEN_SHA,
            "approved": [
                window(name, ((0, i * 50, 0), (45, i * 50, 0)))
                for i, name in enumerate(network_ids)
            ],
            "owner_reviewed": [],
            "nudo": {"windows": []},
        },
        "network-native-proof.json": {
            "exact_sha": FROZEN_SHA,
            "construction_window_count": len(native_ids),
            "windows": [{"id": name} for name in native_ids],
        },
        "ma2141-profile-candidate.json": {
            "exact_sha": FROZEN_SHA,
            "stations": [
                {
                    "xy_local_m": [[p[0], p[1]] for p in section(x)],
                    "candidate_ground_m": [3] * 5,
                }
                for x in (0, 10)
            ],
        },
        # Must be verified as bytes, never executed by the inspection loader.
        "support-consumers/unused.py": "raise RuntimeError('Must not execute support consumer')\n",
    }
    inputs = []
    for name, value in documents.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            value if isinstance(value, str) else json.dumps(value), encoding="utf-8"
        )
        data = path.read_bytes()
        inputs.append(
            {
                "path": name,
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    recipe = {
        "accepted_sha": FROZEN_SHA,
        "owner_artifact_exception": True,
        "source_run_id": 37170332840,
        "inputs": inputs,
        "admission": "Owner frozen visual output only",
    }
    recipe_path = root / "trusted-recipe.json"
    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
    return recipe_path, recipe


class PlannerTests(unittest.TestCase):
    def test_every_window_has_both_directions_and_exact_endpoints(self):
        rows = [window(), window("road-b", ((400, 50, 2), (410, 50, 2)))]
        plan = build_survey_plan(rows, SurveyConfig(SHA))
        self.assertEqual(plan["frame_count"], 12)
        self.assertEqual(len(plan["frames"]), 12)
        for summary in plan["windows"]:
            forward = [
                r
                for r in plan["frames"]
                if r["window_id"] == summary["window_id"]
                and r["direction"] == "forward"
            ]
            reverse = [
                r
                for r in plan["frames"]
                if r["window_id"] == summary["window_id"]
                and r["direction"] == "reverse"
            ]
            self.assertEqual(forward[0]["road_position_cm"], summary["start_cm"])
            self.assertEqual(forward[-1]["road_position_cm"], summary["end_cm"])
            self.assertEqual(
                [r["road_position_cm"] for r in forward],
                [r["road_position_cm"] for r in reverse[::-1]],
            )
            self.assertTrue(
                all(b["station_m"] - a["station_m"] <= 20 for a, b in pairwise(forward))
            )
            self.assertEqual(reverse[0]["travel_distance_m"], 0)
            self.assertEqual(reverse[-1]["travel_distance_m"], summary["length_m"])

    def test_centres_follow_each_cross_section_and_not_endpoint_chord(self):
        plan = build_survey_plan(
            [window(points=((0, 0, 0), (10, 0, 0), (10, 10, 0)))],
            SurveyConfig(SHA, spacing_m=10),
        )
        forward = plan["frames"][:3]
        self.assertEqual(
            [row["road_position_cm"] for row in forward],
            [[0, 0, 0], [1000, 0, 0], [1000, 1000, 0]],
        )
        self.assertEqual(forward[1]["road_forward_unit"], [0, 1, 0])

    def test_reverse_grade_tangent_and_camera_offsets_use_metres_to_cm(self):
        plan = build_survey_plan(
            [window(points=((0, 0, 10), (12, 0, 15)))], SurveyConfig(SHA)
        )
        forward, reverse = plan["frames"][0], plan["frames"][-1]
        self.assertEqual(forward["road_position_cm"], reverse["road_position_cm"])
        self.assertEqual(forward["ball_location_cm"], [0, 0, 1040])
        self.assertEqual(forward["sphere_radius_cm"], 40)
        for a, b in zip(forward["road_forward_unit"], reverse["road_forward_unit"]):
            self.assertAlmostEqual(a, -b)
        for row in (forward, reverse):
            for axis in range(3):
                road = row["road_position_cm"][axis]
                direction = row["road_forward_unit"][axis]
                self.assertAlmostEqual(
                    row["camera_location_cm"][axis],
                    road - direction * 500 + (220 if axis == 2 else 0),
                )
                self.assertAlmostEqual(
                    row["target_cm"][axis],
                    row["ball_location_cm"][axis] + direction * 800,
                )
            self.assertAlmostEqual(math.hypot(*row["road_forward_unit"]), 1)

    def test_window_discontinuity_stays_unverified_even_at_same_endpoint(self):
        rows = [
            window(points=((0, 0, 0), (10, 0, 0))),
            window("road-b", ((10, 0, 0), (20, 0, 0))),
            window("road-c", ((1000, 0, 0), (1010, 0, 0))),
        ]
        plan = build_survey_plan(rows, SurveyConfig(SHA))
        self.assertEqual([r["endpoint_gap_m"] for r in plan["transitions"]], [0, 980])
        self.assertFalse(plan["continuous_route"])
        self.assertFalse(plan["physics_playback"])
        self.assertTrue(
            all(r["continuity"] == "UNVERIFIED" for r in plan["transitions"])
        )
        self.assertTrue(all(not r["captured_connection"] for r in plan["transitions"]))
        self.assertEqual(
            {tuple(r["road_position_cm"]) for r in plan["frames"]},
            {(0, 0, 0), (1000, 0, 0), (2000, 0, 0), (100000, 0, 0), (101000, 0, 0)},
        )

    def test_replay_is_identical_for_reordered_source_inventory(self):
        rows = [window("z"), window("a")]
        a = build_survey_plan(rows, SurveyConfig(SHA))
        b = build_survey_plan(rows[::-1], SurveyConfig(SHA))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(len({r["frame_id"] for r in a["frames"]}), a["frame_count"])
        self.assertEqual(rows[0]["id"], "z")  # Caller inventory was not mutated.

    def test_duplicate_centres_are_reported_without_zero_tangent(self):
        plan = build_survey_plan(
            [window(points=((0, 0, 0), (0, 0, 0), (10, 0, 0)))], SurveyConfig(SHA)
        )
        self.assertEqual(plan["windows"][0]["duplicate_centre_sections_removed"], 1)
        self.assertEqual(plan["frame_count"], 4)

    def test_invalid_geometry_and_duplicate_ids_fail(self):
        invalid = [
            [],
            [window(), window()],
            [window(points=((0, 0, 0), (0, 0, 1)))],
            [window(points=((0, 0, 0), (0, 0, 0)))],
            [window(points=((0, 0, 0), (float("nan"), 0, 0)))],
            [{"id": "bad", "sections": [section(0), [[1, 0, 0]]]}],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                build_survey_plan(rows, SurveyConfig(SHA))

    def test_frame_budget_fails_before_huge_sample_allocation(self):
        with self.assertRaisesRegex(ValueError, "frame budget"):
            build_survey_plan(
                [window(points=((0, 0, 0), (100000, 0, 0)))], SurveyConfig(SHA)
            )
        with self.assertRaisesRegex(ValueError, "frame budget"):
            build_survey_plan([window()], SurveyConfig(SHA, spacing_m=1e-300))

    def test_invalid_config_fails(self):
        for changes in (
            {"exact_sha": "main"},
            {"spacing_m": True},
            {"spacing_m": 0},
            {"camera_height_m": float("inf")},
            {"trailing_m": -1},
            {"sphere_radius_m": 0},
            {"lookahead_m": -1},
            {"fov_deg": 179},
            {"max_frames": 4097},
            {"max_frames": 10.0},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SurveyConfig(**({"exact_sha": SHA} | changes))


class FrozenLoaderTests(unittest.TestCase):
    def test_all_bytes_verified_and_checkpoint_hairpin_lift_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe_path, recipe = fixture(root)
            result = load_frozen_windows(
                root, recipe_path=recipe_path, expected_window_count=2
            )
            self.assertEqual(len(result["windows"]), 3)
            self.assertEqual(result["windows"][-1]["id"], "accepted-hairpin")
            self.assertEqual(result["windows"][-1]["sections"][0][0][2], 3.04)
            self.assertEqual(
                result["source_identity"]["verified_input_count"], len(recipe["inputs"])
            )
            self.assertFalse(result["source_identity"]["geometry_consumers_executed"])
            plan = build_survey_plan(
                result["windows"],
                SurveyConfig(SHA),
                source_identity=result["source_identity"],
            )
            self.assertEqual(plan["source_identity"]["accepted_road_sha"], FROZEN_SHA)

    def test_changed_input_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe_path, _ = fixture(root)
            path = root / "Network/network.json"
            data = path.read_text()
            path.write_text(data.replace("road-a", "road-x"))  # Preserve byte count.
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
                load_frozen_windows(
                    root, recipe_path=recipe_path, expected_window_count=2
                )

    def test_missing_and_duplicate_native_windows_rejected(self):
        for network_ids, native_ids in (
            (["road-a", "road-a"], None),
            (["road-a"], ["road-a", "road-b"]),
            (["road-a", "road-b"], ["road-a", "road-a"]),
        ):
            with (
                self.subTest(network_ids=network_ids, native_ids=native_ids),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                recipe_path, _ = fixture(
                    root, network_ids=network_ids, native_ids=native_ids
                )
                with self.assertRaises(ValueError):
                    load_frozen_windows(
                        root, recipe_path=recipe_path, expected_window_count=2
                    )

    def test_unsafe_paths_and_unhashed_documents_rejected(self):
        for path in (
            "../outside.json",
            "D:\\outside.json",
            "/outside.json",
            "Network\\network.json",
            None,
        ):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                recipe_path, recipe = fixture(root)
                if path is None:
                    recipe["inputs"] = recipe["inputs"][1:]
                else:
                    recipe["inputs"][0]["path"] = path
                recipe_path.write_text(json.dumps(recipe))
                with self.assertRaises(ValueError):
                    load_frozen_windows(
                        root, recipe_path=recipe_path, expected_window_count=2
                    )

    def test_local_recipe_cannot_rewrite_trusted_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe_path, recipe = fixture(root)
            local = copy.deepcopy(recipe)
            local["accepted_sha"] = "b" * 40
            (root / "source-recipe.json").write_text(json.dumps(local))
            with self.assertRaisesRegex(ValueError, "differs from the trusted"):
                load_frozen_windows(
                    root, recipe_path=recipe_path, expected_window_count=2
                )

    def test_verified_documents_must_keep_the_accepted_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recipe_path, recipe = fixture(root)
            path = root / "network-native-proof.json"
            report = json.loads(path.read_text())
            report["exact_sha"] = "b" * 40
            path.write_text(json.dumps(report))
            data = path.read_bytes()
            for item in recipe["inputs"]:
                if item["path"] == path.name:
                    item.update(
                        size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
                    )
            recipe_path.write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError, "Mixed frozen road revisions"):
                load_frozen_windows(
                    root, recipe_path=recipe_path, expected_window_count=2
                )


if __name__ == "__main__":
    unittest.main()
