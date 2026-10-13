# PCG365 single entry point

Issue #365, M3. On 2026-10-13 the owner approved slope-aligned rocks up to 42 degrees and requested existing PCGEx nodes, MCP orchestration and input adaptation. Frozen V1/V2 contact results remain historical; the new recipe is `PCG365_PCGEX_SLOPE_ALIGNED_PREVIEW_V3`.

## Input adapter and graph

Run from the active source checkout, with a new output directory:

```powershell
python -B scripts/worldgen/build_pcg365_world.py --mode prepare-pcgex --output D:/yacs/project/Saved/PCG365/pcgex-input-next
```

The entry point authenticates the 2016.5 m square, original 0.5 m selectors, all technical exclusion bits, slope, supplied meshes and Forge limestone material closure. It writes `world-input-audit.json`, `pcgex-input.json` and `pcgex-node-plan.json`. Python converts data; existing nodes decide placement.

The prepared input contains 39,332 visible scree cells, all within 42 degrees. Of these, 2,923 meet the conservative source clearance: a 93.891702454 cm pivot-centred enclosing sphere plus 50 cm. These are input counts, not spawned instances. Native terrain/road checks, support screening and overlap pruning still apply.

`pcg365_pcgex_graph.py` composes the existing operations:

1. PCG Create Points carries exact positions, source slope and clearance.
2. PCGEx Numeric Compare / Uber Filter applies the source limits.
3. PCGEx Sample Line Trace projects onto the selected Landscape and aligns Z to the normal. A native normal filter repeats the 42-degree limit.
4. PCGEx Asset Staging / Classic Selector selects the supplied rocks and writes real asset bounds while retaining scale 1. The supplied Forge limestone material is reused.
5. PCGEx Bounds Filter protects current road/CUT bounds. Self Pruning operates on one dataset across the area.
6. Existing Transform, Line Trace and Filter nodes screen four surrounding probes. This is a five-probe support screen, not historical V2 contact qualification.
7. PCG Static Mesh Spawner uses PCGEx Mesh Selector Staged and the collection map. Decorative preview collision is disabled.

The graph is a candidate until executed and read back in the target Editor. Input preparation is not native generation or persistence proof. Cliff mesh/surface treatment, simplified/raised-form regions and final M3 review remain distinct work; scree output cannot claim their completion. Existing whole-map material bindings are retained, not relabelled as newly generated materials. Source Landscape and roads are unchanged.

## Versions and MCP

UE 5.8.2: changelist 56702186, compatible binary BuildId 55116800. PCGEx 0.79: `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, with the existing `yacs-pcgex-0.79-horizontal-boundary-v2` patch. The retained source passed the repository bootstrap validator before 2,313 authenticated files were staged into the Remote project. Staging is not proof of module loading.

The owner explicitly requested PCGEx/MCP activation and authorized closing Remote. `Start-YacsLiveHost.ps1` enables PCGEx, PCGEx Assistant, Epic PCG Toolset and Epic MCP on local port 8000. Preserve the immutable release updater, task owner, map hash checks and single Editor ownership. Never edit an installed immutable release in place.

PCGEx Assistant 0.3.2 is installed in the target project from its acquired FAB manifest. The 45 files were downloaded from the manifest's Epic CDN with Legendary 0.20.34, verified against every manifest SHA-1 and copied with SHA-256 verification. No engine updater was used for this installation. Its binary BuildId is 55116800. The installed source confirms `GetNodeSchema`, `CreateNode` and `AddSubnodes`, in addition to knowledge/introspection. Use Assistant to create PCGEx nodes and Epic PCG Toolset to update/connect them; live MCP and generation proof remain pending.

[Kweave](https://pcgex.gitbook.io/pcgex/kweave) generates HLSL for GPU nodes. Bridge adds mesh sampling, scene queries and live editing. It is an optional GPU authoring tool, not proof of this graph or an installed prerequisite.

## Validation and retained evidence

Fourteen CPU tests cover exact-cell conversion, exclusions, unknowns, clipped grid edges, rotation-safe bounds, clearance, receipt identity and create-only output. The existing 107 Live Host CPU checks also pass locally.

```powershell
python -B -m unittest scripts.worldgen.test_build_pcg365_world -v
python -B -m unittest discover -s scripts/live_host -p 'test_*.py' -q
```

The older `--mode regional-preview` remains available for admitted recipe `79e632710e32e576eb5b9d7db0b60a6e43cb7942`. Its corrected three-rock run completed as `CONTACT_JOB_COMPLETED_SAMPLED_ONLY`, with `preview_placed: 3` and `map_saved: false`, before the owner-requested shutdown. It does not prove the new graph.

Follow the [rollout handoff](SA_CALOBRA_ROCK_ROLLOUT_HANDOFF_20261013.md) and [world-graph contract](SA_CALOBRA_WORLD_GRAPH.md). Owner acceptance remains `PENDING_FINAL_M3`; performance remains `DEFERRED_AFTER_M3`, `performance_pass: false`.

The Launcher engine update to 5.8.3 was canceled after IS-UP-MF02-5 (Core.dll relocation failed). The installed engine still reports 5.8.2; cancellation alone is not a complete binary integrity proof.
