"""Read Windows commit headroom before bounded UE/Houdini operations."""
import ctypes
from ctypes import wintypes

class MemoryStatus(ctypes.Structure):
    _fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total_phys','avail_phys','total_commit','avail_commit','total_virtual','avail_virtual','avail_extended')]

def memory_status():
    m=MemoryStatus();m.length=ctypes.sizeof(m)
    assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {'available_commit_bytes':m.avail_commit,'available_physical_bytes':m.avail_phys,'total_commit_bytes':m.total_commit}

def require_headroom(gib=12):
    m=memory_status()
    assert m['available_commit_bytes']>=gib*1024**3,('MEMORY_HEADROOM_GUARD',m)
    return m
