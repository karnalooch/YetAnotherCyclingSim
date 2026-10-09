"""Save and freshly render the retained whole-map material in an isolated map.

Only ``prepare`` assigns a material. ``reload`` and ``render`` audit the saved
binding without repairing it. No canonical map, geometry, lights or LOD policy
are authored; visual acceptance remains an explicit owner decision.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import runpy
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))

from scripts.assets.install_sa_calobra_whole_map_prep import validate_proof  # noqa: E402
from scripts.assets.restore_workspace_data import safe_path  # noqa: E402
from scripts.manage_local_workspace import digest, load_workspace  # noqa: E402
from scripts.ue import sa_calobra_whole_map_prep as prep  # noqa: E402
from scripts.ue.prepare_landscape_capture import prepare_capture  # noqa: E402
from scripts.ue.sa_calobra_detail_capture import decode_png  # noqa: E402

MAP = prep.MASTER_PACKAGE + "/L_SaCalobraMaterialReview"
CANONICAL_SHA = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
MAP_FILE = "Content/" + MAP.removeprefix("/Game/") + ".umap"
CANONICAL_FILE = "Content/" + prep.MAP.removeprefix("/Game/") + ".umap"
VIEW_NAMES = tuple(f"ground-{x}-{y}" for x in range(3) for y in range(3)) + (
    "overview-north",
    "overview-south",
)
SUFFIXES = (".uasset", ".umap", ".uexp", ".ubulk", ".uptnl", ".m.ubulk")


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read_json(path):
    return json.loads(prep.checked_bytes(path, 8 * 1024 * 1024).decode("utf-8-sig"))


def selected_views(capture):
    """Use the actual completed capture plan, including its X-then-Y order."""
    rows = capture.get("capture_plan", [])
    require(
        capture.get("capture_plan_sha256")
        == hashlib.sha256(prep.canonical(rows)).hexdigest(),
        "Source capture plan hash differs",
    )
    result = []
    for name in VIEW_NAMES:
        matches = [
            row
            for row in rows
            if row.get("frame_id") == name and row.get("mode") == "prepared"
        ]
        require(len(matches) == 1, "Missing or duplicate captured pose: " + name)
        row = matches[0]
        values = row.get("camera", []) + row.get("target", [])
        require(
            len(values) == 6
            and all(type(v) in (int, float) and math.isfinite(v) for v in values),
            "Non-finite or incomplete source pose",
        )
        require(
            row.get("fov") == (60.0 if name.startswith("ground-") else 58.0),
            "Source camera FOV differs",
        )
        result.append(
            {
                "name": name,
                "location_cm": row["camera"],
                "target_cm": row["target"],
                "fov_deg": row["fov"],
            }
        )
    return result


def verify_assets(rows, root=None):
    root = ROOT if root is None else root
    require(isinstance(rows, list) and rows, "Empty consumer asset inventory")
    names = set()
    for row in rows:
        name = row.get("path")
        require(
            isinstance(name, str)
            and name.startswith("Content/")
            and name.casefold() not in names,
            "Invalid or duplicate consumer asset path",
        )
        path = safe_path(root, name)
        require(
            path.is_file()
            and path.stat().st_size == row.get("size_bytes")
            and digest(path) == row.get("sha256"),
            "Consumer asset bytes differ: " + name,
        )
        names.add(name.casefold())


def normalized(value):
    if isinstance(value, str):
        for package in (prep.MAP, MAP):
            # Native world-owned object paths contain both package and world
            # object basename: /Game/L_Name.L_Name:PersistentLevel.Actor.
            world_object = package + "." + package.rsplit("/", 1)[-1]
            value = value.replace(world_object + ":", "<scene>.<world>:")
            if value == world_object:
                value = "<scene>.<world>"
            value = value.replace(package + ".", "<scene>.")
        return value
    if isinstance(value, (list, tuple)):
        return [normalized(item) for item in value]
    if isinstance(value, dict):
        return {normalized(key): normalized(item) for key, item in value.items()}
    return value


def snapshot(api, world, landscape, map_file):
    # Reuse the installed native foundation's actor/layer/trace witness. Include
    # separate mesh bindings and every component's LOD policy in the comparison.
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    value = foundation["scene_snapshot"](world, landscape, map_file)
    del value["saved_map_sha256"]
    value["separate_mesh_materials"] = prep.mesh_material_snapshot(api)
    value["component_forced_lod"] = sorted(
        (component.get_path_name(), int(component.get_editor_property("forced_lod")))
        for component in landscape.get_components_by_class(api.LandscapeComponent)
    )
    return normalized(value)


def landscape_for(api, package):
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(
        world.get_path_name().split(".")[0] == package, "Wrong loaded consumer package"
    )
    actors = api.GameplayStatics.get_all_actors_of_class(world, api.Landscape)
    require(len(actors) == 1, "Expected one accepted Landscape")
    return world, actors[0]


def terrain_bounds(api, components):
    # Same installed API and all-component bounds envelope as the source capture.
    bounds = [float("inf"), float("-inf")] * 3
    for component in components:
        origin, extent, _radius = api.SystemLibrary.get_component_bounds(component)
        for index, axis in enumerate(("x", "y", "z")):
            bounds[2 * index] = min(
                bounds[2 * index], float(getattr(origin, axis) - getattr(extent, axis))
            )
            bounds[2 * index + 1] = max(
                bounds[2 * index + 1],
                float(getattr(origin, axis) + getattr(extent, axis)),
            )
    require(
        all(math.isfinite(value) for value in bounds)
        and all(bounds[index] <= bounds[index + 1] for index in (0, 2, 4)),
        "Saved Landscape bounds are invalid",
    )
    return bounds


def inventory(material_files):
    rows = [
        dict(path=row["path"], sha256=row["sha256"], size_bytes=row["size_bytes"])
        for row in material_files
    ]
    for channels in prep.source_assets().values():
        for source in channels.values():
            rows.extend(
                dict(
                    path=row["file"], sha256=row["sha256"], size_bytes=row["size_bytes"]
                )
                for row in prep.package_files(source["asset"])
            )
    return rows


def map_members():
    primary = ROOT / MAP_FILE
    rows = []
    for path in sorted(primary.parent.glob(primary.stem + ".*")):
        require(
            path.name.removeprefix(primary.stem) in SUFFIXES and path.is_file(),
            "Unexpected saved-map sidecar",
        )
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
            }
        )
    require(
        any(row["path"] == MAP_FILE for row in rows), "Saved consumer map is absent"
    )
    return rows


def prepare(api, root, proof_root, head, material_files, evidence, master_receipt):
    require(
        not list((ROOT / MAP_FILE).parent.glob(Path(MAP_FILE).stem + ".*")),
        "Existing derived map collision; no overwrite",
    )
    require(
        api.EditorLoadingAndSavingUtils.load_map(str(ROOT / CANONICAL_FILE))
        is not None,
        "Accepted source map did not load",
    )
    world, landscape = landscape_for(api, prep.MAP)
    master, instance = (
        api.load_asset(prep.MASTER_PATH),
        api.load_asset(prep.INSTANCE_PATH),
    )
    prep.verify_instance(api, master, instance, master_receipt)
    assets = inventory(material_files)
    verify_assets(assets)
    before = snapshot(api, world, landscape, ROOT / CANONICAL_FILE)
    binding = prep.LandscapeBinding(api, landscape, master, instance)
    original_overrides = [
        (component, binding.overrides[component.get_path_name()])
        for component in binding.components
    ]
    failure, errors = None, []
    try:
        binding.apply()
        require(
            snapshot(api, world, landscape, ROOT / CANONICAL_FILE) == before,
            "Scene or geometry witness changed during material assignment",
        )
        require(
            api.EditorLoadingAndSavingUtils.save_map(world, MAP),
            "Derived material map save failed",
        )
        require(
            snapshot(api, world, landscape, ROOT / MAP_FILE) == before,
            "Scene or geometry witness changed during derived save",
        )
        require(digest(ROOT / CANONICAL_FILE) == CANONICAL_SHA, "Canonical map changed")
        verify_assets(assets)
    except Exception as exc:
        failure = exc
    finally:
        if binding.applied:
            # Save-as can rename objects even on a partial failure. Keep each
            # component's original override by object identity across that rename.
            binding.overrides = {
                component.get_path_name(): previous
                for component, previous in original_overrides
            }
            current_meshes = prep.mesh_material_snapshot(api)
            if normalized(current_meshes) == normalized(binding.other_materials):
                binding.other_materials = current_meshes
            errors = binding.restore()
    require(not errors, "Material rollback failed: " + "; ".join(errors))
    if failure is not None:
        raise failure
    assets.extend(map_members())
    capture = read_json(
        proof_root / "capture/whole-map-prep/whole-map-prep-receipt.json"
    )
    views = selected_views(capture)
    bounds = terrain_bounds(api, binding.components)
    traversal = [
        dict(
            views[index],
            location_cm=[
                *views[index]["location_cm"][:2],
                max(views[index]["location_cm"][2], bounds[5] + 2000.0),
            ],
        )
        for index in (0, 4, 8)
    ]
    manifest = {
        "schema_version": 1,
        "status": "SAVED_MATERIAL_CONSUMER_PREPARED",
        "exact_sha": head,
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "map_package": MAP,
        "map_sha256": digest(ROOT / MAP_FILE),
        "canonical_map_package": prep.MAP,
        "canonical_map_sha256": CANONICAL_SHA,
        "terrain_sha256": CANONICAL_SHA,
        "terrain_identity_kind": "immutable_canonical_accepted_map",
        "expected_material_parent": prep.MASTER_PATH,
        "expected_material_instance": prep.INSTANCE_PATH,
        "assets": sorted(assets, key=lambda row: row["path"]),
        "component_count": 1024,
        "geometry_mutation": False,
        "geometry_snapshot": before,
        "geometry_snapshot_sha256": hashlib.sha256(prep.canonical(before)).hexdigest(),
        "geometry_witness_scope": "Frozen source package, actors, component identities, edit layers, nine native traces, mesh bindings and LOD policy",
        "material_recipe_sha256": master_receipt["rendering_recipe_sha256"],
        "source_proof": evidence,
        "source_capture_plan_sha256": capture["capture_plan_sha256"],
        "performance_views": views,
        "traversal": traversal,
        "terrain_bounds_cm": bounds,
        "traversal_clearance_cm": 2000.0,
        "traversal_scope": "diagnostic camera path above the saved Landscape maximum; physical ride not proven",
        "canonical_map_saved": False,
        "visual_acceptance": "PENDING_OWNER",
        "performance_acceptance": "NOT_MEASURED",
    }
    verify_assets(manifest["assets"])
    retain_delivery(root, manifest)
    prep.write_json(root / "consumer-manifest.json", manifest)
    return manifest


def retain_delivery(root, manifest):
    files = []
    prefix = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/"
    for row in manifest["assets"]:
        if row["path"].startswith(prefix):
            source = safe_path(ROOT, row["path"])
            relative = "packages/" + source.name
            destination = safe_path(root, relative)
            require(not destination.exists(), "Retained delivery collision")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            require(
                digest(destination) == row["sha256"], "Retained delivery copy differs"
            )
            row["storage"] = {
                "asset": relative,
                "release": "isolated saved material consumer",
            }
            files.append(dict(row))
    prep.write_json(
        root / "delivery-package-manifest.json", {"schema_version": 1, "files": files}
    )


def reload(api, root, head, master_receipt):
    manifest = read_json(root / "consumer-manifest.json")
    require(
        manifest.get("schema_version") == 1
        and manifest.get("exact_sha") == head
        and manifest.get("map_package") == MAP
        and manifest.get("canonical_map_sha256") == CANONICAL_SHA
        and manifest.get("expected_material_parent") == prep.MASTER_PATH
        and manifest.get("expected_material_instance") == prep.INSTANCE_PATH
        and manifest.get("geometry_mutation") is False
        and manifest.get("producer_sha256_lf")
        == hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "Stale or unsupported consumer manifest",
    )
    verify_assets(manifest.get("assets"))
    require(
        digest(ROOT / MAP_FILE) == manifest.get("map_sha256"),
        "Saved consumer map hash differs",
    )
    require(
        api.EditorLoadingAndSavingUtils.load_map(str(ROOT / MAP_FILE)) is not None,
        "Saved consumer map did not load",
    )
    world, landscape = landscape_for(api, MAP)
    master, instance = (
        api.load_asset(prep.MASTER_PATH),
        api.load_asset(prep.INSTANCE_PATH),
    )
    prep.verify_instance(api, master, instance, master_receipt)
    require(
        landscape.get_editor_property("landscape_material") == instance,
        "Saved Landscape material differs; reload never reapplies",
    )
    binding = prep.LandscapeBinding(api, landscape, master, instance)
    rows = binding.audit()
    require(
        snapshot(api, world, landscape, ROOT / MAP_FILE)
        == manifest.get("geometry_snapshot"),
        "Saved consumer scene differs after fresh load",
    )
    return manifest, world, landscape, binding, rows


class RenderJob:
    """Existing native asynchronous screenshot pattern, without scene rebuild."""

    def __init__(self, api, root, manifest, world, landscape, binding):
        self.api, self.root, self.manifest = api, root, manifest
        self.world, self.landscape, self.binding = world, landscape, binding
        self.handle = self.camera = self.environment = None
        self.frames, self.index, self.prime, self.stopped = [], 0, 0, False
        self.busy = False
        self.report = {
            "schema_version": 1,
            "status": "STARTED",
            "exact_sha": manifest["exact_sha"],
            "map_sha256": manifest["map_sha256"],
            "map_package": MAP,
            "expected_material_parent": prep.MASTER_PATH,
            "component_count": 1024,
            "fresh_process": True,
            "material_reapplied": False,
            "geometry_mutation": False,
            "canonical_map_saved": False,
            "visual_acceptance": "PENDING_OWNER",
            "performance_acceptance": "NOT_MEASURED",
        }

    def start(self):
        self.busy = True
        try:
            # -ExecutePythonScript must retain the interpreter after main()
            # returns while the existing Slate screenshot tasks are pending.
            self.api.EditorPythonScripting.set_keep_python_script_alive(True)
            self.environment = prep.CaptureEnvironment(
                self.api, self.world, self.landscape
            )
            self.camera = self.api.get_editor_subsystem(
                self.api.EditorActorSubsystem
            ).spawn_actor_from_class(self.api.CameraActor, self.api.Vector(0, 0, 0))
            require(self.camera is not None, "Native capture camera spawn failed")
            self.handle = self.api.register_slate_post_tick_callback(self.tick)
            self.begin_view()
        except Exception:
            self.stop(traceback.format_exc())
        finally:
            self.busy = False

    def begin_view(self):
        self.pose = self.manifest["performance_views"][self.index]
        eye, target = (
            self.api.Vector(*self.pose["location_cm"]),
            self.api.Vector(*self.pose["target_cm"]),
        )
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        component = self.camera.get_component_by_class(self.api.CameraComponent)
        component.set_editor_property("field_of_view", self.pose["fov_deg"])
        actual = self.camera.get_actor_location()
        require(
            all(
                abs(float(getattr(actual, axis)) - value) <= 0.001
                for axis, value in zip(("x", "y", "z"), self.pose["location_cm"])
            ),
            "Native saved-consumer camera location readback differs",
        )
        actual_rotation = self.camera.get_actor_rotation()
        require(
            all(
                abs(
                    (
                        float(getattr(actual_rotation, axis))
                        - float(getattr(rotation, axis))
                        + 180
                    )
                    % 360
                    - 180
                )
                <= 0.01
                for axis in ("pitch", "yaw", "roll")
            )
            and abs(
                float(component.get_editor_property("field_of_view"))
                - self.pose["fov_deg"]
            )
            <= 0.001,
            "Native saved-consumer camera rotation or FOV readback differs",
        )
        self.readiness_root = self.root / "readiness" / self.pose["name"]
        prepare_capture(
            self.api,
            self.landscape,
            eye,
            rotation,
            self.readiness_root,
            request_height_mips=False,
        )
        self.prime = 0
        self.submit()

    def submit(self):
        self.path = (
            self.root
            / ("priming" if self.prime < 3 else "frames")
            / (self.pose["name"] + ".png")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        require(
            self.prime < 3 or not self.path.exists(), "Fresh rendered frame collision"
        )
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=prep.RESOLUTION[0],
            res_y=prep.RESOLUTION[1],
            filename=str(self.path),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes="Freshly loaded saved material consumer; owner visual review pending",
            delay=0.0,
            force_game_view=True,
        )
        require(
            self.task and self.task.is_valid_task(), "Native screenshot task invalid"
        )
        self.started = time.monotonic()

    def tick(self, _delta):
        if self.stopped or self.busy:
            return
        self.busy = True
        try:
            require(
                time.monotonic() - self.started <= 90, "Native screenshot timed out"
            )
            if not self.task.is_task_done():
                return
            decode_png(self.path, prep.RESOLUTION)
            if self.prime < 3:
                self.prime += 1
                self.submit()
                return
            self.frames.append(
                dict(
                    self.pose,
                    path=self.path.relative_to(self.root).as_posix(),
                    sha256=digest(self.path),
                    size_bytes=self.path.stat().st_size,
                    readiness_sha256=digest(
                        self.readiness_root / "capture-readiness.json"
                    ),
                )
            )
            self.index += 1
            if self.index == len(VIEW_NAMES):
                self.stop()
            else:
                self.begin_view()
        except Exception:
            self.stop(traceback.format_exc())
        finally:
            self.busy = False

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        errors = [error] if error else []
        for label, action in (
            (
                "callback",
                lambda: (
                    self.api.unregister_slate_post_tick_callback(self.handle)
                    if self.handle is not None
                    else None
                ),
            ),
            (
                "camera",
                lambda: (
                    require(
                        self.api.get_editor_subsystem(
                            self.api.EditorActorSubsystem
                        ).destroy_actor(self.camera)
                        is not False,
                        "Native camera destruction failed",
                    )
                    if self.camera is not None
                    else None
                ),
            ),
            (
                "capture settings",
                lambda: (
                    errors.extend(self.environment.restore())
                    if self.environment
                    else None
                ),
            ),
            ("saved binding", self.binding.audit),
            ("assets", lambda: verify_assets(self.manifest["assets"])),
            (
                "scene",
                lambda: require(
                    snapshot(self.api, self.world, self.landscape, ROOT / MAP_FILE)
                    == self.manifest["geometry_snapshot"],
                    "Scene changed during capture",
                ),
            ),
            (
                "canonical",
                lambda: require(
                    digest(ROOT / CANONICAL_FILE) == CANONICAL_SHA,
                    "Canonical map changed",
                ),
            ),
            (
                "authoring map",
                lambda: require(
                    digest(Path(load_workspace()["project"]) / CANONICAL_FILE)
                    == CANONICAL_SHA,
                    "Authoring map changed",
                ),
            ),
        ):
            try:
                action()
            except Exception as exc:
                errors.append(label + ": " + str(exc))
        if len(self.frames) != len(VIEW_NAMES):
            errors.append("Incomplete fresh rendered view set")
        self.report.update(
            status="FAILED" if errors else "SAVED_MATERIAL_CONSUMER_RENDERED",
            frames=self.frames,
            frame_count=len(self.frames),
            errors=errors,
            saved_assets_unchanged=not errors,
            capture_settings_restored=not errors,
        )
        try:
            prep.write_json(self.root / "fresh-render-receipt.json", self.report)
            if not errors:
                self.manifest["fresh_render_receipt"] = {
                    "path": "fresh-render-receipt.json",
                    "sha256": digest(self.root / "fresh-render-receipt.json"),
                }
                prep.write_json(self.root / "consumer-manifest.json", self.manifest)
        finally:
            # Disk or evidence publication failure must not strand this editor.
            try:
                self.api.EditorPythonScripting.set_keep_python_script_alive(False)
            finally:
                self.api.SystemLibrary.quit_editor()


def main():
    import unreal

    action = os.environ["YACS_MATERIAL_ACTION"]
    require(
        action in ("prepare", "reload", "render"), "Explicit material action required"
    )
    head = os.environ["YACS_2B_EXPECTED_HEAD"]
    require(
        len(head) == 40
        and all(c in "0123456789abcdef" for c in head)
        and subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        == head,
        "Material exact SHA differs",
    )
    config = load_workspace()
    canonical = Path(config["project"]).resolve()
    actual = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    require(
        ROOT != canonical and actual == ROOT, "Material save requires isolated project"
    )
    require(
        unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"),
        "Unverified engine",
    )
    proof_root = Path(os.environ["YACS_MATERIAL_PROOF_ROOT"]).resolve(strict=True)
    root_input = Path(os.environ["YACS_MATERIAL_CONSUMER_ROOT"])
    require(root_input.is_absolute(), "Use absolute consumer evidence directory")
    root = root_input.resolve()
    require(
        not root.is_relative_to(ROOT)
        and root != proof_root
        and root.is_relative_to(proof_root),
        "Consumer evidence must be isolated below the proof root",
    )
    api_evidence = read_json(proof_root / "native-api-evidence.json")
    symbols = {
        symbol
        for row in api_evidence.get("headers", [])
        for symbol in row.get("verified_symbols", [])
    }
    require(
        api_evidence.get("status") == "INSTALLED_PRIMARY_API_SOURCE_VERIFIED"
        and api_evidence.get("exact_sha") == head
        and api_evidence.get("engine_version") == "5.8.2-56702186"
        and {
            "SaveMap",
            "LoadMap",
            "TakeHighResScreenshot",
            "FinishLoadingBeforeScreenshot",
        }
        <= symbols,
        "Installed pinned map-save and screenshot API source evidence missing",
    )
    prep.assert_isolated_bootstrap(unreal)
    require(
        digest(canonical / CANONICAL_FILE) == CANONICAL_SHA
        and digest(ROOT / CANONICAL_FILE) == CANONICAL_SHA,
        "Canonical frozen map differs",
    )
    files, evidence = validate_proof(proof_root)
    require(evidence["exact_sha"] == head, "Completed source material proof is stale")
    verify_assets(files["files"])
    master_receipt = read_json(proof_root / "whole-map-master-receipt.json")
    if action == "prepare":
        require(not root.exists(), "Use a new consumer evidence directory")
        root.mkdir(parents=True)
        prepare(
            unreal, root, proof_root, head, files["files"], evidence, master_receipt
        )
        require(
            digest(canonical / CANONICAL_FILE) == CANONICAL_SHA, "Authoring map changed"
        )
        unreal.SystemLibrary.quit_editor()
    else:
        manifest, world, landscape, binding, rows = reload(
            unreal, root, head, master_receipt
        )
        if action == "reload":
            require(
                digest(canonical / CANONICAL_FILE) == CANONICAL_SHA,
                "Authoring map changed",
            )
            require(
                not (root / "reload-receipt.json").exists(),
                "Fresh reload receipt collision",
            )
            prep.write_json(
                root / "reload-receipt.json",
                {
                    "status": "SAVED_MATERIAL_CONSUMER_RELOADED",
                    "exact_sha": head,
                    "map_package": MAP,
                    "map_sha256": manifest["map_sha256"],
                    "expected_material_parent": prep.MASTER_PATH,
                    "component_count": len(rows),
                    "fresh_process": True,
                    "material_reapplied": False,
                    "geometry_mutation": False,
                    "visual_acceptance": "PENDING_OWNER",
                    "render_admission": "NOT_PROVEN",
                },
            )
            unreal.SystemLibrary.quit_editor()
        else:
            require(
                not (root / "fresh-render-receipt.json").exists(),
                "Fresh-render receipt collision",
            )
            global JOB
            JOB = RenderJob(unreal, root, manifest, world, landscape, binding)
            JOB.start()


if __name__ == "__main__":
    main()
