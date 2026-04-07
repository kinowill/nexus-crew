@echo off
chcp 65001 >nul
title NEXUS Chat - Agents IA autonomes
color 0B

python -c "print(); print('  \u2554' + '\u2550'*50 + '\u2557'); print('  \u2551' + '        NEXUS \u2014 Agents IA autonomes              ' + '\u2551'); print('  \u2551' + '   Brain : Qwen 3.5 | Workers : Kimi / Nemotron  ' + '\u2551'); print('  \u255a' + '\u2550'*50 + '\u255d'); print()"

set /p PROJET=" Chemin du projet (Entree = repertoire courant) : "

if "%PROJET%"=="" (
    python -X utf8 "%~dp0nexus_chat.py"
) else (
    python -X utf8 "%~dp0nexus_chat.py" --project "%PROJET%"
)

echo.
pause
