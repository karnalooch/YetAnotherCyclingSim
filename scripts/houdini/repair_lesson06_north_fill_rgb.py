"""Bounded RGB repair using native SideFX Copernicus Smooth Fill.

Python only assembles/disassembles registered pixels and verifies transport.
The fill itself is the installed native node, not a replacement solver.
Original terrain, masks and caches are read-only. Run create, then verify in a
separate hython process to prove fresh HIP replay before UE admission.
"""
import hashlib,json,sys
from pathlib import Path
import hou,numpy as np,OpenImageIO as oi

BASE=Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
stable='--stable' in sys.argv
pad='--pad' in sys.argv
spot='--spot' in sys.argv or stable or pad
O=BASE/('NorthPadRGB' if pad else 'NorthSpotStableRGB' if stable else 'NorthSpotRGB' if spot else 'NorthFillRGB');O.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def digest(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def image(p):
    f=oi.ImageInput.open(str(p));assert f,p
    a=f.read_image(format=oi.FLOAT);f.close();return a
def write(p,a,typ):
    f=oi.ImageOutput.create(str(p));assert f.open(str(p),oi.ImageSpec(a.shape[1],a.shape[0],a.shape[2],typ))
    assert f.write_image(a);f.close()
def copfile(net,path,name,signature):
    n=net.createNode('file',name)
    n.setParms({'filename':str(path),'colorspace':'raw','aovs':1,'aov1':'C','type1':signature,'raw1':True})
    return n

lat=read(BASE/'sources.json')['lattice'];sx,sy,_=lat['resolution'];ox,_,oz=lat['origin']
rows=read(BASE/'NorthEdgeRGB/manifest.json')['tiles']
rows.sort(key=lambda r:r['uv_origin_cm'][0]);assert len(rows)==2
nx,ny=rows[0]['resolution'];assert all(r['resolution']==[nx,ny] for r in rows)
ax=rows[0]['uv_origin_cm'][0]/100+.25
az=rows[0]['uv_origin_cm'][1]/100-.25
assert all(r['uv_origin_cm'][1]/100-.25==az for r in rows)
offsets=[int(round((r['uv_origin_cm'][0]/100+.25-ax)*2)) for r in rows]
assert offsets==[0,nx-1],offsets
# Two-pixel fixed margins surround the allowed fill rectangle. World depth
# is positive inside Working. The original source mask is never modified.
j0=int(round((az-(oz+33))*2));j1=int(round((az-(oz-5))*2))+1
shape=(j1-j0,offsets[-1]+nx,3)
xs=ax+np.arange(shape[1])*.5
depth=oz-(az-(j0+np.arange(shape[0]))*.5)
allowed=(depth[:,None]>=-32)&(depth[:,None]<=4)&(xs[None,:]>=ox-32)&(xs[None,:]<=ox+(sx-1)*.5+32)

if sys.argv[1]=='create':
    assert not (O/(O.name+'.hiplc')).exists()
    strip=np.empty(shape,np.float32)
    for r,dx in zip(rows,offsets):
        assert digest(r['file'])==r['sha256']
        a=image(r['file'])
        if dx:assert np.array_equal(strip[:,:dx+1][:,-1],a[j0:j1,0])
        strip[:,dx:dx+nx]=a[j0:j1,:,:3]
    write(O/'registered_rgb.exr',strip,oi.FLOAT)
    write(O/'presentation_fill_area.exr',allowed[:,:,None].astype(np.float32),oi.FLOAT)
    net=hou.node('/img').createNode('copnet','NORTH_RGB_ONLY')
    src=copfile(net,O/'registered_rgb.exr','REGISTERED_RGB','vector')
    mask=copfile(net,O/'presentation_fill_area.exr','PRESENTATION_FILL_AREA','float')
    fill=net.createNode('extrapolateboundaries' if pad else 'smoothfill','NATIVE_BOUNDED_RGB_FILL')
    fill.setInput(0,src);fill.setInput(1,mask)
    if pad:fill.setParms({'exterior':'none','side':'below','threshold':.5,'edgepadding':1,'edgeoffset':0,'samplepresent':True})
    else:fill.setParms({'side':'above','threshold':.5,'iterations':1024,'omega':1.9})
    if stable:fill.setParms({'iterations':4096,'omega':1})
    if spot:
        dark=net.createNode('compare','ONLY_NEAR_BLACK_RGB')
        dark.setInput(0,src);dark.setParms({'compare':'less','components':'all','bval':.15})
        fill.setInput(1,dark);fill.setInput(2,mask)
    rop=net.createNode('rop_image','EXPORT_RGB')
    rop.setInput(0,fill);rop.setParms({'copoutput':str(O/'filled_rgb.exr'),'colorconversion':'raw'})
    hou.hipFile.save(str(O/(O.name+'.hiplc')))
    rop.parm('execute').pressButton();assert not rop.errors(),rop.errors()
    out=image(O/'filled_rgb.exr');assert out.shape==strip.shape
    assert np.isfinite(out).all()
    assert np.array_equal(out[~allowed],strip[~allowed]),'Native fill changed fixed boundary'
    if spot:assert np.array_equal(out[strip.max(axis=2)>=.15],strip[strip.max(axis=2)>=.15]),'Changed non-defect RGB'
    for r,dx in zip(rows,offsets):
        a=np.rint(image(r['file'])[:,:,:3]*255).astype(np.uint8)
        a[j0:j1]=np.rint(np.clip(out[:,dx:dx+nx],0,1)*255).astype(np.uint8)
        path=O/(r['name']+'.png');write(path,a,oi.UINT8)
        for key in ['native_pixels_file','native_pixels_sha256','edge_recipe','extension']:
            r.pop(key,None)
        r.update(file=str(path),sha256=digest(path),native_pixels_file=str(path),native_pixels_sha256=digest(path),
                 recipe='Copernicus Smooth Fill: native bounded Poisson fill, RGB only, RAW transport, 1024 iterations / omega 1.9',
                 context_fill_m=32,working_rgb_exception_m=4,shared_vertex_pixels_copied=0)
        if spot:r['recipe']+='; native Compare all RGB <0.15, geometry scope as output mask; non-dark RGB exact'
        if stable:r['recipe']=r['recipe'].replace('1024 iterations / omega 1.9','4096 iterations / omega 1.0 (strict stable relaxation)')
        if pad:r['recipe']='Native Copernicus Compare all RGB <0.15 + Extrapolate Boundaries, sample present, unchanged exterior, edge padding 1 image unit; output restricted by presentation rectangle. Non-dark RGB exact.'
        (O/(r['name']+'.json')).write_text(json.dumps(r,indent=2)+'\n')
    (O/'inputs.json').write_text(json.dumps({'houdini':hou.applicationVersionString(),'input_sha256':digest(O/'registered_rgb.exr'),'fill_area_sha256':digest(O/'presentation_fill_area.exr'),'native_result_sha256':digest(O/'filled_rgb.exr'),'source_variant':'NorthEdgeRGB','original_masks_modified':False},indent=2))
    print('NATIVE_FILL_CREATED',shape,flush=True)
elif sys.argv[1]=='verify':
    proof=read(O/'inputs.json')
    for path,key in [('registered_rgb.exr','input_sha256'),('presentation_fill_area.exr','fill_area_sha256'),('filled_rgb.exr','native_result_sha256')]:assert digest(O/path)==proof[key]
    hou.hipFile.load(str(O/(O.name+'.hiplc')),suppress_save_prompt=True)
    rop=hou.node('/img/NORTH_RGB_ONLY/EXPORT_RGB');rop.parm('copoutput').set(str(O/'fresh_rgb.exr'))
    rop.parm('execute').pressButton();assert not rop.errors(),rop.errors()
    fresh=image(O/'fresh_rgb.exr');native=image(O/'filled_rgb.exr')
    assert np.array_equal(fresh,native),'Fresh native COP replay differs'
    assert np.array_equal(native[~allowed],image(O/'registered_rgb.exr')[~allowed])
    if spot:
        src=image(O/'registered_rgb.exr');assert np.array_equal(native[src.max(axis=2)>=.15],src[src.max(axis=2)>=.15])
    checked=[];images=[]
    for original,dx in zip(rows,offsets):
        r=read(O/(original['name']+'.json'));assert digest(r['file'])==r['sha256']
        a=np.rint(image(r['file'])[:,:,:3]*255).astype(np.uint8)
        prior=np.rint(image(original['file'])[:,:,:3]*255).astype(np.uint8)
        expected=prior.copy();expected[j0:j1]=np.rint(np.clip(fresh[:,dx:dx+nx],0,1)*255).astype(np.uint8)
        assert np.array_equal(a,expected)
        changed=np.any(a!=prior,axis=-1);scope=np.zeros(changed.shape,bool);scope[j0:j1]=allowed[:,dx:dx+nx]
        assert not np.any(changed&~scope),'Changed outside authorized RGB region'
        tx=xs[dx:dx+nx];ys=np.rint((oz-(az-np.arange(ny)*.5))*2).astype(int)
        ix=np.where((tx>=ox)&(tx<=ox+(sx-1)*.5))[0];iy=np.where((ys>=0)&(ys<sy))[0]
        baseline=read(BASE/'SourceBoundaryRGB'/(r['name']+'.json'))
        src=np.rint(image(baseline['file'])[:,:,:3]*255).astype(np.uint8)
        diff=np.any(a[iy[:,None],ix[None,:]]!=src[iy[:,None],ix[None,:]],axis=-1)
        changed_rows=np.where(diff.any(axis=1))[0]
        maxdepth=float(ys[iy[changed_rows]].max()*.5) if changed_rows.size else 0
        assert maxdepth<=4
        r.update(working_rgb_changed_pixels=int(diff.sum()),working_rgb_max_changed_depth_m=maxdepth,sharp_working_pixels_bitexact=int(diff.size-diff.sum()))
        (O/(r['name']+'.json')).write_text(json.dumps(r,indent=2)+'\n')
        checked.append(r);images.append(a)
    assert np.array_equal(images[0][:,-1],images[1][:,0]),'Shared edge differs'
    manifest={'status':'VERIFIED_RGB_ONLY','tiles':checked,'fresh_reopen':'BIT_EXACT_NATIVE_COP','working_rgb_exception_m':4,'working_outside_exception':'BIT_EXACT','max_edge_code_delta':0,'height_or_mask_payload':False,'outside_fill_rectangle':'BIT_EXACT','native_fixed_boundary':'BIT_EXACT','source':proof}
    if spot:manifest['non_dark_rgb']='BIT_EXACT; all RGB channels <0.15 required for fill'
    (O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('NATIVE_FILL_FRESH_REPLAY_PASS',flush=True)
else:raise ValueError('Use create or verify')
