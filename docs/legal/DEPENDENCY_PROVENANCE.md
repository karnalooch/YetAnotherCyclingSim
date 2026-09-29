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
| Poly Haven Stage 3G assets / World Authoring Library | **included** | curated IDs in `scripts/assets/stage3g_polyhaven.json` plus semantic catalog/presets under `worldgen/`; exact resolved source URLs, sizes and MD5 values captured by downloader/selection plan | CC0-1.0; provider/license gate recorded in manifest and semantic catalog | selected textures/models imported as Unreal assets; #230 may use the public API for deterministic candidate discovery and bounded source caching, but discovered candidates are not auto-approved | existing reproducible asset pipeline + #230 semantic discovery layer; reviewed 2026-09-28 |
| TINITALY 1.1 | **acquired / derived input** | dataset v1.1, DOI `10.13127/tinitaly/1.1`; exact WCS request/checksum captured by downloader | CC BY 4.0 recorded by `download_passo_giau_dem.py` and generated `SOURCE_AND_LICENSE.txt` | Passo Giau macro-terrain source; raw GeoTIFF remains outside Git | existing reproducible terrain pipeline; reviewed 2026-09-28 |
| RoadForge | **included** | `YuuhenR/roadforge-osm-ue5-procedural-city` @ `781cb046483cc1887e80085aacf0fb2951f4746d`; vendored by PR #219 | upstream root `LICENSE`: MIT License, copyright 2026 RoadForge Contributors; preserved at `Plugins/RoadForge/LICENSE` | minimal runtime donor subset: module bootstrap + `RoadForgeMeshUtils.{h,cpp}`; descriptor adapted to UE 5.8 and module log category renamed for unity-build safety; OSM/city/editor/sample/content surfaces omitted | source revision/license/subset verified 2026-09-28; trusted UE 5.8 build + Automation proven before merge |
| GeoTerrain | **blocked for copying / reference only** | `caonao/GeoTerrain` @ `c9ba031b77dfecfaa228f993b84685dd470bfe87` | README says “MIT”, but no root `LICENSE` file was present when checked | reference for terrain/OSM/Landscape techniques only; **do not vendor/adapt source until license grant is unambiguous** | checked 2026-09-28 |

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

The donor remains presentation tooling only. Production SP638 use is separately
gated by #222 and must never become route or physics truth.

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
