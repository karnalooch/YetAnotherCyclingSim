"""Sequential transient GPU rock views; sampled decisions never admit placement."""

import json
import math
from pathlib import Path
import traceback

import unreal

from scripts.ue import sa_calobra_pcg_boulder_capture as capture
from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue import sa_calobra_pcg_rock_qualification as qualification
from scripts.ue.sa_calobra_pcg_terrain_contact import require, vector


_ACTIVE = []


class RockCapture:
    def __init__(self, root, output, head, binding, done):
        self.root, self.output = Path(root).resolve(), Path(output).resolve()
        require(self.root == material.project_root(), "Wrong diagnostic root")
        require(
            self.output.is_relative_to(self.root) and self.output != self.root,
            "Unsafe capture output",
        )
        self.head, self.binding, self.done = head, binding, done
        self.actor, self.capture, self.stopped = None, None, False
        self.index = 0
        self.report = {
            "schema_version": 1,
            "code_sha": head,
            "status": "FAILED",
            "placement": False,
            "qualified_assets": [],
            "full_qualification": False,
            "visual_acceptance": "NOT_VERIFIED",
            "performance_pass": False,
            "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
            "scene_saved": False,
            "assets_saved": False,
            "captures": [],
        }

    def verify(self):
        material.verify_binding(self.binding)
        for mesh in self.meshes:
            qualification.source_path(self.root, mesh["source"])
            require(
                material.file_identity(mesh["package"]) == mesh["saved_package"],
                "Saved rock bytes changed",
            )

    def begin(self):
        try:
            # Existing fresh-readback helper verifies request/source/package hashes,
            # geometry and slots without import, repair, save or contact rerun.
            readback = qualification.reload(
                self.root, self.output, self.head, self.binding
            )
            self.meshes = readback["meshes"]
            require(
                len(self.binding["saved_packages"]) == 7,
                "Expected seven saved Forge binding packages",
            )
            self.verify()
            receipt_path = self.root / "proof/rock-qualify/rock-qualify-receipt.json"
            self.receipt_identity = qualification.identity(receipt_path)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            require(
                receipt["code_sha"] == self.head and receipt["placement"] is False,
                "Contact receipt HEAD/scope differs",
            )
            require(
                receipt["meshes"] == self.meshes
                and receipt["saved_packages"] == readback["saved_packages"],
                "Contact receipt mesh/package inventory differs",
            )
            request = json.loads(
                (self.root / "rock-qualification-request.json").read_text(
                    encoding="utf-8"
                )
            )
            cap_review_only = request.get("render_source_caps_only") is True
            self.review_meshes = [
                m
                for m in self.meshes
                if not cap_review_only or "support_patch" in m["source"]
            ]
            require(bool(self.review_meshes), "No declared source cap for GPU review")
            self.report["render_source_caps_only"] = cap_review_only
            self.report["omitted_mesh_ids"] = [
                m["id"] for m in self.meshes if m not in self.review_meshes
            ]
            self.cases = []
            for mesh in self.review_meshes:
                measured = [
                    c
                    for c in receipt["cases"]
                    if c["mesh_id"] == mesh["id"]
                    and c.get("status") == "MEASURED"
                    and c.get("measurement")
                ]
                require(bool(measured), "No usable measured case for " + mesh["id"])
                passed = [
                    c
                    for c in measured
                    if c["policy_decision"]["status"] == "PASS_SAMPLED_CONTACT_ONLY"
                ]
                patch_trials = [
                    c
                    for c in measured
                    if c.get("source_patch_diagnostic", {})
                    .get("fine", {})
                    .get("status")
                    == "DIAGNOSTIC_SUPPORT_PATCH_ONLY"
                ]
                require(
                    not cap_review_only or bool(patch_trials),
                    "Declared cap has no complete diagnostic fit for GPU review",
                )
                chosen = (
                    patch_trials[0]
                    if patch_trials
                    else passed[0]
                    if passed
                    else min(
                        measured, key=lambda c: c["measurement"]["max_local_slope_deg"]
                    )
                )
                self.cases.append(
                    (
                        chosen,
                        "SOURCE_CAP_DIAGNOSTIC_NOT_QUALIFIED"
                        if patch_trials
                        else "SAMPLED_CONTACT_PASS_NOT_FULL_QUALIFICATION"
                        if passed
                        else "DIAGNOSTIC_REJECTED",
                    )
                )
            sources = json.loads(
                (self.root / "qualification-sources.json").read_text(encoding="utf-8")
            )
            require(
                unreal.EditorLoadingAndSavingUtils.load_map(
                    sources["terrain"]["map_package"]
                ),
                "Pinned Landscape map load failed",
            )
            self.world = unreal.get_editor_subsystem(
                unreal.UnrealEditorSubsystem
            ).get_editor_world()
            require(
                self.world.get_path_name().split(".")[0]
                == sources["terrain"]["map_package"],
                "Wrong loaded map",
            )
            self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            self.next_mesh()
        except Exception:
            self.stop(traceback.format_exc())
        return self

    def next_mesh(self):
        mesh_record = self.review_meshes[self.index]
        case, label = self.cases[self.index]
        mesh = unreal.load_asset(mesh_record["package"])
        require(isinstance(mesh, unreal.StaticMesh), "Missing saved rock mesh")
        bounds = mesh.get_bounds()
        require(
            {"origin": vector(bounds.origin), "extent": vector(bounds.box_extent)}
            == mesh_record["bounds_cm"],
            "Render mesh bounds differ",
        )
        root_z = case["measurement"]["fit"]["root_zero_sampled_air_cm"]
        if label == "SOURCE_CAP_DIAGNOSTIC_NOT_QUALIFIED":
            root_z = case["source_patch_diagnostic"]["fine"]["fit"][
                "root_zero_sampled_air_cm"
            ]
        position = [*case["world_xy_cm"], root_z]
        require(
            all(type(v) in (int, float) and math.isfinite(v) for v in position),
            "Invalid capture location",
        )
        self.actor = self.actors.spawn_actor_from_class(
            unreal.StaticMeshActor,
            unreal.Vector(*position),
            unreal.Rotator(),
            transient=True,
        )
        require(self.actor is not None, "Transient rock actor creation failed")
        self.actor.set_actor_scale3d(unreal.Vector(1, 1, 1))
        component = self.actor.static_mesh_component
        require(
            component.set_static_mesh(mesh), "Rock component mesh assignment failed"
        )
        instance = unreal.load_asset(self.binding["forge_import"]["assets"]["instance"])
        require(
            len(mesh.static_materials) == mesh_record["slot_count"]
            and mesh_record["slot_count"] > 0,
            "Rock slot count differs",
        )
        for index in range(mesh_record["slot_count"]):
            component.set_material(index, instance)
            require(
                component.get_material(index) == instance
                and mesh.get_material(index) == instance,
                "Effective rock Forge slot differs",
            )
        require(
            vector(self.actor.get_actor_location()) == [float(v) for v in position]
            and vector(self.actor.get_actor_scale3d()) == [1.0, 1.0, 1.0],
            "Rock transform readback differs",
        )
        rotation = self.actor.get_actor_rotation()
        require(
            [rotation.pitch, rotation.yaw, rotation.roll] == [0.0, 0.0, 0.0],
            "Rock orientation differs",
        )
        center = unreal.Vector(
            position[0] + bounds.origin.x,
            position[1] + bounds.origin.y,
            position[2] + bounds.origin.z,
        )
        self.pending = {
            "mesh_id": mesh_record["id"],
            "package": mesh_record["package"],
            "source": mesh_record["source"],
            "selection": label,
            "candidate_id": case["candidate_id"],
            "world_xy_cm": case["world_xy_cm"],
            "location_cm": position,
            "policy_decision": case["policy_decision"],
            "measurement": case["measurement"],
            "source_patch_diagnostic": case.get("source_patch_diagnostic"),
            "camera_target_cm": vector(center),
            "framing_radius_cm": max(vector(bounds.box_extent)),
        }
        self.capture = capture.start_capture(
            self.world,
            center,
            self.output / mesh_record["id"],
            self.completed,
            framing_radius_cm=self.pending["framing_radius_cm"],
            warmup_captures=2,
        )

    def completed(self, result):
        try:
            self.pending["capture"] = result
            self.report["captures"].append(self.pending)
            require(
                result.get("status") == "CAPTURE_COMPLETED" and not result.get("error"),
                "Rock GPU capture failed",
            )
            self.destroy_actor()
            self.verify()
            self.index += 1
            if self.index < len(self.review_meshes):
                self.next_mesh()
            else:
                require(
                    qualification.identity(
                        self.root / "proof/rock-qualify/rock-qualify-receipt.json"
                    )
                    == self.receipt_identity,
                    "Contact receipt changed during capture",
                )
                self.report["status"] = "ROCKS_REAL_GPU_CAPTURED"
                self.stop()
        except Exception:
            self.stop(traceback.format_exc())

    def destroy_actor(self):
        if self.actor is not None:
            actor, self.actor = self.actor, None
            require(self.actors.destroy_actor(actor), "Transient rock cleanup failed")

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        try:
            self.destroy_actor()
        except Exception:
            error = (error or "") + "\n" + traceback.format_exc()
        if error:
            self.report.update(status="FAILED", error=error)
        if self in _ACTIVE:
            _ACTIVE.remove(self)
        self.done(self.report)


def start(root, output, head, binding, done):
    """Parent keeps Python/Slate alive, writes final receipt and owns editor exit."""
    try:
        operation = RockCapture(root, output, head, binding, done)
    except Exception:
        done(
            {
                "status": "FAILED",
                "code_sha": head,
                "placement": False,
                "qualified_assets": [],
                "full_qualification": False,
                "error": traceback.format_exc(),
            }
        )
        return None
    _ACTIVE.append(operation)
    return operation.begin()
