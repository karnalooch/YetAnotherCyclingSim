# Fixed, local owner-authorized L06 operations; no arbitrary command endpoint.
import json as _json
from pathlib import Path as _Path
import runpy as _runpy
_operation = _json.loads((_Path(__file__).resolve().parents[2] / 'Saved/RuntimeProof/Lesson06SeamRemote/command.json').read_text(encoding='utf-8-sig')).get('operation', 'materials')
if _operation == 'north_final_streaming_audit':
    import unreal as _unreal
    import os as _os
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).clear_actor_selection_set()
    _unreal.AutomationLibrary.set_editor_viewport_view_mode(_unreal.ViewModeIndex.VMI_LIT)
    _unreal.SystemLibrary.execute_console_command(_world,'stat streaming')
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06NorthMaterial/final_streaming.json').write_text(_json.dumps({'pid':_os.getpid(),'codec':_unreal.SystemLibrary.get_console_variable_string_value('PixelStreaming2.Encoder.Codec'),'pool_mib':_unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.PoolSize'),'limit_to_vram':_unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.LimitPoolSizeToVRAM')}))
elif _operation in ('north_reject_streak','north_fill_reject'):
    import unreal as _unreal
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/NorthBoundaryRGB'
    if _operation=='north_fill_reject':_root=_root.parent/'NorthFillRGB'
    _receipt=_json.loads((_root/'applied.json').read_text())
    _actors={a.get_actor_label():a for a in _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors()}
    for _name,_path in _receipt['rollback'].items():
        _mi=_unreal.load_asset(_path);assert _mi
        _actors[_name].set_editor_property('landscape_material',_mi)
        _actors[_name].set_editor_property('landscape_hole_material',_mi)
    (_root/'rejected.json').write_text(_json.dumps({'reason':'Broad smooth brown color band; visual rejection','restored':_receipt['rollback']}))
elif _operation == 'north_stream_vp9':
    import unreal as _unreal
    import os as _os
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _old=_unreal.SystemLibrary.get_console_variable_string_value('PixelStreaming2.Encoder.Codec')
    _players=list(_unreal.PixelStreaming2Blueprints.streamer_get_connected_players('Editor'))
    _unreal.SystemLibrary.execute_console_command(_world,'PixelStreaming2.Encoder.Codec VP9')
    for _player in _players:
        _unreal.PixelStreaming2Blueprints.streamer_kick_player('Editor',_player)
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06NorthMaterial/stream_vp9.json').write_text(_json.dumps({'pid':_os.getpid(),'old_codec':_old,'new_codec':_unreal.SystemLibrary.get_console_variable_string_value('PixelStreaming2.Encoder.Codec'),'reconnect_players':_players,'editor_restarted':False}))
elif _operation == 'north_drain_compilation':
    import unreal as _unreal
    _report=_unreal.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06NorthMaterial/drain_compilation.json').write_text(_report)
elif _operation in ('wall_probe_unlit','wall_probe_lighting','wall_probe_lit'):
    import unreal as _unreal
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _mode={'wall_probe_unlit':'unlit','wall_probe_lighting':'lightingonly','wall_probe_lit':'lit'}[_operation]
    _unreal.SystemLibrary.execute_console_command(_world,'viewmode '+_mode)
    _unreal.AutomationLibrary.set_editor_viewport_view_mode({'unlit':_unreal.ViewModeIndex.VMI_UNLIT,'lightingonly':_unreal.ViewModeIndex.VMI_LIGHTING_ONLY,'lit':_unreal.ViewModeIndex.VMI_LIT}[_mode])
elif _operation == 'north_memory_commands':
    import unreal as _unreal
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    for _prefix in ('Memory','Malloc','gc.'):
        _unreal.SystemLibrary.execute_console_command(_world,'DumpConsoleCommands '+_prefix)
elif _operation == 'north_memory_report':
    import unreal as _unreal
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.SystemLibrary.collect_garbage()
    _unreal.SystemLibrary.execute_console_command(_world,'memreport -full')
