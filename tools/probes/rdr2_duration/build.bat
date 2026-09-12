@echo off
setlocal
if "%~1"=="" exit /b 2
if "%~2"=="" exit /b 2
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b 1
cl /nologo /O2 /EHsc /MT /LD "%~dp0probe.cpp" /I "%~1\inc" /Fo"%~2\DurationProbe.obj" /link "%~1\lib\ScriptHookRDR2.lib" user32.lib /OUT:"%~2\DurationProbe.asi" /IMPLIB:"%~2\DurationProbe.lib"
exit /b %errorlevel%
