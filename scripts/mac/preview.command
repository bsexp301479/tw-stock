#!/bin/bash
# 雙擊即可在瀏覽器預覽網站
cd "$(dirname "$0")/../.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
exec "$PY" -m twstock serve
