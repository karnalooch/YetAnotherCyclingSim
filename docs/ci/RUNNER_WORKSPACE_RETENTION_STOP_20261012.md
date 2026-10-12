# Runner cleanup stop report — 2026-10-12

**Status: STOPPED BY OWNER. No automatic resumption.** Follow-up:
[#475](https://github.com/karnalooch/YetAnotherCyclingSim/issues/475).
Maintenance supports M3
world work (#365); it does not change terrain, assets, remote branches or releases.
The owner explicitly requested stopping cleanup, recording this report and
opening a follow-up issue. The retention contract is
[Local runner workspace retention](RUNNER_WORKSPACE_RETENTION.md).

## Confirmed result

- **23 old trees fully pruned:** 21 of the main 78-entry plan and two incomplete
  source clones. Their complete regular-file bytes and directory structures are
  retained in CRC- and SHA-verified archives outside `_work`.
- Main-plan completed source bytes: **4,140,328,880**; archive bytes:
  **3,624,237,307**. The incomplete pair adds **255,954,344** source bytes and
  **251,172,263** archive bytes. These are logical file totals, not measured
  filesystem space reclaimed.
- The maintenance Python process was stopped on the owner's instruction.
  Listener **PID 23260**, executable `D:/yacs/runner/bin/Runner.Listener.exe`,
  was restored and verified. No Worker was present at the stop inspection.
- `main` and `v0.3.1` remain at
  `4dd792219bfc2eaf7dc216bd60cbde6628bba792`. The canonical checkout stays at
  `504b08b6ffb8a890139df8e4a140341eaa78b7da`; active build cache
  `_unreal-build-37690136030-1` remains protected.
- Free space after stopping: **41,260,892,160 bytes**. No disk-reclaim claim is
  made: archive, receipt and plan creation also consume space.

## Interrupted item — do not rerun the original plan blindly

The next item was
`YetAnotherCyclingSim/YetAnotherCyclingSim/_official-mcp-source-probe-38088310628-1`.
It has already moved out of `_work`, but its retained source was **not pruned**.
Both full copies remain:

```text
D:/yacs/work/runner-retention/_official-mcp-source-probe-38088310628-1-6363f70c46a7ca65
D:/yacs/work/runner-retention/_official-mcp-source-probe-38088310628-1-6363f70c46a7ca65.tar.gz
```

Read-only verification after stopping found **3,672/3,672 entries**, complete
source equality, a valid compression receipt and no prune completion receipt.
The archive was independently read back after stopping; SHA256:
`219335de0c12a5f132a9fbbec8b09feb6fdee91daf0b36352e0a0235c8ec5b3b`.
The original 78-entry plan will encounter missing already-moved paths; it is
not an idempotent resume command.

## Durable evidence and exact code

Host evidence is under `D:/yacs/work/proofs/runner-retention-20261012/`.
`paused-report.json` is the stop snapshot; `apply-small-first-execution.json`
now records `STOPPED_BY_OWNER`, 21 completed main items and interruption details.
Its compact [stop snapshot](../assets/runner-retention-stop-20261012/evidence.json)
is also saved in repository documentation.
The main plan is `apply-small-first.json`, SHA256
`a88965e62b154b6a1943632ec65095cd0b64ebc0d6637d638f8aec555796b8d8`.
Main execution loaded code
`0d6f7b6298ae869da1a91d861c9fc636ea473e0d`.

Local commits, not pushed:

- `fe84ebfa06eed384446457c0627f6cfc97ee2c0c`: bounded retention, completion hook,
  safe preview-only recovery workflow, tests and documentation.
- `3317e90e6251436f32ede54fc88fadafe231686e`: explicit incomplete-clone handling.
- `0d6f7b6298ae869da1a91d861c9fc636ea473e0d`: Windows readonly removal and
  verified recovery of missing retained entries after interrupted pruning.
- `fff59104b5bd6749516ecbc68e73c04bfe231e10`: explicit reviewed-remnant scope.

The two incomplete clones initially hit `WinError 5` on readonly Git pack
indices. Recovery restored missing entries from verified archives, repeated
full verification and successfully pruned both. One earlier listener-stop
attempt aborted before data mutation and the runner was restored. Receipts
for both incidents are preserved; neither was silently reported as success.

## Remaining work and undeployed candidates

1. **57 main-plan entries remain:** the interrupted retained item plus 56
   untouched source paths. Re-preview only untouched paths and inspect current
   ownership, refs and source bytes before preparing a new exact-SHA plan.
2. `remnants-plan.json` qualified **15 additional trees**, SHA256
   `e416a21d9a890b13dfc02cc745a4b6ce0e7cb38684e39d100c255e630d9b17c5`.
   `_portable-powershell-bootstrap` was excluded because its commit is protected.
3. **19 shared-Git trees** require one closed cohort, never independent removal:
   nine `s384`, nine matching `b384/*-session-project`, and their common owner
   `_official-mcp-native-probe`. Audit found reciprocal pointers 18/18, no
   external registered children, detached HEADs and no protected HEAD match.
   Raw absolute Git pointers must stay unchanged; restore every original path
   before using Git after rollback. The new cohort helper is an **uncommitted,
   undeployed candidate**: Ruff passed; **7/8 fixture tests passed**, with
   `WinError 32` during relocation in the phase2 integration fixture. Rollback
   preserved bytes. Full cohort archive/prune compatibility remains unverified.
4. The installed stable completion hook is still **quarantine-only**, at
   `D:/yacs/tools/runner-retention/Invoke-YacsJobCompleted.ps1`. It cleans only
   six exact current-job paths from `_work`; it does not yet prevent loose files
   accumulating in retention. The new compression adapter and PS integration
   are **uncommitted and undeployed**. Existing fixtures passed (21 tests), but
   Worker ancestry/foreign-worker/missing-bundle coverage and final review are
   incomplete. Do not deploy the working-tree hook alone: its adapter bundle
   must be validated and installed together.
5. A real subsequent completed CI job has **not** proven the installed hook.
   GitHub documents hooks as synchronous; see
   [runner job hooks](https://github.com/actions/runner/blob/main/docs/adrs/1751-runner-job-hooks.md).
   This supports the future design, not runtime acceptance.

Working candidates are `archive_shared_probe_cohort.py`, its test,
`compress_current_job_retention.py`, its test, and modifications to
`Invoke-YacsJobCompleted.ps1` / `test_job_completed_retention.py`, all under
`scripts/runner/`. Four untracked `scripts/runner/cohort-test-*` fixture leftovers
also remain; they were not removed after the owner's stop instruction.
Prior PCG evidence compression and rock-production changes remain separate and
must not be staged, discarded or counted as cleanup implementation.

## Safe next session

Wait for explicit owner resumption. First inspect this report and the live host;
never kill an active Worker/editor. Pause only the verified idle Listener and
restore it in `finally`. For the interrupted complete retained copy, bind its
existing compression receipt SHA, repeat full source/archive verification and
use normal phase2 prune; do not quarantine it again. If any source has become
partial, use verified recovery before normal prune. Build a fresh reviewed plan
for untouched paths. Resolve candidate tests and deploy the complete hook bundle
only after review. Keep proof/source/active-cache protections and document actual
counts, errors, restore status and exact SHAs. Do not auto-resume from this issue.

## Verification boundary

The committed retention/remnant implementation plus workflow lifecycle suite
passed **53 tests** on `fff59104`; earlier disk-reserve and host-recovery suites
passed 11 additional tests. New candidate results above are separate and do not
upgrade deployment or real-job proof. Documentation links, i18n, structure and
freshness guards passed for this stop report. Tar archives
preserve regular-file bytes and directory entries, **not NTFS ACLs**; nonempty
ADS block pruning. No protected CI, UE render or full host-restore claim is made.
