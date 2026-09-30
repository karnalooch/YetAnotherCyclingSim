# YACS UE-MCP world-generation architecture

**Status:** M3 world/asset recovery active; legacy Stage 3G asset/flow identifiers are retained for traceability, while persistent **agent-driven MCP** worldgen still requires its own guarded proof before adoption
**Tracking:** #85
**Initial upstream:** `db-lyon/ue-mcp`
**Reviewed pin:** `v1.3.9`
**Unreal target:** UE 5.8.2 on the home/reference PC

## 1. Purpose

YACS uses UE-MCP as a **development-time Unreal Editor execution layer** for bounded M3 world authoring and validation.

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

**Recovery note (28.09.2026):** PR #155 proved the Stage 3G CI/authoring harness and PR #162 is merged, providing the first real conifer baseline plus persisted `PCG_RouteExclusion` and `PCG_Forest` assets. Issue #230 now builds the YACS World Authoring Library above those assets: semantic presets, approved-provider discovery/acquisition, deterministic layout and a guarded Scene Composer. This does **not** mean persistent MCP-driven generation is already approved. #85 remains the controlled agent-orchestration track.

## 3. Why UE-MCP

The selected upstream already provides the Unreal Editor bridge, MCP categories for world authoring, YAML flows, retries/rollback, git snapshots, configurable guards and context strategies. We reuse those capabilities rather than creating a second editor automation framework.

UE-MCP is an **optional controlled execution/orchestration surface**, not the only legal way to author PCG. Deterministic project-owned C++/Python/editor workflows may create and validate the same technical assets when they are easier to test and review. The invariant is shared: route authority, deterministic inputs, generated-content boundaries, proof and rollback remain the same regardless of which editor automation surface performs the mutation.

## 4. Dependency policy

The toolchain pins `ue-mcp` **1.3.9** and records upstream commit `d79a34bb6e7a5883457efe8f33c9f85b1ba3e136`. Do not float `latest`. The complete npm dependency graph is committed in `tools/ue-mcp/package-lock.json`, and setup must use `npm ci --ignore-scripts`. Upgrades require provenance review, lock refresh and integration proof because UE-MCP has direct write access to the editor project.

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

## 4.2. Embark-first read/write tooling boundary

World-authoring automation follows the repository-wide Embark-first tooling
policy, but separates **project knowledge** from **project mutation**.

The preferred architecture is:

```text
                 +--> Embark-style project index/search
agent / Kilo ----+        READ / DISCOVER
                 |
                 +--> guarded YACS execution surface
                          INSPECT / MUTATE / PROVE
                               |
                               v
                    Unreal Editor / PCG / Geometry Script
```

The public Embark `UnrealClaudeFileHelper` project
(`embark-claude-index`) is a strong reference for the read side: indexing
Unreal code/assets so an agent can discover the project quickly instead of
scanning it ad hoc. It is **not** permission to let an index service mutate
Unreal content, and its source must not be copied into YACS until provenance
and license-artifact review explicitly permits that.

Embark SkyHook is the corresponding DCC-integration reference: keep transport
and commands small, explicit and tool-oriented instead of creating a giant
general-purpose remote-control API.

For the mutation side, the existing YACS guards, generated-content boundaries,
rollback and proof rules remain authoritative regardless of whether the eventual
executor is db-lyon `ue-mcp`, selected UE-native Toolset Registry capabilities,
or a later bounded replacement. Any attempt to replace the current executor
must prove parity for guards, rollback, deterministic flows and exact-SHA proof
before the old path is removed.

Public Embark repositories are architecture references unless explicitly
adopted through provenance. They must not be represented as the complete
internal ARC Raiders authoring stack.

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

This phase applies to **persistent mutations performed through the MCP/agent surface**. It does not forbid separately reviewed deterministic editor scripts/workflows such as the in-flight #162 PCG authoring path.

After Phase A is green:

