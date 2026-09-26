# YetAnotherCyclingSim — Unreal tooling & plugin plan

**Status:** active production plan  
**Applies to:** UE 5.8.2 MVP roadmap  
**Rule:** no plugin is enabled “just in case”.

## 1. Purpose

This document is the source of truth for Unreal Engine plugins and editor tooling that YACS intends to introduce during the MVP.

It exists so that required tooling is not forgotten, but also so that the project does not accumulate dozens of unnecessary plugins.

Every planned plugin must answer:

1. Which roadmap stage needs it?
2. What concrete YACS problem does it solve?
3. Is it runtime, editor-only, Beta or Experimental?
4. What new build/performance/stability risk does it introduce?
5. What proof is required before we depend on it?

A plugin being bundled with Unreal Engine does not automatically make it part of YACS.

Enabling a tool is not considered complete by itself. If the tool produces persistent project content, the expected **technical UE assets** must be defined in [`ASSET_PLAN.md`](ASSET_PLAN.md), tracked in the Technical UE Asset Ledger, reviewed like code/configuration, and validated before the roadmap gate is complete.

## 2. Current explicit project state

At the start of the Stage 3G MCP spike, `YetAnotherCyclingSim.uproject` explicitly enables:

- **Modeling Tools Editor Mode**;
- **Python Editor Script Plugin** (`PythonScriptPlugin`).

The project also uses Enhanced Input in C++, but this document focuses on plugin/tooling decisions rather than every engine module dependency.

Any change to the explicit plugin list is an integration change and requires an Unreal editor build plus relevant Automation/proof on the home/reference PC.

## 3. Stage-by-stage plan

| Stage | Tool / plugin | Priority | Why YACS needs it | Activation policy |
|---|---|---:|---|---|
| **3G** | **PCG** | MUST | deterministic vegetation, rocks, biome/set dressing and roadside generation | enable after #85 Phase A smoke setup is ready; first proof on one sector |
| **3G** | **Editor Scripting Utilities** | MUST | safer/simpler editor automation APIs complementing PythonScriptPlugin | enable with first PCG integration |
| **3G** | **Geometry Script** | SHOULD | generate/analyze/edit helper geometry, mesh processing and custom world-authoring tools | enable with PCG integration; do not make route physics depend on it |
| **3G** | **PCG Geometry Script Interop** | CONDITIONAL | PCG ↔ Dynamic/Static Mesh operations and mesh sampling when a graph actually requires them | enable only on demonstrated graph need |
| **3G** | **PCGToolset** | EXPERIMENT | agent-driven creation/modification of PCG Graphs through UE 5.8 Toolset Registry | only after MCP smoke; keep behind YACS guard/flow surface |
| **3G/7** | **Water + Landmass** | OPTIONAL | lake/river/terrain shaping if water survives art-direction review | leave disabled until composition decision |
| **6** | **Control Rig** | MUST | procedural cycling posture and in-engine rig control | enable at Stage 6 start |
| **6** | **IK Rig** | MUST | mocap retargeting, IK goals and retarget chains | enable at Stage 6 start |
| **6** | **FullBodyIK** | MUST | simultaneous hand/pedal/body constraints and procedural pose adjustment | enable with Control Rig proof |
| **6** | **Skeletal Mesh Editing Tools** | OPTIONAL | small mesh/skinning fixes in UE without external round-trip | evaluate only after rider import pain is measured |
| **6** | **Control Rig Modules** | OPTIONAL/BETA | reusable modular rig blocks | evaluate after minimal YACS Control Rig works |
| **7** | **Scriptable Tools Editor Mode** | OPTIONAL | custom “Generate YACS World” editor mode/UI if flows become cumbersome | add only if it clearly beats MCP flows/Editor Utility workflows |
| **8** | **Niagara** | MUST | rain, wheel spray, debris/leaves and atmospheric VFX | enable/verify when weather implementation begins |
| **8** | **MetaSounds** | SHOULD | parameter-driven drivetrain/freehub/tyres/brakes/wind audio | enable/verify when production audio starts |
| **3G+ dev tooling** | **db-lyon ue-mcp** | MUST for current workflow | single orchestration layer for Kilo: flows, guards, rollback, editor actions and proof | pinned release; upgrade only after review |
| **3G+ dev tooling** | **UE ModelContextProtocol / Toolset Registry** | SELECTIVE/EXPERIMENTAL | official UE 5.8 AI-callable toolsets such as PCGToolset | consume selectively through the chosen orchestration path, not as a second uncontrolled server |

