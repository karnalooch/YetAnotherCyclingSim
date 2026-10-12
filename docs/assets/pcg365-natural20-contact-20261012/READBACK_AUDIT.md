# Natural20 contact: independent raw readback audit

Issue: #365. Milestone: M3. Role: proof-qa. Status: local diagnostic evidence only.

This document records an independent CPU replay of saved native contact samples.
It does not grant asset qualification, production scatter admission, owner visual
acceptance, an exact-head native build, or performance acceptance.

## Producer and reader identities

Runtime producer identity and audit reader identity are separate.

| Evidence | Identity |
|---|---|
| Run02 and run03 producer SHA | d0e76c6026befb82c3862d96f8f3b719cfb4d8ed |
| Frozen reader modules used for the final run02/run03 replay | natural20-contact03/scripts |
| Prebatch audit script SHA256 | cbb000626e7f35a5cce51fabf16a4c99572aefe7014bd70d5a8e1ae7dcff619a |
| Prebatch JSON SHA256 | cd98130392655fab12c7ba99154936bdaae9cfdb9162956b19d7fcb077268e41 |
| Final run04 producer SHA | 1a02ac21a7fb1dbc84364843e862b186a2ea0a18 |
| Final run04 frozen reader | natural20-contact04/scripts |
| Final run04 audit script SHA256 | b23eb25b7c490746b9bb9a4f22a939741e4be5f357ab9e03ddf5fed9dc123316 |
| Final run04 JSON SHA256 | 6f2686949b7dbeebee35c4a441a1526f181c60babaf8552bab114c9f25d0887a |
| Native binary provenance | Retained prebuilt dependency; not an exact-head native build |

Run roots:

- Run02: D:/yacs/work/pcg365/d0e76c6026befb82c3862d96f8f3b719cfb4d8ed/natural20-contact02
- Run03: D:/yacs/work/pcg365/d0e76c6026befb82c3862d96f8f3b719cfb4d8ed/natural20-contact03
- Run04: D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04

The run02/run03 audit read the preserved stages while the source worktree was
being changed for run04. It did not import the changing source worktree.
All four audited producer modules had identical bytes in run02, run03 and the
frozen run03 reader:

| Module | SHA256 |
|---|---|
| scripts/assets/pcg_boulder_support.py | 2ee74a9c3349babf5b6d4c39f768215cacc0137b6ffb1f64046b83ee0798fee2 |
| scripts/assets/pcg_rock_contact_policy.py | 4bfd12aca172a64940b49163bb0ecf221fac593e889028cdc8c88cd8a7b1bd5f |
| scripts/ue/sa_calobra_pcg_collection_contact.py | 83698a642774e7b522f79c2c82e02fb0304f5a1217b53b035e56e188f3f36d12 |
| scripts/ue/sa_calobra_pcg_rock_qualification.py | 219f5f7da59f695e2c5e1257a8e0b79f998919a2177950adae9a9e4e53d5bd5a |

## Replay method

The auditor uses the existing solve_support, evaluate, trial_policy and
refined_trial_policy functions. The existing measurement and complete helpers
are selected from the frozen producer module through its Python AST without
importing Unreal. The reader does not write bytecode, modify raw evidence,
launch Unreal, or change the contact policy.

For each saved grid it verifies:

1. Raw file SHA256 and byte length against the receipt.
2. A complete, unique 33 by 33 or 65 by 65 XY grid, partitioned into paired
   support rows and explicitly rejected rows; the existing conditional
   129 by 129 refinement layout remains supported.
3. Exact world XY equals candidate centre plus local mesh XY; finite local and
   world Z values, paired mesh intervals and mesh Z bounds are checked.
4. Slope recomputed from each saved ground normal, plus the maximum grid slope.
5. Every fitted row, root Z bounds, required embedding, penetration, exposure
   and zero positive sampled bottom gap.
6. The reconstructed measurement and the entire V1/V2 policy decision against
   the receipt, including reason order and numeric metrics.
7. Receipt SHA/action and actual completion-marker semantics. Missing process
   completion remains distinct from successful mathematical replay.
8. Stable receipt bytes throughout the audit.

The local mesh was measured with identity rotation and scale. Mesh bottom/top,
Landscape world Z, root Z, embedding and exposure are expressed in centimetres.
World XY is also expressed in centimetres. Slope is expressed in degrees.
No metre/centimetre conversion is introduced by the replay.

For each paired row, define offset = ground Z - local bottom Z. The highest
root Z satisfying zero positive sampled air gap is min(offset). The
nonpenetrating root bound is max(offset). Their difference is required
embedding. Exposure is max(0, top - bottom + root - offset). These equations
were independently checked against solve_support as well as against every
saved fitted row.

The raw replay checks recorded values. It cannot rerun or independently
authenticate an Unreal collision query; actual actor/component identity and
Landscape selection remain properties of the native producer and its other
proof gates. Continuous support between sampled rays remains unverified.

## Verification environment

