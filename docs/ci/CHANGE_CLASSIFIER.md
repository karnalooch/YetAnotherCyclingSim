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
| asset-only | Repository policy, Governance, lightweight asset validation |
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

The reusable lane is ready for source-only execution, but YACS self-hosted
runner policy is still Phase 1 manual/trusted. Therefore `ue_code=true` is a
routing signal, not yet an automatic Aggregate requirement. Automatic Unreal execution must use the proven trusted self-hosted runner
Phase 2/3 path. The hosted CircleCI UE-seed/cache PoC was retired because the
multi-gigabyte engine transport created disproportionate storage/network cost.

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

## Full asset / release lane

Full binary validation is deliberately separate from normal PR CI. The current
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

There is intentionally no schedule or PR trigger yet. Nightly automation
belongs to the trusted runner Phase 2/3 rollout. Packaging is manual and
fail-closed; the package mode performs the cook as part of BuildCookRun rather
than maintaining a second, partially overlapping cook-only implementation.

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
