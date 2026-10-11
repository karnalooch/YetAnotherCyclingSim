"""Reload a closed set of committed live-editor handlers without restarting UE.

The staged JSON selects an exact local descendant commit, never a script path.
Native instances and their rollback data remain owned by the stable bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import time
from types import ModuleType
import uuid

from scripts import committed_git_blobs as committed_git

FILES = {
    "scripts/ue/level_editor_surface_preview.py": ("surface", "SurfacePreview"),
    "scripts/ue/level_editor_shoulder_repair.py": ("shoulder_repair", "ShoulderRepair"),
}
STAGED = "Saved/LevelEditorStream/script-reload.json"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_SOURCE = 512 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _bridge():
    # Deferred to avoid a circular import during stable bridge installation.
    from scripts.ue import level_editor_material_bridge
    return level_editor_material_bridge


def _git(root, args, limit=4096):
    return committed_git._git_bounded(root, tuple(args), limit,
                                     deadline=time.monotonic() + 20)


def _sources(root, baseline, commit):
    require(type(commit) is str and SHA.fullmatch(commit), "Reload requires a full commit SHA")
    require(type(baseline) is str and SHA.fullmatch(baseline), "Reload baseline SHA is invalid")
    require(_git(root, ("rev-parse", "--verify", "HEAD")).decode().strip() == baseline,
            "Reload launcher HEAD changed")
    require(_git(root, ("rev-parse", "--verify", commit + "^{commit}")).decode().strip() == commit,
            "Reload candidate is not an exact commit")
    # Only locally available descendants of the launched code are eligible.
    ancestor = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", baseline, commit],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=20, check=False)
    require(ancestor.returncode == 0, "Reload candidate is not descended from the launched commit")
    changed = _git(root, ("diff", "--name-only", "-z", baseline, commit, "--", "scripts"),
                   limit=65536).decode("utf-8").split("\0")
    require(all(not path or path in FILES or Path(path).name.startswith("test_") for path in changed),
            "Reload candidate changes non-reloadable runtime scripts; launch a new baseline")
    return committed_git._read_exact_blobs(
        root, commit, tuple(FILES), blob_limit=MAX_SOURCE, total_limit=2 * MAX_SOURCE,
        timeout_seconds=20, path_validator=_bridge().safe_path)


def _hashes(blobs):
    return {path: hashlib.sha256(raw).hexdigest() for path, raw in blobs.items()}


def _candidate(path, raw, commit, instance):
    module = ModuleType("scripts.ue._live_" + Path(path).stem + "_" + commit)
    module.__package__ = "scripts.ue"
    module.__file__ = str(Path(__file__).resolve().parents[2] / path)
    exec(compile(raw, "git:" + commit + ":" + path, "exec"), module.__dict__)
    candidate = getattr(module, FILES[path][1], None)
    old = type(instance)
    require(isinstance(candidate, type) and candidate.__bases__ == old.__bases__ == (object,),
            "Reload handler class layout differs")
    require("__slots__" not in candidate.__dict__ and "__slots__" not in old.__dict__,
            "Reload does not support slotted handler state")
    for name, method in old.__dict__.items():
        if inspect.isfunction(method):
            replacement = candidate.__dict__.get(name)
            require(inspect.isfunction(replacement) and
                    str(inspect.signature(replacement)) == str(inspect.signature(method)),
                    "Reload handler method ABI differs: " + name)
    return candidate


def apply(manager):
    """Return revision metadata after an atomic class swap; never increment sequence."""
    bridge = _bridge()
    require(manager.pending is None, "Reload is blocked while another operation is pending")
    path = bridge.safe_path(manager.root, STAGED)
    identity = bridge.file_identity(path, 8192)
    raw = path.read_bytes()
    require(len(raw) == identity["size_bytes"] and hashlib.sha256(raw).hexdigest() == identity["sha256"],
            "Staged reload changed while being read")
    staged = bridge.strict_json(raw, 8192)
    require(set(staged) == {"schema_version", "session_id", "expected_sequence", "commit", "files"}
            and type(staged["schema_version"]) is int and staged["schema_version"] == 1,
            "Reload manifest schema differs")
    require(staged["session_id"] == manager.identity["session_id"] and
            type(staged["expected_sequence"]) is int and staged["expected_sequence"] == manager.sequence - 1,
            "Reload manifest belongs to another session or sequence")
    root = Path(manager.identity["launcher_root"])
    blobs = _sources(root, manager.identity["launcher_sha"], staged["commit"])
    require(staged["files"] == _hashes(blobs), "Reload committed source hashes differ")
    before = manager.observe()
    rows = [(getattr(manager, FILES[path][0]), path, raw) for path, raw in blobs.items()]
    replacements = [(instance, type(instance), _candidate(path, raw, staged["commit"], instance))
                    for instance, path, raw in rows]
    try:
        for instance, _old, candidate in replacements:
            instance.__class__ = candidate
        require(manager.observe() == before, "Reload changed native observations")
    except BaseException:
        for instance, old, _candidate_class in replacements:
            instance.__class__ = old
        require(manager.observe() == before, "Reload rollback could not recover observations")
        raise
    return {"commit": staged["commit"], "files": staged["files"],
            "previous_commit": getattr(manager, "script_revision", manager.identity["launcher_sha"])}


def stage(token, commit):
    """Stage against the authenticated baseline client, without invoking UE."""
    from scripts.ue import level_editor_material_client as client
    from scripts.ue import prepare_level_editor_review as preparation
    require(type(token) is str and client.SESSION_ID.fullmatch(token), "Invalid session token")
    root = preparation.REVIEW_ROOT / (preparation.RUNTIME_SHA[:12] + "-" + token)
    context = client._load_context(root / client.SESSION_RECEIPT)
    history = client._history(context)
    launcher = context["identity"]
    blobs = _sources(Path(launcher["launcher_root"]), launcher["launcher_sha"], commit)
    value = {"schema_version": 1, "session_id": token, "expected_sequence": history["sequence"],
             "commit": commit, "files": _hashes(blobs)}
    bridge = _bridge()
    path = bridge.safe_path(root, STAGED)
    temporary = bridge.safe_path(root, STAGED + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(bridge.canonical(value).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        bridge.safe_path(root, STAGED)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-token", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.session_token, args.commit), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
