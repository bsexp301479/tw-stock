# 第 43 輪｜SA：設計（集保股權分散 F43-1～F43-3）

- 撰寫日期：2026-11-22（週日）
- 依據：
  - `43/01-analyst.md`：F43-1～F43-6、R43～R50、Q43-1～Q43-9。
  - `43/02-pm.md`：範圍、情境表 1～17、手算範例、驗收 1～27、SA 提示 1～10。
  - 使用者決定：D114 = A、D114-1 = B（寬表）、D114-2～D114-8 照建議、D115 = A（`_undated_counts` 不動）、PM 自行決定的 9 項照 PM。
- 做法：
  - 在 scratchpad 建兩份副本 `r43sa/base`（原樣）、`r43sa/proj`（修改）。副本不含 `.git`、`.env`、`logs/`、`_backups`、`_archive`；跑測試時 `site/data` 用符號連結（唯讀）。
  - 在 `proj` 實作、跑測試；用 `git diff --no-index` 產出 `43/03-design.diff`（1,252 行，a/ b/ 前綴）。
  - 驗證：
    - 正式專案 `git apply --check docs/iterations/43/03-design.diff` 通過。
    - 另複製一份 `base` 為 `verify`，套用 diff 後和 `proj` 逐檔比對（`diff -r`），結果相同。
    - `verify` 跑 `test_iter01～43`，43 個全部通過。
    - 前端：`verify/site` 用 8002 起靜態伺服器，在頁面以 JavaScript 對 2421 塞 30 週、0050 塞 1 週的模擬 `sh`，看 1024（深色）、320（淺色）的籌碼分頁：卡片 2 × 2、`scrollWidth = innerWidth`、週圖與圖例正常、1 週時出現「自 11/20 起收錄…」。結束後 localStorage 還原成開始時的內容（`{"tw.todayTab":"ov"}`）、視窗設回 desktop、伺服器關閉。
  - 解析測試用分析師存下的 `r43/od15.csv`（只讀）節錄 7 個代號 × 17 列，內嵌在測試裡；測試本身不讀 scratchpad。
- 守則：外部請求 0 次、資料庫 0 次（副本也沒有連線）、`export` 0 次；沒有讀出或複製 `.env`；沒有用 8000／8001。正式專案只新增 `docs/iterations/43/03-design.md`、`03-design.diff`。

---

## 重點摘要

- **舊測試 0 行改動**，`test_iter01～42` 全部照過（第四節逐項說明）。
- **`setup-db` 是啟用開關**：程式更新後、`setup-db` 之前，收集不排 `tdcc`（0 次請求、不印字）、匯出不讀表、`check` 只多一行提示。所以 11/23 晚的第 40 輪上線收集不受影響，PG／QA 可以照常開發。
- 新檔 `twstock/collectors/tdcc.py`（100 行）：`parse_tdcc` 純函式、`collect_tdcc` 一個 MERGE（OPENJSON）＋ `OUTPUT inserted.is_etf` 取得實際寫入的股票／ETF 檔數。
- 抓取時機：純函式 `tradingcal.last_full_week(today, closed)`（最近一個過完、有交易日的週）；`make_plan` 以「週」比較表中最新資料日，寫入以官方資料日為準；PM 情境 1～17 全部驗過。
- 「有新資料」照 D115 = A：`changed` 另看本次 `undated["tdcc"]` 的 `s`／`e`。
- 匯出 `sh`：純函式 `share_export`（整數四捨五入）；沒有資料的代號不輸出鍵，檔案逐位元組不變。
- 前端：`stock.js` 新增 `shCards`、`SH_NOTE`、`shChart` 三個頂層定義，`renderStock` 加 4 行、`buildChip` 加 1 行；`app.css` 不改。
- 新測試 `test_iter43`：14 個測試、566 行（上限 580 內），反證 20 種（Python 14、JS 6）全部擋下。
- 新決策 D116、D117（第十一節），建議都是 A，設計已照 A 做。

## 一、資料表（`db.py` 的 `DDL`）

```sql
IF OBJECT_ID('share_distribution') IS NULL
CREATE TABLE share_distribution (
    id           BIGINT IDENTITY(1,1) PRIMARY KEY,
    code         NVARCHAR(10)  NOT NULL,   -- 股票或 ETF 代號（寫入時只收 stocks、etfs 表已有的）
    is_etf       BIT           NOT NULL,
    data_date    DATE          NOT NULL,   -- 官方資料日期（每週最後一個營業日），不是抓取日
    n1 INT NOT NULL, …, n16 INT NOT NULL,
    s1 BIGINT NOT NULL, …, s16 BIGINT NOT NULL,
    n_total      INT           NOT NULL,   -- 17 級人數
    s_total      BIGINT        NOT NULL,   -- 17 級股數
    fetched_at   DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_share_distribution UNIQUE (code, data_date)
)
-- 索引（放在 IX_foreign_holdings_date 之後）
CREATE INDEX IX_share_distribution_date ON share_distribution(data_date)
```

