# YACS World Building Bible

**Status:** authoritative world-building methodology  
**Applies to:** all terrain, road, earthwork, vegetation, material, world-streaming and environment-authoring work  
**Product milestone:** M3 now, reused by later world-content milestones  
**Supersedes as methodology:** ad-hoc Stage 3G / R4.1 / B.x world-building decisions  
**Does not supersede:** `ROAD_PHYSICS_PROFILE.md`, route geometry contracts, provenance rules or CI proof contracts

This document answers one question:

> **How do we build a believable, performant YACS world without fighting Unreal Engine?**

It is the architectural source of truth for world construction. Experiments and historical proof documents may explain how we arrived here, but new world work starts from this document.

Architecture and workflow diagrams in this document follow the shared [YACS Blueprint diagram style](DIAGRAM_STYLE.md), inherited from Gumball.

---

## 1. The 12-year-old mental model

Think of the world as a model made from clay.

- **DTM / DEM** is the mold that tells the clay where the mountains and valleys are.
- **Unreal Landscape** is the big piece of clay.
- **Landscape Edit Layers** are transparent sheets placed on top of the clay. One sheet keeps the real terrain, another can contain the road earthworks, another manual corrections.
- **Road spline** is a string showing where the road goes.
- **Landscape Spline / road earthworks layer** is a small bulldozer that cuts or fills the clay around that string.
- **Road mesh** is the actual asphalt placed on the prepared corridor.
- **Static meshes / Nanite meshes** are rocks, cliffs, retaining walls and other shapes that a heightfield cannot represent well.
- **Landscape Material** paints grass, dirt, scree and rock.
- **PCG** is the gardener that places trees, grass, rocks and roadside props according to rules.
- **RVT** helps different surfaces visually blend together. It is makeup, not geometry.
- **World Partition / HLOD / culling** make sure the computer does not render the whole mountain range at full cost all the time.

The important rule is:

> **The road does not fight the terrain. The road defines its local corridor, and the presentation terrain adapts around it.**

Far away from the road, the terrain remains faithful to the real DTM. Near the road, controlled earthworks create a believable cut/fill transition.

---

## 2. Authority: what is allowed to define what

YACS deliberately separates physical truth from visual presentation.

| Domain | Authority | May presentation override it? |
|---|---|---|
| Route XY | canonical route / verified road GIS geometry | **No** |
| Physics grade / distance / curvature / banking inputs | `ROAD_PHYSICS_PROFILE.md` and route contracts | **No** |
| Macro mountain shape | licensed canonical DTM/DEM | only bounded presentation corrections |
| Road visual surface | generated road mesh from canonical alignment | yes, within presentation tolerances |
| Road cut / fill / shoulders | Landscape Edit Layer / local geometry | yes |
| Cliffs / rocks / scree | dedicated meshes / PCG / materials | yes |
| Vegetation | PCG / authored hero placement | yes |
| Weather / lighting | environment systems | yes |

A prettier Landscape must never silently become physics truth.

A road mesh must never be snapped to Landscape vertices just because that makes a seam disappear.

---

## 3. Core technology stack

### Required architecture

**GIS / preprocessing**
- QGIS/GDAL/Python for source inspection, crop, reprojection, deterministic conversion and provenance.
- Metric CRS before metric operations.
- Immutable hashes for canonical external source packages.

**Unreal Engine**
- Landscape for macro terrain.
- Landscape Edit Layers for non-destructive world authoring.
- Landscape Splines or an equivalent controlled spline-earthwork path for road corridor deformation.
- Road presentation mesh generated independently from the Landscape grid; the implementation is selected through the tooling admission policy rather than assumed to be bespoke.
- Geometry Script / Landscape patches / explicit helper meshes for bounded local geometry where Landscape alone is insufficient.
- Landscape Materials for broad surface classification.
- PCG for deterministic repeated placement.
- World Partition, HLOD, culling and instancing for scale.
- Nanite where measured and appropriate.

### Optional tools

These can accelerate production but are not architecture:

- Gaea / World Creator: procedural terrain creation, masks, erosion references.
- Brushify or similar packs: materials, brushes, cliffs, road dressing.
- Megascans / Fab content: rocks, cliffs, surfaces and vegetation.
- Ultra Dynamic Sky or similar weather/sky packages.
- Houdini: advanced procedural world production if later justified by scale.

Do not adopt an optional tool merely because it is fashionable or appears in a tutorial. Prefer it when a bounded evaluation shows that it solves a real YACS production problem better than a smaller or more native solution.

### 3.1 Tools-first authoring policy

YACS owns the **truth and the acceptance contract**. It does not need to own every world-building algorithm.

The default rule is:

> **No custom world-building system before a tool audit.**

Before creating a new terrain, road-earthwork, biome, vegetation, snow, erosion, scatter or world-generation subsystem, evaluate the problem in this order:

1. **Embark production-pattern review first** — inspect the closest public Embark tool or documented workflow and extract the relevant production boundary, data-flow and authoring lessons. This is evidence review, not automatic dependency adoption.
2. **Epic-native capability second** — use current Unreal systems and official Epic samples/reference implementations such as Landscape Edit Layers, Landscape Splines, Landscape Patch, PCG, World Partition, HLOD and material layers when they satisfy the contract.
3. **Proven external / open-source / DCC tooling third** — evaluate established tools such as Houdini Engine or reviewed OSS when Epic-native capabilities leave a concrete gap. Reuse source only after license/provenance review.
4. **Custom YACS last** — write bespoke code only for the smallest remaining gap that is specific to YACS or cannot meet the required quality, determinism, provenance, performance or automation contract with the options above.

The intended architecture is:

```mermaid
flowchart LR
    SRC["SOURCE<br/>Real-world data"] --> AUTH["YACS AUTHORITY<br/>Route · physics · provenance"]
    AUTH --> EMBARK["REVIEW<br/>Embark public pattern"]
    EMBARK --> AUDIT["AUDIT<br/>Smallest capable tool"]

    AUDIT --> NATIVE["EPIC NATIVE<br/>Landscape · Patch · PCG"]
    AUDIT -.-> EXT["PROVEN TOOL<br/>OSS · Houdini · DCC"]
    AUDIT -.-> CUSTOM["YACS GAP<br/>Minimal custom"]

    NATIVE --> ADAPT["INTEGRATE<br/>Thin YACS adapter"]
    EXT --> ADAPT
    CUSTOM --> ADAPT

    ADAPT --> GEN["GENERATE<br/>Deterministic presentation"]
    GEN --> VERIFY["VERIFY<br/>Visual · technical · performance"]
    VERIFY -->|"PASS"| WORLD["OUTPUT<br/>Accepted world slice"]
    VERIFY -->|"FAIL"| FIX["FAIL CLOSED<br/>Change tool or contract"]

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class SRC input;
    class AUTH owned;
    class EMBARK evidence;
    class AUDIT decision;
    class NATIVE,EXT,CUSTOM tool;
    class ADAPT,GEN,VERIFY exec;
    class WORLD success;
    class FIX danger;

    linkStyle default stroke-width:2px;
```

What remains YACS-owned even when an external tool performs authoring:

- canonical route XY and route-local identity;
- Road Physics Profile and simulation authority;
- verified DTM/LiDAR/GIS source data and provenance;
- road visual profile constraints such as width, longitudinal profile and regularized crossfall/camber;
- deterministic seeds/configuration where generation must be reproducible;
- performance budgets;
- exact-SHA technical proof and human rider-camera acceptance.

The tool may shape presentation. It may not silently become the source of physical truth.

### 3.2 Architecture evidence ladder

YACS must distinguish a proven production pattern from an attractive demo.

Use this evidence order when evaluating a world-building architecture:

```mermaid
flowchart LR
    SHIP["1 · SHIPPED PRODUCT<br/>Documented real use"] --> CASE["2 · PRODUCTION CASE<br/>Studio pipeline evidence"]
    CASE --> SAMPLE["3 · OFFICIAL SAMPLE<br/>Working reference project"]
    SAMPLE --> DEMO["4 · TECH DEMO<br/>Integrated proof"]
    DEMO --> TUTORIAL["5 · TUTORIAL<br/>Learning example"]
    TUTORIAL --> HYP["6 · HYPOTHESIS<br/>YACS assumption"]

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class SHIP success;
    class CASE,SAMPLE evidence;
    class DEMO tool;
    class TUTORIAL input;
    class HYP danger;

    linkStyle default stroke-width:2px;
```

The arrow means **decreasing evidentiary strength**, not a mandatory implementation order.

A stronger external precedent increases confidence that a pattern is viable. It does **not** prove that the same tool or configuration works for Passo Giau. YACS still requires its own bounded proof against its own inputs and acceptance contract.

Current reference points:

