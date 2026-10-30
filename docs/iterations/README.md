# 持續優化流程

每一輪（`docs/iterations/NN/`）依序由五個角色產出文件，下一個角色以上一個的文件為輸入：

| 順序 | 角色 | 產出 |
|---|---|---|
| 1 | 股市分析師 | `01-analyst.md`：大盤與個股資訊可優化、可新增的項目，附投資人使用情境與資料來源 |
| 2 | Project Manager | `02-pm.md`：排定優先順序，選出本輪範圍（含驗收條件），其餘列入待辦 |
| 3 | System Analyst | `03-design.md`：設計文件（資料來源、資料表、匯出 JSON 欄位、畫面、邊界情況、測試案例） |
| 4 | Programmer | 依設計文件修改程式，`04-dev.md` 記錄改了什麼、與設計的差異 |
| 5 | Quality Assurance | `05-qa.md`：對照設計文件逐項測試與驗證，列出通過／失敗與缺陷 |

## 專案現況（給各角色的背景）

- Python 套件 `twstock`：`collectors/` 從證交所、櫃買中心、期交所抓資料寫入 SQL Server（Docker 的 Azure SQL Edge，`localhost,1433`，資料庫 `TwStock`，帳密在 `.env`），`export.py` 匯出靜態 JSON 到 `site/data/`（`latest.json` 與 `stocks/{代號}.json`）。
- 網站 `site/`：純 JS 單頁（`app.js` 今日／泡泡圖／排行／自選，`stock.js` 個股頁，`app.css`），圖表用 Lightweight Charts 4.2.0 與 Plotly，無後端。
- 現有資料：個股日線、本益比／淨值比／殖利率、三大法人買賣超（個股）、月營收、產業別、產業鏈族群、自訂概念股、台指期近月日 K（2020 起）、期貨三大法人未平倉（期交所只提供近 3 年）。
- 現有功能：大盤成交額與漲跌家數、三大法人合計、台指期日 K、期貨法人未平倉與漲跌預測（回測未勝過基準）、類股／產業鏈／概念股資金流泡泡圖與象限、排行（1 日／5 日）、自選股、個股 K 線＋均線＋量＋法人堆疊＋MACD、月營收、技術面訊號。
- 指令：`python3 -m twstock export` 重新匯出；`python3 -m twstock setup-db` 建表（可重複執行）；`python3 -m twstock serve --port 8001 --no-browser` 本機預覽。
- 規範：回應與文件用繁體中文；程式風格比照既有程式碼；只改必要的地方；外部網站請求要經過 `twstock/fetch.py` 的 `request`（有節流）；不要 commit 或 push；不要動 `.env`；埠 8000 是使用者自己的伺服器，測試用 8001 並在結束時關掉。
