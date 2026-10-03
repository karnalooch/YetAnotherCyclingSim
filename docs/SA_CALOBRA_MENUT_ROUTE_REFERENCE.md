# Sa Calobra → Menut / Binifaldó — route reference dossier

**Status:** evidence / visual reference, not route-physics authority  
**Owner direction:** 2026-10-02  
**Applies to:** candidate first complete 1:1 YACS route and world reconstruction  
**Authoritative methodology:** [WORLD_BUILDING_BIBLE.md](WORLD_BUILDING_BIBLE.md)  
**Product scope authority:** [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md)

This dossier captures the current reference direction for a complete real-world ride that starts at the sea in Sa Calobra and continues through the Serra de Tramuntana toward the public forests of Menut and Binifaldó.

It is intentionally a **reference dossier**, not a declaration that every metre is already admitted for riding. Canonical route geometry, chainage, access, surface, Road Physics Profile and world-source coverage still require explicit verification.

## 1. Route concept

The candidate corridor is:

`Port de Sa Calobra → Ma-2141 → Coll dels Reis → Ma-10 → Menut → Binifaldó → Coll des Pedregaret`

The design goal is not to compose several fictional biomes. The attraction is that the real road already crosses a strong sequence of real landscapes:

1. Mediterranean sea and the enclosed Sa Calobra valley;
2. exposed limestone and the engineered Ma-2141 hairpins;
3. Coll dels Reis and high Serra de Tramuntana mountain terrain;
4. the Ma-10 transition toward a greener interior;
5. increasingly wooded terrain around Lluc / Menut;
6. the paved forest road through Menut and Binifaldó;
7. Coll des Pedregaret, where the confirmed asphalt ends.

The current working estimate for the complete sea-to-forest asphalt corridor is **roughly 29–30 km**. This is a planning estimate only. Final route length must come from one admitted canonical polyline with exact chainage; do not use this estimate as a Road Physics Profile distance.

### Evidence for the road sequence

- Consell de Mallorca / Mallorca Tourism identifies the real cycling route through Ma-10, Lluc, Coll dels Reis and Ma-2141 to Sa Calobra: https://fundaciomallorcaturisme.net/rutas/cicloturismo/serra-de-tramuntana-nord/
- Mallorca Cycling Center describes the Sa Calobra road as a 9.4 km climb from the sea, with 26 hairpins and the Nus de sa Corbata, and places the Ma-10 junction about 2.4 km from Coll dels Reis in the opposite direction: https://www.mallorcacyclingcenter.com/routes/alcudia-sa-calobra/
- IBANAT confirms that the access to Cases de Binifaldó passes through Menut on an **asphalted Camí de Menut** which continues to Coll des Pedregaret; the described access is approximately 3.5 km: https://caib.es/sites/ibanat/ca/cases_de_binifaldo/
- The current Menut/Binifaldó management document describes the internal Menut–Binifaldó road as public, asphalted, in good condition and about 3 km inside the public estate: https://www.caib.es/sacmicrofront/archivopub.do?ctrl=MCRST34ZI79608&id=79608
- A CAIB route description explicitly says the paved road runs among holm oaks and limestone formations and that asphalt ends at Coll des Pedregaret: https://www.caib.es/sites/espaisnaturalsprotegits/f/488026

Exact bicycle-access semantics for every candidate segment remain an admission task. The presence of asphalt is not by itself permission to activate a segment for riding.

## 2. Geographic-fidelity intent

This route is a reference because it stresses the full YACS 1:1 contract in one continuous real place.

At a given real-world chainage, YACS should reproduce the same durable spatial facts within admitted source accuracy: the same road position and distance, mountain/ridge geometry, valleys and major rock cuts, forest boundaries/open areas, buildings/walls/infrastructure where sources support them, and the same relationship between road, slope, cliffs and vegetation.

The route must not be shortened to fit an MVP duration. If product scope later uses only a shorter section, that section is a crop of the real route, not a compressed version of it.

## 3. Visual identity: what makes this route feel like itself

The reference identity is the **transition**, not one repeated biome.

### Sa Calobra / Ma-2141

Dominant visual cues: pale/warm limestone faces, sparse Mediterranean scrub and exposed rock, tight road engineering and retaining structures, strong sea/rock/asphalt contrast, hard sun and shadows, and abrupt transitions between cut rock, guardrail, shoulder and drop.

Useful visual references:

- Coll dels Reis / Sa Calobra hairpins: https://www.outdooractive.com/de/route/rennrad/mallorca/coll-dels-reis-726-m-von-sa-calobra/804462078/
- Sa Calobra cycling corridor: https://www.mallorcacyclingcenter.com/routes/alcudia-sa-calobra/
- Current YACS Street View review point and source notes remain in [WORLD_BUILDING_BIBLE.md](WORLD_BUILDING_BIBLE.md).

### Ma-10 transition

