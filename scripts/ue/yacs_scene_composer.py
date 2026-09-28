"""Reusable Unreal-side scene composer helpers for YACS world authoring.

The first backend is intentionally transient and reviewable. It consumes a
repo-owned preset plus an asset selection plan, resolves only already-qualified
Unreal assets, and spawns deterministic proof actors. Persistent authoring is a
separate gate and remains restricted to /Game/Generated/YACS/**.

Production PCG assets remain the intended scalable backend. The composer keeps
semantic intent/layout independent from the backend so the same preset can be
replayed through PCG once the patch graph adapter is validated.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

import unreal


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
WORLDGEN_SCRIPT_DIR = REPO_ROOT / "scripts" / "worldgen"
if str(WORLDGEN_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(WORLDGEN_SCRIPT_DIR))

from yacs_scene_layout import (  # noqa: E402
    RectExclusion,
    plan_clustered_forest_patch,
    serialize_placements,
)


GENERATED_ROOT = "/Game/Generated/YACS"
ALLOWED_READONLY_PCG_ROOT = "/Game/YACS/WorldGen/PCG"


def fail(message: str) -> None:
    raise RuntimeError(message)


def log(message: str) -> None:
    unreal.log("[YacsSceneComposer] {}".format(message))


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail("JSON input is missing: {}".format(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail("JSON input must be an object: {}".format(path))
    return payload


def validate_generated_path(path: str) -> None:
    normalized = path.rstrip("/")
    if not (
        normalized == GENERATED_ROOT
        or normalized.startswith(GENERATED_ROOT + "/")
    ):
        fail(
            "persistent destination escapes generated-content sandbox: {!r}".format(
                path
            )
        )


def validate_readonly_pcg_path(path: str) -> None:
    normalized = path.rstrip("/")
    if not (
        normalized == ALLOWED_READONLY_PCG_ROOT
        or normalized.startswith(ALLOWED_READONLY_PCG_ROOT + "/")
    ):
        fail("PCG graph is outside the approved read-only graph root: {!r}".format(path))


def selection_for_slot(plan: dict[str, Any], slot: str) -> dict[str, Any]:
    matches = [
        item
        for item in list(plan.get("selections") or [])
        if item.get("slot") == slot
    ]
    if len(matches) != 1:
        fail(
            "selection plan expected exactly one {!r} slot; found {}".format(
                slot, len(matches)
            )
        )
    return matches[0]


def require_qualified_ue_asset(selection: dict[str, Any]) -> unreal.Object:
    path = selection.get("ue_asset_path")
    if not isinstance(path, str) or not path.startswith("/Game/"):
        fail(
            "slot {!r} selected source {!r} but it is not yet qualified/imported "
            "as a YACS Unreal asset".format(
                selection.get("slot"),
                selection.get("provider_asset_id"),
            )
        )
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if asset is None:
        fail("qualified Unreal asset cannot be loaded: {}".format(path))
    return asset


def load_and_validate_pcg_graph(path: str) -> unreal.PCGGraph:
    validate_readonly_pcg_path(path)
    graph = unreal.EditorAssetLibrary.load_asset(path)
    if not graph or not isinstance(graph, unreal.PCGGraph):
        fail("PCG graph cannot be loaded: {}".format(path))
    return graph


def choose_tree_count(preset: dict[str, Any]) -> int:
    count = (preset.get("composition") or {}).get("tree_count") or {}
    minimum = int(count.get("min", 0))
    maximum = int(count.get("max", 0))
    if minimum <= 0 or maximum < minimum:
        fail("forest tree_count contract is invalid")
    # Stable midpoint keeps visual diffs reproducible while leaving the preset
    # free to express a bounded density range.
    return (minimum + maximum) // 2


def plan_forest_layout(
    preset: dict[str, Any],
    *,
    exclusions: list[RectExclusion] | None = None,
) -> list[Any]:
    composition = preset.get("composition") or {}
    if composition.get("type") != "forest_patch":
        fail("scene composer currently supports forest_patch presets only")

    size_m = list(composition.get("size_m") or [])
    if len(size_m) != 2:
        fail("forest_patch size_m must contain [x, y]")

    return plan_clustered_forest_patch(
        size_x_m=float(size_m[0]),
        size_y_m=float(size_m[1]),
        tree_count=choose_tree_count(preset),
        seed=int(preset["seed"]),
        irregularity=float(composition.get("natural_irregularity", 0.8)),
        exclusions=exclusions or [],
    )


def _rotate_local_xy(
    x_m: float,
    y_m: float,
    world_yaw_deg: float,
) -> tuple[float, float]:
    radians = math.radians(world_yaw_deg)
    cos_yaw = math.cos(radians)
    sin_yaw = math.sin(radians)
    return (
        x_m * cos_yaw - y_m * sin_yaw,
        x_m * sin_yaw + y_m * cos_yaw,
    )


def spawn_transient_forest_patch(
    *,
    preset: dict[str, Any],
    selection_plan: dict[str, Any],
    actor_subsystem: unreal.EditorActorSubsystem,
    center_cm: unreal.Vector,
    world_yaw_deg: float,
    height_resolver: Callable[[float, float, float], float] | None = None,
    label_prefix: str = "YACS_FOREST_PATCH",
    exclusions: list[RectExclusion] | None = None,
) -> dict[str, Any]:
    """Spawn a deterministic transient forest-patch proof.

    height_resolver receives world x/y/base-z in centimetres and returns world z
    in centimetres. When omitted, the patch uses center_cm.z.
    """

    selection = selection_for_slot(selection_plan, "mass_conifer")
    mesh = require_qualified_ue_asset(selection)
    if not isinstance(mesh, unreal.StaticMesh):
        fail("mass_conifer selection is not a StaticMesh")

    pcg = preset.get("pcg") or {}
    forest_graph_path = str(pcg.get("graph", ""))
    route_graph_path = str(pcg.get("route_exclusion_graph", ""))
    load_and_validate_pcg_graph(forest_graph_path)
    load_and_validate_pcg_graph(route_graph_path)

    placements = plan_forest_layout(preset, exclusions=exclusions)
    actors: list[unreal.StaticMeshActor] = []

    mesh_min_z_cm = 0.0
    if hasattr(mesh, "get_bounding_box"):
        bounds = mesh.get_bounding_box()
        if bounds is not None and hasattr(bounds, "min"):
            mesh_min_z_cm = float(bounds.min.z)

    for index, item in enumerate(placements):
        offset_x_m, offset_y_m = _rotate_local_xy(
            float(item.x_m),
            float(item.y_m),
            world_yaw_deg,
        )
        world_x = float(center_cm.x) + offset_x_m * 100.0
        world_y = float(center_cm.y) + offset_y_m * 100.0
        ground_z = (
            float(height_resolver(world_x, world_y, float(center_cm.z)))
            if height_resolver is not None
            else float(center_cm.z)
        )
        scale = float(item.uniform_scale)
        world_z = ground_z - mesh_min_z_cm * scale
        rotation = unreal.Rotator(
            pitch=0.0,
            yaw=world_yaw_deg + float(item.yaw_deg),
            roll=0.0,
        )
        actor = actor_subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(world_x, world_y, world_z),
            rotation,
            transient=True,
        )
        if actor is None:
            fail("failed to spawn forest tree {}".format(index))
        actor.set_actor_label("{}_{:03d}".format(label_prefix, index))
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        if component is None:
            fail("forest tree {} has no StaticMeshComponent".format(index))
        component.set_static_mesh(mesh)
        component.set_cast_shadow(True)
        actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
        actors.append(actor)

    if len(actors) != len(placements):
        fail("forest actor count does not match deterministic layout")

    composition = preset["composition"]
    proof = {
        "preset_id": preset["id"],
        "backend": "transient_static_mesh_proof",
        "generated_root": preset["generated_root"],
        "forest_patch_size_m": [float(v) for v in composition["size_m"]],
        "tree_count": len(actors),
        "seed": int(preset["seed"]),
        "mass_conifer": {
            "catalog_asset_id": selection.get("catalog_asset_id"),
            "provider": selection.get("provider"),
            "provider_asset_id": selection.get("provider_asset_id"),
            "ue_asset_path": selection.get("ue_asset_path"),
            "lifecycle_status": selection.get("lifecycle_status"),
        },
        "pcg_contract": {
            "forest_graph": forest_graph_path,
            "route_exclusion_graph": route_graph_path,
            "graphs_loaded": True,
            "execution_backend": "pending_pcg_patch_adapter",
        },
        "transient": True,
        "saved_to_map": False,
        "center_cm": [
            float(center_cm.x),
            float(center_cm.y),
            float(center_cm.z),
        ],
        "world_yaw_deg": float(world_yaw_deg),
        "mesh_min_z_cm": mesh_min_z_cm,
        "grounding": "mesh_bounds_min_z",
        "placements": serialize_placements(placements),
    }
    log(
        "spawned transient forest patch preset={} trees={} mesh={}".format(
            preset["id"],
            len(actors),
            selection.get("ue_asset_path"),
        )
    )
    return proof
