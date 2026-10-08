"""Offline contract tests for view-proposed face partitioning.

Synthetic geometry deliberately separates perspective visibility from distance,
source ownership from detail priority, and export ordering from geometry edits.
"""

import copy
import tempfile
import unittest
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_sa_calobra_detail_pilot as pilot  # noqa: E402


CAMERA = np.array([0.0, 0.0, 0.0])
TARGET = np.array([1.0, 0.0, 0.0])
SIZE = 64


def from_pixels(pixels, depths):
    """Independent pinhole fixture: +X forward, +Y right, +Z up, FOV 90."""
    pixels = np.asarray(pixels, dtype=float)
    depths = np.asarray(depths, dtype=float)
    return np.column_stack(
        (depths, (pixels[:, 0] - 32) * depths / 32, (32 - pixels[:, 1]) * depths / 32)
    )


class ProjectionContracts(unittest.TestCase):
    def test_native_axes_project_to_expected_screen_directions(self):
        vertices = np.array(
            [[10, 0, 0], [10, 5, 0], [10, 0, 5], [-10, 0, 0]], dtype=float
        )
        xy, depth = pilot.project_vertices(vertices, CAMERA, TARGET, 90, SIZE, SIZE)
        np.testing.assert_allclose(xy[:3], [[32, 32], [48, 32], [32, 16]], atol=1e-10)
        np.testing.assert_allclose(depth, [10, 10, 10, -10])

    def test_heading_rotation_and_roll_free_up(self):
        f, r, u = pilot.camera_basis(CAMERA, np.array([0.0, 1.0, 0.0]))
        np.testing.assert_allclose(f, [0, 1, 0], atol=1e-12)
        np.testing.assert_allclose(r, [-1, 0, 0], atol=1e-12)
        np.testing.assert_allclose(u, [0, 0, 1], atol=1e-12)
        np.testing.assert_allclose(
            np.array([f, r, u]) @ np.array([f, r, u]).T, np.eye(3), atol=1e-12
        )

    def test_nearest_face_wins_over_overlapping_far_face(self):
        pixels = [[16, 16], [48, 16], [32, 48]]
        vertices = np.vstack(
            [from_pixels(pixels, [5] * 3), from_pixels(pixels, [10] * 3)]
        )
        owners, depth = pilot.rasterize(
            vertices, np.array([[0, 1, 2], [3, 4, 5]]), CAMERA, TARGET, 90, SIZE, SIZE
        )
        self.assertEqual(int(owners[27, 32]), 0)
        self.assertAlmostEqual(float(depth[27, 32]), 5.0, places=8)
        self.assertFalse(np.any(owners == 1))

    def test_depth_is_perspective_correct_not_linear_vertex_depth(self):
        pixels = [[16, 16], [48, 16], [32, 48]]
        vertices = np.vstack(
            [from_pixels(pixels, [2, 20, 20]), from_pixels(pixels, [8] * 3)]
        )
        owners, depth = pilot.rasterize(
            vertices, np.array([[0, 1, 2], [3, 4, 5]]), CAMERA, TARGET, 90, SIZE, SIZE
        )
        # Near the centroid, reciprocal interpolation yields approximately 5;
        # linear interpolation incorrectly yields approximately 14 and picks face 1.
        self.assertEqual(int(owners[27, 32]), 0)
        self.assertGreater(float(depth[27, 32]), 4)
        self.assertLess(float(depth[27, 32]), 6)

    def test_fully_behind_camera_never_claims_pixels(self):
        vertices = np.array([[-5, -1, -1], [-5, 1, -1], [-5, 0, 1]], dtype=float)
        owners, depth = pilot.rasterize(
            vertices, np.array([[0, 1, 2]]), CAMERA, TARGET, 90, SIZE, SIZE
        )
        self.assertTrue(np.all(owners == -1))
        self.assertTrue(np.all(np.isinf(depth)))

    def test_triangle_crossing_camera_plane_retains_front_fragment(self):
        vertices = np.array([[-1, 0, 0], [4, -2, -2], [4, 2, -2]], dtype=float)
        owners, depth = pilot.rasterize(
            vertices, np.array([[0, 1, 2]]), CAMERA, TARGET, 90, SIZE, SIZE
        )
        visible = owners == 0
        self.assertTrue(np.any(visible))
        self.assertTrue(np.all(np.isfinite(depth[visible])))
        self.assertTrue(np.all(depth[visible] > 0))


