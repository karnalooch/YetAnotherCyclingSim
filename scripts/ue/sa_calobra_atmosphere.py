"""Transient Mediterranean daylight for Sa Calobra review captures.

The actors returned by this module are diagnostic only. Callers retain them for
the editor session and never save them into Base_DTM.
"""

from __future__ import annotations

import unreal


def spawn_mediterranean_atmosphere(actors, sun_component, sky_component):
    """Create a deterministic blue-sky atmosphere with light coastal haze."""
    sun_component.set_editor_property("atmosphere_sun_light", True)
    sky_component.set_editor_property("real_time_capture", True)

    atmosphere = actors.spawn_actor_from_class(
        unreal.SkyAtmosphere,
        unreal.Vector(0, 0, 300000),
        unreal.Rotator(),
        transient=True,
    )
    if not atmosphere:
        raise RuntimeError("Sa Calobra SkyAtmosphere could not be spawned")

    fog = actors.spawn_actor_from_class(
        unreal.ExponentialHeightFog,
        unreal.Vector(0, 0, 0),
        unreal.Rotator(),
        transient=True,
    )
    if not fog:
        raise RuntimeError("Sa Calobra coastal haze could not be spawned")
    fog_component = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    if not fog_component:
        raise RuntimeError("Sa Calobra coastal haze has no fog component")
    fog_component.set_editor_property("fog_density", 0.0015)
    fog_component.set_editor_property("fog_height_falloff", 0.2)
    fog_component.set_editor_property("fog_max_opacity", 0.25)

    proof = {
        "status": "PASS",
        "preset": "SA_CALOBRA_MEDITERRANEAN_DAYLIGHT_V1",
        "sky_atmosphere": True,
        "skylight_real_time_capture": True,
        "fog_density": 0.0015,
        "fog_height_falloff": 0.2,
        "fog_max_opacity": 0.25,
        "map_saved": False,
    }
    return (atmosphere, fog), proof