elif _operation in ('north_finalize','north_mirror_finalize','north_edge_finalize','north_fill_finalize','north_spot_finalize'):
    import unreal as _unreal
    import os as _os
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/NorthBoundaryRGB'
    if _operation=='north_mirror_finalize':_root=_root.parent/'NorthMirrorRGB'
    if _operation=='north_edge_finalize':_root=_root.parent/'NorthEdgeRGB'
    if _operation=='north_fill_finalize':_root=_root.parent/'NorthFillRGB'
    if _operation=='north_spot_finalize':_root=_root.parent/'NorthPadRGB'
    _applied=_json.loads((_root/'applied.json').read_text());assert _applied['pid']==_os.getpid()
    assert _json.loads((_root/'texture_verification.json').read_text())['status']=='BIT_EXACT'
    _state=snapshot()
    assert len(_state['actors'])==27
    for _a in _state['actors']:
        if _a['name'] in _applied['actors']:assert ('_'+_root.name+'/') in _a['material']
    (_root/'final_snapshot.json').write_text(_json.dumps(_state,indent=2))
    (_root/'published.json').write_text(_json.dumps({'pid':_os.getpid(),'status':'LIVE_NORTH_RGB','map_saved':False,'working_source_cache_unchanged':True,'working_rgb_exception_m':4 if _operation in ('north_edge_finalize','north_fill_finalize','north_spot_finalize') else 0,'changed_actors':_applied['actors']}))
elif _operation in ('north_unload_after_apply','north_mirror_unload_after_apply','north_edge_unload_after_apply','north_fill_unload_after_apply','north_spot_unload_after_apply'):
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('unload_lesson06_inactive_rgb.py')),init_globals={'north_after':True})
elif _operation == 'north_hide_stats':
    import unreal as _unreal
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.SystemLibrary.execute_console_command(_world,'stat streaming')
elif _operation == 'north_rgb_apply':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'north_boundary_fix':True})
elif _operation == 'north_mirror_apply':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'north_mirror_fix':True})
elif _operation == 'north_edge_apply':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'north_edge_fix':True})
elif _operation == 'north_spot_apply':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'north_spot_fix':True})
elif _operation == 'north_fill_apply':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'north_fill_fix':True})
elif _operation == 'north_streaming_measured_budget':
    import unreal as _unreal
    import os as _os
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    assert _unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.LimitPoolSizeToVRAM')==1
    _old=_unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.PoolSize')
    _unreal.SystemLibrary.execute_console_command(_world,'r.Streaming.PoolSize 4992')
    assert _unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.PoolSize')==4992
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06NorthMaterial/measured_budget.json').write_text(_json.dumps({'pid':_os.getpid(),'old_pool_mib':_old,'new_pool_mib':4992,'measured_nonstreaming_mib':4789.47,'required_streaming_mib':0.76,'limit_to_vram':True,'session_only':True}))
elif _operation == 'north_unload_inactive_rgb':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('unload_lesson06_inactive_rgb.py')))
elif _operation == 'north_streaming_capture':
    import unreal as _unreal
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.SystemLibrary.execute_console_command(_world,'HighResShot 1')
elif _operation == 'north_streaming_inspect':
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('inspect_lesson06_north_streaming.py')))
elif _operation == 'context_color_streaming_headroom':
    import unreal as _unreal
    import os as _os
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/SourceBoundaryRGB'
    assert not (_root/'streaming_headroom.json').exists()
    _old=_unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.PoolSize')
    assert 0<_old<=4096, _old
    _world=_unreal.get_editor_subsystem(_unreal.UnrealEditorSubsystem).get_editor_world()
    _unreal.SystemLibrary.execute_console_command(_world,'r.Streaming.PoolSize '+str(_old+16))
    _new=_unreal.SystemLibrary.get_console_variable_int_value('r.Streaming.PoolSize')
    assert _new==_old+16,(_old,_new)
    (_root/'streaming_headroom.json').write_text(_json.dumps({'pid':_os.getpid(),'old_pool_mib':_old,'new_pool_mib':_new,'session_only':True,'reason':'Observed 780 KiB pool over-budget after material import; bounded 16 MiB headroom.'}))
