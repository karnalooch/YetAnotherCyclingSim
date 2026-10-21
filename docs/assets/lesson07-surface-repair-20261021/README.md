# Lesson07 acquired CC0 surfaces and bounded native repair

**Type:** implementation and source evidence, supporting the
[Lesson07 audit](../../tooling/sidefx/LESSON07_MATERIAL_SETUP.md).
**Issue/stage:** #365 / M3, existing Draft PR #474.
**State:** source acquisition, native import and saved-array readback verified;
the rendered candidate remains too dark and visibly stretched on steep faces.
Detailed normals, physical scale, fresh reopen and whole-area acceptance remain open.

## Current native result

[Run 39636694686](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39636694686)
completed the reviewed operation from `c59f717f11b134f75f695a26b94f8655bd3bd271`:
five new textures and three existing arrays were saved. All six native calls
completed (one import and five captures), with twelve matching owner/process/
listener checks. Four Landscape snapshots were identical before and after;
Grass Colour and slots 1/2/4 were preserved. The map, material instance and
shader graph were not saved or changed by this operation.

The [evidence index](import-39636694686-evidence.json) binds the original native
receipts, the byte-preserving compressed bridge report and all five JPEGs.
The same-camera [BEFORE](import-39636694686-surface-before.jpg) and
[AFTER](import-39636694686-surface-after.jpg) show excessive darkening of the
Cliffs candidate; vertical streaks remain. The
[panorama](import-39636694686-surface-panorama.jpg),
[Puig Major](import-39636694686-surface-puig-major.jpg) and
[Scree](import-39636694686-surface-scree.jpg) views do not establish resolved
projection, physical texel scale or whole-area quality. These are image-review
findings, not a measured diagnosis of their geometric or shader cause.

`Global Normal Flatten=1` and `Macro Tiling=0.05` remain unchanged. Correct
source normal maps do not establish a correct inner-function sampler or
normal reconstruction. The frozen denied observer is not retried. A separate
metadata-only discovery completed with zero native calls and 84 advertised
tools. The full `edit_graph` contract exceeded the existing report size bound;
no material-function graph-read capability is inferred from that excluded
contract. The [discovery evidence](discovery-39638776763-evidence.json) separates
this successful metadata operation from a later historical error-reader step,
which refused the different owner session with `FAILURE_LOG_OWNER`. That guard
and the old observer remain unchanged. A bounded follow-up retains the complete
plain-text `edit_graph` description only when it passes the existing secret
checks and an explicit size limit; it does not claim a complete tool schema.

Protected [CI 39636709351](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39636709351)
passed the hosted code/policy/security checks, but native workspace admission
refused `LOCAL_BUSY` while the owner Editor was active. No native build proof
was reached. This does not change the successful in-place import result or
admit final protected delivery.
The subsequent source-only [CI 39638791772](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39638791772)
also refused native admission with `LOCAL_BUSY`; the active owner Editor was
preserved. Neither result is a fresh native build or Automation pass.

## Retaining the saved candidate

The [bounded exporter](../../../scripts/ci/export_lesson07_material_checkpoint.py)
and [delivery workflow](../../../.github/workflows/lesson07-material-delivery.yml)
retain exactly nine packages: five imported textures, three updated arrays and
the previously approved Macro 0.05 material instance. The latter closes an
existing branch-persistence gap; it is not a new scalar edit. Full export is
pinned to the successful producer's exact native receipt bytes.

The Windows phase only reads stable canonical files and writes a new run
directory. A hosted phase uploads their explicit Git LFS objects and downloads
them into empty storage for independent hash/size verification. Only after that
proof may the connector commit the nine pointer texts with a branch-head lease.
This retained candidate remains visually unaccepted.

[Delivery run 39638776920, attempt 2](retention-39638776920-evidence.json)
completed the Windows export and retained immutable artifact `12364181709`
(115,911,097 bytes; GitHub-reported archive SHA-256
`0eb92760bb74917e2349c1066d4cc3efd5229949ad1fcb6f68936faba3266c9e`).
The hosted explicit-OID push returned successfully, then independent `git lfs
fetch` timed out after 900 seconds. Server byte verification and branch pointer
publication are therefore still pending. The failed fetch scanned a local
commit with the full repository tree; git-lfs applies its include filter after
`ls-tree -l`, creating an unrelated promisor-blob hydration risk. A bounded
correction builds the readback commit from only the nine already verified
pointer blobs in a temporary index. It preserves the empty-storage readback,
hash/size checks, source pins and branch lease; it does not assert that the
scanner was the proven cause of the first timeout.

