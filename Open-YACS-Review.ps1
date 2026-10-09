# YACS Sa Calobra - one-file, fail-closed visual review launcher.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .\Open-YACS-Review.ps1
# Optional: -Diagnose (read-only), -Recover (restore a previous interrupted session).
[CmdletBinding()]
param(
    [switch]$Diagnose,
    [switch]$Recover
)

# Windows PowerShell 5.1 can execute this bootstrap; the real work requires pwsh >= 7.4.
if ($PSVersionTable.PSVersion -lt [version]'7.4') {
    $portable = 'D:\yacs\tools\powershell-7.6.6-win-x64\pwsh.exe'
    if (-not (Test-Path -LiteralPath $portable -PathType Leaf)) {
        Write-Error "PowerShell 7.4+ missing. Expected: $portable"
        exit 1
    }
    $forward = @('-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
    if ($Diagnose) { $forward += '-Diagnose' }
    if ($Recover)  { $forward += '-Recover' }
    & $portable @forward
    exit $LASTEXITCODE
}

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$project = 'D:\yacs\project'
$workspace = 'D:\yacs\workspace.json'
$sha = '7e37eec2a2190ef89cb448addec8fb8d7f9e61d7'
$proof = "D:\yacs\work\proofs\sa-calobra-whole-map\$sha\37892732453-1"
$review = 'D:\yacs\work\sa-calobra-live-review'
$stateFile = Join-Path $review 'active-review-state.json'
$logFile = Join-Path $review 'launcher.log'
$expectedMap = '/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004'
$script:changedAnything = $false
$script:session = $null
$script:Failure = $null

function Say([string]$Message, [string]$Color = 'Gray') {
    Write-Host $Message -ForegroundColor $Color
    Add-Content -LiteralPath $logFile -Value ("[{0}] {1}" -f (Get-Date -Format o), $Message) -Encoding utf8
}
function Assert-File([string]$Path, [string]$Description) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing $Description : $Path"
    }
}
function Assert-NoEditor {
    if (@(Get-Process -Name 'UnrealEditor','UnrealEditor-Cmd' -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'Unreal is already running. Save other work, close the editor, then run the launcher again.'
    }
}
function Run-Python([string]$Label, [string[]]$Parameters) {
    Say "--- $Label ---" 'Cyan'
    $oldPreference = $ErrorActionPreference
    try {
        # Preserve raw Python error messages instead of returning only a generic failure.
        $ErrorActionPreference = 'Continue'
        & python @Parameters 2>&1 | ForEach-Object { Write-Host $_; Add-Content -LiteralPath $logFile -Value ([string]$_) -Encoding utf8 }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($code -ne 0) { throw "$Label failed (exit $code). See: $logFile" }
}
function Save-State([hashtable]$Value) {
    $Value | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $stateFile -Encoding utf8
}
function Restore-Session {
    if (-not (Test-Path -LiteralPath $stateFile -PathType Leaf)) { return }
    Assert-NoEditor
    $s = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if ($s.project -ne $project -or $s.map -ne $expectedMap) {
        throw 'Recovery state belongs to a different project/map; no files were modified.'
    }
    $unresolved = $false
    if ($s.ini_modified -eq $true) {
        Assert-File $s.ini 'editor autosave configuration'
        $hash = (Get-FileHash -LiteralPath $s.ini -Algorithm SHA256).Hash
        if ($hash -eq $s.ini_guard_sha256) {
            if ($s.ini_existed -eq $true) {
                Assert-File $s.backup 'original autosave configuration backup'
                [IO.File]::WriteAllBytes([string]$s.ini, [IO.File]::ReadAllBytes([string]$s.backup))
            }
            else {
                Remove-Item -LiteralPath $s.ini -Force
            }
            Say 'Original Auto Save settings restored.' 'Green'
        }
        else {
            Say "WARNING: Unreal or another process changed Auto Save settings. Preserving newer file: $($s.ini)" 'Yellow'
            Say "Review the original backup before manually restoring: $($s.backup)" 'Yellow'
            $unresolved = $true
        }
    }
    if ($s.map_readonly_changed -eq $true) {
        Assert-File $s.map_path 'accepted source map'
        $item = Get-Item -LiteralPath $s.map_path
        if ($item.IsReadOnly) {
            # Restore only the attribute changed by this session; do not change map bytes.
            $item.IsReadOnly = $false
            Say 'Original map ReadOnly attribute restored (map bytes untouched).' 'Green'
        }
    }
    if ($unresolved) {
        throw "Auto Save config has changed since launch. Recovery state and backup retained: $stateFile"
    }
    Remove-Item -LiteralPath $stateFile -Force
    Say 'Session recovery finished.' 'Green'
}

New-Item -ItemType Directory -Path $review -Force | Out-Null
Say '=== YACS SA CALOBRA | 43/43 PROOF | SAFE LIVE REVIEW ===' 'Cyan'

if ($Recover) {
    Restore-Session
    return
}

# Interrupted sessions need explicit cleanup before running a new editor.
if (Test-Path -LiteralPath $stateFile -PathType Leaf) {
    Assert-NoEditor
    Say 'A previous review left recovery state. Restoring it first...' 'Yellow'
    Restore-Session
}

try {
    Assert-NoEditor
    if (@(Get-Process -Name 'Runner.Worker' -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'The Windows GitHub runner is running a job. Do not use Unreal concurrently.'
    }
    Assert-File $workspace 'workspace.json'
    Assert-File (Join-Path $project 'YetAnotherCyclingSim.uproject') 'YACS Unreal project'
    Assert-File (Join-Path $project 'scripts\manage_local_workspace.py') 'workspace launcher'
    Assert-File (Join-Path $project 'scripts\assets\install_sa_calobra_whole_map_prep.py') 'proof-bound installer'
    Assert-File (Join-Path $project 'scripts\ue\sa_calobra_whole_map_prep.py') 'owner preview'
    Assert-File (Join-Path $proof 'native-proof-verification.json') 'native 43-frame proof'
    Assert-File (Join-Path $proof 'checkout-restoration.json') 'checkout restoration proof'
    $null = Get-Command python -ErrorAction Stop

    $env:YACS_WORKSPACE_CONFIG = $workspace
    Push-Location $project
    try {
        # Canonical config, source map hash/checkpoint, and native modules must all pass.
        Run-Python 'VERIFY PROJECT' @('scripts/manage_local_workspace.py','doctor','--config',$workspace)
        $cfg = Get-Content -LiteralPath $workspace -Raw | ConvertFrom-Json
        if ([string]$cfg.map -ne $expectedMap) {
            throw "Configured map differs: $($cfg.map). Expected: $expectedMap"
        }

        # Only repair line-ending differences against the immutable native
        # recipe SHA256. All real catalogue/material changes remain fail-closed.
        Run-Python 'VERIFY RECIPE / SAFE CRLF NORMALIZATION' @(
            'scripts/assets/diagnose_sa_calobra_recipe.py',
            '--proof-root',$proof,'--backup-dir',$review,'--normalize-catalogue-lf'
        )

        Run-Python 'VERIFY NATIVE MATERIAL PACKAGES (NO WRITE)' @(
            'scripts/assets/install_sa_calobra_whole_map_prep.py',
            '--proof-root',$proof,'--workspace-config',$workspace
        )
        if ($Diagnose) {
            Say 'DIAGNOSE PASS; did not install assets, alter Auto Save, or start Unreal.' 'Green'
            return
        }
        # The installer itself is fail-closed: existing mismatched packages are not overwritten.
        Run-Python 'INSTALL ONLY MISSING VERIFIED PACKAGES' @(
            'scripts/assets/install_sa_calobra_whole_map_prep.py',
            '--proof-root',$proof,'--workspace-config',$workspace,'--apply'
        )

        $mapPath = Join-Path $project ('Content\' + $expectedMap.Substring(6).Replace('/','\') + '.umap')
        Assert-File $mapPath 'accepted production .umap'
        $mapItem = Get-Item -LiteralPath $mapPath
        $mapTouched = -not $mapItem.IsReadOnly

        # This file is project-scoped and can be restored byte-for-byte if UE left it unchanged.
        $winEditorIni = Join-Path $project 'Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini'
        $windowsIni = Join-Path $project 'Saved\Config\Windows\EditorPerProjectUserSettings.ini'
        $ini = if (Test-Path -LiteralPath $winEditorIni -PathType Leaf) {
            $winEditorIni
        } elseif (Test-Path -LiteralPath $windowsIni -PathType Leaf) {
            $windowsIni
        } else {
            $winEditorIni
        }
        $iniExisted = Test-Path -LiteralPath $ini -PathType Leaf
        $backup = Join-Path $review ('autosave-before-' + (Get-Date -Format yyyyMMdd-HHmmss-fff) + '.bak')
        if ($iniExisted) { Copy-Item -LiteralPath $ini -Destination $backup -ErrorAction Stop }

        $session = @{
            project=$project; map=$expectedMap; map_path=$mapPath
            map_readonly_changed=$false; ini=$ini; ini_existed=$iniExisted
            ini_modified=$false; ini_guard_sha256=''; backup=$backup
        }
        Save-State $session
        $script:changedAnything = $true

        if ($mapTouched) {
            $session.map_readonly_changed = $true
            Save-State $session
            $mapItem.IsReadOnly = $true
        }

        New-Item -ItemType Directory -Path (Split-Path -Parent $ini) -Force | Out-Null
        # Build the exact prospective bytes, store recovery metadata FIRST, then write.
        $override = "`r`n[/Script/UnrealEd.EditorLoadingSavingSettings]`r`nbAutoSaveEnable=False`r`nbAutoSaveMaps=False`r`nbAutoSaveContent=False`r`n"
        $previousBytes = if ($iniExisted) { [IO.File]::ReadAllBytes($ini) } else { [byte[]]@() }
        $overrideBytes = [Text.UTF8Encoding]::new($false).GetBytes($override)
        $newBytes = [byte[]]::new($previousBytes.Length + $overrideBytes.Length)
        [Array]::Copy($previousBytes, 0, $newBytes, 0, $previousBytes.Length)
        [Array]::Copy($overrideBytes, 0, $newBytes, $previousBytes.Length, $overrideBytes.Length)
        $session.ini_guard_sha256 = [Convert]::ToHexString(
            [Security.Cryptography.SHA256]::HashData($newBytes)
        )
        $session.ini_modified = $true
        Save-State $session
        [IO.File]::WriteAllBytes($ini, $newBytes)

        # Create the two commands for Unreal's built-in Python console.
        $applyPath = Join-Path $review 'apply.py'
        $restorePath = Join-Path $review 'restore.py'
        $applyPython = @"
import sys
sys.path.insert(0, r'$project')
import unreal
settings_type = getattr(unreal, 'EditorLoadingSavingSettings', None)
if settings_type is None:
    raise RuntimeError('EditorLoadingSavingSettings is unavailable. Disable Auto Save in Editor Preferences before preview.')
settings = unreal.get_default_object(settings_type)
for name in ('auto_save_enable', 'auto_save_maps', 'auto_save_content'):
    if bool(settings.get_editor_property(name)):
        raise RuntimeError('Auto Save still enabled (' + name + '); disable it in Editor Preferences and retry.')
from scripts.ue.sa_calobra_whole_map_prep import preview
result = preview('apply', bundle=r'$proof\whole-map-prep', master_receipt=r'$proof\whole-map-master-receipt.json')
unreal.log('YACS PREVIEW ACTIVE (NO SAVE): ' + str(result))
print(result)
"@
        $restorePython = @"
import sys
sys.path.insert(0, r'$project')
from scripts.ue.sa_calobra_whole_map_prep import preview
print(preview('restore'))
"@
        [IO.File]::WriteAllText($applyPath, $applyPython, [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($restorePath, $restorePython, [Text.UTF8Encoding]::new($false))
        $applyCommand = 'py "' + $applyPath + '"'
        $restoreCommand = 'py "' + $restorePath + '"'
        try { Set-Clipboard -Value $applyCommand; Say 'Apply command copied to clipboard.' 'Green' }
        catch { Say "Clipboard unavailable; copy the command shown below: $applyCommand" 'Yellow' }

        Say 'Starting verified Unreal Editor and the accepted Sa Calobra map...' 'Cyan'
        Run-Python 'START UNREAL (CANONICAL LAUNCHER)' @(
            'scripts/manage_local_workspace.py','open','--config',$workspace
        )
        Say 'When the map is fully loaded, open the Unreal Python console and run:' 'Green'
        Say "  $applyCommand" 'Cyan'
        Say "To put the ORIGINAL materials back before closing, run: $restoreCommand" 'Yellow'
        Say 'Auto Save should be OFF. If a Save dialog appears: CANCEL. On exit: DONT SAVE.' 'Yellow'
        Say 'Keep this PowerShell window open; settings will be restored after UE exits.' 'Yellow'

        $editor = $null
        for ($i = 0; $i -lt 90; $i++) {
            $editor = Get-Process -Name UnrealEditor -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($null -ne $editor) { break }
            Start-Sleep -Milliseconds 500
        }
        if ($null -eq $editor) { throw 'UnrealEditor.exe did not appear after launch. See the launch log.' }
        Wait-Process -Id $editor.Id
        Say 'Unreal Editor has closed.' 'Green'
    }
    finally { Pop-Location }
}
catch {
    Say ('ERROR: ' + $_.Exception.Message) 'Red'
    Say "Review log: $logFile" 'Yellow'
    $script:Failure = $_
}
finally {
    if ($script:changedAnything) {
        if (@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count -eq 0) {
            try { Restore-Session }
            catch {
                Say ('RECOVERY REQUIRED: ' + $_.Exception.Message + ' | Re-run this script with -Recover.') 'Red'
                $script:Failure = $_
            }
        }
        else {
            Say 'Unreal remains open. Leaving the no-save guard intact. After closing run this launcher with -Recover.' 'Yellow'
        }
    }
}

if ($null -ne $script:Failure) { throw $script:Failure }