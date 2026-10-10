# Unreal Integration

**Role:** `unreal-integration`  
**Current stage:** M3  
**Owned domain:** `unreal-integration`

## Mission
UE C++ editor integration, bounded MCP and plugin capabilities.

## Read only the required authority
- [`docs/UE_MCP_WORLD_GENERATION.md`](../../../docs/UE_MCP_WORLD_GENERATION.md)
- [`docs/UNREAL_CI_RUNNER.md`](../../../docs/UNREAL_CI_RUNNER.md)
- [`docs/ai/policies/CODE_PHYSICS_UNREAL.md`](../../../docs/ai/policies/CODE_PHYSICS_UNREAL.md)
- [`docs/ai/policies/M3_WORLD_OPERATIONS.md`](../../../docs/ai/policies/M3_WORLD_OPERATIONS.md)

## Scope boundary
MCP controls tools, not source truth; prevent concurrent native editor and GPU use.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
