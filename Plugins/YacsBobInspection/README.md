# YACS BOB Inspection

This opt-in editor plugin is the narrow native boundary for Issue #384. It
depends on Epic's existing `ToolsetRegistry` to expose one YACS domain operation;
the `Landscape` dependency supplies native collision ownership that the current
Python `FHitResult` binding does not reliably expose. It contains no assets and
does not change the project plugin configuration.

The module currently registers no toolset. Native body wiring, registration,
Unreal compilation/reflection, restricted official MCP transport and the
checkpoint proof remain pending. A successful source build alone does not admit
this operation or complete Issue #384.

`InspectAcceptedCheckpoint` accepts only an empty JSON object, with bounded JSON
whitespace. Its native boundary rejects other operation names, fields, scalars,
nulls, trailing tokens and oversized input before accessing the editor world.
The trusted body is supplied internally; the caller cannot select a map, actor,
test, command, script, policy or evidence path.

The no-argument internal
`YacsBobLandscapeHitLibrary.inspect_accepted_checkpoint_identity` reads only the
fixed checkpoint Landscape after the shared stopped-editor/map/unique-Landscape
guard. Its `CHECKPOINT_IDENTITY` result carries the map and native actor identity;
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
