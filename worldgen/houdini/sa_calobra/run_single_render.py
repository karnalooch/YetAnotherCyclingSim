"""Render a single shot for Lesson 04 in an isolated hython process.

Completely eliminates OpenGL driver re-entry / VBO accumulation crashes.
Strictly renders genuine material colors (@Cd = set(r, g, b)) with NO synthetic fallbacks.
"""
import sys
import os
import shutil
import argparse
import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
evidence_dir = f"{project_dir}/evidence"
artifact_dir = "C:/Users/akarn/.gemini/antigravity/brain/a8bdbe87-c1b2-4851-a60b-d95da6c97b58"
os.makedirs(evidence_dir, exist_ok=True)
os.makedirs(artifact_dir, exist_ok=True)


def build_mesh(name, tx, tz, sx=180, sy=180, source_node="/obj/SA_CALOBRA/WORKING_MATERIAL_CACHE"):
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
    # Strictly genuine material colors directly from Lesson 04 R/G/B volume layers
    w.parm("snippet").set("""
    vector p = @P;
    p.y = 0;
    float r = volumesample(1, 'r', p);
    float g = volumesample(1, 'g', p);
    float b = volumesample(1, 'b', p);
    @Cd = set(r, g, b);
    """)

    nrm = geo.createNode("normal")
    nrm.setInput(0, w)
    nrm.setDisplayFlag(True)
    nrm.setRenderFlag(True)
    return geo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", required=True)
    args = parser.parse_args()

    hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson04.hiplc"
    hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

    for n in hou.node("/obj").children():
        n.setDisplayFlag(False)

    if args.shot == "00_working_pano":
        out_filename = "04_working_landscape_panorama.png"
        geo = hou.node("/obj").createNode("geo", "RENDER_WORKING_PANO")
        m_pano = geo.createNode("object_merge")
        m_pano.parm("objpath1").set("/obj/SA_CALOBRA/WORKING_MATERIAL_CACHE")
        resample = geo.createNode("heightfield_resample")
        resample.setInput(0, m_pano)
        resample.parm("divisionmode").set(1)
        resample.parm("gridspacing").set(2.0)
        conv_pano = geo.createNode("convert")
        conv_pano.setInput(0, resample)
        w_pano = geo.createNode("attribwrangle")
        w_pano.setInput(0, conv_pano)
        w_pano.setInput(1, m_pano)
        w_pano.parm("snippet").set("""
        vector p = @P;
        p.y = 0;
        float r = volumesample(1, 'r', p);
        float g = volumesample(1, 'g', p);
        float b = volumesample(1, 'b', p);
        @Cd = set(r, g, b);
        """)
        nrm_pano = geo.createNode("normal")
        nrm_pano.setInput(0, w_pano)
        nrm_pano.setDisplayFlag(True)
        nrm_pano.setRenderFlag(True)
        cam_pos = (-1200, 1800, -2400)
        tgt_pos = (0, 350, 400)

    elif args.shot == "01_pano":
        out_filename = "04_context_background_panorama.png"
        geo = hou.node("/obj").createNode("geo", "RENDER_PANO")
        m_pano = geo.createNode("object_merge")
        m_pano.parm("objpath1").set("/obj/SA_CALOBRA/CONTEXT_MATERIAL_CACHE")
        conv_pano = geo.createNode("convert")
        conv_pano.setInput(0, m_pano)
        w_pano = geo.createNode("attribwrangle")
        w_pano.setInput(0, conv_pano)
        w_pano.setInput(1, m_pano)
        w_pano.parm("snippet").set("""
        vector p = @P;
        p.y = 0;
        float r = volumesample(1, 'r', p);
        float g = volumesample(1, 'g', p);
        float b = volumesample(1, 'b', p);
        @Cd = set(r, g, b);
        """)
        nrm_pano = geo.createNode("normal")
        nrm_pano.setInput(0, w_pano)
        nrm_pano.setDisplayFlag(True)
        nrm_pano.setRenderFlag(True)
        cam_pos = (-2200, 2400, -3200)
        tgt_pos = (0, 300, 500)

    elif args.shot == "02a_crags":
        out_filename = "04_closeup_crags.png"
        geo = build_mesh("CRAGS", 224.0, -711.0, 180, 180)
        cam_pos = (224.0 - 75.0, 357.2 + 45.0, -711.0 - 75.0)
        tgt_pos = (224.0, 357.2, -711.0)

    elif args.shot == "02b_canyon":
        out_filename = "04_closeup_canyon.png"
        geo = build_mesh("CANYON", -324.5, 545.5, 180, 180)
        cam_pos = (-324.5 - 80.0, 362.4 + 50.0, 545.5 - 80.0)
        tgt_pos = (-324.5, 362.4, 545.5)

    elif args.shot == "02c_coastal":
        out_filename = "04_closeup_coastal_sand.png"
        # Real sea-level coastal beach cove at Sa Calobra (X ≈ 18.0, Z ≈ -1368.0, Y ≈ 0-15m)
        geo = build_mesh("COASTAL", 18.0, -1368.0, 180, 180)
        cam_pos = (18.0 - 65.0, 45.0, -1368.0 - 65.0)
        tgt_pos = (18.0, 15.0, -1368.0)

    elif args.shot == "03a_tint_before":
        out_filename = "04_tint_comparison_before.png"
        # Fixed camera framing Before Tint in active vegetation valley (Sand & Grass material without tinting)
        geo = build_mesh("BEFORE_TINT", 0.0, -500.0, 180, 180, source_node="/obj/SA_CALOBRA/WORKING_SAND_MATERIAL")
        cam_pos = (-55.0, 415.0 + 35.0, -555.0)
        tgt_pos = (0.0, 415.0, -500.0)

    elif args.shot == "03b_tint_after":
        out_filename = "04_tint_comparison_after.png"
        # Fixed camera framing After Tint in active vegetation valley (Heightfield Tint gradient & occlusion applied)
        geo = build_mesh("AFTER_TINT", 0.0, -500.0, 180, 180, source_node="/obj/SA_CALOBRA/WORKING_HEIGHTFIELD_TINT")
        cam_pos = (-55.0, 415.0 + 35.0, -555.0)
        tgt_pos = (0.0, 415.0, -500.0)

    elif args.shot == "04_cliff_trans":
        out_filename = "04_cliff_smooth_transition.png"
        # Clean cliff to grass transition boundary (slope transition ~28-35 deg with smooth_radius=6.0 voxels)
        geo = build_mesh("CLIFF_TRANS", 80.0, -520.0, 160, 160)
        cam_pos = (80.0 - 45.0, 430.0 + 30.0, -520.0 - 45.0)
        tgt_pos = (80.0, 430.0, -520.0)

    else:
        raise ValueError(f"Unknown shot: {args.shot}")

    geo.setDisplayFlag(True)

    cam = hou.node("/obj").createNode("cam", "render_cam")
    cam.parm("tx").set(cam_pos[0])
    cam.parm("ty").set(cam_pos[1])
    cam.parm("tz").set(cam_pos[2])

    tgt = hou.node("/obj").createNode("null", "render_target")
    tgt.parm("tx").set(tgt_pos[0])
    tgt.parm("ty").set(tgt_pos[1])
    tgt.parm("tz").set(tgt_pos[2])
    tgt.setDisplayFlag(False)

    cam.parm("lookatpath").set(tgt.path())
    cam.parm("resx").set(1920)
    cam.parm("resy").set(1080)

    rop = hou.node("/out").createNode("opengl", "render_rop")
    rop.parm("camera").set(cam.path())
    rop.parm("vobjects").set(geo.path())

    out_path = f"{evidence_dir}/{out_filename}"
    rop.parm("picture").set(out_path)
    rop.parm("execute").pressButton()

    art_path = f"{artifact_dir}/{out_filename}"
    shutil.copy2(out_path, art_path)
    print(f"SUCCESS: Rendered {out_filename}: {os.path.getsize(out_path)} bytes -> copied to {art_path}")


if __name__ == "__main__":
    main()
