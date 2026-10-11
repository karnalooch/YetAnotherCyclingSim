"""Read eight source-owned hairpin transects from retained NPC03 points.

The predecessor is prepare_sa_calobra_lidar_masks.py: the same authenticated
LAZ files, LasHeader.parse_crs and LasReader.chunk_iterator are reused. This
reader exports observations only; it never fits or authors a road or terrain.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.manage_local_workspace import digest, load_workspace

LIDAR_RELATIVE = "lidar-masks-v1b-2026-10-04/lidar-manifest.json"
LIDAR_IDENTITY = {
    "size_bytes": 19312,
    "sha256": "fd14d0725f867759438727f9f7275f15427220ea185b01783c9d616432523e00",
}
PROFILE_RELATIVE = "frozen-road-c5573b3-2026-10-04/ma2141-profile-candidate.json"
PROFILE_IDENTITY = {
    "size_bytes": 9232773,
    "sha256": "c0ca612dd5af5a311d1917e41d66f44aa83a9d40eed5e9e784432e06e2a52253",
}
STATIONS_M = (95.0, 110.0, 125.0, 135.0, 145.0, 150.0, 155.0, 165.0)
ORIGIN_M = (483000.25, 4409516.25)
HALF_ALONG_M, HALF_LATERAL_M = 1.0, 12.0
DECODER_VERSIONS = {
    "laspy": "2.7.0",
    "lazrs": "0.8.2",
    "numpy": "2.3.5",
    "pyproj": "3.8.0",
}
CHUNK_SIZE = 250_000
MAX_CSV_ROWS, MAX_CSV_BYTES = 100_000, 32 * 1024 * 1024
CSV_FIELDS = (
    "source_station_m",
    "profile_section_index",
    "tile",
    "point_index",
    "raw_x",
    "raw_y",
    "raw_z",
    "easting_m",
    "northing_m",
    "z_m",
    "classification",
    "withheld",
    "synthetic",
    "overlap",
    "key_point",
    "return_number",
    "number_of_returns",
    "point_source_id",
    "scanner_channel",
    "scan_direction_flag",
    "edge_of_flight_line",
    "along_m",
    "lateral_m",
    "accepted_by_existing_reader",
)


class Unavailable(RuntimeError):
    """An existing input or decoder is absent; there are no point observations."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _safe(root, relative):
    root = Path(root).resolve()
    path = root / relative
    require(
        not Path(relative).is_absolute() and ".." not in Path(relative).parts,
        "Source path escapes its cache",
    )
    require(path.resolve().is_relative_to(root), "Source link escapes its cache")
    return path


def _match(path, identity):
    if not path.is_file():
        raise Unavailable("Missing retained source: " + str(path))
    require(
        path.stat().st_size == identity["size_bytes"]
        and digest(path) == identity["sha256"],
        "Retained source bytes differ: " + str(path),
    )


def _read(path, identity):
    _match(path, identity)
    raw = path.read_bytes()
    require(
        len(raw) == identity["size_bytes"]
        and hashlib.sha256(raw).hexdigest() == identity["sha256"],
        "Retained source changed during read: " + str(path),
    )
    return raw, json.loads(raw)


