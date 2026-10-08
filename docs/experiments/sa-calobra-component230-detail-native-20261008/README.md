# Component 230: native detail mask and first bounded treatment

**Work item:** [#445](https://github.com/karnalooch/YetAnotherCyclingSim/issues/445),
[draft PR #446](https://github.com/karnalooch/YetAnotherCyclingSim/pull/446).
**Authority:** [World Building Bible](../../WORLD_BUILDING_BIBLE.md), selected
through [the documentation index](../../README.md).

## Purpose and execution status

Continue the [source-face pilot](../sa-calobra-component230-detail-pilot-20261008/README.md)
inside the existing Unreal v8 scene. The original CPU projection ignores other
scene occluders. This experiment must show the actual selected faces under
renderer depth and establish a visible witness for one local patch before its
native treatment is applied.

The bounded producer and native comparison are implemented. Local producer and
integration checks pass; the exact-head Unreal build, Automation and capture
remain pending. No new native capture, visual improvement or performance
result is claimed at this stage. The exact commit, run and inspected artifacts
will be recorded after execution.

The final local gate ran 86 focused Python tests: 85 passed and the PowerShell
parser check was skipped because this Linux environment has no `pwsh`. The
same check remains enabled on the native runner. Ruff checks, Python
compilation and all four documentation guards passed. Two real
`YACS.DetailNative` Automation tests are implemented but have not yet been run
in Unreal at this status.

## Fixed inputs

| Input | Identity |
| --- | --- |
| Pilot implementation | `a05a4a727b4e1646649842ecb777e842e2984437` |
| Accepted v8 implementation | `4f2cba560d54931dc8ba080370d96a7aad24f15b` |
| Retained source capture | `b1ea05b33b9f3208e7aeb6884f1a67792d9c6121`, run `37800814004`, attempt `1` |
| Combined mesh SHA-256 | `a9d34dbfb32a59b592dca561a7d7b0e53f7d02d90c095cff7c0812c249247965` |
| Native source receipt SHA-256 | `35c76796924681c4d836388761bcc3ee83dd6e9fa544c3adb109e004e1c58225` |
| Camera CSV SHA-256 | `15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3` |

The source has 29,415 vertices and 58,216 ordered triangle rows. The pilot
proposes 324 A faces and 211 B faces. Of those selections, 96 touch protected
vertices and are excluded from treatment. Source-face row indices are never
silently interpreted as native Unreal triangle IDs.

The two frozen camera poses are `window-0021-forward-00005` and
`window-0023-forward-00000`, from the unchanged captured camera CSV. This is
selected-view evidence. It does not establish hidden surfaces across the world,
continuous traversal, reverse-direction completeness or band D.

## Treatment boundary

The producer selects the largest edge-connected eligible A patch with strict
interior vertices. `SILHOUETTE_CRITICAL` faces are excluded. Every vertex
incident to a face outside the selected patch remains fixed, including all
protected, B and U face interfaces. Selection is deterministic, with stable
face-row tie breaking.

The actual sparse pilot mask yields a 65-face patch with 51 vertices: 35 fixed
boundary vertices and 16 strict interior vertices. An additional frozen ring
would leave no movable vertex in any A component; the experiment therefore
freezes the exact outside-incident boundary without expanding the mask.

Only a gentle local normal-direction fairing candidate is prepared. The 5 cm
v8-relative displacement is a ceiling, not a target amplitude; the source
relative displacement must remain at most 50 cm, with numerical tolerance
recorded by the producer. Source XYZ, flags, vertex identity, triangle rows and
winding remain unchanged. Outside-face geometry and protected interfaces must
match exactly. Degenerate triangles, folded faces and nonmanifold output are
rejected. The treatment is an AI proposal, not inferred geology or a repaired
defect classification.

The verified retained input produces the following measured candidate:

| Measure | Result |
| --- | --- |
| Selected / actually changed faces | 65 / 56 |
| Changed vertices | 16 |
| Maximum additional movement | 0.5230451206 cm (5.23 mm) |
| Maximum source displacement among changed vertices | 32.3769206004 cm |
| Global source displacement maximum | 50.00000000000475 cm, within the retained 0.000001 cm numerical tolerance |
| Outside or protected geometry changes | 0 |
| Minimum 3D / XY triangle area ratio | 0.9992782462 / 0.9955198982 |
| XY orientation flips | 0 |
| Normal-direction fairing residual RMS | 0.4641598174 to 0.3343247926 cm |
| Trial mesh SHA-256 | `aed8f5ace6383f67004b5df6bb24da0db820cabd99ecb6186efc0b79f86d35b3` |

These values describe one factor-0.5 Jacobi normal-direction pass. The residual
is an algorithm measure, not a visual quality score. Global triangle
self-intersection testing is not performed; this bounded 2.5D trial checks
orientation and minimum area in both 3D and the source XY projection.

## Native comparison and visibility

The native consumer works on the existing v8 mesh and its native attributes.
It validates source geometry and an explicit face-row/native-ID mapping before
assigning diagnostic material IDs or moving vertices. It does not reconstruct
the accepted surface from OBJ, recalculate every normal or replace its UVs.

For each fixed pose the proof records the v8 limestone baseline,
colored A/B/protected mask, two patch-only color witnesses and the bounded
limestone trial. The patch witnesses change only the diagnostic patch color
between magenta and cyan, using ordinary scene depth. Corroborating changed
pixels must lie inside that patch's projected triangles. The trial requires a
minimum of eight corroborated pixels in at least one of the two poses. The
paired images and pixel inventory are hash-bound into an immutable witness
before trial geometry is applied. This tests the selected
patch against the scene occluders present in those rendered views; it does not
declare every selected face visible or validate all proposed bands.

Native normals referenced by any outside/protected face are preserved. Only
wholly patch-owned normal elements may be recomputed. The limestone baseline
and trial retain the existing material and 3 m physical UV scale. Diagnostic
colors do not imply production material changes.

## Remote proof and preservation

The existing Component 230 workflow uses a separate owner-only `[detail-native]`
push intent for the reviewed PR branch. It verifies the exact event SHA,
retained-source identities, idle host, accepted scene inputs and required
build/Automation before capture. The `YACS.DetailNative` tests exercise sparse
native triangle IDs, rejected source and boundary changes, exact untouched
positions, split UVs, shared normals and complete native snapshot restoration.
Unrelated PCGEx generation and the complete
1,338-frame survey are outside this narrow proof.

Outputs use a fresh directory under the configured persistent workspace work
tree. Uploads contain selected PNGs, manifests, candidate data and diagnostic
logs; they do not copy the full retained survey archive.

The native owner restores its mesh snapshot, transient actors, component
visibility, materials, lights and other scene state. Map bytes, source
heightfield, tracked checkout and frozen source inputs must remain unchanged.
`map_saved`, `assets_saved`, `canonical_landscape_mutation` and collision remain
false. Existing dynamic shadow settings are retained.

The previous combined lighting gate and separate PCGEx admission remain as
recorded in the [repair plan](../../tooling/SA_CALOBRA_COMPONENT230_REPAIR_PLAN.md).
This proof does not close them, replace v8, save production content, establish
whole-Landscape quality or measure the 1080p/60 budget. Owner visual acceptance
and protected merge remain separate decisions.

## Reproduce the pure candidate

```bash
python scripts/assets/prepare_sa_calobra_detail_treatment.py \
  --mesh /path/to/verified/combined-mesh.json \
  --mask docs/experiments/sa-calobra-component230-detail-pilot-20261008/pilot/triangle-bands.json \
  --output /path/to/fresh/detail-treatment
python -m unittest scripts.assets.test_sa_calobra_detail_treatment -v
python scripts/ci/check_docs_index.py
```

Native execution uses UE 5.8 and the repository's existing runner/proof
entrypoints. PCGEx remains pinned at 0.79 / commit
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`; this experiment does not replace
or modify that topology producer.

Primary API references for the bounded native operations:

- [Epic UE 5.8 FDynamicMeshAttributeSet](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/GeometryCore/FDynamicMeshAttributeSet).
- [Epic UE 5.8 FMeshNormals](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/GeometryCore/FMeshNormals).
