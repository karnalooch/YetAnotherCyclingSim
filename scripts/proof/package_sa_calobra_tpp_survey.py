"""Validate captured Sa Calobra TPP evidence and build a portable review bundle.

The immutable survey.json and native PNGs remain primary evidence. Contact
sheets and thumbnails derive only from those PNGs. This sampled visual survey
does not simulate cycling, classify visible surfaces or measure runtime FPS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path

CONTRACT = "sa_calobra_bidirectional_tpp_survey_v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,120}\Z")
FRAME_PATH = re.compile(r"frames/[A-Za-z0-9_-]{1,120}\.png\Z")
READINESS_PATH = re.compile(r"readiness/[A-Za-z0-9_-]{1,120}/capture-readiness\.json\Z")
READY = "NATIVE_LOADING_AND_MIPS_READY"
REVIEW_TAGS = {
    "GEO_FIX": "Geometria wymaga naprawy; zapisz konkretny widoczny problem.",
    "SILHOUETTE_CRITICAL": "Kluczowy obrys krajobrazu; zachowaj czytelny kontur i duże formy.",
    "HERO_DETAIL": "Szczególnie eksponowane miejsce wymagające wysokiej jakości detalu.",
    "BACKGROUND_LOW_PRIORITY": "Tło będące kandydatem do uproszczenia po sprawdzeniu widoczności i innych dojazdów.",
    "MATERIAL_TEST_CANDIDATE": "Kandydat na pierwszy fragment do testów materiału.",
}
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.proof.sa_calobra_tpp_survey import (
    FROZEN_SHA,
    REPOSITORY_RECIPE,
    SurveyConfig,
)


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def vector(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must have three coordinates")
    for coordinate in value:
        finite(coordinate, name)


def checked_path(root, relative):
    if not isinstance(relative, str) or not FRAME_PATH.fullmatch(relative):
        raise ValueError("unsafe frame path")
    path = root / relative
    if any(part.is_symlink() for part in (path, path.parent)):
        raise ValueError("symlink frame path is not primary evidence")
    if root not in path.resolve().parents or not path.is_file():
        raise ValueError("missing or path-escaping frame")
    return path


def validate_readiness(root, frame):
    readiness = frame.get("native_readiness", {})
    if (
        not isinstance(readiness, dict)
        or readiness.get("status") != READY
        or readiness.get("full_height_mips_requested") is not True
    ):
        raise ValueError("frame captured without full native mip readiness")
    relative = readiness.get("receipt")
    if not isinstance(relative, str) or not READINESS_PATH.fullmatch(relative):
        raise ValueError("unsafe native readiness receipt path")
    if relative != f"readiness/{frame['frame_id']}/capture-readiness.json":
        raise ValueError("native readiness receipt belongs to a different frame")
    path = root / relative
    if root not in path.resolve().parents or not path.is_file():
        raise ValueError("missing or path-escaping native readiness receipt")
    if any(part.is_symlink() for part in (path, path.parent, path.parent.parent)):
        raise ValueError("symlink native readiness receipt")
    if path.stat().st_size > 2_000_000:
        raise ValueError("native readiness receipt exceeds bounded size")
    if (
        not SHA256.fullmatch(str(readiness.get("sha256", "")))
        or digest(path) != readiness["sha256"]
    ):
        raise ValueError("native readiness receipt SHA256 mismatch")
    full = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        full.get("status") != READY
        or full.get("height_mip_lease_requested") is not True
        or full.get("native_loading_barrier_completed") is not True
        or full.get("saved_to_map") is not False
        or full.get("height_edits_applied") is not False
    ):
        raise ValueError(
            "full native readiness receipt did not prove mip lease and loading"
        )
    textures = full.get("textures_after")
    if (
        not isinstance(textures, list)
        or not textures
        or readiness.get("height_texture_count") != len(textures)
    ):
        raise ValueError("native readiness texture inventory mismatch")
    for row in textures:
        if (
            not isinstance(row, dict)
            or row.get("is_default_texture") is not False
            or row.get("is_compiling") is not False
            or type(row.get("mips")) is not int
            or row["mips"] <= 0
            or row.get("resident_mips") != row["mips"]
        ):
            raise ValueError(
                "native readiness height texture mips are not fully resident"
            )


def pair_frames(frames):
    """Pair the same local window station, never global/physics chainage."""
    groups = {}
    for frame in frames:
        key = (frame["window_id"], frame["station_m"])
        pair = groups.setdefault(key, {})
        if frame["direction"] in pair:
            raise ValueError("duplicate window/station/direction frame")
        pair[frame["direction"]] = frame
    if any(set(pair) != {"forward", "reverse"} for pair in groups.values()):
        raise ValueError("missing forward/reverse station pair")
    return [
        (window, station, groups[(window, station)])
        for window, station in sorted(groups)
    ]


def validate_schedule(report, config):
    """Recompute sampling/order/rig geometry without rerunning a road producer."""
    windows = report.get("windows")
    if not isinstance(windows, list) or not windows:
        raise ValueError("missing survey window inventory")
    names = [row.get("window_id") for row in windows]
    if any(
        not isinstance(name, str) or not IDENTIFIER.fullmatch(name) for name in names
    ):
        raise ValueError("invalid survey window identity")
    if names != sorted(set(names)):
        raise ValueError("windows must be unique and ordered")
    prepared = []
    for window_index, window in enumerate(windows):
        length = finite(window.get("length_m"), "window length")
        if length <= 0:
            raise ValueError("window length must be positive")
        intervals = math.ceil(length / config.spacing_m)
        stations = [length * i / intervals for i in range(intervals)] + [length]
        if window.get("samples_per_direction") != len(stations):
            raise ValueError("window sample count does not match spacing")
        if window.get("connection_to_other_windows") != "UNVERIFIED":
            raise ValueError("survey cannot declare window continuity")
        for field in ("start_cm", "end_cm"):
            vector(window.get(field), field)
        prepared.append((window_index, window, stations))
    expected = []
    for direction in ("forward", "reverse"):
        for window_index, window, stations in (
            prepared if direction == "forward" else reversed(prepared)
        ):
            for sample_index, station in enumerate(
                stations if direction == "forward" else reversed(stations)
            ):
                expected.append(
                    (window_index, window, direction, sample_index, station)
                )
    if len(expected) != len(report["frames"]):
        raise ValueError("missing or excess schedule samples")
    for frame, (window_index, window, direction, sample_index, station) in zip(
        report["frames"], expected
    ):
        frame_id = f"window-{window_index:04d}-{direction}-{sample_index:05d}"
        checks = {
            "frame_id": frame_id,
            "file": f"frames/{frame_id}.png",
            "window_id": window["window_id"],
            "direction": direction,
            "sample_index": sample_index,
            "station_m": station,
            "distance_along_window_m": station,
            "travel_distance_m": station
            if direction == "forward"
            else window["length_m"] - station,
            "fov_deg": config.fov_deg,
            "sphere_radius_cm": config.sphere_radius_m * 100,
        }
        for key, value in checks.items():
            if frame.get(key) != value:
                raise ValueError(f"recomputed schedule mismatch: {key}")
        road, forward = frame["road_position_cm"], frame["road_forward_unit"]
        if abs(math.sqrt(sum(value * value for value in forward)) - 1) > 1e-8:
            raise ValueError("road forward must be a unit vector")
        ball = [
            road[i] + (config.sphere_radius_m * 100 if i == 2 else 0) for i in range(3)
        ]
        camera = [
            road[i]
            - config.trailing_m * 100 * forward[i]
            + (config.camera_height_m * 100 if i == 2 else 0)
            for i in range(3)
        ]
        target = [ball[i] + config.lookahead_m * 100 * forward[i] for i in range(3)]
        for key, coordinates in (
            ("ball_location_cm", ball),
            ("camera_location_cm", camera),
            ("target_cm", target),
        ):
            if any(abs(a - b) > 1e-5 for a, b in zip(frame[key], coordinates)):
                raise ValueError(f"recomputed TPP rig mismatch: {key}")
        endpoint = (
            window["start_cm"]
            if station == 0
            else (window["end_cm"] if station == window["length_m"] else None)
        )
        if endpoint is not None and road != endpoint:
            raise ValueError("window endpoint differs from captured road location")


def validate(root, expected_sha):
    """Fail before creating review output if a primary-evidence check fails."""
    from PIL import Image

    root = Path(root).resolve()
    if not isinstance(expected_sha, str) or not SHA40.fullmatch(expected_sha):
        raise ValueError("expected exact SHA must be lowercase SHA40")
    manifest = root / "survey.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError("survey.json must be a regular captured manifest")
    if manifest.stat().st_size > 20_000_000:
        raise ValueError("survey manifest exceeds bounded size")
    report = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if report.get("schema_version") != 1 or report.get("contract") != CONTRACT:
        raise ValueError("unsupported survey contract")
    if report.get("exact_sha") != expected_sha:
        raise ValueError("survey exact SHA mismatch")
    if report.get("status") != "CAPTURED" or report.get("error") is not None:
        raise ValueError("survey capture did not complete")
    if report.get("cleanup", {}).get("status") != "RESTORED":
        raise ValueError("survey transient scene cleanup is unverified")
    if report.get("performance_acceptance") != "NOT_MEASURED":
        raise ValueError("sampled survey cannot claim performance acceptance")
    if report.get("visual_acceptance") != "PENDING_REVIEW":
        raise ValueError("package cannot grant visual acceptance")
    for key, expected in (
        ("saved_to_map", False),
        ("physical_simulation", False),
        ("presentation_only", True),
        ("physics_playback", False),
        ("continuous_route", False),
        ("camera_collision_adjusted", False),
        ("route_or_terrain_modified", False),
    ):
        if report.get(key) is not expected:
            raise ValueError(f"survey presentation boundary mismatch: {key}")
    config_data = report.get("config")
    if (
        not isinstance(config_data, dict)
        or config_data.get("exact_sha") != expected_sha
    ):
        raise ValueError("survey config exact SHA mismatch")
    config = SurveyConfig(**config_data)
    if (
        not isinstance(report.get("source_identity"), dict)
        or not report["source_identity"]
    ):
        raise ValueError("missing route source identity")
    identity = report["source_identity"]
    if identity.get("accepted_road_sha") != FROZEN_SHA or identity.get(
        "recipe_sha256"
    ) != digest(REPOSITORY_RECIPE):
        raise ValueError("frozen route source identity mismatch")
    recipe = json.loads(REPOSITORY_RECIPE.read_text(encoding="utf-8-sig"))
    if (
        identity.get("verified_input_count") != len(recipe["inputs"])
        or identity.get("source_run_id") != recipe["source_run_id"]
    ):
        raise ValueError("frozen source verification inventory mismatch")
    if identity.get("geometry_consumers_executed") is not False:
        raise ValueError("survey must not regenerate frozen road geometry")
    scene = report.get("source_scene")
    if not isinstance(scene, dict):
        raise TypeError("missing source scene provenance")
    for key in ("map", "cliff_recipe", "component", "scope", "material_path"):
        if not isinstance(scene.get(key), str) or not scene[key].strip():
            raise ValueError(f"missing source scene provenance: {key}")
    if not SHA256.fullmatch(str(scene.get("map_sha256", ""))):
        raise ValueError("missing source map SHA256")
    if not SHA40.fullmatch(str(scene.get("accepted_cliff_implementation_sha", ""))):
        raise ValueError("missing accepted cliff implementation SHA40")
    planned = report.get("planned_frames")
    frames = report.get("frames")
    if not isinstance(planned, list) or not isinstance(frames, list):
        raise TypeError("planned_frames and frames must be lists")
    count = report.get("frame_count")
    if type(count) is not int or not 0 < count <= config.max_frames:
        raise ValueError("invalid bounded frame_count")
    if len(planned) != count or len(frames) != count:
        raise ValueError("missing or excess planned/captured frames")
    seen_ids, seen_files = set(), set()
    for index, (frame, plan) in enumerate(zip(frames, planned)):
        if not isinstance(frame, dict) or not isinstance(plan, dict):
            raise TypeError("invalid frame record")
        for key, value in plan.items():
            if key not in frame or frame[key] != value:
                raise ValueError(f"captured frame plan mismatch: {key}")
        for key in ("frame_id", "window_id"):
            if not isinstance(frame.get(key), str) or not IDENTIFIER.fullmatch(
                frame[key]
            ):
                raise ValueError(f"invalid {key}")
        if frame.get("index") != index or type(frame.get("index")) is not int:
            raise ValueError("frame indices must be complete and ordered")
        if frame["frame_id"] in seen_ids or frame.get("file") in seen_files:
            raise ValueError("duplicate frame ID or screenshot path")
        seen_ids.add(frame["frame_id"])
        seen_files.add(frame.get("file"))
        if frame.get("direction") not in {"forward", "reverse"}:
            raise ValueError("invalid survey direction")
        if finite(frame.get("station_m"), "station_m") < 0:
            raise ValueError("negative local station")
        for key in (
            "road_position_cm",
            "camera_location_cm",
            "target_cm",
            "ball_location_cm",
            "road_forward_unit",
        ):
            vector(frame.get(key), key)
        validate_readiness(root, frame)
        width, height = frame.get("width_px"), frame.get("height_px")
        if (
            type(width) is not int
            or type(height) is not int
            or not (0 < width <= 4096 and 0 < height <= 2160)
        ):
            raise ValueError("invalid bounded PNG dimensions")
        size = frame.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise ValueError("invalid PNG byte count")
        path = checked_path(root, frame.get("file"))
        if path.stat().st_size != size:
            raise ValueError("PNG byte count mismatch")
        if (
            not SHA256.fullmatch(str(frame.get("sha256", "")))
            or digest(path) != frame["sha256"]
        ):
            raise ValueError("PNG SHA256 mismatch")
        try:
            with Image.open(path) as image:
                if image.format != "PNG" or image.size != (width, height):
                    raise ValueError("PNG format/dimensions mismatch")
                image.verify()
            with Image.open(path) as image:
                image.load()
        except (OSError, SyntaxError) as error:
            raise ValueError(f"PNG decode failed: {frame['file']}") from error
    actual = {
        p.relative_to(root).as_posix()
        for p in (root / "frames").rglob("*")
        if p.suffix.lower() == ".png"
    }
    if actual != seen_files:
        raise ValueError("stale or untracked screenshots in evidence folder")
    validate_schedule(report, config)
    if (
        type(identity.get("network_window_count")) is not int
        or identity["network_window_count"] < 1
        or identity.get("checkpoint_hairpin_count") != 1
        or identity["network_window_count"] + identity["checkpoint_hairpin_count"]
        != len(report["windows"])
    ):
        raise ValueError("frozen source window inventory differs from survey")
    pairs = pair_frames(frames)
    for _, _, pair in pairs:
        if pair["forward"]["road_position_cm"] != pair["reverse"]["road_position_cm"]:
            raise ValueError("forward/reverse road station positions differ")
        if any(
            abs(a + b) > 1e-8
            for a, b in zip(
                pair["forward"]["road_forward_unit"],
                pair["reverse"]["road_forward_unit"],
            )
        ):
            raise ValueError("forward/reverse camera tangent directions differ")
    return report, pairs


def route_svg(report):
    """World XY sketch; camera offsets and disconnected windows stay explicit."""
    frames = report["frames"]
    positions = [
        f[key] for f in frames for key in ("road_position_cm", "camera_location_cm")
    ]
    minx, miny = min(p[0] for p in positions), min(p[1] for p in positions)
    maxx, maxy = max(p[0] for p in positions), max(p[1] for p in positions)
    scale = min(860 / max(maxx - minx, 1), 460 / max(maxy - miny, 1))

    def point(position):
        return (50 + (position[0] - minx) * scale, 530 - (position[1] - miny) * scale)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600">',
        '<rect width="960" height="600" fill="#101827"/>',
        '<g font-family="sans-serif" font-size="14" fill="white">',
        '<text x="20" y="24">World XY • road grey • forward camera blue • reverse camera orange</text>',
        '<text x="20" y="46">Local stations per window; dashed magenta = jump, no connecting road proved</text>',
    ]
    windows = {}
    for frame in frames:
        windows.setdefault(frame["window_id"], []).append(frame)
    previous = None
    for window, rows in windows.items():
        forward = sorted(
            (r for r in rows if r["direction"] == "forward"),
            key=lambda r: r["station_m"],
        )
        reverse = sorted(
            (r for r in rows if r["direction"] == "reverse"),
            key=lambda r: r["station_m"],
            reverse=True,
        )
        for track, key, color in (
            (forward, "road_position_cm", "#a4adb9"),
            (forward, "camera_location_cm", "#39a5ff"),
            (reverse, "camera_location_cm", "#ffb454"),
        ):
            points = " ".join(
                f"{point(row[key])[0]:.2f},{point(row[key])[1]:.2f}" for row in track
            )
            parts.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>'
            )
            # Start marker makes travel direction legible even when paths overlap.
            x, y = point(track[0][key])
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"/>')
        first = point(forward[0]["road_position_cm"])
        if previous is not None:
            parts.append(
                f'<line x1="{previous[0]:.2f}" y1="{previous[1]:.2f}" x2="{first[0]:.2f}" y2="{first[1]:.2f}" stroke="#ea71c7" stroke-dasharray="5 6"/>'
            )
        previous = point(forward[-1]["road_position_cm"])
        parts.append(
            f'<text x="{first[0] + 6:.2f}" y="{first[1] - 8:.2f}">{html.escape(window)}</text>'
        )
    parts.append(
        '</g><text x="20" y="580" fill="white" font-family="sans-serif">Schematic from captured world coordinates; not GIS or a route coverage certificate.</text></svg>'
    )
    return "\n".join(parts)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def package(root, expected_sha):
    from PIL import Image, ImageDraw

    root = Path(root).resolve()
    report, pairs = validate(root, expected_sha)
    output = root / "review"
    # Human review notes are never silently overwritten by another packaging run.
    if output.exists() or output.is_symlink():
        raise ValueError(
            "review output already exists; retain it and choose fresh evidence directory"
        )
    output.mkdir()
    thumbnails = output / "thumbnails"
    thumbnails.mkdir()
    for frame in report["frames"]:
        with Image.open(root / frame["file"]) as source:
            thumbnail = source.convert("RGB")
            thumbnail.thumbnail((640, 360))
            thumbnail.save(thumbnails / f"{frame['frame_id']}.jpg", quality=88)
    cells, sheets = [], []
    for window, station, pair in pairs:
        cards = []
        for direction in ("forward", "reverse"):
            frame = pair[direction]
            cards.append(
                f'<td><a href="../{frame["file"]}"><img loading="lazy" src="thumbnails/{frame["frame_id"]}.jpg" alt="{frame["frame_id"]}"></a><br>{direction} · {frame["frame_id"]}<br>Native readiness verified · visual UNREVIEWED</td>'
            )
        cells.append(
            f'<tr id="{window}-{station:g}"><th>{window}<br>local {station:.2f} m</th>{"".join(cards)}</tr>'
        )
    # Each contact-sheet cell links to the full original through an HTML image map.
    for page, start in enumerate(range(0, len(pairs), 12)):
        selected = pairs[start : start + 12]
        sheet = Image.new("RGB", (1280, len(selected) * 210), "#101827")
        draw = ImageDraw.Draw(sheet)
        page_areas = []
        for row_index, (window, station, pair) in enumerate(selected):
            for column, direction in enumerate(("forward", "reverse")):
                frame = pair[direction]
                x, y = column * 640, row_index * 210
                with Image.open(root / frame["file"]) as source:
                    image = source.convert("RGB")
                    image.thumbnail((632, 176))
                    sheet.paste(image, (x + 4, y + 4))
                draw.text(
                    (x + 4, y + 182),
                    f"{window} local {station:.2f}m {direction} | UNREVIEWED",
                    fill="white",
                )
                page_areas.append(
                    f'<area shape="rect" coords="{x},{y},{x + 640},{y + 210}" href="../{frame["file"]}" alt="{frame["frame_id"]}">'
                )
        filename = f"contact-{page:03d}.jpg"
        sheet.save(output / filename, quality=90)
        sheets.append(
            f'<p><a href="{filename}">Contact sheet {page + 1}</a> · clickable cells open native PNG</p><div class="contact-wrap"><img class="contact" src="{filename}" usemap="#sheet-{page}" alt="Forward and reverse station pairs"><map name="sheet-{page}">{"".join(page_areas)}</map></div>'
        )
    (output / "route.svg").write_text(route_svg(report), encoding="utf-8")
    csv_rows = []
    for frame in report["frames"]:
        row = dict(frame)
        row["native_readiness_status"] = frame["native_readiness"]["status"]
        row["visual_review_status"] = "UNREVIEWED"
        for field in (
            "road_position_cm",
            "camera_location_cm",
            "target_cm",
            "ball_location_cm",
        ):
            row[field] = json.dumps(frame[field], separators=(",", ":"))
        csv_rows.append(row)
    write_csv(
        output / "frames.csv",
        csv_rows,
        (
            "frame_id",
            "index",
            "window_id",
            "direction",
            "station_m",
            "travel_distance_m",
            "road_position_cm",
            "camera_location_cm",
            "target_cm",
            "ball_location_cm",
            "fov_deg",
            "width_px",
            "height_px",
            "size_bytes",
            "sha256",
            "file",
            "native_readiness_status",
            "visual_review_status",
        ),
    )
    review_rows = [
        {
            "window_id": w,
            "local_station_m": s,
            "forward_frame": p["forward"]["file"],
            "reverse_frame": p["reverse"]["file"],
            "review_status": "UNREVIEWED",
            "surface_priority": "UNASSIGNED",
        }
        for w, s, p in pairs
    ]
    write_csv(
        output / "surface-review-template.csv",
        review_rows,
        (
            "window_id",
            "local_station_m",
            "forward_frame",
            "reverse_frame",
            "review_status",
            "surface_id",
            "surface_priority",
            "review_tags",
            "evidence_reason",
            "evidence_frame",
            "screen_fraction",
            "visible_duration_s",
            "silhouette_issue",
            "geometry_issue",
            "material_issue",
            "natural_boundary",
            "other_access_route",
            "reviewer",
            "notes",
        ),
    )
    (output / "review-guide.txt").write_text(
        "PRZEGLĄD POWIERZCHNI — MATERIAŁ DO OCENY\n"
        "Otwórz index.html i porównaj oba kierunki w tej samej LOKALNEJ stacji danego okna drogi.\n"
        "Każdej ciągłej ścianie/powierzchni nadaj stały surface_id i zapisz naturalne granice.\n"
        "surface_priority jest opcjonalne: close_view (blisko), panorama lub background (tło). Jest niezależne od review_tags.\n"
        "review_tags może zawierać wiele etykiet dla tego samego surface_id, rozdzielonych średnikiem: GEO_FIX;SILHOUETTE_CRITICAL.\n"
        "Każda adnotacja człowieka wymaga evidence_reason (konkretne uzasadnienie) i evidence_frame (ścieżka do oryginalnego PNG z frames.csv).\n"
        "Wpisz surface_id, aby powiązać adnotację z ciągłą powierzchnią; kolejne wiersze mogą odnosić się do tej samej powierzchni.\n"
        "Etykiety pozostają puste przed oceną człowieka; nie są wzajemnie wykluczające i nie uruchamiają zmian geometrii.\n"
        + "".join(f"{tag}: {definition}\n" for tag, definition in REVIEW_TAGS.items())
        + "Zapisz udział w ekranie, kierunki oglądania, problemy obrysu/geometrii/materiału i inne dojazdy.\n"
        "Czasu widoczności nie można zmierzyć z rzadkich próbek; pozostaw visible_duration_s puste bez osobnej obserwacji.\n"
        "Stacja określa pozycję kamery, nie granicę ściany. Jedna ściana może wymagać wielu wierszy.\n"
        "Nieznany dostęp i zasłonięcie pozostają nieznane. Przegląd nie obejmuje niezarejestrowanej sieci dróg.\n"
        "Zaakceptowany wygląd klifów jest punktem wyjścia. Propozycje z przeglądu nie zmieniają tej akceptacji.\n"
        "Contact sheets/JPEG służą do nawigacji; ostateczna ocena korzysta z oryginalnych PNG.\n"
        "Pakiet nie zawiera pomiaru wydajności ani automatycznej akceptacji wyglądu.\n",
        encoding="utf-8",
    )
    scene = html.escape(json.dumps(report["source_scene"], indent=2))
    identity = html.escape(json.dumps(report["source_identity"], indent=2))
    groups = {}
    for frame in report["frames"]:
        groups.setdefault(f"{frame['window_id']} / {frame['direction']}", []).append(
            {
                "src": f"../{frame['file']}",
                "label": f"{frame['frame_id']} · local {frame['station_m']:.2f} m",
            }
        )
    options = "".join(f"<option>{html.escape(key)}</option>" for key in groups)
    slideshow_data = json.dumps(groups).replace("<", "\\u003c")
    tag_legend = "".join(
        f"<dt><code>{tag}</code></dt><dd>{html.escape(definition)}</dd>"
        for tag, definition in REVIEW_TAGS.items()
    )
    document = f"""<!doctype html><html lang="pl"><meta charset="utf-8"><title>Sa Calobra — sampled TPP survey</title>
