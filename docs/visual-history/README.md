# YACS Visual History

**Status:** active project standard  
**Version:** 1  
**Scope:** material visual changes to the YACS world, rider, camera and presentation layers

## Purpose

Visual History records whether a change that is supposed to be visible is **actually visible**.

It complements automated technical proof. A green build, Automation run, Map Check or LFS proof does not by itself prove that a visual milestone improved the scene.

Every material visual milestone should answer four questions:

1. What accepted state did we start from?
2. What does the current implementation actually render?
3. What state was finally accepted and merged?
4. Which roadmap item, commit, PR, CI run, assets and world-generation inputs produced the result?

## Canonical triptych

Every tracked capture uses:

`BEFORE | NOW | AFTER`

- **BEFORE** — the most recent `VISUAL_ACCEPTED` baseline for the same capture point.
- **NOW** — the current branch/commit under review.
- **AFTER** — the final accepted state. It remains `PENDING` until visual acceptance; it must never be populated by copying NOW.
- If a milestone is rejected visually, NOW remains preserved as evidence and AFTER stays pending until a later accepted revision.

The triptych is evidence, not decoration. Each panel must identify the exact revision that produced it.

## Stable capture points

Stage 3G keeps three stable primary cameras so visual progress remains comparable across releases:

| Capture ID | Sector | Route distance | Purpose |
|---|---|---:|---|
| `01-valley-1200m` | Valley / meadow | 1200 m | valley shape, ground, water, roadside dressing, depth |
| `02-forest-4900m` | Forest | 4900 m | forest density, tree quality, route clearance, canopy/readability |
| `03-high-alpine-8000m` | High Alpine | 8000 m | rock/scree massing, skyline, alpine ground and atmospheric depth |

Additional feature-specific captures may be added, but the three primary Stage 3G points remain stable.

## Folder layout

```text
docs/visual-history/
├── README.md
├── index.json
├── templates/
│   ├── manifest.template.json
│   └── summary.template.md
└── stage-3g/
    ├── R2-pcg-forest/
    │   ├── manifest.json
    │   └── summary.md
    └── R3-valley-high-alpine/
        ├── manifest.json
        ├── summary.md
        ├── before/
        ├── now/
        ├── after/
        └── captures/
```

Image directories may initially be absent while a milestone is in progress. Once a visual milestone is accepted, its required evidence images must be retained directly in this repository under the Visual History entry. CI artifacts are transient transport/evidence only and never satisfy durable Visual History storage by themselves.

## Visual History ID

Format:

```text
VH-<STAGE>-<VERSION>-<SEQUENCE>
```

Examples:

- `VH-3G-R2-001`
- `VH-3G-R3-001`
- `VH-6-R1-001`

## Required status dimensions

Technical and visual status are intentionally separate.

### technical_status

Allowed values:

- `WORKING`
- `CI_GREEN`
- `TECHNICAL_ACCEPTED`
- `MERGED`
- `SUPERSEDED`

### visual_status

Allowed values:

- `NOT_REVIEWED`
- `IN_REVIEW`
- `VISUAL_REJECTED`
- `VISUAL_ACCEPTED`
- `SUPERSEDED`

A milestone may therefore be technically green and visually rejected. This is a valid and important state.

## Required manifest data

Each entry records at least:

### Identity and roadmap
- Visual History ID;
- title;
- roadmap stage;
- roadmap slice/version;
- roadmap title or issue;
- creation and acceptance dates.

### Git / PR
- branch;
- source commit SHA;
- short SHA;
- baseline commit SHA;
- accepted commit SHA;
- merge commit SHA;
- PR number/title/status.

### CI / proof
- workflow name;
- workflow run ID and run number;
- proof artifact name;
- Automation result;
- Fresh Load result;
- Map Check errors/warnings;
- LFS fsck result;
- Visual Capture result.

### World-generation inputs
- generation seed;
- route-clearance width;
- PCG graphs;
- biome names;
- affected route ranges;
- density values;
- authoritative route source.

### Asset delta
- validated assets used;
- meshes/materials added;
- placeholders replaced or removed;
- important asset provenance references.

