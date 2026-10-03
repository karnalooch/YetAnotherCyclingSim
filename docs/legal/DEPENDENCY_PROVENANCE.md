# Third-Party Dependency and Source Provenance

**Status:** active governance policy  
**Owner:** YACS maintainer  
**Applies to:** external source code, plugins, libraries, datasets, models,
textures, audio, fonts, mocap, snippets and other imported material

## 1. Rule

Public availability is not a license.

Before third-party material is copied, vendored, adapted, imported, generated
from an external dataset, or redistributed with YACS, its provenance and license
must be verified and recorded here (or in a linked machine-readable manifest).

AI-generated output is **not** an exemption from this rule. If generated code
looks derived from, quotes, or is adapted from an external project, treat that
external project as the source and perform the same license review.

## 2. Lifecycle

Use these statuses consistently:

- **reference** — inspected for ideas only; no source copied;
- **candidate** — may be adopted later, but is not yet approved for copying;
- **approved** — license/provenance checked for the intended use;
- **acquired** — exact source/revision downloaded with provenance;
- **included** — material is committed or redistributed with YACS;
- **derived** — a committed artifact is derived from an external source or
  dataset and must retain its provenance obligations;
- **blocked** — provenance or licensing is ambiguous/incompatible.

A project marked `reference`, `candidate` or `blocked` must not be copied
into YACS.

## 3. Minimum record for a new external source

Record, before inclusion:

1. canonical upstream URL/provider;
2. exact release, tag, commit, asset ID or dataset version;
3. license name and the exact license artifact that was verified;
4. copyright/notice text that must be preserved;
5. which files or ideas are being reused;
6. whether YACS copies, modifies, links to, or only studies the source;
7. date of verification;
8. any redistribution, attribution, source-disclosure or commercial-use
   condition;
9. where the required notice is retained in YACS.

For vendored source, prefer pinning an exact upstream commit instead of
recording only a moving branch name.

## 4. Current ledger