def transects(profile):
    """Use actual source keys and cross-sections; no closest-road projection."""
    require(
        profile.get("origin_epsg_m") == list(ORIGIN_M)
        and profile.get("metric_crs") == "EPSG:25831",
        "Profile CRS/origin differs",
    )
    rows = profile["stations"]
    require(
        len(rows) == 2401
        and [r["station_m"] for r in rows] == [i * 0.125 for i in range(2401)],
        "Frozen profile source stations differ",
    )
    result = []
    for station in STATIONS_M:
        index = next(i for i, r in enumerate(rows) if r["station_m"] == station)
        row = rows[index]
        xy, z, ground = (
            row[k] for k in ("xy_local_m", "candidate_ground_m", "native_ground_m")
        )
        require(
            len(xy) == len(z) == len(ground) == 25
            and all(len(p) == 2 for p in xy)
            and all(
                math.isfinite(v) for v in [*z, *ground, *(v for p in xy for v in p)]
            ),
            "Invalid 25-point source section",
        )
        width = math.dist(xy[0], xy[24])
        require(width > 1e-6, "Collapsed source cross-section")
        lateral = [(xy[24][k] - xy[0][k]) / width for k in (0, 1)]
        along = [-lateral[1], lateral[0]]
        forward = [
            rows[index + 1]["xy_local_m"][12][k] - rows[index - 1]["xy_local_m"][12][k]
            for k in (0, 1)
        ]
        alignment = sum(along[k] * forward[k] for k in (0, 1))
        require(
            math.isfinite(alignment) and abs(alignment) > 1e-9,
            "Source station has no forward orientation",
        )
        if alignment < 0:
            along = [-v for v in along]
        center = [ORIGIN_M[0] + xy[12][0], ORIGIN_M[1] - xy[12][1]]
        along, lateral = [along[0], -along[1]], [lateral[0], -lateral[1]]
        corners = [
            [center[k] + s * along[k] + u * lateral[k] for k in (0, 1)]
            for s in (-HALF_ALONG_M, HALF_ALONG_M)
            for u in (-HALF_LATERAL_M, HALF_LATERAL_M)
        ]
        result.append(
            {
                "source_station_m": station,
                "profile_section_index": index,
                "center_epsg25831_m": center,
                "along_unit": along,
                "lateral_unit": lateral,
                "bounds_epsg25831_m": [min(p[k] for p in corners) for k in (0, 1)]
                + [max(p[k] for p in corners) for k in (0, 1)],
                "width_m": width,
                "candidate_crossfall_ratio": (z[24] - z[0]) / width,
                "source_samples": [
                    {
                        "column": c,
                        "xy_local_m": xy[c],
                        "native_ground_m": ground[c],
                        "candidate_ground_m": z[c],
                        "frozen_pavement_m": z[c] + 0.04,
                        "candidate_minus_native_ground_m": z[c] - ground[c],
                    }
                    for c in (0, 12, 24)
                ],
            }
        )
    return result


def _overlaps(header, frame):
    lower, upper = header["bounds"]
    x0, y0, x1, y1 = frame["bounds_epsg25831_m"]
    return lower[0] <= x1 and upper[0] >= x0 and lower[1] <= y1 and upper[1] >= y0


def _headers(manifest):
    inputs, headers = manifest["inputs"], manifest["headers"]
    require(
        manifest["status"] == "LIDAR_EVIDENCE_CANDIDATE"
        and manifest["geometry_mutation"] is False
        and len(inputs) == len(headers) == 9,
        "Unexpected retained LiDAR inventory",
    )
    names = [Path(r["path"]).name for r in inputs]
    require(
        len(set(names)) == 9 and set(names) == {r["file"] for r in headers},
        "Retained header/source inventory differs",
    )
    by_name = {r["file"]: r for r in headers}
    for row in headers:
        require(
            row["crs"] == "EPSG:25831"
            and row["version"] == "1.4"
            and row["point_format"] == 8
            and type(row["points"]) is int
            and row["points"] > 0,
            "Retained header format/CRS differs",
        )
        require(
            len(row["bounds"]) == 2
            and all(len(p) == 3 for p in row["bounds"])
            and all(math.isfinite(v) for p in row["bounds"] for v in p)
            and all(row["bounds"][0][k] <= row["bounds"][1][k] for k in range(3)),
            "Retained header bounds are invalid",
        )
    require(
        sum(r["points"] for r in headers) == manifest["counts"]["decoded_all_tiles"],
        "Retained header point total differs",
    )
    return inputs, by_name


def _decoder(report):
    versions = {}
    for name in DECODER_VERSIONS:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    report["decoder_versions"] = versions
    if versions != DECODER_VERSIONS:
        raise Unavailable("Existing decoder is missing or differs from pinned versions")
    try:
        import laspy
        import lazrs  # noqa: F401
        import numpy as np
        import pyproj  # noqa: F401
    except ImportError as exc:
        raise Unavailable("Existing decoder cannot import: " + str(exc)) from exc
    return laspy, np


