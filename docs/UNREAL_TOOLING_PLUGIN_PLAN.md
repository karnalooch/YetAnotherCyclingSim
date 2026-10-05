# YetAnotherCyclingSim — Unreal tooling & plugin plan

**Status:** active production plan
**Applies to:** UE 5.8.2 MVP roadmap
**Rule:** no plugin is enabled “just in case”.
**Official MCP decision, 2026-10-05:** #384 is the future official-server adoption path, blocked by complete #363 admission/merge and preceding #364. Planning only; preserve the current engine, plugin list, db-lyon pin and safety model. See [the bounded contract](UE_MCP_WORLD_GENERATION.md#official-unreal-mcp-adoption).
**Current M3 recovery gate:** the core PCG assets with legacy Stage 3G identifiers (`PCG_RouteExclusion`, `PCG_Forest`, `PCG_Valley`, `PCG_HighAlpine`) are validated mainline deliverables. Historical R4/R4.1 names remain only where they identify existing evidence or workflows; current planning uses M3 workstreams. The recovery keeps native PCG and route/physics separation and follows the Embark-first tooling admission policy before any new custom authoring surface.

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

`YetAnotherCyclingSim.uproject` currently enables the following editor/tooling plugins explicitly:

- **Modeling Tools Editor Mode** — editor-only;
- **Python Editor Script Plugin** (`PythonScriptPlugin`) — editor-only;
- **PCG** — editor-only for the current authoring path;
- **Editor Scripting Utilities** — editor-only;
- **Geometry Script** (`GeometryScripting`) — editor-only;
- **RoadForge Mesh Core** — vendored MIT donor, **editor-only**; not part of the shipping runtime surface.

The official UE `ModelContextProtocol` plugin is not enabled as an independent server. #384 plans the official server as the future control-plane entrypoint after its #363 entry gate and guard-parity proof; no activation is performed by this decision. The project already has `EngineAssociation: 5.8`; no engine migration is implied. The project also uses Enhanced Input in C++, but this document focuses on plugin/tooling decisions rather than every engine module dependency.

Any change to the explicit plugin list is an integration change and requires an Unreal editor build plus relevant Automation/proof on the home/reference PC.

## 3. Stage-by-stage plan

