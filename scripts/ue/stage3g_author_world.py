"""
Stage 3G map lighting / atmosphere authoring. Idempotent.

Loads L_CyclingTest, reuses the first actor of each supported environment
class or spawns one when missing, applies a restrained daylight/fog baseline,
then saves the map. This is editor authoring only; runtime simulation never
reads these actors.
"""

import os
from pathlib import Path
import sys
import traceback
import unreal

MAP_PATH = "/Game/Prototype/Maps/L_CyclingTest"


def log(message):
    unreal.log("[Stage3GWorld] {}".format(message))


def actors_of_class(actor_class):
    world = unreal.EditorLevelLibrary.get_editor_world()
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, actor_class))


def get_or_spawn(actor_class, label, rotation=None):
    actors = actors_of_class(actor_class)
    if actors:
        actor = sorted(actors, key=lambda a: str(a.get_name()))[0]
        if len(actors) > 1:
            unreal.log_warning(
                "[Stage3GWorld] {} actors of {} exist; reusing {}".format(
                    len(actors), actor_class.__name__, actor.get_name()))
    else:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actor = subsystem.spawn_actor_from_class(
            actor_class,
            unreal.Vector(0.0, 0.0, 0.0),
            rotation or unreal.Rotator(0.0, 0.0, 0.0),
            False)
        if not actor:
            raise RuntimeError("failed to spawn {}".format(actor_class.__name__))
    actor.set_actor_label(label)
    return actor


def component(actor, component_class):
    result = actor.get_component_by_class(component_class)
    if not result:
        raise RuntimeError(
            "{} has no {}".format(actor.get_name(), component_class.__name__))
    return result


def main():
    try:
        world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
        if not world:
            raise RuntimeError("failed to load {}".format(MAP_PATH))

        sun = get_or_spawn(
            unreal.DirectionalLight,
            "Stage3G_Sun",
            unreal.Rotator(pitch=-31.0, yaw=-38.0, roll=0.0))
        sun.set_actor_rotation(
            unreal.Rotator(pitch=-31.0, yaw=-38.0, roll=0.0), False)
        sun_component = component(sun, unreal.DirectionalLightComponent)
        sun_component.set_intensity(8.0)

        sky = get_or_spawn(unreal.SkyLight, "Stage3G_SkyLight")
        sky_component = component(sky, unreal.SkyLightComponent)
        sky_component.set_intensity(0.75)

        get_or_spawn(unreal.SkyAtmosphere, "Stage3G_SkyAtmosphere")

        fog = get_or_spawn(unreal.ExponentialHeightFog, "Stage3G_HeightFog")
        fog_component = component(fog, unreal.ExponentialHeightFogComponent)
        fog_component.set_editor_property("fog_density", 0.0065)
        fog_component.set_editor_property("fog_height_falloff", 0.18)
        fog_component.set_editor_property("fog_max_opacity", 0.55)

        if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH):
            raise RuntimeError("failed to save {}".format(MAP_PATH))

        proof_path = os.environ.get("YACS_STAGE3G_WORLD_PROOF")
        if not proof_path:
            raise RuntimeError("YACS_STAGE3G_WORLD_PROOF is not set")
        Path(proof_path).write_text(
            "stage3g_world_authoring=success\n"
            "sun_intensity=8.0\n"
            "sky_intensity=0.75\n"
            "fog_density=0.0065\n"
            "fog_height_falloff=0.18\n"
            "fog_max_opacity=0.55\n",
            encoding="utf-8",
        )

        log(
            "SUCCESS: sun=8.0 sky=0.75 fog_density=0.0065 "
            "fog_height_falloff=0.18 fog_max_opacity=0.55")
    except Exception as exc:
        unreal.log_error("[Stage3GWorld] FAILURE: {}".format(exc))
        unreal.log_error(traceback.format_exc())
        sys.exit(1)


main()
