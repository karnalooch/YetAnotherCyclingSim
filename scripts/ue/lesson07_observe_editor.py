"""Passive first observation of the already-open YACS Lesson07 editor.

Call collect() explicitly through the authenticated existing editor API. Import
and execution as __main__ are inert. This module does not load assets, refresh
material graphs, compile, collect garbage, save, capture, switch views or exit.
It returns data only; the coordinator owns evidence storage and native calls.

Reuses the traversal pattern in inspect_sa_calobra_material_projection.py and
read-only properties in repair_lesson07_materials.py. Public Epic Python 5.8
MaterialEditingLibrary, UnrealEditorSubsystem, EditorLoadingAndSavingUtils and
AutomationLibrary are capability references; the installed binding is recorded
by successful observations rather than assumed. Native pin/output/mask proof,
built array pixels and shader error/fallback status are deliberately unresolved.
"""

import json
import math
import ntpath
import os
from datetime import datetime, timezone


PROJECT = "D:/yacs/project"
PROJECT_FILE = PROJECT + "/YetAnotherCyclingSim.uproject"
ROOT = "/Game/Generated/YACS/Lesson07_Unified"
WORLD = ROOT + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07"
INSTANCE = ROOT + "/Materials/MI_Landscape_Instance_YACS.MI_Landscape_Instance_YACS"
MASTER = ROOT + "/Materials/M_Landscape_YACS.M_Landscape_YACS"
EXPECTED_ACTORS = {
    "SaCalobra_Unified_0_0",
    "SaCalobra_Unified_1_0",
    "SaCalobra_Unified_0_1",
    "SaCalobra_Unified_1_1",
}
EXPECTED_SCALARS = {
    "Global Normal Flatten": 1.0,
    "Global Colour Strength": 0.0,
    "Global Saturation": 0.0,
    "Global Brightness": 0.0,
    "Detail Brightness": 1.0,
    "Detail Tiling": 0.25,
    "Macro Tiling": 0.25,
    "Macro Texture Distance": 10000.0,
    "Global Specular Scale": 0.0,
    "Global AO Power": 1.0,
    "UV Distort": 4.0,
    "Noise_Scale": 0.0005,
}

# These bound observational work, not visual or geometry acceptance.
MAX_GRAPHS = 128
MAX_NODES = 8192

NODE_PROPERTIES = {
    "MaterialExpressionConstant": ("r",),
    "MaterialExpressionConstant2Vector": ("r", "g"),
    "MaterialExpressionConstant3Vector": ("constant",),
    "MaterialExpressionConstant4Vector": ("constant",),
    "MaterialExpressionScalarParameter": ("parameter_name", "default_value"),
    "MaterialExpressionVectorParameter": ("parameter_name", "default_value"),
    "MaterialExpressionStaticSwitchParameter": ("parameter_name", "default_value"),
    "MaterialExpressionStaticBool": ("value",),
    "MaterialExpressionTextureCoordinate": (
        "coordinate_index",
        "u_tiling",
        "v_tiling",
        "un_mirror_u",
        "un_mirror_v",
    ),
    "MaterialExpressionTextureSample": (
        "texture",
        "sampler_type",
        "sampler_source",
        "mip_value_mode",
    ),
    "MaterialExpressionTextureSampleParameter2D": (
        "parameter_name",
        "texture",
        "sampler_type",
        "sampler_source",
        "mip_value_mode",
    ),
    "MaterialExpressionTextureObjectParameter": (
        "parameter_name",
        "texture",
        "sampler_type",
    ),
    "MaterialExpressionAdd": ("const_a", "const_b"),
    "MaterialExpressionSubtract": ("const_a", "const_b"),
    "MaterialExpressionMultiply": ("const_a", "const_b"),
    "MaterialExpressionDivide": ("const_a", "const_b"),
    "MaterialExpressionPower": ("const_exponent",),
    "MaterialExpressionLinearInterpolate": ("const_a", "const_b", "const_alpha"),
    "MaterialExpressionComponentMask": ("r", "g", "b", "a"),
    "MaterialExpressionRotator": ("center_x", "center_y", "speed"),
    "MaterialExpressionNamedRerouteUsage": ("declaration",),
    "MaterialExpressionNamedRerouteDeclaration": ("name",),
    "MaterialExpressionFunctionInput": (
        "input_name",
        "input_type",
        "id",
        "sort_priority",
        "use_preview_value_as_default",
    ),
    "MaterialExpressionFunctionOutput": ("output_name", "id", "sort_priority"),
}


