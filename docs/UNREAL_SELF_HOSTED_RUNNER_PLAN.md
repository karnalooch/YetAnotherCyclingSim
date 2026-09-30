# Unreal self-hosted runner rollout plan

**Issue:** #24  
**First canary:** #80 / Stage 3G Reference Environment Pass  
**Host:** home/reference Windows PC with Unreal Engine 5.8.x  
**Current target:** Phase 1 proof complete; Stage 3G asset/visual recovery active; Phase 2 operational readiness pending

## Why now

Stage 3G already needs exactly the work that hosted GitHub runners cannot prove
for this project: a real UE 5.8 Editor build, Unreal Automation, editor
authoring, map save/reload, Map Check and rendered 1920×1080 captures.

Doing the first self-hosted runner now converts that repeated home-PC validation
from a manual terminal ritual into a reproducible GitHub workflow. The same
infrastructure can later serve route/world work, assets, animation, PCG,
performance proofs and release validation.

The rollout is intentionally staged because the repository is public. The home
PC must never become an executor for arbitrary fork PR code.

## Non-negotiable security invariants

1. The home runner uses a dedicated repository/workload label: `yacs-ue58`.
2. Phase 1 uses only `workflow_dispatch`; no generic `pull_request` trigger.
3. The executed revision is an exact trusted commit SHA and the checkout verifies
   that SHA before any project script runs.
4. The runner account contains no unrelated personal secrets, browser sessions,
   SSH keys or cloud credentials.
5. Workflow permissions remain read-only unless a later phase explicitly proves
   that a narrowly scoped write permission is necessary.
6. Stage 3G generated `.uasset`/`.umap` files are uploaded as artifacts in
   Phase 1 rather than granting the runner repository write access to commit them.
7. Workspace cleanup runs even after failure.
8. A fork PR must never be able to schedule the self-hosted UE job.
9. Do not use `pull_request_target` to execute PR-controlled code.
10. Unreal CI does not replace hosted governance/security checks; it complements
    them.

## Phase 0 — contract preparation

**Status:** merged to `main` via PR #87.

Deliverables:

- local fail-closed entry point for real UE build + Automation;
- reusable self-hosted workflow contract;
- dedicated `yacs-ue58` runner label;
- exact-SHA verification;
- short-retention proof artifacts;
- unconditional workspace cleanup;
- public-repository trust policy.

Phase 0 is not sufficient to enable the lane. It exists so registration and
canary work have a reviewed contract to run.

## Phase 1 — manual trusted runner

**Current status:** generic runner/build/fail-closed canary proven; Stage 3G
authoring/final-proof mechanics proven by PR #155 / run `36258791131`.
Stage 3G product acceptance remains open because the required progressive
source-asset/PCG visual baseline was not delivered.

### 1. Prepare the home PC

- use the reference Windows machine with UE 5.8.x;
- ensure Git, Git LFS and PowerShell 7 are available;
- create/use a dedicated Windows account for the runner when practical;
- do not expose personal development tokens to the runner process;
- ensure enough free disk space for clean UBT/Automation work;
- register the runner at repository scope;
- add custom label `yacs-ue58`;
- initially run interactively rather than as a privileged always-on service if
  that makes auditing easier.

### 2. Add the manual GitHub workflow