## Acquired sources

| Family | Author | Original files | Physical repeat | Current use |
| --- | --- | --- | --- | --- |
| [Dark Rock 02](https://polyhaven.com/a/dark_rock_02) | Amal Kumar | 2K Diffuse, NormalDX, Roughness, AO, Displacement | Approximately 2.000917 m square | Neutral-grey Cliffs appearance candidate |
| [Rock Boulder Dry](https://polyhaven.com/a/rock_boulder_dry) | Dimitrios Savva, Rico Cilliers | 2K Diffuse, NormalDX, Roughness, AO, Displacement | 1.8 m square | Retained light-rock comparison; not assigned |

Both source sets were downloaded from official `dl.polyhaven.org` URLs under
[CC0-1.0](https://polyhaven.com/license). Each has five complete, mutually matched
2048 x 2048 PNG maps; all ten files passed byte-size, SHA-256 and decode checks.
[Source provenance](provenance.json) records their exact identities. The original
maps and complete source ZIP remain outside Git; the source ZIP contains ten
maps plus README, license, provenance and checksum files (14 entries,
137,119,008 bytes, SHA-256
`b373f67630e0f4eb72fca27df9b688909c15a126a34097622edfd41e5f2ea613`).

A separate ready-to-import three-map Cliffs ZIP contains the neutral-grey
Colour, DirectX Normal and packed Pegasus Masks plus README/provenance/hashes
(26,935,262 bytes, SHA-256
`28255097bff08dd10cc793fbdd1ebbddcac52017e01ef48449476fd9dbe36782`).
It does not contain the remote-only retained Grass maps and is not represented
as the complete five-map native package.

The provider describes generic rock, not authenticated limestone. Dark Rock 02
is distinct from the previously rejected `dark_rock` asset. It is a visual
candidate, not a geological claim or a replacement for the still-unacquired Fab
packages. Its original brown chroma is removed in the derived albedo; original
source files are preserved. The accepted Grass2 layer is unchanged.

## Existing Pegasus material adaptation

This follows the existing Lesson07 matching Colour/Normal/Masks array method
(official Lesson07 24:36-25:31 and Landscape Material / Functions 10:21-11:41,
as reviewed in the main audit). It does not generate terrain, roads or masks.

The [offline adapter](../../../scripts/assets/prepare_lesson07_surface_repair.py)
has fixed source URLs/hashes and no arbitrary target parameters. It copies the
two already prepared Grass data maps from run `39519585751` without regenerating
them, and creates three matching Cliffs maps. The five-map
[package manifest](surface-repair-package.json) has SHA-256
`e8e0ae6cbd752b6b564a67b830aa16a5c4dbb01db3af9792963e8c6121bc88a6`.
The two retained Grass maps exist on the Windows host; local regeneration
produced different bytes and is not treated as matching evidence.

- Colour: original RGBA16 high eight bits, sRGB to linear Rec.709 luminance and
  back to achromatic sRGB. The result preserves luminance subject to 8-bit
  quantization. It is not an exposure boost or a claim of native appearance.
- Normal: matching DirectX source, high eight bits with no gamma conversion or
  green inversion.
- Scalars: raw grayscale16 divided by 257 and rounded to nearest. Direct
  Pillow conversion to `L` would clip values above 255 and is not used.
- Masks: R=AO, G=Roughness, B=Height, A=AO. Runtime displacement stays disabled.
- PNG packaging: fixed filter-zero rows and standard RFC1951 stored blocks
  give platform-independent serialized bytes. These temporary 16 MiB files
  are decoded by Unreal and are not its runtime texture format.

The native [importer](../../../scripts/ue/apply_lesson07_surface_repair.py)
adapts the existing `apply_lesson07_grass2.py` AssetImportTask/SourceTextures
pattern. Dedicated installed Wingman texture tools do not expose local PNG
import or array-source rebuild. The new importer is a distinct, explicit
`execute_python(file=..., mode=file)` request through the normal gate. The
F49-denied observer remains byte-identical and is not retried or bypassed.

The operation requires one verified existing owner Editor on the canonical
Lesson07 map, validates four expected Landscape actors and current asset hashes,
retains byte backups of three arrays, imports five new texture assets and saves
only those assets plus the three affected arrays. Slot 0 receives corrected
Grass Normal/Masks; slot 3 receives the coherent Cliffs family. Grass Colour,
slots 1/2/4, the material instance, shader graph and geographic inputs are
preserved. Existing colour-array grading is retained for accepted layers;
achromatic Cliffs input avoids introducing a hue shift in that slice.

The material's saved `Macro Tiling=0.05` and `Global Normal Flatten=1` remain.
The latter suppresses detailed normals and is a separate unresolved shader
issue; importing correct normals does not itself resolve it. Physical repeat,
steep-wall projection and whole-area appearance still require actual UE proof.

## Execution and verification

The `[l07-import-surfaces]` mode stages the fixed package in a new
`Saved/RuntimeProof/Lesson07SurfaceRepair-20261021/<run>-<attempt>` directory,
captures BEFORE, submits one import, and captures AFTER from the same camera,
then captures the existing panorama, Puig Major and Scree presets. These six
calls contain one import and five screenshots. Their one-frame camera overrides
must match native readback and report restoration; the old scene-changing
capture script is not executed. Each call checks the process, native start time,
owner and listener before and after. A denial,
timeout, stale receipt or failed asset guard stops the operation without retry.
On successful completion, the import receipt and all five exact JPEG files are retained. Import mode cannot start
an Editor or change configuration.

Offline preparation passed six focused tests and independent full-image
roundtrip/hash review. The initial importer passed ten CPU tests; the corrected
executor-compatible importer passed thirteen, independently reproduced. Transport, Windows
staging and marker admission have separate focused validation; none of those
results represents native import or whole-area acceptance.

### Earlier attempts retained as history

The earlier startup run `39580724393`, attempt 2, reached 18.65 GiB free on D:
but was cancelled after its 18-minute budget while fetching the repository
([job 119286447935](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39580724393/job/119286447935)).
It did not reach installer or Editor startup. This supersedes the earlier disk
reserve blocker as a current host observation; no reserve bypass is required.
The scoped checkout fix at `de903a85e67540f451ea86743ea981fb7eb79f18` then passed
protected [CI 39625331286](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39625331286)
with compatible Unreal proof reuse. [Startup run 39625318792](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39625318792)
passed code-only checkout and native preflight with all six checkpoint package
hashes unchanged, and started PID 24984 at `2026-10-21T15:32:25.9789397Z`.
The same PID and native start time owned the verified loopback listener at
`15:36:32 UTC`. The first authenticated discovery then returned `REQUEST_TIMEOUT`
after 20 seconds, with zero native tool calls. The process and listener still
matched at `15:36:53 UTC`; current-world readback and import are not established.
That startup operation retained the active session and requested no asset save.

The [evidence index](startup-evidence.json) records the downloaded archive,
verified SHA-256 and five unchanged startup reports. The initial read-only
connection timeout is distinct from a native tool denial. Import still requires
a fresh owner/process/listener check and successful authenticated discovery.

The first [import run 39627916711](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39627916711)
passed CPU admission and staged the exact five-map manifest on the remote host.
Its next owner/listener check stopped with `SURFACE_IMPORT_OWNER_CHANGED`,
**before the client or any native tool call**. No BEFORE image, import request,
texture save or array save occurred. The owner then reported accidentally
closing the Editor; this is not diagnosed as a crash. The
[exact failure receipt and archive verification](import-39627916711-evidence.json)
are retained. A fresh authorized Editor session and new import run token are
required; the old run directory and checkpoint pins are preserved. Protected
[CI for the importer source](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39627930173)
completed successfully, which does not establish native material success.

The subsequent [read-only diagnostic 39629865244](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39629865244)
observed the exact prior session as `EDITOR_EXITED_NO_AUTORESTART` at
`15:44:07.6634944 UTC`. The task was Ready with result 0, the host had zero
live Editors, all four retained source files matched and all six saved
map/material/array checkpoints were unchanged. The
[closed-session evidence](closed-session-evidence.json) preserves the exact
sanitized reports and original installation/session hashes. Supervisor result
0 is not claimed as proof of a clean Unreal exit. This read-only diagnostic
makes no startup admission; the owner-authorized fresh start still uses the
normal protected CI, owner, disk and specifically pinned closed-session checks.

The fresh-start implementation adds only a fixed `CLOSED_DE903` case to the
existing closed-session validator, using those observed byte identities.
The launcher, original failed-session path and installer execution body remain
unchanged. The same-source one-shot restriction, a new release/state, retained
old evidence and checks immediately before handoff remain enforced. Production
validator tests passed 146 cases, independently reproduced; no native action
was performed by those tests. The exact source `007c5c0737bc36e0dc482b66f4b326e363104621`
then passed protected [CI 39630660478](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39630660478).
[Fresh startup 39630648547](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39630648547)
started canonical owner Editor PID 34848 at `16:07:32.1531735 UTC`; the same
process, native start time and loopback listener were verified at `16:10:20`
and `16:10:40 UTC`. The first authenticated discovery again returned
`REQUEST_TIMEOUT` with zero native tool calls. The Editor was retained and
no asset save was requested; a verified OS listener is not current-world proof.
The [exact restart evidence](restart-39630648547-evidence.json) preserves all
five reports, their byte hashes and the downloaded artifact identity.

The single resumed [import attempt 2](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39627916711/attempts/2)
authenticated successfully and captured the actual `L_SaCalobra_Lesson07`
viewport with PIE off and the camera restored. The subsequent explicit import
call failed during source compilation: `from __future__ imports must occur at
the beginning of the file (<string>, line 17)`. This is a Python compatibility
error, not a policy denial or a reason to retry the frozen observer. The same
owner process/listener was verified afterwards. The tool's generic completion
field remains null, and no `live-import.json` or AFTER image exists; no saved
asset success is inferred. [Exact evidence](import-39627916711-attempt2-evidence.json)
includes the original BEFORE JPEG and both unmodified sanitized receipts.

The source uses no type annotations, so removing its unnecessary future import
allows a preceding tool prologue without changing runtime import semantics.
A focused compile regression reproduces the reported failure mode. Separately,
[Epic's UE 5.8 import-task contract](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/UnrealEd/UAssetImportTask)
states that Interchange ignores `DestinationName`; fixed byte-identical input
copies named for the five required assets avoid that naming ambiguity while
preserving the original manifest and strict destination checks. A reviewed
corrected source uses a new run and all original checkpoint guards; no automatic
retry, gate bypass or Editor restart is introduced.

The corrected source `db494ab48efca53f82848bf52299dddc06af45c9` then reached a
second concrete executor compatibility issue in [run 39635077584](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39635077584):
file-mode execution did not define `__file__`. The source compiled and entered
`main`, then stopped at its first path-context expression, before input or
asset processing. The native BEFORE capture again succeeded and restored the
camera; the same owner session remained verified through `16:31:02 UTC`.
[Original receipts and image](import-39635077584-evidence.json) are retained;
there is no import-save receipt or AFTER image and no policy denial.

The file-context adaptation supplies one literal assignment derived from the
already admitted canonical run path, followed by the complete unchanged
`6c824070afe0ecc178dfa96d5f5fdef44d8b83168250a3917bc7c4c6da85d78e` importer body.
Staging and client validation share the exact rendering rule; both the body
hash and full staged-file hash are verified. The native tool still reviews the
complete source via `execute_python(file=..., mode=file)`, with no nested
execution. The original file-path, source, world, dirty-package and asset guards
remain in the submitted script. Only a new reviewed operation may use this
adaptation; the failed run is not repeated.
The adaptation passed eleven focused client tests and two tests of the actual
Stage writer, independently reproduced, alongside the thirteen unchanged-body
importer tests. PowerShell/YAML parsing and the independent source review passed.

Protected [CI 39635091670](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39635091670)
for `db494ab` did not pass: its native lane stopped at workspace-lock admission
with `LOCAL_BUSY` while the owner Editor was active. The native build/proof was
not reached and the Editor/logs were preserved. This is separate from lightweight
in-place material admission; it does not authorize closing the owner session or
weakening protected CI. Final exact-source delivery proof remains outstanding.

**Lesson07 remains open.** Final M3 owner visual audit and performance remain at
their existing project stages; `performance_pass: false`,
`performance_note: "DEFERRED_AFTER_M3"`.