| Source | Status | Exact source / revision | License evidence | YACS use | Verification |
|---|---|---|---|---|---|
| Embark Studios SkyHook | **candidate / reference** | `EmbarkStudios/skyhook` @ `fa8a44d51518303c0563d03b433b10145af7e51d` | upstream `LICENSE-MIT` and `LICENSE-APACHE`; dual MIT / Apache-2.0 | architecture reference for a small DCC <-> Unreal/game-engine transport and command boundary; no source vendored in YACS | exact revision and license files reviewed 2026-09-30 |
| Embark Studios UnrealClaudeFileHelper / `embark-claude-index` | **reference; copying blocked pending stronger license artifact** | `EmbarkStudios/UnrealClaudeFileHelper` @ `2c87c3b4c433ab710b64ae348d0c0c55a927a641` | `package.json` declares `MIT`, but reviewed root contains no `LICENSE`, `LICENSE.md` or `LICENSE-MIT` artifact | read-only architecture reference for fast Unreal code/asset indexing and agent search; no source copied or vendored | package metadata and missing root license artifact reviewed 2026-09-30 |
| Poly Haven Stage 3G assets / World Authoring Library | **included** | curated IDs in `scripts/assets/stage3g_polyhaven.json` plus semantic catalog/presets under `worldgen/`; exact resolved source URLs, sizes and MD5 values captured by downloader/selection plan | CC0-1.0; provider/license gate recorded in manifest and semantic catalog | selected textures/models imported as Unreal assets; #230 may use the public API for deterministic candidate discovery and bounded source caching, but discovered candidates are not auto-approved | existing reproducible asset pipeline + #230 semantic discovery layer; reviewed 2026-09-28 |
| TINITALY 1.1 | **acquired / derived input** | dataset v1.1, DOI `10.13127/tinitaly/1.1`; exact WCS request/checksum captured by downloader | CC BY 4.0 recorded by `download_passo_giau_dem.py` and generated `SOURCE_AND_LICENSE.txt` | Passo Giau macro-terrain source; raw GeoTIFF remains outside Git | existing reproducible terrain pipeline; reviewed 2026-09-28 |
| CNIG/IGN MDT50 cm — 3ª cobertura | **acquired / derived benchmark included** | v1, 2022–2025 coverage; 17 exact Mallorca COG filenames, byte sizes and SHA-256 values are pinned in `scripts/assets/prepare_sa_calobra_mdt50cm.py`; derived 8 km × 8 km output and report live under `worldgen/terrain/benchmarks/sa_calobra/` | CNIG general-use license compatible with CC BY 4.0; product page prescribes derived-work attribution `Obra derivada de MDT50cm-cob3 2022-2025 CC-BY 4.0 scne.es` | bounded Sa Calobra / Coll de Cal Reis 0.5 m terrain benchmark; source tiles remain in ignored `ExternalAssets/`, final derived GeoTIFF is stored in Git LFS; not Passo Giau authority and not an accepted production world | product/license page, source-file identities and local hashes reviewed 2026-10-01 |
| CartoCiudad Ma-2141 geometry | **acquired / source-review dataset included** | REST Geocoder road ID `604000000293`, exact response SHA-256 `6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36`, acquired 2026-10-02 | CC BY 4.0; attribution `CC BY 4.0 www.scne.es/productos.html#CartoCiudad`; official FAQ confirms service coordinates EPSG:4326 | source XY/topology review only; preserves all six multipart lines including a closed loop; no width/access/surface/Z or gameplay authority inferred | https://www.cartociudad.es/web/portal/faq and exact service response reviewed 2026-10-02 |
| IGN IGR-RT Ma-2141 3D candidate | **acquired / source-review dataset included** | OGC API Features four-feature response, selected `VIAL_TR70190001272`; exact SHA-256 `ebc7c1c985caae5b7727719856646d52824463803d13095462f8d7ef1fcd7d5f`; 2026-10-02 | CC BY 4.0, linked IGN use license; attribution `Obra derivada de IGR Redes de Transporte, consulta 2026-10-02, CC BY 4.0 scne.es` | source-property and numeric third-coordinate comparison only; vertical datum, source fictitious flag, width and bicycle access unresolved; no earthworks/physics admission | collection license link and https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf reviewed before inclusion; pinned review in benchmark |
| CNIG IGR-RT Illes Balears province package | **candidate / not acquired** | catalogue file `11655652`, `RT_ILLES_BALEARS_GPKG.ZIP`, July 2026; payload revision/hash pending | IGN general-use terms compatible with CC BY 4.0; exact downloaded package and attribution must be verified before inclusion | planned complete network inventory/comparison in #349; no package or derived geometry included | official catalogue and RoadLink collection metadata inspected 2026-10-03 |
| GOIB RT-VUIB road axes / BTIB road layers | **candidate / metadata inspection only** | road-axes catalogue updated 2026-07-07; BTIB layer 9 metadata describes 2018 cartography; exact payload/hash pending | catalogue labels Creative Commons Attribution without a precise version; separate BTIB reuse grant remains unverified | bounded query counts and raw-code summaries only in #349; no geometry copied or admitted; resolve license, epoch, schema and vertical datum before import | official catalogue, CKAN metadata and BTIB layer schema/count queries inspected 2026-10-03 |
| OpenStreetMap Sa Calobra road inventory | **derived summary included** | Overpass snapshot `2026-10-01T20:46:35Z`, clipped to WGS84 bounds `2.76258,39.80384,2.85626,39.87588`; aggregate inventory stored in `worldgen/terrain/benchmarks/sa_calobra/sa_calobra_road_inventory_2026-10-01.json` | Open Data Commons Open Database License 1.0; attribution and license link retained in the benchmark README, inventory and notices | aggregate road-class lengths and named-road planning scope only; no raw OSM geometry is committed and the summary is not route, physics, surface or access authority | source, snapshot, bounds, aggregation method and attribution reviewed 2026-10-01 |
| Strava Global Heatmap | **reference; copying and derived-data inclusion blocked** | live Global Heatmap inspected locally on 2026-10-01; no tile, screenshot, sampled intensity, ranked geometry or derivative artifact is committed | Strava Terms of Service and API Policy reserve platform/data rights, prohibit automated collection and restrict copying, derivative works and distribution | local planning reference only; it must not enter YACS source data, deterministic builds, route authority or acceptance evidence without a separate approved data agreement | official terms reviewed 2026-10-01: `https://www.strava.com/legal/terms`, `https://www.strava.com/legal/api_policy` |
| db-lyon ue-mcp | **approved / pinned development dependency** | `db-lyon/ue-mcp` tag `v1.3.9` @ `d79a34bb6e7a5883457efe8f33c9f85b1ba3e136`; npm dependency `ue-mcp@1.3.9` | upstream root `LICENSE`: MIT License; package metadata also declares MIT | local development-time Unreal orchestration only; dependency graph committed in `tools/ue-mcp/package-lock.json`; setup uses `npm ci --ignore-scripts`; deployed bridge remains gitignored; write access stays behind YACS guards/flows/proof; YACS overrides transitive `fast-uri` from upstream-resolved `3.1.6` to patched `3.1.7` because Dependency Review identified HIGH advisories in 3.1.6 | tag, exact commit, package metadata and root license reviewed 2026-09-30; security override reviewed against GHSA-58mr-gqgx-xq4g / GHSA-qw65-cvwx-89v3 |
| PCGEx / PCG Extended Toolkit | **approved pinned authoring dependency** | `PCGEx/PCGExtendedToolkit` stable branch `5.8` @ `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`; descriptor VersionName `0.79`, EngineVersion `5.8.0` | upstream root `LICENSE`: MIT License, copyright 2025 Timothé Lapetite; permits commercial use, modification and redistribution with the license notice retained | **authoring-time only** implementation of the YACS Passo Giau procedural path/corridor pipeline: canonical SP638 presentation input -> resample/smooth/offset/sampling/topology; it is not route/physics authority and is not claimed to be an Embark dependency. Source is fetched exact-SHA on the authoring runner; shipping-runtime dependency is forbidden until separately approved | stable 5.8 revision, root license and plugin descriptor reviewed 2026-09-30; bounded YACS runtime/editor proof pending |
| SideFX Houdini Indie + Houdini Engine Indie / Unreal plug-in | **reference / optional escalation** | Houdini Indie current product line | official SideFX Indie and Houdini Engine licensing pages; commercial use is subject to SideFX Indie eligibility/terms | retained as production-pipeline evidence and a possible later DCC escalation only; **not required by #287/#288** while the PCGEx-first bounded proof is active | licensing/product capability reviewed 2026-09-30; no YACS acquisition required for the current path |
| SideFX Labs / Gaea2Houdini | **reference / optional escalation** | `sideeffects/SideFXLabs` Development @ `56651134bb99f67bdc6e2423fa8a622a06d3c766` | upstream `LICENSE.md`: permissive BSD-style terms; Gaea2Houdini additionally requires an eligible Gaea installation | architecture/reference evidence only for the current PCGEx-first proof; **not required by #287/#288** | exact upstream revision/license reviewed 2026-09-30 |
| QuadSpinner Gaea Professional | **reference / optional escalation** | Gaea 2.x production line | official QuadSpinner pricing/download/EULA; edition/revenue terms apply | optional future terrain-shaping escalation only; **not required by #287/#288** and no Community/non-commercial output may enter YACS production | product/license boundary reviewed 2026-09-30 |
| RoadForge | **included** | `YuuhenR/roadforge-osm-ue5-procedural-city` @ `781cb046483cc1887e80085aacf0fb2951f4746d`; vendored by PR #219 | upstream root `LICENSE`: MIT License, copyright 2026 RoadForge Contributors; preserved at `Plugins/RoadForge/LICENSE` | minimal **editor-only** donor subset: module bootstrap + `RoadForgeMeshUtils.{h,cpp}`; descriptor adapted to UE 5.8 and module log category renamed for unity-build safety; OSM/city/editor/sample/content surfaces omitted; not a shipping runtime dependency | source revision/license/subset verified 2026-09-28; editor-only boundary reaffirmed 2026-09-30 |
| GeoTerrain | **blocked for copying / reference only** | `caonao/GeoTerrain` @ `c9ba031b77dfecfaa228f993b84685dd470bfe87` | README says “MIT”, but no root `LICENSE` file was present when checked | reference for terrain/OSM/Landscape techniques only; **do not vendor/adapt source until license grant is unambiguous** | checked 2026-09-28 |

