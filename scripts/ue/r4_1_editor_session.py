"""Run the bounded Stage 3G R4.1 proof bundle in one Unreal Editor process.

The PowerShell proof-suite wrapper owns exact-SHA checkout, targeted LFS
materialization and the single editor build. This script owns only the in-editor
sequence. Every stage is a fixed repository-owned script; no user supplied
Python, asset path or console command is accepted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import time
import traceback

import unreal


REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_ROOT_ENV = "YACS_R4_1_SESSION_ARTIFACT_ROOT"
EXPECTED_HEAD_ENV = "YACS_R4_1_SESSION_EXPECTED_HEAD"
SESSION_MANAGED_ENV = "YACS_R4_1_EDITOR_SESSION_MANAGED"
SESSION_SUMMARY_NAME = "editor_session_summary.json"
ASYNC_STAGE_TIMEOUT_S = 180.0

_tick_handle = None
_stage_index = 0
_current_stage: dict[str, object] | None = None
_current_deadline = 0.0
_session_root: Path | None = None
_expected_head = ""
_stage_results: dict[str, dict[str, object]] = {}


def _stage(
    name: str,
    script_relative: str,
    proof_relative: str,
    pass_key: str,
    *,
    environment: dict[str, str],
    asynchronous: bool,
) -> dict[str, object]:
    return {
        "name": name,
        "script": REPO_ROOT / script_relative,
        "proof": proof_relative,
        "pass_key": pass_key,
        "environment": environment,
        "asynchronous": asynchronous,
    }


STAGES = (
    _stage(
        "geometry_script_capability",
        "scripts/ue/probe_geometry_script_api.py",
        "GeometryScriptProbe/geometry_script_probe.json",
        "geometry_script_probe",
        environment={
            "YACS_GEOMETRY_SCRIPT_PROBE_JSON": "GeometryScriptProbe/geometry_script_probe.json",
        },
        asynchronous=False,
    ),
    _stage(
        "local_corridor_topology",
        "scripts/ue/probe_sp638_local_corridor_topology.py",
        "LocalCorridorTopology/sp638_corridor_topology.json",
        "sp638_local_corridor_topology",
        environment={
            "YACS_SP638_CORRIDOR_TOPOLOGY_JSON": "LocalCorridorTopology/sp638_corridor_topology.json",
        },
        asynchronous=False,
    ),
    _stage(
        "hairpin_corridor",
        "scripts/ue/stage3g_capture_passo_giau_hairpin_corridor.py",
        "HairpinCorridor/hairpin_capture_proof.json",
        "passo_giau_hairpin_corridor_capture",
        environment={
            "YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PNG": "HairpinCorridor/passo_giau_sp638_hairpin_corridor_3840x2160.png",
            "YACS_PASSO_GIAU_HAIRPIN_CAPTURE_PROOF": "HairpinCorridor/hairpin_capture_proof.json",
        },
        asynchronous=True,
    ),
    _stage(
        "local_corridor_visual",
        "scripts/ue/stage3g_capture_sp638_local_corridor.py",
        "LocalCorridorVisual/local_corridor_visual_proof.json",
        "sp638_local_corridor_visual",
        environment={
            "YACS_SP638_LOCAL_CORRIDOR_VISUAL_PNG": "LocalCorridorVisual/sp638_local_corridor_rider_3840x2160.png",
            "YACS_SP638_LOCAL_CORRIDOR_VISUAL_PROOF": "LocalCorridorVisual/local_corridor_visual_proof.json",
        },
        asynchronous=True,
    ),
)


def _require_environment() -> tuple[Path, str]:
    root_value = os.environ.get(SESSION_ROOT_ENV, "").strip()
    expected_head = os.environ.get(EXPECTED_HEAD_ENV, "").strip()
    if not root_value:
        raise RuntimeError(f"{SESSION_ROOT_ENV} is required")
    if len(expected_head) != 40 or any(ch not in "0123456789abcdef" for ch in expected_head):
        raise RuntimeError(f"{EXPECTED_HEAD_ENV} must be a lowercase 40-character SHA")

    root = Path(root_value).resolve()
    root.mkdir(parents=True, exist_ok=True)
    actual_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    if actual_head != expected_head:
        raise RuntimeError(
            f"R4.1 editor session HEAD {actual_head!r} != expected {expected_head!r}"
        )
    return root, expected_head


def _summary_path() -> Path:
    if _session_root is None:
        raise RuntimeError("session root is not initialized")
    return _session_root / SESSION_SUMMARY_NAME


def _write_summary(status: str, *, error: str = "", traceback_text: str = "") -> None:
    if _session_root is None:
        return
    payload = {
        "schema_version": 1,
        "r4_1_editor_session": status,
        "expected_head": _expected_head,
        "actual_head": _expected_head,
        "editor_process_id": os.getpid(),
        "editor_process_count": 1,
        "single_editor_process": True,
        "session_managed_visual_proofs": True,
        "stages": _stage_results,
        "error": error,
        "traceback": traceback_text,
    }
    _summary_path().write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _annotate_and_validate(stage: dict[str, object]) -> None:
    if _session_root is None:
        raise RuntimeError("session root is not initialized")
    proof_path = _session_root / str(stage["proof"])
    if not proof_path.is_file():
        raise RuntimeError(f"{stage['name']} proof is missing: {proof_path}")

    payload = json.loads(proof_path.read_text(encoding="utf-8"))
    pass_key = str(stage["pass_key"])
    if payload.get(pass_key) != "PASS":
        raise RuntimeError(
            f"{stage['name']} proof did not report PASS in {pass_key!r}"
        )

    payload["r4_1_editor_session"] = {
        "exact_head": _expected_head,
        "editor_process_id": os.getpid(),
        "single_editor_process": True,
        "stage": str(stage["name"]),
    }
    proof_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _stage_results[str(stage["name"])] = {
        "status": "PASS",
        "proof": str(proof_path),
        "exact_head": _expected_head,
    }
    unreal.log(
        f"[YacsR41EditorSession] PASS {stage['name']}: {proof_path}"
    )


def _set_stage_environment(stage: dict[str, object]) -> list[str]:
    if _session_root is None:
        raise RuntimeError("session root is not initialized")
    names: list[str] = []
    environment = dict(stage["environment"])
    for name, relative in environment.items():
        path = _session_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
        names.append(name)
    return names


def _run_stage_script(stage: dict[str, object]) -> None:
    script_path = Path(stage["script"])
    if not script_path.is_file():
        raise RuntimeError(f"R4.1 session script is missing: {script_path}")
    env_names = _set_stage_environment(stage)
    try:
        unreal.log(
            f"[YacsR41EditorSession] START {stage['name']}: {script_path}"
        )
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        for name in env_names:
            os.environ.pop(name, None)


def _finish_success() -> None:
    global _tick_handle
    _write_summary("PASS")
    unreal.log(
        "[YacsR41EditorSession] PASS: all R4.1 proofs completed in one editor process"
    )
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None
    os.environ.pop(SESSION_MANAGED_ENV, None)
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _finish_failure(exc: BaseException) -> None:
    global _tick_handle
    text = traceback.format_exc()
    _write_summary("FAIL", error=str(exc), traceback_text=text)
    unreal.log_error(f"[YacsR41EditorSession] FAILURE: {exc}")
    unreal.log_error(text)
    if _tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(_tick_handle)
        _tick_handle = None
    os.environ.pop(SESSION_MANAGED_ENV, None)
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)


def _advance() -> None:
    global _stage_index, _current_stage, _current_deadline

    while _stage_index < len(STAGES):
        stage = STAGES[_stage_index]
        _current_stage = stage
        _run_stage_script(stage)

        if bool(stage["asynchronous"]):
            _current_deadline = time.monotonic() + ASYNC_STAGE_TIMEOUT_S
            return

        _annotate_and_validate(stage)
        _stage_index += 1

    _finish_success()


def _tick(_delta_time: float) -> None:
    global _stage_index, _current_stage
    if _current_stage is None or not bool(_current_stage["asynchronous"]):
        return
    try:
        if _session_root is None:
            raise RuntimeError("session root is not initialized")
        proof_path = _session_root / str(_current_stage["proof"])
        if proof_path.is_file():
            _annotate_and_validate(_current_stage)
            _stage_index += 1
            _current_stage = None
            _advance()
            return
        if time.monotonic() > _current_deadline:
            raise TimeoutError(
                f"{_current_stage['name']} did not produce proof within "
                f"{ASYNC_STAGE_TIMEOUT_S:.0f}s"
            )
    except BaseException as exc:
        _finish_failure(exc)


def main() -> None:
    global _tick_handle, _session_root, _expected_head
    _session_root, _expected_head = _require_environment()
    os.environ[SESSION_MANAGED_ENV] = "1"
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    _tick_handle = unreal.register_slate_post_tick_callback(_tick)
    _write_summary("RUNNING")
    try:
        _advance()
    except BaseException as exc:
        _finish_failure(exc)


main()
