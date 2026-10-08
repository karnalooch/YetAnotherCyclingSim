"""Export the captured October 8 TPP survey into durable repository evidence.

Copy existing review images without rerendering or assigning visual labels.
The full original ZIP remains unchanged under the repository's existing LFS
rule. This is inspection evidence, not a new visual-change acceptance record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.proof.package_sa_calobra_tpp_survey import digest, pair_frames
from scripts.proof.retain_sa_calobra_tpp_survey import (
    copy_file,
    inventory,
    no_link,
    publish_no_replace,
    validate_source,
)

DOCS_PATH = Path("docs/experiments/sa-calobra-tpp-survey-20261008")
ARCHIVE_DIRECTORY = Path("docs/experiments/component230-cliff/evidence")
LFS_RULE = "docs/experiments/component230-cliff/evidence/*.zip filter=lfs diff=lfs merge=lfs -text"


@dataclass(frozen=True)
class ExportIdentity:
    capture_sha: str
    run_id: int
    attempt: int
    archive_sha256: str
    archive_size_bytes: int
    frame_count: int
    window_count: int
    pair_count: int


CAPTURE = ExportIdentity(
    "b1ea05b33b9f3208e7aeb6884f1a67792d9c6121",
    37800814004,
    1,
    "f9ad39ae59a16dc1fc4615ef10ca950096a94d443bea4dcb0e624284000a0cab",
    1609577808,
    1338,
    185,
    669,
)


def verify_archive(archive, source_inventory, identity):
    """Bind the exact transport ZIP to every donor file, without extracting it."""
    if not stat.S_ISREG(no_link(archive).st_mode):
        raise ValueError("Artifact ZIP must be a regular file")
    if (
        archive.stat().st_size != identity.archive_size_bytes
        or digest(archive) != identity.archive_sha256
    ):
        raise ValueError("Original artifact ZIP hash/size mismatch")
    expected = {row["path"]: row for row in source_inventory["files"]}
    seen = set()
    with zipfile.ZipFile(archive) as packed:
        for member in packed.infolist():
            name = member.filename
            path = PurePosixPath(name)
            if (
                not name
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or ":" in name
                or stat.S_ISLNK(member.external_attr >> 16)
            ):
                raise ValueError("Unsafe artifact ZIP member")
            if member.is_dir():
                continue
            if name in seen or name not in expected:
                raise ValueError(
                    "Artifact ZIP file inventory differs from donor evidence"
                )
            seen.add(name)
            item = expected[name]
            if member.file_size != item["size_bytes"]:
                raise ValueError("Artifact ZIP member size mismatch")
            checksum = hashlib.sha256()
            with packed.open(member) as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    checksum.update(chunk)
            if checksum.hexdigest() != item["sha256"]:
                raise ValueError("Artifact ZIP member hash mismatch")
    if seen != set(expected):
        raise ValueError("Artifact ZIP is missing donor evidence files")


def write_text(path, value):
    path.write_text(value, encoding="utf-8", newline="\n")


def build_docs(staging, source, report, package_sha, source_inventory, identity):
    review = source / "terrain-erosion-mesh/tpp-survey/review"
    copied = []
    selected = sorted(
        path
        for path in review.rglob("*")
        if path.is_file()
        and (
            path.parent.name == "thumbnails"
            or path.name.startswith("contact-")
            or path.name
            in {
                "route.svg",
                "frames.csv",
                "surface-review-template.csv",
                "review-guide.txt",
            }
        )
    )
    for path in selected:
        relative = path.relative_to(review)
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_file(path, target)
        checksum = digest(path)
        if digest(target) != checksum or path.stat().st_size != target.stat().st_size:
            raise ValueError("Copied documentation viewing aid hash/size mismatch")
        copied.append(
            {
                "path": relative.as_posix(),
                "sha256": checksum,
                "size_bytes": target.stat().st_size,
            }
        )
    pairs = pair_frames(report["frames"])
    by_window = {}
    for window, station, pair in pairs:
        by_window.setdefault(window, []).append((station, pair))
    windows = {row["window_id"]: row for row in report["windows"]}
    pages = staging / "windows"
    pages.mkdir()
    rows = []
    for index, (window, samples) in enumerate(by_window.items()):
        filename = f"window-{index:04d}.md"
        rows.append(
            f"| [{index + 1}]({(Path('windows') / filename).as_posix()}) | `{window}` | {len(samples)} | {windows[window]['length_m']:.2f} m |"
        )
        page = [
            f"# TPP survey window: `{window}`\n",
            "[Survey overview](../README.md)\n",
            f"Capture SHA: `{identity.capture_sha}`. Both directions at the same local stations.\n",
            "These JPEGs are copied viewing aids. Original PNGs and the offline HTML review are inside the full evidence ZIP linked from the overview.\n",
            "Visual review: **PENDING_REVIEW**. Surface tags remain unassigned; camera stations are not surface boundaries.\n",
            "| Local station | Forward | Reverse |",
            "| --- | --- | --- |",
        ]
        for station, pair in samples:
            cells = []
            for direction in ("forward", "reverse"):
                frame = pair[direction]
                image = f"../thumbnails/{frame['frame_id']}.jpg"
                cells.append(
                    f"[![{direction}: {frame['frame_id']}]({image})]({image})<br>`{frame['file']}`"
                )
            page.append(f"| {station:.2f} m | {cells[0]} | {cells[1]} |")
        write_text(pages / filename, "\n".join(page) + "\n")
    archive_relative = f"../component230-cliff/evidence/retained-{identity.run_id}.zip"
    readme = f"""# Sa Calobra: captured bidirectional TPP survey

