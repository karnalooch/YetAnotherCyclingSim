# Texture Material Prep: remote continuation report

**Evidence cutoff:** 2026-10-05. **Work item:** [#382](https://github.com/karnalooch/YetAnotherCyclingSim/issues/382). **Delivery:** [draft PR #383](https://github.com/karnalooch/YetAnotherCyclingSim/pull/383).

This report is the entry point for continuing this task without the originating chat or workstation. The owner requested a transition to remote-only work. GitHub now holds the implementation and a verified recovery archive. A remotely running Unreal Editor, working MCP transport and a fully rehearsed restore have **not** been established. Do not confuse remote storage, CI execution, editor deployment and material acceptance.

## Authority and boundaries

Read [the documentation index](../README.md), [texture architecture](TEXTURE_MATERIAL_PREP.md), [commands and proof procedure](TEXTURE_MATERIAL_PREP_EXAMPLES.md), [workspace recovery](LOCAL_WORKSPACE.md), [MCP contract](../UE_MCP_WORLD_GENERATION.md) and [remote editor contract](../YACS_REMOTE_EDITOR_AGENT.md). The World Building Bible owns world decisions; this report records evidence and continuation steps, not a new world architecture.

Texture Graph owns image processing. The small MCP toolset only validates requests, controls the native graph, renders, exports and collects evidence. Do not substitute another processing backend, generic Python executor or unrestricted toolset.

Preserve the scene, roads, Landscape, BOB and existing asset identities. No material from this experiment is assigned to the world. #382 is separately authorized; it does not unblock official MCP control-plane adoption #384. At the evidence cutoff, #363 and #384 are open and the #384 dependency remains binding. Recheck their actual state before any future adoption work.

The owner authorized a third implementation PR for this bounded task, then local activation/testing, saving a scene copy before restart, remote backup, and this report. These approvals do not change the normal branch limit or authorize a main merge without its gates.

## Exact state to resume

| Item | Recorded state |
|---|---|
| Implementation branch | `feat/382-texture-material-prep-foundation` |
| Tested implementation commit | `eb755d87defa7528a84a7321bc4232d1de67a8d2` |
| Scene baseline commit | `a42117988904789c5e23277e8210cd53f603e967` from the separate #363 workspace |
| PR | #383, draft; no main merge performed in this task |
| Engine | UE 5.8.2, CL 56702186, compatible/build ID 55116800 |
| Repository plugin default | Disabled; project descriptor in PR unchanged |
| Reference-host opt-in | Enabled locally; six native schemas registered and capability inspection succeeded |
| Remote editor / MCP | Not deployed or proved; official MCP server disabled |
| Real-source job | `7EE0347149883740027D7DB63B63BD90` |
| Material admission | Review required; no world assignment |

The scene baseline and plugin commit are intentionally separate. Do not merge the entire unmerged #363 branch into #383 to recover an experiment. The archive is a recovery snapshot, not production asset admission or a substitute for the Git/LFS baseline.

## What is implemented

`Plugins/YacsTexturePrep` is an editor-only native plugin depending on Texture Graph and Toolset Registry. `YacsTexturePrep.YacsTextureTools` exposes `InspectCapabilities`, `PrepareTexture`, `RenderPreview`, `ExportPbrSet`, `ValidateTexture` and `GetJobStatus`.

The fixed graph performs bounded de-light/color gain, edge-local mirror blending, grayscale-derived height, native normals, remapped roughness and a blurred macro mask. The implemented subset is opaque saved BGRA8 sRGB Texture2D input, square 128/256/512/1024 output and five BGRA8 maps. Height is an artistic 8-bit preview, not measured displacement. No AO, seed, channel packing or promoted reusable template is implemented. Wider target-contract options in the architecture are future requirements.

Each render uses one named output in a retained transient graph. The adapter serializes the exact retained Texture Graph readback with `UTexture2D::Source.Init`, verifies dimensions/settings/pixels, then saves fresh owned packages. Native asynchronous TG re-render/export produced intermittent zero maps in isolated trials; its replacement changes serialization, not processing authority. Preserve this distinction when editing the adapter.

Jobs pin source GUID and graph package SHA-1, reject dirty/changed inputs and destination collisions, allow one active job and at most eight jobs per proof session. A 180-second timeout enters draining and retains ownership until the native task completes. Do not retry a write into a partially completed run.

The isolated `tools/ue-mcp/texture-proof-profile.yml` and `YacsTextureGuard.js` admit only exact qualified operations and validated inputs. They do not authorize replacing the live profile. The engine registry expects bare operation names; pinned db-lyon 1.3.9 strips the qualification. Native registration and guard unit tests do not establish network transport.

Maintained scripts are `scripts/assets/texture_material_prep.py`, `texture_material_prep_bundle.py`, `scripts/ue/texture_material_prep_ue_smoke.py` and `texture_material_prep_ue_reopen.py`. The smoke/reopen scripts require their disposable-project marker. Archived one-shot deployment scripts are historical evidence, not an instruction to run them on another live scene.

## Tests and their limits

| Evidence | Result and interpretation |
|---|---|
| [Remote CI at the implementation SHA](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37295103416) | PASS, including full Unreal build and Automation. Applies to that commit, not automatically to later commits. |
| Local component build | PASS against the exact installed engine. |
| Synthetic 128px fixture | Five-map render/export exact pixel comparison and fresh-editor decoded-pixel/settings equality PASS. See [committed proof](texture-material-prep-proof.json). |
| Lightweight checks at implementation SHA | 25 Python tests, four pinned guard tests, Ruff, docs links/i18n/structure/freshness and architecture contract PASS. |
| Native tool definitions | Six schemas and registry capability dispatch PASS. Remote transport remains untested. |
| Real Rock026 source | Five 512px outputs exported; structural diagnostics PASS; visual/material admission pending. |
| Scene preservation | 375 actor identities/classes/labels/transforms matched after restart; this is not a new full ground-trace/performance proof. |

The synthetic de-light trial at strength 0.25 produced **+18.54%** mean luminance drift and was correctly flagged. No physical illumination recovery is claimed. Keep de-light disabled for the recorded real-source baseline.

Local full-project activation first failed because PCHs referenced the old `D:/Epic Games/UE_5.8` path. A full no-PCH retry exposed existing non-texture missing includes (`ULevel`, `UMaterial`, among others). No unrelated source repairs were made. The successful plugin-only target used `UnrealEditor Win64 Development`, explicit `-Project` and `-Plugin`, `-NoPCH -NoSharedPCH -NoHotReloadFromIDE -WaitMutex`. A `-Module=YacsTexturePrep` attempt alone did not produce the required module metadata. Do not report the failed full local rebuild as a PASS or copy CI DLLs into a running authoring project.

## Sources and first limestone-role proof

Three official ambientCG CC0 1K PNG packages were acquired: [Rock024](https://ambientcg.com/a/Rock024), [Rock026](https://ambientcg.com/a/Rock026) and [Rock042S](https://ambientcg.com/a/Rock042S). [Provider license](https://docs.ambientcg.com/license/). Original ZIPs, API metadata and per-file size/SHA-256 provenance are preserved in the archive. No source is verified as limestone, Mallorca geology or measured 2m coverage.

| Source | Result |
|---|---|
| Rock024 | Imported fresh source rejected: alpha 253..255 violates the opaque-input guard. Original unchanged; no successful generated outputs claimed. |
| Rock026 | RGB source completed the native graph/render/export path. Used as a visual surrogate for the planned limestone proof role. |
| Rock042S | Acquired only. Provider dimensions 120x120 were recorded, but the unit/physical coverage was not independently verified. |

The imported Rock026 object uses `YACS_SC_Limestone_01_BaseColor` as a proof-role name; it does **not** establish geological identity. Source object: `/Game/Generated/YACS/TextureMaterialPrep/Sources/31edfe9c1bbb4394ad28b12447a76ed5/YACS_SC_Limestone_01_BaseColor.YACS_SC_Limestone_01_BaseColor`.

Rock026 original color PNG SHA-256: `e4ad1fd86606519ca55f412d3ebb99e1ef590d2a2c53f3ea40406a2d21c33f06`. Original provider PNGs contain chromaticity metadata rejected by the strict offline decoder. Metadata was not stripped to bypass that guard. Offline bundle checks used the source PNG exported from UE; preserve the distinction between those byte identities.

Recorded recipe: 512x512, proposed 2x2m, seam width 0.03, de-light 0, white color gain, height 0.5, normal 1, roughness 0.55..0.9, macro 0.5. Saved graph SHA-1: `5914443525D51966FD0060CBFA21D25806A842F3`.

Outputs are under `/Game/Generated/YACS/TextureMaterialPrep/Runs/7EE0347149883740027D7DB63B63BD90`: BaseColor, Height, Normal, Roughness, MacroMask and the graph. Export status is `exported_review_required`.

| Rock026 diagnostic | Recorded value |
|---|---|
| BaseColor seam mean X / Y, linear RGB | 0.0367946314 / 0.0367924951 |
| Boundary/interior ratio X / Y | 0.518 / 0.463 |
| Provisional seam screen | Review required: boundary contrast and gradient mismatch on both axes |
| Mean luminance relative drift | +0.015243859% with de-light disabled |
| Clipping increase / luminance flags | 0 / none |
| Normal maximum unit-length error | 0.0090684 |
| Normal maximum wrap angle X / Y | 9.0446 / 5.9855 degrees |
| Negative normal Z count | 0 |

2x2 and 4x4 previews are archived. Repeated diagonal rock motifs were visible in the 2x2 inspection. Successful diagnostics do not override seam flags. Real-source fresh-editor reopen, compressed GPU/mip sampling, DirectX ramp orientation, physical scale and owner visual acceptance remain open.

## Scene preservation and historical host layout

Before the approved restart, the original map was left unchanged on disk, 18 dirty content packages were backed up and saved individually, and the current world was saved as `L_SaCalobraTextureCheckpoint_20261005`. No Save All was used. The packages included 12 cyclist preview assets and six existing mask/material-foundation assets. These are recovery dependencies, not texture-pipeline changes admitted into this PR.

The saved map SHA-256 is `0eef66dc1f404c7d48a84d2254d4fd09ba0842f749445dd974d83b7b4e1889a0`. A fresh editor matched all 375 actors. The first comparison mistakenly included Python struct memory addresses; the final comparison removed only those addresses and retained actual transform values. The original receipt still says `saved_reopen_pending`; the separate reopen receipt supplies the later evidence. Do not rewrite historical receipts to manufacture a newer result.

Historical paths, not assumptions about a remote host:

- Canonical project: `D:/yacs/project`; implementation worktree: `D:/yacs/work/texture-material-prep-spec`.
- Engine: `D:/yacs/engine/UE_5.8`; every reference-host launch used `-ZenDataPath=D:/yacs/cache/Zen`.
- Sources: `D:/yacs/data/textures/texture-prep-candidates-20261005`.
- Scene preservation: `D:/yacs/checkpoints/2026-10-05-before-texture-prep`.
- Transfer files: `D:/yacs/checkpoints/texture-prep-remote-20261005`.
- Deployment evidence: project `Saved/RuntimeProof/TextureMaterialPrepDeployment`.
- Render bundle: project `Saved/RuntimeProof/TextureMaterialPrep/7EE0347149883740027D7DB63B63BD90`.
- Offline validation: implementation worktree `Saved/RuntimeProof/TextureMaterialPrep/126276881d594e7280f4a1bc2123aa8f`.

The workspace launcher default map was not changed. The canonical checkout contains unrelated #363 work; no blanket staging/reset or branch switch is permitted. A historical editor PID/window is not a usable remote endpoint. Re-discover current host/session state when needed. Keep the 50 GiB reserve and serialize editor/build work.

## Verified remote backup

[Authenticated draft release](https://github.com/karnalooch/YetAnotherCyclingSim/releases/tag/untagged-98fa61b00fe49600cbd1), logical tag `checkpoint-texture-prep-2026-10-05`, release ID **403630725**. Draft URLs may use an `untagged-*` slug; resolve by logical tag or numeric API ID when necessary. Keep it draft: it includes pre-existing scene content, not just CC0 textures. Access requires appropriate repository authentication even though the repository is public.

| Asset | Bytes | SHA-256 |
|---|---|---|
| `texture-prep-checkpoint.zip` | 284770805 | `7c3392ab7aae44388fc52978489fdb85d329a276c7fcd68723d841d7bfdd08d8` |
| `restore-manifest.json` | 15820 | `03ab3b2b3e0df81694918693c432b17744cdd36e220720a5b7ac5e9b253a18c3` |
| `remote-backup-receipt.json` | 893 | `4443f39c5e7ea7cc68df26c04e36bcc78dd9eb40d6fe9411ddd45b2ffe344b46` |

All 76 archive members were checked against their per-file SHA-256 before upload. GitHub reported matching archive/manifest sizes and SHA-256, with upload state `uploaded`. This proves remote byte storage, not a successful recovery rehearsal. The manifest's `prepared_not_uploaded` is its historical preparation status; the separate receipt records subsequent remote verification.

The archive contains `project/` (checkpoint map, saved dependency assets, source/run assets, opt-in project descriptor), `sources/` (three original provider ZIPs plus acquisition/API receipts), and `evidence/` (deployment scripts/receipts, render bundle, diagnostics/previews, scene receipts). It does not include the whole repository, engine, compiled plugin binaries, caches, every local dirty change, or all older world inputs. Earlier baseline/external data recovery remains covered by draft releases `checkpoint-sa-calobra-2026-10-04` and `data-cnig-sa-calobra-working-v1-2026-10-03` and the workspace guide. Do not publish those releases either.

## Remote-only continuation procedure

1. Read #382 and #383, this report and current repository instructions. Fetch the PR branch and confirm exact revision. Recheck #363/#384 dependency state. Use GitHub as the durable task/evidence record; do not rely on chat memory or the original disk.
2. Discover the actual remote execution environment, supported GitHub reads/writes, authenticated draft-release access, UE 5.8.2 availability and authorized GPU runner/remote broker. Record each capability separately. Hosted Python execution is not an Unreal GPU host. If no supported editor endpoint exists, continue docs/static analysis and report that specific missing layer; do not claim remote editor deployment or bypass the allowlist.
3. Download all three assets into a new recovery directory with `gh release download checkpoint-texture-prep-2026-10-05 --repo karnalooch/YetAnotherCyclingSim --dir <new-directory>`. Check the pinned archive and manifest hashes above before extraction. Reject duplicate/absolute/traversing archive names, resolve destinations inside the fresh directory, and verify all manifest sizes/hashes. Do not extract over an active workspace.
4. For texture-only work, use the plugin PR source and copy only the explicitly inventoried texture source/run namespace into a disposable project with required native dependencies. Review and apply the plugin opt-in deliberately. Build for the installed engine rather than reusing host DLLs. Preserve no-overwrite guards and use a new job ID for any new processing attempt.
5. For scene recovery, separately restore the recorded scene Git revision and its LFS dependencies, follow the older workspace recovery instructions for external inputs, and apply only manifest-listed project files in a closed isolated checkout. The archived descriptor belongs to that baseline; do not overwrite an unrelated newer descriptor. Full scene dependency/recovery rehearsal remains pending, so fail on missing assets rather than infer completeness.
6. Prove capability inspection and synthetic render/export/reopen first. Then reproduce Rock026 with the pinned source and recipe, compare five maps/settings, inspect 2x2/4x4/corners, and collect fresh-editor and compressed-sampling proof. Do not replay archived checkpoint scripts against the recovered scene as a texture test.
7. Stop the real-source admission path on the current seam flags. Diagnose a concrete TG recipe issue or select a better licensed candidate; retain immutable originals and compare against the recorded baseline. Establish real limestone suitability and physical coverage before promoting the proof-role asset.
8. If remote tool routing becomes authorized and available, exercise only the existing narrow guarded profile and prove denial cases plus lifecycle semantics. #384 still needs its own dependency/proof gates; no `All Toolsets`, generic execution or unofficial server shortcut.
9. Update this report/issue/PR with new immutable revisions, job IDs, receipts and precise PASS/pending/failed status. Keep PR draft until its relevant validation and review gates are satisfied. A remote backup request is not a request to merge or deploy world materials.

## Remaining work, in order

- Verify the chosen remote environment and authenticated recovery access; rehearse the texture-only restore.
- Reopen the actual Rock026 outputs in a fresh editor and prove settings/pixel persistence.
- Add or execute DirectX ramp and compressed GPU/mip validation on the supported host.
- Resolve the provisional seam failures and obtain visual review; keep de-light limitations explicit.
- Identify a suitable limestone source with provenance and physical-scale evidence; the current name is only a role.
- Prove any separately authorized remote transport without violating #384's dependency gate.
- Only then consider material admission or a separate world integration task. No new heavy build is needed merely to read or transfer this report.

This delivery changes documentation and tracking context only. The reusable distinction between remote backup, executable deployment and admission is already required by AGENTS.md and LOCAL_WORKSPACE.md; no new Gumball subsystem or promotion candidate is introduced.