<style>body{{font:16px system-ui;background:#101827;color:#e4edf8;margin:24px}}a{{color:#65b8ff}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #344356;padding:8px}}td{{width:44%}}td img{{width:100%;height:auto}}pre{{white-space:pre-wrap}}.sheet{{max-width:100%}}.contact-wrap{{overflow:auto}}.contact{{width:1280px;max-width:none}}#slide{{max-width:960px;width:100%}}button,select{{padding:8px;margin:4px}}details{{margin:12px 0}}</style>
<h1>Sa Calobra: TPP w obu kierunkach</h1><p>Próbkowany przegląd zatwierdzonej sceny z kulką. Pełne PNG i <a href="../survey.json">survey.json</a> są źródłem dowodów. Stan: technicznie zweryfikowany; ocena powierzchni UNREVIEWED; wydajność NOT_MEASURED.</p>
<p>SHA: <code>{expected_sha}</code> · klatki: {len(report["frames"])} · pary: {len(pairs)}. Metry oznaczają lokalną odległość w danym oknie drogi; nie są kilometrażem fizyki ani pełnej trasy. Okna są rozłączne; przeskoki nie dowodzą ciągłego przejazdu.</p>
<p><a href="frames.csv">Indeks klatek CSV</a> · <a href="surface-review-template.csv">Szablon oceny powierzchni</a> · <a href="review-guide.txt">Zasady oceny</a> · <a href="package-verification.json">Weryfikacja pakietu</a></p>
<h2>Etykiety przeglądu powierzchni</h2><dl>{tag_legend}</dl><p>Po obejrzeniu oryginalnych PNG wpisz stały <code>surface_id</code> i jedną lub wiele etykiet w <code>review_tags</code>, rozdzielonych średnikiem, np. <code>GEO_FIX;SILHOUETTE_CRITICAL</code>. Etykiety nie wykluczają się. Każda adnotacja człowieka wymaga <code>evidence_reason</code> (konkretnego uzasadnienia) i <code>evidence_frame</code> (ścieżki do oryginalnego PNG z indeksu). Opcjonalne <code>surface_priority</code> opisuje osobno bliski widok, panoramę lub tło.</p><p>Szablon pozostawia etykiety puste do oceny człowieka. Zaakceptowana geometria i wygląd są punktem wyjścia; etykiety nie uruchamiają automatycznych zmian.</p>
<details><summary>Pochodzenie zaakceptowanej sceny i drogi</summary><pre>{scene}</pre><pre>{identity}</pre></details>
<p><img class="sheet" src="route.svg" alt="World XY; direction cameras and explicitly disconnected windows"></p>
<h2>Kolejne ujęcia jednego okna</h2><p>Pokaz próbek, 750 ms na ujęcie. To tempo przeglądarki, bez deklaracji czasu jazdy ani FPS. Zmiana okna jest przeskokiem.</p>
<select id="track">{options}</select><button id="prev">Poprzednie</button><button id="play">Odtwarzaj próbki</button><button id="next">Następne</button><p id="label"></p><a id="original"><img id="slide" alt="Native captured survey frame"></a>
<h2>Porównanie: forward / reverse</h2><p>Kliknij ujęcie, aby otworzyć pełną klatkę. Etykiety powierzchni pozostają nieprzypisane do czasu przeglądu.</p><table><thead><tr><th>Okno / lokalna stacja</th><th>Forward</th><th>Reverse</th></tr></thead><tbody>{"".join(cells)}</tbody></table>
<h2>Contact sheets</h2>{"".join(sheets)}
<script>const tracks={slideshow_data};let idx=0,timer=null;const track=document.getElementById('track');function show(){{const rows=tracks[track.value];idx=(idx+rows.length)%rows.length;document.getElementById('slide').src=rows[idx].src;document.getElementById('original').href=rows[idx].src;document.getElementById('label').textContent=rows[idx].label+' ('+(idx+1)+'/'+rows.length+')';}}function stop(){{clearInterval(timer);timer=null;document.getElementById('play').textContent='Odtwarzaj próbki';}}document.getElementById('play').onclick=()=>{{if(timer)stop();else{{document.getElementById('play').textContent='Pauza';timer=setInterval(()=>{{idx++;if(idx>=tracks[track.value].length){{idx--;stop();}}show();}},750);}}}};track.onchange=()=>{{stop();idx=0;show();}};document.getElementById('prev').onclick=()=>{{stop();idx--;show();}};document.getElementById('next').onclick=()=>{{stop();idx++;show();}};show();</script></html>"""
    (output / "index.html").write_text(document, encoding="utf-8")
    receipt = {
        "schema_version": 1,
        "contract": CONTRACT,
        "exact_sha": expected_sha,
        "technical_status": "VALIDATED",
        "visual_acceptance": "PENDING_REVIEW",
        "performance_acceptance": "NOT_MEASURED",
        "frame_count": len(report["frames"]),
        "pair_count": len(pairs),
        "survey_sha256": digest(root / "survey.json"),
        "source_scene": report["source_scene"],
        "source_identity": report["source_identity"],
        "primary_frames": [
            {
                key: frame[key]
                for key in (
                    "frame_id",
                    "file",
                    "sha256",
                    "size_bytes",
                    "width_px",
                    "height_px",
                )
            }
            for frame in report["frames"]
        ],
        "primary_readiness": [
            {
                "file": frame["native_readiness"]["receipt"],
                "sha256": frame["native_readiness"]["sha256"],
                "size_bytes": (root / frame["native_readiness"]["receipt"])
                .stat()
                .st_size,
            }
            for frame in report["frames"]
        ],
        "derived_files": [],
    }
    for path in sorted(output.rglob("*")):
        if path.is_file():
            receipt["derived_files"].append(
                {
                    "file": path.relative_to(output).as_posix(),
                    "sha256": digest(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    (output / "package-verification.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        report, pairs = validate(args.root, args.expected_sha)
        print(
            f"Survey evidence VALIDATED: {len(report['frames'])} frames, {len(pairs)} pairs; visual PENDING_REVIEW; performance NOT_MEASURED"
        )
    else:
        receipt = package(args.root, args.expected_sha)
        print(
            f"Survey package VALIDATED: {receipt['frame_count']} frames; open {args.root.resolve() / 'review/index.html'}"
        )


if __name__ == "__main__":
    main()
