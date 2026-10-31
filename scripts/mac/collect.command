#!/bin/bash
# 雙擊：補齊最近缺的資料（缺什麼補什麼），有新資料才匯出網站 JSON。帶參數時照傳，例如 --date 2026-10-28
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
[ $# -gt 0 ] || set -- --catch-up
"$PY" -m twstock collect "$@"
read -n 1 -s -r -p "按任意鍵關閉…"