- `n1..n16`、`s1..s16` 在 DDL 裡用 `", ".join(...)` 產生（f-string；Python 3.9 實測可用）。
- 位置：`dividend_notices` 之後、`stocks.shares` 的 ALTER 之前；可重複執行。
- `setup_database()` 提示字串加 `share_distribution（第 43 輪）`，放在 `etf_holding_gaps` 之前（`test_iter06:143` 檢查結尾）。
- `__main__.py` 的 `setup-db` 說明本來就沒有列表名，不改（同第 40 輪）。
- 級距（Q43-3）：本角色不得發外部請求，**沒有再開集保查詢網頁核對表頭**；設計與 `dblayout.md` 依分析師 3-4 節的集保標準級距（12 級 400,001 股起、15 級 1,000,001 股起、8 級止於 50,000 股）。程式與測試只依分級編號，不依文字。見 D116。

## 二、收集（F43-1）

### 2-1 `collectors/tdcc.py`（新檔）

| 函式 | 內容 |
|---|---|
| `parse_tdcc(text)` | 純函式。輸入已去 BOM 的 CSV 文字，輸出 `(資料日, rows, skipped)` |
| `collect_tdcc(latest, today)` | `request("GET", URL, expect_json=False, isolated=True)` → `.content.decode("utf-8-sig")` → 解析 → 官方日 > `latest` 才 MERGE；回傳 `undated.tdcc` |

解析規則（PM 二之一，全部照做）：

| 情況 | 結果 |
|---|---|
| 表頭 6 欄 `strip()` 後不等於 `資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%` | `SchemaError` |
| 0 列資料、某列不是 6 欄 | `SchemaError` |
| 資料日不只 1 個，或不是 8 碼數字 | `SchemaError` |
| 某代號某級重複、1～17 級不齊（含不收的代號） | `SchemaError`（整份不寫） |
| 代號不是 `is_valid_stock_code` 也不是 `is_etf_code`（`2881A`、`01001T`） | 不收、不驗算 |
| 人數或股數不是不帶小數的非負整數（`1.5`、`-1`） | 略過該代號、`skipped += 1` |
| R46：人數 1～15 級和 ≠ 17 級；股數 1～15 級和 − 16 級 ≠ 17 級；17 級股數 ≤ 0 | 略過該代號、`skipped += 1` |

- 讀檔用 `csv.reader(text.splitlines())`（官方是 CRLF）；代號 `strip()`（`'0050  '` → `0050`）。
- `rows` 每筆 `{code, n1..n16, n_total, s1..s16, s_total}`；`000218` 會在 `rows` 裡（`is_etf_code` 為真），寫入時由 SQL 排除。
- `UnicodeDecodeError`（`ValueError`）、`SchemaError` 都在 `PARSE_ERRORS` 內，由 `_guard` 接住。

### 2-2 MERGE

```sql
MERGE share_distribution AS t
USING (
    SELECT j.*, CAST(CASE WHEN et.etf_id IS NULL THEN 0 ELSE 1 END AS BIT) AS is_etf
    FROM OPENJSON(?) WITH (code NVARCHAR(10), n1 INT, …, n16 INT, n_total INT, s1 BIGINT, …, s16 BIGINT, s_total BIGINT) AS j
    LEFT JOIN stocks st ON st.stock_code = j.code
    LEFT JOIN etfs et ON et.etf_code = j.code
    WHERE st.stock_id IS NOT NULL OR et.etf_id IS NOT NULL
) AS s
ON t.code = s.code AND t.data_date = ?
WHEN MATCHED THEN UPDATE SET is_etf = s.is_etf, n1 = s.n1, …, s_total = s.s_total, fetched_at = GETDATE()
WHEN NOT MATCHED THEN
    INSERT (code, is_etf, data_date, n1, …, s_total) VALUES (s.code, s.is_etf, ?, s.n1, …, s.s_total)
OUTPUT inserted.is_etf;
```

- 參數：JSON、資料日、資料日。一次 `execute` ＋ `commit`，同一個交易；約 2,400 列 × 34 個數字欄，JSON 約 1 MB。
- `OUTPUT inserted.is_etf` 回傳每一列（新增或覆寫）的 `is_etf`，`s` = 0 的列數、`e` = 1 的列數，就是「實際寫入的股票、ETF 檔數」。
- BIGINT 不失真：`db.to_json` 對 Python `int` 原樣輸出（`25531000000`，不經 float）；OPENJSON 依 `WITH` 的 `BIGINT` 直接由 JSON 數字文字轉型。最大值 0050 合計 255 億股，在 BIGINT 與 JSON 安全整數範圍內。測試檢查 JSON 文字含 `"s_total": 25531000000`。
- 同鍵（理論上不會發生，Q43-5）整列覆寫。
- 官方日 ≤ `latest` → 不連資料庫；`rows` 為空（全部不收或略過）→ 不連資料庫，算成功，輸出「股票 0 檔、ETF 0 檔」。

### 2-3 輸出（逐字，和 PM 相同）

```
  🏦 集保股權分散 2026-11-20：股票 1,992 檔、ETF 367 檔
  🏦 集保股權分散 2026-11-20：股票 1,992 檔、ETF 367 檔，略過 2 檔（合計不符）
  ℹ️  集保股權分散：官方尚未更新（仍是 2026-11-20 那週），明天再試
  ⚠️  tdcc 失敗：opendata.tdcc.com.tw 附屬查詢失敗（不重試，收集繼續）：HTTP 500（可能被限流）
```

`undated["tdcc"]`：寫入 `{"on", "d", "s", "e"}`；官方未更新 `{"on", "d"}`；失敗沒有這個鍵。

