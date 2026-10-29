#!/bin/bash
# 建立虛擬環境、安裝套件、檢查 ODBC 驅動與 .env
set -e
cd "$(dirname "$0")/../.."

if [ ! -d .venv ]; then
  echo "▶ 建立虛擬環境 .venv"
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -r requirements.txt -q
echo "✅ Python 套件已安裝"

if ! odbcinst -q -d 2>/dev/null | grep -q "ODBC Driver 18 for SQL Server"; then
  echo "⚠️  找不到 ODBC Driver 18，請執行："
  echo "    brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release"
  echo "    HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  已建立 .env，請填入 DB_PASSWORD 後再執行：.venv/bin/python -m twstock setup-db"
else
  .venv/bin/python -m twstock setup-db
fi
