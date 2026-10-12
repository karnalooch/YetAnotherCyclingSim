# PCG365 natural rock palette producer

Status: local candidate for Issue #365 / M3. Three explicit source FBX downloads are verified; no Blender, Unreal, GPU, contact or visual proof has run for this batch. Production admission remains false.

The existing collection contains twenty affine derivatives of two prepared scans. Unique geometry hashes do not establish twenty visibly distinct natural morphologies. The next batch increases source diversity before adding more variants.

## Available sources

- Prepared Namaqualand Boulder 02 and 06: hash-pinned by `worldgen/sa_calobra/pcg365_large_scan_base_diagnostic_v1.json`; local derivatives preserve their source provenance and previous diagnostic history.
- Existing raw Rock07 and Rock09: `worldgen/sa_calobra/pcg365_rock_qualification_v1.json`; corrected LOD0 selection is separate. Do not combine embedded LOD meshes.
- Existing Boulder01: `D:/yacs/data/assets/pcg365-boulder-source`; the canonical asset provenance remains authoritative.
- New bounded candidates: official [Namaqualand03](https://polyhaven.com/a/namaqualand_boulder_03), [04](https://polyhaven.com/a/namaqualand_boulder_04), [05](https://polyhaven.com/a/namaqualand_boulder_05). Provider metadata was read with the existing identified YACS downloader User-Agent. All three provider pages declare [CC0](https://polyhaven.com/license). No geology or ground suitability is inferred from their origin or previews.

The acquisition candidate manifest is `scripts/blender/pcg365_rock_palette_acquisition_v1.json`. It binds exact provider FBX/blend URL, byte count and provider MD5, plus the complete metadata response SHA256. The three sibling `*_rock_provider_files.json` files preserve the actual API responses. Metadata-response hashes and separately recorded downloaded mesh SHA256 values are distinguished. FBX-only acquisition totals 7,377,060 bytes. The blend files are an optional reference route, not an instruction to acquire both formats. Preserve license and download index; verify provider MD5/bytes and record the downloaded SHA256 before making an inspection request. The coordinator subsequently authorized and this producer acquired only the three FBX files into `D:/yacs/work/pcg365/natural-palette-sources`. All provider size/MD5 checks and independent saved-file SHA256 checks passed. The original metadata-only manifest SHA is preserved in the acquisition receipt; the current manifest adds the acquired paths and SHA256 values. Existing source files were read for hash verification and were not modified.

## First owned DCC pass

`inspect_pcg365_rock_components.py` accepts a hash-bound schema1 request containing 1–8 rows `{id,path,sha256,bytes,license}`. Only FBX below existing `D:/yacs/data/assets` or `D:/yacs/work/pcg365` roots is accepted. The output file must be new, inside an existing owned PCG365 stage. Use pinned Blender4.5.9 through the existing launcher after the coordinator grants the host lease:

```powershell
python scripts/blender/run_headless.py run `
  --workspace-config D:/yacs/workspace.json `
  --script scripts/blender/inspect_pcg365_rock_components.py `
  --receipt work/pcg365/rock-palette-inspect01/host.json `
  -- --request <pinned-request.json> `
  --expected-request-sha256 <exact-sha256> `
  --output D:/yacs/work/pcg365/rock-palette-inspect01/inspection.json
```

The inspector records every imported object's actual name and matrix, all mesh LOD objects without automatic selection, vertex-connected triangle components, world bounds, surface area, triangle-index identities, boundary bounds, closedness, winding and signed volume where valid. Vertex connectivity uses mesh indices: coincident coordinates are never welded. Component indices follow ascending original triangle index and remain deterministic for the same importer output. Source SHA/bytes are checked before and after; nothing is exported or saved into a source asset.

N06 may be a geometrically connected cluster. A visual impression of four stones does not prove four separable components. If it has one connected component, extracting its lobes requires a separately declared source-only cut and cap operation, preserving the natural upper surface with an explicit discarded triangle inventory. Do not classify it as four families automatically or hide bridges through the material.

## Smallest meaningful next production batch

Inspect the five existing families and three new scans once. Select exactly one reviewed LOD0 object per source. Prefer large actual disconnected components when they remain natural whole stones; record selected and discarded component identities. Review their source silhouettes before defining twenty final recipe slots. Aim for at least eight useful natural source/component families with at most two or three bounded derivatives per family. A family that fails source integrity or looks repetitive is not promoted to meet the count.

Geometry preparation remains reversible and source-only. Preserve upper scan facets and UV/material provenance; record any underside cut, cap, pose or baked ART scale. No primitives, dome generators, convex-hull replacement, hidden unit correction, Landscape editing, road editing or automatic scatter. Contact fitting uses existing frozen policy and separate native proof. Forge presentation is separately authenticated in the Unreal consumer. Fresh native import, saved/fresh readback and real GPU views remain required; this plan grants none of those proofs.

## Current validation

Pure Python component tests: 3 PASS. Ruff: PASS. Source acquisition: PASS for exactly three FBX files, 7,377,060 bytes. Eight-source request byte/SHA binding: PASS. Blender execution, connected-component counts for the new batch, native import and visual review: NOT RUN. The inspector reports source self-intersection as UNKNOWN; manifoldness alone is not an intersection test.


## Verified acquisition and inspection handoff

| Source | Bytes | Downloaded FBX SHA256 |
|---|---:|---|
| Namaqualand03 | 2281932 | `5890e368f33ed9807966f2ff6daf57ef76d1e5c045947e906bb437bbed90a181` |
| Namaqualand04 | 2058860 | `72c573fa43e787a24f6bf98f96c24e2062e62c115d1937f45c20625d9af0856e` |
| Namaqualand05 | 3036268 | `20bec082d679d510dd840243dc78b251e2ce1ebeb36ff13d7c4b626fbf96e77b` |

The local provenance receipt is `D:/yacs/work/pcg365/natural-palette-sources/acquisition-receipt.json`. It binds the metadata-only acquisition manifest SHA, provider URLs/license/MD5/size and downloaded SHA256 values. No textures or blend files were downloaded. The fresh stage was created exclusively for these three candidates; existing historical output stages remain unchanged.

Inspection request: `scripts/blender/pcg365_rock_palette_inspection_request_v1.json`, SHA256 `cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0`. Its eight sources are original N02/N06 FBX (all objects must be inventoried), explicitly corrected LOD0 Rock07/Rock09, original Boulder01 FBX (all objects), and newly acquired N03/N04/N05. Each actual file's size and SHA256 was rechecked. The request does not select any new LOD or component, grant contact qualification or prove geometric family diversity.

## Generalized source-diverse producer candidate

`build_pcg365_natural_rock_collection.py` is a local candidate, not an executed producer proof. It requires the exact eight-source request above, an actual inspector receipt, and a separate reviewed selection file. It reuses the existing audited `prepare_pcg365_large_scan_bases.py` topology, source-only planar cut/cap validation and component ranking utilities, recording their code hashes. It does not change the old producer or native consumer.

Selection schema1 is `{schema_version:1, inspection_sha256:<actual receipt SHA>, selections:[...]}`. Exactly eight rows are required, with these fields only:

```json
{
  "id": "<one of the eight pinned source IDs>",
  "object_name": "<actual inspected mesh object name>",
  "component_index": 0,
  "component_triangles_sha256": "<actual inspected triangle-index SHA>",
  "cut_fraction": 0.10,
  "post_cut_selection": "KEEP_ALL",
  "variant_count": 2
}
```

The example values are a schema illustration, not selections. Real names, component indices and identity hashes must come from inspection. Each source has two or three variants, summing to exactly twenty; the producer rejects guessed object names, changed component identities, repeated/missing families, automatic selection modes and counts outside that bound. Source cuts must be explicitly frozen within 5–20% of selected source component height before execution, based on source geometry defects/underside preparation, never adjusted to a terrain/contact result. Any original open boundary must lie wholly below the declared cut. `KEEP_ALL` requires a single post-cut connected component; alternatively an explicitly selected `LARGEST_SURFACE_AREA` mode uses the existing deterministic surface-area/bounds/face-coordinate ordering, recording discarded upper triangle counts and all component measurements. It never silently switches mode or raises the cut.

Three fixed mild ART recipes are available per family: identity; scale `(1.08,0.94,0.90)` with lean `(0.025,-0.015)` per metre of height; scale `(0.93,1.05,1.10)` with lean `(-0.02,0.025)`. Source morphology supplies diversity across eight families; the recipes are not presented as independent scans. Their positive affine determinants preserve source orientation and baseZ0. Wholly upper triangle coordinates, UV corners, material indices, smooth flags, edge sharp/seam flags are checked exactly before base translation and declared ART transform. Geometric normals are recalculated after preparation; source custom split normals are explicitly not claimed preserved. The stock `normals_split_custom_set` zero-vector convention is verified in [Blender4.5.9 primary API source](https://raw.githubusercontent.com/blender/blender/v4.5.9/source/blender/makesrna/intern/rna_mesh_api.cc). Smoothing/sharp/seam flags and upper mesh custom-data readback are guarded after normal reset.

The cap uses installed stock `bmesh.ops.triangle_fill` with the previously audited HOLES/POLYS route. Every boundary loop must be simple, disjoint and planar within the existing 1µm numeric guard. Odd-even cap area, centroid containment, nonoverlap, downward winding and full connected closed manifold positive-volume checks remain mandatory. These are source-geometry checks, not terrain-contact admission. Upper overhang and source self-intersection remain unproven; preparation does not certify continuous terrain seating.

Producer CLI after actual inspection and reviewed selection exist:

```powershell
python scripts/blender/run_headless.py run `
  --workspace-config D:/yacs/workspace.json `
  --script scripts/blender/build_pcg365_natural_rock_collection.py `
  --receipt work/pcg365/natural-rock-collection01/host.json `
  -- --request scripts/blender/pcg365_rock_palette_inspection_request_v1.json `
  --expected-request-sha256 cca6cb185f48f586903f1285a2bba19b378873c14494cec89d8f09b548f44ea0 `
  --inspection D:/yacs/work/pcg365/rock-palette-inspect01/inspection.json `
  --expected-inspection-sha256 <actual-sha256> `
  --selection <reviewed-selection.json> `
  --expected-selection-sha256 <actual-sha256> `
  --output-directory D:/yacs/work/pcg365/natural-rock-collection01/derived
```

The output `natural-rock-collection.json` contains catalog-compatible variant fields: `id`, `source`, `source_relative`, FBX SHA/bytes, base/original source SHA, geometry and normalized shape hashes, recipe, expected native bounds/triangle count and license. Additional fields record cap loops, COM, source matrix, cut, source/prepared/derived topology, upper-preservation identity and excluded triangles. Actor scale remains1. The fresh output is never overwritten. A source preparation rejection is retained with its reason and any partially exported files; the receipt becomes `NATURAL_ROCK_COLLECTION_PARTIAL_REJECTION` and missing families are not replaced merely to force twenty outputs. Placement, qualified assets and production admission remain false/empty.

Validation: five pure selection-contract tests plus three component-graph tests PASS; Ruff PASS. Actual DCC import/cut/cap/export/readback, twenty distinct silhouettes, native UE catalog consumption and GPU art review remain NOT RUN. There is intentionally no real selection file before the first inspector receipt exists.
