# Road surface materials — Issue #364 evidence

**Recorded:** 2026-10-10

**Work item:** [#364](https://github.com/karnalooch/YetAnotherCyclingSim/issues/364), in progress; [PR #470](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470) is Draft.

**Authority:** [Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md), [M3 policy](../ai/policies/M3_WORLD_OPERATIONS.md), selected through the [documentation index](../README.md).

This is a scoped evidence record, not world or material admission. #363's
[accepted material checkpoint](../tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md)
remains frozen. #384 completed after protected [PR #467](https://github.com/karnalooch/YetAnotherCyclingSim/pull/467)
merged as `88f6b95e007b61a122b6515fe29041e5e3a3f220`; its gate is satisfied.
This work continues #364, not MCP infrastructure.

## Current proof boundary

| Check | Actual status |
|---|---|
| Windows source-stage tests | 37 discovered; 35 passed, 2 Windows symlink-permission cases skipped on Python 3.12.10 |
| Asphalt source replay | Two independent 2048 × 2048 renders of the same base recipe PASS; graph and all five map bytes match |
| Read-only Unreal baseline reader | 11 candidate contract tests PASS; actual Unreal baseline execution pending |
| Unreal shader/projection/normal and material assignment | Pending |
| Road, shoulder-top and support-side ownership; full mesh geometry proof | Pending native verification |
| Saved consumer, fresh reload/render and whole-area review images | Pending |
| Owner visual status | `PENDING_FINAL_M3` |
| Performance | `DEFERRED_AFTER_M3`, `performance_pass: false` |

The source proof did not start Unreal, author material instances, assign road
slots, save a map, prove geometry or render the Unreal consumer. It does not
satisfy #364's complete definition of done. The owner audits the complete
assembled M3 world at the end, before FPS measurement; intermediate native
technical checks and inspected, retained review images continue.

## Verified source run

[Run 38045485913](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045485913)
executed at `6fa54b508019bd4a1b4aa6fad601835295ec664f` on Windows with Python
3.12.10: 37 tests discovered; 35 passed, 2 Windows symlink-permission cases
skipped (`OK (skipped=2)`). Both renders passed. The downloaded result is
`ROAD_ASPHALT_SOURCE_DETERMINISM_PASS`, with raw `source-proof.json` SHA-256
`3626bf85da28d63908feb9d820171dc03d9d6cc444c8f799f7048f7a8052f79c`
and source fingerprint
`b4d93e24d2059c74e0b8d44f23ee10632e63f44c5c932b3ee1b849e0a6868d97`.
Independent read-only checks of both downloaded bundles passed at 400 cm and
23,747,976 input bytes per bundle, with all map and graph hashes below matching.

The first canary is `aged_mountain_asphalt/base`: seed **101**, a **4 m / 400 cm**
tile, brightness **0.30**, `surface_a` **0.62**, `surface_b` **0.22**, roughness
**0.82** and normal strength **0.48**. Normals use DirectX convention. Local
detail channels remain R=cracks, G=patches, B=binder micro-variation; they do not
generate world semantics. Height remains offline evidence, not displacement.
`worn` and `repaired` are not prerequisites of this first base proof.

| Output | Matching SHA-256 from both renders |
|---|---|
| `Material.ptex` graph | `6b381516854c44dc4bdeb69b69fbb2b97ecf22c228db2c09204822d7f0bc0970` |
| BaseColor | `85b378e871d7f0c70f079a153b1d6f64c517926ee7a3fd5c7bffca50766b88e8` |
| Normal_DX | `16425658df44c1ee3cf1003182dce10415a21894afb75c0ac0506a821c7bc77c` |
| ORM | `4c10e1ac79d0dd1abb276870e39b16663581a5ebf87a53043f80450e19713069` |
| Height | `a8ba0d03e3f7fb6b2a0014689e410a92a687083f12e1ab4c16ae07703b740074` |
| DetailMasks | `766b4b41b4b9b77f2e70a4f57be4e67b7a89b7c4c6049f57cd28771950ec832b` |

The producer authenticates the existing pinned tool archives before replay:

| Input | Pin |
|---|---|
| Godot 4.7.2 Windows archive SHA-256 | `731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953` |
| Material Maker 1.7 Windows archive SHA-256 | `deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808` |
| Material Maker source commit | `4d29a815489866aae483281cf44b2cfe48d3cc3e` |
| Godot source commit | `ed1daf0bf001b61586d9930840f2f1394092c079` |

Program and graph inputs remain unchanged. The receipt explicitly retains the
16 Godot-generated UI SVG import-metadata exceptions: only modified files from
the fixed allowlist, literal-only parsing without Godot Object/Resource
constructors, and destinations confined to the imported texture cache. Their
recorded source blobs and SHA-256 values must remain identical across replay.
This does not admit arbitrary tracked source or cache changes.

The rerun split evidence into independently retrievable bundles below the
32 MiB retrieval limit; source inputs stayed unchanged. Retained ZIP identities:

| Artifact | SHA-256 |
|---|---|
| Receipt, `11666752931` | `42eb28349d221e4edcc1164cbd56cd10a91bb05dee71b6f8a2ea5001502edc47` |
| Run A, `11666718117` | `412b2dec7e6936772fdc237bad7698da04b78f7a4f08e316ac48ed3b48682b1e` |
| Run B, `11666792983` | `bae3c93744afbb63595f7fb32455c8d099ba3d584c42191e4dd2cd5f0eca7e08` |

The preceding [run 38045298256](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045298256)
at `0f1836b00915a193517b7897b019fe8853648dbc` also completed 37 discovered
Windows tests: 35 passed, 2 Windows symlink-permission cases skipped; both
renders passed. Its console pins raw receipt SHA-256
`e4f3443223997e9acbb33822b1810f7f1d2270d905d545b04c7c7a5e35503b96`;
its combined artifact exceeded the retrieval limit. The latest downloaded run
above is the primary source evidence.

## Installed material API evidence

[Declaration run 38044121552](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38044121552)
at `a592f72e5f701e761da6451315fa2ade01c7bb71` read the installed UE 5.8.2
CL 56702186 native `MaterialInstanceTools` source. It established all **17**
declarations without a truncated index; the declaration source SHA-256 is
`abad1c2401323a91e8c760c82184b3918f35581b57e8773493f47f45b1dbc573`.
This was source-only inspection, not runtime schema verification or execution
of those tools. MCP stayed stopped and `material_authoring_admitted` remained
false.

The stock setters do not establish YACS slot ownership, source conservation or
rollback guards. Generic stock material mutation is therefore not admitted.
Reuse the existing fixed [Material Forge importer](../../scripts/ue/import_material_forge_variant.py)
within the scoped policy, initially with `save_assets=False` and 400 cm
world-aligned projection; actual road-specific native proof is still required.

## Validation contract and next gates

1. Authenticate retained graph, map and provenance/validation/render/decode
   receipts with [the source checker](../../scripts/assets/road_material_contract.py).
   Its read-only contract does not independently prove two-run replay or tool
   binaries; [the replay producer](../../scripts/assets/run_road_asphalt_source_proof.py)
   supplies those separate checks. Both retained rerun bundles and the top
   receipt passed these source-stage checks; preserve their pins for handoff.
2. Run [the read-only baseline reader](../../scripts/ue/read_road_material_baseline.py)
   in a fresh isolated native session against the exact staged #363 consumer.
   Verify source/consumer conservation, actual road/support slots and native
   projection functions. Its candidate expects one road, 186 supports and 1024
   Landscape components; these counts are not new executed-baseline proof.
   The reader explicitly leaves full mesh geometry/normal/UV hashing unverified.
3. Establish actual surface ownership and the required geometry/normal/UV
   conservation before bounded base-material assignment. Prove shader,
   400 cm projection, DirectX normal, parameter readback and restoration on the
   actual road/shoulder consumer. Never replace support sides indiscriminately
   or cover unresolved CUT/contact/seam defects.
4. Inspect both travel directions, bends, shoulder/wall separation and the
   Landscape transition. Then retain actual save, fresh reload/render and
   whole-area images for the existing network and approximately 4.07 km²
   working area, with technical review and protected CI. Keep source geometry,
   physics and authority unchanged; future wetness compatibility does not
   implement weather.
5. Retain `PENDING_FINAL_M3` until the owner's final assembled-world audit and
   `performance_pass: false` until the later reference-PC benchmark actually
   passes. Neither source tests nor a protected merge can manufacture those
   admissions.
