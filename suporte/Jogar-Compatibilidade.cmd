@echo off
cd /d "%~dp0..\"
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" run --profile compatibilidade --trace-runtime --collect-crash %*
set "akyno_status=%errorlevel%"
pause
exit /b %akyno_status%
