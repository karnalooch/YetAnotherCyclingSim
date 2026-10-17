"""Keep the legacy checkpoint separate from opt-in Houdini Engine settings.

These are portable configuration checks, not native Engine/HAPI launch proof.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SECTION = "[/Script/HoudiniEngineRuntime.HoudiniRuntimeSettings]"
SETTINGS = (
    ("bUseCustomHoudiniLocation", "True"),
    ("CustomHoudiniLocation", '(Path="D:/yacs/tools/houdini-22.0.466/bin")'),
    ("MarshallingLandscapesUseFullResolution", "True"),
)


class HoudiniConfigurationTests(unittest.TestCase):
    def test_legacy_engine_bytes_match_the_unchanged_checkpoint(self):
        raw = (ROOT / "Config/DefaultEngine.ini").read_bytes()
        self.assertEqual(len(raw), 2877)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "d94045cbb0c78e0fde92d17f37651a11a94cc7c2b4bbd4a46382ac91ee5adb4b",
        )

    def test_host_override_is_not_in_shared_project_defaults(self):
        text = (ROOT / "Config/DefaultEngine.ini").read_text(encoding="utf-8")
        self.assertNotIn(SECTION, text)
        self.assertNotIn("D:/yacs/tools/houdini-", text)

    def test_opt_in_profile_has_exactly_the_three_original_properties(self):
        text = (ROOT / "scripts/houdini/unreal-engine.args").read_text(
            encoding="utf-8"
        ).strip()
        expected = "-ini:Engine:" + ",".join(
            f"{SECTION}:{key}={value}" for key, value in SETTINGS
        )
        self.assertEqual(text, expected)
        self.assertFalse(any(character.isspace() for character in text))

    def test_separation_preserves_the_entire_previous_configuration(self):
        baseline = (ROOT / "Config/DefaultEngine.ini").read_bytes()
        block = "\n" + SECTION + "\n"
        block += "".join(f"{key}={value}\n" for key, value in SETTINGS) + "\n"
        previous = baseline + block.encode("utf-8")
        self.assertEqual(len(previous), 3074)
        self.assertEqual(
            hashlib.sha256(previous).hexdigest(),
            "3cb8337bf8589d292ea5d7a11e174f97e1e18771728c140487b3d8ddff61b19b",
        )


if __name__ == "__main__":
    unittest.main()
