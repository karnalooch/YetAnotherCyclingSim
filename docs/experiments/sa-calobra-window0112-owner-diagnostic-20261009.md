# Issue459 internal shoulder/CUT surface-owner diagnostic

The four interior `window-0112` source cameras at stations 17.7665898620 and
35.5331797241 m in both directions isolate the repeated uphill shoulder/CUT
teeth reported in [Issue459](https://github.com/karnalooch/YetAnotherCyclingSim/issues/459#issuecomment-6079830201).
PR462's shared endpoint miter repair does not establish the owner of this
interior defect. No geometry correction is made by this diagnostic.

The existing isolated Windows proof lane starts a fresh editor on
`/Engine/Maps/Entry` after the host-idle and asset hydration guards. It reopens
the accepted saved scene, verifies the `c5573b3` recipe's complete input hashes,
and matches one saved support actor against all 5,232 frozen interior top
triangles. It does not execute retained road/support consumers. The six or
fewer expected local Landscape components are selected by intersection with
the pinned target CUT extent (grid X1111..1206, Y1011..1080). An unexpected
extent/topology or missing/ambiguous support fails explicitly; the script
never guesses an actor label or hides the entire Landscape.

Each camera produces three original 1280x720 PNGs:

- `baseline`: the saved source surfaces remain visible;
- `support-hidden`: only the proven target support is hidden;
- `local-landscape-hidden`: only intersecting target CUT components are hidden.

Hidden surfaces also disable their hidden-shadow flag. Visibility, shadow
flags, actor inventory/transforms and the viewport are restored. The target
support triangle digest and saved map digest must remain identical. Heightmap
mip residency requests are released. No material, height, road XY, grade,
crossfall, shoulder width, CUT limit or LOD policy is changed. The actual
rendered Landscape LOD remains an explicit unknown; component ForcedLOD and
LODBias policy are recorded without forcing them.

## Executable recipe

The owning workflow uses the exclusive `[shoulder-contact]` marker and skips
whole-map master generation/full-map captures. Set these variables inside its
already checked isolated worktree:

```powershell
$env:YACS_SHOULDER_CONTACT_ROOT = Join-Path $env:YACS_WHOLE_MAP_PROOF_ROOT 'shoulder-contact'
$env:YACS_SHOULDER_CONTACT_EXACT_SHA = $env:GITHUB_SHA
$env:YACS_SHOULDER_CONTACT_WORKTREE = (Get-Location).Path
$env:YACS_SHOULDER_CONTACT_API_RECEIPT = Join-Path $env:YACS_WHOLE_MAP_PROOF_ROOT 'native-api-evidence.json'
$env:YACS_SA_CALOBRA_TPP_FROZEN_ROOT = Join-Path $workspace.data 'world-data/sa-calobra-working-v1/frozen-road-c5573b3-2026-10-04'
```

The installed UE5.8.2 CL56702186 primary-header receipt must include
`SectionBaseX`, `SectionBaseY`, `ComponentSizeQuads`, `ForcedLOD`, `LODBias`,
`SetVisibility`, `bVisible`, `bCastHiddenShadow`, `GetMeshRef`,
`TriangleIndicesItr`, `IsTriangle`, `GetTriangle`, `GetVertex`, `VertexCount`
and `TriangleCount`. The bounded read-only
`YacsLandscapeMeshDiagnosticLibrary.ReadWindow0112SupportTriangles` reads these
native mesh methods and preserves actual triangle IDs, including sparse IDs.
It returns at most 12,000 oriented triangle records and never modifies the mesh.
The earlier Python `get_triangle_positions` call is unsupported by the installed
primary `UDynamicMesh.h`; no native capture was produced by that first attempt.
Use the existing isolated launcher with
`-ExecutePythonScript=scripts/ue/capture_sa_calobra_shoulder_contact.py` and the
same Entry map, rendering and script-error flags. The capture has a 900-second
deadline, with the reused per-screenshot 120-second deadline. Then run:

```powershell
python -m scripts.proof.sa_calobra_shoulder_contact verify --root $env:YACS_SHOULDER_CONTACT_ROOT --exact-sha $env:GITHUB_SHA
```

Retain `shoulder-contact.json`, `capture/survey.json`, all 12
`capture/frames/*.png` and `capture/readiness/**/capture-readiness.json`. The
native status is `SHOULDER_CONTACT_CAPTURED` only after capture and restoration;
the host verifier emits `SHOULDER_CONTACT_EVIDENCE_VERIFIED`. Both leave
`rendered_owner=PENDING_PAIRED_VISUAL_REVIEW`. Neither status closes the defect,
proves continuous riding, provides whole-map coverage or admits performance.

Review the paired originals before choosing the next bounded repair: persistence
when support is hidden implicates a different surface; persistence when local
Landscape is hidden implicates a different surface. Mixed or absent reproduction
remains unresolved. Record the exact runtime commit, affected owner/components
and source-relative extent before making a correction. No source geometry is
regenerated to hide a seam.

CPU validation:

```text
python -m unittest scripts.ci.test_sa_calobra_shoulder_contact scripts.ci.test_sa_calobra_tpp_survey_capture
```

This validates source-camera drift rejection, support triangle addressing,
bounded component selection, mode visibility and best-effort restoration,
PNG evidence and cleanup/failure handling. It does not substitute for the
Windows native captures or paired visual review.

The existing compile/test pass also runs
`YACS.ShoulderContactNative.ReadOnlyTriangles`: sparse IDs, selected/all reads,
invalid/null/duplicate IDs, query budget and exact unchanged fixture geometry.
Its fixture setup additionally uses the already retained native `AppendVertex`,
`InsertTriangle` and `SetMesh` methods; include those symbols in the installed
primary-header preflight. This native test still needs the actual Windows build.
