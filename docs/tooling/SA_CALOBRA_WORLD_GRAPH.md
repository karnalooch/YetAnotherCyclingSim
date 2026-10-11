# Sa Calobra PCG world graph — #365 kickoff

**Status:** M3, CPU candidates, native mesh inspection and saved/reloaded mechanical graph; regional placement pending.
**Owner:** procedural-world. **Base:** `4dd792219bfc2eaf7dc216bd60cbde6628bba792`.
**Current owner instruction (2026-10-12):** implementation resumed for #365,
using subagents and the existing Material Forge contract. The planning-only
instruction of 2026-10-11 is superseded; acceptance gates remain unchanged.
The complete researched continuation is recorded in the
[detailed execution plan](SA_CALOBRA_WORLD_GRAPH_PLAN.md),
[primary-source/tutorial ledger](SA_CALOBRA_WORLD_GRAPH_RESEARCH.md) and
[handoff for another LLM](SA_CALOBRA_WORLD_GRAPH_LLM_HANDOFF.md).
Evidence below separates CPU candidates, isolated native diagnostics and pending
regional asset/contact admission; none closes #365.
The [Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md)
and [World Authoring Library](../YACS_WORLD_AUTHORING_LIBRARY.md) own scope,
methodology and reusable tooling. This adapter is not a second proof framework.

## Dependency and bounded task envelope

