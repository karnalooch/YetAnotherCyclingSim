# Texture Material Prep commands and adapter pseudocode

Companion to the [foundation contract](TEXTURE_MATERIAL_PREP.md), Issue #382.
This page separates the working offline foundation from the proposed UE adapter.

## Implemented commands

Run from the repository root, normally the canonical project described in
[the workspace guide](LOCAL_WORKSPACE.md), using its existing Python environment.
The tool uses NumPy and Pillow already pinned by the hosted Python test lane;
it adds no dependency, service or MCP server.

```powershell
# Filesystem capability facts only; does not connect to or launch Unreal.
python scripts/assets/texture_material_prep.py capabilities `
  --project YetAnotherCyclingSim.uproject `
  --engine-root D:/yacs/engine/UE_5.8

# Use the exact source file you have resolved and provenance-reviewed.
# A supplied 2 x 2 m size is recorded as proposed, never automatically accepted.
python scripts/assets/texture_material_prep.py analyze `
  --source path/to/YACS_SC_Limestone_01_BaseColor.png `
  --input-color-space srgb --world-size-m 2 2

# Compare two images of matching resolution and declared sRGB transfer.
python scripts/assets/texture_material_prep.py analyze `
  --source path/to/candidate.png --baseline path/to/source.png `
  --input-color-space srgb

# Prepare a deterministic draft recipe. This does not render anything.
python scripts/assets/texture_material_prep.py plan `
  --source path/to/YACS_SC_Limestone_01_BaseColor.png `
  --input-color-space srgb --resolution 512
```

The source paths above are placeholders, not bundled or discovered assets.
Resolve engine location from the actual workspace configuration; the example
path is the inspected reference host. `capabilities` emits JSON on stdout.
`analyze` and `plan` print the new evidence directory under
`Saved/RuntimeProof/TextureMaterialPrep/<generated_uuid>/`.
Existing files are never overwritten. Evidence is ignored by Git; source bytes
are read and preserved. Exit 0 means a report/plan was produced, including a
blocked plan or review-required result. Exit 2 means invalid input or an IO error.

An optional `--parameters path/to/parameters.json` accepts exactly the documented
parameter keys, for example:

```json
{
  "SeamBlendWidth": 0.05,
  "DeLightStrength": 0.25,
  "ColorGain": [1.0, 1.0, 1.0],
  "HeightStrength": 0.5,
  "NormalStrength": 1.0,
  "RoughnessMin": 0.55,
  "RoughnessMax": 0.9,
  "MacroVariation": 0.0,
  "Seed": 0,
  "GenerateAO": false
}
```

Unknown keys, non-finite/bool numbers, out-of-range parameters, reversed roughness
limits, non-integer seeds and enabled AO are rejected. Draft recipe IDs hash the
source identity and canonical plan. They are **not execution identities**:
`graph_hash`, `engine_build` and `execution_identity` are null and the plan
returns `blocked / UE_ADAPTER_NOT_IMPLEMENTED`. The future adapter must bind the
actual graph/dependency/engine hashes before creating an executable plan.

### Supported subset

| Implemented now | Deferred until UE adapter/proof |
|---|---|
| Opaque RGB/RGBA **8-bit PNG BaseColor**, 8..4096 px per side, <=64 MiB input | Other formats, HDR, profiled/16-bit color decoding, high-precision height inputs |
| Explicit sRGB declaration, piecewise linearization, both seam axes, edge mean/p95/max, interior contrast and wrap gradients | TG output extraction, decoded UE compression/mips and normal angular seams |
| Linear luminance quantiles/clipping, 8x8 low-frequency grid, row/column drift and fitted plane; before/after comparison | Physical albedo recovery or material calibration |
| 2x2/4x4 bounded labelled previews, half-offset preview, native central seam crops and four-corner junction | Full-image band analysis at all positions, engine material screenshots and visual acceptance |
| Resolution, source SHA-256 and proposed/unresolved world-scale metadata | Accepted physical scale/provenance and production asset admission |
| Parameter validation and draft recipes; filesystem capability inventory | MCP registration/routing, graph mutation, processing, render, export, save/reopen |

The decoder rejects ICC/chromaticity profiles, conflicting PNG gamma, animation,
non-opaque alpha, grayscale and 16-bit PNG rather than silently reinterpret or
downconvert them. It is intentionally not a general image importer. The original
file's bytes are hashed from the same bounded read that is decoded.

