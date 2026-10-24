"""CPU-only checks for the fixed viewport recovery; no native acceptance claim."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('l07_recover', Path(__file__).with_name('lesson07_recover_view.py'))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Vector:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotator:
    def __init__(self, pitch=0, yaw=0, roll=0):
        self.pitch, self.yaw, self.roll = pitch, yaw, roll


class Actor:
    def __init__(self, index):
        self.index = index
        self.origin = Vector(index * 400000, 200000, 30000)
        self.extent = Vector(200000, 200000, 20000)
    def get_class(self):
        return types.SimpleNamespace(get_name=lambda: 'Landscape')
    def get_actor_transform(self):
        return 'unchanged-' + str(self.index)
    def get_actor_bounds(self, colliding):
        assert colliding is False
        return self.origin, self.extent
    def get_actor_label(self):
        return 'Landscape_' + str(self.index)


class FakeUnreal(types.ModuleType):
    UnrealEditorSubsystem = object()
    EditorActorSubsystem = object()
    Vector, Rotator = Vector, Rotator
    def __init__(self):
        super().__init__('unreal')
        self.actors = [Actor(i) for i in range(4)]
        self.world = M.WORLD
        self.pie = None
        self.camera = (Vector(), Rotator())
        self.moves = 0
    def get_editor_subsystem(self, kind):
        assert kind in (self.UnrealEditorSubsystem, self.EditorActorSubsystem)
        return self
    def get_editor_world(self):
        return types.SimpleNamespace(get_path_name=lambda: self.world)
    def get_game_world(self):
        return self.pie
    def get_all_level_actors(self):
        return self.actors
    def get_level_viewport_camera_info(self):
        return self.camera
    def set_level_viewport_camera_info(self, location, rotation):
        self.camera = location, rotation
        self.moves += 1


class RecoveryTests(unittest.TestCase):
    def camera(self, engine):
        out = io.StringIO()
        with patch.dict(sys.modules, {'unreal': engine}), contextlib.redirect_stdout(out):
            exec(M.CAMERA_CODE, {})
        return json.loads(out.getvalue().split('YACS_L07_CAMERA:', 1)[1])

    def test_local_endpoint_extra_vendor_fields(self):
        self.assertEqual(M.endpoint({'url':'http://127.0.0.1:19315/loco','token':'x'*32,'version':1}), (19315,'x'*32))

    def test_remote_or_ambiguous_endpoint_refused(self):
        for url in ('http://localhost:19315/loco','https://127.0.0.1:19315/loco','http://127.0.0.1/loco',
                    'http://127.0.0.1:22/loco','http://10.0.0.1:19315/loco','http://127.0.0.1:19315/loco?x=1',
                    'http://u:p@127.0.0.1:19315/loco','http://127.0.0.1:19315/other'):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                M.endpoint({'url':url,'token':'x'*32})

    def test_invalid_token_refused(self):
        for token in ('short', 'x'*32+'\r\nInjected', None):
            with self.subTest(token=token), self.assertRaises(RuntimeError):
                M.endpoint({'url':'http://127.0.0.1:19315/loco','token':token})

    def test_camera_is_above_every_tile_and_preserves_landscape(self):
        ue = FakeUnreal()
        result = self.camera(ue)
        self.assertEqual(ue.moves, 1)
        self.assertTrue(result['transforms_unchanged'])
        self.assertFalse(result['assets_saved'])
        self.assertGreater(ue.camera[0].z, max(a.origin.z+a.extent.z for a in ue.actors))
        self.assertLess(ue.camera[1].pitch, 0)

    def test_wrong_world_does_not_move(self):
        ue = FakeUnreal(); ue.world = '/Game/Other'
        with self.assertRaisesRegex(RuntimeError,'WRONG_WORLD'):
            self.camera(ue)
        self.assertEqual(ue.moves,0)

    def test_pie_does_not_move(self):
        ue = FakeUnreal(); ue.pie = object()
        with self.assertRaisesRegex(RuntimeError,'PIE_ACTIVE'):
            self.camera(ue)
        self.assertEqual(ue.moves,0)

    def test_unexpected_actor_count_does_not_move(self):
        ue = FakeUnreal(); ue.actors.pop()
        with self.assertRaisesRegex(RuntimeError,'FOUR_LANDSCAPES'):
            self.camera(ue)
        self.assertEqual(ue.moves,0)

    def test_invalid_bounds_do_not_move(self):
        ue = FakeUnreal(); ue.actors[0].extent.x = 0
        with self.assertRaisesRegex(RuntimeError,'INVALID_LOADED_BOUNDS'):
            self.camera(ue)
        self.assertEqual(ue.moves,0)

    def test_camera_setter_must_read_back(self):
        ue = FakeUnreal()
        ue.set_level_viewport_camera_info = lambda *args: None
        with self.assertRaisesRegex(RuntimeError,'READBACK_MISMATCH'):
            self.camera(ue)

    def test_fixed_calls_have_no_asset_or_map_writes(self):
        operations = M.plan()
        self.assertEqual(len(operations),4)
        for operation in operations[2:]:
            self.assertEqual(operation['name'],'edit_material_instance')
            self.assertEqual(set(operation['arguments']),{'name'})
        self.assertEqual(operations[1]['arguments'], {'return_image':False})

    def test_unapproved_rpc_rejected_before_host_access(self):
        client = M.Client.__new__(M.Client)
        with self.assertRaisesRegex(RuntimeError, 'RPC_METHOD'):
            client.rpc('arbitrary')

    def test_modified_payload_rejected_before_host_access(self):
        client = M.Client.__new__(M.Client); client.next_call = 0
        call = M.plan()[0]; call['arguments']['code'] += '\nprint(1)'
        with self.assertRaisesRegex(RuntimeError, 'FIXED_CALL_ONLY'):
            client.rpc('tools/call',call)

    def test_outputs_redact_local_credentials(self):
        text = M.native_text({'content':[{'type':'text','text':'hello secret-value session-value'}]},
                             'secret-value', 'session-value')
        self.assertNotIn('secret-value',text)
        self.assertNotIn('session-value',text)


if __name__ == '__main__':
    unittest.main()
