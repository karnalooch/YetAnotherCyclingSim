# YetAnotherCyclingSim — performance, world streaming and future multiplayer architecture

**Document version:** 0.1  
**Status:** Architecture notes / future constraints  
**Engine baseline:** Unreal Engine 5.8  
**Scope:** performance architecture for the current single-player project and design constraints that keep a future shared-world multiplayer possible  
**Important:** this document does **not** move multiplayer, a multi-route island, real trainer connectivity, MassEntity, Iris, traffic, or crashes into the MVP.

## 1. Purpose

This document records the architectural decisions and edge cases discussed while planning how YetAnotherCyclingSim can combine:

- realistic visual quality;
- a dense Alpine environment;
- dynamic weather;
- stable 1920×1080 / 60 FPS on the reference PC;
- large groups of visible cyclists in a future multiplayer version;
- acceptable behavior on imperfect network connections;
- a future Zwift-like region or island with a network of roads rather than a single fixed route.

The central rule is:

> **Simulation is the source of truth. Rendering, animation, audio and networking are representations of simulation state and must be allowed to run at different update rates.**

The current MVP remains a single 20–30 minute Alpine route and single-player experience. The architecture should avoid choices that would make a future road network or multiplayer unnecessarily expensive to add later.

---

## 2. Core architecture principles

### 2.1 Do not bind simulation to rendering

The existing fixed-step cycling physics direction remains correct.

Conceptually:

```text
input
  |
  v
fixed-step cycling simulation
  |
  +------> local/session state
  |
  +------> presentation state
              |
              +--> rendering
              +--> animation
              +--> audio
              +--> UI
```

A 60 FPS render loop does not require the cycling physics to run at 60 Hz.

A future multiplayer snapshot rate also does not need to equal either the physics rate or render rate.

The current 0.05 s fixed step (20 Hz) is a valid starting point for the cycling model, but it is **not a permanent network contract**. If later cornering or group physics require a higher internal simulation rate, that change must not force an equivalent increase in network traffic.

### 2.2 Avoid per-frame Actor logic where a centralized system is sufficient

Large rider counts, foliage and world objects must not become hundreds or thousands of independent expensive Actors ticking every frame.

Prefer:

- fixed-step simulation;
- event-driven updates;
- timers where appropriate;
- centralized rider significance;
- instancing;
- data-oriented storage for large future populations;
- reduced update frequency for distant or visually insignificant objects.

### 2.3 Road-space is more important than world-space

World `XYZ` is required for rendering, visibility, audio and some collision queries, but it should not be the only semantic representation of a cyclist.

A future road-network position should conceptually resemble:

```cpp
struct FRiderRoadPosition
{
    LaneId Lane;
    float DistanceAlongLane; // S, metres
    float LateralOffset;     // metres
};
```

World position and orientation are derived from road geometry plus the rider state.

This makes it possible to reason cheaply about:

- route progress;
- nearby riders;
- overtaking;
- drafting;
- intersections;
- branches;
- route selection;
- network relevance;
- future AI traffic.

### 2.4 Do not make one spline the permanent world model

The MVP may use one road spline because that is the smallest solution for the current stage.

The long-term concept must allow a graph:

```text
        B ---- C
       /        \
A ----+          +---- D
       \        /
        E ---- F
```

A road graph contains nodes/junctions and directed lane/road segments.

The MVP can therefore be understood as the simplest possible graph: almost a line.

This distinction prevents a future island from requiring a complete rewrite of save data, route logic, rider positioning and networking.

---

## 3. Recommended future road model

### 3.1 Canonical project model

The future project-owned road model should remain engine-independent domain data.

Possible concepts:

- `RoadNetwork`
- `RoadNode`
- `RoadEdge`
- `Lane`
- `LaneConnection`
- `RiderRoadPosition`

The project must not depend on a specific Unreal plugin as the canonical source of cycling simulation truth.

### 3.2 Unreal ZoneGraph

Unreal Engine includes ZoneGraph, which represents lanes, direction and connections and is used by other engine systems.

It may become a useful **adapter or presentation/AI representation** for YACS, especially for future traffic or Mass-based agents.

Recommended dependency direction:

```text
YACS RoadNetwork
    |
    +--> cycling physics
    +--> route logic
    +--> save/session state
    +--> future multiplayer
    +--> drafting
    |
    +--> adapter --> UE ZoneGraph
                      |
                      +--> AI / Mass / ambient traffic
```

Do not make ZoneGraph mandatory for the physics core before a measured need exists.

---

## 4. World structure: a network of corridors

A future island does not need to behave like a completely free-roaming open world.

Cyclists mostly travel on roads, so a large world can be constructed as a **network of visually rich road corridors** surrounded by cheaper terrain and background scenery.

Typical structure:

```text
high-detail road corridor
==========================

medium-detail surrounding vegetation / terrain

distant HLOD landscape / mountains / forests
```

At a junction, multiple possible corridors may temporarily need to be streamed.

This preserves much of the optimization advantage of a linear route while allowing free route choice.

---

## 5. World Partition, HLOD and PCG

### 5.1 World Partition

World Partition is the preferred Unreal-level direction for a future larger world because it:

