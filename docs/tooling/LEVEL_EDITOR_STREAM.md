# M3 Level Editor streaming review

**Scope:** owner-requested viewport review for #364 / PR #470, inside M3.
**Status:** installed-source inspection **PASS**; isolated launch and receiving-client
check prepared; live stream **NOT RUN**.

The owner selected Epic's **Stream Level Editor** on 2026-10-10. The review
must show the level viewport and preserve the current scene, materials and
source geometry. This is review support for the existing material delivery,
not a new world-authoring interface or a whole-editor remote-control service.

## Version and source evidence

The installed engine contract is UE **5.8.2 CL 56702186**. Before automating
startup, the existing filesystem-only source probe can inspect the installed
PixelStreaming2 editor/settings declarations using `level_editor_stream`.
It preserves bounded reads and writes evidence only below the checkout's
ignored `Saved` directory. It does not enable a plugin, start Unreal or create
a network listener. Other existing source-inspection focuses remain available.

Epic's UE 5.8 API documents
`IPixelStreaming2EditorModule::StartStreaming` with
`EPixelStreaming2EditorStreamTypes::LevelEditorViewport`. The enum belongs to
`PixelStreaming2Settings` in this version. The generic start-on-launch example
does not by itself prove that only the viewport will be streamed.

Installed source inspections
[38088310628](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38088310628)
and [38088947399](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38088947399)
confirmed the UE 5.8.2 settings class and startup flow. The class uses
`config=Game` and initializes its CVars from its config properties. The launcher
uses explicit Game configuration overrides for this class:

```text
-EnablePlugins=PixelStreaming2
-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorSource=LevelEditorViewport
-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorStartOnLaunch=True
-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:EditorUseRemoteSignallingServer=False
-ini:Game:[/Script/PixelStreaming2Settings.PixelStreaming2PluginSettings]:ConnectionURL=ws://127.0.0.1:8888
-EditorPixelStreamingRes=1280x720
```

The editor's main-frame callback reads the settings and starts the chosen source.
With local signalling selected it invokes Epic's built-in signalling server.
The installed Windows default viewer port is **80**, streamer port **8888**.
The loopback connection URL is the streamer's destination; it does not restrict
the server's listener interfaces. Actual bindings are recorded after startup.

- [Pixel Streaming in Editor](https://dev.epicgames.com/documentation/en-us/unreal-engine/pixel-streaming-in-editor)
- [PixelStreaming2Editor module API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PixelStreaming2Editor/IPixelStreaming2EditorModule)
- [UE 5.8 editor stream type](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PixelStreaming2Settings/EPixelStreaming2EditorStreamType-)

Installed Epic source excerpts stay in bounded probe logs/ignored artifacts;
do not copy engine source into Git. A source declaration is not proof of a
working plugin, encoder, network connection or received browser frame.

## Review target and remaining proof

The first target is the retained #364 saved road consumer from runtime SHA
`1ef46dacedba5ed1fc909422529be41808d3dbe4`, native run `38084733503-1`.
Its map is `/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview`,
SHA256 `35d485005f123e5648f675d6f91209630c163bddf92d55f6c5b640d55917732d`.
This is the last checked saved asphalt/shoulder checkpoint, not visual approval
or a claim that later dry-asphalt changes have been natively verified.

`prepare_level_editor_review.py` authenticates the retained receipts, binary
provenance and source bytes. It copies **265 files / 743,351,566 bytes** into a
new `D:\yacs\work\level-editor-review\1ef46dacedba-SESSION` project. Copies are
independent regular files, with a 5 GiB free reserve. Existing destinations are
refused. The native source project and its saved map remain unchanged.
Runtime SHA and launcher SHA are separate fields in every session receipt.

The launcher opens the explicit saved map and positions the viewport at the
existing `window-0112-forward-00001` road view. The bootstrap reads back the map,
saved-map hash and actual stream-source CVar before reporting scene readiness.
It keeps the requested editor session alive without saving a world asset.

## Running and checking the review

The `M3 Level Editor review` workflow is restricted to the repository owner and
the current `codex/364-road-surface-materials` branch. A scoped code push starts
it only with the explicit `[level-editor-review]` commit marker; manual dispatch
is also supported. Ordinary material/code pushes do not launch a live editor.

The native entry point, from an unchanged checkout containing these scripts, is:

```powershell
./scripts/ue/Start-YacsLevelEditorStream.ps1 `
  -ExpectedHead (git rev-parse HEAD) `
  -SessionToken ([Guid]::NewGuid().ToString('N'))
```

It checks host ownership, the inspected engine/plugin and free listener ports,
prepares the separate project and uses the repository's existing owner-handoff
convention. The requested editor remains open after the workflow completes and
owns the shared host until it is closed. Startup failure stops only processes
whose ownership, executable and start time were recorded for that session.

The client check uses a fresh, temporary installed Edge profile and loopback
DevTools. It requires two increasing nonzero video-frame counters on the same
live MediaStream, plus nonzero dimensions. It records a screenshot and closes
only its own browser processes. A viewer HTTP response alone remains
`HTTP_READY_CLIENT_PENDING`; actual received frames produce
`BROWSER_VIDEO_RECEIVED`. Neither status grants M3 visual or performance approval.

Session and scene receipts, engine log and client evidence are retained in the
workflow artifact. A copy of the session receipt is stored in its prepared
project. It identifies the owned editor PID/start time and observed local/LAN
URL candidates. The owner can close that editor to release the host; no other
Unreal session is stopped by this launcher.

Use the existing home-host ownership arbitration. An occupied editor or
conflicting native job blocks a new review launch. Do not stop another editor,
change the live authoring checkout or silently replace a scene under review.

The initial connection is local/LAN. A public internet endpoint, router changes,
client console-command execution and full-editor capture are outside this
review's default configuration. A working viewer requires an observed viewport
stream, scene identity and a real receiving-client check. Until those checks
pass, record **NOT RUN** or the actual blocker and do not publish a working URL.

M3 owner visual acceptance remains `PENDING_FINAL_M3`; performance remains
`DEFERRED_AFTER_M3`, `performance_pass: false`.
