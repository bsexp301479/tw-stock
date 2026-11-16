# 第 24 輪｜System Analyst：F24-5 股利金額與 ETF 除息入表、F24-6 股利與填息、F24-7a～f、F24-8 法人官方合計設計

- 撰寫日期：2026-11-14（週六）
- 依據：
  - `24/02-pm.md`：範圍、驗收條件、3-2 開工前提、3-3 上線步驟、5-2 的 24 項舊斷言、第六節提示。
  - `24/01-analyst.md`：口徑、實例、D36-1～D36-16。
  - `23/03-design.md`（格式）、`19/03-design.md`（`events.py` 與 `div_ref` 回補的做法）。
  - 使用者決定：**D36 = A**，範圍 F24-5、F24-6、F24-7a～f、F24-8；**D36-1～16 照分析師預設**；**D37-1～8 照 PM 預設**。
- 原型作業：
  - 在 scratchpad 的 `sa24/` 建兩份專案副本：
    - `orig` = 目前工作目錄（`a739f23`，除了 `docs/iterations/24/` 沒有變更）。
    - `proj` = 本設計。
    - 兩份都**不含 `.env`**、`_archive`、`logs`、`.git`；`site/data` 由各自的唯讀模擬匯出產生。
  - 唯讀模擬匯出（`sa24/run_export.py`）：
    - 包一層連線，所有 SQL 先檢查不是寫入指令，結束 rollback。
    - 資料庫還沒有 3 個新欄位，所以 `proj` 的事件查詢改成 `LEFT JOIN OPENJSON(…)`，金額取自分析師原始回應（`scratchpad/r24/raw/`）用新的 `parse_events_all` 解析的結果。等同「回補完成後」的資料。
    - 輸出寫到各自的 `site/data`（scratchpad）。**沒有寫專案的 `site/data`。**
    - 帳密由 `sa24/dbenv.py` 以 setdefault 讀進環境變數，沒有印出或複製 `.env`。
  - SQL 語法只用 `SET PARSEONLY ON` 檢查（`sa24/parseonly.py`）：
    - 先用 `SELECT 1/0` 證明不會執行，再用故意寫錯的 MERGE 證明會報錯。
    - 新的 DDL 4 條、MERGE 2 段都通過；結束後 `etf_events` 仍不存在，`price_events` 欄位不變。
  - 8001 預覽：`proj` 執行 `serve --port 8001 --no-browser`，結束時已關閉；8000 沒有碰。
    - 預覽前 localStorage 0 個鍵；預覽時新增的 `tw.stockTab` 已刪除，**結束時 0 個鍵**。視窗已恢復 desktop 大小，分頁已關閉。
  - **外部請求 0 次、資料庫寫入 0 次**。前後查 `collect_runs`：最大 17，沒有進行中的收集（`finished_at` 為 NULL 0 列）；資料日 2026-11-13。
  - 沒有修改專案程式，沒有 commit。本文件是唯一寫進專案的檔案。
- 基線：資料日 **2026-11-13（週五）**；`stocks/` 1,999 個檔；`price_events`：`TWT49U` 958、`TPEX_EX` 720、`TWTAUU` 20、`TWTB8U` 3。

---

## 〇、變更總覽

| 檔案 | 內容 | ＋／− |
|---|---|---|
| `twstock/collectors/events.py` | `_AMOUNTS`；新增 `parse_events_all`（股票＋ETF）；`parse_events` 回傳不變；`fetch_events` 回傳兩份；`collect_events` 回傳 `{"stocks", "etfs"}`，`price_events` MERGE 加 3 欄、新增 `etf_events` MERGE | ＋63／−19 |
| `twstock/db.py` | `etf_events` 表；`price_events` 加 `div_total`、`div_cash`、`stock_div`（各一行 `IF COL_LENGTH`）；`setup-db` 輸出清單 | ＋21／−1 |
| `twstock/export.py` | 新增 `dividends`；事件查詢多讀 3 欄（`"a"`）；個股檔加 `dv`、`insti.n` | ＋40／−4 |
| `twstock/collectors/catchup.py` | 事件筆數進 `undated.events`；休市日訊息；`data_date` 用兩市場最新日（QA-03）；`export_failed` 補匯出（QA-09） | ＋9／−7 |
| `twstock/health.py` | `load_state` 加 `events_at`、`events_n`、`warnings`、`export_failed`；`check_report` 加事件一行與警告 | ＋17／−3 |
| `twstock/collectors/history.py` | 只選月資料集時「待抓 N 個月」「成功：N 個月」 | ＋5／−3 |
| `twstock/fetch.py` | `isolated=True` 失敗訊息 | ＋2 |
| `twstock/__main__.py` | `cmd_events` 加鎖；docstring | ＋8／−1 |
| `site/stock.js` | `NET_TIP`、`dfmt`、`divHTML`；基本面分頁季報卡之後插入股利卡；`inst.net` 用 `I.n`；圖例合計加 `title` 與「（每日相加）」 | ＋29／−3 |
| `site/app.css` | `.dv-tbl` 一行 | ＋1 |
| `site/index.html` | `app.css`、`stock.js` 的 `?v=` | ＋2／−2 |
| `README.md` | `setup-db` 清單、`check`、`events` 三行；股利與填息、法人合計兩段 | ＋5／−3 |
| `tests/test_iter24.py`（新） | 16 個測試 | 545 行 |
| `tests/fixtures/`（新） | `twt49u_div_mini.json`（20 列）、`exdailyq_div_mini.json`（20 列）、`dv_prices_mini.json`（7 檔日線） | 約 52 KB |

- 程式＋README **＋202／−46**。
- **舊測試 0 行修改**（D37-8）：`test_iter01`～`23` 全部通過，第五節 5-2 的 24 項都用實作避開（見第十節 10-4）。
- 輸出：
  - `latest.json`、`screen.json`、`etfs/`、`etfp/` 和改前**逐位元組相同**。
  - `stocks/` 只多 `dv` 和 `insti.n`；刪掉這兩個鍵後**逐位元組相同**。

---

## 一、資料來源、欄位與 DDL（F24-5）

### 1-1 來源欄位

| 新欄位 | 型別 | 上市 `TWT49U` | 上櫃 `TPEX_EX`（exDailyQ） | `TWTAUU`、`TWTB8U` |
|---|---|---|---|---|
| `price_events.div_total` | `DECIMAL(12,6) NULL` | 「權值+息值」（息、權、權息都存） | 「權值+息值」 | NULL |
| `price_events.div_cash` | `DECIMAL(12,6) NULL` | 只有「息」：＝「權值+息值」；「權」「權息」NULL（D36-9） | 「息值」 | NULL |
| `price_events.stock_div` | `DECIMAL(14,8) NULL` | NULL（官方表沒有） | 「每仟股無償配股」（0 也照存） | NULL |
| `etf_events.div_cash` | `DECIMAL(12,6) NULL` | 「權值+息值」（ETF 只收「息」） | 「息值」 | — |

- 位數：官方「權值+息值」「息值」6 位小數，「每仟股無償配股」8 位（5511 為 198.87165021）。`DECIMAL(14,8)` 可存到 999,999.99999999 股。
- 分析師原始回應全量比對：存成 DECIMAL 後和原值不同 **0 筆**（`sa24/dbcheck_pre.py`）。
- 欄位找不到、值無法解析（`--`、空白）：該欄存 NULL（`clean_number` 回傳 None 就不放鍵），事件照常寫入，和第 19 輪 `div_ref` 相同。
- 上櫃「息值」和「現金股利」兩欄，分析師比對 1,352 筆 0 筆不同；本設計用「息值」（PM 表）。

### 1-2 DDL（`db.py` 的 `DDL`，可重複執行）

- 新表放在 `etf_sbl` 之後、「第 11 輪：發行股數」之前（`etfs` 已經先建，外鍵可建）：

```sql
IF OBJECT_ID('etf_events') IS NULL
CREATE TABLE etf_events (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    etf_id      INT           NOT NULL REFERENCES etfs(etf_id),
    event_date  DATE          NOT NULL,   -- 官方除息日
    event_type  NVARCHAR(4)   NOT NULL CHECK (event_type IN (N'息', N'權', N'權息')),
    prev_close  DECIMAL(10,2) NOT NULL,
    ref_price   DECIMAL(10,2) NOT NULL,
    div_cash    DECIMAL(12,6) NULL,       -- 每單位配息：上市「權值+息值」、上櫃「息值」
    source      NVARCHAR(10)  NOT NULL,   -- TWT49U / TPEX_EX
    created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_etf_events UNIQUE (etf_id, event_date, source)
)
```

- 3 個新欄位放在第 19 輪 `div_ref` 那一行**之後**，各自一行（`div_ref` 那一行逐字不動，`test_iter19` 第 94 行）：

```sql
IF COL_LENGTH('price_events', 'div_total') IS NULL ALTER TABLE price_events ADD div_total DECIMAL(12,6) NULL
IF COL_LENGTH('price_events', 'div_cash') IS NULL ALTER TABLE price_events ADD div_cash DECIMAL(12,6) NULL
IF COL_LENGTH('price_events', 'stock_div') IS NULL ALTER TABLE price_events ADD stock_div DECIMAL(14,8) NULL
```

- `CHECK` 允許「權」「權息」：兩個來源目前 ETF 只有「息」，程式也只寫「息」；留著是為了第 25 輪若要收 ETF 的其他類型不必改表。
- `setup-db` 的輸出清單在 `etf_holding_gaps` 之前加「`etf_events`（第 24 輪另加 price_events 股利欄）」。**清單最後仍是 `etf_holding_gaps")`**（`test_iter06` 第 143 行比對這個字面）。
- 重複執行：4 條都以 `IF` 開頭；第二次執行全部略過。舊程式相容：新欄位允許 NULL、新表獨立，舊 `events.py` 的 INSERT 有列出欄位名稱、舊 `export.py` 的 SELECT 也列出欄位名稱，不受影響。

---

## 二、解析與寫入（F24-5）

### 2-1 `parse_events` 的預設回傳不變

- 新增 `parse_events_all(source, fields, rows) -> (stocks, etfs)`，`parse_events` 改成：

```python
return [{k: v for k, v in r.items() if k not in ("div_total", "div_cash", "stock_div")} for r in parse_events_all(source, fields, rows)[0]]
```

  - 所以 `test_iter02` 第 49～71 行、`test_iter19` 第 26～30 行的整個 dict 比對、`len(tp) == 114` 都不變（ETF 進的是第二份，股票那份不含 ETF）。
- `parse_events_all` 的規則：
  - 必要欄位缺漏 → `([], [])`。
  - 金額欄 `_AMOUNTS = {"TWT49U": ("權值+息值", None, None), "TPEX_EX": ("權值+息值", "息值", "每仟股無償配股")}`；其他來源沒有。
  - 上市「息」：`div_cash = div_total`。
  - 金額是 None 就**不放鍵**（MERGE 的 OPENJSON 讀到 NULL，`COALESCE` 保留舊值）。
  - 代號分流：`is_valid_stock_code` → 股票；否則 `is_etf_code` 而且來源在 `_AMOUNTS`、類型是「息」→ ETF；其他（ETN `02`、受益證券 `01`、特別股 `2882A`、`8349A`）兩份都不收，和現在相同。
  - ETF dict：`{etf_code, event_date, event_type, prev_close, ref_price, source, div_cash?}`。

### 2-2 寫入：ETF 不會進 stocks 相關查詢

- `collect_events` 的 `price_events` MERGE：
  - `OPENJSON WITH` 多 `div_total DECIMAL(12,6), div_cash DECIMAL(12,6), stock_div DECIMAL(14,8)`（另起一行，`div_ref DECIMAL(10,2)` 字面保留）。
  - `UPDATE SET` 在 `div_ref` 那一行之前另起兩行：

```sql
div_total = COALESCE(s.div_total, t.div_total), div_cash = COALESCE(s.div_cash, t.div_cash),
stock_div = COALESCE(s.stock_div, t.stock_div),
div_ref = COALESCE(s.div_ref, t.div_ref)     -- 欄位暫時找不到時不清掉已存的值
```

  - `INSERT` 多這 3 欄。仍然 `JOIN stocks`，股票那份本來就不含 ETF。
- 第二段 MERGE `etf_events`：`JOIN etfs et ON et.etf_code = j.etf_code`（只寫 `etfs` 已有的 ETF），`div_cash = COALESCE(s.div_cash, t.div_cash)`。
- 兩段在同一個連線，一次 commit；兩份各自依 `(代號, 日期, 來源)` 去重。只要有任一份就連線，兩份都空就不連資料庫。
- ETF 只存在 `etf_events`，`price_events`、`stocks` 不會有 ETF；個股匯出、選股、市場寬度等所有 `JOIN stocks` 的查詢都不受影響（D36-13）。
- 輸出：`  📌 除權息／減資／面額變更事件：股票 N 筆、ETF M 筆（起 ～ 迄）`；回傳 `{"stocks": N, "etfs": M}`。
- 唯讀比對（分析師原始回應 2025-10-30～2026-11-14 × 資料庫）：
  - 股票：`TWT49U` 958、`TPEX_EX` 720 筆，**全部 JOIN 得到 `stocks`**，既有欄位（類型、前收、參考價、`div_ref`）0 筆不同，資料庫沒有的 0 筆，資料庫有而回應沒有的 0 筆。
  - ETF：上市 508 筆（113 檔）、上櫃 630 筆（106 檔），**全部 JOIN 得到 `etfs`**（219 檔），全部是「息」，在 `stocks` 表 0 筆，市場別全部相符。
  - 兩份都不收：上市 44 筆、上櫃 2 筆（`8349A`、`020035`），和 PM 相同。

---

## 三、回補指令與請求數

- 指令：`python3 -m twstock events --start 2025-10-30`（`--end` 預設今天）。
- 2025-10-30～2026-11-17 共 384 天，`CHUNK_DAYS = 183` → 3 段 × 4 個端點 = **12 次**。中途失敗只重跑一次，總計 ≤ 24 次（MERGE 可重跑）。
- `events` 已經加鎖（F24-7f），每晚的收集進行中時會印提示並回傳 1、0 請求。
- 每晚收集照舊往回查 7 天，請求數不變（股利金額與 ETF 都來自原本的回應）。

---

## 四、股利與填息演算法（F24-6）

### 4-1 `export.dividends(d_, c, ev, official)`

- 輸入：該股日線日期 `d_`、原始收盤 `c`、`_price_events` 的 `ev`、同一檔的官方事件 `official`（多了 `"a"` = `(div_total, div_cash, stock_div)`）。
- **列入**（D36-6）：`息`、`權息`；`權` 只在 `k` 是 `s`、`sc`（純配股或股利＋現增）時列入，**只列、不算填權**。`k = c`（只有現增）或分類不明的「權」不列。
- **事件日對應**：直接用 `ev` 的 `i`（和 `ev` 同一套 `_price_events` 規則：休市日的事件生效於下一個交易日；資料第一列或最後一列之外的事件略過）。所以 `dv` 每一列的 `d`、`p` 一定等於同檔 `ev` 的 `d`、`p`。
- **金額**：在 `official` 找 `bisect_left(d_, x["d"]) == i`、而且 `(t, p, r)` 相同的那一筆，取 `"a"`。
- **填息**（D36-1～5）：從事件列 `i`（含）往後找第一個 `c[j] ≥ p` 的列；`n = j − i + 1`（事件列 = 第 1 天，無成交日也算）；原始價、不設期限。
- **不再比較**（D37-1）：還沒填息就遇到之後的股本變動（`j > i` 而且 `j` 是下列事件），停在那一列，`x = [日期, 原因]`：
  - `權`、`權息` 而且 `k ≠ c`：`k = s` 寫「配股」，其他寫「除權」「除權息」。
  - `減`「減資」、`面`「面額變更」、`調`（上櫃反推）「股本變動」。
  - **同一列又是股本變動又收盤 ≥ 前收：算不再比較**（那天的收盤已經是股本變動後的價格）。
  - 只有現增（`k = c`）不算。
- 未填息、也沒有遇到股本變動：沒有 `f`、`n`、`x`，前端從 `prices` 取最新收盤算還差多少。

### 4-2 `dv` 的格式（舊到新；沒有紀錄是 `[]`）

| 鍵 | 內容 | 何時有 |
|---|---|---|
| `d` | 除權息日（`ev` 的日期） | 一定 |
| `t` | `息`、`權息`、`權` | 一定 |
| `k` | 除權類型（`s`、`sc`） | 權、權息而且有分類 |
| `c` | 每股現金股利 | 有值時（上櫃權的 0.0 也輸出） |
| `s` | 每千股配股 | 有值而且不是 0 |
| `a` | 權值＋息值 | **只在沒有 `c` 時**（上市權、權息的 `title` 用） |
| `p` | 除權息前收盤 | 一定 |
| `f`、`n` | 填息日、第幾個交易日 | 已填息 |
| `x` | `[日期, 原因]` | 不再比較 |

### 4-3 驗算（fixture 與全市場）

| 股票 | `dv` | PM 驗收 |
|---|---|---|
| 2421 | `{"d":"2026-06-10","t":"息","c":5.24042,"p":160.0,"f":"2026-08-28","n":56}`；2/24 現增不列 | #1 ✅ |
| 2330 | c 5.000011／6.000035／6.000035／7.000001；n 11（12/26）、1（3/17 當天）、2（6/12）、2（9/17） | #2 ✅ |
| 6488 | 12/31 c 2.0，01/05 第 3；7/16 c 5.7，尚未填息（最新收盤 630 → 還差 850.00 元，+134.92%） | #3 ✅ |
| 6669 | 6/22 c 144.391544，07/02 第 9；9/02 `權` `k:s`、`a` 5185.002642，沒有填權欄 | #4 ✅ |
| 8112 | `權息` `k:sc`、`a` 5.36055、08/11 第 26 | #5 ✅ |
| 5511 | `權息` `k:s`、c 3.6、s 198.87165021，尚未填息 | #6 ✅ |
| 6703 | 3/26 c 4.8，`x: ["2026-07-16","配股"]`；7/16 `權` `k:s`、c 0.0、s 100.00000916 | #7 ✅ |

