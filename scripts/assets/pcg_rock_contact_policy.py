"""Frozen trial v1 sampled-contact decision, never full asset qualification.

Native input contract: height_cm is transformed mesh AABB height; uniform_scale,
yaw_deg, tilt_deg and max_local_slope_deg describe the measured final transform
and maximum local ground slope. sample_count counts paired mesh ray intervals,
valid_ground_count counts their authenticated ground hits. coverage_status must
be COMPLETE_SAMPLED_MESH_FOOTPRINT; ground_class is the actual hit component.
fit contains required_embedding_cm, root_zero_sampled_air_cm, exposure_max_cm,
exposed_count and max_positive_bottom_gap_cm. refinement contains coarse_grid,
fine_grid, coarse_root_cm, fine_root_cm, coarse_embedding_cm, fine_embedding_cm.
The fit must describe the fine 65x65 measurement. This module does not verify
native evidence authenticity, continuous support, source heights or materials.
"""

import math


def trial_policy():
    """Return a fresh frozen-design record; values are not measured accuracy."""
    return {
        "policy_id": "PCG_ROCK_SAMPLED_CONTACT_TRIAL_V1",
        "schema_version": 1,
        "basis": "DESIGN_FROZEN_BEFORE_NATIVE_NOT_MEASURED_TERRAIN_ACCURACY",
        "uniform_scale": 1.0,
        "yaw_deg": 0.0,
        "tilt_deg": 0.0,
        "max_local_slope_deg": 10.0,
        "max_embedding_fraction": 0.20,
        "min_exposed_height_fraction": 0.80,
        "min_exposed_ray_fraction": 0.80,
        "max_positive_bottom_gap_cm": 0.0,
        "required_valid_ground_fraction": 1.0,
        "root_convergence_cm": 0.1,
        "embedding_convergence_cm": 0.1,
        "coarse_grid": 33,
        "fine_grid": 65,
        "ground_class": "LandscapeHeightfieldCollisionComponent",
    }


def refined_trial_policy():
    """Same physical/numeric limits; an explicit 65-to-129 refinement stage."""
    policy = trial_policy()
    policy.update(
        policy_id="PCG_ROCK_SAMPLED_CONTACT_REFINEMENT_V2",
        coarse_grid=65,
        fine_grid=129,
    )
    return policy


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("NONFINITE_OR_NONNUMERIC_MEASUREMENT")
    return value


def evaluate(measurement, policy):
    """Return only a sampled decision; malformed/unknown inputs reject closed."""
    reasons = []
    metrics = {}
    expected = (
        refined_trial_policy()
        if isinstance(policy, dict)
        and policy.get("policy_id") == "PCG_ROCK_SAMPLED_CONTACT_REFINEMENT_V2"
        else trial_policy()
    )
    # Match types too: Python otherwise considers True equal to 1.
    if (
        not isinstance(policy, dict)
        or set(policy) != set(expected)
        or any(
            type(policy[key]) is not type(value) or policy[key] != value
            for key, value in expected.items()
        )
    ):
        reasons.append("UNKNOWN_OR_MODIFIED_POLICY")
    else:
        try:
            m, fit, refinement = (
                measurement,
                measurement["fit"],
                measurement["refinement"],
            )
            height = _number(m["height_cm"])
            if height <= 0:
                raise ValueError("INVALID_MESH_HEIGHT")
            count, valid, exposed = (
                m["sample_count"],
                m["valid_ground_count"],
                fit["exposed_count"],
            )
            if (
                any(type(v) is not int for v in (count, valid, exposed))
                or count <= 0
                or not 0 <= valid <= count
                or not 0 <= exposed <= count
            ):
                raise ValueError("INVALID_SAMPLE_COUNTS")
            embedding = _number(fit["required_embedding_cm"])
            root = _number(fit["root_zero_sampled_air_cm"])
            exposed_height = _number(fit["exposure_max_cm"])
            gap = _number(fit["max_positive_bottom_gap_cm"])
            slope = _number(m["max_local_slope_deg"])
            if (
                min(embedding, exposed_height, gap, slope) < 0
                or slope > 90
                or exposed_height > height
            ):
                raise ValueError("INVALID_MEASUREMENT_RANGE")
            if (
                m["coverage_status"] != "COMPLETE_SAMPLED_MESH_FOOTPRINT"
                or valid != count
            ):
                reasons.append("INCOMPLETE_VALID_GROUND_COVERAGE")
            if m["ground_class"] != expected["ground_class"]:
                reasons.append("UNKNOWN_GROUND_CLASS")
            for key in ("uniform_scale", "yaw_deg", "tilt_deg"):
                if _number(m[key]) != expected[key]:
                    reasons.append("UNSUPPORTED_" + key.upper())
            if slope > expected["max_local_slope_deg"]:
                reasons.append("EXCESSIVE_LOCAL_SLOPE")
            if embedding > height * expected["max_embedding_fraction"]:
                reasons.append("EXCESSIVE_EMBEDDING")
            if exposed_height < height * expected["min_exposed_height_fraction"]:
                reasons.append("INSUFFICIENT_EXPOSED_HEIGHT")
            if exposed < count * expected["min_exposed_ray_fraction"]:
                reasons.append("INSUFFICIENT_EXPOSED_RAYS")
            if gap > expected["max_positive_bottom_gap_cm"]:
                reasons.append("POSITIVE_BOTTOM_GAP")
            if any(
                type(refinement[k]) is not int or refinement[k] != expected[k]
                for k in ("coarse_grid", "fine_grid")
            ):
                reasons.append("INVALID_REFINEMENT_GRIDS")
            coarse_root, fine_root, coarse_embedding, fine_embedding = (
                _number(refinement[key])
                for key in (
                    "coarse_root_cm",
                    "fine_root_cm",
                    "coarse_embedding_cm",
                    "fine_embedding_cm",
                )
            )
            if min(coarse_embedding, fine_embedding) < 0:
                raise ValueError("INVALID_REFINEMENT_EMBEDDING")
            if fine_root != root or fine_embedding != embedding:
                reasons.append("FINE_FIT_REFINEMENT_MISMATCH")
            root_delta, embedding_delta = (
                abs(fine_root - coarse_root),
                abs(fine_embedding - coarse_embedding),
            )
            if root_delta > expected["root_convergence_cm"]:
                reasons.append("ROOT_NOT_CONVERGED")
            if embedding_delta > expected["embedding_convergence_cm"]:
                reasons.append("EMBEDDING_NOT_CONVERGED")
            metrics = {
                "embedding_fraction": embedding / height,
                "exposed_height_fraction": exposed_height / height,
                "exposed_ray_fraction": exposed / count,
                "valid_ground_fraction": valid / count,
                "root_delta_cm": root_delta,
                "embedding_delta_cm": embedding_delta,
            }
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            reasons.append(
                str(error)
                if isinstance(error, ValueError)
                else "MISSING_OR_MALFORMED_MEASUREMENT"
            )
    return {
        "status": "REJECTED" if reasons else "PASS_SAMPLED_CONTACT_ONLY",
        "reasons": reasons,
        "metrics": metrics,
        "policy_id": expected["policy_id"],
        "full_qualification": False,
        "placement": False,
        "continuous_support_verified": False,
        "proof_authenticity": "NOT_VERIFIED",
        "convergence_semantics": "NUMERICAL_SAMPLE_STABILITY_NOT_DTM_ACCURACY_OR_CONTINUOUS_PROOF",
    }
