@echo off
chcp 65001 >nul
rem 收集今天的資料並匯出網站 JSON（排程也是呼叫這個檔案）
cd /d "%~dp0..\.."
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
if not exist logs mkdir logs
set PYTHONUNBUFFERED=1
%PY% -m twstock collect %* >> logs\collect.log 2>&1
