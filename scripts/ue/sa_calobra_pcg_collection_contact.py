"""Saved collection sampled contact; no import, terrain edit or admission."""

import json
import math
from pathlib import Path
import stat
import traceback

import unreal

from scripts.assets.pcg_rock_contact_policy import (
    evaluate,
    trial_policy,
    refined_trial_policy,
)
from scripts.ue import sa_calobra_pcg_rock_collection as collection
from scripts.ue import sa_calobra_pcg_rock_qualification as q
from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue.sa_calobra_pcg_rock_capture import RockCapture, _ACTIVE
from scripts.ue.sa_calobra_pcg_terrain_contact import require, vector


def batch_members(meshes, index):
    require(type(index) is int and 0 <= index < 10, "Invalid contact batch")
    ordered = sorted(meshes, key=lambda m: m["id"])
    require(
        len(ordered) == 20 and len({m["id"] for m in ordered}) == 20,
        "Twenty unique meshes required",
    )
    return ordered[index * 2 : index * 2 + 2]


def complete(grid):
    return (
        grid["sample_count"] > 0
        and grid["valid_ground_count"] == grid["sample_count"]
        and not grid["unpaired_mesh_hits"]
        and bool(grid["fit"])
    )


def measurement(mesh, coarse, fine):
    return {
        "height_cm": mesh["bounds_cm"]["extent"][2] * 2,
        "uniform_scale": 1.0,
        "yaw_deg": 0.0,
        "tilt_deg": 0.0,
        "max_local_slope_deg": fine["max_local_slope_deg"],
        "ground_class": "LandscapeHeightfieldCollisionComponent",
        "sample_count": fine["sample_count"],
        "valid_ground_count": fine["valid_ground_count"],
        "coverage_status": "COMPLETE_SAMPLED_MESH_FOOTPRINT",
        "fit": fine["fit"],
        "refinement": {
            "coarse_grid": coarse["grid_size"],
            "fine_grid": fine["grid_size"],
            "coarse_root_cm": coarse["fit"]["root_zero_sampled_air_cm"],
            "fine_root_cm": fine["fit"]["root_zero_sampled_air_cm"],
            "coarse_embedding_cm": coarse["fit"]["required_embedding_cm"],
            "fine_embedding_cm": fine["fit"]["required_embedding_cm"],
        },
    }


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inputs(root):
    sources = read_json(root / "qualification-sources.json")
    contact = read_json(root / "contact-request.json")
    require(
        contact["placement"] is False and len(contact["points"]) == 5,
        "Five authenticated points required",
    )
    for point in contact["points"]:
        require(
            isinstance(point["candidate_id"], str)
            and len(point["world_xy_cm"]) == 2
            and all(
                type(v) in (int, float) and math.isfinite(v)
                for v in point["world_xy_cm"]
            ),
            "Invalid point",
        )
    return sources, contact


