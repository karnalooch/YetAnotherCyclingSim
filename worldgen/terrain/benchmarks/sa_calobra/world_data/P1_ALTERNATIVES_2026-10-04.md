# Verified alternative P1 acquisition — 2026-10-04

Owner authorized alternative paths after the initial WFS failures. This extends
Issue #335 / PR #359 without changing P0 CNIG files or UE assets/runtime.

## Acquired inputs

| Source | Payloads | Content and completeness |
|---|---|---|
| DG Catastro INSPIRE Buildings ATOM, 07019 Escorca | 2 feed XML + 127,448 B ZIP; 927,698 B total | ZIP CRC PASS; 4 members (3 GML feature types + metadata); 224 Building, 595 BuildingPart, 24 OtherConstruction; inspected EPSG:25831 |
| Official IDEIB regional SIOSE 2014 service | 5 JSON files; 1,236,603 B total | service/layer/license metadata + AOI object IDs + geometry; layer 1 `SIOSE 2014`, 133 fields; 15 IDs / 15 unique returned features, EPSG:25831; no transfer-limit flag/error |

The Catastro feed advertises package update `2026-08-21T00:00:00Z`. Bounding
boxes of package features intersect the working AOI for 2 buildings and 8
building parts; 0 other-construction bbox candidates. This is **not** clipping,
municipal-boundary coverage proof or proof of absence outside that municipality.
SIOSE geometries were selected by intersection, so complete features may extend
outside the AOI. The service describes SPOT5 (2014) and PNOA (2015) source imagery;
this remains the historical SIOSE 2014 product, not current land-cover truth.

## Provider and license evidence

Catastro national ATOM feed discovers the Baleares feed, which discovers the
Escorca ZIP URL; no binary URL or filename was invented. Official entrypoint:
[Catastro INSPIRE](https://www.catastro.hacienda.gob.es/webinspire/index.html).
The [Catastro license](https://www.catastro.hacienda.gob.es/webinspire/documentos/Licencia.pdf)
permits own use and transformed value-added products, but does not authorize
redistributing original supplied information. All raw bytes stay outside Git.

CNIG's SIOSE catalog attempt failed with
`Connection aborted / RemoteDisconnected('Remote end closed connection without response')`.
The official regional [SIOSE 2014 service](https://ideib.caib.es/geoserveis/rest/services/public/GOIB_SIOSE14_IB/MapServer)
provided an AOI-only alternative without a regional bulk download. Its exact
[item license](https://ideib.caib.es/geoserveis/rest/services/public/GOIB_SIOSE14_IB/MapServer/info/iteminfo)
allows publishing/download and requires attribution:

`SIOSE © INSTITUTO GEOGRÁFICO NACIONAL DE ESPAÑA - SITIBSA - GOIB`.

The prior WFS source failures remain preserved in the original receipt and
Julka profile. These alternatives resolve **source acquisition** through
explicit new identities; they do not rewrite the original endpoints as successful.

## Restore, receipts and validation

Raw root:
`D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1\p1-alternatives-2026-10-04`.

[`p1_alternatives_receipt_2026-10-04.json`](p1_alternatives_receipt_2026-10-04.json)
pins all 8 payload sizes/hashes, provider URLs, type counts and source metadata.
Julka's supplemental catalog registers those identities alongside the original
45. `explain catastro_buildings_atom` and `explain siose_2014_ideib` report the
verified alternatives; explanations of the failed WFS sources point to them.

```powershell
python scripts/assets/acquire_sa_calobra_context_alternatives.py --manifest worldgen/terrain/benchmarks/sa_calobra/world_data/working_space_sources.json --persistent-root 'D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1\p1-alternatives-2026-10-04' --receipt-out 'work\p1-alternatives-receipt.json'
python tools/julka/julka.py verify --profile sa-calobra-p1-inputs --root 'D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1'
```

Acquisition exits 0 and Julka verifies 38/38 selected files (30 BTN + 8 alternate
payloads). Restore remains local-only: preserve the relative cache paths and
verify hashes after copying. No remote backup was created. Repeat acquisition
on mutable services is a new snapshot if its bytes differ.

Current SSOT remains World Building Bible for methodology and Asset Plan for
sources/provenance. Required docs, lightweight tests and CI accompany PR #359;
no heavy Unreal proof is needed for these acquisition/catalog changes.

Still required by 2A: municipal coverage admission, normalized AOI/grid/NoData
and confidence contracts, terrain/LiDAR/land-cover/exclusion masks, accepted
road/BOB domains, deterministic regeneration, visual QA and bounded consumer proof.
