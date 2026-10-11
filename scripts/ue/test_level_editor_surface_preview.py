import copy
import unittest
from types import SimpleNamespace
from scripts.ue import level_editor_surface_preview as surface

class Material:
    def __init__(self,path): self.path=path; self.values={}
    def get_path_name(self): return self.path
    def get_scalar_parameter_value(self,name): return self.values[name]
    def set_scalar_parameter_value(self,name,value): self.values[name]=value

class Component:
    def __init__(self,index,slot,material):
        self.path='/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.L_SaCalobraRoadAsphaltReview:PersistentLevel.DynamicMeshActor_'+str(index)+'.DynamicMeshComponent'
        self.slots=[None]*slot+[material]; self.fail=False
    def get_path_name(self): return self.path
    def get_material(self,slot): return self.slots[slot]
    def set_material(self,slot,value):
        if self.fail and value.get_path_name().startswith('/Engine/Transient.'):
            self.fail=False; raise RuntimeError('injected binding failure')
        self.slots[slot]=value


def fixture():
    obj=object.__new__(surface.SurfacePreview)
    obj.targets=[]
    for i in range(186):
        road=i==0; label='YACS_PERSIST_ROAD' if road else f'YACS_PERSIST_SUPPORT_{i-1:03d}'
        slot=0 if road else 1; mat=Material(surface.ROAD_MATERIAL if road else surface.SHOULDER_MATERIAL)
        obj.targets.append((label,Component(i,slot,mat),slot,mat))
    obj.targets.sort(key=lambda r:r[0])
    obj.preset='original'; obj.materials={}; obj.mids={0:Material('/Engine/Transient.RoadMID'),1:Material('/Engine/Transient.ShoulderMID')}
    obj.initial=obj.observe()
    return obj

class SurfaceTests(unittest.TestCase):
    def test_schema_rejects_unexpected_fields_nonfinite_and_changed_ownership(self):
        obj=fixture(); state=obj.apply('worn')
        for mutate in (lambda s:s.update(extra=True),lambda s:s['parameters'].update(CrackGain=float('nan')),lambda s:s['targets'][0].update(slot=True),lambda s:s['targets'][0].update(current='/Game/Untrusted.Material'),lambda s:s['targets'].pop()):
            bad=copy.deepcopy(state); mutate(bad)
            with self.assertRaises(ValueError): surface.validate_observation(bad,obj.initial)
        bad=copy.deepcopy(state); bad['targets'][0]['component'] += '_other'
        with self.assertRaises(ValueError): surface.validate_observation(bad,obj.initial)

    def test_two_updates_restore_exact_original_bindings(self):
        obj=fixture()
        self.assertEqual(obj.apply('worn')['parameters']['CrackGain'],2.5)
        self.assertEqual(obj.apply('strong')['parameters']['CrackGain'],4.)
        self.assertEqual(obj.restore(),obj.initial)
        self.assertTrue(all(c.get_material(slot) is old for _,c,slot,old in obj.targets))

    def test_partial_binding_failure_restores_all_targets(self):
        obj=fixture(); obj.targets[72][1].fail=True
        with self.assertRaisesRegex(RuntimeError,'injected'): obj.apply('worn')
        self.assertEqual(obj.observe(),obj.initial)

    def test_external_rebind_fails_before_new_mutation(self):
        obj=fixture(); component=obj.targets[2][1]
        component.slots[1]=Material('/Game/External.External')
        with self.assertRaisesRegex(ValueError,'externally'): obj.apply('worn')
        self.assertEqual(component.slots[1].path,'/Game/External.External')

    def test_native_parameter_readback_failure_restores(self):
        obj=fixture()
        obj.mids[0].get_scalar_parameter_value=lambda name:0.
        with self.assertRaisesRegex(ValueError,'readback'): obj.apply('worn')
        self.assertEqual(obj.observe(),obj.initial)

    def test_recovery_preserves_foreign_bindings(self):
        obj=fixture(); obj.apply('worn')
        component=obj.targets[25][1]
        foreign=Material('/Game/External.External'); component.slots[1]=foreign
        with self.assertRaisesRegex(ValueError,'Foreign material preserved'):
            obj.restore(check=False)
        self.assertIs(component.slots[1],foreign)
        self.assertTrue(all(c.get_material(slot) is old for _,c,slot,old in obj.targets if c is not component))

    def test_fixed_preset_boundary(self):
        obj=fixture()
        for value in ('original','arbitrary','../strong'):
            with self.assertRaises(ValueError): obj.apply(value)
        self.assertEqual(obj.observe(),obj.initial)

