"""Bounded native detail comparison inside the existing restored v8 scene.

Geometry and native attributes belong to the C++ diagnostic snapshot. This
module owns only two recorded camera poses, ordinary depth-tested captures and
a paired-color visibility witness. No collision query, map save or new world
classification occurs. The existing cliff capture remains the cleanup owner.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import time
import traceback
import zlib

from scripts.ue.prepare_landscape_capture import prepare_capture

RESOLUTION = (1280, 720)
SOURCE_SHA = "a9d34dbfb32a59b592dca561a7d7b0e53f7d02d90c095cff7c0812c249247965"
MASK_SHA = "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953"
PILOT_SHA = "804842ef0893df0d4822caa458ca68b658bf6d9481ef64db5237dde00ec97718"
FRAME_IDS = ("window-0021-forward-00005", "window-0023-forward-00000")
MODES = ("baseline", "mask", "patch-magenta", "patch-cyan", "trial")
MIN_VISIBLE_PIXELS = 8
PRIMES_PER_CAPTURE = 3


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bounded_bytes(path, limit):
    if path.stat().st_size > limit:
        raise ValueError("Oversized native detail input: " + path.name)
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Oversized native detail input: " + path.name)
    return data


def load_inputs(root):
    root = Path(root)
    paths = {
        "source": root / "source/combined-mesh.json",
        "mask": root / "pilot/triangle-bands.json",
        "pilot": root / "pilot/manifest.json",
        "trial": root / "treatment/treatment-mesh.json",
        "manifest": root / "treatment/treatment-manifest.json",
    }
    limits = {"source": 16 * 1024 * 1024, "trial": 16 * 1024 * 1024,
              "mask": 4 * 1024 * 1024, "pilot": 1024 * 1024, "manifest": 1024 * 1024}
    payloads = {name: _bounded_bytes(path, limits[name]) for name, path in paths.items()}
    hashes = {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}
    if hashes["source"] != SOURCE_SHA or hashes["mask"] != MASK_SHA or hashes["pilot"] != PILOT_SHA:
        raise ValueError("Native detail input differs from the fixed v8 source/mask/cameras")
    texts = {name: payload.decode("utf-8-sig") for name, payload in payloads.items()}
    data = {name: json.loads(value) for name, value in texts.items()}
    manifest = data["manifest"]
    if (manifest.get("source_mesh_sha256") != SOURCE_SHA
            or manifest.get("mask_sha256") != MASK_SHA
            or manifest.get("trial_mesh_sha256") != hashes["trial"]):
        raise ValueError("Native detail treatment source or payload hash mismatch")
    frames = data["pilot"].get("frames", [])
    if tuple(frame.get("frame_id") for frame in frames) != FRAME_IDS:
        raise ValueError("Native detail requires the two originally annotated camera poses")
    for frame in frames:
        if (frame.get("width"), frame.get("height")) != RESOLUTION or frame.get("fov") != 76.0:
            raise ValueError("Native detail camera resolution/FOV drift")
    return {"texts": texts, "hashes": hashes, "data": data, "paths": paths}


def decode_png(path, expected_size=RESOLUTION):
    """Read screenshot RGB(A) without adding packages to embedded UE Python."""
    data = _bounded_bytes(Path(path), 16 * 1024 * 1024)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid or oversized native detail PNG")
    offset, header, compressed, ended = 8, None, bytearray(), False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise ValueError("Truncated PNG payload")
        payload = data[offset + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError("PNG CRC mismatch")
        if kind == b"IHDR":
            if header is not None or offset != 8 or size != 13:
                raise ValueError("Invalid PNG header sequence")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            if header is None:
                raise ValueError("PNG data precedes header")
            compressed.extend(payload)
        elif kind == b"IEND":
            if size or end != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
            break
        offset = end
    if not ended or header is None:
        raise ValueError("Incomplete PNG")
    width, height, depth, kind, compression, filtering, interlace = header
    if ((width, height) != tuple(expected_size) or depth != 8 or kind not in (2, 6)
            or compression or filtering or interlace):
        raise ValueError("Unsupported native detail PNG format/dimensions")
    channels = 3 if kind == 2 else 4
    stride, expected_bytes = width * channels, height * (width * channels + 1)
    inflater = zlib.decompressobj()
    raw = inflater.decompress(compressed, expected_bytes + 1)
    if len(raw) != expected_bytes or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError("PNG decompressed payload length mismatch")
    pixels, prior = bytearray(width * height * channels), bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        mode = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        if mode > 4:
            raise ValueError("Invalid PNG filter")
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up, upper_left = prior[x], prior[x - channels] if x >= channels else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = up
            elif mode == 3:
                predictor = (left + up) // 2
            elif mode == 4:
                p = left + up - upper_left
                a, b, c = abs(p - left), abs(p - up), abs(p - upper_left)
                predictor = left if a <= b and a <= c else up if b <= c else upper_left
            else:
                predictor = 0
            row[x] = (row[x] + predictor) & 255
        pixels[y * stride:(y + 1) * stride] = row
        prior = row
    return width, height, channels, pixels


def projected_patch_pixels(source, selected_rows, frame):
    """A conservative screen footprint; renderer colors decide visibility."""
    def unit(v):
        length = math.sqrt(sum(x * x for x in v))
        if not math.isfinite(length) or length <= 1e-10:
            raise ValueError("Degenerate detail camera")
        return tuple(x / length for x in v)

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    width, height = frame["width"], frame["height"]
    eye = frame["camera"]
    forward = unit(tuple(b - a for a, b in zip(eye, frame["target"])))
    right = unit(cross((0, 0, 1), forward))
    up = cross(forward, right)
    scale = width / (2 * math.tan(math.radians(frame["fov"]) / 2))
    vertices = {int(row[0]): row[4:7] for row in source["vertices_cm"]}
    projected = {}
    for row in selected_rows:
        for vertex in source["triangles"][row]:
            if vertex not in projected:
                rel = tuple(a - b for a, b in zip(vertices[vertex], eye))
                z = dot(rel, forward)
                projected[vertex] = None if z <= 0.01 else (
                    width / 2 + scale * dot(rel, right) / z,
                    height / 2 - scale * dot(rel, up) / z)
    pixels = set()
    for row in selected_rows:
        points = [projected[v] for v in source["triangles"][row]]
        # This two-pose proof does not infer coverage for near-plane crossings.
        if any(p is None for p in points):
            continue
        (ax, ay), (bx, by), (cx, cy) = points
        denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(denom) <= 1e-9:
            continue
        for y in range(max(0, math.floor(min(ay, by, cy))), min(height, math.ceil(max(ay, by, cy)))):
            for x in range(max(0, math.floor(min(ax, bx, cx))), min(width, math.ceil(max(ax, bx, cx)))):
                a = ((by - cy) * (x + 0.5 - cx) + (cx - bx) * (y + 0.5 - cy)) / denom
                b = ((cy - ay) * (x + 0.5 - cx) + (ax - cx) * (y + 0.5 - cy)) / denom
                if min(a, b, 1 - a - b) >= 0.02:
                    pixels.add(y * width + x)
    return pixels


def visible_patch_pixels(magenta, cyan, candidates):
    if magenta[:2] != cyan[:2]:
        raise ValueError("Visibility witness dimensions differ")
    accepted = []
    for index in sorted(candidates):
        if not isinstance(index, int) or not 0 <= index < magenta[0] * magenta[1]:
            raise ValueError("Invalid projected visibility pixel")
        m = magenta[3][index * magenta[2]:index * magenta[2] + 3]
        c = cyan[3][index * cyan[2]:index * cyan[2] + 3]
        if (len(m) == len(c) == 3 and m[0] >= 100 and m[2] >= 100 and c[1] >= 100 and c[2] >= 100
                and m[0] - m[1] >= 48 and m[2] - m[1] >= 48
                and c[1] - c[0] >= 48 and c[2] - c[0] >= 48
                and m[0] - c[0] >= 32 and c[1] - m[1] >= 32):
            accepted.append(index)
    return accepted


class DetailCapture:
    def __init__(self, api, world, landscape, camera, component, root, input_root,
                 exact_sha, source_scene, done, *, clock=time.monotonic):
        self.api, self.world, self.landscape = api, world, landscape
        self.camera, self.component = camera, component
        self.root, self.inputs = Path(root), load_inputs(input_root)
        self.done, self.clock = done, clock
        self.task = self.handle = self.pending = None
        self.stopped = self.native_started = False
        self.index = 0
        self.started = clock()
        self.materials, self.original_materials = [], []
        self.report = {
            "schema_version": 1, "status": "RUNNING", "exact_sha": exact_sha,
            "source_scene": source_scene, "inputs_sha256": self.inputs["hashes"],
            "captures": [], "native_modes": [], "native_source": None,
            "visibility": {"status": "PENDING", "frames": [], "min_required_pixels": MIN_VISIBLE_PIXELS,
                           "scope": "selected patch, two recorded poses, ordinary full-scene depth testing; no map-wide visibility classification"},
            "trial": {"applied": False, "visual_improvement": "PENDING_OWNER_REVIEW"},
            "cleanup": {"status": "PENDING"}, "saved_to_map": False,
            "performance_acceptance": "NOT_MEASURED", "visual_acceptance": "PENDING_OWNER",
            "priming_captures_per_phase": PRIMES_PER_CAPTURE, "error": None,
        }
        if self.root.exists():
            raise ValueError("Native detail output must not exist")
        self.root.mkdir(parents=True)
        (self.root / "frames").mkdir()
        (self.root / "priming").mkdir()
        self.frames = self.inputs["data"]["pilot"]["frames"]
        # Finish both witness poses before any trial geometry is applied.
        self.steps = [(frame, mode) for mode in MODES for frame in self.frames]
        self._write()

    def _write(self):
        path = self.root / "detail-native-receipt.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_bytes((json.dumps(self.report, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        temporary.replace(path)

    def _native_result(self, text, expected):
        result = json.loads(text)
        if result.get("status") != expected:
            raise RuntimeError("Native detail: " + json.dumps(result))
        return result

    def _make_materials(self):
        self.original_materials = [self.component.get_material(i)
                                   for i in range(self.component.get_num_materials())]
        if not self.original_materials or self.original_materials[0] is None:
            raise RuntimeError("Native detail baseline limestone material is missing")
        colors = ((1.0, 0.08, 0.035), (1.0, 0.75, 0.015), (0.35, 0.35, 0.35),
                  (1.0, 0.0, 1.0), (0.0, 1.0, 1.0))
        for slot, color in enumerate(colors, 1):
            material = self.api.YacsLandscapeMeshDiagnosticLibrary.create_component230_detail_material()
            if material is None:
                raise RuntimeError("Cannot allocate transient detail diagnostic material")
            self.materials.append(material)
            node = self.api.MaterialEditingLibrary.create_material_expression(
                material, self.api.MaterialExpressionConstant3Vector)
            if node is None:
                raise RuntimeError("Cannot create native detail color expression")
            node.set_editor_property("constant", self.api.LinearColor(*color, 1))
            if not self.api.MaterialEditingLibrary.connect_material_property(
                    node, "", self.api.MaterialProperty.MP_EMISSIVE_COLOR):
                raise RuntimeError("Cannot connect native detail diagnostic emissive color")
            self.api.MaterialEditingLibrary.recompile_material(material)
            self.component.set_material(slot, material)
            if self.component.get_material(slot) != material:
                raise RuntimeError("Native detail material slot did not apply")

    def start(self):
        try:
            engine = self.api.SystemLibrary.get_engine_version()
            if not engine.startswith("5.8.2-56702186"):
                raise RuntimeError("Native detail requires UE 5.8.2 CL 56702186: " + engine)
            self.report["engine_version"] = engine
            texts = self.inputs["texts"]
            native = self._native_result(
                self.api.YacsLandscapeMeshDiagnosticLibrary.begin_component230_detail(
                    self.component, texts["source"], texts["mask"], texts["trial"], texts["manifest"]),
                "DETAIL_NATIVE_SOURCE_VERIFIED")
            self.native_started = True
            if native.get("vertex_count") != 29415 or native.get("triangle_count") != 58216:
                raise RuntimeError("Native detail v8 vertex/triangle inventory drift")
            mapping = native.pop("source_row_to_native_triangle_id")
            if len(mapping) != 58216 or len(set(mapping)) != 58216:
                raise RuntimeError("Native detail source-row mapping is not one-to-one")
            mapping_path = self.root / "source-row-native-triangle-map.json"
            mapping_path.write_bytes((json.dumps(mapping, separators=(",", ":")) + "\n").encode("utf-8"))
            native["source_row_map_file"] = mapping_path.name
            native["source_row_map_sha256"] = digest(mapping_path)
            self.report["native_source"] = native
            self._make_materials()
            self.handle = self.api.register_slate_post_tick_callback(self.tick)
            self._begin_step()
        except Exception:
            self.stop(traceback.format_exc())

    def _begin_step(self):
        frame, mode = self.steps[self.index]
        if mode == "trial" and self.report["visibility"]["status"] != "VISIBLE_IN_CAPTURED_SCENE":
            self._resolve_visibility()
        if mode == "trial" and self.report["visibility"]["status"] != "VISIBLE_IN_CAPTURED_SCENE":
            raise RuntimeError("Selected patch has no corroborated full-scene render witness; trial is blocked")
        if mode == "trial":
            witness = self.root / self.report["trial"]["witness_receipt_file"]
            if digest(witness) != self.report["trial"]["witness_receipt_sha256"]:
                raise RuntimeError("Native detail visibility witness changed before trial")
        result = self._native_result(
            self.api.YacsLandscapeMeshDiagnosticLibrary.set_component230_detail_mode(self.component, mode),
            "DETAIL_NATIVE_MODE_APPLIED")
        counts = result.get("material_slot_face_counts", [])
        if (len(counts) != 6 or sum(counts) != 58216 or result.get("triangle_count") != 58216
                or result.get("outside_or_shared_normal_max_delta") != 0
                or result.get("topology_unchanged") is not True
                or result.get("native_uvs_unchanged") is not True):
            raise RuntimeError("Native detail mode readback failed")
        if mode == "trial":
            self.report["trial"]["applied"] = True
            self.report["trial"]["visibility_before_trial"] = self.report["visibility"]["status"]
            self.report["trial"]["native_geometry"] = result
        self.report["native_modes"].append(dict(result, frame_id=frame["frame_id"]))
        self.component.notify_mesh_modified()
        if self.component.get_collision_enabled() != self.api.CollisionEnabled.NO_COLLISION:
            raise RuntimeError("Native detail preview collision changed")
        eye, target = self.api.Vector(*frame["camera"]), self.api.Vector(*frame["target"])
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        camera_component = self.camera.get_component_by_class(self.api.CameraComponent)
        camera_component.set_editor_property("field_of_view", frame["fov"])
        actual = self.camera.get_actor_location()
        if any(abs(float(getattr(actual, a)) - value) > 0.0001
               for a, value in zip(("x", "y", "z"), frame["camera"])):
            raise RuntimeError("Native detail camera location readback failed")
        actual_rotation = self.camera.get_actor_rotation()
        if any(abs((float(getattr(actual_rotation, a)) - float(getattr(rotation, a)) + 180) % 360 - 180) > 0.01
               for a in ("pitch", "yaw", "roll")):
            raise RuntimeError("Native detail camera rotation readback failed")
        if abs(float(camera_component.get_editor_property("field_of_view")) - frame["fov"]) > 0.0001:
            raise RuntimeError("Native detail FOV readback failed")
        self.api.SystemLibrary.execute_console_command(self.world, "viewmode lit")
        self.api.SystemLibrary.execute_console_command(self.world, "showflag.DynamicShadows 1")
        self.api.AutomationLibrary.set_editor_viewport_view_mode(self.api.ViewModeIndex.VMI_LIT)
        readiness_root = self.root / "readiness" / (frame["frame_id"] + "-" + mode)
        readiness = prepare_capture(self.api, self.landscape, eye, rotation, readiness_root,
                                    request_height_mips=True)
        self.pending = {
            "frame_id": frame["frame_id"], "mode": mode,
            "camera_location_cm": list(frame["camera"]), "target_cm": list(frame["target"]),
            "camera_rotation_deg": [float(getattr(actual_rotation, a)) for a in ("pitch", "yaw", "roll")],
            "fov_deg": frame["fov"], "viewmode": "lit", "dynamic_shadows": True,
            "readiness": {"status": readiness["status"],
                          "file": (readiness_root / "capture-readiness.json").relative_to(self.root).as_posix(),
                          "sha256": digest(readiness_root / "capture-readiness.json")},
        }
        self.prime = 0
        self._submit()

    def _submit(self):
        prime = self.prime < PRIMES_PER_CAPTURE
        name = self.pending["frame_id"] + "-" + self.pending["mode"] + ".png"
        path = self.root / ("priming" if prime else "frames") / name
        if path.exists() and not prime:
            raise RuntimeError("Native detail refuses stale admitted capture: " + str(path))
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0], res_y=RESOLUTION[1], filename=str(path), camera=self.camera,
            mask_enabled=False, capture_hdr=False, comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes="YACS two-pose native detail and scene-depth witness; no performance or map-wide admission",
            delay=0.0, force_game_view=True)
        if not self.task or not self.task.is_valid_task():
            raise RuntimeError("Invalid native detail screenshot task")
        self.capture_path, self.submitted = path, self.clock()

    def tick(self, _delta):
        if self.stopped or self.task is None:
            return
        try:
            if self.clock() - self.started > 1800 or self.clock() - self.submitted > 120:
                raise RuntimeError("Native detail screenshot/total deadline exceeded")
            if not self.task.is_task_done():
                return
            self.task = None
            decoded = decode_png(self.capture_path)
            if self.prime < PRIMES_PER_CAPTURE:
                self.prime += 1
                self._submit()
                return
            self.report["captures"].append(dict(
                self.pending, file=self.capture_path.relative_to(self.root).as_posix(),
                sha256=digest(self.capture_path), size_bytes=self.capture_path.stat().st_size,
                width_px=decoded[0], height_px=decoded[1]))
            self.index += 1
            self._write()
            if self.index == len(self.steps):
                self.stop()
            else:
                self._begin_step()
        except Exception:
            self.stop(traceback.format_exc())

    def _resolve_visibility(self):
        rows = self.inputs["data"]["manifest"]["selected_face_indices"]
        by_key = {(row["frame_id"], row["mode"]): row for row in self.report["captures"]}
        result = []
        for frame in self.frames:
            pair = [by_key[(frame["frame_id"], mode)] for mode in ("patch-magenta", "patch-cyan")]
            identity = ("camera_location_cm", "target_cm", "camera_rotation_deg", "fov_deg", "viewmode", "dynamic_shadows")
            if any(pair[0][key] != pair[1][key] for key in identity):
                raise RuntimeError("Native visibility pair camera/view/light identity drift")
            projected = projected_patch_pixels(self.inputs["data"]["source"], rows, frame)
            admitted = visible_patch_pixels(
                decode_png(self.root / pair[0]["file"]), decode_png(self.root / pair[1]["file"]), projected)
            witness = self.root / (frame["frame_id"] + "-visible-pixels.json")
            witness.write_bytes((json.dumps(admitted, separators=(",", ":")) + "\n").encode("utf-8"))
            result.append({"frame_id": frame["frame_id"], "projected_candidate_pixels": len(projected),
                           "corroborated_pixels": len(admitted), "pixel_indices_file": witness.name,
                           "pixel_indices_sha256": digest(witness),
                           "magenta_sha256": pair[0]["sha256"], "cyan_sha256": pair[1]["sha256"],
                           "pair_pose_and_view_identical": True})
        self.report["visibility"].update(
            frames=result, status="VISIBLE_IN_CAPTURED_SCENE" if any(
                row["corroborated_pixels"] >= MIN_VISIBLE_PIXELS for row in result) else "NO_CORROBORATED_VISIBILITY")
        witness = self.root / "visibility-witness.json"
        if witness.exists() or self.report["trial"]["applied"]:
            raise RuntimeError("Native detail refuses stale or post-treatment visibility evidence")
        witness_payload = {
            "schema_version": 1, "status": self.report["visibility"]["status"],
            "exact_sha": self.report["exact_sha"], "inputs_sha256": self.inputs["hashes"],
            "trial_applied": False, "visibility": self.report["visibility"],
            "paired_captures": [row for row in self.report["captures"]
                                if row["mode"] in ("patch-magenta", "patch-cyan")],
        }
        witness.write_bytes((json.dumps(witness_payload, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        self.report["trial"].update(witness_receipt_file=witness.name,
                                    witness_receipt_sha256=digest(witness))
        self._write()

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        if self.handle is not None:
            try:
                self.api.unregister_slate_post_tick_callback(self.handle)
            except Exception:
                error = (error + "\n" if error else "") + traceback.format_exc()
            self.handle = None
        try:
            if self.native_started:
                self.report["native_restore"] = self._native_result(
                    self.api.YacsLandscapeMeshDiagnosticLibrary.end_component230_detail(self.component),
                    "DETAIL_NATIVE_RESTORED")
                self.native_started = False
        except Exception:
            error = (error + "\n" if error else "") + traceback.format_exc()
        try:
            if self.original_materials:
                for slot in range(max(6, len(self.original_materials))):
                    self.component.set_material(slot, self.original_materials[slot]
                                                if slot < len(self.original_materials) else None)
            self.component.notify_mesh_modified()
        except Exception:
            error = (error + "\n" if error else "") + traceback.format_exc()
        self.report.update(error=error, status="FAILED" if error else "CAPTURE_PENDING_CLEANUP",
                           capture_wall_seconds=self.clock() - self.started)
        try:
            self._write()
        except Exception:
            error = (error + "\n" if error else "") + traceback.format_exc()
            self.report["error"] = error
        finally:
            self.done(error)

    def mark_cleanup(self, error=None):
        error = error or self.report["error"]
        complete = (len(self.report["captures"]) == 10 and self.report["trial"]["applied"]
                    and self.report["visibility"]["status"] == "VISIBLE_IN_CAPTURED_SCENE"
                    and self.report.get("native_restore", {}).get("status") == "DETAIL_NATIVE_RESTORED")
        self.report["cleanup"] = {"status": "FAILED" if error else "RESTORED"}
        self.report["status"] = "DETAIL_NATIVE_CAPTURE_PASS" if complete and not error else "FAILED"
        self.report["error"] = error or (None if complete else "Incomplete native detail evidence")
        self._write()