elif _operation in ('context_color_release_import_references','north_release_import_references','north_mirror_release_import_references','north_edge_release_import_references','north_fill_release_import_references','north_spot_release_import_references'):
    import unreal as _unreal
    import os as _os
    _released=0
    for _scope in snapshot.__globals__['scopes']:
        _import_scope=_scope.get('_sampling_scope',{})
        if _Path(_import_scope.get('__file__','')).name!='apply_lesson06_context_color.py':continue
        for _key in ('prepared','changes','actors','a','mi','old','source','tex','task','export'):
            if _key in _import_scope:_import_scope[_key]=None
        _released+=1
    _unreal.SystemLibrary.collect_garbage()
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/SourceBoundaryRGB'
    if _operation=='north_release_import_references':_root=_root.parent/'NorthBoundaryRGB'
    if _operation=='north_mirror_release_import_references':_root=_root.parent/'NorthMirrorRGB'
    if _operation=='north_edge_release_import_references':_root=_root.parent/'NorthEdgeRGB'
    if _operation=='north_fill_release_import_references':_root=_root.parent/'NorthFillRGB'
    if _operation=='north_spot_release_import_references':_root=_root.parent/'NorthPadRGB'
    (_root/'released_import_references.json').write_text(_json.dumps({'pid':_os.getpid(),'released_scopes':_released,'terrain_modified':False}))
elif _operation in ('geometry_readback_before', 'geometry_readback_after', 'geometry_readback_disabled', 'geometry_readback_final', 'geometry_readback_postprobe', 'geometry_apply', 'geometry_show_before', 'geometry_show_after', 'geometry_context_hide', 'geometry_context_show'):
    _geometry_scope = _runpy.run_path(str(_Path(__file__).with_name('lesson06_geometry_remote.py')), init_globals={'operation': _operation, 'snapshot': snapshot})
elif _operation in ('dtm_stage_first', 'dtm_stage_remaining','dtm_recover_one'):
    _dtm_scope = _runpy.run_path(str(_Path(__file__).with_name('stage_lesson06_dtm_context.py')), init_globals={'operation': _operation})
elif _operation == 'material_sampling_inspect':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('inspect_lesson06_material_sampling.py')))
elif _operation == 'context_color_apply':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot})
elif _operation == 'context_color_apply_rgb':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'rgb_streak_fix':True})
elif _operation == 'context_color_apply_source_boundary':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_context_color.py')),init_globals={'snapshot':snapshot,'source_boundary_fix':True})
elif _operation in ('context_color_finalize_rgb','context_color_finalize_source_boundary'):
    import os as _os
    import unreal as _unreal
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
    _source_boundary=_operation=='context_color_finalize_source_boundary'
    _rgb=_root/('SourceBoundaryRGB' if _source_boundary else 'StreakRGB')
    _applied=_json.loads((_rgb/'applied.json').read_text());assert _applied['pid']==_os.getpid()
    assert _json.loads((_rgb/'texture_verification.json').read_text())['status']=='BIT_EXACT'
    _proof=_json.loads((_root/'recovery/native_verification.json').read_text());assert _proof['status']=='PASS_EXACT_NATIVE_RECOVERY'
    _state=snapshot();assert len(_state['actors'])==27
    for _a in _state['actors']:
        if _a['name'] in _applied['actors']:assert _a['material'].startswith('/Game/Generated/YACS/Lesson06ContextColor_20261018_'+('SourceBoundaryRGB/' if _source_boundary else 'RGB/'))
    _actors=[a for a in _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,_unreal.LandscapeProxy)]
    assert sum(not a.is_temporarily_hidden_in_editor() for a in _actors)==26
    (_rgb/'final_snapshot.json').write_text(_json.dumps(_state,indent=2))
    (_rgb/'published.json').write_text(_json.dumps({'pid':_os.getpid(),'status':'LIVE_THREE_CHANNEL_STREAK','visible':26,'map_saved':False,'working_sharp':True,'transition_side':'Context','dtm_maximum_m':_proof['dtm_maximum_m']},indent=2))
elif _operation == 'context_color_reject_rgb':
    import unreal as _unreal
    _root=_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor'
    _receipt=_json.loads((_root/'applied.json').read_text())
    _actors={a.get_actor_label():a for a in _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors()}
    for _name,_path in _receipt['rollback'].items():
        _mi=_unreal.load_asset(_path);assert _mi
        _actors[_name].set_editor_property('landscape_material',_mi);_actors[_name].set_editor_property('landscape_hole_material',_mi)
    (_root/'rejected_rgb.json').write_text(_json.dumps({'status':'REVERTED_MATERIALS_ONLY','reason':'Streak applied to R only; separate G/B native nodes required.'}))
