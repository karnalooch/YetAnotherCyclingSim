# M3 material iteration cost and editor reuse

**Recorded:** 2026-10-11. **Scope:** owner-requested #364 workflow review;
M3 and the existing role/host boundaries remain in force.

## Recommendation

Use one persistent, identified Editor for material preview; update existing
material parameters and inspect a small set of affected views. Keep a complete
saved/fresh-reloaded 68-view proof as an explicitly requested checkpoint.
Stream Level Editor carries the viewport. The existing official MCP integration
is the preferred basis for a separately qualified material-update operation.
Streaming alone neither applies Git changes nor removes scene/graph costs.

The first cadence, launch-order and authenticated b9fd retarget changes are
implemented in this candidate. The owner subsequently authorized implementation
of the persistent MCP preview and stream integration on 2026-10-11. That work
is in progress; live material editing, focused capture and cache relocation
are not claimed as completed runtime capabilities in this initial checkpoint.

## Measured local cost

The authenticated [b9fd native checkpoint](README.md) reused compiled C++
binaries. The [2ec534c cache receipt](outer-2ec534c/cache-resolution.json) separately
records `Mode: static`, `CompileKind: none`, `Reason: verified-equivalent-proof`.

| b9fd process | Measured elapsed time |
|---|---:|
| Read-only native baseline | 91.368 s |
| Prepare and save the derived consumer | 261.167 s |
| Independent fresh reload | 143.887 s |
| GPU review: 68 Lit plus 16 crack controls | 771.374 s |
| Sum of these four processes | 1,267.796 s / 21.13 min |

This sum excludes the reversible canary, contact processes, host preparation,
queue time and artifact upload. It is not a C++ compilation measurement.
The GPU bundle emitted 336 PNGs: 84 final frames and 252 priming frames. The
first-to-last capture interval was 511.045 seconds. Six shaders compiled in that
GPU process, with 2.78 seconds reported in flight; C++ reuse does not mean that
no shader compilation occurs. The GPU log also records a 7.565-second autosave
to `Saved/Autosaves`, without changing the authenticated source packages.

The new [outer preparation failure](outer-2ec534c/README.md) is a separate
problem. It failed after successful frozen-terrain authentication, inside the
`terrain.build_surface_terms` interval. D3D12 could not allocate a 32 MiB
rendering resource. No completed outer graph, saved map, fresh reload or GPU
review resulted. The exact expression/allocation cause is not established.
Stream encoding, more shader workers or a larger timeout are not demonstrated
repairs for this failure.

## What Epic's documentation establishes

| Mechanism | Documented behavior | Application to YACS |
|---|---|---|
| Material instances | Parameterized instances allow interactive changes; static switches generate compiled permutations [E1] | Expose frequently tuned values as scalar/vector/texture parameters. Avoid rebuilding a master graph to tune roughness, tint or normal strength. |
| Pixel Streaming in Editor | Streams either the complete Editor or only its level viewport; editor streaming is experimental [E2] | Keep the owner-selected Level Editor stream for scene review. It does not show the Content Browser or material-editor panels. |
| Official Unreal MCP | Named toolsets can be discovered and called in Editor; tool refresh and reflected-declaration limits are documented [E3] | Extend the already qualified #384 transport with one scoped preview operation, after checking the actual installed schemas and session lifecycle. |
| Remote Control | HTTP/WebSocket access to exposed functions/properties and presets [E4] | A supported alternative for a small manual control panel. It would be another control path; prefer existing MCP first. |
| DDC / Zen | Caches derived shader/asset data outside Git and supports a common local cache [E5] | Verify existing cache use and its D: configuration. A new cloud/shared service is not the next optimization for one home host. |
| Live Coding | Patches supported C++ changes in a running process; reflected changes have limitations [E6, E3] | Useful when editing C++ implementations. It is not the main remedy for the present material preparation/render workload. |
| Stream tuning | Encoding trades image quality, latency, bandwidth and frame rate [E7] | Begin with the prepared 1280x720 review size and one viewer; qualify a modest preview frame-rate limit. Retain original PNGs for fine cracks/line-gap decisions. |

Installed-source evidence adds an important project-specific limit: the existing
stock material setters call `update_material_instance` and refresh the material
editor, but their transport has not been qualified in the #364 streamed session.
The current launcher deliberately disables MCP/Wingman and Python remote
execution. The #384 bootstrap also exits after its bounded inspection, so it
cannot simply be inserted into a session that must stay open.

## Prioritized changes

### 1. Explicit complete checkpoints — implemented candidate

