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

The plugin descriptor is locally adapted from UE 5.7 to UE 5.8 and stripped to the runtime module. Upstream source remains otherwise unchanged for the first compile attempt.

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

**State:** PENDING

**Change:** import the upstream runtime module and preserve MIT license/provenance; adapt only the plugin descriptor to UE 5.8 and enable the plugin in the YACS project.

**Expected:** UE 5.8 compiles the module with at most small API compatibility fixes.

**Actual:** waiting for exact-SHA CI evidence.

### Exit

- **ACCEPTED**: real UE 5.8 build + Automation + Aggregate CI pass. Next task is a bounded SP638 spline-to-RoadForge adapter / visual proof.
- **REJECTED**: port requires broad rewrites, unsafe coupling, or repeated engine/API surgery disproportionate to the road-mesh value.
- **BLOCKED**: infrastructure prevents a trustworthy build result; keep the failure evidence and do not claim compatibility.
