"""Fresh-editor durability proof for the latest completed isolated texture run."""

import hashlib
import json
import re
import uuid
from pathlib import Path

import unreal

project = Path(unreal.Paths.project_dir()).resolve()
if not (project / ".yacs-texture-prep-proof").is_file():
    raise RuntimeError("Requires a marked disposable proof project")
root = (
    Path(unreal.Paths.project_saved_dir()).resolve()
    / "RuntimeProof/TextureMaterialPrep"
)
receipt_path = max(root.glob("*/ue-receipt.json"), key=lambda p: p.stat().st_mtime)
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
job = receipt["job_id"]
if not re.fullmatch("[0-9A-Fa-f]{32}", job):
    raise RuntimeError("Invalid run identity")
folder = "/Game/Generated/YACS/TextureMaterialPrep/Runs/" + job
if (
    receipt["output_folder"] != folder
    or receipt["status"] != "exported_review_required"
):
    raise RuntimeError("Invalid output receipt")
graph_package = (
    project
    / "Content/Generated/YACS/TextureMaterialPrep/Runs"
    / job
    / "TG_YACS_MaterialPrep.uasset"
)
if (
    hashlib.sha1(graph_package.read_bytes()).hexdigest().upper()
    != receipt["graph_package_sha1"].upper()
):
    raise RuntimeError("Graph changed after export")
graph = unreal.load_asset(folder + "/TG_YACS_MaterialPrep")
if not isinstance(graph, unreal.TextureGraph):
    raise RuntimeError("Saved graph did not reopen")
output = receipt_path.parent / ("reopen-" + uuid.uuid4().hex)
output.mkdir()
results = {}
for role in ("BaseColor", "Height", "Normal", "Roughness", "MacroMask"):
    texture = unreal.load_asset(folder + "/" + role)
    if not isinstance(texture, unreal.Texture2D):
        raise RuntimeError("Missing Texture2D: " + role)
    # Platform mips may still be compiling immediately after load. Actual saved
    # source dimensions are checked from exported PNGs by the offline comparator.
    platform_size = [texture.blueprint_get_size_x(), texture.blueprint_get_size_y()]
    if texture.get_editor_property("srgb") != (role == "BaseColor"):
        raise RuntimeError("Reopened sRGB differs")
    expected = (
        unreal.TextureCompressionSettings.TC_NORMALMAP
        if role == "Normal"
        else (
            unreal.TextureCompressionSettings.TC_DEFAULT
            if role == "BaseColor"
            else unreal.TextureCompressionSettings.TC_MASKS
        )
    )
    if texture.get_editor_property("compression_settings") != expected:
        raise RuntimeError("Reopened compression differs")
    task = unreal.AssetExportTask()
    task.object = texture
    task.exporter = unreal.TextureExporterPNG()
    task.filename = str(output / (role + ".png"))
    task.automated = True
    task.prompt = False
    task.replace_identical = False
    if not unreal.Exporter.run_asset_export_task(task):
        raise RuntimeError("Reopened pixel readback failed: " + role)
    results[role] = {
        "asset": texture.get_path_name(),
        "settings": "matched",
        "platform_size_at_load": platform_size,
        "pixel_comparison": "pending_offline",
    }
with (output / "reopen.json").open("x", encoding="utf-8") as stream:
    json.dump(
        {"job_id": job, "status": "reopened_settings_verified", "outputs": results},
        stream,
        indent=2,
    )
unreal.log("YACS_TEXTURE_REOPEN_COMPLETE " + str(output))
