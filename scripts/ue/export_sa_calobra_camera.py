"""Read the active editor camera for geographic comparison; change nothing."""

import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world.get_path_name().split(".")[0] != "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004":
    raise RuntimeError("Unexpected world; refuse geographic conversion")
position, rotation = unreal.get_editor_subsystem(
    unreal.LevelEditorSubsystem
).get_level_viewport_camera_info(unreal.Name("None"))
data = {
    "world": world.get_path_name(),
    "position_cm": [position.x, position.y, position.z],
    "rotation_deg": {"pitch": rotation.pitch, "yaw": rotation.yaw, "roll": rotation.roll},
    "origin_epsg25831": [483000.25, 4409516.25],
    "axis": "X east; Y south; Z up",
    "scene_changed": False,
}
out = ROOT / "Saved/RuntimeProof/GeographicCamera"
out.mkdir(parents=True, exist_ok=True)
(out / "camera.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
unreal.log("YACS_GEOGRAPHIC_CAMERA " + json.dumps(data))
