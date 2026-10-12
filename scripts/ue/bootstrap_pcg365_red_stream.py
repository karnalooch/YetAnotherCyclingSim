"""Start the owned real Sa Calobra red-marker Level Editor viewport; keep UE alive.

This is the interactive Pixel Streaming 2 variant, not offscreen PNG capture.
No map/asset persistence, not a rock-mask or placement qualification.
"""
import json
import os
from pathlib import Path
import sys
import traceback

import unreal


LIVE = None


def main():
    global LIVE
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    source_checkout = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(source_checkout))
    from scripts.ue.pcg365_red_marker_preview import RedReview, read_json, require

    project = Path(unreal.Paths.project_dir()).resolve()
    root = Path(os.environ["YACS_PCG365_STAGE"]).resolve()
    session = Path(os.environ["YACS_PCG365_LIVE_SESSION"]).resolve()
    manifest_path = source_checkout / "worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json"
    sha = os.environ["YACS_PCG365_LIVE_HEAD"]
    require(project == root, "Live viewport opened unexpected stage project")
    require(session.is_relative_to(Path("D:/yacs/work/pcg365-live-review").resolve()),
            "Live session output escaped owned work root")
    require(session.is_dir() and not any(session.iterdir()),
            "Live handoff requires a fresh empty session directory")
    require(len(sha) == 40 and all(ch in "0123456789abcdef" for ch in sha),
            "Exact code source revision required")
    try:
        manifest = read_json(manifest_path)
        LIVE = RedReview(project, session / "scene", manifest, sha)
        LIVE.start(persistent=True)
        unreal.log(
            "PCG365_RED_PIXEL_STREAM_SCENE_READY "
            + json.dumps({"source_head": sha, "actor_count": len(LIVE.owned)})
        )
    except Exception:
        error = traceback.format_exc()
        (session / "red-live-error.json").write_text(
            json.dumps({"status": "FAILED", "error": error, "source_sha": sha}),
            encoding="utf-8",
        )
        unreal.log_error(error)
        # The owning launcher sees FAILED and terminates only its own Editor.
        # No automatic recovery and no touching any other Editor process.


if __name__ == "__main__":
    main()
