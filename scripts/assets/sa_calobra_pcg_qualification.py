"""Structural #365 mesh/material/ground binding; never proof admission.

This pure CPU validator cannot authenticate a claimed native observation. Its
output always keeps placement disabled and proof authenticity NOT_VERIFIED.
The caller must use existing Gumball/native/human gates before any placement.
No historical catalog approval, texture receipt or material height is ground.
All geometry/contact numbers are SI; no tolerance defaults are provided.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

from prepare_sa_calobra_world_graph_inputs import GRID, MAPPING

FIXTURES = {
    "flat": "supported",
    "admissible_slope": "supported",
    "excessive_slope": "rejected",
    "uneven_support": "rejected",
    "seam": "rejected",
    "class_boundary": "rejected",
    "nodata": "rejected",
    "holdback": "rejected",
    "aoi_edge": "rejected",
    "maximum_scale_offcenter_pivot": "supported",
    "unrelated_collider_above_ground": "supported_or_rejected",
    "generated_collider": "supported_or_rejected",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(
        isinstance(value, dict) and set(value) == set(names.split()),
        "Unexpected or missing " + label + " fields",
    )


def text(value, label):
    require(
        isinstance(value, str)
        and bool(value.strip())
        and value not in {"REQUIRED_UNSET", "UNKNOWN", "PENDING", "NOT_RUN"},
        "Missing explicit " + label,
    )


def digest(value, label, length=64):
    require(
        isinstance(value, str)
        and re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is not None,
        "Malformed " + label,
    )


def number(value, label, minimum=None, maximum=None):
    require(
        type(value) in (int, float) and math.isfinite(value),
        "Finite numeric " + label + " required",
    )
    require(minimum is None or value >= minimum, label + " below minimum")
    require(maximum is None or value <= maximum, label + " above maximum")


def vector(value, count, label):
    require(isinstance(value, list) and len(value) == count, "Malformed " + label)
    for component in value:
        number(component, label)


def evidence(value, code_sha, kind, require_current=True):
    """Check claim consistency only; neither bytes nor execution are authenticated."""
    fields(value, "sha256 code_sha kind status", "evidence")
    digest(value["sha256"], "evidence SHA256")
    digest(value["code_sha"], "evidence code SHA", 40)
    if require_current:
        require(
            value["code_sha"] == code_sha,
            "Evidence code SHA differs from qualification",
        )
    require(value["kind"] == kind, "Wrong evidence kind")
    require(value["status"] == "COMPLETE", "Evidence claim is incomplete")


def validate_qualification(record):
    """Validate a proposed v1 qualification binding without authorizing placement.

    ``lifecycle_status`` stays independent of scoped qualification. Only imported
    or validated StaticMesh entries can reach structural validation. Evidence
    status COMPLETE is a required *claim*, never verified native proof here.
    Material-local Height and masks are deliberately absent from ground inputs.
    """
    fields(
        record,
        "schema_version issue code_sha asset native materials terrain contact fixtures",
        "qualification",
    )
    require(
        type(record["schema_version"]) is int and record["schema_version"] == 1,
        "Unsupported qualification schema",
    )
    require(type(record["issue"]) is int and record["issue"] == 365, "Wrong issue")
    code_sha = record["code_sha"]
    digest(code_sha, "code SHA", 40)

    asset = record["asset"]
    fields(
        asset,
        "catalog_id kind lifecycle_status source_sha256 source_size_bytes source_url license_id license_evidence regional_rationale intended_bands excluded_uses",
        "asset",
    )
    require(asset["kind"] == "StaticMesh", "Texture/material is not a StaticMesh")
    require(
        asset["lifecycle_status"] in {"imported", "validated"},
        "Catalog approval/acquisition is not native import",
    )
    for key in ("catalog_id", "source_url", "license_id", "regional_rationale"):
        text(asset[key], key)
    digest(asset["source_sha256"], "source SHA256")
    require(
        type(asset["source_size_bytes"]) is int and asset["source_size_bytes"] > 0,
        "Nonempty source bytes required",
    )
    evidence(asset["license_evidence"], code_sha, "license", require_current=False)
    require(
        isinstance(asset["intended_bands"], list)
        and asset["intended_bands"]
        and len(set(asset["intended_bands"])) == len(asset["intended_bands"])
        and all(type(b) is int and b in (0, 1, 2) for b in asset["intended_bands"]),
        "Explicit source selector bands required",
    )
    require(
        isinstance(asset["excluded_uses"], list) and asset["excluded_uses"],
        "Explicit excluded uses required",
    )
    for use in asset["excluded_uses"]:
        text(use, "excluded use")

    native = record["native"]
    fields(
        native,
        "object_path package_sha256 evidence bounds_min_m bounds_max_m root_anchor_m support_points_m uniform_scale_range yaw_range_deg import_settings_sha256 collision_settings_sha256 clearance_envelope_radius_m",
        "native geometry",
    )
    require(
        isinstance(native["object_path"], str)
        and native["object_path"].startswith("/Game/")
        and "." in native["object_path"],
        "Explicit native object path required",
    )
    for key in (
        "package_sha256",
        "import_settings_sha256",
        "collision_settings_sha256",
    ):
        digest(native[key], key)
    evidence(native["evidence"], code_sha, "native_mesh_bounds_support")
    for key in ("bounds_min_m", "bounds_max_m", "root_anchor_m"):
        vector(native[key], 3, key)
    require(
        all(a < b for a, b in zip(native["bounds_min_m"], native["bounds_max_m"])),
        "Nondegenerate native bounds required",
    )
    support = native["support_points_m"]
    require(
        isinstance(support, list) and bool(support), "Native support points required"
    )
    for point in support:
        vector(point, 3, "support point")
        require(
            all(
                lo <= coordinate <= hi
                for lo, coordinate, hi in zip(
                    native["bounds_min_m"], point, native["bounds_max_m"]
                )
            ),
            "Support point outside measured mesh bounds",
        )
    require(
        len({tuple(point) for point in support}) == len(support),
        "Duplicate support point",
    )
    for key in ("uniform_scale_range", "yaw_range_deg"):
        vector(native[key], 2, key)
        require(native[key][0] <= native[key][1], "Reversed " + key)
    require(native["uniform_scale_range"][0] > 0, "Positive uniform scale required")
    number(native["clearance_envelope_radius_m"], "clearance envelope", 0)

    materials = record["materials"]
    require(
        isinstance(materials, list) and bool(materials),
        "Bound material receipts required",
    )
    slots = []
    displacement = 0.0
    for material in materials:
        fields(
            material,
            "slot package_sha256 source_receipt native_evidence uv_metres_per_repeat max_displacement_m",
            "material binding",
        )
        text(material["slot"], "material slot")
        slots.append(material["slot"])
        digest(material["package_sha256"], "material package SHA256")
        evidence(
            material["source_receipt"],
            code_sha,
            "material_source_receipt",
            require_current=False,
        )
        evidence(material["native_evidence"], code_sha, "native_material_binding")
        vector(material["uv_metres_per_repeat"], 2, "material physical UV scale")
        require(
            all(v > 0 for v in material["uv_metres_per_repeat"]),
            "Positive material physical scale required",
        )
        # This bound is in final WORLD metres after the maximum admitted mesh
        # scale/transform; a local-space shader amplitude cannot be used here.
        number(material["max_displacement_m"], "final world material WPO extent", 0)
        displacement = max(displacement, material["max_displacement_m"])
    require(len(set(slots)) == len(slots), "Duplicate material slot")
    terrain = record["terrain"]
    fields(
        terrain,
        "source_manifest_sha256 valid_height_mask_sha256 grid world_mapping vertical_datum ue_z_offset_m interpolation owner_id owner_class native_package_sha256 collision_settings_sha256 evidence",
        "terrain binding",
    )
    for key in (
        "source_manifest_sha256",
        "valid_height_mask_sha256",
        "native_package_sha256",
        "collision_settings_sha256",
    ):
        digest(terrain[key], key)
    require(
        terrain["grid"] == GRID and terrain["world_mapping"] == MAPPING,
        "Unadmitted source grid/mapping",
    )
    for key in ("vertical_datum", "interpolation", "owner_id", "owner_class"):
        text(terrain[key], key)
    number(terrain["ue_z_offset_m"], "explicit terrain Z mapping")
    evidence(terrain["evidence"], code_sha, "native_ground_identity")

    contact = record["contact"]
    fields(
        contact,
        "policy_evidence orientation support_mode max_slope_deg max_support_residual_m max_float_m max_penetration_m embedding_m max_source_native_delta_m source_uncertainty_m",
        "contact policy",
    )
    evidence(contact["policy_evidence"], code_sha, "measured_contact_policy")
    require(
        contact["orientation"] in {"upright", "follow_support"},
        "Unknown orientation policy",
    )
    require(
        contact["support_mode"] == "sampled_only",
        "Continuous support requires separate geometric proof",
    )
    for key in (
        "max_support_residual_m",
        "max_float_m",
        "max_penetration_m",
        "embedding_m",
        "max_source_native_delta_m",
        "source_uncertainty_m",
    ):
        number(contact[key], key, 0)
    number(contact["max_slope_deg"], "maximum slope degrees", 0, 90)
    require(
        contact["embedding_m"] <= contact["max_penetration_m"],
        "Embedding exceeds declared penetration limit",
    )
    # Until a bounded tilt range is qualified, use the complete 3D envelope
    # for support-following orientation. Upright meshes need only XY rotation.
    root = native["root_anchor_m"]
    axes = (0, 1, 2) if contact["orientation"] == "follow_support" else (0, 1)
    extent = [
        max(
            abs(native["bounds_min_m"][i] - root[i]),
            abs(native["bounds_max_m"][i] - root[i]),
        )
        for i in axes
    ]
    required_radius = (
        math.hypot(*extent) * native["uniform_scale_range"][1] + displacement
    )
    require(
        native["clearance_envelope_radius_m"] >= required_radius,
        "Clearance envelope omits transformed/offcenter/material extent",
    )
    fixtures = record["fixtures"]
    require(
        isinstance(fixtures, dict) and set(fixtures) == set(FIXTURES),
        "Required native qualification fixtures missing/unknown",
    )
    for name, expected in FIXTURES.items():
        fixture = fixtures[name]
        fields(fixture, "outcome ground_owner_id evidence", "native fixture")
        require(
            fixture["outcome"]
            in (
                {"supported", "rejected"}
                if expected == "supported_or_rejected"
                else {expected}
            ),
            "Wrong expected fixture outcome: " + name,
        )
        if fixture["outcome"] == "supported":
            require(
                fixture["ground_owner_id"] == terrain["owner_id"],
                "Fixture supported by wrong ground owner",
            )
        else:
            require(
                fixture["ground_owner_id"] is None,
                "Rejected fixture retains stale ground owner",
            )
        evidence(fixture["evidence"], code_sha, "native_fixture:" + name)
    raw = json.dumps(
        record, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return {
        "schema_version": 1,
        "issue": 365,
        "status": "STRUCTURALLY_VALID_QUALIFICATION_BINDING_ONLY",
        "record_sha256": hashlib.sha256(raw).hexdigest(),
        "proof_authenticity": "NOT_VERIFIED",
        "placement": False,
        "native_execution": "NOT_VERIFIED",
        "visual_acceptance": "NOT_VERIFIED",
        "performance_pass": False,
        "support_claim": "sampled_only",
    }
