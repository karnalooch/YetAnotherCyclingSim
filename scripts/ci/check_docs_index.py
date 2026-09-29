#!/usr/bin/env python3
"""Validate the YACS documentation entrypoint contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
INDEX = DOCS / "README.md"
ROOT_README = ROOT / "README.md"
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

REQUIRED_HEADINGS = {
    "# YACS documentation",
    "## Start here",
    "## Authority map",
    "## Evidence, experiments and history",
    "## Complete top-level catalog",
    "## Documentation maintenance",
}

REQUIRED_LINKS = {
    "PRODUCT_REQUIREMENTS.md",
    "ROADMAP.md",
    "ROAD_PHYSICS_PROFILE.md",
    "STAGE3G_R4_1_ALPINE_VISUAL_RECOVERY.md",
    "STAGE3G_R4_1_TERRAIN_RESEARCH.md",
    "CI_VALIDATION_TIERS.md",
    "ENGINEERING_PLATFORM.md",
    "visual-history/README.md",
    "performance/PERFORMANCE_FRAMEWORK.md",
    "performance-history/README.md",
    "experiments/README.md",
}


def read_utf8(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise ValueError(\n            f"{path.relative_to(ROOT)} contains Unicode replacement characters"\n        )
    return text


def local_targets(source: Path, text: str) -> set[Path]:
    targets: set[Path] = set()
    for raw in LINK_RE.findall(text):
        raw = raw.strip().strip("<>")
        split = urlsplit(raw)
        if split.scheme or raw.startswith("//") or raw.startswith("#") or not split.path:
            continue

        relative = unquote(split.path)
        candidate = (
            ROOT / relative.lstrip("/")
            if relative.startswith("/")
            else source.parent / relative
        ).resolve()

        if not candidate.is_relative_to(ROOT):
            raise ValueError(\n                f"{source.relative_to(ROOT)} links outside repository: {raw}"\n            )
        targets.add(candidate)
    return targets


def fail(message: str) -> int:
    print(f"docs-index: FAIL - {message}", file=sys.stderr)
    return 1


def main() -> int:
    if not INDEX.is_file():
        return fail("docs/README.md is missing")
    if not ROOT_README.is_file():
        return fail("README.md is missing")

    try:
        index_text = read_utf8(INDEX)
        root_text = read_utf8(ROOT_README)
        print("docs-index: i18n PASS - UTF-8 entrypoints are readable")

        missing_headings = sorted(REQUIRED_HEADINGS - set(index_text.splitlines()))
        if missing_headings:
            return fail("missing headings: " + ", ".join(missing_headings))
        if "(docs/README.md)" not in root_text:
            return fail("README.md must link to docs/README.md")

        index_targets = local_targets(INDEX, index_text)
        root_targets = local_targets(ROOT_README, root_text)
        indexed_docs = {
            path.relative_to(DOCS).as_posix()
            for path in index_targets
            if path.is_relative_to(DOCS)
        }
        missing_required = sorted(REQUIRED_LINKS - indexed_docs)
        if missing_required:
            return fail("missing authority links: " + ", ".join(missing_required))
        print("docs-index: structure PASS")

        broken = sorted(
            str(path.relative_to(ROOT))
            for path in index_targets | root_targets
            if not path.exists()
        )
        if broken:
            return fail("broken local links: " + ", ".join(broken))
        print("docs-index: links PASS")

        top_level = {path.name for path in DOCS.glob("*.md") if path != INDEX}
        indexed_top_level = {
            path.name
            for path in index_targets
            if path.parent == DOCS and path.suffix.lower() == ".md"
        }
        missing_top_level = sorted(top_level - indexed_top_level)
        if missing_top_level:
            return fail(\n                "top-level docs missing from index: " + ", ".join(missing_top_level)\n            )
        print("docs-index: freshness PASS")
    except (OSError, UnicodeError, ValueError) as exc:
        return fail(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
