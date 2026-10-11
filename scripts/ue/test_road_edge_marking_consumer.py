"""Offline source-correspondence and transaction fixtures; no native PASS claim."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import hashlib
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_edge_marking_consumer as consumer
from scripts.ue import road_edge_marking_geometry as geometry
from scripts.ue.test_road_edge_marking_geometry import DIAGONAL_BC, owner_fixture, plan_fixture
from scripts.ue.test_road_edge_marking_material import Engine as MaterialEngine, Material


PRODUCER_BYTES = b"offline-only fixture pavement producer, not retained/native evidence"
PRODUCER = {"sha256": hashlib.sha256(PRODUCER_BYTES).hexdigest(), "size_bytes": len(PRODUCER_BYTES)}


class Vector:
    def __init__(self, x=0., y=0., z=0.):
        self.x, self.y, self.z = x, y, z

    def to_tuple(self):
        return self.x, self.y, self.z


class UV:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Rotation:
    pitch = yaw = roll = 0.

    def to_tuple(self):
        return self.pitch, self.yaw, self.roll


class Buffers:
    def __init__(self):
        self.values = {}

    def set_editor_property(self, name, value):
        self.values[name] = value


class Engine(MaterialEngine):
    def __init__(self):
        super().__init__()
        engine = self
        self.package = consumer.network.MAPS[0]
        self.actors, self.created_actor_count, self.placed_append_count = [], 0, 0
        self.drop_probe_attribute = None
        self.fail_placed_append = self.fail_navigation = self.fail_destroy = False

        class Mesh:
            def __init__(self, component=None):
                self.component = component
                self.positions, self.triangles, self.normals, self.uv0, self.material_ids = [], [], [], [], []

            def get_path_name(self):
                return self.component.get_path_name() + ".DynamicMesh" if self.component else "/Engine/Transient.MeshProbe"

            def get_vertex_count(self):
                return len(self.positions)

            def get_triangle_count(self):
                return len(self.triangles)

            def get_num_uv_sets(self):
                return int(bool(self.uv0))

            def get_triangle_material_id(self, tid):
                return self.material_ids[tid], True

            def append_buffers_to_mesh(self, buffers, material_id, defer_change_notifications):
                if self.component:
                    engine.placed_append_count += 1
                    if engine.fail_placed_append and engine.placed_append_count == 2:
                        raise RuntimeError("fixture partial second paint append failure")
                engine.events.append(("append", self.get_path_name()))
                self.positions = [value.to_tuple() for value in buffers.values["vertices"]]
                self.triangles = [value.to_tuple() for value in buffers.values["triangles"]]
                self.normals = [value.to_tuple() for value in buffers.values["normals"]]
                self.uv0 = [(value.x, value.y) for value in buffers.values["uv0"]]
                self.material_ids = [material_id] * len(self.triangles)
                if not self.component and engine.drop_probe_attribute:
                    setattr(self, engine.drop_probe_attribute, [])

        class Component:
            def __init__(self, actor):
                self.actor, self.mesh = actor, Mesh(self)
                self.properties = {"cast_shadow": True, "can_ever_affect_navigation": True,
                                   "generate_overlap_events": True, "enable_complex_collision": True,
                                   "visible": True, "hidden_in_game": False}
                self.collision, self.tangents, self.slots = "no_collision", "default", [engine.asphalt]

            def get_path_name(self):
                return self.actor.get_path_name() + ".DynamicMeshComponent"

            def get_dynamic_mesh(self):
                return self.mesh

            def set_editor_property(self, name, value):
                engine.events.append(("component_property", self.actor.label, name, value))
                if name != "can_ever_affect_navigation" or not engine.fail_navigation:
                    self.properties[name] = value

            def get_editor_property(self, name):
                return self.properties[name]

            def get_collision_enabled(self):
                return self.collision

            def set_collision_enabled(self, value):
                engine.events.append(("collision", self.actor.label, value))
                self.collision = value

            def set_cast_shadow(self, value):
                engine.events.append(("shadow", self.actor.label, value))
                self.properties["cast_shadow"] = value

            def set_tangents_type(self, value):
                engine.events.append(("tangents", self.actor.label, value))
                self.tangents = value

            def get_tangents_type(self):
                return self.tangents

            def get_num_materials(self):
                return len(self.slots)

            def get_material(self, index):
                return self.slots[index]

            def set_material(self, index, value):
                engine.events.append(("material", self.actor.label, index))
                self.slots[index] = value

            def notify_mesh_modified(self):
                engine.events.append(("notify", self.actor.label))

        class Actor:
            def __init__(self, label, name):
                self.label, self.name = label, name
                self.location, self.rotation, self.scale = Vector(), Rotation(), Vector(1., 1., 1.)
                self.hidden = False
                self.component = Component(self)

            def get_path_name(self):
                return engine.package + "." + engine.package.rsplit("/", 1)[-1] + ":PersistentLevel." + self.name

            def get_actor_label(self):
                return self.label

            def set_actor_label(self, value):
                engine.events.append(("label", self.name, value))
                self.label = value

            def get_dynamic_mesh_component(self):
                return self.component

            def get_actor_location(self):
                return self.location

            def get_actor_rotation(self):
                return self.rotation

            def get_actor_scale3d(self):
                return self.scale

            def get_actor_transform(self):
                return SimpleNamespace(to_tuple=lambda: (self.location, self.rotation, self.scale))

            def get_editor_property(self, name):
                return {"root_component": self.component, "hidden": self.hidden}[name]

            def set_editor_property(self, name, value):
                if name != "hidden":
                    raise AssertionError("Unexpected fixture actor property")
                engine.events.append(("actor_hidden", self.name, value))
                self.hidden = value

        self.api.DynamicMesh, self.api.DynamicMeshComponent, self.api.DynamicMeshActor = Mesh, Component, Actor
        self.api.Vector = self.api.IntVector = Vector
        self.api.Vector2D, self.api.Rotator, self.api.GeometryScriptSimpleMeshBuffers = UV, Rotation, Buffers
        self.api.CollisionEnabled = SimpleNamespace(NO_COLLISION="no_collision")
        self.api.DynamicMeshComponentTangentsMode = SimpleNamespace(AUTO_CALCULATED="auto")
        self.api.UnrealEditorSubsystem, self.api.EditorActorSubsystem = "world", "actors"
        self.actor_subsystem = SimpleNamespace(get_all_level_actors=lambda: list(self.actors),
                                              spawn_actor_from_class=self.spawn, destroy_actor=self.destroy)
        self.api.get_editor_subsystem = lambda kind: self.actor_subsystem if kind == "actors" else SimpleNamespace(
            get_editor_world=lambda: SimpleNamespace(get_path_name=lambda: self.package + ".World"))
        self.api.EditorAssetLibrary.delete_asset = self.delete_asset
        self.api.GeometryScript_MeshQueries = SimpleNamespace(
            get_num_vertex_i_ds=lambda mesh: len(mesh.positions),
            get_num_triangle_i_ds=lambda mesh: len(mesh.triangles),
            get_triangle_indices=lambda mesh, tid: (Vector(*mesh.triangles[tid]), True),
            get_vertex_position=lambda mesh, vid: (Vector(*mesh.positions[vid]), True),
            get_triangle_normals=lambda mesh, tid: (mesh, *[Vector(*mesh.normals[vid]) for vid in mesh.triangles[tid]], True)
                if mesh.normals else (mesh, Vector(), Vector(), Vector(), False),
            get_triangle_u_vs=lambda mesh, layer, tid: (*[UV(*mesh.uv0[vid]) for vid in mesh.triangles[tid]], True)
                if mesh.uv0 else (UV(0, 0), UV(0, 0), UV(0, 0), False),
        )
        owner = owner_fixture(y_values=(0., 1., 2.), height=lambda x, y: 0.03 * x * y + 0.05 * y)
        parapet = {"support_label": "YACS_PERSIST_SUPPORT_001", "window_id": "excluded-parapet",
                   "kind": "parapet", "material_target": False}
        self.source_plan = plan_fixture(owner, parapet)
        self.source_plan["source_identity"]["producer_files"] = {consumer.PRODUCER_PATH: PRODUCER}
        self.road_actor = Actor("YACS_PERSIST_ROAD", "ExistingRoad")
        self.actors.append(self.road_actor)
        self.road = self.road_actor.component.mesh
        self.road.positions = [tuple(v * 100 for v in point) for row in owner["pavement_sections_m"] for point in row]
        self.road.normals = [consumer._unit((-0.03 * y / 100, -0.03 * x / 100 - 0.05, 1.))
                             for x, y, _ in self.road.positions]
        # Explicit topology is ONLY this synthetic producer fixture; production has no default/offset inference.
        for section in range(2):
            for cell in range(24):
                a = section * 25 + cell
                self.road.triangles.extend(((a, a + 1, a + 25), (a + 1, a + 26, a + 25)))
        self.road.material_ids = [0] * len(self.road.triangles)
        for index in range(2):
            self.actors.append(Actor(f"YACS_PERSIST_SUPPORT_{index:03d}", f"ExistingSupport{index}"))
        self.original_actors = tuple(self.actors)
        built = geometry.build_markings(self.source_plan, quad_triangles=DIAGONAL_BC)
        keys = sorted({(mesh.owner_label, *fragment.source_triangle)
                       for mesh in built.meshes for fragment in mesh.fragments})
        self.bindings = []
        for label, section, cell, slot in keys:
            tid = (section * 24 + cell) * 2 + slot
            self.bindings.append([label, section, cell, slot, tid, *self.road.triangles[tid]])

    def spawn(self, cls, location, rotation, transient):
        if transient is not False:
            raise AssertionError("Only the buffer probe is transient; paint belongs to the later saved map")
        self.created_actor_count += 1
        actor = cls("New", f"PaintActor{self.created_actor_count}")
        self.actors.append(actor)
        self.events.append(("spawn", actor.name))
        return actor

    def destroy(self, actor):
        self.events.append(("destroy", actor.name))
        if self.fail_destroy:
            return False
        self.actors.remove(actor)
        return True

    def delete_asset(self, path):
        self.events.append(("delete_asset", path))
        self.assets.pop(path)
        return True

    def inspect(self, api, component):
        mesh = component.mesh
        return {"summary": {"vertex_count": len(mesh.positions), "triangle_count": len(mesh.triangles),
                            "uv_set_count": int(bool(mesh.uv0)),
                            "positions_indices_blake3": consumer._digest(["fixture", mesh.positions, mesh.triangles]),
                            "triangle_corner_normals_uv_blake3": consumer._digest(["fixture", mesh.normals, mesh.uv0]),
                            "material_ids_blake3": consumer._digest(["fixture", mesh.material_ids])}}


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target, name, value in (
            (consumer, "PRODUCER_IDENTITY", PRODUCER),
            (consumer.sources, "OWNER_COUNT", 2), (consumer.sources, "NETWORK_COUNT", 0),
            (consumer.sources, "PROFILE_PAVEMENT_ROW_COUNT", 3),
            (consumer.network, "ROAD_COUNTS", (len(self.engine.road.positions), len(self.engine.road.triangles))),
        ):
            self.stack.enter_context(patch.object(target, name, value))
        self.stack.enter_context(patch.object(consumer, "native_api_evidence", return_value={"fixture_only": True}))
        self.stack.enter_context(patch.object(consumer.material, "_api_evidence", return_value={"fixture_only": True}))
        self.stack.enter_context(patch.object(consumer.network, "inspect_mesh", self.engine.inspect))
        self.stack.enter_context(patch.object(consumer.baseline, "road_support_actors",
                                             side_effect=lambda actors: [a for a in actors if a.label.startswith("YACS_PERSIST_")]))
        self.plan = self.prepare()

    def prepare(self, **overrides):
        args = {"producer_bytes": PRODUCER_BYTES, "quad_triangles": DIAGONAL_BC,
                "triangle_bindings": self.engine.bindings}
        return consumer.prepare(self.engine.source_plan, **{**args, **overrides})

    def create(self):
        return consumer.create(self.engine.api, self.plan, self.engine.asphalt_assets)

    def verify(self, receipt):
        return consumer.verify_loaded(self.engine.api, self.plan, receipt, self.engine.asphalt_assets)

    def test_pure_plan_requires_exact_producer_and_exhaustive_unambiguous_addresses(self):
        self.assertEqual(self.engine.events, [])
        for change in ("producer", "missing", "duplicate", "foreign", "vertex"):
            bindings = deepcopy(self.engine.bindings)
            kwargs = {"triangle_bindings": bindings}
            if change == "producer":
                kwargs["producer_bytes"] = PRODUCER_BYTES + b"tampered"
            elif change == "missing":
                bindings.pop()
            elif change == "duplicate":
                bindings.append(bindings[0])
            elif change == "foreign":
                bindings[0][0] = "YACS_PERSIST_SUPPORT_185"
            else:
                bindings[0][5] = len(self.engine.road.positions)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare(**kwargs)
        self.assertEqual(self.engine.events, [])

    def test_plan_cannot_omit_diagonal_or_tamper_frozen_payload_identity(self):
        with self.assertRaises(TypeError):
            consumer.prepare(self.engine.source_plan, producer_bytes=PRODUCER_BYTES,
                             triangle_bindings=self.engine.bindings)
        with self.assertRaises(ValueError):
            consumer._check_plan(replace(self.plan, plan_sha256="0" * 64))
        modified = replace(self.plan.meshes[0], normals=tuple((0., 0., -1.) for _ in self.plan.meshes[0].normals))
        with self.assertRaises(ValueError):
            consumer._check_plan(replace(self.plan, meshes=(modified, *self.plan.meshes[1:])))

    def test_actual_road_correspondence_blocks_wrong_face_or_position_before_world_writes(self):
        request = self.plan.source_triangles[0]
        original = self.engine.road.triangles[request.triangle_id]
        self.engine.road.triangles[request.triangle_id] = tuple(reversed(original))
        with self.assertRaisesRegex(ValueError, "topology/winding"):
            self.create()
        self.assertEqual(self.engine.created_actor_count, 0)
        self.engine.road.triangles[request.triangle_id] = original
        vid = request.vertex_ids[0]
        old = self.engine.road.positions[vid]
        self.engine.road.positions[vid] = (old[0], old[1], old[2] + 0.01)
        with self.assertRaisesRegex(ValueError, "source surface"):
            self.create()
        self.assertEqual(self.engine.created_actor_count, 0)
        self.assertTrue(all(path not in self.engine.assets for path in consumer.material.asset_paths().values()))

    def test_native_corner_normals_are_checked_and_interpolated_under_a_separate_hash(self):
        before = [geometry.mesh_sha256(mesh) for mesh in self.plan.meshes]
        payloads, receipt = consumer._source_correspondence(self.engine.api, self.plan, self.engine.road_actor.component)
        self.assertEqual(receipt["normal_contract"], consumer.NORMAL_CONTRACT)
        self.assertEqual(before, [geometry.mesh_sha256(mesh) for mesh in self.plan.meshes])
        base, rendered = self.plan.meshes[0], payloads[0]
        fragment = base.fragments[0]
        request = next(row for row in self.plan.source_triangles if row.key == (base.owner_label, *fragment.source_triangle))
        weights = base.barycentric_weights[0]
        expected = consumer._unit(tuple(sum(weights[k] * self.engine.road.normals[request.vertex_ids[k]][axis]
                                             for k in range(3)) for axis in range(3)))
        self.assertEqual(rendered.normals[0], expected)
        self.assertNotEqual(rendered.normals[0], base.normals[0])
        self.assertNotEqual(consumer.render_payload_sha256(rendered), geometry.mesh_sha256(base))
        self.engine.road.normals[request.vertex_ids[0]] = (0., 0., -1.)
        with self.assertRaisesRegex(ValueError, "normal orientation"):
            consumer._source_correspondence(self.engine.api, self.plan, self.engine.road_actor.component)

    def test_clockwise_source_faces_keep_actual_native_normals_without_a_sign_conversion(self):
        # The real pinned pavement producer uses the same ordered triples as
        # this fixture but its source XY orientation has negative cross Z.
        # A readback must not flip those indices or guess native normal signs.
        request = self.plan.source_triangles[0]
        original_indices = self.engine.road.triangles[request.triangle_id]
        positions = tuple((-p[0], p[1], p[2]) for p in request.positions_cm)
        self.assertLess(geometry._cross(*positions)[2], 0)
        original_normals = [self.engine.road.normals[vid] for vid in request.vertex_ids]
        for vid, position in zip(request.vertex_ids, positions, strict=True):
            self.engine.road.positions[vid] = position
        for sign, expected_alignment in ((1., -1), (-1., 1)):
            normals = tuple(tuple(sign * value for value in (-n[0], n[1], n[2])) for n in original_normals)
            for vid, normal in zip(request.vertex_ids, normals, strict=True):
                self.engine.road.normals[vid] = normal
            result = consumer.read_source_triangle(self.engine.api, self.engine.road, request.triangle_id,
                                                  request.vertex_ids, positions)
            self.assertEqual(result["vertex_ids"], original_indices)
            self.assertEqual(result["corner_normals"], normals)
            self.assertEqual(result["ordered_face_cross_z_sign"], -1)
            self.assertEqual(result["native_corner_normal_cross_alignment_sign"], expected_alignment)
        self.engine.road.normals[request.vertex_ids[1]] = original_normals[1]
        with self.assertRaisesRegex(ValueError, "normal orientation"):
            consumer.read_source_triangle(self.engine.api, self.engine.road, request.triangle_id,
                                          request.vertex_ids, positions)

    def test_transient_buffer_probe_rejects_missing_normals_or_uv_before_any_placement(self):
        for field in ("normals", "uv0"):
            self.engine.drop_probe_attribute = field
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.create()
            self.assertEqual(self.engine.created_actor_count, 0)
            self.assertTrue(all(path not in self.engine.assets for path in consumer.material.asset_paths().values()))

    def test_create_adds_exact_render_only_ribbons_and_preserves_every_original_buffer(self):
        before, _ = consumer._source_state(self.engine.api, self.engine.actors, self.engine.package)
        actors, receipt = self.create()
        self.assertEqual(len(actors), 2)
        self.assertEqual(receipt["source_correspondence"]["source_triangle_count"], len(self.plan.source_triangles))
        after, _ = consumer._source_state(self.engine.api, self.engine.actors, self.engine.package)
        self.assertEqual(before, after)
        self.assertTrue(all(receipt[key] is False for key in consumer.FALSE_FLAGS))
        self.assertTrue(receipt["render_flags_verified_before_append"])
        self.assertTrue(receipt["caller_saved_package_bytes_required"])
        for actor in actors:
            consumer._render_flags(self.engine.api, actor.component)
            self.assertEqual(actor.location.to_tuple(), (0., 0., 0.))
            self.assertEqual(actor.component.get_num_materials(), 1)
        self.assertFalse(any(event[0] in ("destroy", "delete_asset") for event in self.engine.events))

    def test_fresh_verification_only_reads_and_normalizes_only_the_allowed_map_owner(self):
        _, receipt = self.create()
        self.engine.package = consumer.network.MAPS[1]
        self.engine.events.clear()
        result = self.verify(deepcopy(receipt))
        self.assertTrue(result["read_only"])
        self.assertTrue(result["all_marking_buffers_verified"])
        self.assertEqual(self.engine.events, [])
        self.engine.package = "/Game/UnapprovedScene"
        with self.assertRaises(ValueError):
            self.verify(receipt)

    def test_fresh_verification_rejects_render_flags_hidden_actor_transform_and_binding(self):
        actors, receipt = self.create()
        actor, component = actors[0], actors[0].component
        for name, value in (("cast_shadow", True), ("can_ever_affect_navigation", True),
                            ("generate_overlap_events", True), ("enable_complex_collision", True),
                            ("visible", False), ("hidden_in_game", True)):
            old = component.properties[name]
            component.properties[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(receipt)
            component.properties[name] = old
        for target, name, value in ((component, "collision", "blocking"), (component, "tangents", "default"),
                                    (actor, "hidden", True), (actor, "location", Vector(0., 0., 0.1))):
            old = getattr(target, name)
            setattr(target, name, value)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(receipt)
            setattr(target, name, old)
        component.slots = [Material("/Game/Foreign.Material")]
        with self.assertRaises(ValueError):
            self.verify(receipt)

    def test_fresh_readback_rejects_each_actual_mesh_buffer_tamper(self):
        actors, receipt = self.create()
        mesh = actors[0].component.mesh
        for field, value in (("positions", (0., 0., 99.)), ("triangles", (2, 1, 0)),
                             ("normals", (0., 0., -1.)), ("uv0", (0.5, 99.)), ("material_ids", 1)):
            values = getattr(mesh, field)
            old = values[0]
            values[0] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.verify(receipt)
            values[0] = old

    def test_fresh_source_hash_catches_interior_road_and_excluded_support_changes(self):
        _, receipt = self.create()
        index = 12  # Interior source vertex, outside either clipped paint band.
        old = self.engine.road.positions[index]
        self.engine.road.positions[index] = (old[0], old[1], old[2] + 1)
        with self.assertRaisesRegex(ValueError, "source scene differs"):
            self.verify(receipt)
        self.engine.road.positions[index] = old
        support = self.engine.original_actors[-1].component
        support.slots = [Material("/Game/ChangedParapet.Material")]
        with self.assertRaisesRegex(ValueError, "source scene differs"):
            self.verify(receipt)

    def test_partial_second_actor_failure_removes_only_owned_objects(self):
        self.engine.fail_placed_append = True
        with self.assertRaisesRegex(RuntimeError, "partial second paint append"):
            self.create()
        self.assertEqual(tuple(self.engine.actors), self.engine.original_actors)
        self.assertTrue(all(path not in self.engine.assets for path in consumer.material.asset_paths().values()))
        self.assertEqual([event for event in self.engine.events if event[0] == "destroy"],
                         [("destroy", "PaintActor2"), ("destroy", "PaintActor1")])
        self.assertIn(self.engine.asphalt_assets["instance"], self.engine.assets)

    def test_failed_material_compilation_removes_only_the_new_partial_master(self):
        self.engine.fail_compile = True
        with self.assertRaisesRegex(ValueError, "compilation"):
            self.create()
        self.assertEqual(self.engine.created_actor_count, 0)
        self.assertEqual(tuple(self.engine.actors), self.engine.original_actors)
        self.assertTrue(all(path not in self.engine.assets for path in consumer.material.asset_paths().values()))
        self.assertIn(self.engine.asphalt_assets["instance"], self.engine.assets)

    def test_failed_navigation_readback_stops_before_nontransient_geometry_append(self):
        self.engine.fail_navigation = True
        with self.assertRaisesRegex(ValueError, "render-only"):
            self.create()
        self.assertEqual(self.engine.placed_append_count, 0)
        self.assertEqual(tuple(self.engine.actors), self.engine.original_actors)

    def test_incomplete_owned_object_cleanup_is_an_explicit_failure(self):
        self.engine.fail_placed_append = self.engine.fail_destroy = True
        with self.assertRaisesRegex(ValueError, "cleanup was incomplete"):
            self.create()
        self.assertTrue(all(actor in self.engine.actors for actor in self.engine.original_actors))

    def test_existing_assets_duplicate_markings_and_changed_receipt_are_rejected(self):
        actors, receipt = self.create()
        with self.assertRaises(ValueError):
            self.create()
        altered = deepcopy(receipt)
        altered["normal_contract"] = "flat_geometry_normals"
        with self.assertRaises(ValueError):
            self.verify(altered)
        actors[1].label = actors[0].label
        with self.assertRaisesRegex(ValueError, "actor inventory"):
            self.verify(receipt)


if __name__ == "__main__":
    unittest.main()
