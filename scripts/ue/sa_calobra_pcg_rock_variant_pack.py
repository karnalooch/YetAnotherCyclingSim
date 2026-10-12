"""Six isolated source-scaled rock library assets; no placement or contact admission."""

import hashlib
import json
import math
from pathlib import Path
import re

import unreal

from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue.sa_calobra_pcg_terrain_contact import require, vector

DESTINATION = "/Game/Generated/YACS/PCG365RockVariants"


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def catalog(root):
    path = root / "rock-variant-catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    require(
        type(data.get("schema_version")) is int and data["schema_version"] == 1,
        "Unknown catalog schema",
    )
    require(
        data.get("placement") is False and data.get("qualified_assets") == [],
        "Catalog cannot admit placement",
    )
    rows = data["variants"]
    require(type(rows) is list and len(rows) == 6, "Exactly six variants required")
    ids, groups = set(), {}
    for row in rows:
        name = row["id"]
        require(
            type(name) is str
            and re.fullmatch("[A-Za-z0-9_]+", name)
            and name not in ids,
            "Invalid or duplicate variant ID",
        )
        ids.add(name)
        require(
            row["source_relative"] == "rock-variants/" + name + ".fbx",
            "Source path must match variant ID",
        )
        for key in ("sha256", "base_source_sha256"):
            require(
                type(row[key]) is str and re.fullmatch("[0-9a-f]{64}", row[key]),
                "Invalid source hash",
            )
        require(type(row["bytes"]) is int and row["bytes"] > 0, "Invalid source size")
        scale = row["art_scale"]
        require(
            type(scale) in (int, float) and scale in (0.75, 1.0, 1.25),
            "Unknown ART source scale",
        )
        scales = groups.setdefault(row["base_source_sha256"], set())
        require(scale not in scales, "Duplicate source scale")
        scales.add(scale)
        bounds = row["expected_native_bounds_cm"]
        require(set(bounds) == {"min", "max"}, "Invalid bounds fields")
        for values in bounds.values():
            require(
                type(values) is list
                and len(values) == 3
                and all(type(v) in (int, float) and math.isfinite(v) for v in values),
                "Invalid source bounds",
            )
        require(
            all(a < b for a, b in zip(bounds["min"], bounds["max"])),
            "Degenerate source bounds",
        )
        require(
            type(row["expected_lod0_triangles"]) is int
            and row["expected_lod0_triangles"] > 0,
            "Invalid triangle witness",
        )
        source(root, row)
    require(
        len(groups) == 2 and all(s == {0.75, 1.0, 1.25} for s in groups.values()),
        "Require two source bases with three scales each",
    )
    return sorted(rows, key=lambda row: row["id"]), identity(path)


def source(root, row):
    path = (root / row["source_relative"]).resolve(strict=True)
    require(path.is_relative_to(root / "rock-variants"), "Source escaped staging")
    require(
        identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
        "Variant source bytes drift",
    )
    return path


def context(root, output, head, binding):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(
        root == material.project_root()
        and output.is_relative_to(root)
        and output != root,
        "Wrong owned stage/output",
    )
    require(
        type(head) is str and re.fullmatch("[0-9a-f]{40}", head), "Exact HEAD required"
    )
    require(
        binding["code_sha"] == head and len(binding["saved_packages"]) == 7,
        "Binding HEAD/inventory differs",
    )
    material.verify_binding(binding)
    assets = binding["forge_import"]["assets"]
    require(
        material.material_readback(assets)["rock_appearance"]["recipe"]
        == "ROCK_APPEARANCE_V2",
        "Strict Forge V2 required",
    )
    verify_binding_bytes(root, binding)
    return root, output, unreal.load_asset(assets["instance"])


def verify_binding_bytes(root, binding):
    for item in binding["saved_packages"]:
        path = (root / item["path"]).resolve(strict=True)
        require(
            path.is_relative_to(root / "Content"), "Binding package escaped Content"
        )
        require(
            identity(path) == {"bytes": item["bytes"], "sha256": item["sha256"]},
            "Protected Forge package changed",
        )


