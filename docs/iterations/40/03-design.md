# 第 40 輪｜SA：設計

- 撰寫日期：2026-11-21（週六）
- 依據：
  - `40/01-analyst.md`：F40-1～F40-5、R29～R34、Q40-1～Q40-10。
  - `40/02-pm.md`：F40-1～F40-3、驗收 1～21。
  - 使用者決定：D86 = A、D86-1～D86-7 = A、D87 = A；PM 自行決定的四項照預設（`--date`／`events` 不抓、過期只 ⚠️、超過 6 位小數不帶入、ETF 寫「以發行人公告為準」）。
- 做法：
  - 在 scratchpad 建兩份副本 `r40sa/base`（原樣）、`r40sa/proj`（修改）。副本不含 `.git`、`.env`、`logs/`、`output/`，`site/data` 用符號連結（唯讀）。
  - 在 `proj` 實作、跑測試；用 `git diff --no-index base proj` 產出 `40/03-design.diff`（1,026 行）。
  - 驗證：
    - 正式專案 `git apply --check docs/iterations/40/03-design.diff` 通過。
    - 另複製一份 `base`，套用這份 diff 後和 `proj` 逐檔比對，結果相同。
    - 套用後的副本跑 `test_iter01～40`，40 個全部通過。
  - 解析測試用的是分析師存下的真實回應（`r40/twse.json`、`r40/tpex.json`，只讀）。從中選出節錄內嵌在測試裡，測試本身不讀 scratchpad。
- 守則：
  - 外部請求 0 次、資料庫 0 次（副本也沒有連線）、`export` 0 次。
  - 沒有啟動伺服器（8000／8001／8002 都沒開）。
  - 沒有讀出或複製 `.env`。
  - 正式專案只新增 `docs/iterations/40/03-design.md`、`03-design.diff`，沒有改程式、測試、`site/`。

---

## 重點摘要

- **舊測試一行都不用改**：`test_iter01～39` 全部照過。
  - PM 提到的「排了 `events` 的舊收集測試會多 2 次請求」實際有 **33 個測試函式**（清單見第四節）。
  - 這些測試全部照過，原因是假 World 對不認得的網址，證交所回 `{"stat": "沒有資料", "tables": []}`、openapi 回 `[]`。設計把這兩種都解析成「0 筆、成功」，0 筆時不連資料庫，所以不會出錯。
  - 這些測試都沒有比對「請求總數」或 `undated` 全等，所以多出的請求不影響結果。
- 為了不改舊測試，有 3 處和 PM 寫法不同（詳見第八節）：
  1. `check` 的新一行放在「最後一次收集的警告」之後，不是緊接在事件那行之下。平常沒有警告時，看起來仍然是事件的下一行（D88）。
  2. `etf_export` 不加參數。ETF 的 `nx` 改在 `export_all` 呼叫 `etf_export` 之後才附加，位置仍是最後一個鍵。
  3. `setup-db` 的提示把 `dividend_notices（第 40 輪）` 放在 `etf_holding_gaps` 之前。
- 新檔 `twstock/collectors/notices.py`（95 行），`events.py` 不改：
  - 解析是純函式（`parse_notices`），測試用真實節錄比對。
  - `fetch_notices` 用 `request(..., isolated=True)`。
  - `collect_notices` 做 MERGE：只收 `stocks`、`etfs` 已有的代號；`first_seen` 只在新增時寫；不刪除任何列。
- 匯出用純函式 `notice_export`，和 `build_status` 共用同一次 `load_state` 結果，只多一個 SELECT。
- 前端：
  - `tools.js` 新增 `tlNx`，修改 `tlDvLoad`、`tlLoad` 各幾行。
  - `stock.js` 新增 `nxText`，並在 `renderStock` 第 39 輪那兩行之後加 1 行 DOM 插入。
  - `divHTML`、`tlDvOut`、`tlBig`、`tlDtOut` 都一字不改。
- 新測試 `test_iter40`：14 個測試，其中反證 20 種（Python 13 種、JS 7 種），全部擋下。
- 新決策 D88～D90，建議都選 A，設計已照 A 做。

## 一、資料表（`db.py` 的 `DDL` 新增一段，`setup-db` 可重複執行）

