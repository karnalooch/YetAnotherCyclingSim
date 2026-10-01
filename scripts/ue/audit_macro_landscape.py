"""Read-only CPU/source and packed-RG height evidence for macro recovery.

No height edits, resampling, material changes or map saves are performed here.
"""
from __future__ import annotations

import hashlib
import json
import struct
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


def _png_dimensions(path: Path) -> list[int]:
    header = path.read_bytes()[:33]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RuntimeError("Native height export is not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    if (width, height) != (4033, 4033):
        raise RuntimeError(f"Native height export was resized: {width}x{height}")
    return [width, height]


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
    rows = []
    exported = 0
    for texture in textures:
        row = {"texture": texture.get_path_name(),
               "properties": {key: _property(texture, key) for key in (
                   "compression_settings", "srgb", "filter", "lod_group",
                   "mip_gen_settings", "lod_bias", "never_stream",
                   "lossy_compression_amount", "max_texture_size",
               )}}
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
        "schema_version": 2,
        "saved_to_map": False,
        "height_edits_applied": False,
        "resampling_applied": False,
        "landscape": landscape.get_path_name(),
        "transform": str(landscape.get_actor_transform()),
        "component_count": len(components),
        "landscape_properties": {key: _property(landscape, key) for key in (
            "enable_nanite", "collision_mip_level", "simple_collision_mip_level",
        )},
    }
    target = None
    try:
        report["source_textures"] = _export_sources(landscape, output)
        # Do not set editor properties on the allocated target: PostEditChange
        # asks a >2048 allocation dialog and unattended mode can resize it.
        target = unreal.RenderingLibrary.create_render_target2d(
            world, width=4033, height=4033,
            format=unreal.TextureRenderTargetFormat.RTF_RGBA8,
            auto_generate_mip_maps=False,
        )
        if target is None:
            raise RuntimeError("Could not allocate packed-height render target")
        actual_size = [int(target.size_x), int(target.size_y)]
        report["render_target"] = {"actual_size": actual_size,
                                   "target_gamma": _property(target, "target_gamma"),
                                   "srgb": _property(target, "srgb")}
        if actual_size != [4033, 4033]:
            raise RuntimeError(f"Packed-height allocation was resized: {actual_size}")
        if not landscape.landscape_export_heightmap_to_render_target(
            target, export_height_into_rg_channel=True,
            export_landscape_proxies=True,
        ):
            raise RuntimeError("Native Landscape heightmap export returned false")
        png = output / "combined-height-rg.png"
        png.unlink(missing_ok=True)
        unreal.RenderingLibrary.export_render_target(world, target, str(output), png.name)
        report["combined_height_export"] = {
            **_file(png), "packing": "uint16 = (R << 8) | G",
            "target_format": "RTF_RGBA8", "size": _png_dimensions(png),
        }
        samples = []
        for x, y in ((1000, 1000), (2016, 2016), (2800, 900)):
            color = unreal.RenderingLibrary.read_render_target_raw_pixel(
                world, target, x, y, normalize=False
            )
            samples.append([x, y, float(color.r), float(color.g)])
        report["raw_height_samples"] = samples
        if not any(row[2] != 0 or row[3] != 0 for row in samples):
            raise RuntimeError("Native export returned only clear height samples")
        report["status"] = "EXPORTED_FOR_DIAGNOSIS"
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        if target is not None:
            unreal.RenderingLibrary.release_render_target2d(target)
        (output / "macro-height-audit.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    return report
