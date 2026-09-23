$ErrorActionPreference = "Stop"

$Repo = if ($env:LEXEDITOR_RDR2_PROJECT) { $env:LEXEDITOR_RDR2_PROJECT } else { 'C:\RDR2Mod' }
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$Toolkit = Join-Path $Repo "_downloads\RDR2TextureTool-v1.1.3"
$Converter = Join-Path $env:LOCALAPPDATA "RedM\RedM.app\CitiCon.com"
$Build = Join-Path $PSScriptRoot "build_casing_generic_textures"
$Dds = Join-Path $Build "dds"
$Builder = Join-Path $Build "BuildYtd.exe"
$GtaYtd = Join-Path $Build "generic_textures.ytd"
$FinalYtd = Join-Path $PSScriptRoot "generic_textures.ytd"

if (!(Test-Path $Toolkit)) { throw "RDR2 Texture Toolkit v1.1.3 is required at $Toolkit" }
if (!(Test-Path $Converter)) { throw "RedM CitiCon converter is required at $Converter" }
New-Item -ItemType Directory -Force $Build | Out-Null

python (Join-Path $PSScriptRoot "prepare_casing_generic_textures.py") --output $Dds
if ($LASTEXITCODE) { throw "DDS preparation failed" }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$rage = Join-Path $Toolkit "RageLib.dll"
$rageGta = Join-Path $Toolkit "RageLib.GTA5.dll"
$builderSource = Join-Path $PSScriptRoot "BuildYtdDirectory.cs"
& $csc /nologo /target:exe /out:$Builder "/reference:$rage" "/reference:$rageGta" $builderSource
if ($LASTEXITCODE) { throw "BuildYtd compilation failed" }
Copy-Item (Join-Path $Toolkit "*.dll") $Build -Force

& $Builder $GtaYtd $Dds
if ($LASTEXITCODE) { throw "GTA-format YTD build failed" }
Push-Location (Split-Path $Converter)
try { & $Converter formats:convert $GtaYtd } finally { Pop-Location }
if ($LASTEXITCODE) { throw "RDR2 YTD conversion failed" }

$converted = Get-ChildItem $Build -Filter "generic_textures*_nya.ytd" |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$converted) { throw "CitiCon did not produce an RDR2 _nya.ytd" }
Copy-Item $converted.FullName $FinalYtd -Force
Copy-Item $FinalYtd (Join-Path $Repo "MyOverhaul\stream\generic_textures.ytd") -Force
Write-Output "Built complete 49-texture GENERIC_TEXTURES replacement: $FinalYtd"
