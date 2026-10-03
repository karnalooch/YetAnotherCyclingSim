"""Non-persistent height-texture readiness and native source evidence.

No height edits, resampling, material changes or map saves are performed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal


def _property(obj, name: str):
    try:
        value = obj.get_editor_property(name)
        if value is None or isinstance(value, (str, bool, int, float)):
            return value
        if hasattr(value, "get_path_name"):
            return value.get_path_name()
        return str(value)
    except Exception as exc:
        return {"unavailable": str(exc)}


def _file(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size < 100:
        raise RuntimeError(f"Native height export missing or empty: {path}")
    data = path.read_bytes()
    return {"file": path.name, "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def _export_sources(landscape, output: Path) -> list[dict]:
    # Component HeightmapTexture is not reflected in UE 5.8 Python. Use the
    # documented object iterator and exact owning package, without editing it.
    prefix = landscape.get_path_name().split(".", 1)[0] + "."
    textures = sorted(
        (obj for obj in unreal.ObjectIterator(unreal.Texture2D)
         if obj.get_path_name().startswith(prefix)),
        key=lambda obj: obj.get_path_name(),
    )
    if not textures:
        raise RuntimeError("No Texture2D source objects found in the Landscape package")
    before = {
        texture.get_path_name(): json.loads(
            unreal.YacsTextureAuditLibrary.describe_texture(texture)
        )
        for texture in textures
    }
    if not unreal.YacsTextureAuditLibrary.finish_texture_compilation(textures):
        raise RuntimeError("Native height-texture compilation did not complete")
    rows = []
    exported = 0
    for texture in textures:
        row = {"texture": texture.get_path_name(),
               "properties": {key: _property(texture, key) for key in (
                   "compression_settings", "srgb", "filter", "lod_group",
                   "mip_gen_settings", "lod_bias", "never_stream",
                   "lossy_compression_amount", "max_texture_size", "compression_none", "availability",
               )}}
        row["native_before_wait"] = before[row["texture"]]
        row["native_runtime"] = json.loads(
            unreal.YacsTextureAuditLibrary.describe_texture(texture)
        )
        if "error" in row["native_runtime"]:
            raise RuntimeError(str(row["native_runtime"]))
        if "heightmap" in str(row["properties"]["lod_group"]).lower() and exported < 8:
            path = output / f"source-height-{exported}.tga"
            path.unlink(missing_ok=True)
            task = unreal.AssetExportTask()
            task.object = texture
            task.filename = str(path)
            task.automated = True
            task.prompt = False
            task.replace_identical = True
            task.exporter = unreal.TextureExporterTGA()
            if not unreal.Exporter.run_asset_export_task(task):
                raise RuntimeError(f"Source texture export failed: {row['texture']}")
            row["source_export"] = _file(path)
            exported += 1
        rows.append(row)
    return rows


def capture_macro_height_evidence(world, landscape, components, output: Path) -> dict:
    """Inspect the persisted Landscape before transient road deformation."""
    output = Path(output) / "macro-height-audit"
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 4,
        "saved_to_map": False,
        "height_edits_applied": False,
        "resampling_applied": False,
        "native_texture_compilation_wait": True,
        "landscape": landscape.get_path_name(),
        "transform": str(landscape.get_actor_transform()),
        "component_count": len(components),
        "landscape_properties": {key: _property(landscape, key) for key in (
            "enable_nanite", "collision_mip_level", "simple_collision_mip_level",
        )},
    }
    try:
        report["source_textures"] = _export_sources(landscape, output)
        report["gpu_height_export"] = {
            "status": "UNAVAILABLE",
            "reason": "Runs 87/88 returned an all-zero render target; not height evidence",
        }
        report["status"] = "SOURCE_PRESERVED_TEXTURE_COMPILATION_READY"
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        (output / "macro-height-audit.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    return report
