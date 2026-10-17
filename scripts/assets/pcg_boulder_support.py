"""Sampled vertical fitting diagnostics; never terrain or placement admission."""

import math
from numbers import Real


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Sample heights must be finite real centimetres")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Sample heights must be finite real centimetres")
    return value


def solve_support(samples):
    """Fit only root Z to finite sampled vertical mesh intervals, in cm.

    For each sample, bottom gap is root + bottom - ground. Thus the highest
    root with every sampled bottom gap <= 0 is min(ground - bottom). The
    nonpenetrating lower bound is max(ground - bottom); their difference is
    the embedding required by the sampled zero-air objective. No margin or
    tolerance is inferred, and unsampled geometry remains unverified.
    """
    records = []
    for sample in samples:
        bottom, top, ground = (
            _finite(sample[key]) for key in ("bottom_z_cm", "top_z_cm", "ground_z_cm")
        )
        if top < bottom:
            raise ValueError("Sample top must be at or above bottom")
        records.append((bottom, top, ground))
    if not records:
        raise ValueError("At least one support sample is required")
    offsets = [_finite(ground - bottom) for bottom, _, ground in records]
    root = min(offsets)
    nonpenetrating = max(offsets)
    embedding = _finite(nonpenetrating - root)
    fitted = []
    for (bottom, top, ground), offset in zip(records, offsets):
        # Subtract offsets rather than re-add large absolute heights: preserves
        # the exact <= 0 sampled inequality without a numerical tolerance.
        gap = _finite(root - offset)
        exposure = max(0.0, _finite((top - bottom) + gap))
        fitted.append(
            {
                "bottom_gap_cm": gap,
                "penetration_cm": -gap,
                "exposed_top_cm": exposure,
            }
        )
    exposure = [sample["exposed_top_cm"] for sample in fitted]
    exposed_count = sum(value > 0 for value in exposure)
    if not exposed_count:
        raise ValueError("All sampled mesh intervals submerged; diagnostic rejected")
    return {
        "status": "SAMPLED_VERTICAL_FIT_DIAGNOSTIC_ONLY",
        "placement": False,
        "continuous_support_verified": False,
        "root_nonpenetrating_cm": nonpenetrating,
        "root_zero_sampled_air_cm": root,
        "required_embedding_cm": embedding,
        "sample_count": len(fitted),
        "exposed_count": exposed_count,
        "penetrating_count": sum(sample["penetration_cm"] > 0 for sample in fitted),
        "max_penetration_cm": max(sample["penetration_cm"] for sample in fitted),
        "exposure_min_cm": min(exposure),
        "exposure_max_cm": max(exposure),
        "exposure_mean_cm": math.fsum(value / len(exposure) for value in exposure),
        "samples": fitted,
    }
