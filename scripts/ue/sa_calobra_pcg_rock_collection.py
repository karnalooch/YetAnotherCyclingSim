"""Twenty local rock assets and a transient studio; no regional placement admission."""

import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time
import traceback

import unreal

from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue.sa_calobra_pcg_terrain_contact import require, vector

DESTINATION = "/Game/Generated/YACS/PCG365RockCollection20"


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def catalog(root):
    path = root / "rock-collection-catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    require(
        type(data.get("schema_version")) is int and data["schema_version"] == 1,
        "Unknown catalog schema",
    )
    require(
        data.get("placement") is False and data.get("qualified_assets") == [],
        "Catalog cannot admit placement",
    )
    rows = data["variants"]
    require(type(rows) is list and len(rows) == 20, "Exactly twenty variants required")
    ids = set()
    for row in rows:
        name = row["id"]
        require(
            type(name) is str
            and re.fullmatch(r"rock(?:02|06)_(?:0[1-9]|10)", name)
            and name not in ids,
            "Invalid or duplicate variant ID",
        )
        ids.add(name)
        require(
            row["source_relative"] == "rock-collection/" + name + ".fbx",
            "Source path must match variant ID",
        )
        for key in ("sha256", "base_source_sha256"):
            require(
                type(row[key]) is str and re.fullmatch("[0-9a-f]{64}", row[key]),
                "Invalid source hash",
            )
        require(type(row["bytes"]) is int and row["bytes"] > 0, "Invalid source size")
        bounds = row["expected_native_bounds_cm"]
        require(set(bounds) == {"min", "max"}, "Invalid bounds fields")
        for values in bounds.values():
            require(
                type(values) is list
                and len(values) == 3
                and all(type(v) in (int, float) and math.isfinite(v) for v in values),
                "Invalid source bounds",
            )
        require(
            all(a < b for a, b in zip(bounds["min"], bounds["max"])),
            "Degenerate source bounds",
        )
        require(
            type(row["expected_lod0_triangles"]) is int
            and row["expected_lod0_triangles"] > 0,
            "Invalid triangle witness",
        )
        source(root, row)
    require(
        len({row["sha256"] for row in rows}) == 20,
        "Collection requires twenty distinct source byte identities",
    )
    return sorted(rows, key=lambda row: row["id"]), identity(path)


def source(root, row):
    path = (root / row["source_relative"]).resolve(strict=True)
    require(path.is_relative_to(root / "rock-collection"), "Source escaped staging")
    require(
        identity(path) == {"bytes": row["bytes"], "sha256": row["sha256"]},
        "Variant source bytes drift",
    )
    return path


def context(root, output, head, binding):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(
        root == material.project_root()
        and output.is_relative_to(root)
        and output != root,
        "Wrong owned stage/output",
    )
    require(
        type(head) is str and re.fullmatch("[0-9a-f]{40}", head), "Exact HEAD required"
    )
    require(
        binding["code_sha"] == head and len(binding["saved_packages"]) == 7,
        "Binding HEAD/inventory differs",
    )
    material.verify_binding(binding)
    assets = binding["forge_import"]["assets"]
    require(
        material.material_readback(assets)["rock_appearance"]["recipe"]
        == "ROCK_APPEARANCE_V2",
        "Strict Forge V2 required",
    )
    verify_binding_bytes(root, binding)
    return root, output, unreal.load_asset(assets["instance"])


def verify_binding_bytes(root, binding):
    for item in binding["saved_packages"]:
        path = (root / item["path"]).resolve(strict=True)
        require(
            path.is_relative_to(root / "Content"), "Binding package escaped Content"
        )
        require(
            identity(path) == {"bytes": item["bytes"], "sha256": item["sha256"]},
            "Protected Forge package changed",
        )


def native_readback(mesh, row, instance):
    require(isinstance(mesh, unreal.StaticMesh), "Variant is not StaticMesh")
    require(
        len(mesh.static_materials) > 0
        and all(
            mesh.get_material(i) == instance for i in range(len(mesh.static_materials))
        ),
        "Variant Forge slots differ",
    )
    bounds = mesh.get_bounds()
    origin, extent = vector(bounds.origin), vector(bounds.box_extent)
    actual = [origin[i] - extent[i] for i in range(3)] + [
        origin[i] + extent[i] for i in range(3)
    ]
    expected = row["expected_native_bounds_cm"]
    require(
        all(
            math.isfinite(a) and abs(a - b) <= 0.01
            for a, b in zip(actual, expected["min"] + expected["max"])
        ),
        "Native source bounds differ",
    )
    require(
        mesh.get_num_triangles(0) == row["expected_lod0_triangles"],
        "Native triangle count differs",
    )
    return {
        "bounds_cm": {"origin": origin, "extent": extent},
        "lod0_render_triangles": mesh.get_num_triangles(0),
        "slot_count": len(mesh.static_materials),
        "material": instance.get_path_name(),
    }


