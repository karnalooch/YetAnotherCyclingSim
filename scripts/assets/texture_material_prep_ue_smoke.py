"""UE Python smoke: run ONLY in a disposable marked proof project, with a GPU.

Registers only YacsTextureTools. Imports a new diagnostic PNG in a fresh folder.
No network server, live world, existing asset, or Save All operation is used.
"""

import json
import struct
import time
import uuid
import zlib
from pathlib import Path

import unreal

project = Path(unreal.Paths.project_dir()).resolve()
if not (project / ".yacs-texture-prep-proof").is_file():
    raise RuntimeError("Refusing to run outside a marked disposable proof project")

saved = Path(unreal.Paths.project_saved_dir()).resolve()
saved.mkdir(exist_ok=True)
proof = saved / ("texture-smoke-" + uuid.uuid4().hex)
proof.mkdir()


def write_json(name, value):
    with (proof / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def chunk(kind, data):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


# Deliberately mismatched borders plus periodic detail; no external input.
rows = bytearray()
for y in range(128):
    rows.append(0)
    for x in range(128):
        v = 50 + x + (y // 16 % 2) * 20 + (x // 8 % 2) * 12
        rows.extend((v, min(v + 10, 255), max(v - 10, 0)))
png = b"\x89PNG\r\n\x1a\n" + chunk(
    b"IHDR", struct.pack(">IIBBBBB", 128, 128, 8, 2, 0, 0, 0)
)
png += chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
source_file = proof / "fixture.png"
source_file.write_bytes(png)
task = unreal.AssetImportTask()
task.filename = str(source_file)
task.destination_path = (
    "/Game/Generated/YACS/TextureMaterialPrep/Fixtures/" + uuid.uuid4().hex
)
task.destination_name = "T_Diagnostic"
task.automated = True
task.replace_existing = False
task.save = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
source_path = task.imported_object_paths[0]

unreal.ToolsetRegistry.register_toolset_class(unreal.YacsTextureTools)
schema = json.loads(
    unreal.ToolsetRegistry.get_toolset_json_schema(unreal.YacsTextureTools)
)
write_json("toolset-schema.json", schema)
registry_probe = unreal.ToolsetRegistry.execute_tool(
    schema["name"], "InspectCapabilities", "{}"
)
capabilities = json.loads(unreal.YacsTextureTools.inspect_capabilities())
write_json("capabilities.json", capabilities)
if capabilities["status"] != "available_opt_in":
    raise RuntimeError(capabilities)

recipe = unreal.YacsTextureRecipe()
recipe.resolution = 128
recipe.seam_blend_width = 0.15
recipe.de_light_strength = 0.25
recipe.macro_variation = 0.5
bad_recipe = unreal.YacsTextureRecipe()
bad_recipe.resolution = 8192
negative = {
    "bad_resolution": json.loads(
        unreal.YacsTextureTools.prepare_texture(source_path, bad_recipe)
    ),
    "outside_game": json.loads(
        unreal.YacsTextureTools.prepare_texture("/Engine/Bad.Bad", recipe)
    ),
    "unknown_job": json.loads(unreal.YacsTextureTools.export_pbr_set("0" * 32)),
}
if any(result["status"] != "rejected" for result in negative.values()):
    raise RuntimeError(negative)
write_json("negative-cases.json", negative)
prepared = json.loads(unreal.YacsTextureTools.prepare_texture(source_path, recipe))
write_json("prepared.json", prepared)
if prepared.get("status") != "prepared":
    raise RuntimeError(prepared)
job_id = prepared["job_id"]
assert (
    json.loads(unreal.YacsTextureTools.export_pbr_set(job_id))["status"] == "rejected"
)
started = time.monotonic()
write_json(
    "render-request.json", json.loads(unreal.YacsTextureTools.render_preview(job_id))
)
phase = "rendering"


def tick(_delta):
    global phase
    try:
        if not (proof / "registry-probe.json").exists() and registry_probe.is_complete:
            if registry_probe.error:
                raise RuntimeError(registry_probe.error)
            write_json("registry-probe.json", json.loads(registry_probe.value))
        status = json.loads(unreal.YacsTextureTools.get_job_status(job_id))
        if (
            status["status"] in ("failed", "timeout_draining", "rejected")
            or time.monotonic() - started > 240
        ):
            raise RuntimeError(status)
        if phase == "rendering" and status["status"] == "rendered":
            write_json("rendered.json", status)
            write_json(
                "export-request.json",
                json.loads(unreal.YacsTextureTools.export_pbr_set(job_id)),
            )
            phase = "exporting"
        elif phase == "exporting" and status["status"] == "export_completed_unverified":
            result = json.loads(unreal.YacsTextureTools.validate_texture(job_id))
            write_json("result.json", result)
            if result["status"] != "exported_review_required":
                raise RuntimeError(result)
            assert (
                json.loads(unreal.YacsTextureTools.export_pbr_set(job_id))["status"]
                == "rejected"
            )
            assert (
                json.loads(unreal.YacsTextureTools.validate_texture(job_id))["status"]
                == "rejected"
            )
            unreal.log("YACS_TEXTURE_SMOKE_COMPLETE " + str(proof))
            unreal.unregister_slate_post_tick_callback(handle)
            unreal.SystemLibrary.quit_editor()
    except Exception as exc:
        write_json("failure.json", {"error": str(exc)})
        unreal.log_error("YACS_TEXTURE_SMOKE_FAILED " + str(exc))
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()


handle = unreal.register_slate_post_tick_callback(tick)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
