# Natural20 contact checkpoint — #365 / M3

**Measurements complete; all 100 cases REJECTED. Fresh aggregate process failed;
terrain renders NOT RUN.** This packet is a transfer checkpoint, not completed
asset qualification or world placement. Start continuation from
[SESSION_HANDOFF](SESSION_HANDOFF.md).

Native producer: `1a02ac21a7fb1dbc84364843e862b186a2ea0a18`.
Retained stage: `D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04`.
The twenty meshes are derivatives of eight licensed scans, not twenty independent
scans. They use the existing Material Forge V2 appearance without world displacement.

## Verified result and failed boundary

Run04 completed six actions with real exit 0: inspection, material save and fresh
readback, twenty-mesh save and fresh readback, and `collection-contact-all`.
The last action measures all ten batches in **one editor process**, with one
authentic completion marker. There are no fabricated per-batch process markers.

The subsequent `collection-contact-reload` wrote a consistent 100-case aggregate,
but UE PID 8268 exited `-1073741819` (`0xC0000005`, access violation). Launcher
line 421 rejected the process; no completion marker exists. The pipeline stopped
before `collection-contact-render`: **zero new terrain PNGs**. A receipt or normal
log closure does not establish process success. No faulting module/root cause
was established; grouping is not a claimed AV repair.

[Independent readback](READBACK_AUDIT.md) used UE's Python 3.11.8 to recompute
200 raw grids, 361,350 support rows and 170,050 rejected/paired-miss rows, then
all decisions, with **zero discrepancies**. Each mesh failed all five sites.
Failures overlap: excessive embedding 100, insufficient exposed height 100,
excessive slope 94, insufficient exposed rays 99, root convergence 77 and
embedding convergence 93. See [summary](summary.json) for individual mesh rows.

The coordinator separately rehashed all 20 saved meshes, seven Forge packages,
202 terrain packages and all 200 raw grids. The full raw and receipt copies are
lossless deterministic gzip (`mtime=0`); [evidence-index](evidence-index.json)
records original/compressed sizes and SHA256. Host editor logs remain at their
retained stage paths, with hashes in the index. No UE cache, uasset or source FBX
is copied into this documentation packet.

## Unchanged authority and scope

The authenticated terrain closure contains 202 packages / 243,104,471 bytes:
the original 14 plus 185 checkpoint CUT textures and three accepted material
instances. Contract SHA256:
`893dce21f8f31c63815bfaf2d559656ef8905894b6264f33e100c1d3149dc6eb`.
The map remains 185,187,721 bytes, SHA256
`bf2b92945865e2307990b6d3da40095dfa0774d28affb32a1e42e55f288764dd`.
Source catalog SHA256:
`3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc`.
Source and stage bytes were independently checked; 198 canonical packages match
their Git LFS pointers and four are from the retained accepted consumer.

Landscape file and transforms remain unchanged. No map save, Landscape/Base_DTM,
road, grid/georeferencing or route/physics edits occurred. The #363 Landscape
consumer does not establish parity with the latest #364 road checkpoint.

The frozen policy stays scale 1, yaw/tilt 0, slope at most 10 degrees, embedding
at most 20% of AABB height, exposed height/rays at least 80%, zero positive sampled
bottom gap, complete actual Landscape collision coverage, and root/embedding
convergence at most 0.1 cm. Grids 33/65 are mandatory; 129 is allowed only when
convergence is the sole failure. Nothing was relaxed to obtain a passing result.

The five sites retain `NOT_ADMITTED_VEGETATION_SELECTOR_DIAGNOSTIC` semantics;
per-mesh World Authority mask/exclusion coverage is unproved. The new consumer
checks actual Landscape actor/component ownership but did not repeat the old
all-actors-ignored negative control: **NOT RUN**, not inherited PASS. Source-cap
planting, Q90 poses, physical stability and continuous support also remain NOT RUN.
The [source support audit](SOURCE_SUPPORT_AUDIT.md) describes possibilities, not
additional work performed. The [contract audit](CONTACT_CONTRACT_AUDIT.md) is
historical preflight context.

`qualified_assets: []`, `placement: false`, `full_qualification: false`,
`PENDING_FINAL_M3`, `DEFERRED_AFTER_M3` and `performance_pass: false` remain.
The twenty meshes total 1,162,056 LOD0 triangles (11,178–103,250 each); this is
not an RTX 2070 FPS result or an optimized LOD chain.

## Retained attempts and restart reduction

- Run01, producer `aff7fdc6`, used an incomplete map with 188 missing packages.
  Batch 00 exited with AV, batch 01 with zero; neither proves complete-terrain contact.
- Run02, producer `d0e76c60`, completed preparation and batches 00–03. Batch 04
  wrote data then AV; later actions did not run.
- Run03, same producer, completed preparation and batches 00–06. Batch 07 wrote
  data then AV. Remaining independent batches 08–09 subsequently exited zero.
  It has 100 raw cases but no valid whole-chain aggregate/render.
- Run04 completed all 100 measurements in one process. Its fresh aggregate
  process failed as described above. Failed outputs were never replaced/promoted.

The implemented [batch grouping](PROCESS_BATCHING.md) removes restarts between
contact batches. The owner's latest instruction additionally minimizes the
whole workflow. The [three-session plan](RESTART_MINIMIZATION_PLAN.md) preserves
real fresh consumers and clean producer exit gates. This was **NOT IMPLEMENTED
at the original handoff**, but a subsequent three-session code candidate was
committed in [`f4d6c0ce`](https://github.com/karnalooch/YetAnotherCyclingSim/commit/f4d6c0ce4eeab8c2ed57280332dc97bfc7a84148),
with source corrections continuing on Draft PR #474. Three-session native
execution, clean exit proof and forty real Landscape frames remain **UNVERIFIED**.
The previous native producer remains `1a02ac21`; do not relabel it as new proof.

## Validation and delivery

26 scoped CPU tests PASS: contact 14, frozen policy 7, collection catalog 5.
Ruff, PowerShell parser and source diff check PASS. Initial sandbox test invocation
had an import-path error and temporary-directory access problem and was interrupted;
the corrected host invocation passed. These checks cover the implemented batch
grouping, not the proposed three-session workflow.

Final documentation links/i18n/structure/freshness and transfer diff checks are
recorded in [SESSION_HANDOFF](SESSION_HANDOFF.md). Exact producer and delivery
heads are distinct. Current-head native build and protected delivery CI are not
claimed by these retained binaries; #365 remains open and PR #474 stays Draft.

The owner subsequently requested uploading this complete work to the existing
remote branch and continuing in a new ChatGPT Chat. The transfer includes the
code history, portable evidence and handoff; external runtime/source data remain
hash-pinned local dependencies. Previous [studio renders](../pcg365-natural20-20261012/README.md)
remain studio-only evidence and are not substituted for the missing terrain views.

Process grouping reuses existing YACS proof invariants and Gumball admission boundaries;
no new shared-platform invariant or separate proof framework was introduced.

## Implementation after this retained transfer checkpoint

The [minimum-restart plan](RESTART_MINIMIZATION_PLAN.md) now has a bounded
post-transfer implementation candidate, with three actual UE process boundaries,
no intermediate per-batch process marker, and hash-bound grouped phase receipts.
A separate [opt-in native workflow](../../../.github/workflows/pcg365-natural20-contact-proof.yml)
requires successful exact-head CI and Blender proof before host acquisition and
native execution. This document's historical run01-run04 findings remain
unchanged. New captures must be inspected from actual PNG bytes and a clean
native process exit; neither is recorded here yet. `qualified_assets: []`,
`placement: false` and `performance_pass: false` remain authoritative.