Interpreter:

D:/yacs/engine/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe

Version: Python 3.11.8, matching the version recorded by the native Unreal log.
The audit runs with -B and sys.dont_write_bytecode enabled.

An initial replay with host Python 3.12.10 produced tiny exact-equality
differences in recomputed slopes. One observed difference was
-1.4210854715202004e-14 degrees: stored 40.40759220073931, recomputed
40.407592200739295. Repeating the replay with the matching bundled Python
3.11.8 produced zero discrepancies. No numeric tolerance, policy threshold or
receipt was changed to obtain this result.

## Run02 and run03 results

| Measure | Run02 | Run03 |
|---|---:|---:|
| Batch receipts present | 5 | 10 |
| Batch processes with verified exit-zero markers | 4 | 9 |
| Recorded cases | 50 | 100 |
| Cases covered by exit-zero markers | 40 | 90 |
| Raw grid files replayed | 100 | 200 |
| Paired support rows replayed | 169,065 | 361,350 |
| Explicit rejected rows | 96,635 | 170,050 |
| Raw-to-receipt discrepancies under Python 3.11.8 | 0 | 0 |
| Recomputed PASS_SAMPLED_CONTACT_ONLY | 0 | 0 |
| Recomputed REJECTED | 50 | 100 |

Explicit rejected rows are distinct from rejected cases. Grid points outside
the sampled mesh footprint are recorded as paired mesh misses. They do not
demonstrate missing Landscape collision coverage for an existing mesh interval.

The run02 batch collection-contact-04 and run03 batch collection-contact-07
lack launcher-completed.json. The coordinator recovered process exit
-1073741819 for each. Their written measurements are retained and can be
replayed, but they are not clean process completion proof. Normal log closure
does not establish exit zero. The root cause of these access violations remains
unestablished.

No aggregate contact reload or terrain render was completed for these
prebatch runs. The mathematical agreement does not repair those missing gates.

### Rejection reasons

A case can have multiple reasons.

| Recomputed V1 reason | Run02 | Run03 |
|---|---:|---:|
| EXCESSIVE_LOCAL_SLOPE | 50 | 94 |
| EXCESSIVE_EMBEDDING | 50 | 100 |
| INSUFFICIENT_EXPOSED_HEIGHT | 50 | 100 |
| INSUFFICIENT_EXPOSED_RAYS | 50 | 99 |
| ROOT_NOT_CONVERGED | 41 | 77 |
| EMBEDDING_NOT_CONVERGED | 48 | 93 |

Run03 ranges across the 100 recorded cases:

| Metric | Minimum | Maximum |
|---|---:|---:|
| Maximum local slope, degrees | 5.877836180076455 | 53.8692453088667 |
| Required embedding / mesh height | 0.5989543262056582 | 4.553849185138385 |
| Maximum exposed height / mesh height | 0.03391395047064237 | 0.5973476274824321 |
| Exposed paired-ray fraction | 0.0037652965171007216 | 0.8001336898395722 |
| Root refinement delta, cm | 0 | 35.05779580332455 |
| Embedding refinement delta, cm | 0 | 35.05779580332455 |

The frozen policy remains scale 1, yaw 0, tilt 0, local slope at most 10 degrees,
embedding at most 20 percent of mesh height, exposed height and ray fractions
at least 80 percent, zero positive sampled gap, complete sampled ground
coverage, and root/embedding convergence at most 0.1 cm.

These outcomes reject the measured mesh/point combinations under that policy.
They do not establish that each mesh is unusable at every possible location,
and do not authorize relaxed policy or changed terrain.

## Additional run02 identity checks

The independent read-only audit also found:

- 9 existing preparation/contact completion markers with matching producer SHA,
  action, exit zero and staged_bytes_unchanged true.
- 202 of 202 staged terrain packages matching their declared SHA256 and sizes.
- 20 saved mesh packages matching their declared SHA256 and sizes.
- 7 saved Material Forge/binding packages and 14 referenced Engine packages
  matching their declared SHA256 and sizes.
- Collection catalog SHA256
  3160143d74ba3e2af8b7033bfeb689ca0d3c29b33abb50a4e68c512e560d15bc.
- Terrain map identity before/after matching
  bf2b92945865e2307990b6d3da40095dfa0774d28affb32a1e42e55f288764dd,
  185,187,721 bytes.
- No missing /Game dependency LoadErrors found in the inspected run02 editor
  logs.
- Zero terrain-contact PNGs in run02.

Zen RPC 500 and DDC write warnings remained visible. Startup UnifiedError
self-test messages were not interpreted as a passing project test. These host
conditions were recorded without attributing the access violation to them.

## Run04: final raw replay

Status: raw replay PASS; aggregate process completion BLOCKED; render NOT RUN.

Runtime producer SHA: 1a02ac21a7fb1dbc84364843e862b186a2ea0a18.
The replay imported only the immutable staged run04 modules, using the bundled
Python 3.11.8 interpreter. The source worktree was not imported or changed.

