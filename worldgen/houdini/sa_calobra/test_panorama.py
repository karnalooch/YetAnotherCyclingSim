import hou, os

hou.hipFile.load('D:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson03.hiplc', suppress_save_prompt=True)

for n in hou.node('/obj').children():
    n.setDisplayFlag(False)

view_geo = hou.node('/obj').createNode('geo', 'VIEW_PANO')
m = view_geo.createNode('object_merge')
m.parm('objpath1').set('/obj/SA_CALOBRA/CONTEXT_MATERIAL_CACHE')

conv = view_geo.createNode('convert')
conv.setInput(0, m)

w = view_geo.createNode('attribwrangle')
w.setInput(0, conv)
w.setInput(1, m)
w.parm('snippet').set('''
vector p = @P;
p.y = 0;
float r = volumesample(1, 'r', p);
float g = volumesample(1, 'g', p);
float b = volumesample(1, 'b', p);

vector rock_col = set(r, g, b);
vector ground_col = set(0.26, 0.30, 0.22); // natural Mediterranean valley vegetation

if (r > 0.05 || g > 0.05 || b > 0.05) {
    @Cd = rock_col;
} else {
    @Cd = ground_col;
}
''')

nrm = view_geo.createNode('normal')
nrm.setInput(0, w)
nrm.setDisplayFlag(True)
nrm.setRenderFlag(True)
view_geo.setDisplayFlag(True)

cam = hou.node('/obj').createNode('cam', 'cam_pano')
cam.parm('tx').set(-2200)
cam.parm('ty').set(2400)
cam.parm('tz').set(-3200)

target = hou.node('/obj').createNode('null', 'target_pano')
target.parm('tx').set(0)
target.parm('ty').set(300)
target.parm('tz').set(500)
target.setDisplayFlag(False)

cam.parm('lookatpath').set(target.path())
cam.parm('resx').set(1920)
cam.parm('resy').set(1080)

rop = hou.node('/out').createNode('opengl', 'rop_pano')
rop.parm('camera').set(cam.path())
rop.parm('vobjects').set(view_geo.path())
out_png = 'D:/yacs/project/worldgen/houdini/sa_calobra/cache/test_pano2.png'
rop.parm('picture').set(out_png)
rop.parm('execute').pressButton()

print('Panorama rendered, exists:', os.path.exists(out_png), 'size:', os.path.getsize(out_png) if os.path.exists(out_png) else 0)
