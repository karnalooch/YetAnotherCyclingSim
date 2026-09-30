# YACS World Authoring Library

> **Role after the 2026-09-29 documentation reset:** this document is the reusable **implementation library/catalog** for world authoring. The authoritative methodology for how YACS builds terrain, roads, earthworks, materials, PCG and world streaming is [`WORLD_BUILDING_BIBLE.md`](WORLD_BUILDING_BIBLE.md), including its **tools-first authoring policy**. This library implements bounded YACS integration; it must not become a parallel custom world-generation framework. Legacy Stage 3G/R4.x labels in this file are historical traceability, not new roadmap hierarchy.


**Status:** M3 world-authoring foundation; legacy Stage 3G implementation identifiers are retained for traceability  
**Tracking:** #230  
**Generated-content sandbox:** `/Game/Generated/YACS/**`

## 1. Purpose

The YACS World Authoring Library turns bounded environment intent into a
deterministic, reviewable world-authoring plan.

The intended operator experience is deliberately semantic:

```text
"make a natural 10x10 m conifer grove beside the road"
                         |
                         v
              repo-owned intent preset
                         |
                         v
        semantic asset catalog / discovery
                         |
             +-----------+-----------+
             |                       |
             v                       v
     qualified local asset     approved provider API
                               discovery / download
             |                       |
             +-----------+-----------+
                         |
                         v
              provenance + cache plan
                         |
                         v
                 Scene Composer
                         |
             +-----------+-----------+
             |                       |
             v                       v
     transient proof backend     existing YACS PCG
                                graph contract/backend
             |                       |
             +-----------+-----------+
                         |
                         v
                screenshot + JSON proof
```

Natural-language interpretation stays outside Unreal. Unreal receives only
repo-reviewed presets and selection plans. Free-form Python, shell, console
commands, arbitrary URLs and arbitrary asset destinations are not part of this
contract.

### Tools-first integration boundary

The World Authoring Library is a **thin integration layer**, not permission to
reimplement capabilities already supplied by Unreal Engine, Epic reference
content or an approved mature authoring tool.

Before adding a new generator/backend here:

1. follow the Embark-first tools audit in `WORLD_BUILDING_BIBLE.md`;
2. use the closest public Embark pattern to shape boundaries and data flow, without treating it as an automatic dependency;
3. prefer an existing qualified Epic-native UE/PCG/Landscape path when it satisfies the contract;
4. evaluate proven OSS/DCC tooling before implementing a new backend;
5. use this library to translate YACS semantic intent, provenance and deterministic configuration into the chosen backend;
6. add custom layout/generation logic only for a demonstrated YACS-specific gap;
7. preserve the ability to replace a backend without changing canonical route, physics or source-data authority.

In particular:

- road-earthwork generation does not belong here unless it is a bounded adapter
  around the chosen Landscape/authoring tool;
- biome placement should consume terrain/GIS-derived masks and proven PCG
  patterns before any bespoke biome engine is introduced;
- asset discovery/selection remains YACS-owned because provenance, license,
  qualification and performance status are project policy rather than renderer
  behavior.

## 2. Existing systems reused

This is not a second Stage 3G asset pipeline.

The library reuses:

- `scripts/assets/download_stage3g_assets.py` for Poly Haven file resolution,
  size/MD5 verification and bounded source downloads;
- the existing ignored `ExternalAssets/` source-cache policy;
- the validated Stage 3G imported assets;
- `/Game/YACS/WorldGen/PCG/PCG_Forest`;
- `/Game/YACS/WorldGen/PCG/PCG_RouteExclusion`;
- `/Game/YACS/WorldGen/PCG/PCG_Valley`;
- `/Game/YACS/WorldGen/PCG/PCG_HighAlpine`;
- the Stage 3G route/physics separation and WorldSpec architecture.

The first accepted mass-forest conifer remains
`SM_Stage3G_FirSaplingMedium`. A live provider result does not replace a
qualified Unreal asset merely because it scores highly.

## 3. Semantic asset catalog

`worldgen/assets/catalog.json` records project knowledge about assets rather
than only filenames.

Each entry can describe:

- semantic roles such as `mass_conifer`, `hero_conifer`,
  `roadside_boulder` or `forest_ground`;
- lifecycle status;
- exact provider/source ID;
- qualified Unreal asset path when one exists;
- authoring capabilities such as PCG mass-scatter suitability;
- known cost/performance restrictions.

Automatic authoring prefers already-approved catalog entries. This is
intentional: provider discovery is a candidate-discovery mechanism, not an
automatic visual/performance acceptance mechanism.

## 4. Provider policy

Phase 1 supports one automatic provider: Poly Haven.

Automatic acquisition is fail-closed:

- provider must be declared in the catalog;
- the preset must explicitly allow that provider;
- the provider license must be explicitly allowed by the preset;
- provider asset IDs must satisfy a safe ID grammar;
- source downloads must use HTTPS;
- the download host must match the provider allowlist;
- known download bytes must stay under the preset cap;
- the low-level downloader verifies provider size/MD5 metadata;
- downloaded source remains under ignored `ExternalAssets/`.

The live API may be used to discover candidates by type, name, tags, category,
description, polycount and LOD metadata. Ranking is deterministic.

