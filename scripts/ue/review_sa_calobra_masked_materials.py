"""Reversible broad camera view of the current material preview."""

import runpy
from pathlib import Path
import unreal


def main(restore=False):
    module = runpy.run_path(
        str(Path(__file__).with_name("preview_sa_calobra_masked_materials.py"))
    )
    world, landscape, components = module["context"]()
    state = getattr(unreal, module["STATE"], None)
    if not state or state["world"] != world:
        raise RuntimeError("No matching material preview")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if restore:
        editor.set_level_viewport_camera_info(*state["review_camera"])
        return
    state.setdefault("review_camera", editor.get_level_viewport_camera_info())
    target = unreal.Vector(*state["before"]["traces"][4][0])
    location = unreal.Vector(target.x - 35000, target.y - 50000, target.z + 35000)
    editor.set_level_viewport_camera_info(
        location, unreal.MathLibrary.find_look_at_rotation(location, target)
    )


if __name__ == "__main__":
    main()
