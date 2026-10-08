"""Capture a bounded TPP sphere survey inside the accepted v8 proof scene.

The owning cliff consumer performs scene restoration and certifies cleanup.
This helper never loads/saves a map, edits terrain, or starts another editor.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct
import time
import traceback

from scripts.proof.sa_calobra_tpp_survey import (
    SurveyConfig, build_survey_plan, load_frozen_windows,
)
from scripts.ue.prepare_landscape_capture import prepare_capture

SPHERE = "/Engine/BasicShapes/Sphere.Sphere"
ACCEPTED_LOOK_SHA = "4f2cba560d54931dc8ba080370d96a7aad24f15b"
RESOLUTION = (1280, 720)


class SurveyCapture:
    def __init__(self, api, world, landscape, camera, root, frozen_root,
                 exact_sha, source_scene, done, retain_actor,
                 *, clock=time.monotonic):
        self.api, self.world, self.landscape, self.camera = api, world, landscape, camera
        self.root, self.done, self.retain_actor = Path(root), done, retain_actor
        self.clock = clock
        self.handle = self.task = self.ball = None
        self.index = 0
        self.stopped = False
        self.pending = None
        self.started = clock()
        config = SurveyConfig(exact_sha)
        source = load_frozen_windows(frozen_root)
        plan = build_survey_plan(source['windows'], config,
                                 source_identity=source['source_identity'])
        self.report = dict(plan, planned_frames=plan['frames'], frames=[],
                           status='RUNNING', source_scene=source_scene,
                           saved_to_map=False, physical_simulation=False,
                           performance_acceptance='NOT_MEASURED',
                           visual_acceptance='PENDING_REVIEW', error=None,
                           capture_kind='endpoint-inclusive sampled TPP survey; no continuous video',
                           camera_obstruction='NOT_MEASURED_FIXED_RECIPE_NO_COLLISION_ADJUSTMENT',
                           cleanup={'status': 'PENDING'},
                           resolution=list(RESOLUTION))
        if self.root.exists() and any(self.root.iterdir()):
            raise RuntimeError('Survey output must be empty; refusing stale evidence')
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'frames').mkdir()
        self._write()

    def _write(self):
        # The newest receipt survives interruption without a partial JSON file.
        temporary = self.root / 'survey.json.tmp'
        temporary.write_text(json.dumps(self.report, indent=2, allow_nan=False) + '\n',
                             encoding='utf-8')
        temporary.replace(self.root / 'survey.json')

    def start(self):
        engine = self.api.SystemLibrary.get_engine_version()
        if not engine.startswith('5.8.2-'):
            raise RuntimeError('TPP capture requires the verified UE 5.8.2 runtime: ' + engine)
        self.report['engine_version'] = engine
        mesh = self.api.load_asset(SPHERE)
        if mesh is None:
            raise RuntimeError('Missing native sphere mesh: ' + SPHERE)
        actors = self.api.get_editor_subsystem(self.api.EditorActorSubsystem)
        self.ball = actors.spawn_actor_from_class(
            self.api.StaticMeshActor, self.api.Vector(), self.api.Rotator(), transient=True)
        if self.ball is None:
            raise RuntimeError('Cannot spawn transient survey sphere')
        # Register immediately so failures in setup are cleaned by the owner.
        self.retain_actor(self.ball)
        component = self.ball.get_component_by_class(self.api.StaticMeshComponent)
        if component is None or not component.set_static_mesh(mesh):
            raise RuntimeError('Cannot assign native sphere mesh')
        component.set_editor_property('mobility', self.api.ComponentMobility.MOVABLE)
        component.set_collision_enabled(self.api.CollisionEnabled.NO_COLLISION)
        component.set_cast_shadow(False)
        self.ball.set_actor_label('YACS TPP Survey Sphere (transient, no collision)')
        # Read the actual mesh bounds instead of assuming an engine shape radius.
        _, bounds = self.ball.get_actor_bounds(False)
        extents = [float(getattr(bounds, axis)) for axis in ('x', 'y', 'z')]
        if min(extents) <= 0 or max(extents) - min(extents) > 0.01:
            raise RuntimeError('Native sphere bounds are invalid: ' + str(extents))
        radius = self.report['config']['sphere_radius_m'] * 100.0
        scale = radius / extents[0]
        self.ball.set_actor_scale3d(self.api.Vector(scale, scale, scale))
        _, actual = self.ball.get_actor_bounds(False)
        if any(abs(float(getattr(actual, axis)) - radius) > 0.01 for axis in ('x', 'y', 'z')):
            raise RuntimeError('Sphere radius readback differs from the survey recipe')
        self.report['sphere'] = {'asset': SPHERE, 'radius_cm': radius,
                                 'collision': False, 'cast_shadow': False,
                                 'rotation': 'distance/radius, presentation only'}
        self.handle = self.api.register_slate_post_tick_callback(self.tick)
        self._submit()

    def _submit(self):
        row = self.report['planned_frames'][self.index]
        eye = self.api.Vector(*row['camera_location_cm'])
        target = self.api.Vector(*row['target_cm'])
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        self.camera.get_component_by_class(self.api.CameraComponent).set_editor_property(
            'field_of_view', row['fov_deg'])
        self.ball.set_actor_location(self.api.Vector(*row['ball_location_cm']), False, False)
        forward = row['road_forward_unit']
        heading = math.degrees(math.atan2(forward[1], forward[0]))
        roll = math.degrees(row['travel_distance_m'] / self.report['config']['sphere_radius_m'])
        self.ball.set_actor_rotation(self.api.Rotator(roll % 360, heading, 0), False)
        for actor, expected, label in (
            (self.camera, row['camera_location_cm'], 'camera'),
            (self.ball, row['ball_location_cm'], 'sphere'),
        ):
            actual = actor.get_actor_location()
            if any(abs(float(getattr(actual, axis)) - value) > 0.1
                   for axis, value in zip(('x', 'y', 'z'), expected, strict=True)):
                raise RuntimeError('Survey ' + label + ' position readback failed')
        actual_rotation = self.camera.get_actor_rotation()
        if any(abs((float(getattr(actual_rotation, axis)) - float(getattr(rotation, axis))
                    + 180.0) % 360.0 - 180.0) > 0.01
               for axis in ('pitch', 'yaw', 'roll')):
            raise RuntimeError('Survey camera rotation readback failed')
        actual_fov = float(self.camera.get_component_by_class(
            self.api.CameraComponent).get_editor_property('field_of_view'))
        if abs(actual_fov - row['fov_deg']) > 0.0001:
            raise RuntimeError('Survey camera FOV readback failed')
        readiness_root = self.root / 'readiness' / row['frame_id']
        full_readiness = prepare_capture(self.api, self.landscape, eye, rotation,
                                         readiness_root, request_height_mips=True)
        receipt_path = readiness_root / 'capture-readiness.json'
        readiness = {
            'status': full_readiness['status'],
            'full_height_mips_requested': full_readiness['height_mip_lease_requested'],
            'height_texture_count': len(full_readiness['textures_after']),
            'receipt': receipt_path.relative_to(self.root).as_posix(),
            'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
        path = self.root / row['file']
        if path.exists():
            raise RuntimeError('Survey frame already exists: ' + row['file'])
        self.pending = dict(row, native_readiness=readiness,
                            camera_rotation_deg=[float(getattr(rotation, a))
                                                 for a in ('pitch', 'yaw', 'roll')])
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0], res_y=RESOLUTION[1], filename=str(path),
            camera=self.camera, mask_enabled=False, capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes='YACS sampled bidirectional TPP survey; not a performance benchmark',
            delay=0.0, force_game_view=True)
        if not self.task or not self.task.is_valid_task():
            raise RuntimeError('Invalid TPP screenshot task')
        self.submitted = self.clock()

    def tick(self, _delta):
        if self.stopped or self.task is None:
            return
        try:
            if self.clock() - self.started > 5400:
                raise RuntimeError('TPP survey total capture deadline exceeded (5400s)')
            if self.clock() - self.submitted > 120:
                raise RuntimeError('TPP screenshot deadline exceeded: ' + self.pending['file'])
            if not self.task.is_task_done():
                return
            # Loading/screenshot calls may re-enter Slate; never process a
            # completed task again while preparing its successor.
            self.task = None
            path = self.root / self.pending['file']
            data = path.read_bytes()
            if (len(data) < 45 or data[:8] != b'\x89PNG\r\n\x1a\n'
                    or data[12:16] != b'IHDR'):
                raise RuntimeError('Invalid survey PNG: ' + self.pending['file'])
            width, height = struct.unpack('>II', data[16:24])
            if (width, height) != RESOLUTION:
                raise RuntimeError('Survey PNG dimensions differ from capture recipe')
            self.report['frames'].append(dict(
                self.pending, sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data), width_px=width, height_px=height))
            self.index += 1
            self._write()
            if self.index == self.report['frame_count']:
                self.stop()
            else:
                self._submit()
        except Exception:
            self.stop(traceback.format_exc())

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        if self.handle is not None:
            self.api.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.report['status'] = 'FAILED' if error else 'CAPTURE_PENDING_CLEANUP'
        self.report['error'] = error
        self.report['capture_wall_seconds'] = self.clock() - self.started
        try:
            self._write()
        except Exception:
            error = (error + '\n' if error else '') + traceback.format_exc()
            self.report['status'] = 'FAILED'
            self.report['error'] = error
        finally:
            # Evidence failure must never prevent the owning consumer from
            # restoring the source scene and releasing its native callbacks.
            self.done(error)

    def mark_cleanup(self, error=None):
        self.stopped = True
        if self.handle is not None:
            self.api.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        error = error or self.report['error']
        complete = len(self.report['frames']) == self.report['frame_count']
        self.report['cleanup'] = {'status': 'FAILED' if error else 'RESTORED'}
        self.report['status'] = 'CAPTURED' if complete and not error else 'FAILED'
        self.report['error'] = error or (None if complete else 'Incomplete TPP frame inventory')
        self._write()