### 4.1 Embark reference rule

Embark references are intentionally strong inputs to YACS architecture review,
but **reference strength is separate from copy permission**.

- SkyHook may be evaluated as a candidate because exact MIT/Apache-2.0 license
  files are present at the reviewed revision.
- UnrealClaudeFileHelper / `embark-claude-index` may be studied as an
  architecture reference, but YACS must not copy or adapt its source while the
  reviewed repository lacks a root license artifact, despite the MIT declaration
  in `package.json`.
- Neither entry is currently a YACS dependency.
- Public Embark code must not be described as the complete internal ARC Raiders
  toolchain without explicit supporting evidence from Embark.

## 5. RoadForge included donor

PR #219 promoted RoadForge from reference/candidate status to an **included**
minimal donor subset from exact upstream commit
`781cb046483cc1887e80085aacf0fb2951f4746d`.

Included surface:

- `Plugins/RoadForge/Source/RoadForge/Private/RoadForge.cpp`;
- `Plugins/RoadForge/Source/RoadForge/Private/RoadForgeMeshUtils.cpp`;
- `Plugins/RoadForge/Source/RoadForge/Public/RoadForge.h`;
- `Plugins/RoadForge/Source/RoadForge/Public/RoadForgeMeshUtils.h`;
- `Plugins/RoadForge/Source/RoadForge/RoadForge.Build.cs`;
- the adapted `Plugins/RoadForge/RoadForge.uplugin`;
- vendoring note `Plugins/RoadForge/README.YACS.md`;
- upstream MIT license preserved verbatim at `Plugins/RoadForge/LICENSE`.

