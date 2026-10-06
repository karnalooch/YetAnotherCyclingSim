"""Serial automatic driver for isolated quality assets; stop on first failure."""

import json
import runpy
import time
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]


class Driver:
    def __init__(self):
        self.quality = runpy.run_path(
            str(ROOT / "scripts/ue/generate_sa_calobra_quality_library.py")
        )
        self.running = False
        self.finished = False
        self.last_check = 0.0
        self.handle = None
        batch = getattr(unreal, "_yacs_quality_library", None)
        if batch is None:
            self.quality["main"]()
        elif batch.phase == "finished":
            raise RuntimeError(
                "Batch already finished; inspect its result before retrying"
            )
        self.handle = unreal.register_slate_post_tick_callback(self.tick)
        self.write("SERIAL_GENERATION_STARTED")

    def write(self, status, error=None):
        batch = getattr(unreal, "_yacs_quality_library", None)
        report = {
            "status": status,
            "error": error,
            "completed_roles": [r["role"] for r in batch.results] if batch else [],
            "map_saved": False,
            "world_assignment": False,
            "rollback_policy": "Original assets untouched; retain isolated candidate assets and failure evidence",
            "visual_acceptance": "pending",
        }
        if batch:
            report["result_directory"] = str(batch.out)
            report["original_scene_preserved"] = (
                self.quality["BASE"]["scene"]() == batch.before
                and self.quality["BASE"]["digest"](batch.map_file) == batch.map_hash
            )
        (ROOT / "Saved/RuntimeProof/quality-library-auto.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        unreal.log("YACS_QUALITY_LIBRARY_AUTO " + json.dumps(report))

    def finish(self, status, error=None):
        if self.finished:
            return
        self.finished = True
        if self.handle is not None:
            unreal.unregister_slate_post_tick_callback(self.handle)
        self.write(status, error)

    def tick(self, _dt):
        if self.running or self.finished or time.monotonic() - self.last_check < 1:
            return
        self.running = True
        self.last_check = time.monotonic()
        try:
            batch = unreal._yacs_quality_library
            if batch.in_tick:
                return
            if batch.phase == "finished":
                result = json.loads((batch.out / "result.json").read_text())
                self.finish(
                    "GENERATED_REVIEW_REQUIRED"
                    if result["status"] == "generated_review_required"
                    else "STOPPED_ON_ERROR",
                    result.get("error"),
                )
            elif batch.phase == "awaiting_next_role":
                # The existing batch verifies scene identity and headroom before
                # each next role. Native render/export remains strictly serial.
                self.quality["main"]()
                self.write("NEXT_ROLE_STARTED")
        except Exception as exc:
            batch = getattr(unreal, "_yacs_quality_library", None)
            if batch and batch.phase not in ("finished", "rendering", "exporting"):
                batch.finish(str(exc))
            self.finish("STOPPED_ON_ERROR", str(exc))
            unreal.log_error("YACS_QUALITY_LIBRARY_AUTO_STOPPED " + str(exc))
        finally:
            self.running = False


def main():
    previous = getattr(unreal, "_yacs_quality_library_auto", None)
    if previous and not previous.finished:
        raise RuntimeError("Automatic generation is already running")
    unreal._yacs_quality_library_auto = Driver()


if __name__ == "__main__":
    main()
