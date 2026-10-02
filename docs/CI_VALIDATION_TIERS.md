# CI Validation Tiers

## Sa Calobra migration import checkpoint

The owner approved the six-step migration on 2026-10-02. During Draft PR #319,
the existing same-repository Unreal CI lane explicitly requests a native terrain
import through `region_terrain_import`. Admission is limited to PR #319 and its
approved `fix/sa-calobra-terrain-import` branch, with the normal same-repository
guard and exact caller SHA. Other PRs and main runs keep code-only behavior.
This temporary bootstrap does not change the default-branch Proof Broker trust
boundary, issue a `proof-m3-terrain` receipt or make SP638 a Spanish proof.

After the verified build/Automation checkpoint, the profile-selected Spanish source TIFF and shared `Content/**` startup assets
are materialized. Code-only Unreal Automation still runs before materialization.
The asset registry and prototype constructors cannot treat LFS pointers as UE
packages, even when the isolated target map uses engine-only shading. The source, topology, transforms and layers
are validated by the producer/importer. Import logs and manifests are uploaded
as `sa-calobra-import-<sha>-<attempt>`. Spanish source and generated assets are
retained outside the mutable worktree before cleanup. The same job captures terrain-only overview/near-ground PNGs through the existing
UE screenshot-task pattern, with an explicit neutral engine BasicShapeMaterial, no fog and no shadows.
The initial 05a7e92 capture exposed the default checker material; its metadata
claimed Lighting Only without reliable viewport evidence. Subsequent diagnostics
record the actual neutral material method instead of claiming that view mode.
A completed capture is not human visual acceptance or measured 1080p60 gameplay.
After successful import/capture, owner-approved Italy retirement inventories and
hash-checks exact named paths in old terrain worktrees/retention archives before
deleting their payloads. Its receipt reports reclaimed bytes; shared LFS caches,
Spanish assets, generic prototype assets and Git history remain untouched.
Visual/performance and road/gameplay acceptance remain separate and pending
until actually measured.
The same checkpoint prepares a 300 m official Ma-2141 alignment away from the
ambiguous loop. It retains original vertices, samples native height with an
explicit bilinear analysis interpretation, and leaves width, surface/access,
asphalt elevation, earthworks and route/physics admission unresolved. This is
source-to-DTM analysis evidence, not a BOB or ride PASS.

The same lane emits `ma2141-profile-candidate.json` before the unchanged contact
trial. This offline inference fits the existing 601 by 25 native-facet samples
and records full-width cut/fill and profile review triggers. `REVIEW_REQUIRED`
is an expected diagnostic outcome, never road acceptance; malformed inputs or
producer errors fail the job. It does not apply the candidate in Unreal. The
four existing captures continue to show the raw native-contact trial, not the
regularized candidate. The JSON is included in the existing artifact upload.

Retire this PR-specific bootstrap after a trusted region proof lane replaces it.

YACS uses staged validation so world/art iteration stays fast without weakening the merge gate.

Sa Calobra terrain preparation is covered by synthetic native-GeoTIFF tests in
the lightweight Python lane. Benchmark/profile/BOB policy/case-memory changes
require render classification without invalidating the C++ compile fingerprint.
The bounded manifest-driven import in Issue #318 still requires an exact-SHA
editor build/import and separate visual/performance acceptance; hosted Python
PASS does not close the terrain milestone. Existing broker `m3-terrain` remains
the legacy SP638 execution lane until its runner migration is separately proven.

## Tier 0 — static / lightweight on every PR update

Runs for draft and ready PRs as applicable:

- change classification;
- repository and governance policy;
- Python/C++ security lanes when their paths change;
- code-only Unreal build for C++ and explicitly build-affecting Unreal changes;
- lightweight asset/LFS-pointer validation for asset changes.

Draft PRs are the normal iteration mode for world-building work.

### Gumball CI Cost Governor routing

The classifier emits a machine-readable `ci_cost_class`:

- `light` — documentation-only work;
- `standard` — Python, ordinary CI/tooling, proof/editor tooling and regular
  asset validation;
- `heavy` — compiled/build-affecting Unreal changes or `asset_full` world
  changes.