- divides the persistent world into runtime cells;
- streams cells based on streaming sources;
- supports distance-based loading;
- integrates with HLOD and Data Layers.

The MVP does not have to introduce World Partition before it is needed, but content should avoid assumptions that make future conversion difficult.

### 5.2 Predictive streaming

A cyclist can move much faster than a walking character, especially on descents.

Streaming must eventually account for:

- current speed;
- direction;
- upcoming intersections;
- possible next branches;
- camera direction when it materially differs from travel direction.

At a junction, both likely branches may need to remain available until the choice is resolved.

### 5.3 HLOD

HLOD is important for Alpine vistas.

Distant, unloaded World Partition cells may still need to show:

- mountains;
- forest mass;
- villages;
- cliffs;
- roads visible across a valley.

HLOD can replace many distant static Actors with cheaper proxy representations and reduce draw calls.

### 5.4 PCG

PCG is a strong candidate for road-corridor content:

```text
road / terrain rules
    |
    +--> grass
    +--> trees
    +--> bushes
    +--> rocks
    +--> roadside clutter
    +--> barriers / repeated details where appropriate
```

UE 5.8 PCG integrates with World Partition, Data Layers and HLOD Layers.

Generated content still requires explicit performance budgets. Procedural generation is not automatically cheap.

---

## 6. Foliage and landscape performance

### 6.1 Prefer instanced foliage over thousands of Actors

Large vegetation counts should use systems intended for instancing.

Avoid representing every tree as a fully independent gameplay Actor unless the tree genuinely has gameplay behavior.

### 6.2 Nanite is a tool, not a project rule

Nanite can be useful for:

- rocks;
- cliffs;
- buildings;
- static infrastructure;
- selected vegetation assets where profiling proves a benefit.

UE 5.8 also documents Nanite Foliage, but the dedicated documentation still labels it Experimental. It must not become a hard dependency for YACS without a later spike and measurement on the reference hardware.

### 6.3 Foliage wind can be more expensive than polygon count suggests

World Position Offset animation on large amounts of foliage can be costly, especially together with shadowing.

Therefore foliage animation should be distance/significance aware.

Conceptual policy:

```text
near camera      full wind animation
medium distance  reduced wind complexity/update
far distance     minimal or no per-vertex wind
```

Exact distances must be measured on representative scenes rather than hard-coded from this document.

### 6.4 Weather must be tested in the worst visual location

A performance test that passes in a bare valley but fails in:

- dense forest;
- rain;
- wet road;
- many shadows;
- large rider group;

does not satisfy the project performance target.

---

## 7. Rider rendering and animation

Future multiplayer may produce scenes where many cyclists are visible simultaneously.

The expensive part is not the simple longitudinal cycling physics. Likely costs include:

- skeletal meshes;
- animation blueprints;
- IK;
- shadows;
- clothing/material complexity;
- multiple modular skeletal components;
- particles;
- audio emitters;
- nameplates and UI.

### 7.1 Central rider significance

Create one project-level concept such as `RiderSignificance`.

It may later consider:

- distance from camera;
- projected screen size;
- visibility;
- local player status;
- whether the rider is directly ahead;
- whether the rider is in the same local group;
- camera mode;
- gameplay relevance.

The significance result can control:

- skeletal LOD;
- animation update frequency;
- IK;
- shadow quality;
- particles;
- audio;
- nameplate visibility;
- future network visual update frequency.

Unreal Significance Manager is designed as a framework for this type of project-specific prioritization.

### 7.2 Animation Budget Allocator

UE's Animation Budget Allocator can limit the total game-thread animation cost and throttle less significant skeletal meshes.

It is a strong future candidate for dense pelotons.

Do not assume that all riders need animation evaluated at render frequency.

### 7.3 Animation Sharing

Animation Sharing may be evaluated for distant cyclists whose exact cadence phase is not visually important.

Near riders should preserve individual cadence and riding state.

Far riders may potentially be grouped into coarse animation states such as:

- seated low cadence;
- seated medium cadence;
- seated high cadence;
- standing;
- coasting.

This is a future optimization, not a current requirement.

### 7.4 Modular characters

Avoid creating every rider as many independently rendered skeletal components unless profiling demonstrates that this is acceptable.

For high rider counts, one merged or otherwise render-efficient body representation can be substantially more scalable than multiple clothing/body skeletal components per rider.

---

## 8. Future multiplayer authority model

### 8.1 Server authority

The future multiplayer model should be server authoritative for state that affects results.

The server owns the authoritative simulation state for:

- rider road position;
- speed;
- valid inputs;
- collisions/contact rules;
- drafting/gameplay effects;
- timing/results.

The client is responsible for responsive local presentation and prediction.

### 8.2 Do not network presentation details

Do not replicate:

- wheel rotation every frame;
- exact pedal bone transforms;
- every rain particle;
- cloud particle positions;
- individual foliage animation;
- purely cosmetic local effects.

Replicate semantic state from which presentation can be reconstructed.

A future rider snapshot may conceptually contain:

```text
RiderId
LaneId
DistanceAlongLane
LateralOffset
Speed
Power
Cadence
RiderStateFlags
ServerTick
LastProcessedInput
```

The exact binary format and quantization are deliberately deferred.

