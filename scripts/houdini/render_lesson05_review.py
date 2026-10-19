"""Render registered native Lesson05 review arrays; no terrain generation."""
import argparse
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--root',type=Path,required=True)
ap.add_argument('--export-stages',action='store_true',help='Run with hython to read retained tint caches first')
a=ap.parse_args()
root=a.root
if a.export_stages:
 import hou
 for area in ['context','working']:
  result={}
  for stage in ['scree_tint','occlusion']:
   g=hou.Geometry();g.loadFromFile(str(root/area/(stage+'.bgeo.sc')))
   channels=[]
   for name in ['r','g','b']:
    v=next(p for p in g.prims() if p.attribValue('name')==name)
    channels.append(np.frombuffer(v.allVoxelsAsString(),np.float32).reshape(v.resolution()[1],v.resolution()[0])[::8,::8].copy())
   result[stage]=np.stack(channels,axis=-1);del g
  result['curvature']=np.load(root/area/'preview_rgb.npy')
  np.savez_compressed(root/area/'tint_stages.npz',**result)
 raise SystemExit(0)
from PIL import Image, ImageDraw, ImageFont
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)
def rgb(a):return Image.fromarray(np.uint8(np.clip(a,0,1)*255))
def gray(a):return rgb(np.repeat(np.clip(a,0,1)[:,:,None],3,axis=2))
def shade(h,spacing):
 dy,dx=np.gradient(h,spacing)
 norm=np.sqrt(dx*dx+dy*dy+1)
 return np.clip(.25+.75*(-dx*.4-dy*.5+1*.768)/norm,0,1)
def sheet(items,path,width=420):
 tiles=[]
 for title,im in items:
  im=im.resize((width,round(im.height*width/im.width)))
  tile=Image.new('RGB',(width,im.height+44),(24,28,32));tile.paste(im,(0,44));ImageDraw.Draw(tile).text((10,10),title,font=font,fill='white');tiles.append(tile)
 canvas=Image.new('RGB',(sum(t.width for t in tiles),max(t.height for t in tiles)),(24,28,32));x=0
 for tile in tiles:canvas.paste(tile,(x,0));x+=tile.width
 canvas.save(path)
for area,spacing in [('working',.5),('context',3.90625)]:
 p=root/area
 if not (p/'preview_rgb.npy').exists():continue
 h=np.load(p/'preview_height.npy');before=np.load(p/'preview_l04_rgb.npy');after=np.load(p/'preview_rgb.npy');mask=np.load(p/'preview_scree.npy')
 sheet([('Lesson04 / encoded RGB',rgb(before)),('Lesson05 / encoded RGB',rgb(after)),('Scree mask / 0 to 1',gray(mask)),('Geometry / CPU hillshade',gray(shade(h,spacing*8)))],p/'whole_domain_review.png',560)
 if (p/'tint_stages.npz').exists():
  stages=np.load(p/'tint_stages.npz')
  sheet([('Occlusion OFF',rgb(stages['scree_tint'])),('Occlusion ON / curvature OFF',rgb(stages['occlusion'])),('Occlusion + curvature ON',rgb(stages['curvature']))],p/'grading_review.png',560)
 for label in ['scree','pocket','transition','gentle']:
  d=np.load(p/('review_'+label+'.npz'))
  sheet([('L04 / '+label,rgb(d['before_rgb'])),('L05 / same location',rgb(d['after_rgb'])),('Scree / 0 to 1',gray(d['mask'])),('L04 / neutral',gray(shade(d['before_h'],spacing))),('L05 / neutral',gray(shade(d['after_h'],spacing))),('Pockets / 0 to 1',gray(d['pockets']))],p/('review_'+label+'.png'))
 print(area,'review images ready')
if (root/'direction_control.npz').exists():
 d=np.load(root/'direction_control.npz');maximum=max(float(d[n].max()) for n in ['zero','opposite','retained'])
 sheet([('Pockets / 0 to 1',gray(d['pockets']))]+[(n+' / shared max '+str(round(maximum,3)),gray(d[n]/maximum)) for n in ['zero','opposite','retained']],root/'direction_control.png')
