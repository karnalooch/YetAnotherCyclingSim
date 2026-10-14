"""Update the owner's current 2x2 map with existing PCG/PCGEx nodes.

This is input adaptation and MCP wiring, not a placement or mesh generator.
The V3 preview contract remains available unchanged.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

from scripts.worldgen import pcg365_pcgex_graph as g

MAP = g.MAP  # Canonical accepted Live Host consumer: /Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface
REVISION = "whole-area-v7-rocks-cliff-stamps-retired"
POLICIES = {
    "rocks": dict(g.POLICY, id="PCG365_ROCKS_V5", native_best_fit=True,
                  support_plane_tolerance_cm=60.0, support_maximum_slope_degrees=89.0),
    # The owner removed the V6 cliff stamps. Do not recreate that rejected lane.
}


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def asset_ref(path):
    return g.ref(path + "." + path.rsplit("/", 1)[1])


def find(a, cls):
    return a.call(g.SCENE, "find_actors", dict(root=None, name="", actor_type=g.ref(cls),
                                             tag="", bounds=None, collision_channels=[]))


def input_radius(assets, policy):
    radii = []
    for asset in assets:
        bounds = asset["expected_native_bounds_cm"]
        radii.append(math.sqrt(sum(max(abs(lo), abs(hi)) ** 2
                                  for lo, hi in zip(bounds["min"], bounds["max"]))))
    offset = policy.get("seat_offset", [0, 0, policy["embed_along_normal_cm"]])
    # Technical exclusions enclose the final mesh AND its declared seating offset.
    return max(radii) * policy.get("uniform_scale", 1.0) + math.sqrt(sum(x*x for x in offset))


def prepare_assets(a, catalog):
    results = []
    for asset in catalog["assets"]:
        source = Path(asset["source"])
        g.require(asset["license"] == "CC0-1.0" and source.is_file()
                  and source.stat().st_size == asset["bytes"]
                  and digest(source) == asset["sha256"], "Asset source/provenance changed")
        path = asset["mesh_package"]
        g.require(path.startswith("/Game/Generated/YACS/PCG365Ex/WholeAreaInputs/SM_"),
                  "Asset is outside the owned input folder")
        mesh = asset_ref(path)
        if asset.get("native_source_file"):
            native = asset["native_source_file"]
            g.require(digest(native["absolute_path"]) == native["sha256"], "Saved native source changed")
            a.call(g.ASSET, "load_asset", {"asset_path": asset["native_source_package"]})
            if not a.call(g.ASSET, "exists", {"path": path}):
                g.require(a.call(g.ASSET, "duplicate", {"path": asset["native_source_package"], "new_path": path}),
                          "Could not adapt saved native mesh input")
        elif not a.call(g.ASSET, "exists", {"path": path}):
            a.call(g.MESH, "import_file", dict(folder_path=path.rsplit("/", 1)[0],
                asset_name=path.rsplit("/", 1)[1], source_file=str(source),
                import_materials=False, import_textures=False, combine_meshes=True))
        # Inspect the full source LOD, not Nanite's reduced fallback mesh.
        if a.call(g.MESH, "is_nanite_enabled", dict(mesh=mesh)):
            a.call(g.MESH, "set_nanite_enabled", dict(mesh=mesh, enabled=False))
        triangles = a.call(g.MESH, "get_triangle_count", dict(mesh=mesh, lod_index=0))
        g.require(triangles == asset["expected_lod0_triangles"], "Imported topology differs")
        bounds = a.call(g.MESH, "get_bounds", dict(mesh=mesh))
        for side in ("min", "max"):
            g.require(all(abs(bounds[side][axis] - value) < .1 for axis, value in
                          zip("xyz", asset["expected_native_bounds_cm"][side])),
                      "Imported native bounds differ")
        material = asset_ref(asset["material_package"])
        slots = a.call(g.MESH, "get_material_slots", dict(mesh=mesh))
        g.require(slots, "Mesh has no material slots")
        for slot in slots:
            g.require(a.call(g.MESH, "set_material", dict(mesh=mesh, slot_name=slot, material=material)),
                      "Cannot bind existing limestone material")
            g.require(a.call(g.MESH, "get_material", dict(mesh=mesh, slot_name=slot)) == material,
                      "Material readback differs")
        a.call(g.MESH, "set_nanite_enabled", dict(mesh=mesh, enabled=True))
        g.require(a.call(g.MESH, "is_nanite_enabled", dict(mesh=mesh)), "Nanite not enabled")
        results.append(dict(mesh=mesh, source_sha256=asset["sha256"], bounds=bounds,
                            triangles=triangles, material=material, nanite=True))
        print("ASSET_READY", asset["id"], flush=True)
    g.require(a.call(g.ASSET, "save_assets", {"asset_paths": [x["mesh_package"] for x in catalog["assets"]]}),
              "Input mesh save failed")
    return results


def set_manual_generation(a, actor):
    components = a.call(g.ACTOR, "get_components", dict(actor=actor, component_type=g.ref("/Script/PCG.PCGComponent")))
    g.require(len(components) == 1, "Expected one PCG component")
    g.require(a.call(g.OBJECT, "set_properties", dict(instance=components[0],
              values=json.dumps({"bRegenerateInEditor": False}))), "Cannot select manual generation")


def update_world(input_path, input_sha, output, asset_catalog):
    output = Path(output)
    g.require(digest(input_path) == input_sha, "Source input changed")
    data = json.loads(Path(input_path).read_text())
    g.verify_input(data)
    catalog = json.loads(Path(asset_catalog).read_text())
    g.require({x["lane"] for x in catalog["assets"]} == {"small", "boulders", "cliffs"}, "Incomplete asset catalog")
    save(output / "whole-area-assets.json", catalog)
    identity = hashlib.sha256((input_sha + digest(asset_catalog) + digest(__file__)
                               + digest(g.__file__)).encode()).hexdigest()
    a = g.Author(input_path, input_sha, output)
    g.require(a.call(g.SCENE, "get_current_level", {}) == MAP, "The owner's current map is not open")
    roads = find(a, "/Script/GeometryFramework.DynamicMeshActor")
    g.require(len(roads) == 559, "Road/CUT inventory differs")
    original_instances = a.call(g.PCG, "ListGraphInstances", {})
    landscapes = find(a, "/Script/Landscape.Landscape")
    landscape_materials = [a.call(g.OBJECT, "get_properties", dict(instance=x, properties=["LandscapeMaterial"]))
                           for x in landscapes]
    native_assets = prepare_assets(a, dict(catalog, assets=[
        asset for asset in catalog["assets"] if asset["lane"] != "cliffs"]))
    lane_results = []
    for lane, base_policy in POLICIES.items():
        policy = dict(base_policy)
        lane_dir = output / lane
        lane_dir.mkdir()
        assets = [x for x in catalog["assets"] if (x["lane"] == "cliffs") == (lane == "cliffs")]
        if policy.get("group_by_mesh_footprint"):
            # Source dimensions define the available fragment box; PCGEx owns
            # grouping, the representative source point and the final mesh fit.
            width = max(max(hi - lo for lo, hi in zip(asset["expected_native_bounds_cm"]["min"],
                                                      asset["expected_native_bounds_cm"]["max"]))
                        for asset in assets)
            policy.update(fuse_footprint_cm=width, fit_extent_cap_cm=width / 2)
        points = data["whole_area_layers"]["cliffs" if lane == "cliffs" else "scree"]
        lane_data = dict(points=points, assets=assets, radius_cm=input_radius(assets, policy))
        save(lane_dir / "lane-input.json", lane_data)
        a = g.Author(input_path, input_sha, lane_dir)
        a.folder = "/Game/Generated/YACS/PCG365Ex/WholeAreaV7/R" + identity[:16] + "/" + lane
        a.graph_path = a.folder + "/PCG365_Rocks"
        a.collection_path = a.folder + "/DA_Rocks"
        if a.call(g.ASSET, "exists", {"path": a.graph_path}):
            tags = a.call(g.ASSET, "get_metadata_tags", {"asset_path": a.graph_path})
            g.require(tags.get("YACS.PCG365.WholeAreaIdentity") == identity,
                      "Existing graph is an incomplete or different run; inspect before retry")
            a.state["graph"] = a.call(g.ASSET, "load_asset", {"asset_path": a.graph_path})
        else:
            g.build_nodes(a, lane_data, policy)
        matching = [x for x in original_instances if x["graph"] == a.state["graph"]]
        g.require(len(matching) <= 1, "Duplicate native graph instances")
        instance = matching[0] if matching else a.call(g.PCG, "SpawnGraphInstance", dict(
            graph=a.state["graph"], name="PCG365_WholeArea_" + lane,
            transform=dict(location=g.v(100825, 100825, 0), scale=g.v(1100, 1100, 1100)), jsonParams="{}"))
        a.state["instance"] = instance
        a.save()
        time.sleep(3)
        messages = a.call(g.PCG, "ExecuteGraphInstance", {"pCGVolume": instance["actor"]})
        save(lane_dir / "initial-generation.json", messages)
        g.require(not messages, "Native generation reports messages; inspect before saving")
        set_manual_generation(a, instance["actor"])
        g.finalize_collection(a)
        messages = a.call(g.PCG, "ExecuteGraphInstance", {"pCGVolume": instance["actor"]})
        save(lane_dir / "generation-messages.json", messages)
        g.require(not messages, "Final generation reports messages")
        proof = g.inspect_instances(a, instance["actor"])
        count = sum(len(x["PerInstanceSMData"]) for x in proof)
        g.require(count > 0, "A full-area lane produced no instances")
        save(lane_dir / "native-instances.json", proof)
        a.call(g.ASSET, "update_metadata_tags", dict(asset_path=a.graph_path,
            set_tags={"YACS.PCG365.WholeAreaIdentity": identity, "YACS.PCG365.Recipe": REVISION}, remove_tags=[]))
        g.require(a.call(g.ASSET, "save_assets", {"asset_paths": [a.graph_path, a.collection_path]}), "Graph save failed")
        result = dict(lane=lane, policy=policy, graph=a.state["graph"], actor=instance["actor"],
                      native_instances=count, input_points=len(points), radius_cm=lane_data["radius_cm"])
        save(lane_dir / "native-result.json", result)
        lane_results.append(result)
        print("LANE_READY", lane, count, flush=True)
    # Replace ONLY owned previous PCG365 output after all new lanes have succeeded.
    kept = {x["graph"]["refPath"] for x in lane_results}
    removed = []
    for item in original_instances:
        owned = any(label in item["actor"]["refPath"] for label in (g.LABEL, "PCG365_WholeArea_"))
        if owned and item["graph"]["refPath"] not in kept:
            g.require(a.call(g.SCENE, "remove_from_scene", {"actor": item["actor"]}), "Old preview removal failed")
            removed.append(item)
    g.require(find(a, "/Script/GeometryFramework.DynamicMeshActor") == roads, "Road inventory changed")
    g.require([a.call(g.OBJECT, "get_properties", dict(instance=x, properties=["LandscapeMaterial"]))
               for x in landscapes] == landscape_materials, "Landscape material changed")
    g.require(a.call(g.SCENE, "get_current_level", {}) == MAP, "Current map changed")
    g.require(a.call(g.ASSET, "save_assets", {"asset_paths": [MAP]}), "Current map save failed")
    result = dict(status="WHOLE_AREA_PCGEX_SAVED_IN_PLACE", map_package=MAP,
        source_input_sha256=input_sha, identity=identity, recipe_revision=REVISION,
        area_size_m=[2016.5, 2016.5], lanes=lane_results, native_assets=native_assets,
        removed_owned_previews=removed, map_copy_created=False, terrain_modified=False,
        road_actors=len(roads), landscape_materials=landscape_materials,
        ground_material_behavior="EXISTING_WHOLE_AREA_MATERIAL_RETAINED",
        placement_logic="NATIVE_PCG_PCGEX_NODES_ONLY", owner_visual="PENDING",
        whole_area_visual_acceptance=False, fresh_reload_verified=False,
        cliff_status="RETIRED_STAMPS_NATIVE_SURFACE_PILOT_ONLY",
        performance="DEFERRED_AFTER_M3", performance_pass=False)
    save(output / "native-result.json", result)
    return result
