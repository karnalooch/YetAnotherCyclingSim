# Local source support and Remote preview — #365 / M3, 2026-10-13

Owner direction: repair contact, prepare Remote import/planting, work in
parallel, and establish spatial treatment **before placement**. P0–P4 are
accepted diagnostic anchors. Live Remote replaces separate new review renders.
Owner explicitly authorized push, CI and Remote deployment, then directed
discarding unsaved scene changes and reopening saved checkpoint v0.3.1.
Source base is `0dd86495fab674a9d6aee22ba0759539d8bd7242`. Release
`a3dcb57829fd5b89b5a7376ef05ef872690dcc27` was pushed to Draft PR #474
and installed after exact-head CyclingSim CI and Forge reference proof passed.
Merge remains unauthorized.

## Source result

Twenty new derivatives from eight licensed scan families passed synthetic
ideal-plane support diagnostics in Blender 4.5.9. Run:
`D:/yacs/work/pcg365/source-envelope20-01/`, actual exit zero. Original catalog
SHA256: `3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc`.
The launcher records the base revision and exact uncommitted producer digest;
a later commit is not relabelled as that execution revision. Portable receipts
and original hashes are in [evidence-index.json](evidence-index.json).

The source-envelope alternative resamples the visible source top and adds a
planar underside/boundary walls. It removes overhangs; it does **not** preserve
original upper triangles or UVs. World-aligned Material Forge is required.
Closed positive-volume topology, source identity, expected native bounds,
triangle counts, centroid errors and discarded cells are recorded. Centroid
error is not a continuous bound. N02_01 retains only 4,295 of 10,087 error-valid
cells: natural silhouette equivalence is unverified. All twenty remain source
candidates, not native-qualified assets. Original FBXs and terrain are unchanged.

## Remote consumer

[`rock_contact_scatter.py`](../../../scripts/live_host/recipes/rock_contact_scatter.py)
provides `import`, `plant`, `status` and `clear`. Import uses `save=False`, a
digest-specific generated namespace, exact LOD0 triangle/bounds readback, Forge
bindings and complex collision. No map or source package save occurs. Clear
cancels measurement and removes only owned preview actors.

Plant is limited to P0–P4, current-road compatibility, authenticated full-radius
exclusions and unchanged V2 65/129 contact gates. Lossless logical buffers bind
directly to original TIFF logical hashes; all existing exclusions remain.
Measurements are incremental Slate callbacks: at most 64 contact positions or 1,024 native triangle IDs per tick,
approximately 8 ms sampling budget, best effort because native calls cannot be
preempted. Initial import and proof hashing may hitch. Job acknowledgement is
RUNNING, never contact PASS; status reports progress/final cases. Fail/cancel
rolls back actors. Native responsiveness and actual-Landscape contact NOT RUN.

[`prepare_pcg365_remote_preview.py`](../../../scripts/assets/prepare_pcg365_remote_preview.py)
stages authenticated FBXs, original TIFFs, logical buffers and six exact Forge
packages. It does not touch the live project. Import-only remains the default;
explicit diagnostic requests still require the consumer's current native road
triangle exclusion for each full footprint plus 50 cm. Source masks are checked
separately; no global road/mask parity is asserted.

The six Forge packages were copied additively and hash-verified in the live
project. Five checkpoint package hashes remained unchanged. Immutable upgrade
retained the previous release. New session `20261013T100623Z-98043255276f`
opened checkpoint v0.3.1 and independently reported `LIVE_VIDEO_VERIFIED`,
current native world readback and 186 material bindings. This is not global
lighting/appearance acceptance or rock contact qualification. Independent client
`remote-deployment-a3dcb578/independent-client01/level-editor-stream-client.json`
recorded increasing video frames and complete owned-client cleanup.

Reviewed import request `716bdf6d25ae5b6b86e03b718ca5721cad9ac46d` was pushed
through the existing exact-head CI/publisher workflow. Its native CI lane failed
`LOCAL_BUSY` because the live Remote owns the shared host; publication/import
did not occur. The owner explicitly authorized a second pause and discard of unsaved changes;
the verified owned session was stopped and the host returned IDLE. Native import and placement remain NOT RUN. No map or source package
was saved. The independently authenticated next diagnostic manifest is
`9dfe907aaf438adfaa4d117c1813ec01a954447522d95ced90fe48d9bf90bf18`;
its five placement requests are not native road/contact proof. The typed request
now uses `plant`, which imports its authenticated candidates and runs native
exclusion/contact checks before any final location is applied. Publication still
requires exact-head protected CI, then the restarted independent receiver.

## Spatial plan first

Use the [source-backed spatial draft](../../experiments/sa-calobra-spatial-treatment-plan-20261013/README.md),
[surface atlas](../../tooling/SA_CALOBRA_SURFACE_DETAIL_ATLAS.md) and
[cliff/scree contract](../../tooling/SA_CALOBRA_CLIFF_EROSION_PASS.md).
Cliff/scree candidates are physical source-grid regions; observation markers
are not physical surface boundaries. The remainder is not automatically
texture-only. Scree at 24–42 degrees does not waive the rock trial's 10-degree
limit. Cliff mesh implementation remains its own scoped consumer. The five
historical diagnostic anchors are outside the cliff/scree
selectors; their explicit owner approval does not admit regional scatter. The
first requested matrix repeats smallest-footprint `rock_09_02` at five sites,
not qualification of twenty variants. Dense LOD0
scatter is unadmitted; whole-area review and later performance proof remain.