Numerical screening uses the provisional BaseColor policy in the contract.
`within_provisional_limits` is only a screen. `admission` stays `review_required`,
`ue_validation` stays `not_run`, and `visual_acceptance` stays `pending`.
Even a perfect constant image cannot become an admitted limestone material.

Reports use linear values. Diagnostic PNGs retain sRGB display pixels and never
serve as production outputs. Contact sheets have a maximum 256-pixel tile edge;
native seam/corner crops are separate. The receipt hashes every generated report
and preview except itself. It is not an exact-SHA UE proof receipt. On an IO
failure, partial evidence may remain in its new run directory; it is not accepted.

```powershell
python scripts/assets/test_texture_material_prep.py
python scripts/ci/check_docs_index.py
python scripts/ci/test_final_architecture_contract.py
```

The test file follows existing `test_*.py` discovery, so the hosted Python lane
runs it without workflow changes. Synthetic cases check sRGB transfer, both axes,
equal-edge gradient defects, zero-denominator JSON, luminance changes, invalid
inputs/parameters, PNG precision, metadata, no-overwrite and CLI evidence hashes.

## Proposed UE adapter — pseudocode only

The following is **not executable Python or verified Unreal API syntax**.
Every lowercase helper is a required future YACS adapter operation, not a claim
that Epic exposes a method with that name. Exact verified native entry points
and unresolved reflection/linkage are recorded in the foundation contract.

```text
prepare_texture(request):
    require approved source ID, preset ID and strict parameter schema
    inspect exact engine build + plugin state + reflected signatures
    require reviewed template and complete dependency hashes
    require existing YACS guards and selected native routing admitted
    require all output names, parameter types and precision supported
    freeze source SHA + graph/dependency SHA + engine + recipe + output contract
    return immutable execution plan (no source/template mutation)

render_preview(plan_id):
    acquire single editor job lock, otherwise BUSY
    verify frozen identities again; reject missing/mismatched evidence
    create transient graph working copy in the disposable proof context
    bind source; set typed values; read every value back
    configure exact output settings and verify role-to-output mapping
    start verified async TG render; hold graph/task/result references
    return job ID immediately

on_render_complete(job):
    reject stale/expired identity or missing outputs
    read back named outputs; verify dimensions, precision, transfer and ranges
    create immutable preview receipt; mark preview_ready only after checks
    release lock only when native task has ended and readback is complete

export_pbr_set(plan_id, preview_receipt):
    acquire lock; verify plan and preview belong to the same exact identity
    allocate a fresh server-generated run namespace
    inspect every output path and pre-existing package before any export
    bind all selected output settings to that namespace
    require no hidden/extra outputs; reject any destination collision
    export through TG: overwrite=false, save=false, export-all=false
    await actual native completion, not a guessed sleep or void return
    verify exact asset set, settings, dimensions and decoded pixels
    compare export to preview (TG export may re-render)
    save ONLY verified newly owned packages; never Save All
    reopen in isolated proof context; collect hash + settings + pixel receipt
    retain any partial/late output as unaccepted evidence on failure
    release lock after actual completion; never treat timeout as cancellation

validate_texture(run_id):
    read source, uncompressed TG output, exported textures and mips
    apply role-specific validation with the recorded policy version
    produce 2x2/4x4 evidence, seam bands/corners and normal-orientation proof
    report technical, scale, provenance and human-review statuses separately
    never assign a material, touch a level or automatically promote assets
```

### Required negative UE integration cases

| Trigger | Required outcome |
|---|---|
| Plugin disabled, reflected name missing, settings enum unsupported | Structured unsupported result before mutation; no generic Python fallback |
| Wrong/missing parameter that native API would only warn about | Preflight/readback rejection; never report a successful stage |
| Unknown role, duplicate output, hidden output outside run root | Abort before export |
| Existing asset, package, name collision or path traversal | Abort; byte-identical pre-existing content |
| Source/template changes between preview and export | New plan required |
| Concurrent job, timeout, exception, late completion | Bounded status, lock held until native completion; no late acceptance |
| Void export return but missing/wrong asset, precision loss or sRGB mismatch | `EXPORT_INCOMPLETE` / failed validation; no success receipt |
| Good metrics but unknown physical coverage or strong baked light | Review/scale gate remains open |
| Successful export and save but fresh reopen differs | Reject durability proof |

No `/yacs-editor texture-*` command exists. Do not paste pseudocode into a generic
remote executor or bypass the current `smoke-cube` allowlist.