def _path(value):
    return value.get_path_name() if value is not None else None


def _normal_windows_path(value):
    return ntpath.normcase(ntpath.normpath(str(value)))


def _value(value):
    if isinstance(value, float):
        return _finite(value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if hasattr(value, "get_path_name"):
        return {"object_path": value.get_path_name()}
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    # Enum/Name/Guid representations stay labelled, not claimed as native bits.
    return {"python_type": type(value).__name__, "representation": str(value)}


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite observed numeric value")
    return number


def _observe(action):
    try:
        return {"observed": True, "value": action()}
    except Exception as error:
        return {
            "observed": False,
            "error_type": type(error).__name__,
            "error": str(error)[:600],
        }


def _properties(obj, names):
    return {
        name: _observe(lambda name=name: _value(obj.get_editor_property(name)))
        for name in names
    }


def _dirty(api):
    return {
        kind: _observe(
            lambda method=method: sorted(
                _path(item)
                for item in getattr(api.EditorLoadingAndSavingUtils, method)()
            )
        )
        for kind, method in (
            ("maps", "get_dirty_map_packages"),
            ("content", "get_dirty_content_packages"),
        )
    }


def _actor_snapshot(api):
    subsystem = api.get_editor_subsystem(api.EditorActorSubsystem)
    actors = [
        actor
        for actor in subsystem.get_all_level_actors()
        if isinstance(actor, api.LandscapeProxy)
    ]
    rows = []
    for actor in sorted(actors, key=lambda item: item.get_name()):
        location = actor.get_actor_location()
        rotation = actor.get_actor_rotation()
        scale = actor.get_actor_scale3d()
        rows.append(
            {
                "name": actor.get_name(),
                "path": actor.get_path_name(),
                "location_cm": [
                    _finite(value) for value in (location.x, location.y, location.z)
                ],
                "rotation_pitch_yaw_roll_deg": [
                    _finite(value)
                    for value in (rotation.pitch, rotation.yaw, rotation.roll)
                ],
                "scale": [_finite(value) for value in (scale.x, scale.y, scale.z)],
                "component_count": len(
                    actor.get_components_by_class(api.LandscapeComponent)
                ),
                "material": _observe(
                    lambda actor=actor: _path(
                        actor.get_editor_property("landscape_material")
                    )
                ),
                "hole_material": _observe(
                    lambda actor=actor: _path(
                        actor.get_editor_property("landscape_hole_material")
                    )
                ),
            }
        )
    return {
        "actors": rows,
        "names_match_expected": {row["name"] for row in rows} == EXPECTED_ACTORS,
        "component_count": sum(row["component_count"] for row in rows),
        "component_render_instances_inspected": False,
    }


def _camera(api, editor):
    def pose():
        result = editor.get_level_viewport_camera_info()
        if result is None:
            raise RuntimeError("No primary level viewport camera")
        location, rotation = result
        return {
            "location_cm": [
                _finite(value) for value in (location.x, location.y, location.z)
            ],
            "rotation_pitch_yaw_roll_deg": [
                _finite(value)
                for value in (rotation.pitch, rotation.yaw, rotation.roll)
            ],
        }

    def size():
        result = editor.get_level_viewport_size()
        if result is None:
            raise RuntimeError("No primary level viewport size")
        return [int(result.x), int(result.y)]

    return {
        "primary_viewport_pose": _observe(pose),
        "primary_viewport_size_pixels": _observe(size),
        "active_viewport_mode": _observe(
            lambda: str(api.AutomationLibrary.get_editor_active_viewport_view_mode())
        ),
        "primary_and_active_viewport_identity_match": None,
        "fov": {"observed": False, "reason": "No verified read-only FOV binding"},
        "exposure": {"observed": False, "reason": "Not read by first observation"},
    }


def _graph_snapshot(api, master):
    lib = api.MaterialEditingLibrary
    graphs, limits = {}, []
    node_count = 0

    def visit(owner, is_function=False):
        nonlocal node_count
        path = owner.get_path_name()
        if path in graphs:
            return
        if len(graphs) >= MAX_GRAPHS:
            limits.append({"kind": "graph_count", "unvisited": path})
            return
        graph = {"owner": path, "is_function": is_function, "nodes": []}
        graphs[path] = graph
        try:
            nodes = list(
                lib.get_material_function_expressions(owner)
                if is_function
                else lib.get_material_expressions(owner)
            )
        except Exception as error:
            graph["enumeration"] = {"observed": False, "error": str(error)[:600]}
            return
        graph["enumeration"] = {"observed": True, "count": len(nodes)}
        for node in nodes:
            if node_count >= MAX_NODES:
                limits.append({"kind": "node_count", "owner": path})
                return
            node_count += 1
            cls = node.get_class().get_name()
            row = {
                "path": node.get_path_name(),
                "name": node.get_name(),
                "class": cls,
                "input_names": _observe(
                    lambda node=node: [
                        str(item)
                        for item in lib.get_material_expression_input_names(node)
                    ]
                ),
                "input_types": _observe(
                    lambda node=node: [
                        int(item)
                        for item in lib.get_material_expression_input_types(node)
                    ]
                ),
                "output_names": _observe(
                    lambda node=node: [
                        str(item)
                        for item in lib.get_material_expression_output_names(node)
                    ]
                ),
                "properties": _properties(node, NODE_PROPERTIES.get(cls, ())),
            }
            # Preserve raw API arrays. No zip into pin records until installed
            # source confirms disconnected-slot/order semantics for that API.
            method = (
                "get_inputs_for_material_function_expression"
                if is_function
                else "get_inputs_for_material_expression"
            )
            row["producer_nodes_in_api_order"] = _observe(
                lambda node=node, method=method: [
                    _path(item) for item in getattr(lib, method)(owner, node)
                ]
            )
            graph["nodes"].append(row)
            if cls == "MaterialExpressionMaterialFunctionCall":
                try:
                    child = node.get_editor_property("material_function")
                    row["function"] = {"observed": True, "path": _path(child)}
                    if child is not None:
                        visit(child, is_function=True)
                except Exception as error:
                    row["function"] = {"observed": False, "error": str(error)[:600]}

    visit(master)
    return {
        "graphs": graphs,
        "observed_node_count": node_count,
        "limits_reached": limits,
        "enumeration_scope": "All direct nodes plus recursively referenced loaded functions",
        "material_output_reachability_verified": False,
        "connection_scope": "Raw producer arrays; not complete per-pin connection records",
        "input_array_alignment_verified": False,
        "selected_output_indices_observed": False,
        "connection_component_masks_observed": False,
        "function_call_guid_synchronization_verified": False,
        "graph_contract_pass": False,
    }


def _instance_snapshot(api, instance):
    lib = api.MaterialEditingLibrary
    names = list(lib.get_scalar_parameter_names(instance))
    scalars = {
        str(name): _observe(
            lambda name=name: _finite(
                lib.get_material_instance_scalar_parameter_value(instance, name)
            )
        )
        for name in names
    }
    textures = {}
    for name in lib.get_texture_parameter_names(instance):
        try:
            texture = lib.get_material_instance_texture_parameter_value(instance, name)
            row = {"observed": True, "path": _path(texture)}
            if texture is not None:
                row["class"] = texture.get_class().get_name()
                row["properties"] = _properties(
                    texture,
                    (
                        "srgb",
                        "compression_settings",
                        "filter",
                        "mip_gen_settings",
                        "address_x",
                        "address_y",
                        "adjust_brightness",
                        "adjust_saturation",
                        "adjust_hue",
                    ),
                )
                if isinstance(texture, api.Texture2DArray):
                    row["source_textures"] = _observe(
                        lambda texture=texture: [
                            _path(item)
                            for item in texture.get_editor_property("source_textures")
                        ]
                    )
                    row["built_slice_pixels_observed"] = False
            textures[str(name)] = row
        except Exception as error:
            textures[str(name)] = {"observed": False, "error": str(error)[:600]}
    return {
        "path": instance.get_path_name(),
        "scalars": scalars,
        "textures": textures,
        "parameter_association": "GLOBAL_PARAMETER (API default)",
        "raw_scalar_names": [str(name) for name in names],
        "duplicate_scalar_names": len(set(map(str, names))) != len(names),
    }


def _lookup_loaded(api, path):
    try:
        value = api.find_object(None, path, follow_redirectors=False)
        return value, {
            "observed": True,
            "path": _path(value),
            "found": value is not None,
        }
    except Exception as error:
        return None, {
            "observed": False,
            "error_type": type(error).__name__,
            "error": str(error)[:600],
        }


def _validation(result):
    """Name deviations/unknowns; never promote metadata into material proof."""
    checks = {}

    def check(name, observed, actual, expected, equal=None):
        matches = (
            (actual == expected if equal is None else equal(actual, expected))
            if observed
            else None
        )
        checks[name] = {
            "status": ("MATCH" if matches else "MISMATCH")
            if observed
            else "UNAVAILABLE",
            "actual": actual if observed else None,
            "expected": expected,
        }

    actors = result["actors"].get("value", {})
    actor_observed = result["actors"].get("observed") is True
    check("landscape_names", actor_observed, actors.get("names_match_expected"), True)
    check("component_count", actor_observed, actors.get("component_count"), 4096)
    for row in actors.get("actors", []):
        check(row["name"] + ".component_count", True, row["component_count"], 1024)
        binding = row["material"]
        check(
            row["name"] + ".material",
            binding.get("observed") is True,
            binding.get("value"),
            INSTANCE,
        )
    parent = result.get("instance_parent", {})
    check(
        "instance_parent", parent.get("observed") is True, parent.get("value"), MASTER
    )
    scalars = result.get("instance", {}).get("value", {}).get("scalars", {})
    for name, expected in EXPECTED_SCALARS.items():
        value = scalars.get(name, {})
        check(
            "scalar." + name,
            value.get("observed") is True,
            value.get("value"),
            expected,
            equal=lambda actual, baseline: abs(actual - baseline) <= 1e-6,
        )
    check(
        "dirty_sets_equal",
        result["dirty_sets_equal"] is not None,
        result["dirty_sets_equal"],
        True,
    )
    graph_observation = result.get("graph", {})
    graph = graph_observation.get("value", {})
    references = []
    for owner in graph.get("graphs", {}).values():
        for node in owner.get("nodes", []):
            path = node.get("function", {}).get("path") or ""
            if "/TextureVariation." in path or "/MF_YACS_ArrayVariation" in path:
                references.append({"node": node["path"], "function": path})
    unavailable = []

    def walk(value, path):
        if isinstance(value, dict):
            if value.get("observed") is False:
                unavailable.append(path)
            for name, child in value.items():
                walk(child, path + "." + str(name))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path + "[" + str(index) + "]")

    walk(result, "report")
    return {
        "baseline_checks": checks,
        "scope": "Metadata comparison with retained recovery baseline; not saved-byte or visual proof",
        "scalar_comparison_absolute_tolerance": 1e-6,
        "rejected_variation_references_in_enumerated_nodes": references,
        "variation_absence_proved": False,
        "graph_truncation": graph.get("limits_reached")
        if graph_observation.get("observed")
        else None,
        "unavailable_observation_count": len(unavailable),
        "unavailable_observation_paths_first_128": unavailable[:128],
        "visual_or_native_graph_acceptance": False,
    }


