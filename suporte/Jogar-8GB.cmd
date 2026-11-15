@echo off
"%~dp0..\ferramentas\python\python.exe" -I "%~dp0..\manage.py" run --profile 8gb %*
set "ocarina_exit=%errorlevel%"
if not "%ocarina_exit%"=="0" pause
exit /b %ocarina_exit%
