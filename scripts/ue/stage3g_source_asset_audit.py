"""Non-mutating Stage 3G source-asset lifecycle audit.

This audit deliberately separates source-asset lifecycle acceptance from the
aggregate environment performance proof. It validates persisted Unreal assets
without modifying them.

Required environment variable:
  YACS_STAGE3G_SOURCE_ASSET_AUDIT_PROOF absolute JSON output path
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import unreal


TEXTURE_ROOT = "/Game/Prototype/Environment/Stage3G/Imported/Textures"
MESH_ROOT = "/Game/Prototype/Environment/Stage3G/Imported/Meshes"
MATERIAL_ROOT = "/Game/Prototype/Environment/Stage3G/Materials"
PCG_ROOT = "/Game/YACS/WorldGen/PCG"

SOURCE_FAMILIES = {
    "sparse_grass": {
        "status_target": "validated",
        "material": MATERIAL_ROOT + "/M_Stage3G_Grass",
        "textures": {
            "base_color": TEXTURE_ROOT + "/T_Stage3G_Meadow_BaseColor",
            "normal": TEXTURE_ROOT + "/T_Stage3G_Meadow_Normal",
            "roughness": TEXTURE_ROOT + "/T_Stage3G_Meadow_Roughness",
        },
    },
    "forrest_ground_03": {
        "status_target": "validated",
        "material": MATERIAL_ROOT + "/M_Stage3G_Forest",
        "textures": {
            "base_color": TEXTURE_ROOT + "/T_Stage3G_ForestGround_BaseColor",
            "normal": TEXTURE_ROOT + "/T_Stage3G_ForestGround_Normal",
            "roughness": TEXTURE_ROOT + "/T_Stage3G_ForestGround_Roughness",
        },
    },
    "rocky_terrain": {
        "status_target": "validated",
        "material": MATERIAL_ROOT + "/M_Stage3G_DistantRock",
        "textures": {
            "base_color": TEXTURE_ROOT + "/T_Stage3G_HighAlpine_BaseColor",
            "normal": TEXTURE_ROOT + "/T_Stage3G_HighAlpine_Normal",
            "roughness": TEXTURE_ROOT + "/T_Stage3G_HighAlpine_Roughness",
        },
    },
    "boulder_01": {
        "status_target": "validated",
        "material": MATERIAL_ROOT + "/M_Stage3G_Rock",
        "textures": {
            "base_color": TEXTURE_ROOT + "/T_Stage3G_Boulder_BaseColor",
            "normal": TEXTURE_ROOT + "/T_Stage3G_Boulder_Normal",
            "roughness": TEXTURE_ROOT + "/T_Stage3G_Boulder_Roughness",
        },
        "mesh": MESH_ROOT + "/SM_Stage3G_Boulder",
        "pcg_graphs": [
            PCG_ROOT + "/PCG_Valley",
            PCG_ROOT + "/PCG_HighAlpine",
        ],
    },
}

MAX_TEXTURE_DIMENSION = 2048


def log(message: str) -> None:
    unreal.log("[Stage3GSourceAssetAudit] {}".format(message))


def path_name(asset: Any) -> str:
    if not asset:
        return ""
    return str(unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(asset))


def enum_text(value: Any) -> str:
    return str(value).split(".")[-1]


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def load_required(path: str, expected_class: type) -> Any:
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError("missing required asset: {}".format(path))
    if not isinstance(asset, expected_class):
        raise RuntimeError(
            "{} class mismatch: actual={} expected={}".format(
                path,
                asset.get_class().get_name(),
                expected_class.__name__,
            )
        )
    return asset


def audit_texture(path: str, role: str) -> dict[str, Any]:
    texture = load_required(path, unreal.Texture2D)
    width = int(texture.blueprint_get_size_x())
    height = int(texture.blueprint_get_size_y())
    never_stream = bool(texture.get_editor_property("never_stream"))
    max_texture_size = int(texture.get_editor_property("max_texture_size"))
    mip_gen = enum_text(texture.get_editor_property("mip_gen_settings"))
    lod_group = enum_text(texture.get_editor_property("lod_group"))
    srgb = bool(texture.get_editor_property("srgb"))
    virtual_texture_streaming = bool(
        texture.get_editor_property("virtual_texture_streaming")
    )
    compression = enum_text(texture.get_editor_property("compression_settings"))

    failures: list[str] = []
    if width <= 0 or height <= 0:
        failures.append("invalid_dimensions")
    if width > MAX_TEXTURE_DIMENSION or height > MAX_TEXTURE_DIMENSION:
        failures.append("dimension_above_2k_contract")
    if not is_power_of_two(width) or not is_power_of_two(height):
        failures.append("non_power_of_two_source")
    if never_stream:
        failures.append("never_stream_enabled")
    if "NO_MIPMAPS" in mip_gen.upper():
        failures.append("mip_generation_disabled")
    if role in {"normal", "roughness"} and srgb:
        failures.append("{}_must_be_linear".format(role))
    if role == "normal" and "NORMALMAP" not in compression.upper():
        failures.append("normal_map_compression_missing")

    return {
        "path": path,
        "role": role,
        "width": width,
        "height": height,
        "lod_group": lod_group,
        "max_texture_size": max_texture_size,
        "mip_gen_settings": mip_gen,
        "never_stream": never_stream,
        "virtual_texture_streaming": virtual_texture_streaming,
        "srgb": srgb,
        "compression_settings": compression,
        "pass": not failures,
        "failures": failures,
    }


def material_texture_paths(material_path: str) -> list[str]:
    material = load_required(material_path, unreal.MaterialInterface)
    used = unreal.MaterialEditingLibrary.get_material_used_textures(material)
    return sorted({path_name(texture).split(".")[0] for texture in used if texture})


def graph_uses_mesh(graph_path: str, mesh_object_path: str) -> dict[str, Any]:
    graph = load_required(graph_path, unreal.PCGGraph)
    nodes = list(graph.get_editor_property("nodes") or [])
    spawners = [
        node
        for node in nodes
        if isinstance(node.get_settings(), unreal.PCGStaticMeshSpawnerSettings)
    ]

    matching_entries = 0
    entry_paths: list[str] = []
    for node in spawners:
        settings = node.get_settings()
        selector = settings.get_editor_property("mesh_selector_parameters")
        if not selector or not isinstance(selector, unreal.PCGMeshSelectorWeighted):
            continue
        for entry in list(selector.get_editor_property("mesh_entries") or []):
            descriptor = entry.get_editor_property("descriptor")
            mesh = descriptor.get_editor_property("static_mesh")
            mesh_path = path_name(mesh)
            if mesh_path:
                entry_paths.append(mesh_path)
            if mesh_path == mesh_object_path:
                matching_entries += 1

    return {
        "graph": graph_path,
        "static_mesh_spawner_count": len(spawners),
        "mesh_entries": sorted(entry_paths),
        "matching_boulder_entries": matching_entries,
        "pass": len(spawners) >= 1 and matching_entries >= 1,
    }


def audit_boulder(mesh_path: str, graph_paths: list[str]) -> dict[str, Any]:
    mesh = load_required(mesh_path, unreal.StaticMesh)
    lod_count = int(mesh.get_num_lods())
    triangles = [int(mesh.get_num_triangles(index)) for index in range(lod_count)]
    vertices = [int(mesh.get_num_vertices(index)) for index in range(lod_count)]
    nanite = mesh.get_editor_property("nanite_settings")
    nanite_enabled = bool(nanite.get_editor_property("enabled"))
    nanite_triangles = int(mesh.get_num_nanite_triangles())
    nanite_vertices = int(mesh.get_num_nanite_vertices())
    allow_cpu_access = bool(mesh.get_editor_property("allow_cpu_access"))
    never_stream = bool(mesh.get_editor_property("never_stream"))
    lod_group = str(mesh.get_editor_property("lod_group"))

    graph_proofs = [
        graph_uses_mesh(graph_path, mesh.get_path_name())
        for graph_path in graph_paths
    ]
    instanced_pcg_use = all(item["pass"] for item in graph_proofs)

    failures: list[str] = []
    if lod_count < 2 and not nanite_enabled:
        failures.append("requires_multiple_lods_or_nanite")
    if not instanced_pcg_use:
        failures.append("missing_pcg_static_mesh_spawner_usage")
    if allow_cpu_access:
        failures.append("unexpected_runtime_cpu_mesh_access")
    if never_stream:
        failures.append("mesh_never_stream_enabled")

    return {
        "path": mesh_path,
        "lod_count": lod_count,
        "triangles_by_lod": triangles,
        "vertices_by_lod": vertices,
        "lod_group": lod_group,
        "nanite_enabled": nanite_enabled,
        "nanite_triangles": nanite_triangles,
        "nanite_vertices": nanite_vertices,
        "allow_cpu_access": allow_cpu_access,
        "never_stream": never_stream,
        "pcg_instancing": graph_proofs,
        "pass": not failures,
        "failures": failures,
    }


def main() -> None:
    proof_value = os.environ.get("YACS_STAGE3G_SOURCE_ASSET_AUDIT_PROOF", "")
    if not proof_value:
        raise RuntimeError("YACS_STAGE3G_SOURCE_ASSET_AUDIT_PROOF is not set")

    families: dict[str, Any] = {}
    global_failures: list[str] = []

    for source_id, spec in SOURCE_FAMILIES.items():
        textures = {
            role: audit_texture(path, role)
            for role, path in spec["textures"].items()
        }
        expected_paths = sorted(spec["textures"].values())
        used_paths = material_texture_paths(spec["material"])
        material_uses_all = all(path in used_paths for path in expected_paths)

        family_failures: list[str] = []
        family_failures.extend(
            "{}:{}".format(role, failure)
            for role, evidence in textures.items()
            for failure in evidence["failures"]
        )
        if not material_uses_all:
            family_failures.append("material_does_not_use_all_expected_textures")

        family: dict[str, Any] = {
            "source_id": source_id,
            "material": spec["material"],
            "material_used_textures": used_paths,
            "material_uses_all_expected_textures": material_uses_all,
            "textures": textures,
            "pass": not family_failures,
            "failures": family_failures,
        }

        if "mesh" in spec:
            mesh = audit_boulder(spec["mesh"], spec["pcg_graphs"])
            family["mesh"] = mesh
            if not mesh["pass"]:
                family["pass"] = False
                family["failures"].extend(
                    "mesh:{}".format(failure) for failure in mesh["failures"]
                )

        if not family["pass"]:
            global_failures.append(source_id)

        families[source_id] = family

    payload = {
        "schema_version": 1,
        "stage3g_source_asset_audit": (
            "PASS" if not global_failures else "FAIL"
        ),
        "max_texture_dimension": MAX_TEXTURE_DIMENSION,
        "families": families,
        "failed_families": global_failures,
        "note": (
            "Aggregate environment performance is proven separately; this audit "
            "owns persisted source-asset streaming/mip/material/mesh/instancing policy."
        ),
    }

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if global_failures:
        log("FAIL: {}".format(", ".join(global_failures)))
        sys.exit(1)

    log("PASS: all curated Stage 3G source asset families satisfy lifecycle audit")


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GSourceAssetAudit] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
