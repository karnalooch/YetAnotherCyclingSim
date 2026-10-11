# Road surface visual rejection and capture-readiness repair — #364

**Milestone:** M3. **PR:** #470 (Draft). **Domain owner:** Visual & DCC.
**Base SHA:** `f9eeb02771ad036892b157059f07876a07abea61`.

## Current b9fd review — material progress and retained defects

The [current original evidence](../experiments/sa-calobra-road-materials-20261011/README.md)
comes from `b9fddea3f6023239da98bec7a5107ed1124cf52e`, successful native
run 38116299783. The live artifact digest, archive and all 629 extracted file
identities were verified. The material specialist reviewed all 68 final Lit
frames and 16 crack controls; the road specialist reviewed the new 16-view
0112 and six-view 0081 contact sets. The primary reviewer checked representative
original Lit, WorldNormal and contact images.

Dry mat/aggregate response and near white-line continuity are useful progress.
Two source-owned crack patches are restrained, without an obvious rectangular
outline. They do not yet establish sparse network distribution or dedicated
edge erosion. Their 0/90 degree UV cases are recorded, but tiny/subpixel crack
features yield an inconclusive WorldNormal orientation comparison; retain
`normal_space_verified: false` rather than strengthening material relief for
the diagnostic. Captured buffer names still lack native string readback.

Far line gaps, transverse asphalt bands and the sharp gravel/terrain boundary
remain. The next existing outer blend and ten band/paint controls will test
those named defects independently, retaining every original Lit camera.
At 0112, hiding nominated support022 removes its shoulder/wall contribution
but does not remove the dark narrow road-edge band. The separate support112
and local-Landscape hides also leave that band. At 0081, support185 owns the
tall exposed wall; actual native wall/source CUT observations are now retained,
but final native Landscape height and a geometry repair are not established.

The original receipts are unchanged. #364 remains in progress and #459 open;
owner audit is `PENDING_FINAL_M3`, performance `DEFERRED_AFTER_M3` with no PASS.

## Historical 4258 review — all 68 Lit and 18 contact frames

The [native run 38105475021](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38105475021)
at `4258aab3527506d64769ecf974dd061d9e580687` completed baseline, canary,
save, separate fresh reopen, 68 final Lit views and two contact captures.
[Artifact 11689633008](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38105475021/artifacts/11689633008)
is 412,622,626 bytes with SHA-256
`fc93cab4b2346781be8d426615ba0bddbbb96be139f0cafc38fc36d7d4cfc075`.
Its path inventory and ZIP bounds were checked before extraction. All 272
Lit PNGs were independently checked against the receipt; the 68-camera plan
retains SHA-256 `3fac9564e4c96c0eee237c2103cc4833af93b8bc493b4334e0b88e1e70d37559`.
All 41 separately inventoried contact files and all 18 contact PNGs were also
checked. Actual save/reload/Lit/contact editor exits were zero.

Three independent review assignments cover every final Lit image: the first
34, the next 17 and the final 17 in filename order. All 18 original contact
PNGs were separately viewed, including each baseline/support-hidden/local-
Landscape-hidden triplet. The primary reviewer additionally inspected the
0112/0081 Lit examples and the full 0081 forward contact triplet.

| Observation | Representative fixed camera IDs | Consequence |
|---|---|---|
| Dry, fine-grained near asphalt; broad colour variation is quieter | 0112 forward 00002, 0141 forward 00001, 0179 reverse 00003 | The current granular source is useful; source export alone was insufficient to establish the appearance. |
| Near white lines are continuous and follow visible curves; no obvious floating paint or parapet paint | Close views throughout the 68-frame set | Save/fresh full-buffer proof for all 370 overlays is supported by the viewed near-field result. |
| Far shallow white lines break into regular dots or short dashes | 0083 forward 00002, 0112 forward 00002, 0127 reverse 00004 | Investigate pixel coverage and actual capture/AA state before changing physical width or elevation. Static frames do not prove temporal flicker. |
| Repeated transverse asphalt bands remain in the distance | 0071 forward 00002, 0082 forward 00002, 0105 reverse 00001, 0173 reverse 00002, 0179 forward 00003 | The separate eight-frame channel/uniform-material diagnostic remains required. The 16 crack controls do not replace it. |
| Asphalt/gravel and particularly gravel/Landscape boundaries remain geometric and sharp | 0013 forward 00001, 0071 reverse 00001, 0097 forward 00003 | The source-owned outer material transition is unfinished. No flat tint is accepted as a substitute for the real Landscape material. |
| Pavement and both paint strips end on the same flat cross-edge | 0139 forward 00001/reverse 00000, 0144 forward 00000/reverse 00001 | These are source/geometry ends, not isolated paint holes. |
| Large dark contact walls, faceted slopes and deep shadows persist | 0112, 0081, 0177 and 0179 | Keep the owning geometry/light questions in their scoped work; material changes have not fixed them. |

