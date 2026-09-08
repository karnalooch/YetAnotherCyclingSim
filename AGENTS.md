# YetAnotherCyclingSim — AI development rules

## Project context

YetAnotherCyclingSim is a realistic indoor cycling simulator built with Unreal Engine 5.

Before making changes, read:

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ROADMAP.md`

The product owner is a beginner programmer. Explanations intended for the product owner must be written in clear Polish. Code, identifiers, filenames, commit messages and technical names must be written in English.

## Scope control

- Implement only the task explicitly requested.
- Do not add speculative features.
- Do not expand MVP scope without updating the requirements.
- Do not start future roadmap stages early.
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

Never claim that code works without running an appropriate check.

## Code rules

- Keep gameplay and physics logic independent from rendering.
- Physics results must not depend on frame rate.
- Use SI units internally.
- Document units in public interfaces.
- Prefer deterministic calculations.
- Avoid logic in Unreal Level Blueprints.
- Use Blueprints for presentation, configuration and rapid prototyping.
- Use C++ for stable domain logic, physics and testable systems.
- Avoid Tick when an event, timer or fixed-step system is sufficient.
- Avoid hard-coded asset paths and unexplained magic numbers.
- Store tunable values in data assets, configuration or clearly named structures.
- Keep classes and functions focused on one responsibility.
- Treat warnings as problems to investigate.
- Do not silently ignore errors.

## Physics rules

- The cycling physics core must be testable without rendering a UE level.
- Separate rider input, environment, route state and physics output.
- Use a fixed simulation step.
- Include tests for flat road, climb, descent, coasting and wind.
- Cornering outcomes must be deterministic for the same inputs.
- Crashes are outside the MVP.
- MVP cornering consequences are line widening, controlled slip, speed loss, time loss and technique score.

## Unreal Engine rules

Do not commit generated Unreal directories:

- `Binaries/`
- `DerivedDataCache/`
- `Intermediate/`
- `Saved/`
- `.vs/`

Track Unreal binary assets through Git LFS:

- `*.uasset`
- `*.umap`

Before adding an asset:

- verify its license;
- record its source;
- check its performance cost;
- confirm that it is required by the current roadmap stage.

Target performance is 60 FPS at 1920×1080 on:

- Intel Core i5 10th generation;
- 32 GB RAM;
- NVIDIA RTX 2070 Super.

Performance must be measured, not guessed.

## Git rules

- Never commit credentials, API keys, tokens or private user data.
- Never rewrite shared Git history without explicit approval.
- Do not use destructive Git commands.
- Keep commits small and focused.
- Use English Conventional Commit messages where practical.
- Review `git status` and the diff before committing.
- Do not commit unrelated files.

Examples:

- `docs: update product requirements`
- `feat: add fixed-step cycling physics`
- `test: cover coasting on negative grade`
- `fix: prevent speed from becoming negative`
- `chore: configure Unreal asset tracking`

## AI safety rules

- Do not execute broad autonomous changes.
- Do not delete files without explicit approval.
- Do not replace working code only to change style.
- Do not invent APIs, SDK capabilities or device behavior.
- Verify external API and Unreal Engine claims against official documentation.
- Mark generated code that still requires validation.
- When uncertain, stop and ask one focused question.
