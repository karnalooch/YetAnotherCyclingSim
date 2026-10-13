# YACS Live Host — independent interactive UE editor and Pixel Streaming 2

**Latest owner operating decision — 2026-10-13:** upgrade the **currently open Remote session in place**, preserving its actual world and unsaved work. Minimize UE restarts; prefer verified supported live updates and batched changes. Do not reopen v0.3.1 or restore an older Landscape as a normal rollout step, and do not close the Editor merely to free the runner. Inspect current identities first; historical checkpoint/source entries below are references, not a command to revert the current session. See the [authorized implementation handoff](SA_CALOBRA_ROCK_ROLLOUT_HANDOFF_20261013.md).

**Issue:** [#476](https://github.com/karnalooch/YetAnotherCyclingSim/issues/476) · **First delivery:** stacked Draft PR on `codex/365-world-graph`.
**State:** implementation candidate. Windows post-logon native proof, durable video and reboot proof **NOT RUN** until a real host rollout completes. A green GitHub job is not a durable Editor handoff.

## Current target: Latest Verified World v0.3.1 — road, shoulders and lighting

**Owner decision 2026-10-13:** YACS Remote must open the latest *saved and
technically verified* Sa Calobra world, not the historical PCG365 P0–P4
diagnostic snapshot. This overrides the original initial red-marker default.
The merged #477 Live Host infrastructure belongs to Draft PR #474; main
still holds the accepted #470 v0.3.1 road checkpoint.

### Source-backed world selection

New code-only releases contain `scripts/live_host/verified_worlds.json`
and the read-only `Resolve-YacsLiveWorld.ps1`. The selected identity is
`sa_calobra_road_v0_3_1`, map:

`/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface`

from `D:/yacs/work/level-editor-review/b9fddea3f602-y473save01/`.
Receipt revision `2a00f7ebba403cf7cda663bc6fa303c7d72e891b`,
native fresh reader `fde7a363d484c3693b65efe13eba76fb71bab6e1`
(v031-reopen02) and original saved-map SHA256
`cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a`
are pinned. The resolver hashes five saved map/material packages and the
pinned original source map/project. It validates saved receipt, 559 mesh
actors and 186 material bindings. If missing or inconsistent, it blocks
startup instead of falling back to the old diagnostic scene. The complete
Material Forge/source dependency closure remains subject to native readback.

The new Live Host bootstrap starts the actual saved `L_RoadSurface` map,
inspects the 559 real road/support DynamicMesh actors and all 186 material
bindings, and positions the viewport at the retained v0.3.1 road camera.
It **observes** native DirectionalLight, SkyLight, SkyAtmosphere/fog/cloud
actors and UE global-illumination/reflection CVars. The established
`capture_material_forge_landscape.py` source has a bounded **transient**
lighting fallback; `live_world_lighting.py` reuses it **only when each
corresponding saved scene actor is absent**, adding temporary DirectionalLight
(6.0), SkyLight (1.15, open lower hemisphere) and SkyAtmosphere as required.
It preserves existing light settings, recaptures SkyLights and never saves
those fallback actors. A clean v0.3.1 saved map remains the source of truth.
The native receipt distinguishes inherited vs temporary light counts.
This is a visual-preview lighting layer, **not an accepted saved change**:
`global_lighting_visual_pass=false` until the owner reviews the actual scene.

Controls: `inspect` reads current world and lighting counts; the new
`focus_road` action restores the fixed road camera, without moving an
actor. The five P0–P4 markers are excluded from the latest-world profile.
No save, rebuild, geometry/physics/Landscape edit, PCG scatter or package
overwrite is executed by this profile.

### Safe rollout — active VP9 UE must NOT be disrupted

**IMPORTANT:** The owner previously moved a road object accidentally in
the streamed Editor. Its unsaved map state is UNKNOWN. Do not stop, kill,
switch, or restart the current editor until the owner has reviewed undo
and explicitly decided what to preserve or discard. Never issue automatic
GitHub Actions `-activate` while old PID is alive.

Once the existing editor has been *normally closed by the owner* and the
GPU is idle, use `Upgrade-YacsLiveHostCodec.ps1` with the current verified
branch HEAD and the installed source SHA. The script is dry-run by default;
it now checks the selected v0.3.1 local project/map and package hashes,
retains the previous immutable release and profile, and only on explicit
`-Apply` updates the owner Task Scheduler Action and installation metadata
with `world_profile_id=latest_verified` and codec VP9. **No Unreal process
is launched by the upgrade.** A timestamped rollback manifest targets the
immediately previous installed source SHA, not the old H264 release.

Run one subsequent owner-controlled Scheduled Task activation after
checking current GPU ownership. Native proof requires a fresh
`LATEST_VERIFIED_WORLD_NATIVE_ROAD_READY` UE receipt, true current
process PID/heartbeat/stream frames and actual material-binding readback.
Check lighting in the native result before claiming the requested global
illumination. Post-job survival and negotiated codec VP9 are separate
checks. Keep M3 final visual audit and performance deferred.


## Goal

On owner logon, a limited interactive Windows Scheduled Task owns the Unreal Editor and Pixel Streaming 2 session. The GitHub Actions runner can remain a Windows service. No job owns the Editor's PID, job object or console session, and the Editor is not killed automatically when Actions prints `Cleaning up orphan processes`.

The owner opens `http://127.0.0.1/` on the home PC or a tested private-LAN address in Chrome. Only an actual received WebRTC video frame proves playback. No public listener, firewall modification, tunnel or broad remote-execution endpoint is installed.

The initial retained diagnostic scene is the exact [#365 producer d361e765](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38278235093): five red transient P0–P4 labels and a frozen accepted Sa Calobra Landscape. This is a **pilot**. General authoring of the canonical `D:\yacs\project` workspace requires the next profile's source/map identities to be reviewed and approved. The initial diagnostic scene is **not** a writable production scene.

## Process boundary

```text
Windows boot
  ├── GitHub runner Windows service (CI, control only)
  └── Owner logs in
       └── Task Scheduler: YACS Live Host (Interactive / Limited)
            └── UnrealEditor.exe + PixelStreaming2 (long-lived)
                 ├── 127.0.0.1:80 viewer, 8888 signaling
                 ├── real native world and transient visual review
                 └── session-pinned live editor command loop
```

The installed release and runtime reside under `D:\yacs\live-host`, outside `runner/_work` and canonical project caches. A task logon instance does not silently restart after a crash and never starts a second Editor while another owner is using the GPU. `YACS Runner Monitor` and GitHub's runner service remain independent and unchanged.

## Installing and managing

Source: `scripts/live_host/Install-YacsLiveHost.ps1`.

- Default call with `-ExpectedHead <40-character SHA>` is **dry-run only**. It verifies the console user, source, real stage, free disk and idle Unreal host.
- Explicit `-Apply` creates a content-hash-verified, immutable code-only release, owner identity record, and **limited interactive AtLogOn** task `YACS Live Host`. It does **not** launch Unreal, enable remote access outside the LAN, modify the runner service, or clean historical worktrees.
- `-Verify` checks task principal and installation source. `-Uninstall` unregisters only its own task while preserving evidence/source/runner/project bytes; it refuses an active owner Editor.
- [Owner-only deployment workflow](../../.github/workflows/yacs-live-host.yml) uses four explicit commit markers: `[yacs-live-preflight]`, `[yacs-live-install]`, `[yacs-live-activate]` and `[yacs-live-verify]`. Always await exact-head protected CI before changing the Windows host. Installer and Task Scheduler do not grant special admin rights.
- Activation requests Task Scheduler to start the user-owned task. The Actions workflow must NOT launch UE directly. After this job terminates, a **separate verification run** uses `Get-YacsLiveHostStatus.ps1 -RequireLive`, checks PID/start time and heartbeat, and launches the independent verified browser receiver to establish *new* video frames. Thus a green installer or launch step cannot imply a durable handoff.

If the PC boots but the owner has not logged in, the interactive Unreal Editor will **not** be started. That is intentional to avoid Windows service Session 0 GPU/editor instability. Whether a locked or disconnected desktop can keep encoding requires real hardware observation.

## Existing install: verify Task Scheduler principal by SID

**2026-10-12 installation observation:** The owner successfully ran
`Install-YacsLiveHost.ps1 -Apply` for source
`f4a0366a5685432fb139b2083bb22ee17d7f6d9e`. It printed
`Neither UE nor the GitHub Actions service was started/restarted`.
The subsequent `-Verify` stopped at the old line 85 with
`Task principal is not the limited interactive console user`.

Windows Task Scheduler is allowed to return `Principal.UserId` as either
`KompAdama\\akarn` or a SID like `S-1-5-21-...`; the old verifier compared
the raw account string with the returned identity. The updated
`Assert-YacsLiveTaskPrincipal.ps1` resolves both representations to **the same
Windows SID** while requiring `Interactive`/`InteractiveToken` and `Limited`
privileges; it does not relax the owner check or grant elevated permissions.
`Test-YacsLiveTaskPrincipal.ps1` exercises both allowed identity types and
rejects foreign SID, service/S4U/password logons and elevated tasks.

**Recovery from this exact observed error is read-only.** Do not re-run
`-Apply`, `-Uninstall`, `Start-ScheduledTask` or UE. Inspect first:

```powershell
Get-ScheduledTask -TaskName "YACS Live Host" |
  Select-Object -ExpandProperty Principal |
  Format-List UserId,LogonType,RunLevel
```

After pulling the fix in the **separate**
`D:\\yacs\\live-host-source` worktree, rerun `-Verify` from that checkout
with its **new current Git HEAD** as `-ExpectedHead` (the source checkout
identity still requires an exact revision). The validator reads
`installation.json.source_sha` and verifies hashes of the **original
installed immutable release**; it never overwrites or upgrades that release.
The existing Task Scheduler registration also remains untouched. Successful
`-Verify` means `INSTALLED_NOT_LIVE_PROOF` only — runtime, Pixel Streaming
and post-job survival still need independent proof.

## Expanding editor editing beyond five labels

The owner authorized access to as many Unreal editing capabilities as actually supported. The [typed protocol](../../scripts/live_host/protocol.py) and [per-frame command loop](../../scripts/live_host/live_requests.py) accept only session/source/replay-authenticated requests, with bounded inputs, immutable receipts and native readback. This avoids a general Python console, remote shell or open MCP endpoint.

The **extensible** `run_recipe` operation loads only source-hashed and exact-commit-pinned Python recipes staged from the owner-controlled GitHub repository **after protected CI**. The [publisher](../../scripts/live_host/Publish-YacsLiveRecipe.ps1) binds trusted source blob, reviewed catalog, capabilities, parameters, asset scope and intended preview/author status; the [sender](../../scripts/live_host/Send-YacsLiveHostCommand.ps1) submits one serialized request. [Dedicated owner workflow](../../.github/workflows/yacs-live-command.yml) consumes only the code-reviewed typed request in `worldgen/live_host/current_command.json`, never a browser-provided code string.

Initial implemented recipe source categories are actor transforms, actor visibility, light intensity and material scalar previews. They run in memory, request native readback and **do not save** accepted map/source packages. These are candidates until tested inside a real native Editor.

The architecture supports further versioned recipes for imported assets, PCG/PCGEx, procedural terrain, animation, Blueprint, material graph and saved project changes. Native availability and correctness must be established per recipe; publishing a recipe catalog does **not** establish an installed UE API. Trusted reviewed Python can change many Unreal objects: this is **not** a security sandbox for malicious code. GitHub repository commit controls, limited Windows user permissions, exact digests, scoped backup/restore and owner approval are required. It never permits unreviewed remote PowerShell, arbitrary shell/Python snippets or unauthenticated public authoring.

For explicit persistence, an `author` recipe must declare the exact saved asset list in its reviewed catalog; the host copies+hashes each existing package to a per-request backup before execution and rejects protected map, road and `Base_DTM` roots. This path is blocked in the initial diagnostic stage, and will require a separately pinned canonical authoring project profile before any production saves. **Do not claim that all UE editing capabilities are native-PASS today.**

## Verification gates

- Offline: source/schema, replay/out-of-order, command path injection, malformed/unknown recipe, malicious value types, frozen asset scopes, preserved map identities, invalid fresh-session state, no automatic re-execution, and strict live status.
- Windows source: PowerShell parser, console SID/interactive privilege, task `AtLogOn`, `MultipleInstances IgnoreNew`, 5 GiB minimum D: reserve, exact clean Git SHA and hash-retained installed scripts. No runtime compilation by default.
- Runtime: verified map/provenance, UE 5.8.2 + Pixel Streaming 2 plugin fingerprint, one native Editor owner, five initial red labels, live queue heartbeat, actual WebRTC video frames.
- **Crucial post-job proof:** a separate GitHub job observes that the same Editor PID/start and owned Task Scheduler session survived the earlier GitHub job, and a new independent Edge/Chrome client can still receive increasing video frames. Test a second update without an Editor restart, then owner logoff/logon and optional workstation reboot, before production activation.
- Keep `#365` Draft, `qualified_assets: []`, `placement: false`, `performance_pass: false`, `PENDING_FINAL_M3` and `DEFERRED_AFTER_M3`. Do not resume paused #475 cleanup or weaken frozen Landscape, physics or road contracts.


## Active f4a0366a session — UTC serialization false negative (2026-10-12)

Owner's independent scheduled task continued in **Running** state and
`UnrealEditor.exe` PID `35248` remained alive with the original creation time.
The live viewer displayed native P3. The old repository
`Get-YacsLiveHostStatus.ps1 -RequireLive` returned
`STALE_OR_DEAD_NOT_LIVE` even though `host-status.json` had
`LIVE_RECEIVER_PROVEN_AWAITING_POST_JOB_VERIFICATION`,
`browser_frames_received=true`, `owner_handoff=true`, and a fresh
`last_seen_utc` updated approximately every 10 seconds.

The diagnostic precisely isolated two timestamp-conversion errors:

- PowerShell `ConvertFrom-Json` may already deserialize the original
  `2026-10-12T21:51:52...` ISO UTC string as a **typed DateTime**. The
  old verifier cast it to a localized string (`12.10.2026 21:51:52`)
  and parsed it again. Under an en-US parser this can be interpreted as
  December 10 instead of October 12: approximately **minus 5.09 million
  seconds** and a spurious stale heartbeat.
- The original process identity gate compared a formatted ISO string to
  the typed `editor_started_utc` object with `-ceq`. The same genuine
  PID/start time was falsely rejected.

The repository correction uses
[`Convert-YacsLiveUtc.ps1`](../../scripts/live_host/Convert-YacsLiveUtc.ps1)
to preserve a deserialized `[DateTime]`/`[DateTimeOffset]` instant; only
explicit timezone-aware ISO strings are parsed with invariant culture.
The process-start identity compares **UTC instants**, with a bounded 1000 ms
allowance to account for precision of OS process timestamps. The active and
heartbeat records must agree within 1 ms. This **does not relax** PID,
executable, SID, live-heartbeat freshness, task state, listener or video
checks. A previously completed receiver is still not equivalent to a fresh
post-job receiver test.

[`Test-YacsLiveUtc.ps1`](../../scripts/live_host/Test-YacsLiveUtc.ps1)
contains no real task, process or file mutation; tests both `pl-PL` and
`en-US`, the typed JSON / exact ISO correspondence, wrong month/day,
reused PID and unsupported localized or timezone-free timestamps.

**No restart is needed for this verifier fix.** Update only the separate
`D:\\yacs\\live-host-source` worktree, then invoke the repository verifier
to read the ongoing `f4a0366a` installation:

```powershell
git -C D:\\yacs\\live-host-source pull --ff-only origin codex/476-yacs-live-host
& D:\\yacs\\live-host-source\\scripts\\live_host\\Test-YacsLiveUtc.ps1
& D:\\yacs\\live-host-source\\scripts\\live_host\\Get-YacsLiveHostStatus.ps1 -RequireLive
```

Neither the installed immutable source release, scheduled-task action,
runner service nor the live UE process is changed by those commands.


## NVENC driver crash — immutable VP9 CPU codec trial

**Incident 2026-10-12 23:52:54 CEST:** Windows Event 1000/1001
confirmed the crash of UnrealEditor.exe 5.8.2 PID 35248
(0x89B0) in C:\Windows\System32\nvEncodeAPI64.dll, version
32.0.16.1088 (NVIDIA driver 610.88), exception 0xc0000409,
offset 0x7fcb4. Retained editor.log had bidirectional Pixel Streaming
2 player/streamer pings through 23:52:45. The owned AtLogOn task
ended as its watched UE process disappeared. This does not establish
a defect in the frozen Sa Calobra map or runner cleanup.

The narrow first intervention is **VP9 software/CPU encoding**, not a
GPU driver swap, rebuilt UE engine, or retry loop. Epic UE 5.8
[Pixel Streaming Reference](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-pixel-streaming-reference?application_version=5.8)
documents command flags -PixelStreamingEncoderCodec=VP9 and
-PixelStreamingWebRTCMaxFps=30; the
[Stream Tuning Guide](https://dev.epicgames.com/documentation/unreal-engine/stream-tuning-guide)
notes that CPU VP8/VP9 trades lower bitrate for CPU work.
The original resolution -EditorPixelStreamingRes=1280x720,
application t.MaxFPS 30 and single-browser receiver are retained.
The client-side Preferred Codec setting alone is not sufficient.

### Exact old-release to VP9 upgrade

The old immutable release is
f4a0366a5685432fb139b2083bb22ee17d7f6d9e.
Its bytes and Task Scheduler identity/AtLogOn triggers must remain intact.

1. Confirm task YACS Live Host is Ready, no UnrealEditor* processes, ports
   80/8888/18784 free, and the D: disk reserve is satisfied.
2. Update only D:\yacs\live-host-source to reviewed HEAD and run the
   source-only Windows codec/UTC tests.
3. Run Upgrade-YacsLiveHostCodec.ps1 first **without -Apply**, passing
   the new source HEAD as -ExpectedHead and the old SHA as
   -ExpectedInstalledHead. It validates hashes of the original release,
   user SID, Task Scheduler action and the shared Unreal host.
4. On an owner-accepted VP9_CODEC_UPGRADE_PREFLIGHT_PASS, explicitly
   rerun with -Apply. This copies a new exact-SHA code-only release,
   preserves the original and installation-before-vp9 backup,
   updates ONLY the task Action, and does NOT launch Unreal.

Example read-only preflight:

    git -C "D:\yacs\live-host-source" pull --ff-only origin codex/476-yacs-live-host
    $newHead = (git -C "D:\yacs\live-host-source" rev-parse HEAD).Trim()
    $original = "f4a0366a5685432fb139b2083bb22ee17d7f6d9e"
    $dir = "D:\yacs\live-host-source\scripts\live_host"
    & "$dir\Test-YacsLiveCodec.ps1"
    & "$dir\Test-YacsLiveUtc.ps1"
    & "$dir\Upgrade-YacsLiveHostCodec.ps1" -ExpectedHead $newHead -ExpectedInstalledHead $original

Stop here to review the actual preflight result before choosing -Apply.

After explicit upgrade, verify task remains Ready with Interactive/Limited
principal, the new immutable release and installation.json.video_codec=VP9.
Activate the AtLogOn task once in the logged-in desktop and only if the
GPU is IDLE. A failed VP9 startup must not silently fall back to H264
or restart in a loop.

### Browser and sustained runtime admission

1. Connect a single Chrome client to private LAN Pixel Streaming,
   with preferred VP9 profile-id=0. This is a hint only.
2. In chrome://webrtc-internals inspect the active PeerConnection's
   inbound-rtp video codecId and its corresponding codec entry.
   Require actual mimeType=video/VP9; otherwise the negotiated codec
   remains CODEC_NOT_VERIFIED. Browser video frames alone do not
   establish which encoder Unreal selected.
3. Check the *same* scheduled-task Editor PID/start identity, heartbeats,
   rising framesReceived counters, requested_video_codec=VP9,
   CPU usage and dropped frames. Keep only one receiver.
4. Observe at least 60 minutes and inspect new Windows Error Reporting
   entries; VP9 is a trial, not a proven permanent fix.
5. Repeat process+video verification after any controlling GitHub Actions
   job exits. Neither a green job nor HTTP 200 grants live admission.

### Returning to the preserved original H264

Rollback-YacsLiveHostCodec.ps1 is dry-run by default, takes the exact
original/trial SHAs, and only proceeds when the task is Ready,
no Editor or viewer/MCP listener is active, and the console SID matches.
Explicit -Apply restores the retained original task Action and
installation record; neither release or evidence is deleted.
It never starts Unreal. The original H264 remains a *known crash
baseline*, not a verified stable solution.

## Known boundaries

A running UE Editor is not proof of a working LAN receiver; a previously written heartbeat is not proof of present process ownership. The Live Host command loop is an internal trusted desktop filesystem queue, not a public arbitrary-input WebSocket service. Intermittent GPU failures, browser reconnection, sign-in after power failure, user-initiated Exit, source asset promotion, and PCGEx tool capabilities all require separate native/owner acceptance. Restore the last source snapshot rather than modifying the frozen world to hide a rejected contact.


### VP9 preflight: invalid codec test (2026-10-13)

On the first owner-local `Test-YacsLiveCodec.ps1` attempt, a negative fixture
reported `Unreviewed/unsafe codec accepted: VP9`; the independent UTC test
still passed. This was an **offline test failure before -Apply**: no VP9
upgrade, Task Scheduler alteration, Unreal startup, or GPU driver change.

The regression includes a string beginning with `VP9` and embedded ASCII
control characters, which the prior error output could display on separate
lines. The new `EncoderProfile.ps1` uses **whole-token** case-sensitive
`\\A(?:VP9|H264)\\z` validation in addition to the two-value membership
check, rejecting a newline, whitespace, NUL, suffix, wrong casing and any
unreviewed codec. The negative test now creates each control-byte string
through explicit .NET concatenation and prints the entire invalid value
JSON-escaped, so a leading `VP9` can never be confused with a clean value.

A passing previous CI or UTC test **does not** qualify this new fix. Run the
separate native Windows PowerShell codec test before any installer `-Apply`.
The original immutable installed H264 release is intentionally unchanged.

## #365/#368 rock inventory from the existing VP9 Editor (2026-10-13)

The owner's live Pixel Streaming 2 VP9 diagnostic scene displays actual Sa
Calobra relief and retained P0–P4 rejection markers. This independent
diagnostic stage is NOT the natural20 source/import/contact studio.
[Draft PR #474](https://github.com/karnalooch/YetAnotherCyclingSim/pull/474)
has twenty real mesh derivatives from eight licensed scan families, with
native import/save and fresh studio inspection. All **100/100** actual-
Landscape contact candidates at the five old diagnostic sites remain
rejected, with no qualified mesh or production scatter admitted.

The source-only **rock_asset_audit** preview recipe is the first safe
same-process bridge step: inspect StaticMesh registry metadata in /Game,
filter rock/limestone/boulder/scree/cliff/stone/pebble asset names and
return at most 24 distinct package paths. It does not load meshes, copy
studio packages, spawn actors, alter Landscape or admit placement.
The result distinguishes zero assets (COMPLETE with zero matches) from
an API error (API_UNAVAILABLE_NOT_PROVEN) or registry budget exceedance.

The approved recipe, catalog and typed command are staged by the existing
yacs-live-command workflow after exact-head protected CI. The active
VP9 Unreal process is never restarted, and no authoring assets are saved.

After the workflow, inspect the active-session command receipt under
D:/yacs/live-host/runtime/sessions/<session>/commands/. Require
COMPLETED_VISUAL_ONLY and the actual native_readback.inventory.scan_status
plus the original Editor process identity. A successful scan means inventory
only, not a rock gallery or qualified terrain-contact pose.

If the current live diagnostic project contains no matching StaticMeshes,
do not pretend the twenty separately imported studio rocks are here.
Next must be a separately sourced derived consumer/gallery and contact
qualification without modifying the accepted Landscape/road/Base_DTM.

## Owner live palette preview: P0–P4 green (2026-10-13)

The user requested changing the five visible diagnostic point labels to green
in the already running VP9 Pixel Streaming 2 Editor. The original red
presenter spawned five transient TextRenderActors with actor labels
PCG365_REVIEW_RED_P0–P4. The owner wants **only a visual palette change**.

An exact-head reviewed `marker_preview_palette` recipe calls native
`TextRenderComponent.set_text_render_color` on exactly those five existing
actors. It accepts enum `green` (32,232,88,255) or `red` (255,32,32,255),
takes a preflight record of each original FColor, verifies native color
readback, and restores originals on any setter/readback error.
The `REJECTED / REVIEW` text, old actor labels/positions, Landscape, road,
mesh/rock positions and source map bytes remain unchanged.

The `worldgen/live_host/current_command.json` one-shot command requests
`marker_preview_palette` with `palette=green`, `intent=preview`, target
issue #476. Its stage/send is subject to exact-source protected CI and
the existing authenticated current-session command queue, without a new UE
process. A workflow success alone does not prove colors changed: require the
same live Editor PID, a `COMPLETED_VISUAL_ONLY` per-command receipt with
`native_readback.native_rgba=[32,232,88,255]` and five native readbacks,
and visible owner confirmation in Pixel Streaming.

**IMPORTANT:** Green is strictly UI paint, NOT qualified rock placement.
The five points remain historical *vegetation-selector* diagnostic XYs,
not the road/shoulder corridor. All 100 actual contact cases remain
REJECTED; `qualified_assets=[]`, `placement=false`, `map_saved=false`.
Source-qualified road-adjacent rock/limestone placement belongs to #365/#368,
not to this cosmetic inspection command. To revert, issue another reviewed
typed recipe request with `palette=red`; do not restart/snapshot the map.


## Live progress overlay — owner request 2026-10-13

Issue #476 adds a read-only progress card to the existing Remote page. The
repository-owned `scripts/live_host/remote-progress.js` polls a sanitized
same-origin `yacs-progress.data.js`; it never sends browser commands to Unreal.
`Install-YacsLiveProgress.ps1 -ExpectedHead <sha> -Apply` requires a clean
commit and successful exact-head CyclingSim CI. It preserves the original
Pixel Streaming `player.html` by SHA256, installs a versioned additive script
and records a reversible deployment under Live Host state. `-Rollback` with
the installed overlay SHA restores the original page after hash checks.
No server port, Unreal plugin/binary, scene package or engine C++ is changed.
The current browser tab must be reloaded once after installation.

Start `Watch-YacsLiveProgress.ps1 -Session <current-session> -RecipeRevision
<published-recipe-sha> -Manifest <staged-manifest-sha256>` as a hidden independent
owner process, outside a GitHub runner. It uses only the existing serialized
`rock_contact_scatter/status` command and matches its request/receipt identity.
It polls at ten-second intervals after command completion, writes only bounded
counters and stops on session replacement or lost native heartbeat. Start a
new observer explicitly for each new Editor session. No raw receipts, paths,
exception messages or arbitrary command endpoint are exposed to the viewer.

The card displays phase, processed triangles, sampling positions, placed,
contact-accepted and rejected counts. The first geometry pass is indeterminate
until its true total is known; the second subtracts the completed first pass.
Sampling denominator is a maximum budget, not a guaranteed count after spatial
rejections. Missing updates older than 35 seconds hide the moving bar and show
stale data. The display never equates diagnostic completion with production
qualification, performance or owner visual acceptance. Host CI and native
ownership rules still apply; adding the web overlay itself requires no UE restart.


The installed UE 5.8 WebSocketNetworking server uses libwebsockets file mounts,
not the Node signalling server. Native HTTP testing found `.json` returns 404
and retains a file handle, preventing atomic replacement on Windows. The data
file therefore uses the supported `.js` transport suffix but contains **JSON
only**: it is fetched and parsed with `response.json()`, never loaded as a script
or evaluated. A native two-version probe served and replaced this payload with
HTTP 200 both times. This requires no new server or execution endpoint.

## Bounded search-region navigation — #365/#476

The existing `rock_contact_scatter` preview recipe supports `region_inspect`,
`region_focus`, and `region_restore` for the exact hashed window-0067 search
manifest. These operations inspect current collision owners and unsaved package
names; focus/restore alter only the viewport camera and verify native readback.
They neither register a planting surface nor save/import/spawn anything.
The current-world check rejects a switched map, and an active contact job retains
exclusive ownership. Original camera and unsaved work are preserved.
See the [execution handoff](SA_CALOBRA_ROCK_ROLLOUT_HANDOFF_20261013.md#first-implementation-batch--current-session-surface-inspection)
for source/API evidence and outstanding native proof. Delivery reuses the existing
exact-head CI, publisher and serialized queue without an Editor restart.
