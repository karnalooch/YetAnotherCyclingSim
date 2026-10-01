import base64
import copy
import hashlib
import unittest

from scripts.ue.clean_baseline_receipt import validate_receipt


class CleanBaselineReceiptTests(unittest.TestCase):
    def receipt(self):
        png = b"\x89PNG\r\n\x1a\nfixture"
        parity = {"status": "PASS", "sample_count": 4033 * 4033, "mismatch_count": 0}
        return {
            "status": "PASS",
            "exact_sha": "a" * 40,
            "import_process_id": 1,
            "reload_process_id": 2,
            "after_import": parity,
            "after_save_reload": copy.deepcopy(parity),
            "screenshot_base64": base64.b64encode(png).decode(),
            "screenshot_sha256": hashlib.sha256(png).hexdigest(),
        }

    def test_accepts_same_sha_fresh_process_and_matching_payload(self):
        validate_receipt(self.receipt(), "a" * 40)

    def test_rejects_stale_sha_same_process_height_drift_and_tampering(self):
        for change in (
            {"exact_sha": "b" * 40},
            {"reload_process_id": 1},
            {
                "after_save_reload": {
                    "status": "PASS",
                    "sample_count": 4033 * 4033,
                    "mismatch_count": 1,
                }
            },
            {"screenshot_sha256": "0" * 64},
        ):
            with self.subTest(change=change):
                report = self.receipt()
                report.update(change)
                with self.assertRaises(ValueError):
                    validate_receipt(report, "a" * 40)


if __name__ == "__main__":
    unittest.main()
