from __future__ import annotations

import json
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from scripts.assets.probe_google_street_view_metadata import (
    ProbeError,
    request_metadata,
    sanitize_metadata,
    validate_request,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "sa-calobra-street-view-metadata.yml"


class FakeResponse:
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit: int) -> bytes:
        return self.body


class StreetViewMetadataTests(unittest.TestCase):
    def test_missing_api_key_fails_before_network_request(self):
        with self.assertRaisesRegex(
            ProbeError, "GOOGLE_STREET_VIEW_API_KEY is missing"
        ):
            request_metadata(
                latitude=39.8304238,
                longitude=2.8167622,
                radius_m=20,
                source="outdoor",
                api_key="",
                opener=lambda *_args, **_kwargs: self.fail("network request executed"),
            )

    def test_request_uses_metadata_endpoint_without_exposing_key_in_payload(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "status": "OK",
                    "pano_id": "pano-test",
                    "date": "2026-07",
                    "location": {"lat": 39.8304442, "lng": 2.8167225},
                }
            )

        payload = request_metadata(
            latitude=39.8304238,
            longitude=2.8167622,
            radius_m=20,
            source="outdoor",
            api_key="secret-value",
            opener=opener,
        )
        query = parse_qs(urlsplit(captured["url"]).query)
        self.assertEqual(query["key"], ["secret-value"])
        self.assertEqual(query["source"], ["outdoor"])
        self.assertEqual(captured["timeout"], 20)
        self.assertNotIn("secret-value", json.dumps(payload))

    def test_receipt_is_metadata_only_and_measures_snap(self):
        receipt = sanitize_metadata(
            {
                "status": "OK",
                "pano_id": "Q0IzBsfssGl-EEeEOAGuLA",
                "date": "2026-07",
                "location": {"lat": 39.8304442, "lng": 2.8167225},
                "copyright": "not retained",
            },
            latitude=39.8304238,
            longitude=2.8167622,
            radius_m=20,
            max_snap_m=10,
            source="outdoor",
        )
        self.assertEqual(receipt["status"], "OK")
        self.assertLess(receipt["panorama"]["snap_distance_m"], 5)
        self.assertTrue(receipt["panorama"]["within_max_snap_m"])
        self.assertFalse(receipt["image_pixels_requested"])
        self.assertFalse(receipt["metric_geometry_admitted"])
        self.assertNotIn("copyright", json.dumps(receipt))

    def test_non_ok_status_does_not_retain_google_error_message(self):
        receipt = sanitize_metadata(
            {"status": "REQUEST_DENIED", "error_message": "secret detail"},
            latitude=39.8,
            longitude=2.8,
            radius_m=20,
            max_snap_m=20,
            source="outdoor",
        )
        self.assertEqual(receipt["status"], "REQUEST_DENIED")
        self.assertIsNone(receipt["panorama"])
        self.assertNotIn("secret detail", json.dumps(receipt))

    def test_distant_panorama_is_retained_but_not_admitted(self):
        receipt = sanitize_metadata(
            {
                "status": "OK",
                "pano_id": "distant-pano",
                "location": {"lat": 39.831, "lng": 2.817},
            },
            latitude=39.8304238,
            longitude=2.8167622,
            radius_m=50,
            max_snap_m=10,
            source="outdoor",
        )
        self.assertGreater(receipt["panorama"]["snap_distance_m"], 10)
        self.assertFalse(receipt["panorama"]["within_max_snap_m"])

    def test_request_validation_fails_closed(self):
        invalid = (
            (91.0, 2.8, 20, 20.0, "outdoor"),
            (39.8, 181.0, 20, 20.0, "outdoor"),
            (39.8, 2.8, 51, 20.0, "outdoor"),
            (39.8, 2.8, 20, 21.0, "outdoor"),
            (39.8, 2.8, 20, 20.0, "indoor"),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ProbeError):
                validate_request(*values)

    def test_workflow_is_owner_only_main_metadata_on_self_hosted_runner(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "github.actor == github.repository_owner",
            "github.ref == 'refs/heads/main'",
            "runs-on: [self-hosted, yacs-ue58]",
            "GOOGLE_STREET_VIEW_API_KEY: ${{ secrets.GOOGLE_STREET_VIEW_API_KEY }}",
            "::add-mask::",
            "probe_google_street_view_metadata.py",
            "retention-days: 3",
        ):
            self.assertIn(token, text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("maps/api/streetview?", text)
        self.assertNotIn("upload image", text.lower())


if __name__ == "__main__":
    unittest.main()
