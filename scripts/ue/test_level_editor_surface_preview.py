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