```sql
IF OBJECT_ID('dividend_notices') IS NULL
CREATE TABLE dividend_notices (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    code         NVARCHAR(10)  NOT NULL,   -- 股票或 ETF 代號（寫入時只收 stocks、etfs 表已有的）
    market       NVARCHAR(4)   NOT NULL CHECK (market IN ('TWSE', 'TPEx')),
    is_etf       BIT           NOT NULL,
    ex_date      DATE          NOT NULL,   -- 除權除息日
    event_type   NVARCHAR(4)   NOT NULL CHECK (event_type IN (N'息', N'權', N'權息')),
    cash_div     DECIMAL(16,8) NULL,       -- 每股現金股利；NULL = 待公告
    stock_ratio  DECIMAL(16,8) NOT NULL DEFAULT 0,   -- 每股無償配股率（× 1,000 = 每千股配股）
    sub_ratio    DECIMAL(16,8) NOT NULL DEFAULT 0,   -- 現金增資配股率
    sub_price    DECIMAL(10,2) NULL,       -- 現金增資認購價；尚未公告或沒有現增 = NULL
    first_seen   DATE          NOT NULL,   -- 第一次在預告表看到的抓取日（台灣日期）
    last_seen    DATE          NOT NULL,   -- 最近一次在預告表看到的抓取日
    updated_at   DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_dividend_notices UNIQUE (code, ex_date)
)
```

- 放在 `foreign_holdings` 之後、`stocks.shares` 的 ALTER 之前。
- 不加索引：資料量很小（每晚約 90 列快照，一年約數千列）；匯出只用 `ex_date > 資料日` 一個條件查詢。
- `setup_database()` 結尾的提示字串加上 `dividend_notices（第 40 輪）`。這段字放在 `etf_holding_gaps` 之前，因為 `test_iter06:143` 逐字檢查字串結尾是 `etf_holding_gaps")`。
- `__main__.py` 的 `setup-db` 說明本來就沒有列出各資料表，所以不改。

## 二、收集（F40-1）

### 2-1 `twstock/collectors/notices.py`（新檔）

| 函式 | 內容 |
|---|---|
| `parse_notices(market, data)` | 純函式。輸入官方回應，輸出 `[{code, ex_date, event_type, cash_div, stock_ratio, sub_ratio, sub_price}]`，數值都是 `Decimal`（詳細規則見 2-2） |
| `fetch_notices(market)` | `request("GET", url, isolated=True, params=...)`。上市帶 `params={"response": "json"}`，上櫃不帶參數 |
| `collect_notices(market, seen)` | 抓一個市場的預告表並 MERGE，回傳解析後的筆數。`seen` 是抓取日（`now.date()`，台灣日期）；0 筆時不連資料庫 |

- 欄位對照表 `_FIELDS`。上櫃的欄位名照官方拼法 `ExRrights…`：

| 用途 | 上市 TWT48U（`fields` 欄名） | 上櫃 `tpex_exright_prepost`（鍵名） |
|---|---|---|
| 除權除息日 | `除權除息日期` | `ExRrightsExDividendDate` |
| 代號 | `股票代號` | `SecuritiesCompanyCode` |
| 類型 | `除權息` | `ExRrightsExDividend` |
| 現金股利 | `現金股利` | `CashDividend` |
| 無償配股率 | `無償配股率` | `StockDividendRatio` |
| 現增配股率 | `現金增資配股率` | `SubscriptionRatioToNewSharesIssued` |
| 認購價 | `現金增資認購價` | `SubscriptionPricePerShare` |

### 2-2 解析規則

| 情況 | 結果 |
|---|---|
| 上市回應不是物件、上櫃回應不是陣列 | `SchemaError` |
| 上市 `stat` 不是 OK，而且沒有 `fields`、`data` | `[]`，算成功（假 World 的「沒有資料」走這條） |
| 上市 `stat` 是 OK，但 `data` 是空的 | `[]` |
| 上市缺少 7 個必要欄位中的任何一個 | `SchemaError` |
| 上櫃是 `[]` | `[]` |
| 上櫃第一列缺少必要的鍵 | `SchemaError` |
| 日期無法解析（`roc_date`，「115年12月03日」和「1151203」都可以解析）、類型不是 息／權／權息 | 略過該列 |
| 上櫃類型「除息／除權／除權息」 | `lstrip("除")`，同 `events.py` 的處理 |
| 代號不是 `is_valid_stock_code`，也不是 `is_etf_code` | 略過，例如 ETN `020038`、受益證券 `01007T` |
| 現金股利解析不了（`<p …>待公告實際收益分配金額</p>`、「尚未公告」） | `None` |
| 無償配股率、現增配股率解析不了 | `Decimal(0)` |
| 認購價：現增配股率是 0，或解析不了（「尚未公告」「註4」） | `None` |
| 同一份回應裡有同鍵（代號, 除權息日） | 只留最後一筆 |

- 數字用 `clean_number(v, Decimal)` 解析，保留官方的 8 位小數。

### 2-3 寫入（MERGE）

