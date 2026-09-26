# YACS CI change classifier

Status: **ACTIVE DESIGN**

YACS routes CI from one path classifier: `scripts/ci/classify_changes.py`.
The classifier decides which lanes are required; individual workflows must not
grow their own competing path-regex policy.

## Routing matrix

| Change class | Required lanes |
| --- | --- |
| docs-only | Repository policy, Governance, Aggregate |
| Python | Python reference tests, security baseline, CodeQL Python |
| C++ | security baseline, CodeQL C++; classifier also emits `ue_code=true` |
| Build.cs / Target.cs / .uproject / .uplugin / critical Config | security baseline, CodeQL C++; classifier also emits `ue_code=true` |
| CI/tooling | CI contract tests plus security baseline; UE canary only when Unreal-facing tooling changed |
| asset-only | Repository policy, Governance, lightweight asset validation; Stage 3G/high-risk assets additionally require full validation |
| code + assets | union of the relevant code lanes and asset validation |
| unknown path | Repository policy, Governance, security baseline; classifier exposes `unknown=true` |
| schedule/manual static run | Python + C++ static/security + CI contracts, but no asset payload and no UE canary |

The local `Aggregate CI gate` is fail-closed. For every optional lane it checks
both directions: a lane classified as required must finish successfully, while
a lane classified as unnecessary must actually be skipped.

## Code-only Unreal contract

The reusable Unreal lane is intentionally source-only:

- `GIT_LFS_SKIP_SMUDGE=1`;
- checkout uses `lfs: false`;
- `Test-YacsCodeOnlyCheckout.ps1` requires tracked LFS assets to remain pointer files;
- only after that guard passes may the Editor build and scoped Automation run.

The reusable code-only lane remains a routing building block. Heavy Unreal execution uses the proven repository-scoped `yacs-ue58` self-hosted runner and must never depend on shipping the Engine through hosted CI cache/workspace storage.

When automatic Unreal execution is enabled, a C++ change must not download
project textures, maps, FBX files, audio or other LFS payloads merely to prove
that source code compiles and the code-centric Automation suites pass.

## Lightweight asset validation

The asset lane does not start Unreal Engine and does not download LFS payloads.
For changed asset paths it validates Git attributes and pointer state. Required
binary UE/source-media extensions must stay in Git LFS. Deletions are valid and
are handled without requiring the removed payload.

Repository policy remains the global guard for maximum non-LFS blob size and
required LFS extensions.

## Full asset / release lanes

High-risk Stage 3G changes now participate in normal PR CI through
`.github/workflows/reusable-stage3g-full.yml`. The classifier emits
`asset_full=true` only for the canonical Stage 3G environment, map, terrain
runtime, authoring/proof tooling and world-generation specification. Ordinary
asset changes still use only lightweight pointer validation.

The automatic Stage 3G lane runs only for same-repository PRs or trusted main
pushes. Fork PRs never receive self-hosted runner access; if such a PR requires
`asset_full=true`, the Aggregate gate fails closed because the heavy lane is
skipped.

The lane materializes full LFS, runs the deterministic Stage 3G authoring pass,
then the final non-mutating proof (Automation, fresh-load persistence, Map
Check, LFS integrity and canonical visual captures), uploads concise proof
artifacts and unconditionally cleans the runner workspace.

Release-oriented binary validation remains deliberately separate. The manual
trusted entrypoint is `.github/workflows/asset-full.yml`.

Phase 1 exposes four manual modes on `main` only:

- `map-smoke` — full LFS checkout, Editor build + Stage 3 Automation,
  deterministic save/reload verification and Map Check, with rendered
  performance intentionally skipped;
- `visual` — full LFS checkout and rendered Stage 3 visual-environment proof;
- `package` — explicit Win64 `BuildCookRun` for
  `/Game/Prototype/Maps/L_CyclingTest`, covering build + cook + stage +
  pak/archive and validating the archived executable/content containers;
- `full` — Stage 3 build/Automation/persistence/Map Check/performance,
  rendered visual proof, and Win64 package proof.

The workflow resolves an exact trusted `main` SHA before checkout, uses the
repository-scoped `yacs-ue58` self-hosted runner, requests read-only repository
permissions, runs `git lfs fsck`, uploads only concise proof artifacts and
always cleans the workspace.

Packaging remains manual and fail-closed; the package mode performs the cook as part of BuildCookRun rather than maintaining a second, partially overlapping cook-only implementation. A future nightly may reuse the trusted heavy lane, but package/full release proof is not part of ordinary PR validation.

The normal Aggregate gate must never start a full asset/cook/package workload
only because a documentation, Python, C++ or small asset change was pushed.

## Ownership

- **Classifier:** which lanes are required.
- **Governance:** high-risk path and workflow policy.
- **Repository policy:** LFS and repository hygiene.
- **Security workflows:** dependency, Trivy and language-specific CodeQL.
- **Unreal code lane:** source build + scoped Automation without assets.
- **Full asset/release lane:** explicit heavy runtime proof.
- **Aggregate CI gate:** verifies the classifier decision was actually honored.
