"""Clipping, source adhesion and sparse ownership fixtures; no native PASS."""

from copy import deepcopy
from dataclasses import replace
import math
import unittest

from scripts.ue import road_crack_geometry as cracks
from scripts.ue import test_road_edge_marking_geometry as paint_fixtures
from scripts.ue.test_road_edge_marking_geometry import (
    DIAGONAL_AD, DIAGONAL_BC, owner_fixture, plan_fixture, surface_area,
)


def event_fixture(owner, **kwargs):
    values = dict(event_id="fixture_crack", motif_id="short_oblique", window_id=owner["window_id"],
                  station_m=2.0, extent_m=1.4)
    return cracks.CrackEvent(**{**values, **kwargs})


def build(owner, *, event=None, topology=DIAGONAL_BC, others=()):
    return cracks.build_cracks(plan_fixture(owner, *others), quad_triangles=topology,
                               events=(event or event_fixture(owner),))


class CrackGeometryTests(unittest.TestCase):
    def setUp(self):
        self.owner = owner_fixture(y_values=(0., 1., 2., 3., 4.))

    def assert_source_surface(self, mesh, owner, topology):
        # Independent existing surface test checks every barycentric XYZ,
        # source-oriented normal and output triangle winding/span ownership.
        helper = paint_fixtures.MarkingGeometryTests()
        helper.assert_source_support(mesh, owner, topology)
        helper.assert_single_continuous_band(mesh)

    def test_complete_metric_square_preserves_source_and_stays_clear_of_paint(self):
        before = deepcopy(self.owner)
        result = build(self.owner)
        self.assertEqual(before, self.owner)
        self.assertEqual(len(result.meshes), 1)
        mesh, summary = result.meshes[0], result.manifest["events"][0]
        self.assert_source_surface(mesh, self.owner, DIAGONAL_BC)
        self.assertAlmostEqual(surface_area(mesh), 1.4 ** 2, places=12)
        self.assertAlmostEqual(summary["complete_uv_square_area"], 1.0, places=13)
        self.assertGreater(summary["minimum_clearance_to_paint_m"], 0.10)
        for point, uv in zip(mesh.positions_m, mesh.uv0, strict=True):
            self.assertAlmostEqual(point[0], 2.4 + (uv[0] - 0.5) * 1.4, places=13)
            self.assertAlmostEqual(point[1], 2.0 + (uv[1] - 0.5) * 1.4, places=13)
            self.assertEqual(point[2], 0.001)
            self.assertTrue(all(0 <= value <= 1 for value in uv))
        self.assertFalse(result.manifest["source_geometry_mutated"])
        self.assertFalse(result.manifest["existing_paint_mutated"])
        self.assertFalse(result.manifest["native_surface_correspondence_verified"])
        self.assertTrue(result.manifest["normal_world_space_canary_required"])

    def test_twisted_faces_both_diagonals_use_all_three_source_weights(self):
        owner = owner_fixture(y_values=(0., 1., 2., 3., 4.), height=lambda x, y: 0.12 * x * y)
        outputs = []
        for topology in (DIAGONAL_BC, DIAGONAL_AD):
            mesh = build(owner, event=event_fixture(owner, rotation_deg=17), topology=topology).meshes[0]
            self.assert_source_surface(mesh, owner, topology)
            self.assertTrue(any(all(weight > 0 for weight in row) for row in mesh.barycentric_weights))
            outputs.append(cracks.mesh_sha256(mesh))
        self.assertNotEqual(*outputs)

    def test_clockwise_source_winding_and_single_world_z_offset_are_retained(self):
        owner = deepcopy(self.owner)
        owner["pavement_sections_m"] = tuple(tuple((-x, y, 700.04 + 0.08 * y) for x, y, z in row)
                                                for row in owner["pavement_sections_m"])
        mesh = build(owner).meshes[0]
        self.assert_source_surface(mesh, owner, DIAGONAL_BC)
        self.assertTrue(all(normal[2] < 0 for normal in mesh.normals))
        for point in mesh.positions_m:
            self.assertAlmostEqual(point[2], 700.041 + 0.08 * point[1], places=11)

    def test_coincident_xy_road_levels_are_selected_only_by_exact_source_window(self):
        upper = owner_fixture(label="YACS_PERSIST_SUPPORT_002", window="nudo-0", kind="nudo",
                              y_values=(0., 1., 2., 3., 4.), height=lambda x, y: 700 + .04 * x)
        lower = owner_fixture(label="YACS_PERSIST_SUPPORT_003", window="nudo-2", kind="nudo",
                              y_values=(0., 1., 2., 3., 4.), height=lambda x, y: 680 + .04 * x)
        result = build(upper, others=(lower,))
        self.assert_source_surface(result.meshes[0], upper, DIAGONAL_BC)
        self.assertEqual({face[0] for face in cracks.needed_faces(result)}, {upper["support_label"]})
        self.assertTrue(all(point[2] > 700 for point in result.meshes[0].positions_m))
        self.assertEqual(result.manifest["counts"]["pavement_owner_count"], 2)
        self.assertEqual(result.manifest["counts"]["mesh_count"], 1)

    def test_fixed_rotation_has_continuous_shared_source_edges_and_exact_extent(self):
        for angle in (0, 17, 45, 90, -128):
            with self.subTest(angle=angle):
                result = build(self.owner, event=event_fixture(self.owner, rotation_deg=angle))
                self.assert_source_surface(result.meshes[0], self.owner, DIAGONAL_BC)
                self.assertAlmostEqual(surface_area(result.meshes[0]), 1.4 ** 2, places=12)
                u, v = (result.manifest["events"][0]["frame"][key] for key in ("u_unit", "v_unit"))
                self.assertAlmostEqual(sum(a * b for a, b in zip(u, v)), 0, places=13)
                self.assertAlmostEqual(math.hypot(*u), 1, places=13)

    def test_nudo_canary_rotates_uv_frame_90_degrees_without_moving_its_source_footprint(self):
        self.assertEqual([event.rotation_deg for event in cracks.CANARY_EVENTS], [0.0, 90.0])
        nudo = cracks.CANARY_EVENTS[1]
        self.assertEqual(nudo.station_m, 39.94374219674143)
        self.assertEqual(nudo.expected_centre_cm, (125897.40827086054, 39245.2767894417, 67462.5197009283))
        owner = owner_fixture(y_values=(0., 1., 2., 3., 4.), height=lambda x, y: .03 * x * y)
        outputs = [build(owner, event=event_fixture(owner, rotation_deg=angle)) for angle in (0.0, 90.0)]
        base_frame, rotated_frame = [result.manifest["events"][0]["frame"] for result in outputs]
        self.assertEqual(rotated_frame["origin_m"], base_frame["origin_m"])
        self.assertEqual(rotated_frame["u_unit"], base_frame["v_unit"])
        self.assertEqual(rotated_frame["v_unit"], [-value for value in base_frame["u_unit"]])
        # Quantization here is only an independent test comparison; production
        # source positions and all payload hashes retain full float64 values.
        vertices = [{tuple(round(value, 10) for value in point): uv
                     for point, uv in zip(result.meshes[0].positions_m, result.meshes[0].uv0, strict=True)}
                    for result in outputs]
        self.assertEqual(set(vertices[0]), set(vertices[1]))
        for point, (u, v) in vertices[0].items():
            actual = vertices[1][point]
            self.assertAlmostEqual(actual[0], v, places=12)
            self.assertAlmostEqual(actual[1], 1 - u, places=12)
        self.assertEqual(cracks.needed_faces(outputs[0]), cracks.needed_faces(outputs[1]))

    def test_retained_camera_anchor_mismatch_fails_without_repositioning(self):
        event = event_fixture(self.owner, expected_centre_cm=(240., 200., 0.), anchor_frame_id="fixture-frame")
        build(self.owner, event=event)
        with self.assertRaisesRegex(ValueError, "retained camera-plan"):
            build(self.owner, event=replace(event, expected_centre_cm=(240., 200., .01)))

    def test_partial_footprint_or_paint_contact_is_rejected_instead_of_silently_shrunk(self):
        with self.assertRaisesRegex(ValueError, "complete local UV square"):
            build(self.owner, event=event_fixture(self.owner, station_m=0.1))
        narrow = owner_fixture(spacing=.10, y_values=(0., 1., 2., 3., 4.))
        with self.assertRaisesRegex(ValueError, "existing edge paint"):
            build(narrow, event=event_fixture(narrow, extent_m=1.8))
        for station in (0, 4, 8):
            with self.subTest(station=station), self.assertRaisesRegex(ValueError, "source-row centreline"):
                build(self.owner, event=event_fixture(self.owner, station_m=station))

    def test_no_default_diagonal_no_alias_window_and_no_duplicate_source_events(self):
        plan = plan_fixture(self.owner)
        with self.assertRaises(TypeError):
            cracks.build_cracks(plan, events=(event_fixture(self.owner),))
        with self.assertRaisesRegex(ValueError, "exact source pavement owner"):
            build(self.owner, event=event_fixture(self.owner, window_id="window-0112"))
        event = event_fixture(self.owner)
        with self.assertRaisesRegex(ValueError, "separate event and source-window"):
            cracks.build_cracks(plan, quad_triangles=DIAGONAL_BC,
                                 events=(event, replace(event, event_id="duplicate_source")))

    def test_invalid_or_unbounded_event_data_is_rejected_before_geometry(self):
        for changes in ({"station_m": True}, {"extent_m": float("nan")}, {"extent_m": 4},
                        {"rotation_deg": 400}, {"event_id": "../escape"}, {"lateral_offset_m": 2},
                        {"expected_centre_cm": (0, 0, float("inf"))}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                build(self.owner, event=event_fixture(self.owner, **changes))
        for values in ((), (event_fixture(self.owner),) * 3, iter((event_fixture(self.owner),))):
            with self.assertRaises(ValueError):
                cracks.build_cracks(plan_fixture(self.owner), quad_triangles=DIAGONAL_BC, events=values)

    def test_sparse_mesh_hash_covers_barycentrics_uvs_winding_and_event_identity(self):
        result = build(self.owner)
        mesh, digest = result.meshes[0], result.manifest["events"][0]["mesh_sha256"]
        self.assertEqual(cracks.mesh_sha256(mesh), digest)
        for changes in ({"event_id": "other"}, {"motif_id": "other"}, {"extent_m": 1.5}, {"uv_rotation_degrees": 90.0},
                        {"barycentric_weights": ((1., 0., 0.), *mesh.barycentric_weights[1:])},
                        {"uv0": ((.5, .5), *mesh.uv0[1:])},
                        {"triangles": (tuple(reversed(mesh.triangles[0])), *mesh.triangles[1:])}):
            with self.subTest(changes=next(iter(changes))):
                self.assertNotEqual(cracks.mesh_sha256(replace(mesh, **changes)), digest)


if __name__ == "__main__":
    unittest.main()
