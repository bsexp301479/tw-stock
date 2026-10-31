#!/bin/bash
# launchd 排程：週一到週五 17:30、19:30、21:45，以及登入時，執行 collect --catch-up
#   bash install_schedule.sh             安裝（安裝當下與之後每次登入都會補跑一次）
#   bash install_schedule.sh --print     只印出 plist 內容，不安裝、不動 launchctl
#   bash install_schedule.sh --uninstall 移除
#   其他參數：印用法後以非 0 結束，不安裝也不移除
set -e
case "$#:${1:-}" in
  0: | 1:--print | 1:--uninstall) ;;
  *)
    echo "❌ 不認得的參數：$*（沒有安裝，也沒有移除）" >&2
    echo "用法：bash install_schedule.sh [--print | --uninstall]" >&2
    exit 2
    ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL=com.twstock.collect
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

render_plist() {
  local times="" wd t
  for wd in 1 2 3 4 5; do
    for t in "17 30" "19 30" "21 45"; do
      set -- $t
      times="$times<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$1</integer><key>Minute</key><integer>$2</integer></dict>"
    done
  done
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/usr/bin/caffeinate</string><string>-i</string><string>$PY</string><string>-m</string><string>twstock</string><string>collect</string><string>--catch-up</string><string>--notify</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key><array>$times</array>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$ROOT/logs/collect.log</string>
  <key>StandardErrorPath</key><string>$ROOT/logs/collect.log</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
</dict></plist>
EOF
}

if [ "$1" = "--print" ]; then
  render_plist
  exit 0
fi

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "$1" = "--uninstall" ]; then
  rm -f "$PLIST"
  echo "✅ 已移除排程"
  exit 0
fi

mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"
render_plist > "$PLIST"
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✅ 已安裝排程：週一至週五 17:30、19:30、21:45，以及登入時；紀錄寫入 logs/collect.log"
echo "   安裝當下會立刻執行一次（RunAtLoad）。立即再測一次：launchctl kickstart gui/$(id -u)/$LABEL"
