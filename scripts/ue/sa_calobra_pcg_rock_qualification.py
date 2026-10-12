"""Two isolated FBX imports and bounded sampled Landscape contact; no admission."""

import hashlib
import json
import math
from pathlib import Path
import re

import unreal

from scripts.assets.pcg_boulder_support import solve_support
from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue.sa_calobra_pcg_terrain_contact import require, unpack, vector


DESTINATION = "/Game/Generated/YACS/PCG365Rocks"


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def write_raw(output, name, value):
    path = output / name
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, allow_nan=False, separators=(",", ":"))
    return {"path": name, **identity(path)}


def source_path(root, row):
    relative = row["source_relative"]
    require(
        isinstance(relative, str)
        and re.fullmatch(r"rock-source/[A-Za-z0-9_-]+\.fbx", relative),
        "Unsafe rock source path",
    )
    path = (root / relative).resolve(strict=True)
    require(path.is_relative_to(root / "rock-source"), "Rock source escaped staging")
    require(
        type(row["bytes"]) is int
        and row["bytes"] > 0
        and isinstance(row["sha256"], str)
        and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
        "Invalid rock source identity",
    )
    require(
        identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
        "Rock source bytes drift",
    )
    return path


def import_mesh(root, row, instance):
    path = source_path(root, row)
    name = "SM_" + row["id"] + "_ForgeDiagnostic"
    package = DESTINATION + "/" + name
    require(
        not unreal.EditorAssetLibrary.does_asset_exist(package),
        "Preserve existing rock import",
    )
    options = unreal.FbxImportUI()
    for key, value in {
        "import_mesh": True,
        "import_as_skeletal": False,
        "import_materials": False,
        "import_textures": False,
        "automated_import_should_detect_type": False,
        "mesh_type_to_import": unreal.FBXImportType.FBXIT_STATIC_MESH,
    }.items():
        options.set_editor_property(key, value)
    data = options.get_editor_property("static_mesh_import_data")
    settings = {
        "combine_meshes": True,
        "convert_scene": True,
        "convert_scene_unit": True,
        "import_uniform_scale": 1.0,
        "import_translation": unreal.Vector(),
        "import_rotation": unreal.Rotator(),
        "transform_vertex_to_absolute": True,
        "bake_pivot_in_vertex": False,
        "build_nanite": False,
        "auto_generate_collision": False,
    }
    for key, value in settings.items():
        data.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    for key, value in {
        "filename": str(path),
        "destination_path": DESTINATION,
        "destination_name": name,
        "automated": True,
        "replace_existing": False,
        "save": False,
        "options": options,
    }.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths") or [])
    require(
        len(imported) == 1 and str(imported[0]).split(".")[0] == package,
        "Unexpected rock imported object inventory",
    )
    mesh = unreal.load_asset(package)
    require(isinstance(mesh, unreal.StaticMesh), "Rock import is not StaticMesh")
    require(len(mesh.static_materials) > 0, "Rock has no material slots")
    for index in range(len(mesh.static_materials)):
        mesh.set_material(index, instance)
        require(
            mesh.get_material(index) == instance, "Rock Forge material binding differs"
        )
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False),
        "Rock mesh save failed",
    )
    bounds = mesh.get_bounds()
    origin, extent = vector(bounds.origin), vector(bounds.box_extent)
    require(all(v > 0 for v in extent), "Degenerate imported rock bounds")
    if "expected_source_dimensions_cm" in row:
        expected = row["expected_source_dimensions_cm"]
        require(
            len(expected) == 3
            and all(
                type(v) in (int, float) and math.isfinite(v) and v > 0 for v in expected
            ),
            "Invalid source dimension witness",
        )
        actual_dimensions = [2 * v for v in extent]
        # FBX/UE axis conversion can swap/reflection-map horizontal axes. This
        # witnesses dimensions/units only; it does not infer support orientation.
        require(
            all(
                abs(a - b) <= 0.01
                for a, b in zip(sorted(actual_dimensions[:2]), sorted(expected[:2]))
            )
            and abs(actual_dimensions[2] - expected[2]) <= 0.01,
            "Native dimensions differ from source unit witness",
        )
    if "support_patch" in row:
        expected_bounds = row["expected_native_bounds_cm"]
        require(
            all(
                abs(actual - expected) <= 0.01
                for actual, expected in zip(
                    [origin[i] - extent[i] for i in range(3)]
                    + [origin[i] + extent[i] for i in range(3)],
                    expected_bounds["min"] + expected_bounds["max"],
                )
            ),
            "Declared patch/native source coordinate witness differs",
        )
    triangles = mesh.get_num_triangles(0)
    require(triangles > 0, "Rock has no render LOD0 triangles")
    if "expected_lod0_triangles" in row:
        require(
            triangles == row["expected_lod0_triangles"],
            "Imported triangle count differs from selected source mesh",
        )
    import_data = mesh.get_editor_property("asset_import_data")
    complexity = unreal.get_editor_subsystem(
        unreal.StaticMeshEditorSubsystem
    ).get_collision_complexity(mesh)
    receipt = {
        "id": row["id"],
        "source": row,
        "package": package,
        "saved_package": material.file_identity(package),
        "slot_count": len(mesh.static_materials),
        "material": instance.get_path_name(),
        "bounds_cm": {"origin": origin, "extent": extent},
        "lod0_render_triangles": triangles,
        "collision_complexity": str(complexity),
        "import_data_class": import_data.get_class().get_name()
        if import_data
        else None,
        "requested_import_options": {
            k: (
                vector(v)
                if isinstance(v, unreal.Vector)
                else [v.pitch, v.yaw, v.roll]
                if isinstance(v, unreal.Rotator)
                else v
            )
            for k, v in settings.items()
        },
        "effective_legacy_import_options": None,
        "unit_and_pivot_qualification": "NATIVE_BOUNDS_RECORDED_NOT_SOURCE_UNIT_AUTHORITY",
    }
    if isinstance(import_data, unreal.FbxStaticMeshImportData):
        receipt["effective_legacy_import_options"] = {
            key: import_data.get_editor_property(key)
            for key in (
                "convert_scene",
                "convert_scene_unit",
                "import_uniform_scale",
                "transform_vertex_to_absolute",
                "bake_pivot_in_vertex",
                "build_nanite",
            )
        }
        require(
            receipt["effective_legacy_import_options"]["convert_scene_unit"] is True
            and receipt["effective_legacy_import_options"]["import_uniform_scale"]
            == 1.0,
            "Effective FBX unit settings differ",
        )
    source_path(root, row)
    return mesh, receipt


