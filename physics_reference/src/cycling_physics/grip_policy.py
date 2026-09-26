"""Deterministic surface + wetness -> grip policy for Stage 4B.

The policy owns no hidden "realistic" coefficients. Every surface rule is
explicit configuration. Wetness interpolates linearly between the configured
dry and fully-wet grip multipliers.

Grip multipliers are relative factors in (0, 1]. The tyre/base friction
coefficient remains a separate caller-owned input to the cornering model.
"""

from __future__ import annotations

from dataclasses import dataclass

from .validation import _clean_name, _closed_unit_interval, _positive_at_most_one

__all__ = [
    "SurfaceGripRule",
    "ResolvedSurfaceGrip",
    "SurfaceGripPolicy",
]


@dataclass(frozen=True, slots=True)
class SurfaceGripRule:
    surface_id: str
    dry_grip_multiplier: float
    fully_wet_grip_multiplier: float

    def __post_init__(self):
        object.__setattr__(self, "surface_id", _clean_name(self.surface_id, "surface_id"))
        object.__setattr__(
            self,
            "dry_grip_multiplier",
            _positive_at_most_one(self.dry_grip_multiplier, "dry_grip_multiplier"),
        )
        object.__setattr__(
            self,
            "fully_wet_grip_multiplier",
            _positive_at_most_one(
                self.fully_wet_grip_multiplier, "fully_wet_grip_multiplier"
            ),
        )


@dataclass(frozen=True, slots=True)
class ResolvedSurfaceGrip:
    surface_id: str
    wetness: float
    dry_grip_multiplier: float
    fully_wet_grip_multiplier: float
    grip_multiplier: float


@dataclass(frozen=True, slots=True)
class SurfaceGripPolicy:
    name: str
    rules: tuple[SurfaceGripRule, ...]

    def __post_init__(self):
        object.__setattr__(self, "name", _clean_name(self.name, "name"))
        if not isinstance(self.rules, tuple):
            raise ValueError(
                f"rules must be a tuple, got {type(self.rules).__name__}"
            )
        if not self.rules:
            raise ValueError("rules must contain at least one SurfaceGripRule")

        seen: set[str] = set()
        for index, rule in enumerate(self.rules):
            if not isinstance(rule, SurfaceGripRule):
                raise ValueError(
                    f"rules[{index}] must be a SurfaceGripRule, "
                    f"got {type(rule).__name__}"
                )
            if rule.surface_id in seen:
                raise ValueError(f"duplicate surface_id: {rule.surface_id}")
            seen.add(rule.surface_id)

    def resolve(self, surface_id: str, wetness: float) -> ResolvedSurfaceGrip:
        surface = _clean_name(surface_id, "surface_id")
        wet = _closed_unit_interval(wetness, "wetness")

        rule = next((item for item in self.rules if item.surface_id == surface), None)
        if rule is None:
            raise ValueError(
                f"surface_id {surface!r} is not configured in grip policy {self.name!r}"
            )

        grip = (
            rule.dry_grip_multiplier
            + (rule.fully_wet_grip_multiplier - rule.dry_grip_multiplier) * wet
        )
        return ResolvedSurfaceGrip(
            surface_id=rule.surface_id,
            wetness=wet,
            dry_grip_multiplier=rule.dry_grip_multiplier,
            fully_wet_grip_multiplier=rule.fully_wet_grip_multiplier,
            grip_multiplier=grip,
        )