### 2-4 目標週（`tradingcal.py`，新增 3 個純函式）

```python
def week_of(d): return d - timedelta(days=d.weekday())

def last_full_week(today, closed):
    wk = week_of(today)
    end = wk if trading_days(today, wk + timedelta(days=4), closed) else today   # 今天到週五還有交易日 → 這週還沒過完
    return week_of(最後一個 < end 的交易日)

def weeks_behind(d, today, closed):   # (week_of(d), last_full_week(today)] 之間「有交易日的週」數，check 用
```

- 和 PM 的定義等價：今天到本週五之間（含今天）還有交易日時，從本週一往前找；否則從今天往前找。週六、週日 `trading_days(today, 週五)` 是空的。
- 放在 `tradingcal.py` 而不是 `collectors/tdcc.py`：`health.py` 註明「health 不匯入 collectors」，`check` 也要用這個函式；`tradingcal` 本來就被兩邊匯入（差異 1）。

情境計算（`closed` = 手寫表 ∪ `AD_HOC`；情境 10、11 拿掉 10/23；情境 15 另加 2027/1/1）：

| # | 今天 | 本週還有交易日？ | 往前找的起點 | 最後交易日 | target | `latest` 的週 | 排？ |
|---|---|---|---|---|---|---|---|
| 8 | 10/8（四） | 有（10/8） | 10/5 | 10/2 | 9/28 | 9/28 | 不排 |
| 9 | 10/9（五，休市） | 沒有 | 10/9 | 10/8 | 10/5 | 9/28 | 排；官方 10/8 |
| 9 之後 | 10/12（一） | 有 | 10/12 | 10/8 | 10/5 | 10/5（10/8） | 不排 |
| 10 | 10/23（五，不在 closed） | 有（10/23） | 10/19 | 10/16 | 10/12 | 10/12 | 不排 |
| 11 | 10/24（六） | 沒有 | 10/24 | 10/23 | 10/19 | 10/12 | 排；官方 10/22 寫入 |
| 11 之後 | 10/27（二） | 有 | 10/26（休市） | 10/23 或 10/22 | 10/19 | 10/19（10/22） | **不排（比週）** |
| 12 | 2/23（一） | 有 | 2/23 | 2/11（2/12～2/20 休市） | 2/9 | 2/9 | 不排 |
| 13 | 3/2（一） | 有 | 3/2 | 2/26（2/27 休市） | 2/23 | 2/9 | 排 |
| 15 | 2027/1/4（一） | 有 | 1/4 | 12/31（1/1 休市） | 12/28 | 12/21 | 排 |

- 「比週不比日期」：若改成「`latest` < 推算的週五」，10/27 會因 10/22 < 10/23 每天重抓（反證「比日期不比週」擋下）。

### 2-5 `catchup.py`

| 位置 | 改動 | 舊測試為什麼不受影響 |
|---|---|---|
| import | `share_state`（health）、`last_full_week`、`week_of`（tradingcal）、`collect_tdcc` | — |
| `make_plan` | 新增**關鍵字**參數 `share=None`；`plan` 字面那行不動，下一行起 2 行：`due = share and share[0] and (share[1] is None or week_of(share[1]) < last_full_week(now.date(), closed)) and state.get("tdcc_on") != now.date()`；`plan["tdcc"] = {"latest": share[1]} if due else None`。放在 `if not days: return plan` 之前（週末、休市日也排） | 舊呼叫都是位置參數、沒有 `share` → `None`；舊 state 沒有 `tdcc_on` 用 `.get`；`"financials": None, "notices": False}` 字面仍只有 1 次 |
| `plan_for_date` | 不改（沒有 `tdcc` 鍵 → `collect --date` 不抓） | — |
| `plan_is_empty` | 加 `or plan.get("tdcc")` | 自組 plan（`test_iter09:197`、`test_iter10:229`）沒有鍵 → `None` |
| `execute_plan` | `notices` 迴圈之後、`revenue` 之前 4 行：`if plan.get("tdcc") and _guard("tdcc", errors, lambda: sd.append(collect_tdcc(plan["tdcc"]["latest"], now.date()))): undated["tdcc"] = sd[0]` | `if plan.get("notices")` 字面不變 |
| `_run_locked` | 第一個連線 `state = load_state(cur)` 之後 `share = share_state(cur)`，傳 `make_plan(..., share=share)`；`changed` 那行之後加 `changed = changed or any((undated.get("tdcc") or {}).get(k) for k in ("s", "e"))`（D115 = A） | `_undated_counts`、`undated_errors` 的 6 個鍵字面都不動 → `tdcc` 失敗不算異常、不通知 |

- 請求數：一般晚上 +0；週最後交易日隔天起第一次執行 +1（約 2.4 MB）；官方延後時當天其餘執行 +0、隔天再 +1；`collect --date`、`history`、`events`、表不存在 +0。
- 抓到舊週時 `undated.tdcc.on` = 今天 → `load_state` 的 `tdcc_on` = 今天 → 當天不再排（情境 5）。失敗沒有 `undated.tdcc` → 下一次執行（同一天）再試（PM 二之一）。
- `share_state` 在收集時也會多查一次「最新一週的股票／ETF 檔數」（`check` 用），走 `IX_share_distribution_date`，成本可忽略；為了讓收集和 `check` 共用一個函式，不另寫只查兩項的版本。

