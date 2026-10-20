# Houdini and SideFX world-authoring workflow

**Status:** authoritative execution workflow under the [World Building Bible](../../WORLD_BUILDING_BIBLE.md).  
**Decision:** `HOUDINI_SIDEFX_PRIMARY_20261016`, active from 2026-10-16.  
**Authority:** explicit owner instructions in the local research/generation task; no GitHub issue or production admission is fabricated.  
**Current scope:** fresh, independent Ma-2141 Landscape in Houdini; the entire road reference with 500 m on either side and surrounding terrain for background. No road mesh, earthworks, vegetation, buildings or assembled world yet.

**Immediate owner priority, reaffirmed 2026-10-20:** finish Pegasus lessons 06 and 07. Houdini leads; Material Forge, Blender and Unreal Engine complement its workflow. Preserve the accepted L06 source/cache, complete the L07 material and transfer, and verify the actual UE consumer's heights, validity/visibility, seams, collision and saved/reopened state. See the current [L07 audit](LESSON07_MATERIAL_SETUP.md) for the remaining gaps; a supporting tool's build or render alone does not close the lesson.

## Owner decision and precedence

Houdini is the **primary executor for procedural world authoring**, including Landscape, roads, cliffs and later environment assets. Original SideFX tutorial projects, HDAs and their demonstrated workflows are the implementation starting point. Unreal consumes the outputs and provides the supported runtime/material/editor integration demonstrated by the selected recipe. This does not replace route, physics or geographic data authority with a DCC tool.

The owner's latest clarification is decisive: **original Sa Calobra geography, using Pegasus methods**. The real macro relief, elevations and metric route reference take precedence. The latest clarification also permits **delicate deformation**, provided it remains a separate adjustable/disableable Houdini layer with a preserved source baseline and measured displacement. Pegasus supplies workflows, native nodes, masks, layers, caching and handoff techniques; copying the fictional island's amplitudes or erosion settings is not the goal. An adaptation to Sa Calobra must be named and recorded; SideFX did not supply a Sa Calobra project.

This decision supersedes the previous native-UE/PCG/Blender-first producer preference for new world generation and the blanket freeze insofar as it would prevent this separate, fresh Houdini Landscape. The original DTM, geographic metadata, accepted checkpoints and active Unreal session remain retained evidence. Replacing the live consumer, deleting assets, changing road physics, widening product scope or claiming production acceptance does not follow from the workflow decision. Earlier proof records remain historically true within their stated scope.

The source 8 km × 8 km raster is an available input footprint, **not a requirement to generate or ship every pixel at full detail**. The 500 m buffer defines the working corridor. Background extent/detail should follow the route's visible ridges and terrain context; visibility trimming requires actual camera/terrain evidence. Until that evidence exists, record a conservative background extent as a candidate rather than claiming a proven minimal visible region.

## What “1:1 with SideFX” means

1. Find the exact series and lesson in the [complete concordance](catalog/README.md), open its original transcript and provided files, and record the relevant time ranges.
2. Use the supplied project/HDA where available. Record original file checksum, node type/version, connections, parameters, masks and output contract. Preserve an untouched source copy outside Git.
3. Use Houdini's supported nodes and the tutorial's demonstrated algorithms. Python/HOM may orchestrate nodes, paths, imports and checks; it must not become a hidden replacement terrain, erosion or road generator.
4. Record every necessary adaptation: source dataset, CRS, input geometry, extent, sampling, units, parameter value, cache location or engine-version migration. Distinguish retained original methods from changed inputs and parameters. Do not copy island settings that destroy real terrain fidelity, or call changed values exact tutorial defaults.
5. A caption, downloaded HDA, available node definition, successfully cooked graph, saved/reopened output, correct spatial result and admitted Unreal consumer are separate evidence levels.
6. If the recipe lacks a needed operation, search official SideFX documentation/examples first. Inspect the installed version and test the smallest relevant case. If the missing dependency or behavior remains unresolved, stop the dependent stage and report the exact gap. Do not invent the missing algorithm or fabricate a successful port.

Source captions may be automatic and contain transcription mistakes. Resolve node names and parameter spellings against the original project and installed Houdini definitions. A lesson index is not a claim that every lesson has been semantically studied. Existing custom implementation is not silently rebranded as SideFX work.

## Current delicate-deformation candidate

