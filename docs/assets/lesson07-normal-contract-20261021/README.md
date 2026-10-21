# Lesson07 normal contract: pinned offline source inspection

## Decision

**Superseding owner direction, 2026-10-21:** download and inspect the original
SideFX Landscape Workflow3 package and Lesson07 again, then reproduce that
workflow. The private normal candidate described below is paused and has never
run in Unreal. The freshly downloaded official package contains the same
`MF_PE_TextureAtlas_SampleNormal` bytes as this inspection. Therefore the
proposed changes below are a separate adaptation, not restoration of missing
original SideFX bytes. They are not the next admitted implementation step.

The saved source supports a narrowly scoped normal repair with **three linked changes**:

1. Set all four texture samplers in a project-private copy of `MF_PE_TextureAtlas_SampleNormal` explicitly to `SAMPLERTYPE_Normal`.
2. Correct the two function-output producer links: `BR` must read `MaterialExpressionTextureSample_13`, and `TL` must read `MaterialExpressionTextureSample_14`. Preserve RGB masks and reconnect both callers by unique semantic input/output names after duplication; do not assume duplicated GUIDs retain the old cache order.
3. Preserve the existing channel rotation in the master, while replacing the R-derived `1-R` component with `-R`: `(G,1-R,B)` becomes `(G,-R,B)`.

Changing only the sampler type and sign leaves a proved BR/TL tile-ID mismatch. Changing the entire swizzle to XYZ is not justified by this inspection.

This is source analysis. It does not record a performed repair, shader compilation, runtime acceptance, visual acceptance, performance result, or fresh reopen. The originals were downloaded and read only. No UE invocation, native observer replay, or uasset serialization to disk occurred during this inspection. The following report and exact evidence were subsequently retained in the existing delivery repository.

The compact review artifact is [normal-contract-evidence.json](normal-contract-evidence.json), 46,950 bytes, SHA256 `1be16149e7fbe87770eae7bdad11444da7d7bd477e4ca12dd9696e7273bd49c7`. It includes source pins, sampler tags, exact connection fields, function output GUIDs, caller mapping, selected expression payload hashes, the normal value path, and explicit limitations.

## Source identity and parser

All assets came from public GitHub media at commit `c59f717f11b134f75f695a26b94f8655bd3bd271`. Every payload matched its complete expected LFS SHA256 and size before being stored. The extra `MF_PE_Material` and `MF_PE_BlendLayers` pins came from canonical public LFS pointers at that same immutable commit.

| Source | Bytes | SHA256 |
| --- | ---: | --- |
| MF_PE_TextureAtlas_SampleNormal | 20,948 | `bb556279f30c6d116a4c24ae18a5234af28cf27cd9f2f59e43e6f85f71d5032a` |
| M_Landscape_YACS | 208,956 | `53a1d68a97a5205a25463dea5c6aaaec4a9bb1167a1ce9e131a84406327fad66` |
| MF_PE_TextureAtlas_Sample | 20,824 | `688e07e906f5c8273d3acaadedc46aa5251d984b54f2d50e002b6bd082c5c5b2` |
| MF_PE_TextureAtlas_SampleMasks | 22,310 | `a5c39ede4f354fe42fbfedf5c07383b0362b651c8a60672679a54bdaf9eda282` |
| MF_PE_BilinearBlend | 13,914 | `f67f4057eba49d734c6dcd54e260f17a4edc350ed713d8af85f12942174dc64d` |
| MF_PE_Material | 13,312 | `2fbd815bdd95f909336eea263ee393329603a03e352e01b3669559178436f71d` |
| MF_PE_BlendLayers | 15,602 | `b4c8c26908bc0b3da33d60ce10b07e395700cf5aa080871e42a75a4770562acb` |

