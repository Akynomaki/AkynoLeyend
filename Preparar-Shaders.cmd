@echo off
"%~dp0ferramentas\python\python.exe" -I -X utf8 "%~dp0manage.py" prepare-shaders %*
set "ocarina_exit=%errorlevel%"
if not "%ocarina_exit%"=="0" pause
exit /b %ocarina_exit%
