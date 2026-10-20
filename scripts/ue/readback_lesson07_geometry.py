"""Inspect the pinned saved L07 in an owned, physically isolated Editor.

The PowerShell launcher authenticates/copies assets and ordinary CI binaries.
This reader never saves or repairs the world. Native package queries and four
diagnostic traces cannot accept source heights, seams, visibility or materials.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

LEVEL_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MAP_FILE = "Content" + LEVEL_PATH.removeprefix("/Game") + ".umap"
MAP_SHA256 = "61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7"
MAP_SIZE = 1842190204
EXPECTED_ACTORS = {f"SaCalobra_Unified_{x}_{y}" for x in range(2) for y in range(2)}
EXPECTED_MATERIAL = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
REQUIRED_PACKAGES = (
    LEVEL_PATH, EXPECTED_MATERIAL,
    "/Game/PegasusDemo/Materials/Landscape/M_Pegasus_Landscape_Master",
    "/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap",
    "/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color",
    *(f"/Game/Generated/YACS/Lesson07_Unified/Materials/TA_{name}_Unified"
      for name in ("Colour", "Normal", "Masks")),
)
MAX_DEPENDENCIES = 2048
MAX_DEPENDENCY_EDGES = 16384
COMPONENT_FIELDS = ("component_size_quads", "subsection_size_quads",
                    "num_subsections", "section_base_x", "section_base_y")


def plain_path(value):
    """Do not follow a linked parent while authenticating evidence or copies."""
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("An absolute, non-traversing path is required")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (
            ancestor.exists()
            and getattr(ancestor.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("Refuse linked/reparse input or output")
    return path.resolve()


def file_identity(path, limit):
    path = plain_path(path)
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= limit:
        raise ValueError("Input is not a bounded, nonempty file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Input changed while hashing")
    return {"path": str(path), "size_bytes": after.st_size, "sha256": digest.hexdigest()}


def authenticated_preparation(project, env):
    project = plain_path(project)
    manifest_path = plain_path(env["YACS_L07_PREPARATION_FILE"])
    manifest_identity = file_identity(manifest_path, 8 * 1024**2)
    if manifest_identity["sha256"] != env["YACS_L07_PREPARATION_SHA256"]:
        raise ValueError("Untrusted L07 staging receipt bytes")
    value = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (value.get("schema_version") != 1
            or value.get("status") != "L07_COPIED_BYTES_NATIVE_READ_PENDING"
            or value.get("source_head") != env["YACS_L07_EXPECTED_HEAD"]
            or re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_head"))) is None
            or plain_path(value["candidate_root"]) != project
            or value.get("level") != LEVEL_PATH
            or value.get("geometry_accepted") is not False
            or value.get("dependency_closure_complete") is not False):
        raise ValueError("Staging receipt does not identify this isolated L07 read")
    if (value["map"]["relative"] != MAP_FILE
            or value["map"]["source_identity"]["sha256"] != MAP_SHA256
            or value["map"]["source_identity"]["size_bytes"] != MAP_SIZE):
        raise ValueError("Staging receipt differs from the pinned saved L07")
    reader_identity = file_identity(__file__, 256 * 1024)
    if reader_identity["sha256"] != value["reader_identity"]["sha256"]:
        raise ValueError("Executed reader bytes differ from staging provenance")
    observed_map = file_identity(project / MAP_FILE, 3 * 1024**3)
    if (observed_map["sha256"], observed_map["size_bytes"]) != (MAP_SHA256, MAP_SIZE):
        raise ValueError("Candidate map differs from the pinned saved L07")
    output = plain_path(env["YACS_LESSON07_READBACK_PATH"])
    if (output != plain_path(value["report_path"])
            or output.parent != manifest_path.parent or output.exists()):
        raise ValueError("Readback output is not its new, owned evidence file")
    return value, manifest_identity, observed_map, output


def observe(call):
    try:
        return {"observed": True, "value": call(), "error": None}
    except Exception as exc:
        return {"observed": False, "value": None, "error": str(exc)[:1000]}


def dependency_inventory(seeds, query, package_exists, staged_packages):
    """Bounded on-disk package walk; None/exception never means no dependencies.

    This is an inventory of native package references, not a claim about dynamic
    string references, shader compilation or a complete rendered asset closure.
    """
    pending = list(sorted(set(seeds)))
    visited = set()
    rows = []
    problems = []
    edge_count = 0
    while pending:
        package = pending.pop()
        if package in visited:
            continue
        if len(visited) >= MAX_DEPENDENCIES:
            problems.append("Native dependency inventory exceeded its package bound")
            break
        visited.add(package)
        row = {"package": package, "present": None, "dependencies": None}
        rows.append(row)
        if re.fullmatch(r"/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*", package) is None:
            problems.append(f"Unsupported package name: {package[:300]}")
            continue
        if package.startswith("/Game/") and package not in staged_packages:
            row["present"] = False
            problems.append(f"Referenced game package was not staged: {package}")
            continue
        try:
            row["present"] = package_exists(package)
            if row["present"] is not True:
                problems.append(f"Package missing or availability UNKNOWN: {package}")
                continue
            if package.startswith("/Script/"):
                row["kind"] = "LOADED_SCRIPT_PACKAGE"
                row["dependencies"] = []
                continue
            dependencies = query(package)
            if dependencies is None:
                problems.append(f"Dependency query UNKNOWN: {package}")
                continue
            dependencies = sorted({str(item) for item in dependencies})
            edge_count += len(dependencies)
            if edge_count > MAX_DEPENDENCY_EDGES:
                problems.append("Native dependency inventory exceeded its edge bound")
                break
            row["dependencies"] = dependencies
            pending.extend(dep for dep in dependencies if dep not in visited)
        except Exception as exc:
            problems.append(f"Dependency query failed for {package}: {str(exc)[:500]}")
    return {
        "status": "ON_DISK_PACKAGE_QUERIES_COMPLETE" if rows and not problems else "INCOMPLETE",
        "queries_complete": bool(rows) and not problems,
        "dependency_closure_complete": False,
        "scope": "Native on-disk hard/soft game/editor package references; dynamic references and shaders are unproved",
        "packages": rows, "edge_count": edge_count, "problems": problems,
    }


def native_dependencies(api, preparation):
    registry = api.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    options = api.AssetRegistryDependencyOptions(
        include_soft_package_references=True, include_hard_package_references=True,
        include_game_package_references=True, include_editor_only_package_references=True,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False,
    )
    staged = {"/Game/" + row["relative"][len("Content/"):].rsplit(".", 1)[0]
              for row in preparation["assets"]
              if row["relative"].endswith((".uasset", ".umap"))}

    def exists(package):
        if package.startswith("/Script/"):
            return api.find_object(None, package) is not None
        assets = registry.get_assets_by_package_name(api.Name(package), True)
        return None if assets is None else len(assets) > 0

    return dependency_inventory(
        REQUIRED_PACKAGES, lambda package: registry.get_dependencies(api.Name(package), options),
        exists, staged,
    )

def on_source_grid(x_m, z_m):
    ax = (x_m + 3999.75) / 0.5
    az = (3999.75 - z_m) / 0.5
    return abs(ax - round(ax)) < 1e-5 and abs(az - round(az)) < 1e-5

def actor_height_step_cm(scale_z):
    if not math.isfinite(scale_z) or scale_z <= 0:
        raise ValueError("Invalid Landscape Scale.Z")
    return float(scale_z) / 128.0

def read_component_layout(api, component):
    """Read public C++ fields once, authenticating the native component result."""
    result = {"observed": False, "component_path": None, "world_package": None,
              "fields": None, "error": None}
    try:
        component_path = component.get_path_name()
        if not isinstance(component_path, str) or not component_path:
            raise ValueError("Native component identity is UNKNOWN")
        result["component_path"] = component_path
        raw = api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_layout(component)
        if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 4096:
            raise ValueError("Native component layout is not bounded JSON")
        value = json.loads(raw)
        if (not isinstance(value, dict) or type(value.get("schema_version")) not in (int, float)
                or value["schema_version"] != 1):
            raise ValueError("Unknown native component layout schema")
        if value.get("observed") is not True:
            raise ValueError("Native component layout UNKNOWN: " + str(value.get("error", "no observation")))
        if value.get("component_path") != component_path or value.get("world_package") != LEVEL_PATH:
            raise ValueError("Native component layout identity differs from this L07 component")
        raw_fields = value.get("fields")
        if not isinstance(raw_fields, dict) or set(raw_fields) != set(COMPONENT_FIELDS):
            raise ValueError("Native component layout fields are missing or unexpected")
        fields = {}
        for name in COMPONENT_FIELDS:
            number = raw_fields[name]
            # UE's JSON number writer may emit 254.0 for an actual int32.
            # Bounds and exact integrality reject NaN/Inf/fractions before conversion.
            if (type(number) not in (int, float) or not -(2**31) <= number < 2**31
                    or (type(number) is float and not number.is_integer())):
                raise ValueError(f"Native component layout {name} is not an exact int32")
            fields[name] = int(number)
        result.update(observed=True, world_package=value["world_package"], fields=fields)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    return result


def actual_component_settings(layouts):
    observed = {}
    for prop in COMPONENT_FIELDS:
        values = [layout["fields"][prop] if layout["observed"] else None for layout in layouts]
        observed[prop] = {
            "values": sorted({v for v in values if v is not None}),
            "read_count": len(values) - values.count(None),
            "total": len(values),
            "complete": bool(values) and None not in values,
        }
    return observed


def actual_landscape_layers(api, proxy):
    """Layer APIs belong to the owning Landscape, including for streaming proxies."""
    try:
        owner = proxy.get_landscape_actor()
        if owner is None or not isinstance(owner, api.Landscape):
            raise ValueError("Owning Landscape is UNKNOWN")
        owner_path = owner.get_path_name()
        if owner_path.split(".")[0] != LEVEL_PATH:
            raise ValueError("Owning Landscape is outside the pinned L07 world")
    except Exception as exc:
        return {key: {"observed": False, "value": None, "error": str(exc)[:1000]}
                for key in ("landscape_owner", "edit_layers", "target_layers")}

    def names(values):
        if values is None:
            raise ValueError("Native layer names are UNKNOWN")
        result = []
        for value in values:
            if value is None:
                raise ValueError("Native layer name is UNKNOWN")
            result.append(str(value))
        return result

    return {
        "landscape_owner": {"observed": True, "value": owner_path, "error": None},
        "edit_layers": observe(lambda: names(layer.get_name_bp() for layer in owner.get_edit_layers_bp())),
        "target_layers": observe(lambda: names(owner.get_target_layer_names(True))),
    }


def structure_problems(rows):
    problems = []
    names = [row["label"] for row in rows]
    if len(rows) != 4 or len(set(names)) != 4 or set(names) != EXPECTED_ACTORS:
        problems.append("Actual Landscape labels/count differ from the four pinned L07 actors")
    for row in rows:
        label = row["label"]
        if row["component_count"] != 1024:
            problems.append(f"{label}: expected 1024 actual components")
        for prop in COMPONENT_FIELDS:
            measured = row["actual_component_properties"][prop]
            if (measured["complete"] is not True or measured["read_count"] != 1024
                    or measured["total"] != 1024):
                problems.append(f"{label}: native component field UNKNOWN/incomplete: {prop}")
        for prop, expected in (("component_size_quads", 254),
                               ("subsection_size_quads", 127), ("num_subsections", 2)):
            if row["actual_component_properties"][prop]["values"] != [expected]:
                problems.append(f"{label}: actual {prop} differs from the L07 layout")
        pairs = row["component_section_bases"]
        if len(pairs) != 1024 or any(None in pair for pair in pairs):
            problems.append(f"{label}: component section positions are UNKNOWN/incomplete")
        else:
            xs, ys = (sorted({pair[i] for pair in pairs}) for i in (0, 1))
            if (len(set(map(tuple, pairs))) != 1024 or len(xs) != 32 or len(ys) != 32
                    or any(b - a != 254 for values in (xs, ys) for a, b in zip(values, values[1:]))):
                problems.append(f"{label}: actual component positions do not form the expected grid")
        for prop in ("location_cm", "rotation_deg_pitch_yaw_roll", "scale", "bounds_origin_cm", "bounds_extent_cm"):
            if len(row[prop]) != 3 or not all(math.isfinite(x) for x in row[prop]):
                problems.append(f"{label}: non-finite or incomplete {prop}")
        if row["scale"][:2] != [50.0, 50.0] or row["scale"][2] <= 0:
            problems.append(f"{label}: unexpected Landscape scale")
        if not row["assigned_material"] or row["assigned_material"].split(".")[0] != EXPECTED_MATERIAL:
            problems.append(f"{label}: expected Landscape material is missing or changed")
        for prop in ("hole_material", "edit_layers", "target_layers"):
            if row[prop]["observed"] is not True:
                problems.append(f"{label}: {prop} is UNKNOWN")
    return problems


def inspect_map(unreal, preparation):
    world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    if not world or world.get_path_name().split(".")[0] != LEVEL_PATH:
        raise RuntimeError(f"Actual loaded world is not the pinned map: {LEVEL_PATH}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()

    landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    print(f"Found {len(landscapes)} landscape actors in level.")

    landscape_data = []
    total_components = 0

    for la in sorted(landscapes, key=lambda x: x.get_name()):
        name = la.get_name()
        loc = la.get_actor_location()
        scale = la.get_actor_scale3d()
        rotation = la.get_actor_rotation()
        origin, extent = la.get_actor_bounds(False)
        comps = la.get_components_by_class(unreal.LandscapeComponent)
        num_comps = len(comps)
        total_components += num_comps
        layouts = [read_component_layout(unreal, comp) for comp in comps]

        mat = la.get_editor_property("landscape_material")
        mat_name = mat.get_path_name() if mat else None

        info = {
            "name": name,
            "label": la.get_actor_label(),
            "class": la.get_class().get_name(),
            "location_cm": [loc.x, loc.y, loc.z],
            "rotation_deg_pitch_yaw_roll": [rotation.pitch, rotation.yaw, rotation.roll],
            "scale": [scale.x, scale.y, scale.z],
            "bounds_origin_cm": [origin.x, origin.y, origin.z],
            "bounds_extent_cm": [extent.x, extent.y, extent.z],
            "component_count": num_comps,
            "actual_component_properties": actual_component_settings(layouts),
            "native_component_layouts": layouts,
            "component_section_bases": [
                [layout["fields"][prop] if layout["observed"] else None
                 for prop in ("section_base_x", "section_base_y")]
                for layout in layouts
            ],
            "expected_design_not_observed": {
                "component_grid": "32x32", "section_quads": 127,
                "num_subsections": 2, "component_quads": 254,
                "tile_quads": 8128, "tile_vertices": 8129,
            },
            "assigned_material": mat_name,
            "hole_material": observe(lambda: (
                la.get_editor_property("landscape_hole_material").get_path_name()
                if la.get_editor_property("landscape_hole_material") else None)),
            **actual_landscape_layers(unreal, la),
        }
        landscape_data.append(info)
        print(f"  Landscape: {name}, comps={num_comps}, mat={mat_name}")

    query_points = [
        {"name": "Puig Major Summit", "x_ue": -128375.0, "y_ue": 349525.0, "x_h": -1283.75, "z_h": 3495.25, "expected_h_m": 1437.16},
        {"name": "Sa Calobra Cove Beach", "x_ue": 47000.0, "y_ue": -106000.0, "x_h": 470.0, "z_h": -1060.0, "expected_h_m": 10.34},
        {"name": "Inland Center (0, 0)", "x_ue": 0.0, "y_ue": 0.0, "x_h": 0.0, "z_h": 0.0, "expected_h_m": 473.51},
        {"name": "Scree Cluster 1 Centroid", "x_ue": -250278.0, "y_ue": 184595.0, "x_h": -2502.78, "z_h": 1845.95, "expected_h_m": 460.95},
    ]

    scales = {a["name"]: float(a["scale"][2]) for a in landscape_data}
    sampled_points = []
    problems = structure_problems(landscape_data)
    rounded_reference_warnings = []
    for qp in query_points:
        sampled = {**qp, "observed": False, "hit": None, "error": None}
        try:
            start = unreal.Vector(qp["x_ue"], qp["y_ue"], 200000.0)
            end = unreal.Vector(qp["x_ue"], qp["y_ue"], -50000.0)
            hit = unreal.SystemLibrary.line_trace_single(
                world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                True, [], unreal.DrawDebugTrace.NONE, True,
            )
            d = hit.to_dict() if hit is not None else {"blocking_hit": False}
            if not isinstance(d, dict) or type(d.get("blocking_hit")) is not bool:
                raise ValueError("Native trace blocking-hit state is UNKNOWN")
            sampled["hit"] = d["blocking_hit"]
            if d["blocking_hit"]:
                impact = d["impact_point"]
                impact_cm = [float(impact.x), float(impact.y), float(impact.z)]
                if not all(math.isfinite(value) for value in impact_cm):
                    raise ValueError("Native trace impact point is non-finite")
                hit_z_cm = impact_cm[2]
                hit_z_m = hit_z_cm / 100.0
                actor_hit = d["hit_actor"].get_name() if d.get("hit_actor") else None
                sampled["impact_point_cm"] = impact_cm
                sampled["hit_z_cm"] = hit_z_cm
                sampled["hit_z_m"] = hit_z_m
                sampled["hit_actor"] = actor_hit
                component = d.get("hit_component") or d.get("component")
                sampled["hit_component"] = component.get_path_name() if component else None
                sampled["hit_component_observed"] = component is not None
                if component is None:
                    problems.append(f"{qp['name']}: hit component is UNKNOWN")
                if qp["expected_h_m"] is not None:
                    delta_m = hit_z_m - qp["expected_h_m"]
                    delta_cm = delta_m * 100.0
                    sampled["delta_m"] = delta_m
                    sampled["delta_cm"] = delta_cm
                    step_cm = (actor_height_step_cm(scales[actor_hit])
                               if actor_hit in scales and math.isfinite(scales[actor_hit])
                               and scales[actor_hit] > 0 else None)
                    sampled["actor_quantization_step_cm"] = step_cm
                    sampled["on_source_grid"] = on_source_grid(qp["x_h"], qp["z_h"])
                    sampled["quantization_steps"] = delta_cm / step_cm if step_cm else None
                    if step_cm is None:
                        problems.append(f"{qp['name']}: hit unexpected actor {actor_hit}")
                    elif sampled["on_source_grid"] and abs(delta_cm) > step_cm / 2.0 + 0.1:
                        rounded_reference_warnings.append(
                            f"{qp['name']}: {delta_cm:.2f}cm differs from a rounded historical "
                            f"reference, not an authoritative source voxel/interpolation."
                        )
                    print(f"  Hit {qp['name']}: {hit_z_m:.3f}m, rounded ref={qp['expected_h_m']}, delta={delta_cm:.2f}cm, actor={actor_hit}; exact native L06 witness still required")
                else:
                    print(f"  Hit {qp['name']}: Z = {hit_z_m:.3f} m, actor={actor_hit}")
            else:
                print(f"  Trace on {qp['name']} did not hit landscape via line trace")
                problems.append(f"{qp['name']}: collision trace did not hit Landscape")
            sampled["observed"] = True
        except Exception as exc:
            sampled["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            problems.append(f"{qp['name']}: collision diagnostic UNKNOWN: {sampled['error']}")
        sampled_points.append(sampled)

    dependencies = observe(lambda: native_dependencies(unreal, preparation))
    if dependencies["observed"]:
        problems.extend(dependencies["value"]["problems"])
    else:
        problems.append("Native package queries are UNKNOWN: " + dependencies["error"])
    report = {
        "status": "STRUCTURE_READBACK_INCOMPLETE" if problems else "STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING",
        "structural_readback_complete": not problems,
        "rounded_reference_warnings": rounded_reference_warnings,
        "geometry_accepted": False,
        "reasons": problems,
        "warning": "Collision raycasts are not raw Landscape height vertex readback.",
        "level": LEVEL_PATH,
        "total_landscape_actors": len(landscapes),
        "total_components": total_components,
        "expected_total_components": 4096,
        "components_pass": not structure_problems(landscape_data),
        "actor_quantization_step_cm": {
            name: actor_height_step_cm(z) if math.isfinite(z) and z > 0 else None
            for name, z in scales.items()
        },
        "native_component_properties_complete": bool(landscape_data) and all(
            all(row["actual_component_properties"][prop]["complete"]
                for prop in COMPONENT_FIELDS)
            for row in landscape_data
        ),
        "native_dependencies": dependencies,
        "dependency_closure_complete": False,
        "material_render_verified": False,
        "native_reopen_after_repair": "NOT_RUN",
        "source_height_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False,
        "transport_envelope": {
            "source_domain": "8000x8000 m, 16000x16000 cells at 0.5m spacing",
            "transport_envelope": "8128x8128 m, 4 tiles of 8129x8129 vertices (16257x16257 total envelope)",
            "padding_handling": "UNVERIFIED IN EXISTING UE MAP; original bake predated visibility-preserving transfer.",
            "quantization_unit_cm": None,
            "note": "Scale.Z differs by actor. Rounded source landmarks are not a true interpolated-height reference."
        },
        "landscapes": landscape_data,
        "sampled_heights": sampled_points,
    }
    return report


def main():
    import unreal

    project = plain_path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    try:
        preparation, preparation_identity, map_before, output = authenticated_preparation(project, os.environ)
    except Exception:
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
        raise
    report = {
        "schema_version": 2, "status": "STRUCTURE_READBACK_INCOMPLETE",
        "structural_readback_complete": False, "geometry_accepted": False,
        "source_height_interpolation_proved": False, "visibility_layer_proved_in_ue": False,
        "material_render_verified": False, "dependency_closure_complete": False,
        "source_head": preparation["source_head"], "project_root": str(project),
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "preparation_identity": preparation_identity, "map_before": map_before,
        "map_after": None, "candidate_map_unchanged": None,
        "reasons": [],
    }
    try:
        if not report["engine_version"].startswith("5.8.2-56702186"):
            raise RuntimeError("Unexpected native engine version")
        report.update(inspect_map(unreal, preparation))
    except Exception as exc:
        report["reasons"].append(f"Native reader failed: {type(exc).__name__}: {exc}")
        report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
        report["structural_readback_complete"] = False
    finally:
        try:
            report["map_after"] = file_identity(project / MAP_FILE, 3 * 1024**3)
            report["candidate_map_unchanged"] = report["map_after"] == map_before
            if not report["candidate_map_unchanged"]:
                report["reasons"].append("Candidate map bytes changed")
                report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
                report["structural_readback_complete"] = False
        except Exception as exc:
            report["reasons"].append("Final candidate map identity is UNKNOWN: " + str(exc))
            report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
            report["structural_readback_complete"] = False
        # Exclusive evidence output; no package save, bake, import or source write.
        payload = json.dumps(finite_json(report), indent=2, allow_nan=False)
        if len(payload.encode("utf-8")) > 8 * 1024**2:
            raise RuntimeError("Native readback exceeded its evidence bound")
        with output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        print(f"L07 structural readback: {report['status']}; geometry_accepted=false")
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


def finite_json(value):
    """Keep invalid native numbers explicit as null, with their recorded errors."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    return value

if __name__ == "__main__":
    main()