This directory contains actual viewing material from the completed sampled TPP survey of the accepted cliff presentation. It preserves the captured appearance and does not change terrain, roads or materials.

- Capture revision: `{identity.capture_sha}`.
- Native capture run: [{identity.run_id}](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/{identity.run_id}), attempt {identity.attempt}.
- Coverage: **{len(report["frames"])} native frames, {len(windows)} disconnected construction windows, {len(pairs)} forward/reverse station pairs**.
- Capture and restoration: technically validated. Visual review: **PENDING_REVIEW**. Performance: **NOT_MEASURED**.
- Accepted cliff implementation: `{report["source_scene"]["accepted_cliff_implementation_sha"]}`; recipe `{report["source_scene"]["cliff_recipe"]}`.

Start with the [contact sheets](contact-sheets.md), then open a window below to compare both directions. Click any thumbnail to view its copied JPEG. Full-resolution PNGs, per-frame loading/mip receipts, and the complete offline HTML review are retained in the [original evidence ZIP]({archive_relative}) through Git LFS.

After hydrating and extracting that ZIP, open `terrain-erosion-mesh/tpp-survey/review/index.html`. Original frame paths in the tables and CSV are relative to `terrain-erosion-mesh/tpp-survey/` inside the ZIP.

![Captured road and camera positions](route.svg)

The map uses captured world XY coordinates. Blue/orange tracks show the two camera directions; dashed magenta segments indicate jumps between disconnected windows. Local metres reset per window. The samples do not prove continuous cycling, route-physics chainage, camera clearance, full-area network coverage, or a runtime FPS result.

[Frame index](frames.csv) · [Surface review template](surface-review-template.csv) · [Original review guide](review-guide.txt) · [Export and source hashes](manifest.json)

Surface annotations need a stable `surface_id`, a reason, and an original evidence frame. Multiple tags can describe one surface: `GEO_FIX`, `SILHOUETTE_CRITICAL`, `HERO_DETAIL`, `BACKGROUND_LOW_PRIORITY`, `MATERIAL_TEST_CANDIDATE`. The captured template keeps tags blank until human review. A tag does not authorize automatic geometry changes.

This is an inspection evidence entry, with no fabricated BEFORE/AFTER panels and no new visual acceptance. The accepted cliff appearance remains the baseline. The original ZIP is unchanged: SHA-256 `{identity.archive_sha256}`, {identity.archive_size_bytes} bytes.

## Window pairs

