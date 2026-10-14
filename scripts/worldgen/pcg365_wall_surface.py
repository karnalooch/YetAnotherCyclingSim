"""Replay the continuous #365 wall using installed PCGEx and Epic native nodes.

Python adapts authenticated inputs, configures native nodes and checks readback.
No triangulation, normal calculation, envelope or material-weight algorithm runs
in Python. This updates the existing bounded wall without restarting Unreal.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
from pathlib import Path

from scripts.worldgen import pcg365_pcgex_graph as g
from scripts.worldgen import pcg365_whole_area as w
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


def check_normal_transfer(before, encoded, mesh):
    original, points, vertices = rows(before), rows(encoded), rows(mesh)
    positions = lambda data: [p["@Points.$Transform"]["translation"] for p in data]
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
    return dict(vertices=len(vertices), normal_projection_position_delta_cm=0,
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
    position = lambda p: p["@Points.$Transform"]["translation"]
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


def replay(state_path, source_path, surface_path, adapter_path, material_path, camera_path, output, hide_after=False):
    g.require(not output.exists(), "Preserve earlier evidence; output must be new")
    g.require(w.digest(source_path) == INPUT_SHA, "Pilot source input changed")
    surface = validate_surface(surface_path)
    state = json.loads(state_path.read_text())
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
    g.require(a.call(g.SCENE, "get_current_level", {}) == w.MAP, "Owner's current map changed")
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

    def inspect(name, pin):
        data = a.call(g.PCG, "GetNodeDataView", dict(pCGVolume=state["instance"]["actor"], node=state["nodes"][name], pinLabel=pin, attributeName="", startIndex=0, endIndex=-1))
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
        candidate = check_normal_transfer(separated, encoded, mesh)
        g.require(candidate["vertices"] == 12619, "Bounded wall coverage changed")
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
