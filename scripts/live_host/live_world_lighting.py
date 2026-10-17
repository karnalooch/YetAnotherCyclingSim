"""Non-persistent v0.3.1 global review lighting, based on existing M3 producer.

The saved road map remains source truth. This copies only the *conditional*
unreal light fallback already used by capture_material_forge_landscape.py:
DirectionalLight 6.0 with sun index when absent, SkyLight intensity 1.15 with
lower hemisphere open when absent, and SkyAtmosphere when absent.
Existing actors are preserved; no Landscape/material/road actor is moved.
"""
from __future__ import annotations


def need(condition, message):
    if not condition:
        raise ValueError(message)


def lights_of(unreal, world, actor_class):
    return list(unreal.GameplayStatics.get_all_actors_of_class(
        world, actor_class
    ))


def ensure_review_lighting(unreal, live):
    need(
        live.profile_id == "sa_calobra_road_v0_3_1"
        and live.world.get_path_name() ==
        live.map_package + ".L_RoadSurface",
        "Temporary review lighting forbidden outside verified v0.3.1"
    )
    original = {
        "directional_lights": lights_of(
            unreal, live.world, unreal.DirectionalLight
        ),
        "sky_lights": lights_of(unreal, live.world, unreal.SkyLight),
        "sky_atmospheres": lights_of(
            unreal, live.world, unreal.SkyAtmosphere
        ),
    }
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    try:
        if not original["sky_atmospheres"]:
            atmosphere = editor.spawn_actor_from_class(
                unreal.SkyAtmosphere,
                unreal.Vector(),
                unreal.Rotator(),
                transient=True,
            )
            need(atmosphere is not None,
                 "Could not create temporary SkyAtmosphere review fallback")
            spawned.append(atmosphere)
        if not original["directional_lights"]:
            sun = editor.spawn_actor_from_class(
                unreal.DirectionalLight,
                unreal.Vector(0, 0, 300000),
                unreal.Rotator(pitch=-36.0, yaw=-52.0, roll=0.0),
                transient=True,
            )
            need(sun is not None,
                 "Could not create temporary DirectionalLight fallback")
            spawned.append(sun)
            component = sun.get_component_by_class(
                unreal.DirectionalLightComponent
            )
            need(component is not None, "Temporary Sun component missing")
            component.set_intensity(6.0)
            component.set_atmosphere_sun_light(True)
        if not original["sky_lights"]:
            skylight = editor.spawn_actor_from_class(
                unreal.SkyLight,
                unreal.Vector(0, 0, 300000),
                unreal.Rotator(),
                transient=True,
            )
            need(skylight is not None,
                 "Could not create temporary SkyLight fallback")
            spawned.append(skylight)
            component = skylight.get_component_by_class(
                unreal.SkyLightComponent
            )
            need(component is not None, "Temporary SkyLight component missing")
            component.set_intensity(1.15)
            component.set_editor_property(
                "lower_hemisphere_is_black", False
            )
        skylights = lights_of(unreal, live.world, unreal.SkyLight)
        for actor in skylights:
            component = actor.get_component_by_class(
                unreal.SkyLightComponent
            )
            need(component is not None, "Native SkyLight component missing")
            component.recapture_sky()
        observed = {
            "directional_lights": len(lights_of(
                unreal, live.world, unreal.DirectionalLight
            )),
            "sky_lights": len(skylights),
            "sky_atmospheres": len(lights_of(
                unreal, live.world, unreal.SkyAtmosphere
            )),
        }
        need(all(count >= 1 for count in observed.values()),
             "Source-backed global review lighting did not materialize")
    except Exception:
        for actor in reversed(spawned):
            try:
                editor.destroy_actor(actor)
            except Exception:
                pass
        raise
    # Keep transient UObjects reachable in the running Editor, never save.
    live.owned.extend(spawned)
    return {
        "status": "NATIVE_REVIEW_LIGHTING_PRESENT_NOT_OWNER_ACCEPTED",
        "inherited_light_counts": {
            name: len(actors) for name, actors in original.items()
        },
        "active_light_counts": observed,
        "transient_light_count": len(spawned),
        "skylight_recaptured": len(skylights),
        "fallback_source": "capture_material_forge_landscape.py",
        "saved_map_modified": False,
        "global_lighting_visual_pass": False,
    }
