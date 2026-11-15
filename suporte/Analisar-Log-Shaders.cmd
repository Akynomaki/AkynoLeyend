@echo off
setlocal
if "%~1"=="" (
  echo Uso: arraste um arquivo de log para Analisar-Log-Shaders.cmd
  echo ou execute: Analisar-Log-Shaders.cmd "caminho\saida.log"
  pause
  exit /b 2
)
if not exist "%~1" (
  echo Arquivo nao encontrado: "%~1"
  pause
  exit /b 2
)
"%~dp0..\ferramentas\python\python.exe" -I "%~dp0..\tools\analisar_log_shaders.py" "%~1" --json-out "%~dpn1-resumo-shaders.json"
set "code=%errorlevel%"
if not "%code%"=="0" pause
exit /b %code%
