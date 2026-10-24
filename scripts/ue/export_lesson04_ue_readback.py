import json
import pathlib
import time
import traceback
import unreal
import os
import runpy
memory_guard = runpy.run_path(str(pathlib.Path(__file__).with_name('lesson06_memory_guard.py'))) if os.environ.get('YACS_L06_MEMORY_GUARD')=='1' else None

MAP = "/Game/Generated/YACS/Lesson05_20261018/L_SaCalobra_Lesson05" if os.environ.get("YACS_LANDSCAPE_LESSON") == "05" else "/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test"
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
assert (
    world.get_path_name().split(".")[0]
    == MAP
), "Only the isolated repair map may be measured"
out = pathlib.Path(os.environ["YACS_LESSON04_READBACK_OUT"]).resolve()
assert not out.exists(), "Use a fresh evidence directory"
out.mkdir(parents=True)
hda_path = pathlib.Path(os.environ["YACS_LESSON04_READBACK_HDA"]).resolve()
assert hda_path.is_file()
assetpath = MAP.rsplit("/", 1)[0] + "/Probe/Landscape_Readback_v3"
if not unreal.EditorAssetLibrary.does_asset_exist(assetpath):
    task = unreal.AssetImportTask()
    task.filename = hda_path.as_posix()
    task.destination_path = assetpath.rsplit("/", 1)[0]
    task.destination_name = "Landscape_Readback_v3"
    task.automated = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
asset = unreal.load_asset(assetpath)
assert asset
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()
assert api.is_session_valid()
landscapes = [
    a
    for a in unreal.get_editor_subsystem(
        unreal.EditorActorSubsystem
    ).get_all_level_actors()
    if isinstance(a, unreal.LandscapeProxy)
]
if os.environ.get('YACS_DTM_CONTEXT_READBACK') == '1':
    dtm_root=pathlib.Path(unreal.Paths.project_dir()).resolve()/'Saved/RuntimeProof/Lesson06DTMContext'
    expected={t['name'] for t in json.loads((dtm_root/'windows.json').read_text())['tiles']}
    landscapes=[a for a in landscapes if a.get_actor_label() in expected]
    staged=[]
    stage_paths = list((pathlib.Path(unreal.Paths.project_dir()).resolve()/'Saved/RuntimeProof/Lesson06ContextColor/recovery').glob('stage_*.json')) if os.environ.get('YACS_L06_RECOVERY_READBACK')=='1' else [dtm_root/f for f in ['dtm_stage_first.json','dtm_stage_remaining.json']]
    for stage_path in stage_paths:
        if stage_path.exists():
            receipt=json.loads(stage_path.read_text())
            assert receipt['status']=='STAGED_HIDDEN'
            if os.environ.get('YACS_L06_RECOVERY_READBACK')=='1':assert receipt['pid']==os.getpid()
            staged += [t['name'] for t in receipt['completed']]
    assert {a.get_actor_label() for a in landscapes}==set(staged) and len(staged) in (1,22)
else:
 landscapes=[a for a in landscapes if not a.get_actor_label().startswith('SaCalobra_DTM_Context_')]
 assert {a.get_actor_label() for a in landscapes} == {
    "SaCalobra_Detail_0_0",
    "SaCalobra_Detail_1_0",
    "SaCalobra_Detail_0_1",
    "SaCalobra_Detail_1_1",
    "SaCalobra_Context_Valid",
 }
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
records = []
wrapper = None
current = None
phase = "next"
ready = False
deadline = time.monotonic() + 3600
last_size = None
stable_since = 0
busy = False


def processed(w):
    global ready
    ready = True