```sql
MERGE dividend_notices AS t
USING (
    SELECT j.*, CAST(CASE WHEN et.etf_id IS NULL THEN 0 ELSE 1 END AS BIT) AS is_etf
    FROM OPENJSON(?) WITH (code NVARCHAR(10), ex_date DATE, event_type NVARCHAR(4), cash_div DECIMAL(16,8),
                           stock_ratio DECIMAL(16,8), sub_ratio DECIMAL(16,8), sub_price DECIMAL(10,2)) AS j
    LEFT JOIN stocks st ON st.stock_code = j.code
    LEFT JOIN etfs et ON et.etf_code = j.code
    WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL
) AS s
ON t.code = s.code AND t.ex_date = s.ex_date
WHEN MATCHED THEN UPDATE SET
    market = ?, is_etf = s.is_etf, event_type = s.event_type, cash_div = s.cash_div, stock_ratio = s.stock_ratio,
    sub_ratio = s.sub_ratio, sub_price = s.sub_price, last_seen = ?, updated_at = GETDATE()
WHEN NOT MATCHED THEN
    INSERT (code, market, is_etf, ex_date, event_type, cash_div, stock_ratio, sub_ratio, sub_price, first_seen, last_seen)
    VALUES (s.code, ?, s.is_etf, s.ex_date, s.event_type, s.cash_div, s.stock_ratio, s.sub_ratio, s.sub_price, ?, ?);
```

- 參數依序為：JSON、市場、抓取日、市場、抓取日、抓取日。
- 現金欄以最新快照為準：不用 COALESCE，所以從有值變回 NULL（待公告）時也會跟著更新。
- 傳給 OPENJSON 前，`Decimal` 先轉成 `format(v, "f")` 字串，例如 `0.00000001`。原因：`db.to_json` 會把 Decimal 轉成 float，而 JSON 可能寫成 `1e-08`，OPENJSON 轉 DECIMAL 時會失敗。
- 輸出（每個成功的市場一行，和 PM 格式相同）：
  - `  📅 上市除權除息預告 6 筆（除權息日 2026-11-24 ～ 2026-12-04）`
  - 0 筆時：`  📅 上櫃除權除息預告 0 筆`
- 資料表還沒建（沒有跑 `setup-db`）時會丟出 `pyodbc.Error`。`_guard` 不會接住這個錯誤，所以會走既有的 `_db_failed`：印出「更新程式後請執行一次 setup-db」，回傳 2。這和其他資料表的行為相同。

### 2-4 `catchup.py`

| 位置 | 改動 | 為什麼舊測試不受影響 |
|---|---|---|
| import | `from .notices import collect_notices` | — |
| `make_plan` | 初始 dict 加 `"notices": False`；排 `events` 的同一個 if 裡加 `plan["notices"] = True` | 舊測試只用 `["events"]`、`["revenue"]` 等鍵查值，沒有比對整個 dict |
| `plan_for_date` | 不改（沒有 `notices` 鍵，所以 `--date` 不抓） | — |
| `plan_is_empty` | 不改（`notices` 只會和 `events` 一起出現） | — |
| `execute_plan` | 在 `events` 之後加 5 行：`for mk in ("TWSE", "TPEx") if plan.get("notices") else ():`，每個市場用 `_guard(f"notices.{mk}", …)` 包住；成功時寫 `undated["notices"][mk] = {"on": "YYYY-MM-DD", "n": 筆數}` | 用 `plan.get`，所以 `test_iter09:197`、`test_iter10:229` 自己組的 plan dict 沒有這個鍵也照跑 |
| `_run_locked` | 不改：`undated_errors` 不含 `notices.*`，`_undated_counts` 的表清單不變 | 失敗不算異常、不通知、不改回傳碼；預告有變也不觸發匯出（D86-5） |

- 每晚請求 +2（約 41 → 43）。
- 休市日、同一晚重跑、`collect --date`、`events` 子命令都 +0。`events` 子命令的路徑本來就不經過 `execute_plan`。
- `notices.TWSE` 失敗時記在 `errors`（`collect_runs.detail.errors` 看得到），收集輸出 `  ⚠️  notices.TWSE 失敗：…`。

### 2-5 `health.py`

- `load_state`：
  - 新增 `state["notices"] = {}`。
  - 逐筆讀紀錄（新到舊），用 `setdefault` 記下每個市場第一次遇到的值，也就是最新的 `(抓取日, 筆數)`。
  - 舊格式紀錄（沒有 `notices`）不報錯。
- 新函式 `notices_line(notices, last_day, closed)`，文字和 PM 表格逐字相同：

| 情況 | 文字 |
|---|---|
| 兩邊都有 | `除權除息預告最後成功：上市 2026-11-23（25 筆）、上櫃 2026-11-23（66 筆）` |
| 只有一邊 | `除權除息預告最後成功：上市 2026-11-23（25 筆）、上櫃 尚無紀錄` |
| 都沒有、`state = {}` | `除權除息預告最後成功：尚無執行紀錄` |
| `trading_days(日期 + 1, days[-1], closed)` 長度 ≥ 3 | `上櫃 2026-11-18（66 筆，⚠️ 已 3 個交易日沒有更新）` |

