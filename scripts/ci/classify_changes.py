#!/usr/bin/env python3
"""Classify YACS changes into CI lanes.

This is the single source of truth for path-based CI routing. The classifier
stays deliberately conservative: known runtime/tooling paths opt into the
relevant expensive lanes, docs-only and asset-only changes stay lightweight,
and unknown paths are surfaced explicitly instead of being silently ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Iterable

ASSET_EXTENSIONS = {
    ".uasset",
    ".umap",
    ".fbx",
    ".blend",
    ".wav",
    ".flac",
    ".mp3",
    ".exr",
    ".hdr",
    ".tga",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

DOC_EXTENSIONS = {".md", ".rst", ".adoc"}

PYTHON_EXACT = {
    "pyproject.toml",
    "pytest.ini",
}

CI_EXACT = {
    ".gitattributes",
    ".gitignore",
    "CODEOWNERS",
}

UE_CRITICAL_CONFIG = {
    "Config/DefaultEngine.ini",
    "Config/DefaultGame.ini",
    "Config/DefaultInput.ini",
    "Config/DefaultEditor.ini",
}


@dataclass(frozen=True)
class Classification:
    docs: bool = False
    python: bool = False
    cpp: bool = False
    assets: bool = False
    ci: bool = False
    ue_code: bool = False
    unknown: bool = False
    docs_only: bool = False
    asset_only: bool = False

    @property
    def security_base(self) -> bool:
        return self.python or self.cpp or self.ci or self.ue_code or self.unknown


def _is_docs(path: str) -> bool:
    pure = PurePosixPath(path)
    if path.startswith("docs/"):
        return True
    if pure.suffix.lower() in DOC_EXTENSIONS:
        return True
    return pure.name.lower() in {"readme", "license", "license.txt", "notice"}


def _is_python(path: str) -> bool:
    pure = PurePosixPath(path)
    name = pure.name.lower()
    if pure.suffix.lower() == ".py":
        return True
    if path.startswith("physics_reference/"):
        return True
    if path in PYTHON_EXACT:
        return True
    if name.startswith("requirements") and pure.suffix.lower() in {".txt", ".in"}:
        return True
    return False


def _is_cpp(path: str) -> bool:
    pure = PurePosixPath(path)
    if not path.startswith("Source/"):
        return False
    return pure.suffix.lower() in {".cpp", ".c", ".h", ".hpp", ".inl", ".cs"}


def _is_asset(path: str) -> bool:
    pure = PurePosixPath(path)
    if path.startswith("Content/") or path.startswith("SourceArt/"):
        return True
    return pure.suffix.lower() in ASSET_EXTENSIONS


def _is_ci(path: str) -> bool:
    if path.startswith(".github/") or path.startswith(".circleci/"):
        return True
    if path.startswith("scripts/ci/") or path.startswith("scripts/ue/"):
        return True
    if path in CI_EXACT:
        return True
    return False


def _is_ue_code(path: str) -> bool:
    pure = PurePosixPath(path)
    if _is_cpp(path):
        return True
    if pure.suffix.lower() in {".uproject", ".uplugin"}:
        return True
    if path in UE_CRITICAL_CONFIG or path.startswith("Config/"):
        return True
    if path.startswith("scripts/ue/"):
        return True
    if path in {
        "scripts/ci/Invoke-YacsUnrealCi.ps1",
        "scripts/ci/Test-YacsCodeOnlyCheckout.ps1",
        ".github/workflows/reusable-unreal.yml",
        ".github/workflows/manual-unreal.yml",
        ".circleci/config.yml",
    }:
        return True
    return False


def classify_paths(paths: Iterable[str]) -> Classification:
    normalized = sorted(
        {
            path.strip().replace("\\", "/").removeprefix("./")
            for path in paths
            if path.strip()
        }
    )
    if not normalized:
        return Classification(unknown=True)

    docs = False
    python = False
    cpp = False
    assets = False
    ci = False
    ue_code = False
    unknown = False

    for path in normalized:
        matched = False

        if _is_docs(path):
            docs = True
            matched = True
        if _is_python(path):
            python = True
            matched = True
        if _is_cpp(path):
            cpp = True
            matched = True
        if _is_asset(path):
            assets = True
            matched = True
        if _is_ci(path):
            ci = True
            matched = True
        if _is_ue_code(path):
            ue_code = True
            matched = True

        # Other scripts are tooling changes, not docs/assets.
        if path.startswith("scripts/") and not matched:
            ci = True
            matched = True

        # Root metadata that is neither runtime nor documentation is policy.
        if "/" not in path and not matched:
            if PurePosixPath(path).suffix.lower() in {".yml", ".yaml", ".toml"}:
                ci = True
                matched = True

        if not matched:
            unknown = True

    docs_only = docs and not any((python, cpp, assets, ci, ue_code, unknown))
    asset_only = assets and not any((python, cpp, ci, ue_code, unknown))

    return Classification(
        docs=docs,
        python=python,
        cpp=cpp,
        assets=assets,
        ci=ci,
        ue_code=ue_code,
        unknown=unknown,
        docs_only=docs_only,
        asset_only=asset_only,
    )


def git_changed_paths(base: str, head: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRTD", base, head],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def full_static_classification() -> Classification:
    return Classification(
        python=True,
        cpp=True,
        assets=False,
        ci=True,
        ue_code=False,
    )


def emit_github_output(
    classification: Classification,
    *,
    output_path: str,
    base: str,
    head: str,
) -> None:
    values = asdict(classification)
    values["security_base"] = classification.security_base
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={'true' if value else 'false'}\n")
        handle.write(f"base_sha={base}\n")
        handle.write(f"head_sha={head}\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--all-static", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument("--paths-file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.all_static:
        classification = full_static_classification()
        paths: list[str] = []
        base = args.base or "ALL_STATIC"
        head = args.head or "ALL_STATIC"
    else:
        if args.paths_file:
            with open(args.paths_file, encoding="utf-8") as handle:
                paths = [line.strip() for line in handle if line.strip()]
            base = args.base or "PATHS_FILE"
            head = args.head or "PATHS_FILE"
        else:
            if not args.base or not args.head:
                raise SystemExit(
                    "--base and --head are required unless --all-static/--paths-file is used"
                )
            base = args.base
            head = args.head
            paths = git_changed_paths(base, head)
        classification = classify_paths(paths)

    payload = {
        "paths": paths,
        **asdict(classification),
        "security_base": classification.security_base,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    output_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if output_path:
        emit_github_output(
            classification,
            output_path=output_path,
            base=base,
            head=head,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
