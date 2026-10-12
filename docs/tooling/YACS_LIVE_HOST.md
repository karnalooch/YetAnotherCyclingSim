# YACS Live Host — independent interactive UE editor and Pixel Streaming 2

**Issue:** [#476](https://github.com/karnalooch/YetAnotherCyclingSim/issues/476) · **First delivery:** stacked Draft PR on `codex/365-world-graph`.
**State:** implementation candidate. Windows post-logon native proof, durable video and reboot proof **NOT RUN** until a real host rollout completes. A green GitHub job is not a durable Editor handoff.

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

## Known boundaries

A running UE Editor is not proof of a working LAN receiver; a previously written heartbeat is not proof of present process ownership. The Live Host command loop is an internal trusted desktop filesystem queue, not a public arbitrary-input WebSocket service. Intermittent GPU failures, browser reconnection, sign-in after power failure, user-initiated Exit, source asset promotion, and PCGEx tool capabilities all require separate native/owner acceptance. Restore the last source snapshot rather than modifying the frozen world to hide a rejected contact.
