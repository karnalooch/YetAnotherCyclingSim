"""Author the Stage 3G R2 PCG_Forest prototype from WorldSpec intent.

R2 now completes the stock-PCG chain: deterministic candidate generation,
route exclusion, then a stock Static Mesh Spawner backed by the measured and
authored Fir Sapling Medium variant-B aggressive LOD asset.

Required environment variables:
  YACS_STAGE3G_WORLDSPEC                  absolute WorldSpec path
  YACS_STAGE3G_R2_PCG_FOREST_PROOF        absolute JSON proof output path
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


PACKAGE = "/Game/YACS/WorldGen/PCG"
ASSET_NAME = "PCG_Forest"
ASSET_PATH = PACKAGE + "/" + ASSET_NAME
FOREST_MESH_PATH = (
    "/Game/Prototype/Environment/Stage3G/Imported/Meshes/"
    "SM_Stage3G_FirSaplingMedium"
)
FOREST_LOD_PROFILE = "aggressive"


def fail(message: str) -> None:
    raise RuntimeError(message)


def log(message: str) -> None:
    unreal.log("[Stage3GR2PCGForest] {}".format(message))


def parse_worldspec(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail("WorldSpec is missing: {}".format(path))

    section = ""
    current_biome = ""
    seed: int | None = None
    forest_start: float | None = None
    forest_end: float | None = None
    forest_density: float | None = None
    route_clearance: float | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            current_biome = ""
            continue

        if section == "generation" and stripped.startswith("seed:"):
            seed = int(stripped.split(":", 1)[1].strip())
            continue

        if section == "biomes":
            if stripped.startswith("- id:"):
                current_biome = stripped.split(":", 1)[1].strip()
                continue
            if current_biome == "alpine_forest":
                if stripped.startswith("start_m:"):
                    forest_start = float(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("end_m:"):
                    forest_end = float(stripped.split(":", 1)[1].strip())
                elif stripped.startswith("intent:"):
                    match = re.search(
                        r"vegetation_density:\s*([0-9]+(?:\.[0-9]+)?)",
                        stripped,
                    )
                    if match:
                        forest_density = float(match.group(1))
            continue

        if section == "constraints" and stripped.startswith(
            "route_clearance_m:"
        ):
            route_clearance = float(stripped.split(":", 1)[1].strip())

    values = {
        "seed": seed,
        "forest_start_m": forest_start,
        "forest_end_m": forest_end,
        "forest_density": forest_density,
        "route_clearance_m": route_clearance,
    }
    missing = [key for key, value in values.items() if value is None]
    if missing:
        fail("WorldSpec forest intent is incomplete: {}".format(", ".join(missing)))

    if not 0.0 <= float(forest_density) <= 1.0:
        fail("WorldSpec forest density must be inside [0, 1]")
    if float(forest_end) <= float(forest_start):
        fail("WorldSpec forest distance range must be ordered")
    if float(route_clearance) <= 0.0:
        fail("WorldSpec route clearance must be positive")

    return values


def first_pin_label(node: unreal.PCGNode, property_name: str) -> unreal.Name:
    pins = list(node.get_editor_property(property_name) or [])
    if not pins:
        fail("{} exposes no {}".format(node.get_name(), property_name))
    props = pins[0].get_editor_property("properties")
    return props.get_editor_property("label")


def main() -> None:
    worldspec_value = os.environ.get("YACS_STAGE3G_WORLDSPEC", "")
    proof_value = os.environ.get("YACS_STAGE3G_R2_PCG_FOREST_PROOF", "")
    if not worldspec_value:
        fail("YACS_STAGE3G_WORLDSPEC is not set")
    if not proof_value:
        fail("YACS_STAGE3G_R2_PCG_FOREST_PROOF is not set")

    if not hasattr(unreal, "Stage3GForestCandidatesSettings"):
        fail("editor module did not expose Stage3GForestCandidatesSettings")
    if not hasattr(unreal, "Stage3GRouteExclusionSettings"):
        fail("editor module did not expose Stage3GRouteExclusionSettings")

    spec = parse_worldspec(Path(worldspec_value).resolve())

    if not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE):
        if not unreal.EditorAssetLibrary.make_directory(PACKAGE):
            fail("failed to create {}".format(PACKAGE))

    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        if not unreal.EditorAssetLibrary.delete_asset(ASSET_PATH):
            fail("failed to replace existing {}".format(ASSET_PATH))

    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        ASSET_NAME,
        PACKAGE,
        unreal.PCGGraph,
        unreal.PCGGraphFactory(),
    )
    if not graph or not isinstance(graph, unreal.PCGGraph):
        fail("failed to create {}".format(ASSET_PATH))

    forest_mesh = unreal.EditorAssetLibrary.load_asset(FOREST_MESH_PATH)
    if not forest_mesh or not isinstance(forest_mesh, unreal.StaticMesh):
        fail(
            "validated R2 forest mesh is missing: {}".format(
                FOREST_MESH_PATH
            )
        )

    candidate_node, candidate_settings = graph.add_node_of_type(
        unreal.Stage3GForestCandidatesSettings
    )
    route_node, route_settings = graph.add_node_of_type(
        unreal.Stage3GRouteExclusionSettings
    )
    spawner_node, spawner_settings = graph.add_node_of_type(
        unreal.PCGStaticMeshSpawnerSettings
    )
    if not candidate_node or not candidate_settings:
        fail("failed to add YACS Forest Candidates node")
    if not route_node or not route_settings:
        fail("failed to add YACS Route Exclusion node")
    if not spawner_node or not spawner_settings:
        fail("failed to add stock PCG Static Mesh Spawner node")

    spawner_settings.set_mesh_selector_type(unreal.PCGMeshSelectorWeighted)
    selector = spawner_settings.get_editor_property(
        "mesh_selector_parameters"
    )
    if not selector or not isinstance(selector, unreal.PCGMeshSelectorWeighted):
        fail("PCG Static Mesh Spawner did not expose weighted mesh selector")

    entry = unreal.PCGMeshSelectorWeightedEntry()
    descriptor = entry.get_editor_property("descriptor")
    descriptor.set_editor_property("static_mesh", forest_mesh)
    descriptor.set_editor_property("can_ever_affect_navigation", False)
    descriptor.set_editor_property("generate_overlap_events", False)
    entry.set_editor_property("descriptor", descriptor)
    entry.set_editor_property("weight", 100)
    selector.set_editor_property("mesh_entries", [entry])

    candidate_settings.set_editor_property(
        "start_distance_m", float(spec["forest_start_m"])
    )
    candidate_settings.set_editor_property(
        "end_distance_m", float(spec["forest_end_m"])
    )
    candidate_settings.set_editor_property(
        "density", float(spec["forest_density"])
    )
    candidate_settings.set_editor_property(
        "generation_seed", int(spec["seed"])
    )
    route_settings.set_editor_property(
        "protected_half_width_m", float(spec["route_clearance_m"])
    )

    candidate_node.set_node_position(-540, 0)
    route_node.set_node_position(-220, 0)
    spawner_node.set_node_position(100, 0)

    output_node = graph.get_editor_property("output_node")
    if not output_node:
        fail("PCG graph output node is unavailable")

    candidate_output = first_pin_label(candidate_node, "output_pins")
    route_input = first_pin_label(route_node, "input_pins")
    route_output = first_pin_label(route_node, "output_pins")
    spawner_input = first_pin_label(spawner_node, "input_pins")
    spawner_output = first_pin_label(spawner_node, "output_pins")
    graph_output = first_pin_label(output_node, "input_pins")

    if not graph.add_edge(
        candidate_node,
        candidate_output,
        route_node,
        route_input,
    ):
        fail("failed to connect forest candidates to route exclusion")
    if not graph.add_edge(
        route_node,
        route_output,
        spawner_node,
        spawner_input,
    ):
        fail("failed to connect route exclusion to static mesh spawner")
    if not graph.add_edge(
        spawner_node,
        spawner_output,
        output_node,
        graph_output,
    ):
        fail("failed to connect static mesh spawner to graph output")

    graph.set_editor_property(
        "description",
        unreal.Text(
            "Stage 3G R2 deterministic Alpine forest prototype. "
            "WorldSpec drives biome range/density/seed; canonical route geometry "
            "drives placement; the 4 m route corridor is fail-closed. "
            "Stock PCG Static Mesh Spawner uses the measured aggressive-LOD "
            "Fir Sapling Medium variant-B mass-forest asset."
        ),
    )
    graph.set_editor_property("expose_to_library", True)

    if not unreal.EditorAssetLibrary.save_asset(
        ASSET_PATH, only_if_is_dirty=False
    ):
        fail("failed to save {}".format(ASSET_PATH))

    reloaded = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if not reloaded or not isinstance(reloaded, unreal.PCGGraph):
        fail("saved PCG_Forest cannot be reloaded")

    nodes = list(reloaded.get_editor_property("nodes") or [])
    candidates = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(),
            unreal.Stage3GForestCandidatesSettings,
        )
    ]
    exclusions = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(),
            unreal.Stage3GRouteExclusionSettings,
        )
    ]
    spawners = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(),
            unreal.PCGStaticMeshSpawnerSettings,
        )
    ]
    if len(candidates) != 1 or len(exclusions) != 1 or len(spawners) != 1:
        fail(
            "PCG_Forest reload expected candidate/exclusion/spawner = 1/1/1; "
            "found {}/{}/{}".format(
                len(candidates),
                len(exclusions),
                len(spawners),
            )
        )

    saved_candidates = candidates[0].get_settings()
    saved_exclusion = exclusions[0].get_settings()
    saved_spawner = spawners[0].get_settings()
    saved_selector = saved_spawner.get_editor_property(
        "mesh_selector_parameters"
    )
    if not saved_selector or not isinstance(
        saved_selector,
        unreal.PCGMeshSelectorWeighted,
    ):
        fail("reloaded PCG_Forest lost weighted mesh selector")
    saved_entries = list(
        saved_selector.get_editor_property("mesh_entries") or []
    )
    if len(saved_entries) != 1:
        fail(
            "reloaded PCG_Forest expected one weighted mesh entry; found {}".format(
                len(saved_entries)
            )
        )
    saved_descriptor = saved_entries[0].get_editor_property("descriptor")
    saved_mesh = saved_descriptor.get_editor_property("static_mesh")
    if not saved_mesh or saved_mesh.get_path_name() != FOREST_MESH_PATH:
        fail(
            "reloaded PCG_Forest mesh mismatch: {}".format(
                saved_mesh.get_path_name() if saved_mesh else "<none>"
            )
        )
    proof = {
        "stage3g_r2_pcg_forest_graph": "success",
        "asset_path": ASSET_PATH,
        "worldspec_path": str(Path(worldspec_value).resolve()),
        "forest_start_m": float(
            saved_candidates.get_editor_property("start_distance_m")
        ),
        "forest_end_m": float(
            saved_candidates.get_editor_property("end_distance_m")
        ),
        "forest_density": float(
            saved_candidates.get_editor_property("density")
        ),
        "generation_seed": int(
            saved_candidates.get_editor_property("generation_seed")
        ),
        "station_spacing_m": float(
            saved_candidates.get_editor_property("station_spacing_m")
        ),
        "points_per_side_per_station": int(
            saved_candidates.get_editor_property(
                "points_per_side_per_station"
            )
        ),
        "min_lateral_offset_m": float(
            saved_candidates.get_editor_property("min_lateral_offset_m")
        ),
        "max_lateral_offset_m": float(
            saved_candidates.get_editor_property("max_lateral_offset_m")
        ),
        "route_clearance_m": float(
            saved_exclusion.get_editor_property("protected_half_width_m")
        ),
        "graph_custom_node_count": len(candidates) + len(exclusions),
        "graph_spawner_node_count": len(spawners),
        "spawner_status": "validated_mass_forest_asset",
        "spawner_mesh": FOREST_MESH_PATH,
        "spawner_selector": "PCGMeshSelectorWeighted",
        "spawner_weight": int(
            saved_entries[0].get_editor_property("weight")
        ),
        "forest_lod_profile": FOREST_LOD_PROFILE,
        "route_truth": "FRouteGeometryProfile",
    }

    expected = {
        "forest_start_m": float(spec["forest_start_m"]),
        "forest_end_m": float(spec["forest_end_m"]),
        "forest_density": float(spec["forest_density"]),
        "generation_seed": int(spec["seed"]),
        "route_clearance_m": float(spec["route_clearance_m"]),
    }
    for key, value in expected.items():
        if abs(float(proof[key]) - float(value)) > 1e-9:
            fail(
                "saved {}={} does not match WorldSpec {}".format(
                    key,
                    proof[key],
                    value,
                )
            )

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log("SUCCESS: authored {}".format(ASSET_PATH))


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GR2PCGForest] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