Ordinary branch pushes no longer start full native or source material proof.
The explicit native and source intents retain owner/branch guards and existing
proof bodies. Native still waits for successful protected CI at the exact SHA.
The lock is acquired by the admitted host job. See the authoritative
[cadence contract](../../CI_VALIDATION_TIERS.md#m3-road-material-iteration-cadence).

The Level Editor launch now waits for its own exact-SHA CI before taking the
shared host. Otherwise the persistent review session could prevent the later
CI job from obtaining Unreal ownership. Existing open-editor protections remain.
The stream target is the latest complete b9fd saved scene; the failed outer
candidate is not relabelled as accepted.

### 2. Parameter preview in the same process — proposed next slice

Reuse the current official MCP/private-registry and transient-material patterns.
Start with one existing paint parameter, such as `PaintRoughness`, on the known
paint consumer. The operation must identify the prepared session, exact map,
checkpoint, owned slots and current values. It must reject conflicting state.

Use a transient MID for the trial, change the allowed scalar, read it back and
capture two existing road views before/after. Restore only the operation's own
slot and camera changes; preserve unrelated dirty packages and owner edits.
Keep the Editor alive. Qualify two requests with the same PID and map, recording
elapsed time, values, originals and restoration. There is no map load or C++
build between values once this operation is installed.

Then extend only the controls required by current work: normal strength,
asphalt variation and transition parameters. Some shoulder widths are currently
graph constants, so they need a deliberate parameterization change before they
can use this path. A graph or texture change may still require shader work or
reimport. A new reflected tool declaration may require a one-time build/restart.

### 3. Focused capture — proposed, distinct from final proof

The current GPU host has no standalone focused mode. Its optional controls
follow all 68 Lit poses. Reuse the existing camera and capture helpers with an
explicit preview result that cannot satisfy full-area admission.

| Current question | Existing relevant view family |
|---|---|
| Transverse asphalt bands | 0071 / 0082 with channel and uniform controls |
| Distant white-line coverage | 0083 original and full-mask control |
| Crack normal response | 0112 / 0082 UV0/90 controls |
| Shoulder contact | Separate 0112 and 0081 contact families |

A usual small preview could contain four final images and twelve priming images
instead of the b9 GPU bundle's 336 images: 95.2% fewer images in that capture
bundle. This is an arithmetic coverage comparison, not a measured 95.2% reduction
in total run time. Preserve readiness, priming, camera identity, native originals
and state restoration. Complete checkpoint coverage remains unchanged.

### 4. Bound graph construction and memory — diagnose before another full run

Instrument the failing graph-building operation more narrowly and test a small
material consumer before involving the complete loaded scene. Reuse authenticated
source materials and construct each required graph once per actual recipe change.
Batch parameter updates and perform the documented final material update at the
operation boundary where supported. The existing outer builder already places
its final explicit recompile outside the node-creation loop, and it does not
use the static-switch setter. Batching is not a ready-made fix for the observed
2ec534c failure. Do not infer that a transaction alone suppresses native
recompilation or GPU allocation.

Moving construction ahead of full scene loading requires separating its existing
live-Landscape authentication from the pure builder; it is an implementation
proposal, not an available switch. Frozen source identity, real mesh assignment
and final full-map checks must still run. If memory growth persists on a small
consumer, diagnose that operation before retrying the complete workflow.

### 5. Use the existing D: cache configuration consistently — proposed

Both inspected native logs report a healthy local Zen service, but its data
directory is still on C:. They also open the 1,679 MiB engine DDC Pak and report
the legacy local cache as writable. This is not evidence of a missing cache or
of every run starting from cold data.

YACS already has the desired D: configuration: `manage_local_workspace.py`
passes `-ZenDataPath=<workspace cache>/Zen`, and `Start-YacsRunner.ps1` sets
`UE-ZenDataPath`. The runner launcher returns early when a listener already
exists, so the intended environment cannot be assumed to have reached it.
Verify the actual runner environment and child launch/readback, then use the
existing resolved cache path consistently. Epic documents `UE-ZenDataPath` and
`-ZenDataPath` as local-data-path overrides, including for local DDC [E8].
Preserve the C: cache until the D:
configuration is verified. No process restart or cache deletion was performed
in this review. Cache location is separate from the diagnosed allocation failure.

### 6. Small supporting savings

Use source rendering only when the selected source producer/inputs change, not
for UE instance parameter tuning. Read the small receipt/manifest first and
retrieve selected originals for review before downloading a complete large ZIP.
Consider reusing the already disabled-autosave policy from the stream launcher
in the isolated proof process; qualify that narrow change separately. Keep
baseline, preparation and preview in one owned session where independence is
not the property under test; the deliberate fresh-reload checkpoint stays a
separate process.

## Success criteria and role split

The next persistent-preview slice should demonstrate zero C++ builds and zero
map reloads between two parameter trials, correct visible consumer readback,
bounded image coverage and restored state. Measure time and memory on the real
home host before publishing a speedup. A 30–120-second small diagnostic bundle
is an initial target, not an achieved result or a promise for graph/texture work.

Visual & DCC owns appearance and source generation; Unreal Integration owns
material application and session lifecycle; road-bob owns separately scoped
geometry/contact work; Proof QA independently checks evidence and coverage.
The coordinator integrates and schedules one host owner. Agents may analyze in
parallel but do not each start their own Editor or GPU job. Final M3 owner audit
remains `PENDING_FINAL_M3`; performance is `DEFERRED_AFTER_M3`, never a synthetic
PASS from preview.

## Official sources

- [E1 — Epic: Instanced Materials](https://dev.epicgames.com/documentation/unreal-engine/instanced-materials-in-unreal-engine)
- [E2 — Epic: Pixel Streaming in Editor](https://dev.epicgames.com/documentation/unreal-engine/pixel-streaming-in-editor)
- [E3 — Epic: Unreal MCP in Unreal Editor, UE 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-mcp-in-unreal-editor?application_version=5.8)
- [E4 — Epic: Remote Control](https://dev.epicgames.com/documentation/unreal-engine/remote-control-for-unreal-engine)
- [E5 — Epic: Derived Data Cache](https://dev.epicgames.com/documentation/unreal-engine/using-derived-data-cache-in-unreal-engine)
- [E6 — Epic: Live Coding](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-live-coding-to-recompile-unreal-engine-applications-at-runtime)
- [E7 — Epic: Stream Tuning Guide](https://dev.epicgames.com/documentation/unreal-engine/stream-tuning-guide)
- [E8 — Epic: Zenserver data location, including local DDC](https://dev.epicgames.com/documentation/unreal-engine/using-zen-storage-server-as-cooked-output-store-for-unreal-engine?lang=en-US)
