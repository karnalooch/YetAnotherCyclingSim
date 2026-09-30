# Phase 1 — manual Unreal runner

Issue: #24

This is the operator guide for the first real Unreal Engine GitHub Actions runner.
Phase 1 is intentionally manual and trusted-only.

## Proven baseline — 2026-09-26

The generic runner/build/fail-closed contract is proven on the real home runner:

- runner: `yacs-home-ue58` / label `yacs-ue58`;
- runner root: `D:\actions-runner-yacs`;
- workflow run: `36240146312`;
- exact main SHA: `9826b0f82d2a895a0a5d6fbf358aac162e199aa5`;
- UE: `5.8.2`;
- normal code-only canary: **13 discovered / 13 passed / 0 failed / 0 errors**;
- intentional-red: expected non-zero failure with **0 discovered tests**, verified fail-closed;
- proof artifact upload: green;
- workspace cleanup: green.

The temporary one-shot workflow used to obtain this baseline was retired after
the proof. The durable Phase 1 entrypoint remains `Manual Unreal proof`.

Stage 3G authoring/final-proof mechanics are now proven by PR #155 / workflow
run `36258791131`. The reopened #80 still requires real source-asset import,
PCG/environment integration and visual acceptance; that is product work using the
proven runner contract, not a missing runner capability.

## What lands in Phase 1

After merge, GitHub Actions exposes:

**Actions -> Manual Unreal proof -> Run workflow**

The workflow definition must be selected from `main`.

Trusted targets:

- `main` for the normal build/Automation canary;
- `feat/stage3g-reference-environment` for Stage 3G authoring/final proof.

Available modes:

- `canary` — real Editor build + scoped Automation;
- `stage3g-author` — author materials/world/map and return changed UE source assets as Actions artifacts;
- `stage3g-proof` — run the final non-mutating Stage 3G acceptance proof;
- `intentional-red` — deliberately request a nonexistent Automation filter to prove zero-test discovery fails closed.

The workflow resolves the selected branch through the GitHub API and checks out the exact resolved SHA. An optional `expected_sha` input can pin the run more tightly and fails if the branch moved.

## One-time home-PC registration

In GitHub open:

`YetAnotherCyclingSim -> Settings -> Actions -> Runners -> New self-hosted runner`

Choose:

- **Windows**
- **x64**

Use a dedicated folder, for example:

```powershell
mkdir D:\actions-runner-yacs
cd D:\actions-runner-yacs
```

Then use the download/extract commands GitHub shows on that page. GitHub also shows a short-lived registration command similar to:

```powershell
.\config.cmd --url <repo-url> --token <one-time-token>
```

Do not copy that registration token into chat, Issues, docs or logs.

When configuring, use:

- name: `yacs-home-ue58`
- custom label: `yacs-ue58`
- work folder: default `_work` is fine.

If GitHub's generated `config.cmd` command does not include the custom label, append:

```text
--labels yacs-ue58
```

For Phase 1, run interactively first:

```powershell
.\run.cmd
```

Leave that terminal open while a canary executes. Do not install it as a privileged always-on service yet.

## Host prerequisites

The runner host must provide:

- Windows x64;
- Unreal Engine 5.8.x;
- PowerShell 7 / `pwsh`;
- Git;
- Git LFS;
- enough free disk/RAM for a clean Editor build and Automation.

Current UE discovery already supports the home/reference installation pattern, including `D:\Epic Games\UE_5.8`.

## First canary

**Status: proven** by workflow run `36240146312` on SHA
`9826b0f82d2a895a0a5d6fbf358aac162e199aa5`.

For future diagnostic reruns, with `run.cmd` waiting for work:

1. open **Actions -> Manual Unreal proof**;
2. click **Run workflow**;
3. keep **Use workflow from: main**;
4. choose mode `canary`;
5. choose target branch `main`;
6. leave `expected_sha` empty for the first run;
7. run it.

The job should be picked up by `yacs-home-ue58`.

Pass requires:

- trusted branch resolution succeeds;
- code-only checkout keeps LFS payloads unmaterialized;
- `Test-YacsCodeOnlyCheckout.ps1` passes;
- UE 5.8.x is discovered;
- `YetAnotherCyclingSimEditor Win64 Development` builds;
- scoped Automation discovers tests and passes;
- proof JSON/logs are uploaded;
- workspace cleanup is green.

## Intentional-red canary

After the normal canary passes, run mode `intentional-red` against `main`.

That run is expected to finish **red** because its Automation filter is deliberately nonexistent. The useful evidence is that it reaches the zero-discovery guard and fails there rather than silently succeeding.

## Stage 3G authoring

**Runner capability: proven.** PR #155 demonstrated this path. For the reopened
#80 visual/asset recovery, reuse the same mode/contract rather than inventing a
new authoring path.

For manual diagnostics or controlled authoring, use:

- mode: `stage3g-author`;
- target: `feat/stage3g-reference-environment`.

Stage3G modes intentionally use a full LFS checkout. The workflow uploads the
generated Stage 3G directory, map and authoring logs as artifacts. It
deliberately does not push or commit anything.

After review, those binary source assets are committed through normal Git LFS rules on the Stage 3G branch.

## Stage 3G final proof

**Proof mechanism: proven** by workflow run `36258791131`. A green technical
proof does not waive visual review: after real Stage 3G assets/PCG outputs are
committed, run the final proof again against that exact SHA and review the three
canonical captures against #80 acceptance criteria.

Once authored assets are committed and the branch has its final SHA:

- mode: `stage3g-proof`;
- target: `feat/stage3g-reference-environment`;
- optionally paste that full SHA into `expected_sha`.

This produces the real build/Automation/reload/Map Check/LFS/visual proof.

## Security boundaries

Phase 1 deliberately has no automatic PR trigger and is not part of `Aggregate CI gate`.

The workflow:

- can only be dispatched manually;
- must use its workflow definition from `main`;
- accepts only a hardcoded trusted branch allowlist;
- resolves target SHA before checkout;
- uses `persist-credentials: false`;
- requests only `contents: read`;
- never commits/pushes generated assets;
- uploads authoring results as artifacts;
- always resets/cleans the self-hosted workspace.

Do not add `pull_request_target` or a generic public-PR trigger.