| Reference | Evidence tier | What it supports | What it does **not** prove |
|---|---|---|---|
| **Far Cry 5 / Ubisoft** | shipped product + documented production pipeline | procedural tools can generate biomes, terrain texturing, freshwater networks, cliffs and other large-world layers while artists retain control | that Ubisoft's exact tools or terrain assumptions fit YACS |
| **THE FINALS / Embark** | shipped product + production case study | procedural Houdini tooling can automate expensive repeated environment-authoring work while exposing artist-friendly controls | that its building/destruction workflow directly solves terrain or roads |
| **Unreal Engine 5.8 City Sample PCG** | official working sample | large procedural world construction can be authored entirely inside current Unreal using PCG, uneven terrain, roads, vegetation and World Partition | shipped-game production maturity for every demonstrated Experimental/Beta subsystem |
| **Project Pegasus / SideFX** | integrated tech demo | Houdini + Unreal can form a coherent open-world terrain, paths, material and foliage pipeline | shipped-product evidence |

Sources:

- SideFX / Ubisoft — Far Cry 5 procedural world generation:  
  https://www.sidefx.com/learn/talks/procedural-world-generation-far-cry-5/
- SideFX / Embark Studios — procedural buildings of THE FINALS:  
  https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/
- Epic Games — Unreal Engine 5.8 City Sample PCG update:  
  https://www.unrealengine.com/learning/city-sample-gets-a-major-update-with-pcg-and-unreal-mcp-workflows
- SideFX — Project Pegasus:  
  https://www.sidefx.com/pegasus/

### 3.3 Implementation proof gate

The architecture is now mature enough that further generalization must be earned by implementation evidence.

> **Do not generalize the world-data model before one complete producer → derived data → consumer → regeneration path has been proven.**

> **A world-generation architecture is not validated until a local source change produces a deterministic, bounded downstream rebuild.**

Before introducing or materially expanding a reusable world-generation subsystem, answer these five production questions with evidence from the smallest working vertical slice:

| Question | Required answer |
|---|---|
| **Data contract** | What exact data crosses the boundary? Define ownership, units, CRS/coordinate space, resolution/sampling and version identity only for fields the slice actually needs. |
| **Invalidation** | If one source changes locally, what becomes dirty, and what explicitly stays clean? |
| **Stable intermediate representation** | Which derived facts are computed once and reused by downstream systems, and in what concrete representation? |
| **Override survival** | Which local authored corrections must survive regeneration, and how is that intent stored independently from regenerated output? |
| **Reproducibility metadata** | Which source hashes, generator/config versions, seed and spatial scope are sufficient to reproduce the generated result? |

Do **not** answer these questions by designing a large speculative schema. Add fields and abstractions only when a proven producer or consumer requires them.

The first proof target is intentionally narrow:

```mermaid
flowchart LR
    SP638["SOURCE<br/>Real SP638 change"] --> CORRIDOR["PRODUCER<br/>Road Corridor Data"]
    DTM["SOURCE<br/>Real DTM"] --> CORRIDOR

    CORRIDOR --> EARTH["AUTHOR<br/>One earthwork path"]
    CORRIDOR --> MASK["DERIVE<br/>Road exclusion / distance"]
    MASK --> CONSUMER["CONSUMER<br/>One PCG/environment rule"]

    EARTH --> BEFORE["PROOF A<br/>Deterministic baseline"]
    CONSUMER --> BEFORE

    CHANGE["LOCAL EDIT<br/>Bounded SP638 change"] --> DIRTY{"INVALIDATE<br/>Affected scope only"}
    DIRTY --> CORRIDOR2["REBUILD<br/>Local corridor data"]
    CORRIDOR2 --> EARTH2["REBUILD<br/>Affected earthworks"]
    CORRIDOR2 --> MASK2["REBUILD<br/>Affected road data"]
    MASK2 --> CONSUMER2["REBUILD<br/>Affected consumer"]

    EARTH2 --> AFTER["PROOF B<br/>Expected local delta"]
    CONSUMER2 --> AFTER
    DIRTY -.-> CLEAN["UNCHANGED<br/>Unrelated world remains clean"]

    AFTER --> GATE{"VERIFY<br/>Same inputs = same output?"}
    CLEAN --> GATE
    GATE -->|"YES"| ACCEPT["ACCEPT<br/>Architecture proven"]
    GATE -->|"NO"| BLOCK["STOP<br/>Fix contract before generalizing"]

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class SP638,DTM,CHANGE input;
    class CORRIDOR,CORRIDOR2 owned;
    class EARTH,MASK,CONSUMER,EARTH2,MASK2,CONSUMER2 exec;
    class DIRTY,GATE decision;
    class BEFORE,AFTER,CLEAN evidence;
    class ACCEPT success;
    class BLOCK danger;

    linkStyle default stroke-width:2px;
```

This is an **implementation proof target**, not permission to pre-design a universal world schema. The concrete data contract should emerge from this slice and then be generalized only when a second real consumer or producer demonstrates the need.

#### Tools-first decision flow

A tools audit is itself a fail-closed architecture decision:

```mermaid
flowchart LR
    PROBLEM["INPUT<br/>Bounded world problem"] --> EMBARK["REVIEW<br/>Closest Embark pattern"]
    EMBARK --> NATIVE["TRY<br/>Epic-native path"]
    NATIVE --> D1{"MEETS<br/>YACS contract?"}
    D1 -->|"YES"| ADOPT["ADOPT<br/>Smallest solution"]
    D1 -->|"NO"| EXT["EVALUATE<br/>Proven OSS / DCC"]
    EXT --> D2{"MEETS<br/>YACS contract?"}
    D2 -->|"YES"| ADOPT
    D2 -->|"NO"| CUSTOM["IMPLEMENT<br/>Minimal YACS gap"]
    CUSTOM --> VERIFY["VERIFY<br/>Same proof contract"]
    ADOPT --> VERIFY
    VERIFY -->|"PASS"| ACCEPT["OUTPUT<br/>Validated architecture"]
    VERIFY -->|"FAIL"| BLOCK["FAIL CLOSED<br/>Revise approach"]
    BLOCK -.-> PROBLEM

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class PROBLEM input;
    class EMBARK evidence;
    class NATIVE,ADOPT,CUSTOM,VERIFY exec;
    class EXT tool;
    class D1,D2 decision;
    class ACCEPT success;
    class BLOCK danger;

    linkStyle default stroke-width:2px;
```

#### Passo Giau Embark escalation — selected after native visual failure

The direct Unreal-native Passo Giau baseline is now a **failed visual baseline**,
not an open architecture question.

Evidence from PR #256 established that the implementation can:

- import the 4033 x 4033 Passo Giau R16 through Unreal's native Landscape reader;
- persist a real `Base_DTM` edit layer;
- author `Road_Earthworks` with the verified SP638 spline using
  `EditorApplySpline`;
- persist an independent spline road mesh;
- generate technical proof and rider-view evidence.

The same rider-view proof showed unacceptable blocky/stair-stepped terrain.
Therefore the tools-first ladder has moved past the direct-DTM/native-only
terrain-foundation tier for this route. Repeating cosmetic variations of the
same direct import is not the default next action.

The selected Passo Giau authoring chain is based on Embark's publicly documented
landscape workflow, while keeping unpublished Embark internals out of scope:

```mermaid
flowchart LR
    RAW["SOURCE<br/>MASE LiDAR + Veneto fallback"] --> PDG["HOUDINI PDG<br/>Ingest · reconcile · condition"]
    PDG --> WORK["WORKING TERRAIN<br/>32-bit metric heightfield"]
    WORK --> GAEA["GAEA BRIDGE<br/>Terrain shaping"]
    GAEA --> HUTIL["HOUDINI HEIGHTFIELD<br/>Utility / validation pass"]
    HUTIL --> HDA["BRIDGE<br/>Houdini → Unreal export/import"]
    HDA --> BASE["UNREAL<br/>Base_DTM Edit Layer"]
    BASE --> EARTH["UNREAL<br/>Road_Earthworks"]
    EARTH --> ROAD["PRESENTATION<br/>Independent SP638 mesh"]
    ROAD --> MESO["PRESENTATION<br/>Cliffs · retaining · meso"]
    MESO --> RVT["BLEND<br/>RVT when geometry is correct"]
    RVT --> WP["SCALE<br/>World Partition when justified"]
    WP --> PROOF["VERIFY<br/>Rider view · exact SHA · perf"]
    PROOF -->|"PASS"| ACCEPT["OUTPUT<br/>Accepted Passo Giau terrain"]
    PROOF -->|"FAIL"| OWNER{"DIAGNOSE<br/>Owning stage"}
    OWNER -.-> PDG
    OWNER -.-> GAEA
    OWNER -.-> HUTIL
    OWNER -.-> EARTH
    OWNER -.-> MESO

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class RAW input;
    class PDG,HUTIL,HDA tool;
    class GAEA tool;
    class WORK evidence;
    class BASE,EARTH,ROAD,MESO,RVT,WP exec;
    class PROOF evidence;
    class OWNER decision;
    class ACCEPT success;

    linkStyle default stroke-width:2px;
```

Public evidence supporting this escalation:

- Embark Landscape Creation, Darko Pracic, GDC HIVE 2023 — Embark publicly
  describes LiDAR terrain input, PDG LiDAR processing, the Gaea bridge,
  in-house heightfield utility HDAs, and export/import from Houdini to Unreal:
  https://www.sidefx.com/learn/talks/embark-landscape-creation/