The maintained reader is official **UAssetAPI 1.1.0**, source revision `73530811a9d91ffa8959a1a4cb74cc3b9c5c6bed`. The [official NuGet catalog entry](https://api.nuget.org/v3/catalog0/data/2026.05.01.04.55.34/uassetapi.1.1.0.json) pins that revision and supplies the published SHA512, which matched the downloaded package. The package SHA256 is `c14060d9303ef1a488d07a82b947022b83f97be11f7799b772f4bcdbe7064221`; the loaded `UAssetAPI.dll` SHA256 is `4048337707660c7c3d810b37747049c85c228d0ed602112685098047bd59dbab`.

The reader ran in an isolated .NET assembly load context, using the verified package and verified Newtonsoft.Json 13.0.3 dependency. No user credentials were accessed. The constructor used `EngineVersion.UNKNOWN`, no mappings, and no serialization override flags. The packages are versioned tagged packages; no engine version or CDO value was guessed.

All six material functions record **UE 5.3.1**, compatible **5.3.0**, UE4 object version **522**, UE5 object version **1009**. Each has a successful complete **in-memory binary equality** check. The master records **UE 5.8.2**, compatible **5.8.0**, object versions **522/1018**. The library's separate retail-version estimate is 5.2 for those functions and 5.7 for the master; it is an estimate from serialization/custom versions, not a replacement for the saved engine-version fields.

The exact release implementation of [`VerifyBinaryEquality`](https://github.com/atenfyr/UAssetAPI/blob/73530811a9d91ffa8959a1a4cb74cc3b9c5c6bed/UAssetAPI/UAsset.cs) was checked: it reads the original and compares against `WriteData()` in a `MemoryStream`. It does not invoke the disk-writing `Write(path)` method. All seven original hashes remained unchanged after inspection.

### Precise master limitation

The master does **not** have a complete package roundtrip PASS. The memory serialization is 208,903 bytes, 53 bytes shorter than the source. The 53-byte size difference occurs before the first export payload. We do not assign it an unsupported specific header/metadata cause.

Using the official reader's export offsets and sizes, the original and serialized export payloads were compared independently:

- **262 of 263** export payloads have identical size and SHA256.
- **All 260 `MaterialExpression*` payloads are byte-identical.** This includes every sampler call, output cache, OneMinus, MakeFloat3, Normal getter/setter, and UV node used in this decision.
- The main `M_Landscape_YACS` export is also byte-identical.
- The only unequal export is `M_Landscape_YACSEditorOnlyData`, 4,453 bytes on both sides. Exactly one byte differs at relative offset 138: source `0x34`, memory serialization `0x40`.

The resulting evidence is sufficient for the identified expression fields. It does not authorize rewriting the master through this library or treating the complete package/EditorOnlyData decode as certified.

## Exact sampler and corner findings

All four original normal samplers have `SamplerSource=SSM_Wrap_WorldGroupSettings`. `MaterialExpressionTextureSample_15` has an explicit `SAMPLERTYPE_Normal` tag. Samples `_7`, `_13`, and `_14` omit `SamplerType`; their current live CDO values are not proved by an omitted tag. Historical readback describes three Color samplers and one Normal sampler, but this inspection does not replace that with a new runtime claim. The corrective requirement is explicit Normal for all four.

The function inputs are Texture2DArray `Texture`, Vector2 `UVS`, and Vector4 `Samples`. Each sampler's TextureObject input refers to the same Texture input. Coordinates append UVS and one component of Samples:

| Sampler | Coordinates producer | Array slice component |
| --- | --- | --- |
| TextureSample_7 | AppendVector_0 | Samples.R |
| TextureSample_13 | AppendVector_1 | Samples.G |
| TextureSample_14 | AppendVector_3 | Samples.B |
| TextureSample_15 | AppendVector_4 | Samples.A |

Colour and Masks functions consistently expose BL/BR/TL/TR from Samples.R/G/B/A. The saved Normal function exposes BL/BR/TL/TR from Samples.R/B/G/A. This is an actual source-producer mismatch, not a conclusion drawn from ambiguous output sorting.

| Material corner | Colour/Masks component | Saved Normal component | Normal caller output index | Detail/Macro consumer calls |
| --- | --- | --- | ---: | --- |
| BL | R | R | 0 | 31 / 39 |
| BR | G | **B** | 2 | 32 / 40 |
| TL | B | **G** | 1 | 34 / 41 |
| TR | A | A | 3 | 35 / 42 |

Calls `_27` and `_38` cache Normal outputs in order BL, TL, BR, TR. Their cached GUIDs match the function's actual output IDs:

| Output | Function expression | GUID | Current producer | Correct producer |
| --- | --- | --- | --- | --- |
| BL | FunctionOutput_0 | `21A446EA-42DE-E7B9-1B90-D9B9048B5CE4` | TextureSample_7 | unchanged |
| BR | FunctionOutput_1 | `96B643CF-41EB-4C07-F125-DBB4F331ABD7` | TextureSample_14 | TextureSample_13 |
| TL | FunctionOutput_2 | `ABA00D55-4FAF-5B7C-98B3-45802B10EFD4` | TextureSample_13 | TextureSample_14 |
| TR | FunctionOutput_3 | `9C01F43D-41B7-4762-2E16-13AA20C5DD16` | TextureSample_15 | unchanged |

Every output's A input retains `OutputIndex=0`, `Mask=1`, `MaskR/G/B=1`, `MaskA=0`. BR and TL both have serialized SortPriority 1; GUID matching removes that sorting ambiguity. Those IDs and numeric indices describe the original saved assets. A private duplicate may regenerate IDs; its corrected function and both caller caches must agree by the actual duplicated GUIDs, and all eight Normal consumers must be reconnected by BL/BR/TL/TR names.

## Why signed negation is source-justified

After explicit Normal sampling of a Normalmap-compressed texture, the normal-vector path contains no further encoding into colour values:

1. `MF_PE_Material` sends its Normal input directly to the Normal material attribute, GUID `0FA2821A-200F-4A4A-B719-B789C1259C64`. Its ConstantBiasScale(-0.5,2) belongs only to ORD.B and displacement.
2. `MF_PE_BlendLayers` reads Detail.Normal and Macro.Normal, interpolates them through `MaterialExpressionLinearInterpolate_2`, and writes Normal. Brightness multiplies BaseColor only.
3. `MF_PE_BilinearBlend` combines the material attributes using three BlendMaterialAttributes nodes. It adds no bias, remapping, or encoding to the normal components.
4. Master call `_45` feeds named reroute `_67`, then GetMaterialAttributes `_1` extracts Normal and BreakOutFloat3 call `_43` separates it.

The exact master inputs are:

- MakeFloat3 call `_30` X receives `_43` output index 1, cached name G, with no mask.
- MakeFloat3 `_30` Y receives OneMinus `_4`.
- OneMinus `_4` receives `_43` output index **0**, cached name **R**, with no mask. The old default-output ambiguity is resolved.
- MakeFloat3 `_30` Z receives `_43` output index 2, cached name B, with no mask.

Thus the saved operation is `(G,1-R,B)`. [Epic documents OneMinus as the componentwise operation `1-X`](https://dev.epicgames.com/documentation/en-us/unreal-engine/math-material-expressions-in-unreal-engine). For a signed normal vector, negating the R-derived axis requires `-R`. This preserves the already-present channel rotation and fixes its offset: the neutral vector `(0,0,1)` otherwise becomes `(0,1,1)`; the proposed operation keeps it `(0,0,1)`.

This reasoning establishes the sign correction once all four samples follow the Normal sampler contract. It does not claim that all current live branches already do so, and it does not independently certify the chosen Landscape tangent orientation. The existing final FlattenNormal operation and approved Flatten=1 checkpoint are separate runtime state; no flatten parameter was changed here.

The direct normal texture-coordinate route is TextureCoordinate `_5` → Reroute `_0` → Multiply `_15` with Detail Tiling or Multiply `_7` with Macro Tiling → calls `_27`/`_38`. TextureCoordinate's CDO values are omitted from the package and were not invented. Their omission does not change the neutral-vector sign proof.

## Evidence files and reproducibility

- `download-receipt.json`, `normal-dependencies-download.json`, and `blend-layers-download.json`: immutable public source URLs, source commit, expected SHA256, sizes, and official parser provenance.
- `parser-receipt.json`: decoded saved versions, parser assembly hashes, original-byte preservation, and equality results.
- `*.uasset.json`: official UAssetAPI JSON representation.
- `*.uasset.connections.json`: public decoded ExpressionInput fields, including producer index, output index, input name, and RGBA masks.
- `M_Landscape_YACS.uasset.memory-diff.json`: the scoped master equality limitation and independent hashes of every original and memory-serialized export payload.
- `resolved-source-graph.json`: resolved names and cached output names for all inspected connections; SHA256 `a5ff45819b95cf015ca72ad480cf33094fb74ce39e93e42d2e891d6659939a9a`.

**JSON caveat:** UAssetAPI's default `SerializeJson` omits inherited MaterialInputPropertyData connection fields. Its apparent `Value:0` is not the producer reference. The separate connections files read the library's public decoded fields directly; [the pinned official MaterialInputProperties implementation](https://github.com/atenfyr/UAssetAPI/blob/73530811a9d91ffa8959a1a4cb74cc3b9c5c6bed/UAssetAPI/PropertyTypes/Structs/Engine/MaterialInputProperties.cs) defines those fields and the read/write contract. No custom binary decoder was introduced.

The minimal authoring proposal remains subject to native preflight, correct duplicate/retarget/update behavior, shader compilation, then controlled visual inspection. This report supplies source knowledge for that work; it does not waive those checks or bypass the frozen observer boundary.

## Retained evidence and paused native candidate

The [evidence index](evidence-index.json) binds the exact compact contract, source-download receipts and byte-preserving gzip archives of the resolved graph, parser receipt and scoped master comparison. Raw source packages and parser binaries are not duplicated here.

The paused proposal would create only a new project-private function and master under `Materials/NormalRepair_20261021`. It leaves the active material instance, its parent, Flatten, the map and all arrays unchanged. Duplication may regenerate function input/output GUIDs, so implementation must explicitly reconnect the two callers and eight consumers by unique semantic pin names and verify the resulting links; it must not assume that duplicated GUIDs or tied output sort priorities preserve old numeric indices. This does not change the source diagnosis above. Native compilation must return an explicit empty error list before the private candidate is saved. No native candidate execution or application is claimed by this source report.
