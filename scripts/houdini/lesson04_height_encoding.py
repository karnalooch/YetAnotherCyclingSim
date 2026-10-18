"""H22.0.466 transport adapter; source heights remain in metres.

Pinned HoudiniLandscapeUtils::ConvertHeightFieldData normalizes about 0.5,
then truncates normalized * 65535. UE's neutral sample is 32768, not 32767.
Encode bin centres for that specific converter, with an explicitly measured
target Landscape scale. This is transport quantization, not terrain authoring.
"""

import numpy as np


def height_codes(heights_m, scale_z):
    if not np.isfinite(scale_z) or scale_z <= 0:
        raise ValueError("Landscape Scale.Z must be finite and positive")
    values = np.asarray(heights_m, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite source height")
    codes = np.rint(values * (12800.0 / scale_z)) + 32768.0
    if codes.min() < 0 or codes.max() > 65535:
        raise ValueError("Height exceeds target Landscape range; refusing clipping")
    return codes.astype(np.uint16)


def h22_transport(codes, scale_z):
    codes = np.asarray(codes)
    if not np.isfinite(codes).all() or codes.min() < 0 or codes.max() > 65535:
        raise ValueError("Invalid unsigned Landscape codes")
    values = (codes.astype(np.float64) + 0.5) / 65535.0 - 0.5
    return (values * (scale_z * 512.0 / 100.0)).astype(np.float32)


def additive_codes(base_m, final_m, scale_z):
    # Quantize the absolute endpoints before differencing. Equal shared samples
    # then produce equal final codes, including at tile boundaries.
    base = height_codes(base_m, scale_z).astype(np.int32)
    final = height_codes(final_m, scale_z).astype(np.int32)
    codes = 32768 + final - base
    if codes.min() < 0 or codes.max() > 65535:
        raise ValueError("Delta exceeds the additive Edit Layer range")
    return codes.astype(np.uint16)


def decode_h22_readback(exported_m, scale_z):
    """Undo H22's UE input codec, then use UE's actual 32768/128 units.

    UnrealLandscapeTranslator exports (q - 32767) * 512/65535 * Scale.Z/100.
    Those exported floats are not unbiased world elevations. Recovering q is
    lossless for all uint16 values at the independently tested target scales.
    """
    if not np.isfinite(scale_z) or scale_z <= 0:
        raise ValueError("Invalid native Landscape scale")
    values = np.asarray(exported_m, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite native export")
    codes = np.rint(values / (512.0 / 65535.0 * scale_z / 100.0)) + 32767
    if codes.min() < 0 or codes.max() > 65535:
        raise ValueError("Invalid native export range")
    return codes.astype(np.uint16), (codes - 32768) * scale_z / 12800.0


def north_first_uv(index0, resolution, spacing_m):
    nx, ny = resolution[:2]
    if nx < 2 or ny < 2 or spacing_m <= 0:
        raise ValueError("Invalid texture grid")
    # The PNG pixel centre (0,0) is at (x_min,z_max), not (x_min,z_min).
    origin_cm = [
        (index0[0] - spacing_m / 2) * 100,
        (index0[2] + spacing_m / 2) * 100,
        0,
    ]
    inverse_cm = [1 / (nx * spacing_m * 100), -1 / (ny * spacing_m * 100), 0]
    return origin_cm, inverse_cm
