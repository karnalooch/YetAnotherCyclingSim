"""Invariant tests for a bounded native-mesh detail proposal, without Unreal."""

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_sa_calobra_detail_treatment as treatment  # noqa: E402
from prepare_sa_calobra_detail_pilot import TAGS, validate_mesh  # noqa: E402


SOURCE_HASH = "a" * 64
MASK_HASH = "b" * 64


def grid_mesh(size=9, bumps=((4, 4, 12),)):
    """25 cm grid with explicit v8 peaks and noncontiguous native vertex IDs."""
    vertices, triangles = [], []
    heights = {(x, y): height for x, y, height in bumps}
    for y in range(size):
        for x in range(size):
            index = y * size + x
            vertices.append(
                [
                    101 + 3 * index,
                    25 * x,
                    25 * y,
                    0,
                    25 * x,
                    25 * y,
                    heights.get((x, y), 0),
                    1,
                ]
            )
    for y in range(size - 1):
        for x in range(size - 1):
            a = 101 + 3 * (y * size + x)
            b, c, d = a + 3, a + 3 * size + 3, a + 3 * size
            triangles.extend([[a, b, c], [a, c, d]])
    return {
        "vertices_cm": vertices,
        "triangles": triangles,
        "source_reference": "original-before-reshaping",
        "source_reference_topology_unchanged": True,
    }


def square_faces(size, x, y, width):
    return {
        2 * (row * (size - 1) + column) + half
        for row in range(y, y + width)
        for column in range(x, x + width)
        for half in (0, 1)
    }


def make_mask(mesh, a_faces, b_faces=(), silhouette_faces=()):
    ids, _, _, movable, triangles = validate_mesh(mesh)
    bands = "".join(
        "A" if index in a_faces else "B" if index in b_faces else "U"
        for index in range(len(triangles))
    )
    return {
        "schema_version": 1,
        "review_status": "AI_PROPOSED",
        "owner_review": "PENDING",
        "mesh_sha256": SOURCE_HASH,
        "triangle_identity": treatment.TRIANGLE_IDENTITY,
        "bands": bands,
        "tag_bit_order": list(TAGS),
        "proposed_tag_masks": [
            2 if index in silhouette_faces else 0 for index in range(len(triangles))
        ],
        "eligible_all_vertices_movable": "".join(
            "1" if value else "0" for value in movable[triangles].all(axis=1)
        ),
        "protected_faces_require_no_treatment": True,
        "selected_faces": [
            {
                "triangle_row_index": index,
                "source_vertex_ids": ids[triangles[index]].tolist(),
                "evidence": [],
            }
            for index, band in enumerate(bands)
            if band != "U"
        ],
    }


def prepare_fixture(mesh=None, selected=None):
    mesh = grid_mesh() if mesh is None else mesh
    selected = square_faces(9, 2, 2, 4) if selected is None else selected
    mask = make_mask(mesh, selected)
    trial, manifest = treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)
    return mesh, mask, trial, manifest