### 2-6 `health.py`

| 函式 | 內容 |
|---|---|
| `load_state` | state 字面加 `"tdcc_on": None`；迴圈裡 `if und.get("tdcc") and state["tdcc_on"] is None: state["tdcc_on"] = date.fromisoformat(und["tdcc"]["on"])`（新到舊，取最近一筆）。**不多下查詢** |
| `share_exists(cur)` | `SELECT OBJECT_ID('share_distribution')`；`fetchone()` 為 None 或值為 None → False |
| `share_state(cur)` | `(表是否存在, 最新資料日, 該週股票檔數, ETF 檔數)`；不存在時不查表。存在時再查 `SELECT MAX(data_date) FROM share_distribution`、`SELECT is_etf, COUNT(*) … WHERE data_date = ? GROUP BY is_etf` |
| `share_line(share, today, closed)` | 4 種文字，逐字照 PM；`weeks_behind ≥ 2` 加 `，⚠️ 已落後 N 週，漏收的週無法回補` |
| `check_report` | 新增**關鍵字**參數 `share=None`；`notices_line` 那行之後 `if share is not None: out.append(share_line(...))`。不放進 `lines`，不算異常、不改回傳碼 |
| `run_check` | `share = share_state(cur)`，`check_report(..., share=share)` |

- 例：最新 11/20 → 12/1 檢查 target 11/23、落後 1 週不加 ⚠️；12/7 → target 11/30、落後 2 週加 ⚠️；春節（最新 2/11、3/2 檢查）→ 2/16 那週沒有交易日不算，落後 1 週不加 ⚠️。

## 三、匯出（F43-2，`export.py`）

- 常數 `SH_WEEKS = 52`。
- `share_pct(x, t)`：`q = (2 * x * 10000 + t) // (2 * t)`，`q % 100 == 0` 時回傳整數 `q // 100`，否則 `q / 100`。邊界：`share_pct(1005, 100000)` = **1.01**（浮點 `round(1.005, 2)` 是 1.0，反證「浮點四捨五入」擋下）；`share_pct(1, 1)` = `100`（JSON 寫 `100`，不是 `100.0`）。
- `_load_share(cur)`：`share_exists` 為否 → `[]`（只下 1 個查詢）；否則

```sql
SELECT code, is_etf, data_date, s1, …, s15, s_total, n1, n12, n13, n14, n15, n_total
FROM share_distribution
WHERE data_date IN (SELECT DISTINCT TOP 52 data_date FROM share_distribution ORDER BY data_date DESC)
```

- `share_export(rows)` → `({股票代號: sh}, {ETF 代號: sh})`：純函式裡也只留最近 52 個資料日（測試可以驗 53 週），依（代號, 日期）排序；某代號某週沒有列就不列那週。鍵順序 `d, b, k, m, r, n, bn, z`，計算照 PM（`b` = s12～s15、`k` = s15、`m` = s9～s11、`r` = s1～s8，分母 `s_total`；`n` = `n_total`、`bn` = n12～n15、`z` = n1）。
- 接線：
  - `eev = _load_etf_events(cur)` 之後、`conn.close()` 之前：`sh_stock, sh_etf = share_export(_load_share(cur))`。
  - 個股 dict 在 `"fh"` 那行之後：`**({"sh": sh_stock[code]} if code in sh_stock else {}),`。
  - ETF 在 `E["nx"]` 之後、`_write(p, E)` 之前：`if code in sh_etf: E["sh"] = sh_etf[code]`（`etf_export` 一字不改，`test_iter40` 的 sha1 照過）。
- `screen.json`、`latest.json` 不變（`sh_stock`／`sh_etf` 只出現在上面三處，測試檢查次數）。
- 手算範例（測試用真實節錄算出，和 PM 二之五相同）：

| 代號 | `b` | `k` | `m` | `r` | `n` | `bn` | `z` |
|---|---|---|---|---|---|---|---|
| 2421 | 63.33 | 51.97 | 13.68 | 22.99 | 53095 | 100 | 32045 |
| 00406A | 23.09 | 10.77 | 48.36 | 28.9 | 635412 | 5584 | 22555 |
| 0050 | 23.17 | 21.51 | 18.45 | 58.39 | 4038137 | 1054 | 1644997 |
| 2330 | 86.91 | 84.15 | 3.68 | 9.41 | 3329043 | 2609 | 2740735 |

## 四、舊測試的影響（逐項，0 行改動）

### 4-1 World（`test_iter03`／`04`／`24` 等的假資料庫）

- 存在查詢的 SQL 是 `SELECT OBJECT_ID('share_distribution')`，不含 `FakeCursor` 認得的任何片段（`SELECT COUNT(*) FROM`、`FROM collect_runs`、`MERGE `、`SELECT holiday_date`、`SELECT MAX(trade_date) FROM daily_prices`、`SELECT etf_id FROM etfs WHERE etf_code`、`revenue_year…`、`fin_year…`）。
- 所以落到 `FakeCursor.execute` 的最後：`self.result = []` → `fetchone()` 為 None → `share_exists` 為 False → `share_state` = `(False, None, 0, 0)`，不再查表 → `make_plan` 的 `tdcc` = None → `plan_is_empty` 照舊 → `w.requests == []`、「休市日沒有要抓的資料，不需要請求」、「不匯出」都照舊；輸出沒有任何「集保」字樣。
- `test_iter03:168` `run_check` 在 World 下多印一行「集保股權分散：尚未建立資料表…」，該測試只看 `rc == 0`、「無異常」、不請求、不寫入，照過。