def import_mesh(root, row, instance):
    package = DESTINATION + "/SM_" + row["id"]
    require(
        not unreal.EditorAssetLibrary.does_asset_exist(package),
        "Preserve existing asset",
    )
    options = unreal.FbxImportUI()
    for key, value in {
        "import_mesh": True,
        "import_as_skeletal": False,
        "import_materials": False,
        "import_textures": False,
        "automated_import_should_detect_type": False,
        "mesh_type_to_import": unreal.FBXImportType.FBXIT_STATIC_MESH,
    }.items():
        options.set_editor_property(key, value)
    data = options.get_editor_property("static_mesh_import_data")
    for key, value in {
        "combine_meshes": True,
        "convert_scene": True,
        "convert_scene_unit": True,
        "import_uniform_scale": 1.0,
        "import_translation": unreal.Vector(),
        "import_rotation": unreal.Rotator(),
        "transform_vertex_to_absolute": True,
        "bake_pivot_in_vertex": False,
        "build_nanite": False,
        "auto_generate_collision": False,
    }.items():
        data.set_editor_property(key, value)
    task = unreal.AssetImportTask()
    for key, value in {
        "filename": str(source(root, row)),
        "destination_path": DESTINATION,
        "destination_name": "SM_" + row["id"],
        "automated": True,
        "replace_existing": False,
        "save": False,
        "options": options,
    }.items():
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = list(task.get_editor_property("imported_object_paths") or [])
    require(
        len(imported) == 1 and str(imported[0]).split(".")[0] == package,
        "Unexpected imported inventory",
    )
    mesh = unreal.load_asset(package)
    require(isinstance(mesh, unreal.StaticMesh), "Import is not StaticMesh")
    for i in range(len(mesh.static_materials)):
        mesh.set_material(i, instance)
    native = native_readback(mesh, row, instance)
    require(
        unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False),
        "Variant save failed",
    )
    source(root, row)
    return {
        "id": row["id"],
        "source": row,
        "package": package,
        "saved_package": material.file_identity(package),
        **native,
    }


def build(root, output, head, binding):
    root, output, instance = context(root, output, head, binding)
    rows, catalog_identity = catalog(root)
    meshes = [import_mesh(root, row, instance) for row in rows]
    require(catalog(root) == (rows, catalog_identity), "Catalog changed during import")
    verify_binding_bytes(root, binding)
    receipt = {
        "schema_version": 1,
        "code_sha": head,
        "status": "ROCK_COLLECTION_ASSETS_SAVED",
        "catalog": catalog_identity,
        "meshes": meshes,
        "binding_saved_packages": binding["saved_packages"],
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "terrain_contact": "NOT_RUN",
        "local_art_geometry_variants": True,
        "native_import_scale": 1.0,
        "map_saved": False,
        "visual_acceptance": "NOT_VERIFIED",
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "rock-collection-inventory.json").open(
        "x", encoding="utf-8"
    ) as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
    return receipt


def reload(root, output, head, binding):
    root, output, instance = context(root, output, head, binding)
    rows, catalog_identity = catalog(root)
    inventory_path = root / "proof/rock-collection/rock-collection-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    require(
        inventory["code_sha"] == head
        and inventory["catalog"] == catalog_identity
        and inventory["placement"] is False
        and inventory["qualified_assets"] == []
        and inventory["binding_saved_packages"] == binding["saved_packages"],
        "Saved inventory binding differs",
    )
    require(len(inventory["meshes"]) == 20, "Saved inventory count differs")
    for row, saved in zip(rows, inventory["meshes"]):
        require(
            saved["id"] == row["id"]
            and saved["source"] == row
            and saved["package"] == DESTINATION + "/SM_" + row["id"],
            "Saved variant identity differs",
        )
        require(
            material.file_identity(saved["package"]) == saved["saved_package"],
            "Saved variant bytes changed",
        )
        native = native_readback(unreal.load_asset(saved["package"]), row, instance)
        require(
            all(saved[k] == value for k, value in native.items()),
            "Fresh readback differs",
        )
    verify_binding_bytes(root, binding)
    require(catalog(root) == (rows, catalog_identity), "Catalog drift during reload")
    return {
        **inventory,
        "status": "ROCK_COLLECTION_ASSETS_FRESH_RELOAD_VERIFIED",
        "inventory_source": identity(inventory_path),
    }


