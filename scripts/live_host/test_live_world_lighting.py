"""Native-stub checks for source-backed transient Sa Calobra lighting."""
from __future__ import annotations

import unittest

from scripts.live_host import live_world_lighting as lighting


class NativeWorld:
    def get_path_name(self):
        return (
            "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/"
            "L_RoadSurface.L_RoadSurface"
        )


class NativeLive:
    profile_id = "sa_calobra_road_v0_3_1"
    map_package = (
        "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface"
    )

    def __init__(self):
        self.world = NativeWorld()
        self.owned = []


class LightComponent:
    def __init__(self):
        self.intensity = None
        self.sun = False
        self.lower_hemisphere = None
        self.recaptures = 0

    def set_intensity(self, value):
        self.intensity = value

    def set_atmosphere_sun_light(self, value):
        self.sun = value

    def set_editor_property(self, key, value):
        assert key == "lower_hemisphere_is_black"
        self.lower_hemisphere = value

    def recapture_sky(self):
        self.recaptures += 1


class Actor:
    def __init__(self, cls):
        self.cls = cls
        self.component = LightComponent()

    def get_component_by_class(self, _type):
        return self.component


class NativeApi:
    DirectionalLight = type("DirectionalLight", (), {})
    SkyLight = type("SkyLight", (), {})
    SkyAtmosphere = type("SkyAtmosphere", (), {})
    DirectionalLightComponent = type("DirectionalLightComponent", (), {})
    SkyLightComponent = type("SkyLightComponent", (), {})
    EditorActorSubsystem = type("EditorActorSubsystem", (), {})
    Vector = tuple
    Rotator = tuple

    class GameplayStatics:
        store = {}

        @classmethod
        def get_all_actors_of_class(cls, _world, actor_class):
            return cls.store.setdefault(actor_class, [])

    class Editor:
        def __init__(self, api, reject=None):
            self.api = api
            self.reject = reject
            self.spawned = []
            self.destroyed = []

        def spawn_actor_from_class(self, kind, *_args, transient):
            assert transient is True
            if kind == self.reject:
                return None
            actor = Actor(kind)
            self.api.GameplayStatics.store.setdefault(kind, []).append(actor)
            self.spawned.append(actor)
            return actor

        def destroy_actor(self, actor):
            self.destroyed.append(actor)
            self.api.GameplayStatics.store[actor.cls].remove(actor)
            return True

    def __init__(self, reject=None):
        self.GameplayStatics.store = {}
        self.editor = self.Editor(self, reject=reject)

    def get_editor_subsystem(self, _type):
        return self.editor

    @staticmethod
    def vector(*args):
        return args


# Engine stubs accept native Vector() and Rotator(pitch=...,yaw=...,roll=...).
def vector(*args):
    return args


def rotator(*args, **kwargs):
    return (args, kwargs)


class SourceLightingContract(unittest.TestCase):
    @staticmethod
    def api(reject=None):
        instance = NativeApi(reject=reject)
        instance.Vector = vector
        instance.Rotator = rotator
        return instance

    def test_missing_lights_use_existing_approved_transient_fallback(self):
        api = self.api()
        world = NativeLive()
        receipt = lighting.ensure_review_lighting(api, world)
        self.assertEqual(receipt["transient_light_count"], 3)
        self.assertEqual(receipt["skylight_recaptured"], 1)
        self.assertEqual(len(world.owned), 3)
        self.assertEqual(
            receipt["active_light_counts"],
            {"directional_lights": 1, "sky_lights": 1, "sky_atmospheres": 1},
        )
        sun = api.GameplayStatics.store[api.DirectionalLight][0]
        sky = api.GameplayStatics.store[api.SkyLight][0]
        self.assertEqual(sun.component.intensity, 6.0)
        self.assertTrue(sun.component.sun)
        self.assertEqual(sky.component.intensity, 1.15)
        self.assertFalse(sky.component.lower_hemisphere)
        self.assertEqual(sky.component.recaptures, 1)
        self.assertFalse(receipt["saved_map_modified"])
        self.assertFalse(receipt["global_lighting_visual_pass"])

    def test_saved_existing_global_lighting_is_not_overwritten(self):
        api = self.api()
        existing = {
            api.DirectionalLight: Actor(api.DirectionalLight),
            api.SkyLight: Actor(api.SkyLight),
            api.SkyAtmosphere: Actor(api.SkyAtmosphere),
        }
        for kind, value in existing.items():
            api.GameplayStatics.store[kind] = [value]
        result = lighting.ensure_review_lighting(api, NativeLive())
        self.assertEqual(result["transient_light_count"], 0)
        self.assertEqual(len(api.editor.spawned), 0)
        self.assertEqual(existing[api.SkyLight].component.recaptures, 1)
        self.assertIsNone(existing[api.DirectionalLight].component.intensity)

    def test_fail_closed_and_rollback_when_skylight_cannot_spawn(self):
        api = self.api()
        api.editor.reject = api.SkyLight
        live = NativeLive()
        with self.assertRaises(ValueError):
            lighting.ensure_review_lighting(api, live)
        self.assertEqual(live.owned, [])
        self.assertEqual(len(api.editor.destroyed), 2)
        self.assertTrue(all(
            not values for values in api.GameplayStatics.store.values()
        ))

    def test_wrong_world_must_never_spawn_lights(self):
        api = self.api()
        live = NativeLive()
        live.profile_id = "legacy_diagnostic"
        with self.assertRaises(ValueError):
            lighting.ensure_review_lighting(api, live)
        self.assertEqual(len(api.editor.spawned), 0)

    def test_frozen_landscape_and_road_apis_are_not_accessed(self):
        import inspect

        source = inspect.getsource(lighting)
        for forbidden in (
            "save_asset(", "save_map(", "set_actor_transform(",
            "set_actor_location(", "set_landscape(", "Stop-Process",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
