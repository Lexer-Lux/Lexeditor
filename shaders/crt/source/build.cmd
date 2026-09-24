@echo off
rem Build the Lexer CRT add-on and its offscreen checks.
rem   build.cmd <sdk> <out>
rem <sdk> holds include\ (ReShade 6.8 add-on headers), imgui\ (imgui.h and
rem imconfig.h at ReShade 6.8's ImGui commit 3912b3d9, 1.92.5 docking) and
rem librashader\ (librashader.h and librashader.dll.lib, 0.12).
setlocal
if "%~2"=="" (echo usage: build.cmd ^<sdk^> ^<out^> & exit /b 64)
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "SRC=%~dp0"
set "SDK=%~1"
set "OUT=%~2"
if not exist "%OUT%" mkdir "%OUT%"
pushd "%OUT%"
cl /nologo /LD /EHsc /std:c++17 /O2 /MT /DRESHADE_ADDON=1 "%SRC%addon.cpp" /I "%SRC%." /I "%SDK%\include" /I "%SDK%\imgui" /I "%SDK%\librashader" /Fe:LexerCRT.addon64 /link "%SDK%\librashader\librashader.dll.lib" d3d11.lib || goto fail
cl /nologo /EHsc /std:c++17 /O2 /MT "%SRC%settings_probe.cpp" /I "%SRC%." /I "%SDK%\librashader" /Fe:settings_probe.exe /link "%SDK%\librashader\librashader.dll.lib" d3d11.lib || goto fail
cl /nologo /EHsc /std:c++17 /O2 /MT "%SRC%render_probe.cpp" /I "%SRC%." /I "%SDK%\librashader" /Fe:render_probe.exe /link "%SDK%\librashader\librashader.dll.lib" d3d11.lib || goto fail
popd
exit /b 0
:fail
popd
exit /b 1