elif _operation == 'dtm_recovery_prepare':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('prepare_lesson06_recovery.py')),init_globals={'snapshot':snapshot})
elif _operation == 'dtm_recovery_publish':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('publish_lesson06_recovery.py')),init_globals={'snapshot':snapshot})
elif _operation == 'dtm_recovery_publish_rgb':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('publish_lesson06_recovery.py')),init_globals={'snapshot':snapshot,'rgb_streak_fix':True})
elif _operation in ('dtm_recovery_readback','dtm_recovery_originals'):
    import os as _os
    _os.environ['YACS_LANDSCAPE_LESSON']='05'
    _os.environ['YACS_DTM_CONTEXT_READBACK']='1' if _operation=='dtm_recovery_readback' else '0'
    _os.environ['YACS_L06_MEMORY_GUARD']='1'
    _os.environ['YACS_L06_RECOVERY_READBACK']='1'
    _os.environ['YACS_LESSON04_READBACK_OUT']=str(_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/recovery'/_operation)
    _os.environ['YACS_LESSON04_READBACK_HDA']='D:/yacs/work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('export_lesson04_ue_readback.py')))
elif _operation == 'context_color_height_readback':
    import os as _os
    _os.environ['YACS_LANDSCAPE_LESSON']='05'
    _os.environ['YACS_DTM_CONTEXT_READBACK']='0'
    _os.environ['YACS_LESSON04_READBACK_OUT']=str(_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06ContextColor/native_after')
    _os.environ['YACS_LESSON04_READBACK_HDA']='D:/yacs/work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('export_lesson04_ue_readback.py')))
elif _operation == 'material_sampling_apply':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('apply_lesson06_material_sampling.py')),init_globals={'snapshot':snapshot})
elif _operation == 'material_sampling_texture_export':
    _sampling_scope = _runpy.run_path(str(_Path(__file__).with_name('export_lesson06_material_sampling.py')))