## 4. Stage 3G world-generation stack

Target:

```text
WorldSpec + authoritative route geometry
                 |
                 v
             YACS flows
                 |
                 v
            db-lyon ue-mcp
                 |
       +---------+----------+
       |         |          |
       v         v          v
      PCG   Geometry Script editor APIs
       |         |          |
       +---- generated presentation ----+
                 |
                 v
        /Game/Generated/YACS/**
```

PCG is a **consumer** of the YACS route, never its owner.

Allowed PCG inputs can include:

- route spline as spatial reference;
- route-distance biome ranges from WorldSpec;
- altitude;
- slope;
- lateral distance from road;
- exclusion corridors;
- approved asset sets;
- deterministic seed.

PCG must not redefine:

- route length;
- route profile;
- route centreline;
- fixed-step grade;
- authoritative route progress;
- cornering physics.

### First PCG proof

The first proof is deliberately small:

1. one Stage 3G sector;
2. one deterministic seed;
3. a small approved asset set;
4. road exclusion corridor;
5. generated rocks/vegetation only;
6. cleanup/regenerate;
7. same seed -> equivalent placement;
8. screenshot + basic performance sanity.

No Runtime PCG is required for the MVP proof. Prefer editor-time generation first.

## 5. Geometry Script policy

Geometry Script is useful for helper geometry and tooling, for example:

- cliff/rock helper generation;
- retaining-wall prototypes;
- mesh sampling/analysis;
- asset cleanup;
- dynamic helper meshes;
- custom editor tools.

It is Beta in UE 5.8. Therefore:

- it must not own authoritative cycling physics;
- it must not become the only representation of route geometry;
- generated results used persistently must have deterministic/reproducible inputs;
- any shipping/runtime dependency must be justified separately from editor tooling.

## 6. MCP strategy

UE 5.8 includes the experimental **Unreal MCP** plugin (`ModelContextProtocol`) and Toolset Registry. PCGToolset is an experimental official toolset specifically for building and modifying PCG Graphs.

YACS does **not** initially expose two independent MCP servers to the agent.

Preferred stack:

```text
Kilo
 |
 v
db-lyon ue-mcp
 |-- YACS guards
 |-- YACS named flows
 |-- rollback / proof capture
 |
 +--> UE Editor bridge
       |
       +--> stock editor APIs
       +--> selected UE 5.8 Toolset Registry capabilities
```

Rules:

- db-lyon stays the initial orchestration and safety boundary;
- `nativeTools.enabled` stays off during #85 Phase A;
- enable only selected native toolsets after their need is demonstrated;
- PCGToolset is the first planned native-tool experiment;
- arbitrary Python/console escape hatches remain blocked in the initial worldgen surface;
- revalidate Experimental toolsets after engine upgrades.

## 7. Stage 6 rider stack

Target presentation pipeline:

```text
cycling mocap / base animation
          |
          v
       IK Rig
          |
          v
    retargeted pose
          |
          v
     Control Rig
          |
          +--> FullBodyIK
          +--> hand goals -> handlebar
          +--> foot goals -> pedals
          +--> pelvis/spine/head procedural offsets
          |
          v
      final rider pose
```

Required principles:

- bike/rider animation consumes physics state but never feeds pose output back into physics;
- hand and foot contact must survive cadence/posture transitions;
- corner lean/tuck/standing are parameterized presentation;
- cost of Control Rig + IK/FBIK must be profiled on RTX 2070 Super reference hardware.

Optional tools are added only if they remove measured production friction.

