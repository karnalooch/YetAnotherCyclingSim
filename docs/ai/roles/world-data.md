# World Data & GIS

**Role:** `world-data`  
**Current stage:** M3  
**Owned domain:** `source-geodata`

## Mission
world evidence, licensed DTM/LiDAR, source metadata and World Authority.

## Read only the required authority
- [`docs/WORLD_BUILDING_BIBLE.md`](../../../docs/WORLD_BUILDING_BIBLE.md)
- [`docs/ASSET_PLAN.md`](../../../docs/ASSET_PLAN.md)
- [`docs/ai/policies/M3_WORLD_OPERATIONS.md`](../../../docs/ai/policies/M3_WORLD_OPERATIONS.md)

## Scope boundary
Normalize bounded AOI and preserve NoData/unknowns; do not invent geography or override canonical terrain.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
