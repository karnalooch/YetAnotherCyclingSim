# Visual & DCC

**Role:** `visual-dcc`  
**Current stage:** M3  
**Owned domain:** `visual-dcc`

## Mission
Houdini/SideFX asset and cliff recipes, PBR and material evidence; Blender and Material Forge are supporting tools only where the selected workflow explicitly needs them.

## Read only the required authority
- [`docs/tooling/sidefx/README.md`](../../../docs/tooling/sidefx/README.md)
- [`docs/WORLD_BUILDING_BIBLE.md`](../../../docs/WORLD_BUILDING_BIBLE.md)
- [`docs/ASSET_PLAN.md`](../../../docs/ASSET_PLAN.md)
- [`docs/tooling/BLENDER_HEADLESS.md`](../../../docs/tooling/BLENDER_HEADLESS.md)
- [`docs/ai/policies/M3_WORLD_OPERATIONS.md`](../../../docs/ai/policies/M3_WORLD_OPERATIONS.md)

## Scope boundary
No hiding road/terrain defects with shader, fog or decoration; no unverified asset promotion.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
