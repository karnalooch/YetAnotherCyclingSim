# Lesson07 ready-made limestone material selection

**Issue:** #365, M3; existing Draft PR #474.

**Checked:** 2026-10-21.

**Authority:** [current Lesson07 audit](../../tooling/sidefx/LESSON07_MATERIAL_SETUP.md).

**State:** source selection and licensed comparison samples; no new native import, purchase or whole-material acceptance.

The owner requested ready-made licensed assets and complete materials, explicitly
including **dark-grey limestone**. This extends source acquisition and appearance
selection for the existing repair. It does not change the Houdini terrain,
geography, road alignment or accepted classification. The saved Macro 0.05
partial improvement remains the last verified material change.

## Recommended complete packages

These are publisher claims checked against the linked primary product pages,
not YACS compatibility or visual acceptance. Each Fab listing's public reader
showed an unpopulated individual license field; account entitlement and the
actual selected license still require acquisition evidence. No paid purchase
has been made. Current checkout prices for paid products were not exposed.

| Priority | Product | Verified supplied content | Decision for this repair |
| --- | --- | --- | --- |
| 1 | [Mediterranean Karst Biome Vol.01, Terravision3D](https://www.fab.com/listings/a60b0ff7-bd20-405b-928f-7a4d650d0b93) | Six scanned limestone meshes and seven landscape materials from Mediterranean Türkiye; 4K PBR maps; Unreal master materials with tint/roughness controls and near/far tiling blend; Nanite meshes. Listing allows AI usage. | Best documented regional/geological package. Prefer its coherent surface families. Dark-grey albedo is a selection requirement, not a proven feature of every supplied material. |
| 2 | [Quixel Quarry Cliff](https://www.fab.com/listings/c88f7f3b-bb08-4e38-8ee5-67e120e99ae1) and [Layered Rock Cliff](https://www.fab.com/listings/31cdea72-2995-4d10-85cc-06e52122017e) | Both currently display Free and are tagged limestone. First is an open cliff mesh, 3.5 x 12.9 x 13.22 m; second is a separate 2 x 2 m PBR surface. | Strong zero-purchase candidates if legitimately acquired. They are not a complete prewired landscape package. Both have NoAI declarations; do not submit their protected contents to generative processing. |
| 3 | [Realistic Rock Set: Limestone Rock Strata, Ancraite](https://www.fab.com/listings/46308132-bcb0-40c6-9527-1c6beb00d311?lang=en) | Ten Unreal rocks, four LODs, collision, PBR material layers, edge/dirt variation and vertex-paint features. Listing allows AI usage. | Layered rock-cut alternative. Its separate free sample is described for preview, so it is not admitted as a free production substitute. |
| 4 | [APEX Nature Dolomites: Free Mountain/Cliff Tileable Surface](https://www.fab.com/listings/a0b22e42-5c9a-4506-8ad7-bc14d5175578?lang=en) | Currently Free: one scanned 8K tileable surface, roughly 50 square metres of capture coverage, Unreal master material, detail textures and overview map. | Useful complete-material trial, particularly for Passo Giau. Capture area does not specify the two UV dimensions. NoAI declaration. |
| 5 | [Shore lime rocks volume one, lucidstormcg](https://www.fab.com/listings/f33796c5-af51-4e7e-ab63-ef14a52c965d?lang=en) | Eight scanned lime rocks, 4K PBR, custom collision, four LODs and adjustable material. Publisher explicitly describes dark-grey through sandy colours and states a UE 5.8.3 test. | Strongest explicit dark-grey colour claim, but porous coastal boulders are not a general mountain-wall replacement. NoAI declaration; publisher compatibility is not our native test. |
| 6 | [Poly Haven Rock Face 01](https://polyhaven.com/a/rock_face_01) | CC0 mesh with up to 8K maps, both normal conventions, FBX/glTF/USD/Blend. | Unrestricted geometry fallback; publisher does not identify it as limestone and does not supply a verified ready Unreal landscape shader. |

None of these product descriptions establishes world-aligned or triplanar
projection. Near/far blending alone is not a solution to the retained vertical
cliff streaks. Do not cover a mapping or geometry defect by making the albedo
darker.

## License decision

[Fab's official Standard summary](https://www.fab.com/eula) permits commercial
projects and modifications, including sharing with project collaborators through
a private repository; standalone redistribution is prohibited. The summary is
explicitly nonbinding and is not an asset-specific entitlement receipt.
[Official licensing documentation](https://dev.epicgames.com/documentation/en-us/fab/licenses-and-pricing-in-fab)
also distinguishes current Standard, CC-BY and legacy Marketplace offerings.
Record the selected license/tier, listing UUID, acquisition date, receipt and
exact package hashes before import. This repository is public: restricted Fab
source packages and private owned-pack inventories must not be committed or
published in public CI artifacts.

The current Fab NoAI help does not establish a general exemption for AI/MCP
content processing. Ordinary engine integration and submitting asset content as
model input are different operations; no blanket clearance is claimed here.
No NoAI asset payload was downloaded or supplied to image generation.

[Poly Haven assets](https://polyhaven.com/license),
[ambientCG assets](https://docs.ambientcg.com/license/) and the
[cgbookcase texture library](https://www.cgbookcase.com/textures) use CC0.
Poly Haven's promotional website renders are separately protected; the four
retained images below are actual downloadable Diffuse source files, not sphere
renders. [Acquisition metadata](acquisition.json) retains exact provider URLs,
authors, dimensions, provider MD5/bytes and local SHA-256 values.

## Raw samples inspected and rejected as the main limestone

| Actual CC0 source sample | Source width | Visual observation of the unmodified 1K Diffuse | Selection |
| --- | --- | --- | --- |
| [Rock 01](rock_01-diffuse-1k.jpg) | 1.5 m | Warm brown-grey, relatively quiet surface. | Reject as the main dark neutral limestone. |
| [Rock 3](rock_3-diffuse-1k.jpg) | 1.5 m | Coarse eroded pits with warm brown areas. | Reject as the main dark neutral limestone. |
| [Gray Rocks](gray_rocks-diffuse-1k.jpg) | 1.8 m | Angular coarse rubble with conspicuous grain. | Possible generic rubble reference only; not authenticated limestone scree. |
| [Seaside Rock](seaside_rock-diffuse-1k.jpg) | 2 m | Dark, but substantially brown/olive rather than a convincing neutral grey. | Reject as the main requested limestone; no full-resolution acquisition. |

These visual descriptions are reviewer observations. No provider authenticates
the four samples' geology as limestone. `dark_rock` is also excluded from the
limestone recommendation because its provider tag identifies metamorphic rock.

Further CC0 candidates remain **not acquired**:
[cgbookcase Grey Rock 03](https://www.cgbookcase.com/textures/grey-rock-03)
advertises a complete DirectX-normal PBR set, while
[ambientCG Rock063](https://ambientcg.com/view?id=Rock063) is a scanned layered
grey/mossy surface. Their physical scale and limestone geology are unverified.
The exact public cgbookcase download module and official Rock063 2K PNG download
returned **HTTP 403** during approved fetches. No ZIP or complete map set was
obtained; no alternate identity or access-control workaround was attempted.
A third official comparison set,
[TextureCan Rock0005](https://www.texturecan.com/details/240/), is a generic
procedural grey tileable rock under [CC0](https://www.texturecan.com/terms/).
Its exact 2K ZIP and preview also returned HTTP 403 with zero retained bytes;
see the [unaltered download receipt](texturecan-download-receipt.json).
Its geology, physical scale, actual map contents and visual suitability remain
unverified. No full material was acquired from any of these three providers.

ShareTextures was excluded from the pure-CC0 acquisition route because its
[current license](https://www.sharetextures.com/p/license) describes custom
restrictions, including redistribution and automated downloads. A CC0-style
badge alone is not sufficient acquisition evidence.

## Integration contract

1. Select a source family containing BaseColor, NormalDX, Roughness, AO and
   Height, or explicitly document a missing map. Preserve original files and
   record hashes, bit depths and physical dimensions. Do not combine normals
   from unrelated rocks.
2. Preserve the five existing array slices: Grass, accepted Grass2, Sand,
   Cliffs and Scree. The required light-grey and dark-grey limestone appearances
   belong in a controlled Cliffs material comparison; they do not authorize new
   terrain classification or replacing accepted Grass2.
3. Use colour maps as sRGB; normals and scalar masks are linear. Pegasus Masks
   use R=AO, G=Roughness, B=Height. A vendor ORM blue metallic channel cannot be
   substituted for height. Keep displacement disabled in the existing runtime
   until separately verified.
4. Do not reapply the old global hue +25-degree grading to neutral-grey source
   maps. Evaluate native albedo, roughness, physical repeat and projection in
   the same lighting/camera before accepting a replacement. Keep the saved
   normal-flatten workaround until its separate sampler/derivative issue is
   resolved.
5. Reuse the dedicated `vault_asset` tool to inspect already-local ready Unreal
   packs. The new mode admits only three fixed list filters: `limestone`,
   `cliff`, `rock`. It cannot install, download, run Python or import textures.
   Each native call retains the existing fresh owner-session identity checks.
   Public output contains only hashes, statuses and observations of six fixed
   public product names; raw inventory stays on the host. A name observation
   does not prove ownership, license, completeness or installability.

The frozen F49-denied observer is unchanged. Local PNG import and Texture2DArray
source rebuilding remain unverified capabilities; source import has not been
attempted or denied. A successful catalogue inspection is not material repair.
Native assignment, saved/reopened evidence, whole-area visual acceptance and
protected CI remain separate outstanding gates.

## Preparation verification

The client/observer suite passed 109 tests, including seven Vault-specific tests.
Independent review confirmed the frozen observer, actual retained schema pin,
all 256 workflow marker combinations and nonowner rejection. Existing PowerShell
7.6.6 parsed the production AST and passed the Vault parameter checks, six
mixed-mode rejections and eleven typed receipt cases. Documentation links,
i18n, structure and freshness guards passed. These are preparation results;
remote catalogue evidence is recorded separately after execution.

## First remote catalogue attempt and current host state

The first exact-source attempt at `6bfa739c03eb55d9bcd3c4374d3fedc62a246c79`
([run 39577528208](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39577528208))
passed 115 CPU tests and the Windows preparation checks. At
`2026-10-21T09:33:16.8578333Z` it stopped before the native client with
`VAULT_INSPECTION_REQUIRES_EXISTING_EDITOR`: the process count was not exactly
one. This error alone did not distinguish zero from multiple Editors. There
were **zero native calls, installs, imports or Editor starts/stops**.
The [unaltered probe receipt](first-vault-probe.json) is retained; its SHA-256 is
`cf7ff8fd4758aeafefa2b9b5e2829fc09f820f21411867e5fd062bcc15865b80`.
Artifact `12334394767` has ZIP SHA-256
`0630c49e02cdeea40dea55183b6c3e73b27cc5f59f331b275ad5b3f40354484e`.

Subsequent independent OS observations resolved the ambiguity:
[CI job 119148097228](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39577539895/job/119148097228)
reported `IDLE`, with zero remote-CI, local/unknown and stale process records at
`09:35:06.3313504 UTC`;
[diagnostic job 119149255036](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39510504128/job/119149255036)
reported `editors=[]`, no discovery file and no diagnostic failures at
`09:37:36.2439524 UTC`. The diagnostic issued no HTTP or Editor commands.

Protected CyclingSim CI for the exact `6bfa739c` source completed **SUCCESS** at
`09:37:11 UTC`. Its Unreal lane reused compatible proof; new build, Automation,
capture and interactive handoff steps were skipped. This source-CI result does
not establish an active Editor, material import or visual acceptance.

The owner's standing instruction permits creating a session when absent. The
old successful `602f8d0` installation is deliberately one-shot and is not being
restarted or reset. A fresh bounded read of its closed session/task and six
saved checkpoint packages precedes any newly reviewed one-shot launch. Preserve
the Macro 0.05 save, prior release/state and all owner/CI/checkpoint controls.
