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

The first cadence, launch-order and authenticated b9fd retarget changes were
published at `c62bbc3e7dcdd9ccaad9b2facef477323413e279`. Protected CI
[38121749832](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38121749832)
passed; both complete material workflows actually skipped the ordinary push.
The owner subsequently authorized implementation of the persistent MCP preview
and stream integration on 2026-10-11. The candidate adds the native operation,
bounded client, initial two-call qualification and later manual requests.
Live qualification remains pending at this code checkpoint; its eventual
runtime outcome belongs in the launch artifact and PR description. Cache
relocation is not claimed as a completed runtime capability.

Candidate qualification before launch: 75 focused local tests passed across
the bridge, client, preparation, workflow admission and workspace configuration;
the changed PowerShell scripts and four workflow blocks parsed successfully.
Independent Proof QA closed the partial-mutation recovery and separate-client
checkout findings. These are code/contract results, not native MCP or received
stream evidence.

The first native launch at `c51801d` passed exact-SHA protected CI and the
Blender reference, then [stopped during snapshot preparation](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38123952484),
before any Editor process started. The path/open-handle metadata comparison
reported `source was replaced before opening`. CPython documents different
Windows `st_ctime_ns` meanings for `stat` and `fstat` [E9]; the first failure
log does not record the tuple fields and does not establish an actual file
replacement. The preparer now compares device, inode, size and modification
time across those APIs on Windows, while retaining complete before/after
checks within each API, pinned byte hashes and independent-copy checks.
Its receipt records the Python version and observed cross-API timestamp
differences so the next native launch can establish whether that case occurs
on this host. Live material and streaming qualification remain pending.

The [next launch at `cae5c07`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38124969667)
established the Windows correction on the real host: Python 3.12.10 copied
278 files / 758,655,493 bytes with 147 cross-API `ctime` differences, preserving
the original hashes and independent copies. The correct saved map and camera
were read back in UE 5.8.2. Bridge installation then failed because the generic
settings wrapper did not recognize `auto_start_server`; the launch flag
`-ScriptErrorsAreFatal` converted the Python exception into an engine fatal.
The candidate now uses the exact native UPROPERTY names, and a handled
bootstrap failure publishes `BLOCKED` without rethrowing into that fatal path.
The host still rejects failed/dead sessions and never hands them off. Actual
Python access to the literal native `bRemoteExecution` property remained a hard
pre-listener check after this run; it was subsequently confirmed at `b92890e`.
Missing access cannot default to a claim that remote execution is disabled.

The owner also reported a Zen warning. The retained Editor log shows Zen using
its existing C: data directory, reaching HTTP and ZenLocal `OK` after 34.962 s;
it contains no Zen warning/error text. The exact UI warning was not retained.
On 2026-10-11 the owner confirmed that the warning no longer appears and asked
to close that follow-up. It is closed on the owner's confirmation; the original
message and cause remain unestablished. The 30.01 GiB reported by that launch's successful CI
measures D:, not the C: cache volume. The next launcher records free bytes on
both volumes, the existing resolved workspace cache and inherited
`UE-ZenDataPath`, without moving data or changing either value. The MCP failure
has its own explicit traceback; it is not attributed to Zen. This run produced
no material request receipt, PNG or received-browser-frame proof.

The [third launch at `8caf82e`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38126488782)
passed protected CI and the Blender reference; Windows reused the verified
C++ binaries without compilation or a cache purge. Snapshot preparation and
the map/camera readback passed. The literal MCP getters worked, then the
registry settings check found empty `AllowedNames` and `BlockedNames` arrays.
The controlled `BLOCKED` receipt preserved that diagnosis; the retained log
contains no engine fatal. The literal Python-remote getter and actual catalog
were not reached, and there was no MCP request, preview PNG or owner handoff.

The startup correction moves the existing Editor settings payload into the
fresh snapshot's additional `Config/DefaultEditorPerProjectUserSettings.ini`.
Epic documents this default-file hierarchy and array merge operations, and
explicitly excludes arrays from command-line property overrides [E10]. The
registry must receive its filters before subsystem initialization. The new
file cannot replace an existing overlay; all six original project/config pins
remain unchanged. Runtime settings, catalog and listener checks remain the
qualification gates. The earlier empty readback does not by itself establish
the internal parser behavior that ignored the Saved-file entries.

