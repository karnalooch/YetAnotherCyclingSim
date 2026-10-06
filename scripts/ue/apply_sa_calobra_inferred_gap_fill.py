"""Fill zero-weight presentation gaps using owner-authorized slope inference."""

import json
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
expected = "/Game/Worlds/SaCalobra/L_SaCalobraMaskDiagnostic_615cb1c66d11"
if world.get_path_name().split(".")[0] != expected:
    raise RuntimeError("Open the current diagnostic map; preserve other user edits")
# Preserve the channel diagnostic exactly as currently inspected before switch.
if not unreal.EditorLoadingAndSavingUtils.save_map(world, expected):
    raise RuntimeError("Diagnostic save failed")
recipe = json.loads(
    (
        ROOT / "worldgen/materials/sa_calobra_surface_presentation_20261005.json"
    ).read_text()
)
source = json.loads(
    (
        ROOT / "worldgen/materials/sa_calobra_surface_presentation_result_20261005.json"
    ).read_text()
)
recipe.update(
    source_map=source["review_map"],
    source_sha256=source["review_map_sha256"],
    inferred_gap_fill={
        "authorization": "Owner explicitly allowed filling black areas from agent inference on 2026-10-05",
        "domain": "Only raw RGB sum zero; gate saturate(1 - 1000 * sumRGB)",
        "rock": "saturate(((1-abs(VertexNormalWS.Z))-0.06)/0.34); more exposed limestone on steeper terrain",
        "grass": "gentle gap fraction * 0.22 * existing decorative macro; mineral remainder",
        "authority": "Artistic presentation fallback, including neutral holdback appearance; not measured cover, source-mask edits or placement permission",
        "geometry_mutation": False,
    },
)
camera = editor.get_level_viewport_camera_info()
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(
    source["review_map"]
):
    raise RuntimeError("Source review did not load")
if camera:
    editor.set_level_viewport_camera_info(*camera)
report = runpy.run_path(
    str(ROOT / "scripts/ue/apply_sa_calobra_generated_surfaces.py")
)["main"](recipe)
path = (
    ROOT
    / "Saved/RuntimeProof/TextureLandscape"
    / report["material"].split("/")[-2]
    / "result.json"
)
verifier = runpy.run_path(
    str(ROOT / "scripts/ue/verify_sa_calobra_generated_surface_map.py")
)
verifier["main"].__globals__["REPORT"] = path
verifier["main"]()
unreal.log("YACS_INFERRED_GAP_FILL_COMPLETE " + str(path))
