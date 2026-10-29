#!/bin/bash
# 安裝 launchd 排程：週一到週五 18:30 執行 collect（解除安裝：加上 --uninstall）
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL=com.twstock.collect
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="$(command -v python3)"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "$1" = "--uninstall" ]; then
  rm -f "$PLIST"
  echo "✅ 已移除排程"
  exit 0
fi

mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"
DAYS=""
for wd in 1 2 3 4 5; do
  DAYS="$DAYS<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer></dict>"
done
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>-m</string><string>twstock</string><string>collect</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartCalendarInterval</key><array>$DAYS</array>
  <key>StandardOutPath</key><string>$ROOT/logs/collect.log</string>
  <key>StandardErrorPath</key><string>$ROOT/logs/collect.log</string>
  <key>EnvironmentVariables</key><dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
</dict></plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✅ 已安裝排程：週一至週五 18:30，紀錄寫入 logs/collect.log"
echo "   立即測試一次：launchctl kickstart gui/$(id -u)/$LABEL"
