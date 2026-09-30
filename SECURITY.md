# Security Policy

## Supported branch

YetAnotherCyclingSim is pre-MVP. Security fixes are supported on the current
`main` branch only.

## Reporting a vulnerability

Prefer GitHub's private vulnerability reporting / Security tab when it is
available for this repository. Do not publish exploit details, credentials,
private keys, personal data, or a working proof of concept in a public issue.

If private reporting is unavailable, open a minimal public issue that states
only that a security report needs a private channel; omit sensitive technical
details until a private channel is established.

## Repository security baseline

Pull requests are expected to pass the exact `Aggregate CI gate`. The baseline
includes repository/LFS policy, deterministic Python reference-model tests,
dependency review on pull requests, CodeQL for Python and C/C++, and Trivy
filesystem scanning.

Unreal Engine build and automation tests require a runner with an installed,
licensed UE toolchain and are tracked separately from this hosted-runner
baseline.
