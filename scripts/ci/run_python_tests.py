"""Run the deterministic reference-model suite and fail if discovery becomes a no-op."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PHYSICS_ROOT = ROOT / "physics_reference"
SRC = PHYSICS_ROOT / "src"
TESTS = PHYSICS_ROOT / "tests"

MIN_EXPECTED_TESTS = 80


def main() -> int:
    sys.path.insert(0, str(SRC))

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(TESTS),
        pattern="test_*.py",
        top_level_dir=str(PHYSICS_ROOT),
    )
    count = suite.countTestCases()

    if count < MIN_EXPECTED_TESTS:
        print(
            f"test discovery: FAIL — expected at least {MIN_EXPECTED_TESTS}, found {count}",
            file=sys.stderr,
        )
        return 1

    print(f"test discovery: {count} tests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
