@echo off
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\reparar-acesso.ps1" %*
set "ocarina_exit=%errorlevel%"
pause
exit /b %ocarina_exit%
