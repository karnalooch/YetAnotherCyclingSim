# M3 Level Editor streaming review

**Scope:** owner-requested viewport review for #364 / PR #470, inside M3.
**Status:** bounded same-process paint preview and five source camera presets
**PASS**; automated browser video qualification remains pending. The latest
[Editor run at `78de72ab`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38147063888)
retained session `38147063888-1`, Editor PID `19740`, with owner handoff.
All nine official MCP calls completed: two material changes, restoration of
370 original bindings, five camera presets and return to the road (sequence 9).
Actual camera positions/rotations passed readback; source/saved inputs stayed
unchanged and dirty-package lists remained empty. FOV, camera screenshots and
a subsequent Chat-issued request remain unverified.

Exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38147068129)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38147067669)
passed. Edge progressed past the earlier array-to-URI failure but failed when
an asynchronous `VoidTaskResult` contaminated the CDP response (`ContainsKey`
error). It observed zero frames; cleanup completed. The overall native job is
**FAILURE**, with `HTTP_READY_CLIENT_PENDING`. The correction suppresses unused
connect/send completion values while retaining the receive result. Local
regression tests do not establish actual Windows frame reception.

The [native artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38147063888/artifacts/11705034569)
was authenticated against SHA-256
`576112e4c01ba558b659dcfec8d118841fb7a9319a4c1dc8483ca16973d7ee4d`.
The owner's earlier Chrome observation is separate manual evidence. Prior
session `38141538137-1` was owner-confirmed closed before publishing `78de72ab`;
that confirmation does not close the new retained session. Freeze its launch
branch until its handoff ends. The Zen warning follow-up remains closed by the
owner's confirmation. The
[workflow review](../experiments/sa-calobra-road-materials-20261011/workflow-review.md)
retains earlier evidence. Viewport proof grants no final M3 or performance approval.

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
For the observed MCP contract mismatch, a source-probe push whose HEAD message
contains `[mcp-domain-source]` selects the existing `domain_extension` focus.
It retains the complete, bounded contents of four already inventoried files:
`ObjectFunctionToolCall.cpp`, `ToolsetJson.cpp`, `ModelContextProtocolToolResults.h`
and the exact registry Python `tool_call_impl.py`. These replace the previous
four full-file priorities, whose complete bodies are retained at `1b2e2ea`.
This supplies the missing return-conversion and text-result contracts without
starting another Editor. Ordinary
automatic selection, owner/ref/path guards and all read/output caps remain.
The probe is declaration evidence only; it cannot admit a preview session.

### Native result contract and rejected-response evidence

The authenticated [source-only run](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38137155495)
retained all four files completely: 1149 lines and 43,544 original bytes.
`ObjectFunctionToolCall::MakeResult` places the reflected return value in
exactly one `returnValue` field. Our declared `FString` contains the domain
receipt as JSON text; `MakeTextResult` copies the serialized envelope into one
MCP text-content item. The client therefore performs two fixed, bounded JSON
decodes: text to the singleton `returnValue` object, then its string to the
domain object. Alias keys, extra envelope fields, direct domain objects and
recursive string unwrapping are rejected. MCP errors remain errors. All four
source implementations are added to the existing startup hash pins.

After the one allowed call returns, the client saves `mcp-response.json`
before domain validation, within 2 MiB including its final newline. It records
the canonical form of the already parsed JSON-RPC object, not original HTTP
bytes. Existing session, process, sequence, material readback, capture and
source-conservation checks still determine acceptance.

If that attempt is blocked, the client performs one bounded local read of
the receipt path derived from the independently validated request ID. Existing
bytes become `native-diagnostic-receipt.json` with `RETAINED_UNVALIDATED`, a
hash and size; their contents never supply paths or establish completion.
`NOT_OBSERVED` means the file was absent at that single observation, while
read/write refusals are `NOT_RETAINED` with a separate diagnostic error.
Neither result overwrites the primary failure or triggers polling, retry,
another material call or restoration. A pending capture might finish later.