### 8.3 Independent clocks

Conceptually:

```text
input sampling          variable / device dependent
local prediction        responsive
physics                 fixed step
server simulation       authoritative fixed step
network snapshots       lower/independent frequency
remote interpolation    render-side
rendering               target 60 FPS
```

Do not encode an assumption that these rates are identical.

### 8.4 Input redundancy

A future unreliable input stream can repeat recent input samples/sequences so one lost packet does not necessarily lose one control action permanently.

Inputs should carry monotonically increasing sequence/tick information.

The server must reject stale, impossible or malicious input.

### 8.5 Client correction

Authoritative corrections must update simulation truth without necessarily snapping the visual rider instantly.

Separate:

- authoritative physical state correction;
- visual smoothing/reconciliation.

Never let visual interpolation feed back into the authoritative physics model.

---

## 9. Replication technology: defer the engine-specific choice

### 9.1 Replication Graph

Replication Graph is designed to scale replication for large player/Actor counts.

It remains a valid candidate.

### 9.2 Iris

Iris is Unreal's newer replication system and includes filtering and prioritization.

UE 5.8 documentation currently has a status inconsistency: the 5.8 release notes call Iris production-ready for licensees, while several Iris documentation pages still display an Experimental warning.

Therefore:

- do not make YACS domain logic depend directly on Iris;
- revisit the choice when multiplayer work actually starts;
- validate the exact engine version and shipping support at that time.

### 9.3 Replication Graph and Iris are alternatives

UE documentation states that Iris does not support Replication Graph. A NetDriver uses one system or the other.

YACS should therefore keep project network state independent from the replication backend so the later project can choose the best supported option.

Conceptually:

```text
YACS network state
       |
replication adapter
       |
       +--> Replication Graph / legacy path
       |
       +--> Iris path
```

---

## 10. Network relevance is not one-dimensional

A critical Alpine edge case is a rider who is far away by road distance but physically visible across a valley or on another hairpin.

Therefore future relevance should be split into at least three concepts.

### 10.1 Gameplay/simulation relevance

Used for:

- drafting;
- rider interaction;
- collision/contact envelopes;
- local race/group logic.

Primary basis:

- connected road/lane graph;
- `S` distance;
- heading;
- compatible lane topology.

### 10.2 Visual/network relevance

Used to decide whether the client should receive enough state to render another rider.

Primary basis may include:

- world-space distance;
- visibility;
- camera frustum;
- occlusion;
- screen size.

### 10.3 Session/UI relevance

Used for:

- leaderboard;
- map;
- event status;
- timing.

A rider can therefore be:

```text
gameplay relevance: no
visual relevance:   yes
session relevance:  yes
```

This occurs naturally on Alpine switchbacks.

---

## 11. Peloton and group simulation

### 11.1 Do not use full Chaos rigid-body interaction for ordinary peloton movement

A future group of 50–100 riders should not require 50–100 complete bicycle rigid-body simulations with detailed wheel constraints and continuous physical contacts merely to maintain pack spacing.

Prefer a cycling-specific road-space interaction model.

Possible concepts:

- rider envelope;
- `LaneId`;
- `S`;
- lateral offset;
- relative speed;
- local neighbors.

Chaos can later be used for effects that genuinely need rigid-body simulation, for example a future crash/ragdoll system outside the MVP.

### 11.2 Spatial/order acceleration

Riders can be indexed by lane/road segment and ordered by `S`.

This allows local neighbor queries instead of all-pairs checks.

Do not use road-distance alone for drafting. Validate:

- compatible lane/connectivity;
- heading;
- world separation when necessary;
- vertical separation;
- obstacle/tunnel/bridge topology.

This prevents drafting through a bridge deck, hairpin or nearby parallel road.

---

## 12. Weather architecture

Separate **physics weather** from **pretty weather**.

### Server/simulation-relevant weather

Examples:

- wind vector;
- air density;
- road wetness;
- temperature if used physically;
- weather zone/state;
- deterministic timeline/seed where required.

### Client visual weather

Examples:

- rain particles;
- droplets on camera;
- cloud detail;
- mist particles;
- splash effects;
- local decorative effects.

Only state that influences simulation/results needs authoritative synchronization.

---

# 13. Edge-case catalogue

These cases are design tests. They do **not** all require immediate MVP implementation.

## 13.1 Road graph and topology

### Crossing roads that are not connected

A bridge above another road may share almost identical world `X/Y` but must not be treated as an intersection.

Requirement:

- topology is explicit;
- proximity does not imply connectivity.

### Parallel lanes and opposite directions

Two riders can have similar `S` values while travelling in opposite directions.

Requirement:

- position identity includes lane/direction, not only distance.

### Hairpins

Two cyclists can be a few metres apart in world-space but hundreds of metres apart by road.

Requirement:

- gameplay relevance and visual relevance remain separate.

### Tunnels and roads directly above/below one another

A tunnel can place riders close in world-space but completely isolated for visibility, drafting and collision.

Requirement:

- topology, occlusion and vertical separation can override raw Euclidean distance.

### Junction boundary

A rider snapshot can arrive exactly while the rider changes from one lane/edge to another.

Requirement:

- transition ordering is deterministic;
- interpolation must know the valid graph connection;
- a client must not interpolate in a straight line through terrain between disconnected spline positions.

### Merge

Two lanes merge into one while multiple riders occupy similar longitudinal positions.

Requirement:

- merge ordering and overlap handling are deterministic;
- no rider is silently teleported behind another because of ambiguous ordering.

### Split / branch choice

A rider changes branch while latency is high.

Requirement:

- branch choice carries sequence/tick context;
- the server has a deterministic acceptance point;
- clients can correct an incorrect predicted branch without corrupting simulation state.

### U-turn or reverse travel

Even if not allowed in the MVP, future free riding may create wrong-way or U-turn cases.

Requirement:

- define whether reverse travel is legal;
- never assume `S` always increases.

### Dead end / closed road

A future live world may contain temporarily disabled lanes or route restrictions.

Requirement:

- graph validity is explicit;
- saved positions have a recovery strategy if the graph changes.

### World/map version change

A saved `LaneId + S` may become invalid after map edits.

Requirement:

- road-network data should eventually have a version or migration/recovery strategy.

---

## 13.2 Simulation edge cases

### Zero speed on a steep climb

If power is insufficient, speed can approach zero.

Requirement:

- no divide-by-zero;
- no oscillation around zero;
- explicitly decide whether backward rolling is supported or clamped.

### Very high descent speed

High speed shortens world-streaming and network reaction time.

Requirement:

- streaming look-ahead is speed-aware;
- simulation remains stable within supported speed limits.

### Frame hitch

A long render hitch must not feed one huge time step into physics.

Requirement:

- fixed-step accumulator;
- bounded catch-up policy;
- measurable behavior when the game cannot keep up.

### Pause/resume

Pausing rendering/session flow must not accidentally advance physical simulation through wall-clock time.

### Restart/reset

Resetting a ride must clear accumulators, interpolation history and derived presentation state consistently.

### Floating-point boundaries

A rider exactly at `S = edge length` must transition consistently rather than oscillating between two edges due to precision differences.

---

## 13.3 Input edge cases

These matter later for real trainers but should not leak into the physics architecture now.

### Power spike

A device may briefly report an impossible power value.

Requirement:

- validate device input before it becomes authoritative simulation input.

### Dropout

Power/cadence data can disappear temporarily.

Requirement:

- define hold-last-value, decay or zero behavior at the input adapter layer;
- physics core should receive a well-defined value, not device ambiguity.

### Cadence zero with positive power

Different devices may produce inconsistent transitional samples.

Requirement:

- the input adapter and simulation contract must define how inconsistent sensor samples are interpreted.

### Reconnect

A sensor may reconnect with stale timestamps.

Requirement:

- reject stale samples and maintain monotonic session time.

---

## 13.4 Networking edge cases

### Packet loss

One or more rider/input updates can disappear.

Requirement:

- interpolation/prediction tolerates missing updates;
- important state is eventually recoverable;
- recent-input redundancy can be evaluated for unreliable input delivery.

### Packet reordering

Older data can arrive after newer data.

Requirement:

- sequence/tick identifiers;
- stale state must never overwrite newer authoritative state.

### Packet duplication

A command may arrive more than once.

Requirement:

- input processing is sequence-aware/idempotent where necessary.

### Jitter

Packets may arrive at irregular intervals despite acceptable average latency.

Requirement:

- remote rider rendering uses a controlled interpolation buffer rather than directly rendering latest packet state.

### Sudden latency increase

A rider moves from 30 ms to 300+ ms latency mid-session.

Requirement:

- prediction/interpolation behavior degrades gracefully;
- no unbounded extrapolation.

### Temporary disconnect

The connection disappears for several seconds.

Requirement:

- define timeout states;
- freeze, coast, AI-hold or remove behavior must be explicit at multiplayer design time.

### Reconnect

A returning client may have old local state.

Requirement:

- server snapshot wins;
- rejoin state is resynchronized before accepting normal prediction again.

### Late join

A new client joins an already-running event/world.

Requirement:

- client can receive a coherent snapshot without replaying the entire historical session.

### Correction on a junction

A client predicts branch B; the server confirms branch C.

Requirement:

- authoritative lane topology is corrected first;
- visual smoothing must not drag the rider through a mountain or across an impossible road gap.

### Correction inside a hairpin

World-space smoothing may cut through the inside of the turn.

Requirement:

- large road-space corrections may need road-constrained visual reconciliation rather than straight-line `XYZ` lerp.

### Clock drift

Client and server clocks diverge.

Requirement:

- simulation/network sequencing uses server/session ticks or explicitly synchronized timing;
- do not trust local wall-clock time for race truth.

### Protocol/version mismatch

Client and server use incompatible road or network schema.

Requirement:

- fail clearly;
- never silently reinterpret lane IDs or snapshot structures.

### Malicious or impossible input

A client reports impossible power, position or timing.

Requirement:

- authoritative server validates input;
- client position is not trusted as race truth.

---

## 13.5 Dense-rider edge cases

### Mass start

Many cyclists may spawn in effectively the same area.

Requirement:

- avoid N² expensive logic;
- avoid every rider starting with maximum animation/shadow/audio cost simultaneously.

