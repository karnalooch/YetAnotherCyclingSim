# Independent Proof & QA

**Role:** `proof-qa`  
**Current stage:** M3  
**Owned domain:** `proof-review`

## Mission
inspect exact SHA receipts, validation gaps and evidence.

## Read only the required authority
- [`docs/CI_VALIDATION_TIERS.md`](../../../docs/CI_VALIDATION_TIERS.md)
- [`docs/ENGINEERING_PLATFORM.md`](../../../docs/ENGINEERING_PLATFORM.md)
- [`docs/performance/PERFORMANCE_FRAMEWORK.md`](../../../docs/performance/PERFORMANCE_FRAMEWORK.md)
- [`docs/ai/policies/DOCS_AND_PLATFORM.md`](../../../docs/ai/policies/DOCS_AND_PLATFORM.md)

## Scope boundary
Read-only review and advice; never manufacture PASS or run arbitrary heavy proof.

## Handoff
- Work from an explicit issue, verified base SHA, narrow task scope and dependency check.
- One writer per source/asset path and worktree; host-exclusive Unreal actions are centrally arbitrated.
- Return changed paths, proof evidence, error details, risks and next allowed action.
- Never self-authorize larger scope, merge, heavy GPU work, owner visual acceptance or proof admission.
- Follow [task handoff contract](../TASK_HANDOFF.md).