**Repository-side implementation:** `\.github/workflows/manual-unreal.yml` (Phase 1 delivery under #24). Operator instructions: [`UNREAL_RUNNER_PHASE1.md`](UNREAL_RUNNER_PHASE1.md).

The Phase 1 entrypoint is a dedicated `workflow_dispatch` workflow on the
default branch. It accepts or resolves a trusted target SHA and schedules only:

```text
[self-hosted, yacs-ue58]
```

The job must:

1. checkout with Git LFS and no persisted credentials;
2. verify `git rev-parse HEAD` equals the requested SHA;
3. print runner/UE provenance;
4. run the requested YACS UE script;
5. upload logs, JSON summaries and screenshots;
6. always clean the workspace.

No Phase 1 workflow is required by `Aggregate CI gate`.

### 3. Canary A — runner/build contract

Run the real Unreal CI entry point against a trusted commit.

Pass criteria:

- UE 5.8.x detected;
- `YetAnotherCyclingSimEditor Win64 Development` builds;
- scoped `CyclingSession + CyclingPhysics + CyclingInput` Automation discovers
  tests and passes;
- zero-test discovery fails closed;
- proof summary is uploaded as an Actions artifact;
- workspace is clean after the run.

### Proven generic runner baseline — 2026-09-26

Canonical proof:

- workflow run: `36240146312`;
- exact main SHA: `9826b0f82d2a895a0a5d6fbf358aac162e199aa5`;
- runner: `yacs-home-ue58`, label `yacs-ue58`;
- runner root: `D:\actions-runner-yacs`;
- Unreal Engine: `5.8.2`;
- normal code-only canary: **13 discovered / 13 passed / 0 failed / 0 errors**;
- intentional-red: expected failure with **0 discovered tests**, verified fail-closed;
- concise proof artifact uploaded successfully;
- workspace cleanup passed.

The final successful proof used the resource-conservative self-hosted UBT profile
(UBA disabled, two parallel actions) after an earlier run exposed Windows commit/pagefile
pressure. The temporary one-shot workflow and sentinel are retired after this proof.
Permanent diagnostics continue through `Manual Unreal proof`.

### 4. Canary B — Stage 3G authoring

Use #80 as the first editor-authoring workload.

The manual Stage 3G authoring run should execute:

```text
Invoke-YacsStage3GAuthoring.ps1
```

Expected outputs include:

- Stage 3G material `.uasset` files;
- updated `L_CyclingTest.umap`;
- authoring logs and deterministic instance counts.

In Phase 1 the runner **does not push or commit** these files. The changed binary
source assets are uploaded as a workflow artifact for review. After review they
are committed on the Stage 3G branch through normal Git LFS rules.

### 5. Canary C — Stage 3G final proof

After the authored source assets are committed and a final SHA exists, run:

```text
Invoke-YacsStage3GProof.ps1
```

Pass requires:

- Editor build;
- Stage 2/3 Automation including `CyclingStage3World` and
  `CyclingStage3FullRoute`;
- fresh-process map/world reload verification;
- Map Check with zero errors;
- `git lfs fsck`;
- rendered AFTER captures at 1200 m, 4900 m and 8000 m;
- uploaded proof summary/logs/screenshots.

### 6. Intentional-red canary

Before expanding automation, prove fail-closed behavior using a temporary trusted
canary branch or other controlled failure.

Examples:

- deliberately wrong expected SHA;
- deliberately impossible test filter producing zero discovered tests;
- a temporary intentionally failing canary test.

The failure must be demonstrated without weakening production tests or leaving
the repository in a broken state.

## Phase 1 acceptance gate

Phase 1 is complete when all of the following are true:

- [x] repository-scoped runner registered and online with `yacs-ue58`;
- [x] manual `workflow_dispatch` is merged to the default branch and visible in Actions;
- [x] exact-SHA checkout verification proven;
- [x] real UE build + Automation canary green;
- [x] Stage 3G authoring/final-validation canary proven on the trusted runner — PR #155 / run `36258791131`;
- [x] Stage 3G final proof green on an exact committed SHA, including Automation/Map Check/LFS/captures/cleanup;
- [ ] reopened #80 rerun after real source assets + PCG/environment baseline are integrated and visually accepted;
- [x] intentional-red canary fails as expected;
- [x] no repository write credential was needed by the runner;
- [x] workspace cleanup verified after success and failure.

## Phase 2 — trusted automatic execution

**Phase 1 technical proof is complete.** Phase 2 still requires the operational
readiness gate below. The narrow trusted Stage 3G `asset_full` lane already
demonstrates same-repository automatic execution; do not generalize that trust
surface to arbitrary C++/PR workloads until the remaining safeguards are met.

### Phase 2 readiness gate — unattended runner startup

Before any trusted automatic UE trigger is enabled, make the home runner operationally
independent from an open PowerShell window.

Target setup:

- run the GitHub runner from Windows Task Scheduler rather than relying on manual
  `run.cmd`;
- use a dedicated local Windows account for the runner when practical;
- start at boot/logon with the runner rooted on `D:\actions-runner-yacs`;
- keep the repository-scoped `yacs-ue58` label and existing trust restrictions;
- do not make a classic Windows service the default for visual/GPU workloads
  unless a separate proof demonstrates that the required UE workload is compatible
  with that execution mode.

Required reboot proof before Phase 2 is considered ready:

1. restart the Windows host;
2. do not manually start `run.cmd`;
3. confirm the runner returns online automatically;
4. run a trusted diagnostic/canary job;
5. confirm Editor build and Automation remain green;
6. confirm at least one interactive-session/GPU-sensitive proof used by YACS
   (for example a visual capture workload) still works;
7. confirm workspace cleanup and runner recovery after failure.

Phase 1 manual execution and Stage 3G do **not** wait for this milestone. This becomes
mandatory only when GitHub is expected to schedule trusted UE jobs automatically.

Possible next step:

- automatically run the UE lane only for trusted same-repository branches;
- explicitly prevent fork PR revisions from scheduling the runner;
- keep a manual dispatch path for diagnostics;
- decide whether generated source assets remain artifact-only or whether a
  narrowly scoped GitHub App should create/update a dedicated branch.

Phase 2 still does not automatically make Unreal CI a required merge gate.

## Phase 3 — merge-gate integration

Start only after:

- Phase 1/2 have multiple stable real runs;
- #22 branch protection is enabled and verified;
- success and intentional failure paths are proven.

Then:

1. call the reusable Unreal workflow from normal trusted CI;
2. include the Unreal result in caller-local `Aggregate CI gate`;
3. require exact `success`;
4. ensure skipped/unavailable UE execution cannot accidentally count as green;
5. document outage/break-glass policy;
6. keep untrusted fork code off the self-hosted host.

At this point #24 can approach completion.

## Relationship to #22

#24 and #22 are independent but converge before the Unreal lane becomes a
required merge gate.

- #24 proves real UE execution.
- #22 protects `main` and makes required checks non-bypassable in normal work.

Phase 1 #24 may proceed while #22 is still open because it is manual and not a
merge requirement. Phase 3 must not be treated as complete until #22 is also
verified.

## Cost and operational policy

The self-hosted runner uses the existing home PC, so the primary costs are local
electricity, disk usage and machine time rather than hosted Windows minutes.

Keep it simple:

- one YACS UE runner;
- no autoscaling;
- no permanent fleet;
- no broad secrets;
- short artifact retention;
- one workflow at a time;
- add caching only after measuring build time and disk pressure.

The purpose is reproducible validation, not building a general CI platform.
