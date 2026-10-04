# Sa Calobra surface coverage audit — 2026-10-04

Status: **read-only evidence report; classification remains unadmitted**. Delivery
item: [#379](https://github.com/karnalooch/YetAnotherCyclingSim/issues/379).
Candidate work: [#335](https://github.com/karnalooch/YetAnotherCyclingSim/issues/335)
and draft [#362](https://github.com/karnalooch/YetAnotherCyclingSim/pull/362).

## Decision

The retained LiDAR has near-complete **spatial sampling support at a 5 m block
scale** across the current Landscape. The reported 37.5% is not evidence that
37.5% of the Landscape lacks source coverage. It combines fine-grid sampling
gaps and unresolved surface classification. No new regional acquisition or
manual painting of the entire map is justified by that percentage alone.

The surface candidate is useful for diagnosis, but it is not ready to become a
production rock/soil map. Existing samples leave 20.981% of cells unresolved;
rock and exposed-ground labels themselves remain uncalibrated candidates.
Review dark/ambiguous ground and the larger unresolved clusters before changing
classification rules. Preserve unknowns and independent hard exclusions.

This report does not admit the candidate implementation, merge #362, close #335,
or unlock #363. It changes no terrain, roads, earthworks, masks, assets, editor
state, runtime behavior or dependency. Landing evidence on main is distinct from
admitting its subject.

## Authority and inspected snapshot

[Documentation index](../README.md) identifies
[World Building Bible](../WORLD_BUILDING_BIBLE.md), section 5.3, as methodology
authority. [Product Requirements](../PRODUCT_REQUIREMENTS.md) and
[Roadmap](../ROADMAP.md) retain M3 scope and the predecessor gate. The audit covers
all 4033 × 4033 cells, 0.5 m spacing, EPSG:25831: **4,066,272.25 m²** of raster
footprint, or a 2,016.5 m square. This is the raster support extent, not a change
to the Landscape vertex extent.

The live authoring checkout was `codex/335-mask-overlay` at
`d94edf7dcb766e5b7c68e32ed32159c6147ac58e`, with pre-existing uncommitted surface
producer/test/editor-review files and a Bible addition. Those files and an
unrelated `Config/DefaultEditor.ini` edit were preserved. Candidate identity is
therefore pinned by **manifest and file hashes**, not incorrectly attributed
entirely to that commit. The documentation-only branch starts from main
`7843fa527bad7042f0c418dcf6fd8b27668935dc` and imports no candidate code.

The [measurement appendix](sa-calobra-surface-coverage-measurements-2026-10-04.md)
records manifest hashes, 64 sectors, crop coordinates and output identities.
The [replay recipe](sa-calobra-surface-coverage-replay-2026-10-04.md) preserves the
exact read-only audit source separately from production tooling. Local source
paths resolve through the canonical workspace configuration. No raw provider
files or source imagery are redistributed in this documentation change.

## What the headline percentage actually measures

| Display category | Cells | Area (m²) | Share of the entire grid |
|---|---:|---:|---:|
| Observed, unresolved surface | 3,412,576 | 853,144 | 20.981% |
| Displayed as no LiDAR observation | 2,686,788 | 671,697 | 16.519% |
| Combined display uncertainty | 6,099,364 | 1,524,841 | 37.500% |
| Light-mineral / rock candidate | 2,512,083 | 628,020.75 | 15.445% |
| Warm exposed-ground candidate | 25,112 | 6,278 | 0.154% |

These shares are **not classification accuracy**. Provider LiDAR classes describe
ground, vegetation and other objects; the retained ground class does not supply
a validated rock-versus-soil distinction. YACS adds conservative RGB rules for
that distinction. See the provider's
[classification description](https://pnoa.ign.es/pnoa-lidar/procesamiento-de-los-datos).
Provider class-quality specifications must not be presented as measured YACS
rock/soil accuracy.

The raw class-count raster has **2,713,728 empty cells (16.684%)**, slightly more
than the display's 16.519%. Mapped pavement/building/infrastructure classes
override the display in **26,940 otherwise empty cells**. This is intentional
separation of evidence sources, not additional LiDAR observations. Even pavement
has 15.327% raw empty cells despite its independently known footprint.

## Sampling gaps are mostly narrow

The accepted count raster contains 23,588,890 returns, averaging **5.801 accepted
returns/m²**. This is an observed count, not independent pulse density or a claim
about ground-only density.

| Nominal aligned block side | Blocks without any accepted return | Empty block footprint (m²) | Area supported by nonempty blocks |
|---|---:|---:|---:|
| 0.5 m | 2,713,728 | 678,432 | 83.3156% |
| 1 m | 11,645 | 11,504 | 99.7171% |
| 2 m | 530 | 1,739 | 99.9572% |
| 5 m | 7 | 175 | 99.9957% |
| 10 m | 0 | 0 | 100% |

Blocks start at the AOI upper-left. Clipped eastern/southern edge blocks are
weighted by their actual cell count. These numbers measure **any-class sampling
support**, not adequate ground sampling, surface classification, continuous
coverage inside each block or permission to fill native empty cells. Their values
also depend on block alignment; no universal coverage threshold is established.

The 50th, 90th, 95th and 99th percentiles of empty-cell distance to the nearest
observed cell center are all **0.5 m**. Only 6,878 empty cells are farther than 1 m,
1,783 farther than 2 m, and 10 farther than 5 m. The maximum is **5.657 m**.
Distance was measured in the raster plane, not along the steep terrain surface.

Four-neighbor connectivity produces 240,333 missing-data components; eight-neighbor
connectivity produces 218,968. The largest eight-connected component contains
9,418 cells (2,354.5 m²), but spans a long narrow region at the eastern edge.
Component area therefore does not imply a compact hole of the same area.
Vertical striping is visible in many crops. Scan/raster sampling is a plausible
explanation, but the audit does not re-decode LAZ or establish its root cause.

## Where classification needs attention

Of unresolved cells, **2,825,514 (82.80%) contain ground-only evidence**. The
remaining 587,062 do not satisfy that condition. Among unresolved ground-only
cells, **2,714,630 (96.08%) have mean RGB below the rock rule's 150 threshold**.
Other color-rule rejections overlap; their counts must not be added together.

This identifies a major rule limitation, not a safe new threshold. Lowering
brightness alone could also admit soil, dry vegetation or artificial surfaces.
Only 151,049 unresolved cells (4.43%) have mean RGB below 60; this arbitrary
dark-pixel diagnostic is not a shadow classifier. It would be inaccurate to
attribute every unresolved cell to deep shadow.

The largest eight-connected unresolved component is **33,421 m² (3.3421 ha)**,
within E 483336.5–483651.0, N 4408446.5–4408919.0. The component is not the full
bounding rectangle. Its center crop shows rugged, partly shaded rock-like
surfaces mixed with vegetation. This supports targeted review, not wholesale
relabeling. The next component is 5,136.5 m².

The grid was partitioned into 64 near-equal sectors, numbered north-to-south and
west-to-east. The largest unresolved shares occur in **R4C3 (38.50%)** and
**R4C2 (38.22%)**, while their raw empty-cell shares are only **4.39%** and
**3.72%**. These are classification-priority locations despite comparatively
dense sampling. R3C2, R8C1, R3C3 and R7C1 are further review targets.

## Road-adjacent findings

| Off-pavement band | Area (m²) | Unresolved surface | Displayed no LiDAR |
|---|---:|---:|---:|
| 0–10 m | 148,474.5 | 21.038% | 15.838% |
| 10–25 m | 187,196.5 | 21.348% | 16.145% |
| 25–50 m | 264,157.25 | 21.221% | 16.996% |
| 50–100 m | 448,030.5 | 20.846% | 16.866% |
| At least 100 m | 2,975,978.75 | 21.253% | 16.717% |

The near-road uncertainty is **36.877%** in the first band. It cannot be dismissed
as a distant-background-only problem. Bands use the existing conservative
`road-distance-lower-bound.tif`, excluding pavement, and are diagnostic planar
proximity bands, not exact measured offsets or new safety boundaries. The frozen
road source remains the owner-authorized `c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6`
artifact set; no builder was executed.

## Visual review and its limits

Review inspected the whole-area orthophoto/candidate overview, **16 systematic
128 m crops** (one per 4 × 4 macro-sector, with a 64 m detail inset), and **11
targeted crops**. The targeted set includes four high-density rock-candidate
locations, four exposed-ground-candidate locations separated by at least 250 m
within each class, the two largest unresolved-component bounding-box centers,
and the deepest missing-data location. Targeted selection is deliberately biased
for diagnosis; neither set is a statistical accuracy sample.

- Bright, visibly rocky outcrops in S13, S24 and the targeted rock crops align
  qualitatively with many light-mineral labels. Fine vegetation mixtures and
  unclassified strips remain. No rock precision/recall score is claimed.
- Shaded, rugged surfaces in S12, S21 and the two unresolved-component crops
  show why brightness-based rock labels are incomplete. RGB alone cannot resolve
  every shaded pixel.
- Exposed-ground candidates occur in warm open patches near buildings/trees and
  amid low vegetation. The images do not reliably separate soil from dry grass
  or gravel at every selected pixel. The 0.154% candidate share is **not** the
  true bare-soil area.
- S43 and S44 demonstrate wooded/building surroundings; the systematic set also
  includes open uplands, rocky slopes and road-adjacent terrain. Vegetation
  presence is still not planting eligibility or verified species.

Review uses the **same RGB imagery used by the candidate rules**, so it is a
consistency check, not independent validation. There are no field labels,
independent dated imagery checks, calibrated confidence, owner visual acceptance,
new Unreal captures or whole-Landscape performance measurements in this audit.

## Saved problem markers for later owner review

At the owner's request, `work/surface-coverage-audit-2026-10-04` now retains
`problem-review-map.png`, a labelled full-area map, and
`problem-overlay-native.png`, an unlabelled 4033-square registered overlay.
`problem-review-flags.tif` and `problem-review-manifest.json` preserve grid,
semantics, source identities and marker coordinates for later reopening.

- **Red:** exactly the 3,412,576 observed-but-unresolved surface cells.
- **Orange:** the 6,878 raw empty cells whose nearest observed cell center is
  farther than 1 m. This is a review-display choice, not an acceptance threshold.
- **P1–P5:** bounding rectangles of the five largest eight-connected unresolved
  components. A rectangle is a navigation aid; its entire interior is not
  labelled as a problem.
- Uncolored cells are not certified correct. Rock/soil candidates still need
  independent validation.

The owner-facing figure has a Polish legend and an 8 × 8 sector grid. The native
texture has no labels or margins, so its original georegistration is retained.
Flag raster readback and unchanged input hashes passed; the overview was visually
inspected. These files are durable **local review artifacts**, not saved Unreal
assets, remote imagery backups or changes to the live Landscape material. No
new editor consumer was implemented or applied. The owner deferred joint review.

## Recommended next bounded action

1. Keep raw 0.5 m occupancy, sampling support at an explicit coarser scale,
   candidate classes and validated confidence as separate concepts. Report them
   separately before deciding on additional acquisition. This is a recommendation,
   not an implemented new mask or authorization to interpolate labels.
2. Prepare a held-out, source-reviewed rock/soil/vegetation/unknown reference set
   across all environments and road-distance bands. Include shaded slopes and
   the identified R4C2/R4C3 clusters. Record reviewer disagreement and source dates.
3. Evaluate candidate changes against that set: confusion matrix, per-class
   precision/recall and retained-unknown share, with location-specific failures.
   Set acceptance criteria before choosing final thresholds. Do not optimize only
   the percentage of colored pixels.
4. Seek additional evidence only for unresolved questions the retained sources
   cannot answer. Keep geometry frozen. Do not assume nominal LAS capabilities
   prove a usable additional spectral band exists in the retained products.
5. Continue #335 admission separately, including its remaining canopy, road and
   earthworks contracts. Start materials only after its actual predecessor gate.

## Validation and delivery boundary

All **25 declared outputs** in the four audited manifests passed SHA-256 checks;
declared byte sizes were checked where present. The four parent-manifest hashes
referenced by the surface candidate also matched. Raster CRS, shape and transform
were checked; independently counted display classes and accepted-return totals
matched their manifests. This is bounded candidate integrity, not an audit of
every ancestor/raw source. Original LAZ decoding was not repeated.

Clipped-block arithmetic and four/eight-neighbor connectivity have explicit toy
checks. A repeated complete audit produced **10/10 byte-identical JSON/image
outputs**. The local runtime was Python 3.12.10, NumPy 2.3.5, SciPy 1.17.1,
Rasterio 1.5.2 and Pillow 12.3.0; no packages were installed. SciPy's documented
[connected-component semantics](https://github.com/scipy/scipy/blob/v1.17.1/scipy/ndimage/_measurements.py)
and [Euclidean distance transform](https://github.com/scipy/scipy/blob/v1.17.1/scipy/ndimage/_morphology.py)
define the diagnostic operations.

Independent reshape-based aggregation confirmed all five support scales;
sector and road-band partitions each covered exactly the entire grid. Explicit
nearest-neighbor calculations confirmed 201 distance samples, including the
maximum-distance cell (random sample seed 379). Versioned SciPy HTML-reference
URLs were inaccessible through the research tool; upstream source/docstrings at
the installed `v1.17.1` tag supplied the matching primary reference instead.

The report and replay documentation require documentation links, i18n, structure
and freshness checks and normal current-head CI. They require no Unreal rebuild,
editor mutation or performance job. Required PR results are recorded in #379's
delivery PR rather than represented as already passing here.

The SSOT remains accurate: unknowns remain explicit and candidate masks do not
grant production admission. Only an evidence-index entry is needed; no
architecture or acceptance threshold is revised. Gumball promotion was considered:
this is a YACS dataset-specific measurement dossier, not a reusable governance or
tooling invariant, so no platform candidate is proposed.

Attribution: Obra derivada de PNOA CC-BY 4.0 scne.es; Obra derivada de
LiDAR-PNOA-cob3 2022-2025 CC-BY 4.0 scne.es. Historical SIOSE context:
SIOSE © INSTITUTO GEOGRÁFICO NACIONAL DE ESPAÑA – SITIBSA – GOIB. Catastro inputs
remain transformed local review context; original provider responses and imagery
remain outside Git under their existing provenance restrictions.