def decoder_environment():
    """Qualify an existing interpreter without opening any geographic input."""
    executable = Path(sys.executable)
    report = {
        "status": "UNAVAILABLE",
        "executable": str(executable),
        "python_version": list(sys.version_info[:3]),
        "implementation": sys.implementation.name,
        "pointer_bits": struct.calcsize("P") * 8,
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "base_executable": getattr(sys, "_base_executable", None),
        "imports_verified": False,
        "decoder_versions": {},
        "error": None,
    }
    try:
        report["executable_identity"] = {
            "size_bytes": executable.stat().st_size,
            "sha256": digest(executable),
        }
        require(
            report["python_version"][:2] == [3, 12]
            and report["implementation"] == "cpython"
            and report["pointer_bits"] == 64,
            "Existing decoder must match the recorded CPython 3.12 x64 ABI",
        )
        _decoder(report)
        report.update(status="EXISTING_DECODER_READY", imports_verified=True)
    except Exception as exc:  # noqa: BLE001
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def resolve_existing_decoder(workspace):
    """Inspect only configured/registered interpreters; never scan or install."""
    project_venv = Path(workspace["project"]) / ".venv"
    candidates = [
        ("configured_project_venv", project_venv / "Scripts/python.exe"),
        ("calling_interpreter", Path(sys.executable)),
    ]
    path_python = shutil.which("python")
    if path_python:
        candidates.append(("registered_path_python", Path(path_python)))
    config = project_venv / "pyvenv.cfg"
    report = {
        "schema_version": 1,
        "status": "GIS_ENVIRONMENT_UNAVAILABLE",
        "read_only": True,
        "installation_performed": False,
        "source_read": False,
        "configured_project": workspace["project"],
        "probe_deadline_seconds": 15,
        "candidates": [],
        "selected": None,
    }
    if config.is_file():
        raw = config.read_bytes()
        require(len(raw) <= 8192, "Existing pyvenv metadata exceeds its bound")
        report["project_pyvenv_config"] = {
            "size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()
        }
        metadata = dict(
            (key.strip(), value.strip())
            for line in raw.decode("utf-8-sig").splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        )
        for key in ("executable", "home"):
            if metadata.get(key):
                candidate = Path(metadata[key])
                if candidate.is_absolute():
                    candidates.append((
                        "project_pyvenv_" + key,
                        candidate / "python.exe" if key == "home" else candidate,
                    ))
        require(config.read_bytes() == raw, "Existing pyvenv metadata changed")
    seen = set()
    # At most five metadata-addressed candidates, each with one bounded child.
    for origin, candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate))
        if key in seen:
            continue
        seen.add(key)
        row = {"origin": origin, "path": str(candidate), "status": "MISSING"}
        report["candidates"].append(row)
        if not candidate.is_absolute() or not candidate.is_file():
            continue
        try:
            before = {
                "size_bytes": candidate.stat().st_size, "sha256": digest(candidate)
            }
            child = subprocess.run(
                [str(candidate), "-I", "-B", str(Path(__file__).resolve()),
                 "--probe-decoder"],
                capture_output=True, timeout=15, check=False,
            )
            row["exit_code"] = child.returncode
            require(
                len(child.stdout) <= 65536 and len(child.stderr) <= 65536,
                "Existing interpreter probe output exceeds its bound",
            )
            probe = json.loads(child.stdout.decode("utf-8-sig"))
            row["probe"] = probe
            require(
                candidate.stat().st_size == before["size_bytes"]
                and digest(candidate) == before["sha256"],
                "Existing interpreter changed during its probe",
            )
            require(
                child.returncode == 0
                and probe.get("status") == "EXISTING_DECODER_READY"
                and probe.get("imports_verified") is True
                and probe.get("decoder_versions") == DECODER_VERSIONS
                and probe.get("python_version", [])[:2] == [3, 12]
                and probe.get("implementation") == "cpython"
                and probe.get("pointer_bits") == 64
                and Path(probe["executable"]).samefile(candidate)
                and probe.get("executable_identity") == before,
                "Existing interpreter has not qualified for the pinned decoder",
            )
            row["status"] = "QUALIFIED"
            report.update(
                status="EXISTING_DECODER_SELECTED",
                selected={"path": str(candidate), "origin": origin, **before},
            )
            break
        except subprocess.TimeoutExpired:
            # subprocess.run kills and waits for its own child on timeout.
            row.update(status="TIMED_OUT", error="Owned probe exceeded 15 seconds")
        except Exception as exc:  # noqa: BLE001
            row.update(status="UNAVAILABLE", error=f"{type(exc).__name__}: {exc}")
    return report


def _check_native_header(header, retained):
    crs = header.parse_crs()
    observed = {
        "points": header.point_count,
        "crs": crs.to_string() if crs else None,
        "version": str(header.version),
        "point_format": header.point_format.id,
        "bounds": [header.mins.tolist(), header.maxs.tolist()],
        "scales": header.scales.tolist(),
        "offsets": header.offsets.tolist(),
    }
    require(
        observed == {k: retained[k] for k in observed},
        "Current LAS header differs from retained evidence: " + retained["file"],
    )


