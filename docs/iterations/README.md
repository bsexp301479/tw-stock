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
- 現有資料：個股日線（2025-10-30 起，滿 52 週）、加權指數（2026-02-23 起）、櫃買指數（2025-10-30 起）、官方休市日曆（`market_holidays`）、收集執行紀錄（`collect_runs`）、處置／注意股、除權息與股本變動事件（`price_events`）、上市官方三大法人金額（`insti_amount`）、月營收（2023 起）、本益比／淨值比／殖利率、三大法人買賣超（個股）、融資融券（個股 `margin_trades` 與官方合計 `margin_market`，2025-10-30 起）、ETF（獨立資料表 `etfs`、`etf_daily`、`etf_margin`，2025-10-30 起；`stocks` 表沒有 ETF）、統一、群益投信 8 檔主動 ETF 每日持股（群益明細沒有市值）（`etf_holdings`、`etf_holding_summary`，上市日起；跨境 ETF 持股日晚一個交易日；投信確定沒有明細的日期記在 `etf_holding_gaps`，不算缺）、官方漲跌家數（`market_breadth`，2026-11-03 起）、產業別、產業鏈族群、自訂概念股、台指期近月日 K（2020 起）、期貨三大法人未平倉（期交所只提供近 3 年）。
- 現有功能：加權／櫃買指數卡片與 60 日走勢、大盤成交額與漲跌家數、上市官方三大法人金額與 20 日走勢（標示資料日）、信用交易卡（股票口徑頭條、官方融資金額、ETF 另計、自算大盤融資維持率）、台指期日 K（前一夜盤／最新夜盤標示）、期貨法人未平倉與籌碼因子觀察（預測未勝過基準時降級）、類股／產業鏈／概念股資金流泡泡圖與象限、排行（1 日／5 日、成交額門檻）、ETF 列表頁（行情、融資融券、排序與市場篩選）、主動 ETF 持股頁（`#/etf/代號`）與個股「主動 ETF 持有」卡、主動 ETF 彙總排行（`#/etf/active`，今日頁小卡）、市場寬度卡（站上 MA20／MA60、20 日新高新低、量能）、自選股、個股融資融券指標卡、個股 K 線（還原／原始切換、事件標記）＋均線＋量＋法人堆疊＋MACD、處置／注意標籤、月營收 36 個月與累計年增、技術面訊號、資料新鮮度橫幅（附建議指令）；`check` 開頭列最後一次收集與排程狀態；排程腳本 17:30、19:30、21:45、22:30。
- 指令：`python3 -m twstock collect --catch-up` 補齊缺的資料；`python3 -m twstock check` 檢查完整性；`python3 -m twstock history --start … [--only …]` 補抓歷史；`python3 -m twstock export` 重新匯出；`python3 -m twstock setup-db` 建表（可重複執行）；`python3 -m twstock backup` 備份資料庫到 `../_backups/`（COPY_ONLY，不做還原）；`python3 -m twstock serve --port 8001 --no-browser` 本機預覽。
- 測試：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`（每輪可新增 `tests/test_iterNN.py`）。
- 待修：無（第 6 輪 QA-03、QA-04 已在 QA 後修正，見 `06/05-qa.md` 第九節）。
- 規範：回應與文件用繁體中文；程式風格比照既有程式碼；只改必要的地方；外部網站請求要經過 `twstock/fetch.py` 的 `request`（有節流）；不要 commit 或 push；不要動 `.env`（建立專案副本時也不要複製 `.env`）；不要安裝排程或改系統設定（launchd、crontab、pmset、docker 設定），這些由使用者自行執行；埠 8000 是使用者自己的伺服器，測試用 8001 並在結束時關掉。