This third run also measured 82.2569 GiB free on C: and 28.4748 GiB on D: before
launch. The workspace resolves `D:\yacs\cache\Zen`, but the launching process
had no `UE-ZenDataPath`; UE used the existing C: data directory. Zen reached
HTTP and ZenLocal `OK` in 2.352 s. The log contains no Zen warning/error text,
so that run did not establish the earlier UI warning's cause. The owner later
closed the warning follow-up as recorded above. The authenticated
[four-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38126488782/artifacts/11697682730)
is 66,467 bytes, SHA-256
`a93e74c1e94afbcae084892f2fae1726f9c416f159ca5aaa4334e7630bd8afaa`.

The [following launch at `60b53b5`](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38127442726)
passed the actual settings/allowlist check. Startup registered zero stock
tool adapters, compared with four before the default-INI correction. The next
step failed before calling the class iterator because `unreal` did not export
`ModelContextProtocolToolLibrary`. That missing Python attribute does not prove
the native base or its subclasses are absent. Legacy-library enumeration must
resolve the pinned native class and retain its complete inheritance check.
No own MCP listener, literal Python-remote readback, preview request or owner
handoff was reached. The controlled failure produced no engine fatal in the
retained log; Zen again reported `OK`, with a 2.502-second initialization.
The [artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38127442726/artifacts/11697204179)
is 66,818 bytes, SHA-256
`a16dd0f7d177cec55f0835ffa7efef8f28f9d4bb992103b6995ed44182be49f3`.

At `f115173`, the correction resolved the core UClass type and both legacy bases
by exact native paths. `ObjectIterator` accepts a native `Class` [E11], but this
does not establish that every iterated object can be converted to a function's
ClassProperty. All 26 bridge tests and an independent 15-case registration
review passed; the [actual native attempt](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38128418393)
failed when `MathLibrary.class_is_child_of` rejected `TestClass` during argument
conversion. The traceback does not identify the candidate or establish failure
of the parent argument. This is a real native API gap, not a qualified census.
The literal Python-remote getter, generated schema and requests were not reached.

Exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38128420822)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38128420326)
passed. Windows recorded `compileKind=none` and verified-equivalent binary reuse;
both full material proofs skipped. The [four-file native artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38128418393/artifacts/11699010691)
is 66,988 bytes, SHA-256
`5da472dbc6e24ab7a595ce773a64209ba3bcb8843134f2e99f12e4b86386be7d`.
Its complete Editor log contains no engine fatal. Zen reached HTTP and ZenLocal
`OK` in 2.294 s, with no retained Zen warning/error. The receipt records
88,314,204,160 bytes free on C: and 27,897,995,264 bytes on D: before launch.

The `b92890e` startup collects the existing legacy census, literal `bRemoteExecution`
getter and material/capture API evidence independently before any owned tool
registration. A census failure also records four fixed inheritance control pairs
and candidate identities before calling the disputed API, limited to 256
elements and four retained failures with explicit counts/truncation. Diagnostic
comparison with `ClassIterator(Object)` records at most 32,768 yields, their
representation, duplicate paths and both base memberships; successful completion
does not establish verified native coverage. Neither diagnostic can admit a
session or exclude an object from the production census.
Any failed required check remains controlled `BLOCKED`; the existing scene and
host receipts retain the combined bounded report. This gathers the next read-only
boundaries in one attempt without allocating a MID or changing a material.
Pixel Streaming starts earlier in the existing launcher, so absence of an owned
MCP listener does not mean absence of the separate streaming listeners.

The [actual `b92890e` launch](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38130290871)
confirmed `bRemoteExecution=False` and passed the material/capture API checks.
All four inheritance controls returned `True`. The diagnostic
`ClassIterator(Object)` completed with **10,109 native Class objects**, no
duplicates or errors, both pinned unexported bases present and exactly two
legacy inheritance matches. This one iterator did not prove complete native
coverage. Production remained `BLOCKED` on the ClassProperty conversion.
The separate ObjectIterator diagnostic tested 256 elements without a failure
and stopped at its declared limit, so the actual bad candidate is still
unidentified. Observing `/Script/CoreUObject.Default__Class` and its native
metaclass does not establish that it caused the original failure.

Exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38130294134)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38130293828)
passed; Windows again recorded `compileKind=none`, verified-equivalent binary
reuse and no cache purge. Both full material proofs skipped. The authenticated
[four-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38130290871/artifacts/11698804381)
is 70,009 bytes, SHA-256
`a867084630d3076d82a286878473800ce43f16441c494753ab2b6051faab183d`.
It records preparation of the independent 278-file snapshot and controlled
failure in Editor PID 18496, with no engine fatal in the complete retained log.
Zen reached HTTP and ZenLocal `OK` in **2.477 s**, with no retained warning/error.
Free-space readback was 91,468,234,752 bytes on C: and 26,560,012,288 bytes on D:.
The inherited `UE-ZenDataPath` was absent; actual Zen data remained on C: while
the existing workspace configuration resolved `D:\yacs\cache\Zen`.
There was no owned MCP listener, material request, PNG or owner handoff.

