# Blender headless producer

**Status:** active supporting tooling for Issue #391.  
**Pinned toolchain:** Blender 4.5.9 portable Windows x64.  
**Authority:** DCC producer only; this document does not replace the World Building Bible, BOB, World Authority, route/physics contracts, Unreal consumers or proof gates.

## Local layout

The admitted executable is outside Git at:

`D:\yacs\tools\blender-4.5.9-windows-x64\blender.exe`

The repository pins that relative location and exact version in
`scripts/blender/toolchain.json`. Do not copy the Blender distribution into
`D:\yacs\project`, Git LFS or a CI checkout. A version upgrade is a
deliberate toolchain change: update the pin, re-run hosted contract tests and
produce a fresh local headless smoke proof.

The launcher reads `YACS_WORKSPACE_CONFIG` when supplied by the runner. In the
canonical authoring checkout it otherwise expects `D:\yacs\workspace.json`
beside `project`. The executable and any explicit `.blend` input must remain
below that workspace root.

## One-command proof

From `D:\yacs\project`:

```powershell
python scripts/blender/run_headless.py smoke
```

The smoke lane verifies the exact 4.5.9 executable, starts Blender without its UI,
creates a deterministic three-vertex mesh through `bpy`, and writes:

- `D:\yacs\work\blender\headless-smoke\host-receipt.json`
- `D:\yacs\work\blender\headless-smoke\host-receipt.log`
- `D:\yacs\work\blender\headless-smoke\blender-report.json`

The host receipt records the Git revision when available, exact Blender version,
script SHA-256, optional input `.blend` SHA-256, process exit code and duration.
The Blender report proves that `bpy.app.background` is true and that the
deterministic mesh operation ran inside the pinned Blender process.

A green hosted Python test validates the launcher contract but is **not** proof
that the local Blender binary exists or ran. Conversely, a Blender smoke PASS is
not Unreal import proof, visual acceptance, physics admission or performance
admission.

## Generic jobs

Jobs are repository-owned Python files. Example:

```powershell
python scripts/blender/run_headless.py run `
  --script scripts/blender/example_job.py `
  --receipt work/blender/example/host-receipt.json `
  -- --output D:\yacs\work\blender\example\result.json
```

An explicit `.blend` input is workspace-relative unless an absolute path below
the workspace root is supplied:

```powershell
python scripts/blender/run_headless.py run `
  --script scripts/blender/example_job.py `
  --blend data/source/example.blend `
  --receipt work/blender/example/host-receipt.json `
  -- --output D:\yacs\work\blender\example\result.json
```

Arguments after `--` belong only to the repository job script.

## Execution boundary

Every invocation uses the Blender 4.5 command-line contract:

- `--background` for UI-less execution;
- `--factory-startup` to avoid relying on the user's startup scene;
- `--disable-autoexec` so automatic Python embedded in a loaded `.blend` is not trusted;
- `--python-exit-code 20` so an unhandled command-line Python exception fails the process;
- `--python <repo-owned-script>`;
- `--` before job-specific arguments.

Do not enable automatic scripts from a `.blend` merely to make a job pass.
If a future trusted pipeline genuinely needs that capability, treat it as a
separate security/architecture decision.

## Producer -> prepared data -> Unreal

Blender may generate or transform candidate meshes, UVs, collision helpers,
LODs, baking inputs or other DCC outputs. The durable pattern is:

```text
verified source / YACS recipe
        -> pinned Blender headless job
        -> prepared data + receipt
        -> explicit Unreal/YACS consumer
        -> technical proof
        -> human visual acceptance where required
```

Blender does not become road, terrain, earthworks, World Authority or physics
truth. It may not silently overwrite accepted Unreal content, mutate frozen
Sa Calobra geometry, or bypass provenance, exact-SHA, CI, visual or performance
gates. Keep intermediate output under the workspace `work` tree unless a
separate asset/provenance contract promotes it elsewhere.

## Upstream references

The command-line flags above are verified against the Blender 4.5 LTS manual:

- https://docs.blender.org/manual/en/4.5/advanced/command_line/index.html
- https://docs.blender.org/manual/en/4.5/advanced/command_line/arguments.html
