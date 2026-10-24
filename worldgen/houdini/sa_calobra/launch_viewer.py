"""Launch Houdini Geometry Viewer (gplay) and keep process alive until user closes the window."""
import subprocess
import sys
import os

bgeo_file = sys.argv[1] if len(sys.argv) > 1 else "D:/yacs/project/worldgen/houdini/sa_calobra/cache/lesson03_working_material_05m.bgeo.sc"
viewer_exe = "D:/yacs/tools/houdini-22.0.466/bin/gplay.exe"

print(f"Opening 3D Geometry Viewer (gplay): {bgeo_file}")
p = subprocess.Popen([viewer_exe, bgeo_file])
print(f"Gplay running with PID {p.pid} in interactive desktop session.")
print("Keeping session alive. Window is open on user desktop.")
sys.stdout.flush()

# Keep process alive until window is closed
p.wait()
print("Viewer window closed by user.")