#364 completed through squash merge [#470](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470).
[PR CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38174079043)
and [main CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38174992518)
passed. The owner [manually accepted](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470#issuecomment-6113634845)
the remaining route/latest-save gate; this does not manufacture an automated
whole-area review or latest fresh-readback PASS. #459 geometry debt is separate.

The first #365 implementation authenticates the existing World Authority masks,
pins graph-input version/seed and emits a deterministic relocatable input
manifest. Scope covers the full 2016.5 m square, not only the Golden Kilometer.
One source writer owns the adapter/config/tests; the coordinator owns docs.
Three read-only specialists audited dependency/proof, source masks and APIs.
No exclusive Unreal, build, GPU or home-runner resource is claimed.

## Resumed implementation — 2026-10-12

`scripts/assets/sa_calobra_world_graph_candidates.py` consumes the authenticated
inputs with an explicit lattice, horizontal probe radius, clearance and overlap
priority. Geographic anchor IDs do not change with seed or manifest identity;
density and native point seeds use separate named streams. The conservative
footprint rejects unknown/excluded cells, including partial cell intersections.
These are XY probes, not qualified mesh transforms or terrain contact.

Two local runs on the real 4033-square source grid used spacing 16 cells (8 m),
radius 0.5 m, clearance 0.25 m, priority `[2,0,1]` and configured seed 36501.
Both produced fingerprint
`17110fb45f877586ccbeb9c3ec1e914392abcf9bb548ecf6b24714c4e272e943`:
64,009 anchors, 124 admitted XY probes, 483 outside-footprint, 37,983 without
selected centre, 19,216 insufficient-clearance, 5,315 semantic-footprint and
888 density rejections. Receipts are ignored local artifacts under
`Saved/RuntimeProof/WorldGraph365/candidates-run-{c,d}/`; this is CPU candidate
evidence and does not replace Gumball native proof or exact-commit CI.

The PCGEx bootstrap now preserves existing source checkouts,
validate exact upstream or reviewed-patched state, and reject hidden local
changes, including assume-unchanged/skip-worktree flags. This does not install
PCGEx or prove its native build/load. Local validation: 7 candidate tests,
7 existing input-adapter tests, 4 existing mask tests and 8 real-Git bootstrap
tests PASS. Sandbox TemporaryDirectory access initially failed with WinError 5;
the affected suites passed outside the sandbox. Critical Ruff checks and all four
docs-index guards (links/i18n/structure/freshness), plus agent contracts, PASS.

### Material Forge integration

Reuse [Material Forge](MATERIAL_FORGE.md) and the accepted
[whole-map material baseline](SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md).
PCG/PCGEx owns classification and placement; Forge owns appearance. Forge may
consume authoritative masks without changing their classification or hashes.
Its local DetailMasks and Height EXR never supply geography, collision support
or Landscape displacement. Preserve the accepted Landscape material consumer.

For each future qualified mesh, bind the material receipt, package dependency
closure, UV/physical scale and validated PBR maps to that mesh qualification.
Reuse `scripts/ue/import_material_forge_variant.py` for validated Forge variants;
do not treat a material package or the `regional_limestone` family as a qualified
rock mesh. The accepted five-role surface library and optional Forge variants
are separate identities; do not silently replace the accepted consumer.

### Native admission remaining

The host audit found UE 5.8.2 CL56702186 and no canonical PCGEx installation.
Latest road checkpoint `Rc6b061b933e6` resides in the isolated
`b9fddea3f602-y473install01` project and reports `reload_proof: NOT_RUN`.
Canonical Content has no corresponding LiveCheckpoints package. Do not substitute
the older accepted canonical map for this road consumer. Regional StaticMesh
qualification, admitted terrain contact, native generation, save/fresh reopen,
intermediate images and protected exact-head CI remain pending. No real-scene
scatter or completion of #365 is claimed.

Forbidden: changing canonical road/physics, `Base_DTM`, Landscape geometry,
BOB semantics, source masks, live Editor state or streaming; treating isolated
plugin preparation as canonical installation or native placement admission;
inventing rock geography, species, terrain contact or placement acceptance.

## Native preparation and mesh qualification — 2026-10-12

[CI run 38179277475](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38179277475)
passed for `1c14beecfd81a6463711ebc9957047900f45b36e`, including the
Aggregate CI gate and hosted script tests. Unreal build/Automation was skipped;
that run is not native PCG evidence.

`scripts/assets/sa_calobra_pcg_qualification.py` adds a structural binding check
for source/license, imported StaticMesh bounds/support, materials/UV/world WPO,
terrain identity/datum and measured contact policies plus native fixture claims.
It always returns `placement: false` and `proof_authenticity: NOT_VERIFIED`.
It does not admit evidence, replace Gumball, set tolerances, or qualify a real
asset. Retained source/license/material evidence keeps its own producer SHA;
new native observations must match the qualification SHA. Nine CPU fixtures PASS.

The retained PCGEx checkout under the runner's `_phase2c-pcgex-cliff` project
matches approved commit `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66` and the
reviewed patch; its 40 DLLs declare engine BuildId `55116800`. These are retained
prebuilt binaries, not a build of current YACS code. The isolated local diagnostic
launcher `scripts/ue/Invoke-YacsPcgNativeProbe.ps1` authenticates retained sources,
stages the plugin without PDB/Intermediate, and preserves canonical Content.
Its Python consumer reads Epic's installed `Skill_PCGGraphGeneration` through
the reflected skill API before graph authoring, then inventories native APIs
and mesh dimensions. Outputs are `LOCAL_DIAGNOSTIC_ONLY`, never a new broker
receipt. Graph generation/save/fresh reload are still pending at this checkpoint.
The first diagnostic attempt at `ab932af13f1e35103a2ca8cf5a02f03ca76c0750`
stopped before Editor launch: Git's CRLF warning entered bootstrap's changed-path
array through merged stderr/stdout and caused `clean_checkout, expected_patch_only`
failure. The fix separates Git output streams, with a CRLF regression fixture;
it does not change retained plugin files or weaken checkout authentication.
The second attempt at `e8e2c2fd18cea949bfad23f801ef988fa38040d1` authenticated
and loaded the staged PCGEx modules, then failed in the skill reader because
the official registry wraps output in `returnValue`. The retained emitted schema
also confirms input `skillPaths` and output `instructions`. The consumer was
corrected to those observed names. No graph or source map was saved by this run.

Native inspection at `fba989c91d9f83842ace99960ffdfeb5f0ba3fa6`, token
`inspect03`, completed in an owned isolated Editor. The skill path was
`/PCGToolset/Skills/Skill_PCGGraphGeneration.Skill_PCGGraphGeneration_C`,
instruction-content identity
`fc1113b6d72c9a629af6bda19293104968d991671d0b9d32e922fcdaa8aa7d50`.
No primitive or example graphs were available in that isolated catalog. The
next mechanical fixture therefore uses native Create Points and graph Output,
with three synthetic fixed-seed points; it is deliberately not regional scatter.
It reads node schemas before authoring, binds completion/cancellation/cleanup
events before execution, compares cleanup/regeneration, and saves only a new
isolated diagnostic graph/map. Fresh reload must read the stored recipe before
regeneration and preserve package bytes. Analytic engine-cube ground and an
unrelated collider test sampled support/owner exclusion; they cannot supply
Terrain Authority admission. Completed fixture evidence is recorded below.

Boulder native inspection: bounds origin cm
`[-11.01963996887207,-3.200286865234375,43.01846694946289]`, extents cm
`[64.36442565917969,91.6882553100586,50.434513092041016]`, four LODs,
vertex inventory `[234411,122537,44796,15918]`. The material slot `boulder_01`
currently references `/Engine/EngineMaterials/WorldGridMaterial`. Source-model
UV-channel query returned `[1,0,0,0]`; installed `GetNumUVChannels` inspects
MeshDescription, so zeros on generated LODs are not proof of missing render UVs.
Render UV/material physical scale and support geometry remain unverified.
At identity rotation/scale, the conservative pivot-centred XY radius from native
AABB is `hypot(abs(origin.x)+extent.x, abs(origin.y)+extent.y)/100 =
1.2118825350159463 m`; local AABB Z is `[-0.07416046142578125,
0.9345298004150391] m`. These are bound calculations, not measured support geometry.
The existing CPU candidate fixture assumes radius 0.5 m: its 124 admitted probes
cannot be reused for this Boulder. Re-evaluate eligibility with the final scaled
footprint, material/WPO envelope and admitted support/contact contract first.
Two CPU envelope sensitivity runs at `137a367395e76d406408e6f8f38fd54313b7d8e7`
used this 1.2118825350159463 m radius, spacing 16 cells, clearance 0.25 m and
priority `2 0 1`. Both produced fingerprint
`8e8849465bed2d0f72e1f9b6a92e700cbd9a9dce5f51dbfd72136dcadd98b69f`:
64,009 anchors, 5 selected XY envelopes; 23,898 clearance, 1,588 footprint-semantic,
483 AOI, 37,983 no-centre and 52 density rejections. Outputs are retained in
`Saved/RuntimeProof/WorldGraph365/boulder-envelope-{a,b}/world-graph-candidates.json`.
This remains the existing **vegetation-selector** probe contract: the five XYs
are not rock-placement semantics or qualified Boulder positions. No Z/contact,
regional rock mask, material/WPO envelope or native spawner admission is inferred.
ImportData points to the historical `D:/ExternalAssets/.../boulder_01_2k.fbx`,
which does not prove correspondence with the newly recovered bytes. All staged
source packages remained byte-identical. No real mesh qualification PASS.

The single Boulder source was recovered with the existing bounded downloader
(2K, five files, 34.2 MiB, 256 MiB cap, no overwrite) into
`D:/yacs/data/assets/pcg365-boulder-source`. The acquisition SHA256 receipt
records provider URLs, CC0-1.0, source/index/config hashes and command/time.
FBX: 6,482,860 bytes, SHA256
`b1125cd1e08a425fa89bc62b96279b40e9a921618e12bfbbe0d575cb78f53c95`.
Initial acquisition status was `NOT_MATCHED_TO_HISTORICAL_IMPORT`. Later native
readback at `7c57428546ea447617d621abc09e440e27147268`, token `mechanical04`,
read the loaded mesh's `AssetImportData` registry JSON: exactly one FBX row with
`FileMD5=e20c1ed68dc10e039761d6bda58c8ef4`, matching the recovered source.
This establishes correspondence with recorded historical import metadata without
editing ImportData or reimporting; legacy MD5 metadata is not a new mesh geometry,
material or regional qualification receipt. The provider's
[Boulder 01](https://polyhaven.com/a/boulder_01) describes weathered rock, not
measured Mallorcan limestone. [Provider license](https://polyhaven.com/license)
was rechecked. Forge appearance cannot supply lithology or mesh support proof.

Retained Forge candidate `D:/yacs/material-forge-v2-final/run-a/regional_limestone/base`
(Weathered pale) was rechecked with the existing `material_forge.check_variant`
CPU validator without rewriting its receipt: `MAP_CHECKS_PASS_UE_REVIEW_PENDING`.
Producer SHA: `ba9e9cfef724f5a7ab2fbaaa0269e4442398be3d`; Material Maker
`4d29a815489866aae483281cf44b2cfe48d3cc3e`, Godot 4.7.2, seed 211,
physical tile 4 m. It is a procedural artistic candidate, not a geological scan.
`refined_b` was not found among retained files; do not substitute its historical
description for the actual `base` bytes. The accepted five-role baseline is unchanged.

| Retained 2048-square map | SHA256 |
|---|---|
| BaseColor | `a397b418d316763afcb4fd0b8a80670bd9fad3080b8495b7e8259b6fb8303bb0` |
| Normal_DX | `90c78d7cc53a02a6ca2e052643712b7065b7b05e9300e9dc493263786183a034` |
| ORM | `99ed7cada4a03578495fe9f179fadcb7f7d7df7bea578c49b09ff0b64284d032` |
| DetailMasks | `40bc6bf1d71bf5fcffccf457f9afad1e6f3a52da3ad9ef768c81e4d58e9df7fc` |
| Height EXR | `13df224ee533162ae91ca7ca11504dc242bb09355928f0ebd16571de18d96c19` |

Retained validation/provenance/render receipt identities respectively:
`2da21368e9dd52a0528cfcf3926fa3f6464a287913186f660c13b44f8cb629fa`,
`e05fc44a876959b0692d4bd3faf3c49e70ccaa4ed74d9b88a674a7e104a8cdf9`,
`3ef37e8d3d862ac5d8bd9f1fd3f7b9088be233b25158bf3a8c8c5be5bc6cc3d6`.
These authenticate a retained material source candidate only. A derived Boulder
material package, native binding and 4 m/repeat UV proof are still missing.
Height is inspection/authoring data, never elevation/contact or displacement authority.

### Native mechanical graph and persistence evidence

Implementation SHA `8e0a38b60dc9ef98c8346548ff2e4dd88333c8cd`, token
`mechanical06`, staged at `D:/yacs/work/pcg365/<SHA>/mechanical06`.
Run the committed launcher with that SHA/token and actions `inspect`, `create`,
then `reload`, serially on an idle host. Existing action outputs are never overwritten.
Inspect and create completed with clean process exit and unchanged staged source
bytes. `create` reports `MECHANICAL_GRAPH_SAVED`: three fixed synthetic points,
two equal inventories separated by component cleanup; 27 finite support traces
hit only `PCG365_AnalyticGround` at Z=0. An unfiltered trace hits the unrelated
collider, owner-filtered traces exclude it, and an unsupported XY misses.
Numeric epsilon is analytic fixture precision, not an admitted regional tolerance.

Saved package identities:

| Package under `Content/Generated/YACS/PCG365Mechanical` | Bytes | SHA256 |
|---|---:|---|
| `PCG_XYFixture.uasset` | 25206 | `a94915336ffd1ce093b5d43a1fd6af67d3af5054f59ecca6b053f622273e692f` |
| `L_XYFixture.umap` | 33441 | `a12197b17bb6b7a13dbda601cd2580764ab48beb538b20702d208893b08de9e1` |

Fresh reload completed: `MECHANICAL_GRAPH_FRESH_RELOAD_REGENERATED`, clean exit 0,
`saved_recipe_verified_before_explicit_generation: true`, two matching inventories
of three points, repeated 27-sample contact fixture and unchanged saved/source bytes.
Receipts are in `proof/{inspect,create,reload}` with per-action
`launcher-completed.json`; logs and staged-file registry remain beside them.
The reload checks stored node/points, component seed 36501, GenerateOnDemand
and package hashes before explicit generation, then compares both completed runs
and verifies unchanged package bytes. Cleanup/regeneration can reuse node cache;
this is lifecycle/inventory evidence, not proof of uncached node execution.

Preserved failed attempts are part of the evidence: `90985ed8/mechanical02`
used the wrong collision enum; `38d8c03c/mechanical03` auto-exited before the
asynchronous result; `7c574285/mechanical04` used the C++ class name instead of
its Python ScriptName; `97f2a346/mechanical05` accessed the new tagged-data wrapper
as a direct property. That inspection also returned process exit `-1073741819`
during shutdown, so its receipt alone is not clean completion. Current code uses
`CollisionResponseType.ECR_BLOCK`, `EditorPythonScripting` keepalive and the
four-output native tagged-data break. Launcher requires both an error-free receipt
and clean inspection exit before graph operations; callback exceptions force FAILED.
API decisions were checked against installed UE 5.8.2 headers, including
`EngineTypes.h` ScriptName, `EditorPythonScriptingLibrary.h`, `PCGData.h`,
`PCGComponent.cpp` completion/cleanup ordering and `CreatePoints.cpp` seed behavior.

All native receipts are `LOCAL_DIAGNOSTIC_ONLY`, `placement: false`,
`qualified_assets: []`, regional terrain contact `NOT_RUN`, native build
`NOT_RUN_PREBUILT_DEPENDENCY`. There is no PCGEx-specific node execution,
Material Forge native binding/render, real terrain-owner contact, regional spawner,
full-area invalidation/override or protected Gumball native admission yet.

Local validation: final bootstrap 10 real-Git cases completed; the initial combined
test invocation then failed to import the qualification module. Correct direct
qualification invocation passed 9/9; agent contracts passed 8/8. Critical Ruff,
PowerShell parser and docs links/i18n/structure/freshness passed. GitHub CI
[38181719536](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38181719536)
for `90985ed858bdb19e1520fa7b711bd989a56ac481` passed, including aggregate,
hosted discovered scripts and security checks; Unreal build/Automation was skipped.
Later delivery-head CI must be checked independently in Draft PR #474.

## Authenticated source contract

### Material binding and real-ground measurement packet — 2026-10-12

Owner explicitly requested native Forge binding and real-terrain contact assessment.
Base `462668bcbc07e720e03c821d39925a2d33ec256f` is clean; its
[CI run38182535894](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38182535894)
passed. This packet remains #365/M3, owner procedural-world; visual-dcc owns the
new material helper, coordinator owns staging/contact/docs, specialists review
source and native API boundaries. Host was IDLE before staging; native actions
remain serialized. No canonical content, terrain, route/physics or accepted
five-role material package may be saved or edited.

Prepared helpers duplicate the staged Boulder into
`/Game/Generated/YACS/PCG365Qualification`, import the pinned Forge variant through
the existing producer, and verify stored mesh slots, effective MI/parent, 400 cm
world-aligned projection and zero WPO/displacement. Explicit save and fresh
readback must complete before contact measurement. Native results are NOT RUN
until the per-action process finishes cleanly with matching source/package hashes.

Real ground is deliberately the retained #363 accepted Landscape material consumer,
not the latest #364 road checkpoint. Source config
[`pcg365_qualification_sources_v1.json`](../../worldgen/sa_calobra/pcg365_qualification_sources_v1.json)
pins its map and all 14 delivered/material dependency packages, Forge sources and
source-height witness. Map SHA256
`bf2b92945865e2307990b6d3da40095dfa0774d28affb32a1e42e55f288764dd`;
DTM SHA256 `6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a`.
This explicit substrate diagnostic cannot close latest-road compatibility.

Two source witness preparations produced identical SHA256
`72b312c5371d38265dd1821d3a416bb658fde39a8d0a86dcf52c9d00b50bc6ae`:
five bounded XYs, each 9x9 interior AABB samples, four valid DTM neighbours per
bilinear height, preserved EPSG:25831/0.5 m mapping. The fixed source producer
checks DTM/inventory/XY hashes again after reading. Four real-GeoTIFF tests cover
interpolation, NoData, wrong SHA and concurrent drift; PASS is CPU only.
The XYs remain vegetation-selector diagnostics, not regional rock placement.

Native contact will measure upward complex-collision rays against the derived
mesh's lower surface and exact Landscape-only owner/component queries, with
unrelated/generated collider and no-hit controls. A vertical analysis transform
minimizes sampled penetration; gaps, slope and source/native height residuals are
measurements, not approved embedding or placement. Finite interior samples do not
prove continuous support, render-triangle equivalence or perimeter coverage.
Contact/slope/float/penetration/source-uncertainty limits remain REQUIRED_UNSET
until justified from measurement and frozen. The source declares inherited
orthometric height; a specific geoid and independent vertical-datum proof are
not supplied. Qualification must remain pending while these gates are unresolved.

Native attempt `a634ba6fb7c0d3e86c26578d91073c45447da1f1/qualification01`:
qualified-source inspection completed with process exit 0 and unchanged staged
bytes. Material action exited 3 before explicit asset save: Python could not
resolve `world_position_offset` on `MaterialEditorOnlyData`. Its failed receipt
is retained under `D:/yacs/work/pcg365/<SHA>/qualification01/proof/material/`.
Fresh material readback and real-terrain contact were NOT RUN for that attempt;
no material/contact PASS follows from successful source staging. The correction
must preserve strict displacement checks and use a new exact-SHA attempt.

Attempt `146ddf750153c87e9006ef90ec05863238919200/qualification02` inspected
cleanly, but material action again exited 3 before save: native property names
resolve, while Python refuses protected `WorldPositionOffset` input readback.
Shutdown also logged a UObject fatal error; no clean completion is admitted.
The diagnostic binding may verify public disconnected WPO and disabled Nanite
tessellation, but must report protected constant/displacement input readback as
UNAVAILABLE and maximum geometric displacement as unknown. It cannot claim zero
displacement or completed material/contact qualification from those partial checks.

Attempt `d08343354bdd172a516f7909ffef4b8f9f1a30ee/qualification03` passed
the bounded public material readback and reached explicit save of seven assets,
then failed direct-dependency enumeration (`get_dependencies()` returned `None`).
No completed binding receipt or clean launcher marker was admitted. Fresh reopen
and terrain measurement remain NOT RUN for this attempt; partially saved files
are retained only as failed-attempt evidence, never reused as an accepted result.

Attempt `49214a1a5574286b9703a3350ecd773fa1d14367/qualification04` reached
saved-asset registry validation, then rejected `SoftObjectPath`: this installed
Python binding requires an FName/string for `get_asset_by_object_path`. Material
completion and downstream measurements were not admitted; next attempt passes
the observed string argument without changing verification scope.

Attempt `0ae3e97967d8100b983952e376391cadb95c07b9/qualification05` wrote
the material binding receipt and seven packages, but editor shutdown exited 3:
`Object is not packaged: ModeManagerInteractiveToolsContext None`. Successful
action JSON does not override failed process completion. Next attempt initializes
an unsaved diagnostic editor world and lets the startup Python stack unwind before
requesting quit through a Slate callback; clean exit remains mandatory.

Attempt `1920c6f40b5ae7aa3ae2296e4b30ae39e404b392/qualification06` completed
inspect, material save and fresh material readback with exit 0, launcher markers,
unchanged source/staged bytes and saved-package hashes. Derived mesh package
SHA256 `6613bf07604ea255acceda9eee4686cc0314b78d8b997840a853cf7575a9a1f9`;
one slot, native 400 cm WorldAligned projection, expected four textures and MI
parent. All direct registry queries returned; recursive engine closure and GPU
shader/render acceptance remain unverified. Protected material-input limits above
still apply. Terrain action exited cleanly but its receipt FAILED the exact mesh
bounds identity guard before contact sampling. Next diagnostic records both
bounds values; no tolerance or qualification is inferred from that mismatch.

Owner requested an end-M3 visual concept. Imagegen produced an explicitly labelled
concept (`KONCEPT M3 — NIE RENDER Z UE`), SHA256
`62dbfa03962595740ea76ec132b17363cefcf8f1d9c04185372f5ec976d77c87`.
It illustrates weathered limestone/asphalt/shoulder composition only; invented
road shapes, shoreline, walls and vegetation are not source authority, scope
approval, a native screenshot, implementation evidence or visual acceptance.

Existing Julka profiles `sa-calobra-pcg-masks-candidate` and
`sa-calobra-mask-transitions-candidate` verified with zero issues, including
inherited source closure. Existing `verified_manifest()` also checked fingerprints,
byte hashes, logical raster hashes and grid. These results authenticate inputs,
not production placement.

| Input | Manifest SHA-256 |
|---|---|
| `pcg-masks-v1-2026-10-04/pcg-mask-manifest.json` | `465788e5d74cf3eccf59bdddc1480fa4d7dac50d6f22255ca69ac3b9f174b5df` |
| `mask-transitions-v1a-2026-10-04/transition-manifest.json` | `2cb28c018f2ed3562762d8c47976307b64397f06417c5c8efc4221bd92182950` |

Grid: EPSG:25831, 4033 × 4033 at 0.5 m; affine
`[0.5,0,483000,0,-0.5,4409516.5]`. UE origin in EPSG metres:
`[483000.25,4409516.25]`; X east, Y south, centimetres. Pixel centres map to
`col=floor(Xcm/50+0.5)`, likewise row; footprint bounds
`[-25,-25,201625,201625]` cm. No Z is inferred from a selector texture.

Reuse `scripts/assets/read_sa_calobra_pcg_masks.py::evaluate` for eligibility:
band must equal 1; reject 0/255, outside AOI and unknown clearance; full horizontal
asset radius must fit inside AOI. Subtract point-to-cell-centre distance from
the conservative clearance lower bound, then require radius + explicit clearance.
PNG alone is insufficient. Density/transition may only reduce admitted domains.

Selector bands low/medium/high overlap and describe source vegetation classes,
not species or plant positions. Preserve the exclusion bit inventory: asphalt,
0.51 m conservative shoulder, complete BOB affected rectangles, buildings,
decorative water/infrastructure holdbacks, other LiDAR classes and missing samples.
Mapped point/line holdback is 5 m, not measured channel width or safety clearance.
High rejects invalid height; low/medium class evidence does not repair height.

Transitions retain NoData. Their relative return fractions and authored fades
are not physical density or confidence. Water gap candidates remain review only.
Unknown rock/bare-soil subtype must not become rocks from yellow/RGB candidates.

## Tools and exact version audit

Installed engine `Build.version`: UE **5.8.2, CL56702186**; native PCG descriptor
Version 8 / VersionName 1.0. Installed matching headers establish graph creation
and edges (`PCGGraph.h`, `AddNodeOfType`/`AddEdge`), stock mesh-selector setup
(`PCGStaticMeshSpawner.h`) and delayed generation/cleanup (`PCGComponent.h`).
Submitting generation is not proof of completion.

Approved PCGEx revision: `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, version
0.79 / descriptor UE 5.8.0. Retained source exists outside the live project;
its only tracked modification is `clipper.triangulation.cpp`. The reviewed
compatibility patch LF hash is
`8182824990670e560d1a1f0d052288cc8a98dc5cdb370bdbf63f2666f9593d89`.
Exact patched-source compatibility remains unverified here. PCGEx is absent
from the active review snapshot; an optional enabled entry is not installation.

The attempted [Epic 5.8 documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview?application_version=5.8)
and [PCGEx agent index](https://pcgex.gitbook.io/pcgex/llms.txt) were inaccessible
during this audit. Matching installed native headers were inspected instead.
No PCGEx-specific node is implemented or asserted as verified.

Later planning research successfully read canonical Epic pages labelled UE 5.8
and specific PCGEx pages, while the version-query URLs and PCGEx agent indexes
remained inaccessible. See the [research ledger](SA_CALOBRA_WORLD_GRAPH_RESEARCH.md)
for exact retrieval limits, installed headers, bootstrap hazards and the unresolved
PCGEx documentation/source mismatch. This does not retroactively change the
original audit's evidence or establish native compatibility.

Existing Stage3G Forest/RouteExclusion graphs and generic patch candidates are
reusable API patterns. Their Alpine recipes, rectangle exclusions and counts
are not Sa Calobra source-mask, contact or production admission.

## Validation and next gates

The CPU adapter uses seed `36501` from
`worldgen/sa_calobra/world_graph_inputs_v1.json`:

```powershell
.\.venv\Scripts\python.exe scripts/assets/prepare_sa_calobra_world_graph_inputs.py --root D:/yacs/data/world-data/sa-calobra-working-v1 --config worldgen/sa_calobra/world_graph_inputs_v1.json --output Saved/PCG365/fresh-inputs
```

The output directory must be new. Two authenticated local runs produced identical
receipt SHA-256 `2028657f97977250e0ec479ec6d90bf61ee09b2fc9a1657a30fa2d51e1bc4c2b`.
Both Julka candidate profiles passed with zero issues. The input-adapter, PCG-mask,
transition and road-mask suite passed **21 tests**. These are CPU checks;
`native_execution: NOT_RUN`, `placement: false` and `qualified_assets: []`
remain explicit in the receipt.

Input adapter validation covers deterministic regeneration, source/config drift,
seed/grid/bounds rejection and unchanged exclusion/unknown semantics. Run the
existing PCG mask, transition and road-mask tests plus docs links, i18n,
structure and freshness. Keep generated receipts outside Git; record exact code
SHA and results in the PR. Use existing Gumball proof admission when native work
is ready; do not invent a separate PASS mechanism.

Next: qualify concrete asset identity/license/mesh hash and footprint; authenticate
Terrain Authority contact/Z and current road-envelope compatibility; connect the
admitted inputs to native PCG and stock spawner. Then prove deterministic
regeneration, local invalidation, override survival and saved reload/render.
All live-editor, build/GPU/runner work remains serialized under existing ownership.

Final whole-area owner audit: `PENDING_FINAL_M3`. Performance:
`DEFERRED_AFTER_M3`, `performance_pass: false`. This kickoff does not close #365,
implement later vegetation/rock stages or conceal unresolved geometry.
