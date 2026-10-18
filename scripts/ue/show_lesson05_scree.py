"""Camera-only close-up of saved Lesson05; no import, cook, or package save."""
import json
import math
from pathlib import Path
import unreal

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
assert world.get_path_name().split(":")[0] == "/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05.L_SaCalobra_Lesson05", world.get_path_name()
# Native Working preview [507,873], stride 8 of the 0.5 m grid.
# Houdini origin (-1771.25, 3144.25) m; scree mask 0.3934420943.
target = (172075.0, 111625.0, 34784.99450683594)
location = (target[0]+500, target[1]-800, target[2]+1800)
delta = [b-a for a,b in zip(location,target)]
rotation = (math.degrees(math.atan2(delta[2], math.hypot(delta[0],delta[1]))), math.degrees(math.atan2(delta[1],delta[0])), 0)
editor.set_level_viewport_camera_info(unreal.Vector(*location), unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]))
actual_location, actual_rotation = editor.get_level_viewport_camera_info()
receipt = {"map": world.get_path_name(), "import": False, "package_save": False,
           "target_cm": target, "camera_cm": [actual_location.x,actual_location.y,actual_location.z],
           "rotation_degrees": [actual_rotation.pitch,actual_rotation.yaw,actual_rotation.roll],
           "native_scree_mask": 0.3934420943260193}
out = Path(unreal.Paths.project_saved_dir()) / "Lesson05ScreeCloseup.json"
out.write_text(json.dumps(receipt,indent=2),encoding="utf-8")
unreal.log("LESSON05_SCREE_CLOSEUP " + json.dumps(receipt))
