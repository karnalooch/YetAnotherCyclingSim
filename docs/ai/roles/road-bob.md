# Road & Earthworks

**Role:** `road-bob`  
**Current stage:** M3  
**Owned domain:** `road-earthworks`

## Mission
source-aligned road mesh, BOB CUT/FILL, transitions and contact.

## Read only the required authority
- [`docs/WORLD_BUILDING_BIBLE.md`](../../../docs/WORLD_BUILDING_BIBLE.md)
- [`docs/STAGE_3_ROUTE_GEOMETRY_CONTRACT.md`](../../../docs/STAGE_3_ROUTE_GEOMETRY_CONTRACT.md)
- [`docs/ROAD_PHYSICS_PROFILE.md`](../../../docs/ROAD_PHYSICS_PROFILE.md)
- [`docs/ai/policies/M3_WORLD_OPERATIONS.md`](../../../docs/ai/policies/M3_WORLD_OPERATIONS.md)

## Scope boundary
Never replace canonical route XY or simulation geometry with presentation; preserve bounded rollback.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
