"""Fixed, source-derived M3 review views; no arbitrary coordinates or asset writes.

Positions and targets are camera_location_cm/target_cm from the pinned survey.
Its FOV is evidence only: the existing editor camera API does not set/read FOV.

Primary API references (Epic Unreal Python 5.8, verified 2026-10-11):
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MathLibrary
The bridge separately requires installed UE 5.8.2 CL 56702186.
"""

import copy
import math

SURVEY_PATH = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
SURVEY_SHA256 = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"
PRESETS = {
    "road": (
        "window-0112-forward-00001",
        (56912.43746055451, 53090.5078449409, 46766.459277036185),
        (58088.73631673153, 52542.60698992016, 46508.19271952782),
    ),
    "hairpin-entry": (
        "window-0081-forward-00004",
        (109450.9636903301, 61482.61393608686, 60561.89003333145),
        (108314.37284330648, 60859.353931051824, 60283.35977104717),
    ),
    "hairpin-middle": (
        "window-0081-forward-00008",
        (105042.35236906033, 56127.00085790906, 59993.97886655077),
        (106331.53853995209, 56116.12918989589, 59647.00334853711),
    ),
    "hairpin-exit": (
        "window-0081-forward-00012",
        (110043.31789041485, 57186.78555655305, 59276.26451517748),
        (109424.57724692047, 56047.65523423272, 58998.58071478912),
    ),
    "nudo": (
        "window-0082-forward-00002",
        (126255.77438750403, 39592.93239490535, 67709.15250835742),
        (125324.02248423095, 38689.02782069985, 67459.90720904173),
    ),
}
COMMANDS = {
    "POKAŻ DROGĘ": "road",
    "POKAŻ WJAZD W NAWRÓT": "hairpin-entry",
    "POKAŻ ŚRODEK NAWROTU": "hairpin-middle",
    "POKAŻ WYJAZD Z NAWROTU": "hairpin-exit",
    "POKAŻ NUDO": "nudo",
}


def preset(name):
    if not isinstance(name, str) or name not in PRESETS:
        raise ValueError("Unknown bounded camera preset")
    frame, location, target = PRESETS[name]
    delta = [b - a for a, b in zip(location, target, strict=True)]
    rotation = [
        math.degrees(math.atan2(delta[2], math.hypot(*delta[:2]))),
        math.degrees(math.atan2(delta[1], delta[0])),
        0.0,
    ]
    return {
        "preset": name,
        "frame_id": frame,
        "source_sha256": SURVEY_SHA256,
        "location_cm": list(location),
        "target_cm": list(target),
        "rotation_deg": rotation,
        "reference_fov_deg": 76.0,
        "viewport_fov_verified": False,
    }


def state(location, rotation):
    value = {
        "location_cm": [float(getattr(location, key)) for key in ("x", "y", "z")],
        "rotation_deg": [
            float(getattr(rotation, key)) for key in ("pitch", "yaw", "roll")
        ],
    }
    validate_state(value)
    return value


def validate_state(value):
    if type(value) is not dict or set(value) != {"location_cm", "rotation_deg"}:
        raise ValueError("Camera readback shape differs")
    for vector in value.values():
        if (
            type(vector) is not list
            or len(vector) != 3
            or not all(type(n) in (int, float) and math.isfinite(n) for n in vector)
        ):
            raise ValueError("Camera readback must contain finite three-vectors")


def matches(actual, expected):
    validate_state(actual)
    return all(
        abs(a - b) < 1.0
        for a, b in zip(actual["location_cm"], expected["location_cm"], strict=True)
    ) and all(
        abs((a - b + 180.0) % 360.0 - 180.0) < 0.01
        for a, b in zip(actual["rotation_deg"], expected["rotation_deg"], strict=True)
    )


def apply(api, editor, name, previous):
    """Move/read back one view; the bridge owns the full request rollback."""
    expected = preset(name)
    if previous is None:
        raise ValueError("No primary level editor viewport camera is available")
    before = state(*previous)
    location = api.Vector(*expected["location_cm"])
    rotation = api.MathLibrary.find_look_at_rotation(
        location, api.Vector(*expected["target_cm"])
    )
    editor.set_level_viewport_camera_info(location, rotation)
    after = state(*editor.get_level_viewport_camera_info())
    if not matches(after, expected):
        raise ValueError(
            "Native viewport camera did not read back the requested preset"
        )
    return {
        "camera_preset": copy.deepcopy(expected),
        "camera_before": before,
        "camera_after": after,
    }


def validate_receipt(value):
    proof = value.get("camera_preset")
    if type(proof) is not dict or proof != preset(proof.get("preset")):
        raise ValueError("Camera preset provenance differs")
    validate_state(value.get("camera_before"))
    if not matches(value.get("camera_after"), proof):
        raise ValueError("Camera receipt readback differs from the source preset")
