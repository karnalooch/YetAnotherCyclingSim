"""Replay a bounded detail proposal from fixed public LFS evidence; never run UE."""

import argparse
import csv
import hashlib
import io
import json
import re
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

OID = "f9ad39ae59a16dc1fc4615ef10ca950096a94d443bea4dcb0e624284000a0cab"
SIZE = 1609577808
CAPTURE = "b1ea05b33b9f3208e7aeb6884f1a67792d9c6121"
LIMIT = 32 * 1024 * 1024
BATCH = "https://github.com/karnalooch/YetAnotherCyclingSim.git/info/lfs/objects/batch"
MESH = "a9d34dbfb32a59b592dca561a7d7b0e53f7d02d90c095cff7c0812c249247965"
RECEIPT = "35c76796924681c4d836388761bcc3ee83dd6e9fa544c3adb109e004e1c58225"
FRAMES = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_bytes(path):
    require(path.stat().st_size < LIMIT, "Local input exceeds bounded size")
    return path.read_bytes()


def download_action():
    body = json.dumps(
        dict(
            operation="download",
            transfers=["basic"],
            objects=[dict(oid=OID, size=SIZE)],
        )
    ).encode()
    request = urllib.request.Request(
        BATCH,
        data=body,
        headers={
            "Content-Type": "application/vnd.git-lfs+json",
            "Accept": "application/vnd.git-lfs+json",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        require(response.status == 200, "Public LFS batch failed")
        data = response.read(1024 * 1024 + 1)
    require(len(data) <= 1024 * 1024, "Oversized LFS batch response")
    objects = json.loads(data)["objects"]
    require(
        len(objects) == 1 and objects[0]["oid"] == OID and objects[0]["size"] == SIZE,
        "LFS identity mismatch",
    )
    action = objects[0]["actions"]["download"]
    url = urlsplit(action["href"])
    require(
        url.scheme == "https"
        and url.hostname is not None
        and (
            url.hostname.endswith(".githubusercontent.com")
            or url.hostname == "github-cloud.s3.amazonaws.com"
        )
        and not url.username
        and not url.password
        and url.port in (None, 443),
        "Unexpected LFS download authority",
    )
    return action


class RemoteArchive(io.RawIOBase):
    def __init__(self, action):
        self.action, self.position, self.bytes_read, self.requests = action, 0, 0, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        require(whence in (0, 1, 2), "Invalid seek mode")
        position = (0, self.position, SIZE)[whence] + offset
        require(0 <= position <= SIZE, "Archive seek outside fixed object")
        self.position = position
        return position

    def read(self, size=-1):
        size = SIZE - self.position if size < 0 else min(size, SIZE - self.position)
        require(
            size < LIMIT and self.bytes_read + size <= 4 * LIMIT,
            "Archive read exceeds bounded budget",
        )
        if size == 0:
            return b""
        start, end = self.position, self.position + size - 1
        headers = dict(
            self.action.get("header", {}),
            Range=f"bytes={start}-{end}",
            **{"Accept-Encoding": "identity"},
        )
        request = urllib.request.Request(self.action["href"], headers=headers)
        with urllib.request.urlopen(request, timeout=45) as response:
            require(response.status == 206, "Range request did not return 206")
            require(
                response.headers.get("Content-Range") == f"bytes {start}-{end}/{SIZE}",
                "Content-Range mismatch",
            )
            data = response.read(size + 1)
        require(len(data) == size, "Range length mismatch")
        self.position += size
        self.bytes_read += size
        self.requests += 1
        return data


def verify_native(receipt):
    trial = receipt["terrain_erosion_trial"]
    export = trial["mesh_export"]
    require(
        receipt["exact_sha"] == CAPTURE
        and receipt["status"] == "COMPONENT230_CLIFF_VISUAL_PASS"
        and receipt["mesh"]["generator"] == "native-source-rock-reshape"
        and export["shape_profile"] == "rounded-limestone-reshape-v8",
        "Native capture identity mismatch",
    )
    require(
        all(
            receipt[k] is False
            for k in (
                "map_saved",
                "assets_saved",
                "canonical_landscape_mutation",
                "selector_policy_mutation",
            )
        )
        and trial["restored"] is True
        and trial["source_heightfield_unchanged"] is True
        and trial["terrain_import_performed"] is False
        and trial["derived_heightfield_modified"] is False
        and export["displacement_limit_cm"] == 50
        and trial["combined_audit"]["status"] == "PASS",
        "Native source preservation mismatch",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("frames", "annotations", "output"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args()
    frames_data = local_bytes(args.frames)
    annotations_data = local_bytes(args.annotations)
    require(sha(frames_data) == FRAMES, "Frozen captured camera CSV identity mismatch")
    rows = list(csv.DictReader(io.StringIO(frames_data.decode("utf-8-sig"))))
    index = {r["frame_id"]: r for r in rows}
    require(len(index) == len(rows), "Duplicate source frame records")
    annotations = json.loads(annotations_data)
    require(
        annotations.get("schema_version") == 1
        and annotations.get("mesh_sha256") == MESH,
        "Pilot schema or source mesh identity mismatch",
    )
    frame_ids = [r["frame_id"] for r in annotations["frames"]]
    require(
        0 < len(frame_ids) <= 8 and len(set(frame_ids)) == len(frame_ids),
        "Expected 1 to 8 unique annotated frames",
    )
    require(
        all(
            re.fullmatch(r"window-\d{4}-(forward|reverse)-\d{5}", fid) and fid in index
            for fid in frame_ids
        ),
        "Unknown annotated frame ID",
    )
    require(
        all(
            r.get("original_image") == "../source/" + r["frame_id"] + ".png"
            for r in annotations["frames"]
        ),
        "Original image references must use verified sibling source",
    )
    require(
        all(
            index[fid]["file"] == "frames/" + fid + ".png"
            and re.fullmatch(r"[a-f0-9]{64}", index[fid]["sha256"])
            for fid in frame_ids
        ),
        "Invalid fixed source frame path or hash",
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    remote = RemoteArchive(download_action())
    records = []
    entries = [
        ("terrain-erosion-mesh/combined-mesh.json", MESH, None),
        ("terrain-erosion-mesh/component230-cliff-visual-receipt.json", RECEIPT, None),
    ]
    entries += [
        (
            "terrain-erosion-mesh/tpp-survey/" + index[fid]["file"],
            index[fid]["sha256"],
            fid,
        )
        for fid in frame_ids
    ]
    with zipfile.ZipFile(remote) as archive:
        for entry, expected, fid in entries:
            matches = [info for info in archive.infolist() if info.filename == entry]
            require(len(matches) == 1, "Missing or ambiguous fixed archive entry")
            info = matches[0]
            require(
                0 < info.file_size < LIMIT and 0 < info.compress_size < LIMIT,
                "Oversized archive entry",
            )
            data = archive.read(
                info
            )  # zipfile verifies the entry CRC before returning.
            require(sha(data) == expected, "Fixed archive entry SHA-256 mismatch")
            if fid:
                row = index[fid]
                require(
                    len(data) == int(row["size_bytes"]), "Original PNG size mismatch"
                )
                require(
                    data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24,
                    "Invalid original PNG",
                )
                require(
                    struct.unpack(">II", data[16:24])
                    == (int(row["width_px"]), int(row["height_px"]))
                    == (1280, 720),
                    "Original PNG dimensions mismatch",
                )
            (source / Path(entry).name).write_bytes(data)
            records.append(
                dict(
                    archive_entry=entry,
                    sha256=expected,
                    size_bytes=len(data),
                    crc32=f"{info.CRC:08x}",
                )
            )
    verify_native(
        json.loads((source / "component230-cliff-visual-receipt.json").read_bytes())
    )
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("prepare_sa_calobra_detail_pilot.py")),
            "--mesh",
            str(source / "combined-mesh.json"),
            "--frames",
            str(args.frames.resolve()),
            "--annotations",
            str(args.annotations.resolve()),
            "--output",
            str(output / "pilot"),
        ],
        check=True,
    )
    receipt = dict(
        status="DERIVATIVE_REPLAY_COMPLETE",
        source_capture_sha=CAPTURE,
        archive_oid=OID,
        archive_size_bytes=SIZE,
        whole_archive_hash_recomputed=False,
        archive_download="PARTIAL_HTTP_RANGES",
        source_files=records,
        frames_csv_sha256=sha(frames_data),
        annotations_sha256=sha(annotations_data),
        range_bytes_read=remote.bytes_read,
        range_request_count=remote.requests,
        native_ue="NOT_RUN",
        performance="NOT_MEASURED",
        owner_review="PENDING",
    )
    (output / "replay-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                status=receipt["status"],
                verified_entries=len(records),
                range_bytes_read=remote.bytes_read,
            )
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit("Detail replay failed: " + type(error).__name__) from None
