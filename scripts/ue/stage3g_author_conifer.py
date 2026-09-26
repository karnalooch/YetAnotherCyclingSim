"""Author the production Stage 3G R2 mass-forest conifer asset.

The source is Poly Haven fir_sapling_medium, variant B. The source FBX contains
multiple variants, so only B is isolated into the project. The accepted R2
mass-scatter proof uses the aggressive measured LOD chain:
LOD0 100%, LOD1 18%, LOD2 5%, LOD3 1.25%.

Required environment variables:
  YACS_STAGE3G_ASSET_CACHE       absolute source cache with download-index.json
  YACS_STAGE3G_CONIFER_PROOF     absolute JSON proof output path
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any

import unreal


ASSET_ID = "fir_sapling_medium"
SOURCE_MESH_NAME = "fir_sapling_medium_b_LOD0"
MESH_ROOT = "/Game/Prototype/Environment/Stage3G/Imported/Meshes"
TEXTURE_ROOT = "/Game/Prototype/Environment/Stage3G/Imported/Textures"
MATERIAL_ROOT = "/Game/Prototype/Environment/Stage3G/Materials"
STAGING_ROOT = "/Game/Transient/YACS/Stage3GR2ConiferAuthor"
MESH_NAME = "SM_Stage3G_FirSaplingMedium"
MESH_PATH = MESH_ROOT + "/" + MESH_NAME
PROFILE_NAME = "aggressive"
PROFILE = [
    (1.0, 1.0),
    (0.18, 0.50),
    (0.05, 0.22),
    (0.0125, 0.08),
]

TEXTURE_SPECS = {
    ("branches", "diffuse"): "T_Stage3G_FirBranches_BaseColor",
    ("branches", "normal_dx"): "T_Stage3G_FirBranches_Normal",
    ("branches", "roughness"): "T_Stage3G_FirBranches_Roughness",
    ("twigs", "diffuse"): "T_Stage3G_FirTwigs_BaseColor",
    ("twigs", "normal_dx"): "T_Stage3G_FirTwigs_Normal",
    ("twigs", "roughness"): "T_Stage3G_FirTwigs_Roughness",
    ("twigs", "alpha"): "T_Stage3G_FirTwigs_Alpha",
}


def log(message: str) -> None:
    unreal.log("[Stage3GR2ConiferAuthor] {}".format(message))


def fail(message: str) -> None:
    raise RuntimeError(message)


def ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        if not unreal.EditorAssetLibrary.make_directory(path):
            fail("failed to create {}".format(path))


def source_path(cache_root: Path, row: dict[str, Any]) -> Path:
    path = (cache_root / str(row["relative_path"])).resolve()
    try:
        path.relative_to(cache_root.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "download-index path escapes cache: {}".format(path)
        ) from exc
    if not path.is_file():
        fail("source file is missing: {}".format(path))
    return path


def preferred_row(
    rows: list[dict[str, Any]],
    group: str,
    map_type: str,
) -> dict[str, Any]:
    candidates = [
        row
        for row in rows
        if row.get("asset_id") == ASSET_ID
        and row.get("map_type") == map_type
        and group in str(row.get("relative_path", "")).lower()
    ]
    if not candidates:
        fail("missing {} {} source texture".format(group, map_type))

    preferred = {
        "normal_dx": [".png", ".jpg", ".jpeg", ".exr"],
        "alpha": [".png", ".jpg", ".jpeg", ".exr"],
        "diffuse": [".jpg", ".jpeg", ".png", ".exr"],
        "roughness": [".jpg", ".jpeg", ".png", ".exr"],
    }[map_type]

    def rank(row: dict[str, Any]) -> tuple[int, str]:
        path = str(row.get("relative_path", ""))
        suffix = Path(path).suffix.lower()
        try:
            extension_rank = preferred.index(suffix)
        except ValueError:
            extension_rank = len(preferred)
        return extension_rank, path.lower()

    return sorted(candidates, key=rank)[0]


def import_texture(
    source: Path,
    canonical_name: str,
    map_type: str,
) -> unreal.Texture2D:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", TEXTURE_ROOT)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    imported_paths = [
        str(path)
        for path in (task.get_editor_property("imported_object_paths") or [])
    ]
    textures = []
    for path in imported_paths:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset and isinstance(asset, unreal.Texture2D):
            textures.append(path)
    if len(textures) != 1:
        fail(
            "{} imported {} textures: {}".format(
                source.name,
                len(textures),
                ", ".join(textures),
            )
        )

    canonical_path = TEXTURE_ROOT + "/" + canonical_name
    imported_path = textures[0]
    if imported_path != canonical_path:
        if unreal.EditorAssetLibrary.does_asset_exist(canonical_path):
            if not unreal.EditorAssetLibrary.delete_asset(canonical_path):
                fail("failed to replace {}".format(canonical_path))
        if not unreal.EditorAssetLibrary.rename_asset(
            imported_path,
            canonical_path,
        ):
            fail("failed to rename {} -> {}".format(imported_path, canonical_path))

    texture = unreal.EditorAssetLibrary.load_asset(canonical_path)
    if not texture or not isinstance(texture, unreal.Texture2D):
        fail("canonical texture cannot be loaded: {}".format(canonical_path))

    if map_type in {"normal_dx", "roughness", "alpha"}:
        texture.set_editor_property("srgb", False)
    if map_type == "normal_dx":
        texture.set_editor_property(
            "compression_settings",
            unreal.TextureCompressionSettings.TC_NORMALMAP,
        )
    texture.modify()
    if not unreal.EditorAssetLibrary.save_asset(
        canonical_path,
        only_if_is_dirty=False,
    ):
        fail("failed to save {}".format(canonical_path))
    return texture


def import_selected_mesh(source: Path) -> unreal.StaticMesh:
    staging = STAGING_ROOT + "/Import"
    ensure_directory(STAGING_ROOT)
    ensure_directory(staging)
    ensure_directory(MESH_ROOT)

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", staging)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    static_data = options.get_editor_property("static_mesh_import_data")
    static_data.set_editor_property("combine_meshes", False)
    static_data.set_editor_property("generate_lightmap_u_vs", True)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported_paths = [
        str(path)
        for path in (task.get_editor_property("imported_object_paths") or [])
    ]
    selected_path = ""
    names = []
    for path in imported_paths:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if not asset or not isinstance(asset, unreal.StaticMesh):
            continue
        names.append(asset.get_name())
        if asset.get_name().lower() == SOURCE_MESH_NAME.lower():
            if selected_path:
                fail("multiple {} meshes imported".format(SOURCE_MESH_NAME))
            selected_path = path

    if not selected_path:
        fail(
            "expected {} in imported meshes: {}".format(
                SOURCE_MESH_NAME,
                ", ".join(sorted(names)),
            )
        )

    if unreal.EditorAssetLibrary.does_asset_exist(MESH_PATH):
        if not unreal.EditorAssetLibrary.delete_asset(MESH_PATH):
            fail("failed to replace {}".format(MESH_PATH))
    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        selected_path,
        MESH_PATH,
    )
    if not duplicated or not isinstance(duplicated, unreal.StaticMesh):
        fail("failed to isolate selected fir mesh")

    if not unreal.EditorAssetLibrary.delete_directory(staging):
        fail("failed to delete heavy FBX staging import")
    unreal.collect_garbage()

    mesh = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    if not mesh or not isinstance(mesh, unreal.StaticMesh):
        fail("canonical fir mesh cannot be reloaded")
    return mesh


def reduction_options() -> unreal.StaticMeshReductionOptions:
    settings = []
    for percent_triangles, screen_size in PROFILE:
        value = unreal.StaticMeshReductionSettings()
        value.set_editor_property("percent_triangles", percent_triangles)
        value.set_editor_property("screen_size", screen_size)
        settings.append(value)

    options = unreal.StaticMeshReductionOptions()
    options.set_editor_property("auto_compute_lod_screen_size", False)
    options.set_editor_property("reduction_settings", settings)
    return options


def apply_lods(mesh: unreal.StaticMesh) -> str:
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if not subsystem:
        fail("StaticMeshEditorSubsystem is required for production conifer authoring")
    count = int(subsystem.set_lods(mesh, reduction_options()))
    if count < 0:
        fail("production LOD reduction returned {}".format(count))
    return "StaticMeshEditorSubsystem"


def material_texture_sample(
    material: unreal.Material,
    texture: unreal.Texture2D,
    x: int,
    y: int,
) -> Any:
    sample = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionTextureSample,
        x,
        y,
    )
    sample.set_editor_property("texture", texture)
    return sample


def create_material(
    name: str,
    *,
    base_color: unreal.Texture2D,
    normal: unreal.Texture2D,
    roughness: unreal.Texture2D,
    alpha: unreal.Texture2D | None = None,
) -> unreal.MaterialInstanceConstant:
    parent_name = "M_Stage3G_" + name
    instance_name = "MI_Stage3G_" + name
    parent_path = MATERIAL_ROOT + "/" + parent_name
    instance_path = MATERIAL_ROOT + "/" + instance_name

    for path in (instance_path, parent_path):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            if not unreal.EditorAssetLibrary.delete_asset(path):
                fail("failed to replace {}".format(path))

    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(
        parent_name,
        MATERIAL_ROOT,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        fail("failed to create {}".format(parent_name))

    material.set_editor_property("material_domain", unreal.MaterialDomain.MD_SURFACE)
    material.set_editor_property(
        "shading_model",
        (
            unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE
            if alpha
            else unreal.MaterialShadingModel.MSM_DEFAULT_LIT
        ),
    )
    material.set_editor_property("two_sided", bool(alpha))
    material.set_editor_property("bUsedWithInstancedStaticMeshes", True)
    if alpha:
        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
        material.set_editor_property("opacity_mask_clip_value", 0.35)

    color_sample = material_texture_sample(material, base_color, -520, -120)
    normal_sample = material_texture_sample(material, normal, -520, 40)
    roughness_sample = material_texture_sample(material, roughness, -520, 200)

    if not unreal.MaterialEditingLibrary.connect_material_property(
        color_sample,
        "RGB",
        unreal.MaterialProperty.MP_BASE_COLOR,
    ):
        fail("failed to connect {} base color".format(name))
    if not unreal.MaterialEditingLibrary.connect_material_property(
        normal_sample,
        "RGB",
        unreal.MaterialProperty.MP_NORMAL,
    ):
        fail("failed to connect {} normal".format(name))
    if not unreal.MaterialEditingLibrary.connect_material_property(
        roughness_sample,
        "R",
        unreal.MaterialProperty.MP_ROUGHNESS,
    ):
        fail("failed to connect {} roughness".format(name))

    if alpha:
        alpha_sample = material_texture_sample(material, alpha, -520, 360)
        if not unreal.MaterialEditingLibrary.connect_material_property(
            alpha_sample,
            "R",
            unreal.MaterialProperty.MP_OPACITY_MASK,
        ):
            fail("failed to connect {} opacity mask".format(name))

    unreal.MaterialEditingLibrary.recompile_material(material)
    if not unreal.EditorAssetLibrary.save_asset(
        parent_path,
        only_if_is_dirty=False,
    ):
        fail("failed to save {}".format(parent_path))

    instance = tools.create_asset(
        instance_name,
        MATERIAL_ROOT,
        unreal.MaterialInstanceConstant,
        unreal.MaterialInstanceConstantFactoryNew(),
    )
    if not instance:
        fail("failed to create {}".format(instance_name))
    unreal.MaterialEditingLibrary.set_material_instance_parent(instance, material)
    unreal.MaterialEditingLibrary.update_material_instance(instance)
    if not unreal.EditorAssetLibrary.save_asset(
        instance_path,
        only_if_is_dirty=False,
    ):
        fail("failed to save {}".format(instance_path))
    return instance


def bind_materials(
    mesh: unreal.StaticMesh,
    branch_material: unreal.MaterialInstanceConstant,
    twig_material: unreal.MaterialInstanceConstant,
) -> list[dict[str, Any]]:
    static_materials = list(mesh.get_editor_property("static_materials") or [])
    if len(static_materials) < 2:
        fail(
            "{} exposes only {} material slots".format(
                MESH_NAME,
                len(static_materials),
            )
        )

    bindings = []
    branch_count = 0
    twig_count = 0
    for index, static_material in enumerate(static_materials):
        names = [
            str(static_material.get_editor_property("material_slot_name")),
            str(static_material.get_editor_property("imported_material_slot_name")),
        ]
        label = " ".join(names).lower()
        if "twig" in label or "needle" in label or "leaf" in label:
            mesh.set_material(index, twig_material)
            kind = "twigs"
            twig_count += 1
        else:
            mesh.set_material(index, branch_material)
            kind = "branches"
            branch_count += 1
        bindings.append({"slot": index, "names": names, "material": kind})

    if branch_count == 0 or twig_count == 0:
        fail(
            "expected both branch and twig material slots; bindings={}".format(
                bindings
            )
        )
    return bindings


def lod_metrics(mesh: unreal.StaticMesh) -> list[dict[str, int]]:
    metrics = []
    for index in range(int(mesh.get_num_lods())):
        metrics.append(
            {
                "lod": index,
                "triangles": int(mesh.get_num_triangles(index)),
                "vertices": int(mesh.get_num_vertices(index)),
                "sections": int(mesh.get_num_sections(index)),
            }
        )
    return metrics


def main() -> None:
    cache_value = os.environ.get("YACS_STAGE3G_ASSET_CACHE", "")
    proof_value = os.environ.get("YACS_STAGE3G_CONIFER_PROOF", "")
    if not cache_value:
        fail("YACS_STAGE3G_ASSET_CACHE is not set")
    if not proof_value:
        fail("YACS_STAGE3G_CONIFER_PROOF is not set")

    cache_root = Path(cache_value).resolve()
    index_path = cache_root / "download-index.json"
    if not index_path.is_file():
        fail("download-index.json is missing")

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    rows = list(payload.get("files") or [])
    fbx_rows = [
        row
        for row in rows
        if row.get("asset_id") == ASSET_ID
        and row.get("map_type") is None
        and str(row.get("relative_path", "")).lower().endswith(".fbx")
    ]
    if len(fbx_rows) != 1:
        fail("expected exactly one {} FBX".format(ASSET_ID))

    ensure_directory(TEXTURE_ROOT)
    ensure_directory(MATERIAL_ROOT)

    textures: dict[tuple[str, str], unreal.Texture2D] = {}
    texture_proof = []
    for key, canonical_name in TEXTURE_SPECS.items():
        group, map_type = key
        row = preferred_row(rows, group, map_type)
        source = source_path(cache_root, row)
        texture = import_texture(source, canonical_name, map_type)
        textures[key] = texture
        texture_proof.append(
            {
                "group": group,
                "map_type": map_type,
                "source": str(source),
                "source_md5": row.get("md5"),
                "destination": texture.get_path_name(),
            }
        )

    source = source_path(cache_root, fbx_rows[0])
    mesh = import_selected_mesh(source)
    reduction_backend = apply_lods(mesh)

    branch_material = create_material(
        "FirBranches",
        base_color=textures[("branches", "diffuse")],
        normal=textures[("branches", "normal_dx")],
        roughness=textures[("branches", "roughness")],
    )
    twig_material = create_material(
        "FirTwigs",
        base_color=textures[("twigs", "diffuse")],
        normal=textures[("twigs", "normal_dx")],
        roughness=textures[("twigs", "roughness")],
        alpha=textures[("twigs", "alpha")],
    )
    bindings = bind_materials(mesh, branch_material, twig_material)

    if not unreal.EditorAssetLibrary.save_asset(
        MESH_PATH,
        only_if_is_dirty=False,
    ):
        fail("failed to save {}".format(MESH_PATH))

    reloaded = unreal.EditorAssetLibrary.load_asset(MESH_PATH)
    if not reloaded or not isinstance(reloaded, unreal.StaticMesh):
        fail("saved conifer mesh cannot be reloaded")
    metrics = lod_metrics(reloaded)
    if [item["triangles"] for item in metrics] != [
        420822,
        75748,
        21042,
        5260,
    ]:
        fail("production conifer LOD metrics changed: {}".format(metrics))

    proof = {
        "stage3g_r2_conifer_authoring": "success",
        "asset_id": ASSET_ID,
        "source_mesh": SOURCE_MESH_NAME,
        "mesh_path": MESH_PATH,
        "profile": PROFILE_NAME,
        "reduction_backend": reduction_backend,
        "lods": metrics,
        "material_bindings": bindings,
        "textures": texture_proof,
        "source_fbx": str(source),
        "source_md5": fbx_rows[0].get("md5"),
    }
    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log("SUCCESS: authored {}".format(MESH_PATH))


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GR2ConiferAuthor] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