def map_identity(sources):
    package = sources["terrain"]["map_package"]
    require(
        isinstance(package, str) and package.startswith("/Game/"), "Invalid map package"
    )
    relative = package.removeprefix("/Game/")
    require(
        relative
        and all(p not in ("", ".", "..") for p in relative.split("/"))
        and "\\" not in relative
        and ":" not in relative,
        "Unsafe map package",
    )
    content = material.project_root() / "Content"
    path = content / (relative + ".umap")
    require(path.is_file(), "Saved terrain map missing")
    for part in (path, *path.parents):
        require(
            not part.is_symlink()
            and not (
                getattr(part.lstat(), "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            ),
            "Aliased map path refused",
        )
        if part == content:
            break
    require(
        path.resolve(strict=True).is_relative_to(content.resolve(strict=True)),
        "Map escaped Content",
    )
    return q.identity(path)


def verify_marker(marker, head, index):
    require(
        marker.get("action") == f"collection-contact-{index:02d}"
        and marker.get("code_sha") == head
        and type(marker.get("exit_code")) is int
        and marker["exit_code"] == 0
        and marker.get("staged_bytes_unchanged") is True
        and marker.get("proof_admission") == "LOCAL_DIAGNOSTIC_ONLY",
        "Batch launcher failed or action differs",
    )


def ground_identity(ground):
    transform = ground.get_actor_transform()
    rotation = transform.rotation.rotator()
    return {
        "location": vector(transform.translation),
        "scale": vector(transform.scale3d),
        "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
    }


def verify_terrain(before_file, after_file, before_transform, after_transform):
    require(
        before_file == after_file and before_transform == after_transform,
        "Terrain file or transform changed",
    )


def run(root, output, head, binding, batch_index):
    root, output = Path(root).resolve(), Path(output).resolve()
    inventory = collection.reload(root, output, head, binding)
    meshes = batch_members(inventory["meshes"], batch_index)
    sources, contact = inputs(root)
    before = map_identity(sources)
    require(
        unreal.EditorLoadingAndSavingUtils.load_map(sources["terrain"]["map_package"]),
        "Terrain load failed",
    )
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    require(
        world.get_path_name().split(".")[0] == sources["terrain"]["map_package"],
        "Wrong map",
    )
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    grounds = [
        a for a in actors.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)
    ]
    require(len(grounds) == 1, "One Landscape required")
    ground = grounds[0]
    transform = ground.get_actor_transform()
    rotation = transform.rotation.rotator()
    ground_record = {
        "location": vector(transform.translation),
        "scale": vector(transform.scale3d),
        "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
    }
    require(
        ground_record["scale"][:2] == [50.0, 50.0]
        and ground_record["rotation"] == [0.0, 0.0, 0.0],
        "Terrain transform differs",
    )
    cases = []
    instance = unreal.load_asset(binding["forge_import"]["assets"]["instance"])
    for mesh in meshes:
        actor = actors.spawn_actor_from_class(
            unreal.StaticMeshActor, unreal.Vector(), transient=True
        )
        require(actor is not None, "Actor creation failed")
        try:
            actor.set_actor_rotation(unreal.Rotator(), False)
            actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
            rotation = actor.get_actor_rotation()
            require(
                vector(actor.get_actor_location()) == [0.0, 0.0, 0.0]
                and vector(actor.get_actor_scale3d()) == [1.0, 1.0, 1.0]
                and [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
                "Measurement actor transform differs",
            )
            component = actor.static_mesh_component
            native = unreal.load_asset(mesh["package"])
            require(component.set_static_mesh(native), "Mesh assignment failed")
            require(
                all(
                    component.get_material(i) == instance
                    for i in range(mesh["slot_count"])
                ),
                "Forge slot drift",
            )
            component.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
            component.set_collision_response_to_all_channels(
                unreal.CollisionResponseType.ECR_BLOCK
            )
            ignored = [a for a in actors.get_all_level_actors() if a != ground]
            for index, point in enumerate(contact["points"]):
                unreal.log(
                    f"Collection contact batch {batch_index}: {mesh['id']} point {index}"
                )
                case = {
                    "mesh_id": mesh["id"],
                    "point_index": index,
                    "candidate_id": point["candidate_id"],
                    "world_xy_cm": point["world_xy_cm"],
                    "grids": [],
                }

                def sample(size):
                    grid = q.measure_grid(
                        component,
                        actor,
                        mesh["bounds_cm"],
                        size,
                        world,
                        ground,
                        ignored,
                        point["world_xy_cm"],
                    )
                    grid["raw_samples"] = q.write_raw(
                        output,
                        f"{mesh['id']}-point{index}-grid{size}.json",
                        {
                            "support_rows": grid.pop("rows"),
                            "rejected_rows": grid.pop("rejected_rows"),
                        },
                    )
                    case["grids"].append(grid)
                    return grid

                coarse, fine = sample(33), sample(65)
                case.update(
                    status="INCOMPLETE",
                    policy_decision={
                        "status": "REJECTED",
                        "reasons": ["INCOMPLETE_GROUND_OR_SUPPORT"],
                    },
                )
                if complete(coarse) and complete(fine):
                    case["measurement"] = measurement(mesh, coarse, fine)
                    case.update(
                        status="MEASURED",
                        policy_decision=evaluate(case["measurement"], trial_policy()),
                    )
                    reasons = case["policy_decision"]["reasons"]
                    if reasons and set(reasons) <= {
                        "ROOT_NOT_CONVERGED",
                        "EMBEDDING_NOT_CONVERGED",
                    }:
                        case["initial_measurement"] = case["measurement"]
                        case["initial_policy_decision"] = case["policy_decision"]
                        refined = sample(129)
                        if complete(refined):
                            case["measurement"] = measurement(mesh, fine, refined)
                            case["policy_decision"] = evaluate(
                                case["measurement"], refined_trial_policy()
                            )
                        else:
                            case["policy_decision"] = {
                                "status": "REJECTED",
                                "reasons": ["INCOMPLETE_REFINED_GROUND_OR_SUPPORT"],
                            }
                cases.append(case)
        finally:
            require(actors.destroy_actor(actor), "Actor cleanup failed")
    require(
        ground_identity(ground) == ground_record and map_identity(sources) == before,
        "Terrain changed",
    )
    require(
        collection.reload(root, output, head, binding)["meshes"] == inventory["meshes"],
        "Package drift",
    )
    return {
        "schema_version": 1,
        "code_sha": head,
        "status": "COLLECTION_CONTACT_BATCH_MEASURED",
        "batch_index": batch_index,
        "catalog": inventory["catalog"],
        "contact_request": q.identity(root / "contact-request.json"),
        "source_contract": sources["terrain"],
        "terrain_file_before": before,
        "terrain_file_after": map_identity(sources),
        "ground_transform": ground_record,
        "terrain_modified": False,
        "terrain_contact": "MEASURED_SAMPLED_ONLY",
        "map_saved": False,
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "meshes": meshes,
        "cases": cases,
    }


def contact_mode(root):
    """One proof layout per stage; partial outputs never select a fallback."""
    all_exists = (root / "proof/collection-contact-all").exists()
    batch_exists = any(
        (root / f"proof/collection-contact-{index:02d}").exists() for index in range(10)
    )
    require(not (all_exists and batch_exists), "Mixed contact process layouts")
    return "SINGLE_PROCESS_ALL_BATCHES" if all_exists else "PER_BATCH_PROCESSES"


def verify_all_marker(marker, head):
    require(
        marker.get("action") == "collection-contact-all"
        and marker.get("code_sha") == head
        and type(marker.get("exit_code")) is int
        and marker["exit_code"] == 0
        and marker.get("staged_bytes_unchanged") is True
        and marker.get("proof_admission") == "LOCAL_DIAGNOSTIC_ONLY",
        "All-contact launcher failed or action differs",
    )


def verify_batch_receipt(receipt, head, index, inventory, sources, contact, root):
    require(
        receipt["code_sha"] == head
        and receipt["status"] == "COLLECTION_CONTACT_BATCH_MEASURED"
        and type(receipt["batch_index"]) is int
        and receipt["batch_index"] == index
        and receipt["catalog"] == inventory["catalog"]
        and receipt["meshes"] == batch_members(inventory["meshes"], index)
        and receipt["source_contract"] == sources["terrain"]
        and receipt["contact_request"] == q.identity(root / "contact-request.json")
        and receipt["terrain_file_before"]
        == receipt["terrain_file_after"]
        == map_identity(sources)
        and receipt["placement"] is False
        and receipt["full_qualification"] is False
        and receipt["qualified_assets"] == []
        and receipt["terrain_modified"] is False
        and receipt["map_saved"] is False,
        "Batch identity/scope drift",
    )
    expected = {(m["id"], i) for m in receipt["meshes"] for i in range(5)}
    require(
        len(receipt["cases"]) == 10
        and all(type(c["point_index"]) is int for c in receipt["cases"])
        and {(c["mesh_id"], c["point_index"]) for c in receipt["cases"]} == expected,
        "Incomplete matrix",
    )
    for case in receipt["cases"]:
        require(
            [g["grid_size"] for g in case["grids"]] in ([33, 65], [33, 65, 129]),
            "Missing or unknown sampling grids",
        )
        point = contact["points"][case["point_index"]]
        require(
            case["candidate_id"] == point["candidate_id"]
            and case["world_xy_cm"] == point["world_xy_cm"],
            "Point drift",
        )


def verify_raw_samples(directory, cases):
    directory = directory.resolve(strict=True)
    for case in cases:
        for grid in case["grids"]:
            raw = grid["raw_samples"]
            file = (directory / raw["path"]).resolve(strict=True)
            require(
                file.is_relative_to(directory)
                and q.identity(file) == {k: raw[k] for k in ("bytes", "sha256")},
                "Raw grid drift",
            )


def run_all(root, output, head, binding):
    """Measure all ten batches in one process; only the launcher proves exit."""
    root, output = Path(root).resolve(), Path(output).resolve()
    require(contact_mode(root) == "SINGLE_PROCESS_ALL_BATCHES", "Wrong contact layout")
    require(
        output == root / "proof/collection-contact-all",
        "Unexpected all-contact output",
    )
    inventory = collection.reload(root, output, head, binding)
    sources, contact = inputs(root)
    before = map_identity(sources)
    batches = []
    for index in range(10):
        directory = output / f"batch-{index:02d}"
        directory.mkdir(exist_ok=False)
        result = run(root, directory, head, binding, index)
        verify_batch_receipt(result, head, index, inventory, sources, contact, root)
        verify_raw_samples(directory, result["cases"])
        if batches:
            require(
                result["ground_transform"] == batches[0]["result"]["ground_transform"],
                "Landscape transform changed between batches",
            )
        batches.append({"directory": directory.name, "result": result})
    require(map_identity(sources) == before, "Terrain changed during all-contact run")
    require(
        collection.reload(root, output, head, binding)["meshes"] == inventory["meshes"],
        "Package drift during all-contact run",
    )
    return {
        "schema_version": 1,
        "code_sha": head,
        "status": "COLLECTION_CONTACT_ALL_MEASURED",
        "contact_execution_mode": "SINGLE_PROCESS_ALL_BATCHES",
        "catalog": inventory["catalog"],
        "meshes": inventory["meshes"],
        "contact_request": q.identity(root / "contact-request.json"),
        "source_contract": sources["terrain"],
        "terrain_file_before": before,
        "terrain_file_after": map_identity(sources),
        "ground_transform": batches[0]["result"]["ground_transform"],
        "terrain_contact": "MEASURED_SAMPLED_ONLY",
        "terrain_modified": False,
        "map_saved": False,
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "batches": batches,
    }


def read_contact_batches(root, head, inventory, sources, contact):
    mode = contact_mode(root)
    cases, receipts = [], []
    if mode == "SINGLE_PROCESS_ALL_BATCHES":
        directory = root / "proof/collection-contact-all"
        session_directory = root / "proof/collection-contact-measure"
        if session_directory.exists():
            marker = read_json(session_directory / "launcher-completed.json")
            require(
                marker.get("action") == "collection-contact-measure"
                and marker.get("code_sha") == head
                and type(marker.get("exit_code")) is int
                and marker["exit_code"] == 0
                and marker.get("staged_bytes_unchanged") is True
                and marker.get("proof_admission") == "LOCAL_DIAGNOSTIC_ONLY",
                "Three-session contact producer did not exit cleanly",
            )
            require(
                not (directory / "launcher-completed.json").exists(),
                "Grouped phase cannot claim an independent exit",
            )
            group = read_json(
                session_directory / "collection-contact-measure-receipt.json"
            )
            require(
                group.get("action") == "collection-contact-measure"
                and group.get("code_sha") == head
                and group.get("status") == "COLLECTION_CONTACT_ALL_MEASURED"
                and group.get("contact_execution_mode") == "THREE_SESSION_MEASURE"
                and group.get("asset_compilation_loading_barrier_completed") is True,
                "Grouped contact producer receipt differs",
            )
            require(
                set(group.get("phases", {}))
                == {"material_readback", "collection_readback", "contact"},
                "Grouped contact phases incomplete",
            )
            for key, expected in (
                ("material_readback", "proof/collection-contact-measure/material-fresh-phase.json"),
                ("collection_readback", "proof/collection-contact-measure/collection-fresh-phase.json"),
                ("contact", "proof/collection-contact-all/collection-contact-all-receipt.json"),
            ):
                record = group["phases"][key]
                phase_file = root / expected
                require(
                    record == {"path": expected, **q.identity(phase_file)},
                    "Grouped phase receipt hash differs: " + key,
                )
        else:
            verify_all_marker(read_json(directory / "launcher-completed.json"), head)
        path = directory / "collection-contact-all-receipt.json"
        receipt = read_json(path)
        require(
            receipt["code_sha"] == head
            and receipt["action"] == "collection-contact-all"
            and receipt["status"] == "COLLECTION_CONTACT_ALL_MEASURED"
            and receipt["contact_execution_mode"] == mode
            and receipt["catalog"] == inventory["catalog"]
            and receipt["meshes"] == inventory["meshes"]
            and receipt["source_contract"] == sources["terrain"]
            and receipt["contact_request"] == q.identity(root / "contact-request.json")
            and receipt["terrain_file_before"]
            == receipt["terrain_file_after"]
            == map_identity(sources)
            and receipt["terrain_modified"] is False
            and receipt["map_saved"] is False
            and receipt["placement"] is False
            and receipt["qualified_assets"] == []
            and receipt["full_qualification"] is False
            and receipt["asset_compilation_loading_barrier_completed"] is True
            and len(receipt["batches"]) == 10,
            "All-contact identity/scope drift",
        )
        for index, batch in enumerate(receipt["batches"]):
            require(batch["directory"] == f"batch-{index:02d}", "Batch directory drift")
            result = batch["result"]
            verify_batch_receipt(result, head, index, inventory, sources, contact, root)
            require(
                result["ground_transform"] == receipt["ground_transform"],
                "All-contact ground transform drift",
            )
            child = directory / batch["directory"]
            require(
                not (child / "launcher-completed.json").exists(),
                "A child batch cannot claim an independent process exit",
            )
            verify_raw_samples(child, result["cases"])
            cases.extend(result["cases"])
        receipts.append({"path": str(path.relative_to(root)), **q.identity(path)})
    else:
        for index in range(10):
            directory = root / f"proof/collection-contact-{index:02d}"
            verify_marker(read_json(directory / "launcher-completed.json"), head, index)
            path = directory / f"collection-contact-{index:02d}-receipt.json"
            receipt = read_json(path)
            verify_batch_receipt(
                receipt, head, index, inventory, sources, contact, root
            )
            verify_raw_samples(directory, receipt["cases"])
            cases.extend(receipt["cases"])
            receipts.append({"path": str(path.relative_to(root)), **q.identity(path)})
    require(
        len(cases) == 100
        and {(c["mesh_id"], c["point_index"]) for c in cases}
        == {(m["id"], i) for m in inventory["meshes"] for i in range(5)},
        "Incomplete collection contact matrix",
    )
    return mode, cases, receipts


def reload(root, output, head, binding):
    root = Path(root).resolve()
    inventory = collection.reload(root, output, head, binding)
    sources, contact = inputs(root)
    mode, cases, receipts = read_contact_batches(
        root, head, inventory, sources, contact
    )
    summary = [
        {
            "mesh_id": mesh["id"],
            "sampled_pass": any(
                c["policy_decision"]["status"] == "PASS_SAMPLED_CONTACT_ONLY"
                for c in cases
                if c["mesh_id"] == mesh["id"]
            ),
        }
        for mesh in inventory["meshes"]
    ]
    return {
        **inventory,
        "status": "COLLECTION_CONTACT_FRESH_READBACK",
        "contact_execution_mode": mode,
        "terrain_contact": "MEASURED_SAMPLED_ONLY",
        "cases": cases,
        "batches": receipts,
        "best_summary": summary,
        "source_contract": sources["terrain"],
        "full_qualification": False,
        "placement": False,
        "qualified_assets": [],
    }


class CollectionCapture(RockCapture):
    def verify(self):
        current = collection.reload(self.root, self.output, self.head, self.binding)
        require(current["meshes"] == self.meshes, "Render mesh drift")
        for receipt in self.contact_receipts:
            require(
                q.identity(self.root / receipt["path"])
                == {key: receipt[key] for key in ("bytes", "sha256")},
                "Contact source receipt changed during render",
            )
        verify_terrain(
            self.terrain_before,
            map_identity(self.terrain_sources),
            self.ground_before,
            ground_identity(self.ground),
        )
        self.report.update(
            terrain_file_after=map_identity(self.terrain_sources),
            ground_transform_after=ground_identity(self.ground),
        )

    def begin(self):
        try:
            receipt = reload(self.root, self.output, self.head, self.binding)
            self.contact_receipts = receipt["batches"]
            self.meshes = self.review_meshes = receipt["meshes"]
            grouped = getattr(self, "grouped_review", False)
            self.receipt_path = (
                self.output / "contact-fresh-phase.json"
                if grouped
                else self.root
                / "proof/collection-contact-reload/collection-contact-reload-receipt.json"
            )
            saved = read_json(self.receipt_path)
            require(
                saved.pop("asset_compilation_loading_barrier_completed", None) is True,
                "Aggregate compilation barrier incomplete",
            )
            require(
                all(
                    key in saved and saved[key] == value
                    for key, value in receipt.items()
                ),
                "Aggregate receipt differs",
            )
            if grouped:
                require(
                    saved.pop("action", None) == "collection-contact-reload",
                    "Review aggregate phase identity differs",
                )
            else:
                marker = read_json(
                    self.receipt_path.parent / "launcher-completed.json"
                )
                require(
                    marker.get("action") == "collection-contact-reload"
                    and marker.get("code_sha") == self.head
                    and type(marker.get("exit_code")) is int
                    and marker["exit_code"] == 0
                    and marker.get("staged_bytes_unchanged") is True,
                    "Aggregate launcher failed",
                )
            self.receipt_identity = q.identity(self.receipt_path)
            self.cases = []
            for mesh in self.meshes:
                measured = [
                    c
                    for c in receipt["cases"]
                    if c["mesh_id"] == mesh["id"] and c.get("measurement")
                ]
                require(bool(measured), "No renderable fit: " + mesh["id"])
                chosen = min(
                    measured,
                    key=lambda c: (
                        c["policy_decision"]["status"] != "PASS_SAMPLED_CONTACT_ONLY",
                        c["measurement"]["max_local_slope_deg"],
                        c["point_index"],
                    ),
                )
                self.cases.append(
                    (
                        chosen,
                        "SAMPLED_CONTACT_PASS_NOT_FULL_QUALIFICATION"
                        if chosen["policy_decision"]["status"]
                        == "PASS_SAMPLED_CONTACT_ONLY"
                        else "DIAGNOSTIC_REJECTED",
                    )
                )
            (
                self.review_views,
                self.review_dynamic_sun,
                self.render_transient_movable,
            ) = 2, True, True
            sources, _ = inputs(self.root)
            self.terrain_sources = sources
            self.terrain_before = map_identity(sources)
            require(
                unreal.EditorLoadingAndSavingUtils.load_map(
                    sources["terrain"]["map_package"]
                ),
                "Render map load failed",
            )
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            require(
                self.world.get_path_name().split(".")[0]
                == sources["terrain"]["map_package"],
                "Wrong render terrain map",
            )
            self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            grounds = [
                a
                for a in self.actors.get_all_level_actors()
                if isinstance(a, unreal.LandscapeProxy)
            ]
            require(len(grounds) == 1, "One render Landscape required")
            self.ground = grounds[0]
            self.ground_before = ground_identity(self.ground)
            self.report.update(
                terrain_contact="MEASURED_SAMPLED_ONLY",
                source_contract=sources["terrain"],
                terrain_file_before=self.terrain_before,
                ground_transform_before=self.ground_before,
                terrain_modified=False,
                map_saved=False,
            )
            self.verify()
            self.next_mesh()
        except Exception:
            self.stop(traceback.format_exc())
        return self

    def completed(self, result):
        try:
            self.pending["capture"] = result
            self.report["captures"].append(self.pending)
            require(
                result.get("status") == "CAPTURE_COMPLETED" and not result.get("error"),
                "GPU capture failed",
            )
            self.destroy_actor()
            self.verify()
            require(
                q.identity(self.receipt_path) == self.receipt_identity,
                "Aggregate drift",
            )
            self.index += 1
            if self.index < len(self.review_meshes):
                self.next_mesh()
            else:
                self.report["status"] = "COLLECTION_CONTACT_REAL_GPU_CAPTURED"
                self.stop()
        except Exception:
            self.stop(traceback.format_exc())


def start(root, output, head, binding, done, grouped_review=False):
    operation = CollectionCapture(root, output, head, binding, done)
    operation.grouped_review = grouped_review
    _ACTIVE.append(operation)
    return operation.begin()
