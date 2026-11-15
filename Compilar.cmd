@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0compilar.ps1" %*
set "ocarina_exit=%errorlevel%"
if not "%ocarina_exit%"=="0" pause
exit /b %ocarina_exit%
