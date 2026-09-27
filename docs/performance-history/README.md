# YACS Performance History

**Status:** planned standard introduced for Stage 3G R5  
**Purpose:** durable, exact-SHA performance evidence that can be compared over time and cross-linked from Visual History.

Performance History answers a different question than Visual History:

- Visual History: **what changed in the rendered image?**
- Performance History: **what changed in frame pacing, timing, memory and hitch behavior?**

Neither system replaces the other.

## ID format

```text
PH-<STAGE>-<SLICE>-<SEQUENCE>
```

Examples:

- `PH-3G-R4-001` — R4 closeout baseline;
- `PH-3G-R5-001` — R5 Native/TSR baseline;
- `PH-3G-R5-002` — first accepted DLSS comparison.

## Required provenance

Each record must include:

- Performance History ID;
- roadmap stage and slice;
- title / experiment name;
- branch;
- exact commit SHA;
- baseline commit SHA;
- PR number/status when applicable;
- CI/workflow run ID and run number;
- engine version;
- date;
- hardware identity;
- driver version where available.

## Required scenario identity

Record:

- scenario / route ID;
- route distance or benchmark path;
- camera preset/path;
- output resolution;
- screen percentage / internal resolution;
- graphics preset;
- weather;
- time of day;
- WorldSpec / PCG seed;
- upscaler backend + quality mode;
- frame-generation backend + mode;
- low-latency backend.

A result without enough scenario identity to reproduce it is not a durable baseline.

## Required timing evidence

Where available, capture:

- FPS average;
- FPS 1% low;
- Frame p50/p95/p99/max;
- Game p50/p95/p99/max;
- Draw p50/p95/p99/max;
- RHI p50/p95/p99/max;
- GPU p50/p95/p99/max;
- percentage of frames above 16.667 ms;
- hitch count;
- hitch duration summary / percentiles;
- limiting timing domain.

Do not use average FPS as the sole acceptance metric.

## Memory and world diagnostics

Record when available:

- RAM high-water mark;
- VRAM high-water mark;
- visible/relevant tree or foliage instance count;
- LOD distribution for diagnostic runs;
- shadow-casting instance count;
- loaded World Partition cells;
- generated/active PCG components or cells;
- streaming stalls.

Diagnostic counters do not have to remain enabled in shipping gameplay.

## Evidence files

A record may reference:

- summary JSON;
- raw CSV;
- comparison JSON;
- Unreal Insights `.utrace`;
- screenshots;
- Visual History entry;
- log excerpt;
- artifact hashes;
- CI artifact names.

Preferred layout:

```text
docs/performance-history/
├── README.md
└── stage-3g/
    ├── R4-closeout/
    └── R5-rendering-tech/
```

Large traces and binary captures may live in a durable CI artifact store; the repository record must retain exact provenance and a stable identifier.

## Baseline comparison

Each accepted experiment should compare against an accepted exact-SHA baseline and state:

- absolute and percentage timing deltas;
- FPS average and 1% low deltas;
- hitch delta;
- RAM/VRAM delta where relevant;
- whether the limiting timing domain changed;
- whether a hard or warning budget changed state;
- known visual artifacts/regressions;
- accept / reject / defer decision.

## Relationship to Visual History

When the same exact SHA has both visual and performance evidence, cross-link them.

A faster result is not automatically visually accepted.
A prettier result is not automatically performance accepted.

For Stage 3G, the canonical visual capture points remain:

- 1200 m — valley;
- 4900 m — forest;
- 8000 m — high Alpine.

## R4 closeout baseline

The active R4 agent must publish a closeout report before R5 implementation begins.

Required baseline fields:

- HEAD/commit;
- visible changes;
- forest/terrain/road status;
- 1200/4900/8000 m screenshots;
- average FPS;
- 1% low;
- Frame/Game/Draw/GPU timing;
- VRAM;
- hitch evidence;
- CI status;
- known problems/regressions.

This record becomes the pre-optimization R5 baseline.

## Acceptance rules

- exact-SHA provenance is mandatory;
- resolution/hardware/scenario mismatches must be called out instead of silently compared;
- generated Frame Generation FPS must not replace base-rendered FPS in hard acceptance;
- threshold changes require explicit review;
- one-variable A/B experiments are preferred when diagnosing a bottleneck;
- a rejected experiment remains traceable rather than being overwritten.
