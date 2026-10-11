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
from scripts.ue import road_shoulder_edges as edges
from scripts.ue import road_shoulder_material as material


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
        self.uv_layers = []

    def get_path_name(self):
        return self.component.get_path_name() + ".Mesh"

    def get_num_uv_sets(self):
        return len(self.uv_layers)


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
        self.fail_uv_assignment = None
        self.fail_outer_uv_assignment = None
        self.actors = [Actor("YACS_PERSIST_ROAD")]
        self.actors.extend(Actor(owner["support_label"], owner, self) for owner in self.plan["owners"])
        self.components = [actor.component for actor in self.actors[1:]]
        self.instance = Material(network.MATERIAL_ROOT + "ShoulderNetwork/MI_ShoulderNetwork.MI_ShoulderNetwork")
        self.material_receipt = {"assets": {"instance": self.instance.path}, "synthetic_fixture_only": True}
        self.api = SimpleNamespace(
            YacsRoadMaterialInspectionLibrary=SimpleNamespace(inspect_mesh=self.read),
            GeometryScript_Materials=SimpleNamespace(set_triangle_material_id=self.setter),
            GeometryScript_UVs=SimpleNamespace(set_num_uv_sets=self.set_num_uv_sets,
                                               set_mesh_triangle_u_vs=self.set_triangle_uvs),
            GeometryScriptUVTriangle=lambda **kwargs: SimpleNamespace(**kwargs),
            Vector2D=lambda x, y: (x, y),
            EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(get_all_level_actors=lambda: self.actors),
        )

    @staticmethod
    def snapshot(component, witness_count=0, preserved_uv_set_count=-1):
        mesh = component.mesh
        value = {
            "schema_version": 2, "status": "ROAD_MATERIAL_MESH_INSPECTED", "hash_format": network.HASH_FORMAT,
            "actor_label": component.actor.label, "component_path": component.get_path_name(),
            "mesh_path": mesh.get_path_name(), "map_package": network.MAPS[1], "geometry_mutated": False,
            "material_ids_included": True, "material_ids": list(mesh.ids),
            "witness_triangle_count": witness_count,
            "witness_triangles": [[tid, *mesh.faces[tid], *(v for vid in mesh.faces[tid] for v in mesh.points[vid])]
                                  for tid in range(witness_count)],
            "summary": {
                "vertex_count": len(mesh.points), "triangle_count": len(mesh.faces), "uv_set_count": len(mesh.uv_layers),
                "positions_indices_blake3": network.digest(["synthetic", mesh.points, mesh.faces]),
                "triangle_corner_normals_uv_blake3": network.digest(["synthetic", mesh.normal, mesh.uv_layers]),
                "material_ids_blake3": network.digest(["synthetic", mesh.ids]),
            },
        }
        if preserved_uv_set_count >= 0:
            if len(mesh.uv_layers) != preserved_uv_set_count + 1:
                return {"error": "synthetic appended channel missing"}
            layer = mesh.uv_layers[preserved_uv_set_count]
            value["material_uv"] = {
                "preserved_uv_set_count": preserved_uv_set_count,
                "preserved_triangle_corner_normals_uv_blake3": network.digest(
                    ["synthetic", mesh.normal, mesh.uv_layers[:preserved_uv_set_count]]),
                "hash_format": edges.HASH_FORMAT,
                "triangles": [[tid, *(v for uv in layer[tid] for v in uv)] for tid in sorted(layer)],
                "set_triangle_count": len(layer),
                "uv_blake3": network.digest(["synthetic", preserved_uv_set_count, len(mesh.faces), layer]),
            }
        return value

    def read(self, component, witness_count=0, preserved_uv_set_count=-1):
        self.events.append(("inspect", component.actor.label, witness_count))
        return json.dumps(self.snapshot(component, witness_count, preserved_uv_set_count), allow_nan=False)

    def set_num_uv_sets(self, mesh, count):
        self.events.append(("uv_count", mesh.component.actor.label, count))
        mesh.uv_layers[:] = (mesh.uv_layers + [{} for _ in range(count)])[:count]
        return mesh

    def set_triangle_uvs(self, mesh, channel, tid, values, defer_change_notifications):
        if channel not in (0, 1) or defer_change_notifications is not True:
            raise AssertionError("Only the batched appended material channel is allowed")
        component = mesh.component
        self.events.append(("uv", component.actor.label, tid))
        mesh.uv_layers[channel][tid] = (values.uv0, values.uv1, values.uv2)
        if self.fail_uv_assignment == (component.actor.label, component.assignment_round, tid):
            self.fail_uv_assignment = None
            raise ValueError("synthetic partial UV assignment failure")
        if channel == 1 and self.fail_outer_uv_assignment == (component.actor.label, component.assignment_round, tid):
            self.fail_outer_uv_assignment = None
            raise ValueError("synthetic partial outer UV assignment failure")
        return mesh, True

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

    def prepare(self, **kwargs):
        with patch.object(network, "native_api_evidence", return_value={"synthetic_fixture_only": True}):
            return network.prepare(self.api, self.actors, self.plan, self.instance, self.material_receipt, **kwargs)


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
        self.component.mesh.uv_layers = [{0: ((0.25, 0.5),) * 3}]
        before = self.h.snapshot(self.component)["summary"]
        for key, replacement in (("points", [(100, 0, 0), *self.component.mesh.points[1:]]),
                                  ("faces", [(0, 27, 1), *self.component.mesh.faces[1:]]),
                                  ("normal", [1, 0, 0]), ("uv_layers", [{0: ((0, 0),) * 3}])):
            old = getattr(self.component.mesh, key)
            setattr(self.component.mesh, key, replacement)
            with self.subTest(buffer=key), self.assertRaisesRegex(ValueError, "full positions"):
                network.verify_delta(before, self.h.snapshot(self.component), self.owner, assigned=False)
            setattr(self.component.mesh, key, old)

    def test_only_source_outer_top_ids_change_and_parapet_remains_literal(self):
        before = self.h.snapshot(self.component)["summary"]
        for tid in self.owner["selected_triangle_ids"]:
            self.component.mesh.ids[tid] = 1
        edges.apply(self.h.api, self.component, edges.triangle_coordinates(self.owner), 0)
        network.verify_delta(before, self.h.snapshot(self.component, preserved_uv_set_count=0), self.owner, assigned=True)
        for tid in (2, self.owner["top_triangle_count"]):
            self.component.mesh.ids[tid] = 1
            with self.assertRaisesRegex(ValueError, "wall/interior/parapet"):
                network.verify_delta(before, self.h.snapshot(self.component, preserved_uv_set_count=0), self.owner, assigned=True)
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
            self.assertEqual(component.mesh.uv_layers, [])

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
        self.assertTrue(receipt["source_vertices_topology_normals_uv_prefix_preserved"])
        self.assertTrue(receipt["material_edge_uv_appended"])
        self.assertEqual(receipt["material_edge_uv_channel"], 0)
        for row in receipt["owners"]:
            self.assertNotIn("selected_triangle_ids", row)
            self.assertEqual(row["selected_triangle_count"], len(row["source"]["selected_triangle_ids"]))
            if row["material_target"]:
                self.assertEqual(row["edge_attribute"]["set_triangle_count"], row["selected_triangle_count"])
                self.assertEqual(row["before_mesh"]["uv_set_count"], 0)
                self.assertEqual(row["after_mesh"]["uv_set_count"], 1)
            else:
                self.assertIsNone(row["edge_attribute"])
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

    def test_partial_new_uv_failure_in_both_rounds_restores_exact_zero_uv_source(self):
        for attempt in (1, 2):
            self.h = Harness()
            self.h.fail_uv_assignment = ("YACS_PERSIST_SUPPORT_080", attempt, 50)
            with self.subTest(attempt=attempt), self.assertRaisesRegex(ValueError, "partial UV assignment"):
                self.h.prepare()
            self.assert_restored()

    def test_existing_uv_channel_is_rejected_before_every_source_write(self):
        self.h.components[-1].mesh.uv_layers.append({})
        with self.assertRaisesRegex(ValueError, "authenticated UV-free source"):
            self.h.prepare()
        self.assertFalse(any(row[0] in ("slots", "id", "uv", "uv_count") for row in self.h.events))

    def test_fresh_readback_rejects_new_uv_tampering_even_with_original_prefix_unchanged(self):
        receipt, _ = self.h.prepare()
        component = self.h.components[0]
        original_normal_hash = receipt["owners"][0]["before_mesh"]["triangle_corner_normals_uv_blake3"]
        component.mesh.uv_layers[0][0] = ((1, 0), (2, 0), (3, 0))
        snapshot = self.h.snapshot(component, preserved_uv_set_count=0)
        self.assertEqual(snapshot["material_uv"]["preserved_triangle_corner_normals_uv_blake3"], original_normal_hash)
        with self.assertRaisesRegex(ValueError, "Fresh full native mesh"):
            network.verify_loaded(self.h.api, receipt, self.h.plan)

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


class OuterTerrainTransactionTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        paths = material.asset_paths(material.DESTINATION_ROOT, outer_terrain=True)
        self.kwargs = {"outer_instance": Material(paths["instance"]),
                       "outer_material_receipt": {"schema_version": 3, "assets": paths,
                           "outer_terrain_enabled": True, "outer_transition": deepcopy(material.OUTER_TRANSITION),
                           "synthetic_fixture_only": True},
                       "outer_owner_labels": ["YACS_PERSIST_SUPPORT_000", "YACS_PERSIST_SUPPORT_080"]}

    def assert_restored(self):
        for owner, component in zip(self.h.plan["owners"], self.h.components, strict=True):
            self.assertEqual(component.mesh.uv_layers, [])
            self.assertTrue(all(value == 0 for value in component.mesh.ids))
            self.assertEqual(component.get_num_materials(), 1)
            self.assertEqual(component.get_material(0).path, owner["original_material_path"])

    def test_selected_owners_get_second_field_with_complete_uv0_stage_and_read_only_fresh_proof(self):
        receipt, state = self.h.prepare(**self.kwargs)
        self.assertEqual(receipt["schema_version"], 4)
        self.assertFalse(receipt["outer_terrain"]["physical_contact_verified"])
        self.assertFalse(receipt["whole_area_admitted"])
        for row, component in zip(receipt["owners"], self.h.components, strict=True):
            outer = row["support_label"] in self.kwargs["outer_owner_labels"]
            expected_count = 2 if outer else 1 if row["material_target"] else 0
            self.assertEqual(component.mesh.get_num_uv_sets(), expected_count)
            if outer:
                attribute = row["edge_attribute"]
                self.assertEqual(attribute["channel"], 0)
                self.assertEqual(attribute["outer_attribute"]["channel"], 1)
                self.assertTrue(attribute["uv0_preserved"])
                self.assertEqual(attribute["outer_attribute"]["original_normals_uv_prefix_blake3"],
                                 attribute["inner_stage_mesh"]["triangle_corner_normals_uv_blake3"])
                self.assertEqual(set(component.mesh.uv_layers[1]), set(row["source"]["selected_triangle_ids"]))
                self.assertEqual(component.get_material(1).path, self.kwargs["outer_instance"].path)
        self.h.events.clear()
        self.assertEqual(network.verify_loaded(self.h.api, receipt, self.h.plan), receipt["aggregate_after_sha256"])
        self.assertEqual(len(self.h.events), 186)
        self.assertTrue(all(row[0] == "inspect" for row in self.h.events))
        network.rollback(self.h.api, state)
        self.assert_restored()

    def test_selection_never_infers_contact_or_accepts_parapet_unknown_duplicate_and_reordered_owners(self):
        for labels in ([], ["YACS_PERSIST_SUPPORT_181"], ["YACS_PERSIST_SUPPORT_186"],
                       ["YACS_PERSIST_SUPPORT_000"] * 2, list(reversed(self.kwargs["outer_owner_labels"]))):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                self.h.prepare(**{**self.kwargs, "outer_owner_labels": labels})
            self.assertEqual(self.h.events, [])
        receipt, _ = self.h.prepare(**self.kwargs)
        changed = deepcopy(receipt)
        changed["outer_terrain"]["physical_contact_verified"] = True
        with self.assertRaises(ValueError):
            network.verify_loaded(self.h.api, changed, self.h.plan)

    def test_partial_second_channel_failure_in_both_rounds_restores_all_original_buffers(self):
        for attempt in (1, 2):
            self.setUp()
            self.h.fail_outer_uv_assignment = ("YACS_PERSIST_SUPPORT_080", attempt, 50)
            with self.subTest(attempt=attempt), self.assertRaisesRegex(ValueError, "partial outer UV"):
                self.h.prepare(**self.kwargs)
            self.assert_restored()

    def test_changed_uv0_or_wall_uv1_during_append_is_detected_before_admission_and_rolled_back(self):
        original = edges.apply_outer
        for change in ("uv0", "wall"):
            self.setUp()

            def changed(api, component, coordinates):
                original(api, component, coordinates)
                if change == "uv0":
                    component.mesh.uv_layers[0][0] = ((0.125, 0), (0, 0), (0, 1))
                else:
                    component.mesh.uv_layers[1][self.h.plan["owners"][0]["top_triangle_count"]] = ((0, 0),) * 3

            with self.subTest(change=change), patch.object(edges, "apply_outer", side_effect=changed), self.assertRaises(ValueError):
                self.h.prepare(**self.kwargs)
            self.assert_restored()

    def test_fresh_chain_rejects_tampered_uv0_stage_even_when_final_summary_is_relabelled(self):
        receipt, _ = self.h.prepare(**self.kwargs)
        for field in ("source_coordinates_sha256", "original_normals_uv_prefix_blake3"):
            changed = deepcopy(receipt)
            changed["owners"][0]["edge_attribute"][field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                network.verify_loaded(self.h.api, changed, self.h.plan)
        self.h.components[0].mesh.uv_layers[0][0] = ((0.125, 0), (0, 0), (0, 1))
        changed = deepcopy(receipt)
        changed["owners"][0]["after_mesh"] = self.h.snapshot(self.h.components[0])["summary"]
        changed["aggregate_after_sha256"] = network.digest([row["after_mesh"] for row in changed["owners"]])
        with self.assertRaisesRegex(ValueError, "Original normals/UV prefix changed"):
            network.verify_loaded(self.h.api, changed, self.h.plan)


if __name__ == "__main__":
    unittest.main()