- `check_report`：
  - 在「⚠️ 最後一次收集的警告」那幾行之後加 `out.append(notices_line(state.get("notices"), days[-1], closed))`，見 D88。
  - 這一行不放進 `lines`，所以不算異常、不改回傳碼；`lines[1]`、`lines[2]`、`lines[-1]` 也不變。
- `build_status(cur, data_date, now, state=None)`：加一個選用參數，讓匯出共用已讀的 state。沒有傳入時照舊自己讀，舊呼叫方式（`test_iter03:1187`、`1282`）不變。

## 三、匯出（F40-2，`export.py`）

- 新增 `_num(v)`：`float(v)`；如果是整數就轉成 `int`。效果：`2.60000000` → `2.6`、`7.00000000` → `7`、`0` → `0`。
- 新增純函式 `notice_export(rows, on, today)`，回傳 `({股票代號: nx}, {ETF 代號: nx})`：
  - `rows` 是 SELECT 的結果，`on` 是 `{市場: 最近一次成功的抓取日}`（來自 `state["notices"]`），`today` 是資料日。
  - 只保留同時符合兩個條件的列：`last_seen == on[market]`，而且 `ex_date > today`。
  - 這個規則涵蓋了 PM 列的各種情況：
    - 某個市場這晚抓失敗：`on` 還停在上次成功的日期，所以上次的快照照樣匯出。
    - 預告改了日期：舊日期那列的 `last_seen` 停在舊日，所以不再匯出。
    - 成功但 0 筆：沒有任何列的 `last_seen` 等於這次的日期，所以全部不匯出。
    - 某個市場從沒成功過：`on` 沒有這個市場，所以不匯出。
    - 到了除權息日：不再匯出，改看 `dv`／`ev`。
  - 每筆輸出 `{"d", "t", "c"}`：
    - `c` 是 `null` 時代表待公告，和 `0` 分得開。
    - `s` = `stock_ratio × 1000`，只在大於 0 時才有。
    - `sr`、`sp` 只在 `sub_ratio` 大於 0 時才有；`sp` 可以是 `null`。
  - 依除權息日由舊到新排序。
- `export_all` 的接線：
  - `state = load_state(cur)` → `build_status(cur, latest_date, now, state)`。
  - 只多一個查詢：`SELECT … FROM dividend_notices WHERE ex_date > ?`，在同一個連線上執行。
  - 個股 dict 在 `"dv"` 之後加 `**({"nx": nx_stock[code]} if code in nx_stock else {})`。
  - ETF 在 `E = etf_export(...)` 之後、`_write(p, E)` 之前加 `if code in nx_etf: E["nx"] = nx_etf[code]`。這樣 `nx` 仍是最後一個鍵，而 `etf_export` 一字不改（`test_iter36:131` 逐字比對了它的呼叫行）。
- 沒有預告的股票、ETF 不會輸出 `nx` 鍵，檔案和改版前逐位元組相同；`latest.json`、`screen.json` 都不變。
- 科學記號（PM 提示 4）：
  - Python 的 `json` 寫 `float` 時，小於 1e-4 的數字會寫成 `1e-08` 這種形式。這仍然是合法的 JSON，前端讀進來就是數字。
  - 畫面上的數字一律用 `dfmt(x, 8)`（`toLocaleString`）格式化，不會出現科學記號。測試用 `1e-8` 驗證過，顯示為 `0.00000001`。
  - 工具頁用 `String(n.c)`。JS 只有在數字小於 1e-6 時才會轉成科學記號，而小於 1e-6 的數字一定超過 6 位小數。這種情況 `tlBig` 會回傳 null，畫面走「超過 6 位小數，請依公告填寫」，不會帶入錯誤的值。

## 四、舊測試的影響（逐一確認）

### 4-1 排了 `events` 的收集測試：33 個，全部照過、不用改

- 確認方式：在副本裡把 `notices.request` 換成會記錄呼叫來源的包裝函式，再用 `runpy` 跑每個舊測試檔，統計每個測試函式呼叫了幾次 TWT48U／`tpex_exright_prepost`。

| 測試檔 | 測試函式（TWT48U 與 prepost 各被呼叫的次數） |
|---|---|
| `test_iter03` | `qa01_calendar_failure_isolated`(4)、`qa02_adhoc_reaches_site`(2)、`qa08_updated_at_is_this_run`(4)、`s3_01_t86_late`、`s3_02_not_published_vs_holiday`、`s3_03_next_morning`、`s3_04_friday_and_monday`、`s3_05_tpex_empty`、`s3_06_fetch_error`、`s3_07_schema_change`(4)、`s3_10_run_twice`、`s3_12_tpex_index_old_month`、`s3_adhoc_closure_flow`(3)、`s3_gap_hint`（共 14 個） |
| `test_iter04` | `t10_new_day_same_requests`、`t12_no_etf_rows`、`t13_margin_not_yet`、`t14_margin_deadline_notify_once`、`t15_no_margin_request_without_prices`、`t16_margin_schema_change`(2)（6 個） |
| `test_iter05` | `a3_flow`(2)、`e2_m1_published`、`e2_m2_m3_not_published`、`e2_m4_schema_only_that_etf`(2)（4 個） |
| `test_iter06` | `f61_m1_thanksgiving`、`f61_m3_b_before_post`(2)、`f61_m4_unpublished_unchanged`（3 個） |
| `test_iter07` | `f71_collect_errors_only_that_source`(2)、`f71_collect_published`、`f71_collect_unpublished`（3 個） |
| `test_iter11` | `f111_catchup_and_history`（1 個） |
| `test_iter24` | `detail_events_count`(2)、`qa03_tpex_only`（2 個） |

