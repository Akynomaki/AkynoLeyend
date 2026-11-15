@echo off
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" run --trace-lighting --collect-crash %*
set "ocarina_exit=%errorlevel%"
if not "%ocarina_exit%"=="0" pause
exit /b %ocarina_exit%
