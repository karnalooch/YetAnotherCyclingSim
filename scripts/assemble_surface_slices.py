"""Assemble selected original Lesson07 slices into a new offline directory.

The current repair selects Grass and Cliffs only. Grass2 in this historical
assembler predates the accepted limestone replacement; do not re-import it.
Colour encoding, 2K sizing and the existing neutral AO/height are preserved.
No Unreal assets, geographic masks or terrain are written by this adapter.

Matching normal families follow SideFX Landscape Material / 6 Functions,
10:21--11:41 (https://vimeo.com/891366382). Packed roughness is a channel,
not RGB luminance: https://pillow.readthedocs.io/en/stable/reference/Image.html
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from PIL import __version__ as PILLOW_VERSION

PROJECT_DIR = Path("D:/yacs/project")
STAGE3G_DIR = Path("D:/yacs/work/lesson07-unified-20261019/stage3g_exported")
SCREE_DIR = Path("D:/yacs/work/lesson05-material-forge-20261018/run-a/mediterranean_soil/limestone_scree_v1/export")
TARGET_SIZE = (2048, 2048)
CLASS_ORDER = ("Grass", "Grass2", "Sand", "Cliffs", "Scree")
# Hash provenance: source-backup.json and local-inventory.json under
# docs/experiments/sa-calobra-material-repair-20261006/. The renamed Grass and
# Cliffs roughness inputs are packed ARM and ORM respectively, not grayscale.
MATCHED_NORMALS = {
    "Grass": Path("worldgen/materials/scanned_refinement/source/aerial_grass_rock_nor_dx_4k.png"),
    "Cliffs": Path("worldgen/materials/material_maker/surface_set/scree/export/SaCalobra_PaleLimestone_Normal_DX.png"),
}
MATCHED_SOURCE_SHA256 = {
    "Grass": {
        "colour": "719cffbc6f7cfec846cc2ba9610228dce5475cd2677f19f462bec6edc3e30ad9",
        "normal": "90219e6e47a750758cd55b5456961dccec0fd4a6ceeaa198a81fa9c36198d11b",
        "packed": "5423503ba94f8e16ced4615cfa05893ec76b3df65cf85be9c8c07201efd5be90",
    },
    "Cliffs": {
        "colour": "6babc8e49248be89b464605c3c9cf427b63ac51ab42aebc05877359e902256e1",
        "normal": "2e75301f9325efb39f37811409bebfd455d9e21bf740ca97d12ed66978290f62",
        "packed": "919faf3cbf33250dd100b6c5e13f8036dd6e2222b29c46b7e09fb8a5c6465df1",
    },
}


def load_rgba(p, target_size=None):
    target_size = TARGET_SIZE if target_size is None else target_size
    with Image.open(p) as im:
        if im.size != target_size:
            im = im.resize(target_size, Image.Resampling.LANCZOS)
        return im.convert("RGBA")


def load_l(p, target_size=None, *, channel=None):
    """Read grayscale, or one explicit packed-data band without a colour mix."""
    target_size = TARGET_SIZE if target_size is None else target_size
    with Image.open(p) as im:
        if channel is not None and im.mode not in {"RGB", "RGBA"}:
            raise ValueError(f"Packed {channel} input must be RGB or RGBA: {p}")
        if im.size != target_size:
            im = im.resize(target_size, Image.Resampling.LANCZOS)
        return im.getchannel(channel) if channel is not None else im.convert("L")


def neutral_masks(roughness):
    """Retain AO=1 and height=128/255; neither is taken from packed metallic."""
    rough = np.asarray(roughness)
    ao = np.full_like(rough, 255)
    height = np.full_like(rough, 128)
    return Image.fromarray(np.stack([ao, rough, height, ao], axis=-1))


def height_to_normal(height_img, strength=2.0):
    # Retained Sand adapter: periodic central differences, not a Sobel kernel.
    h = np.array(height_img, dtype=np.float32) / 255.0
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5
    # DirectX normal map has Y pointing down
    gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    
    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(nx)
    
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    nx /= norm
    ny /= norm
    nz /= norm
    
    # Map [-1, 1] to [0, 255]
    r = np.uint8(np.clip((nx * 0.5 + 0.5) * 255.0, 0, 255))
    g = np.uint8(np.clip((ny * 0.5 + 0.5) * 255.0, 0, 255))
    b = np.uint8(np.clip((nz * 0.5 + 0.5) * 255.0, 0, 255))
    a = np.full_like(r, 255)
    
    return Image.fromarray(np.stack([r, g, b, a], axis=-1), mode="RGBA")


def assemble(out_dir, classes, *, project_dir=PROJECT_DIR,
             stage3g_dir=STAGE3G_DIR, scree_dir=SCREE_DIR):
    """Create only requested slices; an existing output is never overwritten."""
    classes = tuple(classes)
    if not classes or len(classes) != len(set(classes)) or set(classes) - set(CLASS_ORDER):
        raise ValueError("Select distinct known classes explicitly")
    out_dir = Path(out_dir)
    if out_dir.exists():
        raise FileExistsError(f"Output must be a new directory: {out_dir}")
    project_dir, stage3g_dir, scree_dir = map(Path, (project_dir, stage3g_dir, scree_dir))
    tex_dir = project_dir / "worldgen/houdini/sa_calobra/inputs/textures"
    inputs = {}

    def source(path, expected_sha256=None):
        path = Path(path)
        with path.open("rb") as stream:
            inputs[str(path)] = {
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                "size_bytes": path.stat().st_size,
            }
        if expected_sha256 is not None and inputs[str(path)]["sha256"] != expected_sha256:
            raise ValueError(f"Source hash differs from the retained matching surface: {path}")
        return path

    # Fail before producing any candidate files if a renamed source or its
    # matching normal has drifted, is missing, or is still an LFS pointer.
    matched_sources = {}
    for class_name in classes:
        if class_name not in MATCHED_NORMALS:
            continue
        stem = "SaCalobra_Grass" if class_name == "Grass" else "SaCalobra_PaleLimestone"
        paths = {
            "colour": tex_dir / f"{stem}_BaseColor.png",
            "normal": project_dir / MATCHED_NORMALS[class_name],
            "packed": tex_dir / f"{stem}_Roughness.png",
        }
        matched_sources[class_name] = {
            role: source(path, MATCHED_SOURCE_SHA256[class_name][role])
            for role, path in paths.items()
        }
    out_dir.mkdir(parents=True, exist_ok=False)
    for class_name in CLASS_ORDER:
        if class_name not in classes:
            continue
        slot = CLASS_ORDER.index(class_name)
        prefix = f"slice_{slot}_{class_name.lower()}"
        if class_name in MATCHED_NORMALS:
            paths = matched_sources[class_name]
            colour = load_rgba(paths["colour"])
            normal = load_rgba(paths["normal"])
            # Grass is Poly Haven ARM; Cliffs is Material Maker ORM. Both have
            # roughness in G. Keep the established neutral AO/height unchanged.
            rough = load_l(paths["packed"], channel="G")
            masks = neutral_masks(rough)
        elif class_name == "Grass2":
            colour = load_rgba(source(stage3g_dir / "T_Stage3G_HighAlpine_BaseColor.png"))
            normal = load_rgba(source(stage3g_dir / "T_Stage3G_HighAlpine_Normal.png"))
            masks = neutral_masks(Image.new("L", TARGET_SIZE, 200))
        elif class_name == "Sand":
            colour = load_rgba(source(tex_dir / "coast_sand_01_diff_2k.jpg"))
            displacement = load_l(source(tex_dir / "coast_sand_01_disp_2k.png"))
            normal = height_to_normal(displacement, strength=2.5)
            rough = np.asarray(load_l(source(tex_dir / "coast_sand_01_rough_2k.jpg")))
            ao = np.full_like(rough, 255)
            masks = Image.fromarray(np.stack([ao, rough, np.asarray(displacement), ao], axis=-1))
        else:  # Scree: retained Lesson05 Material Forge packing.
            colour = load_rgba(source(scree_dir / "YACS_Material_BaseColor.png"))
            normal = load_rgba(source(scree_dir / "YACS_Material_Normal_DX.png"))
            orm = np.asarray(load_rgba(source(scree_dir / "YACS_Material_ORM.png")))
            try:
                import OpenImageIO as oi
            except ImportError as exc:
                raise RuntimeError("OpenImageIO is required for the retained Scree Height EXR") from exc
            height_exr = source(scree_dir / "YACS_Material_Height.exr")
            reader = oi.ImageInput.open(str(height_exr))
            if reader is None:
                raise RuntimeError(f"Missing scree Height EXR: {height_exr}")
            try:
                height_pixels = np.asarray(reader.read_image(format=oi.FLOAT), dtype=np.float32)
            finally:
                reader.close()
            if height_pixels.ndim == 3:
                height_pixels = height_pixels[:, :, 0]
            if height_pixels.ndim != 2 or not np.isfinite(height_pixels).all():
                raise RuntimeError("Scree height EXR must contain finite 2D data")
            mn, mx = float(height_pixels.min()), float(height_pixels.max())
            if mn < -1e-4 or mx > 1.0001:
                raise RuntimeError(f"Scree height EXR range [{mn}, {mx}] is not [0,1]; verify L05 contract")
            height = Image.fromarray(np.uint8(np.rint(np.clip(height_pixels, 0, 1) * 255)))
            if height.size != TARGET_SIZE:
                height = height.resize(TARGET_SIZE, Image.Resampling.BILINEAR)
            masks = Image.fromarray(np.stack([orm[:, :, 0], orm[:, :, 1], np.asarray(height),
                                             orm[:, :, 0]], axis=-1))
        for channel, image in (("colour", colour), ("normal", normal), ("masks", masks)):
            image.save(out_dir / f"{prefix}_{channel}.png")
    outputs = {}
    for path in sorted(out_dir.glob("*.png")):
        with path.open("rb") as stream:
            outputs[path.name] = {
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                "size_bytes": path.stat().st_size,
            }
    receipt = {
        "status": "OFFLINE_SLICES_ASSEMBLED_UE_IMPORT_PENDING",
        "producer_versions": {"python": sys.version.split()[0],
                              "pillow": PILLOW_VERSION, "numpy": np.__version__},
        "classes": [name for name in CLASS_ORDER if name in classes],
        "size": list(TARGET_SIZE),
        "inputs": inputs,
        "outputs": outputs,
        "classification_changed": False,
        "terrain_changed": False,
        "native_ue_verified": False,
        "visual_accepted": False,
    }
    (out_dir / "assembly-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes", choices=CLASS_ORDER, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=PROJECT_DIR)
    args = parser.parse_args()
    print(json.dumps(assemble(args.output, args.classes, project_dir=args.project), indent=2))


if __name__ == "__main__":
    main()
