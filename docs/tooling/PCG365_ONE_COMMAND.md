# PCG365 single entry point

Issue #365, M3. The owner approved slope alignment up to 42 degrees, existing PCGEx nodes, MCP orchestration and input adaptation on 2026-10-13. The current visual recipe is `PCG365_PCGEX_SLOPE_ALIGNED_PREVIEW_V3`. Historical V1/V2 contact thresholds and rejected results remain unchanged.

## Native authoring safety hold — 2026-10-14

The current head deliberately **fails closed** before contacting Unreal in
`pcg365_wall_surface.replay` and `pcg365_whole_area.update_world`.
The recorded 100k-row MCP request has an unknown native outcome, so the old
wall replay cannot run and `--mode whole-area` cannot edit or save the
accepted `L_RoadSurface` map. Both guards are intentional until an owned,
independently verified derived consumer and true native bounded-probe evidence
are available. Preview inputs can still be prepared offline. There is **no
native acceptance** from these changes and no request to restart UE.

A caller-created `certified_point_count` dictionary is only a claimed value:
it does **not** prove that native graph data was reduced. `SafeMcpAdapter`
requires a separately installed trusted native verifier and a genuinely bounded
transport; neither is present in the current wall replay. It must reject rather
than fall back to the legacy 180-second / 32 MiB client. The source input count
(12,619 pilot records) is not a verified native mesh vertex count, and the
formation-node plan is a **specification, not installed graph wiring**.
Do not unlock a native rollout by fabricating a probe receipt or mocking a
verifier outside offline tests. Maintain the 3 cm diagnostic offset.

## Whole-area continuation and inspection failure - 2026-10-14

The owner authorized the complete 2,016.5 m square, continuous native PCGEx
walls and the existing gray material, preserving exclusions and the running
editor. Base remains `34a20aee62ae71c5af614f24512c4fc315b1c3d3`,
checkpointed at `2085627fb87396e62444c1939f888b897f4b87ed` on working branch
`codex/365-rock-contact-remote` ahead of PR #474 (`codex/365-world-graph`).

The current editor graph contains a whole-area input/region branch. Native
Connect Points and Partition Vtx initially found 934 connected groups from
55,174 source seeds with at least 125 cm exclusion clearance. A single convex
envelope was unsuitable for large sparse groups. The subsequent native
Partition by Values, Convex Hull 2D and Clipper2 Offset pass uses 32 m processing
bins and joins their outlines by 100.001 cm. The output contains 1,064 outlines;
these are **not 1,064 completed wall meshes**. The implementation still needs
hole handling, contact, final connected-component and whole-area visual proof.

The input adapter rasterized native outlines with existing Rasterio/GDAL, then
reapplied the unchanged known-terrain and protected-bit-63 inputs. Its 3,146,810
eligible samples are candidates, not inferred new cliff classification. Epic
Get Texture Data and To Point preserve exact 50 cm positions in a two-pixel
native test. PCGEx Get Texture Data was inspected first: the installed regular
Texture2D branch does not call its local ApplySettings helper, so custom texel
size/filter/channel cannot be assumed to apply. The Epic sampler supplies only
the input conversion; native PCGEx still owns the spatial processing.

The whole-area Sample Nearest Point branch executed, but its output count was
**unverified** after an official `GetNodeDataView` call requesting
100,000 position rows timed out after 180 seconds at 06:58:31 UTC. A later fresh
MCP initialize also timed out. The live editor log stopped at that data-view
dispatch; the Unreal process (PID 37152) remains present and responding.

To eliminate future lockups, [`pcg365_mcp_adapter.py`](../../scripts/worldgen/pcg365_mcp_adapter.py)
enforces:
1. A <=256-point *claimed* receipt is rejected unless an independent native verifier authenticates the actual reduced node; currently no production verifier is installed.
2. Complete elimination of unbounded reads (`endIndex=-1`).
3. Fail-closed circuit breaker on timeout with strict prohibition of automatic retries.
4. Mutual exclusion preventing concurrent access to shared graphs.
5. Multi-hypothesis diagnostic audit of potential blockage causes (serialization volume, GameThread deadlock, socket CloseWait accumulation, slicing algorithm complexity, and concurrent collisions).

[`pcg365_wall_formations.py`](../../scripts/worldgen/pcg365_wall_formations.py) implements:
1. Stable connected component identification (8-connectivity, 0.5m grid step).
2. Cross-batch boundary stitching across the 63 non-empty batches (512-cell limit).
3. Degenerate region detection (< 3 points) preventing bogus polygons and eliminating the `regions_hulls` warning.
4. Data ownership isolation in PCGEx nodes, resolving the forwarded `IsClosed` cleanup warning.
5. Strict hole and exclusion preservation (protected bit 63, clearance >= 125 cm).
6. Landscape contact verification and 3 cm diagnostic vertical separation retention until native proof.