def begin(a):
    global wrapper, current, ready, phase
    current = a
    ready = False
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    wrapper = api.instantiate(
        asset,
        unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT,
        settings,
    )
    assert wrapper
    wrapper.process_component_synchronous()
    inp = wrapper.get_input_at_index(0)
    if not isinstance(inp, unreal.HoudiniPublicAPIWorldInput):
        inp = wrapper.create_empty_input(unreal.HoudiniPublicAPIWorldInput)
    inp.set_editor_property("export_height_data_per_edit_layer", False)
    inp.set_editor_property("world_input_auto_update", False)
    inp.set_editor_property("keep_world_transform", True)
    inp.set_editor_property("export_merged_paint_layers", True)
    assert inp.set_input_objects([a])
    assert wrapper.set_input_at_index(0, inp)
    path = out / (a.get_actor_label() + ".bgeo.sc")
    assert not path.exists()
    assert wrapper.set_string_parameter_value("file", path.as_posix())
    wrapper.on_post_processing_delegate.add_callable(processed)
    assert wrapper.recook(), wrapper.get_last_error_message()
    phase = "cook"


def tick(dt):
    global wrapper, phase, ready, last_size, stable_since, busy
    if busy:
        return
    busy = True
    try:
        assert time.monotonic() < deadline, "Native readback timed out"
        if phase == "next":
            if landscapes:
                if memory_guard:memory_guard['require_headroom']()
                begin(landscapes.pop(0))
            else:
                (out / "complete.json").write_text(
                    json.dumps({"status": "EXPORTED", "actors": len(records)})
                )
                unreal.unregister_slate_post_tick_callback(handle)
        elif phase == "cook" and ready:
            assert wrapper.trigger_button_parameter("capture")
            phase = "capture"
            last_size = None
            stable_since = time.monotonic()
        elif phase == "capture":
            a = current
            path = out / (a.get_actor_label() + ".bgeo.sc")
            size = path.stat().st_size if path.exists() else 0
            if size != last_size:
                last_size = size
                stable_since = time.monotonic()
            if size < 1000 or time.monotonic() - stable_since < 3:
                return
            p, s, r = (
                a.get_actor_location(),
                a.get_actor_scale3d(),
                a.get_actor_rotation(),
            )
            records.append(
                {
                    "name": a.get_actor_label(),
                    "location_cm": [p.x, p.y, p.z],
                    "scale": [s.x, s.y, s.z],
                    "rotation": [r.pitch, r.yaw, r.roll],
                    "bytes": path.stat().st_size,
                    "layers": [
                        str(edit_layer.get_name_bp())
                        for edit_layer in a.get_edit_layers_bp()
                    ],
                }
            )
            if os.environ.get("YACS_LANDSCAPE_LESSON") == "05":
                material = a.get_editor_property("landscape_material")
                texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, "AlbedoTexture")
                records[-1]["material"] = material.get_path_name()
                hole_material = a.get_editor_property("landscape_hole_material")
                records[-1]["hole_material"] = hole_material.get_path_name() if hole_material else None
                parent = material.get_editor_property("parent")
                records[-1]["blend_mode"] = str(parent.get_editor_property("blend_mode"))
                records[-1]["opacity_mask_input"] = str(unreal.MaterialEditingLibrary.get_material_property_input_node(parent, unreal.MaterialProperty.MP_OPACITY_MASK))
                records[-1]["albedo"] = texture.get_path_name() if texture else None
                records[-1]["albedo_srgb"] = bool(texture.get_editor_property("srgb")) if texture else None
                records[-1]["uv"] = {}
                for parameter in ("OriginCm", "InvSizeCm"):
                    value = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, parameter)
                    records[-1]["uv"][parameter] = [value.r, value.g, value.b]
            assert wrapper.delete_instantiated_asset()
            wrapper = None
            if memory_guard:
                unreal.SystemLibrary.collect_garbage()
                records[-1]['memory_after']=memory_guard['memory_status']()
            (out / "inventory.json").write_text(json.dumps(records, indent=2))
            phase = "next"
    except Exception:
        (out / "error.json").write_text(
            json.dumps({"error": traceback.format_exc()}, indent=2)
        )
        unreal.unregister_slate_post_tick_callback(handle)
    finally:
        busy = False


handle = unreal.register_slate_post_tick_callback(tick)
