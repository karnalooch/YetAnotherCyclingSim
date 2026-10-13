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


class RockRemoteGuards(unittest.TestCase):
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
                    scale3d=vector(50, 50, 1),
                    rotation=SimpleNamespace(
                        rotator=lambda: SimpleNamespace(pitch=0, yaw=0, roll=0)
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


if __name__ == "__main__":
    unittest.main()
