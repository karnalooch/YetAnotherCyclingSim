"""Run the bounded R4.1 proof bundle inside one Unreal Editor process.

The sequence is repository-owned and fixed. No PR/comment input is interpreted as
Python, console commands, map paths, or arbitrary proof selection.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback

import unreal


SESSION_MODE_ENV = "YACS_R4_1_SESSION_MODE"
ARTIFACT_ROOT_ENV = "YACS_R4_1_SESSION_ARTIFACT_ROOT"
EXACT_HEAD_ENV = "YACS_R4_1_SESSION_EXACT_HEAD"

_SESSION_TICK = None
_STATE = "INIT"
_MODULES: dict[str, object] = {}
_STATUS = {
    "geometry_script_capability": "PENDING",
    "local_corridor_topology": "PENDING",
    "hairpin_corridor": "PENDING",
    "local_corridor_visual": "PENDING",
}


def _artifact_root() -> Path:
    value = os.environ.get(ARTIFACT_ROOT_ENV, "")
    if not value:
        raise RuntimeError(f"{ARTIFACT_ROOT_ENV} is required")
    root = Path(value)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _exact_head() -> str:
    value = os.environ.get(EXACT_HEAD_ENV, "").strip()
    if len(value) != 40:
        raise RuntimeError(f"{EXACT_HEAD_ENV} must contain a 40-character SHA")
    return value


def _session_id() -> str:
    return f"r4-1-{_exact_head()[:12]}"


def _summary_path() -> Path:
    return _artifact_root() / "proof_suite_summary.json"


def _load_module(name: str, relative_path: str):
    path = Path(__file__).resolve().parents[2] / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load proof module spec: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _read_pass(path: Path, field: str) -> dict[str, object]:
    if not path.is_file():
        raise RuntimeError(f"proof JSON is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get(field) != "PASS":
        raise RuntimeError(f"{path.name} did not report {field}=PASS")
    return payload


def _annotate(path: Path, field: str) -> None:
    payload = _read_pass(path, field)
    payload["exact_head"] = _exact_head()
    payload["r4_1_session_id"] = _session_id()
    payload["editor_pid"] = os.getpid()
    payload["editor_boot_count"] = 1
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_summary(result: str, error: str = "") -> None:
    payload = {
        "schema_version": 1,
        "r4_1_boot_once_proof_suite": result,
        "expected_head": _exact_head(),
        "r4_1_session_id": _session_id(),
        "editor_pid": os.getpid(),
        "editor_boot_count": 1,
        "proofs": dict(_STATUS),
        "error": error,
    }
    _summary_path().write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _finish(success: bool, error: str = "") -> None:
    global _SESSION_TICK
    if _SESSION_TICK is not None:
        unreal.unregister_slate_post_tick_callback(_SESSION_TICK)
        _SESSION_TICK = None
    _write_summary("PASS" if success else "FAIL", error)
    if success:
        unreal.log(
            "[YacsR41Session] PASS: "
            f"session={_session_id()} pid={os.getpid()} head={_exact_head()}"
        )
    else:
        unreal.log_error(f"[YacsR41Session] FAILURE: {error}")
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _start_local_visual() -> None:
    global _STATE
    root = _artifact_root() / "LocalCorridorVisual"
    root.mkdir(parents=True, exist_ok=True)
    os.environ["YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG"] = str(
        root / "sp638_local_corridor_rider_3840x2160.png"
    )
    os.environ["YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF"] = str(
        root / "local_corridor_visual_proof.json"
    )
    _STATUS["local_corridor_visual"] = "RUNNING"
    _STATE = "LOCAL_VISUAL"
    _MODULES["local_visual"].main()


def _tick(_delta_time: float) -> None:
    global _STATE
    try:
        if _STATE == "HAIRPIN":
            result = _MODULES["hairpin"].get_session_result()
            if result is None:
                return
            if not bool(result.get("success")):
                _STATUS["hairpin_corridor"] = "FAIL"
                _finish(False, str(result.get("error") or "hairpin proof failed"))
                return
            root = _artifact_root() / "HairpinCorridor"
            png = root / "passo_giau_sp638_hairpin_corridor_3840x2160.png"
            if not png.is_file() or png.stat().st_size < 100_000:
                _STATUS["hairpin_corridor"] = "FAIL"
                _finish(False, "hairpin proof PNG is missing or too small")
                return
            _annotate(root / "hairpin_capture_proof.json", "passo_giau_hairpin_corridor_capture")
            _STATUS["hairpin_corridor"] = "PASS"
            _start_local_visual()
            return

        if _STATE == "LOCAL_VISUAL":
            result = _MODULES["local_visual"].get_session_result()
            if result is None:
                return
            if not bool(result.get("success")):
                _STATUS["local_corridor_visual"] = "FAIL"
                _finish(False, str(result.get("error") or "local visual proof failed"))
                return
            root = _artifact_root() / "LocalCorridorVisual"
            png = root / "sp638_local_corridor_rider_3840x2160.png"
            if not png.is_file() or png.stat().st_size < 100_000:
                _STATUS["local_corridor_visual"] = "FAIL"
                _finish(False, "local visual proof PNG is missing or too small")
                return
            _annotate(root / "local_corridor_visual_proof.json", "sp638_local_corridor_visual")
            _STATUS["local_corridor_visual"] = "PASS"
            _STATE = "DONE"
            _finish(True)
    except Exception as exc:
        _finish(False, f"{type(exc).__name__}: {exc}")
        unreal.log_error(traceback.format_exc())


def main() -> None:
    global _SESSION_TICK, _STATE

    os.environ[SESSION_MODE_ENV] = "1"
    root = _artifact_root()
    _exact_head()
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)

    _MODULES["geometry"] = _load_module(
        "yacs_r41_geometry_probe",
        "scripts/ue/probe_geometry_script_api.py",
    )
    _MODULES["topology"] = _load_module(
        "yacs_r41_topology_probe",
        "scripts/ue/probe_sp638_local_corridor_topology.py",
    )
    _MODULES["hairpin"] = _load_module(
        "yacs_r41_hairpin_capture",
        "scripts/ue/stage3g_capture_passo_giau_hairpin_corridor.py",
    )
    _MODULES["local_visual"] = _load_module(
        "yacs_r41_local_visual_capture",
        "scripts/ue/stage3g_capture_sp638_local_corridor.py",
    )

    geometry_root = root / "GeometryScriptProbe"
    geometry_root.mkdir(parents=True, exist_ok=True)
    geometry_json = geometry_root / "geometry_script_probe.json"
    os.environ["YACS_GEOMETRY_SCRIPT_PROBE_JSON"] = str(geometry_json)
    _STATUS["geometry_script_capability"] = "RUNNING"
    _MODULES["geometry"].main()
    _annotate(geometry_json, "geometry_script_probe")
    _STATUS["geometry_script_capability"] = "PASS"

    topology_root = root / "LocalCorridorTopology"
    topology_root.mkdir(parents=True, exist_ok=True)
    topology_json = topology_root / "sp638_corridor_topology.json"
    os.environ["YACS_SP638_CORRIDOR_TOPOLOGY_JSON"] = str(topology_json)
    _STATUS["local_corridor_topology"] = "RUNNING"
    _MODULES["topology"].main()
    _annotate(topology_json, "sp638_local_corridor_topology")
    _STATUS["local_corridor_topology"] = "PASS"

    hairpin_root = root / "HairpinCorridor"
    hairpin_root.mkdir(parents=True, exist_ok=True)
    os.environ["YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PNG"] = str(
        hairpin_root / "passo_giau_sp638_hairpin_corridor_3840x2160.png"
    )
    os.environ["YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PROOF"] = str(
        hairpin_root / "hairpin_capture_proof.json"
    )
    _STATUS["hairpin_corridor"] = "RUNNING"
    _STATE = "HAIRPIN"
    _MODULES["hairpin"].main()

    _SESSION_TICK = unreal.register_slate_post_tick_callback(_tick)
    unreal.log(
        "[YacsR41Session] started: "
        f"session={_session_id()} pid={os.getpid()} head={_exact_head()}"
    )


try:
    main()
except Exception as exc:
    unreal.log_error(f"[YacsR41Session] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    try:
        _finish(False, f"{type(exc).__name__}: {exc}")
    except Exception:
        unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    raise
