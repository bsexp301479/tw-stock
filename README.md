# 台股資金流 tw-stock

收集上市、上櫃個股的行情、本益比、三大法人、月營收、處置／注意股、除權息／減資／面額變更事件，上市三大法人買賣金額，加權與櫃買指數、產業鏈族群、台指期日 K 與期貨三大法人未平倉，寫入 SQL Server，再匯出成靜態 JSON 給網站使用。
網站是純前端（`site/`），不需要後端伺服器，日後可直接部署到 Cloudflare Pages 等靜態主機。

```
資料來源 API ──► twstock collect ──► SQL Server ──► twstock export ──► site/data/*.json ──► 瀏覽器
```

## 專案結構

| 路徑 | 說明 |
|---|---|
| `twstock/fetch.py` | HTTP 請求：每個主機各自節流、被封鎖時退避重試 |
| `twstock/collectors/` | `daily` 行情／本益比／法人／加權與櫃買指數、上市三大法人買賣金額、`alerts` 處置／注意股、`events` 除權息／減資／面額變更事件（還原價格用）、`revenue` 月營收、`industry` 產業別、`chains` 產業鏈族群、`futures` 期貨日 K 與法人未平倉、`history` 補抓歷史、`catchup` 缺什麼補什麼 |
| `twstock/tradingcal.py` | 交易日曆（官方休市表、手寫表、臨時休市） |
| `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
| `twstock/export.py` | 匯出 `site/data/latest.json` 與 `site/data/stocks/{代號}.json` |
| `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察）、泡泡圖、排行、自選、個股頁 |
| `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py` |
| `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
| `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
| `scripts/mac/`、`scripts/windows/` | 安裝、預覽、手動收集、排程 |

## 安裝

需要 Python 3.10 以上、Docker、Microsoft ODBC Driver 18 for SQL Server。

1. 複製 `.env.example` 為 `.env`，填入 `DB_PASSWORD`（至少 8 碼，含大小寫英文、數字、符號）。
2. 啟動資料庫（已有自建的 SQL Server 容器就略過）：
   ```bash
   docker compose up -d
   ```
   Windows 或 Intel Mac 請先在 `.env` 加上 `MSSQL_IMAGE=mcr.microsoft.com/mssql/server:2022-latest`。
3. 執行安裝腳本，建立 `.venv`、安裝套件並建立資料表：
   - Mac：`bash scripts/mac/setup.sh`
   - Windows：雙擊 `scripts\windows\setup.bat`