In the 0081 forward 00008 and reverse 00004 contact triplets, the thick dark
wall under the return curve disappears when **support 185** is hidden and
remains as a vertical wall when the selected Landscape components are hidden.
The diagnosed area is approximately source rows 1560–1880 on edge0. This is
distinct from the previously analysed steep inner profile near row 1200.
Actual retained wall-bottom coordinates and CUT contact are still required;
wall height and real-road banking are not inferred from a PNG.

At 0112, hiding support 112 does not remove the dark edge of the neighbouring
return branch. Source-camera projection identifies support **022** on much of
that visible branch. Its source row 9 edge0 projects to (53.94, 458.06) px;
the same source point 8 cm lower projects to (54.67, 462.99) px, consistent
with the visible thin slab side. A separate lower wall is also visible.
This supports a bounded shoulder-top investigation but is not an executed
022 visibility isolation or a repair of the larger hairpin wall.

These reviews leave **#364 unfinished and #459 open**. Owner audit remains
`PENDING_FINAL_M3`; performance is `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Historical initial rejection and readiness repair

### Observed result, not an appearance PASS

The owner rejected the appearance of the initial four Lit road frames. The
same-camera window-0112 images show hard pale shoulder edges, stretched-looking
vertical cliff surfaces and broken-looking pavement silhouettes/black gaps.
A working renderer and a saved/reopened material do not resolve these defects.

The [native run 38077184971](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38077184971)
and [artifact 11678587618](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38077184971/artifacts/11678587618)
subsequently passed the technical pipeline at the base SHA, including clean
GPU Editor exit (0), four original-size PNGs and unchanged saved/source assets.
The reviewed artifact still reports `PENDING_FINAL_M3`; this is not a reversal
of the owner's dissatisfaction or a whole-area visual approval.

## Confirmed capture regression, with an unproven visual consequence

The new road GPU collector copied camera poses from a survey whose native
readiness was `NATIVE_LOADING_AND_MIPS_READY`, but invoked only
`AutomationLibrary.finish_loading_before_screenshot`. It did **not** invoke
[`prepare_capture`](../../scripts/ue/prepare_landscape_capture.py), prime the
active viewport at the selected camera or verify full map-owned Landscape
height mip residency. The original survey used that existing helper with
`request_height_mips=True`. The accepted saved-material renderer additionally
used three priming screenshots per pose; the new road collector omitted them.

This is a verified implementation difference. It is **not yet proof** that
streaming caused the vertical surfaces or the contact gaps. Those observations
must survive a fair same-camera comparison before requesting geometry changes.

## Bounded implementation

The existing road collector now calls the existing native preparation helper
before the first screenshot at each unchanged source-camera pose, with its
120-second expiring heightmap-mip request. It also requests and reads back all
mips of exactly the four manifest-authenticated road textures. Default textures,
pending compilation or incomplete residency fail before image admission.

Three uniquely named priming PNGs precede each final PNG (12 priming frames,
4 final frames). Both height and material telemetry, all priming identities,
and final per-frame SHA-256/size are retained. Priming images are **not** counted
as final review coverage. Every requested mip lease is released on success or
failure, attempting all releases even if one fails. No global streaming/LOD
setting, camera source, material parameter, mesh, CUT input or saved package is
changed. Existing full scene and raw saved/source-byte checks still apply.

This is a diagnostic rendering correction, not a terrain repair. Rendering
continues with real GPU/RHI, the existing serialized Windows host ownership,
unchanged total deadlines and mandatory exact-SHA CI/native proof. No new
workflow, new generic control framework or benchmark was introduced.

## Validation and next decision

Six synthetic regressions cover preparation before screenshots, all three
unique priming frames, missing/low-mip/compiling textures, failure before image
submission, and cleanup that attempts every lease. They passed locally with
unrelated repository/native imports stubbed; this is a focused unit test, not
the full repository suite or a real Unreal run. Hosted tests and independent
native output on the new exact SHA remain required.

Compare all four final images against the original same-pose artifact. Retain
remaining defects, including ones that are unchanged or worse. Do not claim
quality gains based on a green job or PNG diversity alone. The next material
work remains shoulder-top versus wall ownership and explicit edge treatment;
do not swap all support materials indiscriminately. Confirmed contact/geometry
defects remain in [#459](https://github.com/karnalooch/YetAnotherCyclingSim/issues/459)
and require their separately scoped, source-relative local repair/rollback
proof, not fog, foliage or shader concealment.

Authority: [root rules](../../AGENTS.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md),
[road/shoulder asset contract](../ASSET_PLAN.md#44-droga-i-pobocze),
[M3 host policy](../ai/policies/M3_WORLD_OPERATIONS.md), and
[road-material evidence](ROAD_SURFACE_MATERIALS_364.md).

Owner whole-area audit remains `PENDING_FINAL_M3`. Performance is
`DEFERRED_AFTER_M3`, `performance_pass: false`. No merge or #364 closeout.
