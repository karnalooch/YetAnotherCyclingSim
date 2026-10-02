Set-StrictMode -Version Latest

function ConvertFrom-YacsRunnerLine {
    param([string]$Line)
    # Only listener terminal records are job authority. Worker step successes are not.
    if ($Line -notmatch 'INFO Terminal\] WRITE LINE:') { return }
    if ($Line -match 'Running job: (.+)$') {
        return [pscustomobject]@{ Kind = 'started'; Job = $Matches[1]; Result = '' }
    }
    if ($Line -match 'Job (.+) completed with result: (\w+)\s*$') {
        return [pscustomobject]@{ Kind = 'completed'; Job = $Matches[1]; Result = $Matches[2] }
    }
}

function Read-YacsLogDelta {
    param([string]$Path, [hashtable]$Cursor)
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite,Delete')
    try {
        if (-not $Cursor.ContainsKey('Offset') -or $stream.Length -lt $Cursor.Offset) {
            $Cursor.Offset = 0L
            $Cursor.Pending = ''
            $Cursor.Decoder = [Text.Encoding]::UTF8.GetDecoder()
        }
        [void]$stream.Seek($Cursor.Offset, 'Begin')
        $bytes = [byte[]]::new(262144)
        $count = $stream.Read($bytes, 0, $bytes.Length)
        $Cursor.Offset = $stream.Position
        $chars = [char[]]::new(262144)
        $n = $Cursor.Decoder.GetChars($bytes, 0, $count, $chars, 0, $false)
        $text = $Cursor.Pending + [string]::new($chars, 0, $n)
        $parts = $text.Split("`n")
        $Cursor.Pending = $parts[-1]
        # Bound memory even if an unrelated diagnostic record is malformed.
        if ($Cursor.Pending.Length -gt 65536) { $Cursor.Pending = '' }
        for ($i = 0; $i -lt $parts.Length - 1; $i++) { $parts[$i].TrimEnd("`r") }
    } finally { $stream.Dispose() }
}

function Write-YacsMonitorRecord {
    param([string]$Directory, [hashtable]$Record)
    [void][IO.Directory]::CreateDirectory($Directory)
    $path = Join-Path $Directory 'monitor.jsonl'
    if ((Test-Path $path) -and (Get-Item $path).Length -ge 2MB) {
        for ($i = 4; $i -ge 1; $i--) {
            $old = Join-Path $Directory "monitor.$i.jsonl"
            if (Test-Path $old) { Move-Item $old (Join-Path $Directory "monitor.$($i + 1).jsonl") -Force }
        }
        Move-Item $path (Join-Path $Directory 'monitor.1.jsonl') -Force
    }
    $Record.utc = [DateTime]::UtcNow.ToString('o')
    Add-Content -LiteralPath $path -Value ($Record | ConvertTo-Json -Compress) -Encoding utf8
}
Export-ModuleMember -Function ConvertFrom-YacsRunnerLine, Read-YacsLogDelta, Write-YacsMonitorRecord
