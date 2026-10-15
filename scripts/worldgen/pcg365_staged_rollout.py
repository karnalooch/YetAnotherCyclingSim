"""Staged whole-area continuous cliff wall rollout across 63 raster batches (4.07 km2).

Executes the prepared 63 batches in 8 controlled row bands (r0 through r3584).
Spawns native PCG DynamicMeshComponent objects in /Game/Generated/YACS/PCG365Ex/WholeArea/L_PCG365_Rollout.
Saves map checkpoints after each row band, enforcing memory safety and full resume capability.
Never modifies canonical source map L_RoadSurface or 5/5 canonical checkpoints.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.worldgen import pcg365_pcgex_graph as g
from scripts.worldgen.pcg365_wall_surface import (
    ROLLOUT_MAP,
    verify_canonical_checkpoint_integrity,
)

BATCH_MANIFEST = Path("Saved/PCG365/full-walls-20261014/bounded-inputs/batch-manifest.json")
BOUNDED_INPUTS_DIR = Path("Saved/PCG365/full-walls-20261014/bounded-inputs")
TEXTURE_FOLDER = "/Game/Generated/YACS/PCG365Ex/WallSurface/Batches"
GRAPH_PATH = "/Game/Generated/YACS/PCG365Ex/WallSurface/Batches/PCG365_WallBatch"
GRAPH_REF = GRAPH_PATH + ".PCG365_WallBatch"
ROLLOUT_DIR = Path("Saved/PCG365/full-walls-rollout")


def get_or_import_texture(client: g.Client, batch_name: str, png_path: Path) -> Dict[str, str]:
    asset_name = "T_" + batch_name.replace(".png", "")
    full_path = f"{TEXTURE_FOLDER}/{asset_name}"
    exists_resp = client.call(
        "call_tool",
        {"toolset_name": g.ASSET, "tool_name": "exists", "arguments": {"path": full_path}},
    )
    if not g.unpack(exists_resp).get("returnValue", False):
        import_resp = client.call(
            "call_tool",
            {
                "toolset_name": "editor_toolset.toolsets.texture.TextureTools",
                "tool_name": "import_file",
                "arguments": {
                    "folder_path": TEXTURE_FOLDER,
                    "asset_name": asset_name,
                    "source_file": str(png_path.resolve()),
                },
            },
        )
        assert not import_resp.get("isError"), f"Failed to import texture {png_path}"

    tex_ref = {"refPath": f"{full_path}.{asset_name}"}
    client.call(
        "call_tool",
        {
            "toolset_name": g.OBJECT,
            "tool_name": "set_properties",
            "arguments": {
                "instance": tex_ref,
                "values": json.dumps({
                    "SRGB": False,
                    "CompressionSettings": "TC_VectorDisplacementmap",
                    "MipGenSettings": "TMGS_NoMipmaps",
                    "Filter": "TF_Nearest",
                    "NeverStream": True,
                }),
            },
        },
    )
    return tex_ref


def execute_batch(
    client: g.Client,
    batch_info: Dict[str, Any],
    texture_ref: Dict[str, str],
) -> Dict[str, Any]:
    batch_name = batch_info["path"].replace(".png", "")
    actor_name = f"PCG365_Wall_{batch_name}"
    t_transform = batch_info["texture_transform"]
    loc = t_transform["location"]
    scale = t_transform["scale"]

    # 1. Update texture_probe on PCG365_WallBatch
    node_ref = {"refPath": f"{GRAPH_REF}:texture_probe"}
    props = {
        "texture": texture_ref,
        "transform": {
            "location": loc,
            "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "scale": scale,
        },
        "bUseAbsoluteTransform": True,
        "bUseDensitySourceChannel": True,
        "colorChannel": "Alpha",
        "filter": "Point",
        "texelSize": 50,
        "bForceEditorOnlyCPUSampling": True,
        "bKeepZeroDensityPoints": False,
    }
    upd_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.PCG,
            "tool_name": "UpdateNode",
            "arguments": {
                "node": node_ref,
                "nodeTitle": "Texture Probe",
                "jsonParams": json.dumps(props),
            },
        },
    )
    assert g.unpack(upd_resp).get("returnValue", False), f"Failed to update texture_probe for {batch_name}"

    # 2. Check if actor already exists in the scene
    find_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.SCENE,
            "tool_name": "find_actors",
            "arguments": {
                "root": None,
                "name": actor_name,
                "actor_type": None,
                "tag": "",
                "bounds": None,
                "collision_channels": [],
            },
        },
    )
    found = g.unpack(find_resp).get("returnValue", [])
    matching = [a for a in found if actor_name in a.get("refPath", "")]
    exec_msgs = []

    if matching:
        actor_ref = matching[0]
        # Check if dynamic mesh component already exists
        mesh_comps_resp = client.call(
            "call_tool",
            {
                "toolset_name": g.ACTOR,
                "tool_name": "get_components",
                "arguments": {
                    "actor": actor_ref,
                    "component_type": {"refPath": "/Script/GeometryFramework.DynamicMeshComponent"},
                },
            },
        )
        existing_mesh_comps = g.unpack(mesh_comps_resp).get("returnValue", [])
        if existing_mesh_comps:
            mesh_comp = existing_mesh_comps[0]
            # Already generated, ensure locked
            pcg_comps_resp = client.call(
                "call_tool",
                {
                    "toolset_name": g.ACTOR,
                    "tool_name": "get_components",
                    "arguments": {
                        "actor": actor_ref,
                        "component_type": {"refPath": "/Script/PCG.PCGComponent"},
                    },
                },
            )
            pcg_comps = g.unpack(pcg_comps_resp).get("returnValue", [])
            if pcg_comps:
                client.call(
                    "call_tool",
                    {
                        "toolset_name": g.OBJECT,
                        "tool_name": "set_properties",
                        "arguments": {
                            "instance": pcg_comps[0],
                            "values": json.dumps({"bRegenerateInEditor": False}),
                        },
                    },
                )
            bounds_resp = client.call(
                "call_tool",
                {
                    "toolset_name": g.ACTOR,
                    "tool_name": "get_actor_bounds",
                    "arguments": {"actor": actor_ref},
                },
            )
            actor_bounds = g.unpack(bounds_resp).get("returnValue", {})
            return {
                "batch": batch_info["path"],
                "actor": actor_ref["refPath"],
                "mesh_component": mesh_comp["refPath"],
                "selected_vertices": batch_info["selected_vertices"],
                "actor_bounds": actor_bounds,
                "messages": [],
                "status": "GENERATED",
            }
        else:
            # Half-initialized actor without mesh, remove and respawn
            client.call(
                "call_tool",
                {"toolset_name": g.SCENE, "tool_name": "remove_from_scene", "arguments": {"actor": actor_ref}},
            )

    # Spawn new PCGVolume instance enclosing the batch extent
    vol_scale_x = max(300.0, float(scale["x"]) / 50.0)
    vol_scale_y = max(300.0, float(scale["y"]) / 50.0)
    spawn_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.PCG,
            "tool_name": "SpawnGraphInstance",
            "arguments": {
                "graph": {"refPath": GRAPH_REF},
                "name": actor_name,
                "transform": {
                    "location": {"x": loc["x"], "y": loc["y"], "z": 500000.0},
                    "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
                    "scale": {"x": vol_scale_x, "y": vol_scale_y, "z": 6000.0},
                },
                "jsonParams": "{}",
            },
        },
    )
    spawn_val = g.unpack(spawn_resp)
    actor_ref = spawn_val["returnValue"]["actor"]

    # 3. Execute Graph Instance
    exec_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.PCG,
            "tool_name": "ExecuteGraphInstance",
            "arguments": {"pCGVolume": actor_ref},
        },
    )
    exec_msgs = g.unpack(exec_resp).get("returnValue", [])

    # 4. Set bRegenerateInEditor = False on PCGComponent to lock geometry
    pcg_comps_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.ACTOR,
            "tool_name": "get_components",
            "arguments": {
                "actor": actor_ref,
                "component_type": {"refPath": "/Script/PCG.PCGComponent"},
            },
        },
    )
    pcg_comps = g.unpack(pcg_comps_resp).get("returnValue", [])
    if pcg_comps:
        client.call(
            "call_tool",
            {
                "toolset_name": g.OBJECT,
                "tool_name": "set_properties",
                "arguments": {
                    "instance": pcg_comps[0],
                    "values": json.dumps({"bRegenerateInEditor": False}),
                },
            },
        )

    # 5. Inspect spawned DynamicMeshComponent
    mesh_comps_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.ACTOR,
            "tool_name": "get_components",
            "arguments": {
                "actor": actor_ref,
                "component_type": {"refPath": "/Script/GeometryFramework.DynamicMeshComponent"},
            },
        },
    )
    mesh_comps = g.unpack(mesh_comps_resp).get("returnValue", [])
    mesh_comp = mesh_comps[0] if mesh_comps else None

    bounds_resp = client.call(
        "call_tool",
        {
            "toolset_name": g.ACTOR,
            "tool_name": "get_actor_bounds",
            "arguments": {"actor": actor_ref},
        },
    )
    actor_bounds = g.unpack(bounds_resp).get("returnValue", {})

    return {
        "batch": batch_info["path"],
        "actor": actor_ref["refPath"],
        "mesh_component": mesh_comp["refPath"] if mesh_comp else None,
        "selected_vertices": batch_info["selected_vertices"],
        "actor_bounds": actor_bounds,
        "messages": exec_msgs,
        "status": "GENERATED" if mesh_comp else "NO_MESH_COMPONENT",
    }


def run_staged_rollout(
    start_band: int = 0,
    end_band: int = 7,
    save_between_bands: bool = True,
) -> Dict[str, Any]:
    verify_canonical_checkpoint_integrity()

    client = g.Client()
    current_level = g.unpack(client.call(
        "call_tool",
        {"toolset_name": g.SCENE, "tool_name": "get_current_level", "arguments": {}},
    )).get("returnValue")
    assert current_level == ROLLOUT_MAP, f"Expected current map {ROLLOUT_MAP}, got {current_level}"

    ROLLOUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(BATCH_MANIFEST.read_text())
    batches = manifest["batches"]

    # Group batches by row band: r0, r512, r1024, r1536, r2048, r2560, r3072, r3584
    from collections import defaultdict
    row_bands = defaultdict(list)
    for b in batches:
        row_bands[b["bounds_rc"][0]].append(b)

    band_rows = sorted(row_bands.keys())
    progress_file = ROLLOUT_DIR / "rollout-progress.json"
    progress = {}
    if progress_file.exists():
        try:
            progress = json.loads(progress_file.read_text())
        except Exception:
            progress = {}

    all_results = progress.get("results", {})

    print(f"=== PCG365 WHOLE AREA CONTINUOUS WALL ROLLOUT (Bands {start_band} to {end_band}) ===", flush=True)

    for band_idx, row_start in enumerate(band_rows):
        if band_idx < start_band or band_idx > end_band:
            continue

        band_name = f"band_{band_idx}_r{row_start}"
        band_batches = row_bands[row_start]
        print(f"\n--- Starting {band_name} ({len(band_batches)} batches, row {row_start}) ---", flush=True)

        band_results = []
        for b_idx, b_info in enumerate(band_batches):
            b_name = b_info["path"]
            if b_name in all_results and all_results[b_name].get("status") == "GENERATED":
                print(f"[{b_idx+1}/{len(band_batches)}] {b_name}: ALREADY GENERATED, skipping.", flush=True)
                band_results.append(all_results[b_name])
                continue

            png_path = BOUNDED_INPUTS_DIR / b_name
            tex_ref = get_or_import_texture(client, b_name, png_path)
            res = execute_batch(client, b_info, tex_ref)
            band_results.append(res)
            all_results[b_name] = res
            print(f"[{b_idx+1}/{len(band_batches)}] {b_name}: {res['status']} | actor: {res['actor'].split('.')[-1]}", flush=True)

        if save_between_bands:
            print(f"Saving checkpoint for {band_name}...", flush=True)
            save_resp = client.call(
                "call_tool",
                {"toolset_name": g.ASSET, "tool_name": "save_assets", "arguments": {"asset_paths": [ROLLOUT_MAP, GRAPH_PATH]}},
            )
            assert g.unpack(save_resp).get("returnValue", False), f"Failed to save level at {band_name}"
            verify_canonical_checkpoint_integrity()

        progress = {
            "timestamp": time.time(),
            "last_completed_band": band_idx,
            "last_completed_row": row_start,
            "total_batches_completed": len([k for k, v in all_results.items() if v.get("status") == "GENERATED"]),
            "results": all_results,
        }
        progress_file.write_text(json.dumps(progress, indent=2))
        print(f"--- Completed {band_name}: {len(band_results)} batches recorded ---", flush=True)

    print("\n=== ROLLOUT RUN COMPLETED ===", flush=True)
    return progress


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-band", type=int, default=0, help="First row band index (0-7)")
    parser.add_argument("--end-band", type=int, default=7, help="Last row band index (0-7)")
    parser.add_argument("--no-save", action="store_true", help="Do not save level between bands")
    args = parser.parse_args()

    run_staged_rollout(
        start_band=args.start_band,
        end_band=args.end_band,
        save_between_bands=not args.no_save,
    )
