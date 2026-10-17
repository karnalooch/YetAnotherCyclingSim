# Larger scanned rocks — #365 / M3 evidence

The [hash-bound manifest](evidence.json) contains source/preparation receipts,
native receipts and 40 unedited 1920x1080 review PNGs. Original FBX and raw ray
matrices remain hash-bound on the host; engine caches and full host logs are not
committed. Execution completion is separate from production qualification.

## Sources and geometry

Poly Haven CC0 originals: [Namaqualand Boulder 02](https://polyhaven.com/a/namaqualand_boulder_02)
and [Namaqualand Boulder 06](https://polyhaven.com/a/namaqualand_boulder_06).
South African provenance is not Sa Calobra geology evidence. Each file has one
named LOD0 object; no LOD merging. Original source bytes remain unchanged.

02's open boundary rejects the initial 10% height cut. A separate 12% underside
repair and disconnected-fragment selection retain two disjoint support contours.
The final decorative variant bakes half scale and a quarter turn into a separate
FBX. 06 retains its original size and 10% preparation. Native actor scale is 1.
Declared 5% planting depth counts within the same total embedding budget.

- 02 derived SHA256: `4573694aec533421f25b6d854a1fec24431a7a1034ddde1cee4e8837dee0503b`; 82,558 native triangles, about 1.25 m long.
- 06 derived SHA256: `d95cde17e6e6318e83ca0e60e4e5febee9438c0192978da6b7461ce8264b51b8`; 103,250 native triangles, about 1.21 m long.

See [source preparation](source-prepared-half-yaw.json). All earlier cut,
component, full-size and unrotated-half failures remain retained evidence.

## Contact measurements

Both point-3 source-cap alternatives reach DIAGNOSTIC_SUPPORT_PATCH_ONLY;
all unchanged V1 full-footprint decisions remain REJECTED. This is not asset
admission, continuous contact or physical stability proof.

02 uses 33-to-65 refinement with root/embedding deltas 0/0.066295 cm, total
embedding 6.762829 cm over height 38.836063 cm, exposed height 91.569171% and
exposed rays 98.258977%. Full/cap coverage is 2757/2757 and 1953/1953. Remaining
peripheral positive overhang gap is 20.693365 cm.

06 retains its initial 33-to-65 convergence failure. Its 65-to-129 deltas are
0.024237/0.048043 cm; embedding 5.669366 cm over height 58.646835 cm, exposed
height 94.462951% and exposed rays 100%. Full/cap coverage is 12776/12776 and
5322/5322. Remaining peripheral overhang gap is 50.458336 cm. Both maximum
slopes are 9.937148 degrees. Terrain is unchanged and no map was saved.

## Completed native series and renders

Exact code 43d158e0cbc43af087864ab6ecb850ed6545ba05 produced the first twelve
clean baseline/V1 actions and sixteen review PNGs. Code
39815d33190fe0fce10727e35d196081e6fc8d1a produced twelve clean actions in
large-shadow-baseline02 and large-shadow-detail03, with another sixteen PNGs.
Earlier 408383fe and large-shadow-baseline01 rock-reload processes failed with
access violation -1073741819 after log close; their missing completion markers
are preserved. A receipt does not override a failed process.

Forge V2 preserves selectable V1. Its fixed gain/fracture/pore/mineral/normal
parameters are 0.64/0.38/0.22/0.18/0.85; physical tile remains 4 m, ORM unchanged,
zero audited displacement. Final exact code d1903aa952da2f30c237c589e924f95a1b2d994a,
large-dynamic-detail01, completes six clean actions and eight GPU review PNGs.
The isolated directional-sun mobility-only lease preserves intensity, color,
rotation and shadow settings, then verifies original settings restored before
cleanup. No terrain, road, source map or canonical lighting was saved.

Final [02 view01](large-dynamic-detail01-namaqualand_boulder_02-boulder-low-angle-01.png)
and [06 view01](large-dynamic-detail01-namaqualand_boulder_06-boulder-low-angle-01.png).
Critical [02 view03](large-dynamic-detail01-namaqualand_boulder_02-boulder-low-angle-03.png)
and [06 view03](large-dynamic-detail01-namaqualand_boulder_06-boulder-low-angle-03.png).
Compare [02 baseline](large-shadow-baseline02-namaqualand_boulder_02-boulder-low-angle-04.png)
with [02 V2](large-shadow-detail03-namaqualand_boulder_02-boulder-low-angle-04.png),
and [06 baseline](large-shadow-baseline02-namaqualand_boulder_06-boulder-low-angle-04.png)
with [06 V2](large-shadow-detail03-namaqualand_boulder_06-boulder-low-angle-04.png).

## Visual decision and remaining proof

Parent reviewed all final views; independent audit reviewed all eight V2-pair
views. 02 has a natural angular silhouette and improved local seating, with
remaining central/rear undercuts. 06 still has a raised-looking rounded lower
edge in several views and is rejected for production scatter. Forge V2 adds
modest contrast; bright faces remain chalky. Sun mobility change did not establish
convincing ground-cast shadows. No visual PASS or regional asset admission.
Neither material nor shadow changes repair the recorded peripheral overhang.

The variants are reproducible diagnostic products. Future source-pose inspection
may choose a natural support face; no artificial base, plinth, hull fill or
terrain repair has been added. Placement/full qualification remain false,
qualified_assets is empty, native build NOT_RUN_PREBUILT_DEPENDENCY,
performance DEFERRED_AFTER_M3/false. Latest-road, continuous/render parity and
whole-M3 owner audit remain open; #365 and Draft PR474 remain open.

Local validation: 52 asset tests plus 7 candidate tests, Ruff and architecture
contract PASS. Docs guards and delivery CI are recorded separately from native
execution; do not relabel a documentation delivery head as a native run.


## Receipt storage, 2026-10-16

Oversized run receipts are stored as byte-preserving `.json.gz` files.
The [storage index](compressed-evidence.json) authenticates both the compressed
file and its exact decompressed original. Paths and hashes in `evidence.json`
describe the original captured bytes and remain unchanged. Read gzip before
checking those hashes; do not hash the compressed file as an original receipt.
No measured value, rejection, native status or producer identity was changed.
See [repository storage rules](../../evidence/JSON_STORAGE.md).
