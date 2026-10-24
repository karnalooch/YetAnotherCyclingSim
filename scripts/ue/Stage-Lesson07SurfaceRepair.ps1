#requires -Version 7.4
<# Stage the exact reviewed importer and five texture files inside the canonical project.
   No Unreal API, descriptor/config edits, package overwrites or process changes. #>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedHead,
  [Parameter(Mandatory)][ValidatePattern('^[1-9][0-9]{0,19}-[1-9][0-9]{0,4}$')][string]$RunToken
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python='D:\yacs\tool-cache\material-forge\python\Scripts\python.exe'
$stage=Join-Path 'D:\yacs\project\Saved\RuntimeProof\Lesson07SurfaceRepair-20261021' $RunToken
$source=Join-Path $PSScriptRoot 'apply_lesson07_surface_repair.py'
if ((git -C $repo rev-parse HEAD).Trim() -cne $ExpectedHead) { throw 'SURFACE_STAGE_SOURCE_HEAD' }
foreach ($path in @($stage,$source)) {
  $cursor=[IO.Path]::GetFullPath($path)
  while ($cursor) {
    if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
      throw 'SURFACE_STAGE_REDIRECTED_PATH'
    }
    $cursor=[IO.Path]::GetDirectoryName($cursor)
  }
}
if (Test-Path -LiteralPath $stage) { throw 'SURFACE_STAGE_ALREADY_EXISTS' }
& $python -B -c "from scripts.ue.lesson07_wingman_client import SURFACE_IMPORT_SHA256; import hashlib,pathlib; p=pathlib.Path('scripts/ue/apply_lesson07_surface_repair.py'); assert hashlib.sha256(p.read_bytes()).hexdigest()==SURFACE_IMPORT_SHA256, 'SURFACE_STAGE_IMPORTER_HASH'"
if ($LASTEXITCODE -ne 0) { throw 'SURFACE_STAGE_IMPORTER_HASH' }
[void][IO.Directory]::CreateDirectory($stage)
& $python -B scripts/assets/prepare_lesson07_surface_repair.py `
  --output (Join-Path $stage 'package') `
  --source-cache 'D:\yacs\work\lesson07-rock-source-20261021' `
  --grass-sources 'D:\yacs\work\lesson07-source-repair-20261021\39519585751-1' --download
if ($LASTEXITCODE -ne 0) { throw 'SURFACE_STAGE_PACKAGE_FAILED' }
$target=Join-Path $stage 'apply_lesson07_surface_repair.py'
# The installed file tool evaluates the source without defining __file__.
# Add only that exact staged path; retain every byte of the reviewed template.
$renderSource = @'
import hashlib, json, sys
from pathlib import Path
from scripts.ue.lesson07_wingman_client import (
    SURFACE_IMPORT_FILE, plain_path, read_bounded, render_surface_source,
    require, surface_stage, verify_surface_source,
)
run_token, source_name, target_name = sys.argv[1:]
target = plain_path(Path(target_name))
require(target == surface_stage(run_token) / SURFACE_IMPORT_FILE, "SURFACE_STAGE_TARGET")
rendered = render_surface_source(run_token, read_bounded(source_name, 256 * 1024))
with target.open("xb") as stream:
    stream.write(rendered)
proof = verify_surface_source(run_token)
require(proof["rendered_sha256"] == hashlib.sha256(rendered).hexdigest(), "SURFACE_STAGE_RENDER_HASH")
print("SURFACE_STAGE_SOURCE " + json.dumps(proof, sort_keys=True))
'@
& $python -B -c $renderSource $RunToken $source $target
if ($LASTEXITCODE -ne 0) { throw 'SURFACE_STAGE_RENDER_FAILED' }
Write-Host 'SURFACE_STAGE_READY native_import=NOT_RUN'
