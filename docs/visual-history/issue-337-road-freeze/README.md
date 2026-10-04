# Issue #337 — accepted road appearance checkpoint

The owner accepted the current road and Nus de sa Corbata appearance on
2026-10-04 and requested that it be frozen and protected.

- Accepted implementation: `c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6`.
- Protected reference tag: `visual/337-road-accepted-2026-10-04` (never move or replace).
- [PR #338](https://github.com/karnalooch/YetAnotherCyclingSim/pull/338) remains Draft.
- [CI run 37170332840](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37170332840): SUCCESS; native Automation 26/26 PASS.
- [Freeze receipt](freeze.json) records SHA-256 and sizes for six original native
  3840 x 2160 evidence images retained in this repository.
- [Capture proof](terrain-capture-proof.json) identifies all 15 native cameras;
  [handoff proof](owner-handoff-proof.json) identifies the interactive editor result.

The accepted geometry, shoulders, asphalt, bridge and terrain appearance are the
baseline for future work. Do not silently regenerate or alter them. Any intentional
change needs its own scoped review against this reference; preserve this checkpoint.
Existing caches and materialized Unreal/LFS assets must remain retained.

This records feature-specific human visual acceptance. It does not claim collision,
rideability, measured gameplay performance, a merged implementation or full-stage
Visual History completion. The canonical 1200 / 4900 / 8000 m triptych closeout is
still pending; these feature cameras are not substitutes for those stable cameras.
No BEFORE/AFTER image has been invented or copied to imply a separate capture.
The next technical checkpoint is performance on the frozen implementation SHA.
