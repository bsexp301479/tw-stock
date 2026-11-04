# 第 04 輪｜System Analyst：設計文件

- 撰寫日期：2026-11-03（週二）晚間
- 輸入：`02-pm.md` 修訂版的本輪範圍，包括 B2＋A4（含維持率）、E1、S10 核心（含 QA-04、QA-06）、S11、P19 標示與 P20，編號沿用 PM；另參考 `01-analyst.md`，格式比照第 3 輪 `03-design.md`。
- 依據：
  - 閱讀了 `twstock/{__main__,fetch,db,health,export,tradingcal}.py`、`collectors/{catchup,history,daily}.py`、`site/{index.html,app.css,app.js,stock.js}`、`scripts/mac|windows/install_schedule.*`、`tests/test_iter01～03.py`、README。
  - 資料庫只做唯讀查詢。SQL 只用 `SET PARSEONLY ON` 驗語法。
  - 外部請求都經過 `fetch.request(isolated=True)`，每個端點至多 2 次、不重試（附錄 A）。
- **所有設計都已在專案外、不含 `.env` 的暫存副本做成原型並實際跑過**：
  - 測試：`test_iter01`～`test_iter04` 全部通過（第 4 輪 26 個測試）。
  - 原型與真實資料：11/03 的實際回應加上資料庫唯讀，重現 PM 與分析師的每個驗收數值，並算出維持率預期值（附錄 B）。
  - 前端：以 node 載入原型 `app.js`，用 11/03 的實際 ETF 資料（363 檔）與融資融券數值產生信用交易卡、ETF 頁與夜盤 HTML，並確認文字。
  - 排程：`install_schedule.sh --print` 的輸出通過 `plutil -lint`。
  - **專案程式、資料庫、排程都沒有修改。** 原型副本已刪除。
- 本文件只描述設計：
  - 附錄 C 是原型對現有程式的完整 diff，附錄 D 是完整的 `tests/test_iter04.py`，附錄 E 是 PG 執行用的 `logs/` 小工具，**都可以直接套用**。
  - 要改寫法可以，但**函式名稱、資料表、判斷式、畫面文案、輸出訊息請照本文件**，`test_iter04.py` 與 QA 會照著驗。
- **`backup` 指令延到第 5 輪**：本輪改表前的備份已由 coordinator 手動完成（`_backups/TwStock_before_round4.bak`）。設計中沒有 backup 指令；實作順序第 0 步只「確認已備份」。

> **影響設計的實測發現（PM 文件沒有預期到）**
> 1. **櫃買 `margin/balance` 的 `summary` 是原生陣列**，不是字串化陣列。解析兩種都接受，但「字串化」不是本輪的驗收重點。
> 2. **ETF 融資融券的確切值與 PM 推算不同**：上市 ETF 融資 **3,122,700 張（+36,315）**、融券 **128,330 張（+56,155）**。PM 的 3,137,219（+36,348）是「官方 − 股票」，其中含 TDR 912000 晨訊科-DR 的 14,519 張（+33）與 1 張融券。差額見 B2-2。
> 3. **使用率採截斷到小數 2 位**（與櫃買官方欄位一致）：2236 百達-KY = **85.46%**（四捨五入會是 85.47，PM 寫 85.5）；2376 券資比 **33.67%**。
> 4. **ETF 回應裡沒有成交的 ETF 收盤是 `--`**，例如 11/03 的 00666R、00684R。維持率要用最近收盤；補抓前這兩檔沒有歷史收盤，所以 11/03 上市涵蓋率是 99.84%，補抓後約 99.85%。
> 5. **補抓時間約 39 分鐘**，不是 30～35 分鐘。每天上市 2 次 × 4 秒、上櫃 1 秒＋0.5 秒，共 9.5 秒 × 244 天。被限流重跑時最壞約 1.5 小時。
> 6. **E1-8 的「修改前」匯出要用舊程式、在任何程式修改之前產生**，才能確保比對的是同一份資料庫內容。PM 版把它放在 `setup-db` 之後；本設計移到第 1 步，並在 `setup-db` 後、補抓後各比對一次（第〇節）。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | B2＋A4 融資融券 | E1 ETF | S10 核心（含 QA-04、06） | S11 | P19、P20 |
|---|---|---|---|---|---|
| `twstock/fetch.py` | | `ETF_CODE`、`is_etf_code()` | | | |
| `twstock/db.py` | 新表 `margin_trades`、`margin_market`、`etf_margin` | 新表 `etfs`、`etf_daily` | | | |
| `twstock/collectors/daily.py` | `parse_twse_margin`、`parse_tpex_margin`、`fetch_*_margin`、`merge_margin`、`merge_margin_market`；`DAY_KEYS`、`ALL_DATASETS` | `_twse_quote`、`_tpex_quote`、`parse_etf_quotes`、`fetch_*_daily` 回傳 ETF 原始列、`merge_etfs`、`merge_etf_daily`、`_quotes` 快取 | | | |
| `twstock/health.py` | `SPECS` 加 2 鍵、`_MARKET_SQL["margin"]` | `SPECS` 加 2 鍵、ETF 筆數查詢 | `all_missing_days`、`problem_lines(…, last_run)`、`load_state` 加 `last_run`、`schedule_status`、`last_run_line`、`suggest`、`check_report(…, schedule)` | | |
| `twstock/collectors/history.py` | 鍵順序照 `DAY_KEYS` | `SECONDS_PER_KEY`、`SHARED`、`day_seconds` | QA-04：月查詢攔截 `PARSE_ERRORS` | | |
| `twstock/export.py` | `usage`、`short_ratio`、`last_close`、`maint_ratio`、`stock_margin`、`market_margin`、`_load_margin`；`latest.margin`、個股 `margin` | `_load_etfs`、`etf_block`；`latest.etfs` | | | |
| `twstock/__main__.py` | `--only margin` | `--only etf` | QA-06：`--days` < 1 | | |
| `site/index.html` | | 兩組選單加「ETF」 | | | |
| `site/app.css` | `.g-stats .margin` | | | | `.night-old` |
| `site/app.js` | `marginCard()` | `ETF_SORT`、`renderEtf()`、路由 `etf` | 橫幅文字 | | P19 三處文字、P20 `futuresHTML` |
| `site/stock.js` | `MARGIN_NOTE`、四張指標卡 | | | | |
| `scripts/mac/install_schedule.sh` | | | | 加 `"22 30"` | |
| `scripts/windows/install_schedule.bat` | | | | 加 `%TASK%2230` | |
| `tests/test_iter04.py`（新檔） | T03～T08、T10、T13～T17 | T01、T02、T09～T12、T17、T22 | T18～T23、T25 | T14、T24 | （瀏覽器驗收） |
| `tests/test_iter03.py` | `World` 加融資融券端點與假資料 | `World` 行情含 ETF 與其他證券 | 橫幅兩處預期字串 | | |
| `README.md`、`__main__.py` docstring | 第七節清單 | 同左 | 同左 | 同左 | 同左 |

**工作量**：

| 項目 | 程式（含腳本） | 測試 |
|---|---|---|
| 新增 | 約 700 行 | `test_iter04.py` 527 行 |
| 刪改 | 約 90 行 | `test_iter03.py` 新增 50 行、改 9 行 |

這比 PM 估計的 620＋230 行略多，但原型已跑通、測試已寫好，**不需要依 PM 第五節第 13 點延後任何項目**。若 PG 仍覺得超量，依 PM 順序延後即可。程式對應的位置是：

1. `renderEtf` 的排序與篩選：`ETF_SORT` 只留 `tv`，並刪除 `segHTML` 與 `select`。
2. `marginCard` 的 `minibars` 那一行。
3. `check_report` 的 `schedule` 參數。
4. P19 的三處文字。

### 建議實作順序

與 PM 版的差異：

- **「隔離基線」移到第 1 步**，用舊程式匯出，見實測發現 6。
- 程式一次套用。原型已驗證 `daily.py`、`health.py`、`export.py` 彼此相依的部分。
- 補抓改用 `logs/iter04_history.py`。它等同 `history --start 2025-10-30 --only etf margin`，只是順手保存 QA 要的原始回應，**不多發請求**。

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 0 | **改表前確認已備份**：`ls -l ../_backups/`。必須有 `TwStock_before_round4.bak`（> 50 MB），且 `TwStock_before_round3.bak` 的大小與時間不變。**沒有備份就停下來回報，不要自行備份或繼續。** 本輪沒有 `backup` 指令 | 檔案存在 |
| 1 | **隔離基線（舊程式，改任何程式之前）**：`python3 -m twstock export`，然後 `mkdir -p logs/iter04_before && cp site/data/latest.json logs/iter04_before/ && cp -R site/data/stocks logs/iter04_before/`。同時用 SQL 記錄既有表筆數（B2-1、B2-13） | 檔案存在 |
| 2 | 套用附錄 C 的 `fetch.py`、`db.py` → `python3 -m twstock setup-db` 執行兩次 | 兩次都不報錯；既有表筆數不變；新的 5 張表存在且是空的 |
| 3 | 套用其餘 Python：`daily.py`、`health.py`、`history.py`、`export.py`、`__main__.py`；加入 `tests/test_iter04.py`（附錄 D）；修改 `tests/test_iter03.py` | `test_iter01`～`04` 全過，其中 T24 要等步驟 9 |
| 4 | **check 基線**：`python3 -m twstock check 2>&1 \| tee logs/iter04_check_before.log; echo rc=$?` | rc=1；4 個新資料集「缺 … 等 20 天」（B2-10、E1-10） |
| 5 | **隔離比對 1**（新程式、新表為空）：`python3 -m twstock export` → `python3 logs/iter04_compare.py logs/iter04_before site/data` | rc=0，「完全相同」 |
| 6 | **補抓**：`python3 logs/iter04_history.py 2>&1 \| tee -a logs/iter04_history.log`（附錄 E；約 39 分鐘）。中斷或被限流時，等 30 分鐘以上再用同一指令重跑。**期間不要執行 `collect` 或其他 `history`** | 「待抓 0 天」；`logs/iter04_raw_*.json` 4 個檔 |
| 7 | `python3 -m twstock check 2>&1 \| tee logs/iter04_check_after.log; echo rc=$?`；附錄 B 的 SQL | rc=0；B2-2～6、E1-1～5 |
| 8 | **隔離比對 2**：`python3 -m twstock export` → `python3 logs/iter04_compare.py logs/iter04_before site/data`；比較兩份 check log 的行情列 | rc=0；`latest.json` 增加 ≤ 100 KB（E1-8、B2-12） |
| 9 | 前端：`index.html`、`app.css`、`app.js`、`stock.js`；排程腳本 | 瀏覽器（8001，桌機與 375px）：B2-8、B2-9、E1-9、S10-4、P19、P20；`test_iter04` 全過 |
| 10 | README、`__main__.py` docstring（第七節）；`serve --port 8001 --no-browser` 自測，**完成後關閉伺服器** | 第七節清單 |

> **步驟 5 到步驟 8 之間不可執行 `collect`**。`collect` 會寫入新的行情或法人資料，使 E1-8 的比對失去意義。`history` 不算收集，`updated_at` 不變。

### 共通約定（沿用第 3 輪，以下是本輪新增）

- **三類分流**：行情回應與融資融券回應的每一列只會歸到下列其中一類。
  - **股票**：`fetch.is_valid_stock_code`，判斷不變。
  - **ETF**：`fetch.is_etf_code`。
  - **其他**：兩邊都不寫入，包括權證、TDR、ETN、受益證券、特別股。
  - 股票只寫 `stocks`／`daily_prices`／`margin_trades`；ETF 只寫 `etfs`／`etf_daily`／`etf_margin`。
- **ETF 不進 `stocks` 表**。所有既有個股統計（家數、成交額、類股、產業鏈、概念股、排行、自選、法人估算、`check` 的行情筆數）都以 `stocks` 為母體，**一行都不用改**。這就是隔離的保證：
  - `export.py` 既有的查詢完全沒動。
  - ETF 只出現在新增的 `latest.etfs`、`latest.margin.*.etf` 與維持率分子。
- **單位**：
  - 融資融券一律是**張**。
  - 官方融資金額存**仟元**，匯出時轉成**億**。
  - ETF 成交量匯出為**張**（股 ÷ 1,000），成交額為**億**。
- **增減** = 官方每列的「今日餘額 − 前日餘額」，不使用資料庫的前一交易日值。這樣不受漏收日影響，並與官方合計一致。
- **一天內的收集順序**（`DAY_KEYS`）：行情 → 指數 → **ETF 行情** → 本益比 → 法人 → 法人金額 → **融資融券**。融資融券的 ETF 列只寫入 `etfs` 已有的 ETF，所以 ETF 行情必須在前；`history` 的順序也一律照 `DAY_KEYS`。

### 資料集模型（`health.SPECS` 新增 4 鍵）

| 鍵 | 名稱 | 資料表（市場依） | 端點 | 筆數下限 | 回補 |
|---|---|---|---|---|---|
| `etf.TWSE` | 上市ETF | `etf_daily`（`etfs.market_type`） | 與上市行情同一個 `MI_INDEX` 回應 | 150 | `history --only etf` |
| `etf.TPEx` | 上櫃ETF | 同上 | 與上櫃行情同一個 `dailyQuotes` 回應 | 80 | 同上 |
| `margin.TWSE` | 上市融資融券 | `margin_trades`（`stocks.market_type`），**只算股票** | 證交所 `marginTrading/MI_MARGN?selectType=ALL` | 800 | `history --only margin` |
| `margin.TPEx` | 上櫃融資融券 | 同上 | 櫃買 `margin/balance`（POST） | 550 | 同上 |

- **下限依據**：
  - 2025-10-30：ETF 上市 204、上櫃 105；融資融券股票上市 1,028、上櫃 725。
  - 2026-11-03：ETF 245、118；融資融券股票 1,062、802。
  - 下限都低於一年內的最小值，加上既有的「近 20 日中位數 × 80%」規則；ETF 檔數一年內持續增加，不會誤報。
- **門檻只檢查融資融券的股票列與 ETF 行情**：
  - `etf_margin` 與 `margin_market` 由同一個 `_save` 交易寫入，不另設資料集。
  - ETF 融資融券漏寫會反映在維持率涵蓋率（< 99% 顯示「資料不足」）。
- 停資停券股的餘額為 0 或限額為 0 是正常的，`check` 只看市場層級筆數（PM 風險 7）。

### 口徑表（PM 第五節第 1 點：每個畫面數字）

| 位置 | 數字 | 口徑 | 單位 | 計算式 | 資料日 |
|---|---|---|---|---|---|
| 今日・信用交易卡 | 上市、上櫃融資餘額與增減、增減 % | **股票** | 萬張（滑過顯示張）、張、% | Σ`margin_trades.margin_balance`；Σ(今 − 前)；增減 ÷ Σ前日 | `margin.X.d` |
| 同上 | 融券餘額與增減 | **股票** | 萬張、張 | 同上（short_*） | 同上 |
| 同上 | 券資比 | **股票** | %（2 位） | Σ融券 ÷ Σ融資 | 同上 |
| 同上 | 融資維持率（自算）今日、前日 | **股票＋ETF**（分子）／**官方含 ETF**（分母） | %（1 位） | Σ(融資張數 × 1,000 × 收盤) ÷ (官方融資金額仟元 × 1,000)。收盤取該日或之前最近一次有成交的收盤；涵蓋率 < 99% →「資料不足」 | 同上、前一個融資融券日 |
| 同上 | 融資金額 | **官方含 ETF** | 億（1 位），▲▼億 | `margin_market.amount_balance` ÷ 10⁵；今 − 前 | 同上 |
| 同上 | ETF 另計（上市） | **只有 ETF** | 萬張、張 | Σ`etf_margin`（上市） | 同上 |
| 同上 | 20 日迷你柱 | **上市股票** | 張 | 各日 Σ(今 − 前) | 最近 20 個融資融券日 |
| 同上 | **不顯示** | 官方融資、融券**張數**與增減（含 ETF） | — | — | — |
| 個股頁 | 融資餘額、1 日、5 日 | 該股 | 張 | 今日餘額；今 − 前；今 − 第 5 個融資融券日前的餘額 | `margin.d` |
| 個股頁 | 融券餘額、1 日 | 該股 | 張 | 同上 | 同上 |
| 個股頁 | 券資比 | 該股 | %（2 位，四捨五入） | 融券 ÷ 融資；融資 0 → `--` | 同上 |
| 個股頁 | 融資使用率 | 該股 | %（2 位，**截斷**） | 融資餘額 × 10000 // 限額 / 100；上市限額 =「次一營業日限額」、上櫃 =「資限額」；限額 0 或空 → `--` | 同上 |
| 個股頁 | 註記（上市） | 官方註記 | 文字 | `O` 停止融資、`X` 停止融券、`@` 融資分配、`%` 融券分配、`!` 停止買賣，**次一營業日**狀況 | 同上 |
| ETF 頁 | 收盤、漲跌 % | ETF | 元、% | `etf_daily.close_price`；漲跌 ÷ (收盤 − 漲跌) | `etfs.dates[市場]` |
| ETF 頁 | 成交量、成交額 | ETF | 張、億（2 位） | 股 ÷ 1,000；元 ÷ 10⁸ | 同上 |
| ETF 頁 | 融資、融券餘額與增減 | ETF | 張 | `etf_margin`；今 − 前 | 該市場最新融資融券日 |
| 首頁家數、成交額、類股／產業鏈／概念股、泡泡圖、排行、自選、搜尋、法人估算 | （既有） | **股票**（不變） | — | 不讀任何 ETF 表 | — |
| 三大法人卡（上市官方） | （既有） | 官方含 ETF | 億 | 不變；P19 加一行說明 | — |

---

## B2＋A4. 融資融券（優先 1，含大盤維持率）

### B2-1 對應驗收條件（SA 修訂處標 ★）

| PM # | 條件 | 設計對應 |
|---|---|---|
| 1 | `setup-db` 建新表、可重複、既有表筆數不變 | DDL 全部 `IF OBJECT_ID(...) IS NULL`（B2-3）；實作步驟 1、2 |
| 2 | 244 交易日補抓完整、大盤表每天每市場 1 列、重跑 0 請求 | 附錄 B 的 SQL 1；T17 |
| 3 | 11/03 股票口徑數值 | 附錄 B 的 SQL 2；原型已用實際回應重現：上市 1,062 檔 6,345,620（−124,599）／129,630（+6,876）／2.04%；上櫃 802 檔 2,159,879（−40,082）／37,994（+1,780）／1.76% |
| 4 | 11/03 官方合計 | `margin_market`；SQL 2 的「官方」列；T03、T04 用實際回應驗證 |
| 5 ★ | 個股：2303 −10,597、2409 −3,524、2236 使用率、2376 券資比、3105 40.37%；00406A 不在個股表 | ★ 2236 = **85.46%**（截斷）、2376 = **33.67%**；T03、T05 |
| 6 | 維持率高於下限、QA 獨立重算一致到 0.1、mock 資料不足 | 預期值見附錄 B 第 3 節；SQL 3；T06、T08 |
| 7 | 2025-10-30 原始回應存 `logs/`、QA 比對 2330、5904 | `logs/iter04_history.py` 在本來就要抓的那一次保存（附錄 E） |
| 8 | 今日頁卡片、不出現官方融券增減、ETF 另計、20 日序列、尚未更新 | B2-7；node 煙霧測試已確認頁面文字沒有 63,031、6.3 萬、9,482,839、257,961 |
| 9 | 個股頁四卡、無信用交易、註記 | B2-7；★ 指定個股見下 |
| 10 | `check` 列出、基線 rc 1／0、`status.datasets` | `SPECS`；實作步驟 4、7 |
| 11 | mock #1～#6 | T13、T14、T15、T03／T04（#5）、T16 |
| 12 | `latest.json` ≤ 100 KB、375px、console | 實測約 +48 KB（B2-6）；B2-7 |
| 13 | 回歸 | 實作步驟 3、8 |
| 14 | README、`__main__.py` | 第七節 |

**★ B2-9 指定個股**（從 11/03 回應挑選，已用資料庫唯讀確認在 `stocks` 表）：

| 用途 | 上市 | 上櫃 |
|---|---|---|
| 不在信用交易清單 →「無信用交易」 | **6467 泰合** | **3485 敘豐** |
| 有註記 | **2414 精技**（`X` → 次一營業日停止融券）；另可看 2236（`@` 融資分配）、1589（`OX!`） | （上櫃備註本輪不解讀） |

### B2-2 資料來源（2026-11-03 實測，附錄 A）

| 端點 | 表 | 重點 |
|---|---|---|
| 證交所 `GET rwd/zh/marginTrading/MI_MARGN?response=json&date=YYYYMMDD&selectType=ALL` | 表 1「信用交易統計」：`項目, 買進, 賣出, 現金(券)償還, 前日餘額, 今日餘額`，3 列：`融資(交易單位)`、`融券(交易單位)`、`融資金額(仟元)`。表 2「融資融券彙總 (全部)」16 欄 | 表 2 **欄名重複**（買進、賣出、前日餘額…各兩次），依位置取值，並以 `groups = 股票(2)、融資(6)、融券(6)` 與位置欄名驗證。註記值有空白、`OX `、`X `、`@ `、`O `、`OX!` |
| 櫃買 `POST www/zh-tw/margin/balance`（`date=YYYY/MM/DD`） | 1 表 20 欄（欄名不重複）；`summary` 2 列：`合計(張)`、`融資金(仟元)`，與 `fields` 同欄位對齊 | `summary` 實測是**原生陣列**；字串也接受 |

**分流結果（11/03）**：

| 市場 | 股票 | ETF | 其他 | 合計列數 |
|---|---|---|---|---|
| 上市 | 1,062 | 240 | 4（TDR） | 1,306 |
| 上櫃 | 802 | 117 | 0 | 919 |

**股票＋ETF＋其他＝官方合計（11/03，張）**：

| 市場 | 項目 | 股票 | ETF | 其他 | 官方 |
|---|---|---|---|---|---|
| 上市 | 融資餘額 | 6,345,620 | 3,122,700 | 14,519（912000 晨訊科-DR） | **9,482,839** |
| 上市 | 融資增減 | −124,599 | +36,315 | +33 | **−88,251** |
| 上市 | 融券餘額 | 129,630 | 128,330 | 1 | **257,961** |
| 上市 | 融券增減 | +6,876 | +56,155 | 0 | **+63,031** |
| 上櫃 | 融資餘額 | 2,159,879 | 109,433 | 0 | **2,269,312** |
| 上櫃 | 融資增減 | −40,082 | +491 | 0 | **−39,591** |
| 上櫃 | 融券餘額 | 37,994 | 377 | 0 | **38,371** |
| 上櫃 | 融券增減 | +1,780 | −113 | 0 | **+1,667** |

**未公布、休市時的回應**（歸類為「官方尚無資料」，不是欄位不符）：

- 上市 `stat` 不是 `OK`，或明細表沒有列 → `([], None)`。
- 上櫃沒有任何有資料的表 → `([], None)`。

### B2-3 資料庫（`db.py` 的 `DDL`，接在 `market_holidays` 之後、索引之前；完整 DDL 見附錄 C）

| 表 | 用途 | 唯一鍵（MERGE 鍵） | 重點欄位 |
|---|---|---|---|
| `margin_trades` | 股票個股，**只寫 `stocks` 已有的股票**（JOIN `stocks`） | `UQ_margin_trades (stock_id, trade_date)` | `margin_buy, margin_sell, margin_redeem, margin_prev NOT NULL, margin_balance NOT NULL, margin_limit, short_sell, short_buy, short_redeem, short_prev NOT NULL, short_balance NOT NULL, short_limit, offset_lots, note NVARCHAR(20)` |
| `etf_margin` | ETF 個股，**只寫 `etfs` 已有的 ETF** | `UQ_etf_margin (etf_id, trade_date)` | 與 `margin_trades` 相同 |
| `margin_market` | 官方合計（含 ETF 與其他證券），每日每市場 1 列 | `UQ_margin_market (trade_date, market)` | `margin_prev, margin_balance, short_prev, short_balance`（張）、`amount_prev, amount_balance`（仟元），皆 `BIGINT NOT NULL` |

- `offset` 是 T-SQL 保留字，資券互抵欄名用 `offset_lots`。
- 註記存原文：去掉前後空白，截到 20 字，空的存 NULL。上櫃備註例如 `11OX   C`，本輪不解讀。
- 索引：`IX_margin_trades_date (trade_date)`（`check` 與匯出按日期查）。
- 資料量：股票一年約 45 萬列，ETF 融資融券約 8 萬列。

### B2-4 解析與收集（`daily.py`）

```python
MARGIN_COLS = ("margin_buy", "margin_sell", "margin_redeem", "margin_prev", "margin_balance", "margin_limit",
               "short_sell", "short_buy", "short_redeem", "short_prev", "short_balance", "short_limit", "offset_lots")
def parse_twse_margin(data: dict) -> tuple          # → (列, 官方合計 dict 或 None)
def parse_tpex_margin(data: dict) -> tuple          # 同上
def fetch_twse_margin(d: date) -> tuple             # GET MI_MARGN，經 fetch.request
def fetch_tpex_margin(d: date) -> tuple             # POST margin/balance
def merge_margin(cursor, trade_date, rows, kind)    # kind: "stock" → margin_trades JOIN stocks；"etf" → etf_margin JOIN etfs
def merge_margin_market(cursor, trade_date, market, total)
```

**上市欄位位置**（`TWSE_MARGIN_POS`）：

