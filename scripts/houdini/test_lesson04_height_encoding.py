import unittest
import numpy as np
from lesson04_height_encoding import (
    additive_codes,
    height_codes,
    h22_transport,
    north_first_uv,
    decode_h22_readback,
)


class HeightEncodingTests(unittest.TestCase):
    def test_native_input_codec_recovers_all_codes_and_actual_ue_zero(self):
        codes = np.arange(65536, dtype=np.uint16)
        for scale in (100.0, 225.14453125, 585.9375):
            exported = (
                (codes.astype(np.float64) - 32767) * 512.0 / 65535.0 * scale / 100.0
            ).astype(np.float32)
            recovered, world = decode_h22_readback(exported, scale)
            np.testing.assert_array_equal(recovered, codes)
            np.testing.assert_array_equal(
                world, (codes.astype(np.float64) - 32768) * scale / 12800.0
            )
            self.assertEqual(world[32768], 0.0)

    def test_all_unsigned_codes_survive_pinned_native_float_converter(self):
        codes = np.arange(65536, dtype=np.uint16)
        for scale in (100.0, 225.14453125, 585.9375):
            transport = h22_transport(codes, scale)
            # Independently model the installed C++ float operations verbatim.
            factor = np.float32(np.float32(100) / np.float32(scale * 256)) * np.float32(
                0.5
            )
            native = np.clip(
                (transport * factor + np.float32(0.5)) * np.float32(65535), 0, 65535
            ).astype(np.uint16)
            np.testing.assert_array_equal(native, codes)

    def test_zero_delta_has_exact_unreal_neutral_and_roundtrip(self):
        base = np.linspace(-1, 1450, 100001)
        codes = additive_codes(base, base, 585.9375)
        self.assertTrue(np.all(codes == 32768))

    def test_additive_composite_and_shared_edge_codes(self):
        base = np.linspace(-1, 1450, 100001)
        final = base + 0.34 * np.sin(base)
        b = height_codes(base, 585.9375).astype(np.int32)
        d = additive_codes(base, final, 585.9375).astype(np.int32)
        np.testing.assert_array_equal(b + d - 32768, height_codes(final, 585.9375))
        restored = (b + d - 65536) * 585.9375 / 12800
        self.assertLessEqual(float(np.abs(restored - final).max()), 585.9375 / 25600)

    def test_rejects_clipping_and_nonfinite(self):
        for values in ([1501], [-1501], [np.nan], [np.inf]):
            with self.assertRaises(ValueError):
                height_codes(values, 585.9375)

    def test_north_first_pixel_centres_and_coastal_sample(self):
        p = (-1900.25, 0, 739.75)
        n = (3811, 5081)
        s = 0.5
        origin, inverse = north_first_uv(p, n, s)
        for col, row in ((0, 0), (3810, 5080), (3705, 4343)):
            x, z = p[0] + col * s, p[2] - row * s
            self.assertAlmostEqual(
                (x * 100 - origin[0]) * inverse[0], (col + 0.5) / n[0]
            )
            self.assertAlmostEqual(
                (z * 100 - origin[1]) * inverse[1], (row + 0.5) / n[1]
            )


if __name__ == "__main__":
    unittest.main()
