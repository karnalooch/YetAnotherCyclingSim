# Component 230: verified report and repair plan

**Verified:** 2026-10-08  
**Work item:** [#445](https://github.com/karnalooch/YetAnotherCyclingSim/issues/445); implementation [draft PR #446](https://github.com/karnalooch/YetAnotherCyclingSim/pull/446)  
**Historical evidence revision:** `1b0675ee53e796e7f904fa3119bb388fa9489cf6`  
**Limestone implementation revision:** `2f1e15d777fca6fc5f7030b8ce393f968bdefdc8`  
**Status:** limestone combined technical gate and ordinary CI pass; PCGEx overlay admission fails; owner visual acceptance, persistence and whole-area admission remain pending  
**Authority:** [World Building Bible](../WORLD_BUILDING_BIBLE.md), selected through [the documentation index](../README.md); [cliff experiment contract and history](SA_CALOBRA_CLIFF_EROSION_PASS.md)

## Decision

The submitted report is substantially supported by the remote evidence. The
stronger native Landscape trial and its derived mesh were implemented, rendered
and removed. Independent reconstruction reproduces the source-relative audit.
This is a useful local method, with visible softer forms and remaining angular
shadows. It is not an accepted, saved map or completion of #363 / Phase 2B.

Retain the combined candidate as the current comparison reference. Stop general
increases in smoothing or displacement. Repair proof coverage, localize remaining
geometry/shading defects, then evaluate the admitted limestone material and
rider views. Material work may prepare the preview while geometry is diagnosed;
it cannot admit a rejected silhouette or replace the existing neutral fixture.

Implementation update, 2026-10-08: the combined transient proposal now uses
32 thermal passes at talus 1.2 with no preliminary averaging, followed by 24
source-normal-guided mesh passes with no tangential redistribution. Neighbor
weights fall to zero at a source-normal difference of approximately 32 degrees;
the guide remains fixed so creases cannot progressively diffuse away. This
preserves source angular structure instead of inventing random fractures or
strata. It is an engineering candidate, not a geological reconstruction or owner
visual acceptance. The standalone historical erosion and mesh controls remain.

The proposal keeps the 150 cm terrain, 50 cm mesh and 200 cm combined bounds,
fixed interfaces and triangle limits. A separate neutral technical gate runs
even when the existing PCGEx gate fails; checkout restoration also runs after
failure and writes a receipt. An additional diagnostic uses the existing exposed
limestone PBR material after all neutral captures. New evidence is retained for
90 days, which remains finite retention rather than a durable archive. The
exact-revision results and retained evidence are recorded below.
No map save or broader rollout is performed by this implementation.

## Verified limestone implementation

[Runtime proof 37756810383](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37756810383)
at `2f1e15d777fca6fc5f7030b8ce393f968bdefdc8` compiles and captures all
controls. The separate combined technical gate and the always-run checkout
restoration gate pass. [Ordinary CI 37756815269](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37756815269)
also passes. The dedicated workflow remains red because its unchanged PCGEx
A/B gate fails four conditions: 161 > 19 dark pixels and 31 > 19 largest-region
pixels at <0.05, 1,659 > 1,609 dark pixels at <0.10, and 1,378 > 1,279 custom-A
largest-region pixels at <0.15. Native admission does not promote PCGEx.

Independent reconstruction reproduces the combined geometry and erosion:
29,415 vertices, 58,216 triangles, 14,113 changed and 15,296 locked vertices,
1,017 m2, zero nonmanifold edges and XY folds. Maximum original-relative motion
is **177.779610 cm** under the 200 cm envelope. The terrain stage changes 2,348
samples with 28,268 transfers and maximum 149.626461 cm; fixed samples changed
and integer height-sum drift are zero. The mesh stage uses 24 normal passes,
zero tangential passes and maximum 35.133925 cm under its 50 cm allowance.
Candidate/imported heightfields match, and all 16,129 source samples and
metadata match before and after cleanup. PNG hashes, sizes and independently
recomputed lighting measurements match the receipts. Relative to this trial's
own neutral baseline, pixel/largest-region deltas are 0/0 at <0.05,
-760/-15 at <0.10 and -12,137/-5,827 at <0.15: all six conditions pass.
Different acquisitions do not establish a causal ranking of all native profiles.

The native one-component export used proxy-relative UVs, effectively stretching
a tile across approximately 63 m. The transient diagnostic now uses Epic
GeometryScript box projection on UV0 at the admitted **3 m** physical scale;
triangle count is preserved and neutral metric captures precede this change.
The existing limestone material supplies its texture/normal/roughness inputs.
The inspected close view has fine rough rock detail; this is an observed preview,
not owner acceptance of limestone shape, seams or shadows.

Three matched neutral/PBR review pairs use actual source pavement-mask pixels
(bit 1, excluding shoulder-only locations), a common focus on admitted cliff
cells, recorded camera poses, FOV 50 and 1920x1080 frames. Nominal horizontal
ranges are 8/20/45 m; recipes record actual ranges. Eye height is 160 cm above
the accepted Landscape, **not the pavement collision or gameplay camera**.
Visual inspection exposes a coverage limitation: the middle view is substantially
occluded by the road and the distant view barely shows the candidate. Matching
pose/hash checks pass but do not validate useful framing. Correct pavement-height
placement and repeat unobstructed road review before treating packet 3 as complete
or asking for accepted-preview persistence. Retain the useful close and oblique
diagnostics; do not call the three-pair technical PASS rider visual acceptance.

Durable selected evidence is retained through existing Git LFS:

- [Historical selection](../experiments/component230-cliff/evidence/retained-37745658647.json): 56 files, 33,068,223 bytes; archive SHA-256 `5eb936601cde6a9340e28c1b89c86982a70b246a028a2e4ff1a85b62570bd9d5`.
- [Current selection](../experiments/component230-cliff/evidence/retained-37756810383.json): 87 files, 94,050,971 bytes; archive SHA-256 `914657765f402440ac01e9bf7211ecad38fdec1dfceb0ac04842ecdcc7303e8f`.

Both objects were uploaded to the repository's LFS remote, independently fetched
through a separate scratch checkout, and verified against archive and per-entry
manifest hashes before publishing their pointers. The current selection includes
all JSON and all receipt-listed admitted/diagnostic captures across trials;
priming frames and logs are excluded. The historical selection keeps all JSON
and four admitted PNGs each for custom, PCGEx and combined trials. These are
explicit selections, not complete copies of the expiring Actions artifacts.

The current source passes 36 focused tests, including combined-gate failures
and pavement-camera selection; the documentation candidate passes all four
documentation guards. Source/road/physics/checkpoint protections, triangle and
displacement ceilings and existing lighting thresholds are preserved. No map or
asset is saved, no merge occurs, and packets 3-5 remain incomplete. Controlled
shared-baseline ranking of all three native profiles also remains pending.

## Historical evidence and verification method

- [Ordinary CI run 37745665528](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37745665528): success, including Unreal build/Automation and aggregate gate at the evidence revision.
- [Dedicated run 37745658647](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37745658647): topology and capture steps succeed; the A/B lighting gate fails.
- [Artifact 11536127236](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37745658647/artifacts/11536127236): `sa-calobra-component230-pcgex-cliff`, 302,326,271 bytes; GitHub-reported archive SHA-256 `07a31fe4c355a393f533c302bb16fb110df891cabbc603d3c4eb0f89518f087a`; expires 2026-10-22 at 07:56:28 UTC (09:56:28 Europe/Warsaw). Expiration is not durable evidence retention.
- Actual runner engine: UE `5.8.2-56702186`; PCGEx `0.79` at `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, authoring only, with the recorded bounded compatibility patch.

Verification read GitHub metadata, job steps/logs, pinned repository source and
the downloaded artifact. It reran the pinned Python erosion producer, original
surface reconstruction and independent geometry/topology audits; compared native
source/candidate/readbacks; verified the terrain-trial image hashes against their
receipts; recalculated lighting metrics; and visually inspected the baseline,
terrain-only and combined Lit/Lighting Only frames. No new Unreal runtime run
was performed in this documentation task.

### Confirmed technical results

| Check | Reproduced result | Scope |
|---|---|---|
| Erosion profile | 12 smoothing passes, 96 thermal passes, talus slope 0.8 | Derived local heightfield |
| Native sample changes | 2,959; maximum 149.626461 cm; 89,416 transfers | 150 cm stage budget |
| Conservation/protection | Integer height-sum delta 0; fixed samples changed 0 | Discrete regular heightfield, not a geological mass simulation |
| Import and restoration | Candidate equals readback; all 16,129 source samples and metadata equal before/after cleanup | Both terrain-only and combined trials |
| Mesh refinement | 84 normal passes, 3 tangential passes; maximum stage displacement 50.000000000003 cm | Floating-point tolerance; 50 cm budget |
| Exported terrain-stage vertices | Maximum 149.628906 cm relative to original | Export precision differs slightly from native sample metric; below 150 cm |
| Combined audit | 29,415 vertices; 58,216 triangles; 14,119 changed and 15,296 locked vertices | 60,000 triangles per mesh; 1,784 remain |
| Final original-relative motion | 199.612189524 cm maximum | 200 cm total; approximately 3.878 mm remain |
| Local footprint/topology | 1,017 m2; no nonmanifold edges or XY folds; locked positions unchanged | Admitted footprint only |
| PCGEx topology | 19 islands; 28,640 triangles; 1,017 m2; maximum edge 1.5 m | Separate PCGEx presentation generator |
| Trial persistence | Receipts report no map/asset save, restored material/visibility/LOD and no canonical Landscape mutation | Capture contract, subject to workflow gap below |

The displacement audit uses the 3D Euclidean distance between corresponding
original and final vertices. It is not a nearest-surface/Hausdorff measurement
or proof of collision, geological accuracy or whole-route behavior. The footprint
area is measured in XY. Integer height conservation does not establish geological
volume conservation after mesh redistribution.

The original reference file is
`local-cliff-smoothing/local-cliff-smoothing-mesh.json`, SHA-256
`9ed6c9179d2df04117fcc8992224061f942d42a03a714a4a75177c43728b1cd5`.
Reconstruction uses its original SOURCE columns and unique XY correspondence,
not the already-smoothed candidate columns. Reconstructing from
`terrain-erosion-mesh/mesh-stage.json` exactly reproduces `combined-mesh.json`
and `combined-audit.json`.

### Independent lighting measurements

These are recalculated from each trial's own 1920x1080 Lighting Only baseline
and candidate using the existing luminance weights and 8-connected regions.
They are additional diagnostics, not a newly granted acceptance gate.

| Trial / luminance threshold | Baseline dark pixels -> candidate | Baseline largest region -> candidate |
|---|---:|---:|
| Combined / <0.05 | 19 -> 18 | 19 -> 18 |
| Combined / <0.10 | 1,585 -> 802 | 342 -> 328 |
| Combined / <0.15 | 25,496 -> 12,879 | 7,170 -> 1,329 |
| Terrain only / <0.05 | 19 -> 19 | 19 -> 19 |
| Terrain only / <0.10 | 1,599 -> 1,052 | 341 -> 350 |
| Terrain only / <0.15 | 25,540 -> 13,554 | 7,174 -> 1,281 |

The combined candidate improves all six listed comparisons against its own
baseline. Terrain-only has a small largest-region regression at <0.10.
Separately acquired baselines have different image hashes, so these rows do
not establish a controlled winner between terrain-only, combined and the
historical 1 m mesh. Their frozen-neutral readiness checks pass. A common
baseline and candidate removal between captures are needed for that ranking.

Visual inspection supports smoother broad forms and remaining triangular shadow
wedges. The neutral material also gives a soft appearance. Whether the surface
reads as limestone at rider height remains unverified. The combined mesh is a
native eroded-Landscape derivative; its improvements are not proof that the
separate PCGEx overlay is acceptable.

### Exact failures and missing proof

`phase2c-ab-gate.json` records four failing conditions:

1. `<0.05` PCGEx dark pixels: **157 > 19** baseline.
2. `<0.05` PCGEx largest connected dark region: **30 > 19** baseline.
3. `<0.10` PCGEx dark pixels: **1,639 > 1,610** baseline.
4. `<0.15` PCGEx largest region: **1,323 > 1,253** custom A.

The A/B baseline hashes and shared acquisition provenance match. The exact
workflow error is `Phase 2C PCGEx candidate did not satisfy the
lighting/custom-generator admission gate.`; exit code 1. The original report
mentions the dark-pixel problem but omits the two largest-region failures.
All four conditions must be retained in the repair and closeout.

`Enforce non-persistent checkout` is **skipped** after the gate fails: the step
has default success-only execution. Capture receipts and full source readbacks
support local restoration, but the final tracked-file checkout check did not
run. Do not report complete non-persistence workflow admission.

The stronger local trials are checked for receipt/geometry safety in
`Capture custom benchmark A and PCGEx candidate B`; the workflow's metric gate
analyzes only `custom/` and `pcgex/`. Therefore a local
`COMPONENT230_CLIFF_VISUAL_PASS` means capture/restoration protocol success;
the same receipt explicitly states `visual_acceptance=PENDING_OWNER`.
The native combined candidate has no separate enforced lighting verdict yet.

The earlier 212 changed samples are retained historical evidence consistent
with delayed CUT/edit-layer composition. The current code completes the existing
layer update before acquiring the reference, and both current full-source
comparisons pass. This supports the mitigation; this review did not independently
reproduce the earlier asynchronous failure or prove every possible cause.

No actual limestone PBR admission, saved/fresh-editor preview, collision/ride
proof, representative-area transfer or whole-Landscape performance is supplied
by this run. The recorded combined editor-process time, 53.366 seconds, is not
gameplay frame-time evidence.

## Ordered repair work packets

Use #445 and PR #446 as the existing work item and implementation lane. Prepare
small commits in that lane; keep heavy Unreal/editor work serial in isolated
runner roots. Roles below describe responsibilities, not dispatched agents or
new delivery milestones. Preserve original sources, accepted checkpoint,
roads, current hard exclusions and fixed interfaces throughout.

### 1. Proof coverage and evidence retention — first

**Responsible:** CI/proof implementation and independent reviewer.

- Make the final checkout integrity check execute after failed capture/metric
  steps once the checkout exists. Preserve the original failure and artifact
  upload; a cleanup PASS cannot turn a lighting FAIL green. Retain tracked-state
  evidence in the artifact. Diagnose the observed skipped guard rather than
  weakening no-save/no-mutation rules.
- Add an explicit native-combined diagnostic metric receipt alongside the
  PCGEx verdict, with generator identity, exact SHA, baseline readiness,
  original-relative budgets and the unchanged luminance/region measurements.
  Any enforced local acceptance rule must be explicitly scoped; it cannot
  substitute for PCGEx admission or silently redefine it.
- For controlled local candidate ranking, capture native baseline, terrain-only
  and combined surfaces in the same scene with verified rollback between them.
  Retain three priming captures and the current cold-baseline guard. Independent
  acquisitions remain labeled as such.
- Preserve this run's receipts, geometry, heightfields and admitted frames
  before artifact expiry through the existing approved remote retention path.
  Record byte sizes/hashes and restore verification. A GitHub link alone is not
  a retained archive; no public release or new storage dependency is authorized
  by this plan.

**Exit evidence:** a real failed-visual run still executes the integrity guard
and uploads diagnostic results; the successful native trial has a separately
identified verdict; retention has a verified durable location. Do not pay for
a full rerender merely to repeat unchanged evidence before the targeted fix.

### 2. Localize and repair the owning geometry/shading defect

**Responsible:** terrain/mesh implementation; reviewer checks original-relative
motion, footprint and the targeted regression.

- Map the four PCGEx failing dark masks and persistent native shadow wedges to
  camera-space regions and world-space triangles. Record positions, normals,
  local triangle quality, dihedral angles and whether a region touches a fixed
  interface. Keep the PCGEx overlay and native combined paths distinguishable.
- Use existing native baseline, terrain-only, original native mesh, 1 m mesh
  and combined exports to isolate which stage introduces the offending feature.
  Diagnose geometry, normal interpolation or transition ownership before
  selecting the smallest correction; these remain hypotheses until measured.
- Restrict any correction to the admitted local domain and existing 150/50/200
  cm budgets. Preserve fixed positions/normals and single visible surface
  ownership. Recompute original-relative budgets after every candidate; no
  stage receives a reset reference or an extra displacement allowance.
- Do not increase global tessellation or smoothing merely because shadows
  remain. Only 1,784 triangles and about 3.878 mm of the observed total envelope
  remain. Reallocation within existing ceilings needs a new complete audit.
  Shadow bias, lighting, materials and threshold changes cannot hide a defect.
- Retain the previous experiments: VSM cache disable did not remove the wedges,
  and long tangential redistribution was rejected. Repeat those hypotheses only
  if new evidence identifies a specific owning defect.

**Exit evidence:** targeted defect comparisons, zero footprint/lock/fold/edge
violations, original-relative audit PASS and new exact-SHA rendered evidence.
PCGEx replacement additionally requires **all four current failures cleared**
and every existing A/B condition preserved. If PCGEx remains rejected, retain
the custom reference and report that result; do not claim the native mesh
has automatically replaced the chosen production topology architecture.

### 3. Limestone material and rider review

**Responsible:** material/preview implementation; owner provides visual acceptance.

Use the existing admitted limestone assets and Material Forge contract after
neutral geometry review. Verify real ExposedRock/Scree PBR dependent assets;
reject missing texture and Default Material fallback messages. Pin asset
identities and record BaseColor, normal and roughness inputs. No new dependency
or unmerged material integration is assumed available.

Prepare rider-height road-adjacent views at close, middle and distant ranges,
including the persistent wedge and a fixed transition. Record actual camera
transform, height, FOV, viewport resolution and light state. Capture matched
neutral and PBR views of the same geometry. Keep the fixed neutral CI fixture;
its thresholds cannot be reused with a changed material as if unchanged.

**Exit evidence:** explicit owner judgment of limestone character, scale,
silhouette, seams and shadows, supported by the reproducible views and intact
technical gates. A material improvement alone cannot admit geometry.

### 4. Save one accepted preview and prove reopening

**Responsible:** bounded asset integration, after the preceding local acceptance.

Save an isolated preview variant with deterministic provenance, input/recipe
hashes and rollback to the retained original. Keep the canonical source and
checkpoint independently recoverable. Track `.umap`/`.uasset` through existing
LFS rules. Prove a fresh editor loads the saved variant and renders the admitted
geometry/material/visibility state without transient trial actors.

**Exit evidence:** persistent asset identity, remote backup and verified fresh
reopening. The current transient renderer does not provide this step. No save,
whole-map mutation or PR merge was performed by this documentation task.

### 5. Representative transfer, whole-area proof and closeout

**Responsible:** world integration and performance proof, with owner area review.

Validate a moderate slope, a steep/high-earthworks case, a road/shoulder interface
and distant silhouettes using the same source/protection contracts. Select
actual locations from source evidence rather than inventing component IDs.
Each retains local audits and camera/material receipts; one successful fragment
cannot authorize automatic application everywhere.

Only then proceed to the required whole current Landscape review:
2,016.5 m x 2,016.5 m, approximately 4.07 km2. The Golden Kilometer is an
additional check. Measure relevant GPU/frame-time, memory, triangle/draw-call
and streaming costs against existing budgets, including 1920x1080 / 60 FPS on
the reference system. Preserve the #363 -> #384 -> #364 dependency sequence;
this local report does not unblock those successors.

**Exit evidence:** required technical/review gates, owner whole-area acceptance,
saved/fresh-rendered consumer and performance admission, then normal protected
closeout. PR #446 remains draft and requires its recorded explicit merge
authorization; this plan does not supply it.

## Reproduction and documentation checks

At the pinned evidence revision, the following command reproduced the reported
20 focused tests (all PASS):

```text
python -m unittest scripts.geometry.test_local_thermal_erosion scripts.assets.test_analyze_local_cliff_smoothing scripts.assets.test_cliff_baseline_readiness scripts.assets.test_cliff_paired_capture -v
```

To reproduce the geometry check, load the artifact's plan and the original
reference and mesh-stage files named above; call
`original_surface_evidence(reference, derived)` and
`audit(plan, combined, limit_cm=200.0)` from
`scripts/assets/analyze_local_cliff_smoothing.py`. Compare the returned objects
against the recorded combined mesh/audit. The standalone CLI defaults to
100 cm and must not be mistaken for the combined 200 cm check.

Rerun `erode` with the recorded 12/96/0.8/150 parameters and require exact
candidate/readback equality, zero fixed changes and zero integer sum drift.
Compare source, before-cleanup and after-cleanup objects completely. Recalculate
image measurements with the existing `image_metrics` and `baseline_readiness`
functions; preserve each acquisition's baseline identity.

The current SSOT was checked through `docs/README.md`. This documentation task
adds the missing verified outcome/repair sequence and corrects the cliff
document's stale status; the world architecture and scope remain unchanged.
`python scripts/ci/check_docs_index.py` passes **links, i18n, structure and
freshness** on the documentation candidate. The guard checks index entrypoints,
UTF-8, required authority links and top-level catalog freshness; these PASSes
do not imply every prose claim or every embedded external link is automatically
verified. New local links were separately checked against the repository tree.

Remote commit readback and CI status are recorded by GitHub on PR #446. Historical
runtime proof applies to the immutable evidence revision above; it is not
silently relabeled as a new runtime run for the documentation commit.
