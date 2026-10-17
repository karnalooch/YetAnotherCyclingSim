"""Offline contracts for #474 latest v0.3.1 road + lighting Live Host profile.

Native image, complete terrain admission and a real Windows file closure are
separate runtime checks. Tests never start Unreal or write the accepted map.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.live_host import live_requests
from scripts.live_host import live_world_road
from scripts.live_host import protocol
from scripts.ue import read_live_road_checkpoint as road_reader

ROOT = Path(__file__).resolve().parents[2]
LIVE = ROOT / "scripts" / "live_host"
REGISTRY = json.loads((LIVE / "verified_worlds.json").read_text())


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = (float(x), float(y), float(z))

    def __sub__(self, other):
        return Vec(self.x - other.x, self.y - other.y, self.z - other.z)

    def length(self):
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5


class World:
    def get_path_name(self):
        return road_reader.MAP + ".L_RoadSurface"


class NativeActor:
    def __init__(self, name, material):
        self.name = name
        self.material = material

    def get_actor_label(self):
        return self.name

    def get_dynamic_mesh_component(self):
        return self

    def get_material(self, _slot):
        return self

    def get_path_name(self):
        return self.material


class Editor:
    world = World()

    def get_editor_world(self):
        return self.world

    def set_level_viewport_camera_info(self, eye, rotation):
        self.camera = (eye, rotation)

    def get_level_viewport_camera_info(self):
        return self.camera


class FakeApi:
    DynamicMeshActor = type("DynamicMeshActor", (), {})
    DirectionalLight = type("DirectionalLight", (), {})
    SkyLight = type("SkyLight", (), {})
    SkyAtmosphere = type("SkyAtmosphere", (), {})
    ExponentialHeightFog = type("ExponentialHeightFog", (), {})
    VolumetricCloud = type("VolumetricCloud", (), {})
    UnrealEditorSubsystem = type("UnrealEditorSubsystem", (), {})
    Vector = Vec

    class MathLibrary:
        @staticmethod
        def find_look_at_rotation(_eye, _target):
            return "pinned-road-camera"

    class SystemLibrary:
        @staticmethod
        def get_console_variable_int_value(_name):
            return 1

    class EditorLoadingAndSavingUtils:
        @staticmethod
        def load_map(name):
            return name == road_reader.MAP

    class GameplayStatics:
        actors = []

        @classmethod
        def get_all_actors_of_class(cls, _world, kind):
            if kind is FakeApi.DynamicMeshActor:
                return cls.actors
            if kind in (FakeApi.DirectionalLight, FakeApi.SkyLight):
                return [object()]
            return []

    @staticmethod
    def get_editor_subsystem(_cls):
        return Editor()


def native_fixture(project):
    package = road_reader.PACKAGE
    bindings = [{
        "label": "YACS_PERSIST_ROAD",
        "slot": 0,
        "material": package + "/MI_Road.MI_Road",
    }]
    bindings.extend({
        "label": f"YACS_PERSIST_SUPPORT_{i:03d}",
        "slot": 1,
        "material": package + "/MI_Shoulder.MI_Shoulder",
    } for i in range(185))
    actors = [NativeActor(row["label"], row["material"]) for row in bindings]
    actors.extend(
        NativeActor(f"Other_{i:03d}", "") for i in range(559 - len(actors))
    )
    FakeApi.GameplayStatics.actors = actors
    relative = "Content/Generated/YACS/LiveCheckpoints/R2a00f7ebba40"
    dest = project / relative
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "L_RoadSurface.umap").write_bytes(b"test")
    profile = {
        "map_package": road_reader.MAP,
        "map_relative": relative + "/L_RoadSurface.umap",
        "files": [{"bytes": 4, "sha256": "a" * 64}],
        "version": "0.3.1",
        "camera_cm": [56912.0, 53090.0, 46766.0],
        "target_cm": [58088.0, 52542.0, 46508.0],
    }
    return profile, {"bindings": bindings}


class LatestWorldContract(unittest.TestCase):
    def test_v031_is_only_selected_verified_world(self):
        self.assertEqual(REGISTRY["policy"], "LATEST_VERIFIED_FAIL_CLOSED")
        self.assertEqual(REGISTRY["schema_version"], 1)
        profiles = REGISTRY["worlds"]
        self.assertEqual(len(profiles), 1)
        profile = profiles[0]
        self.assertEqual(REGISTRY["selected_world_id"], profile["id"])
        self.assertEqual(profile["version"], "0.3.1")
        self.assertEqual(profile["map_package"], road_reader.MAP)
        self.assertEqual(profile["evidence_status"],
                         "SAVED_CHECKPOINT_REOPENED_RENDERED")
        self.assertFalse(profile["performance_pass"])
        self.assertEqual(profile["owner_visual_status"], "PENDING_FINAL_M3")
        self.assertEqual(
            {entry["path"]: (entry["bytes"], entry["sha256"])
             for entry in profile["files"]},
            {"Content/" + road_reader.PACKAGE.removeprefix("/Game/")
             + "/" + name: identity
             for name, identity in road_reader.EXPECTED_FILES.items()},
        )
        self.assertEqual(profile["native_actor_count"], 559)
        self.assertEqual(profile["native_binding_count"], 186)

    def test_current_road_has_actual_native_bindings_and_light_observations(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root)
            profile, saved = native_fixture(project)
            adapter = live_world_road.VerifiedRoadWorld(
                project, project / "session", REGISTRY,
                REGISTRY["selected_world_id"], project,
            )
            with patch.object(
                live_world_road, "read_world_pins", return_value=(profile, saved)
            ), patch.object(live_world_road, "sha256", return_value="a" * 64):
                result = adapter.start(FakeApi)
            self.assertEqual(
                result["status"], "LATEST_VERIFIED_WORLD_NATIVE_ROAD_READY"
            )
            self.assertEqual(result["road_native_actor_count"], 559)
            self.assertEqual(result["material_bindings_verified"], 186)
            self.assertEqual(result["lighting"]["actor_counts"]["sky_lights"], 1)
            self.assertEqual(
                result["lighting"]["actor_counts"]["directional_lights"], 1
            )
            self.assertFalse(result["global_lighting_visual_pass"])
            self.assertFalse(result["terrain_modified"])
            self.assertFalse(result["map_saved"])
            self.assertEqual(result["markers"], [])

    def test_a_missing_road_binding_blocks_native_scene(self):
        with tempfile.TemporaryDirectory() as root:
            project = Path(root)
            profile, saved = native_fixture(project)
            saved["bindings"][0]["material"] = "/Game/Fake/MI_Road"
            adapter = live_world_road.VerifiedRoadWorld(
                project, project / "session", REGISTRY,
                REGISTRY["selected_world_id"], project,
            )
            with patch.object(
                live_world_road, "read_world_pins", return_value=(profile, saved)
            ), self.assertRaises(ValueError):
                adapter.start(FakeApi)

    def test_road_camera_is_the_only_new_bounded_navigation(self):
        self.assertEqual(
            protocol.validate_request({
                "schema_version": 1, "session": "20261012T220000Z-0123456789ab",
                "source_sha": "a" * 40, "request_id": "focus-road",
                "sequence": 1, "action": "focus_road",
            }, session="20261012T220000Z-0123456789ab",
                source_sha="a" * 40, last_sequence=0)["action"],
            "focus_road",
        )
        with self.assertRaises(protocol.Rejected):
            protocol.validate_request({
                "schema_version": 1, "session": "20261012T220000Z-0123456789ab",
                "source_sha": "a" * 40, "request_id": "focus-road",
                "sequence": 1, "action": "focus_road", "site": "P3",
            }, session="20261012T220000Z-0123456789ab",
                source_sha="a" * 40, last_sequence=0)

    def test_missing_latest_world_must_not_fallback_to_p3(self):
        launcher = (LIVE / "Start-YacsLiveHost.ps1").read_text()
        resolver = (LIVE / "Resolve-YacsLiveWorld.ps1").read_text()
        bootstrap = (LIVE / "bootstrap.py").read_text()
        self.assertIn("Resolve-YacsLiveWorld.ps1", launcher)
        self.assertIn("LATEST_VERIFIED_WORLD_BLOCKED", launcher)
        self.assertNotIn("Pcg365Diagnostic.uproject", launcher)
        self.assertIn("    $mapPackage,", launcher)
        self.assertNotIn(
            "    '/Game/Generated/YACS/SaCalobra/WholeMapPreparation/"
            "L_SaCalobraMaterialReview',",
            launcher,
        )
        self.assertIn("LATEST_VERIFIED_FAIL_CLOSED", resolver)
        self.assertIn("LATEST_VERIFIED_WORLD_PREFLIGHT_PASS", resolver)
        self.assertIn("Get-FileHash", resolver)
        self.assertIn("source_map_relative", resolver)
        self.assertIn("VerifiedRoadWorld", bootstrap)
        self.assertIn("ensure_review_lighting(unreal, LIVE)", bootstrap)
        self.assertIn('"saved_scene_readback": world_receipt["lighting"]', bootstrap)
        self.assertNotIn("RedReview(stage", bootstrap)

    def test_persisted_install_and_upgrade_require_latest_world(self):
        installer = (LIVE / "Install-YacsLiveHost.ps1").read_text()
        upgrade = (LIVE / "Upgrade-YacsLiveHostCodec.ps1").read_text()
        rollback = (LIVE / "Rollback-YacsLiveHostCodec.ps1").read_text()
        self.assertIn("world_profile_id='latest_verified'", installer)
        self.assertIn("video_codec='VP9'", installer)
        self.assertIn("world_profile_id' -NotePropertyValue 'latest_verified'",
                      upgrade)
        self.assertIn("Resolve-YacsLiveWorld.ps1", upgrade)
        self.assertLess(
            upgrade.index("if (-not $Apply)"),
            upgrade.index("Move-Item -LiteralPath $incomplete"),
        )
        self.assertIn("installation-before-latest-world-", upgrade)
        self.assertIn("installation-before-latest-world-", rollback)
        self.assertNotIn("Start-ScheduledTask", upgrade)
        self.assertNotIn("Stop-Process", upgrade)

    def test_newest_world_forbids_unsafe_actor_transform_recipes(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = live_world_road.VerifiedRoadWorld(
                Path(tmp), Path(tmp), REGISTRY,
                "sa_calobra_road_v0_3_1", Path(tmp),
            )
            with self.assertRaises(protocol.Rejected):
                live_requests.execute_visual_request(
                    live,
                    {"action": "run_recipe",
                     "recipe": "actor_preview_transform", "intent": "preview"},
                    FakeApi,
                    live_root=Path(tmp), session_root=Path(tmp),
                )
            self.assertEqual(
                live_requests.execute_visual_request(
                    live, {"action": "focus_site", "site": "P3"}, FakeApi
                )["not_applicable"],
                "OLD_DIAGNOSTIC_SITES",
            )

    def test_native_inspector_is_read_only(self):
        text = (LIVE / "live_world_road.py").read_text()
        for operation in (
            "save_asset(", "save_all(", "spawn_actor(", "Stop-Process",
            "import_asset(", "set_actor_transform(", "remove_actor(",
        ):
            with self.subTest(operation=operation):
                self.assertNotIn(operation, text)


if __name__ == "__main__":
    unittest.main()