- 欄位：0 代號、2 買進、3 賣出、4 現金償還、5 前日餘額、6 今日餘額、7 次一營業日限額、8 買進、9 賣出、10 現券償還、11 前日餘額、12 今日餘額、13 次一營業日限額、14 資券互抵、15 註記。
- **融券的「賣出」是第 9 欄、「買進」是第 8 欄**。
- `groups` 的前 3 組必須等於 `[("股票",2),("融資",6),("融券",6)]`。任一不符就丟 `SchemaError`，訊息列出不符的位置。

**每一列**（`_margin_row`）：

- 數字以 `clean_number(…, int)` 解析。`N/A`、空字串會變成 `None`，限額為 `None` 時使用率顯示 `--`。
- **前日餘額或今日餘額無法解析的列略過**，因為資料表是 NOT NULL。
- 列數不足 16 欄（上櫃則是不足欄數）也略過。

**官方合計**（`_margin_total`）：6 個值任一為空就丟 `SchemaError`。

**`_collect_key` 的 margin 分支**：

1. 抓回應。
2. 分出 `stocks`（`is_valid_stock_code`）與 `etfs`（`is_etf_code`）。
3. 沒有股票列就回傳 0，代表官方尚無資料。
4. 否則**用同一個 `_save`（一個交易）**依序寫入 `merge_margin(stock)`、`merge_margin(etf)`（有 ETF 列時）、`merge_margin_market`，回傳股票列數。

**`collect_for_date`**：

- 同市場行情本次寫入 0 筆時，不發融資融券請求，與本益比、法人相同（B2-11 #3）。
- 休市日不在 `due_days` 內（#4）。

**每日請求數**：齊全時 0 次；需要時每市場 1 次；未公布時每次嘗試多 2 次。**不另設最早嘗試時間**，異常判定沿用 `DEADLINE` 22:00。

### B2-5 大盤融資維持率（A4）

- **公式**：每市場、每個融資融券日 D 計算一次。
  - 分子 = Σ(融資張數 × 1,000 × 收盤)，股票取 `margin_trades` 該日的列，ETF 取 `etf_margin` 該日的列。
  - 分母 = `margin_market.amount_balance`（仟元）× 1,000。
  - 維持率 = 分子 ÷ 分母 × 100，取小數 2 位，畫面顯示 1 位。
- **收盤**（`last_close`）：取日期 ≤ D 的最後一個非空收盤。股票來自匯出已載入的日線，ETF 來自 `etf_daily`（D 前 60 天起）。當日沒有成交就用最近收盤。
- **涵蓋率** = 有收盤的融資張數 ÷ 官方融資張數（`margin_balance`）× 100。**< 99.0（`COVER_MIN`）時維持率為 `null`，畫面顯示「資料不足」**；沒有融資金額時也是 `null`。
- **前日**（`mr0`）：用同一套規則計算前一個融資融券日。
- **市場歸屬**：股票依 `stocks.market_type`，ETF 依 `etfs.market_type`。
  - 5236、8908 在 2025-10-30 時屬上櫃、現為上市，舊日期會使上櫃涵蓋率略低、上市略高。
  - 這只影響補抓區間的早期日期，畫面只顯示最新兩天。

### B2-6 匯出（`export.py`）

**`latest.json` 新增 `margin`**：沒有任何融資融券資料時為 `null`；某市場沒有資料時沒有該鍵。

```json
"margin": {
  "TWSE": {"d": "2026-11-03", "mb": 6345620, "m1": -124599, "mp": -1.93, "sb": 129630, "s1": 6876, "sp": 5.6, "sr": 2.04,
           "amt": 5997.7, "amt1": -229.2, "mr": 162.66, "mr0": 171.67, "cov": 99.84,
           "etf": {"mb": 3122700, "m1": 36315, "sb": 128330, "s1": 56155},
           "d20": ["…（20 個日期）", "2026-11-03"], "m20": [ …, -124599]},
  "TPEx": { …同上，etf 為上櫃 ETF… }
}
```

| 鍵 | 意義 |
|---|---|
| `d` | 該市場最新融資融券日 |
| `mb`、`m1`、`mp` | 股票融資餘額（張）、增減（張）、增減 %（÷ 前日合計） |
| `sb`、`s1`、`sp` | 股票融券餘額、增減、增減 % |
| `sr` | 股票券資比 % |
| `amt`、`amt1` | 官方融資金額（億，含 ETF）、增減（億） |
| `mr`、`mr0`、`cov` | 維持率（今日、前日，`null` = 資料不足）、今日涵蓋率 % |
| `etf` | 該市場 ETF 融資、融券餘額與增減（張） |
| `d20`、`m20` | 最近 20 個融資融券日與股票融資增減（張） |

**個股 `stocks/{代號}.json` 新增 `margin`**，只在該股市場有融資融券資料時才有這個鍵：

```json
"margin": {"d": "2026-11-03", "mb": 146467, "m1": -10597, "m5": …, "sb": 872, "s1": -420, "sr": 0.6, "mu": 4.66}
```

- `m5`：與往前第 5 個融資融券日比較，不足 6 天為 `null`。
- `nt`：只在有註記時出現。
- 該股當天不在清單（無信用交易）時，`margin` 為 **`null`**。
- 區別：**鍵不存在**表示尚無融資融券資料，不顯示卡片；**`null`** 表示顯示「無信用交易」。

**大小**（以 11/03 實際資料計算）：

- `latest.margin` 約 1.2 KB，`latest.etfs` 46,340 bytes（363 檔）。**`latest.json` 合計增加約 48 KB**，在 ≤ 100 KB 內。
- 個股檔每檔約多 100～130 bytes。

### B2-7 畫面

**今日頁「信用交易」卡**：放在 `g-stats` 區，接在三大法人卡之後，`class="card stat idx margin"`。

- 桌機：卡片佔滿一整列（`grid-column:1/-1`）。
- 375px：同樣一整列，每行自動換行，迷你柱寬 100%。
- `.stat .s` 沒有 `nowrap`，不會造成整頁水平捲動。

文案如下，數字取自 11/03 原型的實際輸出，`│` 表示換行：

```
信用交易 11/03（股票，不含 ETF）
上市　融資 634.6 萬張 -124,599（-1.93%）　融券 13.0 萬張 +6,876　券資比 2.04%
上櫃　融資 216.0 萬張 -40,082（-1.82%）　融券 3.8 萬張 +1,780　券資比 1.76%
融資維持率（自算）上市 162.7%（前日 171.7%）　上櫃 156.8%（前日 167.2%）
融資金額（官方，含 ETF）上市 5,997.7 億 ▼229.2 億　上櫃 1,965.6 億 ▼78.5 億
ETF 另計（不計入上方）：上市 ETF 融資 312.3 萬張 +36,315、融券 12.8 萬張 +56,155
[20 日迷你柱：紅 = 增、綠 = 減]
上市股票融資增減（張），近 20 日（MM/DD～11/03）
維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」
```

- 「萬張」的數字有 `title="6,345,620 張"`。
- 兩市場資料日不同時，較舊的那一行尾端加「（MM/DD）」。
- **卡片資料日（兩市場較新者）早於 `L.date` 時，標題加「（尚未更新）」**，與 `instiCard()` 相同（B2-8）。
- 維持率為 `null` 時顯示「資料不足」，前日為 `null` 時顯示 `--`。
- **官方融資、融券張數與官方融券增減一律不顯示。**

**個股頁指標卡**：接在「投信5日」之後。

| 情況 | 卡片 |
|---|---|
| 有資料 | 「融資餘額／146,467 張／1日 -10,597　5日 …」「融券餘額／872 張／1日 -420」「券資比／0.60%／資料 11/03」「融資使用率／4.66%／資料 11/03」 |
| `margin === null` | 一張「信用交易／無信用交易／不在融資融券清單」（與 0 張區分） |
| 鍵不存在 | 不顯示 |
| 上市有註記 | 融資使用率卡副標改為「次一營業日停止融券」（2414）、「次一營業日融資分配」（2236）、「次一營業日停止融資、停止融券、停止買賣」（1589） |
| 限額 0（停資） | 使用率 `--` |

卡片與既有 `stat` 卡同一格式，375px 時兩欄排列。

### B2-8 邊界情況

| 情況 | 行為 |
|---|---|
| 行情已公布、融資融券未公布 | `([], None)` → 0 筆 → 22:00 前「尚未公布」，之後「異常」（S11 的 22:30 判定並通知一次） |
| 欄位、`groups`、統計表或 `summary` 改版 | `SchemaError` → 只有該市場融資融券異常，其他資料集照常；`history` 印「官方欄位不符」、rc=1、無 Traceback |
| 某列餘額無法解析 | 略過該列（筆數下降，`assess` 依筆數判斷） |
| 新上市 ETF 當天的融資融券列 | `etf.*` 先寫入 `etfs`，所以 ETF 列也寫得進去；若 ETF 行情失敗，`etf_margin` 只寫已存在的 ETF（維持率涵蓋率會反映） |
| 股票不在 `stocks` 表（例如新上市還沒收行情） | JOIN 不到，不寫入 |
| 全部股票停資停券 | 不可能，下限 800／550 |
| 某市場只有 1 個融資融券日 | `mr0` 為 `null`，畫面顯示「前日 --」；`d20` 只有 1 天 |

### B2-9 測試案例

| # | 測試 | 內容 |
|---|---|---|
| T03 | `test_t03_parse_twse_margin` | 11/03 實際的 8 列與統計表：官方合計、2303 全部 13 欄、註記 `@`／`X`／`OX!`、00406A 融券 +65,270、`N/A`／空字串、未公布、3 種改版 → `SchemaError` |
| T04 | `test_t04_parse_tpex_margin` | 實際 4 列（含 00679B、006201、2035 `11OX   C`、3105）、`summary` 陣列與字串、空表、2 種改版 |
| T05 | `test_t05_ratios` | 2236 85.46、3105 40.37、限額 0、2376 33.67、上市股票 2.04 |
| T06 | `test_t06_maint_ratio` | `last_close` 取最近收盤；涵蓋率剛好 99% 顯示、98.9% 不顯示；金額 0 |
| T07 | `test_t07_stock_margin` | 1 日／5 日、不足 6 天、停資（`mu` None、`sr` None）、不在清單 → None |
| T08 | `test_t08_market_margin` | 頭條只算股票、ETF 另計、億換算、涵蓋率 98.89 → 資料不足、前日、20 日序列 |
| T10 | `test_t10_new_day_same_requests` | 新的一天：融資融券各 1 次；股票、ETF、其他分流正確；寫入 4 張新表 |
| T13 | `test_t13_margin_not_yet` | B2-11 #1 |
| T14 | `test_t14_margin_deadline_notify_once` | B2-11 #2、S11-3（`osascript` 被 mock，不會真的跳通知） |
| T15 | `test_t15_no_margin_request_without_prices` | B2-11 #3、#4 |
| T16 | `test_t16_margin_schema_change` | B2-11 #6（兩個端點各一次） |
| T17 | `test_t17_history_order_and_rerun` | `--only margin etf`：每天 ETF 行情先於融資融券、重跑 0 請求、預估時間 |
| QA | 瀏覽器 | B2-8：以 8001 開今日頁。修改 `site/data/latest.json` 的 `margin.TWSE.d`、`margin.TPEx.d` 為前一日，確認出現「（尚未更新）」，測完重新 `export` 還原。B2-9：2303、6467、3485、2414 |

---

## E1. ETF 資訊（優先 1）

### E1-1 對應驗收條件

| PM # | 條件 | 設計對應 |
|---|---|---|
| 1 | 新表、`stocks` 無 `00` 開頭 | 附錄 B 的 SQL 5；ETF 只寫 `etfs`（`is_valid_stock_code` 本來就排除 `00`） |
| 2 | 定義與 11/03 檔數 | `is_etf_code`；T01；11/03 符合規則的列：**上市 245、上櫃 118**（`etf_daily` 11/03 的筆數必須相同） |
| 3 | 244 天完整、重跑 0 請求、記錄請求數與耗時 | SQL 1；T17；`logs/iter04_history.log` 每次執行的結尾印外部請求數與耗時 |
| 4 | 4 檔 ETF 數值與原始回應一致；00406A 最早一筆 | SQL 4；`logs/iter04_raw_MI_INDEX_20261103.json`、`iter04_raw_dailyQuotes_20261103.json`；預期值見附錄 B 第 4 節 |
| 5 ★ | ETF 融資融券確切值與差額說明 | ★ 上市 ETF 融資 **3,122,700（+36,315）**、融券 **128,330（+56,155）**；差額見 B2-2 |
| 6 | 每日不增加請求；只缺 ETF 時每市場 1 次、不改股票列 | `_quotes` 快取；T10、T11 |
| 7 | 沒有 ETF 列或欄位缺漏 → 只有 `etf.*` 異常 | T12、T22 |
| 8 | 隔離前後比對 | E1-6 |
| 9 | ETF 頁 | E1-5 |
| 10 | `check` 列出 ETF | `SPECS`；T19 |
| 11 | README、`__main__.py` | 第七節 |

### E1-2 定義（`fetch.py`）

```python
ETF_CODE = re.compile(r"00\d{2,4}[A-Z]?")
def is_etf_code(code: str) -> bool:      # 去空白後長度 ≤ 6 且完全符合
```

**是 ETF**：0050、00878、006201、00406A、00679B、00631L、00632R、00635U、00687C、00625K、00981T、00982D。11/03 實際出現的字尾有 A、B、C、D、K、L、R、T、U。

**不是 ETF**（T01，代號取自 11/03 回應）：

| 類別 | 代號 |
|---|---|
| ETN | 020000、02001L |
| 受益證券 | 01001T |
| TDR | 910322、912000 |
| 特別股 | 1101B、2881A |
| 權證 | 710000、73000U |
| 股票 | 2330、6467 |
| 長度超過 6 | 0050123 |

`is_valid_stock_code` 不變，兩者互斥：`00` 開頭的一律不是股票。

### E1-3 資料來源與收集（`daily.py`）

- **不增加請求**：上市 `MI_INDEX?type=ALLBUT0999`、上櫃 `dailyQuotes` 原本就含 ETF 列，欄位與股票相同。2025-10-30 的回應也已實測（附錄 A）。
- `_twse_quote(row, idx)`、`_tpex_quote(row, idx)`：從原本的迴圈抽出，股票與 ETF 共用，產出的 dict 鍵相同。
- `fetch_twse_daily(d)` 改為回傳 `(股票列, 加權指數, (欄位索引, ETF 原始列))`，休市時回傳 `([], None, ({}, []))`。`fetch_tpex_daily(d)` 改為同形，第 2 項為 `None`。
- `parse_etf_quotes(raw, market)`：
  - 把 ETF 原始列轉成寫入用 dict。
  - **原始列為空時丟 `SchemaError("TWSE 行情回應沒有任何 ETF 列")`**。只有在股票列存在時才會呼叫，所以這代表格式異常。
- `_quotes(market, d, cache)`：同一次執行、同一市場只抓一次。`prices.TWSE`、`index.TAIEX`、`etf.TWSE` 共用；上櫃同理。**失敗也快取**，例外原樣再丟，同一次執行不重打（T12）。
- `_collect_key` 的 etf 分支：
  1. 股票列為空（未公布、休市）時回傳 0。
  2. 否則 `parse_etf_quotes`。
  3. 用一個 `_save` 依序寫入 `merge_etfs` 與 `merge_etf_daily`，回傳 ETF 筆數。
  - **只缺 ETF 的日子只會執行這個分支**：不寫 `daily_prices`、不寫 `stocks`、不寫指數（T11：`merges` 只有 `etfs`、`etf_daily`）。

### E1-4 資料庫

| 表 | 唯一鍵（MERGE 鍵） | 欄位 |
|---|---|---|
| `etfs` | `UQ_etf_code (etf_code)` | `etf_id` 自動編號、`etf_code`、`etf_name`、`market_type`（CHECK `TWSE`／`TPEx`）、`created_at`、`updated_at` |
| `etf_daily` | `UQ_etf_daily (etf_id, trade_date)` | 開高低收、`volume`（股）、`trade_value`（元）、`trade_count`、`change`，與 `daily_prices` 同型別 |

- 索引：`IX_etf_daily_date (trade_date)`。
- **`merge_etfs` 比照第 3 輪 S6**：名稱、市場別只在 `trade_date ≥ etf_daily 最新日期` 或表為空時更新，補抓舊日期不覆蓋。

### E1-5 ETF 列表頁（`#/etf`）

- **選單**：上方分頁在「排行」與「自選」之間加「ETF」；手機底部選單也加一個（三條橫線圖示），變成 5 個，375px 每個 75px。
- **資料**：`latest.etfs = {"dates": {"TWSE": "2026-11-03", "TPEx": "2026-11-03"}, "rows": {代號: 列}}`，每一列如下：

  ```json
  {"n": "元大台灣50", "m": "TWSE", "c": 100.6, "ch": -3.5, "p": -3.36, "v": 302407, "tv": 307.59,
   "mb": 28986, "m1": 1555, "sb": 227, "s1": -1}
  ```

  - `v` 為張，`tv` 為億。
  - `mb`～`s1` 只在該 ETF 有最新融資融券列時出現。
  - 無成交時 `c`、`p` 為 `null`。
- **版面**：
  - 標題列依序是「ETF」、兩市場資料日、`全部／上市／上櫃` 分段鈕、排序下拉（成交額、漲幅、跌幅、融資增減、融券增減）。
  - 下面一張表：ETF（名稱，下一行為代號與市場）、收盤、漲跌、成交量、成交額、融資餘額、融資增減、融券餘額、融券增減。
  - 表下說明：「共 N 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。」
- **排序**：空值永遠排最後；漲跌、增減上色規則與排行頁相同。排序與市場的選擇記在 `localStorage`（`tw.etfSort`、`tw.etfMkt`）。
- **375px**：表格在 `.tbl-wrap` 內水平捲動（既有樣式 `overflow-x:auto`），標題列 `flex-wrap` 換行，不會造成整頁捲動。
- **沒有 `etfs` 時**：顯示「尚無 ETF 資料：請在收集資料的電腦執行 python3 -m twstock history --start 2025-10-30 --only etf margin」。
- 本輪 ETF 列不連到個別頁。

**node 煙霧測試結果**（原型 `app.js` 配 11/03 實際的 363 檔）：

- 全部 363 列，依成交額排序時第一列是 0050，00406A 顯示 0.00%。
- 篩選上櫃剩 118 列；改依融券增減排序時，第一列是 00406A 主動中信台灣收益。

### E1-6 隔離前後比對（E1-8）

**工具**：`logs/iter04_compare.py before after`（附錄 E）。

- **`latest.json`**：除了 `status`、`margin`、`etfs` 以外，每個頂層鍵**完全相同**，用 JSON 值比較。
  - 範圍包括 `updated_at`、`date`、`flow_date`、`dates`、`market`（家數、成交額）、`insti*`、`index`、`hl_from`、`futures*`、`forecast`、`groups`（三種分組的成員、數值、回放座標），以及 `stocks`（代號集合與每個欄位）。
  - `status` 排除是因為 `exported_at` 與 `datasets` 必然改變。
- **`stocks/*.json`**：檔案集合相同，每檔除了 `margin` 以外完全相同。
- **成交額前 10 名**：排行頁的母體就是 `latest.stocks`，依 `tv` 排序，工具會另外印出。
- **`check` 的行情列**：比較 `logs/iter04_check_before.log` 與 `iter04_check_after.log` 中「上市行情」「上櫃行情」兩行的筆數與中位數，`diff <(grep 行情 before) <(grep 行情 after)` 應無差異。
  - 涵蓋欄可能因日期推移不同，所以兩份 log 要在同一天產生。

**兩次比對**（實作步驟 5、8）都必須 rc=0。原型以 T10 確認股票列筆數不含 ETF 與其他證券。

### E1-7 邊界情況

| 情況 | 行為 |
|---|---|
| 新上市 ETF | 第一次出現時 INSERT 到 `etfs`，之後每天 MERGE |
| ETF 下市 | `etfs` 保留，不再有新日線；ETF 頁只列最新日有日線的 ETF |
| ETF 改名、轉市場 | 只在最新日期更新（`merge_etfs` 的 `@latest` 條件） |
| 無成交（收盤 `--`） | `close_price` 為 NULL；ETF 頁顯示「無成交」；維持率用最近收盤 |
| 漲跌為 `X`（不比價，例如 00406A 11/03） | 上市：價差 0.00、符號 `X` → `change = 0.0` |
| 上櫃 `---` | `clean_number` → None |
| 行情有股票列但沒有任何 ETF 列 | `SchemaError` → 只有 `etf.*` 異常（T12） |
| 只缺 ETF 的日子 | 每市場 1 次請求，只寫 ETF（T11） |

### E1-8 測試案例

| # | 測試 | 內容 |
|---|---|---|
| T01 | `test_t01_etf_code` | 12 個 ETF、12 個非 ETF |
| T02 | `test_t02_quotes_split` | 11/03 實際行情列：上市 2330 一檔股票；0050、00406A、00666R、00878 是 ETF；01001T、020000、1101B、910322 兩邊都不收。核對 0050、00878、00406A、00679B 的數值；無 ETF 列 → `SchemaError`；休市 |
| T09 | `test_t09_etf_block` | 0050 整列、無成交、無融資融券、上櫃 |
| T10 | `test_t10_new_day_same_requests` | E1-6：`MI_INDEX`、`dailyQuotes` 各 1 次；股票 1,100／900、ETF 250／120 |
| T11 | `test_t11_only_etf_missing` | E1-6：只缺 ETF |
| T12 | `test_t12_no_etf_rows` | E1-7 |
| T17 | `test_t17_history_order_and_rerun` | 順序、重跑 |
| T22 | `test_t22_qa04_history_schema` | `history --only etf` 欄位不符 |
| QA | 瀏覽器 | E1-9：桌機與 375px；點兩組選單；排序 5 種、市場 3 種；0050、00878、00406A、00679B 與 SQL 4 一致；console 無 error |

---

## 歷史補抓（B2、E1 共用，PG 執行一次）

- **指令**：`python3 logs/iter04_history.py 2>&1 | tee -a logs/iter04_history.log`。
  - 腳本內容等同 `python3 -m twstock history --start 2025-10-30 --only etf margin`，經過 `history` 的鎖與既有流程。
  - 它在本來就要抓的那一次請求中，把下列 4 個回應存到 `logs/`：
    - `iter04_raw_MI_MARGN_20251030.json`
    - `iter04_raw_margin_balance_20251030.json`
    - `iter04_raw_MI_INDEX_20261103.json`
    - `iter04_raw_dailyQuotes_20261103.json`
  - 回應抓到就立刻寫檔，中斷重跑也不會遺失。
- **範圍**：
  - 2025-10-30～今天，244 個交易日（到 11/03）。今天以後多出的交易日每天多 4 次請求。
  - 每天依 `DAY_KEYS` 順序：上市 `MI_INDEX`（只寫 ETF）→ 上櫃 `dailyQuotes`（只寫 ETF）→ 上市 `MI_MARGN` → 上櫃 `margin/balance`。
  - 共 **976 次**，證交所與櫃買各 488 次。
- **預估**：`history` 開頭會印「預估約 38.6 分鐘」（`SECONDS_PER_KEY`：etf.TWSE 4、etf.TPEx 1、margin.TWSE 4、margin.TPEx 0.5）。實際約 40 分鐘。
  - 若同一天也要抓行情（不帶 `--only` 時），ETF 共用回應、不另計時（`SHARED`、`day_seconds`）。
- **可中斷重跑**：
  - 每天每個資料集各自寫入、各自 commit。
  - 重跑時 `missing_keys` 只挑還缺的資料集，「待抓 0 天」時 0 個請求（T17）。
  - 被封鎖時 `history` 印「疑似被封鎖」並停止（rc=1），等 30 分鐘以上用同一指令重跑。
  - 欄位不符時印「官方欄位不符」並停止，不出現 Traceback（QA-04）。
- **`history` 預設資料集**：`ALL_DATASETS` 改為 `prices pe insti etf margin`。不帶 `--only` 的補抓也會補 ETF 與融資融券，S10 建議的 `history --start …` 因此能補齊所有每日資料集。
- **記錄**（寫進 `04-dev.md`）：
  - 實際請求數與耗時：`iter04_history.py` 結束時印「🌐 外部請求 N 次，耗時 M 分鐘」（`fetch.request_count()`）。中斷重跑時，每次的數字要相加。
  - 00406A 最早一筆的日期：SQL 4 的第二段。
  - 11/03 兩市場 ETF 檔數：245、118。

---

## S10 核心. `check` 與橫幅說出原因與下一步（含 QA-04、QA-06）

### S10-1 對應驗收條件

| PM # | 設計對應 |
|---|---|
| 1 | `check_report` 開頭兩行、`all_missing_days`、`suggest`；T18 |
| 2 | 部分缺不合併、`suggest` 只在有異常時印；T19 |
| 3 | `schedule_status(platform, home)` 只做 `Path.exists()`；T20 以 mock 讓 `subprocess.run`、`Popen` 被呼叫就失敗 |
| 4 | `freshLines` 文字；T25 以 node 執行真正的 `app.js`；`test_iter03` 兩處預期字串同步 |
| 5 | QA-04：`history` 月查詢迴圈攔截 `PARSE_ERRORS`，每日迴圈本來就有；T16、T22（`tpex_index`／`margin`／`etf`） |
| 6 | QA-06：`cmd_check` 先檢查 `--days < 1`，不連資料庫；T23 |
| 7 | T18：`fetch._SESSION.request`、`db.connect` 呼叫 0 次 |
| 8 | 第七節 |

### S10-2 `check` 輸出

以 T18 的情境為例：現在 11/03 10:00，11/02 整天缺，以下是原型的實際輸出（節錄）。

