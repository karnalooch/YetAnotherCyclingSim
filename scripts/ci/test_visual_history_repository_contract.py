from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VISUAL_ROOT = ROOT / "docs" / "visual-history"
README = VISUAL_ROOT / "README.md"


class VisualHistoryRepositoryContractTests(unittest.TestCase):
    def test_policy_requires_repository_retained_images(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("retained directly in this repository", text)
        self.assertIn("CI artifacts are transient", text)
        self.assertIn("record SHA-256 hashes", text)

    def test_accepted_entries_reference_existing_repository_images(self):
        manifests = sorted(VISUAL_ROOT.glob("**/manifest.json"))
        self.assertGreater(len(manifests), 0)

        for manifest_path in manifests:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            visual_status = data.get("status", {}).get("visual_status")
            if visual_status != "VISUAL_ACCEPTED":
                continue

            captures = data.get("captures", [])
            self.assertGreater(
                len(captures),
                0,
                f"{manifest_path}: accepted Visual History has no captures",
            )
            for capture in captures:
                triptych = capture.get("triptych_image")
                self.assertTrue(
                    triptych,
                    f"{manifest_path}: accepted capture {capture.get('capture_id')} has no repository triptych",
                )
                image_path = manifest_path.parent / triptych
                self.assertTrue(
                    image_path.is_file(),
                    f"{manifest_path}: repository image is missing: {triptych}",
                )
                sha256 = capture.get("triptych_sha256")
                self.assertRegex(
                    sha256 or "",
                    r"^[0-9a-f]{64}$",
                    f"{manifest_path}: accepted capture {capture.get('capture_id')} has no SHA-256",
                )


if __name__ == "__main__":
    unittest.main()
