# M3 road material review — 2026-10-11

**Issue:** #364; contact observations remain under #459. **PR:** #470, Draft.
**Reviewed runtime:** `b9fddea3f6023239da98bec7a5107ed1124cf52e`.

## Evidence identity

[Native run 38116299783](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38116299783)
completed all selected stages. The original archive is 476,694,696 bytes,
SHA-256 `d580f706d7b645ada9ebea9244126a30de1d22d88a4a0da5a68594ef6a84f7d6`.
Its live GitHub artifact identity, ZIP digest and all 629 extracted file
sizes/hashes were verified. [Source manifest](b9fd/source-artifact.json) records
the original identities of the small retained subset; PNGs are unchanged.
Full manifests, logs, priming frames and remaining originals stay in
[artifact 11694637100](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38116299783/artifacts/11694637100).

## Role handoff

The [role registry](../../ai/ROLE_REGISTRY.json) and
[handoff contract](../../ai/TASK_HANDOFF.md) define the boundaries. These are
actual assignments for this continuation, not new agent types or privileges.

| Role | Bounded assignment | Output / resource boundary |
|---|---|---|
| `visual-dcc` | Inspect all 68 final Lit frames and the 16 crack controls; assess grain, crack appearance, white lines and transitions | Image findings and material recommendations; no source/geometry mutation or host use |
| `road-bob` | Compare 16 window0112 and six hairpin0081 images with retained source/native/CUT data | Surface ownership and source-relative contact analysis under #459; no pavement or Landscape mutation |
| `unreal-integration` | Review the separate outer-blend proof and the existing Level Editor stream launcher | Manifest-specific bounded-read fix and tests; no unverified runtime retarget or native dispatch |
| Primary coordinator | Authenticate artifacts, inspect findings, update current documentation, integrate and publish | One writer per affected path; serial native/GPU/home-runner work through existing ownership gates |

The independent `visual-dcc` reviewer also checks the stream-preparer patch.
Protected CI, actual Unreal evidence, owner visual acceptance and merge remain
separate from specialist recommendations.

## Current findings

- Save and separate fresh reload passed, followed by actual GPU exit zero.
  Coverage is **68 Lit + 16 crack controls + 16 window0112 + 6 hairpin0081**
  final images. Priming images do not increase that coverage.
- Dry aggregate is visible without the previously rejected glossy response.
  The two local crack motifs look restrained, with no visible rectangular
  patch outline in the reviewed Lit views. This is two canaries, not network
  distribution or an edge-erosion result.
- The neutral, BaseColor, Roughness and WorldNormal controls were captured and
  inspected. The two actual patches use UV rotations 0 and 90 degrees. Their
  crack-normal signal is too small in these rider views to resolve normal
  orientation confidently. `normal_space_verified` remains false.
- Near white lines follow the road. Far pixel gaps, transverse asphalt bands,
  and the sharp outer gravel/Landscape transition remain unresolved.
- At 0112, the dark narrow road-edge band remains when support112, support022
  or the selected local Landscape is hidden independently. The new 022 control
  rejects sole ownership by that shoulder; it does not prove a guessed fix.
- At 0081, support185 owns the tall exposed wall. The new native wall/source
  CUT payload is present; source-relative analysis belongs to #459. Final
  native Landscape height is still not established by this payload.

## Original preview frames

![0112 native asphalt, white lines and local crack canary](b9fd/road-crack-visual-controls/frames/window-0112-forward-00002--cracks-lit.png)

![0082 native Nudo material and UV90 crack canary](b9fd/road-crack-visual-controls/frames/window-0082-forward-00002--cracks-lit.png)

The [0112 support022-hidden control](b9fd/shoulder-contact/capture/frames/window-0112-forward-00002-support022-hidden.png)
and [0081 reverse baseline](b9fd/shoulder-contact-0081/capture/frames/window-0081-reverse-00004-baseline.png)
retain visible defects, rather than implying geometry acceptance.

## Next bounded proof

Select the existing five-owner outer terrain blend plus the ten band/paint
controls, retaining all 68 original Lit cameras. Do not repeat the crack or
contact families in this separate attempt. Its 18 exact selected textures,
save/fresh/GPU checks, source/buffer conservation and unchanged strict native
texture checks remain required. The prior outer preparation failure is still
unresolved; the current stage/memory records locate any recurrence.

The stream launcher currently targets an older proved scene. Its metadata
parser now handles the actual 3,225,316-byte b9fd saved manifest: only
that named manifest receives a 4 MiB bound; all other metadata retain 2 MiB.
Runtime/map/receipt pins may be retargeted only after authenticating the chosen
successful native result. No working live stream is claimed here.

Owner audit: `PENDING_FINAL_M3`. Performance: `DEFERRED_AFTER_M3`,
`performance_pass: false`. #364, #459 and M3 remain unfinished.
