"""Bound the owner's 2026-10-04 construction decision to the reviewed geometry."""

import math

from scripts.geometry.network_visual_preview import (
    preview_fingerprint,
    validate_full_preview,
)

REVIEWED_COMMIT = "704203647ff7967ddefdae4d6cb3aa00e0ca1297"
REVIEWED_FINGERPRINT = (
    "fc894083cc8f13c2df86a919af0778b246ec263e271a595ad307a188cfc82da5"
)


def validate_reviewed_geometry(network):
    proof = validate_full_preview(
        network["full_preview"], network["source_clipped_length_m"]
    )
    if proof["fingerprint"] != REVIEWED_FINGERPRINT:
        raise ValueError("Owner construction decision does not cover this geometry")
    return proof


def validate_slab(sections):
    """Keep finite, complete, nonfolded pavement mandatory after visual acceptance."""
    if len(sections) < 3 or any(
        len(row) != 25
        or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in row)
        for row in sections
    ):
        raise ValueError("Invalid reviewed pavement sections")
    for left, right in zip(sections, sections[1:]):
        for j in range(24):
            a, b, c, d = left[j], left[j + 1], right[j], right[j + 1]
            for p, q, r in ((a, b, c), (b, d, c)):
                area = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
                if area >= -1e-9:
                    raise ValueError(
                        "Reviewed pavement has a folded or degenerate triangle"
                    )


def construction_windows(network):
    if "owner_reviewed" not in network:
        return network["approved"]
    validate_reviewed_geometry(network)
    decision = network["owner_construction_decision"]
    if (
        decision["reviewed_commit"] != REVIEWED_COMMIT
        or decision["reviewed_fingerprint"] != REVIEWED_FINGERPRINT
        or decision["construction_sha256"]
        != preview_fingerprint(network["owner_reviewed"])
    ):
        raise ValueError("Reviewed construction receipt mismatch")
    windows = network["approved"] + network["owner_reviewed"]
    if "nudo" in network:
        nudo = network["nudo"]
        replaced = [w["id"] for w in windows if "VIAL_TR70190001178" in w["id"]]
        if (nudo["replaced_window_ids"] != replaced
                or not replaced
                or nudo["construction_sha256"] != preview_fingerprint(nudo["windows"])
                or nudo["structure_sha256"] != preview_fingerprint([nudo["structure"]])):
            raise ValueError("Nudo construction receipt mismatch")
        windows = [w for w in windows if w["id"] not in replaced] + nudo["windows"]
    return windows
