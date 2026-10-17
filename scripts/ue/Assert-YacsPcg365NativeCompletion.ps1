#requires -Version 7.4
# Exact native producer exit proof for the historical #365 saved review stage.
# Keep the type boundary narrow: ConvertFrom-Json emits Int64 for JSON integers
# on supported PowerShell versions, though some readers expose Int32.
function Assert-YacsPcg365NativeCompletion {
    param(
        [Parameter(Mandatory)][psobject]$Receipt,
        [Parameter(Mandatory)][string]$ExpectedHead
    )
    $isInteger = ($Receipt.exit_code -is [int]) -or ($Receipt.exit_code -is [long])
    if (
        $Receipt.action -cne 'collection-contact-review' -or
        $Receipt.code_sha -cne $ExpectedHead -or
        -not $isInteger -or $Receipt.exit_code -ne 0 -or
        $Receipt.staged_bytes_unchanged -isnot [bool] -or
        $Receipt.staged_bytes_unchanged -ne $true -or
        $Receipt.proof_admission -cne 'LOCAL_DIAGNOSTIC_ONLY'
    ) {
        throw 'Historical native GPU producer lacks clean exit proof'
    }
}
