# M3 Level Editor streaming review

**Scope:** owner-requested viewport review for #364 / PR #470, inside M3.
**Status:** installed-source inspection prepared; live stream **NOT RUN**.

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
does not by itself prove that only the viewport will be streamed. Inspect the
installed startup/settings implementation before choosing command-line flags.

- [Pixel Streaming in Editor](https://dev.epicgames.com/documentation/en-us/unreal-engine/pixel-streaming-in-editor)
- [PixelStreaming2Editor module API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PixelStreaming2Editor/IPixelStreaming2EditorModule)
- [UE 5.8 editor stream type](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PixelStreaming2Settings/EPixelStreaming2EditorStreamType-)

Installed Epic source excerpts stay in bounded probe logs/ignored artifacts;
do not copy engine source into Git. A source declaration is not proof of a
working plugin, encoder, network connection or received browser frame.

## Review target and remaining proof

The first requested target is the retained #364 saved road consumer, not the
older whole-map result pinned by `Open-YACS-Review.ps1`. Select a verified
consumer receipt and identify its runtime source SHA separately from the
launcher source SHA. Preserve the native saved/fresh-reload and visual status.

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
