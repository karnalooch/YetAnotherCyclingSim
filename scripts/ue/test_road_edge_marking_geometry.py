"""Source surface, continuity and ownership tests; no native/visual PASS claim."""

from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
import unittest
from unittest.mock import patch

from scripts.ue import road_edge_marking_geometry as markings


DIAGONAL_BC = ((0, 1, 2), (1, 3, 2))
DIAGONAL_AD = ((0, 1, 3), (0, 3, 2))


def owner_fixture(*, label="YACS_PERSIST_SUPPORT_000", window="fixture-window-0",
                  spacing=0.2, y_values=(0., 1.), height=None, kind="ordinary"):
    height = height or (lambda x, y: 0.)
    rows = tuple(tuple((j * spacing, y, height(j * spacing, y)) for j in range(25)) for y in y_values)
    return {"support_label": label, "window_id": window, "kind": kind, "material_target": True,
            "section_count": len(rows), "pavement_sections_m": rows}


def plan_fixture(*owners):
    targets = sum(owner["material_target"] for owner in owners)
    return {"source_identity": {"support_source_schema_version": 1, "support_count": len(owners),
                                "material_target_count": targets, "excluded_parapet_count": len(owners) - targets,
                                "geometry_consumers_executed": False, "geometry_authored": False,
                                "fixture_only": True, "recipe_sha256": "a" * 64},
            "owners": list(owners)}


def build(*owners, topology=DIAGONAL_BC, appearance=markings.MarkingAppearance()):
    return markings.build_markings(plan_fixture(*owners), quad_triangles=topology, appearance=appearance)


def cross(a, b, c):
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def surface_area(mesh):
    return sum(math.hypot(*cross(*(mesh.positions_m[index] for index in face))) / 2 for face in mesh.triangles)


def height_at_xy(mesh, x, y):
    heights = []
    for face in mesh.triangles:
        a, b, c = [mesh.positions_m[index] for index in face]
        determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        first = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
        second = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
        third = 1 - first - second
        if min(first, second, third) >= -1e-10:
            heights.append(first * a[2] + second * b[2] + third * c[2])
    if not heights:
        raise AssertionError("No paint triangle covers the requested interior point")
    if max(heights) - min(heights) > 1e-10:
        raise AssertionError("Overlapping paint fragments disagree about the source surface")
    return heights[0]


