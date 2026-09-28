# RoadForge vendoring note

This directory is a **bounded compile-spike subset** of the MIT-licensed RoadForge project.

- Upstream repository: https://github.com/YuuhenR/roadforge-osm-ue5-procedural-city
- Upstream commit: `781cb046483cc1887e80085aacf0fb2951f4746d`
- Upstream license: MIT; preserved verbatim in `Plugins/RoadForge/LICENSE`.
- Imported scope: runtime module source only (`Plugins/RoadForge/Source/RoadForge`).
- Intentionally omitted: RoadForgeEditor, screenshots, sample data, generated assets and CC0 texture payloads.
- YACS adaptation: `RoadForge.uplugin` declares UE 5.8, contains only the runtime module and sets `CanContainContent=false`.
- No RoadForge source-file copyright headers were removed or rewritten.

## Purpose

Issue #218 evaluates whether RoadForge's procedural road-mesh core can compile inside YetAnotherCyclingSim on the trusted UE 5.8 runner. This is not production adoption and does not alter route/physics truth.

## Decision gate

Keep this subset only if the exact YACS PR SHA passes the real UE 5.8 editor build and existing scoped Automation tests. A later road visual spike is required before production use.