The authenticated [source read at `1b2e2ea`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38133509018)
retained all four files completely: 811 lines, with hashes matching the earlier
inventory. The artifact is 40,023 bytes, SHA-256
`efe51894ab0f370df8face4a8f7b4e801a6c2326f894dcfcb4aafc0fe8864a69`.
`GetToolsetClassName` derives the qualifier from the actual class outer and
combines it with the actual class name; it provides no metadata override for
the previous short name. The MCP adapter reads native `inputSchema` directly.

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
bindings. Saved source and snapshot packages remain unchanged. These requirements
passed in the retained `badb984` paint qualification; later requests must still
pass them against their actual session and current sequence.

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

### Bounded camera requests

The owner authorized five source-derived views on 2026-10-11. They use the
existing official MCP preview operation with `action=camera` and one fixed
preset name. Chat instructions map to this allowlist:

| Owner instruction | Preset | Survey frame |
| --- | --- | --- |
| `POKAŻ DROGĘ` | `road` | `window-0112-forward-00001` |
| `POKAŻ WJAZD W NAWRÓT` | `hairpin-entry` | `window-0081-forward-00004` |
| `POKAŻ ŚRODEK NAWROTU` | `hairpin-middle` | `window-0081-forward-00008` |
| `POKAŻ WYJAZD Z NAWROTU` | `hairpin-exit` | `window-0081-forward-00012` |
| `POKAŻ NUDO` | `nudo` | `window-0082-forward-00002` |

The module copies `camera_location_cm` and `target_cm` from the
[pinned survey](../experiments/sa-calobra-tpp-survey-20261008/frames.csv), whose
SHA-256 is `15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3`.
It does not substitute the survey's separate road-position column. Exact-source
tests authenticate every value. Epic's **Unreal Python 5.8**
[UnrealEditorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem)
documents the existing viewport getter/setter, including an absent viewport;
[MathLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MathLibrary)
documents `find_look_at_rotation`. The installed bridge still requires
UE 5.8.2 CL 56702186. The survey's 76-degree FOV is reference evidence only:
this API path does not set or read FOV, and reports `viewport_fov_verified=false`.

A request is data for the existing authenticated client, for example:

```json
{"schema_version":1,"session_id":"TOKEN","request_id":"camera-001","action":"camera","expected_sequence":9,"preset":"road"}
```

Use the actual session token and current verified sequence, with a fresh request
ID. Camera and material requests share the bounded sequence/history. Startup
qualifies the original three material operations, then the five camera presets
and a return to `road`; a successful unchanged startup therefore ends at
sequence 9. The client and ready receipt authenticate the new camera module.
Native readback must match position within 1 cm and wrapped rotation within
0.01 degree, preserve material bindings, dirty flags and source/snapshot hashes,
and complete before another request. A pending material capture blocks a camera
move. A failed camera transaction attempts a verified camera rollback without
restoring or replacing the active material preview. Uncertain calls are not
retried. Requests cannot provide coordinates, arbitrary commands or FOV.

The client returns and retains `camera_before`, `camera_after` and source preset
provenance. Camera movement does not itself capture an image or establish visual
acceptance. The existing `operation=material-request` workflow can carry this
JSON through the same client, but its branch-only manual dispatch remains
unqualified; a chat instruction is not evidence that it reached Unreal. The
next native launch must establish actual camera readback and receiver evidence.

### Launch and receiving-client verification

The owner-facing [PowerShell launcher](../../scripts/ue/Start-YacsRemoteFromGitHub.ps1)
can run on a computer with PowerShell 7.4+ and GitHub CLI; Unreal remains on
the existing trusted Windows host. Authenticate `gh` as `karnalooch` with
repository write access, close the previous owned session normally, then run:

```powershell
pwsh -NoProfile -File ./scripts/ue/Start-YacsRemoteFromGitHub.ps1
```

`-CheckOnly` performs reads without publishing or launching. A normal run reads
the current PR #470 HEAD and creates one **content-identical checkpoint commit**
with that HEAD as its sole parent and the existing `[level-editor-review]`
marker. It rechecks the branch and updates it without force; a concurrent
forward update is rejected. An uncertain write is never automatically retried.
No local checkout, token embedded in the script, Editor termination or new
dispatch mechanism is involved. The existing PR-wide path diff still includes
the Material Forge reference workflow's admitted paths, so its synchronization
event retains the reference gate even for the unchanged-tree checkpoint.

