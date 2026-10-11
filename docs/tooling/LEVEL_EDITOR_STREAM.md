# M3 Level Editor streaming review

**Scope:** owner-requested viewport review for #364 / PR #470, inside M3.
**Status:** installed-source inspection and authenticated b9fd retarget review
**PASS**; checkpoint cadence delivered at `c62bbc3e7dcdd9ccaad9b2facef477323413e279`
with passing protected CI. The joined startup correction passed independent
code review and 93 focused local checks. At `60b53b5`, protected CI and native
registry settings passed; the next step stopped on a missing Python class
alias before opening MCP. The native-class enumeration correction passed all
26 bridge tests and 15 independent boundary tests. Live stream and same-process
update proof remain **UNQUALIFIED**. The [workflow review](../experiments/sa-calobra-road-materials-20261011/workflow-review.md)
records actual launch evidence and the current startup correction.

The owner selected Epic's **Stream Level Editor** on 2026-10-10. The review
must show the level viewport and preserve the source geometry and saved
checkpoint. On 2026-10-11 the owner extended this scope to bounded material
instance parameter previews in that same isolated Editor. This is support for
#364 material delivery; it grants no general world mutation, source-world save
or whole-editor remote-control authority.

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
`b9fddea3f6023239da98bec7a5107ed1124cf52e`, native run `38116299783-1`.
Its map is `/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview`,
SHA256 `cbbf374309508fdb2c6f86c6324af4a3824a0c5ed32a4bfc29200ad3b29da183`
(193,018,676 bytes). This is the complete dry-asphalt checkpoint with its crack
canaries and contact controls. The later outer-blend preparation failed before
saving; it is not the scene opened for this review. Owner visual acceptance
remains pending.

`prepare_level_editor_review.py` authenticates the retained receipts, binary
provenance and source bytes. It copies **278 files / 758,655,493 bytes** into a
new `D:\yacs\work\level-editor-review\b9fddea3f602-SESSION` project. Copies are
independent regular files, with a 5 GiB free reserve. Existing destinations are
refused. The native source project and its saved map remain unchanged.
Runtime SHA and launcher SHA are separate fields in every session receipt.

The launcher opens the explicit saved map and positions the viewport at the
existing `window-0112-forward-00001` road view. The bootstrap reads back the map,
saved-map hash and actual stream-source CVar before reporting scene readiness.
It keeps the requested editor session alive without saving a world asset.

## Running and checking the review

### Iteration cost and persistent-session boundary

The [road-material cadence](../CI_VALIDATION_TIERS.md#m3-road-material-iteration-cadence)
requires explicit full-proof intent. Ordinary material corrections no longer
start the native 68-view bundle or the source renderer automatically. Normal CI
and its existing compiled-binary reuse remain active.

An open streamed viewport supplies navigation and visual comparison. The owner
also requested a separate parameter-update path into that identified process.
The previous c62bbc3 launcher deliberately disabled MCP/Wingman; its prepared
stream alone did not deliver material updates. The new candidate combines the
viewport with one bounded official MCP material-preview operation. It does not
reuse the #384 bootstrap's exit-after-inspection lifecycle.

The integration contract is scalar `PaintRoughness` and vector `PaintColor` on
the known paint consumers, using transient material instances. Two separate
requests must reach the same owned Editor PID/start identity, session, project
and map. The second request must read the first request's state before applying
its own values. Each update requires native parameter and slot readback, a small
fixed-camera PNG response, and an explicit final restoration of the original
bindings. Saved source and snapshot packages remain unchanged. These are
acceptance requirements, not claims that the runtime proof has already passed.

The session identifier is the exact launch `SessionToken`, for example a
GitHub run-attempt token. Its stable receipt is
`D:\yacs\work\level-editor-review\b9fddea3f602-TOKEN\level-editor-stream-session.json`.
A follow-up request uses the same authenticated client revision and a fresh
request/output identity. It does not copy the scene, build C++, reopen the map
or clean the open project's checkout.

Freeze the launch branch at that exact SHA while the owner uses the session.
Submit parameter values through request JSON, without another code or
documentation push. A later push has a different launcher identity and its CI
may need the occupied host; it cannot silently take over the existing session.
Keep the launch's runtime results in its artifact and PR description until the
owned Editor closes. Publish the next code/documentation checkpoint after that
handoff ends, then explicitly open its next session when needed.

Close the owned Editor normally before an explicit full native checkpoint needs
the shared host. Normal CI retains its open-editor protections. Complete
save/reload and all 68 final Lit views remain checkpoint evidence; a small
preview cannot satisfy whole-area or final visual admission.

### Launch and receiving-client verification

The `M3 Level Editor review` workflow is restricted to the repository owner and
the current `codex/364-road-surface-materials` branch. A branch push starts
it only with the explicit `[level-editor-review]` commit marker; manual dispatch
is declared as well. Ordinary material/code pushes do not launch a live editor.
GitHub documents the **Run workflow** UI button for definitions on the default
branch, and API/CLI branch dispatch after a workflow has run. This file is still
in Draft PR #470: the current integration uses its explicit push launch; the
manual follow-up job is prepared but its dispatch has not been demonstrated.
Do not infer an available default-branch UI control from the branch definition.
See [GitHub workflow-dispatch documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).

The hosted waiter first requires successful protected PR CI and this PR's
independent Blender Material Forge reference proof for the exact launcher SHA.
Both use the shared Windows host; the reference workflow also refuses an open
Editor. Only after both finish may the review job reserve that host and hand
off its persistent session. The waiter holds no Unreal lock. Missing, pending
or failed results cannot launch the session. Both push and manual entry points
retain the same owner and branch scope and require these matching results.

The launcher writes the bounded MCP and registry settings to an additional
`Config/DefaultEditorPerProjectUserSettings.ini` in the fresh review snapshot
before UE starts. That file must not already exist; the six authenticated
source/project configuration files remain unchanged. The registry copies its
filters during initialization, so changing only its CDO afterwards is not
sufficient. Epic's [configuration hierarchy](https://dev.epicgames.com/documentation/en-us/unreal-engine/configuration-files-in-unreal-engine)
supports array operations in the default file; command-line property overrides
do not support arrays. Actual setting and catalog readbacks still gate startup
and each material request. The launch receipt hashes the generated overlays.

Legacy-library checks resolve the native engine/editor base classes by their
pinned paths and enumerate native UClass objects through
[ObjectIterator](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ObjectIterator).
Native inheritance checks must return exactly the two source-verified abstract
bases. Missing or redirected classes, an empty census and any additional
legacy descendant block startup. The same check remains active during preview.

The manual definition separates `operation=open` from
`operation=material-request`. The latter requires the existing session token and
a bounded JSON request, conveyed as data through environment variables and a
file. Its job uses a fresh code-only client checkout and the same host lock;
it invokes only the material client against the existing session. The native
request parser owns the allowed actions/parameters, sequence checks and value
bounds. Requests cannot supply a project path, endpoint, script or tool name.
The hosted waiter checks the existing successful exact-SHA results; it does
not launch another CI or reference run for a parameter value.

The workflow prepares its exact-SHA code checkout at
`D:\yacs\runner\_work\YetAnotherCyclingSim\YetAnotherCyclingSim\_level-editor-review-TOKEN`.
The launcher and client authenticate that retained location separately from the
saved scene. For a direct host invocation, use that unchanged prepared checkout
and its same token; an arbitrary authoring checkout is not an admitted launcher:

```powershell
./scripts/ue/Start-YacsLevelEditorStream.ps1 `
  -ExpectedHead (git rev-parse HEAD) `
  -SessionToken 'TOKEN'
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
