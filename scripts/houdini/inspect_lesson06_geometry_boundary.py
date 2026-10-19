"""Read-only native sampling of retained L06 heights; no HIP load or cook."""
import json
from pathlib import Path
import numpy as np
import hou
from repair_lesson06_idmap import read, volume, lattice, values, digest

root = Path('D:/yacs/work/lesson06-reviewed-20261018')
wpath, cpath = root/'working/final.bgeo.sc', root/'context/final.bgeo.sc'
w = read(wpath)
wv = volume(w, 'height')
wl = lattice(wv)
nx, ny, _ = wl['resolution']
indices = [(x, 0) for x in range(nx)] + [(x, ny-1) for x in range(nx)]
indices += [(0, y) for y in range(ny)] + [(nx-1, y) for y in range(ny)]
positions = [wv.indexToPos((x, y, 0)) for x, y in indices]
wa = values(w, 'height').reshape(ny, nx)
heights = np.array([wa[y, x] for x, y in indices], dtype=np.float64)
del wa, wv, w
c = read(cpath)
cv = volume(c, 'height')
sampled = np.array([cv.sample(p) for p in positions], dtype=np.float64)
delta = heights-sampled
worst = int(np.argmax(np.abs(delta)))
report = {'status': 'SOURCE_SURFACES_DIFFER_AT_SAME_XZ', 'houdini': hou.applicationVersionString(),
          'method': 'Working native perimeter samples versus hou.Volume.sample Context at identical world positions; continuous volume interpolation, not UE triangulated surface',
          'samples_including_duplicate_corners': len(delta), 'working_lattice': wl, 'context_lattice': lattice(cv),
          'mean_abs_m': float(np.abs(delta).mean()), 'max_abs_m': float(np.abs(delta).max()),
          'over_0_05m': int(np.count_nonzero(np.abs(delta)>0.05)),
          'worst': {'position_houdini_m': list(positions[worst]), 'working_m': float(heights[worst]), 'context_m': float(sampled[worst])},
          'source_sha256': {str(p): digest(p) for p in [wpath, cpath]},
          'height_or_mask_written': False, 'hip_loaded': False, 'terrain_cooked': False}
out = Path('Saved/RuntimeProof/Lesson06SeamRemote/geometry_boundary.json')
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report), flush=True)
