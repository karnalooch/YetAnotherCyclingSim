"""Sequential fixed-command recovery from already verified DTM caches."""
import json,time,runpy,ctypes
from pathlib import Path
P=Path(__file__).resolve().parents[2];O=P/'Saved/RuntimeProof/Lesson06ContextColor/recovery'
C=P/'Saved/RuntimeProof/Lesson06SeamRemote'
pid=json.loads((C/'ready.json').read_text())['pid']
memory=runpy.run_path(str(Path(__file__).with_name('lesson06_memory_guard.py')))
handle=ctypes.windll.kernel32.OpenProcess(0x100000,False,pid);assert handle
try:
    for index in range(22):
        assert ctypes.windll.kernel32.WaitForSingleObject(handle,0)==258,'Editor stopped'
        status=memory['require_headroom']()
        receipt=O/('stage_'+str(index).zfill(2)+'.json')
        assert not receipt.exists()
        ident=f'context-recovery-{pid}-{index:02}'
        (C/'command.json').write_text(json.dumps({'id':ident,'action':'apply','operation':'dtm_recover_one','tile_index':index}))
        deadline=time.monotonic()+900
        while time.monotonic()<deadline:
            assert ctypes.windll.kernel32.WaitForSingleObject(handle,0)==258,'Editor stopped'
            if receipt.exists():
                try:r=json.loads(receipt.read_text())
                except json.JSONDecodeError:time.sleep(1);continue
                assert r['status']!='ERROR',r
                if r['status']=='STAGED_HIDDEN':
                    assert r['pid']==pid
                    print('RECOVERED',index+1,'/22',json.dumps(r.get('memory_after',{})),flush=True)
                    break
            if (C/'command_result.json').exists():
                r=json.loads((C/'command_result.json').read_text())
                assert not (r.get('id')==ident and r['status']=='ERROR'),r
            time.sleep(2)
        else:raise TimeoutError(index)
        time.sleep(3) # Allow queued native GC to finish before the next import.
    (O/'complete.json').write_text(json.dumps({'pid':pid,'status':'RECOVERED_22_HIDDEN'}))
finally:ctypes.windll.kernel32.CloseHandle(handle)