def collect(api=None):
    """Return passive observations, rejecting another project/world first."""
    if api is None:
        import unreal as api

    project = api.Paths.convert_relative_path_to_full(api.Paths.project_dir())
    project_file = api.Paths.convert_relative_path_to_full(
        api.Paths.get_project_file_path()
    )
    if _normal_windows_path(project) != _normal_windows_path(
        PROJECT
    ) or _normal_windows_path(project_file) != _normal_windows_path(PROJECT_FILE):
        raise RuntimeError(
            "Wrong active project; no asset or actor inspection performed"
        )
    editor = api.get_editor_subsystem(api.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name() != WORLD:
        raise RuntimeError(
            "Wrong active EditorWorld; no asset or actor inspection performed"
        )

    result = {
        "status": "OBSERVED_PARTIAL_DIAGNOSIS_NOT_ACCEPTANCE",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "project": project,
        "project_file": project_file,
        "world": world.get_path_name(),
        "engine_version": _observe(lambda: api.SystemLibrary.get_engine_version()),
        "process_creation_and_executable": {
            "observed": False,
            "reason": "Coordinator must correlate external process readback",
        },
        "dirty_before": _dirty(api),
        "actors": _observe(lambda: _actor_snapshot(api)),
        "camera": _camera(api, editor),
    }
    # Explicit no-redirect loaded-object lookup: never load a package as fallback.
    instance, instance_lookup = _lookup_loaded(api, INSTANCE)
    master, master_lookup = _lookup_loaded(api, MASTER)
    result["loaded_assets"] = {"instance": instance_lookup, "master": master_lookup}
    if instance is not None:
        result["instance_parent"] = _observe(
            lambda: _path(instance.get_editor_property("parent"))
        )
        result["instance"] = _observe(lambda: _instance_snapshot(api, instance))
    else:
        result["instance"] = {
            "observed": False,
            "reason": (
                "Expected instance not loaded"
                if instance_lookup["observed"]
                else "Loaded instance lookup unavailable"
            ),
        }
    if master is not None:
        result["master_properties"] = _properties(
            master,
            (
                "blend_mode",
                "use_material_attributes",
                "tangent_space_normal",
                "enable_tessellation",
            ),
        )
        result["graph"] = _observe(lambda: _graph_snapshot(api, master))
    else:
        result["graph"] = {
            "observed": False,
            "reason": (
                "Expected master not loaded"
                if master_lookup["observed"]
                else "Loaded master lookup unavailable"
            ),
        }
    result["dirty_after"] = _dirty(api)
    dirty_observed = all(
        section[kind]["observed"]
        for section in (result["dirty_before"], result["dirty_after"])
        for kind in ("maps", "content")
    )
    result["dirty_sets_equal"] = (
        result["dirty_before"] == result["dirty_after"] if dirty_observed else None
    )
    result["limitations"] = {
        "mutating_apis_requested": False,
        "asset_loads_requested": False,
        "disk_asset_hashes_observed": False,
        "native_pin_contract_verified": False,
        "shader_errors_observed": False,
        "fallback_status_observed": False,
        "compilation_state_observed": False,
        "built_array_pixels_observed": False,
        "new_captures": False,
        "visual_acceptance": False,
        "performance_pass": False,
    }
    result["validation"] = _validation(result)
    return result


def collect_json():
    """Convenience return value for transports expecting text; no printing/writes."""
    return json.dumps(collect(), ensure_ascii=True, allow_nan=False)
