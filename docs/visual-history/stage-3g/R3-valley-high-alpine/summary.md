# VH-3G-R3-001 — Stage 3G / R3 — Valley + High-Alpine PCG

## Final state

- Technical status: **MERGED**
- Visual status: **VISUAL_ACCEPTED**
- Issue: **#187 — CLOSED**
- PR: **#192 — MERGED**
- Merge commit: `02ff23f0a24228432ae9c34eb65aa4cb3694ae1d`
- Merged-main proof: **CyclingSim CI #421 / 36308910299 — GREEN**

R3 is complete as the accepted valley/high-Alpine biome and massing baseline. It is not the final Stage 7 environment-art pass, and it does not close the remaining Stage 3G terrain, road, atmosphere or explicit environment-performance gates.

## Provenance chain

| State | Revision | Proof | Decision |
|---|---|---|---|
| **BEFORE** | R2 merged baseline `fd77094…` | CI #398 / `36299298530` | `VISUAL_ACCEPTED` |
| **NOW** | R3 visual revision `58c89674…` | CI #417 / `36305204327` | `VISUAL_ACCEPTED` |
| final sync | `d7dd75a8…` | CI #420 / `36308404800` | exact-SHA technical PASS |
| **AFTER** | merged `main` `02ff23f0…` | CI #421 / `36308910299` | `MERGED + VISUAL_ACCEPTED` |

## Why Visual History mattered

The rejected R3 checkpoints remain part of the history:

- **#408 / `0148f894`** — technical PASS, visual reject: persisted PCG graphs were not visibly consumed by the reference scene.
- **#412 / `07e0803b`** — technical PASS, visual reject: real massing appeared but was oversized and floating.
- **#415 / `7de2cc46`** — technical PASS, visual reject: scale improved, but distant high-Alpine massing still lacked terrain support.
- **#417 / `58c89674`** — technical PASS and visual acceptance: massing became grounded on supported presentation terrain.

This is the intended separation between technical and visual acceptance.

## Final merged-main proof

CI #421 ran against exact merged SHA `02ff23f0a24228432ae9c34eb65aa4cb3694ae1d`.

- Unreal build + scoped Automation: **PASS**
- Automation report: **70 / 70 passed**, 0 failed, 0 errors
- Stage 3G full validation: **PASS**
- Fresh Load: **PASS**
- Map Check: **0 errors / 0 warnings**
- Git LFS fsck: **PASS**
- Visual Capture: **PASS**
- Capture resolution: **1920×1080**
- Required distances: **1200 / 4900 / 8000 m**
- Proof artifact: `stage3g-full-validation-36308910299-1`

The artifact proves successful 1080p capture and the Stage 3G functional/visual contract. It does **not** contain a dedicated environment FPS/GPU budget result, so the separate performance-sanity gate remains open where the asset plan requires it.

## Final captures

| Capture | BEFORE SHA-256 | NOW SHA-256 | AFTER SHA-256 |
|---|---|---|---|
| Valley 1200 m | `de391fb72074…` | `169ff6fff360…` | `5cefb738c8e0…` |
| Forest 4900 m | `c1b1b6a3109e…` | `56233de89d86…` | `867144551a0c…` |
| High Alpine 8000 m | `d1491bbfd506…` | `189e3f63fabb…` | `7dc5dfd18409…` |

The full source hashes and artifact provenance are recorded in `capture-hashes.json` and `manifest.json`.

## Durable final triptychs

The repository-retained final `BEFORE | NOW | AFTER` evidence is:

- `captures/01_valley_1200m_triptych.jpg` — SHA-256 `eb3127aa0ab31af9c20197c4f1ea7776f84e38dbabf1db9979ac5ab6151721a0` — 164622 bytes
- `captures/02_forest_4900m_triptych.jpg` — SHA-256 `be8d00a92f46fd4d9fd5135d89710fe003761fd98caff40a81e3a54525c8fce7` — 164139 bytes
- `captures/03_high_alpine_8000m_triptych.jpg` — SHA-256 `84f3f2830b1cb19d0da9afb24dfd8f440323f63854d0e7a5aafc16bd30a23ea0` — 211285 bytes

Each final triptych is 1920×576 and contains genuine R2, accepted R3 pre-merge and merged-main R3 captures. AFTER is no longer a placeholder.

## Decision

- Technical acceptance: **YES**
- Visual acceptance: **YES**
- Merge acceptance: **YES**
- Visual History entry: **CLOSED**
- Remaining work: continue the broader Stage 3G reference-environment gates without reopening R3 unless a regression is discovered.
