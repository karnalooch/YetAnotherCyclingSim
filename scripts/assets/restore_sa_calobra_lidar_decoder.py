"""Restore the two already approved LAZ wheels in a new canonical project venv.

This is the explicit recovery for the missing environment observed in run
38108177248, not an installer for arbitrary packages or Python versions. It
never modifies the existing base interpreter or a pre-existing project venv.
The following read-only LiDAR command still authenticates every source input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets import read_sa_calobra_hairpin_lidar as reader

BASE_IDENTITY = {
    "size_bytes": 104952,
    "sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
}
WHEELS = {
    "laspy": {
        "version": "2.7.0", "file": "laspy-2.7.0-py3-none-any.whl",
        "sha256": "15f5344c62a1023461996bdf5d1ba5fdd813e96694a524fee712931134f3792f",
        "url": "https://files.pythonhosted.org/packages/ed/fb/ae27ebca327117e35cc717a3a87afdcbbf10d5aac52e405d16ebe777357e/laspy-2.7.0-py3-none-any.whl",
    },
    "lazrs": {
        "version": "0.8.2", "file": "lazrs-0.8.2-cp312-cp312-win_amd64.whl",
        "sha256": "213803fbaaf734d5ff3c886bb4a2d173ea24a31383c3cda5383b9bc16e8f0635",
        "url": "https://files.pythonhosted.org/packages/51/5d/03adf33c24c9c0bceeb234c44bcaa665aa72fc9ce8f5b64ac8b7c19d4378/lazrs-0.8.2-cp312-cp312-win_amd64.whl",
    },
}
STOP_TIMEOUT_SECONDS = 10


def recovery_base(environment, workspace):
    """Require the actual failed probe and its unchanged known base executable."""
    reader.require(
        environment.get("status") == "GIS_ENVIRONMENT_UNAVAILABLE"
        and environment.get("selected") is None
        and environment.get("read_only") is True
        and environment.get("installation_performed") is False
        and environment.get("source_read") is False
        and environment.get("configured_project") == workspace["project"],
        "Recovery requires the current failed read-only environment probe",
    )
    candidates = [r for r in environment["candidates"]
                  if r.get("origin") == "registered_path_python"]
    reader.require(len(candidates) == 1, "Observed registered base is not unique")
    row, = candidates
    probe, base = row.get("probe", {}), Path(row["path"])
    reader.require(
        row.get("exit_code") == 2
        and probe.get("python_version") == [3, 12, 10]
        and probe.get("implementation") == "cpython"
        and probe.get("pointer_bits") == 64
        and probe.get("prefix") == probe.get("base_prefix")
        and probe.get("decoder_versions") == {
            "laspy": None, "lazrs": None, "numpy": "2.3.5", "pyproj": "3.8.0"
        }
        and probe.get("executable_identity") == BASE_IDENTITY
        and base.is_absolute() and base.is_file()
        and Path(probe["executable"]).samefile(base)
        and base.stat().st_size == BASE_IDENTITY["size_bytes"]
        and reader.digest(base) == BASE_IDENTITY["sha256"],
        "Recovery base differs from the observed CPython/GIS environment",
    )
    return base


def verify_wheel(path, expected):
    reader.require(
        path.is_file() and not path.is_symlink() and path.name == expected["file"]
        and 0 < path.stat().st_size <= 2 * 1024 * 1024
        and reader.digest(path) == expected["sha256"],
        "Downloaded approved wheel differs: " + expected["file"],
    )
    return {"file": path.name, "size_bytes": path.stat().st_size,
            "sha256": reader.digest(path), "url": expected["url"]}


def run_owned(argv, label, proof, report, timeout):
    """Record each child; timeout cleanup addresses only its own Windows tree."""
    row = {"operation": label, "owned_pid": None, "exit_code": None,
           "exit_code_observed": False, "timeout_seconds": timeout, "timed_out": False,
           "error": None, "cleanup_errors": [], "owned_tree_cleanup_pid": None,
           "owned_tree_cleanup_exit": None, "owned_tree_cleanup_timed_out": False,
           "owned_tree_cleanup_succeeded": False,
           "taskkill_fallback_kill_attempted": False, "child_fallback_kill_attempted": False}
    report["processes"].append(row)
    log = proof / (label + ".log")
    child = cleanup = None
    log_created = False

    def stop_owned(process, kind):
        if process is not None and process.poll() is None:
            row[kind + "_fallback_kill_attempted"] = True
            try:
                process.kill()
                process.wait(timeout=STOP_TIMEOUT_SECONDS)
            except Exception as exc:  # noqa: BLE001 - retain a failed owned stop too
                row["cleanup_errors"].append(kind + ": " + type(exc).__name__ + ": " + str(exc))

    try:
        with log.open("xb") as stream:
            log_created = True
            try:
                child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT)
                row["owned_pid"] = child.pid
                child.wait(timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - always close/observe this child
                row["timed_out"] = isinstance(exc, subprocess.TimeoutExpired)
                row["error"] = type(exc).__name__ + ": " + str(exc)
            finally:
                if child is not None and child.poll() is None:
                    try:
                        # Avoid subprocess.run's implicit unbounded reap after
                        # its own timeout. This helper is also explicitly owned.
                        cleanup = subprocess.Popen(
                            ["taskkill.exe", "/PID", str(child.pid), "/T", "/F"],
                            stdout=stream, stderr=subprocess.STDOUT,
                        )
                        row["owned_tree_cleanup_pid"] = cleanup.pid
                        cleanup.wait(timeout=STOP_TIMEOUT_SECONDS)
                    except Exception as exc:  # noqa: BLE001
                        row["owned_tree_cleanup_timed_out"] = isinstance(exc, subprocess.TimeoutExpired)
                        row["cleanup_errors"].append("taskkill: " + type(exc).__name__ + ": " + str(exc))
                    finally:
                        stop_owned(cleanup, "taskkill")
                        if cleanup is not None:
                            row["owned_tree_cleanup_exit"] = cleanup.poll()
                        row["owned_tree_cleanup_succeeded"] = (
                            row["owned_tree_cleanup_exit"] == 0 and not row["owned_tree_cleanup_timed_out"])
                        # A failed taskkill must not leave the direct child
                        # running. This fallback does not certify its whole tree.
                        stop_owned(child, "child")
                if child is not None:
                    row["exit_code"] = child.poll()
                    row["exit_code_observed"] = row["exit_code"] is not None
    finally:
        if log_created:
            raw = log.read_bytes()
            row["log"] = {
                "file": log.name, "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "final": (child is None or child.poll() is not None)
                         and (cleanup is None or cleanup.poll() is not None),
            }
    reader.require(not row["timed_out"] and row["error"] is None
                   and not row["cleanup_errors"] and row["exit_code"] == 0,
                   "Owned decoder recovery step failed: " + label + "; "
                   + (row["error"] or "exit_code=" + str(row["exit_code"]))
                   + "; cleanup=" + repr(row["cleanup_errors"]))


def restore(workspace, environment, proof):
    target = Path(workspace["project"]) / ".venv"
    report = {
        "schema_version": 1, "status": "FAILED", "source_mutated": False,
        "base_interpreter_unchanged_verified": False, "target": str(target),
        "created_new_environment": False, "wheels": [], "processes": [],
        "selected": None, "error": None,
    }
    result_path = proof / "decoder-restoration.json"
    reader.require(not result_path.exists(), "Recovery evidence already exists")
    try:
        reader.require(sys.platform == "win32", "Recovery is the observed Windows ABI only")
        base = recovery_base(environment, workspace)
        report["base_interpreter"] = {"path": str(base), **BASE_IDENTITY}
        reader.require(not target.exists() and not target.is_symlink(),
                       "Existing project venv is preserved; recovery requires a new directory")
        pins = (ROOT / "scripts/assets/requirements-sa-calobra-lidar.txt").read_text()
        reader.require(
            {line.strip() for line in pins.splitlines()
             if line.strip() and not line.lstrip().startswith("#")}
            == {name + "==" + row["version"] for name, row in WHEELS.items()},
            "Approved LAZ dependency versions differ",
        )
        wheels = proof / "approved-wheels"
        wheels.mkdir(exist_ok=False)
        for row in WHEELS.values():
            path = wheels / row["file"]
            with urllib.request.urlopen(row["url"], timeout=30) as response:
                final = urllib.parse.urlsplit(response.geturl())
                reader.require(final.scheme == "https" and final.hostname == "files.pythonhosted.org",
                               "Approved wheel download changed origin")
                raw = response.read(2 * 1024 * 1024 + 1)
            reader.require(len(raw) <= 2 * 1024 * 1024, "Approved wheel exceeds its bound")
            with path.open("xb") as stream:
                stream.write(raw)
            report["wheels"].append(verify_wheel(path, row))
        requirements = proof / "decoder-pinned-requirements.txt"
        with requirements.open("x", encoding="utf-8") as stream:
            stream.write("".join(name + "==" + row["version"] + " --hash=sha256:"
                                 + row["sha256"] + "\n" for name, row in WHEELS.items()))
        # --copies avoids the unavailable Windows symlink privilege. Never use
        # --clear/--upgrade, install in base Python, or alter existing GIS pins.
        target.mkdir(exist_ok=False)
        report["created_new_environment"] = True
        run_owned([str(base), "-I", "-B", "-m", "venv", "--copies",
                   "--system-site-packages", str(target)], "create-venv", proof, report, 60)
        python = target / "Scripts/python.exe"
        run_owned([str(python), "-I", "-B", "-m", "pip", "--isolated",
                   "--disable-pip-version-check", "--no-input", "install", "--no-index",
                   "--no-deps", "--no-cache-dir", "--only-binary=:all:", "--require-hashes",
                   "--find-links", str(wheels), "--report", str(proof / "pip-report.json"),
                   "-r", str(requirements)], "install-approved-wheels", proof, report, 60)
        selected = reader.resolve_existing_decoder(workspace)
        report["fresh_environment_probe"] = selected
        reader.require(selected["selected"] is not None
                       and Path(selected["selected"]["path"]).samefile(python),
                       "Restored project venv did not qualify through actual imports")
        reader.require(reader.digest(base) == BASE_IDENTITY["sha256"],
                       "Base interpreter bytes changed during recovery")
        report.update(status="APPROVED_LAZ_ENVIRONMENT_RESTORED",
                      base_interpreter_unchanged_verified=True,
                      selected=selected["selected"])
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", type=Path, required=True)
    parser.add_argument("--environment-report", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    raw = args.environment_report.read_bytes()
    reader.require(len(raw) <= 65536, "Environment evidence exceeds its bound")
    result = restore(reader.load_workspace(args.workspace_config),
                     json.loads(raw.decode("utf-8-sig")), args.evidence_root)
    print(json.dumps({"status": result["status"], "selected": result["selected"]}))
    return 0 if result["status"] == "APPROVED_LAZ_ENVIRONMENT_RESTORED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