### 4-2 其他

| 舊斷言 | 處理 |
|---|---|
| `make_plan` 位置參數呼叫（`test_iter03:1003～1019`、`09:176`、`10:196、209`、`40:205、209`） | `share` 只能是關鍵字，預設 None |
| 自組 plan（`test_iter09:197`、`10:229`） | `plan.get("tdcc")` |
| `test_iter40:254`、`:518` `_undated_counts` 4 張表、字面 | 不動（D115 = A） |
| `test_iter40:509～520` 其他反證字面 | `make_plan` 字面、`if plan.get("notices")`、`undated_errors` 鍵清單、`load_state` 的 `setdefault` 行、`if lag >= 3` 都不動、不複製 |
| `test_iter40:367` `catchup.py` 不可有 `dividend_notices` | 不受影響 |
| `check_report` 位置參數、`state = {}`、`lines[1]`／`[2]`／`[-1]`、`test_iter24:357` | 新參數只能是關鍵字、預設 None 不印 |
| `load_state` 假 cursor（`test_iter03:1050`、`04:438～454`、`10:242～250`、`24:371`、`40:277`） | 只多解析 `undated.tdcc`，不多查詢 |
| `test_iter24:446` mock `_undated_counts` | 不受影響 |
| `test_iter24:536` README 中含「第 24 輪」的行不可有「落後」等字 | README 第 51 行（含「第 24 輪」）新增的句子寫「漏收 2 週以上加 ⚠️」，不寫「落後」 |
| `test_iter06:143` `setup-db` 提示結尾 | 新表名放在 `etf_holding_gaps` 之前 |
| `test_iter36:128、136` `eev =` 之後的 `conn.close()`、`_load_etf_events`～`etf_gaps` 之間不可寫入 | 新的一行在 `eev` 之後、`conn.close()` 之前；新函式放在 `notice_export` 與 `etf_export` 之間，只有 SELECT |
| `test_iter28:47～50` `chipSec` 三行字面 | 不改，只在法人與信用之間插 3 行 |
| `test_iter28`／`29` node 單獨執行 `buildChip`（`$` 自動產生元素） | 新的那行是 `if (data.sh && data.sh.d.length >= 2 && $('#shC')) charts.push(...shChart(data.sh, E, mk));`：舊測試的 `data` 沒有 `sh`，條件第一項就是假，不會碰到 `$('#shC')`，也不會呼叫沒有被取出的 `shChart`；`charts = anchors.map(a => a[0]);` 字面保留，週圖在下一行 `push`（之後的 `fitContent` 迴圈一併處理）。建立的圖數仍是股票 5、ETF 2 |
| `test_iter29:202` 禁用詞掃描區（`// 第 29 輪 F29-4…` 到 `const chipSec`） | 新程式都不在這段裡（`const SH` 放在 `const GK` 之後） |
| `test_iter14:117`、`37:272`、`23:251` | 不用 `note-dup`、`noteHTML`、`mkPos` |
| 各輪 `?v=` 檢查 | `stock.js?v=d7c03cdc` → `a6ab2ef4`（`app.js`、`app.css`、`tools.js` 不變） |

- 「沒有 `sh` 時 `buildChip` 建立的圖與舊版相同」：`test_iter28 test_chip_charts_node` 本身就是比對方法（股票 5 張、順序 cp/ci/cu/cm/cl、ETF 2 張）；`test_iter43 check_charts` 另外對沒有 `sh`、只有 1 週的 `data` 斷言圖數 5。

## 五、前端（F43-3，`site/stock.js`）

### 5-1 `renderStock`（＋4 行）

- `const GK` 之後：`const SH = data.sh && data.sh.d.length ? data.sh : null, shN = SH ? SH.d.length : 0;`
- 法人買賣超那組之後、信用交易之前：

```js
${SH ? chipSec('股權分散', `資料日 ${md(SH.d[shN - 1])}（每週一次，集保結算所）`, shCards(SH, E), shN >= 2 ? chLeg('持股比例（%，每週）', 'shC', 110) +
  chLeg(`${E ? '受益' : '股東'}人數（人，每週）`, 'snC', 90) : `<div class="muted small">自 ${md(SH.d[0])} 起收錄，累積 2 週後顯示走勢。</div>`,
  `<div class="muted small val-note">${SH_NOTE[E ? 1 : 0]}</div>`) : ''}
```

- ETF 沒有法人組，所以這組在 ETF 籌碼分頁排第一個。沒有 `sh` 或 `sh.d` 為空 → `''`。

### 5-2 頂層新增（`buildChip` 之前）

- `shCards(sh, etf)` → 4 張卡陣列（`cardsHTML` 格式），`i` = 最後一筆；週變化 `w(a, k, nd)` = `i − k < 0 ? '--' : sgn((Math.round((a[i] − a[i − k]) × 100) + 0) / 100, nd)`（先到 0.01 消除浮點尾數，`+ 0` 把 −0 變 0）。文字照 PM 表；例（2421 兩週示意）：

