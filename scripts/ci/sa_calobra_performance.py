"""Prepare fixed cameras and evaluate Sa Calobra using the shared proof policy."""

from __future__ import annotations
import argparse
import array
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ci.world_proof_gate import BUDGET_MS, validate_evidence

CONSUMER_SCENARIO = "sa-calobra-material"
CONSUMER_MAP = (
    "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview"
)
CANONICAL_MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
CANONICAL_MAP_SHA256 = (
    "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
)
MATERIAL_PARENT = (
    "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/M_SaCalobraWholeMapPreparation"
)
MATERIAL_INSTANCE = MATERIAL_PARENT.replace("/M_SaCalobra", "/MI_SaCalobra")
CONSUMER_SECTORS = [
    *(f"ground-{row}-{col}" for row in range(3) for col in range(3)),
    "overview-north",
    "overview-south",
    "traversal",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_file(repo, entry):
    """Keep the measured consumer inside the isolated Content checkout."""
    relative = Path(entry["path"])
    path = (repo / relative).resolve()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not path.is_relative_to((repo / "Content").resolve())
        or path.suffix not in {".umap", ".uasset", ".uexp", ".ubulk", ".uptnl"}
        or not re.fullmatch(r"[0-9a-f]{64}", entry.get("sha256", ""))
        or digest(path) != entry["sha256"]
        or path.stat().st_size != entry.get("size_bytes")
    ):
        raise ValueError("Saved consumer asset identity differs")
    return path


def restore_consumer(manifest_path, head, repo=ROOT):
    """Use the existing no-overwrite checkpoint restorer for retained packages."""
    from scripts.assets.restore_workspace_data import restore

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("exact_sha") != head or manifest.get("map_package") != CONSUMER_MAP:
        raise ValueError("Cannot restore a stale or different material consumer")
    generated = [entry for entry in manifest.get("assets", []) if "storage" in entry]
    prefix = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/"
    if not generated or any(
        not entry["path"].startswith(prefix) for entry in generated
    ):
        raise ValueError(
            "Retained consumer packages exceed the generated output boundary"
        )
    result = restore(
        {"schema_version": 1, "files": generated},
        manifest_path.parent,
        repo,
        apply=True,
    )
    consumer_inputs(manifest_path, head, repo)
    return result