def _export(paths, headers, frames, output, report, laspy, np):
    for path in paths:
        with laspy.open(path) as reader:
            _check_native_header(reader.header, headers[path.name])
    report["current_header_status"] = "PASS"
    selected = [p for p in paths if any(_overlaps(headers[p.name], f) for f in frames)]
    require(selected, "No authenticated LAS bounds overlap the source transects")
    report["selected_tiles"] = [p.name for p in selected]
    partial = output / "hairpin-lidar-points.partial.csv"
    row_count, counts = 0, {str(s): 0 for s in STATIONS_M}
    with partial.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CSV_FIELDS)
        for path in selected:
            offset = 0
            with laspy.open(path) as reader:
                _check_native_header(reader.header, headers[path.name])
                for points in reader.chunk_iterator(CHUNK_SIZE):
                    x, y, z = (np.asarray(getattr(points, k)) for k in ("x", "y", "z"))
                    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
                    events = []
                    for frame_index, frame in enumerate(frames):
                        dx, dy = (
                            x - frame["center_epsg25831_m"][0],
                            y - frame["center_epsg25831_m"][1],
                        )
                        along = (
                            dx * frame["along_unit"][0] + dy * frame["along_unit"][1]
                        )
                        lateral = (
                            dx * frame["lateral_unit"][0]
                            + dy * frame["lateral_unit"][1]
                        )
                        chosen = np.flatnonzero(
                            finite
                            & (abs(along) <= HALF_ALONG_M)
                            & (abs(lateral) <= HALF_LATERAL_M)
                        )
                        require(
                            row_count + len(events) + len(chosen) <= MAX_CSV_ROWS,
                            "Transect CSV bound exceeded; no truncation is admitted",
                        )
                        events.extend(
                            (int(i), frame_index, float(along[i]), float(lateral[i]))
                            for i in chosen
                        )
                    # Tile/index/station order is independent of decoder chunk boundaries.
                    for i, frame_index, along, lateral in sorted(events):
                        require(
                            stream.tell() < MAX_CSV_BYTES,
                            "Transect CSV byte bound exceeded",
                        )
                        frame = frames[frame_index]
                        flags = [int(getattr(points, k)[i]) for k in CSV_FIELDS[10:21]]
                        cls, withheld, synthetic, overlap = flags[:4]
                        accepted = not (
                            withheld or synthetic or overlap or cls in (7, 12, 18)
                        )
                        writer.writerow(
                            [
                                frame["source_station_m"],
                                frame["profile_section_index"],
                                path.name,
                                offset + i,
                                *[int(getattr(points, k)[i]) for k in ("X", "Y", "Z")],
                                float(x[i]),
                                float(y[i]),
                                float(z[i]),
                                *flags,
                                along,
                                lateral,
                                int(accepted),
                            ]
                        )
                        row_count += 1
                        counts[str(frame["source_station_m"])] += 1
                    offset += len(points)
            require(
                offset == headers[path.name]["points"],
                "Incomplete source tile decoding",
            )
    require(partial.stat().st_size <= MAX_CSV_BYTES, "Transect CSV byte bound exceeded")
    report["csv_rows"], report["rows_per_station"] = row_count, counts
    require(
        row_count > 0, "Decoded tiles contain no finite points in the source transects"
    )
    return partial


