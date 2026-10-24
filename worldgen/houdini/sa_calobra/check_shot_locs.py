import hou

hou.hipFile.load('D:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson03.hiplc', suppress_save_prompt=True)
geo = hou.node('/obj/SA_CALOBRA')
sc = geo.node('SOURCE_CACHE')

test_locs = [
    ('High Pass', 224.0, -711.0),
    ('Canyon', -324.5, 545.5),
    ('Coastal', -479.0, 2213.0)
]

for name, tx, tz in test_locs:
    crop = geo.createNode('heightfield_crop')
    crop.setInput(0, sc)
    crop.parm('sizex').set(160)
    crop.parm('sizey').set(160)
    crop.parm('tx').set(tx)
    crop.parm('tz').set(tz)
    conv = geo.createNode('convert')
    conv.setInput(0, crop)
    g = conv.geometry()
    bbox = g.boundingBox()
    c = bbox.center()
    print(f'{name}: center=({c[0]:.1f}, {c[1]:.1f}, {c[2]:.1f}), y_range=({bbox.minvec().y():.1f}, {bbox.maxvec().y():.1f})')
