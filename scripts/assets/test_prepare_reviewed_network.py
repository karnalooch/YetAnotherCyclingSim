"""Construction acceptance never silently expands or changes reviewed pavement."""

import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts.assets.prepare_current_landscape_roads import prepare_patch
from scripts.assets.prepare_reviewed_network import join_sections
from scripts.geometry.network_pavement import shoulder_sections
from scripts.geometry.network_visual_preview import preview_fingerprint
from scripts.geometry.reviewed_network import (
    construction_windows,
    validate_slab,
    REVIEWED_COMMIT,
)
from scripts.ue.test_current_landscape_roads import network_fixture


def rows(xs, width=5.0, z=1.0):
    return [[[x, 20 + width * (j / 24 - 0.5), z] for j in range(25)] for x in xs]


class ReviewedConstructionTests(unittest.TestCase):
    def test_join_shares_all_endpoint_vertices_and_never_pinches_width(self):
        source, target = rows([0, 0.5, 1]), rows([9, 9.125, 9.25], 5.25, 1.2)
        joined = join_sections(source, target)
        self.assertEqual(joined[0], source[-1])
        self.assertEqual(joined[-1], target[0])
        widths = [math.dist(r[0][:2], r[-1][:2]) for r in joined]
        self.assertGreaterEqual(min(widths), 5.0)
        self.assertLessEqual(max(widths), 5.25)
        self.assertTrue(all(a <= b for a, b in zip(widths, widths[1:])))

    def test_remote_gap_and_fold_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "boundary gap"):
            join_sections(rows([0, 1, 2]), rows([20, 21, 22]))
        with self.assertRaisesRegex(ValueError, "folded"):
            validate_slab(rows([0, 1, 0]))

    def test_default_cut_stays_bounded_and_reviewed_cut_only_lowers(self):
        terrain = np.full((64, 64), 33792, dtype=np.uint16)
        manifest = {"scale_z": 100.0, "location_z_cm": 0.0}
        sections = np.asarray(shoulder_sections(rows([10, 10.5, 11])))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "patch.json"
            with self.assertRaisesRegex(ValueError, "Ordinary 1 m CUT"):
                prepare_patch(sections, terrain, manifest, path)
            self.assertFalse(path.exists())
            receipt = prepare_patch(
                sections, terrain, manifest, path, reviewed_geometry=True
            )
            self.assertGreater(receipt["max_cut_m"], 1)
            self.assertEqual(receipt["blend_mode"], "Min")
            self.assertFalse(receipt["base_dtm_modified"])
            self.assertTrue(receipt["owner_reviewed_geometry"])
            self.assertLessEqual(
                np.max(np.fromfile(path.with_suffix(".f32"), dtype="<f4")), 800
            )

    def test_review_scope_and_construction_changes_fail_closed(self):
        n = network_fixture()
        n["approved"] = []
        n["owner_reviewed"] = [{"sections": rows([0, 1, 2])}]
        fingerprint = n["full_preview_proof"]["fingerprint"]
        n["owner_construction_decision"] = {
            "reviewed_commit": REVIEWED_COMMIT,
            "reviewed_fingerprint": fingerprint,
            "construction_sha256": preview_fingerprint(n["owner_reviewed"]),
        }
        with self.assertRaisesRegex(ValueError, "does not cover"):
            construction_windows(n)
        with patch(
            "scripts.geometry.reviewed_network.REVIEWED_FINGERPRINT", fingerprint
        ):
            self.assertEqual(construction_windows(n), n["owner_reviewed"])
            changed = copy.deepcopy(n)
            changed["owner_reviewed"][0]["sections"][0][0][2] += 1
            with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                construction_windows(changed)


if __name__ == "__main__":
    unittest.main()
