@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "PYTHONIOENCODING=utf-8"

REM --- Meme detection que nexus.bat ---
set "PY="

if exist "%USERPROFILE%\AppData\Roaming\uv\tools\crewai\Scripts\python.exe" (
  set "PY=%USERPROFILE%\AppData\Roaming\uv\tools\crewai\Scripts\python.exe"
  goto :py_ok
)

for %%P in (python.exe) do (
  if not "%%~$PATH:P"=="" (
    "%%~$PATH:P" -c "import crewai" >nul 2>&1
    if !errorlevel! equ 0 (
      set "PY=%%~$PATH:P"
      goto :py_ok
    )
  )
)

echo.
echo [ERREUR] Python + crewai introuvables.
echo Installe via : uv tool install crewai --with crewai-tools --with "litellm[caching]" --with httpx --with chromadb
echo.
pause
exit /b 1

:py_ok
echo Python : %PY%
echo.
"%PY%" "%HERE%scripts\test_phase0.py"
echo.
pause