## 8. Stage 7 editor-tool policy

Do not build a custom editor application too early.

Start with:

1. WorldSpec;
2. named UE-MCP flows;
3. PCG graphs;
4. Editor Utility/Python where appropriate.

Only if this becomes cumbersome should Stage 7 introduce **Scriptable Tools Editor Mode** for a dedicated YACS world-authoring interface.

A future custom UI may expose actions such as:

- Generate World;
- Regenerate Sector;
- Clean Generated World;
- Preview Seed;
- Capture Proof;
- Validate Route Clearance.

The UI must call the same underlying deterministic generator contract as automation; it must not create a separate manual-only path.

## 9. Stage 8 VFX and audio

### Niagara

Use Niagara for effects whose behavior is genuinely particle/VFX driven:

- rain;
- wheel spray;
- wind-driven leaves/debris;
- dust/pollen/insects where justified;
- localized mist/detail VFX.

Keep VFX density/scalability measurable and configurable.

### MetaSounds

Prefer MetaSounds for parameter-driven cycling audio where it reduces sample explosion and improves continuity.

Candidate inputs:

- speed;
- cadence;
- power;
- coasting state;
- braking;
- surface;
- wetness;
- wind speed/direction.

Candidate outputs:

- drivetrain;
- freehub;
- tyre noise;
- brake detail;
- wind layers.

Do not use the experimental MetaSounds feature plugin merely because it exists; baseline MetaSound functionality is the default.

## 10. Optional Water / Landmass

Water is not a mandatory world subsystem.

Enable Water/Landmass only if the accepted Stage 3G/7 composition includes a lake/river and the visual gain justifies:

- plugin dependencies;
- material/render cost;
- world-generation complexity;
- proof burden.

A simple non-system water solution is allowed if it is sufficient for the single MVP route.

## 11. Plugin admission checklist

Before adding a new plugin to `.uproject`:

- [ ] concrete roadmap task exists;
- [ ] plugin solves a named problem better than existing tools;
- [ ] Beta/Experimental status is recorded;
- [ ] runtime vs editor-only scope is understood;
- [ ] dependencies are understood;
- [ ] build succeeds on UE 5.8.2;
- [ ] relevant Automation/proof stays green;
- [ ] no unintended package/cook dependency is introduced;
- [ ] performance impact is measured when runtime-facing;
- [ ] rollback/removal path is known.
- [ ] expected technical UE assets are named and assigned to a roadmap stage;
- [ ] authoring assets and generated outputs have separate, documented content roots;
- [ ] technical assets have a proof requirement in the Technical UE Asset Ledger.

## 12. Deferred / not planned by default

Do not enable by default:

- large third-party world-generation frameworks;
- runtime procedural-world frameworks for the 10 km MVP route;
- Mass/ECS tooling before post-MVP scaling measurements justify it;
- broad AI/agent toolsets unrelated to the current roadmap stage;
- duplicate MCP orchestration stacks;
- Motion Warping solely for cycling posture when Control Rig/IK solves the actual problem;
- experimental plugin families without a concrete use case.

## 13. Official references

- PCG: https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-framework-in-unreal-engine
- Geometry Script: https://dev.epicgames.com/documentation/unreal-engine/geometry-scripting-users-guide-in-unreal-engine
- PCG Geometry Script Interop: https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/PCGGeometryScriptInterop
- Unreal MCP: https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor
- PCGToolset: https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/PCGToolset
- Control Rig: https://dev.epicgames.com/documentation/unreal-engine/control-rig-in-unreal-engine
- Full Body IK: https://dev.epicgames.com/documentation/unreal-engine/control-rig-full-body-ik-in-unreal-engine
- IK Rig: https://dev.epicgames.com/documentation/unreal-engine/ik-rig-in-unreal-engine
- Scriptable Tools Editor Mode: https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ScriptableToolsEditorMode
- Niagara: https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/Niagara
- MetaSounds: https://dev.epicgames.com/documentation/unreal-engine/metasounds-in-unreal-engine
