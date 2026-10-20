"""Bounded L07 material audit/repair in the existing isolated consumer.

Run AUDIT first, then APPLY with YACS_L07_MATERIAL_AUDIT and its SHA256.
APPLY saves only a local derivative master and the existing MI. REFRESH_MAP is
separately explicit: back up and load the existing isolated L07 map, refresh its
serialized grass caches through the native helper, prove all heightmap bytes
unchanged, then save that same map. No terrain generation, texture import or
shared Pegasus asset mutation is performed. AUDIT never loads or saves a map.

API authority: installed UE 5.8 MaterialEditingLibrary.h; Epic Python
MaterialEditingLibrary; SideFX Unreal landscape/basics (visibility).
The original Pegasus shader remains the surface recipe. Removing its optional
grass output is the explicit YACS terrain-only adaptation, not a replacement
surface shader or an import of the tutorial's vegetation.

The existing l07_visibility_material_author.py authors a separate minimal hole
material. It cannot preserve this Pegasus Material Attributes surface or remove
its inherited grass output. This adapter instead retains the original graph and
uses the existing Epic opacity override function on the main landscape material.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = "/Game/Generated/YACS/Lesson07_Unified"
MASTER = "/Game/PegasusDemo/Materials/Landscape/M_Pegasus_Landscape_Master"
DERIVATIVE = ROOT + "/Materials/M_Landscape_YACS"
INSTANCE = ROOT + "/Materials/MI_Landscape_Instance_YACS"
MAP = ROOT + "/L_SaCalobra_Lesson07"
CLASSES = ("Grass", "Grass2", "Sand", "Cliffs", "Scree")
OPACITY_OVERRIDE = "/Engine/Functions/MaterialLayerFunctions/MatLayerBlend_OverrideOpacityMask"


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package_file(project, package, suffix=".uasset"):
    if not package.startswith("/Game/"):
        raise ValueError("Only explicit Game packages are permitted")
    return project / "Content" / (package[6:] + suffix)


def inventory(project):
    paths = []
    for relative in ("Generated/YACS/Lesson07_Unified", "PegasusDemo/Materials"):
        paths.extend((project / "Content" / relative).rglob("*.uasset"))
        paths.extend((project / "Content" / relative).rglob("*.umap"))
    return {str(p.relative_to(project)): sha256(p) for p in sorted(paths)}


def validate_audit(audit, project, before):
    if audit.get("status") != "AUDIT_COMPLETE":
        raise RuntimeError("A completed prior AUDIT is required")
    if audit.get("project") != str(project) or audit.get("files") != before:
        raise RuntimeError("Project or asset bytes changed since AUDIT")
    if audit["material"]["use_material_attributes"]:
        if not audit["material"].get("attributes_node"):
            raise RuntimeError("Material Attributes require a separately inspected opacity adaptation")
        function = audit.get("opacity_override_function") or {}
        names = {n["input_name"] for n in function.get("expressions", []) if n["input_name"]}
        if function.get("path") != OPACITY_OVERRIDE or names != {"Material", "Mask", "NewOpacityMask"}:
            raise RuntimeError("Opacity override function pins were not authenticated")
    if audit.get("instance_blend_override", {}).get("enabled"):
        raise RuntimeError("Existing MI blend override requires separate inspection")
    if audit["instance_parent"] not in (MASTER, DERIVATIVE):
        raise RuntimeError("Unexpected existing MI parent; preserve inheritance")


def object_path(obj):
    return obj.get_path_name().split(".", 1)[0] if obj is not None else None


def displacement_settings(material):
    result = {}
    for key in ("enable_tessellation", "displacement_scaling", "max_world_position_offset_displacement"):
        try:
            value = material.get_editor_property(key)
            result[key] = {"observed": True, "value": value if isinstance(value, (bool, float, int)) else str(value)}
        except Exception as error:
            result[key] = {"observed": False, "error": str(error)}
    return result


def visibility_contract(snapshot):
    """Validate saved graph observations, independently of authoring calls."""
    nodes = {node["name"]: node for node in snapshot["expressions"]}
    terminal = nodes.get(snapshot.get("attributes_node"), {})
    inputs = dict(zip(terminal.get("input_names", []), terminal.get("inputs", [])))
    material = nodes.get(inputs.get("Material"), {})
    visibility = nodes.get(inputs.get("NewOpacityMask"), {})
    mask = nodes.get(inputs.get("Mask"), {})
    checks = {
        "masked": "BLEND_MASKED" in snapshot["blend_mode"],
        "no_grass_output": not any(n["class"] == "MaterialExpressionLandscapeGrassOutput"
                                   for n in nodes.values()),
        "attributes_override": terminal.get("material_function") == OPACITY_OVERRIDE,
        "original_surface_terminal_preserved": material.get("name") == "MaterialExpressionSetMaterialAttributes_9",
        "visibility_input": visibility.get("class") == "MaterialExpressionLandscapeVisibilityMask",
        "full_override_mask": mask.get("class") == "MaterialExpressionConstant"
        and mask.get("properties", {}).get("r") == 1.0,
    }
    return {"checks": checks, "graph_contract_pass": all(checks.values()),
            "landscape_visibility_data_proved": False, "render_proved": False}


def material_snapshot(unreal, material):
    lib = unreal.MaterialEditingLibrary
    nodes = list(lib.get_material_expressions(material))
    expressions = []
    for node in nodes:
        row = {"name": node.get_name(), "class": node.get_class().get_name()}
        row["input_names"] = [str(name) for name in lib.get_material_expression_input_names(node)]
        properties = {}
        fields = {
            "MaterialExpressionConstant": ("r",),
            "MaterialExpressionConstant2Vector": ("r", "g"),
            "MaterialExpressionScalarParameter": ("parameter_name", "default_value"),
            "MaterialExpressionStaticSwitchParameter": ("parameter_name", "default_value"),
            "MaterialExpressionVectorParameter": ("parameter_name", "default_value"),
            "MaterialExpressionTextureSample": ("texture", "sampler_type", "sampler_source"),
            "MaterialExpressionRotator": ("center_x", "center_y", "speed"),
            "MaterialExpressionTextureObjectParameter": ("parameter_name",),
            "MaterialExpressionTextureSampleParameter2D": ("parameter_name",),
            "MaterialExpressionAdd": ("const_a", "const_b"),
            "MaterialExpressionSubtract": ("const_a", "const_b"),
            "MaterialExpressionMultiply": ("const_a", "const_b"),
            "MaterialExpressionDivide": ("const_a", "const_b"),
            "MaterialExpressionComponentMask": ("r", "g", "b", "a"),
            "MaterialExpressionNamedRerouteUsage": ("declaration",),
            "MaterialExpressionNamedRerouteDeclaration": ("name",),
        }.get(row["class"], ())
        for field in fields:
            try:
                value = node.get_editor_property(field)
                if isinstance(value, unreal.LinearColor):
                    value = [value.r, value.g, value.b, value.a]
                elif isinstance(value, unreal.Object):
                    value = value.get_path_name() if field == "texture" else value.get_name()
                elif not isinstance(value, (str, float, int, bool, type(None))):
                    value = str(value)
                properties[field] = value
            except Exception as error:
                properties[field + "_unavailable"] = str(error)
        row["properties"] = properties
        if row["class"] == "MaterialExpressionLandscapeGrassOutput":
            row["grass_types"] = [
                object_path(item.get_editor_property("grass_type"))
                for item in node.get_editor_property("grass_types")
            ]
        if row["class"] == "MaterialExpressionMaterialFunctionCall":
            row["material_function"] = object_path(node.get_editor_property("material_function"))
            row["input_names"] = [str(name) for name in lib.get_material_expression_input_names(node)]
        # Record graph topology needed for UV inspection, without changing pins.
        row["inputs"] = [
            value.get_name() if value is not None else None
            for value in lib.get_inputs_for_material_expression(material, node)
        ]
        expressions.append(row)
    opacity = lib.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_OPACITY_MASK
    )
    attributes_property = getattr(unreal.MaterialProperty, "MP_MATERIAL_ATTRIBUTES", None)
    attributes = (lib.get_material_property_input_node(material, attributes_property)
                  if attributes_property is not None else None)
    return {
        "path": object_path(material),
        "displacement_settings": displacement_settings(material),
        "blend_mode": str(material.get_editor_property("blend_mode")),
        "use_material_attributes": bool(material.get_editor_property("use_material_attributes")),
        "opacity_node": None if opacity is None else {
            "name": opacity.get_name(), "class": opacity.get_class().get_name()
        },
        "attributes_property_exposed": attributes_property is not None,
        "attributes_node": None if attributes is None else attributes.get_name(),
        "expressions": expressions,
    }


def texture_snapshot(unreal, instance):
    result = {}
    for name in ("Terrain IDmap", "Terrain Colour", "Colour Atlas", "Normal Atlas", "Masks Atlas"):
        texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(
            instance, name
        )
        if texture is None:
            raise RuntimeError("Missing bound texture: " + name)
        row = {"path": object_path(texture), "class": texture.get_class().get_name()}
        for key in ("srgb", "compression_settings", "filter", "mip_gen_settings"):
            row[key] = str(texture.get_editor_property(key))
        if isinstance(texture, unreal.Texture2DArray):
            row["source_textures"] = [
                object_path(item) for item in texture.get_editor_property("source_textures")
            ]
            role = name.split()[0]
            expected = [ROOT + f"/Textures/Slices/T_{label}_{role}" for label in CLASSES]
            row["five_class_order_matches"] = row["source_textures"] == expected
        result[name] = row
    return result


def apply_material(unreal, project, instance, audit, output):
    lib = unreal.MaterialEditingLibrary
    backup = output.parent / (output.stem + "-backup")
    backup.mkdir(parents=True, exist_ok=False)
    for package in (MASTER, INSTANCE, DERIVATIVE):
        source = package_file(project, package)
        if source.is_file():
            shutil.copy2(source, backup / source.name)
    (backup / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    material = unreal.load_asset(DERIVATIVE)
    if material is not None and audit["instance_parent"] != DERIVATIVE:
        raise RuntimeError("Unbound derivative already exists; inspect it before reuse")
    if material is None:
        material = unreal.EditorAssetLibrary.duplicate_asset(MASTER, DERIVATIVE)
    if not isinstance(material, unreal.Material):
        raise RuntimeError("Derivative is not a Material")
    nodes = list(lib.get_material_expressions(material))
    for node in nodes:
        if node.get_class().get_name() == "MaterialExpressionLandscapeGrassOutput":
            lib.delete_material_expression(material, node)
    opacity = lib.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_OPACITY_MASK
    )
    use_attributes = bool(material.get_editor_property("use_material_attributes"))
    if use_attributes:
        terminal = lib.get_material_property_input_node(
            material, unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES
        )
        existing_override = (
            isinstance(terminal, unreal.MaterialExpressionMaterialFunctionCall)
            and object_path(terminal.get_editor_property("material_function")) == OPACITY_OVERRIDE
        )
        if existing_override:
            raise RuntimeError("Derivative already has opacity override; use fresh AUDIT to verify, not reapply")
        if terminal is None:
            raise RuntimeError("Missing Material Attributes terminal")
        visibility = lib.create_material_expression(
            material, unreal.MaterialExpressionLandscapeVisibilityMask, -450, 0
        )
        override = lib.create_material_expression(
            material, unreal.MaterialExpressionMaterialFunctionCall, -250, 0
        )
        override.set_editor_property("material_function", unreal.load_asset(OPACITY_OVERRIDE))
        full_mask = lib.create_material_expression(
            material, unreal.MaterialExpressionConstant, -450, 200
        )
        full_mask.set_editor_property("r", 1.0)
        for source, pin in ((terminal, "Material"), (visibility, "NewOpacityMask"),
                            (full_mask, "Mask")):
            if not lib.connect_material_expressions(source, "", override, pin):
                raise RuntimeError("Could not connect authenticated override input: " + pin)
        if not lib.connect_material_property(
            override, "Blended Material", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES
        ):
            raise RuntimeError("Could not connect opacity override to Material Attributes")
        observed = list(lib.get_inputs_for_material_expression(material, override))
        names = [str(name) for name in lib.get_material_expression_input_names(override)]
        bindings = dict(zip(names, observed))
        if (bindings.get("Material") != terminal or bindings.get("NewOpacityMask") != visibility
                or bindings.get("Mask") != full_mask):
            raise RuntimeError("Attribute override wiring did not read back")
    elif opacity is not None and not isinstance(opacity, unreal.MaterialExpressionLandscapeVisibilityMask):
        raise RuntimeError("Existing opacity graph is not direct visibility; refusing to replace")
    elif opacity is None:
        matches = [n for n in lib.get_material_expressions(material)
                   if isinstance(n, unreal.MaterialExpressionLandscapeVisibilityMask)]
        if len(matches) > 1:
            raise RuntimeError("Ambiguous existing visibility expressions")
        opacity = matches[0] if matches else lib.create_material_expression(
            material, unreal.MaterialExpressionLandscapeVisibilityMask, -450, 0
        )
        if not lib.connect_material_property(opacity, "", unreal.MaterialProperty.MP_OPACITY_MASK):
            raise RuntimeError("Could not connect visibility to Opacity Mask")
    material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    lib.recompile_material(material)
    snapshot = material_snapshot(unreal, material)
    before_nodes = {n["name"]: n["class"] for n in audit["material"]["expressions"]
                    if n["class"] != "MaterialExpressionLandscapeGrassOutput"}
    after_nodes = {n["name"]: n["class"] for n in snapshot["expressions"]}
    if any(after_nodes.get(name) != kind for name, kind in before_nodes.items()):
        raise RuntimeError("Non-grass surface expressions changed unexpectedly")
    if any(n["class"] == "MaterialExpressionLandscapeGrassOutput"
           for n in snapshot["expressions"]):
        raise RuntimeError("Grass output remained after bounded deletion")
    if not use_attributes and snapshot["opacity_node"]["class"] != "MaterialExpressionLandscapeVisibilityMask":
        raise RuntimeError("Visibility connection did not read back")
    if not unreal.EditorAssetLibrary.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError("Derivative save failed; backup retained")
    lib.set_material_instance_parent(instance, material)
    lib.update_material_instance(instance)
    if object_path(instance.get_editor_property("parent")) != DERIVATIVE:
        raise RuntimeError("MI parent did not read back")
    if not unreal.EditorAssetLibrary.save_loaded_asset(instance, only_if_is_dirty=False):
        raise RuntimeError("MI save failed; backup retained")
    return snapshot


def prior_receipt(project, before):
    path = Path(os.environ["YACS_L07_MATERIAL_AUDIT"])
    if sha256(path) != os.environ["YACS_L07_MATERIAL_AUDIT_SHA256"]:
        raise RuntimeError("Prior receipt hash mismatch")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("project") != str(project) or receipt.get("files_after") != before:
        raise RuntimeError("Prior receipt project or physical assets are stale")
    if receipt.get("status") not in ("AUDIT_COMPLETE", "APPLIED_REOPEN_AND_RENDER_PENDING"):
        raise RuntimeError("Prior receipt did not complete material verification")
    return receipt


def refresh_map(unreal, project, output, result, before):
    """Refresh serialized grass caches only; the parent owns native execution."""
    prior_receipt(project, before)
    if result["instance_parent"] != DERIVATIVE or not result["visibility_graph_contract"]["graph_contract_pass"]:
        raise RuntimeError("Verified derivative material is required before map refresh")
    if result["instance_blend_override"]["enabled"]:
        raise RuntimeError("MI blend override was not approved")
    map_file = package_file(project, MAP, ".umap")
    if shutil.disk_usage(project).free < map_file.stat().st_size + 30 * 1024**3:
        raise RuntimeError("Map backup must preserve the 30 GiB free-space reserve")
    backup = output.parent / (output.stem + "-backup")
    backup.mkdir(parents=True, exist_ok=False)
    backup_map = backup / map_file.name
    shutil.copy2(map_file, backup_map)
    if sha256(backup_map) != before[str(map_file.relative_to(project))]:
        raise RuntimeError("Existing map backup identity mismatch")
    result["map_backup"] = str(backup_map)
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    if world is None or object_path(world) != MAP:
        raise RuntimeError("The exact existing L07 world did not load")
    actors = [actor for actor in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem).get_all_level_actors()
        if isinstance(actor, unreal.LandscapeProxy)]
    if len(actors) != 4:
        raise RuntimeError("Existing L07 requires exactly four Landscape actors")
    if any(object_path(actor.get_editor_property("landscape_material")) != INSTANCE for actor in actors):
        raise RuntimeError("Existing actor material binding mismatch")
    native = unreal.YacsLandscapeMeshDiagnosticLibrary
    result["heightmaps_before"] = json.loads(native.read_lesson07_heightmap_hashes())
    validate_height_snapshot(result["heightmaps_before"])
    result["grass_refresh"] = json.loads(native.refresh_lesson07_grass_caches())
    validate_refresh(result["grass_refresh"])
    result["heightmaps_after"] = json.loads(native.read_lesson07_heightmap_hashes())
    validate_height_snapshot(result["heightmaps_after"])
    if result["heightmaps_before"] != result["heightmaps_after"]:
        raise RuntimeError("Whole heightmap content or identity changed; existing map not saved")
    result["whole_heightmaps_unchanged"] = True
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("Existing map save failed; authenticated backup retained")
    result["map_saved_after_cache_refresh"] = True
    result["status"] = "MAP_CACHES_REFRESHED_REOPEN_PENDING"


def validate_height_snapshot(snapshot):
    if (snapshot.get("success") is not True or snapshot.get("component_count") != 4096
            or not snapshot.get("textures")):
        raise RuntimeError("Complete native whole-heightmap hashes are required")


def validate_refresh(snapshot):
    if (snapshot.get("success") is not True or snapshot.get("actor_count") != 4
            or snapshot.get("component_count") != 4096
            or snapshot.get("grass_type_reference_count_after") != 0):
        raise RuntimeError("Native grass cache refresh was incomplete; existing map not saved")


def main():
    import unreal

    mode = os.environ.get("YACS_L07_MATERIAL_MODE", "AUDIT")
    output = Path(os.environ["YACS_L07_MATERIAL_REPORT"]).resolve()
    project = Path(unreal.Paths.get_project_file_path()).resolve().parent
    result = {"status": "STARTED", "mode": mode, "project": str(project),
              "geometry_accepted": False, "render_verified": False,
              "fresh_reopen_verified": False}
    before = None
    try:
        if mode not in ("AUDIT", "APPLY", "REFRESH_MAP"):
            raise RuntimeError("Only AUDIT/APPLY/REFRESH_MAP are supported")
        if mode != "AUDIT" and Path("D:/yacs/work").resolve() not in project.parents:
            raise RuntimeError("Mutation requires the isolated existing work project")
        if not package_file(project, MAP, ".umap").is_file():
            raise RuntimeError("Expected existing L07 map is missing")
        before = inventory(project)
        result["files"] = before
        instance = unreal.load_asset(INSTANCE)
        parent = instance.get_editor_property("parent")
        result["instance_parent"] = object_path(parent)
        overrides = instance.get_editor_property("base_property_overrides")
        result["instance_blend_override"] = {
            "enabled": bool(overrides.get_editor_property("override_blend_mode")),
            "blend_mode": str(overrides.get_editor_property("blend_mode")),
        }
        if not isinstance(parent, unreal.Material):
            raise RuntimeError("Inspect unexpected MI parent chain before adapting")
        result["material"] = material_snapshot(unreal, parent)
        result["visibility_graph_contract"] = visibility_contract(result["material"])
        lib = unreal.MaterialEditingLibrary
        result["instance_scalars"] = {
            name: float(lib.get_material_instance_scalar_parameter_value(instance, name))
            for name in sorted({
                node["properties"]["parameter_name"]
                for node in result["material"]["expressions"]
                if node["class"] == "MaterialExpressionScalarParameter"
                and "parameter_name" in node["properties"]
            })
        }
        result["instance_static_switches"] = {
            name: bool(lib.get_material_instance_static_switch_parameter_value(instance, name))
            for name in sorted({
                node["properties"]["parameter_name"]
                for node in result["material"]["expressions"]
                if node["class"] == "MaterialExpressionStaticSwitchParameter"
                and "parameter_name" in node["properties"]
            })
        }
        offset = lib.get_material_instance_vector_parameter_value(instance, "Offset")
        result["instance_offset"] = [offset.r, offset.g, offset.b, offset.a]
        function = unreal.load_asset(OPACITY_OVERRIDE)
        result["opacity_override_function"] = {
            "path": object_path(function),
            "expressions": [{
                "name": node.get_name(), "class": node.get_class().get_name(),
                "input_name": str(node.get_editor_property("input_name"))
                if isinstance(node, unreal.MaterialExpressionFunctionInput) else None,
                "output_name": str(node.get_editor_property("output_name"))
                if isinstance(node, unreal.MaterialExpressionFunctionOutput) else None,
            } for node in unreal.MaterialEditingLibrary.get_material_function_expressions(function)]
        } if function is not None else None
        result["textures"] = texture_snapshot(unreal, instance)
        if mode == "APPLY":
            audit_file = Path(os.environ["YACS_L07_MATERIAL_AUDIT"])
            if sha256(audit_file) != os.environ["YACS_L07_MATERIAL_AUDIT_SHA256"]:
                raise RuntimeError("Prior AUDIT receipt hash mismatch")
            audit = json.loads(audit_file.read_text(encoding="utf-8"))
            validate_audit(audit, project, before)
            result["material_after"] = apply_material(unreal, project, instance, audit, output)
            result["textures_after"] = texture_snapshot(unreal, instance)
            if result["textures_after"] != result["textures"]:
                raise RuntimeError("Texture bindings/settings changed unexpectedly")
        if mode == "REFRESH_MAP":
            refresh_map(unreal, project, output, result, before)
        else:
            result["status"] = "AUDIT_COMPLETE" if mode == "AUDIT" else "APPLIED_REOPEN_AND_RENDER_PENDING"
    except Exception as error:
        result["status"] = "FAILED"
        result["error"] = str(error)
        raise
    finally:
        if before is not None:
            after = inventory(project)
            result["files_after"] = after
            changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
            allowed = {str(package_file(project, p).relative_to(project))
                       for p in (DERIVATIVE, INSTANCE)} if mode == "APPLY" else set()
            if mode == "REFRESH_MAP":
                allowed = {str(package_file(project, MAP, ".umap").relative_to(project))}
            result["changed_files"] = sorted(changed)
            result["protected_files_unchanged"] = not (set(changed) - allowed)
            if not result["protected_files_unchanged"]:
                result["status"] = "FAILED_PROTECTED_ASSET_CHANGED"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


if __name__ == "__main__":
    main()
