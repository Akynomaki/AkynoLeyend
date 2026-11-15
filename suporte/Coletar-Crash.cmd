@echo off
"%~dp0..\ferramentas\python\python.exe" -I "%~dp0..\manage.py" collect-crash %*
set "ocarina_exit=%errorlevel%"
echo.
pause
exit /b %ocarina_exit%