class MarkingGeometryTests(unittest.TestCase):
    def assert_source_support(self, mesh, owner, topology, offset=0.001):
        corner_offsets = ((0, 0), (0, 1), (1, 0), (1, 1))
        visited_vertices, visited_triangles = set(), set()
        for fragment in mesh.fragments:
            section, cell, slot = fragment.source_triangle
            source = [owner["pavement_sections_m"][section + corner_offsets[index][0]][cell + corner_offsets[index][1]]
                      for index in topology[slot]]
            face_cross = cross(*source)
            normal = tuple(value / math.hypot(*face_cross) for value in face_cross)
            vertex_ids = range(fragment.first_vertex, fragment.first_vertex + fragment.vertex_count)
            triangle_ids = range(fragment.first_triangle, fragment.first_triangle + fragment.triangle_count)
            self.assertTrue(visited_vertices.isdisjoint(vertex_ids))
            self.assertTrue(visited_triangles.isdisjoint(triangle_ids))
            visited_vertices.update(vertex_ids)
            visited_triangles.update(triangle_ids)
            for index in vertex_ids:
                weights = mesh.barycentric_weights[index]
                self.assertGreaterEqual(min(weights), 0)
                self.assertAlmostEqual(sum(weights), 1., places=14)
                expected = [sum(weights[j] * source[j][axis] for j in range(3)) for axis in range(3)]
                expected[2] += offset
                for actual, wanted in zip(mesh.positions_m[index], expected):
                    self.assertAlmostEqual(actual, wanted, places=10)
                for actual, wanted in zip(mesh.normals[index], normal):
                    self.assertAlmostEqual(actual, wanted, places=14)
            for triangle_id in triangle_ids:
                face = mesh.triangles[triangle_id]
                self.assertTrue(set(face).issubset(vertex_ids))
                output_cross = cross(*(mesh.positions_m[index] for index in face))
                self.assertGreater(sum(a * b for a, b in zip(output_cross, normal)), 0.)
        self.assertEqual(visited_vertices, set(range(len(mesh.positions_m))))
        self.assertEqual(visited_triangles, set(range(len(mesh.triangles))))

    def assert_single_continuous_band(self, mesh):
        # Exact position keys deliberately catch split faces that only almost
        # coincide. All internal triangle edges must cancel in pairs; the
        # remaining boundary must be one closed loop without holes or branches.
        edges = Counter()
        for face in mesh.triangles:
            points = [mesh.positions_m[index] for index in face]
            for a, b in zip(points, points[1:] + points[:1]):
                edges[tuple(sorted((a, b)))] += 1
        self.assertTrue(all(count in (1, 2) for count in edges.values()))
        adjacency = defaultdict(set)
        for (a, b), count in edges.items():
            if count == 1:
                adjacency[a].add(b)
                adjacency[b].add(a)
        self.assertTrue(adjacency)
        self.assertTrue(all(len(neighbours) == 2 for neighbours in adjacency.values()))
        seen, pending = set(), [next(iter(adjacency))]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(adjacency[current] - seen)
        self.assertEqual(seen, set(adjacency))

    def test_flat_bands_use_requested_metric_setback_width_and_both_edge_uv_directions(self):
        owner = owner_fixture(y_values=(0., 1., 2.))
        result = build(owner)
        self.assertEqual([mesh.edge for mesh in result.meshes], ["edge0", "edge24"])
        for mesh in result.meshes:
            self.assertAlmostEqual(surface_area(mesh), 0.10 * 2, places=13)
            self.assert_source_support(mesh, owner, DIAGONAL_BC)
            self.assert_single_continuous_band(mesh)
            for point, (u, v) in zip(mesh.positions_m, mesh.uv0):
                distance = point[0] if mesh.edge == "edge0" else 4.8 - point[0]
                self.assertGreaterEqual(distance, 0.12 - 1e-14)
                self.assertLessEqual(distance, 0.22 + 1e-14)
                self.assertAlmostEqual(distance, 0.12 + 0.1 * u, places=13)
                self.assertAlmostEqual(v, point[1], places=13)
                self.assertEqual(point[2], 0.001)
            self.assertEqual(min(uv[0] for uv in mesh.uv0), 0)
            self.assertEqual(max(uv[0] for uv in mesh.uv0), 1)

    def test_twisted_quad_follows_each_actual_diagonal_and_not_bilinear_surface(self):
        owner = owner_fixture(height=lambda x, y: 0.3 * x * y)
        expected_height = {DIAGONAL_BC: 0.015, DIAGONAL_AD: 0.03}
        for topology in (DIAGONAL_BC, DIAGONAL_AD):
            with self.subTest(topology=topology):
                result = build(owner, topology=topology)
                for mesh in result.meshes:
                    self.assert_source_support(mesh, owner, topology)
                    self.assert_single_continuous_band(mesh)
                # Bilinear interpolation would put this point at 0.0225 m,
                # leaving BOTH possible saved triangle planes incorrectly.
                self.assertAlmostEqual(height_at_xy(result.meshes[0], 0.15, 0.5) - 0.001,
                                       expected_height[topology], places=13)
                self.assertNotAlmostEqual(expected_height[topology], 0.3 * 0.15 * 0.5, places=6)

    def test_band_can_cross_multiple_lateral_cells_without_gaps_or_overdraw(self):
        owner = owner_fixture(spacing=0.05, y_values=(0., 0.75, 2.))
        result = build(owner)
        for mesh, expected in zip(result.meshes, ({2, 3, 4}, {19, 20, 21})):
            self.assertEqual({fragment.source_triangle[1] for fragment in mesh.fragments}, expected)
            self.assertAlmostEqual(surface_area(mesh), 0.2, places=13)
            self.assert_single_continuous_band(mesh)
            self.assert_source_support(mesh, owner, DIAGONAL_BC)

    def test_varying_row_width_clips_five_vertex_fragments_across_cell_boundaries(self):
        owner = owner_fixture(y_values=(0., 1., 2.))
        owner["pavement_sections_m"] = tuple(tuple((column * spacing, float(row), 0.) for column in range(25))
                                              for row, spacing in enumerate((0.05, 0.2, 0.09)))
        result = build(owner)
        self.assertTrue(any(fragment.vertex_count == 5 for mesh in result.meshes for fragment in mesh.fragments))
        for mesh in result.meshes:
            self.assertAlmostEqual(surface_area(mesh), 0.2, places=13)
            self.assert_single_continuous_band(mesh)
            self.assert_source_support(mesh, owner, DIAGONAL_BC)

    def test_band_boundaries_on_source_vertices_do_not_emit_zero_area_or_duplicate_faces(self):
        owner = owner_fixture(spacing=0.125, y_values=(0., 1., 2.))
        appearance = markings.MarkingAppearance(width_m=0.125, setback_m=0.125)
        for mesh, cells in zip(build(owner, appearance=appearance).meshes, ({1}, {22})):
            self.assertEqual({fragment.source_triangle[1] for fragment in mesh.fragments}, cells)
            self.assertAlmostEqual(surface_area(mesh), 0.25, places=14)
            self.assert_single_continuous_band(mesh)
            self.assert_source_support(mesh, owner, DIAGONAL_BC)

    def test_shared_vertices_and_uvs_coincide_exactly_under_twist_and_world_translation(self):
        owner = owner_fixture(y_values=(0., 0.7, 2.), height=lambda x, y: x * y * 0.11)
        owner["pavement_sections_m"] = tuple(tuple((x + 12345.125, y - 5321.875, z + 750.125)
                                                  for x, y, z in row) for row in owner["pavement_sections_m"])
        for topology in (DIAGONAL_BC, DIAGONAL_AD):
            for mesh in build(owner, topology=topology).meshes:
                self.assert_source_support(mesh, owner, topology)
                self.assert_single_continuous_band(mesh)
                uv_at_position = {}
                for position, uv in zip(mesh.positions_m, mesh.uv0):
                    if position in uv_at_position:
                        self.assertEqual(uv, uv_at_position[position])
                    uv_at_position[position] = uv

    def test_source_ordered_normals_survive_reversed_winding_and_offset_stays_positive_z(self):
        owner = owner_fixture(height=lambda x, y: 0.04 + 0.1 * x)
        reversed_topology = tuple((a, c, b) for a, b, c in DIAGONAL_BC)
        result = build(owner, topology=reversed_topology)
        self.assertEqual(result.manifest["owners"][0]["ordered_source_normal_z_sign"], -1)
        for mesh in result.meshes:
            self.assert_source_support(mesh, owner, reversed_topology)
            self.assertTrue(all(normal[2] < 0 for normal in mesh.normals))
            for x, _, z in mesh.positions_m:
                self.assertAlmostEqual(z, 0.04 + 0.1 * x + 0.001, places=13)

    def test_three_dimensional_cross_section_distance_and_boundary_station_are_explicit(self):
        owner = owner_fixture(height=lambda x, y: 0.3 * x + 0.2 * y, y_values=(0., 1., 3.))
        result = build(owner)
        for mesh in result.meshes:
            for (x, y, _), (u, v) in zip(mesh.positions_m, mesh.uv0):
                cross_distance = (x if mesh.edge == "edge0" else 4.8 - x) * math.sqrt(1.09)
                self.assertAlmostEqual(cross_distance, 0.12 + 0.1 * u, places=13)
                self.assertAlmostEqual(v, y * math.sqrt(1.04), places=13)

    def test_coincident_owner_seams_remain_separate_and_each_station_restarts(self):
        first = owner_fixture()
        second = owner_fixture(label="YACS_PERSIST_SUPPORT_001", window="fixture-window-1", y_values=(1., 2.))
        result = build(first, second)
        self.assertEqual(len(result.meshes), 4)
        for left, right in zip(result.meshes[:2], result.meshes[2:]):
            self.assertNotEqual(left.owner_label, right.owner_label)
            end = {point for point in left.positions_m if point[1] == 1}
            start = {point for point in right.positions_m if point[1] == 1}
            self.assertEqual(end, start)
            self.assertTrue(all(uv[1] == 0 for point, uv in zip(right.positions_m, right.uv0) if point[1] == 1))
            self.assertTrue(all(uv[1] == 1 for point, uv in zip(left.positions_m, left.uv0) if point[1] == 1))
            self.assert_source_support(left, first, DIAGONAL_BC)
            self.assert_source_support(right, second, DIAGONAL_BC)
            self.assert_single_continuous_band(left)
            self.assert_single_continuous_band(right)
        second["pavement_sections_m"] = tuple(tuple((x + 80, y + 40, z) for x, y, z in row)
                                                  for row in second["pavement_sections_m"])
        moved = build(first, second)
        self.assertEqual(moved.meshes[:2], result.meshes[:2])
        self.assertTrue(all(point[0] >= 80 for mesh in moved.meshes[2:] for point in mesh.positions_m))
        self.assertEqual(moved.manifest["counts"]["triangle_count"], result.manifest["counts"]["triangle_count"])

    def test_excluded_parapet_can_share_window_but_never_acquires_paint(self):
        owner = owner_fixture(kind="nudo")
        parapet = {"support_label": "YACS_PERSIST_SUPPORT_001", "window_id": owner["window_id"],
                   "kind": "parapet", "material_target": False}
        result = build(parapet, owner)
        self.assertEqual({mesh.owner_label for mesh in result.meshes}, {owner["support_label"]})
        self.assertEqual(result.manifest["counts"]["excluded_parapet_count"], 1)
        self.assertEqual(result.manifest["excluded_owners"][0]["support_label"], parapet["support_label"])

    def test_deterministic_separate_payload_hashes_and_no_input_mutation_or_extra_hairpin_lift(self):
        owner = owner_fixture(kind="hairpin", height=lambda x, y: 100.04)
        plan = plan_fixture(owner)
        before = deepcopy(plan)
        first = markings.build_markings(plan, quad_triangles=DIAGONAL_BC)
        second = markings.build_markings(plan, quad_triangles=DIAGONAL_BC)
        self.assertEqual(plan, before)
        self.assertEqual(first, second)
        raw = json.dumps(first.manifest, sort_keys=True)
        self.assertLess(len(raw), 10000)
        for field in ("positions_m", "pavement_sections_m", "barycentric_weights"):
            self.assertNotIn('"' + field + '"', raw)
        for mesh, edge in zip(first.meshes, first.manifest["owners"][0]["edges"]):
            self.assertEqual(markings.mesh_sha256(mesh), edge["mesh_sha256"])
            for point in mesh.positions_m:
                self.assertAlmostEqual(point[2], 100.041, places=12)
        original_source_hash = first.manifest["owners"][0]["pavement_sections_sha256"]
        owner["pavement_sections_m"] = tuple(tuple((x, y, z + 0.0001) for x, y, z in row)
                                              for row in owner["pavement_sections_m"])
        changed = build(owner)
        self.assertNotEqual(changed.manifest["owners"][0]["pavement_sections_sha256"], original_source_hash)
        self.assertNotEqual(changed.manifest["owners"][0]["edges"][0]["mesh_sha256"],
                            first.manifest["owners"][0]["edges"][0]["mesh_sha256"])

    def test_manifest_describes_required_consumer_without_granting_runtime_acceptance(self):
        manifest = build(owner_fixture()).manifest
        self.assertEqual(manifest["source_triangle_layout"]["quad_triangles"], [[0, 1, 2], [1, 3, 2]])
        self.assertFalse(manifest["source_triangle_layout"]["native_triangle_ids_inferred"])
        self.assertEqual(manifest["required_native_consumer"], {"collision_enabled": "NO_COLLISION", "cast_shadow": False,
                                                               "affects_navigation": False, "source_triangle_readback": True})
        for field in ("source_geometry_mutated", "road_uv_mutated", "physics_authored", "native_surface_correspondence_verified",
                      "native_consumer_verified", "owner_visual_pass", "performance_pass"):
            self.assertIs(manifest[field], False)
        self.assertEqual(manifest["performance_status"], "DEFERRED_AFTER_M3")
        self.assertFalse(manifest["appearance"]["legal_standard_claimed"])
        self.assertEqual(manifest["material_uv_contract"], {"channel": 0, "u": "normalized_paint_width", "u_range": [0., 1.],
                                                            "v": "edge_station_metres", "line_width_cm": 10.})

    def test_missing_ambiguous_inconsistent_or_duplicate_source_triangle_layout_fails(self):
        with self.assertRaises(TypeError):
            markings.build_markings(plan_fixture(owner_fixture()))
        for topology in (None, (), ((0, 1, 2),), ((0, 1, 2), (0, 1, 2)),
                         ((0, 1, 2), (0, 1, 3)), ((0, 1, 2), (1, 2, 3)),
                         ((0, 1, 2), (1, 4, 2)), ((0, 1, 2), (True, 3, 2))):
            with self.subTest(topology=topology), self.assertRaises(ValueError):
                build(owner_fixture(), topology=topology)

    def test_degenerate_folded_nonfinite_or_malformed_source_fails_including_unpainted_interior(self):
        for change in ("lateral_duplicate", "boundary_duplicate", "interior_degenerate", "interior_fold",
                       "nan", "coordinate_bound", "wrong_columns", "wrong_xyz", "wrong_count", "too_narrow"):
            owner = owner_fixture()
            rows = [list(row) for row in owner["pavement_sections_m"]]
            if change == "lateral_duplicate":
                rows[0][12] = rows[0][11]
            elif change == "boundary_duplicate":
                rows[1][0] = rows[0][0]
            elif change == "interior_degenerate":
                rows[1][12] = rows[0][12]
            elif change == "interior_fold":
                rows[1][12] = (rows[1][12][0], -1., 0.)
            elif change == "nan":
                rows[0][12] = (float("nan"), 0., 0.)
            elif change == "coordinate_bound":
                rows[0][12] = (1000001., 0., 0.)
            elif change == "wrong_columns":
                rows[0].pop()
            elif change == "wrong_xyz":
                rows[0][12] = (1., 2.)
            elif change == "wrong_count":
                owner["section_count"] = 3
            else:
                rows = [list(row) for row in owner_fixture(spacing=0.01)["pavement_sections_m"]]
            owner["pavement_sections_m"] = rows
            with self.subTest(change=change), self.assertRaises(ValueError):
                build(owner)

    def test_owner_identity_mismatch_or_duplicate_ownership_fails_closed(self):
        for change in ("identity_count", "identity_execution", "identity_nan", "duplicate_label", "duplicate_window",
                       "target_not_bool", "unknown_exclusion", "no_pavement"):
            owner = owner_fixture()
            plan = plan_fixture(owner)
            if change == "identity_count":
                plan["source_identity"]["material_target_count"] = 2
            elif change == "identity_execution":
                plan["source_identity"]["geometry_consumers_executed"] = True
            elif change == "identity_nan":
                plan["source_identity"]["extra"] = float("nan")
            elif change in ("duplicate_label", "duplicate_window"):
                second = owner_fixture(label=owner["support_label"] if change == "duplicate_label" else "OTHER",
                                       window=owner["window_id"] if change == "duplicate_window" else "other-window")
                plan = plan_fixture(owner, second)
            elif change == "target_not_bool":
                owner["material_target"] = 1
            elif change == "unknown_exclusion":
                owner["material_target"] = False
            else:
                owner.update(material_target=False, kind="parapet")
                plan = plan_fixture(owner)
            with self.subTest(change=change), self.assertRaises(ValueError):
                markings.build_markings(plan, quad_triangles=DIAGONAL_BC)

    def test_appearance_and_resource_bounds_fail_without_mutating_source(self):
        for appearance in (markings.MarkingAppearance(width_m=0), markings.MarkingAppearance(width_m=True),
                           markings.MarkingAppearance(width_m=float("inf")), markings.MarkingAppearance(width_m=0.6),
                           markings.MarkingAppearance(setback_m=-0.1), markings.MarkingAppearance(setback_m=2.1),
                           markings.MarkingAppearance(surface_offset_m=-0.001), markings.MarkingAppearance(surface_offset_m=0.006)):
            with self.subTest(appearance=appearance), self.assertRaises(ValueError):
                build(owner_fixture(), appearance=appearance)
        for name in ("MAX_OUTPUT_VERTICES", "MAX_OUTPUT_TRIANGLES", "MAX_MANIFEST_BYTES", "MAX_SOURCE_IDENTITY_BYTES",
                     "MAX_TOTAL_SECTIONS", "MAX_SECTIONS_PER_OWNER", "MAX_OWNERS"):
            plan = plan_fixture(owner_fixture())
            before = deepcopy(plan)
            with self.subTest(bound=name), patch.object(markings, name, 0 if name == "MAX_OWNERS" else 1), self.assertRaises(ValueError):
                markings.build_markings(plan, quad_triangles=DIAGONAL_BC)
            self.assertEqual(plan, before)


if __name__ == "__main__":
    unittest.main()