### 100 riders enter camera view at once

Example: cresting a hill into a large group.

Requirement:

- significance and animation budgeting react without one-frame catastrophic spikes.

### Stationary rider in moving group

A stopped rider may suddenly become an obstacle.

Requirement:

- local interaction model handles large relative speed safely.

### Fast overtake

A descending rider may pass several slower riders within a short period.

Requirement:

- neighbor structures update reliably;
- do not assume rider order changes slowly.

### Exact overlap

Two authoritative rider states may resolve to the same road-space position after reconnect/correction.

Requirement:

- deterministic separation/ghosting policy;
- never depend on full Chaos explosion response as the only recovery.

### Rider visibility across valley

Dozens of cyclists on distant switchbacks can be visible while not gameplay relevant.

Requirement:

- use very cheap distant representation and low update frequency;
- do not enable expensive IK/shadows/nameplates merely because the Actor exists.

### UI/nameplate overload

Even cheap distant rider meshes can become expensive or unreadable if every rider has a full nameplate.

Requirement:

- UI significance must be budgeted separately.

### Audio overload

Dozens of chains/freehubs must not create dozens of equally expensive spatial voices.

Requirement:

- audio has its own significance/voice budget.

---

## 13.6 Streaming and visual edge cases

### High-speed descent into unloaded cells

The player reaches a cell before it finishes loading.

Requirement:

- predictive loading based on velocity and route topology;
- instrument and test storage/CPU stalls.

### Junction preloading

Loading all possible branches too early may exceed memory; loading too late may cause visible pop-in.

Requirement:

- branch streaming has a measurable memory/performance policy.

### Camera looks backward

The cyclist moves forward while the player camera looks behind.

Requirement:

- streaming and HLOD must consider actual visibility, not only travel direction.

### First-person vs third-person

Different camera modes expose different geometry and rider detail.

Requirement:

- significance and near clipping/mesh visibility are camera-aware.

### HLOD transition on a visible distant road

A road across the valley changes between HLOD and full cell representation.

Requirement:

- minimize obvious popping and duplicate geometry.

### Remote rider on unloaded detailed road

A distant rider may remain visually relevant while the local detailed cell containing the road is unloaded.

Requirement:

- the rider must align acceptably with the available HLOD/proxy representation or be culled/faded consistently.

### Occluded crowd

A large peloton exists behind a mountain/forest/building.

Requirement:

- visibility/occlusion can reduce rendering work, but network/session state should not depend on renderer visibility alone.

### Rain + dense foliage + wet road + crowd

This is a likely worst-case GPU scene.

Requirement:

- include it in future stress benchmarks.

### Foliage wind and shadow invalidation

Large animated forests can invalidate shadow work repeatedly.

Requirement:

- wind/shadow distance policies are part of performance tuning.

### Dynamic quality transition

If dynamic resolution or scalability changes during a heavy scene, the transition must not destabilize physics or UI readability.

---

## 13.7 Weather edge cases

### Physics weather changes before visuals

A server-authoritative wetness or wind transition may arrive before local visual effects catch up.

Requirement:

- physics correctness wins;
- visuals converge independently.

### Visual weather differs between clients

Individual rain drops and cloud micro-detail do not need to match.

Requirement:

- only gameplay-relevant weather state is synchronized.

### Weather seed and replayability

Random weather used for testing should be reproducible.

Requirement:

- preserve a deterministic seed/timeline for tests and saved sessions where required.

### Extreme transition

Rain intensity jumps sharply because of a zone boundary or state update.

Requirement:

- visual smoothing is allowed;
- physical state transition behavior must be explicitly defined.

---

## 13.8 Failure and recovery edge cases

### Asset missing or late

A rider cosmetic or environmental asset fails to load.

Requirement:

- safe fallback representation;
- simulation continues.

### Performance budget exceeded

The scene cannot maintain the target frame time.

Requirement:

- degrade presentation before changing simulation correctness.

Candidate degradation order may include:

1. distant animation frequency;
2. rider shadows;
3. foliage animation/shadows;
4. particle density;
5. distant detail;
6. render resolution through TSR/dynamic resolution.

The actual order must be validated visually and by profiling.

### Server overload

A future server cannot simulate all work within its tick budget.

Requirement:

- gameplay simulation must have explicit budgets and instrumentation;
- do not solve overload by making authoritative time nondeterministically follow frame time.

### Save during topology-sensitive state

A future free ride is saved exactly at a lane transition.

Requirement:

- save enough information to restore to one deterministic valid lane location.

---

# 14. Performance contract

The project already has a primary target:

- 1920×1080;
- approximately stable 60 FPS;
- Intel Core i5 10th generation;
- 32 GB DDR4;
- NVIDIA RTX 2070 Super.

At 60 FPS the total frame budget is about **16.67 ms**.

Performance must be measured using representative builds and scenes, not estimated from editor appearance.

## 14.1 Current MVP benchmark scenes

At minimum:

1. simple road baseline;
2. dense forest;
3. high-mountain vista;
4. worst MVP weather;
5. worst MVP weather inside dense vegetation;
6. representative corner with full rider animation and HUD;
7. complete route traversal to catch streaming/memory accumulation.

