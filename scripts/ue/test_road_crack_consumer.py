"""Offline native-shape/transaction fixtures; engine and visual proof stay pending."""

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from scripts.ue import road_crack_consumer as consumer
from scripts.ue import road_crack_geometry as geometry
from scripts.ue import road_edge_marking_geometry as paint_geometry
from scripts.ue.test_road_edge_marking_consumer import Engine, PRODUCER, PRODUCER_BYTES, Vector
from scripts.ue.test_road_edge_marking_geometry import DIAGONAL_BC, owner_fixture, plan_fixture
from scripts.ue.test_road_edge_marking_material import Instance, Material, Texture


class CrackConsumerTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.stack = Engine(), ExitStack()
        self.addCleanup(self.stack.close)
        engine, edge = self.engine, consumer.edge
        self.owners = (
            owner_fixture(window="fixture-ordinary", y_values=(0., 1., 2., 3., 4.),
                          height=lambda x, y: .03 * x * y + .05 * y),
            owner_fixture(label="YACS_PERSIST_SUPPORT_001", window="fixture-nudo", kind="nudo",
                          y_values=(0., 1., 2., 3., 4.), height=lambda x, y: 20 + .03 * x * y + .05 * y),
        )
        parapet = {"support_label": "YACS_PERSIST_SUPPORT_002", "window_id": "fixture-parapet",
                   "kind": "parapet", "material_target": False}
        engine.source_plan = plan_fixture(*self.owners, parapet)
        engine.source_plan["source_identity"]["producer_files"] = {consumer.bindings.PRODUCER_PATH: PRODUCER}
        engine.road.positions, engine.road.triangles, engine.road.normals = [], [], []
        self.offsets = {}
        for owner in self.owners:
            vertex_offset, triangle_offset = len(engine.road.positions), len(engine.road.triangles)
            self.offsets[owner["support_label"]] = (vertex_offset, triangle_offset)
            points = [point for row in owner["pavement_sections_m"] for point in row]
            engine.road.positions.extend(tuple(value * 100 for value in point) for point in points)
            engine.road.normals.extend(edge._unit((-.03 * y, -.03 * x - .05, 1.)) for x, y, _ in points)
            for section in range(owner["section_count"] - 1):
                for cell in range(24):
                    a = vertex_offset + section * 25 + cell
                    engine.road.triangles.extend(((a, a + 1, a + 25), (a + 1, a + 26, a + 25)))
        engine.road.material_ids = [0] * len(engine.road.triangles)
        engine.actors = [engine.road_actor] + [engine.api.DynamicMeshActor(f"YACS_PERSIST_SUPPORT_{i:03d}", f"Support{i}")
                                                for i in range(3)]
        for target, name, value in (
            (consumer.bindings, "PRODUCER_IDENTITY", PRODUCER), (edge, "PRODUCER_IDENTITY", PRODUCER),
            (edge.sources, "OWNER_COUNT", 3), (edge.sources, "NETWORK_COUNT", 1),
            (edge.sources, "PROFILE_PAVEMENT_ROW_COUNT", 10),
            (edge.network, "ROAD_COUNTS", (len(engine.road.positions), len(engine.road.triangles))),
        ):
            self.stack.enter_context(patch.object(target, name, value))
        self.stack.enter_context(patch.object(edge, "native_api_evidence", return_value={"fixture_only": True}))
        self.stack.enter_context(patch.object(edge.material, "_api_evidence", return_value={"fixture_only": True}))
        def source_owner_inspector(api, component):
            # Match the real Python/C++ inspector's source-owner allowlist.
            # A mock must not silently admit a white/crack render component.
            if not component.actor.label.startswith("YACS_PERSIST_"):
                raise ValueError("fixture preserves native source-owner inspector allowlist")
            return engine.inspect(api, component)

        self.stack.enter_context(patch.object(edge.network, "inspect_mesh", side_effect=source_owner_inspector))
        self.stack.enter_context(patch.object(edge.baseline, "road_support_actors", side_effect=lambda actors:
            [actor for actor in actors if actor.label.startswith("YACS_PERSIST_")]))
        white = paint_geometry.build_markings(engine.source_plan, quad_triangles=DIAGONAL_BC)
        white_keys = sorted({(mesh.owner_label, *fragment.source_triangle) for mesh in white.meshes for fragment in mesh.fragments})
        self.white_plan = edge.prepare(engine.source_plan, producer_bytes=PRODUCER_BYTES,
            quad_triangles=DIAGONAL_BC, triangle_bindings=self.resolve(white_keys)["triangle_bindings"])
        self.white_actors, self.white_receipt = edge.create(engine.api, self.white_plan, engine.asphalt_assets)
        self.original_actors = tuple(engine.actors)
        engine.events.clear()
        engine.placed_append_count = 0
        self.events = tuple(geometry.CrackEvent("fixture_" + str(i), motif, owner["window_id"], 2.0, extent,
                                               rotation_deg=90.0 if i == 1 else 0.0)
            for i, (motif, extent, owner) in enumerate(zip(
                consumer.source_maps.CANARY_MOTIFS, (1.8, 1.4), self.owners, strict=True)))
        self.stack.enter_context(patch.object(geometry, "CANARY_EVENTS", self.events))
        self.stack.enter_context(patch.object(consumer.bindings, "prepare_bindings",
            side_effect=lambda plan, *, producer_bytes, needed_faces: self.resolve(needed_faces)))
        self.contracts = {event.motif_id: consumer._expected_geometry_contract(event.extent_m, event.rotation_deg)
                          for event in self.events}
        self.source = {"pins_sha256": "a" * 64, "selected_motifs": list(consumer.source_maps.CANARY_MOTIFS),
                       "motifs": {event.motif_id: {"extent_cm": event.extent_m * 100, "empty_border_cm": 6.,
                                                   "resolution": 2048} for event in self.events}}
        self.fail_import = self.fail_material = self.overclaim_material = False
        self.stack.enter_context(patch.object(consumer.source_maps, "load_sources", side_effect=lambda *a, **k: deepcopy(self.source)))
        self.stack.enter_context(patch.object(consumer.source_maps, "import_textures", side_effect=self.import_maps))
        self.stack.enter_context(patch.object(consumer.source_maps, "verify_import", side_effect=self.verify_maps))
        self.stack.enter_context(patch.object(consumer.material, "create_materials", side_effect=self.make_materials))
        self.stack.enter_context(patch.object(consumer.material, "verify_materials", side_effect=self.verify_materials))
        self.plan = self.prepare()

    def resolve(self, needed):
        rows = []
        for label, section, cell, slot in sorted(set(needed)):
            _, offset = self.offsets[label]
            tid = offset + 2 * (section * 24 + cell) + slot
            rows.append((label, section, cell, slot, tid, *self.engine.road.triangles[tid]))
        return {"quad_triangles": DIAGONAL_BC, "triangle_bindings": tuple(rows)}

    def prepare(self, **kwargs):
        values = {"producer_bytes": PRODUCER_BYTES, "geometry_contracts": self.contracts, "events": self.events}
        return consumer.prepare(self.engine.source_plan, **{**values, **kwargs})

    def import_maps(self, api, root, pins, motif_ids, *, source_repo_root):
        paths, outputs = consumer.source_maps.asset_paths(self.source), {}
        for motif, channels in paths["textures"].items():
            outputs[motif] = {}
            for channel, path in channels.items():
                texture = Texture(path, channel)
                self.engine.assets[path] = texture
                self.engine.events.append(("crack_import", path))
                outputs[motif][channel] = texture
                if self.fail_import:
                    raise RuntimeError("fixture partial crack import")
        return outputs, {"sources": deepcopy(self.source), "assets": paths, "fixture_only": True}

    def verify_maps(self, api, root, pins, receipt, *, source_repo_root):
        self.assertEqual(receipt["sources"], self.source)
        return {motif: {channel: self.engine.assets[path] for channel, path in channels.items()}
                for motif, channels in receipt["assets"]["textures"].items()}

    def make_materials(self, api, root, pins, imports, asphalt, contracts, *, source_repo_root):
        self.assertEqual(contracts, self.contracts)
        self.verify_maps(api, root, pins, imports, source_repo_root=source_repo_root)
        paths = consumer.material.asset_paths(self.source)
        master_path = next(iter(paths.values()))["master"]
        master = Material(master_path)
        self.engine.assets[master_path] = master
        self.engine.events.append(("crack_material", master_path))
        if self.fail_material:
            raise RuntimeError("fixture partial crack material")
        result = {}
        for motif, row in paths.items():
            value = Instance(row["instance"], master)
            value.overrides["scalar"]["NeutralProbe"] = 0.0
            self.engine.assets[row["instance"]] = value
            self.engine.events.append(("crack_material", row["instance"]))
            result[motif] = value
        return result, {"normal_space_verified": self.overclaim_material, "world_normal_canary_required": True,
                        "fixture_only": True, "assets": paths}

    def verify_materials(self, api, root, pins, imports, receipt, asphalt, contracts, *, source_repo_root):
        self.verify_maps(api, root, pins, imports, source_repo_root=source_repo_root)
        self.assertEqual(receipt["assets"], consumer.material.asset_paths(self.source))
        result = {motif: self.engine.assets[row["instance"]] for motif, row in receipt["assets"].items()}
        if any(instance.overrides["scalar"]["NeutralProbe"] != 0.0 for instance in result.values()):
            raise ValueError("fixture neutral probe was not reset")
        return result

    def create(self):
        return consumer.create(self.engine.api, self.plan, "fixture-root", {"fixture_only": True}, self.engine.asphalt_assets,
                               white_plan=self.white_plan, white_receipt=self.white_receipt)

    def original_state(self):
        return consumer._original_state(self.engine.api, self.engine.actors, self.engine.package,
            white_plan=self.white_plan, white_receipt=self.white_receipt, asphalt_assets=self.engine.asphalt_assets)

    def verify(self, receipt):
        return consumer.verify_loaded(self.engine.api, self.plan, receipt, "fixture-root", {"fixture_only": True},
            self.engine.asphalt_assets, white_plan=self.white_plan, white_receipt=self.white_receipt)

    def assert_clean_failure(self):
        self.assertEqual(tuple(self.engine.actors), self.original_actors)
        self.assertTrue(all(path not in self.engine.assets for path in consumer._owned_asset_paths(self.source)))
        self.assertIn(self.engine.asphalt_assets["instance"], self.engine.assets)
        self.assertIn(consumer.edge.material.asset_paths()["instance"], self.engine.assets)

    def test_pure_preparation_authenticates_producer_material_extent_and_complete_source_addresses(self):
        self.assertEqual(self.engine.events, [])
        self.assertEqual(len(self.plan.meshes), 2)
        for changes in ({"producer_bytes": PRODUCER_BYTES + b"\n"},
                        {"geometry_contracts": {}},
                        {"geometry_contracts": {key: {**value, "extent_cm": 160.} for key, value in self.contracts.items()}},
                        {"geometry_contracts": {key: {**value, "uv_rotation_degrees": 0.0}
                                                for key, value in self.contracts.items()}}):
            with self.subTest(changes=next(iter(changes))), self.assertRaises(ValueError):
                self.prepare(**changes)
        with patch.object(consumer.bindings, "prepare_bindings", return_value={"quad_triangles": DIAGONAL_BC,
                                                                               "triangle_bindings": ()}):
            with self.assertRaisesRegex(ValueError, "inventory differs"):
                self.prepare()
        with self.assertRaisesRegex(ValueError, "preparation changed"):
            consumer._check_plan(replace(self.plan, plan_sha256="0" * 64))
        self.assertEqual(self.engine.events, [])

    def test_create_checks_all_existing_white_paint_before_import_or_new_actor(self):
        self.white_actors[0].component.mesh.uv0[0] = (.5, .5)
        with self.assertRaisesRegex(ValueError, "UV0 differs"):
            self.create()
        self.assertFalse(any(event[0] in ("crack_import", "crack_material", "spawn") for event in self.engine.events))

    def test_wrong_actual_source_position_blocks_before_import_or_placement(self):
        request = self.plan.source_triangles[0]
        vid = next(vid for vid in request.vertex_ids if vid % 25 not in (0, 1, 23, 24))
        point = self.engine.road.positions[vid]
        self.engine.road.positions[vid] = (point[0], point[1], point[2] + .01)
        # The existing white lane's complete source hash already detects this
        # interior corruption even before the new crack source reader runs.
        with self.assertRaisesRegex(ValueError, "source scene differs"):
            self.create()
        self.assertFalse(any(event[0] in ("crack_import", "spawn") for event in self.engine.events))

    def test_recorded_corner_normals_are_interpolated_without_replacing_flat_source_hash(self):
        hashes = [geometry.mesh_sha256(mesh) for mesh in self.plan.meshes]
        payloads, witness = consumer._source_correspondence(self.engine.api, self.plan, self.engine.road_actor.component)
        self.assertEqual(hashes, [geometry.mesh_sha256(mesh) for mesh in self.plan.meshes])
        self.assertFalse(witness["source_normal_sign_converted"])
        for mesh, payload in zip(self.plan.meshes, payloads, strict=True):
            self.assertEqual(payload.source_mesh_sha256, geometry.mesh_sha256(mesh))
            self.assertNotEqual(payload.normals, mesh.normals)
            self.assertTrue(all(abs(sum(x * x for x in normal) - 1.) < 1e-12 for normal in payload.normals))
        request = self.plan.source_triangles[0]
        self.engine.road.normals[request.vertex_ids[0]] = (0., 0., -1.)
        with self.assertRaisesRegex(ValueError, "normal orientation"):
            consumer._source_correspondence(self.engine.api, self.plan, self.engine.road_actor.component)

    def test_create_preserves_road_support_and_all_white_buffers_and_keeps_normal_gate_pending(self):
        before, _, _ = self.original_state()
        actors, receipt = self.create()
        self.assertEqual(len(actors), 2)
        self.assertEqual(len(receipt["owned_asset_paths"]), 11)  # Eight maps, one M and two MI.
        after, _, _ = self.original_state()
        self.assertEqual(after, before)
        self.assertTrue(receipt["world_normal_canary_required"])
        self.assertTrue(all(receipt[key] is False for key in consumer.FALSE_FLAGS))
        for actor in actors:
            consumer.edge._render_flags(self.engine.api, actor.component)
        self.assertFalse(any(event[0] == "delete_asset" for event in self.engine.events))

    def test_identity_world_placement_requires_identity_source_actor_and_owned_root(self):
        self.engine.road_actor.location = Vector(0., 0., 100.)
        with self.assertRaisesRegex(ValueError, "identity road transform"):
            self.create()
        self.assertFalse(any(event[0] in ("crack_import", "spawn") for event in self.engine.events))
        self.engine.road_actor.location = Vector()
        original = self.engine.road_actor.get_editor_property
        with patch.object(self.engine.road_actor, "get_editor_property", side_effect=lambda name:
                          object() if name == "root_component" else original(name)):
            with self.assertRaisesRegex(ValueError, "owned root component"):
                self.create()

    def test_aggregate_replays_every_white_buffer_without_source_inspector_or_legacy_actor_filter(self):
        with patch.object(consumer.edge, "verify_loaded", side_effect=AssertionError("legacy whole-actor verifier must not run")):
            _, receipt = self.create()
            self.engine.events.clear()
            result = self.verify(receipt)
        white = result["edge_markings"]
        self.assertEqual(white["aggregate_owner"], "local_crack_canary")
        self.assertEqual(white["actor_count"], 4)
        self.assertEqual(white["native_source_witness_sha256"], self.white_receipt["source_correspondence"]["native_source_witness_sha256"])
        self.assertTrue(white["all_marking_buffers_verified"])
        self.assertTrue(white["full_source_buffers_preserved"])
        self.assertEqual(self.engine.events, [])
        self.white_actors[0].component.mesh.material_ids[0] = 1
        with self.assertRaises(ValueError):
            self.verify(receipt)

    def test_fresh_reopen_only_reads_and_requires_every_original_and_new_buffer(self):
        actors, receipt = self.create()
        self.engine.package = consumer.edge.network.MAPS[1]
        self.engine.events.clear()
        result = self.verify(deepcopy(receipt))
        self.assertTrue(result["read_only"])
        self.assertFalse(result["normal_space_verified"])
        self.assertEqual(self.engine.events, [])
        for target, field, value in ((actors[0].component.mesh, "positions", (0., 0., 0.)),
                                     (actors[0].component.mesh, "normals", (0., 0., -1.)),
                                     (actors[0].component.mesh, "uv0", (.5, .5)),
                                     (actors[0].component.mesh, "triangles", (0, 0, 0)),
                                     (actors[0].component.mesh, "material_ids", 1),
                                     (self.white_actors[0].component.mesh, "uv0", (.5, .5)),
                                     (self.engine.road, "positions", (0., 0., 90000.))):
            values = getattr(target, field)
            old, values[0] = values[0], value
            with self.subTest(field=field, source=target is self.engine.road), self.assertRaises(ValueError):
                self.verify(receipt)
            values[0] = old

    def test_fresh_rejects_collision_shadow_navigation_transform_and_neutral_probe_left_enabled(self):
        actors, receipt = self.create()
        component, actor = actors[0].component, actors[0]
        for name in ("cast_shadow", "can_ever_affect_navigation", "generate_overlap_events", "enable_complex_collision"):
            component.properties[name] = True
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(receipt)
            component.properties[name] = False
        for target, name, value in ((component, "collision", "blocking"), (component, "tangents", "default"),
                                    (actor, "location", Vector(0, 0, .1)), (actor, "hidden", True)):
            old = getattr(target, name)
            setattr(target, name, value)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(receipt)
            setattr(target, name, old)
        component.slots[0].overrides["scalar"]["NeutralProbe"] = 1.0
        with self.assertRaisesRegex(ValueError, "neutral probe was not reset"):
            self.verify(receipt)

    def test_partial_import_and_partial_master_failures_remove_only_owned_assets(self):
        for option, message in (("fail_import", "partial crack import"), ("fail_material", "partial crack material")):
            setattr(self, option, True)
            with self.subTest(option=option), self.assertRaisesRegex(RuntimeError, message):
                self.create()
            self.assert_clean_failure()
            setattr(self, option, False)

    def test_partial_second_mesh_failure_removes_both_new_actors_and_the_shared_master_once(self):
        self.engine.fail_placed_append = True
        with self.assertRaisesRegex(RuntimeError, "partial second paint append"):
            self.create()
        self.assert_clean_failure()
        master = next(iter(consumer.material.asset_paths(self.source).values()))["master"]
        self.assertEqual(self.engine.events.count(("delete_asset", master)), 1)

    def test_native_flag_readback_and_false_material_admission_stop_and_cleanup(self):
        self.overclaim_material = True
        with self.assertRaisesRegex(ValueError, "normal-space canary"):
            self.create()
        self.assert_clean_failure()
        self.overclaim_material = False
        self.engine.fail_navigation = True
        with self.assertRaisesRegex(ValueError, "render-only"):
            self.create()
        self.assert_clean_failure()
        self.assertEqual(self.engine.placed_append_count, 0)

    def test_existing_namespace_is_not_overwritten_and_cleanup_failure_is_reported(self):
        path = consumer._owned_asset_paths(self.source)[0]
        self.engine.assets[path] = Texture(path, "BaseColor")
        with self.assertRaisesRegex(ValueError, "Existing crack assets"):
            self.create()
        self.assertIn(path, self.engine.assets)
        self.assertFalse(any(event[0] in ("crack_import", "delete_asset", "spawn") for event in self.engine.events))
        del self.engine.assets[path]
        self.engine.fail_placed_append = self.engine.fail_destroy = True
        with self.assertRaisesRegex(ValueError, "cleanup was incomplete"):
            self.create()
        self.assertTrue(all(actor in self.engine.actors for actor in self.original_actors))


if __name__ == "__main__":
    unittest.main()
