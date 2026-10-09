# YACS BOB Inspection

This opt-in editor plugin is the narrow native boundary for Issue #384. It
depends on Epic's existing `ToolsetRegistry` to expose one YACS domain operation;
the `Landscape` dependency supplies native collision ownership that the current
Python `FHitResult` binding does not reliably expose. It contains no assets and
does not change the project plugin configuration.

The module currently registers no toolset. Native body wiring, registration,
Python reflection, restricted official MCP transport and the checkpoint proof
remain pending. Run `37996979223` compiled all plugin actions and its DLL on UE
5.8.2 / CL 56702186 at `f557bfd0a760b795bb3294ec047cdfc4c837424d`.
A successful source build alone does not admit this operation or complete
Issue #384.

`InspectAcceptedCheckpoint` accepts only an empty JSON object, with bounded JSON
whitespace. Its native boundary rejects other operation names, fields, scalars,
nulls, trailing tokens and oversized input before accessing the editor world.
The trusted body is supplied internally; the caller cannot select a map, actor,
test, command, script, policy or evidence path.

The no-argument internal
`YacsBobLandscapeHitLibrary.inspect_accepted_checkpoint_identity` reads only the
fixed checkpoint Landscape after the shared stopped-editor/map/unique-Landscape
guard and exact UE 5.8.2 / CL 56702186 check. Its `CHECKPOINT_IDENTITY` result
carries the map and native actor identity;
it supplies no collision component or terrain measurement.

`YacsBobLandscapeHitLibrary.inspect_accepted_landscape_hit` is an internal
reflected helper, without `AICallable` metadata or MCP registration. It consumes
an existing native hit and verifies the stopped editor world is the fixed
accepted material map, containing exactly one `ALandscape`. A usable hit must
name that actor and an exact `ULandscapeHeightfieldCollisionComponent` owned by
it. `OWNED_LANDSCAPE_HIT` carries the native identity and impact point in Unreal
centimetres. `MISSING_HIT` preserves an explicit missing sample with no height or
object references. `REJECTED` carries no usable measurement. The Python producer
also checks these facts against its selected Landscape and collision inventory.

The installed public `ToolsetRegistry/Toolset.h` declarations were collected on
UE 5.8.2 / CL 56702186 in source-only run `37992908998`, with SHA-256
`7bcb28ab8ad3d7b415f7dfd031eb975de177361b10360edd33c3232610c4e0d0`.
The exported native registration and root `tools[]` schema consumer were then
verified in source-only run `37993672276`. `FToolset::ExecuteTool` constructs the
qualified name with `.` and forwards the bare operation to the strict boundary.
These declarations prove an available extension contract; they do not prove
plugin compilation, registration or runtime execution. No generic Unreal
gateway, server process or world-authoring API is introduced by this fragment.

`YacsBobInspection.InputBoundary` tests actual local native registry registration,
the single-operation schema and rejection of caller-selected/malformed input. It
uses the installed registry's slash-wrapped regular expressions
`/^YacsBobInspection$/` and
`/^YacsBobInspection[.]InspectAcceptedCheckpoint$/` and checks actual enabled
schema visibility before testing denials. It owns its registry and unreachable
callback; it does not touch the editor-global
registry or activate MCP. In the isolated empty `HostProject`, even a valid empty
request must reject the unapproved map. This boundary proof is separate from the
existing project `CyclingPhysics.RoadPhysics.ProfileInterpolation` test and the
real checkpoint BOB inspection required by Issue #384. The first native run
completed this test with three errors from the intentionally denied, absent
`actor`, `scene` and `AutomationTestToolset` toolsets; diagnostic run
`37998743610` retained the exact log and report. No assertion failure was
reported. The test now expects each complete observed log message literally,
exactly once, and checks its actual occurrence count; an unused expectation
fails the test. The installed Core declarations, literal matching and positive
count validation were verified in source-only run `38000430250`. Native test
success remains pending a fresh matching host receipt.
