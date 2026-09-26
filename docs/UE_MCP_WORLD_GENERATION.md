# YACS UE-MCP world-generation architecture

**Status:** Stage 3G visual/asset recovery active; spike approved and still required before persistent MCP-driven worldgen  
**Tracking:** #85  
**Initial upstream:** `db-lyon/ue-mcp`  
**Reviewed pin:** `v1.3.9`  
**Unreal target:** UE 5.8.2 on the home/reference PC

## 1. Purpose

YACS will use UE-MCP as a **development-time Unreal Editor execution layer** for building and validating route environments.

UE-MCP does not replace the existing Stage 3 architecture. Route profile, geometry, persisted spline, fixed-step route context and `FSimulationState::DistanceM` remain authoritative.

```text
authoritative YACS route
        |
        v
     WorldSpec
        |
        v
   YACS MCP flows
        |
        v
UE-MCP bridge/actions
        |
        +--> Landscape / PCG
        +--> foliage / rocks / props
        +--> materials
        +--> lighting / atmosphere
        +--> proof capture
        |
        v
generated presentation
```

Actor or Pawn transforms remain presentation state and must never become authoritative route progress.

## 2. Architectural boundary

### Authoritative / protected

World generation must not redefine:

- route profile and route-distance boundaries;
- `FRouteGeometryProfile`;
- Stage 3 spline geometry;
- fixed-step context resolution;
- `FSimulationState::DistanceM`;
- physics;
- start/sector/finish semantics;
- Stage 4 cornering mechanics.

### Generated presentation

Persistent world-generation output will eventually be restricted to:

```text
/Game/Generated/YACS/**
```

Existing authored/prototype content outside that root is input/reference, not an autonomous write target.

The Stage 3G spike is stricter: it starts with inspection and transient verification only. Persistent writes are intentionally not enabled yet.

**Recovery note (26.09.2026):** the Stage 3G CI/authoring harness was proven by PR #155, but the real progressive source-asset + PCG baseline was not delivered. #85 therefore remains Stage 3G work rather than being deferred to the final Stage 7 art pass.

## 3. Why UE-MCP

The selected upstream already provides the Unreal Editor bridge, MCP categories for world authoring, YAML flows, retries/rollback, git snapshots, configurable guards and context strategies. We reuse those capabilities rather than creating a second editor automation framework.

## 4. Dependency policy

The spike pins stable `ue-mcp` **1.3.9**. Do not float `latest`. Upgrades require review because UE-MCP has direct write access to the editor project.

The upstream repository is MIT licensed. The full upstream repository is not vendored into YACS.

The bridge deployed by `ue-mcp init` is treated as reproducible local development tooling during the spike and is ignored by Git. If later validation shows setup-time deployment is insufficient, vendoring can be reconsidered separately.

## 4.1. UE 5.8 native tooling strategy

UE 5.8 also ships an experimental official Unreal MCP implementation whose engine identifier is `ModelContextProtocol`. Its toolsets are exposed through Unreal's Toolset Registry; the experimental `PCGToolset` can create and modify PCG Graphs.

For YACS this is treated as an **engine capability**, not as a second orchestration stack:

```text
Kilo / agent
    |
    v
db-lyon ue-mcp
    |
    +--> YACS guards / flows / rollback
    |
    +--> stock ue-mcp handlers
    |
    +--> UE 5.8 Toolset Registry / selected native toolsets
              |
              +--> PCGToolset (after smoke validation)
```

Initial rule:

- do not run db-lyon and the official Unreal MCP as two independent agent-facing servers at the same time;
- keep db-lyon as the single YACS orchestration/safety surface;
- keep `nativeTools.enabled: false` during Phase A;
- after Phase A, enable only selected native toolsets when they solve a concrete gap;
- `PCGToolset` is the first candidate because it directly supports graph authoring;
- experimental native toolsets remain development-time tooling and require revalidation after UE upgrades.

Detailed plugin schedule: [`UNREAL_TOOLING_PLUGIN_PLAN.md`](UNREAL_TOOLING_PLUGIN_PLAN.md).

## 5. Initial MCP surface

The tracked `ue-mcp.yml` exposes only:

- `level`;
- `asset`;
- `editor`.

Everything else is disabled initially, including project/source mutation, Blueprints, PCG, landscape, foliage, materials, demo and Epic native-tool routing.

