"""Author Stage 3G R3 PCG_Valley and PCG_HighAlpine graphs.

R3 reuses the canonical route geometry and route-clearance contract established
in R2, while WorldSpec owns biome ranges, rock densities and the generation
seed. Both graphs use the validated Stage 3G boulder mesh; valley dressing is
sparse, high-Alpine dressing is intentionally denser.

Required environment variables:
  YACS_STAGE3G_WORLDSPEC             absolute WorldSpec path
  YACS_STAGE3G_R3_PCG_BIOMES_PROOF   absolute JSON proof output path
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import unreal


PACKAGE = "/Game/YACS/WorldGen/PCG"
BOULDER_MESH_PATH = (
    "/Game/Prototype/Environment/Stage3G/Imported/Meshes/"
    "SM_Stage3G_Boulder"
)
BOULDER_MESH_OBJECT_PATH = BOULDER_MESH_PATH + ".SM_Stage3G_Boulder"

GRAPH_SPECS = {
    "valley": {
        "asset_name": "PCG_Valley",
        "worldspec_id": "valley_meadow",
        "station_spacing_m": 80.0,
        "points_per_side_per_station": 2,
        "min_lateral_offset_m": 14.0,
        "max_lateral_offset_m": 85.0,
        "min_uniform_scale": 0.55,
        "max_uniform_scale": 1.00,
    },
    "high_alpine": {
        "asset_name": "PCG_HighAlpine",
        "worldspec_id": "high_alpine",
        "station_spacing_m": 32.0,
        "points_per_side_per_station": 4,
        "min_lateral_offset_m": 8.0,
        "max_lateral_offset_m": 72.0,
        "min_uniform_scale": 0.70,
        "max_uniform_scale": 1.55,
    },
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def log(message: str) -> None:
    unreal.log("[Stage3GR3PCGBiomes] {}".format(message))


def parse_worldspec(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail("WorldSpec is missing: {}".format(path))

    section = ""
    current_biome = ""
    seed: int | None = None
    route_clearance: float | None = None
    biomes: dict[str, dict[str, float]] = {}

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
                biomes.setdefault(current_biome, {})
                continue
            if current_biome:
                if stripped.startswith("start_m:"):
                    biomes[current_biome]["start_m"] = float(
                        stripped.split(":", 1)[1].strip()
                    )
                elif stripped.startswith("end_m:"):
                    biomes[current_biome]["end_m"] = float(
                        stripped.split(":", 1)[1].strip()
                    )
                elif stripped.startswith("rocks_density:"):
                    biomes[current_biome]["rocks_density"] = float(
                        stripped.split(":", 1)[1].strip()
                    )
                elif stripped.startswith("vegetation_density:"):
                    biomes[current_biome]["vegetation_density"] = float(
                        stripped.split(":", 1)[1].strip()
                    )
            continue

        if section == "constraints" and stripped.startswith(
            "route_clearance_m:"
        ):
            route_clearance = float(stripped.split(":", 1)[1].strip())

    if seed is None:
        fail("WorldSpec generation seed is missing")
    if route_clearance is None or route_clearance <= 0.0:
        fail("WorldSpec route clearance must be present and positive")

    for spec in GRAPH_SPECS.values():
        biome_id = spec["worldspec_id"]
        biome = biomes.get(biome_id, {})
        required = ("start_m", "end_m", "rocks_density")
        missing = [key for key in required if key not in biome]
        if missing:
            fail(
                "WorldSpec biome {} is incomplete: {}".format(
                    biome_id, ", ".join(missing)
                )
            )
        if biome["end_m"] <= biome["start_m"]:
            fail("WorldSpec biome {} range must be ordered".format(biome_id))
        if not 0.0 <= biome["rocks_density"] <= 1.0:
            fail(
                "WorldSpec biome {} rock density must be inside [0, 1]".format(
                    biome_id
                )
            )

    return {
        "seed": seed,
        "route_clearance_m": route_clearance,
        "biomes": biomes,
    }


def first_pin_label(node: unreal.PCGNode, property_name: str) -> unreal.Name:
    pins = list(node.get_editor_property(property_name) or [])
    if not pins:
        fail("{} exposes no {}".format(node.get_name(), property_name))
    props = pins[0].get_editor_property("properties")
    return props.get_editor_property("label")


def configure_spawner(
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


def build_graph(
    key: str,
    graph_spec: dict[str, Any],
    worldspec: dict[str, Any],
    boulder_mesh: unreal.StaticMesh,
) -> dict[str, Any]:
    asset_name = graph_spec["asset_name"]
    asset_path = "{}/{}".format(PACKAGE, asset_name)
    biome = worldspec["biomes"][graph_spec["worldspec_id"]]

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        if not unreal.EditorAssetLibrary.delete_asset(asset_path):
            fail("failed to replace existing {}".format(asset_path))

    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name,
        PACKAGE,
        unreal.PCGGraph,
        unreal.PCGGraphFactory(),
    )
    if not graph or not isinstance(graph, unreal.PCGGraph):
        fail("failed to create {}".format(asset_path))

    candidate_node, candidate_settings = graph.add_node_of_type(
        unreal.Stage3GBiomeCandidatesSettings
    )
    route_node, route_settings = graph.add_node_of_type(
        unreal.Stage3GRouteExclusionSettings
    )
    spawner_node, spawner_settings = graph.add_node_of_type(
        unreal.PCGStaticMeshSpawnerSettings
    )
    if not candidate_node or not candidate_settings:
        fail("failed to add YACS Biome Candidates node")
    if not route_node or not route_settings:
        fail("failed to add YACS Route Exclusion node")
    if not spawner_node or not spawner_settings:
        fail("failed to add stock PCG Static Mesh Spawner node")

    configure_spawner(spawner_settings, boulder_mesh)

    candidate_settings.set_editor_property(
        "start_distance_m", float(biome["start_m"])
    )
    candidate_settings.set_editor_property(
        "end_distance_m", float(biome["end_m"])
    )
    candidate_settings.set_editor_property(
        "station_spacing_m", float(graph_spec["station_spacing_m"])
    )
    candidate_settings.set_editor_property(
        "density", float(biome["rocks_density"])
    )
    candidate_settings.set_editor_property(
        "points_per_side_per_station",
        int(graph_spec["points_per_side_per_station"]),
    )
    candidate_settings.set_editor_property(
        "min_lateral_offset_m",
        float(graph_spec["min_lateral_offset_m"]),
    )
    candidate_settings.set_editor_property(
        "max_lateral_offset_m",
        float(graph_spec["max_lateral_offset_m"]),
    )
    candidate_settings.set_editor_property(
        "min_uniform_scale", float(graph_spec["min_uniform_scale"])
    )
    candidate_settings.set_editor_property(
        "max_uniform_scale", float(graph_spec["max_uniform_scale"])
    )
    candidate_settings.set_editor_property(
        "generation_seed", int(worldspec["seed"])
    )
    route_settings.set_editor_property(
        "protected_half_width_m",
        float(worldspec["route_clearance_m"]),
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
        candidate_node, candidate_output, route_node, route_input
    ):
        fail("failed to connect biome candidates to route exclusion")
    if not graph.add_edge(
        route_node, route_output, spawner_node, spawner_input
    ):
        fail("failed to connect route exclusion to static mesh spawner")
    if not graph.add_edge(
        spawner_node, spawner_output, output_node, graph_output
    ):
        fail("failed to connect static mesh spawner to graph output")

    graph.set_editor_property(
        "description",
        unreal.Text(
            "Stage 3G R3 deterministic {} graph. WorldSpec drives biome "
            "range/rock density/seed; canonical route geometry plus YACS route "
            "exclusion owns road clearance; stock PCG spawns the validated "
            "Stage 3G boulder mesh.".format(graph_spec["worldspec_id"])
        ),
    )
    graph.set_editor_property("expose_to_library", True)

    if not unreal.EditorAssetLibrary.save_asset(
        asset_path, only_if_is_dirty=False
    ):
        fail("failed to save {}".format(asset_path))

    reloaded = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not reloaded or not isinstance(reloaded, unreal.PCGGraph):
        fail("saved {} cannot be reloaded".format(asset_name))

    nodes = list(reloaded.get_editor_property("nodes") or [])
    candidates = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(), unreal.Stage3GBiomeCandidatesSettings
        )
    ]
    exclusions = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(), unreal.Stage3GRouteExclusionSettings
        )
    ]
    spawners = [
        node
        for node in nodes
        if isinstance(
            node.get_settings(), unreal.PCGStaticMeshSpawnerSettings
        )
    ]
    if len(candidates) != 1 or len(exclusions) != 1 or len(spawners) != 1:
        fail(
            "{} reload expected candidate/exclusion/spawner = 1/1/1; "
            "found {}/{}/{}".format(
                asset_name,
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
        saved_selector, unreal.PCGMeshSelectorWeighted
    ):
        fail("{} lost weighted mesh selector".format(asset_name))

    saved_entries = list(
        saved_selector.get_editor_property("mesh_entries") or []
    )
    if len(saved_entries) != 1:
        fail(
            "{} expected one weighted mesh entry; found {}".format(
                asset_name, len(saved_entries)
            )
        )
    saved_descriptor = saved_entries[0].get_editor_property("descriptor")
    saved_mesh = saved_descriptor.get_editor_property("static_mesh")
    saved_mesh_path = (
        unreal.EditorAssetLibrary.get_path_name_for_loaded_asset(saved_mesh)
        if saved_mesh
        else ""
    )
    if not saved_mesh or saved_mesh_path != BOULDER_MESH_OBJECT_PATH:
        fail(
            "{} mesh mismatch: actual={!r} expected={!r}".format(
                asset_name,
                saved_mesh_path or "<none>",
                BOULDER_MESH_OBJECT_PATH,
            )
        )

    proof = {
        "asset_path": asset_path,
        "worldspec_biome": graph_spec["worldspec_id"],
        "start_m": float(
            saved_candidates.get_editor_property("start_distance_m")
        ),
        "end_m": float(
            saved_candidates.get_editor_property("end_distance_m")
        ),
        "rocks_density": float(
            saved_candidates.get_editor_property("density")
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
        "min_uniform_scale": float(
            saved_candidates.get_editor_property("min_uniform_scale")
        ),
        "max_uniform_scale": float(
            saved_candidates.get_editor_property("max_uniform_scale")
        ),
        "generation_seed": int(
            saved_candidates.get_editor_property("generation_seed")
        ),
        "route_clearance_m": float(
            saved_exclusion.get_editor_property("protected_half_width_m")
        ),
        "spawner_mesh": BOULDER_MESH_PATH,
        "spawner_selector": "PCGMeshSelectorWeighted",
        "spawner_weight": int(
            saved_entries[0].get_editor_property("weight")
        ),
        "route_truth": "FRouteGeometryProfile",
    }

    expected = {
        "start_m": float(biome["start_m"]),
        "end_m": float(biome["end_m"]),
        "rocks_density": float(biome["rocks_density"]),
        "generation_seed": int(worldspec["seed"]),
        "route_clearance_m": float(worldspec["route_clearance_m"]),
    }
    for field, value in expected.items():
        if abs(float(proof[field]) - float(value)) > 1e-9:
            fail(
                "{} saved {}={} does not match WorldSpec {}".format(
                    asset_name, field, proof[field], value
                )
            )

    return proof


def main() -> None:
    worldspec_value = os.environ.get("YACS_STAGE3G_WORLDSPEC", "")
    proof_value = os.environ.get("YACS_STAGE3G_R3_PCG_BIOMES_PROOF", "")
    if not worldspec_value:
        fail("YACS_STAGE3G_WORLDSPEC is not set")
    if not proof_value:
        fail("YACS_STAGE3G_R3_PCG_BIOMES_PROOF is not set")

    if not hasattr(unreal, "Stage3GBiomeCandidatesSettings"):
        fail("editor module did not expose Stage3GBiomeCandidatesSettings")
    if not hasattr(unreal, "Stage3GRouteExclusionSettings"):
        fail("editor module did not expose Stage3GRouteExclusionSettings")

    worldspec = parse_worldspec(Path(worldspec_value).resolve())

    if not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE):
        if not unreal.EditorAssetLibrary.make_directory(PACKAGE):
            fail("failed to create {}".format(PACKAGE))

    boulder_mesh = unreal.EditorAssetLibrary.load_asset(BOULDER_MESH_PATH)
    if not boulder_mesh or not isinstance(boulder_mesh, unreal.StaticMesh):
        fail(
            "validated Stage 3G boulder mesh is missing: {}".format(
                BOULDER_MESH_PATH
            )
        )

    graph_proofs = {}
    for key, graph_spec in GRAPH_SPECS.items():
        graph_proofs[key] = build_graph(
            key, graph_spec, worldspec, boulder_mesh
        )

    proof = {
        "stage3g_r3_pcg_biomes_graphs": "success",
        "worldspec_path": str(Path(worldspec_value).resolve()),
        "generation_seed": int(worldspec["seed"]),
        "route_clearance_m": float(worldspec["route_clearance_m"]),
        "graphs": graph_proofs,
    }

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log("SUCCESS: authored PCG_Valley + PCG_HighAlpine")


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GR3PCGBiomes] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
