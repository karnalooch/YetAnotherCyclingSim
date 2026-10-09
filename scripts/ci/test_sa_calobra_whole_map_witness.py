"""CPU-only whole-map witness contract tests — no Unreal or world mutation."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.ue.sa_calobra_whole_map_witness import (
    WITNESS_IDS,
    WITNESS_MODES,
    audit_witnesses,
    witness_parameters,
    witness_steps,
)


class WholeMapWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "diagnostics").mkdir()
        self.primary, self.diagnostics = [], []
        for name in WITNESS_IDS:
            pose = {
                "frame_id": name,
                "camera_location_cm": [100, 200, 300],
                "target_cm": [0, 0, 0],
                "camera_rotation_deg": [1, 2, 3],
                "fov_deg": 60.0,
            }
            self.primary.append(dict(pose, mode="prepared"))
            for mode in WITNESS_MODES:
                relative = f"diagnostics/{name}-{mode}.png"
                path = self.root / relative
                Image.new("RGB", (96, 72), (200, 200, 200)).save(path)
                data = path.read_bytes()
                # PNG fixtures need >10KB: add a deterministic non-image payload
                # after IEND, as Unreal screenshots allow extra metadata.
                if len(data) < 10000:
                    path.write_bytes(data + bytes([7]) * (10000 - len(data)))
                    data = path.read_bytes()
                self.diagnostics.append(
                    dict(
                        pose,
                        mode=mode,
                        file=relative,
                        size_bytes=len(data),
                        sha256=hashlib.sha256(data).hexdigest(),
                        dynamic_shadows=mode != "no-shadows",
                        material_parameters={
                            "MicroNormalStrength": (
                                0.0 if mode == "flat-normal" else 0.75
                            )
                        },
                    )
                )

    def verify(self):
        return audit_witnesses(self.root, self.primary, self.diagnostics, (96, 72))

    def test_eight_distinct_paired_witnesses_preserve_original_pose(self):
        r = self.verify()
        self.assertEqual(r["frame_count"], 8)
        self.assertEqual(r["camera_count"], 4)
        self.assertEqual(r["visual_acceptance"], "PENDING_OWNER")
        self.assertFalse(r["material_repair_proven"])

    def test_fixed_view_inventory_and_parameter_override(self):
        views = [{"frame_id": name} for name in WITNESS_IDS]
        self.assertEqual(len(witness_steps(views)), 8)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            witness_steps(views[:-1])
        self.assertEqual(
            witness_parameters("flat-normal", {})["MicroNormalStrength"], 0
        )
        self.assertEqual(
            witness_parameters("no-shadows", {})["MicroNormalStrength"], 0.75
        )
        with self.assertRaisesRegex(ValueError, "Unknown"):
            witness_parameters("magic", {})

    def test_missing_or_modified_png_fails_closed(self):
        path = self.root / self.diagnostics[0]["file"]
        path.write_bytes(path.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.verify()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.verify()

    def test_camera_or_shadow_mismatch_fails_closed(self):
        self.diagnostics[0]["target_cm"] = [5, 5, 5]
        with self.assertRaisesRegex(ValueError, "camera"):
            self.verify()
        self.diagnostics[0]["target_cm"] = [0, 0, 0]
        self.diagnostics[0]["dynamic_shadows"] = False
        with self.assertRaisesRegex(ValueError, "shadow"):
            self.verify()

    def test_incomplete_order_or_invalid_normal_rejected(self):
        self.diagnostics.reverse()
        with self.assertRaisesRegex(ValueError, "sequence"):
            self.verify()
        self.diagnostics.reverse()
        self.diagnostics[0]["material_parameters"]["MicroNormalStrength"] = 0.75
        with self.assertRaisesRegex(ValueError, "normal-strength"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
