# Persistent YACS workspace

Owner-approved supporting workflow, 2026-10-04. The World Building Bible remains
world authority; Julka remains the asset identity/restore catalog. This is not
road engineering, runtime collision or performance admission.

## One active project

The local layout is `D:\yacs\project`, `data`, `cache`, `checkpoints`, and `work`.
`workspace.json` lives beside the repository and contains machine paths. It is
not committed. `scripts/workspace.py` resolves it relative to the repository or
the explicit `YACS_WORKSPACE_CONFIG` environment variable. Production scripts
belong in the repository, not a Codex conversation's scratch directory.

Unreal and Computer Use operate on this project. CI retains isolated checkouts;
CI cleanup must never target the live project or external data/cache roots.
The engine installation remains external. Python uses the workspace `.venv`.

## Accepted scene checkpoint

`scripts/ue/accepted_scene_checkpoint.py` consumes hash-pinned accepted road
sections and fixed CUT payloads. It builds one pavement mesh with the accepted
60-degree split-normal correction, plus 186 support meshes. It preserves road
coordinates and creates no new CUT targets. Historical support functions are
loaded only from their two explicitly hash-verified consumer snapshots.

The map stores ordinary DynamicMesh actors. UE 5.8's `UDynamicMesh::Serialize`
serializes mesh data; the component owns the mesh through an instanced property.
On load, `FDynamicMesh3::Serialize` rebuilds vertex reference counts from faces.
The three Nudo arch supports have 10,905 unused source vertices that disappear
from that inventory. The verification therefore proves the precise unused count
and compares every oriented triangle against the hash-pinned source consumer:
24,448 triangles, maximum coordinate difference 0.0 cm. It does not waive a
geometry mismatch or substitute triangle counts for coordinate verification.
Materials are saved MaterialInstanceConstants. CUT actors/components and their
R32F textures are persistent. Float32 texture source and `TC_SingleFloat`
preserve height precision on reload. Review overlay assets are saved separately
and remain diagnostic masks, not production landscape materials.

The original source baseline is retained. The accepted scene uses
`/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004`. The original live session
crashed before its checkpoint completed (D3D12 out of video memory); recovery
uses the frozen inputs and prior numeric proof rather than claiming a successful
export from that lost session. Recovery avoids duplicate full pavement actors.

Persistence changes are explicit opt-in arguments to the native CUT consumer;
its existing callers still default to transient output. The native API never
saves a package itself. A caller verifies the result and saves deliberately.

## Verification and storage

Treat these as distinct states: live preview; locally saved; reopen verified;
remotely backed up. A fresh editor must read the saved actor/material inventory
and compare ground traces before the launcher admits a checkpoint. No replay of
the road builder is part of opening an accepted map.

Git tracks scripts/configuration/recipes and LFS tracks `.umap`/`.uasset` bytes.
Julka and hash manifests identify external sources and prepared data. DDC/Zen is
reusable engine cache, not authoritative data or a substitute for backup.
Local checkpoint receipts record actual remote-backup status independently.
Original locations are retained until migration verification; do not blanket
clean runner assets, shared LFS objects, or cache directories.

Run `python scripts/workspace.py doctor` for the local launch contract and
`python scripts/workspace.py open` to open the configured saved map. These
commands require the workspace configuration and a successful reopening proof.
The launcher rejects a map whose bytes changed since that proof and refuses a
second editor process. `Restore-YacsSaCalobraWorldData.ps1` resolves its default
destination from the workspace; CI must supply an explicit destination.

The local launch shortcut is `D:\yacs\Open-YACS.cmd`. Preserve `workspace.json`
and the verified checkpoint receipts during host recovery. Native modules must
be built for the installed engine; their successful build receipt is local
evidence, not a claim that a future source revision has already been built.

## Evidence and known engine behavior

Validated against installed UE 5.8.2 source: `UDynamicMesh.cpp`,
`DynamicMeshComponent.h`, `LandscapeTexturePatch.h`, `TextureDefines.h`,
`FileHelpers.cpp`, and `MaterialEditingLibrary.cpp`. The material vector setter
always returns false in this engine implementation even after setting the
value; checkpoint code checks the value by readback instead.

The public [Embark landscape workflow](https://www.sidefx.com/learn/talks/embark-landscape-creation/)
supports the producer/prepared-data/Unreal-consumer boundary. The directory
layout and checkpoint implementation are YACS decisions, not claims about
Embark's unpublished storage infrastructure.