```
📋 資料完整性檢查：近 20 個交易日 2026-10-01 ～ 2026-11-02（現在 2026-11-03 10:00，台灣時間）
🕘 最後一次收集：2026-10-31 13:38（collect --catch-up，有新資料）
🗓️  排程：未安裝（安裝方式見 README，由使用者自行執行）

資料集          涵蓋         最新日     筆數    中位數  本益比/淨值比/殖利率  狀態
上市行情      19/20   2026-10-30  1,086  1,086                        ❌ 異常
…（共 15 個資料集，新增 上市ETF、上櫃ETF、上市融資融券、上櫃融資融券）
處置／注意股最後成功：2026-10-31 13:38

❌ 2026-11-02 全部資料集都沒有：最後一次收集是 10/31 13:38，之後沒有執行收集

結果：異常 1 項
👉 請執行 python3 -m twstock collect --catch-up
```

**最後一次收集**（`load_state` 新增 `last_run`）：

- 來源是最新一筆 `collect_runs`，含 `finished_at`、`command`、`new_data`。
- `command` 對照：`catch-up` →「collect --catch-up」，`date` →「collect --date」，其他 →「收集」。
- 沒有紀錄時顯示「尚無執行紀錄」。
- 舊的 3 欄假資料仍相容（`*extra`）。

**排程**：

| 情況 | 顯示 |
|---|---|
| Mac，`~/Library/LaunchAgents/com.twstock.collect.plist` 存在 | 「已安裝（路徑）」 |
| Mac，檔案不存在 | 「未安裝（安裝方式見 README，由使用者自行執行）」 |
| 非 Mac | 「無法判斷，請在工作排程器確認」 |

- **不呼叫 `launchctl`、`schtasks`。**
- `check_report` 是純函式，`schedule` 由 `run_check` 傳入，沒有傳時不印這一行。

**全缺合併**：

- 某交易日的**每個資料集**都是「異常且 0 筆」時，合併成一行。休市與臨時休市日本來就不在清單內。
- 說明文字依最後一次收集時間而定：
  - 早於該日 15:00：「最後一次收集是 MM/DD HH:MM，之後沒有執行收集」。
  - 晚於或等於該日 15:00：「最後一次收集 MM/DD HH:MM 也沒有取得」（例如被限流）。
- 多天時用「、」連接，超過 8 天時顯示「等 N 天」。
- 這些日期不再逐資料集列出。

**建議指令**：只在「結果：異常」時印。以最早的異常日距今幾個交易日（N，含當天）決定：

| N | 建議 |
|---|---|
| ≤ 10（`--catch-up` 預設） | `👉 請執行 python3 -m twstock collect --catch-up` |
| ≤ 30 | `… collect --catch-up --days N` |
| > 30 | `👉 請執行 python3 -m twstock history --start 最早異常日，再執行 python3 -m twstock collect --catch-up` |

- 只有處置／注意股落後時，也建議 `collect --catch-up`。
- `CATCHUP_DAYS = 10`、`CATCHUP_MAX = 30` 與 `catchup.DEFAULT_DAYS`、`MAX_DAYS` 同值，`health` 不匯入 `collectors`，避免循環匯入。
- 實作步驟 4 的基線會建議 `--days 20`（新資料集 20 天都缺）。這是預期行為，PG 照本設計用 `history` 補抓即可。

### S10-3 網站橫幅（`app.js` 的 `freshLines`）

「資料停在 10/30，最新交易日為 11/02，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up」

- 只改這一句，判斷不變。
- 375px 時橫幅本來就會換行。

### S10-4 測試案例

| 測試 | 內容 |
|---|---|
| T18 `test_t18_check_whole_day_missing` | S10-1 的全部；另外三種情況：已收集仍全缺、缺 12 天 → `--days 12`、缺 35 天 → `history` |
| T19 `test_t19_check_partial_pending` | S10-2；新資料集出現在表格 |
| T20 `test_t20_schedule_status_readonly` | S10-3 |
| T21 `test_t21_load_state_compat` | 4 欄、3 欄、空 |
| T22 `test_t22_qa04_history_schema` | S10-5（含 CLI rc=1） |
| T23 `test_t23_qa06_check_days` | S10-6 |
| T25 `test_t25_banner_text` | S10-4（沒有 node 時略過） |

---

## S11. 排程加一次 22:30

- `install_schedule.sh`：
  - 第 2 行說明改為「週一到週五 17:30、19:30、21:45、22:30…（22:30 負責當天的異常判定）」。
  - 迴圈改為 `for t in "17 30" "19 30" "21 45" "22 30"`。
  - 完成訊息加「22:30」。
- `install_schedule.bat`：
  - 第 3 行說明加 22:30。
  - 第 17 行（`%TASK%2145` 的 Delete）之後加 `schtasks /Delete /TN %TASK%2230 /F >nul 2>&1`。`/uninstall` 與安裝前的清除共用這一段，所以 `/uninstall` 會刪除 4 個工作。
  - 第 24 行（2145 的 Create）之後加 `schtasks /Create /TN %TASK%2230 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 22:30 /F`。
  - 完成訊息加 22:30。
  - **檔案維持 CRLF**，請用編輯器修改，不要用會轉成 LF 的工具；附錄 C 的 diff 已去掉 CR。
- `DEADLINE` 維持 22:00，`health.py` 不改。
- **驗證**（只用 `--print` 與靜態檢查）：
  - `bash -n scripts/mac/install_schedule.sh`。
  - `bash scripts/mac/install_schedule.sh --print > /tmp/x.plist && plutil -lint /tmp/x.plist`：20 組 `StartCalendarInterval`、`RunAtLoad`、`--notify`。原型已驗證。
  - T24 以 `HOME=暫存目錄` 執行 `--print`，以 `plistlib` 解析，並確認沒有寫任何檔案。
  - 測試結束後，`launchctl list | grep twstock` 無結果，`~/Library/LaunchAgents/com.twstock*` 不存在（S11-4，QA 用唯讀指令確認）。
- 22:30 的 mock 判定：T14。

---

## P19（標示）、P20

**P19**（`app.js`，只改文字）：

| 位置 | 改後 |
|---|---|
| 「錢流去哪」卡標題右側 | 加 `<span class="muted small">估算，不含 ETF</span>` |
| 「法人買超」表頭副標 | 「MM/DD，億，估算，不含 ETF」 |
| 「法人賣超」表頭副標 | 同上 |
| 三大法人卡（上市官方） | 外資／投信／自營那行之後加一行「官方含 ETF 與權證避險，與下方估算口徑不同」 |

尚無官方資料時的估算卡不改。

**P20**（`futuresHTML`）：

- 夜盤歸屬日 ≤ 日盤日期時，文字為「**前一夜盤**（11/02 15:00～11/03 05:00）　收 44,310 -917 (-2.03%)」，**排在「成交量」之前**，並加 `class="night-old"`（`opacity:.7`）。
- 歸屬日晚於日盤日期時，文字為「**最新夜盤**（11/03 15:00～11/04 05:00）…」，維持在「未平倉」之後。
- node 煙霧測試已確認兩種文字與位置。
- **QA**：把 `latest.json` 的 `futures.night.date` 改為 2026-11-04，確認顯示「最新夜盤」，測完重新 `export` 還原。

---

## 七、README 與 `__main__.py` 修改清單

### README

| # | 段落 | 修改 |
|---|---|---|
| 1 | 「安裝」第 40 行（新增資料表要 `setup-db`） | 括號內加「第 4 輪的 `etfs`、`etf_daily`、`margin_trades`、`etf_margin`、`margin_market`」 |
| 2 | 「日常使用」指令區 `history --start 2026-01-02` | 說明改為「補抓歷史（行情、本益比、法人、ETF、融資融券），只補缺的，可中斷重跑」 |
| 3 | 同上 | 新增一行 `python -m twstock history --start 2025-10-30 --only etf margin   # 只補 ETF 行情與融資融券（同一天 ETF 先於融資融券；一年約 976 個請求、40 分鐘）` |
| 4 | 同上 `check` 那一行 | 說明改為「…開頭列最後一次收集與排程狀態；有異常時印建議指令並回傳 1（`--days` 至少 1）」 |
| 5 | 同上 | 新增 `python3 tests/test_iter04.py   # 第 4 輪測試` |
| 6 | 「### 自動排程（週一至週五 17:30、19:30、21:45）」 | 標題與內文改為四個時間；加一句「22:30 負責當天的異常判定（融資融券等晚間資料 22:00 前未公布才算異常）」；Windows「會建立三個工作」改「四個工作」；保留「**以下步驟由使用者自行執行**」 |
| 7 | 「注意事項」新增：融資融券 | 來源（上市 MI_MARGN、上櫃 margin/balance，每市場每日 1 個請求）；當天 22:00 前未公布記「尚未公布」；**今日卡頭條是股票口徑（不含 ETF）**，官方含 ETF 的數字只列融資金額；ETF 另計一行；官方融資、融券張數不顯示的原因（例：11/03 官方融券 +63,031，其中 00406A 一檔 +65,270） |
| 8 | 同上：使用率、券資比 | 使用率 = 融資餘額 ÷ 限額（上市用次一營業日限額，上櫃用資限額），截斷到小數 2 位；券資比 = 融券 ÷ 融資；停資停券（上市註記 O、X、@、%、!，表示**次一營業日**狀況）；「無信用交易」與 0 張的差別 |
| 9 | 同上：維持率 | 公式、股票＋ETF、最近收盤、涵蓋率 < 99% 顯示「資料不足」、**自算、非官方** |
| 10 | 同上：ETF | 定義（`00` 開頭 4～6 碼、最多一個英文字尾；排除 ETN、受益證券、TDR、權證、特別股）；ETF 存在獨立資料表，每日不增加請求、歷史需補抓；ETF 頁欄位與單位；第二節口徑表的「不計入」清單 |
| 11 | 同上：法人估算 | 第 96 行之後加「今日頁法人買超／賣超表與錢流標示『估算，不含 ETF』；三大法人卡的官方值含 ETF 與權證避險，兩者口徑不同」 |
| 12 | 同上：夜盤 | 第 93 行加「今日頁的夜盤若在日盤收盤之前（歸屬日 ≤ 日盤日期），標示『前一夜盤』並排在前面；之後的標示『最新夜盤』」 |
| 13 | 同上：資料完整性 | 新增 4 個資料集；`check` 開頭兩行與建議指令；網站橫幅的建議指令 |

### `twstock/__main__.py`（附錄 C 的 diff 已包含）

| # | 位置 | 修改 |
|---|---|---|
| 1 | docstring `check` 行 | 「…（唯讀、不連外）：開頭列最後一次收集與排程狀態，有異常時印建議指令並回傳 1」 |
| 2 | docstring `history --start 2026-01-01` 行 | 「補抓歷史（行情、本益比、法人、ETF、融資融券；只補缺的，可中斷重跑）」 |
| 3 | docstring | 新增 `history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）` |
| 4 | `cmd_check` 開頭 | `if args.days < 1: print("❌ --days 至少 1"); return 1`（在匯入 `health` 與連資料庫之前） |
| 5 | `history --only` choices | 加 `"etf", "margin"`；help 加「etf = ETF 行情，margin = 融資融券）；預設 prices pe insti etf margin」 |
| 6 | `check --days` help | 「預設 20，至少 1」 |

---

## 八、給 PG、QA 的提醒

### PG

- **第 0 步只確認備份**，本輪不寫 `backup` 指令、不執行 BACKUP、不碰 `TwStock_before_round3.bak`、不改 Docker 設定、不執行還原。
- 套用附錄 C：每個 `diff` 區塊存成檔案，在專案根目錄執行 `patch -p1 < 檔案`。`install_schedule.bat` 例外，見 S11，要保留 CRLF。
  - **`site/app.css` 的 diff 只加兩行**，原有的「手機佔滿一列」註解留在原位。
- `tests/test_iter03.py` 的修改見附錄 C：`World` 的假資料加 ETF、其他證券與兩個融資融券端點，橫幅兩處預期字串也要改。不改的話 `test_iter03` 會因為新的 `SPECS` 判異常。
- 補抓前後不要同時執行其他 `history` 或 `collect`；步驟 5～8 期間不可 `collect`（E1-8）。
- 伺服器用 8001，結束時關閉；不要動 `.env`、不要 commit、不要安裝排程。
- `04-dev.md` 要記錄：
  - 備份確認結果。
  - 兩次比對的輸出。
  - 補抓的請求數、耗時、被限流次數。
  - 00406A 最早一筆的日期。
  - 11/03 兩市場 ETF 檔數。
  - 附錄 B 各 SQL 的實際結果，含維持率涵蓋率。

### QA

- 附錄 B 的 SQL 都是唯讀 SELECT。
- 維持率以 SQL 3 獨立重算，與頁面一致到 0.1。SQL 的最近收盤沒有 60 天上限，與匯出可能差在長期停牌的 ETF，實務上不影響小數 1 位。
- 2025-10-30 的 2330、5904：用 `logs/iter04_raw_MI_MARGN_20251030.json`，以及 `iter04_raw_margin_balance_20251030.json`（5904 是上櫃），與 `margin_trades` 該日比對。
- 測試不可實際跳通知（T14 mock `subprocess.run`）、不可安裝排程（T24 只執行 `--print`，`HOME` 指向暫存目錄）、不可執行還原。
- Windows 批次檔只做靜態檢查，`05-qa.md` 註明未在 Windows 實測。

---

## 九、對 PM 範圍的調整建議

1. **補抓時間改為約 40 分鐘**（原 30～35）；被限流重跑時最壞約 1.5 小時。請求數 976 不變。
2. **工作量**：程式約 700 行＋測試約 580 行，略高於 850 行的估計。原型與測試已完成，建議**不延後任何項目**。
3. **E1-5 預期值**改用確切值：上市 ETF 融資 3,122,700（+36,315）、融券 128,330（+56,155）；差額是 TDR 912000（14,519 張、+33）與 1 張融券。
4. **B2-5**：2236 使用率 85.46%（截斷，與櫃買官方一致），2376 券資比 33.67%。
5. **B2-11 #5**：「上櫃字串化 `summary`」實測是原生陣列，兩種都支援並測試。
6. **E1-8 基線時點**提前到任何程式修改之前（用舊程式匯出），之後比對兩次（`setup-db` 後、補抓後）。
7. **`history` 預設資料集**加入 `etf`、`margin`，S10 建議的 `history` 指令才能補齊所有每日資料集。
8. **ETF 頁的「--」**同時代表「不在信用交易清單」與「該 ETF 尚無融資融券資料」，本輪不區分。
9. 5236、8908 在補抓區間早期轉市場，舊日期的分市場融資融券合計與維持率涵蓋率略有偏差，只影響歷史、不影響畫面。

---

## 附錄 A：資料來源驗證紀錄（2026-11-03，`fetch.request(isolated=True)`，不重試）

| 端點 | 日期 | 次數 | 結果 |
|---|---|---|---|
| 證交所 `MI_MARGN?selectType=ALL` | 20261103、20251030 | 各 1（共 2） | `stat=OK`；統計 3 列；明細 1,306／1,231 列；欄位與 `groups` 相同 |
| 櫃買 `margin/balance` | 2026/11/03、2025/10/30 | 各 1（共 2） | 919／829 列；`summary` 原生陣列 2 列 |
| 證交所 `MI_INDEX?type=ALLBUT0999` | 20261103、20251030 | 各 1（共 2） | ETF 列與股票同欄位；符合 `is_etf_code` 的列：245／204 |
| 櫃買 `dailyQuotes` | 2026/11/03、2025/10/30 | 各 1（共 2） | 符合的列：118／105；2025-10-30 的 ETF 列欄位相同 |

- 每個端點都已達 2 次上限，SA 不再請求。
- 原始回應保存在 SA 的暫存目錄，已隨原型刪除。正式比對用 PG 補抓時保存的 `logs/iter04_raw_*.json`。

## 附錄 B：預期值與 QA 用 SQL（全部唯讀）

### 1. 補抓完整性（B2-2、E1-3）

預期 `days = 244`（若補抓到 11/03 之後，就是到最新交易日的天數）、`bad_days = 0`。

```sql
DECLARE @s DATE = '2025-10-30', @e DATE = '2026-11-03';
WITH d AS (SELECT DISTINCT trade_date FROM daily_prices WHERE trade_date BETWEEN @s AND @e),
c AS (
  SELECT d.trade_date,
    (SELECT COUNT(*) FROM margin_trades x JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date = d.trade_date AND s.market_type = 'TWSE') AS mg_tw,
    (SELECT COUNT(*) FROM margin_trades x JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date = d.trade_date AND s.market_type = 'TPEx') AS mg_tp,
    (SELECT COUNT(*) FROM etf_daily x JOIN etfs z ON z.etf_id = x.etf_id WHERE x.trade_date = d.trade_date AND z.market_type = 'TWSE') AS etf_tw,
    (SELECT COUNT(*) FROM etf_daily x JOIN etfs z ON z.etf_id = x.etf_id WHERE x.trade_date = d.trade_date AND z.market_type = 'TPEx') AS etf_tp,
    (SELECT COUNT(*) FROM margin_market m WHERE m.trade_date = d.trade_date) AS mkt
  FROM d)
SELECT COUNT(*) AS days,
       SUM(CASE WHEN mg_tw < 800 OR mg_tp < 550 OR etf_tw < 150 OR etf_tp < 80 OR mkt <> 2 THEN 1 ELSE 0 END) AS bad_days,
       MIN(mg_tw) AS min_mg_tw, MIN(mg_tp) AS min_mg_tp, MIN(etf_tw) AS min_etf_tw, MIN(etf_tp) AS min_etf_tp
FROM c;
```

- `daily_prices` 的日期就是已收的交易日（股票行情一年已齊）。
- 筆數門檻與 `SPECS` 下限相同：800、550、150、80；大盤表每天必須 2 列。
- 重跑 `python3 logs/iter04_history.py` 應印「待抓 0 天」與「外部請求 0 次」。

### 2. 11/03 股票、ETF、官方合計（B2-3、B2-4、E1-5）

```sql
DECLARE @d DATE = '2026-11-03';
SELECT '股票' AS kind, s.market_type, COUNT(*) AS n, SUM(t.margin_balance) AS mb, SUM(t.margin_balance - t.margin_prev) AS m1,
       SUM(t.short_balance) AS sb, SUM(t.short_balance - t.short_prev) AS s1,
       CAST(SUM(t.short_balance) * 100.0 / NULLIF(SUM(t.margin_balance), 0) AS DECIMAL(6,2)) AS sr
FROM margin_trades t JOIN stocks s ON s.stock_id = t.stock_id WHERE t.trade_date = @d GROUP BY s.market_type
UNION ALL
SELECT 'ETF', e.market_type, COUNT(*), SUM(t.margin_balance), SUM(t.margin_balance - t.margin_prev),
       SUM(t.short_balance), SUM(t.short_balance - t.short_prev), NULL
FROM etf_margin t JOIN etfs e ON e.etf_id = t.etf_id WHERE t.trade_date = @d GROUP BY e.market_type
UNION ALL
SELECT '官方', market, NULL, margin_balance, margin_balance - margin_prev, short_balance, short_balance - short_prev, NULL
FROM margin_market WHERE trade_date = @d
ORDER BY 2, 1;
```

| kind | 市場 | n | mb | m1 | sb | s1 | sr |
|---|---|---|---|---|---|---|---|
| 股票 | TPEx | 802 | 2,159,879 | −40,082 | 37,994 | +1,780 | 1.76 |
| ETF | TPEx | 117 | 109,433 | +491 | 377 | −113 | |
| 官方 | TPEx | | 2,269,312 | −39,591 | 38,371 | +1,667 | |
| 股票 | TWSE | 1,062 | 6,345,620 | −124,599 | 129,630 | +6,876 | 2.04 |
| ETF | TWSE | 240 | 3,122,700 | +36,315 | 128,330 | +56,155 | |
| 官方 | TWSE | | 9,482,839 | −88,251 | 257,961 | +63,031 | |

- 官方融資金額：上市 599,774,466 仟元（前日 622,699,365），即 **5,997.7 億（−229.2）**；上櫃 196,562,898（前日 204,410,217），即 **1,965.6 億（−78.5）**。
- 個股（B2-5）：

  ```sql
  SELECT s.stock_code, t.* FROM margin_trades t JOIN stocks s ON s.stock_id = t.stock_id
  WHERE t.trade_date = '2026-11-03' AND s.stock_code IN ('2303','2409','2236','2376','3105','2414','6467','3485')
  ```

  | 代號 | 預期 |
  |---|---|
  | 2303 | 融資 146,467，增減 −10,597 |
  | 2409 | 融資增減 −3,524 |
  | 2236 | 13,571 ÷ 15,879 → 85.46%，註記 `@` |
  | 2376 | 2,281 ÷ 6,774 → 33.67% |
  | 3105 | 42,794 ÷ 105,985 → 40.37% |
  | 2414 | 註記 `X` |
  | 6467、3485 | **沒有列** |

  另外 `SELECT COUNT(*) FROM margin_trades t JOIN stocks s ON s.stock_id = t.stock_id WHERE s.stock_code = '00406A'` 必須是 0。

### 3. 大盤融資維持率（B2-6）

```sql
DECLARE @d DATE = '2026-11-03', @m NVARCHAR(10) = 'TWSE';
WITH x AS (
  SELECT t.margin_balance AS n,
         (SELECT TOP 1 p.close_price FROM daily_prices p
          WHERE p.stock_id = t.stock_id AND p.trade_date <= @d AND p.close_price IS NOT NULL ORDER BY p.trade_date DESC) AS px
  FROM margin_trades t JOIN stocks s ON s.stock_id = t.stock_id
  WHERE t.trade_date = @d AND s.market_type = @m
  UNION ALL
  SELECT t.margin_balance,
         (SELECT TOP 1 p.close_price FROM etf_daily p
          WHERE p.etf_id = t.etf_id AND p.trade_date <= @d AND p.close_price IS NOT NULL ORDER BY p.trade_date DESC)
  FROM etf_margin t JOIN etfs e ON e.etf_id = t.etf_id
  WHERE t.trade_date = @d AND e.market_type = @m)
SELECT CAST(SUM(CASE WHEN x.px IS NOT NULL THEN x.n * x.px END) / MAX(mm.amount_balance) * 100 AS DECIMAL(8,2)) AS ratio,
       CAST(SUM(CASE WHEN x.px IS NOT NULL THEN x.n END) * 100.0 / MAX(mm.margin_balance) AS DECIMAL(6,2)) AS coverage
FROM x CROSS JOIN (SELECT amount_balance, margin_balance FROM margin_market WHERE trade_date = @d AND market = @m) AS mm;
```

把 `@d`、`@m` 換成 2026-11-03、2026-11-02 與 TWSE、TPEx，共執行 4 次。

| 日期 | 市場 | 預期維持率 | PM 下限 | 涵蓋率 |
|---|---|---|---|---|
| 11/03 | 上市 | **約 162.66%** | > 153.9 | 約 99.85%（未涵蓋：TDR 912000 的 14,519 張） |
| 11/03 | 上櫃 | **約 156.8%** | > 155.9 | 100% |
| 11/02 | 上市 | **約 171.67%** | > 163.0 | ≥ 99% |
| 11/02 | 上櫃 | **約 167.24%** | > 166.3 | ≥ 99% |

- 原型以 11/03 回應與資料庫唯讀計算，11/02 的 ETF 收盤用 11/03 的「收盤 − 漲跌」推得。
- 補抓後以真實 11/02 ETF 收盤計算，差異應 < 0.1。
- 頁面與 SQL 一致到 0.1 個百分點；`04-dev.md` 記錄 4 個涵蓋率。
- **mock**：T06、T08（涵蓋率 98.9%、98.89% → `null` →「資料不足」）。

### 4. ETF（E1-1、E1-4）

```sql
SELECT COUNT(*) AS stocks_00 FROM stocks WHERE stock_code LIKE '00%';            -- 0
SELECT e.market_type, COUNT(*) FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
WHERE x.trade_date = '2026-11-03' GROUP BY e.market_type;                          -- TWSE 245、TPEx 118
SELECT e.etf_code, e.etf_name, e.market_type, x.close_price, x.change, x.volume, x.trade_value, x.trade_count
FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
WHERE x.trade_date = '2026-11-03' AND e.etf_code IN ('0050','00878','00406A','00679B');
SELECT MIN(x.trade_date) FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id WHERE e.etf_code = '00406A';  -- 第一個交易日
```

| 代號 | 市場 | 收盤 | 漲跌 | 成交量（股） | 成交額（元） | 融資餘額（增減） | 融券餘額（增減） |
|---|---|---|---|---|---|---|---|
| 0050 | TWSE | 100.60 | −3.50 | 302,407,473 | 30,759,303,345 | 28,986（+1,555） | 227（−1） |
| 00878 | TWSE | 33.87 | −0.93 | 192,034,182 | 6,572,661,708 | 5,097（+934） | 561（−8） |
| 00406A | TWSE | 7.98 | 0.00（官方 `X`） | 1,608,938,491 | 13,060,137,327 | 247,190（+13,266） | 65,270（+65,270） |
| 00679B | TPEx | 26.54 | +0.14 | 37,322,231 | 990,372,248 | 4,860（+754） | 24（−1） |

ETF 頁對應顯示：

| 代號 | 收盤 | 漲跌 | 成交量 | 成交額 |
|---|---|---|---|---|
| 0050 | 100.6 | −3.36% | 302,407 張 | 307.59 億 |
| 00406A | 7.98 | 0.00% | 1,608,938 張 | 130.60 億 |
| 00679B | 26.54 | +0.53% | 37,322 張 | 9.90 億 |

