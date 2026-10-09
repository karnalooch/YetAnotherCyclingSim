# Sa Calobra material repair: implementation and recovery checkpoint

Date: 2026-10-06. Issue #363; draft PR #381. This is a retained work checkpoint,
not visual acceptance, performance admission or a merge-ready declaration.

## Outcome

The work produced a more precise projection/normal diagnosis, corrected weight
composition, saved candidate assets, comparison renders and a safer way to prepare
one material outside the owner editor. The intended finished Mallorca appearance
has **not** been delivered. The current surface still looks too soft and often
yellow-green; vertical artifacts are not fully resolved. No 60 FPS claim is made.

## What worked and what the evidence actually proves

| Area | Verified result | Limit |
| --- | --- | --- |
| Frozen scene | Accepted map SHA-256 remains `276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c`; bounded actor-transform, component, layer and nine collision-trace snapshots matched during application | This is not an exhaustive triangle-by-triangle proof for the new material |
| Installed native functions | Inspected the UE 5.8.2 graphs: WorldAlignedTexture's surface normal participates in blend weighting; WorldAlignedNormal's Normal input is tangent-space and is transformed internally | Generic documentation wording alone was insufficient; conclusions are pinned to the inspected version |
| Projection comparison | Native, geometric and mixed checker captures completed; geometric/mixed direction reduced visible stretching on steep walls | Some faceting remains; no complete seam/motion acceptance |
| Layer weights | Default exponent 1 preserves minority base classes; slope replacement defaults to zero; independent scree A is applied after base normalization | Source classification remains candidate geography, not validated vegetation placement |
| Weight tests | Six tests pass, including minority preservation, independent A, residual mineral, bounded slope, randomized normalization and invalid input rejection | Tests validate the reference weight math, not every compiled GPU expression |
| Surface graph | Five domains, macro/meso/micro scales, tangent-space normal handling and bounded scalar controls implemented | A compiled/saved graph does not prove acceptable appearance |
| Saved first candidate | All 17 asset hashes matched the receipt after the crash | This candidate predates the later parameterized graph; do not conflate versions |
| Area observations | Weight/neutral/flat/candidate comparisons and nine ground views captured | These are diagnostic observations, not a whole-area PASS |
| Offline preparation | One parameterized material was prepared and saved by an isolated NullRHI commandlet without loading/saving the accepted map | NullRHI cannot establish render correctness. Unhydrated unrelated LFS packages emitted registry errors; this was not a clean full-project validation |
| Bounded live preview | New material instance assigned to exactly LandscapeComponent_260; other overrides/global binding and bounded geometry snapshot checked | Only one component; current render-parent native audit and fresh-process reload still pending |
| Parameter editing | Scale/tint changes use a material instance; scalar/vector values read back successfully | UE's scalar setter returns false unconditionally in this installed source; return value alone is not a success test |

## Versions and saved state

The first saved candidate is under MaterialRepair `a941b778c0474e3b8faaf4ac5cca215f`.
Its material hash is `4282e0a8ade091194d5346e25fe70b8adf3cdd31382b98a0be5149ae1b074560`.
The 17-file receipt is `worldgen/materials/sa_calobra_repair_asset.json`.

The offline parameterized candidate is under MaterialRepair
`5e717564dbc449a89b766ff75949037e`; its material hash is
`cdb65133c1c516e59ecda27b3ff64942d11e89d99323a451be1cf1aa1ea06ae5`.
The separate offline receipt pins its producer and input receipt. A saved preview
instance retains GroundMetres=3, RockMesoMetres=8, NormalStrength=0.25 and the
subsequent tint experiment. See `saved-patch-instance.json` for identity/tints.

Neither variant overwrote the accepted map. The live single-component override
is a session preview; the saved instance does not make that map binding persistent.
Do not use Save All to turn an experimental override into the accepted checkpoint.

## Crash and recovery

At 04:58:31 UTC UE failed in D3D12RHI with “Out of video memory trying to allocate
a rendering resource”. This followed a live full-Landscape rebuild after several
heavy material iterations. Earlier in that session GPU timeout warnings and very
high process memory had already occurred. The final rebuilt graph was not saved.
The evidence identifies allocation failure, not a proven driver defect.

Crash reports, full local logs and autosaves were retained before reopening.
The original accepted map was reopened and the saved asset hashes were verified.
The repair entry point now rejects `rebuild_candidate`, `surface_review` and
`bounded_residency`. This is a guard against repeating those actions, not a
general guarantee against memory exhaustion through every historical script.

Offline graph preparation and a one-component preview subsequently completed.
An observed GPU reading was about 3.6/8 GB. That single reading is neither peak
memory proof nor a performance benchmark. Full crash dumps and unrelated editor
telemetry remain local; the repository contains relevant filtered excerpts.

## Texture sharpness: corrected diagnosis

