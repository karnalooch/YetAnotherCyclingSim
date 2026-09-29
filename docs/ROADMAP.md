# YetAnotherCyclingSim — MVP roadmap

**Status:** authoritative delivery plan  
**Current milestone:** **M3 — Route & World Foundation**  
**Scope authority:** `PRODUCT_REQUIREMENTS.md`  
**World-building method:** `WORLD_BUILDING_BIBLE.md`

This roadmap answers **what must be delivered and in what order**.

It intentionally does **not** encode every experiment, proof or implementation attempt as another nested stage number. Concrete work belongs in GitHub Issues.

The pre-2026-09-29 roadmap with Stage 3G / 3H / R4.1 / B.x identifiers is preserved unchanged in:

- `archive/ROADMAP_STAGE_TREE_2026-09-29.md`

Those identifiers remain useful for historical PRs, workflows and evidence, but they are no longer the active planning model.

---

## 1. Planning rules

1. Product milestones use only `M0` through `M10`.
2. A milestone may contain **named workstreams**, not recursive numeric sub-stages.
3. A concrete task is identified by its GitHub Issue number and title.
4. Do not create identifiers such as `M3.4.2`, `R4.1B.3` or equivalent.
5. Historical workflow/check names may retain legacy identifiers until a separate migration is justified.
6. Architecture belongs in dedicated SSOT documents, not in roadmap nesting.
7. Experiments belong in `docs/experiments/` or an issue/PR, not in the active roadmap.
8. Proof history belongs in Visual History / Performance History.
9. A milestone closes only when its acceptance criteria pass.
10. Performance is measured throughout development, not postponed to M10.

---

## 2. Current product path

```text
M0 Repository Foundation          DONE
M1 Physics Core                  DONE
M2 Playable Runtime              DONE
M3 Route & World Foundation      IN PROGRESS
M4 Cornering Technique           BLOCKED by M3
M5 HUD & Session
M6 Rider, Bike & Cameras
M7 World Content & Life
M8 Weather & Audio
M9 Save & FIT Export
M10 MVP Stabilization
```

The current goal is still a complete playable ride from start to finish before broad polish.

---

## 3. Current milestone — M3 Route & World Foundation

### Goal

Produce a believable, deterministic Passo Giau route/world foundation that can support the later gameplay milestones without rebuilding the terrain and road architecture again.

### Named workstreams

| Workstream | Purpose | Current state |
|---|---|---|
| **Route truth** | canonical route XY, distance, grade, curvature and road-physics profile | established; remains authoritative |
| **Terrain** | real DTM -> metric deterministic Landscape foundation | active / proven source path; architecture being consolidated |
| **Road & Earthworks** | real SP638 alignment, road mesh, non-destructive cut/fill, shoulder tie-in | **current priority** |
| **Materials** | coherent terrain/road surface foundation | baseline exists; refine after geometry |
| **Biomes** | valley / forest / high-Alpine PCG and route exclusion | baseline exists; preserve and refine |
| **Proof** | rider-camera visual acceptance, exact-SHA technical evidence, performance | active |
| **Tooling** | reproducible authoring, remote editor, CI/proof orchestration | active support work |

### Immediate order

1. Put the production Landscape on the `WORLD_BUILDING_BIBLE.md` layer model.
2. Preserve the canonical DTM as `Base_DTM`.
3. Use real SP638 alignment as the road presentation source.
4. Author road cut/fill on a non-destructive `Road_Earthworks` layer or equivalent reproducible path.
5. Generate the final road mesh independently from the Landscape vertex grid.
6. Add dedicated cliff/retaining geometry where a heightfield is the wrong representation.
7. Re-apply/refine materials and PCG after geometry is stable.
8. Validate from the rider camera.
9. Run the relevant performance checkpoint.
10. Close M3 only after the complete route/world foundation is accepted.

### M3 exit criteria

M3 is complete when:

- route/physics authority is stable and documented;
- macro terrain is reproducible from canonical source data;
- road alignment is real-data-first;
- road/terrain integration no longer depends on fragile exact seams;
- the Landscape workflow is non-destructive and reproducible;
- valley / forest / high-Alpine world foundation remains usable;
- rider-camera proof has no obvious grid, floating-road, black-wedge or major intersection failures;
- required exact-SHA Unreal proof passes;
- the relevant 1080p/60 performance budget passes on the reference PC;
- documentation and provenance are current.

---

## 4. M4 — Cornering Technique

### Goal

Make cornering a real gameplay skill without adding crash simulation to MVP.

### Required outcome

- deterministic cornering state;
- power/cadence timing matters;
- line widening / controlled slip / speed or time loss can occur;
- technique score is understandable;
- assistance is configurable;
- road physics uses the canonical smooth physics profile, not noisy render geometry.

### Entry gate

M3 route/world foundation accepted.

---

## 5. M5 — HUD & Session

### Goal

A complete ride is understandable from start to finish.

### Required outcome

HUD exposes the MVP information defined in Product Requirements, including power, cadence, speed, grade, distance, time and route progress/profile.

Session flow has reliable start, run, finish and restart behavior.

---

## 6. M6 — Rider, Bike & Cameras

### Goal

Replace placeholders with one believable rider+bike presentation.

### Required outcome

- one production rider;
- one road bike;
- required camera modes;
- mocap/retargeting pipeline where appropriate;
- stable rider-bike contact;
- animation cost fits the performance budget.

