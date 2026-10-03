#!/usr/bin/env python3
"""Execute the complete isolated DVC lifecycle proof for issue #339."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import os
import shutil
import stat
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "raw" / "mallorca_mdt05.tif"
SOURCE_DVC = ROOT / "data" / "raw" / "mallorca_mdt05.tif.dvc"
PREPARED = ROOT / "data" / "prepared" / "mallorca_mdt05_129.f32"
REPORT = ROOT / "data" / "prepared" / "mallorca_mdt05_report.json"
EVIDENCE = ROOT / "evidence" / "latest-run.json"


def run_dvc(*args: str) -> str:
    command = [sys.executable, "-m", "dvc", *args]
    print("+", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    return completed.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_metadata() -> dict[str, Any]:
    return json.loads((ROOT / "source.json").read_text(encoding="utf-8"))


def verify_source() -> str:
    expected = source_metadata()["expected_sha256"]
    actual = sha256_file(SOURCE)
    if actual != expected:
        raise RuntimeError(
            f"source SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return actual


def prepared_hashes() -> dict[str, str]:
    return {
        "heightfield_sha256": sha256_file(PREPARED),
        "report_sha256": sha256_file(REPORT),
    }


def remove_exact(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise RuntimeError(f"refusing to remove path outside spike root: {resolved}")
    if resolved.is_dir():
        def remove_readonly(function: Any, blocked_path: str, _: Any) -> None:
            os.chmod(blocked_path, stat.S_IWRITE)
            function(blocked_path)

        shutil.rmtree(resolved, onexc=remove_readonly)
    elif resolved.exists():
        resolved.unlink()


def require_equal(label: str, expected: dict[str, str], actual: dict[str, str]) -> None:
    if expected != actual:
        raise RuntimeError(f"{label} hashes differ: {expected} != {actual}")


def main() -> int:
    if not SOURCE_DVC.is_file():
        raise RuntimeError(
            "missing source DVC descriptor; run the documented registration step"
        )

    # 1. Acquire from the declared official URL and put it in DVC's cache.
    run_dvc("update", str(SOURCE_DVC.relative_to(ROOT)))
    source_sha256 = verify_source()

    # 2. Store the source in the isolated proof remote.
    run_dvc("push", str(SOURCE_DVC.relative_to(ROOT)))

    # 3. Remove both the working copy and local cache, then hydrate from remote.
    cache_text = run_dvc("cache", "dir").strip().splitlines()[-1]
    cache_dir = Path(cache_text)
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir
    cache_dir = cache_dir.resolve()
    expected_cache = (ROOT / ".dvc" / "cache").resolve()
    if cache_dir != expected_cache:
        raise RuntimeError(
            f"unexpected DVC cache path {cache_dir}; expected {expected_cache}"
        )
    remove_exact(SOURCE)
    remove_exact(cache_dir)
    run_dvc("pull", str(SOURCE_DVC.relative_to(ROOT)))
    rehydrated_source_sha256 = verify_source()

    # 4. Prepare once, store derived outputs, then prove remote reuse.
    run_dvc("repro")
    baseline = prepared_hashes()
    report_payload = json.loads(REPORT.read_text(encoding="utf-8"))
    run_dvc("push")

    remove_exact(PREPARED)
    remove_exact(REPORT)
    remove_exact(cache_dir)
    run_dvc("pull")
    rehydrated_outputs = prepared_hashes()
    require_equal("rehydrated output", baseline, rehydrated_outputs)

    # 5. Force actual computation and require byte-identical results.
    run_dvc("repro", "--force")
    reproduced = prepared_hashes()
    require_equal("forced reproduction", baseline, reproduced)

    status = run_dvc("status")
    if "Data and pipelines are up to date." not in status:
        raise RuntimeError(f"unexpected DVC status: {status.strip()}")

    version = run_dvc("version").splitlines()[0]
    evidence = {
        "schema_version": 1,
        "result": "TECHNICAL_PASS",
        "dvc": version,
        "source_sha256": source_sha256,
        "rehydrated_source_sha256": rehydrated_source_sha256,
        "baseline": baseline,
        "rehydrated_outputs": rehydrated_outputs,
        "forced_reproduction": reproduced,
        "artifact_fingerprint_sha256": report_payload[
            "artifact_fingerprint_sha256"
        ],
        "scope": {
            "experimental_only": True,
            "production_code_changed": False,
            "unreal_content_changed": False,
        },
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Evidence: {EVIDENCE}")
    print("DVC Mallorca lifecycle spike: TECHNICAL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
