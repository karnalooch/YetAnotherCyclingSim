# Sa Calobra material reference review — 2026-10-05

Status: **reference brief ready for visual review; no owner acceptance recorded**.
Work item: [#363](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363),
draft [#381](https://github.com/karnalooch/YetAnotherCyclingSim/pull/381).

Follow-up: the owner authorized the proposed candidate comparison. See the
[21-source surface comparison](sa-calobra-surface-candidates-2026-10-05.md)
for the next checkpoint; discovery leads below retain their earlier context.
Authority selected through [the documentation index](../README.md):
[World Building Bible](../WORLD_BUILDING_BIBLE.md),
[Roadmap](../ROADMAP.md) and [Asset Plan](../ASSET_PLAN.md).
This report is not a surface classification, asset approval or visual admission.

## Scope and source identities

The owner authorized beginning the reference plan on 2026-10-05. The current
material remains visually rejected. This checkpoint adds repeatable reference
plates and observations; it does not import assets or mutate the Unreal scene.

- Whole Landscape: 2016.5 m square, 4033 × 4033 pixels at 0.5 m, EPSG:25831.
- Extent: west 483000, south 4407500, east 485016.5, north 4409516.5 m.
- First pixel center: 483000.25, 4409516.25 m; north-up, rows advance south.
- Accepted map identity: `276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c`.
- Orthophoto: retained `mask-transition-review-v1a-2026-10-04/orthophoto.png`,
  under canonical `data/world-data/sa-calobra-working-v1`; 2024 source imagery,
  exact flight day/season unverified.
- Orthophoto SHA-256: `36eb65995ccd9ff7b8d169a208f97d2f3c6729c97053c5a5fcba4b3a6c62faa5`.
- Registration manifest SHA-256: `aed7f8324102750fd898224a3951e10507b27e6878a7c093def723b4c0a5bf14`.
- Attribution: **Obra derivada de PNOA CC-BY 4.0 scne.es**.

The producer reads only that source image and registration manifest. It does not
load the deferred red overlay, flag raster, candidate rock/soil labels or class
thresholds. Those remain in #372. Historical sampling/classification limits are
retained in the [coverage audit](sa-calobra-surface-coverage-2026-10-04.md).

## Reproducible whole-area visual index

Run from the canonical project with the existing Pillow-capable Python environment:

```powershell
.venv/Scripts/python.exe scripts/assets/prepare_sa_calobra_reference_plates.py --workspace-config D:/yacs/workspace.json --output-name 2b-reference-review-v2-20261005
```

The output name must be a new direct child of canonical `work`; existing outputs
are never overwritten. The manifest records all 16 disjoint pixel bounds, metric
bounds, source hashes, producer hash and five PNG hashes. Four row plates show
all sectors; an overview locates them. No source payload enters Git.

Sector names O11–O44 are this report's orthophoto index, **not** the deferred
red-overlay review queue. Each sector is approximately 504 m square. Every input
pixel belongs to one sector. The displayed sector is reduced to 500 × 500 pixels:
complete area coverage does not imply complete detail or ground-level coverage.

All four plates were inspected. Descriptions below are visible RGB morphology,
not measured percentages, species labels, geological analysis or calibrated
confidence. Shadow changes apparent colour and hides ground.

| Sector | Visible appearance | Remaining uncertainty |
|---|---|---|
| O11 | Winding road, pale ridges, olive/tan open patches, scattered dark crowns | Fine substrate and thin linear features |
| O12 | Strong shaded ridge; olive west, brighter fractured surfaces east | Ground in shadow; apparent colour is lighting-dependent |
| O13 | Road loop near southern edge; broad pale fractured surfaces with vegetation patches | Grain size, rock versus thin soil between fractures |
| O14 | Pale fractured mosaic and olive patches; dark diagonal depression | Substrate and vegetation identity |
| O21 | Road bend, large shadow pocket and pale broken surface southeast | Shadowed ground; rubble versus solid rock |
| O22 | Large pale ribs/slabs, narrow olive interstices, road to north | Fine transitions between ribs |
| O23 | Several road segments, more continuous olive centre/south, pale outcrops | Open-ground composition; rectangular feature not classified |
| O24 | Pale fractured surface, olive patches and diagonal dark line | Meaning of dark line; ground detail |
| O31 | Broad olive/tan patches between pale edges; thin crossing lines | Lines are not admitted trails/drainage or material boundaries |
| O32 | Open olive southern portion, pale ridges north/east, shaded western break | Soil/grass fractions and shaded ground |
| O33 | Road curves, clusters of dark crowns, pale east and olive west | Ground beneath crowns and exact transition boundaries |
| O34 | Olive corridor between pale fractured surfaces | Fine substrate in corridor and dark central line |
| O41 | Olive slope, large north/west shadow, pale eastern surface | Ground hidden in shadow |
| O42 | Pale broken surface with isolated crowns; denser cover east | Litter beneath crowns; loose versus attached fragments |
| O43 | Denser southern crowns, built/structured features, open rocky north/east | Forest-floor composition and building evidence remain independent |
| O44 | Pale/olive open north, western linear patterns, denser southern crowns | Under-canopy floor, shadow and meaning of linear patterns |

## Ground-level evidence

Three locations were inspected: two dated Google Street View panoramas and one
dated contributor panorama. Multiple headings at a location are not independent
geographic samples. Off-road interiors remain represented by aerial evidence.

### Northern roadside rock and loose material

- Provider: Google Street View, Ma-2141, panorama `ISNWmsDuk5pvjtG_JAUMtQ`.
- Location: 39.8304352 N, 2.8136241 E; provider UI date **July 2026**.
- [Source panorama](https://www.google.com/maps/@39.8304352,2.8136241,3a,90y,124.22h,90t/data=!3m7!1e1!3m5!1sISNWmsDuk5pvjtG_JAUMtQ!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D0%26panoid%3DISNWmsDuk5pvjtG_JAUMtQ%26yaw%3D124.22!7i16384!8i8192).
- Heading approximately 124°: pale exposed distant faces, olive/dark shrubs,
  dry grass tufts and loose pale roadside fragments.
- Heading approximately 152°: continuous loose fragments/fines around isolated
  dry tufts, with substantial substrate visible between tufts.
- Heading approximately 182°: grey fractured solid rock immediately beside the
  road; darker cracks and local vegetation. This is not the same structure as
  the loose foreground debris.

Road context provides qualitative scale only. No centimetre-level grain or
calibrated albedo measurement is claimed. The 2024 orthophoto and July 2026
panorama have different epochs and lighting. Imagery is consulted as reference;
Google imagery is not acquired as a production texture or copied into Git.

### Southern canopy/open-ground edge

- Provider: Google Street View, Ma-2141, panorama `LZtlHzXmAUuAuIuMN1Ympg`.
- Returned location: 39.8189973 N, 2.8151433 E; UI date **July 2026**.
- [Source panorama](https://www.google.com/maps/@39.8189973,2.8151433,3a,90y,72.17h,90t/data=!3m7!1e1!3m5!1sLZtlHzXmAUuAuIuMN1Ympg!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D0%26panoid%3DLZtlHzXmAUuAuIuMN1Ympg%26yaw%3D72.16692887612959!7i16384!8i8192).
- Heading 0°: shallow exposed fractured/slab rock with dry grass tufts on one
  side; trees and visible brown ground with scattered rocks on the other.
- Heading approximately 72°: a patchy brown litter-like layer, exposed rocks
  and stones beneath broad crowns. The visible roadside floor is not a uniform
  leaf carpet, green meadow or wet mossy floor. Individual litter species and
  the shaded interior are not resolved.

The lookup was grounded in the actual road visible in O43: approximately
E484184/N4407683, converted from EPSG:25831 to WGS84. The returned panorama
position, rather than the requested point, is the observation location.

### Nus de sa Corbata open rock and broad transitions

- Provider: contributor **Edgars Latkovskis**, hosted in Google Maps, panorama
  `CIHM0ogKEICAgICO3facswE`; UI date **June 2022**.
- Returned location: 39.8322538 N, 2.8159916 E; heading 0° in the viewer.
- [Source panorama](https://www.google.com/maps/@39.8322538,2.8159916,3a,90y,90t/data=!3m7!1e1!3m5!1sCIHM0ogKEICAgICO3facswE!2e10!6shttps:%2F%2Flh3.googleusercontent.com%2Fgpms-cs-s%2FAM4Q-U_J3BtEwiaOj8dL4DUdgciftwSTcPdHgelrvZ345TcIVgtSMpdYfHa-V2XKPsw6FZByXXW3ScVqMxwP-JTjAErdAw3wBxVpKLkSh-ZHHiJrTYOFqn0WSb7qmvypDEXsJ0y_BhGiMQ%3Dw900-h600-k-no-pi0-ya0-ro0-fo100!7i8192!8i4096).
- Pale grey exposed solid rock and fractures on both shallow foreground surfaces
  and steep faces; grass/shrub clumps grow between rock exposures. A warmer fine
  substrate appears locally between clumps. Large dark areas include shadows.
- The UI also reported no Street View at the requested point but displayed this
  contributor panorama. It is an older photographic reference, **not July 2026
  Google road coverage**. Position/direction accuracy is provider-supplied and
  independently unverified. Stone walls/bridge are not natural rock texture.

### Access and coverage limits

A first request at the Landscape centre (39.82641749, 2.81312695) returned
“To miejsce nie ma zdjęć Street View.” The verified road panorama above was the
successful alternative. This is a location-specific gap, not proof that the
Landscape lacks Street View coverage.

## Surface brief and transition evidence

| Role | Current direction | Evidence limit before approval |
|---|---|---|
| Exposed limestone | Compare pale weathered surfaces and greyer fractured near-road faces; separate shallow and steep projection | Texture must preserve fractures at believable scale; no selected geological scan yet |
| Scree/gravel | Angular loose fragments over mineral fines, continuous colour relationship with adjacent rock | Close-up grain distribution still needs comparison |
| Dry mineral ground | Restrained pale/earthy fines; substrate visible without ubiquitous grass | No isolated close-up establishing the fine-ground mix across the area |
| Sparse dry grass ground | Separate tufts and exposed substrate, subdued dry palette | One roadside observation is not a whole-area grass mask |
| Forest floor | Patchy brown litter/ground interspersed with visible rocks at the southern roadside | Species, litter identity and shaded interior remain unresolved; do not extrapolate one edge to every canopy |
| Existing cuts/fills | Compare fractured rock and loose weathered material independently | Do not infer CUT/FILL boundaries from this imagery |

Observed locally: loose material ↔ sparse dry tufts and exposed rock beside
vegetation/open ground. The orthophoto supports broad juxtaposition of pale
surfaces and olive/canopy patches, not centimetre-level blending rules. Exact
rock ↔ scree and scree ↔ mineral-fines mixtures need closer comparison. The
southern panorama adds a local canopy-floor/open-rock edge; it does not establish
all forest interiors or their exact material mixture.

The existing earthworks receipt is CUT-only. A FILL value of 0 in that receipt
means NOT_AUTHORED, not a measured fill footprint; 255 remains unknown. Current
ground imagery does not upgrade these semantics or authorize regeneration.

## Candidate discovery checkpoint

These are provider-page research leads, **not a completed three-candidate
comparison per role**. No source is newly approved, acquired or imported here.
Existing assets keep their historical lifecycle status but must compete for
Sa Calobra suitability. Provider descriptions do not replace visual sample proof.

| Role | Leads for comparison | Current concern |
|---|---|---|
| Exposed rock | Existing `rocky_terrain`; [Rocks Ground 06](https://polyhaven.com/a/rocks_ground_06) | Loose/coastal slabs may not represent local steep solid rock; third credible source missing |
| Scree/gravel | [Rock Ground](https://polyhaven.com/a/rock_ground), [Rocks Ground 09](https://polyhaven.com/a/rocks_ground_09), [Gravel Ground 01](https://polyhaven.com/a/gravel_ground_01) | Compare angularity, fines and pale-grey continuity; source colour alone is insufficient |
| Dry mineral ground | Gravel Ground 01; [Gravelly Sand](https://polyhaven.com/a/gravelly_sand); [Dry Ground Rocks](https://polyhaven.com/a/dry_ground_rocks); [Rocky Trail](https://polyhaven.com/a/rocky_trail) | Compare fines versus stones; cracked parched dirt and warm brown colour may conflict with the local reference |
| Sparse dry grass | Existing `sparse_grass` | Legacy import does not establish dry local appearance; two credible alternatives missing |
| Forest floor | Existing `forrest_ground_03`; [Forest Leaves 04](https://polyhaven.com/a/forest_leaves_04); [Dry Decay Leaves](https://polyhaven.com/a/dry_decay_leaves) | Dense autumn litter may mismatch the observed patchy rock/litter floor; species remain unverified |
| Cuts/fills | Reconsider exposed-rock and gravel leads separately | CUT and FILL do not yet each have three fit-for-role comparisons |

Verified on provider pages on 2026-10-05: Rock Ground is 1.5 m wide; Gravel
Ground 01 is 3 m wide. Both advertise CC0 and Diffuse, Normal DX/GL, Roughness,
AO and Displacement maps up to 8K. These are published source dimensions/map
availability, not verified downloaded bytes or a proposed import resolution.
Dry Ground Rocks advertises a 4 m tile; Gravelly Sand a 2.5 m tile. Their pages
list the same main channels; maximum advertised resolution is 8K and 16K
respectively. No downloaded channels have been inspected.
Forest Leaves 04 is described as dry autumn leaf/twig litter, which is a
potential mismatch rather than proof of local forest-floor suitability.
Consult the [provider licence](https://polyhaven.com/license) again with exact
chosen files at acquisition and record provenance before incorporation.

## Open evidence and next gate

1. Review the six-role visual direction against the full aerial index and the
   three ground-reference locations. Remaining gaps are off-road/under-canopy
   interiors, isolated fine-substrate close-ups, exact litter species, and
   separately admitted CUT/FILL appearance domains. These require bounded
   presentation decisions or further evidence, not invented surface labels.
2. Compare at least three credible sources per required role, at source metric
   scale with native colour, including legacy assets. Resolve the shortfalls
   above; distinguish solid rock, loose fragments and fine mineral ground.
3. Present the reference brief and complete visual shortlist for the owner's
   recorded appearance decision. Then proceed through approved → acquired →
   imported → validated and controlled Unreal sample comparisons.

The reference brief and bounded gap register are ready for owner review. The
complete visual shortlist remains subsequent work. No owner visual
acceptance, clean render/reopening, performance PASS or #364 handoff is claimed.
Houdini and new PCGEx graphs are not needed for this reference checkpoint.

## Checkpoint validation

- Python Ruff check: PASS for the new producer.
- Two independent v2 outputs: all five PNGs and the JSON manifest byte-identical.
- Coverage invariant: 16 sectors, 4033 × 4033 input pixels accounted for.
- Existing-output and parent-directory escape requests: rejected as expected.
- Source image/registration identities: checked by the producer before writing.
- Accepted map SHA-256: unchanged from the recorded identity above.
- `scripts/ci/check_docs_index.py`: links PASS, i18n PASS, structure PASS,
  freshness PASS. A semantic update marks the old material as rejected and
  removes the active fictional-Alpine route statement from the Asset Plan.
- Whole-worktree `git diff --check` reported a pre-existing new blank line at
  EOF in `Config/DefaultEditor.ini:6`; that unrelated file was preserved.
  Delivery uses a separately checked scoped diff.
- No Unreal build, asset import, scene mutation, GPU measurement or fresh-load
  proof was performed for this source-reference checkpoint.

This is YACS-specific reference evidence, not a new shared engineering contract;
no Gumball promotion candidate is required.
