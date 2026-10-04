# Working-space P1 acquisition — 2026-10-04

Issue #335 remains open. This is source acquisition and byte-integrity evidence,
not normalized masks, World Authority admission or a consumer proof.

## Results

| Source | Status | Files and payload bytes | Types/layers and features |
|---|---|---|---|
| BTN vector context | acquired | 30 PBF, 250,386 B | 21 distinct layer names; 2,382 tile feature fragments (may repeat across tile edges) |
| SIOSE 2014 WFS | partial / rejected edition | 1 capabilities XML + 1 diagnostic GML, 1,434,573 B | 4 advertised types; requested `lcv:LandCoverUnit`; 244/244 returned, **0 admitted** |
| Catastro Buildings | partial / provider exception | 1 capabilities XML + 12 exception GML, 19,782 B | `bu:Building`, `bu:BuildingPart`, `bu:OtherConstruction`; **0 admitted**; actual feature count unknown |

Counts exclude local JSON extract/tiles manifests and earlier probe files.
All 45 payload identities and hashes are registered in Julka's supplemental
[`p1_context.json`](../../../../../tools/julka/data/p1_context.json).
The portable, hash-bearing
[`p1_context_receipt_2026-10-04.json`](p1_context_receipt_2026-10-04.json)
records source results, requests, rejected payloads, earlier failures and the
protected CNIG verification. The 17 CNIG files were read-only rehashed:
17/17 match the original receipt, totaling 3,339,596,438 B. No P0 download or
modification was performed; the original receipt is unchanged.

## Exact failures and verified adjustments

- BTN's previous z17 request returned HTTP 404 after four attempts at
  `https://vt-btn.idee.es/1.0.0/btn/tile/17/49699/66555.pbf`.
  The [official IGN style index](https://www.ign.es/web/estilos-de-los-servicios-de-teselas-vectoriales)
  points to `BTN_Completa.json`. Its `BTN_Vtiles` source has standard
  `maxzoom=16`, alongside legacy `maxZoom=14`. The run used the documented
  standard z16 and verified all 30 MVT layer inventories. This is service
  context, not a thematic GeoPackage acquisition or a native survey-accuracy claim.
- SIOSE's first capabilities retry timed out at 30 s. A subsequent response
  and metric EPSG:25831 query completed. Completeness was 244 matched / 244
  returned / 244 members, but capabilities declare **SIOSE HR 2017**, not 2014.
  The payload has `observationDate=2016-01-01T00:00:00` and
  `namespace=ES.SCNE.CLC`. These identities are preserved without interpreting
  them as the requested 2014 product. The edition guard rejects the source;
  no guessed typename, replacement edition or geographic axis swap is admitted.
- Catastro returned HTTP 200 with `OperationProcessingFailed` and exact text
  `Area of extension out of limits` for all four ~1.0166 km² quadrants and all
  three advertised types. The [official WFS specification](https://www.catastro.hacienda.gob.es/webinspire/documentos/inspire-bu-wfs.pdf)
  documents a 4 km² / 5,000-element limit and the metric BBOX query syntax.
  A separately recorded lowercase request following its example, with
  `srsname=EPSG::25831` and no CRS suffix in BBOX, returned the same 300-byte
  exception. Root cause remains provider/query behavior unconfirmed. No
  unproven coordinate swap, smaller-area workaround or empty-coverage claim is used.

The selected P1 acquisition exits **2** while any source is partial/failed.
The SIOSE and Catastro errors are source-acquisition blockers, not failed UE
builds. Pipeline regression tests may pass while source readiness stays incomplete.

## Cache, Julka and restoration

Actual Windows cache:
`D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1\p1-2026-10-04`.
Existing root-level SIOSE/Catastro probes and all `manual-cnig` files are retained.
Raw PBF/GML/XML stay outside Git. Only receipts, manifests, catalog and docs
are committed. No remote copy of this P1 snapshot has been registered.

Use the parent working-v1 cache as Julka's explicit root:

```powershell
python tools/julka/julka.py explain btn_vector_context
python tools/julka/julka.py explain siose_2014_wfs
python tools/julka/julka.py explain catastro_buildings_wfs
python tools/julka/julka.py verify --profile sa-calobra-btn-context --root 'D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1'
python tools/julka/julka.py status --verify --profile sa-calobra-p1-context --root 'D:\actions-runner-yacs\_work\YetAnotherCyclingSim\_yacs-world-data\sa-calobra-working-v1'
```

BTN byte verification passes. All 45 registered files have matching size/SHA-256,
but the complete P1 profile returns nonzero because two sources are unadmitted.
`plan` reports missing local files as requiring local restore; `hydrate` checks
the local identities and never claims a remote backup. Restore by copying the
retained relative paths into the selected cache root, then verify. Reacquiring
mutable provider services is a new snapshot and may not reproduce the pinned hashes.

## Remaining 2A work

Obtain a confirmed SIOSE **2014** WFS identity or explicitly resolve the provider
edition mismatch; resolve Catastro's bounded query failure before admitting its
geometry. Then normalize the admitted sources to the AOI, choose the common
grid/NoData/confidence contract, generate terrain/LiDAR/land-cover/exclusion
layers, integrate accepted YACS road/BOB domains, prove regeneration and visual
QA, and demonstrate bounded Landscape-material/PCGEx ingestion. Expansion to
8×8 km remains gated by that working-space proof.

## Local validation

Ten lightweight service-evidence tests and 18 Julka tests pass, including P1-only
producer isolation, wrong edition, HTTP-200 exceptions, partial/unknown counts,
MVT framing, and missing-local-restore rejection. The final architecture/tooling
contract and source planner pass. Documentation links, i18n, structure and
freshness all pass via `python scripts/ci/check_docs_index.py`.
The SSOT remains World Building Bible for methodology and Asset Plan for
source/provenance; the asset ledger, Julka docs and provenance notices were
updated together. No Unreal assets/runtime were changed or heavy build invoked.
