"""Verify actual MM exports and create an explicitly illustrative relief preview."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def check(directory):
    maps = {}
    arrays = {}
    for channel in ("BaseColor", "Normal_DX", "ORM"):
        path = directory / "export" / ("SaCalobra_PaleLimestone_" + channel + ".png")
        with Image.open(path) as im:
            if im.size != (2048, 2048):
                raise ValueError("Unexpected resolution: " + channel)
            a = np.asarray(im.convert("RGB"), dtype=np.float32) / 255
        arrays[channel] = a
        # Compare wrap-boundary steps with ordinary within-image pixel steps.
        dx = np.abs(a[:, 1:] - a[:, :-1]).mean()
        dy = np.abs(a[1:] - a[:-1]).mean()
        sx = np.abs(a[:, 0] - a[:, -1]).mean()
        sy = np.abs(a[0] - a[-1]).mean()
        if sx > max(0.015, 4 * dx) or sy > max(0.015, 4 * dy):
            raise ValueError("Discontinuous wrap boundary: " + channel)
        maps[channel] = {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": [2048, 2048],
            "wrap_step_x": float(sx),
            "wrap_step_y": float(sy),
            "interior_step_x": float(dx),
            "interior_step_y": float(dy),
        }
    color, normal, orm = (arrays[x] for x in ("BaseColor", "Normal_DX", "ORM"))
    if color.std() < 0.003 or normal[..., :2].std() < 0.01:
        raise ValueError("Missing surface detail")
    if np.max(orm[..., 2]) > 1 / 255:
        raise ValueError("Limestone must not be metallic")
    vectors = normal * 2 - 1
    length = np.linalg.norm(vectors, axis=2)
    if np.quantile(np.abs(length - 1), 0.99) > 0.025 or vectors[..., 2].min() < 0:
        raise ValueError("Invalid DirectX normal vectors")
    exr = directory / "export/SaCalobra_PaleLimestone_Height.exr"
    if exr.read_bytes()[:4] != b"\x76\x2f\x31\x01":
        raise ValueError("Missing EXR height")
    maps["Height"] = {
        "path": str(exr.resolve()),
        "sha256": hashlib.sha256(exr.read_bytes()).hexdigest(),
    }
    vectors /= length[..., None]
    vectors[..., 1] *= -1  # DirectX tangent Y to illustrative image lighting.
    light = np.array([-0.45, -0.65, 0.7], dtype=np.float32)
    light /= np.linalg.norm(light)
    diffuse = 0.28 + 0.72 * np.maximum(0, np.sum(vectors * light, axis=2))
    linear = np.where(color <= 0.04045, color / 12.92, ((color + 0.055) / 1.055) ** 2.4)
    shaded = linear * diffuse[..., None] * orm[..., 0, None]
    shaded = np.where(
        shaded <= 0.0031308,
        12.92 * shaded,
        1.055 * np.maximum(shaded, 0) ** (1 / 2.4) - 0.055,
    )
    preview = Image.fromarray(np.uint8(np.clip(shaded, 0, 1) * 255))
    preview.resize((1024, 1024), Image.Resampling.LANCZOS).save(
        directory / "relief-preview.png"
    )
    plate = Image.new("RGB", (1440, 770), (27, 30, 34))
    draw = ImageDraw.Draw(plate)
    for i, (title, array) in enumerate(
        (
            ("BASE COLOR", color),
            ("NORMAL DX", normal),
            ("RELIEF / ILLUSTRATIVE LIGHT", shaded),
        )
    ):
        tile = Image.fromarray(np.uint8(np.clip(array, 0, 1) * 255)).resize(
            (480, 480), Image.Resampling.LANCZOS
        )
        plate.paste(tile, (480 * i, 40))
        draw.text((480 * i + 15, 15), title, fill="white")
    tile = Image.fromarray(np.uint8(color * 255)).resize(
        (225, 225), Image.Resampling.LANCZOS
    )
    repeat = Image.new("RGB", (675, 675))
    for y in range(3):
        for x in range(3):
            repeat.paste(tile, (x * 225, y * 225))
    repeat.save(directory / "basecolor-3x3.png")
    draw.text(
        (16, 550),
        "Sa Calobra - pale limestone candidate / 2 m tile / 2048 px",
        fill="white",
    )
    draw.text(
        (16, 580),
        "Actual Material Maker maps. Relief image is a flat diffuse preview, not an Unreal render.",
        fill="white",
    )
    draw.text(
        (16, 610),
        "No terrain displacement. No photographic scan. Visual approval and UE shading still pending.",
        fill="white",
    )
    plate.crop((0, 0, 1440, 645)).save(directory / "review.png")
    result = {
        "status": "MAP_CHECKS_PASS_UE_REVIEW_PENDING",
        "maps": maps,
        "normal_length_error_p99": float(np.quantile(np.abs(length - 1), 0.99)),
        "color_mean_srgb": color.mean(axis=(0, 1), dtype=np.float64).tolist(),
        "geometry_changed": False,
        "visual_accepted": False,
    }
    (directory / "validation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    check(parser.parse_args().directory)