| Stage | Tool / plugin | Priority | Why YACS needs it | Activation policy |
|---|---|---:|---|---|
| **M3** | **PCG** | MUST | deterministic vegetation, rocks, biome/set dressing and roadside generation | validated mainline foundation; R4.1 extends composition/roadside usage without changing route ownership |
| **M3** | **Editor Scripting Utilities** | MUST | safer/simpler editor automation APIs complementing PythonScriptPlugin | active authoring dependency for deterministic editor-time world generation and proof workflows |
| **M3** | **Geometry Script** | SHOULD | generate/analyze/edit helper geometry, mesh processing and custom world-authoring tools | R4.1 uses it in a bounded continuous/tiled-terrain vertical-slice comparison; keep route physics independent and persist only reproducible results |
| **M3** | **PCG Geometry Script Interop** | CONDITIONAL | PCG ↔ Dynamic/Static Mesh operations and mesh sampling when a graph actually requires them | enable only on demonstrated graph need |
| **M3** | **PCGToolset + Skill_PCGGraphGeneration** | EXPERIMENT | official graph authoring with reference examples and skill context | later #365 after #384 admission; not required by the minimal spike; preserve YACS authority/guards |
| **M3/M7** | **Water + Landmass** | OPTIONAL | lake/river/terrain shaping if water survives art-direction review | leave disabled until composition decision |
| **6** | **Control Rig** | MUST | procedural cycling posture and in-engine rig control | enable at Stage 6 start |
| **6** | **IK Rig** | MUST | mocap retargeting, IK goals and retarget chains | enable at Stage 6 start |
| **6** | **FullBodyIK** | MUST | simultaneous hand/pedal/body constraints and procedural pose adjustment | enable with Control Rig proof |
| **6 reference** | **Game Animation Sample 5.8** | REFERENCE | current Epic examples for retargeting, Control Rig, additive Look-At and animation debugging | study/copy patterns selectively; do not migrate the locomotion framework into YACS |
| **6 cameras** | **Gameplay Cameras** | DEFER / EXPERIMENTAL | possible future data-driven camera rigs if the conventional camera stack shows a concrete gap | MVP starts with CameraComponent/SpringArm/PlayerCameraManager; comparative spike only on measured need |
| **6 cameras dev tooling** | **GameplayCameraToolset** | EXPERIMENT / THIRD-PARTY | optional MCP authoring surface for Gameplay Cameras | do not add unless Gameplay Cameras itself passes the separate admission spike |
| **6** | **Skeletal Mesh Editing Tools** | OPTIONAL | small mesh/skinning fixes in UE without external round-trip | evaluate only after rider import pain is measured |
| **6** | **Control Rig Modules** | OPTIONAL/BETA | reusable modular rig blocks | evaluate after minimal YACS Control Rig works |
| **M7 reference** | **PCG Biome Core / Sample** | REFERENCE / EXPERIMENTAL | study data-driven biome composition for valley/forest/high-Alpine authoring | reference first; production dependency only after a YACS-specific proof |
| **M3/M7** | **PCGEx** | PINNED EXTENSION / THIRD-PARTY | extend native PCG for named spatial/path/filter gaps | preserve already proven authoring integrations; new uses require version-matched API evidence and bounded proof; the Bible owns admission |
| **M7** | **Scriptable Tools Editor Mode** | OPTIONAL | custom “Generate YACS World” editor mode/UI if flows become cumbersome | add only if it clearly beats MCP flows/Editor Utility workflows |
| **M8** | **Niagara** | MUST | rain, wheel spray, debris/leaves and atmospheric VFX | enable/verify when weather implementation begins |
| **M8** | **MetaSounds** | SHOULD | parameter-driven drivetrain/freehub/tyres/brakes/wind audio | enable/verify when production audio starts |
| **M3+ dev tooling** | **db-lyon ue-mcp** | RETAINED BASELINE | historical #85 flows, guards, rollback and editor/proof interface pending #384 cutover | keep exact `1.3.9` / `d79a34bb6e7a5883457efe8f33c9f85b1ba3e136`, committed lock and `npm ci --ignore-scripts`; do not remove before safety-parity proof |
| **M3+ dev tooling** | **Official Unreal MCP / All Toolsets / Toolset Registry** | PLANNED / EXPERIMENTAL / BLOCKED | #384 official interface with scene/object inspection and AutomationTestToolset; later MaterialInstanceTools for #364 | full #363 admission first; bounded surface, real BOB result/proof/receipt and guard parity; no two independent mutation servers |
| **M3 editor tooling** | **RoadForge Mesh Core** | INCLUDED / EDITOR-ONLY | vendored MIT road-mesh primitives used only as a bounded presentation-geometry donor | Editor target only; no shipping/runtime dependency; production SP638 adapter still requires its own bounded visual/technical proof and never owns route/physics truth |

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
| **PCGEx / PCGExtendedToolkit** | additional spatial/filter/path/asset-staging uses beyond the already proven integration | a named gap in native PCG plus bounded proof | `new-use candidate; existing pin/admission retained` |
| **EssentialUE5PCG** | reference patterns for spline-driven forest/rocks/path and dynamic-mesh authoring | Stage 3G implementation | `reference` |
| **PCG Biome Core** | reference architecture for data-driven biome definitions, asset sets, filters, exclusions and blending | Stage 3G-R5 / Stage 7 | `reference/optional-experiment` |
| **Analog Strike** | reference for deterministic offline generation -> UE import/authoring -> capture pipeline | Stage 3G-R5 / Stage 7 | `reference` |
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
## 4. M3 world-generation stack (legacy Stage 3G identifiers retained)

Retained db-lyon baseline diagram below. The future official-server target and
authority diagram are in [the #384 decision](UE_MCP_WORLD_GENERATION.md#official-unreal-mcp-adoption).
The old path is not a mandate to build a second generic bridge.

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

Native PCG remains the foundation and PCGEx a pinned extension. Load the official
PCG graph-generation skill before later graph work; evaluate PCG Primitives and
the shape grammar definition skill for #377, with exact installed identifiers
and source/licence checks. Semantic Search and Terminal are optional, not #384
deliverables. #376 performance tooling is also outside the minimal spike.

From world-finishing step 3 onward, use official Epic MCP for supported generic
Unreal control within YACS safety constraints. Custom toolsets contain only YACS
domain knowledge/contracts. Existing producers and proof/CI workflows keep their
roles. After the bounded #384 DoD succeeds, stop infrastructure work and return
to #364 asphalt/shoulder; no general platform expansion is authorized.

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