The owner permits subtle changes while retaining original Sa Calobra. Use a separate reversible detail layer, a control that can reduce its strength to zero, and measured source-versus-output displacement. The primary agent proposed **0.5 m maximum absolute displacement inside the 500 m working corridor** for the first candidate. This is an explicitly labelled working parameter, **not a value specified by the owner or a SideFX recommendation**. The measured candidate now meets that working bound; it does not establish production admission.

The [source/geographic verification](catalog/sa-calobra-geographic-verification.json) and [detail verification](catalog/sa-calobra-gentle-detail-verification.json) are unchanged copies of the current deliverable's evidence JSON files. Their numeric fields establish:

| Measured property | Result | Scope / limit |
|---|---|---|
| Native source HeightField versus imported real DTM | **0.0 m maximum and mean absolute difference** over 70,316,666 valid cells | Exact measured equality on the checked input grid; no claim of survey accuracy beyond the source |
| Source grid | 7,154 × 9,829 cells, **0.5 m** spacing, EPSG:25831 | Cropped source extent; distinct from the rejected 3.90625 m experiment |
| Validity/Alpha comparison | **0 mismatched cells** | Source-validity agreement on this grid |
| 500 m working-mask comparison | IoU **0.9999979991289959**; **64 differing boundary cells** | Small boundary rasterization difference; do not claim exact mask identity |
| Complete route reference coverage | **All 6 parts covered** | Geographic route reference only; no road generation or physics admission |
| Detail maximum absolute displacement | **0.17791748046875 m** | Measured candidate at blend **0.001**, below the proposed 0.5 m limit |
| Detail mean absolute displacement within corridor | **0.02350447326898575 m** | Measured over the working corridor |
| Detail 95th-percentile absolute displacement within corridor | **0.072998046875 m** | Measured over the working corridor |
| Maximum absolute detail displacement outside corridor | **0.0 m** | No measured height change outside the current working mask |

These source and detail differences are separate quantities. The original source/geographic receipt uses the conservative textual summary “less than 1 mm”; its actual measured maximum and mean fields are both exactly **0.0 m**. The receipt is preserved unchanged rather than rewritten to alter that historical wording.

The current deliverable is `Ma2141_SaCalobra_Houdini/SaCalobra_Pegasus.hiplc`, with the real-terrain source and bounded detail candidate. The [fresh-process receipt](catalog/sa-calobra-fresh-readback.json) now confirms **fresh reopen PASS in Houdini Indie 22.0.466**, the cached source/detail switch, matching source/final height hashes and portable project-relative caches. The [preview/switch receipt](catalog/sa-calobra-preview-and-switch-verification.json) independently records the switch hashes and the context-preview maximum delta of **0.177001953125 m**. The default 2048 × 2048 context preview is distinct from the 0.5 m working terrain.

The native `evidence/SaCalobra_Pegasus.png` was rendered and inspected. This confirms render execution and a reviewed preview, not owner visual acceptance or full geographic/consumer admission. **Unreal import remains `NOT_PERFORMED`; production admission remains `NOT_CLAIMED`.** The old large-deformation snapshot remains rejected historical evidence only.

## Source corpus and portable references

The [catalog](catalog/README.md) covers all 16 registered Pegasus series and all 130 parts, all 304 extracted material files from 14 original downloads plus 2 nested archives, 13 supplementary videos and the three Embark/Far Cry talks. It preserves original titles, order, links, language, caption provenance, timestamps, file paths and integrity identifiers. Both series titled *Architecture* have distinct IDs and source URLs.

Resolve source paths through these explicit local roots:

| Root | Contents | Local mapping at acquisition |
|---|---|---|
| `YACS_SIDEFX_CORPUS` | `manifest_transkrypcji.json`, `manifest_materialow.json`, per-series `Czesci/` and `Materialy/`, `DODATKI/` | The task's retained `outputs/Pegasus_Komplet` directory |
| `YACS_SIDEFX_TALKS` | Embark and Far Cry transcripts plus their `manifest.json` | The parent `outputs` directory |
| YACS workspace `work` | Versioned working copies, HIP/HDA recipes, caches, exports and proof | Resolve through `workspace.json` and the [local workspace contract](../LOCAL_WORKSPACE.md) |

Do not copy licensed project archives, third-party binary assets or full transcripts into Git merely to make links work. Configure corpus roots on the host and preserve the originals; relative paths and checksums identify the required file on another host. Availability does not establish unrestricted redistribution rights. Materials borrowed from other packages, such as Megascans, need their own provenance/license and dependency checks.

To rebuild the metadata catalog from retained originals:

