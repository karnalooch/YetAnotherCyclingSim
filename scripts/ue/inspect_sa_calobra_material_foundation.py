"""Read-only UE 5.8 material-function and frozen-scene inventory for Issue #363."""

import json
import sys
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.manage_local_workspace import load_workspace  # noqa: E402


def inspect():
    config = load_workspace()
    if Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve() != Path(config["project"]):
        raise RuntimeError("Wrong authoring project")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != config["map"]:
        raise RuntimeError("Wrong map; inspection will not load another map")
    functions = {}
    for name in ("WorldAlignedTexture", "WorldAlignedNormal"):
        path = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name
        asset = unreal.load_asset(path)
        if asset is None:
            raise RuntimeError("Missing native material function: " + path)
        inputs, outputs, details = [], [], []
        for (
            expression
        ) in unreal.MaterialEditingLibrary.get_material_function_expressions(asset):
            if isinstance(expression, unreal.MaterialExpressionFunctionInput):
                inputs.append(str(expression.get_editor_property("input_name")))
                details.append(
                    {
                        "name": str(expression.get_editor_property("input_name")),
                        "description": str(
                            expression.get_editor_property("description")
                        ),
                        "preview": str(expression.get_editor_property("preview_value")),
                        "use_preview_default": bool(
                            expression.get_editor_property(
                                "use_preview_value_as_default"
                            )
                        ),
                    }
                )
            elif isinstance(expression, unreal.MaterialExpressionFunctionOutput):
                outputs.append(str(expression.get_editor_property("output_name")))
        functions[name] = {
            "path": path,
            "inputs": inputs,
            "outputs": outputs,
            "input_details": details,
        }
    actors = unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    consumers = []
    for actor in actors:
        if isinstance(actor, unreal.Landscape):
            components = actor.get_components_by_class(unreal.LandscapeComponent)
            roots = {}
            for component in components:
                material = component.get_material(0)
                seen = set()
                while isinstance(material, unreal.MaterialInstance):
                    if material.get_path_name() in seen:
                        raise RuntimeError("Cyclic component material parent")
                    seen.add(material.get_path_name())
                    material = material.get_editor_property("parent")
                path = material.get_path_name() if material else None
                roots[path] = roots.get(path, 0) + 1
            consumers.append(
                {
                    "actor": actor.get_path_name(),
                    "assigned": str(
                        actor.get_editor_property("landscape_material").get_path_name()
                    ),
                    "component_count": len(components),
                    "component_material_roots": roots,
                }
            )
    report = {
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "world": world.get_path_name(),
        "functions": functions,
        "landscape_consumers": consumers,
        "actors": [
            {
                "label": a.get_actor_label(),
                "class": a.get_class().get_name(),
                "path": a.get_path_name(),
            }
            for a in actors
        ],
        "scene_modified": False,
    }
    path = Path(config["work"]) / "2b-material-native-inspection.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    unreal.log("YACS 2B native inspection complete; scene unchanged")
    return report


if __name__ == "__main__":
    inspect()