- fixture（`tests/fixtures/`）重現上表 7 檔（`test_dividends_real`）。
- 全市場（唯讀模擬匯出）：
  - 類型：息 1,432、權息 110、權 38，**合計 1,580**（`k = c` 0 列）。
  - 四類：已填息 992、尚未填息 530、不再比較 20、配股 38。
  - 不再比較的原因：配股 17、減資 1、除權息 1、股本變動 1（例：6176 減資、3260 除權息、4527 股本變動）。
  - 沒有任何紀錄（`dv: []`）545 檔。
  - 和分析師口徑對帳（`sa24/recon.py`）：差異都能用 D37-1、純配股不算、事件在資料第一列解釋。

---

## 五、F24-7a～f

| 子項 | 改法 | mock 測試 | 反證（舊程式或突變後失敗） |
|---|---|---|---|
| **7a** 事件筆數 | `execute_plan`：`got = {}`；`_guard("events", errors, lambda: got.update(collect_events(*plan["events"])))` 成功時 `undated["events_to"]` 照舊，另存 `undated["events"] = {"stocks": n, "etfs": m}`。失敗時兩個鍵都沒有，`errors` 有 `events` | `test_detail_events_count`：`World` 子類別讓 TWT49U 回 4 列股票、2 列 ETF → `undated.events == {"stocks": 4, "etfs": 2}`；端點 500 → rc 1、沒有筆數鍵 | 舊程式 `KeyError: 'events'`；刪掉那一行 → 失敗 |
| **7b** `check` 新行 | `load_state` 的 SELECT 改成 `finished_at, new_data, detail, command, outcome, export_seconds`，新增 `events_at`、`events_n`（事件最後成功那一筆的完成時間與 `undated.events`）、`warnings`（最後一次收集的 `detail.warnings`）、`export_failed`。`check_report` 在「處置／注意股最後成功」之後加：<br>`除權息事件最後成功：至 {events_to}（YYYY-MM-DD HH:MM），股票 n 筆、ETF m 筆（含往回 7 天重查）`；沒有紀錄寫「除權息事件最後成功：尚無執行紀錄」；舊紀錄沒有筆數時只寫日期。<br>每條警告一行：`⚠️  最後一次收集的警告：…`。都不算異常（D37-5） | `test_check_lines`：`{}`、舊格式、有筆數與警告各一；rc 不變、沒有新的 ❌ 行、新行不在第 1、2 行與最後一行、其他行逐行不變。`test_load_state_new_keys`：6 欄、4 欄、3 欄假資料 | 舊程式缺鍵；刪掉警告那一行、`export_failed` 不看耗時 → 失敗 |
| **7c** QA-07 訊息 | ① 休市日 `--date`（`plan["days"]` 是空的）：`✅ 休市日沒有要抓的資料，不需要請求`。② `history`：沒有以日為單位的資料集時寫「待抓 N 個月」「✅ 成功：N 個月」（`month_ok` 在 `collect_tpex_index` 成功時 +1）；以日為單位的照舊。③ `fetch.request(isolated=True)` 失敗：`{host} 附屬查詢失敗（不重試，收集繼續）：{last_err}`；`isolated=False` 不變 | `test_qa07_messages` | 舊程式三處都失敗；各自突變 → 失敗 |
| **7d** QA-03 | 原因：`data_date` 只看上市，`status_changed` 用它算的狀態和匯出端（兩市場最新日）不同，只有上櫃公布時每次都判成變動。改法：`data_date` 改用兩市場最新日，刪掉 `site_date`，`site_closed(closed, data_date)` | `test_qa03_tpex_only`（`run_site`，真的 `status_changed`）：上櫃先公布 → 匯出 1 次 → 0 → 0；上市公布 → 再 1 次 → 之後 0 | 舊程式第 2 次就再匯出（`AssertionError: 17`） |
| **7e** QA-09 | `need_export` 多 `or state.get("export_failed")`：最近一筆「有新資料或有匯出耗時」的紀錄是 `abnormal` 而且 `export_seconds` 是 NULL。`--no-export` 不補 | `test_qa09_retry_export`：`Cursor24` 記錄 outcome 與耗時；只有沒有日期的資料變動、匯出失敗 → 下一次補 → 補又失敗 → 再補 → 成功後 0 次；`--no-export` 那次 0、下一次補；沒有新資料又上次成功 → 0 次 | 舊程式第 2 次 0 次匯出 |
| **7f** `events` 加鎖 | `cmd_events` 照 `cmd_history`：`acquire_lock()`，拿不到印「⏭️  另一個收集程序正在執行，請稍後再跑（同時跑會超過網站節流）」回傳 1；`finally: release_lock(lock)` | `test_events_lock`：拿不到鎖 → rc 1、`collect_events` 沒被呼叫、0 請求、不連資料庫；正常、`FetchError`、其他例外都會釋放 | 舊程式沒有鎖 |

- QA-09 的條件只看「有新資料或有匯出耗時」的最近一筆，所以：
  - 沒有新資料、也沒有匯出的紀錄（每晚多次的空跑）不會蓋掉失敗的那筆。
  - 補匯出成功後那一筆有耗時，下一次就不再匯出。
  - `test_iter03` 第 1278～1287 行（有日期的資料、匯出失敗後補匯出）照樣通過；`env()` 之下沒有新資料、上次成功 → 0 次（5-2 第 15 項）。

---

## 六、F24-8（Q22-2）法人官方合計

- 匯出：`insti.n = [round(x / 1000) if x is not None else None for x in total]`，`total` 就是日線查詢已有的 `i.total_net`，和 `f`、`t`、`dl` 同一個寫法。
- 前端：`inst.net = has ? I.n?.[i] ?? inst.f + inst.t + inst.dl : null;`
  - 有 `n` 用 `n`；`n` 是 null 或舊 JSON 沒有 `n` 時退回三者相加；ETF 沒有法人資料仍是 null。
  - 週／月 K 的合計是每日 `n` 相加（`aggregate` 原本就逐日相加 `net`）。
  - 圖例：`<span class="lg" title="${NET_TIP}">合計${mode === '日' ? '' : '（每日相加）'} …`。`NET_TIP` 是常數，沒有新增 `noteHTML` 呼叫。
- 驗證：
  - **全市場 0 差異**：1,999 檔、493,242 列，`n` 和資料庫 `round(total_net / 1000)` 不同 0 列（附錄 B `iter24_db.py fill` 的最後一段）。
  - `n ≠ f + t + dl`：比較 464,036 列中 33,592 列（7.2%），最大差 1 張；11/13 有 157 檔。
  - 8001 實測 2330：日 K 圖例 −2,618／+2,946／+416，合計 +744；週 K 合計（每日相加）−4,039，三者相加 −4,038。

---

## 七、匯出 JSON 的變更

| 檔案 | 變更 | 大小 |
|---|---|---|
| `stocks/{代號}.json` | 新增 `dv`（陣列，見 4-2；沒有紀錄是 `[]`）；`insti` 新增 `n` | 36,728,446 → 38,713,770 bytes，**＋1,985,324（約 ＋1.9 MB）**：`dv` 約 113 KB、`insti.n` 約 1.87 MB |
| `latest.json`、`screen.json`、`etfs/`、`etfp/` | 不變（逐位元組相同） | 0 |

- `ev` 元素不加鍵（`dv` 另外組裝，`_price_events` 不動）。
- `cmp.py`（附錄 B）的結果：檔案數 2,373；`stocks/` 以外 0 個不同；`stocks/` 刪掉 `dv`、`insti.n` 後 0 個不同；`dv` 和 `ev` 不一致 0。

---

## 八、畫面（8001，`proj`）

### 8-1 股利與填息卡

- 位置：基本面分頁，月營收／季報那個 grid section **之後**（D37-2），`${data.dv ? divHTML(data.dv, data.market, P) : ''}`。舊 JSON 沒有 `dv` 時不顯示，不出錯。
- 表頭：`除權息日｜現金股利<br>（元）｜配股<br>每千股｜除權息<br>前收盤｜填息`；最新的在最上面。
- 各欄：
  - 除權息日：`2026/07/16`，非「息」加小字「除權」「除權息」（`EV_LABEL`）。
  - 現金股利：`c > 0` 顯示（最多 4 位小數、去尾 0，D36-12）；上市權息寫「--」，`title`「上市除權息的官方表只有權值＋息值合計 5.36055 元，無法拆分現金與配股」；上櫃純配股 c = 0 也寫「--」。
  - 配股：上櫃 `fmt(s, 2)`（198.87、100.00）；上市「權」或 `k = s` 寫「有」，`title`「上市的官方表沒有配股數；權值＋息值 … 元」；其他「--」。
  - 除權息前收盤：`pfmt`。
  - 填息：
    - `08/28`，小字「第 56 個交易日」；`n = 1` 寫「當天」。
    - `不再比較`，小字「07/16 配股後」。
    - `尚未填息`，小字「還差 850.00 元，+134.92%」；停牌股加「，最後成交 11/12」（D37-7）。
    - 純配股「--」，`title`「純配股不計算填權」。
- 說明：`noteHTML(short, full)`，`short` 是變數「填息 = 收盤回到除息前收盤；天數含除息日當天。資料自 2025-10-30 起」，`full` 寫口徑、無成交日算天數、純配股與現增、不再比較、上市權息的「--」、還差的算法。字面 `noteHTML('…'` 仍是 8 個（`test_iter13` 第 81 行）。
- 沒有紀錄：卡片只有一行「2025-10-30 起沒有除權息紀錄」（D37-3；實測 1213 大飲）。

### 8-2 實測（375、1024，深淺色；主控台 0 錯誤）

| 寬度 | 股票 | 表格寬 | 容器寬 | 頁面 `scrollWidth` |
|---|---|---|---|---|
| 375 | 2421、2330、6488、6669、8112、6703、5511 | 309 | 309 | 375（不水平捲動） |
| 375 | 最寬的候選 5289、2755、5548、4911，停牌 7782、6881 | 309 | 309 | 375 |
| 375 | 1213（沒有紀錄） | — | — | 375 |
| 1024 | 2330、6669、8112、6488 | 720（`max-width`） | 958 | 1024 |

- 375 寬的調整過程（寫給 PG、QA）：
  - 一開始表頭不換行，表格 460～529 px，填息欄被擠到容器外（要捲動才看得到）。
  - 改成表頭用 `<br>` 分兩行、`th`／`td` 左右內距 5 px、小字 `white-space: normal`，「不再比較」放主行、「07/16 配股後」放小字之後，上面所有股票都是 309 px。
  - 所以 `app.css` 只加一行：

```css
table.dv-tbl{max-width:720px}.dv-tbl td span{white-space:normal}.dv-tbl th,.dv-tbl td{padding-left:5px;padding-right:5px}.dv-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 24 輪 F24-6 股利與填息 */
```

- 深色：卡片、小字用既有的 `--text2`，對比和季報卡相同。
- 版本參數：改完 js／css 之後才算，`index.html` 為 `app.css?v=8ff7e8b4`、`app.js?v=b1f56347`（不變）、`stock.js?v=0a8a6929`；`test_iter23` 通過。

---

## 九、邊界情況

| # | 情況 | 處理 |
|---|---|---|
| 1 | 事件在資料第一列（2025-10-30） | `_price_events` 本來就略過（沒有前一天），`dv` 也沒有。這是 1,580 和分析師 1,581 差 1 列的原因 |
| 2 | 除息日休市、生效於下一個交易日 | 用 `ev` 的 `i`，和還原、`ev` 相同 |
| 3 | 除息日當天沒有成交 | 那一列算第 1 天；`c` 是 None 就跳過比較 |
| 4 | 除息日當天就填息 | `n = 1`，畫面「當天」 |
| 5 | 最後一天才除息 | 當天收盤 ≥ 前收就是當天填息；否則尚未填息 |
| 6 | 停牌、下市（最後一列不是資料日） | 照算，還差用最後成交收盤，加「最後成交 M/D」（11/13 有 6 檔，例：7782、6881） |
| 7 | 同一列填息又股本變動 | 不再比較（停止判斷在前） |
| 8 | 之後的「權」`k = c`（只有現增） | 不列、不停止 |
| 9 | 之後的「權」「權息」分類不明（沒有 `div_ref`） | 不列（權）；算股本變動（停止） |
| 10 | 權息 `k = c` | 「息」的部分照列、照算填息（11/13 沒有這種列） |
| 11 | 官方金額對不到（只有減資、面額變更來源，或前收、參考價不同） | 沒有 `c`、`s`、`a`，畫面金額「--」；填息照算 |
| 12 | 回補前的舊資料庫（新欄位都是 NULL） | `"a"` 全是 None，`dv` 沒有金額鍵；不出錯 |
| 13 | 金額欄找不到或「--」 | 存 NULL；MERGE 的 `COALESCE` 保留舊值 |
| 14 | 新上市 ETF 還不在 `etfs` | `JOIN etfs` 略過；每晚往回查 7 天，`etfs` 更新後下一晚會寫進去 |
| 15 | `check`：舊紀錄沒有 `events` | 只寫「至 YYYY-MM-DD」，不寫時間以外的筆數 |
| 16 | `load_state` 舊的 3、4 欄假資料 | `export_failed` 是 False，其他新鍵 None 或 `[]` |
| 17 | 只用 `export` 指令手動匯出成功 | `collect_runs` 沒有紀錄，下一次收集會再補匯出一次（多一次、無害） |
| 18 | `--no-export` 而且有新資料的那次 | 該筆沒有耗時；若結果是 abnormal，下一次會補匯出 |
| 19 | `insti.n` 是 null（官方沒有合計） | 前端退回三者相加 |
| 20 | node 14（測試）沒有 `String.prototype.replaceAll` | 測試加 polyfill；瀏覽器都有（`app.js` 原本就用） |

---

## 十、測試（`tests/test_iter24.py`，全文見附錄 A）

### 10-1 測試清單

| 測試 | 內容 | 驗收 |
|---|---|---|
| `test_parse_amounts` | fixture 的金額、ETF 分流、ETN／受益證券／特別股排除；`parse_events` 預設輸出不變；欄位改名、值「--」、必要欄位缺漏、`TWTAUU` | F24-5 #4～#9 |
| `test_merge_sql` | `COALESCE` 字面（ETF 那段另外檢查）；mock `fetch_events`、`db.connect` 跑 `collect_events`：跨 3 段去重、回傳兩種筆數、同一連線一次 commit、ETF 不在股票 JSON；沒有事件不連資料庫 | F24-5 #6、#9 |
| `test_setup_db_ddl` | `etf_events` 與 3 欄都有 `IF`；外鍵表先建 | F24-5 #1 |
| `test_dividends_real` | fixture 7 檔逐列相等；`ev` 元素不加鍵 | F24-6 #1～#7、#9 |
| `test_dividends_edges` | 合成資料：無成交、當天、對不到金額、8 種停止原因、現增不停、自己是權息、`a`／`s` 的輸出規則、純配股不算填權、列入類型、第一列事件 | F24-6、D37-1 |
| `test_export_source` | `dv`、`n`、3 欄 SELECT 的字面；`etf_export` 沒有 `dv` | F24-6、F24-8、D37-4 |
| `test_js_dividend_card` | node 執行 `divHTML`：沒有紀錄、新到舊、當天、不再比較、尚未填息、停牌「最後成交」、上市權息 `title`、純配股、上櫃配股；卡片在季報之後；字面 `noteHTML` 8 個 | F24-6 #5、#10、#11 |
| `test_js_insti_net` | 取出 `stock.js` 的 3 行執行：有 `n`、`n` 為 null、舊 JSON、ETF | F24-8 #5 |
| `test_detail_events_count` | 7a | F24-7 #1 |
| `test_check_lines`、`test_load_state_new_keys` | 7b | F24-7 #2～#4 |
| `test_qa03_tpex_only` | 7d | F24-7 #6 |
| `test_qa09_retry_export` | 7e | F24-7 #7 |
| `test_qa07_messages` | 7c | F24-7 #5 |
| `test_events_lock` | 7f | F24-7 #8 |
| `test_no_advice_words` | `divHTML`、`NET_TIP`、`dfmt`、README 含「第 24 輪」的行：29＋6 個禁用詞 | 共通規則 4 |

### 10-2 fixture

- 從分析師原始回應（`scratchpad/r24/raw/`）與 `orig` 的唯讀匯出裁出（`sa24/mkfix.py`），欄位不變：
  - `twt49u_div_mini.json`：2421×2、2330×4、6669×2、8112、0056×4、00401A×4（含 11/13 前收 12.42、參考價 12.28、0.138）、020036、01007T、2882A，共 20 列。
  - `exdailyq_div_mini.json`：6488×2、5511、1294、6703×2、00937B×12、8349A、020035，共 20 列。
  - `dv_prices_mini.json`：2421、2330、6488、6669、8112、6703、5511 的 `market` 與 `d`、`c`、`ch`。
- 成品在 `sa24/proj/tests/fixtures/`，PG 直接複製（`sa24/r24.diff` 也含這 3 個檔）。

### 10-3 反證

- 舊程式（`orig` 副本放入 `test_iter24.py` 與 fixture）：**16 個全部失敗**。
- 突變測試（`sa24/mutate.py`，在 `proj` 副本逐一還原一處修改）：**16 種突變全部被抓到**：
  - QA-03 `data_date` 只看上市、QA-09 不補匯出、7a 不記筆數、7b 沒有警告行、`export_failed` 不看耗時、7c 三種訊息、7f 無鎖、ETF MERGE 清掉舊值、ETF 進股票、不停止比較、權也算填權、現增也列、前端不用 `n`、卡片舊到新。

### 10-4 PM 5-2 的 24 項舊斷言

