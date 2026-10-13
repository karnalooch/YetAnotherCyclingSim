"""Issue #365: authenticated, memory-only import and five-anchor diagnostic planting.

No regional selector, source save, terrain edit or production admission. Native
complex mesh/Landscape samples are remeasured at 65/129; frozen V2 limits apply.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import sys
import time

STAGE = Path("D:/yacs/work/pcg365/remote-rock-preview")
DESTINATION = "/Game/Generated/YACS/PCG365RemotePreview"
HELPERS = {
    "scripts/assets/pcg_rock_contact_policy.py": "4bfd12aca172a64940b49163bb0ecf221fac593e889028cdc8c88cd8a7b1bd5f",
    "scripts/assets/pcg_boulder_support.py": "2ee74a9c3349babf5b6d4c39f768215cacc0137b6ffb1f64046b83ee0798fee2",
}


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    need(
        type(value) in (int, float) and math.isfinite(value), "Nonfinite numeric input"
    )
    return float(value)


def vec(value):
    return [number(value.x), number(value.y), number(value.z)]


def file_proof(root, proof):
    need(
        type(proof) is dict and set(proof) == {"path", "sha256", "bytes"},
        "File proof schema differs",
    )
    name = proof["path"]
    need(
        type(name) is str
        and "\\" not in name
        and ":" not in name
        and all(p not in ("", ".", "..") for p in name.split("/")),
        "Unsafe relative proof path",
    )
    path = root / name
    cursor = path
    while cursor != root:
        need(not cursor.is_symlink(), "Aliased proof path")
        cursor = cursor.parent
    need(
        path.is_file() and path.resolve().is_relative_to(root.resolve()),
        "Missing bounded source",
    )
    need(
        type(proof["bytes"]) is int
        and 0 < proof["bytes"] <= 256 * 1024 * 1024
        and path.stat().st_size == proof["bytes"]
        and digest(path) == proof["sha256"],
        "Source byte identity differs",
    )
    return path


def read_manifest(expected_digest, *, require_plant=False):
    need(
        type(expected_digest) is str and re.fullmatch(r"[0-9a-f]{64}", expected_digest),
        "Exact manifest digest required",
    )
    path = STAGE / "preview-manifest.json"
    need(
        STAGE.is_dir()
        and not STAGE.is_symlink()
        and not path.is_symlink()
        and path.is_file()
        and 0 < path.stat().st_size <= 128 * 1024,
        "Missing bounded preview manifest",
    )
    need(digest(path) == expected_digest, "Preview manifest changed")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    need(
        set(data)
        == {
            "schema_version",
            "scope",
            "map_package",
            "anchor_source",
            "protected_packages",
            "assets",
            "placements",
            "exclusion_sources",
        },
        "Preview schema differs",
    )
    need(
        type(data["schema_version"]) is int
        and data["schema_version"] == 1
        and data["scope"] == "P0_P4_DIAGNOSTIC_ONLY",
        "Unapproved preview scope",
    )
    original = json.loads(
        file_proof(STAGE, data["anchor_source"]).read_text(encoding="utf-8-sig")
    )
    need(
        type(original.get("points")) is list and len(original["points"]) == 5,
        "Five original anchors required",
    )
    anchors = {
        "P" + str(i): row["world_xy_cm"] for i, row in enumerate(original["points"])
    }
    need(
        list(anchors.values())
        == [
            [16800, 70400],
            [4800, 96800],
            [184800, 180800],
            [181600, 189600],
            [91200, 200800],
        ],
        "Historical owner-approved anchor identities differ",
    )
    assets = data["assets"]
    need(
        type(assets) is list and 1 <= len(assets) <= 20,
        "Bounded imported asset set required",
    )
    ids = set()
    for asset in assets:
        need(
            set(asset)
            == {
                "id",
                "fbx",
                "bounds_cm",
                "material_package",
                "expected_lod0_triangles",
            },
            "Asset schema differs",
        )
        name = asset["id"]
        need(
            type(name) is str
            and re.fullmatch(r"[a-z][a-z0-9_]{2,63}", name)
            and name not in ids,
            "Invalid duplicate asset",
        )
        ids.add(name)
        need(
            type(asset["expected_lod0_triangles"]) is int
            and 0 < asset["expected_lod0_triangles"] <= 500000,
            "Invalid source triangle witness",
        )
        need(
            file_proof(STAGE, asset["fbx"]).suffix.lower() == ".fbx",
            "FBX source required",
        )
        bounds = asset["bounds_cm"]
        need(
            set(bounds) == {"origin", "extent"}
            and all(type(v) is list and len(v) == 3 for v in bounds.values()),
            "Invalid mesh bounds",
        )
        for v in bounds["origin"]:
            number(v)
        need(
            all(0 < number(v) <= 2000 for v in bounds["extent"]),
            "Mesh extent outside preview budget",
        )
    sources = data["exclusion_sources"]
    need(
        type(sources) is list and 1 <= len(sources) <= 16,
        "Authenticated exclusion sources required",
    )
    for proof in sources:
        file_proof(STAGE, proof)
    need(
        any(
            p["sha256"]
            == "465788e5d74cf3eccf59bdddc1480fa4d7dac50d6f22255ca69ac3b9f174b5df"
            for p in sources
        ),
        "Frozen World Authority manifest missing",
    )
    binding = hashlib.sha256(
        json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    placements = data["placements"]
    need(
        type(placements) is list
        and (1 if require_plant else 0) <= len(placements) <= 5,
        "At most five anchor placements",
    )
    sites = set()
    by_id = {a["id"]: a for a in assets}
    for row in placements:
        need(
            set(row) == {"site", "asset_id", "world_xy_cm", "exclusions"},
            "Placement schema differs",
        )
        site = row["site"]
        need(
            site in anchors and site not in sites and row["asset_id"] in by_id,
            "Unknown or duplicate anchor/asset",
        )
        sites.add(site)
        need(
            row["world_xy_cm"] == anchors[site] and len(row["world_xy_cm"]) == 2,
            "Placement moved from approved anchor",
        )
        for value in row["world_xy_cm"]:
            need(abs(number(value)) <= 250000, "Anchor outside bounded Landscape")
        e = row["exclusions"]
        need(
            set(e)
            == {
                "status",
                "road_source_compatible",
                "footprint_radius_cm",
                "unknown",
                "road",
                "nodata",
                "holdback",
                "aoi",
                "source_binding_sha256",
            },
            "Exclusion evidence schema differs",
        )
        bounds = by_id[row["asset_id"]]["bounds_cm"]
        radius = math.hypot(
            abs(bounds["origin"][0]) + bounds["extent"][0],
            abs(bounds["origin"][1]) + bounds["extent"][1],
        )
        need(
            e["status"] == "PASS_SOURCE_MASK_FOOTPRINT_CURRENT_ROAD_UNVERIFIED"
            and e["road_source_compatible"] is False
            and e["source_binding_sha256"] == binding
            and number(e["footprint_radius_cm"]) >= radius
            and all(
                e[k] is False for k in ("unknown", "road", "nodata", "holdback", "aoi")
            ),
            "Unknown/excluded/undersized footprint",
        )
    return data


def authenticated_exclusion_buffers(data):
    """Read lossless logical arrays authenticated by original raster manifest.

    These are original row-major ds.read().tobytes buffers, not resampled masks.
    Their exact SHA equals the pinned TIFF logical_sha256. Use stdlib only in UE.
    """
    sources = data["exclusion_sources"]
    masks = [
        p
        for p in sources
        if p["sha256"]
        == "465788e5d74cf3eccf59bdddc1480fa4d7dac50d6f22255ca69ac3b9f174b5df"
    ]
    need(len(masks) == 1, "Unique pinned mask manifest required")
    authority = json.loads(file_proof(STAGE, masks[0]).read_text(encoding="utf-8-sig"))
    need(
        authority.get("geometry_mutation") is False
        and authority.get("fingerprint")
        == "c9191f8dadf21d1820bebc80dd92e91641f4f4b74eb9d90342d7459611473864",
        "World Authority fingerprint or geometry boundary differs",
    )
    grid = authority["grid"]
    need(
        grid["width"] == grid["height"] == 4033
        and grid["crs"] == "EPSG:25831"
        and grid["transform"] == [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5]
        and sys.byteorder == "little",
        "Original logical mask grid/endian differs",
    )
    selected = []
    for stem, item_size in (
        ("exclusion-distance-lower-bound", 4),
        ("exclusion-reasons", 2),
    ):
        outputs = [r for r in authority["outputs"] if r["path"] == stem + ".tif"]
        tiffs = [r for r in sources if Path(r["path"]).name == stem + ".tif"]
        buffers = [r for r in sources if Path(r["path"]).name == stem + ".bin"]
        need(
            len(outputs) == len(tiffs) == len(buffers) == 1,
            "Original mask/buffer missing or ambiguous",
        )
        need(
            tiffs[0]["sha256"] == outputs[0]["sha256"]
            and tiffs[0]["bytes"] == outputs[0]["size_bytes"],
            "Exclusion TIFF differs from pinned authority",
        )
        file_proof(STAGE, tiffs[0])
        need(
            buffers[0]["sha256"] == outputs[0]["logical_sha256"]
            and buffers[0]["bytes"] == 4033 * 4033 * item_size,
            "Logical buffer differs from original authenticated raster",
        )
        selected.append(file_proof(STAGE, buffers[0]).read_bytes())
    return selected


def footprint_clearance_sample(xy, radius, distance_m, reasons):
    x, y = [number(v) for v in xy]
    radius = number(radius)
    need(
        radius > 0 and min(x + 25, y + 25, 201625 - x, 201625 - y) >= radius + 50,
        "Full footprint plus clearance escapes AOI",
    )
    col, row = math.floor(x / 50 + 0.5), math.floor(y / 50 + 0.5)
    need(
        0 <= row < 4033 and 0 <= col < 4033 and type(reasons) is int and reasons == 0,
        "Excluded or unknown source footprint",
    )
    distance = number(distance_m)
    lower_cm = max(0.0, distance * 100 - math.hypot(x - col * 50, y - row * 50))
    need(
        distance >= 0 and lower_cm >= radius + 50,
        "Insufficient full-footprint exclusion clearance",
    )
    return {
        "source_cell": [row, col],
        "radius_cm": radius,
        "clearance_cm": 50,
        "clearance_lower_bound_cm": lower_cm,
        "status": "PASS_AUTHENTICATED_FULL_RADIUS_EXCLUSIONS_ONLY",
        "regional_rock_domain_admitted": False,
    }


def verify_footprints(data, native_bounds=None):
    distances, reasons = authenticated_exclusion_buffers(data)
    by_id = {a["id"]: a for a in data["assets"]}
    results = {}
    for row in data["placements"]:
        x, y = row["world_xy_cm"]
        col, r = math.floor(x / 50 + 0.5), math.floor(y / 50 + 0.5)
        need(0 <= r < 4033 and 0 <= col < 4033, "Anchor outside exclusion grid")
        offset = r * 4033 + col
        distance = struct.unpack_from("<f", distances, offset * 4)[0]
        bits = struct.unpack_from("<H", reasons, offset * 2)[0]
        bounds = (native_bounds or {}).get(
            row["asset_id"], by_id[row["asset_id"]]["bounds_cm"]
        )
        radius = math.hypot(
            abs(bounds["origin"][0]) + bounds["extent"][0],
            abs(bounds["origin"][1]) + bounds["extent"][1],
        )
        results[row["site"]] = footprint_clearance_sample(
            [x, y], radius, distance, bits
        )
    return results


def load_helpers():
    # Resolve the actual installed protocol, never a user-controlled source path.
    from scripts.live_host import protocol

    root = Path(protocol.__file__).resolve().parents[2]
    modules = []
    for relative, expected in HELPERS.items():
        path = root / relative
        need(
            path.is_file() and not path.is_symlink() and digest(path) == expected,
            "Installed contact helper source differs",
        )
        spec = importlib.util.spec_from_file_location("_pcg365_" + path.stem, path)
        need(
            spec is not None and spec.loader is not None,
            "Contact helper loader missing",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def load_materials(unreal, context, data):
    project = Path(context["project"]).resolve()
    packages = data["protected_packages"]
    need(
        type(packages) is list and 1 <= len(packages) <= 24,
        "Exact Forge package closure required",
    )
    paths, known = [], set()
    for row in packages:
        need(
            set(row) == {"package", "path", "sha256", "bytes"},
            "Forge package schema differs",
        )
        package = row["package"]
        need(
            type(package) is str
            and package.startswith("/Game/Generated/YACS/")
            and package not in known
            and row["path"] == "Content/" + package[6:] + ".uasset",
            "Unowned Forge dependency path",
        )
        known.add(package)
        paths.append(
            str(file_proof(project, {k: row[k] for k in ("path", "sha256", "bytes")}))
        )
    unreal.AssetRegistryHelpers.get_asset_registry().scan_files_synchronous(
        paths, False
    )
    result = {}
    for asset in data["assets"]:
        package = asset["material_package"]
        need(package in known, "Unpinned Forge material")
        instance = unreal.load_asset(package)
        need(
            isinstance(instance, unreal.MaterialInstanceConstant),
            "Missing Forge material instance",
        )
        result[asset["id"]] = instance
    return result


def import_mesh(unreal, asset, material, destination):
    package = destination + "/SM_" + asset["id"]
    need(
        not unreal.EditorAssetLibrary.does_asset_exist(package),
        "Preserve existing mesh package; clear cannot delete packages",
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
    mesh_data = options.get_editor_property("static_mesh_import_data")
    for key, value in {
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
    }.items():
        mesh_data.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    for key, value in {
        "filename": str(file_proof(STAGE, asset["fbx"])),
        "destination_path": destination,
        "destination_name": "SM_" + asset["id"],
        "automated": True,
        "replace_existing": False,
        "save": False,
        "options": options,
    }.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths") or [])
    need(
        len(imported) == 1 and str(imported[0]).split(".")[0] == package,
        "Unexpected imported objects",
    )
    mesh = unreal.load_asset(package)
    need(isinstance(mesh, unreal.StaticMesh), "Import lacks native StaticMesh")
    need(
        mesh.get_num_triangles(0) == asset["expected_lod0_triangles"],
        "Imported LOD0 triangles differ",
    )
    actual = mesh.get_bounds()
    need(
        all(
            abs(a - b) <= 0.01
            for a, b in zip(
                vec(actual.origin) + vec(actual.box_extent),
                asset["bounds_cm"]["origin"] + asset["bounds_cm"]["extent"],
            )
        ),
        "Imported bounds differ",
    )
    need(len(mesh.static_materials) > 0, "Mesh lacks material slots")
    for i in range(len(mesh.static_materials)):
        mesh.set_material(i, material)
        need(mesh.get_material(i) == material, "Native Forge material binding differs")
    body = mesh.get_editor_property("body_setup")
    need(body is not None, "Mesh has no collision body")
    body.set_editor_property(
        "collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    )
    body.set_editor_property("double_sided_geometry", True)
    need(
        body.get_editor_property("collision_trace_flag")
        == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
        and body.get_editor_property("double_sided_geometry") is True,
        "Native complex collision settings differ",
    )
    return mesh


def unpack(hit, actor, component=None):
    if hit is None:
        return None
    values = hit.to_tuple()
    need(
        len(values) == 18
        and values[1] is False
        and values[9] == actor
        and (component is None or values[10] == component),
        "Wrong native contact owner/shape",
    )
    need(component is not None or values[0] is True, "Nonblocking Landscape hit")
    need(
        type(values[2]) in (int, float)
        and math.isfinite(values[2])
        and 0 <= values[2] <= 1
        and type(values[3]) in (int, float)
        and math.isfinite(values[3])
        and values[3] >= 0,
        "Invalid native hit time/distance",
    )
    return {
        "position": vec(values[5]),
        "normal": vec(values[7]),
        "component": values[10],
        "distance_cm": values[3],
    }


def trace_ground(unreal, world, xy, ignored):
    return unreal.SystemLibrary.line_trace_single(
        world,
        unreal.Vector(*xy, 150000),
        unreal.Vector(*xy, -150000),
        unreal.TraceTypeQuery.ECC_VISIBILITY,
        True,
        ignored,
        unreal.DrawDebugTrace.NONE,
        True,
    )


def measure_grid_steps(
    unreal, world, ground, ignored, actor, bounds, xy, size, support
):
    origin, extent = bounds["origin"], bounds["extent"]
    low, high = origin[2] - extent[2] - 100, origin[2] + extent[2] + 100
    component, rows, count, max_slope = actor.static_mesh_component, [], 0, 0.0

    def ray(x, y, z0, z1):
        result = component.line_trace_component(
            unreal.Vector(x, y, z0), unreal.Vector(x, y, z1), True, False, False
        )
        if result is None:
            return None
        need(isinstance(result, tuple), "Unexpected complex ray shape")
        hits = [v for v in result if isinstance(v, unreal.HitResult)]
        need(len(hits) == 1, "Ambiguous complex ray")
        hit = unpack(hits[0], actor, component)
        need(
            low <= hit["position"][2] <= high and hit["distance_cm"] <= high - low,
            "Complex hit outside source bounds",
        )
        return hit

    for iy in range(size):
        for ix in range(size):
            x, y = (
                origin[0] + extent[0] * (2 * ix / (size - 1) - 1),
                origin[1] + extent[1] * (2 * iy / (size - 1) - 1),
            )
            bottom, top = ray(x, y, low, high), ray(x, y, high, low)
            if bottom is None and top is None:
                yield {"grid": size}
                continue
            count += 1
            need(
                bottom is not None
                and top is not None
                and bottom["position"][2] <= top["position"][2],
                "Unpaired/inverted complex mesh rays",
            )
            hit = unpack(
                trace_ground(unreal, world, [xy[0] + x, xy[1] + y], ignored), ground
            )
            need(
                hit is not None
                and hit["component"].get_class().get_name()
                == "LandscapeHeightfieldCollisionComponent",
                "Missing authorized Landscape footprint",
            )
            normal = hit["normal"]
            length = math.sqrt(sum(v * v for v in normal))
            need(length > 0, "Zero ground normal")
            max_slope = max(
                max_slope,
                math.degrees(math.acos(max(-1.0, min(1.0, normal[2] / length)))),
            )
            rows.append(
                {
                    "bottom_z_cm": bottom["position"][2],
                    "top_z_cm": top["position"][2],
                    "ground_z_cm": hit["position"][2],
                }
            )
            yield {"grid": size}
    need(count > 0 and len(rows) == count, "Incomplete sampled footprint")
    fit = support.solve_support(rows)
    fit["max_positive_bottom_gap_cm"] = max(
        0.0, max(p["bottom_gap_cm"] for p in fit.pop("samples"))
    )
    return {"fit": fit, "sample_count": count, "max_local_slope_deg": max_slope}


def native_measure_steps(
    unreal, world, ground, actor, bounds, xy, editor, policy, support
):
    actors = editor.get_all_level_actors()
    ignored = [a for a in actors if a != ground]
    need(
        trace_ground(unreal, world, xy, actors) is None,
        "Ground exclusion negative control failed",
    )
    coarse = yield from measure_grid_steps(
        unreal, world, ground, ignored, actor, bounds, xy, 65, support
    )
    fine = yield from measure_grid_steps(
        unreal, world, ground, ignored, actor, bounds, xy, 129, support
    )
    measurement = {
        "height_cm": 2 * bounds["extent"][2],
        "uniform_scale": 1.0,
        "yaw_deg": 0.0,
        "tilt_deg": 0.0,
        "max_local_slope_deg": fine["max_local_slope_deg"],
        "ground_class": "LandscapeHeightfieldCollisionComponent",
        "sample_count": fine["sample_count"],
        "valid_ground_count": fine["sample_count"],
        "coverage_status": "COMPLETE_SAMPLED_MESH_FOOTPRINT",
        "fit": fine["fit"],
        "refinement": {
            "coarse_grid": 65,
            "fine_grid": 129,
            "coarse_root_cm": coarse["fit"]["root_zero_sampled_air_cm"],
            "fine_root_cm": fine["fit"]["root_zero_sampled_air_cm"],
            "coarse_embedding_cm": coarse["fit"]["required_embedding_cm"],
            "fine_embedding_cm": fine["fit"]["required_embedding_cm"],
        },
    }
    return measurement, policy.evaluate(measurement, policy.refined_trial_policy())


def public_job(live):
    job = getattr(live, "_pcg365_remote_job", None)
    if job is None:
        return {
            "status": "APPLIED_PREVIEW",
            "map_saved": False,
            "operation_status": "NO_CONTACT_JOB",
            "preview_placed": len(getattr(live, "_pcg365_remote_actors", [])),
            "production_admitted": False,
            "qualified_assets": [],
            "performance_pass": False,
        }
    return {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        **{k: v for k, v in job.items() if not k.startswith("_")},
    }


def stop_job_callback(unreal, job):
    handle = job.pop("_tick", None)
    if handle is None:
        return True
    try:
        unreal.unregister_slate_post_tick_callback(handle)
        job["tick_unregistered"] = True
        return True
    except Exception as exc:
        job["_tick"] = handle
        job["tick_unregistered"] = False
        job["tick_unregister_error"] = type(exc).__name__ + ": " + str(exc)[:256]
        return False


def cleanup_native_mesh_guards(job):
    failed = []
    for mesh, delegate, callback, path in job.get("_mesh_edit_bindings", []):
        try:
            delegate.remove_callable(callback)
            need(
                delegate.contains_callable(callback) is False,
                "Native mesh delegate remains bound",
            )
        except Exception as exc:
            failed.append((mesh, delegate, callback, path))
            job["mesh_edit_guard_cleanup_error"] = (
                type(exc).__name__ + ": " + str(exc)[:256]
            )
    job["_mesh_edit_bindings"] = failed
    job["mesh_edit_guard_cleanup_complete"] = not failed
    return not failed


def bind_native_mesh_guards_steps(unreal, world, job):
    job["phase"] = "BIND_CURRENT_NATIVE_MESH_CHANGE_GUARDS"
    job["native_mesh_dirty"] = False
    job["native_mesh_dirty_owners"] = []
    job["_mesh_edit_bindings"] = []
    job["mesh_edit_guard_bound_meshes"] = 0
    for actor in native_geometry_inventory(
        unreal, world, job["_expected_native_labels"]
    ):
        mesh = actor.get_dynamic_mesh_component().get_dynamic_mesh()
        need(mesh is not None, "Native mesh absent before mutation guard binding")
        delegate = mesh.get_editor_property("mesh_modified_bp_event")
        need(
            all(
                callable(getattr(delegate, name, None))
                for name in ("add_callable", "remove_callable", "contains_callable")
            ),
            "Native MeshModifiedBPEvent delegate schema unavailable",
        )
        path = actor.get_path_name()

        def make_callback(expected_mesh, owner):
            def modified(modified_mesh):
                if job.get("operation_status") == "CONTACT_JOB_RUNNING":
                    job["native_mesh_dirty"] = True
                    if len(job["native_mesh_dirty_owners"]) < 20:
                        job["native_mesh_dirty_owners"].append(
                            owner
                            if modified_mesh == expected_mesh
                            else owner + ":unexpected_event_owner"
                        )

            return modified

        callback = make_callback(mesh, path)
        # Retain exact callable identity even if native add partially fails.
        job["_mesh_edit_bindings"].append((mesh, delegate, callback, path))
        delegate.add_callable(callback)
        need(
            delegate.contains_callable(callback) is True,
            "Native mesh modification callback not actually bound",
        )
        job["mesh_edit_guard_bound_meshes"] += 1
        yield {"grid": None, "native_guard_binding": True}
    need(
        job["mesh_edit_guard_bound_meshes"] == 559,
        "Not all559native mesh change guards bound",
    )


def assert_native_mesh_guards(job):
    need(
        job.get("native_mesh_dirty") is not True,
        "Native geometry emitted MeshModified during qualification",
    )
    bindings = job.get("_mesh_edit_bindings")
    need(
        bindings is not None and len(bindings) == 559,
        "Complete native geometry mutation guard missing",
    )
    for mesh, delegate, callback, path in bindings:
        need(
            delegate.contains_callable(callback) is True,
            "Native mesh modification guard disconnected",
        )
    need(
        job.get("native_mesh_dirty") is not True,
        "Native geometry emitted MeshModified during guard verification",
    )


def assert_native_snapshot_metadata(unreal, world, job, snapshot):
    """Synchronous full collective metadata check, no Slate yield before commit."""
    need(
        job.get("native_mesh_dirty") is not True,
        "Native geometry changed during qualification",
    )
    actors = native_geometry_inventory(unreal, world, job["_expected_native_labels"])
    need(len(snapshot) == len(actors), "Native snapshot owner count changed")
    for actor, expected in zip(actors, snapshot):
        metadata, mesh = native_component_snapshot(unreal, actor)
        need(
            metadata == expected["metadata"],
            "Previously scanned native metadata/transform changed",
        )
    need(
        job.get("native_mesh_dirty") is not True,
        "Native geometry changed during final metadata verification",
    )


def rollback_job(unreal, live, editor, job, status, reason=None):
    # Make an unregister failure inert before attempting any native cleanup.
    job["operation_status"] = status
    callback_stopped = stop_job_callback(unreal, job)
    generator = job.pop("_generator", None)
    generator_closed = True
    if generator is not None:
        try:
            generator.close()
        except Exception as exc:
            generator_closed = False
            job["generator_close_error"] = type(exc).__name__ + ": " + str(exc)[:256]
    failed = []
    for actor in getattr(live, "_pcg365_remote_actors", []):
        try:
            if not editor.destroy_actor(actor):
                failed.append(actor)
        except Exception:
            failed.append(actor)
    live._pcg365_remote_actors = failed
    guards_cleaned = cleanup_native_mesh_guards(job)
    complete = not failed and callback_stopped and generator_closed and guards_cleaned
    job["operation_status"] = status if complete else "CONTACT_JOB_ROLLBACK_INCOMPLETE"
    job["preview_placed"] = len(failed)
    job["rollback_complete"] = complete
    if reason:
        job["error"] = reason[:512]


def validate_job_world(unreal, live, world, ground, meshes, materials, data, job):
    need(
        job.get("native_mesh_dirty") is not True,
        "Native mesh modification observed; qualification cancelled",
    )
    current = unreal.get_editor_subsystem(
        unreal.UnrealEditorSubsystem
    ).get_editor_world()
    need(
        current == world
        and live.world == world
        and world.get_path_name().split(".")[0] == data["map_package"],
        "Editor world changed during contact job",
    )
    need(
        str(ground.get_actor_transform()) == job["_ground_transform"],
        "Landscape transform changed during contact job",
    )
    for asset in data["assets"]:
        mesh = meshes[asset["id"]]
        bounds = mesh.get_bounds()
        need(
            mesh.get_num_triangles(0) == asset["expected_lod0_triangles"]
            and all(
                abs(a - b) <= 0.01
                for a, b in zip(
                    vec(bounds.origin) + vec(bounds.box_extent),
                    asset["bounds_cm"]["origin"] + asset["bounds_cm"]["extent"],
                )
            )
            and len(mesh.static_materials) > 0
            and all(
                mesh.get_material(i) == materials[asset["id"]]
                for i in range(len(mesh.static_materials))
            ),
            "Imported geometry/material changed during contact job",
        )
    for actor, location, asset_id in job["_expected_actors"]:
        component = actor.static_mesh_component
        need(
            component.static_mesh == meshes[asset_id]
            and component.get_collision_enabled() == unreal.CollisionEnabled.QUERY_ONLY,
            "Owned preview mesh/collision binding changed during contact job",
        )
        angle = actor.get_actor_rotation()
        need(
            vec(actor.get_actor_location()) == location
            and vec(actor.get_actor_scale3d()) == [1.0, 1.0, 1.0]
            and [angle.pitch, angle.yaw, angle.roll] == [0.0, 0.0, 0.0],
            "Owned preview transform changed during contact job",
        )


def triangle_square_overlap(triangle, center, half_extent):
    """Conservative inclusive XY SAT; handles edge crossing and vertical faces.

    XY projection discards height deliberately: road, shoulders, cuts and support
    geometry exclude the complete vertical column, including bridge structures.
    """
    need(len(triangle) == 3 and len(center) == 2, "Invalid triangle/square schema")
    cx, cy = [number(v) for v in center]
    half = number(half_extent)
    need(half > 0, "Invalid native exclusion square")
    points = []
    for vertex in triangle:
        need(len(vertex) == 3, "Invalid native triangle position")
        xyz = [number(v) for v in vertex]
        points.append((xyz[0] - cx, xyz[1] - cy))
    axes = [(1.0, 0.0), (0.0, 1.0)]
    for i in range(3):
        a, b = points[i], points[(i + 1) % 3]
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx or dy:
            axes.append((-dy, dx))
    for ax, ay in axes:
        projections = [x * ax + y * ay for x, y in points]
        square_radius = half * (abs(ax) + abs(ay))
        if max(projections) < -square_radius or min(projections) > square_radius:
            return False
    return True


def native_expected_geometry_labels(unreal, context):
    """Same read-only source-World inventory used by the accepted native reader.

    Only actor labels/class identity are inherited; current support112 geometry
    remains independently read, never incorrectly compared to its old version.
    """
    project = Path(context["project"]).resolve()
    proof = {
        "path": "Content/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.umap",
        "bytes": 193018676,
        "sha256": "cbbf374309508fdb2c6f86c6324af4a3824a0c5ed32a4bfc29200ad3b29da183",
    }
    file_proof(project, proof)
    original_path = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.L_SaCalobraRoadAsphaltReview"
    source = unreal.load_asset(original_path)
    need(
        isinstance(source, unreal.World) and source.get_path_name() == original_path,
        "Pinned source World missing; active World must not be switched",
    )
    originals = list(
        unreal.GameplayStatics.get_all_actors_of_class(source, unreal.DynamicMeshActor)
    )
    labels = [a.get_actor_label() for a in originals]
    need(
        len(labels) == len(set(labels)) == 559,
        "Pinned source World mesh-label inventory differs",
    )
    return frozenset(labels)


def native_geometry_inventory(unreal, world, expected_labels):
    need(len(expected_labels) == 559, "Exact pinned559label set required")
    actors = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.DynamicMeshActor)
    )
    need(
        len(actors) == 559,
        "Current native road/CUT/support inventory must contain559 meshes",
    )
    labels = [a.get_actor_label() for a in actors]
    need(
        len(set(labels)) == 559
        and set(labels) == set(expected_labels)
        and "YACS_PERSIST_ROAD" in labels
        and {"YACS_PERSIST_SUPPORT_" + str(i).zfill(3) for i in range(186)}
        <= set(labels),
        "Missing/unknown/duplicate current native road/CUT/support owner",
    )
    owners = {a.get_actor_label(): a for a in actors}
    all_actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    for actor in all_actors:
        label = actor.get_actor_label()
        if label in expected_labels:
            need(
                isinstance(actor, unreal.DynamicMeshActor) and actor == owners[label],
                "Unsupported actor class or duplicate expected native owner",
            )
    return sorted(actors, key=lambda a: a.get_actor_label())


def native_component_snapshot(unreal, actor):
    component = actor.get_dynamic_mesh_component()
    need(component is not None, "Current native road/CUT/support component missing")
    mesh = component.get_dynamic_mesh()
    need(mesh is not None, "Current native road/CUT/support mesh missing")
    count, ids = mesh.get_triangle_count(), mesh.get_num_triangle_ids()
    need(
        type(count) is int and type(ids) is int and 0 < count <= ids <= 4000000,
        "Unsupported native mesh triangle-ID inventory",
    )
    transform = component.get_world_transform()
    # Exact reflected FTransform operation; four calls produce its affine basis.
    basis = [
        vec(unreal.MathLibrary.transform_location(transform, unreal.Vector(*point)))
        for point in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    ]
    origin = basis[0]
    columns = [[basis[i + 1][j] - origin[j] for j in range(3)] for i in range(3)]
    determinant = (
        columns[0][0] * (columns[1][1] * columns[2][2] - columns[1][2] * columns[2][1])
        - columns[1][0]
        * (columns[0][1] * columns[2][2] - columns[0][2] * columns[2][1])
        + columns[2][0]
        * (columns[0][1] * columns[1][2] - columns[0][2] * columns[1][1])
    )
    need(
        math.isfinite(determinant) and determinant != 0,
        "Degenerate native component world transform",
    )
    return {
        "actor": actor.get_path_name(),
        "label": actor.get_actor_label(),
        "component": component.get_path_name(),
        "mesh": mesh.get_path_name(),
        "triangle_count": count,
        "triangle_ids": ids,
        "component_transform": str(transform),
        "actor_transform": str(actor.get_actor_transform()),
        "basis": basis,
    }, mesh


def world_triangle(local, basis, unreal=None, transform=None):
    # Identity components retain exact native doubles without cancellation from
    # affine-basis reconstruction. Nonidentity transforms use the native method
    # for every vertex; no guessed local/world mapping or XY rounding margin.
    identity = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if basis == identity:
        return [vec(vertex) for vertex in local]
    need(
        unreal is not None and transform is not None,
        "Native nonidentity transform unavailable",
    )
    return [
        vec(unreal.MathLibrary.transform_location(transform, vertex))
        for vertex in local
    ]


def native_road_exclusion_steps(unreal, world, data, native_bounds, job, previous=None):
    """Complete current-geometry positional snapshot, incrementally read only.

    We deliberately do not use GeometryScript box selection: installed Epic
    docs say it misses triangles crossing a box without any vertices inside.
    Native triangle IDs/world coordinates are streamed and hashed, not retained.
    """
    need(
        job.get("native_mesh_dirty") is not True,
        "Native mesh modified before triangle scan",
    )
    actors = native_geometry_inventory(unreal, world, job["_expected_native_labels"])
    squares = {}
    for row in data["placements"]:
        bounds = native_bounds[row["asset_id"]]
        radius = math.hypot(
            abs(bounds["origin"][0]) + bounds["extent"][0],
            abs(bounds["origin"][1]) + bounds["extent"][1],
        )
        squares[row["site"]] = (row["world_xy_cm"], radius + 50.0)
    decisions = {
        site: {
            "status": "PASS_CURRENT_NATIVE_TRIANGLE_EXCLUSION",
            "half_extent_cm": half,
            "clearance_cm": 50.0,
            "method": "ALL559_NATIVE_MESHES_WORLD_XY_TRIANGLE_SQUARE_SAT",
            "production_domain_admitted": False,
        }
        for site, (_, half) in squares.items()
    }
    snapshots = []
    total_ids = 0
    job["phase"] = (
        "VERIFY_CURRENT_NATIVE_GEOMETRY"
        if previous is not None
        else "READ_CURRENT_NATIVE_GEOMETRY"
    )
    for index, actor in enumerate(actors):
        metadata, mesh = native_component_snapshot(unreal, actor)
        transform = actor.get_dynamic_mesh_component().get_world_transform()
        total_ids += metadata["triangle_ids"]
        need(
            total_ids <= 32000000,
            "Current native geometry exceeds bounded32million triangle-ID budget",
        )
        if previous is not None:
            need(
                index < len(previous) and metadata == previous[index]["metadata"],
                "Current road/CUT/support owner, transform or triangle inventory changed",
            )
        digestor = hashlib.sha256()
        valid = 0
        for tid in range(metadata["triangle_ids"]):
            result = mesh.get_triangle_positions(tid)
            need(
                isinstance(result, tuple)
                and len(result) == 4
                and type(result[0]) is bool,
                "Unsupported native triangle-position return schema",
            )
            digestor.update(struct.pack("<q?", tid, result[0]))
            if result[0]:
                valid += 1
                triangle = world_triangle(
                    result[1:], metadata["basis"], unreal, transform
                )
                digestor.update(
                    struct.pack("<9d", *(v for point in triangle for v in point))
                )
                x_min = min(p[0] for p in triangle)
                x_max = max(p[0] for p in triangle)
                y_min = min(p[1] for p in triangle)
                y_max = max(p[1] for p in triangle)
                for site, (center, half) in squares.items():
                    if (
                        x_max < center[0] - half
                        or x_min > center[0] + half
                        or y_max < center[1] - half
                        or y_min > center[1] + half
                    ):
                        continue
                    if (
                        decisions[site]["status"]
                        == "PASS_CURRENT_NATIVE_TRIANGLE_EXCLUSION"
                        and triangle_square_overlap(triangle, center, half)
                    ):
                        decisions[site].update(
                            status="REJECTED_CURRENT_NATIVE_TRIANGLE_OVERLAP",
                            witness_actor=metadata["actor"],
                            witness_label=metadata["label"],
                            witness_triangle_id=tid,
                            witness_world_triangle_cm=triangle,
                        )
            need(
                job.get("native_mesh_dirty") is not True,
                "Native mesh modified during triangle scan",
            )
            yield {"grid": None, "phase": job["phase"], "native_triangle_id": True}
        need(
            valid == metadata["triangle_count"],
            "Native mesh valid triangle-ID count differs",
        )
        after, _ = native_component_snapshot(unreal, actor)
        need(
            after == metadata,
            "Native owner or transform changed during triangle snapshot",
        )
        snapshot = {
            "metadata": metadata,
            "world_triangle_positions_sha256": digestor.hexdigest(),
        }
        if previous is not None:
            need(
                snapshot == previous[index],
                "Current road/CUT/support world triangle positions changed",
            )
        snapshots.append(snapshot)
    need(
        [
            a.get_path_name()
            for a in native_geometry_inventory(
                unreal, world, job["_expected_native_labels"]
            )
        ]
        == [a.get_path_name() for a in actors],
        "Native geometry inventory changed during snapshot",
    )
    assert_native_snapshot_metadata(unreal, world, job, snapshots)
    if previous is not None:
        need(
            snapshots == previous,
            "Current native geometry snapshot changed before final placement",
        )
    job["native_geometry_snapshot_sha256"] = hashlib.sha256(
        json.dumps(
            snapshots, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    job["native_geometry_actor_count"] = len(actors)
    job["native_geometry_triangle_ids_per_scan"] = total_ids
    return snapshots, decisions


def planting_steps(
    unreal, context, data, meshes, result, policy, support, editor, ground, job
):
    live, world = context["live"], context["live"].world
    snapshot, native_exclusions = yield from native_road_exclusion_steps(
        unreal, world, data, job["_native_bounds"], job
    )
    job["current_native_road_exclusions"] = native_exclusions
    pending_placements = []
    job["phase"] = "MEASURE_LANDSCAPE_CONTACT"
    for row in sorted(data["placements"], key=lambda r: r["site"]):
        job["active_site"] = row["site"]
        if (
            native_exclusions[row["site"]]["status"]
            != "PASS_CURRENT_NATIVE_TRIANGLE_EXCLUSION"
        ):
            job["cases"].append(
                {
                    "site": row["site"],
                    "asset_id": row["asset_id"],
                    "status": "REJECTED_NATIVE_SPATIAL_EXCLUSION",
                    "native_exclusion": native_exclusions[row["site"]],
                }
            )
            continue
        actor = editor.spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(), transient=True
        )
        need(actor is not None, "Native rock spawn failed")
        live._pcg365_remote_actors.append(actor)
        expected_actor = [actor, [0.0, 0.0, 0.0], row["asset_id"]]
        job["_expected_actors"].append(expected_actor)
        actor.set_actor_label("PCG365_RemotePreview_" + row["site"])
        actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
        actor.set_actor_rotation(unreal.Rotator(), False)
        component = actor.static_mesh_component
        need(
            component.set_static_mesh(meshes[row["asset_id"]]),
            "Native mesh binding failed",
        )
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
        component.set_collision_response_to_all_channels(
            unreal.CollisionResponseType.ECR_BLOCK
        )
        need(
            vec(actor.get_actor_location()) == [0.0, 0.0, 0.0],
            "Initial measurement actor moved",
        )
        measurement, decision = yield from native_measure_steps(
            unreal,
            world,
            ground,
            actor,
            job["_native_bounds"][row["asset_id"]],
            row["world_xy_cm"],
            editor,
            policy,
            support,
        )
        case = {
            "site": row["site"],
            "asset_id": row["asset_id"],
            "measurement": measurement,
            "decision": decision,
            "ground_exclusion_control": "PASS",
        }
        job["cases"].append(case)
        if decision["status"] != "PASS_SAMPLED_CONTACT_ONLY":
            need(editor.destroy_actor(actor), "Rejected actor rollback failed")
            live._pcg365_remote_actors.remove(actor)
            job["_expected_actors"].remove(expected_actor)
            continue
        location = row["world_xy_cm"] + [measurement["fit"]["root_zero_sampled_air_cm"]]
        pending_placements.append((actor, expected_actor, case, location))
    # No final XY placement is exposed before the complete current-geometry
    # snapshot has been read again and proved unchanged.
    if pending_placements:
        _, final_exclusions = yield from native_road_exclusion_steps(
            unreal, world, data, job["_native_bounds"], job, previous=snapshot
        )
        need(
            final_exclusions == native_exclusions,
            "Current native per-footprint exclusion changed",
        )
    # Completion alone performs the expensive proof rehash, never every tick.
    read_manifest(job["manifest_sha256"], require_plant=True)
    need(
        verify_footprints(data, job["_native_bounds"])
        == result["footprint_exclusions"],
        "Exclusion bytes changed during contact job",
    )
    load_materials(unreal, context, data)
    # Last synchronous collective check follows all long hashes/native reads.
    # No Slate yield exists between these checks and the final location setters.
    assert_native_snapshot_metadata(unreal, world, job, snapshot)
    assert_native_mesh_guards(job)
    need(not job.get("_cancel_requested"), "Diagnostic cancellation requested")
    job["phase"] = "APPLY_VERIFIED_DIAGNOSTIC_LOCATIONS"
    for actor, expected_actor, case, location in pending_placements:
        need(not job.get("_cancel_requested"), "Diagnostic cancellation requested")
        actor.set_actor_location(unreal.Vector(*location), False, False)
        need(
            all(
                abs(a - b) <= 1e-6
                for a, b in zip(vec(actor.get_actor_location()), location)
            ),
            "Planted native location differs",
        )
        expected_actor[1] = vec(actor.get_actor_location())
        case["location_cm"] = location
        job["preview_placed"] += 1
    if pending_placements:
        _, expected_actor, _, location = pending_placements[0]
        asset_id = expected_actor[2]
        bounds = job["_native_bounds"][asset_id]
        center = [location[i] + bounds["origin"][i] for i in range(3)]
        radius = max(
            20.0,
            math.hypot(
                abs(bounds["origin"][0]) + bounds["extent"][0],
                abs(bounds["origin"][1]) + bounds["extent"][1],
            ),
        )
        eye = unreal.Vector(
            center[0] - 4 * radius, center[1] - 4 * radius, center[2] + 3 * radius
        )
        angle = unreal.MathLibrary.find_look_at_rotation(eye, unreal.Vector(*center))
        viewport = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        viewport.set_level_viewport_camera_info(eye, angle)
        observed = viewport.get_level_viewport_camera_info()
        need(
            observed is not None and (observed[0] - eye).length() <= 1.0,
            "Native diagnostic review camera readback differs",
        )
        job["review_camera"] = {
            "location_cm": vec(observed[0]),
            "target_cm": center,
            "map_saved": False,
        }
    job["phase"] = "COMPLETED"
    job["operation_status"] = "CONTACT_JOB_COMPLETED_SAMPLED_ONLY"
    job["active_site"] = None


def start_contact_job(
    unreal, context, data, meshes, materials, result, policy, support
):
    live, world = context["live"], context["live"].world
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = [
        a for a in editor.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)
    ]
    need(len(landscapes) == 1, "Ambiguous Landscape authority")
    ground = landscapes[0]
    transform = ground.get_actor_transform()
    rotation = transform.rotation.rotator()
    need(
        vec(transform.scale3d)[:2] == [50.0, 50.0]
        and [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
        "Landscape grid transform differs",
    )
    expected_native_labels = native_expected_geometry_labels(unreal, context)
    job = {
        **result,
        "operation_status": "CONTACT_JOB_RUNNING",
        "request_id": context.get("request_id"),
        "manifest_sha256": context["_pcg365_manifest_sha256"],
        "sampled_positions": 0,
        "maximum_grid_positions": len(data["placements"]) * (65 * 65 + 129 * 129),
        "active_site": None,
        "current_grid": None,
        "tick_position_budget": 64,
        "tick_native_geometry_budget": 1024,
        "tick_wall_budget_ms": 8,
        "wall_budget_semantics": "BEST_EFFORT_SINGLE_NATIVE_CALL_CANNOT_BE_PREEMPTED",
        "_ground_transform": str(transform),
        "_expected_actors": [],
        "_native_bounds": result["_native_bounds"],
        "_expected_native_labels": expected_native_labels,
        "phase": "STARTED_PENDING_CURRENT_NATIVE_EXCLUSIONS",
        "native_geometry_triangle_ids_read": 0,
        "native_guard_bindings_processed": 0,
        "native_mesh_dirty": False,
        "_mesh_edit_bindings": [],
        "atomic_native_geometry_guarantee": False,
        "mutation_guard_scope": "MeshModifiedBPEvent plus synchronous final owner/transform metadata; direct/deferred/realtime native bypass not proven observable; exclusive quiescent Editor required",
    }
    live._pcg365_remote_actors = []
    live._pcg365_remote_job = job
    generator = planting_steps(
        unreal, context, data, meshes, result, policy, support, editor, ground, job
    )
    job["_generator"] = generator

    def tick(_delta):
        if job.get("operation_status") != "CONTACT_JOB_RUNNING" or job.get(
            "_advancing", False
        ):
            return
        job["_advancing"] = True
        try:
            validate_job_world(
                unreal, live, world, ground, meshes, materials, data, job
            )
            need(not job.get("_cancel_requested"), "Diagnostic cancellation requested")
            deadline = time.perf_counter() + 0.008
            contact_positions = 0
            for _ in range(1024):
                update = next(generator)
                need(
                    not job.get("_cancel_requested"),
                    "Diagnostic cancellation requested",
                )
                if update.get("native_triangle_id"):
                    job["native_geometry_triangle_ids_read"] += 1
                elif update.get("native_guard_binding"):
                    job["native_guard_bindings_processed"] += 1
                else:
                    job["sampled_positions"] += 1
                    contact_positions += 1
                job["current_grid"] = update["grid"]
                if contact_positions >= 64 or time.perf_counter() >= deadline:
                    break
        except StopIteration:
            if job.get("_cancel_requested"):
                rollback_job(
                    unreal, live, editor, job, "CONTACT_JOB_CANCELLED_ROLLED_BACK"
                )
                return
            stopped = stop_job_callback(unreal, job)
            guards_cleaned = cleanup_native_mesh_guards(job)
            job.pop("_generator", None)
            if not stopped or not guards_cleaned:
                job["operation_status"] = (
                    "CONTACT_JOB_COMPLETED_CALLBACK_CLEANUP_REQUIRED"
                )
        except Exception as exc:
            rollback_job(
                unreal,
                live,
                editor,
                job,
                (
                    "CONTACT_JOB_CANCELLED_ROLLED_BACK"
                    if job.get("_cancel_requested")
                    else "FAILED_NATIVE_GUARD_NO_PLACEMENT"
                    if job.get("phase") == "BIND_CURRENT_NATIVE_MESH_CHANGE_GUARDS"
                    and not getattr(live, "_pcg365_remote_actors", [])
                    else "CONTACT_JOB_FAILED_ROLLED_BACK"
                ),
                type(exc).__name__ + ": " + str(exc),
            )

        finally:
            job["_advancing"] = False

    try:
        job["_tick"] = unreal.register_slate_post_tick_callback(tick)
    except Exception:
        rollback_job(
            unreal,
            live,
            editor,
            job,
            "CONTACT_JOB_FAILED_ROLLED_BACK",
            "Tick registration failed",
        )
        raise
    return public_job(live)


def run(unreal, context, parameters):
    need(
        context.get("intent") == "preview" and context.get("asset_scope") == (),
        "Memory-only preview required",
    )
    need(
        set(parameters) == {"operation", "manifest_sha256"}
        and parameters["operation"] in ("import", "plant", "clear", "status"),
        "Unknown bounded preview operation",
    )
    live = context["live"]
    world = live.world
    need(
        world.get_path_name().split(".")[0] == live.map_package,
        "Current world identity differs",
    )
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    owned = getattr(live, "_pcg365_remote_actors", [])
    job = getattr(live, "_pcg365_remote_job", None)
    if parameters["operation"] == "status":
        return public_job(live)
    if (
        parameters["operation"] == "clear"
        and job is not None
        and (job.get("operation_status") == "CONTACT_JOB_RUNNING" or "_tick" in job)
    ):
        if job.get("_advancing"):
            # A native call may be pumping Slate inside the generator. Its
            # owned actor/iterator cannot be destroyed until that call returns.
            job["_cancel_requested"] = True
            job["cancellation_requested"] = True
            return {
                **public_job(live),
                "operation_status": "CONTACT_JOB_CANCEL_REQUESTED_DEFERRED",
            }
        rollback_job(unreal, live, editor, job, "CONTACT_JOB_CANCELLED_ROLLED_BACK")
        return public_job(live)
    if job is not None and job.get("operation_status") == "CONTACT_JOB_RUNNING":
        return {
            **public_job(live),
            "request_rejected": "CONTACT_JOB_RUNNING_USE_STATUS_OR_CLEAR",
        }
    if parameters["operation"] == "clear":
        failures = []
        for actor in owned:
            try:
                if not editor.destroy_actor(actor):
                    failures.append(actor)
            except Exception:
                failures.append(actor)
        live._pcg365_remote_actors = failures
        need(not failures, "Owned actor rollback incomplete; retained failed ownership")
        if job is not None:
            job["operation_status"] = "CONTACT_JOB_CLEARED"
            job["preview_placed"] = 0
            job["rollback_complete"] = True
        return {
            "status": "APPLIED_PREVIEW",
            "map_saved": False,
            "preview_placed": 0,
            "production_admitted": False,
            "cleared": len(owned),
        }
    if owned:
        return {**public_job(live), "request_rejected": "CLEAR_EXISTING_PREVIEW_FIRST"}
    try:
        data = read_manifest(
            parameters["manifest_sha256"],
            require_plant=parameters["operation"] == "plant",
        )
        need(data["map_package"] == live.map_package, "Manifest targets another map")
        footprint_evidence = {}
        if parameters["operation"] == "plant":
            need(
                data["placements"],
                "No approved exclusion-valid anchor placement supplied",
            )
            footprint_evidence = verify_footprints(data)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # A rejected preflight has not imported/spawned anything. Keep status and
        # cleanup available; no native command is replayed or declared passing.
        return {
            "status": "APPLIED_PREVIEW",
            "map_saved": False,
            "operation_status": "REJECTED_PRECHECK_NO_SCENE_MUTATION",
            "reason": type(exc).__name__ + ": " + str(exc)[:512],
            "preview_placed": 0,
            "native_contact_executed": False,
            "production_admitted": False,
            "qualified_assets": [],
            "performance_pass": False,
        }
    policy, support = load_helpers()
    materials = load_materials(unreal, context, data)
    cache = getattr(live, "_pcg365_remote_imports", {})
    key = parameters["manifest_sha256"]
    meshes = cache.get(key)
    if meshes is None:
        meshes = {}
        # Cache each success immediately; a partial failed import never grants
        # contact but remains explicitly owned memory for a later safe retry.
        cache[key] = meshes
        live._pcg365_remote_imports = cache
    for asset in data["assets"]:
        if asset["id"] not in meshes:
            meshes[asset["id"]] = import_mesh(
                unreal, asset, materials[asset["id"]], DESTINATION + "/R" + key[:16]
            )
        mesh = meshes[asset["id"]]
        actual = mesh.get_bounds()
        need(
            mesh.get_num_triangles(0) == asset["expected_lod0_triangles"]
            and all(
                abs(a - b) <= 0.01
                for a, b in zip(
                    vec(actual.origin) + vec(actual.box_extent),
                    asset["bounds_cm"]["origin"] + asset["bounds_cm"]["extent"],
                )
            ),
            "Cached native geometry changed",
        )
        need(
            all(
                mesh.get_material(i) == materials[asset["id"]]
                for i in range(len(mesh.static_materials))
            ),
            "Cached Forge binding changed",
        )
    native_bounds = {}
    for asset in data["assets"]:
        actual = meshes[asset["id"]].get_bounds()
        native_bounds[asset["id"]] = {
            "origin": vec(actual.origin),
            "extent": vec(actual.box_extent),
        }
    if parameters["operation"] == "plant":
        footprint_evidence = verify_footprints(data, native_bounds)
    result = {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        "preview_placed": 0,
        "production_admitted": False,
        "qualified_assets": [],
        "performance_pass": False,
        "memory_imports": sorted(meshes),
        "_native_bounds": native_bounds,
        "cases": [],
        "footprint_exclusions": footprint_evidence,
        "full_qualification": False,
        "continuous_support_verified": False,
    }
    if parameters["operation"] == "import":
        read_manifest(parameters["manifest_sha256"])
        load_materials(unreal, context, data)
        return {k: v for k, v in result.items() if not k.startswith("_")}
    try:
        return start_contact_job(
            unreal,
            {**context, "_pcg365_manifest_sha256": parameters["manifest_sha256"]},
            data,
            meshes,
            materials,
            result,
            policy,
            support,
        )
    except Exception as exc:
        job = getattr(live, "_pcg365_remote_job", None)
        if job is not None and (
            job.get("operation_status") == "CONTACT_JOB_RUNNING"
            or job.get("_mesh_edit_bindings")
            or "_tick" in job
        ):
            rollback_job(
                unreal,
                live,
                editor,
                job,
                "FAILED_NATIVE_GUARD_NO_PLACEMENT",
                type(exc).__name__ + ": " + str(exc),
            )
            return public_job(live)
        failed = {k: v for k, v in result.items() if not k.startswith("_")}
        failed.update(
            operation_status="FAILED_NATIVE_GUARD_NO_PLACEMENT",
            reason=type(exc).__name__ + ": " + str(exc)[:512],
            native_contact_executed=False,
            preview_placed=0,
        )
        live._pcg365_remote_job = failed
        return public_job(live)
