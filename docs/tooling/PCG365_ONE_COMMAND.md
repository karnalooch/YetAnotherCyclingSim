# PCG365 single entry point

Issue #365, M3. The owner approved slope alignment up to 42 degrees, existing PCGEx nodes, MCP orchestration and input adaptation on 2026-10-13. The current visual recipe is `PCG365_PCGEX_SLOPE_ALIGNED_PREVIEW_V3`. Historical V1/V2 contact thresholds and rejected results remain unchanged.

## Run

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
