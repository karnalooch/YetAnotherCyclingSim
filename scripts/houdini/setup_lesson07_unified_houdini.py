"""Resume Lesson 07 and repair its display-only branches on the retained cache.

Initial setup is explicit and refuses to overwrite an existing L07 checkpoint.
The export recipe follows SideFX Project Pegasus Landscape Workflow Lesson 7;
the diagnostic cameras and preview crops are YACS adaptations:
- Checkpoint: SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc (Save As from L06)
- 4 Preview modes connected to FINAL_CACHE with authentic native display mechanisms
- 5 Verified Camera Bookmarks in /obj
- Dedicated full-resolution Scree isolation and closeup
- Procedural Delta calculation: final_height - stage1_base_height
- IDMap export branch: HeightField Output, 8b fixed, single channel, id layer
- Global Color export branch: HeightField RGB ColorSpace (Linear->sRGB), @height=0, HeightField Output RGB
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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


def initialize_from_lesson06():
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
    print("Setting up 4 Preview modes with verified native mechanisms...", flush=True)

    # Responsive Preview Resample node for fluid interactive viewport navigation
    # Resamples 16000x16000 (0.5m) to 2000x2000 (4.0m) preserving all layers
    # Uses filter=point to preserve categorical discrete class IDs without linear blur
    prev_resample = net.node("PREVIEW_RESAMPLE")
    if not prev_resample:
        prev_resample = net.createNode("heightfield_resample", "PREVIEW_RESAMPLE")
    prev_resample.setInput(0, final_cache_node)
    prev_resample.parm("divisionmode").set(0)  # By scale
    prev_resample.parm("resscale").set(0.125)  # 2000x2000
    prev_resample.parm("filter").set("point")  # Nearest-neighbor categorical sampling
    prev_resample.setColor(hou.Color((0.3, 0.5, 0.8)))

    # Mode 1: PREVIEW_GLOBAL_COLOR
    # Native 3D terrain with global RGB volumes.
    # We delete detail attribute 'volvis' so Houdini's native HeightField shader
    # renders the authentic r, g, b color volumes directly!
    prev_color = net.node("PREVIEW_GLOBAL_COLOR")
    if prev_color and prev_color.type().name() != "attribdelete":
        prev_color.destroy()
        prev_color = None
    if not prev_color:
        prev_color = net.createNode("attribdelete", "PREVIEW_GLOBAL_COLOR")
    prev_color.setInput(0, prev_resample)
    prev_color.parm("dtldel").set("volvis")
    prev_color.setColor(hou.Color((0.2, 0.7, 0.3)))

    # Mode 2: PREVIEW_NEUTRAL_SHADING
    # Pure clay neutral shading: isolate height layer, delete volvis and color layers
    iso_neutral = net.node("PREVIEW_NEUTRAL_ISO")
    if not iso_neutral:
        iso_neutral = net.createNode("heightfield_isolatelayer", "PREVIEW_NEUTRAL_ISO")
    iso_neutral.setInput(0, prev_resample)
    iso_neutral.parm("layer").set("height")

    prev_neutral = net.node("PREVIEW_NEUTRAL_SHADING")
    if prev_neutral and prev_neutral.type().name() != "attribdelete":
        prev_neutral.destroy()
        prev_neutral = None
    if not prev_neutral:
        prev_neutral = net.createNode("attribdelete", "PREVIEW_NEUTRAL_SHADING")
    prev_neutral.setInput(0, iso_neutral)
    prev_neutral.parm("dtldel").set("volvis")
    prev_neutral.setColor(hou.Color((0.6, 0.6, 0.6)))

    # Mode 3: PREVIEW_IDMAP
    # Native discrete 5-class Pegasus IDMap palette visualization via heightfield_visualize
    prev_idmap = net.node("PREVIEW_IDMAP")
    if prev_idmap and prev_idmap.type().name() != "heightfield_visualize":
        prev_idmap.destroy()
        prev_idmap = None
    if not prev_idmap:
        prev_idmap = net.createNode("heightfield_visualize", "PREVIEW_IDMAP")
    prev_idmap.setInput(0, prev_resample)
    prev_idmap.parm("cdvolume").set("id")
    keys = (0.0, 0.125, 0.375, 0.625, 0.875)
    values = (
        (64 / 255.0, 140 / 255.0, 38 / 255.0),    # grass (0.0)
        (217 / 255.0, 217 / 255.0, 38 / 255.0),  # grass 2 (0.25)
        (230 / 255.0, 191 / 255.0, 115 / 255.0), # sand (0.50)
        (102 / 255.0, 89 / 255.0, 77 / 255.0),   # cliffs (0.75)
        (1.0, 1.0, 1.0)                          # scree (1.0)
    )
    basis = (hou.rampBasis.Constant,) * 5
    ramp_idmap = hou.Ramp(basis, keys, values)
    prev_idmap.parm("cdramp").set(ramp_idmap)
    prev_idmap.parm("cdrange1").set(0.0)
    prev_idmap.parm("cdrange2").set(1.0)
    prev_idmap.setColor(hou.Color((0.9, 0.6, 0.2)))

    # Mode 4: PREVIEW_CLASS_ISOLATION
    # Uses PE_Heightfield_id_to_layer node to extract scree to mask
    id_to_layer = net.node("ID_TO_LAYER")
    if not id_to_layer:
        id_to_layer = net.createNode("PE_Heightfield_id_to_layer", "ID_TO_LAYER")
    id_to_layer.setInput(0, prev_resample)
    id_to_layer.parm("srcname1").set("id")
    id_to_layer.parm("dstname1").set("mask")
    id_to_layer.parm("id_layer").set("255")  # Explicitly Scree discrete ID 255

    prev_iso = net.node("PREVIEW_CLASS_ISOLATION")
    if prev_iso and prev_iso.type().name() != "heightfield_visualize":
        prev_iso.destroy()
        prev_iso = None
    if not prev_iso:
        prev_iso = net.createNode("heightfield_visualize", "PREVIEW_CLASS_ISOLATION")
    prev_iso.setInput(0, id_to_layer)
    prev_iso.parm("cdvolume").set("mask")
    ramp_iso = hou.Ramp((hou.rampBasis.Linear, hou.rampBasis.Linear), (0.0, 1.0), ((0.7, 0.7, 0.7), (1.0, 0.0, 0.0)))
    prev_iso.parm("cdramp").set(ramp_iso)
    prev_iso.parm("cdrange1").set(0.0)
    prev_iso.parm("cdrange2").set(1.0)
    prev_iso.setColor(hou.Color((0.8, 0.2, 0.2)))

    # Full resolution Scree isolation node for bit-exact full-resolution verification
    id_to_layer_full = net.node("ID_TO_LAYER_FULLRES")
    if not id_to_layer_full:
        id_to_layer_full = net.createNode("PE_Heightfield_id_to_layer", "ID_TO_LAYER_FULLRES")
    id_to_layer_full.setInput(0, final_cache_node)
    id_to_layer_full.parm("srcname1").set("id")
    id_to_layer_full.parm("dstname1").set("mask")
    id_to_layer_full.parm("id_layer").set("255")

    scree_fullres = net.node("SCREE_FULLRES_PREVIEW")
    if not scree_fullres:
        scree_fullres = net.createNode("heightfield_visualize", "SCREE_FULLRES_PREVIEW")
    scree_fullres.setInput(0, id_to_layer_full)
    scree_fullres.parm("cdvolume").set("mask")
    scree_fullres.parm("cdramp").set(ramp_iso)
    scree_fullres.parm("cdrange1").set(0.0)
    scree_fullres.parm("cdrange2").set(1.0)
    scree_fullres.setColor(hou.Color((0.9, 0.1, 0.1)))

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
        pos=(-2783.75, 1800.0, 1995.25),
        target=(-1283.75, 1437.16, 3495.25),
        focal=45.0,
        clip_far=20000.0
    )

    # Cam 3: Sa Calobra Cove (Beach at X=470.0, Y=10.34, Z=-1060.0, camera elevated over bay looking into cove)
    create_or_update_cam(
        obj, "cam_sa_calobra_cove",
        pos=(470.0, 160.0, -1800.0),
        target=(470.0, 10.34, -1060.0),
        focal=35.0,
        clip_far=10000.0
    )

    # Cam 4: Transition Grass/Sand/Cliffs
    create_or_update_cam(
        obj, "cam_transition",
        pos=(-2480.0, 500.0, 1800.0),
        target=(-2495.0, 460.0, 1840.0),
        focal=40.0,
        clip_far=10000.0
    )

    # Cam 5: Scree Site (Cluster 1 centroid at X=-2502.78, Y=460.95, Z=1845.95)
    create_or_update_cam(
        obj, "cam_scree_site",
        pos=(-2550.0, 520.0, 1780.0),
        target=(-2502.78, 460.95, 1845.95),
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
    delta_layer.parm("mode").set("subtract")

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
    delta_cache.parm("filemode").set(2)

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
    color_srgb.parm("input").set(0)

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

    net.layoutChildren()

    print(f"Saving L07 Checkpoint to: {L07_HIP}...", flush=True)
    hou.hipFile.save(str(L07_HIP))
    print("[ok] SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc saved successfully!", flush=True)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def repair_previews():
    """Resume L07 and change only display branches/cameras, never the producer."""
    import numpy as np
    from PIL import Image

    expected_cache = "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
    expected_idmap = "cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3"
    if digest(FINAL_CACHE) != expected_cache or digest(IDMAP_PNG) != expected_idmap:
        raise RuntimeError("L06 cache / L07 IDMap changed; review source identity first")
    old_hip_sha = digest(L07_HIP)
    base_hip_sha = digest(L06_HIP)
    backup = WORK_DIR / "checkpoints" / f"{L07_HIP.stem}-{old_hip_sha}.hiplc"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(L07_HIP, backup)
    if digest(backup) != old_hip_sha:
        raise RuntimeError("L07 backup does not match the checkpoint")

    hou.hipFile.load(str(L07_HIP), suppress_save_prompt=True)
    net = hou.node("/obj/SA_CALOBRA_UNIFIED")
    final = net.node("FINAL_CACHE")
    if final.type().name() != "file" or final.inputs():
        raise RuntimeError("FINAL_CACHE must read the retained file without upstream cooking")
    if Path(final.parm("file").eval()).resolve() != FINAL_CACHE:
        raise RuntimeError("HIP uses a different FINAL_CACHE")

    def visualize(name, source, field, ramp=None):
        node = net.node(name)
        if node and node.type().name() != "heightfield_visualize":
            node = node.changeNodeType(
                "heightfield_visualize", keep_parms=False, keep_network_contents=False,
            )
        if node is None:
            node = net.createNode("heightfield_visualize", name)
        node.matchCurrentDefinition()
        node.setInput(0, source)
        # Houdini 22 defaults are unchanged tint + an elevation material.
        # Explicit native tinting is necessary for RGB and categorical displays.
        node.setParms({
            "updatetinting": "custom", "updatematerial": "none",
            "heightvolume": "height", "cdvolume": field,
            "cdrangeoverride": 1, "cdrange1": 0.0, "cdrange2": 1.0,
            "cdrampmode": "clamp" if ramp is not None else "none",
        })
        if ramp is not None:
            node.parm("cdramp").set(ramp)
        return node

    overview = net.node("PREVIEW_RESAMPLE")
    color = visualize("PREVIEW_GLOBAL_COLOR", overview, "r g b")
    palette = net.node("PREVIEW_IDMAP").parm("cdramp").eval()
    visualize("PREVIEW_IDMAP", overview, "id", palette)
    isolation = hou.Ramp(
        (hou.rampBasis.Linear,) * 2, (0.0, 1.0),
        ((0.7, 0.7, 0.7), (1.0, 0.0, 0.0)),
    )
    visualize("PREVIEW_CLASS_ISOLATION", net.node("ID_TO_LAYER"), "mask", isolation)

    # Select an actual encoded texel in the densest 32 m diagnostic neighbourhood.
    # A centroid need not belong to the class. This only selects the camera;
    # neither the mask nor the terrain is changed.
    Image.MAX_IMAGE_PIXELS = None  # This pinned 16000² local export is expected.
    with Image.open(IDMAP_PNG) as image:
        ids = np.asarray(image)
        if ids.shape != (16000, 16000) or ids.dtype != np.uint8:
            raise RuntimeError("Unexpected pinned IDMap encoding")
        rows, cols = np.where(ids == 255)
    if not len(rows):
        raise RuntimeError("Pinned IDMap has no Scree texels")
    distance_squared = (
        (cols[:, None] - cols[None, :]) ** 2 + (rows[:, None] - rows[None, :]) ** 2
    )
    nearby_counts = np.count_nonzero(distance_squared <= 64 ** 2, axis=1)
    selected = int(np.argmax(nearby_counts))
    png_xy = (int(cols[selected]), int(rows[selected]))
    voxel = (png_xy[0], 15999 - png_xy[1], 0)
    geo = final.geometry()
    volumes = {p.attribValue("name"): p for p in geo.prims() if isinstance(p, hou.Volume)}
    if volumes["id"].resolution() != (16000, 16000, 1):
        raise RuntimeError("Unexpected source resolution")
    source_id = float(volumes["id"].voxel(voxel))
    if abs(source_id - 1.0) > 1e-6 or volumes["Alpha"].voxel(voxel) <= 0:
        raise RuntimeError("PNG Scree site does not match valid native source data")
    pos = volumes["height"].indexToPos(voxel)
    target = (float(pos[0]), float(volumes["height"].voxel(voxel)), float(pos[2]))
    expected_xz = (-3999.75 + png_xy[0] * 0.5, -3999.75 + png_xy[1] * 0.5)
    if max(abs(target[0] - expected_xz[0]), abs(target[2] - expected_xz[1])) > 0.0005:
        raise RuntimeError("PNG/native orientation or sample centers differ")

    # Native crop preserves 0.5 m samples. The 4 m overview can miss rare Scree.
    crop = net.node("SCREE_SITE_CROP") or net.createNode("heightfield_crop", "SCREE_SITE_CROP")
    crop.setInput(0, final)
    crop.setParms({
        "cropmode": "intersect", "orient": "zx", "sizex": 128.0, "sizey": 128.0,
        "tx": target[0], "ty": 0.0, "tz": target[2],
    })
    decoder = net.node("ID_TO_LAYER_FULLRES")
    decoder.setInput(0, crop)
    decoder.setParms({"srcname1": "id", "dstname1": "mask", "id_layer": "255"})
    local_iso = visualize("SCREE_FULLRES_PREVIEW", decoder, "mask", isolation)
    visualize("SCREE_SITE_GLOBAL_COLOR", crop, "r g b")
    crop_geo = decoder.geometry()
    crop_vols = {p.attribValue("name"): p for p in crop_geo.prims() if isinstance(p, hou.Volume)}
    decoded = np.frombuffer(crop_vols["mask"].allVoxelsAsString(), dtype=np.float32)
    local_ids = np.frombuffer(crop_vols["id"].allVoxelsAsString(), dtype=np.float32)
    expected = np.isclose(local_ids, 1.0, atol=1e-6)
    mismatches = int(np.count_nonzero((decoded > 0.5) != expected))
    count = int(np.count_nonzero(expected))
    if not count or mismatches:
        raise RuntimeError(f"Native Scree decoder failed: count={count}, mismatches={mismatches}")

    # The witness can lie below a steep neighbouring cliff. Place the camera
    # above the entire diagnostic crop, not just above the target's elevation.
    crop_max_height = float(max(crop_vols["height"].allVoxels()))
    cam_x, cam_z = target[0], target[2] - 0.5
    create_or_update_cam(
        hou.node("/obj"), "cam_scree_site",
        (cam_x, crop_max_height + 80.0, cam_z),
        target, focal=85.0, clip_far=5000.0,
    )
    color.setDisplayFlag(True)
    color.setRenderFlag(True)
    for node in hou.selectedNodes():
        node.setSelected(False)
    if local_iso.errors() or crop.errors():
        raise RuntimeError(str(local_iso.errors() + crop.errors()))
    # Check the cooked native attributes, not just setters. Converting a node
    # while retaining its old internal network can silently pass the input through.
    cooked_fields = {}
    preview_names = {
        "PREVIEW_GLOBAL_COLOR": "r g b", "PREVIEW_IDMAP": "id",
        "PREVIEW_CLASS_ISOLATION": "mask", "SCREE_FULLRES_PREVIEW": "mask",
        "SCREE_SITE_GLOBAL_COLOR": "r g b",
    }
    for name, expected_field in preview_names.items():
        settings = net.node(name).geometry().attribValue("volvis")
        if settings.get("cdfield") != expected_field:
            raise RuntimeError(f"{name} cooked the wrong color field: {settings}")
        if expected_field == "r g b" and settings.get("cdramp"):
            raise RuntimeError(f"{name} still applies an inherited categorical ramp")
        cooked_fields[name] = expected_field
    hou.hipFile.save(str(L07_HIP))
    new_hip_sha = digest(L07_HIP)
    # Rendering uses isolated processes for driver stability. Cache only these
    # small diagnostic outputs so each frame need not reread/resample 256M voxels.
    cache_dir = WORK_DIR / "preview_cache" / new_hip_sha
    cache_dir.mkdir(parents=True, exist_ok=True)
    render_caches = {}
    for name in [*preview_names, "PREVIEW_NEUTRAL_SHADING"]:
        path = cache_dir / f"{name}.bgeo.sc"
        net.node(name).geometry().saveToFile(str(path))
        render_caches[name] = {"path": str(path), "sha256": digest(path)}
    if digest(L06_HIP) != base_hip_sha or digest(FINAL_CACHE) != expected_cache:
        raise RuntimeError("Retained L06 source changed during preview repair")
    report = {
        "status": "PREVIEW_GRAPH_REPAIRED_RENDER_REVIEW_PENDING",
        "houdini_version": hou.applicationVersionString(),
        "hip": str(L07_HIP), "hip_before_sha256": old_hip_sha,
        "hip_after_sha256": new_hip_sha, "backup": str(backup),
        "source_cache": str(FINAL_CACHE), "source_cache_sha256": expected_cache,
        "source_l06_hip_sha256": base_hip_sha, "source_unchanged": True,
        "idmap_sha256": expected_idmap, "scree_png_xy": png_xy,
        "scree_native_voxel": voxel, "scree_houdini_xyz_m": target,
        "scree_source_id": source_id, "scree_crop_size_m": 128,
        "scree_selection_radius_m": 32, "scree_selection_neighbours": int(nearby_counts[selected]),
        "scree_crop_resolution": list(crop_vols["id"].resolution()),
        "scree_crop_class_pixels": count, "scree_decoder_mismatches": mismatches,
        "scree_crop_max_height_m": crop_max_height,
        "global_tint_field": "r g b", "global_tint_ramp": "none",
        "cooked_preview_fields": cooked_fields, "render_caches": render_caches,
        "invalidated": ["L07 preview renders", "historical Scree camera/texel evidence"],
        "terrain_exports_regenerated": False, "unreal_assets_changed": False,
    }
    report_path = WORK_DIR / "preview_repair_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize-from-l06", action="store_true",
                        help="Explicit initial setup only; normally resume the existing L07 HIP")
    args = parser.parse_args()
    if args.initialize_from_l06:
        if L07_HIP.exists():
            raise RuntimeError("L07 already exists; resume it instead of restarting from L06")
        initialize_from_lesson06()
    repair_previews()
