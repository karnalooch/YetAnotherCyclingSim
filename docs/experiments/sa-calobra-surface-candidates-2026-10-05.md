# Sa Calobra surface candidate comparison — 2026-10-05

Status: **visual shortlist delivered; production-set approval pending**.
Issue [#363](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363),
draft [#381](https://github.com/karnalooch/YetAnotherCyclingSim/pull/381).
The owner authorized this comparison after reviewing the proposed surface
direction. This does not record acceptance of a production asset set.

## Authority and unchanged boundaries

Selected through [docs/README.md](../README.md):
[World Building Bible](../WORLD_BUILDING_BIBLE.md) owns methodology,
[Roadmap](../ROADMAP.md) sequence, [Asset Plan](../ASSET_PLAN.md) and
[provenance ledger](../legal/DEPENDENCY_PROVENANCE.md) acquisition/admission.
The [reference brief](sa-calobra-material-reference-review-2026-10-05.md)
retains 16 aerial sectors, three dated photographic locations and evidence gaps.

No terrain, road, CUT/FILL, mask, material, Unreal package, PCG graph or runtime
configuration changed. The old material remains rejected; #364 stays blocked.
No Houdini, plugin, paid purchase or new dependency is introduced.

## Deliverables and replay

- [Comparison decisions](../../worldgen/materials/sa_calobra_surface_comparison_20261005.json): six roles, 26 comparisons, recommendations, alternatives and rejection reasons. Owner-facing board text is Polish.
- [Review receipt](../../worldgen/materials/sa_calobra_surface_review_receipt_20261005.json): 21 unique source IDs, providers/authors, exact URLs, licences, bytes, checksums, published dimensions and available channels/resolutions.
- [Offline producer](../../scripts/assets/prepare_sa_calobra_asset_comparison.py): checks SHA-256 identities and emits self-contained HTML, a six-panel PNG and an output manifest.

Review copies remain at canonical `work/2b-asset-comparison-20261005`.
Output: `work/2b-asset-board-final-20261005`. No image payload enters Git.
HTML embeds its images; network is only needed to open reference/provider links.
The temporary loopback preview server is not a product backend.

```powershell
.venv/Scripts/python.exe scripts/assets/prepare_sa_calobra_asset_comparison.py --workspace-config D:/yacs/workspace.json --output-name 2b-asset-board-final-20261005
```

Use a new output name for replay. Missing or mismatched review bytes fail before
generation. Restore copies only from recorded URLs with the same licence scope;
do not silently accept changed provider bytes. The producer does not download
or import assets.

The board switches between full source tiles and centered 2 × 2 m areas,
periodically wrapping at tile boundaries. It uses provider dimensions, not an
independent survey. Colour has no tint, exposure or contrast correction.
Aerial sectors show approximately 504 m-wide context, not grain. Dated ground
photographs remain links; Google imagery is not copied into the project.

## Recommendations for subsequent samples

| Role | First candidate / alternative | Other comparisons and reasons |
|---|---|---|
| Exposed rock | `Rock024` for closest grey colour/fracture character, **scale unknown**; `rocks_ground_06` for shallow weathered slabs | `rock_face_03`: brown/rounded; `rock_face_04`: dark slabs with baked-in leaves; legacy `rocky_terrain`: 90 m aerial surface with large slabs and green bands |
| Scree/gravel | `rocks_ground_09` for coarser fragments; `rock_ground` for finer grit | `gravel_ground_01` belongs primarily to mineral ground, not coarse scree |
| Dry mineral ground | `gravel_ground_01`; warmer alternative `gravelly_sand` | `dry_ground_rocks`: ochre earth; `dry_ground_01`: mud-crack network lacks local support |
| Sparse dry grass ground | `withered_grass` as a limited dry-fibre contribution; `grass_ground` only if greener areas are justified | Legacy `sparse_grass`: green blades/dark substrate. Withered Grass itself is too continuous for blanket coverage |
| Ground beneath trees | `dry_decay_leaves` for localized brown litter tests, conditional | Legacy `forrest_ground_03`: needles not established at the observed edge; `forest_leaves_04`: dense tangled organic detail; `forest_floor`: yellow/orange autumn leaves |
| Existing cuts/fills | CUT compares `Rock024`, `rocks_ground_06`, `rock_face_03`; FILL compares `rocks_ground_09`, `rock_ground`, `gravel_ground_01` | `excavated_soil_wall` is brown earth, not the observed grey solid-rock cut; name alone is insufficient |

Two additional inspected rejections: `dry_riverbed_rock` has parallel stepped
layers/darker brown colour; `seaside_rock` is very dark and lacks pale slab
character. All 21 review colours were visually inspected. The provider's legacy
forest ID is **`forrest_ground_03`**; the earlier single-r spelling was corrected.

The direction is pale mineral ground plus grey fragments, with dry fibres and
brown litter in limited patches. Six roles do not require six simultaneous
shader layers. No percentages or geographic boundaries are invented here.

## Scale, maps and cost evidence

Poly Haven's official API schema defines texture dimensions in millimetres;
the receipt converts them to metres. Catalogue/schema snapshots remain local.
Examples: Rock Ground 1.5 m; Rocks Ground 09, Gravel Ground 01 and Rocks Ground
06 3 m; Gravelly Sand 2.48 m; Withered Grass and Dry Decay Leaves 2 m.

**Rocky Terrain is 90 × 90 m**, corroborated by its
[provider page](https://polyhaven.com/a/rocky_terrain). At 1K, a 2 m preview
contains only about 23 source pixels; enlargement cannot add detail. The
published 8K maximum gives approximately 91 px/m at native scale. This does not
measure actual legacy Unreal tiling or performance.

ambientCG Rock024 returns zero dimensions: **unknown**, not a zero-size surface
or an implicit 2 m tile. Its full colour preview stays outside the metric
comparison and is labelled accordingly.

All 20 Poly Haven responses list Diffuse, Normal DX/GL, Roughness, AO and
Displacement. ambientCG lists Color, Normal, Roughness, AO and Displacement.
Maximum published resolution is 8K or 16K as recorded. **Only colour bytes were
downloaded and decoded**: channel availability is metadata, not verified normal
or roughness quality. No sample moves frozen geometry. Memory, mip residency,
shader cost and visual response remain Unreal/performance work; no runtime
budget PASS is inferred. All compared sources have a zero purchase price.

## Licence and review-copy acquisition

The provenance ledger recorded review-use approval before colour downloads.
Local review copies progressed to verified acquisition; **production selection
remains candidate**. A review download is not a production-set approval.

- [Poly Haven licence](https://polyhaven.com/license): asset files are CC0; website example renders are separately protected. This board uses actual Diffuse JPEGs, not copied website renders.
- [Official API](https://polyhaven.com/our-api) and [API terms](https://github.com/Poly-Haven/Public-API/blob/master/ToS.md): identified `YACS-SurfaceReview/1.0` requests and visible provider credit. No provider code copied. The review uses `/master/ToS.md`; the old Stage 3G `/main/ToS.md` link is not used or changed here.
- [ambientCG licence](https://docs.ambientcg.com/license/) covers asset files and preview renders. Rock024 uses the colour preview returned by the API, not a full production package.
- **19,340,606 bytes**: 20 Poly Haven 1K colour JPEGs plus one ambientCG colour preview. Provider bytes/MD5 were checked for Poly Haven; SHA-256 and decoded dimensions were checked for every file. Metadata hashes are retained.
- CC0 adds no mandatory redistribution notice. Voluntary provider credit and existing PNOA attribution are displayed; no new entry in `THIRD_PARTY_NOTICES.md` is required.

## Open decisions and next evidence

1. Review the conditional shortlist; do not treat the six-role library as admitted.
2. Resolve Rock024 scale with provider/source evidence or choose a better documented source. An explicit presentation-scale experiment cannot be described as measured source scale.
3. Check sparse fibre/leaf integration; continuous hay or dense autumn leaves do not match the brief.
4. Preserve independent CUT/FILL authority: the CUT-only receipt and surface colour do not establish FILL domains.
5. After source/use approval, acquire full PBR files, inspect their maps, then compare flat/steep Unreal samples and pairwise transitions at the same camera/light.

Later cliff/boulder selection (#368) must match accepted fracture scale and
palette. Scree texture does not replace rock silhouettes. No mesh placement or
model approval occurred; foliage silhouettes remain #369. Whole-Landscape
blending and #364 are not unlocked by this report.

## Validation

Ruff passes. Browser review confirmed six role sections, 26 cards, loaded
images, no horizontal overflow at the observed desktop width, both scale modes
and the enlargement dialog. These are board checks, not Unreal acceptance.
Deterministic replay produced byte-identical HTML, PNG and manifest. Existing
output/path-escape attempts and zero metric dimensions were rejected. All 21
review hashes passed; the frozen saved-map hash remains
`276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c`.
`scripts/ci/check_docs_index.py`: links PASS, i18n PASS, structure PASS and
freshness PASS. A patch initially missed a line changed by Ruff's quote
formatting; it was reapplied against the actual formatted source and checks
passed. The local preview's optional favicon request returned HTTP 404; board
images and controls loaded successfully. The existing unrelated dirty files
remain outside this delivery.

This is a scoped YACS review artifact, not a new shared engineering contract;
no Gumball promotion candidate is required.
