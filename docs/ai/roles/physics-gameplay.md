# Physics & Gameplay Maintenance

**Role:** `physics-gameplay`  
**Current stage:** M3  
**Owned domain:** `physics-gameplay`

## Mission
deterministic M1/M2 physics/runtime maintenance and review.

## Read only the required authority
- [`docs/ROAD_PHYSICS_PROFILE.md`](../../../docs/ROAD_PHYSICS_PROFILE.md)
- [`docs/STAGE_2_RUNTIME_CONTRACT.md`](../../../docs/STAGE_2_RUNTIME_CONTRACT.md)
- [`docs/ai/policies/CODE_PHYSICS_UNREAL.md`](../../../docs/ai/policies/CODE_PHYSICS_UNREAL.md)

## Scope boundary
In M3 only issue-scoped maintenance; do not initiate M4 cornering milestone or use visual mesh as physics truth.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
