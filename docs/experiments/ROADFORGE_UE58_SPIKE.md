# RoadForge -> UE 5.8 compile spike

**Issue:** #218  
**Status:** PENDING UE 5.8 CI proof  
**Branch:** `spike/r4-1f-roadforge-ue58`  
**Upstream:** `YuuhenR/roadforge-osm-ue5-procedural-city@781cb046483cc1887e80085aacf0fb2951f4746d`  
**License:** MIT

## Hypothesis

RoadForge's runtime procedural road-mesh core can be reused as the presentation-road donor for YACS after a bounded UE 5.8 adaptation, avoiding a bespoke road generator.

## Imported boundary

The spike vendors only the runtime RoadForge module:

- OSM parsing / projection;
- procedural road mesh utilities;
- `AOSMRoadGenerator`;
- PCG scatter integration.

It does **not** vendor:

- RoadForgeEditor;
- material/editor-menu automation;
- lighting helpers;
- screenshots/sample cities;
- CC0 texture payloads.

The plugin descriptor is locally adapted from UE 5.7 to UE 5.8 and stripped to the runtime module.

## Safety boundary

- no changes to `FRouteGeometryProfile`;
- no changes to road/grade/banking physics;
- no changes to `L_CyclingTest`;
- no changes to PR #217 or its stacked base branches;
- no SP638 production integration in this spike.

## Proof required

1. normal path classifier marks the change as Unreal code;
2. trusted `yacs-ue58` lane builds `YetAnotherCyclingSimEditor`;
3. existing scoped Automation suites discover tests and pass;
4. Aggregate CI is green.

## Decision journal

### Attempt 1 — bounded runtime vendor

**State:** FAILED — small source compatibility issue, donor not rejected.

**Exact SHA:** `76a93781ca5310840a8f77b576dbb03a292c3c8d`  
**CI:** CyclingSim CI #656 / run `36418207953`

**Change:** import the upstream runtime module and preserve MIT license/provenance; adapt only the plugin descriptor to UE 5.8 and enable the plugin in the YACS project.

**Expected:** UE 5.8 compiles the module with at most small API compatibility fixes.

**Actual:** the real UE 5.8 editor build reached RoadForge compilation and failed with exit code 6. The compiler reported `C2027` / `C2672` at `RoadForge.cpp:11` because `LogRoadForge` is also defined as a file-local static log category in `OSMRoadGenerator.cpp`. Under Unreal unity compilation both source files can share one generated translation unit, making the duplicate static category name collide.

**Diagnosis:** bounded source-level unity-build incompatibility. This does not affect road geometry logic.

**Fix:** rename only the module startup category to `LogRoadForgeModule`; keep the generator category unchanged.

**Unrelated gate:** Governance also failed because the PR body initially omitted the required exact line `Auto-merge: manual`. The PR metadata was corrected; no product code change was needed for that gate.

### Attempt 2 — distinct unity-safe module log category

**State:** PENDING

**Change:** use `LogRoadForgeModule` in `RoadForge.cpp` and document the local adaptation.

**Expected:** compilation proceeds past the only error observed in Attempt 1; any next compiler error must be evaluated independently rather than weakening the build.

### Exit

- **ACCEPTED**: real UE 5.8 build + Automation + Aggregate CI pass. Next task is a bounded SP638 spline-to-RoadForge adapter / visual proof.
- **REJECTED**: port requires broad rewrites, unsafe coupling, or repeated engine/API surgery disproportionate to the road-mesh value.
- **BLOCKED**: infrastructure prevents a trustworthy build result; keep the failure evidence and do not claim compatibility.
