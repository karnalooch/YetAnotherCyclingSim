"""Synthetic full-network transactions; native BLAKE3 is tested by UE Automation.

The fake boundary hashes its in-memory fixtures with SHA256 only to exercise
readback comparisons. It is never evidence about actual native or visual PASS.
"""

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_shoulder_network as network
from scripts.ue import road_shoulder_sources as sources


def vector(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def source_plan():
    def window(index, **extra):
        return {"id": f"window-{index:04d}", "sections": [
            [(index * 10 + j * 0.2, -float(i), 0.08) for j in range(25)] for i in range(3)], **extra}
    windows = [window(i) for i in range(181)]
    windows.extend(window(i, nudo_structure=True, station_start_m=(i - 181) * 100.0)
                   for i in range(181, 184))
    windows.append(window(184, id="accepted-hairpin"))
    return {"source_identity": {"synthetic_fixture_only": True},
            "owners": sources._plan_owners({"windows": windows}, {"upper_domain_station_m": 2.0})}


class Material:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path


class Mesh:
    def __init__(self, component, owner):
        self.component = component
        if owner["kind"] == "parapet":
            self.points = list(owner["parapet_vertices_cm"])
            self.faces = list(owner["parapet_faces"])
        else:
            self.points = [point for section in owner["sections_cm"] for point in section]
            self.faces = []
            for tid in range(owner["top_triangle_count"]):
                strip, side = divmod(tid, 2)
                section, column = divmod(strip, 26)
                a = section * 27 + column
                self.faces.append((a, a + 1, a + 27) if side == 0 else (a + 1, a + 28, a + 27))
            # Existing structure face outside the authenticated top prefix.
            a = len(self.points)
            self.points.extend(((0, 0, 0), (0, 10, 0), (0, 10, -100)))
            self.faces.append((a, a + 1, a + 2))
        self.ids = [0] * len(self.faces)
        self.normal = [0.0, 0.0, 1.0]
        self.uv = [0.25, 0.5]

    def get_path_name(self):
        return self.component.get_path_name() + ".Mesh"


class Actor:
    def __init__(self, label, owner=None, harness=None):
        self.label = label
        self.location = vector(0.0, 0.0, 0.0)
        if owner is not None:
            self.component = Component(self, owner, harness)

    def get_actor_label(self):
        return self.label

    def get_path_name(self):
        return network.MAPS[1] + ".PersistentLevel." + self.label

    def get_actor_location(self):
        return self.location

    def get_actor_rotation(self):
        return SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0)

    def get_actor_scale3d(self):
        return vector(1.0, 1.0, 1.0)

    def get_dynamic_mesh_component(self):
        return self.component


class Component:
    def __init__(self, actor, owner, harness):
        self.actor, self.harness = actor, harness
        self.materials = [Material(owner["original_material_path"])]
        self.mesh = Mesh(self, owner)
        self.assignment_round = 0

    def get_owner(self):
        return self.actor

    def get_path_name(self):
        return self.actor.get_path_name() + ".DynamicMeshComponent"

    def get_dynamic_mesh(self):
        return self.mesh

    def get_num_materials(self):
        return len(self.materials)

    def get_material(self, index):
        return self.materials[index]

    def configure_material_set(self, values, delete_extra_slots):
        if delete_extra_slots is not True:
            raise AssertionError("Rollback must remove the derived slot")
        self.harness.events.append(("slots", self.actor.label, len(values)))
        self.assignment_round += len(values) == 2
        self.materials[:] = values

    def notify_mesh_modified(self):
        self.harness.events.append(("notify", self.actor.label))