數值需與 `logs/iter04_raw_MI_INDEX_20261103.json`、`iter04_raw_dailyQuotes_20261103.json` 一致。

### 5. 既有表筆數不變（B2-1、B2-13）

實作步驟 1 與步驟 8 各執行一次，結果必須相同：

```sql
SELECT 'stocks', COUNT(*) FROM stocks UNION ALL SELECT 'daily_prices', COUNT(*) FROM daily_prices
UNION ALL SELECT 'stock_fundamentals', COUNT(*) FROM stock_fundamentals
UNION ALL SELECT 'institutional_trades', COUNT(*) FROM institutional_trades
UNION ALL SELECT 'market_index', COUNT(*) FROM market_index UNION ALL SELECT 'insti_amount', COUNT(*) FROM insti_amount;
```

## 附錄 C：原型對現有程式的完整 diff（已通過 `test_iter01`～`04`）

- 每個區塊都是 `diff -u`，路徑為 `a/…`、`b/…`。存成檔案後，在專案根目錄執行 `patch -p1 < 檔案` 即可套用；也可以照著手改。
- `scripts/windows/install_schedule.bat` 是 CRLF，不放進 patch，照 S11 的 4 處手改並保留 CRLF。原型去掉 CR 後的差異如下，只供核對：

```diff
--- a/scripts/windows/install_schedule.bat
+++ b/scripts/windows/install_schedule.bat
@@ -1,6 +1,6 @@
 @echo off
 chcp 65001 >nul
-rem 安裝工作排程器：週一到週五 17:30、19:30、21:45 執行 collect.bat（解除安裝：加上 /uninstall）
+rem 安裝工作排程器：週一到週五 17:30、19:30、21:45、22:30 執行 collect.bat（解除安裝：加上 /uninstall）
 rem 其他參數：印用法後以非 0 結束，不安裝也不移除
 if not "%~2"=="" goto :usage
 if "%~1"=="" goto :start
@@ -15,6 +15,7 @@
 schtasks /Delete /TN %TASK%1730 /F >nul 2>&1
 schtasks /Delete /TN %TASK%1930 /F >nul 2>&1
 schtasks /Delete /TN %TASK%2145 /F >nul 2>&1
+schtasks /Delete /TN %TASK%2230 /F >nul 2>&1
 if /i "%~1"=="/uninstall" (
   echo ✅ 已移除排程
   goto :eof
@@ -22,7 +23,8 @@
 schtasks /Create /TN %TASK%1730 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 17:30 /F
 schtasks /Create /TN %TASK%1930 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 19:30 /F
 schtasks /Create /TN %TASK%2145 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 21:45 /F
-echo ✅ 已安裝排程：週一至週五 17:30、19:30、21:45，紀錄寫入 logs\collect.log
+schtasks /Create /TN %TASK%2230 /TR "\"%~dp0collect.bat\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 22:30 /F
+echo ✅ 已安裝排程：週一至週五 17:30、19:30、21:45、22:30，紀錄寫入 logs\collect.log
 echo    錯過排程要補跑：請在工作排程器勾選各工作的「錯過排程時儘快執行」
 echo    立即測試一次：schtasks /Run /TN %TASK%1730
 pause
```

### `twstock/fetch.py`

```diff
--- a/twstock/fetch.py
+++ b/twstock/fetch.py
@@ -5,6 +5,7 @@
 HTML 錯誤頁或 403/429，而不是 JSON。這裡把它和「休市沒資料」明確區分：
 封鎖 → 退避重試，仍失敗就丟 FetchError，呼叫端不可寫入半套資料。
 """
+import re
 import ssl
 import time
 from decimal import InvalidOperation
@@ -132,3 +133,15 @@
     """
     code = code.strip()
     return code.isdigit() and 4 <= len(code) <= 5 and not code.startswith(("00", "06"))
+
+
+ETF_CODE = re.compile(r"00\d{2,4}[A-Z]?")
+
+
+def is_etf_code(code: str) -> bool:
+    """
+    ETF：00 開頭、4～6 碼，數字後最多一個英文字尾（0050、00878、006201、00406A、00679B、00631L、00632R、00635U）。
+    ETN（02 開頭）、受益證券（01 開頭）、TDR（91 開頭）、特別股（4 碼＋英文）、權證（7 開頭 6 碼）都不是。
+    """
+    code = code.strip()
+    return len(code) <= 6 and ETF_CODE.fullmatch(code) is not None
```

### `twstock/db.py`

```diff
--- a/twstock/db.py
+++ b/twstock/db.py
@@ -272,6 +272,102 @@
         fetched_at   DATETIME2(0)  NOT NULL      -- 台灣時間
     )
     """,
+    # ETF（第 4 輪）：與 stocks 分開，所有個股統計都不會讀到
+    """
+    IF OBJECT_ID('etfs') IS NULL
+    CREATE TABLE etfs (
+        etf_id      INT IDENTITY(1,1) PRIMARY KEY,
+        etf_code    NVARCHAR(10)  NOT NULL,
+        etf_name    NVARCHAR(50)  NOT NULL,
+        market_type NVARCHAR(10)  NOT NULL CHECK (market_type IN ('TWSE','TPEx')),
+        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
+        updated_at  DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_code UNIQUE (etf_code)
+    )
+    """,
+    """
+    IF OBJECT_ID('etf_daily') IS NULL
+    CREATE TABLE etf_daily (
+        id          BIGINT IDENTITY(1,1) PRIMARY KEY,
+        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
+        trade_date  DATE           NOT NULL,
+        open_price  DECIMAL(10,2)  NULL,
+        high_price  DECIMAL(10,2)  NULL,
+        low_price   DECIMAL(10,2)  NULL,
+        close_price DECIMAL(10,2)  NULL,
+        volume      BIGINT         NULL,     -- 股
+        trade_value BIGINT         NULL,     -- 元
+        trade_count INT            NULL,
+        change      DECIMAL(10,2)  NULL,
+        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_daily UNIQUE (etf_id, trade_date)
+    )
+    """,
+    # 融資融券（第 4 輪；張）：股票 margin_trades、ETF etf_margin 欄位相同；官方合計（含 ETF）margin_market
+    """
+    IF OBJECT_ID('margin_trades') IS NULL
+    CREATE TABLE margin_trades (
+        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
+        stock_id       INT           NOT NULL REFERENCES stocks(stock_id),
+        trade_date     DATE          NOT NULL,
+        margin_buy     INT           NULL,    -- 融資買進
+        margin_sell    INT           NULL,    -- 融資賣出
+        margin_redeem  INT           NULL,    -- 現金償還
+        margin_prev    INT           NOT NULL,-- 融資前日餘額
+        margin_balance INT           NOT NULL,-- 融資今日餘額
+        margin_limit   INT           NULL,    -- 融資限額（上市：次一營業日限額）
+        short_sell     INT           NULL,    -- 融券賣出
+        short_buy      INT           NULL,    -- 融券買進（回補）
+        short_redeem   INT           NULL,    -- 現券償還
+        short_prev     INT           NOT NULL,
+        short_balance  INT           NOT NULL,
+        short_limit    INT           NULL,
+        offset_lots    INT           NULL,    -- 資券互抵（offset 是保留字）
+        note           NVARCHAR(20)  NULL,    -- 上市註記／上櫃備註原文
+        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_margin_trades UNIQUE (stock_id, trade_date)
+    )
+    """,
+    """
+    IF OBJECT_ID('etf_margin') IS NULL
+    CREATE TABLE etf_margin (
+        id             BIGINT IDENTITY(1,1) PRIMARY KEY,
+        etf_id         INT           NOT NULL REFERENCES etfs(etf_id),
+        trade_date     DATE          NOT NULL,
+        margin_buy     INT           NULL,
+        margin_sell    INT           NULL,
+        margin_redeem  INT           NULL,
+        margin_prev    INT           NOT NULL,
+        margin_balance INT           NOT NULL,
+        margin_limit   INT           NULL,
+        short_sell     INT           NULL,
+        short_buy      INT           NULL,
+        short_redeem   INT           NULL,
+        short_prev     INT           NOT NULL,
+        short_balance  INT           NOT NULL,
+        short_limit    INT           NULL,
+        offset_lots    INT           NULL,
+        note           NVARCHAR(20)  NULL,
+        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_margin UNIQUE (etf_id, trade_date)
+    )
+    """,
+    """
+    IF OBJECT_ID('margin_market') IS NULL
+    CREATE TABLE margin_market (
+        id             INT IDENTITY(1,1) PRIMARY KEY,
+        trade_date     DATE          NOT NULL,
+        market         NVARCHAR(10)  NOT NULL CHECK (market IN ('TWSE','TPEx')),
+        margin_prev    BIGINT        NOT NULL,   -- 官方融資前日餘額（張，含 ETF 與其他證券）
+        margin_balance BIGINT        NOT NULL,
+        short_prev     BIGINT        NOT NULL,   -- 官方融券（張）
+        short_balance  BIGINT        NOT NULL,
+        amount_prev    BIGINT        NOT NULL,   -- 官方融資金額（仟元）
+        amount_balance BIGINT        NOT NULL,
+        created_at     DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_margin_market UNIQUE (trade_date, market)
+    )
+    """,
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -283,6 +379,10 @@
     "CREATE INDEX IX_institutional_date ON institutional_trades(trade_date)",
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_industry_chains_code') "
     "CREATE INDEX IX_industry_chains_code ON industry_chains(stock_code)",
+    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_margin_trades_date') "
+    "CREATE INDEX IX_margin_trades_date ON margin_trades(trade_date)",
+    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_daily_date') "
+    "CREATE INDEX IX_etf_daily_date ON etf_daily(trade_date)",
 ]
 
 
@@ -302,4 +402,5 @@
     conn.close()
     print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
-          "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays")
+          "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
+          "etfs、etf_daily、margin_trades、etf_margin、margin_market")
```

### `twstock/collectors/daily.py`

```diff
--- a/twstock/collectors/daily.py
+++ b/twstock/collectors/daily.py
@@ -1,24 +1,29 @@
 """
-每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超。
+每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券。
 
 寫入採批次：整批資料序列化成一個 JSON 參數，由 OPENJSON 展開後 MERGE；
 每張表一次資料庫往返，取代逐筆查詢/更新的上萬次往返。
 """
+import json
 from datetime import date
 
 from .. import db
-from ..fetch import FetchError, SchemaError, clean_number, is_valid_stock_code, request
+from ..fetch import FetchError, SchemaError, clean_number, is_etf_code, is_valid_stock_code, request
 
 TWSE = "https://www.twse.com.tw/rwd/zh"
 TPEX = "https://www.tpex.org.tw/www/zh-tw"
 
 # history --only 的資料集名稱；INDEX = 加權指數（抓行情時會一併寫入），TPEX_INDEX = 櫃買指數（月查詢）
 PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
-ALL_DATASETS = (PRICES, PE, INSTI)
-# 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵；順序：行情先於本益比、法人
+ETF, MARGIN = "etf", "margin"
+ALL_DATASETS = (PRICES, PE, INSTI, ETF, MARGIN)
+# 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵
 DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
-                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",)}
-DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "pe.TWSE", "pe.TPEx", "insti.TWSE", "insti.TPEx", "amount")
+                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",),
+                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx")}
+# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券（融資融券的 ETF 列只寫入 etfs 已有的 ETF）
+DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "etf.TWSE", "etf.TPEx", "pe.TWSE", "pe.TPEx",
+            "insti.TWSE", "insti.TPEx", "amount", "margin.TWSE", "margin.TPEx")
 PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)
 
 
@@ -47,39 +52,41 @@
     return None
 
 
+def _twse_quote(row: list, idx: dict) -> dict:
+    """MI_INDEX 行情表的一列（股票與 ETF 共用）。"""
+    # 漲跌價差是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段，如 <p style= color:green>-</p>）
+    change = clean_number(row[idx["漲跌價差"]])
+    if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
+        change = -change
+    return {
+        "stock_code": str(row[idx["證券代號"]]).strip(), "stock_name": str(row[idx["證券名稱"]]).strip(),
+        "open_price":  clean_number(row[idx["開盤價"]]),
+        "high_price":  clean_number(row[idx["最高價"]]),
+        "low_price":   clean_number(row[idx["最低價"]]),
+        "close_price": clean_number(row[idx["收盤價"]]),
+        "volume":      clean_number(row[idx["成交股數"]], int),
+        "trade_value": clean_number(row[idx["成交金額"]], int),
+        "trade_count": clean_number(row[idx["成交筆數"]], int),
+        "change":      change,
+    }
+
+
 def fetch_twse_daily(d: date):
-    """上市每日收盤行情與加權指數；休市回傳 ([], None)。"""
+    """上市每日收盤行情、加權指數、ETF 原始列 → (股票列, 指數, (欄位索引, ETF 原始列))；休市回傳 ([], None, ({}, []))。"""
     data = request("GET", f"{TWSE}/afterTrading/MI_INDEX",
                    params={"response": "json", "date": f"{d:%Y%m%d}", "type": "ALLBUT0999"})
     if data.get("stat") != "OK":
-        return [], None
+        return [], None, ({}, [])
     taiex = parse_taiex(data, d)
     for table in data.get("tables", []):
         fields = table.get("fields", [])
         if "證券代號" not in fields:
             continue
         idx = {f: i for i, f in enumerate(fields)}
-        results = []
-        for row in table.get("data", []):
-            code = str(row[idx["證券代號"]]).strip()
-            if not is_valid_stock_code(code):
-                continue
-            # 漲跌價差是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段，如 <p style= color:green>-</p>）
-            change = clean_number(row[idx["漲跌價差"]])
-            if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
-                change = -change
-            results.append({
-                "stock_code": code, "stock_name": str(row[idx["證券名稱"]]).strip(),
-                "open_price":  clean_number(row[idx["開盤價"]]),
-                "high_price":  clean_number(row[idx["最高價"]]),
-                "low_price":   clean_number(row[idx["最低價"]]),
-                "close_price": clean_number(row[idx["收盤價"]]),
-                "volume":      clean_number(row[idx["成交股數"]], int),
-                "trade_value": clean_number(row[idx["成交金額"]], int),
-                "trade_count": clean_number(row[idx["成交筆數"]], int),
-                "change":      change,
-            })
-        return results, taiex
+        code = lambda row: str(row[idx["證券代號"]]).strip()
+        rows = table.get("data", [])
+        results = [_twse_quote(r, idx) for r in rows if is_valid_stock_code(code(r))]
+        return results, taiex, (idx, [r for r in rows if is_etf_code(code(r))])
     raise SchemaError("MI_INDEX 找不到含「證券代號」的個股表")
 
 
@@ -126,28 +133,45 @@
     return [t for t in data.get("tables", []) if t.get("fields") and t.get("data")]
 
 
-def fetch_tpex_daily(d: date) -> list:
+def _tpex_quote(row: list, idx: dict) -> dict:
+    """dailyQuotes 行情表的一列（股票與 ETF 共用）。"""
+    return {
+        "stock_code": str(row[idx["代號"]]).strip(), "stock_name": str(row[idx["名稱"]]).strip(),
+        "close_price": clean_number(row[idx["收盤"]]),
+        "open_price":  clean_number(row[idx["開盤"]]),
+        "high_price":  clean_number(row[idx["最高"]]),
+        "low_price":   clean_number(row[idx["最低"]]),
+        "change":      clean_number(row[idx["漲跌"]]),          # 上櫃的漲跌本身帶正負號
+        "volume":      clean_number(row[idx["成交股數"]], int),
+        "trade_value": clean_number(row[idx["成交金額(元)"]], int),
+        "trade_count": clean_number(row[idx["成交筆數"]], int),
+    }
+
+
+def fetch_tpex_daily(d: date) -> tuple:
+    """上櫃每日行情 → (股票列, None, (欄位索引, ETF 原始列))；與 fetch_twse_daily 同形。"""
     tables = _tpex_tables("afterTrading/dailyQuotes", d)
     for table in tables:
         idx = {f: i for i, f in enumerate(table["fields"])}
         if "代號" not in idx:
             continue
-        return [{
-            "stock_code": str(row[idx["代號"]]).strip(), "stock_name": str(row[idx["名稱"]]).strip(),
-            "close_price": clean_number(row[idx["收盤"]]),
-            "open_price":  clean_number(row[idx["開盤"]]),
-            "high_price":  clean_number(row[idx["最高"]]),
-            "low_price":   clean_number(row[idx["最低"]]),
-            "change":      clean_number(row[idx["漲跌"]]),          # 上櫃的漲跌本身帶正負號
-            "volume":      clean_number(row[idx["成交股數"]], int),
-            "trade_value": clean_number(row[idx["成交金額(元)"]], int),
-            "trade_count": clean_number(row[idx["成交筆數"]], int),
-        } for row in table["data"] if is_valid_stock_code(str(row[idx["代號"]]))]
+        code = lambda row: str(row[idx["代號"]]).strip()
+        return ([_tpex_quote(r, idx) for r in table["data"] if is_valid_stock_code(code(r))], None,
+                (idx, [r for r in table["data"] if is_etf_code(code(r))]))
     if tables:
         raise SchemaError("dailyQuotes 找不到含「代號」的行情表")
-    return []
+    return [], None, ({}, [])
 
 
+def parse_etf_quotes(raw: tuple, market: str) -> list:
+    """(欄位索引, ETF 原始列) → 寫入用 dict（鍵與股票行情相同）。股票列存在卻沒有任何 ETF 列 → SchemaError。"""
+    idx, rows = raw
+    if not rows:
+        raise SchemaError(f"{market} 行情回應沒有任何 ETF 列")
+    quote = _twse_quote if market == "TWSE" else _tpex_quote
+    return [quote(r, idx) for r in rows]
+
+
 def parse_tpex_index(tables: list) -> list:
     """櫃買指數月查詢（日期為西元 2026/10/30，漲跌本身帶正負號）→ 寫入用 dict。"""
     need = ("日期", "開市", "最高", "最低", "收市", "漲/跌")
@@ -215,8 +239,123 @@
         }
         for row in tables[0].get("data", []) if is_valid_stock_code(row[0])
     }
+
+
+# ─── 融資融券（上市 MI_MARGN、上櫃 margin/balance；張；股票、ETF、其他證券同一個回應）──
+TWSE_MARGIN_GROUPS = [("股票", 2), ("融資", 6), ("融券", 6)]
+# 上市明細表欄名重複，依位置取值；位置 → 欄名（用來驗證沒有改版）
+TWSE_MARGIN_POS = {0: "代號", 2: "買進", 3: "賣出", 4: "現金償還", 5: "前日餘額", 6: "今日餘額", 7: "次一營業日限額",
+                   8: "買進", 9: "賣出", 10: "現券償還", 11: "前日餘額", 12: "今日餘額", 13: "次一營業日限額",
+                   14: "資券互抵", 15: "註記"}
+MARGIN_COLS = ("margin_buy", "margin_sell", "margin_redeem", "margin_prev", "margin_balance", "margin_limit",
+               "short_sell", "short_buy", "short_redeem", "short_prev", "short_balance", "short_limit", "offset_lots")
+TPEX_MARGIN_COLS = dict(zip(MARGIN_COLS, ("資買", "資賣", "現償", "前資餘額(張)", "資餘額", "資限額",
+                                          "券賣", "券買", "券償", "前券餘額(張)", "券餘額", "券限額", "資券相抵(張)")))
+TWSE_MARGIN_IDX = dict(zip(MARGIN_COLS, (2, 3, 4, 5, 6, 7, 9, 8, 10, 11, 12, 13, 14)))   # 融券：9 賣出、8 買進
+
+
+def _margin_row(code: str, get, note) -> dict:
+    """get(欄) → 原始字串；前日餘額或今日餘額無法解析的列回傳 None（略過）。"""
+    row = {"stock_code": code, **{c: clean_number(get(c), int) for c in MARGIN_COLS},
+           "note": str(note or "").strip()[:20] or None}
+    if None in (row["margin_prev"], row["margin_balance"], row["short_prev"], row["short_balance"]):
+        return None
+    return row
+
+
+def _margin_total(mp, mb, sp, sb, ap, ab) -> dict:
+    vals = [clean_number(v, int) for v in (mp, mb, sp, sb, ap, ab)]
+    if None in vals:
+        raise SchemaError("融資融券官方合計有空值：" + "、".join(map(str, (mp, mb, sp, sb, ap, ab))))
+    return dict(zip(("margin_prev", "margin_balance", "short_prev", "short_balance", "amount_prev", "amount_balance"), vals))
+
+
+def parse_twse_margin(data: dict) -> tuple:
+    """
+    MI_MARGN（selectType=ALL）→ (列, 官方合計)。列含股票、ETF、其他證券，由呼叫端分流；
+    官方合計 = 信用交易統計（含 ETF）：融資、融券（張）、融資金額（仟元）的前日與今日餘額。
+    stat 不是 OK 或明細沒有列 → ([], None)（官方尚無資料）；明細欄位、groups 或統計表不符 → SchemaError。
+    """
+    if data.get("stat") != "OK":
+        return [], None
+    tables = data.get("tables") or []
+    detail = next((t for t in tables if (t.get("fields") or [None])[0] == "代號"), None)
+    if detail is None:
+        if any(t.get("data") for t in tables):
+            raise SchemaError("MI_MARGN 找不到「代號」開頭的明細表")
+        return [], None
+    if not detail.get("data"):
+        return [], None
+    fields = detail["fields"]
+    groups = [(g.get("title"), g.get("span")) for g in detail.get("groups") or []][:3]
+    bad = [f"{i}:{name}" for i, name in TWSE_MARGIN_POS.items() if i >= len(fields) or fields[i] != name]
+    if groups != TWSE_MARGIN_GROUPS or bad:
+        raise SchemaError(f"MI_MARGN 欄位不符：groups {groups}，位置 {'、'.join(bad) or '正常'}")
+    rows = []
+    for r in detail["data"]:
+        if len(r) < 16:
+            continue
+        row = _margin_row(str(r[0]).strip(), lambda c: r[TWSE_MARGIN_IDX[c]], r[15])
+        if row:
+            rows.append(row)
+    total_t = next((t for t in tables if (t.get("fields") or [None])[0] == "項目"), None)
+    if total_t is None or not {"前日餘額", "今日餘額"} <= set(total_t["fields"]):
+        raise SchemaError("MI_MARGN 找不到信用交易統計")
+    i, j = total_t["fields"].index("前日餘額"), total_t["fields"].index("今日餘額")
+    by = {}
+    for r in total_t.get("data") or []:
+        label = str(r[0])
+        key = "amount" if label.startswith("融資金額") else "margin" if label.startswith("融資(") else \
+            "short" if label.startswith("融券(") else None
+        if key and len(r) > max(i, j):
+            by[key] = (r[i], r[j])
+    if set(by) != {"margin", "short", "amount"}:
+        raise SchemaError("MI_MARGN 信用交易統計列不符：" + "、".join(str(r[0]) for r in total_t.get("data") or []))
+    return rows, _margin_total(*by["margin"], *by["short"], *by["amount"])
 
 
+def parse_tpex_margin(data: dict) -> tuple:
+    """
+    櫃買 margin/balance → (列, 官方合計)。欄名不重複，依名稱取值；官方合計在 summary（實測是陣列，
+    舊格式可能是字串化陣列，兩種都接受），與 fields 同欄位對齊：「合計(張)」列、「融資金(仟元)」列。
+    沒有資料列 → ([], None)；欄位或 summary 不符 → SchemaError。
+    """
+    tables = [t for t in data.get("tables") or [] if t.get("data")]
+    if not tables:
+        return [], None
+    t = tables[0]
+    idx = {f: i for i, f in enumerate(t.get("fields") or [])}
+    need = ("代號", "備註", *TPEX_MARGIN_COLS.values())
+    miss = [f for f in need if f not in idx]
+    if miss:
+        raise SchemaError("margin/balance 欄位不符，缺：" + "、".join(miss))
+    rows = []
+    for r in t["data"]:
+        if len(r) < len(idx):
+            continue
+        row = _margin_row(str(r[idx["代號"]]).strip(), lambda c: r[idx[TPEX_MARGIN_COLS[c]]], r[idx["備註"]])
+        if row:
+            rows.append(row)
+    summary = t.get("summary") or []
+    if isinstance(summary, str):
+        summary = json.loads(summary)
+    lots = next((s for s in summary if any("合計" in str(x) for x in s)), None)
+    amount = next((s for s in summary if any("融資金" in str(x) for x in s)), None)
+    if lots is None or amount is None or min(len(lots), len(amount)) < len(idx):
+        raise SchemaError(f"margin/balance summary 不符：{str(summary)[:200]}")
+    mp, mb, sp, sb = (idx[f] for f in ("前資餘額(張)", "資餘額", "前券餘額(張)", "券餘額"))
+    return rows, _margin_total(lots[mp], lots[mb], lots[sp], lots[sb], amount[mp], amount[mb])
+
+
+def fetch_twse_margin(d: date) -> tuple:
+    return parse_twse_margin(request("GET", f"{TWSE}/marginTrading/MI_MARGN",
+                                     params={"response": "json", "date": f"{d:%Y%m%d}", "selectType": "ALL"}))
+
+
+def fetch_tpex_margin(d: date) -> tuple:
+    return parse_tpex_margin(request("POST", f"{TPEX}/margin/balance", data={"date": f"{d:%Y/%m/%d}", "response": "json"}))
+
+
 # ─── 批次寫入 ─────────────────────────────────────────────
 def merge_stocks(cursor, rows: list, trade_date: date):
     """
@@ -308,9 +447,100 @@
         WHEN NOT MATCHED THEN
             INSERT (stock_id, trade_date, foreign_net, trust_net, dealer_net, total_net)
             VALUES (s.stock_id, ?, s.foreign_net, s.trust_net, s.dealer_net, s.total_net);
+    """, db.to_json(rows), trade_date, trade_date)
+
+
+def merge_etfs(cursor, rows: list, market: str, trade_date: date):
+    """ETF 清單（與 stocks 分開）。名稱、市場別只在 trade_date ≥ ETF 日線最新日期時更新（同 merge_stocks）。"""
+    cursor.execute("""
+        DECLARE @latest DATE = (SELECT MAX(trade_date) FROM etf_daily);
+        MERGE etfs AS t
+        USING OPENJSON(?) WITH (stock_code NVARCHAR(10), stock_name NVARCHAR(50)) AS s
+        ON t.etf_code = s.stock_code
+        WHEN MATCHED AND (@latest IS NULL OR ? >= @latest) THEN
+            UPDATE SET etf_name = s.stock_name, market_type = ?, updated_at = GETDATE()
+        WHEN NOT MATCHED THEN
+            INSERT (etf_code, etf_name, market_type) VALUES (s.stock_code, s.stock_name, ?);
+    """, db.to_json([{"stock_code": r["stock_code"], "stock_name": r["stock_name"]} for r in rows]),
+        trade_date, market, market)
+
+
+def merge_etf_daily(cursor, trade_date, rows: list):
+    cursor.execute("""
+        MERGE etf_daily AS t
+        USING (
+            SELECT e.etf_id, j.*
+            FROM OPENJSON(?) WITH (
+                stock_code  NVARCHAR(10),
+                open_price  DECIMAL(10,2), high_price  DECIMAL(10,2),
+                low_price   DECIMAL(10,2), close_price DECIMAL(10,2),
+                volume      BIGINT,        trade_value BIGINT,
+                trade_count INT,           change      DECIMAL(10,2)
+            ) AS j
+            JOIN etfs e ON e.etf_code = j.stock_code
+        ) AS s
+        ON t.etf_id = s.etf_id AND t.trade_date = ?
+        WHEN MATCHED THEN UPDATE SET
+            open_price = s.open_price, high_price = s.high_price,
+            low_price  = s.low_price,  close_price = s.close_price,
+            volume = s.volume, trade_value = s.trade_value,
+            trade_count = s.trade_count, change = s.change
+        WHEN NOT MATCHED THEN
+            INSERT (etf_id, trade_date, open_price, high_price, low_price, close_price,
+                    volume, trade_value, trade_count, change)
+            VALUES (s.etf_id, ?, s.open_price, s.high_price, s.low_price, s.close_price,
+                    s.volume, s.trade_value, s.trade_count, s.change);
+    """, db.to_json(rows), trade_date, trade_date)
+
+
+# 融資融券個股表：股票寫 margin_trades（只寫 stocks 已有的），ETF 寫 etf_margin（只寫 etfs 已有的）
+_MARGIN_TABLE = {"stock": ("margin_trades", "stocks", "stock_id", "stock_code"),
+                 "etf": ("etf_margin", "etfs", "etf_id", "etf_code")}
+
+
+def merge_margin(cursor, trade_date, rows: list, kind: str):
+    table, ref, key, code = _MARGIN_TABLE[kind]
+    cols = ", ".join(MARGIN_COLS)
+    cursor.execute(f"""
+        MERGE {table} AS t
+        USING (
+            SELECT r.{key}, j.*
+            FROM OPENJSON(?) WITH (
+                stock_code NVARCHAR(10),
+                margin_buy INT, margin_sell INT, margin_redeem INT, margin_prev INT, margin_balance INT, margin_limit INT,
+                short_sell INT, short_buy INT, short_redeem INT, short_prev INT, short_balance INT, short_limit INT,
+                offset_lots INT, note NVARCHAR(20)
+            ) AS j
+            JOIN {ref} r ON r.{code} = j.stock_code
+        ) AS s
+        ON t.{key} = s.{key} AND t.trade_date = ?
+        WHEN MATCHED THEN UPDATE SET
+            {", ".join(f"{c} = s.{c}" for c in MARGIN_COLS)}, note = s.note
+        WHEN NOT MATCHED THEN
+            INSERT ({key}, trade_date, {cols}, note)
+            VALUES (s.{key}, ?, {", ".join(f"s.{c}" for c in MARGIN_COLS)}, s.note);
     """, db.to_json(rows), trade_date, trade_date)
 
 
+def merge_margin_market(cursor, trade_date, market: str, total: dict):
+    cursor.execute("""
+        MERGE margin_market AS t
+        USING OPENJSON(?) WITH (
+            trade_date DATE, market NVARCHAR(10),
+            margin_prev BIGINT, margin_balance BIGINT, short_prev BIGINT, short_balance BIGINT,
+            amount_prev BIGINT, amount_balance BIGINT
+        ) AS s
+        ON t.trade_date = s.trade_date AND t.market = s.market
+        WHEN MATCHED THEN UPDATE SET
+            margin_prev = s.margin_prev, margin_balance = s.margin_balance, short_prev = s.short_prev,
+            short_balance = s.short_balance, amount_prev = s.amount_prev, amount_balance = s.amount_balance
+        WHEN NOT MATCHED THEN
+            INSERT (trade_date, market, margin_prev, margin_balance, short_prev, short_balance, amount_prev, amount_balance)
+            VALUES (s.trade_date, s.market, s.margin_prev, s.margin_balance, s.short_prev, s.short_balance,
+                    s.amount_prev, s.amount_balance);
+    """, db.to_json([{"trade_date": str(trade_date), "market": market, **total}]))
+
+
 def merge_market_index(cursor, rows: list):
     cursor.execute("""
         MERGE market_index AS t
@@ -406,21 +636,36 @@
 
 
 # ─── 單日收集 ─────────────────────────────────────────────
+def _quotes(market: str, d: date, cache: dict) -> tuple:
+    """同一市場的行情回應只抓一次：股票行情、加權指數、ETF 共用；失敗也快取，同一次執行不重打。"""
+    if market not in cache:
+        try:
+            cache[market] = fetch_twse_daily(d) if market == "TWSE" else fetch_tpex_daily(d)
+        except (FetchError, *PARSE_ERRORS) as e:
+            cache[market] = e
+    if isinstance(cache[market], Exception):
+        raise cache[market]
+    return cache[market]
+
+
 def _collect_key(key: str, d: date, cache: dict) -> int:
     """抓取並寫入一個資料集，回傳筆數（0 = 官方尚無資料）。"""
     dataset, _, market = key.partition(".")
+    if dataset in (PRICES, INDEX, ETF):
+        rows, taiex, etf_raw = _quotes("TPEx" if market == "TPEx" else "TWSE", d, cache)
+    if dataset == ETF:
+        if not rows:
+            return 0                                # 行情未公布
+        etfs = parse_etf_quotes(etf_raw, market)    # 有股票列卻沒有 ETF 列 → SchemaError，只影響 etf.*
+        _save(lambda cur: (merge_etfs(cur, etfs, market, d), merge_etf_daily(cur, d, etfs)))
+        return len(etfs)
     if key == "prices.TWSE" or key == "index.TAIEX":
-        if "mi" not in cache:                       # 上市行情與加權指數來自同一個 MI_INDEX 回應
-            cache["mi"] = fetch_twse_daily(d)
-        rows, taiex = cache["mi"]
         if taiex:
             _save(merge_market_index, [taiex])
         elif rows:
             print("  ⚠️  MI_INDEX 找不到加權指數表")
         if key == "index.TAIEX":
             return 1 if taiex else 0
-    elif key == "prices.TPEx":
-        rows = fetch_tpex_daily(d)
     if dataset == "prices":
         if rows:
             stocks = [{"stock_code": r["stock_code"], "stock_name": r["stock_name"], "market_type": market} for r in rows]
@@ -436,6 +681,15 @@
         if insti:
             _save(merge_institutional, d, [{"stock_code": c, **r} for c, r in insti.items()])
         return len(insti)
+    if dataset == MARGIN:
+        rows, total = (fetch_twse_margin if market == "TWSE" else fetch_tpex_margin)(d)
+        stocks = [r for r in rows if is_valid_stock_code(r["stock_code"])]
+        etfs = [r for r in rows if is_etf_code(r["stock_code"])]
+        if not stocks:
+            return 0
+        _save(lambda cur: (merge_margin(cur, d, stocks, "stock"), etfs and merge_margin(cur, d, etfs, "etf"),
+                           merge_margin_market(cur, d, market, total)))
+        return len(stocks)
     amount = fetch_twse_insti_amount(d)
     if amount:
         _save(merge_insti_amount, amount)
@@ -452,8 +706,8 @@
     written, errors, cache = {}, {}, {}
     for key in keys:
         dataset, _, market = key.partition(".")
-        if dataset in ("pe", "insti") and written.get(f"prices.{market}") == 0:
-            continue                # 同市場行情還沒有：本益比、法人不可能先有，不發請求
+        if dataset in ("pe", "insti", MARGIN) and written.get(f"prices.{market}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人、融資融券不可能先有，不發請求
         if dataset == "pe" and f"prices.{market}" in errors:
             continue                # 本益比只寫入有行情列的股票
         try:
@@ -470,4 +724,4 @@
     return written, errors
 
 
-__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ALL_DATASETS"]
+__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "ALL_DATASETS"]
```