`scripts/ue/**` is **not** an automatic code-build trigger. Most scripts in
that directory are authoring/proof/editor tooling and remain on hosted
CI/contract lanes unless the exact path is part of the automatic code-build
contract. The build-sensitive exceptions are documented in
[`ci/CHANGE_CLASSIFIER.md`](ci/CHANGE_CLASSIFIER.md).

Unknown paths inside runtime-sensitive `Source/`, `Config/`, `Plugins/`
or `Build/` fail closed to the heavy `ue_code` path. Ordinary unknown
repository paths remain visible as `unknown=true` and receive conservative
security/contract validation without automatically burning the Unreal runner.

### M3 Embark terrain proof sub-tiers

The dedicated Passo Giau Embark/PCGEx proof refines the central change
classification into three execution modes without weakening exact-SHA evidence:

- `cheap` — documentation, policy and contract-only changes run hosted
  classification/contract checks and do not reserve the Unreal runner;
- `render` — native-DTM preparation, bounded geometry/Python capture changes,
  proof-camera changes and other presentation inputs prepare current data and
  rerun author/render evidence; compilation may be skipped only on a verified
  exact compile-cache hit;
- `heavy` — compiled Unreal source, `.Build.cs` / `.Target.cs`,
  `.uproject`, the PCGEx build/bootstrap wrapper, shared build-environment
  resolver or proof workflow contract changed, so build execution is required.
  **Heavy does not mean cold.**

The compile fingerprint is SHA-256 over the pinned UE/PCGEx identity plus the
project descriptor, compiled source/build inputs and M3 build contract. The M3
runner then resolves one of three compile actions:

- **none / exact hit** — fingerprint, environment identity, PCGEx pin/checkout
  and expected project/plugin binaries match a previously green state; skip
  compilation and continue current-revision graph author/render proof;
- **warm** — build is required but UE/toolchain identity and the pinned PCGEx
  dependency remain compatible. Preserve project/plugin build state and let
  UnrealBuildTool determine the minimal outdated compile/link graph. A compile
  fingerprint mismatch, previous failed build or missing expected binary uses
  this path;
- **cold** — environment identity or PCGEx pin/checkout drifted, cache state is
  malformed/untrusted, or no usable state exists. Purge the incompatible build
  surfaces before rebuilding.

The legacy schema-1 M3 cache is migrated once through **warm** rather than being
trusted as an exact hit: the previous green binaries/intermediates are preserved,
but UBT must validate/rebuild them before schema-2 state with environment
identity can be recorded.

The persistent state is compile output only. Exact-SHA checkout, prepared
SP638/DTM inputs, graph execution, rider render, evidence upload and deviation
validation still run for the current revision when the proof mode requires
them. A fingerprint change therefore invalidates proof reuse but no longer
implies destructive cleanup by itself.

#### M3 admission and scheduling after #292

Cost classification is not permission to launch expensive work. Every scoped
non-main push runs hosted admission/classification/contracts only, including a
push classified as `render` or `heavy`. Main and Dependabot pushes remain outside
the dedicated automatic M3 workflow. The independent normal Unreal CI lane is
unchanged and still validates binary-affecting work when required.

Use `/gumball proof m3-terrain` for the full checkpoint. Use
`/gumball proof m3-h-focus` for the dedicated H focus/wide diagnostic without
deduplicating to an existing full-terrain receipt. The broker resolves one
same-repository PR HEAD, deduplicates requests and dispatches the trusted default-
branch workflow with `exact_sha` and `gumball_request_id`. Explicit manual
`workflow_dispatch` with those same inputs is the recovery fallback. Admission
rejects other repositories, unsupported events, malformed SHA and request IDs.
The target must be reachable from a branch fetched from the canonical repository.
Workflow-definition SHA and proof-target SHA are separate: every preparation,
checkout, author/render wrapper and proof receipt uses the validated target SHA.

An operator may additionally set `include_surface_isolation=true` on an explicit
manual M3 dispatch to append F/G, without replacing A-E/C3 or deviation. The
optional boolean defaults to false, so broker requests and ordinary iteration
retain their previous cost. F isolates the additional transient native spline
cut/fill without meshes; G isolates corridor meshes without that additional edit.
These controls preserve existing map layers, camera and input identity, and do
not imply visual acceptance. The receipt records the request. Before this new
workflow input is on main, dispatch the reviewed same-repository PR branch as
the documented recovery fallback, with its exact target SHA and a unique request
ID; keep admission, resource lock and compile fingerprint reuse intact.

