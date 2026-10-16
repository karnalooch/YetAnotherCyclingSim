# SideFX-to-YACS recipe record template

Copy this record into the bounded recipe's durable documentation and fill it from actual evidence. Unfilled fields mean `NOT ESTABLISHED`, never an implied PASS. [Workflow authority](README.md) · [Source concordance](catalog/README.md) · [Unreal configuration boundary](UNREAL_CONFIGURATION.md).

## Identity and scope

- Recipe ID and version:
- Approved owner task / issue, milestone, bounded output:
- Repository base SHA and changed source SHA:
- Current implementation status: `NOT STARTED / SOURCE INSPECTED / CANDIDATE / COOKED / REOPEN VERIFIED / CONSUMER VERIFIED / ADMITTED`:
- Explicitly excluded operations:
- Persistent project and output root:

## Exact source mapping

| Execution step | Catalog part ID and source URL | Caption start–end | Original HIP/HDA path and SHA-256 | Source node path/type/version | Source behavior retained |
|---|---|---|---|---|---|
| Fill from evidence | | | | | |

Do not pair a file with a lesson based only on similar names. Inspect the project or record that the material is shared at series level. If the video supplies no downloadable asset, record that absence and cite the demonstrated operation and verified official node documentation.

## Input and coordinate contract

- Dataset/provider/license, acquisition date, exact path and checksum:
- CRS, horizontal/vertical units, axis order and vertical interpretation:
- Local origin and world transform; numerical control-point evidence:
- Validity/NoData behavior, water/background boundaries and missing coverage:
- Working AOI and background extent; route/camera coverage evidence:
- Input file/HDA/texture dependency list; unresolved entries:

## Graph and parameter delta

| Actual Houdini node path | Original source node | Input connections | Original value | Adapted value | Reason and official/source evidence |
|---|---|---|---|---|---|
| Fill from the saved graph | | | | | |

List added, removed, bypassed and retained nodes explicitly. Record random seeds, erosion resets/frame range/cook settings, resolution, mask semantics and material/export attributes. Label the adapter code separately from the generator; state why every adapter is needed. Record any node-version migration and small-case verification.

## Output and regeneration contract

- Exact Houdini version/license category; Houdini Engine/Unreal version if used:
- Original assets loaded vs embedded; package/environment configuration:
- Regeneration command or reproducible UI steps; working directory:
- Cache invalidation keys and explicit cache hit/miss behavior:
- Output filenames, dimensions, voxel spacing, origin/bounds, layer names, hashes:
- Immutable source retained; source-relative displacement/delta and rollback:
- Consumer import/export settings and allowed destination; optional [Engine profile](UNREAL_CONFIGURATION.md) and effective settings readback:

## Proof and gaps

| Claim | Actual evidence path/hash | Result | Limits / next required action |
|---|---|---|---|
| Source integrity and license/dependencies | | NOT RUN | |
| Installed node/API compatibility | | NOT RUN | |
| Cook completed without relevant errors | | NOT RUN | |
| Coordinate, AOI and source-validity checks | | NOT RUN | |
| Source-relative procedural displacement | | NOT RUN | |
| Saved HIP/cache reopened in a fresh process | | NOT RUN | |
| Output inspected visually at relevant scales | | NOT RUN | |
| Unreal consumer import/save/reload, if scoped | | NOT RUN | |
| Existing technical/protected delivery gates | | NOT RUN | |
| Owner assembled-M3 visual audit | | NOT RUN | |
| Performance | | DEFERRED_AFTER_M3 | `performance_pass: false` |

For a missing step, record the official SideFX pages/examples checked, exact missing behavior and the smallest blocked operation. Preserve raw errors. No replacement algorithm is authorized merely because research found a gap.