def measure_grid(component, actor, bounds, size, world, ground, ignored, center):
    origin, extent = bounds["origin"], bounds["extent"]
    low, high = origin[2] - extent[2] - 100.0, origin[2] + extent[2] + 100.0
    rows, paired_misses, unpaired, missing_ground, max_slope = [], 0, 0, 0, 0.0
    rejected_rows = []
    footprint_count = 0

    def mesh_hit(x, y, z0, z1):
        result = component.line_trace_component(
            unreal.Vector(x, y, z0), unreal.Vector(x, y, z1), True, False, False
        )
        if result is None:
            return None
        require(isinstance(result, tuple), "Unexpected component ray result")
        hits = [item for item in result if isinstance(item, unreal.HitResult)]
        require(len(hits) == 1, "Ambiguous complex component ray")
        hit = unpack(hits[0], actor, component, require_blocking=False)
        require(
            low <= hit["position_cm"][2] <= high and hit["distance_cm"] <= high - low,
            "Complex hit outside bounded ray",
        )
        return hit

    for iy in range(size):
        for ix in range(size):
            x = origin[0] + extent[0] * (2 * ix / (size - 1) - 1)
            y = origin[1] + extent[1] * (2 * iy / (size - 1) - 1)
            bottom, top = mesh_hit(x, y, low, high), mesh_hit(x, y, high, low)
            if bottom is None and top is None:
                paired_misses += 1
                rejected_rows.append(
                    {"local_xy_cm": [x, y], "status": "PAIRED_MESH_MISS"}
                )
                continue
            footprint_count += 1
            if bottom is None or top is None:
                unpaired += 1
                rejected_rows.append(
                    {
                        "local_xy_cm": [x, y],
                        "status": "UNPAIRED_MESH_HIT",
                        "bottom": bottom,
                        "top": top,
                    }
                )
                continue
            wx, wy = center[0] + x, center[1] + y
            raw = unreal.SystemLibrary.line_trace_single(
                world,
                unreal.Vector(wx, wy, 150000),
                unreal.Vector(wx, wy, -150000),
                unreal.TraceTypeQuery.ECC_VISIBILITY,
                True,
                ignored,
                unreal.DrawDebugTrace.NONE,
                True,
            )
            native = unpack(raw, ground)
            if native is None:
                missing_ground += 1
                rejected_rows.append(
                    {
                        "local_xy_cm": [x, y],
                        "world_xy_cm": [wx, wy],
                        "status": "MISSING_GROUND",
                        "bottom": bottom,
                        "top": top,
                    }
                )
                continue
            require(
                native["component_class"] == "LandscapeHeightfieldCollisionComponent",
                "Wrong ground component class",
            )
            normal = native["normal"]
            require(all(math.isfinite(v) for v in normal), "Nonfinite ground normal")
            normal_length = math.sqrt(sum(v * v for v in normal))
            require(normal_length > 0, "Zero ground normal")
            slope = math.degrees(
                math.acos(max(-1.0, min(1.0, normal[2] / normal_length)))
            )
            max_slope = max(max_slope, slope)
            rows.append(
                {
                    "local_xy_cm": [x, y],
                    "world_xy_cm": [wx, wy],
                    "bottom_z_cm": bottom["position_cm"][2],
                    "top_z_cm": top["position_cm"][2],
                    "ground_z_cm": native["position_cm"][2],
                    "ground_normal": native["normal"],
                    "ground_slope_deg": slope,
                }
            )
    fit, fit_error = None, None
    if rows:
        try:
            fit = solve_support(rows)
            fit["max_positive_bottom_gap_cm"] = max(
                0.0, max(p["bottom_gap_cm"] for p in fit["samples"])
            )
            for row, fitted in zip(rows, fit.pop("samples")):
                row["fit"] = fitted
        except ValueError as exc:
            fit_error = str(exc)
    return {
        "grid_size": size,
        "sample_count": footprint_count,
        "valid_ground_count": len(rows),
        "paired_misses": paired_misses,
        "unpaired_mesh_hits": unpaired,
        "missing_ground_count": missing_ground,
        "max_local_slope_deg": max_slope,
        "fit": fit,
        "fit_error": fit_error,
        "rows": rows,
        "rejected_rows": rejected_rows,
    }


