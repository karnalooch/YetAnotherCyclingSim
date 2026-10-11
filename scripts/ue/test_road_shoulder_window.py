"""Synthetic source/mesh tests; no native or visual proof is fabricated here."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from scripts.ue import road_shoulder_window as shoulder


def vector(values):
    return SimpleNamespace(**dict(zip(("x", "y", "z"), values, strict=True)))


class Mesh:
    def __init__(self):
        self.sections = [[(j * 0.2, float(i), 0.08) for j in range(25)] for i in range(110)]
        self.points = [tuple(p) for i in range(110)
                       for p in [(-50, i * 100, 0),
                                 *((j * 20, i * 100, 0) for j in range(25)),
                                 (530, i * 100, 0)]]
        self.faces = []
        for i in range(109):
            for j in range(26):
                a, b, c, d = i * 27 + j, i * 27 + j + 1, (i + 1) * 27 + j, (i + 1) * 27 + j + 1
                self.faces.extend(((a, b, c), (b, d, c)))
        offset = len(self.points)
        self.points.extend(((-50, 0, 0), (-50, 100, 0), (-50, 100, -100), (-50, 0, -100)))
        self.faces.extend(((offset, offset + 1, offset + 2), (offset, offset + 2, offset + 3)))
        self.ids = [0] * len(self.faces)
        self.normal = (0.0, 0.0, 1.0)
        self.uv = (0.25, 0.5)

    def get_vertex_count(self):
        return len(self.points)

    def get_triangle_count(self):
        return len(self.faces)

    def get_num_uv_sets(self):
        return 1

    def get_triangle_material_id(self, tid):
        return self.ids[tid], True


class Queries:
    @staticmethod
    def get_num_vertex_i_ds(mesh):
        return len(mesh.points)

    @staticmethod
    def get_num_triangle_i_ds(mesh):
        return len(mesh.faces)

    @staticmethod
    def get_vertex_position(mesh, vid):
        return vector(mesh.points[vid]), True

    @staticmethod
    def get_triangle_indices(mesh, tid):
        return vector(mesh.faces[tid]), True

    @staticmethod
    def get_triangle_normals(mesh, tid):
        return mesh, *(vector(mesh.normal) for _ in range(3)), True

    @staticmethod
    def get_triangle_u_vs(mesh, layer, tid):
        return *(SimpleNamespace(x=mesh.uv[0], y=mesh.uv[1]) for _ in range(3)), True


class WindowShoulderTests(unittest.TestCase):
    def setUp(self):
        self.mesh = Mesh()
        self.api = SimpleNamespace(GeometryScript_MeshQueries=Queries)
        self.before = shoulder.read_mesh(self.api, self.mesh)

    def apply_ids(self):
        for tid in shoulder.SHOULDER_IDS:
            self.mesh.ids[tid] = 1
        return shoulder.read_mesh(self.api, self.mesh)

    def test_exact_outer_strip_selection_excludes_interior_and_walls(self):
        selection = shoulder.verify_selection(self.before, self.mesh.sections)
        self.assertEqual(selection["selected_triangle_count"], 436)
        self.assertEqual(selection["min_shoulder_width_m"], 0.5)
        self.assertEqual(selection["max_shoulder_width_m"], 0.5)
        for tid in shoulder.SHOULDER_IDS:
            self.assertIn(tid % 52, (0, 1, 50, 51))
            self.assertLess(tid, shoulder.TOP_TRIANGLES)
        after = self.apply_ids()
        shoulder.verify_mesh_delta(self.before, after)
        self.assertEqual(after["material_ids"][2], 0)
        self.assertEqual(after["material_ids"][-1], 0)

    def test_same_counts_but_changed_position_normal_or_uv_fail(self):
        self.apply_ids()
        for field, replacement in (
            ("points", [(1, 2, 3), *self.mesh.points[1:]]),
            ("normal", (0, 1, 0)),
            ("uv", (0.1, 0.5)),
        ):
            old = getattr(self.mesh, field)
            setattr(self.mesh, field, replacement)
            with self.assertRaisesRegex(ValueError, "positions, topology, normals or UVs"):
                shoulder.verify_mesh_delta(self.before, shoulder.read_mesh(self.api, self.mesh))
            setattr(self.mesh, field, old)

    def test_wall_or_under_road_material_changes_are_rejected(self):
        self.apply_ids()
        for tid in (2, shoulder.TOP_TRIANGLES):
            self.mesh.ids[tid] = 1
            with self.assertRaisesRegex(ValueError, "Unexpected wall/interior"):
                shoulder.verify_mesh_delta(self.before, shoulder.read_mesh(self.api, self.mesh))
            self.mesh.ids[tid] = 0
        with self.assertRaisesRegex(ValueError, "selection widened"):
            shoulder.verify_mesh_delta(self.before, self.apply_ids(), (*shoulder.SHOULDER_IDS, 2))

    def test_source_owner_requires_coordinate_and_topology_correspondence(self):
        changed = deepcopy(self.before)
        changed["points"][1] = (0, 0, 1)
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            shoulder.verify_selection(changed, self.mesh.sections)
        changed = deepcopy(self.before)
        changed["faces"][0] = (0, 27, 1)
        with self.assertRaisesRegex(ValueError, "top triangle topology"):
            shoulder.verify_selection(changed, self.mesh.sections)

    def test_unknown_structure_face_cannot_become_a_shoulder(self):
        changed = deepcopy(self.before)
        changed["points"][-1] = (50, 0, -100)
        with self.assertRaisesRegex(ValueError, "nonvertical"):
            shoulder.verify_selection(changed, self.mesh.sections)

    def component_and_setter(self, fail_once=False):
        old = SimpleNamespace(get_path_name=lambda: shoulder.OLD_MATERIAL)
        gravel = SimpleNamespace(get_path_name=lambda: "/synthetic/gravel")
        materials = [old]
        failed = False

        def configure(values, delete_extra_slots):
            self.assertTrue(delete_extra_slots)
            materials[:] = values

        def setter(mesh, tid, value, defer_change_notifications):
            nonlocal failed
            self.assertTrue(defer_change_notifications)
            if fail_once and value == 1 and tid == shoulder.SHOULDER_IDS[2] and not failed:
                failed = True
                raise ValueError("synthetic partial native assignment failure")
            mesh.ids[tid] = value
            return mesh, True

        component = SimpleNamespace(get_num_materials=lambda: len(materials),
            get_material=lambda slot: materials[slot], get_dynamic_mesh=lambda: self.mesh,
            configure_material_set=configure, notify_mesh_modified=lambda: None)
        self.api.GeometryScript_Materials = SimpleNamespace(set_triangle_material_id=setter)
        return component, gravel, old

    def test_partial_native_failure_restores_every_id_and_the_single_old_slot(self):
        component, gravel, old = self.component_and_setter(fail_once=True)
        with self.assertRaisesRegex(ValueError, "partial native"):
            shoulder.apply_with_rollback_proof(self.api, component, gravel, self.before)
        self.assertTrue(all(value == 0 for value in self.mesh.ids))
        self.assertEqual(component.get_num_materials(), 1)
        self.assertIs(component.get_material(0), old)
        self.assertEqual(shoulder.read_mesh(self.api, self.mesh)["summary"], self.before["summary"])

    def test_success_preserves_original_wall_material_and_exact_geometry(self):
        component, gravel, old = self.component_and_setter()
        after = shoulder.apply_with_rollback_proof(self.api, component, gravel, self.before)
        self.assertEqual(component.get_num_materials(), 2)
        self.assertIs(component.get_material(0), old)
        self.assertIs(component.get_material(1), gravel)
        shoulder.verify_mesh_delta(self.before, after)


if __name__ == "__main__":
    unittest.main()
