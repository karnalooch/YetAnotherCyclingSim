# Sa Calobra rock rollout — authorized implementation handoff, 2026-10-13

**Issues:** #365 (procedural world), #476 (live Remote). **Milestone:** M3.
**Domain owner:** procedural-world; serialize Unreal/GPU/home-runner operations.
**Status:** owner authorized publishing the complete plan and starting implementation in a new chat. No native rollout or regional qualification is established by this document.

## Authority and owner decisions

Use [documentation authority](../README.md), [agent routing](../ai/README.md),
[Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md),
[world graph contract](SA_CALOBRA_WORLD_GRAPH.md), and [Live Host contract](YACS_LIVE_HOST.md).
The [complete Polish plan](SA_CALOBRA_ROCK_ROLLOUT_PLAN_20261013.md) is preserved verbatim from the planning chat, including its historical read-only introduction and local-status statements. Its host-local links are intentionally unchanged to preserve 1:1 content. This handoff supplies portable links and the later execution decisions.

Owner authorization, 2026-10-13: "niech to trafi do remote 1:1 i do docsów, zacznij implmentacje w nowym oknie". This supersedes the earlier planning-only hold for the bounded plan. It does not waive dependency, source, native, CI or acceptance gates. P0–P4 are retired from continuation; do not rerun them as a prerequisite.

**Latest owner instructions take precedence over the verbatim plan where necessary:**

- "ograniczaj restarty ue!" — minimize Unreal restarts. Use the existing owned Editor and verified supported live recipe/material/content update paths. Batch changes and proofs. An occupied runner is not permission to stop the Editor. Later owner authorization below permits technically necessary restarts and forced closure, including loss of unsaved state, without repeated confirmation. Explain the concrete reason and preserve saved state; minimize restarts.
- "i pamietaj ze teraz upgejdujemy otwarta sesje remote, nie cofamy sie juz do starych landscapów" — upgrade the **currently open Remote session in place**. Inspect its actual process/session, map, scene changes, loaded recipe and asset identities first. Do not restore an older Landscape, reload an older map, discard current work or reopen v0.3.1 as a normal deployment step. Historical accepted checkpoints are references and rollback evidence only; rollback must preserve the current pre-change state.
- Gray simplified-object review is deliberately deferred to a joint owner session. It blocks only decisions depending on those regions, not unrelated CPU work, the first reviewed area or other qualified surfaces.
- Review through Remote. Do not create separate review renders. Do not bypass a browser-policy rejection using alternate CDP/helper access. Missing visual access must remain explicit.

## Exact planning snapshot and active worktree

