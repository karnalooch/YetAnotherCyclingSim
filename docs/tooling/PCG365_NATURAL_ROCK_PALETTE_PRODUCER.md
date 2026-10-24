# PCG365 natural rock palette producer

Status: local candidate for Issue #365 / M3. Three additional CC0 FBX files were acquired, eight sources were inspected, and twenty source-derived FBX variants were prepared in pinned Blender4.5.9. Native Unreal/material/readback/GPU/contact and production admission remain unverified. Landscape, road and scatter were not changed.

## Authority and purpose

The existing twenty-rock collection was ten affine derivatives per two prepared scans. Unique geometry hashes did not establish twenty visibly distinct natural morphologies. This bounded continuation increases source diversity to eight actual source families, with at most three mild derivatives per source. World Building Bible, asset provenance, the existing Blender headless contract and the #365/M3 proof gates remain authoritative. No source processing grants geographic or terrain-contact admission.

## Licensed sources and acquisition

Existing sources: original Namaqualand02/06 (`worldgen/sa_calobra/pcg365_large_rock_sources_v1.json`), explicitly corrected LOD0 Rock07/09 (`worldgen/sa_calobra/pcg365_rock_lod0_qualification_v1.json`), and Boulder01 (`D:/yacs/data/assets/pcg365-boulder-source/acquisition-sha256-receipt.json`). Existing source files and historical output stages were not overwritten.

