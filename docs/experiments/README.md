# YACS Experiment Journal

<!-- Generated/validated by scripts/evidence/render_experiment_journal.py. -->

This journal keeps successful, failed and superseded experiments in the repository so the team does not repeat disproven work or lose the reasoning behind accepted decisions.

Heavy runtime evidence (for example 4K Unreal captures) stays in GitHub Actions artifacts. The repository keeps the durable decision record and links back to the exact PR/commit/run. A visually failed experiment can still be a successful diagnostic experiment.

## Status vocabulary

- `TECHNICAL PASS` — the pipeline/implementation proved what it was meant to prove; visual acceptance may still be pending.
- `VISUAL FAIL` — technically valid enough to inspect, but rejected from the rider-camera visual gate.
- `ACCEPTED` — accepted as the current baseline/decision.
- `SUPERSEDED` — useful historical result replaced by a better path.
- `BLOCKED` — experiment could not reach its intended proof.
- `IN PROGRESS` — evidence is still being gathered.

## Fast path for new experiments

1. Add one small JSON record under `docs/experiments/records/`.
2. Run `python scripts/evidence/render_experiment_journal.py`.
3. Commit the record plus refreshed index with the experiment code/decision.
4. Keep large screenshots/log bundles in Actions artifacts unless a human accepts one as a long-term visual baseline.

The renderer is standard-library-only and intentionally not coupled to the heavy Unreal authoring workflow.

## History

| Date | Stage | Area | Status | Experiment record | PR | Run |
|---|---|---|---|---|---:|---:|
| 2026-10-03 | M3 / Tooling | tooling | **TECHNICAL PASS** | [DVC Mallorca source lifecycle and reproduction spike](records/2026-10-03-dvc-mallorca-lifecycle-spike.json) | [#340](https://github.com/karnalooch/YetAnotherCyclingSim/pull/340) | — |
| 2026-09-28 | R4.1B | terrain | **VISUAL FAIL** | [Veneto 5 m DTM -> 4033 Landscape candidate](records/2026-09-28-veneto-dtm-4033-landscape.json) | [#215](https://github.com/karnalooch/YetAnotherCyclingSim/pull/215) | [36395726623](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36395726623) |
| 2026-09-28 | R4.1B | terrain | **TECHNICAL PASS** | [4K FXAA Landscape geometry diagnostic](records/2026-09-28-veneto-4k-fxaa-diagnostic.json) | [#215](https://github.com/karnalooch/YetAnotherCyclingSim/pull/215) | [36399060374](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36399060374) |
| 2026-09-28 | R4.1B | terrain | **SUPERSEDED** | [TINITALY 10 m DEM bootstrap and Unreal heightmap preparation](records/2026-09-28-tinitaly-dem-bootstrap.json) | [#212](https://github.com/karnalooch/YetAnotherCyclingSim/pull/212) | [36357523138](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36357523138) |
| 2026-09-28 | R4.1B.1 | road-terrain | **VISUAL FAIL** | [SP638 cyclist-height Unreal rider proof](records/2026-09-28-sp638-rider-proof.json) | [#216](https://github.com/karnalooch/YetAnotherCyclingSim/pull/216) | [36409905697](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36409905697) |
| 2026-09-28 | R4.1B.1 | road | **TECHNICAL PASS** | [Persist official SP638 spline in L_PassoGiauTerrainSpike.umap](records/2026-09-28-sp638-persisted-spline.json) | [#216](https://github.com/karnalooch/YetAnotherCyclingSim/pull/216) | [36409905697](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36409905697) |
| 2026-09-28 | R4.1B.1 | road | **TECHNICAL PASS** | [Official Veneto SP638 road extraction and centerline preparation](records/2026-09-28-sp638-official-road-source.json) | [#216](https://github.com/karnalooch/YetAnotherCyclingSim/pull/216) | [36409905710](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36409905710) |
| 2026-09-28 | R4.1B.2 | road-terrain | **VISUAL FAIL** | [SP638 bounded hairpin corridor cut/fill proof](records/2026-09-28-sp638-hairpin-corridor-cut-fill.json) | [#217](https://github.com/karnalooch/YetAnotherCyclingSim/pull/217) | [36415573299](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/36415573299) |

## Policy

- Never delete a meaningful failed record merely because the next attempt works.
- Prefer `SUPERSEDED` over rewriting history.
- A green CI result never overrides a human rider-camera visual rejection.
- Record the hypothesis, result, retained pieces, rejected pieces and next decision.
- Keep physics/simulation truth separate from presentation experiments unless an explicit reviewed migration changes that contract.
