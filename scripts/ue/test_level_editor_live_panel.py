"""Offline protocol tests for the loopback live-authoring panel."""

import json
import http.client
import threading
import unittest
from unittest.mock import Mock

from scripts.ue import level_editor_live_panel as panel


class LivePanelProtocolTests(unittest.TestCase):
    def test_active_preset_uses_native_readback(self):
        self.assertEqual(panel.active_edge_preset({"transient_mid": False}), "original")
        self.assertEqual(panel.active_edge_preset({"transient_mid": True, "paint_color": [0.75999999, 0.73, 0.66, 1]}), "warm")
        self.assertEqual(panel.active_edge_preset({"transient_mid": True, "paint_color": [1, 0, 1, 1]}), "magenta")
        self.assertEqual(panel.active_edge_preset({"transient_mid": True, "paint_color": [0, 0, 0, 1]}), "custom")

    def test_only_fixed_camera_and_edge_presets_are_admitted(self):
        for value in (
            {"action": "camera", "preset": "road"},
            {"action": "camera", "preset": "hairpin-entry"},
            {"action": "surface", "preset": "worn"},
            {"action": "surface", "preset": "strong"},
            {"action": "edge", "preset": "warm"},
            {"action": "edge", "preset": "cool"},
            {"action": "edge", "preset": "magenta"},
            {"action": "restore", "preset": "original"},
        ):
            with self.subTest(value=value):
                self.assertEqual(panel.parse_control(json.dumps(value).encode()), value)

    def test_arbitrary_paths_coordinates_parameters_and_actions_are_rejected(self):
        for value in (
            {"action": "spawn", "preset": "rock"},
            {"action": "texture", "preset": "/Game/Any"},
            {"action": "camera", "preset": "road", "x": 1},
            {"action": "edge", "preset": "warm", "paint_color": [0, 0, 0, 1]},
            {"action": "edge", "preset": "other"},
            {"action": "restore", "preset": "warm"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                panel.parse_control(json.dumps(value).encode())

    def test_duplicate_json_keys_non_finite_and_oversized_body_fail_closed(self):
        for raw in (
            b'{"action":"camera","action":"edge","preset":"road"}',
            b'{"action":"edge","preset":NaN}',
            b"x" * (panel.BODY_LIMIT + 1),
            b'{"action":"surface","preset":"/Game/arbitrary"}',
            b'{"action":"surface","preset":"worn","texture":"x"}',
            b"[]",
        ):
            with self.subTest(raw=raw[:60]), self.assertRaises(ValueError):
                panel.parse_control(raw)

    def test_native_request_uses_only_fixed_action_data(self):
        edge = panel.native_request(
            {"action": "edge", "preset": "warm"},
            token="session-01", sequence=4, request_id="panel-" + "a" * 32,
        )
        self.assertEqual(edge, {
            "schema_version": 1,
            "session_id": "session-01",
            "request_id": "panel-" + "a" * 32,
            "expected_sequence": 4,
            "action": "set",
            "paint_roughness": 0.9,
            "paint_color": [0.76, 0.73, 0.66, 1.0],
        })
        camera = panel.native_request(
            {"action": "camera", "preset": "road"},
            token="session-01", sequence=5, request_id="panel-" + "b" * 32,
        )
        self.assertEqual(camera["action"], "camera")
        self.assertEqual(camera["preset"], "road")
        self.assertNotIn("location", camera)


class LivePanelHttpTests(unittest.TestCase):
    def setUp(self):
        self.native = Mock()
        self.native.status.return_value = {"connected": True, "editor_pid": 123}
        self.native.apply.return_value = {"status": "COMPLETED", "sequence": 1}
        self.native.last_frame = None
        self.server = panel.ThreadingHTTPServer(("127.0.0.1", 0), panel.Handler)
        self.server.panel = self.native
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        request_headers = {"Host": "127.0.0.1:18785", "Origin": "http://127.0.0.1:18785",
                           "Content-Type": "application/json"}
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_page_status_and_missing_frame(self):
        code, headers, html = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b'<iframe src="http://127.0.0.1/?AutoConnect=true&amp;AutoPlayVideo=true"', html)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(self.request("GET", "/api/status")[0], 200)
        self.assertEqual(self.request("GET", "/api/frame.png")[0], 404)
        self.native.apply.assert_not_called()

    def test_foreign_origin_host_and_unknown_endpoint_cannot_mutate(self):
        body = b'{"action":"edge","preset":"warm"}'
        for headers in ({"Origin": "https://example.org"}, {"Origin": "null"},
                        {"Host": "example.org:18785"}):
            self.assertEqual(self.request("POST", "/api/preview", body, headers)[0], 403)
        self.assertEqual(self.request("POST", "/api/preview?x=1", body)[0], 404)
        self.assertEqual(self.request("POST", "/api/preview", body,
                                      {"Content-Type": "text/plain"})[0], 415)
        self.native.apply.assert_not_called()

    def test_valid_control_is_dispatched_once_and_errors_are_not_retried(self):
        body = b'{"action":"edge","preset":"warm"}'
        self.assertEqual(self.request("POST", "/api/preview", body)[0], 200)
        self.native.apply.assert_called_once_with({"action": "edge", "preset": "warm"})
        self.native.apply.side_effect = ValueError("Native result uncertain")
        self.assertEqual(self.request("POST", "/api/preview", body)[0], 400)
        self.assertEqual(self.native.apply.call_count, 2)

    def test_malformed_input_and_arbitrary_paths_are_rejected(self):
        self.assertEqual(self.request("POST", "/api/preview", b'{"action":"spawn","preset":"rock"}')[0], 400)
        self.assertEqual(self.request("GET", "/../../workspace.json")[0], 404)
        self.native.apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
