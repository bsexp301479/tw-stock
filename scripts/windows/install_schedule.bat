@echo off
chcp 65001 >nul
rem 安裝工作排程器：週一到週五 17:30、19:30、21:45 執行 collect.bat（解除安裝：加上 /uninstall）
rem 其他參數：印用法後以非 0 結束，不安裝也不移除
if not "%~2"=="" goto :usage
if "%~1"=="" goto :start
if /i "%~1"=="/uninstall" goto :start
:usage
echo ❌ 不認得的參數：%*（沒有安裝，也沒有移除）
echo 用法：install_schedule.bat [/uninstall]
exit /b 2
:start
set TASK=TwStockCollect
schtasks /Delete /TN %TASK% /F >nul 2>&1
schtasks /Delete /TN %TASK%1730 /F >nul 2>&1
schtasks /Delete /TN %TASK%1930 /F >nul 2>&1
schtasks /Delete /TN %TASK%2145 /F >nul 2>&1
if /i "%~1"=="/uninstall" (
  echo ✅ 已移除排程
  goto :eof
)
schtasks /Create /TN %TASK%1730 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 17:30 /F
schtasks /Create /TN %TASK%1930 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /F
schtasks /Create /TN %TASK%2145 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 21:45 /F
echo ✅ 已安裝排程：週一至週五 17:30、19:30、21:45，紀錄寫入 logs\collect.log
echo    錯過排程要補跑：請在工作排程器勾選各工作的「錯過排程時儘快執行」
echo    立即測試一次：schtasks /Run /TN %TASK%1730
pause
