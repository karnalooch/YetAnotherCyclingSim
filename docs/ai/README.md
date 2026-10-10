# YACS — agent contract router

**Status:** current. This documents delegation/authority; it does **not** run agents, create sessions, grant tool permissions or schedule jobs.

Read [root AGENTS](../../AGENTS.md), then [documentation SSOT router](../README.md). Use [ROLE_REGISTRY.json](ROLE_REGISTRY.json) to map a bounded task domain to one specialist and read only the corresponding role card and listed authority sources.

## Context routing
1. Verify the real issue, dependency gates and milestone in the current [roadmap](../ROADMAP.md).
2. Identify which data authority owns the proposed edit (not simply which tool the agent likes).
3. Locate the `domain_owners` entry and one [role card](roles/); load its `read_docs` paths.
4. Read only the relevant [scoped policies](policies/), not all policy files or archived experiments.
5. Declare task scope, forbidden operations, base SHA, source docs and expected proofs in [TASK_HANDOFF.md](TASK_HANDOFF.md).
6. Delegate independent read-only audits freely; serialize writers in one domain/worktree and any Unreal/GPU/home runner resource.
7. Evidence from a subagent is a claim until checked against the actual head and required proof; no role has merge or proof-admission authority.

## SSOT separation
- Product/milestone: `docs/PRODUCT_REQUIREMENTS.md`, `docs/ROADMAP.md`.
- Road/physics: `docs/STAGE_3_ROUTE_GEOMETRY_CONTRACT.md`, `docs/ROAD_PHYSICS_PROFILE.md`.
- World: `docs/WORLD_BUILDING_BIBLE.md` and World Authority source proofs.
- Runtime/Unreal/MCP: relevant UE contract; MCP is an interface, not world authority.
- Required checks/hosting: `docs/CI_VALIDATION_TIERS.md`, `docs/ENGINEERING_PLATFORM.md` and native runner policies.
- Agent conflicts/supersession: [DECISION_LIFECYCLE.md](DECISION_LIFECYCLE.md).

## Milestone activations
Eight M3 specialist roles are defined, including Physics & Gameplay **maintenance only**. Future M4–M10 specialists appear as planned entries; they cannot author future milestones early. M7 reuses existing world specializations.

This registry is vendor-neutral and contains no IDE adapters or model configuration. Existing unrelated developer/editor preferences are not modified.

## Legacy migration
Six current scoped policy files preserve the prior 727-line root AGENTS rules (original blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`) for task-local reading. Existing current SSOT retains subject authority. Report ambiguous chronological exceptions; do not silently drop them.