## 14.2 Future rider-count benchmark tiers

These are **post-MVP architecture benchmarks**, not current acceptance criteria:

- 1 rider;
- 20 visible riders;
- 50 visible riders;
- 100 visible riders stress case.

Each tier should record:

- game thread;
- render thread;
- GPU frame time;
- frame-time spikes;
- animation cost;
- draw calls;
- memory;
- network cost when applicable.

## 14.3 Future network test profiles

Suggested future profiles:

| Profile | RTT / latency intent | Packet loss | Purpose |
|---|---:|---:|---|
| Good | ~30 ms | 0% | baseline |
| Typical | ~80 ms | 0–1% | ordinary Internet |
| Weak | ~150 ms | ~5% | degraded connection |
| Bad | ~300 ms | ~10% | stress |
| Harsh | ~500 ms RTT | 10%+ | failure/exploit discovery |

UE Network Emulation can simulate latency, loss, jitter, reordering and duplication.

Epic's documentation explicitly recommends testing very harsh multiplayer conditions, including approximately 500 ms round-trip ping and 10% packet loss or higher, to reveal bugs that ideal local/LAN testing misses.

---

# 15. Quality scaling strategy

The project should have meaningful presets rather than only an "everything max" target.

Conceptually:

### Ultra

- highest supported lighting/shadow quality;
- highest foliage density/detail;
- highest rider visual quality;
- intended for faster GPUs.

### High

- visual target for the reference machine if profiling permits;
- high-quality lighting;
- controlled foliage/shadow cost.

### Medium

- reduced shadow/foliage cost;
- cheaper distant rider presentation;
- preserve physics and gameplay.

### Low

- aggressive shadow, foliage and effect reductions;
- maintain readable road, rider and HUD behavior.

TSR and/or Dynamic Resolution may be evaluated as tools to preserve frame rate in GPU-heavy scenes.

No visual scalability setting may change authoritative physics outcomes.

---

# 16. Technology decisions: now versus later

## Adopt as project principles now

- fixed-step simulation independent from rendering;
- avoid unnecessary Tick;
- performance measurement on the reference PC;
- simulation/presentation separation;
- future road-network compatibility;
- project-owned domain data rather than plugin-owned truth;
- significance-based visual cost;
- separate gameplay, visual and session relevance;
- degrade graphics before simulation correctness.

## Use when the world reaches the relevant stage

- World Partition;
- HLOD;
- PCG;
- instanced foliage;
- Significance Manager;
- Animation Budget Allocator;
- TSR/Dynamic Resolution where profiling justifies them.

## Evaluate later with spikes before commitment

- ZoneGraph adapter;
- Animation Sharing for distant riders;
- MassEntity/MassCrowd for large distant populations or ambient agents;
- Nanite Foliage;
- Replication Graph;
- Iris;
- Network Prediction;
- specialized network compression/quantization.

## Explicitly avoid making mandatory now

- multiplayer implementation before stable single-player MVP;
- dedicated backend merely because multiplayer is planned;
- full Chaos bicycle rigid-body simulation for every rider;
- server replication of cosmetic animation transforms;
- one Actor Tick per environmental object;
- single-spline assumptions in persistent data formats;
- engine-plugin-specific road representation inside the cycling physics core.

---

# 17. Proposed future architecture

```text
                       YACS DOMAIN
                           |
            +--------------+--------------+
            |                             |
      Road Network                  Cycling Simulation
   Lane + S + lateral                 fixed step
            |                             |
            +--------------+--------------+
                           |
                    Session State
                           |
            +--------------+--------------+
            |                             |
      Local single-player          Future server authority
                                          |
                                   network snapshots
                                          |
                             prediction / interpolation
                                          |
            +-----------------------------+-----------------------------+
            |                             |                             |
        World/road                    Rider visuals                 Weather visuals
  World Partition / HLOD          significance / budgets        client-side effects
      PCG / instancing             skeletal LOD / audio          physics state separate
```

The important dependency direction is:

> **Unreal presentation consumes domain state. The domain simulation must not require the renderer to be correct.**

---

# 18. Development consequences for the current MVP

This document should influence current code only where the choice is cheap and does not expand scope.

Examples:

- keep physics independent of Actor transform;
- keep the fixed-step runner;
- avoid embedding route semantics only in Level Blueprint;
- use explicit route/road position abstractions rather than spreading raw spline calculations everywhere;
- avoid unnecessary per-frame Actor Tick;
- profile the reference PC regularly;
- keep weather physics data separate from visual effects;
- do not create persistent save formats that can only represent one hard-coded route implementation.

Do **not** start:

- multiplayer;
- road-network UI;
- island construction;
- MassEntity migration;
- Iris integration;
- Replication Graph integration;
- real trainer networking;

until the roadmap reaches those stages.

---

# 19. Architectural guardrails for reproducibility, observability and long-term maintainability

These rules are intentionally broader than one Unreal subsystem. They exist to keep future debugging, performance work, data migrations and multiplayer development tractable without expanding the current MVP feature scope.

## 19.1 Reproducibility and data evolution

### Replayable simulation log

The project should make it possible to reproduce a ride from domain inputs rather than from recorded presentation frames.

