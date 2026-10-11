"""Synthetic save/reload contract tests; these never import Unreal or save a map."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue import road_edge_marking_consumer as markings
from scripts.ue import road_edge_marking_material as paint
from scripts.ue import road_crack_consumer as cracks
from scripts.ue import road_crack_geometry as crack_geometry
from scripts.ue import road_crack_material as crack_material
from scripts.ue import road_crack_sources as crack_sources
from scripts.ue import road_pavement_source_bindings as pavement_bindings
from scripts.ue.test_road_asphalt_slot_canary import CanaryTests


class RoadAsphaltSavedConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CanaryTests()
        self.fixture.setUp()
        self.old = self.fixture.snapshot()
        source = saved.session.operation.MAP_PACKAGE
        source_world = source + "." + source.rsplit("/", 1)[-1]
        self.old["map_package"] = source
        self.old["world"] = source_world
        road = source_world + ":PersistentLevel.YACS_PERSIST_ROAD"
        support = source_world + ":PersistentLevel.YACS_PERSIST_SUPPORT_000"
        self.old["road_supports"][0]["actor"] = road
        self.old["road_supports"][0]["component"] = road + ".DynamicMeshComponent"
        self.old["mesh_material_collision_snapshot"][0]["component"] = (
            road + ".DynamicMeshComponent"
        )
        self.old["road_supports"][1]["actor"] = support
        self.old["road_supports"][1]["component"] = support + ".DynamicMeshComponent"
        self.old["mesh_material_collision_snapshot"][1]["component"] = (
            support + ".DynamicMeshComponent"
        )
        self.old["actors"] = [
            (road, [1.0, 2.0, 3.0]),
            (support, [4.0, 5.0, 6.0]),
        ]
        self.new_material = (
            saved.PACKAGE
            + "/aged_mountain_asphalt/dry_varied/6b381516854c/MI_MaterialForge.MI_MaterialForge"
        )

    def new_inventory(self):
        value = deepcopy(self.old)
        value["road_supports"][0]["slots"] = [{
            "path": self.new_material,
            "parent": self.new_material.rsplit("/", 1)[0]
            + "/M_MaterialForge.M_MaterialForge",
            "class": "MaterialInstanceConstant",
            "effective_color": None,
        }]
        value["mesh_material_collision_snapshot"][0]["materials"] = [
            self.new_material
        ]
        return value

    def outer_material_receipt(self):
        """Only the structural fixture consumed by saved orchestration tests."""
        material = saved.shoulder_material
        return {
            "schema_version": 3, "outer_terrain_enabled": True,
            "assets": material.asset_paths(material.DESTINATION_ROOT, outer_terrain=True),
            "edge_transition": {**material.EDGE_TRANSITION, "outer_terrain_transition": True},
            "outer_transition": deepcopy(material.OUTER_TRANSITION),
            "terrain_source": {
                "source_packages": deepcopy(material.TERRAIN_PINS),
                "texture_objects": {name: material._object_path(row["path"])
                                    for name, row in material.TERRAIN_PINS.items() if name not in ("master", "instance")},
                "instance": material._object_path(material.TERRAIN_PINS["instance"]["path"]),
                "landscape_component_count": 1024,
            },
            "gpu_compile_verified": False,
            "native_statistics": {"num_samplers": 6, "num_pixel_shader_instructions": 350,
                "num_pixel_texture_samples": 49, "num_vertex_shader_instructions": 10,
                "num_vertex_texture_samples": 0, "num_virtual_texture_samples": 0,
                "num_uv_scalars": 4, "num_interpolator_scalars": 0},
        }

    def shoulder_inventory_fixture(self, *, outer=False):
        original, after = deepcopy(self.old), self.new_inventory()
        assets = saved.shoulder_material.asset_paths(saved.shoulder_material.DESTINATION_ROOT)
        receipt = {"schema_version": saved.shoulder.OUTER_SCHEMA_VERSION if outer else saved.shoulder.SCHEMA_VERSION,
                   "support_count": 186, "material_target_count": 185, "rollback_verified": True,
                   "selected_triangle_count": 67760, "owners": [], "material": {"assets": assets}}
        outer_material = self.outer_material_receipt() if outer else None
        for i in range(186):
            target = i != 181
            material = saved.shoulder_sources.SUPPORT_MATERIAL if target else saved.shoulder_sources.PARAPET_MATERIAL
            label = original["road_supports"][i + 1]["label"]
            receipt["owners"].append({"support_label": label, "material_target": target,
                "kind": "ordinary" if target else "parapet", "source": {"original_material_path": material}})
            canary = next((row for row in saved.OUTER_TERRAIN_CANARY if row["support_label"] == label), None)
            if canary:
                row = receipt["owners"][-1]
                fields = {key: value for key, value in canary.items() if key != "camera_window"}
                row.update(fields)
                row["source"].update(fields, material_target=True)
            for inventory in (original, after):
                inventory["road_supports"][i + 1]["slots"] = [{"path": material}]
                inventory["mesh_material_collision_snapshot"][i + 1]["materials"] = [material]
            if target:
                selected = outer_material["assets"] if outer and label in saved.OUTER_TERRAIN_OWNER_LABELS else assets
                after["road_supports"][i + 1]["slots"].append({"path": selected["instance"], "parent": selected["master"],
                    "class": "MaterialInstanceConstant", "effective_color": None})
                after["mesh_material_collision_snapshot"][i + 1]["materials"].append(selected["instance"])
        if outer:
            receipt["outer_terrain"] = saved.shoulder.outer_configuration(
                {"owners": receipt["owners"]}, outer_material, list(saved.OUTER_TERRAIN_OWNER_LABELS))
        return original, after, receipt

    def marking_receipt(self):
        """Full-count structural fixture only; never source/native evidence."""
        owners = [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(186) if i != 181]
        assets, rows = paint.asset_paths(), []
        for owner in owners:
            for edge in ("edge0", "edge24"):
                label = markings.ACTOR_PREFIX + owner[-3:] + "_" + edge
                path = "<scene>.<world>:PersistentLevel." + label
                rows.append({"label": label, "actor": {
                    "path": path, "label": label, "location_cm": [0., 0., 0.],
                    "rotation_deg": [0., 0., 0.], "scale": [1., 1., 1.],
                }, "component": path + ".DynamicMeshComponent", "material": assets["instance"]})
        return {"schema_version": 1, "status": "EDGE_MARKINGS_CREATED_REVIEW_PENDING",
                "material_packages_saved": True, "native_no_collision": "NO_COLLISION",
                "native_surface_correspondence_verified": True, "all_marking_buffers_verified": True,
                "full_source_buffers_preserved": True, "original_source_state": {"fixture": True},
                "geometry": {"owners": [{"support_label": label} for label in owners], "counts": {
                    "source_owner_count": 186, "pavement_owner_count": 185,
                    "excluded_parapet_count": 1, "mesh_count": 370,
                }}, "actors": rows, "material": {"assets": assets},
                **dict.fromkeys(markings.FALSE_FLAGS, False)}

    def with_marking_inventory(self, receipt=None):
        receipt = receipt or self.marking_receipt()
        value = saved.normalized(self.new_inventory(), saved.session.operation.MAP_PACKAGE)
        additions = saved.edge_marking_inventory(receipt)
        for field, key in (("actors", lambda row: row[0]),
                           ("mesh_material_collision_snapshot", lambda row: row["component"])):
            value[field] = sorted(value[field] + additions[field], key=key)
        package = saved.session.operation.MAP_PACKAGE
        world = package + "." + package.rsplit("/", 1)[-1]
        return json.loads(json.dumps(value).replace("<scene>.<world>", world).replace("<scene>", package))

    def crack_receipt(self):
        """Exact-count structural fixture; no source or native admission claim."""
        source = {"pins": deepcopy(crack_sources.VERIFIED_PINS),
                  "pins_sha256": crack_sources.digest(crack_sources.VERIFIED_PINS),
                  "selected_motifs": list(crack_sources.CANARY_MOTIFS)}
        assets, rows = crack_material.asset_paths(source), []
        for event in crack_geometry.CANARY_EVENTS:
            label = cracks.ACTOR_PREFIX + event.event_id
            path = "<scene>.<world>:PersistentLevel." + label
            rows.append({"label": label, "motif_id": event.motif_id, "actor": {
                "path": path, "label": label, "location_cm": [0., 0., 0.],
                "rotation_deg": [0., 0., 0.], "scale": [1., 1., 1.],
            }, "component": path + ".DynamicMeshComponent", "material": assets[event.motif_id]["instance"]})
        return {"schema_version": 1, "status": "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING",
                "asset_packages_saved": True, "native_no_collision": "NO_COLLISION",
                "native_surface_correspondence_verified": True, "all_crack_buffers_verified": True,
                "full_source_and_existing_paint_buffers_preserved": True, "world_normal_canary_required": True,
                "original_scene_state": {"synthetic_full_white_snapshot": True},
                "geometry": {"counts": {"source_owner_count": 186, "pavement_owner_count": 185,
                                         "excluded_parapet_count": 1, "mesh_count": 2}},
                "imports": {"sources": source, "assets": crack_sources.asset_paths(source), "texture_count": 8},
                "actors": rows, "material": {"assets": assets},
                "owned_asset_paths": list(cracks._owned_asset_paths(source)), **dict.fromkeys(cracks.FALSE_FLAGS, False)}

    def with_crack_inventory(self, receipt=None):
        receipt = receipt or self.crack_receipt()
        package = saved.session.operation.MAP_PACKAGE
        value = saved.normalized(self.with_marking_inventory(), package)
        additions = saved.crack_canary_inventory(receipt)
        for field, key in (("actors", lambda row: row[0]),
                           ("mesh_material_collision_snapshot", lambda row: row["component"])):
            value[field] = sorted(value[field] + additions[field], key=key)
        world = package + "." + package.rsplit("/", 1)[-1]
        return json.loads(json.dumps(value).replace("<scene>.<world>", world).replace("<scene>", package))

    def test_crack_inventory_adds_exactly_two_rows_without_masking_original_or_white_drift(self):
        receipt, white = self.crack_receipt(), self.marking_receipt()
        observed = self.with_crack_inventory(receipt)

        def verify(value, candidate=receipt, paint_receipt=white):
            return saved.expected_saved_inventory(self.old, value, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE,
                edge_marking_receipt=paint_receipt, crack_canary_receipt=candidate)

        self.assertEqual(verify(observed), saved.inventory_digest(
            saved.normalized(observed, saved.session.operation.MAP_PACKAGE)))
        self.assertEqual(len(observed["actors"]), len(self.old["actors"]) + 370 + 2)
        self.assertEqual(len(self.old["actors"]), 2)
        with self.assertRaisesRegex(ValueError, "requires the complete white"):
            verify(observed, paint_receipt=None)
        with self.assertRaisesRegex(ValueError, "changed geometry"):
            verify(observed, candidate=None)
        crack_index = next(i for i, row in enumerate(observed["actors"]) if cracks.ACTOR_PREFIX in row[0])
        white_index = next(i for i, row in enumerate(observed["actors"]) if markings.ACTOR_PREFIX in row[0])
        crack_component = next(i for i, row in enumerate(observed["mesh_material_collision_snapshot"])
                               if cracks.ACTOR_PREFIX in row["component"])
        for mutate in (
            lambda value: value["actors"].pop(crack_index),
            lambda value: value["actors"].append(["/Game/Foreign.Actor", [0., 0., 0.]]),
            lambda value: value["actors"][crack_index][1][0].__setitem__(2, .1),
            lambda value: value["actors"][white_index][1][0].__setitem__(2, .1),
            lambda value: value["mesh_material_collision_snapshot"][crack_component].update(collision="BLOCK_ALL"),
            lambda value: value["mesh_material_collision_snapshot"][crack_component]["materials"].append("foreign"),
            lambda value: value["road_supports"][0].update(vertices=3),
            lambda value: value["landscape"].update(component_count=1023),
        ):
            changed = deepcopy(observed)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                verify(changed)

    def test_crack_inventory_rejects_unowned_assets_transforms_motifs_and_false_normal_admission(self):
        original = self.crack_receipt()
        for mutate in (
            lambda value: value.update(asset_packages_saved=False),
            lambda value: value.update(normal_space_verified=True),
            lambda value: value.update(world_normal_canary_required=False),
            lambda value: value.update(collision_enabled=True),
            lambda value: value["imports"].update(texture_count=7),
            lambda value: value["imports"]["sources"]["pins"].update(run="999"),
            lambda value: value["owned_asset_paths"].pop(),
            lambda value: value["material"]["assets"][crack_sources.CANARY_MOTIFS[0]].update(master="/Game/Foreign.M"),
            lambda value: value["geometry"]["counts"].update(mesh_count=3),
            lambda value: value["actors"].__setitem__(0, value["actors"][1]),
            lambda value: value["actors"][0].update(motif_id="foreign"),
            lambda value: value["actors"][0]["actor"].update(path="/Game/Foreign.Actor"),
            lambda value: value["actors"][0]["actor"].update(scale=[1., 2., 1.]),
            lambda value: value["actors"][0].update(component="<scene>.<world>:PersistentLevel.Foreign.Component"),
        ):
            changed = deepcopy(original)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                saved.crack_canary_inventory(changed)

    def test_saved_inventory_allows_only_exact_verified_render_additions(self):
        receipt = self.marking_receipt()
        observed = self.with_marking_inventory(receipt)

        def verify(value, candidate=receipt):
            return saved.expected_saved_inventory(self.old, value, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE, edge_marking_receipt=candidate)

        self.assertEqual(verify(observed), saved.inventory_digest(
            saved.normalized(observed, saved.session.operation.MAP_PACKAGE)))
        self.assertEqual(len(self.old["actors"]), 2)  # Input baseline is never rewritten.
        with self.assertRaisesRegex(ValueError, "changed geometry"):
            saved.expected_saved_inventory(self.old, observed, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE)
        actor_index = next(i for i, row in enumerate(observed["actors"]) if markings.ACTOR_PREFIX in row[0])
        component_index = next(i for i, row in enumerate(observed["mesh_material_collision_snapshot"])
                               if markings.ACTOR_PREFIX in row["component"])
        mutations = (
            lambda value: value["actors"][actor_index][1][0].__setitem__(2, 0.1),
            lambda value: value["actors"].append(["/Game/Foreign.Actor", [0., 0., 0.]]),
            lambda value: value["actors"].pop(actor_index),
            lambda value: value["mesh_material_collision_snapshot"][component_index].update(collision="BLOCK_ALL"),
            lambda value: value["mesh_material_collision_snapshot"][component_index]["materials"].append("extra"),
            lambda value: value["road_supports"][0].update(vertices=3),
            lambda value: value["road_supports"].pop(),
            lambda value: value["landscape"].update(component_count=1023),
        )
        for mutate in mutations:
            changed = deepcopy(observed)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                verify(changed)
        source, target = saved.session.operation.MAP_PACKAGE, saved.MAP
        raw = json.dumps(observed).replace(source + "." + source.rsplit("/", 1)[-1],
                                           target + "." + target.rsplit("/", 1)[-1]).replace(source, target)
        loaded = json.loads(raw)
        self.assertEqual(saved.expected_saved_inventory(self.old, loaded, self.new_material,
            observed_map_package=target, edge_marking_receipt=receipt), verify(observed))

    def test_marking_inventory_rejects_incomplete_ownership_receipts_and_path_aliases(self):
        receipt = self.marking_receipt()
        for mutate in (
            lambda value: value.update(material_packages_saved=False),
            lambda value: value.update(native_surface_correspondence_verified=False),
            lambda value: value.update(collision_enabled=True),
            lambda value: value["geometry"]["owners"].pop(),
            lambda value: value["geometry"]["owners"][0].update(support_label="YACS_PERSIST_SUPPORT_999"),
            lambda value: value["actors"].pop(),
            lambda value: value["actors"].__setitem__(0, value["actors"][1]),
            lambda value: value["actors"][0]["actor"].update(path="/Game/Foreign.Actor"),
            lambda value: value["actors"][0]["actor"].update(location_cm=[0., 0., 1.]),
            lambda value: value["actors"][0].update(component="<scene>.<world>:PersistentLevel.Foreign.Component"),
            lambda value: value["material"]["assets"].update(instance="/Game/Foreign.MI"),
        ):
            changed = deepcopy(receipt)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                saved.edge_marking_inventory(changed)

    def test_edge_lane_is_explicit_and_does_not_silently_skip_an_enabled_receipt(self):
        for value, expected in (("0", False), ("1", True)):
            with patch.dict("os.environ", {"YACS_ROAD_EDGE_MARKINGS": value}):
                self.assertIs(saved.edge_markings_enabled(), expected)
        for value in ("", "yes", "true", "2"):
            with patch.dict("os.environ", {"YACS_ROAD_EDGE_MARKINGS": value}), self.assertRaises(ValueError):
                saved.edge_markings_enabled()
        self.assertIsNone(saved.verify_edge_markings(None, {}, enabled=False))
        for manifest, enabled in (({}, True), ({"edge_markings": {}}, False),
                                  ({"edge_markings_enabled": True}, False),
                                  ({"edge_markings_enabled": True, "edge_markings": {}}, "1")):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                saved.verify_edge_markings(None, manifest, enabled=enabled)

    def test_new_paint_material_save_failure_cleans_only_owned_new_objects(self):
        original = self.marking_receipt()
        original.pop("material_packages_saved")
        original.pop("native_no_collision")
        snapshot = deepcopy(original)
        actors, plan, asphalt = (object(), object()), object(), object()
        saved_assets = {path: object() for path in paint.asset_paths().values()}
        api = SimpleNamespace(load_asset=lambda path: saved_assets[path],
            EditorAssetLibrary=SimpleNamespace(save_loaded_asset=Mock(return_value=True)),
            CollisionEnabled=SimpleNamespace(NO_COLLISION="NO_COLLISION"))
        with patch.object(markings, "create", return_value=(actors, original)) as create, \
             patch.object(markings, "_rollback_created") as rollback, \
             patch.object(markings, "_world", return_value=saved.session.operation.MAP_PACKAGE):
            actual_actors, receipt = saved.create_edge_markings(api, plan, asphalt)
            self.assertIs(actual_actors, actors)
            self.assertTrue(receipt["material_packages_saved"])
            self.assertEqual(original, snapshot)
            create.assert_called_once_with(api, plan, asphalt)
            self.assertEqual([call.args[0] for call in api.EditorAssetLibrary.save_loaded_asset.call_args_list],
                             list(saved_assets.values()))
            self.assertTrue(all(call.kwargs == {"only_if_is_dirty": False}
                                for call in api.EditorAssetLibrary.save_loaded_asset.call_args_list))
            rollback.assert_not_called()
            api.EditorAssetLibrary.save_loaded_asset.reset_mock(side_effect=True)
            api.EditorAssetLibrary.save_loaded_asset.side_effect = [True, False]
            with self.assertRaisesRegex(ValueError, "marking material save failed"):
                saved.create_edge_markings(api, plan, asphalt)
            rollback.assert_called_once_with(api, actors, original["original_source_state"],
                                             saved.session.operation.MAP_PACKAGE)

    def test_fresh_paint_entry_rebuilds_pinned_plan_then_only_reads_and_requires_package_pins(self):
        receipt = self.marking_receipt()
        source, plan = object(), object()
        manifest = {"edge_markings_enabled": True, "edge_markings": receipt,
                    "material_instance": "asphalt-mi", "material_master": "asphalt-m",
                    "texture_objects": {"BaseColor": "existing-tex"},
                    "assets": [{"path": "Content/" + path.split(".", 1)[0].removeprefix("/Game/") + ".uasset"}
                               for path in paint.asset_paths().values()]}
        api = SimpleNamespace(CollisionEnabled=SimpleNamespace(NO_COLLISION="NO_COLLISION"))
        result = {"status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED", "read_only": True}
        before = deepcopy(manifest)
        with patch.object(saved.shoulder_sources, "load_sources", return_value=source) as load, \
             patch.object(saved, "load_edge_marking_plan", return_value=plan) as build, \
             patch.object(markings, "verify_loaded", return_value=result) as verify, \
             patch.object(markings, "create") as create, \
             patch.object(saved, "create_edge_markings") as save:
            self.assertIs(saved.verify_edge_markings(api, manifest, enabled=True), result)
            load.assert_called_once_with()
            build.assert_called_once_with(source)
            verify.assert_called_once_with(api, plan, receipt, {
                "instance": "asphalt-mi", "master": "asphalt-m", "textures": {"BaseColor": "existing-tex"}})
            create.assert_not_called()
            save.assert_not_called()
            self.assertEqual(manifest, before)
            verify.reset_mock()
            manifest["assets"].pop()
            with self.assertRaisesRegex(ValueError, "retained byte identities"):
                saved.verify_edge_markings(api, manifest, enabled=True)
            verify.assert_not_called()
            manifest["assets"] = before["assets"]
            manifest["edge_markings"]["native_no_collision"] = "BLOCK_ALL"
            with self.assertRaisesRegex(ValueError, "collision enum"):
                saved.verify_edge_markings(api, manifest, enabled=True)

    def test_edge_plan_loader_reads_exact_inert_bytes_before_calling_the_resolver(self):
        raw = b"not executable Python: explicit loader fixture\r\n"
        identity = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        source, plan = object(), object()
        addresses = {"quad_triangles": ((0, 1, 2), (1, 3, 2)), "triangle_bindings": (("fixture",),)}
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            path = data / Path(saved.session.PROFILE_RELATIVE).parent / markings.PRODUCER_PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            with patch.object(saved, "load_workspace", return_value={"data": str(data)}), \
                 patch.object(markings, "PRODUCER_IDENTITY", identity), \
                 patch.object(pavement_bindings, "prepare_bindings", return_value=addresses) as bind, \
                 patch.object(markings, "prepare", return_value=plan) as prepare:
                self.assertIs(saved.load_edge_marking_plan(source), plan)
                bind.assert_called_once_with(source, producer_bytes=raw)
                prepare.assert_called_once_with(source, producer_bytes=raw, **addresses)
                bind.reset_mock()
                prepare.reset_mock()
                path.write_bytes(raw.replace(b"\r\n", b"\n"))
                with self.assertRaisesRegex(ValueError, "exact retained pavement producer"):
                    saved.load_edge_marking_plan(source)
                bind.assert_not_called()
                prepare.assert_not_called()

    def test_crack_lane_requires_explicit_boolean_and_existing_white_mode(self):
        for white, value, expected in (("0", "0", False), ("1", "0", False), ("1", "1", True)):
            with patch.dict("os.environ", {"YACS_ROAD_EDGE_MARKINGS": white, "YACS_ROAD_CRACK_CANARY": value}):
                self.assertIs(saved.crack_canary_enabled(), expected)
        for white, value in (("0", "1"), ("1", "yes"), ("1", ""), ("1", "2")):
            with patch.dict("os.environ", {"YACS_ROAD_EDGE_MARKINGS": white, "YACS_ROAD_CRACK_CANARY": value}), \
                 self.assertRaises(ValueError):
                saved.crack_canary_enabled()
        self.assertEqual(saved.verify_surface_details(None, {}, False, False),
                         {"edge_markings": None, "crack_canary": None})
        for manifest, white, enabled in (({}, False, True), ({}, True, "1"),
                ({"crack_canary": {}}, False, False), ({"crack_canary_enabled": True}, True, False),
                ({"crack_canary_enabled": True}, True, True)):
            with self.subTest(manifest=manifest, white=white, enabled=enabled), self.assertRaises(ValueError):
                saved.verify_surface_details(None, manifest, white, enabled)

    def test_crack_plan_loader_authenticates_source_and_passes_actual_zero_ninety_uv_contracts(self):
        source_plan, plan, producer = object(), object(), b"inert authenticated producer fixture"
        source = {"motifs": {event.motif_id: {"extent_cm": event.extent_m * 100.,
            "empty_border_cm": 6., "resolution": 2048} for event in crack_geometry.CANARY_EVENTS}}
        source_root = Path("retained-crack-source")
        with patch.object(saved, "_retained_pavement_producer_bytes", return_value=producer) as read, \
             patch.object(crack_sources, "source_root", return_value=source_root), \
             patch.object(crack_sources, "load_sources", return_value=source) as load, \
             patch.object(cracks, "prepare", return_value=plan) as prepare, \
             patch.object(cracks, "create") as create:
            self.assertIs(saved.load_crack_plan(source_plan), plan)
            read.assert_called_once_with()
            load.assert_called_once_with(source_root, crack_sources.VERIFIED_PINS)
            prepare.assert_called_once_with(source_plan, producer_bytes=producer, geometry_contracts={
                event.motif_id: crack_material.geometry_contract(source["motifs"][event.motif_id],
                    uv_rotation_degrees=event.rotation_deg) for event in crack_geometry.CANARY_EVENTS})
            self.assertEqual([row["uv_rotation_degrees"] for row in prepare.call_args.kwargs["geometry_contracts"].values()],
                             [0., 90.])
            create.assert_not_called()

    def test_crack_save_owns_all_eleven_packages_and_cleanup_preserves_existing_white(self):
        original = self.crack_receipt()
        original.pop("asset_packages_saved")
        original.pop("native_no_collision")
        snapshot = deepcopy(original)
        actors, plan, asphalt, white_plan, white_receipt = (object(), object()), object(), object(), object(), self.marking_receipt()
        assets = {path: object() for path in original["owned_asset_paths"]}
        source_root = Path("retained-crack-source")
        api = SimpleNamespace(load_asset=lambda path: assets[path],
            EditorAssetLibrary=SimpleNamespace(save_loaded_asset=Mock(return_value=True)),
            CollisionEnabled=SimpleNamespace(NO_COLLISION="NO_COLLISION"))
        with patch.object(crack_sources, "source_root", return_value=source_root), \
             patch.object(cracks, "create", return_value=(actors, original)) as create, \
             patch.object(cracks, "_rollback") as rollback, \
             patch.object(markings, "_world", return_value=saved.session.operation.MAP_PACKAGE):
            actual_actors, receipt = saved.create_crack_canary(api, plan, asphalt,
                white_plan=white_plan, white_receipt=white_receipt)
            self.assertIs(actual_actors, actors)
            self.assertTrue(receipt["asset_packages_saved"])
            self.assertFalse(receipt["normal_space_verified"])
            self.assertEqual(original, snapshot)
            create.assert_called_once_with(api, plan, source_root, crack_sources.VERIFIED_PINS, asphalt,
                                           white_plan=white_plan, white_receipt=white_receipt)
            calls = api.EditorAssetLibrary.save_loaded_asset.call_args_list
            self.assertEqual([call.args[0] for call in calls], list(assets.values()))
            self.assertEqual(len(calls), 11)
            self.assertTrue(all(call.kwargs == {"only_if_is_dirty": False} for call in calls))
            rollback.assert_not_called()
            api.EditorAssetLibrary.save_loaded_asset.reset_mock(side_effect=True)
            api.EditorAssetLibrary.save_loaded_asset.side_effect = [True] * 10 + [False]
            with self.assertRaisesRegex(ValueError, "crack canary asset save failed"):
                saved.create_crack_canary(api, plan, asphalt, white_plan=white_plan, white_receipt=white_receipt)
            rollback.assert_called_once_with(api, actors, original["owned_asset_paths"], original["original_scene_state"],
                saved.session.operation.MAP_PACKAGE, white_plan=white_plan, white_receipt=white_receipt, asphalt_assets=asphalt)

    def test_fresh_crack_aggregate_replays_white_and_cracks_with_every_package_pinned(self):
        white, receipt = self.marking_receipt(), self.crack_receipt()
        paths = list(white["material"]["assets"].values()) + receipt["owned_asset_paths"]
        manifest = {"edge_markings_enabled": True, "edge_markings": white,
                    "crack_canary_enabled": True, "crack_canary": receipt,
                    "material_instance": "asphalt-mi", "material_master": "asphalt-m",
                    "texture_objects": {"BaseColor": "existing-tex"},
                    "assets": [{"path": "Content/" + path.split(".", 1)[0].removeprefix("/Game/") + ".uasset"}
                               for path in paths]}
        source_plan, white_plan, plan = object(), object(), object()
        source_root = Path("retained-crack-source")
        white_readback = {"status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED", "actor_count": 370,
                          "read_only": True, "aggregate_owner": "local_crack_canary"}
        readback = {"status": "LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING", "actor_count": 2,
                    "read_only": True, "world_normal_canary_required": True, "normal_space_verified": False,
                    "edge_markings": white_readback}
        api = SimpleNamespace(CollisionEnabled=SimpleNamespace(NO_COLLISION="NO_COLLISION"))
        before = deepcopy(manifest)
        with patch.object(saved.shoulder_sources, "load_sources", return_value=source_plan) as load, \
             patch.object(saved, "load_edge_marking_plan", return_value=white_plan) as white_build, \
             patch.object(saved, "load_crack_plan", return_value=plan) as build, \
             patch.object(crack_sources, "source_root", return_value=source_root), \
             patch.object(cracks, "verify_loaded", return_value=readback) as verify, \
             patch.object(markings, "verify_loaded") as old_white_verify, \
             patch.object(cracks, "create") as create, patch.object(saved, "create_crack_canary") as save:
            actual = saved.verify_surface_details(api, manifest, True, True)
            self.assertIs(actual["edge_markings"], white_readback)
            self.assertNotIn("edge_markings", actual["crack_canary"])
            self.assertFalse(actual["crack_canary"]["normal_space_verified"])
            load.assert_called_once_with()
            white_build.assert_called_once_with(source_plan)
            build.assert_called_once_with(source_plan)
            verify.assert_called_once_with(api, plan, receipt, source_root, crack_sources.VERIFIED_PINS,
                {"instance": "asphalt-mi", "master": "asphalt-m", "textures": {"BaseColor": "existing-tex"}},
                white_plan=white_plan, white_receipt=white)
            old_white_verify.assert_not_called()
            create.assert_not_called()
            save.assert_not_called()
            self.assertEqual(manifest, before)
            verify.reset_mock()
            manifest["assets"].pop()
            with self.assertRaisesRegex(ValueError, "retained byte identities"):
                saved.verify_surface_details(api, manifest, True, True)
            verify.assert_not_called()
            manifest["assets"] = before["assets"]
            manifest["crack_canary"]["native_no_collision"] = "BLOCK_ALL"
            with self.assertRaisesRegex(ValueError, "collision enum"):
                saved.verify_surface_details(api, manifest, True, True)

    @contextmanager
    def saved_lane_fixture(self, *, crack_canary=False, fail_map=False, fail_paint_cleanup=False,
                           fail_crack_cleanup=False, fail_crack_asset=False, outer_terrain=False, fail_outer_asset=False):
        """Exercise orchestration and real file pins with explicit native stubs.

        Separate tests above and in the paint consumer check full inventories
        and mesh behaviour; these synthetic bytes are not Unreal packages.
        """
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root, events = Path(directory) / "project", []
            root.mkdir()
            proof, retained = Path(directory) / "proof", Path(directory) / "retained"
            proof.mkdir()
            old_asset = SimpleNamespace(get_path_name=lambda: self.old["road_supports"][0]["slots"][0]["path"])
            new_asset = SimpleNamespace(get_path_name=lambda: self.new_material)
            state = {"material": old_asset, "shoulder": False, "cracks": False, "outer": False,
                     "package": saved.session.operation.MAP_PACKAGE}

            def set_material(slot, asset):
                self.assertEqual(slot, 0)
                events.append("road-original" if asset is old_asset else "road-asphalt")
                state["material"] = asset

            component = SimpleNamespace(get_material=lambda _: state["material"], set_material=set_material,
                get_path_name=lambda: self.old["road_supports"][0]["component"])
            road = SimpleNamespace(get_actor_label=lambda: saved.canary.ROAD_LABEL,
                                   get_dynamic_mesh_component=lambda: component)
            world = SimpleNamespace(get_path_name=lambda: state["package"] + "." + state["package"].rsplit("/", 1)[-1])
            subsystem = SimpleNamespace(get_all_level_actors=lambda: [road], get_editor_world=lambda: world)

            def save_asset(asset, only_if_is_dirty):
                self.assertIs(only_if_is_dirty, False)
                if fail_crack_asset and asset.get_path_name() == native_cracks["owned_asset_paths"][-1]:
                    events.append("crack-asset-save-failed")
                    return False
                if fail_outer_asset and asset.get_path_name() == outer_material["assets"]["instance"]:
                    events.append("outer-asset-save-failed")
                    return False
                relative = "Content/" + asset.get_path_name().split(".", 1)[0].removeprefix("/Game/") + ".uasset"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("SYNTHETIC PACKAGE FIXTURE " + relative).encode())
                return True

            def save_map(_world, package):
                events.append("save-map")
                self.assertEqual(package, saved.MAP)
                if fail_map:
                    return False
                path = root / saved.MAP_FILE
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"SYNTHETIC DERIVED MAP FIXTURE")
                return True

            api = SimpleNamespace(EditorActorSubsystem=object(), UnrealEditorSubsystem=object(),
                get_editor_subsystem=lambda _: subsystem, log=Mock(),
                load_asset=lambda path: SimpleNamespace(get_path_name=lambda: path),
                EditorAssetLibrary=SimpleNamespace(save_loaded_asset=save_asset),
                EditorLoadingAndSavingUtils=SimpleNamespace(save_map=save_map),
                CollisionEnabled=SimpleNamespace(NO_COLLISION="NO_COLLISION"))
            landscape = object()
            api.Landscape = type("Landscape", (), {})
            api.GameplayStatics = SimpleNamespace(get_all_actors_of_class=lambda _world, _kind: [landscape])
            observed_statistics = dict.fromkeys(saved.shoulder_material.STATISTICS_FIELDS, 0)
            api.MaterialEditingLibrary = SimpleNamespace(get_statistics=lambda _: SimpleNamespace(
                get_editor_property=lambda name: observed_statistics[name]))
            asphalt_assets = {"instance": self.new_material,
                "master": self.new_material.rsplit("/", 1)[0] + "/M_MaterialForge.M_MaterialForge",
                "textures": {name: self.new_material.rsplit("/", 1)[0] + "/T_" + name + ".T_" + name
                             for name in saved.TEXTURES.values()}}
            imported = {"status": "IMPORTED_UE_REVIEW_PENDING", "family": saved.asphalt_contract.FAMILY,
                "variant": saved.asphalt_contract.VARIANT, "saved": True,
                "graph_sha256": saved.asphalt_source.GRAPH_SHA256, "tile_metres": 4,
                "normal_convention": "DirectX", "landscape_mutated": False, "geometry_changed": False,
                "assets": asphalt_assets, "dry_asphalt_response": {"synthetic": True}}

            def forge_import(*_args, **_kwargs):
                for path in (asphalt_assets["instance"], asphalt_assets["master"], *asphalt_assets["textures"].values()):
                    save_asset(api.load_asset(path), False)
                return new_asset, imported

            shoulder_receipt = self.shoulder_inventory_fixture(outer=outer_terrain)[2]
            gravel_receipt = shoulder_receipt["material"]
            outer_material = None if not outer_terrain else shoulder_receipt["outer_terrain"]["material"]
            outer_instance = None if outer_material is None else api.load_asset(outer_material["assets"]["instance"])
            rollback_state, marking_plan, crack_plan = object(), object(), object()
            source_plan = {"owners": shoulder_receipt["owners"]}
            consumer_assets = list(deepcopy(saved.shoulder_material.TERRAIN_PINS).values())
            native_paint = self.marking_receipt()
            native_paint.pop("material_packages_saved")
            native_paint.pop("native_no_collision")
            paint_actors = (object(),)
            native_cracks = self.crack_receipt()
            native_cracks.pop("asset_packages_saved")
            native_cracks.pop("native_no_collision")
            crack_actors = (object(), object())
            crack_root = Path(directory) / "crack-source-fixture"

            def prepare_shoulders(*_args, **kwargs):
                self.assertEqual(kwargs, {} if not outer_terrain else {
                    "outer_instance": outer_instance, "outer_material_receipt": outer_material,
                    "outer_owner_labels": list(saved.OUTER_TERRAIN_OWNER_LABELS)})
                events.append("shoulder-asphalt")
                state["shoulder"] = True
                state["outer"] = outer_terrain
                return shoulder_receipt, rollback_state

            def rollback_shoulders(_api, rollback):
                self.assertIs(rollback, rollback_state)
                self.assertIs(state["material"], old_asset)
                events.append("shoulder-original")
                state["shoulder"] = False
                state["outer"] = False

            def create_material(_api, _root, _dependencies, _asphalt, **kwargs):
                if not kwargs:
                    return api.load_asset(gravel_receipt["assets"]["instance"]), gravel_receipt
                self.assertIs(kwargs["terrain_consumer_assets"], consumer_assets)
                self.assertIs(kwargs["landscape"], landscape)
                return outer_instance, outer_material

            def cleanup_paint(_api, actors, before, package):
                self.assertIs(actors, paint_actors)
                self.assertEqual(before, native_paint["original_source_state"])
                self.assertIs(state["material"], new_asset)
                self.assertTrue(state["shoulder"])
                self.assertFalse(state["cracks"])
                self.assertEqual(package, saved.session.operation.MAP_PACKAGE)
                events.append("paint-rollback")
                if fail_paint_cleanup:
                    raise ValueError("fixture owned paint cleanup failed")

            def create_cracks(_api, plan, source_root, pins, asphalt, *, white_plan, white_receipt):
                self.assertIs(plan, crack_plan)
                self.assertEqual(source_root, crack_root)
                self.assertEqual(pins, crack_sources.VERIFIED_PINS)
                self.assertIs(asphalt, asphalt_assets)
                self.assertIs(white_plan, marking_plan)
                self.assertTrue(white_receipt["material_packages_saved"])
                self.assertIs(state["material"], new_asset)
                self.assertTrue(state["shoulder"])
                events.append("cracks-create")
                state["cracks"] = True
                return crack_actors, native_cracks

            def cleanup_cracks(_api, actors, paths, before, package, *, white_plan, white_receipt, asphalt_assets):
                self.assertIs(actors, crack_actors)
                self.assertEqual(paths, native_cracks["owned_asset_paths"])
                self.assertEqual(before, native_cracks["original_scene_state"])
                self.assertEqual(package, saved.session.operation.MAP_PACKAGE)
                self.assertIs(white_plan, marking_plan)
                self.assertTrue(white_receipt["material_packages_saved"])
                self.assertEqual(asphalt_assets, imported["assets"])
                self.assertIs(state["material"], new_asset)
                self.assertTrue(state["shoulder"])
                self.assertTrue(state["cracks"])
                events.append("cracks-rollback")
                for path in paths:
                    package_file = root / ("Content/" + path.split(".", 1)[0].removeprefix("/Game/") + ".uasset")
                    package_file.unlink(missing_ok=True)
                state["cracks"] = False
                if fail_crack_cleanup:
                    raise ValueError("fixture owned crack cleanup failed")

            readback = {"status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED", "actor_count": 370, "read_only": True}
            aggregate_white = {**readback, "aggregate_owner": "local_crack_canary"}
            crack_readback = {"status": "LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING", "actor_count": 2,
                "read_only": True, "world_normal_canary_required": True, "normal_space_verified": False,
                "edge_markings": aggregate_white}
            patches = {}
            for owner, name, kwargs in (
                (saved, "ROOT", {"new": root}),
                (saved, "native_world", {"side_effect": lambda _api, package: state.update(package=package)}),
                (saved, "verify_material_instance", {"return_value": new_asset}),
                (saved, "expected_saved_inventory", {"return_value": "d" * 64}),
                (saved, "load_edge_marking_plan", {"return_value": marking_plan}),
                (saved, "load_crack_plan", {"return_value": crack_plan}),
                (saved.baseline, "native_inventory", {"return_value": deepcopy(self.old)}),
                (saved.baseline, "road_support_actors", {"return_value": [road]}),
                (saved.baseline, "native_projection", {}), (saved.baseline, "dirty_packages", {}),
                (saved.shoulder_sources, "load_sources", {"return_value": source_plan}),
                (saved.shoulder_sources, "network_profile_report", {"return_value": {"synthetic": True}}),
                (saved.asphalt_source, "verify_retained_replay", {"return_value": {"synthetic": True}}),
                (saved.asphalt_source, "source_root", {"return_value": Path(directory) / "forge-source-fixture"}),
                (saved.shoulder, "inspect_mesh", {"return_value": {"summary": {"synthetic": True}}}),
                (saved.shoulder, "prepare", {"side_effect": prepare_shoulders}),
                (saved.shoulder, "rollback", {"side_effect": rollback_shoulders}),
                (saved.shoulder, "verify_loaded", {}),
                (saved.shoulder_material, "create_material", {"side_effect": create_material}),
                (saved.shoulder_material, "verify_material", {"side_effect":
                    lambda _api, receipt, _dependencies, **_kwargs: api.load_asset(receipt["assets"]["instance"])}),
                (saved.session, "_verify_rows", {}), (saved.session, "_assert_package_members", {}),
                (markings, "create", {"return_value": (paint_actors, native_paint)}),
                (markings, "verify_loaded", {"return_value": readback}),
                (markings, "_rollback_created", {"side_effect": cleanup_paint}),
                (markings, "_world", {"return_value": saved.session.operation.MAP_PACKAGE}),
                (crack_sources, "source_root", {"return_value": crack_root}),
                (cracks, "create", {"side_effect": create_cracks}),
                (cracks, "verify_loaded", {"return_value": crack_readback}),
                (cracks, "_rollback", {"side_effect": cleanup_cracks}),
            ):
                patches[(owner.__name__, name)] = stack.enter_context(patch.object(owner, name, **kwargs))
            stack.enter_context(patch.dict("sys.modules", {"scripts.ue.import_material_forge_variant":
                                                          SimpleNamespace(import_variant=forge_import)}))
            yield SimpleNamespace(api=api, proof=proof, retained=retained, events=events, state=state,
                args=(api, proof, retained, "a" * 40, "b" * 64, {"native_inventory": self.old}, []),
                kwargs={"source_dependencies": [], "edge_markings": True, "crack_canary": crack_canary,
                        "outer_terrain": outer_terrain, "terrain_consumer_assets": consumer_assets},
                readback=readback, aggregate_white=aggregate_white, crack_readback=crack_readback, patches=patches)

    def test_enabled_saved_lane_pins_paint_packages_then_fresh_reopens_without_reapplying(self):
        with self.saved_lane_fixture() as lane:
            saved.prepare(*lane.args, **lane.kwargs)
            manifest = json.loads((lane.proof / saved.MANIFEST).read_text())
            self.assertTrue(manifest["edge_markings_enabled"])
            self.assertTrue(manifest["edge_markings"]["material_packages_saved"])
            self.assertEqual(len(manifest["assets"]), 11)
            self.assertEqual(manifest["material_changes"], "road_slot_zero_network_outer_shoulder_ids_and_edge_uv")
            self.assertFalse(manifest["source_scene_mutated"])
            saved.verify_retained_files(lane.retained, manifest["assets"])
            saved.verified_manifest_identity(lane.proof, lane.retained)
            events = list(lane.events)
            saved.reload(*lane.args, **lane.kwargs)
            self.assertEqual(lane.events, events)
            receipt = json.loads((lane.proof / saved.RELOADED).read_text())
            self.assertTrue(receipt["edge_markings_fresh_reload_verified"])
            self.assertFalse(receipt["edge_marking_material_reapplied"])
            self.assertFalse(receipt["edge_marking_geometry_reapplied"])
            self.assertEqual(receipt["edge_marking_readback"], lane.readback)
            self.assertTrue(receipt["shoulder_material_edge_uv_fresh_reload_verified"])

    def test_outer_lane_is_explicit_and_requires_exact_five_owner_frozen_surface_contract(self):
        for value, expected in (("0", False), ("1", True)):
            with patch.dict("os.environ", {"YACS_ROAD_OUTER_TERRAIN_CANARY": value}):
                self.assertIs(saved.outer_terrain_enabled(), expected)
        for value in ("", "true", "yes", "2"):
            with patch.dict("os.environ", {"YACS_ROAD_OUTER_TERRAIN_CANARY": value}), self.assertRaises(ValueError):
                saved.outer_terrain_enabled()
        network = self.shoulder_inventory_fixture(outer=True)[2]
        manifest = {"outer_terrain_enabled": True, "shoulder_network": network}
        self.assertEqual(saved.outer_terrain_receipt(manifest), network["outer_terrain"])
        paths = saved.outer_terrain_texture_paths(manifest)
        self.assertEqual(len(paths), 11)
        self.assertEqual(len(set(paths)), 11)
        self.assertEqual(paths[0], saved.shoulder_material._object_path(saved.shoulder_material.TERRAIN_PINS["WeightTex"]["path"]))
        for mutate in (
            lambda value: value.update(outer_terrain_enabled=False),
            lambda value: value.update(outer_terrain_enabled="1"),
            lambda value: value["shoulder_network"].update(schema_version=3),
            lambda value: value["shoulder_network"]["outer_terrain"]["owner_labels"].__setitem__(0, "YACS_PERSIST_SUPPORT_022"),
            lambda value: value["shoulder_network"]["outer_terrain"].update(physical_contact_verified=True),
            lambda value: value["shoulder_network"]["outer_terrain"].update(uv_channel=0),
            lambda value: value["shoulder_network"]["owners"][182].update(window_id="other_nudo_level"),
            lambda value: value["shoulder_network"]["owners"][182]["source"].update(kind="parapet"),
            lambda value: value["shoulder_network"]["owners"][18].update(selected_triangle_count=708),
            lambda value: value["shoulder_network"]["outer_terrain"]["material"]["terrain_source"]["texture_objects"].pop("ScreeNormalTex"),
            lambda value: value["shoulder_network"]["outer_terrain"]["material"]["terrain_source"]["source_packages"]["WeightTex"].update(sha256="0" * 64),
        ):
            changed = deepcopy(manifest)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                saved.outer_terrain_texture_paths(changed)
        legacy = {"outer_terrain_enabled": False, "shoulder_network": self.shoulder_inventory_fixture()[2]}
        self.assertEqual(saved.outer_terrain_texture_paths(legacy), [])

    def test_outer_native_helper_reads_both_materials_and_actual_landscape_without_mutators(self):
        network = self.shoulder_inventory_fixture(outer=True)[2]
        manifest = {"outer_terrain_enabled": True, "shoulder_network": network, "assets": []}
        for receipt in (network["material"], network["outer_terrain"]["material"]):
            manifest["assets"].extend({"path": "Content/" + path.split(".", 1)[0].removeprefix("/Game/") + ".uasset"}
                                      for path in receipt["assets"].values())
        landscape, world, dependencies, consumer = object(), object(), object(), object()
        landscapes = [landscape]
        statistics = dict.fromkeys(saved.shoulder_material.STATISTICS_FIELDS, 0)
        api = SimpleNamespace(UnrealEditorSubsystem=object(), Landscape=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(get_editor_world=lambda: world),
            GameplayStatics=SimpleNamespace(get_all_actors_of_class=lambda w, cls: landscapes if w is world and cls is api.Landscape else []),
            MaterialEditingLibrary=SimpleNamespace(get_statistics=lambda _: SimpleNamespace(
                get_editor_property=lambda name: statistics[name])))
        before = deepcopy(manifest)
        with patch.object(saved.shoulder_material, "verify_material", side_effect=lambda _api, receipt, _dependencies, **_kwargs:
                          SimpleNamespace(get_path_name=lambda: receipt["assets"]["instance"])) as verify:
            result = saved.verify_shoulder_materials(api, manifest, dependencies, consumer)
            self.assertEqual(result["status"], "SHOULDER_MATERIALS_NATIVE_READBACK_VERIFIED")
            self.assertEqual(result["outer_owner_labels"], list(saved.OUTER_TERRAIN_OWNER_LABELS))
            self.assertEqual(result["landscape_component_count"], 1024)
            self.assertTrue(result["read_only"])
            self.assertFalse(result["physical_contact_verified"])
            self.assertFalse(result["normal_response_visual_verified"])
            self.assertEqual(result["outer_native_statistics"], statistics)
            self.assertNotEqual(result["outer_native_statistics"], network["outer_terrain"]["material"]["native_statistics"])
            self.assertFalse(result["outer_gpu_compile_verified"])
            self.assertEqual(verify.call_count, 2)
            self.assertEqual(verify.call_args_list[0].kwargs, {})
            self.assertIs(verify.call_args_list[1].kwargs["terrain_consumer_assets"], consumer)
            self.assertIs(verify.call_args_list[1].kwargs["landscape"], landscape)
            self.assertEqual(manifest, before)
            verify.reset_mock()
            manifest["assets"].pop()
            with self.assertRaisesRegex(ValueError, "fully retained"):
                saved.verify_shoulder_materials(api, manifest, dependencies, consumer)
            verify.assert_not_called()
            manifest["assets"] = before["assets"]
            for count in (0, 2):
                landscapes[:] = [landscape] * count
                with self.subTest(landscape_count=count), self.assertRaisesRegex(ValueError, "exactly one actual"):
                    saved.verify_shoulder_materials(api, manifest, dependencies, consumer)
            landscapes[:] = [landscape]
            with self.assertRaisesRegex(ValueError, "frozen consumer inventory"):
                saved.verify_shoulder_materials(api, manifest, dependencies)

    def test_outer_saved_lane_retains_only_two_new_packages_and_fresh_never_reauthors(self):
        for cracks_enabled in (False, True):
            with self.subTest(cracks=cracks_enabled), self.saved_lane_fixture(
                    outer_terrain=True, crack_canary=cracks_enabled) as lane:
                saved.prepare(*lane.args, **lane.kwargs)
                manifest = json.loads((lane.proof / saved.MANIFEST).read_text())
                prepared = json.loads((lane.proof / saved.PREPARED).read_text())
                self.assertIs(manifest["outer_terrain_enabled"], True)
                self.assertIs(prepared["outer_terrain_enabled"], True)
                self.assertEqual(manifest["shoulder_network"]["schema_version"], 4)
                self.assertEqual(manifest["shoulder_network"]["outer_terrain"]["owner_labels"], list(saved.OUTER_TERRAIN_OWNER_LABELS))
                self.assertEqual(len(manifest["assets"]), 24 if cracks_enabled else 13)
                self.assertEqual(sum("/TerrainBlend/" in row["path"] for row in manifest["assets"]), 2)
                saved.verify_retained_files(lane.retained, manifest["assets"])
                events = list(lane.events)
                creator = lane.patches[(saved.shoulder_material.__name__, "create_material")]
                self.assertEqual(creator.call_count, 2)
                saved.reload(*lane.args, **lane.kwargs)
                self.assertEqual(creator.call_count, 2)
                self.assertEqual(lane.events, events)
                fresh = json.loads((lane.proof / saved.RELOADED).read_text())
                self.assertIs(fresh["outer_terrain_enabled"], True)
                self.assertIs(fresh["outer_terrain_fresh_reload_verified"], True)
                self.assertIs(fresh["outer_material_reapplied"], False)
                self.assertIs(fresh["outer_geometry_reapplied"], False)
                self.assertEqual(fresh["outer_terrain_readback"]["outer_owner_labels"], list(saved.OUTER_TERRAIN_OWNER_LABELS))
                self.assertFalse(fresh["outer_terrain_readback"]["normal_response_visual_verified"])
                self.assertFalse(fresh["outer_terrain_readback"]["physical_contact_verified"])
                self.assertEqual(fresh["outer_terrain_readback"]["outer_native_statistics"],
                                 dict.fromkeys(saved.shoulder_material.STATISTICS_FIELDS, 0))
                self.assertFalse(fresh["outer_terrain_readback"]["outer_gpu_compile_verified"])
                lane.patches[(saved.shoulder.__name__, "prepare")].assert_called_once()
                lane.patches[(saved.shoulder.__name__, "verify_loaded")].assert_called_once()

    def test_outer_package_save_failure_precedes_all_source_writes_and_map_failure_rolls_back_uv_owner(self):
        with self.saved_lane_fixture(outer_terrain=True, fail_outer_asset=True) as lane:
            with self.assertRaisesRegex(ValueError, "shoulder material save failed"):
                saved.prepare(*lane.args, **lane.kwargs)
            self.assertEqual(lane.events, ["outer-asset-save-failed"])
            self.assertFalse(lane.state["shoulder"])
            self.assertFalse(lane.state["outer"])
            self.assertFalse((lane.proof / saved.PREPARED).exists())
            lane.patches[(saved.shoulder.__name__, "prepare")].assert_not_called()
        with self.saved_lane_fixture(outer_terrain=True, crack_canary=True, fail_map=True) as lane:
            with self.assertRaisesRegex(ValueError, "map save failed"):
                saved.prepare(*lane.args, **lane.kwargs)
            self.assertEqual(lane.events, ["road-asphalt", "shoulder-asphalt", "cracks-create", "save-map",
                "cracks-rollback", "paint-rollback", "road-original", "shoulder-original"])
            self.assertFalse(lane.state["outer"])
            self.assertFalse((lane.proof / saved.MANIFEST).exists())
            lane.patches[(saved.shoulder.__name__, "rollback")].assert_called_once()

    def test_outer_mode_or_missing_frozen_inventory_cannot_silently_skip_a_saved_variant(self):
        with self.saved_lane_fixture(outer_terrain=True) as lane:
            with self.assertRaisesRegex(ValueError, "explicit mode and frozen consumer"):
                saved.prepare(*lane.args, **{**lane.kwargs, "terrain_consumer_assets": None})
            self.assertEqual(lane.events, [])
            saved.prepare(*lane.args, **lane.kwargs)
            events = list(lane.events)
            with self.assertRaisesRegex(ValueError, "No authentic native saved-consumer preparation"):
                saved.reload(*lane.args, **{**lane.kwargs, "outer_terrain": False})
            self.assertEqual(lane.events, events)
            self.assertFalse((lane.proof / saved.RELOADED).exists())

    def test_outer_inventory_uses_the_correct_material_only_on_five_source_owners(self):
        original, after, receipt = self.shoulder_inventory_fixture(outer=True)

        def verify(value, selection=receipt):
            return saved.expected_saved_inventory(original, value, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE, shoulder_receipt=selection)

        verify(after)
        outer = receipt["outer_terrain"]["material"]["assets"]
        for index in (22, 185, 181):
            changed = deepcopy(after)
            row = changed["road_supports"][index + 1]
            if index == 181:
                row["slots"].append({"path": outer["instance"]})
                changed["mesh_material_collision_snapshot"][index + 1]["materials"].append(outer["instance"])
            else:
                row["slots"][1].update(path=outer["instance"], parent=outer["master"])
                changed["mesh_material_collision_snapshot"][index + 1]["materials"][1] = outer["instance"]
            with self.subTest(unselected_owner=index), self.assertRaises(ValueError):
                verify(changed)
        changed = deepcopy(after)
        changed["road_supports"][19]["slots"][1]["path"] = receipt["material"]["assets"]["instance"]
        with self.assertRaises(ValueError):
            verify(changed)

    def test_crack_saved_lane_retains_all_packages_and_fresh_reads_explicit_white_aggregate(self):
        with self.saved_lane_fixture(crack_canary=True) as lane:
            saved.prepare(*lane.args, **lane.kwargs)
            manifest = json.loads((lane.proof / saved.MANIFEST).read_text())
            prepared = json.loads((lane.proof / saved.PREPARED).read_text())
            self.assertTrue(manifest["crack_canary_enabled"])
            self.assertTrue(prepared["crack_canary_enabled"])
            self.assertEqual(len(manifest["assets"]), 22)
            crack = manifest["crack_canary"]
            self.assertTrue(crack["asset_packages_saved"])
            self.assertEqual(crack["native_no_collision"], "NO_COLLISION")
            self.assertEqual(len(crack["owned_asset_paths"]), 11)
            self.assertEqual(len(crack["actors"]), 2)
            self.assertEqual(crack["imports"]["texture_count"], 8)
            self.assertFalse(crack["normal_space_verified"])
            self.assertTrue(crack["world_normal_canary_required"])
            expected = {"Content/" + path.split(".", 1)[0].removeprefix("/Game/") + ".uasset"
                        for path in crack["owned_asset_paths"]}
            self.assertEqual({row["path"] for row in manifest["assets"] if "/CrackLayer/" in row["path"]}, expected)
            saved.verify_retained_files(lane.retained, manifest["assets"])
            saved.verified_manifest_identity(lane.proof, lane.retained)
            events = list(lane.events)
            saved.reload(*lane.args, **lane.kwargs)
            self.assertEqual(lane.events, events)
            reloaded = json.loads((lane.proof / saved.RELOADED).read_text())
            self.assertTrue(reloaded["crack_canary_fresh_reload_verified"])
            self.assertTrue(reloaded["edge_markings_fresh_reload_verified"])
            self.assertFalse(reloaded["crack_material_reapplied"])
            self.assertFalse(reloaded["crack_geometry_reapplied"])
            self.assertFalse(reloaded["crack_readback"]["normal_space_verified"])
            self.assertTrue(reloaded["crack_readback"]["world_normal_canary_required"])
            self.assertEqual(reloaded["edge_marking_readback"], lane.aggregate_white)
            self.assertEqual(reloaded["edge_marking_readback"]["aggregate_owner"], "local_crack_canary")
            lane.patches[(markings.__name__, "verify_loaded")].assert_not_called()
            lane.patches[(cracks.__name__, "create")].assert_called_once()
            lane.patches[(cracks.__name__, "verify_loaded")].assert_called_once()
            inventory = lane.patches[(saved.__name__, "expected_saved_inventory")]
            self.assertEqual(inventory.call_count, 3)
            self.assertTrue(all(call.kwargs["crack_canary_receipt"] == crack for call in inventory.call_args_list))

    def test_failed_crack_lane_rolls_back_cracks_then_white_then_original_materials(self):
        for failed_cracks, failed_paint in ((False, False), (True, False), (False, True)):
            with self.subTest(crack_cleanup_failure=failed_cracks, paint_cleanup_failure=failed_paint), \
                 self.saved_lane_fixture(crack_canary=True, fail_map=True,
                    fail_crack_cleanup=failed_cracks, fail_paint_cleanup=failed_paint) as lane:
                expected = ("fixture owned paint cleanup failed" if failed_paint else
                            "fixture owned crack cleanup failed" if failed_cracks else "map save failed")
                with self.assertRaisesRegex(ValueError, expected):
                    saved.prepare(*lane.args, **lane.kwargs)
                self.assertEqual(lane.events, ["road-asphalt", "shoulder-asphalt", "cracks-create", "save-map",
                    "cracks-rollback", "paint-rollback", "road-original", "shoulder-original"])
                self.assertFalse(lane.state["shoulder"])
                self.assertFalse(lane.state["cracks"])
                self.assertFalse((lane.proof / saved.MANIFEST).exists())
                self.assertFalse((lane.proof / saved.PREPARED).exists())
                lane.patches[(cracks.__name__, "_rollback")].assert_called_once()

    def test_failed_eleventh_crack_package_save_never_saves_map_and_cleans_once_before_white(self):
        with self.saved_lane_fixture(crack_canary=True, fail_crack_asset=True) as lane:
            with self.assertRaisesRegex(ValueError, "crack canary asset save failed"):
                saved.prepare(*lane.args, **lane.kwargs)
            self.assertEqual(lane.events, ["road-asphalt", "shoulder-asphalt", "cracks-create",
                "crack-asset-save-failed", "cracks-rollback", "paint-rollback", "road-original", "shoulder-original"])
            lane.patches[(cracks.__name__, "_rollback")].assert_called_once()
            self.assertFalse((lane.proof / saved.MANIFEST).exists())
            self.assertFalse((lane.proof / saved.PREPARED).exists())

    def test_crack_fresh_mode_cannot_silently_disable_an_existing_saved_lane(self):
        with self.saved_lane_fixture(crack_canary=True) as lane:
            saved.prepare(*lane.args, **lane.kwargs)
            events = list(lane.events)
            with self.assertRaisesRegex(ValueError, "No authentic native saved-consumer preparation"):
                saved.reload(*lane.args, **{**lane.kwargs, "crack_canary": False})
            self.assertEqual(lane.events, events)
            lane.patches[(cracks.__name__, "verify_loaded")].assert_not_called()
            self.assertFalse((lane.proof / saved.RELOADED).exists())

    def test_outer_failed_map_save_removes_paint_before_restoring_road_and_shoulders(self):
        for failed_cleanup in (False, True):
            with self.subTest(cleanup_failure=failed_cleanup), \
                 self.saved_lane_fixture(fail_map=True, fail_paint_cleanup=failed_cleanup) as lane:
                expected = "fixture owned paint cleanup failed" if failed_cleanup else "map save failed"
                with self.assertRaisesRegex(ValueError, expected):
                    saved.prepare(*lane.args, **lane.kwargs)
                self.assertEqual(lane.events, ["road-asphalt", "shoulder-asphalt", "save-map", "paint-rollback",
                                               "road-original", "shoulder-original"])
                self.assertFalse(lane.state["shoulder"])
                self.assertFalse((lane.proof / saved.MANIFEST).exists())
                self.assertFalse((lane.proof / saved.PREPARED).exists())

    def test_native_actor_tuples_equal_authentic_json_arrays_without_field_loss(self):
        # The real Unreal inventory builds actors with sorted((path, transform)
        # for actor ...), so the current process owns tuples. Persisted JSON
        # always restores arrays. Both must hash to the same exact scene bytes.
        native = deepcopy(self.old)
        native["actors"] = [
            ("/Game/Map.Map:PersistentLevel.Road", [1.0, 2.0, 3.0]),
            ("/Game/Map.Map:PersistentLevel.Support", [4.0, 5.0, 6.0]),
        ]
        retained = deepcopy(native)
        retained["actors"] = [list(row) for row in retained["actors"]]
        self.assertNotEqual(native, retained)
        self.assertEqual(
            saved.inventory_digest(native),
            saved.inventory_digest(retained),
        )
        retained["actors"][1][1][2] = 9.0
        self.assertNotEqual(
            saved.inventory_digest(native),
            saved.inventory_digest(retained),
        )

    def test_only_road_slot_zero_changes_across_derived_save(self):
        after = self.new_inventory()
        signature = saved.expected_saved_inventory(
            self.old, after, self.new_material,
            observed_map_package=saved.session.operation.MAP_PACKAGE,
        )
        self.assertEqual(len(signature), 64)
        for mutation in (
            lambda snapshot: snapshot["road_supports"][1].update(vertices=-1),
            lambda snapshot: snapshot["landscape"].update(component_count=1023),
            lambda snapshot: snapshot["mesh_material_collision_snapshot"][1][
                "materials"
            ].append("unexpected"),
        ):
            changed = deepcopy(after)
            mutation(changed)
            with self.assertRaises(ValueError):
                saved.expected_saved_inventory(
                    self.old, changed, self.new_material,
                    observed_map_package=saved.session.operation.MAP_PACKAGE,
                )

    def test_source_slot_binding_before_save_and_new_map_names_after_save(self):
        source = saved.session.operation.MAP_PACKAGE
        source_world = source + "." + source.rsplit("/", 1)[-1]
        target_world = saved.MAP + "." + saved.MAP.rsplit("/", 1)[-1]
        temporary = self.new_inventory()
        first = saved.expected_saved_inventory(
            self.old, temporary, self.new_material,
            observed_map_package=source,
        )

        def renamed(value):
            if isinstance(value, str):
                return (
                    value.replace(source_world, target_world)
                    .replace(source, saved.MAP)
                )
            if isinstance(value, list):
                return [renamed(item) for item in value]
            if isinstance(value, tuple):
                return [renamed(item) for item in value]
            if isinstance(value, dict):
                return {renamed(k): renamed(v) for k, v in value.items()}
            return value

        persisted = renamed(temporary)
        second = saved.expected_saved_inventory(
            self.old, persisted, self.new_material,
            observed_map_package=saved.MAP,
        )
        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, "approved save phase"):
            saved.expected_saved_inventory(
                self.old, temporary, self.new_material,
                observed_map_package=saved.MAP,
            )
        with self.assertRaisesRegex(ValueError, "approved save phase"):
            saved.expected_saved_inventory(
                self.old, persisted, self.new_material,
                observed_map_package="/Game/Unauthorized/Map",
            )
        altered = deepcopy(persisted)
        altered["actors"][0][1][0] = -1.0
        with self.assertRaisesRegex(ValueError, "changed geometry"):
            saved.expected_saved_inventory(
                self.old, altered, self.new_material,
                observed_map_package=saved.MAP,
            )

    def test_network_allows_only_source_owned_outer_slots_and_preserves_parapet(self):
        original, after = deepcopy(self.old), self.new_inventory()
        assets = saved.shoulder_material.asset_paths(saved.shoulder_material.DESTINATION_ROOT)
        receipt = {"schema_version": 3, "support_count": 186, "material_target_count": 185,
                   "owners": [], "material": {"assets": assets}}
        for i in range(186):
            target = i != 181
            material = (saved.shoulder_sources.SUPPORT_MATERIAL if target
                        else saved.shoulder_sources.PARAPET_MATERIAL)
            label = original["road_supports"][i + 1]["label"]
            receipt["owners"].append({"support_label": label, "material_target": target,
                "kind": "ordinary" if target else "parapet",
                "source": {"original_material_path": material}})
            for inventory in (original, after):
                inventory["road_supports"][i + 1]["slots"] = [{"path": material}]
                inventory["mesh_material_collision_snapshot"][i + 1]["materials"] = [material]
            if target:
                after["road_supports"][i + 1]["slots"].append({
                    "path": assets["instance"], "parent": assets["master"],
                    "class": "MaterialInstanceConstant", "effective_color": None})
                after["mesh_material_collision_snapshot"][i + 1]["materials"].append(assets["instance"])

        def verify(value, selection=receipt):
            return saved.expected_saved_inventory(
                original, value, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE,
                shoulder_receipt=selection,
            )

        verify(after)
        self.assertTrue(all(len(row["slots"]) == 1 for row in original["road_supports"][1:]))
        for mutate in (
            lambda value: value["road_supports"][1]["slots"][0].update(path="changed-wall"),
            lambda value: value["road_supports"][182]["slots"].append({"path": assets["instance"]}),
            lambda value: value["road_supports"][186]["slots"].pop(),
            lambda value: value["mesh_material_collision_snapshot"][1].update(collision="BLOCK_ALL"),
            lambda value: value["landscape"].update(component_count=1023),
        ):
            value = deepcopy(after)
            mutate(value)
            with self.assertRaises(ValueError):
                verify(value)
        for mutate in (
            lambda value: value["owners"].pop(),
            lambda value: value["owners"][1].update(support_label=value["owners"][0]["support_label"]),
            lambda value: value["owners"][181].update(material_target=True),
            lambda value: value["material"]["assets"].update(instance="/Game/Unapproved/MI.MI"),
        ):
            value = deepcopy(receipt)
            mutate(value)
            with self.assertRaises(ValueError):
                verify(after, value)

    def test_fresh_road_full_buffers_reject_geometry_corner_or_id_drift(self):
        summary = {"vertex_count": 856250, "triangle_count": 1711760,
                   "uv_set_count": 0, "positions_indices_blake3": "a" * 64,
                   "triangle_corner_normals_uv_blake3": "b" * 64,
                   "material_ids_blake3": "c" * 64}
        component = object()
        road = SimpleNamespace(get_dynamic_mesh_component=lambda: component)
        api = SimpleNamespace(EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(get_all_level_actors=lambda: [road]))
        with patch.object(saved.baseline, "road_support_actors", return_value=[road]), \
             patch.object(saved.shoulder, "inspect_mesh", return_value={"summary": summary}) as read:
            self.assertEqual(saved.verify_road_mesh(api, summary), summary)
            read.assert_called_once_with(api, component)
            for field in ("positions_indices_blake3", "triangle_corner_normals_uv_blake3", "material_ids_blake3"):
                changed = {**summary, field: "d" * 64}
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "full native buffers"):
                    saved.verify_road_mesh(api, changed)

    def test_downloadable_manifest_must_match_retained_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            proof, retained = Path(directory) / "proof", Path(directory) / "retained"
            proof.mkdir()
            retained.mkdir()
            value = {"shoulder_network": {"selected_triangle_ids": [0, 1, 50, 51]}}
            expected = saved.write_once(retained / saved.MANIFEST, value)
            saved.write_once(proof / saved.MANIFEST, value)
            self.assertEqual(saved.verified_manifest_identity(proof, retained), expected)
            (proof / saved.MANIFEST).write_bytes((proof / saved.MANIFEST).read_bytes().replace(b"50", b"52"))
            with self.assertRaisesRegex(ValueError, "Downloadable material manifest differs"):
                saved.verified_manifest_identity(proof, retained)

    def test_profile_diagnostic_is_retained_once_and_both_copies_remain_byte_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            proof, retained = Path(directory) / "proof", Path(directory) / "retained"
            proof.mkdir()
            retained.mkdir()
            plan = object()
            report = {"synthetic_file_contract_fixture": True, "values": [0, 1, 2]}
            with patch.object(saved.shoulder_sources, "network_profile_report", return_value=report) as read:
                identity = saved.write_profile_diagnostic(proof, retained, plan)
                read.assert_called_once_with(plan)
                with self.assertRaises(FileExistsError):
                    saved.write_profile_diagnostic(proof, retained, plan)
            self.assertEqual(identity["file"], saved.PROFILE_DIAGNOSTIC)
            original = (proof / saved.PROFILE_DIAGNOSTIC).read_bytes()
            self.assertEqual(json.loads(original), report)
            self.assertEqual(identity["sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(identity["size_bytes"], len(original))
            for folder in (proof, retained):
                path = folder / saved.PROFILE_DIAGNOSTIC
                path.write_bytes(original.replace(b"[0,1,2]", b"[0,1,3]"))
                with self.assertRaisesRegex(ValueError, "diagnostic bytes changed"):
                    saved.verified_profile_identity(proof, retained, identity)
                path.write_bytes(original)
            for changed in (
                {**identity, "file": "../another.json"},
                {**identity, "size_bytes": saved.shoulder_sources.PROFILE_REPORT_MAX_BYTES + 1},
                {**identity, "size_bytes": True},
                {**identity, "sha256": "unverified"},
                {**identity, "extra": 1},
            ):
                with self.assertRaisesRegex(ValueError, "fixed file/byte contract"):
                    saved.verified_profile_identity(proof, retained, changed)
            self.assertEqual(saved.verified_profile_identity(proof, retained, identity), identity)

    def test_editor_dispatch_keeps_source_dependency_role_separate_from_scene_assets(self):
        # Real staging has 14 scene rows and 236 unique dependency rows, with
        # ten valid paths shared across those roles. Only the dependency list
        # belongs to the material validator; the union still guards all files.
        dependencies = list(saved.shoulder_material.SOURCE_PINS.values())
        consumer = [dependencies[0]]
        stage = {"consumer_assets": consumer, "source_dependencies": dependencies}
        rows = consumer + dependencies
        saved.shoulder_material.source_rows(dependencies)
        with self.assertRaisesRegex(ValueError, "duplicate source dependency"):
            saved.shoulder_material.source_rows(rows)
        api = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(saved.ROOT),
                convert_relative_path_to_full=lambda value: value),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: "5.8.2-56702186+++UE5+Release-5.8",
                quit_editor=Mock()),
        )
        trial = {"result": {"graph_sha256": saved.asphalt_source.GRAPH_SHA256,
                            "source_receipt_sha256": saved.asphalt_source.SOURCE_RECEIPT_SHA256}}
        original, identity = {"native_inventory": {}}, {"sha256": "a" * 64, "size_bytes": 100}
        for action, mode, cracks_mode in (("prepare", "0", "0"), ("reload", "0", "0"),
                ("prepare", "1", "0"), ("reload", "1", "0"), ("prepare", "1", "1"), ("reload", "1", "1")):
            with self.subTest(action=action, edge_markings=mode, crack_canary=cracks_mode), \
                 patch.dict("os.environ", {"YACS_ROAD_SAVED_ACTION": action, "YACS_ROAD_EDGE_MARKINGS": mode,
                                           "YACS_ROAD_CRACK_CANARY": cracks_mode}), \
                 patch.dict("sys.modules", {"unreal": api}), \
                 patch.object(saved.session, "_assert_isolated_root"), \
                 patch.object(saved, "proof_paths", return_value=("b" * 40, "a" * 64, "1-1", Path("proof"), Path("retained"))), \
                 patch.object(saved, "verified_staging", return_value=(Path("stage"), identity, stage, {}, rows)), \
                 patch.object(saved, "verified_predecessors", return_value=(original, trial)), \
                 patch.object(saved.baseline, "dirty_packages"), \
                 patch.object(saved.prep, "assert_isolated_bootstrap"), \
                 patch.object(saved.session, "_verify_rows") as verify_files, \
                 patch.object(saved.session, "_identity", return_value=identity), \
                 patch.object(saved, action) as dispatch:
                saved.main()
                self.assertIs(dispatch.call_args.kwargs["source_dependencies"], dependencies)
                self.assertIs(dispatch.call_args.kwargs["edge_markings"], mode == "1")
                self.assertIs(dispatch.call_args.kwargs["crack_canary"], cracks_mode == "1")
                self.assertIs(dispatch.call_args.args[-1], rows)
                verify_files.assert_called_once_with(saved.ROOT, rows)

    def test_savemap_may_keep_original_world_until_fresh_editor_reload(self):
        def mock_editor(package):
            world = SimpleNamespace(
                get_path_name=lambda: package + "." + package.rsplit("/", 1)[-1]
            )
            system = SimpleNamespace(get_editor_world=lambda: world)
            return SimpleNamespace(
                UnrealEditorSubsystem=object(),
                get_editor_subsystem=lambda cls: system,
            )

        source = saved.session.operation.MAP_PACKAGE
        for package in (source, saved.MAP):
            with self.subTest(package=package):
                self.assertEqual(
                    saved.active_map_after_save(mock_editor(package)), package
                )
                stage = self.new_inventory()
                stage["map_package"] = package
                if package == saved.MAP:
                    # The other test verifies exact actor path rebasing
                    # rather than weakening the complete scene equality.
                    self.assertNotEqual(stage["map_package"], self.old["map_package"])
        with self.assertRaisesRegex(ValueError, "unapproved map"):
            saved.active_map_after_save(mock_editor("/Game/Unapproved/L_Other"))

    def test_world_identity_normalizes_but_materials_are_not_aliases(self):
        before = saved.session.operation.MAP_PACKAGE
        after = saved.MAP
        for old, new in (
            (before + "." + before.rsplit("/", 1)[-1], after + "." + after.rsplit("/", 1)[-1]),
            (before + ".L", after + ".L"),
        ):
            self.assertEqual(
                saved.normalized(old + ":PersistentLevel.Actor", before),
                saved.normalized(new + ":PersistentLevel.Actor", after),
            )
        original = {"material": "/Game/Textures/Test.T_Test"}
        self.assertEqual(saved.normalized(original, before), original)
        self.assertEqual(saved.normalized(original, after), original)

    def test_durable_manifest_copies_are_byte_pinned_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            retained = Path(directory) / "retained"
            rows = []
            for index in range(7):
                relative = (
                    saved.MAP_FILE
                    if index == 0
                    else saved.PREFIX + f"test/T_{index:02d}.uasset"
                )
                data = f"SYNTHETIC SAVED MATERIAL ASSET {index}".encode()
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                rows.append({
                    "path": relative,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
            with patch.object(saved, "ROOT", root):
                delivered = saved.retain_files(retained, rows)
                self.assertEqual(len(delivered), 7)
                saved.verify_retained_files(retained, delivered)
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    saved.retain_files(retained, rows)
                (retained / delivered[-1]["storage"]).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "differs"):
                    saved.verify_retained_files(retained, delivered)

    def test_generated_package_tree_audits_directories_and_all_seven_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / saved.PREFIX
            expected_paths = [saved.MAP_FILE] + [
                saved.PREFIX + f"aged_mountain_asphalt/dry_varied/abcdef/T_{i}.uasset"
                for i in range(6)
            ]
            for i, relative in enumerate(expected_paths):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"native-package-{i}".encode("utf-8"))
            with patch.object(saved, "ROOT", root):
                rows = saved.produced_files()
                self.assertEqual(
                    [row["path"] for row in rows], sorted(expected_paths)
                )
                self.assertEqual(len(rows), 7)
                # Exercise real Windows path-comparison semantics even when
                # this contract runs on Linux. Byte/path auditing still uses
                # the actual disposable package files through _safe_path.
                class WindowsFixturePath(PureWindowsPath):
                    def relative_to(self, other):
                        # Python 3.14 no longer coerces a Path of another
                        # flavour. Use a Windows root for this Windows view;
                        # native filesystem auditing retains the real ROOT.
                        return super().relative_to(PureWindowsPath(str(other)))

                windows_paths = [WindowsFixturePath(str(path)) for path in folder.rglob("*")]
                with patch.object(Path, "rglob", return_value=iter(windows_paths)):
                    windows_rows = saved.produced_files()
                self.assertEqual(windows_rows, rows)
                extra = folder / "aged_mountain_asphalt/dry_varied/abcdef/UNAPPROVED.txt"
                extra.write_text("not a package", encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, "Unapproved generated road-material file type"
                ):
                    saved.produced_files()
                extra.unlink()
                # Never silently accept an asset file with a real path alias.
                alias = folder / "aged_mountain_asphalt/dry_varied/abcdef/ALIAS.uasset"
                try:
                    alias.symlink_to(root / expected_paths[1])
                except (OSError, NotImplementedError):
                    pass  # Symlink privilege may be unavailable on Windows.
                else:
                    with self.assertRaisesRegex(ValueError, "reparse|symlink"):
                        saved.produced_files()

    def test_schema_and_packages_are_fixed_to_new_separate_namespace(self):
        self.assertEqual(
            saved.MAP_FILE,
            "Content/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.umap",
        )
        self.assertNotEqual(saved.MAP, saved.session.operation.MAP_PACKAGE)
        self.assertTrue(saved.MAP.startswith(saved.PACKAGE + "/"))
        self.assertTrue(saved.PREFIX.startswith("Content/Generated/YACS/"))
        self.assertNotIn("Worlds/SaCalobra", saved.MAP)
        self.assertEqual(saved.TEXTURES["NormalTex"], "Normal_DX")
        self.assertEqual(saved.MAX_ASSET_COUNT, 64)


if __name__ == "__main__":
    unittest.main()