- 這些測試能照過，有三個原因：
  1. 假 World 對 TWT48U 回 `{"stat": "沒有資料", "tables": []}`，對 openapi 回 `[]`，兩者都解析成 0 筆、成功，不連資料庫。
  2. `w.requests == []`（例如 `s3_10` 的第二次執行）都出現在「同一晚重跑」的情境，這時不會排 `notices`。
  3. 沒有任何測試比對請求總數或 `undated` 全等；只有 `s3_01` 比對 `w.paths() == ["/rwd/zh/fund/T86"]`，而那次是同一晚的第二次執行，不會排 `notices`。
- 證交所主機在同一次執行中被標記失敗時（例如 `s3_06` 讓 BWIBBU_d 一直失敗），`notices.TWSE` 不會發請求，直接以 `FetchError` 結束：只印 ⚠️，不影響結果。

### 4-2 其他會碰到的舊斷言

| 舊斷言 | 處理 |
|---|---|
| `test_iter24:357`：拿掉「除權息事件」那一行和下一行（警告）後，其餘各行要和舊格式相同 | 新的一行放在警告之後（D88）。PM 原本要求放在事件正下方，那樣這條斷言會失敗 |
| `test_iter06:143`：`setup-db` 提示字串的結尾是 `etf_holding_gaps")` | 新表名稱放在 `etf_holding_gaps` 之前 |
| `test_iter36:131`：逐字比對 `etf_export` 的呼叫行 | 呼叫行不改，`nx` 在呼叫之後才附加 |
| `test_iter39` 反證「換股票沿用持有成本」：逐字比對 `y1: '', cost: '' }, h = [];` | 保留原行，`h.push(N[1])` 寫在下一行 |
| `test_iter39` `test_card_link`：取 `const dvh` 那一行起算的 2 行來執行 | 新的一行加在第 3 行 |
| `test_iter39` `LOCK`（`tlInfo`、`tlDtOut`、`tlDraw` 等函式的 sha1）、`divHTML` 的 sha1 | 都沒改 |
| `test_iter23`／`test_iter39`：`?v=` 必須等於檔案 sha1 的前 8 碼 | `stock.js?v=00d41238`、`tools.js?v=bc6f8d2c`（`app.js`、`app.css` 不變） |
| `test_iter03`、`04`、`06`、`09`、`10`、`24` 的 `check_report`（傳 `{}` 或缺鍵的 dict） | 用 `state.get("notices")`；新的一行不在 `lines` 裡 |
| `load_state` 的舊測試（`test_iter03:1050`、`test_iter04:450`、`test_iter10:250`、`test_iter24:376`） | 只多一個 `notices` 鍵，這些測試都是查單一鍵的值，不受影響 |

## 五、前端（F40-3）

### 5-1 `tools.js`

- 新函式 `tlNx(n, tw, e)`，回傳 `[帶入?, 提示]`。判斷依序如下：
  1. 有 `sr`（含現金增資）→ `[false, "12/04 除權含現金增資，參考價請看官方公告"]`。
  2. `c` 是 null → `[false, "12/10 除息，金額待公告"]`。
  3. `tlBig(String(c), 6)` 是 null（超過 6 位小數）→ `[false, "11/24 除息的預告現金股利 2.12345678 元超過 6 位小數，請依公告填寫"]`。
  4. 其他情況 → `[true, "已帶入 12/03 除息的預告股利（證交所預告表，僅供參考，以公司公告為準）"]`。上櫃寫「櫃買中心預告表」；ETF 寫「以發行人公告為準」；類型寫「除息／除權／除權息」。
- `tlDvLoad(d, e)`（第二個參數是 ETF 旗標，由 `tlLoad` 傳入 `!!E`）：
  - 可以帶入預告時：`c`、`s`（沒有 `s` 就填 `'0'`）改用預告值，第一句提示換成預告那句。原本那三個分支（sc、上市權息只有合計、一般）都跳過。
  - 不帶入預告時：照第 39 輪的寫法帶入最近一次的股利，然後在原本那句提示之後加 `tlNx` 的提示。
  - 「上次官方參考價」「近一年現金股利」兩行照舊。
  - 沒有最近一次紀錄時：有預告金額就帶入，提示依序是預告那句、「YYYY-MM-DD 起沒有除權息紀錄，請依公司公告填寫」；沒有預告金額時，`tlNx` 的提示加在最後。
  - 沒有 `nx` 時，所有分支和第 39 輪完全相同（`test_iter39` `check_load` 照過）。