Three new explicit candidates are official [Namaqualand03](https://polyhaven.com/a/namaqualand_boulder_03), [04](https://polyhaven.com/a/namaqualand_boulder_04) and [05](https://polyhaven.com/a/namaqualand_boulder_05). Their provider pages declare [CC0](https://polyhaven.com/license). No geology or ground suitability is inferred from geographic origin or previews. Official API access used the repository's existing identified YACS downloader User-Agent; plain urllib requests returned403.

Manifest: `scripts/blender/pcg365_rock_palette_acquisition_v1.json`. Three sibling `namaqualand_boulder_0{3,4,5}_rock_provider_files.json` files retain complete official API responses, each bound by SHA256. FBX and optional blend URL/bytes/provider MD5 are recorded separately from downloaded mesh SHA256. The coordinator authorized only the three FBX downloads into a fresh `D:/yacs/work/pcg365/natural-palette-sources`; no textures or blend files were downloaded.

| Source | Downloaded bytes | Provider MD5 | Downloaded FBX SHA256 |
|---|---:|---|---|
| N03 | 2281932 | `7db8e6ecbcc8712319c357bdf142deab` | `5890e368f33ed9807966f2ff6daf57ef76d1e5c045947e906bb437bbed90a181` |
| N04 | 2058860 | `0bc2445f3423907b3cff3a03ae95e2c1` | `72c573fa43e787a24f6bf98f96c24e2062e62c115d1937f45c20625d9af0856e` |
| N05 | 3036268 | `01a8646f4664bf74f8f7ce749b5aa19b` | `20bec082d679d510dd840243dc78b251e2ce1ebeb36ff13d7c4b626fbf96e77b` |

Total7,377,060bytes. Provider size/MD5 and independent saved-file SHA256 checks passed. The local `acquisition-receipt.json` retains the metadata-only pre-download manifest SHA, URLs/license/provider MD5/bytes/downloaded SHA256. The current workspace manifest adds acquired paths and hashes. An asset SHA is not confused with its metadata response SHA.

## Actual eight-source inspection

Request: `scripts/blender/pcg365_rock_palette_inspection_request_v1.json`, SHA256 `cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0`. Every actual source file's byte count/SHA256 was rechecked. The request includes raw N02/N06, corrected explicit LOD0 Rock07/Rock09, raw Boulder01 and new N03/N04/N05. Raw FBX sources are inventoried as all objects; embedded LODs are never combined.

`inspect_pcg365_rock_components.py` accepts a hash-bound schema1 request containing1-8rows `{id,path,sha256,bytes,license}` below existing `D:/yacs/data/assets` or `D:/yacs/work/pcg365`. The output must be fresh and below an existing owned PCG365 stage. It records actual object names/matrices, all mesh LOD objects, vertex-connected render-triangle components, world bounds, areas, triangle-index identities, boundary bounds, closedness/winding and signed volume where verified. Mesh indices define connectivity; coincident positions are never welded. Components follow ascending original render-triangle index. Sources are hashed before/after; the inspector exports or mutates nothing.

```powershell
python scripts/blender/run_headless.py run `
  --workspace-config D:/yacs/workspace.json `
  --script scripts/blender/inspect_pcg365_rock_components.py `
  --receipt work/pcg365/rock-palette-inspect01/host.json `
  -- --request scripts/blender/pcg365_rock_palette_inspection_request_v1.json `
  --expected-request-sha256 cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0 `
  --output D:/yacs/work/pcg365/rock-palette-inspect01/inspection.json
```

Actual inspection completed pinned Blender4.5.9 exit0. Receipt SHA256 `bf1c2129201448b63e54e43d7f69cba109cf920ab415ab11da8f50da0d3c2b23`. All eight LOD0 sources have one actual vertex-connected component. N06's apparent separate stones are not disconnected components and are not counted as extra families. Boulder01 has four LOD objects; only actual `boulder_01_LOD0` was selected. Each source has one UVMap and one original material slot.

| Actual source LOD0 | Render triangles | Original boundary edges |
|---|---:|---:|
| N02 | 97964 | 396 |
| N06 | 109114 | 0 |
| Rock07 corrected | 14844 | 0 |
| Rock09 corrected | 12416 | 0 |
| Boulder01 | 66122 | 0 |
| N03 | 64826 | 0 |
| N04 | 59066 | 0 |
| N05 | 89618 | 0 |

Original N02 is open: original signed volume remains UNVERIFIED. Source self-intersection is UNKNOWN for every source; manifoldness is not an intersection test.

## Generalized producer contract

`build_pcg365_natural_rock_collection.py` requires exact request SHA, actual inspector SHA and a separately reviewed selection SHA. Exactly eight selection rows and twenty variants are required, with two or three variants per source. The selection is bound to actual object names and actual component triangle-index hashes; no LOD/component is guessed.

Selection schema1: `{schema_version:1, inspection_sha256:<actual receipt SHA>, selections:[...]}`. Allowed row fields:

```json
{
  "id": "<one of the eight pinned source IDs>",
  "object_name": "<actual inspected LOD0 name>",
  "component_index": 0,
  "component_triangles_sha256": "<actual inspected hash>",
  "cut_fraction": 0.10,
  "post_cut_selection": "KEEP_ALL",
  "variant_count": 2
}
```

This is a schema illustration, not guessed selection data. The real selection files were written only after actual inspection. Selection v1 SHA256 `66037cca8a8f25da76da777821b75783beb4a965cece4768b25c5e14b6ef9802` chooses three variants each from N03/N04/N05/Boulder01 and two each from N02/N06/Rock07/Rock09. V2 (`scripts/blender/pcg365_natural_rock_selection_v2.json`, SHA256 `45fb615895582e7e360b75ad614850a784730357ea2ec652ec49e6ee1f502e5e`) changes only N03 to largest post-cut component after observed source-only disconnection.

Cuts are declared within5-20percent of selected source height before execution, based on source geometry/underside repair, never adjusted to terrain-contact measurements. Actual cuts remain N02's previously established12percent and10percent for all others. Every original open boundary must lie wholly below the cut. KEEP_ALL requires a single post-cut component; LARGEST_SURFACE_AREA explicitly uses the existing deterministic area/bounds/canonical-face tie break and records every component plus excluded wholly upper triangles. It never silently switches selection mode or raises the cut.

N03 contains source quads. The producer explicitly materializes the exact inspected `Mesh.loop_triangles`, mapping original loop UV/material/smooth and source edge sharp/seam flags. It does not choose an alternative diagonal. Bisect-created clipped polygons are triangulated using the existing FIXED/EAR_CLIP operation. Wholly upper triangle coordinates, UV corners, material indices, face smooth and edge sharp/seam flags are checked exactly before base translation and declared ART transform.

The producer reuses audited `prepare_pcg365_large_scan_bases.py` helpers and records dependency hashes. Stock `bmesh.ops.triangle_fill` uses the previously verified HOLES/POLYS route. Boundary loops must be simple/disjoint/planar within the existing1micrometre numeric guard. Odd-even area, centroid containment, triangle nonoverlap, downward cap winding and full connected closed manifold positive-volume checks remain mandatory. Caps and source cuts do not certify continuous ground contact or absence of upper overhang.

Fixed recipes: identity; scale `(1.08,0.94,0.90)` with lean `(0.025,-0.015)` per metre of height; scale `(0.93,1.05,1.10)` with lean `(-0.02,0.025)`. Positive affine determinant and baseZ0 are checked. These are mild derivatives of eight natural source families, not twenty independent scans. No dome, primitive, hull, plinth or source overwrite is generated.

Source custom split normals are not claimed preserved. The zero-vector custom-normal reset is documented in [Blender4.5.9 primary API source](https://raw.githubusercontent.com/blender/blender/v4.5.9/source/blender/makesrna/intern/rna_mesh_api.cc), but actual N05 execution changed sharp/smooth flags and was rejected. The corrected producer does not call it: fresh mesh data must have no custom normals, geometric normals honor retained smooth/sharp flags, and the complete upper geometry/UV/material/smooth/sharp/seam identity is independently read back through BMesh.

```powershell
python scripts/blender/run_headless.py run `
  --workspace-config D:/yacs/workspace.json `
  --script scripts/blender/build_pcg365_natural_rock_collection.py `
  --receipt work/pcg365/natural-rock-collection03/host.json `
  -- --request scripts/blender/pcg365_rock_palette_inspection_request_v1.json `
  --expected-request-sha256 cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0 `
  --inspection D:/yacs/work/pcg365/rock-palette-inspect01/inspection.json `
  --expected-inspection-sha256 bf1c2129201448b63e54e43d7f69cba109cf920ab415ab11da8f50da0d3c2b23 `
  --selection scripts/blender/pcg365_natural_rock_selection_v2.json `
  --expected-selection-sha256 45fb615895582e7e360b75ad614850a784730357ea2ec652ec49e6ee1f502e5e `
  --output-directory D:/yacs/work/pcg365/natural-rock-collection03/derived
```

The exact stage03 command is historical evidence; reruns must choose a fresh stage. Output `natural-rock-collection.json` contains catalog variant ID/source/source_relative, FBX SHA/bytes, base/original source SHA, geometry/normalized-shape hashes, recipe, expected native bounds/triangles, license, cap loops/COM, source matrix/cut/topology and upper-preservation witnesses. Native actor scale remains1. Source rejection retains reason and unadmitted partial files and produces PARTIAL_REJECTION; missing families are never replaced merely to force twenty. Placement, qualified assets and production admission remain false/empty.

## Actual production and proof limits

Stage01 completed exit0 but prepared0/20: it exposed omitted clipped-face triangulation and N03 source quads. Stage02 completed exit0 with14 prepared variants/six families: N03 failed declared KEEP_ALL and N05 failed normal-reset flag preservation after exporting its first partial FBX. Both stages, rejection receipts and partial files remain unchanged. Exit0 alone is not complete production.

Stage `D:/yacs/work/pcg365/natural-rock-collection03` completed pinned Blender4.5.9 exit0 in127.984seconds. Receipt `derived/natural-rock-collection.json`, SHA256 `3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc`, status NATURAL_ROCK_COLLECTION20_PREPARED_ONLY: **20 FBXs, eight families, zero rejected sources**. Every saved FBX size/SHA was independently rechecked. All derived meshes are connected, consistently wound closed manifolds, with positive signed volume and zero boundary/nonmanifold edges. Twenty geometry hashes and twenty normalized edge-length hashes differ; that does not replace visual acceptance.

| Source | Variants | Derived triangles/variant | Preserved wholly upper triangles | Excluded upper triangles |
|---|---:|---:|---:|---:|
| Boulder01 | 3 | 65130 | 63932 | 0 |
| N02 | 2 | 82558 | 78421 | 37 |
| N03 | 3 | 52084 | 50256 | 4 |
| N04 | 3 | 46886 | 45339 | 0 |
| N05 | 3 | 84424 | 82907 | 0 |
| N06 | 2 | 103250 | 101869 | 0 |
| Rock07 | 2 | 11256 | 10327 | 0 |
| Rock09 | 2 | 11178 | 10146 | 0 |

N03 retained post-cut component:50987faces/13.033959square metres; four discarded small components:40/10/6/8faces and0.002576/0.000180/0.000103/0.000061square metres. Only four wholly upper triangles were excluded. N02 retained80094faces/6.578727square metres; all small components and37excluded upper triangles are recorded. Upper preservation refers to the retained selected source component, not every original source triangle. Original FBX hashes remain unchanged.

Host receipt GitHEAD was `59b55497c71c6c74860aca64ff944fe30e9095d6` while this new producer was an uncommitted local candidate. Raw producer file SHA256 `87ad5772bb3e95e202e970bf1fa8b8c74d481453636762bc3f5ea4819c135546`; normalized LF source SHA256 `1290715fa7692a5e5c8d19926ef3dca61d71e6b09124c9c6d16eafbff2b960ca`. This is source-script-bound local diagnostic evidence, not committed-head native or CI admission. Dependency file hashes are retained in the receipt.

Actual units are preserved: baseline N03 is240.71x306.54x132.59cm, baseline N04 is252.22x249.64x171.04cm, and small Rock09 is7.40x14.46x2.96cm. Variants reach324.06cm across N03 and188.15cm high for N04. Studio layout/camera must use actual bounds; no implicit rescale or relabeling as the old rock02/rock06 families. The existing native catalog validator's two-family ID regex requires a coordinator-owned explicit update before consumption. Renderer/launcher were not edited here.

Blender lease released after fresh host IDLE/no Blender at2026-10-12T12:35:37UTC. Validation: five pure selection tests plus three component tests PASS; Ruff PASS; actual DCC source inspection/preparation PASS. Remaining: integration/commit, fresh native import, Forge binding, saved/fresh readback, GPU views and family-diversity review. Source self-intersection, continuous footprint/contact, regional placement, performance, protected CI and production admission remain unverified. No terrain/road/scatter changes, no remote push or commit by this producer agent.
