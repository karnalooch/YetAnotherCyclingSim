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
| C++ | security baseline, CodeQL C++, code-only Unreal canary |
| Build.cs / Target.cs / .uproject / .uplugin / critical Config | security baseline, CodeQL C++, code-only Unreal canary |
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

A C++ change therefore does not download project textures, maps, FBX files,
audio or other LFS payloads merely to prove that source code compiles and the
code-centric Automation suites pass.

## Lightweight asset validation

The asset lane does not start Unreal Engine and does not download LFS payloads.
For changed asset paths it validates Git attributes and pointer state. Required
binary UE/source-media extensions must stay in Git LFS. Deletions are valid and
are handled without requiring the removed payload.

Repository policy remains the global guard for maximum non-LFS blob size and
required LFS extensions.

## Full asset / release lane

Full binary validation is deliberately separate from normal PR CI. Workloads
that intentionally materialize assets — full asset load, map smoke, cook,
package, release proof — belong in an explicit trusted lane such as manual
Unreal proof, nightly validation, or a pre-release workflow.

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
