# YACS — AI engineering rules

## Entry and authority
- Identify the approved issue and milestone before making a change.
- Read [documentation authority index](docs/README.md) and [agent context router](docs/ai/README.md); load only relevant SSOT, role card and scoped rules.
- [Product Requirements](docs/PRODUCT_REQUIREMENTS.md) owns scope; [Roadmap](docs/ROADMAP.md) owns delivery and dependencies; [World Building Bible](docs/WORLD_BUILDING_BIBLE.md) owns world-building methodology.
- [Role registry](docs/ai/ROLE_REGISTRY.json) records task owners, not a running autonomous agent framework.
- Historical experiments, notes and archived plans are evidence, not active authority. Report contradictions instead of guessing.

## Houdini is the primary world-authoring executor
- Owner decision `HOUDINI_SIDEFX_PRIMARY_20261016`, reaffirmed 2026-10-20: use Houdini and original SideFX tutorial HIP/HDA workflows for new terrain, roads, cliffs and environment generation. Houdini leads the workflow. Unreal is the consumer/runtime; PCG/PCGEx and Blender are supporting or retained integration tools. Material Forge supplies supporting surface appearance, and Blender supplies supporting preparation/inspection. The immediate priority is completing Pegasus lessons 06 and 07 while preserving the accepted Houdini source/cache and proving the resulting UE consumer.
- Read the [SideFX workflow and complete source concordance](docs/tooling/sidefx/README.md). Map every implemented step to an exact lesson/time range, original project/node/parameter or a verified official SideFX solution. Record all adaptations and missing dependencies; indexing a transcript is not implementation proof.
- Before Sa Calobra authoring, read the [build guide](docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md). It operationalizes this direction under the Bible: real geography -> Houdini/Pegasus with suitable native/Labs tools -> Unreal consumer. Its later-stage rows are not permission to exceed the current terrain/mask scope.
- Owner clarification, 2026-10-17: follow the Pegasus workflow itself, **base first, details afterwards**. Review/cache the base, keep manual corrections separate, then apply the source-mapped terrain-detail and material workflow. DTM import plus a low-amplitude noise preview is not the completed Landscape. Preserve Source / Manual Edits / Procedural Detail separation; historical 0.178 m results and the proposed 0.5 m bound are not permanent detail specifications. Follow the ordered passes in the build guide without rebuilding the base on every detail iteration.
- Consult the [reviewed SideFX Labs 22.0.466 package](docs/tooling/sidefx/SIDEFX_LABS_22_0_466.md) before implementing an operation it may already provide. Verify actual loaded package/node versions, deprecated replacements and dependencies; an uploaded archive is not runtime proof. Keep the distribution, binaries and full help corpus outside Git.
- Resume the existing Sa Calobra HIP and verified caches; change one bounded graph/layer branch, record invalidation and fresh-reopen/geometry evidence. Do not restart the pipeline, recook unchanged whole areas or create parallel delivery PRs merely because a new session lacks context. Preserve the separate Unreal configuration profile and active owner sessions.
- Do not invent replacement terrain, erosion, road or world-generation algorithms. Research official SideFX solutions for a missing step; if unresolved, stop that dependent stage and report the exact gap.
- Current owner scope is an independent, fresh Houdini Landscape for the entire Ma-2141 with 500 m on each side and surrounding background. Latest clarification: original Sa Calobra relief/elevations, using Pegasus methods; do not copy fictional-island noise/erosion settings that change real macro terrain. The latest owner clarification permits delicate deformation in a separate reversible Houdini layer, while retaining real macro relief. Record and measure the actual delta; never treat an assistant-proposed tuning value as an owner or SideFX standard. No road or other world assets are included yet.

## Implementation: research and reuse first
- Before starting implementation, search the internet for current official documentation and existing working solutions: supported tools, plugins, APIs, MCP integrations and examples. Do not begin by writing replacement logic.
- Prefer a suitable existing solution. When a tool already provides the required logic, automate that tool and adapt the input data instead of reimplementing its behavior.
- Write custom logic only after research establishes a concrete gap that existing solutions cannot cover within the approved scope. Record the solutions checked and the reason an adapter or custom implementation is necessary.
- Match documentation to the installed versions and verify the chosen solution with a small reproducible case. Vendor documentation is capability evidence, not proof that the YACS integration works.

## Global safety
- Change only approved scope. Do not add speculative features, bypass predecessor issues or begin post-MVP systems early.
- Keep physics deterministic and frame-independent, with SI units; route truth, physics inputs and geographic truth must not be overwritten by visual presentation.
- Treat terrain, roads and generated assets as sourced, reproducible and non-destructive; never conceal geometry defects with materials or foliage.
- **Source retention and scoped fresh rebuild:** preserve original `Base_DTM`, geographic metadata, accepted checkpoints and the active Unreal scene. The 2026-10-16 owner decision authorizes a separate fresh Houdini Landscape and supersedes the freeze for that candidate only. Record source-relative deltas; a procedural experiment is not measured geography or an admitted replacement. Existing consumer repairs remain bounded and reversible; follow [World Building Bible section 6](docs/WORLD_BUILDING_BIBLE.md#6-landscape-edit-layers-contract).
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
- Preserve canonical real-road alignment, licensed DTM and World Authority spatial evidence. Road Physics Profile owns physics; BOB owns its bounded earthworks constraints; Houdini executes the selected SideFX authoring recipe. MCP, PCG/PCGEx and Blender are interfaces/supporting tools, never source truth.
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