YACS intentionally omits the upstream OSM ingestion, procedural-city
generator, PCG scatter/editor modules, sample data, screenshots, textures and
other content payloads. The retained descriptor targets UE 5.8 and the module
log category was renamed to `LogRoadForgeModule` for unity-build safety.
No retained upstream source-file copyright header was removed.

The donor remains presentation tooling only and is now explicitly **Editor-target only**. It may generate or help author persistent YACS presentation assets, but the RoadForge module itself is not part of the shipping runtime surface. Production SP638 use still requires a bounded adapter/proof and must never become route or physics truth. Any future request for runtime RoadForge execution requires a new dependency-admission decision and runtime/package proof.

## 6. GeoTerrain adoption rule

GeoTerrain is useful as a technical reference, but the checked revision has a
license ambiguity: its README labels the project “MIT” while a root license
artifact was not found.

Until that is resolved, YACS may study public documentation and independently
implement ideas that are not protected expression, but must not copy or adapt
GeoTerrain source code.

Promotion from `blocked` requires one of:

- an upstream license file or release artifact that clearly grants the intended
  rights; or
- direct written clarification from the rights holder.

Record the evidence and exact revision before any source import.

## 7. Pull-request rule

A PR that adds or materially changes third-party material must:

- update this ledger or its linked manifest;
- update `THIRD_PARTY_NOTICES.md` when redistribution/attribution applies;
- preserve license/copyright notices;
- identify generated/derived artifacts whose source data carries obligations;
- fail review when license evidence is absent, ambiguous or incompatible.

Dependency/security automation does not replace this review: a dependency can
be technically safe while still having unsuitable license terms.

## 8. Project license decision

YACS currently has no project-wide `LICENSE` file. This document does not
choose one. A future decision to publish YACS under an open-source license, a
source-available license or proprietary terms must be made explicitly by the
project owner and checked against all included third-party obligations.


## Hosted diagnostic media encoding (Issue #293)

FFmpeg/ffprobe are host build tools for derived diagnostic MP4s, not linked,
vendored or redistributed runtime dependencies. Explicit diagnostic media jobs
install Ubuntu 24.04 package `ffmpeg=7:6.1.1-3ubuntu5` from the signed distro
archive, verify its version and fail if unavailable. Source/package evidence:
https://packages.ubuntu.com/noble/ffmpeg . No binary is committed or installed
on the reference PC. Only hash-checked, fully Pillow-decoded project PNGs enter
the PNG decoder; ffprobe reads the resulting local MP4. This is not a generic
uploaded-media ingestion service. The media report records the exact
host version/build configuration from `ffmpeg -version` and `ffprobe -version`;
libx264 capability and output are checked at execution. Official reference:
https://ffmpeg.org/ffmpeg.html ; project/legal notices: https://ffmpeg.org/legal.html .
Do not infer one license for all external codec builds or bundle one without a
separate source/version/license review. Existing pinned Pillow 11.3.0 is reused
on the hosted lane. PNG evidence and a capture receipt survive missing host tools;
that condition is a media validation failure, not fabricated MP4 success.

Distro security notice USN-8329-1 documents a CAF decoder issue and an ESM
update. CAF is not accepted by this bounded PNG-to-MP4 tool path. The pin is
not a security-clean claim for arbitrary formats; expanding accepted input
requires a codec/security review and a supported updated distribution.
https://ubuntu.com/security/notices/USN-8329-1


## PNOA Ma-2141 bounded pavement review image

- Provider/product: IGN/CNIG PNOA most-recent orthophoto WMS.
- Source: https://www.ign.es/wms-inspire/pnoa-ma
- License: CC BY 4.0; https://www.ign.es/resources/licencia/Condiciones_licenciaUso_IGN.pdf
- Attribution: Obra derivada de PNOA, consulta 2026-10-02, CC BY 4.0 scne.es.
- Included image: `worldgen/terrain/benchmarks/sa_calobra/ma2141_pnoa_review_2026-10-02.jpg`.
- SHA-256: `4c896f9e64f9e86aa4005d59bd33d46f6b7619dac84cf0201180f4b79b1f20f9`.
- Exact request, CRS/bounds, pixel size and inferred edge observations are recorded
  in the adjacent `ma2141_pavement_preview_profile.json`.
- Status: admitted for bounded visual source review and an inferred contact trial;
  not admitted as survey, height, road-width, access or physics authority.
- Acquisition date and native GSD remain unknown; request date is not flight date.
  Approximate AI-interpreted edge positions have an explicit review allowance,
  not measured statistical accuracy. The generated preview is not road acceptance.
