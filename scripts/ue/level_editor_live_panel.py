"""Loopback-only browser controls for one exact retained Level Editor session.

This first panel slice exposes only authenticated camera presets, two fixed
edge-marking diagnostics, and restore. It accepts no asset paths, coordinates,
console commands or Python. The UE process remains the source of the live view.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit
import uuid

from scripts.ue import level_editor_material_bridge as bridge
from scripts.ue import level_editor_material_client as client
from scripts.ue import prepare_level_editor_review as preparation

ROOT = Path(__file__).resolve().parents[2]
PORT = 18785
BODY_LIMIT = 1024
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z")
REQUEST_ID = re.compile(r"panel-[0-9a-f]{32}\Z")
EDGE_PRESETS = {
    "warm": {"paint_roughness": 0.90, "paint_color": [0.76, 0.73, 0.66, 1.0]},
    "cool": {"paint_roughness": 0.90, "paint_color": [0.58, 0.61, 0.63, 1.0]},
    "magenta": {"paint_roughness": 0.90, "paint_color": [1.0, 0.0, 1.0, 1.0]},
}
CAMERA_PRESETS = frozenset(bridge.camera_presets.PRESETS)
HTML_PATH = Path(__file__).with_suffix(".html")
OUTPUT_ROOT = "Saved/RuntimeProof/LevelEditorLivePanel"
LOGGER = logging.getLogger("yacs.level_editor_live_panel")


def active_edge_preset(current: dict) -> str:
    if current.get("transient_mid") is False:
        return "original"
    color = current.get("paint_color", [])
    for name, preset in EDGE_PRESETS.items():
        if len(color) == 4 and all(abs(a - b) < 1e-5 for a, b in zip(color, preset["paint_color"])):
            return name
    return "custom"


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON member")
        value[key] = item
    return value


def parse_control(raw: bytes) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= BODY_LIMIT, "Request exceeds its bound")
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")),
    )
    require(type(value) is dict and set(value) == {"action", "preset"},
            "Control request fields differ")
    action, preset = value["action"], value["preset"]
    if action == "camera":
        require(type(preset) is str and preset in CAMERA_PRESETS, "Camera preset is not allowlisted")
    elif action == "repair":
        require(preset == "nearby", "Only nearby shoulder repair is admitted")
    elif action == "surface":
        require(type(preset) is str and preset in bridge.surface_preview.PRESETS, "Surface preset is not allowlisted")
    elif action == "edge":
        require(type(preset) is str and preset in EDGE_PRESETS, "Edge preset is not allowlisted")
    elif action == "restore":
        require(preset == "original", "Restore preset differs")
    else:
        raise ValueError("Control action is not allowlisted")
    return value


def native_request(control: dict, *, token: str, sequence: int, request_id: str) -> dict:
    require(TOKEN.fullmatch(token) is not None, "Session identity is invalid")
    require(type(sequence) is int and 0 <= sequence < client.HISTORY_LIMIT,
            "Session sequence is outside its bound")
    require(REQUEST_ID.fullmatch(request_id) is not None, "Request identity is invalid")
    request = {
        "schema_version": 1,
        "session_id": token,
        "request_id": request_id,
        "expected_sequence": sequence,
    }
    if control["action"] == "camera":
        return {**request, "action": "camera", "preset": control["preset"]}
    if control["action"] == "repair":
        return {**request, "action": "repair"}
    if control["action"] == "surface":
        return {**request, "action": "surface", "preset": control["preset"], "capture": False}
    if control["action"] == "edge":
        return {**request, "action": "set", "capture": False, **EDGE_PRESETS[control["preset"]]}
    return {**request, "action": "restore"}


class LivePanel:
    def __init__(self, token: str):
        require(TOKEN.fullmatch(token) is not None, "Session token is invalid")
        self.token = token
        self.session_root = preparation.REVIEW_ROOT / (preparation.RUNTIME_SHA[:12] + "-" + token)
        self.session_receipt = self.session_root / client.SESSION_RECEIPT
        self.output_root = bridge.safe_path(ROOT, OUTPUT_ROOT + "/" + token)
        self.lock = threading.Lock()
        self.last_frame: bytes | None = None
        self.last_result: dict | None = None

    def _context(self):
        return client._load_context(self.session_receipt)

    def status(self) -> dict:
        context = self._context()
        history = client._history(context)
        return {
            "connected": True,
            "session_id": self.token,
            "editor_pid": context["identity"]["editor_pid"],
            "sequence": history["sequence"],
            "shoulder_repair": history["current"].get("shoulder_repair"),
            "active_surface_preset": history["current"].get("surface", {}).get("preset", "unavailable"),
            "active_edge_preset": active_edge_preset(history["current"]),
            "map_package": context["identity"]["map_package"],
            "last_result": self.last_result,
        }

    def apply(self, control: dict) -> dict:
        require(self.lock.acquire(blocking=False), "Another live preview request is running")
        try:
            context = self._context()
            history = client._history(context)
            request_id = "panel-" + uuid.uuid4().hex
            request = native_request(
                control, token=self.token, sequence=history["sequence"], request_id=request_id
            )
            self.output_root.mkdir(parents=True, exist_ok=True)
            request_path = bridge.safe_path(self.output_root, request_id + ".request.json")
            output = bridge.safe_path(self.output_root, request_id)
            require(not request_path.exists() and not output.exists(), "Panel request identity collided")
            request_path.write_bytes(bridge.canonical(request).encode("utf-8"))
            result = client.run(self.session_receipt, request_path, output)
            if result.get("status") != "COMPLETED":
                raise ValueError(result.get("error", "Native preview did not complete"))
            frame = None
            for capture in result.get("captures", []):
                if capture.get("priming") is False:
                    frame_path = bridge.safe_path(output, capture["client_path"])
                    identity = bridge.file_identity(frame_path, bridge.PNG_LIMIT)
                    require(identity == {
                        "sha256": capture["sha256"], "size_bytes": capture["size_bytes"]
                    }, "Native panel capture changed after client verification")
                    frame = frame_path.read_bytes()
            self.last_frame = frame
            self.last_result = {
                "status": "COMPLETED",
                "action": request["action"],
                "preset": control["preset"],
                "sequence": result["sequence"],
                "request_id": request_id,
                "frame_available": self.last_frame is not None,
                "camera_after": result.get("camera_after"),
            }
            return self.last_result
        finally:
            self.lock.release()


def _html() -> bytes:
    raw = HTML_PATH.read_bytes()
    require(0 < len(raw) <= 128 * 1024, "Live panel document exceeds its bound")
    return raw


class Handler(BaseHTTPRequestHandler):
    server_version = "YACS-Live-Panel/1"

    @property
    def panel(self) -> LivePanel:
        return self.server.panel

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "").casefold() in {
            f"127.0.0.1:{PORT}", f"localhost:{PORT}"
        }

    def _json(self, status: int, value: dict) -> None:
        raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"status": "BLOCKED", "error": message[:240]})

    def do_GET(self) -> None:
        if not self._host_ok():
            self._error(403, "Loopback Host header is required")
            return
        path = urlsplit(self.path)
        if path.query:
            self._error(400, "Query parameters are not supported")
            return
        elif path.path == "/":
            raw = _html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "img-src 'self' blob:; frame-src http://127.0.0.1 http://localhost; "
                "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(raw)
        elif path.path == "/api/status":
            try:
                self._json(200, self.panel.status())
            except Exception as error:  # noqa: BLE001 - report a bounded status without issuing a write.
                self._json(200, {"connected": False, "error": str(error)[:240]})
        elif path.path == "/api/frame.png":
            frame = self.panel.last_frame
            if frame is None:
                self._error(404, "No completed material capture is available")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(frame)
        else:
            self._error(404, "Endpoint not found")

    def do_POST(self) -> None:
        origin = self.headers.get("Origin", "")
        if not self._host_ok() or origin not in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}:
            self._error(403, "Same-origin loopback control is required")
            return
        if self.path != "/api/preview":
            self._error(404, "Endpoint not found")
            return
        length = self.headers.get("Content-Length", "")
        if not re.fullmatch(r"[0-9]{1,4}", length) or int(length) == 0 or int(length) > BODY_LIMIT:
            self._error(413, "Request body length is invalid")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(400, "Transfer encoding is not supported")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._error(415, "JSON content type is required")
            return
        try:
            control = parse_control(self.rfile.read(int(length)))
            result = self.panel.apply(control)
            self._json(200, result)
        except ValueError as error:
            status = 409 if "Another live preview" in str(error) else 400
            self._error(status, str(error))
        except Exception as error:  # noqa: BLE001 - fail closed and return bounded diagnostics.
            LOGGER.exception("Live panel preview failed")
            self._error(502, "Native preview failed; inspect the retained session receipt")

    def log_message(self, format: str, *args) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)


def serve(token: str) -> None:
    panel = LivePanel(token)
    # Validate the retained exact process and map before creating a listener.
    panel.status()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    server.panel = panel
    LOGGER.info("Live panel ready at http://127.0.0.1:%d/ for session %s", PORT, token)
    server.serve_forever(poll_interval=0.25)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-token", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    serve(args.session_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
