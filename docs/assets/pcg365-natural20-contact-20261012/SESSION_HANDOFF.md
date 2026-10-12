# Resume natural20 contact and minimum restarts — #365 / M3

This is the current transfer checkpoint. Read [README](README.md), then the
[restart plan](RESTART_MINIMIZATION_PLAN.md) and [raw audit](READBACK_AUDIT.md).
Earlier handoffs with active PID 8484/session 85545 are obsolete.

## Owner instructions and execution state

The owner requested: qualify twenty rocks against real accepted Landscape, show
actual UE Material Forge renders, use subagents, document everything, preserve
terrain/roads/Base_DTM/georeferencing/source truth. The latest additions are:

1. Minimize editor restarts absolutely; restart only for a required proof boundary.
2. Upload the complete current work to remote and continue in a new window in
   **ChatGPT → Chat** mode. Earlier local-only/no-push instruction is superseded.

Source is frozen. No owned UnrealEditor process remained when the coordinator
checked after run04; do not infer that the host stays idle. Recheck existing host
arbitration before any new native work and never interrupt an owner's editor.
Both delegated specialists have finished. There is no background implementation
or transferable active native session.

The tools in the sending chat cannot create ordinary ChatGPT Chat or switch a
new native window into that mode; they expose Codex and ChatGPT Work creation.
This handoff therefore provides an explicit remote continuation point, without
claiming a new ChatGPT Chat was automatically created.

## Repository and exact identities