- SideFX Houdini Engine for Unreal — current plugin documentation supports
  Landscape input/output, Height Fields, Edit Layers and World Partition:
  https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html
- Epic / Embark ARC Raiders production interview — Embark identifies Runtime
  Virtual Texturing and World Partition as key UE5 worldbuilding systems for
  large terrain-heavy worlds:
  https://www.unrealengine.com/developer-interviews/embark-studios-build-the-award-winning-arc-raiders-with-unreal-engine

This does **not** authorize invention of Embark's proprietary HDA internals.
YACS must use official Houdini/Gaea primitives and its own explicit contracts
for source reconciliation, terrain shaping, masks and export. Unknown Embark
parameters remain unknown.

##### Passo Giau data contract

The pipeline must keep these boundaries explicit:

1. **Canonical source evidence** — original MASE/Veneto packages, hashes,
   licenses, CRS and coverage reports remain immutable.
2. **PDG working heightfield** — 32-bit metric terrain in EPSG:32632, with source
   masks and reconciliation metadata. This is derived, reproducible data.
3. **Gaea shaping result** — 32-bit terrain output with a fixed seed/build
   recipe and explicit input/output paths. It is presentation authoring, not
   route or physics authority.
4. **Houdini final heightfield** — validated dimensions, bounds, min/max domain,
   masks and export attributes suitable for the documented Houdini → Unreal
   export/import boundary. The exact bridge implementation is YACS-owned unless
   stronger public Embark evidence proves their internal choice.
5. **Unreal `Base_DTM`** — engine representation of the conditioned terrain.
   It remains separate from `Road_Earthworks` and later
   `Local_Corrections`.
6. **SP638 authority** — canonical road XY/profile/physics stay outside the
   terrain generator and may not be moved by Gaea/Houdini shaping.

Every stage must record:

- tool executable/version identity;
- recipe/HIP/HDA/terrain-file hash;
- input hashes;
- output hashes;
- CRS / spatial bounds / resolution;
- deterministic seed or explicit statement that the stage is deterministic
  without a seed;
- stage duration and exit code;
- the exact downstream artifact that consumed the output.

##### No-shortcut rule for this escalation

For Passo Giau, do not replace the selected chain with:

- another direct cubic R16 import with different smoothing constants;
- a custom NumPy blur sold as "terrain conditioning";
- material/RVT camouflage for geometric defects;
- helper meshes that merely hide the failed macro terrain;
- guessed recreations of Embark proprietary nodes.

A deviation is allowed only when a documented tool is unavailable/incompatible
or a bounded YACS proof demonstrates that a stage adds no value. Record that
evidence before removing the stage.

##### Current bounded substitution — PCGEx-first proof

Issue #287 / PR #288 currently use a **bounded PCGEx-first substitution** for the
first procedural authoring proof. The public Embark evidence still defines the
production pattern we are preserving — deterministic source ingest, procedural
derived-data authoring, explicit authority boundaries, reproducible handoff to
Unreal and rider-camera proof — but **PCGEx is not claimed to be an Embark Studios dependency**.

This substitution is selected because the exact Houdini/Gaea DCC chain is not a
current runner prerequisite and its commercial/tooling setup would block the
bounded YACS proof before we know whether an Unreal-native, MIT-licensed authoring
tool can satisfy the immediate road/corridor need. Houdini/Gaea remain the
documented optional escalation when the bounded PCGEx proof leaves a demonstrated
terrain-authoring gap.

The current PCGEx proof is deliberately narrow:

- bootstrap the reviewed PCGEx revision at an immutable commit and keep it
  authoring-only;
- compile the YACS Editor module against that exact plugin API;
- generate a deterministic PCG graph from YACS-owned C++ rather than hand-edited
  graph state;
- consume the prepared official SP638 presentation data while preserving the
  canonical route or physics authority outside PCGEx;
- derive bounded resample/smooth/offset corridor paths without moving the
  authoritative road;
- keep `Base_DTM` and `Road_Earthworks` separate and non-destructive;
- record exact-SHA evidence, presentation deviation and rider-camera visual proof
  before accepting any generated road/earthworks result.

The current Gate B proof is now an **established road-authoring baseline**.
At exact repository state `eb33c583...`, the pinned PCGEx path executed against
the prepared official SP638 presentation data and fed the rider-close consumer.
The measured presentation deviation remained bounded (about 0.176 m horizontal
p95, about 0.8 m horizontal max and about 7.5 mm vertical p95 for the proven
corridor). This is sufficient to stop treating PCGEx road smoothing as the default
suspect for the current visual failure.

Gate C.1 then separated two independent terrain-presentation defects at the
same exact-SHA hairpin. Variant A proved that rider-close faceting already exists
with the macro Landscape alone. Variant C proved that the previous local terrain
skin is independently invalid even with the Landscape hidden, so the failure is
not explained by coincident-surface overlap alone. Variants B/D/E preserve those
failures while adding the corridor/combined ownership states.

Therefore, until a concrete regression says otherwise, **freeze the proven PCGEx
road path and diagnose terrain source/near-field ownership instead of tuning road
smoothing**. The active Gate C.3 proof reads a bounded 512 m x 512 m, 1 m working
grid directly from the prepared native metric DTM, transfers only that patch to
the Unreal proof runner, performs no Landscape collision sampling and no terrain
smoothing, hides the macro Landscape, and renders the resulting DynamicMesh with
the road corridor disabled. Its purpose is diagnostic: distinguish source quality
from DynamicMesh transform/winding/rendering defects before road constraints are
introduced.

If the terrain-ownership recovery later proves a real PCGEx boundary, document
that evidence and then use the tools-first ladder. Do not hide the failure with
material camouflage, another bespoke smoothing stack or a road-alignment change.

#### Passo Giau surface-ownership recovery after Gate B

Issue #287 / PR #288 established a useful separation of concerns:

- official SP638 -> YACS source -> PCGEx resample/smooth -> bounded corridor is a
  working presentation path;
- the road/corridor can be technically healthy while the surrounding terrain is
  still visually unacceptable;
- the current rider proof still depends on the legacy
  `/Game/Prototype/Maps/L_PassoGiauTerrainSpike` macro Landscape and a local
  terrain surface sampled back from that Landscape.

The immediate architecture problem is therefore **surface ownership**, not
another road-centerline algorithm.

##### One visual owner per place

Do not render two independently modified ground surfaces in the same rider-close
space and rely on a tiny Z offset to keep them ordered. If a local near-field
surface is the rider-visible ground owner, the macro Landscape must stop owning
that same patch.

The target ownership model is:

| Zone / concern | Geometry authority |
|---|---|
| distant mountains / valley mass | Macro Landscape / `Base_DTM` |
| medium distance | Macro Landscape plus meso meshes |
| broad road accommodation | `Road_Earthworks` |
| rider-close ground requiring higher fidelity | native-DTM-derived bounded near-field surface |
| asphalt | independent road mesh |
| shoulders | road/shoulder presentation geometry |
| unusual cut/fill | local earthwork geometry or constrained local ground |
| cliffs / walls / rocks / scree | dedicated mesh / PCG geometry |
| simulation | Road Physics Profile / route contracts, separately |

PCGEx does not become physics authority. Landscape does not become road XY
authority. A visually better terrain mesh does not become simulation truth.

##### Diagnostic matrix before another generator

Before changing the terrain architecture again, capture the same exact-SHA
hairpin, camera pose, FOV and lighting with only ownership toggled:

| Variant | Macro Landscape | near-field/local ground | road corridor | Purpose |
|---|---:|---:|---:|---|
| A | ON | OFF | OFF | isolate macro-terrain faceting |
| B | ON | OFF | ON | macro terrain + road |
| C | OFF | ON | OFF | isolate local ground quality |
| D | OFF | ON | ON | local ground + road without macro overlap |
| E | ON | ON | ON | current combined baseline |

Observed Gate C.1 result is evidence-driven:

- A fails with macro-Landscape faceting before any road/local surface is present;
- C fails independently with the Landscape hidden, so the old
  `Landscape -> line trace -> 4 m grid -> smoothing -> DynamicMesh` path is not a
  valid near-field foundation;
- B/D/E combine those failures with corridor/ownership interactions and do not
  justify changing the frozen road authority.

Gate C.3 therefore changes exactly one causal variable: the local terrain source.
It uses the prepared 1 m metric DTM directly as a bounded neutral mesh and keeps
macro Landscape, road corridor, cut/fill, smoothing, materials camouflage and
route/physics changes out of the proof.

The proof location is versioned explicitly. Do not let the DTM-preparation stage
and the post-PCGEx Unreal renderer independently choose a "most curved" hairpin:
bounded smoothing can change which hairpin wins that heuristic without changing
road authority. Gate C uses the representative hairpin recorded in
`worldgen/embark/passo_giau_terrain_pipeline.json`; the native patch is cut at
that official-SP638 station and the renderer still fails closed unless its actual
PCGEx-selected focus lands inside the patch with the required margin. Proof
location selection is test infrastructure, not route or physics truth.

Do not replace this diagnostic with guessed smoothing percentages.

##### Capture resource readiness — Issue #293