`nativeTools.enabled` is false and context strategy is `lean`.

## 6. Initial guard policy

`YacsStage3GGuard` applies to all editor mutations during the spike.

Allowed mutations are limited to:

- spawning transient verification actors with labels starting `YACS_MCP_`;
- destroying UE-MCP transient verification actors;
- proof screenshots under `Saved/`;
- a small set of transient viewport controls.

Everything else is denied. The connected agent can inspect the project and prove editor control, but it cannot persistently place actors, modify the route, create assets or save the map.

## 7. WorldSpec

A `WorldSpec` is deterministic text input describing environment intent rather than Unreal implementation details.

Initial spec:

```text
worldgen/specs/stage3g_alpine_reference.worldspec.yml
```

It records route/map identity, seed, biome ranges, proof distances, generated-content root and protected boundaries.

The same spec + approved asset set + generator version should produce equivalent placement.

## 8. Phased implementation

### Phase A — safe connection spike

1. Install pinned UE-MCP locally.
2. Deploy the bridge on the home PC.
3. Build it with UE 5.8.2.
4. Run `ue-mcp doctor`.
5. Open `L_CyclingTest` manually and make sure there is no unsaved editor work that should be preserved.
6. Run `yacs_stage3g_inspect` and confirm it reports the expected map.
7. Run `yacs_stage3g_transient_smoke`; the flow deliberately does not load or save a map.
8. Verify no persistent map/content change remains.
9. Re-run Stage 3 Automation/proof.

No persistent world generation is enabled in Phase A.

### Phase B — generated-content sandbox

After Phase A is green:

1. add a generated-content write guard for `/Game/Generated/YACS/**`;
2. keep route/core/prototype inputs protected;
3. enable only the additional categories required by 3G: `material`, `landscape`, `pcg`, `foliage`;
4. enable the native UE **PCG** plugin and **Editor Scripting Utilities**;
5. enable **Geometry Script**; add **PCG Geometry Script Interop** only when a graph needs mesh interop;
6. evaluate **PCGToolset** only after the stock PCG bridge path is proven;
7. add deterministic cleanup/regeneration;
8. enable git snapshot around persistent generation flows.

### Phase C — Stage 3G generator flows

Prefer focused YACS flows:

- `yacs.inspect_route`;
- `yacs.generate_valley_baseline`;
- `yacs.generate_forest_baseline`;
- `yacs.generate_high_alpine_baseline`;
- `yacs.populate_roadside`;
- `yacs.capture_stage3g_proof`;
- `yacs.clean_generated_world`;
- `yacs.regenerate_world`.

Stock UE-MCP actions remain the execution substrate.

### Phase D — thin YACS extension only if justified

Create `ue-mcp-yacs` only when repeated flows reveal a real abstraction gap, for example route-distance-aware placement, route-clearance validation or proof manifests tied to WorldSpec seed.

Do not create a custom MCP layer merely to rename stock UE-MCP actions.

## 9. Proof and validation

Reuse Stage 3 proof points:

- 1200 m — valley/meadow;
- 4900 m — forest;
- 8000 m — high Alpine.

Persistent generation must eventually prove deterministic seed behavior, no route/simulation regressions, editor build, relevant Automation, map save/reopen, Map Check, LFS/fresh checkout where needed, comparable BEFORE/AFTER screenshots and 1080p performance sanity on RTX 2070 Super.

## 10. Home/office split

Office/lightweight work may edit docs, WorldSpecs, flow definitions, guards and setup scripts.

The home/reference PC owns bridge deployment, UE 5.8.2 compilation, editor connection proof, runtime/editor proof, screenshot validation and performance sanity.

Per `AGENTS.md`, an Unreal integration checkpoint may be pushed, but an implementation PR is not opened until required home-PC validation is green.

## 11. Kilo usage

Kilo should connect to YACS UE-MCP as an additional controlled tool source. It does not replace the existing Kilo responsibilities for code, Git, build logs and tests.

For routine world generation, prefer named YACS flows over free-form chains of low-level actions.

## 12. Non-goals

This integration does not change physics ownership, Stage 3 route geometry ownership, begin Stage 4 mechanics, turn 3G into final Stage 7 art, authorize broad autonomous writes, authorize arbitrary Python/console execution or require a backend service.
