"""Native SideFX transfer of the verified Sa Calobra Unified terrain into UE tiles.

Extracts 4 seamless 8129 x 8129 tiles at native 0.5 m spacing from the accepted
unified cache (D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc).
Domain bounds: [-4064, +4064] m in X and Z, covering the full 8000 x 8000 m domain.
"""
import hashlib
import os
import shutil
import json
from pathlib import Path
import time
import hou
import numpy as np

from l07_tile_invariants import compare_all_four, interpolate_bilinear, mask_padding

SOURCE_CACHE = Path("D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc")
OUTPUT_DIR = Path(os.environ.get("YACS_LESSON07_EXPORT_DIR", "D:/yacs/work/lesson07-ue-transfer-repair-20261020")).resolve()
PINNED_L06_SHA256 = "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
PINNED_L06_BYTES = 4808520505

MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
REVIEW_MATERIAL = "/Game/Worlds/SaCalobra_Houdini_20261016/Materials/M_TerrainReview.M_TerrainReview"
# SideFX Houdini Engine 22 uses this primitive attribute for Landscape
# holes. Empty is allowed for source-only proof but forbids production bake.
HOLE_MATERIAL = os.environ.get("YACS_LESSON07_MASKED_HOLE_MATERIAL", "")
if HOLE_MATERIAL and not HOLE_MATERIAL.startswith("/Game/"):
    raise RuntimeError("Hole material must be an Unreal /Game/ asset path")
BAKE_FOLDER = "/Game/Generated/YACS/Lesson07_Unified/Baked"

def attr(parent, name, inp, values):
    a = parent.createNode("attribcreate::2.0", name, exact_type_name=True)
    a.setInput(0, inp)
    a.parm("numattr").set(len(values))
    for i, (key, value) in enumerate(values.items(), 1):
        a.parm(f"name{i}").set(key)
        a.parm(f"class{i}").set(1) # Primitive
        if isinstance(value, str):
            a.parm(f"type{i}").set(3) # String
            a.parm(f"string{i}").set(value)
        elif isinstance(value, int):
            a.parm(f"type{i}").set(1) # Integer
            a.parm(f"value{i}v1").set(value)
        elif isinstance(value, float):
            a.parm(f"type{i}").set(0) # Float
            a.parm(f"value{i}v1").set(value)
    return a

