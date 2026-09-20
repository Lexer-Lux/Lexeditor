@echo off
setlocal
set "CL=/DGAMEPLAYTWEAKS_DEV_MODE=1 %CL%"
echo Building GameplayTweaks with development-only features enabled.
call "%~dp0build.bat"
exit /b %errorlevel%
