# RoadForge vendoring note

This directory is a **minimal donor subset** of the MIT-licensed RoadForge project.

- Upstream repository: https://github.com/YuuhenR/roadforge-osm-ue5-procedural-city
- Upstream commit: `781cb046483cc1887e80085aacf0fb2951f4746d`
- Upstream license: MIT; preserved verbatim in `Plugins/RoadForge/LICENSE`.
- Retained source: module bootstrap plus `RoadForgeMeshUtils.{h,cpp}`.
- Intentionally omitted: OSM parser/downloader, `AOSMRoadGenerator`, PCG scatter node, RoadForgeEditor, sample data, generated assets, screenshots and texture payloads.
- YACS descriptor adaptation: UE 5.8, no content payload, **Editor-target-only** module plus the `ProceduralMeshComponent` dependency.
- YACS source adaptation: the module startup log category is named `LogRoadForgeModule` for unity-build safety.
- No retained RoadForge source-file copyright headers were removed or rewritten.

## Why this subset

YACS already owns route truth. The useful donor surface is the geometry layer: flat ribbons, dashed ribbons, vertical strips, polyline offsets, miter handling and per-vertex Z. OSM ingestion and city generation would duplicate responsibilities and enlarge the long-term dependency surface.

## Shipping boundary

RoadForge is an **editor-time geometry donor**, not a shipping runtime system. Persistent road presentation created with these primitives must be saved as normal YACS content/output and remain reproducible from canonical inputs. Runtime/game targets must not load the RoadForge module.

If a future feature genuinely requires runtime RoadForge execution, that is a new dependency-admission decision with its own Embark-first review, runtime/package proof, performance evidence and rollback path.

## Decision gate

Issue #218 proves this donor can compile on the trusted UE 5.8 runner. Production SP638 use still requires a bounded spline adapter and visual proof; this module must not become route or physics truth.