- Repository: `karnalooch/YetAnotherCyclingSim`.
- Existing branch: `codex/365-world-graph`.
- Existing PR: [#474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474), Draft; keep it Draft.
- Current issue: [#365](https://github.com/karnalooch/YetAnotherCyclingSim/issues/365), OPEN.
- M3 comes from Roadmap; GitHub issue milestone is null. #363/#384/#364 are completed.
- Source worktree: `C:/Users/akarn/.codex/worktrees/pcg365-rock-gallery/project`.
- Native producer: `1a02ac21a7fb1dbc84364843e862b186a2ea0a18`.
- Run: `D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04`.
- Final delivery head is the commit containing this handoff; obtain it from Git.
  It is not relabelled as a native execution head.

The verified pre-transfer remote was `fe3541c4405356e6b3a5c61fe614c0b21ac80fe2`,
an ancestor of the complete local source history. Push must be a normal
fast-forward to the existing branch, never force. Inspect actual remote HEAD
before continuing. Older committed history also includes the separately approved
runner cleanup work; it is not permission to resume cleanup now.

Original worktree `C:/Users/akarn/.codex/worktrees/2f86/project` contains separate
dirty historical gzip/docs work. Do not bulk-stage, revert, delete or use that
checkout as current native source. The default `D:/yacs/project` checkout is also
not the isolated producer checkout. Do not push unrelated dirty worktrees under
the assumption that this handoff authorizes it.

## What actually completed

At `1a02ac21`, `collection-contact-all` groups the old ten two-mesh batches in
one owned editor process. It produced 100 cases and 200 raw grids, with a real
exit-0 completion marker. Six total run04 actions have exit-0 markers.
All cases are REJECTED; no mesh passed any of the five fixed diagnostic sites.
Independent raw recomputation found zero discrepancies. Source assets, the full
202-package Landscape closure, all twenty saved mesh packages and seven Forge
packages were rehashed. No terrain or source edit/map save occurred.

`collection-contact-reload` then wrote its receipt but UE PID 8268 exited
`-1073741819` / `0xC0000005`. Launcher line 421 rejected it; completion marker
is missing. `collection-contact-render` never ran, so there are zero new terrain
PNG images. Do not claim an admitted fresh aggregate or complete native chain.
Normal log closure does not explain the AV; no faulting module was established.

Run02 failed at batch04 and run03 at batch07 after measurements; raw data are
retained in the packet, with their actual completion boundaries. Run01 additionally
had an incomplete map. Do not reuse/promote failed receipts or overwrite stages.

The previous twenty-rock studio gallery at producer
`92f5184c0e5df7cf7698d2c8b28b9e5796e831d7` is complete but proves no terrain
contact. Its five native images remain in the previous studio evidence directory.
They must not stand in for the requested real Landscape contact renders.

## Next authorized work

1. Read root AGENTS, docs/README.md, docs/ai/README.md and relevant scoped policies.
   The authority chain is Product Requirements → Roadmap M3/#365 and World
   Building Bible section 11; evidence handoff is SA_CALOBRA_WORLD_GRAPH.md.
2. Implement the explicit three-session plan: prepare → measure → review. It is
   **NOT IMPLEMENTED**: there is no hidden scratch patch or finished new test suite.
   Source-and-docs specialist only performed read-only design/timing analysis.
3. Preserve actual process boundaries save→fresh consumer and clean contact exit→
   fresh review, the 420-second timeout and all physical/source/identity gates.
   Do not invent independent exit markers for phases within one process.
4. Review and test the bounded change, commit it, then use a new exact-head stage
   under the existing single-owner host arbitration. Do not run the legacy eight-
   process sequence merely to repeat identical data before minimizing restarts.
5. Complete fresh readback and real 20×2 GPU views. Inspect original PNGs and show
   them to the owner. Preserve rejected poses/labels; no material or foliage may
   conceal contact defects. If the process crashes, retain exact failure evidence
   and diagnose rather than asserting receipt success or blindly retrying.
6. Update this packet and the relevant SSOT; run documentation guards and exact
   delivery checks. Keep #365 open, PR Draft and performance deferred. Do not merge
   without all required gates and standing merge conditions.

User explicitly authorizes subagents. Use one domain owner and one writer per
path. The prior two specialists actually ran source/dependency/process and raw
contact audits; their completion is evidence, not a running agent framework.

## Reproduction and validation notes

The runtime is UE 5.8.2 CL56702186 with retained authenticated PCGEx pin
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`; no new native build was performed.
Never delete the retained `_phase2c-pcgex-cliff` dependency. Source collection is
`D:/yacs/work/pcg365/natural-rock-collection03/derived/natural-rock-collection.json`,
SHA256 `3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc`.
Stage with `-QualificationSources -QualificationSet natural20-contact`.
Using `rock-detail` here loses the complete accepted terrain closure.

26 scoped CPU tests passed for source `1a02ac21` (contact14 + policy7 + catalog5),
along with Ruff, PowerShell parser and diff check. The test import path needs both
the source root and `scripts/assets`. Run against the intended source checkout;
host temporary-directory permissions may require the approved elevated executor.
An initial sandbox invocation failed import/temp access and was interrupted; that
is not counted as PASS. The corrected host run completed in 2.149 seconds.

The independent auditor is retained losslessly as `contact_readback_audit.py.gz`
with its result JSONs. Decompress it to a `.py` file before execution; the archive
preserves the original runtime reader hash despite Git text normalization. For literal numerical replay use
`D:/yacs/engine/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe -B`,
Python 3.11.8. Example arguments: `--root <run04> --source <run04>
--expected-producer-sha 1a02ac21a7fb1dbc84364843e862b186a2ea0a18`.
Frozen source and native producer identities are separate. Host Python 3.12 last-
bit angle differences are documented, not waived with a new tolerance.

Final transfer docs guards: links, i18n, structure and freshness PASS via
`python -B scripts/ci/check_docs_index.py`; `git diff --check` PASS.
The documentation integration initially exposed one legacy Windows-1252 dash
in the world-graph heading; it was corrected to UTF-8 and all guards passed. Delivery CI status must be checked for the actual
pushed head; older PR CI success does not cover this new delivery.

## Scope still not proved

No regional placement, admitted rock masks/exclusions, new-consumer negative
control, continuous support, source-cap/Q90 alternative, physical stability,
latest-road checkpoint parity, native compile or owner visual acceptance follows
from these measurements. `qualified_assets: []`, `placement: false`,
`full_qualification: false`, `PENDING_FINAL_M3`, `DEFERRED_AFTER_M3`,
`performance_pass: false` remain. No M4–M10 implementation or historical cleanup.
