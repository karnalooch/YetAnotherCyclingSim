# Sa Calobra material foundation

Issue [#363](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363)
implements the Landscape material step after completed #335 / merged #362.
Methodology authority: [World Building Bible](../WORLD_BUILDING_BIBLE.md).
Delivery order: [Roadmap](../ROADMAP.md). This workflow describes a candidate,
not completed visual, reload or performance admission.

## Inputs and evidence boundaries

Resolve project, data, work and map through `scripts/manage_local_workspace.py`
and the host's `workspace.json`. Author only in the canonical live project.
The current consumer is `/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004`:
4033 x 4033 samples at 0.5 m, EPSG:25831, covering the whole 2016.5 m square.

`scripts/assets/prepare_sa_calobra_material_inputs.py` verifies the frozen PCG
and historical-cover manifests and their output hashes before packing weights.
R is a low-vegetation visual fallback, G a medium/high-class forest-floor
fallback, B the dated SIOSE open-rock share outside those vegetation selections.
A records accepted sample availability, not calibrated confidence.

These are presentation amplitudes, never current land-cover classification,
species evidence or planting authority. Missing classes remain named neutral
ground fallbacks. All hard exclusions and unknowns suppress RGB before and
after a radius-2-pixel presentation box filter (2.5 m window). Filtering neither
changes source masks nor fills unknown pixels. Quantized RGB sums stay <=255;
the material uses the remaining weight for neutral ground. The deferred red
review overlay and unadmitted diagnostic rock/soil candidates are not inputs.

The neutral ground is a configurable decorative PBR fallback reusing
`sparse_grass`, with separate neutral tint/roughness scale. Its normal and
roughness detail avoids a flat-color boundary against textured ground. This
does not assert grass/soil cover in excluded or unknown pixels; their evidence
and planting weights remain zero. Full source uncertainty is retained in the
manifests and the deferred diagnostic review, not encoded as a false biome.

An existing output directory is never overwritten. New recipe/input revisions
retain preceding evidence. Each manifest records producer, sources, bytes,
logical raster hash, grid and world mapping.

## Authoring and live review

`worldgen/materials/sa_calobra_foundation.json` owns texture families, metric
tiling, native functions, package and input identity. Existing Stage 3G Poly
Haven texture families have recorded CC0 provenance in the
[dependency ledger](../legal/DEPENDENCY_PROVENANCE.md). Their suitability for
Sa Calobra limestone remains unverified; an imported Alpine family name grants
no geographic admission.

`scripts/ue/inspect_sa_calobra_material_foundation.py` reads the installed
functions' pins/default descriptions and the current actor inventory.
It also follows each component material's parent chain to confirm the visible
consumer, rather than checking only the Landscape actor property. The first
saved candidate matched all 1024 component roots in the live editor.
`scripts/ue/sa_calobra_material_foundation.py` runs in the existing editor:

```python
import runpy
foundation = runpy.run_path('D:/yacs/project/scripts/ue/sa_calobra_material_foundation.py')
foundation['apply_foundation']()
# Restore the preceding Landscape material without loading/saving a map:
foundation['apply_foundation']('original')
```

The producer rejects the wrong project, engine, map, grid, stale input hashes,
changed producer identity or asset collisions. Texture weights use linear color,
uncompressed BGRA8, nearest filtering, clamped addressing and no mipmaps.
Native WorldAlignedTexture/WorldAlignedNormal provide configurable metric
projection. Convex weighted color/roughness/normal blending preserves the
neutral residual. No displacement or WorldPositionOffset is connected.

Before/after checks compare actor transforms, Landscape component identities,
edit-layer names, nine height traces and the saved map hash. This is a bounded
live invariant check, not a replacement for full checkpoint geometry proof.
Default application saves neither assets nor the map; UE may independently
autosave recovery copies under ignored `Saved/Autosaves`. Preserve the owner's
other dirty packages. Asset saving is explicit and limited to the new material
and packed texture; never use Save All or save the owner's map as a shortcut.
The portable receipt `worldgen/materials/sa_calobra_foundation_asset.json` pins
the saved candidate, recipe, producer and input identities. Saved assets and
live component readback do not establish fresh reload, visual acceptance or
performance admission; those remain explicitly pending in the receipt.

`scripts/ue/review_sa_calobra_material_foundation.py` moves only the viewport
to nine distributed grid positions, keeping the camera above a separately
traced local surface. It uses native Look At rotation, verifies the camera
readback, completes the native loading barrier and compares the frozen scene.
These ground views supplement overview and road/rider inspection; they do not
constitute whole-area acceptance by themselves. Restore the original camera
with `review(restore=True)`; no actor is spawned or saved.

```python
review = runpy.run_path('D:/yacs/project/scripts/ue/review_sa_calobra_material_foundation.py')['review']
review(4)  # Central ground; 0 through 8 select distributed grid views.
review(restore=True)
```

## Version-matched tools audit

Verified editor: UE 5.8.2, changelist 56702186. Consulted Epic's
[MaterialEditingLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary),
[texturing functions](https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine),
and matching installed `MaterialEditingLibrary.h` / material expression headers.
Native function pins were additionally inspected in that running editor.
Viewport operations follow UE 5.8's
[UnrealEditorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem),
[MathLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MathLibrary)
and [AutomationLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary).
The installed recompile API returns compiler errors; empty means compilation
succeeded, but does not establish visual or performance acceptance.

GitHub API verified the reference revisions of Embark
[SkyHook](https://github.com/EmbarkStudios/skyhook/tree/fa8a44d51518303c0563d03b433b10145af7e51d)
and [UnrealClaudeFileHelper](https://github.com/EmbarkStudios/UnrealClaudeFileHelper/tree/2c87c3b4c433ab710b64ae348d0c0c55a927a641).
SkyHook separates transport from commands and uses UE Remote Control for Unreal;
the indexer is read/search tooling. Neither is a new dependency in this slice.

PCGEx GitHub API verified pinned revision
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, descriptor 0.79 / UE 5.8.0.
Official [Sampling documentation](https://pcgex.gitbook.io/pcgex/node-library/sampling)
was reviewed. Its agent indexes returned HTTP 403 during this audit; the pinned
descriptor/source remains independently accessible. No PCGEx graph executes in
this material-only step. Embark references do not establish Embark's PCGEx use.

## Required closeout

Review different environments, steep surfaces, demanding overviews and rider
views across the whole Landscape; retain the Golden Kilometer as an additional
check. Resolve visible material defects before owner visual acceptance.
Prove saved assets and a fresh consumer reload separately from live review.
Execute the deferred 2A/2B performance measurement on this actual map/material
at the exact candidate SHA, using existing budgets, reference hardware and raw
Frame/GPU evidence. A legacy terrain-baseline map cannot prove this consumer.
Run source tests, all four documentation guards and the required Unreal/asset
proofs. Keep the PR draft until required admission passes. Step #364 remains
blocked until #363 is completed and its implementation merged with proof.