class BoundaryAndShapeContracts(unittest.TestCase):
    def test_only_interior_candidate_coordinates_change_without_input_mutation(self):
        mesh = grid_mesh()
        selected = square_faces(9, 2, 2, 4)
        mask = make_mask(mesh, selected, b_faces={0, 1})
        original_mesh, original_mask = copy.deepcopy(mesh), copy.deepcopy(mask)
        trial, manifest = treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)
        ids, source, before, movable, triangles = validate_mesh(mesh)
        new_ids, new_source, after, new_movable, new_triangles = validate_mesh(trial)
        self.assertEqual(mesh, original_mesh)
        self.assertEqual(mask, original_mask)
        np.testing.assert_array_equal(ids, new_ids)
        np.testing.assert_array_equal(source, new_source)
        np.testing.assert_array_equal(movable, new_movable)
        np.testing.assert_array_equal(triangles, new_triangles)
        self.assertEqual(mesh["triangles"], trial["triangles"])
        self.assertEqual(mesh["source_reference"], trial["source_reference"])
        outside = sorted(set(range(len(triangles))) - selected)
        np.testing.assert_array_equal(
            after[triangles[outside]], before[triangles[outside]]
        )
        changed = np.flatnonzero(np.any(after != before, axis=1))
        self.assertGreater(len(changed), 0)
        self.assertEqual(manifest["changed_vertex_ids"], ids[changed].tolist())
        self.assertTrue(set(ids[changed]) <= set(manifest["interior_vertex_ids"]))
        for vertex in changed:
            touching = set(np.flatnonzero(np.any(triangles == vertex, axis=1)))
            self.assertTrue(touching <= selected)
        self.assertFalse(manifest["extra_frozen_one_ring"])
        self.assertEqual(manifest["owner_review"], "PENDING")
        self.assertFalse(manifest["production_admission"])

    def test_source_domain_border_stays_fixed_when_entire_mesh_is_selected(self):
        mesh = grid_mesh(size=7, bumps=((3, 3, 12),))
        _, _, trial, manifest = prepare_fixture(
            mesh, set(range(len(mesh["triangles"])))
        )
        _, _, before, _, _ = validate_mesh(mesh)
        _, _, after, _, _ = validate_mesh(trial)
        border = [
            y * 7 + x
            for y in range(7)
            for x in range(7)
            if x in (0, 6) or y in (0, 6)
        ]
        np.testing.assert_array_equal(before[border], after[border])
        self.assertEqual(manifest["outside_incident_vertex_count"], 0)
        self.assertEqual(len(manifest["fixed_boundary_vertex_ids"]), len(border))

    def test_protected_and_silhouette_faces_freeze_all_incident_vertices(self):
        mesh = grid_mesh()
        mesh["vertices_cm"][2 * 9 + 2][7] = 0
        selected = square_faces(9, 2, 2, 4)
        silhouette = {2 * (5 * 8 + 5), 2 * (5 * 8 + 5) + 1}
        mask = make_mask(mesh, selected, silhouette_faces=silhouette)
        trial, manifest = treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)
        _, _, before, movable, triangles = validate_mesh(mesh)
        _, _, after, _, _ = validate_mesh(trial)
        protected = set(np.flatnonzero(~movable[triangles].all(axis=1)))
        forbidden = protected | silhouette
        self.assertFalse(forbidden & set(manifest["selected_face_indices"]))
        np.testing.assert_array_equal(
            before[triangles[sorted(forbidden)]], after[triangles[sorted(forbidden)]]
        )

    def test_largest_component_wins_and_row_order_breaks_equal_size_ties(self):
        mesh = grid_mesh(size=13, bumps=((3, 3, 12), (9, 9, 12)))
        first, second = square_faces(13, 1, 1, 4), square_faces(13, 7, 7, 4)
        for other in (square_faces(13, 7, 7, 3), second):
            with self.subTest(other_size=len(other)):
                mask = make_mask(mesh, first | other)
                _, manifest = treatment.create_treatment(
                    mesh, mask, SOURCE_HASH, MASK_HASH
                )
                self.assertEqual(manifest["selected_face_indices"], sorted(first))
                self.assertEqual(manifest["eligible_a_component_count"], 2)

    def test_normal_residual_reduces_without_claiming_visual_improvement(self):
        _, _, _, manifest = prepare_fixture()
        residual = manifest["fairing_residual"]
        self.assertGreater(residual["before_cm"], residual["after_cm"])
        self.assertFalse(residual["visual_quality_score"])
        self.assertEqual(manifest["world_occlusion"], "NOT_MEASURED")

    def test_large_local_peak_keeps_both_caps_and_positive_triangle_orientation(self):
        mesh = grid_mesh(bumps=((4, 4, 49),))
        _, _, trial, manifest = prepare_fixture(mesh)
        _, source, before, _, triangles = validate_mesh(mesh)
        _, _, after, _, _ = validate_mesh(trial)
        added = np.linalg.norm(after - before, axis=1)
        total = np.linalg.norm(after - source, axis=1)
        self.assertLessEqual(float(added.max()), 5 + 1e-6)
        self.assertGreater(float(added.max()), 4.9)
        self.assertLessEqual(float(total.max()), 50 + 1e-6)
        old_cross = np.cross(
            before[triangles[:, 1]] - before[triangles[:, 0]],
            before[triangles[:, 2]] - before[triangles[:, 0]],
        )
        new_cross = np.cross(
            after[triangles[:, 1]] - after[triangles[:, 0]],
            after[triangles[:, 2]] - after[triangles[:, 0]],
        )
        self.assertTrue(np.all(np.sum(old_cross * new_cross, axis=1) > 0))
        self.assertTrue(
            np.all(
                np.linalg.norm(new_cross, axis=1)
                >= 0.5 * np.linalg.norm(old_cross, axis=1)
            )
        )
        for record in manifest["changed_vertices"]:
            index = record["row_index"]
            self.assertAlmostEqual(record["added_displacement_cm"], added[index])
            self.assertAlmostEqual(record["total_source_displacement_cm"], total[index])

    def test_identical_inputs_produce_identical_json_and_geometry(self):
        mesh, mask, trial, manifest = prepare_fixture()
        second, second_manifest = treatment.create_treatment(
            mesh, mask, SOURCE_HASH, MASK_HASH
        )
        self.assertEqual(
            json.dumps(trial, separators=(",", ":")),
            json.dumps(second, separators=(",", ":")),
        )
        self.assertEqual(manifest, second_manifest)

    def test_xy_fold_backtracks_even_with_positive_3d_normal_dot(self):
        mesh = grid_mesh(size=3, bumps=())
        for row in mesh["vertices_cm"]:
            row[3] = row[6] = 10 * row[1]
        # The inner vertex is very near the left boundary of a steep plane.
        # Normal fairing of this depression would cross that fixed XY boundary.
        center = mesh["vertices_cm"][4]
        center[1] = center[4] = 0.1
        center[3], center[6] = 1.0, -11.0
        _, _, trial, manifest = prepare_fixture(mesh, set(range(8)))
        _, _, before, _, triangles = validate_mesh(mesh)
        _, _, after, _, _ = validate_mesh(trial)
        scale = manifest["accepted_step_scale"]
        self.assertLess(scale, 1)
        unscaled = before + (after - before) / scale
        old_cross = treatment.triangle_normals(before, triangles)
        unchecked_cross = treatment.triangle_normals(unscaled, triangles)
        final_cross = treatment.triangle_normals(after, triangles)
        self.assertTrue(np.all(np.sum(old_cross * unchecked_cross, axis=1) > 0))
        self.assertTrue(np.any(old_cross[:, 2] * unchecked_cross[:, 2] < 0))
        self.assertTrue(np.all(old_cross[:, 2] * final_cross[:, 2] > 0))
        self.assertGreaterEqual(
            manifest["geometric_audit"]["min_xy_projected_area_ratio"], 0.5
        )


