# YetAnotherCyclingSim — MVP roadmap

**Status:** authoritative delivery plan  
**Current milestone:** **M3 — Route & World Foundation**  
**Scope authority:** `PRODUCT_REQUIREMENTS.md`  
**World-building method:** `WORLD_BUILDING_BIBLE.md`

**Current M3 checkpoint — 2026-10-10:** [#363](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363) is completed and its whole-area material foundation is accepted and frozen. [PR #446](https://github.com/karnalooch/YetAnotherCyclingSim/pull/446) merged into `main` as `ad9a487ba2177fd49bb2d90784bac9a9f661ab3b` after [protected CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37978579196) passed. The delivery order is **#384 bounded official MCP inspection/test spike → #364 asphalt/shoulder → #365 world graph**. #384's fixed native session, separate [InputBoundary](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38039426402) and authenticated [source-only receipt readback](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38040872136) passed. Start #364 only after protected [PR #467](https://github.com/karnalooch/YetAnotherCyclingSim/pull/467) is merged and [#384](https://github.com/karnalooch/YetAnotherCyclingSim/issues/384) is closed as completed; then stop MCP infrastructure work.

Acceptance covers the material baseline on the **2,016.5 m × 2,016.5 m / 1024-component** working Landscape, not a finished rideable world or completed M3. [The material handoff](tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md) pins the saved/fresh-rendered consumer and native evidence. Canonical-map promotion, unresolved road/CUT/cliff/contact geometry and production PCGEx admission remain outside this acceptance. Performance is **`DEFERRED_AFTER_M3` / `performance_pass: false`**.

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

### Approved world destination — complete real-road coverage

Owner decision of 2026-10-01, with the active terrain benchmark recorded by Issue #312: the final Sa Calobra world must include all roads that actually exist inside the explicit project area, not just Ma-2141 or a few selected rides. [Product Requirements section 3.1](PRODUCT_REQUIREMENTS.md#31-docelowo-wszystkie-rzeczywiste-drogi-obszaru) owns the scope; [World Building Bible section 7.4](WORLD_BUILDING_BIBLE.md#74-full-area-real-road-network-target) owns coverage, topology, provenance and regeneration acceptance.

This destination is approved but not implemented by its documentation record. First import and validate the Sa Calobra MDT50cm terrain, then prove the Ma-2141 corridor before delivering additional roads and junctions through scoped Issues. Plan playable-route activation separately from world coverage without reducing the final network to scenery only. The present MVP still proves one complete ride; this decision does not start later gameplay systems or change M0-M10 entry/exit rules. The expansion schedule remains to be assigned after the inventory and foundation proof.

The owner also approved mixed asphalt/gravel riding (Issue #297; Product Requirements section 3.2). The existing reference model may receive an independent synthetic support proof now; this does not activate roads, calibrate gravel physics or complete a future gameplay milestone. After the terrain/road foundation and source inventory are accepted, select a real mixed-route checkpoint before expanding activation. A fixed mixed itinerary is sufficient initially; free junction navigation remains a separate feature.

---

## 3. Current milestone — M3 Route & World Foundation

### Goal

Produce a believable, deterministic Sa Calobra route/world foundation that can support the later gameplay milestones without rebuilding the terrain and road architecture again.

### Named workstreams

| Workstream | Purpose | Current state |
|---|---|---|
| **Route truth** | canonical route XY, distance, grade, curvature and road-physics profile | established; remains authoritative |
| **Terrain** | real DTM -> metric deterministic Landscape foundation | active / proven source path; architecture being consolidated |
| **Road & Earthworks** | real Ma-2141 alignment, road mesh, non-destructive cut/fill, shoulder tie-in | remaining road/CUT/contact debt; separate #337/#459 scopes |
| **Materials** | coherent terrain/road surface foundation | #363 whole-area Landscape foundation accepted/frozen; #364 asphalt/shoulder follows #384's protected delivery gate |
| **Biomes** | valley / forest / exposed limestone-upland PCG and route exclusion | baseline systems exist; preserve the tooling and retune presentation for Mallorca |
| **Proof** | rider-camera visual acceptance, exact-SHA technical evidence, performance | active |
| **Tooling** | reproducible authoring, remote editor, CI/proof orchestration | active support work |

### Foundation dependency order

The list below describes architectural dependencies, not a restart of completed work. The current delivery handoff is #384 → #364, as recorded above; unresolved geometry remains separately scoped.

1. Put the production Landscape on the `WORLD_BUILDING_BIBLE.md` layer model.
2. Preserve the canonical DTM as `Base_DTM`.
3. Use real Ma-2141 alignment as the road presentation source.
4. Author road cut/fill on a non-destructive `Road_Earthworks` layer or equivalent reproducible path.
5. Generate the final road mesh independently from the Landscape vertex grid.
6. Add dedicated cliff/retaining geometry where a heightfield is the wrong representation.
7. After road geometry and earthworks are stable, execute the **post-road world-finishing sequence** below.
8. Validate that sequence on a bounded rider-camera section within the current Landscape before expanding beyond that Landscape; the validation section does not limit the authoring area.
9. Expand only the accepted systems beyond the current Landscape across the complete playable route.
10. Run required exact-SHA visual/technical checkpoints.
11. Close M3 implementation only after the assembled route/world foundation is accepted, retaining post-closeout #373 benchmark debt and pending performance admission.

### Post-road world-finishing sequence

This is an ordered M3 delivery sequence, not a new nested milestone hierarchy. Concrete implementation remains tracked by GitHub Issues, while `WORLD_BUILDING_BIBLE.md` remains the methodology authority.

**Owner clarification — 2026-10-04:** the current authoring area is the **entire existing Sa Calobra Landscape**, 2,016.5 m × 2,016.5 m (~4.07 km²), not a 500–1000 m strip. Prepare masks across that full grid and apply the material, biome, foliage, rock and roadside foundations across the current Landscape wherever their source/placement contracts permit. Preserve explicit unknowns and the frozen terrain/road geometry; full-area scope does not authorize invented geography or missing evidence.

**Appearance and performance acceptance also cover the entire current Landscape.** Review the different environments, road/terrain transitions and broad views, and measure representative traversal and demanding views across the full area. Record location-specific results so one fast or attractive section cannot hide problems elsewhere. Use the existing performance framework/budgets and milestone-driven capture cadence; this does not introduce new thresholds or require a heavy benchmark after every edit.

**Owner decision — 2026-10-09:** "wydajność zmierzymy po domknięciu m3".
The benchmark is due after the assembled M3 world is closed out, rather than
at each intermediate handoff. This supersedes the earlier 2A/2B measurement
deadline. Record `DEFERRED_AFTER_M3` with `performance_pass: false`; retain
whole-area owner visual acceptance, saved/fresh-rendered consumers, native
build/Automation/asset evidence and protected CI/review. The later benchmark
still measures the actual assembled consumer at its exact SHA against the
same full-area scope, reference hardware and budgets. No performance PASS or
later-stage exception is implied.

The 500–1000 m Golden Kilometer is an **additional representative check inside this Landscape**, not an acquisition boundary, reduced implementation scope or replacement for whole-Landscape visual/performance acceptance. Step 13 concerns subsequent expansion **outside the current Landscape** to the remaining playable route. It does not mean that the current Landscape must wait until step 13 to receive its environment foundation. Keep the full 13-step sequence as the execution scope; prepare the complete baseline mask set before detailed quality refinement.

1. [**World Authority inputs and masks**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/335) — establish reproducible spatial inputs for road/shoulder domains, route exclusion, terrain classes, slope/elevation/exposure and road-earthworks zones. Real-world source evidence owns geographically meaningful boundaries; procedural systems do not invent replacement geography.
2. [**Landscape material foundation**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363) — produce a coherent terrain material baseline for soil, grass, forest ground, exposed limestone/rock and earthworks transitions without using materials to hide unresolved geometry.
3. [**Road surface material system**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/364) — after full #363 closeout and the bounded official MCP adoption #384, establish the asphalt/shoulder presentation foundation, including edge breakup and later wetness compatibility. Visual materials remain presentation only; Road Physics Profile remains physics authority.
4. [**PCG/PCGEx world graph**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/365) — consume canonical route and World Authority outputs to derive stable road-adjacent, roadside, terrain and biome domains. PCG/PCGEx executes reconstruction rules; it does not become geographic or physics authority.
5. [**Route exclusion and safety corridor**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/366) — protect the rideable road and required clearance from trees, large rocks and incompatible props, with deterministic behavior that can be proven after reload/regeneration.
6. [**Biome generators**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/367) — establish source-faithful valley/lower-Mediterranean, forest and exposed-limestone presentation using deterministic generators and real spatial boundaries instead of hand-authored biome replacement.
7. [**Rock, cliff and scree dressing**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/368) — use dedicated meshes/procedural dressing where Landscape is not an adequate representation, especially road cuts, steep limestone faces and scree, while preserving one clear visual ground owner.
8. [**Foliage system**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/369) — place trees, shrubs, grass and understory through deterministic, budgeted instancing/culling/LOD or Nanite policies rather than unconstrained scatter density.
9. [**Roadside procedural foundation**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/370) — establish rule-driven placement for the structural roadside layer such as barriers, posts, signs, walls, drainage and bounded rock/vegetation treatment where source evidence or admitted rules justify it. Rich hero dressing, selected buildings and lived-in scenes remain M7.
10. [**Surface and biome blending**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/371) — remove hard visual seams between asphalt, shoulders, soil, rock and biome domains through reproducible transition logic; blending may improve presentation but may not conceal geometric disagreement.
11. [**Whole-Landscape visual review and rider-camera check**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/372) — review appearance across the entire current Landscape with integrated materials, PCG/PCGEx, biomes, foliage, rocks and roadside foundation. Include different environments, road/terrain transitions and demanding broad views. An approximately **500–1000 m** Golden Kilometer supplies an additional detailed rider-camera check; it does not replace the full-area review. Concrete proof remains tracked in scoped Issues rather than a new roadmap stage.
12. [**Whole-Landscape reference-PC performance gate**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/373) — retain the performance obligation and measure it after assembled M3 closeout under the 2026-10-09 owner decision. Measure traversal and representative demanding views across the entire current Landscape against `performance/PERFORMANCE_FRAMEWORK.md` and `performance/BUDGETS.md`, including the 1920×1080 / 60 FPS target on the reference RTX 2070 Super system and applicable frame/GPU/memory/streaming evidence. Retain location-specific results; a passing Golden Kilometer alone does not admit whole-Landscape performance.
13. [**Full-route rollout**](https://github.com/karnalooch/YetAnotherCyclingSim/issues/374) — after the entire current Landscape is visually and technically accepted, expand the same accepted systems **beyond the current Landscape** across the remaining playable route and verify representative problem areas plus the end-to-end rider-camera experience. Record performance as deferred to after assembled M3 closeout, rather than claiming that the rollout is within budget. The entire current Landscape is the preceding authoring and acceptance area, not a new expansion target at this step.


**Issue dependency gate:** steps are separate execution issues in the YACS — MVP Project. Reuse #335 for step 1; each later issue has a native GitHub `blocked_by` dependency on its immediate predecessor. Steps 2–13 remain `Blocked` while that predecessor is open. Do not begin implementation, open an implementation PR or move a step to Ready/In progress until the predecessor is completed with required proof and merged implementation where applicable. Closing as not planned or merely having green CI does not satisfy the gate. Change the order or remove a dependency only with explicit owner authorization. GitHub records the dependency; this execution rule governs agents because the dependency does not itself prevent branch/PR creation.

**Authorized execution-order exception — 2026-10-09:** keep the 13 step identifiers above, but execute **#372 whole-area visual/technical acceptance → #374 full-route assembly and implementation closeout → #373 performance measurement**. Retain #372 as an additional prerequisite of #373. The native graph still has #373 blocking #374 and must be reconciled before #374 starts; this documentation does not change dependencies or Project columns. #363 is completed, so #384's material entry gate is satisfied; downstream work remains gated by its own open predecessors. M3 implementation closeout carries the outstanding benchmark debt; performance/release admission remains pending until measured evidence passes.

### Official Unreal MCP adoption between materials and asphalt

Owner decision, 2026-10-05: [#384](https://github.com/karnalooch/YetAnotherCyclingSim/issues/384)
inserts a bounded adoption checkpoint between #363 and #364. The informal name
"step 2.5" does not create a new milestone or renumber the 13 delivery steps.
The order is **#363 fully accepted/merged → #384 → #364 → #365**; #364 retains
its original #363 dependency and additionally depends on #384.

#384's entry condition requires #363's whole-Landscape owner visual acceptance,
saved/fresh-rendered consumer evidence, required exact-SHA technical/review gates
and merged implementation. Performance measurement is deferred until after
assembled M3 closeout under the 2026-10-09 decision; it is not this entry gate.
That condition was satisfied by the accepted material closeout and protected
merge recorded above. Historical rejected candidates remain rejected; the
accepted whole-area baseline has its own evidence. A connection test or a
closed-as-not-planned state cannot satisfy adoption DoD. #384 implementation
in PR #467 has passed the fixed official native session in
[run 38027596123](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38027596123)
at runtime SHA `241104de320f8417c7abc4dd973ac148ed98a66d`. Its bounded verified
summary records one passing `CyclingPhysics.RoadPhysics.ProfileInterpolation`
test and complete BOB inspection with `REVIEW_REQUIRED` / `INSPECTOR_ONLY` and
all false authoring/admission flags. Authenticated original receipt readback
passed in [run 38029602978](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38029602978).
Separate `YacsBobInspection.InputBoundary` passed in
[run 38039426402](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38039426402)
at execution SHA `2016a91f03438f1d866be0eb26f3ae49fd43b803`, using the plugin
compiled at `0ee5eaf39e0d673fee061f7e33372710278d50be`. Original runtime
receipt admission flags remain false. Authenticated source-only
[receipt readback 38040872136](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38040872136)
passed at reader SHA `df80c44a027102560767d9aaa14edab12526fd6d`; it performed
no new native session or unit execution. Start #364 only after protected [PR #467](https://github.com/karnalooch/YetAnotherCyclingSim/pull/467)
is merged and #384 is closed as completed;
see the [MCP evidence and remaining gates](UE_MCP_WORLD_GENERATION.md#official-unreal-mcp-adoption).

The [MCP decision and DoD](UE_MCP_WORLD_GENERATION.md#official-unreal-mcp-adoption)
cap the spike at one map/scene, one Actor/UObject inspection, one existing
Automation Test and one real BOB inspection returning result/proof/receipt.
Prove the restricted surface and safety parity before cutover. After success,
**STOP infrastructure work and return to #364**. #376 performance tooling,
#377 buildings and #365 graph authoring remain separately gated work.
This fixed inspector does not admit stock `MaterialInstanceTools`; #364 needs
separate version-matched schemas, argument/resource restrictions and material-only
native authoring proof before using those tools.

From step 3 onward, use official Epic MCP for supported generic editor control
within YACS constraints; do not add custom generic workarounds. Custom toolsets
carry only YACS domain knowledge. MCP stays an interface; BOB, World Authority,
route/physics contracts and tests/proofs keep authority. Native PCG is the
foundation, with pinned PCGEx extensions for named gaps. The existing Embark-first
evidence review, producer/consumer contracts and all governance gates remain.

### Deferred surface-review polish

Owner decision, 2026-10-04: retain the red surface problem-review overlay from
the merged [coverage audit](experiments/sa-calobra-surface-coverage-2026-10-04.md)
for the final polish/review pass tracked by #372. Defer loading that overlay
into the live editor and reviewing P1–P5 / R4C2 / R4C3 until that pass. Keep
the native overlay, flag raster, manifest and pinned source hashes available;
uncolored pixels are not independently validated. Unknowns and conservative
exclusions remain explicit when #363 consumes admitted inputs or documented
fallbacks. This decision does not promote RGB rock/soil candidates to truth.

On 2026-10-04 the owner authorized 2A baseline merge and progression to #363, and
requested that the 2A performance measurement be performed in 2B (#363), not at
2A closeout.
The frozen-baseline CI exception reports `DEFERRED_TO_2B`, never a performance
PASS. New material, mask, geometry, runtime configuration or producer changes
restore normal exact-SHA proof under that historical exception. The 2026-10-09
decision above supersedes its measurement deadline: the obligation now applies
to the assembled M3 consumer after closeout, not #363's intermediate handoff.
Required technical checks and protected CI admission must be resolved before
the predecessor is represented as completed. Deferred measurement is not PASS.

### M3 / M7 content boundary

M3 builds the **reproducible world factory and believable baseline**: authority inputs, materials, procedural domains, route exclusion, biome/foliage/rock foundations, structural roadside rules and their visual/performance proof.

M7 builds **richer authored content and life** on top of that foundation: stronger vegetation composition, selected buildings, hero roadside dressing and controlled lived-in scenes. M7 may extend and tune the accepted M3 systems, but it must not reinvent the terrain, road, World Authority, material or procedural-world architecture.

### M3 exit criteria

M3 is complete when:

- route/physics authority is stable and documented;
- macro terrain is reproducible from canonical source data;
- road alignment is real-data-first;
- road/terrain integration no longer depends on fragile exact seams;
- the Landscape workflow is non-destructive and reproducible;
- World Authority-backed masks/domains and generated presentation are reproducible, with route exclusion enforced;
- valley / forest / exposed limestone-upland material, biome, foliage and rock foundations are usable from the rider camera;
- the entire current Landscape has visual acceptance and technical admission before expansion beyond it; the Golden Kilometer is an additional detailed check;
- full-route world generation uses the accepted M3 systems rather than ad-hoc per-location reconstruction;
- rider-camera proof has no obvious grid, floating-road, black-wedge or major intersection failures;
- required exact-SHA Unreal proof passes;
- the deferred reference-PC 1080p/60 benchmark is explicitly retained for the assembled world after M3 closeout; performance admission remains pending until it actually passes;
- documentation and provenance are current.

### Legacy prototype-world retirement gate

`AStage3PrototypeTerrainActor` / the HISM-heavy prototype world is frozen as a regression scaffold during M3. No new world feature may target it. After the real Landscape/Ma-2141/PCG path satisfies the M3 exit proof with equivalent fresh-load, rider-camera, performance and exact-SHA coverage, the legacy actor/path may be removed in a bounded housekeeping PR without preserving it as a second production architecture.

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

Turn the technically correct M3 world foundation into a coherent, lived-in Serra de Tramuntana route.

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

For current M3 world assembly, the 2026-10-09 owner decision supersedes the
performance-before-closeout timing above: owner visual acceptance and required
exact-SHA technical/protected closeout proceed with `DEFERRED_AFTER_M3`, then
the assembled world is benchmarked under #373. Budgets and measured admission
remain unchanged. The legacy `L_CyclingTest` lane is regression-only unless
legacy authoring inputs change; it cannot admit the current Sa Calobra world.

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
