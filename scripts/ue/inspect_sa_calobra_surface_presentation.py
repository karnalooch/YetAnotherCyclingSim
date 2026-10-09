"""Record current light settings without editing the saved review scene."""

import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if (
    world.get_path_name().split(".")[0]
    != "/Game/Worlds/SaCalobra/L_SaCalobraGeneratedSurfaces_9992abd22044"
):
    raise RuntimeError("Open the recorded presentation review map")
lights = []
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Light):
    component = actor.get_component_by_class(unreal.LightComponent)
    if component:
        color = component.get_editor_property("light_color")
        lights.append(
            {
                "actor": actor.get_path_name(),
                "class": actor.get_class().get_name(),
                "color": [color.r, color.g, color.b, color.a],
                "use_temperature": component.get_editor_property("use_temperature"),
                "temperature_kelvin": component.get_editor_property("temperature"),
                "intensity": component.get_editor_property("intensity"),
            }
        )
path = (
    ROOT
    / "Saved/RuntimeProof/TextureLandscape/9992abd220444900a404703ffd4e92f6/lighting.json"
)
if path.exists():
    raise RuntimeError("Lighting evidence already recorded")
path.write_text(
    json.dumps(
        {"map": world.get_path_name(), "lights": lights, "scene_modified": False},
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
unreal.log("YACS_PRESENTATION_LIGHTING_RECORDED " + str(path))
