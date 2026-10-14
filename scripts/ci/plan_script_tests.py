"""Plan an exact-head, fail-closed Python test tier for hosted YACS CI.

Only a one-commit, same-repository Draft PR synchronization may select a
scoped suite. Every other event, ambiguous history or CI/platform change runs
the complete dynamically discovered suite. A scoped PASS is NEVER a full PASS.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

# The planner works both as a directly invoked script and an imported module.
if __package__:
    from .run_script_tests import MIN_MODULES, discover
else:
    from run_script_tests import MIN_MODULES, discover

ROOT = Path(__file__).resolve().parents[2]

# Conservative integration boundaries. Any unmapped source path triggers FULL.
DOMAIN_TESTS = {
    "assets": ("assets", "worldgen", "ue"),
    "blender": ("blender", "assets"),
    "geometry": ("geometry", "worldgen", "ue"),
    "live_host": ("live_host", "ue", "worldgen"),
    "runner": ("runner", "ci"),
    "ue": ("ue", "worldgen"),
    "worldgen": ("worldgen", "ue"),
}

# Always validate CI/test discovery and architectural safeguards even in Draft.
SCOPED_GUARDS = (
    "scripts/ci/test_agent_contracts.py",
    "scripts/ci/test_ci_aggregate_contract.py",
    "scripts/ci/test_final_architecture_contract.py",
    "scripts/ci/test_script_test_discovery.py",
)

MAX_CHANGED_PATHS = 32


def decide_scope(
    changed_paths: list[str] | None, discovered: list[str]
) -> tuple[str, str, list[str]]:
    """Select conservative integration domains, or FULL if anything is unknown."""
    full = sorted(discovered)
    if not changed_paths:
        return "FULL", "no trustworthy incremental change set", full
    if len(changed_paths) > MAX_CHANGED_PATHS:
        return "FULL", "large multi-file change set", full

    selected_domains: set[str] = set()
    for path in changed_paths:
        if path == "README.md" or path.startswith("docs/"):
            continue
        parts = path.split("/")
        if (
            len(parts) >= 3
            and parts[0] == "scripts"
            and parts[1] in DOMAIN_TESTS
            and path.endswith(".py")
        ):
            selected_domains.update(DOMAIN_TESTS[parts[1]])
            continue
        return "FULL", f"unmapped or security-sensitive path: {path}", full

    guard_paths = set(SCOPED_GUARDS)
    if not guard_paths.issubset(full):
        return "FULL", "mandatory guard test absent from discovery", full

    if selected_domains:
        selected = sorted(
            set(SCOPED_GUARDS)
            | {
                path
                for path in full
                if any(
                    path.startswith(f"scripts/{domain}/") for domain in selected_domains
                )
            }
        )
        if len(selected) == len(full):
            return "FULL", "scoped domain covers entire suite", full
        return (
            "DRAFT_SCOPED",
            "single-commit Draft change in verified integration domains",
            selected,
        )

    return (
        "DRAFT_SCOPED",
        "single-commit Draft documentation-only change",
        sorted(guard_paths),
    )


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=root, text=True, stderr=subprocess.DEVNULL
    ).strip()


def build_plan(root: Path, *, draft_incremental: bool, previous_sha: str) -> dict:
    root = Path(root)
    all_tests = discover(root)
    if len(all_tests) < MIN_MODULES:
        raise ValueError(
            f"Test inventory truncated: {len(all_tests)} modules (expected >= {MIN_MODULES})"
        )

    head = _git(root, "rev-parse", "HEAD")
    mode, reason, modules = "FULL", "non-incremental or required full event", all_tests
    changed: list[str] = []

    if draft_incremental:
        if re.fullmatch(r"[a-f0-9]{40}", previous_sha) is None:
            reason = "missing or malformed GitHub PR synchronize before-SHA"
        else:
            try:
                parent = _git(root, "rev-parse", "HEAD^")
                # Exact single-commit synchronization only. Multiple commits,
                # merges, rebases and shallow-history uncertainty run FULL.
                if parent != previous_sha or head == previous_sha:
                    reason = (
                        "PR synchronization was not one verifiable fast-forward commit"
                    )
                else:
                    raw = subprocess.check_output(
                        [
                            "git",
                            "diff",
                            "--no-renames",
                            "--name-only",
                            "-z",
                            "--diff-filter=ACMRTD",
                            previous_sha,
                            head,
                        ],
                        cwd=root,
                        stderr=subprocess.DEVNULL,
                    )
                    changed = [
                        name.decode("utf-8", errors="strict")
                        for name in raw.split(b"\0")
                        if name
                    ]
                    mode, reason, modules = decide_scope(changed, all_tests)
            except (OSError, subprocess.CalledProcessError, UnicodeError):
                reason = "commit parent or Git diff could not be verified"

    return {
        "schema_version": 1,
        "head": head,
        "previous_sha": previous_sha if draft_incremental else None,
        "mode": mode,
        "reason": reason,
        "changed_paths": changed,
        "full_module_count": len(all_tests),
        "modules": modules,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-incremental", choices=("true", "false"), required=True)
    parser.add_argument("--previous-sha", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = build_plan(
        ROOT,
        draft_incremental=args.draft_incremental == "true",
        previous_sha=args.previous_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(
        f"PCG/YACS TEST PLAN {plan['mode']}: "
        f"{len(plan['modules'])}/{plan['full_module_count']} modules; "
        f"{plan['reason']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