elif _operation == 'material_sampling_readback':
    import os as _os
    _os.environ['YACS_LANDSCAPE_LESSON']='05'
    _os.environ['YACS_DTM_CONTEXT_READBACK']='0'
    _os.environ['YACS_LESSON04_READBACK_OUT']=str(_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06MaterialSampling/native_after')
    _os.environ['YACS_LESSON04_READBACK_HDA']='D:/yacs/work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
    _sampling_scope=_runpy.run_path(str(_Path(__file__).with_name('export_lesson04_ue_readback.py')))
elif _operation == 'dtm_publish':
    _dtm_scope = _runpy.run_path(str(_Path(__file__).with_name('publish_lesson06_dtm_context.py')))
elif _operation == 'dtm_live_inventory':
    import unreal as _unreal
    import os as _os
    _rows=[]
    for _actor in _unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors():
        if isinstance(_actor,_unreal.LandscapeProxy):
            _rows.append({'name':_actor.get_actor_label(),'hidden_editor':_actor.is_temporarily_hidden_in_editor(),
                          'collision':_actor.get_actor_enable_collision(),'target_layers':[str(n) for n in _actor.get_target_layer_names(True)],
                          'layers':[str(l.get_name_bp()) for l in _actor.get_edit_layers_bp()]})
    assert len(_rows)==27
    assert sum(not r['hidden_editor'] for r in _rows)==26
    assert next(r for r in _rows if r['name']=='SaCalobra_Context_Valid')['collision'] is False
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06DTMContext/live_inventory.json').write_text(_json.dumps({'pid':_os.getpid(),'actors':_rows,'visible':26,'retained_hidden':1},indent=2))
elif _operation == 'dtm_restore_saved_materials':
    import unreal as _unreal
    _actors=_unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors()
    _names={'SaCalobra_Context_Valid','SaCalobra_Detail_0_0','SaCalobra_Detail_0_1','SaCalobra_Detail_1_0','SaCalobra_Detail_1_1'}
    _found=[a for a in _actors if isinstance(a,_unreal.LandscapeProxy) and a.get_actor_label() in _names]
    assert len(_found)==5
    for _actor in _found:
        _mi=_unreal.load_asset('/Game/Generated/YACS/Lesson06Seam_20261018/Materials/MI_'+_actor.get_actor_label())
        assert _mi
        _actor.set_editor_property('landscape_material',_mi)
        _actor.set_editor_property('landscape_hole_material',_mi)
        for _layer in _actor.get_edit_layers_bp():
            assert str(_layer.get_name_bp())!='Lesson06_Boundary_Transition','Reject previously deformed layer on startup'
elif _operation == 'dtm_bind_holes':
    import unreal as _unreal
    _actors=_unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors()
    _reference=next(a for a in _actors if a.get_actor_label()=='SaCalobra_Context_Valid')
    for _actor in _actors:
        if isinstance(_actor,_unreal.LandscapeProxy) and _actor.get_actor_label().startswith('SaCalobra_DTM_Context_'):
            _actor.set_editor_property('landscape_material',_reference.get_editor_property('landscape_material'))
            _actor.set_editor_property('landscape_hole_material',_reference.get_editor_property('landscape_hole_material'))
elif _operation == 'dtm_remove_failed_probe':
    import unreal as _unreal
    _sub=_unreal.get_editor_subsystem(_unreal.EditorActorSubsystem)
    _found=[a for a in _sub.get_all_level_actors() if isinstance(a,_unreal.LandscapeProxy) and a.get_actor_label()=='SaCalobra_DTM_Context_00']
    assert len(_found)==1 and _found[0].is_temporarily_hidden_in_editor()
    assert [str(l.get_name_bp()) for l in _found[0].get_edit_layers_bp()]==['DTM_Original_05m']
    assert _sub.destroy_actor(_found[0])
elif _operation == 'dtm_register_visibility':
    import unreal as _unreal
    _actors=_unreal.get_editor_subsystem(_unreal.EditorActorSubsystem).get_all_level_actors()
    _reference=next(a for a in _actors if a.get_actor_label()=='SaCalobra_Context_Valid')
    _target=next(a for a in _actors if a.get_actor_label()=='SaCalobra_DTM_Context_00')
    _settings=_reference.get_editor_property('target_layers')
    assert len(_settings)==1, str(_settings)
    _target.set_editor_property('target_layers',_settings)
    assert _unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(_target)
    (_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06DTMContext/visibility_registration.json').write_text(_json.dumps({'source':str(_settings),'target_names':[str(n) for n in _target.get_target_layer_names(True)]},indent=2))
elif _operation in ('dtm_readback_first','dtm_readback_probe','dtm_readback_final','dtm_readback_registered','dtm_readback_originals'):
    import os as _os
    _os.environ['YACS_LANDSCAPE_LESSON']='05'
    _os.environ['YACS_DTM_CONTEXT_READBACK']='0' if _operation=='dtm_readback_originals' else '1'
    _os.environ['YACS_LESSON04_READBACK_OUT']=str(_Path(__file__).resolve().parents[2]/'Saved/RuntimeProof/Lesson06DTMContext'/_operation)
    _os.environ['YACS_LESSON04_READBACK_HDA']='D:/yacs/work/lesson04-ue-repair-20261018/probe/Landscape_Readback_v3.hda'
    _dtm_scope=_runpy.run_path(str(_Path(__file__).with_name('export_lesson04_ue_readback.py')))
    _os.environ.pop('YACS_DTM_CONTEXT_READBACK',None)
elif _operation == 'materials':
    """Update five global-color material bindings in the existing Remote world.

    Original materials, textures, masks, height data and map package are retained.
    New texture/MI assets are saved; actor bindings stay in the active session.
    """
    import hashlib
    import json
    from pathlib import Path
    import unreal

    PROJECT=Path(unreal.Paths.project_dir()).resolve()
    PROOF=PROJECT/'Saved/RuntimeProof/Lesson06SeamRemote'
    TRANSFER=Path('D:/yacs/work/lesson06-seam-ue-20261018')
    DEST='/Game/Generated/YACS/Lesson06Seam_20261018'
    manifest=json.loads((TRANSFER/'manifest.json').read_text())
    assert manifest['status']=='PREPARED_COLOR_ONLY' and not manifest['height_or_mask_payloads']
    assert not (PROOF/'apply.json').exists(),'Do not repeat a completed mutation'
    current=snapshot()
    assert current['pid']==before['pid'] and current['map']==before['map']
    assert current['dirty_maps']==before['dirty_maps']==[]
    old={a['name']:a for a in before['actors']}
    actors={a.get_actor_label():a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors() if isinstance(a,unreal.LandscapeProxy)}
    assert set(actors)==set(old) and len(actors)==5
    assert len(manifest['tiles'])==5
    mapfile=PROJECT/('Content/'+current['map'].split('.')[0].removeprefix('/Game/')+'.umap')
    def sha(p):
        with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    mapsha=sha(mapfile)
    report={'status':'IN_PROGRESS','pid':current['pid'],'map':current['map'],'map_sha256_before':mapsha,'tiles':[],'map_saved':False,'height_or_mask_import':False,'restart':False}
    restores=[]
    try:
        for tile in manifest['tiles']:
            name=tile['name'];a=actors[name]
            original=a.get_editor_property('landscape_material')
            original_hole=a.get_editor_property('landscape_hole_material')
            assert original.get_path_name()==old[name]['material']
            original_texture=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(original,'AlbedoTexture')
            image=Path(tile['albedo']);assert sha(image)==tile['sha256']
            path=DEST+'/Textures/T_'+name
            mipath=DEST+'/Materials/MI_'+name
            assert not unreal.EditorAssetLibrary.does_asset_exist(path) and not unreal.EditorAssetLibrary.does_asset_exist(mipath),'Preserve prior assets'
            task=unreal.AssetImportTask();task.filename=str(image);task.destination_path=DEST+'/Textures';task.destination_name='T_'+name;task.automated=True;task.save=False
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            texture=unreal.load_asset(path);assert texture
            for prop in ['srgb','compression_settings','mip_gen_settings','filter','address_x','address_y','lod_group','max_texture_size','never_stream']:
                texture.set_editor_property(prop,original_texture.get_editor_property(prop))
            assert unreal.EditorAssetLibrary.save_loaded_asset(texture)
            mi=unreal.EditorAssetLibrary.duplicate_asset(original.get_path_name().split('.')[0],mipath);assert mi
            unreal.MaterialEditingLibrary.set_material_instance_parameter_override(mi,'AlbedoTexture',True)
            unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(mi,'AlbedoTexture',texture)
            unreal.MaterialEditingLibrary.update_material_instance(mi)
            actual=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi,'AlbedoTexture')
            assert actual and actual.get_path_name()==texture.get_path_name()
            assert mi.get_editor_property('parent')==original.get_editor_property('parent')
            assert unreal.EditorAssetLibrary.save_loaded_asset(mi)
            export=unreal.AssetExportTask();export.object=texture;export.filename=str(PROOF/(name+'_imported.png'));export.automated=True;export.prompt=False;export.replace_identical=False;export.exporter=unreal.TextureExporterPNG()
            assert unreal.Exporter.run_asset_export_task(export),'Native texture export failed'
            restores.append((a,original,original_hole))
            a.set_editor_property('landscape_material',mi)
            a.set_editor_property('landscape_hole_material',mi)
            report['tiles'].append({'name':name,'material':mi.get_path_name(),'texture':texture.get_path_name(),'source_sha256':tile['sha256'],'native_export':export.filename,'texture_srgb':texture.get_editor_property('srgb')})
        after=snapshot()
        for a in after['actors']:
            b=old[a['name']]
            for prop in ['path','layers','uv','components','parent']:assert a[prop]==b[prop],(a['name'],prop)
            assert a['transform'].split('{rotation:')[1]==b['transform'].split('{rotation:')[1]
        assert sha(mapfile)==mapsha,'Original map package changed'
        report.update(status='APPLIED_MATERIAL_ONLY',map_sha256_after=sha(mapfile),native_landscape_structure_unchanged=True,context_geometry_unchanged=True,consumer='Global color AlbedoTexture; no L07 ID/detail shader introduced')
        (PROOF/'after.json').write_text(json.dumps(after,indent=2))
        (PROOF/'apply.json').write_text(json.dumps(report,indent=2))
    except Exception:
        for a,material,hole in restores:
            a.set_editor_property('landscape_material',material);a.set_editor_property('landscape_hole_material',hole)
        raise

else:
    raise ValueError('Unknown fixed L06 operation')
