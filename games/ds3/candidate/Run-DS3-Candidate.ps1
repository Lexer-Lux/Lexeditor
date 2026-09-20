$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root '.venv-ds3-candidate'
$Python = Join-Path $Venv 'Scripts\python.exe'
$Pythonw = Join-Path $Venv 'Scripts\pythonw.exe'
$Requirements = Join-Path $Root 'requirements.txt'
$Candidate = Join-Path $Root 'ds3_candidate.py'

if ((Resolve-Path $Root).Path.TrimEnd('\') -ieq 'C:\Lexeditor') {
    throw 'Extract this candidate to a NEW folder. Do not run it from C:\Lexeditor.'
}

if (-not (Test-Path -LiteralPath $Python)) {
    $Py = Get-Command py -ErrorAction SilentlyContinue
    if ($Py) {
        & py -3 -m venv $Venv
    } else {
        $SystemPython = Get-Command python -ErrorAction Stop
        & $SystemPython.Source -m venv $Venv
    }
    & $Python -m pip install --disable-pip-version-check -r $Requirements
}

& $Python $Candidate --check
if ($LASTEXITCODE -ne 0) {
    throw 'The DS3 candidate self-check failed.'
}

Start-Process -FilePath $Pythonw -ArgumentList @($Candidate) -WorkingDirectory $Root