## Failed diagnostics retained

- `source-recut-support01`: N04_01 rejected all four cuts; 65% also exposed
  float32 plane/witness mismatch. `support02` freezes the native float32 plane
  before witness and still rejects every physical cut. No contact limit changed.
- All-source `source-recut-support03` was stopped after 647.016 seconds,
  exit `4294967295`. FAIL/incomplete, not an all-source qualification result.
- `source-envelope01`: source top error exceeded the fixed one-cell diagnostic
  bound. `envelope02`: diagonal corner nonmanifold walls. Final producer rejects
  error cells and erodes corner-only contacts without filling absent regions.
  Envelope03 proved one source; envelope20-01 prepared twenty. Real appearance
  and Landscape contact remain unverified.

Interactive HTML browser verification was blocked: the browser tool permits
only HTTP/HTTPS and refused `file:`. No alternate surface/server circumvented
the restriction. PNG inspection and offline tests are separate from UI proof.

`qualified_assets: []`, `placement: false`, `PENDING_FINAL_M3`,
`DEFERRED_AFTER_M3`, `performance_pass: false` remain. No #475 cleanup or
merge. Landscape, Base_DTM, roads and georeferencing are unchanged.

## Local validation

64 focused CPU tests PASS, including source topology/recut contracts, exact
mask clearance, incremental sampling budget/cancel/rollback, protocol, registry
inspection and latest-world contracts. Changed Python files pass Ruff check and
format. Documentation links, i18n, structure and freshness PASS; diff check PASS.
Twenty lossless evidence copies were decompressed and compared to original bytes.
The final import manifest is
`dd6fcb0b514d66bba6f241c114ad30a0e2e107245c5411e47285e3e8ac8ef885`:
twenty assets, zero placements. The consumer authenticated both logical buffers
(65,060,356 distance bytes; 32,530,178 exclusion bytes). This verifies staging,
not native import. Exact-head CI and new-session native world/video proof passed;
rock import/contact proof remains pending.

The map's Protected display now contains only pavement bit 1, per owner request;
remaining hard presentation exclusions are a separate default-hidden layer.
The source rules and planting restrictions are unchanged by layer visibility.

Follow-up validation: 46 focused CPU tests PASS, including triangle crossing,
nonidentity transforms, changed geometry, exact actor labels, actual native
footprint radius and separate incremental work budgets. Ruff check/format and
documentation links/i18n/structure/freshness PASS. Native rock execution remains
NOT RUN until the protected publisher and receiver complete.

Final audit follow-up: moving an earlier road actor during the final sequential
scan could previously evade its transform check. The consumer now requires a
synchronous final check of all 559 owner/transform metadata records immediately
before placement, and subscribes to native Blueprint mesh-modified events for
the complete job with explicit cleanup on completion/cancel/failure. Event or
metadata changes reject the job and roll back owned preview actors.

This does not make native geometry reads atomic. Installed UE source exposes
separate non-reflected realtime/direct/deferred C++ mutation paths which can
bypass the Blueprint event. Exclusive quiescent geometry ownership remains a
requirement throughout the diagnostic; concurrent mesh-edit tools are not
admitted. Camera observation through Remote is compatible with this requirement.

The final audit fix passed 52 focused CPU tests (27 recipe tests), Ruff and all
four documentation guards. After accepted placement, the consumer aims the
existing live viewport at the first accepted stone using its actual bounds and
verifies the camera position; this creates no render or saved map change.

## Native rollout and receiver fix

Release `2412383830d676435dba7eb5649af3838f86e570` passed exact-head CI and
Forge proof, then reopened v0.3.1 in session `20261013T105244Z-53685d72a80e`.
The real publisher workflow 38385208653 passed both source admission and
publication. Native request 000001 imported all twenty candidates with exact
LOD0/bounds readback, Forge bindings, collision settings and actual-radius
mask checks. Its receipt acknowledged a running diagnostic job with zero
placements at that instant; later contact/placement status is UNVERIFIED.

During native import UE pumped Slate and reentered the same queue request.
The second attempt to create its immutable STARTED receipt raised
`FileExistsError`; the outer import completed, but the receiver blocked. A new
independent client still received increasing video frames after the workflow
ended. This proves the live viewer survived, not that the contact job passed.
The owner explicitly authorized another discard/pause for the receiver fix;
five checkpoint package hashes were verified unchanged before stopping only
the owned offscreen Editor. No native completion or rock qualification is claimed.

The fix guards the whole queue poll and contact callback against nested entry.
A nested Clear requests cancellation and waits until the native call yields
or finishes before closing the generator and removing owned actors. Tests
reproduce nested request handling, nested generator advancement and nested
cancellation without replay or concurrent destruction. 55 focused tests PASS;
Ruff check/format, docs guards and diff checks PASS. Formatting of the two
legacy protocol files was independently checked for identical Python AST.
This receiver fix still requires protected CI and a new native execution.

