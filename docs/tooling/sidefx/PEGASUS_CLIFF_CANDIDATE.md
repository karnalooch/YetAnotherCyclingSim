# Pegasus cliff candidate: bounded native extraction

## Current status

**PAUSED: 92 / 178 raw candidate windows validated; 86 remain.** The raw layer
uses provisional 2D road exclusion, which is not valid production clearance for
tunnels or overhanging rock. Full-route generation and world admission are open.
There is **no final spire/overhang proof**. The isolated native UE preview was a
thin folded sheet and was **not accepted for visual quality**. Neither strength,
normal-blur nor texture-scale controls established a finished cliff appearance.

The paused orchestrator was subsequently stopped at its verified boundary;
there is no orphaned batch process. Checkpoint-only recovery validation is
recorded below; it never generates the remaining windows or changes sources.
Historical successful component tests below do not override this current state.

Date: 2026-10-24. M3, existing #365 workstream and `codex/365-world-graph`;
research base `dd2322f1e1ad784ee45878d40e80fcf69f953b30`, local uncommitted adapter.
The owner authorized cliffs and real Ma-2141 roads in this conversation. This
receipt does not itself amend SSOT scope or claim a remote commit.

## Sources and adaptation

The [official Cliff Generation series](https://www.sidefx.com/tutorials/project-pegasus-cliff-generation/)
and [PEG-05 concordance](catalog/PEG-05.md) supply the original project.
L02 captions were read, including 01:27–01:50 (feature-mask alternative),
01:56–04:27 (mesh extraction/cleanup/connectivity) and 05:52–10:57
(flow-based section separation). L03 describes boundary-aware displacement,
two blended height maps, restored Y, reduction and vertex material masks.
Captions and original definitions were inspected; no claim of watching the film.

`CliffPDG.hip` SHA-256:
`3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a`.
`sop_PE_Heightfield_Extract_Cliffs.1.0.hda` SHA-256:
`16d7c13d9ca5ba4af221584a1fde7232fecfee0a3d173b616e1aabadf3464f70`.
Originals remain in the external corpus under
`P1_05_Cliff_Generation/Materialy/Pegasus_Cliff_Project_Files_2/Pegasus_Cliff_Project_Files`.
The actual source root on this host is
`<owner-source-library>/Pegasus_Komplet`.

The adapter [pegasus_cliff_candidate.py](../../../scripts/houdini/pegasus_cliff_candidate.py)
loads the original HDA, verifies its resolved definition and hash, and feeds
the retained native `cliff_mask` into `mask`. It bypasses only the original
ID decoder because this input already contains semantic masks. All original
flow/conversion/blast/cleanup/connectivity operations remain. Small-parts
threshold is explicitly adapted from 1000 to 0 for the bounded patch.
The fallback slope range 35–90 degrees is an experimental parameter used only
without crop metadata; it was **not used** for the successful accepted crop.
No replacement cliff algorithm is implemented in Python.

## Actual source and result

The successful input is the existing native
`D:/yacs/work/lesson07-cc0-real-material/39808914161-1/real_source.bgeo.sc`,
SHA-256 `c40d82ade89e1175f66edf3763deff6ac8fa81826e8944f10d806285b88be889`.
All seven native volume byte hashes and first/last voxel coordinates were
checked against retained crop receipts at
`D:/yacs/work/lesson07-cc0-real-crops/39785285512-1`.
The base source pin is
`08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952`;
the masks source pin is
`203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8`.
This is **accepted L06 base geometry**, not the later final procedural-detail
surface. The crop has 256 × 256 samples at 0.5 m spacing, nominal 128 m footprint.
First/last samples are `(-19.249916, 0, -1780.250122)` and
`(108.250084, 0, -1907.750122)` in the retained Houdini local coordinate frame.
The entire verified crop is used; optional CLI center/size do not override its
measured bounds.

Houdini 22.0.466 cooked 46,155 points and 44,471 primitives. Bounds:
X −19.249916…108.250084 m, Y 201.100006…326.290009 m,
Z −1907.750122…−1780.250122 m. Coordinates were finite. Extraction reported no
node warnings. Labs resolved from
`D:/yacs/tools/sidefx_packages/SideFXLabs22.0/otls/SideFX_Labs.hda`.

Outputs are retained outside Git at
`D:/yacs/work/pegasus-cliff-real-crop-20261024-verified`:

- `candidate.hiplc`: `e3bd81d358775a610ce98da11beb1dd54376c70a017fdf51bb1fb7fe34de41dd`.
- `cliffs.bgeo.sc`: `6d40cb2f6222a0403f8f77aae99e42f840169bdc987ae2988616d364f1d36a52`.
- `receipt.json`: producer identity, measured bounds, source lineage, resolved definitions.
- `fresh_reopen.json`: separate fresh-process HIP identity/file-binding/hash/count check.

Fresh output disk reload passed. **Graph regeneration was not tested.**
The native run logged a Python menu callback error on the bypassed original
ID decoder: `dictAttribValue: No attribute with this name exists`. This input
does not supply ID metadata; the geometry path uses the already decoded mask.
Retain this diagnostic rather than presenting the console as error-free.

## Reproduction and remaining work

Use the installed `D:/yacs/tools/houdini-22.0.466/bin/hython.exe` with
`HOUDINI_OCL_DEVICETYPE=CPU`. Supply `--source` and `--crop-metadata` paths above,
`--otls` pointing at the source bundle's `Houdini/Packages/PegasusDemo/otls`,
and a **new** `--output` directory. Then run the same output with `--reopen`.
Do not overwrite existing evidence. Source files, accepted HIP and UE scene
are never changed. Cook uses two CPU threads; no GPU/UE operation was performed.

Two initial coarse-context experiments yielded empty geometry because Manual
update mode suppressed native cooking even with `cook(force=True)`. Automatic
mode fixed this; those results are not evidence of absent cliffs. A wrong
crop receipt was also rejected on the height hash before the correct retained
source token was identified. The successful source excludes those experiments.
Direct sandbox launch failed with Windows DLL relocation; authorized escalated
execution worked. None of these errors justifies altering the active editor.

Remaining: boundary/contact measurements, road exclusion/clearance, full route
inventory and coverage, material binding, UE import/collision/save/reopen and
visual review. No spire/stalactite-specific source mapping has been established.
Do not infer arbitrary geological forms from this extraction rehearsal.
Full-cache read was avoided because only about 4.44 GiB physical RAM was free;
the existing exact crop allowed native proof without recooking or reading the
entire 16000² terrain. Performance remains `DEFERRED_AFTER_M3`,
`performance_pass: false`; production admission remains false.

## Original Generator: one real component

The subsequent `--detail` run used original `PE_Cliff_Generator::1.0`, library
SHA-256 `3d264fdc67648609a8c83bd1d7a34d65bb15744a23114477cda4ae48b1fde3f4`.
Extracted class 27 contains 606 source polygons. Original internal subdivision,
boundary distance mask, triplanar blend, Y restoration, reduction, curvature and
AO operations were retained. Extra subdivision was reduced to 1; displacement
strength 0.15 and texture scale 0.1 are explicit candidate settings, not SideFX
or owner standards. Output percentage remains 80.

The two retained CC0 inputs replace the tutorial's Megascans textures:

| Input | SHA-256 |
|---|---|
| `dark_rock_02_disp_4k.exr` | `50260bf6b1af4cdc16dc1f556ab0934bfc3462e1007a4a5796c6cbfe20b001fe` |
| `dark_rock_disp_4k.exr` | `8104875e4a3c7bdf3019fffa17273d4d24f467353db6543203aa6b93935d558e` |

Files and license binding were checked against the existing
`D:/yacs/work/lesson07-polyhaven-cc0-v1/bindings-v1.json`; no new asset purchase
or acquisition occurred. The native result has 26,716 points and 30,105
primitives; bounds X 30.749710…50.250481 m, Y 270.900360…287.329559 m,
Z −1898.250488…−1880.250122 m. No generator node warnings occurred.

Measured displacement versus the **same original graph at zero strength,
before reduction**: maximum 0.078680123 m, mean 0.014443212 m, maximum absolute
Y change 0.0 m. This isolates added displacement. It does **not** measure total
deviation from DTM: original smoothing/subdivision changes topology, and that
separate macro/contact comparison remains open.

Retained folder: `D:/yacs/work/pegasus-cliff-detail-20261024`.
HIP SHA-256 `43e12d9397534ddfed056cdc0d1aaa2cf4f8017820a49f3649a6bd186e5b3b5c`;
geometry SHA-256 `2d960c8d16b07ec7415555e42387ccaca2db6446d3b5df7454f55cf703699759`.
The folder includes the zero-strength geometry, final BGEO/OBJ, producer receipt
and separate fresh-output-reload receipt. Fresh output disk reload passed;
graph regeneration, Unreal and full-route proof remain unperformed.

An actual OBJ geometry projection was generated on CPU and inspected at
`Saved/pegasus-cliff-detail-20261024.png`. It shows a smooth, curtain-like
surface with conservative detail. It is a diagnostic geometry view, not a
native UE render or visually accepted reconstruction. Roadside context and
contact are absent from that image. No production visual PASS is claimed.

## Full-route input feasibility

The existing 16 files under
`D:/yacs/work/lesson07-full-domain-producer/2026102232-1/tiles` contain core
`rgb_u8` and `id_u8` arrays plus height/Alpha **edges only**. Native geometry
cannot be reconstructed from those core files alone. Current exported full
IDMap can support bounded classification windows after source/hash/axis checks.

Four native transport tiles under
`D:/yacs/work/lesson07-consumer-update-20261020` are approximately 95–149 MB
compressed each, so a serialized single-tile inspection is a plausible next
step. Their manifest identifies the `f741335d...` L06 source and October 20 consumer.
The subsequent independent source audit streamed the current final cache and
confirmed SHA-256 `f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24`;
all four tile hashes match their manifest and retained height/transform hashes.
Their height lineage is resolved; the newer pre-ID colour branch is not
admitted replacement geometry. Before coupling these heights to current IDMap,
verify PNG row orientation, exact pixel registration and visibility polarity.
The earlier exporter flips volume rows, so unverified direct raw-voxel-index
to PNG-row mapping is unsafe. Full roadside inventory, clearances and all-cliff
coverage are still outstanding; a small successful class does not close them.

Final producer validation: Python compilation and whitespace checks passed.
After defensive finite/version/lineage guards, the same bounded generator was
rerun successfully with producer SHA-256
`622e00ec6d612b35ee67e80549b180bc3af6339028e073164c9f580436dbbde0`.
Final outputs are in `D:/yacs/work/pegasus-cliff-detail-20261024-final`:
HIP `c5320ca42b5e9284a6c1969a805844eb17d15a8bf2cfd38058fa8c0dc87e3eb6`,
BGEO `1743475979a3f9d814a6ce55c81b260f2da2a8bbc0a17c1426394b4ffd42d246`.
Counts, bounds and displacement measurements match the earlier run. Final OBJ
bytes are identical to the visually inspected earlier OBJ. Independent OBJ
readback confirmed all 26,716 positions finite. Final fresh-process output
reload passed. This is local exact-producer proof; remote exact-SHA delivery
and full-route proof remain outstanding.

Lightweight native `ginfo` readback of transport tile `SaCalobra_Unified_0_0`
confirmed exactly two volumes, `height` and `visibility`, each 8129 × 8129 × 1;
66,080,641 samples per layer. Reported memory is 139.28 MB in its compressed
native representation (dense float32 arrays would require more). This supports
serialized native extraction feasibility. `visibility` must
be decoded according to the retained transport polarity, not treated as Alpha.

## Bounded strength comparison and geometric limits

The owner-authorized comparison keeps default strength 0.15 and exposes
`--strength` within 0…1.2. Values 0.6 and 1.2 are experiments on the same
component, not standards or full-route deployment settings. Both retain scale
0.1; the original example uses 0.01. The Labs documentation states that lower
scale means less repetition. This texture projection choice requires visual
calibration to the real surface and does not establish geological scale.

| Strength | Added displacement max / mean m | Output vertices → original surface max / P95 m | Source vertices → output max m |
|---|---|---|---|
| 0.6 | 0.314636 / 0.057772 | 0.414008 / 0.201482 | 1.692449 |
| 1.2 | 0.629193 / 0.115544 | 0.654597 / 0.378119 | 1.691098 |

Added Y displacement remains zero. Surface distances use native
[`xyzdist`](https://www.sidefx.com/docs/houdini/vex/functions/xyzdist.html)
at vertices in both directions, including original smoothing/subdivision and
reduction. They are not continuous Hausdorff distance or proof of contact with
the final Landscape. The approximately 1.69 m reverse maximum shows why the
small added displacement alone was insufficient geometry proof.

Both experiments cooked and freshly reloaded with producer
`395775b7a715236233431f7a962c908ef67b8fe9b516ec75b474a22f4a9ab4a9`.
Their folders are `D:/yacs/work/pegasus-cliff-detail-20261024-strength06` and
`D:/yacs/work/pegasus-cliff-detail-20261024-strength12`.
`Saved/pegasus-cliff-strength-comparison-20261024.png` shows the actual three
meshes with identical camera, projection scale and lighting. Inspection finds
stronger surface roughness but persistent smooth curtain-like macro forms.
Neither stronger setting is visually admitted; no automatic full refinement
rollout follows.

## Current FINAL road-adjacent extraction and full-route inventory

`--inventory` reads the pinned full six-part Ma-2141 source record, transforms
EPSG:25831 using `X=E-483650`, `Z=4409899.5-N`, and inventories current IDMap
windows. The parent independently checked this transform against four controls.
The current IDMap SHA is
`cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3`.
Independent comparison of 4096 samples in four distant retained core tiles
found zero mismatches for `PNG row=15999-j`; direct `row=j` was wrong.

Inventory: **555** nominal 128 m windows intersect the 500 m working corridor;
**178** windows intersect the explicitly experimental 64 m roadside band and
contain cliff code 191. Their whole-window cliff pixel count is **3,526,097**,
not exact corridor area. Windows are candidates; pavement exclusion, source
visibility and geological locality must still qualify actual placement.
Receipt: `Saved/pegasus-cliff-inventory-20261024/inventory.json`.

The selected high-mask window belongs to route part 3, center XZ `(-608,1184)`.
It uses current FINAL tile `SaCalobra_Unified_0_1.bgeo.sc`, SHA
`fc59fec6a03eeda70d32e57fa75787b7763e287cb26f69cee0f4451235ba42c5`.
Native HeightField Crop includes edge rounding and yields **258 × 258** samples,
first `(-672.250122,0,1248.250122)`, last `(-543.750122,0,1119.750122)`.
All 66,564 height and visibility samples were compared exactly to the original
native tile indices; they are unchanged. The window contains zero holes.

`--current-crop` adds an indexed `id` layer using the audited PNG orientation,
retains `height` and `visibility`, and runs the **original ID decoder**, with
`srcname1=id`, `dstname1=mask`, `id_layer=191`. No slope substitute is used.
The original extraction HDA produced **48,750 points / 46,541 primitives**,
without node warnings; fresh output reload passed. Initial output folder:
`D:/yacs/work/pegasus-cliff-current-roadside-20261024-native`.
This current-FINAL branch supersedes the base-only limitation for this window;
earlier base-component displacement trials remain separate evidence.

Final guarded current-source run: producer SHA
`c5a2e6521927651556ee08d62cca998bf14594e18d561e512fa565ecd8a2e5d2`,
folder `D:/yacs/work/pegasus-cliff-current-roadside-20261024-final`.
The original decoder's complete mask matched code-191 classification with
**0.0 maximum error**; all generated coordinates were finite. Final geometry
SHA is `234c9653f4cabc01fddbaaf51e42ff5ba09fc268e3be7e2edaab1d5ee64c7f4e`;
HIP SHA is `fcff4c13930f7d68f732a7439a28440fcfaef494b46b2cc2381454bec301b9fd`.
Fresh output disk reload passed again. No final source, road or UE asset changed.

The measured extracted BGEO is 443,088 bytes, source crop 186,102 bytes and HIP
250,342 bytes. Naively repeating the approximately 10-second process for 178
windows would take roughly 30 minutes; storage extrapolated from this high-mask
window is below 160 MB before logs/other evidence. These are planning estimates,
not performance proof. Reusing one verified tile per serial batch avoids
repeated tile reads. Actual full-window seam/overlap, clearances and empty/invalid
window handling must be established before executing a larger batch.

## Rock spires and overhangs

The owner clarified that “sople” means rock spires and overhangs. Existing
Pegasus lateral displacement supplies an overhang-capable mesh method, but
does not identify actual spire locations. PEG-07 Procedural Stone offers detail
of supplied base meshes; PEG-06 pile simulation is not a spire recipe.

[CAIB's protected-area description](https://www.caib.es/sites/espaisnaturalsprotegits/es/monumento_natural_del_torrent_de_pareis/)
and [IGME geological inventory BL001](https://info.igme.es/ielig/LIGInfo.aspx?codigo=BL001)
identify the local limestone karst, gorge and lapiaz context. They do not
provide a surveyed road-by-road inventory of individual spires/overhangs.
The [SideFX-hosted rock-formation tutorial](https://www.sidefx.com/tutorials/procedural-rock-formations-1/)
is explicitly stylized and is not adopted as a reconstruction recipe.
Regional geological evidence is known; exact local form footprints and source
silhouettes remain unknown. Randomly placing procedural pinnacles would not
fulfil the real Sa Calobra requirement.

## Current roadside component quality control (2026-10-24)

The current FINAL crop class 2 is an interior 339-face component (359 points),
X -638.75..-624.75, Y 571.56..584.90, Z 1220.25..1230.75 m.
The adapter now accepts this current extraction lineage and exposes `--class-id`
with a 1000-face bound. Original HDA remains unchanged on disk.

PEG-05 L03 06:29–06:46 describes blurring N for 200 iterations, while the shipped
HDA `attribblur2/attributes` is `P N`. The explicit `--normal-blur-only` control
sets N inside the candidate instance. Default retains the shipped graph. This
is a transcript-versus-project discrepancy, not an established fix.

Both controls used strength 0.6, scale 0.1 and subdivision 1. Original P N output
has 14,880 points / 16,921 faces; N-only has 14,964 / 16,921. Native vertex-to-source
maximum distances are 0.328018 / 0.365598 m; reverse distances 0.409391 / 0.350027 m.
First and second subdivision outputs have source distances 0.176273 / 0.181505 m.
The intermediate `blur_to_source` measurement (~15.08 m) is in the intentionally
warped Y projection space before `restore_y_pos`; it is **not terrain drift**.
Displacement Y delta relative to each same-graph zero-strength baseline is zero.

Evidence directories: `D:/yacs/work/pegasus-cliff-current-class2-pn-v2` and
`D:/yacs/work/pegasus-cliff-current-class2-n-v2`. Both native cooks and independent
output disk reloads passed; graph regeneration remains NOT RUN. P N producer
SHA is `78cda74f32d531e33a98a53624a68c3f15b432109b750e26af582b13493ee5aa`;
N-only producer is `1331b4a8c0cb5f2e974f143857db8c75b892e3e92f473fa068daa3b9968d8eb3`
(the intervening change corrects the N-only parameter name to `attributes`).

Actual fixed-camera CPU polygon preview:
`Saved/pegasus-cliff-current-comparison-20261024.png` compares extracted source,
zero displacement, P N and N-only. The extracted source already contains the
broad folds; subdivision smooths the facets. N-only does not restore a distinctly
rock-like macroform, and displacement introduces thin grit. This diagnostic
has no materials or UE lighting and grants no production visual acceptance.
No detailed full-route rollout follows from this comparison. Adjacent core/halo
seams, 5 m candidate road exclusion and sourced spire placement remain unverified.

## Adjacent raw-core trial: batch gate failed

Native `HeightField Mask by Geometry` subtracts a native Sweep ribbon of 10 m
width (explicit 5 m candidate half-band) before Convert HeightField. Native
Clip 2.0 clips four planes to the nominal 128 m core; each source crop has an
8 m halo. Official recipes: [Mask by Geometry](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_maskbyobject)
and [Clip](https://www.sidefx.com/docs/houdini/nodes/sop/clip.html). This is a
candidate exclusion band, not surveyed pavement width.

Outputs `D:/yacs/work/pegasus-cliff-core-2640-v1` and
`D:/yacs/work/pegasus-cliff-core-2740-v1` cooked with producer
`f303ddd0fb0f05265eb106bd390fa4d0ff431336c94211c7343c2c4d92416527`.
Both native 290-square source crops preserve every height/visibility value.
There are 9,860 overlapping height samples, all exactly equal. However, extracted
boundary sets contain 137 versus 167 points, with 18/48 unmatched at millimetre
rounding. The local original flow/split/mask context does not yet produce matching
independent cores. **Full-route independent-window batch is not admitted.**

The selected components lie at least 55.73 / 41.35 m from the registered route,
so these two windows do not exercise the 5 m mask. Zero vertices inside 5 m here
is not proof of effective road exclusion. Native vertex distance is not a
triangle intersection test. Measurement is retained in
`Saved/pegasus-cliff-two-core-proof.json`. Next prerequisite is a genuinely
road-intersecting source window and a shared/global flow-mask context, with
matching extracted seam geometry; no artificial seam cover was added.

The road-intersecting core (30,38), `pegasus-cliff-core-3038-v1`, additionally
proved nominal 10 m ribbon insufficient: minimum vertex distance 4.502901 m,
780 vertices inside the required 5 m half-band. This is a measured failure,
not acceptance. The subsequent `--pre-flow` trial uses PEG-05 L02 01:56–04:27
raw extraction, bypassing only `blast2` (`@flow>0.5`) from the later optional
flow split. A 12 m candidate raster ribbon is under test for conservative
5 m final clearance; final polygon checks remain required. The guarded route
inventory now verifies original source bytes, six finite parts / 522 points,
and full 500 m corridor containment inside the enumerated grid; it reproduces
178 candidate windows and 555 working-corridor windows.

Pre-flow results: the adjacent core boundaries match 169/169 points at 1 mm
quantization, with zero unmatched. The road-intersecting core (30,38), using
12 m projected ribbon, has 39,094 actual output polygons; independent planar
polygon-to-registered-route distance is at least 5.5015165367 m, with zero
polygons inside 5 m. This validates a conservative raster margin for that test,
not a general constant. Every batch core must independently satisfy the same
5 m polygon clearance and matching neighboring edge sets. Failed windows stop
the batch; they are not silently accepted. Evidence:
`Saved/pegasus-cliff-preflow-seam.json` and
`Saved/pegasus-cliff-preflow-clearance.json`.

The `--batch <guarded inventory> --otls <original directory> --output <new directory>`
mode serializes native processes. Each window uses 8 m source halo, original
pre-flow extraction, 12 m candidate raster ribbon and native Clip core. It checks
all output polygon footprints against the real registered road, neighboring
boundary vertices, finite geometry, native source samples and an independent
fresh output disk reload. `batch.json` checkpoints completed validated cores;
create `PAUSE` inside the batch output to pause before the next window. The
manifest never grants production admission. This is raw source geometry only;
flow splitting/detail, spires/overhangs and UE delivery remain separate stages.

Batch producer `ece78990c3ed57138441e4065e899d0060df6ce76f1a2b1169c878034a794aa5`
is frozen in `Saved/pegasus-cliff-producer-ece78990.py`. The first six cores passed
source, finite geometry, complete planar polygon clearance and fresh output
reload checks. Boundary checks currently compare quantized vertex sets; this
proves aligned boundary points, **not boundary edge connectivity or a watertight
manifold**. Audit identified eight grid-crossing windows whose halo cannot fit
one transport tile: (22,31), (23,31), (24,31), (25,31), (28,31), (29,31),
(31,37), (31,38). The existing producer fails closed there. A native
[HeightField Tile Splice](https://www.sidefx.com/docs/houdini/nodes/sop/heightfield_tilesplice.html)
operation on small pre-cropped source pieces is being verified before those
windows can be included. No full 16k terrain recook is authorized or needed.

Native boundary proof is now available at
`D:/yacs/work/pegasus-cliff-boundary-2231-v1`. The installed node type is
`volumesplice`; the documentation name `heightfield_tilesplice` is not a valid
createNode type in 22.0.466. Native Crop must use Intersect (`cropmode=2`) before
joining. Replace mode pads outside source bounds and is not an acceptable join
input. The verified boundary test preserves 46,980 + 121,800 source samples,
then all 168,200 joined height/visibility samples exactly, with no uncovered
voxels. Original pre-flow extraction produces 27,946 points / 26,940 polygons.
This separate proof used scratch producer
`318852885e42ce0cfbebc28b3741862320b8b69636b009e438015b8021d7f198`.
The next publication candidate is being formatted and reviewed separately;
the active batch producer remains immutable and its completed cores are retained.

## Resumed full-route raw extraction

The original batch stopped after 32 admitted checkpoints when decimal-rounded
boundary sets disagreed at core (21,27). Inspection found 42 points on each side,
with maximum bidirectional displacement only 0.000120204 m. Values straddled a
rounding bin; the intended 1 mm tolerance was not exceeded. The new validator
uses actual boundary-edge endpoint pairs, a bijective correspondence and a
measured maximum endpoint distance <= 0.001 m. It no longer treats decimal bins
as geometric distance. This validates matching seam edge connectivity at the
stated tolerance; it does not assert global closed-manifold topology.

Producer `c5b268c3fa7ff70b4992a486152eeef259d3267046da51dd928b24bbbf7b7d16`
passes Ruff, compilation and whitespace checks. Its fresh native joined-source
proof is `D:/yacs/work/pegasus-cliff-boundary-2231-final`; the source and joined
samples remain exact. Overlapping source tiles must agree in value, and native
join index positions must agree within 1 mm, or the adapter fails.

Batch V2: `D:/yacs/work/pegasus-cliff-raw-route-20261024-v2`, started with
`--reuse-batch D:/yacs/work/pegasus-cliff-raw-route-20261024-v1` and the guarded
inventory `Saved/pegasus-cliff-inventory-20261024-guarded/inventory.json`.
Reused ECE checkpoints are hash-bound to their original receipts, HIP and fresh
reload evidence, then independently revalidated for complete projected polygon
clearance and boundary-edge correspondence. Each V2 manifest entry records its
actual native producer and output directory; historical geometry is not claimed
to have been generated by C5B. Source tile boundary windows use the proven native
intersect-crop / Volume Splice path. Native processes remain serialized.

## Source lattice precision and V3 status

V2 stopped at 35 validated cores: one boundary point differed by 1.328 mm in
height, while point/edge counts matched. Native Crop introduced roughly 0.12 mm
XZ position noise; clipping a steep triangle amplified that to a height seam.
The source adapter now reindexes converted source points onto the admitted
0.5 m XZ lattice before clipping. It measures maximum Euclidean coordinate
change <= 1 mm and enforces exactly zero Y change. This is explicit coordinate
registration, not bit-identical XZ or a terrain-detail operation. Original
sample heights and visibility remain exactly preserved.

Producer `5636169a61819c976c1956cf7f62606e1de9c4bac9e956a233fdef0b8315d856`
passed two fresh native controls at (24,26)/(24,27): 226 boundary points on each
side, maximum seam distance exactly zero. Maximum input registration movement
was submillimetre; Y delta was zero. Evidence:
`D:/yacs/work/pegasus-cliff-lattice-24-26-v1`,
`D:/yacs/work/pegasus-cliff-lattice-24-27-v1`, and
`Saved/pegasus-cliff-lattice-seam-proof.json`.

Current batch V3 is `D:/yacs/work/pegasus-cliff-raw-route-20261024-v3`.
At this publication checkpoint 35/178 cores were validated, including 32
explicitly inherited ECE cores and three new producer cores; the batch is in
progress. The live `batch.json` owns subsequent measured progress. Earlier
outputs and stopped manifests remain retained; no full-route completion is
claimed at this checkpoint. Native processes are serialized with road work.

## Source-supported overhang research

No actual geographically verified overhang or rock-spire geometry has yet been
proved. Original PEG-05 lateral displacement can create non-heightfield forms,
but the measured controls show folds and grit, not verified local rock anatomy.
Current heightfields cannot encode multiple heights at one horizontal position.

The retained original `PNOA_2024_BAL_483-4409_H31_NPC03.laz` has 7,423,640 points,
LAS format 8, millimetre integer scales and EPSG:25831 horizontal coordinates.
A read-only 40 m box E483000..483040 / N4408655..4408695 around the representative
current cliff contains 11,335 returns: classes 1=21, 2=2969, 3=4952, 4=2979,
5=398, 7=16, none withheld. These are observations, not an overhang inventory;
vegetation dominates, so surface reconstruction must not interpret every return
as rock.

Official supported workflow is [Lidar Import](https://www.sidefx.com/docs/houdini/nodes/sop/lidarimport)
(LAS/LAZ, real64 positions and metadata-only modes), then
[Point Cloud Normal](https://www.sidefx.com/docs/houdini/nodes/sop/pointcloudnormal.html)
and [Point Cloud Surface](https://www.sidefx.com/docs/houdini/nodes/sop/pointcloudsurface.html)
for an observed surface with oriented normals. Local propagation requires dense,
consistent neighborhoods; it cannot prove that missing wall samples exist.
[Triangulate 2D](https://www.sidefx.com/docs/houdini/nodes/sop/triangulate2d.html)
projects points to a plane and is unsuitable as a general overhang reconstruction.
No new LiDAR mesh cook, invented spire placement or full-route overhang claim
follows from this research.

## Native Unreal diagnostic for the existing detail component

The parent exported retained CURRENT class 2 / original P N / strength 0.6 through
the native FBX ROP. Export receipt:
`Saved/cliff-native-export-20261024/receipt.json`; FBX SHA-256
`180eb016ae608091ba5d79ae3a5ad1570c27e9df8e44bbd2233c421ff9c9b354`.
Source BGEO SHA remains
`625427c85d1840afe8b075f20ccf619150769aaab88ea1b3b7b9c344ce294f22`.
Native UE readback (`Saved/ue-cliff-readback-20261024.json`) reports 14,880
vertices and 29,311 triangulated faces. Centimetre bounds agree with the
Houdini metre bounds after axis/unit mapping to approximately 0.004 cm.
This proves native export/import and measured geometry bounds for that component.

The isolated front-facing diagnostic was temporarily moved +300 m, with actor
bounds verified. `Saved/ue-cliff-isolated-reverse-preview-20261024.png` was viewed
by parent and procedural-world reviewer: the result is a smooth, thin folded
sheet. It is not a finished cliff or verified rock spire. The opposite view
showed culled backfaces; the original-location camera was inside terrain, so
that capture was not suitable for visual acceptance. No material treatment was
used to conceal the geometry finding.

Parent reports all three temporary preview actors removed successfully, camera
restored and no map save. This is an isolated native diagnostic, not admitted
world placement, collision proof, full-route delivery or owner visual approval.

The parent saved only the diagnostic static-mesh asset
`/Game/Generated/YACS/RoadCliffCandidate_20261024/SM_Pegasus_CurrentCliff_Class2`.
Its `.uasset` disk SHA-256 is
`d214d6c3394ab2694e1518d98a3ae8a91b9be94ca10abd5c9799fce40ea932fb`;
receipt: `Saved/ue-cliff-asset-save-20261024.json`.
The exact measured maximum bounds difference is 0.00341796875 cm. A fresh UE
process reopen has NOT RUN. All preview actors were removed and the map was
not saved; asset persistence does not imply world placement or visual acceptance.

## Exact LF publication producer

Publication snapshot `Saved/pegasus-cliff-final-lf.py` has SHA-256
`224078f9ef490ccf2b7d574634d5c24c6dcfe7588abf07897346949af7a52bfd`.
It is byte-for-byte the running `5636169...` producer with CRLF normalized to
LF, required by the repository. The running batch file remains unchanged until
its process exits; per-core evidence continues to name its actual producer.
The publication snapshot independently passed fresh native cooks and output disk
reloads for (24,26), (24,27), and the joined boundary (22,31), all with exact
224078f9 producer hashes in their receipts. Graph regeneration is NOT RUN.

Evidence directories: `D:/yacs/work/pegasus-cliff-lf-proof-24-26`,
`D:/yacs/work/pegasus-cliff-lf-proof-24-27`, and
`D:/yacs/work/pegasus-cliff-lf-proof-22-31`.
Independent geometry summary: `Saved/pegasus-cliff-final-lf-proof.json`.
The precision pair has 226/226 seam points with zero nearest seam distance.
All 47,777 / 40,906 / 26,940 projected output polygons respectively exceed the
5 m required clearance, with minima 5.518379674 / 5.507545111 / 25.651084851 m.
Maximum lattice registration movements are 0.000122070313 / 0.000172633492 /
0.000244259805 m; Y remains unchanged. Joined source samples remain exact.
At this publication checkpoint V3 has 49/178 validated cores and is resumed;
this is not a completion claim. Ruff and Python compilation pass for the LF
snapshot. Historical ECE/C5B/563 receipts are retained with their true identities.

## Texture-scale control and 3D clearance limitation (2026-10-24)

PEG-05 L03 05:03-05:11 addresses overly small texture tiling by setting scale
0.01. The [official Labs Triplanar Displace documentation](https://www.sidefx.com/docs/houdini/nodes/sop/labs--triplanar_displace.html)
confirms that a lower value enlarges the projected pattern. A separate retained
adapter `Saved/pegasus-cliff-scale001.py`, SHA-256
`b1e2c577d3a8cc2a62869d6ff457b49c2a01da531d004331f636ad7272d75ab6`,
changes only both recorded/applied scale literals from 0.1 to 0.01 relative to
the LF producer. The running batch producer remains immutable.

The CURRENT class-2 control retains strength 0.6, subdivision 1, the original
boundary mask, P/N blur, CC0 maps and Y restoration. Output is retained at
`D:/yacs/work/pegasus-cliff-current-class2-scale001`: 14,954 points and 16,921
polygons, BGEO SHA-256
`1d3e69e19fe51d07e53121fb0aa8dea1ba5bacd72be23b2e0f240995c0502ad4`.
Matched pre-reduction displacement max/mean is 0.311958 / 0.039763 m; Y delta
is zero. Vertex-to-source maximum is 0.335671 m; reverse maximum 0.409395 m.
Fresh-process output disk reload passed; graph regeneration was NOT RUN.
`Saved/pegasus-cliff-scale001-comparison.png` uses actual exported polygons,
identical orthographic camera and flat CPU lighting for source, scale 0.1 and
scale 0.01. Larger projection removes much of the fine grit but retains smooth
folded-sheet forms. It does not establish a finished cliff or surveyed spire,
and is not admitted for rollout. Tutorial strengths 10/15 were not adopted.

The raw 178-window route candidate uses a conservative **2D** road exclusion.
It is not a production 3D clearance contract: a tunnel roof or natural overhang
above the road can share its XY footprint and would be incorrectly removed by
this rule. A road diagnostic reported a steep DTM transition on part 3, edges
280-286; tunnel interpretation remains under investigation. World admission
requires an actual road elevation/profile and 3D road-volume clearance before
retaining or removing overhanging rock. The current raw batch remains an
explicit candidate/history layer, not full-world geometry acceptance.
## Raw batch paused after input diagnosis

V3 was deliberately paused at a completed window boundary: **92 / 178** validated
candidate cores, **86 not generated/admitted**, last core `(27,36)`. Six of the
eight cross-tile windows passed native source/splice checks. Full-batch PASS is
not claimed. The reason is the unresolved real-road profile, 3D clearance and
visual-detail quality, not a relaxation of validation thresholds.

The original pause was session `95522`, PID `36940`. After checking the exact
command line, `PAUSE` marker and absence of native children, that owned process
was terminated. Exact producer `5636169...` is retained at
`Saved/pegasus-cliff-producer-5636169.py`; verified LF `224078...` remains at
`Saved/pegasus-cliff-final-lf.py`. The owned script now contains the LF recovery
adapter below. No background generation remains.

## Checkpoint-only recovery verification

The final recovery producer is
`b5b6e28d406269d0786924e753dbd29d86539d90ac704f35219dc45e683ef4b6`.
`--resume` validates the existing V3 prefix into a new evidence directory; it
**does not generate the remaining windows**, recook terrain, or amend original
receipts. It pins the original inventory, current ID image, source manifest and
all four native tile hashes; checks route source, per-core ECE/563 producer,
window/configuration, HIP/BGEO hashes and bound prior reload; then loads BGEO
natively into fresh OBJ files and repeats actual projected-polygon clearance
and edge endpoint bijection at the unchanged 5 m / 1 mm thresholds.
The internal `--resume-native` helper alone is only file readback, not full
source/configuration validation. Python 3.12 supplies existing Shapely; Houdini
22.0.466 Python 3.13 performs the serialized native readback without a HIP cook.

Reproducible validation command (choose a new output directory on each run):

```powershell
$env:HOUDINI_OCL_DEVICETYPE = 'CPU'
python scripts/houdini/pegasus_cliff_candidate.py --batch Saved/pegasus-cliff-inventory-20261024-guarded/inventory.json --resume D:/yacs/work/pegasus-cliff-raw-route-20261024-v3 --output D:/yacs/work/pegasus-cliff-resume-validation-20261024
```

Exact final-producer validation passed **92 / 92 retained checkpoints**, totaling
1,919,597 polygons; minimum planar clearance 5.501383146 m, maximum matched
boundary endpoint delta 0.000244 m. The original generation target remains
178, with 86 remaining NOT RUN. Evidence is
`D:/yacs/work/pegasus-cliff-resume-validation-20261024/batch.json`; it binds
original V3 manifest SHA-256
`99f563818117d8724c3388e0da90f323de15010e548a9839c9e99e95e802dde9`.
Ruff format/check passed; independent read-only audit found no blocking defect
for this known checkpoint. This is recoverability proof, not a corrected road
profile, production clearance, full-route completion or visual acceptance.
