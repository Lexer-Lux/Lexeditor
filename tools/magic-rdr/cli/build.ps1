$ErrorActionPreference = "Stop"

$toolRoot = Split-Path -Parent $PSScriptRoot
$appRoot = Join-Path $toolRoot "app"
$sources = @(
    (Join-Path $PSScriptRoot "Rpf6ReadCli.cs"),
    (Join-Path $PSScriptRoot "DdsWriter.cs")
)
$output = Join-Path $appRoot "Rpf6ReadCli.exe"
$config = $output + '.config'
$compiler = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
$references = @(
    (Join-Path $appRoot "MagicRDR.exe"),
    (Join-Path $appRoot "Assemblies\PikIO.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_MSIL\WindowsBase\v4.0_4.0.0.0__31bf3856ad364e35\WindowsBase.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_32\PresentationCore\v4.0_4.0.0.0__31bf3856ad364e35\PresentationCore.dll"),
    (Join-Path $env:WINDIR "Microsoft.NET\assembly\GAC_MSIL\PresentationFramework\v4.0_4.0.0.0__31bf3856ad364e35\PresentationFramework.dll")
)

foreach ($required in @($compiler) + $sources + $references) {
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
) + ($references | ForEach-Object { "/reference:$_" }) + $sources

& $compiler $compilerArguments
if ($LASTEXITCODE -ne 0) {
    throw "Rpf6ReadCli compilation failed with exit code $LASTEXITCODE"
}

# MagicRDR keeps private dependencies such as PikIO in app\Assemblies. The CLI
# is a separate .NET executable, so it needs its own probing configuration.
@'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <runtime>
    <assemblyBinding xmlns="urn:schemas-microsoft-com:asm.v1">
      <probing privatePath="Assemblies" />
    </assemblyBinding>
  </runtime>
</configuration>
'@ | Set-Content -LiteralPath $config -Encoding UTF8

Get-FileHash -LiteralPath $output -Algorithm SHA256