### Visual review
- whether a visible change was detected;
- technical acceptance;
- visual acceptance;
- reviewer summary;
- rejection reason when applicable;
- next step.

### Capture metadata
For every capture:
- capture ID and label;
- route distance;
- camera name/preset;
- resolution;
- BEFORE/NOW/AFTER revision;
- image paths;
- image hashes when available;
- optional pixel-diff metrics;
- panel status.

## HUD contract

The triptych image must be self-describing.

### Global header
- `YACS VISUAL HISTORY`;
- Visual History ID;
- roadmap stage/version/title.

### Per-panel HUD
- `BEFORE`, `NOW` or `AFTER`;
- branch;
- short commit SHA;
- roadmap stage/version;
- visual status;
- capture label and route distance;
- CI run number/ID;
- resolution;
- Automation status;
- Fresh Load status;
- Map Check result;
- Visual Capture status.

When AFTER does not yet exist, render a clear placeholder such as:

```text
AFTER
PENDING
Awaiting visual acceptance
```

## Optional performance evidence

The durable performance source of truth is [`../performance-history/README.md`](../performance-history/README.md). Visual History may cross-link a Performance History record for the same exact SHA.

When the same exact SHA has a YACS Performance Framework proof, a Visual History entry may include a compact **BEFORE / NOW performance delta** next to the visual evidence.

Recommended fields:
- Frame p95;
- Game p95 when relevant;
- Draw p95;
- RHI p95 when relevant;
- GPU p95;
- absolute delta in milliseconds;
- limiting timing domain;
- performance proof/run identifier;
- Performance History ID when one exists;
- FPS average / 1% low when relevant to R5;
- hitch or VRAM delta when the visual change materially affects them.

This performance block is contextual evidence only. Visual History automation must not convert timing improvements into a visual-acceptance decision.

## Definition of Done

A material visual milestone is not complete until:

- the implementation passes its normal technical gates;
- the Visual History manifest is complete;
- the required stable capture points exist as repository-retained image files under the Visual History entry;
- every repository-retained image has a SHA-256 recorded in the manifest or capture-hashes file;
- BEFORE/NOW/AFTER provenance is unambiguous;
- technical and visual decisions are recorded independently;
- the accepted state is linked to its PR/merge commit;
- rejected visual attempts remain traceable rather than being overwritten.

For Stage 3G, required primary captures are 1200 m, 4900 m and 8000 m.

For the R4 -> R5 handoff, the accepted R4 visual closeout must be cross-linkable to the pre-optimization Performance History baseline. R5 renderer experiments must not silently replace the accepted R4 visual baseline.

## When Visual History is required

Create or update an entry for:

- a roadmap visual slice;
- placeholder -> production/validated asset replacement;
- a new biome or major PCG graph;
- a material terrain/ground/sky/fog change;
- major vegetation/rock density or massing changes;
- a major rider/animation/camera presentation change;
- any change whose acceptance explicitly depends on what the rendered scene looks like.

It is not required for docs-only work, CI-only fixes or refactors with no intended visual effect.

## Automation policy

The long-term preferred workflow is:

1. obtain the last accepted baseline captures;
2. run the current committed-SHA visual proof;
3. produce NOW captures;
4. compose deterministic triptych PNGs with HUD metadata;
5. compute hashes and optional pixel-diff metrics;
6. write/update the manifest and summary;
7. copy the canonical captures/triptychs into the matching `docs/visual-history/.../captures/` directory and record SHA-256 hashes;
8. require human visual acceptance before promoting NOW to AFTER.

A workflow artifact may be used to move capture bytes between CI and review, but accepted Visual History is incomplete until the selected evidence is committed to the repository.

Automation may prepare the evidence. It must not decide visual quality on behalf of the reviewer.

## Current feature checkpoint

[Issue #337 — accepted road appearance](issue-337-road-freeze/README.md) freezes
the owner-accepted road and Nudo candidate, with repository-retained native images
and hashes. Full-stage stable-camera triptych and performance closeout remain pending.