class Harness:
    def __init__(self):
        self.plan = source_plan()
        self.events = []
        self.fail_assignment = None
        self.fail_restore = None
        self.actors = [Actor("YACS_PERSIST_ROAD")]
        self.actors.extend(Actor(owner["support_label"], owner, self) for owner in self.plan["owners"])
        self.components = [actor.component for actor in self.actors[1:]]
        self.instance = Material(network.MATERIAL_ROOT + "ShoulderNetwork/MI_ShoulderNetwork.MI_ShoulderNetwork")
        self.material_receipt = {"assets": {"instance": self.instance.path}, "synthetic_fixture_only": True}
        self.api = SimpleNamespace(
            YacsRoadMaterialInspectionLibrary=SimpleNamespace(inspect_mesh=self.read),
            GeometryScript_Materials=SimpleNamespace(set_triangle_material_id=self.setter),
            EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(get_all_level_actors=lambda: self.actors),
        )

    @staticmethod
    def snapshot(component, witness_count=0):
        mesh = component.mesh
        return {
            "schema_version": 2, "status": "ROAD_MATERIAL_MESH_INSPECTED", "hash_format": network.HASH_FORMAT,
            "actor_label": component.actor.label, "component_path": component.get_path_name(),
            "mesh_path": mesh.get_path_name(), "map_package": network.MAPS[1], "geometry_mutated": False,
            "material_ids_included": True, "material_ids": list(mesh.ids),
            "witness_triangle_count": witness_count,
            "witness_triangles": [[tid, *mesh.faces[tid], *(v for vid in mesh.faces[tid] for v in mesh.points[vid])]
                                  for tid in range(witness_count)],
            "summary": {
                "vertex_count": len(mesh.points), "triangle_count": len(mesh.faces), "uv_set_count": 1,
                "positions_indices_blake3": network.digest(["synthetic", mesh.points, mesh.faces]),
                "triangle_corner_normals_uv_blake3": network.digest(["synthetic", mesh.normal, mesh.uv]),
                "material_ids_blake3": network.digest(["synthetic", mesh.ids]),
            },
        }

    def read(self, component, witness_count=0):
        self.events.append(("inspect", component.actor.label, witness_count))
        return json.dumps(self.snapshot(component, witness_count), allow_nan=False)

    def setter(self, mesh, tid, value, defer_change_notifications):
        if defer_change_notifications is not True:
            raise AssertionError("Native setter must batch owner notifications")
        component = mesh.component
        self.events.append(("id", component.actor.label, tid, value))
        if value == 0 and self.fail_restore == component.actor.label:
            raise ValueError("synthetic unrecoverable restore failure")
        mesh.ids[tid] = value
        if value == 1 and self.fail_assignment == (component.actor.label, component.assignment_round, tid):
            self.fail_assignment = None
            raise ValueError("synthetic partial assignment failure")
        return mesh, True

    def prepare(self):
        with patch.object(network, "native_api_evidence", return_value={"synthetic_fixture_only": True}):
            return network.prepare(self.api, self.actors, self.plan, self.instance, self.material_receipt)


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.component = self.h.components[0]
        self.owner = self.h.plan["owners"][0]

    def read_value(self, value, count=0):
        with patch.object(self.h.api.YacsRoadMaterialInspectionLibrary, "inspect_mesh", return_value=json.dumps(value)):
            return network.inspect_mesh(self.h.api, self.component, count)

    def test_complete_ordered_source_witnesses_and_native_schema(self):
        count = self.owner["top_triangle_count"]
        actual = network.inspect_mesh(self.h.api, self.component, count)
        proof = network.verify_ownership(actual, self.owner, sources.owner_identity(self.owner))
        self.assertEqual(proof["oriented_triangles_compared"], 104)
        self.assertEqual(proof["max_source_coordinate_delta_cm"], 0)
        self.assertFalse(proof["count_only_or_label_only_ownership"])

    def test_native_schema_paths_hashes_counts_and_witnesses_fail_closed(self):
        original = self.h.snapshot(self.component, 2)
        cases = [[], {"error": "native rejected the mesh"}]
        for key, value in (("map_package", "/Game/Unrelated"), ("actor_label", "YACS_PERSIST_SUPPORT_186"),
                           ("component_path", "/wrong"), ("mesh_path", "/wrong"),
                           ("geometry_mutated", True), ("material_ids_included", False),
                           ("material_ids", []), ("witness_triangle_count", True)):
            cases.append({**original, key: value})
        for key, value in (("vertex_count", 85001), ("triangle_count", True),
                           ("uv_set_count", 5), ("positions_indices_blake3", "x" * 64)):
            cases.append({**original, "summary": {**original["summary"], key: value}})
        for row in ([1, *original["witness_triangles"][0][1:]],
                    [0, 0, 0, 27, *original["witness_triangles"][0][4:]],
                    [0, *original["witness_triangles"][0][1:4], True, *original["witness_triangles"][0][5:]]):
            cases.append({**original, "witness_triangles": [row, original["witness_triangles"][1]]})
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read_value(value, 2)

    def test_road_requires_exact_frozen_counts_and_hashes_without_large_id_array(self):
        self.component.actor.label = "YACS_PERSIST_ROAD"
        value = self.h.snapshot(self.component)
        value.update(material_ids=[], material_ids_included=False)
        value["summary"].update(vertex_count=network.ROAD_COUNTS[0], triangle_count=network.ROAD_COUNTS[1])
        self.assertEqual(self.read_value(value)["summary"]["triangle_count"], 1711760)
        for key in ("vertex_count", "triangle_count"):
            changed = deepcopy(value)
            changed["summary"][key] -= 1
            with self.assertRaisesRegex(ValueError, "exact frozen"):
                self.read_value(changed)
        with self.assertRaises(ValueError):
            self.read_value({**value, "material_ids": [0]})

    def test_matching_counts_cannot_replace_all_source_positions_and_oriented_topology(self):
        original = self.h.snapshot(self.component, self.owner["top_triangle_count"])
        moved = deepcopy(original)
        moved["witness_triangles"][-1][-1] += 0.01
        with self.assertRaisesRegex(ValueError, "immutable source coordinates"):
            network.verify_ownership(moved, self.owner, sources.owner_identity(self.owner))
        reversed_face = deepcopy(original)
        reversed_face["witness_triangles"][0][1:4] = [0, 27, 1]
        with self.assertRaisesRegex(ValueError, "connectivity changed"):
            network.verify_ownership(reversed_face, self.owner, sources.owner_identity(self.owner))

    def test_full_buffer_delta_catches_positions_indices_normals_and_uvs(self):
        before = self.h.snapshot(self.component)["summary"]
        for key, replacement in (("points", [(100, 0, 0), *self.component.mesh.points[1:]]),
                                  ("faces", [(0, 27, 1), *self.component.mesh.faces[1:]]),
                                  ("normal", [1, 0, 0]), ("uv", [0, 0])):
            old = getattr(self.component.mesh, key)
            setattr(self.component.mesh, key, replacement)
            with self.subTest(buffer=key), self.assertRaisesRegex(ValueError, "full positions"):
                network.verify_delta(before, self.h.snapshot(self.component), self.owner, assigned=False)
            setattr(self.component.mesh, key, old)

    def test_only_source_outer_top_ids_change_and_parapet_remains_literal(self):
        before = self.h.snapshot(self.component)["summary"]
        for tid in self.owner["selected_triangle_ids"]:
            self.component.mesh.ids[tid] = 1
        network.verify_delta(before, self.h.snapshot(self.component), self.owner, assigned=True)
        for tid in (2, self.owner["top_triangle_count"]):
            self.component.mesh.ids[tid] = 1
            with self.assertRaisesRegex(ValueError, "wall/interior/parapet"):
                network.verify_delta(before, self.h.snapshot(self.component), self.owner, assigned=True)
            self.component.mesh.ids[tid] = 0
        parapet, owner = self.h.components[181], self.h.plan["owners"][181]
        before = self.h.snapshot(parapet)["summary"]
        parapet.mesh.ids[0] = 1
        with self.assertRaisesRegex(ValueError, "wall/interior/parapet"):
            network.verify_delta(before, self.h.snapshot(parapet), owner, assigned=True)


class NetworkTransactionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()

    def assert_restored(self):
        for owner, component in zip(self.h.plan["owners"], self.h.components, strict=True):
            self.assertTrue(all(value == 0 for value in component.mesh.ids))
            self.assertEqual(component.get_num_materials(), 1)
            self.assertEqual(component.get_material(0).path, owner["original_material_path"])

    def test_all_186_owners_preflight_before_first_assignment_and_real_rollback_proof(self):
        receipt, state = self.h.prepare()
        first_write = next(i for i, row in enumerate(self.h.events) if row[0] == "slots")
        self.assertEqual(first_write, 186)
        self.assertEqual([row[1] for row in self.h.events[:first_write]],
                         [owner["support_label"] for owner in self.h.plan["owners"]])
        self.assertTrue(all(row[2] > 0 for row in self.h.events[:first_write]))
        self.assertEqual(sum(row[0] == "inspect" for row in self.h.events), 4 * 186)
        self.assertFalse(any(row[0] in ("slots", "id") and row[1] == "YACS_PERSIST_SUPPORT_181"
                             for row in self.h.events))
        self.assertEqual(receipt["material_target_count"], 185)
        self.assertEqual(receipt["excluded_parapet_count"], 1)
        self.assertEqual(receipt["rollback_proof"]["support_count"], 186)
        self.assertFalse(receipt["whole_area_admitted"])
        self.assertFalse(receipt["performance_pass"])
        for row in receipt["owners"]:
            self.assertNotIn("selected_triangle_ids", row)
            self.assertEqual(row["selected_triangle_count"], len(row["source"]["selected_triangle_ids"]))
        proof = network.rollback(self.h.api, state)
        self.assertEqual(proof["aggregate_meshes_sha256"], receipt["rollback_proof"]["aggregate_meshes_sha256"])
        self.assertEqual(state["attempted"], [])
        self.assert_restored()

    def test_missing_duplicate_reordered_or_transformed_owners_fail_before_assignment(self):
        for change in ("missing", "duplicate", "reordered", "transformed"):
            self.h = Harness()
            if change == "missing":
                self.h.actors.pop()
            elif change == "duplicate":
                self.h.actors[-1].label = self.h.actors[-2].label
            elif change == "reordered":
                self.h.plan["owners"][-2:] = self.h.plan["owners"][-2:][::-1]
            else:
                self.h.actors[-1].location.z = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.h.prepare()
            self.assertFalse(any(row[0] in ("slots", "id") for row in self.h.events))

    def test_last_native_source_mismatch_prevents_every_assignment(self):
        self.h.components[-1].mesh.points[0] = (100, 100, 100)
        with self.assertRaisesRegex(ValueError, "immutable source coordinates"):
            self.h.prepare()
        self.assertFalse(any(row[0] in ("slots", "id") for row in self.h.events))
        self.assert_restored()

    def test_partial_failure_in_both_apply_rounds_rolls_back_every_attempted_owner(self):
        for attempt in (1, 2):
            self.h = Harness()
            self.h.fail_assignment = ("YACS_PERSIST_SUPPORT_080", attempt, 50)
            with self.subTest(attempt=attempt), self.assertRaisesRegex(ValueError, "partial assignment"):
                self.h.prepare()
            self.assert_restored()
            self.assertEqual([row[1] for row in self.h.events[-186:]],
                             [owner["support_label"] for owner in self.h.plan["owners"]])
            self.assertTrue(all(row[0] == "inspect" for row in self.h.events[-186:]))

    def test_rollback_error_remains_failure_and_other_owners_and_slots_are_restored(self):
        _, state = self.h.prepare()
        self.h.fail_restore = "YACS_PERSIST_SUPPORT_080"
        with self.assertRaisesRegex(ValueError, "Full-network rollback failed.*restore failure"):
            network.rollback(self.h.api, state)
        self.assertTrue(state["attempted"])
        self.assertEqual(self.h.components[80].get_num_materials(), 1)
        self.assertTrue(all(all(value == 0 for value in component.mesh.ids)
                            for i, component in enumerate(self.h.components) if i != 80))

    def test_fresh_load_reauthenticates_sources_and_full_buffers_without_any_setter(self):
        receipt, _ = self.h.prepare()
        loaded = json.loads(json.dumps(receipt))
        self.h.events.clear()
        with patch.object(sources, "load_sources", return_value=self.h.plan) as loader:
            self.assertEqual(network.verify_loaded(self.h.api, loaded), receipt["aggregate_after_sha256"])
        loader.assert_called_once_with()
        self.assertEqual(len(self.h.events), 186)
        self.assertTrue(all(row[0] == "inspect" and row[2] == 0 for row in self.h.events))
        self.h.components[-1].mesh.normal = [1, 0, 0]
        with self.assertRaisesRegex(ValueError, "Fresh full native mesh"):
            network.verify_loaded(self.h.api, loaded, self.h.plan)

    def test_fresh_load_rejects_receipt_identity_totals_rollback_and_material_slot_tampering(self):
        receipt, _ = self.h.prepare()
        cases = []
        for key, value in (("selected_triangle_count", receipt["selected_triangle_count"] + 1),
                           ("total_vertex_count", receipt["total_vertex_count"] + 1),
                           ("rollback_proof", {}), ("original_wall_material_preserved", False)):
            cases.append({**receipt, key: value})
        for field in ("source", "summary", "ownership"):
            changed = deepcopy(receipt)
            if field == "source":
                changed["owners"][0]["source"]["selected_triangle_ids"].append(2)
            elif field == "summary":
                changed["owners"][0]["selected_triangle_count"] += 1
            else:
                changed["owners"][0]["ownership"]["count_only_or_label_only_ownership"] = True
            cases.append(changed)
        for value in cases:
            with self.subTest(change=value.keys()), self.assertRaises(ValueError):
                network.verify_loaded(self.h.api, value, self.h.plan)
        self.h.components[182].materials[0] = Material("/wrong/wall")
        with self.assertRaisesRegex(ValueError, "Literal original"):
            network.verify_loaded(self.h.api, receipt, self.h.plan)


if __name__ == "__main__":
    unittest.main()
