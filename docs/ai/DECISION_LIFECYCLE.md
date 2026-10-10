# YACS — agent decision lifecycle

## Precedence and conflicts
1. System, tool/permission, security and protected branch boundaries cannot be overridden by an agent role or repository instructions.
2. Current [Product Requirements](../PRODUCT_REQUIREMENTS.md) own product scope; [Roadmap](../ROADMAP.md) owns the current milestone and dependency graph.
3. The domain SSOT from [documentation index](../README.md) owns implementation methodology; root AGENTS defines non-negotiable cross-domain engineering behavior.
4. Scoped policy documents clarify how to operate in a domain. They do not authorize changes contrary to the approved owner decisions or current SSOT.
5. A later explicit owner decision supersedes only its stated earlier decision and bounded scope; any permanent change must be recorded in its owning SSOT, not silently inferred from chronology.
6. Historical experiments, chat summaries and archived snapshots are evidence and may not become sole authority.

## Decision record
For disputes, record `decision_id`, `scope`, `status` (ACTIVE/SUPERSEDED/HISTORICAL), `source_issue_or_pr`, `authority_file`, `supersedes`, `effective_since` and `expiration_or_review_gate`. Ambiguity blocks the specific mutation; don't choose a convenient precedent.

## Guarded examples (2026-10-10)
- #363 is accepted; #384 remains the bounded official Epic MCP spike before #364. It is not general permission to control/modify world truth.
- Performance is measured after assembled M3 under the 2026-10-09 directive: record `DEFERRED_AFTER_M3` / `performance_pass: false`. Whole-area visual, native, exact-SHA and protected CI gates still apply.
- Frozen Landscape directives have narrow later authorized local-correction exceptions, with fixed original data, bounded delta and rollback. See [M3 scoped decisions](policies/M3_WORLD_OPERATIONS.md) and current world SSOT before any editing.
- Future M4–M10 competencies in the role registry are plans, not permission to implement out-of-stage functionality.
