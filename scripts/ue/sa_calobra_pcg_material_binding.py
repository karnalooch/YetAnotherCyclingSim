"""Isolated #365 Forge-on-mesh diagnostic helpers; no regional placement admission.

Caller owns the isolated Editor, package save/reload and proof admission. This
module never runs on import, opens a map, starts a process or edits source mesh.
Stage this module and the existing importer at their repository-relative paths.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

import unreal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ue.import_material_forge_variant import import_variant  # noqa: E402

DESTINATION = "/Game/Generated/YACS/PCG365Qualification"
SOURCE_MESH = "/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder"
DERIVED_MESH = DESTINATION + "/SM_Boulder_ForgeDiagnostic"
SOURCE_PINS = {
    "validation.json": "2da21368e9dd52a0528cfcf3926fa3f6464a287913186f660c13b44f8cb629fa",
    "provenance.json": "e05fc44a876959b0692d4bd3faf3c49e70ccaa4ed74d9b88a674a7e104a8cdf9",
}
CHANNELS = {
    "BaseColorTex": "BaseColor",
    "NormalTex": "Normal_DX",
    "ORMTex": "ORM",
    "DetailMasksTex": "DetailMasks",
}
WORLD_FUNCTION_ROOT = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
LIB = unreal.MaterialEditingLibrary
ROCK_RECIPE = "ROCK_APPEARANCE_V1"
ROCK_PREFIX = "PCG365_ROCK_V1:"


def rock_appearance_mode():
    path = project_root() / "qualification-sources.json"
    value = (
        json.loads(path.read_text(encoding="utf-8"))["forge"].get("rock_appearance")
        if path.exists()
        else None
    )
    require(value in (None, ROCK_RECIPE), "Unknown rock appearance recipe")
    return value


def rock_spec():
    """Fixed rock-only response; source textures retain their physical 4 m tile."""
    spec = {}
    for key, value in {
        "Gain": 0.82,
        "Fracture": 0.20,
        "Pore": 0.12,
        "Mineral": 0.10,
        "NormalStrength": 1.35,
    }.items():
        spec[key] = (
            "MaterialExpressionScalarParameter",
            {"parameter_name": "Rock" + key, "default_value": value},
        )
    for key, flags in {
        "R": (True, False, False),
        "G": (False, True, False),
        "B": (False, False, True),
        "NormalXY": (True, True, False),
        "NormalZ": (False, False, True),
    }.items():
        spec[key] = (
            "MaterialExpressionComponentMask",
            dict(zip(("r", "g", "b", "a"), (*flags, False))),
        )
    for key, value in {"One": 1.0, "Two": 2.0, "Zero": 0.0}.items():
        spec[key] = ("MaterialExpressionConstant", {"r": value})
    for key in (
        "FractureMul",
        "PoreMul",
        "MineralDouble",
        "MineralMul",
        "ColorGain",
        "ColorFinal",
        "NormalMul",
    ):
        spec[key] = ("MaterialExpressionMultiply", {})
    for key in ("MinusFracture", "MinusPore", "MineralCenter"):
        spec[key] = ("MaterialExpressionSubtract", {})
    spec.update(
        ColorAdd=("MaterialExpressionAdd", {}),
        ColorClamp=("MaterialExpressionClamp", {}),
        NormalAppend=("MaterialExpressionAppendVector", {}),
        NormalFinal=("MaterialExpressionNormalize", {}),
    )
    return spec


def rock_edges():
    return [
        ("detail", "XYZ Texture", "R", ""),
        ("detail", "XYZ Texture", "G", ""),
        ("detail", "XYZ Texture", "B", ""),
        ("R", "", "FractureMul", "A"),
        ("Fracture", "", "FractureMul", "B"),
        ("G", "", "PoreMul", "A"),
        ("Pore", "", "PoreMul", "B"),
        ("One", "", "MinusFracture", "A"),
        ("FractureMul", "", "MinusFracture", "B"),
        ("MinusFracture", "", "MinusPore", "A"),
        ("PoreMul", "", "MinusPore", "B"),
        ("B", "", "MineralDouble", "A"),
        ("Two", "", "MineralDouble", "B"),
        ("MineralDouble", "", "MineralCenter", "A"),
        ("One", "", "MineralCenter", "B"),
        ("MineralCenter", "", "MineralMul", "A"),
        ("Mineral", "", "MineralMul", "B"),
        ("MinusPore", "", "ColorAdd", "A"),
        ("MineralMul", "", "ColorAdd", "B"),
        ("ColorAdd", "", "ColorClamp", ""),
        ("Zero", "", "ColorClamp", "Min"),
        ("One", "", "ColorClamp", "Max"),
        ("base", "XYZ Texture", "ColorGain", "A"),
        ("Gain", "", "ColorGain", "B"),
        ("ColorGain", "", "ColorFinal", "A"),
        ("ColorClamp", "", "ColorFinal", "B"),
        ("normal_base", "", "NormalXY", ""),
        ("normal_base", "", "NormalZ", ""),
        ("NormalXY", "", "NormalMul", "A"),
        ("NormalStrength", "", "NormalMul", "B"),
        ("NormalMul", "", "NormalAppend", "A"),
        ("NormalZ", "", "NormalAppend", "B"),
        ("NormalAppend", "", "NormalFinal", ""),
    ]


def rock_sources(master):
    sources = {}
    for expression in LIB.get_material_expressions(master):
        if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall):
            textures = [
                item
                for item in LIB.get_inputs_for_material_expression(master, expression)
                if isinstance(item, unreal.MaterialExpressionTextureObjectParameter)
            ]
            require(len(textures) == 1, "Ambiguous rock projection texture")
            parameter = str(textures[0].get_editor_property("parameter_name"))
            key = {
                "BaseColorTex": "base",
                "DetailMasksTex": "detail",
                "NormalTex": "normal_projection",
                "ORMTex": "orm",
            }.get(parameter)
            require(
                key is not None and key not in sources, "Unexpected rock projection"
            )
            sources[key] = expression
    normals = [
        expression
        for expression in LIB.get_material_expressions(master)
        if isinstance(expression, unreal.MaterialExpressionNormalize)
        and list(LIB.get_inputs_for_material_expression(master, expression))
        == [sources["normal_projection"]]
    ]
    require(len(normals) == 1, "Missing original normal normalization")
    sources["normal_base"] = normals[0]
    return sources


def apply_rock_appearance(assets):
    master = unreal.load_asset(assets["master"])
    nodes = rock_sources(master)
    for key, (class_name, properties) in rock_spec().items():
        node = LIB.create_material_expression(master, getattr(unreal, class_name))
        require(node is not None, "Rock material node creation failed")
        node.set_editor_property("desc", ROCK_PREFIX + key)
        for field, value in properties.items():
            node.set_editor_property(field, value)
        nodes[key] = node
    for source, output, target, input_name in rock_edges():
        require(
            LIB.connect_material_expressions(
                nodes[source], output, nodes[target], input_name
            ),
            "Rock material edge failed: " + target,
        )
    for node, prop in (
        ("ColorFinal", unreal.MaterialProperty.MP_BASE_COLOR),
        ("NormalFinal", unreal.MaterialProperty.MP_NORMAL),
    ):
        require(
            LIB.connect_material_property(nodes[node], "", prop),
            "Rock material output failed",
        )
    require(not LIB.recompile_material(master), "Rock material compilation failed")
    LIB.update_material_instance(unreal.load_asset(assets["instance"]))


def rock_readback(master, instance):
    tagged = {}
    for node in LIB.get_material_expressions(master):
        description = str(node.get_editor_property("desc"))
        if description.startswith(ROCK_PREFIX):
            key = description.removeprefix(ROCK_PREFIX)
            require(key not in tagged, "Duplicate rock material node")
            tagged[key] = node
    mode = rock_appearance_mode()
    if mode is None:
        require(not tagged, "Unexpected opt-in rock graph")
        return {"recipe": "LEGACY_BASELINE", "physical_tile_cm": 400.0}
    require(set(tagged) == set(rock_spec()), "Rock material graph inventory differs")
    values = {}
    for key, (class_name, properties) in rock_spec().items():
        node = tagged[key]
        require(
            isinstance(node, getattr(unreal, class_name)),
            "Rock expression class differs",
        )
        for field, expected in properties.items():
            actual = node.get_editor_property(field)
            if field == "parameter_name":
                require(str(actual) == expected, "Rock parameter name differs")
            elif type(expected) is float:
                require(
                    math.isfinite(actual) and abs(actual - expected) <= 1e-6,
                    "Rock float32 scalar differs",
                )
            else:
                require(actual == expected, "Rock expression setting differs")
        if class_name == "MaterialExpressionScalarParameter":
            value = LIB.get_material_instance_scalar_parameter_value(
                instance,
                properties["parameter_name"],
                unreal.MaterialParameterAssociation.GLOBAL_PARAMETER,
            )
            require(
                math.isfinite(value)
                and abs(value - properties["default_value"]) <= 1e-6,
                "Effective rock scalar differs",
            )
            values[properties["parameter_name"]] = float(value)
    nodes = {**rock_sources(master), **tagged}
    expected_inputs = {}
    for source, _, target, input_name in rock_edges():
        names = list(LIB.get_material_expression_input_names(nodes[target]))
        # GetMaterialExpressionInputNames shortens native "Input" to NAME_None
        # (MaterialGraphNode.cpp:610); its reflected input remains index zero.
        index = names.index(input_name) if input_name not in ("", "Input") else 0
        expected_inputs.setdefault(target, [None] * len(names))[index] = nodes[source]
    for target, expected in expected_inputs.items():
        require(
            list(LIB.get_inputs_for_material_expression(master, nodes[target]))
            == expected,
            "Rock input topology differs: " + target,
        )
    for key, prop in (
        ("ColorFinal", unreal.MaterialProperty.MP_BASE_COLOR),
        ("NormalFinal", unreal.MaterialProperty.MP_NORMAL),
    ):
        require(
            LIB.get_material_property_input_node(master, prop) == nodes[key],
            "Rock output topology differs",
        )
    for prop, flags in (
        (unreal.MaterialProperty.MP_AMBIENT_OCCLUSION, [True, False, False, False]),
        (unreal.MaterialProperty.MP_ROUGHNESS, [False, True, False, False]),
    ):
        node = LIB.get_material_property_input_node(master, prop)
        require(
            isinstance(node, unreal.MaterialExpressionComponentMask)
            and [node.get_editor_property(k) for k in ("r", "g", "b", "a")] == flags
            and list(LIB.get_inputs_for_material_expression(master, node))
            == [nodes["orm"]],
            "Rock recipe changed original ORM response",
        )
    return {
        "recipe": mode,
        "physical_tile_cm": 400.0,
        "effective_scalars": values,
        "float32_readback_tolerance": 1e-6,
        "detail_semantics": "R fractures; G pores/pits; B mineral variation; artistic contrast only",
        "geometry_modified": False,
    }


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def project_root():
    root = Path(unreal.Paths.project_dir()).resolve(strict=True)
    require(
        root.is_relative_to(Path("D:/yacs/work/pcg365").resolve()),
        "Material binding is restricted to owned isolated PCG365 stages",
    )
    require(
        (root / "Pcg365Diagnostic.uproject").is_file(), "Unexpected isolated project"
    )
    return root


def package_file(object_path):
    package = object_path.split(".")[0]
    require(
        package.startswith("/Game/") and ".." not in package,
        "Unexpected package identity",
    )
    return project_root() / ("Content/" + package.removeprefix("/Game/") + ".uasset")


def file_identity(object_path):
    path = package_file(object_path)
    require(
        path.is_file() and path.stat().st_size > 128, "Missing/non-package saved bytes"
    )
    return {
        "path": str(path.relative_to(project_root())).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def source_identity(mesh):
    return {
        "package": file_identity(mesh.get_path_name()),
        "material_slots": [
            mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
            for i in range(len(mesh.static_materials))
        ],
    }


def verify_source(before):
    source = unreal.load_asset(SOURCE_MESH)
    require(isinstance(source, unreal.StaticMesh), "Source Boulder is not a StaticMesh")
    require(source_identity(source) == before, "Protected source Boulder changed")


def verify_variant(directory):
    directory = Path(directory).resolve(strict=True)
    for name, expected in SOURCE_PINS.items():
        require(
            sha(directory / name) == expected,
            "Pinned Forge source receipt drift: " + name,
        )
    validation = json.loads((directory / "validation.json").read_text(encoding="utf-8"))
    provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
    for value in (validation, provenance):
        require(
            value["family"] == "regional_limestone" and value["variant"] == "base",
            "Unexpected Forge variant",
        )
        require(
            value["world_semantics_generated"] is False
            and value["semantic_owner"] == "PCG/PCGEx",
            "Forge must not supply world semantics",
        )
    require(
        validation["status"] == "MAP_CHECKS_PASS_UE_REVIEW_PENDING",
        "Unvalidated Forge maps",
    )
    require(provenance["tile_metres"] == 4, "Pinned 4m tile required")
    files = dict(SOURCE_PINS)
    for channel in (*CHANNELS.values(), "Height"):
        entry = validation["maps"][channel]
        path = (directory / entry["path"]).resolve(strict=True)
        require(path.is_relative_to(directory), "Forge map escaped source root")
        require(sha(path) == entry["sha256"], "Forge map byte drift: " + channel)
        files[entry["path"]] = entry["sha256"]
    return {
        "family": "regional_limestone",
        "variant": "base",
        "files": files,
        "graph_sha256": provenance["graph_sha256"],
        "tile_metres": 4,
        "height_imported_or_displaced": False,
    }


def material_readback(assets):
    instance = unreal.load_asset(assets["instance"])
    master = unreal.load_asset(assets["master"])
    require(
        isinstance(instance, unreal.MaterialInstanceConstant)
        and isinstance(master, unreal.Material),
        "Missing native Forge material/instance",
    )
    require(
        instance.get_editor_property("parent") == master,
        "Forge instance parent differs",
    )
    appearance = rock_readback(master, instance)
    association = unreal.MaterialParameterAssociation.GLOBAL_PARAMETER
    tile = LIB.get_material_instance_scalar_parameter_value(
        instance, "TileSizeCm", association
    )
    require(
        math.isfinite(tile) and tile == 400.0, "Effective TileSizeCm differs from 400"
    )
    for parameter, channel in CHANNELS.items():
        texture = LIB.get_material_instance_texture_parameter_value(
            instance, parameter, association
        )
        require(
            isinstance(texture, unreal.Texture2D)
            and texture.get_path_name() == assets["textures"][channel],
            "Effective material texture differs: " + parameter,
        )
        require(
            texture.get_editor_property("srgb") is (channel == "BaseColor"),
            "Texture colour space differs: " + channel,
        )
    calls = [
        expression
        for expression in LIB.get_material_expressions(master)
        if isinstance(expression, unreal.MaterialExpressionMaterialFunctionCall)
    ]
    functions = []
    for call in calls:
        function = call.get_editor_property("material_function")
        require(function is not None, "Missing WorldAligned function")
        functions.append(function.get_path_name().split(".")[0])
        inputs = LIB.get_inputs_for_material_expression(master, call)
        scalars = [
            item
            for item in inputs
            if isinstance(item, unreal.MaterialExpressionScalarParameter)
        ]
        require(
            len(scalars) == 1
            and str(scalars[0].get_editor_property("parameter_name")) == "TileSizeCm"
            and scalars[0].get_editor_property("default_value") == 400.0,
            "WorldAligned TextureSize is not the pinned scalar",
        )
    require(
        sorted(functions)
        == sorted(
            [WORLD_FUNCTION_ROOT + "WorldAlignedTexture"] * 3
            + [WORLD_FUNCTION_ROOT + "WorldAlignedNormal"]
        ),
        "WorldAligned projection function inventory differs",
    )
    # Installed MaterialEditingLibrary.cpp:1148 reads the material input directly;
    # no active Material Editor lookup occurs in that implementation.
    require(
        LIB.get_material_property_input_node(
            master, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET
        )
        is None,
        "Forge master has connected WPO",
    )
    # Native Python denies access to the protected editor-only material inputs.
    # Keep this diagnostic binding separate from geometry qualification.
    require(
        master.get_editor_property("bEnableTessellation") is False,
        "Forge master enables Nanite tessellation",
    )
    geometry = {
        "status": "PENDING_EFFECTIVE_GEOMETRY_READBACK",
        "max_displacement_world_m": None,
    }
    try:
        # Installed 5.8.2 MaterialShared.cpp:635 excludes WPO/displacement from
        # inline-constant compilation; AttributeDefinitionMap.cpp:407 sets WPO
        # default to zero. Displacement default is 0.5, not zero. Confirm the
        # attributes path and instance tessellation override before bounding it.
        attributes = master.get_editor_property("bUseMaterialAttributes")
        overrides = instance.get_editor_property("base_property_overrides")
        override_tessellation = overrides.get_editor_property(
            "bOverride_bEnableTessellation"
        )
        require(attributes is False, "Material Attributes path is not qualified")
        require(
            override_tessellation is False,
            "Forge instance tessellation override is not qualified",
        )
        geometry = {
            "status": "SOURCE_AUDITED_ZERO_WPO_TESSELLATION_DISPLACEMENT_READBACK",
            "use_material_attributes": False,
            "wpo_default_world_m": [0.0, 0.0, 0.0],
            "displacement_connected": None,
            "displacement_root_readback": "UNAVAILABLE_PYTHON_ENUM",
            "displacement_default_scalar": 0.5,
            "instance_tessellation_override": False,
            "nanite_tessellation_enabled": False,
            "max_displacement_world_m": 0.0,
            "basis": "UE5.8.2 WPO fallback and tessellation compiler guard with loaded master/instance readback; not GPU parity or all-deformer proof",
        }
    except Exception as error:
        geometry["readback_error"] = str(error)
    return {
        "instance": instance.get_path_name(),
        "parent": master.get_path_name(),
        "TileSizeCm": float(tile),
        "projection": "native_world_aligned_4m",
        "world_aligned_functions": sorted(functions),
        "wpo_connected": False,
        "displacement_connected": None,
        "nanite_tessellation_enabled": False,
        "protected_constant_and_displacement_readback": "UNAVAILABLE",
        "max_displacement_world_m": None,
        "geometry_qualification": "PENDING_PROTECTED_INPUT_READBACK",
        "source_audited_geometry_readback": geometry,
        "shader_gpu_compilation_verified": False,
        "rock_appearance": appearance,
    }


def verify_binding(receipt, component=None):
    """Fresh read-only package/material/slot check; never reimports or repairs."""
    project_root()
    verify_source(receipt["source_mesh"])
    for entry in receipt.get("saved_packages", []):
        path = project_root() / entry["path"]
        require(
            path.resolve().is_relative_to(project_root()),
            "Saved package escaped project",
        )
        require(
            path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"],
            "Saved package bytes differ",
        )
    for entry in receipt.get("direct_package_dependencies", []):
        package = entry["package"]
        if package.startswith("/Script/"):
            continue  # Engine/module pin is authenticated by the owning launcher.
        path = (
            package_file(package)
            if package.startswith("/Game/")
            else (
                Path(unreal.Paths.engine_content_dir())
                / (package.removeprefix("/Engine/") + ".uasset")
            )
        )
        require(
            path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"],
            "Saved direct dependency bytes differ: " + package,
        )
    mesh = unreal.load_asset(receipt["derived_mesh"])
    require(
        isinstance(mesh, unreal.StaticMesh)
        and mesh.get_path_name().split(".")[0] == DERIVED_MESH,
        "Unexpected derived StaticMesh",
    )
    assets = receipt["forge_import"]["assets"]
    materials = material_readback(assets)
    require(
        len(mesh.static_materials) == receipt["slot_count"]
        and receipt["slot_count"] > 0,
        "Derived mesh slot inventory differs",
    )
    for index in range(receipt["slot_count"]):
        require(
            mesh.get_material(index).get_path_name() == assets["instance"],
            "Derived mesh material slot differs",
        )
    if component is not None:
        require(
            component.get_editor_property("static_mesh") == mesh,
            "Native component mesh differs",
        )
        for index in range(receipt["slot_count"]):
            require(
                component.get_material(index).get_path_name() == assets["instance"],
                "Native component effective material differs",
            )
    return {
        "status": "ISOLATED_NATIVE_MATERIAL_BINDING_READBACK",
        "derived_mesh": mesh.get_path_name(),
        "material": materials,
        "component_checked": component is not None,
        "placement": False,
        "qualification_status": "PENDING",
        "terrain_contact": "NOT_RUN",
        "visual_accepted": False,
        "performance_pass": False,
    }


def prepare_binding(variant_directory, code_sha):
    """Import once and duplicate only the staged Boulder, leaving source intact."""
    project_root()
    require(
        re.fullmatch("[0-9a-f]{40}", code_sha) is not None, "Exact code SHA required"
    )
    require(
        not unreal.EditorAssetLibrary.does_directory_exist(DESTINATION),
        "Preserve existing qualification assets; use a fresh isolated stage",
    )
    source_receipt = verify_variant(variant_directory)
    source = unreal.load_asset(SOURCE_MESH)
    require(isinstance(source, unreal.StaticMesh), "Source Boulder is not a StaticMesh")
    before = source_identity(source)
    instance, imported = import_variant(
        Path(variant_directory), DESTINATION + "/MaterialForge", False
    )
    if rock_appearance_mode() == ROCK_RECIPE:
        apply_rock_appearance(imported["assets"])
    mesh = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MESH, DERIVED_MESH)
    require(
        isinstance(mesh, unreal.StaticMesh) and mesh != source,
        "Distinct derived StaticMesh required",
    )
    count = len(mesh.static_materials)
    require(count > 0, "Source mesh has no material slot")
    for index in range(count):
        mesh.set_material(index, instance)
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "code_sha": code_sha,
        "status": "ISOLATED_MATERIAL_BINDING_UNSAVED",
        "source_mesh": before,
        "source_material": source_receipt,
        "forge_import": imported,
        "derived_mesh": mesh.get_path_name(),
        "slot_count": count,
        "placement": False,
        "qualified_assets": [],
        "terrain_contact": "NOT_RUN",
        "visual_accepted": False,
        "performance_pass": False,
    }
    receipt["readback"] = verify_binding(receipt)
    require(
        verify_variant(variant_directory) == source_receipt,
        "Forge source changed during import",
    )
    return receipt


def bind_component(component, receipt):
    """Caller supplies an owned diagnostic component in the isolated project."""
    project_root()
    require(
        isinstance(component, unreal.StaticMeshComponent),
        "Expected owned StaticMeshComponent",
    )
    mesh = unreal.load_asset(receipt["derived_mesh"])
    component.set_static_mesh(mesh)
    instance = unreal.load_asset(receipt["forge_import"]["assets"]["instance"])
    for index in range(receipt["slot_count"]):
        component.set_material(index, instance)
    return verify_binding(receipt, component)


def save_binding(receipt):
    """Save the explicit new asset inventory only; caller saves its own map."""
    verify_binding(receipt)
    assets = receipt["forge_import"]["assets"]
    paths = [
        *assets["textures"].values(),
        assets["master"],
        assets["instance"],
        receipt["derived_mesh"],
    ]
    for path in paths:
        require(
            path.startswith(DESTINATION + "/"), "Refuse save outside owned destination"
        )
        require(
            unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False),
            "Explicit asset save failed",
        )
    receipt["saved_packages"] = [file_identity(path) for path in paths]
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous([DESTINATION], force_rescan=True)
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False,
        include_hard_management_references=False,
    )
    dependency_names = set()
    queries = []
    for path in paths:
        package = path.split(".")[0]
        object_path = package + "." + package.rsplit("/", 1)[1]
        data = registry.get_asset_by_object_path(
            object_path, include_only_on_disk_assets=True
        )
        require(data.is_valid(), "Saved asset absent from disk registry: " + package)
        raw = registry.get_dependencies(package, options)
        names = [] if raw is None else sorted(str(name) for name in raw)
        queries.append(
            {
                "package": package,
                "status": "QUERY_UNAVAILABLE" if raw is None else "RETURNED",
                "references": names,
            }
        )
        dependency_names.update(names)
    # K2_GetDependencies returns bool + output array; Python's None is a failed
    # query, not proof that the package has no references. Independently checked
    # native slots/parent/texture parameters bind this minimum dependency set.
    verified = verify_binding(receipt)
    require(verified["material"]["parent"] == assets["master"], "Master binding drift")
    expected = {
        assets["master"].split(".")[0],
        assets["instance"].split(".")[0],
        *(path.split(".")[0] for path in assets["textures"].values()),
    }
    dependency_names.update(expected)
    receipt["direct_dependency_queries"] = queries
    receipt["dependency_query_status"] = (
        "PENDING_UNAVAILABLE_REGISTRY_QUERIES"
        if any(query["status"] == "QUERY_UNAVAILABLE" for query in queries)
        else "DIRECT_QUERIES_RETURNED_NOT_RECURSIVE_CLOSURE"
    )
    receipt["native_binding_dependency_packages"] = sorted(expected)
    dependencies = []
    for package in sorted(dependency_names):
        if package.startswith("/Script/"):
            dependencies.append({"package": package, "kind": "native_script_module"})
            continue
        if package.startswith("/Game/"):
            identity = file_identity(package)
            identity["package"] = package
        elif package.startswith("/Engine/"):
            path = Path(unreal.Paths.engine_content_dir()) / (
                package.removeprefix("/Engine/") + ".uasset"
            )
            require(path.is_file(), "Missing native engine dependency: " + package)
            identity = {
                "package": package,
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            }
        else:
            raise RuntimeError("Unexpected plugin dependency: " + package)
        dependencies.append(identity)
    receipt["direct_package_dependencies"] = dependencies
    receipt["dependency_scope"] = (
        "registry references plus independently checked mesh slots, MI parent and texture bindings; query failures explicit; not recursive engine closure"
    )
    receipt["status"] = "ISOLATED_MATERIAL_BINDING_SAVED_RENDER_PENDING"
    receipt["readback"] = verify_binding(receipt)
    return receipt
