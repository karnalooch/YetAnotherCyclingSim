# YACS CI change classifier

Status: **ACTIVE DESIGN**

YACS routes CI from one path classifier: `scripts/ci/classify_changes.py`.
The classifier decides which lanes are required; individual workflows must not
grow their own competing path-regex policy.

The classifier follows the Gumball CI Cost Governor rule: **classify before
computing and run the cheapest trustworthy proof**.

## Routing outputs

The main impact outputs are:

- `python` — Python/static contract surface changed;
- `cpp` — C/C++/C# source under a project or plugin `Source/` tree changed;
- `assets` — tracked source/game asset surface changed;
- `ci` — CI/tooling surface changed;
- `ue_code` — the automatic code-only Unreal lane is required (legacy
  compatibility signal; equivalent to `unreal_runtime`);
- `unreal_compile` — an input capable of changing Editor binaries or their
  build/engine-selection contract changed;
- `unreal_runtime` — fresh code-only Unreal/Automation evidence is required;
- `unreal_execution_class` — `static`, `runtime`, or `compile`;
- `ue_tooling` — Unreal editor/authoring/proof tooling changed, but that fact
  alone does **not** require an automatic Editor build;
- `asset_full` — the change requires the heavy legacy Stage 3G compatibility
  lane at the configured readiness boundary;
- `stage3g_authoring` — actual legacy assets, specifications or authoring producers
  changed; require legacy world authoring and final proof rather than the
  compatibility-only mode;
- `unknown` — the classifier could not map at least one path confidently;
- `ci_cost_class` — one of `light`, `standard`, `heavy`.

## Routing matrix

| Change class | Required lanes | Cost |
| --- | --- | --- |
| docs-only | Repository policy, Governance, Aggregate | `light` |
| Python | Python reference tests, security baseline, CodeQL Python | `standard` |
| C++ / plugin C++ | security baseline, CodeQL C++, code-only Unreal build + Automation | `heavy` |
| Build.cs / Target.cs / .uproject / .uplugin / compile-orchestration helper | security baseline, CodeQL C++, code-only Unreal COMPILE + Automation | `heavy` |
| critical Config | security baseline plus code-only Unreal RUNTIME Automation on verified binaries | `heavy` |
| CI/tooling | CI contract tests plus security baseline | normally `standard` |
| Unreal proof/editor/authoring tooling | CI/Python/contracts as applicable; **no automatic code build solely because the path is under `scripts/ue/**`** | normally `standard` |
| code-build tooling used by the automatic Unreal lane | CI contracts plus code-only Unreal build + Automation | `heavy` |
| asset-only | Repository policy, Governance, lightweight asset validation | `standard` |
| `asset_full` world change | lightweight validation plus legacy compatibility at readiness; full legacy authoring only when `stage3g_authoring=true` | `heavy` |
| code + assets | union of the relevant code lanes and asset validation | highest required class |
| unknown repository path | Repository policy, Governance, security baseline; exposes `unknown=true` | `standard` |
| unknown runtime-sensitive path under `Source/`, `Config/`, `Plugins/` or `Build/` | fail closed to `ue_code=true` | `heavy` |
| schedule/manual static run | Python + C++ static/security + CI contracts, but no asset payload and no automatic UE build | `standard` |

The local `Aggregate CI gate` is fail-closed. For every optional lane it checks
both directions: a lane classified as required must finish successfully, while
a lane classified as unnecessary must actually be skipped. It also validates
that `ci_cost_class` is one of the three canonical values and that heavy
Unreal/full-world impact cannot be mislabeled as a cheaper class.

### Unreal execution class

The cost label and the Unreal execution mode are deliberately separate. The
classifier also emits `unreal_execution_class`:

- `static` — no fresh Unreal runtime is required by the changed surface;
- `runtime` — Unreal/world/Automation evidence is required, but verified
  Editor binaries may be reused;
- `compile` — the compiled binary contract changed and a build is required
  before runtime evidence. The self-hosted resolver then chooses `warm` or
  `cold`; path classification does not try to outsmart UnrealBuildTool's
  dependency graph.

