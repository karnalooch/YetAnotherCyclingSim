import numpy as np
from PIL import Image
from pathlib import Path

out_dir = Path("D:/yacs/work/lesson07-unified-20261019/assembled_slices")
out_dir.mkdir(parents=True, exist_ok=True)

tex_dir = Path("D:/yacs/project/worldgen/houdini/sa_calobra/inputs/textures")
stage3g_dir = Path("D:/yacs/work/lesson07-unified-20261019/stage3g_exported")
scree_dir = Path("D:/yacs/work/lesson05-material-forge-20261018/run-a/mediterranean_soil/limestone_scree_v1/export")

def load_rgba(p, target_size=(2048, 2048)):
    im = Image.open(p)
    if im.size != target_size:
        im = im.resize(target_size, Image.Resampling.LANCZOS)
    return im.convert("RGBA")

def load_l(p, target_size=(2048, 2048)):
    im = Image.open(p)
    if im.size != target_size:
        im = im.resize(target_size, Image.Resampling.LANCZOS)
    return im.convert("L")

def height_to_normal(height_img, strength=2.0):
    # Sobel filter to create DirectX tangent-space normal map
    h = np.array(height_img, dtype=np.float32) / 255.0
    # Sobel gradients
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

# --- Class 0: Grass ---
print("Assembling Class 0: Grass...")
c0_col = load_rgba(tex_dir / "SaCalobra_Grass_BaseColor.png")
c0_col.save(out_dir / "slice_0_grass_colour.png")

c0_norm = load_rgba(stage3g_dir / "T_Stage3G_Meadow_Normal.png")
c0_norm.save(out_dir / "slice_0_grass_normal.png")

c0_rough = np.array(load_l(tex_dir / "SaCalobra_Grass_Roughness.png"))
c0_ao = np.full_like(c0_rough, 255)
c0_disp = np.full_like(c0_rough, 128)
c0_masks = Image.fromarray(np.stack([c0_ao, c0_rough, c0_disp, c0_ao], axis=-1), mode="RGBA")
c0_masks.save(out_dir / "slice_0_grass_masks.png")

# --- Class 1: Grass 2 (High Alpine / Tundra) ---
print("Assembling Class 1: Grass 2...")
c1_col = load_rgba(stage3g_dir / "T_Stage3G_HighAlpine_BaseColor.png")
c1_col.save(out_dir / "slice_1_grass2_colour.png")

c1_norm = load_rgba(stage3g_dir / "T_Stage3G_HighAlpine_Normal.png")
c1_norm.save(out_dir / "slice_1_grass2_normal.png")

c1_rough = np.full((2048, 2048), 200, dtype=np.uint8)
c1_ao = np.full_like(c1_rough, 255)
c1_disp = np.full_like(c1_rough, 128)
c1_masks = Image.fromarray(np.stack([c1_ao, c1_rough, c1_disp, c1_ao], axis=-1), mode="RGBA")
c1_masks.save(out_dir / "slice_1_grass2_masks.png")

# --- Class 2: Sand ---
print("Assembling Class 2: Sand...")
c2_col = load_rgba(tex_dir / "coast_sand_01_diff_2k.jpg")
c2_col.save(out_dir / "slice_2_sand_colour.png")

sand_disp = load_l(tex_dir / "coast_sand_01_disp_2k.png")
c2_norm = height_to_normal(sand_disp, strength=2.5)
c2_norm.save(out_dir / "slice_2_sand_normal.png")

c2_rough = np.array(load_l(tex_dir / "coast_sand_01_rough_2k.jpg"))
c2_disp_arr = np.array(sand_disp)
c2_ao = np.full_like(c2_rough, 255)
c2_masks = Image.fromarray(np.stack([c2_ao, c2_rough, c2_disp_arr, c2_ao], axis=-1), mode="RGBA")
c2_masks.save(out_dir / "slice_2_sand_masks.png")

# --- Class 3: Cliffs ---
print("Assembling Class 3: Cliffs...")
c3_col = load_rgba(tex_dir / "SaCalobra_PaleLimestone_BaseColor.png")
c3_col.save(out_dir / "slice_3_cliffs_colour.png")

c3_norm = load_rgba(stage3g_dir / "T_Stage3G_Boulder_Normal.png")
c3_norm.save(out_dir / "slice_3_cliffs_normal.png")

c3_rough = np.array(load_l(tex_dir / "SaCalobra_PaleLimestone_Roughness.png"))
c3_ao = np.full_like(c3_rough, 255)
c3_disp = np.full_like(c3_rough, 128)
c3_masks = Image.fromarray(np.stack([c3_ao, c3_rough, c3_disp, c3_ao], axis=-1), mode="RGBA")
c3_masks.save(out_dir / "slice_3_cliffs_masks.png")

# --- Class 4: Scree (Mediterranean limestone scree from Lesson 05) ---
print("Assembling Class 4: Scree...")
c4_col = load_rgba(scree_dir / "YACS_Material_BaseColor.png")
c4_col.save(out_dir / "slice_4_scree_colour.png")

c4_norm = load_rgba(scree_dir / "YACS_Material_Normal_DX.png")
c4_norm.save(out_dir / "slice_4_scree_normal.png")

# Assemble Pegasus masks according to original master contract:
# R = Ambient Occlusion, G = Roughness, B = Displacement/Height, A = Ambient Occlusion / 255
c4_orm = np.array(load_rgba(scree_dir / "YACS_Material_ORM.png"))
c4_ao = c4_orm[:, :, 0]
c4_rough = c4_orm[:, :, 1]
# Derive the slice deterministically from the retained Material Forge EXR,
# rather than a temporary scree_height_test.png removed from the workspace.
try:
    import OpenImageIO as oi
except ImportError as exc:
    raise RuntimeError(
        "Use D:/yacs/tools/houdini-22.0.466/bin/hython.exe "
        "to assemble the EXR-based scree masks (OpenImageIO required)."
    ) from exc
height_exr = scree_dir / "YACS_Material_Height.exr"
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
height_image = Image.fromarray(
    np.uint8(np.rint(np.clip(height_pixels, 0, 1) * 255)), mode="L"
)
if height_image.size != (2048, 2048):
    height_image = height_image.resize((2048, 2048), Image.Resampling.BILINEAR)
c4_disp = np.asarray(height_image)
c4_masks = Image.fromarray(np.stack([c4_ao, c4_rough, c4_disp, c4_ao], axis=-1), mode="RGBA")
c4_masks.save(out_dir / "slice_4_scree_masks.png")

print("ALL 5 CLASSES ASSEMBLED SUCCESSFULLY!")
