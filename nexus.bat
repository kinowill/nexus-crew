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

REM Si arguments fournis en ligne de commande, passer direct
if not "%~1"=="" (
  "%PY%" "%HERE%crew\crew.py" %*
  pause
  exit /b
)

REM ============================================================
REM  Mode interactif
REM ============================================================
cls
echo.
echo ============================================================
echo   NEXUS Crew - Lanceur interactif
echo ============================================================
echo.
echo   COMMANDES UTILES (ligne de commande) :
echo.
echo     nexus.bat "tache" --project C:/mon-projet
echo     nexus.bat "tache" --project C:/X --write        (ecrit reellement)
echo     nexus.bat "tache" --project C:/X --deep         (gros projets)
echo     nexus.bat "tache" --project C:/X --allow D:/lib (ajoute un dossier)
echo.
echo   AGENTS : Researcher -^> Architect -^> Coder -^> Critic
echo   FALLBACK auto entre modeles NVIDIA NIM si un tombe
echo.
echo ------------------------------------------------------------
echo   Selection du dossier de travail...
echo ------------------------------------------------------------

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command ^
  "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Choisis le dossier de travail pour NEXUS'; $f.ShowNewFolderButton = $false; if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath } else { '' }"`) do set "PROJECT=%%I"

if "!PROJECT!"=="" (
  echo.
  echo   Annule.
  pause
  exit /b
)

echo.
echo   Projet selectionne : !PROJECT!
echo.
echo ------------------------------------------------------------
echo   Apercu du dossier
echo ------------------------------------------------------------

REM Apercu via PowerShell : top-level + compte total
powershell -NoProfile -Command ^
  "$p = '!PROJECT!'; $items = Get-ChildItem -LiteralPath $p -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch '^(\.git|node_modules|__pycache__|\.venv|dist|build)$' } | Select-Object -First 25; foreach ($i in $items) { if ($i.PSIsContainer) { Write-Host ('   [DIR]  ' + $i.Name) } else { Write-Host ('   [FILE] ' + $i.Name) } }; $total = (Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Host ''; Write-Host ('   Total fichiers (recursif) : ' + $total)"

echo.
echo ------------------------------------------------------------
echo.
set /p TASK="  Tache : "
if "!TASK!"=="" (
  echo   Tache vide, abandon.
  pause
  exit /b
)

echo.
set /p WRITE="  Ecriture reelle des fichiers ? [o/N] : "
set "WFLAG="
if /i "!WRITE!"=="o" set "WFLAG=--write"

set /p DEEP="  Mode deep (gros projets)     ? [o/N] : "
set "DFLAG="
if /i "!DEEP!"=="o" set "DFLAG=--deep"

echo.
echo ------------------------------------------------------------
echo   Lancement du Crew...
echo ------------------------------------------------------------
echo.
"%PY%" "%HERE%crew\crew.py" "!TASK!" --project "!PROJECT!" !WFLAG! !DFLAG!

echo.
pause
