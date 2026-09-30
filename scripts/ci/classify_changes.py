#!/usr/bin/env python3
"""Classify YACS changes into CI lanes.

This is the single source of truth for path-based CI routing. The classifier
stays deliberately conservative: known runtime/tooling paths opt into the
relevant expensive lanes, docs-only and asset-only changes stay lightweight,
and unknown paths are surfaced explicitly instead of being silently ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
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

UE_CODE_TOOLING_EXACT = {
    ".github/workflows/reusable-unreal.yml",
    "scripts/ci/Invoke-YacsUnrealCi.ps1",
    "scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1",
    "scripts/ci/Resolve-YacsUnrealCiCache.ps1",
    "scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1",
    "scripts/ci/Test-YacsCodeOnlyCheckout.ps1",
    "scripts/ue/Invoke-YacsProof.ps1",
    "scripts/ue/Preflight-YacsProof.ps1",
    "scripts/ci/Resolve-YacsUnrealEngine.ps1",
}

UNREAL_COMPILE_TOOLING_EXACT = {
    ".github/workflows/reusable-unreal.yml",
    "scripts/ci/Invoke-YacsUnrealCi.ps1",
    "scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1",
    "scripts/ue/Invoke-YacsProof.ps1",
    "scripts/ue/Preflight-YacsProof.ps1",
    "scripts/ci/Resolve-YacsUnrealEngine.ps1",
}

UE_TOOLING_PREFIXES = (
    "scripts/ue/",
    "tools/ue-mcp/",
)

RUNTIME_SENSITIVE_PREFIXES = (
    "Source/",
    "Config/",
    "Plugins/",
    "Build/",
)

EMBARK_TERRAIN_HEAVY_EXACT = {
    ".github/workflows/passo-giau-embark-terrain.yml",
    "scripts/ci/classify_changes.py",
    "scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1",
    "scripts/ci/Resolve-YacsUnrealEngine.ps1",
    "scripts/ue/Invoke-YacsPassoGiauPcgExGraph.ps1",
    "scripts/worldgen/Bootstrap-YacsPcgEx.ps1",
}

EMBARK_TERRAIN_RENDER_PREFIXES = (
    "scripts/assets/",
    "scripts/geometry/",
    "scripts/houdini/",
    "scripts/worldgen/",
    "worldgen/embark/",
)

EMBARK_TERRAIN_RENDER_EXACT = {
    "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1",
    "scripts/ue/stage3g_capture_sp638_local_corridor.py",
}


@dataclass(frozen=True)
class Classification:
    docs: bool = False
    python: bool = False
    cpp: bool = False
    assets: bool = False
    ci: bool = False
    ue_code: bool = False
    ue_tooling: bool = False
    unreal_compile: bool = False
    unreal_runtime: bool = False
    unknown: bool = False
    docs_only: bool = False
    asset_only: bool = False
    asset_full: bool = False

    @property
    def security_base(self) -> bool:
        return self.python or self.cpp or self.ci or self.ue_code or self.unknown

    @property
    def ci_cost_class(self) -> str:
        if self.ue_code or self.asset_full:
            return "heavy"
        if self.docs_only:
            return "light"
        return "standard"

    @property
    def unreal_execution_class(self) -> str:
        if self.unreal_compile:
            return "compile"
        if self.unreal_runtime or self.asset_full:
            return "runtime"
        return "static"


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
    in_source_tree = path.startswith("Source/") or "/Source/" in path
    if not in_source_tree:
        return False
    return pure.suffix.lower() in {".cpp", ".c", ".h", ".hpp", ".inl", ".cs"}


def _is_asset(path: str) -> bool:
    pure = PurePosixPath(path)
    if path.startswith("Content/") or path.startswith("SourceArt/"):
        return True
    return pure.suffix.lower() in ASSET_EXTENSIONS


def _is_asset_full(path: str) -> bool:
    if path.startswith("Content/Prototype/Environment/Stage3G/"):
        return True
    if path.startswith("Content/YACS/WorldGen/PCG/"):
        return True
    if path == "Content/Prototype/Maps/L_CyclingTest.umap":
        return True
    if path in {
        "Source/YetAnotherCyclingSim/Private/Cycling/Stage3PrototypeTerrainActor.cpp",
        "Source/YetAnotherCyclingSim/Public/Cycling/Stage3PrototypeTerrainActor.h",
        "Source/YetAnotherCyclingSim/Private/Editor/CyclingStage3RouteSetupCommandlet.cpp",
        "Source/YetAnotherCyclingSim/Private/Tests/Stage3PrototypeTerrain.spec.cpp",
        "scripts/ue/Invoke-YacsStage3GAuthoring.ps1",
        "scripts/ue/Invoke-YacsStage3GProof.ps1",
        "scripts/ue/Invoke-YacsStage3GVisualCapture.ps1",
        "scripts/ue/stage3g_author_materials.py",
        "scripts/ue/stage3g_author_world.py",
        "tools/ue-mcp/guards/YacsStage3GGuard.js",
        "ue-mcp.yml",
        ".github/workflows/reusable-stage3g-full.yml",
    }:
        return True
    return path.startswith("worldgen/specs/stage3g_")


def _is_ci(path: str) -> bool:
    if path.startswith(".github/") or path.startswith(".circleci/"):
        return True
    if path.startswith("scripts/ci/") or path.startswith("scripts/ue/"):
        return True
    if path in CI_EXACT:
        return True
    return False


def _is_ue_tooling(path: str) -> bool:
    return path == "ue-mcp.yml" or path.startswith(UE_TOOLING_PREFIXES)


def _is_unreal_compile_input(path: str) -> bool:
    pure = PurePosixPath(path)
    if path in UNREAL_COMPILE_TOOLING_EXACT:
        return True
    if _is_cpp(path):
        return True
    return pure.suffix.lower() in {".uproject", ".uplugin"}


def _is_unreal_runtime_input(path: str) -> bool:
    if _is_unreal_compile_input(path):
        return True
    if path in UE_CRITICAL_CONFIG:
        return True
    if path in UE_CODE_TOOLING_EXACT:
        return True
    return False


def _is_ue_code(path: str) -> bool:
    """Backward-compatible signal for the automatic code-only Unreal lane."""
    return _is_unreal_runtime_input(path)


def _is_runtime_sensitive_unknown(path: str) -> bool:
    return path.startswith(RUNTIME_SENSITIVE_PREFIXES)


def _is_known_repository_path(path: str) -> bool:
    matched = any(
        (
            _is_docs(path),
            _is_python(path),
            _is_cpp(path),
            _is_asset(path),
            _is_asset_full(path),
            _is_ci(path),
            _is_ue_tooling(path),
            _is_unreal_runtime_input(path),
        )
    )
    if matched:
        return True
    if path.startswith("scripts/"):
        return True
    if "/" not in path:
        return PurePosixPath(path).suffix.lower() in {".yml", ".yaml", ".toml"}
    return False


def _is_unknown_runtime_compile_input(path: str) -> bool:
    return _is_runtime_sensitive_unknown(path) and not _is_known_repository_path(path)


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
    ue_tooling = False
    unreal_compile = False
    unreal_runtime = False
    unknown = False
    asset_full = False

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
        if _is_asset_full(path):
            asset_full = True
            matched = True
        if _is_ci(path):
            ci = True
            matched = True
        if _is_ue_tooling(path):
            ue_tooling = True
            matched = True
        if _is_unreal_compile_input(path):
            unreal_compile = True
            unreal_runtime = True
            ue_code = True
            matched = True
        elif _is_unreal_runtime_input(path):
            unreal_runtime = True
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
            if _is_runtime_sensitive_unknown(path):
                # Unknown runtime-sensitive inputs fail closed to a binary rebuild.
                ue_code = True
                unreal_runtime = True
                unreal_compile = True

    docs_only = docs and not any((python, cpp, assets, ci, ue_code, unknown))
    asset_only = assets and not any((python, cpp, ci, ue_code, unknown))

    return Classification(
        docs=docs,
        python=python,
        cpp=cpp,
        assets=assets,
        ci=ci,
        ue_code=ue_code,
        ue_tooling=ue_tooling,
        unreal_compile=unreal_compile,
        unreal_runtime=unreal_runtime,
        unknown=unknown,
        docs_only=docs_only,
        asset_only=asset_only,
        asset_full=asset_full,
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
        asset_full=False,
    )


def classify_embark_terrain_proof(paths: Iterable[str]) -> str:
    """Return the cheapest trustworthy M3 Embark terrain proof mode.

    The central classifier remains the only path-policy authority.  The
    specialized proof mode refines already-classified repository changes into
    cheap, render, or heavy execution for the dedicated Passo Giau proof.
    """

    normalized = sorted(
        {
            path.strip().replace("\\", "/").removeprefix("./")
            for path in paths
            if path.strip()
        }
    )
    if not normalized:
        return "heavy"

    for path in normalized:
        if path in EMBARK_TERRAIN_HEAVY_EXACT or _is_ue_code(path):
            return "heavy"

    for path in normalized:
        if path in EMBARK_TERRAIN_RENDER_EXACT:
            return "render"
        if path.startswith(EMBARK_TERRAIN_RENDER_PREFIXES):
            return "render"

    return "cheap"


UNREAL_COMPILE_EXTENSIONS = {".cpp", ".c", ".h", ".hpp", ".inl", ".cs"}

UNREAL_PROOF_EXACT = {
    ".github/workflows/reusable-unreal.yml",
    "scripts/ci/Invoke-YacsUnrealCi.ps1",
    "scripts/ci/Release-YacsUnrealWorkspaceLocks.ps1",
    "scripts/ci/Resolve-YacsUnrealCiCache.ps1",
    "scripts/ci/Resolve-YacsUnrealBuildEnvironment.ps1",
    "scripts/ci/Test-YacsCodeOnlyCheckout.ps1",
    "scripts/ue/Invoke-YacsProof.ps1",
    "scripts/ue/Preflight-YacsProof.ps1",
    "scripts/ci/Resolve-YacsUnrealEngine.ps1",
}


def _hash_repository_inputs(
    root: Path,
    *,
    namespace: str,
    inputs: Iterable[Path],
    seed: str = "",
) -> str:
    hasher = hashlib.sha256()
    hasher.update(f"{namespace}\n{seed}\n".encode("utf-8"))
    for path in sorted(set(inputs), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        hasher.update(relative.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _unreal_binary_fingerprint(repo_root: str | Path = ".") -> str:
    """Hash project/plugin inputs that define the compiled binary graph."""

    root = Path(repo_root).resolve()
    candidates: set[Path] = {root / "YetAnotherCyclingSim.uproject"}

    for source_root in (
        root / "Source",
        root / "Plugins",
        root / "Config",
        root / "Build",
    ):
        if not source_root.exists():
            continue
        for path in source_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if _is_unreal_compile_input(relative) or _is_unknown_runtime_compile_input(
                relative
            ):
                candidates.add(path)

    return _hash_repository_inputs(
        root,
        namespace="yacs-unreal-binary-v1",
        inputs=candidates,
    )


def unreal_compile_fingerprint(repo_root: str | Path = ".") -> str:
    """Hash binary inputs plus the normal lane's build/engine-selection contract."""

    root = Path(repo_root).resolve()
    candidates = {root / path for path in UNREAL_COMPILE_TOOLING_EXACT}
    return _hash_repository_inputs(
        root,
        namespace="yacs-unreal-compile-v2",
        inputs=candidates,
        seed=f"binary={_unreal_binary_fingerprint(root)}",
    )


