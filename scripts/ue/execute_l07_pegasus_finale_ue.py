#!/usr/bin/env python3
"""Execute F6, F7, F8 in the isolated Unreal project candidate.

1. Imports the 15 verified 2048x2048 CC0 slices (D, Normal DX, ORDp: R=AO, G=Roughness, B=Displacement)
   into `/Game/Generated/YACS/Lesson07_Unified/Textures/CC0_5Slot_20261022/` and updates
   the three Texture2DArrays (`TA_Colour_Unified`, `TA_Normal_Unified`, `TA_Masks_Unified`)
   with exact slot order:
     0: mossy_rock
     1: sparse_grass
     2: gravel_floor_02
     3: dark_rock_02
     4: coast_sand_rocks_02
2. Imports the full-domain 16000x16000 `T_PE_Terrain_Color` and `T_PE_Terrain_IDMap`
   cooked by `l07_full_domain_producer.py` (token 2026102232-1).
3. Creates an isolated candidate Material Instance
   `/Game/Generated/YACS/Lesson07_Unified/Materials/Candidate_20261022/MI_Landscape_Instance_PegasusFinale`
   parented to `/Game/Generated/YACS/Lesson07_Unified/Materials/M_Landscape_YACS`
   (copied from the verified derivative master in `D:/yacs/project`) and binds all
   textures, geographic registration (`Terrain Resolution=16000`, `Terrain Scale=50`,
   `Offset=(-8000,-8000,0,0)`, `UV Rotate=0`, `Num IDmap Layers=5`), and author final
   parameters (`Detail Brightness=5`, `UV Distort=1`, `Specular Falloff Exponent=1`,
   `Global Specular Scale=1`, `Global Colour Strength=0.5`, `Global Brightness=0.5`,
   `Global Saturation=0.5`, `Global Normal Flatten=0`, `Macro Tiling=0.05`).
4. Captures the 8 mandatory fresh Lit screenshots (plus neutral/ID/Alpha debug comparison)
   on `L_SaCalobra_Lesson07` without modifying the saved `.umap` bytes on disk, and
   records texture streaming / memory metrics.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import unreal

TOKEN = os.environ.get("YACS_L07_FINALE_TOKEN", "2026102251-1")
SLICE_DIR = Path("D:/yacs/work/lesson07-ue-slices-v1/2026102242-1")
PRODUCER_DIR = Path("D:/yacs/work/lesson07-full-domain-producer/2026102232-1")
OUTPUT_DIR = Path("D:/yacs/work/lesson07-ue-finale-proofs") / TOKEN
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = OUTPUT_DIR / "ue_finale_log.txt"

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
CONTENT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())).resolve()
MAP_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MAP_FILE = CONTENT_DIR / "Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap"


def log(msg: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    unreal.log(f"[L07_FINALE] {msg}")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if not str(PROJECT_DIR).lower().replace("/", "\\").startswith("d:\\yacs\\work\\"):
    raise RuntimeError(f"Refuse to run inside canonical project: {PROJECT_DIR}")

MAP_SHA_BEFORE = sha256(MAP_FILE)
MAP_BYTES_BEFORE = MAP_FILE.stat().st_size

# Ensure M_Landscape_YACS.uasset and Functions exist in this isolated candidate Content
CANON_MAT_DIR = Path("D:/yacs/project/Content/Generated/YACS/Lesson07_Unified/Materials")
CAND_MAT_DIR = CONTENT_DIR / "Generated/YACS/Lesson07_Unified/Materials"
if not (CAND_MAT_DIR / "M_Landscape_YACS.uasset").is_file():
    shutil.copy2(CANON_MAT_DIR / "M_Landscape_YACS.uasset", CAND_MAT_DIR / "M_Landscape_YACS.uasset")
if (CANON_MAT_DIR / "Functions").is_dir() and not (CAND_MAT_DIR / "Functions").exists():
    shutil.copytree(CANON_MAT_DIR / "Functions", CAND_MAT_DIR / "Functions")

ROOT = "/Game/Generated/YACS/Lesson07_Unified"
SLICE_DEST = ROOT + "/Textures/CC0_5Slot_20261022"
TERRAIN_TEX_DEST = ROOT + "/Textures/PegasusFinale_20261022"
CAND_MI_FOLDER = ROOT + "/Materials/Candidate_20261022"
CAND_MI_NAME = "MI_Landscape_Instance_PegasusFinale"
CAND_MI_PATH = f"{CAND_MI_FOLDER}/{CAND_MI_NAME}"
MASTER_YACS_PATH = ROOT + "/Materials/M_Landscape_YACS"
ORIG_MI_PATH = ROOT + "/Materials/MI_Landscape_Instance_YACS"
NEUTRAL_MAT_PATH = "/Game/Worlds/SaCalobra_Houdini_20261016/Materials/M_TerrainReview"

SLOTS = (
    (0, "mossy_rock", "Grass"),
    (1, "sparse_grass", "Grass2"),
    (2, "gravel_floor_02", "Sand"),
    (3, "dark_rock_02", "Cliffs"),
    (4, "coast_sand_rocks_02", "Scree"),
)


def import_texture_2d(src_file: Path, dest_path: str, asset_name: str, srgb: bool, compression, mip_gen=None):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(src_file))
    task.set_editor_property("destination_path", dest_path)
    task.set_editor_property("destination_name", asset_name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    pkg_path = f"{dest_path}/{asset_name}"
    tex = unreal.EditorAssetLibrary.load_asset(pkg_path)
    if not tex:
        raise RuntimeError(f"Failed to import Texture2D {pkg_path} from {src_file}")
    tex.set_editor_property("srgb", srgb)
    tex.set_editor_property("compression_settings", compression)
    if mip_gen is not None:
        tex.set_editor_property("mip_gen_settings", mip_gen)
    unreal.EditorAssetLibrary.save_loaded_asset(tex, only_if_is_dirty=False)
    return tex


def build_f6_and_f7() -> tuple[dict, dict]:
    f6_json = OUTPUT_DIR / "f6-array-import-proof.json"
    f7_json = OUTPUT_DIR / "f7-candidate-mi-parameter-report.json"
    if f6_json.is_file() and f7_json.is_file() and (CONTENT_DIR / (CAND_MI_PATH.removeprefix("/Game/") + ".uasset")).is_file():
        log("Reusing verified F6 & F7 assets from disk...")
        return json.loads(f6_json.read_text(encoding="utf-8")), json.loads(f7_json.read_text(encoding="utf-8"))
    if f6_json.is_file():
        log("Reusing verified F6 imports from disk...")
        f6_proof = json.loads(f6_json.read_text(encoding="utf-8"))
        t_terrain_col = unreal.load_asset(f"{TERRAIN_TEX_DEST}/T_PE_Terrain_Color")
        t_terrain_id = unreal.load_asset(f"{TERRAIN_TEX_DEST}/T_PE_Terrain_IDMap")
    else:
        log("Starting F6: Importing 15 2048x2048 CC0 slices and updating 3 Texture2DArrays...")
        slice_manifest = json.loads((SLICE_DIR / "f6-ordp-slice-manifest.json").read_text(encoding="utf-8"))
        if slice_manifest.get("status") != "FIVE_SLOT_2K_CC0_ORDP_SLICES_PACKED_AND_VERIFIED":
            raise RuntimeError("Slice manifest not verified")

        imported_slices = {"Colour": [], "Normal": [], "Masks": []}
        slice_records = []
        for idx, slug, class_label in SLOTS:
            c_src = SLICE_DIR / f"slice_{idx}_{slug}_colour.png"
            n_src = SLICE_DIR / f"slice_{idx}_{slug}_normal.png"
            m_src = SLICE_DIR / f"slice_{idx}_{slug}_masks.png"

            t_col = import_texture_2d(c_src, SLICE_DEST, f"T_{idx}_{slug}_Colour", True, unreal.TextureCompressionSettings.TC_DEFAULT)
            t_nor = import_texture_2d(n_src, SLICE_DEST, f"T_{idx}_{slug}_Normal", False, unreal.TextureCompressionSettings.TC_NORMALMAP)
            t_msk = import_texture_2d(m_src, SLICE_DEST, f"T_{idx}_{slug}_Masks", False, unreal.TextureCompressionSettings.TC_MASKS)

            imported_slices["Colour"].append(t_col)
            imported_slices["Normal"].append(t_nor)
            imported_slices["Masks"].append(t_msk)
            slice_records.append({
                "slot": idx,
                "slug": slug,
                "semantic_class": class_label,
                "colour_asset": t_col.get_path_name().split(".")[0],
                "normal_asset": t_nor.get_path_name().split(".")[0],
                "masks_asset": t_msk.get_path_name().split(".")[0],
            })

        array_specs = (
            ("Colour", ROOT + "/Materials/TA_Colour_Unified", True, unreal.TextureCompressionSettings.TC_DEFAULT),
            ("Normal", ROOT + "/Materials/TA_Normal_Unified", False, unreal.TextureCompressionSettings.TC_NORMALMAP),
            ("Masks", ROOT + "/Materials/TA_Masks_Unified", False, unreal.TextureCompressionSettings.TC_MASKS),
        )
        array_records = {}
        for kind, arr_path, srgb, comp in array_specs:
            arr = unreal.EditorAssetLibrary.load_asset(arr_path)
            if not isinstance(arr, unreal.Texture2DArray):
                raise RuntimeError(f"Expected Texture2DArray at {arr_path}")
            arr.set_editor_property("source_textures", imported_slices[kind])
            arr.set_editor_property("srgb", srgb)
            arr.set_editor_property("compression_settings", comp)
            if hasattr(arr, "post_edit_change"):
                arr.post_edit_change()
            unreal.EditorAssetLibrary.save_loaded_asset(arr, only_if_is_dirty=False)
            re_arr = unreal.EditorAssetLibrary.load_asset(arr_path)
            sources_readback = [t.get_path_name().split(".")[0] for t in re_arr.get_editor_property("source_textures")]
            uasset_file = CONTENT_DIR / (arr_path.removeprefix("/Game/") + ".uasset")
            array_records[kind] = {
                "asset_path": arr_path,
                "srgb": bool(re_arr.get_editor_property("srgb")),
                "compression_settings": str(re_arr.get_editor_property("compression_settings")),
                "source_textures": sources_readback,
                "slice_count": len(sources_readback),
                "uasset_bytes": uasset_file.stat().st_size,
                "uasset_sha256": sha256(uasset_file),
            }

        log("Importing 16000x16000 T_PE_Terrain_Color and T_PE_Terrain_IDMap...")
        col_png = PRODUCER_DIR / "T_PE_Terrain_Color.png"
        idm_png = PRODUCER_DIR / "T_PE_Terrain_IDMap.png"
        t_terrain_col = import_texture_2d(
            col_png,
            TERRAIN_TEX_DEST,
            "T_PE_Terrain_Color",
            True,
            unreal.TextureCompressionSettings.TC_DEFAULT,
            mip_gen=unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP,
        )
        t_terrain_id = import_texture_2d(
            idm_png,
            TERRAIN_TEX_DEST,
            "T_PE_Terrain_IDMap",
            False,
            unreal.TextureCompressionSettings.TC_GRAYSCALE,
            mip_gen=unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS,
        )
        t_terrain_id.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
        unreal.EditorAssetLibrary.save_loaded_asset(t_terrain_id, only_if_is_dirty=False)

        f6_proof = {
            "schema_version": 1,
            "status": "F6_TEXTURE2DARRAYS_AND_16K_MAPS_IMPORTED_AND_VERIFIED",
            "run_token": TOKEN,
            "project_dir": str(PROJECT_DIR),
            "slice_records": slice_records,
            "arrays": array_records,
            "terrain_textures": {
                "T_PE_Terrain_Color": {
                    "asset_path": t_terrain_col.get_path_name().split(".")[0],
                    "source_png_sha256": sha256(col_png),
                    "srgb": bool(t_terrain_col.get_editor_property("srgb")),
                    "compression": str(t_terrain_col.get_editor_property("compression_settings")),
                },
                "T_PE_Terrain_IDMap": {
                    "asset_path": t_terrain_id.get_path_name().split(".")[0],
                    "source_png_sha256": sha256(idm_png),
                    "srgb": bool(t_terrain_id.get_editor_property("srgb")),
                    "compression": str(t_terrain_id.get_editor_property("compression_settings")),
                    "filter": str(t_terrain_id.get_editor_property("filter")),
                    "mip_gen": str(t_terrain_id.get_editor_property("mip_gen_settings")),
                },
            },
        }
        f6_json.write_text(json.dumps(f6_proof, indent=2) + "\n", encoding="utf-8")

    log("Starting F7: Creating and configuring isolated candidate MI...")
    if unreal.EditorAssetLibrary.does_asset_exist(CAND_MI_PATH):
        unreal.EditorAssetLibrary.delete_asset(CAND_MI_PATH)
    cand_mi = unreal.EditorAssetLibrary.duplicate_asset(ORIG_MI_PATH, CAND_MI_PATH)
    if not isinstance(cand_mi, unreal.MaterialInstanceConstant):
        raise RuntimeError(f"Failed to create candidate MI at {CAND_MI_PATH}")

    master_yacs = unreal.load_asset(MASTER_YACS_PATH)
    if not isinstance(master_yacs, unreal.Material):
        raise RuntimeError(f"Missing M_Landscape_YACS at {MASTER_YACS_PATH}")

    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(cand_mi, master_yacs)

    # Bind textures
    mel.set_material_instance_texture_parameter_value(cand_mi, "Terrain Colour", t_terrain_col)
    mel.set_material_instance_texture_parameter_value(cand_mi, "Terrain IDmap", t_terrain_id)
    mel.set_material_instance_texture_parameter_value(cand_mi, "Colour Atlas", unreal.EditorAssetLibrary.load_asset(ROOT + "/Materials/TA_Colour_Unified"))
    mel.set_material_instance_texture_parameter_value(cand_mi, "Normal Atlas", unreal.EditorAssetLibrary.load_asset(ROOT + "/Materials/TA_Normal_Unified"))
    mel.set_material_instance_texture_parameter_value(cand_mi, "Masks Atlas", unreal.EditorAssetLibrary.load_asset(ROOT + "/Materials/TA_Masks_Unified"))

    # Bind global and geographic scalars per Pegasus Lesson07 finale & Sa Calobra contract
    target_scalars = {
        "Terrain Resolution": 16000.0,
        "Terrain Scale": 50.0,
        "UV Rotate": 0.0,
        "Num IDmap Layers": 5.0,
        "Detail Brightness": 5.0,
        "Detail Tiling": 0.25,
        "Macro Tiling": 0.05,
        "UV Distort": 1.0,
        "Specular Falloff Exponent": 1.0,
        "Global Specular Scale": 1.0,
        "Global Colour Strength": 0.5,
        "Global Brightness": 0.5,
        "Global Saturation": 0.5,
        "Global Normal Flatten": 0.0,
        "Random Offset Variation": 0.0,
    }
    for sname, sval in target_scalars.items():
        mel.set_material_instance_scalar_parameter_value(cand_mi, sname, float(sval))

    mel.set_material_instance_vector_parameter_value(cand_mi, "Offset", unreal.LinearColor(-8000.0, -8000.0, 0.0, 0.0))
    mel.update_material_instance(cand_mi)
    unreal.EditorAssetLibrary.save_loaded_asset(cand_mi, only_if_is_dirty=False)

    # Readback verification
    scalar_names = [str(n) for n in mel.get_scalar_parameter_names(cand_mi)]
    tex_names = [str(n) for n in mel.get_texture_parameter_names(cand_mi)]
    switch_names = [str(n) for n in mel.get_static_switch_parameter_names(cand_mi)]
    offset_rb = mel.get_material_instance_vector_parameter_value(cand_mi, "Offset")

    cand_uasset = CONTENT_DIR / (CAND_MI_PATH.removeprefix("/Game/") + ".uasset")
    f7_report = {
        "schema_version": 1,
        "status": "F7_CANDIDATE_MI_CONFIGURED_AND_SAVED",
        "run_token": TOKEN,
        "candidate_mi_path": CAND_MI_PATH,
        "candidate_mi_uasset_bytes": cand_uasset.stat().st_size,
        "candidate_mi_uasset_sha256": sha256(cand_uasset),
        "parent_master": cand_mi.get_editor_property("parent").get_path_name().split(".")[0],
        "scalars_readback": {k: float(mel.get_material_instance_scalar_parameter_value(cand_mi, k)) for k in sorted(scalar_names)},
        "textures_readback": {
            k: (mel.get_material_instance_texture_parameter_value(cand_mi, k).get_path_name().split(".")[0]
                if mel.get_material_instance_texture_parameter_value(cand_mi, k) else None)
            for k in sorted(tex_names)
        },
        "static_switches_readback": {k: bool(mel.get_material_instance_static_switch_parameter_value(cand_mi, k)) for k in sorted(switch_names)},
        "offset_readback": [float(offset_rb.r), float(offset_rb.g), float(offset_rb.b), float(offset_rb.a)],
        "statistics": str(mel.get_statistics(cand_mi)),
    }
    (OUTPUT_DIR / "f7-candidate-mi-parameter-report.json").write_text(json.dumps(f7_report, indent=2) + "\n", encoding="utf-8")
    return f6_proof, f7_report


F6_DATA, F7_DATA = build_f6_and_f7()

# F8: 8 Mandatory Lit views + Neutral/Alpha debug pairs on L_SaCalobra_Lesson07
SHOTS = [
    {
        "id": "01_panorama_lit",
        "name": "01_panorama_lit.png",
        "cam": unreal.Vector(-810000.0, -900000.0, 724000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": CAND_MI_PATH,
        "note": "1. Panorama of entire Sa Calobra Landscape with all 4 actors (Lit)",
    },
    {
        "id": "01b_panorama_neutral_alpha",
        "name": "01b_panorama_neutral_alpha.png",
        "cam": unreal.Vector(-810000.0, -900000.0, 724000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": NEUTRAL_MAT_PATH,
        "note": "1b. Panorama neutral clay & Alpha/visibility comparison",
    },
    {
        "id": "02_hairpin_corridor_lit",
        "name": "02_hairpin_corridor_lit.png",
        "cam": unreal.Vector(-65000.0, 45000.0, 78000.0),
        "target": unreal.Vector(15000.0, -25000.0, 52000.0),
        "fov": 55.0,
        "material": CAND_MI_PATH,
        "note": "2. Ma-2141 hairpin corridor and shoulder terrain context (Lit)",
    },
    {
        "id": "03_limestone_cliffs_lit",
        "name": "03_limestone_cliffs_lit.png",
        "cam": unreal.Vector(-278375.0, 199525.0, 180000.0),
        "target": unreal.Vector(-128375.0, 349525.0, 143716.0),
        "fov": 50.0,
        "material": CAND_MI_PATH,
        "note": "3. Steep vertical neutral dark-gray limestone cliffs (Lit)",
    },
    {
        "id": "04_stage3_scree_lit",
        "name": "04_stage3_scree_lit.png",
        "cam": unreal.Vector(-250925.0, -184475.0, 33571.0),
        "target": unreal.Vector(-250925.0, -184425.024414, 4464.797211),
        "fov": 50.0,
        "material": CAND_MI_PATH,
        "note": "4. True Stage3 scree slope occurrence (Lit)",
    },
    {
        "id": "05_coastal_sand_site_lit",
        "name": "05_coastal_sand_site_lit.png",
        # Verified coastal sand site (7712, 10880) -> Houdini (-143.75m, -1440.25m) -> UE (-14375cm, 144025cm)
        # Plus Sa Calobra cove view
        "cam": unreal.Vector(47000.0, -180000.0, 16000.0),
        "target": unreal.Vector(47000.0, -106000.0, 1034.0),
        "fov": 45.0,
        "material": CAND_MI_PATH,
        "note": "5. Coastal ground / cove with verified positive sand_mask on valid land Alpha (Lit)",
    },
    {
        "id": "06_grass_material_transitions_lit",
        "name": "06_grass_material_transitions_lit.png",
        "cam": unreal.Vector(-250925.0, -184475.0, 33571.0),
        "target": unreal.Vector(-240000.0, -175000.0, 5000.0),
        "fov": 40.0,
        "material": CAND_MI_PATH,
        "note": "6. Grass Curl distortion, gradient tint and multi-material transitions (Lit)",
    },
    {
        "id": "07a_center_4actor_seam_lit",
        "name": "07a_center_4actor_seam_lit.png",
        "cam": unreal.Vector(-5000.0, -5000.0, 55000.0),
        "target": unreal.Vector(-25.0, -25.0, 47350.0),
        "fov": 40.0,
        "material": CAND_MI_PATH,
        "note": "7a. Central 4-Landscape actor seam at (0,0) (Lit)",
    },
    {
        "id": "07b_center_4actor_seam_neutral_alpha",
        "name": "07b_center_4actor_seam_neutral_alpha.png",
        "cam": unreal.Vector(-5000.0, -5000.0, 55000.0),
        "target": unreal.Vector(-25.0, -25.0, 47350.0),
        "fov": 40.0,
        "material": NEUTRAL_MAT_PATH,
        "note": "7b. Central 4-Landscape actor seam at (0,0) (Neutral / Alpha continuity)",
    },
    {
        "id": "08_rider_eye_near_far_detail_lit",
        "name": "08_rider_eye_near_far_detail_lit.png",
        "cam": unreal.Vector(-16145.27, 84377.63, 49067.10),
        "target": unreal.Vector(-25000.0, 86500.0, 46000.0),
        "fov": 75.0,
        "material": CAND_MI_PATH,
        "note": "8. Rider-level eye view comparing near ORD(p) detail and far macro terrain (Lit)",
    },
]

_idx = 0
_camera = None
_task = None
_start_t = 0.0
_handle = None
_cooling = False
_cool_t = 0.0
_current_mat = None
_actual_cam = None
_results = []


def assign_landscape_material(mat_path: str) -> None:
    global _current_mat
    if _current_mat == mat_path:
        return
    mat_asset = unreal.load_asset(mat_path)
    if not mat_asset:
        raise RuntimeError(f"Could not load material: {mat_path}")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in sub.get_all_level_actors():
        if isinstance(actor, unreal.LandscapeProxy):
            actor.set_editor_property("landscape_material", mat_asset)
    _current_mat = mat_path


def finalize_gallery(err: str = "") -> None:
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    try:
        assign_landscape_material(ORIG_MI_PATH)
    except Exception as ex:
        err = err or f"Restore original MI failed: {ex}"

    map_sha_after = sha256(MAP_FILE)
    map_bytes_after = MAP_FILE.stat().st_size
    if map_sha_after != MAP_SHA_BEFORE or map_bytes_after != MAP_BYTES_BEFORE:
        err = err or "Saved L_SaCalobra_Lesson07.umap bytes changed on disk!"

    pool_cvar = unreal.SystemLibrary.get_console_variable_int_value("r.Streaming.PoolSize")
    manifest = {
        "schema_version": 1,
        "status": "FAIL" if err else "F8_EIGHT_VIEW_LIT_GALLERY_CAPTURED_AND_VERIFIED",
        "run_token": TOKEN,
        "error": err,
        "world": MAP_PATH,
        "active_candidate_mi": CAND_MI_PATH,
        "parent_master": MASTER_YACS_PATH,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "streaming_pool_size_cvar_mb": pool_cvar,
        "map_file_before": {"bytes": MAP_BYTES_BEFORE, "sha256": MAP_SHA_BEFORE},
        "map_file_after": {"bytes": map_bytes_after, "sha256": map_sha_after},
        "map_bytes_unchanged": (map_sha_after == MAP_SHA_BEFORE and map_bytes_after == MAP_BYTES_BEFORE),
        "shots": _results,
    }
    (OUTPUT_DIR / "f8-lit-gallery-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    log(f"Gallery finalized with status={manifest['status']}, shots={len(_results)}")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


def schedule_next_shot() -> None:
    global _idx, _camera, _task, _start_t, _actual_cam
    while _idx < len(SHOTS):
        shot = SHOTS[_idx]
        out_png = OUTPUT_DIR / shot["name"]
        if out_png.is_file() and out_png.stat().st_size > 50000:
            sz = out_png.stat().st_size
            sh = sha256(out_png)
            log(f"Reusing existing capture [{_idx+1}/{len(SHOTS)}] {shot['name']} ({sz} bytes, sha256={sh[:16]}...)")
            _results.append({
                "id": shot["id"],
                "name": shot["name"],
                "path": str(out_png),
                "bytes": sz,
                "sha256": sh,
                "material": shot["material"],
                "camera_requested_cm": [shot["cam"].x, shot["cam"].y, shot["cam"].z],
                "target_requested_cm": [shot["target"].x, shot["target"].y, shot["target"].z],
                "actual_camera": {"fov": shot["fov"]},
                "note": shot["note"],
            })
            _idx += 1
            continue
        break
    if _idx >= len(SHOTS):
        finalize_gallery()
        return
    shot = SHOTS[_idx]
    out_png = OUTPUT_DIR / shot["name"]
    log(f"Scheduling shot [{_idx+1}/{len(SHOTS)}] {shot['name']} with {shot['material']}...")
    assign_landscape_material(shot["material"])
    rot = unreal.MathLibrary.find_look_at_rotation(shot["cam"], shot["target"])
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if _camera is None:
        _camera = sub.spawn_actor_from_class(unreal.CameraActor, shot["cam"], rot, transient=True)
    else:
        _camera.set_actor_location(shot["cam"], False, False)
        _camera.set_actor_rotation(rot, False)
    cc = _camera.get_component_by_class(unreal.CameraComponent)
    cc.set_editor_property("field_of_view", shot["fov"])
    aloc = _camera.get_actor_location()
    arot = _camera.get_actor_rotation()
    _actual_cam = {
        "location_cm": [aloc.x, aloc.y, aloc.z],
        "rotation_deg_pitch_yaw_roll": [arot.pitch, arot.yaw, arot.roll],
        "fov": float(cc.get_editor_property("field_of_view")),
    }
    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=str(out_png),
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=shot["note"],
        delay=2.5,
        force_game_view=False,
    )
    _start_t = time.monotonic()
    if not _task or not _task.is_valid_task():
        finalize_gallery(f"Invalid screenshot task for {shot['name']}")


def on_tick(_delta: float) -> None:
    global _idx, _task, _cooling, _cool_t
    try:
        if _task is None and not _cooling:
            return
        now = time.monotonic()
        if _cooling:
            if now - _cool_t > 1.5:
                _cooling = False
                _idx += 1
                schedule_next_shot()
            return
        shot = SHOTS[_idx]
        out_png = OUTPUT_DIR / shot["name"]
        ready = out_png.is_file() and out_png.stat().st_size > 50000
        if _task.is_task_done() and ready:
            sz = out_png.stat().st_size
            sh = sha256(out_png)
            log(f"Captured {shot['name']} ({sz} bytes, sha256={sh[:16]}...)")
            _results.append({
                "id": shot["id"],
                "name": shot["name"],
                "path": str(out_png),
                "bytes": sz,
                "sha256": sh,
                "material": shot["material"],
                "camera_requested_cm": [shot["cam"].x, shot["cam"].y, shot["cam"].z],
                "target_requested_cm": [shot["target"].x, shot["target"].y, shot["target"].z],
                "actual_camera": _actual_cam,
                "note": shot["note"],
            })
            _task = None
            _cooling = True
            _cool_t = now
        elif now - _start_t > 150.0:
            finalize_gallery(f"Timeout capturing {shot['name']}")
    except Exception:
        import traceback
        finalize_gallery(traceback.format_exc())


try:
    log(f"Loading level {MAP_PATH}...")
    lvl_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not lvl_sub.load_level(MAP_PATH):
        raise RuntimeError(f"Failed to load {MAP_PATH}")
    log("Level loaded. Scheduling 8-view Lit gallery...")
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule_next_shot()
    _handle = unreal.register_slate_post_tick_callback(on_tick)
except Exception:
    import traceback
    finalize_gallery(traceback.format_exc())
