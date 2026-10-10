# Road surface materials — Issue #364 evidence

**Recorded:** 2026-10-10

**Work item:** [#364](https://github.com/karnalooch/YetAnotherCyclingSim/issues/364), in progress; [PR #470](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470) is Draft.

**Authority:** [Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md), [M3 policy](../ai/policies/M3_WORLD_OPERATIONS.md), selected through the [documentation index](../README.md).

This is a scoped evidence record, not world or material admission. #363's
[accepted material checkpoint](../tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md)
remains frozen. #384 completed after protected [PR #467](https://github.com/karnalooch/YetAnotherCyclingSim/pull/467)
merged as `88f6b95e007b61a122b6515fe29041e5e3a3f220`; its gate is satisfied.
This work continues #364, not MCP infrastructure.

## Current proof boundary

| Check | Actual status |
|---|---|
| Windows source-stage tests | 37 discovered; 35 passed, 2 Windows symlink-permission cases skipped on Python 3.12.10 |
| Asphalt source replay | Two independent 2048 × 2048 renders of the same base recipe PASS; graph and all five map bytes match |
| Read-only Unreal baseline reader | Linux: 11 tests passed. Windows: parser passed; 10 tests passed and one symlink-permission case skipped. Actual scene read blocked before Unreal launch |
| Unreal shader/projection/normal and material assignment | Pending |
| Road, shoulder-top and support-side ownership; full mesh geometry proof | Pending native verification |
| Saved consumer, fresh reload/render and whole-area review images | Pending |
| Owner visual status | `PENDING_FINAL_M3` |
| Performance | `DEFERRED_AFTER_M3`, `performance_pass: false` |

The source proof did not start Unreal, author material instances, assign road
slots, save a map, prove geometry or render the Unreal consumer. It does not
satisfy #364's complete definition of done. The owner audits the complete
assembled M3 world at the end, before FPS measurement; intermediate native
technical checks and inspected, retained review images continue.

## Owner pause and actual native attempt — 2026-10-10

The owner stopped implementation and requested a report plus smaller roadmap
batches. Agent implementation/review work is stopped; no additional native job
is dispatched for this documentation update. The remote implementation head is
`33a35a74f17e56ef073248581e265db9db16cf7c`; #364 remains open and PR #470 Draft.
#364 changes are on that branch, not merged into `main`.
[Normal CI 38046180394](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38046180394)
passed. It does not override the failed stage-specific native attempt.

[Baseline run 38046175645](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38046175645)
passed PowerShell parsing and the Windows reader suite (11 discovered, 10 passed,
one permission-dependent symlink case skipped). It stopped at cache preflight
before staging, copying modules, invoking the cache resolver or starting Unreal.
The original verified cache state, binaries and scene were preserved.

| Fingerprint view | Compile | Proof |
|---|---|---|
| Actual fresh Windows files | `8caee4876a7a00aef42f6fea90f887193c4f38ddb6c69679cc0bec313f31f54f` | `7fdcba7f638c1c2a00edec7a5a14c7c7a81fde186849cad4ee0af435d2be99f8` |
| Retained hosted CI cache state | `e5fc3e8d77e350ba1bb94458bd71fd2fe2e771915f0c9838de7876b7fbbc01de` | `7e6a4073b34d86ae4c11122ecbac3d5b15f2088c774b5265008999e82734236c` |

The canonical native engine/toolchain environment matched the retained state.
Its original compile/proof head is
`40b85b0c07fc9bda28164f052641dd45c775f666`; mutable cache HEAD at observation was
`88f6b95e007b61a122b6515fe29041e5e3a3f220`. Preserve that distinction rather than
claiming a new compilation or Automation run. The failed-attempt artifact is
`11667629439`, ZIP SHA-256
`add0483d15f22018d37d489276bcd71b5035d015f8552ce625916898e7bfcd52`.

A read-only local simulation of native Windows EOL checkout exactly reproduced
the observed Windows fingerprints from 14 existing `.cs`/`.ps1` inputs whose
EOL is unspecified. This supports an EOL diagnosis; it is not actual Windows
per-file qualification, cache admission or a successful scene read. Resolve the
specific identity contract on resumption, retaining byte/source checks and the
existing cache authority.

An authenticated two-run source bridge remains a **checkpoint candidate** in `scripts/assets/road_material_contract.py` and its tests: 45
contract tests passed, but independent review did not finish before the stop.
Its strict raw receipt/current-input comparison remains; Linux and Windows raw
catalog/source fingerprints differ with their EOL bytes. No complete bridge or
native material admission is claimed from the separately downloaded Linux
bundles. A complete mesh/normal/UV hash reader was researched but not implemented.

The owner subsequently authorized publishing all retained work to the existing
Draft PR branch. The bridge and its tests are committed as an incomplete
checkpoint together with this status update; implementation remains paused.
A normal push can trigger automatic CI, but no manual native job is dispatched
by this checkpoint publication. The 45 contract tests were rerun successfully;
independent review and native material validation remain pending.

Resume batches are recorded in the [authoritative roadmap](../ROADMAP.md).

## Verified source run

[Run 38045485913](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045485913)
executed at `6fa54b508019bd4a1b4aa6fad601835295ec664f` on Windows with Python
3.12.10: 37 tests discovered; 35 passed, 2 Windows symlink-permission cases
skipped (`OK (skipped=2)`). Both renders passed. The downloaded result is
`ROAD_ASPHALT_SOURCE_DETERMINISM_PASS`, with raw `source-proof.json` SHA-256
`3626bf85da28d63908feb9d820171dc03d9d6cc444c8f799f7048f7a8052f79c`
and source fingerprint
`b4d93e24d2059c74e0b8d44f23ee10632e63f44c5c932b3ee1b849e0a6868d97`.
Independent read-only checks of both downloaded bundles passed at 400 cm and
23,747,976 input bytes per bundle, with all map and graph hashes below matching.

The first canary is `aged_mountain_asphalt/base`: seed **101**, a **4 m / 400 cm**
tile, brightness **0.30**, `surface_a` **0.62**, `surface_b` **0.22**, roughness
**0.82** and normal strength **0.48**. Normals use DirectX convention. Local
detail channels remain R=cracks, G=patches, B=binder micro-variation; they do not
generate world semantics. Height remains offline evidence, not displacement.
`worn` and `repaired` are not prerequisites of this first base proof.

| Output | Matching SHA-256 from both renders |
|---|---|
| `Material.ptex` graph | `6b381516854c44dc4bdeb69b69fbb2b97ecf22c228db2c09204822d7f0bc0970` |
| BaseColor | `85b378e871d7f0c70f079a153b1d6f64c517926ee7a3fd5c7bffca50766b88e8` |
| Normal_DX | `16425658df44c1ee3cf1003182dce10415a21894afb75c0ac0506a821c7bc77c` |
| ORM | `4c10e1ac79d0dd1abb276870e39b16663581a5ebf87a53043f80450e19713069` |
| Height | `a8ba0d03e3f7fb6b2a0014689e410a92a687083f12e1ab4c16ae07703b740074` |
| DetailMasks | `766b4b41b4b9b77f2e70a4f57be4e67b7a89b7c4c6049f57cd28771950ec832b` |

The producer authenticates the existing pinned tool archives before replay:

| Input | Pin |
|---|---|
| Godot 4.7.2 Windows archive SHA-256 | `731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953` |
| Material Maker 1.7 Windows archive SHA-256 | `deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808` |
| Material Maker source commit | `4d29a815489866aae483281cf44b2cfe48d3cc3e` |
| Godot source commit | `ed1daf0bf001b61586d9930840f2f1394092c079` |

Program and graph inputs remain unchanged. The receipt explicitly retains the
16 Godot-generated UI SVG import-metadata exceptions: only modified files from
the fixed allowlist, literal-only parsing without Godot Object/Resource
constructors, and destinations confined to the imported texture cache. Their
recorded source blobs and SHA-256 values must remain identical across replay.
This does not admit arbitrary tracked source or cache changes.

The rerun split evidence into independently retrievable bundles below the
32 MiB retrieval limit; source inputs stayed unchanged. Retained ZIP identities:

| Artifact | SHA-256 |
|---|---|
| Receipt, `11666752931` | `42eb28349d221e4edcc1164cbd56cd10a91bb05dee71b6f8a2ea5001502edc47` |
| Run A, `11666718117` | `412b2dec7e6936772fdc237bad7698da04b78f7a4f08e316ac48ed3b48682b1e` |
| Run B, `11666792983` | `bae3c93744afbb63595f7fb32455c8d099ba3d584c42191e4dd2cd5f0eca7e08` |

The preceding [run 38045298256](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045298256)
at `0f1836b00915a193517b7897b019fe8853648dbc` also completed 37 discovered
Windows tests: 35 passed, 2 Windows symlink-permission cases skipped; both
renders passed. Its console pins raw receipt SHA-256
`e4f3443223997e9acbb33822b1810f7f1d2270d905d545b04c7c7a5e35503b96`;
its combined artifact exceeded the retrieval limit. The latest downloaded run
above is the primary source evidence.

## Installed material API evidence

[Declaration run 38044121552](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38044121552)
at `a592f72e5f701e761da6451315fa2ade01c7bb71` read the installed UE 5.8.2
CL 56702186 native `MaterialInstanceTools` source. It established all **17**
declarations without a truncated index; the declaration source SHA-256 is
`abad1c2401323a91e8c760c82184b3918f35581b57e8773493f47f45b1dbc573`.
This was source-only inspection, not runtime schema verification or execution
of those tools. MCP stayed stopped and `material_authoring_admitted` remained
false.

The stock setters do not establish YACS slot ownership, source conservation or
rollback guards. Generic stock material mutation is therefore not admitted.
Reuse the existing fixed [Material Forge importer](../../scripts/ue/import_material_forge_variant.py)
within the scoped policy, initially with `save_assets=False` and 400 cm
world-aligned projection; actual road-specific native proof is still required.

## Validation contract and next gates

1. Authenticate retained graph, map and provenance/validation/render/decode
   receipts with [the source checker](../../scripts/assets/road_material_contract.py).
   Its read-only contract does not independently prove two-run replay or tool
   binaries; [the replay producer](../../scripts/assets/run_road_asphalt_source_proof.py)
   supplies those separate checks. Both retained rerun bundles and the top
   receipt passed these source-stage checks; preserve their pins for handoff.
2. Run [the read-only baseline reader](../../scripts/ue/read_road_material_baseline.py)
   in a fresh isolated native session against the exact staged #363 consumer.
   Verify source/consumer conservation, actual road/support slots and native
   projection functions. Its candidate expects one road, 186 supports and 1024
   Landscape components; these counts are not new executed-baseline proof.
   The reader explicitly leaves full mesh geometry/normal/UV hashing unverified.
3. Establish actual surface ownership and the required geometry/normal/UV
   conservation before bounded base-material assignment. Prove shader,
   400 cm projection, DirectX normal, parameter readback and restoration on the
   actual road/shoulder consumer. Never replace support sides indiscriminately
   or cover unresolved CUT/contact/seam defects.
4. Inspect both travel directions, bends, shoulder/wall separation and the
   Landscape transition. Then retain actual save, fresh reload/render and
   whole-area images for the existing network and approximately 4.07 km²
   working area, with technical review and protected CI. Keep source geometry,
   physics and authority unchanged; future wetness compatibility does not
   implement weather.
5. Retain `PENDING_FINAL_M3` until the owner's final assembled-world audit and
   `performance_pass: false` until the later reference-PC benchmark actually
   passes. Neither source tests nor a protected merge can manufacture those
   admissions.

### Bounded asphalt-only material binding candidate — 2026-10-10

`scripts/ue/road_asphalt_slot_canary.py` adds a small native-session library for
the **asphalt road actor only**. It consumes the independently authenticated
two-run `aged_mountain_asphalt/base` source bridge and reuses
`import_material_forge_variant.import_variant(..., save_assets=False)`
with metric `TileSizeCm = 400` and DirectX normals. The candidate requires
the accepted one-road / 186-support / 1024-Landscape inventory and the pinned
road's 856,250 vertices and 1,711,760 triangles. It does not author road
geometry, Landscape layers, shoulder materials or retaining-wall slots.

A transient test sets **only road material slot zero**, reads back the bound
Material Instance and verifies that the native actor/mesh/collision/Landscape
snapshot differs only in that named road binding. It always attempts to restore
the original material and checks complete pre/post snapshot equality, including
all 186 supports. A failed assignment, changed source or unexpected shared
support binding fails closed. No package or map saving is performed; unsaved
candidate assets are confined to a distinct `/Game/Generated/YACS/RoadAsphaltCanary`
namespace.

This is a **code/test candidate, not completed Unreal validation**. The existing
read-only native baseline must pass independently before the candidate is wired
into a serial isolated Editor proof. Geometry/normal/UV hashes, native shader
compilation, material projection, visual review, saved/reloaded consumer,
roadside shoulder/wall separation and whole-area admission remain pending.
No bypass of the existing active-cache trust gate is authorized.

## Cache provenance gate — 2026-10-10 follow-up

At HEAD `17a1142825fa8794f3ef661731d6df21299accda`, [protected CI run 38055292848](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38055292848)
passed the hosted tests but stopped its normal Unreal lane **before Editor**:
the physically checked-out compile/proof source bytes did not match the hosted
exact-SHA fingerprints. A Git status clean check and C#/PowerShell-only raw
source correction did not cover every fingerprint input. This is a preserved
failure, not a native material PASS.

This revision adds a **read-only full fingerprint-input raw Git comparison**
during cache selection, including native C++/project/plugin/config and explicit
Automation tooling inputs. Source mismatches and unverifiable input inventory
force the already-established fresh isolated checkout fallback while preserving
the old cache pointer, original binaries and original verified state. The
normal CI must then pass real build/Automation before publishing the new
pointer. The separate #364 native reader remains fail-closed and can run only
after successful exact-SHA protected CI. No geometry, Landscape or road physics
authority is changed.

`PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3` /
`performance_pass: false`. No native material import/road authoring claimed
until actual evidence exists.


## Native retry 38056671833 and proof-retention repair candidate — 2026-10-10

[Protected exact-head CI 38056675118](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38056675118)
succeeded at `3262a7529c97e1ed34f1ba5a436c2b84e06db55d`, including Windows Unreal
build/Automation, verified cache publication and the Aggregate gate.
The independently gated [native read 38056671833](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38056671833)
**FAILED before Unreal launch**. Its fixed Windows reader checks completed
(12 tests, one permission-dependent skip), then the runner raised `Get-Item`
at `Invoke-YacsRoadMaterialBaseline.ps1:64`: the active cache no longer held
`Saved/RuntimeProof/CI/Unreal/unreal_ci_summary.json`. The normal CI cleanup
explicitly removes current-run RuntimeProof files after cache publication,
while preserving `Saved/BuildCache/UnrealCi`. A green normal CI is not a
successful native scene read.

This candidate closes that lifecycle mismatch without loosening provenance:
normal CI `Record` retains the **actual** bounded, green exact-HEAD Automation
summary as a content-addressed immutable file under the existing preserved
build-cache namespace and records its SHA-256/byte size in verified state.
Cache selection and static proof reuse reject missing/tampered/incorrect-HEAD
retained summaries; older cache state must run real Automation again, then
record authentic proof before native reuse. The #364 native reader independently
checks the pinned bytes and green original proof head instead of expecting
a transient file deleted by normal cleanup. No synthetic summary, cache pointer
override, foreign worktree, new geometry/material binding, or owner-project
mutation is authorized by this fix.

**Status of this candidate:** source implementation/tests submitted for
protected verification. New exact-SHA normal CI, retained-summary admission,
fresh native reader and subsequent asphalt canary are **NOT YET VERIFIED**.
Owner visual `PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3`,
`performance_pass: false`. PR remains Draft until stage-specific evidence.

## Native stage failure at 5a4a9c1b and bounded checkout-path correction — 2026-10-10

[Exact-head protected CI 38058686733](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058686733)
PASSED: Windows Unreal Automation, authenticated cache proof retention and
Aggregate CI. The separately gated
[native attempt 38058683514](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058683514)
**FAILED during accepted-consumer staging, before launching Unreal**.
[Artifact 11672726865](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058683514/artifacts/11672726865)
retained complete host receipt, pinned original green Automation summary,
static/none cache resolver and the `accepted-consumer-stage-stderr.log` showing
`_hydrate_dependencies -> _verify_rows: ValueError: accepted asset bytes differ`.
The verified fingerprint/cache/proof gates passed; the staging error does not
authorize altering any source hash or marking the native read as PASS.

A scoped Windows MAX_PATH hypothesis is supported by the exact dependency tree:
five frozen limestone palette `.uasset` paths exceed **260 characters** when
prefixed by the original 99-character isolated Actions checkout root; the
longest reaches **268 characters**. The LFS process returned without a
diagnostic path, so this remains a **hypothesis**, not a proven mismatch
identity. This candidate shortens **only** the separate native Actions
checkout directory to `rm-<run>-<attempt>`, keeping the real workspace,
isolated source/exact SHA, protected cache, Git/LFS checks and accepted
assets unchanged. A hosted contract test covers the exact old-vs-new Windows
path lengths and the wrapper/workflow binding. The common stager now includes
the exact relative path and expected/observed byte identities when a hydrated
file mismatches, without skipping or rewriting it. Its synthetic test confirms
the error remains fail-closed and preserves the original wrong bytes.

**Candidate status:** awaiting protected tests and a fresh independent native
staging/read result on the new exact SHA. No native scene/material admission,
saved consumer or geometry change claimed. PR remains Draft; owner visual
`PENDING_FINAL_M3`, FPS `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Native LFS checkout diagnosis and offline hydration repair — 2026-10-10

[Native run 38061545088](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061545088)
at `e950d6b19fd721fff4bbc699ec03b9c919d4b2a1`
**FAILED during dependency hydration, before Unreal** despite
[exact-head protected CI 38061548431](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061548431)
passing. [Artifact 11673397029](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061545088/artifacts/11673397029)
identifies `Content/Generated/YACS/MaskReview/M_MaskReview_1.uasset`
(expected 11,780 bytes, SHA-256
`0d6a1a6061fd8922b44f6c7ae7d49b9219182149deed1cca42d5f4c0d2047068`)
as still the **exact committed 130-byte Git LFS pointer** (SHA-256
`00a8cfcafa5946a7c7ca36b70463c34bc9dc2bee1328f72a6bd8c6e8cfc20229`).
This source is short, so the previously suspected long-path boundary
**does not explain the observed failure**. Short isolated checkout remains
a harmless Windows path safety improvement, not an admission claim.

The active original asset cache, original Automation summary and exact source
fingerprints were all verified and unchanged. The current repair candidate
initializes Git LFS filters **locally inside only the fresh code-only checkout**,
under the isolated Actions Git environment, with automatic smudging disabled.
It then performs bounded batches of explicit-pinned `git lfs checkout`
against the already SHA-256-checked offline cache, verifying each batch before
continuation. No remote fetch, arbitrary input, silent overwrite of modified
owner assets, geodata/geometry change or weakened hash guard is introduced.
A synthetic test exercises missing local filters, empty global/system config,
skip-smudge and multi-batch hydration before comparing original bytes.

**This is a candidate, not evidence that the native stage now passes.**
Both new exact-SHA CI and the independent native rerun remain required.
The #364 asphalt canary, saved/fresh-rendered consumer and final owner
visual audit remain pending. Performance stays `DEFERRED_AFTER_M3` /
`performance_pass: false`.

## Real native map read and bounded redirected-log teardown fix — 2026-10-10

[Normal exact-head CI 38062379452](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062379452)
**PASS** at `50d02fa69bdf4bbbe5679759245672621bec9d90`.
[Native run 38062375118](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062375118)
**FAILED on host receipt teardown**, but notably progressed through the
previously failing LFS stage and an actual native Unreal Editor read:

- [Retained artifact 11673672792](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062375118/artifacts/11673672792)
  contains `session-preparation.json` with status
  `ACCEPTED_CONSUMER_BYTES_STAGED` (236 dependencies, 14 consumer assets),
  `road-material-baseline.json` with
  `ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE`, and original Editor logs.
- UE **5.8.2-56702186** genuinely started on the frozen saved derived consumer,
  MapCheck finished with **zero errors and warnings**, and the native reader
  reported **1 road, 186 supports, 1024 Landscape components**. The owned
  Editor returned exit code **0**.
- Reader receipt recorded `read_only: true`,
  `pre_post_inventory_equal: true`, `saved_asset_bytes_unchanged: true`,
  `persistent_world_mutation: false`, `material_authoring_verified: false`,
  `full_mesh_geometry_hash_verified: false`, and correct M3 deferrals.
- **The overall native job did not pass**. Host receipt `status: FAILED`,
  `reader_pass: false` after Windows rejected hashing the two redirected
  `owned-editor-stdout.log` / `owned-editor-stderr.log` files while still
  open by another process. The wrapper's fail-closed finalization correctly
  rejected partial evidence. No accepted native stage/merge is inferred.

The scoped repair adds a **bounded sharing-violation-only retry** for the
real redirected Editor stdout/stderr identity reads, up to forty attempts
with 250ms pauses (no new process launch or output mutation). Every log
must still hash successfully with its existing 64MiB bound and stable
size/mtime check. Non-sharing failures fail immediately; persistent locks
still FAIL the host receipt. A dedicated actual PowerShell function test
exercises transient success, immediate unrelated I/O rejection and bounded
persistent failure. The current document section is a candidate pending
protected exact-head CI plus a **separate independent native rerun**.
Owner visual `PENDING_FINAL_M3` and performance
`DEFERRED_AFTER_M3` / `performance_pass: false` remain unchanged.

## Correct native road support label boundary — 2026-10-10

The authenticated [native baseline from run 38063289931](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063289931)
records exactly 186 supports named `YACS_PERSIST_SUPPORT_000` through
`YACS_PERSIST_SUPPORT_185`, not `001` through `186`. The synthetic
transient asphalt canary still expected the latter and would falsely reject
the accepted frozen scene. This correction makes the material-only canary
use actual native saved actor labels; it changes no scene, topology, Physics
Profile, Landscape or support material ownership. A new exact-range and
out-of-range regression is included; native asphalt assignment remains
**NOT VERIFIED** until an actual separate editor run.

## M3 asphalt on accepted road — bounded transient native execution candidate

The owner resumed #364 after the exact-HEAD green
[CI 38063294944](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063294944)
and independently green
[native baseline 38063289931](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063289931)
at `229c4e416f7149fd1a6ae383ae0fe31a7547f21b`.
The actual captured native scene has one road (856,250 vertices,
1,711,760 triangles), 186 **zero-based** supports and 1024
Landscape components. The baseline is source/geometry read only.

This **implementation candidate**, in the same #364 Draft PR, adds:

- `scripts/ue/road_asphalt_source_preflight.py`: separately verifies the
  retained two-run `aged_mountain_asphalt/base` producer bundle from exact
  source `6fa54b50` and original run `38045485913-1`, pinned original
  receipt SHA-256 `3626bf85…`, source fingerprint `b4d93e24…`, and
  graph `6b381516…`. Missing retained source is a hard failure: no
  implicit re-render, download or loosened hash check.
- `scripts/ue/run_road_asphalt_native_canary.py`: independently rechecks
  the staged consumer, original producer bytes, projection
  `WorldAlignedTexture`/`WorldAlignedNormal`, original road/side materials
  and the exact saved scene; reuses the existing Material Forge importer with
  `save_assets=False`, world alignment 400 cm and DirectX normals. It
  temporarily swaps **only the road material slot zero**, verifies material
  readback and the complete actor/material/geometry snapshot, restores the
  original slot even on failure and verifies input packages unchanged.
- `scripts/ue/Invoke-YacsRoadAsphaltNativeCanary.ps1`: a **second,
  separately owned Unreal Editor process** only after the existing complete
  read-only native baseline passes in the same isolated Windows checkout.
  Authentic original baseline hashes, exact source SHA, approved engine/DLLs,
  the trusted host lock, bounded process lifetime and exclusive proof files
  remain mandatory. Actual-run logs and trial receipt are retained.
- Synthetic source, native entry, slot ownership and host/workflow tests.
  Source `YACS_PERSIST_SUPPORT_000..185` identity is corrected; no geometry
  mutation or support-side material replacement is allowed.

The first native canary intentionally runs with `-NullRHI` to validate the
Material Editing API, importer graph and reversible native slot binding
without claiming GPU shader compilation or a rendered appearance pass.
`shader_gpu_compilation_verified: false`,
`saved_consumer_verified: false`, `owner_visual_status: PENDING_FINAL_M3`
and `performance_pass: false` remain binding. Actual native canary success
requires an independently completed exact-SHA workflow and readable
`road-asphalt-canary.json` **plus** `asphalt-host-receipt.json`; source,
synthetic tests or a green regular Unreal build alone never admit this stage.

Future #364 batches must separately prove real shader output, authored
shoulder-top/wall slot separation, a new saved material-only derived consumer,
fresh reopening and review frames from both road directions. Do not merge until
all applicable technical/review gates and final M3 owner audit policy are met.

## Transient Unreal Python bootstrap correction — 2026-10-10

[Native #38065442572](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38065442572)
at `99da397bf880d9d4a68449d7bc1c2bc7404dd580` **failed** in its second
Editor process, after the complete read-only baseline PASS. The retained
[artifact 11674572801](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38065442572/artifacts/11674572801)
confirms that `asphalt-source-preflight.json` succeeded with two pinned original
renders and that the Editor launched. Its actual `asphalt-editor.log`
records `ModuleNotFoundError: No module named 'scripts'` at line 17 of
`run_road_asphalt_native_canary.py`. Unreal's `-ExecutePythonScript`
does not automatically add the script's repository root to Python's path.
The Editor exited 3; no material import, assignment or rollback was observed.

The corrective candidate inserts only `Path(__file__).resolve().parents[2]`
into the transient script's Python search path before any repository imports.
The host continues to verify exact committed script bytes and isolated checkout.
A hosted regression executes the real Python entry with `-I` and an unrelated
working directory, with no ambient project import path; it never starts UE.
Source, map, material and geometry inputs are unchanged, and no success is
claimed until a fresh exact-SHA CI and independent native Editor trial pass.

## Saved road-asphalt derivative and independent fresh-reload candidate — 2026-10-10

This stage follows the verified [native road-slot-only transient PASS
38066292810](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38066292810)
at exact SHA `4f11e0dadf3ac099e49402ca69f319c592052dd0`
and its [protected green CI 38066296977](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38066296977).
The new implementation is **not yet native-admitted** simply because its
source has been committed.

- `scripts/ue/road_asphalt_saved_consumer.py` is the bounded two-action
  Unreal entrypoint. In `prepare`, require the original pinned source replay,
  real accepted saved scene, native baseline and rolled-back transient canary.
  Reuse the verified Material Forge importer with `save_assets=True`,
  metric 400 cm projection and DirectX normal settings, bind only the
  original road DynamicMesh material slot zero and save **only** the new
  `/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview`
  map. Verify the complete old/new actor, road mesh, all 186 supports,
  Landscape 1024 components and other material bindings remain identical
  apart from road material slot zero. Verify immutable source/retained
  producer bytes before/after. Preserve new files with exact SHA-256/byte
  sizes in `D:\yacs\work\road-materials\saved-consumers\<sha>\<run-attempt>`.
- In `reload`, a **separate fresh Editor process** loads the new saved
  map, never reassigns or saves a material, checks the same normalized
  inventory digest and all four real Material Instance texture parameters,
  effective `TileSizeCm=400` and DirectX normal compression/green/sRGB.
  The original map and derived packages must still match their raw SHA-256
  and byte-sized immutable manifest. No rolling back the **new saved**
  material binding: the original accepted map is not modified.
- `Invoke-YacsRoadSavedConsumer.ps1` owns serial, isolated,
  exact-HEAD/host-lease authenticated **prepare -> reload** Editors.
  The existing successful baseline and transient canary must precede
  either process; both actual native receipts and stdout/stderr/Editor
  logs are mandatory. The host writes a separate exclusive
  `saved-road-host-receipt.json` only after both operations.
- New offline synthetic tests cover world-identity-only normalization,
  original/support/Landscape mutation rejection, no-overwrite package
  retention and mandatory source/workflow boundaries.

This candidate intentionally uses `-NullRHI`: it is **a saved native
binding and reload test**, not a claim of GPU shader compilation,
high-quality rendered pixels, whole-area shoulder/wall transitions,
owner visual PASS or final material delivery. Owner audit
`PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3` /
`performance_pass: false`. PR #470 remains Draft and #364 remains OPEN
until the further roadmap/native/asset/render/review gates pass.
