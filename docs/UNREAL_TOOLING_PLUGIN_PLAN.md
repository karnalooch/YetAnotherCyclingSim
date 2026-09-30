# YetAnotherCyclingSim — Unreal tooling & plugin plan

**Status:** active production plan
**Applies to:** UE 5.8.2 MVP roadmap
**Rule:** no plugin is enabled “just in case”.
**Current recovery gate (28.09.2026):** the core Stage 3G PCG assets (`PCG_RouteExclusion`, `PCG_Forest`, `PCG_Valley`, `PCG_HighAlpine`) are validated mainline deliverables, and PR #200 merged the route-aware presentation surface. Post-merge human review rejected R4 as the required visual closeout, so Stage 3G now enters **R4.1 Alpine Visual Recovery** before R5. The recovery keeps native PCG and route/physics separation, and runs a bounded UE Landscape vs deterministic Geometry Script/tiled-terrain vertical-slice comparison before choosing the macro-terrain presentation path.

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
| **3G** | **PCG** | MUST | deterministic vegetation, rocks, biome/set dressing and roadside generation | validated mainline foundation; R4.1 extends composition/roadside usage without changing route ownership |
| **3G** | **Editor Scripting Utilities** | MUST | safer/simpler editor automation APIs complementing PythonScriptPlugin | active authoring dependency for deterministic editor-time world generation and proof workflows |
| **3G/R4.1** | **Geometry Script** | SHOULD | generate/analyze/edit helper geometry, mesh processing and custom world-authoring tools | R4.1 uses it in a bounded continuous/tiled-terrain vertical-slice comparison; keep route physics independent and persist only reproducible results |
| **3G** | **PCG Geometry Script Interop** | CONDITIONAL | PCG ↔ Dynamic/Static Mesh operations and mesh sampling when a graph actually requires them | enable only on demonstrated graph need |
| **3G** | **PCGToolset** | EXPERIMENT | agent-driven creation/modification of PCG Graphs through UE 5.8 Toolset Registry | only after MCP smoke; keep behind YACS guard/flow surface |
| **3G/7** | **Water + Landmass** | OPTIONAL | lake/river/terrain shaping if water survives art-direction review | leave disabled until composition decision |
| **6** | **Control Rig** | MUST | procedural cycling posture and in-engine rig control | enable at Stage 6 start |
| **6** | **IK Rig** | MUST | mocap retargeting, IK goals and retarget chains | enable at Stage 6 start |
| **6** | **FullBodyIK** | MUST | simultaneous hand/pedal/body constraints and procedural pose adjustment | enable with Control Rig proof |
| **6 reference** | **Game Animation Sample 5.8** | REFERENCE | current Epic examples for retargeting, Control Rig, additive Look-At and animation debugging | study/copy patterns selectively; do not migrate the locomotion framework into YACS |
| **6 cameras** | **Gameplay Cameras** | DEFER / EXPERIMENTAL | possible future data-driven camera rigs if the conventional camera stack shows a concrete gap | MVP starts with CameraComponent/SpringArm/PlayerCameraManager; comparative spike only on measured need |
| **6 cameras dev tooling** | **GameplayCameraToolset** | EXPERIMENT / THIRD-PARTY | optional MCP authoring surface for Gameplay Cameras | do not add unless Gameplay Cameras itself passes the separate admission spike |
| **6** | **Skeletal Mesh Editing Tools** | OPTIONAL | small mesh/skinning fixes in UE without external round-trip | evaluate only after rider import pain is measured |
| **6** | **Control Rig Modules** | OPTIONAL/BETA | reusable modular rig blocks | evaluate after minimal YACS Control Rig works |
| **7 reference** | **PCG Biome Core / Sample** | REFERENCE / EXPERIMENTAL | study data-driven biome composition for valley/forest/high-Alpine authoring | reference first; production dependency only after a YACS-specific proof |
| **7** | **PCGEx** | CONDITIONAL SPIKE / THIRD-PARTY | candidate for spatial/path/filter operations only if native graphs become materially cumbersome | bounded native-vs-PCGEx comparison on one named problem before dependency admission |
| **7** | **Scriptable Tools Editor Mode** | OPTIONAL | custom “Generate YACS World” editor mode/UI if flows become cumbersome | add only if it clearly beats MCP flows/Editor Utility workflows |
| **8** | **Niagara** | MUST | rain, wheel spray, debris/leaves and atmospheric VFX | enable/verify when weather implementation begins |
| **8** | **MetaSounds** | SHOULD | parameter-driven drivetrain/freehub/tyres/brakes/wind audio | enable/verify when production audio starts |
| **3G+ dev tooling** | **db-lyon ue-mcp** | MUST for planned worldgen workflow | single orchestration layer for Kilo: flows, guards, rollback, editor actions and proof | #85 remains part of Stage 3G recovery; pinned release; upgrade only after review |
| **3G+ dev tooling** | **UE ModelContextProtocol / Toolset Registry** | SELECTIVE/EXPERIMENTAL | official UE 5.8 AI-callable toolsets such as PCGToolset | consume selectively through the chosen orchestration path, not as a second uncontrolled server |