Rider visual animation remains presentation; simulation physics stays deterministic and testable separately.

---

## 7. M7 — World Content & Life

### Goal

Turn the technically correct M3 world foundation into a coherent, lived-in Alpine route.

### Required outcome

- stronger vegetation composition;
- rocks/cliffs/scree polish;
- roadside props and selected buildings;
- a few controlled "life" scenes;
- no unnecessary full traffic or crowd system;
- world remains performant and reproducible.

M7 adds content. It must not reinvent the M3 terrain/road architecture.

---

## 8. M8 — Weather & Audio

### Goal

Dynamic weather changes both presentation and the already-defined simulation inputs.

### Required outcome

- dynamic weather states;
- wet-road presentation;
- wind/weather audio;
- drivetrain / tyre / braking feedback;
- weather VFX within measured budgets.

---

## 9. M9 — Save & FIT Export

### Goal

Finish the local session-data loop.

### Required outcome

- local session save;
- deterministic summary data;
- valid FIT export for the supported MVP fields;
- clear failure handling.

---

## 10. M10 — MVP Stabilization

### Goal

Create the releasable single-player MVP.

### Required outcome

- full-route packaged proof;
- final performance baseline;
- asset/license freeze;
- no known release-blocking errors;
- reproducible build;
- final user-facing flow from launch to exported ride.

---

## 11. Completed foundations

### M0 — Repository Foundation — DONE

Repository, Git/LFS, Unreal project, contributor policy and baseline infrastructure exist.

### M1 — Physics Core — DONE

Deterministic, fixed-step cycling physics exists in the reference implementation and Unreal C++ with automated coverage.

### M2 — Playable Runtime — DONE

The Unreal runtime connects test input, fixed-step simulation and movement with diagnostic controls.

Detailed historical tranche numbering remains available in the archived roadmap and merged PR history.

---

## 12. Cross-cutting contracts

These are not product milestones.

| Contract | SSOT |
|---|---|
| MVP scope | `PRODUCT_REQUIREMENTS.md` |
| World construction | `WORLD_BUILDING_BIBLE.md` |
| Road physics | `ROAD_PHYSICS_PROFILE.md` |
| Runtime | `STAGE_2_RUNTIME_CONTRACT.md` |
| Route context | `STAGE_3_ROUTE_CONTEXT_CONTRACT.md` |
| Route geometry | `STAGE_3_ROUTE_GEOMETRY_CONTRACT.md` |
| World authoring library | `YACS_WORLD_AUTHORING_LIBRARY.md` |
| Assets / provenance | `ASSET_PLAN.md` |
| Performance | `performance/PERFORMANCE_FRAMEWORK.md` and `performance/BUDGETS.md` |
| CI/proof cadence | `CI_VALIDATION_TIERS.md` |
| Engineering governance | `ENGINEERING_PLATFORM.md` |

A cross-cutting contract can evolve without inventing a new product milestone number.

---

## 13. Proof model

World/art work uses:

```text
cheap iteration
  -> human visual candidate
  -> exact-SHA performance checkpoint
  -> heavy closeout proof
```

See `CI_VALIDATION_TIERS.md`.

A technical GREEN result and a visual PASS are independent decisions.

---

## 14. Legacy identifier mapping

| Legacy planning label | Active interpretation |
|---|---|
| Stage 0 | M0 |
| Stage 1 | M1 |
| Stage 2 | M2 |
| Stage 3 / 3G / 3H | M3 Route & World Foundation |
| Stage 3G R4 / R4.1 / R4.1B.* | historical M3 world-recovery work |
| Stage 3G R5 rendering tech | M3 proof/performance workstream unless/until renamed |
| Stage 3G R6 tooling | M3 tooling workstream |
| Stage 4 | M4 |
| Stage 5 | M5 |
| Stage 6 | M6 |
| Stage 7 | M7 |
| Stage 8 | M8 |
| Stage 9 | M9 |
| Stage 10 | M10 |

Do not rename old PRs, evidence artifacts or workflow runs merely to make history look tidy.

---

## 15. Work-item example

Good:

```text
M3
Workstream: Road & Earthworks
Issue: #253 — enable non-destructive road earthworks
PR: one scoped implementation
Proof: named exact-SHA evidence
```

Bad:

```text
Stage 3G R4.1B.4.3.2-a
```

The issue tracker is where task-level detail lives.

---

## 16. Parallel work

Parallel work is allowed only when workstreams are genuinely independent and respect the repository branch/validation rules in `AGENTS.md`.

Documentation-only branches do not consume the implementation-branch limit.

A later milestone must not silently pull product scope forward merely because a supporting technical spike is convenient.

---

## 17. Post-MVP

Post-MVP ideas remain outside the M0-M10 delivery chain until MVP is stable.

Examples already explored historically include multiplayer/pack dynamics, expanded technical rider profiles, additional guidance systems, larger content sets and deeper progression.

Historical detailed specifications remain in the archived roadmap until they are promoted into dedicated post-MVP design documents.

---

## 18. Rule for future roadmap edits

Before adding a new roadmap heading, ask:

> Is this a product outcome, or merely a task/experiment?

If it is a task, create/update an Issue.

If it is architecture, update its SSOT.

If it is proof history, update the evidence area.

Only product outcomes belong in this roadmap.
