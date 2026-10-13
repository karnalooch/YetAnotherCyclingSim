"""Compose the PCG365 slope-aligned preview from existing PCGEx nodes.

No placement solver is implemented here. Python converts authenticated input
records to PCG points and wires existing nodes. Run build_preview() in Unreal.
Requires the PCGEx 0.79 API; absence/drift fails before generation. Native
generation and support-screen results are not the frozen V2 contact proof.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

POLICY = {
    "id": "PCG365_PCGEX_SLOPE_ALIGNED_PREVIEW_V3",
    "maximum_slope_degrees": 42.0,
    "uniform_scale": 1.0,
    "seed": 36501,
    "source_clearance_cm": 50.0,
    "support_plane_tolerance_cm": 4.0,
    "embed_along_normal_cm": 5.0,
    "support_status": "PCGEX_FIVE_PROBE_SCREEN_NOT_V2_CONTACT_QUALIFICATION",
}
MAP = "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface"
LABEL = "PCG365_PCGEx_V3_Preview"
ACTIVE = []


def require(value, message):
    if not value:
        raise ValueError(message)


def selector(name):
    """Serialize UE's existing selector; no expression evaluator of our own."""
    parts = name.lstrip("$").split(".")
    return {
        "Selection": "Property" if name.startswith("$") else "Attribute",
        "PropertyName" if name.startswith("$") else "AttributeName": parts[0],
        "ExtraNames": parts[1:],
    }


def constant(value):
    return {"Input": "Constant", "Constant": value}


def vector(x=0.0, y=0.0, z=0.0):
    return {"X": x, "Y": y, "Z": z}


