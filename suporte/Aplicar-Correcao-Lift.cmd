@echo off
setlocal EnableExtensions DisableDelayedExpansion
title AkynoLeyend - Aplicar correcao da traducao
if not exist "%~dp0..\tools\reparar_lift.py" goto unzip_first
if not exist "%~dp0..\third_party\a64-kit\lift\a64_lift.py" goto unzip_first
set "akyno_repair_root=%~1"
if not defined akyno_repair_root if exist "%~dp0..\AkynoLeyendBuilder.exe" set "akyno_repair_root=%~dp0..\"
if not defined akyno_repair_root if exist "%USERPROFILE%\Downloads\AkynoLeyend-0.4.2-Candidato-Windows\AkynoLeyend-0.4.2\AkynoLeyendBuilder.exe" set "akyno_repair_root=%USERPROFILE%\Downloads\AkynoLeyend-0.4.2-Candidato-Windows\AkynoLeyend-0.4.2"
if not defined akyno_repair_root (
  echo Cole o caminho da pasta que contem AkynoLeyendBuilder.exe.
  set /p "akyno_repair_root=Pasta: "
)
if not defined akyno_repair_root goto no_folder
set "akyno_repair_root=%akyno_repair_root:"=%"
if not exist "%akyno_repair_root%\ferramentas\python\python.exe" goto no_python
echo Feche o Builder antes de aplicar a correcao.
"%akyno_repair_root%\ferramentas\python\python.exe" -I -X utf8 "%~dp0..\tools\reparar_lift.py" --root "%akyno_repair_root%\." --payload "%~dp0..\third_party\a64-kit\lift\a64_lift.py"
set "akyno_repair_exit=%errorlevel%"
echo.
pause
exit /b %akyno_repair_exit%
:no_folder
echo Nenhuma pasta foi informada.
pause
exit /b 1
:no_python
echo Python do pacote nao encontrado em "%akyno_repair_root%\ferramentas\python\python.exe".
echo Execute este CMD arrastando a pasta AkynoLeyend-0.4.2 sobre ele.
pause
exit /b 1
:unzip_first
echo Extraia o ZIP inteiro antes de executar este CMD.
pause
exit /b 1
