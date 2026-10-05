"""Manual resumable native stages with Windows commit-memory admission."""

import ctypes


def available_memory():
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("free_physical", ctypes.c_ulonglong),
            ("total_commit", ctypes.c_ulonglong),
            ("free_commit", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("free_virtual", ctypes.c_ulonglong),
            ("extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise RuntimeError("Cannot verify Windows memory headroom")
    return {"free_physical": status.free_physical, "free_commit": status.free_commit}


class Waves:
    """Each explicit invocation advances one stage; never auto-retry."""

    def __init__(self, iterator, memory=available_memory):
        self.iterator = iterator
        self.memory = memory
        self.running = False
        self.status = "READY"
        self.completed = []
        self.result = None

    def advance(self):
        if self.running:
            raise RuntimeError("Native stage still running; refuse re-entry")
        if self.status in ("COMPLETE", "FAILED"):
            raise RuntimeError("Finished sequence; no implicit duplicate run")
        self.running = True
        try:
            memory = self.memory()
            # Operational guard, not a guarantee or performance acceptance.
            if (
                memory["free_physical"] < 8 * 1024**3
                or memory["free_commit"] < 12 * 1024**3
            ):
                self.status = "PAUSED_LOW_MEMORY"
                return {"phase": self.status, "memory": memory}
            self.status = "RUNNING"
            try:
                stage = next(self.iterator)
            except StopIteration as completed:
                self.result = completed.value
                self.status = "COMPLETE"
                return {"phase": self.status, "result": self.result}
            self.completed.append(stage)
            self.status = "AWAITING_NEXT_INVOCATION"
            return {**stage, "memory_before": memory, "automatic_continuation": False}
        except Exception:
            self.status = "FAILED"
            raise
        finally:
            self.running = False
