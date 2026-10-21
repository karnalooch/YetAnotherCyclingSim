# Lesson07 acquired CC0 surfaces and bounded native repair

**Type:** implementation and source evidence, supporting the
[Lesson07 audit](../../tooling/sidefx/LESSON07_MATERIAL_SETUP.md).
**Issue/stage:** #365 / M3, existing Draft PR #474.
**State:** complete source acquisition and offline preparation verified;
native import and whole-area technical/visual verification pending.

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
roundtrip/hash review. The importer passed ten CPU tests. Transport, Windows
staging and marker admission have separate focused validation; none of those
results represents native import or whole-area acceptance.

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

**Lesson07 remains open.** Final M3 owner visual audit and performance remain at
their existing project stages; `performance_pass: false`,
`performance_note: "DEFERRED_AFTER_M3"`.