### `twstock/health.py`

```diff
--- a/twstock/health.py
+++ b/twstock/health.py
@@ -10,6 +10,7 @@
 import sys
 from collections import namedtuple
 from datetime import date, datetime, time, timedelta
+from pathlib import Path
 
 from .config import LOG_DIR
 from .tradingcal import load_closed, trading_days
@@ -32,6 +33,8 @@
     Spec("amount", "上市法人金額", 6, False),
     Spec("index.TAIEX", "加權指數", 1, False), Spec("index.TPEX", "櫃買指數", 1, False),
     Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
+    Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
+    Spec("margin.TWSE", "上市融資融券", 800, False), Spec("margin.TPEx", "上櫃融資融券", 550, False),
 )
 SPEC = {s.key: s for s in SPECS}
 
@@ -40,6 +43,7 @@
     "pe": "SELECT x.trade_date, s.market_type, COUNT(*), COUNT(x.pe_ratio), COUNT(x.pb_ratio), COUNT(x.dividend_yield) "
           "FROM stock_fundamentals x",
     "insti": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM institutional_trades x",
+    "margin": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM margin_trades x",
 }
 
 
@@ -54,6 +58,9 @@
     for d, code, n in cur.execute("SELECT trade_date, index_code, COUNT(*) FROM market_index "
                                   "WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date, index_code", start, end).fetchall():
         snap[f"index.{code}"][d] = Row(n)
+    for d, market, n in cur.execute("SELECT x.trade_date, e.market_type, COUNT(*) FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id "
+                                    "WHERE x.trade_date BETWEEN ? AND ? GROUP BY x.trade_date, e.market_type", start, end).fetchall():
+        snap[f"etf.{market}"][d] = Row(n)
     for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                      # 只看日盤：夜盤的日期是歸屬日，不代表該日資料已齊
                      ("futures", "SELECT trade_date, COUNT(*) FROM futures_daily_prices WHERE commodity_id = 'TX' AND session = 'DAY' "
@@ -124,20 +131,41 @@
     return ABNORMAL if ABNORMAL in states else PENDING if PENDING in states else OK
 
 
-def problem_lines(items) -> list:
-    """把異常與尚未公布的項目彙總成一行一項（同資料集同原因合併）。"""
+def _day_list(days) -> str:
+    return "、".join(map(str, days[:8])) + (f" 等 {len(days)} 天" if len(days) > 8 else "")
+
+
+def all_missing_days(items) -> list:
+    """所有資料集都是「異常且 0 筆」的交易日（整天沒有收集）；休市日本來就不在 items 裡。"""
+    by_day = {}
+    for i in items:
+        by_day.setdefault(i.date, []).append(i)
+    return sorted(d for d, its in by_day.items()
+                  if len(its) == len(SPECS) and all(i.status == ABNORMAL and not i.n for i in its))
+
+
+def problem_lines(items, last_run=None) -> list:
+    """把異常與尚未公布的項目彙總成一行一項（同資料集同原因合併）；整天所有資料集都缺的日子合併成一行。"""
+    whole = all_missing_days(items)
+    lines = []
+    if whole:
+        why = ""
+        if last_run:
+            at = last_run["at"]
+            why = (f"：最後一次收集是 {at:%m/%d %H:%M}，之後沒有執行收集"
+                   if at < datetime.combine(whole[-1], COLLECT_FROM) else f"：最後一次收集 {at:%m/%d %H:%M} 也沒有取得")
+        lines.append(f"❌ {_day_list(whole)} 全部資料集都沒有{why}")
     groups = {}
     for i in items:
-        if i.status != OK:
+        if i.status != OK and i.date not in whole:
             groups.setdefault((i.status, i.key, i.reason[0]), []).append(i)
-    lines = []
     for (status, _, kind), its in sorted(groups.items(), key=lambda g: (g[0][0] != ABNORMAL, list(SPEC).index(g[0][1]))):
         mark, label = ("❌", its[0].label) if status == ABNORMAL else ("⏳", its[0].label)
         days = [i.date for i in its]
         if status == PENDING:
             lines.append(f"{mark} {label}：{days[-1]} 尚未公布")
         elif kind == "none":
-            lines.append(f"{mark} {label}：缺 " + "、".join(map(str, days[:8])) + (f" 等 {len(days)} 天" if len(days) > 8 else ""))
+            lines.append(f"{mark} {label}：缺 " + _day_list(days))
         elif len(days) == 1:
             lines.append(f"{mark} {label}：{days[0]} {its[0].reason[1]}")
         else:
@@ -147,10 +175,15 @@
 
 # ─── 執行紀錄 ─────────────────────────────────────────────
 def load_state(cur) -> dict:
-    """由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，與最後一次有新資料的時間。"""
-    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None}
-    for finished, new_data, detail in cur.execute(
-            "SELECT TOP 200 finished_at, new_data, detail FROM collect_runs ORDER BY run_id DESC").fetchall():
+    """
+    由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，最後一次有新資料的時間，
+    與最後一次收集（last_run：時間、指令、有無新資料）。
+    """
+    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None, "last_run": None}
+    for finished, new_data, detail, *extra in cur.execute(
+            "SELECT TOP 200 finished_at, new_data, detail, command FROM collect_runs ORDER BY run_id DESC").fetchall():
+        if state["last_run"] is None:
+            state["last_run"] = {"at": finished, "command": extra[0] if extra else None, "new_data": bool(new_data)}
         if new_data and state["collected_at"] is None:
             state["collected_at"] = finished
         und = json.loads(detail).get("undated", {})
@@ -203,10 +236,46 @@
 
 
 # ─── check 指令 ───────────────────────────────────────────
-def check_report(days, snap, now, state, closed, adhoc=()) -> tuple:
-    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求。"""
+PLIST = Path("Library/LaunchAgents/com.twstock.collect.plist")      # 相對於使用者家目錄
+RUN_LABEL = {"catch-up": "collect --catch-up", "date": "collect --date"}
+CATCHUP_DAYS, CATCHUP_MAX = 10, 30      # 與 collectors.catchup 的 DEFAULT_DAYS、MAX_DAYS 相同（health 不匯入 collectors）
+
+
+def schedule_status(platform=None, home=None) -> str:
+    """只看排程檔是否存在（唯讀，不呼叫 launchctl／schtasks）。"""
+    if (platform or sys.platform) != "darwin":
+        return "無法判斷，請在工作排程器確認"
+    path = Path(home or Path.home()) / PLIST
+    return f"已安裝（{path}）" if path.exists() else "未安裝（安裝方式見 README，由使用者自行執行）"
+
+
+def last_run_line(run) -> str:
+    if not run:
+        return "尚無執行紀錄"
+    what = RUN_LABEL.get(run["command"], "收集")
+    return f"{run['at']:%Y-%m-%d %H:%M}（{what}，{'有新資料' if run['new_data'] else '沒有新資料'}）"
+
+
+def suggest(items, days, stale_alerts) -> str:
+    """有異常時的建議指令：缺口在 --catch-up 預設範圍內 → collect --catch-up；30 天內 → 加 --days；更早 → history。"""
+    bad = sorted({i.date for i in items if i.status == ABNORMAL})
+    if not bad and not stale_alerts:
+        return ""
+    n = len(days) - days.index(bad[0]) if bad else 1
+    if n <= CATCHUP_DAYS:
+        return "👉 請執行 python3 -m twstock collect --catch-up"
+    if n <= CATCHUP_MAX:
+        return f"👉 請執行 python3 -m twstock collect --catch-up --days {n}"
+    return f"👉 請執行 python3 -m twstock history --start {bad[0]}，再執行 python3 -m twstock collect --catch-up"
+
+
+def check_report(days, snap, now, state, closed, adhoc=(), schedule=None) -> tuple:
+    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）。"""
     items, med = evaluate(days, snap, now), medians(snap)
-    out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）"]
+    out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）",
+           f"🕘 最後一次收集：{last_run_line(state.get('last_run'))}"]
+    if schedule:
+        out.append(f"🗓️  排程：{schedule}")
     if now.weekday() >= 5 or now.date() in closed:
         out.append(f"ℹ️  今天 {now.date()} 休市")
     if adhoc:
@@ -226,7 +295,7 @@
                    f"{last.n if last else 0:>7,}{med[spec.key]:>7,.0f}  {fill:<20}  {mark[worst]}")
     alerts = state.get("alerts_at")
     out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
-    lines = problem_lines(items)
+    lines = problem_lines(items, state.get("last_run"))
     # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
     stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
     if stale:
@@ -234,6 +303,8 @@
     abnormal = sum(ln.startswith("❌") for ln in lines)
     out += ["", *lines] if lines else []
     out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
+    if abnormal:
+        out.append(suggest(items, days, bool(stale)))
     return "\n".join(out), (1 if abnormal else 0)
 
 
@@ -251,7 +322,7 @@
                                            "ORDER BY holiday_date", start, days[-1]).fetchall()]
     finally:
         conn.close()
-    text, rc = check_report(days, snap, now, state, closed, adhoc)
+    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status())
     print(text)
     return rc
 
```

### `twstock/collectors/history.py`

```diff
--- a/twstock/collectors/history.py
+++ b/twstock/collectors/history.py
@@ -11,12 +11,14 @@
 from ..fetch import FetchError
 from ..health import load_snapshot, medians, missing_keys
 from ..tradingcal import HOLIDAYS, is_trading_day, load_closed, trading_days  # noqa: F401（沿用的對外名稱）
-from .daily import ALL_DATASETS, DATASET_KEYS, INDEX, PRICES, TPEX_INDEX, collect_for_date, collect_tpex_index
+from .daily import (ALL_DATASETS, DATASET_KEYS, DAY_KEYS, INDEX, PARSE_ERRORS, PRICES, TPEX_INDEX, collect_for_date,  # noqa: F401
+                    collect_tpex_index)
 from .revenue import collect_monthly_revenue, revenue_month_for
 
 # 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
 SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
-                   "index.TAIEX": 4, "amount": 4}
+                   "index.TAIEX": 4, "amount": 4, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5}
+SHARED = {"etf.TWSE": "prices.TWSE", "etf.TPEx": "prices.TPEx"}   # 同一天也要抓行情時共用回應，不另計時
 SECONDS_PER_MONTH = 3.2
 
 
@@ -32,20 +34,25 @@
         conn.close()
 
 
+def day_seconds(keys) -> float:
+    return sum(SECONDS_PER_KEY[k] for k in keys if SHARED.get(k) not in keys)
+
+
 def run_history(start: date, end: date, datasets=ALL_DATASETS, force=False,
                 revenue=True, delay=0.0) -> bool:
     """回傳 True = 全部完成；False = 中途疑似被封鎖或欄位不符而停止。"""
     closed, snap, med = load_status(start, end)
     days = trading_days(start, end, closed)
-    keys = tuple(k for ds in datasets if ds != TPEX_INDEX for k in DATASET_KEYS[ds])
-    # 每一天只抓還缺的細項（分市場、看筆數與填充率）；順序照 DATASET_KEYS，行情先於本益比
+    wanted = {k for ds in datasets if ds != TPEX_INDEX for k in DATASET_KEYS[ds]}
+    keys = tuple(k for k in DAY_KEYS if k in wanted)
+    # 每一天只抓還缺的細項（分市場、看筆數與填充率）；順序一律照 DAY_KEYS（行情先於本益比，ETF 先於融資融券），與 --only 的順序無關
     todo = [(d, keys if force else missing_keys(d, keys, snap, med)) for d in days]
     todo = [(d, ks) for d, ks in todo if ks]
     months = []
     if TPEX_INDEX in datasets:
         months = sorted({(d.year, d.month) for d in days if force or missing_keys(d, ("index.TPEX",), snap, med)})
 
-    est = (sum(sum(SECONDS_PER_KEY[k] for k in ks) + delay for _, ks in todo) + SECONDS_PER_MONTH * len(months)) / 60
+    est = (sum(day_seconds(ks) + delay for _, ks in todo) + SECONDS_PER_MONTH * len(months)) / 60
     print(f"📅 補抓範圍：{start} ~ {end}，資料集：{'、'.join(datasets)}")
     print(f"📊 交易日 {len(days)} 天，待抓 {len(todo)} 天；⏱️  預估約 {est:.1f} 分鐘")
     for k in keys:
@@ -82,6 +89,9 @@
                 print(f"  ❌ {e}")
                 blocked_at = date(y, m, 1)
                 break
+            except PARSE_ERRORS as e:          # QA-04：欄位不符不可出現 Traceback
+                schema_err = (date(y, m, 1), e)
+                break
 
     # 月營收：每個月份只抓一次（每市場 1 個請求）
     revenue_months = sorted({m for m in map(revenue_month_for, days) if m})
```

### `twstock/export.py`