def source_patch_diagnostic(grid, mesh_receipt, refinement=None):
    """Separate source-cap experiment; never reinterpret the V1/V2 decision."""
    from scripts.assets.pcg_rock_patch_diagnostic import diagnose, inside

    source = mesh_receipt["source"]
    declaration = dict(source["support_patch"])
    require(
        declaration["source_sha256"] == source["sha256"]
        and declaration["basecut_source_sha256"] == source["original_source_sha256"],
        "Patch/source identity differs",
    )
    bounds = mesh_receipt["bounds_cm"]
    size = grid["grid_size"]
    origin, extent = bounds["origin"], bounds["extent"]
    declaration.update(
        height_cm=2 * extent[2],
        expected_full_ray_count=grid["sample_count"],
        expected_cap_ray_count=sum(
            inside(
                [
                    origin[0] + extent[0] * (2 * ix / (size - 1) - 1),
                    origin[1] + extent[1] * (2 * iy / (size - 1) - 1),
                ],
                declaration["cap_xy_polygon"],
            )
            for iy in range(size)
            for ix in range(size)
        ),
    )
    result = diagnose(grid["rows"], declaration, refinement)
    result.pop("samples", None)
    result["declaration"] = declaration
    result["native_unpaired_mesh_hits"] = grid["unpaired_mesh_hits"]
    if grid["unpaired_mesh_hits"]:
        result["status"] = "REJECTED_DIAGNOSTIC"
        result["reasons"].append("UNPAIRED_NATIVE_MESH_RAYS")
    return result


