"""Quintic endpoint interpolation in metric distance; no engine or SciPy dependency."""

import math


def quintic(p0, v0, a0, p1, v1, a1, length):
    if not all(math.isfinite(x) for x in (p0, v0, a0, p1, v1, a1, length)) or length <= 0:
        raise ValueError("Invalid finite transition endpoints")
    c0, c1, c2 = p0, v0 * length, a0 * length**2 / 2
    d, e, f = p1 - c0 - c1 - c2, v1 * length - c1 - 2 * c2, a1 * length**2 - 2 * c2
    return [c0, c1, c2, 10 * d - 4 * e + f / 2, -15 * d + 7 * e - f, 6 * d - 3 * e + f / 2]


def evaluate(coefficients, distance, length, derivative=0):
    if derivative not in (0, 1, 2) or not 0 <= distance <= length or length <= 0:
        raise ValueError("Transition evaluation outside domain")
    u = distance / length
    return sum(
        c * math.factorial(i) / math.factorial(i - derivative) * u ** (i - derivative)
        for i, c in enumerate(coefficients) if i >= derivative
    ) / length**derivative


def verify_join_proof(proofs, spans):
    if not isinstance(proofs, list) or len(proofs) != len(spans):
        raise ValueError("Missing G2 transition joins")
    for proof, span in zip(proofs, spans):
        if any(proof.get(k) != span[k] for k in ("start_station_m", "end_station_m")) or len(proof.get("joins", [])) != 2:
            raise ValueError("G2 transition domain mismatch")
        for join in proof["joins"]:
            for key in ("position_error_m", "unit_tangent_error", "curvature_error_per_m"):
                value = join.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1e-4:
                    raise ValueError("G2 transition join failed")
