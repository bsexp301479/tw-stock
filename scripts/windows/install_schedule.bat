@echo off
chcp 65001 >nul
rem 安裝工作排程器：週一到週五 18:30 執行 collect.bat（解除安裝：加上 /uninstall）
set TASK=TwStockCollect
if /i "%~1"=="/uninstall" (
  schtasks /Delete /TN %TASK% /F
  echo ✅ 已移除排程
  goto :eof
)
schtasks /Create /TN %TASK% /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 18:30 /F
echo ✅ 已安裝排程：週一至週五 18:30，紀錄寫入 logs\collect.log
echo    立即測試一次：schtasks /Run /TN %TASK%
pause
