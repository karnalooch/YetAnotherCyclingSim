# Window 0112: original-image review and source correspondence

Recorded: 2026-10-09. Work item: [#459](https://github.com/karnalooch/YetAnotherCyclingSim/issues/459). [Retrieval and scope](README.md).

## Executed evidence

The isolated hosted [retrieval run 37922075422](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37922075422) succeeded at commit `4ec5873ce93a746087ba1619f65ea30be13f419c`. Its six identity/rejection tests passed before copying the original files. The [small original PNG artifact 11612177784](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37922075422/artifacts/11612177784) contains eight unchanged 1280 x 720 images, original frame metadata and a provenance receipt. ZIP bytes: 7,181,085; SHA256 `c20ba7eb2cd71d7a71a20739a140eeb47140fbc07dd5d5ff85c95fd404c2caf4`.

The original TPP capture is `b1ea05b33b9f3208e7aeb6884f1a67792d9c6121` / run 37800814004. This was not a new native render, and the retrieval did not use Unreal or the self-hosted Windows runner. All eight original images were decoded, hash-checked and visually inspected after retrieval. No generated images or re-encoded substitutes were used.

## Source position proof

The images refer to frozen source window `reviewed-VIAL_TR70190001272-1-interval-24-0`, captured in the road artifact at `c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6` / run 37170332840. Reconstructing the midpoint of its 110 source cross-sections gives:

| Quantity | Independently computed value |
| --- | ---: |
| Plan-view length | 53.18931558128703 m |
| Spatial 3D length | 53.29976958609156 m |
| Plan-view pavement width | 5 m, within floating-point rounding |
| Maximum projection residual, eight captured road positions | 5.6844e-14 m |

The residual describes numerical agreement of these saved data, not real-world geographic accuracy. The survey uses the 3D distance, explaining its 53.30 m label versus the 53.19 m source plan length. Every original captured road position and 3D station matches this polyline. Other scene settings are not inferred to be identical between the two capture revisions.

| 3D station | Forward original | Reverse original |
| --- | --- | --- |
| 0 m | `window-0112-forward-00000.png` | `window-0112-reverse-00003.png` |
| 17.7665898620 m | `window-0112-forward-00001.png` | `window-0112-reverse-00002.png` |
| 35.5331797241 m | `window-0112-forward-00002.png` | `window-0112-reverse-00001.png` |
| 53.2997695861 m | `window-0112-forward-00003.png` | `window-0112-reverse-00000.png` |

Six additional local correspondence tests passed: paired poses, planar versus 3D length, wrong units/displaced camera, nonfinite input, duplicate/wrong identity and degenerate geometry. Two complete read-only audits produced identical JSON, SHA256 `409987da49cc1c815da294448e194b1543342032df8bc480c3974e7764103d4a`. Those are coordinator-local audit checks, not new full repository CI.

## Observations from original PNGs

1. A repeated tooth-shaped boundary is plainly visible at the shoulder/ground-to-uphill-cut interface, especially forward 00001/00002 and reverse 00001/00002. This is a concrete visual finishing problem across multiple views, not a diagnosis from darkness.
2. The tall uphill cut face has strongly readable faceting and vertical striping. The frozen 0.5 m heightfield, current rendering LOD, normal response and interface tessellation need discrimination before assigning a geometric root cause.
3. Asphalt has large triangular tonal regions. Images alone do not prove missing or malformed pavement triangles. Do not reverse the historical sampled-contact or width findings on that basis.

Purple/yellow surfaces are historical diagnostic presentation, not final accepted material colours. Current live scene appearance was not recaptured in this review. Recorded zero penetrations at sampled points do not prove that the visible interface is visually finished or continuously rideable.

## First bounded correction target

Start with the uphill cut-face/shoulder junction visible at the 17.77 m and 35.53 m paired stations. Retain the frozen pavement boundaries, 0.5 m shoulder contract, grade/crossfall, source heightfields, local and distant silhouette. Identify the actual rendered primitive and LOD at the visible tooth-shaped interface; then test the smallest reversible presentation-side correction with unchanged road and lighting. No blanket flattening, route shift, global LOD0, dynamic-shadow removal or decorative masking is authorized by this audit.

`GEO_FIX` remains a review proposal rather than a canonical physical-surface assignment. A/B/C/D/U and the five PCGEx tags remain independent and unchanged. No geometry repair, saved-map delivery, collision/rideability or performance acceptance is claimed.

## Delivery status

The retrieval code, tests and evidence notes are on the isolated audit branch. A tool safety check blocked creation of its Draft PR; no PR or merge is claimed and no alternative PR-creation route was attempted. Existing #338/#381/#446 were not modified. The detailed findings are also recorded in [issue comment 6079830201](https://github.com/karnalooch/YetAnotherCyclingSim/issues/459#issuecomment-6079830201).
