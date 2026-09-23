$ErrorActionPreference = "Stop"

$Repo = if ($env:LEXEDITOR_RDR2_PROJECT) { $env:LEXEDITOR_RDR2_PROJECT } else { 'C:\RDR2Mod' }
$Repo = (Resolve-Path -LiteralPath $Repo).Path
$Toolkit = Join-Path $Repo "_downloads\RDR2TextureTool-v1.1.3"
$Converter = Join-Path $env:LOCALAPPDATA "RedM\RedM.app\CitiCon.com"
$Build = Join-Path $PSScriptRoot "build"
$Builder = Join-Path $Build "BuildYtd.exe"
$GtaYtd = Join-Path $Build "LEX_INVENTORY_ITEMS.ytd"
$FinalYtd = Join-Path $PSScriptRoot "LEX_INVENTORY_ITEMS.ytd"
$ModStream = Join-Path $Repo "MyOverhaul\stream"

if (!(Test-Path $Toolkit)) { throw "RDR2 Texture Toolkit v1.1.3 is required at $Toolkit" }
if (!(Test-Path $Converter)) { throw "RedM's CitiCon converter is required at $Converter" }

python (Join-Path $PSScriptRoot "prepare_inventory_dds.py")
New-Item -ItemType Directory -Force $Build | Out-Null

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$rage = Join-Path $Toolkit "RageLib.dll"
$rageGta = Join-Path $Toolkit "RageLib.GTA5.dll"
$builderSource = Join-Path $Repo "GameplayTweaks\icons\tools\BuildYtd.cs"
& $csc /nologo /target:exe /out:$Builder `
    "/reference:$rage" `
    "/reference:$rageGta" `
    $builderSource
if ($LASTEXITCODE) { throw "BuildYtd compilation failed" }

Copy-Item (Join-Path $Toolkit "*.dll") $Build -Force
$dds = Get-ChildItem (Join-Path $Build "dds") -Filter *.dds | Sort-Object Name | ForEach-Object FullName
& $Builder $GtaYtd @dds
if ($LASTEXITCODE) { throw "GTA-format YTD build failed" }

Push-Location (Split-Path $Converter)
try { & $Converter formats:convert $GtaYtd } finally { Pop-Location }
if ($LASTEXITCODE) { throw "RDR2 YTD conversion failed" }

$converted = Get-ChildItem $Build -Filter "LEX_INVENTORY_ITEMS*_nya.ytd" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$converted) { throw "CitiCon did not produce an RDR2 _nya.ytd" }
Copy-Item $converted.FullName $FinalYtd -Force

# Repo copy, for version control.
New-Item -ItemType Directory -Force $ModStream | Out-Null
Copy-Item $FinalYtd (Join-Path $ModStream "LEX_INVENTORY_ITEMS.ytd") -Force

# LIVE copy. LML streams from the TOP-LEVEL lml\stream folder only; a `stream`
# subfolder inside a mod is never read (see Worklog #147/#193). This script used
# to stop at the repo copy above, so every rebuild silently had no effect in
# game and the icons stayed blank.
$GameStream = "C:\Program Files (x86)\Steam\steamapps\common\Red Dead Redemption 2\lml\stream"
if (Test-Path (Split-Path $GameStream)) {
    New-Item -ItemType Directory -Force $GameStream | Out-Null
    Copy-Item $FinalYtd (Join-Path $GameStream "LEX_INVENTORY_ITEMS.ytd") -Force
    Write-Output "Built $FinalYtd; installed to $ModStream and $GameStream"
} else {
    Write-Warning "lml folder not found - repo copy only, NOT installed to the game"
}