`unreal_compile_fingerprint` hashes the project descriptor, compiled
project/plugin source, plugin descriptors and the normal lane's build/engine-selection
orchestration contract. `unreal_proof_fingerprint` extends that identity with
runtime-critical Config and the remaining code-only proof contract.

The self-hosted code-only lane keeps a repository-scoped warm worktree. Only
the explicit build-state allow-list survives between revisions: project/plugin
`Binaries`, `Intermediate`, and `Saved/BuildCache/UnrealCi`. All other
untracked and ignored residue is removed before and after proof execution.
Reuse is accepted only when the current compile fingerprint, proof fingerprint,
installed UE build identity and expected project DLLs match a previously green
state. Engine discovery is shared with the actual build through
`scripts/ci/Resolve-YacsUnrealEngine.ps1`; the `.uproject` `EngineAssociation` is
mandatory and the identity includes the resolved root plus hashes of the engine
version, build launcher and Editor command binary. Missing or malformed state fails closed. COMPILE has two runner-side
submodes:

- `warm` — verified engine/toolchain provenance matches. Preserve project and
  plugin `Binaries/Intermediate` and let UBT/UBA decide the minimal outdated
  compile/link action graph. Compile-fingerprint mismatch, a previous failed
  compile, or a missing final DLL use this path.
- `cold` — cache provenance is missing/malformed or the engine/toolchain
  environment identity drifted. Purge project/plugin build outputs before UBT.

Before COMPILE work the prior verified stamp is invalidated; before RUNTIME work
its proof bit is invalidated. A cancelled or failed mutable run can therefore
never leave a green stamp that a later revision may trust. A proof-only mismatch
runs Automation with `-SkipBuild`; a full match emits a fresh exact-head
equivalence artifact without rerunning unchanged Automation.

This is semantic proof reuse, not SHA reuse: the current HEAD is still checked
out and verified exactly, and the equivalence evidence records the current HEAD
plus the fingerprints of every input allowed to affect the reused proof.

## Dedicated proof refinements

Specialized heavyweight proofs may ask the same central classifier for a
narrower execution mode when the proof has materially different setup costs.
They must not create a second independent path-regex authority.

The active Passo Giau Embark terrain workflow calls
`scripts/ci/classify_changes.py --embark-terrain-proof`. That refinement emits:

- `proof_mode=cheap` for contract/documentation-only changes;
- `proof_mode=render` for current terrain-preparation, bounded geometry and
  visual-proof inputs that need fresh evidence but not a new binary contract;
- `proof_mode=heavy` for build-affecting Unreal or proof-build contract
  changes.

The same invocation emits `compile_fingerprint`, a SHA-256 identity derived
from the pinned UE/PCGEx versions plus the project binary graph and M3 build
contract. `proof_mode=heavy` means **build required**, not **cold rebuild**.
The self-hosted M3 resolver separately chooses:

- `none` on a verified fingerprint + environment + PCGEx pin/binary hit;
- `warm` when build inputs changed but the UE/toolchain environment and pinned
  plugin dependency remain compatible, preserving intermediates for UBT;
- `cold` only for missing/untrusted state, environment drift or PCGEx
  pin/checkout drift.

Unknown/empty specialized change sets still fail closed to `heavy`; they may
benefit from WARM compilation only after the runner proves the reusable
environment boundary.

## Unreal code vs Unreal tooling

The old rule `scripts/ue/** => ue_code=true` was intentionally removed.

Most files under `scripts/ue/` are proof wrappers, authoring scripts, visual
capture helpers, profiling tools or editor orchestration. Changing those files
usually needs hosted CI/contract validation and, for Python files, Python
security/static checks. It does not prove that recompiling
`YetAnotherCyclingSimEditor` is useful evidence.

The automatic code-only Unreal lane is reserved for:

- compiled project/plugin source;
- `.uproject` / `.uplugin`;
- critical runtime/editor Config;
- the reusable automatic Unreal workflow itself;
- the exact build/provenance helpers used by that lane:
  - `scripts/ci/Invoke-YacsUnrealCi.ps1`;
  - `scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1`;
  - `scripts/ci/Resolve-YacsUnrealEngine.ps1`;
  - `scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1`;
  - `scripts/ci/Test-YacsCodeOnlyCheckout.ps1`;
  - `scripts/ue/Invoke-YacsProof.ps1`;
  - `scripts/ue/Preflight-YacsProof.ps1`.

