"""Import the curated Stage 3G R1 source-asset slice into Unreal Engine.

The download cache is intentionally outside Git. This script imports only the
explicitly selected source files and renames the resulting Unreal assets to
stable project-owned paths under /Game/Prototype/Environment/Stage3G/Imported.

Required environment variables:
  YACS_STAGE3G_ASSET_CACHE  absolute path containing download-index.json
  YACS_STAGE3G_IMPORT_PROOF absolute JSON proof output path

This is editor authoring only. Runtime simulation never consumes source files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import unreal


CONTENT_ROOT = "/Game/Prototype/Environment/Stage3G/Imported"
TEXTURE_ROOT = CONTENT_ROOT + "/Textures"
MESH_ROOT = CONTENT_ROOT + "/Meshes"

TEXTURE_SPECS = {
    "sparse_grass": {
        "diffuse": "T_Stage3G_Meadow_BaseColor",
        "normal_dx": "T_Stage3G_Meadow_Normal",
        "roughness": "T_Stage3G_Meadow_Roughness",
    },
    "forrest_ground_03": {
        "diffuse": "T_Stage3G_ForestGround_BaseColor",
        "normal_dx": "T_Stage3G_ForestGround_Normal",
        "roughness": "T_Stage3G_ForestGround_Roughness",
    },
    "rocky_terrain": {
        "diffuse": "T_Stage3G_HighAlpine_BaseColor",
        "normal_dx": "T_Stage3G_HighAlpine_Normal",
        "roughness": "T_Stage3G_HighAlpine_Roughness",
    },
    "boulder_01": {
        "diffuse": "T_Stage3G_Boulder_BaseColor",
        "normal_dx": "T_Stage3G_Boulder_Normal",
        "roughness": "T_Stage3G_Boulder_Roughness",
    },
}

MODEL_SPECS = {
    "boulder_01": "SM_Stage3G_Boulder",
}


def log(message: str) -> None:
    unreal.log("[Stage3GImport] {}".format(message))


def fail(message: str) -> None:
    raise RuntimeError(message)


def ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        if not unreal.EditorAssetLibrary.make_directory(path):
            fail("failed to create content directory {}".format(path))


def canonical_asset_path(folder: str, name: str) -> str:
    return "{}/{}".format(folder.rstrip("/"), name)


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


def import_task(
    filename: Path,
    destination_path: str,
    *,
    fbx: bool = False,
) -> list[str]:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(filename))
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)

    if fbx:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        static_data = options.get_editor_property("static_mesh_import_data")
        static_data.set_editor_property("combine_meshes", True)
        static_data.set_editor_property("generate_lightmap_u_vs", True)
        task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths") or [])
    if not paths:
        fail("Unreal imported no objects from {}".format(filename))
    return [str(path) for path in paths]


def find_import_of_class(paths: list[str], expected_class: type) -> str:
    matches: list[str] = []
    for path in paths:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset and isinstance(asset, expected_class):
            matches.append(path)
    if not matches:
        fail(
            "imported objects contain no {}: {}".format(
                expected_class.__name__, ", ".join(paths)
            )
        )
    return sorted(matches)[0]


def rename_to_canonical(imported_path: str, canonical_path: str) -> Any:
    if imported_path != canonical_path:
        if unreal.EditorAssetLibrary.does_asset_exist(canonical_path):
            if not unreal.EditorAssetLibrary.delete_asset(canonical_path):
                fail("failed to replace existing asset {}".format(canonical_path))
        if not unreal.EditorAssetLibrary.rename_asset(imported_path, canonical_path):
            fail(
                "failed to rename imported asset {} -> {}".format(
                    imported_path, canonical_path
                )
            )

    asset = unreal.EditorAssetLibrary.load_asset(canonical_path)
    if not asset:
        fail("canonical imported asset cannot be loaded: {}".format(canonical_path))
    if not unreal.EditorAssetLibrary.save_asset(
        canonical_path, only_if_is_dirty=False
    ):
        fail("failed to save canonical asset {}".format(canonical_path))
    return asset


def configure_texture(texture: Any, map_type: str) -> None:
    if map_type in {"normal_dx", "roughness"}:
        texture.set_editor_property("srgb", False)

    if map_type == "normal_dx":
        try:
            texture.set_editor_property(
                "compression_settings",
                unreal.TextureCompressionSettings.TC_NORMALMAP,
            )
        except Exception as exc:
            unreal.log_warning(
                "[Stage3GImport] unable to force normal-map compression: {}".format(
                    exc
                )
            )
    texture.modify()


def choose_rows(
    rows: list[dict[str, Any]], asset_id: str, map_type: str | None
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("asset_id") == asset_id and row.get("map_type") == map_type
    ]
    return sorted(selected, key=lambda row: str(row.get("relative_path", "")))


def import_texture(
    cache_root: Path,
    row: dict[str, Any],
    canonical_name: str,
) -> dict[str, Any]:
    source = source_path(cache_root, row)
    imported = import_task(source, TEXTURE_ROOT)
    imported_path = find_import_of_class(imported, unreal.Texture2D)
    canonical = canonical_asset_path(TEXTURE_ROOT, canonical_name)
    texture = rename_to_canonical(imported_path, canonical)
    configure_texture(texture, str(row["map_type"]))
    if not unreal.EditorAssetLibrary.save_asset(
        canonical, only_if_is_dirty=False
    ):
        fail("failed to resave configured texture {}".format(canonical))
    return {
        "asset_id": row["asset_id"],
        "map_type": row["map_type"],
        "source": str(source),
        "source_md5": row.get("md5"),
        "destination": canonical,
        "class": texture.get_class().get_name(),
    }


def import_static_mesh(
    cache_root: Path,
    row: dict[str, Any],
    canonical_name: str,
) -> dict[str, Any]:
    source = source_path(cache_root, row)
    imported = import_task(source, MESH_ROOT, fbx=True)
    imported_path = find_import_of_class(imported, unreal.StaticMesh)
    canonical = canonical_asset_path(MESH_ROOT, canonical_name)
    mesh = rename_to_canonical(imported_path, canonical)
    return {
        "asset_id": row["asset_id"],
        "map_type": None,
        "source": str(source),
        "source_md5": row.get("md5"),
        "destination": canonical,
        "class": mesh.get_class().get_name(),
    }


def main() -> None:
    cache_value = os.environ.get("YACS_STAGE3G_ASSET_CACHE", "")
    proof_value = os.environ.get("YACS_STAGE3G_IMPORT_PROOF", "")
    if not cache_value:
        fail("YACS_STAGE3G_ASSET_CACHE is not set")
    if not proof_value:
        fail("YACS_STAGE3G_IMPORT_PROOF is not set")

    cache_root = Path(cache_value).resolve()
    index_path = cache_root / "download-index.json"
    if not index_path.is_file():
        fail("Stage 3G download index is missing: {}".format(index_path))

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    rows = list(payload.get("files") or [])
    if not rows:
        fail("Stage 3G download index contains no files")

    ensure_directory(CONTENT_ROOT)
    ensure_directory(TEXTURE_ROOT)
    ensure_directory(MESH_ROOT)

    imported: list[dict[str, Any]] = []

    for asset_id, maps in TEXTURE_SPECS.items():
        for map_type, canonical_name in maps.items():
            candidates = choose_rows(rows, asset_id, map_type)
            if not candidates:
                fail(
                    "download index has no {} / {} source".format(
                        asset_id, map_type
                    )
                )
            imported.append(
                import_texture(cache_root, candidates[0], canonical_name)
            )

    for asset_id, canonical_name in MODEL_SPECS.items():
        candidates = choose_rows(rows, asset_id, None)
        if not candidates:
            fail("download index has no {} FBX geometry".format(asset_id))
        imported.append(
            import_static_mesh(cache_root, candidates[0], canonical_name)
        )

    expected_count = sum(len(value) for value in TEXTURE_SPECS.values()) + len(
        MODEL_SPECS
    )
    if len(imported) != expected_count:
        fail(
            "import count mismatch: actual={} expected={}".format(
                len(imported), expected_count
            )
        )

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(
            {
                "stage3g_asset_import": "success",
                "source_provider": payload.get("provider", {}).get("name"),
                "resolution": payload.get("resolution"),
                "imported_count": len(imported),
                "imported": imported,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    log("SUCCESS: imported {} canonical Stage 3G R1 assets".format(len(imported)))


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GImport] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