An explicit request always runs the existing A-E/C3 and deviation bundle, even
when its most recent commit is docs-only. Compilation remains independently
subject to the verified `none`/`warm`/`cold` decision above. A static push does not
produce an accepted heavy-proof artifact.

Static workflow cancellation is scoped by branch and event. Explicit requests
use a separate request group and are not cancelled by later pushes. A separate
non-cancelling author-job concurrency group serializes the persistent PCGEx
worktree; `queue: max` retains up to GitHub's supported queue limit instead of
replacing the single pending author job. Temporary input-download directories
are namespaced by run and attempt. This lock is not a global multi-runner GPU
scheduler and does not change the independent Unreal CI worktree contract.

Only successful author/render **and** deviation validation publish
`proof-m3-terrain-<exact-sha>` for broker reuse. Partial diagnostics have different
names. The receipt distinguishes technical PASS from human visual acceptance,
which remains PENDING until the owner accepts the images.

This change does not claim prepared-DTM cache, single-Editor A-E/C3 execution or
unified full-world compile reuse. Those are separate measured optimization steps;
all six standalone captures and current preparation remain intact here.

### General Unreal STATIC / RUNTIME / COMPILE reuse

The normal code-only Unreal lane now separates binary work from runtime proof:

- **STATIC** — the current exact HEAD has the same compile and proof
  fingerprints as a previously green run. CI verifies the current checkout,
  installed UE build identity and expected project DLLs, then emits a fresh
  exact-head equivalence artifact without launching Unreal.
- **RUNTIME** — compiled inputs are unchanged but runtime-critical Config or
  the proof/orchestration contract changed. CI reuses verified DLLs and reruns
  scoped Automation with `-SkipBuild`.
- **COMPILE** — compiled project/plugin source, project/plugin descriptors,
  Build/Target rules or another binary-contract input changed, or verified
  binaries cannot be proven reusable. COMPILE then splits again:
  - **WARM COMPILE** preserves trusted project/plugin `Binaries` and
    `Intermediate` and lets UnrealBuildTool/UBA compute the minimal outdated
    action graph. Source/header/Build.cs/Target.cs/.uproject/.uplugin edits and
    a missing final DLL use this path when the engine/toolchain identity still
    matches.
  - **COLD COMPILE** purges project/plugin build outputs first. It is reserved
    for missing/malformed cache provenance or engine/toolchain drift.

The runner-local warm worktree is serialized by repository-wide Unreal CI
concurrency. Every run resets tracked files to the requested SHA and removes all
untracked/ignored residue except the explicit warm-state allow-list: project and
plugin `Binaries`, `Intermediate`, and `Saved/BuildCache/UnrealCi`. Diagnostic-only
exceptions preserve the exact canonical `Saved/Logs/YetAnotherCyclingSim.log`
and `Saved/RuntimeProof/CI/RegionTerrain/*/*.log` files. Windows may retain file
locks even for exited Unreal processes; these logs are neither build cache nor
reusable proof. The existing scoped process/lock guard still runs before cleanup.
Other generated files, including old JSON/PNG receipts, remain disposable.
Sa Calobra import/capture use per-run `-AbsLog` destinations and new evidence
directories; upload is restricted to the exact run ID and attempt. A failed
preparation cannot upload old-run diagnostic files under the new commit name.
This preserves locked diagnostics without suppressing other cleanup failures. The
code-only LFS contract and exact HEAD are then rechecked. Preserved outputs are
only candidates for reuse; they are never trusted without fingerprint and
environment checks. A compile-fingerprint mismatch is **not** cache corruption:
when engine/toolchain provenance still matches, the lane invalidates the green
stamp but keeps `Intermediate/Binaries` and performs a WARM COMPILE. Missing
final project DLLs are handled the same way because UBT can relink/rebuild them
from trusted intermediates. Only an untrusted cache state or environment drift
requests COLD purge. Before mutable COMPILE/RUNTIME work starts, the
corresponding previous green state is invalidated so cancellation or failure
cannot leave reusable proof behind.