def recipe(collection_path, radius_cm):
    """Return a graph of stock nodes, with all placement decisions in PCGEx.

    The four support probes are ordinary Transform/Line Trace/Filter nodes.
    They screen a plane around the point; they do not prove continuous contact.
    One dataset flows through pruning so tile seams cannot evade overlap tests.
    """
    require(math.isfinite(radius_cm) and 0 < radius_cm <= 250, "Invalid rock radius")
    nodes, edges = [], []

    def node(name, cls, props=None):
        nodes.append({"id": name, "class": cls, "properties": props or {}})
        return name

    def edge(a, b, source="Out", target="In"):
        edges.append([a, source, b, target])

    def filter_stack(name, previous, rules, source="Out"):
        hub = node(name, "PCGExUberFilterSettings", {"bOutputDiscardedElements": True})
        edge(previous, hub, source)
        for index, (attribute, operator, value) in enumerate(rules):
            condition = node(f"{name}_rule{index}", "PCGExNumericCompareFilterProviderSettings", {
                "Config": {"OperandA": selector(attribute), "Comparison": operator,
                           "OperandBValue": constant(value)},
            })
            edge(condition, hub, "Filter", "Filters")
        return hub

    def move(name, previous, xyz, absolute, source="Out"):
        target = node(name, "PCGTransformPointsSettings", {
            "OffsetMin": vector(*xyz), "OffsetMax": vector(*xyz),
            "bAbsoluteOffset": absolute, "bRecomputeSeed": False,
        })
        edge(previous, target, source)
        return target

    def trace(name, previous, apply, distance):
        target = node(name, "PCGExSampleSurfaceGuidedSettings", {
            "SurfaceSource": "ActorReferences", "Origin": selector("$Position"),
            "Direction": selector("TraceDirection"),
            "Distance": constant(distance), "bPruneFailedSamples": True,
            "bWriteNormal": True, "NormalAttributeName": "GroundNormal",
            "bWriteDistance": True, "DistanceAttributeName": "GroundDistance",
            "bWriteSuccess": True, "SuccessAttributeName": "GroundHit",
            "RotationConstruction": "Z", "CrossAxis": constant(vector(1, 0, 0)),
            "CollisionSettings": {"bTraceComplex": True},
            "ApplySampling": {"bApplyTransform": apply, "TransformPosition": 7 if apply else 0,
                              "TransformRotation": 7 if apply else 0, "TransformScale": 0},
        })
        # Direction is supplied as a dedicated attribute by a stock Add Attribute
        # node at build time. It remains world-down after point rotation changes.
        edge(previous, target)
        edge("ground", target, "Out", "Actor References")
        return target

    node("input", "PCGCreatePointsSettings")
    node("ground", "PCGDataFromActorSettings", {
        "ActorSelector": {"ActorFilter": "AllWorldActors", "ActorSelection": "ByClass",
                          "ActorSelectionClass": "/Script/Landscape.Landscape"},
        "Mode": "GetSinglePoint", "bMergeSinglePointData": True,
        "bAlwaysRequeryActors": True, "bComponentsMustOverlapSelf": False,
    })
    node("road_bounds", "PCGCreatePointsSettings")
    source = filter_stack("source_masks", "input", [
        ("$Color.X", "EqualOrSmaller", POLICY["maximum_slope_degrees"]),
        ("$Color.Y", "EqualOrGreater", radius_cm + POLICY["source_clearance_cm"]),
    ])
    node("direction", "PCGAddAttributeSettings")
    edge(source, "direction", "Inside")
    projected = trace("project_and_align", "direction", True, 2000000.0)
    slope = filter_stack("native_slope", projected, [
        ("GroundNormal.Z", "EqualOrGreater", math.cos(math.radians(42.0))),
    ])
    staged = node("stage_assets", "PCGExAssetStagingSettings", {
        "SourceCollection": constant(collection_path), "OutputMode": "CollectionMap",
        "SelectorMode": "External", "bApplyFitting": True, "Seed": POLICY["seed"],
        "ScaleToFit": {"ScaleToFitMode": "None"},
        "Justification": {"bDoJustifyX": False, "bDoJustifyY": False, "bDoJustifyZ": False},
        "bConsiderEntryScaleToFit": False, "bConsiderEntryJustification": False,
    })
    edge(slope, staged, "Inside")
    choice = node("asset_choice", "PCGExSelectorClassicFactoryProviderSettings", {
        "Config": {"Mode": "WeightedRandom"},
    })
    edge(choice, staged, "Selector", "Selector")
    reject = node("current_road_exclusion", "PCGExBoundsFilterProviderSettings", {
        "Config": {"CheckType": "Intersects", "bInvert": True},
    })
    edge("road_bounds", reject, "Out", "Bounds")
    road_filter = node("protect_current_road", "PCGExUberFilterSettings")
    edge(staged, road_filter)
    edge(reject, road_filter, "Filter", "Filters")
    # Prune before support probes: dense points are thinned by PCGEx, not Python.
    previous = node("rock_spacing", "PCGExSelfPruningSettings", {
        "bRandomize": True, "Seed": POLICY["seed"], "bPreciseTest": True,
        "PrimaryMode": "After", "PrimaryExpansionValue": constant(25.0),
        "SecondaryMode": "After", "SecondaryExpansionValue": constant(25.0),
        "bOutputDiscard": True,
    })
    edge(road_filter, previous, "Inside")
    # Radius covers any orientation of either imported rock. Four surrounding
    # samples and the centre are computed entirely by PCGEx's native ray node.
    tolerance = POLICY["support_plane_tolerance_cm"]
    for index, (x, y) in enumerate(((radius_cm, 0), (-radius_cm, 0), (0, radius_cm), (0, -radius_cm))):
        previous = move(f"probe{index}_offset", previous, (x, y, 0), False)
        previous = move(f"probe{index}_above", previous, (0, 0, 1000), True)
        previous = trace(f"probe{index}_trace", previous, False, 2000.0)
        previous = filter_stack(f"probe{index}_support", previous, [
            ("GroundDistance", "EqualOrGreater", 1000.0 - tolerance),
            ("GroundDistance", "EqualOrSmaller", 1000.0 + tolerance),
            ("GroundNormal.Z", "EqualOrGreater", math.cos(math.radians(42.0))),
        ])
        previous = move(f"probe{index}_restore_z", previous, (0, 0, -1000), True, "Inside")
        previous = move(f"probe{index}_restore_xy", previous, (-x, -y, 0), False)
    previous = move("seat_rock", previous, (0, 0, -POLICY["embed_along_normal_cm"]), False)
    node("spawn", "PCGStaticMeshSpawnerSettings")
    edge(previous, "spawn")
    edge(staged, "spawn", "Map", "Overrides")
    edges.append(["spawn", "Out", "output", "Out"])
    return {"policy": POLICY.copy(), "nodes": nodes, "edges": edges}


def verify_input(document):
    require(document["schema_version"] == 1 and document["policy"] == POLICY, "Input policy differs")
    require(document["map_package"] == MAP, "Wrong world")
    rows = document["points"]
    require(0 < len(rows) <= 50000, "Expected at most 50,000 exact source cells")
    seen = set()
    for row, col, slope, clearance in rows:
        require(type(row) is int and type(col) is int and 0 <= row < 4033 and 0 <= col < 4033,
                "Source cell outside the accepted grid")
        require((row, col) not in seen, "Duplicate source cell")
        seen.add((row, col))
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (slope, clearance))
                and 0 <= slope <= 90 and clearance >= 0, "Invalid source sample")
    require(math.isfinite(document["radius_cm"]) and 0 < document["radius_cm"] <= 250,
            "Invalid asset radius")