```powershell
python docs/tooling/sidefx/build_catalog.py `
  --corpus $env:YACS_SIDEFX_CORPUS `
  --talks $env:YACS_SIDEFX_TALKS `
  --hda-audit <retained-hda-definition-audit.json> `
  --output docs/tooling/sidefx/catalog
```

The optional HDA audit must match each corresponding source file checksum. The builder reads all registered transcript files and material bytes, checks original VTT hashes and extracted CRCs, and records SHA-256. It executes no supplied project or embedded script. Original archive hashes remain acquisition receipts; this rebuild does not re-download ZIPs. The catalog's verification labels describe only this bounded audit.

## Execution and data ownership

| Stage | Executor / owner | Durable input and output | Required evidence |
|---|---|---|---|
| Source acquisition | World Data / domain authority | Original DTM, route/GIS, source validity, CRS and license → immutable source manifest | Provider, acquisition date, checksum, units, NoData and source limits |
| Project setup | Houdini package / original Pegasus folder workflow | Untouched source HIP/HDA → separate working recipe and dependency map | Original checksum; exact Houdini/Engine versions; paths and dependencies |
| Geographic adaptation | Houdini import and documented adapters | Metric Sa Calobra sources, full Ma-2141 reference, 500 m corridor → registered inputs/masks | Axis/scale/origin samples, full route coverage, invalid-data handling |
| Terrain authoring | Houdini tutorial-backed import, curves, masks, layers and sampling; only source-faithful derived detail | Registered real DTM + explicit parameters → source-faithful HeightField and named layers | Node/parameter provenance, real cook logs and source-relative fidelity; noise/erosion cannot redefine macro relief |
| Cache/output | Houdini file/ROP/PDG mechanisms as demonstrated | Cooked fields/meshes/layers → portable caches and exports | Input fingerprint, output checksum, successful reload, dimensions and bounds |
| Engine consumption | Houdini Engine / documented Unreal handoff | Versioned Houdini outputs → Unreal Landscape/assets/material bindings | Exact consumer version, import settings, saved/reloaded native data and visual evidence |
| Review/admission | Existing YACS proof and owner boundaries | Candidate output + source/delta/visual evidence → accepted or rejected bounded result | Existing technical gates; assembled-M3 owner audit; performance remains deferred after M3 |

Unreal/PCG/PCGEx remain possible consumers or demonstrated integration mechanisms. They are not the default alternative generators for the new workflow. Blender may provide a documented input/UI/preparation role (as in the Embark Asset Processor reference); it does not replace Houdini's processing. Material Forge remains retained supporting surface tooling, not the authority for spatial placement. BOB retains road/earthworks domain constraints and validators; new road geometry execution belongs in the selected SideFX/Houdini recipe.

## Current terrain recipe and explicit adaptation

Start with **PEG-01 Landscape Creation**, especially `PEG-01-01` (HeightField Erode), `PEG-01-02` (Building the Landscape) and `PEG-01-03` (Landscape Digital Asset). `PEG-02-02` records the layered pipeline; `PEG-02-03` and `PEG-02-04` cover heightfield material detail and masks. Their exact captions, original projects and shared HDA bundles are linked in the catalog. Those material-detail steps are references, not authorization to add the rest of the world now.

The supplied Landscape Creation HDA is `pe_landscape::1.0`; its source library SHA-256 is `23dcea9051f5d4d980b548eec95005d2616dc0093717aa6df0cbdce4a8faee27`. The source HIP SHA-256 is `35194d7f7c2784c17f9b539cfc46b76df89d01cbb602618aab43dd803283f645`. A [selected original-node audit](catalog/landscape-source-node-audit.json) records the inspected values and connections under Houdini 22.0.466. It is source inspection, not proof of a successful adaptation.

The inspected original contains the following stages; exact selected node values are retained in that audit:

| Source operations | Original role | Ma-2141 adaptation requirement |
|---|---|---|
| `curve::2.0`, `reverse`, `polyextrude::2.0`, `tube`, `merge` | Example island shaping geometry | Keep the geographic road reference; document which source shapes are retained, replaced or constrained for the real terrain |
| `heightfield`, `heightfield_project` | Create and project the shaping geometry | Document DTM import/registration and any replacement of the blank/example input |
| `heightfield_maskbyobject`, `heightfield_blur` | Derive and soften shaping masks | Record corridor/background/source-validity masks and their provenance; do not treat NoData as measured ground |
| `heightfield_noise`, `heightfield_distort`, `heightfield_remap` | Layer procedural forms and remap height/masks | Record changed amplitude, scale, seed, masks and bounds; preserve a source-relative delta |
| `heightfield_erode::2.0`, `heightfield_resample` | Successive erosion/detail passes | Record simulation settings, reset/cook sequence, output layers and sampling; do not substitute a custom erosion solver |
| Bedrock/debris/water/sediment remaps, layer filtering, material attribute, output | Prepare exported layers and consumer bindings | Keep only currently required terrain outputs; report absent material dependencies without fabricating them |

