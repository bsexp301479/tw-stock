#!/bin/bash
# 雙擊即可手動收集今天的資料並匯出網站 JSON
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
"$PY" -m twstock collect "$@"
read -n 1 -s -r -p "按任意鍵關閉…"