def native_readback(mesh, row, instance):
    require(isinstance(mesh, unreal.StaticMesh), "Variant is not StaticMesh")
    require(
        len(mesh.static_materials) > 0
        and all(
            mesh.get_material(i) == instance for i in range(len(mesh.static_materials))
        ),
        "Variant Forge slots differ",
    )
    bounds = mesh.get_bounds()
    origin, extent = vector(bounds.origin), vector(bounds.box_extent)
    actual = [origin[i] - extent[i] for i in range(3)] + [
        origin[i] + extent[i] for i in range(3)
    ]
    expected = row["expected_native_bounds_cm"]
    require(
        all(
            math.isfinite(a) and abs(a - b) <= 0.01
            for a, b in zip(actual, expected["min"] + expected["max"])
        ),
        "Native source bounds differ",
    )
    require(
        mesh.get_num_triangles(0) == row["expected_lod0_triangles"],
        "Native triangle count differs",
    )
    return {
        "bounds_cm": {"origin": origin, "extent": extent},
        "lod0_render_triangles": mesh.get_num_triangles(0),
        "slot_count": len(mesh.static_materials),
        "material": instance.get_path_name(),
    }


def import_mesh(root, row, instance):
    package = DESTINATION + "/SM_" + row["id"]
    require(
        not unreal.EditorAssetLibrary.does_asset_exist(package),
        "Preserve existing asset",
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
        data.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    for key, value in {
        "filename": str(source(root, row)),
        "destination_path": DESTINATION,
        "destination_name": "SM_" + row["id"],
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
        "Unexpected imported inventory",
    )
    mesh = unreal.load_asset(package)
    require(isinstance(mesh, unreal.StaticMesh), "Import is not StaticMesh")
    for i in range(len(mesh.static_materials)):
        mesh.set_material(i, instance)
    native = native_readback(mesh, row, instance)
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False),
        "Variant save failed",
    )
    source(root, row)
    return {
        "id": row["id"],
        "source": row,
        "package": package,
        "saved_package": material.file_identity(package),
        **native,
    }


def build(root, output, head, binding):
    root, output, instance = context(root, output, head, binding)
    rows, catalog_identity = catalog(root)
    meshes = [import_mesh(root, row, instance) for row in rows]
    require(catalog(root) == (rows, catalog_identity), "Catalog changed during import")
    verify_binding_bytes(root, binding)
    receipt = {
        "schema_version": 1,
        "code_sha": head,
        "status": "ROCK_VARIANT_ASSETS_SAVED",
        "catalog": catalog_identity,
        "meshes": meshes,
        "binding_saved_packages": binding["saved_packages"],
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "terrain_contact": "NOT_RUN",
        "source_art_scales_only": True,
        "native_import_scale": 1.0,
        "map_saved": False,
        "visual_acceptance": "NOT_VERIFIED",
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "rock-pack-inventory.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
    return receipt


def reload(root, output, head, binding):
    root, output, instance = context(root, output, head, binding)
    rows, catalog_identity = catalog(root)
    inventory_path = root / "proof/rock-pack/rock-pack-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    require(
        inventory["code_sha"] == head
        and inventory["catalog"] == catalog_identity
        and inventory["placement"] is False
        and inventory["qualified_assets"] == []
        and inventory["binding_saved_packages"] == binding["saved_packages"],
        "Saved inventory binding differs",
    )
    require(len(inventory["meshes"]) == 6, "Saved inventory count differs")
    for row, saved in zip(rows, inventory["meshes"]):
        require(
            saved["id"] == row["id"]
            and saved["source"] == row
            and saved["package"] == DESTINATION + "/SM_" + row["id"],
            "Saved variant identity differs",
        )
        require(
            material.file_identity(saved["package"]) == saved["saved_package"],
            "Saved variant bytes changed",
        )
        native = native_readback(unreal.load_asset(saved["package"]), row, instance)
        require(
            all(saved[k] == value for k, value in native.items()),
            "Fresh readback differs",
        )
    verify_binding_bytes(root, binding)
    require(catalog(root) == (rows, catalog_identity), "Catalog drift during reload")
    return {
        **inventory,
        "status": "ROCK_VARIANT_ASSETS_FRESH_RELOAD_VERIFIED",
        "inventory_source": identity(inventory_path),
    }
