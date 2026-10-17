"""Transient sampled Boulder fitting on preserved #363 ground; no admission/save."""

import json
from pathlib import Path

import unreal

from scripts.assets.pcg_boulder_support import solve_support
from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue.sa_calobra_pcg_terrain_contact import require, unpack, vector


def prepare(root, binding):
    """Return receipt, world, transient actor, camera target in centimetres."""
    root = Path(root)
    request = json.loads((root / "contact-request.json").read_text(encoding="utf-8"))
    sources = json.loads(
        (root / "qualification-sources.json").read_text(encoding="utf-8")
    )
    require(
        request["placement"] is False and 4 <= len(request["points"]) <= 16,
        "Unbounded or missing diagnostic point",
    )
    require(
        unreal.EditorLoadingAndSavingUtils.load_map(sources["terrain"]["map_package"]),
        "Pinned diagnostic Landscape load failed",
    )
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(
        world.get_path_name().split(".")[0] == sources["terrain"]["map_package"],
        "Wrong diagnostic map",
    )
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        a
        for a in subsystem.get_all_level_actors()
        if isinstance(a, unreal.LandscapeProxy)
    ]
    require(len(landscapes) == 1, "Ambiguous Landscape ownership")
    ground = landscapes[0]
    transform = ground.get_actor_transform()
    rotation = transform.rotation.rotator()
    require(
        vector(transform.scale3d)[:2] == [50.0, 50.0]
        and [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
        "Unadmitted Landscape transform",
    )
    actor = subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(), transient=True
    )
    require(actor is not None, "Diagnostic actor spawn failed")
    try:
        actor.set_actor_label("PCG365_Boulder_SampledSettleDiagnostic")
        actor.set_actor_rotation(unreal.Rotator(0, 0, 0), False)
        actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
        component = actor.static_mesh_component
        material.bind_component(component, binding)
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        component.set_collision_response_to_all_channels(
            unreal.CollisionResponseType.ECR_BLOCK
        )
        bounds = request["mesh_bounds_cm"]
        actual = component.static_mesh.get_bounds()
        origin, extent = vector(actual.origin), vector(actual.box_extent)
        require(
            all(
                extent[i] > 0
                and bounds["origin"][i] - bounds["extent"][i] <= origin[i] - extent[i]
                and origin[i] + extent[i] <= bounds["origin"][i] + bounds["extent"][i]
                for i in range(3)
            ),
            "Derived mesh escapes source witness bounds",
        )
        low = bounds["origin"][2] - bounds["extent"][2] - 100
        high = bounds["origin"][2] + bounds["extent"][2] + 100

        def mesh_hit(x, y, start_z, end_z):
            result = component.line_trace_component(
                unreal.Vector(x, y, start_z),
                unreal.Vector(x, y, end_z),
                True,
                False,
                False,
            )
            if result is None:
                return None
            require(isinstance(result, tuple), "Unexpected mesh trace result")
            hits = [v for v in result if isinstance(v, unreal.HitResult)]
            require(len(hits) == 1, "Ambiguous component hit result")
            row = unpack(hits[0], actor, component, require_blocking=False)
            require(
                low <= row["position_cm"][2] <= high
                and row["distance_cm"] <= high - low,
                "Mesh hit outside ray",
            )
            return row

        point = request["points"][3]
        center_x, center_y = point["world_xy_cm"]
        ignored = [a for a in subsystem.get_all_level_actors() if a != ground]
        rows, misses = [], 0
        for iy in range(33):
            for ix in range(33):
                x = bounds["origin"][0] + bounds["extent"][0] * (2 * ix / 32 - 1)
                y = bounds["origin"][1] + bounds["extent"][1] * (2 * iy / 32 - 1)
                bottom, top = mesh_hit(x, y, low, high), mesh_hit(x, y, high, low)
                require((bottom is None) == (top is None), "Unpaired mesh interval")
                if bottom is None:
                    misses += 1
                    continue
                world_x, world_y = center_x + x, center_y + y
                hit = unreal.SystemLibrary.line_trace_single(
                    world,
                    unreal.Vector(world_x, world_y, 150000),
                    unreal.Vector(world_x, world_y, -150000),
                    unreal.TraceTypeQuery.ECC_VISIBILITY,
                    True,
                    ignored,
                    unreal.DrawDebugTrace.NONE,
                    True,
                )
                native = unpack(hit, ground)
                require(
                    native is not None
                    and native["component_class"]
                    == "LandscapeHeightfieldCollisionComponent",
                    "Ground contact missing/wrong owner",
                )
                control = unreal.SystemLibrary.line_trace_single(
                    world,
                    unreal.Vector(world_x, world_y, 150000),
                    unreal.Vector(world_x, world_y, -150000),
                    unreal.TraceTypeQuery.ECC_VISIBILITY,
                    True,
                    subsystem.get_all_level_actors(),
                    unreal.DrawDebugTrace.NONE,
                    True,
                )
                require(control is None, "Ground exclusion control remained blocked")
                rows.append(
                    {
                        "local_xy_cm": [x, y],
                        "world_xy_cm": [world_x, world_y],
                        "bottom_z_cm": bottom["position_cm"][2],
                        "top_z_cm": top["position_cm"][2],
                        "ground_z_cm": native["position_cm"][2],
                        "bottom": bottom,
                        "top": top,
                        "ground": native,
                    }
                )
        fit = solve_support(rows)
        for row, fitted in zip(rows, fit["samples"]):
            row["fit"] = fitted
        root_z = fit["root_zero_sampled_air_cm"]
        actor.set_actor_location(
            unreal.Vector(center_x, center_y, root_z), False, False
        )
        require(
            vector(actor.get_actor_location())
            == [float(center_x), float(center_y), root_z],
            "Diagnostic actor location readback differs",
        )
        actor_origin, actor_extent = actor.get_actor_bounds(False)
        target = [center_x, center_y, root_z + origin[2]]
        receipt = {
            "status": "TRANSIENT_SAMPLED_BOULDER_SETTLE_RENDER_PENDING",
            "placement": False,
            "qualified_assets": [],
            "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
            "scene_saved": False,
            "assets_saved": False,
            "terrain_mutation_requested": False,
            "map_package": sources["terrain"]["map_package"],
            "source_contract": sources["terrain"],
            "ground_owner": ground.get_path_name(),
            "ground_transform": {
                "location_cm": vector(transform.translation),
                "scale": vector(transform.scale3d),
            },
            "candidate_id": point["candidate_id"],
            "world_xy_cm": point["world_xy_cm"],
            "material_readback": material.verify_binding(binding, component),
            "source_bounds_cm": bounds,
            "derived_bounds_cm": {"origin": origin, "extent": extent},
            "grid": {
                "size": [33, 33],
                "ray_count": 1089,
                "paired_misses": misses,
                "interval_count": len(rows),
                "domain": "conservative source AABB including boundary",
            },
            "orientation": "identity",
            "uniform_scale": 1,
            "fit": fit,
            "support_rows": rows,
            "before_location_cm": [center_x, center_y, fit["root_nonpenetrating_cm"]],
            "after_location_cm": [center_x, center_y, root_z],
            "actor_bounds_cm": {
                "origin": vector(actor_origin),
                "extent": vector(actor_extent),
            },
            "camera_target_cm": target,
            "contact_limits": "REQUIRED_UNSET",
            "continuous_support_verified": False,
            "datum_independently_verified": False,
            "latest_road_consumer_contact": "NOT_RUN",
            "visual_acceptance": "NOT_VERIFIED",
            "performance_pass": False,
            "limitations": "Finite vertical collision intervals, not render-triangle or silhouette closure; concavity/multiple crossings unverified; embedding is diagnostic, not an accepted policy",
        }
        return receipt, world, actor, target
    except Exception:
        subsystem.destroy_actor(actor)
        raise
