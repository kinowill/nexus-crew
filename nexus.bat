@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "PY=C:\Users\ArtLi\AppData\Roaming\uv\tools\crewai\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%PY%" (
  echo [ERREUR] CrewAI introuvable. Installe-le :
  echo     uv tool install crewai --with crewai-tools --with litellm
  pause
  exit /b 1
)

if "%~1"=="" (
  set /p TASK="Tache NEXUS : "
  set /p PROJECT="Projet (chemin, defaut=.) : "
  if "!PROJECT!"=="" set "PROJECT=."
  "%PY%" "%HERE%crew\crew.py" "!TASK!" --project "!PROJECT!" %*
) else (
  "%PY%" "%HERE%crew\crew.py" %*
)

pause
