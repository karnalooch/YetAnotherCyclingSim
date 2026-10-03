"""Coverage, unchanged candidates and non-admission of full network previews."""

import copy
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, box, mapping

from scripts.assets.prepare_current_landscape_roads import (
    build_full_source_markers,
    write_full_preview_plan,
)
from scripts.geometry.network_visual_preview import (
    source_marker_mesh,
    overview_camera,
    validate_full_preview,
)


def source_fixture():
    return {
        "features": [
            {
                "id": "main",
                "geometry": mapping(LineString([(0, 5, 10), (4, 5, 20), (4, 9, 30)])),
            },
            {
                "id": "VIAL_TR70190001288",
                "geometry": mapping(LineString([(1, 1), (2, 1)])),
            },
            {"id": "outside", "geometry": mapping(LineString([(20, 20), (21, 20)]))},
        ]
    }


def fixture():
    markers = build_full_source_markers(
        source_fixture(), box(0, 0, 10, 10), lambda x, y, z=None: (x, y), [0, 10]
    )
    for marker in markers:
        marker["ground_m"] = [0.0] * len(marker["xy_local_m"])
    road = [[[float(x), 1 + j / 5, 2.0] for j in range(25)] for x in (1, 2, 3)]
    return {
        "schema_version": 1,
        "role": "VISUAL_REVIEW_ONLY",
        "road_admitted": False,
        "height_change_applied": False,
        "terrain_change_applied": False,
        "source_markers": markers,
        "rejected_surfaces": [
            {
                "id": "conflict",
                "reason": "CUT > 1 m",
                "sections": road,
                "road_admitted": False,
            }
        ],
    }


class FullPreviewTests(unittest.TestCase):
    def test_source_coverage_keeps_vertices_and_short_nudo_without_source_z(self):
        preview = fixture()
        proof = validate_full_preview(preview, 9.0)
        self.assertEqual(proof["source_marker_count"], 2)
        self.assertAlmostEqual(proof["source_marker_length_m"], 9.0)
        self.assertIn([4, 5], preview["source_markers"][0]["xy_local_m"])
        nudo = preview["source_markers"][1]
        self.assertTrue(nudo["structure_review_required"])
        self.assertEqual(nudo["xy_local_m"], [[1, 9], [2, 9]])
        self.assertFalse(proof["road_admitted"])

    def test_missing_part_or_false_length_does_not_claim_complete_context(self):
        for mutate in (
            lambda p: p["source_markers"].pop(),
            lambda p: p["source_markers"][0].update(length_m=100),
            lambda p: p["source_markers"].append(copy.deepcopy(p["source_markers"][0])),
            lambda p: p["source_markers"][0]["ground_m"].pop(),
            lambda p: p["rejected_surfaces"][0].update(road_admitted=True),
        ):
            preview = fixture()
            mutate(preview)
            with self.assertRaises(ValueError):
                validate_full_preview(preview, 9.0)

    def test_receipt_detects_changed_candidate_height_and_nonfinite_geometry(self):
        preview = fixture()
        original = copy.deepcopy(preview)
        proof = validate_full_preview(preview, 9.0)
        self.assertEqual(preview, original)
        preview["rejected_surfaces"][0]["sections"][1][12][2] += 0.01
        self.assertNotEqual(
            validate_full_preview(preview, 9.0)["fingerprint"], proof["fingerprint"]
        )
        preview["rejected_surfaces"][0]["sections"][1][12][2] = math.nan
        with self.assertRaises(ValueError):
            validate_full_preview(preview, 9.0)

    def test_marker_is_narrow_annotation_and_does_not_move_input(self):
        points = [[0, 0, 2], [2, 0, 3], [2, 2, 4]]
        original = copy.deepcopy(points)
        vertices, triangles = source_marker_mesh(points)
        self.assertEqual(points, original)
        self.assertEqual(len(vertices), 16)
        self.assertEqual(len(triangles), 24)
        self.assertAlmostEqual(math.dist(vertices[0], vertices[1]), 0.15)
        for triangle in triangles:
            self.assertTrue(all(0 <= i < len(vertices) for i in triangle))
        from collections import Counter

        edges = Counter(
            tuple(sorted((a, b)))
            for face in triangles
            for a, b in zip(face, (*face[1:], face[0]))
        )
        self.assertTrue(all(count == 2 for count in edges.values()))
        self.assertAlmostEqual(vertices[0][2] - vertices[4][2], 0.01)
        with self.assertRaises(ValueError):
            source_marker_mesh([[0, 0, 0], [0, 0, 1]])

    def test_overview_fits_all_source_markers_at_existing_camera_fov(self):
        preview = fixture()
        camera = overview_camera(preview)
        location = camera["location_m"]
        # Check against the highest ground, the most restrictive projection.
        distance = location[2] - max(
            v for m in preview["source_markers"] for v in m["ground_m"]
        )
        half_width = distance * math.tan(math.radians(74) / 2)
        half_height = half_width * 9 / 16
        for marker in preview["source_markers"]:
            for x, y in marker["xy_local_m"]:
                self.assertLess(abs(x - location[0]), half_width)
                self.assertLess(abs(y - location[1]), half_height)

    def test_full_plan_contains_source_and_both_decision_classes(self):
        preview = fixture()
        original = copy.deepcopy(preview)
        network = {
            "full_preview": preview,
            "approved": [{"sections": preview["rejected_surfaces"][0]["sections"]}],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.png"
            write_full_preview_plan(network, path)
            from PIL import Image

            with Image.open(path) as image:
                self.assertEqual(image.size, (1800, 1800))
                pixels = np.asarray(image)
                self.assertTrue(((pixels == (255, 184, 53)).all(axis=2)).any())
                self.assertTrue(((pixels == (250, 62, 49)).all(axis=2)).any())
        self.assertEqual(preview, original)


if __name__ == "__main__":
    unittest.main()
