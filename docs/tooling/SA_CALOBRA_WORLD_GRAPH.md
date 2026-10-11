# Sa Calobra PCG world graph — #365 kickoff

**Status:** M3, CPU input preparation; native graph and placement NOT RUN.
**Owner:** procedural-world. **Base:** `4dd792219bfc2eaf7dc216bd60cbde6628bba792`.
The [Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md)
and [World Authoring Library](../YACS_WORLD_AUTHORING_LIBRARY.md) own scope,
methodology and reusable tooling. This adapter is not a second proof framework.

## Dependency and bounded task envelope

#364 completed through squash merge [#470](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470).
[PR CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38174079043)
and [main CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38174992518)
passed. The owner [manually accepted](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470#issuecomment-6113634845)
the remaining route/latest-save gate; this does not manufacture an automated
whole-area review or latest fresh-readback PASS. #459 geometry debt is separate.

The first #365 implementation authenticates the existing World Authority masks,
pins graph-input version/seed and emits a deterministic relocatable input
manifest. Scope covers the full 2016.5 m square, not only the Golden Kilometer.
One source writer owns the adapter/config/tests; the coordinator owns docs.
Three read-only specialists audited dependency/proof, source masks and APIs.
No exclusive Unreal, build, GPU or home-runner resource is claimed.

Forbidden: changing canonical road/physics, `Base_DTM`, Landscape geometry,
BOB semantics, source masks, live Editor state or streaming; installing plugins;
inventing rock geography, species, terrain contact or placement acceptance.

## Authenticated inputs

Existing Julka profiles `sa-calobra-pcg-masks-candidate` and
`sa-calobra-mask-transitions-candidate` verified with zero issues, including
inherited source closure. Existing `verified_manifest()` also checked fingerprints,
byte hashes, logical raster hashes and grid. These results authenticate inputs,
not production placement.

| Input | Manifest SHA-256 |
|---|---|
| `pcg-masks-v1-2026-10-04/pcg-mask-manifest.json` | `465788e5d74cf3eccf59bdddc1480fa4d7dac50d6f22255ca69ac3b9f174b5df` |
| `mask-transitions-v1a-2026-10-04/transition-manifest.json` | `2cb28c018f2ed3562762d8c47976307b64397f06417c5c8efc4221bd92182950` |

Grid: EPSG:25831, 4033 × 4033 at 0.5 m; affine
`[0.5,0,483000,0,-0.5,4409516.5]`. UE origin in EPSG metres:
`[483000.25,4409516.25]`; X east, Y south, centimetres. Pixel centres map to
`col=floor(Xcm/50+0.5)`, likewise row; footprint bounds
`[-25,-25,201625,201625]` cm. No Z is inferred from a selector texture.

Reuse `scripts/assets/read_sa_calobra_pcg_masks.py::evaluate` for eligibility:
band must equal 1; reject 0/255, outside AOI and unknown clearance; full horizontal
asset radius must fit inside AOI. Subtract point-to-cell-centre distance from
the conservative clearance lower bound, then require radius + explicit clearance.
PNG alone is insufficient. Density/transition may only reduce admitted domains.

Selector bands low/medium/high overlap and describe source vegetation classes,
not species or plant positions. Preserve the exclusion bit inventory: asphalt,
0.51 m conservative shoulder, complete BOB affected rectangles, buildings,
decorative water/infrastructure holdbacks, other LiDAR classes and missing samples.
Mapped point/line holdback is 5 m, not measured channel width or safety clearance.
High rejects invalid height; low/medium class evidence does not repair height.

Transitions retain NoData. Their relative return fractions and authored fades
are not physical density or confidence. Water gap candidates remain review only.
Unknown rock/bare-soil subtype must not become rocks from yellow/RGB candidates.

## Tools and exact version audit

Installed engine `Build.version`: UE **5.8.2, CL56702186**; native PCG descriptor
Version 8 / VersionName 1.0. Installed matching headers establish graph creation
and edges (`PCGGraph.h`, `AddNodeOfType`/`AddEdge`), stock mesh-selector setup
(`PCGStaticMeshSpawner.h`) and delayed generation/cleanup (`PCGComponent.h`).
Submitting generation is not proof of completion.

Approved PCGEx revision: `39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, version
0.79 / descriptor UE 5.8.0. Retained source exists outside the live project;
its only tracked modification is `clipper.triangulation.cpp`. The reviewed
compatibility patch LF hash is
`8182824990670e560d1a1f0d052288cc8a98dc5cdb370bdbf63f2666f9593d89`.
Exact patched-source compatibility remains unverified here. PCGEx is absent
from the active review snapshot; an optional enabled entry is not installation.

The attempted [Epic 5.8 documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview?application_version=5.8)
and [PCGEx agent index](https://pcgex.gitbook.io/pcgex/llms.txt) were inaccessible
during this audit. Matching installed native headers were inspected instead.
No PCGEx-specific node is implemented or asserted as verified.

Existing Stage3G Forest/RouteExclusion graphs and generic patch candidates are
reusable API patterns. Their Alpine recipes, rectangle exclusions and counts
are not Sa Calobra source-mask, contact or production admission.

## Validation and next gates

The CPU adapter uses seed `36501` from
`worldgen/sa_calobra/world_graph_inputs_v1.json`:

```powershell
.\.venv\Scripts\python.exe scripts/assets/prepare_sa_calobra_world_graph_inputs.py --root D:/yacs/data/world-data/sa-calobra-working-v1 --config worldgen/sa_calobra/world_graph_inputs_v1.json --output Saved/PCG365/fresh-inputs
```

The output directory must be new. Two authenticated local runs produced identical
receipt SHA-256 `2028657f97977250e0ec479ec6d90bf61ee09b2fc9a1657a30fa2d51e1bc4c2b`.
Both Julka candidate profiles passed with zero issues. The input-adapter, PCG-mask,
transition and road-mask suite passed **21 tests**. These are CPU checks;
`native_execution: NOT_RUN`, `placement: false` and `qualified_assets: []`
remain explicit in the receipt.

Input adapter validation covers deterministic regeneration, source/config drift,
seed/grid/bounds rejection and unchanged exclusion/unknown semantics. Run the
existing PCG mask, transition and road-mask tests plus docs links, i18n,
structure and freshness. Keep generated receipts outside Git; record exact code
SHA and results in the PR. Use existing Gumball proof admission when native work
is ready; do not invent a separate PASS mechanism.

Next: qualify concrete asset identity/license/mesh hash and footprint; authenticate
Terrain Authority contact/Z and current road-envelope compatibility; connect the
admitted inputs to native PCG and stock spawner. Then prove deterministic
regeneration, local invalidation, override survival and saved reload/render.
All live-editor, build/GPU/runner work remains serialized under existing ownership.

Final whole-area owner audit: `PENDING_FINAL_M3`. Performance:
`DEFERRED_AFTER_M3`, `performance_pass: false`. This kickoff does not close #365,
implement later vegetation/rock stages or conceal unresolved geometry.