The compile fingerprint covers the project descriptor, compiled project/plugin
inputs and the build/engine-selection orchestration used by the normal Unreal lane.
`scripts/ci/Resolve-YacsUnrealEngine.ps1` is the single engine-discovery authority
for both preflight/build and cache validation: it requires the `.uproject`
`EngineAssociation` and identities the resolved installation from its root plus
hashed `Build.version`, `Build.bat` and `UnrealEditor-Cmd.exe` evidence.
The cache resolver separately identities the active MSVC compiler/linker and
Windows resource tool. The resulting environment identity is the COLD/WARM
boundary: source/build-graph drift with the same environment is WARM; engine or
toolchain drift is COLD. The proof fingerprint extends the compile identity with
runtime-critical Config and the remaining code-only Unreal proof tooling.
Unknown or malformed state fails closed.

World/runtime cost is independent from compilation. A normal tree, house,
material or similar asset does not imply a C++ rebuild. A world change that
crosses an `asset_full` boundary is RUNTIME work at its configured readiness
checkpoint, and becomes COMPILE only when a binary-contract input also changed.

#### PR #290 validation evidence

The first live validation of this policy on `yacs-ue58` established the cost
difference directly:

- COLD seed: `compileKind=cold`, `reason=missing-cache-state`, purge enabled;
  UBT total execution **146.16 s**, including **135.59 s** in the local UBA
  executor.
- WARM build after a legitimate build-contract fingerprint change:
  `compileKind=warm`, `reason=compile-fingerprint-mismatch`, purge disabled;
  UBT total execution **1.54 s**, including **0.12 s** in local UBA, followed by
  26/26 Automation tests passing.
- RUNTIME after a proof-only fingerprint change: `mode=runtime`,
  `compileKind=none`, purge disabled and the build phase explicitly
  **skipped** before Automation.

These timings are evidence from that runner/revision, not a guaranteed future
performance budget. The architectural invariant is the cache decision and
fail-closed provenance, not a specific duration.

### Executable workflow lifecycle

The set of executable GitHub Actions workflows is governed by
[`ci/WORKFLOW_LIFECYCLE.md`](ci/WORKFLOW_LIFECYCLE.md) and the machine-readable
`.gumball/workflow-lifecycle.json` registry.

Historical Stage/R experiments remain valid evidence in PRs, docs and retained
scripts, but their branch-specific workflow files are not kept executable after
their branch/workstream is finished. Current M3 SP638/MASE proofs, explicit
performance/source-asset audits, manual recovery tools and broker targets remain
available.

The two legacy-named Passo Giau author workflows currently marked `UNKNOWN`
remain failed-baseline/recovery evidence after #288. Their final disposition
follows macro-terrain convergence; they do not regain production authority.

## Tier 1 — heavy Stage 3G proof at merge-candidate readiness

The full Stage 3G self-hosted proof is required only when both conditions are true:

1. the PR contains a path classified as `asset_full`; and
2. the PR is not a draft.

Transitioning a draft to **Ready for review** explicitly triggers CI, so the exact current head receives the full proof even when no new commit is pushed. Any later push to a non-draft PR re-runs the proof for the new exact head.

For `main` pushes, `asset_full` changes continue to run the full proof.

This means vegetation, material, water, lighting and other world-art iteration can be accumulated in a draft PR without paying for a full LFS checkout, authoring pass and three-point Stage 3G proof after every small commit.

## Gumball Proof Broker — explicit heavy proof intent

R4.1 and M3 heavyweight proof requests use the trusted Gumball v0.6 Proof Broker
instead of routine Actions-UI clicking.

Current configured proof commands:

```text
/gumball proof r4-1b3-geometry
/gumball proof m3-hairpin-corridor
/gumball proof m3-terrain
/gumball proof m3-h-focus
/gumball proof world-authoring-sp638
/gumball proof environment-performance
/gumball proof source-asset-audit
```

All six are explicit, heavy and non-automatic. Successful exact-revision
artifacts may be reused; failed runs require explicit `retry`.

The broker runs from trusted default-branch code, authorizes the requester,
resolves the open same-repository PR HEAD to an exact 40-character SHA, verifies
the allow-listed target workflow contract, then dispatches that workflow with
the exact SHA and a deterministic request id.

