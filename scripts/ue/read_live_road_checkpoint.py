"""Read-only fresh-process proof for the fixed #364 derived checkpoint.

This is technical evidence, not Gumball admission, owner visual acceptance or
performance acceptance. It never saves an asset or changes the source world.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import traceback

PROJECT = Path(r'D:\yacs\work\level-editor-review\b9fddea3f602-y473save01')
PACKAGE = '/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40'
MAP = PACKAGE + '/L_RoadSurface'
SAVED_REVISION = '2a00f7ebba403cf7cda663bc6fa303c7d72e891b'
SOURCE_WORLD = '/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.L_SaCalobraRoadAsphaltReview'
RECEIPT = PROJECT / 'Content/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/checkpoint-receipt.json'
RELATIVE_SCRIPT = 'scripts/ue/read_live_road_checkpoint.py'
EXPECTED_FILES = {
    'L_RoadSurface.umap': (193245865, 'cf806999d73e6762ba6d91fab8b4e29d6c475a828ad9afcd525462054602ed1a'),
    'M_Road.uasset': (44025, 'd5bf7fdc7d34e70c30b29ec37d2f4c04afa01cd3dc9a9c12cec707be48078842'),
    'M_Shoulder.uasset': (66132, '94c40717a34d2b18f6d706abc7714cb6cbfb4ed0d631dda8bd1c624c38e7ae65'),
    'MI_Road.uasset': (10022, '7d96a2396bb8ef9e5d4d19d65b6c7e9d00e7b0e80ebd5ff5733dbab1a61e9a92'),
    'MI_Shoulder.uasset': (11428, '76425a2289c3907a8f3c831ad24fb1ba1f219e79204507efdce222c831c76cdf'),
}
CAMERA = (56912.43746055451, 53090.5078449409, 46766.459277036185)
TARGET = (58088.73631673153, 52542.60698992016, 46508.19271952782)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_saved_receipt(value):
    require(isinstance(value, dict) and value.get('schema_version') == 1,
            'Checkpoint receipt schema differs')
    require(value.get('status') == 'DERIVED_CHECKPOINT_SAVED'
            and value.get('revision') == SAVED_REVISION and value.get('map_package') == MAP
            and value.get('preset') == 'worn' and value.get('active_source_unchanged') is True
            and value.get('source_world') == SOURCE_WORLD,
            'Checkpoint saved identity differs')
    require(value.get('native_mesh_comparison') == {
        'actor_count': 559, 'all_attributes': True, 'epsilon': 0.0, 'road_equal': True},
        'Saved native mesh comparison differs')
    files = value.get('files')
    require(isinstance(files, list) and len(files) == 5, 'Expected exactly five packages')
    expected_prefix = 'Content/' + PACKAGE.removeprefix('/Game/') + '/'
    expected = {expected_prefix + name: identity for name, identity in EXPECTED_FILES.items()}
    actual = {}
    for row in files:
        require(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'},
                'Package row schema differs')
        require(row['path'] not in actual, 'Duplicate package path')
        actual[row['path']] = (row['bytes'], row['sha256'])
    require(actual == expected, 'Package inventory or pinned bytes differ')
    rows = value.get('bindings')
    require(isinstance(rows, list) and len(rows) == 186, 'Expected 186 material bindings')
    labels = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'label', 'slot', 'material'},
                'Binding schema differs')
        label = row['label']
        require(isinstance(label, str) and (label == 'YACS_PERSIST_ROAD'
                or re.fullmatch(r'YACS_PERSIST_SUPPORT_\d{3}', label)), 'Binding label differs')
        require(label not in labels, 'Duplicate material owner')
        labels.add(label)
        road = label == 'YACS_PERSIST_ROAD'
        suffix = 'Road' if road else 'Shoulder'
        require(type(row['slot']) is int and row['slot'] == (0 if road else 1)
                and row['material'] == PACKAGE + '/MI_' + suffix + '.MI_' + suffix,
                'Persistent material binding differs')
    require('YACS_PERSIST_ROAD' in labels, 'Road binding missing')
    repair = value.get('repair', {})
    require(repair.get('road_unchanged') is True and repair.get('landscape_mutated') is False
            and [row['label'] for row in repair.get('targets', [])] == ['YACS_PERSIST_SUPPORT_112'],
            'Saved repair scope differs')
    return value


def verify_packages(project, receipt):
    result = []
    for row in receipt['files']:
        path = project / row['path']
        require(path.resolve().is_relative_to(project.resolve()), 'Package escaped project')
        require(path.is_file() and path.stat().st_size == row['bytes']
                and sha256(path) == row['sha256'], 'Package bytes changed: ' + row['path'])
        result.append(dict(row))
    return result


def validate_png(path):
    raw = path.read_bytes()
    require(len(raw) > 4096 and raw[:8] == b'\x89PNG\r\n\x1a\n'
            and raw[12:16] == b'IHDR' and struct.unpack('>II', raw[16:24]) == (1280, 720),
            'Native screenshot missing or wrong dimensions')
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def authenticate_reader():
    revision = os.environ['YACS_CHECKPOINT_PROOF_SHA']
    require(re.fullmatch('[0-9a-f]{40}', revision), 'Proof SHA must be full commit')
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    require(git('rev-parse', 'HEAD').decode().strip() == revision, 'Proof checkout HEAD differs')
    blob = git('show', revision + ':' + RELATIVE_SCRIPT)
    require(Path(__file__).read_bytes() == blob, 'Reader physical bytes differ from commit')
    # Imported production validators must also be exactly the committed bytes.
    for name in ('level_editor_surface_preview.py', 'road_shoulder_network.py'):
        relative = 'scripts/ue/' + name
        require((root / relative).read_bytes() == git('show', revision + ':' + relative),
                'Imported helper physical bytes differ: ' + name)
    sys.path.insert(0, str(root))
    return revision


def read_native(api, saved):
    from scripts.ue.level_editor_surface_preview import PRESETS
    from scripts.ue.road_shoulder_network import inspect_mesh
    editor = api.get_editor_subsystem(api.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world.get_path_name() == MAP + '.L_RoadSurface', 'Fresh process loaded wrong map')
    actors = {}
    for actor in api.GameplayStatics.get_all_actors_of_class(world, api.DynamicMeshActor):
        label = actor.get_actor_label()
        require(label not in actors, 'Duplicate native actor label')
        actors[label] = actor
    require(len(actors) == 559, 'Fresh native actor inventory differs')
    for row in saved['bindings']:
        require(row['label'] in actors, 'Saved material owner is missing')
        material = actors[row['label']].get_dynamic_mesh_component().get_material(row['slot'])
        require(material is not None and material.get_path_name() == row['material'],
                'Fresh native material binding differs: ' + row['label'])
    parameters = {}
    for suffix in ('Road', 'Shoulder'):
        instance = api.load_asset(PACKAGE + '/MI_' + suffix)
        master = api.load_asset(PACKAGE + '/M_' + suffix)
        require(isinstance(instance, api.MaterialInstanceConstant) and isinstance(master, api.Material),
                'Fresh persistent material type differs')
        require(instance.get_editor_property('parent') == master, 'Persistent material parent differs')
        expected = {name: value for name, value in PRESETS['worn'].items()
                    if suffix == 'Shoulder' or not name.startswith('Edge')}
        require({str(name) for name in api.MaterialEditingLibrary.get_scalar_parameter_names(master)}
                == set(expected), 'Fresh scalar inventory differs')
        parameters[suffix] = {}
        for name, expected_value in expected.items():
            actual = api.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(instance, name)
            require(math.isfinite(actual) and abs(actual - expected_value) < 1e-5,
                    'Fresh scalar readback differs: ' + name)
            parameters[suffix][name] = actual
    # Native C++ inspector intentionally accepts the original source maps only.
    # Load source UObject without switching the active derived map; retain its gate.
    source = api.load_asset(saved['source_world'])
    require(isinstance(source, api.World), 'Saved source world could not be loaded')
    originals = {actor.get_actor_label(): actor for actor in
                 api.GameplayStatics.get_all_actors_of_class(source, api.DynamicMeshActor)}
    require(set(originals) == set(actors), 'Source/derived native actor inventories differ')
    road_summary = inspect_mesh(api, originals['YACS_PERSIST_ROAD'].get_dynamic_mesh_component())['summary']
    require(road_summary == saved['repair']['road_summary'], 'Frozen source road hash differs')
    options = api.GeometryScriptIsSameMeshOptions()
    for token in ('checkconnectivity', 'checkedgeids', 'checknormals', 'checkcolors', 'checkuvs', 'checkgroups', 'checkattributes'):
        names = [name for name in dir(options) if name.replace('_', '').lower() == token]
        require(len(names) == 1, 'Native comparison option missing: ' + token)
        options.set_editor_property(names[0], True)
    options.set_editor_property('epsilon', 0.0)
    compared = 0
    for label, actor in actors.items():
        require(actor.get_actor_transform() == originals[label].get_actor_transform(),
                'Saved actor transform differs: ' + label)
        if label == 'YACS_PERSIST_SUPPORT_112':
            continue
        result = api.GeometryScript_MeshComparison.is_same_mesh_as(
            actor.get_dynamic_mesh_component().get_dynamic_mesh(),
            originals[label].get_dynamic_mesh_component().get_dynamic_mesh(), options)
        require(isinstance(result, tuple) and len(result) == 3 and result[1] is True,
                'Reopened native geometry differs: ' + label)
        compared += 1
    require(editor.get_editor_world() == world, 'Reader switched active world')
    return {'native_actor_count': len(actors), 'native_binding_count': len(saved['bindings']),
            'scalar_readback': parameters, 'source_road_summary': road_summary,
            'exact_source_mesh_comparisons': compared, 'comparison_epsilon': 0.0,
            'comparison_all_attributes': True,
            'saved_repair_package_hash_verified': True,
            'repair_delta_reproved': False,
            'repair_delta_limitation': 'Saved receipt has no repaired-support post-save buffer hash'}


def main():
    import unreal as api
    token = os.environ['YACS_CHECKPOINT_PROOF_TOKEN']
    require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,47}', token), 'Invalid proof token')
    require(Path(api.Paths.project_dir()).resolve() == PROJECT, 'Wrong proof project root')
    output = PROJECT / 'Saved/RuntimeProof/LiveRoadCheckpoint' / token
    require(not output.exists(), 'Proof output already exists; refusing overwrite')
    output.mkdir(parents=True)
    receipt_path = output / 'receipt.json'
    result = {'schema_version': 1, 'status': 'BLOCKED', 'editor_pid': os.getpid(),
              'project_root': str(PROJECT), 'map_package': MAP,
              'saved_handler_revision': SAVED_REVISION, 'owner_visual_status': 'PENDING_FINAL_M3',
              'performance_status': 'DEFERRED_AFTER_M3', 'performance_pass': False,
              'assets_saved': False, 'proof_admission': 'NOT_REQUESTED'}
    state = {'handle': None, 'task': None, 'started': time.monotonic(), 'finished': False}
    def finish(error=None):
        if state['finished']:
            return
        state['finished'] = True
        if state['handle'] is not None:
            api.unregister_slate_post_tick_callback(state['handle'])
        if error is not None:
            result.update(status='BLOCKED', error=str(error))
        receipt_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        api.SystemLibrary.quit_editor()
    try:
        result['proof_reader_revision'] = authenticate_reader()
        saved = validate_saved_receipt(json.loads(RECEIPT.read_text(encoding='utf-8')))
        result['checkpoint_receipt_sha256'] = sha256(RECEIPT)
        result['files_before'] = verify_packages(PROJECT, saved)
        result['native'] = read_native(api, saved)
        result['engine_version'] = api.SystemLibrary.get_engine_version()
        editor = api.get_editor_subsystem(api.UnrealEditorSubsystem)
        location = api.Vector(*CAMERA)
        rotation = api.MathLibrary.find_look_at_rotation(location, api.Vector(*TARGET))
        editor.set_level_viewport_camera_info(location, rotation)
        screenshot = output / 'reopened-road.png'
        def tick(_delta):
            try:
                elapsed = time.monotonic() - state['started']
                require(elapsed < 180, 'Fresh render timeout')
                if state['task'] is None:
                    if elapsed < 10:
                        return
                    api.AutomationLibrary.finish_loading_before_screenshot()
                    state['task'] = api.AutomationLibrary.take_high_res_screenshot(
                        res_x=1280, res_y=720, filename=str(screenshot), mask_enabled=False,
                        capture_hdr=False, comparison_tolerance=api.ComparisonTolerance.LOW,
                        comparison_notes='Fresh #364 saved checkpoint technical render; visual acceptance pending',
                        delay=0.0, force_game_view=False)
                    require(state['task'] is not None and state['task'].is_valid_task(),
                            'Native screenshot task invalid')
                    return
                if not state['task'].is_task_done():
                    return
                result['screenshot'] = validate_png(screenshot)
                result['files_after'] = verify_packages(PROJECT, saved)
                require(result['files_before'] == result['files_after'], 'Proof altered saved packages')
                result['status'] = 'SAVED_CHECKPOINT_REOPENED_RENDERED'
                finish()
            except Exception:
                finish(traceback.format_exc())
        state['handle'] = api.register_slate_post_tick_callback(tick)
    except Exception:
        finish(traceback.format_exc())


if __name__ == '__main__':
    main()
