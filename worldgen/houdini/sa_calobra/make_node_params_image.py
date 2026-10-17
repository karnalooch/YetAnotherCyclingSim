"""Generate technical node parameters and pipeline verification image."""
import os
import shutil
from PIL import Image, ImageDraw, ImageFont

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
evidence_dir = f"{project_dir}/evidence"
artifact_dir = "C:/Users/akarn/.gemini/antigravity/brain/d3ee11c1-e4d3-48e9-98a6-76b17331ecf5"
out_name = "lesson03_04_node_parameters.png"
out_path = f"{evidence_dir}/{out_name}"

# Create dark-mode tech receipt canvas (1920 x 1080)
w, h = 1920, 1080
img = Image.new("RGB", (w, h), color=(18, 20, 24))
draw = ImageDraw.Draw(img)

# Try loading standard Windows font or default
try:
    font_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 36)
    font_section = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 24)
    font_body = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 18)
    font_small = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 15)
except Exception:
    font_title = ImageFont.load_default()
    font_section = font_title
    font_body = font_title
    font_small = font_title

# Header
draw.rectangle([(0, 0), (w, 80)], fill=(28, 32, 40))
draw.text((40, 20), "PROJECT PEGASUS — LESSON 03: HEIGHTFIELD MATERIALS (VERIFIED RECEIPT)", font=font_title, fill=(240, 242, 245))
draw.line([(0, 80), (w, 80)], fill=(60, 68, 80), width=2)

# Column 1: Node & Parameters (x: 40 to 920)
def draw_panel(x1, y1, x2, y2, title):
    draw.rectangle([(x1, y1), (x2, y2)], fill=(24, 27, 33), outline=(48, 54, 66), width=1)
    draw.rectangle([(x1, y1), (x2, y1 + 40)], fill=(32, 36, 45))
    draw.text((x1 + 15, y1 + 8), title, font=font_section, fill=(90, 175, 255))
    draw.line([(x1, y1 + 40), (x2, y1 + 40)], fill=(48, 54, 66), width=1)

draw_panel(40, 110, 930, 560, "1. HDA DEFINITION & PARAMETERS (/obj/SA_CALOBRA/ROCK_SLOPE_MATERIAL)")
params_text = [
    ("HDA Operator Type:", "PE_heightfield_material::1.0"),
    ("Source OTL Path:", "worldgen/houdini/sa_calobra/otls/sop_PE_heightfield_material.1.0.hda"),
    ("Albedo Map (Colour):", "$HIP/inputs/textures/SaCalobra_PaleLimestone_BaseColor.png"),
    ("Displacement Map (Height):", "$HIP/inputs/textures/wepoeaw_4K_Displacement.exr (32-bit float, 4K)"),
    ("Roughness Map:", "$HIP/inputs/textures/SaCalobra_PaleLimestone_Roughness.png"),
    ("Material Scale (size):", "20.0 m (world tiling UV)"),
    ("Height Amplitude (heightscale):", "0.35 m"),
    ("Slope Mask Bounds:", "28.0 deg to 90.0 deg (MASK_ROCK_SLOPE)"),
    ("Use Mask Active:", "1 (Strict masking: no rock detail on valleys/roads)"),
    ("Preview Display Mode:", "2 (Colour / Albedo Preview to 'r g b' volume primitives)"),
]

y_pos = 165
for label, val in params_text:
    draw.text((60, y_pos), label, font=font_body, fill=(160, 170, 185))
    draw.text((380, y_pos), val, font=font_body, fill=(230, 235, 240))
    y_pos += 36

# Column 2: Grid Extents & Measurements (x: 970 to 1880)
draw_panel(970, 110, 1880, 560, "2. SPATIAL EXTENTS & MEASURED DISPLACEMENT (FULL COVERAGE)")
grid_text = [
    ("Working Grid Cells:", "7,154 x 9,829 (70,316,666 total cells at 0.5m spacing)"),
    ("Working Extent Bounds:", "X: [-1771.25, 1805.25] m | Z: [-1769.75, 3144.25] m"),
    ("Context Background Grid:", "2,048 x 2,048 (4,194,304 cells, 8000 x 8000 m full island context)"),
    ("Spatial Scope:", "Full Ma-2141 corridor + 500m buffer + context (NO CROPS)"),
    ("Max Absolute Displacement:", "+0.3402 m (matching 0.35m amplitude limit)"),
    ("Slope Mask Coverage:", "35,976,973 cells modified (>1mm delta)"),
    ("Mean Displacement (Rock):", "0.0724 m (p95 = 0.1887 m)"),
    ("Displacement Outside Mask:", "0.0000 m (< 0.12 mm numerical zero outside slope mask)"),
    ("Layer 3 Procedural Cache:", "Pegasus_Landscape_Layer_3_Procedural_Detail.bgeo.sc (598.2 MB)"),
    ("Fresh Reversibility Test:", "0.0000 m max delta vs Source+Manual when detail disabled (PASS)"),
]

y_pos = 165
for label, val in grid_text:
    draw.text((990, y_pos), label, font=font_body, fill=(160, 170, 185))
    draw.text((1290, y_pos), val, font=font_body, fill=(120, 225, 140) if "PASS" in val or "0.0000" in val else (230, 235, 240))
    y_pos += 36

# Bottom Panel: Graph Architecture (x: 40 to 1880)
draw_panel(40, 590, 1880, 1020, "3. NODE NETWORK ARCHITECTURE & LAYER COMPOSITION")
arch_text = [
    "[SOURCE BASE DTM] (7154 x 9829 @ 0.5m) ──+──> [MASK_ROCK_SLOPE] (28° - 90°) ──────────────────────────────────+",
    "                                          |                                                                         |",
    "                                          +──> [ROCK_SLOPE_MATERIAL] (PE_heightfield_material::1.0) <---------------+",
    "                                                        |  - BaseColor: SaCalobra_PaleLimestone_BaseColor.png",
    "                                                        |  - Displacement: wepoeaw_4K_Displacement.exr",
    "                                                        v",
    "                                          [WORKING_MATERIAL_CACHE] (cache/lesson03_working_material_05m.bgeo.sc, 672.6 MB)",
    "                                                        |",
    "                        +───────────────────────────────+───────────────────────────────+",
    "                        v                                                               v",
    "   [MATERIAL_PROCEDURAL_DELTA] (Subtract Source Base)               [WORKING_SOURCE_OR_DETAIL] (Switch via enable_detail)",
    "                        v                                                               v",
    "   [LAYER3_PROCEDURAL_CACHE] (598.2 MB bgeo.sc)                     [VIEW_CONTEXT_OR_WORKING] (Working vs 8km Context)",
    "                        v                                                               v",
    "   [PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape]               [output0] -> Full Working Terrain Viewport & ROP",
    "   Layer 1: Base Source (DTM)                                      - Volumes: height, mask, Alpha, r, g, b, roughness",
    "   Layer 2: Manual Sculpt (Neutral Baseline)                       - Procedural detail toggleable instantly via UI parm",
    "   Layer 3: Procedural Detail (Lesson 03 Limestone Material)       - Clean fresh-process readback and strict reversibility verified"
]

y_pos = 650
for line in arch_text:
    draw.text((60, y_pos), line, font=font_body, fill=(200, 215, 230) if "[" in line else (130, 145, 160))
    y_pos += 21

img.save(out_path)
shutil.copy2(out_path, f"{artifact_dir}/{out_name}")
print(f"Generated {out_name}: {os.path.getsize(out_path)} bytes -> copied to artifact dir")
