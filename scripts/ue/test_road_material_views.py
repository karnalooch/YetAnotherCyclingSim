"""Meaningful coverage and rejection checks on the actual retained camera CSV."""

import csv
import hashlib
import io
from pathlib import Path
import unittest

from scripts.ue import road_material_views as views
from scripts.proof.sa_calobra_shoulder_contact import FRAME_IDS

ROOT = Path(__file__).resolve().parents[2]


class WholeNetworkViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = (ROOT / views.SURVEY).read_bytes()

    def altered(self, change):
        reader = csv.DictReader(io.StringIO(self.raw.decode("utf-8-sig")))
        names, rows = reader.fieldnames, list(reader)
        change(rows)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)
        raw = output.getvalue().encode()
        return raw, hashlib.sha256(raw).hexdigest()

    def test_real_survey_covers_every_occupied_cell_and_exception(self):
        plan = views.select_network_views(self.raw)
        self.assertEqual(plan["source_window_count"], 185)
        self.assertEqual(len(plan["occupied_road_cells"]), 24)
        self.assertEqual([r["frame_id"] for r in plan["frames"][:4]], list(FRAME_IDS))
        directions = {}
        for row in plan["frames"]:
            cell = tuple(int(v // 25000) for v in row["road_position_cm"][:2])
            directions.setdefault(cell, set()).add(row["direction"])
        self.assertEqual(len(directions), 24)
        self.assertTrue(all(value == {"forward", "reverse"} for value in directions.values()))
        for name in ("nudo-0", "nudo-1", "nudo-2", "accepted-hairpin"):
            self.assertEqual({r["direction"] for r in plan["frames"] if r["window_id"] == name},
                             {"forward", "reverse"})
        self.assertFalse(plan["whole_area_owner_accepted"])
        self.assertFalse(plan["exhaustive_road_pixel_visibility"])
        self.assertEqual(plan, views.select_network_views(self.raw))

    def test_different_source_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash/size"):
            views.select_network_views(self.raw + b"\n")

    def test_missing_direction_rejected_even_with_reauthenticated_fixture(self):
        raw, digest = self.altered(lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, "paired travel direction"):
            views.select_network_views(raw, digest)

    def test_duplicate_camera_rejected(self):
        raw, digest = self.altered(lambda rows: rows.append(dict(rows[0])))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            views.select_network_views(raw, digest)

    def test_changed_coordinate_pair_rejected(self):
        raw, digest = self.altered(lambda rows: rows[0].update(road_position_cm="[124073,39968,66568]"))
        with self.assertRaisesRegex(ValueError, "coordinates differ"):
            views.select_network_views(raw, digest)

    def test_unready_source_frame_rejected(self):
        raw, digest = self.altered(lambda rows: rows[100].update(native_readiness_status="UNKNOWN"))
        with self.assertRaisesRegex(ValueError, "provenance"):
            views.select_network_views(raw, digest)


if __name__ == "__main__":
    unittest.main()