def main():
    start_time = time.time()
    print("=== STARTING PREPARATION OF LESSON 07 UE TRANSFER TILES ===")
    work_root = Path("D:/yacs/work").resolve()
    if work_root not in OUTPUT_DIR.parents or OUTPUT_DIR.exists():
        raise RuntimeError("L07 output must be a NEW directory below D:/yacs/work")
    free_gib = shutil.disk_usage(work_root).free / (1024 ** 3)
    if free_gib < 30:
        raise RuntimeError(f"Need 30 GiB free for L07 transfer, got {free_gib:.2f}")
    if not SOURCE_CACHE.is_file() or SOURCE_CACHE.stat().st_size != PINNED_L06_BYTES:
        raise RuntimeError("Accepted L06 cache missing or size mismatch")
    with SOURCE_CACHE.open("rb") as stream:
        accepted_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if accepted_sha != PINNED_L06_SHA256:
        raise RuntimeError("Accepted L06 cache hash mismatch, refusing export")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    print(f"Accepted L06 SHA256 pinned: {accepted_sha}")
    
    geo = hou.node("/obj").createNode("geo", "UNIFIED_UE_TRANSFER", run_init_scripts=False)
    
    # 1. Load verified unified cache and isolate height layer
    src = geo.createNode("file", "SOURCE_UNIFIED")
    src.parm("file").set(str(SOURCE_CACHE).replace("\\", "/"))
    
    height_only = geo.createNode("blast", "HEIGHT_AND_ALPHA")
    height_only.setInput(0, src)
    height_only.parm("group").set("@name=height @name=Alpha")
    height_only.parm("negate").set(1)
    
    source_geo = src.geometry()
    source_volumes = {p.attribValue("name"): p for p in source_geo.prims()
                      if isinstance(p, hou.Volume)}
    if not {"height", "Alpha"}.issubset(source_volumes):
        raise RuntimeError("Source L06 cache must contain height and Alpha")
    source_height = source_volumes["height"]
    xres, zres, depth = source_height.resolution()
    if (xres, zres, depth) != (16000, 16000, 1):
        raise RuntimeError("L06 accepted source is not 16000x16000x1")
    first = source_height.indexToPos((0, 0, 0))
    last = source_height.indexToPos((xres - 1, zres - 1, 0))
    src_x = sorted((float(first[0]), float(last[0])))
    src_z = sorted((float(first[2]), float(last[2])))
    # Tile definitions:
    # ix=0: tx = -2032.25, ix=1: tx = +2031.75
    # iy=0: tz = -2032.25, iy=1: tz = +2031.75
    # Width and Depth = 4064.0 m (8128 quads * 0.5 m = 8129 vertices)
    tile_configs = [
        {"ix": 0, "iy": 0, "tx": -2032.25, "tz": -2032.25, "name": "SaCalobra_Unified_0_0"},
        {"ix": 1, "iy": 0, "tx": +2031.75, "tz": -2032.25, "name": "SaCalobra_Unified_1_0"},
        {"ix": 0, "iy": 1, "tx": -2032.25, "tz": +2031.75, "name": "SaCalobra_Unified_0_1"},
        {"ix": 1, "iy": 1, "tx": +2031.75, "tz": +2031.75, "name": "SaCalobra_Unified_1_1"},
    ]
    
    tiles_manifest = []
    arrays = {}
    masks = {}
    world_coords = {}
    
    for cfg in tile_configs:
        name = cfg["name"]
        ix, iy = cfg["ix"], cfg["iy"]
        tx, tz = cfg["tx"], cfg["tz"]
        print(f"\nProcessing {name} (ix={ix}, iy={iy}, tx={tx}, tz={tz})...")
        
        # Crop directly from unified heightfield preserving orientation and voxel data
        crop = geo.createNode("heightfield_crop", f"{name}_CROP")
        crop.setInput(0, height_only)
        crop.parm("cropmode").set(0) # Center & Size
        crop.parm("sizex").set(4064.0)
        crop.parm("sizey").set(4064.0)
        crop.parm("tx").set(tx)
        crop.parm("tz").set(tz)
        
        # Add Unreal Engine attributes
        attrs = {
            "unreal_output_name": name,
            "unreal_bake_name": name,
            "unreal_bake_folder": BAKE_FOLDER,
            "unreal_landscape_section_size": 127,
            "unreal_landscape_sections_per_component": 2,
            "unreal_landscape_layer_min": -5.0,
            "unreal_landscape_layer_max": 1500.0,
            "unreal_landscape_editlayer_name": "Houdini_Unified_Final",
            "unreal_material": REVIEW_MATERIAL,
            # Opaque review material is not a hole/visibility shader.
            "unreal_uproperty_tag_source": "SaCalobra_Unified_Lesson07",
        }
        if HOLE_MATERIAL:
            # Official Houdini Engine 22 spelling: unreal_material_hole.
            attrs["unreal_material_hole"] = HOLE_MATERIAL
        attributed = attr(geo, f"{name}_ATTRS", crop, attrs)
        attributed.cook(force=True)
        if attributed.errors():
            raise RuntimeError(f"Cook error on {name}: {attributed.errors()}")
            
        g = attributed.geometry().freeze()
        layers = {p.attribValue("name"): p for p in g.prims()
                  if isinstance(p, hou.Volume)}
        if set(layers) != {"height", "Alpha"}:
            raise RuntimeError(f"{name}: expected height + Alpha, got {sorted(layers)}")
        validity = layers["Alpha"]
        validity.setAttribValue("name", "visibility")
        # Houdini Engine uses prim min/max settings for masks too.
        # Height remains [-5, 1500], visibility must be mapped from [0, 1].
        validity.setAttribValue("unreal_landscape_layer_min", 0.0)
        validity.setAttribValue("unreal_landscape_layer_max", 1.0)
        prim = layers["height"]
        res = prim.resolution()
        if res != (8129, 8129, 1):
            raise RuntimeError(f"{name}: expected 8129x8129 native tile, got {res}")
        
        pos0 = tuple(prim.indexToPos((0, 0, 0)))
        pos_max = tuple(prim.indexToPos((res[0] - 1, res[1] - 1, 0)))
        bbox = prim.boundingBox()
        raw_mask = np.frombuffer(
            validity.allVoxelsAsString(), dtype=np.float32
        ).reshape(res[1], res[0])
        mask, padded_count = mask_padding(
            raw_mask, pos0, pos_max, src_x, src_z
        )
        validity.setAllVoxelsFromString(
            np.ascontiguousarray(mask, dtype=np.float32).tobytes()
        )
        valid_count = int(np.count_nonzero(mask > 0.5))
        invalid_count = int(mask.size - valid_count)
        arr = np.frombuffer(prim.allVoxelsAsString(), dtype=np.float32).reshape(res[1], res[0])
        arrays[(ix, iy)] = arr.copy()
        masks[(ix, iy)] = mask
        world_coords[(ix, iy)] = (pos0, pos_max)
        
        out_filename = f"{name}.bgeo.sc"
        out_path = OUTPUT_DIR / out_filename
        print(f"  Saving to {out_path}...")
        g.saveToFile(str(out_path).replace("\\", "/"))
        
        # Stream multi-gigabyte file hashing; do not allocate entire file in RAM.
        with out_path.open("rb") as stream:
            file_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        
        tile_info = {
            "name": name,
            "ix": ix,
            "iy": iy,
            "file": out_filename,
            "resolution": list(res),
            "pos0": [float(x) for x in pos0],
            "pos_max": [float(x) for x in pos_max],
            "bounds": {
                "min": [float(x) for x in bbox.minvec()],
                "max": [float(x) for x in bbox.maxvec()],
            },
            "elevation_min_m": float(arr.min()),
            "elevation_max_m": float(arr.max()),
            "sha256": file_sha256,
            "visibility": {
                "layer": "visibility", "source": "Alpha",
                "valid_samples": valid_count,
                "invalid_samples": invalid_count,
                "padded_samples": padded_count,
                "outside_source_zero": True,
                "ue_masked_material_verified": False,
                "requested_hole_material": HOLE_MATERIAL or None,
                "mask_export_range": [0.0, 1.0],
                "pixel_registration_ue_verified": False,
            },
        }
        tiles_manifest.append(tile_info)
        print(f"  Done: min={tile_info['elevation_min_m']:.2f} m, max={tile_info['elevation_max_m']:.2f} m, sha256={file_sha256[:12]}...")

    # Compare physically identical world-coordinate edges, including
    # alternate Houdini volume-row orientation and the visibility layer.
    print("\n=== VERIFYING NATIVE L07 WORLD-COORDINATE SEAMS ===")
    height_tiles = {
        key: (value, *world_coords[key]) for key, value in arrays.items()
    }
    mask_tiles = {
        key: (value, *world_coords[key]) for key, value in masks.items()
    }
    height_seams = compare_all_four(height_tiles, tolerance_m=0.0001)
    mask_seams = compare_all_four(mask_tiles, tolerance_m=1.0 / 255.0)
    max_seam_error = max(v["sample_error"] for v in height_seams.values())
    for side, stats in height_seams.items():
        print(f"  {side}: height={stats['sample_error']:.7f}m "
              f"world-position={stats['position_error_m']:.7f}m")
    # The point (0,0) is off the source's 0.5m lattice. Compare later to
    # an interpolated native reference, not the rounded 473.51m receipt.
    origin_reference_m = interpolate_bilinear(
        arrays[(1, 1)], *world_coords[(1, 1)], 0.0, 0.0
    )
    print(f"  Source center interpolation: {origin_reference_m:.6f} m")
    print("  4 exact world-aligned seams verified.")

    # Verify landmarks against source cache
    print("\n=== VERIFYING LANDMARK ELEVATIONS ===")
    src_geo = src.geometry()
    src_prim = next(p for p in src_geo.prims() if p.attribValue("name") == "height")
    
    landmarks = [
        {"name": "Puig Major peak", "x": -1283.75, "z": 3495.25, "tile": (0, 1)},
        {"name": "Sa Calobra cove", "x": 470.0, "z": -1060.0, "tile": (1, 0)},
        {"name": "Scree patch", "x": 2179.25, "z": 262.25, "tile": (1, 1)},
    ]
    landmark_results = []
    for lm in landmarks:
        vec = hou.Vector3(lm["x"], 0, lm["z"])
        src_val = float(src_prim.sample(vec))
        ix, iy = lm["tile"]
        tile_name = f"SaCalobra_Unified_{ix}_{iy}"
        tile_node = geo.node(f"{tile_name}_ATTRS")
        tile_prim = next(p for p in tile_node.geometry().prims() if p.attribValue("name") == "height")
        tile_val = float(tile_prim.sample(vec))
        diff = abs(src_val - tile_val)
        print(f"  {lm['name']}: src={src_val:.4f} m, tile={tile_val:.4f} m, diff={diff:.8f} m")
        assert diff < 0.001, f"Elevation mismatch on {lm['name']}: src={src_val}, tile={tile_val}"
        landmark_results.append({
            "name": lm["name"],
            "coord": [lm["x"], lm["z"]],
            "source_elevation_m": src_val,
            "tile_elevation_m": tile_val,
            "difference_m": diff,
        })

    manifest = {
        "status": "NATIVE_TRANSFER_READY_UE_VALIDATION_PENDING",
        "accepted_l06_sha256": accepted_sha,
        "output_policy": "NEW_DIRECTORY_NO_OVERWRITE",
        "masked_material_ue_verified": False,
        "requested_hole_material": HOLE_MATERIAL or None,
        "performance_1080p60_verified": False,
        "duration_seconds": time.time() - start_time,
        "source_cache": str(SOURCE_CACHE).replace("\\", "/"),
        "tiles": tiles_manifest,
        "seam_verification": {
            "height_world_aligned": height_seams,
            "visibility_world_aligned": mask_seams,
            "max_height_seam_error_m": max_seam_error,
            "seams_perfect": True,
            "accepted_l06_center_0_0_bilinear_m": origin_reference_m,
            "center_0_0_ue_collision_verified": False,
        },
        "landmark_verification": landmark_results,
    }
    
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest written to {MANIFEST_PATH}")
    print("=== PREPARATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