The printed commit and workflow links identify the requested launch. Publication
does not establish an Editor, browser frames or a viewer URL: read the actual
run artifact for those observations. This launcher uses the supported push
trigger while the branch-only manual dispatch remains unqualified.

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

The two startup name filters admit only the observed generated-name shape:
`PythonTypes.YacsRoadMaterialPreview_0x` followed by eight uppercase hexadecimal
digits, and that same name followed by `.preview` or `.Preview`. This is the
preview's bounded admission policy, not a universal UE naming guarantee.
The config-facing patterns spell out eight consecutive `[0-9A-F]` classes.
This is equivalent to `[0-9A-F]{8}`, whose braces disappeared between the
authenticated startup file and the `3ecc90f` native property readback. The
pure Python identity validator retains its original quantifier. Filter
diagnostics retain bounded values with explicit lengths and truncation flags.
Before defining the owned class, the live filtered registry catalog must be
empty. After registration it must equal exactly that class's native schema.

The installer reads the owned native class's name, path and outer name. The
outer must be an ordinary bounded absolute package name whose final segment
is `PythonTypes`; its full package root is read, not guessed. The generated
class name and full class path must agree with that outer. The derived toolset
name must equal the native schema's top-level name and the tool's prefix.
Those four identity fields are recorded in `ready.toolset_identity`, covered
by the launch receipt's existing hash and rechecked by later native guards.
The client uses the same identity validator and still requires the actual MCP
`tools/list` to equal the one authenticated tool descriptor. An additional
tool, a different generated class or an old unqualified name blocks the call.