## Native receiver success and transform value fix

Release `a5e2730c8954efa1d8c2387c0632431516bc785c` passed exact-head CI and
Forge proof and reopened v0.3.1 in session `20261013T111647Z-35e67509f1d3`.
Publisher 38387960838 passed. All twenty meshes imported again; the receiver
then completed request sequences 1, 2 and 3 without a blocked queue. This is
native evidence for the reentrancy fix. The contact job returned a rollback
with zero sampled positions and zero placed actors: its Landscape transform
guard compared `str(Transform)` and falsely reported a change.

Installed `PyWrapperStruct.cpp:807` formats structs as
`<Struct '%s' (%p) %s>` and assigns this formatter to both str and repr. Thus
fresh copies include different allocation addresses even with identical
values. The new guard stores exact numeric translation (cm), quaternion XYZW
and scale for Landscape, component and actor snapshots. It does not loosen
any tolerance. Tests distinguish new identical-value copies from real changes
of every transform field and reject nonfinite values. 56 focused CPU tests,
Ruff and docs guards PASS. This fix remains pending exact-head/native rollout.
The owner explicitly authorized another discard/pause; saved v0.3.1 hashes
were verified unchanged before stopping only the owned session.

## Reflected Geometry Script query correction

Release `2b7c3bfcf6d910e36199595f3fa0aa7ddb596603` passed exact-head CI and
Forge proof, reopened v0.3.1 and imported twenty candidates. The numeric
Landscape transform guard passed. The next native read rejected a missing
`DynamicMesh.get_num_triangle_ids` method; no triangle/contact samples or
placements occurred and rollback completed. Source `ScriptMethod` metadata
did not establish an instance method in this installed Python runtime.

The correction calls the installed `GeometryScript_MeshQueries` function
library explicitly. Reflected names are resolved unambiguously by a fixed
normalized token, covering the generated `IDs` / `i_ds` spelling without
inventing a method or accepting arbitrary request code. Test meshes deliberately
lack the unsupported instance methods. Review also found that the binding
generator was defined but not invoked; it is now explicitly completed before
the first triangle query, with a regression test of this ordering. 57 focused
CPU tests, Ruff, docs guards and diff check PASS. Native proof remains pending.
Owner-authorized continuation retained/discarded only the owned zero-placement
preview session after rechecking the five saved checkpoint package hashes.


## Native diagnostic completed — f0588aa2

The explicit Geometry Script library passed in session
`20261013T122444Z-7815ee9e71d4`: 559 mesh-change guards,
2,911,650 triangle IDs per scan (two unchanged snapshots), and 104,330
contact sampling positions. The final status receipt reports one transient
`rock_09_02` at P3 and verified review camera coordinates. P3 sampled maximum
local slope is 5.877836 degrees and embedding fraction is 0.169753; unchanged
V2 limits passed. P0/P1/P2/P4 were rejected for slope, embedding and exposure.
The saved map was not changed. Source `f0588aa2cb8a9362cc7e524b54d80b60e478ed39`
passed protected CI 38394970294 and recipe publisher 38394962138. Independent
post-job receiver confirmed fresh increasing video frames and cleanup.
Portable exact native receipts are indexed under `native-f0588aa2-completed`.
This is sampled diagnostic placement only: `qualified_assets=[]`, production
`placement=false`, `performance_pass=false`; owner visual acceptance remains open.


## Coarse larger variants — owner preference 2026-10-13

The owner prioritizes convincing broad shapes and final rider-view appearance
rather than intricate individual rocks. The existing source-envelope producer
now accepts bounded grid33/49/129, preserving default129 and recording the
actual grid. Four CC0 source-derived variants were generated by pinned Blender
4.5.9, with source/catalog/producer hashes retained. Execution used uncommitted
producer bytes on base `0dd3a1ca3a42e070f1370634782135f64d976148`; its recorded
script hash, not that Git SHA alone, identifies the executed candidate.

N05_01 has 3,168 triangles; N06_01 has 3,388; N03_01 has 5,640;
N04_01 has 6,320. These are 85.8–93.4% fewer than their grid129 equivalents.
All four passed source topology and analytical-plane checks. Source sampled
maximum shape errors are approximately 3.6–6.1 cm; this is simplification
error, not permission to relax native terrain-contact tolerances.

The first two are about 0.5–0.6 m high; N03/N04 reach about 1.3–1.7 m.
The conservative exclusion diameter must not be described as actual mesh width:
the earlier dense N06_01 longest AABB dimension is 1.202 m, not 1.489 m.
The four-candidate Remote stage is manifest
`2981ce1f35f60a4cd1bf9d8abd424b52b2e82241731eedd2946d482aba13bb4f`.
It recomputes source footprint exclusions and retains the original five anchors;
native cooked bounds, contact and owner visual acceptance remain required.
No native qualification or measured GPU-performance benefit is claimed here.