[`pcg365_wall_batches.py`](../../scripts/worldgen/pcg365_wall_batches.py) prepares
63 non-empty bounded input textures, each at most 513 x 513 vertices. Adjacent
batches share their boundary vertices and no complete grid cells. It authenticates
sources and preserves the original texture coordinates and exclusions.

Local evidence is retained under `Saved/PCG365/full-walls-20261014`: node state,
official schemas, native outline readbacks, execution warnings, immutable input
manifest and `bounded-inputs/batch-manifest.json`. Fifty-one relevant local
unit tests pass with zero Ruff errors. Full native deployment in UE, owner visual
acceptance and performance remain **not complete / pending safe verification**.

References: [Partition Vtx](https://pcgex.gitbook.io/pcgex/node-library/clusters/analyze/cluster-partition-vtx),
[PCGEx topology](https://pcgex.gitbook.io/pcgex/working-with-pcgex/additional-systems/topology),
[Rasterio rasterization](https://rasterio.readthedocs.io/en/stable/topics/features.html).

## Current live continuation — 2026-10-14

The owner removed the rejected V6 cliff stamps. `--mode whole-area` now builds
the natural-rock lane only; it neither prepares nor regenerates those stamps.
Do not run that command merely to inspect the continuous-wall pilot.

The same pilot actor now has **one connected surface**, rather than a merged
collection of isolated patches. The owner authorized continuous derived walls;
source classification, unknown terrain and protected exclusion bits **63** stay
unchanged. The 129×129 review window remains bounded at rows 1300–1428 and
columns 508–636 of the original 0.5 m grid, approximately 65×65 m.

PCGEx Assistant 0.3.2 automates PCGEx 0.79 and Epic UE 5.8.2 nodes:

1. Native Convex Hull 2D builds the local envelope from 5,194 cliff seeds.
   Sample Nearest Path selects from 13,309 authenticated known, eligible surface
   samples. These geometry samples do not rewrite the cliff classification.
2. Direction probes and Cluster Surface produce grid faces. Native traces fit
   the current Landscape. The 3 cm world-Z diagnostic separation is explicit.
3. PCG Projection obtains Landscape normals without moving points. Existing
   Geometry Script nodes transfer normals and compute tangents; native Merge
   Dynamic Meshes and PCGEx Spawn Dynamic Mesh produce one visible component.
4. PCGEx Attribute Remap and Uber Blend compute a material transition using
   distance to the native envelope and the existing exclusion-clearance input.
   Vertex alpha carries that weight. A derived copy of the existing five-role
   material uses native Lerp to select ExposedRock in the interior and restore
   the original terrain weights at the boundary. Existing rock textures are reused.

Python configures these nodes, adapts authenticated inputs and validates native
output. It implements no hull, triangulation, placement or material-weight
algorithm. Exclusion rasters are neither smoothed nor recolored. The global
Landscape material and all 559 road/CUT actors remain unchanged.

Replay in the current editor session, using a new evidence directory:

```powershell
python -B -m scripts.worldgen.pcg365_wall_surface `
  --state D:/yacs/project/Saved/PCG365/wall-continuous-replay02/graph-state.json `
  --source D:/yacs/project/Saved/PCG365/wall-surface-20261014-pilot01/input.json `
  --surface D:/yacs/project/Saved/PCG365/wall-continuous-20261014/surface-input.json `
  --adapter D:/yacs/project/Saved/PCG365/wall-surface-20261014-resume/normal-adapter-state.json `
  --material D:/yacs/project/Saved/PCG365/wall-continuous-20261014/blend-material-state.json `
  --camera D:/yacs/project/Saved/PCG365/wall-surface-20261014-pilot01/close-camera.json `
  --output D:/yacs/project/Saved/PCG365/wall-continuous-replay-next
```

This configures and replays the existing bounded graph and material, not a
clean-install or full-area builder. It verifies both input hashes and original
source files, actor/graph ownership, connected geometry, normals, material
weights, collision and unchanged scene inventory. Success leaves the pilot
visible; `--hide-after` hides it. Failures during generation hide the pilot.
The camera is restored. Only the named graph, normal Blueprint and derived
material assets are saved; no map save, reload, new map or editor restart occurs.

Native evidence in `Saved/PCG365/wall-continuous-replay02/native-proof.json`:
12,619 vertices, 37,350 edges, one connected region and one `NoCollision`
component. Maximum XY edge is 70.711 cm, below the minimum authenticated
clearance of 144.922 cm; the conservative remaining clearance is 74.212 cm.
Normal-vector error is at most `1.49e-7`. All 37,350 edge-midpoint probes remain
above Landscape by 3.000–3.093 cm. Material alpha spans 0–1 with 3,497 intermediate
vertices. This is sampled native evidence, not a continuous whole-face contact
guarantee. Material-only changes preserve every read-back vertex transform.

**Whole-area cliff rollout and owner visual acceptance remain pending.** The
pilot is visible for review, and the prior mask-patch failure is superseded for
this local surface. Do not apply one global convex hull across unrelated walls.
The entire 2×2 km area, global material balance and green vegetation still need
their own work and review. The original Landscape's geometric artifacts remain
visible; this material pass does not repair them. Performance is
`DEFERRED_AFTER_M3`, with `performance_pass: false`; PR #474 remains Draft.

Primary capability sources: [PCGEx topology](https://pcgex.gitbook.io/pcgex/working-with-pcgex/additional-systems/topology),
[Sample Nearest Path](https://pcgex.gitbook.io/pcgex/node-library/sampling/nearest/sample-nearest-path),
[Attribute Remap](https://pcgex.gitbook.io/pcgex/node-library/metadata/modify/attribute-remap),
[Uber Blend](https://pcgex.gitbook.io/pcgex/node-library/metadata/blending/uber-blend),
[Epic per-vertex normals](https://dev.epicgames.com/documentation/en-us/unreal-engine/BlueprintAPI/GeometryScript/Normals/SetMeshToPerVertexNormals_FromLi-)
and [material instances](https://dev.epicgames.com/documentation/en-us/unreal-engine/instanced-materials-in-unreal-engine).
Installed Assistant knowledge and schemas resolved version differences,
including the actual `Sources` pin. Session `20261013T203714Z-90a9943bcfd6`
was retained. The source is a local candidate on base
`34a20aee62ae71c5af614f24512c4fc315b1c3d3`; native receipts hash the actual dirty
producer files. This is not a claim of remote exact-SHA or fresh-load proof.

## Historical V3 run

Keep the authenticated Sa Calobra road checkpoint open in the existing Live Host, with PCGEx Assistant, Epic PCG Toolset and Epic Editor Toolset exposed on localhost port 8000. From the source checkout:

```powershell
python -B scripts/worldgen/build_pcg365_world.py --mode build-pcgex --save-preview-map --output D:/yacs/project/Saved/PCG365/native-next
```

The output directory must be new. `--save-preview-map` creates a separate level asset; it never saves the accepted original level. Omit this flag when regenerating an existing saved graph. A different existing PCG365 preview is preserved and stops the command, rather than doubling the rocks. Unknown outcomes from timed-out mutations are not retried automatically.

`--mode prepare-pcgex` performs input preparation without touching Unreal. `--mode regional-preview` retains the earlier admitted contact recipe. `--mode whole-area` still reports incomplete cliff and other treatment lanes; scree output is not completion of the entire world graph.

## Native recipe

The input adapter authenticates the 2016.5 m square, original 0.5 m selectors, technical exclusions, slope, supplied N05/N06 meshes and Forge limestone material closure. Python converts records and calls official tools. All placement decisions run in installed PCG/PCGEx nodes:

1. PCG Create Points carries exact cells, deterministic point seeds, slope and clearance.
2. PCGEx Numeric Compare / Uber Filter applies the source limits.
3. PCGEx Sample Line Trace projects onto Landscape and aligns Z to the actual normal; another native filter enforces 42 degrees.
4. PCGEx Build Asset Collection prepares the saved collection once. The persisted graph uses Asset Staging and Classic Selector directly with that asset to choose supplied rocks and real bounds at scale 1.
5. PCGEx Sample Line Trace uses a sphere sweep against current road/CUT primitives. This replaces the rejected whole-road AABB approach, whose large boxes excluded unrelated terrain.
6. PCGEx Self Pruning operates on one dataset across the area. Four ordinary Transform / Trace / Filter branches screen surrounding support, followed by 5 cm embedding along the point normal.
7. PCG Static Mesh Spawner uses PCGEx Mesh Selector Staged and its collection map. Epic Object Tools sets and reads back `bForceDisableCollisions`; component readback must report `NoCollision`.
8. The PCG component uses explicit generation (`bRegenerateInEditor=false`). The temporary collection-construction nodes are removed before the final generation and save. Epic Asset Tools saves only the named graph, collection and meshes. Optional level duplication saves a separate preview map.

The working support tolerance is **±20 cm**. The initial ±4 cm setting eliminated every point in the native trial; the wider preview setting follows the owner's acceptance of minor manually repaired visual artifacts. This five-probe screen is not continuous-contact qualification or historical V2 admission.

The collection is a saved asset reference. PCGEx 0.79 rejected the transient collection-subobject path as a per-point asset source. The saved collection retains the existing PCGEx staging logic. Fresh loading the first persisted builder graph triggered `PCGExBuildAssetCollection.cpp:98` (`OutData && OutData->Metadata`). The final graph detaches this one-time preparation stage before saving, and native explicit generation prevents the editor from racing the orchestration while connections change. Selector properties use the installed MCP DSL strings and real pin names (`Sources`, `ActorReferences`, `Map`, `Overrides`).

## Current evidence and limits

The authenticated input has 39,332 visible scree cells. Source slope and conservative clearance leave 2,923. The complete command at `e3da98f4023b48c61b7c408dcfaec8ffab342e06` produced 20 actual mesh instances (12 N06, 8 N05), supplied Forge limestone bindings and `NoCollision`. Graph, collection, both meshes and a separate 193,290,890-byte preview level were saved. The output is `/Game/Generated/YACS/PCG365Ex/Ra1e9cbdd48ad0c85_s2/L_PCG365_Rocks`.

A fresh process (`20261013T203714Z-90a9943bcfd6`) reopened that level. All 20 transforms, mesh identities, material bindings and collision settings matched the saved result; subsequent explicit native regeneration matched again with no generation messages. Two native viewport captures were inspected. The supplied coarse source-envelope meshes expose angular/stepped sides, and their pale limestone material needs visual adjustment. These findings remain visible, not accepted or hidden.

[Portable native evidence](../experiments/sa-calobra-pcgex-mcp-20261013/manifest.json) records producer/host SHAs, package hashes, readback, images and the two resolved failure attempts. The build receipt's `fresh_reload_verified=false` describes the initial save stage; separate fresh proof and the final manifest record the later successful check. The original project descriptor and five protected packages still pass their authenticated preflight.

Existing whole-map material bindings are retained, not relabelled as newly generated materials. Cliff treatment, simplified/raised-form regions and final M3 review remain open; the command does not represent the scree preview as whole-area completion. The [rollout handoff](SA_CALOBRA_ROCK_ROLLOUT_HANDOFF_20261013.md) records delivery and CI status.

## Installation and access

UE 5.8.2 uses changelist 56702186 and binary BuildId 55116800. PCGEx 0.79 is pinned to `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, retaining `yacs-pcgex-0.79-horizontal-boundary-v2`. PCGEx Assistant 0.3.2 was installed independently from its acquired FAB manifest: 45 files verified by manifest SHA-1 and copy SHA-256. Live MCP confirms its knowledge, schema, creation and subnode tools.

The interrupted Launcher engine update was canceled. The 5.8.2 restoration receipt covers 5,907 affected files: 1,378 already matched, 4,529 restored, zero verification errors. No further UE download is needed for Assistant.

The owner explicitly authorized **broad editor MCP access**. The project allowlist includes `PCGExAssistant.PCGExToolset`, `PCGToolset.*`, `EditorToolset.*` and `editor_toolset.toolsets.*`. The last prefix is the actual name of Epic's Python toolsets, not `PythonTypes`. MCP remains local. Access does not grant terrain/source changes, performance acceptance or owner visual signoff.

`Start-YacsLiveHost.ps1` enables installed plugins through the command line. Preserve the original project descriptor and all five protected packages; changing the descriptor causes the existing latest-world preflight to reject startup. Keep the immutable release updater and single-editor ownership. Never edit an installed release in place.

[Kweave](https://pcgex.gitbook.io/pcgex/kweave) is an optional GPU graph authoring tool; its Bridge is not required by this CPU-node recipe.

## Validation

```powershell
python -B -m unittest scripts.worldgen.test_build_pcg365_world -v
python -B -m unittest discover -s scripts/live_host -p 'test_*.py' -q
```

The 14 input/receipt tests and 107 Live Host tests pass locally. They do not replace native instance readback, fresh reload, visual review or CI. Follow the [rollout handoff](SA_CALOBRA_ROCK_ROLLOUT_HANDOFF_20261013.md) and [world-graph contract](SA_CALOBRA_WORLD_GRAPH.md). PR #474 remains Draft; owner acceptance is `PENDING_FINAL_M3`, performance is `DEFERRED_AFTER_M3`, and `performance_pass` is false.
