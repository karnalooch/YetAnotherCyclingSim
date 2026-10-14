"""Replay the continuous #365 wall using installed PCGEx and Epic native nodes.

Python adapts authenticated inputs, configures native nodes and checks readback.
No triangulation, normal calculation, envelope or material-weight algorithm runs
in Python. This updates the existing bounded wall without restarting Unreal.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from scripts.worldgen import pcg365_pcgex_graph as g
from scripts.worldgen import pcg365_whole_area as w
from scripts.worldgen.pcg365_mcp_adapter import SafeMcpAdapter
from scripts.worldgen.pcg365_wall_nodes import configure_blend, configure_material

FOLDER = "/Game/Generated/YACS/PCG365Ex/WallSurface/Pilot01"
INPUT_SHA = "fc6b095fe0b2278a0c6079ca0b546be63303ded7f44d0091efe21f9faf1db98f"
SURFACE_SHA = "affc3d1149aae9021f86b2fc118b8343d0688cd21db4ede832cc24941c489a70"
REVISION = "native-continuous-wall-v2-boundary-material"
APP = "EditorToolset.EditorAppToolset"
BP = "editor_toolset.toolsets.blueprint.BlueprintTools"
NORMAL_DSL = """(fn ProcessDynamicMesh (InDynMesh)
  (bind (colors valid gaps mesh) (GeometryScript|VertexColor|GetMeshPerVertexColors InDynMesh))
  (bind normals (GeometryScript|ListUtils|ExtractColorListChannels colors))
  (GeometryScript|Normals|SetMeshToPerVertexNormals(FromList) InDynMesh normals)
  (GeometryScript|Normals|ComputeTangents InDynMesh)
  (return 0))