| # | 處理 | 結果 |
|---|---|---|
| 1～4 | `parse_events` 回傳不變；金額與 ETF 在 `parse_events_all` | 通過 |
| 5 | `div_ref DECIMAL(10,2)`、`div_ref = COALESCE(s.div_ref, t.div_ref)` 逐字保留，新欄另起一行 | 通過 |
| 6 | `div_ref` 的 DDL 一行不動，新欄各一行 | 通過 |
| 7 | `dv` 另外組裝，`ev` 元素不加鍵 | 通過 |
| 8 | 不動 `etf_export` | 通過 |
| 9～10 | 新行在「處置／注意股」之後、不以 ❌ 開頭、不在最後；一律 `state.get` | 通過 |
| 11 | `load_state` 只加鍵，3 欄、4 欄相容 | 通過 |
| 12 | 沒有警告時不寫 `warnings` 鍵（沒有改寫入端） | 通過 |
| 13、15 | `finish_run` 不變；補匯出是「加上」的條件 | 通過 |
| 14 | 只改 `data_date` 來源；`test_qa02_*` 實跑通過 | 通過 |
| 16 | 以日為單位的照舊 | 通過 |
| 17 | 只改 `isolated=True` | 通過 |
| 18～19 | 讀新鍵用 `.get`；事件 0 筆照舊不出錯 | 通過 |
| 20 | 說明用變數傳入，字面 `noteHTML` 仍 8 個 | 通過 |
| 21～22 | 卡片在基本面分頁；既有說明不改 | 通過 |
| 23 | 新文字避開禁用詞（另外發現「另存股利」含「存股」兩字，README 與 docstring 改寫成「一併寫入股利金額」） | 通過 |
| 24 | `index.html` 的 `?v=` 已更新 | 通過 |
| 另 | `test_iter06` 第 143 行要 `setup-db` 清單以 `etf_holding_gaps")` 結尾 → `etf_events` 放在它之前 | 通過 |

- `python3 tests/test_iter01.py`～`test_iter24.py` 逐檔執行全部通過；`node --check` 通過。

---

## 十一、比對腳本與 DB 檢查腳本（全文見附錄 B）

- `cmp.py`（存成 `logs/iter24_cmp.py`，只讀檔案）：`python3 logs/iter24_cmp.py <基線 site/data> <新 site/data>`，全部通過回傳 0。印出 `dv` 類型、四類筆數、`insti.n` 差 1 張的列數與 11/13 的檔數、`stocks/` 大小變化。
- `iter24_db.py`（存成 `logs/iter24_db.py`，在專案根目錄執行，只 SELECT、結束 rollback）：
  - `base`（backup 之前）：`price_events` 2026-11-13 以前的筆數與 checksum。11/14 實測 `(1701, -936250043)`。
  - `schema`（`setup-db` 兩次之後）：`etf_events` 存在、3 欄存在、筆數與 checksum 和 `base` 相同。
  - `fill`（回補、`export` 之後）：F24-5 驗收 #3～#8、F24-8 驗收 #2。預期值：

| 項目 | 預期 |
|---|---|
| checksum（≤ 11/13） | 和 `base` 相同（F24-5 #3） |
| `TWT49U` | 958 筆，`div_total` 958、`div_cash` 827、`stock_div` 0；息 827 筆中 `div_cash = div_total` 827 |
| `TPEX_EX` | 720 筆，`div_total` 720、`div_cash` 720、`stock_div` 720；息 606 筆 |
| 上市權／權息有 `div_cash` | 0 |
| `TWTAUU`、`TWTB8U` 有金額 | 0 |
| `etf_events` | `TWT49U` 508 筆、113 檔；`TPEX_EX` 630 筆、106 檔；全部有金額、全部是息 |
| ETF 在 `stocks`、市場別不符 | 0、0 |
| 實例 | 2421、2330、6488、5511、6703 的金額和第四節相同 |
| `insti.n` 對資料庫 | 不同 0 列 |

- 範圍以 2026-11-14 為界：回補時（11/17 之後）官方可能已有 11/17 起的新除息（PM 提到 006208 11/17），`fill` 只算 11/14 以前，新的列另外列出即可。

---

## 十二、PG 步驟

- **開工前提（PM 3-2，全部成立才可以動工作目錄與資料庫）**：
  1. **使用者在對話中確認 11/16（週一）晚上的 `collect --catch-up` 與 `check` 都正常**。
  2. 日期是 11/17 起，或第 1 項已確認。
  3. `git status` 除了 `docs/iterations/24/` 沒有變更；HEAD 是 `a739f23`。
  4. 沒有進行中的收集（`collect_runs` 最新一筆已結束、`finished_at` 為 NULL 0 列），並事先告訴使用者作業時段（建議白天）。
  5. 前提不成立時只能在 scratchpad 副本工作。
- **順序**（對應 PM 3-3）：

| # | 動作 | 說明 |
|---|---|---|
| 1 | 基線 | 記錄資料日、`collect_runs` 最大 `run_id`；`python3 logs/iter24_db.py base`；`price_events` 全表（不含新欄）匯出到 `logs/iter24_before/`；把要改的 12 個檔複製到 `logs/iter24_before/`；`site/data` 複製到 `logs/iter24_base/`（`collect_runs` 有變時，先用舊程式 `export` 一次再複製） |
| 2 | **`python3 -m twstock backup`** | 記錄時間、檔名、大小；早於任何資料庫寫入 |
| 3 | 先在暫存副本（不含 `.env`）套用附錄 A：`patch -p1 --dry-run`、套用、複製 fixture、`test_iter01`～`24` 全部通過；放舊檔跑 `test_iter24` → 16 個失敗 | 不碰工作目錄 |
| 4 | **套用到工作目錄，緊接著 `setup-db` 兩次** | `patch -p1` 附錄 A（含 `index.html` 的 `?v=`）；複製 3 個 fixture；第二次不報錯；`python3 logs/iter24_db.py schema` |
| 5 | **回補**：`python3 -u -m twstock events --start 2025-10-30` | 12 次請求（失敗只重跑一次，≤ 24）；輸出「股票 N 筆、ETF M 筆」 |
| 6 | **`python3 -u -m twstock export`** | 記錄秒數（PM 上限：比改前多 3 秒以內）與大小 |
| 7 | `python3 logs/iter24_db.py fill`；`python3 logs/iter24_cmp.py logs/iter24_base site/data` | 都要 0 差異（`cmp.py` 回傳 0） |
| 8 | `python3 -m twstock check`（唯讀） | 有「除權息事件最後成功」一行；回補不是 `collect`，所以這一行是上一次收集的紀錄，回補的筆數看第 5 步輸出（見第十三節第 7 點） |
| 9 | `test_iter01`～`24` 再跑一次；`test_iter23` 確認 `?v=` | 照附錄 A 原樣套用時 `?v=` 已正確；之後若再改 js／css，照 `test_iter23` 的失敗訊息更新 |
| 10 | 8001 預覽 | 375、1024，深淺色；2421、2330、6488、6669、8112、6703、5511、1213；記錄表格寬度與 `scrollWidth`；結束時關閉 8001、刪除新增的 localStorage 鍵 |

- 回退：新欄位允許 NULL、新表獨立，舊程式在新資料表上照常運作；退回程式只要用第 1 步的副本覆蓋，不必還原資料庫。`setup-db` 或回補失敗：停下來回報，不可以為了重試超過請求上限。
- 行數預估：程式＋README **＋202／−46**；測試 545 行＋fixture 3 個檔（約 52 KB）；腳本 `cmp.py` 54 行、`iter24_db.py` 63 行。

---

## 十三、對 PM 的調整

1. **`dv` 1,580 列，不是 1,581**：分析師多算的 1 列是在資料第一列（2025-10-30）的事件，`_price_events` 沒有前一天所以略過（`ev` 也沒有）。息 1,432（PM 1,433）、權息 110、純配股 38。
2. **`n ≠ f + t + dl` 是 33,592 列，不是 33,314**：前端把 `t`、`dl` 的 null 當 0 相加，分析師的口徑把有 null 的列排除。比例同樣約 7.2%，11/13 同樣 157 檔、差都是 1 張。
3. **`check` 用詞**：「除權息事件最後成功：至 2026-11-17（2026-11-17 19:36），股票 n 筆、ETF m 筆（含往回 7 天重查）」。日期寫完整的 `YYYY-MM-DD`（和既有行一致）；「寫入」改為「股票 n 筆」，並註明是往回 7 天的重查筆數，免得誤以為是新事件數。
4. **事件筆數存在 `detail.undated.events`**（和 `events_to` 放一起），不是 `detail.events`。
5. **`a`（權值＋息值）只在沒有現金股利時輸出**：上櫃的 `c`、`s` 已經足夠，避免多存。
6. **畫面文字**：
   - 表頭用「除權息日」「除權息前收盤」（列內有除權、除權息），配股寫「配股／每千股」。
   - 日期用站內的 `md`：「08/28」小字「第 56 個交易日」，不是「8/28（第 56 個交易日）」；「不再比較」放主行、「07/16 配股後」放小字；「尚未填息」主行、「還差 … 元，+…%」小字。
   - 上市權息的配股欄：`k = s`（權的部分就是配股）寫「有」並帶 `title`「上市的官方表沒有配股數」；其他（如 `k = sc`）寫「--」並帶合計的 `title`（PM 只定了現金欄）。（2026-11-16 依 QA24-01 更正，與實作一致）
   - 上櫃純配股的現金 0 寫「--」。
7. **F24-7 驗收 #9（回補後 `check` 的筆數和回補輸出相同）做不到**：`events` 指令本來就不寫 `collect_runs`（第 19 輪起），`check` 的事件一行讀的是每晚收集的紀錄。改成：回補的筆數看第 5 步的輸出；套用後第一晚的收集，`check` 的筆數和那晚的輸出相同（使用者或 QA 看）。若要讓 `events` 也寫紀錄，列入待辦。
8. **F24-5 驗收 #11（用暫存副本跑舊 `events.py`＋新資料表）改成靜態確認**：實際跑要寫資料庫又要請求。舊 `events.py` 的 INSERT、舊 `export.py` 的 SELECT 都列出欄位名稱，新欄位允許 NULL、新表獨立，所以不受影響；PG 在 04-dev 列出這兩處字面即可。
9. **CSS 多 3 個宣告**（`.dv-tbl` 一行）：375 寬不加的話表格 460～529 px，填息欄要捲動才看得到；加了之後 7 檔與最寬的候選都是 309 px，不捲動。所以 `app.css` 的 `?v=` 也會變。
10. **`stocks/` ＋1.9 MB**：`dv` 約 113 KB（PM 估約 100 KB）、`insti.n` 約 1.87 MB（PM 約 2 MB）。
11. **QA-07 ① 的文字**：「✅ 休市日沒有要抓的資料，不需要請求」（只在計畫是空的時候印；休市日若還有沒有日期的資料要抓，照常執行、不印這行）。
12. **README 沒有列出 `test_iter24`**：README 的測試指令只列到第 10 輪，照現狀不補。
13. 其他照 PM。

---

## 十四、給 QA 的提醒

1. **填息獨立驗算**：不要 import `dividends`。用 `stocks/{代號}.json` 的 `prices`（原始價）＋`ev` 自己算；停止條件照 4-1；`n` 從事件列算第 1 天（含無成交日）。
2. **金額**：自己查 `price_events` 的 3 個新欄；上市權、權息的 `div_cash` 必須是 NULL。
3. **`insti.n`**：自己查 `institutional_trades.total_net`，用 Python `round(x / 1000)`。
4. **QA-03、QA-09** 用 mock 重現，並用 `orig` 的檔案跑反證；實機看上線後 2～3 晚 `export_seconds` 只在有新資料或補匯出時有值。
5. 375 寬記錄表格寬度與 `scrollWidth`；8000 不碰。
6. 數字以 PG 匯出當時為準；本文件的數字是 11/13、run 17 的基線，加上分析師 11/14 的原始回應。

---

## 十五、使用者自行執行（照 PM 第七節）

1. **11/16（週一）晚上照常 `collect --catch-up`，然後 `check`，並在對話中告訴 PG 結果是否正常**（PG 開工的前提）。
2. PG 作業期間（建議 11/17 起的白天）不要收集。
3. 套用後照常每晚收集；第一晚看輸出有「股票 N 筆、ETF M 筆」，`check` 有「除權息事件最後成功」一行；之後 2～3 晚看有沒有重複匯出。
4. 第 23 輪若還沒做：重新啟動 8000 的 `serve`，最後一次強制重新整理。
5. 本輪完成後決定是否 commit。

---

## 附錄 A：完整 diff（`orig` → `proj`；新測試檔全文在內；fixture 另見 scratchpad `sa24/proj/tests/fixtures/`）

- 驗證：
  - 在 scratchpad 另外複製專案目前的工作目錄（不含 `.env`、`site/data`、`logs`、`_archive`、`docs`、`.git`），`patch -p1 --dry-run` 通過後正式套用（含 3 個 fixture 的 `sa24/r24.diff`）：16 個檔和原型逐位元組相同，`test_iter01`～`24` 全部通過。
  - 2026-11-14 再對專案目前的工作目錄執行 `patch -p1 --dry-run`（不寫檔）：全部可套用，沒有 offset 或 fuzz。
- 下面的 diff 不含 fixture（共 13 個檔，1,120 行）。

