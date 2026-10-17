"""Render all visual evidence for Pegasus Lesson 03 - Sa Calobra.

Outputs:
1. lesson03_01_full_panorama_color.png: Full panorama of the whole landscape with Colour ON
2. lesson03_02a_closeup_crags_color.png: High pass crags close-up with limestone color and micro-relief
3. lesson03_02b_closeup_canyon_color.png: Torrent de Pareis canyon close-up
4. lesson03_02c_closeup_coastal_color.png: Coastal cliffs close-up
5. lesson03_03a_fixed_cam_before_base.png: Fixed-cam Before (Base Source+Manual DTM)
6. lesson03_03b_fixed_cam_after_material.png: Fixed-cam After (Lesson 3 displaced rock micro-relief)
"""
import os
import shutil
import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
evidence_dir = f"{project_dir}/evidence"
artifact_dir = "C:/Users/akarn/.gemini/antigravity/brain/d3ee11c1-e4d3-48e9-98a6-76b17331ecf5"
os.makedirs(evidence_dir, exist_ok=True)
os.makedirs(artifact_dir, exist_ok=True)

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson03.hiplc"
print(f"Loading scene: {hip_file}")
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

for n in hou.node("/obj").children():
    n.setDisplayFlag(False)


def render_view(geo_node, cam_pos, look_target, out_filename, res=(1920, 1080)):
    geo_node.setDisplayFlag(True)
    clean_name = out_filename.replace(".", "_")

    cam = hou.node("/obj").createNode("cam", f"cam_{clean_name}")
    cam.parm("tx").set(cam_pos[0])
    cam.parm("ty").set(cam_pos[1])
    cam.parm("tz").set(cam_pos[2])

    tgt = hou.node("/obj").createNode("null", f"tgt_{clean_name}")
    tgt.parm("tx").set(look_target[0])
    tgt.parm("ty").set(look_target[1])
    tgt.parm("tz").set(look_target[2])
    tgt.setDisplayFlag(False)

    cam.parm("lookatpath").set(tgt.path())
    cam.parm("resx").set(res[0])
    cam.parm("resy").set(res[1])

    rop = hou.node("/out").createNode("opengl", f"rop_{clean_name}")
    rop.parm("camera").set(cam.path())
    rop.parm("vobjects").set(geo_node.path())

    out_path = f"{evidence_dir}/{out_filename}"
    rop.parm("picture").set(out_path)
    rop.parm("execute").pressButton()

    art_path = f"{artifact_dir}/{out_filename}"
    shutil.copy2(out_path, art_path)
    print(f"Rendered {out_filename}: {os.path.getsize(out_path)} bytes -> copied to artifact dir")

    cam.destroy()
    tgt.destroy()
    rop.destroy()
    geo_node.setDisplayFlag(False)
    return out_path


# =========================================================================
# 1. SHOT 01: FULL PANORAMA (8000m x 8000m) with Colour & Displacement
# =========================================================================
print("--- Building Shot 01: Full Panorama ---")
pano_geo = hou.node("/obj").createNode("geo", "RENDER_PANO")
m_pano = pano_geo.createNode("object_merge")
m_pano.parm("objpath1").set("/obj/SA_CALOBRA/CONTEXT_MATERIAL_CACHE")

conv_pano = pano_geo.createNode("convert")
conv_pano.setInput(0, m_pano)

w_pano = pano_geo.createNode("attribwrangle")
w_pano.setInput(0, conv_pano)
w_pano.setInput(1, m_pano)
w_pano.parm("snippet").set("""
vector p = @P;
p.y = 0;
float r = volumesample(1, 'r', p);
float g = volumesample(1, 'g', p);
float b = volumesample(1, 'b', p);
vector rock_col = set(r, g, b);
vector ground_col = set(0.26, 0.30, 0.22);
if (r > 0.05 || g > 0.05 || b > 0.05) {
    @Cd = rock_col;
} else {
    @Cd = ground_col;
}
""")

nrm_pano = pano_geo.createNode("normal")
nrm_pano.setInput(0, w_pano)
nrm_pano.setDisplayFlag(True)
nrm_pano.setRenderFlag(True)

render_view(pano_geo, (-2200, 2400, -3200), (0, 300, 500), "lesson03_01_full_panorama_color.png")
pano_geo.destroy()


