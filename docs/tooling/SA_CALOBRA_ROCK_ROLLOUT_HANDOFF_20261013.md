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

- "ograniczaj restarty ue!" — minimize Unreal restarts. Use the existing owned Editor and verified supported live recipe/material/content update paths. Batch changes and proofs. An occupied runner is not permission to stop the Editor. If a restart is technically unavoidable, explain the concrete reason beforehand, preserve unsaved work and follow existing ownership/approval rules; no restart loops.
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

Preserve accepted Landscape, original Base_DTM, metric grid/CRS, canonical roads/physics and source masks. A local repair requires its own authorized issue, delta and rollback evidence. Runtime updates must preserve the current session's unsaved work. Current whole-area owner acceptance remains `PENDING_FINAL_M3`; performance remains `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Delivery evidence

This publication retains the existing local visibility candidate and its source/results; it does not execute a new visibility calculation or native scene mutation. Validation results and exact delivery SHA are reported by the publishing chat/PR. The implementation chat must distinguish local candidate, remote source, test result, native runtime proof, visible live result, saved consumer and merge.
