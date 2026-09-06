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
set "CHECK_REPORT=%TEMP%\Lexeditor-warband-checks-%RANDOM%.txt"
echo Warband disposable fixture checks > "%CHECK_REPORT%"
echo No installed game or module is modified. >> "%CHECK_REPORT%"
"%CHECK_PYTHON%" -c "import PIL, fontTools" >> "%CHECK_REPORT%" 2>&1
if errorlevel 1 goto failed
"%CHECK_PYTHON%" -m unittest discover -s tests -p "test_warband*.py" -v >> "%CHECK_REPORT%" 2>&1
if errorlevel 1 goto failed
"%CHECK_PYTHON%" -m unittest discover -s tests -p "test_data_map_coverage.py" -v >> "%CHECK_REPORT%" 2>&1
if errorlevel 1 goto failed
"%CHECK_PYTHON%" -m unittest discover -s tests -p "test_wse2*.py" -v >> "%CHECK_REPORT%" 2>&1
if errorlevel 1 goto failed
type "%CHECK_REPORT%"
echo Report: %CHECK_REPORT%
if /i "%~1"=="--checks-only" goto passed
call Lexeditor.cmd --game warband
:passed
popd
exit /b 0
:failed
type "%CHECK_REPORT%"
echo Checks failed. Report: %CHECK_REPORT%
echo Run this from an existing Lexeditor installation with its normal dependencies.
if /i not "%~1"=="--checks-only" pause
popd
exit /b 1
