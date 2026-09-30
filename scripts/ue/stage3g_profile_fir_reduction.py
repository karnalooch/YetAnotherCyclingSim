"""Profile transient LOD reduction chains for a Stage 3G R2 conifer source.

This is a measurement gate, not persistent asset authoring. The selected
source mesh is imported into transient editor paths, several LOD
chains are generated with the UE 5.8 Static Mesh Editor Subsystem when it is
available. UnrealEditor-Cmd Python commandlets may not instantiate that editor
subsystem, so the script deliberately falls back to EditorStaticMeshLibrary
from Editor Scripting Utilities. Actual triangle/vertex counts are written to
JSON regardless of backend.

Required environment variables:
  YACS_STAGE3G_ASSET_CACHE       absolute source cache containing download-index.json
  YACS_STAGE3G_FIR_REDUCTION     absolute JSON proof output path
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import unreal


ASSET_ID = os.environ.get("YACS_STAGE3G_REDUCTION_ASSET_ID", "fir_tree_01").strip()
SOURCE_MESH_NAME = os.environ.get(
    "YACS_STAGE3G_REDUCTION_SOURCE_MESH", "fir_tree_01_c_LOD0"
).strip()
PROFILE_ROOT = "/Game/Transient/YACS/Stage3GR2ReductionProfile"

PROFILES: dict[str, list[tuple[float, float]]] = {
    "conservative": [
        (1.0, 1.0),
        (0.50, 0.60),
        (0.20, 0.30),
        (0.06, 0.12),
    ],
    "balanced": [
        (1.0, 1.0),
        (0.30, 0.55),
        (0.10, 0.25),
        (0.025, 0.10),
    ],
    "aggressive": [
        (1.0, 1.0),
        (0.18, 0.50),
        (0.05, 0.22),
        (0.0125, 0.08),
    ],
}


def log(message: str) -> None:
    unreal.log("[Stage3GR2FirReduction] {}".format(message))


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


def import_selected_variant(source: Path, profile_name: str) -> unreal.StaticMesh:
    profile_root = "{}/{}".format(PROFILE_ROOT, profile_name)
    staging = "{}/Import".format(profile_root)
    isolated = "{}/Selected".format(profile_root)
    isolated_asset = "{}/{}".format(isolated, SOURCE_MESH_NAME)

    for directory in (staging, isolated):
        if not unreal.EditorAssetLibrary.does_directory_exist(directory):
            if not unreal.EditorAssetLibrary.make_directory(directory):
                fail("failed to create transient directory {}".format(directory))

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", staging)
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
    paths = [
        str(path)
        for path in (task.get_editor_property("imported_object_paths") or [])
    ]
    if not paths:
        fail("Unreal imported no objects from {}".format(source))

    selected_path: str | None = None
    static_mesh_names: list[str] = []
    for imported_path in sorted(paths):
        asset = unreal.EditorAssetLibrary.load_asset(imported_path)
        if not asset or not isinstance(asset, unreal.StaticMesh):
            continue
        static_mesh_names.append(asset.get_name())
        if asset.get_name().lower() == SOURCE_MESH_NAME.lower():
            if selected_path is not None:
                fail("multiple {} meshes were imported".format(SOURCE_MESH_NAME))
            selected_path = imported_path

    asset = None
    if selected_path is None:
        fail(
            "expected {} in imported static meshes: {}".format(
                SOURCE_MESH_NAME,
                ", ".join(static_mesh_names),
            )
        )

    # The Poly Haven FBX contains A/B/C variants. Keeping all three imported
    # objects alive while reducing C makes UE's async StaticMesh compiler budget
    # several GiB for geometry that R2 will never scatter. Duplicate only C into
    # a clean transient package, then delete the whole staging import before
    # asking the mesh reducer to build LODs.
    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        selected_path,
        isolated_asset,
    )
    if not duplicated or not isinstance(duplicated, unreal.StaticMesh):
        fail(
            "failed to isolate {} from multi-variant FBX import".format(
                SOURCE_MESH_NAME
            )
        )

    selected_path = None
    paths = []
    static_mesh_names = []
    if not unreal.EditorAssetLibrary.delete_directory(staging):
        fail("failed to remove heavy FBX staging directory {}".format(staging))

    # UE 5.8 exposes an immediate module-level GC entry point. Purge references
    # to the discarded A/B source meshes before LOD reduction so the reducer is
    # budgeted against the selected ~505k-triangle C mesh only.
    unreal.collect_garbage()

    reloaded = unreal.EditorAssetLibrary.load_asset(isolated_asset)
    if not reloaded or not isinstance(reloaded, unreal.StaticMesh):
        fail("isolated selected mesh cannot be reloaded after staging cleanup")

    log(
        "isolated {} at {} before LOD reduction".format(
            SOURCE_MESH_NAME,
            isolated_asset,
        )
    )
    return reloaded


def reduction_options(settings: list[tuple[float, float]]) -> Any:
    values = []
    for percent_triangles, screen_size in settings:
        value = unreal.StaticMeshReductionSettings()
        value.set_editor_property("percent_triangles", float(percent_triangles))
        value.set_editor_property("screen_size", float(screen_size))
        values.append(value)

    options = unreal.StaticMeshReductionOptions()
    options.set_editor_property("auto_compute_lod_screen_size", False)
    options.set_editor_property("reduction_settings", values)
    return options


def set_lods(
    mesh: unreal.StaticMesh,
    settings: list[tuple[float, float]],
) -> tuple[int, str]:
    options = reduction_options(settings)

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if subsystem:
        return int(subsystem.set_lods(mesh, options)), "StaticMeshEditorSubsystem"

    library = getattr(unreal, "EditorStaticMeshLibrary", None)
    if library is None:
        fail(
            "StaticMeshEditorSubsystem is unavailable and "
            "EditorStaticMeshLibrary fallback is unavailable"
        )

    log(
        "StaticMeshEditorSubsystem unavailable in commandlet; "
        "using EditorStaticMeshLibrary.set_lods fallback"
    )
    return int(library.set_lods(mesh, options)), "EditorStaticMeshLibrary"


def lod_metrics(mesh: unreal.StaticMesh) -> list[dict[str, Any]]:
    count = int(mesh.get_num_lods())
    if count <= 0:
        fail("{} reports zero LODs".format(mesh.get_name()))

    metrics: list[dict[str, Any]] = []
    for index in range(count):
        metrics.append(
            {
                "lod": index,
                "triangles": int(mesh.get_num_triangles(index)),
                "vertices": int(mesh.get_num_vertices(index)),
                "sections": int(mesh.get_num_sections(index)),
                "tex_coords": int(mesh.get_num_tex_coords(index)),
            }
        )
    return metrics


def validate_monotonic(profile_name: str, metrics: list[dict[str, Any]]) -> None:
    if len(metrics) != 4:
        fail(
            "{} generated {} LODs; expected 4".format(
                profile_name,
                len(metrics),
            )
        )

    for previous, current in zip(metrics, metrics[1:]):
        if int(current["triangles"]) >= int(previous["triangles"]):
            fail(
                "{} triangle count is not strictly decreasing: LOD{}={} LOD{}={}".format(
                    profile_name,
                    previous["lod"],
                    previous["triangles"],
                    current["lod"],
                    current["triangles"],
                )
            )
        if int(current["vertices"]) >= int(previous["vertices"]):
            fail(
                "{} vertex count is not strictly decreasing: LOD{}={} LOD{}={}".format(
                    profile_name,
                    previous["lod"],
                    previous["vertices"],
                    current["lod"],
                    current["vertices"],
                )
            )


def main() -> None:
    cache_value = os.environ.get("YACS_STAGE3G_ASSET_CACHE", "")
    proof_value = os.environ.get("YACS_STAGE3G_FIR_REDUCTION", "")
    if not cache_value:
        fail("YACS_STAGE3G_ASSET_CACHE is not set")
    if not proof_value:
        fail("YACS_STAGE3G_FIR_REDUCTION is not set")

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
    if len(rows) != 1:
        fail(
            "expected exactly one {} FBX source, found {}".format(
                ASSET_ID,
                len(rows),
            )
        )

    source = source_path(cache_root, rows[0])

    results: dict[str, Any] = {}
    source_lod0_triangles: int | None = None
    source_lod0_vertices: int | None = None
    reduction_backend: str | None = None

    try:
        for profile_name, settings in PROFILES.items():
            mesh = import_selected_variant(source, profile_name)
            before = lod_metrics(mesh)
            if len(before) != 1:
                fail(
                    "{} source import unexpectedly has {} LODs".format(
                        profile_name,
                        len(before),
                    )
                )

            if source_lod0_triangles is None:
                source_lod0_triangles = int(before[0]["triangles"])
                source_lod0_vertices = int(before[0]["vertices"])
            elif (
                int(before[0]["triangles"]) != source_lod0_triangles
                or int(before[0]["vertices"]) != source_lod0_vertices
            ):
                fail("source mesh metrics changed between reduction profiles")

            generated_count, backend = set_lods(mesh, settings)
            if reduction_backend is None:
                reduction_backend = backend
            elif backend != reduction_backend:
                fail(
                    "LOD reduction backend changed between profiles: {} -> {}".format(
                        reduction_backend,
                        backend,
                    )
                )
            if generated_count < 0:
                fail(
                    "{} LOD reduction returned {}".format(
                        profile_name,
                        generated_count,
                    )
                )

            after = lod_metrics(mesh)
            validate_monotonic(profile_name, after)

            results[profile_name] = {
                "requested": [
                    {
                        "lod": index,
                        "percent_triangles": float(percent),
                        "screen_size": float(screen_size),
                    }
                    for index, (percent, screen_size) in enumerate(settings)
                ],
                "generated_lod_count": generated_count,
                "actual": after,
                "actual_percent_of_lod0": [
                    round(
                        float(item["triangles"]) / float(after[0]["triangles"]),
                        6,
                    )
                    for item in after
                ],
            }

            log(
                "{}: {}".format(
                    profile_name,
                    ", ".join(
                        "LOD{}={} tris".format(item["lod"], item["triangles"])
                        for item in after
                    ),
                )
            )

        proof = {
            "stage3g_r2_fir_reduction_profile": "success",
            "asset_id": ASSET_ID,
            "source_mesh": SOURCE_MESH_NAME,
            "source_provider": payload.get("provider", {}).get("name"),
            "resolution": payload.get("resolution"),
            "source_fbx": str(source),
            "source_md5": rows[0].get("md5"),
            "source_lod0_triangles": source_lod0_triangles,
            "source_lod0_vertices": source_lod0_vertices,
            "reduction_backend": reduction_backend,
            "profiles": results,
        }

        proof_path = Path(proof_value)
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(
            json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    finally:
        try:
            unreal.EditorAssetLibrary.delete_directory(PROFILE_ROOT)
        except Exception as exc:
            unreal.log_warning(
                "[Stage3GR2FirReduction] transient cleanup warning: {}".format(exc)
            )

    log("SUCCESS: generated and measured {} transient LOD chains".format(len(results)))


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GR2FirReduction] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
