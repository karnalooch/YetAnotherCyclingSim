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
| Poly Haven Stage 3G assets | **included** | asset IDs in `scripts/assets/stage3g_polyhaven.json`; exact resolved URLs/checksums captured by downloader | manifest records CC0-1.0 and Poly Haven license page | selected textures/models imported as Unreal assets | existing reproducible asset pipeline; reviewed 2026-09-28 |
| TINITALY 1.1 | **acquired / derived input** | dataset v1.1, DOI `10.13127/tinitaly/1.1`; exact WCS request/checksum captured by downloader | CC BY 4.0 recorded by `download_passo_giau_dem.py` and generated `SOURCE_AND_LICENSE.txt` | Passo Giau macro-terrain source; raw GeoTIFF remains outside Git | existing reproducible terrain pipeline; reviewed 2026-09-28 |
| RoadForge | **candidate / reference** | `YuuhenR/roadforge-osm-ue5-procedural-city` @ `781cb046483cc1887e80085aacf0fb2951f4746d` | root `LICENSE`: MIT License, copyright 2026 RoadForge Contributors | architecture/implementation reference for procedural road geometry; **no code recorded as copied yet** | license file verified 2026-09-28 |
| GeoTerrain | **blocked for copying / reference only** | `caonao/GeoTerrain` @ `c9ba031b77dfecfaa228f993b84685dd470bfe87` | README says “MIT”, but no root `LICENSE` file was present when checked | reference for terrain/OSM/Landscape techniques only; **do not vendor/adapt source until license grant is unambiguous** | checked 2026-09-28 |

## 5. RoadForge adoption rule

RoadForge may be used as a source candidate because its verified revision
contains an MIT license. Before copying any substantial portion:

- record the exact files and upstream commit used;
- retain the upstream copyright and MIT permission notice in a local notice or
  vendored license file;
- describe material YACS modifications;
- update `THIRD_PARTY_NOTICES.md`;
- review whether any RoadForge subcomponent has its own third-party terms.

Studying an algorithm/API shape without copying source still remains
`reference` use and should not be misrepresented as vendoring.

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
