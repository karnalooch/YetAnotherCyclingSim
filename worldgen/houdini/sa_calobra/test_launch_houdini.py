import subprocess
import time

hip = "D:/yacs/project/worldgen/houdini/sa_calobra/SaCalobra_Pegasus_Lesson03.hiplc"
exe = "D:/yacs/tools/houdini-22.0.466/bin/houdini.exe"

print(f"Launching Houdini and monitoring for 20 seconds...")
p = subprocess.Popen([exe, hip], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print(f"PID: {p.pid}")

for i in range(20):
    time.sleep(1)
    ret = p.poll()
    if ret is not None:
        out, err = p.communicate()
        print(f"Exited at T+{i+1}s with code {ret}")
        print("STDOUT:", out.decode("utf-8", errors="ignore"))
        print("STDERR:", err.decode("utf-8", errors="ignore"))
        break
    else:
        if (i + 1) % 5 == 0:
            print(f"Still running at T+{i+1}s...")

if p.poll() is None:
    print(f"SUCCESS: Houdini is running steadily in GUI mode! PID={p.pid}")
