"""Fixed trusted startup caller for the owned #384 accepted Editor session.

The host supplies only its pinned project/revision context. This script never
starts a server, registers a tool, loads/saves a map, or selects a domain body.
It binds the actual already-open checkpoint through the existing stager and
quits its Editor after the fixed native owner publishes a terminal receipt.
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "scripts/ue/bootstrap_official_mcp_bob_session.py"
CALLER = "scripts/ue/Invoke-YacsOfficialMcpBobSession.ps1"


def main() -> None:
    expected = os.environ.get("YACS_MCP_BOB_EXPECTED_HEAD", "")
    project = os.environ.get("YACS_MCP_BOB_PROJECT_ROOT", "")
    if (
        os.name != "nt"
        or re.fullmatch(r"[0-9a-f]{40}", expected) is None
        or project != str(ROOT)
    ):
        raise RuntimeError(
            "The fixed bootstrap lacks its owned exact-source project context"
        )
    for path in (
        ROOT,
        *ROOT.parents,
        Path(__file__),
        ROOT / "YetAnotherCyclingSim.uproject",
    ):
        info = path.lstat()
        if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RuntimeError("The fixed bootstrap refuses project/source aliases")
    sys.path.insert(0, str(ROOT))
    import unreal

    from scripts.ci import official_mcp_bob_session as session
    from scripts.ue import official_mcp_bob_operation as operation

    if (
        os.name != "nt"
        or operation.adapter.SHA40.fullmatch(expected) is None
        or project != str(ROOT)
        or session.ROOT.resolve() != ROOT.resolve()
        or operation.ROOT.resolve() != ROOT.resolve()
    ):
        raise RuntimeError(
            "The fixed bootstrap lacks its owned exact-source project context"
        )
    session._assert_isolated_root()
    sources = session._sources(expected)
    for relative in (SCRIPT, CALLER):
        if relative not in session.UTILITY_SOURCE_PATHS:
            raise RuntimeError(
                "The bootstrap/caller is absent from the pinned source inventory"
            )

    settings_class = unreal.load_class(
        None, "/Script/PythonScriptPlugin.PythonScriptPluginSettings"
    )
    if (
        settings_class is None
        or settings_class.get_path_name()
        != "/Script/PythonScriptPlugin.PythonScriptPluginSettings"
        or unreal.get_default_object(settings_class) is None
    ):
        raise RuntimeError("The fixed native Python settings class/CDO is unavailable")
    # This private property is not exposed to Python in the installed engine.
    # Early config adoption sets it false; the native owner independently reads
    # the actual bRemoteExecution FBoolProperty before starting its listener.
    context = session.prepare_native_session_context()
    if context.get("exact_sha") != expected:
        raise RuntimeError(
            "The actual native checkpoint context differs from the pinned revision"
        )

    # -ExecutePythonScript otherwise releases its command after main returns.
    # The existing tick/keepalive convention retains this exact owned caller.
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)

    started = time.monotonic()
    terminal = operation.SESSION_DIR + "/native-session.json"
    tick_handle = None

    def finish_tick(_delta_seconds: float) -> None:
        nonlocal tick_handle
        if time.monotonic() - started > 420:
            unreal.unregister_slate_post_tick_callback(tick_handle)
            unreal.SystemLibrary.quit_editor()
            return
        path = operation._safe_path(ROOT, terminal)
        if not path.exists():
            return
        if path.stat().st_size == 0:
            return
        # No declared native admission is inherited. The host independently
        # authenticates terminal/counter/transport/bundle evidence after exit.
        try:
            receipt = session._read_json(path)
        except (OSError, ValueError, RuntimeError):
            # The native exclusive file can be visible before its writer closes.
            # The host's shared deadline and final hash-bound parse remain final.
            return
        if (
            receipt.get("exact_sha") != expected
            or receipt.get("owned_editor_pid") != os.getpid()
            or receipt.get("status")
            not in {"NATIVE_BODY_COMPLETED", "NATIVE_SESSION_FAILED"}
        ):
            raise RuntimeError("The fixed native terminal receipt is invalid")
        if session._sources(expected) != sources:
            raise RuntimeError("The pinned bootstrap/session inputs changed")
        unreal.unregister_slate_post_tick_callback(tick_handle)
        unreal.SystemLibrary.quit_editor()

    tick_handle = unreal.register_slate_post_tick_callback(finish_tick)


if __name__ == "__main__":
    main()