class FailClosedContracts(unittest.TestCase):
    def test_missing_interior_and_flat_patch_fail_without_inferred_mask_growth(self):
        for mesh, selected, expected in (
            (grid_mesh(), {0}, "strictly interior"),
            (grid_mesh(bumps=()), square_faces(9, 2, 2, 4), "nonzero"),
            (grid_mesh(), set(), "strictly interior"),
        ):
            with self.subTest(expected=expected):
                mask = make_mask(mesh, selected)
                original = copy.deepcopy(mesh)
                with self.assertRaisesRegex(ValueError, expected):
                    treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)
                self.assertEqual(mesh, original)

    def test_mask_cannot_relabel_protected_vertices_or_wrong_face_identities(self):
        mesh = grid_mesh()
        mask = make_mask(mesh, square_faces(9, 2, 2, 4))
        corruptions = {
            "wrong_mesh": lambda value: value.update(mesh_sha256="c" * 64),
            "implicit_D": lambda value: value.update(bands="D" + value["bands"][1:]),
            "eligibility": lambda value: value.update(
                eligible_all_vertices_movable="0"
                + value["eligible_all_vertices_movable"][1:]
            ),
            "missing_row": lambda value: value["selected_faces"].pop(),
            "wrong_ID": lambda value: value["selected_faces"][0][
                "source_vertex_ids"
            ].__setitem__(0, 999999),
            "wrong_winding": lambda value: value["selected_faces"][0][
                "source_vertex_ids"
            ].reverse(),
            "duplicate_row": lambda value: value["selected_faces"].__setitem__(
                1, value["selected_faces"][0]
            ),
            "unknown_bit": lambda value: value["proposed_tag_masks"].__setitem__(0, 32),
            "boolean_tag": lambda value: value["proposed_tag_masks"].__setitem__(
                0, True
            ),
            "tag_order": lambda value: value["tag_bit_order"].reverse(),
            "protection_off": lambda value: value.update(
                protected_faces_require_no_treatment=False
            ),
        }
        for name, corrupt in corruptions.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(mask)
                corrupt(bad)
                with self.assertRaises(ValueError):
                    treatment.create_treatment(mesh, bad, SOURCE_HASH, MASK_HASH)

    def test_duplicate_triangle_and_inconsistent_shared_edge_winding_are_rejected(self):
        for defect in ("duplicate", "winding"):
            with self.subTest(defect=defect):
                mesh = grid_mesh()
                if defect == "duplicate":
                    mesh["triangles"].append(mesh["triangles"][0][:])
                else:
                    mesh["triangles"][1].reverse()
                mask = make_mask(mesh, square_faces(9, 2, 2, 4))
                with self.assertRaisesRegex(ValueError, defect):
                    treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)

    def test_edge_nonmanifold_source_rejected_before_any_treatment(self):
        mesh = grid_mesh()
        edge = mesh["triangles"][0][:2]
        for extra, position in ((10001, [10, -20, 0]), (10004, [10, -20, 20])):
            mesh["vertices_cm"].append([extra, *position, *position, 1])
            mesh["triangles"].append([*edge, extra])
        mask = make_mask(mesh, square_faces(9, 2, 2, 4))
        with self.assertRaisesRegex(ValueError, "nonmanifold source edge"):
            treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)

    def test_bow_tie_vertex_is_rejected_even_when_edges_are_manifold(self):
        mesh = grid_mesh()
        for extra, position in ((10001, [-25, 0, 0]), (10004, [0, -25, 0])):
            mesh["vertices_cm"].append([extra, *position, *position, 1])
        mesh["triangles"].append([101, 10001, 10004])
        mask = make_mask(mesh, square_faces(9, 2, 2, 4))
        with self.assertRaisesRegex(ValueError, "nonmanifold source vertex fan"):
            treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)

    def test_degenerate_candidate_is_rejected(self):
        mesh = grid_mesh()
        mesh["vertices_cm"][1][1:7] = mesh["vertices_cm"][0][1:7]
        mask = make_mask(mesh, square_faces(9, 2, 2, 4))
        with self.assertRaisesRegex(ValueError, "degenerate"):
            treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)

    def test_vertical_projected_triangle_is_not_admitted_as_a_heightfield_trial(self):
        mesh = grid_mesh(size=3, bumps=())
        for row in mesh["vertices_cm"]:
            row[1:4] = [0, row[2], row[1]]
            row[4:7] = row[1:4]
        mask = make_mask(mesh, set(range(8)))
        with self.assertRaisesRegex(ValueError, "XY projection"):
            treatment.create_treatment(mesh, mask, SOURCE_HASH, MASK_HASH)