For one proof + PR + exact SHA:

- existing matching artifact -> reuse;
- successful matching run -> reuse;
- queued/running matching run -> do not duplicate;
- failed matching run -> explicit `retry` is required;
- explicit authorized request -> dispatch;
- non-critical automatic heavy request -> defer.

Each broker target keeps `workflow_dispatch` as a recovery fallback, but
broker-driven dispatch is the normal operator path. Heavy proof still runs only
when explicitly requested; this changes the control plane, not the evidence bar.

Mutating asset-author workflows, `asset-full.yml`, manual Unreal recovery,
runner-space recovery and Project/bootstrap operations are deliberately **not**
Proof Broker targets. Their purpose is mutation, release/full validation or
administrative recovery rather than reusable PR proof.

Explicit current exceptions are:

- `reusable-stage3g-full.yml` — merge-critical, classifier-driven exact-head
  proof; it belongs in the local Aggregate graph rather than explicit broker
  intent;
- `asset-full.yml` — release/full-asset entrypoint;
- `stage3g-forest-target-density-author.yml` — mutating author workflow owned
  by its still-live dedicated branch;
- `stage3g-forest-target-density-performance.yml` — paired with that live
  dedicated-branch workstream and still has its own automatic branch trigger;
- `passo-giau-r4-1-landscape-author.yml` and
  `passo-giau-r4-1-road-author.yml` — failed-baseline recovery after #288,
  tracked as `UNKNOWN` until macro-terrain convergence resolves disposition;
- `manual-unreal.yml`, `runner-space-recovery.yml`, Project bootstrap and
  remote-editor command — administrative/recovery controls, not reusable PR
  evidence.

## R4.1 prepared proof-suite reuse

For the bounded Stage 3G R4.1 terrain/road diagnostics, the canonical heavy manual lane uses **build once, boot once, prove many** inside one trusted runner job:

1. exact-SHA clean checkout once;
2. targeted materialization of the persisted Passo Giau map once;
3. one `YetAnotherCyclingSimEditor Win64 Development` build;
4. one `UnrealEditor.exe` process for the complete bounded proof bundle;
5. Geometry Script capability -> SP638 topology -> bounded hairpin -> rider-close local visual proof inside that same Editor process;
6. evidence-only validation after the Editor exits, with no second UE boot.

The prepared-workspace stamp is valid only inside that exact worktree/job and records the exact HEAD, map byte count and editor build identity. The in-editor dispatcher is fixed-scope and repository-owned; it accepts no arbitrary Python, console commands, map paths or asset paths. Every proof JSON is annotated with the exact HEAD and the single Editor process id. Existing child wrappers retain their standalone cold path, but the canonical suite invokes them in `-ValidateOnly` mode so their assertions are reused without reopening Unreal.

The single-Editor session is **job-local**, not a daemon and not a cross-commit warm cache. A new exact SHA still gets a fresh clean checkout and a fresh Editor boot. This preserves reproducibility while eliminating repeated startup/shutdown inside one proof run.

The R4.1 heavy visual suite remains an explicit `workflow_dispatch` checkpoint. Deterministic kernel/contract tests stay automatic. This reduces runner cost and visible Editor churn without weakening the later human visual gate, performance checkpoint or Stage 3G full closeout proof.

## Tier 2 — visual acceptance checkpoint

Visual History captures at 1200 / 4900 / 8000 m are produced when a world slice is a review candidate, not for every art edit.

The candidate must retain:

- BEFORE / NOW / AFTER provenance;
- exact SHA / PR / CI provenance;
- repository-retained images and SHA-256;
- AFTER = PENDING until visual acceptance.

## Tier 3 — performance / package / release evidence

Performance, package/cook and other long-running proofs run when their evidence is decision-relevant:

- before closing a performance-sensitive roadmap slice;
- before merge when the slice has an explicit performance budget;
- on `main` / release checkpoints;
- manually when investigating a regression.

Stage-specific authoring/performance workflows should default to `workflow_dispatch` or another explicit milestone trigger unless an automatic run is required to produce a deterministic generated asset.

## Fail-closed rule

Tiering changes *when* expensive proof runs, not *whether* it is required.

