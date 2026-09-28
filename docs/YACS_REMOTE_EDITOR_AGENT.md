# YACS Remote Editor Agent

**Tracking:** #85  
**Status:** controlled spike  
**Runner:** `yacs-home-ue58` / label `yacs-ue58`  
**Transport:** GitHub Actions, outbound-only  
**Initial command:** `smoke-cube`

## Goal

Allow an approved chat/GitHub operator flow to request a small, named Unreal
Editor action on the trusted home runner without exposing Unreal MCP or a shell
to the public network.

The initial proof is deliberately tiny:

```text
Chat / operator
    |
    v
Issue #85 exact command
    |
    v
GitHub Actions
    |
    v
self-hosted yacs-ue58
    |
    v
repository-owned allowlist wrapper
    |
    v
UnrealEditor-Cmd.exe
    |
    v
transient cube -> destroy -> proof artifact
```

This is a transport/orchestration layer only. It does not change route authority,
physics, Stage 3 geometry, or the UE-MCP generated-content guard model.

## Command boundary

The first accepted comment is exactly:

```text
/yacs-editor smoke-cube
```

The comment text is never executed. GitHub Actions recognizes that exact literal
and maps it to:

```text
Invoke-YacsRemoteEditorCommand.ps1 -Command smoke-cube
```

The PowerShell entry point has its own `ValidateSet('smoke-cube')`, and that
command maps to the fixed repository-owned `remote_editor_smoke.py` script.

## Security invariants

- only Issue **#85** is accepted for comment-driven execution;
- only the repository owner may issue the command;
- no fork pull-request trigger is used;
- `pull_request_target` is forbidden for this path;
- workflow permission is `contents: read`;
- credentials are not persisted by checkout;
- the exact trusted event SHA is verified before execution;
- the C++/Automation lane runs before the Editor command;
- required LFS payloads are materialized and checked before Editor startup;
- no issue text becomes shell, Python, asset path, map path, or console input;
- the smoke actor is transient and is destroyed before the script exits;
- the script does not save a map or create a persistent asset;
- the worktree must remain clean;
- proof artifacts have short retention;
- cleanup runs after success or failure;
- Unreal MCP remains localhost-only and is not exposed by this bridge.

## Canary

Before `issue_comment` can execute from the default-branch workflow definition,
the dedicated spike branch is allowed one trusted push canary:

`feat/85-remote-editor-command-bridge`

The push path is owner-only and runs the same fixed `smoke-cube` command. It is
not a generic branch executor.

## Proof contract

A green canary must prove all of the following:

1. trusted exact-SHA checkout;
2. code-only checkout contract before the build;
3. real UE 5.8 Editor build and scoped Automation;
4. trusted LFS materialization and `git lfs fsck`;
5. UE 5.8.x preflight;
6. `UnrealEditor-Cmd.exe` starts YACS;
7. PythonScriptPlugin runs the fixed script;
8. a transient `StaticMeshActor` using `/Engine/BasicShapes/Cube.Cube` is spawned;
9. the actor is destroyed;
10. no map is saved and no persistent asset is created;
11. JSON/log evidence is uploaded;
12. the worktree is clean after execution and cleanup.

A screenshot is not required for this first headless proof. Interactive/GPU
capture becomes a separate acceptance gate before remote visual authoring is
claimed to work.

## Next gated step

Only after `smoke-cube` is green may #85 add another named command. The next
safe candidate is a read-only visual command such as `capture-current-map`.
Persistent Stage 3G authoring commands come later and must reuse the existing
generated-content sandbox and deterministic proof rules.

Arbitrary Python, arbitrary Unreal console commands, arbitrary asset/map paths,
and free-form world-edit instructions remain out of scope for this spike.
