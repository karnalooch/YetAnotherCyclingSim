# Argon continuation: Pegasus cliffs and real Ma-2141

**Status:** local implementation handoff, 2026-10-24. This is not production admission.
**Owner:** continue the existing work autonomously, with subagents and YACS skills.
**Scope:** M3 / #365, the authorized #368/#337/#459-related cliff, road and contact work.
**Do not search for another repository, branch, scene or source bundle. Use the exact paths below.**

## 1. Start here: fixed identities

Canonical code and Houdini source repository:

`D:/yacs/project`

Existing branch:

`codex/365-world-graph`

Local HEAD verified at handoff:

`dd2322f1e1ad784ee45878d40e80fcf69f953b30`

Existing delivery PR: [#474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474), still Draft.
Its current remote branch head was read directly from GitHub during this handoff:

`792fcff001445f0c203d067549c7ec855e9118f2`

**Local HEAD and remote HEAD deliberately differ.** The canonical checkout contains owner changes and untracked new producer files. Do not run checkout, reset, clean, pull/rebase, switch branches, create a parallel delivery PR, or stage the entire tree to make these identities match. Preserve local bytes. Integrate only the intended paths into the existing PR using an isolated index/checkout or guarded GitHub update after rechecking that exact remote ref. Never force-push. Old scripts in `Saved/roads-cliffs-delivery` contain old base assumptions: do not rerun them blindly.

The correct live owner project is a DIFFERENT project directory:

`D:/yacs/work/lesson07-readback-39439835210-2/YetAnotherCyclingSim.uproject`

Current UE PID at handoff: **36340**. Revalidate process identity before action; do not assume a PID survives reboot.

Current map package:

`/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07`

Correct saved map file:

`D:/yacs/work/lesson07-readback-39439835210-2/Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap`

Saved 2026-10-24 at **03:11:47 +02:00**, 1,940,786,611 bytes, SHA-256:

`a22b0a8e0d7927ea48d289ea9299e5eeb709d750e96023164f04a32ad3252170`

**Never substitute the same-named map in D:/yacs/project. That map is the older 2026-10-20 consumer and was explicitly rejected by the owner in this session.** The correct nighttime project has the accepted colour, cloud and manual lighting work. Its historical “readback” directory name does NOT make it disposable CI output.

Four actual actors are `SaCalobra_Unified_0_0`, `1_0`, `0_1`, `1_1`. Their material AND hole material are:

`/Game/PegasusDemo/Materials/Landscape/MI_Landscape_Instance`

Do not substitute `MI_Landscape_Instance_YACS` from the older canonical project.

Latest read-only state and saved new-cliff checkpoint:

`D:/yacs/project/Saved/argon-handoff-20261024/native-session-checkpoint.json`

That check saved ONLY the new Cd-preserving mesh, read `map_dirty=false`, and independently rehashed the unchanged correct map. No cliff/road preview actor has been placed by this coordinator, and no map save was performed.

## 2. Owner instructions and execution boundaries

The owner asked to:

1. Use the original Pegasus cliff lessons and supplied materials.
2. Find and implement beautiful asphalt using source-led Houdini/SideFX workflows, with Blender only where useful as support.
3. Implement ALL required roadside cliffs, including supported rock spires/overhangs.
4. Implement the real Ma-2141, at real scale and using source settings 1:1.

The current terrain appearance is accepted. That acceptance does not automatically admit newly generated geometry. Broad permission for necessary work and obsolete-junk cleanup persists; do not request the same permission again.

**No Computer Use.** The owner explicitly prohibited it. Do not use sky, CUA, desktop/browser UI automation, simulated clicks or keyboard navigation. Use UE MCP, native APIs, CLI, official web/HTTP sources and existing scripts.

Keep Source / Manual Edits / Procedural Detail separate. Do not overwrite the original DTM, FINAL cache, physical route inputs or accepted current packages. Do not restart terrain authoring. Do not resume the historical 300 m road. Do not invent replacement terrain, road or flow algorithms.

Use one writer per path and serialize GPU, native builds, UE and memory-heavy Houdini operations. All three former specialists have released their files and have no active native Houdini process at handoff. The 0.5 m global-flow experiment was explicitly stopped, not completed.

Read only this relevant authority set, in order:

- `D:/yacs/project/AGENTS.md`
- `D:/yacs/project/docs/README.md`
- `D:/yacs/project/docs/ai/README.md`
- `D:/yacs/project/docs/ROADMAP.md`
- `D:/yacs/project/docs/WORLD_BUILDING_BIBLE.md`, current executor decision and edit-layer contract
- `D:/yacs/project/docs/tooling/LOCAL_WORKSPACE.md`, “Current owner consumer — 2026-10-24”
- `D:/yacs/project/docs/ai/policies/M3_WORLD_OPERATIONS.md`
- `D:/yacs/project/docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md`
- `D:/yacs/project/docs/tooling/sidefx/SIDEFX_LABS_22_0_466.md`
- the two candidate documents in section 4

Use these existing skills under `D:/yacs/project/.agents/skills/`:

`yacs-orchestrate`, `yacs-houdini-world`, `yacs-road-bob`, `yacs-materials-visual`, `yacs-unreal-integration`, `yacs-verify-evidence`; use `yacs-docs-governance` and `yacs-github-delivery` for closeout.

Delegate three disjoint responsibilities: cliff geometry/global context; actual road/contact; material/source review. Keep UE writes under one coordinator. These are real tasks, not a claim that role cards automatically run agents.

## 3. UE MCP: known working access, no new controller

Live endpoint:

`http://127.0.0.1:8000/mcp`

Port 8000 was verified as owned by PID 36340 in the correct nighttime project. The actual current flags are:

```text
-EnablePlugins=ModelContextProtocol,EditorToolset
-DisablePlugins=Wingman,AndroidFileServer,HoudiniEngine,PCGExtendedToolkit,YacsPcgWitness
-ModelContextProtocolStartServer -ModelContextProtocolPort=8000
-NoSplash -NoLiveCoding -NoP4
```

Keep the editor running. Do not launch another copy. Do not use stale Live Host state or the older accepted-road launcher. The existing `D:/yacs/Open_Lesson07_Unreal.bat` was corrected to select the nighttime project; its previous bytes are in `Saved/CleanupOwner20261024/Open_Lesson07_Unreal.before.bat`. The general `Open-YACS.cmd` still represents an older checkpoint workflow.

First verify the OS process/port identity using the existing host script and normal PowerShell APIs; a failed process query is UNKNOWN, not idle. A useful exact read:

```powershell
Set-Location -LiteralPath 'D:/yacs/project'
& ./scripts/runner/Get-YacsUnrealHostState.ps1 -AsJson
Get-CimInstance Win32_Process -Filter 'ProcessId=36340' | Select-Object ProcessId,CommandLine
Get-NetTCPConnection -State Listen -LocalPort 8000 | Select-Object OwningProcess,LocalAddress,LocalPort
```

The tested fixed-target read-only bootstrap is:

```powershell
Set-Location -LiteralPath 'D:/yacs/project'
& ./.venv/Scripts/python.exe -B Saved/argon-handoff-20261024/mcp_readback.py
```

It reads the current map, four actors, supported ProgrammaticToolset environment and six actual texture settings. It writes:

`D:/yacs/project/Saved/argon-handoff-20261024/argon-first-readback.json`

This command was actually executed successfully. The six textures are non-VT: Colour = TC_Default/sRGB true; Normal = TC_Normalmap/sRGB false; Masks = TC_Masks/sRGB false. This resolves the previously pending VT input question without changing texture assets.

Sandboxed shell networking returned WinError 10013 even for loopback. The authorized host command needed `sandbox_permissions=require_escalated`; this is not an absent MCP server. Do not disable protections or change settings to hide that error.

Reuse:

- `scripts/worldgen/pcg365_bounded_transport.py`: `BoundedPcgMcpClient`, absolute 10-second bounded reads.
- `scripts/worldgen/pcg365_pcgex_graph.py`: existing `Client` and `unpack`, 180-second native import transport.

Native schemas and current readbacks are already saved in:

`D:/yacs/project/Saved/correct-owner-world-20261024/`

Relevant files: `mcp-tools.json`, `SceneTools.json`, `ActorTools.json`, `StaticMeshTools.json`, `ObjectTools.json`, `AssetTools.json`, `MaterialTools.json`, `TextureTools.json`, `ProgrammaticToolset.json`, `EditorAppToolset.json`, `expression-property-schemas.json`, `native-world-readback.json`.

Top-level MCP tools are `list_toolsets`, `describe_toolset`, `call_tool`. To invoke a toolset operation use the correct wrapper:

```python
from scripts.worldgen.pcg365_pcgex_graph import Client, unpack
c = Client()
result = c.call("call_tool", {
    "toolset_name": "editor_toolset.toolsets.programmatic.ProgrammaticToolset",
    "tool_name": "execute_tool_script",
    "arguments": {"script": source_text},
})
```

Do NOT substitute a top-level JSON-RPC tool named with the fully qualified function: the actual server exposes `call_tool`. In a fresh conversation call/read `get_execution_environment` before executing a tool script. Its safe script environment imports only json, re, math, time, datetime and copy, and supplies `execute_tool`; it is not general Unreal Python execution.

Reflected property names are lowerCamelCase. For example `landscapeMaterial`, not Python `landscape_material`. Many results have a `returnValue` which itself contains a JSON string. Parse that second level; do not print image base64 into the chat.

`CaptureViewport` actually requires explicit `captureTransform` and `annotations` despite optional schema wording. The working example/response is in `native-night-landscape-capture.json`; its image is `native-night-landscape.png`.

Never pass an empty `asset_paths` list to `save_assets`: it means SAVE ALL.

## 4. Files to continue, exact local hashes

All specialist changes remain local/untracked; preserve and inspect them, do not discard them because git calls them untracked.

- `D:/yacs/project/scripts/houdini/pegasus_cliff_candidate.py`
  SHA256 `bbfb1e576a28434b6b135e8226f8c3aa95b7c10aa433913f7d2b1eeaf000181a`
- `D:/yacs/project/docs/tooling/sidefx/PEGASUS_CLIFF_CANDIDATE.md`
  SHA256 `2fefa86b8074a0d04c03d549678060b6a1839dc9c36f23cf504f80b55c957c74`
- `D:/yacs/project/scripts/houdini/ma2141_road_candidate.py`
  SHA256 `e451b99e6581e4f0a79cbf05fa3a2a7ddcf8015f6a6c968fbe00bd05745ba21f`
- `D:/yacs/project/docs/tooling/sidefx/MA2141_ROAD_CANDIDATE.md`
  SHA256 `645d76c6bb7d1c4396319feefd80764a9b4fd7a623c5ae5bab4be386815038ce`
- `D:/yacs/project/scripts/ue/author_pegasus_cliff_material.py`
  SHA256 `a3e94285b3dc0ea705a6abb6dc34068c70b58b4b93d640e3486f89356a8e4890`

The coordinator also changed the current-consumer sections of `docs/WORLD_BUILDING_BIBLE.md` and `docs/tooling/LOCAL_WORKSPACE.md` and corrected the external Lesson07 launcher. The repository contained many other pre-existing local changes; do not stage or revert them as a batch.

Machine-readable cliff checkpoint:

`D:/yacs/project/Saved/cliff-argon-checkpoint-20261024.json`

Older coordinator state is at `Saved/owner-cliff-road-continuation-20261024.json`, but its flow/material-progress paragraphs are superseded by this handoff and the specialist checkpoint.

## 5. Original Pegasus sources: already present

Official series: [Pegasus Cliff Generation](https://www.sidefx.com/tutorials/project-pegasus-cliff-generation/).
The concordance is `D:/yacs/project/docs/tooling/sidefx/catalog/PEG-05.md`.

Exact supplied source project root:

```text
C:/Users/akarn/OneDrive/Dokumenty/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/Pegasus_Komplet/P1_05_Cliff_Generation/Materialy/Pegasus_Cliff_Project_Files_2/Pegasus_Cliff_Project_Files
```

The original HIP is `CliffPDG.hip` directly under that root, SHA256:

`3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a`

Original HDA directory relative to that root:

`Houdini/Packages/PegasusDemo/otls`

Exact HDA filenames:

- `sop_PE_Heightfield_Extract_Cliffs.1.0.hda`
- `sop_PE_Cliff_Generator.1.0.hda`
- `sop_PE_Cliff_Split.1.0.hda`
- `sop_PE_Heightfield_id_to_layer.hda`
- `object_PE_PDG_Heightfield_Cliff_Generator.1.0.hda`

Both original displacement maps exist under `SourceContent/Pegasus/Textures`:

- `wepoeaw_4K_Displacement.exr`: `bfd92a6294d246c2ce58a2e93cbbfffa13c3653b77eb7ae00a9ed2a328f99993`
- `tlonbisya_4K_Displacement.exr`: `e0e7c2ddcf6e3d98d91ffa3747a9234791ebf8aae52009bddc8ab9d740279b30`

Keep tutorial Megascans files external. Owner-supplied local use does not establish redistribution rights. Do not commit original scans, caches, extracted source bundles or binaries into public Git.

Installed native runtime:

`D:/yacs/tools/houdini-22.0.466/bin/hython.exe`

Reviewed Labs HDA runtime:

`D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda`

Use actual loaded definitions, not merely an archive inventory. Set CPU OpenCL and at most two Houdini threads unless a separately checked operation permits otherwise:

```powershell
$env:HOUDINI_OCL_DEVICETYPE = 'CPU'
$env:HOUDINI_MAXTHREADS = '2'
```

## 6. Cliff geometry: completed work and the exact next step

Literal original generator settings, verified against original HIP and HDA:

- subdivision = 2
- edge mask/falloff = 4 m
- texture scale = 0.01
- displacement strength = 10
- exponent = 1.5
- output percentage = 80 (keep the actual native meaning)
- extraction small-parts threshold = 1000

Do not continue the old custom 0.15-strength/0.1-scale/CC0-height-map candidate and call it 1:1. The supplied HDA blurs **P N**, whereas the L03 captions describe an N-only operation; preserve and report that discrepancy.

The original supplied terrain caches were measured at **2 m sampling**, approximately 2016/2017 squared samples. Proof:

`D:/yacs/project/Saved/cliff-original-source-grid-20261024.json`

The currently accepted terrain remains **0.5 m**. The owner-authorized next adaptation is a **separate 2 m derivative input for cliffs**, matching the measured source input resolution. This does not downsample, rebuild or replace the accepted Landscape/FINAL. Numeric generator controls stay literal. Measure native resampling deltas, spacing, phase, mask and Alpha separately; do not interpolate categorical IDs as heights.

**The 2 m adapter is APPROVED BUT NOT IMPLEMENTED / NOT RUN.** Do not report it finished. Relevant existing producer functions are `prepare_global_flow` and `cook_global_flow`. Current flow-cache identity pins and current-crop 258-square layout guards still admit the old 0.5 m boundary; adapt these explicitly for a newly proved 2 m branch, not by weakening checks.

Already prepared common-domain input:

`D:/yacs/work/pegasus-cliff-route-source-20261024-global-input`

Contains `flow_input.bgeo.sc`, `input_preparation.json`, and `height_piece_0.bgeo.sc` through `height_piece_3.bgeo.sc`.
The shared height/mask input is 7938 x 10498 at 0.5 m: 83,333,124 samples, with exact native preservation against four transport tiles. Input BGEO SHA256:

`067ae4ebdc0f68afef7dc88782834017c974a761a3e0db8e308ab9180500405e`

FINAL source lineage:

`f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24`

The original Flowfield parameters are rainamount 0.1, raindensity 0.1, iterations 100, smoothiterations 0, domask 1, maskscale 1, doheight 0, seed 8736.
The source Resample has fixedresample=0 and resscale=1; its displayed gridspacing=4 is **inactive**. Do not claim the previous flow ran at 4 m.

The expensive 0.5 m control was stopped deliberately. It is **NOT_COMPLETED**, has no output cache or runtime-progress checkpoint, and must not be resumed as a prerequisite. Preserved record:

`D:/yacs/work/pegasus-cliff-route-source-20261024-global-flow-v2/not_completed.json`

Its `setup_graph_reconstructed.hiplc` is a graph checkpoint, not resumed solver state.

Planned NEW output directories, which do not yet exist:

- `D:/yacs/work/pegasus-cliff-route-source-20261024-global-input-2m`
- `D:/yacs/work/pegasus-cliff-route-source-20261024-global-flow-2m-v1`

After implementing and proving the 2 m adapter, the existing global-flow command is:

```powershell
$C = Get-Content -LiteralPath 'D:/yacs/project/Saved/cliff-argon-checkpoint-20261024.json' -Raw | ConvertFrom-Json
$Otls = Join-Path $C.source_project 'Houdini/Packages/PegasusDemo/otls'
$env:HOUDINI_OCL_DEVICETYPE = 'CPU'
$env:HOUDINI_MAXTHREADS = '2'
& $C.hython -j 2 $C.producer --cook-global-flow $C.future_paths_not_created.prepared2m --otls $Otls --output $C.future_paths_not_created.flow2m
```

Do not run this before the missing adapter writes valid `flow_input.bgeo.sc` and `input_preparation.json`.

Full current inventory:

`D:/yacs/project/Saved/pegasus-cliff-corridor-inventory-20261024-source/inventory.json`

555 windows intersect the 500 m corridor; 543 contain cliff sample centres, totalling 10,801,467 original 0.5 m class samples. This is mask coverage, not geology, visible coverage or world admission. The old 92/178 raw-window checkpoint used a 64 m helper band and invalid-for-overhangs 2D road exclusion; it is not the new production baseline.

Compute shared flow/context BEFORE independent extraction. Separate 128 m flow solves caused context differences. The original Split HDA groups existing geometry with a bbox-fitted grid/centroids and output attrs; it does not reduce or cut generation cost. Its nominal 100 m parameter does not guarantee exact 100 m cutting planes. Do not split a large connected source component before the generator and pretend the changed boundary falloff/order is original.

### Existing full-recipe pilot: reuse it

Houdini directory:

`D:/yacs/work/pegasus-cliff-source-settings-20261024-full-recipe-class0`

Source extraction directory:

`D:/yacs/work/pegasus-cliff-source-settings-20261024-extract`

Split proof:

`D:/yacs/work/pegasus-cliff-source-settings-20261024-class0-split/split_receipt.json`

The complete original-recipe pilot has 2100 input polygons, 394519 unique P, 423833 output polygons, and exactly 787256 triangles after triangulation. Native cook and fresh graph regeneration reproduced exact P/topology. Cd is point data, N is vertex data. Original displacement is max 11.372801 m versus the zero-strength same-graph control; it is procedural lateral detail, not measured geography or clearance.

Export:

`D:/yacs/project/Saved/cliff-native-full-recipe-export-20261024/pegasus_current_class2.fbx`

The inherited filename says class2 but contains **class0**. SHA256:

`974a10778dd5e4393c3048545dfa84245b454c7f021a2a4396dfdc11b8e57268`

Do not recook/re-export this unchanged pilot.

Correct imported AND NOW SAVED UE asset:

`/Game/Generated/YACS/PegasusCliffs_Source20261024/SM_Pegasus_Source_Class0_Cd`

Physical package:

`D:/yacs/work/lesson07-readback-39439835210-2/Content/Generated/YACS/PegasusCliffs_Source20261024/SM_Pegasus_Source_Class0_Cd.uasset`

Package SHA256 `9e14f80af51f97850571d2841bb60bf56e35fad46931822d7360f0be7b214fa7`, 19,101,137 bytes.
Native triangle count is exactly 787256; native render vertex count is 394521. The two extra vertices have not been independently classified; do not claim full vertex-position equivalence. Native bounds agree with the expected (100*Houdini X, 100*Houdini Z, 100*Houdini Y) conversion within float storage.

The first asset without suffix `_Cd` ignored vertex colours and is a superseded diagnostic. Use the `_Cd` version. There is no placed actor yet. The saved correct candidate still has WorldGridMaterial, Nanite false and one auto-generated simple collision primitive: **these are pending integration, not a finished source cliff**.

Root discovered actual FBX default `vertexColorImportOption=Ignore`. A scoped change to BOTH `/Script/UnrealEd.Default__FbxStaticMeshImportData` and `/Script/UnrealEd.Default__FbxImportUI:StaticMeshImportData` set Replace for the second import, then restored both previous Ignore values in finally. Actual second import is Replace + ImportNormals. Do not globally leave importer preferences altered.

Proofs and exact native property names are in:

`D:/yacs/project/Saved/cliff-native-ue-source-pilot-20261024/`

## 7. Cliff material: source frames and prepared producer

Producer is the exact file in section 4. It contains the verified PBR, triplanar, normal-driven slope blend and Cd overlays from L13. No source `M_Cliff.uasset` was packaged; the workflow must be reconstructed with native MaterialTools. A generic UV limestone material is not equivalent: the original cliff has no UV requirement and uses world projection.

Official mirrors already read:

- [L13 Cliff Material](https://www.youtube.com/watch?v=XeQqHUrjvI0)
- [L04 Cliff Material](https://www.youtube.com/watch?v=jp5S76eleE8)

Do not download the videos again. Thirty-two exact 1080p source frames, URLs, timestamps and hashes are retained in:

`D:/yacs/project/Saved/asphalt-research-20261024/official-source-frame-receipts.json`

Key frames: `source-L04-267s.png`, `source-L13-40s.png` for RGB; `source-L13-1973s.png` for final masks; `source-L13-2155s.png`, `2235s.png`, `2266s.png` for RVT.

Confirmed controls:

- MapTiling 10; TextureSize = (1,1,1) * 100 * MapTiling = 1000 cm.
- Both PBR branches: saturation 1, contrast 0, hue 0, brightness 1, normal intensity 1, roughness intensity 1.
- Raw rock WorldAlignedNormal.XYZ -> TangentToWorld -> B -> SmoothStep(0.6,0.8).
- Attributes A=rock, B=grass.
- Cd R=convexity, G=concavity, inverted B=occlusion.
- Colour order base -> occlusion -> convexity -> concavity.
- Power/multiplier/contrast/opacity: convexity .5/1/.1/1; concavity .5/2/.1/.6; occlusion .4/2/.1/.5. Spoken early “multiplier2” for convexity was superseded by actual final-frame1.
- Linear RGB: convexity (.322917,.296007,.296007), concavity (.078125,.028740,.018584), occlusion (.062500,.052529,.050130), alpha1. These reproduce the displayed six-decimal precision, not hidden original float bytes.

Current producer defaults:

```python
MODE = "preflight"
SAVE_CANDIDATE = False
DESTINATION = "/Game/Generated/YACS/PegasusCliffs/Materials"
ASSET_NAME = "M_Cliff_Pegasus_L13_Confirmed_20261024"
MASK_GREEN_ROUGHNESS_VERIFIED = True
ACCEPTED_TEXTURE_VT_SETTINGS_VERIFIED = False
```

The final False is a handoff guard. The now-tested bootstrap has resolved it: all six actual accepted inputs are non-VT and match Color/Normal/Masks sampler types. Review `Saved/argon-handoff-20261024/argon-first-readback.json`, recheck if the session/assets changed, then set that guard True with the proof reference. Do not convert existing texture assets to VT merely because the tutorial inputs were VT; this is an explicit accepted-appearance input adapter.

Roughness G is independently proved in `Saved/cliff-material-native-20261024/accepted-roughness-graph.json`: existing MF_PE_Material.Roughness <- BreakOutFloat3Components.G.

Run fresh current-version `preflight`, then `author_surface` through the correct MCP wrapper. The older `Saved/cliff-material-native-20261024/preflight-result.json` proves dependencies for an earlier version and retains historical gaps; do not treat it as final graph/compile proof.

The producer does NOT assign the material, place actors, change Landscape, save a map or overwrite an existing destination. It verifies reflected fields, native pin names, values and wiring. Inspect/record any partial mutation before retrying after an error. Validate native compile, binding, vertex masks and a fresh render before expansion. Do not call a checker fallback finished.

RVT remains a real separate gap. Native queries found no RVT actor or asset in the correct owner consumer:
`Saved/cliff-material-native-20261024/native-rvt-source-state.json`.

Source math is verified: WorldPosition.Z - RVT.WorldHeight -> SmoothStep; attributes A=Landscape RVT, B=cliff/grass. Material defaults Min0/Max1; the source example instance displays Min1.701348/Max130.948547 cm. Do not silently copy those island-specific instance values or create fake RVT data. `author_complete` intentionally refuses until the actual colour/height providers and integration are proven. Preserve the accepted Landscape while resolving that dependency.

## 8. Real Ma-2141: reuse the new 3D BTIB candidate

Do not use the old DTM-draped ribbon or the completed 5 m-width fallback in `surface1/2/3` as the final road. New source-native footprint geometry is already cooked:

`D:/yacs/work/ma2141-road-owner-20261024-btib1`

Files: `btib_source_surface.hip`, thirteen `boundary_*.bgeo.sc`, `pavement_top.bgeo.sc`, `pavement_slab.bgeo.sc`, `canonical_profile_observations.json`, `btib_receipt.json`, `btib_reopen.json`.

FBX ready for later bounded UE import:

`D:/yacs/work/ma2141-road-owner-20261024-btib1/export/ma2141_btib_asphalt.fbx`

SHA256 `b17c49222d750e99624efde4a4ce65dc83dba8f490063c08b960cfdbf07cf44d`.

The exact producing code is frozen in that directory as `producer.py`, SHA256 `edf231720c613941fd4d948fd81f943aa547266bddde0e5edf3498b651b67972`. The current main producer only added later diagnostics; do not recook good geometry just because its code hash is newer.

Actual output: 6524 original boundary points, 6498 top triangles, closed slab13048 points/19520 polygons. Native triangulation, UVProject and PolyExtrude preserve source footprint XYZ and area. Thickness0.1 m and tiling4 m are explicit presentation assumptions. Source includes some steep top triangles: not a rideability/physical-profile PASS.

BTIB raw data is already local under `D:/yacs/project/Saved/asphalt-research-20261024/`:

- `btib2021-road-surface-ma2141-source.json`, SHA256 `92fd933d551f7513bf906a8b8134bf6eda9302c4c00b6de3f45a0a9d3bdc3776`
- `btib2021-road-surface-layer-metadata.json`
- `btib2018-road-axis-ma2141-source.json`, SHA256 `08f2f6d53c48c1bb28cdac5d4c07e41e6b80367ee8c2245bc5358d1d1aff753e`
- `btib2018-road-axis-layer-metadata.json`
- `btib2018-csw-dataset.xml` and `btib2021-csw-dataset.xml`, which establish dataset CC BY4.0.

BTIB nominal accuracy is1 m XY/1.25 m Z; do not call it centimetre survey. Keep original CartoCiudad XY/physics separately. CartoCiudad source is the existing `worldgen/terrain/benchmarks/sa_calobra/ma2141_cartociudad_source_2026-10-02.json`, SHA256 `6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36`.

Chosen road polygons: 7605,7608,7612,7613,7614,7625,29026,29027,29042,29043,29044,29046,29047.
All107 formerly missing cleft stations now hit source-native pavement. The 86 misses of the OLD CartoCiudad axis do not automatically mean holes in the new road.

### Complete the southern junction and urban terminal

The thirteen polygons form two XY components. Connect only the needed source-faithful local part of polygon7664 (large Ma-10), near E484795/N4407265; do not include the entire7 km Ma-10. Prepared clip bounds: E484770..484830, N4407235..4407310. Use native Clip2.0 on original triangulated geometry; clipop0 keeps the positive side, originx/originz, dirx/dirz, snaptol1e-5, dofill0. This clip is **NOT IMPLEMENTED / NOT RUN**.

At crossing29043/29044, one XY contact has7.523 m vertical separation. Do not weld those levels. The actual loop connects via29047/29046 with matching Z.

The urban endpoint lacks an official pavement polygon; paved areas were checked, nearest46851 is~82 m away. Separate owner-authorized interpretation from real ortho25 cm is next, not completed. Already prepared:

- `urban-terminal-ortho-raw.png`
- `urban-terminal-ortho-route.png`
- `urban-terminal-ortho-metadata.json`

All three are in `Saved/asphalt-research-20261024`. Bounds E482820..482940 / N4411040..4411220; E=482820+0.25*x, N=4411220-0.25*y. Preserve shadow/car occlusion uncertainty. Original axis2018 IDs109/112 PORT DE SA CALOBRA supply XYZ context, not widths.

### Contact: actual measured problem, no cosmetic fix

Diagnostic directory:

`D:/yacs/work/ma2141-road-owner-20261024-btib1-residual`

Read `source_residual_summary.json`, `source_residuals_by_sample_kind.json`, `source_footprint_continuity.json`, `cleft-native-cross-sections.json`, and the PNG/PDF maps in that directory.

13022/13022 boundary and centroid samples have valid source terrain heights. Road minus FINAL ranges -73.2875..+9.4325 m. Absolute p95 is1.2527 m on boundaries and0.8703 m at triangle centroids. This is bilinear native-volume diagnostics, not UE triangle or whole-road collision admission.

The coordinator ALREADY ran19 native distance-only probes BEFORE placing any new road/cliff actor:

`D:/yacs/project/Saved/correct-owner-world-20261024/native-road-source-probes.json`

SHA256 `45574a9ebc45ddc7f88299ff1ea86fb663da48dbfa16227743c1520a0ceab7ef`.
Maximum native collision versus source-cache difference was0.0705127 m. The exposed trace returns distance, not hit actor identity; the latter remains UNKNOWN.

The cleft mismatch is real in the correct consumer: independently sourced road~172 m, current terrain~245 m. Do not label it a proved tunnel/overhang or mere bad boundary sample. Source XY accuracy, epoch, DTM representation and real structure remain possible causes.

Exact comparison image:

`D:/yacs/project/Saved/asphalt-research-20261024/cleft-ortho-btib-context.png`

First compare original retained DTM TIFF at the SAME geo coordinates against FINAL, both road datasets and ortho. That specific raw-DTM-versus-FINAL cross-check has NOT RUN. Use:

`D:/yacs/data/world-data/sa-calobra-working-v1/accepted-base-dtm/sa_calobra_8x8km_mdt50cm_epsg25831.tif`

Do not perform a global73 m CUT. Resolve the cause, then use a bounded reversible Road_Earthworks layer or source-supported dedicated structure where appropriate. Existing native adapter functions `current_terrain_trial` and `terrain_trial` use supported HeightField Project/MaskByObject/Boolean operations; inspect their exact side effects, limits and source inputs. They are not admission for a new full-route rebake.

Current accepted asphalt material is already in the correct consumer:

`/Game/Generated/YACS/RoadAsphaltConsumer/aged_mountain_asphalt/dry_varied/9c0a41f6e2ae/MI_MaterialForge`

Binding/dependencies are documented by `Saved/ue-road-material-native-20261024.json`. Reuse it for the new road asset. Never use material/foliage to conceal contact defects. Native import of the NEW BTIB FBX, collision, placement, terrain integration, persistence and fresh reopen are still pending.

### Exact road reproduction, only when the graph actually changes

Do not execute simply to repeat completed proof. Use new output directories and keep old evidence.

```powershell
Set-Location -LiteralPath 'D:/yacs/project'
$env:HOUDINI_OCL_DEVICETYPE = 'CPU'
$env:HOUDINI_MAXTHREADS = '2'
$hy = 'D:/yacs/tools/houdini-22.0.466/bin/hython.exe'
$script = 'D:/yacs/project/scripts/houdini/ma2141_road_candidate.py'
$raw = 'D:/yacs/project/Saved/asphalt-research-20261024/btib2021-road-surface-ma2141-source.json'
$profile = 'D:/yacs/project/Saved/road-source-diagnostic-20261024/profile_excluded.json'
$rawSha = '92fd933d551f7513bf906a8b8134bf6eda9302c4c00b6de3f45a0a9d3bdc3776'
$next = 'D:/yacs/work/ma2141-road-argon-20261024-next'
& $hy -j 2 $script btib --record $raw --record-sha256 $rawSha --profile-record $profile --object-ids 7605 7608 7612 7613 7614 7625 29026 29027 29042 29043 29044 29046 29047 --thickness-m 0.1 --uv-tile-m 4 --output $next
& $hy -j 2 $script btib-verify --record $raw --record-sha256 $rawSha --profile-record $profile --object-ids 7605 7608 7612 7613 7614 7625 29026 29027 29042 29043 29044 29046 29047 --thickness-m 0.1 --uv-tile-m 4 --output $next
& $hy -j 2 $script export-btib --preview-root $next --output "$next/export"
& $hy -j 2 $script btib-residual --preview-root $next --terrain-root 'D:/yacs/work/pegasus-cliff-route-source-20261024-global-input' --output 'D:/yacs/work/ma2141-road-argon-20261024-next-residual'
```

Do not rerun btib-verify into a directory which already has btib_reopen.json; refusal to overwrite prior proof is intentional.

## 9. Recommended completion order

1. Read fixed-target state and current authority; confirm the live owner project. Do not reopen or search for alternatives.
2. Assign disjoint implementation owners; preserve all existing local changes.
3. Finish/prove the separate2 m cliff input adapter, then one shared source flow, connected extraction and original generation/Split. Budget actual components and keep source/layer/halo evidence.
4. Execute source material preflight, confirm the now-known non-VT inputs, author surface graph through MaterialTools, verify native wiring/compile and bind only the new candidate.
5. Inspect the saved full-recipe cliff in actual context, verify import Cd/N, Nanite and appropriate collision. Current auto-convex simple collision is not final complex cliff geometry. Demonstrate real3D road clearance, including upper/lower levels.
6. Complete source junction/urban road geometry; resolve raw DTM/FINAL/source-road differences and bounded earthworks/structures. Import the current source-native BTIB output, not the obsolete5 m ribbon.
7. Extend across ALL required corridor coverage, with explicit generated/imported/omitted counts and reasons. A successful one-crop pilot is not completion.
8. Save only authorized new/changed candidates with recovery; prove fresh native reload, scene/collision/materials and whole-area rider/overview views. Do not restart the owner session merely to obtain CI access.
9. Inspect final diffs, run focused checks/docs guards, deliver to existing Draft PR474 with exact remote SHA. Protected CI/review/native/visual gates remain separate. No merge merely because code-only checks pass.

## 10. Storage and validation at handoff

All original sources, accepted checkpoints, current consumer and active caches stay protected. The previous cleanup sent five obsolete appearance-trial directories to Windows Recycle Bin:181 files,3,498,789,935 logical bytes. This does not claim free disk reclaimed. Exact manifests:

`D:/yacs/project/Saved/CleanupOwner20261024`

Do not empty the whole Recycle Bin. Do not delete the active nighttime readback project or `lesson05-ue-20261018/transfer-height-only` (still referenced by rebuild scripts). Keep the common cliff height pieces: road residual analysis also uses them.

Host snapshot during handoff:~25.75 GiB D: free,~8.54 GiB physical headroom; these are observations, not future guarantees. Check again before heavy work. No active hython remained when checked. Do not change the5 GiB disk admission guard.

Native mesh build succeeded but Zen cache emitted a write-RPC500 for a missing shard under the C: path/junction into D: cache. Preserve the actual diagnostic; do not delete the active cache or call cache writing PASS.

Specialists ran scoped Ruff/syntax/native cook/reopen checks. The four docs-index checks passed before this final handoff was added; rerun after changes:

```powershell
Set-Location -LiteralPath 'D:/yacs/project'
& ./.venv/Scripts/python.exe -B scripts/ci/check_docs_index.py
git diff --check
```

Run evidence-storage validation if adding public receipt JSON/archives. Do not commit generated UE caches, Saved, Binaries, Intermediate, credentials or unlicensed tutorial sources. The newly saved UE mesh is a local package checkpoint, not a Git/LFS delivery or independent fresh-process proof.

Performance remains `DEFERRED_AFTER_M3`, `performance_pass=false`. Current appearance is accepted; new cliff/road geometry, source contact, full coverage, protected CI, final assembled-world acceptance and merge are NOT automatically passed.

## Pasteable start instruction for Argon

Continue the owner-authorized M3 Pegasus cliff and real Ma-2141 work from this exact handoff. Your code cwd is D:/yacs/project on codex/365-world-graph, with dirty/untracked work to preserve; the correct live UE consumer is D:/yacs/work/lesson07-readback-39439835210-2, PID36340, official MCP127.0.0.1:8000/mcp. Do not open the older same-named canonical map, search other branches, use Computer Use, restart the base pipeline or resume the old300 m road. Reuse the supplied scripts, native outputs, verified source frames and exact command lines here. Implement the missing2 m cliff-input branch, source material/native integration, all required roadside coverage and source-supported road/contact closeout. Keep original numeric settings, disclose necessary geographic/texture/version adaptations, and distinguish actual proof from incomplete stages. Proceed autonomously within the owner's existing permissions and report concrete remaining blockers honestly.