The next correction checks complete native coverage with both iterators [E11,
E12]. Each must finish within 32,768 unique objects. Every ClassIterator object
must also exist in ObjectIterator with the same native identity. A difference
is admissible only when its actual metaclass is a native subclass of core Class,
the metaclass's CDO has that same metaclass, and the difference object is exactly
that CDO [E13]. Only those metaclasses require a CDO lookup. A name beginning
with `Default__`, absence from ClassIterator or a best-matching Python wrapper
cannot admit an object. All other differences, errors and incomplete reads
block. The first complete set still must contain only the two source-pinned
abstract legacy bases as inheritance matches. Every later guard repeats the
complete cross-check; it does not pin the global class count across registration
of the owned Python tool class.

The production path also records the actual candidate identity and operation
context before disputed native calls, retaining that first failure separately
from its native error through report compaction. This removes dependence on a
256-item diagnostic rescan for finding the original failing candidate. These
are implementation requirements; the corrected census and persistent preview
still need native qualification. No request, capture or handoff is inferred
from the successful independent preflight checks.

The [actual `5fa5d09` launch](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38131946787)
passed the complete native cross-check, literal Python-remote and material API
preflight, and constructed the preview manager. The next availability check
blocked after UE logged registration of
`PythonTypes.YacsRoadMaterialPreview_0xF5C3E262`. That name does not match either
current exact allowlist entry. Pinned source shows that registration applies
name filters before reporting success; an excluded handler is unavailable to
registry lookup. Both bridge and client also require the old unqualified tool
name, so changing only the INI would be incomplete. The exact naming, schema
and result contracts require additional installed-source excerpts before the
next native attempt. The existing filesystem-only `domain_extension` probe now
retains four fixed, already inventoried files within its unchanged output cap;
the `[mcp-domain-source]` HEAD marker selects that focus on a source-probe push.
This read neither launches UE nor activates a tool.

Exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38131949269)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38131948773)
passed. Windows recorded 23.77 GiB free on D: and verified-equivalent binary
reuse with `compileKind=none`; both full material proofs skipped. The
authenticated [four-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38131946787/artifacts/11700275116)
is 67,361 bytes, SHA-256
`6790f9d685bac909741d43b61153173450023a41a8333d0c2f465e5a5e3d316b`.
Editor PID 26240 ended in controlled `BLOCKED`, with no engine fatal in the
complete retained log. Zen reached HTTP and ZenLocal `OK` in 2.511 s, with no
retained Zen warning/error. Before launch, C: had 91,470,360,576 free bytes and
D: had 25,218,703,360. The ready receipt was not written, so no successful
census counters or excluded identities from this run are claimed. There was
no owned MCP listener startup, material request, PNG or owner handoff.

The [source-only `1b2e2ea` run](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38133509018)
succeeded without an Editor process. The existing probe read 322 files /
2,536,440 bytes and retained all four requested bodies completely, totaling
811 lines. Their hashes match the earlier inventory. The authenticated
[two-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38133509018/artifacts/11699349641)
is 40,023 bytes, SHA-256
`efe51894ab0f370df8face4a8f7b4e801a6c2326f894dcfcb4aafc0fe8864a69`.
Exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38133513325)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38133512817)
passed. Editor launch and both complete material workflows skipped.

The complete source confirms the naming defect: `GetToolsetClassName` combines
the actual class name with a qualifier derived from its actual outer; schema
generation then prefixes the tool function with that name. It supplies no
metadata hook for restoring the previous short name. `Find` returns a handler
only when it is enabled by the registry filters. The actual MCP adapter copies
`name`, `description` and `inputSchema` directly, so no schema-field translation
is required. The known reflected FString serialization remains covered by the
client's existing single JSON-string unwrap; no speculative result-wrapper
fallback is added.

The naming correction uses a bounded startup pattern for the observed
`PythonTypes.YacsRoadMaterialPreview_0x` plus eight uppercase hexadecimal digits.
It binds the exact native class name, class path and actual outer to the
derived toolset name; it does not guess the full outer's package root. Native
schema and client descriptor must belong to that same identity. A preexisting
enabled handler is rejected by a required empty catalog before declaring the
owned class; the later catalog must equal exactly its native schema. The
existing hashed ready receipt carries the four identity fields to the client,
which still compares the complete actual `tools/list` descriptor. These are
implementation checks awaiting the next real preview qualification.