def unreal_proof_fingerprint(repo_root: str | Path = ".") -> str:
    """Hash inputs that can change the code-only Unreal Automation proof."""

    root = Path(repo_root).resolve()
    candidates = {root / path for path in UE_CRITICAL_CONFIG | UNREAL_PROOF_EXACT}
    return _hash_repository_inputs(
        root,
        namespace="yacs-unreal-proof-v1",
        inputs=candidates,
        seed=f"compile={unreal_compile_fingerprint(root)}",
    )


def embark_terrain_compile_fingerprint(repo_root: str | Path = ".") -> str:
    """Extend the generic Unreal fingerprint with the pinned PCGEx dependency."""

    root = Path(repo_root).resolve()
    config_path = root / "worldgen/embark/pcgex/passo_giau_corridor.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    engine_version = str(config["pcgex"]["engine_version"])
    pcgex_commit = str(config["pcgex"]["commit"])

    heavy_contract = _hash_repository_inputs(
        root,
        namespace="yacs-embark-terrain-build-contract-v1",
        inputs={root / path for path in EMBARK_TERRAIN_HEAVY_EXACT},
    )
    hasher = hashlib.sha256()
    hasher.update(b"yacs-embark-terrain-compile-v3\n")
    hasher.update(f"ue={engine_version}\npcgex={pcgex_commit}\n".encode("utf-8"))
    hasher.update(_unreal_binary_fingerprint(root).encode("ascii"))
    hasher.update(heavy_contract.encode("ascii"))
    return hasher.hexdigest()


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
        handle.write(f"ci_cost_class={classification.ci_cost_class}\n")
        handle.write(f"base_sha={base}\n")
        handle.write(f"head_sha={head}\n")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--all-static", action="store_true")
    parser.add_argument("--github-output")
    parser.add_argument("--paths-file")
    parser.add_argument("--embark-terrain-proof", action="store_true")
    parser.add_argument("--repo-root", default=".")
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

    proof_mode = None
    compile_fingerprint = None
    if args.embark_terrain_proof:
        proof_mode = classify_embark_terrain_proof(paths)
        compile_fingerprint = embark_terrain_compile_fingerprint(args.repo_root)

    unreal_compile_fp = unreal_compile_fingerprint(args.repo_root)
    unreal_proof_fp = unreal_proof_fingerprint(args.repo_root)

    payload = {
        "paths": paths,
        **asdict(classification),
        "security_base": classification.security_base,
        "ci_cost_class": classification.ci_cost_class,
        "unreal_execution_class": classification.unreal_execution_class,
        "unreal_compile_fingerprint": unreal_compile_fp,
        "unreal_proof_fingerprint": unreal_proof_fp,
    }
    if proof_mode is not None:
        payload["proof_mode"] = proof_mode
        payload["compile_fingerprint"] = compile_fingerprint
    print(json.dumps(payload, indent=2, sort_keys=True))

    output_path = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if output_path:
        emit_github_output(
            classification,
            output_path=output_path,
            base=base,
            head=head,
        )
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(
                f"unreal_execution_class={classification.unreal_execution_class}\n"
            )
            handle.write(f"unreal_compile_fingerprint={unreal_compile_fp}\n")
            handle.write(f"unreal_proof_fingerprint={unreal_proof_fp}\n")
            if proof_mode is not None:
                handle.write(f"proof_mode={proof_mode}\n")
                handle.write(f"compile_fingerprint={compile_fingerprint}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
