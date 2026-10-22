# YACS Lesson07: registered real Stage3 scree-mask diagnostic (2026-10-22)

## Status and provenance

**Source crop: VERIFIED DIAGNOSTIC ONLY.** Do not promote this to whole-area or original Pegasus Stage3 authoring acceptance. The owner authorizes CC0 substitute textures, but the original SideFX HDA workflow, spatial registration, and untouched 16,000² Sa Calobra height/masks are mandatory.

[Native Stage3 scree crop run 39794174742](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39794174742): both the hosted preflight and native Windows readback passed. [Retained artifact 12432611716](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39794174742/artifacts/12432611716) contains the raw bounded scree array and both native/external receipts.

The historical input is `D:/yacs/work/lesson06-unified-20261019/stage3_scree.bgeo.sc`, 96,479,665 bytes, SHA256 `2af8ce5b467db28613c2033677c444dba5a89af943b906b01258a0b44106edb7`. Native ginfo identified exactly one 16,000×16,000 scree_mask volume. Producer receipt `stage3_scree.json` agrees with that hash. **Its full upstream source lineage is still unverified**: historical `stage4c_cliff.bgeo.sc` is 4,308,246,202 bytes and was deliberately not hashed during the bounded metadata audit, and its standalone producer receipt was absent in the audited directory. Source cache was never rewritten.

The 256×256 scree crop was independently matched in source voxel indices and world coordinates against the accepted 7-layer real Sa Calobra proof, [run 39785285512](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39785285512).

## What is actually in the site

| Metric | Historical real Stage3 scree | Old temporary cliff-mask proxy |
| --- | ---: | ---: |
| Nonzero 0.5-m resolution samples | **8,619** | **51,727** |
| Coverage among 65,536 sample sites | 13.15% | 78.93% |
| Source mask mean | 0.00889685 | 0.72815663 |
| Maximum source value | 0.60774755 | 1.0 |

Only **7 of 65,536** true Stage3 scree cells exceed intensity 0.5. The historical scree is a much more restrained surface application than the overbroad temporary cliff proxy. The numbers are computed from the retained verified NPZ files; this is not a render or photographic comparison.

- True Stage3 extracted crop SHA256: `0109fc20c375e5658b424fec46c06bf55ff534ceae08952fc571015e8a93a942`.
- Source world-coordinate corners: approximately `[-19.249916, 0, -1780.250122]` to `[108.250137, 0, -1907.750122]` (metres).
- Output on Windows: `D:/yacs/work/lesson07-cc0-real-crops/39794174742-1/`, including `scree-real-crop.npz`, `scree-real-crop.json`, `scree-diagnostic-verified.json`.
- No terrain/Alpha/Stage2 source mutation, no original full-world cache recook, and no UE changes.

## Next native material check

The [real five-material SideFX HDA workflow](https://github.com/karnalooch/YetAnotherCyclingSim/actions/workflows/lesson07-polyhaven-real-material.yml) now supports explicit opt-in `--scree-token 39794174742-1` in `scripts/houdini/l07_real_material_canary.py`, which uses **the actual historical scree-mask voxels** in place of the temporary cliff proxy on exactly the same site. Source guard, native height and original mask byte identity, actual source mask coverage, material images and scratch BGEO reopen remain required. The submitted run `39795208757` is *not a PASS claim*: check [its current live status](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39795208757) before using its evidence.

Still outstanding: historic Stage3 upstream lineage, the author's full material/tint/occlusion/curvature graph, a separate coastal site with sand coverage, full area native authoring memory proof and compliant UE D/N/ORD(p) arrays/Lit viewport. PR #474 must remain Draft; `LESSON07_TECHNICAL_PASS=false` and `performance_pass=false`.

Proof provenance should not be confused: **preexisting Stage3 scree source + real-site registered crop** is supported, **production-authoritative scree output** is not.
