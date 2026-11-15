@echo off
cd /d "%~dp0..\"
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" maintain-build %*
set "akyno_status=%errorlevel%"
pause
exit /b %akyno_status%
