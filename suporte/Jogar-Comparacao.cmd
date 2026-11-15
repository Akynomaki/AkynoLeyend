@echo off
setlocal
echo AkynoLeyend 0.4.2: visual comparison, escala 100%%, nitidez 0, sem quadros gerados.
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" run --require-current-build --visual-mode comparison --profile original --resolution 100 --upscaling lanczos --sharpness 0 --framegen 0 --collect-crash %*
set "akyno_status=%errorlevel%"
if not "%akyno_status%"=="0" pause
exit /b %akyno_status%
