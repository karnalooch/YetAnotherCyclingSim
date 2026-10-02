import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

from scripts.assets.prepare_ma2141_road_preview import (
    PROFILE, build_trial, read_profile,
)


class PavementTrialTests(unittest.TestCase):
    def test_real_hairpin_solid_is_closed_and_supported_on_plane(self):
        _, samples = read_profile()
        vertices, triangles, contact = build_trial(
            samples, lambda x, y: 600 + (x-484000)*.01, (483000.25,4409516.25))
        self.assertEqual(contact["r16_contact_status"], "PASS")
        self.assertEqual(contact["native_unreal_contact_status"], "PENDING")
        self.assertEqual(len(vertices), 30050)
        counts = Counter(tuple(sorted(e)) for a,b,c in triangles
                         for e in ((a,b),(b,c),(c,a)))
        self.assertEqual(set(counts.values()), {2})
        directed = Counter(e for a,b,c in triangles for e in ((a,b),(b,c),(c,a)))
        self.assertTrue(all(directed[(b,a)] == n for (a,b),n in directed.items()))

    def test_curved_ground_exposes_between_vertex_contact_failure(self):
        import math
        _, samples = read_profile()
        _, _, contact = build_trial(samples,
            lambda x,y: 600+0.5*math.sin(x*5)*math.cos(y*5), (483000.25,4409516.25))
        self.assertEqual(contact["r16_contact_status"], "FAIL")
        self.assertGreater(contact["floating_centroid_count"], 0)
        self.assertGreater(contact["penetrating_centroid_count"], 0)

    def test_edges_cannot_silently_be_promoted_to_geographic_truth(self):
        raw = json.loads(PROFILE.read_text())
        raw["geographic_width_admitted"] = True
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"profile.json"
            p.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "promote"):
                read_profile(p)

    def test_image_mutation_is_rejected(self):
        raw = json.loads(PROFILE.read_text())
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/"profile.json"
            p.write_text(json.dumps(raw))
            (p.parent/raw["imagery_file"]).write_bytes(b"wrong image")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_profile(p)


if __name__ == "__main__":
    unittest.main()
