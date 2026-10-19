import os
from pathlib import Path
import subprocess
import sys

def main():
    engine_bin = Path("D:/yacs/engine/UE_5.8/Engine/Binaries/Win64")
    editor_exe = engine_bin / "UnrealEditor.exe"
    project = Path("D:/yacs/project/YetAnotherCyclingSim.uproject").resolve()
    if len(sys.argv) > 1:
        script = Path(sys.argv[1]).resolve()
    else:
        script = Path("D:/yacs/project/scripts/ue/capture_lesson07_shots.py").resolve()
    
    toolset_bin = Path("D:/yacs/engine/UE_5.8/Engine/Plugins/Experimental/ToolsetRegistry/Binaries/Win64")
    sandbox_bin = Path("D:/yacs/engine/UE_5.8/Engine/Plugins/Developer/Sandbox/FileSandbox/Binaries/Win64")
    env = os.environ.copy()
    env["PATH"] = f"{toolset_bin};{sandbox_bin};{engine_bin};" + env.get("PATH", "")
    
    cmd = [
        str(editor_exe),
        str(project),
        f"-ExecutePythonScript={script}",
        "-RenderOffscreen",
        "-unattended",
        "-nopause",
        "-nosplash",
        "-nosound",
        "-NoLiveCoding",
        "-stdout",
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print("RETURN CODE:", result.returncode)
    print("STDOUT TAIL:")
    print("\n".join(result.stdout.splitlines()[-30:]))
    if result.stderr:
        print("STDERR TAIL:")
        print("\n".join(result.stderr.splitlines()[-30:]))
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
