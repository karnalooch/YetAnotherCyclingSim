# YACS Lesson07 — approved replacement PBR asset selection (2026-10-22)

Status: **SELECTED / NOT ACQUIRED / NOT INSTALLED / NOT COOKED**.

Owner instruction on 2026-10-22: when identity of the ten original Quixel families cannot be established, **choose suitable replacement assets** rather than block the repair indefinitely. This is explicit approval of *material-source substitution*, **not** approval to alter accepted Sa Calobra heightfields, masks, terrain registration, or silently change Pegasus graph structure. The reconstruction goal is now: **Pegasus workflow/topology and independently verified parameters as close as possible, with openly substituted textures**; it can no longer be described as pixel-accurate or asset-identical 1:1.

## Single authorized replacement library

**Poly Haven CC0**, primary license: https://polyhaven.com/license . All eight assets below have direct publisher pages and free PBR maps; no Fab login or purchase is required. Do not silently substitute a different asset with a similar title.

| Slug | Source asset | Publisher URL | Primary assigned roles |
|---|---|---|---|
| `dark_rock` | Dark Rock | https://polyhaven.com/a/dark_rock | Houdini rock predecessor (replaces legacy `tjmledzr` Hawaiian Lava Stone) |
| `sparse_grass` | Sparse Grass | https://polyhaven.com/a/sparse_grass | Houdini sparse vegetation (`ulgmbhwn` Rocky Steppe); UE array slot 1 |
| `dense_sand` | Dense Sand | https://polyhaven.com/a/dense_sand | Houdini sand (`td1hcimn` Thai Rippled Sand) |
| `dark_rock_02` | Dark Rock 02 | https://polyhaven.com/a/dark_rock_02 | Houdini cliff (`tdwlcc1l` Icelandic Cliff); UE array slot 3 |
| `gray_rocks` | Gray Rocks | https://polyhaven.com/a/gray_rocks | Houdini scree (`vjdqcba` Rocky Ground) |
| `mossy_rock` | Mossy Rock | https://polyhaven.com/a/mossy_rock | UE array slot 0 |
| `gravel_floor_02` | Gravel Floor 02 | https://polyhaven.com/a/gravel_floor_02 | UE array slot 2; shoulder and stony ground |
| `coast_sand_rocks_02` | Coast Sand Rocks 02 | https://polyhaven.com/a/coast_sand_rocks_02 | UE array slot 4; coastal rocky ground |

### Pegasus Houdini material stages (fixed order and mapping)

| Tutorial family | Chosen source | Semantic treatment |
|---|---|---|
| `tjmledzr` / rock predecessor | `dark_rock` | Charcoal fractured base rock |
| `ulgmbhwn` / grass | `sparse_grass` | Sparse, subdued Mediterranean vegetation; retain final mask enabled |
| `td1hcimn` / sand | `dense_sand` | Matte compacted sand, limited by existing source mask |
| `tdwlcc1l` / cliff | `dark_rock_02` | Dominant matte, fractured dark-gray exposed-rock response |
| `vjdqcba` / scree | `gray_rocks` | Angular gray rock fragments; no uniform black field |

Retain the source-verified graph and tint sequence in `scripts/houdini/lesson06_unified_pipeline.py` and the independent receipt `graph-source-correction-20261022.json`. No unverified mask curve or roughness setting should be invented to unblock cooking. The original tutorial's literal `default.pic` roughness semantics remain unresolved: use genuine Roughness PBR maps only as an **explicitly documented substitution adaptation**, not as an unmarked claim of exact source fidelity.

### Pegasus final Unreal D/N/ORDp array order (fixed, five slots)

| Array index | Original legacy Quixel ID / meaning | Selected replacement |
|---|---|---|
| 0 | `tkekcgfn` / Mossy Ground | `mossy_rock` |
| 1 | `vjulbjjr` / Tundra Mossy Ground | `sparse_grass` |
| 2 | `wenocdss` / Gravel Ground | `gravel_floor_02` |
| 3 | `ultncbnlw` / Layered Rock Cliff | `dark_rock_02` |
| 4 | `ullmagidy` / Shoreline Beach Rocks | `coast_sand_rocks_02` |

**Do not assume** the engine's original `ORDp` channel packing. Inspect original decoded material-layer sampler swizzles and compress the 5 packed maps to its verified channel contract. Do not simply rename third-party ARM/ORM maps as ORD(p). Original slot dimensions were 2048x2048: generate a **consistent 2K derived** engine set from the originals with documented resampling, color spaces and hashes. Use 4K originals for Houdini material source tests where relevant, not 8K defaults on the whole 8 km domain.

## Producer / quality gates

1. Retrieve from the **official Poly Haven publisher URLs** above (not scraped lookalike files or a third-party reupload). Record source page URL, license, downloaded file paths, resolution, byte count and SHA256; distinguish official source bytes from derived/converted output bytes.
2. Verify each source has appropriate Diffuse/Basecolor, Roughness, Normal (OpenGL for Houdini, DirectX for UE if provided), and Displacement/Height when required. Keep albedo in sRGB and non-color maps as linear data; preserve tangent convention or explicitly convert it.
3. Install in a versioned external source folder under `D:/yacs/work/`, not over the historical original archives. Reference it through a separately versioned, reversible material-source manifest. Do not overwrite archived Pegasus/Houdini source evidence.
4. Preserve the original graph order, verified parameter values, mask identities and full-area spatial registration. Height/displacement maps are for **material shading/evidence**, not permission to modify the accepted Sa Calobra terrain elevation. Existing geometry and masks must remain hash-identical.
5. Run a small source-domain material preview/canary with explicit provenance and baseline/after invariant tests; then validate bounded full Landscape and UE viewport separately. Apply a dark-gray cliff palette by approved color-grade only after the source-image colors are measured, and prevent crushed black RGB on valid source cells. Avoid gloss and repeated black/vertical streak artifacts.
6. UE import only after channel-packing proof, identical 2K dimensions for all arrays, MI scalar readback, shader compile and external preview. The previously observed texture streaming pool overage demands a streaming-memory check.
7. **Do not bypass historical material-entry/canary guards blindly.** Transition them only once the eight source map families, derived channels and tests are actually present and evidenced. No new cook / no native render / no graphical PASS is claimed by this selection document.
8. Stay in the existing Draft PR #474 on `codex/365-world-graph`. Do not invent 1:1 source asset identity or report whole-area acceptance before native proof.

## Reason for the decision

Original Quixel title/legacy-ID matches were ambiguous in contemporary Fab, some listings are paid or account-dependent, and the owner's browser session was not reachable. Poly Haven CC0 avoids that dependency while supplying actual photogrammetric PBR data with clean game-development permissions. `dark_rock_02` and `dark_rock` are chosen deliberately to satisfy the owner's dark-gray, low-specular Sa Calobra limestone-like **visual** target. This is art direction; the scans themselves are not independently verified geological Sa Calobra limestone.

References:
- https://polyhaven.com/license
- https://polyhaven.com/a/dark_rock
- https://polyhaven.com/a/sparse_grass
- https://polyhaven.com/a/dense_sand
- https://polyhaven.com/a/dark_rock_02
- https://polyhaven.com/a/gray_rocks
- https://polyhaven.com/a/mossy_rock
- https://polyhaven.com/a/gravel_floor_02
- https://polyhaven.com/a/coast_sand_rocks_02

Status summary: eight unique source sets selected; zero downloads/imports/cooks certified by this change. Keep all operational gates closed until real files and native results exist.