- `tlLoad`：
  - `ex: d.nx ? d.nx[0].d : (原算式)`。
  - 交易成本分頁既有的「MM/DD 除權息，參考價另計」因此開始出現。`tlDtOut` 不改。
- 行數：＋18／−7。新程式不用 `?.`、`??`、`parseFloat`，node 14 可以執行。

### 5-2 `stock.js`

- 新函式 `nxText(n, etf)`。數字用 `dfmt(x, 8)`（只去掉尾端的 0、不另外四捨五入），認購價用 `dfmt(sp, 2)`。輸出逐字符合 PM 的 5 個例句：
  - `即將除息 12/03：現金股利 0.624652 元（預告，以公司公告為準）`
  - `即將除息 11/24：配息 7 元（預告，以發行人公告為準）`
  - `即將除息 12/02：金額待公告（預告，以發行人公告為準）`
  - `即將除權 11/27：含現金增資，認購價 52 元（預告，以公司公告為準）`
  - `即將除權 12/03：含現金增資，認購價尚未公告（預告，以公司公告為準）`
  - 另外測了配股：`即將除權息 12/10：現金股利 1 元、每千股配股 50 股（預告，以公司公告為準）`。
- `renderStock`：在第 39 輪 F39-3 那兩行之後加 1 行：

```js
if (dvh && data.nx) dvh.parentElement.insertAdjacentHTML('afterend', data.nx.map(n => `<div class="small dv-nx">${esc(nxText(n, E))}</div>`).join(''));
```

  - `dvh.parentElement` 是卡片的 `.sec-h`，所以這一行會插在表格或「沒有紀錄」那句之前。
  - 股票卡在「基本面」分頁，ETF 卡在「走勢」分頁，兩邊都有效。
  - `divHTML` 和它的呼叫字串都不改。
- 樣式只用既有的 `small`，`app.css` 不改。它是一般的區塊 `div`，320 寬時會自動換行；QA 在 1024／375／320 × 淺／深色驗收 15。

### 5-3 `index.html`

- `stock.js?v=a88a6b25` → `00d41238`。
- `tools.js?v=2a957b9a` → `bc6f8d2c`。

## 六、測試 `tests/test_iter40.py`（14 個，555 行）

| 測試 | 驗收 | 內容 |
|---|---|---|
| `test_parse` | 1～3 | 上市 8 列真實節錄：00406A 待公告、00901、01007T、020038、1437、2345（認購價尚未公告）、3706、6655。上櫃 6 列：8390、3680（8 位小數）、00958B 尚未公告、6523、6160「註4」、5483（跨年）。再加 1 列假資料「除權息」配股 0.05。也測沒有資料的 4 種形式、欄位不符的 4 種形式、同鍵重複、配股率解析不了、`sub_ratio` = 0 時認購價為 NULL、日期或類型不明 |
| `test_write` | 4 | 假連線：一次 MERGE；JOIN `stocks`／`etfs`；UPDATE 不含 `first_seen`；INSERT 寫入 `first_seen, last_seen`；沒有 DELETE；參數順序；JSON 的小數是不帶指數的字串（假資料 `0.00000001`）；輸出文字；0 筆時不連資料庫 |
| `test_timing` | 5 | `NxWorld`（`test_iter03` 的 World 加上兩個真實節錄）：新交易日各抓 1 次、上市參數 `{"response": "json"}`、`undated.notices`、兩行 📅；同一晚重跑、週六、`collect --date` 都 +0（`--date` 的事件照抓）；`make_plan` 的 `notices` 跟著 `events`；`__main__.py`、`events.py` 不碰預告 |
| `test_isolation` | 6 | TWT48U 回 500：只打 1 次、證交所主機沒有被標記、印 `⚠️  notices.TWSE 失敗`、上櫃照抓、`undated.notices` 只有 TPEx；回傳碼、結果、`items`、通知、匯出次數都和沒有失敗時相同 |
| `test_counts` | 7 | `_undated_counts` 的表清單不變 |
| `test_state` | 8 | 兩個市場各自取最新；舊格式不報錯 |
| `test_lines` | 9 | 4 種文字逐字相符；2 個交易日不提醒、3 個交易日才 ⚠️；回傳碼不變；其他各行和沒有預告時相同 |
| `test_export` | 10、11 | 全部成功；除權息日 = 資料日不匯出；改日期；上市失敗時沿用上次快照；0 筆和從沒成功；到了除權息日；去尾 0（`0.624652`、`7`、`50`）；`c` 的 null 和 0 分得開；`s`、`sr`、`sp` 的出現規則；股票和 ETF 分開輸出 |
| `test_export_wiring` | 11、12 | 和 `build_status` 共用 state；個股 `nx` 在 `dv` 之後、ETF `nx` 在 `_write` 之前；`etf_export` 的 sha1 不變；`build_status` 的參數；`catchup.py` 沒有新表名稱 |
| `test_setup_db` | 4、文件 | DDL 6 個片段；README 有新表、新測試與功能說明 |
| `test_load` | 13 | node 執行 `renderTools`，7 檔涵蓋 PM 表格的 6 種情況再加配股：帶入值、提示依序出現、`TL.info.ex`、交易成本分頁的「MM/DD 除權息，參考價另計」 |
| `test_card` | 14 | `nxText` 7 個例句（PM 5 句＋配股＋`1e-8`）；DOM 插入用 node 實跑（股票、ETF、沒有 `nx`）；第 39 輪那兩行不動；`divHTML` 的 sha1 不變 |
| `test_wiring_and_words` | 16、17、21 | 4 個 `?v=`；node 14 語法；新函式、新模組、例句、提示裡沒有禁用詞與 PM 另列的詞 |
| `test_contrast` | 19 | 反證 20 種（見下） |