def run(root, output, head, binding):
    from scripts.assets.pcg_rock_contact_policy import (
        evaluate,
        refined_trial_policy,
        trial_policy,
    )

    root, output = Path(root).resolve(), Path(output).resolve()
    require(
        root == material.project_root() and output.is_relative_to(root),
        "Wrong owned diagnostic root",
    )
    require(re.fullmatch("[0-9a-f]{40}", head), "Exact code HEAD required")
    request = json.loads(
        (root / "rock-qualification-request.json").read_text(encoding="utf-8")
    )
    request_before = identity(root / "rock-qualification-request.json")
    require(
        type(request["schema_version"]) is int
        and request["schema_version"] == 1
        and request["scope"] == "ISOLATED_ROCK_QUALIFICATION_ONLY",
        "Wrong rock qualification scope",
    )
    require(
        request.get("placement") is False and request.get("qualified_assets") == [],
        "Rock request must remain unqualified",
    )
    assets = request["assets"]
    require(
        isinstance(assets, list) and len(assets) == 2,
        "Exactly two new rock sources required",
    )
    require(
        all(
            isinstance(row["id"], str)
            and re.fullmatch("[A-Za-z][A-Za-z0-9_]{0,63}", row["id"])
            for row in assets
        )
        and len({row["id"] for row in assets}) == 2
        and len({row["source_relative"] for row in assets}) == 2,
        "Invalid or duplicate rock sources",
    )
    for row in assets:
        source_path(root, row)
    contact = json.loads((root / "contact-request.json").read_text(encoding="utf-8"))
    points = request.get("points", contact["points"])
    require(
        contact["placement"] is False
        and isinstance(points, list)
        and len(points) == 5
        and points == contact["points"],
        "Exactly five authenticated contact diagnostic points required",
    )
    for point in points:
        require(
            len(point["world_xy_cm"]) == 2
            and all(
                type(v) in (int, float) and math.isfinite(v)
                for v in point["world_xy_cm"]
            ),
            "Invalid contact XY",
        )
    instance = unreal.load_asset(binding["forge_import"]["assets"]["instance"])
    require(
        isinstance(instance, unreal.MaterialInstanceConstant), "Missing shared Forge MI"
    )
    readback = material.material_readback(binding["forge_import"]["assets"])
    policy = trial_policy()
    if "policy" in request:
        require(request["policy"] == policy, "Staged policy differs from frozen trial")
    imported = [import_mesh(root, row, instance) for row in assets]
    sources = json.loads(
        (root / "qualification-sources.json").read_text(encoding="utf-8")
    )
    require(
        unreal.EditorLoadingAndSavingUtils.load_map(sources["terrain"]["map_package"]),
        "Pinned Landscape load failed",
    )
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(
        world.get_path_name().split(".")[0] == sources["terrain"]["map_package"],
        "Wrong terrain map",
    )
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        a
        for a in subsystem.get_all_level_actors()
        if isinstance(a, unreal.LandscapeProxy)
    ]
    require(len(landscapes) == 1, "Ambiguous Landscape ownership")
    ground = landscapes[0]
    ground_before = ground.get_actor_transform()
    require(
        vector(ground_before.scale3d)[:2] == [50.0, 50.0]
        and [
            ground_before.rotation.rotator().pitch,
            ground_before.rotation.rotator().yaw,
            ground_before.rotation.rotator().roll,
        ]
        == [0.0, 0.0, 0.0],
        "Unadmitted Landscape transform",
    )
    report = {
        "schema_version": 1,
        "code_sha": head,
        "status": "ROCK_CONTACT_MATRIX_MEASURED",
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "native_build": "NOT_RUN_PREBUILT_DEPENDENCY",
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        "material_readback": readback,
        "policy": policy,
        "meshes": [],
        "cases": [],
        "source_contract": sources["terrain"],
        "map_saved": False,
        "terrain_modified": False,
        "limitations": "Finite vertical collision samples; continuous/render geometry and protected material inputs unverified",
    }
    for mesh, mesh_receipt in imported:
        report["meshes"].append(mesh_receipt)
        actor = subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(), transient=True
        )
        require(actor is not None, "Rock diagnostic actor creation failed")
        try:
            component = actor.static_mesh_component
            actor.set_actor_rotation(unreal.Rotator(), False)
            actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
            component.set_static_mesh(mesh)
            require(
                all(
                    component.get_material(i) == instance
                    for i in range(len(mesh.static_materials))
                ),
                "Effective rock component Forge slots differ",
            )
            component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
            component.set_collision_response_to_all_channels(
                unreal.CollisionResponseType.ECR_BLOCK
            )
            require(
                vector(actor.get_actor_location()) == [0.0, 0.0, 0.0]
                and vector(actor.get_actor_scale3d()) == [1.0, 1.0, 1.0],
                "Rock measurement transform differs",
            )
            rotation = actor.get_actor_rotation()
            require(
                [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
                "Rock measurement rotation differs",
            )
            ignored = [a for a in subsystem.get_all_level_actors() if a != ground]
            for index, point in enumerate(points):
                center = point["world_xy_cm"]
                case = {
                    "mesh_id": mesh_receipt["id"],
                    "point_index": index,
                    "candidate_id": point["candidate_id"],
                    "world_xy_cm": center,
                }
                grids = [
                    measure_grid(
                        component,
                        actor,
                        mesh_receipt["bounds_cm"],
                        size,
                        world,
                        ground,
                        ignored,
                        center,
                    )
                    for size in (33, 65)
                ]
                control = unreal.SystemLibrary.line_trace_single(
                    world,
                    unreal.Vector(*center, 150000),
                    unreal.Vector(*center, -150000),
                    unreal.TraceTypeQuery.ECC_VISIBILITY,
                    True,
                    subsystem.get_all_level_actors(),
                    unreal.DrawDebugTrace.NONE,
                    True,
                )
                require(control is None, "Ground exclusion negative control failed")
                case["ground_exclusion_control"] = "PASS"
                if "support_patch" in mesh_receipt["source"]:
                    coarse_patch, fine_patch = [
                        source_patch_diagnostic(g, mesh_receipt) for g in grids
                    ]
                    if "fit" in coarse_patch and "fit" in fine_patch:
                        refinement = {
                            "root_delta_cm": abs(
                                coarse_patch["fit"]["root_zero_sampled_air_cm"]
                                - fine_patch["fit"]["root_zero_sampled_air_cm"]
                            ),
                            "embedding_delta_cm": abs(
                                coarse_patch["fit"]["required_embedding_cm"]
                                - fine_patch["fit"]["required_embedding_cm"]
                            ),
                        }
                        fine_patch = source_patch_diagnostic(
                            grids[1], mesh_receipt, refinement
                        )
                        fine_patch["refinement"] = refinement
                    case["source_patch_diagnostic"] = {
                        "coarse": coarse_patch,
                        "fine": fine_patch,
                        "coarse_grid": 33,
                        "fine_grid": 65,
                        "full_qualification": False,
                        "placement": False,
                    }
                    if (
                        fine_patch.get("reasons") == ["SAMPLE_REFINEMENT_NOT_CONVERGED"]
                        and request.get("source_patch_refinement_grid") == 129
                    ):
                        patch_refined = measure_grid(
                            component,
                            actor,
                            mesh_receipt["bounds_cm"],
                            129,
                            world,
                            ground,
                            ignored,
                            center,
                        )
                        patch_initial = source_patch_diagnostic(
                            patch_refined, mesh_receipt
                        )
                        if "fit" in patch_initial:
                            patch_delta = {
                                "root_delta_cm": abs(
                                    fine_patch["fit"]["root_zero_sampled_air_cm"]
                                    - patch_initial["fit"]["root_zero_sampled_air_cm"]
                                ),
                                "embedding_delta_cm": abs(
                                    fine_patch["fit"]["required_embedding_cm"]
                                    - patch_initial["fit"]["required_embedding_cm"]
                                ),
                            }
                            patch_final = source_patch_diagnostic(
                                patch_refined, mesh_receipt, patch_delta
                            )
                            patch_final["refinement"] = patch_delta
                            case["source_patch_diagnostic"].update(
                                initial_coarse=coarse_patch,
                                initial_fine=fine_patch,
                                coarse=fine_patch,
                                fine=patch_final,
                                coarse_grid=65,
                                fine_grid=129,
                            )
                        patch_refined["raw_samples"] = write_raw(
                            output,
                            "%s-point%d-patch-grid129.json"
                            % (mesh_receipt["id"], index),
                            {
                                "support_rows": patch_refined.pop("rows"),
                                "rejected_rows": patch_refined.pop("rejected_rows"),
                            },
                        )
                        case["source_patch_refined_grid"] = patch_refined
                for grid in grids:
                    grid["raw_samples"] = write_raw(
                        output,
                        "%s-point%d-grid%d.json"
                        % (mesh_receipt["id"], index, grid["grid_size"]),
                        {
                            "support_rows": grid.pop("rows"),
                            "rejected_rows": grid.pop("rejected_rows"),
                        },
                    )
                coarse, fine = grids
                case["grids"] = grids
                complete = all(
                    g["sample_count"] > 0
                    and g["valid_ground_count"] == g["sample_count"]
                    and not g["unpaired_mesh_hits"]
                    and g["fit"]
                    for g in grids
                )
                if complete:
                    measurement = {
                        "height_cm": mesh_receipt["bounds_cm"]["extent"][2] * 2,
                        "uniform_scale": 1.0,
                        "yaw_deg": 0.0,
                        "tilt_deg": 0.0,
                        "max_local_slope_deg": fine["max_local_slope_deg"],
                        "ground_class": "LandscapeHeightfieldCollisionComponent",
                        "sample_count": fine["sample_count"],
                        "valid_ground_count": fine["valid_ground_count"],
                        "coverage_status": "COMPLETE_SAMPLED_MESH_FOOTPRINT",
                        "fit": fine["fit"],
                        "refinement": {
                            "coarse_grid": 33,
                            "fine_grid": 65,
                            "coarse_root_cm": coarse["fit"]["root_zero_sampled_air_cm"],
                            "fine_root_cm": fine["fit"]["root_zero_sampled_air_cm"],
                            "coarse_embedding_cm": coarse["fit"][
                                "required_embedding_cm"
                            ],
                            "fine_embedding_cm": fine["fit"]["required_embedding_cm"],
                        },
                    }
                    case["measurement"] = measurement
                    case["policy_decision"] = evaluate(measurement, policy)
                    reasons = case["policy_decision"]["reasons"]
                    if (
                        reasons
                        and set(reasons)
                        <= {"ROOT_NOT_CONVERGED", "EMBEDDING_NOT_CONVERGED"}
                        and request.get("refinement_policy_id")
                        == refined_trial_policy()["policy_id"]
                    ):
                        # Preserve the failed coarse decision. Refinement changes
                        # sampling resolution, never physical or convergence limits.
                        case["initial_measurement"] = measurement
                        case["initial_policy_decision"] = case["policy_decision"]
                        refined = measure_grid(
                            component,
                            actor,
                            mesh_receipt["bounds_cm"],
                            129,
                            world,
                            ground,
                            ignored,
                            center,
                        )
                        refined["raw_samples"] = write_raw(
                            output,
                            "%s-point%d-grid129.json" % (mesh_receipt["id"], index),
                            {
                                "support_rows": refined.pop("rows"),
                                "rejected_rows": refined.pop("rejected_rows"),
                            },
                        )
                        case["grids"].append(refined)
                        if (
                            refined["fit"]
                            and refined["valid_ground_count"] == refined["sample_count"]
                            and not refined["unpaired_mesh_hits"]
                        ):
                            measurement = {
                                **measurement,
                                "max_local_slope_deg": refined["max_local_slope_deg"],
                                "sample_count": refined["sample_count"],
                                "valid_ground_count": refined["valid_ground_count"],
                                "fit": refined["fit"],
                                "refinement": {
                                    "coarse_grid": 65,
                                    "fine_grid": 129,
                                    "coarse_root_cm": fine["fit"][
                                        "root_zero_sampled_air_cm"
                                    ],
                                    "fine_root_cm": refined["fit"][
                                        "root_zero_sampled_air_cm"
                                    ],
                                    "coarse_embedding_cm": fine["fit"][
                                        "required_embedding_cm"
                                    ],
                                    "fine_embedding_cm": refined["fit"][
                                        "required_embedding_cm"
                                    ],
                                },
                            }
                            case["measurement"] = measurement
                            case["policy_decision"] = evaluate(
                                measurement, refined_trial_policy()
                            )
                        else:
                            case["policy_decision"] = {
                                "status": "REJECTED",
                                "reasons": ["INCOMPLETE_REFINED_GROUND_OR_SUPPORT"],
                                "full_qualification": False,
                            }
                    case["status"] = "MEASURED"
                else:
                    case.update(
                        status="REJECTED",
                        reason="INCOMPLETE_GROUND_OR_MESH_SUPPORT",
                        policy_decision={
                            "status": "REJECTED",
                            "full_qualification": False,
                        },
                    )
                report["cases"].append(case)
        finally:
            require(
                subsystem.destroy_actor(actor), "Rock diagnostic actor cleanup failed"
            )
    after = ground.get_actor_transform()
    require(
        vector(after.translation) == vector(ground_before.translation)
        and vector(after.scale3d) == vector(ground_before.scale3d)
        and after.rotation == ground_before.rotation,
        "Landscape transform changed",
    )
    for row in assets:
        source_path(root, row)
    for _, saved in imported:
        require(
            material.file_identity(saved["package"]) == saved["saved_package"],
            "Saved rock package changed during measurement",
        )
    report["saved_packages"] = [saved["saved_package"] for _, saved in imported]
    require(
        identity(root / "rock-qualification-request.json") == request_before,
        "Rock request changed during measurement",
    )
    write_raw(
        output,
        "mesh-inventory.json",
        {
            "code_sha": head,
            "meshes": report["meshes"],
            "request_sha256": identity(root / "rock-qualification-request.json")[
                "sha256"
            ],
            "saved_packages": report["saved_packages"],
        },
    )
    return report


def reload(root, output, head, binding):
    """Fresh process readback only; no import, repair, save or contact rerun."""
    root, output = Path(root).resolve(), Path(output).resolve()
    require(
        root == material.project_root() and output.is_relative_to(root),
        "Wrong owned diagnostic root",
    )
    require(re.fullmatch("[0-9a-f]{40}", head), "Exact code HEAD required")
    inventory = json.loads(
        (root / "proof/rock-qualify/mesh-inventory.json").read_text(encoding="utf-8")
    )
    require(
        inventory["code_sha"] == head
        and inventory["request_sha256"]
        == identity(root / "rock-qualification-request.json")["sha256"],
        "Fresh rock request/HEAD differs",
    )
    request = json.loads(
        (root / "rock-qualification-request.json").read_text(encoding="utf-8")
    )
    meshes = inventory["meshes"]
    require(
        len(meshes) == 2
        and len({row["package"] for row in meshes}) == 2
        and len({row["id"] for row in meshes}) == 2,
        "Unexpected fresh rock inventory",
    )
    require(
        [row["source"] for row in meshes] == request["assets"],
        "Saved rock source inventory differs",
    )
    instance = unreal.load_asset(binding["forge_import"]["assets"]["instance"])
    require(
        isinstance(instance, unreal.MaterialInstanceConstant), "Missing shared Forge MI"
    )
    material_readback = material.material_readback(binding["forge_import"]["assets"])
    for row in meshes:
        source_path(root, row["source"])
        require(
            row["package"] == DESTINATION + "/SM_" + row["id"] + "_ForgeDiagnostic",
            "Unexpected fresh rock package",
        )
        require(
            material.file_identity(row["package"]) == row["saved_package"],
            "Fresh saved rock bytes differ",
        )
        mesh = unreal.load_asset(row["package"])
        require(
            isinstance(mesh, unreal.StaticMesh)
            and mesh.get_path_name().split(".")[0] == row["package"],
            "Fresh native rock identity differs",
        )
        bounds = mesh.get_bounds()
        require(
            {"origin": vector(bounds.origin), "extent": vector(bounds.box_extent)}
            == row["bounds_cm"]
            and mesh.get_num_triangles(0) == row["lod0_render_triangles"],
            "Fresh rock geometry readback differs",
        )
        require(
            len(mesh.static_materials) == row["slot_count"]
            and all(
                mesh.get_material(index) == instance
                for index in range(row["slot_count"])
            ),
            "Fresh rock Forge slots differ",
        )
        complexity = unreal.get_editor_subsystem(
            unreal.StaticMeshEditorSubsystem
        ).get_collision_complexity(mesh)
        require(
            str(complexity) == row["collision_complexity"],
            "Fresh rock collision complexity differs",
        )
        import_data = mesh.get_editor_property("asset_import_data")
        require(
            (import_data.get_class().get_name() if import_data else None)
            == row["import_data_class"],
            "Fresh rock import data class differs",
        )
        if row["effective_legacy_import_options"] is not None:
            require(
                isinstance(import_data, unreal.FbxStaticMeshImportData),
                "Fresh legacy FBX import data missing",
            )
            require(
                {
                    key: import_data.get_editor_property(key)
                    for key in row["effective_legacy_import_options"]
                }
                == row["effective_legacy_import_options"],
                "Fresh effective FBX settings differ",
            )
        require(
            material.file_identity(row["package"]) == row["saved_package"],
            "Fresh readback changed saved rock bytes",
        )
    saved = [row["saved_package"] for row in meshes]
    require(saved == inventory["saved_packages"], "Saved package registry differs")
    return {
        "schema_version": 1,
        "code_sha": head,
        "status": "ROCK_MESHES_FRESH_READBACK",
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        "native_build": "NOT_RUN_PREBUILT_DEPENDENCY",
        "saved_packages": saved,
        "meshes": meshes,
        "material_readback": material_readback,
    }
