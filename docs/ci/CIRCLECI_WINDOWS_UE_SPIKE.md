# CircleCI Windows UE spike

Issue: #95

## Purpose

This spike checks whether CircleCI's hosted Windows VM is a practical free/low-cost
execution environment for YACS Windows CI before we spend time bootstrapping Unreal
Engine 5.8.

Phase A is deliberately tiny: it measures the actual Windows machine and toolchain.
It does **not** install or build Unreal Engine.

## Why this executor

CircleCI documents `windows.medium` as 4 vCPU / 16 GB RAM / 200 GB disk on Cloud.
The spike uses:

```yaml
resource_class: windows.medium
machine:
  image: windows-server-2022-gui:current
```

The 200 GB disk is the main reason this is worth testing for Unreal Engine.

## Cost guard

The CircleCI pipeline parameter `windows_probe` defaults to `false`.

That means merely connecting the repository to CircleCI does not spend Windows credits
on this spike. Run it only when explicitly requested with:

```text
windows_probe = true
```

Do not convert this spike to an every-push workflow.

## One-time CircleCI setup

1. Sign in to CircleCI with GitHub.
2. Connect/follow `karnalooch/YetAnotherCyclingSim`.
3. Let CircleCI use the checked-in `.circleci/config.yml`.
4. Trigger a new pipeline and set pipeline parameter `windows_probe` to `true`.
5. Open the `windows-probe` job and download the `circleci-windows-probe` artifact.

No Epic credential is required for Phase A.

## Evidence collected

The job writes:

- `windows_probe.json`;
- `windows_probe.txt`.

It records:

- Windows version;
- CPU/logical CPU count;
- RAM;
- disk total/free space;
- Git;
- Git LFS;
- PowerShell 7;
- CMake/Ninja;
- Visual Studio/MSVC detection;
- whether a known UE 5.8 installation already exists.

Phase A fails if Git, Git LFS or Visual Studio C++ tools are missing.

## Phase B decision

If Phase A is green, evaluate UE delivery in this order:

1. restore a lawful reproducible UE 5.8 Installed Build from a private cache/source;
2. generate an Installed Build once, then cache it if storage/time economics are sane;
3. compile UE from source only if measured credits and wall time still make sense.

Do not use unofficial public Windows UE binaries with unclear provenance/licensing.

Current CircleCI docs state that caches do not have a fixed object-size limit, but the
free plan's storage allowance still matters. Therefore a 40–80+ GB UE cache may be
technically possible yet economically useless; measure before committing to it.
