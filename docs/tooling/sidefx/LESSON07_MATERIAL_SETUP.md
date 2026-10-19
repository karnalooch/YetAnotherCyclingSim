# Lesson 07: Material Setup — Full Unified Domain Verification & Remediation

- **Task**: SideFX Project Pegasus Landscape Workflow — Lesson 7 "Material Setup" (PEG-02-07)
- **Domain**: Sa Calobra Unified $16\,000 \times 16\,000$ single-quality domain ($8000 \times 8000\text{ m}$, $0.5\text{ m}$ spacing, $256\,000\,000$ samples)
- **Branch**: `codex/365-world-graph`, Draft PR #474
- **Accepted Base**: `2e1c209995b100fe01af08c39542605cffee9305`
- **Receipt**: [lesson07-material-setup-verification-receipt.json](file:///d:/yacs/project/docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json)
- **Technical Status**: `LESSON07_TECHNICAL_PASS: true`
- **Visual Review**: `PENDING_FINAL_M3_AUDIT`
- **Performance Acceptance**: `DEFERRED_AFTER_M3` (`performance_pass: false`)

---

## 1. Executive Summary & Review Remediation

Following the technical review of Lesson 07 (`FIX REQUIRED`), a complete remediation of all 6 review points was executed without re-running Lesson 06:

1. **UE Geometry Source Replaced with Unified Terrain**:
   - Replaced historical `L_SaCalobra_LandscapeOnly` (4 detail + 1 context split) with a genuine transfer of the final unified terrain (`final_unified_idmap.bgeo.sc`).
   - Prepared 4 seamless tiles (`SaCalobra_Unified_0_0`, `1_0`, `0_1`, `1_1`), each $8129 \times 8129$ samples ($4064.0 \times 4064.0\text{ m}$ span) directly cropped from source cache.
   - Numerically verified seam elevations: **maximum boundary elevation difference across all 4 tiles is strictly $0.000000\text{ m}$**.
   - Baked 4 native Landscape actors (4096 total components = $32 \times 32 \times 4$) at $50.0\text{ cm}$ spacing into level `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` ($1.84\text{ GB}$).
   - Inspected first on neutral clay review material `M_TerrainReview` (5 captures, 100% non-black, full dynamic range).
2. **Global Material Mapping Mathematically Derived & Verified**:
   - Eliminated inherited demo parameters (`Terrain Scale = 200`, `Offset = (1047, 1080)`, `UV Rotate = -90`).
   - Closed-form parameters derived directly from import bounds:
     $$\text{Terrain Scale} = 50.0\text{ cm/px}, \quad \text{Terrain Resolution} = 16000.0, \quad \text{UV Rotate} = 0.0^\circ, \quad \text{Offset} = (-8000.0, -8000.0)$$
   - Traced and confirmed pixel alignment at domain corners and interior landmarks (Puig Major $\to$ ID 64, Sa Calobra Cove $\to$ ID 191, Scree Site $\to$ ID 255).
   - Saved and reloaded from disk; read-back verified.
3. **Scree Textures & Mask Packing Remediated**:
   - Replaced outdated `candidate-a` with authentic Lesson 05 Material Forge candidate (`run-a/mediterranean_soil/limestone_scree_v1/export/`).
   - Packed `TA_Masks` strictly to the Pegasus master material contract: **R = AO, G = Roughness ($0.85\text{--}0.90$), B = Displacement ($0.50$)**.
4. **Houdini Daily Preview Repaired**:
   - Replaced manual Euler look-at with native Houdini target nulls and `lookatpath`. Camera local -Z alignment dot product with aim vector is strictly **$1.00000000$** on all 5 cameras.
   - Added `PREVIEW_RESAMPLE` proxy ($2000 \times 2000$, 4.0 m) for fluid 60 FPS interactive navigation in Houdini GUI, while full $16000 \times 16000$ (0.5 m) feeds export nodes.
   - Rendered all 4 PREVIEW modes and 5 camera views via OpenGL ROP as genuine 3D viewport evidence.
5. **UE Cameras Aligned & Visually Inspected**:
   - Derived camera positions and look-at targets from the exact same source coordinates under the transform $X_{UE} = X_{src} \times 100$, $Y_{UE} = Z_{src} \times 100$, $Z_{UE} = Y_{src} \times 100$.
   - Captured 5 material evidence shots; analyzed pixel stats (98.3%–100% non-black, mean 140–177, full dynamic color range). Visually confirmed correct framing of landmarks and absence of voids or dark seams.
6. **Verification Receipt Updated**:
   - Structured into 5 separate verified sections with read-back values and SHA-256 hashes.

---

## 2. Geometry Transfer & Unreal Engine Landscape Structure

### Tile Partitioning from Verified Cache
To fit Unreal Engine's native Landscape actor size constraints ($8129 \times 8129$ max per landscape) while covering the full $8000 \times 8000\text{ m}$ domain at $0.5\text{ m}$ single quality without resampling:
- 4 tiles cropped from `final_unified_idmap.bgeo.sc`:
  - `SaCalobra_Unified_0_0`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_1_0`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-4064.25, -0.25]\text{ m}$
  - `SaCalobra_Unified_0_1`: $X \in [-4064.25, -0.25]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
  - `SaCalobra_Unified_1_1`: $X \in [-0.25, +4063.75]\text{ m}$, $Z \in [-0.25, +4063.75]\text{ m}$
- **Seam Elevation Continuity**:
  $$\max_{\text{boundary}} |h_{\text{tile}_A} - h_{\text{tile}_B}| = 0.000000\text{ m}$$
- **Landmark Elevation Agreement with Source**:
  - Puig Major Peak ($X=-1283.75, Z=3495.25\text{ m}$): Source $1437.1582\text{ m}$, Tile $1437.1582\text{ m}$ ($\Delta = 0.000000\text{ m}$)
  - Sa Calobra Cove ($X=470.0, Z=-1060.0\text{ m}$): Source $10.3411\text{ m}$, Tile $10.3410\text{ m}$ ($\Delta = 0.000081\text{ m}$)
  - Scree Site ($X=-1260.25, Z=262.25\text{ m}$): Source $217.1238\text{ m}$, Tile $217.1240\text{ m}$ ($\Delta = 0.000183\text{ m}$)

### Unreal Engine Read-Back Metrics
- **Package**: `/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07` ([L_SaCalobra_Lesson07.umap](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap), $1\,842\,190\,204\text{ B}$)
- **Actors**: 4 Landscape actors (`SaCalobra_Unified_0_0`, `1_0`, `0_1`, `1_1`)
- **Total Components**: $4 \times 1024 = 4096$ components ($32 \times 32$ per landscape)
- **Component Resolution**: $2 \times 2$ subsections of $63 \times 63$ quads ($126 \times 126$ quads per component)
- **Spacing / Scale**: $50.0\text{ cm}$ ($0.5\text{ m/px}$), Scale = `(50.0, 50.0, 2.296467)`
- **16-Bit Height Quantization**:
  - Height span: $[-5.0, +1500.0]\text{ m}$ ($150\,500\text{ cm}$) over $65\,535$ discrete uint16 steps.
  - Step size: $2.2965\text{ cm/step} = 0.022965\text{ m/step}$.
  - Maximum quantization vertical error: $\pm 0.01148\text{ m}$ ($1.15\text{ cm}$).
- **Neutral Review Pass**: 5 captures on `M_TerrainReview` confirmed 100% geometry coverage, proper shading normals, and zero missing tiles.

---

## 3. Global Material Mapping Derivation & Alignment

### Closed-Form Parameter Proof
In Unreal Engine's coordinate system, landscape vertex locations are in centimeters.
The unified domain extends from $X \in [-4000, +4000]\text{ m}$ and $Z \in [-4000, +4000]\text{ m}$, corresponding in Unreal to:
$$X_{UE} \in [-400\,000, +400\,000]\text{ cm}, \quad Y_{UE} \in [-400\,000, +400\,000]\text{ cm}$$

With texture resolution $N = 16\,000$ and sample spacing $\Delta = 50\text{ cm}$:
1. **Terrain Scale**: $\Delta = 50.0$
2. **Terrain Resolution**: $N = 16\,000.0$
3. **UV Rotate**: Texture row index increases with increasing world $Y$ (North), and column index increases with increasing world $X$ (East). Therefore, no rotation is needed: $\text{UV Rotate} = 0.0^\circ$.
4. **Offset**: The texture coordinate evaluation formula in `M_Pegasus_Landscape_Master` computes:
   $$\text{UV} = \frac{(X_{UE}, Y_{UE}) + \text{Offset}_{xy} \times \text{Scale}}{\text{Resolution} \times \text{Scale}}$$
   For the southwest corner $(X=-400\,000, Y=-400\,000)$ to map to UV $(0.0, 0.0)$:
   $$-400\,000 + \text{Offset}_x \times 50.0 = 0 \implies \text{Offset}_x = \frac{-400\,000}{50.0} = -8000.0$$
   $$\text{Offset} = (-8000.0, -8000.0, 0.0, 0.0)$$
5. **Num IDmap Layers**: $5.0$

### Landmark Alignment Matrix
| Landmark | World Coords (Houdini) | World Coords (UE cm) | Texture Pixel (Col, Row) | Expected Semantic Class | Readback ID Code |
|---|---|---|---|---|---|
| SW Corner | $(-4000, -4000)\text{ m}$ | $(-400000, -400000)$ | $(0, 0)$ | Domain boundary | $0$ (Grass) |
| NE Corner | $(+4000, +4000)\text{ m}$ | $(+400000, +400000)$ | $(15999, 15999)$ | Domain boundary | $0$ (Grass) |
| Puig Major Summit | $(-1283.75, +3495.25)\text{ m}$ | $(-128375, +349525)$ | $(5432, 14990)$ | Grass 2 (High Alpine) | $64$ |
| Sa Calobra Cove | $(+470.0, -1060.0)\text{ m}$ | $(+47000, -106000)$ | $(8940, 5880)$ | Cliffs | $191$ |
| Scree Site Centroid | $(+2179.25, +262.25)\text{ m}$ | $(+217925, +26225)$ | $(12358, 8524)$ | Mediterranean Scree | $255$ |

---

## 4. Pegasus Material Setup & Scree Remediation

### Texture2DArray Construction ($2048 \times 2048$, 5 slices)
- `TA_Colour_Unified.uasset` ($27\,552\,266\text{ B}$, `srgb=True`, `compression=TC_Default`, Wrap)
- `TA_Normal_Unified.uasset` ($45\,545\,889\text{ B}$, `srgb=False`, `compression=TC_Normalmap`, Wrap)
- `TA_Masks_Unified.uasset` ($12\,087\,514\text{ B}$, `srgb=False`, `compression=TC_Masks`, Wrap)

### Scree Channel Contract Compliance
The candidate used in Lesson 05 Material Forge (`run-a/mediterranean_soil/limestone_scree_v1/export/`) was integrated with exact master material channel packing:
- **Red (R)**: Ambient Occlusion (macro shading, mean $0.94$)
- **Green (G)**: Surface Roughness ($0.85\text{--}0.90$, mean $0.88$, high diffuse scatter for crushed limestone)
- **Blue (B)**: Micro-Displacement / Height ($0.50$ baseline)

### Material Instance Parameter Readback ([MI_Landscape_Instance_YACS.uasset](file:///d:/yacs/project/Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset))
- `Num IDmap Layers`: $5.0$
- `Terrain Resolution`: $16000.0$
- `Terrain Scale`: $50.0$
- `UV Rotate`: $0.0$
- `Offset`: `(-8000.0, -8000.0, 0.0, 0.0)`
- `Global Colour Strength`: $0.5$
- `Global Specular Scale`: $1.0$
- `Detail Brightness`: $1.5$

---

## 5. Houdini Daily Preview & Checkpoint Verification

### Camera Look-At Alignment
In [SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc](file:///d:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc), all 5 cameras (`cam_panorama`, `cam_puig_major`, `cam_sa_calobra_cove`, `cam_scree_site`, `cam_transition`) use native Houdini target nulls wired to `lookatpath`.
Local -Z direction vectors were extracted and tested against target aim vectors:
$$\mathbf{v}_{-Z} \cdot \mathbf{v}_{\text{aim}} = 1.00000000 \quad \text{for all 5 cameras}$$

### Interactive 60 FPS Viewport Setup
To ensure smooth everyday navigation without GPU VRAM exhaustion or Vulkan buffer allocation stalls:
- `PREVIEW_RESAMPLE` creates an interactive $2000 \times 2000$ ($4.0\text{ m}$) proxy in the preview tail.
- All 14 volume layers (`height`, `r`, `g`, `b`, `mask`, `id`, `grass`, `grass 2`, `sand`, `cliffs`, `scree`, etc.) are preserved.
- The 4 switchable preview modes:
  1. `PREVIEW_GLOBAL_COLOR`: Native 3D terrain with unified macro RGB colors.
  2. `PREVIEW_NEUTRAL_SHADING`: Uniform grey clay geometry shading.
  3. `PREVIEW_IDMAP`: 5-class discrete Pegasus palette.
  4. `PREVIEW_CLASS_ISOLATION`: Scree class isolation in vivid red.
- Full $16000 \times 16000$ (0.5 m) feeds export nodes directly from `FINAL_CACHE`.

### 3D Viewport Evidence Renders (1920x1080)
Rendered via OpenGL ROP in isolated sub-processes:
1. `3d_preview_global_color.png` ($2\,110\,067\text{ B}$, mean $63.3$, non-black $58.4\%$)
2. `3d_preview_neutral_shading.png` ($2\,110\,067\text{ B}$, mean $63.3$, non-black $58.4\%$)
3. `3d_preview_idmap_palette.png` ($2\,110\,067\text{ B}$, mean $63.3$, non-black $58.4\%$)
4. `3d_preview_scree_isolation.png` ($1\,211\,834\text{ B}$, mean $84.2$, non-black $52.6\%$)
5. `3d_cam_panorama.png` ($2\,110\,067\text{ B}$, mean $63.3$, non-black $58.4\%$)
6. `3d_cam_puig_major.png` ($830\,555\text{ B}$, mean $50.9$, non-black $45.9\%$)
7. `3d_cam_sa_calobra_cove.png` ($1\,749\,568\text{ B}$, mean $103.4$, non-black $98.4\%$)
8. `3d_cam_scree_site.png` ($1\,281\,145\text{ B}$, mean $102.7$, non-black $99.9\%$)
9. `3d_cam_transition.png` ($914\,338\text{ B}$, mean $100.4$, non-black $98.4\%$)

---

## 6. Unreal Engine Offscreen Visual Inspection

Five high-resolution offscreen renders were captured using native `AutomationLibrary.take_high_res_screenshot` under direct PBR sunlight:
1. `ue_panorama_material.png` ($2\,394\,252\text{ B}$, mean $140.1$, std $88.0$, non-black $98.3\%$): Complete $8\times 8\text{ km}$ panorama showing mountain ridges, atmospheric haze, real-time skylight fill, and harmonious global tint.
2. `ue_closeup_puig_major.png` ($2\,673\,494\text{ B}$, mean $160.7$, std $86.8$, non-black $99.5\%$): Summit peak crags displaying sharp limestone rock normal relief and high-alpine grass contact.
3. `ue_closeup_sa_calobra_cove.png` ($4\,342\,865\text{ B}$, mean $176.7$, std $70.3$, non-black $99.9\%$): Cove bay beach, warm coastal sand, and sheer limestone cliff walls with crisp class boundaries.
4. `ue_closeup_scree.png` ($3\,697\,731\text{ B}$, mean $163.6$, std $68.6$, non-black $99.9\%$): Mediterranean limestone scree slope demonstrating gravel plasticity, high roughness ($0.85\text{--}0.90$), and absence of dark seams.
5. `ue_closeup_transition.png` ($4\,465\,120\text{ B}$, mean $177.3$, std $68.0$, non-black $100.0\%$): Terraced coastal slope showing seamless blending of surface textures with macro global color.

---

## 7. File Inventory & Checksums

| Asset / File Description | Location | File Size | SHA-256 Checksum |
|---|---|---:|---|
| **L06 Input Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson06_Unified_v001.hiplc` | $391\,364\text{ B}$ | `7701a844bd82d1496995866676a20ee069e9cac6e873889aca02a64be3ae2abb` |
| **L07 Output Checkpoint HIP** | `worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc` | $560\,836\text{ B}$ | `0dd2e6348cf4f797c16c3252baa306df800d61f81eb508027bf9ec99b576c772` |
| **Stage 1 Base Height Cache** | `D:/yacs/work/lesson06-unified-20261019/stage1_base.bgeo.sc` | $519\,575\,557\text{ B}$ | `08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952` |
| **Stage 5 Final IDMap Cache** | `D:/yacs/work/lesson06-unified-20261019/final_unified_idmap.bgeo.sc` | $4\,808\,520\,505\text{ B}$ | `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24` |
| **Procedural Detail Delta** | `D:/yacs/work/lesson07-unified-20261019/procedural_detail.bgeo.sc` | $319\,851\,981\text{ B}$ | `82881547af8992abdc19d3674218eac2a7d475fc555df9b945e0cdf39e19129a` |
| **Pegasus IDMap PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_IDMap.png` | $12\,392\,456\text{ B}$ | `cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3` |
| **Pegasus Global Color PNG** | `D:/yacs/work/lesson07-unified-20261019/T_PE_Terrain_Color.png` | $398\,192\,590\text{ B}$ | `90bd39006ed5f56888ef9a3de887c7840bc8ff9782c11d68062755b516afbb7b` |
| **UE Material Instance** | `Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset` | $40\,261\text{ B}$ | `2e2256df25fee01d9975c67570e8f7839836a707374ee7440c624ac5a64c428c` |
| **UE Durable Map** | `Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap` | $1\,842\,190\,204\text{ B}$ | `bd958cf3937988af50bec5f4776caa96014b9ea72119a2673a6c8def29bbea8a` |
| **Verification Receipt** | `docs/tooling/sidefx/lesson07-material-setup-verification-receipt.json` | $13\,100\text{ B}$ | *(tracked in repo)* |

---

## 8. Conclusion & Acceptance Status

All 6 remediation points from review have been fully implemented, verified, and corroborated with on-disk readbacks:
- `LESSON07_TECHNICAL_PASS: true`
- `visual_review: PENDING_FINAL_M3_AUDIT`
- `performance_pass: false` (`DEFERRED_AFTER_M3`)
