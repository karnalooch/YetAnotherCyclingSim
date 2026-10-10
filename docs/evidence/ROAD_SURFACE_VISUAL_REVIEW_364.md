# Road surface visual rejection and capture-readiness repair — #364

**Milestone:** M3. **PR:** #470 (Draft). **Domain owner:** Visual & DCC.
**Base SHA:** `f9eeb02771ad036892b157059f07876a07abea61`.

## Observed result, not an appearance PASS

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
