@echo off
set "LEXEDITOR_ROOT=%~dp0"
if not exist "%LEXEDITOR_ROOT%.venv\Scripts\pythonw.exe" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LEXEDITOR_ROOT%install.ps1"
start "" "%LEXEDITOR_ROOT%.venv\Scripts\pythonw.exe" "%LEXEDITOR_ROOT%app.py" %*
