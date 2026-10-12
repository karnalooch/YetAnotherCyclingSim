# Twenty natural rock derivatives — #365 / M3

Owner-authorized local production on 2026-10-12; no push or terrain/road change.

## Prepared sources

Pinned Blender4.5.9 produced twenty saved FBX derivatives from eight licensed CC0 scan families. [Producer receipt](producer-receipt.json), [Blender host receipt](blender-host.json) and [actual source inspection](source-inspection.json) bind source/output bytes. The collection has eight source families, with two or three variants per family, not twenty independent scans. Mild declared affine ART transforms preserve the natural scanned upper surface; planar undersides and rejected/excluded source components are recorded. Source-only underside preparation does not grant Landscape contact.

The first two stages were retained after partial rejection: post-bisect nontriangles required explicit triangulation; one source required explicit largest-component selection; stale imported custom normals were avoided through fresh mesh data. Guard failures were fixed without relaxing topology, source-preservation or contact limits. Final stage natural-rock-collection03 has twenty prepared outputs and zero rejected sources.

## Native status

Native save/reload/Material Forge/render chain completed all six actions with exit 0 at exact producer `92f5184c0e5df7cf7698d2c8b28b9e5796e831d7`, run `D:/yacs/work/pcg365/92f5184c0e5df7cf7698d2c8b28b9e5796e831d7/natural20-forge01`. The native receipt reports twenty saved and freshly reloaded assets, with Material Forge V2 bound. [Overview](overview.png), [closer view](row-02.png) and [evidence index](evidence.json) retain actual GPU output. Placement is false, qualified assets remain empty, terrain contact NOT_RUN, performance_pass false and benchmark DEFERRED_AFTER_M3.

## Validation

Five native-catalog CPU tests and eight producer/component CPU tests PASS. Documentation links, i18n, structure and freshness guards PASS before native launch. Protected CI/native build and owner visual acceptance are not claimed.
