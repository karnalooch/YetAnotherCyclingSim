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
    # MP_Displacement is hidden from Python's enum. Its mirrored UPROPERTY input
    # is available through the installed Material.h editor-only data instead.
    editor_data = master.get_editor_property("editor_only_data")
    wpo = editor_data.get_editor_property("world_position_offset")
    if wpo.get_editor_property("use_constant"):
        constant = wpo.get_editor_property("constant")
        require(
            all(float(getattr(constant, axis)) == 0 for axis in "xyz"),
            "Nonzero constant WPO",
        )
    displacement = editor_data.get_editor_property("displacement")
    require(
        displacement.get_editor_property("expression") is None,
        "Forge master has connected displacement",
    )
    require(
        not displacement.get_editor_property("use_constant")
        or displacement.get_editor_property("constant") == 0,
        "Nonzero constant displacement",
    )
    return {
        "instance": instance.get_path_name(),
        "parent": master.get_path_name(),
        "TileSizeCm": float(tile),
        "projection": "native_world_aligned_4m",
        "world_aligned_functions": sorted(functions),
        "wpo_connected": False,
        "displacement_connected": False,
        "max_displacement_world_m": 0.0,
        "shader_gpu_compilation_verified": False,
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
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False,
        include_hard_management_references=False,
    )
    dependency_names = set()
    for path in paths:
        dependency_names.update(
            str(name) for name in registry.get_dependencies(path.split(".")[0], options)
        )
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
        "native registry direct references of explicitly saved assets; not recursive engine closure"
    )
    receipt["status"] = "ISOLATED_MATERIAL_BINDING_SAVED_RENDER_PENDING"
    receipt["readback"] = verify_binding(receipt)
    return receipt
