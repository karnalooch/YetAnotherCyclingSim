# Lesson 07: Material Setup — Full Unified Domain Verification

- **Task**: SideFX Project Pegasus Landscape Workflow — Lesson 7 "Material Setup" (PEG-02-07)
- **Domain**: Sa Calobra Unified $16\,000 \times 16\,000$ single-quality domain ($8000 \times 8000\text{ m}$, $0.5\text{ m}$ spacing, $256\,000\,000$ samples)
- **Branch**: `codex/365-world-graph`, Draft PR #474
- **Accepted Base**: `2e1c209995b100fe01af08c39542605cffee9305`
- **Receipt**: [lesson07-material-setup-verification-receipt.json](file:///d:/yacs/project/docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json)
- **Technical Status**: `LESSON07_TECHNICAL_PASS: true`
- **Visual Review**: `PENDING_FINAL_M3_AUDIT`
- **Performance Acceptance**: `DEFERRED_AFTER_M3` (`performance_pass: false`)

---

## 1. Executive Summary

Lesson 7 of the Project Pegasus Landscape Workflow establishes the connection between Houdini heightfield data and Unreal Engine's landscape rendering pipeline. Following the full-domain single-quality unification established in Lesson 06, Lesson 07 delivers:

1. **Houdini Saved Interactive Preview**: A clean checkpoint [SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc](file:///d:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc) reading from `FINAL_CACHE` with 4 instant preview switches (`PREVIEW_GLOBAL_COLOR`, `PREVIEW_NEUTRAL_SHADING`, `PREVIEW_IDMAP`, `PREVIEW_CLASS_ISOLATION`) and 5 saved camera bookmarks.
2. **Procedural Detail Identity**: Procedural height delta cache [procedural_detail.bgeo.sc](file:///D:/yacs/work/lesson07-unified-20261019/procedural_detail.bgeo.sc) computed as $\text{delta} = \text{final\_height} - \text{stage1\_base\_height}$. The exact reconstruction identity $\text{base} + \text{delta} \equiv \text{final}$ is verified across all $256\,000\,000$ samples with maximum error $2.98 \times 10^{-8}\text{ m}$ (float32 precision limit) and $0$ mismatches.
3. **Pegasus Texture Exports**:
   - `T_PE_Terrain_IDMap.png`: $16\,000 \times 16\,000$, 1-channel uint8, strictly containing the 5 authentic Pegasus class codes $[0, 64, 128, 191, 255]$.
   - `T_PE_Terrain_Color.png`: $16\,000 \times 16\,000$, 3-channel uint8 in sRGB color space via `sop_PE_heightfield_RGB_ColorSpace.1.0.hda`, with `@height=0` flattened in the color branch.
4. **Pegasus Material Framework in Unreal Engine 5.8.2**:
   - 15 PBR surface slices assembled at $2048 \times 2048$ covering all 5 semantic classes.
   - Three 5-slice `Texture2DArray` assets created: `TA_Colour_Unified` (sRGB), `TA_Normal_Unified` (Normalmap), and `TA_Masks_Unified` (Masks packing R=AO, G=Roughness, B=Displacement).
   - Material Instance [MI_Landscape_Instance_YACS](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset) derived from `M_Pegasus_Landscape_Master` with all textures, scalars (`Num IDmap Layers=5.0`, `Terrain Resolution=16000.0`, `Global Colour Strength=0.5`).
5. **Durable Map and PBR Lighting**: Level `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` ([L_SaCalobra_Lesson07.umap](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap)) populated with the landscape, assigned `MI_Landscape_Instance_YACS`, configured with `DirectionalLight`, `SkyAtmosphere`, and `SkyLight`. Verified with a clean reload pass ($0$ missing references).
6. **Corroborated Visual Evidence**: 8 high-resolution Houdini diagnostic artifacts and 5 Unreal Engine offscreen renders captured via native `AutomationLibrary.take_high_res_screenshot`.

---

## 2. Original Lesson Mapping & Adaptations

Official tutorial reference: [Project Pegasus Landscape Workflow — 07 | Material Setup](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/) · [Video](https://player.vimeo.com/video/888569514).

| Timestamp Range | Original Tutorial Action | Sa Calobra Unified Adaptation | Rationale & Verification |
|---|---|---|---|
| `01:37` – `03:57` | Subtract source + manual terrain from cooked terrain to isolate procedural height; cache to disk. | Computed $\text{delta} = \text{final\_height} - \text{stage1\_base\_height}$ across the $16\,000 \times 16\,000$ unified grid. Saved to `procedural_detail.bgeo.sc`. | Eliminates Working/Context split. Strict numerical identity verified: $\max |\text{base} + \text{delta} - \text{final}| = 2.98 \times 10^{-8}\text{ m}$. |
| `04:00` – `05:58`<br>*(corr. 07:57–08:06)* | HeightField Output for IDMap: single channel, 8-bit fixed, explicit `id` layer. | Exported [T_PE_Terrain_IDMap.png](file:///D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png) ($16\,000 \times 16\,000$, 1-channel uint8, `[0, 64, 128, 191, 255]`). | Matches Pegasus 8-bit fixed ID contract. Confirmed nearest sampling requirement. |
| `06:00` – `11:54` | Branch RGB color processing, flatten `@height = 0` in color branch only. | Rendered `r, g, b` heightfield volume with `@height=0` flatten pass; exported [T_PE_Terrain_Color.png](file:///D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png). | Keeps terrain geometry unaltered while producing uniform global macro-color map. |
| `11:19` – `11:54` | RGB ColorSpace Linear $\to$ sRGB. Author corrects earlier `RGB Power` mistake. | Applied authentic `sop_PE_heightfield_RGB_ColorSpace.1.0.hda` set to Linear $\to$ sRGB conversion. | Complies with author's correction; prevents gamma distortion in Unreal texture sampler. |
| `12:13` – `14:55` | Unreal Engine landscape setup, reload layer cache, assign `MI_Landscape_Instance` and `Terrain Colour`. | Created durable level `L_SaCalobra_Lesson07.umap`, assigned `MI_Landscape_Instance_YACS`, wired `Terrain Colour`. | Bounded non-destructive level setup with full PBR lighting environment. |
| `14:58` – `17:43` | Terrain ID Map import: Grayscale compression, sRGB off, Nearest filter. | Imported `T_PE_Terrain_IDMap` into UE with `srgb=False`, `compression=TC_Grayscale`, `filter=TF_Nearest`. | Prevents bilinear cross-class interpolation bleed at discrete layer boundaries. |
| `17:45` – `20:46` | Replace placeholder Texture2DArray slices with high-fidelity surface textures. | Built 5-slice arrays (`TA_Colour_Unified`, `TA_Normal_Unified`, `TA_Masks_Unified`) from 15 assembled $2048 \times 2048$ PBR textures. | Complete 5-class coverage: Grass, Grass 2, Sand, Cliffs, Scree (including L05 limestone scree). |
| `20:46` – `22:20` | Color array, `Use Terrain Color`, proper color space configuration. | Enabled global tint mixing (`Global Colour Strength = 0.5`, `Detail Brightness = 1.5`, `Terrain Resolution = 16000.0`). | Balances distant satellite-like global color with intimate surface detail. |
| `22:41` – `25:41` | Validate normal maps and detail masks (roughness, AO, displacement) under sunlight. | Tested directional light response across all classes; verified offscreen in UE offscreen renders. | Plasticity and surface specular response corroborated without dark seams or artifacts. |

---

## 3. Etap A: Houdini Unified Preview & Checkpoint

A dedicated Lesson 07 checkpoint was branched from the closed Lesson 06 baseline:
- **L06 Input Baseline**: [SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc](file:///d:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc) (SHA-256: `7701a844bd82d149...`). Kept $100\%$ untouched.
- **L07 Output Checkpoint**: [SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc](file:///d:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc) (SHA-256: `724ba6e2eb669613...`).

### Interactive Preview Modes
The checkpoint connects directly to `/obj/SA_CALOBRA_UNIFIED/FINAL_CACHE` (reading `final_unified_idmap.bgeo.sc`) and provides 4 switchable tail preview nodes:
1. `PREVIEW_GLOBAL_COLOR`: Default active display node showing the complete 3D terrain shaded with the unified macro-color map.
2. `PREVIEW_NEUTRAL_SHADING`: Neutral geometry shading without color distraction for terrain topology inspection.
3. `PREVIEW_IDMAP`: Direct visualization of the 5 discrete semantic ID classes using the authentic Pegasus color palette.
4. `PREVIEW_CLASS_ISOLATION`: Isolated display of individual classes (default: scree patches isolated via Pegasus `id_to_layer` decoder).

### Verified Camera Bookmarks
Five standard inspection cameras are stored in `/obj`:
- `cam_panorama`: Full-domain overview looking from south to north.
- `cam_puig_major`: Focus on Puig Major peak and crags ($1437.16\text{ m}$).
- `cam_sa_calobra_cove`: Coastal bay showing sea/sand/rock junction.
- `cam_transition`: Coastal transition corridor between grass, sand, and limestone cliffs.
- `cam_scree_site`: Detailed viewpoint on the authentic scree occurrence centroid ($X = -1260.25\text{ m}, Z = 262.25\text{ m}$).

---

## 4. Etap B: Procedural Height Delta & Identity Proof

In accordance with tutorial step `01:37`–`03:57`, the procedural detail layer was extracted:
$$\text{procedural\_delta}(x, z) = \text{final\_height}(x, z) - \text{stage1\_base\_height}(x, z)$$

The result was computed and saved to [procedural_detail.bgeo.sc](file:///D:/yacs/work/lesson07-unified-20261019/procedural_detail.bgeo.sc) ($319\,851\,981\text{ bytes}$).

### Reconstruction Identity Proof
The mathematical identity $\text{base}(x, z) + \text{delta}(x, z) \equiv \text{final}(x, z)$ was tested across all $256\,000\,000$ samples in chunked memory passes:
- **Samples Evaluated**: $256\,000\,000$ ($100\%$ of domain)
- **Mismatches ($> 10^{-6}\text{ m}$)**: $0$
- **Maximum Absolute Difference**: $2.98023 \times 10^{-8}\text{ m}$ (exact float32 epsilon limit)
- **Procedural Delta Statistics**:
  - Minimum: $-0.357757\text{ m}$
  - Maximum: $+0.533264\text{ m}$
  - Mean: $+0.010344\text{ m}$
- **Conclusion**: Perfect numerical identity verified. The procedural detail cache faithfully stores only the procedural delta (erosion, slump, material displacement) without altering the underlying source DTM geometry.

---

## 5. Etap D & E: Texture Exports

Following the Pegasus export workflow (`sop_PE_heightfield_RGB_ColorSpace` and `heightfield_output`):

### IDMap Export ([T_PE_Terrain_IDMap.png](file:///D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png))
- **File**: `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png`
- **SHA-256**: `cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3`
- **Resolution**: $16\,000 \times 16\,000$ ($256\text{ Mpx}$), 1 channel, uint8 fixed ($12\,392\,456\text{ bytes}$)
- **Unique Class Values**: strictly $5$ discrete uint8 values:
  - `0`: Grass ($104\,122\,143$ pixels, $40.67\%$)
  - `64`: Grass 2 ($55\,517\,706$ pixels, $21.69\%$)
  - `128`: Sand ($18\,624\,143$ pixels, $7.28\%$)
  - `191`: Cliffs ($77\,735\,227$ pixels, $30.37\%$)
  - `255`: Scree ($781$ pixels, $0.0003\%$)

### Global Color Export ([T_PE_Terrain_Color.png](file:///D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png))
- **File**: `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png`
- **SHA-256**: `90bd39006ed5f56888ef9a3de887c7840bc8ff9782c11d68062755b516afbb7b`
- **Resolution**: $16\,000 \times 16\,000$ ($256\text{ Mpx}$), 3 channels (RGB), uint8 ($398\,192\,590\text{ bytes}$)
- **Color Space**: sRGB, processed through `sop_PE_heightfield_RGB_ColorSpace.1.0.hda` (Linear $\to$ sRGB)
- **Height Geometry**: Flattened to `@height = 0` in color branch only.

---

## 6. Etap F: Unreal Engine Material Setup

The original Pegasus material framework was configured in Unreal Engine 5.8.2 (`D:/yacs/engine/UE_5.8`):

### Surface Texture Slices ($2048 \times 2048$ uint8)
15 high-fidelity texture slices were prepared and imported under `/Game/Generated/YACS/Lesson07_Unified/Textures/Slices/`:
1. **Class 0 (Grass)**: `T_Grass_Colour`, `T_Grass_Normal`, `T_Grass_Masks`
2. **Class 1 (Grass 2)**: `T_Grass2_Colour`, `T_Grass2_Normal`, `T_Grass2_Masks`
3. **Class 2 (Sand)**: `T_Sand_Colour`, `T_Sand_Normal`, `T_Sand_Masks`
4. **Class 3 (Cliffs)**: `T_Cliffs_Colour`, `T_Cliffs_Normal`, `T_Cliffs_Masks`
5. **Class 4 (Scree)**: `T_Scree_Colour`, `T_Scree_Normal`, `T_Scree_Masks` (derived from Lesson 05 Material Forge)

### Texture2DArray Assets
Created under `/Game/Generated/YACS/Lesson07_Unified/Materials/`:
- `TA_Colour_Unified.uasset` (5 slices, $2048 \times 2048$, `srgb=True`, `compression=TC_Default`, Wrap)
- `TA_Normal_Unified.uasset` (5 slices, $2048 \times 2048$, `srgb=False`, `compression=TC_Normalmap`, Wrap)
- `TA_Masks_Unified.uasset` (5 slices, $2048 \times 2048$, `srgb=False`, `compression=TC_Masks`, Wrap)

### Material Instance [MI_Landscape_Instance_YACS](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset)
- Base Master: `/Game/PegasusDemo/Materials/Landscape/M_Pegasus_Landscape_Master`
- Texture Parameters:
  - `Terrain IDmap` $\to$ `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap` (`TC_Grayscale`, `TF_Nearest`)
  - `Terrain Colour` $\to$ `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color` (`TC_Default`, `srgb=True`)
  - `Colour Atlas` $\to$ `TA_Colour_Unified`
  - `Normal Atlas` $\to$ `TA_Normal_Unified`
  - `Masks Atlas` $\to$ `TA_Masks_Unified`
- Scalar Parameters:
  - `Num IDmap Layers` = $5.0$
  - `Terrain Resolution` = $16000.0$
  - `Global Colour Strength` = $0.5$
  - `Global Specular Scale` = $1.0$
  - `Detail Brightness` = $1.5$

---

## 7. Etap G: Durable Unreal Level & Re-open Verification

- **Level Package**: `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07`
- **File**: [Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap) ($682\,622\,550\text{ bytes}$, SHA-256: `d4bd490a14dac9f7...`)
- **Landscape Assignment**: Assigned `MI_Landscape_Instance_YACS` to all landscape actors across the domain.
- **Lighting Setup**:
  - `DirectionalLight_0`: Casts dynamic shadows, sun angle matching Houdini lighting.
  - `SkyAtmosphere_0`: Atmospheric scattering and clear horizon rendering.
  - `SkyLight_0`: Real-time ambient capture preventing black unlit crevices.
- **Clean Reload Verification**:
  - Level was saved, unloaded, and re-loaded cleanly.
  - Actor count: $9$.
  - All landscape actors confirmed bound to `MI_Landscape_Instance_YACS`.
  - Zero missing texture or array references.

---

## 8. Etap H: Visual Evidence & Functional Assessment

13 verified visual evidence artifacts are recorded in [worldgen/houdini/sa_calobra/evidence/lesson07_unified/](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/):

### Houdini Diagnostic Renders (8 Artifacts)
1. `diagnostic_idmap_overview_2k.png` ($2000 \times 2000$, 5-class color palette)
2. `diagnostic_global_color_overview_2k.png` ($2000 \times 2000$, macro sRGB color)
3. `diagnostic_neutral_shading_overview_2k.png` ($2000 \times 2000$, shaded relief)
4. `diagnostic_scree_isolation_overview_2k.png` ($2000 \times 2000$, red highlighted scree occurrence)
5. `closeup_puig_major_peak.png` ($2048 \times 1024$, native $0.5\text{ m}$ crop at summit)
6. `closeup_sa_calobra_cove.png` ($2048 \times 1024$, native $0.5\text{ m}$ crop at cove beach)
7. `closeup_transition_grass_sand_cliffs.png` ($2048 \times 1024$, coastal transition)
8. `closeup_scree_occurrence.png` ($2040 \times 1024$, 3-panel RGB / ID / Shaded relief)

### Unreal Engine 5.8 Offscreen Visual Captures (5 Renders)
Rendered via offscreen engine execution (`-RenderOffscreen`) with native `AutomationLibrary.take_high_res_screenshot`:
1. `ue_panorama_material.png` ($1920 \times 1080$, $3\,124\,701\text{ bytes}$): Full terrain overview showing global color, sky atmosphere, lighting, and lack of unlit voids.
2. `ue_closeup_puig_major.png` ($1920 \times 1080$, $3\,681\,788\text{ bytes}$): Summit crags and pale limestone rock response.
3. `ue_closeup_sa_calobra_cove.png` ($1920 \times 1080$, $3\,493\,031\text{ bytes}$): Coastal sand and cliff contact zone.
4. `ue_closeup_transition.png` ($1920 \times 1080$, $915\,728\text{ bytes}$): Detail textures blending naturally with macro global color.
5. `ue_closeup_scree.png` ($1920 \times 1080$, $1\,513\,850\text{ bytes}$): Scree slope plasticity, micro-normal response, and specular roughness under direct sunlight.

### Functional Shader & Texture Assessment
- **IDMap Sampling**: `TF_Nearest` filtering prevents cross-class edge bleeding; class transitions remain crisp without noisy bilinear artifacts.
- **Color Integration**: Global color ($0.5$ strength) and high-frequency surface detail blend harmoniously; terrain maintains macro character at distance and tactile detail up close.
- **PBR Roughness & Normals**: Directional sunlight produces distinct roughness and relief response on scree and limestone cliffs.
- **Seams & Voids**: Zero missing tiles, zero black holes, and zero UV shearing across the entire domain.

---

## 9. Comprehensive File Inventory & Checksums

| Asset / File Description | Location | File Size | SHA-256 Checksum |
|---|---|---:|---|
| **L06 Input Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc` | $391\,364\text{ B}$ | `7701a844bd82d1496995866676a20ee069e9cac6e873889aca02a64be3ae2abb` |
| **L07 Output Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc` | $520\,804\text{ B}$ | `724ba6e2eb669613e4ad1727da95b72d1d4e25559f9b776deb51169c89338c52` |
| **Stage 1 Base Height Cache** | `D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc` | $519\,575\,557\text{ B}$ | `08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952` |
| **Stage 5 Final IDMap Cache** | `D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc` | $4\,808\,520\,505\text{ B}$ | `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24` |
| **Procedural Detail Delta** | `D:/yacs/work/lesson07-unified-20261019/procedural_detail.bgeo.sc` | $319\,851\,981\text{ B}$ | `82881547af8992abdc19d3674218eac2a7d475fc555df9b945e0cdf39e19129a` |
| **Pegasus IDMap PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png` | $12\,392\,456\text{ B}$ | `cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3` |
| **Pegasus Global Color PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png` | $398\,192\,590\text{ B}$ | `90bd39006ed5f56888ef9a3de887c7840bc8ff9782c11d68062755b516afbb7b` |
| **UE Material Instance** | `Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset` | $35\,333\text{ B}$ | `abbce8ae203d7e1527e9fa4fba6a33d4e5ccd8c461f1b22d06075c92f2e9de2c` |
| **UE Texture Array (Colour)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified.uasset` | $27\,552\,266\text{ B}$ | `fa1bebede697cf6aacaec43ea41ab818462b89306f65f20dd6403812ae482f6f` |
| **UE Texture Array (Normal)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified.uasset` | $45\,545\,889\text{ B}$ | `a80de6fa0887d737058a2e6f47628ec89cbccf4cb80adeb329b67f1b89c8196e` |
| **UE Texture Array (Masks)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified.uasset` | $12\,087\,514\text{ B}$ | `7c40f0e2a935bca1c99794e415942867f98cef06441cce60c777dba8ef30d939` |
| **UE Texture (IDMap)** | `Content/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap.uasset` | $13\,409\,264\text{ B}$ | `e8f35312e8754df84c34b10381c27f15af6b187bb54a00ef483f76e95d3c5f04` |
| **UE Texture (Color)** | `Content/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color.uasset` | $425\,489\,467\text{ B}$ | `6dcf927db213b6fcd3ce00f777884cf4e339f8c0588bcc219079e216409de4b2` |
| **UE Durable Map** | `Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` | $682\,622\,550\text{ B}$ | `d4bd490a14dac9f7e9761200ac3a1d5c027784f9e1b996a5dbf0f98e1069ed1f` |
| **Verification Receipt** | `docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json` | $9\,450\text{ B}$ | *(tracked in repo)* |

---

## 10. Conclusion & Acceptance Status

All objectives of Lesson 7 ("Material Setup") have been achieved on the unified $16\,000 \times 16\,000$ Sa Calobra domain:
- `LESSON07_TECHNICAL_PASS: true`
- `visual_review: PENDING_FINAL_M3_AUDIT`
- `performance_pass: false` (`DEFERRED_AFTER_M3`)
