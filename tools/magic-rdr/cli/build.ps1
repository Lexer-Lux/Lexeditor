$ErrorActionPreference = "Stop"

$toolRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $toolRoot "app"
$source = Join-Path $PSScriptRoot "Rpf6ReadCli.cs"
$output = Join-Path $appRoot "Rpf6ReadCli.exe"
$compiler = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
$references = @(
    (Join-Path $appRoot "MagicRDR.exe"),
    (Join-Path $appRoot "Assemblies\PikIO.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_MSIL\WindowsBase\v4.0_4.0.0.0__31bf3856ad364e35\WindowsBase.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_32\PresentationCore\v4.0_4.0.0.0__31bf3856ad364e35\PresentationCore.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_MSIL\PresentationFramework\v4.0_4.0.0.0__31bf3856ad364e35\PresentationFramework.dll")
)

foreach ($required in @($compiler, $source) + $references) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing build input: $required"
    }
}

$compilerArguments = @(
    "/nologo",
    "/target:exe",
    "/platform:x86",
    "/optimize+",
    "/out:$output",
    "/reference:System.Core.dll",
    "/reference:System.Windows.Forms.dll"
) + ($references | ForEach-Object { "/reference:$_" }) + @($source)

& $compiler $compilerArguments
if ($LASTEXITCODE -ne 0) {
    throw "Rpf6ReadCli compilation failed with exit code $LASTEXITCODE"
}

Get-FileHash -LiteralPath $output -Algorithm SHA256