- 反證（每一種都要讓上面的某個檢查失敗）：
  - Python 13 種。PM 指定的 7 種：匯出不比 `last_seen`、`s` 不乘 1,000、待公告存成 0、`notices` 失敗算異常、`_undated_counts` 加新表、除權息日 = 資料日也匯出、MERGE 更新 `first_seen`。設計另加 6 種：認購價不看現增、不是 isolated、每次都排預告、`collect --date` 也抓、`load_state` 取最舊的、過期門檻改成 2。
  - JS 7 種：含現增也帶入、待公告也帶入、超過 6 位小數也帶入、ETF 也寫「公司」、`ex` 不看 `nx`、卡片的 ETF 也寫「公司」、卡片數字四捨五入到 2 位。
  - Python 反證的做法：用 `inspect.getsource` 取出函式原始碼，把指定的一段換掉後在原模組重新定義，測完換回原函式。這樣流程測試（`run_world`）會呼叫到改壞的版本。
- 測試裡的禁用詞清單本身是檢查用的字串（比照 `test_iter34`、`test_iter38`、`test_iter39`），不是使用者看得到的文字。

## 七、檔案與行數（`git diff --numstat`）

| 檔案 | ＋／− | PM 估計（上限） |
|---|---|---|
| `twstock/collectors/notices.py`（新檔） | ＋95 | 收集約 75（98） |
| `twstock/collectors/catchup.py` | ＋9／−1 | 掛上約 25（33），和 `db.py` 合計 |
| `twstock/db.py` | ＋21／−1 | 同上 |
| `twstock/health.py` | ＋21／−3 | 約 25（33） |
| `twstock/export.py` | ＋34／−2 | 約 35（46） |
| `site/tools.js` | ＋18／−7 | 約 20（26） |
| `site/stock.js` | ＋7 | 約 12（16） |
| `site/index.html` | ＋2／−2 | — |
| `README.md` | ＋4／−2 | 約 15（20），和 `__main__.py` 合計 |
| `docs/iterations/README.md` | ＋1 | — |
| **程式合計** | **＋205／−14** | 約 207（270） |
| `tests/test_iter40.py` | ＋555 | 約 280（364），**超出 191 行**（D90） |

- 測試超出的原因：
  - 兩邊真實節錄逐字內嵌，約 35 行（一列一行，最長的列約 250 字）。
  - 前端 7 檔假資料和預期值，約 45 行。
  - 反證 20 種，約 45 行；比 PM 列的 7 種多 13 種。
  - 收集流程 4 種情境，約 80 行。
- 測試行數仍在一個工作階段的上限（580）之內。

## 八、和 PM 的差異

| # | 差異 | 原因 |
|---|---|---|
| 1 | `check` 的新一行放在「最後一次收集的警告」之後，不是緊接在事件之下 | `test_iter24:357` 要求事件之後的下一行是警告。平常沒有警告時，看起來仍然是事件的下一行（D88） |
| 2 | `etf_export` 不加參數，`nx` 在 `export_all` 裡附加 | `test_iter36:131` 逐字比對呼叫行；輸出相同（`nx` 是最後一個鍵） |
| 3 | `setup-db` 提示中，新表名稱放在 `etf_holding_gaps` 之前 | `test_iter06:143` |
| 4 | `__main__.py` 不改 | `setup-db` 的說明本來就沒有列出各資料表 |
| 5 | `build_status` 加選用參數 `state` | PM 提示 3「不要多開連線」：共用同一次 `load_state`，連線照舊只有一條 |
| 6 | 多測 1 種卡片情況（配股）和 `1e-8` | 驗收 3 的 `s` = 50 要在畫面上驗到；PM 提示 4 的科學記號 |
| 7 | 測試行數超出 PM 上限 | 見第七節（D90） |