```diff
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/README.md proj/README.md
--- orig/README.md	2026-11-14 11:08:24
+++ proj/README.md	2026-11-14 18:50:28
@@ -37,7 +37,7 @@
    - Mac：`bash scripts/mac/setup.sh`
    - Windows：雙擊 `scripts\windows\setup.bat`
 
-更新程式後若有新增資料表（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`，第 3 輪的 `collect_runs`、`market_holidays`，第 4 輪的 `etfs`、`etf_daily`、`margin_trades`、`etf_margin`、`margin_market`，第 5 輪的 `etf_holdings`、`etf_holding_summary`、`market_breadth`，第 6 輪的 `etf_holding_gaps`，第 10 輪的 `quarterly_financials`，第 11 輪的 `sbl_trades`、`etf_sbl` 與 `stocks.shares` 欄，第 19 輪的 `price_events.div_ref` 欄），請再執行一次 `python -m twstock setup-db`（可重複執行，不影響既有資料），否則 `collect`、`check`、`export` 會失敗。第 9 輪：`insti_amount` 加 `market` 欄（既有列為 `TWSE`），唯一鍵改成 `(trade_date, market, unit)`；`setup-db` 可重複執行，改表前請先 `backup`，改表後不可再執行舊版程式。
+更新程式後若有新增資料表（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`，第 3 輪的 `collect_runs`、`market_holidays`，第 4 輪的 `etfs`、`etf_daily`、`margin_trades`、`etf_margin`、`margin_market`，第 5 輪的 `etf_holdings`、`etf_holding_summary`、`market_breadth`，第 6 輪的 `etf_holding_gaps`，第 10 輪的 `quarterly_financials`，第 11 輪的 `sbl_trades`、`etf_sbl` 與 `stocks.shares` 欄，第 19 輪的 `price_events.div_ref` 欄，第 24 輪的 `etf_events` 與 `price_events.div_total`、`div_cash`、`stock_div` 欄），請再執行一次 `python -m twstock setup-db`（可重複執行，不影響既有資料），否則 `collect`、`check`、`export` 會失敗。第 9 輪：`insti_amount` 加 `market` 欄（既有列為 `TWSE`），唯一鍵改成 `(trade_date, market, unit)`；`setup-db` 可重複執行，改表前請先 `backup`，改表後不可再執行舊版程式。
 
 ## 日常使用
 
@@ -48,7 +48,7 @@
 python -m twstock collect --catch-up --days 20   # 回溯 20 個交易日（上限 30，更早用 history）
 python -m twstock collect                        # 今天全部重抓覆寫（含指數、台指期、處置／注意股、除權息事件、三大法人金額（上市、上櫃））並匯出網站 JSON
 python -m twstock collect --date 2026-10-28      # 指定日期全部重抓覆寫；也用來復原被誤判的臨時休市
-python -m twstock check                          # 檢查近 20 個交易日各資料集的完整性（唯讀、不連外）；開頭列最後一次收集與排程狀態；有異常時印建議指令並回傳 1（--days 至少 1）
+python -m twstock check                          # 檢查近 20 個交易日各資料集的完整性（唯讀、不連外）；開頭列最後一次收集與排程狀態；有異常時印建議指令並回傳 1（--days 至少 1）。第 24 輪起另列除權息事件最後成功的時間與筆數（股票、ETF）、最後一次收集的警告（只顯示，不算異常）
 python -m twstock history --start 2026-01-02     # 補抓歷史（行情、本益比、法人、ETF、融資融券），只補缺的，可中斷重跑
 python -m twstock history --start 2025-10-30 --only etf margin   # 只補 ETF 行情與融資融券（同一天 ETF 先於融資融券；一年約 976 個請求、40 分鐘）
 python -m twstock history --start 2025-10-30 --only holdings   # 只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過；一年約 1,250 個請求、1～2 小時：群益偶爾逾時重試，第 7 輪實測群益 596 次花 52 分鐘）
@@ -59,7 +59,7 @@
 python -m twstock history --start 2026-07-31 --only amount  # 只補三大法人買賣金額（上市、上櫃；已有的市場自動略過；每市場一天一個請求）
 python -m twstock history --start 2024-01-01 --only financials   # 只補季報（季底日在範圍內、窗口已開始的季別；每季上市、上櫃各 1 個請求；已有的季別自動略過，--force 重抓；約 22 次、2 分鐘）
 python -m twstock history --start 2025-10-30 --only sbl   # 只補借券賣出（上市、上櫃各 1 個請求／天；晚上 8 點半後才有當天資料；一年約 490 次、30 分鐘）；不指定 --only 時不補借券
-python -m twstock events --start 2025-10-30      # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑；每半年一段 × 4 個端點，這個區間 12 次請求。第 19 輪 setup-db 後執行一次，補齊減除股利參考價）
+python -m twstock events --start 2025-10-30      # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑；每半年一段 × 4 個端點，這個區間 12 次請求。第 19 輪 setup-db 後執行一次，補齊減除股利參考價）。第 24 輪起一併寫入股利金額與 ETF 除息（`etf_events`），和收集共用鎖：收集進行中時不執行
 python -m twstock revenue --year 2026 --month 9 --force     # 重抓某月營收
 python -m twstock futures --start 2020-01-01     # 補抓台指期日 K 與期貨三大法人未平倉（--commodity MTX 可抓小台）
 python -m twstock chains                         # 立即更新產業鏈族群（collect 每 30 天會自動更新）
@@ -139,6 +139,8 @@
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
 - 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。現金增資除權也依官方參考價調整。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 19 輪：除權事件依官方「減除股利參考價」（只扣股利、不扣現金增資，存在 `price_events.div_ref`；減資、面額變更沒有這一欄）分類，匯出 `ev[].k`：等於參考價 `s`（沒有現增，圖例「除權（配股）」）、等於前收 `c`（只有現增，標記「現增」、圖例「除權（現金增資）」）、其他 `sc`（股利＋現增，「權息」圖例「除權息（含現金增資）」）；容差 0.005 元，只對「權」「權息」，沒有值時照舊寫「除權」。週／月 K 的事件標記寫事件日（例如「2/24 現增」「6/10 息・6/24 權」），圖例第一欄寫「2026-02-23 當週」「2026-02 月」；「原始」價的週／月 K 那一根含事件時，前一根收盤先乘上每筆事件的參考價 ÷ 前收再相減，漲跌幅和「還原」相同（6669 週 K 2026-08-31 由 −64.38% 改為 +6.26%）。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。第 22 輪：技術面訊號的 MACD 柱依昨、今柱值的正負寫「MACD 正柱加長／正柱縮短／負柱縮短／負柱加長／柱由負翻正／柱由正翻負」（柱值相同寫「柱持平」），偏多／偏空的歸類照舊只看柱值是否比昨天大。
 - 個股頁近期表現（第 23 輪，「走勢」分頁 K 線與技術面訊號之間；`stocks/{代號}.json` 的 `pf` = [[區間, 基準日, 本股 %, 指數 %, 差距], ...]）：區間 5、20、60、120 日（基準日 = 全市場往前第 N 個交易日）、`y` 今年以來（前一年最後一個交易日）、`w` 52 週（資料日往前 365 天以前的最後一個交易日，同 52 週高低）。本股用還原收盤（含股息；今天無成交時用最後成交收盤，表頭寫最後成交日），上市比加權指數、上櫃比櫃買指數（價格指數，**不含股息**，長區間的差距會偏向個股）；差距 = 本股 − 指數（百分點）。5、20、60 日和選股的 `r5`、`r20`、`r60`、`rs20`、`rs60` 用同一個函式（`period_return`、`index_return`），數字相同。基準日時還沒有成交的區間寫「--」，並加一列 `s`「上市以來」（上櫃寫「上櫃以來」）：從本站第一個成交日的收盤起算，不是承銷價；本站日線從 2025-10-30 起，復牌或轉換為控股公司的股票也從第一個成交日算。停牌、下市（最後一列不是資料日）的股票沒有 `pf`、不顯示；ETF 頁不顯示。
+- 個股頁股利與填息（第 24 輪，「基本面」分頁季報卡之後；`stocks/{代號}.json` 的 `dv`，舊到新，沒有紀錄是 `[]`）：資料表 `price_events` 的 `div_total`（權值+息值）、`div_cash`（每股現金股利）、`stock_div`（每千股無償配股），只有證交所 TWT49U、櫃買 exDailyQ 兩個來源有值；上市的官方表只有權值+息值，所以上市「息」的現金股利 = 權值+息值，上市「權」「權息」的現金股利、配股數是 NULL（畫面寫「--」或「有」，滑過可看合計）。列入除息、除權息，以及純配股的除權（`k` 為 `s`、`sc`；只列、不算填權）；只有現金增資的除權不列。填息日 = 除權息日起（含當天）第一個收盤 ≥ 除權息前收盤的交易日，原始價、不設期限，`n` 從除權息日當天算第 1 天（無成交日也算）；還沒填息就遇到之後的配股、減資、面額變更或上櫃反推的股本變動時寫「不再比較」（`x` = [日期, 原因]）。ETF 的除息另存 `etf_events`（只收兩個來源的「息」），本輪只入表、網站還沒有使用。
+- 個股頁法人合計（第 24 輪）：`stocks/{代號}.json` 的 `insti.n` = 官方三大法人合計（股數）÷ 1,000 四捨五入，和外資、投信、自營各自四捨五入後相加可能差 1 張；週、月 K 是每日合計相加（圖例寫「合計（每日相加）」）。舊的 JSON 沒有 `n` 時畫面照舊三者相加。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
 - 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
 - 月營收：第 9 輪起從每月第一個交易日開始，`collect --catch-up` 每天第一次成功收集時抓已公布的公司（只補資料庫還沒有的公司，同一天只抓一次），直到該月家數達前一月的 98% 為止（約 10～12 日），之後到月底 0 個請求；`collect --date`、`history` 也收前一個月。月初官方檔案只有標題列時寫入 0 家，不是錯誤。
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/site/app.css proj/site/app.css
--- orig/site/app.css	2026-11-14 11:08:24
+++ proj/site/app.css	2026-11-14 18:58:01
@@ -263,4 +263,5 @@
 .note-dup .note[open] summary i{font-size:12px;margin-left:0}
 .tbl td.hl-tags,.tbl th.hl-th{white-space:normal;min-width:12em;text-align:left}.hl-tag{display:inline-block;margin:1px 8px 1px 0;font-size:12px}.hl-tag i{font-style:normal;color:var(--text2)}   /* 第 21 輪 F21-1 */
 .hl-sub{display:none}table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 23 輪 F23-4a、F23-1 */
+table.dv-tbl{max-width:720px}.dv-tbl td span{white-space:normal}.dv-tbl th,.dv-tbl td{padding-left:5px;padding-right:5px}.dv-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 24 輪 F24-6 股利與填息 */
 @media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}.tbl .nm .hl-sub span{color:var(--text);font-size:12px;margin:2px 8px 0 0}}
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/site/index.html proj/site/index.html
--- orig/site/index.html	2026-11-14 11:08:44
+++ proj/site/index.html	2026-11-14 19:00:16
@@ -6,11 +6,11 @@
 <title>台股資金流</title>
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
-<link rel="stylesheet" href="app.css?v=52d5a6c7">
+<link rel="stylesheet" href="app.css?v=8ff7e8b4">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
 <script src="app.js?v=b1f56347" defer></script>
-<script src="stock.js?v=a3b1a5c6" defer></script>
+<script src="stock.js?v=0a8a6929" defer></script>
 </head>
 <body>
 <header class="top">
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-14 11:08:44
+++ proj/site/stock.js	2026-11-14 18:58:01
@@ -5,6 +5,7 @@
 const CHART_IDS = ['kC', 'vC', 'iC', 'gC', 'mC'];   // gC（融資融券）只在有 mg 時存在
 // 法人買賣超堆疊柱：外資在最靠近零軸的一層，往外依序投信、自營
 const INVESTORS = [['f', '外資', '#4C6EF5'], ['t', '投信', '#F08C00'], ['dl', '自營', '#AE3EC9']];
+const NET_TIP = '合計 = 官方三大法人合計（股數）換算張數，和外資、投信、自營各自四捨五入後相加可能差 1 張；週／月 K 是每日合計相加，可能和股數加總後四捨五入差 1～2 張';   // 第 24 輪 F24-8
 
 const disposeKCharts = () => { charts.forEach(c => c.remove()); charts = []; };
 // 離開個股頁時一併釋放月營收圖；切換日／週／月只重建 K 線（buildCharts），不動月營收圖
@@ -44,6 +45,30 @@
     `</tbody></table></div><div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
 }
 
