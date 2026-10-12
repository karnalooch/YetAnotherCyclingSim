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
    from scripts.live_host.protocol import (
        Rejected, need, load_bounded_json, validate_red_manifest,
        existing_abslog_only, safe_session_root, STAGE,
    )
    from scripts.live_host import live_requests
    from scripts.ue.pcg365_red_marker_preview import RedReview

    session_id = os.environ["YACS_LIVE_SESSION_ID"]
    code_sha = os.environ["YACS_LIVE_SOURCE_SHA"]
    live_root = Path(os.environ["YACS_LIVE_ROOT"]).resolve()
    stage = Path(unreal.Paths.project_dir()).resolve()
    session = safe_session_root(live_root, session_id)
    try:
        need(stage == STAGE.resolve(), "Editor did not load pinned diagnostic stage")
        need(session.parent.parent == live_root, "Session path escaped dedicated live host")
        existing_abslog_only(session)
        manifest = load_bounded_json(
            release / "worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json",
            size=8192,
        )
        validate_red_manifest(manifest)
        LIVE = RedReview(stage, session / "scene", manifest, code_sha)
        LIVE.start(persistent=True)
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
            "marker_count": len(LIVE.owned),
            "world_package": LIVE.map_package,
            "map_saved": False,
            "terrain_modified": False,
            "placement": False,
            "qualified_assets": [],
            "owner_handoff": False,
            "post_job_alive": False,
            "browser_frames_received": False,
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
