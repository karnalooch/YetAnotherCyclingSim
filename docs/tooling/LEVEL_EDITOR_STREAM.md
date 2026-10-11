# M3 Level Editor streaming review

**Scope:** owner-requested viewport review for #364 / PR #470, inside M3.
**Status:** bounded same-process paint preview **PASS**; automated browser
video qualification remains pending. The latest recorded
[Editor run at `e4bac543`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38141538137)
retained session `38141538137-1`, Editor PID `46540`, and restored the original
370 material bindings. Its Edge receiver failed with
`Cannot convert System.Object[] to System.Uri` and observed no browser frames;
the overall job is **FAILURE**. The owner's Chrome observation is separate
manual viewport evidence. Exact-SHA
[CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38141543196)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38141542405)
passed. On 2026-10-11 the owner confirmed this session was closed and authorized
publication of the next checkpoint. The receiver correction and camera controls
require their own new native proof; the previous paint proof does not admit them.
The Zen warning follow-up is closed by the owner's confirmation. The
[workflow review](../experiments/sa-calobra-road-materials-20261011/workflow-review.md)
records the authenticated evidence, measured client durations and remaining
receiver correction. Paint preview does not grant final M3 or performance approval.

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