- Active source/worktree: `D:/yacs/work/pcg365-contact-remote`.
- Local branch: `codex/365-rock-contact-remote`; remote branch: `codex/365-world-graph`; Draft [PR #474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474).
- Planning base and last published head before this delivery: `c210fdbed734690ffe638a7210177459751a9475`.
- Do not assess the implementation from the older `D:/yacs/project` checkout alone. Recheck the delivered HEAD and working tree at takeover; one writer owns these paths.
- Verbatim plan UTF-8 SHA-256: `99b7d4d67a14ee62ac3bb8dff392d4b9a3d330a74bc53d8e64fdd76e866ab684`.
- Last recorded native recipe: `f0588aa2cb8a9362cc7e524b54d80b60e478ed39`, historical session `20261013T132819Z-730779601501`. These identify retained evidence, not proof of current liveness or the current state.
- Retained cancellation evidence: [hold receipt](../experiments/sa-calobra-spatial-treatment-plan-20261013/visibility-hold-receipt.json), sequence 13, `CONTACT_JOB_CANCELLED_ROLLED_BACK`, zero placed previews and complete rollback.

## Inputs and first bounded surface

- [Current interactive spatial plan](../experiments/sa-calobra-spatial-treatment-plan-20261013/spatial-plan.html), [meaning/provenance](../experiments/sa-calobra-spatial-treatment-plan-20261013/README.md), [visibility manifest](../experiments/sa-calobra-spatial-treatment-plan-20261013/visibility-plan.json), [arrays](../experiments/sa-calobra-spatial-treatment-plan-20261013/visibility-arrays.npz), and [deferred gray queue](../experiments/sa-calobra-spatial-treatment-plan-20261013/gray-live-review-queue.json).
- [Surface atlas](SA_CALOBRA_SURFACE_DETAIL_ATLAS.md), [existing window 0067 views](../experiments/sa-calobra-tpp-survey-20261008/windows/window-0067.md), and [rock source/Remote evidence](../assets/pcg365-source-support-remote-20261013/README.md).
- First proposed search area: source-cell centers X 1128.5–1135.5 m, Y 1162.0–1173.5 m, local X east/Y south. Read-only planning found a connected 137-cell subset; this rectangle is not a planting polygon. At X 1129.5/Y 1164.5 m, source 7x7 maximum slope was 9.648094 degrees, source exclusion-distance lower bound 3.286501 m, and the 4 m planning bin had 15 camera hits, maximum 40.622734 pixels/m and nearest sampled horizontal distance 23 m. The first bin witness was `window-0067-forward-00000`.
- Screen method: original 0.5 m slope raster; conservative 7x7 maximum <=10 degrees; exclusion reasons exactly zero; source distance lower bound >=1.23 m; containing planning bin with hits>0 and pixels/m>=8. This was an in-memory planning read, not a committed producer or native proof. The bin is material-first; actual visibility, rock-treatment need, full asset footprint, current road compatibility and physical surface ownership remain unverified. Reproduce/authenticate this screen before executable use; no automatic rock domain is inferred.
- Prepared coarse assets: N05 3168, N06 3388, N03 5640, N04 6320 triangles. Start with N06/N05 only where native contact and visible need support them. The stage at `D:/yacs/work/pcg365/remote-rock-preview` has manifest SHA-256 `2981ce1f35f60a4cd1bf9d8abd424b52b2e82241731eedd2946d482aba13bb4f`; its historical placements still target retired points and must not be submitted unchanged.

## Execution sequence and constraints

1. Authenticate this published checkpoint, original inputs and the **currently open** Remote session without restarting or switching the world.
2. Identify and register one physical surface in the window-0067 search area; use existing views as context, not current native surface proof. If unsuitable, select the next source-backed candidate rather than modifying terrain to fit the model.
3. Add the smallest typed, versioned per-area manifest/consumer and reviewed camera bookmark needed for that surface. Reuse the existing serialized Remote queue, import, contact, progress, cancellation and rollback facilities. No unrestricted execution endpoint or new control platform.
4. Qualify the exact coarse variants and transforms on that surface. Preserve 10-degree slope, 20-percent embedding, exposure and 65/129 refinement rules; Landscape-only measurements do not establish BOB/mesh support. Start with three rocks, at most five in the first request, as a proposed diagnostic cap rather than an approved world budget.
5. Review the useful small group in the same Remote session, then prove deterministic regeneration and owned saved/fresh-readback delivery. Plan unavoidable fresh-load proof around host availability without displacing the open owner Editor. No separate renders or invented visual PASS.
6. Continue the full plan's separate near-rock, steep-scree, cliff/large-form, material and deferred-gray lanes within their real issue gates. Map display uses exact road/water pixels; all technical consumer exclusions remain binding until a separately justified, scoped change is proved.
7. Publish bounded reviewed batches with relevant docs, tests and exact-SHA CI. Use existing Gumball Proof Broker targets for applicable heavy proofs and the existing publisher for Remote changes. Do not stop UE merely to free CI. Do not merge Draft #474 or infer permission to bypass #365 -> #366 -> #367 -> #368; the existing cliff diagnostic exception stays narrow.

Native mesh guards currently cover 559 meshes and 2,911,650 triangle IDs per scan, twice for a completed placement. Batch one region's work before optimizing this control. Any localized verification must prove equivalent coverage and change detection; no weaker check or another proof framework.

Preserve accepted Landscape, original Base_DTM, metric grid/CRS, canonical roads/physics and source masks. A local repair requires its own authorized issue, delta and rollback evidence. Prefer live updates that preserve unsaved work. Necessary restarts and forced closure are covered by the later explicit owner risk acceptance below; do not request the same approval again. Current whole-area owner acceptance remains `PENDING_FINAL_M3`; performance remains `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Delivery evidence

This publication retains the existing local visibility candidate and its source/results; it does not execute a new visibility calculation or native scene mutation. Validation results and exact delivery SHA are reported by the publishing chat/PR. The implementation chat must distinguish local candidate, remote source, test result, native runtime proof, visible live result, saved consumer and merge.

## First implementation batch — current-session surface inspection

Takeover verified clean `48aaa68e6621134635cc133b0eb707c61c0ac247`,
Draft #474 and completed #364. Current native host observation identifies
session `20261013T132819Z-730779601501`, PID 38416, installed source
`f0588aa2cb8a9362cc7e524b54d80b60e478ed39`, live heartbeat and map
`/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface`.
The supported Chrome Remote receiver now displays the current road world.
No Editor restart, map switch or scene save was performed.

The existing `rock_contact_scatter` recipe gains `region_inspect`,
`region_focus` and `region_restore`, using an independently hashed,
code-reviewed search manifest embedded in that single-file published recipe.
It observes 25 collision samples plus the source witness, actual hit actor and
component, normals, dirty map/content packages, cached import identities and
current camera. Focus derives a bounded camera from the witness's current native
height and retains the original camera for restoration. Wrong map/digest,
active contact jobs, missing hits and failed camera readback fail closed.
This is an inspection extent, **not** a planting polygon or registered surface.
First collision hits do not prove hidden/noncolliding mesh exclusions or contact.
No import, actor setter, package save, mask edit or geometry mutation is added.

API evidence: installed UE **5.8.2-56702186** `FileHelpers.h`
(`UEditorLoadingAndSavingUtils::GetDirtyMapPackages/GetDirtyContentPackages`),
`UnrealEditorSubsystem.h` (current world and camera read/write), and the existing
version-proved `SystemLibrary.line_trace_single`/18-field HitResult consumer.
Epic's [UE 5.8 loading/saving API](https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/EditorScripting/EditorLoadingAndSaving)
also lists the two dirty-package queries. PCGEx is not involved in this batch.
Native execution/readback of the new operations is pending exact-head CI and
existing publisher delivery. CPU tests do not establish native API success.

Takeover also found stale progress presentation: repeated authenticated status
receipts report `CONTACT_JOB_CANCELLED_ROLLED_BACK`, zero previews and complete
rollback while the HUD retains its old scan-phase label. The counter is retained
history, not current planting. The Blender proof for the planning HEAD stopped
at `LOCAL_BUSY`; preserve the open Editor and do not retry merely to turn it green.

CPU source screening reproduced the original 137-cell connected component
(plus one separate eligible cell in the search rectangle). Authenticated the
visibility archive and all seven logical arrays, source slope TIFF, original
mask manifest, TIFFs and logical exclusion buffers. The witness reproduces
9.648094177 degrees, 3.286501408 m lower-bound clearance, zero exclusion bits,
15 camera hits, 40.622734070 px/m, 23 m minimum sampled distance and first
camera index 219. These are planning-bin measurements, not native contact.

Local validation: all 93 `scripts/live_host/test_*.py` tests pass, including
six new region inspection/camera rollback cases. Ruff, diff whitespace,
agent contracts and docs links/i18n/structure/freshness pass. The verbatim plan
still hashes to its original digest above.

**Historical native deployment blocker (resolved below):** planning-base CyclingSim CI
[38415446073](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38415446073)
completed with failure in Unreal workspace cleanup:
`Unreal workspace cleanup refused: status=LOCAL_BUSY. Local/unknown Editors and their logs are preserved.`
The aggregate gate consequently reports `unreal-code: expected success, got failure`.
The subsequent invalid `_unreal-ci-warm` working directory is downstream of that
refusal. Hosted Python/security checks passed; neither that fact nor a local
camera test authorizes publishing executable recipes without aggregate CI.
The existing publisher remains unchanged. Do not terminate the live Editor,
forge CI admission, run a parallel native proof or bypass the queue to execute
this candidate. Source publication remains allowed; native region inspection,
registered footprint, N05/N06 qualification, first group and saved/fresh proof
remain pending the required host/proof window. No broader rollout is admitted.

## Later owner restart authorization — 2026-10-13

After source publication `8f5ec42d4a525cc986e53ce2f047ec6a61c0497f`, the owner
explicitly authorized necessary restarts without repeated confirmation and then
accepted possible loss of unsaved state for force-closing PID 38416. This
supersedes the earlier no-stop instruction for necessary restarts within this
approved implementation, including required CI windows. The owner subsequently
reiterated that repeated undo/confirmation gates waste time. Do not re-request
restart or unsaved-state-loss approval already granted. Minimize restarts and
preserve the current saved world; this does not authorize historical terrain
rollback or changes beyond approved scope.
The offscreen Editor had no main window; `CloseMainWindow()` returned false.
After explicit risk acceptance, its identity was rechecked and PID 38416 stopped.
The current saved map was copied to
`D:/yacs/work/pcg365/restart-20261013-8f5ec42d/L_RoadSurface.umap` and verified
against `cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a`.
This backs up saved state, not unsaved memory. CyclingSim CI run 38417151123
was retried for the same source SHA. Blender was not retried. Restart must use
the same current world package; no historical Landscape rollback is authorized.

## Native inspection delivered — 2026-10-13

CyclingSim CI [38417151123](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38417151123)
completed successfully for exact source `8f5ec42d4a525cc986e53ce2f047ec6a61c0497f`.
The same saved world restarted as session `20261013T152150Z-1f1c70ebd985`,
PID 37932. Independent host status reports `LIVE_VIDEO_VERIFIED`, fresh
heartbeat, verified process identity, native world and received browser frames.
The installed host remains `f0588aa2cb8a9362cc7e524b54d80b60e478ed39`;
the separately admitted recipe revision is `8f5ec42d4a525cc986e53ce2f047ec6a61c0497f`.

Publisher run 38417135614 staged the CI-admitted immutable recipe, but its
post-job verification failed during startup. Its workflow conclusion remains
failure. After host readiness, the existing serialized sender delivered the
staged recipe successfully; no alternate execution endpoint was introduced.

Native session receipts under `runtime/sessions/20261013T152150Z-1f1c70ebd985/commands`
at `D:/yacs/live-host`:

- `000001-bdcbdb82cdd740c28fcf.result.json`, SHA-256
  `53c9a0a6aa5cebaf904ef0b2e395fed71856150d664729319ff6d60838440649`:
  `COMPLETED_VISUAL_ONLY`, `REGION_OBSERVED_NOT_REGISTERED`.
- `000002-298e605ba7cf4e838778.result.json`, SHA-256
  `b267c3c027fcb525755d0b506e30d633db8d3c26efb98acca0aab99081a23334`:
  `COMPLETED_VISUAL_ONLY`, `REGION_CAMERA_READBACK_NOT_VISUAL_ACCEPTANCE`.

All 26 samples hit the current Landscape, with native slopes from
1.861075647 to 9.244494142 degrees. The witness hit is
`[112950, 116450, 69153.74513427293]` cm, slope 5.877306200 degrees.
Camera focus read back at `[113750, 117450, 69853.74513427293]` cm.
Dirty package inventories stayed unchanged; no imported content or preview
actors were present. The existing progress observer now follows this session.

These receipts establish live inspection and camera placement, not a registered
planting footprint, qualified rocks, contact placement, saved consumer or owner
visual acceptance. The next bounded implementation remains the typed regional
consumer and initial three-rock diagnostic using the existing contact controls.
Draft #474 remains unmerged; performance admission remains false.

## First bounded regional consumer — implementation candidate

The inspected Landscape is registered as `window0067-landscape-v1`, version 1,
within `[112850,116200,113550,117350]` cm. Remote inspection shows bare mineral
surface to the right of the nearby channel; the diagnostic tests a sparse small
group there. It does not cover or repair the channel, authorize a regional rock
budget, or change the material-first planning classification.

The [typed regional manifest](../../worldgen/live_host/window0067-regional-manifest.json)
hashes to `fc49334f9ceb77ed963d882524073c1c512a8f875569c5b7213b3673f20304e1`.
It pins the [native inspection](../experiments/sa-calobra-spatial-treatment-plan-20261013/window0067-native-inspection.json)
and [authenticated source screen](../experiments/sa-calobra-spatial-treatment-plan-20261013/window0067-source-screen.json).
The historical `preview-manifest.json` is retained unchanged; the new fixed
`regional-manifest.json` is independently hash-bound, with no caller-selected path.

Stable diagnostic rows are N06 at `[113000,116450]`, N05 at `[113300,116350]`
and N06 at `[113350,116750]` cm. Source 7x7 maxima are respectively
9.648094177, 8.679563522 and 7.253269196 degrees; source clearance lower bounds
are 3.181980371, 1.707999349 and 1.646446466 m. All exclusion bits are zero and
all containing visibility bins satisfy the retained planning heuristic.
Original archive and all seven logical arrays, source slope TIFF and original
exclusion buffers were authenticated before preparing these rows.

The consumer rechecks origin-inclusive full radii plus 50 cm inside the bounded
surface, a 25 cm gap between same-batch radius envelopes, and the exact native
Landscape owner. Source and imported native bounds are both checked; final
rehash/revalidation and both complete 559-mesh/2,911,650-ID scans remain intact.
10-degree slope, 20-percent embedding and 65/129 contact policy remain unchanged.
Only N05/N06 are imported. The reproducible CPU producer is `scripts/assets/prepare_pcg365_regional_manifest.py --check`;
it compares generated canonical bytes against both committed inputs and stage copies.
All 107 live-host tests pass. Thirteen regional CPU regressions cover boundaries, native
bounds, pairwise overlap, finite values and tampered surface/source receipts.
Native group placement, deterministic regeneration and saved/fresh proof remain
pending execution of this candidate. This implementation is not owner acceptance.

## Later owner correction — live iteration, not repeated native validation

The owner explicitly requires changes in the already open Editor and rejects
restarts/full native validation for each recipe iteration. Full CyclingSim CI
run 38424708274 and the waiting publisher run 38424694288 were cancelled.
Blender 38424707444 had already completed successfully; it was not rerun.
The same saved world is starting in session `20261013T155106Z-5842c308675d`,
PID 20060, with the installed host source unchanged. Do not repeat the native
CI/restart cycle merely to publish another bounded preview recipe.

The dedicated existing publisher now uses exact-source lightweight admission
for memory-only rock recipes: strict typed request/catalog/empty asset scope,
CPU contracts and immutable source digests, followed by native readback in the
same live process. Full protected CI and final merge remain separate. This
supersedes the earlier aggregate-CI-before-every-recipe instruction for this
narrow path. No authoring or generic execution capability is added.

An unpublished create-only derived-sublevel authoring candidate was retained
under `D:/yacs/work/pcg365/regional-authoring-candidate-20261013` and removed
from the active change. It needs a receiver upgrade; current work stays on live
preview and deterministic same-session regeneration. Saved/fresh consumer proof
is not claimed by that result and must not cause another normal-iteration reset.
