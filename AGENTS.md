# YACS — AI engineering rules

## Entry and authority
- Identify the approved issue and milestone before making a change.
- Read [documentation authority index](docs/README.md) and [agent context router](docs/ai/README.md); load only relevant SSOT, role card and scoped rules.
- [Product Requirements](docs/PRODUCT_REQUIREMENTS.md) owns scope; [Roadmap](docs/ROADMAP.md) owns delivery and dependencies; [World Building Bible](docs/WORLD_BUILDING_BIBLE.md) owns world-building methodology.
- [Role registry](docs/ai/ROLE_REGISTRY.json) records task owners, not a running autonomous agent framework.
- Historical experiments, notes and archived plans are evidence, not active authority. Report contradictions instead of guessing.

## Global safety
- Change only approved scope. Do not add speculative features, bypass predecessor issues or begin post-MVP systems early.
- Keep physics deterministic and frame-independent, with SI units; route truth, physics inputs and geographic truth must not be overwritten by visual presentation.
- Treat terrain, roads and generated assets as sourced, reproducible and non-destructive; never conceal geometry defects with materials or foliage.
- Never commit credentials, secrets, personal data, generated UE caches or unlicensed third-party material; follow [AI policy](docs/legal/AI_ASSISTED_DEVELOPMENT.md) and [provenance requirements](docs/legal/DEPENDENCY_PROVENANCE.md).
- No destructive Git operations, shared-history rewrites, new major dependencies or architecture/scope expansion without the required authorization.
- Never weaken tests, CI, exact-SHA evidence, hardware proof or human visual acceptance. Unverified is not PASS.

## Owner communication and execution
- Explain to the owner in clear Polish. GitHub issue/PR titles, descriptions, comments and reviews, code identifiers and commits must use English.
- Before edits: inspect current code/docs/issue state; state assumptions, risks, and bounded plan. Await approval for changes beyond standing scope.
- After edits: inspect the diff, run relevant validation, report changed files, status, exact errors, and outstanding proof.
- Prefer authorized remote GitHub delivery over requesting avoidable manual patches or mode switching. Report the exact capability failure when unavailable.
- Follow standing merge authorization only when an approved non-Draft PR is mergeable with all required CI, review and Unreal/visual gates verified.

## M3 and authority boundaries
- M0–M2 complete; M3 Route & World Foundation is current. Do not implement M4–M10 early.
- #363 accepted; #384 official UE MCP bounded spike precedes #364 asphalt/shoulder. Reverify issue dependencies and the actual stage gate before implementation.
- Preserve canonical real-road alignment, licensed DTM and World Authority spatial evidence. Road Physics Profile owns physics; BOB owns its bounded earthworks; MCP, PCG/PCGEx and Blender are tools/consumers, never source truth.
- M3 benchmark decision: `DEFERRED_AFTER_M3`, `performance_pass: false`. Native proof, whole-area visual review and protected CI remain mandatory as scoped.
- Read [M3 world/host policy](docs/ai/policies/M3_WORLD_OPERATIONS.md) for UE/terrain/road/material/world tasks.

## Agent delegation
- Use [agent router](docs/ai/README.md) and [task handoff](docs/ai/TASK_HANDOFF.md); choose one domain owner and the minimal task-specific context.
- One writer per affected path/worktree. At most two unmerged implementation branches; documentation-only branches excluded from that limit.
- Serialize conflicting Unreal Editor, native build, GPU and home-runner operations using existing ownership arbitration. Never disrupt an open local editor to obtain runner access.
- Specialists cannot grant scope, proof acceptance, owner visual signoff, heavy-workflow authority or merge privileges to themselves.
- A role definition is documentation, not an automatic guarantee that a subagent launched. Report NOT RUN or BLOCKED honestly.

## Verification and project hygiene
- Verify and update relevant documentation SSOT in the same PR; report docs links/i18n/structure/freshness guards.
- Use [CI validation tiers](docs/CI_VALIDATION_TIERS.md) and [Gumball](docs/ENGINEERING_PLATFORM.md) Proof Broker. Do not invent a second proof framework.
- Distinguish local candidate, remote commit, tests, native runtime proof, visual acceptance and merge. Record exact head SHA and evidence for each claim.

## Detailed rules (load only when applicable)
- [Delivery, scope and owner preferences](docs/ai/policies/DELIVERY_AND_SCOPE.md)
- [World/Unreal editor/BOB/PCG decisions](docs/ai/policies/M3_WORLD_OPERATIONS.md)
- [Docs, platform, incident reports](docs/ai/policies/DOCS_AND_PLATFORM.md)
- [Code, physics, Unreal, provenance](docs/ai/policies/CODE_PHYSICS_UNREAL.md)
- [Git, issue, Project, merge, office/home](docs/ai/policies/GIT_AND_PROJECT.md)
- [Tools, production evidence and AI safety](docs/ai/policies/TOOLING_AND_AI_SAFETY.md)
