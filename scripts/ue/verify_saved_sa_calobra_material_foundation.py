"""Fresh-process saved-consumer proof, restricted to an isolated checkout."""

import json
import os
import runpy
import subprocess
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]


def verify():
    foundation = runpy.run_path(
        str(REPO / "scripts/ue/sa_calobra_material_foundation.py")
    )
    canonical = Path(foundation["load_workspace"]()["project"]).resolve()
    if REPO == canonical:
        raise RuntimeError(
            "Fresh verification must not load maps in the authoring project"
        )
    if (
        Path(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        ).resolve()
        != REPO
    ):
        raise RuntimeError("Wrong verification project checkout")
    head = os.environ["YACS_2B_EXPECTED_HEAD"]
    if len(head) != 40 or any(char not in "0123456789abcdef" for char in head):
        raise RuntimeError("Invalid exact SHA")
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    if actual != head:
        raise RuntimeError("Fresh verification exact SHA differs")
    report_path = Path(os.environ["YACS_2B_RELOAD_REPORT"]).resolve()
    if report_path.exists():
        raise RuntimeError("Existing reload evidence must not be overwritten")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    recipe = json.loads(
        (REPO / "worldgen/materials/sa_calobra_foundation.json").read_text(
            encoding="utf8"
        )
    )
    map_file = REPO / "Content" / (recipe["map"].removeprefix("/Game/") + ".umap")
    receipt = json.loads(
        (REPO / "worldgen/materials/sa_calobra_foundation_asset.json").read_text(
            encoding="utf8"
        )
    )
    if foundation["digest"](map_file) != receipt["saved_map_sha256"]:
        raise RuntimeError("Frozen saved map bytes differ before loading")
    world = unreal.EditorLoadingAndSavingUtils.load_map(str(map_file))
    if world is None or world.get_path_name().split(".")[0] != recipe["map"]:
        raise RuntimeError("Frozen saved map did not load")
    consume = runpy.run_path(
        str(REPO / "scripts/ue/consume_saved_sa_calobra_material_foundation.py")
    )["consume"]
    report = consume(report_path, require_fresh=True)
    report.update(
        exact_sha=head,
        verification_checkout=str(REPO),
        verification_script_sha256=foundation["digest"](__file__),
        render_admission="NOT_PROVEN",
    )
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    unreal.log("YACS 2B fresh saved consumer verified; no render/performance admission")


if __name__ == "__main__":
    verify()
