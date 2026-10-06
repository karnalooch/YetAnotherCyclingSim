# Sa Calobra material repair plan

**Status:** documentation-only repair plan; implementation not started by this update  
**Recorded:** 2026-10-06  
**Work item:** [#363 — Landscape material foundation](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363)  
**Delivery lane:** existing draft [PR #381](https://github.com/karnalooch/YetAnotherCyclingSim/pull/381)

## Authority, scope and execution boundary

The owner requested a detailed repair plan, explicitly without implementation,
then requested its inclusion in project documentation and the issue description.
This record authorizes documentation delivery only. No material application,
import, scene mutation, build, GPU benchmark, visual acceptance, issue completion
or successor unblock is performed or implied by this update.

[World Building Bible](../WORLD_BUILDING_BIBLE.md) remains the methodology
authority selected through [the documentation index](../README.md).
[Product Requirements](../PRODUCT_REQUIREMENTS.md) and [Roadmap](../ROADMAP.md)
retain scope and ordering; the [material foundation workflow](SA_CALOBRA_MATERIAL_FOUNDATION.md)
retains reusable authoring, native instance audit and persistence procedures.
This plan defines the immediate repair sequence for the current candidate.
Earlier reference, six-role library, licence, acquisition and sample-approval
gates in #363 remain required; diagnostic use of an imported scan does not
retroactively approve it as a production surface.

Appearance and performance acceptance cover the entire existing Landscape:
2016.5 m x 2016.5 m, approximately 4.07 km2, on the existing 4033 x 4033 grid
at 0.5 m with its EPSG:25831 registration. The Golden Kilometer is an additional
rider-view check, not a substitute for whole-area coverage.

The accepted terrain and roads are frozen. Repair material projection, weights,
colour, normals, roughness and their delivery only. Preserve heights, topology,
road alignment, CUT/FILL geometry, collision and route/physics authority.
Do not add displacement, WorldPositionOffset, terrain smoothing or road rebuilds.
Spatial vegetation, PCG placement, rock meshes, RVT integration, new plugins and
official MCP adoption are separate work. Preserve the deferred #372 red-overlay
review. #384 remains blocked by full #363 completion, before #364, as recorded
in the Roadmap; this plan changes no issue dependency or project status.

## Evidence snapshot and open hypotheses

This plan follows static reading of the local preview scripts and manifests,
the retained receipt and UE 5.8.2 installation metadata (CL 56702186). It does
not claim a new editor inspection or a new rendered/performance proof.

Local evidence inspected on 2026-10-06:

- `scripts/ue/preview_sa_calobra_scanned_surfaces.py`, SHA-256
  `e6e151c83a73d048c6f4abb37f33a6f91d9500cff8d3d7d82c5f20d9a8caed41`;
- `scripts/ue/preview_sa_calobra_masked_materials.py`, the base mask consumer;
- `worldgen/materials/scanned_refinement/manifest.json`, SHA-256
  `287e27833967de065d5fc264496784d4fcf185d3824e022c6134a8ae8b03c807`;
- `worldgen/materials/visual_fill/material-input-manifest.json`, active
  presentation-mask semantics and registration;
- ignored local `Saved/RuntimeProof/MaskedMaterials/scanned.json`, reporting
  1024 assigned components, matching bounded scene snapshot, `map_saved=false`,
  visual acceptance pending and performance not measured.

The scanned preview script and scan manifest were locally untracked at inspection.
The paths and hashes identify inspected evidence; this documentation change does
not publish those scripts, source texture bytes or ignored receipts. Preserve them
before any later integration or cleanup. Existing technical proof for a different
candidate is not transferable visual or runtime admission.

### Confirmed code behaviour

1. All five layer weights are squared and normalized. This suppresses minority
   contributions, including vegetation and the dry-channel overlay.
2. The slope factor is `saturate((0.75 - abs(N.z)) / 0.35)`. It begins at about
   41.4 degrees and reaches one at about 66.4 degrees for a normalized surface
   direction. Every non-rock layer is multiplied by its complement; the slope
   factor is then added to exposed rock. The overlay is therefore also suppressed.
3. The direction reconstructed from screen derivatives of world position is
   used both for projection-function inputs and slope replacement. Those
   responsibilities are currently coupled.
4. The scan candidate uses 50 m rock tiling and 15 m vegetation-ground tiling,
   enables the high-quality normal option and blends the final normal toward
   `(0, 0, 1)` with a 0.4 detail contribution before normalization.
5. Component `GetMaterial(0)` readback proves assignment, not generated
   render-instance consumption. The existing native instance audit is a separate
   required gate.

For an illustrative two-layer mixture with no overlay, squaring and normalization
turn 20% / 80% into approximately 5.9% / 94.1%. The current slope rule at 60 degrees
further reduces the first non-rock contribution to about 1.7%. This is arithmetic
from the code, not a measurement of a particular Landscape location.

### Unresolved questions

The exact source of the remaining stripes, correct normal-space conversions,
installed projection-function pin behaviour, camera/LOD stability and the last
candidate's visible result remain unverified. The reported unlit stripes mean
lighting alone is insufficient as an explanation; weaker normals are not proof
of a corrected projection. Treat each proposed cause as a hypothesis until its
isolated test passes.

## Ordered repair work

### 1. Retain an identifiable baseline and rollback

**Work**

- Retain the previous material and latest candidate with source/configuration
  identities, parameter values and texture/mask hashes.
- Capture actual camera, FOV, exposure, lighting, resolution and quality settings.
- Preserve the owner's dirty packages and live session. Use the existing binding
  restore path; do not create hidden geometry copies or use Save All.
- State exactly what the scene snapshot checks. Matching bounded traces,
  transforms and map hash is not a fresh exhaustive geometry proof.

**Deliverable:** reproducible baseline, retained candidate and verified binding
rollback procedure.

**Exit gate:** a later comparison can identify its inputs and restore the prior
material without changing frozen content.

### 2. Establish fixed diagnostic views

**Work**

- Reuse existing review/capture tools and distributed review positions.
- Include a gentle mixed slope, steep roadside face, slope-to-wall transition,
  forest floor, dry channel/scree appearance, mineral fallback, Landscape
  component boundary and demanding wide view.
- Include different face directions and a repeatable rider-camera traversal.
  Use the existing nine distributed positions as coverage support, not a claim
  that all demanding environments have been inspected.
- Prepare separate diagnostic views for a directional metric checker, unlit/base
  colour, layer weights, normal directions and the full lit material.
- Hold camera/light/render settings fixed within each comparison and wait for
  shader compilation and texture residency to settle.

**Deliverable:** location-based view list, comparable captures and repeatable
camera path, with blocked or unobserved locations explicit.

**Exit gate:** each subsequent adjustment changes one identified variable and
can be compared against the same baseline view.

### 3. Correct colour projection on a control pattern

**Work**

- Start with a single directional checker of known metric size, constant
  roughness and no detail normal map.
- Inspect the installed UE 5.8.2 function graphs and pins. Separate projection
  coordinate orientation, the surface direction used to blend projections and
  texture size in world units.
- Epic describes `World Space Normal` on `WorldAlignedTexture` as a world-up
  orientation input. Do not assume that feeding a per-face direction into that
  pin correctly supplies projection blend weights.
- Compare the native function with a fixed world basis against the current
  derivative-driven variant. Evaluate a stable base-surface direction and the
  geometric direction independently, without changing sharpness and tile size
  at the same time.
- Prefer the existing native function where it satisfies the contract. A custom
  correction requires a demonstrated specific gap and the existing architecture
  policy; do not invent another generic material framework.
- Check axis transitions, differently oriented steep faces, component boundaries,
  camera motion and Landscape LOD changes without changing terrain geometry.

**Deliverable:** controlled A/B projection evidence and the selected coordinate/
blend contract.

**Exit gate:** no severe steep-face stretching, projection-induced triangle
pattern or camera-dependent instability. Checker overlap in a triplanar blend
is expected; continuity of every individual square is not the acceptance rule.

### 4. Verify normal spaces before appearance tuning

**Work**

- Establish the installed `WorldAlignedNormal` output space, its `WorldSpace`
  pin semantics, the material's tangent-space setting, axis reorientation and
  normal-map convention. Verify import/compression and green-channel settings.
- Validate whether `(0, 0, 1)` is the correct neutral reference in that space.
  In world space it points upward, not along every wall's base normal.
- Test a flat normal map first, then a directional pattern with obvious relief.
- Compare disabled, weak and intended normal strength with identical colour,
  weights and lighting. Inspect projection seams and two-material transitions.
- Keep surface classification independent of the final perturbed detail normal;
  do not use a normal-dependent output as an unexplained feedback source.
- Restore normal strength only after the direction/space tests pass.

**Deliverable:** normal-space contract and flat/directional/strength comparisons.

**Exit gate:** a flat map preserves expected base shading, relief keeps its
orientation across projections and stronger detail does not recreate stripes.

### 5. Repair weight composition and explain vegetation loss

**Work**

- Bind diagnostics to the exact active mask manifest. In the visual-fill package,
  R is low-vegetation appearance, G forest-floor appearance, B rock appearance
  and A an artistic dry-channel overlay. The RGB remainder is mineral ground.
  Observation availability is a separate image.
- Do not apply the older foundation package's A-as-availability contract to this
  package. These are different input versions, not interchangeable channel names.
- Show raw RGBA, residual/overlay composition, sharpened weights, slope-adjusted
  weights and final colour at the same locations.
- Start from unsharpened mixing to establish input fidelity. Separate projection
  orientation/blending from the slope signal and policy for vegetation coverage.
- Reintroduce sharpening only where evidence supports it. Define whether and
  where slope may replace each role, particularly the dry-channel/scree overlay,
  rather than retaining a blanket accidental suppression.
- Preserve zero-source constraints, road/building exclusions, existing
  appearance-inference limits and original placement selectors. Do not repair
  missing green by globally boosting coverage or inventing geography.
- Check single-role cases, 20/80 and 50/50 mixtures, zero RGB, full A, exclusions,
  and slopes below, within and above the transition range. Verify finite,
  nonnegative normalized weights and a defined mineral fallback.

**Deliverable:** input-to-final weight comparisons, explicit composition order
and focused mathematical/consumer regression cases.

**Exit gate:** every loss of green or overlay has an explicit rule; zero RGB is
the agreed fallback rather than a hole; invalid weights fail visibly.

### 6. Establish limestone appearance at three scales

**Work**

- Resume production surface selection only on the corrected projection and
  normal path. Retain prior reference/library/licence gates and source identity.
  The two aerial scans remain candidates, not verified local limestone.
- Separate large-scale restrained value/colour variation, medium-scale fractures
  and weathering, and small-scale roughness/normal detail visible nearby.
- Choose metric sizes from actual source features and controlled samples.
  Current 50 m / 15 m settings are test parameters, not accepted targets.
- Retain pale grey limestone with bounded warm variation and locally justified
  olive/straw vegetation. Avoid flat white rock, blanket brown rock, baked
  shadows, visible repeats and implausibly strong relief.
- If final vegetation weights are correct but colour remains grey, inspect
  desaturation/tint and the source surface separately from mask coverage.
- Check roughness packing, colour spaces and common physical scale for colour,
  normal and roughness maps under fixed lighting.
- Compare close, rider, medium and overview views, including simple neighbouring
  surface pairs, before restoring the full mixture.

**Deliverable:** reviewed coherent surface samples with recorded scale, palette,
normal strength and roughness settings.

**Exit gate:** believable limestone at the required distances, readable vegetation
ground and coherent transitions; no claim of spatial foliage from ground colour.

### 7. Make tuning explicit and prove the actual consumer

**Work**

- Once a variant works, expose named parameters for scales, normal strength,
  blend sharpness and slope policy instead of rebuilding unexplained constants.
- Replace fragile recognition of a `0.55` multiply node and inferred graph
  topology with explicit graph/parameter identity where necessary. Reject
  unexpected graphs rather than modifying an arbitrary matching node.
- Independently verify actor/component assignment, generated instance parent
  chains through the existing native audit, and the visible rendered result.
- Follow existing isolated build requirements if the native audit is unavailable
  in the running binary; do not claim assignment readback substitutes for it.
- Repeat the bounded frozen-scene check after meaningful changes and verify
  rollback/partial-failure handling.

**Deliverable:** reproducible settings, graph identity and actual-consumer proof.

**Exit gate:** all 1024 component consumers use the expected candidate, the visible
result matches it and frozen-scene checks preserve their stated scope.

### 8. Review the whole area and measure the stable candidate

**Work**

- Inspect relative shader/texture cost during projection and detail selection.
  Run the full benchmark at stable-candidate readiness, not every cosmetic edit.
- Review every identified environment, demanding overview, steep face and
  traversal across the whole area, plus the additional Golden Kilometer.
- Use the existing [Performance Framework](../performance/PERFORMANCE_FRAMEWORK.md),
  [Budgets](../performance/BUDGETS.md) and [CI cadence](../CI_VALIDATION_TIERS.md).
- Retain raw Frame/GPU and available Game/Draw/RHI data, percentiles, hitches,
  texture residency/memory and location-specific results. An area average or
  average FPS cannot conceal a failing view.
- Preserve the 1920 x 1080 / 60 FPS reference target: Intel Core i5 10th
  generation, 32 GB RAM and RTX 2070 Super. Existing gates remain Frame p95
  <= 16.667 ms, GPU p95 <= 16.667 ms and <= 5% frames above 16.667 ms;
  required GPU timing missing means FAIL. This is the whole-frame budget,
  not an allocation to the material alone.
- Bind deferred 2A/2B performance admission to the actual saved consumer and
  exact candidate SHA. No legacy map or frozen-baseline exception substitutes.
- Diagnose the limiting domain before optimizing. Any appearance-affecting
  optimization returns to the relevant visual checks.

**Deliverable:** explicit whole-area visual decision and performance evidence for
the same candidate; final admitted measurements use the saved consumer in step 9.

**Exit gate:** whole-area appearance is accepted and cost risks are measured.
Final performance admission remains pending until the saved, freshly rendered
consumer passes step 9. Report unobserved locations and unresolved diagnostics
rather than averaging them away.

### 9. Persist, reopen and deliver through the existing lane

**Work**

- Save only explicitly scoped material/assets and consumer changes through the
  existing workspace procedure; preserve unrelated dirty packages.
- Retain code, parameter, texture, mask and package identities. Distinguish
  canonical frozen-map identity from a derived proof map.
- In an isolated verification checkout and fresh process, verify saved data,
  actual instance consumption and frozen-scene invariants, then capture real
  rendered evidence. Live reapplication and NullRHI are insufficient.
- Resolve or explicitly triage renderer diagnostics, including the retained
  ray-tracing ensure described in the foundation workflow, before admission.
- Execute final performance proof on that saved/rendered consumer. Reuse build
  evidence only within the exact-SHA/compile-reuse policy.
- Run relevant source/consumer, Unreal/asset and protected CI/review checks.
  Update changed input semantics and recipes in the same implementation PR.
- Run documentation links, i18n, structure and freshness guards; retain original
  failed/rejected evidence and rollback information.
- Keep #381 draft until all required gates pass. Deliver within #363 and its
  existing branch, without closing it or unblocking #384/#364 on planning alone.

**Deliverable:** saved and freshly rendered consumer, exact-version proof bundle,
current documentation and protected repository delivery.

**Exit gate:** live, saved and fresh-loaded states agree; owner visual acceptance,
performance and technical proof apply to the delivered revision.

## Diagnostic routing and first implementation checkpoint

- Stripes on the checker with detail normals disabled: investigate projection.
- Clean checker but stripes with normals: investigate normal space/reorientation.
- Green absent from final weights: investigate composition and slope policy.
- Correct weights but grey ground: investigate source colour/desaturation/tint.
- Defect only during motion: inspect LOD, filtering, residency and temporal
  behaviour; do not assume a particular cause without comparison.
- Correct live preview but failed reopen: investigate persistence and consumption.
- Acceptable appearance but budget failure: diagnose cost before admission.
- Any frozen-geometry change: stop the candidate and restore the previous state.

The first future implementation checkpoint must deliver three independent
results: a stable checker on steep faces, correct flat/directional normal tests,
and raw-mask versus final-weight evidence. Do not proceed to final texture
polish merely because the shader compiles.

## External technical references

Use the installed UE 5.8.2 graphs/source to resolve pin details not established
by public documentation:

- [Epic texturing material functions](https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine):
  projection orientation, world-unit scale and normal projection.
- [Epic coordinate expressions](https://dev.epicgames.com/documentation/en-us/unreal-engine/coordinates-material-expressions-in-unreal-engine):
  world position and normal-dependent coordinate expressions.
