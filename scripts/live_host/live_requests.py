"""Bounded file-queue bridge to an already running YACS Live Host Editor.

No arbitrary scripts, socket listener, process launching, asset saves or shell.
All requests are session+exact-source pinned, replay-checked and owned by a
single live editor thread. A started but incomplete command is never replayed.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from scripts.live_host.protocol import (
    Rejected, need, load_bounded_json, validate_request, file_proof,
    safe_session_root, SITE_IDS,
)

POLL_INTERVAL = 0.75
HEARTBEAT_INTERVAL = 10.0
MAX_PENDING = 32


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_receipt(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(doc, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def atomic_status(path: Path, doc: dict) -> None:
    """State is not proof without matching process identity and fresh heartbeat."""
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(doc, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def focus_site(live, site_id: str, unreal):
    """One five-site camera allowlist; nothing ever edits the Landscape."""
    marker = next((m for m in live.report["markers"] if m["id"] == site_id), None)
    need(marker is not None and site_id in SITE_IDS, "Unknown historical camera site")
    x, y = marker["xy_cm"]
    z = marker["ground_z_cm"]
    target = unreal.Vector(x, y, z + 160)
    eye = unreal.Vector(x - 850, y - 900, z + 900)
    rot = unreal.MathLibrary.find_look_at_rotation(eye, target)
    viewport = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    viewport.set_level_viewport_camera_info(eye, rot)
    observed = viewport.get_level_viewport_camera_info()
    need(observed is not None, "Editor camera cannot be read back")
    # UE Python returns (location, rotation). Do not infer a working viewport
    # merely from a successful setter call.
    where, angle = observed
    need((where - eye).length() <= 1.0, "Native camera readback position drift")
    return {
        "site": site_id,
        "camera_location_cm": [where.x, where.y, where.z],
        "camera_rotation_deg": [angle.pitch, angle.yaw, angle.roll],
    }


def focus_latest_road(live, unreal):
    """Restore the fixed saved v0.3.1 road camera, never transform road actors."""
    need(getattr(live, "profile_id", None) == "sa_calobra_road_v0_3_1",
         "Focus road is restricted to the pinned saved v0.3.1 profile")
    eye = unreal.Vector(*live.camera_cm)
    target = unreal.Vector(*live.target_cm)
    rotation = unreal.MathLibrary.find_look_at_rotation(eye, target)
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    editor.set_level_viewport_camera_info(eye, rotation)
    observed = editor.get_level_viewport_camera_info()
    need(observed is not None and (observed[0] - eye).length() <= 1.0,
         "Current UE native road-camera readback differs")
    return {
        "action": "focus_road",
        "map_package": live.map_package,
        "camera_location_cm": [eye.x, eye.y, eye.z],
        "map_saved": False,
        "road_transformed": False,
    }


def execute_visual_request(live, request: dict, unreal, *, live_root=None, session_root=None) -> dict:
    action = request["action"]
    if action == "focus_road":
        return focus_latest_road(live, unreal)
    if action == "focus_site":
        if getattr(live, "profile_id", None) == "sa_calobra_road_v0_3_1":
            return {
                "action": action, "not_applicable": "OLD_DIAGNOSTIC_SITES",
                "map_saved": False, "placement": False,
            }
        return {"action": action, **focus_site(live, request["site"], unreal)}
    if action == "set_markers_visible":
        if getattr(live, "profile_id", None) == "sa_calobra_road_v0_3_1":
            return {
                "action": action, "not_applicable": "NO_OLD_P0_P4_MARKERS",
                "map_saved": False, "placement": False,
            }
        for marker in live.owned:
            component = marker.get_component_by_class(unreal.TextRenderComponent)
            need(component is not None, "Owned temporary marker disappeared")
            component.set_visibility(request["visible"])
        return {"action": action, "visible": request["visible"], "count": len(live.owned)}
    if action == "inspect":
        report = live.report
        return {
            "action": action,
            "world_profile_id": getattr(live, "profile_id", "legacy_diagnostic"),
            "map_package": live.map_package,
            "marker_ids": [m["id"] for m in report.get("markers", [])],
            "road_native_actor_count": report.get("road_native_actor_count", 0),
            "material_bindings_verified": report.get(
                "material_bindings_verified", 0
            ),
            "lighting": report.get("lighting", {}),
            "map_saved": False,
            "placement": False,
        }
    if action == "run_recipe":
        if getattr(live, "profile_id", None) == "sa_calobra_road_v0_3_1":
            need(
                request.get("intent") == "preview"
                and request.get("recipe") == "rock_asset_audit",
                "Latest accepted road forbids unqualified actor/material edits",
            )
        need(live_root is not None and session_root is not None,
             "Native editor recipe requires the owned Live Host session")
        from scripts.live_host import editor_recipes
        return editor_recipes.load_and_run(
            unreal=unreal, live=live, root=live_root, project=live.project,
            request=request, session_root=session_root,
        )
    raise Rejected("Visual command not authorized")


class LiveRequestLoop:
    def __init__(self, *, root: Path, session: str, source_sha: str, handler):
        self.root = root.resolve()
        self.session = session
        self.source_sha = source_sha
        self.handler = handler
        self.queue = self.root / "inbox" / session
        self.session_root = safe_session_root(self.root, session)
        self.receipts = self.session_root / "commands"
        self.processed = self.session_root / "processed"
        self.queue.mkdir(parents=True, exist_ok=False)
        self.receipts.mkdir(parents=True, exist_ok=False)
        self.processed.mkdir(parents=True, exist_ok=False)
        self.last_sequence = 0
        self.last_poll = 0.0
        self.last_heartbeat = None
        self.alive = True
        self.status_file = self.session_root / "live-heartbeat.json"

    def heartbeat(self, now: float, *, force=False) -> None:
        if (not force and self.last_heartbeat is not None
                and now - self.last_heartbeat < HEARTBEAT_INTERVAL):
            return
        self.last_heartbeat = now
        atomic_status(self.status_file, {
            "schema_version": 1,
            "session": self.session,
            "source_sha": self.source_sha,
            "status": "EDITOR_TICK_ALIVE",
            "sequence": self.last_sequence,
            "updated_utc": utc_now(),
            "owner_handoff": False,
            "placement": False,
            "qualified_assets": [],
        })

    def poll(self, now: float) -> None:
        if not self.alive:
            return
        self.heartbeat(now)
        if now - self.last_poll < POLL_INTERVAL:
            return
        self.last_poll = now
        files = list(self.queue.iterdir())
        need(len(files) <= MAX_PENDING, "Too many requests in bounded live queue")
        for path in sorted(files):
            need(path.is_file() and not path.is_symlink()
                 and path.name.endswith(".json")
                 and len(path.name) <= 72,
                 "Queue contains an untrusted/unready file")
        if not files:
            return
        path = sorted(files)[0]
        # The file writer uses an atomic rename after validation, so every
        # visible .json request must be complete. Do not silently retry.
        value = load_bounded_json(path)
        validate_request(
            value, session=self.session, source_sha=self.source_sha,
            last_sequence=self.last_sequence
        )
        req_id = value["request_id"]
        seq = value["sequence"]
        receipt_id = f"{seq:06d}-{req_id}"
        before = file_proof(path)
        started = self.receipts / (receipt_id + ".started.json")
        finished = self.receipts / (receipt_id + ".result.json")
        new_receipt(started, {
            "status": "STARTED_NO_RETRY", "request": value,
            "input": before, "recorded_utc": utc_now()
        })
        try:
            result = self.handler(value)
            need(type(result) is dict, "Native visual handler did not return a readback")
            status = "COMPLETED_VISUAL_ONLY"
        except Exception as exc:
            result = {"error": type(exc).__name__, "reason": str(exc)[:256]}
            status = "FAILED_NO_RETRY"
        new_receipt(finished, {
            "status": status,
            "request_id": req_id,
            "sequence": seq,
            "input": before,
            "readback": result,
            "map_saved": False,
            "placement": False,
            "recorded_utc": utc_now(),
        })
        # Strictly one request per camera tick, even on rejected responses;
        # do not treat process survival or ack creation as physical admission.
        path.rename(self.processed / path.name)
        if status == "COMPLETED_VISUAL_ONLY":
            self.last_sequence = seq
        else:
            self.alive = False
        self.heartbeat(now, force=True)


_ACTIVE = None
_CALLBACK = None


def attach(unreal, *, live, root: Path, session: str, source_sha: str):
    global _ACTIVE, _CALLBACK
    need(_ACTIVE is None, "Live visual command bridge may be installed only once")
    _ACTIVE = LiveRequestLoop(
        root=root, session=session, source_sha=source_sha,
        handler=lambda value: execute_visual_request(
            live, value, unreal, live_root=root,
            session_root=safe_session_root(root, session),
        ),
    )
    _ACTIVE.heartbeat(time.monotonic(), force=True)

    def on_tick(_delta):
        # An exception deliberately blocks further commands without
        # terminating the Editor, deleting accepted source, or retrying a
        # potentially already executed camera update.
        try:
            _ACTIVE.poll(time.monotonic())
        except Exception as exc:
            _ACTIVE.alive = False
            try:
                new_receipt(_ACTIVE.session_root / "queue-blocked.json", {
                    "status": "BLOCKED_NO_RETRY",
                    "error": type(exc).__name__,
                    "reason": str(exc)[:256],
                    "recorded_utc": utc_now(),
                    "placement": False,
                })
            except OSError:
                pass
            unreal.log_warning("YACS_LIVE_REQUEST_QUEUE_BLOCKED")

    _CALLBACK = unreal.register_slate_post_tick_callback(on_tick)
    return _ACTIVE
