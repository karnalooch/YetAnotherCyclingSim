# #365 M3 — actual Landscape natural20: post-render contact triage

**2026-10-12.** Owner accepted the rendered visual checkpoint; this is not physical-contact qualification or production placement. Exact native producer SHA `d361e7651d16ff424ae4e812c7d8cbe1fe81d662`; [native run 38278235093](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278235093) completed all three UE process boundaries with real exit 0. [Exact-head CI 38278247085](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278247085) and [Blender Material Forge 38278246147](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278246147) succeeded.

Archive: [real Landscape native GPU evidence](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278235093/artifacts/11761550579). CPU reader `scripts/assets/pcg365_natural20_contact_triage.py` verified: all 100 unique cases (20 meshes × 5 distinct positions), one clean final process exit marker, phase receipt SHA/length, unchanged Landscape map/transforms, all 40 final 1920×1080 PNGs and 40 warmups against native SHA-256 and PNG headers. The committed read-only reader can produce deterministic machine-readable JSON directly from the original native archive; this table is its rounded display summary. This is a replay of recorded evidence, not a new Unreal measurement or new physics evaluator.

## Spatial diagnosis

Existing policy requires at most **10° slope** and at most **20% of mesh height embedded**, among other gates. All 100 recorded cases were REJECTED under unchanged V1 gates. Every site fails embedding/exposed-height for all twenty assets; even point 3 (the least severe slope group) does not pass the full geometric constraints. This makes simply changing the apparent rock placement or material an inadmissible shortcut.

| Site | Ground XY (cm) | Minimum–maximum sampled slope | Smallest burial / height | V1 rejected |
|---|---|---:|---:|---:|
| 0 | [16800, 70400] | 38.20–45.64° | 111.6% | 20/20 |
| 1 | [4800, 96800] | 52.81–53.87° | 131.0% | 20/20 |
| 2 | [184800, 180800] | 35.17–43.69° | 91.5% | 20/20 |
| 3 | [181600, 189600] | 5.88–18.77° | 64.5% | 20/20 |
| 4 | [91200, 200800] | 26.46–29.92° | 59.9% | 20/20 |

The five XY anchors are **historical diagnostic selector sites**, not authenticated per-rock world-scatter mask cells. None of these values establish valid regional rock domains, unknown resolution, exclusion admission, continuous support or physical stability. An already-rendered pose may look acceptable while failing penetration/exposure policy.

## Source/geometry QA priority, not quality ranking

The table below uses the fewest recorded reasons, then least embedding and slope, solely to identify which mesh/site evidence to inspect. No row means PASS, and ranking is **not** a new placement rule. At least two failures remain on every rock/site combination.

| Rock variant | Least-failing recorded site | Failed reasons | Burial / height | Slope |
|---|---:|---:|---:|---:|
| `rock_09_01` | 3 | 3 | 77.8% | 5.88° |
| `rock_09_02` | 3 | 3 | 78.2% | 5.88° |
| `namaqualand_boulder_05_01` | 3 | 4 | 78.9% | 18.77° |
| `namaqualand_boulder_03_02` | 4 | 4 | 147.6% | 29.92° |
| `namaqualand_boulder_03_01` | 0 | 4 | 183.5% | 45.64° |
| `boulder_01_02` | 3 | 5 | 65.6% | 18.77° |
| `namaqualand_boulder_05_03` | 3 | 5 | 68.0% | 18.77° |
| `namaqualand_boulder_04_03` | 3 | 5 | 78.7% | 18.77° |
| `namaqualand_boulder_06_02` | 3 | 5 | 94.9% | 9.94° |
| `namaqualand_boulder_06_01` | 3 | 5 | 95.6% | 9.94° |
| `rock_07_01` | 3 | 5 | 97.1% | 5.88° |
| `rock_07_02` | 3 | 5 | 97.2% | 5.88° |
| `namaqualand_boulder_02_01` | 4 | 5 | 154.4% | 29.92° |
| `namaqualand_boulder_04_02` | 1 | 5 | 160.9% | 52.81° |
| `namaqualand_boulder_02_02` | 4 | 5 | 174.3% | 29.92° |
| `boulder_01_01` | 4 | 6 | 59.9% | 27.69° |
| `boulder_01_03` | 4 | 6 | 61.0% | 27.69° |
| `namaqualand_boulder_03_03` | 3 | 6 | 75.6% | 18.77° |
| `namaqualand_boulder_05_02` | 3 | 6 | 80.4% | 18.77° |
| `namaqualand_boulder_04_01` | 3 | 6 | 84.7% | 18.77° |

## Next bounded implementation order

1. **Spatial domain owner / World Authority:** establish per-rock known/unknown, road/building/water/terrain/biome exclusions and mask-valid candidate XY across the accepted 2016.5 × 2016.5 m Landscape. Retain provenance, CRS, seeds, registered raster cell identity and fail-closed NoData. Do not search arbitrary flat spots or relabel vegetation sites as admissible rock masks.
2. **Source-geometry owner / Blender:** source-preserving offline audits of natural support caps and convex-hull-versus-true-cap COM; prioritize concave Boulder01 (COM lies outside actual cap), narrow-contact Namaqualand05, two disjoint-loop families N02/Rock09, and historic positive-gap N06/Rock07. A quarter-turn must be **baked and rehashed in a derived FBX** with actor yaw=0 before native V1 eligibility; do not alter source/terrain or pretend historical N02/Q90 measurements cover the new FBX.
3. **UE proof owner:** only after identity-verified, mask-valid candidates exist, run one bounded native contact session (33/65 and convergence-only 129), including genuine Landscape owner/no-foreign-actor negative control and zero-completion-on-failure. Group independent sites in one owned process and do **not** relaunch UE just to regenerate the same rejected images. Use Forge V2 for subsequent genuinely improved low-angle visual evidence.
4. **Technical acceptance:** do not weaken <=10°/<=20%/exposure >=80%/0 sampled positive air gap/0.1 cm convergence. Preserve rejected outcomes, saved packages and exact process SHA. Owner visual acceptance of these renders is recorded separately; per-asset contact policy, native current-head proof and final whole-M3 audit remain unresolved.

**Boundaries:** `qualified_assets: []`, `placement: false`, `full_qualification: false`, `performance_pass: false`, `DEFERRED_AFTER_M3`. No accepted Landscape/`Base_DTM`/road/physics/CRS edits, no scatter, no runner cleanup #475, no release or merge.