if __name__=='__main__': unittest.main()

class SurfaceBridgeTests(unittest.TestCase):
    def test_two_live_actions_capture_and_global_restore(self):
        import json
        import tempfile
        from pathlib import Path
        from scripts.ue.test_level_editor_material_bridge import Fixture
        with tempfile.TemporaryDirectory() as temporary:
            f = Fixture(Path(temporary))
            f.manager.surface = fixture()
            f.manager.original_bindings = f.manager.observe()
            original = copy.deepcopy(f.manager.original_bindings)
            for i,preset in enumerate(('worn','strong')):
                request = {'schema_version':1,'session_id':f.manager.identity['session_id'],
                           'request_id':'surface'+str(i),'action':'surface',
                           'expected_sequence':i,'preset':preset}
                result = json.loads(f.manager.handle_json(json.dumps(request)))
                self.assertEqual(result['status'],'ACCEPTED')
                self.assertEqual(result['after']['surface']['preset'],preset)
                f.complete()
                self.assertEqual(f.receipt(request['request_id'])['status'],'COMPLETED')
            restored=f.manager.restore()
            self.assertEqual(restored,original)

    def test_surface_request_refuses_paths_and_extra_parameters(self):
        import json
        from scripts.ue import level_editor_material_bridge as bridge
        base={'schema_version':1,'session_id':'synthetic','request_id':'surface',
              'action':'surface','expected_sequence':0,'preset':'worn'}
        self.assertEqual(bridge.validate_request(json.dumps(base),'synthetic',0,set()),base)
        for update in ({'preset':'/Game/Other'},{'preset':[]},{'CrackGain':10}):
            with self.assertRaises(ValueError):
                bridge.validate_request(json.dumps({**base,**update}),'synthetic',0,set())


