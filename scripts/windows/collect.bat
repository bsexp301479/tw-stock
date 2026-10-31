@echo off
chcp 65001 >nul
rem 補齊最近缺的資料（缺什麼補什麼），有新資料才匯出網站 JSON（排程也是呼叫這個檔案）。帶參數時照傳，例如 --date 2026-10-28
cd /d "%~dp0..\.."
set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python
if not exist logs mkdir logs
set PYTHONUNBUFFERED=1
set ARGS=%*
if "%ARGS%"=="" set ARGS=--catch-up
%PY% -m twstock collect %ARGS% >> logs\collect.log 2>&1
