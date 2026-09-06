$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cliRoot = Join-Path $root 'tools\magic-rdr\cli'
$appRoot = Join-Path $root 'tools\magic-rdr\app'
& (Join-Path $cliRoot 'build.ps1') | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Rpf6ReadCli build failed" }

$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
$fixtureSource = Join-Path $cliRoot 'Rpf6CopyFixture.cs'
# .NET Framework probes referenced private assemblies beside the executable,
# not from the process working directory. Build this fixture beside MagicRDR.exe
# and give it the same private-path probing config as the bridge.
$fixtureExe = Join-Path $appRoot ('Rpf6CopyFixture-test-' + [guid]::NewGuid().ToString('N') + '.exe')
$fixtureConfig = $fixtureExe + '.config'
$references = @(
    (Join-Path $appRoot 'MagicRDR.exe'),
    (Join-Path $appRoot 'Assemblies\PikIO.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_MSIL\WindowsBase\v4.0_4.0.0.0__31bf3856ad364e35\WindowsBase.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_32\PresentationCore\v4.0_4.0.0.0__31bf3856ad364e35\PresentationCore.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_MSIL\PresentationFramework\v4.0_4.0.0.0__31bf3856ad364e35\PresentationFramework.dll')
)
& $compiler /nologo /target:exe /platform:x86 /optimize+ "/out:$fixtureExe" /reference:System.Core.dll /reference:System.Windows.Forms.dll ($references | ForEach-Object { "/reference:$_" }) $fixtureSource
if ($LASTEXITCODE -ne 0) { throw "Fixture compiler failed" }
Copy-Item -LiteralPath (Join-Path $appRoot 'Rpf6ReadCli.exe.config') -Destination $fixtureConfig -Force

function Invoke-ExpectedFailure([scriptblock]$Command) {
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 converts native stderr to a terminating
        # NativeCommandError when ErrorActionPreference is Stop. These calls are
        # deliberately invalid, so allow the process to finish and inspect its code.
        $ErrorActionPreference = 'Continue'
        & $Command
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

$temp = Join-Path $env:TEMP ('lexeditor-rdr-rpf-copy-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $temp | Out-Null
try {
    $before = Join-Path $temp 'before.xml'
    $after = Join-Path $temp 'after.xml'
    $source = Join-Path $temp 'source.rpf'
    $built = Join-Path $temp 'built.rpf'
    $manifest = Join-Path $temp 'replacements.tsv'
    Set-Content -LiteralPath $before -Encoding UTF8 -NoNewline '<root><value>vanilla</value></root>'
    Set-Content -LiteralPath $after -Encoding UTF8 -NoNewline '<root><value>project copy only</value></root>'

    Push-Location $appRoot
    try { & $fixtureExe $source $before } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create synthetic source RPF' }
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    Set-Content -LiteralPath $manifest -Encoding UTF8 -NoNewline ("root/test.xml`t$after")

    $cli = Join-Path $appRoot 'Rpf6ReadCli.exe'
    Push-Location $appRoot
    try { & $cli build-copy $source $built $manifest } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'build-copy rejected the valid synthetic fixture' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) { throw 'build-copy changed its source archive' }
    if (-not (Test-Path -LiteralPath $built)) { throw 'build-copy did not create output archive' }

    $extract = Join-Path $temp 'extract'
    # Synthetic "test.xml" is deliberately not in MagicRDR's real filename hash
    # dictionary, so a reopened RPF names it by hash. Match every file, require the
    # single fixture entry, and verify its bytes instead of relying on display name.
    Push-Location $appRoot
    try { & $cli extract $built $extract '**' } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'built archive did not reopen/extract' }
    $extracted = @(Get-ChildItem -LiteralPath $extract -Recurse -File)
    if ($extracted.Count -ne 1) { throw "rebuilt fixture extracted $($extracted.Count) files instead of one" }
    $actual = [IO.File]::ReadAllBytes($extracted[0].FullName)
    $expected = [IO.File]::ReadAllBytes($after)
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$actual, [byte[]]$expected)) { throw 'built replacement did not round-trip exactly' }

    Push-Location $appRoot
    try { $overwriteExit = Invoke-ExpectedFailure { & $cli build-copy $source $source $manifest 2>$null | Out-Null } } finally { Pop-Location }
    if ($overwriteExit -eq 0) { throw 'build-copy allowed source archive overwrite' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) { throw 'failed overwrite test changed source archive' }

    Set-Content -LiteralPath $manifest -Encoding UTF8 -NoNewline ("root/missing.xml`t$after")
    Remove-Item -LiteralPath $built -Force
    Push-Location $appRoot
    try { $missingExit = Invoke-ExpectedFailure { & $cli build-copy $source $built $manifest 2>$null | Out-Null } } finally { Pop-Location }
    if ($missingExit -eq 0 -or (Test-Path -LiteralPath $built)) { throw 'unknown entry produced an archive' }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) { throw 'unknown-entry test changed source archive' }

    Write-Host 'PASS RDR RPF copy builder: source immutable, replacement exact, invalid targets fail closed'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixtureExe -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixtureConfig -Force -ErrorAction SilentlyContinue
}
