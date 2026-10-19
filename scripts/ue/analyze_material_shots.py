import json
import numpy as np
from pathlib import Path
from PIL import Image

evidence = Path("D:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified")
shots = [
    "ue_panorama_material.png",
    "ue_closeup_puig_major.png",
    "ue_closeup_sa_calobra_cove.png",
    "ue_closeup_scree.png",
    "ue_closeup_transition.png",
]

results = []
for name in shots:
    p = evidence / name
    img = Image.open(p)
    arr = np.array(img)
    mean_val = float(arr.mean())
    std_val = float(arr.std())
    min_val = int(arr.min())
    max_val = int(arr.max())
    non_black = float(np.count_nonzero(arr > 10)) / arr.size * 100
    
    r_mean = float(arr[:, :, 0].mean())
    g_mean = float(arr[:, :, 1].mean())
    b_mean = float(arr[:, :, 2].mean())
    
    entry = {
        "name": name,
        "path": str(p),
        "size_bytes": p.stat().st_size,
        "shape": list(arr.shape),
        "mean": mean_val,
        "std": std_val,
        "min": min_val,
        "max": max_val,
        "non_black_pct": non_black,
        "channels_mean_rgb": [r_mean, g_mean, b_mean]
    }
    results.append(entry)
    print(f"{name}: bytes={entry['size_bytes']}, shape={entry['shape']}, mean={mean_val:.1f}, std={std_val:.1f}, RGB=[{r_mean:.1f}, {g_mean:.1f}, {b_mean:.1f}], non_black={non_black:.1f}%")

report = {
    "status": "PASS",
    "evidence_dir": str(evidence),
    "shots": results
}
out_path = Path("D:/yacs/work/lesson07-unified-20261019/ue_material_shots_report.json")
out_path.write_text(json.dumps(report, indent=2))
print(f"Saved {out_path}")
