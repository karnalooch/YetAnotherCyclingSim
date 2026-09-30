# GitHub Actions workflow lifecycle

Status: **ACTIVE / AUTHORITATIVE FOR WORKFLOW DISPOSITION**

This document explains which GitHub Actions workflows are current, broker-managed,
historical/retired, one-shot/dead or intentionally unresolved. The machine-readable
source is `.gumball/workflow-lifecycle.json`.

The purpose is not to erase historical engineering evidence. It is to keep
**executable Actions surface finite** while preserving reusable scripts, tests,
PR history and documentation.

## Lifecycle rules

- **CURRENT** — part of today's CI, proof, recovery, Project, notification or
  repository-operations contract.
- **BROKER-MANAGED** — current heavyweight target whose normal operator intent
  goes through the Gumball Proof Broker; direct `workflow_dispatch` remains a
  recovery fallback.
- **HISTORICAL/RETIRED** — useful evidence or implementation history, but no
  longer an executable Actions authority. The workflow file must be absent.
- **ONE-SHOT/DEAD** — incident/canary/mutation helper whose purpose ended. The
  workflow file must be absent.
- **UNKNOWN** — deliberately retained because an active workstream owns the
  disposition. Unknown is not permission to leave a workflow unresolved
  forever.

New workflow files must be added to the registry in the same PR. A workflow
with a permanent `if: false` job or a hardcoded historical run-cancellation
endpoint is forbidden outside an explicit test fixture.

## Current workflow inventory

| Workflow | State | Why it remains executable |
|---|---|---|
| `asset-full.yml` | CURRENT | Explicit trusted full asset/release validation |
| `branch-hygiene.yml` | CURRENT | Stronger YACS-local merged-branch cleanup |
| `ci.yml` | CURRENT | Primary CI graph and caller-local Aggregate gate |
| `manual-unreal.yml` | CURRENT | Trusted manual Unreal validation/recovery |
| `passo-giau-embark-terrain.yml` | CURRENT | Fail-closed exact-SHA DCC-to-Unreal Passo Giau terrain proof selected by #287 after the direct native baseline failed rider-view acceptance |
| `passo-giau-r4-1-hairpin-corridor.yml` | BROKER-MANAGED | Exact-SHA SP638 hairpin proof; manual dispatch is fallback |
| `passo-giau-r4-1-landscape-author.yml` | UNKNOWN | Failed direct-DTM/native Landscape baseline retained as recovery evidence while #287/#288 proves the Embark-mode replacement |
| `passo-giau-r4-1-road-author.yml` | UNKNOWN | Legacy SP638 native-authoring recovery evidence retained while #287/#288 proves the Embark-mode replacement |
| `passo-giau-r4-1-roadside-house.yml` | BROKER-MANAGED | World Authoring Library SP638 proof; manual dispatch is fallback |
| `passo-giau-r4-1b3-geometry-probe.yml` | BROKER-MANAGED | Gumball proof target for `r4-1b3-geometry` |
| `passo-giau-road-alignment.yml` | CURRENT | Current official SP638 GIS preparation/alignment proof |
| `pr-orchestrator.yml` | CURRENT | Trusted PR orchestration |
| `project-bootstrap.yml` | CURRENT | Manual Project bootstrap/recovery |
| `project-status.yml` | CURRENT | YACS-specific Project lifecycle synchronization |
| `proof-broker.yml` | CURRENT | Trusted Proof Broker orchestration |
| `repository-ops.yml` | CURRENT | Gumball labels/lifecycle reconciliation |
| `reusable-python.yml` | CURRENT | Hosted Python and repository contracts |
| `reusable-stage3g-full.yml` | CURRENT | Exact-head full-world proof used by CI |
| `reusable-unreal.yml` | CURRENT | Code-only Unreal build + Automation |
| `runner-space-recovery.yml` | CURRENT | Owner-only manual main-branch runner recovery |
| `scorecard.yml` | CURRENT | OpenSSF supply-chain audit |
| `slack-notify.yml` | CURRENT | High-signal CI/release Slack routing |
| `stage3g-environment-performance.yml` | BROKER-MANAGED | Exact-SHA 1080p60 performance proof; manual dispatch is fallback |
| `stage3g-forest-target-density-author.yml` | CURRENT | Live target-density authoring branch + manual fallback |
| `stage3g-forest-target-density-performance.yml` | CURRENT | Paired target-density performance proof |
| `stage3g-source-asset-audit.yml` | BROKER-MANAGED | Exact-SHA non-mutating source-asset/performance audit; manual dispatch is fallback |
| `windows-probe.yml` | CURRENT | Cheap manual hosted-Windows probe |
| `yacs-editor-command.yml` | CURRENT | Owner-only issue-command remote-editor smoke |

