import hou, shutil, os

project_dir = 'D:/yacs/project/worldgen/houdini/sa_calobra'
cache_dir = f'{project_dir}/Pegasus/Landscape/Landscape Heightfield Layers'
evidence_dir = f'{project_dir}/evidence'
artifact_dir = 'C:/Users/akarn/.gemini/antigravity/brain/d3ee11c1-e4d3-48e9-98a6-76b17331ecf5'

neutral_file = f'{cache_dir}/Pegasus_Landscape_Layer_2_Manual_Edits.NEUTRAL.bgeo.sc'
active_file = f'{cache_dir}/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc'
shutil.copy2(neutral_file, active_file)

hip_file = f'{project_dir}/SaCalobra_Pegasus_Lesson02.hiplc'
hou.hipFile.load(hip_file, suppress_save_prompt=True, ignore_load_warnings=True)

for n in hou.node('/obj').children():
    n.setDisplayFlag(False)

view_geo = hou.node('/obj').createNode('geo', 'VIEW_MOUND')
merge = view_geo.createNode('object_merge')
merge.parm('objpath1').set('/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape')

crop = view_geo.createNode('heightfield_crop')
crop.setInput(0, merge)
crop.parm('sizex').set(180)
crop.parm('sizey').set(180)
crop.parm('tx').set(-950.75)
crop.parm('tz').set(-529.75)

conv = view_geo.createNode('convert')
conv.setInput(0, crop)

nrm = view_geo.createNode('normal')
nrm.setInput(0, conv)
nrm.setDisplayFlag(True)
nrm.setRenderFlag(True)
view_geo.setDisplayFlag(True)

cam = hou.node('/obj').createNode('cam', 'cam_mound')
# Closer, lower profile view
cam.parm('tx').set(-950.75 - 45.0)
cam.parm('ty').set(107.29 + 18.0)
cam.parm('tz').set(-529.75 - 45.0)

target = hou.node('/obj').createNode('null', 'mound_target')
target.parm('tx').set(-950.75)
target.parm('ty').set(107.29 + 2.0)
target.parm('tz').set(-529.75)
cam.parm('lookatpath').set(target.path())
cam.parm('resx').set(1920)
cam.parm('resy').set(1080)

h_load = hou.node('/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape')
h_load.parm('environment').set(1)
h_load.cook(force=True)

out_off = f'{evidence_dir}/03a_houdini_manual_off.png'
rop = hou.node('/out').createNode('opengl', 'rop_mound')
rop.parm('camera').set(cam.path())
rop.parm('vobjects').set('*')
rop.parm('picture').set(out_off)
rop.parm('execute').pressButton()

shutil.copy2(out_off, f'{artifact_dir}/03a_houdini_manual_off.png')
print('Rendered Manual OFF successfully! Size:', os.path.getsize(out_off))