A draft PR cannot merge. A ready PR with `asset_full=true` cannot satisfy the aggregate gate unless the exact-head Stage 3G full proof succeeds. If more commits are pushed after review readiness, the exact-head heavy proof is required again.

Code-only Unreal validation remains independent from the Stage 3G full-LFS lane so C++ correctness can still fail fast without materializing the world asset set.

## World-stage operating model

For Stage 3G R4/R5 world-art work, one long-lived **Draft stage integration PR** is the normal iteration surface.

The lifecycle is:

1. **Iteration — lightweight**
   - add or tune vegetation, water, rocks, terrain dressing, materials, lighting, fog and similar world elements;
   - run static/contract/policy/LFS-pointer checks;
   - keep code-only Unreal validation for C++ and build-contract changes; keep ordinary proof/editor tooling on hosted CI/contract validation;
   - do not run the full map/world proof after every art commit.

2. **Owner visual acceptance — performance checkpoint**
   - when the owner accepts the candidate look, freeze that candidate SHA;
   - capture the stable 1200 / 4900 / 8000 m views and record Visual History NOW;
   - run the stage performance budget on that exact SHA;
   - if performance fails, optimize the accepted visual candidate rather than silently changing art direction.

3. **Stage closeout — full proof**
   - only when the stage is ready to close, mark the stage integration PR Ready for review;
   - run the exact-head full Unreal/Automation/full-LFS/Map Check/save-reopen/Stage 3G proof;
   - require the full proof before merge.

If the final full proof runs on the same tree that already passed the accepted performance checkpoint, performance does not need to be repeated merely because the full proof ran. A material visual/runtime change after the accepted performance checkpoint invalidates that checkpoint and requires a new one.

The intent is to make **world iteration cheap and stage acceptance strict**.

### Bounded traversal diagnostics (Issue #293)

Owner approval, 2026-10-01: use a light scout and a focused +/-2-second clip to
localize the current road/terrain defect instead of repeatedly producing long
rides. This is diagnostic M3 tooling, not a new world generator, gameplay camera,
physics replay or Performance Framework milestone.

`passo-giau-embark-terrain.yml` keeps its full A-E/C3 (optional F/G) path when
`ride_probe_mode=off` (the default and ordinary broker request). Explicit `light`
or `focus` requests use one allow-listed surface variant and one editor process.
Their artifacts are named `ride-probe-<run>-<attempt>` and MUST NOT satisfy the
`proof-m3-terrain-<sha>` broker receipt. Combining traversal with F/G isolation is
rejected before reserving the reference runner.

- **light:** 12 virtual seconds at 10 m/s; 25 native 960x540 screenshots at 2 Hz.
  The original native spline is sampled at 10 Hz, including +/-2-second margins
  (161 cheap route/height queries total). Landscape collision more than 0.20 m
  above the source road nominates an inspection location; this threshold is a
  diagnostic trigger, not a terrain-design or acceptance budget. Select at most
  one maximum-severity location and capture its full +/-2-second context.
- **focus:** request a known `ride_probe_station_m` directly, including a station
  chosen from a scout image. Capture 41 endpoint-inclusive 1920x1080 frames at
  10 Hz over a four-second virtual window; no new scout or whole-route run.
- Camera direction comes from the original local native tangent before slicing;
  eye height stays 160 cm and primary horizontal FOV stays 76 degrees. Optional
  `ride_probe_wide=true` adds a secondary 105-degree clip at identical positions,
  never replaces the primary camera or moves it away from an obstruction.
- Every frame has exact SHA context, virtual time, station, camera pose/FOV,
  visibility/geometry provenance, readiness status and a PNG digest. Native
  height-mip readiness is renewed per frame for visible macro terrain. The scene
  is prepared once; no new editor or mesh generation is launched per frame.
- Missing terrain queries remain `unmeasured_ground`. Collision is not rendered
  height: it can be stale, differ in LOD, or miss mesh ownership problems. No
  automatic finding means inspect the scout, NOT a clean-world verdict. This
  does not detect every wall, hole, material issue or temporal streaming defect.
- Existing 700 m prepared-corridor and local-surface bounds still apply. Requests
  outside the prepared corridor fail; they are never clamped, relocated or
  represented as full-area coverage. Normal terrain representative-location,
  regeneration and performance gates remain unchanged.

