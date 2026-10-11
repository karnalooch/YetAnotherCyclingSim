"""Measure complex mesh support against the pinned #363 Landscape; no admission."""

import json
import math
from pathlib import Path

import unreal

from scripts.ue import sa_calobra_pcg_material_binding as material


def require(value, message):
    if not value:
        raise RuntimeError(message)


def vector(value):
    result = [float(value.x), float(value.y), float(value.z)]
    require(all(math.isfinite(v) for v in result), "Nonfinite native measurement")
    return result


def unpack(hit, actor, component=None):
    if hit is None:
        return None
    fields = hit.to_tuple()
    require(len(fields) == 18, "Unexpected native hit break shape")
    require(fields[0] is True and fields[1] is False, "Nonblocking/overlapping query")
    require(fields[9] == actor, "Unauthorized contact owner")
    require(component is None or fields[10] == component, "Unauthorized component")
    return {
        "position_cm": vector(fields[5]),
        "normal": vector(fields[7]),
        "actor": fields[9].get_path_name(),
        "component": fields[10].get_path_name(),
        "component_class": fields[10].get_class().get_name(),
    }


def measure(root, binding):
    root = Path(root)
    request = json.loads((root / "contact-request.json").read_text(encoding="utf-8"))
    sources = json.loads(
        (root / "qualification-sources.json").read_text(encoding="utf-8")
    )
    require(
        request["placement"] is False and len(request["points"]) <= 16,
        "Unbounded source witness",
    )
    require(
        unreal.EditorLoadingAndSavingUtils.load_map(sources["terrain"]["map_package"]),
        "Accepted #363 Landscape load failed",
    )
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    require(len(landscapes) == 1, "Ambiguous Landscape ownership")
    ground = landscapes[0]
    transform = ground.get_actor_transform()
    require(
        vector(transform.scale3d)[:2] == [50.0, 50.0],
        "Accepted Landscape XY scale differs",
    )
    rotation = transform.rotation.rotator()
    require(
        [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
        "Rotated Landscape requires separate mapping",
    )
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
    actor.set_actor_label("PCG365_ComplexSupportMeasurementOnly")
    component = actor.static_mesh_component
    material.bind_component(component, binding)
    component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
    component.set_collision_response_to_all_channels(
        unreal.CollisionResponseType.ECR_BLOCK
    )
    bounds = request["mesh_bounds_cm"]
    actual_bounds = component.static_mesh.get_bounds()
    require(
        vector(actual_bounds.origin) == bounds["origin"]
        and vector(actual_bounds.box_extent) == bounds["extent"],
        "Native mesh bounds differ from source witness: "
        + repr(
            {
                "expected": bounds,
                "actual_origin": vector(actual_bounds.origin),
                "actual_extent": vector(actual_bounds.box_extent),
            }
        ),
    )
    low = bounds["origin"][2] - bounds["extent"][2] - 100
    high = bounds["origin"][2] + bounds["extent"][2] + 100
    support = []
    for sample in request["points"][0]["samples"]:
        x, y = sample["local_xy_cm"]
        result = component.line_trace_component(
            unreal.Vector(x, y, low), unreal.Vector(x, y, high), True, False, False
        )
        if result is None:
            support.append(None)
            continue
        require(isinstance(result, tuple), "Unexpected component trace return shape")
        hits = [value for value in result if isinstance(value, unreal.HitResult)]
        require(
            len(hits) == 1,
            "Component trace does not expose exactly one native HitResult",
        )
        support.append(unpack(hits[0], actor, component))
    require(
        any(row is not None for row in support),
        "No native complex-collision support samples",
    )

    def trace(x, y, ignored):
        return unreal.SystemLibrary.line_trace_single(
            world,
            unreal.Vector(x, y, 150000),
            unreal.Vector(x, y, -150000),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            ignored,
            unreal.DrawDebugTrace.NONE,
            True,
        )

    rows = []
    collision = {}
    for point in request["points"]:
        require(
            len(point["samples"]) == len(support), "Support/source sample counts differ"
        )
        require(
            [s["local_xy_cm"] for s in point["samples"]]
            == [s["local_xy_cm"] for s in request["points"][0]["samples"]],
            "Support grid identity differs",
        )
        samples = []
        actors = subsystem.get_all_level_actors()
        ignored = [a for a in actors if a != ground]
        for source, bottom in zip(point["samples"], support):
            if bottom is None:
                continue
            x, y = source["world_xy_cm"]
            hit = trace(x, y, ignored)
            require(
                hit is not None,
                "Landscape support query missed; no stale height allowed",
            )
            native = unpack(hit, ground)
            require(
                native["component_class"] == "LandscapeHeightfieldCollisionComponent",
                "Unexpected Landscape collision owner class",
            )
            require(
                trace(x, y, actors) is None,
                "Ground exclusion negative control remained blocked",
            )
            fields = hit.to_tuple()
            owner = fields[10]
            collision[native["component"]] = {
                "enabled": str(owner.get_collision_enabled()),
                "profile": str(owner.get_collision_profile_name()),
            }
            normal = native["normal"]
            length = math.sqrt(sum(v * v for v in normal))
            require(length > 0, "Invalid Landscape contact normal")
            samples.append(
                {
                    "local_xy_cm": source["local_xy_cm"],
                    "mesh_bottom_local_cm": bottom["position_cm"][2],
                    "source_height_m": source["source_height_m"],
                    "native": native,
                    "source_native_delta_m": native["position_cm"][2] / 100
                    - source["source_height_m"],
                    "slope_deg": math.degrees(
                        math.acos(max(-1, min(1, normal[2] / length)))
                    ),
                }
            )
        require(
            len(samples) == sum(s is not None for s in support),
            "Incomplete support inventory",
        )
        root_z = max(
            s["native"]["position_cm"][2] - s["mesh_bottom_local_cm"] for s in samples
        )
        for sample in samples:
            sample["gap_m"] = (
                root_z
                + sample["mesh_bottom_local_cm"]
                - sample["native"]["position_cm"][2]
            ) / 100
        rows.append(
            {
                "candidate_id": point["candidate_id"],
                "world_xy_cm": point["world_xy_cm"],
                "analysis_root_z_cm": root_z,
                "analysis_embedding_m": 0,
                "transform_policy": "identity rotation/scale; lowest nonpenetrating sampled vertical translation, not approved placement",
                "max_sample_gap_m": max(s["gap_m"] for s in samples),
                "max_source_native_delta_m": max(
                    abs(s["source_native_delta_m"]) for s in samples
                ),
                "max_slope_deg": max(s["slope_deg"] for s in samples),
                "samples": samples,
            }
        )

    # Explicit wrong-owner and generated-content canaries above the first sample.
    first = rows[0]["samples"][0]["native"]["position_cm"]
    canaries = []
    cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    for index, label in enumerate(
        ("PCG365_UnrelatedCollider", "PCG365_GeneratedCollider")
    ):
        control = subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(first[0], first[1], first[2] + 300 * (index + 1)),
        )
        control.set_actor_label(label)
        control.static_mesh_component.set_static_mesh(cube)
        control.static_mesh_component.set_collision_enabled(
            unreal.CollisionEnabled.QUERY_ONLY
        )
        control.static_mesh_component.set_collision_response_to_all_channels(
            unreal.CollisionResponseType.ECR_BLOCK
        )
        if index:
            control.tags = [unreal.Name("PCG_Generated")]
        raw = trace(first[0], first[1], [])
        require(
            raw is not None and raw.to_tuple()[9] == control,
            "Wrong-owner canary not effective",
        )
        all_actors = subsystem.get_all_level_actors()
        filtered = unpack(
            trace(first[0], first[1], [a for a in all_actors if a != ground]), ground
        )
        require(filtered is not None, "Ground disappeared under canary")
        require(
            trace(first[0], first[1], all_actors) is None,
            "Excluded-ground canary remained blocked",
        )
        canaries.append(
            {
                "label": label,
                "unfiltered_hits_canary": True,
                "filtered_hits_landscape": True,
            }
        )
    require(
        trace(
            -10000, -10000, [a for a in subsystem.get_all_level_actors() if a != ground]
        )
        is None,
        "Outside-Landscape no-hit control failed",
    )
    return {
        "status": "REAL_LANDSCAPE_SAMPLED_CONTACT_MEASURED_QUALIFICATION_PENDING",
        "placement": False,
        "qualified_assets": [],
        "ground_owner": ground.get_path_name(),
        "ground_class": ground.get_class().get_name(),
        "map_package": sources["terrain"]["map_package"],
        "ground_transform": {
            "location_cm": vector(transform.translation),
            "scale": vector(transform.scale3d),
        },
        "ground_collision_components": collision,
        "material_readback": material.verify_binding(binding, component),
        "source_contract": {k: v for k, v in request.items() if k != "points"},
        "mesh_support": {
            "method": "upward complex collision rays; finite 9x9 interior AABB grid; not continuous render-triangle support",
            "trace_signature": str(component.line_trace_component.__doc__),
            "sample_count": len(support),
            "hits": sum(s is not None for s in support),
        },
        "cases": rows,
        "canaries": canaries,
        "all_actors_excluded_control": True,
        "contact_limits": "REQUIRED_UNSET",
        "datum_independently_verified": False,
        "latest_road_consumer_contact": "NOT_RUN",
        "scene_saved": False,
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        "performance_pass": False,
    }
