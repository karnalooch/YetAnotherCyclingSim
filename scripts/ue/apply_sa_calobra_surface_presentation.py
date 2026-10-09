"""Build a separate native UE material/map variant from the approved palette."""

import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
recipe = json.loads(
    (
        ROOT / "worldgen/materials/sa_calobra_surface_presentation_20261005.json"
    ).read_text()
)
report = runpy.run_path(
    str(ROOT / "scripts/ue/apply_sa_calobra_generated_surfaces.py")
)["main"](recipe)
path = (
    ROOT
    / "Saved/RuntimeProof/TextureLandscape"
    / report["material"].split("/")[-2]
    / "result.json"
)
verifier = runpy.run_path(
    str(ROOT / "scripts/ue/verify_sa_calobra_generated_surface_map.py")
)
verifier["main"].__globals__["REPORT"] = path
verifier["main"]()