A future replayable session record should conceptually contain:

- initial rider/bike configuration;
- route or road-network version;
- physics model version;
- weather seed/timeline when relevant;
- ordered rider input samples with simulation timestamps/ticks;
- session configuration and assists;
- only the minimum additional authoritative events that cannot be reconstructed deterministically.

This does **not** require a user-facing replay feature in the MVP.

The immediate architectural goal is to avoid designs in which a bug can only be reproduced by visually recording the original run.

Potential later uses include:

- physics bug reproduction;
- regression tests;
- ghost rides;
- corner analysis;
- support diagnostics;
- spectator/replay systems;
- multiplayer dispute investigation.

### Version all persistent domain contracts

Persistent or externally exchanged data should not rely on an implicit "current" interpretation forever.

Introduce explicit versions when the corresponding format exists, for example:

- `PhysicsModelVersion`;
- `SaveFormatVersion`;
- `RoadNetworkVersion`;
- `ReplayFormatVersion`;
- future `NetworkProtocolVersion`.

A recorded ride must not silently change meaning because CdA handling, cornering logic, road geometry or another domain rule changed in a later build.

Migration behavior should be explicit:

- migrate when safe and well-defined;
- preserve the original version when historical interpretation matters;
- reject clearly when compatibility is impossible;
- never silently reinterpret incompatible identifiers or units.

### Golden Ride regression harness

Create a deterministic reference ride that feeds a known sequence of inputs through the cycling simulation.

The scenario should eventually cover representative conditions such as:

- steady flat riding;
- acceleration;
- climbing;
- descending;
- coasting;
- wind;
- selected cornering states when that subsystem exists;
- wet-road behavior when that subsystem exists.

The harness should compare outputs against approved reference values with documented tolerances.

Useful checkpoints include:

- distance;
- velocity;
- elapsed simulation time;
- selected sector times;
- important state transitions.

The purpose is to detect unintended physics drift automatically.

The Golden Ride belongs to simulation/testing architecture, not to rendering and not to a manually driven Unreal scene.

---

## 19.2 Observability and performance discipline

### Built-in YACS performance telemetry

Manual Unreal profiling remains necessary, but the project should also expose lightweight project-specific telemetry.

A future diagnostic stream may record:

- simulation step time;
- game-thread frame time;
- render-thread frame time;
- GPU frame time where accessible;
- total/visible/significant rider counts;
- rider animation budget state;
- active/streamed world-cell counts;
- memory high-water marks;
- streaming events;
- current weather state;
- quality/scalability state;
- network RTT/loss/jitter in multiplayer builds.

Telemetry must be cheap enough that a diagnostic build can capture an entire ride.

The goal is to answer questions such as:

> "At what point did rain + dense forest + 54 visible riders begin exceeding the frame budget?"

rather than relying on memory or subjective impressions.

### Track hitches, not only average FPS

The 60 FPS target implies approximately 16.67 ms per frame, but average FPS alone is insufficient.

A build that averages 60 FPS while producing periodic 100–200 ms stalls is not acceptable.

Performance analysis should therefore track:

- frame-time percentiles;
- worst-frame spikes;
- asset/streaming hitches;
- shader/PSO-related stalls when relevant;
- garbage collection or allocation spikes;
- memory pressure and unexpected growth during a full-route run.

A future performance contract should define an acceptable hitch budget from measurements on the reference PC.

### Add an explicit memory/streaming budget

A large future road network can be GPU-fast while still stuttering because too much content is loaded or streamed at once.

World work should therefore eventually define measurable budgets for:

- resident memory;
- streaming look-ahead;
- branch preloading;
- texture/mesh residency;
- HLOD transition cost;
- worst-case junction memory.

Do not solve streaming pop-in by indefinitely increasing the amount of permanently loaded content.

### Make scalability data-driven and centralized

Quality decisions should be expressed through a coherent YACS scalability policy rather than scattered one-off conditionals.

A centralized quality/significance configuration should be able to coordinate:

- foliage density;
- foliage wind;
- shadow distance/quality;
- rider skeletal LOD;
- animation frequency;
- IK;
- particles;
- audio voice limits;
- distant rider representation;
- HLOD/detail ranges;
- render resolution strategy.

This ensures that "Low", "Medium", "High" and "Ultra" describe coherent performance envelopes instead of unrelated switches.

---

## 19.3 State boundaries and content validation

### Make Simulation State and Presentation State explicit

The existing simulation/presentation separation should become a named code-level boundary.

Conceptually:

```text
authoritative simulation state
          |
          v
 presentation target/state
          |
          v
 interpolation / animation / camera / FX
```

Examples:

- simulation may immediately set an authoritative lean target;
- presentation may blend the visible rider toward that target;
- authoritative road position may be corrected instantly;
- visual reconciliation may smooth the correction along valid road topology.

Presentation state must never become an input to authoritative cycling physics merely because it looks smoother.

This distinction is important for:

- frame-rate independence;
- replay;
- multiplayer reconciliation;
- animation throttling;
- camera smoothing;
- future server/headless execution.

### Add a world/content validation pipeline

As route/world complexity grows, important geometric and semantic assumptions should be machine-checkable.

Future validators should check appropriate subsets of:

- continuous road/lane connections;
- valid node/edge references;
- unique/stable IDs where required;
- legal lane direction/connectivity;
- discontinuities in grade/elevation;
- extreme curvature/radius values;
- invalid zero-length segments;
- impossible spawn/start/finish placement;
- duplicate or disconnected graph pieces;
- topology-sensitive save points;
- missing performance metadata for expensive assets where the pipeline requires it.

For the MVP spline, the validator can begin small and expand only when needed.

The purpose is to prevent world-authoring errors from becoming hard-to-reproduce runtime bugs.

### Define safe fallback rider representation

A future remote cyclist must remain representable even when a cosmetic asset fails, loads late or is unsupported.

Provide a known fallback:

- default rider;
- default bike;
- safe materials;
- bounded animation/render cost.

Simulation/session identity must not depend on cosmetic asset availability.

A missing jersey, helmet or bike mesh must never make a competitor disappear from race truth.

---

## 19.4 Runtime and server independence

### Keep multiplayer domain independent from the final backend/runtime

The future authoritative simulation should not conceptually require:

- a rendered Unreal level;
- skeletal meshes;
- local audio;
- player cameras;
- cosmetic assets.

The long-term target should allow the authoritative domain to run in a headless/server-oriented environment.

A likely future deployment target is a headless Linux server, but the exact backend process, hosting model and transport must not be selected before multiplayer requirements and measurements justify them.

Dependency direction should remain:

```text
cycling / road / session domain
            |
            +--> Unreal client presentation
            |
            +--> future authoritative server adapter
```

and not:

```text
Unreal visual Actor state
            |
            v
     cycling domain truth
```

This preserves the option to scale simulation separately from graphics and makes automated server-side tests practical.

---

# 20. External technology references

Official Unreal Engine 5.8 documentation:

- World Partition: https://dev.epicgames.com/documentation/unreal-engine/world-partition-in-unreal-engine
- World Partition HLOD: https://dev.epicgames.com/documentation/unreal-engine/world-partition---hierarchical-level-of-detail-in-unreal-engine
- PCG with World Partition: https://dev.epicgames.com/documentation/unreal-engine/using-pcg-with-world-partition-in-unreal-engine
- Significance Manager: https://dev.epicgames.com/documentation/unreal-engine/significance-manager-in-unreal-engine
- Animation Budget Allocator: https://dev.epicgames.com/documentation/unreal-engine/animation-budget-allocator-in-unreal-engine
- Replication Graph: https://dev.epicgames.com/documentation/unreal-engine/replication-graph-in-unreal-engine
- Iris introduction: https://dev.epicgames.com/documentation/unreal-engine/introduction-to-iris-in-unreal-engine
- Migrate to Iris / Replication Graph difference: https://dev.epicgames.com/documentation/unreal-engine/migrate-to-iris-in-unreal-engine
- Network Emulation: https://dev.epicgames.com/documentation/unreal-engine/using-network-emulation-in-unreal-engine
- MassCrowd API: https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/MassCrowd
- Nanite Foliage: https://dev.epicgames.com/documentation/unreal-engine/nanite-foliage
- UE 5.8 release notes: https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes

The exact feature status of experimental/new engine systems must be re-verified against the engine version used when implementation starts.

---

# 21. Summary of architectural decisions

1. The MVP remains single-player and one route.
2. The long-term world model is a road/lane graph, not a permanently linear spline.
3. Rider semantic position is future-friendly as `Lane + S + lateral offset`; world `XYZ` remains a derived presentation/spatial value.
4. Physics, network snapshots, animation and rendering have independent update rates.
5. Future multiplayer is server authoritative with client prediction/interpolation.
6. Network semantic state, not cosmetic transforms.
7. Visual relevance is separate from drafting/gameplay relevance.
8. Large pelotons require significance and explicit animation/render/audio budgets.
9. Ordinary peloton interaction should be a cycling-specific road-space model rather than full rigid-body Chaos for every bike.
10. World Partition + HLOD + PCG are strong candidates for a future island/network-of-corridors world.
11. Instancing and measured foliage policies are required for dense vegetation.
12. Experimental/new technologies such as Nanite Foliage or a specific replication backend are optional until measured and needed.
13. Poor-network tests, including packet loss, jitter and reordering, are part of future multiplayer acceptance rather than an afterthought.
14. Performance degradation must sacrifice visual fidelity before simulation correctness.
15. Edge cases in this document are architectural tests and future requirements, not permission to expand the current MVP.
16. Sessions and persistent domain data should be reproducible and explicitly versioned rather than relying on implicit current behavior.
17. A deterministic Golden Ride should guard against unintended physics drift.
18. Performance acceptance includes hitches, memory/streaming behavior and project-specific telemetry, not only average FPS.
19. Scalability should be centralized and data-driven across foliage, riders, shadows, FX, audio and resolution.
20. Simulation State and Presentation State are explicit architectural boundaries; presentation smoothing never becomes physics truth.
21. Road/world content should gain automated validation as complexity grows.
22. Missing cosmetics/assets must fall back safely without removing riders from simulation/session truth.
23. Future authoritative multiplayer domain logic should remain capable of headless/server execution and independent from Unreal presentation assets.