"""Copy eight original window-0112 PNGs from a pinned, read-only native artifact.

This is evidence retrieval only: no Unreal, geometry edits or image generation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import stat
import struct
from pathlib import Path
from zipfile import ZipFile

ARTIFACT_ID = 11562342248
ARCHIVE_BYTES = 1609577808
ARCHIVE_SHA256 = "f9ad39ae59a16dc1fc4615ef10ca950096a94d443bea4dcb0e624284000a0cab"
CAPTURE_SHA = "b1ea05b33b9f3208e7aeb6884f1a67792d9c6121"
INDEX_REF = "bfbc48057b8b84d087a3685cd71972678a32d412"
INDEX_BLOB_SHA = "6aa5fa289231aff5823451977624c7ef87713d45"
WINDOW_ID = "reviewed-VIAL_TR70190001272-1-interval-24-0"
PREFIX = "terrain-erosion-mesh/tpp-survey/"
FRAME_IDS = tuple(
    f"window-0112-{direction}-{index:05d}"
    for direction in ("forward", "reverse")
    for index in range(4)
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def select_rows(data):
    require(len(data) <= 2 * 1024 * 1024, "Oversized source frame index")
    require(git_blob_sha(data) == INDEX_BLOB_SHA, "Frame index identity differs")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    selected = [row for row in rows if row["window_id"] == WINDOW_ID]
    require(len(selected) == 8, "Expected eight source-bound frame rows")
    by_id = {row["frame_id"]: row for row in selected}
    require(set(by_id) == set(FRAME_IDS), "Missing or duplicate frame identity")
    for row in selected:
        identity = row["frame_id"]
        require(row["file"] == f"frames/{identity}.png", "Unsafe frame path")
        require(
            identity.split("-")[2] == row["direction"],
            "Frame direction differs from identity",
        )
        require(
            row["native_readiness_status"] == "NATIVE_LOADING_AND_MIPS_READY",
            "Source native frame was not ready",
        )
    return [by_id[name] for name in FRAME_IDS]


def extract(archive, index_file, output):
    archive, index_file, output = map(Path, (archive, index_file, output))
    require(not output.exists(), "Preserve existing evidence output")
    require(archive.stat().st_size == ARCHIVE_BYTES, "Archive byte count differs")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    require(digest == ARCHIVE_SHA256, "Original native archive SHA256 differs")
    rows = select_rows(index_file.read_bytes())
    images = []
    with ZipFile(archive) as bundle:
        names = bundle.namelist()
        require(len(names) == len(set(names)), "Duplicate archive member")
        for row in rows:
            member = PREFIX + row["file"]
            info = bundle.getinfo(member)
            require(not stat.S_ISLNK(info.external_attr >> 16), "Symlink image")
            require(0 < info.file_size <= 24 * 1024 * 1024, "Image byte bounds")
            require(info.file_size == int(row["size_bytes"]), "Image size differs")
            data = bundle.read(info)
            require(
                hashlib.sha256(data).hexdigest() == row["sha256"],
                "Original PNG SHA256 differs",
            )
            require(
                len(data) >= 33
                and data[:8] == b"\x89PNG\r\n\x1a\n"
                and data[12:16] == b"IHDR",
                "Image is not a native PNG",
            )
            width, height = struct.unpack(">II", data[16:24])
            require(
                (width, height) == (int(row["width_px"]), int(row["height_px"])),
                "PNG dimensions differ from captured frame",
            )
            images.append((row, data))
    report = {
        "schema_version": 1,
        "status": "ORIGINAL_EVIDENCE_SUBSET_EXTRACTED",
        "source_artifact_id": ARTIFACT_ID,
        "source_run_id": 37800814004,
        "source_capture_sha": CAPTURE_SHA,
        "source_archive_sha256": digest,
        "index_source_ref": INDEX_REF,
        "index_git_blob_sha": INDEX_BLOB_SHA,
        "extraction_sha": os.environ.get("GITHUB_SHA"),
        "window_id": WINDOW_ID,
        "frame_count": len(images),
        "geometry_mutation": False,
        "new_native_capture": False,
        "ai_generated_images": False,
        "visual_acceptance": "PENDING_OWNER",
        "frames": [dict(row, retained_file=f"{row['frame_id']}.png") for row in rows],
    }
    output.mkdir(parents=True, exist_ok=False)
    for row, data in images:
        (output / f"{row['frame_id']}.png").write_bytes(data)
    with (output / "frames.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "receipt.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract(args.archive, args.index, args.output)
    print(json.dumps({"status": result["status"], "frames": result["frame_count"]}))