A fixed screenshot delay is not evidence that the engine has loaded the height
textures needed by the rider view. The bounded capture path primes the existing
rider camera in the editor viewport and invokes Epic's native
`AutomationLibrary.finish_loading_before_screenshot()` immediately before
submitting A-E/C3 screenshots. It records map-owned height-texture metadata
before/after in `capture-readiness.json` and in the proof. Missing viewport,
failed native loading or still-placeholder/compiling height textures fail closed.
No height pixels, source resolution, LOD policy, road geometry, materials or
persisted map assets are changed by this preparation.

This is a capture-validity experiment, not acceptance of the macro terrain.
Mip readback is taken before screenshot-task submission, not on the exact GPU
capture frame; completed texture compilation alone does not establish full mip
residency or visual quality. Compare the unchanged camera and road hashes and
inspect the PNG before attributing stair-stepping to this stage. Never respond
to a failed result with a hidden global streaming disable or DTM smoothing.

M3 run 92 completed the native loading barrier but retained macro stepping;
64 combined height textures still reported 7 of 10 resident mips. The controlled
run 94 at `b22ea83432c96dc7796cba9b802fe4c049001536` requested full height mips
for variant A only. All 64 became 10/10 and the pronounced macro staircase
artifact disappeared from that same-camera A image. B/E retained 7/10 and the
coarse terrain. The sampled height-texture source exports were byte-identical,
and camera, PCGEx output and corridor hashes were unchanged. This establishes
height-mip residency as a cause of the observed capture defect, not source-data
quantization or a reason to replace the established road pipeline.

The bounded capture preparation therefore requests a transient 120-second native
mip-residency lease for map-owned, mipmapped height textures whenever the macro
Landscape is visible (A/B/E). C/D/C3 do not request macro mip residency. The native
loading barrier must finish and full-mip readback must pass before capture;
partial/placeholder results fail closed. The lease expires after the process or
duration, does not serialize `NeverStream`, and does not disable streaming globally.

This fixes a forced-LOD proof resource precondition; it is not a blanket production
runtime policy, performance acceptance or a cure for every terrain/road seam.
Keep the single-owner near-field and road/earthwork acceptance gates independent.
The A-only causal result does not substitute for reviewing the combined A-E/C3
candidate, additional representative locations and performance where required.

Official API references:
- https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UStreamableRenderAsset
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem

##### Native metric DTM for rider-close ground

The production candidate for near-field ground should be:

`prepared native metric DTM -> bounded rider patch -> road/earthwork constraints -> transition -> mesh`

not:

`Landscape -> vertical trace -> replacement terrain skin`.

MASE remains the primary terrain source and the documented Veneto source remains
fallback where required by coverage/provenance. Road and terrain preprocessing
must meet in the same metric coordinate system before Unreal Landscape-grid
quantization.

Start with a bounded representative hairpin at native or near-native spacing
(typically around 1-2 m for the current proof) rather than making the entire
8 km world equally dense. The rider corridor and distant mountain mass have
different spatial-quality budgets.

##### Deterministic transition to macro terrain

The local owner must transition to macro Landscape through a deliberate band,
not by coincident overlap or an arbitrary lift. A suitable bounded pattern is:

- high-fidelity native-DTM interior;
- transition band;
- outer ring pinned/constrained to macro-terrain height;
- measurable seam delta and no competing surface inside the owned patch.

Reuse proven local primitives such as existing pinned-border-cell behavior where
they satisfy this contract instead of inventing another world system.

##### Road constraints before local triangulation

Where practical, apply the proven PCGEx centerline/corridor and YACS road-profile
constraints to the near-field terrain before final triangulation:

`native terrain -> road corridor constraints -> cut/fill transition -> single local ground mesh -> asphalt/shoulders`.

The goal is to avoid stacking road mesh + earthwork mesh + terrain skin +
Landscape as four independent surfaces at the same location.

##### Edit-layer semantics are explicit

Never select a Landscape edit layer by API-return order. For road work:

- `Base_DTM` must exist and remain semantic source terrain;
- exactly one `Road_Earthworks` layer must exist;
- road cut/fill selects `Road_Earthworks` explicitly by name;
- missing/duplicate `Road_Earthworks`, or accidental `Base_DTM` selection,
  fails closed;
- proof output records available edit layers and the selected earthworks layer.

##### Acceptance and scaling order

Neutral geometry passes before materials/foliage/RVT/lighting camouflage.
The first accepted hairpin is only a bounded proof. Before route propagation,
repeat the rider proof on at least:

- a difficult hairpin;
- a normal/moderate slope corridor;
- a high-elevation-difference / strong-earthworks section.

Only after neutral geometry is visually accepted should the relevant performance
proof set thresholds for the chosen representation. Meso cliffs/rocks/retaining,
materials, vegetation and final weather follow after the ground ownership contract
is proven.

##### BOB — Builder Of Berms: adaptive terrain policy and verified-case learning

Route-wide terrain adaptation must not become a growing list of location-specific
patches. The production direction is a deterministic adaptive solver that observes
road/terrain context, chooses among already-admitted terrain strategies, records
why it made that choice, and may reuse parameters only from previously verified
proof cases.

The initial decision vector includes at least:

- longitudinal grade;
- left/right cross-slope;
- road-to-native-DTM elevation delta;
- local native-DTM roughness;
- signed curvature/radius;
- distance and height separation to a competing road branch;
- required cut/fill magnitude.

The strategy library is intentionally small:

- native blend / minor correction;
- constrained cut/fill corridor;
- tight-hairpin clearance corridor;
- retaining/cliff or other non-heightfield escalation when one heightfield cannot
  represent the geometry safely.

The adaptive layer is a **policy/orchestration layer**, not permission to bypass
the tools-first decision ladder below. A strategy may invoke only an already
admitted native/custom authoring path. If a heightfield is structurally wrong for
the observed geometry, the solver escalates instead of learning to hide the defect.

PCGEx is the preferred **spatial feature engine**, not the owner of the adaptive
policy. Reuse its strengths in filters, attributes, sampling, graph/path operations,
heuristics and—only where separately proven useful—tensor/vector-field operations
to measure or propagate corridor context. Normalize those results into the
versioned `adaptive_terrain_feature_contract.json` packet. The packet must record
its source artifact and exact PCGEx revision, preserve canonical road XY, and
explicitly remain non-authoritative for route geometry and physics.

The YACS-owned architect for this layer is **BOB — Builder Of Berms**.
BOB is the deterministic road-earthworks decision system; the technical module
and schemas retain descriptive adaptive-terrain names so implementation details
remain searchable and backend-neutral.

BOB owns the next layer:

- safe baseline strategy selection;
- strategy-specific bounded parameters;
- verified-case similarity matching;
- learning eligibility;
- non-heightfield escalation;
- the final explainable decision report.

This separation is deliberate. A PCGEx graph may answer **"what spatial situation
is this?"** and may provide reusable scores/attributes. It must not answer **"this
proof is accepted, add it to memory"** and must not silently rewrite the policy.

Embark's public `texture-synthesis` project is useful only as an architectural
analogy for **example-based generation**: multiple examples may inform a new
result while the generator remains explicit about its inputs. It is not evidence
that Embark uses an equivalent terrain-learning system, and YACS does not copy or
depend on that repository for terrain generation. The transferable lesson is to
keep examples as explicit inputs instead of burying successful one-off fixes in
location-specific code.

Learning is review-gated and deterministic:

1. baseline policy chooses a safe strategy from versioned thresholds;
2. only cases with exact-SHA technical PASS **and** human visual PASS are eligible
   learning examples;
3. sufficiently similar accepted cases may tune bounded parameters **inside the
   same safe strategy**;
4. case memory cannot override a retaining/cliff or ambiguity escalation;
5. proof output records the feature vector, baseline strategy, final parameters,
   contributing case IDs and similarity/confidence;
6. accepted cases enter a versioned repository ledger through normal review;
7. threshold/model calibration happens offline and produces a reviewed candidate
   config change; runtime/editor generation never rewrites its own policy.

Do not auto-promote failed, merely green, or unreviewed visual evidence into the
learning memory. Do not infer successful terrain behavior from a single hairpin.
The first route-general policy requires accepted cases for the difficult hairpin,
a normal/moderate slope and a major-earthworks section already required by the
acceptance order above.

The bounded H candidate now runs `scripts/worldgen/review_sp638_terrain.py`
against its actual rendered centerline, road-edge/shoulder constraint mesh and
verified native-DTM grid. This measures the existing candidate and may generate the bounded retaining
repair candidate described below. It does not execute BOB's proposed heightfield
parameters. Feature measurement is YACS Python
analysis; it must not be described as native PCGEx feature emission.

`bob_terrain_review.json` retains exact SHA and input digests, per-station
features/decisions, missing DTM coverage, non-heightfield escalation and the
existing candidate's measured adjustment metrics. Branch search is bounded to
the supplied render slice, with an explicit 20 m adjacent-arc exclusion; it
does not prove absence of competing branches outside that slice. Roughness is
the 3x3 native-grid tangent-plane residual; required cut/fill is the road-edge
and shoulder envelope, excluding zero-weight outer ties. The report is written
before constraint generation so rejected/failed attempts retain the decisions.
The existing H render remains diagnostic and is retained for inspection, but
the H validator rejects BOB escalation or incomplete coverage. `MEASURED`
means measurement and strategy admission completed, not human visual PASS.
This review never updates policy, applies proposed heightfield parameters or
promotes a learning case. Retaining execution has its own explicit
`repair_execution.geometry_applied` evidence; `parameters_applied` still refers
to the heightfield decision parameters. Offline calibration and full acceptance remain
under Issue #303.

