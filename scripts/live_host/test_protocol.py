"""Offline #476 command, source, replay, persistence and editor isolation tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.live_host import protocol
from scripts.live_host.live_requests import LiveRequestLoop

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json"
HEAD = "a" * 40
SESSION = "20261012T220000Z-0123456789ab"


def request(action="inspect", sequence=1, **kwargs):
    return {
        "schema_version": 1,
        "session": SESSION,
        "source_sha": HEAD,
        "request_id": "visit-one",
        "sequence": sequence,
        "action": action,
        **kwargs,
    }


class ProtocolContract(unittest.TestCase):
    def test_authentic_rejected_sites_and_no_placement(self):
        doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
        protocol.validate_red_manifest(doc)
        for value in (
            {"placement": True},
            {"qualified_assets": ["foo"]},
            {"source_map_sha256": "0" * 64},
            {"scope": "PRODUCTION"},
            {"full_qualification": True},
        ):
            altered = copy.deepcopy(doc)
            altered.update(value)
            with self.subTest(value=value), self.assertRaises(protocol.Rejected):
                protocol.validate_red_manifest(altered)
        doc["markers"][0]["xy_cm"][0] += 1
        with self.assertRaises(protocol.Rejected):
            protocol.validate_red_manifest(doc)

    def test_versioned_exact_session_source_and_replay(self):
        self.assertEqual(
            protocol.validate_request(
                request("focus_site", site="P3"),
                session=SESSION,
                source_sha=HEAD,
                last_sequence=0,
            )["site"],
            "P3",
        )
        for changes in (
            {"session": "other"},
            {"source_sha": "b" * 40},
            {"sequence": 0},
            {"sequence": True},
            {"sequence": 2},
            {"schema_version": True},
            {"schema_version": 2},
            {"action": "execute"},
            {"action": "set_material"},
            {"request_id": "../../other"},
            {"code": "unreal.EditorUtilityLibrary.save_asset(...)"},
        ):
            payload = {**request(), **changes}
            with self.subTest(changes=changes), self.assertRaises(protocol.Rejected):
                protocol.validate_request(
                    payload, session=SESSION, source_sha=HEAD, last_sequence=0
                )
        with self.assertRaises(protocol.Rejected):
            protocol.validate_request(
                request(), session=SESSION, source_sha=HEAD, last_sequence=1
            )

    def test_commands_reject_unbounded_coordinates_and_type_coercion(self):
        for command in (
            request("focus_site", site="P7"),
            request("focus_site", site="P3", x=123),
            request("focus_site", site=3),
            request("set_markers_visible", visible="true"),
            request("set_markers_visible", visible=1),
            request("inspect", site="P3"),
        ):
            with self.subTest(command=command), self.assertRaises(protocol.Rejected):
                protocol.validate_request(
                    command, session=SESSION, source_sha=HEAD, last_sequence=0
                )
        protocol.validate_request(
            request("set_markers_visible", visible=False),
            session=SESSION,
            source_sha=HEAD,
            last_sequence=0,
        )

    def test_bound_json_file_and_new_abslog_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "request.json"
            path.write_text(json.dumps(request()), encoding="utf-8")
            self.assertEqual(protocol.load_bounded_json(path)["action"], "inspect")
            path.write_bytes(b"{" + b"a" * 4096)
            with self.assertRaises(protocol.Rejected):
                protocol.load_bounded_json(path)
            first = root / "session"
            first.mkdir()
            protocol.existing_abslog_only(first)
            (first / "editor.log").write_text("Unreal Engine startup", encoding="utf-8")
            protocol.existing_abslog_only(first)
            (first / "old-receipt.json").write_text("stale", encoding="utf-8")
            with self.assertRaises(protocol.Rejected):
                protocol.existing_abslog_only(first)
            with self.assertRaises(protocol.Rejected):
                protocol.safe_session_root(root, "../outside")

    def test_historical_browsers_are_not_live_claims(self):
        self.assertFalse(
            protocol.normalize_capture_result(
                {
                    "status": "BROWSER_VIDEO_RECEIVED",
                    "browser_frames_received": True,
                    "owner_handoff": True,
                    "placement": False,
                }
            )
        )
        self.assertFalse(
            protocol.normalize_capture_result(
                {
                    "status": "LIVE_VIDEO_VERIFIED",
                    "browser_frames_received": True,
                    "owner_handoff": True,
                    "placement": False,
                    "post_job_alive": False,
                }
            )
        )


class VisualCommandQueueContract(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="yacs-live-")
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / "sessions" / SESSION).mkdir(parents=True)
        self.calls = []
        self.loop = LiveRequestLoop(
            root=self.root,
            session=SESSION,
            source_sha=HEAD,
            handler=self.perform,
        )

    def perform(self, value):
        self.calls.append(value)
        return {"action": value["action"], "readback": True}

    def enqueue(self, action="inspect", seq=1, **kwargs):
        payload = request(action, seq, **kwargs)
        payload["request_id"] = f"req-{seq}"
        location = self.loop.queue / f"{seq:06d}-req-{seq}.json"
        location.write_text(json.dumps(payload), encoding="utf-8")
        return location

    def test_one_command_completed_once_not_replayed(self):
        self.enqueue()
        self.loop.poll(1.0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.loop.last_sequence, 1)
        self.assertFalse(any(self.loop.queue.iterdir()))
        complete = (
            self.root / "sessions" / SESSION / "commands" / "000001-req-1.result.json"
        )
        self.assertEqual(
            json.loads(complete.read_text())["status"], "COMPLETED_VISUAL_ONLY"
        )
        self.loop.poll(2.0)
        self.assertEqual(len(self.calls), 1)
        self.enqueue("focus_site", 2, site="P3")
        self.loop.poll(3.0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.loop.last_sequence, 2)
        self.assertTrue(
            (
                self.root / "sessions" / SESSION / "processed" / "000002-req-2.json"
            ).exists()
        )

    def test_native_import_nested_slate_tick_cannot_reenter_request(self):
        def native_import(value):
            self.calls.append(value)
            self.loop.poll(2.0)
            self.loop.poll(3.0)
            return {"action": value["action"], "readback": True}

        self.loop.handler = native_import
        self.enqueue()
        self.loop.poll(1.0)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.loop.alive)
        self.assertFalse(self.loop._processing)
        self.assertEqual(self.loop.last_sequence, 1)
        self.assertEqual(len(list(self.loop.receipts.glob("*.started.json"))), 1)
        self.assertEqual(len(list(self.loop.receipts.glob("*.result.json"))), 1)
        self.enqueue(seq=2)
        self.loop.poll(4.0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.loop.last_sequence, 2)

    def test_bad_sequence_does_not_execute(self):
        self.enqueue(seq=2)
        with self.assertRaises(protocol.Rejected):
            self.loop.poll(1.0)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.loop.last_sequence, 0)

    def test_no_arbitrary_scripts_in_queue(self):
        payload = self.enqueue()
        path = payload.with_suffix(".ps1")
        payload.rename(path)
        with self.assertRaises(protocol.Rejected):
            self.loop.poll(1.0)
        self.assertEqual(self.calls, [])

    def test_failed_native_handler_is_not_replayed(self):
        self.loop.handler = lambda value: (_ for _ in ()).throw(
            RuntimeError("readback failed")
        )
        self.enqueue()
        self.loop.poll(1.0)
        self.assertFalse(self.loop.alive)
        self.assertEqual(self.loop.last_sequence, 0)
        receipt = (
            self.root / "sessions" / SESSION / "commands" / "000001-req-1.result.json"
        )
        self.assertEqual(json.loads(receipt.read_text())["status"], "FAILED_NO_RETRY")
        self.loop.poll(2.0)
        self.assertEqual(len(list(self.loop.receipts.glob("*.result.json"))), 1)

    def test_heartbeat_never_claims_post_job_alive(self):
        self.loop.poll(1.0)
        file = self.root / "sessions" / SESSION / "live-heartbeat.json"
        heartbeat = json.loads(file.read_text())
        self.assertEqual(heartbeat["status"], "EDITOR_TICK_ALIVE")
        self.assertFalse(heartbeat["owner_handoff"])
        self.assertNotIn("post_job_alive", heartbeat)


class GeneralUnrealEditingProtocol(unittest.TestCase):
    """UE operations are extensible without accepting raw scripts in a request."""

    @staticmethod
    def recipe_request(**changes):
        row = request(
            "run_recipe",
            recipe="actor_preview_transform",
            recipe_revision="b" * 40,
            recipe_sha256="c" * 64,
            intent="preview",
            parameters={
                "actor_path": "/Game/Test.Map:PersistentLevel.Actor",
                "location_cm": [100.0, 200.0, 300.0],
                "rotation_deg": [0, 0, 0],
            },
        )
        row.update(changes)
        return row

    def test_source_pinned_general_unreal_recipe_is_validated(self):
        value = self.recipe_request()
        protocol.validate_request(
            value, session=SESSION, source_sha=HEAD, last_sequence=0
        )
        for altered in (
            {"recipe": "../../bad.py"},
            {"recipe_sha256": "00"},
            {"recipe_revision": "main"},
            {"intent": "shell"},
            {"parameters": {"__import__": "os"}},
            {"parameters": {"a": float("inf")}},
            {"python_code": "import os"},
        ):
            with (
                self.subTest(altered=altered),
                self.assertRaises((protocol.Rejected, ValueError)),
            ):
                protocol.validate_request(
                    self.recipe_request(**altered),
                    session=SESSION,
                    source_sha=HEAD,
                    last_sequence=0,
                )

    def test_reviewed_recipe_manifest_and_sha256_required(self):
        from scripts.live_host import editor_recipes
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "recipes" / ("b" * 40) / "actor_preview_transform.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "def run(unreal, context, parameters):\n    return {'status':'APPLIED_PREVIEW','map_saved':False}\n"
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            contract = {
                "schema_version": 1,
                "repository": "karnalooch/YetAnotherCyclingSim",
                "revision": "b" * 40,
                "recipe": "actor_preview_transform",
                "source_path": "scripts/live_host/recipes/actor_preview_transform.py",
                "sha256": digest,
                "intents": ["preview"],
                "capability": "actor_presentation",
                "parameters": {"actor_path": {"type": "string"}},
                "asset_scope": [],
                "review_issue": 476,
                "ci_admitted": True,
            }
            manifest = source.with_suffix(".json")
            manifest.write_text(json.dumps(contract))
            value = self.recipe_request(recipe_sha256=digest)
            read, path = editor_recipes.parse_manifest(root, value)
            self.assertEqual(path, source)
            self.assertEqual(read["capability"], "actor_presentation")
            source.write_text("unreviewed source replacement")
            with self.assertRaises(protocol.Rejected):
                editor_recipes.parse_manifest(root, value)
            source.write_text(
                "def run(unreal, context, parameters):\n    return {'status':'APPLIED_PREVIEW','map_saved':False}\n"
            )
            with self.assertRaises(protocol.Rejected):
                editor_recipes.parse_manifest(
                    root, self.recipe_request(recipe_sha256=digest, intent="author")
                )

    def test_authoring_declares_exact_backup_and_never_frozen_map(self):
        from scripts.live_host import editor_recipes

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for relative in (
                "Content/Generated/YACS/SaCalobra/WholeMapPreparation/M.uasset",
                "Content/Worlds/SaCalobra/Landscape.umap",
                "Content/Other/Base_DTM.uasset",
                "Content/Generated/YACS/RoadAsphaltConsumer/Road.uasset",
                "Content/../../escape.uasset",
            ):
                with (
                    self.subTest(relative=relative),
                    self.assertRaises(protocol.Rejected),
                ):
                    editor_recipes.author_asset_path(root, relative)
            with self.assertRaises(protocol.Rejected):
                editor_recipes.reserve_backups(
                    project=root,
                    session_root=root,
                    request={"intent": "author", "sequence": 1, "request_id": "test"},
                    contract={"asset_scope": ["Content/Art/SM_Example.uasset"]},
                )

    def test_parameter_type_units_and_enumerated_scope(self):
        from scripts.live_host import editor_recipes

        schema = {
            "enabled": {"type": "boolean"},
            "intensity": {"type": "number", "minimum": 0, "maximum": 500},
            "translation": {"type": "vec3"},
            "choice": {"type": "enum", "enum": ["preview", "commit"]},
        }
        valid = {
            "enabled": True,
            "intensity": 120.5,
            "translation": [1, 2, 3],
            "choice": "preview",
        }
        editor_recipes.verify_parameters(schema, valid)
        for key, bad in (
            ("enabled", 1),
            ("intensity", float("nan")),
            ("intensity", 1000),
            ("translation", [1, 2, 3e100]),
            ("choice", "shell"),
        ):
            changed = {**valid, key: bad}
            with self.subTest(key=key, bad=bad), self.assertRaises(protocol.Rejected):
                editor_recipes.verify_parameters(schema, changed)

    def test_repo_recipes_have_no_bare_shell_remote_payload(self):
        catalog = json.loads(
            (ROOT / "scripts/live_host/recipes/catalog.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(catalog["policy"], "SOURCE_REVIEWED_RECIPES_ONLY")
        self.assertGreaterEqual(len(catalog["recipes"]), 4)
        for row in catalog["recipes"]:
            self.assertEqual(row["intents"], ["preview"])
            self.assertEqual(row["asset_scope"], [])
            script = ROOT / "scripts/live_host/recipes" / (row["id"] + ".py")
            self.assertTrue(script.is_file())
            self.assertIn("def run(unreal, context, parameters):", script.read_text())


if __name__ == "__main__":
    unittest.main()
