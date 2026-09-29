#!/usr/bin/env python3
"""Validate the YACS documentation entrypoint contract.

This guard is intentionally small and fast. It protects the repository-level
documentation map without trying to lint every historical Markdown file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
INDEX = DOCS_DIR / "README.md"
ROOT_README = ROOT / "README.md"

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

REQUIRED_INDEX_LINKS = {
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

REQUIRED_HEADINGS = {
    "# YACS documentation",
    "## Start here",
    "## Authority map",
    "## Evidence, experiments and history",
    "## Complete top-level catalog",
    "## Documentation maintenance",
}


class ContractError(RuntimeError):
    pass


def read_utf8(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"{path.relative_to(ROOT)} is not readable UTF-8: {exc}") from exc
    if "\ufffd" in text:
        raise ContractError(f"{path.relative_to(ROOT)} contains Unicode replacement characters")
    return text


def normalized_local_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    split = urlsplit(target)

    if split.scheme or target.startswith("//") or target.startswith("#"):
        return None

    relative = unquote(split.path)
    if not relative:
        return None

    if relative.startswith("/"):
        candidate = ROOT / relative.lstrip("/")
    else:
        candidate = source.parent / relative

    resolved = candidate.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ContractError(
            f"{source.relative_to(ROOT)} links outside the repository: {raw_target}"
        ) from exc
    return resolved


def local_links(source: Path, text: str) -> dict[str, Path]:
    links: dict[str, Path] = {}
    for match in LINK_RE.finditer(text):
        raw = match.group(1)
        target = normalized_local_target(source, raw)
        if target is not None:
            links[raw] = target
    return links


def check_structure(index_text: str, root_text: str) -> None:
    missing_headings = sorted(h for h in REQUIRED_HEADINGS if h not in index_text)
    if missing_headings:
        raise ContractError(
            "docs/README.md is missing required headings: " + ", ".join(missing_headings)
        )

    if "(docs/README.md)" not in root_text:
        raise ContractError("README.md must link to docs/README.md")

    index_targets = {
        target.relative_to(DOCS_DIR).as_posix()
        for target in local_links(INDEX, index_text).values()
        if target.is_relative_to(DOCS_DIR)
    }
    missing_required = sorted(REQUIRED_INDEX_LINKS - index_targets)
    if missing_required:
        raise ContractError(
            "docs/README.md is missing required authority-map links: "
            + ", ".join(missing_required)
        )


def check_links(source: Path, text: str) -> None:
    broken = []
    for raw, target in local_links(source, text).items():
        if not target.exists():
            broken.append(f"{raw} -> {target.relative_to(ROOT)}")
    if broken:
        raise ContractError(
            f"{source.relative_to(ROOT)} has broken local links: " + "; ".join(sorted(broken))
        )


def check_freshness(index_text: str) -> None:
    top_level_docs = {
        path.name for path in DOCS_DIR.glob("*.md") if path.name != INDEK›˜[YBˆBˆ[šÙYİÜÛ]™[ÙØÜÈHÂˆ\™Ù]›˜[YBˆ›Üˆ\™Ù][ˆØØ[Û[šÜÊS‘V[™^İ^
K˜[Y\Ê
BˆYˆ\™Ù]œ\™[OHĞÔ×ÑTˆ[™\™Ù]œİY™š^›İÙ\Š
HOH‹›Y‚ˆB‚ˆZ\ÜÚ[™ÈHÛÜY
ÜÛ]™[ÙØÜÈH[šÙYİÜÛ]™[ÙØÜÊBˆYˆZ\ÜÚ[™Î‚ˆ˜Z\ÙHÛÛ˜Xİ\œ›ÜŠˆÜ[]™[ØÜÈ\™HZ\ÜÚ[™Èœ›ÛHØÜËÔ‘PQQK›Yˆˆ
È‹‹š›Ú[ŠZ\ÜÚ[™ÊBˆ
B‚‚™YˆXZ[Š
HOˆ[‚ˆYˆ›İS‘Vš\×Ùš[J
N‚ˆš[
™ØÜËZ[™^ˆİXİ\™HRSHØÜËÔ‘PQQK›Y\ÈZ\ÜÚ[™È‹š[O\Ş\Ëœİ\œŠBˆ™]\›ˆBˆYˆ›İ“ÓÕÔ‘PQQKš\×Ùš[J
N‚ˆš[
™ØÜËZ[™^ˆİXİ\™HRSH‘PQQK›Y\ÈZ\ÜÚ[™È‹š[O\Ş\Ëœİ\œŠBˆ™]\›ˆB‚ˆN‚ˆ[™^İ^H™XYİ]
S‘V
Bˆ›Ûİİ^H™XYİ]
“ÓÕÔ‘PQQJBˆš[
™ØÜËZ[™^ˆLNˆTÔÈHU‹N[\Ú[È\™H™XYX›HŠB‚ˆÚXÚ×ÜİXİ\™J[™^İ^›Ûİİ^
Bˆš[
™ØÜËZ[™^ˆİXİ\™HTÔÈŠB‚ˆÚXÚ×Û[šÜÊS‘V[™^İ^
BˆÚXÚ×Û[šÜÊ“ÓÕÔ‘PQQK›Ûİİ^
Bˆš[
™ØÜËZ[™^ˆ[šÜÈTÔÈŠB‚ˆÚXÚ×Ùœ™\Ú™\ÜÊ[™^İ^
Bˆš[
™ØÜËZ[™^ˆœ™\Ú™\ÜÈTÔÈŠBˆ^Ù\ÛÛ˜Xİ\œ›Üˆ\È^Î‚ˆš[
ˆ™ØÜËZ[™^ˆRSHÙ^ßH‹š[O\Ş\Ëœİ\œŠBˆ™]\›ˆB‚ˆ™]\›ˆ‚‚šYˆ×Û˜[YW×ÈOH—×ÛXZ[—×È‚ˆ˜Z\ÙHŞ\İ[Q^]
XZ[Š
JB