## 九、風險

| 風險 | 說明 | 緩解 |
|---|---|---|
| 同一晚證交所主機已被標記失敗 | `notices.TWSE` 不發請求，直接以 FetchError 結束。如果事件已經成功（`events_to` 已更新），這天就不會再抓預告 | 沿用上次的快照（D86-6）；連續 3 個交易日沒有更新時 `check` 會顯示 ⚠️；要不要重抓見 D89 |
| 事件失敗後下一次排程重跑 | `events_to` 沒有更新，下一次會同時重排 `events` 和 `notices`，每次重跑都 +2 請求 | 和事件同進退，次數有限（一天最多 4 次排程） |
| 資料表沒建就收集 | `pyodbc.Error` 讓這次收集回傳 2 | 套用步驟先跑 `setup-db`；沿用既有的提示訊息 |
| 預告現金是 0，而且沒有配股、沒有現增 | 卡片會只剩「即將除息 MM/DD：（預告…）」；工具頁帶入 0，`tlDvOut` 顯示「請輸入現金股利或配股」 | 這份快照中 0 例（官方的「權」都有現增）；QA 觀察 |
| 旺季資料被截斷、配股率單位、7～8 位小數 | Q40-2、Q40-3、Q40-5 | `check` 有筆數；配股率依 R33 乘 1,000；超過 6 位小數不帶入（PM 預設） |
| 預告被誤讀成已確定 | — | 畫面每處都寫「預告」「以公司（發行人）公告為準」，工具頁另寫「僅供參考」 |

## 十、PG 套用步驟

1. `git apply --check docs/iterations/40/03-design.diff`，通過後執行 `git apply docs/iterations/40/03-design.diff`。
2. 跑 `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`，應該 40 個全部通過。
3. 以下步驟需要使用者同意後才執行（D87 = A）：
   - `python -m twstock backup` → `python -m twstock setup-db`（新表建立後再跑一次，確認不報錯）。
   - 在交易日晚上、行情公布之後手動執行 `collect --catch-up`。確認輸出有兩行 📅，`collect_runs` 這次的請求數比前一晚多 2。如果這次沒有自動匯出，再執行 `export`。
   - 如果在週末套用：`setup-db` 之後等 11/23（週一）的排程自然抓取，隔天用 `check` 確認。
4. `check` 出現「除權除息預告最後成功」那一行。
5. 抽查 `stocks/1437.json`、`etfp/00901.json`、`stocks/3706.json`（如果除權息日還沒到）裡有 `nx`。
6. 從專案目錄用 8001 啟動做冒煙測試：
   - 個股 1437「基本面」的股利卡有「即將除息」那一行。
   - `#/tools/dv?c=1437` 帶入預告股利；`#/tools/dt?c=1437` 有「12/03 除權息，參考價另計」。
   - 測完關閉 8001。

## 十一、需要使用者決定的事項（D88 起；已 grep `docs/iterations`，目前最大 D87）

| 編號 | 問題 | 選項 | SA 建議 |
|---|---|---|---|
| D88 | `check` 新一行的位置 | **A** 放在「⚠️ 最後一次收集的警告」之後（沒有警告時就是事件的下一行；舊測試 0 行改動）；**B** 照 PM，緊接在事件那行之下，需要使用者逐行同意修改 `test_iter24:357` | **A**：只有在有警告的那幾天，位置才會差一兩行，不需要改舊測試。設計已照 A 做 |
| D89 | 同一晚證交所主機已被標記失敗、而事件已成功時，預告要不要在下一次排程重抓 | **A** 不重抓：下一個交易日再抓，期間沿用上次快照，連續 3 個交易日沒有更新時 `check` 顯示 ⚠️；**B** 重抓：`make_plan` 另外記錄預告各市場最後成功的日期，沒有成功就再排（約 +6 行程式、+20 行測試；同一晚最多多 2 次請求） | **A**：符合 D86-6「沿用上次快照」；預告大多提前數天公布，晚一天影響小 |
| D90 | `test_iter40` 共 555 行，超出 PM 估計上限（364） | **A** 接受（在工作階段上限 580 之內，多出來的是真實節錄與反證）；**B** 刪掉設計另加的反證與情境，約可減到 420 行 | **A** |

## 使用者決定（2026-11-21）

- **D88 = A**：`check` 新行放在「最後一次收集的警告」之後，舊測試 0 行改動。
- **D89 = A**：預告抓失敗不在下一次排程重抓，沿用上次快照，連續 3 個交易日沒更新時 `check` 顯示 ⚠️。
- **D90 = A**：接受 `test_iter40` 555 行。
