@echo off
rem Limites opcionais de cache/compile; nao muda shaders nem o jogo.
"%~dp0..\ferramentas\python\python.exe" -I "%~dp0..\manage.py" run --cache-mode equilibrado %*
set "akyno_exit=%errorlevel%"
if not "%akyno_exit%"=="0" pause
exit /b %akyno_exit%
