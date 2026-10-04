"""Contract tests for the transient Sa Calobra daylight preset."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


class SaCalobraAtmosphereTests(unittest.TestCase):
    def _load(self):
        unreal = Mock()
        unreal.SkyAtmosphere = type("SkyAtmosphere", (), {})
        unreal.ExponentialHeightFog = type("ExponentialHeightFog", (), {})
        unreal.ExponentialHeightFogComponent = type(
            "ExponentialHeightFogComponent", (), {}
        )
        namespace = {}
        script = Path(__file__).with_name("sa_calobra_atmosphere.py")
        with patch.dict(sys.modules, {"unreal": unreal}):
            exec(compile(script.read_text(), str(script), "exec"), namespace)
        return unreal, namespace["spawn_mediterranean_atmosphere"]

    def test_preset_spawns_blue_sky_and_light_coastal_haze(self):
        unreal, spawn = self._load()
        actors = Mock()
        atmosphere = Mock()
        fog = Mock()
        fog_component = Mock()
        fog.get_component_by_class.return_value = fog_component
        actors.spawn_actor_from_class.side_effect = [atmosphere, fog]
        sun_component = Mock()
        sky_component = Mock()

        objects, proof = spawn(actors, sun_component, sky_component)

        self.assertEqual(objects, (atmosphere, fog))
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(
            proof["preset"], "SA_CALOBRA_MEDITERRANEAN_DAYLIGHT_V1"
        )
        self.assertFalse(proof["map_saved"])
        sun_component.set_editor_property.assert_called_once_with(
            "atmosphere_sun_light", True
        )
        sky_component.set_editor_property.assert_called_once_with(
            "real_time_capture", True
        )
        fog_component.set_editor_property.assert_any_call("fog_density", 0.0015)
        fog_component.set_editor_property.assert_any_call(
            "fog_height_falloff", 0.2
        )
        fog_component.set_editor_property.assert_any_call("fog_max_opacity", 0.25)

    def test_missing_sky_atmosphere_fails_closed(self):
        _unreal, spawn = self._load()
        actors = Mock()
        actors.spawn_actor_from_class.return_value = None

        with self.assertRaisesRegex(RuntimeError, "SkyAtmosphere"):
            spawn(actors, Mock(), Mock())


if __name__ == "__main__":
    unittest.main()