BOB also carries the versioned expert rule `bob-local-retaining-repair-v1` in
`adaptive_terrain_policy.json`. On escalation its report proposes a local rock
cut/retaining solution for cut and a supported shoulder/retaining solution for
fill, using signed native-DTM deltas at both road edges and shoulders. Left and
right refer to the road-local mesh frame, not screenshot coordinates. Mixed
cut/fill on one side retains both design candidates. Shared ground between
branches must have one owner; canonical road XY and escalation thresholds stay
protected. The recipe requires local tie-ins, candidate generation, repeated
measurement and neutral render review. It is proposed expert knowledge, **not
executed geometry or a verified learning case**. The bounded candidate executor now reuses the existing transient DynamicMesh
consumer: it clips original shoulder-to-tie ground triangles, inserts a bench,
vertical cut/fill face and native tie-in, and tapers the flagged interval at both
ends. Signed edge measurements choose the side; station numbers are not hardcoded.
Folded footprints, unsupported stacked branches, mixed cut/fill faces and excessive
region/face bounds fail closed. The report labels execution
`GENERATED_PENDING_VALIDATION`: source-DTM escalation remains visible and still
blocks the H acceptance gate. Generation is not structural suitability or proof
of all clearance/ownership/performance contracts. Verification and final promotion
remain under Issue #303, requiring technical and human visual PASS on the same
exact SHA.

```mermaid
flowchart LR
    OBS["OBSERVE<br/>Road + native DTM"] --> FEAT["MEASURE<br/>Deterministic features"]
    FEAT --> POLICY["DECIDE<br/>Versioned safe policy"]
    CASES["MEMORY<br/>Verified PASS cases"] --> MATCH["MATCH<br/>Similar same-strategy cases"]
    POLICY --> MATCH
    MATCH --> STRAT["AUTHOR<br/>Admitted terrain strategy"]
    STRAT --> PROOF["VERIFY<br/>Exact-SHA rider proof"]
    PROOF -->|"PASS"| ACCEPT["ACCEPT<br/>Reviewed case"]
    PROOF -->|"FAIL"| FIX["FAIL CLOSED<br/>Owning layer / escalation"]
    ACCEPT --> CASES
    FIX -.-> POLICY

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class OBS input;
    class FEAT,STRAT exec;
    class POLICY,MATCH decision;
    class CASES owned;
    class PROOF evidence;
    class ACCEPT success;
    class FIX danger;

    linkStyle default stroke-width:2px;
```

#### Road / earthworks decision ladder

For road-terrain adaptation, do not extend the custom earthwork solver merely because a difficult hairpin exposes another edge case.

For a representative difficult corridor, compare the smallest viable approaches against the **same** canonical road input and the **same** rider-camera proof:

```mermaid
flowchart LR
    ROAD["AUTHORITY<br/>Canonical SP638"] --> REVIEW["REVIEW<br/>Embark / production pattern"]
    REVIEW --> A["A · UE NATIVE<br/>Landscape Spline"]
    REVIEW --> B["B · UE NATIVE<br/>Landscape Patch"]
    REVIEW --> C["C · YACS BASELINE<br/>Current cut/fill"]
    A --> PROOF["VERIFY<br/>Same hairpin proof"]
    B --> PROOF
    C --> PROOF
    PROOF -->|"native passes"| KEEP["PREFER<br/>Native solution"]
    PROOF -->|"native gap remains"| HDA["EVALUATE<br/>Houdini HDA"]
    HDA --> PROOF2["VERIFY<br/>Same proof contract"]
    PROOF2 -->|"PASS"| KEEP2["ADOPT<br/>Tool-backed solution"]
    PROOF2 -->|"FAIL"| GAP["CUSTOM<br/>Smallest remaining gap"]

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class ROAD,C owned;
    class REVIEW evidence;
    class A,B exec;
    class PROOF,PROOF2 evidence;
    class HDA tool;
    class KEEP,KEEP2 success;
    class GAP decision;

    linkStyle default stroke-width:2px;
```

Compare at minimum:

- cut/fill plausibility;
- road/terrain continuity and absence of black wedges/light leaks;
- preservation of canonical route and road profile authority;
- behavior at stacked/nearby hairpin branches;
- reproducibility and editability;
- authoring complexity;
- runtime/editor cost.

If a native Unreal path satisfies the contract, prefer it and delete or avoid bespoke machinery that no longer adds value.

If native Unreal cannot satisfy the contract, evaluate an established procedural route such as a bounded Houdini HDA **before** adding another layer of custom earthwork mathematics.

#### Biome / environment decision ladder

Do not build a separate YACS biome engine before exhausting the existing PCG ecosystem.

Biome decisions should start from real or derived spatial inputs such as:

- elevation;
- slope;
- aspect / sun exposure;
- land-cover or vegetation masks;
- forest type / density;
- distance from road;
- exclusion zones;
- season/weather state where relevant.

The preferred pattern is:

```mermaid
flowchart LR
    GIS["SOURCE<br/>GIS · DTM · land cover"] --> FEATURES["DERIVE<br/>Elevation · slope · aspect"]
    GIS --> MASKS["CLASSIFY<br/>Vegetation · rock · water"]
    FEATURES --> BIOME["WORLD DATA<br/>Biome / snow potential"]
    MASKS --> BIOME
    BIOME --> PCG["AUTHOR<br/>UE PCG / proven patterns"]
    CATALOG["YACS OWNED<br/>Semantic asset catalog"] --> PCG
    PCG --> OUTPUT["GENERATE<br/>Trees · grass · rocks · snow"]
    OUTPUT --> PROOF["VERIFY<br/>Visual + performance"]
    PROOF -->|"PASS"| ACCEPT["OUTPUT<br/>Accepted environment"]

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class GIS input;
    class FEATURES,MASKS,PCG,OUTPUT exec;
    class BIOME evidence;
    class CATALOG owned;
    class PROOF evidence;
    class ACCEPT success;

    linkStyle default stroke-width:2px;
```

Epic's PCG Biome Core/Sample should be inspected as a reference implementation for biome maps, generators, filters and composition. Because it is Experimental in UE 5.8, adopting it as a hard runtime/editor dependency requires a separate bounded evaluation. Its patterns may be reused without requiring YACS to depend on the plugin itself.

The same principle applies to snow: first represent *where snow may accumulate* as terrain/material/environment data; only use custom PCG or meshes for details that actually need geometry.

### 3.4 Legacy prototype-world retirement boundary

`AStage3PrototypeTerrainActor` and the HISM-heavy prototype-world presentation in `L_CyclingTest` are now **frozen legacy regression scaffolding**, not a second production world architecture.

Rules:

- do not add new terrain, road, biome, asset-pipeline or visual features to the prototype actor;
- new M3 world work must use the real-data Landscape / SP638 / PCG architecture defined by this Bible;
- legacy code may receive only the smallest compatibility or regression-proof fix needed to keep an already-required proof valid;
- no new subsystem may depend on `AStage3PrototypeTerrainActor`;
- removal is allowed only after the M3 production world replacement demonstrates equivalent route continuity, fresh-load/save-reopen behavior, rider-camera acceptance, required performance evidence and exact-SHA technical proof;
- deletion/cleanup may be a separate housekeeping change after that parity evidence exists; historical proof artifacts and workflow names remain preserved for traceability.

This freezes the old path without deleting a regression oracle before the replacement has earned it.

---

## 4. Canonical world-building pipeline

Every new YACS route/world follows this order.

```mermaid
flowchart LR
    SRC["SOURCE<br/>Verified real data"] --> GIS["PREPARE<br/>Metric GIS"]
    GIS --> LAND["AUTHOR<br/>Macro Landscape"]
    LAND --> LAYERS["AUTHOR<br/>Edit Layers"]
    LAYERS --> ROAD["AUTHOR<br/>Road + earthworks"]
    ROAD --> MESO["AUTHOR<br/>Cliffs · retaining · meso"]
    MESO --> MAT["SHADE<br/>Landscape materials"]
    MAT --> PCG["POPULATE<br/>PCG environment"]
    PCG --> BLEND["BLEND<br/>RVT if justified"]
    BLEND --> ATM["LIGHT<br/>Atmosphere · weather"]
    ATM --> PERF["SCALE<br/>Partition · HLOD · culling"]
    PERF --> PROOF["VERIFY<br/>Visual + technical proof"]
    PROOF -->|"PASS"| DONE["OUTPUT<br/>Accepted world slice"]
    PROOF -->|"FAIL"| FIX["FAIL CLOSED<br/>Fix owning layer"]
    FIX -.-> ROAD

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class SRC input;
    class GIS,LAND,LAYERS,ROAD,MESO,MAT,PCG,BLEND,ATM,PERF exec;
    class PROOF evidence;
    class DONE success;
    class FIX danger;

    linkStyle default stroke-width:2px;
```