### Embark-first tooling admission rule

Before YACS creates a new Unreal/editor/DCC/agent tool, review the closest
public Embark implementation or published workflow first. The default order is:

```text
Embark tool/pattern -> Epic-native capability -> proven OSS -> custom YACS tool
```

This is deliberately stronger than a generic "build vs buy" check. Embark is
the preferred external architecture reference because its public tooling shows
production-oriented patterns around Unreal, DCC integration, asset search and
automation. It does **not** imply that every public Embark repository is part of
ARC Raiders or that YACS should adopt another runtime/language without need.

Two public Embark references are now explicit:

- **SkyHook** — DCC <-> game-engine communication reference for Blender,
  Houdini, Maya, Substance and Unreal integration. Treat as a reference/candidate
  for transport and command-boundary design, not an automatic dependency.
- **UnrealClaudeFileHelper / `embark-claude-index`** — project index/search
  reference for fast read-side discovery across Unreal code/assets. Treat it as
  a read-only knowledge/index layer pattern, separate from the mutation plane.

YACS should expose high-level domain operations (for example generate a road
corridor, regenerate a world sector, validate clearance, capture proof) rather
than asking an agent to assemble production changes from dozens of low-level
editor calls. Any adopted external implementation still requires provenance,
pinning, rollback and the normal UE proof contract.

### Researched worldgen candidates

These are tracked candidates, **not current dependencies**:

| Tool / project | Planned role | Earliest decision point | Current status |
|---|---|---|---|
| **PCGEx / PCGExtendedToolkit** | advanced PCG spatial/filter/path/asset-staging helpers | after first green stock `PCG_Forest` proof | `spike` |
| **EssentialUE5PCG** | reference patterns for spline-driven forest/rocks/path and dynamic-mesh authoring | Stage 3G implementation | `reference` |
| **PCG Biome Core** | reference architecture for data-driven biome definitions, asset sets, filters, exclusions and blending | Stage 3G-R5 / Stage 7 | `reference/optional-experiment` |
| **Analog Strike** | reference for deterministic offline generation -> UE import/authoring -> capture pipeline | Stage 3G-R5 / Stage 7 | `reference` |
| **RoadForge** | spline-to-road presentation, markings, shoulders and roadside dressing patterns | Stage 7 / post-MVP | `reference-later` |
| **GeoTerrain** | DEM/OSM terrain, slope/altitude materials and foliage-avoidance research | Stage 7 / post-MVP route import | `research-later` |
| **Heightmap Level Generator** | erosion/heightmap/mask R&D only | optional post-MVP terrain experiments | `r&d-only` |
| **Embark SkyHook** | reference/candidate for a small DCC <-> Unreal transport boundary and command model | when Blender/Houdini round-trips become a measured bottleneck | `reference/candidate` |
| **Embark UnrealClaudeFileHelper / embark-claude-index** | read-only project indexing/search pattern for code, assets and agent context | before building any YACS-specific project index | `reference; copy blocked pending license-artifact review` |

Adoption policy:
- run the Embark-first architecture/tooling review before designing a custom solution;
- stock UE PCG + WorldSpec remains the default production worldgen base until a measured gap exists;
- prefer an Epic-native capability over adding a third-party runtime dependency when both solve the same problem cleanly;
- a candidate is adopted only when it removes a concrete implementation/performance/authoring problem;
- editor-only adoption is preferred over runtime dependency for the MVP;
- any adopted third-party tool requires license/provenance review, an exact pin, build/integration proof and a removal/rollback path;
- reference projects may inform patterns without entering the dependency graph;
- do not claim a public Embark repository represents the complete internal ARC Raiders production stack unless Embark documents that explicitly.
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

This proof is part of the reopened Stage 3G acceptance. A green build or capture harness without real imported/scattered assets does not satisfy it.

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
- the bike exposes four stable contact targets: left/right handlebar grip and left/right pedal;
- crank/pedal phase is driven from cadence and supplies foot-goal transforms instead of relying on baked clip contact;
- hand and foot contact must survive cadence/posture transitions;
- corner lean/tuck/standing are parameterized presentation driven from existing YACS physics/route state;
- head stabilization/look-ahead is an additive presentation layer and must not disturb contact constraints;
- cost of Control Rig + IK/FBIK must be profiled on RTX 2070 Super reference hardware.

