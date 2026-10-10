# Tooling architecture and AI safety

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

## External tooling architecture policy

YACS uses an **Embark-first tooling review** because proven production tooling
patterns are preferable to inventing another local framework.

For a new editor, DCC, asset-pipeline, indexing, world-authoring or agent tool,
use this decision order:

1. inspect the closest public Embark Studios tool or documented pattern first;
2. use an Epic-native Unreal capability when it solves the same problem cleanly;
3. evaluate a proven open-source tool when neither of the above is sufficient;
4. build custom YACS tooling only for a concrete remaining gap.

"Embark-first" means **adopt or adapt proven patterns before inventing**, not
that every Embark repository becomes a dependency. Public Embark repositories
are evidence of public tooling approaches, not proof of the complete internal
ARC Raiders production stack.

### Explicit Embark-mode directive

When the product owner explicitly says **"Embarkuj"**, **"embark this"** or an
equivalent unambiguous instruction for a subsystem, treat that as explicit
architecture/scope approval to follow the strongest relevant **publicly
documented, production-proven Embark pattern end-to-end** for the current task.

- Do not silently down-scope the pattern to a cheaper, smaller or custom
  approximation merely to save implementation effort, CI time or tool cost.
- Do not replace a documented Embark stage with a guessed YACS shortcut while
  the documented stage is available and applicable.
- Embark mode copies the strongest **public production pattern and boundary**, not
  a vendor brand by itself. If the exact DCC/tool used by the reference pattern is
  unavailable, commercially unsuitable, or unjustified for YACS, use the strongest
  license-clean Unreal-native or open-source implementation that preserves the same
  producer -> derived-data -> consumer contract and required proof. Record the
  substitution explicitly and never claim Embark uses the substitute unless public
  evidence says so.
- Distinguish evidence from inference. If Embark's internal implementation is
  proprietary or unpublished, do **not** invent its node graph, algorithm or
  parameters. Reproduce only the public stage/contract with documented tools
  and YACS-owned inputs, or fail closed and report the missing recipe, license,
  asset or evidence.
- Once a lower-tier YACS/native baseline has failed its required visual or
  technical proof and the evidence ladder justifies escalation, do not keep
  retrying variations of that failed tier unless new evidence identifies a
  specific owning defect.
- Preserve YACS-owned truths: route/physics authority, source provenance,
  deterministic inputs, exact-SHA proof, performance budgets and human visual
  acceptance remain mandatory even in Embark mode.
- A tool or paid license required by the proven pattern is a real dependency
  decision. Record provenance/license evidence and surface acquisition cost or
  runner prerequisites explicitly instead of pretending the dependency does
  not exist.

Before copying, vendoring or adapting third-party source, follow
`docs/legal/DEPENDENCY_PROVENANCE.md`. A reference implementation may be
studied without entering the dependency graph.

Prefer small, high-level YACS domain operations such as route/world generation,
clearance validation and proof capture over exposing a large surface of
low-level Unreal calls to an agent. Repeated multi-step manual authoring should
be treated as pipeline friction worth automating once it is stable and
repeatable.

External tooling never bypasses Gumball policy, generated-content boundaries,
exact-SHA proof, rollback, CI or human visual acceptance. Do not introduce
Rust, AngelScript or another language merely because Embark uses it elsewhere;
language/runtime changes still require a concrete YACS need.

## AI safety rules

- Do not execute broad autonomous changes.
- Do not delete files without explicit approval.
- Do not replace working code only to change style.
- Do not invent APIs, SDK capabilities or device behavior.
- Verify external API and Unreal Engine claims against official documentation.
- Mark generated code that still requires validation.
- Follow `docs/legal/AI_ASSISTED_DEVELOPMENT.md` for AI-assisted work.
- Treat recognizable external implementations in generated output as
  third-party material requiring provenance review.
- When uncertain, stop and ask one focused question.
