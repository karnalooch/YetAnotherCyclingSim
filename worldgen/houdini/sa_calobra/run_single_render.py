"""Render a single shot in an isolated hython process to prevent OpenGL driver re-entry issues."""
import sys
import os
import shutil
import argparse
import hou

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
evidence_dir = f"{project_dir}/evidence"
artifact_dir = "C:/Users/akarn/.gemini/antigravity/brain/d3ee11c1-e4d3-48e9-98a6-76b17331ecf5"
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
    return geo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shot", required=True)
    args = parser.parse_args()

    hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson03.hiplc"
    hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

    for n in hou.node("/obj").children():
        n.setDisplayFlag(False)

    if args.shot == "02a_crags":
        out_filename = "lesson03_02a_closeup_crags_color.png"
        geo = build_mesh("CRAGS", 224.0, -711.0, 160, 160)
        cam_pos = (224.0 - 75.0, 357.2 + 45.0, -711.0 - 75.0)
        tgt_pos = (224.0, 357.2, -711.0)

    elif args.shot == "02b_canyon":
        out_filename = "lesson03_02b_closeup_canyon_color.png"
        geo = build_mesh("CANYON", -324.5, 545.5, 180, 180)
        cam_pos = (-324.5 - 80.0, 362.4 + 50.0, 545.5 - 80.0)
        tgt_pos = (-324.5, 362.4, 545.5)

    elif args.shot == "02c_coastal":
        out_filename = "lesson03_02c_closeup_coastal_color.png"
        geo = build_mesh("COASTAL", -479.0, 2213.0, 180, 180)
        cam_pos = (-479.0 - 80.0, 911.6 + 45.0, 2213.0 - 80.0)
        tgt_pos = (-479.0, 911.6, 2213.0)

    elif args.shot == "03a_before":
        out_filename = "lesson03_03a_fixed_cam_before_base.png"
        geo = build_mesh("BEFORE", 224.0, -711.0, 120, 120, source_node="/obj/SA_CALOBRA/SOURCE_CACHE")
        cam_pos = (224.0 - 55.0, 357.2 + 25.0, -711.0 - 55.0)
        tgt_pos = (224.0, 357.2, -711.0)

    elif args.shot == "03b_after":
        out_filename = "lesson03_03b_fixed_cam_after_material.png"
        geo = build_mesh("AFTER", 224.0, -711.0, 120, 120, source_node="/obj/SA_CALOBRA/WORKING_MATERIAL_CACHE")
        cam_pos = (224.0 - 55.0, 357.2 + 25.0, -711.0 - 55.0)
        tgt_pos = (224.0, 357.2, -711.0)

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
    print(f"SUCCESS: Rendered {out_filename}: {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
