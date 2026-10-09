"""Non-admitting, same-camera visual regression evidence for whole-map captures.

Detect large prepared-only black regions relative to both the lit baseline and
emissive checker. This cannot identify the offending mesh, light or material
node; it must never mark a screenshot or the production map visually accepted.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageStat

DARK_MAX_RGB_EXCLUSIVE = 16
PREPARED_ONLY_ALERT_FRACTION = 0.20
CONTROL_MAX_DARK_FRACTION = 0.03
MODES = ("baseline", "prepared", "checker")
POSE_FIELDS = ("camera_location_cm", "target_cm", "camera_rotation_deg", "fov_deg")


def _dark_mask(path: Path, size: tuple[int, int]):
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or symlinked native review frame: " + str(path))
    with Image.open(path) as image:
        if image.format != "PNG" or image.size != size:
            raise ValueError("Visual review requires fixed native PNG dimensions")
        rgb = image.convert("RGB")
        red, green, blue = rgb.split()
        maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        return maximum.point(lambda value: 255 if value < DARK_MAX_RGB_EXCLUSIVE else 0)


def _fraction(mask):
    return ImageStat.Stat(mask).sum[0] / (255 * mask.width * mask.height)


def audit_near_views(proof, captures, near_views, size=(1920, 1080)):
    """Bind a bounded RGB analysis to already independently verified captures."""
    proof = Path(proof)
    lookup = {}
    for row in captures:
        key = (row.get("frame_id"), row.get("mode"))
        if key in lookup:
            raise ValueError("Ambiguous visual review frame key")
        lookup[key] = row
    observations = []
    flagged = []
    for frame_id in near_views:
        frames = []
        for mode in MODES:
            row = lookup.get((frame_id, mode))
            relative = f"frames/{frame_id}-{mode}.png"
            if row is None or row.get("file") != relative:
                raise ValueError(
                    "Visual review frame or provenance is missing: " + relative
                )
            frames.append(row)
        poses = [{key: row.get(key) for key in POSE_FIELDS} for row in frames]
        if poses[0] != poses[1] or poses[0] != poses[2]:
            raise ValueError("Visual review cannot compare unequal camera poses")
        baseline, prepared, checker = (
            _dark_mask(proof / row["file"], size) for row in frames
        )
        new_dark = ImageChops.darker(
            ImageChops.darker(prepared, ImageChops.invert(baseline)),
            ImageChops.invert(checker),
        )
        controls = {
            "baseline_dark_fraction": round(_fraction(baseline), 6),
            "prepared_dark_fraction": round(_fraction(prepared), 6),
            "checker_dark_fraction": round(_fraction(checker), 6),
            "prepared_only_dark_fraction": round(_fraction(new_dark), 6),
        }
        anomaly = (
            controls["prepared_only_dark_fraction"] >= PREPARED_ONLY_ALERT_FRACTION
            and controls["baseline_dark_fraction"] <= CONTROL_MAX_DARK_FRACTION
            and controls["checker_dark_fraction"] <= CONTROL_MAX_DARK_FRACTION
        )
        if anomaly:
            flagged.append(frame_id)
        observations.append(
            {
                "frame_id": frame_id,
                "pixel_count": size[0] * size[1],
                "modes": {
                    mode: {"file": row["file"], "sha256": row.get("sha256")}
                    for mode, row in zip(MODES, frames, strict=True)
                },
                "camera_pose": poses[0],
                **controls,
                "prepared_only_blackout_review_required": anomaly,
            }
        )
    return {
        "schema_version": 1,
        "status": "VISUAL_REVIEW_REQUIRED"
        if flagged
        else "NO_LARGE_PREPARED_ONLY_BLACKOUT",
        "flagged_views": flagged,
        "thresholds": {
            "max_rgb_exclusive": DARK_MAX_RGB_EXCLUSIVE,
            "min_prepared_only_fraction": PREPARED_ONLY_ALERT_FRACTION,
            "max_control_dark_fraction": CONTROL_MAX_DARK_FRACTION,
        },
        "observations": observations,
        "scope": (
            "Lit baseline/prepared versus emissive checker: appearance only. "
            "Does not prove rendered pixel depth, material root cause, shadow "
            "ownership, geometry defects, performance or visual acceptance."
        ),
        "visual_acceptance": "PENDING_OWNER",
        "production_material_update_authorized": False,
    }
