#!/usr/bin/env python3
"""Resolve explicit M3 proof intent before checking out or running target code.

Pushes are static-only. The trusted default-branch Gumball broker (or an
operator with workflow-dispatch permission) requests a full proof of one SHA.
This module admits work; it never treats a skipped proof as successful evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

REPOSITORY = "karnalooch/YetAnotherCyclingSim"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\Z")


@dataclass(frozen=True)
class ProofRequest:
    source_sha: str
    execute_proof: bool
    request_id: str
    reason: str


def resolve_request(environment: Mapping[str, str]) -> ProofRequest:
    """Validate platform context, not user-supplied shell expressions."""
    if environment.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise ValueError("M3 terrain proof is restricted to the canonical repository")
    event = environment.get("GITHUB_EVENT_NAME", "")
    if event not in {"push", "workflow_dispatch"}:
        raise ValueError(f"unsupported terrain proof event: {event!r}")
    workflow_sha = environment.get("GITHUB_SHA", "")
    if not SHA40.fullmatch(workflow_sha):
        raise ValueError(
            "workflow SHA must be exactly 40 lowercase hexadecimal characters"
        )
    if event == "push":
        return ProofRequest(workflow_sha, False, "", "push-static-only")
    source_sha = environment.get("YACS_REQUESTED_SHA", "")
    if not SHA40.fullmatch(source_sha):
        raise ValueError(
            "exact_sha must be exactly 40 lowercase hexadecimal characters"
        )
    request_id = environment.get("YACS_REQUEST_ID", "")
    if not REQUEST_ID.fullmatch(request_id):
        raise ValueError(
            "gumball_request_id must be a safe nonempty identifier (max 200 characters)"
        )
    return ProofRequest(source_sha, True, request_id, "explicit-exact-sha-request")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = resolve_request(os.environ)
    except ValueError as exc:
        parser.exit(2, f"terrain proof admission failed: {exc}\n")
    with args.github_output.open("a", encoding="utf-8") as handle:
        for key, value in asdict(request).items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            handle.write(f"{key}={rendered}\n")
    print(json.dumps(asdict(request), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
