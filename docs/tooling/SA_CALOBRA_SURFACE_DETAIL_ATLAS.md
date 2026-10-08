# Sa Calobra surface detail atlas and PCGEx handoff plan

**Owner direction:** 2026-10-08  
**Work item:** [#445](https://github.com/karnalooch/YetAnotherCyclingSim/issues/445), [draft PR #446](https://github.com/karnalooch/YetAnotherCyclingSim/pull/446)  
**Status:** surface-detail plan with a tested Component 230 source-face pilot and native mask/visibility/bounded-patch proof, a [complete captured-survey prestudy](../experiments/sa-calobra-roadside-visibility-prestudy-20261008/README.md) and [six original-PNG proposal cards](../experiments/sa-calobra-surface-detail-review-20261008/README.md); owner review and wider physical registration remain pending
**Authority:** [World Building Bible](../WORLD_BUILDING_BIBLE.md), selected through [the documentation index](../README.md); [cliff presentation contract](SA_CALOBRA_CLIFF_EROSION_PASS.md)

## Purpose and current scope

Identify where the camera can read rock shape and where fine detail is unnecessary.
The whole existing Sa Calobra Landscape should retain coherent appearance, while
individual surfaces may require different treatment. Select locations and detail
requirements before implementing a PCG/PCGEx consumer or changing presentation.

The owner requested the five independent review tags below for PCGEx planning.
The A-D bands describe viewer demand; tags describe responsibilities and proposed
work. This task does not request performance measurement. Existing later
performance and production-admission requirements remain in force.

Use the [captured bidirectional TPP survey](../experiments/sa-calobra-tpp-survey-20261008/README.md):
1,338 frames, 669 station pairs and 185 disconnected construction windows.
These sampled views do not establish continuous traversal, camera look-around,
stopping views, all other road approaches or visibility throughout the whole area.

The accepted Component 230 v8 appearance at
`4f2cba560d54931dc8ba080370d96a7aad24f15b` remains the comparison baseline:
source-relative movement at most 50 cm, protected interfaces and original domain,
existing limestone material and 3 m physical UV scale. This local acceptance does
not classify every visible surface or authorize whole-Landscape application.

## Assign detail to physical surfaces

A review surface is a bounded, continuous part of a wall, slope or landform.
Give it a stable `surface_id` after its natural or justified treatment boundaries
are established. A camera station, road window or Landscape component is not a
surface boundary. One view may contain several surfaces; one surface may occur
in many windows and both camera directions.

A large mountain may need several reviewed regions: a close wall, a dominant
middle-distance face, a skyline and a hidden back. Split only where observed
physical boundaries or a justified treatment boundary support the split.
Record adjacent regions and preserve their visual continuity.

Assess each surface across all available views, including other approaches.
A distant image must not downgrade a surface seen nearby elsewhere. Retain the
most demanding supported requirement for each detail scale, rather than using
distance alone or averaging away an important view:

- **Outline:** skyline, major boundary and characteristic large cuts.
- **Major and intermediate forms:** planes, shelves, ledges and shape-producing
  fractures that remain readable from the camera.
- **Fine surface detail:** small cracks, pores and roughness; prefer material
  treatment when the detail does not alter a readable shape.

Use screen occupancy, readability of those forms, viewing angle and silhouette
importance as evidence. Record observed camera pose/FOV and source frames.
Screen occupancy is evidence for a particular view, not an automatic numeric
threshold. Visibility duration remains blank unless separately observed; sparse
stills cannot measure it. Unobserved approaches remain explicitly unresolved.

## Viewer-demand bands

These are review bands, not configured Unreal LOD levels, distance cutoffs,
triangle targets or measured costs.

| Band | View role | Required treatment | Candidate savings |
|---|---|---|---|
| **A - close contact** | Roadside walls, banks, bends and confirmed stopping views where shape is readable nearby | Readable corners, ledges, local planes, rock-ground contact and convincing fine surface appearance | Put pores and tiny cracks in materials when they do not change a visible shape |
| **B - dominant walls** | A cliff occupies a substantial or compositionally important part of the view, including across a valley | Characteristic outline, major fractures, shelves, broad planes and forms responsible for large shadows | Omit unsupported fine rounding and unnecessary material layers |
| **C - panorama** | Distant ridges and slopes contribute to the landscape composition | Skyline, large divisions, broad colour variation and coherent texture scale | Simplify interior geometry and omit detail the available views cannot distinguish |
| **D - confirmed occluded surfaces** | Evidence establishes the surface is hidden from the reviewed accessible cameras and approaches | Preserve any needed shadow, reflection, support or other world contribution | Minimize visual finishing only where those contributions allow it |

Coverage uncertainty is separate from the band. Leave the band unassigned when
the evidence is insufficient. A surface absent from the capture is not evidence
for D. A D candidate requires recorded reviewed access and camera coverage plus
an assessment of indirect contributions; the current sparse survey alone does
not establish all of those facts.

A distant dominant wall can demand more shape work than a small nearby rock.
Likewise, a C skyline can require careful geometry while needing no fine cracks
on the interior of the massif. Short exposure does not justify abrupt detail
changes. Future implementation must review transitions as well as static views.

## Five independent review tags

Use the exact existing tags in `review_tags`, separated by semicolons when more
than one applies. Preserve the existing template's independent
`surface_priority` values (`close_view`, `panorama`, `background`); do not
replace that column with A-D bands. Bands belong to the derived atlas record.

| Tag | Evidence or responsibility | Planned presentation consequence |
|---|---|---|
| `GEO_FIX` | An observed geometry defect requiring repair, with a specific reason and original evidence frame | Diagnose the owning surface and smallest authorized correction before finishing it; the tag alone triggers no edit |
| `SILHOUETTE_CRITICAL` | A landscape outline or characteristic large form is important to the view | Preserve the outline and major forms during any later simplification or detail operation |
| `HERO_DETAIL` | A surface needs particular quality because its shape or appearance is prominently readable | Prioritize readable forms, local edges, interfaces and appropriate surface detail |
| `BACKGROUND_LOW_PRIORITY` | Simplification may be considered after visibility and other approaches are checked | Propose reduced fine geometry or material complexity with explicit retained requirements |
| `MATERIAL_TEST_CANDIDATE` | A useful location for the first controlled material comparisons | Compare appearance using fixed geometry, camera and lighting; material suitability is separate from geometry priority |

Each annotation requires `surface_id`, `evidence_reason` and
`evidence_frame` referring to an original PNG listed in
[frames.csv](../experiments/sa-calobra-tpp-survey-20261008/frames.csv).
The [captured review guide](../experiments/sa-calobra-tpp-survey-20261008/review-guide.txt)
owns the existing annotation requirements.

### Resolve combinations explicitly

- `SILHOUETTE_CRITICAL;BACKGROUND_LOW_PRIORITY`: preserve the outline and
  large forms; consider omitting unnecessary fine interior detail.
- A supported `HERO_DETAIL` observation prevents blanket background
  simplification of the same surface. Verify identity, evidence and boundaries;
  retain both observations until the conflict is reviewed.
- `GEO_FIX;HERO_DETAIL`: diagnose and repair the authorized shape problem
  before detailing it. A geometry defect does not itself imply hero priority.
- `HERO_DETAIL;MATERIAL_TEST_CANDIDATE`: a representative close surface can
  test material scale and character while its shape is held fixed.
- `MATERIAL_TEST_CANDIDATE` alone does not raise geometry detail or record
  material acceptance.
- Diagnostic colours, a dark image region or faceting in a thumbnail do not
  establish a geometry fault or natural material class.

Neither a tag nor a band authorizes source terrain changes, material replacement,
asset persistence or production rollout. The accepted reference and existing
eligibility, exclusions and protected interfaces continue to govern changes.

## Whole-Landscape coverage outside the road strip

The [off-road appearance plan](../experiments/sa-calobra-roadside-visibility-prestudy-20261008/off-road-plan.md)
sets a coherent macro/material baseline for the entire 2,016.5 m working square,
with approximate owner-marked review sectors and two original off-road examples.
Sector outlines remain unregistered review sketches, not detail masks. Readable
remote faces can require B; separate panoramas can require C; no blanket C or D
is assigned outside a road strip. Existing Dynamic Mesh/v8 and source/material
semantics remain the basis for later mapped presentation treatment.

## Complete captured-survey prestudy

The [roadside visibility and detail prestudy](../experiments/sa-calobra-roadside-visibility-prestudy-20261008/README.md)
now screens all 56 contact sheets / 1,338 directional viewing aids / 669 paired
stations, with 24 original-PNG spot checks. Every pair has separate near-form,
image-side, B broad-face and C independent-panorama observations plus uncertainty.
The [generation guide](../experiments/sa-calobra-roadside-visibility-prestudy-20261008/generation-guide.md)
explains how these requirements feed existing Dynamic Mesh/v8 work, material
layers, reviewed masks and future bounded PCG/PCGEx selection.

This is a coarse AI prestudy, not review of every original PNG or a full-area
world visibility mask. Camera markers do not classify nearby land. D remains
unconfirmed; unknown, conflicting and unmapped surfaces receive no inferred
simplification. A B massif's own skyline is protected under B and does not alone
establish a separate C region. Source scene, geometry, materials and canonical
capture annotations remain unchanged. Street View is excluded; no performance
measurement is requested here.

## Road-observation planning map

The [detail planning map](../experiments/sa-calobra-detail-planning-map-20261008/README.md)
places all 669 paired survey stations in their 185 disconnected windows, with
six proposed card markers, anchor viewing orientations and separate A/B/C needs.
Grey observations are unassigned. Points locate road observations, not rocks;
no classified physical footprints or complete A-D area map are established.
The offline interactive map supports navigation and export of separate draft
planning notes without assigning canonical tags or PCGEx selectors.

The owner excluded Street View from this work on 2026-10-08. Previously prepared
links remain historical evidence and are not required comparisons. Current
planning uses captured original PNGs and source camera/road positions.

## First original-PNG proposal review

The [2026-10-08 proposal review](../experiments/sa-calobra-surface-detail-review-20261008/README.md)
contains six cards, twelve unchanged original PNGs and seven separate image-space
ROIs. The cards distinguish required shape from candidate omissions. Bands and
`proposed_review_tags` remain `AI_PROPOSED`; canonical tags and physical IDs are
unassigned. Paired station images are context unless correspondence is established.

Original-PNG inspection revises window 0181 from the earlier C proposal to B:
the peak's broad faces and ledges require attention as well as its skyline.
No confirmed D, geometry defect or approved background simplification is assigned.
The ROI polygons are observations, not world footprints or PCGEx selectors.

Each card includes two requested Google Street View links derived from the frozen
source mapping and capture poses. All remain `NOT_INSPECTED`: the available web
tool could not open interactive panoramas. Actual pano/date/location and visual
comparison remain unresolved. Navigation hints do not establish panorama coverage,
camera alignment or physical surface mapping.

## Provisional location shortlist

The following places were inspected through the repository JPEG viewing aids.
They are starting points for review, not established physical-surface records.
All proposed bands/tags remain pending original-PNG review, boundary definition
and cross-view correspondence. No final `GEO_FIX`, confirmed D surface or
approved background simplification is assigned here.

Stations are rounded local metres within each window, not route/physics chainage.
Original paths below are relative to `terrain-erosion-mesh/tpp-survey/` inside
the [retained evidence ZIP](../experiments/component230-cliff/evidence/retained-37800814004.zip).
The capture revision is `b1ea05b33b9f3208e7aeb6884f1a67792d9c6121`.

| Window and local station | Observed reason for review | Provisional treatment to check |
|---|---|---|
| [0103 - 34.55 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0103.md) | A tall roadside wall occupies much of both directional views | A candidate; `HERO_DETAIL;MATERIAL_TEST_CANDIDATE`; readable planes, edges and base contact |
| [0132 - 33.35 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0132.md) | The reverse view separates a close wall, intermediate rock bands and a distant ridge | Distinct A/B/C candidate regions; close wall may be `HERO_DETAIL`, ridge may be `SILHOUETTE_CRITICAL`; establish separate boundaries |
| [0168 - 30.99 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0168.md) | A close wall contrasts with a broad slope and additional road segments | `MATERIAL_TEST_CANDIDATE`; compare near-wall detail with broad Landscape material structure; other approaches may raise slope requirements |
| [0181 - 68.81 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0181.md) | An isolated rocky peak dominates the forward skyline above the bend | Originally C on thumbnails; [original-PNG card SC-P04](../experiments/sa-calobra-surface-detail-review-20261008/cards/SC-P04.md) revises to B with `SILHOUETTE_CRITICAL`; outline, broad faces and ledges matter |
| [0039 - 59.82 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0039.md) | The reverse view contains nearby ground and more distant slopes | Separate near-ground and distant regions; check material transitions and correspondence across other approaches before proposing background treatment |
| [0077 - 25.36 m](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0077.md) | The reverse view contains a distant rocky ridge against the sea | Check outline and broad form; fine detail is not justified in this view, but closer views of the same surface remain unresolved |

| Window | Forward original PNG | Reverse original PNG |
|---|---|---|
| 0103 | `frames/window-0103-forward-00002.png` | `frames/window-0103-reverse-00002.png` |
| 0132 | `frames/window-0132-forward-00002.png` | `frames/window-0132-reverse-00004.png` |
| 0168 | `frames/window-0168-forward-00002.png` | `frames/window-0168-reverse-00001.png` |
| 0181 | `frames/window-0181-forward-00004.png` | `frames/window-0181-reverse-00000.png` |
| 0039 | `frames/window-0039-forward-00003.png` | `frames/window-0039-reverse-00002.png` |
| 0077 | `frames/window-0077-forward-00002.png` | `frames/window-0077-reverse-00000.png` |

Use [accepted-hairpin window 0081](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0081.md)
at 153.87 m (`frames/window-0081-forward-00008.png` and
`frames/window-0081-reverse-00008.png`) as an additional reference for
direction-dependent views. The window name does not mean every surface visible
in it has the accepted v8 recipe or owner acceptance.

## Review deliverable

The completed atlas should contain a colour map of bounded A-D regions,
unassigned coverage where evidence is missing, and short surface cards.
It should answer both "which detail is needed here?" and "which detail can be
omitted here?" rather than marking entire hills as uniformly high or low quality.

Each card needs:

- stable `surface_id`, physical/treatment boundary and relationship to neighbours;
- registered spatial footprint or a clearly unresolved mapping, scene/source
  identity and coordinate units;
- all linked original frames, camera direction and local station;
- source-backed correspondence across windows and other reviewed approaches;
- proposed or reviewed band, independent tags, reviewer and evidence reason;
- required outline, major/intermediate forms and fine material detail;
- proposed omissions, with retained shadow/reflection/interface requirements;
- unresolved approaches, occlusion and identity conflicts, kept separate from
  the detail band;
- matched comparison views for any later proposed treatment.

JPEGs and contact sheets select places. Final annotations use the original PNGs.
Retain the original captured CSV/template and its hashes; write a separately
versioned reviewed derivative when annotations are confirmed. Do not represent
this shortlist as 669 reviewed pairs or a complete map.

## Planned PCG/PCGEx handoff

This is a proposed information contract, not an implemented schema, node graph
or mapping to plugin APIs. Native PCG remains the procedural foundation;
the pinned PCGEx extension remains a presentation executor under World Authority.

Associate reviewed metadata with physical footprints: stable surface identity,
source revision/provenance, view references, band, independent tags, required
detail scales, silhouette constraints, review status and unresolved coverage.

Where a footprint overlaps existing source-derived cliff patches, record its
explicit relationship to stable `patch_id` values from the
[cliff handoff contract](SA_CALOBRA_CLIFF_EROSION_PASS.md).
Do not equate `surface_id` with a station, component name or `patch_index`.
One reviewed surface may overlap multiple patches; a patch may need several
reviewed regions. A camera observation alone is insufficient to create a
world-space geometry selection.

A future consumer may use reviewed, spatially mapped annotations to select
presentation treatment within existing eligibility and exclusions. It must
retain silhouette constraints, protected boundaries and one visual ground owner.
Unknown, conflicting or unmapped entries receive no inferred downgrade or
geometry operation. Atlas priority cannot create new geographic eligibility,
change authoritative masks or transfer route/physics authority.

Any future graph/API implementation must verify the exact supported UE and
PCGEx versions and operation semantics under the
[API-first authoring rule](../WORLD_BUILDING_BIBLE.md#api-first-authoring-rule).
The current recorded baseline is UE 5.8.2-56702186 and PCGEx 0.79 at
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`; no new API capability is
claimed by this plan. The separate PCGEx admission failures remain recorded.
This documentation does not start #365 or later dressing implementation.

## Next review sequence

1. Confirm the six shortlist locations on original PNGs; trace surface boundaries
   and assign stable identities where evidence supports them.
2. Link each surface to its other visible appearances among the captured pairs.
   Preserve unresolved correspondence and uncaptured approaches.
3. Record required and unnecessary detail per scale, then propose bands/tags.
   Give additional views priority when they resolve a doubtful downgrade.
4. Review the colour map and cards with the owner. Keep proposals distinct from
   confirmed annotations and preserve the accepted Component 230 reference.
5. Prepare the documented spatial handoff only for reviewed mapped surfaces.
   Plan subsequent implementation under its existing work-item and proof gates.

## Validation scope

The methodology was checked against World Authority, cliff presentation,
Landscape materials and spatial quality rings in the World Building Bible.
Exact shortlist frame IDs, pair stations and source membership were checked
against the captured frame index. This documentation task does not alter
capture aids, their byte hashes, the original ZIP, selectors, geometry,
materials or runtime settings.

The repository documentation guard is
`python scripts/ci/check_docs_index.py` (links, i18n, structure and freshness).
Its result belongs to the remote documentation commit and CI run; historical
runtime/capture results retain their original revision identities.

## First executable source-surface registration pilot

The [Component 230 detail pilot](../experiments/sa-calobra-component230-detail-pilot-20261008/README.md)
now projects explicit image regions onto the immutable accepted v8 mesh. It
produces proposed A/B face groups, independent five-tag masks, protected-face
flags and an unchanged-geometry OBJ/MTL preview. The owner-only `[detail-pilot]`
workflow lane replays retained evidence on a hosted runner without Unreal or
performance measurements. This is a tested registration/selection producer;
the original replay does not prove native consumption or whole-scene occlusion.

The [bounded native continuation](../experiments/sa-calobra-component230-detail-native-20261008/README.md)
passed its `[detail-native]` proof of that exact mask in the existing v8 scene
at `520c7c98961b3a4be7fbb6eb7930e6dea8eb8b46`. Two paired-color captures
confirmed the selected patch before a 16-vertex, maximum-5.23-mm trial was
applied and fully restored. Ten original PNGs and native evidence are retained
with the experiment. This is a selected-view
experiment, not a complete visibility atlas, a PCGEx admission or owner approval
of the proposed bands. Unreviewed surfaces remain U and no D is inferred.

