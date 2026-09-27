# CI Validation Tiers

YACS uses staged validation so world/art iteration stays fast without weakening the merge gate.

## Tier 0 — static / lightweight on every PR update

Runs for draft and ready PRs as applicable:

- change classification;
- repository and governance policy;
- Python/C++ security lanes when their paths change;
- code-only Unreal build for UE C++/tooling changes;
- lightweight asset/LFS-pointer validation for asset changes.

Draft PRs are the normal iteration mode for world-building work.

## Tier 1 — heavy Stage 3G proof at merge-candidate readiness

The full Stage 3G self-hosted proof is required only when both conditions are true:

1. the PR contains a path classified as `asset_full`; and
2. the PR is not a draft.

Transitioning a draft to **Ready for review** explicitly triggers CI, so the exact current head receives the full proof even when no new commit is pushed. Any later push to a non-draft PR re-runs the proof for the new exact head.

For `main` pushes, `asset_full` changes continue to run the full proof.

This means vegetation, material, water, lighting and other world-art iteration can be accumulated in a draft PR without paying for a full LFS checkout, authoring pass and three-point Stage 3G proof after every small commit.

## Tier 2 — visual acceptance checkpoint

Visual History captures at 1200 / 4900 / 8000 m are produced when a world slice is a review candidate, not for every art edit.

The candidate must retain:

- BEFORE / NOW / AFTER provenance;
- exact SHA / PR / CI provenance;
- repository-retained images and SHA-256;
- AFTER = PENDING until visual acceptance.

## Tier 3 — performance / package / release evidence

Performance, package/cook and other long-running proofs run when their evidence is decision-relevant:

- before closing a performance-sensitive roadmap slice;
- before merge when the slice has an explicit performance budget;
- on `main` / release checkpoints;
- manually when investigating a regression.

Stage-specific authoring/performance workflows should default to `workflow_dispatch` or another explicit milestone trigger unless an automatic run is required to produce a deterministic generated asset.

## Fail-closed rule

Tiering changes *when* expensive proof runs, not *whether* it is required.

A draft PR cannot merge. A ready PR with `asset_full=true` cannot satisfy the aggregate gate unless the exact-head Stage 3G full proof succeeds. If more commits are pushed after review readiness, the exact-head heavy proof is required again.

Code-only Unreal validation remains independent from the Stage 3G full-LFS lane so C++ correctness can still fail fast without materializing the world asset set.

## World-stage operating model

For Stage 3G R4/R5 world-art work, one long-lived **Draft stage integration PR** is the normal iteration surface.

The lifecycle is:

1. **Iteration — lightweight**
   - add or tune vegetation, water, rocks, terrain dressing, materials, lighting, fog and similar world elements;
   - run static/contract/policy/LFS-pointer checks;
   - keep code-only Unreal validation for C++/UE tooling changes;
   - do not run the full map/world proof after every art commit.

2. **Owner visual acceptance — performance checkpoint**
   - when the owner accepts the candidate look, freeze that candidate SHA;
   - capture the stable 1200 / 4900 / 8000 m views and record Visual History NOW;
   - run the stage performance budget on that exact SHA;
   - if performance fails, optimize the accepted visual candidate rather than silently changing art direction.

3. **Stage closeout — full proof**
   - only when the stage is ready to close, mark the stage integration PR Ready for review;
   - run the exact-head full Unreal/Automation/full-LFS/Map Check/save-reopen/Stage 3G proof;
   - require the full proof before merge.

If the final full proof runs on the same tree that already passed the accepted performance checkpoint, performance does not need to be repeated merely because the full proof ran. A material visual/runtime change after the accepted performance checkpoint invalidates that checkpoint and requires a new one.

The intent is to make **world iteration cheap and stage acceptance strict**.
