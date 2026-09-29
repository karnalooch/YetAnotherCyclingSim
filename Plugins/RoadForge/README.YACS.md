# RoadForge vendoring note

This directory is a **minimal donor subset** of the MIT-licensed RoadForge project.

- Upstream repository: https://github.com/YuuhenR/roadforge-osm-ue5-procedural-city
- Upstream commit: `781cb046483cc1887e80085aacf0fb2951f4746d`
- Upstream license: MIT; preserved verbatim in `Plugins/RoadForge/LICENSE`.
- Retained source: module bootstrap plus `RoadForgeMeshUtils.{h,cpp}`.
- Intentionally omitted: OSM parser/downloader, `AOSMRoadGenerator`, PCG scatter node, RoadForgeEditor, sample data, generated assets, screenshots and texture payloads.
- YACS descriptor adaptation: UE 5.8, no content payload, only the runtime module and `ProceduralMeshComponent` plugin dependency.
- YACS source adaptation: the module startup log category is named `LogRoadForgeModule` for unity-build safety.
- No retained RoadForge source-file copyright headers were removed or rewritten.

## Why this subset

YACS already owns route truth. The useful donor surface is the geometry layer: flat ribbons, dashed ribbons, vertical strips, polyline offsets, miter handling and per-vertex Z. OSM ingestion and city generation would duplicate responsibilities and enlarge the long-term dependency surface.

## Decision gate

Issue #218 proves this donor can compile on the trusted UE 5.8 runner. Production use still requires a later bounded SP638 spline adapter and visual proof; this module must not become route or physics truth.
