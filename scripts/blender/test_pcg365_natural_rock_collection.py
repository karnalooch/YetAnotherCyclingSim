"""Pure selection contract checks: no bpy import or DCC process."""

import copy
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "natural_rocks", Path(__file__).with_name("build_pcg365_natural_rock_collection.py")
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class NaturalSelectionTests(unittest.TestCase):
    def packet(self):
        ids = sorted(m.IDS)
        request = {
            "schema_version": 1,
            "assets": [{"id": i, "sha256": "a" * 64} for i in ids],
        }
        inspection = {
            "schema_version": 1,
            "status": "ROCK_COMPONENT_SOURCE_INSPECTION_ONLY",
            "request_sha256": m.REQUEST_SHA,
            "assets": [
                {
                    "id": i,
                    "source_sha256_before": "a" * 64,
                    "source_sha256_after": "a" * 64,
                    "objects": [
                        {
                            "name": i + "_LOD0",
                            "type": "MESH",
                            "components": [{"triangle_indices_sha256": "b" * 64}],
                        }
                    ],
                }
                for i in ids
            ],
        }
        selection = {
            "schema_version": 1,
            "inspection_sha256": "c" * 64,
            "selections": [
                {
                    "id": i,
                    "object_name": i + "_LOD0",
                    "component_index": 0,
                    "component_triangles_sha256": "b" * 64,
                    "cut_fraction": 0.10,
                    "post_cut_selection": "KEEP_ALL",
                    "variant_count": 3 if n < 4 else 2,
                }
                for n, i in enumerate(ids)
            ],
        }
        return request, inspection, selection

    def test_exact_twenty_eight_families(self):
        r, i, s = self.packet()
        self.assertEqual(len(m.validate_selection(r, i, s)), 8)
        self.assertTrue(
            all(recipe[0] * recipe[1] * recipe[2] > 0 for recipe in m.RECIPES)
        )

    def test_guessed_object_or_component_rejected(self):
        for field, value in [
            ("object_name", "guessed_LOD0"),
            ("component_index", 1),
            ("component_triangles_sha256", "d" * 64),
        ]:
            r, i, s = self.packet()
            s["selections"][0][field] = value
            with self.assertRaises(ValueError):
                m.validate_selection(r, i, s)

    def test_unbounded_cut_and_counts_rejected(self):
        for field, value in [
            ("cut_fraction", 0.21),
            ("cut_fraction", float("nan")),
            ("variant_count", 4),
            ("post_cut_selection", "AUTO"),
        ]:
            r, i, s = self.packet()
            s["selections"][0][field] = value
            with self.assertRaises(ValueError):
                m.validate_selection(r, i, s)

    def test_source_identity_and_inspection_request_drift_rejected(self):
        r, i, s = self.packet()
        i["assets"][0]["source_sha256_after"] = "d" * 64
        with self.assertRaises(ValueError):
            m.validate_selection(r, i, s)
        r, i, s = self.packet()
        i["request_sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            m.validate_selection(r, i, s)

    def test_duplicate_family_is_not_twenty_sources(self):
        r, i, s = self.packet()
        s["selections"][0] = copy.deepcopy(s["selections"][1])
        with self.assertRaises(ValueError):
            m.validate_selection(r, i, s)


if __name__ == "__main__":
    unittest.main()