At `3ecc90f`, exact-SHA [CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38134673382)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38134672975)
passed after 74 full bridge/client tests and independent 26-test focused QA.
Windows recorded `mode=static compileKind=none reason=verified-equivalent-proof`
with 22.11 GiB free on D:. Both full material proofs skipped. The
[Editor attempt](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38134669588)
opened PID 8732 and ended in controlled `BLOCKED` at the initial registry
settings check. This attempt did not reach census, registration, an owned MCP
listener, requests, captures or owner handoff. The complete log contains no
engine fatal; local Zen reached HTTP and ZenLocal `OK` in 2.636 seconds.

The [four-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38134669588/artifacts/11700802022)
is 67,446 bytes, SHA-256
`bedb34ff231237dda0a09a97db80f6058e081f53f0242ef108f397f5a5b0757d`.
Its original session JSON is 8,316 bytes, SHA-256
`8de19b374cb5e6e97fd2a8e22c43be052d664a2441305bc6210c9c6e4ae2d743`.
The written INI was independently reconstructed from the exact launcher:
465 bytes, UTF-8 without BOM, CRLF and final CRLF. Its hash equals the launch
receipt's `1731c3ee10f4aeab170eb5c2e8cb650c51f330da23e7cafc99909c9fa405b333`;
both `{8}` quantifiers and end anchors are present. The first native property
value has lost its braces. The missing end of the second displayed value is
only the bridge's 64-character diagnostic truncation, not separate evidence
of a lost anchor. The exact internal UE transformation is not established.

The correction replaces each config-facing repetition quantifier with eight
explicit `[0-9A-F]` classes in the launcher and bridge. The admitted set of
names remains identical; exact native setting equality is still mandatory.
The pure Python identity validator is unchanged. Filter diagnostics now carry
bounded values with explicit original lengths and truncation flags, so their
display limits cannot silently resemble another configuration defect. Native
qualification remains pending.

The [actual `9a7be52` attempt](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38135683574)
passed the settings correction and started the owned MCP server. Exact-SHA
[CI](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38135686942)
and [Blender reference](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38135686667)
passed; Windows recorded `compileKind=none` and 20.86 GiB free on D:. Both full
material proofs skipped. Local correction checks passed 53 full bridge tests
and independent 23-test registration QA before publication.

The authenticated [11-file artifact](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38135683574/artifacts/11700609470)
is 83,411 bytes, SHA-256
`9eb7635589911f37635aab7b32eab1575354a1b6ce04447399ffcf49778cc55e`.
Both ready copies are exactly 211,264 bytes, SHA-256
`9a9a014dce5b28adb0f61f1fb4a2cc5f19fb45c99f8796d21391f61a617d0511`.
They bind PID 43736, FILETIME 134361922309269381 and session 38135683574-1.
Complete native coverage now has retained counts: 10,109 Class objects,
10,126 ObjectIterator objects and 17 exact metaclass CDO exclusions. The first
four exclusions are recorded with explicit truncation; exactly the two
abstract legacy bases and zero concrete libraries are present. These counts
do not retrospectively identify the failing candidate from earlier attempts.

The actual class is `/Engine/PythonTypes.YacsRoadMaterialPreview_0x20FFE68B`.
The listener on `127.0.0.1:18784` belongs to that same Editor; the real
`tools/list` is exactly the ready descriptor for its single `.preview` tool,
with one required `request_json` string. The initial readback has 370 unique
original material bindings, no MID, and the retained b9 values within float32
precision. The complete log records initialize, listing and native adapter
dispatch. Local Zen reached `OK` in 2.476 seconds; no engine fatal is present.

One `set` call was attempted. The client then refused `Native receipt schema
differs` and forbade retry. Its 13.875-second duration measures the whole
client entry, not a completed update. The successful text-result parser had
decoded a JSON object, but that object did not have integer `schema_version=1`.
Because the response was not saved before this check, its exact fields remain
unknown. The artifact also does not inventory the native request directory.
Actual mutation, asynchronous captures, rollback and post-call input
conservation are therefore unverified. No second call, received browser frame
or owner handoff occurred.

