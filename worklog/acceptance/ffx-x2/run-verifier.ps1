[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,

    [string]$OutputPath = (Join-Path $PSScriptRoot "install-verification.json"),

    [string]$BaselinePath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$baseline = $null
$resolvedBaseline = ""
if (-not [string]::IsNullOrWhiteSpace($BaselinePath)) {
    $resolvedBaseline = (Resolve-Path -LiteralPath $BaselinePath).Path
    if ([System.StringComparer]::OrdinalIgnoreCase.Equals($resolvedBaseline, $resolvedOutput)) {
        throw "OutputPath must differ from BaselinePath so the baseline cannot be overwritten."
    }
    try {
        $baseline = Get-Content -LiteralPath $resolvedBaseline -Raw | ConvertFrom-Json
    }
    catch {
        throw "Baseline report is not valid JSON: $resolvedBaseline"
    }
    if ($baseline.contract -ne "Lexeditor.ffx-x2-install-verification") {
        throw "Unexpected baseline verifier contract '$($baseline.contract)': $resolvedBaseline"
    }
    if (-not [bool]$baseline.acceptanceReady) {
        throw "Baseline report did not pass the strict real-install verifier baseline: $resolvedBaseline"
    }
    if (-not [System.StringComparer]::OrdinalIgnoreCase.Equals([string]$baseline.gameRoot, $resolvedGameRoot)) {
        throw "Baseline report belongs to a different game root ('$($baseline.gameRoot)'): $resolvedBaseline"
    }
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
        throw "Verifier passed its ordinary checks, but the strict real-install baseline is incomplete: $detail. Report: $resolvedOutput"
    }

    if ($null -ne $baseline) {
        foreach ($game in @("x", "x2")) {
            $before = $baseline.archives.$game
            $after = $report.archives.$game
            foreach ($field in @("headerMd5", "sha256")) {
                $beforeValue = [string]$before.$field
                $afterValue = [string]$after.$field
                if ([string]::IsNullOrWhiteSpace($beforeValue) -or [string]::IsNullOrWhiteSpace($afterValue)) {
                    throw "Cannot compare $game $field because one report is missing it. Baseline: $resolvedBaseline; current: $resolvedOutput"
                }
                if ($beforeValue -ne $afterValue) {
                    throw "Installed $game archive changed: $field differs from baseline. Baseline: $resolvedBaseline; current: $resolvedOutput"
                }
            }
        }
        Write-Host "Installed VBF immutability comparison PASS"
        Write-Host "Baseline JSON: $resolvedBaseline"
    }

    Write-Host "FFX/X-2 real-install verifier PASS"
    Write-Host "Acceptance JSON: $resolvedOutput"
    Write-Host "Both installed VBF hashes and Fahrenheit launch prerequisites are present."
}
finally {
    Pop-Location
}
