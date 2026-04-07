@echo off
REM NEXUS — Script d'installation Windows
REM Lance ce script UNE SEULE FOIS apres avoir clone le projet.
REM
REM AVANT de lancer : copie .env.example vers .env et remplis ta cle API NVIDIA.

echo.
echo ============================================================
echo   NEXUS - Installation du systeme multi-agents
echo ============================================================
echo.

REM Verifier que .env existe
if not exist "%~dp0..\.env" (
    echo ERREUR : Fichier .env manquant.
    echo Copie .env.example vers .env et remplis ta cle NVIDIA_API_KEY.
    pause
    exit /b 1
)

REM Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python n'est pas installe ou pas dans le PATH.
    echo Installez Python depuis https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Python detecte.

REM Installer les dependances
echo [2/4] Installation des dependances Python...
pip install mcp httpx --quiet
if errorlevel 1 (
    echo ERREUR lors de l'installation des packages.
    pause
    exit /b 1
)
echo       OK : mcp, httpx installes.

REM Charger la cle API depuis .env
for /f "tokens=1,2 delims==" %%a in (%~dp0..\.env) do (
    if "%%a"=="NVIDIA_API_KEY" set NVIDIA_API_KEY=%%b
)

REM Enregistrer le MCP dans Claude Code
echo [3/4] Enregistrement du serveur MCP NEXUS dans Claude Code...
claude mcp add -s user -e "NVIDIA_API_KEY=%NVIDIA_API_KEY%" nexus -- python "%~dp0..\mcp-servers\nexus\server.py"
if errorlevel 1 (
    echo AVERTISSEMENT : Enregistrement MCP peut avoir echoue.
    echo Essayez manuellement avec votre cle depuis .env
) else (
    echo       OK : MCP NEXUS enregistre scope=user.
)

REM Test de connexion
echo [4/4] Test de connexion NVIDIA NIM...
python -X utf8 "%~dp0test_connection.py"

echo.
echo ============================================================
echo   Installation terminee.
echo   Relancez Claude Code pour activer le MCP NEXUS.
echo   Puis lancez : python scripts\discover_models.py
echo ============================================================
echo.
pause
