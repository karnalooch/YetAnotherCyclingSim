import os
import time
import hashlib
import json
from pathlib import Path
import unreal

EVIDENCE_DIR = os.environ["YACS_L07_CAPTURE_OUTPUT"]
os.makedirs(EVIDENCE_DIR, exist_ok=False)
LOG_FILE = os.path.join(EVIDENCE_DIR, "ue_capture_log.txt")
MAP_FILE = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())) / "Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap"

def map_hash():
    with MAP_FILE.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

MAP_BEFORE = map_hash()
RESULTS = []
RENDER_CONTEXT = {}
SCRIPT_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("=== START LESSON 07 UE OFFSCREEN CAPTURE ===\n")

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    unreal.log(f"[UE_CAPTURE] {msg}")

MAP_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MAT_NEUTRAL = "/Game/Worlds/SaCalobra_Houdini_20261016/Materials/M_TerrainReview"
MAT_MATERIAL = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"

SHOTS = [
    # 1. Full Domain Panorama (Material)
    {
        "name": "ue_panorama_material.png",
        "cam": unreal.Vector(-810000.0, -900000.0, 724000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": MAT_MATERIAL,
        "note": "Full terrain panorama with Pegasus master material, global color and PBR lighting"
    },
    # 2. Full Domain Panorama (Neutral Clay)
    {
        "name": "ue_panorama_neutral.png",
        "cam": unreal.Vector(-810000.0, -900000.0, 724000.0),
        "target": unreal.Vector(0.0, 0.0, 40000.0),
        "fov": 75.0,
        "material": MAT_NEUTRAL,
        "note": "Full terrain panorama with neutral review material"
    },
    # 3. Authentic Scree Occurrence Closeup (Material)
    {
        "name": "ue_closeup_scree.png",
        # Authenticated L06 IDMap texel (2981,4311), not the old guessed centroid.
        "cam": unreal.Vector(-250925.0, -184475.0, 33571.0),
        "target": unreal.Vector(-250925.0, -184425.024414, 4464.797211),
        "fov": 50.0,
        "material": MAT_MATERIAL,
        "note": "Closeup Scree occurrence showing normal map response and roughness under sunlight"
    },
    # 4. Authentic Scree Occurrence Closeup (Neutral Clay) - Identical camera!
    {
        "name": "ue_closeup_scree_neutral.png",
        "cam": unreal.Vector(-250925.0, -184475.0, 33571.0),
        "target": unreal.Vector(-250925.0, -184425.024414, 4464.797211),
        "fov": 50.0,
        "material": MAT_NEUTRAL,
        "note": "Closeup Scree occurrence neutral shading from identical camera and lighting"
    },
    # 5. Puig Major Summit Ridge
    {
        "name": "ue_closeup_puig_major.png",
        "cam": unreal.Vector(-278375.0, 199525.0, 180000.0),
        "target": unreal.Vector(-128375.0, 349525.0, 143716.0),
        "fov": 50.0,
        "material": MAT_MATERIAL,
        "note": "Closeup Puig Major summit ridge showing rock/cliffs surface and global tint"
    },
    # 6. Sa Calobra Cove Beach and Bay
    {
        "name": "ue_closeup_sa_calobra_cove.png",
        "cam": unreal.Vector(47000.0, -180000.0, 16000.0),
        "target": unreal.Vector(47000.0, -106000.0, 1034.0),
        "fov": 45.0,
        "material": MAT_MATERIAL,
        "note": "Historical cove camera; geographic framing requires image review"
    },
    # 7. Two-class boundary transition (Scree / Cliffs)
    {
        "name": "ue_closeup_transition.png",
        "cam": unreal.Vector(-250925.0, -184475.0, 33571.0),
        "target": unreal.Vector(-250925.0, -184425.024414, 4464.797211),
        "fov": 40.0,
        "material": MAT_MATERIAL,
        "note": "Authenticated Scree neighbourhood; adjacent classes require image review"
    },
    # 8. Tile Seam Inspection across X=0 border
    {
        "name": "ue_tile_seam_check.png",
        "cam": unreal.Vector(-5000.0, -5000.0, 55000.0),
        "target": unreal.Vector(-25.0, -25.0, 47350.0),
        "fov": 40.0,
        "material": MAT_MATERIAL,
        "note": "Closeup inspection across tile seam at domain center verifying continuous UV mapping and lighting"
    }
]

selected_shots = os.environ.get("YACS_L07_CAPTURE_SHOTS", "").split(",")
if selected_shots != [""]:
    requested = set(selected_shots)
    if len(requested) != len(selected_shots) or requested - {shot["name"] for shot in SHOTS}:
        raise ValueError("Capture selection must contain unique existing shot filenames")
    SHOTS = [shot for shot in SHOTS if shot["name"] in requested]

_current_idx = 0
_camera = None
_task = None
_start_time = 0.0
_handle = None
_cooling_down = False
_cooldown_start = 0.0
_current_mat_path = None
_actual_camera = None

def set_landscape_material(mat_path):
    global _current_mat_path
    if _current_mat_path == mat_path:
        return
    log(f"Setting landscape material to {mat_path}...")
    mat_asset = unreal.EditorAssetLibrary.load_asset(mat_path)
    if not mat_asset:
        raise RuntimeError(f"Failed to load material asset: {mat_path}")
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in actor_subsystem.get_all_level_actors():
        if isinstance(a, unreal.LandscapeProxy):
            a.set_editor_property("landscape_material", mat_asset)
    _current_mat_path = mat_path

def finish(error=""):
    global _handle
    if _handle is not None:
        unreal.unregister_slate_post_tick_callback(_handle)
        _handle = None
    # Restore Pegasus material before exit
    try:
        set_landscape_material(MAT_MATERIAL)
    except Exception as e:
        error = error or f"Failed to restore transient material: {e}"

    after = map_hash()
    if after != MAP_BEFORE:
        error = error or "Saved map bytes changed during capture"
    with open(os.path.join(EVIDENCE_DIR, "capture-report.json"), "w", encoding="utf-8") as stream:
        json.dump({"status": "FAIL" if error else "CAPTURED_VISUAL_REVIEW_PENDING",
                   "script_sha256": SCRIPT_SHA256,
                   "error": error, "map": MAP_PATH, "map_before_sha256": MAP_BEFORE,
                   "map_after_sha256": after, "map_unchanged": after == MAP_BEFORE,
                   "engine_version": unreal.SystemLibrary.get_engine_version(),
                   "render_context": RENDER_CONTEXT,
                   "shots": RESULTS, "owner_visual_pass": False}, stream, indent=2)
    if error:
        log(f"ERROR: {error}")
    else:
        log("All shots captured and verified successfully!")
    log("Quitting editor...")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def schedule_current_shot():
    global _camera, _task, _start_time, _current_idx, _actual_camera
    if _current_idx >= len(SHOTS):
        finish()
        return

    shot = SHOTS[_current_idx]
    out_file = os.path.join(EVIDENCE_DIR, shot["name"])
    if os.path.exists(out_file):
        finish(f"Refusing to overwrite capture: {out_file}")
        return

    log(f"--- Scheduling [{_current_idx + 1}/{len(SHOTS)}] {shot['name']} ---")
    set_landscape_material(shot["material"])

    rot = unreal.MathLibrary.find_look_at_rotation(shot["cam"], shot["target"])

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if _camera is None:
        _camera = actor_subsystem.spawn_actor_from_class(unreal.CameraActor, shot["cam"], rot, transient=True)
    else:
        _camera.set_actor_location(shot["cam"], False, False)
        _camera.set_actor_rotation(rot, False)

    cam_comp = _camera.get_component_by_class(unreal.CameraComponent)
    cam_comp.set_editor_property("field_of_view", shot["fov"])
    actual_location = _camera.get_actor_location()
    actual_rotation = _camera.get_actor_rotation()
    _actual_camera = {
        "location_cm": [actual_location.x, actual_location.y, actual_location.z],
        "rotation_deg_pitch_yaw_roll": [
            actual_rotation.pitch, actual_rotation.yaw, actual_rotation.roll
        ],
        "fov": float(cam_comp.get_editor_property("field_of_view")),
    }

    unreal.AutomationLibrary.set_editor_viewport_view_mode(unreal.ViewModeIndex.VMI_LIT)
    unreal.AutomationLibrary.finish_loading_before_screenshot()

    _task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=out_file,
        camera=_camera,
        mask_enabled=False,
        capture_hdr=False,
        comparison_tolerance=unreal.ComparisonTolerance.LOW,
        comparison_notes=shot["note"],
        delay=2.0,
        force_game_view=False
    )
    _start_time = time.monotonic()

    if not _task or not _task.is_valid_task():
        finish(f"Invalid screenshot task for {shot['name']}")