Changing the order requires an explicit architecture decision.

---

## 5. Terrain foundation

### 5.1 Source rules

For a real-world YACS route:

1. prefer official/licensed DTM or DEM;
2. record provenance and license;
3. verify CRS, axis order, vertical interpretation and NoData;
4. reproject to an appropriate metric CRS before metric sampling;
5. preserve the original source package and hash;
6. produce deterministic derived inputs.

Do not treat geographic degrees as metres.

Do not claim a Landscape is higher fidelity merely because it has more vertices than the source raster.

### 5.2 Landscape is macro terrain

Landscape is the macro continuity representation, not a requirement that every
rider-visible centimetre of ground be owned by the heightfield. A bounded
native-DTM-derived near-field surface may own rider-close ground when a proof
shows that Landscape resolution/topology is visually insufficient. In that case,
ownership must be exclusive inside the patch and transition deterministically
back to the macro Landscape.

Landscape represents:

- valleys;
- slopes;
- ridgelines;
- broad road surroundings;
- large terrain continuity.

Landscape is **not** responsible for:

- overhangs;
- vertical rock faces;
- undercuts;
- detailed retaining structures;
- every roadside boulder;
- high-frequency geological detail.

Those belong to meshes and material/PCG layers.

---

## 6. Landscape Edit Layers contract

Worlds intended for production must use non-destructive Landscape Edit Layers unless a documented engine limitation blocks them.

Recommended logical layers:

| Layer | Purpose |
|---|---|
| `Base_DTM` | imported canonical macro terrain; normally not hand-edited |
| `Road_Earthworks` | spline-driven road cut/fill and shoulder tie-in |
| `Local_Corrections` | small bounded visual corrections with documented reason |
| `Water_or_Special` | only when a later feature actually requires it |

Rules:

- `Base_DTM` remains recoverable and inspectable.
- Road work must not destructively bake itself into the only terrain source.
- Manual corrections must be bounded and explainable.
- Do not use manual sculpting to hide a systemic road pipeline error.
- If a layer is generated, its inputs must be reproducible.

This is the default YACS answer to "how do people on YouTube avoid destroying their whole Landscape while building roads?"

---

## 7. Road architecture

The road has three separate concepts.

### Rider-camera direction is route-local

The terrain diagnostic keeps its selected camera station, XY and 1.6 m eye
height fixed. Camera orientation uses the forward tangent at that same station,
not a chord to a point far beyond a hairpin. A route-ahead point can already be
behind the rider in world space; such a view is not forward-riding evidence.
Record the old target and its angle to the local tangent in `camera_frame` so
the change remains auditable. This changes proof-camera orientation only; it
must not lift/reposition the camera to hide geometry or change the established
PCGEx road, earthworks, source terrain or simulation. Historical same-pose
captures remain comparison evidence, not deleted or reclassified as accepted.
A forward camera still requires review for real road/terrain penetration,
exclusive surface ownership, fresh loading and representative locations.

### Bounded transient-edit isolation

M3 #98 at `bb15df0003c7ad22025844f3ca8b8e93d42a9fca` completed the forward-camera
experiment. Native spline data measured the old look-ahead chord at 135.616 degrees
from forward. B now reveals the road and severe adjacent walls; E partly covers
those with its legacy collision-derived skin. Neither image is accepted geometry.
Camera correctness did not cure surface ownership. Do not tune the established
PCGEx alignment or hide the exposed walls with the skin.

Keep A/B/C/D/E/C3 unchanged and optionally add F/G at the same pose, material,
height-mip readiness, prepared inputs and corridor hash:

| Control | Additional transient spline edit | Corridor meshes | Local skin |
|---|---|---|---|
| A | off | off | off |
| F | on | off | off |
| G | off | on | off |
| B | on | on | off |

All four keep the persisted map and its original edit layers; `off` means not
executing the additional `editor_apply_spline` in this capture, not clearing
existing `Road_Earthworks`. F can attribute a regression to that operation; it
cannot by itself distinguish layer blending, geometry or resource-update causes.
G tests corridor visibility against the persisted terrain without the extra edit.
No camera repositioning, terrain smoothing or parameter tuning is part of this
isolation. F/G are evidence controls, never substitute production ground owners.
They require explicit `include_surface_isolation=true` in a manual M3 dispatch;
the normal broker still requests the six baseline captures. No additional proof
runs on ordinary pushes. Technical receipts record whether F/G were requested.

A also captures a second control with only `Base_DTM` visible, using the same
camera, lighting, FOV and resource-readiness path. It temporarily hides
`Road_Earthworks`, restores both original visibility flags, and never saves the
map. The original A capture remains the combined persisted Landscape. This pair
isolates persisted layer contribution; it does not establish an accepted repair
or prove a particular blend/transform defect without reviewing the evidence.
H carries the pair's exact-SHA metadata and hash-verified PNG payloads in its
existing compact artifact (bounded to 20 MB of raw comparison images). A
standalone H without A reports the comparison unavailable. The original H
acceptance gate remains unchanged.

### 7.1 Canonical alignment

The line saying **where the road is**.

For Passo Giau this comes from verified SP638/GIS route geometry plus the canonical route contract.

Never derive the canonical road XY from Landscape vertices.

### 7.2 Earthworks corridor

The terrain adaptation around the road:

- cut into uphill slopes;
- fill or embankment on downhill sides;
- shoulder;
- ditch / verge where required;
- soft transition into untouched macro terrain.

This belongs primarily to the `Road_Earthworks` Landscape Edit Layer. The first implementation choice should be a native Landscape Spline / spline edit-layer or Landscape Patch workflow when it satisfies the corridor contract. Use helper meshes where a heightfield is the wrong representation. Extend the custom YACS cut/fill solver only for a demonstrated gap that survives the tools-first comparison in section 3.1.

### 7.3 Final road mesh

The actual visible asphalt:

- width;
- longitudinal profile;
- crossfall/camber;
- banking transition;
- shoulder edge;
- markings;
- surface material.

The road mesh is generated independently from the Landscape grid.

The road presentation may use real cross-section evidence, but noisy LiDAR samples must be regularized before they become a road surface. Dense mesh stations are not automatically independent survey observations.

### 7.4 Full-area real-road network target

**Owner-approved destination, 2026-10-01; requirement record: Issue #295.** [Product Requirements section 3.1](PRODUCT_REQUIREMENTS.md#31-docelowo-wszystkie-rzeczywiste-drogi-obszaru) requires every real road within the project's Passo Giau area, not just SP638. SP638 is the first validated producer/consumer slice, not the final world inventory. This section records requirements, not an implemented network subsystem or a new prerequisite for terrain-recovery PR #294.

Coverage and source evidence must preserve:

- one explicit, versioned world area of interest, with CRS, boundary and reference data date; do not silently shrink it to a rider corridor or screenshot;
- all real road classes where present, including minor/access/service and unpaved roads; retain cycleways and paths as separately classified features rather than silently dropping them or pretending they are asphalt;
- source identities, geometry, surface/access evidence and unresolved attributes; retain immutable source packages and complete the existing license/provenance review before importing a new dataset;
- actual junction connectivity, dead ends and boundary continuations; a bridge, tunnel or nearby hairpin must not become a junction merely because lines overlap in XY;
- a coverage ledger mapping source segments to represented, pending, uncertain or verified-not-a-road states, with counts and length by class and explicit discrepancy review. Pending/missing roads are not completed coverage. A complete import from one dataset alone is not proof that all real roads have been captured.

World coverage is distinct from playable-route activation. Do not reduce the final network to decorative lines, but activate riding only through the established route/physics contracts and validated topology, surface and access semantics. Roads not suitable or permitted for riding may still require faithful world representation. No presentation mesh, PCGEx output or sampled Landscape becomes simulation authority.

Reuse the established pinned, authoring-only PCGEx road/corridor path and Epic-native capabilities under the tools-first gate. Embark remains production-pattern evidence, not a claim that Embark uses PCGEx. Neither Houdini nor Gaea is a prerequisite for this target. Prove a second real road and junction through the existing producer -> derived data -> consumer -> regeneration gate before generalizing; do not build a universal schema in anticipation of the full network.

Expansion must preserve independent alignment, non-destructive Road_Earthworks, route-local handling of vertically separated roads and one rider-close ground owner. An accepted source edit must regenerate only affected road/earthwork/PCG scope and justified dependencies, with source/config fingerprints and unrelated outputs remaining reusable. Full-area coverage does not require full-detail residency everywhere: spatial streaming and quality budgets must preserve visible roads while respecting the measured 1080p/60 target.

Before claiming the expanded network accepted, require a reviewed full-area coverage ledger and discrepancy resolution, true-junction/grade-separation checks, representative rider-camera proofs (including normal slopes and major earthworks), fresh-load/regeneration evidence and applicable exact-SHA performance proof. A good SP638 hairpin or green build cannot substitute for whole-area coverage.

### 7.5 Mixed-surface riding destination

