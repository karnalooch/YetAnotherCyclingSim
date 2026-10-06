"""Prepare one material from verified saved sources in an isolated NullRHI run.

Never opens or saves a world. This is asset preparation, not rendering proof.
"""

import hashlib
import json
import runpy
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]


def main():
    actual = Path(unreal.Paths.project_dir()).resolve()
    if actual != ROOT or ROOT == Path("D:/yacs/project"):
        raise RuntimeError("Use an isolated checkout, never the authoring editor")
    command = unreal.SystemLibrary.get_command_line().lower()
    if "-nullrhi" not in command or "-run=pythonscript" not in command:
        raise RuntimeError("Requires a non-rendering Python commandlet")
    receipt_path = ROOT / "worldgen/materials/sa_calobra_repair_asset.json"
    receipt = json.loads(receipt_path.read_text())
    for row in receipt["assets"]:
        path = (ROOT / row["path"]).resolve()
        if not path.is_relative_to(ROOT / "Content"):
            raise RuntimeError("Asset path escapes Content")
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise RuntimeError("Saved input identity mismatch: " + row["path"])
    sources = {}
    for row in receipt["sources"]:
        name = row["asset"].split(".")[-1].removeprefix("T_")
        channel = next(c for c in ("nor_dx", "diff", "arm") if name.endswith("_" + c))
        role = name[: -(len(channel) + 1)]
        texture = unreal.load_asset(row["asset"])
        if not texture:
            raise RuntimeError("Cannot load verified texture: " + row["asset"])
        sources.setdefault(role, {})[channel] = texture
    weight_row = next(r for r in receipt["assets"] if "/VisualFill/" in r["path"])
    sources["weights"] = unreal.load_asset("/Game/" + weight_row["path"][8:-7])
    if not sources["weights"]:
        raise RuntimeError("Cannot load registered mask")
    state = {"repair_sources": sources}
    material = runpy.run_path(
        str(ROOT / "scripts/ue/build_sa_calobra_repaired_surface.py")
    )["build"](state, "candidate")
    if not unreal.EditorAssetLibrary.save_loaded_asset(
        material, only_if_is_dirty=False
    ):
        raise RuntimeError("Material save failed")
    package = material.get_path_name().split(".")[0]
    asset_file = ROOT / "Content" / (package.removeprefix("/Game/") + ".uasset")
    report = {
        "status": "PREPARED_NOT_RENDER_VERIFIED",
        "material": material.get_path_name(),
        "asset": asset_file.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(asset_file.read_bytes()).hexdigest(),
        "input_receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "producer_sha256": hashlib.sha256(
            (ROOT / "scripts/ue/build_sa_calobra_repaired_surface.py").read_bytes()
        ).hexdigest(),
        "parameters": state["repair_parameters"]["candidate"],
        "map_loaded_or_saved": False,
        "render_validation": "PENDING",
        "performance": "NOT_MEASURED",
    }
    output = ROOT / "Saved/RuntimeProof/MaterialRepair/offline-preparation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    unreal.log("YACS_REPAIR_OFFLINE_PREPARED " + str(output))


if __name__ == "__main__":
    main()
