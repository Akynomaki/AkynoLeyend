@echo off
setlocal
rem Escala interna experimental. Nao equivale ao mod Max Resolution do emulador.
echo AkynoLeyend: escala 125%% experimental. Exige o host 0.4.2 recompilado.
"%~dp0..\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\manage.py" run --require-current-build --resolution 125 --upscaling lanczos --framegen 0 %*
set "akyno_status=%errorlevel%"
if not "%akyno_status%"=="0" pause
exit /b %akyno_status%