The two `UNKNOWN` native Passo Giau workflows are intentionally retained only as
failed-baseline/recovery evidence while #287/#288 proves the replacement Embark-mode
terrain path. Their final disposition follows that proof; they must not silently
become current production authority again.

## Retired executable surface

| Retired workflow | State | Evidence / replacement |
|---|---|---|
| `adaptive-unreal-profile-canary.yml` | ONE-SHOT/DEAD | Deleted canary branch; only job was permanently disabled |
| `drain-legacy-passo-giau-author.yml` | ONE-SHOT/DEAD | Historical hardcoded run cancellation |
| `passo-giau-r4-1-terrain-spike.yml` | HISTORICAL/RETIRED | TINITALY baseline; current World Bible uses MASE PST |
| `passo-giau-cortina-2m-probe.yml` | HISTORICAL/RETIRED | Source investigation superseded by MASE |
| `passo-giau-veneto-fast-probe.yml` | HISTORICAL/RETIRED | Veneto endpoint discovery preserved in research history |
| `passo-giau-veneto-lidar-probe.yml` | HISTORICAL/RETIRED | Older Veneto source path |
| `passo-giau-veneto-source-ab.yml` | HISTORICAL/RETIRED | TINITALY/Veneto A-B is evidence, not current source authority |
| `passo-giau-road-source-probe.yml` | HISTORICAL/RETIRED | Superseded by `passo-giau-road-alignment.yml` |
| `stage3g-boulder-lod-author.yml` | ONE-SHOT/DEAD | One-shot authoring branch no longer exists |
| `stage3g-r2-conifer-author.yml` | HISTORICAL/RETIRED | Deleted R2 branch |
| `stage3g-r2-conifer-reduction-profile.yml` | HISTORICAL/RETIRED | Deleted R2 branch; reusable profiler remains |
| `stage3g-r2-fir-profile.yml` | HISTORICAL/RETIRED | Workflow retired; profiler/wrapper contract remains tested |
| `stage3g-r2-fir-reduction-profile.yml` | HISTORICAL/RETIRED | Old manual reduction experiment |
| `stage3g-r2-pcg-route-exclusion.yml` | HISTORICAL/RETIRED | Deleted R2 branch; implementation remains contract-tested |
| `stage3g-r2-persist-forest-assets.yml` | HISTORICAL/RETIRED | Deleted mutating R2 branch |
| `stage3g-r2-persist-pcg-forest.yml` | HISTORICAL/RETIRED | Deleted R2 recovery branch |
| `stage3g-r3-persist-pcg-biomes.yml` | HISTORICAL/RETIRED | Deleted R3 branch |
| `stage3g-r4-terrain-coherence-author.yml` | HISTORICAL/RETIRED | Deleted R4 authoring branch; reusable harness remains tested |

Historical proof conclusions remain discoverable in PRs, docs, terrain research,
visual/performance history and retained scripts. Removing a workflow file does
not rewrite that history.

## Active families

The surviving Actions surface is intentionally grouped:

1. **Main CI:** `ci.yml` + reusable Python/Unreal/full-world workflows.
2. **Gumball/repository operations:** governance consumers, Proof Broker,
   Repository Ops, branch hygiene and PR orchestration.
3. **Explicit recovery/probes:** manual Unreal, Windows probe, runner-space
   recovery, Project bootstrap and remote-editor command.
4. **Current M3 road/world proof:** the Embark-mode Passo Giau DCC-to-Unreal terrain
   proof, SP638 alignment, plus broker-managed geometry, hairpin and World Authoring
   Library SP638 proofs.
5. **Current environment evidence:** target-density forest plus broker-managed
   source-asset audit and environment performance.
6. **Delivery/notification:** full asset validation, Scorecard and Slack.

A branch-specific experiment workflow should not survive merely because its
historical branch name still explains where it came from.
