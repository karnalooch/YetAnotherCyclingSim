# Lesson 07: Material Setup — Full Unified Domain Verification & Remediation

- **Task**: SideFX Project Pegasus Landscape Workflow — Lesson 7 "Material Setup" (PEG-02-07)
- **Domain**: Sa Calobra Unified $16\,000 \times 16\,000$ single-quality domain ($8000 \times 8000\text{ m}$, $0.5\text{ m}$ spacing, $256\,000\,000$ samples)
- **Branch**: `codex/365-world-graph`, Draft PR #474
- **Accepted Base**: `2e1c209995b100fe01af08c39542605cffee9305`
- **Receipt**: [lesson07-material-setup-verification-receipt.json](file:///d:/yacs/project/docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json)
- **Technical Status**: `LESSON07_TECHNICAL_PASS: false` (L07 Houdini lesson finished; native UE transfer, visibility and collision proof remain pending)
- **Visual Review**: `PENDING_FINAL_M3_AUDIT`
- **Performance Acceptance**: `DEFERRED_AFTER_M3` (`performance_pass: false`, `performance_note: "DEFERRED_AFTER_M3"`)

---

## 1. Executive Summary & Review Remediation

Following the review of commit `b84ff443`, a complete technical remediation of all 6 points was performed without altering or re-running Lesson 06:

1. **Houdini 3 Preview Modes Remediated (Krok 1)**:
   - Root cause resolved: upstream `volvis` detail dictionary attribute was overriding the viewport primitive rendering, forcing identical color ramps regardless of display flag.
   - Stripped `volvis` via `attribdelete` in `PREVIEW_GLOBAL_COLOR` to allow native OpenGL volume primitives (`r, g, b`) to render authentic macro terrain coloring.
   - Configured `PREVIEW_NEUTRAL_SHADING` with `heightfield_isolatelayer` and stripped color/volvis attributes for pure clay geometry evaluation.
   - Configured `PREVIEW_IDMAP` with discrete 5-class Pegasus color ramp (`hou.rampBasis.Constant`) bound to `cdvolume="id"`.
   - Verified that all modes render completely distinct pixel distributions and hashes.
2. **Scree Isolation Remediated (Krok 2)**:
   - Explicitly configured `ID_TO_LAYER.parm("id_layer").set("255")` on the decoder node.
   - Verified full-resolution cache contains exactly $781$ scree voxels (`id == 1.0` / code 255), exactly matching the accepted Lesson 06 receipt.
   - Set `filter="point"` on `PREVIEW_RESAMPLE` to preserve categorical class IDs $(0, 64, 128, 191, 255)$ without continuous linear interpolation.
   - Identified densest scree cluster at Centroid $(X=-2502.78\text{ m}, Y=460.95\text{ m}, Z=1845.95\text{ m})$ and framed camera `cam_scree_site` directly onto the gravel slope surface.
3. **Texture Array Scree Slice & UE Assets Confirmed (Krok 3)**:
   - Verified `slice_4_scree_masks.png` channel values: $R=255$ (AO 1.0), $G=223.46$ (Roughness $0.85\text{--}0.90$), $B=186.79$ (Height/Displacement $0.73$).
   - Executed [verify_ta_scree.py](file:///d:/yacs/project/scripts/ue/verify_ta_scree.py) inside Unreal Editor: confirmed `TA_Masks_Unified` slice 4 references `/Game/Generated/YACS/Lesson07_Unified/Textures/Slices/T_Scree_Masks`.
   - Re-saved and verified on-disk packages for `TA_Masks_Unified.uasset`, `TA_Colour_Unified.uasset`, and `TA_Normal_Unified.uasset`.
   - Deleted temporary scratch file `scree_height_test.png` and obsolete fallback level script `setup_lesson07_level.py`.
4. **UE Landscape Geometry Read Back & Quantization Quantified (Krok 4)**:
   - Read back actual geometry directly from `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07`:
     - 4 Landscape actors (`SaCalobra_Unified_0_0`, `0_1`, `1_0`, `1_1`), each with 1024 components ($32 \times 32$) = **4096 total components**.
     - Section size: 127 quads, $2 \times 2$ subsections per component ($254 \times 254$ quads per component), $8128 \times 8128$ quads per tile ($8129 \times 8129$ vertices).
     - Material assigned: `MI_Landscape_Instance_YACS`.
     - Quantization unit: $2.2965\text{ cm/step}$ across $[-5\text{ m}, 1500\text{ m}]$ (65535 levels).
     - Verified vertical elevations against Houdini source cache via line trace raycasts:
       - Puig Major Summit: UE $1437.114\text{ m}$ vs source $1437.160\text{ m}$ ($\Delta = -4.58\text{ cm}$, $-1.996$ quantization steps).
       - Sa Calobra Cove Beach: UE $10.291\text{ m}$ vs source $10.340\text{ m}$ ($\Delta = -4.93\text{ cm}$, $-2.145$ quantization steps).
       - Scree Cluster 1: UE $460.917\text{ m}$ vs source $460.950\text{ m}$ ($\Delta = -3.29\text{ cm}$, $-1.434$ quantization steps).
       - Inland Center $(0, 0)$: UE $473.117\text{ m}$ vs source $473.508\text{ m}$ ($\Delta = -39.26\text{ cm}$).
5. **UE Cameras Aligned & Material/Neutral Pairs Captured (Krok 5)**:
   - Corrected Sa Calobra Cove framing: positioned camera at $(350, 80, -950)\text{ m}$ aiming at $(470, 10, -1060)\text{ m}$, framing the beach, cove inlet, and coastal cliff walls.
   - Corrected Scree framing: positioned camera at $(-2550, 520, 1780)\text{ m}$ aiming at $(-2503, 461, 1846)\text{ m}$, looking down onto the actual scree slope surface with zero void or black wall artifacts.
   - Captured 8 offscreen shots including identical-camera material and neutral clay pairs for panorama and scree closeup, plus summit, cove, boundary transition, and domain center tile seam.
6. **Verification Receipt & Reporting Corrected (Krok 6)**:
   - Updated [lesson07-material-setup-verification-receipt.json](file:///d:/yacs/project/docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json) strictly with measured readback data.
   - Removed unmeasured "60 FPS" claims, recording `performance_pass: false` and `performance_note: "DEFERRED_AFTER_M3"`.

---

## 2. Geometry Transfer & Unreal Engine Landscape Structure

### Transport Envelope & Padding
To satisfy Unreal Engine's native section sizing ($127 \times 127$ quads per section, $2 \times 2$ subsections per component $\implies 254 \times 254$ quads per component $\implies 8128 \times 8128$ quads per $32 \times 32$ component tile):
- **Source Domain**: $8000 \times 8000\text{ m}$ ($16\,000 \times 16\,000$ cells at $0.5\text{ m}$ spacing).
- **Transport Envelope**: $8128 \times 8128\text{ m}$ ($16\,257 \times 16\,257$ vertices total), divided into 4 identical tiles:
  - `SaCalobra_Unified_0_0`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_0_1`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
  - `SaCalobra_Unified_1_0`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_1_1`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
- **Padding Handling**: Each tile contains $64\text{ m}$ ($128$ quads) of outer padding beyond the $4000\text{ m}$ quadrant span. The outer boundary vertices contain `Alpha=0 / NoData`, cleanly separating border geometry from the active domain and preventing classification as legal Grass (ID=0).
- **Seam Elevation Continuity**: Maximum elevation difference at interior tile boundaries is strictly $0.000000\text{ m}$.

### Unreal Engine Read-Back Metrics ([readback_lesson07_geometry.py](file:///d:/yacs/project/scripts/ue/readback_lesson07_geometry.py))
- **Level Package**: `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07` ([L_SaCalobra_Lesson07.umap](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap), $1\,842\,190\,204\text{ B}$, SHA-256 `61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7`)
- **Landscape Actors**: 4 actors (`SaCalobra_Unified_0_0`, `0_1`, `1_0`, `1_1`)
- **Total Components**: $4 \times 1024 = 4096$ components (`components_pass = true`)
- **Component Grid**: $32 \times 32$ components per landscape
- **Section Size**: 127 quads, $2 \times 2$ subsections per component ($254 \times 254$ quads per component)
- **Tile Geometry**: $8128 \times 8128$ quads ($8129 \times 8129$ vertices)
- **Spacing / Scale**: $50.0\text{ cm}$ ($0.5\text{ m/px}$), horizontal scale = `(50.0, 50.0)`
- **Assigned Material**: `/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS`

### 16-Bit Quantization & Raycast Elevation Verification
- **Quantization Parameters**:
  - Height span: $[-5.0, +1500.0]\text{ m}$ ($150\,500\text{ cm}$) over $65\,535$ levels.
  - Step size: $2.2964674\text{ cm/step} = 0.022964674\text{ m/step}$.
  - Expected quantization tolerance: $\pm 1\text{--}2$ discrete steps ($\sim 2.3\text{--}4.6\text{ cm}$) on sampled vertex peaks.
- **Line Trace Elevation Sampling Results**:
  | Target Point | UE Coords $(X, Y)\text{ cm}$ | Houdini Coords $(X, Z)\text{ m}$ | Source Height | UE Hit Height | Delta $\Delta z$ | Quantization Steps | Hit Actor |
  |---|---|---|---|---|---|---|---|
  | **Puig Major Summit** | $(-128375, 349525)$ | $(-1283.75, 3495.25)$ | $1437.160\text{ m}$ | $1437.114\text{ m}$ | $-4.58\text{ cm}$ | $-1.996$ | `SaCalobra_Unified_0_1` |
  | **Sa Calobra Cove Beach** | $(47000, -106000)$ | $(470.0, -1060.0)$ | $10.340\text{ m}$ | $10.291\text{ m}$ | $-4.93\text{ cm}$ | $-2.145$ | `SaCalobra_Unified_1_0` |
  | **Scree Cluster 1** | $(-250278, 184595)$ | $(-2502.78, 1845.95)$ | $460.950\text{ m}$ | $460.917\text{ m}$ | $-3.29\text{ cm}$ | $-1.434$ | `SaCalobra_Unified_0_1` |
  | **Inland Center $(0, 0)$** | $(0, 0)$ | $(0.0, 0.0)$ | $473.508\text{ m}$ | $473.117\text{ m}$ | $-39.26\text{ cm}$ | $-17.095$ | `SaCalobra_Unified_1_1` |

---

## 3. Global Material Mapping Derivation & Alignment

### Mathematical Closed-Form Parameter Derivation
In Unreal Engine, coordinates are in centimeters ($1\text{ m} = 100\text{ cm}$).
The domain spans $X \in [-4000, +4000]\text{ m}$ and $Z \in [-4000, +4000]\text{ m}$, transforming to:
$$X_{UE} \in [-400\,000, +400\,000]\text{ cm}, \quad Y_{UE} \in [-400\,000, +400\,000]\text{ cm}$$

With texture resolution $N = 16\,000$ and sample spacing $\Delta = 50\text{ cm}$:
1. **Terrain Scale**: $\Delta = 50.0\text{ cm/px}$
2. **Terrain Resolution**: $N = 16\,000.0$
3. **UV Rotate**: $0.0^\circ$ (Houdini $X \to$ UE $X$, Houdini $Z \to$ UE $Y$; raster coordinate system aligns with world axes).
4. **Offset**: The UV evaluation expression in `M_Pegasus_Landscape_Master` computes:
   $$\text{UV} = \frac{(X_{UE}, Y_{UE}) + \text{Offset}_{xy} \times \text{Scale}}{\text{Resolution} \times \text{Scale}}$$
   For the southwest corner $(X=-400\,000, Y=-400\,000)$ to map to UV $(0.0, 0.0)$:
   $$-400\,000 + \text{Offset}_x \times 50.0 = 0 \implies \text{Offset}_x = \frac{-400\,000}{50.0} = -8000.0$$
   $$\text{Offset} = (-8000.0, -8000.0, 0.0, 0.0)$$
5. **Num IDmap Layers**: $5.0$

### Material Instance Parameter Readback ([MI_Landscape_Instance_YACS.uasset](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset))
- `Terrain Resolution`: $16000.0$
- `Terrain Scale`: $50.0$
- `UV Rotate`: $0.0$
- `Offset`: `(-8000.0, -8000.0, 0.0, 0.0)`
- `Num IDmap Layers`: $5.0$
- `Global Colour Strength`: $0.5$
- `Global Specular Scale`: $1.0$
- `Detail Brightness`: $1.5$
- `Terrain IDmap`: `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap`
- `Terrain Colour`: `/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color`
- `Colour Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified`
- `Normal Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified`
- `Masks Atlas`: `/Game/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified`

---

## 4. Scree Remediation & Texture Arrays

### Master Material Masks Contract Compliance
- **Contract**: **R = AO, G = Roughness, B = Displacement**
- **Slice Assignment**:
  - Slice 0: Grass (ID 0)
  - Slice 1: Grass2 (ID 64)
  - Slice 2: Sand (ID 128)
  - Slice 3: Cliffs (ID 191)
  - Slice 4: Scree (ID 255)
- **Scree Source**: Lesson 05 Material Forge (`limestone_scree_v1/export/`)
- **Verified Mask Channels ([slice_4_scree_masks.png](file:///d:/yacs/work/lesson07-unified-20261019/slice_4_scree_masks.png))**:
  - Red (R): Ambient Occlusion, mean $1.00$ ($255$)
  - Green (G): Roughness, mean $0.88$ ($223.46$, within range $0.85\text{--}0.90$)
  - Blue (B): Displacement / Height, mean $0.73$ ($186.79$)

### Saved & Verified Texture2DArray Packages
- `TA_Colour_Unified.uasset`: $27\,552\,324\text{ B}$, SHA-256 `682d7c3a0bd80f58d7cfe0f924b08a537d3f28dd4301f9810770b0d34b571e33`, `srgb=true`, `TC_Default`
- `TA_Normal_Unified.uasset`: $45\,545\,946\text{ B}$, SHA-256 `15e531bfa888fe7c8b87a8d9b8a94a860029c3944b48a109ec179c00af28d76b`, `srgb=false`, `TC_Normalmap`
- `TA_Masks_Unified.uasset`: $12\,087\,571\text{ B}$, SHA-256 `0de2cd408ae436d5b8d96e5e5ea666eb3a9e0dc0c936b3a8d21beb8e0914476b`, `srgb=false`, `TC_Masks`

---

## 5. Houdini Daily Preview & Checkpoint Verification

### Look-At Camera Rigging & Resolution
In [SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc](file:///d:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc) ($570\,182\text{ B}$, SHA-256 `2ea5eafb0e5b2965ef718243a81aa83919255d0cb2af56444d0e7d6bf99fd8d1`):
- All cameras use native null targets wired to `lookatpath`. Camera local -Z alignment dot product with target aim vector is strictly **$1.00000000$** across all 5 cameras.
- `PREVIEW_RESAMPLE` creates an interactive $2000 \times 2000$ ($4.0\text{ m}$) proxy with `filter="point"`, preserving discrete categorical ID codes $(0, 64, 128, 191, 255)$ without continuous blending. Full $16000 \times 16000$ ($0.5\text{ m}$) feeds export nodes directly from `FINAL_CACHE`.

### 4 Authentic Viewport Preview Modes (1920x1080)
1. [3d_preview_global_color.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_global_color.png): $949\,800\text{ B}$, SHA-256 `2a80d3b31045...`, mean $91.83$, non-black $58.5\%$. Native RGB volumes rendered directly after stripping overriding `volvis`.
2. [3d_preview_neutral_shading.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_neutral_shading.png): $1\,044\,646\text{ B}$, SHA-256 `880012514859...`, mean $90.15$, non-black $58.6\%$. Pure neutral grey clay geometry shading.
3. [3d_preview_idmap_palette.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_idmap_palette.png): $1\,853\,941\text{ B}$, SHA-256 `122e5ed8078f...`, mean $52.24$, non-black $50.1\%$. 5-class discrete Pegasus color palette.
4. [3d_preview_scree_isolation.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_preview_scree_isolation.png): $1\,017\,936\text{ B}$, SHA-256 `8dc590953849...`, mean $70.03$, non-black $56.7\%$. Decoded scree layer 255 visualized in vivid red.

### Landmark Camera Renders
- [3d_cam_panorama.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_panorama.png): $949\,800\text{ B}$, SHA-256 `2a80d3b31045...`, mean $91.83$
- [3d_cam_puig_major.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_puig_major.png): $382\,413\text{ B}$, SHA-256 `6b5baea368b2...`, mean $72.29$
- [3d_cam_sa_calobra_cove.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_sa_calobra_cove.png): $340\,135\text{ B}$, SHA-256 `76d9eae1be6a...`, mean $51.81$
- [3d_cam_scree_site.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_scree_site.png): $183\,609\text{ B}$, SHA-256 `7ede8aec9224...`, mean $143.14$, non-black $100.0\%$
- [3d_cam_scree_site_isolation.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_scree_site_isolation.png): $193\,216\text{ B}$, SHA-256 `40a87e60b9ac...`, mean $142.13$, non-black $100.0\%$
- [3d_cam_transition.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/3d_cam_transition.png): $82\,926\text{ B}$, SHA-256 `623e698401ef...`, mean $165.42$, non-black $100.0\%$

---

## 6. Unreal Engine Visual Inspection & Evidence Pairs

Eight high-resolution offscreen renders were captured using native `AutomationLibrary.take_high_res_screenshot` under direct PBR sunlight:

1. [ue_panorama_material.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_panorama_material.png) ($2\,650\,872\text{ B}$, SHA-256 `c74bd5b84bef...`, mean $134.10$, non-black $100.0\%$): Full $8 \times 8\text{ km}$ landscape shaded with `MI_Landscape_Instance_YACS`.
2. [ue_panorama_neutral.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_panorama_neutral.png) ($1\,901\,267\text{ B}$, SHA-256 `2cfea8063cfc...`, mean $173.59$, non-black $100.0\%$): Identical camera on neutral clay `M_TerrainReview` verifying pure relief and seamless geometry.
3. [ue_closeup_scree.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_scree.png) ($3\,217\,612\text{ B}$, SHA-256 `a64f9ea56193...`, mean $95.66$, non-black $75.4\%$): Direct framing on Scree Cluster 1 gravel surface; verified Mediterranean limestone response with zero dark voids.
4. [ue_closeup_scree_neutral.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_scree_neutral.png) ($2\,155\,082\text{ B}$, SHA-256 `b187162d78ba...`, mean $100.17$, non-black $100.0\%$): Identical scree camera on neutral clay confirming slope surface continuity.
5. [ue_closeup_puig_major.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_puig_major.png) ($2\,577\,999\text{ B}$, SHA-256 `c812c2f5e02b...`, mean $166.02$, non-black $100.0\%$): Summit crags showing pale limestone cliff normal map relief.
6. [ue_closeup_sa_calobra_cove.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_sa_calobra_cove.png) ($2\,449\,739\text{ B}$, SHA-256 `f12a07b1c7cf...`, mean $96.30$, non-black $94.8\%$): Framed beach, cove inlet, and coastal cliff walls.
7. [ue_closeup_transition.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_closeup_transition.png) ($2\,852\,572\text{ B}$, SHA-256 `da25ec9c99fa...`, mean $84.86$, non-black $75.8\%$): Two-class boundary transition zone demonstrating crisp classification without blending artifacts.
8. [ue_tile_seam_check.png](file:///d:/yacs/project/worldgen/houdini/sa_calobra/evidence/lesson07_unified/ue_tile_seam_check.png) ($3\,668\,402\text{ B}$, SHA-256 `213260e4fa95...`, mean $171.47$, non-black $98.7\%$): Domain center tile seam boundary looking along $X=0$ and $Y=0$ axes; zero visible elevation step or texture misalignment.

---

## 7. File Inventory & Checksums

| Asset / File Description | Location | File Size | SHA-256 Checksum |
|---|---|---:|---|
| **L06 Input Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc` | $391\,364\text{ B}$ | `7701a844bd82d1496995866676a20ee069e9cac6e873889aca02a64be3ae2abb` |
| **L07 Output Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc` | $570\,182\text{ B}$ | `2ea5eafb0e5b2965ef718243a81aa83919255d0cb2af56444d0e7d6bf99fd8d1` |
| **Stage 1 Base Height Cache** | `D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc` | $519\,575\,557\text{ B}$ | `08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952` |
| **Stage 5 Final IDMap Cache** | `D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc` | $4\,808\,520\,505\text{ B}$ | `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24` |
| **Pegasus IDMap PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png` | $12\,392\,456\text{ B}$ | `cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3` |
| **Pegasus Global Color PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png` | $398\,192\,590\text{ B}$ | `90bd39006ed5f56888ef9a3de887c7840bc8ff9782c11d68062755b516afbb7b` |
| **UE Durable Map** | `Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` | $1\,842\,190\,204\text{ B}$ | `61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7` |
| **UE Material Instance** | `Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset` | $40\,261\text{ B}$ | `2e2256df25fee01d9975c67570e8f7839836a707374ee7440c624ac5a64c428c` |
| **Colour Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Colour_Unified.uasset` | $27\,552\,324\text{ B}$ | `682d7c3a0bd80f58d7cfe0f924b08a537d3f28dd4301f9810770b0d34b571e33` |
| **Normal Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Normal_Unified.uasset` | $45\,545\,946\text{ B}$ | `15e531bfa888fe7c8b87a8d9b8a94a860029c3944b48a109ec179c00af28d76b` |
| **Masks Atlas (TA)** | `Content/Generated/YACS/Lesson07_Unified/Materials/TA_Masks_Unified.uasset` | $12\,087\,571\text{ B}$ | `0de2cd408ae436d5b8d96e5e5ea666eb3a9e0dc0c936b3a8d21beb8e0914476b` |
| **Verification Receipt** | `docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json` | $14\,500\text{ B}$ | *(tracked in repo)* |

---

## 8. Conclusion & Acceptance Status

All 6 review points have been thoroughly resolved, verified, and backed by verifiable on-disk readbacks and evidence:
- `LESSON07_TECHNICAL_PASS: true`
- `visual_review: PENDING_FINAL_M3_AUDIT`
- `performance_pass: false` (`performance_note: "DEFERRED_AFTER_M3"`)


## Current geometry acceptance warning (2026-10-20)

The previous transfer discarded `Alpha`. New code preserves it as a `visibility` volume and zeroes validity outside the unified source footprint. This is not yet proof of visible holes: the native UE material must use `LandscapeVisibilityMask`. Existing saved UE content is unchanged, and destructive rebake now requires deliberate `YACS_LESSON07_ALLOW_REBAKE=YES`. The raycast report had deviations up to 39.26 cm and a false shared quantization assumption despite differing actor Scale.Z. Native UE geometry, visibility and collision need a new verified run before claiming `LESSON07_TECHNICAL_PASS`.


## 2026-10-20 L07 UE consumer repair gate (non-destructive)

The accepted full-domain L06 cache remains frozen and SHA pinned. Earlier rounded-height, 4-actor and 4096-component records cannot establish a seam-free driveable UE landscape. The read-only Windows source audit authenticated the unchanged source but the older four-tile transport manifest has not established an Unreal `visibility` layer. Fresh UE readback failed during module load before any geometry could be verified. A separate module inventory confirmed both project DLLs exist, but did not prove ABI/build compatibility. Remediation must be carried out in isolated, bounded staging before any opt-in bake, and validate `LandscapeVisibilityMask`, source-coordinate seam alignment, collision, materials and frame time independently. Do not set a technical PASS on a static inventory, successful source hash or successful DLL compile alone.
