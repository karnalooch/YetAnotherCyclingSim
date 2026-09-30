# YACS Performance Budgets

**Status:** active policy; values evolve only through measured, reviewed changes  
**Reference hardware:** project reference PC, RTX 2070 SUPER class GPU  
**Reference presentation target:** 1920×1080 / 60 FPS

## Budget model

60 FPS provides a hard frame interval of approximately **16.667 ms**.

YACS distinguishes:
- **hard acceptance budgets** — a proof fails when the established stage contract is exceeded;
- **development warning budgets** — earlier warnings that preserve headroom for later systems;
- **diagnostic watch metrics** — recorded and trended until enough data exists to lock a meaningful threshold.

A warning is not a failure. It means the current stage is consuming headroom that later stages are expected to need.

## v1.0 budgets

The Stage 3G environment proof keeps its already-established hard acceptance contract:

| Metric | Hard Stage 3G acceptance |
|---|---:|
| Frame p95 | <= 16.667 ms |
| GPU p95 | <= 16.667 ms |
| Frames above 16.667 ms | <= 5% |
| Missing required GPU timing | FAIL |

v1.0 adds provisional development warnings:

| Metric | Development warning | Rationale |
|---|---:|---|
| Frame p95 | > 14.0 ms | preserve margin for rider, animation, weather and later presentation |
| Draw p95 | > 13.0 ms | surface render-thread pressure before it reaches frame budget |
| GPU p95 | > 14.0 ms | preserve graphics headroom |
| Game p95 | > 8.0 ms | surface gameplay/animation pressure early |
| RHI p95 | record/watch | do not lock an arbitrary threshold before representative measurements |

These warning values are deliberately provisional. They must not be silently tightened or relaxed to make a pull request pass.

## Stage 3G R5 measurement policy

R5 keeps the same hard product target and uses the existing warnings as the headroom target.

Additional R5 rules:

- **base-rendered performance is authoritative** for acceptance;
- Frame Generation displayed/generated FPS is recorded separately and cannot make a failing base-rendered result pass;
- average FPS and **1% low** are required trend metrics, but do not replace Frame/GPU percentile gates;
- hitches and VRAM become required R5 evidence when instrumentation is available, even though final locked thresholds remain a later framework responsibility;
- Native/TSR is retained as a vendor-neutral comparison baseline;
- DLSS/FSR/XeSS results must use the same scenario, resolution, preset and exact-SHA provenance when compared;
- dynamic-resolution runs must record actual screen percentage / internal resolution behavior;
- visual artifacts can reject a faster result;
- a threshold may move only through an explicit reviewed budget change, never as part of an optimization PR whose result missed the existing gate.

R5 optimization goal: preserve enough margin that representative Frame/GPU p95 remains around or below the **14 ms development warning** where practical. This is a headroom target, not a new hidden hard gate.

## Baseline deltas

Every framework version should prefer comparison against an accepted exact-SHA baseline.

At minimum record:
- absolute p95 delta in milliseconds;
- percentage delta;
- whether the limiting timing domain changed;
- whether a hard or warning threshold changed state.

Large regressions require explanation even when the absolute hard 60 FPS gate still passes.

## Stage-specific budget growth

### Stage 5 / v1.1
No new expensive world/rendering system is expected. HUD/session work should not materially consume the preserved world headroom. If a HUD change produces a meaningful CPU/GPU regression, measure and fix it rather than raising world budgets.

### Stage 6 / v2.0
Lock rider/animation budgets only after representative near/medium/far scenarios exist. The target is to allocate rider presentation inside the existing frame budget, not to redefine 60 FPS.

### Stage 7 / v2.1
Introduce measured RAM/VRAM, hitch and streaming budgets from representative traversal data. Do not invent fixed MB/GB or hitch thresholds before baseline evidence exists on the reference machine.

### Stage 8 / v3.0
Worst-weather scenes must fit the same final 60 FPS product target. Weather may consume reserved headroom, but it does not receive permission to redefine the target.

### Stage 10 / v4.0
Before final MVP acceptance, freeze explicit packaged-build budgets for:
- Frame/Game/Draw/RHI/GPU;
- RAM/VRAM peaks;
- hitch percentiles / unacceptable stalls;
- streaming continuity;
- first-use/PSO stutter.

Those final numbers become release criteria and require an explicit reviewed change to move.

## Anti-patterns

Do not:
- optimize only average FPS;
- call an asset safe because its triangle count is low;
- change a threshold after a regression merely to restore green CI;
- compare results from different resolutions/hardware as if they were one baseline;
- use editor-only numbers as the final Stage 10 packaged-build acceptance;
- hide a hot Draw/Game/RHI domain behind an acceptable GPU number;
- report Frame Generation output FPS as if it were real rendered FPS;
- compare upscalers at different uncontrolled scene states, seeds or presets;
- accept an upscaler solely because average FPS increased while 1% low, hitches or image stability regressed.
