# M3 world, host and owner decisions

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

### Live editor collaboration with the owner

Owner checkpoint/workspace decision, 2026-10-04: the canonical home workspace is
`D:\yacs`, with the live project at `D:\yacs\project`. Resolve data, cache and
checkpoint paths through `scripts/manage_local_workspace.py` and the local `workspace.json`.
Do not resume authoring from a chat scratch directory or a CI runner checkout.
The owner explicitly authorized durable storage of the accepted frozen scene;
this supersedes the session-only restriction below for that checkpoint and its
verified reopening. It does not authorize new road design or terrain targets.
Use persistent actors/materials and persistent float32 CUT textures, retain
fixed source hashes, and verify a fresh editor reads the saved geometry and
earthworks. A file-copy receipt is not a scene checkpoint, and a local checkpoint
is not a remote backup. Keep heavy build and editor migration operations serial.
Never create full hidden pavement copies merely to back up a live GPU scene.
See `docs/tooling/LOCAL_WORKSPACE.md` for the authoritative host workflow.

Owner expansion, 2026-10-04: consolidate the whole YACS host environment under
`D:\yacs`, including `runner`, `runner-monitor`, `engine`, external `data/mocap`,
caches and retained historical worktrees. Remove verified obsolete duplicates
only after preserving unique bytes and local Git changes. Old-path junctions
are compatibility aliases, never new authoring roots. Runner credentials and
local caches stay outside Git. CI owns its isolated `_work` checkout and must
never compile or clean the open authoring project. Preserve the interactive GPU
runner mode; changing it to a Windows service requires a separate runtime proof.

