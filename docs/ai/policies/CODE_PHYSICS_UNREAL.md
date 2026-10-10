# Code, physics, Unreal and provenance

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

## Code rules

- Keep gameplay and physics logic independent from rendering.
- Physics results must not depend on frame rate.
- Use SI units internally.
- Document units in public interfaces.
- Prefer deterministic calculations.
- Avoid logic in Unreal Level Blueprints.
- Use Blueprints for presentation, configuration and rapid prototyping.
- Use C++ for stable domain logic, physics and testable systems.
- Avoid Tick when an event, timer or fixed-step system is sufficient.
- Avoid hard-coded asset paths and unexplained magic numbers.
- Store tunable values in data assets, configuration or clearly named structures.
- Keep classes and functions focused on one responsibility.
- Treat warnings as problems to investigate.
- Do not silently ignore errors.

## Physics rules

- The cycling physics core must be testable without rendering a UE level.
- Separate rider input, environment, route state and physics output.
- Use a fixed simulation step.
- Include tests for flat road, climb, descent, coasting and wind.
- Cornering outcomes must be deterministic for the same inputs.
- Crashes are outside the MVP.
- MVP cornering consequences are line widening, controlled slip, speed loss, time loss and technique score.

## Unreal Engine rules

Do not commit generated Unreal directories:

- `Binaries/`
- `DerivedDataCache/`
- `Intermediate/`
- `Saved/`
- `.vs/`

Track Unreal binary assets through Git LFS:

- `*.uasset`
- `*.umap`

Before adding an asset:

- verify its license;
- record its source;
- update `docs/legal/DEPENDENCY_PROVENANCE.md` when the source is external;
- preserve any required notice in `THIRD_PARTY_NOTICES.md`;
- check its performance cost;
- confirm that it is required by the current product milestone or an explicitly approved supporting workstream.

Target performance is 60 FPS at 1920×1080 on:

- Intel Core i5 10th generation;
- 32 GB RAM;
- NVIDIA RTX 2070 Super.

Performance must be measured, not guessed.

## Third-party provenance rules

- Publicly visible code or assets are not automatically reusable.
- Before copying, vendoring, adapting or redistributing external code, plugins,
  datasets or assets, verify the exact source revision and license.
- Record external material in `docs/legal/DEPENDENCY_PROVENANCE.md` before it
  becomes part of YACS.
- Update `THIRD_PARTY_NOTICES.md` whenever redistribution or attribution
  obligations apply.
- Do not copy from a source marked `reference`, `candidate` or `blocked`
  in the provenance ledger.
- AI-generated or AI-rewritten output does not bypass third-party license and
  provenance review.

