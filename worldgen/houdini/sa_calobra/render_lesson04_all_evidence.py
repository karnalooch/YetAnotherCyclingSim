"""Master runner to render all visual evidence for Pegasus Lesson 04.

Invokes run_single_render.py in isolated sub-processes for each shot to guarantee
clean OpenGL context recreation and avoid driver buffer exhaustion.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys


def main():
    proj_dir = pathlib.Path("D:/yacs/project/worldgen/houdini/sa_calobra").resolve()
    hython_bin = "D:/yacs/tools/houdini-22.0.466/bin/hython.exe"
    script = proj_dir / "run_single_render.py"

    shots = [
        "00_working_pano",
        "01_pano",
        "02a_crags",
        "02b_canyon",
        "02c_coastal",
        "03a_tint_before",
        "03b_tint_after",
        "04_cliff_trans"
    ]

    print("==================================================")
    print("  RENDERING ALL LESSON 04 EVIDENCE VIEWS")
    print(f"  Total Shots: {len(shots)}")
    print("==================================================")

    for i, shot in enumerate(shots, 1):
        print(f"\n>>> [{i}/{len(shots)}] Rendering Shot: {shot} ...")
        cmd = [hython_bin, script.as_posix(), "--shot", shot]
        res = subprocess.run(cmd, cwd=proj_dir.as_posix(), capture_output=True, text=True)
        print(res.stdout)
        if res.returncode != 0:
            print(f"STDERR: {res.stderr}")
            sys.exit(res.returncode)

    print("\n==================================================")
    print("  ALL LESSON 04 EVIDENCE RENDERS COMPLETED!")
    print("==================================================")


if __name__ == "__main__":
    main()
