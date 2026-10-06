"""Retain only the two assets made by the failed, unapplied palette attempt."""

import json
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
key = "f6344bc52fab47f187e6baae4f8f2033"
package = (
    "/Game/Generated/YACS/TextureMaterialPrep/Libraries/3fb8a9508ac141a396189f4a0c3438f9/Landscape/"
    + key
)
path = (
    ROOT / "Saved/RuntimeProof/TextureLandscape" / key / "failed-attempt-retained.json"
)
if path.exists():
    raise RuntimeError("Failed-attempt retention already recorded")
for name in ("M_SaCalobraGeneratedSurfaces", "T_SurfaceWeights"):
    asset = unreal.EditorAssetLibrary.load_asset(package + "/" + name)
    if asset is None or not unreal.EditorAssetLibrary.save_loaded_asset(
        asset, only_if_is_dirty=True
    ):
        raise RuntimeError("Failed-attempt retention failed")
path.write_text(
    json.dumps(
        {
            "status": "FAILED_UNAPPLIED_ATTEMPT_RETAINED",
            "failure": "Desaturation connection used Input instead of unnamed first pin",
            "landscape_assignment_reached": False,
            "package": package,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
unreal.log("YACS_FAILED_PRESENTATION_ATTEMPT_RETAINED " + str(path))