1. add a generated-content write guard for `/Game/Generated/YACS/**`;
2. keep route/core/prototype inputs protected;
3. enable only the additional categories required by 3G: `material`, `landscape`, `pcg`, `foliage`;
4. enable the native UE **PCG** plugin and **Editor Scripting Utilities**;
5. enable **Geometry Script**; add **PCG Geometry Script Interop** only when a graph needs mesh interop;
6. evaluate **PCGToolset** only after the stock PCG bridge path is proven;
7. add deterministic cleanup/regeneration;
8. enable git snapshot around persistent generation flows.

### Phase C — M3 generator flows (legacy command names retained)

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

This integration does not change physics ownership, Stage 3 route geometry ownership, begin Stage 4 mechanics, turn 3G into final Stage 7 art, authorize broad autonomous writes, authorize arbitrary Python/console execution, require a backend service, or monopolize world authoring by forcing all PCG creation through MCP.

## 13. Remote GitHub runner transport

Issue #228, under the broader #85 architecture track, owns the controlled
chat-to-runner transport spike documented in
[`YACS_REMOTE_EDITOR_AGENT.md`](YACS_REMOTE_EDITOR_AGENT.md).

The transport is deliberately separated from the agent-facing MCP surface:

```text
ChatGPT / repository owner
        |
        | exact allowlisted command
        v
GitHub Issue #228
        |
        v
GitHub Actions
        |
        v
[self-hosted, yacs-ue58]
        |
        v
repository-owned allowlist wrapper
        |
        v
UnrealEditor-Cmd.exe + fixed Unreal Python
        |
        v
proof JSON + Unreal log artifact
```

The transport does **not** expose UE-MCP to the network. GitHub Actions remains
the only remote control plane; the trusted `yacs-ue58` host executes
repository-owned allowlisted commands locally.

The initial command is exactly:

```text
/yacs-editor smoke-cube
```

Its behavior is intentionally non-persistent:

- only the repository owner may trigger it;
- only Issue #228 is accepted;
- comment text is compared to one exact literal and is never interpolated into
  PowerShell, Python or Unreal arguments;
- the PowerShell wrapper exposes a fixed `ValidateSet`;
- the Unreal script spawns `YACS_REMOTE_SMOKE_CUBE` with `transient=true`;
- the actor is destroyed before exit;
- no level is saved and no persistent asset is created;
- repository permissions remain read-only;
- the worktree must be clean before/after execution and is cleaned unconditionally.

The branch-only owner push canary exists only to prove the bridge before the
`issue_comment` workflow lands on `main`. It must not be broadened to forks or
pull-request-controlled execution.

This transport is complementary to the existing MCP architecture. Later named
commands may call guarded YACS MCP flows on localhost only after their own
write-boundary and proof gates are green. Persistent editor/MCP mutations still
require the Phase B `/Game/Generated/YACS/**` sandbox, rollback/proof rules and
an explicit work item.

The first proven headless transport command is not visual acceptance. A later
interactive/GPU proof must separately demonstrate visual capture before remote
world-art authoring is claimed to work.

## 14. World Authoring Library intent layer

Issue #230 introduces the repo-owned semantic layer documented in
[`YACS_WORLD_AUTHORING_LIBRARY.md`](YACS_WORLD_AUTHORING_LIBRARY.md).

The library sits **above** the transport/MCP surface and **above** raw provider
APIs:

```text
natural-language request
        -> repo-owned intent preset
        -> semantic asset selection / approved acquisition
        -> deterministic Scene Composer
        -> existing YACS PCG graphs or transient proof backend
        -> screenshot/proof
```

The agent never passes arbitrary Python, shell, asset URLs or Unreal paths
through this interface. Automatic provider discovery is candidate discovery;
only qualified catalog assets may be used by the first visual composer.

The initial #230 proof remains transient. Persistent output keeps the existing
Phase B requirement: writes only under `/Game/Generated/YACS/**`, with
rollback/proof and separate acceptance.
