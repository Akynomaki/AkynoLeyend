@echo off
setlocal
"%~dp0ferramentas\python\python.exe" -I -X utf8 "%~dp0manage.py" run --require-current-build %*
set "akyno_status=%errorlevel%"
if not "%akyno_status%"=="0" pause
exit /b %akyno_status%