def read(cache_root, output):
    """Create one new evidence directory; inputs are only opened for reading."""
    cache_root, output = Path(cache_root).resolve(), Path(output).resolve()
    require(
        not output.is_relative_to(cache_root),
        "Evidence output cannot enter source cache",
    )
    output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema_version": 1,
        "status": "FAILED",
        "observations_available": False,
        "geometry_mutation": False,
        "profile_fit": False,
        "authoritative_physics": False,
        "real_road_profile_admitted": False,
        "csv_rows": 0,
        "retained_header_status": "NOT_RUN",
        "current_header_status": "NOT_RUN",
        "post_read_source_status": "NOT_RUN",
        "reader_sha256": digest(Path(__file__)),
        "python_executable": {
            "path": sys.executable,
            "size_bytes": Path(sys.executable).stat().st_size,
            "sha256": digest(Path(sys.executable)),
        },
        "python_version": sys.version,
        "parameters": {
            "source_stations_m": STATIONS_M,
            "half_along_m": HALF_ALONG_M,
            "half_lateral_m": HALF_LATERAL_M,
            "max_csv_rows": MAX_CSV_ROWS,
            "max_csv_bytes": MAX_CSV_BYTES,
            "chunk_size": CHUNK_SIZE,
        },
        "interpretation": "Original point observations, including excluded classes/flags; a transect may contain multiple surfaces. No nearest-road association or fitted profile.",
        "csv_row_identity": "Original tile + zero-based point index + source station; a point in multiple strips is retained separately, not counted as independent measurements.",
        "accepted_flag_basis": "Matches the predecessor's withheld/synthetic/overlap and class7/12/18 exclusion only; accepted does not mean asphalt or a measured road deck.",
        "height_basis": "Provider orthometric convention; independent vertical datum verification is not claimed. Frozen pavement equals source candidate ground plus 0.04 m.",
        "frame_basis": "Original source edge0-to-edge24 direction and its perpendicular, oriented by adjacent source centers; actual source keys, not cumulative center distance.",
        "attribution": "Obra derivada de LiDAR-PNOA-cob3 2022-2025 CC-BY 4.0 scne.es",
    }
    try:
        manifest_path = _safe(cache_root, LIDAR_RELATIVE)
        raw, manifest = _read(manifest_path, LIDAR_IDENTITY)
        (output / "source-lidar-manifest.json").write_bytes(raw)
        inputs, headers = _headers(manifest)
        report.update(
            retained_header_status="PASS",
            retained_headers=list(headers.values()),
            lidar_manifest_identity=LIDAR_IDENTITY,
            source_inputs=inputs,
        )
        profile_path = _safe(cache_root, PROFILE_RELATIVE)
        _, profile = _read(profile_path, PROFILE_IDENTITY)
        frames = transects(profile)
        report.update(profile_identity=PROFILE_IDENTITY, transects=frames)
        pinned = [
            (manifest_path, LIDAR_IDENTITY),
            (profile_path, PROFILE_IDENTITY),
            (output / "source-lidar-manifest.json", LIDAR_IDENTITY),
        ]
        paths = []
        for row in inputs:
            relative = Path(row["path"])
            require(
                relative.parts[:2] == ("sa-calobra-working-v1", "manual-cnig")
                and len(relative.parts) == 3,
                "Unexpected original LAZ source path",
            )
            path = _safe(cache_root, Path(*relative.parts[1:]))
            _match(path, row)
            paths.append(path)
            pinned.append((path, row))
        laspy, np = _decoder(report)
        partial = _export(paths, headers, frames, output, report, laspy, np)
        for path, identity in pinned:
            _match(path, identity)
        report["post_read_source_status"] = "PASS"
        final = output / "hairpin-lidar-points.csv"
        partial.rename(final)
        report.update(
            status="OBSERVATIONS_EXPORTED",
            observations_available=True,
            csv={
                "path": final.name,
                "size_bytes": final.stat().st_size,
                "sha256": digest(final),
            },
        )
    except Unavailable as exc:
        report.update(
            status="UNAVAILABLE", error=str(exc), error_type=type(exc).__name__
        )
    # Preserve the original decoder/provenance failure in this owned receipt.
    except Exception as exc:  # noqa: BLE001
        report.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
    partial = output / "hairpin-lidar-points.partial.csv"
    if partial.is_file():
        report["partial_csv_not_admitted"] = {
            "path": partial.name,
            "size_bytes": partial.stat().st_size,
            "sha256": digest(partial),
        }
    report_path = output / "hairpin-lidar.json"
    report_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", type=Path)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--output-name")
    operation.add_argument("--probe-decoder", action="store_true")
    operation.add_argument("--resolve-decoder", type=Path)
    args = parser.parse_args()
    if args.probe_decoder:
        report = decoder_environment()
        print(json.dumps(report, allow_nan=False))
        return 0 if report["status"] == "EXISTING_DECODER_READY" else 2
    require(args.workspace_config is not None, "Explicit workspace config required")
    workspace = load_workspace(args.workspace_config)
    if args.resolve_decoder:
        require(not args.resolve_decoder.exists(), "Decoder evidence already exists")
        report = resolve_existing_decoder(workspace)
        with args.resolve_decoder.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": report["status"], "selected": report["selected"]}))
        return 0 if report["selected"] is not None else 2
    require(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", args.output_name),
        "Output name must be one new workspace work directory",
    )
    cache = _safe(Path(workspace["data"]), "world-data/sa-calobra-working-v1")
    output = _safe(Path(workspace["work"]), args.output_name)
    report = read(cache, output)
    print(
        json.dumps(
            {k: report[k] for k in ("status", "observations_available", "csv_rows")}
        )
    )
    return {"OBSERVATIONS_EXPORTED": 0, "UNAVAILABLE": 2, "FAILED": 1}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
