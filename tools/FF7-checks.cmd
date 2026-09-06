@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "CHECK_PYTHON=%LEXEDITOR_CHECK_PYTHON%"
if defined CHECK_PYTHON goto python_ready
set "CHECK_PYTHON=%CD%\.venv\Scripts\python.exe"
if exist "%CHECK_PYTHON%" goto python_ready
set "CHECK_PYTHON=python"
:python_ready
echo FF7 installed-data checks. Only disposable project files are written.
"%CHECK_PYTHON%" tools\verify_ff7_installed.py %*
set "CHECK_RESULT=%ERRORLEVEL%"
echo This does not deploy a mod or validate gameplay or sound selection.
if not "%CHECK_RESULT%"=="0" pause
popd
exit /b %CHECK_RESULT%
