"""Read-only native height evidence for the macro-Landscape recovery proof.

Export height bytes, not a lit scene or a grayscale screenshot. No height edits,
source resampling, material changes or map saves are performed here.
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
    return {"file": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def capture_macro_height_evidence(world, landscape, components, output: Path) -> dict:
    """Inspect the persisted Landscape before transient road deformation."""
    output = Path(output) / "macro-height-audit"
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "saved_to_map": False,
        "height_edits_applied": False,
        "resampling_applied": False,
        "landscape": landscape.get_path_name(),
        "transform": str(landscape.get_actor_transform()),
        "component_count": len(components),
        "landscape_properties": {key: _property(landscape, key) for key in (
            "enable_nanite", "collision_mip_level", "simple_collision_mip_level",
            "component_size_quads", "subsection_size_quads", "num_subsections",
        )},
    }
    try:
        # Exact persisted grid dimensions: 32*126+1. RG stores the two bytes
        # separately; R-only RGBA16F would itself discard height precision.
        target = unreal.RenderingLibrary.create_render_target2d(
            world, width=4033, height=4033,
            format=unreal.TextureRenderTargetFormat.RTF_RGBA8,
            auto_generate_mip_maps=False,
        )
        if target is None:
            raise RuntimeError("Could not allocate packed-height render target")
        target.set_editor_property("target_gamma", 1.0)
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
            "target_format": "RTF_RGBA8", "target_gamma": 1.0,
            "size": [4033, 4033],
        }
        unreal.RenderingLibrary.release_render_target2d(target)

        # Source texture access is version-dependent. Record unavailable
        # properties explicitly rather than pretending they were inspected.
        ordered = sorted(components, key=lambda c: c.get_path_name())
        indices = sorted(set([0, len(ordered)//4, len(ordered)//2,
                              3*len(ordered)//4, len(ordered)-1]))
        texture_rows = []
        seen = set()
        for i in indices:
            component = ordered[i]
            row = {"component": component.get_path_name(),
                   "location": str(component.get_world_location()),
                   "heightmap_scale_bias": _property(component, "heightmap_scale_bias")}
            try:
                texture = component.get_editor_property("heightmap_texture")
                if texture is None:
                    raise RuntimeError("heightmap_texture is null")
                row["texture"] = texture.get_path_name()
                row["properties"] = {key: _property(texture, key) for key in (
                    "compression_settings", "srgb", "filter", "lod_group",
                    "mip_gen_settings", "lod_bias", "never_stream",
                    "lossy_compression_amount", "max_texture_size",
                )}
                if row["texture"] not in seen:
                    path = output / f"source-height-{i}.tga"
                    path.unlink(missing_ok=True)
                    task = unreal.AssetExportTask()
                    task.object = texture
                    task.filename = str(path)
                    task.automated = True
                    task.prompt = False
                    task.replace_identical = True
                    task.exporter = unreal.TextureExporterTGA()
                    if unreal.Exporter.run_asset_export_task(task):
                        row["source_export"] = _file(path)
                    else:
                        row["source_export_unavailable"] = "TextureExporterTGA returned false"
                    seen.add(row["texture"])
            except Exception as exc:
                row["source_texture_unavailable"] = str(exc)
            texture_rows.append(row)
        report["source_textures"] = texture_rows
        report["status"] = "EXPORTED_FOR_DIAGNOSIS"
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        raise
    finally:
        (output / "macro-height-audit.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
    return report