The high-road transition should not jump from bare rock to a generated wall of trees. Source data should reveal gradual changes in canopy density, roadside walls, rock exposure, drainage, clearings and forest edge.

Useful public visual reference for the shaded Ma-10 character: https://www.komoot.com/highlight/425608

### Menut / Binifaldó

IBANAT states that **holm-oak woodland (alzinar / encinar)** is the predominant vegetation in Binifaldó, associated with relatively abundant local water. Official descriptions also identify dry-stone walls, lime kilns, charcoal structures and huts as characteristic cultural elements of the forest estate.

Official references:

- Cases de Binifaldó, access and photographs: https://caib.es/sites/ibanat/ca/cases_de_binifaldo/
- Coma de Binifaldó, vegetation and forest heritage: https://caib.es/sites/ibanat/ca/coma_de_binifaldo/
- Finca pública de Menut: https://www.caib.es/sites/espaisnaturalsprotegits/es/finca_pablica_de_menut
- Balearic Forest Centre at Menut: https://www.caib.es/sites/xarxaforestal/es/informacion-19072/

The destination should therefore not read as a generic conifer forest. The reference mix is a Mediterranean mountain woodland with holm oak as an important/predominant local element, pines where supported by data, limestone rock, shaded understory and dry-stone cultural features.

## 4. Serra de Tramuntana cultural layer

UNESCO describes Serra de Tramuntana as a Mediterranean cultural landscape formed by steep mountain terrain together with terraces, olive groves, dry-stone structures, roads and water-management systems.

Reference: https://whc.unesco.org/en/list/1371

This matters to YACS because dry-stone walls, terraces, old paths and water infrastructure are not decorative "Mediterranean clutter". Where mapped or measurable, they are part of the real landscape and belong to World Authority.

## 5. Source data still required for the complete corridor

The present 8 km × 8 km Sa Calobra MDT50cm benchmark covers only the first working
region. Extending to Menut/Binifaldó requires source coverage for the real corridor,
not a manually generated transition. Issue #335 establishes the bounded **World Data
Stack v1** acquisition contract for the next presentation phase.

### 5.1 Immediate acquisition priority for the Golden Hairpin

| Priority | Data | Role | Admission rule |
|---|---|---|---|
| P0 | **PNOA LiDAR 3rd coverage — Illes Balears NPC03** | vegetation/canopy, building/object-height and ground-class cross-check evidence | Illes Balears NPC03 publication was announced 2026-08-18; acquire only the 1 × 1 km LAZ tiles intersecting the bounded AOI plus controlled margin; record exact filenames, classification level, date, CRS/vertical reference and SHA-256 |
| P0 | **PNOA Máxima Actualidad orthophoto — 2024 Baleares** | dated visible-surface evidence for forest/open ground/rock/bare soil and independent road-edge review | acquire exact COG/MTN25 source covering the AOI; record native product GSD and never confuse request/export pixel spacing with source accuracy |
| P1 | **BTN thematic GeoPackages** | hydrology, nature/landscape, buildings/constructions and transport context | clip only relevant thematic layers to the AOI; use as semantic/context evidence, not automatic centimeter-precision authority |
| P2 | **SIOSE** | coarse historical land-cover cross-check | classic CNIG SIOSE editions are 2005/2009/2011/2014; do not treat them as current vegetation truth when LiDAR/orthophoto disagree |
| existing | **MDT50cm / admitted DTM** | macro ground geometry | keep accepted `Base_DTM`; World Data Stack does not replace ground authority |
| existing | **CartoCiudad + IGR-RT** | road geometry/attribute source review | preserve current road-authority boundaries |
| later | **Catastro INSPIRE buildings** | footprint authority | admit exact source separately before building generation |
| qualitative | **dated ground photography / Street View where accessible** | roadside interpretation | visual evidence only unless measured independently |

Current official product references:

- PNOA LiDAR 3rd coverage product: https://centrodedescargas.cnig.es/CentroDescargas/lidar-tercera-cobertura
- PNOA LiDAR 3rd-coverage specifications: https://pnoa.ign.es/pnoa-lidar/especificaciones-tecnicas
- CNIG LiDAR publication notices (including Illes Balears NPC03): https://centrodedescargas.cnig.es/CentroDescargas/novedades?codSerie=LIDA3
- PNOA Máxima Actualidad catalogue: https://centrodedescargas.cnig.es/CentroDescargas/catalogo.do?Serie=PNOAH
- BTN thematic catalogue: https://centrodedescargas.cnig.es/CentroDescargas/btn
- SIOSE catalogue: https://centrodedescargas.cnig.es/CentroDescargas/siose
- IGN/CNIG geographic-data license: https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf

