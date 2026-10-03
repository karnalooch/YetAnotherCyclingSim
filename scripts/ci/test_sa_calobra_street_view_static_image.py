from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from scripts.assets.capture_google_street_view_static import (
    CaptureError,
    request_image,
    validate_request,
    write_atomic_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "sa-calobra-street-view-static-image.yml"
JPEG = b"\xff\xd8\xffdiagnostic-image\xff\xd9"


class FakeHeaders:
    def get(self, name: str, default: str = "") -> str:
        if name.lower() == "content-type":
            return "image/jpeg"
        return default


class FakeResponse:
    headers = FakeHeaders()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, _limit: int) -> bytes:
        return JPEG


class StreetViewStaticImageTests(unittest.TestCase):
    def test_missing_key_fails_before_network_request(self):
        with self.assertRaisesRegex(CaptureError, "API_KEY is missing"):
            request_image(
                pano_id="Q0IzBsfssGl-EEeEOAGuLA",
                width=640,
                height=640,
                scale=2,
                heading=123.6,
                pitch=-22,
                fov=90,
                api_key="",
                opener=lambda *_args, **_kwargs: self.fail("network request executed"),
            )

    def test_request_is_one_exact_static_image(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse()

        image = request_image(
            pano_id="Q0IzBsfssGl-EEeEOAGuLA",
            width=640,
            height=640,
            scale=2,
            heading=123.6,
            pitch=-22,
            fov=90,
            api_key="secret-value",
            opener=opener,
        )
        split = urlsplit(captured["url"])
        query = parse_qs(split.query)
        self.assertEqual(split.path, "/maps/api/streetview")
        self.assertEqual(query["pano"], ["Q0IzBsfssGl-EEeEOAGuLA"])
        self.assertEqual(query["size"], ["640x640"])
        self.assertEqual(query["scale"], ["2"])
        self.assertEqual(query["return_error_code"], ["true"])
        self.assertEqual(query["key"], ["secret-value"])
        self.assertEqual(captured["timeout"], 30)
        self.assertEqual(image, JPEG)

    def test_invalid_view_parameters_fail_closed(self):
        invalid = (
            ("bad pano!", 640, 640, 2, 123.6, -22.0, 90.0),
            ("pano", 641, 640, 2, 123.6, -22.0, 90.0),
            ("pano", 640, 640, 3, 123.6, -22.0, 90.0),
            ("pano", 640, 640, 2, 360.0, -22.0, 90.0),
            ("pano", 640, 640, 2, 123.6, -91.0, 90.0),
            ("pano", 640, 640, 2, 123.6, -22.0, 121.0),
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(CaptureError):
                validate_request(*values)

    def test_atomic_image_output_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "street-view.jpg"
            write_atomic_bytes(output, JPEG)
            self.assertEqual(output.read_bytes(), JPEG)
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(),
                hashlib.sha256(JPEG).hexdigest(),
            )

    def test_workflow_requires_owner_main_and_billable_confirmation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "workflow_dispatch:",
            "github.actor == github.repository_owner",
            "github.ref == 'refs/heads/main'",
            "inputs.confirm_billable_request == true",
            "runs-on: [self-hosted, yacs-ue58]",
            "GOOGLE_STREET_VIEW_API_KEY: ${{ secrets.GOOGLE_STREET_VIEW_API_KEY }}",
            "--width 640",
            "--height 640",
            "--scale 2",
            "retention-days: 1",
        ):
            self.assertIn(token, text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("schedule:", text)

    def test_workflow_defaults_to_confirmed_target_panorama(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('default: "Q0IzBsfssGl-EEeEOAGuLA"', text)
        self.assertIn('default: "123.6"', text)
        self.assertIn('default: "-22"', text)
        self.assertIn('default: "90"', text)
        self.assertEqual(text.count("capture_google_street_view_static.py"), 2)


if __name__ == "__main__":
    unittest.main()
