# VH-3G-R3-002 — Stage 3G — representative forest target-density baseline

## Goal

Replace the sparse R2/R3 forest performance proxy with a representative deterministic forest before R4 terrain coherence continues. The target scene uses three layers — primary mass trees, background forest and understory saplings — while preserving route exclusion and the validated aggressive-LOD conifer.

## Roadmap

- Stage: Stage 3G
- Slice: R3 forest target-density follow-up
- Issue: #201
- PR: #202

## Baseline — BEFORE

- Accepted baseline: VH-3G-R3-001
- Commit: `02ff23f0a24228432ae9c34eb65aa4cb3694ae1d`
- Visual status: `VISUAL_ACCEPTED`
- Historical sparse-forest 4900 m performance: **11.443 ms frame p95 / 10.641 ms GPU p95 / 94.52 FPS avg**

## Current — NOW

- Branch: `feat/stage3g-forest-target-density`
- Exact performance HEAD: `09aed220ed286ccda5f4214b10f4b0a43e6f2ac9`
- Persisted forest/map commit: `eea7da9e1b202073406a246f66946817679cebca`
- Authoring: run #25 / `36333000449` — **PASS**
- Target-density performance: run #1 / `36334574786` — **PASS**
- Evidence artifact: `stage3g-forest-target-density-performance-36334574786-1`
- Technical status: **PERFORMANCE_PASS / FULL_STAGE3G_PROOF_PASS**
- Visual status: **VISUAL_REJECTED_V1 / V2_ITERATING**

The v1 representative forest is physically persisted in both `PCG_Forest.uasset` and the canonical `L_CyclingTest.umap`. Full Stage 3G proof run `36336130795` passed and produced comparable 1200 / 4900 / 8000 m captures. Review of the 4900 m capture rejected v1 visually: it still reads as a sparse repeated line of thin conifers rather than a dense layered forest. The branch therefore moves to `target_density_v2` instead of merging the technically green v1 result.

## Forest profile

| Layer | Spacing | Candidates / side | Density | Lateral band | Scale |
|---|---:|---:|---:|---:|---:|
| primary | 28 m | 4 | 0.78 | 8–34 m | 0.84–1.16 |
| background | 36 m | 3 | 0.78 × 0.92 | 30–58 m | 0.75–1.05 |
| understory | 22 m | 2 | 0.78 × 0.58 | 10–48 m | 0.30–0.55 |

The mass scatter continues to use `SM_Stage3G_FirSaplingMedium` with the accepted aggressive LOD chain. The heavy `Fir Tree 01` source remains excluded from mass scatter.

## Performance result

Reference hardware: RTX 2070 SUPER, 1920×1080, normal project rendering/shadows.

| Sector | Distance | Frame p95 | GPU p95 | Average FPS | Frames over 16.667 ms |
|---|---:|---:|---:|---:|---:|
| Valley | 1200 m | **9.469 ms** | **6.408 ms** | **134.27** | **0.00%** |
| Forest | 4900 m | **9.530 ms** | **7.953 ms** | **122.90** | **0.00%** |
| High Alpine | 8000 m | **8.868 ms** | **6.487 ms** | **135.32** | **0.00%** |

The ordinary 60 FPS / 16.667 ms gate passes in all three sectors. The representative forest additionally passes the stricter pre-rider/pre-weather budget of **frame p95 <= 14.0 ms** and **GPU p95 <= 14.0 ms**.

This performance result is accepted technical evidence for the target-density forest, but it is not yet final visual acceptance and it is not the R4 pre-optimization baseline.

## Visual review

### 1200 m — Valley
Regression capture only; the forest slice should not materially change the valley.

### 4900 m — Forest
Primary acceptance view. It must visibly read as a dense layered forest rather than a sparse row of repeated trees while keeping the road readable.

### 8000 m — High Alpine
Regression capture only; the forest slice should not materially change the high-Alpine baseline.

## Decision

- Target-density v1 performance: **PASS**
- Exact-SHA full Stage 3G proof: **PASS** — run `36336130795`
- Visual acceptance: **REJECTED** at 4900 m
- Merge #202: **BLOCKED** until a corrected forest passes visual + performance gates
- Next step: author and persist `target_density_v2`, rerun the unchanged 14 ms forest gate and full 1200 / 4900 / 8000 m capture, then accept/reject again before merge.

## R3.1 visual correction — target_density_v2

The v2 source target deliberately spends part of the measured performance headroom on visible forest mass without introducing a new heavy mass-scatter asset.

| Layer | Spacing | Candidates / side | Density | Lateral band | Scale |
|---|---:|---:|---:|---:|---:|
| primary | 20 m | 4 | 0.84 | 10–36 m | 0.95–1.35 |
| background | 26 m | 4 | 0.84 × 0.95 | 30–62 m | 0.85–1.20 |
| understory | 16 m | 3 | 0.84 × 0.68 | 12–50 m | 0.40–0.70 |

Configured expected candidate mean is approximately **1,997** versus approximately **1,069** in v1 (about **+87%**). The canonical 4 m route exclusion remains fail-closed, while the nearest generated band now starts at 10 m so the future R4 flat road/shoulder corridor is not crowded by the forest correction.

Status after the source update: **REAUTHOR_PENDING / PERFORMANCE_REVALIDATION_PENDING / VISUAL_REVIEW_PENDING**.

## Repository evidence checkpoint

- Full Stage 3G proof source: **run #510 / 36341840827** on pre-squash equivalent tree `94adc3dd19574dfb023fafcdc98b1983b82e2361` — **PASS**.
- target_density_v2 performance source: **run #2 / 36340735616** — forest **12.290 ms frame p95 / 9.817 ms GPU p95 / 101.90 FPS avg** — **PASS**.
- Stable triptychs **1200 / 4900 / 8000 m** are retained directly in `docs/visual-history/stage-3g/R3-forest-target-density/captures/` with SHA-256 in the manifest.
- Current visual status: **IN_REVIEW**. The 4900 m forest view remains the acceptance view; AFTER stays **PENDING** until a visual decision is recorded.