def consumer_inputs(manifest_path, head, repo=ROOT):
    """Validate saved data and its fresh rendered witness before/after timing."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("schema_version") != 1
        or manifest.get("exact_sha") != head
        or manifest.get("map_package") != CONSUMER_MAP
        or manifest.get("component_count") != 1024
        or not re.fullmatch(r"[0-9a-f]{40}", head or "")
        or manifest.get("canonical_map_package") != CANONICAL_MAP
        or manifest.get("canonical_map_sha256") != CANONICAL_MAP_SHA256
        or manifest.get("terrain_sha256") != CANONICAL_MAP_SHA256
        or manifest.get("terrain_identity_kind") != "immutable_canonical_accepted_map"
        or manifest.get("geometry_mutation") is not False
        or not re.fullmatch(
            r"[0-9a-f]{64}", manifest.get("geometry_snapshot_sha256", "")
        )
        or not re.fullmatch(r"[0-9a-f]{64}", manifest.get("material_recipe_sha256", ""))
        or manifest.get("expected_material_parent") != MATERIAL_PARENT
        or manifest.get("expected_material_instance") != MATERIAL_INSTANCE
    ):
        raise ValueError("Saved material consumer contract differs")
    assets = manifest.get("assets", [])
    if not assets or len({a["path"] for a in assets}) != len(assets):
        raise ValueError("Saved consumer asset inventory missing or duplicated")
    for entry in assets:
        checked_file(repo, entry)
    expected_map = "Content/" + CONSUMER_MAP.removeprefix("/Game/") + ".umap"
    maps = [a for a in assets if a["path"] == expected_map]
    parent = manifest["expected_material_parent"].split(".")[0]
    expected_parent = "Content/" + parent.removeprefix("/Game/") + ".uasset"
    instance = manifest.get("expected_material_instance", "").split(".")[0]
    expected_instance = "Content/" + instance.removeprefix("/Game/") + ".uasset"
    if (
        len(maps) != 1
        or maps[0]["sha256"] != manifest.get("map_sha256")
        or expected_parent not in {a["path"] for a in assets}
        or expected_instance not in {a["path"] for a in assets}
    ):
        raise ValueError("Saved map or material is absent from the pinned inventory")
    fresh = manifest.get("fresh_render_receipt", {})
    receipt_path = (manifest_path.parent / fresh.get("path", "")).resolve()
    if (
        not receipt_path.is_relative_to(manifest_path.parent.resolve())
        or not receipt_path.is_file()
        or digest(receipt_path) != fresh.get("sha256")
    ):
        raise ValueError("Fresh rendered consumer receipt missing or changed")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    if (
        receipt.get("status") != "SAVED_MATERIAL_CONSUMER_RENDERED"
        or receipt.get("exact_sha") != head
        or receipt.get("map_sha256") != manifest["map_sha256"]
        or receipt.get("expected_material_parent") != parent
        or receipt.get("component_count") != 1024
        or receipt.get("fresh_process") is not True
        or receipt.get("material_reapplied") is not False
        or receipt.get("saved_assets_unchanged") is not True
        or receipt.get("capture_settings_restored") is not True
    ):
        raise ValueError("Fresh render does not witness the measured saved consumer")
    # The producer decodes these native frames; require their retained bytes,
    # rather than admitting a green receipt whose witnesses disappeared.
    from PIL import Image
    from scripts.assets.restore_workspace_data import safe_path

    frames = receipt.get("frames", [])
    if (
        receipt.get("frame_count") != 11
        or len(frames) != 11
        or [frame.get("name") for frame in frames] != CONSUMER_SECTORS[:-1]
        or len({frame.get("path") for frame in frames}) != 11
    ):
        raise ValueError("Fresh rendered consumer view inventory differs")
    for frame in frames:
        path = safe_path(manifest_path.parent, frame["path"])
        if (
            path.suffix != ".png"
            or digest(path) != frame.get("sha256")
            or path.stat().st_size != frame.get("size_bytes")
        ):
            raise ValueError("Fresh rendered consumer frame missing or changed")
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != (1920, 1080):
                raise ValueError("Fresh rendered consumer frame dimensions differ")
            image.load()
    return manifest


def prepare_consumer(root, manifest_path, head, repo=ROOT):
    manifest = consumer_inputs(manifest_path, head, repo)
    views = [
        *manifest.get("performance_views", []),
        {"name": "traversal", "path": manifest.get("traversal", [])},
    ]
    if (
        len(views) != len(CONSUMER_SECTORS)
        or [v["name"] for v in views] != CONSUMER_SECTORS
    ):
        raise ValueError("Whole-Landscape performance views/traversal are incomplete")
    for view in views:
        poses = view.get("path", []) if view["name"] == "traversal" else [view]
        if not poses or (view["name"] == "traversal" and len(poses) < 3):
            raise ValueError("Source-bound traversal requires at least three poses")
        for pose in poses:
            if (
                not isinstance(pose.get("fov_deg"), (int, float))
                or not 1 <= pose["fov_deg"] < 180
            ):
                raise ValueError("Source-bound camera FOV missing or invalid")
            for key in ("location_cm", "target_cm"):
                values = pose.get(key, [])
                if len(values) != 3 or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    for v in values
                ):
                    raise ValueError("Performance camera pose is invalid")
            x, y, _ = pose["target_cm"]
            if not (0 <= x <= 201600 and 0 <= y <= 201600):
                raise ValueError("Performance target is outside the working Landscape")
        if view["name"].startswith("ground-"):
            _, row, col = view["name"].split("-")
            x, y, _ = view["target_cm"]
            # Existing native capture indexes X first, then Y; retain its IDs.
            if not (
                int(row) * 67200 <= x <= (int(row) + 1) * 67200
                and int(col) * 67200 <= y <= (int(col) + 1) * 67200
            ):
                raise ValueError("Ground view does not cover its declared area sector")
    settings = {
        "scenario_id": CONSUMER_SCENARIO,
        "exact_sha": head,
        "map_package": CONSUMER_MAP,
        "map_sha256": manifest["map_sha256"],
        "terrain_sha256": manifest["terrain_sha256"],
        "consumer_manifest_sha256": digest(manifest_path),
        "expected_material_parent": manifest["expected_material_parent"].split(".")[0],
        "expected_material_instance": manifest["expected_material_instance"].split(".")[
            0
        ],
        "resolution": [1920, 1080],
        "screen_percentage": 100,
        "dynamic_resolution": False,
        "vsync": False,
        "fov_deg": 74,
        "warmup_seconds": 5,
        "sample_seconds": 8,
        "traversal_sample_seconds": 30,
        "traversal_scope": "Camera-only path above the native Landscape maximum bounds; no riding/physics claim",
        "lighting_preserved": True,
        "views": views,
    }
    (root / "sa-calobra-settings.json").write_text(
        json.dumps(settings, sort_keys=True) + "\n"
    )
    return settings


def prepare(root: Path):
    manifest = json.loads((root / "Prepared/terrain-import.json").read_text())
    values = array.array("H")
    values.frombytes((root / "Prepared/terrain.r16").read_bytes())
    if sys.byteorder != "little":
        values.byteswap()

    def point(x, y, lift=170):
        i, j = round(x / 50), round(y / 50)
        if not (0 <= i < 4033 and 0 <= j < 4033):
            raise ValueError("Camera outside terrain")
        z = (values[j * 4033 + i] - 32768) * manifest["scale_z"] / 128 + manifest[
            "location_z_cm"
        ]
        return [x, y, z + lift]

    settings = {
        "resolution": [1920, 1080],
        "vsync": False,
        "screen_percentage": 100,
        "dynamic_resolution": False,
        "fov_deg": 74,
        "warmup_seconds": 5,
        "sample_seconds": 8,
        "shadows": False,
        "sun_intensity": 8,
        "sky_intensity": 0.8,
        "scope": "terrain baseline only; no road, foliage, earthworks or gameplay",
        "views": [
            {
                "name": "overview",
                "location_cm": [
                    -35000,
                    100800,
                    manifest["elevation_max_m"] * 100 + 90000,
                ],
                "target_cm": point(100800, 100800, 0),
            },
            {
                "name": "rider",
                "location_cm": point(125000, 85000),
                "target_cm": point(127000, 87000),
            },
            {
                "name": "slope",
                "location_cm": point(105000, 56000, 15000),
                "target_cm": point(108000, 58500, 0),
            },
        ],
    }
    (root / "sa-calobra-settings.json").write_text(
        json.dumps(settings, sort_keys=True) + "\n"
    )


def evaluate(root: Path, head: str, exit_code: int):
    settings = json.loads((root / "sa-calobra-settings.json").read_text())
    consumer = settings.get("scenario_id") == CONSUMER_SCENARIO
    scenario = CONSUMER_SCENARIO if consumer else "sa-calobra-terrain"
    csv_path = root / "sa-calobra-terrain-performance.csv"
    text = csv_path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    identity = json.loads(
        Path(str(csv_path) + ".identity.json").read_text(encoding="utf-8-sig")
    )
    manifest = (
        settings
        if consumer
        else json.loads((root / "Prepared/terrain-import.json").read_text())
    )
    summary = {
        "Head": head,
        "Result": "PASS",
        "EditorExitCode": exit_code,
        "Resolution": identity["Resolution"],
        "VSync": "disabled",
        "ReferenceGpuMatched": True,
        "GpuNames": [identity["ActiveGpu"]],
        "TargetFps": 60,
        "AllowedOverBudgetRatio": 0.05,
        "FrameBudgetMs": BUDGET_MS,
        "P95FrameBudgetMs": BUDGET_MS,
        "P95GpuBudgetMs": BUDGET_MS,
        "ScenarioId": scenario,
        "MapPackage": identity["MapPackage"],
        "ComponentCount": identity["ComponentCount"],
        "TerrainSha256": manifest["terrain_sha256"]
        if consumer
        else manifest["heightmap_sha256"],
        "SettingsSha256": hashlib.sha256(
            (root / "sa-calobra-settings.json").read_bytes()
        ).hexdigest(),
        "ScreenPercentage": 100,
        "DynamicResolution": False,
        "Sectors": [],
    }
    if consumer:
        for key, native_key in (
            ("MapSha256", "map_sha256"),
            ("ConsumerManifestSha256", "consumer_manifest_sha256"),
            ("MaterialParent", "expected_material_parent"),
        ):
            summary[key] = identity.get(key)
            if identity.get(key) != settings[native_key]:
                summary["Result"] = "FAIL"
        summary["MaterialComponentCount"] = identity.get("MaterialComponentCount")
        summary["RenderInstanceCount"] = identity.get("RenderInstanceCount")
        summary["LightingPreserved"] = identity.get("LightingPreserved")
        if identity.get("Head") != head:
            summary["Result"] = "FAIL"

    def pct(xs, p):
        return sorted(xs)[math.floor(p * (len(xs) - 1))] if xs else None

    for sector in CONSUMER_SECTORS if consumer else ["overview", "rider", "slope"]:
        samples = [r for r in rows if r["sector"] == sector]
        frames = [float(r["frame_ms"]) for r in samples]
        gpu = [float(r["gpu_ms"]) for r in samples if float(r["gpu_ms"]) > 0.01]
        record = {
            "Sector": sector,
            "Pass": True,
            "SampleCount": len(samples),
            "PositiveGpuSampleCount": len(gpu),
            "FrameP95Ms": pct(frames, 0.95),
            "GpuP95Ms": pct(gpu, 0.95),
            "OverBudgetRatio": sum(v > BUDGET_MS for v in frames) / len(frames)
            if frames
            else 1,
        }
        record["Percentiles"] = {
            domain: {
                f"p{p}": pct([float(r[domain]) for r in samples], p / 100)
                for p in (50, 95, 99)
            }
            for domain in ("frame_ms", "game_ms", "draw_ms", "rhi_ms", "gpu_ms")
        }
        summary["Sectors"].append(record)
    policy = json.loads((ROOT / ".gumball/world-proof-policy.json").read_text())[
        "scenarios"
    ][scenario]
    error = None
    try:
        validate_evidence(summary, text, policy, scenario, head)
    except (ValueError, KeyError, TypeError) as exc:
        error = exc
        summary["Result"] = "FAIL"
        summary["Failure"] = str(exc)
    (root / "sa-calobra-terrain-performance-summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(summary, indent=2))
    if error:
        raise error
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "prepare",
            "prepare-consumer",
            "verify-consumer",
            "restore-consumer",
            "evaluate",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--head")
    parser.add_argument("--editor-exit-code", type=int, default=0)
    parser.add_argument("--consumer-manifest", type=Path)
    args = parser.parse_args()
    if args.action in {"prepare-consumer", "verify-consumer", "restore-consumer"}:
        if args.consumer_manifest is None:
            parser.error("--consumer-manifest is required")
        if args.action == "restore-consumer":
            restore_consumer(args.consumer_manifest, args.head)
        elif args.action == "prepare-consumer":
            prepare_consumer(args.root, args.consumer_manifest, args.head)
        else:
            consumer_inputs(args.consumer_manifest, args.head)
    elif args.action == "prepare":
        prepare(args.root)
    else:
        evaluate(args.root, args.head, args.editor_exit_code)
