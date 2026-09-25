# CircleCI Windows UE Phase B

Issue: #95

## Goal

Use the home PC only once to seed a private CircleCI cache with the local UE 5.8
Launcher installation, then run normal YACS Windows build + Automation canaries on
CircleCI hosted Windows.

Nothing in this phase is a merge gate. All expensive workflows are disabled by default.

## Why this design

The measured hosted Windows executor has:

- Windows Server 2022;
- 4 logical CPUs;
- 16 GB RAM;
- 199.89 GB total disk;
- only 70.61 GB free after the base image;
- VS2022 Build Tools + VC tools;
- no UE 5.8.

A full UE source build is therefore intentionally out of scope. The seed path reuses
the already licensed local UE 5.8 installation and keeps it inside CircleCI cache
storage for this project. Do not publish the archive as a GitHub release or public
artifact.

## Pipeline parameters

All default to safe/off values.

### Measure-only probe

```text
windows_probe = true
```

### One-time cache seed

```text
ue_cache_seed = true
ue_seed_resource_class = karnalooch/yacs-ue58-seed
ue_cache_key = yacs-ue58-win64-v1
```

The seed job is self-hosted. It runs on the home PC, packages the local UE 5.8
installation, and saves only these cache payloads:

- `Saved/RuntimeProof/CI/UE58Seed/ue58-win64.tar.gz`
- `Saved/RuntimeProof/CI/UE58Seed/ue58-win64-manifest.json`

The cache key is immutable. Bump the version suffix when intentionally replacing the
engine package.

### Hosted Windows UE canary

```text
ue_canary = true
ue_cache_key = yacs-ue58-win64-v1
```

The hosted job restores the cache, checks SHA256 and available disk, expands UE to
`C:\UE_5.8`, deletes the compressed archive to free disk, then executes:

```powershell
pwsh ./scripts/ci/Invoke-YacsUnrealCi.ps1 -ExpectedHead $env:CIRCLE_SHA1
```

That runs the real YACS Editor build and scoped Unreal Automation contract already
used by #24.

## UE seed package policy

`Prepare-YacsUe58Seed.ps1` defaults to measurement-only mode.

Run locally first:

```powershell
pwsh ./scripts/ci/Prepare-YacsUe58Seed.ps1
```

It records the current UE install size and a conservative estimate after excluding only:

- `Engine/DerivedDataCache`;
- `Engine/Intermediate`;
- `Engine/Saved`;
- `FeaturePacks`;
- `Samples`;
- `Templates`.

It deliberately keeps Engine plugins, source, shaders, content and Win64 binaries because
YACS currently enables `ModelingToolsEditorMode` and `PythonScriptPlugin`, and the
hosted build must not silently lose required engine components.

The default safety limit is 45 GiB uncompressed. If the estimate is larger, the script
fails before creating an archive. Review the measurements before pruning anything else.

Only after the measurement is acceptable:

```powershell
pwsh ./scripts/ci/Prepare-YacsUe58Seed.ps1 -CreateArchive
```

## One-time CircleCI self-hosted seed runner

CircleCI machine runner execution itself does not consume hosted compute credits.
Create one resource class in CircleCI:

```text
karnalooch/yacs-ue58-seed
```

Install/start the Windows machine runner on the home PC only for the cache-seed job.
Do not commit the runner resource-class token.

Once the runner is online, trigger a pipeline from `main` with:

```text
ue_cache_seed = true
```

After a successful seed, stop the runner. Normal `ue_canary=true` executions use the
hosted Windows VM and no longer require the home PC.

## Disk fail-closed rule

Before extraction, `Restore-YacsUe58Seed.ps1` requires enough free disk for:

```text
compressed archive + estimated extracted engine + 8 GiB safety
```

The restore also verifies the archive SHA256 and UE 5.8 version. A cache miss, corrupt
archive, version mismatch, or insufficient disk is a hard failure.

## Slack notifications

For CircleCI Cloud, use the native CircleCI Slack integration instead of adding the
Slack orb or storing another Slack token in the repository.

Recommended target channel:

```text
#yacs-dev
```

In CircleCI:

1. open Organization/Project Settings;
2. open **Slack Notifications**;
3. connect the Slack workspace if it is not connected yet;
4. add `#yacs-dev`;
5. enable workflow failure and success notifications for the YACS project.

This keeps Slack credentials outside `.circleci/config.yml`.

## Cost guard

- `windows_probe`, `ue_cache_seed`, and `ue_canary` all default to `false`;
- no every-push CircleCI Windows build;
- seed is intended to happen once per UE package version;
- hosted Windows uses `windows.medium`;
- cache/storage size is measured before saving;
- do not bump cache versions casually because old immutable caches consume storage until
  retention cleanup.

## Phase B acceptance

- [ ] measure local UE 5.8 package size;
- [ ] package stays within the configured safety limit or exclusions are reviewed;
- [ ] one self-hosted seed job saves the cache;
- [ ] hosted canary restores UE successfully;
- [ ] real YACS Editor build passes;
- [ ] scoped Unreal Automation passes and discovers tests;
- [ ] proof artifacts are available;
- [ ] CircleCI Slack notifications reach `#yacs-dev`;
- [ ] recurring hosted run time and credit usage are recorded.
