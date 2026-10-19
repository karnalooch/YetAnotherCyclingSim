import hou, os

hou.hda.installFile("D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda")
project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
for hda in ["sop_PE_Load_Landscape.2.hda", "sop_PE_Cache_Landscape.hda"]:
    hou.hda.installFile(f"{project_dir}/otls/{hda}")

hip_file = f"{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc"
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

h_load = hou.node("/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape")
h_load.cook(force=True)

# Create camera
cam = hou.node("/obj").createNode("cam", "render_cam")
cam.parm("tx").set(0)
cam.parm("ty").set(4000)
cam.parm("tz").set(-2000)
cam.parm("rx").set(-60)
cam.parm("ry").set(0)
cam.parm("rz").set(0)
cam.parm("resx").set(1280)
cam.parm("resy").set(720)

out_png = "D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_houdini_render.png"
rop = hou.node("/out").createNode("opengl", "test_opengl")
rop.parm("camera").set(cam.path())
rop.parm("picture").set(out_png)

print("Rendering with OpenGL ROP...")
try:
    rop.parm("execute").pressButton()
    print("Render finished. Exists:", os.path.exists(out_png))
    if os.path.exists(out_png):
        print("Render file size:", os.path.getsize(out_png))
except Exception as e:
    print("Render failed:", e)