Legacy-library checks resolve the native engine/editor base classes by their
pinned paths. The candidate enumerates actual native objects through both
[ClassIterator(Object)](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ClassIterator)
and [ObjectIterator(native Class)](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ObjectIterator),
each required to complete within 32,768 elements without duplicates or errors.
Every class from the first iterator must occur in the second with the same
native object identity. An additional object is admissible only when its actual
metaclass derives from the literal core Class, its metaclass CDO has that same
metaclass, and the candidate is exactly that CDO. This uses the documented
[object/class/CDO relationship](https://dev.epicgames.com/documentation/en-us/unreal-engine/objects-in-unreal-engine),
not a name prefix or a substituted Python wrapper. CDO lookups concern only
these difference objects' metaclasses, never every represented legacy class.

Native inheritance over the complete first set must return exactly the two
source-verified abstract legacy bases. Missing or redirected classes, incomplete
coverage and any additional legacy descendant block startup. The same complete
cross-check remains active during preview. Its per-read counts may change after
the owned Python tool class is registered; only the two-base legacy result is
required to remain unchanged between reads.

The `f115173` and `b92890e` production attempts failed during the
Python-to-ClassProperty conversion without identifying their candidate.
The `b92890e` diagnostic checked only the first 256 ObjectIterator elements and
did not reach that failure. The observed core Class CDO does not establish the
cause. The corrected production path therefore retains candidate identity and
operation context before each disputed inheritance/coverage call, separately
from its native error and bounded diagnostic rescans.

The joined preflight also records the literal Python-remote getter and existing
material/capture API checks independently. Any required failure produces the
combined controlled `BLOCKED` report before owned tool registration, refresh or
server startup. Bounded diagnostic comparisons cannot grant admission. Epic's
viewport streaming may already have started before this Python bootstrap runs,
so this is specifically an owned MCP admission boundary. The `badb984` native
paint qualification passed this boundary and the subsequent material chain.

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

The receiving-client correction requires an actual nonempty executable readback
before recording a process identity. It holds the original process handle and
waits at most two seconds inside the existing 80-second discovery budget.
Only final cleanup may use the existing 88-second boundary to admit a child
created before its held parent's exit. PID and every start-time tick must remain
equal. The root's observed path must match
the selected Edge executable. Listener checks and cleanup use the same exact
identity comparison, with bounded expected/observed diagnostics. A missing path
is never filled from the requested launch path. The correction has local
PowerShell contract tests; actual Windows receiving-frame validation is pending.

The failed `badb984` receipt records a root with a null executable and refused
cleanup. A later browser-only retry still needs the fixed debug port 9237 to be
free and a fresh output/profile directory. Any remaining old process needs a
fresh exact identity readback before it can be closed. Keep the retained
material launcher checkout and Editor unchanged while qualifying the receiver.

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

## Local live controls — M3 #473

The local panel candidate uses the existing material client against an already
authenticated, handed-off editor. It starts no editor, performs no build, and
does not use browser automation or Computer Use. Start it from a checkout whose
HEAD and client/helper bytes still match the session launcher:

```powershell
python -m scripts.ue.level_editor_live_panel --session-token TOKEN
```

Open `http://127.0.0.1:18785/`. The panel embeds the existing viewport stream
at `http://127.0.0.1/`. The owner navigates manually; camera preset buttons are
omitted at the owner's request. Three fixed edge-marking material presets and
original-material restore use the existing exact-process,
sequence, immutable-source and saved-package checks. Successful material changes
also return the verified native PNG. Camera and restore results clear the old
PNG so it cannot be mistaken for a new capture. HTTP availability and native PNGs
alone do not establish received browser video frames or owner visual acceptance.

Script callers can POST JSON to `/api/preview` with Content-Type
`application/json` and Origin `http://127.0.0.1:18785`. The complete body is
`{"action":"edge","preset":"warm"}` (or `cool` or diagnostic `magenta`),
`{"action":"camera","preset":"road"}` (or another listed camera preset), or
`{"action":"restore","preset":"original"}`. `/api/status` checks the
retained session and `/api/frame.png` returns the latest material capture with
caching disabled. The listener is loopback-only and rejects foreign Host/Origin,
unknown actions, arbitrary paths/coordinates, extra fields and oversized bodies.
Requests are serialized; native failures are never retried automatically because
a failed confirmation can follow an applied edit. Original receipts remain under
`Saved/RuntimeProof/LevelEditorLivePanel/TOKEN` in the panel checkout.

Keep the client checkout HEAD pinned while this session is open. This initial
panel does not add rock spawning, arbitrary texture replacement or persistent
saves. The bounded surface candidate below adds named asphalt/shoulder previews. Those #473 capabilities still need their existing
#368/#364 source, placement and native gates; #473 is not complete merely because
the current material/camera panel works. No restart-free loading of new native
bridge capabilities is claimed.

### Surface preview extension — local candidate

Owner authorization on 2026-10-11 covers one scripted editor restart to load
bounded asphalt/shoulder previews. The already running paint-only session cannot
load this module remotely. Subsequent named surface changes use the same native
process and official MCP tool; no arbitrary Python or paths are exposed.

The `surface` action accepts only `worn` and `strong`. It uses retained source
textures in transient material graphs, preserves original bindings, and returns
native parameter/binding readback plus the existing verified capture. Global
`restore` restores asphalt, selected shoulder slots and paint together. The
new module is authenticated against the exact launcher commit and its native
ready receipt. Package/source byte conservation and dirty-state checks remain.

These controls are material presentation, not a repair for raised support walls
or road/contact geometry (#459). They do not save assets, move actors, change
terrain/physics, or admit final visual/performance acceptance. Native shader and
received-frame verification for this candidate must be recorded before claiming
live delivery. Source-only tests do not satisfy that proof.

Owner interaction update, 2026-10-11: normal startup no longer cycles paint or
camera presets. Those unchanged native regression checks require the explicit
`-QualifyPreview` switch; otherwise their receipt status is `NOT_RUN`, never
PASS. Stream reception remains checked. The panel shows the live stream only,
without a comparison-image section. The currently loaded bcb702ac bridge still
captures material operations internally; removing that requirement needs a
separately loaded bridge revision and is not claimed for the active session.

Native local candidate evidence: launcher `bcb702ac0bdff21a1860b7abda162b4e73f602d2`,
session `y473surface02`, editor PID 10860. The `worn` surface request
`panel-8ab9664156ec424cacce0716b5a44ae4` completed at sequence 10 with 186
read-back bindings; saved/source fingerprints and dirty package inventories
were unchanged. The resulting Lit capture was inspected and showed cracks,
patch variation and the shoulder transition. A separate scripted Edge receiver
confirmed increasing received frames after the change. The stronger preset and
native surface restoration were not run after the owner stopped comparison
cycles; their offline tests are not native proof. Owner acceptance remains
`PENDING_FINAL_M3`, performance `DEFERRED_AFTER_M3` / `performance_pass: false`.
The later opt-in startup qualification change has parser/docs validation only;
it has not been loaded into the currently running editor.

### Bounded shoulder geometry candidate — #459 / #473

On 2026-10-11 the owner explicitly authorized a script-only bridge extension and
restart to correct the observed shoulder steps while preserving asphalt
alignment. This is separate from #364's material-only conservation claim.
The candidate repairs a bounded camera-near ordinary support from authenticated
frozen source and native Landscape contacts. It excludes special structures;
it must preserve the complete road buffers, Landscape and saved packages.
Original support mesh references are retained for rollback. No camera tour,
before/after screenshots or automatic comparison cycle is requested.

Interactive material requests now explicitly set `capture:false`; the capture
pipeline remains available only when requested for qualification. Geometry
requests never capture or move the camera. Native readback and exact source
identity remain required for action completion. Unit tests are not run in this
iteration at the owner's request; do not report their status as PASS.


### Live script revisions and recovered operations — #473

Owner authorization on 2026-10-11 extends the live bridge with script reload
and recovery after errors. It supersedes mandatory comparison captures for
interactive changes, not source, native identity or world authority gates.
The stable bridge loads only the fixed material and shoulder modules from
an explicitly staged local Git revision. Existing native object references,
viewport and stream remain owned by the same Editor process. This is not a
general remote Python endpoint or a promise that native plugin changes reload.

A failed operation is not successful. Only a verified rollback with unchanged
saved/source fingerprints and dirty inventory may produce `RECOVERED`; the
error remains in the immutable history. Uncertain/failed rollback stays blocked.
Hot reload is restricted to the compatible instance-state ABI; changes to the
stable bridge itself still need installation/restart. Native results for this
revision are pending; unit tests remain NOT RUN at the owner's request.


Native local execution on 2026-10-11: baseline
`b0c0c407be8694dfe5582b7b74f18e9289a9cd73`, session `y473live01`,
Editor PID 33524. Sequences 1 and 3 returned `RECOVERED` after bounded
contact failures; exact rollback and saved/source/dirty conservation were
confirmed. Sequences 2 and 4 reloaded committed handler revisions without
restarting that editor or moving its camera. Active handler revision:
`a5b0d4f53a14c4867bf7ed2387443b1bc1834ddc`.

Sequence 5, request `panel-fc47e4cb9d1f4d3aa34d82364cd6cffa`, completed
the local support112 correction: 491 vertices, including 222 wall vertices,
maximum vertical displacement 39.395 cm. Complete asphalt buffer digests,
Landscape and saved/source fingerprints remained unchanged. 47 contact samples
were deferred because their contact exceeds the bounded operation or lacks a
bounded Landscape hit. This is a local partial contact repair, not whole-road
geometry acceptance. Authored normal/UV overlays remain original; corrected
slope shading is not admitted. No screenshots or camera comparison tour ran.

The panel listens on 127.0.0.1:18785. Repairs and material previews remain
transient and are not saved assets. General object/rock authoring is not
implemented: the retained snapshot lacks the catalogued rock mesh and an
eligible #368 Sa Calobra placement selector. Historical Alpine scatter is not
a substitute. Final M3 visual acceptance and performance remain unchanged.

### Explicit saved checkpoint and current native result — 2026-10-11

The owner subsequently authorized the required tests and one installation
restart for the explicit `checkpoint` action. The earlier NOT RUN statements
above describe earlier iterations only. Ordinary surface and repair actions
remain transient; `checkpoint` creates a new derived map with persistent
materials, preserving the live source world and stream. On failed checkpoint
creation, only the five exact revision-owned output package names may be added
to the dirty inventory; all pre-existing dirty entries and source hashes must
remain unchanged. Failure is RECOVERED only when live state is conserved.

Session `y473save01`, launcher `6c823eaaeec859cb4c7ae9db52fd82a065351018`,
Editor PID 14704: repair and worn surface completed as sequences 1 and 2.
Sequence 3 failed because UE 5.8.2's scalar setter returns false even after
assignment. Recovery preserved the active scene. Revision
`2a00f7ebba403cf7cda663bc6fa303c7d72e891b` replaced that unreliable return
check with parameter inventory and exact native scalar readback. Sequence 4
reloaded it without restarting UE; sequence 5 saved the derived checkpoint.

Saved map: `/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface`.
Native request: `panel-ac7fe7ff172d4e7b91eb47dbe7aec03b`.
The five saved packages contain 186 persistent surface bindings and 559
exact-compared dynamic meshes. Map SHA-256:
`cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a`.
Receipt and packages are retained in the live snapshot under
`D:/yacs/work/level-editor-review/b9fddea3f602-y473save01/Content/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/`.

The new viewport AOI changed 654 vertices (302 wall vertices), maximum
39.395 cm, on support112. All 50 deferred contacts are on outer column zero.
This is still partial geometry repair. Do not stretch the narrow shoulder down
a 0.57–2 m cliff or enlarge the displacement cap. Source-bounded outer earthwork
and actual contact/overlap diagnosis remain #459 work. Both-sides/world-wide
repair, corrected normal shading and final visual acceptance are not claimed.

Local tests: bridge/client/panel 102 PASS, two Windows symlink capability skips;
surface/shoulder 19 PASS; saved consumer/shoulder material/source preflight
73 PASS. A regression rejects a scalar setter whose actual readback differs.
Fresh-process saved-world reload remains NOT RUN: the existing proof launcher
requires an idle host and must not interrupt the owner's live editor. This
local saved checkpoint is not remote backup, protected CI or #364 completion.

### Both-side contact diagnosis — #459, 2026-10-11

Owner request: remove the remaining shoulder steps on both sides, scripts only,
without changing asphalt geometry or restarting UE. Base implementation
`b2e5ed7d9e1f5ba73fba8f91d3573a4ce2b12fa1`; domain `road-earthworks`.
The active owner-selected correction is now support022, not support112.

Handler `ae9511aaa3c33862b60a9a0fe6f086c1a8a4df8b` loaded into the same
Editor PID 14704 at sequence 8. Sequence 9, request
`panel-f4c0f2a861584746aaa8b9099b0fcdb5`, performs a read-only audit of
the existing active repair when `repair` is submitted again. It does not claim
another geometry repair. The panel keeps its ordinary repair button disabled
while a repair is active. The audit samples both original source outer edges
against actual native Landscape collision over a wider +/-20 m read-only ray;
the mutation displacement cap remains 50 cm. Its receipt is immutable in the
normal bridge history and does not rewrite previous observation dictionaries.

Native results, support022, original 0.5 m shoulder width:

| Source column | Samples / rows | Landscape minus source shoulder Z | Missing hits |
|---|---|---|---|
| 0 | 119 / 33–151 | -16.414 to -9.503 cm | 0 |
| 26 | 119 / 32–150 | -306.933 to -11.387 cm | 0 |

Of column26's 119 samples, 103 exceed the existing displacement limit.
The audited existing repair bounds, local UE centimetres, are
`[52453.870,50790.942,45667.162]` to `[58289.298,52834.550,46134.353]`.
All source/saved fingerprints and the asphalt mesh remain unchanged. Six
focused planner/audit tests PASS; no second restart and no camera movement.
No additional visible geometry correction is claimed by this diagnostic.

Proposed next scope is a separately owned local shoulder-to-terrain transition,
not stretching the 0.5 m shoulder down a 3.07 m drop. It requires source-ground
profile and exclusion/overlap checks, stable pavement interfaces, explicit
footprint/topology/normal/collision deltas and rollback. The owner has been
asked to extend #459 beyond the existing width/displacement operation. Until
that decision, no new fill, wider geometry or Landscape edit is authorized by
this diagnostic; global Base_DTM and canonical road remain protected.
