@echo off
chcp 65001 >nul
title NEXUS Chat — Agents IA autonomes
color 0B

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║        NEXUS — Agents IA autonomes              ║
echo  ║   Brain : Qwen 3.5 ^| Workers : Kimi / Nemotron  ║
echo  ╚══════════════════════════════════════════════════╝
echo.

set /p PROJET=" Chemin du projet (Entree = repertoire courant) : "

if "%PROJET%"=="" (
    python -X utf8 "%~dp0nexus_chat.py"
) else (
    python -X utf8 "%~dp0nexus_chat.py" --project "%PROJET%"
)

echo.
pause