def tick_impl(_delta):
    global _current_idx, _task, _start_time, _cooling_down, _cooldown_start
    if _task is None and not _cooling_down:
        return

    now = time.monotonic()
    elapsed = now - _start_time

    if _cooling_down:
        if now - _cooldown_start > 1.5:
            _cooling_down = False
            _current_idx += 1
            schedule_current_shot()
        return

    shot = SHOTS[_current_idx]
    target_file = os.path.join(EVIDENCE_DIR, shot["name"])
    file_ready = os.path.exists(target_file) and os.path.getsize(target_file) > 50000

    if _task.is_task_done() and file_ready:
        log(f"Shot {shot['name']} captured successfully ({os.path.getsize(target_file)} bytes in {elapsed:.2f}s)")
        with open(target_file, "rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        RESULTS.append({"name": shot["name"], "sha256": digest,
                        "camera_cm": [shot["cam"].x, shot["cam"].y, shot["cam"].z],
                        "target_cm": [shot["target"].x, shot["target"].y, shot["target"].z],
                        "fov": shot["fov"], "actual_camera": _actual_camera,
                        "material": shot["material"], "note": shot["note"]})
        _task = None
        _cooling_down = True
        _cooldown_start = now
    elif elapsed > 120.0:
        finish(f"Shot {shot['name']} timed out after {elapsed:.2f}s (file_ready={file_ready})")

