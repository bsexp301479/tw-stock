@echo off
chcp 65001 >nul
rem 雙擊即可在瀏覽器預覽網站
cd /d "%~dp0..\.."
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
%PY% -m twstock serve