An early inspection showed nine resident mips on 4K/2K source textures, whose
largest resident level was 256x256. Installed Landscape code only recognizes
certain direct coordinate/sample patterns for its texture scale metadata. This
made streaming a plausible hypothesis, not an established root cause.

Later, with a closer camera, `InvestigateTexture T_aerial_grass_rock_diff` reported
current **and wanted 4096x4096**, a dynamic reference to component 260 and no mip
bias for that asset. The pool was approximately 190.36/600 MB, with 336.07 MB
non-streaming mips. The soft appearance therefore cannot be attributed solely to
a full pool or permanently missing top mips. Do not increase the pool or disable
streaming on the strength of the earlier observation. Global quality settings
were not changed by these experiments.

## What failed or remains unresolved

- Full-Landscape live batch iteration was not operationally safe on this machine.
- The final visual appearance is not accepted: soft detail, unwanted warm/green
  blending, remaining vertical artifacts and local faceting need controlled review.
- Neutral color with flat normals still exhibited some vertical structure. This
  limits what can be attributed to texture normals alone; it does not authorize
  changing the frozen terrain or lighting.
- Earlier historical previews contain superseded approaches, including aggressive
  slope replacement and incorrect normal-space assumptions. Retention is not endorsement.
- The 2K forced-residency experiment was not saved as a delivered fix and did not
  establish sufficient visual improvement. The later live rebuild was lost.
- No fresh rendered reload, full 1024-component native parent-chain audit, whole-area
  visual acceptance, exact-commit GPU benchmark or protected CI closeout exists for
  the latest candidate. Previous-version proofs must not be relabeled as current.

## Next work, in execution order

1. **Pin one candidate and camera set.** Use the saved parameterized parent and
   one instance. Record values, asset hashes, scene baseline, quality and memory.
   Keep shader preparation outside the full live Landscape; no automatic batch retries.
2. **Complete projection and normal acceptance.** On slope, vertical face and their
   transition, compare a metric checker and fixed-camera flat/weak/target normals.
   Require stable metric scale, no texture stretching/seams and acceptable motion.
3. **Validate compiled weights.** Compare raw R/G/B/A and final contributions with
   the reference math. Preserve minority vegetation, residual mineral and independent
   scree. Separate projection direction from any optional slope art rule.
4. **Resolve softness with evidence.** Capture texture residency at the actual
   capture time, inspect sample scale and blended color at close/road/far distances,
   and change one parameter at a time. Avoid treating the streaming hypothesis as proven.
5. **Tune limestone and ground.** Establish neutral pale-grey rock, readable meso
   fractures and restrained microdetail; reduce muddy color blending while retaining
   the source mask semantics. CC0 aerial scans are references, not local geological proof.
6. **Prove a fresh saved consumer.** Save a separate review map, never replace the
   accepted map implicitly. Reopen in a fresh rendered process; verify all 1024 native
   material parent chains, frozen-scene contract and exact asset hashes, including
   negative controls. The old isolated proof is not transferable.
7. **Measure whole-area performance.** At 1920x1080 use the agreed representative
   views/traversal and both frame/GPU timing: p95 <=16.667 ms and <=5% over budget.
   Missing GPU timing fails admission. Record actual host hardware; this run's log
   reports an i5-9600K, which differs from the stated i5-10th-generation target.
8. **Close out only after gates.** Obtain owner visual acceptance, pass required
   checks on the delivered commit, keep PR #381 draft until ready, and leave #363
   open. #384 and #364 remain dependent work, not part of this checkpoint.

## Remote retention and reproduction limits

The checkpoint retains all 329 initially inventoried modified/untracked project
files either at their project path or as exact local variants under
`sa-calobra-material-repair-20261006/local-versions`. Newer published code is
preserved where a local version would roll it back. The local project descriptor
and editor permission/preferences file are archived, not activated elsewhere.
The mapping is in `local-versions.json`; original sizes/hashes are in
`local-inventory.json`. Assets and evidence images use Git LFS.

Additional retention includes the later saved preview instance, the MaterialRepair
evidence directory and six hash-verified CC0 source PNGs. `source-backup.json` maps
their portable repository paths to the original URLs and hashes. Historical scripts
still contain machine paths and some reference ignored local proof files. A clean
clone is therefore a recoverable research checkpoint, not a one-command reproduction
or a production material release. Reconcile paths and source/version contracts before
replaying a historical script; do not bypass its integrity checks.

Engine installations, compiled binaries, caches, raw crash dumps, authentication
state and full editor autosave history are not repository payloads. Their local
recovery copies remain intact. No generated geometry was re-created for this backup.

Evidence: [retained records](sa-calobra-material-repair-20261006/evidence/),
[local variant mapping](sa-calobra-material-repair-20261006/local-versions.json),
[repair plan](../tooling/SA_CALOBRA_MATERIAL_REPAIR_PLAN.md).