A change to `.github/workflows/manual-unreal.yml` or a bounded proof wrapper is
CI/tooling work and does not automatically schedule the code build. Its own
contract tests and any explicit proof workflow remain responsible for its
behavior.

## Code-only Unreal contract

The reusable Unreal lane is intentionally source-only:

- `GIT_LFS_SKIP_SMUDGE=1`;
- checkout uses `lfs: false`;
- `Test-YacsCodeOnlyCheckout.ps1` requires tracked LFS assets to remain pointer files;
- only after that guard passes may the Editor build and scoped Automation run.

Heavy Unreal execution uses the repository-scoped `yacs-ue58` self-hosted
runner and must never depend on shipping the Engine through hosted CI
cache/workspace storage.

A C++ or build-contract change must not download project textures, maps, FBX
files, audio or other LFS payloads merely to prove that source code compiles and
the code-centric Automation suites pass.

## Lightweight asset validation

The asset lane does not start Unreal Engine and does not download LFS payloads.
For changed asset paths it validates Git attributes and pointer state. Required
binary UE/source-media extensions must stay in Git LFS. Deletions are valid and
are handled without requiring the removed payload.

Repository policy remains the global guard for maximum non-LFS blob size and
required LFS extensions.

## Full asset / release lanes

High-risk Stage 3G changes participate in normal PR CI through
`.github/workflows/reusable-stage3g-full.yml`. The classifier emits
`asset_full=true` only for the canonical Stage 3G environment, map, terrain
runtime, authoring/proof tooling and world-generation specification. Ordinary
asset changes still use only lightweight pointer validation.

The automatic Stage 3G lane runs only for same-repository PRs or trusted main
pushes. Fork PRs never receive self-hosted runner access; if such a PR requires
`asset_full=true`, the Aggregate gate fails closed because the heavy lane is
skipped.

Both modes materialize full LFS. When `stage3g_authoring=true`, the lane runs
deterministic legacy authoring followed by its final proof (Automation,
fresh-load persistence, Map Check, LFS integrity and legacy visual captures).
Otherwise CI passes `legacy_regression_only=true`: a real Editor build and one
fresh `CyclingStage3World.PrototypeTerrain` Automation test prove compatibility
without authoring, saving, Map Checking or rendering `L_CyclingTest`. The gate
checks exact-SHA receipts, the fresh singleton report and a clean checkout.
Neither mode admits the current Sa Calobra world; its saved/fresh-rendered
consumer requires its own proof and owner acceptance. Cleanup also checks host
ownership before releasing or deleting the runner worktree; a busy or unknown
host preserves that workspace and fails closed.

Release-oriented binary validation remains deliberately separate. The manual
trusted entrypoint is `.github/workflows/asset-full.yml`.

The normal Aggregate gate must never start a full asset/cook/package workload
only because a documentation, Python, CI or proof-tooling change was pushed.

## Ownership

- **Classifier:** which lanes are required and the machine-readable cost class.
- **Governance:** high-risk path and workflow policy.
- **Repository policy:** LFS and repository hygiene.
- **Security workflows:** dependency, Trivy and language-specific CodeQL.
- **Unreal code lane:** source/build-contract proof without assets.
- **Unreal tooling/proof workflows:** project-owned explicit evidence, not an
  automatic code-build trigger by directory name.
- **Full asset/release lane:** explicit heavy runtime proof.
- **Aggregate CI gate:** verifies the classifier decision was actually honored.

## Hosted policy and world configuration coverage

Non-documentation `worldgen/**` and `.gumball/**` changes also emit `ci=true`, so
configuration-only edits cannot bypass script tests. This does not set
`unreal_compile` or `ue_code`. Existing `asset_full` classification remains
unchanged. Scenario-specific performance requirements are evaluated separately
by the read-only world-proof admission job; see
[CI validation tiers](../CI_VALIDATION_TIERS.md#exact-world-performance-admission).
