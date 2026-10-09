# Road-First: source-bound window 0112 review

Work item: [#459](https://github.com/karnalooch/YetAnotherCyclingSim/issues/459), under [#457](https://github.com/karnalooch/YetAnotherCyclingSim/issues/457).
Authority: [World Building Bible](../../WORLD_BUILDING_BIBLE.md). No production authoring, material changes or source-road changes.

## Exact target

`reviewed-VIAL_TR70190001272-1-interval-24-0` is the 53.18931558128704 m road window whose frozen CUT manifest reports 11.698235723168352 m maximum cut. This is not the old `extreme_cut_case` at interval 01287/66. The historical native road artifact is 11291895548, capture c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6, run 37170332840.

The later original TPP survey maps this source ID to **window-0112**, with four stations viewed in both directions. Its original capture SHA is b1ea05b33b9f3208e7aeb6884f1a67792d9c6121, run 37800814004, artifact 11562342248. The copied frame index is Git blob 6aa5fa289231aff5823451977624c7ef87713d45 at reference bfbc48057b8b84d087a3685cd71972678a32d412. The reported survey length of about 53.30 m is not silently substituted for the earlier 53.19 m source length; camera/road positions must be checked before geometric correspondence is claimed.

## Bounded retrieval

The connector rejects the full 1,609,577,808-byte archive above its 512 MiB limit. `sa-calobra-window-evidence.yml` therefore downloads that one hash-pinned historical archive on a GitHub-hosted Linux runner and copies only eight exact original PNGs. It verifies archive size/SHA256, original index Git blob, source window ID, each frame hash/size/resolution and native readiness. No archive content is executed, images are not re-encoded, and existing evidence cannot be overwritten.

The workflow requires the repository owner, the dedicated `audit/459-window-0112-evidence` branch and an explicit `[window-0112-evidence]` push marker, or manual dispatch. It has read-only repository/Actions permission, no persistent credentials, no LFS checkout, no Unreal process and no self-hosted Windows runner. Six local negative/identity tests pass; remote run and original-PNG review remain pending until their receipts exist. Retire the retrieval trigger after this bounded review rather than adding an always-running pipeline.

## Required review

Inspect the uphill cut face, asphalt-to-shoulder edge and shoulder-to-ground tie-in at all four stations in both directions. Compare source sections and native contact receipts; zero sampled penetrations do not prove the absence of a visible seam or continuous collision. Do not deform the road, cut the mountain or generate new cliffs solely because a historical CUT maximum is large. Keep the accepted road tag, v8 cliffs, A/B/C/D/U bands and independent PCGEx review tags intact.