更新程式後若有新增資料表（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`，第 3 輪的 `collect_runs`、`market_holidays`），請再執行一次 `python -m twstock setup-db`（可重複執行，不影響既有資料），否則 `collect`、`check`、`export` 會失敗。

## 日常使用

指令在 Mac 用 `.venv/bin/python`，在 Windows 用 `.venv\Scripts\python`：

```bash
python -m twstock collect --catch-up             # 補齊最近 10 個交易日缺的資料（可重複執行；齊全時 0 個請求、不匯出）。排程用這個
python -m twstock collect --catch-up --days 20   # 回溯 20 個交易日（上限 30，更早用 history）
python -m twstock collect                        # 今天全部重抓覆寫（含指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站 JSON
python -m twstock collect --date 2026-10-28      # 指定日期全部重抓覆寫；也用來復原被誤判的臨時休市
python -m twstock check                          # 檢查近 20 個交易日各資料集的完整性（唯讀、不連外）；有異常回傳 1
python -m twstock history --start 2026-01-02     # 補抓歷史（行情、本益比、法人），只補缺的，可中斷重跑
python -m twstock history --start 2026-01-02 --only insti   # 只補法人
python -m twstock history --start 2025-10-30 --only pe      # 只補本益比／淨值比／殖利率（--only prices 不再順帶寫入）
python -m twstock history --start 2026-02-23 --only index   # 只補加權指數歷史（一天一個請求）
python -m twstock history --start 2025-10-30 --only tpex_index  # 只補櫃買指數（一個月一個請求）
python -m twstock history --start 2026-07-31 --only amount  # 只補上市三大法人買賣金額（一天一個請求）
python -m twstock events --start 2025-10-30      # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑）
python -m twstock revenue --year 2026 --month 9 --force     # 重抓某月營收
python -m twstock futures --start 2020-01-01     # 補抓台指期日 K 與期貨三大法人未平倉（--commodity MTX 可抓小台）
python -m twstock chains                         # 立即更新產業鏈族群（collect 每 30 天會自動更新）
python -m twstock export                         # 只重新匯出網站 JSON
python -m twstock serve                          # 本機預覽 http://localhost:8000
python -m twstock chanlun 2330                   # 產生 output/chanlun_2330.svg
python -m twstock setup-db                       # 建立／補建資料表
python3 tests/test_iter01.py                     # 執行測試
python3 tests/test_iter02.py                     # 第 2 輪測試
python3 tests/test_iter03.py                     # 第 3 輪測試
```

也可以直接雙擊：Mac 的 `scripts/mac/preview.command`、`collect.command`，Windows 的 `scripts\windows\preview.bat`、`collect.bat`。`collect.command`、`collect.bat` 補齊最近缺的資料（等同 `collect --catch-up`）；帶參數時照傳。

### 自動排程（週一至週五 17:30、19:30、21:45）

**以下步驟由使用者自行執行**，程式不會自動安裝。排程執行 `collect --catch-up`：缺什麼補什麼，一天多次也不會重抓。

- Mac：`bash scripts/mac/install_schedule.sh`（只看內容不安裝：`--print`；移除：`--uninstall`；其他參數只印用法，不會安裝）。**安裝當下會立刻執行一次**，之後每次登入也會補跑一次。排程以 `caffeinate -i` 執行，只在執行期間防止睡眠，不改系統設定。有異常時發本機通知，同一天同一問題只通知一次。
- Windows：執行 `scripts\windows\install_schedule.bat`（移除：加上 `/uninstall`；其他參數只印用法，不會安裝）。會建立三個工作；要補跑錯過的排程，請在工作排程器勾選各工作的「錯過排程時儘快執行」。異常只寫紀錄。

執行紀錄寫入 `logs/collect.log` 與資料表 `collect_runs`。

**電腦設定（由使用者決定、自行執行）：**

- Mac 睡眠：電腦睡著時排程不會執行，喚醒後合併補跑一次，所以資料通常是「下次打開電腦時補齊」，不會遺失（處置／注意股例外，只查得到近幾日）。要當天晚上就有資料，可固定喚醒（需要管理者權限）：`sudo pmset repeat wakeorpoweron MTWRF 17:25:00`。
- 資料庫容器：重開機後容器沒啟動時收集會失敗（回傳 2、提示啟動）。可設定自動重啟：`docker update --restart unless-stopped MySqlServer`，並在 Docker Desktop 設定開機啟動。

## 注意事項

- 法人資料通常比收盤行情晚公布，網站上的「法人資料」日期可能比「資料日」早一天。資金流與象限都以法人資料日為準。各資料集獨立收集：行情公布、法人還沒公布時，會先寫入行情並更新網站（不再全有全無），下次排程補上法人。
- 抓取間隔已依各主機設定（證交所 3.5 秒、櫃買 3 秒），請勿調短，否則容易被暫時封鎖。
- `.env` 含資料庫密碼，已列在 `.gitignore`，請勿提交。
- 族群有三種：**類股**（證交所／櫃買產業別）、**產業鏈**（[櫃買中心產業價值鏈平台](https://ic.tpex.org.tw/)，自動更新）、**概念股**（`data/concepts.csv` 手動維護）。
- 台指期日 K 來自期交所「每日行情下載」，以「當天有成交的最近月份」接成近月連續線，只畫日盤。夜盤的日期是成交量歸屬日：標示 10/29 的夜盤是 10/28 15:00 到 10/29 05:00。
- 期貨三大法人未平倉來自期交所「三大法人－區分各期貨契約」，抓大台（TXF）、小台（MXF）、微台（TMF），換算成約當大台 = 大台 + 小台/4 + 微台/20。
- 籌碼因子觀察（大盤漲跌預測）：以外資淨未平倉水位、外資 1 日／5 日增減、投信與自營商 1 日增減（相對近 60 日標準化）做羅吉斯迴歸，預測下一交易日台指期近月日盤漲跌。網站同時顯示 walk-forward 回測命中率與「永遠猜多數方向」的基準；模型沒有勝過基準時，首頁只顯示因子方向，機率與回測收在摺疊區；僅供籌碼面參考，非投資建議。
- 個股法人：排行可切換 1 日／5 日，提供外資、投信、自營、法人合計的買超／賣超與連買排行；金額 = 張數 × 當日收盤（估算值，與官方公布的買賣金額可能不同）。
- 今日頁三大法人卡：上市為證交所 BFI82U 官方買賣金額（含 ETF；外資 = 外資及陸資，不含外資自營商，外資自營商已計入自營商），附近 20 日外資買賣超與連買／連賣天數；上櫃仍為張數 × 收盤估算（不含 ETF），另列一行，不與上市相加。
- 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
- 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。
- 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。日線未滿一年時顯示「區間高／低」與起始日。
- 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
- 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
- 月營收匯出最近 36 個月，累計年增以完整歷史計算；「新高」= 高於之前所有月份，且至少有 2 年資料。
- 台指期分 K 尚未支援。期交所只提供近 30 個交易日的逐筆成交檔，需要時可由逐筆資料合成。
- 往前補抓日線時，請用同一區間執行 `python -m twstock events --start …`，否則補抓區段的價格不會還原。
- 資料完整性：每個資料集分市場判斷。**齊全** = 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比、淨值比、殖利率的非空比例都 ≥ 50%。狀態：**正常**；**尚未公布**（當天 22:00 前還沒有）；**異常**（22:00 後或隔日仍缺、抓取失敗、欄位不符）；**休市**（不列入）。`collect --catch-up` 回傳 0 = 正常、尚未公布、休市或另一個程序正在執行；1 = 有異常；2 = 連不上資料庫。
- 交易日曆：優先用證交所官方休市表（`market_holidays`，只有當年，30 天更新一次），抓不到時只印警告、不影響當次收集，沿用已存的官方表；沒有該年資料時用程式內的手寫表；都沒有時平日一律視為交易日並印警告，**每年年底請確認新年度的休市表**。
- 臨時休市（颱風假）：日期已過，且上市、上櫃、期交所都沒有資料、查詢都沒有失敗時，自動登記為臨時休市，不再算缺漏。判定錯誤時執行 `python -m twstock collect --date 該日`，查到資料就會移除判定。
- 網站的「更新於」是**最後一次收集到新資料的時間**，不是匯出時間；還沒有執行紀錄時退回資料寫入時間，並標示「（依資料寫入時間）」。`history` 補抓不算。依交易日曆資料落後時（交易日 18:00 前看前一交易日，之後看當天，台灣時間），顯示橘色提示；部分資料異常時顯示局部提示。分頁回到前景時會重新檢查，有新資料會提示重新整理，不會自動跳轉。
- 補抓舊日期（`collect --date`、`history`）不會覆蓋股票的名稱與市場別；只有最新日期的資料會更新。
- `_archive/` 是舊腳本，**不要再執行**：它連同一個資料庫，會把上櫃殖利率覆寫成 NULL，並蓋掉名稱與市場別。目前已把 `_archive/config.py` 改名為 `config.py.disabled` 使它無法執行，請不要改回來。
- 資料僅供研究參考，不構成投資建議。