| 標題 | 主數字 | 副標 |
|---|---|---|
| 持股超過 400 張 | 63.45% | `1週 +0.12　4週 --（百分點）<br>101 人` |
| 持股超過 1,000 張 | 52.01% | `1週 +0.04　4週 --（百分點）` |
| 50 張以下 | 22.95% | `1週 -0.04　4週 --（百分點）` |
| 股東人數（ETF：受益人數） | 53,407 人 | `1週 +312　4週 --（人）<br>未滿 1 張 32,210 人` |

  - PM 表的主數字寫第 1 週（63.33%）、變化寫第 2 週減第 1 週，兩者不一致；設計以「最新一週」為主數字（差異 3）。
- `SH_NOTE`：股票、ETF 兩段說明，逐字照 PM。
- `shChart(sh, E, mk)`：用 `buildChip` 的 `mk` 建 `shC`（兩條線）、`snC`（一條線），時間軸 = `sh.d`（固定全部，最多 52 週，和 `chipN` 無關）；圖例預設最後一週，任一張圖十字線移動時兩張圖例一起換成該週；**不加入** `anchors`（不和日資料的籌碼圖十字線同步），兩張週圖之間也不同步十字線（只同步圖例）。回傳兩張圖，由 `buildChip` 加入 `charts`。
  - 圖 1 圖例：`<b>11/20</b>`、`超過 400 張 63.33%`（實線色塊）、`50 張以下 22.99%`（虛線色塊，inline `border-top:2px dashed`）、`超過 50 至 400 張 13.68%`。
  - 圖 2 圖例：`<b>11/20</b>`、`股東 53,095 人`（ETF `受益人`）。

### 5-3 `buildChip`（＋1 行）

- `charts = anchors.map(a => a[0]);` 的下一行：`if (data.sh && data.sh.d.length >= 2 && $('#shC')) charts.push(...shChart(data.sh, E, mk));`。切換圖表區間時整個籌碼分頁重建，`disposeKCharts` 一併釋放週圖。

### 5-4 線色（不用 `--up`／`--dn`）

| 用途 | 色 | 白底 `#fff` | 深色卡片 `#17181b` |
|---|---|---|---|
| 超過 400 張（實線） | `#4C6EF5` | 4.32 | 4.11 |
| 50 張以下（虛線，`lineStyle: 2`） | `#DB6E00` | 3.36 | 5.28 |
| 人數 | `#1C7ED6` | 4.20 | 4.23 |

- PM 建議的 `#F08C00` 白底只有 2.48（低於非文字 3:1），改用 `#DB6E00`（D117）。兩條線藍／橘不同色相，另以實線／虛線區分。

### 5-5 版面、相容

- 只用既有 `metrics kv`、`.chip-g`、`.ch-label`、`.lg`；`app.css` 不改。
- 實看（模擬資料）：1024 深色一組一列、兩張週圖正常；320 淺色卡片 2 × 2、`scrollWidth = innerWidth = 320`、圖例換行不撐寬。觀察：320 寬時副標「（百分點）」會折到第二行（PM 希望一行；卡寬約 126px 放不下），不影響閱讀，列 QA 觀察。
- 新 JS 不用 `.at(`、`??`、`?.`、`||=`、`&&=`、`replaceAll`、`structuredClone`、`Object.hasOwn`、`findLast`、`parseFloat(`；node 14.17 執行通過。

## 六、測試 `tests/test_iter43.py`（14 個，566 行）

