"""Deterministic adaptive near-field terrain policy with verified-case memory.

This module deliberately has no Unreal dependency. It does not generate geometry
itself; it decides which already-reviewed terrain strategy should own a corridor
and which bounded parameters to use.

"Learning" is case-based and review-gated:
- only exact-SHA technical PASS + human visual PASS cases are eligible;
- similar accepted cases may tune parameters inside the same safe strategy;
- safety/escalation decisions are never overridden by case memory;
- case memory and policy are versioned repository inputs, so the same inputs
  always produce the same decision.

Units are metres unless a field explicitly says otherwise.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


STRATEGY_NATIVE_BLEND = "native_blend"
STRATEGY_CONSTRAINED_CUT_FILL = "constrained_cut_fill"
STRATEGY_HAIRPIN_CLEARANCE = "hairpin_clearance"
STRATEGY_RETAINING_OR_CLIFF = "retaining_or_cliff"

HEIGHTFIELD_STRATEGIES = frozenset(
    {
        STRATEGY_NATIVE_BLEND,
        STRATEGY_CONSTRAINED_CUT_FILL,
        STRATEGY_HAIRPIN_CLEARANCE,
    }
)
ALL_STRATEGIES = HEIGHTFIELD_STRATEGIES | {STRATEGY_RETAINING_OR_CLIFF}


@dataclass(frozen=True)
class TerrainFeatures:
    longitudinal_grade: float
    left_cross_slope: float
    right_cross_slope: float
    road_to_dtm_delta_m: float
    dtm_roughness_m: float
    curvature_radius_m: float | None
    nearest_branch_xy_m: float | None
    nearest_branch_z_separation_m: float | None
    max_cut_fill_m: float

    def __post_init__(self) -> None:
        finite = (
            self.longitudinal_grade,
            self.left_cross_slope,
            self.right_cross_slope,
            self.road_to_dtm_delta_m,
            self.dtm_roughness_m,
            self.max_cut_fill_m,
        )
        if not all(math.isfinite(value) for value in finite):
            raise ValueError("terrain features contain a non-finite required value")
        if self.dtm_roughness_m < 0.0 or self.max_cut_fill_m < 0.0:
            raise ValueError("roughness and max_cut_fill_m cannot be negative")
        for name, value in (
            ("curvature_radius_m", self.curvature_radius_m),
            ("nearest_branch_xy_m", self.nearest_branch_xy_m),
            (
                "nearest_branch_z_separation_m",
                self.nearest_branch_z_separation_m,
            ),
        ):
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"{name} must be finite and non-negative when present")


@dataclass(frozen=True)
class TerrainParameters:
    shoulder_apron_m: float
    transition_width_m: float
    max_ground_adjustment_m: float
    min_asphalt_clearance_m: float

    def __post_init__(self) -> None:
        values = (
            self.shoulder_apron_m,
            self.transition_width_m,
            self.max_ground_adjustment_m,
            self.min_asphalt_clearance_m,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError("terrain parameters must be finite and positive")


@dataclass(frozen=True)
class VerifiedTerrainCase:
    case_id: str
    exact_sha: str
    technical_status: str
    visual_status: str
    strategy: str
    features: TerrainFeatures
    parameters: TerrainParameters

    @property
    def eligible_for_learning(self) -> bool:
        return (
            bool(self.case_id)
            and len(self.exact_sha) == 40
            and self.technical_status == "PASS"
            and self.visual_status == "PASS"
            and self.strategy in HEIGHTFIELD_STRATEGIES
        )


@dataclass(frozen=True)
class TerrainDecision:
    strategy: str
    parameters: TerrainParameters
    baseline_strategy: str
    learning_applied: bool
    contributing_case_ids: tuple[str, ...]
    best_similarity: float
    reasons: tuple[str, ...]


FEATURE_SOURCE_PCGEX = "pcgex_spatial_analysis"
FEATURE_SOURCE_YACS = "yacs_python_analysis"
ALLOWED_FEATURE_SOURCES = frozenset({FEATURE_SOURCE_PCGEX, FEATURE_SOURCE_YACS})


@dataclass(frozen=True)
class TerrainFeatureProvenance:
    source_kind: str
    source_artifact_sha256: str
    source_dataset_id: str
    canonical_road_xy_preserved: bool
    authoritative_route_geometry: bool
    authoritative_physics: bool
    pcgex_commit: str | None = None

    def __post_init__(self) -> None:
        if self.source_kind not in ALLOWED_FEATURE_SOURCES:
            raise ValueError(f"unsupported terrain feature source {self.source_kind!r}")
        if len(self.source_artifact_sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.source_artifact_sha256
        ):
            raise ValueError("feature source artifact SHA256 must be lowercase hex")
        if not self.source_dataset_id:
            raise ValueError("feature source dataset id cannot be empty")
        if self.canonical_road_xy_preserved is not True:
            raise ValueError("feature producer must preserve canonical road XY")
        if self.authoritative_route_geometry is not False:
            raise ValueError("feature producer cannot claim route authority")
        if self.authoritative_physics is not False:
            raise ValueError("feature producer cannot claim physics authority")
        if self.source_kind == FEATURE_SOURCE_PCGEX:
            if (
                self.pcgex_commit is None
                or len(self.pcgex_commit) != 40
                or any(character not in "0123456789abcdef" for character in self.pcgex_commit)
            ):
                raise ValueError(
                    "PCGEx feature packets require the exact lowercase PCGEx commit"
                )


@dataclass(frozen=True)
class TerrainFeaturePacket:
    corridor_id: str
    exact_sha: str
    provenance: TerrainFeatureProvenance
    features: TerrainFeatures

    def __post_init__(self) -> None:
        if not self.corridor_id:
            raise ValueError("terrain feature packet corridor_id cannot be empty")
        if len(self.exact_sha) != 40 or any(
            character not in "0123456789abcdef" for character in self.exact_sha
        ):
            raise ValueError("terrain feature packet exact_sha must be lowercase SHA40")


def _feature_vector(features: TerrainFeatures) -> dict[str, float]:
    curvature_inverse = (
        0.0
        if features.curvature_radius_m is None
        else 1.0 / max(features.curvature_radius_m, 1e-6)
    )
    branch_inverse = (
        0.0
        if features.nearest_branch_xy_m is None
        else 1.0 / max(features.nearest_branch_xy_m, 1e-6)
    )
    branch_z = (
        0.0
        if features.nearest_branch_z_separation_m is None
        else features.nearest_branch_z_separation_m
    )
    return {
        "grade_abs": abs(features.longitudinal_grade),
        "cross_slope_abs": max(
            abs(features.left_cross_slope),
            abs(features.right_cross_slope),
        ),
        "road_dtm_delta_abs_m": abs(features.road_to_dtm_delta_m),
        "dtm_roughness_m": features.dtm_roughness_m,
        "curvature_inverse_per_m": curvature_inverse,
        "branch_inverse_per_m": branch_inverse,
        "branch_z_separation_m": branch_z,
        "max_cut_fill_m": features.max_cut_fill_m,
    }


def _strategy_parameters(policy: Mapping[str, Any], strategy: str) -> TerrainParameters:
    strategies = policy.get("strategies")
    if not isinstance(strategies, Mapping) or strategy not in strategies:
        raise ValueError(f"policy is missing strategy {strategy!r}")
    raw = strategies[strategy]
    if not isinstance(raw, Mapping):
        raise ValueError(f"strategy {strategy!r} policy must be an object")
    return TerrainParameters(
        shoulder_apron_m=float(raw["shoulder_apron_m"]),
        transition_width_m=float(raw["transition_width_m"]),
        max_ground_adjustment_m=float(raw["max_ground_adjustment_m"]),
        min_asphalt_clearance_m=float(raw["min_asphalt_clearance_m"]),
    )


def validate_policy(policy: Mapping[str, Any]) -> None:
    if int(policy.get("schema_version", -1)) != 1:
        raise ValueError("adaptive terrain policy schema_version must be 1")

    scales = policy.get("feature_scales")
    if not isinstance(scales, Mapping):
        raise ValueError("policy feature_scales must be an object")
    expected_features = set(_feature_vector(TerrainFeatures(
        longitudinal_grade=0.0,
        left_cross_slope=0.0,
        right_cross_slope=0.0,
        road_to_dtm_delta_m=0.0,
        dtm_roughness_m=0.0,
        curvature_radius_m=None,
        nearest_branch_xy_m=None,
        nearest_branch_z_separation_m=None,
        max_cut_fill_m=0.0,
    )))
    if set(scales) != expected_features:
        raise ValueError("policy feature_scales keys do not match the feature vector")
    if not all(math.isfinite(float(value)) and float(value) > 0.0 for value in scales.values()):
        raise ValueError("all feature scales must be finite and positive")

    thresholds = policy.get("thresholds")
    if not isinstance(thresholds, Mapping):
        raise ValueError("policy thresholds must be an object")
    required_thresholds = (
        "stacked_branch_xy_m",
        "stacked_branch_z_m",
        "retaining_cut_fill_m",
        "hairpin_radius_m",
        "hairpin_branch_xy_m",
        "minor_delta_m",
        "minor_roughness_m",
        "minor_cut_fill_m",
    )
    for name in required_thresholds:
        value = float(thresholds[name])
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"threshold {name!r} must be finite and positive")

    learning = policy.get("learning")
    if not isinstance(learning, Mapping):
        raise ValueError("policy learning must be an object")
    minimum_similarity = float(learning["minimum_similarity"])
    max_cases = int(learning["max_cases"])
    if not 0.0 < minimum_similarity <= 1.0:
        raise ValueError("learning.minimum_similarity must be in (0, 1]")
    if max_cases < 1:
        raise ValueError("learning.max_cases must be positive")

    for strategy in ALL_STRATEGIES:
        _strategy_parameters(policy, strategy)


def baseline_strategy(
    features: TerrainFeatures,
    policy: Mapping[str, Any],
) -> tuple[str, tuple[str, ...]]:
    validate_policy(policy)
    thresholds = policy["thresholds"]
    reasons: list[str] = []

    branch_xy = features.nearest_branch_xy_m
    branch_z = features.nearest_branch_z_separation_m
    if (
        branch_xy is not None
        and branch_z is not None
        and branch_xy <= float(thresholds["stacked_branch_xy_m"])
        and branch_z >= float(thresholds["stacked_branch_z_m"])
    ):
        reasons.append(
            "nearby road branches are vertically separated inside one heightfield footprint"
        )
        return STRATEGY_RETAINING_OR_CLIFF, tuple(reasons)

    if features.max_cut_fill_m >= float(thresholds["retaining_cut_fill_m"]):
        reasons.append("required cut/fill exceeds the bounded heightfield policy")
        return STRATEGY_RETAINING_OR_CLIFF, tuple(reasons)

    tight_radius = (
        features.curvature_radius_m is not None
        and features.curvature_radius_m <= float(thresholds["hairpin_radius_m"])
    )
    close_branch = (
        branch_xy is not None
        and branch_xy <= float(thresholds["hairpin_branch_xy_m"])
    )
    if tight_radius or close_branch:
        if tight_radius:
            reasons.append("tight curvature requires protected road-edge clearance")
        if close_branch:
            reasons.append("nearby same-level branch requires route-local ownership")
        return STRATEGY_HAIRPIN_CLEARANCE, tuple(reasons)

    if (
        abs(features.road_to_dtm_delta_m) <= float(thresholds["minor_delta_m"])
        and features.dtm_roughness_m <= float(thresholds["minor_roughness_m"])
        and features.max_cut_fill_m <= float(thresholds["minor_cut_fill_m"])
    ):
        reasons.append("native terrain is already close to the road corridor")
        return STRATEGY_NATIVE_BLEND, tuple(reasons)

    reasons.append("bounded road/earthwork correction is required")
    return STRATEGY_CONSTRAINED_CUT_FILL, tuple(reasons)


def similarity_score(
    left: TerrainFeatures,
    right: TerrainFeatures,
    policy: Mapping[str, Any],
) -> float:
    validate_policy(policy)
    scales = policy["feature_scales"]
    left_vector = _feature_vector(left)
    right_vector = _feature_vector(right)
    squared = 0.0
    for name in sorted(left_vector):
        scale = float(scales[name])
        delta = (left_vector[name] - right_vector[name]) / scale
        squared += delta * delta
    distance = math.sqrt(squared / len(left_vector))
    return math.exp(-distance)


def _blend_parameters(
    baseline: TerrainParameters,
    matches: Sequence[tuple[float, VerifiedTerrainCase]],
) -> TerrainParameters:
    if not matches:
        return baseline

    total_weight = sum(score for score, _case in matches)
    if total_weight <= 0.0:
        return baseline

    def weighted(name: str) -> float:
        return sum(
            score * float(getattr(case.parameters, name))
            for score, case in matches
        ) / total_weight

    learned = TerrainParameters(
        shoulder_apron_m=weighted("shoulder_apron_m"),
        transition_width_m=weighted("transition_width_m"),
        max_ground_adjustment_m=weighted("max_ground_adjustment_m"),
        min_asphalt_clearance_m=weighted("min_asphalt_clearance_m"),
    )

    # Learning may tune a strategy, but it may not weaken baseline safety bounds.
    return TerrainParameters(
        shoulder_apron_m=max(baseline.shoulder_apron_m, learned.shoulder_apron_m),
        transition_width_m=max(
            baseline.transition_width_m,
            learned.transition_width_m,
        ),
        max_ground_adjustment_m=min(
            baseline.max_ground_adjustment_m,
            learned.max_ground_adjustment_m,
        ),
        min_asphalt_clearance_m=max(
            baseline.min_asphalt_clearance_m,
            learned.min_asphalt_clearance_m,
        ),
    )


def choose_terrain_decision(
    features: TerrainFeatures,
    policy: Mapping[str, Any],
    cases: Sequence[VerifiedTerrainCase],
) -> TerrainDecision:
    strategy, reasons = baseline_strategy(features, policy)
    baseline = _strategy_parameters(policy, strategy)

    # Non-heightfield escalation is a safety decision, not a learnable preference.
    if strategy not in HEIGHTFIELD_STRATEGIES:
        return TerrainDecision(
            strategy=strategy,
            parameters=baseline,
            baseline_strategy=strategy,
            learning_applied=False,
            contributing_case_ids=(),
            best_similarity=0.0,
            reasons=reasons + ("case memory cannot override safety escalation",),
        )

    learning = policy["learning"]
    minimum_similarity = float(learning["minimum_similarity"])
    max_cases = int(learning["max_cases"])

    matches: list[tuple[float, VerifiedTerrainCase]] = []
    for case in cases:
        if not case.eligible_for_learning or case.strategy != strategy:
            continue
        score = similarity_score(features, case.features, policy)
        if score >= minimum_similarity:
            matches.append((score, case))

    matches.sort(key=lambda item: (-item[0], item[1].case_id))
    selected = matches[:max_cases]
    best_similarity = selected[0][0] if selected else 0.0
    parameters = _blend_parameters(baseline, selected)

    if selected:
        learning_reason = (
            "parameters tuned from verified similar cases: "
            + ", ".join(case.case_id for _score, case in selected)
        )
        decision_reasons = reasons + (learning_reason,)
    else:
        decision_reasons = reasons + (
            "no sufficiently similar verified case; using baseline policy",
        )

    return TerrainDecision(
        strategy=strategy,
        parameters=parameters,
        baseline_strategy=strategy,
        learning_applied=bool(selected),
        contributing_case_ids=tuple(case.case_id for _score, case in selected),
        best_similarity=best_similarity,
        reasons=decision_reasons,
    )


def _features_from_mapping(raw: Mapping[str, Any]) -> TerrainFeatures:
    return TerrainFeatures(
        longitudinal_grade=float(raw["longitudinal_grade"]),
        left_cross_slope=float(raw["left_cross_slope"]),
        right_cross_slope=float(raw["right_cross_slope"]),
        road_to_dtm_delta_m=float(raw["road_to_dtm_delta_m"]),
        dtm_roughness_m=float(raw["dtm_roughness_m"]),
        curvature_radius_m=(
            None
            if raw.get("curvature_radius_m") is None
            else float(raw["curvature_radius_m"])
        ),
        nearest_branch_xy_m=(
            None
            if raw.get("nearest_branch_xy_m") is None
            else float(raw["nearest_branch_xy_m"])
        ),
        nearest_branch_z_separation_m=(
            None
            if raw.get("nearest_branch_z_separation_m") is None
            else float(raw["nearest_branch_z_separation_m"])
        ),
        max_cut_fill_m=float(raw["max_cut_fill_m"]),
    )


def _provenance_from_mapping(raw: Mapping[str, Any]) -> TerrainFeatureProvenance:
    return TerrainFeatureProvenance(
        source_kind=str(raw["source_kind"]),
        source_artifact_sha256=str(raw["source_artifact_sha256"]),
        source_dataset_id=str(raw["source_dataset_id"]),
        canonical_road_xy_preserved=bool(raw["canonical_road_xy_preserved"]),
        authoritative_route_geometry=bool(raw["authoritative_route_geometry"]),
        authoritative_physics=bool(raw["authoritative_physics"]),
        pcgex_commit=(
            None if raw.get("pcgex_commit") is None else str(raw["pcgex_commit"])
        ),
    )


def feature_packet_from_mapping(raw: Mapping[str, Any]) -> TerrainFeaturePacket:
    if int(raw.get("schema_version", -1)) != 1:
        raise ValueError("terrain feature packet schema_version must be 1")
    features = raw.get("features")
    provenance = raw.get("provenance")
    if not isinstance(features, Mapping):
        raise ValueError("terrain feature packet features must be an object")
    if not isinstance(provenance, Mapping):
        raise ValueError("terrain feature packet provenance must be an object")
    return TerrainFeaturePacket(
        corridor_id=str(raw["corridor_id"]),
        exact_sha=str(raw["exact_sha"]),
        provenance=_provenance_from_mapping(provenance),
        features=_features_from_mapping(features),
    )


def _parameters_from_mapping(raw: Mapping[str, Any]) -> TerrainParameters:
    return TerrainParameters(
        shoulder_apron_m=float(raw["shoulder_apron_m"]),
        transition_width_m=float(raw["transition_width_m"]),
        max_ground_adjustment_m=float(raw["max_ground_adjustment_m"]),
        min_asphalt_clearance_m=float(raw["min_asphalt_clearance_m"]),
    )


def load_policy(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("adaptive terrain policy root must be an object")
    validate_policy(payload)
    return payload


def load_case_memory(path: Path) -> tuple[VerifiedTerrainCase, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schema_version", -1)) != 1:
        raise ValueError("terrain case memory schema_version must be 1")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("terrain case memory cases must be a list")

    cases: list[VerifiedTerrainCase] = []
    ids: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, Mapping):
            raise ValueError("terrain case entry must be an object")
        case_id = str(raw["case_id"])
        if not case_id or case_id in ids:
            raise ValueError(f"duplicate or empty terrain case id: {case_id!r}")
        ids.add(case_id)
        strategy = str(raw["strategy"])
        if strategy not in ALL_STRATEGIES:
            raise ValueError(f"terrain case uses unknown strategy {strategy!r}")
        cases.append(
            VerifiedTerrainCase(
                case_id=case_id,
                exact_sha=str(raw["exact_sha"]),
                technical_status=str(raw["technical_status"]),
                visual_status=str(raw["visual_status"]),
                strategy=strategy,
                features=_features_from_mapping(raw["features"]),
                parameters=_parameters_from_mapping(raw["parameters"]),
            )
        )
    return tuple(cases)


def decision_to_dict(decision: TerrainDecision) -> dict[str, Any]:
    payload = asdict(decision)
    payload["contributing_case_ids"] = list(decision.contributing_case_ids)
    payload["reasons"] = list(decision.reasons)
    return payload


def decision_report(
    packet: TerrainFeaturePacket,
    decision: TerrainDecision,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "corridor_id": packet.corridor_id,
        "exact_sha": packet.exact_sha,
        "feature_provenance": asdict(packet.provenance),
        "features": asdict(packet.features),
        "decision": decision_to_dict(decision),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    policy = load_policy(args.policy)
    cases = load_case_memory(args.cases)
    raw_features = json.loads(args.features.read_text(encoding="utf-8"))
    if not isinstance(raw_features, Mapping):
        raise ValueError("terrain feature input must be an object")
    packet = feature_packet_from_mapping(raw_features)

    decision = choose_terrain_decision(
        packet.features,
        policy,
        cases,
    )
    rendered = json.dumps(
        decision_report(packet, decision),
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
