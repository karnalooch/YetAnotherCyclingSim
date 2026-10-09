param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ForgeArgs
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Script = Join-Path $RepoRoot "scripts\assets\material_forge.py"

$Python = if (Test-Path (Join-Path $RepoRoot ".venv\Scripts\python.exe")) {
    Join-Path $RepoRoot ".venv\Scripts\python.exe"
} else {
    "python"
}

& $Python $Script @ForgeArgs
exit $LASTEXITCODE
