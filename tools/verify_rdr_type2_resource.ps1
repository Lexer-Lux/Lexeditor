$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$cliRoot = Join-Path $root 'tools\magic-rdr\cli'
$appRoot = Join-Path $root 'tools\magic-rdr\app'
& (Join-Path $cliRoot 'build.ps1') | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Rpf6ReadCli build failed' }

$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
$fixtureSource = Join-Path $cliRoot 'Rsc85Type2Fixture.cs'
$fixtureExe = Join-Path $appRoot ('Rsc85Type2Fixture-test-' + [guid]::NewGuid().ToString('N') + '.exe')
$fixtureConfig = $fixtureExe + '.config'
$references = @(
    (Join-Path $appRoot 'MagicRDR.exe'),
    (Join-Path $appRoot 'Assemblies\PikIO.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_MSIL\WindowsBase\v4.0_4.0.0.0__31bf3856ad364e35\WindowsBase.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_32\PresentationCore\v4.0_4.0.0.0__31bf3856ad364e35\PresentationCore.dll'),
    (Join-Path $env:WINDIR 'Microsoft.NET\assembly\GAC_MSIL\PresentationFramework\v4.0_4.0.0.0__31bf3856ad364e35\PresentationFramework.dll')
)
& $compiler /nologo /target:exe /platform:x86 /optimize+ "/out:$fixtureExe" /reference:System.Core.dll /reference:System.Windows.Forms.dll ($references | ForEach-Object { "/reference:$_" }) $fixtureSource
if ($LASTEXITCODE -ne 0) { throw 'Encrypted fixture compiler failed' }
Copy-Item -LiteralPath (Join-Path $appRoot 'Rpf6ReadCli.exe.config') -Destination $fixtureConfig -Force

$temp = Join-Path $env:TEMP ('lexeditor-rdr-type2-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $temp | Out-Null
try {
    $original = Join-Path $temp 'original.raw'
    $candidate = Join-Path $temp 'candidate.raw'
    $template = Join-Path $temp 'template.wsc'
    $packed = Join-Path $temp 'candidate.wsc'
    $unpackedTemplate = Join-Path $temp 'template-unpacked.raw'
    $unpackedCandidate = Join-Path $temp 'candidate-unpacked.raw'
    $bytes = New-Object byte[] 4096
    for ($i = 0; $i -lt $bytes.Length; $i++) { $bytes[$i] = [byte](($i * 37 + 11) -band 255) }
    [IO.File]::WriteAllBytes($original, $bytes)
    $changed = [byte[]]$bytes.Clone()
    $changed[762 % 4096] = $changed[762 % 4096] -bxor 0x5A
    $changed[2048] = $changed[2048] -bxor 0xA5
    [IO.File]::WriteAllBytes($candidate, $changed)

    Push-Location $appRoot
    try { & $fixtureExe $template $original } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create encrypted RSC85 type-2 fixture' }
    $header = [IO.File]::ReadAllBytes($template)
    if ([BitConverter]::ToUInt32($header, 0) -ne 0x85435352 -or [BitConverter]::ToInt32($header, 4) -ne 2) {
        throw 'Synthetic WSC header is not RSC85 type 2'
    }

    $cli = Join-Path $appRoot 'Rpf6ReadCli.exe'
    Push-Location $appRoot
    try {
        & $cli resource-unpack $template $unpackedTemplate
        if ($LASTEXITCODE -ne 0) { throw 'resource-unpack rejected encrypted type-2 template' }
        & $cli resource-pack $template $candidate $packed
        if ($LASTEXITCODE -ne 0) { throw 'resource-pack rejected encrypted type-2 template' }
        & $cli resource-unpack $packed $unpackedCandidate
        if ($LASTEXITCODE -ne 0) { throw 'resource-unpack rejected repacked type-2 resource' }
    } finally { Pop-Location }

    if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($unpackedTemplate), [byte[]]$bytes)) {
        throw 'Encrypted template did not decrypt/decompress exactly'
    }
    if (-not [Linq.Enumerable]::SequenceEqual([byte[]][IO.File]::ReadAllBytes($unpackedCandidate), [byte[]]$changed)) {
        throw 'Encrypted repack did not decrypt/decompress to the candidate bytes'
    }
    $packedHeader = [IO.File]::ReadAllBytes($packed)
    if ([BitConverter]::ToInt32($packedHeader, 4) -ne 2) { throw 'Repack lost WSC resource type 2' }
    Write-Host 'PASS RDR encrypted WSC resource: type-2 AES/Zstandard unpack, repack and exact readback'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixtureExe -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $fixtureConfig -Force -ErrorAction SilentlyContinue
}
exit 0
