@echo off
REM NEXUS Chat — Lanceur Windows
REM Usage : nexus.bat
REM         nexus.bat --project C:\mon-projet
REM         nexus.bat --project C:\mon-projet --write

python "%~dp0nexus_chat.py" %*
