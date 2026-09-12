[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [string]$OutputPath = (Join-Path $PSScriptRoot "install-verification.json")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

Push-Location $repoRoot
try {
    $jsonLines = & python -m games.ffx_x2.verify_install `
        --game-root $resolvedGameRoot `
        --require-fahrenheit `
        --hash-archives `
        --json
    $exitCode = $LASTEXITCODE
    $jsonText = $jsonLines -join [Environment]::NewLine

    if ([string]::IsNullOrWhiteSpace($jsonText)) {
        throw "FFX/X-2 verifier produced no JSON output."
    }

    [System.IO.File]::WriteAllText(
        $resolvedOutput,
        $jsonText + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )

    try {
        $report = $jsonText | ConvertFrom-Json
    }
    catch {
        throw "FFX/X-2 verifier output was not valid JSON. Raw output was saved to $resolvedOutput"
    }

    if ($report.contract -ne "Lexeditor.ffx-x2-install-verification") {
        throw "Unexpected verifier contract '$($report.contract)'. Raw output was saved to $resolvedOutput"
    }

    if ($exitCode -ne 0) {
        throw "FFX/X-2 verification failed with exit code $exitCode. Report: $resolvedOutput"
    }

    $failedChecks = @(
        $report.acceptanceChecks.PSObject.Properties |
            Where-Object { -not [bool]$_.Value } |
            ForEach-Object { $_.Name }
    )
    if (-not [bool]$report.acceptanceReady -or $failedChecks.Count -ne 0) {
        $detail = if ($failedChecks.Count) { $failedChecks -join ", " } else { "acceptanceReady=false" }
        throw "Verifier passed its ordinary checks, but draft-exit evidence is incomplete: $detail. Report: $resolvedOutput"
    }

    Write-Host "FFX/X-2 real-install verifier PASS"
    Write-Host "Acceptance JSON: $resolvedOutput"
    Write-Host "Both installed VBF hashes and Fahrenheit launch prerequisites are present."
}
finally {
    Pop-Location
}
