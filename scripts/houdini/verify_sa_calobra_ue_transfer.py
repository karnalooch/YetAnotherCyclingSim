import pathlib, json, hashlib, hou
import numpy as np
root=pathlib.Path('D:/yacs/work/sa-calobra-houdini-unreal-20261016/unreal_transfer')
reference=pathlib.Path('C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/work/pegasus/geographic_verify/final_height.npy')
expected=np.load(reference,mmap_mode='r')
manifest=json.loads((root/'manifest.json').read_text())
arrays=[];results=[];samples=[]
for tile in manifest['tiles']:
 if tile['index']==4:continue
 g=hou.Geometry();g.loadFromFile(str(root/tile['file']))
 p=next(p for p in g.prims() if p.attribValue('name')=='height')
 a=np.frombuffer(p.allVoxelsAsString(),np.float32).reshape(p.resolution()[1],p.resolution()[0]).copy()
 arrays.append(a)
 px,_,pz=tile['index0'];col0=round((px+1771.25)/.5);row0=round((3144.25-pz)/.5)
 r0=max(0,row0);r1=min(expected.shape[0],row0+a.shape[0]);c0=max(0,col0);c1=min(expected.shape[1],col0+a.shape[1])
 actual=a[r0-row0:r1-row0,c0-col0:c1-col0]
 max_diff=float(np.abs(actual-expected[r0:r1,c0:c1]).max())
 assert max_diff<.0002,(tile['name'],max_diff)
 results.append({'name':tile['name'],'samples_compared':int(actual.size),'max_difference_m':max_diff})
 for row in [500,1500,2500,3500,4500]:
  for col in [500,1500,2500,3300]:
   samples.append({'tile':tile['name'],'x_cm':(px+col*.5)*100,'y_cm':(pz-row*.5)*100,'height_cm':float(a[row,col])*100})
seams=[float(np.max(np.abs(arrays[0][:,-1]-arrays[1][:,0]))),float(np.max(np.abs(arrays[2][:,-1]-arrays[3][:,0]))),float(np.max(np.abs(arrays[2][-1,:]-arrays[0][0,:]))),float(np.max(np.abs(arrays[3][-1,:]-arrays[1][0,:])))]
assert max(seams)==0,seams
report={'verified':True,'comparisons':results,'tile_edge_max_errors_m':seams,'height_samples':samples}
(root/'source_transfer_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='height_samples'}))
