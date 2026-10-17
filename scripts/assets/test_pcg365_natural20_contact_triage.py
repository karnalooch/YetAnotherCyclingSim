"""Offline fixtures for a read-only, fail-closed native GPU receipt auditor."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from scripts.assets.pcg365_natural20_contact_triage import assess_archive

SHA = "a" * 40
PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 1920, 1080) + b"\x08\x02\x00\x00\x00" + b"0" * 32


def write_archive(path, change=None):
    data = {}
    captures, meshes, cases = [], [], []
    for idx in range(20):
        mid = f"rock_{idx:02d}"
        meshes.append({"id": mid})
        shots, warmups = [], []
        for name, target in (
            ("boulder-low-angle-01.png", shots),
            ("boulder-low-angle-02.png", shots),
            ("warmup-01.png", warmups),
            ("warmup-02.png", warmups),
        ):
            data[f"{mid}/{name}"] = PNG
            target.append({
                "file": name, "size_bytes": len(PNG),
                "sha256": hashlib.sha256(PNG).hexdigest(),
                "width_px": 1920, "height_px": 1080,
            })
        captures.append({
            "mesh_id": mid,
            "capture": {
                "status": "CAPTURE_COMPLETED", "error": None,
                "frames": shots, "warmup_frames": warmups,
            },
        })
        for site in range(5):
            cases.append({
                "mesh_id": mid, "point_index": site,
                "candidate_id": f"point-{site}",
                "world_xy_cm": [site * 100, site * 200],
                "status": "MEASURED",
                "measurement": {"max_local_slope_deg": 15.0},
                "policy_decision": {
                    "status": "REJECTED", "placement": False,
                    "full_qualification": False,
                    "reasons": ["EXCESSIVE_LOCAL_SLOPE"],
                    "metrics": {
                        "embedding_fraction": 0.65,
                        "exposed_height_fraction": 0.35,
                        "exposed_ray_fraction": 0.5,
                        "valid_ground_fraction": 1.0,
                    },
                },
            })
    fresh = {
        "code_sha": SHA, "status": "COLLECTION_CONTACT_FRESH_READBACK",
        "meshes": meshes, "cases": cases,
        "placement": False, "qualified_assets": [],
    }
    raw = json.dumps(fresh, sort_keys=True).encode("utf-8")
    data["contact-fresh-phase.json"] = raw
    review = {
        "code_sha": SHA, "action": "collection-contact-review",
        "status": "COLLECTION_CONTACT_REAL_GPU_CAPTURED",
        "contact_execution_mode": "THREE_SESSION_MEASURE",
        "placement": False, "full_qualification": False,
        "terrain_modified": False, "map_saved": False,
        "qualified_assets": [],
        "terrain_file_before": {"sha256": "x"},
        "terrain_file_after": {"sha256": "x"},
        "ground_transform_before": [0, 0, 0],
        "ground_transform_after": [0, 0, 0],
        "captures": captures,
        "phases": {
            "contact_readback": {
                "path": "proof/collection-contact-review/contact-fresh-phase.json",
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            },
        },
    }
    marker = {
        "code_sha": SHA, "action": "collection-contact-review",
        "exit_code": 0, "staged_bytes_unchanged": True,
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
    }
    if change:
        change(data, fresh, review, marker)
    data["collection-contact-review-receipt.json"] = json.dumps(review).encode("utf-8")
    data["launcher-completed.json"] = json.dumps(marker).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in data.items():
            archive.writestr(name, content)


class NativeContactTriage(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "review.zip"

    def test_authentic_complete_source_is_not_contact_admission(self):
        write_archive(self.path)
        result = assess_archive(self.path, SHA)
        self.assertEqual(result["cases"], 100)
        self.assertEqual((result["final_png"], result["warmup_png"]), (40, 40))
        self.assertEqual(result["decision_counts"]["REJECTED"], 100)
        self.assertEqual(result["qualified_assets"], [])
        self.assertFalse(result["placement"])

    def test_crash_or_fake_exit_rejected(self):
        for exit_code in (False, -1073741819, 1):
            with self.subTest(exit_code=exit_code):
                write_archive(self.path, lambda data, fresh, review, marker: marker.update(exit_code=exit_code))
                with self.assertRaisesRegex(ValueError, "exit-zero"):
                    assess_archive(self.path, SHA)

    def test_stale_phase_and_wrong_head_rejected(self):
        write_archive(self.path)
        with self.assertRaisesRegex(ValueError, "marker identity"):
            assess_archive(self.path, "b" * 40)
        write_archive(self.path, lambda data, fresh, review, marker: data.__setitem__("contact-fresh-phase.json", b"{}"))
        with self.assertRaisesRegex(ValueError, "phase hash"):
            assess_archive(self.path, SHA)

    def test_landscape_mutation_rejected(self):
        def mutate(data, fresh, review, marker):
            review["terrain_file_after"] = {"sha256": "different"}
        write_archive(self.path, mutate)
        with self.assertRaisesRegex(ValueError, "Frozen terrain"):
            assess_archive(self.path, SHA)

    def test_modified_real_png_rejected(self):
        write_archive(self.path, lambda data, fresh, review, marker: data.__setitem__("rock_00/boulder-low-angle-01.png", PNG + b"tamper"))
        with self.assertRaisesRegex(ValueError, "PNG hash"):
            assess_archive(self.path, SHA)


if __name__ == "__main__":
    unittest.main()
