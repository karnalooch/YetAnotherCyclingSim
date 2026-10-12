"""Issue #365 transient red site review in the *real* saved Sa Calobra Landscape.

Runs in one owned Unreal Editor, never saves the accepted map or any package.
The historical five vegetation-selector XY sites are NOT rock placement admission.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import traceback

import unreal


REQUIRED_PRODUCER = "d361e7651d16ff424ae4e812c7d8cbe1fe81d662"
REQUIRED_RUN = "38278235093-1"
EXPECTED_IDS = ["P0", "P1", "P2", "P3", "P4"]
EXPECTED_XY = [
    [16800, 70400],
    [4800, 96800],
    [184800, 180800],
    [181600, 189600],
    [91200, 200800],
]
ACTIVE = None
QUIT_TICK = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def site_check(manifest, readback):
    require(manifest["source_producer_sha"] == REQUIRED_PRODUCER, "Wrong producer")
    require(manifest["source_run"] == REQUIRED_RUN, "Wrong original run")
    require(
        manifest["scope"] == "OWNER_VISUAL_DIAGNOSTIC_NOT_PLACEMENT"
        and manifest["placement"] is False
        and manifest["qualified_assets"] == []
        and manifest["full_qualification"] is False
        and manifest["performance_pass"] is False,
        "Diagnostic scope drift",
    )
    sites = manifest["markers"]
    require(
        len(sites) == 5
        and [site["id"] for site in sites] == EXPECTED_IDS
        and [site["xy_cm"] for site in sites] == EXPECTED_XY,
        "Exactly five frozen historical sites are required",
    )
    cases = readback["cases"]
    require(
        readback["code_sha"] == REQUIRED_PRODUCER
        and readback["status"] == "COLLECTION_CONTACT_FRESH_READBACK"
        and readback["placement"] is False
        and len(cases) == 100
        and len({(c["mesh_id"], c["point_index"]) for c in cases}) == 100
        and len({c["mesh_id"] for c in cases}) == 20,
        "Historical complete 20x5 contact matrix missing",
    )
    for index, site in enumerate(sites):
        matched = [case for case in cases if case["point_index"] == index]
        require(
            len(matched) == 20
            and all(
                c["world_xy_cm"] == site["xy_cm"]
                and c["policy_decision"]["status"] == "REJECTED"
                for c in matched
            )
            and site["status"] == "REJECTED"
            and site["reason"] == "HISTORICAL_VEGETATION_DIAGNOSTIC_NOT_ROCK_ADMITTED",
            "Site input/decision differs: " + site["id"],
        )
    return sites


def stage_check(project_root, manifest):
    stage = read_json(project_root / "staged-files.json")
    require(stage["expected_head"] == REQUIRED_PRODUCER, "Stage producer SHA drift")
    review_dir = project_root / "proof/collection-contact-review"
    completed = read_json(review_dir / "launcher-completed.json")
    require(
        completed["action"] == "collection-contact-review"
        and completed["code_sha"] == REQUIRED_PRODUCER
        and type(completed["exit_code"]) is int
        and completed["exit_code"] == 0
        and completed["staged_bytes_unchanged"] is True
        and completed["proof_admission"] == "LOCAL_DIAGNOSTIC_ONLY",
        "Historical real GPU producer did not exit zero",
    )
    phase_file = review_dir / "contact-fresh-phase.json"
    require(
        identity(phase_file)
        == {
            "bytes": manifest["source_contact_fresh_bytes"],
            "sha256": manifest["source_contact_fresh_sha256"],
        },
        "Historical native contact phase hash differs",
    )
    return site_check(manifest, read_json(phase_file))


class RedReview:
    def __init__(self, project, output, manifest, tool_sha):
        self.project = project
        self.output = output
        self.manifest = manifest
        self.tool_sha = tool_sha
        self.sites = stage_check(project, manifest)
        self.world = None
        self.actors = None
        self.landscape = None
        self.owned = []
        self.index = 0
        self.current = None
        self.finished = False
        self.report = {
            "schema_version": 1,
            "issue": 365,
            "status": "FAILED",
            "producer_sha": REQUIRED_PRODUCER,
            "review_tool_sha": tool_sha,
            "scope": "OWNER_VISUAL_DIAGNOSTIC_NOT_PLACEMENT",
            "owner_decision": "PENDING",
            "placement": False,
            "qualified_assets": [],
            "performance_pass": False,
            "map_saved": False,
            "terrain_modified": False,
            "marker_color": manifest["color_rgba"],
            "markers": [],
            "captures": [],
        }
        self.map_package = manifest["map_package"]
        rel = self.map_package.removeprefix("/Game/")
        self.map_path = project / "Content" / (rel + ".umap")
        self.before = identity(self.map_path)
        require(
            self.before["sha256"] == manifest["source_map_sha256"],
            "Accepted map bytes differ",
        )

    def start(self):
        from scripts.ue.sa_calobra_pcg_terrain_contact import unpack

        require(unreal.EditorLoadingAndSavingUtils.new_blank_map(False), "Blank world failed")
        require(
            unreal.EditorLoadingAndSavingUtils.load_map(self.map_package),
            "Accepted Landscape map load failed",
        )
        self.world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        require(
            self.world.get_path_name().split(".")[0] == self.map_package,
            "Wrong live world",
        )
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        all_actors = self.actors.get_all_level_actors()
        grounds = [a for a in all_actors if isinstance(a, unreal.LandscapeProxy)]
        require(len(grounds) == 1, "Expected exactly one real Landscape")
        self.landscape = grounds[0]
        self.transform_before = str(self.landscape.get_actor_transform())
        for site in self.sites:
            x, y = site["xy_cm"]
            hit = unreal.SystemLibrary.line_trace_single(
                self.world,
                unreal.Vector(x, y, 150000),
                unreal.Vector(x, y, -150000),
                unreal.TraceTypeQuery.ECC_VISIBILITY,
                True,
                [a for a in all_actors if a != self.landscape],
                unreal.DrawDebugTrace.NONE,
                True,
            )
            ground = unpack(hit, self.landscape)
            require(ground is not None, "Missing real Landscape hit: " + site["id"])
            z = float(ground["position_cm"][2])
            marker = self.actors.spawn_actor_from_class(
                unreal.TextRenderActor,
                unreal.Vector(x, y, z + 180.0),
                unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0),
                transient=True,
            )
            require(marker is not None, "Red label actor unavailable")
            self.owned.append(marker)
            marker.set_actor_label("PCG365_REVIEW_RED_" + site["id"])
            component = marker.get_component_by_class(unreal.TextRenderComponent)
            require(component is not None, "Text render component unavailable")
            component.set_text(site["id"] + "  REJECTED  /  REVIEW")
            component.set_text_render_color(unreal.Color(255, 32, 32, 255))
            component.set_world_size(155.0)
            self.report["markers"].append({
                "id": site["id"],
                "xy_cm": site["xy_cm"],
                "ground_z_cm": z,
                "text_z_cm": z + 180.0,
                "label": "REJECTED / REVIEW",
                "collision_owner": self.landscape.get_path_name(),
                "marker_actor": marker.get_path_name(),
                "transient": True,
                "production_placement": False,
            })
        require(len(self.report["markers"]) == 5, "Five marker actors required")
        self.next_site()
        return self

    def next_site(self):
        from scripts.ue import sa_calobra_pcg_boulder_capture as capture

        site = self.sites[self.index]
        record = self.report["markers"][self.index]
        x, y = site["xy_cm"]
        target = unreal.Vector(x, y, record["ground_z_cm"] + 160.0)
        self.current = capture.start_capture(
            self.world,
            target,
            self.output / site["id"],
            self.complete_site,
            framing_radius_cm=430.0,
            warmup_captures=2,
            review_views=2,
            review_dynamic_sun=True,
        )

    def complete_site(self, result):
        try:
            require(
                result["status"] == "CAPTURE_COMPLETED"
                and len(result["frames"]) == 2
                and len(result["warmup_frames"]) == 2,
                "Real native GPU frames incomplete",
            )
            for frame in result["frames"]:
                path = self.output / self.sites[self.index]["id"] / frame["file"]
                data = path.read_bytes()
                require(
                    data[:8] == b"\x89PNG\r\n\x1a\n"
                    and data[12:16] == b"IHDR"
                    and struct.unpack(">II", data[16:24]) == (1920, 1080)
                    and identity(path)
                    == {"bytes": frame["size_bytes"], "sha256": frame["sha256"]},
                    "Native PNG hash/dimensions differ",
                )
            self.report["captures"].append({
                "id": self.sites[self.index]["id"],
                "status": "REAL_LANDSCAPE_DIAGNOSTIC_ONLY",
                "capture": result,
            })
            self.index += 1
            if self.index < len(self.sites):
                self.next_site()
            else:
                self.stop()
        except Exception:
            self.stop(traceback.format_exc())

    def stop(self, error=None):
        if self.finished:
            return
        self.finished = True
        failures = []
        if self.actors:
            for actor in reversed(self.owned):
                try:
                    require(self.actors.destroy_actor(actor), "Transient red marker cleanup failed")
                except Exception:
                    failures.append(traceback.format_exc())
        try:
            require(
                identity(self.map_path) == self.before,
                "Accepted map bytes changed during marker preview",
            )
            require(
                str(self.landscape.get_actor_transform()) == self.transform_before,
                "Landscape transform changed during marker preview",
            )
        except Exception:
            failures.append(traceback.format_exc())
        self.report["terrain_file_before"] = self.before
        self.report["terrain_file_after"] = identity(self.map_path)
        if error or failures:
            self.report["error"] = "\n".join(([error] if error else []) + failures)
        else:
            self.report["status"] = "REAL_LANDSCAPE_RED_REVIEW_CAPTURED"
        self.output.mkdir(parents=True, exist_ok=True)
        path = self.output / "red-review-receipt.json"
        with path.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(self.report, output, indent=2, sort_keys=True, allow_nan=False)
            output.write("\n")
        finish_editor()


def finish_editor():
    global QUIT_TICK
    ticks = 0

    def quit_after_tick(delta):
        global QUIT_TICK
        nonlocal ticks
        ticks += 1
        if ticks < 20:
            return
        unreal.unregister_slate_post_tick_callback(QUIT_TICK)
        QUIT_TICK = None
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        unreal.SystemLibrary.quit_editor()

    QUIT_TICK = unreal.register_slate_post_tick_callback(quit_after_tick)


def main():
    global ACTIVE
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    project = Path(unreal.Paths.project_dir()).resolve()
    sys.path.insert(0, str(project))
    output = Path(os.environ["YACS_PCG365_RED_REVIEW_OUTPUT"]).resolve()
    tool_sha = os.environ["YACS_PCG365_RED_REVIEW_SHA"]
    request = Path(os.environ["YACS_PCG365_RED_REVIEW_MANIFEST"]).resolve()
    require(output.is_relative_to(Path("D:/yacs/work/pcg365-red-review").resolve()),
            "Unsafe output root")
    require(tool_sha and len(tool_sha) == 40, "Exact tool HEAD required")
    manifest = read_json(request)
    try:
        ACTIVE = RedReview(project, output, manifest, tool_sha)
        ACTIVE.start()
    except Exception:
        report = {
            "status": "FAILED",
            "error": traceback.format_exc(),
            "issue": 365,
            "review_tool_sha": tool_sha,
            "placement": False,
            "qualified_assets": [],
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "red-review-receipt.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        unreal.log_error(report["error"])
        finish_editor()


main()
