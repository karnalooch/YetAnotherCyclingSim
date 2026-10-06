# Fact-checked external architecture audit — 2026-10-06

**Status:** evidence / follow-up record  
**Issue:** [#389](https://github.com/karnalooch/YetAnotherCyclingSim/issues/389)  
**Repository baseline:** `main@00bdf3b5cffe2d815802658a6db02614f7c4cba7`  
**Authority:** none — this document does not replace Product Requirements, Roadmap, World Building Bible, Road Physics Profile, Asset Plan or CI Validation Tiers.

## Purpose

An external AI architecture audit was reviewed against the exact YACS repository revision above.

The audit was useful as a red-team prompt, but it mixed three different classes of statement:

1. valid concerns supported by repository evidence;
2. valid questions that are already owned by existing YACS workstreams;
3. false negative claims caused by incomplete repository retrieval being interpreted as proof of absence.

This note records the fact-check so future agents do not repeat either the useful investigation or the false repair work.

## Review method

Repository verification used the exact baseline revision and checked:

- the recursive Git tree rather than only the first retrieval page/chunk;
- runtime C++ under `Source/YetAnotherCyclingSim/`;
- C++ Automation tests under `Source/YetAnotherCyclingSim/Private/Tests/`;
- Editor C++ under `Source/YetAnotherCyclingSimEditor/`;
- `.gitattributes`;
- `Config/DefaultEngine.ini`;
- current CI and performance workflows;
- BOB inspector and adaptive terrain policy;
- `docs/ASSET_PLAN.md`, `docs/CI_VALIDATION_TIERS.md` and local-workspace documentation.

Counts in this document are revision-specific evidence, not permanent architecture requirements.

At `00bdf3b5` the recursive tree contains:

- **129** `.cpp/.h` files below `Source/YetAnotherCyclingSim/`;
- **40** C++ test files below `Source/YetAnotherCyclingSim/Private/Tests/`;
- **15** `.cpp/.h` files below `Source/YetAnotherCyclingSimEditor/`;
- **185** persisted `Content/Worlds/SaCalobra/CheckpointEarthworks/T_Cut_*.uasset` files (`000` through `184`).

The last count is especially important: the external audit reported only the first 18 CUT assets. That mismatch demonstrates why partial retrieval cannot support a negative or completeness claim.

---

## Findings that survived fact-check

### 1. Cold-start reproducibility and raw-data durability

**Classification:** verified risk, already owned  
**Owner:** [#339](https://github.com/karnalooch/YetAnotherCyclingSim/issues/339)

The external audit was directionally correct that a clean machine cannot yet be proven to reconstruct every required Sa Calobra input and accepted project state without relying on unresolved acquisition/hydration work.

Repository evidence:

- `docs/ASSET_PLAN.md` records that the currently registered transport snapshot contains MDS, LAZ and orthophoto inputs but not the complete MDT50cm source-tile set behind the 8x8 benchmark;
- `sa-calobra-8x8` is explicitly marked incomplete until those inputs are acquired/adopted;
- `YACS_ASSET_ROOT` is explicitly not synchronized or backed up automatically;
- `docs/tooling/LOCAL_WORKSPACE.md` documents the canonical home workspace and separates it from CI, but that operational path is not itself a clean-host proof.

Important correction:

The existence of `D:\yacs\project` is **not** by itself an architectural defect. It is a canonical host layout. The actual risk is whether authoritative source inputs, accepted checkpoints and required dependencies can be reconstructed from declared provenance without undocumented host knowledge.

Required closure remains under #339:

`fresh clone -> hydrate -> verify -> prepare -> build -> launch`

must be demonstrated on a clean/recreated host, with explicit reporting of missing, stale, valid and rebuildable data.

### 2. Render-performance admission must be measured on the accepted consumer

**Classification:** verified risk, existing gate already present  
**Owner:** [#373](https://github.com/karnalooch/YetAnotherCyclingSim/issues/373)

`Config/DefaultEngine.ini` enables a demanding renderer configuration:

- Lumen GI;
- Lumen reflections;
- Virtual Shadow Maps;
- Ray Tracing;
- Substrate;
- mesh distance fields.

That is a legitimate performance risk on the RTX 2070 SUPER reference target.

The external audit was wrong to convert that configuration directly into a deterministic FPS failure from generic millisecond estimates.

YACS already has fail-closed measurement infrastructure:

- `CyclingSaCalobraPerformance.spec.cpp`;
- `CyclingStage3GEnvironmentPerformanceProof.spec.cpp`;
- `Invoke-YacsSaCalobraPerformance.ps1`;
- `Invoke-YacsStage3GEnvironmentPerformance.ps1`;
- explicit RTX 2070 SUPER identity checks;
- 1920x1080 rendered execution;
- `TargetFps = 60.0`;
- `FrameBudgetMs = 1000 / TargetFps`;
- Frame p95 and GPU p95 acceptance against the frame budget;
- maximum 5% over-budget frames;
- missing GPU timing as failure;
- non-zero failure exit.

Therefore the correct next action is measurement under #373, not a speculative renderer rewrite.

If the accepted candidate fails, diagnostics may compare RT/Lumen/Substrate/VSM variants, but the failing subsystem must be measured before architecture is changed.

### 3. BOB construction readiness is still open

**Classification:** verified risk, deliberately fail-closed  
**Owner:** [#303](https://github.com/karnalooch/YetAnotherCyclingSim/issues/303)

BOB's current inspection layer is real and explicit:

- `scripts/worldgen/bob_terrain_fit_inspector.py` classifies `CONTACT_OK`, `CUT_REQUIRED`, `FILL_REQUIRED`, `STRUCTURE_REVIEW`;
- the inspector publishes `role = INSPECTOR_ONLY`;
- `earthworks_authoring_permitted = false`;
- `geometry_repair_executed = false`;
- `Base_DTM` is preserved.

The historical construction experiment is also correctly preserved as failed evidence:

- CUT samples improved from **986 to 3**;
- FILL samples regressed from **2046 to 13642**;
- the recipe was rejected rather than promoted.

This is a real open problem: inspection is more mature than production construction/admission.

However, the external audit incorrectly claimed that BOB lacks bounded terrain policy. `worldgen/terrain/adaptive_terrain_policy.json` already defines:

- stacked-branch XY/Z thresholds;
- retaining cut/fill threshold;
- hairpin radius/branch thresholds;
- minor cut/fill limits;
- transition widths;
- per-strategy maximum ground adjustment;
- dedicated `hairpin_clearance` and `retaining_or_cliff` strategies.

The next BOB work should therefore extend and prove the existing policy rather than invent a second one.

A particularly valuable missing proof is a **multi-level / stacked-hairpin conflict case**: a locally valid CUT/FILL operation must not bury, intersect or invalidate another nearby road branch at a different elevation.

---

## Rejected claims

### "There is no C++ physics core"

**Result:** rejected.

Runtime implementation exists in repository C++, including:

- `CyclingForces.cpp`;
- `SimulationStep.cpp`;
- `FixedStepRunner.cpp`;
- `CyclingSimulationSession.cpp`;
- `RiderInputController.cpp`;
- `RoadPhysicsProfile.cpp`;
- `RoadPhysicsProfileBuilder.cpp`;
- braking, cornering, grip-budget, consequence and route-geometry components.

`SimulationStep.cpp` contains the longitudinal energy/force integration path. `FixedStepRunner.cpp` orchestrates deterministic fixed steps and route/corner context.

The prototype presentation actor is not evidence of a Chaos rigid-body bicycle authority.

### "There are no physics or geometry tests"

**Result:** rejected.

The revision contains 40 C++ test files, including:

- `CyclingForces.spec.cpp`;
- `FixedStepRunner.spec.cpp`;
- `RoadPhysicsProfile.spec.cpp`;
- `RoadPhysicsProfileBuilder.spec.cpp`;
- `RouteGeometry.spec.cpp`;
- `LongRunDynamics.spec.cpp`;
- `GoldenRide.spec.cpp`;
- braking, cornering, grip, runtime and performance proof suites.

`FixedStepRunner.spec.cpp` explicitly covers deterministic frame-rate independence, which the external audit listed as an untested failure class.

### "Banking/cross-slope is missing from road physics"

**Result:** rejected as an architecture claim.

`RoadPhysicsProfile` contains:

- left/right cross-slope angles;
- locally resolved cross-slope;
- horizontal curvature;
- vertical curvature;
- width;
- surface id;
- wetness;
- roughness;
- transition-rate validation.

Tests cover planar banking, crown and transition behavior.

The valid open question is not whether the contract exists, but how real-road banking/cross-slope values are populated for production route data.

### ".gitattributes is truncated / LFS rules are absent"

**Result:** rejected.

The complete file includes LFS rules for, among others:

- `.uasset`, `.umap`;
- `.fbx`, `.blend`;
- audio formats;
- `.exr`, `.hdr`, `.tga`;
- Houdini formats;
- `.terrain`;
- `.tif`.

The audit saw an incomplete excerpt and interpreted it as the end of the file.

### "Performance tests have no hard thresholds"

**Result:** rejected.

The current performance harness has explicit 60 FPS, p95 frame/GPU and over-budget-ratio acceptance with fail-closed execution on reference hardware.

### "BOB has no terrain-modification limits"

**Result:** rejected.

Bounded policy exists in `adaptive_terrain_policy.json`. Whether those limits are sufficient for every real Mallorca case remains an engineering question, not an absence finding.

### "Only 18 CUT checkpoint textures exist"

**Result:** rejected.

The recursive tree contains 185 `T_Cut_*.uasset` files, `000` through `184`.

This is retained as a concrete example of retrieval truncation producing a false completeness claim.

---

## Unresolved questions worth keeping

The fact-check does not prove that every YACS subsystem is production-ready. The following questions remain valid and should be answered by their owning workstreams rather than by speculative audit conclusions:

1. Can #339 reproduce the required active-world inputs and project state on a clean host?
2. Does the accepted Sa Calobra consumer pass #373 on the RTX 2070 SUPER with the current renderer configuration?
3. If performance fails, which subsystem actually owns the cost?
4. Can #303 produce bounded, continuous, visually accepted earthworks from current inspection output?
5. Can BOB prove that a construction action on one hairpin branch cannot damage a nearby branch at another elevation?
6. Are real-road banking/cross-slope inputs sufficient for the production route, independent of the already-valid physics contract?
7. Which legacy Passo Giau workflows remain operational dependencies versus retirement candidates? Use the workflow lifecycle authority before deleting anything.

---

## Audit evidence rule for AI agents

Future external/AI audits must distinguish **absence of evidence** from **evidence of absence**.

A finding marked `CONFIRMED` or `HIGH` confidence must identify:

- exact repository SHA/ref;
- exact file path;
- relevant symbol/config/workflow key;
- enough source context to support the claim;
- the retrieval method used to establish completeness for negative claims.

For claims such as:

- "there are no tests";
- "there is no implementation";
- "there is no LFS rule";
- "there is no performance threshold";
- "there is no policy";

the auditor must prove that the search/listing was exhaustive enough for that scope.

A first page, first chunk, top-N search result or truncated tool response is **not** adequate evidence of absence.

If completeness cannot be established, the finding must be downgraded to `SPECULATIVE` and must not alter:

- ROADMAP status;
- Architecture Scorecard;
- MVP probability/risk score;
- deletion recommendations;
- subsystem ownership.

---

## Action map

| Concern | Current owner | Action |
|---|---|---|
| Clean-host / source durability | #339 | Complete reproducible hydration + clean-host proof |
| Whole-Landscape reference-PC performance | #373 | Measure accepted exact-SHA candidate before renderer changes |
| BOB construction readiness | #303 | Advance from inspector-only evidence to bounded admitted construction |
| Audit/retrieval false positives | #389 | Preserve this fact-check and evidence rule |

## Non-authority statement

This document is historical/evidence material.

If it disagrees with an authoritative YACS contract, the current authority document wins:

- product scope: `PRODUCT_REQUIREMENTS.md`;
- delivery: `ROADMAP.md`;
- world methodology: `WORLD_BUILDING_BIBLE.md`;
- road physics: `ROAD_PHYSICS_PROFILE.md`;
- assets: `ASSET_PLAN.md`;
- CI/proof: `CI_VALIDATION_TIERS.md`.

No runtime, world, renderer, BOB or milestone state changes are admitted by this documentation record.