Each workflow attempt owns a new output directory under
`Saved/RuntimeProof/CI/M3/PCGExCorridor/<run_id>-<run_attempt>/`, resolved by
`YACS_M3_EVIDENCE_ROOT`. Authoring, captures and uploads use only that directory;
an existing directory for the same attempt fails closed. Old runs and their
backup logs are never merged into the current artifact. No history or compile
cache is deleted: `Saved/BuildCache/PCGEx`, Binaries, Intermediate and the pinned
plugin remain under the independent compile-reuse policy. Deviation validation
requires exactly one source and one executed graph instead of choosing the first
recursive match. Diagnostic media still cannot issue a full terrain receipt.
The broker contract tests the guard on the actual reusable upload step, including
the explicit exclusion of light/focus runs.

The ephemeral Ubuntu 24.04 media stage uses the already-used `Pillow==11.3.0`
and installs distro `ffmpeg=7:6.1.1-3ubuntu5` from the signed Ubuntu archive only
for an explicit diagnostic request. It verifies the package version and records
FFmpeg/ffprobe versions/configuration with the output. It
validates frame identities/counts/hashes/dimensions and fully decodes PNGs, then
produces labelled contact sheets, H.264 MP4, small GIF and `frames.csv`.
PNG + `ride-probe.json` remain primary evidence. GIF palettes and MP4 compression
are not geometry truth. 41 samples span four seconds; video holds the last sample
for another 0.1 s. Missing codecs fail the media step while raw author artifacts
remain available. No binary is downloaded or installed on the owner's machine.

These are settled deterministic camera samples, NOT real-time footage. Capture
wall time and encoded 10 FPS do not measure runtime FPS or prove streaming under
motion. Existing Frame/Game/Draw/RHI/GPU sampling and performance gates remain
separate. `package_ride_probe.py --performance-csv ... --performance-context ...`
can produce station locators only with matching exact SHA and explicit
`route_id=SP638-presentation`, plus a positive caller-owned `frame_threshold_ms`.
It uses existing CSV `distance_m` and `frame_ms`; a sector-local `rel_s` is NOT
mapped to the new clip clock. Legacy Alpine Journey benchmark data is rejected
rather than silently overlaid on Passo Giau.

Tools-first review: the existing production-reference dossier's Embark lesson is
bounded high-level reproducible operations, not a public Embark video-capture
recipe. Reuse Epic's existing screenshot task, native spline and loading barrier;
no new runtime plugin or claimed Embark/PCGEx upstream feature. Primary API/tool
references reviewed for the adapter and derived-media commands:

- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary
- https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/Actor
- https://ffmpeg.org/ffmpeg.html

The exact UE runner proof, not the API reference alone, establishes compatibility.

## Byte-pinned GIS responses on persistent Windows worktrees

Raw external source response JSON uses path-scoped `-text` attributes so its
SHA-256 describes original bytes on all operating systems. A persistent checkout
can still contain CRLF bytes from an earlier revision. Before editor startup, the
region bootstrap reads each allow-listed response directly from the exact HEAD
Git blob, verifies its pinned SHA-256, and restores those verified bytes. It then
checks the on-disk hash. A mismatch fails before expensive import/capture. This
does not normalize or reinterpret external data to make a hash check pass.


### BOB native builder lesson

The Sa Calobra lane additionally prepares the bounded experimental BOB recipe
and executes it after the original four contact/terrain captures. Two additional
fixed-camera before/after captures make six total. The recipe and native lesson
receipt are uploaded with the exact current run. Trial status in the lesson
receipt is independent of technical screenshot success; no production map is
saved and no learning case is automatically admitted. WORLD_BUILDING_BIBLE owns
the recipe limits, native API decision and remaining acceptance requirements.

The first six-image archive exceeded the connector's 32 MiB local-transfer limit
(33,963,108 bytes at run 36994612419). Lesson PNGs now live in a separate
`bob-build-lesson-<sha>-<attempt>` artifact with their recipe and receipt;
the main import artifact retains the other four PNGs and all JSON/log evidence.
The small lesson receipt is also printed in the capture job log. Both artifacts
remain scoped to the exact run/attempt; this packaging change does not alter
image resolution, sampling or acceptance thresholds.
