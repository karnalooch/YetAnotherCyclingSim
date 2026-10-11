"""Capture source owner isolation: default 12 window0112 or 6 hairpin0081 frames.

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
    cut_bounds,
    diagnostic_plan,
    digest,
    hairpin_wall_contact,
    interior_top_triangles,
    overlaps,
    target_spec,
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
    "GetComponentBounds",
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


def native_support_snapshot(api, mesh, *, target="window0112"):
    """Respect the native 12000-face limit while hashing the complete support."""
    if target == "window0112":
        return native_triangles(api, mesh)
    expected = target_spec(target)["mesh_counts"]
    positions = {}
    for first in range(0, expected[1], 12000):
        ids = range(first, min(first + 12000, expected[1]))
        part = native_triangles(api, mesh, ids)
        if (part["vertex_count"], part["triangle_count"]) != expected:
            raise RuntimeError("Hairpin native support buffer inventory differs")
        if not set(positions).isdisjoint(part["positions"]):
            raise RuntimeError("Hairpin native support triangle chunks overlap")
        positions.update(part["positions"])
    if set(positions) != set(range(expected[1])):
        raise RuntimeError("Hairpin native support triangle inventory is not dense/complete")
    return {"vertex_count": expected[0], "triangle_count": expected[1],
            "returned_triangle_count": len(positions), "positions": positions}


def native_component_layout(api, component, landscape_transform):
    """Use the already exercised native world-bounds API, not hidden properties.

    See sa_calobra_saved_material_consumer.terrain_bounds and the whole-map
    native capture. The fresh installed KismetSystemLibrary.h receipt proves
    GetComponentBounds. Source section bases and the actual Landscape transform
    independently check these world XY bounds against the unchanged 0.5m grid.
    This reads a footprint; it does not infer terrain height or rendered LOD.
    """
    if (landscape_transform["rotation_deg"] != (0.0, 0.0, 0.0)
            or tuple(landscape_transform["scale"][:2]) != (50.0, 50.0)):
        raise RuntimeError("Source Landscape transform/grid differs")
    base = tuple(component.get_editor_property(key) for key in ("section_base_x", "section_base_y"))
    if any(type(value) is not int or not -2147483648 <= value <= 2147483647 for value in base):
        raise RuntimeError("Native Landscape section base is invalid")
    raw = api.SystemLibrary.get_component_bounds(component)
    if not isinstance(raw, tuple) or len(raw) != 3:
        raise RuntimeError("Native Landscape component bounds return contract differs")
    origin, extent, radius = xyz(raw[0]), xyz(raw[1]), raw[2]
    if (type(radius) not in (int, float)
            or not all(math.isfinite(value) for value in (*origin, *extent, radius))
            or min(extent) < 0 or min(extent[:2]) <= 0 or radius <= 0):
        raise RuntimeError("Native Landscape component bounds are invalid")
    bounds = (origin[0] - extent[0], origin[1] - extent[1],
              origin[0] + extent[0], origin[1] + extent[1])
    location, scale = landscape_transform["location_cm"], landscape_transform["scale"]
    spans = tuple(2.0 * extent[axis] / scale[axis] for axis in (0, 1))
    size = round(spans[0])
    if (not 1 <= size <= 512 or any(abs(span - size) > 0.000001 for span in spans)
            or any(abs(bounds[axis] - (location[axis] + base[axis] * scale[axis])) > 0.001
                   for axis in (0, 1))):
        raise RuntimeError("Native Landscape bounds disagree with the source section grid")
    return {"section_base": base, "component_size_quads": size, "bounds_cm": bounds,
            "component_size_source": "native_world_bounds_divided_by_source_grid",
            "native_bounds_query": "SystemLibrary.GetComponentBounds",
            "native_origin_cm": origin, "native_extent_cm": extent, "native_radius_cm": float(radius)}


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


def read_hairpin_wall_contact(actual, sections, support, source_identity, frozen, cut_raw):
    """Use the completed mesh snapshot and exact inert source bytes only."""
    cut_bounds(cut_raw, target="hairpin0081")
    cut = json.loads(cut_raw.decode("utf-8-sig"))
    path = Path(frozen) / "ma2141-cut-patch.f32"
    size = path.stat().st_size
    if size != cut["patch_byte_count"]:
        raise RuntimeError("Hairpin source CUT patch byte inventory differs")
    before = digest(path)
    with path.open("rb") as stream:
        raw = stream.read(size + 1)
    identity = dict(path=str(path), size_bytes=size, sha256_before=before, sha256_after=digest(path))
    return hairpin_wall_contact(actual["positions"], sections, support, source_identity,
                                cut_raw, raw, identity)


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
            frame_count=diagnostic["frame_count"],
            windows=[diagnostic["frames"][0]["window_id"]],
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
            self.stop("Bounded owner-isolation diagnostic deadline exceeded (900s)")
            return
        super().tick(delta)


class Owner:
    def __init__(self, api):
        self.api, self.capture = api, None
        self.target = os.environ.get("YACS_SHOULDER_CONTACT_TARGET", "window0112")
        self.spec = target_spec(self.target)
        self.transient = []
        self.before = self.mesh = self.viewport = None
        self.report = {
            "status": "STARTED",
            "source_road_sha": FROZEN_SHA,
            "window_id": self.spec["window_id"],
            "geometry_mutated": False,
            "saved_to_map": False,
            "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
            "performance_acceptance": "NOT_MEASURED",
            "error": None,
            "restoration": {"status": "PENDING"},
            "capture_root": "capture",
        }
        if self.target == "hairpin0081":
            self.report["support_wall_contact"] = {"schema_version": 1, "status": "PENDING"}
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
            try:
                self.api.EditorPythonScripting.set_keep_python_script_alive(False)
            except Exception:
                # Slate may catch callback exceptions after stop() has set its
                # guard. Do not leave a successful receipt if release fails.
                lifecycle_error = traceback.format_exc()
                self.report.update(status="FAILED", error=lifecycle_error)
                try:
                    if self.capture:
                        self.capture.mark_cleanup(lifecycle_error)
                finally:
                    self.write()
                raise
            finally:
                self.api.SystemLibrary.quit_editor()

    def _start_capture(self):
        # ExecutePythonScript otherwise exits before the asynchronous Slate
        # callbacks can collect the images, as in the road GPU loop.
        self.api.EditorPythonScripting.set_keep_python_script_alive(True)
        self.capture.start()

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
        ):
            try:
                action()
            except Exception:
                errors.append(traceback.format_exc())
        height_mips_released = False
        try:
            self.release_height_mips()
            height_mips_released = True
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
                support_hash = mesh_digest(native_support_snapshot(self.api, self.mesh, target=self.target))
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
                "status": "FAILED" if error else "RESTORED",
                "map_sha256": map_hash,
                "support_triangle_sha256": support_hash,
                "transient_actors_destroyed": len(self.transient),
                "height_mip_leases_released": height_mips_released,
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
            "layout": native_component_layout(self.api, c, self.landscape_transform),
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
        cut_raw = (frozen / self.spec["cut_file"]).read_bytes()
        self.cut_footprint = cut_bounds(cut_raw, target=self.target)
        if self.target == "hairpin0081":
            # Retain the tiny exact source document so an artifact verifier can
            # independently derive this AOI, without trusting a receipt's box.
            with (self.out / "source-cut-manifest.json").open("xb") as stream:
                stream.write(cut_raw)
        self.report.update(
            source_identity=source["source_identity"],
            cut_manifest_sha256=self.spec["cut_sha256"],
            cut_footprint_cm=self.cut_footprint,
            geometry_consumers_executed=False,
        )
        diagnostic = diagnostic_plan(
            source,
            expected,
            ROOT / "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv",
            target=self.target,
            view_plan_path=os.environ.get("YACS_SHOULDER_CONTACT_VIEW_PLAN") or None,
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
        sections = next(w["sections"] for w in source["windows"] if w["id"] == self.spec["window_id"])
        target = list(interior_top_triangles(sections, target=self.target))
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
                actual = native_support_snapshot(api, mesh, target=self.target)
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
        if self.target == "hairpin0081":
            try:
                if actor.get_actor_label() != "YACS_PERSIST_SUPPORT_185":
                    raise RuntimeError("Diagnosed hairpin source owner label differs")
                self.report["support_wall_contact"] = read_hairpin_wall_contact(
                    actual, sections, self.report["support"], source["source_identity"], frozen, cut_raw)
            except Exception as exc:
                self.report["support_wall_contact"] = {"schema_version": 1, "status": "FAILED", "error": str(exc)}
                raise
        landscape_transform = self.landscape_transform = actor_snapshot(self.landscape)
        if landscape_transform["rotation_deg"] != (0.0, 0.0, 0.0):
            raise RuntimeError("Rotated source Landscape requires explicit owner proof")
        sx, sy, _ = landscape_transform["scale"]
        if sx != 50.0 or sy != 50.0:
            raise RuntimeError("Source Landscape must retain accepted 0.5m grid")
        components = []
        evidence = []
        all_components = self.landscape.get_components_by_class(api.LandscapeComponent)
        if len(all_components) != 1024:
            raise RuntimeError("Accepted Landscape component inventory differs")
        for c in all_components:
            layout = native_component_layout(api, c, landscape_transform)
            if overlaps(layout["bounds_cm"], self.cut_footprint):
                components.append(c)
                evidence.append(
                    dict(
                        path=c.get_path_name(),
                        **layout,
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
        self._start_capture()


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