+// 第 24 輪 F24-6：股利與填息（匯出端 dv：d 除權息日、t 類型、k 分類、c 現金股利、s 每仟股配股、a 權值＋息值（沒有 c 時）、p 除權息前收盤、
+// f 填息日、n 第幾個交易日、x = [日期, 原因] 股本變動後不再比較）；填息在匯出端算，這裡只顯示。D36-12：金額最多 4 位小數、去掉尾端 0
+const dfmt = (n, d = 4) => n == null ? '--' : Number(n).toLocaleString('zh-TW', { maximumFractionDigits: d });
+function divHTML(dv, mkt, P) {
+  const head = '<section class="sec card"><div class="sec-h"><h2>股利與填息</h2></div>', from = P.d[0];
+  if (!dv.length) return `${head}<div class="muted small">${from} 起沒有除權息紀錄</div></section>`;
+  const tr = P.c.map((c, i) => c != null ? i : -1).filter(i => i >= 0), lt = tr[tr.length - 1], lc = P.c[lt];
+  const late = P.d[lt] !== App.latest.date ? `，最後成交 ${md(P.d[lt])}` : '';      // D37-7：停牌股照算，寫最後成交日
+  const split = r => mkt === 'TWSE' && r.t === '權息' ? ` title="上市除權息的官方表只有權值＋息值合計 ${dfmt(r.a, 6)} 元，無法拆分現金與配股"` : '';
+  const cash = r => r.c > 0 ? dfmt(r.c) : `<span${split(r)}>--</span>`;
+  const stock = r => r.s ? fmt(r.s, 2) : mkt === 'TWSE' && (r.t === '權' || r.k === 's')
+    ? `<span title="上市的官方表沒有配股數${r.t === '權' && r.a != null ? `；權值＋息值 ${dfmt(r.a, 6)} 元` : ''}">有</span>` : `<span${split(r)}>--</span>`;
+  const fill = r => r.t === '權' ? '<span title="純配股不計算填權">--</span>' : r.f ? `${r.n === 1 ? '當天' : md(r.f)}<span>第 ${r.n} 個交易日</span>`
+    : r.x ? `不再比較<span>${md(r.x[0])} ${r.x[1]}後</span>` : `尚未填息<span>還差 ${fmt(r.p - lc, 2)} 元，+${fmt((r.p - lc) / lc * 100, 2)}%${late}</span>`;
+  const short = `填息 = 收盤回到除息前收盤；天數含除息日當天。資料自 ${from} 起`;     // 短句用變數：test_iter13 數 noteHTML 字面呼叫
+  const full = '填息日 = 除權息日起（含當天）第一個收盤大於或等於除權息前收盤的交易日，用原始價、不設期限；第 N 個交易日從除權息日當天算第 1 天，無成交日也算。' +
+    '純配股（除權）不計算填權；只有現金增資的除權不列入。還沒填息就遇到之後的配股、減資或面額變更時，原始價不能再和除權息前收盤比較，寫「不再比較」。' +
+    '上市除權息的官方表只有權值＋息值合計，現金股利寫「--」（滑過可看合計）；上櫃的配股是每千股無償配股的股數。還差 = 除權息前收盤 − 最新收盤，% 以最新收盤計算。';
+  return `${head}<div class="tbl-wrap"><table class="tbl dv-tbl"><thead><tr><th>除權息日</th><th>現金股利<br>（元）</th><th>配股<br>每千股</th><th>除權息<br>前收盤</th><th>填息</th></tr></thead><tbody>` +
+    dv.slice().reverse().map(r => `<tr><td>${r.d.replaceAll('-', '/')}${r.t === '息' ? '' : `<span>${EV_LABEL[r.t]}</span>`}</td><td class="num">${cash(r)}</td>` +
+      `<td class="num">${stock(r)}</td><td class="num">${pfmt(r.p)}</td><td>${fill(r)}</td></tr>`).join('') +
+    `</tbody></table></div><div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
+}
+
 const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];
 const ETF_TABS = STOCK_TABS.slice(0, 2);       // 第 15 輪 F15-2：ETF 個股頁沒有基本面
 // 第 15 輪 F15-2：ETF 個股頁的價格說明（原始價；本站沒有 ETF 除息資料）。短句一定可見，完整說明收合（短句用變數：test_iter13 數 noteHTML 字面呼叫）
@@ -173,7 +198,8 @@
     <section class="sec grid ${F ? 'g2' : 'g-one'}">
       <div class="card"><div class="sec-h"><h2>月營收</h2><span class="sp"></span><span id="revSegBox"></span></div><div id="revBox"></div></div>
       ${F ? `<div class="card"><div class="sec-h"><h2>季報</h2><span class="muted small">${qName(F.q.at(-1)[0])}${F.c.fs ? `｜本站收錄 ${md(F.c.fs)}` : ''}｜${FIN_TBL[F.t] || ''}</span></div><div id="finBox"></div></div>` : ''}
-    </section>` : `
+    </section>
+    ${data.dv ? divHTML(data.dv, data.market, P) : ''}` : `
 
     <section class="sec card">
       <div class="sec-h">
@@ -257,7 +283,7 @@
   P.d.forEach((d, i) => {
     const has = I?.f[i] != null;                     // ETF 沒有法人資料
     const inst = { f: has ? I.f[i] : null, t: has ? I.t[i] ?? 0 : null, dl: has ? I.dl[i] ?? 0 : null };
-    inst.net = has ? inst.f + inst.t + inst.dl : null;
+    inst.net = has ? I.n?.[i] ?? inst.f + inst.t + inst.dl : null;      // 第 24 輪 F24-8：官方合計；舊 JSON 沒有 n 時三者相加
     const e = evAt[d] ? [evAt[d]] : [];
     if (P.c[i] != null && P.o[i] != null) {
       const k = af[i], ch = P.ch?.[i] ?? null;
@@ -490,7 +516,7 @@
     if (ic) $('#iLegend').innerHTML = (j !== i && N[j] != null ? `<span class="muted">${T[j]}</span>` : '') +
       INVESTORS.map(([key, name, color]) =>
         `<span class="lg"><i style="background:${color}"></i>${name} <b class="num ${cls(r[key])}">${v(r[key])}</b></span>`).join('') +
-      `<span class="lg">合計 <b class="num ${cls(N[j])}">${v(N[j])}</b></span>`;
+      `<span class="lg" title="${NET_TIP}">合計${mode === '日' ? '' : '（每日相加）'} <b class="num ${cls(N[j])}">${v(N[j])}</b></span>`;
     if (gc) {   // 融資融券比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
       let g = i;
       if (MB[g] == null && i === raw.length - 1) while (g > 0 && MB[g] == null) g--;
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/tests/test_iter24.py proj/tests/test_iter24.py
--- orig/tests/test_iter24.py	1970-01-01 08:00:00
+++ proj/tests/test_iter24.py	2026-11-14 18:58:01
@@ -0,0 +1,545 @@
+"""第 24 輪（不連網、不連資料庫）：F24-5 股利金額與 ETF 除息入表、F24-6 個股頁股利與填息、F24-7a～f 小修、F24-8 法人合計用官方值。
+fixture：tests/fixtures/twt49u_div_mini.json、exdailyq_div_mini.json（官方原始回應的精簡版：欄位不變，只留幾列；
+2026-11-14 分析師取得的 2025-10-30～2026-11-14 區間），dv_prices_mini.json（7 檔的日線 d、c、ch，取自第 23 輪程式的匯出）。
+收集流程沿用 test_iter03 的 World、env、run_site；有 node 時逐字取出 stock.js、app.js 的函式執行。"""
+import contextlib
+import io
+import json
+import re
+import shutil
+import subprocess
+import sys
+import tempfile
+from datetime import date, datetime, timedelta
+from pathlib import Path
+from unittest import mock
+
+ROOT = Path(__file__).resolve().parents[1]
+sys.path.insert(0, str(ROOT))
+sys.path.insert(0, str(ROOT / "tests"))
+import test_iter03 as t3  # noqa: E402
+from twstock import db, export, fetch, health, tradingcal  # noqa: E402
+from twstock.collectors import catchup, events, history  # noqa: E402
+from twstock.fetch import FetchError  # noqa: E402
+
+D, T, World, CLOSED = t3.D, t3.T, t3.World, t3.CLOSED
+FIX = Path(__file__).resolve().parent / "fixtures"
+T49 = json.loads((FIX / "twt49u_div_mini.json").read_text(encoding="utf-8"))
+EXQ = json.loads((FIX / "exdailyq_div_mini.json").read_text(encoding="utf-8"))["tables"][0]
+PX = json.loads((FIX / "dv_prices_mini.json").read_text(encoding="utf-8"))
+APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+README = (ROOT / "README.md").read_text(encoding="utf-8")
+SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+EVSRC = (ROOT / "twstock" / "collectors" / "events.py").read_text(encoding="utf-8")
+OLD_KEYS = {"stock_code", "event_date", "event_type", "prev_close", "ref_price", "source", "div_ref"}
+
+
+# ─── F24-5：解析、寫入、DDL ─────────────────────────────
+def test_parse_amounts():
+    st, et = events.parse_events_all("TWT49U", T49["fields"], T49["data"])
+    by = {(r["stock_code"], r["event_date"]): r for r in st}
+    assert by[("2330", "2025-12-11")] == {"stock_code": "2330", "event_date": "2025-12-11", "event_type": "息", "prev_close": 1505.0,
+                                          "ref_price": 1499.99, "source": "TWT49U", "div_ref": 1499.99, "div_total": 5.000011, "div_cash": 5.000011}
+    assert by[("2421", "2026-06-10")]["div_cash"] == 5.24042
+    r = by[("6669", "2026-09-02")]                                                     # 上市「權」：只有權值+息值，現金股利不存
+    assert r["event_type"] == "權" and r["div_total"] == 5185.002642 and "div_cash" not in r and "stock_div" not in r
+    r = by[("8112", "2026-07-06")]
+    assert r["event_type"] == "權息" and r["div_total"] == 5.36055 and "div_cash" not in r
+    # ETF 另成一份，只收「息」；ETN（020036）、受益證券（01007T）、特別股（2882A）兩邊都不收
+    assert {r["etf_code"] for r in et} == {"0056", "00401A"} and {r["event_type"] for r in et} == {"息"}
+    assert {"etf_code": "00401A", "event_date": "2026-11-13", "event_type": "息", "prev_close": 12.42, "ref_price": 12.28,
+            "source": "TWT49U", "div_cash": 0.138} in et
+    codes = {r["stock_code"] for r in st} | {r["etf_code"] for r in et}
+    assert not codes & {"020036", "01007T", "2882A", "0056 ", "00401A "} and "0056" not in {r["stock_code"] for r in st}
+    st2, et2 = events.parse_events_all("TPEX_EX", EXQ["fields"], EXQ["data"])
+    by = {(r["stock_code"], r["event_date"]): r for r in st2}
+    r = by[("6703", "2026-07-16")]
+    assert r["event_type"] == "權" and r["div_cash"] == 0.0 and r["stock_div"] == 100.00000916
+    r = by[("5511", "2026-07-09")]
+    assert r["event_type"] == "權息" and r["div_cash"] == 3.6 and r["stock_div"] == 198.87165021
+    assert by[("6488", "2026-07-16")]["div_cash"] == 5.7 and by[("6488", "2026-07-16")]["stock_div"] == 0.0     # 0 照存（dv 才省略）
+    assert len(et2) == 12 and {r["etf_code"] for r in et2} == {"00937B"} and et2[0]["div_cash"] == 0.072
+    assert not {r["stock_code"] for r in st2} & {"8349A", "020035", "00937B"}
+    # 預設的 parse_events 不變：不含股利金額、不含 ETF（test_iter02、test_iter19 整個 dict 比對）
+    for src, f, rows, full in (("TWT49U", T49["fields"], T49["data"], st), ("TPEX_EX", EXQ["fields"], EXQ["data"], st2)):
+        old = events.parse_events(src, f, rows)
+        assert old == [{k: v for k, v in r.items() if k in OLD_KEYS} for r in full] and all(set(r) <= OLD_KEYS for r in old)
+    # 欄位缺漏、值為 --：照常回傳，金額不放鍵
+    f = [x if x != "權值+息值" else "改名" for x in T49["fields"]]
+    st3, et3 = events.parse_events_all("TWT49U", f, T49["data"])
+    assert len(st3) == len(st) and len(et3) == len(et) and all("div_total" not in r and "div_cash" not in r for r in st3 + et3)
+    rows = [list(r) for r in EXQ["data"]]
+    k = EXQ["fields"].index("息值")
+    for r in rows:
+        r[k] = "--"
+    st4, et4 = events.parse_events_all("TPEX_EX", EXQ["fields"], rows)
+    assert all("div_cash" not in r for r in st4 + et4) and len(et4) == 12 and by[("5511", "2026-07-09")]["div_total"] == \
+        next(r for r in st4 if r["stock_code"] == "5511")["div_total"]
+    # 必要欄位缺漏：兩份都是空的；減資、面額變更沒有股利欄、不收 ETF
+    assert events.parse_events_all("TWT49U", T49["fields"][1:], T49["data"]) == ([], [])
+    fields = ["恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價"]
+    assert events.parse_events_all("TWTAUU", fields, [["115年07月01日", "0056", "30.00", "36.00"], ["115年07月01日", "1101", "30.00", "36.00"]]) == \
+        ([{"stock_code": "1101", "event_date": "2026-07-01", "event_type": "減", "prev_close": 30.0, "ref_price": 36.0, "source": "TWTAUU"}], [])
+
+
+class _Conn:
+    def __init__(self, log):
+        self.log = log
+
+    def cursor(self):
+        return self
+
+    def execute(self, sql, *params):
+        self.log.append((sql, params))
+        return self
+
+    def commit(self):
+        self.log.append(("commit", ()))
+
+    def close(self):
+        pass
+
+
+def _fake_fetch(source, s, e):
+    if source == "TWT49U":
+        return events.parse_events_all(source, T49["fields"], T49["data"])
+    if source == "TPEX_EX":
+        return events.parse_events_all(source, EXQ["fields"], EXQ["data"])
+    return [], []
+
+
+def test_merge_sql():
+    # 新欄位另起一行，舊的兩段逐字保留（test_iter19）；金額缺漏時 COALESCE 不清掉已存的值
+    for s in ("div_total = COALESCE(s.div_total, t.div_total), div_cash = COALESCE(s.div_cash, t.div_cash),",
+              "stock_div = COALESCE(s.stock_div, t.stock_div),", "div_ref = COALESCE(s.div_ref, t.div_ref)",
+              "div_total DECIMAL(12,6), div_cash DECIMAL(12,6), stock_div DECIMAL(14,8)",
+              "MERGE etf_events AS t", "JOIN etfs et ON et.etf_code = j.etf_code"):
+        assert s in EVSRC, s
+    assert "div_cash = COALESCE(s.div_cash, t.div_cash)\n" in EVSRC[EVSRC.index("MERGE etf_events"):]               # ETF 那段也不清掉
+    log, buf = [], io.StringIO()
+    with mock.patch.object(events, "fetch_events", _fake_fetch), mock.patch.object(db, "connect", lambda: _Conn(log)), \
+            contextlib.redirect_stdout(buf):
+        n = events.collect_events(D(10, 30, 2025), D(11, 14))          # 2 段：同一列抓到兩次也只寫一次
+    assert n == {"stocks": 15, "etfs": 20}
+    assert "股票 15 筆、ETF 20 筆（2025-10-30 ～ 2026-11-14）" in buf.getvalue()
+    (s1, p1), (s2, p2), (c, _) = log
+    assert "MERGE price_events" in s1 and "MERGE etf_events" in s2 and c == "commit"         # 同一個連線、一次 commit
+    rows, etfs = json.loads(p1[0]), json.loads(p2[0])
+    assert len(rows) == 15 and all("etf_code" not in r for r in rows) and not {r["stock_code"] for r in rows} & {"0056", "00401A", "00937B"}
+    assert len(etfs) == 20 and {r["etf_code"] for r in etfs} == {"0056", "00401A", "00937B"} and all("stock_code" not in r for r in etfs)
+    # 沒有任何事件：不連資料庫
+    log.clear()
+    with mock.patch.object(events, "fetch_events", lambda *a: ([], [])), mock.patch.object(db, "connect", lambda: _Conn(log)), \
+            contextlib.redirect_stdout(io.StringIO()):
+        assert events.collect_events(D(11, 7), D(11, 14)) == {"stocks": 0, "etfs": 0}
+    assert log == []
+
+
+def test_setup_db_ddl():
+    ddl = [s.strip() for s in db.DDL]
+    i = next(k for k, s in enumerate(ddl) if "CREATE TABLE etf_events" in s)
+    assert ddl[i].startswith("IF OBJECT_ID('etf_events') IS NULL") and "REFERENCES etfs(etf_id)" in ddl[i]
+    assert "CONSTRAINT UQ_etf_events UNIQUE (etf_id, event_date, source)" in ddl[i] and "div_cash    DECIMAL(12,6) NULL" in ddl[i]
+    assert i > next(k for k, s in enumerate(ddl) if "CREATE TABLE etfs" in s)                    # 外鍵表先建
+    for col, typ in (("div_total", "DECIMAL(12,6)"), ("div_cash", "DECIMAL(12,6)"), ("stock_div", "DECIMAL(14,8)")):
+        assert f"IF COL_LENGTH('price_events', '{col}') IS NULL ALTER TABLE price_events ADD {col} {typ} NULL" in ddl, col
+    # 可重複執行：每一條都有存在檢查
+    new = [s for s in ddl if "etf_events" in s or "div_total" in s or "'div_cash'" in s or "stock_div" in s]
+    assert len(new) == 4 and all(s.startswith("IF ") for s in new)
+
+
+# ─── F24-6：股利與填息 ───────────────────────────────────
+def _official():
+    out = {}
+    for src, f, rows in (("TWT49U", T49["fields"], T49["data"]), ("TPEX_EX", EXQ["fields"], EXQ["data"])):
+        for r in events.parse_events_all(src, f, rows)[0]:          # 同匯出端讀 price_events 的 dict
+            out.setdefault(r["stock_code"], []).append({
+                "d": date.fromisoformat(r["event_date"]), "t": r["event_type"], "p": r["prev_close"], "r": r["ref_price"], "src": src,
+                "k": export.rights_kind(r["event_type"], r["prev_close"], r["ref_price"], r.get("div_ref")),
+                "a": (r.get("div_total"), r.get("div_cash"), r.get("stock_div"))})
+    return out
+
+
+def _dv(code):
+    v, off = PX[code], sorted(_official().get(code, []), key=lambda e: e["d"])
+    d_ = [date.fromisoformat(s) for s in v["d"]]
+    ev, _ = export._price_events(d_, v["c"], v["ch"], v["market"], off)
+    assert all(set(e) <= {"i", "d", "t", "p", "r", "k"} for e in ev)                    # ev 元素不加鍵（test_iter02、08、19）
+    return export.dividends(d_, v["c"], ev, off)
+
+
+def test_dividends_real():
+    assert _dv("2421") == [{"d": "2026-06-10", "t": "息", "c": 5.24042, "p": 160.0, "f": "2026-08-28", "n": 56}]    # 2/24 現增（k=c）不列
+    assert [(r["c"], r["f"], r["n"]) for r in _dv("2330")] == [(5.000011, "2025-12-26", 11), (6.000035, "2026-03-17", 1),
+                                                               (6.000035, "2026-06-12", 2), (7.000001, "2026-09-17", 2)]
+    assert _dv("6488") == [{"d": "2025-12-31", "t": "息", "c": 2.0, "p": 413.0, "f": "2026-01-05", "n": 3},
+                           {"d": "2026-07-16", "t": "息", "c": 5.7, "p": 1480.0}]                                  # 尚未填息
+    assert _dv("6669") == [{"d": "2026-06-22", "t": "息", "c": 144.391544, "p": 5130.0, "f": "2026-07-02", "n": 9},
+                           {"d": "2026-09-02", "t": "權", "k": "s", "a": 5185.002642, "p": 7800.0}]               # 純配股：只列，不算填權
+    assert _dv("8112") == [{"d": "2026-07-06", "t": "權息", "k": "sc", "a": 5.36055, "p": 92.9, "f": "2026-08-11", "n": 26}]
+    assert _dv("6703") == [{"d": "2026-03-26", "t": "息", "c": 4.8, "p": 120.5, "x": ["2026-07-16", "配股"]},
+                           {"d": "2026-07-16", "t": "權", "k": "s", "c": 0.0, "s": 100.00000916, "p": 117.0}]
+    assert _dv("5511") == [{"d": "2026-07-09", "t": "權息", "k": "s", "c": 3.6, "s": 198.87165021, "p": 79.7}]
+
+
+def test_dividends_edges():
+    d_ = [D(7, 1) + timedelta(days=i) for i in range(10)]
+    ev = lambda i, t, p=100.0, k=None: {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": p - 2, **({"k": k} if k else {})}
+    off = lambda i, t, a=(2.0, 2.0, None), p=100.0: {"d": d_[i], "t": t, "p": p, "r": p - 2, "src": "TWT49U", "a": a}
+    c = [100.0, 100.0, None, 97.0, 99.99, 100.0, 101.0, 95.0, 96.0, 97.0]
+    # 除息日當天沒有成交、無成交日也算天數
+    assert export.dividends(d_, c, [ev(2, "息")], [off(2, "息")]) == [{"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}]
+    # 當天就填息
+    assert export.dividends(d_, [98.0] * 3 + [100.0] * 7, [ev(3, "息")], [])[0] == {"d": str(d_[3]), "t": "息", "p": 100.0, "f": str(d_[3]), "n": 1}
+    # 沒有官方金額（對不到）：沒有 c、s、a；最後一天才除息且未填息
+    assert export.dividends(d_, c, [ev(9, "息")], [off(8, "息")]) == [{"d": str(d_[9]), "t": "息", "p": 100.0}]
+    # 停止原因：填息前遇到之後的股本變動；同一天又填息又股本變動 → 不再比較；只有現增（k=c）不算
+    for t, k, word in (("減", None, "減資"), ("面", None, "面額變更"), ("調", None, "股本變動"), ("權", "s", "配股"),
+                       ("權", "sc", "除權"), ("權", None, "除權"), ("權息", "sc", "除權息"), ("權息", None, "除權息")):
+        dv = export.dividends(d_, c, [ev(2, "息"), ev(5, t, 100.0, k)], [off(2, "息")])
+        assert dv[0] == {"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "x": [str(d_[5]), word]}, (t, k, dv)
+    dv = export.dividends(d_, c, [ev(2, "息"), ev(4, "權", 100.0, "c")], [off(2, "息")])
+    assert dv == [{"d": str(d_[2]), "t": "息", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}]          # 現增不列、不停
+    # 自己這一列是權息：不被自己停住
+    dv = export.dividends(d_, c, [ev(2, "權息", 100.0, "sc")], [off(2, "權息", (5.0, None, None))])
+    assert dv == [{"d": str(d_[2]), "t": "權息", "k": "sc", "a": 5.0, "p": 100.0, "f": str(d_[5]), "n": 4}]
+    # a 只在沒有現金股利時輸出；配股 0 不輸出；上櫃權息有 c、s
+    dv = export.dividends(d_, c, [ev(2, "權息", 100.0, "s")], [off(2, "權息", (3.0, 2.0, 0.0))])
+    assert dv[0] == {"d": str(d_[2]), "t": "權息", "k": "s", "c": 2.0, "p": 100.0, "f": str(d_[5]), "n": 4}
+    # 對應官方事件要同一列、同類型、同前收與參考價
+    assert "c" not in export.dividends(d_, c, [ev(2, "息")], [off(2, "息", p=101.0)])[0]
+    # 列入的類型：息、權息、權（k=s、sc）；權（k=c 或不明）、減、面、調不列
+    assert [r["t"] for r in export.dividends(d_, c, [ev(1, "權", 100.0, "c"), ev(2, "權"), ev(3, "減"), ev(4, "面"), ev(5, "調"),
+                                                    ev(6, "權", 100.0, "sc")], [])] == ["權"]
+    assert export.dividends(d_, c, [], []) == []
+    # 純配股：之後收盤回到前收也不算填權
+    assert export.dividends(d_, c, [ev(2, "權", 100.0, "s")], [off(2, "權", (3.0, None, None))]) == [
+        {"d": str(d_[2]), "t": "權", "k": "s", "a": 3.0, "p": 100.0}]
+    # 事件在資料第一列：_price_events 不收（沒有前一天），所以不會出現在 dv
+    ev0, _ = export._price_events(d_, c, [0.0] * 10, "TWSE", [off(0, "息")])
+    assert ev0 == [] and export.dividends(d_, c, ev0, [off(0, "息")]) == []
+
+
+def test_export_source():
+    for s in ('"dv": dividends(d_, c, ev, events.get(code, [])),',
+              '"n": [round(x / 1000) if x is not None else None for x in total]},',
+              "e.div_total, e.div_cash, e.stock_div", "for code, d, t, p, r, src, dr, *amt in cur.execute(",
+              '"a": tuple(None if x is None else float(x) for x in amt)})',
+              '"ev": [{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e} for e in ev],'):
+        assert s in SRC, s
+    etf = SRC[SRC.index("def etf_export"):]
+    etf = etf[:etf.index("\ndef ")]
+    assert '"dv"' not in etf and "dividends" not in etf and "etf_events" not in SRC          # D37-4：ETF 本輪只入表
+
+
+# ─── node：stock.js ─────────────────────────────────────
+def _grab(src, name):
+    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
+    if m:
+        i, n = src.index("{", src.index(")", m.start())), 0
+        for j in range(i, len(src)):
+            n += {"{": 1, "}": -1}.get(src[j], 0)
+            if n == 0:
+                return src[m.start():j + 1]
+    m = re.search(rf"^const {name}\b", src, re.M)
+    assert m, name
+    lines = src[m.start():].splitlines()
+    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
+    return "\n".join(lines[:k + 1])
+
+
+PF = ("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"     # node 14
+      "if (!String.prototype.replaceAll) String.prototype.replaceAll = function (a, b) { return this.split(a).join(b); };\n")
+
+
+def _node(js):
+    node = shutil.which("node")
+    if not node:
+        print("  （沒有 node，略過執行）")
+        return None
+    return json.loads(subprocess.run([node, "-e", PF + js], capture_output=True, text=True, check=True).stdout)
+
+
+def test_js_dividend_card():
+    js = "\n".join(_grab(APP, n) for n in ("fmt", "pfmt", "md", "noteHTML")) + "\n" + \
+        "\n".join(_grab(STK, n) for n in ("EV_LABEL", "dfmt", "divHTML")) + """
+const App = { latest: { date: '2026-11-13' } };
+const P = { d: ['2025-10-30', '2026-11-12', '2026-11-13'], c: [90, 80, 100] }, S = { d: P.d, c: [90, 80, null] };
+const dv = [{ d: '2026-06-10', t: '息', c: 5.24042, p: 160, f: '2026-08-28', n: 56 }, { d: '2026-07-01', t: '息', c: 1, p: 50, f: '2026-07-01', n: 1 },
+  { d: '2026-03-26', t: '息', c: 4.8, p: 120.5, x: ['2026-07-16', '配股'] }, { d: '2026-07-16', t: '息', c: 5.7, p: 125 },
+  { d: '2026-07-06', t: '權息', k: 'sc', a: 5.36055, p: 92.9, f: '2026-08-11', n: 26 }, { d: '2026-09-02', t: '權', k: 's', a: 5185.002642, p: 7800 }];
+const tpex = [{ d: '2026-07-16', t: '權', k: 's', c: 0, s: 100.00000916, p: 117 }, { d: '2026-07-09', t: '權息', k: 's', c: 3.6, s: 198.87165021, p: 79.7 }];
+console.log(JSON.stringify([divHTML([], 'TWSE', P), divHTML(dv, 'TWSE', P), divHTML(dv.slice(3, 4), 'TWSE', S), divHTML(tpex, 'TPEx', P)]));"""
+    o = _node(js)
+    if o is None:
+        return
+    empty, tw, stop, tp = o
+    assert "2025-10-30 起沒有除權息紀錄" in empty and "<table" not in empty and "<h2>股利與填息</h2>" in empty
+    assert "<th>除權息日</th><th>現金股利<br>（元）</th><th>配股<br>每千股</th><th>除權息<br>前收盤</th><th>填息</th>" in tw
+    rows = re.findall(r"<tr><td>(.*?)</tr>", tw)
+    assert [r[:10] for r in rows] == ["2026/09/02", "2026/07/06", "2026/07/16", "2026/03/26", "2026/07/01", "2026/06/10"]   # 新到舊
+    assert "08/28<span>第 56 個交易日</span>" in tw and "當天<span>第 1 個交易日</span>" in tw
+    assert "不再比較<span>07/16 配股後</span>" in tw and "尚未填息<span>還差 25.00 元，+25.00%</span>" in tw
+    assert "2026/07/06<span>除權息</span>" in tw and "上市除權息的官方表只有權值＋息值合計 5.36055 元，無法拆分現金與配股" in tw
+    assert '<span title="純配股不計算填權">--</span>' in tw and "權值＋息值 5,185.002642 元\">有</span>" in tw
+    assert '<td class="num">5.2404</td>' in tw and '<td class="num">160</td>' in tw                                      # 最多 4 位、去尾 0
+    assert "尚未填息<span>還差 45.00 元，+56.25%，最後成交 11/12</span>" in stop                                          # 停牌：寫最後成交
+    assert '<td class="num">100.00</td>' in tp and '<td class="num">198.87</td>' in tp and '<td class="num">3.6</td>' in tp
+    assert "<span>除權</span></td><td class=\"num\"><span>--</span></td>" in tp                                          # 上櫃純配股：現金 0 → --
+    # 卡片在基本面分頁、季報卡之後；說明用變數傳入（test_iter13 數 noteHTML 字面呼叫）
+    i = STK.index("${data.dv ? divHTML(data.dv, data.market, P) : ''}")
+    assert STK.index("<h2>季報</h2>") < i < STK.index("<section class=\"sec card\">", i) and "noteHTML(short, full)" in _grab(STK, "divHTML")
+    assert len(re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)) == 8
+
+
+def test_js_insti_net():
+    lines = [l.strip() for l in STK.splitlines() if l.strip().startswith(("const has = I?.f[i] != null", "const inst = { f: has", "inst.net = has"))]
+    assert len(lines) == 3 and "I.n?.[i] ??" in lines[2]
+    js = "function net(I, i) {\n" + "\n".join(lines) + "\nreturn inst.net; }\n" + """
+const I = { f: [10, 3, null], t: [null, 1, null], dl: [2, null, null], n: [13, null, null] }, Old = { f: [10], t: [1], dl: [2] };
+console.log(JSON.stringify([net(I, 0), net(I, 1), net(I, 2), net(Old, 0), net(undefined, 0)]));"""
+    o = _node(js)
+    if o is not None:
+        assert o == [13, 4, None, 13, None]                     # 官方合計；n 為 null 時三者相加；舊 JSON 沒有 n；ETF 沒有法人
+    assert "const NET_TIP = '合計 = 官方三大法人合計" in STK and "合計${mode === '日' ? '' : '（每日相加）'}" in STK
+
+
+# ─── F24-7a：收集紀錄的事件筆數 ─────────────────────────
+class EvWorld(World):
+    """事件端點：TWT49U 回 3 檔股票（含 1 列現增）、2 檔 ETF；其他三個端點沒有資料。"""
+
+    def http(self, method, url, timeout=30, params=None, data=None, json=None):
+        if "TWT49U" in url and "TWT49U" not in self.down:
+            self.requests.append(("/rwd/zh/exRight/TWT49U", params or {}))
+            keep = [r for r in T49["data"] if r[1] in ("2421", "6669")] + [r for r in T49["data"] if r[1] == "0056"][:2]
+            return t3.Resp({"stat": "OK", "fields": T49["fields"], "data": keep})
+        return super().http(method, url, timeout, params, data, json)
+
+
+def test_detail_events_count():
+    w = EvWorld(D(10, 30))
+    w.publish(t3.FIRST_DAY)
+    rc, out = t3.run_world(w, T(11, 2, 18, 0))
+    und = json.loads(w.runs[-1][2])["undated"]
+    assert rc == 0 and und["events_to"] == "2026-11-02" and und["events"] == {"stocks": 4, "etfs": 2}
+    assert "股票 4 筆、ETF 2 筆" in out and "price_events" in w.merges and "etf_events" in w.merges
+    # 端點失敗：沒有 events_to、events，errors 有 events
+    w = EvWorld(D(10, 30))
+    w.publish(t3.FIRST_DAY)
+    w.down.add("TWT49U")
+    rc, out = t3.run_world(w, T(11, 2, 18, 0))
+    d = json.loads(w.runs[-1][2])
+    assert rc == 1 and "events" in d["errors"] and "events" not in d["undated"] and "events_to" not in d["undated"]
+
+
+# ─── F24-7b：check 的新行 ───────────────────────────────
+def test_check_lines():
+    now = T(11, 3, 10, 0)
+    days = health.due_days(now, 20, CLOSED)
+    snap = t3._full_snapshot(days)
+    base = {"alerts_at": datetime(2026, 11, 2, 19, 35), "events_to": D(11, 2), "revenue_on": D(11, 2), "collected_at": None,
+            "last_run": {"at": datetime(2026, 11, 2, 19, 35), "command": "catch-up", "new_data": True}}
+    ok = lambda s: health.check_report(days, snap, now, s, CLOSED)
+    text, rc = ok({})
+    assert rc == 0 and "除權息事件最後成功：尚無執行紀錄" in text
+    text, rc = ok(base)                                                                 # 舊格式：沒有時間與筆數
+    assert rc == 0 and "除權息事件最後成功：至 2026-11-02\n" in text + "\n"
+    s = dict(base, events_at=datetime(2026, 11, 2, 19, 36), events_n={"stocks": 1678, "etfs": 1138},
+             warnings=["官方休市表更新失敗（沿用已存的官方表）：HTTP 500"])
+    text, rc = ok(s)
+    lines = text.splitlines()
+    assert rc == 0 and "除權息事件最後成功：至 2026-11-02（2026-11-02 19:36），股票 1,678 筆、ETF 1,138 筆（含往回 7 天重查）" in lines
+    assert "⚠️  最後一次收集的警告：官方休市表更新失敗（沿用已存的官方表）：HTTP 500" in lines
+    i = lines.index("除權息事件最後成功：至 2026-11-02（2026-11-02 19:36），股票 1,678 筆、ETF 1,138 筆（含往回 7 天重查）")
+    assert lines[i - 1].startswith("處置／注意股最後成功") and i > 2 and i < len(lines) - 1 and "無異常" in text
+    old = ok(base)[0].splitlines()
+    assert not any(l.startswith("❌") for l in lines) and lines[:i] + lines[i + 2:] == [l for l in old if not l.startswith("除權息事件")]   # 其他行不變
+
+
+class _Cur:
+    def __init__(self, rows):
+        self.rows = rows
+
+    def execute(self, *a):
+        return self
+
+    def fetchall(self):
+        return self.rows
+
+
+def test_load_state_new_keys():
+    j = lambda **k: json.dumps(k)
+    rows = [(datetime(2026, 11, 3, 21, 45), 0, j(undated={}, warnings=["官方休市表更新失敗"]), "catch-up", "ok", None),
+            (datetime(2026, 11, 3, 19, 30), 1, j(undated={"events_to": "2026-11-03", "events": {"stocks": 5, "etfs": 2}}), "catch-up", "abnormal", None),
+            (datetime(2026, 11, 2, 19, 30), 1, j(undated={"events_to": "2026-11-02"}), "catch-up", "ok", 25.1)]
+    s = health.load_state(_Cur(rows))
+    assert s["events_to"] == D(11, 3) and s["events_at"] == datetime(2026, 11, 3, 19, 30) and s["events_n"] == {"stocks": 5, "etfs": 2}
+    assert s["warnings"] == ["官方休市表更新失敗"] and s["export_failed"] is True
+    s = health.load_state(_Cur(rows[1:2] + [rows[2][:5] + (25.1,)]))
+    assert s["export_failed"] is True and s["warnings"] == []
+    s = health.load_state(_Cur([rows[0], (datetime(2026, 11, 3, 19, 30), 1, j(undated={}), "catch-up", "abnormal", 24.0)]))
+    assert s["export_failed"] is False                                                  # 有匯出耗時：匯出成功（異常是資料集）
+    s = health.load_state(_Cur([r[:4] for r in rows]))                                 # 舊的 4 欄、3 欄假資料
+    assert s["export_failed"] is False and s["events_n"] == {"stocks": 5, "etfs": 2}
+    s = health.load_state(_Cur([r[:3] for r in rows[2:]]))
+    assert s["export_failed"] is False and s["events_n"] is None and s["events_at"] == datetime(2026, 11, 2, 19, 30)
+    s = health.load_state(_Cur([]))
+    assert s["export_failed"] is None and s["events_n"] is None and s["warnings"] == []
+
+
+# ─── F24-7d（QA-03）：只有上櫃公布時不重複匯出 ──────────────
+def test_qa03_tpex_only():
+    with tempfile.TemporaryDirectory() as tmp:
+        site = Path(tmp)
+        w = World(D(10, 30))
+        t3.run_site(w, T(10, 30, 22, 0), site)
+        twse = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "MI_MARGN", "TWT93U")
+        w.publish(t3.FIRST_DAY, *twse)
+        rc, _, L = t3.run_site(w, T(11, 2, 17, 0), site, T(11, 2, 17, 1))
+        assert w.exports == 1 and L["date"] == "2026-11-02" and t3.FIRST_DAY not in w.rows["prices.TWSE"]
+        for h in (17, 18):
+            rc, out, _ = t3.run_site(w, T(11, 2, h, 30), site, T(11, 2, h, 31))
+            assert w.exports == 1 and "沒有新資料，不匯出" in out, h
+        for ep in twse:
+            w.published[ep].add(t3.FIRST_DAY)
+        rc, _, L = t3.run_site(w, T(11, 2, 19, 30), site, T(11, 2, 19, 31))
+        assert rc == 0 and w.exports == 2 and t3.FIRST_DAY in w.rows["prices.TWSE"]
+        rc, out, _ = t3.run_site(w, T(11, 2, 20, 0), site, T(11, 2, 20, 1))
+        assert w.exports == 2
+
+
+# ─── F24-7e（QA-09）：匯出失敗後下一次補匯出 ────────────────
+class Cursor24(t3.FakeCursor):
+    """collect_runs 回 6 欄（含 outcome、export_seconds）；種子紀錄視為已匯出成功。"""
+
+    def execute(self, sql, *params):
+        w = self.w
+        meta = w.__dict__.setdefault("meta24", {})
+        if "FROM collect_runs" in sql:
+            self.result = [(f, n, d, "catch-up", *meta.get(i, ("ok", 1.0))) for i, (f, n, d) in enumerate(w.runs, 1)][::-1]
+            return self
+        super().execute(sql, *params)
+        if sql.startswith("INSERT INTO collect_runs"):
+            meta[len(w.runs)] = (params[3], None)
+        elif sql.startswith("UPDATE collect_runs"):
+            meta[params[2]] = (params[0], params[1])
+        return self
+
+
+def _run24(w, now, export_error=None, no_export=False):
+    def exporter():
+        w.exports += 1
+        if export_error:
+            raise export_error
+        return 1.0
+    buf = io.StringIO()
+    with t3.env(w), mock.patch.object(t3, "FakeCursor", Cursor24), mock.patch.object(export, "export_all", exporter), \
+            contextlib.redirect_stdout(buf):
+        rc = catchup.run(now=now, no_export=no_export)
+    return rc, buf.getvalue()
+
+
+def test_qa09_retry_export():
+    # 處置股有新資料（只有沒有日期的資料變動）、匯出失敗 → 下一次（沒有新資料、狀態沒變）補匯出；補匯出又失敗 → 再下一次繼續補；成功後不再匯出
+    def counts(*seq):
+        return mock.patch.object(catchup, "_undated_counts", mock.Mock(side_effect=list(seq) + [seq[-1]] * 40))
+    w = World(D(10, 30))
+    with mock.patch.object(catchup, "collect_alerts", lambda: None), counts((1,), (2,)):
+        rc, out = _run24(w, T(10, 31, 10, 0), export_error=OSError("磁碟已滿"))
+        assert rc == 1 and w.exports == 1 and "匯出失敗" in out and w.runs[-1][1] == 1 and w.meta24[len(w.runs)] == ("abnormal", None)
+        rc, out = _run24(w, T(10, 31, 11, 0), export_error=OSError("磁碟已滿"))
+        assert rc == 1 and w.exports == 2 and w.runs[-1][1] == 0 and w.meta24[len(w.runs)] == ("abnormal", None)
+        rc, out = _run24(w, T(10, 31, 12, 0))
+        assert rc == 0 and w.exports == 3 and w.meta24[len(w.runs)] == ("ok", 1.0)
+        rc, out = _run24(w, T(10, 31, 13, 0))
+        assert rc == 0 and w.exports == 3 and "沒有新資料，不匯出" in out
+    # --no-export 那次不補，下一次補
+    w = World(D(10, 30))
+    with mock.patch.object(catchup, "collect_alerts", lambda: None), counts((1,), (2,)):
+        _run24(w, T(10, 31, 10, 0), export_error=OSError("磁碟已滿"))
+        rc, out = _run24(w, T(10, 31, 11, 0), no_export=True)
+        assert w.exports == 1
+        rc, out = _run24(w, T(10, 31, 12, 0))
+        assert rc == 0 and w.exports == 2
+    # 沒有新資料、上次匯出成功（env 之下）：0 次匯出（舊行為不變）
+    w = World(D(10, 30))
+    rc, out = _run24(w, T(10, 31, 10, 0))
+    assert rc == 0 and w.exports == 0
+
+
+# ─── F24-7c：訊息 ───────────────────────────────────────
+def test_qa07_messages():
+    w = World(D(12, 24))
+    rc, out = t3.run_world(w, T(12, 25, 18, 0), date_=D(12, 25))
+    assert "休市日沒有要抓的資料，不需要請求" in out and "最近 0 個交易日" not in out
+    w = World(D(10, 30))
+    w.rows["index.TPEX"] = {d: r for d, r in w.rows["index.TPEX"].items() if d.month == 10}
+    buf = io.StringIO()
+    with t3.env(w), contextlib.redirect_stdout(buf):
+        assert history.run_history(D(9, 29), D(10, 30), ("tpex_index",)) is True
+    assert "待抓 1 個月" in buf.getvalue() and "✅ 成功：1 個月" in buf.getvalue() and "待抓 0 天" not in buf.getvalue()
+    fetch._dead_hosts.clear()
+    with mock.patch.object(fetch._SESSION, "request", lambda *a, **k: t3.Resp(status=500)), mock.patch.object(fetch, "RETRY_BACKOFF", (30,)), \
+            mock.patch.object(fetch, "MIN_INTERVAL", {}), mock.patch.object(fetch, "DEFAULT_INTERVAL", 0), \
+            mock.patch.object(fetch.time, "sleep", lambda s: None), contextlib.redirect_stdout(io.StringIO()):
+        for isolated, words in ((True, ("附屬查詢失敗（不重試，收集繼續）",)), (False, ("連續失敗，可能已被封鎖",))):
+            try:
+                fetch.request("GET", "https://www.twse.com.tw/x", isolated=isolated)
+                assert False
+            except FetchError as e:
+                assert all(x in str(e) for x in words) and (not isolated or "封鎖" not in str(e)), str(e)
+    fetch._dead_hosts.clear()
+
+
+# ─── F24-7f：events 加鎖 ────────────────────────────────
+def test_events_lock():
+    from twstock import __main__ as cli
+    calls, rel = [], []
+
+    def run(lock, effect=None):
+        calls.clear()
+        rel.clear()
+
+        def fake(s, e):
+            calls.append((s, e))
+            if effect:
+                raise effect
+            return {"stocks": 0, "etfs": 0}
+        buf = io.StringIO()
+        with mock.patch.object(db, "acquire_lock", lambda: "L" if lock else None), mock.patch.object(db, "release_lock", rel.append), \
+                mock.patch.object(events, "collect_events", fake), mock.patch.object(db, "connect", mock.Mock(side_effect=AssertionError)), \
+                mock.patch.object(fetch._SESSION, "request", mock.Mock(side_effect=AssertionError)), contextlib.redirect_stdout(buf):
+            rc = cli.main(["events", "--start", "2026-11-07", "--end", "2026-11-14"])
+        return rc, buf.getvalue()
+    rc, out = run(False)
+    assert rc == 1 and calls == [] and rel == [] and "另一個收集程序正在執行" in out
+    assert run(True) == (0, "") and calls == [(D(11, 7), D(11, 14))] and rel == ["L"]
+    rc, out = run(True, FetchError("www.twse.com.tw 連續失敗"))
+    assert rc == 1 and rel == ["L"] and "MERGE 覆寫" in out
+    try:
+        run(True, RuntimeError("x"))
+        assert False
+    except RuntimeError:
+        assert rel == ["L"]
+
+
+# ─── 用詞、README ───────────────────────────────────────
+def test_no_advice_words():
+    seg = _grab(STK, "divHTML") + _grab(STK, "NET_TIP") + _grab(STK, "dfmt")
+    seg += "".join(l[l.index("第 24 輪"):] for l in README.splitlines() if "第 24 輪" in l)
+    assert seg.count("第 24 輪") >= 4, seg.count("第 24 輪")
+    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
+              "利多", "利空", "看多", "看空", "轉強", "轉弱",
+              "跑贏", "跑輸", "強於大盤", "弱於大盤", "贏過", "輸給", "領先", "落後", "抗跌", "超額報酬", "獲利能力佳", "惡化",
+              "填息行情", "貼息", "填息機率", "配息穩定", "高殖利率首選", "存股"):
+        assert w not in seg, w
+    for s in ("etf_events", "div_total", "stock_div", "insti.n"):
+        assert s in README, s
+
+
+if __name__ == "__main__":
+    for n, f in list(globals().items()):
+        if n.startswith("test_") and callable(f):
+            f()
+            print("ok", n)
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/__main__.py proj/twstock/__main__.py
--- orig/twstock/__main__.py	2026-11-14 11:08:24
+++ proj/twstock/__main__.py	2026-11-14 18:50:28
@@ -15,7 +15,7 @@
   python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過）
   python -m twstock history --start 2024-01-01 --only financials  只補季報（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
-  python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用；第 19 輪起另存減除股利參考價，分辨配股與現金增資）
+  python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用；第 19 輪起另存減除股利參考價，分辨配股與現金增資；第 24 輪起一併寫入股利金額與 ETF 除息；和收集共用鎖）
   python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/、etfp/；含季報、期現貨價差與下次結算日、營收與 EPS 基期、ETF 個股頁、處置／注意股清單與接近處置推算）
   python -m twstock serve                            本機預覽網站 http://localhost:8000
   python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
@@ -109,12 +109,19 @@
 
 def cmd_events(args):
     from .collectors.events import collect_events
+    from .db import acquire_lock, release_lock
     from .fetch import FetchError
+    lock = acquire_lock()           # 第 24 輪 F24-7f：和每晚收集、history 用同一把鎖
+    if lock is None:
+        print("⏭️  另一個收集程序正在執行，請稍後再跑（同時跑會超過網站節流）")
+        return 1
     try:
         collect_events(args.start, args.end or date.today())
     except FetchError as e:
         print(f"\n❌ {e}\n   稍後用同樣的指令重跑即可（MERGE 覆寫，不會重複）")
         return 1
+    finally:
+        release_lock(lock)
     return 0
 
 
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/collectors/catchup.py proj/twstock/collectors/catchup.py
--- orig/twstock/collectors/catchup.py	2026-11-06 23:47:12
+++ proj/twstock/collectors/catchup.py	2026-11-14 18:36:22
@@ -129,8 +129,10 @@
         _guard("index.TPEX", errors, collect_tpex_index, y, m)
     if plan["alerts"] and _guard("alerts", errors, collect_alerts):
         undated["alerts"] = now.isoformat(timespec="seconds")
-    if plan["events"] and _guard("events", errors, collect_events, *plan["events"]):
+    got = {}
+    if plan["events"] and _guard("events", errors, lambda: got.update(collect_events(*plan["events"]))):
         undated["events_to"] = str(plan["events"][1])
+        undated["events"] = got                 # 第 24 輪 F24-7a：{"stocks": 筆數, "etfs": 筆數}
     if plan["revenue"] and not no_revenue:
         if all([_guard("revenue", errors, collect_monthly_revenue, y, m) for y, m in plan["revenue"]]):
             undated["revenue"] = str(now.date())
@@ -257,7 +259,7 @@
             gap_hint = between[0]
 
     if plan_is_empty(plan):
-        print(f"✅ 最近 {len(plan['days'])} 個交易日資料齊全，不需要請求")
+        print(f"✅ 最近 {len(plan['days'])} 個交易日資料齊全，不需要請求" if plan["days"] else "✅ 休市日沒有要抓的資料，不需要請求")
         written, errors, undated = {}, {}, {}
     else:
         written, errors, undated = execute_plan(plan, now, no_revenue)
@@ -312,12 +314,12 @@
         conn.close()
 
     export_failed = False
-    data_date = max((d for d, r in after["prices.TWSE"].items() if r.n), default=None)
-    # closed 的起點要和匯出時相同（export 的資料日是兩市場的最新日），否則只有上櫃公布時會誤判為變動
-    site_date = max((d for k in ("prices.TWSE", "prices.TPEx") for d, r in after[k].items() if r.n), default=None)
-    need_export = not no_export and (date_ is not None or changed or
+    # 資料日、closed 的起點都要和匯出時相同（export 的資料日是兩市場的最新日），否則只有上櫃公布時每次都會誤判為變動（QA-03）
+    data_date = max((d for k in ("prices.TWSE", "prices.TPEx") for d, r in after[k].items() if r.n), default=None)
+    # 第 24 輪 F24-7e（QA-09）：上一次有新資料或有匯出的紀錄是匯出失敗 → 這次補匯出（--no-export 除外）
+    need_export = not no_export and (date_ is not None or changed or state.get("export_failed") or
                                      (data_date is not None and status_changed(health.dataset_status(after, data_date, now, closed),
-                                                                               health.site_closed(closed, site_date))))
+                                                                               health.site_closed(closed, data_date))))
     if need_export:
         export_seconds = None
         try:
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/collectors/events.py proj/twstock/collectors/events.py
--- orig/twstock/collectors/events.py	2026-11-09 22:27:15
+++ proj/twstock/collectors/events.py	2026-11-14 18:32:40
@@ -5,7 +5,7 @@
 from datetime import timedelta
 
 from .. import db
-from ..fetch import FetchError, clean_number, is_valid_stock_code, request
+from ..fetch import FetchError, clean_number, is_etf_code, is_valid_stock_code, request
 from .alerts import roc_date
 
 EVENT_TYPES = ("息", "權", "權息", "減", "面")
@@ -24,17 +24,28 @@
     "TPEX_EX": ("POST", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", "%Y/%m/%d",
                 ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None, "減除股利參考價"),
 }
+# 第 24 輪 F24-5：股利金額欄（選用，找不到或無法解析存 NULL）：(權值+息值, 現金股利, 每仟股無償配股)；ETF 只取這兩個來源的「息」
+# 上市只有「權值+息值」：「息」= 現金股利，「權」「權息」混了配股與現增，現金股利存 NULL
+_AMOUNTS = {"TWT49U": ("權值+息值", None, None), "TPEX_EX": ("權值+息值", "息值", "每仟股無償配股")}
 
 
 def parse_events(source: str, fields, rows) -> list:
-    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；必要欄位缺漏回傳 []（減除股利參考價缺漏只存 None）。"""
+    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；必要欄位缺漏回傳 []（減除股利參考價缺漏只存 None）。
+    第 24 輪：回傳不變（不含股利金額、ETF）；收集用 parse_events_all。"""
+    return [{k: v for k, v in r.items() if k not in ("div_total", "div_cash", "stock_div")} for r in parse_events_all(source, fields, rows)[0]]
+
+
+def parse_events_all(source: str, fields, rows) -> tuple:
+    """第 24 輪 F24-5：(股票, ETF)。股票 dict 另帶有值的 div_total、div_cash、stock_div；ETF 只收 TWT49U、TPEX_EX 的「息」，
+    {etf_code, event_date, event_type, prev_close, ref_price, source, div_cash}。ETN、受益證券、特別股等兩邊都不收。"""
     names, fixed, dcol = _SOURCES[source][3:6]
     idx = {f: i for i, f in enumerate(fields or [])}
     j = idx.get(dcol)
+    amt = [idx.get(n) if n else None for n in _AMOUNTS.get(source, (None,) * 3)]
     need = [n for n in names if n]
     if not all(n in idx for n in need):
-        return []
-    out = []
+        return [], []
+    out, etfs = [], []
     for row in rows or []:
         if len(row) <= max(idx[n] for n in need):
             continue
@@ -42,11 +53,18 @@
         prev, ref = clean_number(row[idx[names[2]]]), clean_number(row[idx[names[3]]])
         kind = fixed or str(row[idx[names[4]]]).strip().lstrip("除")     # 櫃買為「除權息」→「權息」
         div = clean_number(row[j]) if j is not None and j < len(row) else None
-        if not is_valid_stock_code(code) or d is None or not prev or not ref or kind not in EVENT_TYPES:
+        total, cash, stock = (clean_number(row[k]) if k is not None and k < len(row) else None for k in amt)
+        if source == "TWT49U" and kind == "息":
+            cash = total
+        if d is None or not prev or not ref or kind not in EVENT_TYPES:
             continue
-        out.append({"stock_code": code, "event_date": d.isoformat(), "event_type": kind,
-                    "prev_close": prev, "ref_price": ref, "source": source, **({"div_ref": div} if div else {})})
-    return out
+        base = {"event_date": d.isoformat(), "event_type": kind, "prev_close": prev, "ref_price": ref, "source": source}
+        if is_valid_stock_code(code):
+            out.append({"stock_code": code, **base, **({"div_ref": div} if div else {}),
+                        **{k: v for k, v in (("div_total", total), ("div_cash", cash), ("stock_div", stock)) if v is not None}})
+        elif is_etf_code(code) and source in _AMOUNTS and kind == "息":
+            etfs.append({"etf_code": code, **base, **({"div_cash": cash} if cash is not None else {})})
+    return out, etfs
 
 
 def fetch_events(source: str, start, end) -> list:
@@ -57,20 +75,23 @@
         raise FetchError(f"事件回應格式不符：{source}")
     if source == "TPEX_EX":
         data = next((t for t in data.get("tables", []) if "代號" in (t.get("fields") or [])), {})
-    return parse_events(source, data.get("fields"), data.get("data"))
+    return parse_events_all(source, data.get("fields"), data.get("data"))
 
 
-def collect_events(start, end) -> int:
-    """[start, end] 依 CHUNK_DAYS 切段，四個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
-    rows, s = [], start
+def collect_events(start, end) -> dict:
+    """[start, end] 依 CHUNK_DAYS 切段，四個端點全部抓完才寫入；只寫入 stocks、etfs 表已有的代號。回傳 {"stocks": 筆數, "etfs": 筆數}。"""
+    rows, etfs, s = [], [], start
     while s <= end:
         e = min(end, s + timedelta(days=CHUNK_DAYS - 1))
         for source in _SOURCES:
-            rows += fetch_events(source, s, e)
+            got = fetch_events(source, s, e)
+            rows += got[0]
+            etfs += got[1]
         s = e + timedelta(days=1)
     # 同鍵只留一筆，避免 MERGE 同一列被更新兩次
     rows = list({(r["stock_code"], r["event_date"], r["source"]): r for r in rows}.values())
-    if rows:
+    etfs = list({(r["etf_code"], r["event_date"], r["source"]): r for r in etfs}.values())
+    if rows or etfs:
         conn = db.connect()
         try:
             conn.cursor().execute("""
@@ -79,20 +100,43 @@
                     SELECT st.stock_id, j.*
                     FROM OPENJSON(?) WITH (
                         stock_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
-                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_ref DECIMAL(10,2), source NVARCHAR(10)
+                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_ref DECIMAL(10,2), source NVARCHAR(10),
+                        div_total DECIMAL(12,6), div_cash DECIMAL(12,6), stock_div DECIMAL(14,8)
                     ) AS j
                     JOIN stocks st ON st.stock_code = j.stock_code
                 ) AS s
                 ON t.stock_id = s.stock_id AND t.event_date = s.event_date AND t.source = s.source
                 WHEN MATCHED THEN UPDATE SET
                     event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price,
+                    div_total = COALESCE(s.div_total, t.div_total), div_cash = COALESCE(s.div_cash, t.div_cash),
+                    stock_div = COALESCE(s.stock_div, t.stock_div),
                     div_ref = COALESCE(s.div_ref, t.div_ref)     -- 欄位暫時找不到時不清掉已存的值
                 WHEN NOT MATCHED THEN
-                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, div_ref, source)
-                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_ref, s.source);
+                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, div_ref, source, div_total, div_cash, stock_div)
+                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_ref, s.source,
+                            s.div_total, s.div_cash, s.stock_div);
             """, db.to_json(rows))
+            # 第 24 輪 F24-5：ETF 除息（只寫 etfs 表已有的 ETF；金額缺漏時不清掉已存的值）
+            conn.cursor().execute("""
+                MERGE etf_events AS t
+                USING (
+                    SELECT et.etf_id, j.*
+                    FROM OPENJSON(?) WITH (
+                        etf_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
+                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_cash DECIMAL(12,6), source NVARCHAR(10)
+                    ) AS j
+                    JOIN etfs et ON et.etf_code = j.etf_code
+                ) AS s
+                ON t.etf_id = s.etf_id AND t.event_date = s.event_date AND t.source = s.source
+                WHEN MATCHED THEN UPDATE SET
+                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price,
+                    div_cash = COALESCE(s.div_cash, t.div_cash)
+                WHEN NOT MATCHED THEN
+                    INSERT (etf_id, event_date, event_type, prev_close, ref_price, div_cash, source)
+                    VALUES (s.etf_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_cash, s.source);
+            """, db.to_json(etfs))
             conn.commit()
         finally:
             conn.close()
-    print(f"  📌 除權息／減資／面額變更事件：{len(rows)} 筆（{start} ～ {end}）")
-    return len(rows)
+    print(f"  📌 除權息／減資／面額變更事件：股票 {len(rows)} 筆、ETF {len(etfs)} 筆（{start} ～ {end}）")
+    return {"stocks": len(rows), "etfs": len(etfs)}
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/collectors/history.py proj/twstock/collectors/history.py
--- orig/twstock/collectors/history.py	2026-11-07 00:56:37
+++ proj/twstock/collectors/history.py	2026-11-14 18:36:22
@@ -109,7 +109,8 @@
 
     est = (sum(day_seconds(ks) + delay for _, ks in todo) + SECONDS_PER_MONTH * len(months)) / 60
     print(f"📅 補抓範圍：{start} ~ {end}，資料集：{'、'.join(datasets)}")
-    print(f"📊 交易日 {len(days)} 天，待抓 {len(todo)} 天；⏱️  預估約 {est:.1f} 分鐘")
+    # 第 24 輪 F24-7c：只選了以月為單位的櫃買指數時寫月數（以日為單位的照舊）
+    print(f"📊 交易日 {len(days)} 天，待抓 {f'{len(todo)} 天' if keys else f'{len(months)} 個月'}；⏱️  預估約 {est:.1f} 分鐘")
     for k in keys:
         n = sum(k in ks for _, ks in todo)
         if n:
@@ -117,7 +118,7 @@
     if months:
         print(f"   櫃買指數：{len(months)} 個月")
 
-    success, no_data, blocked_at, schema_err = 0, [], None, None
+    success, no_data, blocked_at, schema_err, month_ok = 0, [], None, None, 0
     for i, (d, ks) in enumerate(todo, 1):
         print(f"[{i}/{len(todo)}]", end="")
         written, errors = collect_for_date(d, ks)
@@ -140,6 +141,7 @@
         for y, m in months:
             try:
                 collect_tpex_index(y, m)
+                month_ok += 1
             except FetchError as e:
                 print(f"  ❌ {e}")
                 blocked_at = date(y, m, 1)
@@ -160,7 +162,7 @@
                 blocked_at = end
                 break
 
-    print(f"\n{'=' * 50}\n✅ 成功：{success} 天")
+    print(f"\n{'=' * 50}\n✅ 成功：{f'{success} 天' if keys else f'{month_ok} 個月'}")
     if no_data:
         print(f"ℹ️  無資料（未列入休市表的休市日或尚未公布）：{', '.join(map(str, no_data))}")
     if schema_err:
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/db.py proj/twstock/db.py
--- orig/twstock/db.py	2026-11-09 22:27:15
+++ proj/twstock/db.py	2026-11-14 18:50:54
@@ -506,10 +506,30 @@
         CONSTRAINT UQ_etf_sbl UNIQUE (etf_id, trade_date)
     )
     """,
+    # 第 24 輪 F24-5：ETF 除息（官方 TWT49U、櫃買 exDailyQ；和 price_events 分開，個股統計不會讀到）
+    """
+    IF OBJECT_ID('etf_events') IS NULL
+    CREATE TABLE etf_events (
+        id          INT IDENTITY(1,1) PRIMARY KEY,
+        etf_id      INT           NOT NULL REFERENCES etfs(etf_id),
+        event_date  DATE          NOT NULL,   -- 官方除息日
+        event_type  NVARCHAR(4)   NOT NULL CHECK (event_type IN (N'息', N'權', N'權息')),
+        prev_close  DECIMAL(10,2) NOT NULL,
+        ref_price   DECIMAL(10,2) NOT NULL,
+        div_cash    DECIMAL(12,6) NULL,       -- 每單位配息：上市「權值+息值」、上櫃「息值」
+        source      NVARCHAR(10)  NOT NULL,   -- TWT49U / TPEX_EX
+        created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_events UNIQUE (etf_id, event_date, source)
+    )
+    """,
     # 第 11 輪：發行股數（update_industry 一併寫入；目前股數，不保留歷史）
     "IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL",
     # 第 19 輪：減除股利參考價（只扣股利、不扣現金增資；TWT49U、TPEX_EX 才有，其他來源 NULL），分辨配股與現金增資
     "IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE price_events ADD div_ref DECIMAL(10,2) NULL",
+    # 第 24 輪 F24-5：股利金額（TWT49U、TPEX_EX 才有，其他來源 NULL）：權值+息值、每股現金股利（上市只有「息」）、每仟股無償配股（只有上櫃）
+    "IF COL_LENGTH('price_events', 'div_total') IS NULL ALTER TABLE price_events ADD div_total DECIMAL(12,6) NULL",
+    "IF COL_LENGTH('price_events', 'div_cash') IS NULL ALTER TABLE price_events ADD div_cash DECIMAL(12,6) NULL",
+    "IF COL_LENGTH('price_events', 'stock_div') IS NULL ALTER TABLE price_events ADD stock_div DECIMAL(14,8) NULL",
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -550,4 +570,4 @@
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
           "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
           "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、quarterly_financials、"
-          "sbl_trades、etf_sbl（第 11 輪另加 stocks.shares）、etf_holding_gaps")
+          "sbl_trades、etf_sbl（第 11 輪另加 stocks.shares）、etf_events（第 24 輪另加 price_events 股利欄）、etf_holding_gaps")
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/export.py proj/twstock/export.py
--- orig/twstock/export.py	2026-11-14 11:08:24
+++ proj/twstock/export.py	2026-11-14 18:33:29
@@ -291,6 +291,38 @@
     return None
 
 
+def dividends(d_, c, ev, official):
+    """
+    第 24 輪 F24-6：股利與填息（舊到新）。ev = _price_events 的事件，official = 同一檔的官方事件（"a" = (權值+息值, 現金股利, 每仟股配股)）。
+    列入：息、權息（算填息）；權且 k 為 s、sc（純配股：只列，不算填權）。只有現增（k = c）或分類不明的權不列。
+    填息：從事件列（含）起第一個收盤 ≥ 除權息前收盤的資料列，n = 第幾個交易日（事件列 = 1，含無成交日）；原始價、不設期限。
+    D37-1：還沒填息就遇到之後的股本變動（權、權息但 k 不是 c；減資、面額變更、上櫃反推），停在那一列：x = [日期, 原因]。
+    """
+    stop = {e["i"]: "配股" if e.get("k") == "s" else {"權": "除權", "權息": "除權息", "減": "減資", "面": "面額變更", "調": "股本變動"}[e["t"]]
+            for e in ev if e["t"] in ("減", "面", "調") or (e["t"] in ("權", "權息") and e.get("k") != "c")}
+    out = []
+    for e in ev:
+        if not (e["t"] in ("息", "權息") or (e["t"] == "權" and e.get("k") in ("s", "sc"))):
+            continue
+        i, p = e["i"], e["p"]
+        o = next((x for x in official if bisect_left(d_, x["d"]) == i and (x["t"], x["p"], x["r"]) == (e["t"], p, e["r"])), {})
+        total, cash, stock = o.get("a") or (None,) * 3
+        # c 現金股利、s 每仟股配股（有才輸出）；a 權值+息值只在沒有現金股利時輸出（上市權、權息的 title 用）
+        row = {"d": e["d"], "t": e["t"], **({"k": e["k"]} if "k" in e else {}), **({"c": cash} if cash is not None else {}),
+               **({"s": stock} if stock else {}), **({"a": total} if cash is None and total is not None else {}), "p": p}
+        out.append(row)
+        if e["t"] == "權":
+            continue
+        for j in range(i, len(d_)):
+            if j > i and j in stop:
+                row["x"] = [str(d_[j]), stop[j]]
+                break
+            if c[j] is not None and float(c[j]) >= p:
+                row.update(f=str(d_[j]), n=j - i + 1)
+                break
+    return out
+
+
 def amount_by_market(rows):
     """F9-1：rows = [(日期, 市場, 單位, 買賣差額)] → {"TWSE": {日期: {單位: 差額}}, "TPEx": {…}}；insti_official 只用 TWSE。"""
     out = {"TWSE": defaultdict(dict), "TPEx": defaultdict(dict)}
@@ -1477,12 +1509,14 @@
         WHERE a.alert_type = 'notice' AND a.announce_date >= ? AND a.announce_date <= ?""", watch_days[0], latest_date):
         watch_notes[code][ann] = clauses(reason)
     events = defaultdict(list)
-    for code, d, t, p, r, src, dr in cur.execute("""
-        SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source, e.div_ref
+    for code, d, t, p, r, src, dr, *amt in cur.execute("""
+        SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source, e.div_ref,
+               e.div_total, e.div_cash, e.stock_div
         FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
         ORDER BY s.stock_code, e.event_date"""):
         events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src,
-                             "k": rights_kind(t, float(p), float(r), dr and float(dr))})
+                             "k": rights_kind(t, float(p), float(r), dr and float(dr)),
+                             "a": tuple(None if x is None else float(x) for x in amt)})     # 第 24 輪 F24-6：股利金額
     mdates, mofficial, mstocks, metfs, mper = _load_margin(cur)
     first_m = min((ds[0] for ds in mdates.values()), default=latest_date)
     etf_px, etf_latest = _load_etfs(cur, first_m - timedelta(days=60))
@@ -1575,7 +1609,8 @@
             "ev": [{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e} for e in ev],
             "insti": {"f": [round(x / 1000) if x is not None else None for x in fn],   # 張
                       "t": [round(x / 1000) if x is not None else None for x in tn],
-                      "dl": [round(x / 1000) if x is not None else None for x in dn]},
+                      "dl": [round(x / 1000) if x is not None else None for x in dn],
+                      "n": [round(x / 1000) if x is not None else None for x in total]},     # 第 24 輪 F24-8：官方合計
             "revenue": rev_rows[-REVENUE_MONTHS:],
             # 第 10 輪 B5；第 15 輪 F15-1：c 加 eb（去年同期累計 EPS）
             **({"fin": {**fb, "c": {**fb["c"], "eb": fin_cum_base(fin[code])}}}
@@ -1597,6 +1632,7 @@
             # 第 23 輪 F23-1：近期表現；最後一列不是資料日（停牌、下市）或從沒成交 → 不輸出（同 latest.stocks）
             **({"pf": stock_perf(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], p_days,
                                  idx_close[info["market"]], w52_start)} if d_[-1] == latest_date and any(x is not None for x in c) else {}),
+            "dv": dividends(d_, c, ev, events.get(code, [])),      # 第 24 輪 F24-6：股利與填息（沒有紀錄是 []）
         })
         # 市場寬度：還原收盤（無成交日不列入）、成交額
         b_series[info["market"]].append({d_[i]: float(c[i]) * af[i] for i in range(len(d_)) if d_[i] >= b_from and c[i] is not None})
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/fetch.py proj/twstock/fetch.py
--- orig/twstock/fetch.py	2026-11-04 22:13:15
+++ proj/twstock/fetch.py	2026-11-14 18:36:22
@@ -111,6 +111,8 @@
                 time.sleep(pause)
     if not isolated:
         _dead_hosts.add(host)
+    if isolated:            # 第 24 輪 F24-7c：附屬查詢不重試，失敗不代表被封鎖
+        raise FetchError(f"{host} 附屬查詢失敗（不重試，收集繼續）：{last_err}")
     raise FetchError(f"{host} 連續失敗，可能已被封鎖，請稍後再跑：{last_err}")
 
 
diff -ruN -x .git -x data -x __pycache__ -x *.pyc -x logs -x fixtures orig/twstock/health.py proj/twstock/health.py
--- orig/twstock/health.py	2026-11-07 00:56:37
+++ proj/twstock/health.py	2026-11-14 18:36:22
@@ -228,19 +228,27 @@
     """
     由最近 200 筆執行紀錄整理：處置注意股、事件、營收、季報（financials_on）最後成功的時間，最後一次有新資料的時間，
     與最後一次收集（last_run：時間、指令、有無新資料）。
+    第 24 輪：events_at、events_n（事件最後成功那次的完成時間與 {"stocks", "etfs"} 筆數，舊紀錄沒有筆數為 None）、
+    warnings（最後一次收集的警告）、export_failed（最近一筆「有新資料或有匯出」的紀錄是 abnormal 且沒有匯出耗時 = 匯出失敗）。
     """
-    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "financials_on": None, "collected_at": None, "last_run": None}
+    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "financials_on": None, "collected_at": None, "last_run": None,
+             "events_at": None, "events_n": None, "warnings": [], "export_failed": None}
     for finished, new_data, detail, *extra in cur.execute(
-            "SELECT TOP 200 finished_at, new_data, detail, command FROM collect_runs ORDER BY run_id DESC").fetchall():
+            "SELECT TOP 200 finished_at, new_data, detail, command, outcome, export_seconds FROM collect_runs ORDER BY run_id DESC").fetchall():
+        d = json.loads(detail)
         if state["last_run"] is None:
             state["last_run"] = {"at": finished, "command": extra[0] if extra else None, "new_data": bool(new_data)}
+            state["warnings"] = d.get("warnings") or []
         if new_data and state["collected_at"] is None:
             state["collected_at"] = finished
-        und = json.loads(detail).get("undated", {})
+        if state["export_failed"] is None and (new_data or (len(extra) > 2 and extra[2] is not None)):
+            state["export_failed"] = len(extra) > 2 and extra[1] == ABNORMAL and extra[2] is None
+        und = d.get("undated", {})
         if und.get("alerts") and state["alerts_at"] is None:
             state["alerts_at"] = datetime.fromisoformat(und["alerts"])
         if und.get("events_to") and state["events_to"] is None:
             state["events_to"] = date.fromisoformat(und["events_to"])
+            state["events_at"], state["events_n"] = finished, und.get("events")
         if und.get("revenue") and state["revenue_on"] is None:
             state["revenue_on"] = date.fromisoformat(und["revenue"])
         if und.get("financials") and state["financials_on"] is None:
@@ -441,6 +449,12 @@
                                                     for label, d, r in gaps))
     alerts = state.get("alerts_at")
     out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
+    # 第 24 輪 F24-7b：除權息事件最後成功與筆數、最後一次收集的警告（只顯示，不算異常）
+    ev_to, ev_at, ev_n = state.get("events_to"), state.get("events_at"), state.get("events_n")
+    out.append(f"除權息事件最後成功：至 {ev_to}" + (f"（{ev_at:%Y-%m-%d %H:%M}）" if ev_at else "") +
+               (f"，股票 {ev_n.get('stocks', 0):,} 筆、ETF {ev_n.get('etfs', 0):,} 筆（含往回 7 天重查）" if ev_n else "")
+               if ev_to else "除權息事件最後成功：尚無執行紀錄")
+    out += [f"⚠️  最後一次收集的警告：{w}" for w in state.get("warnings") or []]
     rev = revenue_status(now.date(), revenue, state.get("revenue_on"), closed) if revenue is not None else None
     if rev:
         out.append(rev[1] if rev[0] != ABNORMAL else f"{rev[1]}，❌ 異常")
```

---

## 附錄 B：比對與 DB 檢查腳本（PG、QA 可存成 `logs/iter24_cmp.py`、`logs/iter24_db.py`；只讀）

- `cmp.py` 用法：`python3 logs/iter24_cmp.py <基線 site/data> <新 site/data>`；全部通過回傳 0，否則印出差異並回傳 1。2026-11-14 用 `orig`、`proj` 的唯讀模擬匯出執行：回傳 0。
- `iter24_db.py` 用法：在專案根目錄 `python3 logs/iter24_db.py base|schema|fill [site/data]`；只執行 SELECT，結束 rollback。2026-11-14 實跑 `base`、`schema`（`etf_events` 尚不存在、3 欄 None），以及 `fill` 的 `insti.n` 段（對 `proj` 的匯出：1,999 檔、493,242 列，不同 0 列）。

### `cmp.py`

```python
"""第 24 輪比對：python3 cmp.py 基線目錄 新目錄（只讀檔案）
1. 檔案清單相同；stocks/ 以外逐位元組相同（latest.json 去掉 updated_at、status 後逐值相同）。
2. stocks/：新的刪掉 dv 與 insti.n 後，和基線逐位元組相同（_write 的格式重新輸出）。
3. insti.n：和 f、t、dl 等長；n ≠ f + t + dl 的列數、最後一天的檔數、差的最大值。
4. dv：每列的 d、p 等於同檔 ev 中同一天事件的 d、p；類型與四類（已填息、尚未填息、不再比較、配股）筆數；k = c 的權 0 列。
5. stocks/ 大小變化（dv、n 分開）。"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path
A, B = Path(sys.argv[1]), Path(sys.argv[2])
fa = {p.relative_to(A) for p in A.rglob("*") if p.is_file()}
fb = {p.relative_to(B) for p in B.rglob("*") if p.is_file()}
assert fa == fb, ("檔案清單不同", sorted(fa ^ fb)[:10])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
other = [f for f in sorted(fa) if f.parts[0] != "stocks" and str(f) != "latest.json" and h(A / f) != h(B / f)]
la, lb = (json.loads((x / "latest.json").read_text(encoding="utf-8")) for x in (A, B))
for x in (la, lb):
    x.pop("updated_at", None); x.pop("status", None)
print("檔案數", len(fa), "；stocks/、latest.json 以外不同：", len(other), [str(f) for f in other[:5]], "；latest.json 相同：", la == lb)
dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
bad, kinds, types, n_rows, n_diff, last_diff, maxd, size, sz_dv, sz_n = [], Counter(), Counter(), 0, 0, 0, 0, [0, 0], 0, 0
for f in sorted(fa):
    if f.parts[0] != "stocks":
        continue
    a, b = (A / f).read_bytes(), (B / f).read_bytes()
    size[0] += len(a); size[1] += len(b)
    o = json.loads(b)
    dv, n = o.pop("dv", "缺"), o["insti"].pop("n", "缺")
    if dump(o).encode() != a or dv == "缺" or n == "缺":
        bad.append(str(f)); continue
    sz_dv += len(dump({"dv": dv})) - 1; sz_n += len(dump({"n": n})) - 1
    I = o["insti"]
    if len(n) != len(I["f"]):
        bad.append((str(f), "n 長度"))
    for i, x in enumerate(n):
        if I["f"][i] is None or x is None:
            continue
        n_rows += 1
        s = I["f"][i] + (I["t"][i] or 0) + (I["dl"][i] or 0)
        if s != x:
            n_diff += 1; maxd = max(maxd, abs(s - x))
            last_diff += i == len(n) - 1 and o["prices"]["d"][-1] == lb["date"]
    ev = {e["d"]: e for e in o["ev"]}
    for r in dv:
        e = ev.get(r["d"])
        if not e or (e["t"], e["p"]) != (r["t"], r["p"]) or (e.get("k") == "c" and e["t"] == "權"):
            bad.append((o["code"], r["d"], "dv 和 ev 不一致"))
        types[r["t"]] += 1
        kinds["配股" if r["t"] == "權" else "已填息" if "f" in r else "不再比較" if "x" in r else "尚未填息"] += 1
print("stocks/ 刪掉 dv、insti.n 後不同或 dv 和 ev 不一致：", len(bad), bad[:5])
print("dv 類型", dict(types), "合計", sum(types.values()), "；四類", dict(kinds))
print(f"insti.n：比較 {n_rows} 列，n ≠ f+t+dl {n_diff} 列（{n_diff / max(n_rows, 1):.1%}），最大差 {maxd} 張；資料日 {lb['date']} {last_diff} 檔")
print("stocks/ 大小", size[0], "→", size[1], f"（+{(size[1] - size[0]) / 1024:.1f} KB；dv 約 {sz_dv / 1024:.1f} KB、insti.n 約 {sz_n / 1024:.1f} KB）")
sys.exit(0 if not other and la == lb and not bad else 1)
```

### `iter24_db.py`

```python
"""第 24 輪 DB 檢查（只執行 SELECT，結束 rollback；PG、QA 可存成 logs/iter24_db.py，在專案根目錄執行）
python3 logs/iter24_db.py base                 套用前：記下 2026-11-13 以前事件的筆數與 checksum
python3 logs/iter24_db.py schema               setup-db 後：etf_events、3 個新欄位存在
python3 logs/iter24_db.py fill [site/data]     回補、export 後：F24-5 驗收 #3～#8 與 insti.n 對資料庫"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from twstock import db  # noqa: E402

mode = sys.argv[1]
conn = db.connect()
cur = conn.cursor()
one = lambda sql, *p: cur.execute(sql, *p).fetchone()
OLD = """SELECT COUNT(*), CHECKSUM_AGG(BINARY_CHECKSUM(stock_id, event_date, source, event_type, prev_close, ref_price, div_ref))
         FROM price_events WHERE event_date <= '2026-11-13'"""
try:
    if mode == "base":
        print("price_events（≤ 2026-11-13）筆數、checksum：", tuple(one(OLD)))
    elif mode == "schema":
        print("etf_events 存在：", one("SELECT OBJECT_ID('etf_events')")[0] is not None)
        print("新欄位：", [(c, one(f"SELECT COL_LENGTH('price_events', '{c}')")[0]) for c in ("div_total", "div_cash", "stock_div")])
        print("price_events（≤ 2026-11-13）筆數、checksum（要和 base 相同）：", tuple(one(OLD)))
    elif mode == "fill":
        print("price_events（≤ 2026-11-13）筆數、checksum（要和 base 相同）：", tuple(one(OLD)))
        for r in cur.execute("""SELECT source, COUNT(*), COUNT(div_total), COUNT(div_cash), COUNT(stock_div),
                   SUM(CASE WHEN event_type = N'息' AND div_cash = div_total THEN 1 ELSE 0 END),
                   SUM(CASE WHEN event_type = N'息' THEN 1 ELSE 0 END)
                   FROM price_events WHERE event_date <= '2026-11-14' GROUP BY source ORDER BY source""").fetchall():
            print(f"  {r[0]}：{r[1]} 筆，div_total {r[2]}、div_cash {r[3]}、stock_div {r[4]}；息 {r[6]} 筆中 div_cash = div_total {r[5]}")
        print("上市權／權息有 div_cash（要 0）：", one("""SELECT COUNT(*) FROM price_events WHERE source = 'TWT49U'
              AND event_type IN (N'權', N'權息') AND div_cash IS NOT NULL""")[0])
        print("TWTAUU、TWTB8U 有金額（要 0）：", one("""SELECT COUNT(*) FROM price_events WHERE source IN ('TWTAUU', 'TWTB8U')
              AND (div_total IS NOT NULL OR div_cash IS NOT NULL OR stock_div IS NOT NULL)""")[0])
        print("etf_events（≤ 2026-11-14）：", [tuple(r) for r in cur.execute("""SELECT source, COUNT(*), COUNT(DISTINCT etf_id), COUNT(div_cash),
              SUM(CASE WHEN event_type = N'息' THEN 1 ELSE 0 END) FROM etf_events WHERE event_date <= '2026-11-14'
              GROUP BY source ORDER BY source""").fetchall()], "（來源、筆數、檔數、有金額、息）")
        print("etf_events 的代號在 stocks 表（要 0）：", one("""SELECT COUNT(*) FROM etf_events e JOIN etfs et ON et.etf_id = e.etf_id
              JOIN stocks s ON s.stock_code = et.etf_code""")[0])
        print("etf_events 市場別不符（要 0）：", one("""SELECT COUNT(*) FROM etf_events e JOIN etfs et ON et.etf_id = e.etf_id
              WHERE NOT ((e.source = 'TWT49U' AND et.market_type = 'TWSE') OR (e.source = 'TPEX_EX' AND et.market_type = 'TPEx'))""")[0])
        print("2421、2330、6488、5511、6703 的金額：", [tuple(str(x) for x in r) for r in cur.execute("""SELECT s.stock_code, e.event_date, e.event_type,
              e.div_total, e.div_cash, e.stock_div FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
              WHERE s.stock_code IN ('2421', '2330', '6488', '5511', '6703') AND e.source IN ('TWT49U', 'TPEX_EX') ORDER BY 1, 2""").fetchall()])
        site = Path(sys.argv[2] if len(sys.argv) > 2 else "site/data")
        db_n = {}
        for code, d, t in cur.execute("""SELECT s.stock_code, d.trade_date, i.total_net FROM daily_prices d JOIN stocks s ON s.stock_id = d.stock_id
                LEFT JOIN institutional_trades i ON i.stock_id = d.stock_id AND i.trade_date = d.trade_date"""):
            db_n[(code, str(d))] = None if t is None else round(t / 1000)
        rows = diff = files = 0
        for f in sorted((site / "stocks").glob("*.json")):
            o = json.loads(f.read_text(encoding="utf-8"))
            if "insti" not in o:
                continue
            files += 1
            for d, n in zip(o["prices"]["d"], o["insti"]["n"]):
                rows += 1
                diff += db_n.get((o["code"], d), "缺") != n
        print(f"insti.n 對資料庫 round(total_net / 1000)：{files} 檔、{rows} 列，不同 {diff} 列（要 0）")
finally:
    conn.rollback()
    conn.close()
```
