# Houdini Engine configuration boundary

Current integration note under the [SideFX workflow](README.md) and
[World Building Bible](../../WORLD_BUILDING_BIBLE.md). Scope: #365 / PR #474,
M3 configuration isolation. This is not a new launcher or a native proof.

## Why the shared configuration was restored

At `ea2d8d2b1739afa79a03c3343ccf4306713a3db1`, `Config/DefaultEngine.ini`
contained the historical 2,877-byte configuration plus a 197-byte Houdini block.
The retained #364 review adapter authenticates the original project inputs at
`b9fddea3f6023239da98bec7a5107ed1124cf52e`. Feeding it the new 3,074-byte file
correctly failed before a material/camera request could reach Unreal.

The shared file is restored to its original Git blob
`b54b30a29aba144cbd63c9448e0e705b678f6c7a`, SHA256
`d94045cbb0c78e0fde92d17f37651a11a94cc7c2b4bbd4a46382ac91ee5adb4b`.
Checkpoint pins, receipts, consumers and rejection behavior are unchanged.
Do not replace those hashes with the current project's hash to manufacture
compatibility. A future deliberate shared configuration migration needs its own
consumer-aware checkpoint migration; this repair is not a permanent ban on
changing project settings.

## Opt-in Houdini consumer profile

The three relocated properties are retained in
[`scripts/houdini/unreal-engine.args`](../../../scripts/houdini/unreal-engine.args)
as one native Unreal `-ini:Engine:` argument. It contains only the custom
Houdini location switch, the recorded `D:/yacs/tools/houdini-22.0.466/bin`
location and `MarshallingLandscapesUseFullResolution=True`. No map, renderer,
physics, port or network setting is overridden. The path is the recorded host
profile, not a portable installation discovery claim.

The `.args` file is **not loaded automatically**. For an explicitly approved
new, separate Houdini consumer session, append it to the existing trusted
launcher's arguments, after its normal source/version/host-ownership checks.
For PowerShell, with the executable, candidate project and candidate map already
resolved by that launch procedure:

```powershell
$HoudiniConfig = (Get-Content -LiteralPath "$Repo/scripts/houdini/unreal-engine.args" -Raw).Trim()
& $UnrealEditor $CandidateProject $CandidateMap $HoudiniConfig
```

This example demonstrates argument forwarding only. It is not permission to
launch beside an occupied shared host or to replace the trusted launcher's
other arguments and gates. Do not use this profile for the retained #364
checkpoint launcher, Live Host or accepted-world review. Do not append it to
shared `DefaultEngine.ini`, copy it into `Saved/Config`, or rewrite an existing
session to make the new profile active. It is unnecessary for standalone
Houdini HIP authoring.

Before the next scoped Unreal consumer proof, inspect the installed plugin's
settings/API, verify the HAPI library at the selected location and matching
built-against/running-against versions, and record the effective settings.
SideFX's per-user Custom Location preference can override project settings;
record and resolve any such override rather than assuming the argument won.
Then prove actual import, saved/fresh reload and source-relative fidelity.
Native application of this relocated profile is **NOT RUN** by this repair.

## Validation and rollback

`python scripts/houdini/test_unreal_configuration.py` verifies the original
checkpoint identity, absence of a host override from shared defaults, the exact
three-property single-argument profile, and byte-identical reconstruction of
the former 3,074-byte configuration. Existing `test_prepare_level_editor_review`
and `test_level_editor_material_client` remain unchanged and must pass in the
normal discovered hosted suite. Documentation guards and full protected CI
are separate checks, not implied by these four tests.

Omitting the optional argument leaves the baseline configuration unchanged.
There is no new workflow, dependency, background task, terrain mutation or
native acceptance claim. The reusable configuration-isolation principle already
fits the platform's existing exact-source policy; no separate Gumball mechanism
is introduced for these YACS-specific checkpoint pins.

## Official references checked

- [Epic: configuration files and specific command-line property overrides](https://dev.epicgames.com/documentation/unreal-engine/configuration-files-in-unreal-engine?lang=en-US)
- [SideFX: Houdini Engine plugin settings and library/version checks](https://www.sidefx.com/docs/houdini/unreal/settings.html)
- [SideFX: per-user Custom Location precedence](https://www.sidefx.com/docs/houdini/unreal/editorpref.html)

These document the supported mechanisms, not execution of the YACS profile.