| 測試 | 驗收 | 內容 |
|---|---|---|
| `test_parse` | 1～3 | 真實節錄 7 代號 × 17 列（000218、00406A、0050、01001T、2330、2421、2881A，含 BOM、CRLF、右補空白）：資料日、保留代號、去空白、2421／00406A／0050／2330 全部欄位等於原始檔；合計驗算 5 種假資料各只略過 2421；`SchemaError` 7 種 |
| `test_write` | 4、5 | 假連線：URL、`expect_json=False`、`isolated=True`；一個 MERGE、JOIN、WHERE、`OUTPUT`、參數順序、BIGINT 原樣；官方未更新與回退不連資料庫；三種輸出逐字；0 列可寫不連資料庫 |
| `test_timing` | 6、7、10、17 | 情境表（PM 1～15 ＋ 9 之後、11 之後共 17 列）逐列驗 `last_full_week` 與 `make_plan["tdcc"]`；表不存在、舊呼叫不排；`plan_for_date` 沒有 `tdcc`；只有 `tdcc` 時 `plan_is_empty` 為否；`__main__.py`、`history.py` 不碰 |
| `test_world` | 6、9、11 | `SdWorld`（World ＋ getOD ＋ 假 `share_distribution`）跑 `collect --catch-up`：情境 4（ℹ️、記 `on`、不匯出）、5（同一天 0 次）、6（隔天寫入、匯出 1 次、`new_data` = 1、🏦 行）、2、16（`--date` 0 次）、11（`AD_HOC` 拿掉 10/23：10/24 寫入 10/22，10/27 0 次）、17（表不存在 0 次、沒有「集保」字樣、沒有 MERGE） |
| `test_isolation` | 8 | getOD 回 500：只打 1 次、主機沒被標記、⚠️ 文字；回傳碼、`new_data`、`items`、通知、匯出和「沒有這功能（表不存在）」相同；`undated` 沒有 `tdcc`；同一天下一次執行再打 1 次 |
| `test_state` | 12 | 取最近一筆有 `tdcc` 的 `on`；舊格式、空紀錄；只查 `collect_runs` 一次 |
| `test_lines` | 11、13 | 4 種文字逐字、位置在預告那行之後、其他行與回傳碼不變、舊呼叫不印；12/1 不加 ⚠️、12/7 加；春節 3/2 不加、3/9 加；World 下 `run_check` 印「尚未建立資料表」、回傳 0 |
| `test_export` | 14～16 | 手算 5 檔（含 000218 整數 `100`）、`28.9` 去尾 0、股票／ETF 分流；假資料 53 週只留 52、1.005 進位到 1.01、缺週不補、ETF 只進 `etfp`、空輸入 |
| `test_export_wiring` | 16、17 | `sh` 在 `fh` 之後、ETF 在 `nx` 之後 `_write` 之前、`sh_stock`／`sh_etf` 出現次數、讀取在 `conn.close()` 之前、表不存在只下 1 個查詢、`TOP {SH_WEEKS}` |
| `test_setup_db` | 文件 | DDL 7 個片段、不存比例、README 與 `dblayout.md` 有新表 |
| `test_cards` | 18、20 | node：股票 2 週、ETF 2 週、股票 1 週、股票 5 週的 4 張卡逐字；組標題與右側小字、圖容器、圖標題（股東／受益）、兩段說明逐字；1 週的「自 11/20 起收錄…」；沒有 `sh`、`sh.d` 為空 → `''` |
| `test_charts` | 19 | node（沿用 `test_iter28` 的假 LightweightCharts，`chipN = '2'`）：5 週 → 7 張圖、`charts` 也 7 張、週圖線色／虛線／點數 5（和 `chipN` 無關）、圖例逐字、十字線換週、重建時釋放；1 週、沒有 `sh` → 5 張；ETF → 4 張、「受益人」 |
| `test_wiring_and_words` | 22、23、27 | 4 個 `?v=`；新 JS 的 node 14 語法；新程式（`tdcc.py`、新 health／export／tradingcal 函式、新 JS）沒有禁用詞 |
| `test_contrast` | 25 | 反證 20 種（下表） |

- 反證：

| 類 | 改壞的地方 | 擋下的檢查 |
|---|---|---|
| Python | 比日期不比週（`latest` < target 週五） | timing、world |
| | `tdcc` 失敗算進 `undated_errors` | isolation |
| | `isolated=False` | isolation、write |
| | 同一天抓到舊週後再抓（拿掉 `tdcc_on`） | timing、world |
| | `load_state` 取最舊 | state |
| | `collect --date` 也抓 | timing、world |
| | 表不存在也排 | timing |
| | 合計驗算不扣 16 級 | parse |
| | 拿掉 `strip()` | parse |
| | 分母改 1～15 級股數和 | export |
| | 週數上限改 26 | export |
| | 浮點四捨五入 | export（1.005） |
| | 新週不算有新資料（拿掉 D115 那行） | world（匯出次數） |
| | 落後門檻改 1 週 | lines |
| JS | ETF 卡片寫「股東人數」 | cards |
| | 少於 2 週也畫圖 | charts |
| | 少於 2 週也放圖的容器 | cards |
| | 週圖跟 `chipN` 連動 | charts |
| | 4 週改和第 3 筆比 | cards |
| | 50 張以下改實線 | charts |

- PM 反證「比例改用官方比例相加」不適用：官方比例欄不解析、不存（R48），程式拿不到官方比例；2330 自算 86.91（官方相加 86.89）由 `test_export` 鎖定。
- 測試裡的禁用詞清單本身是檢查用字串，不是使用者看得到的文字（比照前幾輪）。

## 七、檔案與行數（`git apply --numstat`）

| 檔案 | ＋／− | PM 估計（上限） |
|---|---|---|
| `twstock/collectors/tdcc.py`（新檔） | ＋100 | 約 95（124） |
| `twstock/tradingcal.py` | ＋24 | （PM 算在 tdcc.py 內） |
| `twstock/db.py` | ＋19／−1 | 約 15（20） |
| `twstock/collectors/catchup.py` | ＋17／−6 | 約 25（33） |
| `twstock/health.py` | ＋37／−5 | 約 30（39） |
| `twstock/export.py` | ＋39／−1 | 約 40（52） |
| `site/stock.js` | ＋33 | 約 45（59） |
| `site/index.html` | ＋1／−1 | — |
| **程式小計** | **＋270／−14** | 約 250（PM 程式合計 270 含文件） |
| `README.md` | ＋4／−2 | 約 20（26），三份文件合計 |
| `docs/dblayout.md` | ＋57／−2 | 同上（欄位表 39 列逐欄列出，超過估計） |
| `docs/iterations/README.md` | ＋1 | — |
| `tests/test_iter43.py` | ＋566 | 約 430（559），**超出 7 行**，在工作階段上限 580 內 |

## 八、和 PM 的差異

