function Resolve-YacsPhysicalPath {
    param([Parameter(Mandatory)][string]$Path)
    $absolute = [IO.Path]::GetFullPath($Path)
    $resolved = [IO.Path]::GetPathRoot($absolute)
    foreach ($part in $absolute.Substring($resolved.Length).Split([char[]]@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $resolved = Join-Path $resolved $part
        if (Test-Path -LiteralPath $resolved) {
            $item = Get-Item -LiteralPath $resolved -Force -ErrorAction Stop
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                $link = $item.ResolveLinkTarget($true)
                if ($null -eq $link) { throw "Cannot resolve build path alias: $resolved" }
                $resolved = $link.FullName
            }
        }
    }
    return $resolved
}

function Assert-YacsBuildIsolation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ProjectPath,
        [object[]]$EditorProcesses
    )
    $AutoDiscovered = -not $PSBoundParameters.ContainsKey('EditorProcesses')
    if ($AutoDiscovered) {
        $EditorProcesses = @(
            Get-CimInstance Win32_Process |
                Where-Object Name -in @('UnrealEditor.exe', 'UnrealEditor-Cmd.exe') |
                Where-Object {
                    # Win32_Process can retain a stale CIM record after the native
                    # process is gone. Only auto-discovered Editors that still have
                    # a live native process may own/block a build workspace.
                    $Native = Get-Process -Id ([int]$_.ProcessId) -ErrorAction SilentlyContinue
                    if ($null -eq $Native) {
                        return $false
                    }
                    return $Native.ProcessName -in @('UnrealEditor', 'UnrealEditor-Cmd')
                }
        )
    }
    $target = Resolve-YacsPhysicalPath $ProjectPath
    foreach ($process in $EditorProcesses) {
        $match = [regex]::Match([string]$process.CommandLine, '"(?<project>[^"]+\.uproject)"|(?<project>[^\s"]+\.uproject)', 'IgnoreCase')
        if (-not $match.Success) { throw 'Cannot establish project ownership of a running Unreal Editor.' }
        $open = Resolve-YacsPhysicalPath $match.Groups['project'].Value
        if ($open -ieq $target) { throw "Close the editor for the build workspace before compiling: $target" }
    }
}
