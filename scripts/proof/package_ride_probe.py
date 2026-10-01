"""Validate exact-SHA traversal PNGs and make small derived viewing aids.

Run on the hosted media lane, not the UE runner. Pillow is already pinned in
YACS; use host FFmpeg/ffprobe and record their versions, never install a codec
on the owner's machine. Encoded FPS is playback cadence, not runtime FPS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.proof.ride_probe import (
    ProbeConfig,
    frame_plan,
    sample_plan,
    select_focus,
    performance_hotspots,
)  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(root, expected_sha):
    root = Path(root).resolve()
    manifest = root / "ride-probe.json"
    if manifest.stat().st_size > 10_000_000:
        raise ValueError("probe manifest exceeds bounded size")
    report = json.loads(manifest.read_text(encoding="utf-8-sig"))
    config = ProbeConfig(**report["config"])
    if report["exact_sha"] != expected_sha or config.exact_sha != expected_sha:
        raise ValueError("ride-probe exact SHA mismatch")
    if report["status"] != "CAPTURED" or report.get("error"):
        raise ValueError("ride-probe capture did not complete")
    if (
        report["performance_acceptance"] != "NOT_MEASURED"
        or report["frame_timing_is_benchmark"] is not False
    ):
        raise ValueError("diagnostic capture cannot pass as a benchmark")
    if (
        report["visual_acceptance"] != "PENDING_HUMAN_REVIEW"
        or report["saved_to_map"] is not False
    ):
        raise ValueError("diagnostic capture cannot accept or persist the world")
    samples = report["samples"]
    expected_samples = sample_plan(config, 0.0, 1_000_000.0)
    if len(samples) != len(expected_samples):
        raise ValueError("unexpected camera sample count")
    for row, expected in zip(samples, expected_samples):
        for key in ("tick", "time_s", "station_m"):
            if row[key] != expected[key]:
                raise ValueError("route time/station samples drifted")
        for key in (
            "camera_location_cm",
            "road_position_cm",
            "target_cm",
            "road_forward_unit",
        ):
            if len(row[key]) != 3 or not all(math.isfinite(float(v)) for v in row[key]):
                raise ValueError("invalid native camera sample")
        if (
            row["camera_location_cm"][:2] != row["road_position_cm"][:2]
            or abs(row["camera_location_cm"][2] - row["road_position_cm"][2] - 160.0)
            > 1e-6
        ):
            raise ValueError("camera location adjusted for visibility")
    focus = select_focus(report["events"]) if config.mode == "light" else None
    if report["focus"] != focus:
        raise ValueError("focus selection is not reproducible")
    planned = frame_plan(config, samples, focus)
    if len(report["frames"]) != len(planned):
        raise ValueError("missing or excess traversal frames")
    groups = {}
    for row, expected in zip(report["frames"], planned):
        for key in (
            "file",
            "group",
            "index",
            "size",
            "fps",
            "fov",
            "tick",
            "time_s",
            "station_m",
            "camera_location_cm",
            "target_cm",
        ):
            if row[key] != expected[key]:
                raise ValueError(f"frame plan mismatch: {key}")
        if not re.fullmatch(r"(scout|focus|wide)/frame_[0-9]{4}\.png", row["file"]):
            raise ValueError("unsafe frame path")
        path = (root / row["file"]).resolve()
        if root not in path.parents or digest(path) != row["sha256"]:
            raise ValueError("missing/corrupt/path-escaping frame")
        data = path.read_bytes()
        if (
            len(data) != row["bytes"]
            or data[:8] != b"\x89PNG\r\n\x1a\n"
            or list(struct.unpack(">II", data[16:24])) != row["size"]
        ):
            raise ValueError("invalid PNG header or size")
        if row["readiness"]["status"] not in {
            "NATIVE_LOADING_AND_MIPS_READY",
            "NATIVE_LOADING_COMPLETED",
        }:
            raise ValueError("frame captured without readiness barrier")
        macro = report["geometry"]["surface_visibility"]["macro_landscape"]
        if macro and (
            not row["readiness"]["full_height_mips_requested"]
            or row["readiness"]["status"] != "NATIVE_LOADING_AND_MIPS_READY"
        ):
            raise ValueError("visible macro frame lacks full height-mip readiness")
        groups.setdefault(row["group"], []).append(row)
    actual = {
        p.relative_to(root).as_posix()
        for group in ("scout", "focus", "wide")
        for p in (root / group).glob("frame_*.png")
    }
    if actual != {row["file"] for row in planned}:
        raise ValueError("stale or untracked frames in evidence folder")
    return report, groups


def checked(args):
    return subprocess.run(
        args, capture_output=True, text=True, check=True, timeout=120
    ).stdout


def package(root, expected_sha):
    root = Path(root)
    report, groups = validate(root, expected_sha)
    from PIL import Image, ImageDraw

    for frame in report["frames"]:
        with Image.open(root / frame["file"]) as image:
            image.verify()
        with Image.open(root / frame["file"]) as image:
            image.load()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError(
            "host FFmpeg/ffprobe missing; raw PNG evidence is retained, media not certified"
        )
    tools = {name: checked([name, "-version"]) for name in ("ffmpeg", "ffprobe")}
    result = {
        "exact_sha": expected_sha,
        "technical_status": "VALIDATED",
        "visual_acceptance": "PENDING_HUMAN_REVIEW",
        "performance_acceptance": "NOT_MEASURED",
        "media": [],
        "tools": tools,
    }
    for group, frames in groups.items():
        # Bounded contact sheet; detail clips use 11 representative stills.
        selected = frames if group == "scout" else frames[::4]
        cols, cellw, cellh = 4, 384, 250
        sheet = Image.new(
            "RGB", (cols * cellw, math.ceil(len(selected) / cols) * cellh)
        )
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(selected):
            with Image.open(root / row["file"]) as im:
                thumbnail = im.convert("RGB")
                thumbnail.thumbnail((384, 216))
                x, y = index % cols * cellw, index // cols * cellh
                sheet.paste(thumbnail, (x, y))
                draw.text(
                    (x + 4, y + 218),
                    f"{group} t={row['time_s']:.1f}s S={row['station_m']:.1f}m FOV={row['fov']}",
                )
        sheet.save(root / f"{group}-contact.png")
        fps = frames[0]["fps"]
        mp4 = root / f"{group}.mp4"
        checked(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-framerate",
                str(fps),
                "-start_number",
                "0",
                "-f",
                "image2",
                "-c:v",
                "png",
                "-i",
                str(root / group / "frame_%04d.png"),
                "-frames:v",
                str(len(frames)),
                "-an",
                "-c:v",
                "libx264",
                "-threads",
                "2",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4),
            ]
        )
        stream = json.loads(
            checked(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-count_frames",
                    "-show_entries",
                    "stream=codec_name,width,height,nb_read_frames,r_frame_rate,duration",
                    "-of",
                    "json",
                    str(mp4),
                ]
            )
        )["streams"][0]
        if (
            int(stream["nb_read_frames"]) != len(frames)
            or [stream["width"], stream["height"]] != frames[0]["size"]
            or stream["codec_name"] != "h264"
        ):
            raise RuntimeError(
                "encoded media did not preserve the frame count/dimensions/codec"
            )
        if (
            stream["r_frame_rate"] != f"{fps}/1"
            or abs(float(stream["duration"]) - len(frames) / fps) > 0.02
        ):
            raise RuntimeError("encoded media timing mismatch")
        images = []
        for row in frames:
            with Image.open(root / row["file"]) as im:
                im = im.convert("RGB")
                im.thumbnail((640, 360))
                images.append(im.copy())
        images[0].save(
            root / f"{group}.gif",
            save_all=True,
            append_images=images[1:],
            duration=1000 // fps,
            loop=0,
        )
        result["media"].append(
            {
                "file": mp4.name,
                "sha256": digest(mp4),
                "stream": stream,
                "sampled_time_span_s": frames[-1]["time_s"] - frames[0]["time_s"],
                "last_frame_hold_s": 1 / fps,
                "duplicate_png_hashes": len(frames)
                - len({r["sha256"] for r in frames}),
            }
        )
    fields = (
        "group",
        "index",
        "time_s",
        "station_m",
        "fov",
        "capture_wall_s",
        "sha256",
        "file",
    )
    with (root / "frames.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["frames"])
    (root / "media-verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (root / "README.txt").write_text(
        "DIAGNOSTIC CAMERA TRAVERSAL - NOT GAMEPLAY OR A PERFORMANCE BENCHMARK\n"
        "PNG + ride-probe.json are primary evidence; GIF may introduce palette artifacts.\n"
        "Inspect scout-contact.png; the locator is collision-only, not complete visual defect detection.\n"
        "Focus is two seconds before/after the selected route station at 10 m/s.\n"
        "41 endpoint-inclusive frames span 4 seconds, with a final 0.1-second video hold.\n"
        "For an image-only finding rerun focus with that frame's station_m, same SHA and variant.\n",
        encoding="utf-8",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--performance-csv", type=Path)
    parser.add_argument("--performance-context", type=Path)
    args = parser.parse_args()
    if args.validate_only:
        validate(args.root, args.expected_sha)
    else:
        package(args.root, args.expected_sha)
    if bool(args.performance_csv) != bool(args.performance_context):
        parser.error("CSV and performance context must be provided together")
    if args.performance_csv:
        config = ProbeConfig(args.expected_sha)
        with args.performance_csv.open(encoding="utf-8-sig", newline="") as source:
            events = performance_hotspots(
                list(csv.DictReader(source)),
                json.loads(args.performance_context.read_text()),
                config,
            )
        (args.root / "performance-locators.json").write_text(
            json.dumps(events, indent=2) + "\n"
        )
    print("Ride probe evidence: VALIDATED; visual PENDING; performance NOT_MEASURED")


if __name__ == "__main__":
    main()
