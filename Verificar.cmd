@echo off
"%~dp0ferramentas\python\python.exe" -I "%~dp0manage.py" doctor %*
set "ocarina_exit=%errorlevel%"
pause
exit /b %ocarina_exit%
