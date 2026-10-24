"""Cross-checkout editor admission must reject writes even with Python -O."""

from pathlib import Path
import subprocess
import sys
import unittest


class EditorProjectGuardTests(unittest.TestCase):
    def test_all_material_entrypoints_reject_other_project_before_editor_access(self):
        scripts = Path(__file__).parent
        for name in (
            "apply_lesson07_grass2.py",
            "repair_lesson07_global_colour.py",
            "tune_lesson07_landscape_appearance.py",
            "readback_lesson07_texture_variation.py",
        ):
            with self.subTest(script=name):
                code = """
import runpy,sys,types
paths=types.SimpleNamespace(project_dir=lambda: '/another/editor/project',
    convert_relative_path_to_full=lambda p:p)
sys.modules['unreal']=types.SimpleNamespace(Paths=paths)
module=runpy.run_path(sys.argv[1])
try:
    module['main']()
except RuntimeError as error:
    if 'Active Unreal project differs' not in str(error): raise
else:
    raise RuntimeError('Wrong project was admitted')
"""
                result = subprocess.run(
                    [sys.executable, "-O", "-c", code, str(scripts / name)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
