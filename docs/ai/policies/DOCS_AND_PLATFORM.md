# Docs, Gumball and problem reporting

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

### Documentation SSOT and freshness

Documentation verification is mandatory for every repository-changing task.

Before implementation:

- Start from `docs/README.md` and use it to identify the current authoritative SSOT for the affected area.
- Do not treat takeover notes, snapshots, historical handoffs, or anything under `archive/` as current truth unless the current SSOT explicitly points to it as authoritative.
- If `docs/README.md` is missing or does not identify an authoritative source for the affected area, report that as a documentation-governance defect instead of guessing which document is current.

After implementation:

- Re-check the relevant SSOT against the resulting code, configuration, workflows and CI behavior.
- If the implementation makes the documentation stale, incomplete or misleading, update the affected documentation in the **same pull request**.
- Do not defer a required documentation correction to a later task merely because the code change is already working.

When any documentation changes, run all required documentation guards:

- links;
- i18n;
- structure;
- freshness.

Do not silently skip a required guard. If a guard is unavailable, missing or broken, report that explicitly with the command/workflow attempted and the resulting evidence.

The final status/report for the task must state:

- which current SSOT was identified through `docs/README.md` and verified;
- whether implementation required documentation updates;
- the result of each documentation guard: links, i18n, structure and freshness.

## Gumball repository baseline

YACS consumes shared engineering contracts through Gumball (`karnalooch/engineering-platform`). The repository-specific authority for that integration is `docs/ENGINEERING_PLATFORM.md`.

- Adopt Gumball in `preserve-local` mode: never replace a stronger YACS-specific control merely because a generic platform equivalent exists.
- Keep all external Actions and shared workflow references pinned to reviewed immutable 40-character SHAs.
- Keep the final `Aggregate CI gate` caller-local and fail closed.
- Treat `.gumball/repository-os.json` as the shared lifecycle/label/CI-cost policy, while preserving existing YACS Project automation and branch hygiene when they are stronger or more specific.
- Active pull requests should normally carry the canonical Gumball `type:*`, `area:*`, `risk:*` and `ci:*` dimensions once trusted Repository Ops has classified them.
- Heavy runtime, visual, hardware or editor proofs must follow the YACS validation tiers and exact-SHA policy. When a proof is broker-managed, use the trusted Proof Broker intent path and keep manual `workflow_dispatch` only as fallback.
- After completing a CI, governance, security, documentation, tooling, MCP or agent-workflow improvement, decide whether the reusable invariant should be promoted back to Gumball. Record a downstream candidate under `.gumball/candidates/` when appropriate.
- Promote reusable invariants and failure behavior, not YACS-specific map names, machine paths or product-specific acceptance thresholds.

### Problem reporting

If any problem, failure, blocker, unexpected behavior, or incomplete validation occurs, describe it precisely in the status or final report. Do not reduce it to a vague statement such as "it failed", "UE hung", or "the test did not work".

For every relevant problem, report:

- what operation was being performed and the exact command, test, script, or workflow involved;
- what was expected to happen;
- what actually happened;
- the exact error message, exit code, failing assertion, relevant log excerpt, or other evidence when available;
- whether the problem is in product code, tests, build/tooling, CI, Unreal/editor/runtime environment, local machine setup, or still unknown;
- the current diagnosis and the evidence supporting it;
- every meaningful fix or workaround attempted and its result;
- any files or configuration changed while investigating;
- what remains unverified or blocked;
- the smallest recommended next action to continue safely.

Clearly distinguish a confirmed root cause from a hypothesis. Do not claim a blocker is resolved until the relevant build, test, runtime proof, or other required validation has actually passed.

Never claim that code works without running an appropriate check.