```diff
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -2,8 +2,8 @@
 把資料庫內容匯出成靜態 JSON（site/data/），網站只讀這些檔案、不需要後端：
 
   latest.json        今日總覽：大盤統計、台指期日 K、類股/產業鏈/概念股資金流（含回放用的每日座標）、
-                     每檔股票最新指標
-  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈
+                     每檔股票最新指標、融資融券（margin）、ETF（etfs，與股票完全分開）
+  stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券
 """
 import json
 import os
@@ -32,6 +32,8 @@
 CAP_TYPES = ("權", "權息", "減", "面", "調")
 CAP_DAYS = 90
 # 升降單位（一般股票）：(價格上限, 單位)
+MARGIN_DAYS = 20               # 首頁上市股票融資增減迷你柱天數
+COVER_MIN = 99.0               # 維持率分子涵蓋的融資張數 ÷ 官方融資張數（%）低於此值不顯示
 _TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
           (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
 
@@ -196,6 +198,140 @@
             "t": [yi(amount[d]["total"]) for d in recent], "fs": streak(foreign)}
 
 
+# ─── 融資融券（B2＋A4）與 ETF（E1）────────────────────────
+def usage(balance, limit):
+    """融資（券）使用率 %：餘額 ÷ 限額，截斷到小數 2 位（與櫃買官方欄位一致）；限額 0 或空 → None。"""
+    return balance * 10000 // limit / 100 if limit and balance is not None else None
+
+
+def short_ratio(short, margin):
+    """券資比 %：融券餘額 ÷ 融資餘額，四捨五入到小數 2 位；融資 0 → None。"""
+    return round(short / margin * 100, 2) if margin else None
+
+
+def last_close(series, day):
+    """series：[(日期, 收盤)] 舊到新；回傳日期 ≤ day 的最後一個非空收盤（當日無成交用最近收盤）；沒有 → None。"""
+    return next((float(c) for d, c in reversed(series) if d <= day and c is not None), None)
+
+
+def maint_ratio(items, official_lots, amount_k):
+    """
+    大盤融資維持率（自算）= Σ(融資張數 × 1,000 × 收盤) ÷ (官方融資金額仟元 × 1,000) × 100。
+    items：[(融資張數, 收盤或 None)]，股票＋ETF。涵蓋率 = 有收盤的張數 ÷ 官方融資張數（%）。
+    回傳 (維持率, 涵蓋率)，各取小數 2 位；涵蓋率 < COVER_MIN 或沒有金額 → 維持率 None。
+    """
+    covered = sum(n for n, c in items if c is not None)
+    cov = round(covered / official_lots * 100, 2) if official_lots else 0.0
+    if not amount_k or cov < COVER_MIN:
+        return None, cov
+    return round(sum(n * c for n, c in items if c is not None) / amount_k * 100, 2), cov
+
+
+def stock_margin(rows: dict, mdate, d5):
+    """
+    個股 JSON 的 margin。rows：{日期: (融資前日, 融資餘額, 融資限額, 融券前日, 融券餘額, 註記)}；
+    mdate：該市場最新融資融券日；d5：往前第 5 個融資融券日（不足 6 天為 None）。該股當天沒有列 → None（無信用交易）。
+    """
+    r = rows.get(mdate)
+    if r is None:
+        return None
+    mp, mb, ml, sp, sb, nt = r
+    old = rows.get(d5) if d5 else None
+    out = {"d": str(mdate), "mb": mb, "m1": mb - mp, "m5": mb - old[1] if old else None,
+           "sb": sb, "s1": sb - sp, "sr": short_ratio(sb, mb), "mu": usage(mb, ml)}
+    if nt:
+        out["nt"] = nt
+    return out
+
+
+def market_margin(dates, official, stocks, etfs, close):
+    """
+    一個市場的融資融券區塊（latest.json 的 margin.TWSE／margin.TPEx）。
+    dates：該市場有官方合計的日期（舊到新）；official：{日期: (資前, 資今, 券前, 券今, 金前, 金今)}；
+    stocks、etfs：{日期: [(代號, 融資前日, 融資餘額, 融券前日, 融券餘額)]}；close(代號, 日期, 是否ETF) → 收盤或 None。
+    頭條（mb、sb…）只用股票；etf 另計；維持率分子用股票＋ETF、分母用官方融資金額。
+    """
+    if not dates:
+        return None
+    d = dates[-1]
+    pct = lambda a, b: round(a / b * 100, 2) if b else None
+    total = lambda rows, i: sum(r[i] for r in rows)
+
+    def ratio(day):
+        items = [(r[2], close(r[0], day, False)) for r in stocks.get(day, [])] + \
+                [(r[2], close(r[0], day, True)) for r in etfs.get(day, [])]
+        return maint_ratio(items, official[day][1], official[day][5])
+
+    S, E, o = stocks.get(d, []), etfs.get(d, []), official[d]
+    mb, mp, sb, sp = total(S, 2), total(S, 1), total(S, 4), total(S, 3)
+    mr, cov = ratio(d)
+    recent = dates[-MARGIN_DAYS:]
+    return {"d": str(d), "mb": mb, "m1": mb - mp, "mp": pct(mb - mp, mp), "sb": sb, "s1": sb - sp, "sp": pct(sb - sp, sp),
+            "sr": short_ratio(sb, mb), "amt": round(o[5] / 1e5, 1), "amt1": round((o[5] - o[4]) / 1e5, 1),
+            "mr": mr, "mr0": ratio(dates[-2])[0] if len(dates) > 1 else None, "cov": cov,
+            "etf": {"mb": total(E, 2), "m1": total(E, 2) - total(E, 1), "sb": total(E, 4), "s1": total(E, 4) - total(E, 3)},
+            "d20": [str(x) for x in recent], "m20": [total(stocks.get(x, []), 2) - total(stocks.get(x, []), 1) for x in recent]}
+
+
+def _load_margin(cur):
+    """回傳 (各市場日期, 官方合計, 股票列, ETF 列, 個股 rows)；沒有融資融券資料時日期為空。"""
+    mdates = [r[0] for r in cur.execute("SELECT DISTINCT TOP 25 trade_date FROM margin_market ORDER BY trade_date DESC")][::-1]
+    dates, official = defaultdict(list), defaultdict(dict)
+    stocks, etfs = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
+    per_stock = defaultdict(dict)
+    if not mdates:
+        return dates, official, stocks, etfs, per_stock
+    for d, m, *v in cur.execute("SELECT trade_date, market, margin_prev, margin_balance, short_prev, short_balance, "
+                                "amount_prev, amount_balance FROM margin_market WHERE trade_date >= ? ORDER BY trade_date", mdates[0]):
+        dates[m].append(d)
+        official[m][d] = v
+    for code, m, d, mp, mb, ml, sp, sb, nt in cur.execute("""
+        SELECT s.stock_code, s.market_type, x.trade_date, x.margin_prev, x.margin_balance, x.margin_limit,
+               x.short_prev, x.short_balance, x.note
+        FROM margin_trades x JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date >= ?""", mdates[0]):
+        stocks[m][d].append((code, mp, mb, sp, sb))
+        per_stock[code][d] = (mp, mb, ml, sp, sb, nt)
+    for code, m, d, mp, mb, sp, sb in cur.execute("""
+        SELECT e.etf_code, e.market_type, x.trade_date, x.margin_prev, x.margin_balance, x.short_prev, x.short_balance
+        FROM etf_margin x JOIN etfs e ON e.etf_id = x.etf_id WHERE x.trade_date >= ?""", mdates[0]):
+        etfs[m][d].append((code, mp, mb, sp, sb))
+    return dates, official, stocks, etfs, per_stock
+
+
+def _load_etfs(cur, since):
+    """(ETF 收盤序列 {代號: [(日期, 收盤)]}（since 起）, 最新一天的 ETF 列 {市場: (日期, [列])})。"""
+    px = defaultdict(list)
+    for code, d, c in cur.execute("""
+        SELECT e.etf_code, x.trade_date, x.close_price FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
+        WHERE x.trade_date >= ? ORDER BY e.etf_code, x.trade_date""", since):
+        px[code].append((d, c))
+    latest = {}
+    for code, name, m, d, c, ch, v, tv in cur.execute("""
+        SELECT e.etf_code, e.etf_name, e.market_type, x.trade_date, x.close_price, x.change, x.volume, x.trade_value
+        FROM etf_daily x JOIN etfs e ON e.etf_id = x.etf_id
+        WHERE x.trade_date = (SELECT MAX(y.trade_date) FROM etf_daily y JOIN etfs z ON z.etf_id = y.etf_id
+                              WHERE z.market_type = e.market_type)
+        ORDER BY e.etf_code"""):
+        latest.setdefault(m, (d, []))[1].append((code, name, c, ch, v, tv))
+    return px, latest
+
+
+def etf_block(latest, margin_rows):
+    """latest.json 的 etfs。margin_rows：{代號: (融資前日, 融資餘額, 融券前日, 融券餘額)}（該市場最新融資融券日）。"""
+    if not latest:
+        return None
+    rows = {}
+    for m, (d, items) in latest.items():
+        for code, name, c, ch, v, tv in items:
+            r = {"n": name, "m": m, "c": _f(c), "ch": _f(ch), "p": _f(_pct(c, ch)) if c is not None else None,
+                 "v": round((v or 0) / 1000), "tv": round((tv or 0) / YI, 2)}
+            mg = margin_rows.get(code)
+            if mg:
+                r.update(mb=mg[1], m1=mg[1] - mg[0], sb=mg[3], s1=mg[3] - mg[2])
+            rows[code] = r
+    return {"dates": {m: str(d) for m, (d, _) in latest.items()}, "rows": rows}
+
+
 def _load_chains(cur):
     """回傳 ({產業鏈: [代號...]}, {代號: [[產業鏈, 區段, [細項...]], ...]})。"""
     groups, tags = defaultdict(list), defaultdict(dict)
@@ -331,8 +467,13 @@
         FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
         ORDER BY s.stock_code, e.event_date"""):
         events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
+    mdates, mofficial, mstocks, metfs, mper = _load_margin(cur)
+    first_m = min((ds[0] for ds in mdates.values()), default=latest_date)
+    etf_px, etf_latest = _load_etfs(cur, first_m - timedelta(days=60))
     status = build_status(cur, latest_date, now)
     conn.close()
+    mlast = {m: ds[-1] for m, ds in mdates.items()}
+    m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
 
     concepts = load_concepts()
     concept_of = defaultdict(list)
@@ -380,6 +521,9 @@
                     if code in fund else None,
             **({"capchg": cap} if (cap := _cap_event(ev, latest_date)) else {}),
             **({"alerts": alerts[code]} if code in alerts else {}),
+            # 該市場有融資融券資料時才有 margin；null = 不在信用交易清單（無信用交易）
+            **({"margin": stock_margin(mper.get(code, {}), mlast[info["market"]], m5[info["market"]])}
+               if info["market"] in mlast else {}),
         })
 
         # 板塊計算用的近 WINDOW 天
@@ -451,6 +595,13 @@
     for code in snapshot:
         industries[snapshot[code]["i"]].append(code)
 
+    # 維持率用的收盤：股票取 prices（日期 ≤ 當日最後收盤），ETF 取 etf_daily
+    stock_px = {code: [(r[0], r[4]) for r in rows] for code, rows in prices.items()}
+    close = lambda code, day, is_etf: last_close((etf_px if is_etf else stock_px).get(code, []), day)
+    margin = {m: market_margin(mdates[m], mofficial[m], mstocks[m], metfs[m], close) for m in ("TWSE", "TPEx")
+              if mdates.get(m)} or None
+    etf_margin_rows = {code: (mp, mb, sp, sb) for m, d in mlast.items() for code, mp, mb, sp, sb in metfs[m].get(d, [])}
+
     replay_dates = [str(d) for d in dates[-REPLAY:]]
     latest = {
         "updated_at": status["collected_at"],     # 最後成功收集時間，不是匯出時間
@@ -471,6 +622,8 @@
         "futures": futures,
         "futures_oi": futures_oi,
         "forecast": forecast,
+        "margin": margin,
+        "etfs": etf_block(etf_latest, etf_margin_rows),
         "groups": {
             "industry": group_flows(industries, daily, dates, REPLAY),
             "chain": group_flows(chains, daily, dates, REPLAY),
```

### `twstock/__main__.py`

```diff
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -4,12 +4,13 @@
   python -m twstock setup-db                         建立資料庫與資料表
   python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額）並匯出網站資料
   python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行），有新資料才匯出；排程用這個
-  python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）；有異常回傳 1
-  python -m twstock history --start 2026-01-01       補抓歷史（只補缺的，可中斷重跑）
+  python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）：開頭列最後一次收集與排程狀態，有異常時印建議指令並回傳 1
+  python -m twstock history --start 2026-01-01       補抓歷史（行情、本益比、法人、ETF、融資融券；只補缺的，可中斷重跑）
   python -m twstock history --start 2025-10-30 --only pe      只補本益比／淨值比／殖利率
   python -m twstock history --start 2026-02-23 --only index   只補加權指數歷史
   python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
   python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
+  python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
   python -m twstock export                           從資料庫匯出網站 JSON（site/data）
@@ -58,6 +59,9 @@
 
 
 def cmd_check(args):
+    if args.days < 1:
+        print("❌ --days 至少 1")
+        return 1
     from .health import run_check
     import pyodbc
     try:
@@ -177,9 +181,9 @@
     s = sub.add_parser("history", help="補抓歷史資料")
     s.add_argument("--start", type=_date, required=True)
     s.add_argument("--end", type=_date, help="預設今天")
-    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index"],
+    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "etf", "margin"],
                    help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
-                        "amount = 上市三大法人買賣金額）")
+                        "amount = 上市三大法人買賣金額，etf = ETF 行情，margin = 融資融券）；預設 prices pe insti etf margin")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
     s.add_argument("--no-revenue", action="store_true")
     s.add_argument("--delay", type=float, default=0.0, help="每日之間額外暫停秒數")
@@ -197,7 +201,7 @@
     s.set_defaults(fn=cmd_events)
 
     s = sub.add_parser("check", help="檢查近 N 個交易日各資料集的完整性（唯讀、不連外）；有異常回傳 1")
-    s.add_argument("--days", type=int, default=20, help="預設 20")
+    s.add_argument("--days", type=int, default=20, help="預設 20，至少 1")
     s.set_defaults(fn=cmd_check)
 
     sub.add_parser("export", help="匯出網站 JSON 到 site/data").set_defaults(fn=cmd_export)
```

### `site/index.html`

```diff
--- a/site/index.html
+++ b/site/index.html
@@ -26,6 +26,7 @@
     <a href="#/today" data-tab="today">今日</a>
     <a href="#/bubble" data-tab="bubble">泡泡圖</a>
     <a href="#/rank" data-tab="rank">排行</a>
+    <a href="#/etf" data-tab="etf">ETF</a>
     <a href="#/watch" data-tab="watch">自選</a>
   </nav>
 </header>
@@ -38,6 +39,7 @@
   <a href="#/today" data-tab="today"><svg viewBox="0 0 24 24"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg>今日</a>
   <a href="#/bubble" data-tab="bubble"><svg viewBox="0 0 24 24"><circle cx="8" cy="14" r="5"/><circle cx="17" cy="8" r="4"/><circle cx="17" cy="18" r="2.5"/></svg>泡泡圖</a>
   <a href="#/rank" data-tab="rank"><svg viewBox="0 0 24 24"><path d="M5 20V10M12 20V4M19 20v-7"/></svg>排行</a>
+  <a href="#/etf" data-tab="etf"><svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>ETF</a>
   <a href="#/watch" data-tab="watch"><svg viewBox="0 0 24 24"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>自選</a>
 </nav>
 
```

### `site/app.css`

```diff
--- a/site/app.css
+++ b/site/app.css
@@ -186,6 +186,8 @@
 .ev-note{color:var(--blue)}
 .rel{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
 @media (max-width:520px){.g-stats .insti{grid-column:1/-1}}   /* 手機佔滿一列，三行數字不擠成 166px */
+.g-stats .margin{grid-column:1/-1}   /* 信用交易卡：行數多，佔滿一列 */
+.night-old{opacity:.7}               /* P20：前一夜盤淡化 */
 .al{display:inline-block;font-style:normal;font-size:10px;line-height:15px;padding:0 3px;border-radius:3px;margin-left:4px;color:#fff;vertical-align:1px}
 .al-d{background:var(--up)}.al-n{background:var(--amber)}
 .pill.al-d{background:var(--up-bg);border-color:var(--up);color:var(--up)}
```

### `site/app.js`

```diff
--- a/site/app.js
+++ b/site/app.js
@@ -62,6 +62,7 @@
   bubble: renderBubble,
   rank: renderRank,
   watch: renderWatch,
+  etf: renderEtf,
   stock: code => window.renderStock(code),
 };
 
@@ -150,6 +151,7 @@
     <section class="sec grid g-stats">
       ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
       ${instiCard(L)}
+      ${marginCard(L)}
     </section>
 
     ${futuresHTML(L.futures)}
@@ -164,7 +166,7 @@
 
     <section class="sec grid g2">
       <div class="card">
-        <div class="sec-h"><h2>錢流去哪</h2><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
+        <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
         <div class="bars">${inflow.map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
       </div>
       <div class="card">
@@ -174,9 +176,9 @@
     </section>
 
     ${flowNote()}<section class="sec grid g2">
-      <div class="card"><div class="sec-h"><h2>法人買超</h2><span class="muted small">${md(L.flow_date)}，億</span></div>
+      <div class="card"><div class="sec-h"><h2>法人買超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
         <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topBuy)}</tbody></table></div></div>
-      <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">${md(L.flow_date)}，億</span></div>
+      <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
         <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topSell)}</tbody></table></div></div>
     </section>`;
 
@@ -236,6 +238,28 @@
     vals.map((v, i) => { const h = Math.abs(v) / m * 16;
       return `<rect x="${(i * w + w * 0.15).toFixed(2)}" y="${(v >= 0 ? 17 - h : 17).toFixed(2)}" width="${(w * 0.7).toFixed(2)}" height="${h.toFixed(2)}" fill="var(--${v >= 0 ? 'up' : 'dn'})"/>`; }).join('') +
     '</svg>';
+}
+
+// 信用交易卡（B2＋A4）：頭條為股票口徑（不含 ETF）；官方含 ETF 只列融資金額；ETF 另計一行；官方融資、融券張數不顯示
+function marginCard(L) {
+  const M = L.margin;
+  if (!M) return '';
+  const T = M.TWSE, O = M.TPEx, d = [T?.d, O?.d].filter(Boolean).sort().at(-1);
+  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, 1)}</b> 萬張`;
+  const lots = n => `<span class="${cls(n)}">${sgn(n, 0)}</span>`;
+  const row = (x, name) => !x ? '' : `<div class="s num">${name}　融資 ${wan(x.mb)} ${lots(x.m1)}（${sgn(x.mp)}%）　融券 ${wan(x.sb)} ${lots(x.s1)}　券資比 ${fmt(x.sr, 2)}%${x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : ''}</div>`;
+  const mr = x => !x ? '--' : x.mr == null ? '資料不足' : `${fmt(x.mr, 1)}%（前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}）`;
+  const amt = x => !x ? '--' : `${fmt(x.amt, 1)} 億 <span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`;
+  const E = T?.etf;
+  return `<div class="card stat idx margin">
+      <div class="l">信用交易 ${md(d)}（股票，不含 ETF）${d < L.date ? '<span class="muted">（尚未更新）</span>' : ''}</div>
+      ${row(T, '上市')}${row(O, '上櫃')}
+      <div class="s num">融資維持率（自算）上市 ${mr(T)}　上櫃 ${mr(O)}</div>
+      <div class="s num">融資金額（官方，含 ETF）上市 ${amt(T)}　上櫃 ${amt(O)}</div>
+      ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
+      ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
+      <div class="s">維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
+    </div>`;
 }
 
 // 三大法人卡：上市用證交所官方金額（A2），上櫃另列估算值；尚無官方資料時維持第 1 輪估算卡
@@ -251,6 +275,7 @@
       <div class="l">三大法人　上市，官方，含 ETF<span class="muted">　${md(O.date)}${stale ? '（尚未更新）' : ''}</span></div>
       <div class="v num ${cls(O.total)}">${yi1(O.total)}</div>
       <div class="s num">外資 <span class="${cls(O.foreign)}">${yi1(O.foreign)}</span>　投信 <span class="${cls(O.trust)}">${yi1(O.trust)}</span>　自營 <span class="${cls(O.dealer)}">${yi1(O.dealer)}</span></div>
+      <div class="s">官方含 ETF 與權證避險，與下方估算口徑不同</div>
       ${minibars(O.f)}
       <div class="s">外資近 ${O.f.length} 日（${md(O.d[0])}～${md(O.d.at(-1))}）<b class="${cls(fs)}">${fs > 0 ? `連買 ${fs} 日` : fs < 0 ? `連賣 ${-fs} 日` : '當日持平'}</b></div>
       ${X ? `<div class="s num">上櫃估算（${md(L.flow_date)}）：外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
@@ -262,12 +287,13 @@
   if (!F || !F.d.length) return '';
   const k = F.d.length - 1, c = F.c[k], ch = F.ch[k], pct = ch != null && c !== ch ? ch / (c - ch) * 100 : null;
   const N = F.night;
+  // P20：夜盤歸屬日 D = 前一個交易日 15:00 ~ D 05:00；D ≤ 日盤日期 = 日盤收盤之前的夜盤，放最前面並淡化
+  const old = N && N.date <= F.d[k];
   let night = '';
   if (N) {
-    // 夜盤歸屬日 D = 前一個交易日 15:00 ~ D 05:00
     const from = [...F.d].reverse().find(d => d < N.date);
     const np = N.ch != null && N.c !== N.ch ? N.ch / (N.c - N.ch) * 100 : null;
-    night = `<span>夜盤 ${from ? md(from) + ' 15:00～' : ''}${md(N.date)} 05:00　收 <b class="num ${cls(N.ch)}">${fmt(N.c)}</b>
+    night = `<span class="${old ? 'night-old' : ''}">${old ? '前一夜盤' : '最新夜盤'}（${from ? md(from) + ' 15:00～' : ''}${md(N.date)} 05:00）　收 <b class="num ${cls(N.ch)}">${fmt(N.c)}</b>
       <span class="num ${cls(N.ch)}">${sgn(N.ch, 0)} (${sgn(np)}%)</span></span>`;
   }
   return `<section class="sec card">
@@ -278,8 +304,8 @@
         <span class="s-chg num ${cls(ch)}">${ch > 0 ? '▲' : ch < 0 ? '▼' : ''} ${fmt(Math.abs(ch ?? 0))} (${sgn(pct)}%)</span>
         <span class="muted small">${F.d[k]}</span>
       </div>
-      <div class="fut-sub muted small"><span>成交量 <b class="num">${fmt(F.v[k])}</b> 口</span>
-        <span>未平倉 <b class="num">${fmt(F.oi[k])}</b> 口</span>${night}</div>
+      <div class="fut-sub muted small">${old ? night : ''}<span>成交量 <b class="num">${fmt(F.v[k])}</b> 口</span>
+        <span>未平倉 <b class="num">${fmt(F.oi[k])}</b> 口</span>${old ? '' : night}</div>
       <div class="kleg" id="fLegend"></div>
       <div id="fC" class="chart-box" style="height:300px"></div>
     </section>`;
@@ -622,7 +648,41 @@
   onSeg('mktSeg', v => { localStore('mkt', null, v); renderRank(); });
   $('#view').addEventListener('click', onRowClick);
 }
+
+// ─── ETF（E1）：與股票完全分開，不計入任何個股統計 ─────────
+const ETF_SORT = [['tv', '成交額', -1], ['p+', '漲幅', -1], ['p-', '跌幅', 1], ['m1', '融資增減', -1], ['s1', '融券增減', -1]];
 
+function renderEtf() {
+  const E = App.latest.etfs;
+  if (!E) {
+    $('#view').innerHTML = '<div class="empty">尚無 ETF 資料：請在收集資料的電腦執行 python3 -m twstock history --start 2025-10-30 --only etf margin</div>';
+    return;
+  }
+  const by = localStore('etfSort', 'tv'), mkt = localStore('etfMkt', 'all');
+  const [key, , dir] = ETF_SORT.find(x => x[0] === by) || ETF_SORT[0];
+  const f = key.replace(/[+-]$/, '');
+  const list = Object.entries(E.rows).filter(([, r]) => mkt === 'all' || r.m === mkt)
+    .sort((a, b) => (a[1][f] == null) - (b[1][f] == null) || dir * ((a[1][f] ?? 0) - (b[1][f] ?? 0)));
+  const lots = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, 0)}</td>`;
+  const dates = Object.entries(E.dates).map(([m, d]) => `${m === 'TWSE' ? '上市' : '上櫃'} ${md(d)}`).join('　');
+  $('#view').innerHTML = `<section class="sec">
+      <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span><span class="sp"></span>
+        ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
+        <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
+      <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
+        <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th></tr></thead><tbody>` +
+      list.map(([c, r]) => `<tr><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span></td>
+        <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
+        <td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
+        <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
+        <td class="num">${r.mb == null ? '--' : fmt(r.mb)}</td>${lots(r.m1)}
+        <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}</tr>`).join('') +
+      `</tbody></table></div></div>
+      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
+  $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
+  onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
+}
+
 function renderWatch() {
   const S = App.latest.stocks, span = localStore('rspan', '1');
   const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
@@ -658,7 +718,7 @@
   const st = L.status;
   if (!st) return [];               // 舊版 latest.json：維持原本的日期列
   const lines = [], exp = expectedDate(t, new Set(st.closed || []));
-  if (L.date < exp) lines.push(`資料停在 ${md(L.date)}，最新交易日為 ${md(exp)}，可能尚未收集`);
+  if (L.date < exp) lines.push(`資料停在 ${md(L.date)}，最新交易日為 ${md(exp)}，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up`);
   const bad = (st.datasets || []).filter(x => x.s === 'abnormal' && x.m).map(x => x.m);
   if (bad.length) lines.push(`部分資料異常：${bad.slice(0, 3).join('、')}${bad.length > 3 ? ` 等 ${bad.length} 項` : ''}`);
   return lines;
```

### `site/stock.js`

```diff
--- a/site/stock.js
+++ b/site/stock.js
@@ -13,6 +13,8 @@
   if (window.Plotly && $('#revC')) Plotly.purge('revC');
 };
 
+const MARGIN_NOTE = { O: '停止融資', X: '停止融券', '@': '融資分配', '%': '融券分配', '!': '停止買賣' };   // 上市註記
+
 window.renderStock = async function (code) {
   const s = App.latest.stocks[code];
   let data;
@@ -40,6 +42,14 @@
   const fd = md(App.latest.flow_date);
   const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
   const hlSub = hlFrom ? '自 ' + hlFrom.replaceAll('-', '/') : '';
+  // B2：融資融券指標卡。margin 不存在 = 尚無融資融券資料（不顯示）；null = 不在信用交易清單
+  const MG = data.margin;
+  const mgNote = MG?.nt && data.market === 'TWSE' ? [...MG.nt].map(ch => MARGIN_NOTE[ch]).filter(Boolean).join('、') : '';
+  const mgCards = MG === undefined ? [] : MG === null ? [['信用交易', '無信用交易', 'flat', '不在融資融券清單']]
+    : [['融資餘額', fmt(MG.mb) + ' 張', '', `1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`],
+       ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
+       ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
+       ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
 
   $('#view').innerHTML = `
     <section class="sec card">
@@ -71,7 +81,7 @@
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          ['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
-         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd]]
+         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
 
```

### `scripts/mac/install_schedule.sh`

```diff
--- a/scripts/mac/install_schedule.sh
+++ b/scripts/mac/install_schedule.sh
@@ -1,5 +1,5 @@
 #!/bin/bash
-# launchd 排程：週一到週五 17:30、19:30、21:45，以及登入時，執行 collect --catch-up
+# launchd 排程：週一到週五 17:30、19:30、21:45、22:30，以及登入時，執行 collect --catch-up（22:30 負責當天的異常判定）
 #   bash install_schedule.sh             安裝（安裝當下與之後每次登入都會補跑一次）
 #   bash install_schedule.sh --print     只印出 plist 內容，不安裝、不動 launchctl
 #   bash install_schedule.sh --uninstall 移除
