@echo off
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" update-renderer %*
set "ocarina_exit=%errorlevel%"
pause
exit /b %ocarina_exit%
