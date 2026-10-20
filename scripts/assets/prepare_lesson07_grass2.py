"""Pack one validated Forge Grass2 variant for the existing Pegasus slot.

The existing Scree adapter in scripts/assemble_surface_slices.py establishes
AO/Roughness/Height/AO packing. This adapter adds strict dimensions and receipts,
without its resizing, clipping, normal generation or colour re-encoding.
OpenImageIO ImageInput reads EXR pixels directly, without colour transforms:
https://openimageio.readthedocs.io/en/latest/pythonbindings.html
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


RESOLUTION = 2048
FAMILY = "mediterranean_soil"
VARIANT = "limestone_grass2_v1"
PREFIX = "YACS_Material"
MAP_SUFFIXES = {
    "BaseColor": "BaseColor.png",
    "Normal_DX": "Normal_DX.png",
    "ORM": "ORM.png",
    "Height": "Height.exr",
    "DetailMasks": "DetailMasks.png",
}
OUTPUT_NAMES = {
    "Colour": "T_Grass2_Colour.png",
    "Normal": "T_Grass2_Normal.png",
    "Masks": "T_Grass2_Masks.png",
}


def _load_forge():
    spec = importlib.util.spec_from_file_location(
        "grass2_material_forge", Path(__file__).with_name("material_forge.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load existing Material Forge validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def read_height_exr(path: Path) -> np.ndarray:
    """Read the first Height channel, matching the existing Scree adapter."""
    try:
        import OpenImageIO as oi
    except ImportError as exc:
        raise RuntimeError("OpenImageIO is required to decode the original Height EXR") from exc
    reader = oi.ImageInput.open(str(path))
    if reader is None:
        raise ValueError(f"Cannot open Height EXR: {path}")
    try:
        spec = reader.spec()
        if (spec.width, spec.height, spec.depth) != (RESOLUTION, RESOLUTION, 1):
            raise ValueError("Height EXR must be exactly 2048 by 2048, depth 1")
        pixels = reader.read_image(format=oi.FLOAT)
        if pixels is None:
            raise ValueError(f"Cannot decode Height EXR: {reader.geterror()}")
        pixels = np.asarray(pixels)
        if not np.isfinite(pixels).all():
            raise ValueError("Height EXR must contain finite values")
        if pixels.ndim == 3 and pixels.shape[2] >= 1:
            pixels = pixels[:, :, 0]
        return pixels
    finally:
        reader.close()


def pack_masks(orm: np.ndarray, height: np.ndarray) -> np.ndarray:
    """Return raw uint8 AO/Roughness/Height/AO; ORM metallic is never sampled."""
    if orm.shape != (RESOLUTION, RESOLUTION, 3) or orm.dtype != np.uint8:
        raise ValueError("ORM must contain exactly 2048 by 2048 RGB uint8 samples")
    height = np.asarray(height)
    if height.shape != (RESOLUTION, RESOLUTION):
        raise ValueError("Height must contain exactly 2048 by 2048 samples")
    if not np.issubdtype(height.dtype, np.floating) or not np.isfinite(height).all():
        raise ValueError("Height must contain finite floating-point samples")
    if float(height.min()) < 0.0 or float(height.max()) > 1.0:
        raise ValueError("Height must already be normalized to [0, 1]; no clipping or rescaling")
    displacement = np.rint(height.astype(np.float64) * 255.0).astype(np.uint8)
    return np.stack((orm[:, :, 0], orm[:, :, 1], displacement, orm[:, :, 0]), axis=-1)


def _identity(path: Path, forge) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": forge.sha256_path(path),
        "size_bytes": path.stat().st_size,
    }


def prepare(variant: Path, output: Path) -> dict[str, Any]:
    variant, output = variant.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f"Output must be a new directory: {output}")
    if output.is_relative_to(variant):
        raise ValueError("Output must be outside the source variant")
    if not output.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    forge = _load_forge()
    provenance = _json(variant / "provenance.json")
    validation = _json(variant / "validation.json")
    for record in (provenance, validation):
        if (record.get("family"), record.get("variant")) != (FAMILY, VARIANT):
            raise ValueError(f"Only {FAMILY}/{VARIANT} is admitted")
    if validation.get("status") != "MAP_CHECKS_PASS_UE_REVIEW_PENDING":
        raise ValueError("Missing successful Forge validation")

    relative_inputs = {
        name: Path("export") / f"{PREFIX}_{suffix}" for name, suffix in MAP_SUFFIXES.items()
    }
    relative_inputs.update({
        "provenance": Path("provenance.json"),
        "validation": Path("validation.json"),
        "native_decode": Path("export") / f"{PREFIX}_native-check.json",
    })
    # Verify the original graph identity as well as the rendered map receipts.
    graph_name = provenance.get("graph")
    if (
        not isinstance(graph_name, str)
        or Path(graph_name).name != graph_name
        or Path(graph_name).suffix != ".ptex"
    ):
        raise ValueError("Provenance must name the original local .ptex graph")
    if forge.sha256_path(variant / graph_name) != provenance.get("graph_sha256"):
        raise ValueError("Original graph hash differs from provenance")
    relative_inputs["graph"] = Path(graph_name)
    inputs = {name: _identity(variant / path, forge) for name, path in relative_inputs.items()}

    # check_variant writes validation.json. A temporary snapshot lets it perform
    # all existing checks without overwriting an original or tampered receipt.
    with tempfile.TemporaryDirectory(prefix=".grass2-validate-", dir=output.parent) as temporary:
        snapshot = Path(temporary)
        for name, relative in relative_inputs.items():
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(variant / relative, destination)
            if forge.sha256_path(destination) != inputs[name]["sha256"]:
                raise ValueError(f"Source changed while staging: {name}")
        actual = forge.check_variant(snapshot, expected_resolution=RESOLUTION)
        if actual != validation:
            raise ValueError("Existing validation receipt differs from fresh Forge validation")
        orm_path = snapshot / relative_inputs["ORM"]
        with Image.open(orm_path) as image:
            if image.mode not in {"RGB", "RGBA"}:
                raise ValueError("ORM must use RGB or RGBA bytes without colour conversion")
            orm = np.asarray(image)[:, :, :3].copy()
        height = read_height_exr(snapshot / relative_inputs["Height"])
        masks = pack_masks(orm, height)
        for name, relative in relative_inputs.items():
            if _identity(variant / relative, forge) != inputs[name]:
                raise ValueError(f"Source changed during validation: {name}")

        output.mkdir(exist_ok=False)
        for target, source in (("Colour", "BaseColor"), ("Normal", "Normal_DX")):
            shutil.copyfile(snapshot / relative_inputs[source], output / OUTPUT_NAMES[target])
            if forge.sha256_path(output / OUTPUT_NAMES[target]) != inputs[source]["sha256"]:
                raise ValueError(f"Byte-preserving copy failed: {target}")
        Image.fromarray(masks).save(output / OUTPUT_NAMES["Masks"], format="PNG")
        maps = {
            name: {
                "file": filename,
                "sha256": forge.sha256_path(output / filename),
                "size_bytes": (output / filename).stat().st_size,
                "size": [RESOLUTION, RESOLUTION],
            }
            for name, filename in OUTPUT_NAMES.items()
        }
        result = {
            "schema_version": 1,
            "status": "GRASS2_PACKAGE_PREPARED_UE_IMPORT_PENDING",
            "family": FAMILY,
            "variant": VARIANT,
            "variant_directory": str(variant),
            "source_validation_sha256": inputs["validation"]["sha256"],
            "class_name": "Grass2",
            "slot": 1,
            "id_code": 64,
            "inputs": inputs,
            "maps": maps,
            "mask_channels": {"R": "ORM.R (AO)", "G": "ORM.G (Roughness)",
                              "B": "round(255 * Height.channel0)", "A": "ORM.R (AO)"},
            "height": {
                "min": float(height.min()),
                "max": float(height.max()),
                "rounding": "nearest, ties to even (numpy.rint)",
                "rescaled": False,
                "clipped": False,
            },
            "resized": False,
            "flipped": False,
            "colour_transformed": False,
            "classification_changed": False,
            "terrain_changed": False,
            "geometry_changed": False,
            "native_ue_verified": False,
            "visual_accepted": False,
        }
        with (output / "grass2-package.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.variant, args.output), indent=2))


if __name__ == "__main__":
    main()