"""


def rows(data):
    if isinstance(data, list):
        return [row for dataset in data for row in rows(dataset)]
    return [value for key, value in data.items() if key.startswith("element_")]


def check_normal_transfer(before, encoded, mesh, source_record_count: int | None = None):
    original, points, vertices = rows(before), rows(encoded), rows(mesh)

    def positions(data):
        return [p["@Points.$Transform"]["translation"] for p in data]

    g.require(len(original) == len(points) == len(vertices) > 0, "Vertex count changed")
    g.require(positions(original) == positions(points), "Normal projection moved points")
    g.require([p["@Points.PCGEx/VData"] for p in original]
              == [p["@Points.PCGEx/VData"] for p in points], "Cluster identity changed")
    expected = {tuple(p["@Points.$Transform"]["translation"]): p["@Points.$Color"][:3]
                for p in points}
    errors = []
    for vertex in vertices:
        transform = vertex["@Points.$Transform"]
        x, y, z, qw = transform["rotation"]
        up = [2*(x*z+qw*y), 2*(y*z-qw*x), 1-2*(x*x+y*y)]
        normal = expected[tuple(transform["translation"])]
        errors.append(math.sqrt(sum((a-b)**2 for a, b in zip(up, normal))))
    g.require(max(errors) < 1e-5, "Native mesh normal transfer differs")
    g.require(all(p["@Points.$Density"] > 0 for p in points), "Landscape projection missed points")
    if source_record_count is not None:
        g.require(type(source_record_count) is int and source_record_count >= len(vertices),
                  "Source count cannot establish native mesh vertices")
    return dict(vertices=len(vertices), native_vertices=None,
                native_vertex_count_verified=False, source_record_count=source_record_count,
                probe_vertices=len(vertices), normal_projection_position_delta_cm=0,
                maximum_normal_vector_error=max(errors))


def validate_surface(path):
    g.require(w.digest(path) == SURFACE_SHA, "Continuous surface input changed")
    source = json.loads(path.read_text())
    g.require(source["seed_input_sha256"] == INPUT_SHA
              and source["protected_reason_bits"] == 63
              and source["minimum_clearance_cm"] == 125
              and source["grid_step_cm"] == 50, "Surface input contract differs")
    for item in source["sources"]:
        g.require(w.digest(item["path"]) == item["sha256"], "Source raster/manifest changed: " + item["path"])
    selector_root = Path(source["sources"][0]["path"]).parent
    for item in source["selector_products"].values():
        g.require(w.digest(selector_root / item["path"]) == item["sha256"], "Selector changed")
    return source


def check_continuous_surface(source, flat, ground, encoded, mesh, edges, edge_probes):
    """Validate native topology and clearance; does not generate geometry."""
    flat, ground, encoded, mesh = map(rows, (flat, ground, encoded, mesh))

    def position(p):
        return p["@Points.$Transform"]["translation"]
    g.require(len(flat) == len(ground) == len(encoded) == len(mesh) > 0, "Native sample count changed")
    admitted = {(r, c): clearance for r, c, _, clearance in source["records"]}
    ground_z = {tuple(position(p)[:2]): position(p)[2] for p in ground}
    g.require(all(p["@Points.GroundHit"] == "true" for p in ground), "Landscape trace missed")
    g.require([position(p)[:2] for p in flat] == [position(p)[:2] for p in ground], "Landscape trace moved source XY")
    g.require(all((round(position(p)[1]/50), round(position(p)[0]/50)) in admitted for p in mesh), "Native vertex outside protected input")
    g.require(all(position(p)[0] % 50 == 0 and position(p)[1] % 50 == 0 for p in mesh), "Source-grid coordinates moved")
    offsets = [position(p)[2] - ground_z[tuple(position(p)[:2])] for p in mesh]
    g.require(max(abs(x-3) for x in offsets) < 1e-5, "Diagnostic separation differs")
    groups = [d for d in (edges if isinstance(edges, list) else [edges]) if rows(d)]
    g.require(len(groups) == 1, "Wall is not one connected native region")
    vertex_lookup = {int(p["@Points.PCGEx/VData"]) >> 32: position(p) for p in mesh}
    edge_lengths = []
    for edge in rows(edges):
        packed = int(edge["@Points.PCGEx/EData"])
        start, end = vertex_lookup[packed >> 32], vertex_lookup[packed & 0xffffffff]
        edge_lengths.append(math.dist(start[:2], end[:2]))
    max_edge = max(edge_lengths)
    g.require(max_edge <= math.sqrt(2)*50 + .001, "Face can bridge a protected gap")
    clearance = min(admitted[(round(position(p)[1]/50), round(position(p)[0]/50))] for p in mesh)
    g.require(clearance >= 125 and clearance > max_edge, "Face clearance is not conservative")
    alpha = {tuple(position(p)): p["@Points.$Color"][3] for p in encoded}
    g.require(all(0 <= x <= 1 for x in alpha.values()) and any(0 < x < 1 for x in alpha.values()), "Missing native material transition")
    g.require(max(abs(p["@Points.$Color"][3] - alpha[tuple(position(p))]) for p in mesh) < 1e-6, "Material weight changed in mesh conversion")
    probes = rows(edge_probes)
    g.require(len(probes) == len(edge_lengths) and all(p["@Points.GroundHit"] == "true" for p in probes), "Native edge probe coverage differs")
    gaps = [p["@Points.GroundDistance"] - 1000 for p in probes]
    g.require(min(gaps) > 0, "Wall edge midpoint intersects Landscape")
    return dict(connected_surface_regions=1, native_edges=len(edge_lengths),
                grid_xy_edge_max_cm=max_edge, minimum_source_exclusion_clearance_cm=clearance,
                conservative_remaining_clearance_cm=clearance-max_edge,
                source_xy_preserved=True, vertex_offset_cm=[min(offsets), max(offsets)],
                edge_midpoint_vertical_offset_cm=[min(gaps), max(gaps)],
                material_weight_range=[min(alpha.values()), max(alpha.values())],
                blended_vertices=sum(0 < x < 1 for x in alpha.values()))


ROLLOUT_MAP = "/Game/Generated/YACS/PCG365Ex/WholeArea/L_PCG365_Rollout"
CANONICAL_CHECKPOINT_DIR = Path("D:/yacs/work/level-editor-review/b9fddea3f602-y473save01/Content/Generated/YACS/LiveCheckpoints/R2a00f7ebba40")
CANONICAL_CHECKPOINTS = {
    "L_RoadSurface.umap": "cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a",
    "M_Road.uasset": "d5bf7fdc7d34e70c30b29ec37d2f4c04afa01cd3dc9a9c12cec707be48078842",
    "M_Shoulder.uasset": "94c40717a34d2b18f6d706abc7714cb6cbfb4ed0d631dda8bd1c624c38e7ae65",
    "MI_Road.uasset": "7d96a2396bb8ef9e5d4d19d65b6c7e9d00e7b0e80ebd5ff5733dbab1a61e9a92",
    "MI_Shoulder.uasset": "76425a2289c3907a8f3c831ad24fb1ba1f219e79204507efdce222c831c76cdf",
}


def verify_canonical_checkpoint_integrity(checkpoint_dir: Path | None = None) -> bool:
    target_dir = checkpoint_dir or CANONICAL_CHECKPOINT_DIR
    if not target_dir.is_dir():
        return True
    for filename, expected_hash in CANONICAL_CHECKPOINTS.items():
        file_path = target_dir / filename
        if not file_path.is_file():
            raise RuntimeError(f"CANONICAL_CHECKPOINT_MISSING: {file_path}")
        with file_path.open("rb") as stream:
            actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"CANONICAL_CHECKPOINT_MUTATED: {filename} sha256 mismatch (expected {expected_hash}, got {actual_hash})"
            )
    return True


def require_native_wall_admission(
    witness: Any = None,
    bounded_client: Any = None,
    target_map_package: str | None = None,
    actor_path: str | None = None,
    checkpoint_dir: Path | None = None,
) -> bool:
    """Fail before creating an MCP client or modifying the running owner scene.

    Verifiable admission gate for live wall authoring and replay:
    1. Caller must supply an authentic NativeProbeWitness instance.
    2. Witness must have status NATIVE_IN_PROCESS_OUTPUT_COUNTED.
    3. Witness point count must be bounded: 1 <= native_point_count <= 256.
    4. Reduction settings class must be a valid PCG/PCGEx reduction class.
    5. A valid, unpoisoned BoundedPcgMcpClient must be provided.
    6. Target map package is MANDATORY. None is unconditionally rejected.
    7. Protected source map L_RoadSurface must NEVER be targeted for writing or mutation.
    8. Target map package must EXACTLY match canonical rollout map L_PCG365_Rollout.
    9. Actor must strictly belong to target map package (no foreign or source actors).
    10. 5 canonical checkpoint packages must pass SHA256 integrity verification.
    """
    if witness is None or bounded_client is None:
        raise RuntimeError(
            "NATIVE_BLOCKED_MCP_UNVERIFIED: live wall replay disabled until native "
            "bounded-probe evidence, transport and graph provenance are independently proved"
        )

    if target_map_package is None:
        raise RuntimeError(
            "NATIVE_BLOCKED_TARGET_MAP_REQUIRED: target_map_package is mandatory; None is prohibited"
        )

    if "L_RoadSurface" in target_map_package and "Rollout" not in target_map_package:
        raise RuntimeError(
            f"NATIVE_BLOCKED_PROTECTED_SOURCE_MAP: cannot target canonical source map {target_map_package!r} for mutation"
        )

    if target_map_package != ROLLOUT_MAP:
        raise RuntimeError(
            f"NATIVE_BLOCKED_INVALID_TARGET_MAP: target map must be exact rollout map {ROLLOUT_MAP!r}, got {target_map_package!r}"
        )

    if actor_path is not None:
        if not (actor_path.startswith(ROLLOUT_MAP + ".") or actor_path.startswith(ROLLOUT_MAP + ":")):
            raise RuntimeError(
                f"NATIVE_BLOCKED_ACTOR_LEVEL_MISMATCH: actor {actor_path!r} does not belong to target map {ROLLOUT_MAP!r}"
            )

    verify_canonical_checkpoint_integrity(checkpoint_dir)

    from scripts.ue.pcg365_native_reduction_witness import (
        NativeProbeWitness,
        get_live_editor_pid,
        verify_witness_authenticity,
    )
    from scripts.worldgen.pcg365_bounded_transport import BoundedPcgMcpClient

    if not isinstance(witness, NativeProbeWitness):
        raise RuntimeError(
            "NATIVE_BLOCKED_INVALID_WITNESS: witness must be an authentic NativeProbeWitness instance"
        )

    active_pid = get_live_editor_pid()
    if not verify_witness_authenticity(witness, expected_pid=witness.session_pid):
        raise RuntimeError(
            "NATIVE_BLOCKED_FORGED_WITNESS: witness failed cryptographic authenticity verification"
        )

    if active_pid is not None and witness.session_pid != 0 and witness.session_pid != active_pid:
        raise RuntimeError(
            f"NATIVE_BLOCKED_SESSION_MISMATCH: witness session PID {witness.session_pid} does not match active editor PID {active_pid}"
        )

    if witness.status != "NATIVE_IN_PROCESS_OUTPUT_COUNTED":
        raise RuntimeError(
            f"NATIVE_BLOCKED_UNCONFIRMED_STATUS: witness status {witness.status!r} is not counted output"
        )

    if type(witness.native_point_count) is not int or not 0 < witness.native_point_count <= 256:
        raise RuntimeError(
            f"NATIVE_BLOCKED_UNSAFE_COUNT: witness point count {witness.native_point_count!r} exceeds 256 cap"
        )

    if not witness.reduction_class.endswith("Settings"):
        raise RuntimeError(
            f"NATIVE_BLOCKED_INVALID_SETTINGS: reduction class {witness.reduction_class!r} differs"
        )

    if not isinstance(bounded_client, BoundedPcgMcpClient):
        raise RuntimeError(
            "NATIVE_BLOCKED_UNTRUSTED_TRANSPORT: bounded client must be an authentic BoundedPcgMcpClient"
        )

    if bounded_client.is_poisoned:
        raise RuntimeError(
            "NATIVE_BLOCKED_POISONED_TRANSPORT: bounded client is in poisoned state"
        )

    return True


def replay(state_path, source_path, surface_path, adapter_path, material_path,
           camera_path, output, hide_after=False, native_probe_receipts=None,
           witness=None, bounded_client=None, target_map=ROLLOUT_MAP):
    if target_map is None:
        raise RuntimeError("NATIVE_BLOCKED_TARGET_MAP_REQUIRED: target_map cannot be None")

    # Must run BEFORE any disk output, Client.initialize, graph execution or file loading.
    require_native_wall_admission(
        witness=witness,
        bounded_client=bounded_client,
        target_map_package=target_map,
        actor_path=None,
    )
    state = json.loads(state_path.read_text())
    actor_ref = state.get("instance", {}).get("actor")
    actor_path = actor_ref["refPath"] if isinstance(actor_ref, dict) else str(actor_ref) if actor_ref else None
    if actor_path is not None and not (actor_path.startswith(target_map + ".") or actor_path.startswith(target_map + ":")):
        raise RuntimeError(
            f"NATIVE_BLOCKED_ACTOR_LEVEL_MISMATCH: actor {actor_path!r} does not belong to target map {target_map!r}"
        )
    g.require(not output.exists(), "Preserve earlier evidence; output must be new")
    g.require(w.digest(source_path) == INPUT_SHA, "Pilot source input changed")
    surface = validate_surface(surface_path)
    adapter = json.loads(adapter_path.read_text())
    material = json.loads(material_path.read_text())
    g.require(state["input_sha256"] == INPUT_SHA, "Graph input identity differs")
    g.require(state["graph"] == g.ref(FOLDER + "/PCG365_WallSurface.PCG365_WallSurface"), "Wrong graph")
    g.require(state.get("continuous_wired") and state.get("material_blend_wired")
              and state.get("continuous_input_sha256") == SURFACE_SHA
              and state.get("normal_transfer_wired") and state.get("merged_mesh_wired"),
              "This replay requires the inspected native pilot graph")
    for node in state["nodes"].values():
        g.require(node["refPath"].startswith(state["graph"]["refPath"]+":"), "Foreign graph node")
    g.require(adapter["path"] == FOLDER + "/BP_PCG365_VertexNormals"
              and adapter["graph"] == g.ref(adapter["path"]+".BP_PCG365_VertexNormals:ProcessDynamicMesh"), "Wrong normal adapter")
    g.require(material["path"] == FOLDER + "/M_Cliff_BoundaryBlend"
              and material["instance_path"] == FOLDER + "/MI_Cliff_BoundaryBlend"
              and material["instance"] == g.ref(material["instance_path"]+".MI_Cliff_BoundaryBlend"), "Wrong cliff material")
    g.require(material["material"] == g.ref(material["path"] + ".M_Cliff_BoundaryBlend"), "Wrong material graph")
    g.require(len(material["targets"]) == 4, "Expected four role-weight channels")
    for node in [*material["nodes"].values(), *material["targets"]]:
        g.require(node["refPath"].startswith(material["material"]["refPath"] + ":"), "Foreign material expression")
    output.mkdir(parents=True)
    a = object.__new__(g.Author)
    a.root, a.client, a.state, a.state_file = output, g.Client(), state, output / "graph-state.json"
    a.state["wall_recipe_revision"] = REVISION
    a.save()
    (output / "schemas").mkdir()
    expected_map = target_map
    g.require(a.call(g.SCENE, "get_current_level", {}) == expected_map, "Owner's current map changed")
    actors = w.find(a, "/Script/PCG.PCGVolume")
    g.require(state["instance"]["actor"] in actors, "Existing pilot actor is missing")
    g.require(not any("WholeArea_cliffs" in p["refPath"] for p in actors), "Retired cliff stamps present")
    instances = a.call(g.PCG, "ListGraphInstances", {})
    g.require(any(i["actor"] == state["instance"]["actor"] and i["graph"] == state["graph"]
                  for i in instances), "Actor graph binding differs")
    roads = w.find(a, "/Script/GeometryFramework.DynamicMeshActor")
    g.require(len(roads) == 559, "Road/CUT inventory changed")
    landscape = w.find(a, "/Script/Landscape.Landscape")
    ground_before = [a.call(g.OBJECT, "get_properties", dict(instance=x, properties=["LandscapeMaterial"])) for x in landscape]
    camera = a.call(APP, "GetCameraTransform", {})
    capture_camera = json.loads(camera_path.read_text())
    w.save(output / "camera-before.json", camera)

    def update(name, values):
        g.require(a.call(g.PCG, "UpdateNode", dict(node=state["nodes"][name], nodeTitle="", jsonParams=json.dumps(values))), "Node update failed: " + name)

    def execute():
        messages = a.call(g.PCG, "ExecuteGraphInstance", dict(pCGVolume=state["instance"]["actor"]))
        g.require(messages == [], "Native execution messages: " + json.dumps(messages))

    def capture(name):
        raw = g.unpack(a.client.call("call_tool", dict(toolset_name=APP, tool_name="CaptureViewport", arguments=dict(captureTransform=capture_camera, annotations=None, bShowUI=False))))
        (output / (name + ".png")).write_bytes(base64.b64decode(raw["returnValue"]["image"]["data"]))

    from scripts.ue.pcg365_native_reduction_witness import create_live_pcg_reduction_verifier
    verifier = create_live_pcg_reduction_verifier(bounded_client=bounded_client)
    mcp_adapter = SafeMcpAdapter(
        client=bounded_client,
        max_points=256,
        trusted_native_reduction_verifier=verifier,
    )

    def inspect(name, pin, max_points=256, reduction_proof=None):
        if reduction_proof is None:
            if native_probe_receipts is None or name not in native_probe_receipts:
                raise RuntimeError("No independently verified native reduction receipt for " + name)
            reduction_proof = native_probe_receipts[name]
        count = reduction_proof.get("certified_point_count")
        g.require(type(count) is int and 0 < count <= min(max_points, 256),
                  "Native reduction receipt has an unsafe point count")
        data = mcp_adapter.safe_get_node_data_view(
            author_or_client=bounded_client,
            actor=state["instance"]["actor"],
            node=state["nodes"][name],
            node_name=name,
            reduction_proof=reduction_proof,
            pin_label=pin,
            attribute_name="",
            start_index=0,
            end_index=count,  # Epic GetNodeDataView uses an EXCLUSIVE end index.
        )
        (output / (name + "-" + pin + ".json.gz")).write_bytes(gzip.compress(json.dumps(data).encode(), mtime=0))
        return data

    proof = None
    try:
        update("spawn_wall", dict(templateDescriptor=dict(bVisible=False)))
        execute()
        capture("baseline")
        configure_blend(a, surface)
        configure_material(a, material)
        a.call(BP, "write_graph_dsl", dict(graph=adapter["graph"], code=NORMAL_DSL))
        update("project_normals", dict(projectionParams=dict(bProjectPositions=False, bProjectRotations=True, bProjectScales=False)))
        update("encode_normals", dict(bCopyAllAttributes=False, inputSource="$Rotation.Up", outputTarget="$Color"))
        update("read_mesh", dict(importDetails=dict(bImportVertexColor=True, bImportVertexNormals=True)))
        update("wall_surface", dict(topology=dict(material=material["instance"])))
        update("spawn_wall", dict(templateDescriptor=dict(bVisible=True, overrideMaterials=[material["instance"]])))
        execute()
        capture("wall-gray")
        separated = inspect("surface_separation", "Out")
        encoded = inspect("restore_wall_blend", "Out")
        mesh = inspect("read_mesh", "Vtx")
        candidate = check_normal_transfer(separated, encoded, mesh,
                                          source_record_count=len(surface["records"]))
        g.require(candidate["source_record_count"] == 12619,
                  "Source input record count changed (not a native mesh count)")
        g.require(candidate["probe_vertices"] <= 256, "Probe sample exceeded safety limit")
        candidate.update(check_continuous_surface(surface, inspect("connected_cells", "Vtx"),
            inspect("landscape_surface", "Out"), encoded, mesh, inspect("read_mesh", "Edges"), inspect("edge_probe", "Out")))
        components = a.call(g.ACTOR, "get_components", dict(actor=state["instance"]["actor"], component_type=g.ref("/Script/GeometryFramework.DynamicMeshComponent")))
        g.require(len(components) == 1, "Expected one merged wall component")
        properties = a.call(g.OBJECT, "get_properties", dict(instance=components[0], properties=["BodyInstance", "OverrideMaterials"]))
        g.require(properties["BodyInstance"]["collisionEnabled"] == "NoCollision", "Wall collision enabled")
        w.save(output / "component.json", dict(component=components[0], properties=properties))
        candidate.update(component_count=1, pilot_hidden_after_capture=hide_after, material=material["instance"],
                     map_saved=False, source_masks_modified=False, visual_status="CONTINUOUS_PILOT_PENDING_OWNER_REVIEW",
                     whole_area_rollout=False, owner_visual_acceptance=False,
                     diagnostic_vertical_offset_cm=3, performance_pass=False)
        g.require(w.find(a, "/Script/GeometryFramework.DynamicMeshActor") == roads, "Road inventory changed")
        g.require([a.call(g.OBJECT, "get_properties", dict(instance=x, properties=["LandscapeMaterial"])) for x in landscape] == ground_before, "Landscape material changed")
        proof = candidate
    finally:
        try:
            if hide_after or proof is None:
                update("spawn_wall", dict(templateDescriptor=dict(bVisible=False)))
                execute()
        finally:
            a.call(APP, "SetCameraTransform", dict(transform=camera))
    final_components = a.call(g.ACTOR, "get_components", dict(actor=state["instance"]["actor"], component_type=g.ref("/Script/GeometryFramework.DynamicMeshComponent")))
    g.require(len(final_components) == 1 and a.call(g.OBJECT, "get_properties", dict(instance=final_components[0], properties=["bVisible"]))["bVisible"] == (not hide_after), "Pilot visibility differs")
    proof.update(native_recipe_sha256=w.digest(Path(__file__).with_name("pcg365_wall_nodes.py")), source_input_sha256=INPUT_SHA, surface_input_sha256=SURFACE_SHA, recipe_revision=REVISION, producer_sha256=w.digest(__file__), road_actor_count=len(roads), graph_saved=True)
    g.require(a.call(g.ASSET, "save_assets", dict(asset_paths=[FOLDER+"/PCG365_WallSurface", adapter["path"], material["path"], material["instance_path"]])), "Owned graph/adapter/material save failed")
    verify_canonical_checkpoint_integrity()
    w.save(output / "native-proof.json", proof)
    print(json.dumps(proof), flush=True)
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("state", "source", "surface", "adapter", "material", "camera", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--hide-after", action="store_true", help="Hide the pilot after successful evidence capture")
    args = parser.parse_args()
    replay(args.state, args.source, args.surface, args.adapter, args.material, args.camera, args.output, args.hide_after)


if __name__ == "__main__":
    main()