def tick(delta):
    try:
        tick_impl(delta)
    except Exception:
        import traceback
        finish(traceback.format_exc())

def observe_render_context():
    """Record native settings; unresolved properties remain explicitly unknown."""
    def properties(obj, names):
        observed = {}
        for name in names:
            try:
                value = obj.get_editor_property(name)
                observed[name] = {
                    "observed": True,
                    "value": value if isinstance(value, (bool, int, float)) else str(value),
                }
            except Exception as error:
                observed[name] = {"observed": False, "error": str(error)}
        return observed

    instance = unreal.load_asset(MAT_MATERIAL)
    parent = instance.get_editor_property("parent")
    RENDER_CONTEXT["material"] = {
        "instance": instance.get_path_name(), "parent": parent.get_path_name(),
        "properties": properties(parent, ("enable_tessellation", "displacement_scaling",
                                         "max_world_position_offset_displacement")),
        "instance_base_property_overrides": properties(
            instance, ("base_property_overrides",)),
    }
    neutral = {"asset": MAT_NEUTRAL, "observed": False, "graph_verified": False}
    try:
        neutral_material = unreal.load_asset(MAT_NEUTRAL)
        if not isinstance(neutral_material, unreal.Material):
            raise RuntimeError("Expected the existing neutral Material asset")
        blend = neutral_material.get_editor_property("blend_mode")
        uses_attributes = bool(neutral_material.get_editor_property("use_material_attributes"))
        opacity = unreal.MaterialEditingLibrary.get_material_property_input_node(
            neutral_material, unreal.MaterialProperty.MP_OPACITY_MASK
        )
        neutral.update(
            observed=True,
            blend_mode=str(blend),
            use_material_attributes=uses_attributes,
            opacity_input=None if opacity is None else {
                "path": opacity.get_path_name(), "class": opacity.get_class().get_name()
            },
            graph_verified=(
                blend == unreal.BlendMode.BLEND_MASKED
                and not uses_attributes
                and isinstance(opacity, unreal.MaterialExpressionLandscapeVisibilityMask)
            ),
        )
        if not neutral["graph_verified"]:
            neutral["reason"] = "Direct masked neutral visibility graph was not confirmed"
    except Exception as error:
        neutral["reason"] = str(error)
    neutral["landscape_visibility_data_proved"] = False
    neutral["collision_proved"] = False
    RENDER_CONTEXT["neutral_material"] = neutral
    RENDER_CONTEXT["landscapes"] = [{
        "actor": actor.get_name(),
        "properties": properties(actor, ("enable_nanite",)),
    } for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
        if isinstance(actor, unreal.LandscapeProxy)]

try:
    log(f"Loading level {MAP_PATH}...")
    level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level_subsystem.load_level(MAP_PATH):
        raise RuntimeError("Could not load the existing L07 level")
    log("Level loaded successfully.")
    observe_render_context()

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    schedule_current_shot()
    _handle = unreal.register_slate_post_tick_callback(tick)

except Exception:
    import traceback
    finish(traceback.format_exc())
