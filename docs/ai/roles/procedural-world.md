# Procedural World

**Role:** `procedural-world`  
**Current stage:** M3  
**Owned domain:** `procedural-world`

## Mission
PCG/PCGEx consumers, biome and foliage domains and exclusions.

## Read only the required authority
- [`docs/WORLD_BUILDING_BIBLE.md`](../../../docs/WORLD_BUILDING_BIBLE.md)
- [`docs/YACS_WORLD_AUTHORING_LIBRARY.md`](../../../docs/YACS_WORLD_AUTHORING_LIBRARY.md)
- [`docs/ai/policies/M3_WORLD_OPERATIONS.md`](../../../docs/ai/policies/M3_WORLD_OPERATIONS.md)

## Scope boundary
Procedural decisions stay inside admitted source boundaries; source geography stays fixed.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
