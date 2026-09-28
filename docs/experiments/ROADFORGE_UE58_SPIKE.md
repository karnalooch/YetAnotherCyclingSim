# RoadForge -> UE 5.8 compile spike

**Issue:** #218  
**Status:** ACCEPTED as a compile donor; minimal donor extraction is under proof  
**Branch:** `spike/r4-1f-roadforge-ue58`  
**Upstream:** `YuuhenR/roadforge-osm-ue5-procedural-city@781cb046483cc1887e80085aacf0fb2951f4746d`  
**License:** MIT

## Hypothesis

RoadForge's procedural road-mesh primitives can be reused as the presentation-road donor for YACS after a bounded UE 5.8 adaptation, avoiding a bespoke road generator.

## Imported boundary

The first compile attempts imported the upstream runtime module to establish compatibility. After the successful UE 5.8 proof, the branch is intentionally reduced to the YACS-relevant donor surface:

- `RoadForgeMeshUtils.{h,cpp}`;
- module bootstrap;
- MIT license and provenance.

The retained mesh utilities provide:

- flat road/shoulder ribbons;
- dashed marking ribbons;
- vertical strips for edges/curbs;
- polyline offsetting;
- bounded miter handling;
- per-vertex Z input for non-flat roads.

Omitted from the minimized donor:

- OSM parsing/downloading/projection;
- `AOSMRoadGenerator`;
- PCG scatter integration;
- RoadForgeEditor;
- material/editor-menu automation;
- sample cities, screenshots and texture payloads.

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

**Actual:** the real UE 5.8 editor build reached RoadForge compilation and failed with exit code 6. The compiler reported `C2027` / `C2672` because `LogRoadForge` was defined as a file-local static category in both `RoadForge.cpp` and `OSMRoadGenerator.cpp`. Unreal unity compilation can place both sources in one generated translation unit.

**Diagnosis:** bounded unity-build incompatibility, unrelated to road geometry.

**Fix:** rename only the module startup category to `LogRoadForgeModule`.

**Unrelated gate:** Governance also failed because the PR body initially omitted the exact required line `Auto-merge: manual`. PR metadata was corrected; no product code change was needed.

### Attempt 2 — unity-safe full runtime compile

**State:** PASSED / DONOR ACCEPTED

**Exact code SHA:** `8fd08105699ffc743abee6c74bf84385accc8735`  
**CI:** CyclingSim CI #657 / run `36418752759` — **SUCCESS**

**Proof:**

- trusted UE 5.8 editor build: **PASS**;
- build log: `Result: Succeeded`;
- build execution: **167.31 s**;
- scoped Automation: **26 discovered / 26 passed / 0 failed / 0 errors**;
- Automation process exit code: **0**;
- Aggregate CI: **PASS**;
- Governance: **PASS**;
- Dependency Review: **PASS**;
- Trivy filesystem: **PASS**;
- CodeQL C++: **PASS**;
- unresolved review threads: **0**.

The Automation log also reported SDK validation warnings for platforms not used by this Windows UE proof. The test process exited 0 and the YACS tally passed; they are not RoadForge compatibility failures.

### Attempt 3 — minimize the retained donor surface

**State:** PENDING

**Change:** remove OSM ingestion/generator and PCG source from the vendored module; remove HTTP/Json/XmlParser/DesktopPlatform/PCG dependencies; retain only module bootstrap + `RoadForgeMeshUtils` + `ProceduralMeshComponent`.

**Reason:** YACS already owns route truth and only needs road presentation geometry. The spike should prove the smallest useful legal donor, not carry a procedural-city subsystem into the simulator.

**Expected:** the minimized donor compiles on the same UE 5.8 lane and preserves all existing YACS Automation behavior.

### Exit

- **ACCEPTED**: minimized donor passes real UE 5.8 build + Automation + Aggregate CI. Next task is a bounded SP638 spline-to-RoadForge adapter / visual proof.
- **REJECTED**: the useful geometry donor requires broad rewrites or unsafe coupling disproportionate to its value.
- **BLOCKED**: infrastructure prevents a trustworthy result; keep the evidence and do not claim compatibility.
