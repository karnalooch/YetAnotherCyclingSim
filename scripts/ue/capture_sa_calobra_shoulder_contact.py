"""Capture 12 original-size window0112 owner-isolation frames in isolated CI.

No geometry is generated, no LOD is forced, no map is saved. This script never
attaches to the owner's editor. The workflow must prove the host idle before
starting this fresh editor on /Engine/Maps/Entry in its isolated worktree.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.proof.sa_calobra_shoulder_contact import (  # noqa: E402
    CUT_BOUNDS_CM,
    CUT_FILE,
    CUT_SHA256,
    WINDOW,
    diagnostic_plan,
    digest,
    interior_top_triangles,
    overlaps,
    triangle_delta,
)
from scripts.proof.sa_calobra_tpp_survey import FROZEN_SHA, load_frozen_windows  # noqa: E402
from scripts.ue.sa_calobra_tpp_survey_capture import SurveyCapture  # noqa: E402

MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MAP_FILE = ROOT / "Content/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.umap"
MAP_SHA256 = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
PRIMARY_SYMBOLS = {
    "SectionBaseX",
    "SectionBaseY",
    "ComponentSizeQuads",
    "ForcedLOD",
    "LODBias",
    "SetVisibility",
    "bVisible",
    "bCastHiddenShadow",
    "GetMeshRef",
    "TriangleIndicesItr",
    "IsTriangle",
    "GetTriangle",
    "GetVertex",
    "VertexCount",
    "TriangleCount",
}


def xyz(value):
    return tuple(float(getattr(value, axis)) for axis in ("x", "y", "z"))


def native_integer(value):
    # FJsonValueNumber stores doubles; admit 2 and 2.0 as the same native ID.
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or value < 0
        or value > 2147483647
        or value != int(value)
    ):
        raise RuntimeError("Native support query has invalid integer ID/count")
    return int(value)


def native_triangles(api, mesh, ids=(), *, allow_missing=False):
    text = api.YacsLandscapeMeshDiagnosticLibrary.read_window0112_support_triangles(
        mesh, list(ids)
    )
    if not isinstance(text, str) or len(text) > 16 * 1024 * 1024:
        raise RuntimeError(
            "Native support query returned invalid or unbounded evidence"
        )
    report = json.loads(text)
    if (
        allow_missing
        and report.get("error") == "missing or duplicate native support triangle ID"
    ):
        return None
    if (
        report.get("status") != "NATIVE_WINDOW0112_SUPPORT_TRIANGLES"
        or report.get("geometry_mutated") is not False
        or report.get("mesh_path") != mesh.get_path_name()
    ):
        raise RuntimeError("Native support query failed: " + str(report.get("error")))
    for field in ("vertex_count", "triangle_count", "returned_triangle_count"):
        report[field] = native_integer(report.get(field))
    rows = report.get("triangles", [])
    if (
        not isinstance(rows, list)
        or not 0 <= len(rows) <= 12000
        or report.get("returned_triangle_count") != len(rows)
        or (not ids and len(rows) != report["triangle_count"])
    ):
        raise RuntimeError("Native support query triangle inventory differs")
    positions = {}
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != 10
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[1:])
        ):
            raise RuntimeError("Native support query has invalid ID or coordinates")
        tid = native_integer(row[0])
        if tid in positions:
            raise RuntimeError("Native support query has duplicate triangle IDs")
        positions[tid] = tuple(tuple(row[start : start + 3]) for start in (1, 4, 7))
    if ids and set(positions) != set(ids):
        raise RuntimeError(
            "Native support query did not return the exact requested IDs"
        )
    report["positions"] = positions
    return report


def mesh_triangle(snapshot, tid):
    if tid not in snapshot["positions"]:
        raise RuntimeError("Saved support triangle is unavailable: " + str(tid))
    return snapshot["positions"][tid]


def mesh_digest(snapshot):
    result = hashlib.sha256()
    for tid in sorted(snapshot["positions"]):
        result.update(struct.pack("<i", tid))
        for point in mesh_triangle(snapshot, tid):
            result.update(struct.pack("<3d", *point))
    return result.hexdigest()


def actor_snapshot(actor):
    return {
        "path": actor.get_path_name(),
        "label": actor.get_actor_label(),
        "location_cm": xyz(actor.get_actor_location()),
        "rotation_deg": tuple(
            float(getattr(actor.get_actor_rotation(), a))
            for a in ("pitch", "yaw", "roll")
        ),
        "scale": xyz(actor.get_actor_scale3d()),
    }


def visibility(component):
    return (
        bool(component.get_editor_property("visible")),
        bool(component.get_editor_property("cast_hidden_shadow")),
    )


def set_visibility(component, state):
    visible, hidden_shadow = state
    component.set_editor_property("cast_hidden_shadow", hidden_shadow)
    component.set_visibility(visible, False)
    if visibility(component) != state:
        raise RuntimeError(
            "Surface visibility readback differs: " + component.get_path_name()
        )


class ContactCapture(SurveyCapture):
    def __init__(self, *args, diagnostic, support, components, **kwargs):
        self.support, self.components = support, components
        self.surface_state = [(c, visibility(c)) for c in (support, *components)]
        if any(not state[0] for _, state in self.surface_state):
            raise RuntimeError(
                "Target source surfaces are not initially visible; owner unknown"
            )
        super().__init__(*args, **kwargs)
        self.report.update(
            planned_frames=diagnostic["frames"],
            frame_count=12,
            windows=[WINDOW],
            window_count=1,
            transitions=[],
            capture_kind="Issue459 internal contact surface-owner isolation",
            whole_map_coverage=False,
            rendered_owner="PENDING_PAIRED_VISUAL_REVIEW",
            actual_rendered_landscape_lod="NOT_MEASURED_NO_LOD_OVERRIDE",
        )
        self._write()

    def _submit(self):
        mode = self.report["planned_frames"][self.index]["diagnostic_mode"]
        for component, original in self.surface_state:
            hidden = (component == self.support and mode == "support-hidden") or (
                component != self.support and mode == "local-landscape-hidden"
            )
            set_visibility(component, (False, False) if hidden else original)
        super()._submit()
        self.pending["surface_visibility"] = {
            "support_visible": visibility(self.support)[0],
            "landscape_visible": all(visibility(c)[0] for c in self.components),
            "hidden_shadow_disabled_on_hidden_surfaces": True,
            "support_component": self.support.get_path_name(),
            "landscape_components": [c.get_path_name() for c in self.components],
        }

    def restore_visibility(self):
        errors = []
        for component, original in self.surface_state:
            try:
                set_visibility(component, original)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))

    def tick(self, delta):
        if not self.stopped and self.clock() - self.started > 900:
            self.stop("Bounded 12-frame diagnostic deadline exceeded (900s)")
            return
        super().tick(delta)


class Owner:
    def __init__(self, api):
        self.api, self.capture = api, None
        self.transient = []
        self.before = self.mesh = self.viewport = None
        self.report = {
            "status": "STARTED",
            "source_road_sha": FROZEN_SHA,
            "window_id": WINDOW,
            "geometry_mutated": False,
            "saved_to_map": False,
            "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
            "performance_acceptance": "NOT_MEASURED",
            "error": None,
            "restoration": {"status": "PENDING"},
            "capture_root": "capture",
        }
        self.out = Path(os.environ["YACS_SHOULDER_CONTACT_ROOT"])
        if not self.out.is_absolute() or self.out.resolve().is_relative_to(ROOT):
            raise RuntimeError(
                "Diagnostic output must be external to the isolated worktree"
            )
        if self.out.exists() and any(self.out.iterdir()):
            raise RuntimeError(
                "Diagnostic output must be empty; refusing stale evidence"
            )
        self.out.mkdir(parents=True, exist_ok=True)

    def write(self):
        temporary = self.out / "shoulder-contact.json.tmp"
        temporary.write_text(
            json.dumps(self.report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        temporary.replace(self.out / "shoulder-contact.json")

    def inventory(self):
        return sorted(
            (actor_snapshot(a) for a in self.actors.get_all_level_actors()),
            key=lambda row: row["path"],
        )

    def finish(self, error=None):
        # Shutdown is guaranteed even when a final disk/native readback fails.
        try:
            self._finish(error)
        finally:
            self.api.SystemLibrary.quit_editor()

    def _finish(self, error=None):
        errors = [error] if error else []
        if self.capture:
            self.capture.stopped = True
            if self.capture.handle is not None:
                try:
                    self.api.unregister_slate_post_tick_callback(self.capture.handle)
                    self.capture.handle = None
                except Exception:
                    errors.append(traceback.format_exc())
        for action in (
            lambda: self.capture.restore_visibility() if self.capture else None,
            lambda: self.restore_viewport(),
            lambda: self.release_height_mips(),
        ):
            try:
                action()
            except Exception:
                errors.append(traceback.format_exc())
        for actor in reversed(self.transient):
            try:
                if not self.actors.destroy_actor(actor):
                    raise RuntimeError("Transient diagnostic actor cleanup failed")
            except Exception:
                errors.append(traceback.format_exc())
        map_hash = support_hash = None
        try:
            map_hash = digest(MAP_FILE)
            if map_hash != MAP_SHA256:
                raise RuntimeError("Saved accepted source map bytes changed")
            if self.before is not None and self.inventory() != self.before:
                raise RuntimeError(
                    "Source actor inventory/transforms differ after cleanup"
                )
            if self.mesh is not None:
                support_hash = mesh_digest(native_triangles(self.api, self.mesh))
                if support_hash != self.report["support"]["triangle_sha256"]:
                    raise RuntimeError("Target support triangle coordinates changed")
            for component, before in getattr(self, "landscape_state", []):
                if self.component_state(component) != before:
                    raise RuntimeError(
                        "Local Landscape visibility/material/LOD policy changed"
                    )
        except Exception:
            errors.append(traceback.format_exc())
        error = "\n".join(errors) if errors else None
        if self.capture:
            try:
                self.capture.mark_cleanup(error)
            except Exception:
                error = (error + "\n" if error else "") + traceback.format_exc()
            if self.capture.report["status"] != "CAPTURED" and not error:
                error = "Incomplete diagnostic capture"
        elif not error:
            error = "Diagnostic capture was not started"
        self.report.update(
            status="FAILED" if error else "SHOULDER_CONTACT_CAPTURED",
            error=error,
            restoration={
                "status": "FAILED" if errors else "RESTORED",
                "map_sha256": map_hash,
                "support_triangle_sha256": support_hash,
                "transient_actors_destroyed": len(self.transient),
                "height_mip_leases_released": True,
            },
        )
        self.write()

    def restore_viewport(self):
        if self.viewport:
            subsystem = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem)
            subsystem.set_level_viewport_camera_info(*self.viewport)
            actual = subsystem.get_level_viewport_camera_info()
            if xyz(actual[0]) != xyz(self.viewport[0]) or any(
                abs(
                    (
                        float(getattr(actual[1], a))
                        - float(getattr(self.viewport[1], a))
                        + 180
                    )
                    % 360
                    - 180
                )
                > 0.01
                for a in ("pitch", "yaw", "roll")
            ):
                raise RuntimeError("Original viewport camera did not restore")

    def release_height_mips(self):
        if getattr(self, "landscape", None):
            from scripts.ue.prepare_landscape_capture import _height_texture_objects

            for texture in _height_texture_objects(self.api, self.landscape):
                texture.set_force_mip_levels_to_be_resident(0.0, 0)

    def component_state(self, c):
        material = c.get_material(0)
        return {
            "visibility": visibility(c),
            "forced_lod": int(c.get_editor_property("forced_lod")),
            "lod_bias": int(c.get_editor_property("lod_bias")),
            "material": material.get_path_name() if material else None,
        }

    def start(self):
        api = self.api
        expected = os.environ["YACS_SHOULDER_CONTACT_EXACT_SHA"]
        self.report["exact_sha"] = expected
        worktree = Path(os.environ["YACS_SHOULDER_CONTACT_WORKTREE"]).resolve()
        if (
            worktree != ROOT
            or str(ROOT).replace("\\", "/").lower().rstrip("/") == "d:/yacs/project"
        ):
            raise RuntimeError(
                "Diagnostic requires its named isolated checkout; refusing authoring root"
            )
        head = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, timeout=15
        ).strip()
        if head != expected or digest(MAP_FILE) != MAP_SHA256:
            raise RuntimeError("Exact source commit or accepted map payload differs")
        receipt_path = Path(os.environ["YACS_SHOULDER_CONTACT_API_RECEIPT"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        symbols = {
            s for h in receipt.get("headers", []) for s in h.get("verified_symbols", [])
        }
        if (
            receipt.get("status") != "INSTALLED_PRIMARY_API_SOURCE_VERIFIED"
            or receipt.get("exact_sha") != expected
            or receipt.get("engine_version") != "5.8.2-56702186"
            or not PRIMARY_SYMBOLS <= symbols
            or not api.SystemLibrary.get_engine_version().startswith("5.8.2-56702186")
        ):
            raise RuntimeError(
                "Required installed exact-version primary API proof is missing"
            )
        self.report["primary_api_receipt_sha256"] = digest(receipt_path)
        frozen = Path(os.environ["YACS_SA_CALOBRA_TPP_FROZEN_ROOT"])
        source = load_frozen_windows(frozen)
        if digest(frozen / CUT_FILE) != CUT_SHA256:
            raise RuntimeError("Target CUT footprint source differs")
        self.report.update(
            source_identity=source["source_identity"],
            cut_manifest_sha256=CUT_SHA256,
            cut_footprint_cm=CUT_BOUNDS_CM,
            geometry_consumers_executed=False,
        )
        diagnostic = diagnostic_plan(
            source,
            expected,
            ROOT / "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv",
        )
        self.report["plan"] = diagnostic
        current = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
        if (
            current is None
            or current.get_path_name().split(".")[0] != "/Engine/Maps/Entry"
        ):
            raise RuntimeError(
                "Must start fresh on installed /Engine/Maps/Entry; refusing active scene"
            )
        self.world = api.EditorLoadingAndSavingUtils.load_map(MAP)
        if self.world is None:
            raise RuntimeError("Cannot reopen accepted source scene; owner unknown")
        self.actors = api.get_editor_subsystem(api.EditorActorSubsystem)
        landscapes = list(
            api.GameplayStatics.get_all_actors_of_class(self.world, api.Landscape)
        )
        if len(landscapes) != 1:
            raise RuntimeError("Exactly one source Landscape required; owner unknown")
        self.landscape = landscapes[0]
        self.landscape.force_layers_full_update()
        self.before = self.inventory()
        self.report["source_scene"] = {
            "map": MAP,
            "map_sha256": MAP_SHA256,
            "actor_count": len(self.before),
            "lighting_modified": False,
        }
        self.viewport = api.get_editor_subsystem(
            api.UnrealEditorSubsystem
        ).get_level_viewport_camera_info()
        sections = next(w["sections"] for w in source["windows"] if w["id"] == WINDOW)
        target = list(interior_top_triangles(sections))
        matches = []
        for actor in self.actors.get_all_level_actors():
            if not actor.get_actor_label().startswith("YACS_PERSIST_SUPPORT_"):
                continue
            snapshot = actor_snapshot(actor)
            if (
                snapshot["location_cm"] != (0.0, 0.0, 0.0)
                or snapshot["rotation_deg"] != (0.0, 0.0, 0.0)
                or snapshot["scale"] != (1.0, 1.0, 1.0)
            ):
                continue
            comp = actor.get_dynamic_mesh_component()
            mesh = comp.get_dynamic_mesh()
            tid, wanted = target[0]
            probe = native_triangles(api, mesh, [tid], allow_missing=True)
            if probe is None:
                continue
            if triangle_delta(mesh_triangle(probe, tid), wanted) <= 0.0001:
                actual = native_triangles(api, mesh)
                worst = max(
                    triangle_delta(mesh_triangle(actual, i), points)
                    for i, points in target
                )
                if worst <= 0.0001:
                    matches.append((actor, comp, mesh, actual, worst))
        if len(matches) != 1:
            raise RuntimeError(
                "Exact frozen target support owner is missing/ambiguous: "
                + str(len(matches))
            )
        actor, support, self.mesh, actual, worst = matches[0]
        self.report["support"] = dict(
            actor_snapshot(actor),
            component=support.get_path_name(),
            interior_top_triangles_compared=len(target),
            max_coordinate_delta_cm=worst,
            vertices=actual["vertex_count"],
            triangles=actual["triangle_count"],
            native_query="YacsLandscapeMeshDiagnosticLibrary.ReadWindow0112SupportTriangles",
            native_ids_in_triangle_digest=True,
            triangle_sha256=mesh_digest(actual),
        )
        landscape_transform = actor_snapshot(self.landscape)
        if landscape_transform["rotation_deg"] != (0.0, 0.0, 0.0):
            raise RuntimeError("Rotated source Landscape requires explicit owner proof")
        x, y, _ = landscape_transform["location_cm"]
        sx, sy, _ = landscape_transform["scale"]
        if sx != 50.0 or sy != 50.0:
            raise RuntimeError("Source Landscape must retain accepted 0.5m grid")
        components = []
        evidence = []
        all_components = self.landscape.get_components_by_class(api.LandscapeComponent)
        if len(all_components) != 1024:
            raise RuntimeError("Accepted Landscape component inventory differs")
        for c in all_components:
            bx, by = (
                int(c.get_editor_property(p))
                for p in ("section_base_x", "section_base_y")
            )
            size = int(c.get_editor_property("component_size_quads"))
            bounds = (
                x + bx * sx,
                y + by * sy,
                x + (bx + size) * sx,
                y + (by + size) * sy,
            )
            if overlaps(bounds):
                components.append(c)
                evidence.append(
                    dict(
                        path=c.get_path_name(),
                        section_base=[bx, by],
                        component_size_quads=size,
                        bounds_cm=bounds,
                        state=self.component_state(c),
                    )
                )
        if not 1 <= len(components) <= 16:
            raise RuntimeError("Target CUT component ownership is unbounded/unknown")
        self.landscape_state = [(c, self.component_state(c)) for c in components]
        self.report.update(
            landscape=dict(
                transform=landscape_transform,
                components=evidence,
                actual_rendered_lod="UNKNOWN_NO_LOD_OVERRIDE",
            ),
            scene_mutation="visibility and hidden-shadow only on proven target surfaces",
        )
        camera = self.actors.spawn_actor_from_class(
            api.CameraActor, api.Vector(), api.Rotator(), transient=True
        )
        if camera is None:
            raise RuntimeError("Cannot create transient diagnostic camera")
        self.transient.append(camera)
        self.write()
        # SurveyCapture requires an empty output; retain its original receipts
        # and PNGs in a child directory beside the final owner receipt.
        capture_root = self.out / "capture"
        self.capture = ContactCapture(
            api,
            self.world,
            self.landscape,
            camera,
            capture_root,
            frozen,
            expected,
            self.report["source_scene"],
            self.finish,
            self.transient.append,
            diagnostic=diagnostic,
            support=support,
            components=components,
        )
        self.capture.start()


def main():
    import unreal

    owner = None
    try:
        owner = Owner(unreal)
        builtins._yacs_shoulder_contact = owner
        owner.start()
    except Exception:
        if owner is None:
            unreal.log_error(traceback.format_exc())
            unreal.SystemLibrary.quit_editor()
        else:
            owner.finish(traceback.format_exc())


if __name__ == "__main__":
    main()
