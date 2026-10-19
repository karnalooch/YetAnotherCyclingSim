"""Setup Lesson 07 Unified Houdini Checkpoint, Preview Nodes, Cameras, and Export Graph.

Follows SideFX Project Pegasus Landscape Workflow Lesson 7 ("Material Setup") exactly:
- Checkpoint: SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc (Save As from L06)
- 4 Preview modes connected to FINAL_CACHE
- 5 Verified Camera Bookmarks in /obj
- Procedural Delta calculation: final_height - stage1_base_height
- IDMap export branch: HeightField Output, 8b fixed, single channel, id layer
- Global Color export branch: HeightField RGB ColorSpace (Linear->sRGB), @height=0, HeightField Output RGB
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

# Set Houdini environment overrides
os.environ["HOUDINI_COP_MAXRES"] = "32768"
os.environ["HOUDINI_OCL_DEVICETYPE"] = "CPU"

import hou

PROJECT_DIR = Path("D:/yacs/project").resolve()
WORLD_DIR = PROJECT_DIR / "worldgen/houdini/sa_calobra"
WORK_DIR = Path("D:/yacs/work/lesson07-unified-20261019").resolve()
WORK_DIR.mkdir(parents=True, exist_ok=True)

L06_HIP = WORLD_DIR / "SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc"
L07_HIP = WORLD_DIR / "SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc"

STAGE1_BASE = Path("D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc").resolve()
FINAL_CACHE = Path("D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc").resolve()
PROCEDURAL_DETAIL_CACHE = WORK_DIR / "procedural_detail.bgeo.sc"
IDMAP_PNG = WORK_DIR / "T_PE_Terrain_IDMap.png"
COLOR_PNG = WORK_DIR / "T_PE_Terrain_Color.png"


def compute_lookat_rotations(pos: tuple[float, float, float], target: tuple[float, float, float]) -> tuple[float, float, float]:
    """Compute Houdini rx, ry, rz Euler angles (in degrees, order XYZ) to aim camera from pos to target."""
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    dz = target[2] - pos[2]
    dist_xz = math.sqrt(dx * dx + dz * dz)

    # In Houdini camera space: pointing down -Z axis
    # Pitch (rx): rotation around X
    rx = -math.degrees(math.atan2(dy, dist_xz))
    # Yaw (ry): rotation around Y
    ry = math.degrees(math.atan2(dx, -dz))
    rz = 0.0
    return (rx, ry, rz)


def create_or_update_cam(parent: hou.Node, name: str, pos: tuple[float, float, float], target: tuple[float, float, float], focal: float = 35.0, clip_far: float = 25000.0) -> hou.Node:
    cam = parent.node(name)
    if not cam:
        cam = parent.createNode("cam", name)
    cam.parm("tx").set(pos[0])
    cam.parm("ty").set(pos[1])
    cam.parm("tz").set(pos[2])

    rx, ry, rz = compute_lookat_rotations(pos, target)
    cam.parm("rx").set(rx)
    cam.parm("ry").set(ry)
    cam.parm("rz").set(rz)

    cam.parm("focal").set(focal)
    cam.parm("far").set(clip_far)
    cam.parm("near").set(1.0)
    return cam


def main():
    print(f"Loading L06 Checkpoint: {L06_HIP}...", flush=True)
    hou.hipFile.load(str(L06_HIP), suppress_save_prompt=True)

    # Install required HDAs
    hdas_to_install = [
        WORLD_DIR / "otls/sop_PE_heightfield_material.1.0.hda",
        WORLD_DIR / "otls/sop_PE_heightfield_tint.1.0.hda",
        WORLD_DIR / "otls/sop_PE_Heightfield_Layers_to_ID.2.0.hda",
        WORLD_DIR / "otls/lesson06_reviewed/sop_PE_heightield_idmap_layers.hda",
        WORLD_DIR / "otls/lesson06_reviewed/sop_PE_Heightfield_id_to_layer.hda",
        WORLD_DIR / "otls/sop_PE_heightfield_RGB_ColorSpace.1.0.hda",
    ]
    for hda in hdas_to_install:
        if hda.exists():
            print(f"Installing HDA: {hda.name}...", flush=True)
            hou.hda.installFile(str(hda), force_use_assets=True)

    net = hou.node("/obj/SA_CALOBRA_UNIFIED")
    if not net:
        raise RuntimeError("Network /obj/SA_CALOBRA_UNIFIED not found")

    final_cache_node = net.node("FINAL_CACHE")
    if not final_cache_node:
        raise RuntimeError("FINAL_CACHE node not found")

    # -------------------------------------------------------------
    # 1. SETUP PREVIEW MODES
    # -------------------------------------------------------------
    print("Setting up 4 Preview modes...", flush=True)

    # Mode 1: PREVIEW_GLOBAL_COLOR
    # Native 3D terrain with global RGB volumes.
    # We clean any overriding shop_materialpath attribute or visualizer tint
    prev_color = net.node("PREVIEW_GLOBAL_COLOR")
    if not prev_color:
        prev_color = net.createNode("null", "PREVIEW_GLOBAL_COLOR")
    prev_color.setInput(0, final_cache_node)
    prev_color.setColor(hou.Color((0.2, 0.7, 0.3)))

    # Mode 2: PREVIEW_NEUTRAL_SHADING
    # Neutral geometry clay visualization
    prev_neutral = net.node("PREVIEW_NEUTRAL_SHADING")
    if not prev_neutral:
        prev_neutral = net.createNode("heightfield_visualize", "PREVIEW_NEUTRAL_SHADING")
    prev_neutral.setInput(0, final_cache_node)
    prev_neutral.parm("updatetinting").set(1)
    prev_neutral.parm("cdrampmode").set("clamp")
    # Set ramp to uniform neutral grey
    ramp_grey = hou.Ramp(
        [hou.rampBasis.Linear, hou.rampBasis.Linear],
        [0.0, 1.0],
        [hou.Vector3(0.55, 0.55, 0.55), hou.Vector3(0.55, 0.55, 0.55)]
    )
    prev_neutral.parm("cdramp").set(ramp_grey)
    prev_neutral.parm("updatematerial").set(0)
    prev_neutral.setColor(hou.Color((0.6, 0.6, 0.6)))

    # Mode 3: PREVIEW_IDMAP
    # Colorized 5-class IDMap visualization
    # grass: dark green, grass 2: yellow-green, sand: golden sand, cliffs: slate brown, scree: limestone grey/white
    prev_idmap = net.node("PREVIEW_IDMAP")
    if not prev_idmap:
        prev_idmap = net.createNode("heightfield_visualize", "PREVIEW_IDMAP")
    prev_idmap.setInput(0, final_cache_node)
    prev_idmap.parm("updatetinting").set(1)
    prev_idmap.parm("cdvolume").set("id")
    prev_idmap.parm("cdrangeoverride").set(1)
    prev_idmap.parm("cdrange1").set(0.0)
    prev_idmap.parm("cdrange2").set(1.0)
    prev_idmap.parm("cdrampmode").set("clamp")
    # 5 discrete class steps
    ramp_id = hou.Ramp(
        [hou.rampBasis.Constant, hou.rampBasis.Constant, hou.rampBasis.Constant, hou.rampBasis.Constant, hou.rampBasis.Constant],
        [0.0, 64.0 / 255.0, 128.0 / 255.0, 191.0 / 255.0, 1.0],
        [
            hou.Vector3(64/255, 140/255, 38/255),    # grass (green)
            hou.Vector3(217/255, 217/255, 38/255),  # grass 2 (olive/tundra)
            hou.Vector3(230/255, 191/255, 115/255), # sand (golden)
            hou.Vector3(102/255, 89/255, 77/255),   # cliffs (rock brown)
            hou.Vector3(255/255, 255/255, 255/255)  # scree (white/limestone)
        ]
    )
    prev_idmap.parm("cdramp").set(ramp_id)
    prev_idmap.parm("updatematerial").set(0)
    prev_idmap.setColor(hou.Color((0.9, 0.6, 0.2)))

    # Mode 4: PREVIEW_CLASS_ISOLATION
    # Uses existing PE_Heightfield_id_to_layer node
    id_to_layer = net.node("ID_TO_LAYER")
    if not id_to_layer:
        id_to_layer = net.createNode("PE_Heightfield_id_to_layer", "ID_TO_LAYER")
    id_to_layer.setInput(0, final_cache_node)
    id_to_layer.parm("srcname1").set("id")
    id_to_layer.parm("dstname1").set("mask")

    prev_iso = net.node("PREVIEW_CLASS_ISOLATION")
    if not prev_iso:
        prev_iso = net.createNode("heightfield_visualize", "PREVIEW_CLASS_ISOLATION")
    prev_iso.setInput(0, id_to_layer)
    prev_iso.parm("updatetinting").set(1)
    prev_iso.parm("cdvolume").set("mask")
    prev_iso.parm("cdrangeoverride").set(1)
    prev_iso.parm("cdrange1").set(0.0)
    prev_iso.parm("cdrange2").set(1.0)
    prev_iso.parm("cdrampmode").set("clamp")
    ramp_iso = hou.Ramp(
        [hou.rampBasis.Linear, hou.rampBasis.Linear],
        [0.0, 1.0],
        [hou.Vector3(0.05, 0.05, 0.05), hou.Vector3(0.95, 0.1, 0.1)] # Dark to vivid red
    )
    prev_iso.parm("cdramp").set(ramp_iso)
    prev_iso.setColor(hou.Color((0.8, 0.2, 0.2)))

    # Set default display and selection flag to Mode 1 (PREVIEW_GLOBAL_COLOR)
    prev_color.setDisplayFlag(True)
    prev_color.setRenderFlag(True)
    prev_color.setSelected(True, clear_all_selected=True)

    # -------------------------------------------------------------
    # 2. SETUP CAMERAS IN /obj
    # -------------------------------------------------------------
    print("Setting up 5 verified Camera Bookmarks in /obj...", flush=True)
    obj = hou.node("/obj")
    
    # Cam 1: Panorama (Whole domain overview looking South-East towards Puig Major)
    create_or_update_cam(
        obj, "cam_panorama",
        pos=(-4500.0, 4200.0, -5000.0),
        target=(0.0, 400.0, 0.0),
        focal=28.0,
        clip_far=35000.0
    )

    # Cam 2: Puig Major (Peak summit at X=-1283.75, Y=1437.16, Z=3495.25)
    create_or_update_cam(
        obj, "cam_puig_major",
        pos=(-2800.0, 2200.0, 1800.0),
        target=(-1283.75, 1437.16, 3495.25),
        focal=45.0,
        clip_far=20000.0
    )

    # Cam 3: Sa Calobra Cove (Beach at X=470.0, Y=10.34, Z=-1060.0)
    create_or_update_cam(
        obj, "cam_sa_calobra_cove",
        pos=(-200.0, 450.0, -1800.0),
        target=(470.0, 10.34, -1060.0),
        focal=35.0,
        clip_far=10000.0
    )

    # Cam 4: Transition Grass/Sand/Cliffs (Coastal transition zone)
    create_or_update_cam(
        obj, "cam_transition",
        pos=(150.0, 350.0, -1450.0),
        target=(380.0, 45.0, -1120.0),
        focal=40.0,
        clip_far=10000.0
    )

    # Cam 5: Scree Site (Centroid at X=-1260.25, Y=445.08, Z=262.25)
    create_or_update_cam(
        obj, "cam_scree_site",
        pos=(-1450.0, 580.0, 100.0),
        target=(-1260.25, 445.08, 262.25),
        focal=50.0,
        clip_far=5000.0
    )

    # -------------------------------------------------------------
    # 3. SETUP PROCEDURAL DELTA BRANCH (ETAP B)
    # -------------------------------------------------------------
    print("Setting up Procedural Delta branch...", flush=True)
    base_file = net.node("STAGE1_BASE_CACHE")
    if not base_file:
        base_file = net.createNode("file", "STAGE1_BASE_CACHE")
    base_file.parm("file").set(str(STAGE1_BASE).replace("\\", "/"))
    base_file.parm("missingframe").set(1)

    delta_layer = net.node("PROCEDURAL_DELTA_DIFF")
    if not delta_layer:
        delta_layer = net.createNode("heightfield_layer", "PROCEDURAL_DELTA_DIFF")
    delta_layer.setInput(0, final_cache_node)
    delta_layer.setInput(1, base_file)
    delta_layer.parm("layer").set("height")
    delta_layer.parm("mode").set("subtract")  # Input 1 - Input 2 = final - base

    # Isolate height volume only for storage efficiency
    delta_isolate = net.node("PROCEDURAL_DELTA_ISOLATE")
    if not delta_isolate:
        delta_isolate = net.createNode("heightfield_isolatelayer", "PROCEDURAL_DELTA_ISOLATE")
    delta_isolate.setInput(0, delta_layer)
    delta_isolate.parm("layer").set("height")

    delta_cache = net.node("PROCEDURAL_DELTA_OUT")
    if not delta_cache:
        delta_cache = net.createNode("file", "PROCEDURAL_DELTA_OUT")
    delta_cache.setInput(0, delta_isolate)
    delta_cache.parm("file").set(str(PROCEDURAL_DETAIL_CACHE).replace("\\", "/"))
    delta_cache.parm("filemode").set(2)  # Write files

    # -------------------------------------------------------------
    # 4. SETUP IDMAP EXPORT BRANCH (ETAP D)
    # -------------------------------------------------------------
    print("Setting up IDMap Export branch...", flush=True)
    out_idmap = net.node("EXPORT_IDMAP")
    if not out_idmap:
        out_idmap = net.createNode("heightfield_output", "EXPORT_IDMAP")
    out_idmap.setInput(0, final_cache_node)
    out_idmap.parm("output").set(str(IDMAP_PNG).replace("\\", "/"))
    out_idmap.parm("out_type").set("packed")
    out_idmap.parm("out_format").set("single")
    out_idmap.parm("red_channel").set("id")
    out_idmap.parm("red_out_range").set("none")

    # -------------------------------------------------------------
    # 5. SETUP GLOBAL COLOR EXPORT BRANCH (ETAP E)
    # -------------------------------------------------------------
    print("Setting up Global Color Export branch...", flush=True)
    color_srgb = net.node("COLOR_COLORSPACE_SRGB")
    if not color_srgb:
        color_srgb = net.createNode("heightfield_rgb_colorspace::1.0", "COLOR_COLORSPACE_SRGB")
    color_srgb.setInput(0, final_cache_node)
    color_srgb.parm("input").set(0)  # Linear to sRGB

    color_flatten = net.node("COLOR_FLATTEN_HEIGHT")
    if not color_flatten:
        color_flatten = net.createNode("volumewrangle", "COLOR_FLATTEN_HEIGHT")
    color_flatten.setInput(0, color_srgb)
    color_flatten.parm("snippet").set("@height = 0.0;")

    out_color = net.node("EXPORT_GLOBAL_COLOR")
    if not out_color:
        out_color = net.createNode("heightfield_output", "EXPORT_GLOBAL_COLOR")
    out_color.setInput(0, color_flatten)
    out_color.parm("output").set(str(COLOR_PNG).replace("\\", "/"))
    out_color.parm("out_type").set("packed")
    out_color.parm("out_format").set("rgb")
    out_color.parm("red_channel").set("r")
    out_color.parm("green_channel").set("g")
    out_color.parm("blue_channel").set("b")
    out_color.parm("red_out_range").set("none")
    out_color.parm("green_out_range").set("none")
    out_color.parm("blue_out_range").set("none")

    # Layout nodes neatly
    net.layoutChildren()

    # Save checkpoint HIP
    print(f"Saving L07 Checkpoint to: {L07_HIP}...", flush=True)
    hou.hipFile.save(str(L07_HIP))
    print("[ok] SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc saved successfully!", flush=True)


if __name__ == "__main__":
    main()
