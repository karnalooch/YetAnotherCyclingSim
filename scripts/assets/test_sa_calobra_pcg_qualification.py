"""Synthetic structural fixtures; never native qualification evidence."""

import copy
import unittest

from sa_calobra_pcg_qualification import FIXTURES, validate_qualification
from prepare_sa_calobra_world_graph_inputs import GRID, MAPPING


def fixture():
    code = "a" * 40
    sha = "b" * 64

    def evidence(kind):
        return {"sha256": sha, "code_sha": code, "kind": kind, "status": "COMPLETE"}

    return {
        "schema_version": 1,
        "issue": 365,
        "code_sha": code,
        "asset": {
            "catalog_id": "synthetic_test_only",
            "kind": "StaticMesh",
            "lifecycle_status": "imported",
            "source_sha256": sha,
            "source_size_bytes": 42,
            "source_url": "https://example.invalid/fixture",
            "license_id": "synthetic_fixture",
            "license_evidence": evidence("license"),
            "regional_rationale": "test only; no real regional admission",
            "intended_bands": [0],
            "excluded_uses": ["real_scene"],
        },
        "native": {
            "object_path": "/Game/Fixture/SM_Test.SM_Test",
            "package_sha256": sha,
            "evidence": evidence("native_mesh_bounds_support"),
            "bounds_min_m": [-1, -1, 0],
            "bounds_max_m": [1, 1, 2],
            "root_anchor_m": [0, 0, 0],
            "support_points_m": [[0, 0, 0]],
            "uniform_scale_range": [1, 1],
            "yaw_range_deg": [-180, 180],
            "import_settings_sha256": sha,
            "collision_settings_sha256": sha,
            "clearance_envelope_radius_m": 1.5,
        },
        "materials": [
            {
                "slot": "surface",
                "package_sha256": sha,
                "source_receipt": evidence("material_source_receipt"),
                "native_evidence": evidence("native_material_binding"),
                "uv_metres_per_repeat": [1, 1],
                "max_displacement_m": 0.01,
            }
        ],
        "terrain": {
            "source_manifest_sha256": sha,
            "valid_height_mask_sha256": sha,
            "grid": copy.deepcopy(GRID),
            "world_mapping": copy.deepcopy(MAPPING),
            "vertical_datum": "fixture_datum",
            "ue_z_offset_m": 0,
            "interpolation": "fixture_nearest",
            "owner_id": "fixture_ground",
            "owner_class": "LandscapeComponent",
            "native_package_sha256": sha,
            "collision_settings_sha256": sha,
            "evidence": evidence("native_ground_identity"),
        },
        "contact": {
            "policy_evidence": evidence("measured_contact_policy"),
            "orientation": "upright",
            "support_mode": "sampled_only",
            "max_slope_deg": 15,
            "max_support_residual_m": 0.01,
            "max_float_m": 0.01,
            "max_penetration_m": 0.02,
            "embedding_m": 0,
            "max_source_native_delta_m": 0.03,
            "source_uncertainty_m": 0.02,
        },
        "fixtures": {
            name: {
                "outcome": "rejected" if expected != "supported" else "supported",
                "ground_owner_id": "fixture_ground"
                if expected == "supported"
                else None,
                "evidence": evidence("native_fixture:" + name),
            }
            for name, expected in FIXTURES.items()
        },
    }


class QualificationTests(unittest.TestCase):
    def test_binding_never_admits_proof_or_placement(self):
        record = fixture()
        result = validate_qualification(record)
        self.assertFalse(result["placement"])
        self.assertEqual(result["proof_authenticity"], "NOT_VERIFIED")
        self.assertEqual(result, validate_qualification(record))
        self.assertEqual(record["asset"]["lifecycle_status"], "imported")

    def test_texture_and_historical_approval_rejected(self):
        for key, value in (("kind", "Texture2D"), ("lifecycle_status", "approved")):
            record = fixture()
            record["asset"][key] = value
            with self.assertRaises(ValueError):
                validate_qualification(record)

    def test_missing_unknown_and_wrong_sha_proof_rejected(self):
        for key, value in (
            ("status", "NOT_RUN"),
            ("sha256", "unknown"),
            ("code_sha", "c" * 40),
            ("kind", "texture_preview"),
        ):
            record = fixture()
            record["native"]["evidence"][key] = value
            with self.assertRaises(ValueError):
                validate_qualification(record)

    def test_retained_source_receipts_reuse_own_producer_sha(self):
        record = fixture()
        record["asset"]["license_evidence"]["code_sha"] = "d" * 40
        record["materials"][0]["source_receipt"]["code_sha"] = "e" * 40
        self.assertFalse(validate_qualification(record)["placement"])
        record["materials"][0]["native_evidence"]["code_sha"] = "e" * 40
        with self.assertRaises(ValueError):
            validate_qualification(record)

    def test_tolerances_must_be_explicit_finite_numbers(self):
        for value in ("REQUIRED_UNSET", None, True, -1, float("nan")):
            record = fixture()
            record["contact"]["max_float_m"] = value
            with self.assertRaises(ValueError):
                validate_qualification(record)

    def test_complete_footprint_offcenter_scale_and_wpo(self):
        for section, key, value in (
            ("native", "root_anchor_m", [1, 0, 0]),
            ("native", "uniform_scale_range", [1, 2]),
        ):
            record = fixture()
            record[section][key] = value
            with self.assertRaises(ValueError):
                validate_qualification(record)
        record = fixture()
        record["materials"][0]["max_displacement_m"] = 1
        with self.assertRaises(ValueError):
            validate_qualification(record)

    def test_support_and_material_scale(self):
        record = fixture()
        record["native"]["support_points_m"] = [[0, 0, -1]]
        with self.assertRaises(ValueError):
            validate_qualification(record)
        record = fixture()
        record["materials"][0]["uv_metres_per_repeat"] = [0, 1]
        with self.assertRaises(ValueError):
            validate_qualification(record)

    def test_ground_source_and_fixture_owner(self):
        for section, key, value in (
            ("terrain", "vertical_datum", "UNKNOWN"),
            ("terrain", "valid_height_mask_sha256", None),
            ("contact", "support_mode", "continuous"),
        ):
            record = fixture()
            record[section][key] = value
            with self.assertRaises(ValueError):
                validate_qualification(record)
        record = fixture()
        record["terrain"]["grid"]["pixel_size_m"] = 1
        with self.assertRaises(ValueError):
            validate_qualification(record)
        for name in ("flat", "nodata"):
            record = fixture()
            record["fixtures"][name]["ground_owner_id"] = "unrelated_collider"
            with self.assertRaises(ValueError):
                validate_qualification(record)

    def test_fixture_coverage_and_schema_fail_closed(self):
        record = fixture()
        del record["fixtures"]["generated_collider"]
        with self.assertRaises(ValueError):
            validate_qualification(record)
        record = fixture()
        record["terrain"]["material_height_exr"] = "fake_ground"
        with self.assertRaises(ValueError):
            validate_qualification(record)


if __name__ == "__main__":
    unittest.main()
