# Texture Material Prep commands and isolated UE proof

Companion to the [foundation contract](TEXTURE_MATERIAL_PREP.md), Issue #382.
This page separates offline diagnostics, the opt-in editor adapter and pending production gates.

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
returns `blocked / UE_CONNECTION_REQUIRED`. The editor adapter creates its own run receipt with graph package hash, source
data GUID, exact engine build and recipe. Offline draft IDs are never accepted
as executable job IDs. A full transitive dependency identity remains deferred.

### Supported subset

| Implemented now | Still deferred |
|---|---|
| Opaque RGB/RGBA 8-bit PNG BaseColor analysis, 8..4096 px, <=64 MiB | HDR, profiled/16-bit inputs and calibrated displacement |
| Opt-in UE 5.8.2 fixed native graph, async named renders, exact-pixel serialization and five-map readback | Main project activation and reusable promoted graph template |
| Seam/luminance metrics, normal unit length and angular seam metrics, 2x2/4x4 previews | Compressed GPU/mip readback, DirectX ramp and visual acceptance |
| Exact engine build, graph package hash, source GUID/PNG SHA-256, proposed world scale | Full dependency manifest, accepted limestone coverage/provenance |
| Native Toolset Registry definition, scoped db-lyon guard and isolated profile | End-to-end remote MCP transport admission and texture broker command |

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

## Implemented opt-in editor adapter

The plugin descriptor is disabled by default. Do not add it to the canonical
project or copy over its live MCP configuration for this test. Reserve at least
50 GiB free disk under the workspace policy. Use a new proof directory; UAT
clears an existing packaging destination. Compile only this plugin, not YACS.
Resolve the engine/work roots from `workspace.json`; these are the reference
host's paths. Run from the isolated repository checkout:

```powershell
$engineRoot = 'D:/yacs/engine/UE_5.8'
$repoRoot = (Get-Location).Path
$proofRoot = Join-Path 'D:/yacs/work' ('texture-prep-proof-' + [Guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $proofRoot) { throw 'Proof destination must be new' }
& "$engineRoot/Engine/Build/BatchFiles/RunUAT.bat" BuildPlugin `
  "-Plugin=$repoRoot/Plugins/YacsTexturePrep/YacsTexturePrep.uplugin" `
  "-Package=$proofRoot" -TargetPlatforms=Win64 -StrictIncludes -NoDeleteHostProject
if ($LASTEXITCODE -ne 0) { throw 'Plugin build failed' }
$proofProject = "$proofRoot/HostProject/HostProject.uproject"
New-Item "$proofRoot/HostProject/.yacs-texture-prep-proof" -ItemType File | Out-Null
Start-Process "$engineRoot/Engine/Binaries/Win64/UnrealEditor.exe" -WindowStyle Hidden `
  -ArgumentList @($proofProject, '-unattended', '-nosplash', '-nosound', '-NoLiveCoding',
    '-RenderOffscreen', '-ZenDataPath=D:/yacs/cache/Zen', "-ExecutePythonScript=$repoRoot/scripts/assets/texture_material_prep_ue_smoke.py")
```

The smoke generates a deliberately discontinuous 128x128 PNG, imports it into a
new fixture folder, registers only `YacsTexturePrep.YacsTextureTools`, verifies
its schema and dispatch, then prepares, renders, exports and reads back five
maps. It owns and quits only the disposable editor. Engine shutdown/exit 0 is
**not success**: require a `texture-smoke-<uuid>/result.json` under that project's
Saved directory with `exported_review_required`, no failure receipt, and a
registry probe. The result contains the bundle evidence directory.

Run diagnostics on that directory with the repository Python environment:

```powershell
python scripts/assets/texture_material_prep_bundle.py path/to/bundle
# After the fresh-editor reopen script:
python scripts/assets/texture_material_prep_bundle.py path/to/bundle --reopen path/to/reopen-evidence
python -m unittest discover -s scripts/assets -p 'test_texture_material_prep*.py'
node --test tools/ue-mcp/guards/YacsTextureGuard.test.js
```

The validator exits 1 on detected degenerate BaseColor, out-of-range roughness or
non-unit normal vectors. Other seam/de-light screens remain review gates. Linear
map channels are not sRGB-decoded. All previews are diagnostic; no image is
processed into a production output by Python.

After diagnostics, launch the **same proof project in a fresh editor process**
with `texture_material_prep_ue_reopen.py` in place of the smoke script. It verifies
the graph package hash and reopened texture dimensions/color/compression, then
exports source-mip PNGs into a new `reopen-<uuid>` directory. The `--reopen` validator compares all five
decoded PNG arrays to the original bundle; settings success alone does not prove
pixel durability. It does not rerun the graph or save any asset.

### Tool calls and guarded MCP routing

Explicit registration in the proof editor:

```python
unreal.ToolsetRegistry.register_toolset_class(unreal.YacsTextureTools)
```

`InspectCapabilities`, `PrepareTexture`, `RenderPreview`, `ExportPbrSet`,
`ValidateTexture`, `GetJobStatus` are the six native operations. Their JSON schema
is generated from the compiled definitions; inputs use camelCase (`jobId`,
`sourceAssetPath`, `recipe`). Registry results wrap the JSON report in
`returnValue`. Direct Python methods use snake_case names. `PrepareTexture`
accepts a saved source object path and `YacsTextureRecipe`; it creates a fixed
new graph, not arbitrary caller-authored nodes. WorldSizeMeters is required as a
positive hypothesis, never assumed to be accepted limestone coverage.

For a db-lyon integration test, copy `tools/ue-mcp/texture-proof-profile.yml` as
`ue-mcp.yml` **only in the disposable project**, with the pinned package and
`tools/ue-mcp/guards/YacsTextureGuard.js` available at the declared relative path.
Bind that client to the proof editor, not the open authoring project. Keep
`nativeTools.enabled: false`: the narrow `epic.call_tool` gateway still works;
the guard rejects other toolsets, Python, console commands and arbitrary writes.
Do not enable `All Toolsets` or start an additional native MCP server.

Example gateway payload:

```json
{
  "action": "call_tool",
  "toolset": "YacsTexturePrep.YacsTextureTools",
  "tool": "YacsTexturePrep.YacsTextureTools.InspectCapabilities",
  "input": {}
}
```

The engine registry's direct `ExecuteTool` API expects the **bare** operation
name. db-lyon 1.3.9 strips the qualifier before dispatch. Never bypass the guard
with an alternate `inputJson` channel. Poll job status between phases: a timeout
means the task is draining, not cancelled. Do not retry a write on the same job.

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

No `/yacs-editor texture-*` command exists. Do not paste tool calls into a generic
remote executor or bypass the current `smoke-cube` allowlist.
