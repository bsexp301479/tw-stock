@echo off
chcp 65001 >nul
rem 建立虛擬環境、安裝套件、檢查 .env
cd /d "%~dp0..\.."

if not exist .venv (
  echo ▶ 建立虛擬環境 .venv
  py -3 -m venv .venv || python -m venv .venv
)
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\python -m pip install -r requirements.txt -q
echo ✅ Python 套件已安裝

reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server" >nul 2>&1
if errorlevel 1 (
  echo ⚠️  找不到 ODBC Driver 18，請至 https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server 下載安裝
)

if not exist .env (
  copy .env.example .env >nul
  echo ⚠️  已建立 .env，請填入 DB_PASSWORD 後再執行：.venv\Scripts\python -m twstock setup-db
) else (
  .venv\Scripts\python -m twstock setup-db
)
pause
