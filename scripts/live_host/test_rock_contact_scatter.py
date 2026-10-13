"""CPU-only tests for Remote rock preview guards; no native/GPU execution."""

from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.live_host.recipes import rock_contact_scatter as m


def vector(x=0, y=0, z=0):
    return SimpleNamespace(x=x, y=y, z=z)


class Hit:
    def __init__(self, owner, component, blocking=True):
        self.fields = [None] * 18
        self.fields[0:4] = [blocking, False, 0.5, 10.0]
        self.fields[5], self.fields[7] = vector(0, 0, 1), vector(0, 0, 1)
        self.fields[9], self.fields[10] = owner, component

    def to_tuple(self):
        return tuple(self.fields)


class FakeMeshDelegate:
    def __init__(self):
        self.callbacks = []

    def add_callable(self, callback):
        self.callbacks.append(callback)

    def remove_callable(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def contains_callable(self, callback):
        return callback in self.callbacks

    def emit(self, mesh):
        for callback in list(self.callbacks):
            callback(mesh)


class RockRemoteGuards(unittest.TestCase):
    def test_transform_snapshot_ignores_struct_address_but_detects_all_values(self):
        def native_copy():
            return SimpleNamespace(
                translation=vector(10, 20, 30),
                rotation=SimpleNamespace(x=0, y=0, z=0, w=1),
                scale3d=vector(1, 2, 3),
            )

        class AddressedStruct:
            def __init__(self):
                self.__dict__.update(native_copy().__dict__)

        first, second = AddressedStruct(), AddressedStruct()
        self.assertNotEqual(str(first), str(second))
        baseline = m.transform_snapshot(first)
        self.assertEqual(baseline, m.transform_snapshot(second))
        for part, key in (("translation", "z"), ("rotation", "w"), ("scale3d", "x")):
            altered = native_copy()
            target = getattr(altered, part)
            setattr(target, key, getattr(target, key) + 0.125)
            self.assertNotEqual(baseline, m.transform_snapshot(altered))
        invalid = native_copy()
        invalid.rotation.w = float("nan")
        with self.assertRaises(ValueError):
            m.transform_snapshot(invalid)

    def test_full_radius_with_fixed_clearance(self):
        xy = [181600, 189600]
        result = m.footprint_clearance_sample(xy, 100, 1.5, 0)
        self.assertEqual(
            result["status"], "PASS_AUTHENTICATED_FULL_RADIUS_EXCLUSIONS_ONLY"
        )
        self.assertFalse(result["regional_rock_domain_admitted"])
        for args in (
            (xy, 100, 1.499, 0),
            (xy, 100, float("nan"), 0),
            (xy, 100, 100, 128),
            (xy, 100, 100, 1),
            ([201600, 200000], 100, 100, 0),
            (xy, -1, 100, 0),
        ):
            with self.assertRaises(ValueError):
                m.footprint_clearance_sample(*args)

    def test_all_exclusion_classes_reject(self):
        for bit in (1, 2, 4, 8, 16, 32, 64, 128):
            with self.assertRaises(ValueError):
                m.footprint_clearance_sample([181600, 189600], 100, 100, bit)

    def test_subcell_offset_consumes_clearance(self):
        with self.assertRaises(ValueError):
            m.footprint_clearance_sample([181601, 189600], 100, 1.5, 0)

    def test_native_hit_ownership_overlap_time_distance(self):
        actor, comp = object(), object()
        hit = Hit(actor, comp)
        self.assertEqual(m.unpack(hit, actor, comp)["position"], [0.0, 0.0, 1.0])
        self.assertIsNone(m.unpack(None, actor))
        for field, value in (
            (1, True),
            (2, float("nan")),
            (2, 1.1),
            (3, -1),
            (9, object()),
            (10, object()),
        ):
            invalid = Hit(actor, comp)
            invalid.fields[field] = value
            with self.assertRaises(ValueError):
                m.unpack(invalid, actor, comp)
        with self.assertRaises(ValueError):
            m.unpack(Hit(actor, comp, False), actor)
        # Native component traces may legitimately be nonblocking.
        self.assertIsNotNone(m.unpack(Hit(actor, comp, False), actor, comp))

    def test_proof_rejects_traversal_symlink_and_byte_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "one.bin"
            path.write_bytes(b"source")
            proof = {"path": "one.bin", "bytes": 6, "sha256": m.digest(path)}
            self.assertEqual(m.file_proof(root, proof), path)
            for name in (
                "../one.bin",
                "/one.bin",
                "one\\bin",
                "D:/one.bin",
                "./one.bin",
            ):
                with self.assertRaises(ValueError):
                    m.file_proof(root, {**proof, "path": name})
            path.write_bytes(b"drift!")
            with self.assertRaises(ValueError):
                m.file_proof(root, proof)

    def test_logical_buffer_index_and_radius_without_rasterio(self):
        bounds = {"origin": [0, 0, 1], "extent": [1, 1, 1]}
        data = {
            "assets": [{"id": "rock", "bounds_cm": bounds}],
            "placements": [
                {"site": "P0", "asset_id": "rock", "world_xy_cm": [100, 100]}
            ],
        }
        offset = 2 * 4033 + 2
        distances = bytearray((offset + 1) * 4)
        reasons = bytearray((offset + 1) * 2)
        struct.pack_into("<f", distances, offset * 4, 2.0)
        with patch.object(
            m, "authenticated_exclusion_buffers", return_value=[distances, reasons]
        ):
            self.assertIn("P0", m.verify_footprints(data))
            struct.pack_into("<H", reasons, offset * 2, 128)
            with self.assertRaises(ValueError):
                m.verify_footprints(data)

    def context(self, actors):
        package = "/Game/Test"
        live = SimpleNamespace(
            world=SimpleNamespace(get_path_name=lambda: package + ".Test"),
            map_package=package,
            _pcg365_remote_actors=actors,
        )
        return {"live": live, "intent": "preview", "asset_scope": ()}

    def test_clear_works_with_absent_stale_manifest_and_retains_failures(self):
        a, b = object(), object()
        context = self.context([a, b])
        destroyed = []

        def destroy(actor):
            destroyed.append(actor)
            return actor is a

        editor = SimpleNamespace(destroy_actor=destroy)
        api = SimpleNamespace(
            EditorActorSubsystem=object(), get_editor_subsystem=lambda _: editor
        )
        with patch.object(
            m, "read_manifest", side_effect=AssertionError("must not read")
        ):
            with self.assertRaises(ValueError):
                m.run(api, context, {"operation": "clear", "manifest_sha256": "stale"})
        self.assertEqual(context["live"]._pcg365_remote_actors, [b])
        editor.destroy_actor = lambda _: True
        result = m.run(api, context, {"operation": "clear", "manifest_sha256": "stale"})
        self.assertEqual(result["cleared"], 1)
        self.assertFalse(result["map_saved"])
        self.assertEqual(context["live"]._pcg365_remote_actors, [])

    def test_wrong_intent_and_scope_reject_without_native_api(self):
        context = self.context([])
        for field, value in (
            ("intent", "authoring"),
            ("asset_scope", ("/Game/Other",)),
        ):
            invalid = {**context, field: value}
            with self.assertRaises(ValueError):
                m.run(None, invalid, {"operation": "clear", "manifest_sha256": "stale"})


class IncrementalContact(unittest.TestCase):
    def setup_job(self):
        class Landscape:
            def get_actor_transform(self):
                return SimpleNamespace(
                    translation=vector(),
                    scale3d=vector(50, 50, 1),
                    rotation=SimpleNamespace(
                        x=0,
                        y=0,
                        z=0,
                        w=1,
                        rotator=lambda: SimpleNamespace(pitch=0, yaw=0, roll=0),
                    ),
                )

        ground = Landscape()
        world = SimpleNamespace(get_path_name=lambda: "/Game/Test.Test")
        live = SimpleNamespace(world=world, map_package="/Game/Test")
        editor = SimpleNamespace(
            get_all_level_actors=lambda: [ground], destroy_actor=lambda _: True
        )
        callbacks = {}
        api = SimpleNamespace(
            LandscapeProxy=Landscape,
            EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: editor,
            register_slate_post_tick_callback=lambda fn: (
                callbacks.setdefault("callback", fn) or 7
            ),
            unregister_slate_post_tick_callback=lambda h: callbacks.update(
                unregistered=True
            ),
        )
        context = {
            "live": live,
            "_pcg365_manifest_sha256": "a" * 64,
            "request_id": "request",
        }
        data = {
            "placements": [{"site": "P0"}],
            "assets": [],
            "map_package": "/Game/Test",
        }
        result = {
            "status": "APPLIED_PREVIEW",
            "map_saved": False,
            "preview_placed": 0,
            "cases": [],
            "production_admitted": False,
            "qualified_assets": [],
            "performance_pass": False,
        }
        result["_native_bounds"] = {}
        expected = patch.object(
            m, "native_expected_geometry_labels", return_value=frozenset()
        )
        expected.start()
        self.addCleanup(expected.stop)
        return api, context, data, result, callbacks

    def test_initial_ack_has_no_contact_pass_and_each_tick_is_bounded(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            job = args[-1]
            for i in range(130):
                yield {"grid": 65}
            job["operation_status"] = "CONTACT_JOB_COMPLETED_SAMPLED_ONLY"

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", return_value=0.0),
        ):
            ack = m.start_contact_job(api, context, data, {}, {}, result, None, None)
            self.assertEqual(ack["sampled_positions"], 0)
            self.assertEqual(ack["operation_status"], "CONTACT_JOB_RUNNING")
            self.assertEqual(ack["qualified_assets"], [])
            self.assertEqual(ack["maximum_grid_positions"], 65 * 65 + 129 * 129)
            callbacks["callback"](0)
            self.assertEqual(m.public_job(context["live"])["sampled_positions"], 64)
            callbacks["callback"](0)
            self.assertEqual(m.public_job(context["live"])["sampled_positions"], 128)
            callbacks["callback"](0)
            self.assertEqual(
                m.public_job(context["live"])["operation_status"],
                "CONTACT_JOB_COMPLETED_SAMPLED_ONLY",
            )
            self.assertTrue(callbacks["unregistered"])

    def test_native_geometry_has_separate_bounded_budget(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            for _ in range(1300):
                yield {"grid": None, "native_triangle_id": True}

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", return_value=0),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            callbacks["callback"](0)
            job = context["live"]._pcg365_remote_job
            self.assertEqual(job["native_geometry_triangle_ids_read"], 1024)
            self.assertEqual(job["sampled_positions"], 0)
            callbacks["callback"](0)
            self.assertEqual(job["native_geometry_triangle_ids_read"], 1300)

    def test_native_pumped_slate_cannot_reenter_contact_generator(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            callbacks["callback"](0)
            yield {"grid": 65}

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", return_value=0),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            callbacks["callback"](0)
            job = context["live"]._pcg365_remote_job
            self.assertEqual(job["sampled_positions"], 1)
            self.assertNotIn("error", job)
            self.assertFalse(job["_advancing"])

    def test_nested_clear_waits_until_native_generator_yields(self):
        api, context, data, result, callbacks = self.setup_job()
        context.update(intent="preview", asset_scope=())
        owned = object()
        observed = []

        def steps(*args):
            context["live"]._pcg365_remote_actors.append(owned)
            reply = m.run(
                api, context, {"operation": "clear", "manifest_sha256": "stale"}
            )
            observed.append(reply["operation_status"])
            self.assertEqual(context["live"]._pcg365_remote_actors, [owned])
            yield {"grid": 65}
            self.fail("Cancelled generator must not resume")

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", return_value=0),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            callbacks["callback"](0)
            job = context["live"]._pcg365_remote_job
            self.assertEqual(observed, ["CONTACT_JOB_CANCEL_REQUESTED_DEFERRED"])
            self.assertEqual(
                job["operation_status"], "CONTACT_JOB_CANCELLED_ROLLED_BACK"
            )
            self.assertTrue(job["rollback_complete"])
            self.assertEqual(context["live"]._pcg365_remote_actors, [])
            self.assertFalse(job["_advancing"])

    def test_wall_budget_yields_early_without_dropping_positions(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            for _ in range(130):
                yield {"grid": 129}

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", side_effect=[0.0, 0.009]),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            callbacks["callback"](0)
            self.assertEqual(m.public_job(context["live"])["sampled_positions"], 1)

    def test_async_failure_rolls_back_unregisters_and_keeps_status(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            context["live"]._pcg365_remote_actors.append(object())
            yield {"grid": 65}
            raise ValueError("Wrong ground owner")

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "validate_job_world"),
            patch.object(m.time, "perf_counter", return_value=0.0),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            callbacks["callback"](0)
            status = m.public_job(context["live"])
            self.assertEqual(
                status["operation_status"], "CONTACT_JOB_FAILED_ROLLED_BACK"
            )
            self.assertTrue(status["rollback_complete"])
            self.assertEqual(context["live"]._pcg365_remote_actors, [])
            self.assertTrue(callbacks["unregistered"])
            self.assertIn("Wrong ground owner", status["error"])

    def test_unregister_error_does_not_skip_actor_rollback(self):
        api, context, data, result, callbacks = self.setup_job()

        def steps(*args):
            while True:
                yield {"grid": 65}

        def fail_unregister(handle):
            raise RuntimeError("native callback cleanup unavailable")

        with patch.object(m, "planting_steps", side_effect=steps):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            context["live"]._pcg365_remote_actors.append(object())
            api.unregister_slate_post_tick_callback = fail_unregister
            job = context["live"]._pcg365_remote_job
            m.rollback_job(
                api,
                context["live"],
                api.get_editor_subsystem(None),
                job,
                "CONTACT_JOB_CANCELLED_ROLLED_BACK",
            )
            self.assertEqual(context["live"]._pcg365_remote_actors, [])
            self.assertEqual(job["operation_status"], "CONTACT_JOB_ROLLBACK_INCOMPLETE")
            before = job["sampled_positions"]
            callbacks["callback"](0)
            self.assertEqual(job["sampled_positions"], before)
            self.assertFalse(job["tick_unregistered"])

    def test_cancel_running_job_does_not_read_stale_manifest(self):
        api, context, data, result, callbacks = self.setup_job()
        context.update(intent="preview", asset_scope=())

        def steps(*args):
            while True:
                yield {"grid": 65}

        with (
            patch.object(m, "planting_steps", side_effect=steps),
            patch.object(m, "read_manifest", side_effect=AssertionError),
        ):
            m.start_contact_job(api, context, data, {}, {}, result, None, None)
            status = m.run(
                api, context, {"operation": "clear", "manifest_sha256": "stale"}
            )
            self.assertEqual(
                status["operation_status"], "CONTACT_JOB_CANCELLED_ROLLED_BACK"
            )
            self.assertTrue(status["rollback_complete"])
            self.assertTrue(callbacks["unregistered"])

    def test_synchronous_native_guard_failure_returns_status_and_preserves_clear(self):
        api, context, data, result, callbacks = self.setup_job()
        context.update(intent="preview", asset_scope=())
        with (
            patch.object(m, "read_manifest", return_value=data),
            patch.object(m, "verify_footprints", return_value={}),
            patch.object(m, "load_helpers", return_value=(None, None)),
            patch.object(m, "load_materials", return_value={}),
            patch.object(
                m,
                "start_contact_job",
                side_effect=AttributeError("native guard API unavailable"),
            ),
        ):
            failed = m.run(
                api, context, {"operation": "plant", "manifest_sha256": "a" * 64}
            )
        self.assertEqual(failed["operation_status"], "FAILED_NATIVE_GUARD_NO_PLACEMENT")
        self.assertFalse(failed["native_contact_executed"])
        self.assertEqual(failed["preview_placed"], 0)
        self.assertEqual(
            m.run(api, context, {"operation": "status", "manifest_sha256": "stale"})[
                "operation_status"
            ],
            "FAILED_NATIVE_GUARD_NO_PLACEMENT",
        )
        self.assertEqual(
            m.run(api, context, {"operation": "clear", "manifest_sha256": "stale"})[
                "preview_placed"
            ],
            0,
        )

    def test_preflight_rejection_returns_without_poisoning_receiver(self):
        api, context, data, result, callbacks = self.setup_job()
        context.update(intent="preview", asset_scope=())
        with (
            patch.object(
                m, "read_manifest", side_effect=ValueError("Native road parity missing")
            ),
            patch.object(
                m, "load_helpers", side_effect=AssertionError("must not load")
            ),
        ):
            status = m.run(
                api, context, {"operation": "plant", "manifest_sha256": "stale"}
            )
        self.assertEqual(
            status["operation_status"], "REJECTED_PRECHECK_NO_SCENE_MUTATION"
        )
        self.assertFalse(status["native_contact_executed"])
        self.assertFalse(status["map_saved"])


class NativeRoadExclusion(unittest.TestCase):
    def test_triangle_square_crossing_containment_edges_and_vertical_faces(self):
        overlap = m.triangle_square_overlap
        center = [0, 0]
        self.assertTrue(
            overlap([[-10, -0.5, 0], [10, -0.5, 0], [10, 0.5, 0]], center, 1)
        )
        self.assertTrue(overlap([[-10, -10, 0], [10, -10, 0], [0, 20, 0]], center, 1))
        self.assertTrue(overlap([[1, -10, 0], [1, 10, 0], [1, 10, 50]], center, 1))
        self.assertTrue(overlap([[0, 0, 0], [0, 0, 1], [0, 0, 2]], center, 1))
        self.assertFalse(overlap([[2, -10, 0], [2, 10, 0], [2, 10, 50]], center, 1))
        self.assertFalse(overlap([[2, 0, 0], [0, 2, 0], [2, 2, 0]], center, 0.9))
        with self.assertRaises(ValueError):
            overlap([[float("nan"), 0, 0], [1, 0, 0], [1, 1, 0]], center, 1)

    def fixture(self):
        class Transform:
            def __init__(self, offset=(0, 0, 0)):
                self.offset = offset
                self.rotation = SimpleNamespace(x=0, y=0, z=0, w=1)
                self.scale3d = vector(1, 1, 1)

            @property
            def translation(self):
                return vector(*self.offset)

            def __str__(self):
                return "Transform" + str(id(self)) + str(self.offset)

        class Mesh:
            positions = [(1000, 1000, 0), (1010, 1000, 0), (1000, 1010, 0)]

            def get_editor_property(self, name):
                if name != "mesh_modified_bp_event":
                    raise AttributeError(name)
                if not hasattr(self, "delegate"):
                    self.delegate = FakeMeshDelegate()
                return self.delegate

            def get_triangle_count(self):
                return 1

            def get_num_triangle_ids(self):
                return 1

            def get_path_name(self):
                return "/Game/Test.Mesh"

            def get_triangle_positions(self, tid):
                return (True, *(vector(*p) for p in self.positions))

        class Component:
            def __init__(self, label):
                self.label = label
                self.mesh = Mesh()
                self.transform = Transform()

            def get_dynamic_mesh(self):
                return self.mesh

            def get_path_name(self):
                return "/Game/Test." + self.label + ".Component"

            def get_world_transform(self):
                return self.transform

        class Actor:
            def __init__(self, label):
                self.label = label
                self.component = Component(label)

            def get_actor_label(self):
                return self.label

            def get_path_name(self):
                return "/Game/Test." + self.label

            def get_actor_transform(self):
                return self.component.transform

            def get_dynamic_mesh_component(self):
                return self.component

        labels = ["YACS_PERSIST_ROAD"] + [
            f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(186)
        ]
        labels += [f"CONTEXT_{i:03d}" for i in range(372)]
        actors = [Actor(label) for label in labels]

        def transform_location(t, p):
            return vector(p.x + t.offset[0], p.y + t.offset[1], p.z + t.offset[2])

        api = SimpleNamespace(
            DynamicMeshActor=Actor,
            Actor=object,
            Vector=vector,
            GameplayStatics=SimpleNamespace(get_all_actors_of_class=lambda *_: actors),
            MathLibrary=SimpleNamespace(transform_location=transform_location),
        )
        data = {
            "assets": [{"id": "rock"}],
            "placements": [{"site": "P0", "asset_id": "rock", "world_xy_cm": [0, 0]}],
            "_expected_labels": frozenset(labels),
        }
        bounds = {"rock": {"origin": [0, 0, 1], "extent": [1, 1, 1]}}
        return api, actors, data, bounds

    def consume(self, generator):
        updates = []
        while True:
            try:
                updates.append(next(generator))
            except StopIteration as done:
                return updates, done.value

    def test_complete_native_inventory_snapshot_recheck_and_crossing_rejection(self):
        api, actors, data, bounds = self.fixture()
        updates, (snapshot, decisions) = self.consume(
            m.native_road_exclusion_steps(
                api,
                None,
                data,
                bounds,
                {"_expected_native_labels": data["_expected_labels"]},
            )
        )
        self.assertEqual(len(updates), 559)
        self.assertEqual(len(snapshot), 559)
        self.assertEqual(
            decisions["P0"]["status"], "PASS_CURRENT_NATIVE_TRIANGLE_EXCLUSION"
        )
        self.consume(
            m.native_road_exclusion_steps(
                api,
                None,
                data,
                bounds,
                {"_expected_native_labels": data["_expected_labels"]},
                previous=snapshot,
            )
        )
        actors[0].component.mesh.positions = [(-100, 0, 0), (100, 0, 0), (100, 1, 0)]
        with self.assertRaisesRegex(ValueError, "positions changed"):
            self.consume(
                m.native_road_exclusion_steps(
                    api,
                    None,
                    data,
                    bounds,
                    {"_expected_native_labels": data["_expected_labels"]},
                    previous=snapshot,
                )
            )
        _, (_, decisions) = self.consume(
            m.native_road_exclusion_steps(
                api,
                None,
                data,
                bounds,
                {"_expected_native_labels": data["_expected_labels"]},
            )
        )
        self.assertEqual(
            decisions["P0"]["status"], "REJECTED_CURRENT_NATIVE_TRIANGLE_OVERLAP"
        )

    def test_nonidentity_component_transforms_geometry_to_world(self):
        api, actors, data, bounds = self.fixture()
        actors[0].component.transform.offset = (-1000, -1000, 0)
        _, (_, decisions) = self.consume(
            m.native_road_exclusion_steps(
                api,
                None,
                data,
                bounds,
                {"_expected_native_labels": data["_expected_labels"]},
            )
        )
        self.assertEqual(
            decisions["P0"]["status"], "REJECTED_CURRENT_NATIVE_TRIANGLE_OVERLAP"
        )
        self.assertEqual(decisions["P0"]["witness_world_triangle_cm"][0], [0, 0, 0])

    def test_missing_duplicate_and_changed_transform_fail_closed(self):
        api, actors, data, bounds = self.fixture()
        actors.pop()
        with self.assertRaises(ValueError):
            m.native_geometry_inventory(api, None, data["_expected_labels"])
        api, actors, data, bounds = self.fixture()
        actors[-1].label = actors[0].label
        with self.assertRaises(ValueError):
            m.native_geometry_inventory(api, None, data["_expected_labels"])
        api, actors, data, bounds = self.fixture()
        _, (snapshot, _) = self.consume(
            m.native_road_exclusion_steps(
                api,
                None,
                data,
                bounds,
                {"_expected_native_labels": data["_expected_labels"]},
            )
        )
        actors[0].component.transform.offset = (0, 1, 0)
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.consume(
                m.native_road_exclusion_steps(
                    api,
                    None,
                    data,
                    bounds,
                    {"_expected_native_labels": data["_expected_labels"]},
                    previous=snapshot,
                )
            )

    def test_unknown_context_label_and_foreign_actor_class_reject(self):
        api, actors, data, bounds = self.fixture()
        actors[-1].label = "UNKNOWN_REPLACEMENT"
        with self.assertRaisesRegex(ValueError, "unknown"):
            m.native_geometry_inventory(api, None, data["_expected_labels"])
        api, actors, data, bounds = self.fixture()
        foreign = SimpleNamespace(get_actor_label=lambda: "YACS_PERSIST_ROAD")
        api.GameplayStatics.get_all_actors_of_class = lambda world, cls: (
            actors if cls is api.DynamicMeshActor else actors + [foreign]
        )
        with self.assertRaisesRegex(ValueError, "actor class"):
            m.native_geometry_inventory(api, None, data["_expected_labels"])

    def guarded_job(self, api, data):
        job = {
            "_expected_native_labels": data["_expected_labels"],
            "operation_status": "CONTACT_JOB_RUNNING",
        }
        self.consume(m.bind_native_mesh_guards_steps(api, None, job))
        self.addCleanup(m.cleanup_native_mesh_guards, job)
        return job

    def test_late_transform_change_after_earlier_final_scan_actor_rejects(self):
        api, actors, data, bounds = self.fixture()
        job = self.guarded_job(api, data)
        _, (snapshot, _) = self.consume(
            m.native_road_exclusion_steps(api, None, data, bounds, job)
        )
        final = m.native_road_exclusion_steps(
            api, None, data, bounds, job, previous=snapshot
        )
        next(final)
        next(final)
        earlier = next(a for a in actors if a.label == "CONTEXT_000")
        earlier.component.transform.offset = (-1000, -1000, 0)
        with self.assertRaisesRegex(ValueError, "Previously scanned"):
            self.consume(final)

    def test_late_same_count_vertex_edit_event_rejects_final_scan(self):
        api, actors, data, bounds = self.fixture()
        job = self.guarded_job(api, data)
        _, (snapshot, _) = self.consume(
            m.native_road_exclusion_steps(api, None, data, bounds, job)
        )
        final = m.native_road_exclusion_steps(
            api, None, data, bounds, job, previous=snapshot
        )
        next(final)
        next(final)
        earlier = next(a for a in actors if a.label == "CONTEXT_000")
        mesh = earlier.component.mesh
        mesh.positions = [(-100, 0, 0), (100, 0, 0), (100, 1, 0)]
        mesh.get_editor_property("mesh_modified_bp_event").emit(mesh)
        self.assertTrue(job["native_mesh_dirty"])
        with self.assertRaisesRegex(ValueError, "modified"):
            self.consume(final)

    def test_binding_rejected_schema_cleans_partial_native_subscriptions(self):
        api, actors, data, bounds = self.fixture()
        ordered = sorted(actors, key=lambda a: a.label)
        ordered[1].component.mesh.get_editor_property = lambda name: object()
        job = {
            "_expected_native_labels": data["_expected_labels"],
            "operation_status": "CONTACT_JOB_RUNNING",
        }
        with self.assertRaisesRegex(ValueError, "delegate schema"):
            self.consume(m.bind_native_mesh_guards_steps(api, None, job))
        first = ordered[0].component.mesh.get_editor_property("mesh_modified_bp_event")
        self.assertEqual(len(first.callbacks), 1)
        self.assertTrue(m.cleanup_native_mesh_guards(job))
        self.assertEqual(first.callbacks, [])

    def test_guard_cleanup_removes_only_owned_callable_and_can_retry_failure(self):
        api, actors, data, bounds = self.fixture()
        job = self.guarded_job(api, data)
        delegate = actors[0].component.mesh.get_editor_property(
            "mesh_modified_bp_event"
        )

        def foreign(mesh):
            return None

        delegate.add_callable(foreign)
        self.assertTrue(m.cleanup_native_mesh_guards(job))
        self.assertEqual(delegate.callbacks, [foreign])
        job = self.guarded_job(api, data)
        delegate = actors[0].component.mesh.get_editor_property(
            "mesh_modified_bp_event"
        )
        original = delegate.remove_callable
        delegate.remove_callable = lambda cb: (_ for _ in ()).throw(
            RuntimeError("native remove unavailable")
        )
        self.assertFalse(m.cleanup_native_mesh_guards(job))
        self.assertEqual(len(job["_mesh_edit_bindings"]), 1)
        delegate.remove_callable = original
        self.assertTrue(m.cleanup_native_mesh_guards(job))
        self.assertEqual(delegate.callbacks, [foreign])

    def test_disconnected_guard_is_not_silently_accepted(self):
        api, actors, data, bounds = self.fixture()
        job = self.guarded_job(api, data)
        mesh, delegate, callback, path = job["_mesh_edit_bindings"][0]
        delegate.remove_callable(callback)
        with self.assertRaisesRegex(ValueError, "disconnected"):
            m.assert_native_mesh_guards(job)

    def test_actual_native_radius_consumes_mask_clearance(self):
        data = {
            "assets": [
                {"id": "rock", "bounds_cm": {"origin": [0, 0, 1], "extent": [1, 1, 1]}}
            ],
            "placements": [
                {"site": "P0", "asset_id": "rock", "world_xy_cm": [100, 100]}
            ],
        }
        offset = 2 * 4033 + 2
        distances = bytearray((offset + 1) * 4)
        reasons = bytearray((offset + 1) * 2)
        struct.pack_into("<f", distances, offset * 4, 0.515)
        with patch.object(
            m, "authenticated_exclusion_buffers", return_value=[distances, reasons]
        ):
            self.assertIn("P0", m.verify_footprints(data))
            with self.assertRaises(ValueError):
                m.verify_footprints(
                    data, {"rock": {"origin": [0, 0, 1], "extent": [1.1, 1.1, 1]}}
                )


if __name__ == "__main__":
    unittest.main()
