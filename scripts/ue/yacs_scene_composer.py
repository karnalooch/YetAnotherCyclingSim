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
TEMP_PCG_ROOT = "/Game/Generated/YACS/Temp"


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


def _first_pin_label(node: unreal.PCGNode, property_name: str) -> unreal.Name:
    pins = list(node.get_editor_property(property_name) or [])
    if not pins:
        fail("{} exposes no {}".format(node.get_name(), property_name))
    props = pins[0].get_editor_property("properties")
    return props.get_editor_property("label")


def _configure_weighted_mesh_spawner(
    settings: unreal.PCGStaticMeshSpawnerSettings,
    mesh: unreal.StaticMesh,
) -> None:
    settings.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    selector = settings.get_editor_property("mesh_selector_parameters")
    if not selector or not isinstance(selector, unreal.PCGMeshSelectorWeighted):
        fail("PCG Static Mesh Spawner did not expose weighted mesh selector")

    entry = unreal.PCGMeshSelectorWeightedEntry()
    descriptor = entry.get_editor_property("descriptor")
    descriptor.set_editor_property("static_mesh", mesh)
    descriptor.set_editor_property("can_ever_affect_navigation", False)
    descriptor.set_editor_property("generate_overlap_events", False)
    entry.set_editor_property("descriptor", descriptor)
    entry.set_editor_property("weight", 100)
    selector.set_editor_property("mesh_entries", [entry])


def _create_pcg_forest_patch_graph(
    *,
    preset: dict[str, Any],
    mesh: unreal.StaticMesh,
    center_cm: unreal.Vector,
    world_yaw_deg: float,
) -> tuple[unreal.PCGGraph, str]:
    if not hasattr(unreal, "YacsPatchCandidatesSettings"):
        fail("editor module did not expose YacsPatchCandidatesSettings")

    validate_generated_path(TEMP_PCG_ROOT)
    if not unreal.EditorAssetLibrary.does_directory_exist(TEMP_PCG_ROOT):
        if not unreal.EditorAssetLibrary.make_directory(TEMP_PCG_ROOT):
            fail("failed to create {}".format(TEMP_PCG_ROOT))

    asset_name = "PCG_YacsForestPatch_Proof"
    asset_path = "{}/{}".format(TEMP_PCG_ROOT, asset_name)
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        if not unreal.EditorAssetLibrary.delete_asset(asset_path):
            fail("failed to replace temporary PCG graph {}".format(asset_path))

    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        TEMP_PCG_ROOT,
        unreal.PCGGraph,
        unreal.PCGGraphFactory(),
    )
    if not graph or not isinstance(graph, unreal.PCGGraph):
        fail("failed to create temporary PCG patch graph")

    candidate_node, candidate_settings = graph.add_node_of_type(
        unreal.YacsPatchCandidatesSettings
    )
    spawner_node, spawner_settings = graph.add_node_of_type(
        unreal.PCGStaticMeshSpawnerSettings
    )
    if not candidate_node or not candidate_settings:
        fail("failed to add YACS Patch Candidates node")
    if not spawner_node or not spawner_settings:
        fail("failed to add PCG Static Mesh Spawner node")

    composition = preset.get("composition") or {}
    size_m = list(composition.get("size_m") or [])
    if len(size_m) != 2:
        fail("forest_patch size_m must contain [x, y]")

    candidate_settings.set_editor_property("patch_center_cm", center_cm)
    candidate_settings.set_editor_property("size_xm", float(size_m[0]))
    candidate_settings.set_editor_property("size_ym", float(size_m[1]))
    candidate_settings.set_editor_property("patch_yaw_deg", float(world_yaw_deg))
    candidate_settings.set_editor_property("point_count", choose_tree_count(preset))
    candidate_settings.set_editor_property("cluster_count", 3)
    candidate_settings.set_editor_property("min_spacing_m", 0.85)
    candidate_settings.set_editor_property("edge_margin_m", 0.35)
    candidate_settings.set_editor_property("min_uniform_scale", 0.82)
    candidate_settings.set_editor_property("max_uniform_scale", 1.22)
    candidate_settings.set_editor_property(
        "irregularity",
        float(composition.get("natural_irregularity", 0.82)),
    )
    candidate_settings.set_editor_property("generation_seed", int(preset["seed"]))

    _configure_weighted_mesh_spawner(spawner_settings, mesh)

    candidate_node.set_node_position(-320, 0)
    spawner_node.set_node_position(40, 0)
    output_node = graph.get_editor_property("output_node")
    if not output_node:
        fail("PCG graph output node is unavailable")

    candidate_output = _first_pin_label(candidate_node, "output_pins")
    spawner_input = _first_pin_label(spawner_node, "input_pins")
    spawner_output = _first_pin_label(spawner_node, "output_pins")
    graph_output = _first_pin_label(output_node, "input_pins")

    if not graph.add_edge(
        candidate_node,
        candidate_output,
        spawner_node,
        spawner_input,
    ):
        fail("failed to connect patch candidates to mesh spawner")
    if not graph.add_edge(
        spawner_node,
        spawner_output,
        output_node,
        graph_output,
    ):
        fail("failed to connect mesh spawner to graph output")

    graph.set_editor_property(
        "description",
        unreal.Text(
            "Transient YACS World Authoring Library patch proof. Repo-owned "
            "intent drives deterministic patch points; weighted PCG spawning "
            "uses an approved semantic asset."
        ),
    )
    graph.set_editor_property("expose_to_library", False)
    return graph, asset_path