Owner preference, 2026-10-04 (Issue #335): combine reproducible scripts with
visible work in the already open Unreal Editor. Scripts prepare data, validate
contracts and collect evidence; Computer Use supports navigation, inspection and
showing the owner the result directly in the editor.

- Before declaring desktop control unavailable, read the installed Computer Use
  skill and discover its supported runtime. Browser-only tool limitations do not
  establish that a separate Windows Computer Use plugin is unavailable.
- Select the actual returned Unreal window, observe its current state, perform
  one UI action and refresh. Never click from stale screenshots or guessed UI.
- Explain meaningful actions and findings briefly in Polish while the owner
  watches. Prefer the existing session and preserve their unsaved work.
- Use direct UI work for bounded visual review; capture reusable multi-step
  production operations in repository-owned scripts rather than repeated clicks.
- Existing task authorization covers routine reversible navigation and review;
  do not repeatedly ask permission. Respect tool safety rules and report exact
  tool failures instead of claiming success or silently switching mechanisms.
- UI access does not authorize a wider mutation scope. For Issue #335, keep
  terrain/roads frozen, fit masks to their existing contract, and keep previews
  session-only: no Save/Save All, heightmap import or earthworks regeneration.
- Distinguish live inspection, owner visual acceptance, saved assets, exact-SHA
  proof and performance admission. A screenshot or successful click proves none
  of the other gates by itself.

Operational guidance: [live local editor review](../../../docs/UE_MCP_WORLD_GENERATION.md#live-local-editor-review).

### Blender headless DCC producer — Issue #391

Owner decision, 2026-10-06: the canonical portable Blender toolchain is pinned
to **4.5.9** at `D:\yacs\tools\blender-4.5.9-windows-x64\blender.exe`.
Use `scripts/blender/run_headless.py` and
`docs/tooling/BLENDER_HEADLESS.md`; do not rely on a system Blender, PATH
discovery or a copy committed inside the repository.

- Blender is a deterministic DCC producer, not road, terrain, BOB, World
  Authority, route/physics or Unreal authority.
- Headless jobs must use the pinned exact version, repository-owned Python and
  the launcher safety boundary: background mode, factory startup, automatic
  .blend script execution disabled and non-zero Python exception exit.
- Keep default intermediates/proofs below the persistent workspace `work` tree.
  Promotion into source assets or Unreal content requires the relevant existing
  provenance/consumer/proof contract.
- A successful Blender receipt proves only that the named headless job ran on
  the recorded inputs. It is not Unreal integration, visual acceptance or
  performance admission.
- Do not use Blender work under #391 to mutate the currently frozen Sa Calobra
  road/terrain geometry or to bypass the staged world-authoring dependency gates.

### Whole-Landscape appearance and performance scope

Owner clarification, 2026-10-04: while the owner explores the open Unreal scene,
normal authoring iterations must update that same visible session. Use Live
Coding for supported C++ changes and explicit editor refresh/reimport for
changed masks, materials and scene consumers. Verify the visible consumer
actually updated; a green CI build is not delivery to the owner's preview.
CI remains isolated. Announce required editor restarts before performing them
and preserve unsaved work. Frozen geometry restrictions still apply.

Owner clarification, 2026-10-04: author, review and optimize the **entire current
Sa Calobra Landscape**, 2,016.5 m × 2,016.5 m (~4.07 km²). Both appearance and
performance acceptance cover this whole area. The 500–1000 m Golden Kilometer
is an additional representative check, not a substitute for whole-Landscape
review or measurement. Cover the area's different environments, demanding views
and traversal; do not infer area-wide PASS from one selected section. Preserve
existing budgets, exact-SHA proof, milestone-driven heavy measurement and frozen
terrain/road geometry. Full-route expansion means going beyond this Landscape.

Owner extension, 2026-10-08 (PR #446 whole-map surface preparation): local
Landscape and seam corrections are authorized when needed to preserve visual
coherence. Diagnose the owning surface and keep each correction spatially
bounded, source-relative and reversible through the existing derived-output or
Edit Layer workflow. Retain the original source/checkpoint, record the changed
extent and displacement, preserve neighbouring interfaces and check close plus
distant views. This supersedes blanket frozen-Landscape restrictions for these
named local corrections; it does not authorize global smoothing, changes to
canonical road XY/physics, weakened exclusions or invented macro geography.
Material-only proofs must still establish their own unchanged-geometry claim;
a geometry correction requires its own delta and rollback evidence.

### Deferred red-overlay review

Owner decision, 2026-10-04: retain the red surface problem-review overlay and
its P1–P5 / R4C2 / R4C3 queue for the final polish/review pass tracked by #372.
Do not load or refine that overlay during the current 2A closeout / 2B kickoff.
Preserve the native registered PNG, flag raster, source hashes and manifest;
the merged #379 / #380 audit records their meaning and replay procedure.
Unknowns remain unknown, hard exclusions remain binding, and candidate RGB
classes are not validated geography or production planting authority.

The owner authorized merging the 2A baseline and starting #363, and explicitly
transferred the 2A performance measurement to 2B (#363). Do not dispatch a GPU
benchmark to close 2A. The narrow frozen-baseline exception is recorded in
`.gumball/world-proof-policy.json` and reports `DEFERRED_TO_2B`; any material,
mask, geometry, runtime configuration or producer change ends that exception.
This is authorization to progress the baseline, not a fabricated performance
PASS or permission to bypass protected CI. Resolve required technical admission
before marking #335 complete or starting its dependent implementation.

Owner decision, 2026-10-09: "wydajność zmierzymy po domknięciu m3".
Measure performance after the assembled M3 world is closed out. This supersedes
the earlier 2A-to-2B measurement deadline and the performance prerequisite for
the intermediate #363 → #384 → #364 handoff. Record `DEFERRED_AFTER_M3` and
`performance_pass: false`; this is neither a performance PASS nor final
performance admission. Preserve whole-area owner visual acceptance, saved and
fresh-rendered consumer proof, native build/Automation/asset proof, review and
protected CI. The later benchmark retains exact-SHA/default-branch provenance,
the full-area scope, reference hardware and existing budgets. This decision
does not authorize an exception for later product milestones.

### Region migration and LFS retirement

Owner update, 2026-10-02: execute the six-step Sa Calobra migration and retire
obsolete Italian LFS payloads. This supersedes the 2026-10-01 retention directive
for positively identified obsolete Italy assets only. Inventory dependencies
and exact paths/object hashes before removal. Do not blanket-prune shared LFS
storage, delete Spanish inputs/output, or rewrite Git history. Report actual disk
reclamation separately from removing tracked pointers. Until bounded retirement
runs, existing retention guards continue to preserve bytes.

### Historical terrain retention baseline

Owner directive, 2026-10-01 (Issue #308): keep downloaded/materialized LFS assets on disk while rebuilding terrain. Do not prune LFS storage or delete asset payloads during cleanup. The original `_embark-terrain-worktree` remains untouched by the recovery lane. Before checkout/reset/cleanup of `_terrain-recovery-worktree`, move materialized Unreal assets to the sibling `_yacs-retained-lfs/<run>-<attempt>/` archive, verify their SHA-256 and size, and fail before cleanup if retention fails. Code-only checkouts can still use pointers; the retained binary bytes and `.git/lfs/objects` remain on disk.

### Roadmap and world-building nomenclature

- `docs/ROADMAP.md` uses only product milestones `M0` through `M10`.
- Do not create recursive planning identifiers such as `M3.1.2`, `R4.1B.3` or equivalent.
- Concrete work is tracked by GitHub Issue number plus a human-readable title.
- Existing Stage/R/B identifiers may remain in historical documents, workflow names and proof artifacts for traceability.
- For any terrain, road, earthwork, Landscape, PCG, material, cliff, world-streaming or world-performance change, `docs/WORLD_BUILDING_BIBLE.md` is the methodology SSOT.
- Before creating or materially extending a custom world-building subsystem, follow the Bible's tools-first audit and architecture evidence ladder. External production evidence increases confidence but never replaces a bounded YACS proof against YACS inputs.
- `docs/YACS_WORLD_AUTHORING_LIBRARY.md` defines reusable implementation/catalog systems; it does not override the Bible's world architecture.
- New or substantially revised architecture/workflow diagrams must follow `docs/DIAGRAM_STYLE.md`, the YACS adoption of the Gumball Blueprint Mermaid language.

### Official Unreal MCP adoption — bounded delivery decision

Owner decision, 2026-10-05: #384 is the bounded official Unreal MCP adoption
workstream, informally "step 2.5", between #363 and #364 inside M3. It is
**blocked until #363 is fully completed and merged**, with whole-Landscape
visual acceptance, saved/fresh-rendered consumer proof and all required
technical/review gates. The 2026-10-09 performance deferral above applies.
No implementation,
plugin activation, implementation PR or Ready/In progress promotion before that
gate. Documentation-only planning (#385) may merge without closing/unblocking #384.
#364 retains its #363 dependency and also depends on #384; the remaining sequence
is unchanged. A closed-as-not-planned issue or green CI alone is insufficient.

Verified closeout, 2026-10-09: #363 is completed after protected PR #446 merge
`ad9a487ba2177fd49bb2d90784bac9a9f661ab3b`. Its whole-area material acceptance,
saved/fresh-rendered consumer and technical evidence satisfy #384's entry gate.
#384 is open. [Native run 38027596123](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/38027596123)
passed the fixed inspection/test session at runtime SHA
`241104de320f8417c7abc4dd973ac148ed98a66d`. Its bounded verified summary records
official transport, one passing `CyclingPhysics.RoadPhysics.ProfileInterpolation`
test and real BOB capture, retaining `REVIEW_REQUIRED` / `INSPECTOR_ONLY` and
all false authoring/admission flags. Full pinned receipt review, standalone
`YacsBobInspection.InputBoundary` proof and protected PR #467 closeout remain
pending; official MCP admission is still false and #364 remains blocked by #384.
Reverify the [material handoff](../../../docs/tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md)
at kickoff. This checkpoint does not admit geometry or change Project status.

Read [the current MCP decision and bounded DoD](../../../docs/UE_MCP_WORLD_GENERATION.md#official-unreal-mcp-adoption)
before MCP work. The official Epic server has bounded native inspection/test
evidence; the pinned db-lyon integration remains the retained baseline until
reviewed cutover. The repository already targets UE 5.8; this decision does not
migrate it.

MCP is orchestration/interface, never authority. BOB, World Authority,
route/physics contracts, tests, proof producers and governance keep their
responsibilities. Native PCG is the foundation; PCGEx is a pinned extension for
named gaps. Preserve already proven PCGEx work and all current safety boundaries.
From world-finishing step 3 onward, do not build custom generic Unreal-control
workarounds when official Epic MCP supports the case within YACS constraints.
Custom toolsets contain only YACS domain knowledge/contracts. Existing producers,
CI commandlets and proof collectors remain valid; this is not a blanket rewrite.

The spike proves one map/scene, Actor/UObject read, existing Automation Test and
real BOB inspection with result/proof/receipt. Prove guard parity before cutover;
never assume native tools inherit the old guard. After success, **STOP adding
infrastructure and return to #364**. Missing/unsafe capability is an explicit
blocker, not permission to create another platform or weaken a gate.
The fixed inspector does not admit stock `MaterialInstanceTools`: #364 requires
separate version-matched schemas, argument/resource restrictions and material-only
native authoring proof before using that surface.

### Frozen geometry and environment fidelity — Issue #335

Owner decision, 2026-10-04: existing terrain and roads are frozen for the current
2A World Authority / masks task. Fit masks to the existing Landscape and road
coordinate contract; never modify heights, reimport a heightmap, smooth terrain,
move roads or regenerate earthworks to make masks fit. Source discrepancies are
review evidence, not permission to repair geometry.

- Roads, building placement/footprints and Landscape require source-faithful 1:1
  metric scale and spatial alignment within admitted source accuracy. Unknown or
  conflicting building evidence must remain explicit, not guessed.
- Surroundings should preserve the place's character as closely as practical:
  broad vegetation/open-ground/rock domains, density, canopy character and scenic
  cues. Individual trees, shrubs and small decorative rocks need not reproduce
  exact measured positions; do not spend work moving a tree 50 cm for scan fidelity.
- Decorative freedom must respect road safety/exclusion, buildings, terrain and
  meaningful landscape domains. It does not authorize arbitrary biome changes.
- The current consumer proof is a diagnostic color overlay on existing geometry,
  with separate labels for context, measured disagreement and unknown evidence.
  Fix mask processing/alignment errors; leave unresolved geometry discrepancies
  for review. Production materials/PCG remain subsequent stages.

The normative world contract is in `docs/WORLD_BUILDING_BIBLE.md`, section 5.3.

Owner exception, 2026-10-04 (Issue #335): this mask task may consume only the
already frozen, visually accepted road output artifacts from
`c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6` / draft PR #338 as read-only mask
inputs. Pin source hashes and retain all original admission limits. This narrowly
overrides the parallel-unmerged dependency rule for those output artifacts only;
do not adopt that branch's code, execute its road builder, alter geometry or
claim that PR #338 is merged or engineering/performance-admitted.

### BOB single-direction bend contract

Owner decision, 2026-10-03 (Issue #331): apply this requirement to the current
Ma-2141 hairpin and future BOB-authored single bends. Read the normative
[World Building Bible contract](../../../docs/WORLD_BUILDING_BIBLE.md#bob-single-direction-bend-contract)
before changing a bend.

- Entry and exit have the same explicit base pavement width, constant within
  each approach. Either approach may be a gentle curve in the bend's direction.
- The main bend may have a small, explicit widening only where a vehicle
  swept-path requirement justifies it. Blend to/from that widening inside the
  main-bend design domain; return to base width before the constant-width exit.
- Entry, main bend and exit turn in one direction. Check signed curvature and
  accumulated heading on both final pavement boundaries and the derived axis;
  reject unintended reverse turns, noses, pinching and local bulges. G2 joins,
  dense tessellation or green CI alone do not satisfy this requirement.
- Solve boundary alignment and width together, retaining cliff-reference
  priority and independent physical-edge/travel/bend/terrain labels. Small
  approach adjustments stay within the admitted presentation envelope.
- Treat the 183a30e visual result as rejected against this contract; its green
  technical run is historical evidence, not visual acceptance. Implement and
  verify the new invariant before accepting or propagating the bend.

### Unreal / PCGEx API-first source policy

For any task that depends on Unreal Engine, native PCG, Landscape, Geometry Script,
Spline/SplineMesh, DynamicMesh or PCGEx behavior, **do not implement from model
memory or guessed editor/API behavior**. Establish the exact tool versions first,
then verify the operation against version-matched primary documentation.

Use this evidence order:

1. use `docs/README.md` to select the current YACS SSOT that defines **what YACS
   wants and which subsystem owns the truth**;
2. identify the exact Unreal Engine version used by the project/runner, then read
   Epic's official documentation and C++ API reference for that version:
   `https://dev.epicgames.com/documentation/en-us/unreal-engine/` and
   `https://dev.epicgames.com/documentation/en-us/unreal-engine/API`;
3. when PCGEx is involved, identify the exact approved/pinned PCGEx revision and
   plugin version from YACS provenance/bootstrap evidence, then read the official
   PCGEx GitBook: `https://pcgex.gitbook.io/pcgex`;
4. for agent research, start from PCGEx's official agent indexes
   `https://pcgex.gitbook.io/pcgex/llms.txt` and
   `https://pcgex.gitbook.io/pcgex/llms-full.txt`, then open the exact per-node or
   system page; use the GitBook Markdown/`ask` interface when a targeted behavior
   is not explicit on the page;
5. if official PCGEx documentation is ambiguous, incomplete or newer than the YACS
   pin, inspect the **pinned upstream source/header at the exact YACS revision**
   before writing an adapter or graph; source may clarify implementation behavior
   but does not override YACS authority boundaries;
6. prove the resulting YACS integration with the smallest relevant build, graph,
   editor, automation or visual proof required by the current SSOT.

Hard rules:

- Never invent an Unreal/PCGEx class, function, node, pin, property, enum, default,
  lifecycle rule or editor behavior because it sounds plausible.
- Never silently apply documentation for a different UE or PCGEx version. If the
  matching behavior cannot be verified, fail closed and report it as unverified.
- Search snippets, forums, videos, DeepWiki and secondary tutorials may help locate
  concepts, but they are **not authority** when Epic/PCGEx primary docs or pinned
  source are available.
- For PCGEx path work, verify the path data model and every selected node against
  the official Paths/node-library documentation before authoring or changing a
  graph; point order, closure, tangents, normals and segment semantics are part of
  the contract, not implementation trivia.
- A vendor API proving that an operation exists does not make it correct for YACS.
  YACS SSOT still owns route/physics/world authority, architecture and acceptance.
- In the Issue/PR report for a non-trivial Unreal/PCGEx API decision, record the
  exact UE version, PCGEx revision/version when applicable, and the primary docs or
  pinned source consulted so a later agent can reproduce the decision.

### Passo Giau terrain-recovery guardrails

For Issue #287 / PR #288, Gate B is an established road-authoring baseline, not an
open smoothing experiment. The pinned PCGEx graph has executed against prepared
official SP638 presentation data, produced bounded deviation evidence and fed the
rider-close consumer. Until a concrete regression proves otherwise:

- do not change PCGEx resample/smoothing/corridor behavior merely to improve terrain appearance;
- do not move canonical road XY, route authority or Road Physics Profile truth to repair a visual seam;
- keep PCGEx presentation-only and authoring-only; it is not physics authority.

Before introducing another terrain generator, another smoothing stack or another
global-resolution change, isolate the owning surface with the same exact-SHA
camera/light/FOV proof. For the current hairpin this means the A-E diagnostic matrix:

- A: macro Landscape only;
- B: macro Landscape + road corridor;
- C: local/near-field ground only;
- D: local/near-field ground + road corridor;
- E: full combined baseline.

Use the result to identify the owning layer before changing architecture.

Rider-close terrain must follow these rules:

- prefer a bounded near-field surface derived directly from the prepared native
  metric DTM over line-tracing/resampling a known-bad Landscape;
- use finer bounded spacing where the rider camera can inspect the ground rather
  than increasing the entire world to the same resolution;
- select `Road_Earthworks` explicitly by semantic name; missing, duplicate or
  accidental `Base_DTM` selection fails closed;
- one place has one visual ground owner: do not rely on two coincident surfaces,
  arbitrary Z lift or overlap to hide disagreement between Landscape and a local mesh;
- connect near-field to macro terrain with a deterministic transition band whose
  outer boundary is constrained to the macro surface;
- apply road/cut/fill constraints to the local ground before final triangulation
  where that produces a single coherent surface;
- do not use materials, RVT, vegetation, fog, AA or lighting to conceal unresolved geometry.

A terrain recovery is not accepted because one hairpin looks good. After the
baseline hairpin passes, prove at least a normal/moderate slope corridor and a
large-elevation-difference/earthworks case. Run the relevant performance proof
after neutral geometry passes visually, not as a substitute for visual acceptance.