The result is saved in contact_readback_final04.json. Its SHA256 is
6f2686949b7dbeebee35c4a441a1526f181c60babaf8552bab114c9f25d0887a.
The exact reader script SHA256 is
b23eb25b7c490746b9bb9a4f22a939741e4be5f357ab9e03ddf5fed9dc123316.

| Verified property | Run04 result |
|---|---|
| Execution mode | SINGLE_PROCESS_ALL_BATCHES |
| Actual contact process completion markers | 1 |
| All-contact completion | Exit 0, exact producer SHA, unchanged staged bytes |
| Inline batches | 10 in order, exactly 2 saved meshes and 5 points per mesh |
| Independent child markers | None; not permitted |
| Cases covered by genuine process completion | 100 |
| Raw grids replayed | 200 |
| Paired support rows replayed | 361,350 |
| Explicit rejected rows | 170,050 |
| Raw-to-receipt discrepancies | 0 |
| Recomputed policy outcomes | 100 REJECTED, 0 PASS_SAMPLED_CONTACT_ONLY |
| Aggregate reload receipt | Present, mathematically consistent |
| Aggregate reload process completion | BLOCKED_MISSING_COMPLETION |
| Terrain-contact render receipt / completion marker | Absent / absent |
| Terrain-contact PNGs | 0 |

The one contact marker is
proof/collection-contact-all/launcher-completed.json, SHA256
c46c0f4a2015d4fcb0d749b93ca79d251ee7964fcec4bd238fc53f7620ed6db6.
The reader checked it using the existing frozen verify_all_marker function.
The ten completed_batches in the JSON mean ten inline batches covered by this
one successful process; they do not mean ten separate successful processes.

Each inline result matches the parent catalog, contact request, terrain source
contract, before/after terrain file identity and Landscape transform. Mesh
partitions cover all twenty unique meshes. The full case matrix is twenty
meshes by five authenticated points. Raw SHA256/size, grid geometry, fit
arithmetic and complete V1 decisions match exactly. The parent loading barrier
is recorded complete. No mixed process layout or fabricated child marker was
found.

The existing solve_support and policy module hashes are unchanged from run03.
The run04 collection-contact module hash is
8d4344e727abe0d4f851d6b8c00aad41407c98ea7f5d66494d9a8b7d1da84551.
The qualification module hash remains
219f5f7da59f695e2c5e1257a8e0b79f998919a2177950adae9a9e4e53d5bd5a.

All twenty meshes have five REJECTED cases. Rejection counts and metric
ranges match the 100-case run03 summary above: slope 94, embedding 100,
exposed height 100, exposed rays 99, root convergence 77 and embedding
convergence 93. This agreement does not grant full asset qualification.

### Aggregate receipt without clean process completion

The aggregate receipt is
proof/collection-contact-reload/collection-contact-reload-receipt.json,
2,130,523 bytes, SHA256
65d0779d46a00383b2a5ae2b37e266e6798230d1ebc954b2068cd04ab06af1fa.
Its producer SHA, SINGLE_PROCESS_ALL_BATCHES mode, ordered 100 cases and
single hash-bound all-contact receipt reference were verified by the reader.

However, proof/collection-contact-reload/launcher-completed.json does not
exist. The coordinator reports Unreal process 8268 exited -1073741819 after
writing the receipt. The root cause of this access violation remains
unestablished. The saved receipt must not be described as a successful
fresh-reload process, and must not bypass the render completion prerequisite.

No render was run: there is no render receipt, no render completion marker and
no PNG. No claim of forty terrain-contact renders is valid for this run.
The accepted earlier studio images remain a separate type of evidence.

### Reproduction command

Run from the prepared scratch or durable copied audit script, with bytecode
disabled:

~~~powershell
& 'D:/yacs/engine/UE_5.8/Engine/Binaries/ThirdParty/Python3/Win64/python.exe' -B '<path-to-contact_readback_audit.py>' --root 'D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04' --source 'D:/yacs/work/pcg365/1a02ac21a7fb1dbc84364843e862b186a2ea0a18/natural20-contact04' --expected-producer-sha '1a02ac21a7fb1dbc84364843e862b186a2ea0a18'
~~~

The reader only reads evidence and prints JSON. The reported reader script
path changes when the script is copied; its content hash and the runtime
producer SHA remain separately recorded. This command does not launch Unreal.

## Scope and outstanding gates

No source, terrain, road, Base_DTM, georeferencing, accepted package or native
evidence file was changed by the proof auditor. Only its scratch audit script,
JSON results and this audit report were written.

Performance remains DEFERRED_AFTER_M3 with performance_pass: false. No FPS,
RTX 2070 result, owner visual signoff, production scatter admission or #365
completion is claimed.

The exact executed reader is preserved as `contact_readback_audit.py.gz` using
lossless gzip. Decompress it to a `.py` file before running the command above;
its decompressed SHA256 remains the recorded reader identity.