The existing filesystem-only `domain_extension` read now prioritizes four
known missing bodies: `ObjectFunctionToolCall.cpp`, `ToolsetJson.cpp`,
`ModelContextProtocolToolResults.h` and the exact `tool_call_impl.py` helper.
All paths and hashes were already inventoried (43,544 bytes total). The full
source and byte/output limits are unchanged; no inspected code is executed.
The previous four complete bodies remain authenticated in the `1b2e2ea`
artifact. The runtime response parser stays unchanged pending this evidence.

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
The previous c62bbc3 launcher deliberately disabled MCP/Wingman and Python
remote execution. The new candidate enables only its scoped official MCP
operation; Wingman and Python remote execution stay disabled. The #384 bootstrap
exits after its bounded inspection, so it cannot simply be inserted into a
session that must stay open.

## Prioritized changes

### 1. Explicit complete checkpoints — published and CI-verified

Ordinary branch pushes no longer start full native or source material proof.
The explicit native and source intents retain owner/branch guards and existing
proof bodies. Native still waits for successful protected CI at the exact SHA.
The lock is acquired by the admitted host job. See the authoritative
[cadence contract](../../CI_VALIDATION_TIERS.md#m3-road-material-iteration-cadence).

The Level Editor launch now waits for its own exact-SHA CI and this PR's
independent Blender reference proof before taking the shared host. Otherwise
the persistent review session could prevent a later job from obtaining host
ownership. Existing open-editor protections remain.
The stream target is the latest complete b9fd saved scene; the failed outer
candidate is not relabelled as accepted.

### 2. Parameter preview in the same process — candidate awaiting live qualification

Reuse the current official MCP/private-registry and transient-material patterns.
Start with the existing scalar `PaintRoughness` and vector `PaintColor` on the
known paint consumers. The operation must identify the prepared session, exact map,
checkpoint, owned slots and current values. It must reject conflicting state.

Use one transient MID for the trial, change the allowed scalar/vector and read
both back from the actually bound material. Capture the same existing road
camera after each of two distinct requests. Restore the original 370 bindings;
preserve the camera, unrelated dirty packages and owner edits. Keep the Editor
alive. Qualify both requests with the same PID/start time and map, recording
elapsed time, values, originals and restoration. There is no map load or C++
build between values once this operation is installed. The later request client
authenticates the retained launcher separately from its fresh code-only
checkout. Freeze the launch SHA until owner handoff ends; parameter JSON does
not require a code or documentation push.

Then extend only the controls required by current work: normal strength,
asphalt variation and transition parameters. Some shoulder widths are currently
graph constants, so they need a deliberate parameterization change before they
can use this path. A graph or texture change may still require shader work or
reimport. A new reflected tool declaration may require a one-time build/restart.

### 3. Focused capture — fixed preview candidate, wider view selection proposed

The full-proof GPU host has no standalone focused mode. Its optional controls
follow all 68 Lit poses. The new persistent candidate instead returns a bounded
1280x720 capture from its unchanged viewport for each allowed update. This
explicit preview result cannot satisfy full-area admission. Broader standalone
view selection remains a separate proposal:

| Current question | Existing relevant view family |
|---|---|
| Transverse asphalt bands | 0071 / 0082 with channel and uniform controls |
| Distant white-line coverage | 0083 original and full-mask control |
| Crack normal response | 0112 / 0082 UV0/90 controls |
| Shoulder contact | Separate 0112 and 0081 contact families |

The first two-request qualification is bounded to two final images and six
priming images, instead of the b9 GPU bundle's 336 images. These are different
coverage scopes; the reduced count does not establish a measured runtime
speedup. Preserve readiness, priming, camera identity, native originals and
state restoration. Complete checkpoint coverage remains unchanged.

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

### 5. Use the existing D: cache configuration consistently — partial code correction

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
configuration is verified. A reviewed runner correction now resolves the
configured `cache` value instead of hard-coding `root/cache`; its local tests
passed without creating or moving a cache. It does not change the environment
of an existing listener. No process restart or cache deletion was performed
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
- [E9 — CPython: Windows stat/fstat timestamp inconsistency, issue 157671](https://github.com/python/cpython/issues/157671)
- [E10 — Epic: Configuration file hierarchy and array settings](https://dev.epicgames.com/documentation/en-us/unreal-engine/configuration-files-in-unreal-engine)
- [E11 — Epic: ObjectIterator native Class parameter, Python 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ObjectIterator)
- [E12 — Epic: ClassIterator, Python 5.8](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ClassIterator)
- [E13 — Epic: Objects, native classes and class default objects](https://dev.epicgames.com/documentation/en-us/unreal-engine/objects-in-unreal-engine)
