# Persistent YACS workspace

Owner-approved supporting workflow, 2026-10-04. The World Building Bible remains
world authority; Julka remains the asset identity/restore catalog. This is not
road engineering, runtime collision or performance admission.

The [script entry-point index](../../scripts/README.md) lists maintained commands,
their effects and naming conventions.

## One active project

The local layout is `D:\yacs\project`, `runner`, `runner-monitor`, `engine`,
`data`, `cache`, `checkpoints`, `work`, `tools`, and `archive`. Cyclist mocap source data
lives at `data/mocap/cyclist-spike`; it remains a research dataset, not imported
or admitted cycling animation.
`workspace.json` lives beside the repository and contains machine paths. It is
not committed. `scripts/manage_local_workspace.py` resolves it relative to the repository or
the explicit `YACS_WORKSPACE_CONFIG` environment variable. Production scripts
belong in the repository, not a Codex conversation's scratch directory.

Unreal and Computer Use operate on this project. CI retains isolated checkouts;
CI cleanup must never target the live project or external data/cache roots.
UE 5.8.2 lives at `engine/UE_5.8`. System Git, Visual Studio and base Python remain
installed system tools. Python dependencies use the project's `.venv`.

Portable DCC binaries live outside the repository under `D:\yacs\tools`. The
currently admitted Blender toolchain is `blender-4.5.9-windows-x64`; repository
code pins and invokes it through `scripts/blender/run_headless.py`, never PATH or
a system install. See [Blender headless producer](BLENDER_HEADLESS.md).

Portable PowerShell is also workspace-owned rather than installed system-wide.
The pinned runner shell is `D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe`.
`scripts/runner/Install-YacsPortablePowerShell.ps1` downloads the official
Microsoft ZIP, verifies its exact SHA-256, validates version 7.6.6 and publishes
it atomically. `Start-YacsRunner.ps1` prepends that directory to the runner
process PATH, while `portable-powershell.yml` can bootstrap the tool even when
only Windows PowerShell 5.1 is initially available. An already-running runner
keeps its inherited process environment until restarted; a workflow that
bootstraps the tool may use `GITHUB_PATH` for later steps in that same job.

The runner is started by `scripts/runner/Start-YacsRunner.ps1` in the logged-in
desktop session, with one listener only. It reads `workspace.json`, sets scoped
temporary/cache paths, and preserves the registered GitHub identity. The monitor
uses its existing per-user scheduled task with the new installed path. Do not
silently switch the GPU runner to Windows Session 0.

The owner requested disk-growth protection. `Invoke-YacsJobStarted.ps1` is the
runner's pre-job hook and requires **50 GiB free** before workflow steps start.
Unreal checks the same reserve immediately before compilation. These checks
stop admission when space is low; they are not an operating-system disk quota
and do not promise a fixed ceiling during an already running job. The monitor
records remaining space. The existing persistent warm checkout is reused.
`Clear-YacsRunnerWorkspace.ps1` previews eligible old `Intermediate` and local
`DerivedDataCache` folders; apply requires the exact reviewed count/byte total,
an idle worker and unchanged inventory. Source assets, shared caches and active
build cache remain protected. Never lower the reserve simply to turn CI green.
The hook uses GitHub's supported
[pre-job script mechanism](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts).

The engine resolver reads the configured engine for canonical/runner work and
uses the canonical engine root before legacy discovery on other hosts. Older
Epic/Windows/Codex registrations may use zero-payload directory junctions into
the canonical tree. These do not contain independent copies. Update privileged
registrations before removing their compatibility aliases.

UE 5.8's Live Coding mutex is keyed by the engine executable, so another open
project can block an isolated CI build. `Invoke-YacsProof.ps1` verifies that the
target checkout is not open, then uses `-NoHotReloadFromIDE` for its isolated
build. It never compiles the live authoring checkout through that path.

Everyday iteration updates the owner's existing editor session: supported C++
changes use Live Coding; mask/material/data changes use their explicit editor
consumer refresh. Verify the displayed result. CI validates separately and does
not copy its DLLs or map files over a running authoring session. If a change
requires a restart, announce it and preserve unsaved work first.

## Accepted scene checkpoint

`scripts/ue/create_accepted_scene_checkpoint.py` consumes hash-pinned accepted road
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

Run `python scripts/manage_local_workspace.py doctor` for the local launch contract and
`python scripts/manage_local_workspace.py open` to open the configured saved map. These
commands require the workspace configuration and a successful reopening proof.
The launcher rejects a map whose bytes changed since that proof and refuses a
second editor process. `Restore-YacsSaCalobraWorldData.ps1` resolves its default
destination from the workspace; CI must supply an explicit destination.

The local launch shortcut is `D:\yacs\Open-YACS.cmd`. Preserve `workspace.json`
and the verified checkpoint receipts during host recovery. Native modules must
be built for the installed engine; their successful build receipt is local
evidence, not a claim that a future source revision has already been built.

## Restore procedure

For the 2026-10-04 snapshot, retain access to both unpublished GitHub releases:
`checkpoint-sa-calobra-2026-10-04` and
`data-cnig-sa-calobra-working-v1-2026-10-03`. Do not publish them: original source
responses retain redistribution restrictions. The newer `restore-manifest.json`
identifies 820 source/prepared files and references previously backed-up CNIG
bytes by exact digest; nine session logs remain local. Its initial status field
describes archive preparation; a separate remote receipt confirms upload hashes.

1. Restore the recorded Git revision and run `git lfs pull` for map/assets.
2. Download assets from both draft releases with authenticated `gh release download`
   into one empty recovery bundle directory. Preserve the manifest and notices.
3. Run `python scripts/assets/restore_workspace_data.py --manifest <bundle>/restore-manifest.json
   --bundle <bundle> --destination <workspace>/data/world-data/sa-calobra-working-v1`.
   This reports missing files without writing. Add `--apply` to restore them.
   The tool verifies SHA-256/size, rejects escaping paths and never overwrites
   existing files; corrupt bytes fail before publication.
4. Restore the local workspace configuration and checkpoint receipts, build the
   project for the installed UE version, then run fresh-editor verification.
   Open the verified map through the workspace launcher.

Zen/DDC may be restored from the retained local cache or rebuilt. They are not
required authoritative inputs. The external-data receipt covers the files in
this working snapshot; it does not establish that every future Julka source is
available or that Issue #345 is complete.

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