def begin_pcg_forest_patch(
    *,
    preset: dict[str, Any],
    selection_plan: dict[str, Any],
    actor_subsystem: unreal.EditorActorSubsystem,
    center_cm: unreal.Vector,
    world_yaw_deg: float,
    label_prefix: str = "YACS_PCG_FOREST_PATCH",
) -> tuple[dict[str, Any], unreal.PCGVolume, unreal.PCGComponent]:
    """Start the real PCG patch backend and return without blocking editor ticks."""

    selection = selection_for_slot(selection_plan, "mass_conifer")
    mesh = require_qualified_ue_asset(selection)
    if not isinstance(mesh, unreal.StaticMesh):
        fail("mass_conifer selection is not a StaticMesh")

    # Existing Stage 3G graphs remain compatibility/read-only contracts. The
    # generic local patch graph is deliberately separate from route-distance
    # forest generation.
    pcg = preset.get("pcg") or {}
    forest_graph_path = str(pcg.get("graph", ""))
    route_graph_path = str(pcg.get("route_exclusion_graph", ""))
    load_and_validate_pcg_graph(forest_graph_path)
    load_and_validate_pcg_graph(route_graph_path)

    graph, graph_path = _create_pcg_forest_patch_graph(
        preset=preset,
        mesh=mesh,
        center_cm=center_cm,
        world_yaw_deg=world_yaw_deg,
    )

    if not hasattr(unreal, "PCGVolume") or not hasattr(unreal, "PCGComponent"):
        fail("UE Python does not expose PCGVolume/PCGComponent")

    volume = actor_subsystem.spawn_actor_from_class(
        unreal.PCGVolume,
        center_cm,
        unreal.Rotator(),
        transient=True,
    )
    if volume is None:
        fail("failed to spawn transient PCGVolume")
    volume.set_actor_label(label_prefix)

    component = volume.get_component_by_class(unreal.PCGComponent)
    if component is None:
        try:
            component = volume.get_editor_property("pcg_component")
        except Exception:
            component = None
    if component is None:
        fail("spawned PCGVolume exposes no PCGComponent")

    if hasattr(component, "set_graph_local"):
        component.set_graph_local(graph)
    elif hasattr(component, "set_graph"):
        component.set_graph(graph)
    else:
        fail("PCGComponent exposes neither set_graph_local nor set_graph")

    if hasattr(component, "generate_local"):
        component.generate_local(True)
    elif hasattr(component, "generate"):
        component.generate(True)
    else:
        fail("PCGComponent exposes no generation method")

    composition = preset["composition"]
    expected_count = choose_tree_count(preset)
    proof = {
        "preset_id": preset["id"],
        "backend": "pcg_patch_adapter_v1",
        "generated_root": preset["generated_root"],
        "temporary_graph_path": graph_path,
        "forest_patch_size_m": [float(v) for v in composition["size_m"]],
        "tree_count": expected_count,
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
            "execution_backend": "pcg_patch_adapter_v1",
            "generic_candidate_node": "YACSPatchCandidates",
            "generation_requested": True,
        },
        "transient": True,
        "saved_to_map": False,
        "center_cm": [
            float(center_cm.x),
            float(center_cm.y),
            float(center_cm.z),
        ],
        "world_yaw_deg": float(world_yaw_deg),
        "grounding": "pcg_patch_center_surface_v1",
    }
    log(
        "started PCG forest patch preset={} expected_trees={} mesh={}".format(
            preset["id"],
            expected_count,
            selection.get("ue_asset_path"),
        )
    )
    return proof, volume, component


def count_pcg_instances(volume: unreal.PCGVolume) -> int:
    total = 0
    components = list(
        volume.get_components_by_class(unreal.InstancedStaticMeshComponent)
    )
    for component in components:
        if hasattr(component, "get_instance_count"):
            total += int(component.get_instance_count())
    return total
