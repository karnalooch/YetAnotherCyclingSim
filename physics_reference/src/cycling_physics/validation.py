"""Private numeric validation helpers shared inside the cycling_physics package.

The helpers reject booleans and non-numeric values, convert accepted
integers to floats and raise ValueError with a readable message that
includes the field name. They are not part of the public API.
"""

import math


def _require_real_number(value, field_name):
    """Return value as a float, rejecting non-real or non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"{field_name} must be a real number, got {value!r} "
            f"of type {type(value).__name__}"
        )
    return float(value)


def _finite(value, field_name):
    """Return value as a finite float."""
    result = _require_real_number(value, field_name)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be a finite number, got {result}")
    return result


def _positive(value, field_name):
    """Return a validated float strictly greater than zero."""
    result = _finite(value, field_name)
    if result <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero, got {result}")
    return result


def _non_negative(value, field_name):
    """Return a validated float greater than or equal to zero."""
    result = _finite(value, field_name)
    if result < 0.0:
        raise ValueError(f"{field_name} must not be negative, got {result}")
    return result


def _efficiency(value, field_name):
    """Return a validated float inside the open-closed interval (0, 1]."""
    result = _finite(value, field_name)
    if not 0.0 < result <= 1.0:
        raise ValueError(f"{field_name} must be in the interval (0, 1], got {result}")
    return result


def _clean_name(value, field_name):
    """Return value as a stripped non-empty string."""
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string, got {value!r} "
            f"of type {type(value).__name__}"
        )
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty after stripping whitespace")
    return cleaned
