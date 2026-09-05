$ErrorActionPreference = 'Stop'

$appRoot = 'C:\Lexeditor'
$launcher = Join-Path $appRoot 'Lexeditor.cmd'
$appScript = Join-Path $appRoot 'app.py'
$icon = Join-Path $appRoot 'assets\lexeditor.ico'
$venvRoot = Join-Path $appRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
$venvPythonWindow = Join-Path $venvRoot 'Scripts\pythonw.exe'
$requirements = Join-Path $appRoot 'requirements.txt'
$desktop = [Environment]::GetFolderPath('Desktop')
$startMenu = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Lexeditor launcher not found: $launcher"
}
if (-not (Test-Path -LiteralPath $icon)) {
    throw "Lexeditor icon not found: $icon"
}
if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv $venvRoot
}
$dependencyReady = $false
try {
    & $venvPython -c "import PIL, fontTools, texfury, webview; from importlib.metadata import version; raise SystemExit(0 if version('pywebview') == '6.2.1' else 1)" 2>$null
    $dependencyReady = $LASTEXITCODE -eq 0
} catch {
    $dependencyReady = $false
}
if (-not $dependencyReady) {
    & $venvPython -m pip install --disable-pip-version-check -r $requirements
}

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
    (Join-Path $desktop 'Lexeditor.lnk'),
    (Join-Path $startMenu 'Lexeditor.lnk')
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $venvPythonWindow
    $shortcut.Arguments = "`"$appScript`""
    $shortcut.WorkingDirectory = $appRoot
    $shortcut.Description = "Edit Lexer's game mod data"
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Save()
}

Write-Host "Installed Lexeditor shortcuts:"
Write-Host "  $(Join-Path $desktop 'Lexeditor.lnk')"
Write-Host "  $(Join-Path $startMenu 'Lexeditor.lnk')"
Write-Host "Embedded desktop runtime: $venvPythonWindow"