# =========================================================================
# 2. CLOSE-UPS (High Pass, Canyon, Coastal) on Full Working 0.5m Landscape
# =========================================================================
def build_closeup_mesh(name, tx, tz, sx=180, sy=180, source_node="/obj/SA_CALOBRA/output0"):
    geo = hou.node("/obj").createNode("geo", f"GEO_{name}")
    m = geo.createNode("object_merge")
    m.parm("objpath1").set(source_node)

    crop = geo.createNode("heightfield_crop")
    crop.setInput(0, m)
    crop.parm("sizex").set(sx)
    crop.parm("sizey").set(sy)
    crop.parm("tx").set(tx)
    crop.parm("tz").set(tz)

    conv = geo.createNode("convert")
    conv.setInput(0, crop)

    w = geo.createNode("attribwrangle")
    w.setInput(0, conv)
    w.setInput(1, crop)
    w.parm("snippet").set("""
    vector p = @P;
    p.y = 0;
    float r = volumesample(1, 'r', p);
    float g = volumesample(1, 'g', p);
    float b = volumesample(1, 'b', p);
    if (r > 0.05 || g > 0.05 || b > 0.05) {
        @Cd = set(r, g, b);
    } else {
        @Cd = set(0.30, 0.33, 0.25);
    }
    """)

    nrm = geo.createNode("normal")
    nrm.setInput(0, w)
    nrm.setDisplayFlag(True)
    nrm.setRenderFlag(True)
    return geo, nrm


# Shot 02a: High Pass / Coll dels Reis Crags
print("--- Building Shot 02a: High Pass Crags Close-up ---")
geo_crags, nrm_crags = build_closeup_mesh("CRAGS", 224.0, -711.0, 160, 160)
render_view(geo_crags, (224.0 - 75.0, 357.2 + 45.0, -711.0 - 75.0), (224.0, 357.2, -711.0), "lesson03_02a_closeup_crags_color.png")
geo_crags.destroy()

# Shot 02b: Torrent de Pareis Canyon
print("--- Building Shot 02b: Canyon Close-up ---")
geo_canyon, nrm_canyon = build_closeup_mesh("CANYON", -324.5, 545.5, 180, 180)
render_view(geo_canyon, (-324.5 - 80.0, 362.4 + 50.0, 545.5 - 80.0), (-324.5, 362.4, 545.5), "lesson03_02b_closeup_canyon_color.png")
geo_canyon.destroy()

# Shot 02c: Coastal Cliffs above Sea
print("--- Building Shot 02c: Coastal Cliffs Close-up ---")
geo_coastal, nrm_coastal = build_closeup_mesh("COASTAL", -479.0, 2213.0, 180, 180)
render_view(geo_coastal, (-479.0 - 80.0, 911.6 + 45.0, 2213.0 - 80.0), (-479.0, 911.6, 2213.0), "lesson03_02c_closeup_coastal_color.png")
geo_coastal.destroy()

# =========================================================================
# 3. FIXED-CAMERA BEFORE / AFTER HEIGHT COMPARISON (Same Camera & Target)
# =========================================================================
print("--- Building Shot 03a & 03b: Fixed-Camera Before / After ---")
# Fixed camera framing on the high crag face
fixed_cam_pos = (224.0 - 55.0, 357.2 + 25.0, -711.0 - 55.0)
fixed_tgt_pos = (224.0, 357.2, -711.0)

# 3a. Before: Base Terrain (Source + Manual, Material detail disabled)
geo_before, _ = build_closeup_mesh("BEFORE", 224.0, -711.0, 120, 120, source_node="/obj/SA_CALOBRA/SOURCE_CACHE")
render_view(geo_before, fixed_cam_pos, fixed_tgt_pos, "lesson03_03a_fixed_cam_before_base.png")
geo_before.destroy()

# 3b. After: Lesson 3 Material (Full rock displacement & pale limestone micro-relief)
geo_after, _ = build_closeup_mesh("AFTER", 224.0, -711.0, 120, 120, source_node="/obj/SA_CALOBRA/WORKING_MATERIAL_CACHE")
render_view(geo_after, fixed_cam_pos, fixed_tgt_pos, "lesson03_03b_fixed_cam_after_material.png")
geo_after.destroy()

print("=== ALL RENDERS COMPLETED SUCCESSFULLY ===")