| # | 差異 | 原因 |
|---|---|---|
| 1 | 目標週純函式放 `tradingcal.py`（`last_full_week`、`weeks_behind`、`week_of`），不放 `collectors/tdcc.py` | `health.py` 不匯入 collectors；`tradingcal` 已被 health、catchup 共用 |
| 2 | `make_plan` 的新參數是 `share`（`share_state` 的結果），`plan["tdcc"]` = `{"latest": …}` 或 None | 讓 `execute_plan` 拿到 `latest`；None 同時代表「不排」 |
| 3 | 卡片主數字用最新一週 | PM 表的主數字與週變化不一致 |
| 4 | 50 張以下線色 `#DB6E00`（PM `#F08C00`） | 白底對比 2.48 → 3.36（D117） |
| 5 | 兩張週圖只同步圖例、不同步十字線 | PM 讓 SA 定；少一組同步邏輯 |
| 6 | `share_state` 收集時也查檔數 | 收集與 `check` 共用一個函式；多一個走索引的查詢 |
| 7 | 級距文字沒有再看官方網頁表頭 | 本角色不得發外部請求（D116） |
| 8 | `docs/dblayout.md` 增加 57 行 | 寬表 39 欄逐欄列出，比照該文件格式 |

## 九、風險

| 風險 | 說明 | 緩解 |
|---|---|---|
| 程式更新後還沒 `setup-db` | 表不存在 | 收集不排、匯出不讀、`check` 提示；測試以 World 驗過 0 次請求 |
| `OUTPUT` 子句 | 若日後在表上加觸發程序，`OUTPUT` 沒有 `INTO` 會失敗 | 本專案不用觸發程序；失敗時是 `pyodbc.Error`，走 `_db_failed`（明顯，不會默默少寫） |
| 官方公布時間（Q43-1）、更正重發（Q43-5）、改頻率（Q43-2） | — | 同 PM；`check` 落後 2 週 ⚠️ |
| 官方改格式 | — | `SchemaError` 整份不寫、只 ⚠️ |
| 第一週來不及（11/28 換檔） | — | 二之八時程；F43-6 備用（需另外同意） |
| 320 寬副標折行 | 「（百分點）」換到第二行 | QA 觀察；要一行需縮短文字（例如拿掉「（百分點）」改寫在組說明），另案 |
| 模擬資料只在前端驗 | 真實 `sh` 要等套用後 | 二之八第 7 步抽查 |

## 十、PG 套用步驟與上線步驟

### 10-1 套用程式（不連資料庫，可隨時做）

1. `git apply --check docs/iterations/43/03-design.diff`，通過後 `git apply docs/iterations/43/03-design.diff`。
2. `for f in tests/test_iter*.py; do python3 -u $f >/dev/null 2>&1 || echo FAIL $f; done`，43 個全部通過（`test_iter39` 需要 `site/data`）。
3. 這時資料庫還沒有新表：排程收集、匯出都照舊，`check` 多一行「集保股權分散：尚未建立資料表…」。

### 10-2 上線（寫資料庫，**需使用者同意後才執行**；11/23 晚第 40 輪上線確認之後、11/24～11/27 任一晚、排程跑完之後）

1. `python3 -u -m twstock backup`
2. `python3 -u -m twstock setup-db`，再跑一次確認可重複執行、不報錯。
3. 記下 `collect_runs` 最近一筆的請求數，然後 `python3 -u -m twstock collect --catch-up`（不要和排程同時跑）：
   - 輸出有 `  🏦 集保股權分散 2026-11-20：股票 N 檔、ETF M 檔`（預期 N ≈ 1,992、M ≈ 367）。
   - 請求數比同樣情況多 1（行情已齊時就是 1）；自動匯出（印出匯出耗時）。
4. 再跑一次 `collect --catch-up`：沒有 🏦 行、0 次 opendata 請求。
5. 若第 3 步沒有匯出，`python3 -u -m twstock export`。
6. `python3 -u -m twstock check`：`集保股權分散最新一週：2026-11-20（股票 N 檔、ETF M 檔）`，回傳碼和套用前相同。
7. 抽查 `site/data/stocks/2421.json`、`etfp/00406A.json`、`etfp/0050.json` 的 `sh` 和第三節表格相同；8001 冒煙測試 2421、0050 籌碼分頁有 4 張卡、沒有圖、「自 11/20 起收錄，累積 2 週後顯示走勢。」；測完關 8001。
8. 11/30（一）晚之後（第 43 輪上線確認）：`check` 最新一週 11/27、籌碼頁出現兩張週圖。

- 不回補；不安裝排程、不改系統設定。

## 十一、需要使用者決定的事項（D116 起；已 grep `docs/`，目前最大 D115）

| 編號 | 問題 | 選項 | SA 建議 |
|---|---|---|---|
| D116 | 級距文字（Q43-3）怎麼確認 | **A** 照集保標準級距（分析師 3-4 節）上線；上線確認時由使用者或 QA 開集保查詢網頁看一次表頭（只看頁面，0 次資料查詢），不符再改畫面文字（程式只依分級編號，不用改表）；**B** 套用前先另派一次網頁查證再開發 | **A**：畫面只用到「超過 400 張」「超過 1,000 張」「50 張以下」「未滿 1 張」4 個邊界，都是財經網站通用的標準級距 |
| D117 | 「50 張以下」線色 | **A** `#DB6E00`（白底 3.36、深色 5.28，非文字對比 ≥ 3:1）；**B** 照 PM `#F08C00`（白底 2.48） | **A**；設計已照 A 做 |

## 使用者決定（2026-11-22）

- **D116 = A**：照集保標準級距上線；上線確認時開集保查詢網頁看一次表頭（只看頁面），不符只改畫面文字。
- **D117 = A**：「50 張以下」線色用 `#DB6E00`。