@@ -21,7 +21,7 @@
 render_plist() {
   local times="" wd t
   for wd in 1 2 3 4 5; do
-    for t in "17 30" "19 30" "21 45"; do
+    for t in "17 30" "19 30" "21 45" "22 30"; do
       set -- $t
       times="$times<dict><key>Weekday</key><integer>$wd</integer><key>Hour</key><integer>$1</integer><key>Minute</key><integer>$2</integer></dict>"
     done
@@ -57,5 +57,5 @@
 mkdir -p "$ROOT/logs" "$HOME/Library/LaunchAgents"
 render_plist > "$PLIST"
 launchctl bootstrap "gui/$(id -u)" "$PLIST"
-echo "✅ 已安裝排程：週一至週五 17:30、19:30、21:45，以及登入時；紀錄寫入 logs/collect.log"
+echo "✅ 已安裝排程：週一至週五 17:30、19:30、21:45、22:30，以及登入時；紀錄寫入 logs/collect.log"
 echo "   安裝當下會立刻執行一次（RunAtLoad）。立即再測一次：launchctl kickstart gui/$(id -u)/$LABEL"
```

### `tests/test_iter03.py`

```diff
--- a/tests/test_iter03.py
+++ b/tests/test_iter03.py
@@ -101,7 +101,8 @@
 def _full_snapshot(days, skip=()):
     ok = {"prices.TWSE": Row(1086), "prices.TPEx": Row(889), "pe.TWSE": Row(1082, 870, 1082, 1082),
           "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6),
-          "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9)}
+          "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9),
+          "etf.TWSE": Row(250), "etf.TPEx": Row(120), "margin.TWSE": Row(1100), "margin.TPEx": Row(900)}   # 第 4 輪
     return {k: {d: v for d in days if (k, d) not in skip} for k, v in ok.items()}
 
 
@@ -355,7 +356,18 @@
 INX_FIELDS = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
 FUT_HEAD = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\r\n"
 OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
-ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown")
+ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown",
+          "MI_MARGN", "margin/balance")
+# 第 4 輪：行情回應含 ETF 列（另有權證、TDR 等其他證券，兩邊都不可寫入）；融資融券回應含股票與 ETF
+TWSE_ETFS = [f"00{n:03d}" for n in range(100, 350)]          # 250 檔，如 00100
+TPEX_ETFS = [f"00{n:03d}B" for n in range(700, 820)]         # 120 檔，如 00700B
+OTHERS = ["910322", "020001", "01001T", "2881A", "710000"]    # TDR、ETN、受益證券、特別股、權證
+MGN_FIELDS = ["代號", "名稱", "買進", "賣出", "現金償還", "前日餘額", "今日餘額", "次一營業日限額",
+              "買進", "賣出", "現券償還", "前日餘額", "今日餘額", "次一營業日限額", "資券互抵", "註記"]
+MGN_GROUPS = [{"title": "股票", "span": 2}, {"title": "融資", "span": 6}, {"title": "融券", "span": 6},
+              {"title": "", "span": 1}, {"title": "", "span": 1}]
+TPM_FIELDS = ["代號", "名稱", "前資餘額(張)", "資買", "資賣", "現償", "資餘額", "資屬證金", "資使用率(%)", "資限額", "前券餘額(張)",
+              "券賣", "券買", "券償", "券餘額", "券屬證金", "券使用率(%)", "券限額", "資券相抵(張)", "備註"]
 
 
 class World:
@@ -364,6 +376,7 @@
     def __init__(self, seed_until, unsettled=False):
         self.published = {ep: set() for ep in ALL_EP}
         self.renamed, self.down, self.requests, self.merges = set(), set(), [], []
+        self.no_etf = False                                     # 第 4 輪：行情回應沒有任何 ETF 列
         self.cells = defaultdict(lambda: defaultdict(dict))     # {表: {日期: {鍵: 列}}}
         self.rows = {s.key: {} for s in health.SPECS}
         self.runs, self.holidays, self.exports, self.notices = [], [], 0, []
@@ -397,7 +410,8 @@
             return Resp(CAL)
         for key, fn in (("MI_INDEX", self._mi), ("BWIBBU_d", self._bwi), ("fund/T86", self._t86), ("BFI82U", self._bfi),
                         ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
-                        ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi)):
+                        ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi),
+                        ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn)):
             if key in url:
                 return fn(form)
         return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})
@@ -415,7 +429,8 @@
         if self._no("MI_INDEX", form):
             return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
         fields = ["欄位改名"] + MI_FIELDS[1:] if "MI_INDEX" in self.renamed else MI_FIELDS
-        rows = [[c, "名", "1000", "10", "10000", "10", "11", "9", "10.5", "+", "0.5"] for c in TWSE_CODES]
+        etfs = [] if self.no_etf else TWSE_ETFS
+        rows = [[c, "名", "1000", "10", "10000", "10", "11", "9", "10.5", "+", "0.5"] for c in TWSE_CODES + etfs + OTHERS]
         idx = {"title": "價格指數(臺灣證券交易所)", "fields": ["指數", "收盤指數", "漲跌(+/-)", "漲跌點數", "漲跌百分比(%)"],
                "data": [["發行量加權股價指數", "45,211.83", "<p>-</p>", "1,156.50", "-2.49"]]}
         return Resp({"stat": "OK", "tables": [idx, {"fields": fields, "data": rows}]})
@@ -444,8 +459,31 @@
     def _quotes(self, form):
         if self._no("dailyQuotes", form):
             return self._empty_tables(Q_FIELDS)
-        return Resp({"stat": "ok", "tables": [{"fields": Q_FIELDS, "data": [[c, "名", "10.5", "0.5", "10", "11", "9", "1000", "10000", "10"] for c in TPEX_CODES]}]})
+        etfs = [] if self.no_etf else TPEX_ETFS
+        return Resp({"stat": "ok", "tables": [{"fields": Q_FIELDS, "data": [[c, "名", "10.5", "0.5", "10", "11", "9", "1000", "10000", "10"]
+                                                                            for c in TPEX_CODES + etfs + OTHERS]}]})
 
+    def _mgn(self, form):
+        if self._no("MI_MARGN", form):
+            return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
+        fields = MGN_FIELDS[:6] + ["改名"] + MGN_FIELDS[7:] if "MI_MARGN" in self.renamed else MGN_FIELDS
+        total = {"fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
+                 "data": [["融資(交易單位)", "1", "1", "0", "200", "200"], ["融券(交易單位)", "1", "1", "0", "20", "20"],
+                          ["融資金額(仟元)", "1", "1", "0", "3,000", "3,000"]]}
+        rows = [[c, "名", "1", "1", "0", "100", "100", "1,000", "0", "0", "0", "10", "10", "1,000", "0", " "]
+                for c in TWSE_CODES + TWSE_ETFS + OTHERS]
+        return Resp({"stat": "OK", "tables": [total, {"fields": fields, "groups": MGN_GROUPS, "data": rows}]})
+
+    def _tpex_mgn(self, form):
+        if self._no("margin/balance", form):
+            return self._empty_tables(TPM_FIELDS)
+        fields = ["改名" if f == "資餘額" else f for f in TPM_FIELDS] if "margin/balance" in self.renamed else TPM_FIELDS
+        rows = [[c, "名", "100", "1", "1", "0", "100", "0", "10.0", "1,000", "10", "0", "0", "0", "10", "0", "1.0", "1,000", "0", ""]
+                for c in TPEX_CODES + TPEX_ETFS]
+        summary = [["", "合計(張)", "200", "", "", "", "200", "", "", "", "20", "", "", "", "20", "", "", "", "", ""],
+                   ["", "融資金(仟元)", "3,000", "", "", "", "3,000", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
+        return Resp({"stat": "ok", "tables": [{"fields": fields, "data": rows, "summary": summary}]})
+
     def _pe(self, form):
         if self._no("peQryDate", form):
             return self._empty_tables(PE_FIELDS)
@@ -489,8 +527,13 @@
         rows = json.loads(params[0])
         pd = next((p for p in params[1:] if isinstance(p, date)), None)
         market = lambda c: "TWSE" if c < "3000" else "TPEx"
-        if table in ("daily_prices", "stock_fundamentals", "institutional_trades"):
-            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti"}[table]
+        if table == "etf_daily":                                # 第 4 輪：上櫃 ETF 以 B 結尾
+            for mk in ("TWSE", "TPEx"):
+                mine = [r for r in rows if r["stock_code"].endswith("B") == (mk == "TPEx")]
+                if mine:
+                    self.rows[f"etf.{mk}"][pd] = Row(len(mine))
+        elif table in ("daily_prices", "stock_fundamentals", "institutional_trades", "margin_trades"):
+            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti", "margin_trades": "margin"}[table]
             for mk in ("TWSE", "TPEx"):
                 mine = [r for r in rows if market(r["stock_code"]) == mk]
                 if mine:
@@ -1083,7 +1126,7 @@
         rc, out, first = run_site(w, T(10, 30, 22, 0), Path(tmp))
         assert rc == 0 and w.exports == 0 and "2026-11-02" not in first["status"]["closed"]
         lines = fresh_lines(first, "2026-11-03T10:00:00+08:00")
-        assert lines is None or lines == [["資料停在 10/30，最新交易日為 11/02，可能尚未收集"]]    # 修正前的誤報
+        assert lines is None or lines == [["資料停在 10/30，最新交易日為 11/02，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up"]]    # 修正前的誤報
         rc, out, L = run_site(w, T(11, 3, 9, 0), Path(tmp))
         assert rc == 0 and "判定為臨時休市" in out and w.exports == 1 and "2026-11-02" in L["status"]["closed"]
         assert L["status"]["collected_at"] == first["status"]["collected_at"] and w.runs[-1][1] == 0
@@ -1100,7 +1143,7 @@
         assert rc == 0 and "判定為臨時休市" in out and w.exports == 1 and "2026-11-06" in L["status"]["closed"]
         lines = fresh_lines(L, "2026-11-07T10:00:00+08:00", "2026-11-08T20:00:00+08:00", "2026-11-09T17:59:00+08:00",
                             "2026-11-09T18:00:00+08:00")
-        assert lines is None or lines == [[], [], [], ["資料停在 11/05，最新交易日為 11/09，可能尚未收集"]]
+        assert lines is None or lines == [[], [], [], ["資料停在 11/05，最新交易日為 11/09，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up"]]
         rc, out, _ = run_site(w, T(11, 8, 10, 0), Path(tmp))
         assert rc == 0 and w.exports == 1
 
```

## 附錄 D：`tests/test_iter04.py`（新檔，完整內容）

執行：`python3 tests/test_iter04.py`，應印出 26 個 ✅ 與「全部通過」。它從 `tests/` 匯入 `test_iter03` 的 `World`，所以附錄 C 的 `test_iter03.py` 修改必須先套用。

```python
"""
第 04 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
B2＋A4 融資融券解析、資料集、維持率；E1 ETF 分流與資料集；S10 check 開頭、全缺合併、建議指令、QA-04、QA-06；
S11 排程 22:30；橫幅文字。假的官方網站與資料庫沿用 test_iter03 的 World（真實流程，只有 HTTP 與資料庫是假的）。

  python3 tests/test_iter04.py      （也相容 pytest）
"""
import contextlib
import io
import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, fetch, health  # noqa: E402
from twstock.collectors import catchup, daily, history  # noqa: E402
from twstock.fetch import SchemaError, is_etf_code, is_valid_stock_code  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, env, run_world, CLOSED = t3.D, t3.T, t3.World, t3.env, t3.run_world, t3.CLOSED
REAL_NOTIFY = health.notify_once

# ─── 2026-11-03 實際回應的樣本列（scratchpad 保存的原始回應，未修改）────
TW_MARGIN_TOTAL = {"title": "115年11月03日 信用交易統計", "fields": ["項目", "買進", "賣出", "現金(券)償還", "前日餘額", "今日餘額"],
                   "data": [["融資(交易單位)", "377,983", "450,131", "16,103", "9,571,090", "9,482,839"],
                            ["融券(交易單位)", "31,896", "103,607", "8,680", "194,930", "257,961"],
                            ["融資金額(仟元)", "21,189,249", "41,240,308", "2,873,840", "622,699,365", "599,774,466"]]}
TW_MARGIN_ROWS = [
    ["00406A", "主動中信台灣收益", "28,884", "14,722", "896", "233,924", "247,190", "4,138,390", "0", "65,270", "0", "0", "65,270", "4,138,390", "3,381", " "],
    ["0050", "元大台灣50", "2,953", "1,345", "53", "27,431", "28,986", "5,922,500", "76", "75", "0", "228", "227", "5,922,500", "23", " "],
    ["1589", "永冠-KY", "0", "0", "32", "37", "5", "0", "0", "0", "0", "0", "0", "0", "0", "OX!"],
    ["2236", "百達-KY", "167", "131", "0", "13,535", "13,571", "15,879", "12", "14", "0", "19", "21", "15,879", "0", "@ "],
    ["2303", "聯電", "6,108", "16,355", "350", "157,064", "146,467", "3,142,523", "574", "258", "104", "1,292", "872", "3,142,523", "145", " "],
    ["2376", "技嘉", "279", "189", "4", "6,688", "6,774", "167,472", "20", "66", "6", "2,241", "2,281", "167,472", "1", " "],
    ["2414", "精技", "6", "6", "0", "252", "252", "40,433", "0", "0", "0", "0", "0", "40,433", "0", "X "],
    ["912000", "晨訊科-DR", "53", "20", "0", "14,486", "14,519", "39,480", "0", "0", "0", "1", "1", "39,480", "0", " "],
]
TPM_ROWS = [
    ["00679B", "元大美債20年", "4,106", "899", "145", "0", "4,860", "27", "0.32", "1,513,298", "25", "0", "1", "0", "24", "0", "0.0", "1,513,298", "1", ""],
    ["006201", "元大富櫃50", "567", "153", "21", "0", "699", "72", "11.2", "6,236", "19", "0", "4", "0", "15", "0", "0.24", "6,236", "4", ""],
    ["2035", "唐榮", "0", "0", "0", "0", "0", "0", "0.0", "0", "0", "0", "0", "0", "0", "0", "0.0", "0", "0", "11OX   C"],
    ["3105", "穩懋", "42,425", "2,464", "2,093", "2", "42,794", "506", "40.37", "105,985", "1,413", "912", "428", "0", "1,897", "47", "1.78", "105,985", "7", ""],
]
TPM_SUMMARY = [["", "合計(張)", "2,308,903", "60,870", "97,921", "2,540", "2,269,312", "", "", "", "36,704", "10,076", "6,584", "1,825", "38,371", "", "", "", "", ""],
               ["", "融資金(仟元)", "204,410,217", "6,397,083", "13,109,481", "1,134,921", "196,562,898", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
MI_ROWS = [   # MI_INDEX 行情表（欄位 = MI_FIELDS_REAL）
    ["0050", "元大台灣50", "302,407,473", "732,782", "30,759,303,345", "102.50", "103.35", "100.50", "100.60", "<p style= color:green>-</p>", "3.50", "100.55", "3,058", "100.60", "970", "0.00"],
    ["00406A", "主動中信台灣收益", "1,608,938,491", "331,206", "13,060,137,327", "8.30", "8.35", "7.96", "7.98", "<p>X</p>", "0.00", "7.98", "6,349", "7.99", "9,238", "0.00"],
    ["00666R", "富邦恒生國企反1", "1", "1", "9", "--", "--", "--", "--", "<p> </p>", "0.00", "9.60", "80", "9.63", "104", "0.00"],
    ["00878", "國泰永續高股息", "192,034,182", "174,043", "6,572,661,708", "34.58", "34.74", "33.77", "33.87", "<p style= color:green>-</p>", "0.93", "33.86", "351", "33.87", "1,295", "0.00"],
    ["01001T", "土銀富邦R1", "18,100", "5", "199,863", "11.04", "11.04", "11.02", "11.02", "<p style= color:green>-</p>", "0.03", "11.02", "2", "11.04", "26", "0.00"],
    ["020000", "富邦特選蘋果N", "0", "0", "0", "--", "--", "--", "--", "<p> </p>", "0.00", "27.85", "10", "27.91", "10", "0.00"],
    ["1101B", "台泥乙特", "9,000", "7", "386,300", "42.95", "42.95", "42.90", "42.90", "<p style= color:green>-</p>", "0.10", "42.90", "4", "43.00", "11", "0.00"],
    ["2330", "台積電", "46,137,336", "518,606", "106,329,297,685", "2,300.00", "2,335.00", "2,280.00", "2,295.00", "<p style= color:green>-</p>", "35.00", "2,290.00", "133", "2,295.00", "843", "26.60"],
    ["910322", "康師傅-DR", "91,611", "64", "2,413,089", "26.05", "26.50", "25.50", "25.50", "<p style= color:green>-</p>", "0.55", "25.65", "1", "26.45", "1", "0.00"],
]
MI_FIELDS_REAL = ["證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)", "漲跌價差",
                  "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"]
DQ_FIELDS_REAL = ["代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "均價", "成交股數", "成交金額(元)", "成交筆數", "最後買價",
                  "最後買量(張數)", "最後賣價", "最後賣量(張數)", "發行股數", "次日 參考價", "次日 漲停價", "次日 跌停價"]
DQ_ROWS = [
    ["006201", "元大富櫃50", "37.48", "-3.10 ", "40.00", "40.00", "37.44", "38.45", "667,586", "25,665,547", "840", "37.47", "1", "37.48", "16", "24,446,000", "37.48", "41.22", "33.74"],
    ["00679B", "元大美債20年", "26.54", "+0.14", "26.49", "26.60", "26.46", "26.54", "37,322,231", "990,372,248", "8,205", "26.54", "661", "26.55", "183", "6,082,692,000", "26.54", "9999.95", "0.01"],
    ["020001", "富邦存股雙十N", " ---", "--- ", "---", "---", "---", "26.88", "0", "0", "0", "24.95", "50", "25.02", "50", "40,000,000", "25.02", "27.52", "22.52"],
    ["3105", "穩懋", "530.00", "-58.00 ", "555.00", "564.00", "530.00", "544.08", "24,059,926", "13,090,432,968", "36,153", "0.00", "0", "530.00", "2586", "423,940,384", "530.00", "583.00", "477.00"],
    ["710000", "精材群益5C購02", " ---", "--- ", "---", "---", "---", "9.05", "0", "0", "0", "0.00", "0", "5.85", "10", "5,000,000", "5.85", "8.00", "3.70"],
]


def _tw_margin(rows=TW_MARGIN_ROWS, fields=None, groups=None, total=True, stat="OK"):
    detail = {"title": "115年11月03日 融資融券彙總 (全部)", "fields": fields or t3.MGN_FIELDS, "groups": groups or t3.MGN_GROUPS,
              "data": [list(r) for r in rows]}
    return {"stat": stat, "tables": ([TW_MARGIN_TOTAL] if total else []) + [detail]}


def _tp_margin(rows=TPM_ROWS, fields=None, summary=TPM_SUMMARY):
    return {"stat": "ok", "tables": [{"title": "上櫃股票融資融券餘額", "fields": fields or t3.TPM_FIELDS,
                                      "data": [list(r) for r in rows], "summary": summary}]}


def _by_code(rows):
    return {r["stock_code"]: r for r in rows}


# ─── E1：ETF 定義與分流 ───────────────────────────────────
def test_t01_etf_code():
    for c in ("0050", "00878", "00406A", "00679B", "006201", "00687C", "00631L", "00632R", "00635U", "00625K", "00981T", "00982D"):
        assert is_etf_code(c) and not is_valid_stock_code(c), c
    # ETN（02）、受益證券（01）、TDR（91）、特別股、權證、股票都不是 ETF
    for c in ("020000", "02001L", "01001T", "910322", "912000", "1101B", "2881A", "710000", "73000U", "2330", "6467", "0050123"):
        assert not is_etf_code(c), c
    assert is_valid_stock_code("2330") and not is_valid_stock_code("1101B") and not is_valid_stock_code("910322")


def test_t02_quotes_split():
    # 上市：股票只有 2330；ETF 是 0050、00406A、00666R（無成交）、00878；其他證券兩邊都不收
    data = {"stat": "OK", "tables": [{"fields": MI_FIELDS_REAL, "data": MI_ROWS}]}
    with mock.patch.object(daily, "request", lambda *a, **k: data):
        stocks, taiex, raw = daily.fetch_twse_daily(D(11, 3))
    assert [r["stock_code"] for r in stocks] == ["2330"] and stocks[0]["change"] == -35.0 and taiex is None
    etfs = _by_code(daily.parse_etf_quotes(raw, "TWSE"))
    assert sorted(etfs) == ["00406A", "0050", "00666R", "00878"]
    e = etfs["0050"]
    assert (e["close_price"], e["change"], e["volume"], e["trade_value"], e["trade_count"]) == (100.6, -3.5, 302407473, 30759303345, 732782)
    assert etfs["00878"]["close_price"] == 33.87 and etfs["00878"]["change"] == -0.93
    assert etfs["00406A"]["close_price"] == 7.98 and etfs["00406A"]["change"] == 0.0 and etfs["00406A"]["stock_name"] == "主動中信台灣收益"
    assert etfs["00666R"]["close_price"] is None
    # 上櫃
    tdata = {"stat": "ok", "tables": [{"fields": DQ_FIELDS_REAL, "data": DQ_ROWS}]}
    with mock.patch.object(daily, "request", lambda *a, **k: tdata):
        stocks, none, raw = daily.fetch_tpex_daily(D(11, 3))
    assert [r["stock_code"] for r in stocks] == ["3105"] and none is None
    etfs = _by_code(daily.parse_etf_quotes(raw, "TPEx"))
    assert sorted(etfs) == ["006201", "00679B"]
    assert (etfs["00679B"]["close_price"], etfs["00679B"]["change"], etfs["00679B"]["volume"], etfs["00679B"]["trade_value"]) == \
        (26.54, 0.14, 37322231, 990372248)
    assert etfs["006201"]["change"] == -3.1
    # 有股票列卻沒有 ETF 列 → SchemaError（只影響 etf.*）；休市回傳空
    try:
        daily.parse_etf_quotes(({}, []), "TWSE")
        raise AssertionError("沒有 ETF 列要丟 SchemaError")
    except SchemaError:
        pass
    with mock.patch.object(daily, "request", lambda *a, **k: {"stat": "很抱歉，沒有符合條件的資料!"}):
        assert daily.fetch_twse_daily(D(11, 3)) == ([], None, ({}, []))


# ─── B2：融資融券解析 ─────────────────────────────────────
def test_t03_parse_twse_margin():
    rows, total = daily.parse_twse_margin(_tw_margin())
    assert total == {"margin_prev": 9571090, "margin_balance": 9482839, "short_prev": 194930, "short_balance": 257961,
                     "amount_prev": 622699365, "amount_balance": 599774466}
    r = _by_code(rows)
    assert r["2303"] == {"stock_code": "2303", "margin_buy": 6108, "margin_sell": 16355, "margin_redeem": 350, "margin_prev": 157064,
                         "margin_balance": 146467, "margin_limit": 3142523, "short_sell": 258, "short_buy": 574, "short_redeem": 104,
                         "short_prev": 1292, "short_balance": 872, "short_limit": 3142523, "offset_lots": 145, "note": None}
    assert r["2303"]["margin_balance"] - r["2303"]["margin_prev"] == -10597
    assert (r["2236"]["note"], r["2414"]["note"], r["1589"]["note"]) == ("@", "X", "OX!")
    assert r["00406A"]["short_balance"] - r["00406A"]["short_prev"] == 65270
    assert len(rows) == 8        # 股票、ETF、TDR 都在；分流由呼叫端做
    # 無法解析的限額 → None；餘額無法解析 → 略過該列
    bad = [list(x) for x in TW_MARGIN_ROWS]
    bad[4][7] = "N/A"
    bad[5][6] = ""
    rows, _ = daily.parse_twse_margin(_tw_margin(bad))
    assert _by_code(rows)["2303"]["margin_limit"] is None and "2376" not in _by_code(rows)
    # 未公布 → 官方尚無資料
    assert daily.parse_twse_margin({"stat": "很抱歉，沒有符合條件的資料!"}) == ([], None)
    assert daily.parse_twse_margin(_tw_margin(rows=[])) == ([], None)
    # 改版：欄名、groups、統計表
    for kw in ({"fields": t3.MGN_FIELDS[:6] + ["改名"] + t3.MGN_FIELDS[7:]},
               {"groups": [{"title": "股票", "span": 2}, {"title": "融券", "span": 6}, {"title": "融資", "span": 6}]},
               {"total": False}):
        try:
            daily.parse_twse_margin(_tw_margin(**kw))
            raise AssertionError(f"要丟 SchemaError：{kw}")
        except SchemaError:
            pass


def test_t04_parse_tpex_margin():
    rows, total = daily.parse_tpex_margin(_tp_margin())
    assert total == {"margin_prev": 2308903, "margin_balance": 2269312, "short_prev": 36704, "short_balance": 38371,
                     "amount_prev": 204410217, "amount_balance": 196562898}
    r = _by_code(rows)
    assert r["3105"] == {"stock_code": "3105", "margin_buy": 2464, "margin_sell": 2093, "margin_redeem": 2, "margin_prev": 42425,
                         "margin_balance": 42794, "margin_limit": 105985, "short_sell": 912, "short_buy": 428, "short_redeem": 0,
                         "short_prev": 1413, "short_balance": 1897, "short_limit": 105985, "offset_lots": 7, "note": None}
    assert r["2035"]["note"] == "11OX   C" and r["00679B"]["margin_balance"] == 4860
    # summary 是字串化陣列也接受（分析師描述的格式）
    assert daily.parse_tpex_margin(_tp_margin(summary=json.dumps(TPM_SUMMARY, ensure_ascii=False)))[1] == total
    assert daily.parse_tpex_margin({"stat": "ok", "tables": [{"fields": t3.TPM_FIELDS, "data": []}]}) == ([], None)
    for kw in ({"fields": ["改名" if f == "資餘額" else f for f in t3.TPM_FIELDS]}, {"summary": []}):
        try:
            daily.parse_tpex_margin(_tp_margin(**kw))
            raise AssertionError(f"要丟 SchemaError：{kw}")
        except SchemaError:
            pass


def test_t05_ratios():
    assert export.usage(13571, 15879) == 85.46            # 2236（截斷，不是四捨五入的 85.47）
    assert export.usage(42794, 105985) == 40.37           # 3105，與櫃買官方欄位相同
    assert export.usage(5, 0) is None and export.usage(5, None) is None      # 停資（限額 0）
    assert export.short_ratio(2281, 6774) == 33.67        # 2376
    assert export.short_ratio(129630, 6345620) == 2.04    # 上市股票合計
    assert export.short_ratio(1, 0) is None


def test_t06_maint_ratio():
    series = [(D(10, 30), 10), (D(11, 2), None), (D(11, 3), 12)]
    assert export.last_close(series, D(11, 2)) == 10.0 and export.last_close(series, D(11, 3)) == 12.0
    assert export.last_close(series, D(10, 29)) is None
    # 990 張有收盤、10 張沒有：涵蓋率 99%，剛好可以顯示
    mr, cov = export.maint_ratio([(500, 100.0), (490, 50.0), (10, None)], 1000, 60000)
    assert cov == 99.0 and mr == round((500 * 100 + 490 * 50) / 60000 * 100, 2) == 124.17
    assert export.maint_ratio([(989, 100.0), (11, None)], 1000, 60000) == (None, 98.9)       # < 99% → 資料不足
    assert export.maint_ratio([(1, 1.0)], 0, 1)[0] is None and export.maint_ratio([(1, 1.0)], 1, 0)[0] is None


def test_t07_stock_margin():
    d1, d6 = D(10, 27), D(11, 3)
    rows = {d1: (100, 120, 1000, 5, 6, None), d6: (150, 140, 1000, 6, 9, "X")}
    assert export.stock_margin(rows, d6, d1) == {"d": "2026-11-03", "mb": 140, "m1": -10, "m5": 20, "sb": 9, "s1": 3,
                                                  "sr": 6.43, "mu": 14.0, "nt": "X"}
    assert export.stock_margin(rows, d6, None)["m5"] is None              # 不足 6 個融資融券日
    assert export.stock_margin({d6: (0, 0, 0, 0, 0, "OX")}, d6, d1) == {"d": "2026-11-03", "mb": 0, "m1": 0, "m5": None, "sb": 0, "s1": 0,
                                                                        "sr": None, "mu": None, "nt": "OX"}
    assert export.stock_margin(rows, D(11, 4), d6) is None                # 不在信用交易清單


def test_t08_market_margin():
    d1, d2 = D(11, 2), D(11, 3)
    official = {d1: (0, 1000, 0, 50, 0, 60000), d2: (1000, 900, 50, 80, 60000, 45000)}
    stocks = {d1: [("A", 0, 500, 0, 20)], d2: [("A", 500, 450, 20, 30), ("B", 0, 0, 0, 0)]}
    etfs = {d1: [("E", 0, 500, 0, 30)], d2: [("E", 500, 440, 30, 50)]}
    px = {("A", d1): 100, ("A", d2): 90, ("E", d1): 20, ("E", d2): 18}
    close = lambda code, day, is_etf: px.get((code, day))
    m = export.market_margin([d1, d2], official, stocks, etfs, close)
    # 頭條只有股票；ETF 另計；維持率分子股票＋ETF、分母官方金額
    assert (m["mb"], m["m1"], m["mp"], m["sb"], m["s1"], m["sp"], m["sr"]) == (450, -50, -10.0, 30, 10, 50.0, 6.67)
    assert m["etf"] == {"mb": 440, "m1": -60, "sb": 50, "s1": 20}
    assert (m["amt"], m["amt1"]) == (0.5, -0.1)
    assert m["cov"] == 98.89 and m["mr"] is None          # 官方 900 張只涵蓋 890 張（< 99%）→ 資料不足
    assert m["mr0"] == round((500 * 100 + 500 * 20) / 60000 * 100, 2) == 100.0
    assert m["d20"] == ["2026-11-02", "2026-11-03"] and m["m20"] == [500, -50]
    assert export.market_margin([], {}, {}, {}, close) is None


def test_t09_etf_block():
    latest = {"TWSE": (D(11, 3), [("0050", "元大台灣50", 100.6, -3.5, 302407473, 30759303345),
                                  ("00666R", "富邦恒生國企反1", None, 0, 1, 9)]),
              "TPEx": (D(11, 3), [("00679B", "元大美債20年", 26.54, 0.14, 37322231, 990372248)])}
    b = export.etf_block(latest, {"0050": (27431, 28986, 228, 227)})
    assert b["dates"] == {"TWSE": "2026-11-03", "TPEx": "2026-11-03"}
    assert b["rows"]["0050"] == {"n": "元大台灣50", "m": "TWSE", "c": 100.6, "ch": -3.5, "p": -3.36, "v": 302407, "tv": 307.59,
                                 "mb": 28986, "m1": 1555, "sb": 227, "s1": -1}
    assert b["rows"]["00666R"]["c"] is None and b["rows"]["00666R"]["p"] is None and "mb" not in b["rows"]["00666R"]
    assert b["rows"]["00679B"]["m"] == "TPEx" and export.etf_block({}, {}) is None


# ─── E1／B2：真實流程（假的 HTTP 與資料庫）─────────────────
def test_t10_new_day_same_requests():
    # E1-6：新的一天，行情請求數與修改前相同（各 1 次），同時寫入股票與 ETF；融資融券各 1 次
    w = World(D(10, 30))
    w.publish(t3.FIRST_DAY)
    rc, out = run_world(w, T(11, 2, 22, 30))
    assert rc == 0 and "Traceback" not in out
    assert len(t3._hit(w, "MI_INDEX")) == 1 and len(t3._hit(w, "dailyQuotes")) == 1
    assert len(t3._hit(w, "MI_MARGN")) == 1 and len(t3._hit(w, "margin/balance")) == 1
    d = t3.FIRST_DAY
    assert w.rows["prices.TWSE"][d].n == 1100 and w.rows["prices.TPEx"][d].n == 900       # ETF、其他證券沒有混進股票
    assert w.rows["etf.TWSE"][d].n == 250 and w.rows["etf.TPEx"][d].n == 120
    assert w.rows["margin.TWSE"][d].n == 1100 and w.rows["margin.TPEx"][d].n == 900        # 只有股票列
    assert {"etfs", "etf_daily", "etf_margin", "margin_market"} <= set(w.merges)


def test_t11_only_etf_missing():
    # E1-6：股票行情已齊、只缺 ETF：每市場 1 次請求，不寫股票列、不更新 stocks
    w = World(D(10, 30))
    for k in ("etf.TWSE", "etf.TPEx"):
        del w.rows[k][D(10, 30)]
    w.published["MI_INDEX"].add(D(10, 30))
    w.published["dailyQuotes"].add(D(10, 30))
    rc, out = run_world(w, T(10, 31, 12, 0))
    assert rc == 0 and sorted(w.paths()) == ["/rwd/zh/afterTrading/MI_INDEX", "/www/zh-tw/afterTrading/dailyQuotes"]
    assert sorted(set(w.merges)) == ["etf_daily", "etfs"]
    assert w.rows["etf.TWSE"][D(10, 30)].n == 250


def test_t12_no_etf_rows():
    # E1-7：行情回應沒有任何 ETF 列：只有 etf.* 異常，股票行情照常寫入，沒有 Traceback
    w = World(D(10, 30))
    w.publish(t3.FIRST_DAY)
    w.no_etf = True
    rc, out = run_world(w, T(11, 2, 18, 0))
    assert rc == 1 and "Traceback" not in out and "❌ 上市ETF" in out and "❌ 上櫃ETF" in out
    assert w.rows["prices.TWSE"][t3.FIRST_DAY].n == 1100 and w.rows["margin.TWSE"][t3.FIRST_DAY].n == 1100
    assert len(t3._hit(w, "MI_INDEX")) == 1                     # 失敗也不重打同一個回應
    assert set(k.split(":")[0] for k in w.notices[0]) == {"etf.TWSE", "etf.TPEx"}


def test_t13_margin_not_yet():
    # B2-11 #1：11/04 17:30 行情已有、融資融券未公布 → 尚未公布，rc=0；下次只抓融資融券
    w = World(D(11, 3))
    w.publish(D(11, 4), "MI_MARGN", "margin/balance")
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 上市融資融券：2026-11-04 尚未公布" in out and "⏳ 上櫃融資融券：2026-11-04 尚未公布" in out
    w.requests.clear()
    w.published["MI_MARGN"].add(D(11, 4))
    w.published["margin/balance"].add(D(11, 4))
    rc, out = run_world(w, T(11, 4, 18, 30))            # 18:30：處置／注意股 17:30 已抓過，19:00 前不重抓
    assert rc == 0 and sorted(w.paths()) == ["/rwd/zh/marginTrading/MI_MARGN", "/www/zh-tw/margin/balance"]


def test_t14_margin_deadline_notify_once():
    # B2-11 #2、S11-3：21:45 未公布 → 尚未公布、不通知；22:30 仍未公布 → 異常、通知一次；同日再跑不重複通知
    w = World(D(11, 3))
    w.publish(D(11, 4), "MI_MARGN", "margin/balance")
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(health, "NOTIFY_FILE", Path(tmp) / "notify.json"), \
            mock.patch.object(health.sys, "platform", "darwin"), mock.patch.object(health.subprocess, "run") as osa:
        def go(hh, mm):
            buf = io.StringIO()
            with env(w), mock.patch.object(health, "notify_once", REAL_NOTIFY), contextlib.redirect_stdout(buf):
                return catchup.run(now=T(11, 4, hh, mm), notify=True), buf.getvalue()
        rc, out = go(21, 45)
        assert rc == 0 and osa.call_count == 0 and "尚未公布" in out
        rc, out = go(22, 30)
        assert rc == 1 and osa.call_count == 1 and "❌ 上市融資融券" in out
        assert "上市融資融券" in osa.call_args[0][0][2]
        rc, out = go(22, 40)
        assert rc == 1 and osa.call_count == 1                  # 同一天同一問題只通知一次


def test_t15_no_margin_request_without_prices():
    # B2-11 #3：當日行情還沒有 → 不發融資融券請求；#4：休市日 → 不發
    w = World(D(11, 3))
    w.published["MI_MARGN"].add(D(11, 4))
    w.published["margin/balance"].add(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and t3._hit(w, "MI_INDEX") and not t3._hit(w, "MI_MARGN", "margin/balance")
    w = World(D(12, 24))
    rc, out = run_world(w, T(12, 25, 22, 30))
    assert rc == 0 and not t3._hit(w, "MI_INDEX", "MI_MARGN", "margin/balance")


def test_t16_margin_schema_change():
    # B2-11 #6：欄位改名 → --catch-up 只有融資融券異常、其他照常；history --only margin 停下、印欄位不符；都沒有 Traceback
    for ep, label in (("MI_MARGN", "上市融資融券"), ("margin/balance", "上櫃融資融券")):
        w = World(D(10, 30))
        w.publish(t3.FIRST_DAY)
        w.renamed.add(ep)
        rc, out = run_world(w, T(11, 2, 18, 0))
        assert rc == 1 and "Traceback" not in out and f"❌ {label}" in out, ep
        assert {k.split(":")[0] for k in w.notices[0]} == {"margin.TWSE" if ep == "MI_MARGN" else "margin.TPEx"}, ep
        assert w.rows["insti.TPEx"][t3.FIRST_DAY].n == 900 and w.rows["etf.TWSE"][t3.FIRST_DAY].n == 250, ep
        w.requests.clear()
        buf = io.StringIO()
        with env(w), contextlib.redirect_stdout(buf):
            assert history.run_history(D(10, 28), t3.FIRST_DAY, ("margin",)) is False
        assert "官方欄位不符" in buf.getvalue() and "Traceback" not in buf.getvalue(), ep


def test_t17_history_order_and_rerun():
    # --only margin etf：同一天一律 ETF 行情先於融資融券（ETF 融資融券列只寫入 etfs 已有的 ETF）；重跑請求 0 次
    days = [D(10, 29), D(10, 30)]
    w = World(D(10, 30))
    for d in days:
        w.publish(d)
        for k in ("etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"):
            del w.rows[k][d]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[1], ("margin", "etf")) is True
    out = buf.getvalue()
    assert "待抓 2 天" in out and "預估約 0.3 分鐘" in out      # (4 + 1 + 4 + 0.5) 秒 × 2 天
    eps = [p.rsplit("/", 1)[-1] for p in w.paths()]
    assert eps == ["MI_INDEX", "dailyQuotes", "MI_MARGN", "balance"] * 2
    assert [f["date"] for p, f in w.requests if "MI_INDEX" in p] == ["20261029", "20261030"]
    w.requests.clear()
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(days[0], days[1], ("etf", "margin")) is True
    assert "待抓 0 天" in buf.getvalue() and w.requests == []
    # 同一天也要抓行情時，ETF 共用回應，不另計時
    assert history.day_seconds(("prices.TWSE", "etf.TWSE")) == 4 and history.day_seconds(("etf.TWSE", "margin.TWSE")) == 8


# ─── S10 核心：check 開頭、全缺合併、建議指令 ─────────────
STATE = {"alerts_at": datetime(2026, 10, 31, 13, 38), "events_to": D(10, 30), "revenue_on": D(10, 31), "collected_at": None,
         "last_run": {"at": datetime(2026, 10, 31, 13, 38), "command": "catch-up", "new_data": True}}


def test_t18_check_whole_day_missing():
    # S10-1：現在 11/03 10:00、資料到 10/30、最後一次收集 10/31 13:38、11/02 全部缺 → 開頭兩行、11/02 一行、建議指令、rc=1
    now = T(11, 3, 10, 0)
    days = health.due_days(now, 20, CLOSED)
    assert days[-1] == D(11, 2)
    snap = t3._full_snapshot(days[:-1])
    with mock.patch.object(fetch._SESSION, "request") as http, mock.patch.object(db, "connect") as conn:
        text, rc = health.check_report(days, snap, now, STATE, CLOSED, schedule="未安裝（安裝方式見 README，由使用者自行執行）")
    assert rc == 1 and http.call_count == 0 and conn.call_count == 0
    lines = text.splitlines()
    assert lines[1] == "🕘 最後一次收集：2026-10-31 13:38（collect --catch-up，有新資料）"
    assert lines[2] == "🗓️  排程：未安裝（安裝方式見 README，由使用者自行執行）"
    bad = [ln for ln in lines if ln.startswith("❌")]
    assert bad == ["❌ 2026-11-02 全部資料集都沒有：最後一次收集是 10/31 13:38，之後沒有執行收集"]
    assert lines[-1] == "👉 請執行 python3 -m twstock collect --catch-up" and "異常 1 項" in text
    # 有收集過但仍全缺（例如被限流）：說明不同
    state = dict(STATE, last_run={"at": datetime(2026, 11, 2, 21, 45), "command": "catch-up", "new_data": False})
    text, _ = health.check_report(days, snap, now, state, CLOSED)
    assert "❌ 2026-11-02 全部資料集都沒有：最後一次收集 11/02 21:45 也沒有取得" in text and "🗓️" not in text
    # 缺口超過 --catch-up 預設 10 天：建議加 --days；超過 30 天：建議 history
    text, _ = health.check_report(days, t3._full_snapshot(days[:-12]), now, STATE, CLOSED)
    assert text.splitlines()[-1] == "👉 請執行 python3 -m twstock collect --catch-up --days 12"
    days40 = health.due_days(now, 40, CLOSED)
    text, _ = health.check_report(days40, t3._full_snapshot(days40[:-35]), now, STATE, CLOSED)
    assert text.splitlines()[-1] == f"👉 請執行 python3 -m twstock history --start {days40[-35]}，再執行 python3 -m twstock collect --catch-up"


def test_t19_check_partial_pending():
    # S10-2：11/03 21:00 只有上市法人缺：不合併、逐項顯示尚未公布，rc=0，沒有建議指令
    now = T(11, 3, 21, 0)
    days = health.due_days(now, 20, CLOSED)
    snap = t3._full_snapshot(days, skip={("insti.TWSE", D(11, 3))})
    state = dict(STATE, alerts_at=datetime(2026, 11, 3, 19, 30))
    text, rc = health.check_report(days, snap, now, state, CLOSED)
    assert rc == 0 and "⏳ 上市法人：2026-11-03 尚未公布" in text and "全部資料集" not in text and "👉" not in text
    # 第 4 輪的資料集在 check 表格中
    for label in ("上市ETF", "上櫃ETF", "上市融資融券", "上櫃融資融券"):
        assert label in text, label


def test_t20_schedule_status_readonly():
    # S10-3：只看檔案是否存在，不呼叫 subprocess
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(subprocess, "run", side_effect=AssertionError("不可呼叫")), \
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("不可呼叫")):
        assert health.schedule_status("darwin", tmp) == "未安裝（安裝方式見 README，由使用者自行執行）"
        plist = Path(tmp) / "Library/LaunchAgents/com.twstock.collect.plist"
        plist.parent.mkdir(parents=True)
        plist.write_text("x")
        assert health.schedule_status("darwin", tmp).startswith("已安裝（")
        assert health.schedule_status("win32", tmp) == "無法判斷，請在工作排程器確認"
        assert health.last_run_line(None) == "尚無執行紀錄"


def test_t21_load_state_compat():
    # load_state 多讀 command；相容只有 3 欄的舊假資料
    class Cur:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, *a):
            return self

        def fetchall(self):
            return self.rows
    detail = json.dumps({"undated": {}})
    s = health.load_state(Cur([(datetime(2026, 11, 3, 20, 52), 1, detail, "catch-up")]))
    assert s["last_run"] == {"at": datetime(2026, 11, 3, 20, 52), "command": "catch-up", "new_data": True}
    s = health.load_state(Cur([(datetime(2026, 11, 3, 21, 45), 0, detail), (datetime(2026, 11, 3, 20, 52), 1, detail)]))
    assert s["last_run"]["new_data"] is False and s["last_run"]["command"] is None and s["collected_at"] == datetime(2026, 11, 3, 20, 52)
    assert health.load_state(Cur([]))["last_run"] is None


def test_t22_qa04_history_schema():
    # QA-04：櫃買指數、融資融券、ETF 行情欄位不符時，history 印欄位不符並回傳失敗，沒有 Traceback
    class Renamed(World):
        def _inx(self, form):
            return t3.Resp({"stat": "ok", "tables": [{"fields": ["改名"] + t3.INX_FIELDS[1:], "data": [["2026/09/30"] + ["1"] * 5]}]})
    w = Renamed(D(10, 30))
    del w.rows["index.TPEX"][D(10, 30)]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(10, 30), D(10, 30), ("tpex_index",)) is False
    assert "官方欄位不符" in buf.getvalue() and "indexInfo/inx 欄位不符" in buf.getvalue()
    w = World(D(10, 30))
    w.no_etf = True
    w.publish(D(10, 30))
    del w.rows["etf.TWSE"][D(10, 30)]
    buf = io.StringIO()
    with env(w), contextlib.redirect_stdout(buf):
        assert history.run_history(D(10, 30), D(10, 30), ("etf",)) is False
    assert "官方欄位不符" in buf.getvalue() and "沒有任何 ETF 列" in buf.getvalue()
    # 透過 CLI：回傳 1
    with env(w), contextlib.redirect_stdout(io.StringIO()):
        assert cli.main(["history", "--start", "2026-10-30", "--end", "2026-10-30", "--only", "etf"]) == 1


def test_t23_qa06_check_days():
    for bad in ("0", "-5"):
        buf = io.StringIO()
        with mock.patch.object(db, "connect", side_effect=AssertionError("不可連資料庫")), contextlib.redirect_stdout(buf):
            assert cli.main(["check", "--days", bad]) == 1, bad
        assert "--days 至少 1" in buf.getvalue()


# ─── S11：排程 22:30（只讀檔、只執行 --print）─────────────
def test_t24_schedule_2230():
    sh = (ROOT / "scripts/mac/install_schedule.sh").read_text(encoding="utf-8")
    assert '"22 30"' in sh and "22:30" in sh
    bat = (ROOT / "scripts/windows/install_schedule.bat").read_text(encoding="utf-8")
    assert "/ST 22:30" in bat and "schtasks /Delete /TN %TASK%2230 /F" in bat and bat.count("schtasks /Create") == 4
    if shutil.which("bash"):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(ROOT / "scripts/mac/install_schedule.sh"), "--print"], capture_output=True, text=True,
                               timeout=30, env={"HOME": tmp, "PATH": "/usr/bin:/bin"})
            assert r.returncode == 0 and not list(Path(tmp).iterdir())      # 沒有寫任何檔案
            plist = plistlib.loads(r.stdout.encode())
            times = {(x["Hour"], x["Minute"]) for x in plist["StartCalendarInterval"]}
            assert len(plist["StartCalendarInterval"]) == 20 and times == {(17, 30), (19, 30), (21, 45), (22, 30)}
            assert plist["RunAtLoad"] is True and "--notify" in plist["ProgramArguments"]
    assert health.DEADLINE.hour == 22 and health.DEADLINE.minute == 0         # DEADLINE 維持 22:00


