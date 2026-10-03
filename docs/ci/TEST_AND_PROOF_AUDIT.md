# Hosted tests and world-proof convergence

Issue: #320. Audit baseline: `5ae8d2a99b833ce62ae8f6681ac6460a22cf3167`.

Authority is [CI validation tiers](../CI_VALIDATION_TIERS.md), reached through
[the documentation index](../README.md). This report records findings and
implementation boundaries; it does not replace that authority.

## Findings and disposition

| Finding | Evidence | Disposition |
|---|---|---|
| Hand-maintained hosted test subset | 49 tracked `scripts/**/test_*.py` modules; 26 directly named in `reusable-python.yml`, 23 not directly named there | Discover all modules, isolate each process, reject empty discovery and retain counts, durations and failure logs. Some previously omitted modules ran in specialized workflows or the classifier; this is not a claim they never ran. |
| Aggregate had only text-presence assertions | `test_ci_aggregate_contract.py` was not in the reusable Python list | Execute the actual Aggregate Bash with success, missing, cancelled, skipped, failed and malformed inputs. |
| Policy and world JSON could miss hosted contracts | `.gumball/**` and general `worldgen/**` were not CI path families | Run hosted contracts for policy and non-documentation world data, independently of Unreal compile classification. |
| Cheap failure could overlap an expensive build | `unreal-code` depended only on `changes` | Wait for applicable hosted Python checks before reserving Unreal; keep C++-only changes valid when Python is legitimately skipped. |
| Explicit performance was not an Aggregate dependency | `stage3g-environment-performance.yml` was broker-managed but absent from Aggregate needs | Add read-only, fail-closed exact-world admission. Draft iteration defers hardware; ready PRs and main world changes require evidence. |
| Geometry PR workflow duplicated hosted kernels | Geometry probe ran two deterministic modules and syntax checks on PR events | Keep broker/manual proof bundle, move automatic coverage to the complete hosted suite and compile all script Python. Remove duplicate push/PR entrypoints. |
| Current-world and legacy-world labels were conflated | Documentation index moved to Sa Calobra while lifecycle listed SP638 proofs as current M3 world evidence | Mark legacy proofs as regression/recovery evidence. They cannot admit Sa Calobra. Preserve them until equivalent replacement is proven. |
| Rapid updates produced cancelled runs | Runs 37025230350, 37025318867 and 37025369813 were cancelled before final run 37025464029 | Keep cancellation for superseded PR checks. Batch this CI implementation before final tests/push; do not claim a new cache or scheduler is needed from cancellation alone. |

The final inspected #319 run, 37025464029 on `6e3db4ea...`, failed both the
Python region-preparation step and the Unreal build/Automation step. Its upload
also lacked the native artifact after earlier failure. This audit does not
attribute those failures to GPU performance and does not repair #319 in a second
branch. Its branch, assets and owner Editor handoff are untouched.

The first complete hosted batch found three stale, previously unlisted contracts:
forest cleanup expected the old fixed worktree names instead of run-isolated
full-world and verified warm-code worktrees; progressive foliage expected the
removed height-normalization variable instead of shared candidate uniform scale;
M3 upload expected the retired worktree instead of the retained-asset recovery
worktree. Assertions now follow those existing implementations while preserving
cleanup failure checks, tree-base placement and exact-run artifact isolation.
No Unreal implementation or threshold was changed to satisfy those tests.

## What stays

- Verified STATIC/RUNTIME/COMPILE and WARM/COLD cache boundaries.
- Independent code-only versus full-LFS validation.
- Physics reference tests, hosted PowerShell parsing and LFS smoke.
- Existing security, governance and caller-local Aggregate name.
- Existing explicit Proof Broker hardware dispatch and deduplication.
- Legacy deterministic geometry/authoring tests, including those protecting
  reusable tools after an experiment workflow was retired.
- Existing per-worktree resource locks. No global GPU scheduler or live-process
  reuse across revisions is introduced by this PR.

Do not collapse all Unreal workflows into one mutable checkout: the current
full-asset, code-only and owner-handoff lifecycles have different cleanup and
ownership requirements. Prepared-data caching or full-world compile reuse needs
measured input/ownership proof before migration. The inspected evidence does not
justify deleting these boundaries merely to reduce the workflow count.

## Final validation evidence

`run_script_tests.py` writes `summary.json` and per-module logs outside the
checkout. It records elapsed time for every module, runs remaining modules after
a failure, and rejects zero-test or all-skipped modules. The existing
assertion-based final-architecture entrypoint is explicitly identified, executed
and reported separately from unittest cases.

`world-proof-admission-<run>-<attempt>` records required scenarios, exact SHA,
admission phase and validated artifact/run IDs. `DEFERRED_DRAFT`, `STATIC_ONLY`
and `NOT_REQUIRED` are not measured performance PASS.

Tests are run only after implementation and review of the complete candidate,
as requested for Issue #320. Runtime or performance success must never be inferred
from synthetic validator fixtures or from this audit document.

## Independent Sa Calobra integration boundary

PR #319 owns the terrain and pending sampler. This CI PR does not import its
unmerged source or claim to finish that sampler. The consumer contract is
[documented with the validation tiers](../CI_VALIDATION_TIERS.md#exact-world-performance-admission).
Until `sa-calobra-terrain-performance` is registered in the existing broker and
produces the required real evidence, merge-ready Sa Calobra changes fail closed.
A terrain-only pass still does not admit final asphalt, cut/fill, collision,
visual quality, traversal or the complete M3 world.