**Current terrain is sourced from the real DTM.** Curve-driven corridor masks, layers and cache/output methods can be adopted without imposing the example island's invented relief. Noise and erosion are not permission to move ridges, valleys or elevations. If a detail operation is needed, demonstrate its source-faithful purpose and effect first; unresolved fidelity requirements are not an invitation to guess parameters. Never move canonical Ma-2141 XY, alter physics, conceal missing elevation data or overwrite the original DTM.

The initial experiment copied the original procedural values onto real DTM input and substantially changed the relief. It is **rejected as a representation of Sa Calobra**, retained only as negative evidence. It must not be the current/default terrain or an admitted Unreal/physics input. Its source geometry and all adaptation records remain separate from the real-terrain baseline. The [retained trial receipt](catalog/rejected-terrain-trial-20261016.json) records 36 copied nodes and a 15-node / 874-parameter comparison, with the erosion memory-cache exception. Despite that source matching, the measured maximum height displacement was 173.49 m, the mean absolute displacement inside the working corridor was 22.57 m, and 63.10% of corridor cells moved by more than 10 m. Original mask blur also spread changes outside the 500 m corridor. These are rejection evidence, not fidelity tolerances. The 2048-square trial grid was 3.90625 m spacing over 8 km; it was not the original 0.5 m source resolution. Exact reuse of parameter values does not establish geographic fidelity.

Road construction is a later recipe. `PEG-13` includes pathfinding and Unreal spline workflows, but a shortest-path solver may not reroute the measured Ma-2141 alignment merely because it appears in the tutorial. Use the parts that match the approved source-aligned road task and explicitly document omitted/different stages.

## Recipe record and stopping conditions

Use the [recipe template](RECIPE_TEMPLATE.md) for every implemented chain. Required fields are source part/time range, source HIP/HDA checksum, input contract, actual graph, parameter deltas, installed versions, output contract, dependency gaps, regeneration instructions and separate proof states. The complete catalog is a lookup layer; it does not replace a recipe's exact step mapping.

Stop the affected stage if the referenced material is absent/corrupt; a node/API is not available in the installed version; a required external asset is unavailable or unlicensed; source registration/NoData semantics cannot be established; the recipe needs an undemonstrated operation with no verified official solution; or the output cannot be validated against its contract. Independent documentation/research may continue. Report `MISSING`, `NOT RUN`, `FAILED` or `UNVERIFIED`, with the actual evidence.

Do not infer production PASS from a downloaded transcript, HDA inspection, green process exit, screenshot or catalog entry. No global scene replacement, road generation or broad world rollout is admitted by this documentation update.

## Official capability references

Match these current SideFX references to the installed Houdini version and the recipe before relying on a behavior. The tutorial and original asset remain the primary recipe; documentation fills a named gap, not a hidden redesign.

- [HeightField File](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_file.html)
- [HeightField Project](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_project.html)
- [HeightField Mask by Geometry](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyobject.html)
- [HeightField Noise](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_noise.html)
- [HeightField Erode](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_erode.html)
- [HeightField Resample](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_resample.html)
- [HeightField Crop](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_crop.html)
- [HeightField Output](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_output.html)
- [Houdini Engine for Unreal: Landscapes](https://www.sidefx.com/docs/houdini/unreal/landscape/index.html)

## Current verification boundary

The catalog verifies source availability/integrity and records prior HDA definition inspection under Houdini 22.0.466. The selected Landscape source graph has been inspected. There is **no catalog-wide claim of semantic mastery, successful cooking, complete dependency closure or implemented YACS behavior**. The current real-Landscape source/grid and gentle-detail measurements are recorded above with their unchanged JSON receipts. Fresh-process reopen, the source/detail switch and a rendered/inspected native preview are now supported by the linked receipts. Unreal integration and production admission remain unperformed/unclaimed; no catalog-wide implementation claim follows. The deformed Pegasus trial is rejected evidence, not that baseline. The older production-reference dossier remains architecture evidence, not permission to return to its superseded native-first producer choices.
