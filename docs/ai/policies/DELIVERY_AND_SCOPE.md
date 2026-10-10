# Delivery, scope and remote-first execution

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

## Project context

YetAnotherCyclingSim is a realistic indoor cycling simulator built with Unreal Engine 5.

Before making changes, read:

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ROADMAP.md`
- for world/terrain/road work: `docs/WORLD_BUILDING_BIBLE.md`

The product owner is a beginner programmer. Explanations intended for the product owner must be written in clear Polish. Code, identifiers, filenames, commit messages and technical names must be written in English.

Owner language rule, 2026-10-04: all GitHub issue and pull-request titles,
descriptions, comments, review summaries and review replies must be written
exclusively in English. This includes progress reports and owner-decision
summaries published on GitHub. Polish is for direct conversation with the owner,
not GitHub delivery. Check the language before creating or updating GitHub text;
preserve exact code, paths, identifiers and source titles where required.

## Scope control

- Implement only the task explicitly requested.
- Do not add speculative features.
- Do not expand MVP scope without updating the requirements.
- Do not start future product milestones early.
- Prefer the smallest working solution.
- Do not introduce a service, framework, plugin or dependency without explaining why it is needed.
- Do not create a separate backend process unless measurements or requirements justify it.
- Do not implement multiplayer before the single-player MVP is stable.
- Do not implement real trainer connectivity before the simulated input is stable.

## Working method

Before editing:

1. Explain in Polish what will change.
2. Inspect existing files and conventions.
3. State assumptions and risks.
4. Propose a small implementation plan.
5. Wait for approval when the change affects architecture, dependencies or scope.

After editing:

1. Build or validate the changed component.
2. Run relevant tests.
3. Describe the result in Polish.
4. List changed files.
5. Report any unverified behavior.
6. Suggest one logical commit message.

### Remote-first delivery and durable owner preferences

Owner reaffirmation, 2026-10-01 (Issue #297): use authorized remote GitHub delivery from the current conversation whenever available. Do not default to handing the owner a patch or requiring a mode switch merely because local Git, credentials, DNS, Unreal or a workstation is unavailable.

- Discover the current connector's read and write capabilities, inspect the exact repository/PR state, and attempt the applicable authorized operation before declaring a remote limitation. Historical success is not proof that every current operation is available, but an unavailable local CLI is not proof that GitHub is read-only.
- Prefer normal connector writes, focused branches/PRs and the trusted Proof Broker. Use an authorized supported alternative when necessary; never obtain hidden credentials, bypass permissions, weaken protection, fabricate CI success or force-push shared history.
- Report a real failure with the attempted operation, error and affected layer: local container, tool availability, authorization, protected branch, Actions or runner. Do not turn one failing operation into a blanket claim that all remote delivery is impossible.
- Within the approved scope, the owner's standing authorization covers choosing necessary proofs and normal protected closeout. Keep cost classification, compile reuse, exact-SHA evidence, required tests and visual/performance gates. Do not launch unnecessary heavy jobs or ask repeatedly for approval already given.
- Distinguish a local candidate, a remote commit, a passing test, a render, a merge and a playable feature. Never promise unattended/background continuation unless an actual supported scheduled mechanism was created.
- These instructions are durable project memory in this repository. Do not claim to have changed global ChatGPT profile memory without a successful memory-write operation.