def minimal_mesh():
    return {
        "vertices_cm": [
            [10, 5, -1, -1, 5, -1, -1, 0],
            [20, 5, 1, -1, 5, 1, -1, 1],
            [30, 5, 1, 1, 5, 1, 1, 1],
            [40, 5, -1, 1, 5, -1, 1, 0],
        ],
        "triangles": [[10, 20, 30], [10, 30, 40]],
        "source_reference_topology_unchanged": True,
    }


class MeshIdentityContracts(unittest.TestCase):
    def test_noncontiguous_vertex_ids_resolve_without_changing_source(self):
        mesh = minimal_mesh()
        before = copy.deepcopy(mesh)
        ids, source, candidate, movable, triangles = pilot.validate_mesh(mesh)
        np.testing.assert_array_equal(ids, [10, 20, 30, 40])
        np.testing.assert_array_equal(triangles, [[0, 1, 2], [0, 2, 3]])
        np.testing.assert_array_equal(movable, [False, True, True, False])
        np.testing.assert_array_equal(source, candidate)
        self.assertEqual(mesh, before)

    def test_missing_vertex_reference_rejected_before_projection(self):
        mesh = minimal_mesh()
        mesh["triangles"][0][2] = 999
        with self.assertRaises((ValueError, KeyError)):
            pilot.validate_mesh(mesh)

    def test_duplicate_vertex_identity_rejected(self):
        mesh = minimal_mesh()
        mesh["vertices_cm"][1][0] = 10
        with self.assertRaises(ValueError):
            pilot.validate_mesh(mesh)


class SourceProtectionContracts(unittest.TestCase):
    def test_locked_vertex_change_rejected(self):
        mesh = minimal_mesh()
        mesh["vertices_cm"][0][4] += 0.01
        with self.assertRaisesRegex(ValueError, "locked"):
            pilot.validate_mesh(mesh)

    def test_movable_vertex_has_bounded_source_displacement(self):
        mesh = minimal_mesh()
        mesh["vertices_cm"][1][4] += 50.1
        with self.assertRaisesRegex(ValueError, "50 cm"):
            pilot.validate_mesh(mesh)


