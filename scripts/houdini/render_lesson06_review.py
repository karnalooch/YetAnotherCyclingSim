"""Render measured native decoder output and report cross-grid boundaries.

Images are CPU diagnostic views, not Houdini viewport or Unreal screenshots.
No terrain or material selection is generated or modified here.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

COLORS = np.array([[.25,.55,.15],[.85,.85,.15],[.90,.75,.45],[.40,.35,.30],[.60,.60,.60]])
CODES = np.array([0,64,128,191,255])
NAMES = ['grass','grass 2','sand','cliffs','scree']


def rgb(ids):
    ints = np.rint(ids*255).astype(int)
    result = np.zeros((*ints.shape,3))
    for i, code in enumerate(CODES):
        result[ints == code] = COLORS[i]
    return result


def image(arr):
    if arr.ndim == 2:
        arr = np.repeat(arr[:,:,None],3,axis=2)
    return Image.fromarray(np.uint8(np.clip(arr,0,1)*255))


def sheet(items, path, width=400):
    tiles=[]
    for title, arr in items:
        im=image(arr)
        im=im.resize((width,round(im.height*width/im.width)), Image.Resampling.NEAREST)
        tile=Image.new('RGB',(width,im.height+40),(24,28,32))
        tile.paste(im,(0,40))
        ImageDraw.Draw(tile).text((6,12),title,fill='white')
        tiles.append(tile)
    result=Image.new('RGB',(sum(t.width for t in tiles),max(t.height for t in tiles)),(24,28,32))
    x=0
    for tile in tiles:
        result.paste(tile,(x,0));x+=tile.width
    result.save(path)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    a=ap.parse_args()
    for area in ['working','context']:
        folder=a.root/area
        data=np.load(folder/'native_previews.npz')
        h=data['height'];dy,dx=np.gradient(h)
        shade=np.clip(.25+.75*(-.4*dx-.5*dy+1)/np.sqrt(dx*dx+dy*dy+1),0,1)
        sheet([('Native IDMap / '+area,rgb(data['id'])),('Geometry / CPU hillshade',shade)],folder/'review_overview.png')
        sheet([(name+' / native ID-to-Layer',data[name]) for name in NAMES],folder/'review_decoded.png',width=300)
        for name in NAMES:
            detail=np.load(folder/('detail_'+name.replace(' ','_')+'.npz'))
            sheet([('Source mask / '+name,detail['source']),('Native IDMap',rgb(detail['id'])),('Native decoded / '+name,detail['decoded'])],folder/('review_'+name.replace(' ','_')+'.png'),width=512)
    working=json.loads((a.root/'working/repair.json').read_text())['lattice']
    context=json.loads((a.root/'context/repair.json').read_text())['lattice']
    nx,ny,_=working['resolution']
    ix=np.concatenate([np.arange(nx),np.arange(nx),np.zeros(ny),np.full(ny,nx-1)])
    iy=np.concatenate([np.zeros(nx),np.full(nx,ny-1),np.arange(ny),np.arange(ny)])
    x=working['origin'][0]+ix*working['x'][0]
    z=working['origin'][2]+iy*working['y'][2]
    cx=np.rint((x-context['origin'][0])/context['x'][0]).astype(int)
    cy=np.rint((z-context['origin'][2])/context['y'][2]).astype(int)
    assert np.all((cx>=0)&(cx<context['resolution'][0])&(cy>=0)&(cy<context['resolution'][1]))
    wi=np.load(a.root/'working/boundary.npz')['id']
    ci=np.load(a.root/'context/boundary.npz')['id'][cy,cx]
    mismatch=wi!=ci
    report={'comparison':'nearest Context cell at each Working rectangular perimeter sample; corners counted twice',
            'samples':len(wi),'disagree':int(mismatch.sum()),'disagree_percent':float(mismatch.mean()*100),
            'registration':'both Houdini metre lattices verified; Context covers full Working perimeter',
            'interpretation':'Different resolutions and retained source masks; this is a material seam assessment, not a demand for resampling height.',
            'boundary_acceptance':'REQUIRES_REVIEW' if mismatch.any() else 'PASS'}
    (a.root/'boundary-review.json').write_text(json.dumps(report,indent=2)+'\n')
    for name,start,length in [('north',0,nx),('south',nx,nx),('west',2*nx,ny),('east',2*nx+ny,ny)]:
        w=wi[start:start+length];c=ci[start:start+length]
        strip=np.stack([w,c],axis=0)
        im=image(rgb(strip)).resize((1600,100),Image.Resampling.NEAREST)
        im.save(a.root/('boundary_'+name+'.png'))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