# ─── S10 橫幅（node 跑 app.js 真正的 freshLines；沒有 node 略過）────
def test_t25_banner_text():
    latest = {"date": "2026-10-30", "status": {"closed": [], "datasets": []}}
    lines = t3.fresh_lines(latest, "2026-11-02T18:30:00+08:00")
    assert lines is None or lines == [["資料停在 10/30，最新交易日為 11/02，可能尚未收集。請在收集資料的電腦執行 python3 -m twstock collect --catch-up"]]


def test_t26_specs_and_keys():
    keys = [s.key for s in health.SPECS]
    assert keys[-4:] == ["etf.TWSE", "etf.TPEx", "margin.TWSE", "margin.TPEx"]
    assert daily.DAY_KEYS.index("etf.TWSE") < daily.DAY_KEYS.index("margin.TWSE")
    assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
    assert daily.ALL_DATASETS == ("prices", "pe", "insti", "etf", "margin")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print("全部通過")
```

## 附錄 E：PG 執行用的 `logs/` 小工具（`logs/` 已在 `.gitignore`，不是程式修改）

### `logs/iter04_history.py`（補抓並保存 QA 要的原始回應，不多發請求）

```python
"""
第 4 輪一次性補抓：等同 python3 -m twstock history --start 2025-10-30 --only etf margin，
另外把 QA 要比對的原始回應在「本來就要抓」的那一次順手存到 logs/（不多發請求）：
  2025-10-30 上市 MI_MARGN、上櫃 margin/balance（驗收 B2-7）；2026-11-03 上市 MI_INDEX、上櫃 dailyQuotes（驗收 E1-4）
用法（專案根目錄）：python3 logs/iter04_history.py 2>&1 | tee -a logs/iter04_history.log
中斷或被限流時用同一指令重跑：只補缺的；已存的原始回應不會被刪除。
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from twstock import __main__ as cli  # noqa: E402
from twstock import fetch  # noqa: E402
from twstock.collectors import daily  # noqa: E402

KEEP = {("MI_MARGN", "20251030"), ("margin/balance", "2025/10/30"), ("MI_INDEX", "20261103"), ("dailyQuotes", "2026/11/03")}
_real = daily.request


def saving(method, url, **kw):
    data = _real(method, url, **kw)
    when = (kw.get("params") or kw.get("data") or {}).get("date")
    for ep, d in KEEP:
        if ep in url and when == d:
            out = ROOT / "logs" / f"iter04_raw_{ep.replace('/', '_')}_{d.replace('/', '')}.json"
            out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            print(f"  💾 已保存原始回應 {out.name}")
    return data


if __name__ == "__main__":
    daily.request = saving
    t0 = time.monotonic()
    rc = cli.main(["history", "--start", "2025-10-30", "--only", "etf", "margin"])
    print(f"🌐 外部請求 {fetch.request_count()} 次，耗時 {(time.monotonic() - t0) / 60:.1f} 分鐘（rc={rc}）")
    sys.exit(rc)
```

### `logs/iter04_compare.py`（E1-8 隔離比對）

```python
"""
E1-8 隔離比對：python3 logs/iter04_compare.py logs/iter04_before site/data
  before：修改程式前以舊程式匯出後複製的 latest.json 與 stocks/；after：修改後的匯出（site/data）。
latest.json 除了 status、margin、etfs 之外每個鍵完全相同；stocks/*.json 檔案集合相同、除了 margin 之外完全相同。
另印成交額前 10 名（排行頁「成交額」的母體 = latest.json 的 stocks，依 tv 由大到小）。完全相同 → rc 0。
"""
import json
import sys
from pathlib import Path

NEW_LATEST, NEW_STOCK = {"status", "margin", "etfs"}, {"margin"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(before, after):
    before, after, bad = Path(before), Path(after), []
    a, b = load(before / "latest.json"), load(after / "latest.json")
    for k in sorted((set(a) | set(b)) - NEW_LATEST):
        if a.get(k) != b.get(k):
            bad.append(f"latest.json 的 {k} 不同")
    top = lambda L: [c for c, _ in sorted(L["stocks"].items(), key=lambda x: -(x[1].get("tv") or 0))[:10]]
    print("成交額前 10：", top(a), "→", "相同" if top(a) == top(b) else f"不同 {top(b)}")
    fa = {p.name for p in (before / "stocks").glob("*.json")}
    fb = {p.name for p in (after / "stocks").glob("*.json")}
    if fa != fb:
        bad.append(f"stocks/ 檔案集合不同：少 {sorted(fa - fb)[:10]}，多 {sorted(fb - fa)[:10]}")
    for name in sorted(fa & fb):
        x, y = load(before / "stocks" / name), load(after / "stocks" / name)
        diff = sorted(k for k in (set(x) | set(y)) - NEW_STOCK if x.get(k) != y.get(k))
        if diff:
            bad.append(f"stocks/{name} 的 {'、'.join(diff)} 不同")
    print(f"latest.json 比對 {len(set(a) - NEW_LATEST)} 個鍵、stocks {len(fa & fb)} 檔")
    print("\n".join(bad[:30]) if bad else "✅ 完全相同（不含 status、margin、etfs）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
```
