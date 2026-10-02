"""Discover all script tests, isolate modules and retain complete failure evidence.

No Unreal, source downloads or GPU jobs are launched by this hosted suite.
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="/tmp/yacs-script-tests")
    parser.add_argument("--module", help=argparse.SUPPRESS)
    args = parser.parse_args()
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

    paths = discover(ROOT)
    if len(paths) < MIN_MODULES:
        raise SystemExit(
            f"test discovery regression: expected >= {MIN_MODULES} modules, found {len(paths)}"
        )
    results = []
    for relative in paths:
        folder = output / relative.removesuffix(".py")
        folder.mkdir(parents=True, exist_ok=True)
        receipt = folder / "result.json"
        receipt.unlink(missing_ok=True)
        started = time.monotonic()
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
                code = 124
        result = (
            json.loads(receipt.read_text(encoding="utf-8"))
            if receipt.exists()
            else {"tests": 0, "skipped": 0, "passed": False}
        )
        result.update(
            path=relative, exit_code=code, seconds=round(time.monotonic() - started, 3)
        )
        result["passed"] = result["passed"] is True and code == 0
        results.append(result)
        print(
            f"{'PASS' if result['passed'] else 'FAIL'} {relative}: {result['tests']} tests ({result['seconds']} s)",
            flush=True,
        )
        if not result["passed"]:
            print((folder / "output.log").read_text(encoding="utf-8"), flush=True)
    summary = {
        "schema_version": 1,
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "modules": len(results),
        "tests": sum(r["tests"] for r in results),
        "passed": all(r["passed"] for r in results),
        "results": results,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(
                f"## Hosted script tests\n\n{summary['modules']} modules; {summary['tests']} tests; passed={summary['passed']}.\n\n"
            )
            handle.write("| Module | Result | Tests | Seconds |\n|---|---|---:|---:|\n")
            for r in results:
                handle.write(
                    f"| `{r['path']}` | {'PASS' if r['passed'] else 'FAIL'} | {r['tests']} | {r['seconds']} |\n"
                )
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