The first policy intentionally allows only Poly Haven CC0 assets. Fab,
Marketplace and arbitrary website scraping are outside this automation
contract.

## 5. Presets

Presets live under `worldgen/presets/`.

The first preset is:

```text
alpine_roadside_grove_v1
```

It describes a 10 x 10 m natural conifer patch with:

- deterministic seed;
- bounded tree-count range;
- natural irregularity;
- road-clearance intent;
- a view-corridor intent;
- semantic asset slots;
- provider/license/download limits;
- existing PCG graph references.

The preset describes intent. It does not contain executable shell/Python text.

## 6. Deterministic layout

`scripts/worldgen/yacs_scene_layout.py` owns engine-independent layout
planning.

The first forest planner provides:

- deterministic seeded output;
- clustered rather than uniform-random placement;
- configurable patch dimensions;
- minimum tree spacing;
- edge margins;
- bounded scale variation;
- yaw variation;
- rectangular exclusion regions for view/subject corridors.

The pure planner is unit-tested without Unreal.

## 7. Asset selection and acquisition

`scripts/assets/yacs_asset_library.py` resolves a preset.

Selection order:

1. find a compatible approved semantic asset in the YACS catalog;
2. only when no acceptable catalog asset exists and the preset allows automatic
   acquisition, query the approved provider;
3. rank compatible provider candidates deterministically;
4. reject explicit exclusions and candidates over configured cost limits;
5. resolve exact source files through the existing checksum-aware downloader;
6. write a machine-readable selection plan.

A typical proof command is:

```powershell
python scripts/assets/yacs_asset_library.py `
  --preset worldgen/presets/alpine_roadside_grove_v1.json `
  --live-discovery `
  --download `
  --output Saved/RuntimeProof/world_asset_selection_plan.json
```

A downloaded candidate is not automatically usable in a scene. It must still
pass import, scale/pivot/material, performance and visual qualification before
receiving an approved catalog entry with a qualified Unreal asset path.

## 8. Scene Composer

`scripts/ue/yacs_scene_composer.py` is the Unreal adapter.

Its responsibilities are:

- validate generated-content paths;
- load only qualified selections for visual authoring;
- validate the existing PCG graph contract;
- translate deterministic layout points into an Unreal backend;
- emit proof data describing assets, placement and persistence state.

The first vertical slice uses a **transient StaticMesh proof backend**. This
keeps the initial Passo Giau experiment easy to inspect and guarantees that the
map is not saved.

This backend is not the final scalability mechanism. Existing YACS PCG graphs
remain the intended mass-environment backend. A later bounded adapter will
instantiate/generate the requested local patch through PCG without changing
the semantic preset or selection API.

## 9. Persistent-import boundary

Persistent generated authoring may write only below:

```text
/Game/Generated/YACS/**
```

Existing validated source assets under
`/Game/Prototype/Environment/Stage3G/Imported/**` and the project PCG graphs
under `/Game/YACS/WorldGen/PCG/**` are read-only inputs to this library.

Route geometry, Road Physics Profile, simulation state, canonical route assets
and prototype maps are never world-authoring output.

## 10. Proof contract

The first vertical proof target is the bounded Passo Giau / SP638 hairpin
scene already used by #217/#230.

A successful proof must show:

- exact repo revision;
- deterministic preset ID and seed;
- approved selected asset identity;
- source-download URLs/checksums/cache status;
- 10 x 10 m forest patch;
- bounded tree count;
- existing PCG graph contract loads successfully;
- transient scene mutation only;
- no map save;
- 3840 x 2160 screenshot;
- clean tracked worktree after execution.

Human visual acceptance remains separate from technical PASS.

## 11. Growth path

The library can grow by adding semantic slots and composition presets rather
than one-off scripts.

Expected M3/M7 families include:

- conifer forest and treeline;
- meadow and ground cover;
- boulders, scree and cliff dressing;
- roadside props and barriers;
- alpine buildings and small settlements;
- view corridors and hero composition;
- biome/altitude/slope-aware placement;
- weather-compatible material variants.

New providers require a separate license/API/terms review and explicit catalog
policy. They are never enabled merely because an endpoint can technically be
scraped.

## 12. Methodology boundary

`docs/README.md` identifies `WORLD_BUILDING_BIBLE.md` as the authoritative
world-building methodology. This document may define reusable catalogs,
presets, selectors and adapters, but it must not override the Bible's decisions
about:

- truth versus presentation authority;
- tools-first evaluation;
- road/earthwork architecture;
- terrain and Landscape ownership;
- PCG/biome strategy;
- visual and performance acceptance.

If a reusable authoring implementation would require changing those rules,
update and review the Bible first rather than silently encoding a new
architecture here.

## 13. Documentation guard implementation

`docs/README.md` routes world-building work to
`WORLD_BUILDING_BIBLE.md`, and `scripts/ci/check_docs_index.py` is the
repository-local documentation guard required for documentation changes.

That single guard reports the four named checks required by `AGENTS.md`:

- **i18n** — UTF-8 documentation entrypoints are readable;
- **structure** — required headings, authority links and root routing are present;
- **links** — local documentation links resolve;
- **freshness** — every top-level Markdown document under `docs/` is indexed.

The main CI runs this contract in the `Classify changes` job. Reports must
state the result of each named check from that guard rather than describing
them as unavailable merely because they are implemented by one script.
