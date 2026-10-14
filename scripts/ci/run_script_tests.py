"""Discover all script tests, isolate modules and retain complete failure evidence.

No Unreal, source downloads or GPU jobs are launched by this hosted suite.
Scoped Draft plans are visibly non-full and the merge-ready gate runs every
discovered module. Processes run in parallel with separate receipts and logs.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
# This existing assertion-based entrypoint is not a unittest module.
STANDALONE = {"scripts/ci/test_final_architecture_contract.py"}
MIN_MODULES = 49
MAX_WORKERS = 4


def discover(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix() for p in (root / "scripts").rglob("test_*.py")
    )


def run_module(root: Path, relative: str) -> dict:
    path = (root / relative).resolve()
    if relative not in discover(root) or not path.is_relative_to(root.resolve()):
        raise ValueError("test module is outside the discovered suite")
    sys.path[:0] = [str(path.parent), str(root)]
    name = "yacs_test_" + relative.replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if relative in STANDALONE:
        code = module.main()
        return {
            "tests": 1,
            "skipped": 0,
            "passed": code == 0,
            "kind": "assertion_entrypoint",
        }
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(module)
    count = suite.countTestCases()
    if loader.errors or count == 0:
        raise ValueError(
            f"non-empty discovery required: {relative}: {count} tests, {loader.errors}"
        )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {
        "tests": result.testsRun,
        "skipped": len(result.skipped),
        "passed": result.wasSuccessful() and result.testsRun > len(result.skipped),
        "kind": "unittest",
    }


def validate_plan(root: Path, plan_path: Path) -> tuple[str, str, list[str], int]:
    """Never trust a scope file without exact SHA and full-inventory validation."""
    discovered = discover(root)
    if len(discovered) < MIN_MODULES:
        raise ValueError("Full script test discovery is truncated")
    if plan_path is None:
        return "FULL", "no plan specified", discovered, len(discovered)

    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    actual_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("Invalid script test plan schema")
    if plan.get("head") != actual_head:
        raise ValueError("Script test plan SHA does not match checkout")
    if plan.get("full_module_count") != len(discovered):
        raise ValueError("Script test plan inventory does not match discovery")

    mode = plan.get("mode")
    selected = plan.get("modules")
    if (
        mode not in {"FULL", "DRAFT_SCOPED"}
        or not isinstance(selected, list)
        or not selected
        or any(not isinstance(p, str) for p in selected)
        or selected != sorted(set(selected))
        or not set(selected).issubset(discovered)
    ):
        raise ValueError("Invalid, missing or duplicate script test plan modules")
    if mode == "FULL" and selected != discovered:
        raise ValueError("Full suite plan cannot omit discovered modules")
    if mode == "DRAFT_SCOPED" and not set(
        (
            "scripts/ci/test_agent_contracts.py",
            "scripts/ci/test_ci_aggregate_contract.py",
            "scripts/ci/test_final_architecture_contract.py",
            "scripts/ci/test_script_test_discovery.py",
        )
    ).issubset(selected):
        raise ValueError("Scoped Draft plan cannot omit mandatory guards")
    reason = plan.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ValueError("Script test plan reason is missing")
    return mode, reason, selected, len(discovered)


def run_isolated(relative: str, output: Path) -> dict:
    """Always execute a discovered module in its own subprocess and output dir."""
    folder = output / relative.removesuffix(".py")
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / "result.json"
    receipt.unlink(missing_ok=True)
    started = time.monotonic()
    code = 125
    error = None
    with (folder / "output.log").open("w", encoding="utf-8") as log:
        try:
            code = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--module",
                    relative,
                    "--output",
                    str(folder.resolve()),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            ).returncode
        except subprocess.TimeoutExpired:
            code, error = 124, "isolated module timed out after 120 seconds"
        except OSError as exc:
            error = f"cannot start isolated module: {type(exc).__name__}"

    try:
        result = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        result = {"tests": 0, "skipped": 0, "passed": False}
        error = error or f"test receipt unavailable: {type(exc).__name__}"

    if not isinstance(result, dict):
        result = {"tests": 0, "skipped": 0, "passed": False}
        error = "non-object test receipt"
    if error:
        result["error"] = error
    result.update(
        path=relative,
        exit_code=code,
        seconds=round(time.monotonic() - started, 3),
    )
    result["passed"] = (
        result.get("passed") is True
        and code == 0
        and type(result.get("tests")) is int
        and result["tests"] > 0
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/tmp/yacs-script-tests")
    parser.add_argument("--module", help=argparse.SUPPRESS)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.workers <= MAX_WORKERS:
        parser.error(f"--workers must be in 1..{MAX_WORKERS}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.module:
        try:
            result = run_module(ROOT, args.module)
        except Exception as exc:
            result = {
                "tests": 0,
                "skipped": 0,
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            print(result["error"], file=sys.stderr)
        (output / "result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        return 0 if result["passed"] else 1

    mode, reason, paths, total = validate_plan(ROOT, args.plan)
    print(
        f"Hosted script-test tier: {mode}, selected={len(paths)}/{total}, "
        f"workers={args.workers}, reason={reason}",
        flush=True,
    )
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_isolated, path, output): path for path in paths}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{'PASS' if result['passed'] else 'FAIL'} {result['path']}: "
                f"{result['tests']} tests ({result['seconds']} s)",
                flush=True,
            )
            if not result["passed"]:
                log = output / result["path"].removesuffix(".py") / "output.log"
                print(log.read_text(encoding="utf-8"), flush=True)

    results.sort(key=lambda r: r["path"])
    passed = all(r["passed"] for r in results)
    summary = {
        "schema_version": 2,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "mode": mode,
        "full_suite_passed": passed and mode == "FULL",
        "total_discovered_modules": total,
        "modules": len(results),
        "tests": sum(r["tests"] for r in results),
        "passed": passed,
        "reason": reason,
        "results": results,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(
                f"## Hosted script tests: {mode}\n\n"
                f"{summary['modules']}/{total} modules; "
                f"{summary['tests']} tests; passed={passed}; "
                f"**full_suite_passed={summary['full_suite_passed']}**.\n\n"
            )
            handle.write(f"Reason: {reason}.\n\n")
            handle.write("| Module | Result | Tests | Seconds |\n|---|---|---:|---:|\n")
            for result in results:
                handle.write(
                    f"| \x60{result['path']}\x60 | "
                    f"{'PASS' if result['passed'] else 'FAIL'} | "
                    f"{result['tests']} | {result['seconds']} |\n"
                )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
