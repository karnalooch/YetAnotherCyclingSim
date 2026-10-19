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
    target_node = parent.node(f"{name}_target")
    if not target_node:
        target_node = parent.createNode("null", f"{name}_target")
    target_node.parm("tx").set(target[0])
    target_node.parm("ty").set(target[1])
    target_node.parm("tz").set(target[2])

    cam = parent.node(name)
    if not cam:
        cam = parent.createNode("cam", name)
    cam.parm("tx").set(pos[0])
    cam.parm("ty").set(pos[1])
    cam.parm("tz").set(pos[2])

    # Use native Houdini look-at target
    cam.parm("lookatpath").set(target_node.path())
    cam.parm("focal").set(focal)
    cam.parm("far").set(clip_far)
    cam.parm("near").set(1.0)

    # Verify camera local -Z direction vector points directly at target
    wt = cam.worldTransform()
    rot = wt.extractRotationMatrix3()
    vec_neg_z = hou.Vector3(0, 0, -1) * rot
    aim = (hou.Vector3(target) - hou.Vector3(pos)).normalized()
    dot = float(vec_neg_z.dot(aim))
    print(f"  Camera {name}: local -Z alignment dot={dot:.8f}", flush=True)
    assert dot > 0.999, f"Camera {name} local -Z not aligned to target (dot={dot})"

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

    # Responsive Preview Resample node for fluid interactive 60 FPS viewport navigation
    # Resamples 16000x16000 (0.5m) to 2000x2000 (4.0m) preserving all 14 heightfield volume layers
    prev_resample = net.node("PREVIEW_RESAMPLE")
    if not prev_resample:
        prev_resample = net.createNode("heightfield_resample", "PREVIEW_RESAMPLE")
    prev_resample.setInput(0, final_cache_node)
    prev_resample.parm("divisionmode").set(0)  # By scale
    prev_resample.parm("resscale").set(0.125)  # 2000x2000
    prev_resample.setColor(hou.Color((0.3, 0.5, 0.8)))

    # Mode 1: PREVIEW_GLOBAL_COLOR
    # Native 3D terrain with global RGB volumes.
    prev_color = net.node("PREVIEW_GLOBAL_COLOR")
    if not prev_color:
        prev_color = net.createNode("null", "PREVIEW_GLOBAL_COLOR")
    prev_color.setInput(0, prev_resample)
    prev_color.setColor(hou.Color((0.2, 0.7, 0.3)))

    # Mode 2: PREVIEW_NEUTRAL_SHADING
    # Neutral geometry clay visualization via uniform RGB volume
    prev_neutral = net.node("PREVIEW_NEUTRAL_SHADING")
    if not prev_neutral or prev_neutral.type().name() != "python":
        if prev_neutral:
            prev_neutral.destroy()
        prev_neutral = net.createNode("python", "PREVIEW_NEUTRAL_SHADING")
    prev_neutral.setInput(0, prev_resample)
    code_neutral = """import numpy as np
geo = hou.pwd().geometry()
r_p = [p for p in geo.prims() if p.attribValue('name') == 'r'][0]
g_p = [p for p in geo.prims() if p.attribValue('name') == 'g'][0]
b_p = [p for p in geo.prims() if p.attribValue('name') == 'b'][0]
n = r_p.resolution()[0] * r_p.resolution()[1]
grey = tuple([0.55] * n)
r_p.setAllVoxels(grey)
g_p.setAllVoxels(grey)
b_p.setAllVoxels(grey)
"""
    prev_neutral.parm("python").set(code_neutral)
    prev_neutral.setColor(hou.Color((0.6, 0.6, 0.6)))

    # Mode 3: PREVIEW_IDMAP
    # Colorized 5-class IDMap visualization via direct RGB volume mapping
    # grass: dark green, grass 2: yellow-green, sand: golden sand, cliffs: slate brown, scree: limestone grey/white
    prev_idmap = net.node("PREVIEW_IDMAP")
    if not prev_idmap or prev_idmap.type().name() != "python":
        if prev_idmap:
            prev_idmap.destroy()
        prev_idmap = net.createNode("python", "PREVIEW_IDMAP")
    prev_idmap.setInput(0, prev_resample)
    code_idmap = """import numpy as np
geo = hou.pwd().geometry()
id_p = [p for p in geo.prims() if p.attribValue('name') == 'id'][0]
r_p = [p for p in geo.prims() if p.attribValue('name') == 'r'][0]
g_p = [p for p in geo.prims() if p.attribValue('name') == 'g'][0]
b_p = [p for p in geo.prims() if p.attribValue('name') == 'b'][0]

id_arr = np.array(id_p.allVoxels())
r = np.zeros_like(id_arr)
g = np.zeros_like(id_arr)
b = np.zeros_like(id_arr)

m0 = id_arr <= 0.125
r[m0] = 64/255.0; g[m0] = 140/255.0; b[m0] = 38/255.0

m1 = (id_arr > 0.125) & (id_arr <= 0.375)
r[m1] = 217/255.0; g[m1] = 217/255.0; b[m1] = 38/255.0

m2 = (id_arr > 0.375) & (id_arr <= 0.625)
r[m2] = 230/255.0; g[m2] = 191/255.0; b[m2] = 115/255.0

m3 = (id_arr > 0.625) & (id_arr <= 0.875)
r[m3] = 102/255.0; g[m3] = 89/255.0; b[m3] = 77/255.0

m4 = id_arr > 0.875
r[m4] = 1.0; g[m4] = 1.0; b[m4] = 1.0

r_p.setAllVoxels(tuple(r))
g_p.setAllVoxels(tuple(g))
b_p.setAllVoxels(tuple(b))
"""
    prev_idmap.parm("python").set(code_idmap)
    prev_idmap.setColor(hou.Color((0.9, 0.6, 0.2)))

    # Mode 4: PREVIEW_CLASS_ISOLATION
    # Uses existing PE_Heightfield_id_to_layer node to extract scree to mask
    id_to_layer = net.node("ID_TO_LAYER")
    if not id_to_layer:
        id_to_layer = net.createNode("PE_Heightfield_id_to_layer", "ID_TO_LAYER")
    id_to_layer.setInput(0, prev_resample)
    id_to_layer.parm("srcname1").set("id")
    id_to_layer.parm("dstname1").set("mask")

    prev_iso = net.node("PREVIEW_CLASS_ISOLATION")
    if not prev_iso or prev_iso.type().name() != "python":
        if prev_iso:
            prev_iso.destroy()
        prev_iso = net.createNode("python", "PREVIEW_CLASS_ISOLATION")
    prev_iso.setInput(0, id_to_layer)
    code_iso = """import numpy as np
geo = hou.pwd().geometry()
mask_p = [p for p in geo.prims() if p.attribValue('name') == 'mask'][0]
r_p = [p for p in geo.prims() if p.attribValue('name') == 'r'][0]
g_p = [p for p in geo.prims() if p.attribValue('name') == 'g'][0]
b_p = [p for p in geo.prims() if p.attribValue('name') == 'b'][0]

m_arr = np.array(mask_p.allVoxels())
r = np.full_like(m_arr, 0.2)
g = np.full_like(m_arr, 0.2)
b = np.full_like(m_arr, 0.2)

iso = m_arr > 0.05
r[iso] = 0.95
g[iso] = 0.10
b[iso] = 0.10

r_p.setAllVoxels(tuple(r))
g_p.setAllVoxels(tuple(g))
b_p.setAllVoxels(tuple(b))
"""
    prev_iso.parm("python").set(code_iso)
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