PNOA third-coverage specifications state a minimum density of 5 points/m², 1 × 1 km
files, estimated planimetric precision <=25 cm and orthometric heights. CNIG's
2026-08-18 notice records the Illes Balears update at NPC03. These are regional/product
facts only: no tile becomes YACS evidence until its exact identity, hash and local
coverage have been verified.

### 5.2 First derived products

For the bounded Golden Hairpin AOI, the first deterministic outputs should be:

- DTM-derived slope, aspect, curvature/roughness and local-relief rasters;
- LiDAR-derived canopy height/density and class occupancy, preserving source classes
  and unknown/unclassified state;
- orthophoto-assisted visible-surface masks for vegetation/open ground/rock/bare
  soil with confidence rather than forced classification;
- water/building/infrastructure occupancy or exclusion masks where the admitted
  source supports them;
- road-distance/protected-corridor plus BOB CUT/FILL/inner-edge/outer-edge channels
  imported as separate YACS-owned evidence.

The World Data Stack must not bake presentation decisions into source truth. PCGEx
and Landscape materials consume these outputs; they do not query raw providers
directly and they do not promote a visual classification to route/physics authority.

### 5.3 Download boundary

The pipeline should download source tiles based on the **Golden Hairpin AOI plus a
controlled context margin**, not because an arbitrary Unreal Landscape square or
the whole island happens to exist. The full ~29–30 km route expands only after one
bounded source edit proves deterministic producer -> derived-data -> consumer
regeneration.

## 6. Reference photographs: copyright boundary

Internet photographs in this dossier are **reference-only unless their exact license and reuse permission are recorded in the provenance ledger**.

Do not copy Outdooractive, Komoot, Wikiloc, Getty/iStock or other third-party photographs into game assets or the repository merely because they are visible online. Link to the source page for human visual review.

Official source photography can still have separate image rights. Dataset license and webpage/image copyright must be reviewed independently.

The correct workflow is:

`photo / Street View / official page → visual observation → documented trait`

not:

`photo → copied texture / copied mesh`.

## 7. Asset candidates for visual prototyping

These are **REFERENCE_ONLY / CANDIDATE** until exact license, performance, format and provenance are reviewed. They are not geographic authority and must never decide where vegetation or rocks exist.

| Candidate | Why it is interesting | Admission note |
|---|---|---|
| Quixel Megaplants: Aleppo Pine | exact Mediterranean species candidate; procedural variations; Unreal/Nanite-oriented | Free listing, but PVE/Nanite foliage workflow is marked Experimental; license and shipping risk must be reviewed |
| Fab: Quercus ilex — Holm oak | exact species candidate for the dominant Binifaldó woodland | third-party asset; license, UE performance and visual fidelity require review |
| Quixel Megascans Quarry Cliff | high-fidelity limestone cliff/rock forms | useful material/shape reference only; scan geology is not proof of Mallorca geology at a specific coordinate |
| Quixel Megascans Stone Wall | stone surface/material reference | generic wall scan; cannot replace measured Mallorcan dry-stone wall geometry |

Candidate links:

- Aleppo Pine: https://www.fab.com/listings/a441387b-c3e0-4982-82c4-5f661ccca6dd
- Quercus ilex / Holm oak: https://www.fab.com/listings/fd64a92e-9f11-4bbe-b86e-ee36b10bdcb3
- Quarry Cliff: https://www.fab.com/listings/c88f7f3b-bb08-4e38-8ee5-67e120e99ae1
- Stone Wall: https://www.fab.com/listings/d1aa68e6-b404-4f7f-babb-a84fdd2f860d

Before importing any candidate, follow `AGENTS.md`, `ASSET_PLAN.md`, `docs/legal/DEPENDENCY_PROVENANCE.md` and `THIRD_PARTY_NOTICES.md`.

## 8. What PCG is allowed to do on this route

PCG is a reconstruction executor. It may instantiate appropriate tree/rock/ground-cover assets at positions constrained by verified/derived spatial evidence, choose an asset variant inside confidence bounds, generate small non-geographic detail while respecting exclusion masks, and rebuild deterministic bounded areas when source data changes.

It may not move a forest boundary, invent a grove, relocate a building, change road length or create a mountain because the composition looks better.

## 9. Reference acceptance before this becomes the canonical first route

Before this candidate can become the canonical first complete route, prove:

1. one authoritative route polyline from sea start to paved end;
2. exact 1:1 chainage and elevation profile;
3. road-surface and bicycle-access state per segment;
4. complete DTM/LiDAR/orthophoto coverage with provenance and dates;
5. forest/land-cover reconstruction from source data rather than manual biome painting;
6. building/infrastructure coverage expectations;
7. deterministic multi-window regeneration without geographic seams;
8. rider-camera visual comparison at representative sea, hairpin, high-mountain, transition and forest checkpoints;
9. 1080p/60 performance evidence on the YACS reference PC.

Until those gates pass, this document defines the **reference vision and evidence target**, not a claim that the 29–30 km route is implemented or playable.
