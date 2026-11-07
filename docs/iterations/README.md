# 持續優化流程

每一輪（`docs/iterations/NN/`）依序由五個角色產出文件，下一個角色以上一個的文件為輸入：

| 順序 | 角色 | 產出 |
|---|---|---|
| 1 | 股市分析師 | `01-analyst.md`：大盤與個股資訊可優化、可新增的項目，附投資人使用情境與資料來源 |
| 2 | Project Manager | `02-pm.md`：排定優先順序，選出本輪範圍（含驗收條件），其餘列入待辦 |
| 3 | System Analyst | `03-design.md`：設計文件（資料來源、資料表、匯出 JSON 欄位、畫面、邊界情況、測試案例） |
| 4 | Programmer | 依設計文件修改程式並同步更新 README 與 `__main__.py` 指令說明，`04-dev.md` 記錄改了什麼、與設計的差異 |
| 5 | Quality Assurance | `05-qa.md`：對照設計文件逐項測試與驗證，列出通過／失敗與缺陷 |

## 專案現況（給各角色的背景）

- Python 套件 `twstock`：`collectors/` 從證交所、櫃買中心、期交所抓資料寫入 SQL Server（Docker 的 Azure SQL Edge，`localhost,1433`，資料庫 `TwStock`，帳密在 `.env`），`export.py` 匯出靜態 JSON 到 `site/data/`（`latest.json` 與 `stocks/{代號}.json`）。
- 網站 `site/`：純 JS 單頁（`app.js` 今日／泡泡圖／排行／ETF／自選，`stock.js` 個股頁，`app.css`），圖表用 Lightweight Charts 4.2.0 與 Plotly，無後端。
- 現有資料：個股日線（2025-10-30 起，滿 52 週）、加權指數（2026-02-23 起）、櫃買指數（2025-10-30 起）、官方休市日曆（`market_holidays`）、收集執行紀錄（`collect_runs`）、處置／注意股、除權息與股本變動事件（`price_events`）、上市、上櫃官方三大法人金額（`insti_amount`，第 9 輪起以 `market` 區分，上市、上櫃都是 2026-07-31 起 65 天）、月營收（2023 起）、季報（`quarterly_financials`，113Q1 起累計值，單季在匯出時相減）、本益比／淨值比／殖利率、三大法人買賣超（個股）、融資融券（個股 `margin_trades` 與官方合計 `margin_market`，2025-10-30 起）、借券賣出（個股 `sbl_trades`、ETF `etf_sbl`，單位股，2025-10-30 起；`stocks.shares` 存目前發行股數，沒有歷史）、ETF（獨立資料表 `etfs`、`etf_daily`、`etf_margin`，2025-10-30 起；`stocks` 表沒有 ETF）、統一、群益投信 8 檔主動 ETF 每日持股（群益明細沒有市值）（`etf_holdings`、`etf_holding_summary`，上市日起；跨境 ETF 持股日晚一個交易日；投信確定沒有明細的日期記在 `etf_holding_gaps`，不算缺）、官方漲跌家數（`market_breadth`，2026-11-03 起）、產業別、產業鏈族群、自訂概念股、台指期近月日 K（2020 起）、期貨三大法人未平倉（期交所只提供近 3 年）。
- 現有功能：加權／櫃買指數卡片與 60 日走勢、大盤成交額與漲跌家數、上市官方三大法人金額與 20 日走勢、上櫃官方金額一行與 20 日迷你圖（標示資料日）、市場估值位置卡（上市、上櫃本益比、淨值比、殖利率中位數的一年位置；第 12 輪加市值加權本益比）與個股估值一年位置、個股季報卡（近 8 季單季 EPS 柱狀圖、毛利率、營益率、近 4 季 EPS）與季 EPS 選股條件、今日頁季報公布進度、信用交易卡（股票口徑頭條、官方融資金額、ETF 另計、自算大盤融資維持率）、台指期日 K（前一夜盤／最新夜盤標示）、期貨法人未平倉與籌碼因子觀察（預測未勝過基準時降級）、類股／產業鏈／概念股資金流泡泡圖與象限、排行（1 日／5 日、成交額門檻）、ETF 列表頁（行情、融資融券、借券，排序與市場篩選）、主動 ETF 持股頁（`#/etf/代號`）與個股「主動 ETF 持有」卡、主動 ETF 彙總排行（`#/etf/active`，今日頁小卡）、主動 ETF 單位數 1 日變化與個股卡「投信買超中主動 ETF 占比」（申購影響的誤導修正）、條件選股（`#/rank/screen`，`screen.json`，約 40 個條件、7 組預設＋2 組參考，可用網址分享；估值條件預設排除 90 天內股本變動）、排行擴充（新增 13 種：融資融券 7 種、價量 3 種、基本面 3 種，如殖利率、本益比最低、20 日相對強度）、融資融券排行（面額變更時換算張數）與個股融資融券圖、市場寬度卡（站上 MA20／MA60、20 日新高新低、量能）、自選股、個股融資融券指標卡、借券賣出（第 11 輪：個股融資融券圖第三條線與指標卡、借券排行 2 種、今日頁信用交易卡一行、選股條件 2 個；第 12 輪：ETF 借券、圖的刻度說明）、市值與週轉率（第 12 輪：個股指標卡、週轉率排行、選股條件 2 個）、首頁與個股頁分頁、版面整理（第 13 輪：表格固定名稱欄並把排序欄放在第 2 欄、較長的口徑說明預設收合、個股頁首一行開高低昨收量、首頁錢流預設前 5）、個股 K 線（還原／原始切換、事件標記）＋均線＋量＋法人堆疊＋MACD、處置／注意標籤、月營收 36 個月與累計年增、技術面訊號、資料新鮮度橫幅（附建議指令）；`check` 開頭列最後一次收集與排程狀態，並有月營收、季報進度各一行（季報在公布期間每天上市、上櫃各 1 次請求；月營收月初起提前收集，達前一月 98% 為 ✅）；資料庫連不上時指令回傳 2 並顯示一行說明；排程腳本 17:30、19:30、21:45、22:30。
- 指令：`python3 -m twstock collect --catch-up` 補齊缺的資料；`python3 -m twstock check` 檢查完整性；`python3 -m twstock history --start … [--only …]` 補抓歷史；`python3 -m twstock export` 重新匯出；`python3 -m twstock setup-db` 建表（可重複執行）；`python3 -m twstock backup` 備份資料庫到 `../_backups/`（COPY_ONLY，不做還原）；`python3 -m twstock serve --port 8001 --no-browser` 本機預覽。
- 測試：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`、`python3 tests/test_iter08.py`、`python3 tests/test_iter09.py`、`python3 tests/test_iter10.py`、`python3 tests/test_iter11.py`、`python3 tests/test_iter12.py`、`python3 tests/test_iter13.py`（每輪可新增 `tests/test_iterNN.py`）。
- 待修：無（第 13 輪 QA 後使用者發現的 D1 寬螢幕首頁卡片位置已修正）。待上線確認：使用者恢復每晚 `collect --catch-up` 後，季報「本站收錄」日期、同一晚第二次不再抓季報、`check` 季報一行（一般業 11/14、金融業 11/29 截止）；借券 20:30 前顯示「尚未公布」、21:45 後寫入、22:30 不重抓（`11/05-qa.md` 第八節）。
- 規範：回應與文件用繁體中文；程式風格比照既有程式碼；只改必要的地方；外部網站請求要經過 `twstock/fetch.py` 的 `request`（有節流）；不要 commit 或 push；不要動 `.env`（建立專案副本時也不要複製 `.env`）；不要安裝排程或改系統設定（launchd、crontab、pmset、docker 設定），這些由使用者自行執行；埠 8000 是使用者自己的伺服器，測試用 8001 並在結束時關掉。