Owner approval of 2026-10-01 (Issue #297) extends the network destination to rideable asphalt/gravel combinations; [Product Requirements section 3.2](PRODUCT_REQUIREMENTS.md#32-jazda-mieszana-szosa-i-gravel) owns this scope. This is not an additional closure requirement for terrain PR #294.

Preserve surface evidence separately from road class, roughness/obstacles, width, topology and bicycle access. Distinguish asphalt, compacted aggregate, loose gravel, earth and unknown at inventory/authoring boundaries without treating them as calibrated physics presets. Unknown or conflicting inputs remain unresolved; neither a path label nor the appearance of a mesh establishes safe/legal ride activation. Review actual source licenses before any new dataset enters the project.

Reuse the pinned authoring-only PCGEx corridor and existing route/physics boundaries. Surface-aware presentation must not manufacture asphalt widths, move road XY, merge grade-separated branches or layer competing ground surfaces to hide seams. No separate gravel generator, global streaming disable, arbitrary speed penalty or new dependency is authorized by this requirement.

The first real mixed-route proof must establish source-backed surface transitions and true road connections, continuous rider state, explicit rolling/grip configuration, neutral rider-camera geometry, regeneration and relevant performance. Keep source coverage, physics calibration, technical tests and visual acceptance distinct. A synthetic reference example cannot stand in for these proofs.

The current support exercise is `physics_reference/examples/run_mixed_surface.py`, tested through the existing reference-test discovery. It composes RoadPhysicsProfile, SurfaceGripPolicy, Environment and the unchanged step_simulation. Fixture coefficients are explicitly synthetic. Surface selection occurs at current S/D before each fixed substep; batching cannot alter the result. The last substep may pass the test endpoint slightly without resetting distance or velocity. The straight-line exercise reports grip but does not execute a corner/braking solver or prove UE/runtime parity. Detailed tyre/roughness physics and actual network activation remain separate work after the applicable foundation gate.

---

### Bounded scout and focused traversal evidence

Owner-approved Issue #293 tooling adds an opt-in light traversal followed by a
single +/-2-second detail window. The operational contract and limits live in
[CI Validation Tiers](CI_VALIDATION_TIERS.md#bounded-traversal-diagnostics-issue-293).
Reuse the current exact-SHA PCGEx scene, native route-local camera and transient
height-mip preparation. The camera is not raised or moved to avoid faults.
Collision-derived suspects only locate candidate stations; missing signals do
not pass the world. Inspect both clips and original PNGs before attributing a
render defect. The light/focus receipt is NOT the full A-E/C3 acceptance receipt.
These settled camera samples do not measure live gameplay FPS, streaming hitches
or the full road network. Normal rider-camera, surface-owner, representative
location and performance gates still apply.

## 8. The road/terrain rule that prevents black wedges

Avoid designing two unrelated surfaces that must meet perfectly along one mathematical edge.

Bad model:

```text
terrain mesh edge  == exact seam ==  road/earthwork mesh edge
```

Preferred model:

```text
macro Landscape
    \
     \ controlled earthwork falloff
      \_________________
         prepared corridor
         [road mesh above/within it]
```

The terrain should continue underneath / into a controlled corridor, while the road mesh owns the visible drivable surface.

Use deliberate overlap, burial or falloff where visually appropriate. Do not rely on zero-width coplanar seams.

At hairpins, cross-section construction must understand that nearby road branches can be geometrically close while belonging to different elevations. Corridor logic must be route-local, not "nearest arbitrary road point wins."

---

## 9. Cut, fill, cliffs and retaining geometry

### Use Landscape for

- smooth cuts;
- broad embankments;
- shoulders;
- gentle ditching;
- transitions over several metres.

### Use dedicated meshes for

- near-vertical rock;
- undercuts;
- sharp retaining walls;
- exposed layered cliffs;
- complex drainage structures;
- geometry inspected from rider-close cameras where the heightfield grid becomes visible.

Do not globally blur a good DTM to hide a local cliff problem.

Do not scatter cliff meshes over the whole map. Place meso geometry where slope, visibility and composition justify it.

---

## 10. Landscape materials

A production Landscape Material should be rule-driven first and hand-painted second.

Useful inputs include:

- slope;
- elevation;
- macro masks;
- biome;
- road-distance masks;
- wetness / weather state later.

Typical classes:

- meadow / grass;
- forest ground;
- exposed dirt;
- scree;
- rock;
- high-Alpine sparse ground.

Materials cannot fix incorrect geometry. If a silhouette is wrong, fix geometry first.

---

## 11. PCG vegetation and rocks

PCG is the default for repeated world content.

PCG rules should be based on explicit inputs such as:

- elevation band;
- slope;
- biome mask;
- distance from road;
- visibility/composition zone;
- deterministic seed;
- exclusion areas.

Minimum road rule:

> mass vegetation must respect a deterministic protected road corridor.

Use manual placement for hero objects and composition exceptions, not for thousands of repeated trees.

Generated PCG output must remain reproducible from its graph, inputs and seed.

Do not create a parallel custom biome engine merely to classify where these graphs should run. Prefer GIS/terrain-derived masks plus existing UE PCG capabilities and proven biome patterns; add YACS-specific code only for the remaining integration gap.

---

## 12. RVT and visual blending

Runtime Virtual Texturing can help blend:

- road shoulder into terrain;
- cliff/rock base into Landscape;
- decal-like surface variation;
- material information between Landscape and meshes.

RVT is **not**:

- a replacement for road earthworks;
- a geometry repair tool;
- a reason to leave floating meshes;
- mandatory before a visible blending problem exists.

YACS uses RVT when a bounded visual problem justifies it.

---

## 13. Nanite

Nanite is a rendering technology, not a data-resolution generator.

Use it for suitable static meshes and evaluate Landscape Nanite only by measurement.

Never say:

> "Nanite will turn the DTM into more detailed terrain."

It will not recover elevation information that the source never contained.

---

## 14. World Partition, HLOD and streaming

Large worlds must be designed so the entire route does not remain equally expensive.

Use:

- World Partition for spatial streaming;
- HLOD where it reduces distant-world cost;
- foliage/PCG cull distances;
- instancing;
- sensible texture and material budgets;
- bounded high-detail zones near the rider.

The rider camera defines what deserves expensive detail.

---

## 15. Spatial quality rings

World detail should increase toward the rider and route.

A useful model:

**Macro**
- mountain mass;
- skyline;
- valley form;
- broad materials.

**Meso**
- road cuts;
- cliff masses;
- scree;
- tree groups;
- retaining elements.

**Micro**
- roadside grass;
- gravel;
- stones;
- surface normals;
- markings.

Do not spend micro-detail budget on mountains the rider only sees kilometres away.

---

## 16. Asset policy

Before an external asset enters YACS:

1. verify source and license;
2. record provenance;
3. identify exact use;
4. import only what is required;
5. check scale, material count, collision, LOD/Nanite suitability and texture cost;
6. measure repeated-world performance where relevant.

Preferred order if paid assets become necessary:

1. coherent Alpine surface/material foundation;
2. vegetation;
3. rocks/cliffs;
4. road/roadside props;
5. Alpine buildings;
6. weather/audio polish.

Do not buy a pack merely because a tutorial used it.

---

## 17. Lighting, atmosphere and weather

Lighting comes after geometry and material readability.

Order:

1. readable terrain silhouettes;
2. material separation;
3. sky/sun/fog baseline;
4. only then dynamic weather polish.

A dramatic sunset must not be used to hide broken road/terrain geometry.

Weather systems belong to later product milestones, but world architecture must not make them impossible.

---

## 18. Performance contract

Target remains 1920x1080 / 60 FPS on the reference PC defined in `AGENTS.md`.

Performance rules:

- measure; do not guess;
- optimize after identifying the limiting domain;
- prefer deterministic A/B evidence;
- separate visual acceptance from performance acceptance;
- a green build does not prove a good world;
- a pretty screenshot does not prove a performant world.

Heavy proof cadence is defined in `CI_VALIDATION_TIERS.md`.

---

## 19. Visual acceptance

World success is judged from the rider camera.

Reject visible:

- Landscape component/grid structure;
- staircase / Minecraft-like terrain;
- floating road;
- severe road-terrain penetration;
- black wedges or light leaks caused by broken seams;
- obviously repeated vegetation patterns;
- cliffs represented as implausible terraced heightfields;
- road crossfall that looks physically absurd;
- scenery clipping through the protected road corridor.

Top-down editor views are diagnostic, not final acceptance.

---

## 20. Passo Giau production recipe

For the current YACS world:

```mermaid
flowchart TB
    DTM["SOURCE<br/>MASE PST LiDAR / DTM"] --> VERIFYDTM["VERIFY<br/>Hash · CRS · provenance"]
    VERIFYDTM --> GIS["PREPARE<br/>EPSG:32632"]
    GIS --> BASE["AUTHOR<br/>Base_DTM Edit Layer"]

    SP638["SOURCE<br/>Verified SP638"] --> ROUTE["YACS AUTHORITY<br/>Canonical route-local data"]
    ROUTE --> AUDIT["AUDIT<br/>Earthworks tool"]

    AUDIT --> SPLINE["UE NATIVE<br/>Landscape Spline"]
    AUDIT --> PATCH["UE NATIVE<br/>Landscape Patch"]
    AUDIT -.-> CUSTOM["YACS OWNED<br/>Existing cut/fill"]
    SPLINE --> CORRIDOR["AUTHOR<br/>Road_Earthworks"]
    PATCH --> CORRIDOR
    CUSTOM --> CORRIDOR

    CORRIDOR --> HAIRPIN["VERIFY<br/>Difficult hairpin"]
    HAIRPIN -->|"native gap"| HDA["FALLBACK<br/>Houdini HDA"]
    HDA --> CORRIDOR
    HAIRPIN -->|"PASS"| ROAD["AUTHOR<br/>Final road mesh"]
    ROUTE --> ROAD

    BASE --> WORLD["COMPOSE<br/>Landscape world"]
    CORRIDOR --> WORLD
    ROAD --> WORLD

    WORLD --> MESO["DETAIL<br/>Cliffs · retaining · scree"]
    WORLD --> MASKS["CLASSIFY<br/>Slope · elevation · biome"]
    MASKS --> PCG["POPULATE<br/>Forest · valley · high Alpine"]
    MESO --> FINAL["ASSEMBLE<br/>World presentation"]
    PCG --> FINAL
    ROAD --> FINAL

    FINAL --> PERF["VERIFY<br/>World Partition · LOD · 60 FPS"]
    FINAL --> VIS["VERIFY<br/>Rider-camera visual"]
    PERF --> GATE["ACCEPT<br/>Exact-SHA world slice"]
    VIS --> GATE

    classDef input fill:#303846,stroke:#8ea1b8,color:#f7f9fc,stroke-width:2px;
    classDef exec fill:#123f73,stroke:#49a2ff,color:#ffffff,stroke-width:3px;
    classDef tool fill:#4b2f69,stroke:#b77cff,color:#ffffff,stroke-width:2px;
    classDef decision fill:#69470e,stroke:#f0a72f,color:#ffffff,stroke-width:3px;
    classDef success fill:#1f5736,stroke:#63d889,color:#ffffff,stroke-width:3px;
    classDef danger fill:#6b2429,stroke:#ff6b73,color:#ffffff,stroke-width:3px;
    classDef owned fill:#34373d,stroke:#9da4ae,color:#ffffff,stroke-width:2px;
    classDef evidence fill:#164d5c,stroke:#5bd6ef,color:#ffffff,stroke-width:2px;

    class DTM,SP638 input;
    class ROUTE,CUSTOM owned;
    class VERIFYDTM,HAIRPIN,PERF,VIS evidence;
    class GIS,BASE,CORRIDOR,ROAD,WORLD,MESO,MASKS,PCG,FINAL exec;
    class AUDIT decision;
    class SPLINE,PATCH,HDA tool;
    class GATE success;

    linkStyle default stroke-width:2px;
```

The road may request bounded local terrain adaptation. It may not rewrite route/physics authority.

---

## 21. Forbidden shortcuts

Do not:

- snap canonical road XY to Landscape vertices;
- interpret a denser resampled Landscape as new source detail;
- destructively sculpt the only copy of imported terrain for every road revision;
- solve a local cliff problem with global terrain blur;
- use material tricks to hide wrong silhouettes;
- make physics depend on render mesh noise;
- use a zero-width seam between independently generated surfaces as the primary road/terrain joining strategy;
- place thousands of repeated assets manually when PCG can express the rule;
- buy a plugin before identifying the problem it solves;
- build a custom world-authoring subsystem before completing the tools-first audit;
- generalize a universal world-data schema before one complete producer → derived data → consumer → regeneration path is proven;
- rebuild the whole world when a bounded source change can be represented by a bounded invalidation contract;
- treat a tutorial or tech demo as if it were shipped-product evidence;
- choose an architecture only because another studio used it without proving it against YACS inputs;
- keep bespoke machinery merely because it already exists when a simpler validated native/tool-based path replaces it;
- call a technical proof "visual acceptance";
- create a new planning identifier like `Stage 3G R4.1B.4.3.2`.

---

## 22. Work-item naming

World architecture is stable; tasks are not architecture levels.

Use:

- product milestone: `M3`;
- named workstream: `Terrain`, `Road & Earthworks`, `Materials`, `Biomes`, `Proof`, `Tooling`;
- concrete work: GitHub Issue number and human-readable title.

Example:

```text
M3 / Road & Earthworks / #253
```

Do **not** create recursive roadmap numbering for individual experiments.

Legacy Stage/R/B identifiers remain searchable historical aliases only.

---

## 23. Definition of Done for a world slice

A route slice is acceptable when:

- canonical route/physics authority is unchanged unless intentionally revised;
- source provenance is recorded;
- Landscape base can be regenerated;
- road earthworks are on a non-destructive layer or equivalent reproducible path;
- road mesh and terrain form a believable corridor from rider view;
- cliffs use the correct representation;
- materials and biome are coherent;
- mass placement respects route exclusion;
- no obvious grid/seam/floating-road artifact remains;
- performance meets the relevant budget;
- exact-SHA proof exists where required;
- human visual acceptance exists for changes whose success depends on image quality;
- when a reusable generation subsystem is introduced or materially changed, a local source edit has demonstrated deterministic bounded downstream regeneration before the abstraction is generalized.

---

## 24. Learning references

### Production architecture evidence

For detailed copyright-safe reconstructions of the public Far Cry 5 and THE FINALS pipelines, including data-flow graphs and direct YACS mappings, see [`PRODUCTION_WORLD_ARCHITECTURE_REFERENCES.md`](PRODUCTION_WORLD_ARCHITECTURE_REFERENCES.md).

- Ubisoft / SideFX — Far Cry 5 procedural world generation:  
  https://www.sidefx.com/learn/talks/procedural-world-generation-far-cry-5/
- Embark Studios / SideFX — procedural buildings of THE FINALS:  
  https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/
- Epic Games — UE 5.8 City Sample PCG update:  
  https://www.unrealengine.com/learning/city-sample-gets-a-major-update-with-pcg-and-unreal-mcp-workflows
- SideFX — Project Pegasus tech demo:  
  https://www.sidefx.com/pegasus/

### Official tool references

Official Unreal Engine references are architecture references:

- Epic Games — Landscape Splines:  
  https://dev.epicgames.com/documentation/unreal-engine/landscape-splines-in-unreal-engine
- Epic Games — Landscape Edit Layers:  
  https://dev.epicgames.com/documentation/unreal-engine/landscape-edit-layers-in-unreal-engine
- Epic Games — Landscape Technical Guide:  
  https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine
- Epic Games — Importing and Exporting Landscape Heightmaps:  
  https://dev.epicgames.com/documentation/unreal-engine/importing-and-exporting-landscape-heightmaps-in-unreal-engine
- Epic Games — Runtime Virtual Texturing:  
  https://dev.epicgames.com/documentation/unreal-engine/runtime-virtual-texturing-in-unreal-engine
- Epic Games — World Partition:  
  https://dev.epicgames.com/documentation/unreal-engine/world-partition-in-unreal-engine
- Epic Games — Nanite with Landscapes:  
  https://dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine
- Epic Games — PCG framework:  
  https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-framework-in-unreal-engine
- Epic Games — Landscape Patch System:  
  https://dev.epicgames.com/documentation/unreal-engine/landscape-patch-system
- Epic Games — PCG Biome Core and Sample:  
  https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-in-unreal-engine
- SideFX — Houdini Engine for Unreal Landscapes:  
  https://www.sidefx.com/docs/houdini/unreal/landscape/index.html

Learning/tutorial references that illustrate the workflow:

- UNF Games — long-form UE5 Landscape workflow:  
  https://www.youtube.com/watch?v=V54kqpy1Q-Q
- Aziel Arts — Landscape Splines / road / PCG workflow:  
  https://www.youtube.com/watch?v=_NEybBdACCo
- Unreal Sensei — Landscape material / environment workflow:  
  https://www.youtube.com/watch?v=5ju7wyvZGBI
- Smart Poly — Landscape road spline / Edit Layers concepts:  
  https://www.youtube.com/watch?v=8WIWuybAKj4

Tutorials are examples, not source of truth. When tutorial advice conflicts with current Epic documentation or YACS contracts, the official/current contract wins.

---

## 25. One-page cheat sheet

When confused, ask in this order:

1. **What is truth?** DTM? route profile? verified road GIS?
2. **What is presentation?** Landscape, road mesh, cliffs, vegetation?
3. **What is the evidence tier?** Shipped product, production case, sample, demo, tutorial or hypothesis?
4. **Has one complete producer → derived data → consumer → regeneration path been proven before I generalize the model?**
5. **Have I completed the tools-first audit before writing custom world-building code?**
6. **Am I editing non-destructively?**
7. **Should this be Landscape or a mesh?**
8. **Should this be generated by spline/PCG instead of hand-built?**
9. **Am I trying to fix geometry with a material?**
10. **Can I see the problem from the rider camera?**
11. **Did I measure performance?**
12. **Can the result be reproduced from source inputs?**

If those answers are clear, world building is usually straightforward.
