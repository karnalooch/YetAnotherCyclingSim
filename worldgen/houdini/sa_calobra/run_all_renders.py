"""Batch runner for individual shot renders to ensure separate OpenGL contexts."""
import subprocess
import sys
import time

shots = ["02a_crags", "02b_canyon", "02c_coastal", "03a_before", "03b_after"]
hython = "D:/yacs/tools/houdini-22.0.466/bin/hython.exe"
script = "D:/yacs/project/worldgen/houdini/sa_calobra/run_single_render.py"

for shot in shots:
    print(f"=== Rendering shot: {shot} ===")
    t0 = time.time()
    res = subprocess.run([hython, script, "--shot", shot], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED shot {shot}:\n{res.stderr}\n{res.stdout}")
        sys.exit(1)
    else:
        print(f"COMPLETED {shot} in {time.time() - t0:.2f}s:\n{res.stdout.strip()}")

print("=== ALL 5 SHOTS RENDERED SUCCESSFULLY ===")