def position_readback(requested, actual, label):
    """Bound Python/native vector serialization only; never a contact tolerance."""
    native = vector(unreal.Vector(*requested))
    actual = vector(actual)
    limit = max(1e-6, max(abs(value) for value in requested) * 2**-22)
    errors = [n - r for n, r in zip(native, requested)]
    record = {
        "requested_cm": list(requested),
        "native_constructed_cm": native,
        "actual_cm": actual,
        "serialization_errors_cm": errors,
        "serialization_guard_cm": limit,
        "contact_tolerance": False,
    }
    require(
        all(math.isfinite(value) for value in requested + native + actual)
        and all(abs(error) <= limit for error in errors)
        and actual == native,
        label + " native position differs: " + repr(record),
    )
    return record


def rotation_values(actor):
    rotation = actor.get_actor_rotation()
    return [float(getattr(rotation, axis)) for axis in ("pitch", "yaw", "roll")]


_ACTIVE = []


class StudioCapture:
    """Owned blank-world preview; floor seating is presentation, never terrain proof."""

    def __init__(self, root, output, head, binding, done):
        self.root, self.output, self.instance = context(root, output, head, binding)
        self.head, self.binding, self.done = head, binding, done
        require(
            not self.output.exists()
            or (self.output.is_dir() and not any(self.output.iterdir())),
            "Preserve existing studio output",
        )
        self.output.mkdir(parents=True, exist_ok=True)
        self.owned, self.callback, self.task = [], None, None
        self.index, self.stopped, self.warmups = 0, False, 2
        self.started = time.monotonic()
        self.report = {
            "schema_version": 1,
            "code_sha": head,
            "status": "RUNNING",
            "placement": False,
            "qualified_assets": [],
            "full_qualification": False,
            "scope": "TRANSIENT_STUDIO_PREVIEW_ONLY",
            "map_saved": False,
            "terrain_contact": "NOT_RUN",
            "visual_acceptance": "PENDING_OWNER",
            "actors": [],
            "lighting": [],
            "frames": [],
            "warmup_frames": [],
        }

    def spawn(self, cls, position, rotation=None):
        actor = self.actors.spawn_actor_from_class(
            cls, unreal.Vector(*position), rotation or unreal.Rotator(), transient=True
        )
        require(actor is not None, "Studio actor spawn failed")
        self.owned.append(actor)
        return actor

    def start(self):
        try:
            from scripts.ue.sa_calobra_pcg_boulder_capture import shadow_readback

            inventory = reload(self.root, self.output, self.head, self.binding)
            self.inventory = inventory
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            existing = self.actors.get_all_level_actors()
            require(
                not any(
                    isinstance(
                        a,
                        (
                            unreal.LandscapeProxy,
                            unreal.StaticMeshActor,
                            unreal.DirectionalLight,
                            unreal.SkyLight,
                        ),
                    )
                    for a in existing
                ),
                "Studio requires parent-owned blank world without geometry or lights",
            )
            meshes = inventory["meshes"]
            max_x = max(2 * m["bounds_cm"]["extent"][0] for m in meshes)
            max_y = max(2 * m["bounds_cm"]["extent"][1] for m in meshes)
            max_z = max(2 * m["bounds_cm"]["extent"][2] for m in meshes)
            pitch_x, pitch_y = max_x * 1.8, max_y * 1.9
            self.width, self.depth = 5 * pitch_x, 4 * pitch_y
            for index, item in enumerate(meshes):
                row, col = divmod(index, 5)
                bounds = item["bounds_cm"]
                origin, extent = bounds["origin"], bounds["extent"]
                location = [
                    (col - 2) * pitch_x - origin[0],
                    (row - 1.5) * pitch_y - origin[1],
                    extent[2] - origin[2],
                ]
                actor = self.spawn(unreal.StaticMeshActor, location)
                actor.set_actor_label(item["id"])
                component = actor.static_mesh_component
                component.set_mobility(unreal.ComponentMobility.MOVABLE)
                require(
                    component.set_static_mesh(unreal.load_asset(item["package"])),
                    "Studio mesh assignment failed",
                )
                actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
                for slot in range(item["slot_count"]):
                    component.set_material(slot, self.instance)
                position = position_readback(
                    location, actor.get_actor_location(), "Studio rock"
                )
                require(
                    vector(actor.get_actor_scale3d()) == [1, 1, 1],
                    "Studio actor scale differs",
                )
                native_readback(
                    component.get_editor_property("static_mesh"),
                    item["source"],
                    self.instance,
                )
                require(
                    component.get_editor_property("mobility")
                    == unreal.ComponentMobility.MOVABLE
                    and all(
                        component.get_material(i) == self.instance
                        for i in range(item["slot_count"])
                    ),
                    "Studio effective component settings differ",
                )
                actual_rotation = rotation_values(actor)
                require(actual_rotation == [0, 0, 0], "Studio rock orientation differs")
                self.report["actors"].append(
                    {
                        "id": item["id"],
                        "package": item["package"],
                        "grid_row": row,
                        "grid_col": col,
                        "location_cm": position["actual_cm"],
                        "position_readback": position,
                        "scale": [1, 1, 1],
                        "rotation_deg": actual_rotation,
                        "preview_floor_z_cm": 0.0,
                        "shadow_readback": shadow_readback(component),
                    }
                )
            floor = self.spawn(unreal.StaticMeshActor, [0, 0, 0])
            floor_component = floor.static_mesh_component
            floor_component.set_mobility(unreal.ComponentMobility.MOVABLE)
            plane = unreal.load_asset("/Engine/BasicShapes/Plane")
            require(
                isinstance(plane, unreal.StaticMesh)
                and floor_component.set_static_mesh(plane),
                "Engine preview plane missing",
            )
            plane_bounds = plane.get_bounds()
            require(
                vector(plane_bounds.origin) == [0, 0, 0]
                and vector(plane_bounds.box_extent) == [50, 50, 0],
                "Engine preview plane dimensions differ",
            )
            floor.set_actor_scale3d(
                unreal.Vector(self.width * 1.5 / 100, self.depth * 1.5 / 100, 1)
            )
            self.report["preview_floor"] = {
                "mesh": plane.get_path_name(),
                "z_cm": float(floor.get_actor_location().z),
                "location_cm": vector(floor.get_actor_location()),
                "rotation_deg": rotation_values(floor),
                "native_bounds_cm": {
                    "origin": vector(plane_bounds.origin),
                    "extent": vector(plane_bounds.box_extent),
                },
                "scale": vector(floor.get_actor_scale3d()),
                "shadow_readback": shadow_readback(floor_component),
            }
            for cls, comp_cls, intensity in (
                (unreal.DirectionalLight, unreal.DirectionalLightComponent, 3.0),
                (unreal.SkyLight, unreal.SkyLightComponent, 0.65),
            ):
                actor = self.spawn(
                    cls, [0, 0, max_z * 4], unreal.Rotator(pitch=-45, yaw=-35)
                )
                component = actor.get_component_by_class(comp_cls)
                component.set_mobility(unreal.ComponentMobility.MOVABLE)
                component.set_intensity(intensity)
                if cls == unreal.SkyLight:
                    component.recapture_sky()
                self.report["lighting"].append(
                    {
                        "class": actor.get_class().get_name(),
                        "intensity": float(component.get_editor_property("intensity")),
                        "rotation_deg": rotation_values(actor),
                        "shadow_readback": shadow_readback(component, light=True),
                    }
                )
            self.camera = self.spawn(unreal.CameraActor, [0, 0, 0])
            self.camera.get_component_by_class(
                unreal.CameraComponent
            ).set_editor_property("field_of_view", 50.0)
            self.views = [
                {
                    "name": "overview",
                    "target": [0, 0, max_z * 0.35],
                    "eye": [
                        self.width * 0.55,
                        -self.depth * 1.45,
                        max(self.width, self.depth) * 1.05,
                    ],
                }
            ]
            for row in range(4):
                y = (row - 1.5) * pitch_y
                self.views.append(
                    {
                        "name": "row-%02d" % (row + 1),
                        "target": [0, y, max_z * 0.4],
                        "eye": [
                            self.width * 0.12,
                            y - self.width * 1.15,
                            self.width * 0.62,
                        ],
                    }
                )
            unreal.AutomationLibrary.set_editor_viewport_view_mode(
                unreal.ViewModeIndex.VMI_LIT
            )
            self.callback = unreal.register_slate_post_tick_callback(self.tick)
            self.submit()
        except Exception:
            self.stop(traceback.format_exc())
        return self

    def submit(self):
        view = self.views[self.index]
        eye, target = unreal.Vector(*view["eye"]), unreal.Vector(*view["target"])
        rotation = unreal.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        camera_position = position_readback(
            view["eye"], self.camera.get_actor_location(), "Studio camera"
        )
        actual_rotation = rotation_values(self.camera)
        require(
            all(
                abs((a - b + 180) % 360 - 180) <= 0.01
                for a, b in zip(
                    actual_rotation, [rotation.pitch, rotation.yaw, rotation.roll]
                )
            ),
            "Studio camera orientation differs",
        )
        actual_fov = float(
            self.camera.get_component_by_class(
                unreal.CameraComponent
            ).get_editor_property("field_of_view")
        )
        require(abs(actual_fov - 50) <= 0.0001, "Studio camera FOV differs")
        unreal.get_editor_subsystem(
            unreal.UnrealEditorSubsystem
        ).set_level_viewport_camera_info(eye, rotation)
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        name = ("warmup-%02d" % (3 - self.warmups)) if self.warmups else view["name"]
        self.pending = {
            "file": name + ".png",
            "view": view,
            "resolution_px": [2560, 1440],
            "camera_rotation_deg": actual_rotation,
            "camera_position_readback": camera_position,
            "fov_deg": actual_fov,
        }
        self.task = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=2560,
            res_y=1440,
            filename=str(self.output / self.pending["file"]),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=unreal.ComparisonTolerance.LOW,
            comparison_notes="YACS local 20-rock studio; no regional qualification",
            delay=1.0,
            force_game_view=True,
        )
        require(
            self.task and self.task.is_valid_task(), "Invalid studio screenshot task"
        )
        self.submitted = time.monotonic()

    def tick(self, _delta):
        if self.stopped or self.task is None:
            return
        try:
            require(
                time.monotonic() - self.submitted <= 120, "Studio screenshot timed out"
            )
            if not self.task.is_task_done():
                return
            self.task = None
            path = self.output / self.pending["file"]
            raw = path.read_bytes()
            require(
                len(raw) > 45
                and raw[:8] == b"\x89PNG\r\n\x1a\n"
                and raw[12:16] == b"IHDR"
                and struct.unpack(">II", raw[16:24]) == (2560, 1440),
                "Invalid studio PNG",
            )
            frame = {**self.pending, **identity(path)}
            if self.warmups:
                self.report["warmup_frames"].append(frame)
                self.warmups -= 1
            else:
                self.report["frames"].append(frame)
                self.index += 1
            if self.index == len(self.views):
                self.stop()
            else:
                self.submit()
        except Exception:
            self.stop(traceback.format_exc())

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        errors = []
        if self.callback is not None:
            try:
                unreal.unregister_slate_post_tick_callback(self.callback)
            except Exception:
                errors.append(traceback.format_exc())
            self.callback = None
        for actor in reversed(self.owned):
            try:
                require(self.actors.destroy_actor(actor), "Owned studio cleanup failed")
            except Exception:
                errors.append(traceback.format_exc())
        try:
            verify_binding_bytes(self.root, self.binding)
            reload(self.root, self.output, self.head, self.binding)
        except Exception:
            errors.append(traceback.format_exc())
        self.report.update(
            status="FAILED" if error or errors else "ROCK_COLLECTION_REAL_GPU_CAPTURED",
            cleanup_errors=errors,
            wall_seconds=time.monotonic() - self.started,
            saved_mesh_packages_unchanged=not errors,
        )
        if error or errors:
            self.report["error"] = error or "Studio cleanup/readback failed"
        with (self.output / "studio-capture-receipt.json").open(
            "x", encoding="utf-8"
        ) as stream:
            json.dump(self.report, stream, indent=2, allow_nan=False)
        if self in _ACTIVE:
            _ACTIVE.remove(self)
        self.done(self.report)


def start_capture(root, output, head, binding, on_complete):
    capture = StudioCapture(root, output, head, binding, on_complete)
    _ACTIVE.append(capture)
    return capture.start()
