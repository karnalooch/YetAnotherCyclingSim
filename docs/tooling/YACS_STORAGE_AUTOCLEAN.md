# YACS safe automatic disk maintenance

The runner's historical 5 GiB job-start minimum is retained unchanged.
A separately installed, limited Windows Scheduled Task audits the D: disk
at user logon and daily at **12:00** without relying on GitHub Actions.
Install first as audit-only; enable automatic cleanup explicitly later.

## Allowlist, 14-day retention, 12-GiB cap

| Data | Automatic deletion? |
| --- | --- |
| Inactive old numbered _unreal-build-N-N or _unreal-region-N-N Intermediate / DerivedDataCache | Yes, through the existing reviewed Clear-YacsRunnerWorkspace.ps1 which checks active pointers, age, ownership and byte inventory |
| Old individual files under D:\yacs\cache\DerivedDataCache | Yes, if at least 14 days old, no UE/Houdini/runner worker and no Zen process |
| D:\yacs\cache\Zen | **NEVER** (may contain cooked output; only Zen native GC) |
| work\lesson*, work\runner-retention, project\Saved\RuntimeProof | **NEVER** |
| Git LFS, project sources/maps, Content, .umap, .hiplc, engine, data, tools | **NEVER** |
| Unknown directories, junctions, symlinks, recent or changing files | **NEVER** |

When 50 GiB or more is free, warm cache is left alone. Below 50 GiB,
automatic reclamation targets at most 12 GiB per run, with an age floor of
14 days. Oversized runner candidates are skipped for manual review. Each
cache file is checked again immediately before removal. A new native process
causes the cleanup to stop. Zen running prevents filesystem DDC cleanup.
The task will not touch the Zen database even when the server is stopped.

A dedicated exclusive lock prevents simultaneous maintenance jobs.
Scheduled audit mode writes **only** one tiny status JSON (no cache deletion).
Results are stored as one bounded file:
D:\yacs\maintenance\latest-autoclean.json. An unhandled failure is
fail-closed, not silently reported as successful. The task does not reboot,
kill processes, restore scenes, move data or restart runner services.

## Install on the Windows host only after reviewed merge

From an updated authenticated YACS repository:

~~~powershell
# Read-only, no deletion:
pwsh -NoProfile -File D:\yacs\project\scripts\runner\Invoke-YacsStorageAutoclean.ps1 -Json

# Preview the task (no installation):
pwsh -NoProfile -File D:\yacs\project\scripts\runner\Install-YacsStorageAutoclean.ps1

# Install audit-only:
pwsh -NoProfile -File D:\yacs\project\scripts\runner\Install-YacsStorageAutoclean.ps1 -Install

# Explicitly opt into daily auto-clean after reviewing audit:
pwsh -NoProfile -File D:\yacs\project\scripts\runner\Install-YacsStorageAutoclean.ps1 -Install -EnableDeletion

# Remove schedule, keep all sources, cache and receipts:
pwsh -NoProfile -File D:\yacs\project\scripts\runner\Install-YacsStorageAutoclean.ps1 -Uninstall
~~~

Installation copies both reviewed scripts with SHA-256 verification into
D:\yacs\maintenance outside mutable checkouts. A GitHub commit does not
silently update installed code. Scheduled execution uses the logged-in
desktop user (limited rights), ignores overlapping instances and does not
automatically run when the installer completes. Running at logon and noon
ensures the cleaner does not depend on the runner's 5-GiB admission gate.

## Heavy-job guidance

At 30–50 GiB free: treat heavy Houdini exports as risky, clean first.
Below 30 GiB: defer new 8x8 km cooks and UE builds. Below 15 GiB:
stop all heavy native jobs. These are **recommendations**, not an
already-deployed build admission policy. The 5-GiB fail-closed runner
minimum is unchanged, in line with the previous owner approval.

Do not run the legacy broad runner-space-recovery workflow: it has
been replaced with a safe, hosted informational workflow.

## Acceptance and limitations

Hosted CI parses the PowerShell without executing host operations and checks
the allowlist contract. Native acceptance still requires an audit-only install,
a Task Scheduler logon/day cycle, a busy-job skip, a symlink rejection and a
measured filesystem DDC cleanup. None of these are implied by code review
alone. Old Pegasus lesson caches and the 21-GiB Zen store are deliberately
not auto-cleaned. Control their size via explicit archival and verified
native Zen GC configuration separately.
