# Sa Calobra appearance-only gap fill

This package fills the surface presentation without changing the original
observations, PCG exclusions, geometry or roads. It is not a land-cover survey.

- RGBA weights: low vegetation, forest floor, rock, artistic dry-channel overlay.
- Blend the first three with mineral residual `1 - R - G - B`; then apply A as
  a separate scree overlay. Do not add A to the same unnormalized weight sum.
- All-zero RGB means mineral fallback, not transparency or a Landscape hole.
- Availability retains the original missing samples. Inference-kind distinguishes
  0 observed, 1 neighbor fill, 2 neutral fallback, 3 protected road/building.
- Road/building barriers stop propagation. BOB rectangles and water holdbacks
  remain unchanged for placement but no longer cut holes in visual domains.
- Eight four-connected propagation steps bound donor paths to 4 m. One 25%
  neighbor smoothing pass softens the appearance only. No slope rule was needed
  for the small remaining neutral fallback; no steep-terrain geology is invented.

Results: 2,686,632 neighbor-filled cells; 357 neutral fallback cells; 172,585
protected cells; original 2,713,728 unknown cells retained in evidence.
Five unit tests pass, including no crossing of a road, bounded distance,
unchanged inputs and bounded weights. Two independent runs have identical hashes
for all three PNGs. Native UE import verified linear-data/bilinear/clamp settings
and unchanged saved map hash. The mask is now connected to a session-only
Landscape preview on all 1024 components. Whole-area appearance/performance
acceptance remains pending.

## Live material preview, 2026-10-06

`scripts/ue/preview_sa_calobra_masked_materials.py` prepares five blended roles:
Material Maker fractured limestone, scree and mineral, plus existing generated
dry grass and forest litter. R contributes 55% dry fibres with the remainder
returned to mineral; G/B retain their weights. A overlays scree after RGB plus
mineral has been normalized. Native world-aligned projections retain physical
tile sizes. No height, displacement, WPO, geometry or light edits are applied.

In the existing UE Python console, use `runpy.run_path(path)['main']('prepare')`,
then `main('apply')` after compilation settles. `main('restore')` restores the
original global material and the component-230 limestone override, provided
bindings have not changed externally. The session must retain its Python state.
Preparation requires the same-process mask import receipt and existing local
legacy-library receipt/assets. This is not yet a clean-machine replay package.

The live run verified all 1024 component material bindings and unchanged actor
transforms, component topology, edit-layer list, nine collision traces and saved
map hash. The first apply rolled back because this running editor lacks the
newer native instance-audit function. The subsequent preview uses native
component GetMaterial readback; render-instance audit is explicitly pending,
not a PASS. The editor was not restarted and user changes were not saved.

Close and broad viewport inspection confirms visible material replacement.
The broad view is too pale with brown vegetation-floor patches; palette/blend
tuning and more ground-level views remain necessary. No final visual acceptance,
fresh-editor persistence or performance result is claimed.
`native-material-preview-receipt.json` records the live assignment.
`scripts/ue/review_sa_calobra_masked_materials.py` provides a broad review camera;
its `main(restore=True)` restores the previous viewport camera.

Producer: `scripts/assets/prepare_sa_calobra_visual_fill.py` with `--source`,
`--placement` and a new `--output` directory. Source manifest paths/hashes are in
`material-input-manifest.json`. Source packages remain under the canonical data
workspace. Import with `scripts/ue/prepare_sa_calobra_visual_fill.py` in the open
accepted map. Import does not change the map, camera, light or existing materials.

Method references: [SideFX masking](https://www.sidefx.com/docs/houdini/heightfields/masking.html)
and [Epic Landscape materials](https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine).
Named-purpose layers and bounded smoothing follow the documented pattern;
propagation settings are YACS artistic decisions, not SideFX defaults.
