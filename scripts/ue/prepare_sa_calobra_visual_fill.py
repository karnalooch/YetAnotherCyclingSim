"""Import a verified appearance-only weight texture; never assign or save a map."""

import hashlib
import json
import os
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "worldgen/materials/visual_fill"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Insufficient memory headroom; no import performed")
    manifest = PACKAGE / "material-input-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    content = {k: v for k, v in data.items() if k != "fingerprint"}
    fingerprint = hashlib.sha256(
        json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if (
        fingerprint != data["fingerprint"]
        or data["status"] != "PRESENTATION_VISUAL_FILL_CANDIDATE"
    ):
        raise RuntimeError("Unexpected visual-fill manifest")
    if data["geometry_mutation"] is not False or data["grid"]["transform"] != [
        0.5,
        0,
        483000,
        0,
        -0.5,
        4409516.5,
    ]:
        raise RuntimeError("Frozen coordinate contract mismatch")
    producer = ROOT / "scripts/assets/prepare_sa_calobra_visual_fill.py"
    if (
        hashlib.sha256(producer.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        != data["producer_sha256_lf"]
    ):
        raise RuntimeError("Producer identity changed")
    for row in data["outputs"]:
        if (
            Path(row["path"]).name != row["path"]
            or digest(PACKAGE / row["path"]) != row["sha256"]
        ):
            raise RuntimeError("Mask identity changed")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world_path = world.get_path_name()
    if (
        world_path.split(".")[0]
        != "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
    ):
        raise RuntimeError("Keep the accepted map open; no automatic map switch")
    map_file = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
    map_hash = digest(map_file)
    task = unreal.AssetImportTask()
    destination = "/Game/Generated/YACS/VisualFill/" + uuid.uuid4().hex
    for prop, value in {
        "filename": str(PACKAGE / "material-weights.png"),
        "destination_path": destination,
        "destination_name": "T_VisualFillWeights",
        "automated": True,
        "replace_existing": False,
        "save": False,
    }.items():
        task.set_editor_property(prop, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = task.get_editor_property("imported_object_paths")
    if len(paths) != 1:
        raise RuntimeError("Expected exactly one mask texture")
    texture = unreal.load_asset(paths[0])
    settings = {
        "srgb": False,
        "filter": unreal.TextureFilter.TF_BILINEAR,
        "address_x": unreal.TextureAddress.TA_CLAMP,
        "address_y": unreal.TextureAddress.TA_CLAMP,
        "mip_gen_settings": unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
        "compression_settings": unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
        "never_stream": True,
    }
    for prop, value in settings.items():
        texture.set_editor_property(prop, value)
        if texture.get_editor_property(prop) != value:
            raise RuntimeError("Texture setting readback failed: " + prop)
    if digest(map_file) != map_hash or world.get_path_name() != world_path:
        raise RuntimeError("Map identity changed during import")
    report = {
        "status": "NATIVE_MASK_IMPORTED_NOT_ASSIGNED",
        "asset": paths[0],
        "manifest_sha256": digest(manifest),
        "map_sha256": map_hash,
        "map_saved": False,
        "texture_saved": False,
        "sampling": "bilinear_linear_data",
        "geometry_mutation": False,
        "material_integration": "PENDING",
        "memory_before": memory,
    }
    out = ROOT / "Saved/RuntimeProof/VisualFill"
    out.mkdir(parents=True, exist_ok=True)
    (out / (str(os.getpid()) + ".json")).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    unreal.log("YACS_VISUAL_FILL " + json.dumps(report))


if __name__ == "__main__":
    main()
