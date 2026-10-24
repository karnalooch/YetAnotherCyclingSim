"""Bounded regional contract regressions; CPU checks are not native proof."""

from copy import deepcopy
import math
import unittest

from scripts.live_host.recipes import rock_contact_scatter as m


def fixture():
    return {
        "schema_version": 2,
        "surface": {
            "surface_id": "window0067-landscape-v1",
            "bounds_xy_cm": [112850, 116200, 113550, 117350],
        },
        "assets": [
            {
                "id": "small",
                "bounds_cm": {"origin": [0, 0, 20], "extent": [30, 40, 20]},
            },
            {
                "id": "offset",
                "bounds_cm": {"origin": [10, -10, 20], "extent": [30, 20, 20]},
            },
        ],
        "placements": [
            {"site": "W0067_R01", "asset_id": "small", "world_xy_cm": [113000, 116450]},
            {
                "site": "W0067_R02",
                "asset_id": "offset",
                "world_xy_cm": [113300, 116350],
            },
            {"site": "W0067_R03", "asset_id": "small", "world_xy_cm": [113350, 116750]},
        ],
    }


class RegionalFootprintTests(unittest.TestCase):
    def test_historical_schema_has_no_regional_claim(self):
        self.assertEqual(m.regional_footprint_checks({"schema_version": 1}), {})

    def test_three_separated_footprints_return_only_bounded_claim(self):
        data = fixture()
        result = m.regional_footprint_checks(data)
        self.assertEqual(set(result), {r["site"] for r in data["placements"]})
        for row in result.values():
            self.assertEqual(row["surface_id"], "window0067-landscape-v1")
            self.assertEqual(row["status"], "PASS_BOUNDED_REGIONAL_FOOTPRINT_ONLY")
            self.assertAlmostEqual(row["radius_cm"], 50)
            self.assertGreaterEqual(row["edge_clearance_cm"], 50)

    def test_center_inside_is_insufficient_when_full_footprint_escapes(self):
        data = fixture()
        data["placements"][0]["world_xy_cm"][0] = 112900
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data)

    def test_native_bounds_are_rechecked_after_import(self):
        data = fixture()
        native = {"small": {"origin": [0, 0, 20], "extent": [150, 150, 20]}}
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data, native)

    def test_origin_offset_counts_in_full_radius(self):
        data = fixture()
        data["assets"][0]["bounds_cm"]["origin"][0] = 120
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data)

    def test_same_batch_rocks_cannot_overlap(self):
        data = fixture()
        data["placements"][1]["world_xy_cm"] = [113050, 116450]
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data)

    def test_pairwise_composition_gap_is_preserved(self):
        data = fixture()
        data["placements"][1]["world_xy_cm"] = [113124, 116450]
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data)
        data["placements"][1]["world_xy_cm"] = [113125, 116450]
        self.assertEqual(len(m.regional_footprint_checks(data)), 3)

    def test_boundary_clearance_threshold_is_inclusive(self):
        data = fixture()
        data["placements"][0]["world_xy_cm"][0] = 112950
        self.assertEqual(len(m.regional_footprint_checks(data)), 3)
        data["placements"][0]["world_xy_cm"][0] -= 0.01
        with self.assertRaises(ValueError):
            m.regional_footprint_checks(data)

    def test_nonfinite_coordinate_or_bound_is_rejected(self):
        for invalid in (math.nan, math.inf, -math.inf):
            for target in ("coordinate", "bounds"):
                with self.subTest(invalid=invalid, target=target):
                    data = deepcopy(fixture())
                    if target == "coordinate":
                        data["placements"][0]["world_xy_cm"][0] = invalid
                    else:
                        data["assets"][0]["bounds_cm"]["extent"][0] = invalid
                    with self.assertRaises(ValueError):
                        m.regional_footprint_checks(data)


class RegionalSurfaceTests(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        import json
        import tempfile

        self.root = Path(__file__).resolve().parents[2]
        self.data = json.loads(
            (
                self.root / "worldgen/live_host/window0067-regional-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.stage = Path(self.temporary.name)
        for key in ("inspection_receipt", "source_screen"):
            proof = self.data["surface"][key]
            target = self.stage / proof["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            source = (
                self.root
                / "docs/experiments/sa-calobra-spatial-treatment-plan-20261013"
                / target.name
            )
            target.write_bytes(source.read_bytes())

    def validate(self, surface=None):
        from unittest.mock import patch

        with patch.object(m, "STAGE", self.stage):
            return m.validate_regional_surface(surface or self.data["surface"])

    def test_retained_inspection_and_screen_validate(self):
        self.assertIsInstance(self.validate(), dict)

    def test_changed_receipt_bytes_are_rejected(self):
        path = self.stage / self.data["surface"]["inspection_receipt"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.validate()

    def test_changed_source_screen_bytes_are_rejected(self):
        path = self.stage / self.data["surface"]["source_screen"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.validate()

    def test_surface_identity_bounds_and_owner_are_fixed(self):
        for key, value in (
            ("surface_id", "another-surface"),
            ("bounds_xy_cm", [112800, 116200, 113550, 117350]),
            ("owner_actor", "/Game/AnotherWorld.Landscape"),
            ("search_manifest_sha256", "0" * 64),
            ("plan_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                surface = deepcopy(self.data["surface"])
                surface[key] = value
                with self.assertRaises(ValueError):
                    self.validate(surface)


if __name__ == "__main__":
    unittest.main()
