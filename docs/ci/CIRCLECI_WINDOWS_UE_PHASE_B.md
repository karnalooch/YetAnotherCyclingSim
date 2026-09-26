# CircleCI Windows UE Phase B

Issue: #95

## Status

**RETIRED: hosted UE seed transport**

The original Phase B design packaged the local UE 5.8 installation, uploaded the
archive through a CircleCI workspace, republished it into CircleCI cache storage,
then restored it on a hosted Windows executor.

That design is no longer used.

The measured UE archive is roughly 10 GiB compressed. Persisting it first as a
workspace and then again as a cache creates unnecessary CircleCI storage and
network usage. The hosted canary was only a proof-of-concept and was never part
of the required Aggregate CI gate, so paying this storage cost is not justified.

## Current CircleCI design

CircleCI keeps only two explicit opt-in paths:

### Lightweight Windows probe

```text
windows_probe = true
```

This uses CircleCI hosted Windows to validate the executor environment. It does
not download Unreal Engine and stores only small probe artifacts.

### Local Unreal canary

```text
ue_local_canary = true
```

This runs on the repository-scoped self-hosted Windows resource class:

```text
karnalooch/yacs-ue58-seed
```

The resource-class name is retained for compatibility with the registered
CircleCI runner, even though the job no longer seeds CircleCI storage.

The local canary:

- runs only from `main`;
- uses the UE 5.8 installation already present on the runner host;
- keeps `GIT_LFS_SKIP_SMUDGE=1` so project LFS payloads remain unmaterialized;
- executes `Test-YacsCodeOnlyCheckout.ps1`;
- executes `Invoke-YacsUnrealCi.ps1 -ExpectedHead $env:CIRCLE_SHA1`;
- emits phase telemetry and heartbeats;
- uploads only concise runtime proof/log artifacts.

## Storage circuit breaker

The active CircleCI configuration must not contain any UE use of:

- `persist_to_workspace`;
- `attach_workspace`;
- `save_cache`;
- `restore_cache`;
- `ue58-win64.zip`;
- `C:\YacsUe58Seed`.

`scripts/ci/test_circleci_windows_phase_b.py` enforces this contract.

The old packaging helpers remain in the repository as manual/archive utilities:

- `Prepare-YacsUe58Seed.ps1`;
- `Restore-YacsUe58Seed.ps1`;
- `Test-YacsUe58SeedPayload.ps1`.

They are not called from the active CircleCI workflow and must not be reconnected
to CircleCI storage without a new explicit design review.

## Trust boundary

The self-hosted runner remains Phase 1 manual/trusted-only.

The local canary:

- defaults to off;
- has no PR trigger;
- is not part of Aggregate CI;
- only accepts `main`;
- never runs untrusted fork PR code;
- requires the dedicated local runner to be online.

Promotion to automatic PR gating belongs to the Phase 2/3 self-hosted rollout and
requires the normal and intentional-red canaries plus the documented outage policy.

## Cost guard

The intended steady state is:

- UE installation: local runner disk only;
- CircleCI workspace: no UE payload;
- CircleCI cache: no UE payload;
- CircleCI artifacts: logs, JSON summaries and screenshots only;
- hosted Windows: lightweight probe only.

Existing old workspaces/caches may remain billable until their configured retention
expires. Reducing retention in CircleCI Plan / Usage Controls accelerates cleanup.

## Acceptance

- [x] original hosted-cache experiment measured the UE payload;
- [x] storage-heavy workspace/cache transport retired;
- [x] storage-free local-canary contract enforced in CI tests;
- [ ] normal local UE canary proven green;
- [ ] intentional-red local/self-hosted canary proven fail-closed;
- [ ] Phase 2/3 outage policy accepted before any automatic PR gate.