class DisplacementAndFileContracts(unittest.TestCase):
    def test_added_step_and_total_source_cap_are_both_enforced(self):
        source = np.zeros(3)
        for before, proposed in (
            ([49, 0, 0], [8, 6, 0]),
            ([50, 0, 0], [1, 0, 0]),
            ([50, 0, 0], [0, 10, 0]),
            ([50, 0, 0], [-10, 0, 0]),
            ([49.9, 0, 0], [-1, 10, 0]),
        ):
            with self.subTest(before=before, step=proposed):
                before = np.asarray(before, dtype=float)
                step = treatment.bound_step(
                    before, source, np.asarray(proposed, dtype=float)
                )
                self.assertLessEqual(float(np.linalg.norm(step)), 5 + 1e-6)
                self.assertLessEqual(
                    float(np.linalg.norm(before + step - source)), 50 + 1e-6
                )
        np.testing.assert_array_equal(
            treatment.bound_step(np.array([50., 0, 0]), source, np.array([1., 0, 0])),
            np.zeros(3),
        )
        np.testing.assert_array_equal(
            treatment.bound_step(np.array([50., 0, 0]), source, np.array([-10., 0, 0])),
            [-5, 0, 0],
        )
        with self.assertRaisesRegex(ValueError, "outside the total source"):
            treatment.bound_step(np.array([51., 0, 0]), source, np.array([-1., 0, 0]))

    def test_wrong_pinned_mesh_fails_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mesh = root / "mesh.json"
            mesh.write_text(json.dumps(grid_mesh()), encoding="utf-8")
            output = root / "trial"
            with self.assertRaisesRegex(ValueError, "fixed v8 source mesh SHA256"):
                treatment.prepare(mesh, root / "unused-mask.json", output)
            self.assertFalse(output.exists())

    def test_fixed_mask_bytes_are_hash_checked_before_json_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            mask = Path(temporary) / "mask.json"
            data = b'{"mesh_sha256":"forged"}'
            mask.write_bytes(data)
            with self.assertRaisesRegex(ValueError, "fixed detail mask SHA256"):
                treatment.read_fixed(mask, treatment.MASK, "detail mask")
            self.assertEqual(
                treatment.read_fixed(mask, hashlib.sha256(data).hexdigest(), "fixture"),
                json.loads(data),
            )

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "marker.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "output directory must not exist"):
                treatment.prepare("unused", "unused", temporary)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