class RegionAndUnknownContracts(unittest.TestCase):
    def test_duplicate_overlapping_same_band_regions_do_not_inflate_hits(self):
        owners = np.array([[0, 0, -1], [1, 1, -1]])
        polygon = [[0, 0], [1, 0], [1, 1], [0, 1]]
        regions = [{"band": "A", "polygon": polygon}, {"band": "A", "polygon": polygon}]
        scores = pilot.classify_frame(owners, regions)
        self.assertEqual(scores[0], {"A": 2, "B": 0, "C": 0})
        self.assertEqual(scores[1], {"A": 2, "B": 0, "C": 0})
        self.assertNotIn(-1, scores)

    def test_unknown_is_never_hidden_D_and_cross_view_demand_cannot_downgrade(self):
        scores = [{0: {"C": 7}, 1: {"B": 3}}, {0: {"A": 1}, 1: {"C": 100}}]
        self.assertEqual(pilot.merge_scores(scores, 3), ["A", "B", "U"])
        self.assertEqual(pilot.merge_scores([], 3), ["U", "U", "U"])

    def test_face_index_outside_exact_mesh_rejected(self):
        for invalid in [-1, 2]:
            with self.subTest(face=invalid), self.assertRaises(ValueError):
                pilot.merge_scores([{invalid: {"A": 1}}], 2)

    def test_annotations_require_exact_source_hash_and_reject_D(self):
        sha = "a" * 64
        data = {
            "schema_version": 1,
            "mesh_sha256": sha,
            "frames": [
                {
                    "frame_id": "fixture-frame",
                    "regions": [
                        {
                            "region_id": "near-bank",
                            "band": "A",
                            "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
                        }
                    ],
                }
            ],
        }
        before = copy.deepcopy(data)
        records = pilot.validate_annotations(data, sha, {"fixture-frame": {}})
        self.assertEqual(records, data["frames"])
        self.assertEqual(data, before)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            pilot.validate_annotations(data, "b" * 64, {"fixture-frame": {}})
        invalid = copy.deepcopy(data)
        invalid["frames"][0]["regions"][0]["band"] = "D"
        with self.assertRaises(ValueError):
            pilot.validate_annotations(invalid, sha, {"fixture-frame": {}})

    def test_five_tags_are_independent_proposals_and_not_inferred_from_band(self):
        sha = "a" * 64
        region = {
            "region_id": "b-face",
            "band": "B",
            "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "tags": ["HERO_DETAIL", "MATERIAL_TEST_CANDIDATE"],
        }
        data = {
            "schema_version": 1,
            "mesh_sha256": sha,
            "frames": [{"frame_id": "fixture-frame", "regions": [region]}],
        }
        before = copy.deepcopy(data)
        pilot.validate_annotations(data, sha, {"fixture-frame": {}})
        self.assertEqual(data, before)
        scores = pilot.classify_frame(np.array([[0, 0]]), [region])
        self.assertEqual(pilot.merge_scores([scores], 2), ["B", "U"])
        untagged = copy.deepcopy(data)
        del untagged["frames"][0]["regions"][0]["tags"]
        pilot.validate_annotations(untagged, sha, {"fixture-frame": {}})
        self.assertNotIn("tags", untagged["frames"][0]["regions"][0])

    def test_unknown_or_duplicated_tags_rejected(self):
        sha = "a" * 64
        for tags in [["NOT_A_REVIEW_TAG"], ["HERO_DETAIL", "HERO_DETAIL"]]:
            with self.subTest(tags=tags):
                data = {
                    "schema_version": 1,
                    "mesh_sha256": sha,
                    "frames": [
                        {
                            "frame_id": "fixture-frame",
                            "regions": [
                                {
                                    "region_id": "b-face",
                                    "band": "B",
                                    "tags": tags,
                                    "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
                                }
                            ],
                        }
                    ],
                }
                with self.assertRaisesRegex(ValueError, "tags"):
                    pilot.validate_annotations(data, sha, {"fixture-frame": {}})


class ImmutableObjContracts(unittest.TestCase):
    def test_repeated_export_is_identical_and_preserves_vertices_faces_winding(self):
        vertices = np.array(
            [[1 / 3, 0, 0], [2, 1e-7, 0], [2, 3, 0], [0, 3, -7]], dtype=float
        )
        triangles = np.array([[0, 1, 2], [0, 2, 3], [3, 2, 1], [3, 1, 0]])
        bands = ["C", "A", "U", "B"]
        before_vertices = vertices.copy()
        before_triangles = triangles.copy()
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.obj", Path(folder) / "b.obj"
            pilot.write_obj(a, vertices, triangles, bands)
            pilot.write_obj(b, vertices, triangles, bands)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            lines = a.read_text().splitlines()
        actual_vertices = np.array(
            [
                [float(v) for v in line.split()[1:]]
                for line in lines
                if line.startswith("v ")
            ]
        )
        actual_faces = np.array(
            [
                [int(v) - 1 for v in line.split()[1:]]
                for line in lines
                if line.startswith("f ")
            ]
        )
        np.testing.assert_array_equal(actual_vertices, vertices)
        np.testing.assert_array_equal(actual_faces, triangles)
        np.testing.assert_array_equal(vertices, before_vertices)
        np.testing.assert_array_equal(triangles, before_triangles)
        self.assertEqual(
            [line for line in lines if line.startswith("g ")],
            ["g C", "g A", "g U", "g B"],
        )
        self.assertNotIn("g D", lines)


if __name__ == "__main__":
    unittest.main()
