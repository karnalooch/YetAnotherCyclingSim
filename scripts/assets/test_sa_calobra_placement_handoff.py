"""Check safety semantics rather than granting planting from context evidence."""

import unittest
import tempfile
from pathlib import Path
import numpy as np
from scripts.assets.prepare_sa_calobra_placement_handoff import placement_state, prepare


class PlacementHandoffTests(unittest.TestCase):
    def test_mapped_building_prohibited_and_unmapped_remains_unresolved(self):
        source = np.array([[0, 1, 255]], dtype=np.uint8)
        np.testing.assert_array_equal(placement_state(source), [[255, 0, 255]])
        np.testing.assert_array_equal(source, [[0, 1, 255]])

    def test_no_positive_admission_without_road_and_vegetation_authority(self):
        self.assertFalse((placement_state(np.zeros((3, 3), dtype=np.uint8)) == 1).any())

    def test_unrecognized_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            placement_state(np.array([[2]], dtype=np.uint8))

    def test_existing_output_is_preserved_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sentinel = output / "retained.json"
            sentinel.write_text("retained", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare(output / "missing-source.json", output)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "retained")


if __name__ == "__main__":
    unittest.main()
