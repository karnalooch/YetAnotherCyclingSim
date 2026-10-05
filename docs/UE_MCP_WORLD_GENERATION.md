# YACS UE-MCP world-generation architecture

**Status:** official Epic MCP direction approved; #384 blocked by full #363 closeout, before #364. Planning only; no MCP activation or engine migration.
**Tracking:** #384 adoption; #385 documentation; #85 historical integration
**Retained integration:** `db-lyon/ue-mcp` at reviewed `v1.3.9`; unchanged until proven cutover
**Engine baseline:** project association 5.8; home engine inspected 2026-10-05: 5.8.2, changelist 56702186. Reverify exact project/runner versions at kickoff.

## Official Unreal MCP adoption

### Decision and status

**BLOCKED by #363 — Landscape material foundation. Planning is authorized; implementation is not started.**

The owner approved a small official Unreal MCP adoption workstream between world-finishing step 2 (#363) and step 3 (#364). "Step 2.5" is a shorthand inside **M3**, not a new product milestone or a renumbering of the existing 13 steps.

**Execution order:** #363 full acceptance and protected merge → this bounded spike → #364 asphalt/shoulder → #365 PCG/PCGEx world graph → the unchanged downstream sequence.

Keep the native GitHub `blocked_by` relationship to #363 and `lifecycle:blocked`; the YACS — MVP Project status must remain **Blocked**. #364 keeps its existing #363 dependency and also depends on this spike. Dependencies and board states do not technically prevent PR creation: agents must enforce the gate below.

### Hard entry gate: what “step 2 complete” means

Before implementation, plugin activation, an implementation PR, or promotion to Ready/In progress, record and verify:

- #363 is closed **as completed**, with its implementation merged; closing as not planned, a draft PR or a green build is insufficient.
- Explicit owner visual acceptance covers the entire current 2,016.5 m × 2,016.5 m Sa Calobra Landscape (~4.07 km²), including representative environments/traversal and the additional Golden Kilometer check.
- Saved material/consumer identity and fresh rendered reopening are admitted. NullRHI or a screenshot alone does not establish rendered acceptance.
- Deferred 2A/2B whole-Landscape performance has passed under the existing exact-SHA policy and canonical budgets; `DEFERRED_TO_2B` is not PASS.
- Required build, Automation, asset, review, documentation and protected Aggregate CI gates have passed; the handoff pins outputs, versions/hashes, limitations and proof links.

At creation, #363 is OPEN and its current material remains a visually rejected prototype. No admission is implied here. Re-read its latest evidence at kickoff; do not freeze this checkpoint into future truth.

Documentation/issue planning may be delivered now through a separate documentation issue/PR. That PR must **not** close this adoption issue or move it out of Blocked.

### Why the control plane changes

Epic supplies the engine-facing interface that YACS previously had to assemble around bridges, scripts and editor commands. The target is one official, development-time MCP entrypoint into Unreal, with stock Epic tools for generic operations and thin YACS tools for domain operations. This reduces duplicated integration code and makes editor inspection, test invocation and later authoring discoverable through the same interface.

**MCP is orchestration/interface, never authority.** An LLM tool response does not redefine a road, certify an asset, approve a scene or grant a proof PASS.

| Owner | Responsibility retained |
|---|---|
| Route/physics contracts | Canonical alignment, distance, profile, fixed-step simulation and ride semantics; Actor/Pawn transforms are presentation. |
| World Authority | Admitted GIS/DTM/masks, registration, geographic facts, provenance, unknowns and exclusions. |
| BOB (#303) | Deterministic road/earthworks inspection and domain decisions within its admitted policy; no new construction or verified-case learning authority. |
| Tests, proof producers and governance | Actual assertions, measured evidence, receipts, exact-SHA admission, review and human visual decisions. MCP requests/collects these; it does not replace them. |
| Native PCG / PCGEx | Reconstruction and presentation execution. Native PCG is the foundation; pinned PCGEx extends named spatial/path/filter gaps. Neither owns geography or physics. |


```mermaid
flowchart TB
    AGENT["AGENT<br/>Approved bounded task"] --> MCP["INTERFACE<br/>Official Unreal MCP"]
    MCP --> EPIC["EPIC TOOLS<br/>Scene · objects · tests · PCG"]
    MCP --> DOMAIN["YACS TOOLS<br/>Thin domain operations"]
    DOMAIN --> BOB["AUTHORITY<br/>BOB domain logic"]
    TRUTH["AUTHORITY<br/>World data · route · physics"] --> BOB
    TRUTH --> EXEC["EXECUTE<br/>Admitted presentation rules"]
    EPIC --> EXEC
    BOB --> EXEC
    EXEC --> PROOF["EVIDENCE<br/>Tests · results · receipts"]
    PROOF --> GATE["ADMISSION<br/>CI · review · visual decision"]
    GATE -.-> AGENT

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;
    class AGENT input;
    class MCP,EPIC,DOMAIN tool;
    class BOB,TRUTH owned;
    class EXEC exec;
    class PROOF evidence;
    class GATE decision;
    linkStyle default stroke-width:2px;
```

This is the future admitted architecture, not an implementation/proof claim.
The initial spike uses read-only inspection/test operations, not the diagram's
later world-generation capabilities.

Existing proven PCGEx work stays intact. This is not a road-builder rewrite, a new biome engine or a month-long automation platform.

### Official capabilities to reuse

Epic documentation checked on **2026-10-05**:

- **Unreal MCP** (`ModelContextProtocol`) with **All Toolsets / Toolset Registry**; select only the toolsets needed for the admitted task.
- **SceneTools / ActorTools / ObjectTools** for scene and object inspection; **MaterialInstanceTools** for later #364 material work.
- **AutomationTestToolset** for discovery, execution, status and results using the Session Frontend automation backend.
- **PCGToolset** for later graph work; load **Skill_PCGGraphGeneration** before PCG tasks, inspect existing PCG examples and reuse suitable graphs.
- The **shape grammar definition skill**, PCG Primitives and City Sample PCG patterns are candidates for #377; verify the exact installed skill identifier instead of inventing one.
- **Semantic Search** is documented for UE 5.8+ asset discovery. It does not replace Julka approval/provenance. Integrated Terminal is optional convenience.

These are an adoption map, **not a requirement to enable or prove every capability in this spike**. PCG generation, buildings, profiling and asset indexing remain separate work. Epic marks Unreal MCP/PCG tooling Experimental: version-match primary docs and verify the exact installed schemas.

### Current baseline and transition

At main commit `83b5281`, `YetAnotherCyclingSim.uproject` already uses `EngineAssociation: 5.8`. The inspected home engine reports **5.8.2, changelist 56702186**. Reverify the project/runner engine and plugin revisions at kickoff. This decision does not authorize an engine migration.

#85 concerns the older `db-lyon/ue-mcp` integration and is closed. Its code, reviewed `1.3.9` pin, guard configuration and evidence remain unchanged; its closure does not prove the official server works. The older “db-lyon remains the single orchestration surface” target is superseded by this owner decision **for the future admitted path**, not retroactively rewritten as an executed migration.

Do not run two independent agent-facing mutation servers. Before cutover, prove the old safety invariants on the official path. Native MCP must not be assumed to inherit `YacsStage3GGuard`. If the necessary restriction cannot be established with bounded existing mechanisms, stop with a gap report; do not compensate by building a generic gateway.

### Bounded spike

**Scope cap:** one approved local editor/client session, one admitted map, one Actor/UObject inspection, one existing small relevant Automation Test, one real read-only BOB operation and one evidence bundle. No new service, generic transport, universal tool framework or full suite of YACS toolsets.

1. Verify the entry gate and pin the accepted map, source inputs, repository SHA, engine/plugin versions and relevant BOB policy.
2. Discover the official server and actual tool schemas. Preserve the owner’s live/unsaved editor work. Use a local endpoint and serial calls.
3. Read the current map/scene identity and a stable Actor/UObject path/class/property; compare them with the admitted checkpoint.
4. Discover and run one existing relevant YACS Automation Test through `AutomationTestToolset`. Record the exact test name, final result and log/report; zero tests, timeout, unavailable workers or missing results fail the spike.
5. Expose only one thin YACS-domain operation, for example a proposed `bob.inspect_contact`. That is a candidate interface name, **not a claimed existing API**. Inspect the current implementation and delegate to the real BOB inspector (existing references include `scripts/worldgen/adaptive_terrain_solver.py::review_pavement_contact_trial` and `scripts/worldgen/bob_terrain_fit_inspector.py::inspect_terrain_fit`). Do not reimplement its calculations in MCP or fabricate a success-shaped response.
6. Return the actual BOB assessment, proof references and a structured receipt. Compare with direct execution on the same pinned inputs and record repeatability. `REJECT_CONTACT`, `REVIEW_PENDING` or `INSPECTOR_ONLY` must retain their meaning; successful orchestration is not road acceptance.
7. Verify the restricted surface and unchanged persistent content. Unsupported operations, paths outside scope, absent/stale evidence and denied mutations fail closed.
8. Record the bounded outcome and the handoff to #364. After success, **STOP infrastructure work and return to asphalt/shoulder**. If a capability is absent or unsafe, stop with an explicit blocker; retain the prior guarded workflow without silently treating the new gate as passed.

The receipt should bind repository SHA, actual UE/plugin versions, map/object identity, tool calls/arguments, input hashes, BOB policy/version, Automation test/run/status, domain result, artifact paths/hashes, timestamp and mutation scope. Reuse current proof/receipt conventions. A log claiming success without the referenced evidence is insufficient.

### Safety and preserved governance

- Prove a narrow read/inspect/test surface. Loading All Toolsets is not blanket authorization for every registered operation.
- Keep the server local; no public/remote exposure, new authentication service or arbitrary caller-supplied Python/shell/console/CVAR execution.
- Frozen terrain/road geometry, canonical route/core assets and World Authority remain protected. This spike performs no persistent world mutation.
- Later separately admitted persistent outputs remain under `/Game/Generated/YACS/**`; preserve snapshots/rollback, deterministic seeds and reproducibility.
- Keep exact-SHA evidence, compile-reuse rules, trusted Proof Broker intent, current performance budgets, serial heavy jobs and isolated CI. A warm editor test is not a substitute for required cold/fresh-load proof.
- Preserve normal provenance, build/Automation/asset, documentation, review and Aggregate gates. No changes to branch protection, required checks or proof policy.
- From **step 3 onward**, do not create custom generic Unreal-control workarounds when official Epic MCP supports the case within YACS safety constraints. YACS toolsets contain only YACS domain knowledge/contracts. Existing deterministic producers, CI commandlets and proof collectors keep their jobs; no wholesale rewrite.
- Any genuinely unsupported case needs primary-source evidence and a bounded, reviewed decision. Do not silently use a new generic bridge as fallback.

### Definition of Done

- [ ] #363 entry gate is verified with completed state, merged implementation and linked visual/render/performance/technical evidence.
- [ ] Exact environment, one map and the permitted official tool surface are pinned.
- [ ] Agent sees the admitted map/scene through official Unreal MCP.
- [ ] Agent reads an actual Actor/UObject and verifies its identity.
- [ ] One existing relevant Automation Test completes through the official toolset, with real results/logs.
- [ ] One real BOB inspector executes through a thin domain tool and matches the direct invocation on identical inputs.
- [ ] Result + proof + receipt are retrievable, hash/identity-bound and explicit about domain FAIL/review states.
- [ ] Fail-closed behavior and absence of unauthorized persistent/authority changes are verified; guard parity is proven before any cutover.
- [ ] Required integration/build/Automation, documentation, protected CI and review gates pass for the candidate; implementation is merged.
- [ ] #364 receives the admitted interface, environment, evidence and limits. Optional #376/#377/#365 work remains deferred. **STOP infrastructure expansion.**

A documentation merge, plugin enablement, connection handshake, mock BOB result or list of tool names alone cannot close this issue.

### Related work

- #363 — sole immediate prerequisite: full Landscape material closeout.
- #85 — historical controlled MCP integration and safety baseline.
- #303 — BOB authority and verified-case boundaries.
- #364 — next delivery: asphalt/shoulder, first real consumer after this spike.
- #365 — later native-PCG foundation plus PCGEx extensions; preserve its #364 gate.
- #376 — bounded performance toolset; optional follow-up, not spike scope.
- #377 — source-faithful procedural buildings; optional follow-up, not spike scope.

### Agent starting context and sources

Start with [the documentation index](README.md), [Roadmap](ROADMAP.md), [World Building Bible](WORLD_BUILDING_BIBLE.md), [plugin plan](UNREAL_TOOLING_PLUGIN_PLAN.md), [CI Validation Tiers](CI_VALIDATION_TIERS.md) and canonical [performance framework](performance/PERFORMANCE_FRAMEWORK.md)/[budgets](performance/BUDGETS.md). Issue #384 is the execution checklist; #385 delivers this planning record without activating MCP.

Primary Epic references:

- [Unreal MCP](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor)
- [AutomationTestToolset](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/AutomationTestToolset/UAutomationTestToolset)
- [PCGToolset](https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/PCGToolset)
- [PCG and LLM workflow / Skill_PCGGraphGeneration / Semantic Search](https://dev.epicgames.com/documentation/unreal-engine/working-with-pcg-and-llms-using-unreal-mcp-in-unreal-engine)
- [City Sample PCG and MCP / shape grammar skill](https://dev.epicgames.com/documentation/unreal-engine/city-sample-pcg-and-mcp-server-interaction-in-unreal-engine)

## Retained integration baseline and operating history

The numbered sections below describe the existing db-lyon integration and its
historical phases, plus independently admitted local/remote workflows. They are
not permission to execute those phases now or an alternative roadmap to #384.
The decision above governs future MCP adoption; the Bible, Roadmap and AGENTS
remain authoritative for methodology, delivery and admission.

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

## Live local editor review

Owner decision, 2026-10-04 (Issue #335): work through both reproducible preparation
scripts and the already open Unreal Editor. The installed Windows Computer Use
plugin was verified for window discovery, activation, observation and closing an
obscuring Content Browser panel. This establishes local UI access only; it does
not establish PCGEx execution, controller support or persistent authoring admission.

The working loop is:

1. Prepare and verify source/derived data with existing repository tools; keep
   raw and generated payloads in their contracted cache and record Julka identity.
2. Read the installed Computer Use skill, discover its runtime and select the
   actual returned Unreal window. Check the current map, dialogs and unsaved state.
3. Explain the next meaningful action briefly in Polish. Observe, act once and
   refresh; use live navigation to inspect masks, source disagreements and close
   views together with the owner. Reobserve after owner interaction or focus changes.
4. Record findings and the scope of owner acceptance. Move repeatable production
   steps into tested repository scripts, then collect required exact-SHA proof.

Prefer the existing editor session; preserve unsaved user work and do not close
or restart the editor merely to regain control. Check a separate desktop plugin
before interpreting browser-only limitations as absence of Windows access. If
control fails, report the operation/error and use an authorized supported fallback.
Follow the plugin's safety/confirmation requirements; never use UI control to
bypass a blocked action or execute terminal commands through desktop controls.

The mask reviewer must reuse the expected map already open in the editor. It
must not call `load_map` to reopen its saved baseline: the accepted road,
earthworks and supports can exist only as transient session objects and are not
present in the saved baseline. A different or missing current map is an error,
not permission to replace the owner's world. Road restoration was explicitly
authorized on 2026-10-04; it replayed fixed CUT files and existing support recipes
without saving the map. This does not admit fresh road/earthworks authoring.

For #335, the preview remains session-only: no Save/Save All, terrain sculpting,
heightmap import, road movement or earthworks generation. Masks fit the frozen
Landscape/road contract. Sky and diagnostic overlays are review aids. Live review
does not replace provenance, determinism, CI, trusted performance or human visual
acceptance. This local workflow does not extend the remote #228 command allowlist
or the MCP spike's persistent-write boundary.

Owner exception, later on 2026-10-04: persist the accepted scene and consolidate
local work under `D:\yacs`. The explicit checkpoint operation may save the
existing fixed geometry, CUT assets and diagnostic materials. Ordinary mask
review remains no-save. Follow [the persistent workspace workflow](tooling/LOCAL_WORKSPACE.md)
and verify saved state by reopening; never treat transient actors as a backup.

For the unresolved #335 stream candidates, prepare the hash-pinned queue using
`scripts/assets/prepare_sa_calobra_mask_review_queue.py --transition-manifest
<transition-manifest.json> --pcg-manifest <pcg-mask-manifest.json> --output
<external-cache>/mask-review-queue.json`. Its `focus_world_xy_cm` locates each
gap for closer inspection in the existing session; it deliberately supplies no
invented elevation or automatic repair. Use a separately verified terrain height
when setting a 3D camera. Conservative overlaps are review hints, not culvert
proof. Julka profile `sa-calobra-mask-review-queue-candidate` retains the queue
and full transition parent closure. Owner acceptance remains pending.

## 3. Why UE-MCP

The selected upstream already provides the Unreal Editor bridge, MCP categories for world authoring, YAML flows, retries/rollback, git snapshots, configurable guards and context strategies. We reuse those capabilities rather than creating a second editor automation framework.

UE-MCP is an **optional controlled execution/orchestration surface**, not the only legal way to author PCG. Deterministic project-owned C++/Python/editor workflows may create and validate the same technical assets when they are easier to test and review. The invariant is shared: route authority, deterministic inputs, generated-content boundaries, proof and rollback remain the same regardless of which editor automation surface performs the mutation.

## 4. Dependency policy

The toolchain pins `ue-mcp` **1.3.9** and records upstream commit `d79a34bb6e7a5883457efe8f33c9f85b1ba3e136`. Do not float `latest`. The npm graph is committed in `tools/ue-mcp/package-lock.json`, and setup must use `npm ci --ignore-scripts`. YACS additionally pins the transitive `fast-uri` security override to **3.1.8**: the upstream 1.3.9 graph resolved 3.1.6 (blocked by the HIGH-severity Dependency Review gate), and 3.1.7 remains affected by GHSA-hrr3-gc8f-f4qj. The 3.1.8 update is verified with encoded-host normalization and Hono request regression checks; it does not change the UE-MCP bridge or editor API. Upgrades require provenance review, lock refresh and integration proof because UE-MCP has direct write access to the editor project.

The upstream repository is MIT licensed. The full upstream repository is not vendored into YACS.

The bridge deployed by `ue-mcp init` is treated as reproducible local development tooling during the spike and is ignored by Git. If later validation shows setup-time deployment is insufficient, vendoring can be reconsidered separately.

## 4.1. UE 5.8 native tooling strategy

The 2026-10-05 [official MCP decision](#official-unreal-mcp-adoption) supersedes
the earlier target of keeping db-lyon as the permanent single orchestration
surface and routing native tools through it. #384 selects the official server
after full #363 closeout and bounded proof. This is not an executed cutover.

Keep the tracked db-lyon configuration, including `nativeTools.enabled: false`,
unchanged until admitted implementation. Do not run two independent agent-facing
mutation servers. Safety/guard parity and exact-SHA evidence remain mandatory;
Experimental tooling must be reverified after version changes. Do not execute
the historical Phase A-D schedule below as an alternative to the #384 gate.

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