class CheckpointTests(unittest.TestCase):
    def _fixture(self, project, *, exists=False, shared=False, compare=True, save=True):
        obj = fixture()
        obj.apply('worn')
        obj.materials = {0: Material('/Engine/Transient.Road'), 1: Material('/Engine/Transient.Shoulder')}
        class World:
            def __init__(self, path): self.path = path
            def get_path_name(self): return self.path
        class Actor:
            def __init__(self, label, component): self.label, self.component = label, component
            def get_actor_label(self): return self.label
            def get_dynamic_mesh_component(self): return self.component
            def get_actor_transform(self): return (0, 0, 0)
        class Options:
            check_connectivity = check_edge_ids = check_normals = check_colors = check_uvs = check_groups = check_attributes = False
            def set_editor_property(self, name, value): setattr(self, name, value)
        obj.world = World('/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.L_SaCalobraRoadAsphaltReview')
        originals, duplicates = [], []
        for label, component, slot, old in obj.targets:
            component.mesh = object()
            component.get_dynamic_mesh = lambda c=component: c.mesh
            component.get_num_materials = lambda c=component: len(c.slots)
            clone = Component(1, slot, component.get_material(slot))
            clone.mesh = component.mesh if shared else object()
            clone.get_dynamic_mesh = lambda c=clone: c.mesh
            clone.get_num_materials = lambda c=clone: len(c.slots)
            originals.append(Actor(label, component))
            duplicates.append(Actor(label, clone))
        calls = []
        def save_asset(asset, dirty):
            calls.append(asset.get_path_name())
            if not save: return False
            path = project / 'Content' / asset.get_path_name().split('.')[0].removeprefix('/Game/')
            path = path.with_suffix('.umap' if isinstance(asset, World) else '.uasset')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic serialized asset')
            return True
        def scalar(instance, name, value): instance.values[name] = value; return True
        obj.api = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(project), convert_relative_path_to_full=lambda p: p),
            get_editor_subsystem=lambda _: SimpleNamespace(get_editor_world=lambda: obj.world),
            UnrealEditorSubsystem=object, DynamicMeshActor=Actor, World=World, Material=Material, MaterialInstanceConstant=Material,
            MaterialInstanceConstantFactoryNew=lambda: object(),
            GeometryScriptIsSameMeshOptions=Options,
            GeometryScript_MeshComparison=SimpleNamespace(is_same_mesh_as=lambda one, two, options: (one, compare, None)),
            GameplayStatics=SimpleNamespace(get_all_actors_of_class=lambda world, cls: originals if world is obj.world else duplicates),
            EditorAssetLibrary=SimpleNamespace(does_directory_exist=lambda _: exists,
                duplicate_loaded_asset=lambda world, path: World(path + '.L_RoadSurface'), save_loaded_asset=save_asset),
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(
                duplicate_asset=lambda name, root, source: Material(root + '/' + name + '.' + name),
                create_asset=lambda name, root, cls, factory: Material(root + '/' + name + '.' + name))),
            MaterialEditingLibrary=SimpleNamespace(recompile_material=lambda _: [], set_material_instance_parent=lambda *_: None,
                set_material_instance_scalar_parameter_value=scalar,
                get_material_instance_scalar_parameter_value=lambda instance, name: instance.values[name],
                update_material_instance=lambda _: None))
        repair = SimpleNamespace(observe=lambda: {'state': 'applied', 'road_unchanged': True})
        return obj, repair, calls

    def test_existing_destination_refused_without_saves_or_live_mutation(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temporary:
            obj, repair, saves = self._fixture(Path(temporary), exists=True)
            before = obj.observe()
            with self.assertRaisesRegex(ValueError, 'already exists'):
                obj.checkpoint(temporary, 'a' * 40, repair)
            self.assertEqual(obj.observe(), before)
            self.assertEqual(saves, [])

    def test_shared_or_changed_copy_mesh_refused_without_saves(self):
        import tempfile
        from pathlib import Path
        for kwargs, message in (({'shared': True}, 'shares owned mesh'), ({'compare': False}, 'native mesh differs')):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temporary:
                obj, repair, saves = self._fixture(Path(temporary), **kwargs)
                before = obj.observe()
                with self.assertRaisesRegex(ValueError, message):
                    obj.checkpoint(temporary, 'a' * 40, repair)
                self.assertEqual(obj.observe(), before)
                self.assertEqual(saves, [])

    def test_copy_saved_under_new_root_with_active_bindings_unchanged(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temporary:
            obj, repair, saves = self._fixture(Path(temporary))
            before = obj.observe()
            result = obj.checkpoint(temporary, 'b' * 40, repair)
            self.assertEqual(obj.observe(), before)
            self.assertEqual(len(saves), 5)
            self.assertTrue(all(path.startswith('/Game/Generated/YACS/LiveCheckpoints/Rbbbbbbbbbbbb/') for path in saves))
            self.assertEqual(result['status'], 'DERIVED_CHECKPOINT_SAVED')
            self.assertEqual(len(result['files']), 5)
            self.assertEqual(result['native_mesh_comparison']['actor_count'], 186)
            self.assertFalse(result['visual_acceptance'])
            self.assertEqual(result['reload_proof'], 'NOT_RUN')
            self.assertTrue(Path(result['receipt_path']).is_file())

    def test_failed_save_does_not_publish_success_receipt_or_change_live_bindings(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temporary:
            obj, repair, saves = self._fixture(Path(temporary), save=False)
            before = obj.observe()
            with self.assertRaisesRegex(ValueError, 'save failed'):
                obj.checkpoint(temporary, 'c' * 40, repair)
            self.assertEqual(obj.observe(), before)
            self.assertFalse(list(Path(temporary).rglob('checkpoint-receipt.json')))