def native_capabilities(unreal):
    classes = {n["class"] for n in recipe("/Engine/Transient.PCG365Collection", 100)["nodes"]}
    classes |= {"PCGExMeshCollection", "PCGExMeshCollectionEntry", "PCGExMeshSelectorStaged",
                "PCGVolume", "PCGGraph", "ToolsetRegistry"}
    missing = sorted(name for name in classes if not hasattr(unreal, name))
    return {"required": sorted(classes), "missing": missing, "ready": not missing}


def build_preview(input_path, expected_sha256):
    """Build once in the current Editor; no server, plugin install or map save."""
    import unreal

    raw = Path(input_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "PCGEx input digest changed")
    data = json.loads(raw)
    verify_input(data)
    capabilities = native_capabilities(unreal)
    require(capabilities["ready"], "PCGEX_NOT_LOADED: " + ", ".join(capabilities["missing"]))
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(world.get_path_name().split(".")[0] == MAP, "Unexpected open map")
    original = list(actors.get_all_level_actors())
    require(not any(a.get_actor_label() == LABEL for a in original), "Existing PCGEx preview is preserved")
    grounds = [a for a in original if isinstance(a, unreal.Landscape)]
    require(len(grounds) == 1 and grounds[0].get_name() == "SaCalobraLandscape", "Ambiguous ground owner")
    roads = [a for a in original if isinstance(a, unreal.DynamicMeshActor)]
    require(len(roads) == 559, "Current road/CUT actor inventory differs")
    # Reuse the existing asset importer only as an input-format adapter.
    from scripts.live_host.recipes import rock_contact_scatter as inputs

    manifest = inputs.read_manifest(inputs.REGIONAL_MANIFEST_SHA256, require_plant=True)
    require(data["assets"] == manifest["assets"], "Input rock inventory changed")
    context = {"project": unreal.Paths.project_dir()}
    materials = inputs.load_materials(unreal, context, manifest)
    # Nothing is persisted. The folder is unique to these exact input bytes.
    destination = "/Game/Generated/YACS/PCG365PCGExPreview/R" + expected_sha256[:12]
    meshes = [inputs.import_mesh(unreal, a, materials[a["id"]], destination) for a in data["assets"]]
    collection = unreal.new_object(unreal.PCGExMeshCollection)
    entries = []
    for mesh in meshes:
        entry = unreal.PCGExMeshCollectionEntry()
        entry.set_editor_property("static_mesh", mesh)
        entry.set_editor_property("weight", 1)
        descriptor = entry.get_editor_property("ism_descriptor")
        body = descriptor.get_editor_property("body_instance")
        body.set_editor_property("collision_profile_name", "NoCollision")
        body.set_editor_property("collision_enabled", unreal.CollisionEnabled.NO_COLLISION)
        descriptor.set_editor_property("body_instance", body)
        entry.set_editor_property("ism_descriptor", descriptor)
        entries.append(entry)
    collection.set_editor_property("entries", entries)
    collection.call_method("EDITOR_RebuildStagingData")
    plan = recipe(collection.get_path_name(), data["radius_cm"])
    graph = unreal.new_object(unreal.PCGGraph)
    registry = unreal.ToolsetRegistry
    tool_class = unreal.load_class(None, "/Script/PCGToolset.PCGToolset")
    require(tool_class is not None, "PCG Toolset is unavailable")
    if not registry.is_toolset_class_registered(tool_class):
        registry.register_toolset_class(tool_class)
    schema = json.loads(registry.get_toolset_json_schema(tool_class))

    def update(node, properties):
        # Epic's installed AddNode whitelist excludes non-/Script/PCG classes.
        # Construct those through PCGGraph, then use the same reflected UpdateNode
        # operation exposed by MCP. No custom PCG execution engine is introduced.
        result = registry.execute_tool(schema["name"], "UpdateNode", json.dumps({
            "Node": node.get_path_name(), "JsonParams": json.dumps(properties),
        }))
        require(result.get_editor_property("bIsComplete") and not result.error,
                "PCG Toolset rejected node parameters: " + str(result.error))
        require(json.loads(result.value).get("returnValue") is True, "Node update failed")

    native = {}
    for index, definition in enumerate(plan["nodes"]):
        node, settings = graph.add_node_of_type(getattr(unreal, definition["class"]))
        native[definition["id"]] = (node, settings)
        node.set_editor_property("node_title", definition["id"])
        node.set_node_position((index % 8) * 280, (index // 8) * 180)
        if definition["properties"]:
            update(node, definition["properties"])
    create = native["input"][1]
    points = []
    for row, col, slope, clearance in data["points"]:
        p = unreal.PCGPoint()
        p.transform = unreal.Transform(location=unreal.Vector(col * 50, row * 50, 1000000))
        p.seed = row * 4033 + col + POLICY["seed"]
        p.color = unreal.Vector4(slope, clearance, 0, 1)
        points.append(p)
    create.set_editor_property("points_to_create", points)
    create.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    create.set_editor_property("cull_points_outside_volume", False)
    exclusion_points = []
    road_snapshot = []
    for actor in roads:
        center, extent = actor.get_actor_bounds(False)
        road_snapshot.append((actor, actor.get_actor_transform(), center, extent))
        p = unreal.PCGPoint()
        p.transform = unreal.Transform(location=unreal.Vector(center.x, center.y, 0))
        p.bounds_min = unreal.Vector(-extent.x - 50, -extent.y - 50, -1000000)
        p.bounds_max = unreal.Vector(extent.x + 50, extent.y + 50, 1000000)
        exclusion_points.append(p)
    bounds = native["road_bounds"][1]
    bounds.set_editor_property("points_to_create", exclusion_points)
    bounds.set_editor_property("coordinate_space", unreal.PCGCoordinateSpace.WORLD)
    bounds.set_editor_property("cull_points_outside_volume", False)
    # Use stock Add Attribute to carry a world-space ray direction.
    direction = native["direction"][1]
    attributes = direction.get_editor_property("attribute_types")
    attributes.set_editor_property("type", unreal.PCGMetadataTypes.VECTOR)
    attributes.set_editor_property("vector_value", unreal.Vector(0, 0, -1))
    direction.set_editor_property("attribute_types", attributes)
    update(native["direction"][0], {"OutputTarget": selector("TraceDirection")})
    spawner = native["spawn"][1]
    spawner.set_mesh_selector_type(unreal.PCGExMeshSelectorStaged)
    mesh_selector = spawner.get_editor_property("mesh_selector_parameters")
    require(isinstance(mesh_selector, unreal.PCGExMeshSelectorStaged), "Staged selector was not instantiated")
    mesh_selector.set_editor_property("use_template_descriptor", False)
    mesh_selector.set_editor_property("output_points", True)
    native["output"] = (graph.get_output_node(), None)
    for source, source_pin, target, target_pin in plan["edges"]:
        require(graph.add_edge(native[source][0], source_pin, native[target][0], target_pin),
                f"PCGEx pin contract differs: {source}.{source_pin} -> {target}.{target_pin}")
    volume = actors.spawn_actor_from_class(unreal.PCGVolume, unreal.Vector(), transient=True)
    require(volume is not None, "Cannot create owned PCG volume")
    volume.set_actor_label(LABEL)
    component = volume.pcg_component
    component.set_editor_property("generation_trigger", unreal.PCGComponentGenerationTrigger.GENERATE_ON_DEMAND)
    component.seed = POLICY["seed"]
    component.set_graph(graph)
    job = {"graph": graph, "collection": collection, "meshes": meshes, "volume": volume,
           "component": component, "input_sha256": expected_sha256,
           "status": "PCGEX_GENERATING", "started": time.monotonic(),
           "native_contact_qualification": False, "map_saved": False, "performance_pass": False}
    ACTIVE.append(job)

    def complete(completed_component):
        try:
            require(completed_component == component, "Wrong completion callback")
            for actor, transform, center, extent in road_snapshot:
                require(actor.get_actor_transform() == transform and actor.get_actor_bounds(False) == (center, extent),
                        "Road bounds/transform changed during PCG generation")
            output = component.get_generated_graph_output()
            point_data = [tag.to_tuple()[0] for tag in output.tagged_data]
            count = sum(item.get_num_points() for item in point_data
                        if isinstance(item, unreal.PCGBasePointData))
            job.update(status="PCGEX_PREVIEW_COMPLETED" if count else "PCGEX_EMPTY_OUTPUT", points=count)
            unreal.log(json.dumps({k: v for k, v in job.items() if isinstance(v, (str, int, float, bool))}))
        except Exception as error:
            job.update(status="PCGEX_FAILED", error=str(error))
            component.cleanup_local(True)
            unreal.log_error(str(error))

    component.on_pcg_graph_generated_external.add_callable(complete)
    component.generate_local(True)
    return job
