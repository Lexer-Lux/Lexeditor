@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not defined RDR2_SDK_ROOT goto :missing_sdk
if not exist "%RDR2_SDK_ROOT%\inc\natives.h" goto :missing_sdk
if not exist "%RDR2_SDK_ROOT%\inc\main.h" goto :missing_sdk
if not exist "%RDR2_SDK_ROOT%\lib\ScriptHookRDR2.lib" goto :missing_sdk

if defined VCVARS64 goto :toolchain
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" for /f "usebackq tokens=*" %%I in (`"%VSWHERE%" -latest -products * -version [17.0^,18.0^) -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VCVARS64=%%I\VC\Auxiliary\Build\vcvars64.bat"
if defined VCVARS64 goto :toolchain
set "VCVARS64=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"

:toolchain
if not exist "%VCVARS64%" goto :missing_toolchain
call "%VCVARS64%" >nul
if errorlevel 1 goto :failed
if not exist ".build" mkdir ".build"
if errorlevel 1 goto :failed

rem Topic modules are included by script.cpp; compile the two translation units only.
cl /nologo /O2 /EHsc /MT /LD main.cpp script.cpp third_party\minhook\src\buffer.c third_party\minhook\src\hook.c third_party\minhook\src\trampoline.c third_party\minhook\src\hde\hde64.c /Fo.build\ /I "%RDR2_SDK_ROOT%\inc" /I third_party\minhook\include /I third_party\minhook\src /link "%RDR2_SDK_ROOT%\lib\ScriptHookRDR2.lib" user32.lib xinput.lib /OUT:.build\GameplayTweaks.asi /MAP:.build\GameplayTweaks.map /IMPLIB:.build\GameplayTweaks.lib
if errorlevel 1 goto :failed

echo Built "%CD%\.build\GameplayTweaks.asi"
popd
endlocal & exit /b 0

:missing_sdk
echo ERROR: Set RDR2_SDK_ROOT to an RDR2 SDK directory with inc and lib. 1>&2
popd
endlocal & exit /b 2

:missing_toolchain
echo ERROR: VS2022 C++ x64 tools were not found. Set VCVARS64 to vcvars64.bat. 1>&2
popd
endlocal & exit /b 3

:failed
set "BUILD_EXIT=%errorlevel%"
if "%BUILD_EXIT%"=="0" set "BUILD_EXIT=1"
popd
endlocal & exit /b %BUILD_EXIT%
