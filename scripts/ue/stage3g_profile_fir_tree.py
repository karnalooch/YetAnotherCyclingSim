"""Profile the curated Stage 3G R2 Fir Tree 01 source asset in Unreal.

The source cache remains outside Git. This script imports every selected Fir Tree
FBX into a transient editor-only path with save=False, records mesh/LOD/material/
Nanite/bounds metrics, and writes a JSON proof for R2 asset selection.

Required environment variables:
  YACS_STAGE3G_ASSET_CACHE  absolute source cache containing download-index.json
  YACS_STAGE3G_FIR_PROFILE absolute JSON proof output path
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any

import unreal


ASSET_ID = "fir_tree_01"
PROFILE_ROOT = "/Game/Transient/YACS/Stage3GR2Profile/FirTree"


def log(message: str) -> None:
    unreal.log("[Stage3GR2FirProfile] {}".format(message))


def fail(message: str) -> None:
    raise RuntimeError(message)


def source_path(cache_root: Path, row: dict[str, Any]) -> Path:
    path = (cache_root / str(row["relative_path"])).resolve()
    try:
        path.relative_to(cache_root.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "download-index path escapes the Stage 3G cache: {}".format(path)
        ) from exc
    if not path.is_file():
        fail("source file is missing: {}".format(path))
    return path


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return name[:72] or "source"


def vector_payload(value: Any) -> dict[str, float]:
    return {
        "x": float(value.x),
        "y": float(value.y),
        "z": float(value.z),
    }


def read_nanite_enabled(mesh: unreal.StaticMesh) -> bool:
    settings = mesh.get_editor_property("nanite_settings")
    try:
        return bool(settings.get_editor_property("enabled"))
    except Exception:
        return bool(getattr(settings, "enabled", False))


def material_names(mesh: unreal.StaticMesh) -> list[str]:
    names: list[str] = []
    for index in range(len(mesh.get_editor_property("static_materials"))):
        material = mesh.get_material(index)
        names.append(material.get_name() if material else "<none>")
    return names


def mesh_profile(mesh: unreal.StaticMesh, source: Path, object_path: str) -> dict[str, Any]:
    lod_count = int(mesh.get_num_lods())
    if lod_count <= 0:
        fail("{} reports zero LODs".format(object_path))

    lods: list[dict[str, int]] = []
    for lod_index in range(lod_count):
        lods.append(
            {
                "lod": lod_index,
                "triangles": int(mesh.get_num_triangles(lod_index)),
                "vertices": int(mesh.get_num_vertices(lod_index)),
                "sections": int(mesh.get_num_sections(lod_index)),
                "tex_coords": int(mesh.get_num_tex_coords(lod_index)),
            }
        )

    bounds = mesh.get_bounds()
    extent = bounds.get_editor_property("box_extent")
    origin = bounds.get_editor_property("origin")
    nanite_enabled = read_nanite_enabled(mesh)

    nanite_triangles = 0
    nanite_vertices = 0
    if nanite_enabled:
        nanite_triangles = int(mesh.get_num_nanite_triangles())
        nanite_vertices = int(mesh.get_num_nanite_vertices())

    return {
        "source": str(source),
        "object_path": object_path,
        "mesh_name": mesh.get_name(),
        "lod_count": lod_count,
        "lods": lods,
        "material_count": len(mesh.get_editor_property("static_materials")),
        "materials": material_names(mesh),
        "nanite_enabled": nanite_enabled,
        "nanite_triangles": nanite_triangles,
        "nanite_vertices": nanite_vertices,
        "bounds_cm": {
            "origin": vector_payload(origin),
            "box_extent": vector_payload(extent),
            "size": {
                "x": float(extent.x) * 2.0,
                "y": float(extent.y) * 2.0,
                "z": float(extent.z) * 2.0,
            },
            "sphere_radius": float(bounds.get_editor_property("sphere_radius")),
        },
    }


def import_source(source: Path, source_index: int) -> list[dict[str, Any]]:
    destination = "{}/S{:03d}_{}".format(
        PROFILE_ROOT,
        source_index,
        safe_name(source.stem),
    )
    if not unreal.EditorAssetLibrary.does_directory_exist(destination):
        if not unreal.EditorAssetLibrary.make_directory(destination):
            fail("failed to create transient profile directory {}".format(destination))

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    static_data = options.get_editor_property("static_mesh_import_data")
    static_data.set_editor_property("combine_meshes", False)
    static_data.set_editor_property("generate_lightmap_u_vs", False)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = [str(path) for path in (task.get_editor_property("imported_object_paths") or [])]
    if not paths:
        fail("Unreal imported no objects from {}".format(source))

    meshes: list[dict[str, Any]] = []
    for path in sorted(paths):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset and isinstance(asset, unreal.StaticMesh):
            meshes.append(mesh_profile(asset, source, path))

    if not meshes:
        fail("FBX import produced no StaticMesh objects: {}".format(source))
    return meshes


def main() -> None:
    cache_value = os.environ.get("YACS_STAGE3G_ASSET_CACHE", "")
    proof_value = os.environ.get("YACS_STAGE3G_FIR_PROFILE", "")
    if not cache_value:
        fail("YACS_STAGE3G_ASSET_CACHE is not set")
    if not proof_value:
        fail("YACS_STAGE3G_FIR_PROFILE is not set")

    cache_root = Path(cache_value).resolve()
    index_path = cache_root / "download-index.json"
    if not index_path.is_file():
        fail("Stage 3G download index is missing: {}".format(index_path))

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    rows = [
        row
        for row in list(payload.get("files") or [])
        if row.get("asset_id") == ASSET_ID
        and row.get("map_type") is None
        and str(row.get("relative_path", "")).lower().endswith(".fbx")
    ]
    rows.sort(key=lambda row: str(row.get("relative_path", "")))
    if not rows:
        fail("download index contains no fir_tree_01 FBX geometry")

    meshes: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        source = source_path(cache_root, row)
        sources.append(
            {
                "path": str(source),
                "relative_path": row.get("relative_path"),
                "size_bytes": int(row.get("size") or source.stat().st_size),
                "md5": row.get("md5"),
            }
        )
        meshes.extend(import_source(source, index))

    if not meshes:
        fail("Fir Tree profile contains no imported meshes")

    ranked = sorted(
        meshes,
        key=lambda item: (
            int(item["lods"][0]["triangles"]),
            int(item["lods"][0]["vertices"]),
            item["mesh_name"],
        ),
    )

    total_source_bytes = sum(int(item["size_bytes"]) for item in sources)
    proof = {
        "stage3g_r2_fir_profile": "success",
        "asset_id": ASSET_ID,
        "source_provider": payload.get("provider", {}).get("name"),
        "resolution": payload.get("resolution"),
        "source_fbx_count": len(sources),
        "source_bytes": total_source_bytes,
        "mesh_count": len(meshes),
        "meshes": meshes,
        "ranking_by_lod0_triangles": [
            {
                "mesh_name": item["mesh_name"],
                "object_path": item["object_path"],
                "lod0_triangles": int(item["lods"][0]["triangles"]),
                "lod_count": int(item["lod_count"]),
                "height_cm": float(item["bounds_cm"]["size"]["z"]),
                "material_count": int(item["material_count"]),
                "nanite_enabled": bool(item["nanite_enabled"]),
            }
            for item in ranked
        ],
    }

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    try:
        unreal.EditorAssetLibrary.delete_directory(PROFILE_ROOT)
    except Exception as exc:
        unreal.log_warning(
            "[Stage3GR2FirProfile] transient cleanup warning: {}".format(exc)
        )

    log(
        "SUCCESS: profiled {} FBX sources / {} meshes; lightest LOD0={} tris".format(
            len(sources),
            len(meshes),
            ranked[0]["lods"][0]["triangles"],
        )
    )


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GR2FirProfile] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