### Stage 6 risk-reduction sequence

Before committing to the final production rider:

1. retarget one representative cycling mocap clip onto a placeholder/target rider with IK Rig + IK Retargeter;
2. prove the four simultaneous contact goals with FullBodyIK;
3. prove cadence-driven crank/pedals and contact preservation while cadence changes;
4. feed existing Stage 4 lean/corner context into a procedural rider pose without duplicating the physics model in animation code;
5. add additive head stabilization/look-ahead;
6. capture deterministic/reference proof poses and runtime sanity;
7. only then replace placeholder art with the selected production rider/bike and tune skinning/poses.

**Game Animation Sample 5.8 is a reference project, not a dependency.** Use it to learn current Epic patterns (including retargeting, Control Rig and additive Look-At) without migrating its general locomotion/motion-matching framework into a rider who is constrained to a bicycle.

Where already supported by the guarded YACS tooling surface, `ue-mcp` may automate repeatable asset creation/inspection/proof. Missing authoring operations do not by themselves justify another broad animation framework or an uncontrolled MCP server.

### Camera policy for MVP

The two MVP views are intentionally small in scope. Start with the stable conventional Unreal path:

`CameraComponent + SpringArm (where useful) + PlayerCameraManager`.

The UE 5.8 **Gameplay Camera System is Experimental**. Do not make it a production dependency unless the conventional approach demonstrates a named problem (for example damping/collision/blending/authoring complexity) and a bounded comparison proves the experimental system is worth the upgrade risk. The third-party `GameplayCameraToolset` is subordinate to that decision and is never an independent reason to adopt Gameplay Cameras.

Optional tools are added only if they remove measured production friction.

## 8. Stage 7 editor-tool policy

Do not build a custom editor application too early.

Start with:

1. WorldSpec;
2. named UE-MCP flows;
3. native PCG graphs;
4. Editor Utility/Python where appropriate.

For biome structure, study Epic's **PCG Biome Core / Sample** as reference architecture only. It is Experimental; YACS should reuse concepts (data-driven biome definitions, spline/volume boundaries, local/global composition) before deciding whether the plugin itself belongs in the production project.

**PCGEx** is not a default dependency. It gets one bounded comparison only after vanilla PCG exposes a named pain point such as route-exclusion/spatial queries, path processing or forest-density graph complexity. Admission requires a before/after comparison covering graph complexity, determinism, UE 5.8.2 build/upgrade risk and runtime/editor performance.

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

For MVP rain/spray, prefer **localized emitters around the rider/camera and wheels**. Weather state can be route/session-global, but particle simulation should not cover kilometres of unseen route merely to represent that global state. Profile the dense-foliage + rain + wet-road case explicitly.

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

Prefer a small source-sample set driven by `speed`, `cadence`, `power`, `coasting`, `braking`, `surface`, `wetness` and wind inputs over a large matrix of pre-rendered variants. No separate audio framework/plugin is admitted until baseline MetaSounds proves a concrete missing capability.

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
- PCGEx as a default dependency before a native-vs-PCGEx comparative spike;
- PCG Biome Core/Sample as a production dependency merely because its reference architecture is useful;
- the full Game Animation Sample locomotion/motion-matching stack;
- Gameplay Cameras / GameplayCameraToolset before a conventional-camera gap is demonstrated;
- large third-party weather/audio frameworks before Niagara/MetaSounds prove a concrete gap;
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
- Game Animation Sample 5.8 update: https://www.unrealengine.com/tech-blog/download-the-latest-game-animation-sample-project-now-updated-for-ue-5-8
- Gameplay Camera System overview (Experimental): https://dev.epicgames.com/documentation/unreal-engine/gameplay-camera-system-overview
- GameplayCameraToolset (third-party/MIT): https://github.com/iEclisse/GameplayCameraToolset
- PCG Biome Core / Sample: https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-in-unreal-engine
- PCGEx (third-party): https://github.com/PCGEx/PCGExtendedToolkit
- Scriptable Tools Editor Mode: https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ScriptableToolsEditorMode
- Niagara: https://dev.epicgames.com/documentation/unreal-engine/API/PluginIndex/Niagara
- MetaSounds: https://dev.epicgames.com/documentation/unreal-engine/metasounds-in-unreal-engine
