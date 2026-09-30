"""Pure-lateral corner limit for Stage 4B-C.

This layer consumes:
- route-derived CornerContext from Stage 4B-A;
- explicit SurfaceGripPolicy from Stage 4B-B;
- a caller-owned base tyre friction coefficient.

It applies local cross-slope/banking to the pure-lateral cornering limit.
Braking is intentionally absent here; the shared longitudinal+lateral grip
budget belongs to Stage 4C.

Route sign convention:
- positive curvature turns toward +D (rider right);
- positive cross-slope rises toward +D.

Therefore a supportive bank has opposite signs for curvature and cross-slope.
The derived support angle is:
    support_angle = -sign(curvature) * cross_slope
so positive support_angle helps the turn and negative support_angle is
off-camber/adverse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .corner_context import CornerContext
from .cornering import effective_friction_coefficient
from .grip_policy import SurfaceGripPolicy
from .model import STANDARD_GRAVITY_MPS2
from .validation import _positive

__all__ = [
    "CornerLateralLimit",
    "corner_lateral_limit",
]


@dataclass(frozen=True, slots=True)
class CornerLateralLimit:
    surface_id: str
    wetness: float
    grip_multiplier: float
    effective_friction_coefficient: float
    bank_support_angle_rad: float
    lateral_acceleration_limit_mps2: float
    maximum_speed_mps: float


def corner_lateral_limit(
    context: CornerContext,
    grip_policy: SurfaceGripPolicy,
    base_friction_coefficient: float,
) -> CornerLateralLimit:
    """Return the pure-lateral physical corner limit for one context.

    No safety/recommended-speed margin is applied. A later presentation or
    assist layer may choose a lower target, but this function exposes the
    deterministic physics limit only.
    """

    if not isinstance(context, CornerContext):
        raise ValueError(
            f"context must be a CornerContext, got {type(context).__name__}"
        )
    if not isinstance(grip_policy, SurfaceGripPolicy):
        raise ValueError(
            f"grip_policy must be a SurfaceGripPolicy, got {type(grip_policy).__name__}"
        )
    if not context.has_corner:
        raise ValueError("corner lateral limit requires a context with a corner")
    if not math.isfinite(context.effective_radius_m) or context.effective_radius_m <= 0.0:
        raise ValueError(
            "context effective_radius_m must be finite and greater than zero"
        )
    if not math.isfinite(context.signed_curvature_per_m) or context.signed_curvature_per_m == 0.0:
        raise ValueError(
            "context signed_curvature_per_m must be finite and non-zero"
        )
    if not math.isfinite(context.cross_slope_angle_rad):
        raise ValueError("context cross_slope_angle_rad must be finite")

    base = _positive(base_friction_coefficient, "base_friction_coefficient")
    surface_grip = grip_policy.resolve(context.surface_id, context.wetness)
    effective_mu = effective_friction_coefficient(base, surface_grip.grip_multiplier)

    turn_sign = 1.0 if context.signed_curvature_per_m > 0.0 else -1.0
    support_angle = -turn_sign * context.cross_slope_angle_rad

    sin_bank = math.sin(support_angle)
    cos_bank = math.cos(support_angle)
    numerator = sin_bank + effective_mu * cos_bank
    denominator = cos_bank - effective_mu * sin_bank

    if numerator <= 0.0 or denominator <= 0.0:
        raise ValueError(
            "bank/friction combination is outside the supported pure-lateral model"
        )

    lateral_limit = STANDARD_GRAVITY_MPS2 * numerator / denominator
    if not math.isfinite(lateral_limit) or lateral_limit <= 0.0:
        raise ValueError("derived lateral acceleration limit must be finite and positive")

    maximum_speed = math.sqrt(lateral_limit * context.effective_radius_m)
    if not math.isfinite(maximum_speed):
        raise ValueError("derived maximum corner speed must be finite")

    return CornerLateralLimit(
        surface_id=surface_grip.surface_id,
        wetness=surface_grip.wetness,
        grip_multiplier=surface_grip.grip_multiplier,
        effective_friction_coefficient=effective_mu,
        bank_support_angle_rad=support_angle,
        lateral_acceleration_limit_mps2=lateral_limit,
        maximum_speed_mps=maximum_speed,
    )
