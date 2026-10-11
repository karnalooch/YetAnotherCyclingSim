# Road surface materials — Issue #364 evidence

**Recorded:** 2026-10-11

**Work item:** [#364](https://github.com/karnalooch/YetAnotherCyclingSim/issues/364), in progress; [PR #470](https://github.com/karnalooch/YetAnotherCyclingSim/pull/470) is Draft.

**Authority:** [Roadmap](../ROADMAP.md), [World Building Bible](../WORLD_BUILDING_BIBLE.md), [M3 policy](../ai/policies/M3_WORLD_OPERATIONS.md), selected through the [documentation index](../README.md).

This is a scoped evidence record, not world or material admission. #363's
[accepted material checkpoint](../tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md)
remains frozen. #384 completed after protected [PR #467](https://github.com/karnalooch/YetAnotherCyclingSim/pull/467)
merged as `88f6b95e007b61a122b6515fe29041e5e3a3f220`; its gate is satisfied.
This work continues #364, not MCP infrastructure.

## Current b9fd saved, fresh and GPU result

Revision `b9fddea3f6023239da98bec7a5107ed1124cf52e` passed
[protected CI 38116301824](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38116301824)
and the complete [native run 38116299783](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38116299783).
The CI Unreal lane reused verified equivalent proof; this does not claim a
fresh compilation or Automation run. Actual native save, separate fresh reopen,
GPU capture and both contact processes exited zero. The selection retained
**68 Lit, 16 crack controls, 16 window0112 and six hairpin0081 final frames**.
All 370 paint overlays, two crack actors, 186 source supports, 185 shoulder
targets and 67,760 selected tops retain their full material/buffer checks.

The [authenticated original subset and role handoff](../experiments/sa-calobra-road-materials-20261011/README.md)
pins artifact 11694637100, 476,694,696 bytes, SHA-256
`d580f706d7b645ada9ebea9244126a30de1d22d88a4a0da5a68594ef6a84f7d6`.
The live artifact identity, archive digest and all 629 extracted file identities
were checked. The independent material reviewer inspected all 68 final Lit
images and 16 crack controls; the road reviewer inspected the contact set.

The asphalt is dry and granular; the two crack canaries are subtle and show no
visible rectangular patch outline. UV0/90 cases and neutral channel comparisons
are present, but the small normal signal does not confidently establish crack
normal-space correctness. The original receipt remains
`normal_space_verified: false`; no network crack distribution or dedicated
edge-erosion proof is claimed. Near white lines are continuous, while distant
pixel gaps, asphalt bands and the hard outer gravel boundary remain open.

The new 0112 `support022-hidden` view removes the lower wall strip and shoulder,
while a separate thin upper line touching the asphalt remains. Source projection
supports attribution of that upper line to the existing 8 cm pavement slab side.
Support022 remains the owner of the lower feature. Hairpin0081 now
retains actual native wall/source CUT observations. Support185 owns its exposed
wall; final native Landscape height and a contact/profile repair remain #459
work. Materials have not repaired that geometry.

The separate **outer terrain + band/paint** attempt at `2ec534c0b62a18b05eb3ce066a151b0d9bb3bc08`
passed [protected CI 38119542097](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38119542097),
with verified binary reuse. Its [native run 38119538994](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38119538994)
failed before save: the prepare process exited 3 after 385.443 seconds, below
its 420-second deadline. Stage records show successful terrain authentication,
then D3D12 `E_OUTOFMEMORY` inside the `terrain.build_surface_terms` interval.
The [authenticated failure record](../experiments/sa-calobra-road-materials-20261011/outer-2ec534c/README.md)
retains the original host/cache receipts and derived stage observations. There
is no new map, reload, band/paint result or PNG, and the precise allocation cause
remains unproved. The strict verifier and source/buffer gates stay intact.

The owner requested [lighter iteration cadence](../CI_VALIDATION_TIERS.md#m3-road-material-iteration-cadence):
ordinary pushes no longer request complete native/source proofs. The corrected
[offline contact analysis](../experiments/sa-calobra-road-materials-20261011/road-contact-source-analysis/README.md)
is source-relative evidence under #459, not an applied geometry repair.
The Level Editor preparer now supports a manifest-only 4 MiB read bound because
the successful b9fd manifest is 3,225,316 bytes; other metadata stay at 2 MiB.
The live stream remains pending a verified current-runtime retarget and launch.

Owner audit stays `PENDING_FINAL_M3`; performance is `DEFERRED_AFTER_M3`,
`performance_pass: false`. This result does not close #364 or #459.

## Historical 56c5 memory failure and separated recovery proof

Revision `56c5dadeadd806c8b6aa58d8508fa20f1ed45457` passed
[protected CI 38113635913](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38113635913).
The Unreal job verified equivalent proof reuse (`compileKind=none`,
`reason=verified-equivalent-proof`); this was not a new build or Automation run.
The [native run 38113632914](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38113632914)
passed preflight, the authenticated baseline and the reversible asphalt canary.
Its offscreen preparation PID 34352 exited 3 after 379.812 seconds, before the
unchanged 420-second deadline. It did not save the map or start reload/GPU.

The closed Unreal log reports an allocation failure for 4,194,306 bytes and
the Windows error that the paging file is too small. At that failure Unreal
recorded `AvailablePhysical=3756032`, `AvailableVirtual=2527232`,
`PeakUsedPhysical=17959821312` and `UsedVirtual=76600205312` bytes. These are
the reported memory counters, not a VRAM measurement or proof that shader
workers caused the exhaustion. Startup and the preceding attempts used three
local shader workers. The authenticated executable and requested arguments
were `UnrealEditor.exe -RenderOffscreen -norhithread -NoVSync`.

The last explicit success marker is the asphalt import/save at 05:17:42.399
UTC. Three later UObject hash compactions do not identify the Python operation
being executed. The log contains neither the newly detailed WeightTex
rejection nor a successful 4033-pixel readback, outer material statistics or a
Python traceback locating the allocation. It therefore does not establish
whether the outer graph or a subsequent scene operation caused the failure.

The independently downloaded ZIP is 206,502 bytes, contains 31 files and has
SHA-256 `32b971feebf7d47dabaeffabc15fa92c5d8a3163073f2a33a7453b71fc899221`.
The prepare log is 382,028 bytes, SHA-256
`016888aa5878993cda92fdb90479419493e92c46632f93a778d899d92637bcb0`;
its identity matches the host receipt. The artifact contains **zero PNGs**
and no reload/GPU result. At that time, 4258 held the latest actual images;
the current b9fd result above supersedes that image availability statement.

The recovery separates existing proof modes. The next native attempt selects
the two crack canaries and contact diagnostics without the optional outer
terrain mode, retaining the established NullRHI save/reload and independent
fresh GPU capture. It must still pass the selected eight-texture completion
barrier, strict 2048-pixel/PBR checks, all 370 paint witnesses and the sixteen
normal/neutral/crack controls. Outer terrain remains pending its own run;
omitting it from this attempt is not acceptance of that feature.

Small flushed stage records now distinguish material verification, mesh
inspection, ordinary/outer material creation, terrain authentication,
recompilation and scene/paint/crack preparation. They read the existing Windows
memory helper, explicitly label unavailable observations and retain bounded
output. Its [GlobalMemoryStatusEx fields](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-memorystatusex)
report available system physical memory and the calling process's available
commit allowance, not process usage or VRAM. They do not configure memory, change a material, extend the
deadline or relax texture, geometry, source, GPU or image requirements.

The same recovery adds the missing #459 owner isolation at 0112. All four
existing camera poses retain baseline, support-112-hidden and local-Landscape-
hidden views, plus a fourth `support022-hidden` view. The current window plan
therefore requires 16 images; the separate hairpin plan remains six. Historical
unversioned twelve-image plans remain readable but cannot satisfy the current
host's sixteen-image prerequisite. The exact nominated owner 022 is checked
against its authenticated 153 source sections, 5,555 vertices, 8,616 triangles
and 7,904 ordered top triangles. The existing bounded native API reads TID and
ordered XYZ, not VID. Its complete returned triangle digest and both supports'
visibility are checked again after restoration. No geometry is moved, and the
new control does not yet identify the dark strip or authorize a guessed height
change. Its actual images and the previously pending hairpin wall/CUT payload
remain required.

The recovery patch passed 142 focused local tests in two suites (105 material/
saved-consumer/host tests and 37 contact/host tests), with actual PowerShell
7.4.13 and no skips. Required Ruff checks, PowerShell parsing and all four
documentation guards passed. An independent contact review also verified the
original 4258 twelve-image window and six-image hairpin receipts against the
current backward-compatible verifier. These checks do not replace the pending
current native capture.

## Prior e81 native preparation failure and wall observations

Revision `e81a4377cc6b8d635c0036adf01fc8427f987ff9` passed
[protected CI 38111920048](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38111920048),
including the Unreal build/Automation lane. The
[native run 38111916743](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38111916743)
passed 409 Windows preflight tests with two supported skips, baseline readback
and the reversible asphalt canary. Preparation PID 46996 exited 3 after
57.556 seconds, before saving the derived map or starting fresh reload/GPU.

The actual traceback reaches the newly reused frozen-Landscape verifier:
`road_shoulder_material._authenticate_terrain` calls
`sa_calobra_whole_map_prep.verify_instance`, which rejects the weight texture's
combined 4033 × 4033 / linear-registration check. It has already resolved all
eleven texture bindings, drained native asset compilation and rejected default
or still-compiling texture objects. The old exception does not retain the
actual dimensions or sRGB value. This is not evidence that a further wait will
fix the problem. The diagnostic now includes the actual native dimensions,
format, mip counts and state flags without changing the rejection condition.

That verifier reads `FTexturePlatformData`, and its earlier #363 4033-pixel
proof ran in `UnrealEditor.exe -RenderOffscreen`. The failed e81 preparation
used `UnrealEditor-Cmd.exe -NullRHI`. The correction runs only outer-terrain
save/reload in the existing offscreen GUI Editor, derived from the authenticated
commandline executable's directory and hashed before/after each owned process.
Legacy save/reload remains NullRHI. The same idle-host guard, serial ownership,
420-second deadline and unchanged geometry/texture requirements apply. The
mode is recorded as requested; a flag does not itself prove the runtime result.
This restores the verifier's proven execution context without claiming that
the unrecorded e81 dimensions or cause have been established.

The same correction closes a separate pre-read gap for crack maps: import and
fresh verification now hold the exact eight selected Texture2D objects through
one existing native `finish_texture_compilation` call before their strict
2048-pixel/PBR readback. The call must return literal `True`; there is no GC,
retry, reimport or settings repair. Its actual API signature is retained in the
import receipt. Synthetic cold-size tests cover both entry points and confirm
that a failed finish, a foreign object or persistent CLAMP drift still rejects
the operation. This is readiness ordering, not an assertion about the unknown
dimensions in either failed native run.

The correction passed 225 local source/material/consumer/GPU/host/shared-prep
tests in 57.427 seconds on Python 3.12 with actual PowerShell 7.4.13, without
skips. Independent host/shared-prep and crack-source reviews found no blocker.
Both changed host scripts parse, the required Ruff rules pass, and all four
documentation guards pass. The next native save/reload and capture remain
required; local fixtures do not grant that result.

The downloaded 31-file native artifact is 204,197 bytes, SHA-256
`4a8d87fe11d242b0cf94e268d3bd419fe96d019dfef0eab5a858c6aa6e7262c0`.
The prepare log is 364,965 bytes, SHA-256
`608372eee970af560e94ebb047f8e9b428e57e41b24ca49ef5c81de408895180`;
all three retained prepare-log references match the host receipt. This run
produced no PNG, crack normal comparison or new native wall/CUT payload.
The earlier 5b99 saved/fresh result and 4258 actual images remain historical
evidence; neither is presented as an e81 render.

The separate [source run 38111916772](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38111916772)
passed at e81. Reader PID 41544 exited 0 in 6.118 seconds using the existing
isolated decoder, without another restoration. The closed wall-contact set
contains 2,398 rows / 2,270 distinct tile-and-point-index observations at
195, 200, 205, 210, 215, 220, 225, 230 and 235 m. The CSV is 417,842 bytes,
SHA-256 `6af3704cc525bcc7282989e74beb061ba6fdec9f3c7492ee6d428ca3b603fb0d`.
Its reader receipt and source manifest also match their host-pinned sizes and
hashes. These are raw source observations, not an applied geometry repair.

## Prior 5b99 results and next material comparison

Revision `5b99f3e16a0ccbbda9dc9c489e61f638d4dc453a` passed
[protected CI 38109506009](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38109506009).
Its [source run 38109503685](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38109503685)
successfully restored the approved isolated decoder and exported the eight
source transects. Setup PIDs 46568 and 9824 exited 0. Reader PID 21104 exited 0
in 6.321 seconds; all retained source identities matched after the read.
The independently downloaded artifact is 622,946 bytes, SHA-256
`e0f55b36bcbd96f00d6f82c54915a99153b401504ccc93e28555d81ce301be25`.
It contains 2,132 CSV rows / 2,037 distinct tile-and-point-index observations.
The CSV is 371,067 bytes, SHA-256
`e96a54f7b90bcafe03a33cd523ee4d6cb714c7af1e8571d93ac950b11a1a3946`;
the reader receipt is 25,011 bytes, SHA-256
`f463e70ac0b76edd90a471199ab3cfcdf8251f61b0fcbdb09cb148146185303d`.
This supersedes the earlier missing-environment outcome; it does not fit or
admit a road profile. Original geographic inputs remain unchanged.

The observed source stations 95–165 m show a localized disagreement with the
existing presentation profile, especially at 110/125/135 m. They do not sample
the separate support-185 wall at 195–235 m. A second closed read-only set,
`wall-contact`, samples 195, 200, 205, 210, 215, 220, 225, 230 and 235 m with
the unchanged ±12 m lateral / ±1 m along bounds and source/CSV/process limits.
The original `hairpin-profile` set remains the default. The host requires
exactly one of `[hairpin-lidar]` or `[hairpin-wall-lidar]` and checks the returned
set name and exact stations. Class 2 is not an asphalt label; no point-class,
nearest-height or minimum-height snap is authorized by an observation receipt.
The [native run 38109503833](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38109503833)
passed 358 Windows preflight tests (two supported skips), baseline, the
reversible asphalt canary, saved preparation and fresh reload. Preparation
PID 26480 exited 0 in 264.795 seconds; reload PID 23568 exited 0 in 146.271
seconds. Both crack actors and all 370 paint overlays passed the complete
saved/fresh buffer and material readbacks. The derived map SHA-256 is
`c5ff9cd05312f7761f79834c85f26b88b330d2007dc8ad04e43f6e3a5d0bca31`;
the saved manifest is 3,225,060 bytes, SHA-256
`0840c8bc87b71942214988061a3748dc34ed18ffb45d58849a0ceb3f35f85d38`.

GPU PID 44636 then exited 3 after 142.506 seconds, before the first capture.
The traceback stops in `road_crack_sources._verify_textures` at its combined
BaseColor size/settings check, called before the per-pose native loading
barrier. The log does not record which observed value differed; asynchronous
texture construction is a hypothesis, not a measured cause. No PNG or new
wall/CUT observation was produced, and both later contact steps were skipped.
The authenticated 44-file artifact is 3,021,662 bytes, SHA-256
`232388075af3bd62e1a769c9b113eca5b8247eba16ee427dfd9c6063877a9f36`.
The closed GPU log is 365,922 bytes, SHA-256
`a2fa78c643119a81493a6298b28aa0c7aad382a028cd38d0894c9aae551946da`;
21 retained file references match their host receipts. This is saved/fresh
success followed by GPU failure, not crack appearance or normal admission.

The correction finishes compilation of the same authenticated 7/15/18/26
material textures immediately after loading the saved map, before reading
their dimensions. It uses the existing native
`YacsTextureAuditLibrary.finish_texture_compilation`, which finishes only the
selected textures and rejects default or still-compiling objects. All original
2048-pixel crack dimensions, CLAMP, colour-space, compression and normal
settings remain mandatory. The verifier now reports every actual setting and
both dimensions separately, including getter errors, so a persistent mismatch
cannot hide behind the old combined message. No retry, reimport or texture
setting repair is performed by this readback.

The next material canary adds a separate opaque gravel-to-terrain variant on
five existing source-owned shoulder tops. It reuses the actual frozen
Landscape's five roles, eleven texture objects, scalar values, weight-map
registration and normal-distance response. The shared graph extraction leaves
the original 146-node Landscape producer unchanged in the regression witness.
No global Landscape material, weight texture, geometry or RVT setting changes.

The camera ordinal is not the support ordinal. The selection is resolved from
the retained 4258 frame `window_id` and the source owner's `material_target`:

| Review camera window | Native source owner | Source window | Selected top triangles |
|---|---|---|---:|
| 0013 | `YACS_PERSIST_SUPPORT_018` | `VIAL_TR70190001272-1-interval-15-tile-1` | 704 |
| 0071 | `YACS_PERSIST_SUPPORT_073` | `VIAL_TR70190001287-0-interval-51-tile-0` | 340 |
| 0097 | `YACS_PERSIST_SUPPORT_093` | `reviewed-VIAL_TR70190001272-1-interval-0-1` | 800 |
| 0112 | `YACS_PERSIST_SUPPORT_112` | `reviewed-VIAL_TR70190001272-1-interval-24-0` | 436 |
| 0082 / Nudo-0 | `YACS_PERSIST_SUPPORT_182` | `nudo-0` | 800 |

Nudo's separate parapet owner 181 is excluded. Supports 022 and 185 retain
their separate contact/geometry diagnosis. The original UV0 inner transition
is independently hashed before appending UV1, whose first coordinate measures
the actual outer-edge distance in centimetres. The final native prefix must
match that intermediate UV0/normal hash. Both rollback stages restore the
original source. Terrain is complete within 1 cm of the outer edge and gravel
within 10 cm, with breakup from the scanned gravel grain; the original inner
0–8 cm transition remains protected on narrow tapers.

Saved and fresh outer-terrain Editors use offscreen rendering; legacy cases
remain NullRHI. Their material statistics are retained as observations,
allowing zero and differences between processes;
they cannot claim GPU compilation. A separate read-only material-statistics
check runs after native GPU readiness, together with a targeted closed-log
check for this material's compile/fallback errors. It does not invent an
unavailable shader-error getter or global shader admission. The added eleven
maps require their own actual mip residency, giving 18 total road/shoulder
textures, or 26 with the two crack canaries. Physical contact and the normal
response still require the actual images.

The separate band diagnosis retains its original eight jobs and hash. An
explicit `[road-paint-controls]` adds two identical-camera Lit jobs at 0083:
the original saved paint and a transient full-mask variant. Only three mask
scalars change; all 370 source-clipped overlays, widths and offsets are
conserved. Every observation reads all 370 native slots and effective scalar
values; complete binding templates occur once to keep the receipt below its
unchanged 2 MiB cap. Restoration checks every original slot and saved MIC.
The 68 Lit cameras, three primings per pose and both control-plan alternatives
remain fixed. Each capture also records twelve actual CVar observations and
GFrameCounter. Missing CVar values remain unknown; these getters do not prove
effective view AA or temporal-history state. New pixel, normal, owner and
performance acceptance remains pending.

The first combined runtime invocation selects the two crack actors and five
outer-blend owners with the existing 16 crack controls, including the neutral
border and WorldNormal comparisons. The separate 8/10 band/paint control
family is implemented and reviewed but remains opt-in for the subsequent
comparison. A run does not claim to have captured both control families.

## Prior af7 outcomes — native setter failure and exact missing LAZ packages

Revision `af7ac202b5d1466db525bae54566e4f7f3b7d95e` passed
[protected CI 38108180813](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38108180813).
Its [native run 38108177261](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38108177261)
passed 348 Windows preflight tests (two supported skips), baseline and the
reversible asphalt canary. Preparation PID 4564 then exited 3 at the first
local crack texture setter's false return, before saving the derived map or
capturing any crack images. The independently authenticated native artifact
is 208,229 bytes, SHA-256
`10e32cbcecb4eaa44ac3616d09c29a0efa85f35ba1d4b372cf1537aaa0ab916f`.
The original traceback names `CrackBaseColorTex`; cleanup removed the new crack
assets and white overlays. This remains a failed native attempt.

Epic's [UE-291403](https://issues.unrealengine.com/issue/UE-291403) documents
false return values from the texture, scalar and vector setters even after a
successful update. The correction refreshes inherited MIC metadata after
assigning its parent, as the existing Material Forge importer already does,
then judges the result by the full native parameter inventory and effective
texture/scalar/vector getters after updating the instance. It does not treat
either boolean as success. Regressions cover successful writes returning false
and ignored texture, scalar or vector writes returning either false or true.
The graph, source textures, placement and normal-review gates are unchanged.
The subsequent 5b99 saved/fresh result passed; its separate GPU failure is
recorded above.

The [source run 38108177248](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38108177248)
passed all 20 decoder/reader tests on the actual Windows host, then correctly
reported `GIS_ENVIRONMENT_UNAVAILABLE` before starting a LiDAR reader. The
registered base is CPython 3.12.10 x64, with NumPy 2.3.5 and PyProj 3.8.0;
only laspy 2.7.0 and lazrs 0.8.2 are absent. The old project venv is absent too.
The base executable is 104,952 bytes, SHA-256
`4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`.
The independently checked [LiDAR artifact 11691365092](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38108177248/artifacts/11691365092)
is 1,418 bytes, SHA-256
`6eeebfe7bd9006ff4e615467e13904744e2ef4859b7fca6324ba1e58e2f7e552`;
it contains the failed host receipt and all three candidate outcomes, with no
point observations or geographic source mutation.

The next `[hairpin-lidar] [restore-hairpin-decoder]` source invocation restores
the already approved isolated decoder described in
[dependency provenance](../legal/DEPENDENCY_PROVENANCE.md#sa-calobra-local-laz-decoder--2026-10-04).
The recovery is restricted to this observed base executable and a new canonical
project `.venv`, using `--system-site-packages` for the existing two GIS pins.
It authenticates the same two approved wheel hashes before creating the venv,
then installs them offline with no dependencies and mandatory hashes. It
refuses an existing target, never modifies the base interpreter, records each
owned process and its actual exit, and reruns all four real import checks
before any source read. Failed recovery remains failed and retains its logs;
the ordinary read-only resolver still performs no installation. Recovery and
actual LiDAR observations had not yet passed at that af7 checkpoint; the
subsequent successful 5b99 result is recorded above.

The next `[shoulder-contact]` diagnostic also retains a bounded subset of the
already read native support-185 triangles at source rows 1560–1880. The actual
outer-top corners identify matching wall faces, including conditional partial
faces; perimeter IDs are not inferred from a builder. Each retained wall
corner selects enclosing nodes from the authenticated source CUT float32
file, with their raw four bytes and offsets. These are source nodes, not an
interpolated or observed final Landscape height. The optional receipt field
is limited to 1 MiB, fails explicitly on ambiguous ownership, and changes no
geometry, material, camera or source file. The historical 4258 contact
contract remains valid; new native wall/source measurements are still pending.

## Earlier observed results — 4258 images and 735 preflight failure

Revision `735f049746da753622b9948251f625331edb772b` passed
[protected CI 38107099181](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38107099181).
Its [native run 38107095697](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38107095697)
stopped **before Unreal**: the real-symlink source fixture raised Windows
error 1314. The host ran 345 tests, with one error and one unrelated skipped
test; it produced no crack scene or image. The replacement fixture separates
real link creation from link/reparse metadata rejection and the independent
outline/border cases. Only unsupported OS link creation is skipped; ordinary
I/O errors still fail. The runtime source guards are unchanged.

The [source run 38107095678](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38107095678)
completed the bounded installed-API read. Seven actual installed files and
four function bodies are retained; the MID header is in `Public/Materials`,
while the Kismet header is in `Classes/Kismet`. The API artifact is 1,691 bytes,
SHA-256 `b48d34df4600acc58c66388f5395dddcbde82fd868e4231206447dfc2f9a7d5e`.
That source run failed only at the subsequent LiDAR step: the recorded project
`.venv` executable was absent, before a child or source read. Actual point
observations are still unavailable. The native preflight traceback establishes
that the existing Material Forge environment uses the Python 3.12 base library;
the earlier local Python 3.14 test version was not a host-version observation.

The next source invocation qualifies only already configured or registered
interpreters: the configured project venv, the calling Material Forge Python,
PATH's Python and absolute executable/home entries in that project's small
`pyvenv.cfg`, if present. Each distinct existing candidate gets one 15-second
read-only child probe. Selection requires actual imports and the unchanged
four package pins, CPython 3.12 x64, matching executable identity and unchanged
bytes after the probe. There is no filesystem scan, package installation,
decoder substitution or geographic source read during qualification. If none
qualifies, the retained result remains `GIS_ENVIRONMENT_UNAVAILABLE`.

The targeted local verification passed 34 source/decoder contract tests, all
14 current workflow PowerShell parses, scoped Ruff checks and all four docs
index guards. The crack fixture additionally passed on Python 3.12 and 3.14;
simulated Windows error 1314 skips only the OS link-creation case while its
independent rejection checks still execute. This is not a new Windows/UE PASS.

The completed 4258 artifact has now been independently authenticated: **523
files**, including all **272 Lit PNGs** (68 final and 204 priming) and **18
contact PNGs**. All 68 final Lit images and all 18 contact images were directly
viewed across the independent review assignments. The ZIP is 412,622,626 bytes,
SHA-256 `fc93cab4b2346781be8d426615ba0bddbbb96be139f0cafc38fc36d7d4cfc075`.
The fixed 68-camera plan is unchanged. Save PID 10560, reload PID 25412,
Lit PID 27076 and both contact PIDs 32956/21760 exited 0; both full readbacks
conserve all 370 white-line actors and original source geometry.

Near white lines follow the source surface and the asphalt has visible fine
aggregate. Far white lines break into dashes in some shallow views, transverse
asphalt bands remain, and the outer gravel/terrain transition is still sharp.
Contact isolation identifies an exposed wall belonging to support 185 at the
hairpin; it does not repair that wall or establish the correct road profile.
See the [complete visual findings](ROAD_SURFACE_VISUAL_REVIEW_364.md#verified-4258-review--all-68-lit-and-18-contact-frames).
Material completion, native crack/normal proof, #459 repair, the owner's final
M3 audit and performance admission remain pending.

## Current joint candidate — local cracks and native capture readback

The next integrated candidate consumes the already verified `07ebafad`
Material Forge outputs without regenerating them. It introduces two small,
source-owned crack fragments: `drifting_interrupted` on 0112 and
`short_oblique` on Nudo-0. The latter uses UV rotation 90 degrees. This is the
native material canary, not completed network-wide crack distribution.

The fragments are clipped against the actual ordered pavement triangles and
their split normals. Their only positional offset is world Z +1 mm; the
complete footprint stays at least 10 cm inside the inner white-line boundary.
Owner/station selection cannot jump to another road level at a hairpin. Two
actors, eight textures and eleven owned material/texture packages are added;
collision, shadows, navigation and physics remain disabled. The saved/fresh
reader rechecks all existing white-line buffers as well as both crack buffers.
The original source geometry and saved checkpoint remain unchanged.

The material preserves the projected base asphalt and adds the local crack
colour, roughness and normal delta. Its diagnostic `NeutralProbe` belongs only
to two transient MIDs; the saved MICs stay at zero. After the unchanged 68 Lit
views, an explicitly requested `[road-crack-canary]` run captures 16 separate
controls: both cameras, each with base/neutral BaseColor, Roughness and
WorldNormal pairs plus the crack Lit and WorldNormal views. The fixed control
plan SHA-256 is
`f6f8a4fef0c10438fee2ee88827f797b9451ebf5d9e1f0b2334f754f593738d8`.
Actual normal-space and rendered appearance remain **pending**, including the
90-degree case. A successful source export, graph test or fresh readback cannot
admit those images.

Independent review identified two capture-reporting gaps and the candidate
corrects both. Every final and priming screenshot now checks the actual active
viewport enum before submission and after completion. The receipt retains
`native_viewmode_before` and `native_viewmode_after`; the host checks them for
all 68 Lit frames and both optional diagnostic plans. Restoration is verified
only with a successful restore status, no cleanup errors and every applicable
material, visibility, probe, MID-reference, package and dirty-content check.
The existing per-shot and total deadlines, fixed cameras and source hashes
remain binding.

Revision `4258aab3527506d64769ecf974dd061d9e580687` passed
[protected CI 38105477966](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38105477966).
Its separate white-line Lit/contact
[native run 38105475021](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38105475021)
has passed baseline, canary, save/fresh, the 68-frame Lit capture and both
contact stages (12 frames at 0112 and six at the hairpin). The full native
workflow is successful. The artifact and full direct image review are now
complete as recorded above; remaining appearance defects are not admitted.

The bounded [installed-source read 38105475097](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38105475097)
retained four actual function observations from two CPP files, then failed on
an assumed `Classes/Materials/MaterialInstanceDynamic.h` path. Its partial
receipt is 4,711 bytes, SHA-256
`da92c72a3b98c243406675e21e9b8609bb22031e2a6e76159458ebe67dc63e9a`.
The observations establish that the buffer wrapper forwards `BufferName` to
`ChangeBufferVisualizationMode`; its own body does not contain the previously
required viewmode literal. The candidate verifies that forwarding together
with the separate real viewmode setter/getter bodies. Header discovery is
bounded to the two documented `Public`/`Classes` layouts and retains the actual
chosen file identity.

The unrelated LiDAR step was skipped after that failed source read. It now
requires successful source prerequisites and a non-cancelled workflow rather
than success of the optional API step. Three isolated executions of the real
inline header resolver passed, including the retained failure when both
layouts are absent. The next source invocation requests `[hairpin-lidar]` and
`[road-api-read]`, without `[road-cracks-source]`. That 735 invocation completed
the API read but found no executable at the old GIS path, as recorded above.
No geometry repair or visual acceptance follows from these workflow changes.

The integrated preflight was also run locally with Python 3.14.8 and actual
PowerShell 7.4.13: **345 tests passed, none skipped**, using the exact 26-module
list from the native workflow. Independent specialists reviewed the source
adapter, clipped geometry, material graph, saved/fresh integration and GPU host.
All 14 rendered inline PowerShell blocks parse; changed Python AST, the scoped
Ruff checks and documentation index guards pass. These are preflight results,
not native crack proof.

## Latest native paint result and remaining diagnostic failure

Revision `e4af3a74bf7f53565acd75b7d9a91a4e6d2d8691` passed
[protected CI 38103790299](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38103790299).
The [native run 38103787193](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38103787193)
passed the baseline, reversible asphalt canary, save and separate fresh reload
with **370 source-clipped white edge actors**. Prepare PID 34996 and reload
PID 16572 both exited 0. The fresh reader rechecked every paint buffer and the
source witness `3e25a18c76cb730c90c30d9b84263d0755b42fe7e85435dd02b50546cb11cd2e`.
This establishes native save/reload conservation; the paint has not yet been
reviewed in rendered images.

The GPU stage failed **before its first screenshot**. The new optional buffer
diagnostic assumed a particular lexical implementation of
`SetEditorViewportVisualizeBuffer`; the installed engine did not satisfy that
assumption. The real GPU Editor exited 0, but the independent host correctly
rejected the failed receipt with zero of 68 final frames and zero diagnostic
frames. Both subsequent contact captures were skipped. No new paint, band or
contact image admission follows from this run.

The original [artifact 11689148232](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38103787193/artifacts/11689148232)
was independently downloaded and verified: 3,004,820 bytes,
SHA-256 `a2f5aa4f797ca27af9ce1ae22888a9db54688198a8d516f4283dd027d033388a`,
46 retained files and no PNGs. The fresh receipt is 2,393 bytes,
SHA-256 `d45e53e74b3aa80129d6caed2b3cdac0c08083703016794cfcb1fcea244571f3`;
the saved manifest is 3,116,093 bytes,
SHA-256 `71e9bc22301070075361e84a06a1f165562f3948544abf4715fa7bd50190d13a`.

The next bounded run requests the unchanged 68 Lit cameras and contact
diagnostics. The optional eight buffer controls now require the explicit
`[road-band-controls]` marker and remain failed/pending until their installed
implementation and actual images are verified. This does not relax the Lit,
save/reload, source, dirty-package or image/owner acceptance gates. A separate
`[road-api-read]` source step retains only bounded installed function symbols,
calls and file hashes; it neither executes native APIs nor redistributes
engine function bodies.

The independently reviewed `[hairpin-lidar]` reader adds eight narrow source
transects through the existing hairpin using the recorded GIS interpreter.
It authenticates all nine retained LAZ files and their real headers before
reading bounded points, retains classification/rejection flags and source
point identity, and rechecks hashes afterwards. It does not fit a road or
modify heights, crossfall, route truth or terrain. Missing decoders/data,
partial reads and deadline exits remain unavailable/failed with retained
evidence. The host owns only its launched process, retains its observed exit
and bounded output even after timeout, and always emits the host receipt.
Fourteen reader contracts and independent workflow review passed locally;
actual source point observations are still pending.

## Current refinement after the f75 visual rejection — 2026-10-11

The owner requested another texture-first Material Forge refinement, followed
by the remaining road/contact defects, with independent specialist review.
The starting technical baseline was `f75e76ba1ecde8a3ac4458557ed51ce60492847c`:
[protected CI 38092749669](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092749669)
and [native/GPU 38092747036](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092747036)
passed. The actual host receipt verifies all 68 planned final frames, 186
support owners, 185 material targets and 67,760 selected shoulder triangles,
with an observed GPU Editor exit of 0 and fresh-reload conservation. These are
technical results, not approval of the appearance.

Direct inspection of the original `window-0112-forward-00002`,
`window-0071-forward-00002` and `window-0081-forward-00008` PNGs confirms the
remaining broad cloudy asphalt, transverse distant repetition, straight gravel
boundaries, the inner dark contact edge and severely dark hairpin shadows.
The retained d91 BaseColor already contains the broad variation. Its dry
shader combines interpolated fields rather than distinct aggregate grains;
the old one-sided 25 cm luma minimum also rewards the rejected broad signal.

The next source candidate changes only `dry_varied`: explicit metric aggregate,
quieter broad colour, and complementary checks rejecting both a flat map and
cloud-dominated variation. The existing four-metre tile, DirectX normal, dry
nonmetallic response, deterministic two-render proof and native source pins
remain required. Historical material variants and provider-scaled CC0
`rock_ground` gravel remain retained. A new source receipt must be independently
verified before updating the native source bridge or claiming new images.

Material comparison uses the same f75 camera and lighting plan. Surface-owner
isolation for #459 is a separate read-only diagnostic; it cannot establish a
geometry repair. Any later bounded road/terrain correction needs its own
source-relative delta, rollback and native proof. Owner audit remains
`PENDING_FINAL_M3`; performance remains `DEFERRED_AFTER_M3` and
`performance_pass: false`.

### Verified granular source and current integration

Source `27f24ead669807eaf6e4f9e6f317d4506962da2a` passed
[protected CI 38096073155](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096073155)
and [Material Forge source run 38096069404](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096069404).
The two actual Godot exports contain byte-identical graphs and all five maps.
All three original ZIPs were independently downloaded and matched their GitHub
sizes and SHA-256 digests:

| Original artifact | Bytes | SHA-256 |
|---|---:|---|
| [Receipt 11685194177](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096069404/artifacts/11685194177) | 4,026 | `52d41bc79541145359afd86eab1d388207e714ed3a1f63eaf2c066764cb690e9` |
| [Run-a 11685209399](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096069404/artifacts/11685209399) | 30,137,392 | `fd3414f7929553acc0848b9aea4de3b08b58b8c763b7f1c1ce75fa6223d26758` |
| [Run-b 11684894933](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096069404/artifacts/11684894933) | 30,137,389 | `d7da540d47bbc8967824a1f30b9ea8df1a17f7fc7d92fcc1dbba6856377f58c8` |

The unchanged read-only replay checker also passes against both retained
bundles. Its offline input mirror reproduces the host's raw CRLF catalog and
upstreams; executable Python bytes and every original export/receipt remain
unchanged. The resulting native-source pins are:

- producer/run: `27f24ead669807eaf6e4f9e6f317d4506962da2a` / `38096069404-1`;
- original `source-proof.json`: `0dc2d0f09cd968cf60a7cb711516d056e77c737eba63115f2e0c47fada870b3f`;
- current source fingerprint: `5c692af95b9e5366094b34f49d61a0f2b0e1bd71d9da855cafb9667aefefb7f5`;
- graph: `9c0a41f6e2ae5733469cb0cf87df25cb2460c9aadcf3f3c948f030661b1ba562`.

Actual BaseColor coarse variance falls from d91's 25.77% to 2.09%; resolved
grain RMS rises from 0.01592 to 0.02512. Mean roughness is 0.93296. Direct map
review finds distinct, irregular aggregate and quieter broad colour. Normal
XY RMS rises from 0.03019 to 0.08217, so sunlit grain response and temporal
stability still need the real Unreal camera review. CPU previews and simple
map downsampling are diagnostic only, not native UE pixels.

The intermediate [native run 38096069322](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38096069322)
passed the unchanged native baseline but correctly stopped the old retained
source bridge with `ValueError: Graph surface field changed`. It did not save
the new material consumer or render new road frames. The next integration pins
the verified new producer instead of relaxing that gate.

The edge integration at `95e7fc22cb24bc1495179fdce1ffa45965f8110e` passed
[protected CI and the actual Unreal build/Automation](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38098305035).
Its native baseline, transient asphalt canary, saved/fresh consumer and all
68 ordered GPU frames passed in
[run 38098301959](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38098301959).
The source-derived material coordinate is confined to authenticated outer
shoulder tops. Its explicit delta is one appended material UV channel plus
material assignments. Positions, topology, normals and the complete original
UV prefix remain unchanged. The actual native one-to-zero UV preflight, the new
source-distance witnesses, full UV hash and fresh reload all passed.

Original [artifact 11686303649](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38098301959/artifacts/11686303649)
was independently downloaded and verified: 395,390,861 bytes, SHA-256
`ac1d6fa2dca93502bbedef28d2b1a7a3632736c1049ec371851b74d6c8370da4`.
All 68 final PNG hashes match the host receipt, seven retained source receipts
match their recorded hashes, and the camera plan is byte-identical to f75.
The GPU Editor's actual observed exit is zero. Initial direct review finds
clearer fine aggregate and much quieter broad colour; distant transverse
repetition remains visible in 0071 and Nudo-0. The original dark contact line,
hairpin profile and faceted terrain remain unresolved.

The overall native workflow is **failed** because its subsequent contact-only
diagnostic stopped before launching an Editor: Windows converted the unpinned
`Get-YacsUnrealHostState.ps1` line endings, violating the raw committed-byte
check. No twelve-frame contact diagnostic or retained pavement producer copy
was created. The scoped follow-up pins that helper to LF; a real Git checkout
fixture reproduces the original single-file mismatch and checks all fifty
source/helper files after the fix. The raw-byte gate remains unchanged. This
separate failure does not invalidate the already retained 68 material frames,
and those frames do not establish a contact repair or owner visual acceptance.

The owner additionally requested sparse, individually authored crack motifs,
subtle edge erosion and white edge lines matching the supplied reference.
These are subsequent local appearance layers: stable source-owned placement,
visible clean intervals, bounded material footprints and no repeated regular
stamp. The reference supports narrow continuous off-white edge markings.
Their source/render/placement proof is still pending. RVT remains an option
for a justified shoulder/terrain material transition, not a substitute for
resolving #459 contact geometry.

### Latest native result and next integrated candidate

Revision `9519e0c5f9a523c02ddea4c1c8875c41784c4f98` passed
[protected CI 38099857098](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38099857098).
Its [native run 38099853386](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38099853386)
again passed baseline, canary, saved/fresh material consumer and all 68 GPU
frames. The original ZIP, [artifact 11687752206](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38099853386/artifacts/11687752206),
contains 395,317,768 bytes and independently matches SHA-256
`74b0db419ad1a87de8c31241b27b14d5b5bacc9b0fecf8874335a336b20ad437`.
All 68 final PNG hashes and sizes match both native and host receipts. The
actual GPU exit is zero; the camera plan remains byte-identical to f75
(`3fac9564e4c96c0eee237c2103cc4833af93b8bc493b4334e0b88e1e70d37559`).
The detailed appearance review above concerns the inspected 95e7 images;
hash verification alone is not a new visual review of all 9519 images.

The subsequent contact diagnostic did launch an owned Editor, then failed
before any capture: `LandscapeComponent` does not expose
`component_size_quads` to this Python build. Its real process exit was zero,
but the native receipt is **FAILED**, so the overall workflow correctly failed.
The read-only support query had already matched all 5,232 interior top
triangles with zero coordinate delta. No contact PNG or repair PASS exists.
The next candidate uses the existing public `SystemLibrary.GetComponentBounds`
pattern, independently checks its footprint against the actual section bases
and unchanged 0.5 m grid, and requires a fresh installed-header receipt.
An initialization failure now reports its original native error before trying
to open an absent survey, and cannot claim successful restoration.

The same artifact retains the actual unchanged pavement and Nudo producers.
Their 3,393/6,580 bytes match the source pins. Independent review of the
pavement producer confirms ordered top triples `(0,1,2)` / `(1,3,2)`, with
top and bottom faces interleaved. The new explicit source resolver accounts
for every complete slab before addressing a paint triangle; it never executes
the archived generator. Native placement must still verify the actual
triangle IDs, vertices, positions and split corner normals.

The integrated candidate adds 10 cm continuous off-white edge paint, set
12 cm inside each source edge and raised only 1 mm for rendering. It produces
370 separate overlays for 185 pavement owners, with no collision, shadow,
navigation or physics authority. The paint reuses the existing asphalt maps;
its two material packages and every overlay buffer must survive save and a
separate fresh process. The full original road/support buffers and existing
shoulder material UV contract remain protected. A review caught and removed
an incorrect assumption that the source triangle cross product always points
up; source winding and actual corner normals are retained unchanged.

After the unchanged 68 Lit frames, eight separately receipted controls reuse
0071 forward 2 and 0082 forward 2: current Lit, BaseColor, WorldNormal and a
transient uniform Lit material. They retain three priming images per condition,
actual camera/view/material observations, texture readiness, installed API
source hashes and restoration, under the same 180/1080 second deadlines.
The host pins the eight-condition plan before opening the Editor. These
controls diagnose the remaining bands; no buffer-name getter, visual PASS or
saved diagnostic material is claimed.

After a complete, restored twelve-frame 0112 contact diagnostic, a separate
six-frame `hairpin0081` target uses the existing 0081 forward 8 and reverse 4
poses. Its local Landscape footprint comes from the exact retained 1,749-byte
`ma2141-cut-patch.json`, and the complete native support is read in bounded
chunks. The baseline/support-hidden/local-Landscape-hidden comparison changes
visibility only. The 68-frame material plan and original twelve-frame target
remain unchanged. All new paint/control/contact native results are **pending**.

The [source run 38099853373](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38099853373)
passed the existing two asphalt exports, then stopped the crack addition on
the raw-byte gate: Windows converted `render_material_forge.gd` to CRLF.
There were no actual crack exports. The next candidate explicitly pins that
unchanged exporter to LF. A real Git Windows-style checkout regression checks
both the repaired checkout and rejection of altered physical bytes; it does
not relax source authentication.

### Authored local crack source contract

The source addition defines eight distinct authored crack motifs in
`worldgen/materials/material_forge/road_crack_decals.json`, with 1.2–1.8 m
footprints and 2048-square exports. Each motif uses an individual arrangement
of interrupted paths, unequal branches and small aggregate chips. Millimetre
wall variation preserves those authored shapes. The recipe rejects an outline
reused through translation, scale, rotation, reflection or a changed seed.
These are sparse local masks with a 60 mm empty border and CLAMP addressing,
not another tiled asphalt layer. Height remains authoring-only.

`material_forge_road_decals.py` authors six-node Material Maker graphs and
validates the unchanged five-map exporter. It leaves native process evidence
to `run_road_decals_source_proof.py`: the host authenticates the existing
producer archives, executable bytes, primed source and original PBR node;
observes sixteen owned Godot exits; retains both complete runs and compares
all graph/map bytes. Exporter/shader errors also fail when the process returns
zero. The existing source workflow runs this bounded addition only for an
explicit `[road-cracks-source]` commit, under the same serialized host lock.

Revision `07ebafad08bce8bc227089901cb46785079fefda` passed
[protected CI 38102426201](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102426201)
and [source run 38102423216](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102423216).
The source host observed all sixteen distinct Godot processes exit zero within
their deadlines. Eight motifs each have two complete, byte-identical exports:
80 maps including the native Height EXRs. Independent read-only replay checked
every map, graph, recorded process/log, native validation and original receipt.
The source receipt is 28,571 bytes, SHA-256
`bdfb2b889a8c8ed48960518909f497d822b5c34e7d4631a890368de984310afb`.
Both run manifests have SHA-256
`4918510f4dfd656440baee73862ebb4c951a36b11ab1f446ad8953b4e8eebca6`.

| Original crack source artifact | Bytes | SHA-256 |
|---|---:|---|
| [Receipt 11688367643](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102423216/artifacts/11688367643) | 4,670 | `b92d65de3bdbcc49ec896deaff645bf034777f612883b5f53c4ed759831c3679` |
| [Run-a 11688242761](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102423216/artifacts/11688242761) | 1,945,168 | `9451c0d31a244d94529ad608218d62915641be05a1504dcdfd547a4b7632abb6` |
| [Run-b 11688412564](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102423216/artifacts/11688412564) | 1,945,169 | `faef253ee887909bdee6376547ea41f0b3164582052ba2f0dadc7d2e1ab17dff` |

The raw-byte source gate remains unchanged. The offline replay uses an explicit
mirror of the host's two CRLF JSON inputs, checked against their original pins;
all four executable source files and all exports/receipts remain unmodified.
These results establish source export determinism. Local receiver ownership,
stable placement, native saved/fresh proof and image review are still required
before admitting any UE crack layer.
No road, shoulder, Landscape, physics or Unreal asset is changed by this
source-only addition. Owner audit and performance remain pending as above.

The same revision's [native run 38102423208](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38102423208)
failed during its 257-test preflight, before opening Unreal. One saved-package
fixture exposed Windows' case-folded `Path` ordering versus the portable
case-sensitive receipt order. The repair sorts explicit relative POSIX names
and exercises real `PureWindowsPath` comparison semantics in the same physical
file audit. It does not change package identities or relax the inventory gate.
Artifact retention now names the run-owned checkout directly: an early failure
before `GITHUB_ENV` initialization must not expand an empty variable to `/**`.
The failed run uploaded no artifact and produced no paint/control/contact PNG.
The targeted local repair tests pass (57 tests, eight PowerShell-only checks
skipped on Linux); a new exact-head Windows/native run remains required.

The repair revision `2d8d1bf3c627ecc7ab7a058dea3975edc8140a37` then stopped in
[protected CI 38103410287](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38103410287).
Its Python 3.14 lane rejects mixing POSIX and Windows path flavours inside the
new regression fixture, whereas local Python 3.12 had coerced the root. The
fixture now explicitly converts its root to the same Windows flavour while
retaining native Windows comparisons and real-file auditing. Production sorting
and all inventory checks stay intact. Native execution was skipped at the
protected-CI prerequisite; no additional UE result is claimed.

## Whole-network revision following owner feedback

The owner requested gravel beside the entire existing road network, a drier
and more varied asphalt made in Material Forge, and one complete #364 delivery.
The hairpin concern means realistic crossfall/banking and longitudinal profile,
not new guardrails. Diagnose that geometry separately against its source;
the material proof retains its unchanged-geometry contract.

Source candidate `c773f871aa9b8fc269888f12f8714d584de4dd66` introduces
`aged_mountain_asphalt/dry_varied`: the existing 4 m / 2048 px / five-map
contract, roughness target 0.90–0.99, normal strength 0.24 and irregular
variation at several scales. Historical asphalt recipes retain their shader.
The 74 local source tests passed, and
[protected CI 38087793104](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38087793104)
passed. This does not establish source-render or visual acceptance.

The first actual
[source run 38087789852](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38087789852)
failed `DetailMasks` horizontal wrap QA after rendering run-a. No run-b or
two-render PASS exists for this candidate. Original logs are retained in
[artifact 11683365198](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38087789852/artifacts/11683365198),
484 bytes, SHA-256
`5e956c3020ddf553278d4c07f1c7f3a38d2d69c8177c20adb4a896bb9afbfe4b`.
The actual first bundle is
[artifact 11682871037](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38087789852/artifacts/11682871037),
20,532,779 bytes, SHA-256
`3a15ded3458b5978ce7a36b0b1bee76d0dca4e602325df3915af65b77ac7a4a4`.
Both archives were downloaded and their bytes independently verified. The
intermediate native run stopped at the source bridge: the previous base bundle
does not contain `dry_varied`. It did not reach new material authoring.

The isolated fix at `b385c6cf601764ab91220caa24d8a2d1d2d033e8` changes only
the dry recipe's periodic lattice addressing: canonical tile coordinates and
explicit neighbouring-index wrap replace floating modulo there. Seed,
frequencies, contrast, material response, historical recipes and wrap
thresholds remain unchanged. All 76 source tests pass locally, including
regression rejection of both measured failed seam axes.

[Source proof 38089061451](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089061451)
then passed two actual renders, both with exit 0 and identical graph/all five
map bytes. The original `source-proof.json` is 15,357 bytes, SHA-256
`6a073cf0223b47ac0734017a9e6691b749c871275ad2279a1b8f0aaec9439236`.
Its retained producer fingerprint is
`0968cc9e3a4c882faada014bb498a844fe09414d6960e209f7ffc02922fbce99`;
the graph is
`25257e365ec99155d6e2e5a89ec527d153a7156427ad67777444f90b1b5561cd`.
The source bridge used for the first full-network native run selected exactly
this producer/run and receipt.

All three original archives were independently downloaded and byte-verified:

| Source artifact | ZIP bytes | SHA-256 |
|---|---:|---|
| [Receipt/logs 11683416306](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089061451/artifacts/11683416306) | 3,989 | `0d7761bcda19b8598ca841e48627d027edd3c4561da275c6cf5430e1863a919b` |
| [Run-a 11682901906](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089061451/artifacts/11682901906) | 20,532,813 | `ebbf30a7dec71b92ff177d8072f150dc2d8a5918bc8ded2ea11e18cc92ae2ef0` |
| [Run-b 11683666047](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089061451/artifacts/11683666047) | 20,532,813 | `e4d0b31460afb3b21e0f3e13312cde73247d843b89f260b90b4a3c79298b4ce8` |

Independent pixel remeasurement confirms `DetailMasks` wrap X/Y fell from
0.063345/0.072007 to 0.012891/0.012899 under the unchanged QA rule. Both
axes are now close to their adjacent interior pixel steps. Mean roughness is
0.936347; the minimum 0.898039 is the 8-bit quantization of the 0.90 lower
bound. Large-scale colour variation remains a visual candidate for Unreal
review. The numerical diagnosis does not establish the GPU compiler's actual
lowering of the prior floating modulo expression.

The strict retained replay checker also passed locally using explicit,
hash-verified Windows CRLF catalog input bytes. Git's current JSON checkout
policy makes the catalog and upstream file CRLF on the host and LF locally;
those two conversions exactly reproduce the retained producer fingerprint.
No source, receipt or map bytes were rewritten to obtain this verification.
Windows source tests completed 76 tests with two unavailable-platform skips.

The full-network consumer under integration source-authenticates all 186
support owners before assignment, assigns only the two outer top strips on
185 material targets, and preserves the existing Nudo parapet and all original
wall materials. A narrow, read-only native inspector reads complete road and
support position/index, rendered corner-normal/UV and MaterialID buffers.
Its versioned `blake3-256-le-i32-f64-corners-v1` fields are new evidence;
historical SHA-256 mesh fields are not relabelled. It uses the existing Core,
GeometryCore, GeometryFramework and Json dependencies, with no geometry
authoring API. API review used Epic's UE 5.8 documentation for
[FBlake3](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Core/FBlake3),
[FBlake3Hash](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Core/FBlake3Hash)
and [FDynamicMeshAttributeSet](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/GeometryCore/FDynamicMeshAttributeSet).
The initial build in CI 38089067078 was cancelled after a concurrent branch
update; its failed aggregate gate is not build or Automation acceptance.
The subsequent [CI 38089333376](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089333376)
at `52d7a6fd3ea8d354a4e69522e470c1fcd62ef1d3` actually compiled the unchanged
native inspector and completed **28/28 Automation tests**, with editor exit 0.
Its compile/proof fingerprints are respectively
`18040d5e7a7e1fc3a6bc74f78dd8f025459237aa40e0fdd97c0f6b2050b962f5`
and `417c89dbcb6fe8306717adfc2e6f5a9f090634fee555505730ed7408c9bb827d`.
[CI 38089666262](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089666262)
at the full-network revision `4234f41908072d59645c0055dad83aa960973e8f`
passed by authenticating and reusing those equivalent native fingerprints;
it did not perform another build or Automation execution.

The first full-network [native run 38089663072](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089663072)
successfully staged and read the frozen scene, then failed before material
authoring because the PowerShell canary still pinned the previous base recipe.
Its Python preflight had already authenticated the correct dry two-render
source. Original [artifact 11683487567](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38089663072/artifacts/11683487567)
is 110,553 bytes, SHA-256
`37c9dc27610c08feb7bc4115bf8870a17ac1a674f70c72c1ff997a70eec62c9d`,
independently downloaded and verified. No full-network save or GPU capture
occurred. The follow-up aligns both host source pins with the authenticated
dry bridge and corrects the native result gate to the producer's
`dry_asphalt_response_verified` field. Regression checks for both boundaries
now run before staging a native session. All 27 focused boundary/import tests
and the documentation/architecture guards passed locally. Source/map identity
checks and all admission limits remain enforced.

The representative camera plan selects 68 existing, authenticated survey poses:
both directions in all 24 occupied 250 m road cells, the original four
comparisons, Nudo, the accepted hairpin and elevation extremes. It represents
28 of 185 road windows; it does not assert exhaustive road-pixel visibility or
owner acceptance. At `9242964495670e354836b9e65e47d2155c30d98a`,
[protected CI 38090399959](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38090399959)
passed with the authenticated equivalent native build/Automation proof. The
[native run 38090395135](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38090395135)
passed the baseline, reversible dry-asphalt canary, complete network save and
separate fresh-process reopening. The actual selection is **67,760 outer-top
triangles across 185 material targets**, with all 186 support owners checked;
all road/support geometry and rendered corner normal/UV buffers were preserved.
Prepare and reload processes exited 0. The saved manifest is 1,909,237 bytes,
SHA-256 `e7c764ddc7c6876dbf64cd6213dd61e9f5ed225c74b86df180f8603030f269f6`;
the freshly reopened map is
`4ea74f77112c1323203569b5ee10c34a15c6f7db006ea33f01f3e77bf90c60e5`.

The GPU stage **failed**, retaining 23 of 68 final poses in its receipt. The
24th final PNG (`window-0081-reverse-00008`) was eventually written, but its
trace-to-save interval was 98.964 seconds, beyond the 90-second per-shot
watchdog. All previous 95 prime/final trace-to-save intervals were at most
0.513 seconds. The log does not identify what blocked the engine during that
interval; no GPU, shader or disk cause is inferred from the missing entries.
The disk contains 24 final plus 72 priming PNGs; the completed receipt prefix
contains 23 final plus 69 linked priming PNGs, with correct hashes and poses.
Full texture readiness and source/material/geometry conservation checks passed,
and GPU editor PID 10860 exited 0. Neither its clean exit nor the late PNG
changes the failed 68-pose result into a PASS.

The original [artifact 11683194509](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38090395135/artifacts/11683194509)
was downloaded and independently verified: 144,105,118 bytes, SHA-256
`4e9e7f2559f54fb150d2e22ecbc51711827793f5d0a1d3526117181a5fcbfdac`.
Technical inspection of actual lit, shadowed and hairpin images also rejected
the dry recipe's appearance: large smoky/marbled albedo fields dominate the
aggregate, with smooth U/S-shaped cracks. The revised Material Forge recipe
therefore needs a new real two-render source proof and new native images.
Numerical source QA was not visual acceptance. Owner visual status stays
`PENDING_FINAL_M3`; performance stays `DEFERRED_AFTER_M3`,
`performance_pass: false`.

The next source revision `d91b4d09e3f7fcd8720f4157c495bc34060d6319`
reduces the large wear field's weight from 0.58 to 0.18, increases the existing
aggregate/micro weights, attenuates the shared crack field to 0.20 and reduces
repair-mask albedo contrast from 0.050 to 0.020. Its dry periodic helper,
frequencies, source seed, scale, UE response and all source QA limits remain
unchanged. Historical material variants are preserved. All 78 source tests
passed locally; the real host ran 78 with two unavailable-platform skips.

[Source run 38092391221](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092391221)
passed two actual renders with identical graph and all five maps. Original
receipt: 15,351 bytes, SHA-256
`43715d7dda0b188a90f90cfd1bec609cd22e280898d0a6869c5cb6be73b9b167`.
Producer fingerprint:
`9c939121d126a7920624acdf33694479627fe828c17b6cbb2320c050bd0a4d1f`;
graph SHA-256:
`e6693675d01617023bdce014254a2074ea6ca571e21f2232a8dccc2ae78bb4cc`.
The Python bridge and PowerShell canary now select this exact new source.

| New source artifact | ZIP bytes | SHA-256 |
|---|---:|---|
| [Receipt/logs 11684168342](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092391221/artifacts/11684168342) | 3,973 | `051f1f743d35b3dc1b590d1c1627c9bfa3634f17dee2936190b8b883ab88b61a` |
| [Run-a 11684522800](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092391221/artifacts/11684522800) | 22,543,229 | `d88a0b89450bc997c9f8406e5a00040d8d0f3d90882529e88995075b9abd411a` |
| [Run-b 11684298065](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38092391221/artifacts/11684298065) | 22,543,229 | `61f14589bef2514589804699da428c17171efaaf283b2f9ec706294d850bdb41` |

All three original ZIPs were downloaded and byte-verified. The actual 25 cm
block luma standard deviation fell from 0.042601 to 0.013930, while total luma
standard deviation is 0.027441 and mean roughness is 0.936163. Source-map
inspection finds the large variations and crack motifs less dominant. This
qualifies a new native visual candidate, not finished UE appearance.

For the next capture only, the per-shot watchdog is explicitly 180 seconds,
within the unchanged 1080-second total and 1200-second host limits. Both
deadline checks still precede completion polling; a late existing PNG cannot
bypass them. Every prime/final records monotonic submission-to-observed-
completion latency, with the configured watchdog and maximum in the receipt.
These are capture diagnostics, not GPU-only timings or performance admission.
All 48 focused source-bridge/canary/GPU tests pass locally with three PowerShell
skips. The old 9242 timeout remains failed; new full-network native proof is
pending on the newly pinned material.

The integrated local contract suite completed **237 tests, with six skipped
because PowerShell is unavailable locally**. Documentation/architecture and
diff checks passed. Independent reviews caught and corrected the importer
receipt key mismatch and a missing camera-direction readback. Each final and
priming capture now observes the camera after loading; the host independently
compares its location, FOV and forward vector against the pinned survey pose.
These local results do not replace the new full-network native proof. At the
owner's request, UE Remote review follows completion of the corrected material
scene and must show that verified version.

The integrated source-only profile diagnostic records all 17,125 frozen
pavement cross sections across the 185 road windows. It retains the original
edge/centre XYZ, signed crossfall, each track's longitudinal grade and local
curvature in a separate bounded 8 MiB compact file, linked by SHA-256 from
the material manifest and rehashed during fresh reload and GPU review.
Its status explicitly keeps `real_road_match_validated=false`; it neither
authors geometry nor turns DTM inference into measured road banking.
The sidecar retained in native run 38090395135 is 5,684,256 bytes, SHA-256
`b2f5f3306157ba4431371d9d7e1bf0241e19874fea4f9a3009899b614b52821d`.
Its actual full accepted-hairpin source has signed edge0-to-edge24 crossfall
from -7.43% to +13.72%, across 2,401 sections and 306.46 m of local XY station.
The source centre's longitudinal grade ranges from -15.29% to -2.71%.
The provisional 2% inward design belongs only to a limited central region;
it does not describe the whole saved hairpin. Nudo's main `nudo-1` window is
transversely level in 201 of 202 sections within a 1e-9 slope tolerance.
These are measurements of the frozen visual/design source, not surveyed road
banking, a native geometry repair or authoritative cycling physics. Establishing
faithful real-road profiles remains the separate measurement and geometry
workstream requested by the owner.

## Current proof boundary

The verified asphalt baseline is exact commit
`396861de0884135d18006e6d3f133edebef639aa`. Its protected
[CI 38078462035](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38078462035)
and [native/GPU run 38078459124](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38078459124)
both passed. CI reused existing equivalent build/Automation evidence; it did
not perform a new Unreal build or Automation run. Original native receipts and
images are retained in
[artifact 11679925399](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38078459124/artifacts/11679925399).

The completed bounded shoulder proof is exact commit
`1ef46dacedba5ed1fc909422529be41808d3dbe4`:
[CI 38084736631](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38084736631)
and [native/GPU 38084733503](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38084733503)
both PASS. CI reused equivalent Unreal build/Automation evidence; the new
native run performed the material assignment, rollback, save, separate fresh
reload and GPU capture. All three owned editor processes exited 0.
[Four same-camera before/after pairs and selected original receipts](../experiments/sa-calobra-road-shoulder-window0112-20261010/README.md)
are retained in the repository. This completes the single-support canary,
not whole-area #364 delivery or M3 owner acceptance.

GPU PASS covers capture, texture readiness, conservation checks and observed
process exit 0. The separate `gpu_shader_compilation_admitted=false` and
`road_pixel_visibility_admitted=false` admission flags remain unchanged.

| Check | Actual status |
|---|---|
| Asphalt source replay | Two independent 2048 × 2048 renders of the same base recipe PASS; graph and all five map bytes match |
| Protected CI at `396861de` | PASS, including the aggregate gate; existing equivalent Unreal build/Automation proof reused |
| Native asphalt baseline at `396861de` | PASS: read-only scene inventory, reversible road canary, saved derived consumer and fresh reopening |
| Native GPU review at `396861de` | PASS: four final same-camera frames, forward/reverse in window 0112; each readiness receipt records full 12/12 resident mips for all four asphalt textures before capture |
| Full geometry and rendered normal/UV conservation | Baseline counts and saved-file checks do not prove every mesh buffer; the current shoulder candidate adds exact checks on its sole changed support |
| Current shoulder candidate: local checks | Integrated 63-test suite completed successfully with 2 platform-dependent skips; `py_compile` PASS |
| Shoulder material at `1ef46da`: save and fresh reload | PASS: exact 436-ID selection, rollback, material/source checks, saved derivative and separate fresh process; independent manifest and inventory review PASS |
| Shoulder GPU at `1ef46da` | PASS: four final frames, twelve priming frames, all readiness/conservation checks and observed process exit 0; four-pair technical image review completed |
| Whole-area visual acceptance | Unaccepted; four bounded road frames do not establish whole-area acceptance |
| Owner visual status | `PENDING_FINAL_M3` |
| Performance | `DEFERRED_AFTER_M3`, `performance_pass: false` |

### Completed window 0112 shoulder canary

The bounded #364 change targets exactly **436 source-owned outer top
triangle IDs on the sole window 0112 support**. Only those material IDs may
change from slot 0 to slot 1. Interior tops and walls retain slot 0 and its
literal original material instance. The added slot uses the existing staged
`FillGravel` maps from Poly Haven `rock_ground`, CC0, with a **150 cm** world
projection matching the provider's 1.5 m source scale; it imports or edits no
source texture. See the pinned source and use limits in the
[asset plan](../ASSET_PLAN.md#sa-calobra-road-material-preparation--2026-10-10).

At `1ef46dacedba5ed1fc909422529be41808d3dbe4`, native before/after and
fresh-load checks passed for the target mesh's positions, triangle indices and
every rendered corner normal. The support has no UV sets; no UV data was
invented. Its exact 436-ID assignment delta is separate from those immutable
geometry/attribute checks. The downloadable manifest retains all 436 IDs,
hashes and native API declarations, pinned across fresh reload and final
in-editor GPU checks. After the lifecycle correction, the integrated local
63-test suite completed with two PowerShell/Windows skips, and `py_compile`
passed. Independent review confirmed the complete native/save/reload/GPU
chain, including process exit 0, and technical image review confirmed the
visible aggregate shoulders. Full buffer proof remains limited to support
112; other supports retain inventory checks.

This remains material-only #364 work: no geometry, Base_DTM, road physics,
displacement or weather change. The unresolved inner seam belongs to #459 and
is outside this patch; material work must not conceal it. The owner audits the
complete assembled M3 world at the end, before FPS measurement. Intermediate
technical proof and retained review images continue without changing
`PENDING_FINAL_M3` or the deferred performance status.

### Final native proof and retained comparison

The successful run's full
[artifact 11682625600](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38084733503/artifacts/11682625600)
is 23,062,207 bytes, SHA-256
`e18e3780255794b18b150e498b80a7aa69e608d110ff8ead16d765f0bd7673b5`.
Independent audit verified every extracted file against that ZIP, 63
references to 55 distinct files, all 16 original 1280 x 720 PNGs and the
readiness receipts. Every pose has four asphalt textures at 12/12 mips and
three gravel textures at 11/11 mips. Camera positions, targets, station,
direction and FOV match the pinned CSV and the asphalt baseline exactly.

Prepare PID 27604 and fresh-reload PID 5056 exited 0. GPU PID 14720 exited 0
after 79.7248 seconds; the host observed that exit, verified four final frames
and recorded no errors. The complete saved manifest is 22,701 bytes, SHA-256
`ccd13145400c756e5d27efd332f84fe87001a8e1e4fe00e08df00997310e5cbd`.
The unchanged support position/index and corner-normal hashes remain those
listed in the earlier native result below; its entire `shoulder_window`
proof is identical. The expected normalized inventory remains
`3c9098b4ce21292165b35201b140b4e01dbc60b363489c27c652513a4ce0f49d`.
The original nine native material/map packages remain in the host's retained
output, with their native hash checks and identities in the manifest.

The selected repository copy includes eight final before/after PNGs and the
native material, save, reload, GPU and readiness receipts, all byte-for-byte
copies with a [retained-file index](../experiments/sa-calobra-road-shoulder-window0112-20261010/retained-files.json).
Full engine logs and priming images remain in the linked complete artifacts.
Technical review confirms aggregate on the foreground strips and no visible
wall repaint. Sharp boundaries, rhythmic light/dark patches at middle distance,
the lower road's unchanged beige shoulders and #459's dark seam remain visible.
The lifecycle-only correction introduces no meaningful visual change against
the earlier captured shoulder frames. This successful run does not establish
the earlier access violation's engine-level cause; the native log still
contains the engine's normal `QUIT_EDITOR` shutdown command.

### Next bounded #364 scope

Continue with source mapping and coverage of the remaining ordinary shoulder
tops using the same proven 150 cm material. The baseline has 186 supports;
183 have counts consistent with the regular 27-column producer, but counts
and material names alone cannot establish ownership. First map source windows
to candidates `000`-`180`; keep `181`-`185` explicit for separate qualification.
The latter set includes a parapet, irregular Nudo construction, two windows
whose source flags need checking and the large accepted hairpin. Do not copy
the 0112 constants: only support 112 has 110 sections and 436 selected IDs.
Every newly changed support requires source-authenticated selection and full
before/after/fresh-load buffer checks. Preserve #459 and the final M3 owner
audit; complete-area coverage and technical review are still required.

### Shoulder recipe checkout correction

Candidate `926ed9c592d12142d082195a1c5b93ebfe8aebcc` passed
[protected CI 38082004301](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38082004301).
The Unreal gate explicitly reused verified equivalent build/Automation evidence.
[Native run 38081999577](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38081999577)
passed the fresh baseline and reversible asphalt canary, then stopped before
launching the saved-material editor: the newly read frozen road recipe lacked
an explicit LF checkout rule and failed the raw Git-byte guard on Windows.
The failed run did not apply shoulder materials, save the candidate or render it.

The correction pins LF only for that existing recipe in `.gitattributes`; the
recipe blob and the raw-byte guard are unchanged. A real temporary Git checkout
with `core.autocrlf=true` proves the recipe remains byte-identical to its index
while an unmatched JSON control becomes CRLF. The six-test saved-host suite
passed with one unavailable-PowerShell parser skip. A fresh native run remains
required. The original failure artifact is `11680528146`, SHA-256
`e95eec21856185fd5bd135f3fb770c2de478eeccdb10abe2da3081db22227ba5`.

### Shoulder source dependency handoff correction

At `1e5d8b1579c56d364102e0ce1d4ea811d246aa47`,
[CI 38082699835](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38082699835)
passed, including 27/27 fresh Unreal Automation tests without recompilation.
[Native 38082696315](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38082696315)
passed the corrected checkout, native source-owned support selection and API
checks, but stopped before gravel creation: the caller passed the combined
scene/source rows into the unique-dependency validator. The authentic staging
receipt contains 14 consumer rows and 236 unique source dependencies, with ten
valid paths shared across those distinct roles.

Prepare, fresh reload and both GPU checks now receive the authenticated
`source_dependencies` list explicitly. The combined inventory still guards
every original package; the material validator still rejects duplicate source
dependencies. A dispatcher regression covers both editor actions with shared
scene/source paths. The integrated local suite is now 61 tests, with two
unavailable-PowerShell skips. Fresh native material/save/render proof remains
required. Failure artifact `11681067447` has SHA-256
`ed5c595849c70de65f6d5c98eab19a79e60c0a0c1e9980bac4debf16e21e0b16`.

### Shoulder native material result and GPU exit correction

Commit `8faed55c067d42856c2d6a8eca8b5a15f237a5d8` passed
[CI 38083586294](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38083586294),
using verified equivalent Unreal build/Automation evidence without a new
compile or Automation run. In
[native 38083583775](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38083583775),
the accepted baseline, reversible asphalt canary, saved shoulder consumer and
fresh reload passed. Prepare PID 31380 and separate reload PID 8660 both
exited 0. Independent review verified all nine saved-host file references and
reconstructed the expected road/support/Landscape inventory from baseline.

The unique owner is `YACS_PERSIST_SUPPORT_112`: 4,050 vertices, 6,208 triangles,
zero UV sets and a 0 cm maximum difference against all 5,232 source interior
triangles. Exactly 436 outer top MaterialIDs change to 1; the remaining 5,772
stay 0. Slot 0 interior tops and walls keep the original material. The target
position/index hash is
`aac7a97734192b30994916f2a521e14c1be0194741ec4111184a759e854e037f`
and its corner-normal/UV hash is
`c4e55257197cc083ac1a75d495b93e86afd0ecb85acca4e5fbb526203228fdb1`,
unchanged before/after assignment and verified after fresh load. Full buffer
proof applies to this support; the other 185 supports and 1,024 Landscape
components retain their existing full inventory checks. The manifest is
22,701 bytes, SHA-256
`ff3c13e5a748edd9190e3ed0003189f7c390acc745da4edd78a2be035dd3ffea`.

All four final 1280 x 720 images and twelve priming images were retained with
the same cameras. Each final pose records all four asphalt textures at 12/12
mips and all three 1024 px gravel textures at 11/11 mips. Final in-editor
source, package, mesh, material and manifest checks passed. Technical image
review sees grey-brown aggregate replacing the flat beige foreground shoulder
strips, with no visible wall repaint. The lower road's beige shoulders and the
dark inner seam remain visible. Repeated light/dark patches are noticeable at
middle distance in reverse views; material boundaries remain sharp. These
observations do not admit the entire area's appearance or conceal #459 debt.

The GPU host nevertheless returned **-1073741819 / 0xC0000005** after all
frames, `QUIT_EDITOR` and `LogExit: Exiting.`. Its failed status is retained;
successful image generation does not override the required zero exit. The
artifact is
[11680954421](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38083583775/artifacts/11680954421),
23,062,216 bytes, verified SHA-256
`895f0f10ad9835d9d7212fa9581b66f4c9e8b18a5dfe301ea75baecd3a2fa2ee`.

The narrow follow-up removed the explicit `quit_editor()` from the Slate
callback and leaves `set_keep_python_script_alive(False)` as the exit request
for the existing `-ExecutePythonScript` process. This follows the project's
[`stage3g_capture_passo_giau_landscape.py`](../../scripts/ue/stage3g_capture_passo_giau_landscape.py)
lifecycle precedent. No capture settings, cleanup sequence, ten-second wait,
material assignment or exit-code gate changes. The shutdown cause is still a
hypothesis, not an established engine diagnosis. The subsequent exact-SHA
run at `1ef46da` passed with exit 0 and all existing proof checks, as recorded
above.
Two new regressions execute the real stop/receipt path with synthetic native
boundaries. They require cleanup, all existing checks and a written receipt
before lifecycle release; the capture-error case must retain failed status.
The integrated 63-test suite passed with two unavailable-PowerShell skips.

## Historical owner pause and first native attempt — 2026-10-10

The following chronology retains earlier attempts. Its paused, blocked and
pending statements apply to their recorded heads; the current baseline and
candidate status are stated above.

The owner stopped implementation and requested a report plus smaller roadmap
batches. Agent implementation/review work is stopped; no additional native job
is dispatched for this documentation update. The remote implementation head is
`33a35a74f17e56ef073248581e265db9db16cf7c`; #364 remains open and PR #470 Draft.
#364 changes are on that branch, not merged into `main`.
[Normal CI 38046180394](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38046180394)
passed. It does not override the failed stage-specific native attempt.

[Baseline run 38046175645](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38046175645)
passed PowerShell parsing and the Windows reader suite (11 discovered, 10 passed,
one permission-dependent symlink case skipped). It stopped at cache preflight
before staging, copying modules, invoking the cache resolver or starting Unreal.
The original verified cache state, binaries and scene were preserved.

| Fingerprint view | Compile | Proof |
|---|---|---|
| Actual fresh Windows files | `8caee4876a7a00aef42f6fea90f887193c4f38ddb6c69679cc0bec313f31f54f` | `7fdcba7f638c1c2a00edec7a5a14c7c7a81fde186849cad4ee0af435d2be99f8` |
| Retained hosted CI cache state | `e5fc3e8d77e350ba1bb94458bd71fd2fe2e771915f0c9838de7876b7fbbc01de` | `7e6a4073b34d86ae4c11122ecbac3d5b15f2088c774b5265008999e82734236c` |

The canonical native engine/toolchain environment matched the retained state.
Its original compile/proof head is
`40b85b0c07fc9bda28164f052641dd45c775f666`; mutable cache HEAD at observation was
`88f6b95e007b61a122b6515fe29041e5e3a3f220`. Preserve that distinction rather than
claiming a new compilation or Automation run. The failed-attempt artifact is
`11667629439`, ZIP SHA-256
`add0483d15f22018d37d489276bcd71b5035d015f8552ce625916898e7bfcd52`.

A read-only local simulation of native Windows EOL checkout exactly reproduced
the observed Windows fingerprints from 14 existing `.cs`/`.ps1` inputs whose
EOL is unspecified. This supports an EOL diagnosis; it is not actual Windows
per-file qualification, cache admission or a successful scene read. Resolve the
specific identity contract on resumption, retaining byte/source checks and the
existing cache authority.

An authenticated two-run source bridge remains a **checkpoint candidate** in `scripts/assets/road_material_contract.py` and its tests: 45
contract tests passed, but independent review did not finish before the stop.
Its strict raw receipt/current-input comparison remains; Linux and Windows raw
catalog/source fingerprints differ with their EOL bytes. No complete bridge or
native material admission is claimed from the separately downloaded Linux
bundles. A complete mesh/normal/UV hash reader was researched but not implemented.

The owner subsequently authorized publishing all retained work to the existing
Draft PR branch. The bridge and its tests are committed as an incomplete
checkpoint together with this status update; implementation remains paused.
A normal push can trigger automatic CI, but no manual native job is dispatched
by this checkpoint publication. The 45 contract tests were rerun successfully;
independent review and native material validation remain pending.

Resume batches are recorded in the [authoritative roadmap](../ROADMAP.md).

## Verified source run

[Run 38045485913](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045485913)
executed at `6fa54b508019bd4a1b4aa6fad601835295ec664f` on Windows with Python
3.12.10: 37 tests discovered; 35 passed, 2 Windows symlink-permission cases
skipped (`OK (skipped=2)`). Both renders passed. The downloaded result is
`ROAD_ASPHALT_SOURCE_DETERMINISM_PASS`, with raw `source-proof.json` SHA-256
`3626bf85da28d63908feb9d820171dc03d9d6cc444c8f799f7048f7a8052f79c`
and source fingerprint
`b4d93e24d2059c74e0b8d44f23ee10632e63f44c5c932b3ee1b849e0a6868d97`.
Independent read-only checks of both downloaded bundles passed at 400 cm and
23,747,976 input bytes per bundle, with all map and graph hashes below matching.

The first canary is `aged_mountain_asphalt/base`: seed **101**, a **4 m / 400 cm**
tile, brightness **0.30**, `surface_a` **0.62**, `surface_b` **0.22**, roughness
**0.82** and normal strength **0.48**. Normals use DirectX convention. Local
detail channels remain R=cracks, G=patches, B=binder micro-variation; they do not
generate world semantics. Height remains offline evidence, not displacement.
`worn` and `repaired` are not prerequisites of this first base proof.

| Output | Matching SHA-256 from both renders |
|---|---|
| `Material.ptex` graph | `6b381516854c44dc4bdeb69b69fbb2b97ecf22c228db2c09204822d7f0bc0970` |
| BaseColor | `85b378e871d7f0c70f079a153b1d6f64c517926ee7a3fd5c7bffca50766b88e8` |
| Normal_DX | `16425658df44c1ee3cf1003182dce10415a21894afb75c0ac0506a821c7bc77c` |
| ORM | `4c10e1ac79d0dd1abb276870e39b16663581a5ebf87a53043f80450e19713069` |
| Height | `a8ba0d03e3f7fb6b2a0014689e410a92a687083f12e1ab4c16ae07703b740074` |
| DetailMasks | `766b4b41b4b9b77f2e70a4f57be4e67b7a89b7c4c6049f57cd28771950ec832b` |

The producer authenticates the existing pinned tool archives before replay:

| Input | Pin |
|---|---|
| Godot 4.7.2 Windows archive SHA-256 | `731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953` |
| Material Maker 1.7 Windows archive SHA-256 | `deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808` |
| Material Maker source commit | `4d29a815489866aae483281cf44b2cfe48d3cc3e` |
| Godot source commit | `ed1daf0bf001b61586d9930840f2f1394092c079` |

Program and graph inputs remain unchanged. The receipt explicitly retains the
16 Godot-generated UI SVG import-metadata exceptions: only modified files from
the fixed allowlist, literal-only parsing without Godot Object/Resource
constructors, and destinations confined to the imported texture cache. Their
recorded source blobs and SHA-256 values must remain identical across replay.
This does not admit arbitrary tracked source or cache changes.

The rerun split evidence into independently retrievable bundles below the
32 MiB retrieval limit; source inputs stayed unchanged. Retained ZIP identities:

| Artifact | SHA-256 |
|---|---|
| Receipt, `11666752931` | `42eb28349d221e4edcc1164cbd56cd10a91bb05dee71b6f8a2ea5001502edc47` |
| Run A, `11666718117` | `412b2dec7e6936772fdc237bad7698da04b78f7a4f08e316ac48ed3b48682b1e` |
| Run B, `11666792983` | `bae3c93744afbb63595f7fb32455c8d099ba3d584c42191e4dd2cd5f0eca7e08` |

The preceding [run 38045298256](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38045298256)
at `0f1836b00915a193517b7897b019fe8853648dbc` also completed 37 discovered
Windows tests: 35 passed, 2 Windows symlink-permission cases skipped; both
renders passed. Its console pins raw receipt SHA-256
`e4f3443223997e9acbb33822b1810f7f1d2270d905d545b04c7c7a5e35503b96`;
its combined artifact exceeded the retrieval limit. The latest downloaded run
above is the primary source evidence.

## Installed material API evidence

[Declaration run 38044121552](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38044121552)
at `a592f72e5f701e761da6451315fa2ade01c7bb71` read the installed UE 5.8.2
CL 56702186 native `MaterialInstanceTools` source. It established all **17**
declarations without a truncated index; the declaration source SHA-256 is
`abad1c2401323a91e8c760c82184b3918f35581b57e8773493f47f45b1dbc573`.
This was source-only inspection, not runtime schema verification or execution
of those tools. MCP stayed stopped and `material_authoring_admitted` remained
false.

The stock setters do not establish YACS slot ownership, source conservation or
rollback guards. Generic stock material mutation is therefore not admitted.
Reuse the existing fixed [Material Forge importer](../../scripts/ue/import_material_forge_variant.py)
within the scoped policy, initially with `save_assets=False` and 400 cm
world-aligned projection; actual road-specific native proof is still required.

## Validation contract and next gates

1. Authenticate retained graph, map and provenance/validation/render/decode
   receipts with [the source checker](../../scripts/assets/road_material_contract.py).
   Its read-only contract does not independently prove two-run replay or tool
   binaries; [the replay producer](../../scripts/assets/run_road_asphalt_source_proof.py)
   supplies those separate checks. Both retained rerun bundles and the top
   receipt passed these source-stage checks; preserve their pins for handoff.
2. Run [the read-only baseline reader](../../scripts/ue/read_road_material_baseline.py)
   in a fresh isolated native session against the exact staged #363 consumer.
   Verify source/consumer conservation, actual road/support slots and native
   projection functions. Its candidate expects one road, 186 supports and 1024
   Landscape components; these counts are not new executed-baseline proof.
   The reader explicitly leaves full mesh geometry/normal/UV hashing unverified.
3. Establish actual surface ownership and the required geometry/normal/UV
   conservation before bounded base-material assignment. Prove shader,
   400 cm projection, DirectX normal, parameter readback and restoration on the
   actual road/shoulder consumer. Never replace support sides indiscriminately
   or cover unresolved CUT/contact/seam defects.
4. Inspect both travel directions, bends, shoulder/wall separation and the
   Landscape transition. Then retain actual save, fresh reload/render and
   whole-area images for the existing network and approximately 4.07 km²
   working area, with technical review and protected CI. Keep source geometry,
   physics and authority unchanged; future wetness compatibility does not
   implement weather.
5. Retain `PENDING_FINAL_M3` until the owner's final assembled-world audit and
   `performance_pass: false` until the later reference-PC benchmark actually
   passes. Neither source tests nor a protected merge can manufacture those
   admissions.

### Bounded asphalt-only material binding candidate — 2026-10-10

`scripts/ue/road_asphalt_slot_canary.py` adds a small native-session library for
the **asphalt road actor only**. It consumes the independently authenticated
two-run `aged_mountain_asphalt/base` source bridge and reuses
`import_material_forge_variant.import_variant(..., save_assets=False)`
with metric `TileSizeCm = 400` and DirectX normals. The candidate requires
the accepted one-road / 186-support / 1024-Landscape inventory and the pinned
road's 856,250 vertices and 1,711,760 triangles. It does not author road
geometry, Landscape layers, shoulder materials or retaining-wall slots.

A transient test sets **only road material slot zero**, reads back the bound
Material Instance and verifies that the native actor/mesh/collision/Landscape
snapshot differs only in that named road binding. It always attempts to restore
the original material and checks complete pre/post snapshot equality, including
all 186 supports. A failed assignment, changed source or unexpected shared
support binding fails closed. No package or map saving is performed; unsaved
candidate assets are confined to a distinct `/Game/Generated/YACS/RoadAsphaltCanary`
namespace.

This is a **code/test candidate, not completed Unreal validation**. The existing
read-only native baseline must pass independently before the candidate is wired
into a serial isolated Editor proof. Geometry/normal/UV hashes, native shader
compilation, material projection, visual review, saved/reloaded consumer,
roadside shoulder/wall separation and whole-area admission remain pending.
No bypass of the existing active-cache trust gate is authorized.

## Cache provenance gate — 2026-10-10 follow-up

At HEAD `17a1142825fa8794f3ef661731d6df21299accda`, [protected CI run 38055292848](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38055292848)
passed the hosted tests but stopped its normal Unreal lane **before Editor**:
the physically checked-out compile/proof source bytes did not match the hosted
exact-SHA fingerprints. A Git status clean check and C#/PowerShell-only raw
source correction did not cover every fingerprint input. This is a preserved
failure, not a native material PASS.

This revision adds a **read-only full fingerprint-input raw Git comparison**
during cache selection, including native C++/project/plugin/config and explicit
Automation tooling inputs. Source mismatches and unverifiable input inventory
force the already-established fresh isolated checkout fallback while preserving
the old cache pointer, original binaries and original verified state. The
normal CI must then pass real build/Automation before publishing the new
pointer. The separate #364 native reader remains fail-closed and can run only
after successful exact-SHA protected CI. No geometry, Landscape or road physics
authority is changed.

`PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3` /
`performance_pass: false`. No native material import/road authoring claimed
until actual evidence exists.


## Native retry 38056671833 and proof-retention repair candidate — 2026-10-10

[Protected exact-head CI 38056675118](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38056675118)
succeeded at `3262a7529c97e1ed34f1ba5a436c2b84e06db55d`, including Windows Unreal
build/Automation, verified cache publication and the Aggregate gate.
The independently gated [native read 38056671833](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38056671833)
**FAILED before Unreal launch**. Its fixed Windows reader checks completed
(12 tests, one permission-dependent skip), then the runner raised `Get-Item`
at `Invoke-YacsRoadMaterialBaseline.ps1:64`: the active cache no longer held
`Saved/RuntimeProof/CI/Unreal/unreal_ci_summary.json`. The normal CI cleanup
explicitly removes current-run RuntimeProof files after cache publication,
while preserving `Saved/BuildCache/UnrealCi`. A green normal CI is not a
successful native scene read.

This candidate closes that lifecycle mismatch without loosening provenance:
normal CI `Record` retains the **actual** bounded, green exact-HEAD Automation
summary as a content-addressed immutable file under the existing preserved
build-cache namespace and records its SHA-256/byte size in verified state.
Cache selection and static proof reuse reject missing/tampered/incorrect-HEAD
retained summaries; older cache state must run real Automation again, then
record authentic proof before native reuse. The #364 native reader independently
checks the pinned bytes and green original proof head instead of expecting
a transient file deleted by normal cleanup. No synthetic summary, cache pointer
override, foreign worktree, new geometry/material binding, or owner-project
mutation is authorized by this fix.

**Status of this candidate:** source implementation/tests submitted for
protected verification. New exact-SHA normal CI, retained-summary admission,
fresh native reader and subsequent asphalt canary are **NOT YET VERIFIED**.
Owner visual `PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3`,
`performance_pass: false`. PR remains Draft until stage-specific evidence.

## Native stage failure at 5a4a9c1b and bounded checkout-path correction — 2026-10-10

[Exact-head protected CI 38058686733](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058686733)
PASSED: Windows Unreal Automation, authenticated cache proof retention and
Aggregate CI. The separately gated
[native attempt 38058683514](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058683514)
**FAILED during accepted-consumer staging, before launching Unreal**.
[Artifact 11672726865](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38058683514/artifacts/11672726865)
retained complete host receipt, pinned original green Automation summary,
static/none cache resolver and the `accepted-consumer-stage-stderr.log` showing
`_hydrate_dependencies -> _verify_rows: ValueError: accepted asset bytes differ`.
The verified fingerprint/cache/proof gates passed; the staging error does not
authorize altering any source hash or marking the native read as PASS.

A scoped Windows MAX_PATH hypothesis is supported by the exact dependency tree:
five frozen limestone palette `.uasset` paths exceed **260 characters** when
prefixed by the original 99-character isolated Actions checkout root; the
longest reaches **268 characters**. The LFS process returned without a
diagnostic path, so this remains a **hypothesis**, not a proven mismatch
identity. This candidate shortens **only** the separate native Actions
checkout directory to `rm-<run>-<attempt>`, keeping the real workspace,
isolated source/exact SHA, protected cache, Git/LFS checks and accepted
assets unchanged. A hosted contract test covers the exact old-vs-new Windows
path lengths and the wrapper/workflow binding. The common stager now includes
the exact relative path and expected/observed byte identities when a hydrated
file mismatches, without skipping or rewriting it. Its synthetic test confirms
the error remains fail-closed and preserves the original wrong bytes.

**Candidate status:** awaiting protected tests and a fresh independent native
staging/read result on the new exact SHA. No native scene/material admission,
saved consumer or geometry change claimed. PR remains Draft; owner visual
`PENDING_FINAL_M3`, FPS `DEFERRED_AFTER_M3`, `performance_pass: false`.

## Native LFS checkout diagnosis and offline hydration repair — 2026-10-10

[Native run 38061545088](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061545088)
at `e950d6b19fd721fff4bbc699ec03b9c919d4b2a1`
**FAILED during dependency hydration, before Unreal** despite
[exact-head protected CI 38061548431](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061548431)
passing. [Artifact 11673397029](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38061545088/artifacts/11673397029)
identifies `Content/Generated/YACS/MaskReview/M_MaskReview_1.uasset`
(expected 11,780 bytes, SHA-256
`0d6a1a6061fd8922b44f6c7ae7d49b9219182149deed1cca42d5f4c0d2047068`)
as still the **exact committed 130-byte Git LFS pointer** (SHA-256
`00a8cfcafa5946a7c7ca36b70463c34bc9dc2bee1328f72a6bd8c6e8cfc20229`).
This source is short, so the previously suspected long-path boundary
**does not explain the observed failure**. Short isolated checkout remains
a harmless Windows path safety improvement, not an admission claim.

The active original asset cache, original Automation summary and exact source
fingerprints were all verified and unchanged. The current repair candidate
initializes Git LFS filters **locally inside only the fresh code-only checkout**,
under the isolated Actions Git environment, with automatic smudging disabled.
It then performs bounded batches of explicit-pinned `git lfs checkout`
against the already SHA-256-checked offline cache, verifying each batch before
continuation. No remote fetch, arbitrary input, silent overwrite of modified
owner assets, geodata/geometry change or weakened hash guard is introduced.
A synthetic test exercises missing local filters, empty global/system config,
skip-smudge and multi-batch hydration before comparing original bytes.

**This is a candidate, not evidence that the native stage now passes.**
Both new exact-SHA CI and the independent native rerun remain required.
The #364 asphalt canary, saved/fresh-rendered consumer and final owner
visual audit remain pending. Performance stays `DEFERRED_AFTER_M3` /
`performance_pass: false`.

## Real native map read and bounded redirected-log teardown fix — 2026-10-10

[Normal exact-head CI 38062379452](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062379452)
**PASS** at `50d02fa69bdf4bbbe5679759245672621bec9d90`.
[Native run 38062375118](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062375118)
**FAILED on host receipt teardown**, but notably progressed through the
previously failing LFS stage and an actual native Unreal Editor read:

- [Retained artifact 11673672792](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38062375118/artifacts/11673672792)
  contains `session-preparation.json` with status
  `ACCEPTED_CONSUMER_BYTES_STAGED` (236 dependencies, 14 consumer assets),
  `road-material-baseline.json` with
  `ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE`, and original Editor logs.
- UE **5.8.2-56702186** genuinely started on the frozen saved derived consumer,
  MapCheck finished with **zero errors and warnings**, and the native reader
  reported **1 road, 186 supports, 1024 Landscape components**. The owned
  Editor returned exit code **0**.
- Reader receipt recorded `read_only: true`,
  `pre_post_inventory_equal: true`, `saved_asset_bytes_unchanged: true`,
  `persistent_world_mutation: false`, `material_authoring_verified: false`,
  `full_mesh_geometry_hash_verified: false`, and correct M3 deferrals.
- **The overall native job did not pass**. Host receipt `status: FAILED`,
  `reader_pass: false` after Windows rejected hashing the two redirected
  `owned-editor-stdout.log` / `owned-editor-stderr.log` files while still
  open by another process. The wrapper's fail-closed finalization correctly
  rejected partial evidence. No accepted native stage/merge is inferred.

The scoped repair adds a **bounded sharing-violation-only retry** for the
real redirected Editor stdout/stderr identity reads, up to forty attempts
with 250ms pauses (no new process launch or output mutation). Every log
must still hash successfully with its existing 64MiB bound and stable
size/mtime check. Non-sharing failures fail immediately; persistent locks
still FAIL the host receipt. A dedicated actual PowerShell function test
exercises transient success, immediate unrelated I/O rejection and bounded
persistent failure. The current document section is a candidate pending
protected exact-head CI plus a **separate independent native rerun**.
Owner visual `PENDING_FINAL_M3` and performance
`DEFERRED_AFTER_M3` / `performance_pass: false` remain unchanged.

## Correct native road support label boundary — 2026-10-10

The authenticated [native baseline from run 38063289931](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063289931)
records exactly 186 supports named `YACS_PERSIST_SUPPORT_000` through
`YACS_PERSIST_SUPPORT_185`, not `001` through `186`. The synthetic
transient asphalt canary still expected the latter and would falsely reject
the accepted frozen scene. This correction makes the material-only canary
use actual native saved actor labels; it changes no scene, topology, Physics
Profile, Landscape or support material ownership. A new exact-range and
out-of-range regression is included; native asphalt assignment remains
**NOT VERIFIED** until an actual separate editor run.

## M3 asphalt on accepted road — bounded transient native execution candidate

The owner resumed #364 after the exact-HEAD green
[CI 38063294944](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063294944)
and independently green
[native baseline 38063289931](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38063289931)
at `229c4e416f7149fd1a6ae383ae0fe31a7547f21b`.
The actual captured native scene has one road (856,250 vertices,
1,711,760 triangles), 186 **zero-based** supports and 1024
Landscape components. The baseline is source/geometry read only.

This **implementation candidate**, in the same #364 Draft PR, adds:

- `scripts/ue/road_asphalt_source_preflight.py`: separately verifies the
  retained two-run `aged_mountain_asphalt/base` producer bundle from exact
  source `6fa54b50` and original run `38045485913-1`, pinned original
  receipt SHA-256 `3626bf85…`, source fingerprint `b4d93e24…`, and
  graph `6b381516…`. Missing retained source is a hard failure: no
  implicit re-render, download or loosened hash check.
- `scripts/ue/run_road_asphalt_native_canary.py`: independently rechecks
  the staged consumer, original producer bytes, projection
  `WorldAlignedTexture`/`WorldAlignedNormal`, original road/side materials
  and the exact saved scene; reuses the existing Material Forge importer with
  `save_assets=False`, world alignment 400 cm and DirectX normals. It
  temporarily swaps **only the road material slot zero**, verifies material
  readback and the complete actor/material/geometry snapshot, restores the
  original slot even on failure and verifies input packages unchanged.
- `scripts/ue/Invoke-YacsRoadAsphaltNativeCanary.ps1`: a **second,
  separately owned Unreal Editor process** only after the existing complete
  read-only native baseline passes in the same isolated Windows checkout.
  Authentic original baseline hashes, exact source SHA, approved engine/DLLs,
  the trusted host lock, bounded process lifetime and exclusive proof files
  remain mandatory. Actual-run logs and trial receipt are retained.
- Synthetic source, native entry, slot ownership and host/workflow tests.
  Source `YACS_PERSIST_SUPPORT_000..185` identity is corrected; no geometry
  mutation or support-side material replacement is allowed.

The first native canary intentionally runs with `-NullRHI` to validate the
Material Editing API, importer graph and reversible native slot binding
without claiming GPU shader compilation or a rendered appearance pass.
`shader_gpu_compilation_verified: false`,
`saved_consumer_verified: false`, `owner_visual_status: PENDING_FINAL_M3`
and `performance_pass: false` remain binding. Actual native canary success
requires an independently completed exact-SHA workflow and readable
`road-asphalt-canary.json` **plus** `asphalt-host-receipt.json`; source,
synthetic tests or a green regular Unreal build alone never admit this stage.

Future #364 batches must separately prove real shader output, authored
shoulder-top/wall slot separation, a new saved material-only derived consumer,
fresh reopening and review frames from both road directions. Do not merge until
all applicable technical/review gates and final M3 owner audit policy are met.

## Transient Unreal Python bootstrap correction — 2026-10-10

[Native #38065442572](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38065442572)
at `99da397bf880d9d4a68449d7bc1c2bc7404dd580` **failed** in its second
Editor process, after the complete read-only baseline PASS. The retained
[artifact 11674572801](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38065442572/artifacts/11674572801)
confirms that `asphalt-source-preflight.json` succeeded with two pinned original
renders and that the Editor launched. Its actual `asphalt-editor.log`
records `ModuleNotFoundError: No module named 'scripts'` at line 17 of
`run_road_asphalt_native_canary.py`. Unreal's `-ExecutePythonScript`
does not automatically add the script's repository root to Python's path.
The Editor exited 3; no material import, assignment or rollback was observed.

The corrective candidate inserts only `Path(__file__).resolve().parents[2]`
into the transient script's Python search path before any repository imports.
The host continues to verify exact committed script bytes and isolated checkout.
A hosted regression executes the real Python entry with `-I` and an unrelated
working directory, with no ambient project import path; it never starts UE.
Source, map, material and geometry inputs are unchanged, and no success is
claimed until a fresh exact-SHA CI and independent native Editor trial pass.

## Saved road-asphalt derivative and independent fresh-reload candidate — 2026-10-10

This stage follows the verified [native road-slot-only transient PASS
38066292810](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38066292810)
at exact SHA `4f11e0dadf3ac099e49402ca69f319c592052dd0`
and its [protected green CI 38066296977](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38066296977).
The new implementation is **not yet native-admitted** simply because its
source has been committed.

- `scripts/ue/road_asphalt_saved_consumer.py` is the bounded two-action
  Unreal entrypoint. In `prepare`, require the original pinned source replay,
  real accepted saved scene, native baseline and rolled-back transient canary.
  Reuse the verified Material Forge importer with `save_assets=True`,
  metric 400 cm projection and DirectX normal settings, bind only the
  original road DynamicMesh material slot zero and save **only** the new
  `/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview`
  map. Verify the complete old/new actor, road mesh, all 186 supports,
  Landscape 1024 components and other material bindings remain identical
  apart from road material slot zero. Verify immutable source/retained
  producer bytes before/after. Preserve new files with exact SHA-256/byte
  sizes in `D:\yacs\work\road-materials\saved-consumers\<sha>\<run-attempt>`.
- In `reload`, a **separate fresh Editor process** loads the new saved
  map, never reassigns or saves a material, checks the same normalized
  inventory digest and all four real Material Instance texture parameters,
  effective `TileSizeCm=400` and DirectX normal compression/green/sRGB.
  The original map and derived packages must still match their raw SHA-256
  and byte-sized immutable manifest. No rolling back the **new saved**
  material binding: the original accepted map is not modified.
- `Invoke-YacsRoadSavedConsumer.ps1` owns serial, isolated,
  exact-HEAD/host-lease authenticated **prepare -> reload** Editors.
  The existing successful baseline and transient canary must precede
  either process; both actual native receipts and stdout/stderr/Editor
  logs are mandatory. The host writes a separate exclusive
  `saved-road-host-receipt.json` only after both operations.
- New offline synthetic tests cover world-identity-only normalization,
  original/support/Landscape mutation rejection, no-overwrite package
  retention and mandatory source/workflow boundaries.

This candidate intentionally uses `-NullRHI`: it is **a saved native
binding and reload test**, not a claim of GPU shader compilation,
high-quality rendered pixels, whole-area shoulder/wall transitions,
owner visual PASS or final material delivery. Owner audit
`PENDING_FINAL_M3`; performance `DEFERRED_AFTER_M3` /
`performance_pass: false`. PR #470 remains Draft and #364 remains OPEN
until the further roadmap/native/asset/render/review gates pass.

## Native saved-consumer baseline JSON equality fix — 2026-10-10

[Protected exact-head CI 38068143388](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068143388)
**PASS** on `432dfad3ef2067b8d34a9c7f4508fec21b6a3a4d`.
[Native #38068139306](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068139306)
**FAILED in the new prepare Editor**, after the authentic base read and transient
canary both passed. [Retained artifact #11675927513](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068139306/artifacts/11675927513)
shows a read-only failure at `inventory_before == before` before
any Material Forge import or derived map save. Its prior complete baseline
inventory agrees *exactly* with the independent green native baseline at
`4f11e0da`, including 375 world actors, all road/support
material/geometry/collision slots and Landscape 1024 components.

Cause: the native inventory creator represents its sorted `actors` as
`list[tuple]`. Its persisted authenticated JSON receipt serializes tuples as
JSON arrays and Python restores them as `list[list]`. Direct Python equality
fails on the container type even for identical semantic snapshot bytes.
The candidate now hashes **every** original/live field in the **same
canonical JSON serialization domain** (`sort_keys=True`, explicit separators
and finite values) and requires the SHA-256 digests to match. Actor transforms,
component/material ownership, geometry counts and all other fields remain in
the comparison; nothing is ignored. Synthetic regression proves tuples and
their exact JSON arrays hash identically while an actual transform mutation
fails. No Landscape/map/asset mutation was performed in the failed native
attempt. Fresh exact-SHA CI and **new independent saved-map/Editor proof**
are required; no saved consumer PASS is inferred from this fix.

## Strict road material slot snapshot mismatch diagnostic — 2026-10-10

[Protected CI #38068822892](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068822892)
**PASS** at `10464c9ce6aaa07fc514fb6ee63b133a926b7719`.
[Native run #38068818538](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068818538)
**FAILED before derived map save or fresh reload**, although the original
read-only scene, source replay and reversible transient canary passed.
The [retained original Editor log #11676386973](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38068818538/artifacts/11676386973)
shows the Material Forge importer successfully **wrote its own six material
packages** under the isolated `RoadAsphaltConsumer` namespace; then the
material-only scene equality check rejected
`_expected_live_snapshot` after binding road slot zero.
This is **not** an accepted new derived world. The original accepted
Landscape, road/physics authority and source map were not saved or
replaced. Permanent package retention had not begun.

The next candidate changes **diagnostics only**, not admissible state:
the existing complete `during == expected` proof remains mandatory.
When it fails, the error now includes up to eight exact structural paths
(e.g. `$.road_supports[1].vertices`), including type/missing/length
differences, without logging geometry/transform values or relaxing any
source/asset/scene guard. A fixed 100,000-node diagnostic budget prevents
unbounded scans. A dedicated synthetic test proves field-level mismatches,
strict identity for untouched inventory, length detection and no raw value
disclosure. A new protected exact-SHA CI and independent native save attempt
must identify and resolve the observed drift; do not treat this diagnostic
candidate as material/geometry/reload PASS.

## Native atlas ownership: original map names before SaveMap — 2026-10-10

[Exact-head protected CI #38069493158](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38069493158)
**PASS** at `90df60e6a84ba3bc25d6dd757b07cda90a17354f`.
[Independent native proof #38069488817](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38069488817)
**FAILED during new-map preparation**, although the original read-only
scene and reversible material-only asphalt canary both passed. The
[retained Editor artifact #11676467435](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38069488817/artifacts/11676467435)
records actual saved Material Forge master/instance/four texture packages
(6 assets, TileSizeCm=400), then a strict native inventory failure with
`first_differences=['$.actors[0][0]', '$.actors[1][0]', ...]` before
`SaveMap`. Neither final derived map nor fresh-reload admission exists.

The mismatch was caused by a bug in **comparison identity**, not admitted
terrain drift: after the road slot was changed, the Editor still owned
`session.operation.MAP_PACKAGE`. The `expected_saved_inventory` helper
prematurely normalized observed actors as if the future `MAP` SaveMap target
already owned them. The resulting map name prefixes differed for every
actor path while geometry and materials were otherwise protected.

The repair requires an explicit, authoritative `observed_map_package`:
**the canonical accepted source** immediately after transient slot assignment
and **the new derived map** only after `SaveMap` / on fresh Editor reload.
A mismatch between the requested phase and the actual inventory
`map_package` remains a hard failure. It still compares every source/target
field, actor path, transform, geometry/collision/material inventory and all
Landscape components exactly; there is no bypass for actors. New offline
tests reproduce both phases, reject an incorrect declared phase or foreign
map, and fail on altered actor transforms. New protected exact-SHA CI and
independent native save/reload are required. This fix alone is **not PASS**.

## SaveMap successfully wrote the map; Editor world remained the source — 2026-10-10

[Protected exact-head CI #38072282586](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072282586)
**PASS** at `a1ffacddb14be4a3fc76287fdc6ad6ed685dec71`.
[Independent native #38072278630](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072278630)
**FAILED in prepare** after the original source native baseline and transient
road-slot canary **passed again**. The retained
[artifact #11677521256](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072278630/artifacts/11677521256)
shows that the genuine Material Forge six packages were saved and Unreal
successfully wrote
`/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.umap`:
`LogFileHelpers: Saving map ...` completed. No fresh-reload receipt exists.
Failure occurred *after* SaveMap: the Python script tried to read the
current Editor world as if it was already the new map and
`read_road_material_baseline.native_inventory` refused
`ValueError: wrong loaded consumer map`.

The installed UE 5.8 `EditorLoadingAndSavingUtils.save_map(world, MAP)`
writes a **new derived map package**, but does not guarantee swapping the
current Editor world to that destination. This is a contract error in
the **follow-up in-memory inspection**, not evidence that the derived map
file was absent or that accepted source geometry changed.

The next bounded fix observes the actual Editor world package immediately
after saving (must be **exactly the original source map or the new derived
map**, no arbitrary package), requires the new `.umap` file to physically
exist and checks the full current-world inventory using that observed
identity. The **fresh, separately owned second Editor** remains the
mandatory authority for loading and comparing the new persisted map
against the expected full normalized road/support/Landscape snapshot.
The code **does not** use this in-process check as fresh reload proof,
never edits the original source map package and never loosens material,
geometry or hash admission. Tests cover both observed-world cases and
foreign-map rejection. This source change remains unverified until
protected CI and a new exact-SHA native save/reload result.

## Genuine save passed; package inventory must traverse real directory nodes — 2026-10-10

At exact source `77e87e45cc3568113bca83f2be4269c85d4f5c5f`,
[protected CI #38072942254](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072942254)
**PASS**. In the independently gated
[native run #38072938977](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072938977),
the accepted baseline and reversible road canary passed; UE5.8 saved all six
Material Forge assets and
`L_SaCalobraRoadAsphaltReview.umap`. The
[retained failure artifact #11677547020](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38072938977/artifacts/11677547020)
records **no final manifest or fresh reload**. The post-save package inventory
failed at `produced_files()`, line 239,
`ValueError: Unexpected package family member`.

This was caused by scanning `folder.rglob("*")` and treating every member as
a regular package file: Material Forge necessarily places assets in nested
`aged_mountain_asphalt/base/<graph-hash>/` directories. The scoped fix
authenticates **every** descendant's path with the pre-existing
`session._safe_path` junction/symlink/reparse-point guard, then explicitly
allows ordinary directories to be traversed while **requiring that every
non-directory member** be a bounded approved `.uasset`, `.umap` or
permitted package sidecar. All actual files still undergo SHA-256, size/count
limits, independent persistent-copy verification and no-overwrite rules.
Neither path aliases, unknown files nor silent filesystem omissions are
admitted. Synthetic regression builds a real nested 1-map/6-asset structure,
rejects an unexpected file and rejects symlinks when the host permits
their creation.

Original accepted world, road/support geometry and Landscape remain frozen.
Successful `SaveMap` alone is **not** a fresh-opened consumer proof; the
candidate requires a new exact-SHA protected CI and native two-process reload.

## M3 native road-facing GPU Lit review candidate — 2026-10-10

The [first complete exact-head saved + independent fresh-reload proof
38073659235](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38073659235)
and [protected CI 38073662051](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38073662051)
are both **PASS** at `c57ef87e476bf8a4fc2ff1e9c7bb6c2b0449fd32`.
The previous read-only Scene Inventory, transient asphalt bind/rollback,
saved `RoadAsphaltConsumer` derived map, six Material Forge assets,
durable SHA-256 bytes and a **separate fresh Editor reopen without reapplication**
are now **technically verified**. These are source/asset/scene checks with
`-NullRHI`, not pixel/lighting acceptance.

The next bounded #364 subgate is **four road-facing, bidirectional GPU Lit
screenshots** from the exact frozen window **0112**. The producer is the
unchanged
`docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv` (raw SHA-256
`15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3`),
not a new interpolated map, invented camera or route restaging. Exact IDs are
`window-0112-forward-00001`, `window-0112-forward-00002`,
`window-0112-reverse-00001` and `window-0112-reverse-00002`. The 1280×720,
76-degree-FOV road poses are reused as photographed by the accepted
TPP source. No sphere/traffic/collision actor is created; only a transient
camera is allowed. The original CSV includes an unreviewed visual status,
which is not silently upgraded by this reuse.

The new `scripts/ue/road_asphalt_gpu_review.py` strictly authenticates
the current same-exact-SHA native base, transient canary and saved/fresh
consumer host receipts, stage identity, source camera CSV, all retained
derived asset byte hashes and the full real saved road/support/Landscape
inventory **before** requesting any screenshots. It opens the **saved
derived** map in a new GUI `UnrealEditor.exe -RenderOffscreen` process
(not `-NullRHI`). The native `AutomationLibrary` produces four independently
named Lit PNGs with complete format/CRC/dimension checks and fixed sampled
non-blank diversity, retains per-frame SHA-256/bytes and camera provenance,
destroys the transient camera, restores viewport position, then checks
the exact complete scene and all immutable packages again.

The new serialized host `Invoke-YacsRoadAsphaltRender.ps1` only starts
after existing exact-SHA protected CI, read-only baseline, transient
road-slot canary **and native saved/fresh reload** have passed in the
same run. It refuses an owner-active Editor, authenticates the installed
Unreal commandline executable and derived same-directory GUI executable,
enforces strict source/checkout boundaries, caps the render Editor to 480s,
requires four exact file IDs and checks every output hash. Retained
`road-asphalt-lit-review.json` and
`road-asphalt-gpu-host-receipt.json` record failure as failure; a missing
PNG, crash, alias, saved-asset drift or unsupported material is not
coerced to a PASS. The workflow keeps the normal 22-minute serial
native-job cap, including preparation and GPU work.

**Admission boundary:** this is a four-frame **technical camera/render canary**,
not whole-area approval. Valid lit screenshots do not alone certify that
asphalt covers specific visible pixels, that GPU shader compilation produced
the intended normals/roughness, or that shoulder tops vs retaining walls
have correct material ownership. `road_pixel_visibility_admitted=false`,
`gpu_shader_compilation_admitted=false`,
`shoulder_wall_materials_admitted=false`,
`whole_area_visual_admitted=false`, owner visual
`PENDING_FINAL_M3`, performance `DEFERRED_AFTER_M3` /
`performance_pass=false`. The resulting four PNGs must be inspected
before choosing any quality iteration, then a distinct shoulder/edge/wall
ownership pass and ultimately complete-area M3 owner review.
This source candidate is **not a native render PASS** until separately
proven at its new exact SHA.

## First real road Lit PNGs and Windows GPU-exit follow-up — 2026-10-10

At exact SHA `fc4430197015c2d7823950c5458cc74ac05f957b`,
[protected CI 38075979780](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38075979780)
**PASS**, including hosted tests, Windows Unreal/Automation and Aggregate CI.
The independently gated
[native 38075976518](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38075976518)
**FAILED only the new GPU Lit step**: complete native accepted baseline,
transient slot-zero asphalt and saved/fresh-reloaded derivative all
**passed on the same SHA**. Its
[artifact 11679615853](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38075976518/artifacts/11679615853)
contains four **real 1280×720 UE5.8 Lit PNGs**, two forward and two reverse
of window 0112, source camera/FOV pinned, and exact per-PNG
hashes in `road-asphalt-lit-review.json`. The observed screenshot
nonuniformity was 1531/1647/1723/1737 sampled RGB values.

Technical visual inspection now shows real muted grey, micro-cracked
asphalt road (first material appears on **road** pixels), but also
hard-edged light shoulders/support faces, pronounced vertical tan cliff
striations and black wedge/seam artifacts in the first forward
hairpin view. Neither road material quality, shoulder/wall ownership
nor entire area can be marked 8/10 / owner PASS from these frames.
These defects must remain actionable in #364 and #372 review; visual
material alone cannot conceal geometry defects or thaw frozen Landscape.

Two independent final-proof defects are captured:
1. `road-asphalt-lit-review.json` is `ROAD_ASPHALT_LIT_REVIEW_FAILED`
   **despite four captured PNGs**, with
   `errors=["dirty scene: native map/content is dirty"]`. Spawning and
   removing even a `transient=True` CameraActor in the *derived
   in-memory* UWorld can mark that map package dirty. All original asset
   SHA/inventory checks passed, and no saved map was changed. The repair
   explicitly accepts **only the known derived map's unsaved dirty
   package** and **zero dirty content packages**, with an exact package
   path audit in the native receipt. The original source and any other
   package dirt remain hard-fail; full after-render geometry, actor,
   support, Landscape and byte-exact saved packages still must match.
2. The owning real GUI `UnrealEditor.exe -RenderOffscreen` returned
   **-1073741819 / 0xC0000005 access violation** during shutdown *after*
   all four PNGs, a `QUIT_EDITOR`, and log line `LogExit: Exiting.`.
   Neither native proof nor renderer acceptance is claimed from those
   images. The candidate inserts ten seconds of **no new frames/tasks**
   after final screenshot completion before camera teardown/exit and
   disables the concurrent RHI thread with `-norhithread` for a
   bounded diagnostic shutdown. The Windows process **must still exit 0**,
   with four authenticated original-size PNGs, a pristine source/saved
   map and positive `road-asphalt-gpu-host-receipt.json`, before
   the native job may mark this subgate PASS. A real exit crash or
   foreign dirty asset is never downgraded to success.

This is a new small diagnostic native candidate, NOT an admitted
render. No maps/packages are saved or edited by the GPU run; original
Landscape frozen globally. Final owner M3 visual audit and
`DEFERRED_AFTER_M3` FPS remain unchanged.

## Live material checkpoint candidate — 2026-10-11

Issue #473 supports #364 with explicit derived-world checkpoint saving. The
fixed `checkpoint` command duplicates the current world and persistent road /
shoulder materials into a new revision-owned package directory. It verifies
all dynamic-mesh copies with native exact comparison and preserves the active
world, camera, source packages and route alignment. Existing destinations are
never overwritten. Failed saves retain only the named partial output packages,
preserve the live preview, and remain failures. Saved bytes are authenticated
by the client; this is not fresh-editor reopening or visual acceptance.

Local validation: material bridge/client/panel 102 PASS, two Windows symlink
capability skips; surface/shoulder 18 PASS; saved consumer, shoulder material and
source preflight 73 PASS. The existing all-out-of-bounds shoulder regression
remains intact: production now rejects repairs with no verified bounded outer
contact instead of lowering the test requirement. Native checkpoint NOT RUN.

Live session `y473live01` applied worn materials and a bounded repair to support
112 without restarting PID 33524. Both inner edges are targeted, but 47 outer
contacts on column zero remain deferred: terrain is beyond the 50 cm bound or
the bounded trace misses. This is not a whole-road or both-sides completion.
Further contact geometry belongs to #459 and must preserve canonical asphalt
and the global Landscape freeze. Preserved normals may need a separate shading
correction. #364 remains OPEN; #365 PCG remains dependency-blocked. Final M3
owner visual acceptance stays pending and performance stays
`DEFERRED_AFTER_M3`, `performance_pass: false`.

Native follow-up: session `y473save01`, PID 14704, saved a derived checkpoint
at handler revision `2a00f7ebba403cf7cda663bc6fa303c7d72e891b` after one
authorized installation restart and subsequent live reload. The failed first
save recovered without losing the worn surface or repair. Final request
`panel-ac7fe7ff172d4e7b91eb47dbe7aec03b` completed: five saved packages,
186 persistent material bindings, 559 exact native mesh comparisons, unchanged
asphalt. Map SHA-256 `cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a`.
See [stream evidence](../tooling/LEVEL_EDITOR_STREAM.md#explicit-saved-checkpoint-and-current-native-result--2026-10-11).
Surface/shoulder tests now 19 PASS. Fresh-process reload remains NOT RUN; the
new AOI has 50 deferred contacts on one side and is not full geometry repair.

## Material-only closeout continuation — 2026-10-11

The owner deferred the remaining steps/contact geometry to #459 and retained
its limits. #364 can continue its existing material scope; this is not a waiver
of fresh reload/render or protected delivery. CI run38167515175 failed five
camera error tests: the generic material recovery path swallowed camera
exceptions and reset material state. Production now retains the distinct
camera rollback contract, preserves materials, records BLOCKED, blocks further
mutations and propagates the original exception. The existing camera tests
were not changed. Focused camera/bridge/client/panel suite: 112 PASS, two
Windows symlink capability skips. This bridge change is source-only for the
next installation; no live camera action or editor restart was performed.

The [prepared PCG handoff](../ROADMAP.md#prepared-handoff-from-364-to-365--2026-10-11)
pins saved outputs, engine/plugin baselines, source masks, exclusions and
remaining gates. The current live review snapshot does not include PCGEx.
No #365 implementation or source/terrain/physics mutation is claimed.


### Owner preview interruption during closeout — 2026-10-11

CI run `38168499513`, job `114557325505`, terminated owner Editor PID `14704`
at `2026-10-11T19:41:23Z`. The cleanup helper matched a Python launcher path
inside the runner workspace even though the owner project lived outside it.
Its ownership check ran too late. The helper now enforces the existing host
ownership contract before mutations and both kill paths. Executable fixture
regressions preserve the owner process/log and still clean stale unattended CI.

That run passed on `194159b7aca552164cb9e08a92eb5b3159f9b0fe` using
`verified-equivalent-proof`; it did not fresh-load the new material checkpoint.
Blender run `38168498901` was cancelled. The earlier saved checkpoint remains
retained; subsequent request sequence 10 recovered from
`Apply a surface preset before checkpointing` and did not save a new candidate.
PR #470 and release v0.3.1 remain drafts pending outstanding proof and review.
