"""Independent owner-logon UE5 Live Host bootstrap; no GitHub Actions ancestry.

This module is executed by Unreal's Python plugin in the already-authenticated
release. No arbitrary request source is evaluated, and zero source assets save.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import unreal

LIVE = None
BRIDGE = None


def main():
    global LIVE, BRIDGE
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    release = Path(os.environ["YACS_LIVE_RELEASE"]).resolve()
    sys.path.insert(0, str(release))
    from scripts.live_host.protocol import need, existing_abslog_only, safe_session_root
    from scripts.live_host import live_requests
    from scripts.live_host.live_world_road import VerifiedRoadWorld

    session_id = os.environ["YACS_LIVE_SESSION_ID"]
    code_sha = os.environ["YACS_LIVE_SOURCE_SHA"]
    requested_codec = os.environ.get("YACS_LIVE_CODEC", "H264")
    if requested_codec not in ("H264", "VP9"):
        raise ValueError("Unreviewed Pixel Streaming 2 codec")
    world_profile = os.environ.get("YACS_LIVE_WORLD_PROFILE")
    if world_profile != "latest_verified":
        raise ValueError("No reviewed latest-world profile; reject old diagnostics")
    live_root = Path(os.environ["YACS_LIVE_ROOT"]).resolve()
    stage = Path(unreal.Paths.project_dir()).resolve()
    session = safe_session_root(live_root, session_id)
    try:
        need(session.parent.parent == live_root, "Session path escaped dedicated live host")
        existing_abslog_only(session)
        registry_path = release / "scripts/live_host/verified_worlds.json"
        need(registry_path.is_file() and registry_path.stat().st_size <= 8192,
             "No bounded admitted latest-world registry")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        LIVE = VerifiedRoadWorld(
            project=stage,
            session=session,
            registry=registry,
            profile_id=registry["selected_world_id"],
            release=release,
        )
        world_receipt = LIVE.start(unreal)
        BRIDGE = live_requests.attach(
            unreal, live=LIVE, root=live_root, session=session_id,
            source_sha=code_sha,
        )
        # A native receipt is not a browser-video proof, and cannot alone make
        # this Editor "durably alive after GitHub job exit".
        status = {
            "status": "LIVE_SCENE_AND_COMMAND_BRIDGE_READY",
            "session": session_id,
            "code_sha": code_sha,
            "editor_pid": os.getpid(),
            "world_profile_id": "latest_verified",
            "world_id": LIVE.profile_id,
            "world_package": LIVE.map_package,
            "road_native_actor_count": world_receipt["road_native_actor_count"],
            "material_binding_count": world_receipt["material_bindings_verified"],
            "lighting": world_receipt["lighting"],
            "global_lighting_visual_pass": False,
            "map_saved": False,
            "terrain_modified": False,
            "placement": False,
            "qualified_assets": [],
            "owner_handoff": False,
            "post_job_alive": False,
            "browser_frames_received": False,
            "requested_video_codec": requested_codec,
            "negotiated_video_codec_verified": False,
        }
        (session / "live-scene-ready.json").write_text(
            json.dumps(status, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        unreal.log("YACS_LIVE_HOST_SCENE_READY " + json.dumps(status))
    except Exception:
        error = traceback.format_exc()
        try:
            (session / "live-start-failed.json").write_text(
                json.dumps({
                    "status": "FAILED_NO_RETRY",
                    "error": error,
                    "source_sha": code_sha,
                    "session": session_id,
                    "placement": False,
                }, indent=2),
                encoding="utf-8",
            )
        finally:
            # Fatal script errors are not necessary. The owning scheduled-task
            # launcher sees the FAILED receipt and stops only its own Editor.
            unreal.log_warning("YACS_LIVE_HOST_BOOTSTRAP_REJECTED " + error)


if __name__ == "__main__":
    main()