| Window | Source ID | Station pairs | Local length |
| --- | --- | --- | --- |
{chr(10).join(rows)}
"""
    write_text(staging / "README.md", readme)
    contacts = sorted(path.name for path in staging.glob("contact-*.jpg"))
    contact_page = [
        "# Captured TPP contact sheets\n",
        "[Survey overview](README.md)\n",
        f"Capture `{identity.capture_sha}`; {len(pairs)} matched forward/reverse stations. All images are copied from the validated review package. Visual review remains PENDING_REVIEW.\n",
    ]
    for index, name in enumerate(contacts):
        contact_page += [
            f"## Sheet {index + 1}\n",
            f"[![Forward/reverse contact sheet {index + 1}]({name})]({name})\n",
        ]
    write_text(staging / "contact-sheets.md", "\n".join(contact_page))
    generated = inventory(staging)["files"]
    manifest = {
        "schema_version": 1,
        "record_kind": "captured_tpp_inspection_evidence",
        "capture_sha": identity.capture_sha,
        "run_id": identity.run_id,
        "attempt": identity.attempt,
        "capture_date": "2026-10-08",
        "capture_status": "CAPTURED",
        "technical_status": "VALIDATED",
        "visual_acceptance": "PENDING_REVIEW",
        "performance_acceptance": "NOT_MEASURED",
        "frame_count": len(report["frames"]),
        "window_count": len(windows),
        "pair_count": len(pairs),
        "source_scene": report["source_scene"],
        "source_identity": report["source_identity"],
        "package_verification_sha256": package_sha,
        "archive": {
            "path": (ARCHIVE_DIRECTORY / f"retained-{identity.run_id}.zip").as_posix(),
            "sha256": identity.archive_sha256,
            "size_bytes": identity.archive_size_bytes,
            "storage": "git_lfs",
            "contents_verified_against_donor": True,
        },
        "primary_frames": [
            {
                key: row[key]
                for key in (
                    "frame_id",
                    "file",
                    "sha256",
                    "size_bytes",
                    "width_px",
                    "height_px",
                )
            }
            for row in report["frames"]
        ],
        "copied_viewing_aids": copied,
        "documentation_files": generated,
        "donor_files": source_inventory["files"],
        "source_preserved": True,
        "geometry_modified": False,
        "visual_classifications_assigned": False,
    }
    write_text(staging / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def export_docs(source, artifact_zip, repo, identity=CAPTURE):
    source, artifact_zip, repo = (
        Path(source).resolve(strict=True),
        Path(artifact_zip).resolve(strict=True),
        Path(repo).resolve(strict=True),
    )
    no_link(source)
    source_inventory = inventory(source, exclude_metadata=True)
    report, package_sha = validate_source(source, identity.capture_sha)
    if (
        len(report["frames"]) != identity.frame_count
        or len(report["windows"]) != identity.window_count
        or len(pair_frames(report["frames"])) != identity.pair_count
    ):
        raise ValueError("Captured survey counts differ from the fixed export identity")
    verify_archive(artifact_zip, source_inventory, identity)
    if (
        LFS_RULE
        not in (repo / ".gitattributes").read_text(encoding="utf-8").splitlines()
    ):
        raise ValueError("Repository lacks the reviewed evidence ZIP LFS rule")
    docs = repo / DOCS_PATH
    archive = repo / ARCHIVE_DIRECTORY / f"retained-{identity.run_id}.zip"
    if (
        docs.is_relative_to(source)
        or source.is_relative_to(docs)
        or archive == artifact_zip
    ):
        raise ValueError(
            "Donor evidence and documentation destinations must be separate"
        )
    docs.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    for parent in (docs.parent, archive.parent):
        for path in (parent, *parent.parents):
            no_link(path)
    with tempfile.TemporaryDirectory(
        prefix=".tpp-docs-staging-", dir=docs.parent
    ) as temporary:
        staging = Path(temporary)
        build_docs(staging, source, report, package_sha, source_inventory, identity)
        expected = inventory(staging)
        if docs.exists() and inventory(docs) != expected:
            raise FileExistsError(
                "Documentation entry already exists with different bytes; never overwrite"
            )
        if archive.exists():
            no_link(archive)
            if (
                archive.stat().st_size != identity.archive_size_bytes
                or digest(archive) != identity.archive_sha256
            ):
                raise FileExistsError(
                    "Evidence ZIP already exists with different bytes; never overwrite"
                )
        if inventory(source, exclude_metadata=True) != source_inventory:
            raise ValueError("Donor evidence changed while exporting documentation")
        docs_reused, archive_reused = docs.exists(), archive.exists()
        if not archive_reused:
            with tempfile.TemporaryDirectory(
                prefix=".tpp-archive-staging-", dir=archive.parent
            ) as archive_temporary:
                archive_staging = Path(archive_temporary) / archive.name
                copy_file(artifact_zip, archive_staging)
                if (
                    archive_staging.stat().st_size != identity.archive_size_bytes
                    or digest(archive_staging) != identity.archive_sha256
                ):
                    raise ValueError("Copied original evidence ZIP hash/size mismatch")
                # Atomic no-overwrite publication; only the temporary copy is linked.
                archive.hardlink_to(archive_staging)
        if not docs_reused:
            publish_no_replace(staging, docs)
    if (
        inventory(docs) != expected
        or archive.stat().st_size != identity.archive_size_bytes
        or digest(archive) != identity.archive_sha256
    ):
        raise ValueError("Published documentation evidence verification failed")
    if (
        inventory(source, exclude_metadata=True) != source_inventory
        or digest(artifact_zip) != identity.archive_sha256
    ):
        raise ValueError(
            "Donor evidence or original artifact ZIP changed during publication"
        )
    return {
        "status": "DOCS_EXPORTED",
        "capture_sha": identity.capture_sha,
        "run_id": identity.run_id,
        "attempt": identity.attempt,
        "frame_count": identity.frame_count,
        "window_count": identity.window_count,
        "pair_count": identity.pair_count,
        "docs_path": DOCS_PATH.as_posix(),
        "archive_path": archive.relative_to(repo).as_posix(),
        "archive_sha256": identity.archive_sha256,
        "archive_size_bytes": identity.archive_size_bytes,
        "source_preserved": True,
        "outputs_verified": True,
        "idempotent_reuse": docs_reused and archive_reused,
        "visual_acceptance": "PENDING_REVIEW",
        "performance_acceptance": "NOT_MEASURED",
        "copied_files": expected["file_count"],
        "preview_bytes": expected["size_bytes"],
        "manifest_sha256": digest(docs / "manifest.json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact-zip", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--run-id", type=int, default=CAPTURE.run_id)
    parser.add_argument("--attempt", type=int, default=CAPTURE.attempt)
    args = parser.parse_args()
    if (args.expected_sha, args.run_id, args.attempt) != (
        CAPTURE.capture_sha,
        CAPTURE.run_id,
        CAPTURE.attempt,
    ):
        parser.error(
            "This fixed exporter requires the October 8 captured SHA, run and attempt"
        )
    print(json.dumps(export_docs(args.source, args.artifact_zip, args.repo)))


if __name__ == "__main__":
    main()
