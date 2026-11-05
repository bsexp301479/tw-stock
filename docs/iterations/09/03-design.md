# 第 09 輪｜System Analyst：設計規格

- 撰寫日期：2026-11-05
- 輸入：`09/01-analyst.md`、`09/02-pm.md`（含 2026-11-05 範圍變更：QA-05 併入 F9-1）、`08/03-design.md`（格式與第 8 輪換算規則）、`03/05-qa.md`（QA-05）。
- 依據：現行程式 `twstock/`（`db.py`、`health.py`、`export.py`、`__main__.py`、`collectors/daily.py`、`revenue.py`、`catchup.py`、`history.py`、`fetch.py`）、`site/app.js`、`site/stock.js`、`tests/test_iter02/03/08.py`、`logs/iter08_compare.py`、README。
- 原型驗證（全部在 scratchpad，不寫專案資料庫、不改專案程式）：
  - 把 `twstock/`、`site/`、`tests/` 複製成 `orig/`（基線）與 `proj/`（原型），在 `proj/` 實作本文全部修改。差異見附錄 C～E。
  - `test_iter01～09` 在原型上全部通過；`test_iter09.py` 拿去跑舊程式，除了「只有標題列的 CSV」一項（現行行為本來就正確）以外全部失敗（反證成立）。
  - 匯出：以真實資料庫**唯讀**連線執行原型的 `export_all`（寫到 scratchpad），另以 `--sim` 改寫 SQL 模擬「已加 `market` 欄、上櫃只有 11/05 一天」。隔離比對（附錄 G `iter09_compare.py`）判定「✅ 相同」；SQL 獨立重算（附錄 H `iter09_recalc.py`）判定「✅ 相同」。
  - 前端：原型匯出 + 原型 `site/` 以 8001 埠預覽，375 px 檢查今日頁、個股頁、選股頁、持股頁。
  - **DDL 沒有在任何資料庫上執行過**（不可寫入專案資料庫，也沒有另一個 SQL Server），交給 PG 依第三節步驟 4 驗證。
- 實測發現：
  1. 上櫃 `insti/summary` 回應的單位名稱前面有全形空白（`"　外資及陸資(不含自營商)"`），合計列帶 `*`（`"三大法人合計*"`）；`notes` 寫明外資自營商不納入三大法人合計，和上市「合計」口徑相同。
  2. 還沒有公司公布的月份，mopsov `t21sc03_115_11.csv` 回 **200、344 B、只有標題列**，不是 404。現行 `fetch_monthly_revenue` 回傳 `{}`、`execute_plan` 照常記 `revenue_on`，不需要改（測試 `test_f92_header_only_csv`）。
  3. 「月初起收營收」實際上是從**當月第一個交易日**開始，不是 1 日：`make_plan` 依評估範圍內的交易日決定要收哪個月份；11/01 是週日，範圍內全是 10 月的交易日，月份是 9 月（已齊）。見第五節 #1。
  4. 一年窗口 = 最近 242 個有官方本益比資料的交易日；11/05 時為 2025-11-05～2026-11-05，和日曆一年剛好一致。PM 的 11/04、11/05 數字全部重算吻合（附錄 A）。
  5. 匯出耗時 16.7 秒 → 18.9～19.3 秒（+2.5 秒，其中讀約 47 萬列 `stock_fundamentals` 1.7 秒）。
  6. 現行上市 `amount` 鍵**沒有**「同市場行情還沒有就不發請求」的保護（`partition` 後 market 是空字串）。本輪只對上櫃加保護，上市維持原狀（第五節 #2）。

---

## 〇、變更總覽

| 檔案 | F9-1 上櫃法人金額 | QA-05 | F9-2 月營收 | F9-3 小修 | F9-4 估值位置 | 原型行數（+/−） |
|---|---|---|---|---|---|---|
| `twstock/db.py` | `insti_amount` 加 `market`、改唯一鍵、3 條遷移 DDL | | | | | +12 / −2 |
| `twstock/collectors/daily.py` | 鍵 `amount.TPEx`、解析、抓取、MERGE 加 market、行情保護 | | | | | +48 / −10 |
| `twstock/collectors/history.py` | 間隔 `amount.TPEx: 3.2` | | | | | +1 / −1 |
| `twstock/collectors/revenue.py` | | | `revenue_month_for` 一律回上個月 | | | +1 / −3 |
| `twstock/collectors/catchup.py` | | | `REVENUE_DONE_RATIO` 改由 health import | | | +1 / −2 |
| `twstock/health.py` | `Spec amount.TPEx`、`load_snapshot` 分市場 | | `revenue_status`、`revenue_counts`、`check_report(revenue=)` | | | +42 / −6 |
| `twstock/export.py` | `amount_by_market`、`insti_official_tpex` | | | `stock_margin(conv)` | `position`、`market_valuation`、`stock_valuation`、`_load_valuation`、`valuation`、`val`、`pbp` | +104 / −11 |
| `twstock/__main__.py` | 說明文字 | `main()` 攔截 `pyodbc.Error` | | | | +8 / −3 |
| `site/app.js` | `instiCard` 上櫃官方一行 | | `revMixed`、頁尾說明 | 「重設」、持股頁日期 | `valCard`、選股 `pbp` | +40 |
| `site/stock.js` | | | | | 三張指標卡的位置、說明 | +9 |
| `tests/test_iter03.py` | fixture 補 `amount.TPEx`、`insti/summary` | | | | | +12 / −3 |
| `tests/test_iter09.py`（新） | ✓ | ✓ | ✓ | ✓ | ✓ | 309 行 |
| `logs/iter09_compare.py`、`logs/iter09_recalc.py`（新） | ✓ | | ✓（營收家數） | ✓ | ✓ | 75、115 行 |
| README | ✓ | ✓ | ✓ | ✓ | ✓ | 見第九節 |

### 建議實作順序（PM 指定：`backup → 改查詢 → 改表 → 補抓 → 匯出`，細節見第三節）

| 步驟 | 內容 | 驗證 | 失敗時 |
|---|---|---|---|
| 0 | `backup` | 記錄指令、時間、檔名、大小 | 停，不改任何程式 |
| 1 | 舊程式 `export` 產生基線、存 `insti_amount` 快照 | 檔案存在、390 列 | 停 |
| 2 | 改查詢與收集器、測試（不碰資料庫） | `test_iter01～09` 全過 | 修到過為止，不往下 |
| 3 | `setup-db` 兩次（改表） | 第 2 節 SQL 檢查 | 停，交使用者決定是否從備份還原 |
| 4 | `history --start 2026-07-31 --only amount`（補上櫃） | 計畫 amount 0 天、amount.TPEx 約 65 天；SQL 每日 6 列 | 停，保留紀錄 |
| 5 | `export` → `iter09_compare` → `iter09_recalc` | 兩者皆「✅ 相同」 | 停，不更新網站 |
| 6 | F9-2～F9-4 其餘、前端、README、`__main__.py`，8001 埠預覽 | 測試、375 px、主控台 | 修到過為止 |

> F9-2～F9-4 的後端程式可以在步驟 2 一起改（原型就是一起改的，隔離比對已涵蓋），但 F9-4 的 `export` 驗證放在步驟 5 之後；若 PG 想分開驗證，先只做 F9-1 跑完步驟 5，再加其餘再跑一次 compare。

---

## 一、F9-1 上櫃官方三大法人金額

### 1-1 資料來源與欄位對應

- 端點：`POST https://www.tpex.org.tw/www/zh-tw/insti/summary`，form `date=YYYY/MM/DD`、`response=json`，經 `fetch.request`（`TPEX` 常數已有前綴）。
- 回應（11/05 實測，`stat` 小寫 `"ok"`、`date` = `"20261105"`）：`tables[0].fields = ["單位名稱","買進金額(元)","賣出金額(元)","買賣超(元)"]`，8 列，單位為**元**（與上市 BFI82U 相同）。

| 上櫃單位名稱（原文） | 處理後名稱（`.strip().rstrip("*")`） | `unit` | 上市 BFI82U 對應 |
|---|---|---|---|
| 外資及陸資合計 | 外資及陸資合計 | **不存**（= foreign + foreign_dealer） | — |
| 　外資及陸資(不含自營商) | 外資及陸資(不含自營商) | `foreign` | 外資及陸資(不含外資自營商) |
| 　外資自營商 | 外資自營商 | `foreign_dealer` | 外資自營商 |
| 投信 | 投信 | `trust` | 投信 |
| 自營商合計 | 自營商合計 | **不存**（= dealer_self + dealer_hedge） | — |
| 　自營商(自行買賣) | 自營商(自行買賣) | `dealer_self` | 自營商(自行買賣) |
| 　自營商(避險) | 自營商(避險) | `dealer_hedge` | 自營商(避險) |
| 三大法人合計* | 三大法人合計 | `total` | 合計 |

- 比對方式：**完全比對**字典 `TPEX_AMOUNT_UNIT`（不共用上市 `_amount_unit` 的子字串判斷，因為上櫃有「外資及陸資合計」「自營商合計」，子字串判斷會誤收）。
- 回傳空（不寫入）的條件：`stat` 不是 `ok`（大小寫不拘）、回應 `date` 存在且 ≠ 查詢日、找不到含 4 個必要欄位的表、6 個單位不齊（例如休市回應只有空表）。
- 「外資」顯示值 = `foreign`（不含外資自營商，外資自營商已計入自營商合計）；「自營」= `dealer_self + dealer_hedge`；與上市 `_insti_official` 同一套函式。

### 1-2 資料表變更（方案 (a)：加 `market` 欄）

`db.py` 的 `CREATE TABLE insti_amount`（新資料庫直接建出新結構）：

```sql
IF OBJECT_ID('insti_amount') IS NULL
CREATE TABLE insti_amount (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    trade_date  DATE          NOT NULL,
    market      NVARCHAR(10)  NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE'
                              CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx')),
    unit        NVARCHAR(20)  NOT NULL,
    buy_amount  BIGINT NULL, sell_amount BIGINT NULL, net_amount BIGINT NULL,
    created_at  DATETIME NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)
)
```

緊接在它後面的 3 條遷移（既有資料庫；每條都先判斷，可重複執行；`DDL` 清單逐條執行，順序不可對調）：

```sql
-- ① 加欄位：既有 390 列由 DEFAULT 填 'TWSE'（ADD … NOT NULL DEFAULT 會回填既有列）
IF COL_LENGTH('insti_amount', 'market') IS NULL
ALTER TABLE insti_amount ADD market NVARCHAR(10) NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE'
CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx'))
-- ② 刪舊唯一鍵
IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount' AND parent_object_id = OBJECT_ID('insti_amount'))
ALTER TABLE insti_amount DROP CONSTRAINT UQ_insti_amount
-- ③ 建新唯一鍵
IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount_market' AND parent_object_id = OBJECT_ID('insti_amount'))
ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)
```

- 重複執行：第二次 ① 的 `COL_LENGTH` 不是 NULL、② 找不到舊鍵、③ 已有新鍵 → 三條都不動作。空資料庫：`CREATE TABLE` 已含新結構，①～③ 都不動作。
- 交易：`setup_database` 逐條 `execute`、最後才 `commit`，任何一條失敗整批回滾（含其他表的 `CREATE`），資料庫維持改表前。
- **PG 必須驗證的風險點**（原型無法驗證）：
  1. SQL Server 對「同一批次中參照剛 `ADD` 的欄位」會在編譯期報錯；本設計 ③ 是獨立的 `execute`，不是同一批次，應無問題。若 PG 實測 ③ 仍報「無效的資料行名稱 market」，把 ③ 改成 `EXEC('ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)')`，並在 `04-dev.md` 記錄。
  2. 舊唯一鍵名稱必須是 `UQ_insti_amount`（現行 DDL 的名稱）；步驟 1 先用 SQL 確認（第三節）。
- 回滾：不寫反向 DDL。改表後若要回到舊結構，由**使用者**從步驟 0 的備份（`../_backups/`）還原；PG、QA 不自行還原。改表後**不可再執行舊版程式**（舊 MERGE 沒有 market，`ON` 只比 `trade_date, unit`，會把上櫃列當成上市列更新）。

### 1-3 所有讀寫 `insti_amount` 的地方

| 位置 | 現行 | 改後 |
|---|---|---|
| `daily.merge_insti_amount` | `ON trade_date, unit` | OPENJSON 加 `market NVARCHAR(10)`；`ON … AND t.market = s.market`；INSERT 加 market |
| `daily.parse_insti_amount`（上市） | 列無 market | 每列加 `"market": "TWSE"` |
| `health.load_snapshot` | 不分市場計數 | `amount`：`WHERE market = 'TWSE'`；新增 `amount.TPEx`：`WHERE market = 'TPEx'` |
| `export.export_all`（原第 769 行） | `SELECT trade_date, unit, net_amount` | `SELECT trade_date, market, unit, net_amount` → `amount_by_market` |
| `db.py` 第 477 行 | 說明字串列出表名 | 不改 |
| `logs/counts.py`、`iter04/05_counts.py` | `COUNT(*)` 全表 | 不改（舊工具；改表後總數會含上櫃列，屬預期） |

### 1-4 資料集鍵與收集器

- 鍵名：**保留 `amount` = 上市**，新增 **`amount.TPEx` = 上櫃**。
  - 理由：`collect_runs.detail` 舊紀錄的 `amount` 仍代表上市，不需轉換；`history --only amount` 對應 `DATASET_KEYS[AMOUNT] = ("amount", "amount.TPEx")`，**不新增 `--only` 選項**；已有的市場由 `missing_keys` 自動略過，所以補抓上櫃時上市 0 次請求。
  - 不改成 `amount.TWSE` 的理由：會讓舊 `detail` 與 `check` 的 key 對不上、需要轉換程式，沒有收益。
- `DAY_KEYS`：`"amount"` 後面加 `"amount.TPEx"`（在 `insti.TPEx` 之後、`margin` 之前）。
- `_collect_key`：最後一段改成 `(fetch_tpex_insti_amount if market == "TPEx" else fetch_twse_insti_amount)(d)`。
- `collect_for_date` 行情保護：`dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT)`。`amount.TPEx` 的 market = `TPEx`，上櫃行情寫入 0 列時不發請求；上市 `amount` 的 market 是空字串，`written.get("prices.")` 永遠是 None，**行為不變**。
- `history.SECONDS_PER_KEY` 加 `"amount.TPEx": 3.2`（櫃買節流與其他 TPEx 鍵相同）。

### 1-5 `check`

- `health.AMOUNT_TPEX_FROM = date(2026, 7, 31)`；`SPECS` 在上市法人金額後面加 `Spec("amount.TPEx", "上櫃法人金額", 6, False, AMOUNT_TPEX_FROM)`。
- 上市一列只計 `market = 'TWSE'`，筆數仍 6、中位數不變。
- 範例（mock 缺 11/04）：表格「上櫃法人金額 19/20 ❌」，問題行「❌ 上櫃法人金額：缺 2026-11-04」，建議指令沿用 `suggest`（`history --start 2026-11-04` + `collect --catch-up`）。2026-07-31 以前不判缺（`since`）。

### 1-6 匯出（`latest.json`）

| 鍵 | 內容 | 說明 |
|---|---|---|
| `insti_official` | **不變**（結構、值） | 改為 `_insti_official(amount["TWSE"])`，只取上市 |
| `insti_official_tpex`（新） | 結構同 `insti_official`：`date, foreign, trust, dealer, total`（億，1 位）、`d`、`f`、`t`（20 日）、`fs` | 上櫃沒有任何「合計」列時為 `null` |
| `insti_otc` | 保留（估算） | 前端只在 `insti_official_tpex` 為 null 時使用 |
| `status.datasets` | 多一項 `k = "amount.TPEx"` | 由 SPECS 自動產生 |

- 大小：上櫃 1 天約 +0.4 KB；補滿 20 天約 +1.0 KB（與 `insti_official` 相當）。
- 11/05 預期值（`amount_by_market` → `_insti_official`）：上市外資 −1,024.6、投信 +225.9、自營 −435.3、合計 −1,233.9 億；上櫃外資 −15.8、投信 −11.0、自營 −11.7、合計 −38.5 億。

### 1-7 畫面（今日頁 `instiCard`）

- 標題與大字仍是**上市**合計（「三大法人　上市，官方，含 ETF　11/05」）。
- 上市一行（外資／投信／自營）+ 上市外資 20 日迷你圖 + 連買連賣（不變）。
- 新增上櫃一行：`上櫃（官方，11/05）合計 −38.5億　外資 −15.8億　投信 −11.0億　自營 −11.7億`；上櫃日期早於網站資料日 → `（官方，11/04，尚未更新）`。
- 上櫃外資 20 日迷你圖與連買連賣一行（PM 延後順序第 3；原型已做，+3 行，建議保留；若時間不足可刪除該兩行，不影響其他）。
- 上櫃官方 `null`（從未有資料）→ 退回估算一行，文字「上櫃官方金額尚無資料，暫以張數 × 收盤估算、不含 ETF，不可與上市官方值相加」。
- **只要 `insti_official_tpex` 不是 null，就不顯示上櫃估算數字**（即使晚一天，也顯示官方 + 尚未更新）。
- 不加「上市＋上櫃」合計大字（第五節 #5）。卡片底部統一一句口徑：「官方金額含 ETF 與權證避險，外資不含外資自營商（已計入自營）；上市、上櫃同一天時可相加。下方法人買超／賣超表為張數 × 收盤估算、不含 ETF，口徑不同」。
- 上市也沒有官方資料時（`insti_official` null）維持第 1 輪估算卡（不變）。

### 1-8 請求量

- 每日：+1 次（上櫃行情有資料後）。
- 補抓：2026-07-31～11/05 約 65 個交易日 × 1 次，間隔 3.2 秒 → 約 3.5 分鐘。

---

## 二、QA-05：`main()` 攔截資料庫錯誤

```python
    args = p.parse_args(argv)
    import pyodbc
    try:
        return args.fn(args) or 0
    except pyodbc.Error as e:        # QA-05：history、export 等連不上資料庫時不印 Traceback（collect、check、backup 各自已處理）
        print(f"❌ 連不上資料庫或資料表不存在（請確認 Docker 與容器已啟動，並執行過 setup-db）：{str(e).splitlines()[0][:200]}")
        return 2
```

- 只攔 `pyodbc.Error`（含 `OperationalError`、`ProgrammingError`「資料表不存在」）；其他例外照常顯示 Traceback（程式錯誤要看得到）。
- 回傳碼 2（與 1「check 有異常」區分）。
- `str(e)` 是 pyodbc 的 tuple repr，可能很長，取第一行前 200 字。
- 已自行處理的指令（`collect` 的 DB 重試、`check`、`backup`）不受影響，因為它們不會把 `pyodbc.Error` 拋到 `main`。

---

## 三、PG 實作與資料操作步驟（含驗證與停止條件）

> 所有 SQL 都是唯讀查詢，除了步驟 3 的 `setup-db` 與步驟 4 的 `history`。每一步的輸出貼進 `04-dev.md`。

**步驟 0：備份**
- `python3 -m twstock backup`；記錄指令、開始時間、`../_backups/` 的檔名與大小。
- 必須早於任何程式修改。失敗 → 停，回報使用者。

**步驟 1：基線**
- 舊程式 `python3 -m twstock export`，記錄耗時（第 8 輪 16.6 秒、SA 實測 16.7 秒）；把 `site/data/` 複製到 `logs/iter09_before/`。
- 快照與檢查：
  ```sql
  SELECT name FROM sys.key_constraints WHERE parent_object_id = OBJECT_ID('insti_amount');   -- 應為 UQ_insti_amount 與 PK
  SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM insti_amount;                          -- 390、2026-07-31、最新日
  SELECT trade_date, unit, buy_amount, sell_amount, net_amount FROM insti_amount ORDER BY trade_date, unit;  -- 存成 logs/iter09_amount_before.csv
  ```
- 舊鍵名不是 `UQ_insti_amount` → 停，回報 SA（遷移 ② 會找不到，③ 會因重複鍵失敗）。

**步驟 2：改查詢、收集器、測試（不連資料庫）**
- 依附錄 C 改 `db.py` 以外的全部後端檔案、`tests/test_iter03.py`（附錄 E）、新增 `tests/test_iter09.py`（附錄 F）。`db.py` 的 DDL 也可在此步改好，但**不執行 `setup-db`**。
- 驗證：`for f in tests/test_iter0*.py; do python3 $f; done` 全過。
- **此步到步驟 3 之間不可執行 `export`、`check`、`collect`**（新程式的 `WHERE market = …` 在舊表上會報錯；`collect` 會用新 MERGE 寫舊表而失敗）。

**步驟 3：改表**
- `python3 -m twstock setup-db` 執行**兩次**，兩次都不報錯。
- 驗證 SQL：
  ```sql
  SELECT name, is_nullable FROM sys.columns WHERE object_id = OBJECT_ID('insti_amount') AND name = 'market';      -- 1 列、0
  SELECT name FROM sys.key_constraints WHERE parent_object_id = OBJECT_ID('insti_amount') AND type = 'UQ';          -- 只有 UQ_insti_amount_market
  SELECT market, COUNT(*) FROM insti_amount GROUP BY market;                                                         -- TWSE 390（只有一列）
  ```
  再匯出 `trade_date, unit, buy_amount, sell_amount, net_amount`（`WHERE market='TWSE'`）與步驟 1 的 CSV 用 `diff` 比對，必須完全相同。
- 任何一項不符 → **停**，不執行步驟 4；回報使用者，由使用者決定是否從備份還原。

**步驟 4：補抓上櫃**
- `python3 -m twstock history --start 2026-07-31 --only amount`。
- 先看印出的計畫：`amount` 0 天、`amount.TPEx` 約 65 天、預估約 3.5 分鐘。若 `amount` 不是 0 天 → 中斷（Ctrl+C），回報 SA。
- 驗證 SQL：
  ```sql
  SELECT market, COUNT(DISTINCT trade_date), COUNT(*) FROM insti_amount GROUP BY market;   -- TPEx 天數 = TWSE 天數、列數 = 天數 × 6
  SELECT trade_date FROM insti_amount WHERE market='TWSE' GROUP BY trade_date
  EXCEPT SELECT trade_date FROM insti_amount WHERE market='TPEx' GROUP BY trade_date;       -- 0 列（反向也 0 列）
  SELECT unit, buy_amount, sell_amount, net_amount FROM insti_amount WHERE market='TPEx' AND trade_date='2026-11-05';  -- 附錄 A-1
  ```
- 記錄請求次數與耗時。fetch 錯誤（主機 dead）→ 停，回報；不要重試超過一次。

**步驟 5：匯出與比對**
- `python3 -m twstock export`，記錄耗時（預期 +2.5 秒左右，上限 +5 秒）。
- `python3 logs/iter09_compare.py logs/iter09_before site/data` → 「✅ 相同」；`--keep-new` → 判定不同（反證）。
- `python3 logs/iter09_recalc.py` → 「✅ 相同」。
- `python3 -m twstock check` → 「上櫃法人金額」全部正常、上市「法人金額」6 列、營收一行出現（⏳ 或 ✅）。
- 任一不符 → 停，不更新網站，回報。

**步驟 6：前端與文件**
- 依附錄 D 改 `app.js`、`stock.js`；README、`__main__.py` 依第九節。
- 8001 埠預覽（不用 8000）：375 px 今日頁、`#/stock/2603`、`#/stock/5314`、`#/rank/screen`、`#/etf/00997A`、`#/etf/00982A`；主控台無錯誤。

---

## 四、F9-2 月營收提前收集（B15）

### 4-1 收集邏輯

- `revenue_month_for(d)` 一律回傳 d 的上一個月（1 月 → 前一年 12 月）。三條路徑都經過它：
  - `catchup.make_plan`：評估範圍內每個交易日各算一個月份，**每個月份分別判斷**；已有 `revenue_on == 今天` 不排；該月家數 ≥ 前一月 × 98% 不排。
  - `catchup.plan_for_date`（`collect --date`）：`collect --date 2026-11-02` 收 10 月（測試已涵蓋）。
  - `history`：`--no-revenue` 以外，依 `revenue_month_for` 收月份；`history` 本來就只補沒有的公司，月初執行只會多收已公布的公司，無副作用。
- `fetch_monthly_revenue`、`collect_monthly_revenue` 不改：OpenAPI 月份不符 → mopsov；只有標題列 → `{}` → 寫入 0 家 → `revenue_on` 照記當天（`execute_plan` 的現行行為，`test_f92_header_only_csv` 鎖住）。
- 時序（11 月為例）：
  - 11/01（週日）：評估範圍都是 10 月交易日 → 月份 9 月（已齊）→ 0 次。
  - 11/02 起每天第一次成功 catch-up：10 月未達 1,940 家（1,980 × 98%）→ 兩市場各 OpenAPI 1 + mopsov 1 = **4 次**；`revenue_on` = 當天後同日不再排。
  - 約 11/11～12 達 98% → 之後到月底 0 次。
  - 12/01 起自動切到 11 月。
  - 跨月 catch-up（範圍含 10/30 與 11/02）：9 月已齊不重抓，只排 10 月；若 9 月沒齊，兩個月份都排（測試涵蓋）。
- 同一天只抓一次（PM 接受）；不新增「當天最後一次排程再抓」。
- 更正值不覆寫（不變）。

### 4-2 請求量

| 情境 | 次數 |
|---|---|
| 未達 98% 的日子 | 每天 4 次（只在當天第一次成功 catch-up） |
| 一個月 | mock 模擬（每天都執行、含週末）：11/02～11/11 共 10 天 × 4 = **40 次**；舊規則（10 日以後才收）約 3～5 天 × 4 = 12～20 次 |
| 已達 98% 後 | 0 次 |

### 4-3 `check` 的營收一行

- 輸入：`check_report(..., revenue=None)` 新增參數 = `{(年, 月): 家數}`（`health.revenue_counts(cur)`，SQL 同 `catchup._revenue_counts`）；`revenue_on` 取自 `state`。`check_report` 仍是純函式；`revenue=None` 時不印（舊呼叫方式不變）。
- 常數移到 `health`：`REVENUE_DONE_RATIO = 0.98`（`catchup` 改為 import）、`REVENUE_DUE_DAY = 10`。
- 月份 = 今天的上一個月（與 `revenue_month_for` 相同）；前一月 = 再上一個月。

| 狀態 | 條件 | 文字 |
|---|---|---|
| ✅ | 該月家數 > 0 且 ≥ 前一月 × 98% | `月營收 2026/10：已收 1,945 家（前一月 1,980 家的 98%），✅ 已齊` |
| ⏳ | 未達，今天 ≤ 10 日 | `月營收 2026/10：已收 287 家（前一月 1,980 家的 14%），⏳ 公布期間（每月 10 日前）` |
| ⏳ | 未達，已過 10 日，`revenue_on` ≥ 前一個交易日 | `…，⏳ 晚交公司陸續補進（最後收集 11/12）` |
| ❌ | 其餘 | 行：`…，最後一次收集營收 2026-11-09，❌ 異常`；問題行：`❌ 月營收 2026/10：…：已過 10 日仍未收齊，收集可能停了`；計入「異常 N 項」、rc = 1；建議指令印出 `python3 -m twstock collect --catch-up`（`suggest(..., stale=True)` 分支） |

- 前一月家數 0（資料庫沒有）時括號省略。位置：「處置／注意股最後成功」那一行之後。
- 「前一個交易日」以 `trading_days(today − 30, today − 1, closed)[-1]` 計算（週一 → 上週五）。

### 4-4 網站

- 選股資料日一行：`revMixed(S)` = `rmd` 有兩個以上月份，且最多的月份 < 總數 × 98% → 在營收檔數後加「（每月 1～10 日為公布期間，各股月份不同）」。只有一個月份（現在的 `screen.json`）不顯示。
- 月份小字：第 8 輪已完成（`SCR_COLS.ry` 在 `rm ≠ revMonth()` 時加「（10月）」；C1 營收年增排行經 `RANK_COLS.ry` 共用同一格式），本輪不改。
- 頁尾說明改為：「營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。」
- 個股頁月營收卡逐月顯示，不需修改（已確認）。
- 匯出：不變（`rmd`、`rm` 第 8 輪已有）。

---

## 五、F9-3 第 8 輪收尾小修（P23）

1. **選股「清除」→「重設」**：按鈕文字改「重設」；`st = { ...SCREEN_DEFAULT }`（`SCREEN_DEFAULT` 第 854 行 = `xd=1&xn=1&xc=1&o=tv`，和首次進入相同）。實測 11/05 重設後 1,961 檔、hash 回到 `xd=1&xn=1&xc=1&o=tv`、5314 不在結果中。README 沒有「清除」字樣，不需改。
2. **持股頁日期**：`${S.d === App.latest.date ? '今天' : md(S.d) + ' '}單位數 1 日 ${sgn(S.u1)}%`。11/05：00997A「11/04 單位數 1 日 -0.48%」、00982A「今天單位數 1 日 +0.61%」。
3. **個股 `margin.m5` 換算**：`stock_margin(rows, mdate, d5, conv=())` 的 m5 = `round(mb − old[1] × conv_k(conv, d5))`；`screen_margin` 改為直接用 `r["m5"]`（共用一套，不另寫）。`export_all` 呼叫時傳入該股的 `conv`（與 screen 相同變數）。`conv` 空 → `conv_k = 1.0` → 與現行相同（`round` 對整數不變）。11/05 全部 0 檔不同（compare 檢查 m5 只在 5 日內有換算時允許不同）。

---

## 六、F9-4 市場與個股估值的一年位置（A10＋B7）

### 6-1 定義表

| 項目 | 定義 |
|---|---|
| 窗口 | 最近 `VAL_DAYS = 242` 個 `stock_fundamentals` 有資料的交易日（`SELECT DISTINCT TOP 242 trade_date … DESC`）；11/05 = 2025-11-05～2026-11-05 |
| 市場中位數 | 每天、分市場（`stocks.market_type`）：本益比、淨值比只計入 > 0；殖利率計入非 null（含 0）；`statistics.median` |
| 市場計入檔數 `n` | 窗口最後一天本益比 > 0 的檔數 |
| 位置 | 窗口內（序列含今天）數值 ≤ 今天數值的天數 ÷ 天數 × 100；市場取 1 位小數、個股取整數 |
| 區間 | 窗口內最小值～最大值（2 位小數） |
| 一年最低／最高 | 今天值 ≤ lo 顯示「一年最低」、≥ hi 顯示「一年最高」（取代百分比，避免「0.4%」讓人誤以為還有更低） |
| 個股序列 | 窗口內該欄 > 0 的值（殖利率也只計 > 0，與市場不同：個股殖利率 0 = 不配息，位置沒有意義） |
| 個股不輸出 | 今天值 null 或 ≤ 0（虧損、無股利）；有效天數 < `VAL_MIN = 120`；`cap = 1`（90 天內股本變動）整個 `val` 不輸出（二選一定案「不顯示」） |
| 市場是否排除 cap | **不排除**（影響很小、口徑單純） |
| 全部相同值 | 位置 100%（依定義），lo = hi，顯示「一年最低」（≤ lo 先判斷），不報錯 |
| 計算位置 | Python（`_load_valuation` 讀窗口內約 47 萬列，1.7 秒）；不用 SQL 視窗函數（需要每天、每檔的完整序列計位置，Python 較簡單） |

### 6-2 匯出欄位與大小

`latest.json` 新增 `valuation`（無資料 → `null`）：

```json
"valuation": {
  "TWSE": {"d": "2026-11-05", "from": "2025-11-05", "days": 242, "n": 877,
           "pe": {"v": 15.75, "p": 0.4, "lo": 15.75, "hi": 21.76},
           "pb": {"v": 1.53, "p": 0.4, "lo": …, "hi": …},
           "dy": {"v": 2.77, "p": 56.6, "lo": …, "hi": …},
           "s": [60 天本益比中位數], "sf": "2026-08-10"},
  "TPEx": {…}
}
```

`stocks/{代號}.json` 新增 `val`（不輸出規則見 6-1）：

```json
"val": {"d": "2026-11-05", "pe": [16, 22.47, 34.87], "pb": [30, lo, hi], "dy": [59, lo, hi]}
```

`screen.json` 每檔新增 `pbp`（淨值比位置整數或 null；**cap = 1 也輸出**，由前端 `valGuard` 依估值條件規則排除）。

| 檔案 | 實測增加（11/05） | PM 上限 |
|---|---|---|
| `latest.json` | +1,361 B（含上櫃法人 1 天）；上櫃法人補滿後約 +1.7 KB | 3 KB |
| `stocks/` | +142,433 B（1,901 檔有 `val`；48 檔 cap 不輸出） | 300 KB |
| `screen.json` | +5,188 B | 15 KB |
| 匯出耗時 | 16.7 → 18.9～19.3 秒 | +5 秒 |

### 6-3 畫面

- **今日頁 `valCard`**（市場寬度卡 `breadthCard` 之後，同一個 `section`）：
  - 標題「估值位置（官方，股票中位數）　11/05」。
  - 上市一行、上櫃一行：`上市　本益比 15.75（一年最低）　淨值比 1.53（一年位置 0.4%）　殖利率 2.77%（一年位置 56.6%）`。
  - 上市本益比 60 日迷你圖（`spark(V.TWSE.s)`，PM 延後順序第 2；原型已做，+1 行）＋「上市本益比中位數，近 60 個交易日（08/10 起）」。
  - 口徑說明（定稿）：「一年位置 = 近 242 個交易日（11/05 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 877、上櫃 674 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號」。
  - `valuation` null → 整張卡不顯示。
- **個股頁**（`stock.js` 指標卡）：本益比、股價淨值比、殖利率三張卡的小字加「一年位置 16%（22.47～34.87）」，最低／最高時「一年位置 最低（…）」；與既有 `fundSub` 以 `<br>` 並列。有 `val` 時指標卡下方加一行說明：「一年位置 = 近 242 個交易日中，官方值小於或等於今天的天數比例（資料 11/05）。本益比位置也反映獲利變化：獲利下降時本益比會升高，請一併看淨值比。」
  - 5314、6669、5904（cap）：沒有 `val`，卡片維持原樣（已有「股本變動，官方值可能尚未調整」）。
  - 6456 只有淨值比位置（本益比、殖利率不足或 ≤ 0）。
- **選股**（PM 延後順序第 1；原型已做，+3 行）：條件「淨值比一年位置 ≤ {10|20|30}%」（預設 20，`val: true`，結果欄 pb、pbp）；`SCR_COLS.pbp = ['淨值比位置', …, v => fmt(v) + '%', 1]`，不上色。11/05：pbp ≤ 20 共 1,041 檔（含預設排除）。

---

## 七、邊界情況總表

| # | 情況 | 預期 | 測試 |
|---|---|---|---|
| 1 | 上櫃回應 `stat` 非 ok／休市空表 | 回 []，不寫入 | `test_f91_parse_tpex_amount` |
| 2 | 上櫃回應 `date` ≠ 查詢日 | 回 [] | 同上 |
| 3 | 欄位名稱改變／單位不齊 6 個 | 回 [] | 同上 |
| 4 | 「外資及陸資合計」「自營商合計」 | 不存；`total` 不重複 | 同上 |
| 5 | 同日同單位上市、上櫃各一列 | 兩列並存；同市場重寫 = 更新 | `test_f91_merge_sql_has_market`（SQL 文字）；實際由步驟 4 SQL 驗證 |
| 6 | 上櫃行情當天 0 列 | 不發上櫃金額請求 | `test_f91_collect_waits_for_tpex_prices` |
| 7 | `history --only amount` 上市已齊 | 只抓上櫃 | `test_f91_history_only_amount_fills_tpex` |
| 8 | 7/31 以前沒有上櫃金額 | `check` 不判缺 | `test_f91_check_rows` |
| 9 | 上櫃比上市晚一天 | 上櫃一行「尚未更新」，不退回估算 | 前端預覽（mock JSON） |
| 10 | 上櫃官方從未有資料 | `insti_official_tpex: null`，退回估算一行 | `test_f91_amount_by_market`＋預覽 |
| 11 | `setup-db` 重複執行 | 三條遷移都有 IF 判斷 | `test_f91_ddl_repeatable`（文字）＋步驟 3 |
| 12 | 資料庫連不上（history、export） | 一行中文、rc 2、無 Traceback | `test_qa05_main_db_error` |
| 13 | 月初週末（11/01） | 不收營收（第一個交易日才開始） | `test_f92_month_requests` |
| 14 | mopsov 只有標題列 | 0 家、無錯誤、`revenue_on` 記當天 | `test_f92_header_only_csv` |
| 15 | 跨月 catch-up、上月未齊 | 兩個月份都排 | `test_f92_make_plan` |
| 16 | 1 月 | 收前一年 12 月 | `test_f92_revenue_month_for` |
| 17 | 11/10 未齊 | ⏳ 公布期間 | `test_f92_check_revenue` |
| 18 | 週一、前一交易日週五有收 | ⏳ | 同上 |
| 19 | 已過 10 日、收集停了 | ❌、rc 1、建議指令 | 同上 |
| 20 | `check_report` 舊呼叫（無 revenue） | 不印營收一行 | 同上 |
| 21 | 5 日窗口內面額變更（5904） | 個股 m5 = 換算值 = screen m5 | `test_f93_stock_margin_conv` |
| 22 | 無換算 | m5 與現行相同 | 同上＋compare |
| 23 | 估值序列空／今天 None | `position` 回 None | `test_f94_position` |
| 24 | 全部相同值 | 位置 100、lo = hi | 同上 |
| 25 | 今天本益比 null／≤ 0 | 不輸出 pe，pb 照常 | `test_f94_stock_valuation` |
| 26 | 有效天數 < 120 | 不輸出 | 同上 |
| 27 | cap = 1 | 不輸出 `val`；screen 仍有 pbp | recalc 檢查 |
| 28 | `stock_fundamentals` 空 | `valuation: null`、無 `val` | `_load_valuation` 第一個 return |
| 29 | 某市場某天沒有本益比 > 0 的股票 | 該天不計入窗口天數 | `test_f94_market_valuation` |
| 30 | 營收只有一個月份 | 不顯示公布期間說明 | 預覽 |

---

## 八、測試

### 8-1 `tests/test_iter09.py`（全文見附錄 F；不連網、不連資料庫，`python3 tests/test_iter09.py`，相容 pytest）

| 測試 | 內容 |
|---|---|
| `test_f91_parse_tpex_amount` | 11/05 原始回應 → 6 列、值與附錄 A-1 相同；stat 非 ok、日期不符、缺欄位、缺單位 → [] |
| `test_f91_twse_rows_have_market` | 上市解析每列 market = TWSE |
| `test_f91_merge_sql_has_market` | MERGE 的 OPENJSON、ON、INSERT 都含 market |
| `test_f91_amount_by_market` | 上市、上櫃並存時 `insti_official` 只取上市；上櫃 null 時 |
| `test_f91_keys_and_spec` | `DATASET_KEYS`、`DAY_KEYS` 順序、`SPECS.since`、`SECONDS_PER_KEY` |
| `test_f91_collect_waits_for_tpex_prices` | 上櫃行情 0 列 → 不呼叫上櫃金額 |
| `test_f91_history_only_amount_fills_tpex` | 上市已有、上櫃缺 → 只排 `amount.TPEx` |
| `test_f91_check_rows` | 上櫃缺一天 → ❌；7/31 前不判；上市一列不受影響 |
| `test_f91_ddl_repeatable` | DDL 清單含 3 條遷移且都有 IF 判斷、順序正確 |
| `test_qa05_main_db_error` | `pyodbc.Error` → rc 2、無 Traceback |
| `test_f92_*` | 第四節所有情境（PM 驗收 F9-2 #1、#2、#3、#6） |
| `test_f93_stock_margin_conv` | 寶雅 5904 |
| `test_f94_*` | `position`、`market_valuation`、`stock_valuation` |

舊測試要改：`tests/test_iter03.py`（附錄 E：`_full_snapshot` 加 `amount.TPEx`、`ALL_EP` 加 `insti/summary`、`World._tpex_amount`、`apply_merge` 依 market 分鍵）。不改的話 test_iter03～07 會出 `KeyError: 'amount.TPEx'`。

### 8-2 QA 清單

1. 單元測試：`test_iter01～09` 全過；`test_iter09` 對舊程式反證（除 header_only 外皆失敗）。
2. 改表：第三節步驟 3 的 SQL；上市 390 列改表前後 `diff` 相同。
3. 補抓：步驟 4 的 SQL；上櫃 11/05 與附錄 A-1 完全相同；11/04 外資 −22.41 億。
4. 隔離：`python3 logs/iter09_compare.py logs/iter09_before site/data` → ✅；`--keep-new` → 不同。
5. 獨立重算：`python3 logs/iter09_recalc.py` → ✅（**之後的資料日一律以此為準**，不比對附錄 A 的 11/05 數字）。
6. `check`：上櫃法人金額一列；營收一行狀態符合當天日期。
7. 畫面（375 px，8001 埠）：今日頁三大法人卡兩行官方、無上櫃估算數字；估值位置卡；`#/stock/2603` 三張卡位置＋說明；`#/stock/5314` 無位置；選股「重設」檔數 = 清 localStorage 後的預設檔數、hash 回預設；`#/etf/00997A`、`00982A` 文字；選股 mock `rmd = {"202610": 285, "202609": 1693}` 時資料日一行有說明、6456 標「（10月）」。
8. QA SQL（獨立重算的核心，`iter09_recalc.py` 內含，可單獨執行）：
   ```sql
   -- 上櫃法人金額（億 = 元 / 1e8，1 位）
   SELECT TOP 20 trade_date,
          SUM(CASE WHEN unit='foreign' THEN net_amount END) foreign_,
          SUM(CASE WHEN unit='trust' THEN net_amount END) trust,
          SUM(CASE WHEN unit IN ('dealer_self','dealer_hedge') THEN net_amount END) dealer,
          SUM(CASE WHEN unit='total' THEN net_amount END) total
   FROM insti_amount WHERE market='TPEx' GROUP BY trade_date ORDER BY trade_date DESC;
   -- 市場本益比中位數（每天、分市場、> 0）
   WITH w AS (SELECT DISTINCT TOP 242 trade_date FROM stock_fundamentals ORDER BY trade_date DESC)
   SELECT DISTINCT f.trade_date, s.market_type,
          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.pe_ratio) OVER (PARTITION BY f.trade_date, s.market_type) med
   FROM stock_fundamentals f JOIN stocks s ON s.stock_id=f.stock_id
   WHERE f.trade_date IN (SELECT trade_date FROM w) AND f.pe_ratio > 0;
   -- 月營收各月家數（check 營收一行）
   SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month ORDER BY 1 DESC, 2 DESC;
   ```
9. F9-2 實際資料：**使用者**下一次 `collect --catch-up` 後再驗（PG、QA 不自行觸發）；未收集前以 mock 驗證並在 `05-qa.md` 註明。

---

## 九、README 與 `__main__.py` 修改清單

### README

| 行（現行） | 修改 |
|---|---|
| 第 3、15、21 行 | 測試清單加 `tests/test_iter09.py` |
| 第 40 行（setup-db） | 補「第 9 輪：`insti_amount` 加 `market` 欄、唯一鍵改 `(trade_date, market, unit)`；可重複執行；改表前請先 `backup`」 |
| 第 49、51 行（history 範例） | `--only amount` 說明改「三大法人買賣金額（上市、上櫃；已有的市場自動略過）」 |
| 第 59 行（collect 說明） | 三大法人金額（上市、上櫃）；月營收「月初起（當月第一個交易日）每天收已公布的公司，達前一月 98% 為止」，刪除「每月 10 日以後」 |
| 第 76 行（資料表） | `insti_amount`：上市 BFI82U、上櫃 insti/summary，`market` 欄 |
| 第 126 行（選股） | 新條件「淨值比一年位置 ≤ N%」；按鈕「重設」回到預設（保留共同排除）；營收公布期間說明 |
| 第 127 行（今日三大法人卡） | 「上櫃仍為估算」改為「上市、上櫃都是官方金額（上櫃從 2026-07-31 起）；上櫃官方尚無資料時才顯示估算」 |
| 新增（今日頁） | 估值位置卡：口徑（窗口 242 日、中位數計入條件、位置定義、不是加權指數本益比） |
| 新增（個股頁） | 本益比、淨值比、殖利率一年位置；股本變動、虧損、無股利、新上市不顯示 |
| 第 134、135 行（月營收） | 收集時點改為月初起；選股月份混雜說明 |
| 第 146 行（資料完整性） | `check` 新增「上櫃法人金額」一列與「月營收」一行（✅／⏳／❌ 條件） |
| 匯出欄位段落 | `latest.json`：`insti_official_tpex`、`valuation`；`stocks/{代號}.json`：`val`；`screen.json`：`pbp` |
| 指令段落 | `history`、`export` 連不上資料庫時顯示一行說明、回傳碼 2 |

### `__main__.py`

- docstring 第 5 行 collect 說明：「三大法人金額（上市、上櫃）」；若提到營收時點，改為月初起。
- docstring `--only amount` 範例行（附錄 C 已改）。
- `history --only` 的 help：`amount = 上市、上櫃三大法人買賣金額`；`choices` 不變。
- `main()` 攔截 `pyodbc.Error`（第二節）。

---

## 十、對 PM 範圍的調整建議（不改 02-pm.md）

1. **月營收從「當月第一個交易日」開始收，不是 1 日**：`make_plan` 依交易日決定月份。PM 驗收 F9-2 #3「11/02、10 月 0 家 → ⏳」仍成立；#6 的模擬結果是 11/02～11/11。
2. **上市 `amount` 不加行情保護**：現行本來沒有，加了會改變上市行為（違反隔離），留待之後。
3. **不新增 `history --only` 選項**：`amount` 同時涵蓋上市、上櫃，已有的市場自動略過。PM 驗收 F9-1 #9「`--only` 新鍵」改為「說明文字更新」。
4. **選股月份小字第 8 輪已完成**：本輪只加資料日說明與頁尾說明。
5. **三大法人卡不加「上市＋上櫃」合計大字**：兩邊日期可能不同；且各自四捨五入到 0.1 億後相加會和真實合計差 0.1 億。上櫃一行寫自己的合計。
6. **選股按鈕改名「重設」**；README 無「清除」字樣。
7. **cap = 1 不輸出個股 `val`**（二選一定案「不顯示」）；市場中位數不排除 cap。
8. **個股殖利率位置只計 > 0**，今天殖利率 0 不顯示（與市場中位數含 0 不同，寫在定義表）。
9. **`latest.json status.datasets` 多一項 `amount.TPEx`**：列入 compare 的新鍵清單。
10. **延後順序三項（選股 `pbp`、今日頁 60 日迷你圖、上櫃 20 日迷你圖）原型都已完成且量小**（合計約 +8 行、`screen.json` +5 KB），建議本輪一併做；時間不足時依 PM 順序（`pbp` → 60 日迷你圖 → 上櫃迷你圖）**由後往前**刪。
11. **改表後不可再執行舊程式**；「改查詢」到「改表」之間不可執行 `export`、`check`、`collect`（第三節步驟 2）。建議 PM 在 `04-dev.md` 檢查項加這一條。
12. QA-05 回傳碼定為 2（PM 只要求非 0）。

---

## 十一、給 PG、QA 的提醒

- PG：
  - 步驟順序不可調換；步驟 3 前務必確認舊鍵名；DDL ③ 若報欄位不存在，改用 `EXEC(...)`（1-2）。
  - `merge_insti_amount` 的 rows **每列都要有 `market`**；上市解析漏了會被 DEFAULT 'TWSE' 蓋過，看不出錯，所以測試 `test_f91_twse_rows_have_market` 不可刪。
  - 不得為了驗收執行 `collect`、`revenue` 或另外抓 10 月營收（PM 風險 4）。
  - 匯出耗時超過 +5 秒時在 `04-dev.md` 說明。
  - 預覽用 8001 埠；暫存檔放 scratchpad 或 `logs/`，不放 `/tmp`。
- QA：
  - 資料日已不是 11/05 時，一律以 `iter09_recalc.py` 的 SQL 重算為準。
  - `iter09_compare.py` 的基線必須是步驟 1 用舊程式匯出的 `logs/iter09_before/`。
  - F9-2 實際資料等使用者收集。

## 十二、待辦（本輪之後）

- 上市 `amount` 的行情保護（第十節 #2）。
- 營收「當天最後一次排程再抓一次」（請求量 ×2，PM 暫不要）。
- 估值：產業別位置、加權指數本益比、B5 之後用季 EPS 自算本益比。
- `logs/counts.py` 等舊工具的 `insti_amount` 分市場計數。

---

## 附錄 A：預期值

### A-1 上櫃 11/05（`insti/summary` 原始回應，元）

| unit | buy_amount | sell_amount | net_amount |
|---|---|---|---|
| foreign | 68,076,212,954 | 69,660,322,744 | −1,584,109,790 |
| foreign_dealer | 0 | 0 | 0 |
| trust | 4,007,623,069 | 5,103,111,498 | −1,095,488,429 |
| dealer_self | 1,702,055,844 | 1,952,825,490 | −250,769,646 |
| dealer_hedge | 2,618,281,045 | 3,538,074,742 | −919,793,697 |
| total | 76,404,172,912 | 80,254,334,474 | −3,850,161,562 |

顯示：外資 −15.8、投信 −11.0、自營 −11.7、合計 −38.5 億。上市 11/05 不變：外資 −1,024.6、投信 +225.9、自營 −435.3、合計 −1,233.9 億。

### A-2 市場估值（原型匯出，與 PM 表全部相同）

| 資料日 | 市場 | 本益比 | 淨值比 | 殖利率 | n |
|---|---|---|---|---|---|
| 11/04 | 上市 | 16.41（16.39～21.76；0.8%） | 1.56（3.3%） | 2.65%（45.5%） | 875 |
| 11/04 | 上櫃 | 18.21（18.20～25.38；0.8%） | 1.87（1.7%） | 1.86%（54.5%） | 674 |
| 11/05 | 上市 | 15.75（15.75～21.76；0.4%，一年最低） | 1.53（0.4%） | 2.77%（56.6%） | 877 |
| 11/05 | 上櫃 | 17.57（17.57～25.38；0.4%，一年最低） | 1.82（0.8%） | 1.95%（61.6%） | 674 |

### A-3 個股（11/05，`val`）

| 股票 | pe | pb | dy |
|---|---|---|---|
| 2330 | [16, 22.47, 34.87] | 30 | 59 |
| 2317 | [10, 13.83, 21.95] | 11 | 87 |
| 2412 | [100, 26.16, 31.73]（顯示「最高」） | 100 | 1 |
| 2603 | [94, 2.98, 10.88] | 95 | 6 |
| 5314、6669、5904 | 無 `val`（cap = 1） | | |
| 6456 | 無 | 90 | 無 |

（11/04 的 2330、2603 數字與 PM 表相同，以窗口 2025-11-04～2026-11-04 重算。）

### A-4 `check` 範例

```
上櫃法人金額      19/20 ❌
…
處置／注意股最後成功：2026-11-05 19:00
月營收 2026/10：已收 287 家（前一月 1,980 家的 14%），⏳ 公布期間（每月 10 日前）

❌ 上櫃法人金額：缺 2026-11-04
```

---

（附錄 B 以後為原型程式碼與工具全文，由 scratchpad 原型直接附上。）

## 附錄 B：原型的驗證方式（供 PG 重現，不需照做）

- `orig/`、`proj/` 為 `twstock/`、`site/`、`tests/` 的副本（不含 `.env`）；附錄 C～E 為 `diff -ru orig proj` 的結果（已去掉 `__pycache__` 的二進位差異行）。
- 匯出：以 `config` 唯讀連線呼叫 `proj` 的 `export_all`，輸出到 scratchpad；`--sim` 只在讀取時改寫 SQL（`insti_amount` 視為已有 `market = 'TWSE'`，並以 `CAST(n AS BIGINT)` 注入上櫃 11/05 的 6 列），沒有寫入資料庫。
- 基線：同樣方式用 `orig` 匯出，作為 `iter09_compare.py` 的第一個參數。
- 結果：compare「✅ 相同」（`margin.m5` 0 檔不同）；`--keep-new` 判定不同；recalc「✅ 相同」；匯出 18.9～19.3 秒（基線 16.7 秒）。

## 附錄 C：後端程式差異（`diff -ru orig/twstock proj/twstock`）

```diff
diff -ru orig/twstock/__main__.py proj/twstock/__main__.py
--- orig/twstock/__main__.py	2026-11-05 21:33:55
+++ proj/twstock/__main__.py	2026-11-05 21:43:21
@@ -9,7 +9,7 @@
   python -m twstock history --start 2025-10-30 --only pe      只補本益比／淨值比／殖利率
   python -m twstock history --start 2026-02-23 --only index   只補加權指數歷史
   python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
-  python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
+  python -m twstock history --start 2026-07-31 --only amount  只補三大法人買賣金額（上市、上櫃；已有的市場自動略過）
   python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
   python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
@@ -195,7 +195,7 @@
     s.add_argument("--end", type=_date, help="預設今天")
     s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "etf", "margin", "holdings"],
                    help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
-                        "amount = 上市三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股）；"
+                        "amount = 上市、上櫃三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股）；"
                         "預設 prices pe insti etf margin")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
     s.add_argument("--no-revenue", action="store_true")
@@ -244,7 +244,12 @@
     s.set_defaults(fn=cmd_backup)
 
     args = p.parse_args(argv)
-    return args.fn(args) or 0
+    import pyodbc
+    try:
+        return args.fn(args) or 0
+    except pyodbc.Error as e:        # QA-05：history、export 等連不上資料庫時不印 Traceback（collect、check、backup 各自已處理）
+        print(f"❌ 連不上資料庫或資料表不存在（請確認 Docker 與容器已啟動，並執行過 setup-db）：{str(e).splitlines()[0][:200]}")
+        return 2
 
 
 if __name__ == "__main__":
diff -ru orig/twstock/collectors/catchup.py proj/twstock/collectors/catchup.py
--- orig/twstock/collectors/catchup.py	2026-11-05 21:33:55
+++ proj/twstock/collectors/catchup.py	2026-11-05 21:38:53
@@ -14,7 +14,7 @@
 from .. import db, fetch, health
 from ..config import DB_CONFIG, SITE_DATA_DIR, tw_now
 from ..fetch import FetchError
-from ..health import Row, due_days, evaluate, load_snapshot, load_state, medians, missing_keys
+from ..health import REVENUE_DONE_RATIO, Row, due_days, evaluate, load_snapshot, load_state, medians, missing_keys
 from ..tradingcal import (add_adhoc, is_adhoc_closure, is_trading_day, load_closed, remove_adhoc, trading_days,
                           update_calendar, warn_uncovered)
 from .alerts import collect_alerts
@@ -28,7 +28,6 @@
 DEFAULT_DAYS, MAX_DAYS = 10, 30
 CHAINS_REFRESH_DAYS = 30
 DB_RETRY_SECONDS = 60       # 開機登入時 Docker 可能還沒起來，等一下再試一次
-REVENUE_DONE_RATIO = 0.98   # 該月筆數 ≥ 前一月 × 98% 視為公布完成
 
 
 def month_key(d: date) -> tuple:
diff -ru orig/twstock/collectors/daily.py proj/twstock/collectors/daily.py
--- orig/twstock/collectors/daily.py	2026-11-05 21:33:55
+++ proj/twstock/collectors/daily.py	2026-11-05 21:38:00
@@ -23,12 +23,12 @@
 HOLDINGS_KEYS = tuple(f"holdings.{c}" for c in HOLDINGS)
 # 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵
 DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
-                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount",),
+                INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount", "amount.TPEx"),
                 ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx"), HOLDINGS_DS: HOLDINGS_KEYS}
 # 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券與持股（兩者都只寫入 etfs 已有的 ETF）
 # 漲跌家數不補歷史（health.BREADTH_FROM），所以不在 DATASET_KEYS；上市家數與行情共用同一個 MI_INDEX 回應
 DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "etf.TWSE", "etf.TPEx", "pe.TWSE", "pe.TPEx",
-            "insti.TWSE", "insti.TPEx", "amount", "margin.TWSE", "margin.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
+            "insti.TWSE", "insti.TPEx", "amount", "amount.TPEx", "margin.TWSE", "margin.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
 PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)
 
 
@@ -641,7 +641,7 @@
         unit = _amount_unit(str(row[idx["單位名稱"]]).strip())
         if unit:
             rows[unit] = {"trade_date": d.isoformat(), "unit": unit,
-                          "buy_amount": clean_number(row[idx["買進金額"]], int),
+                          "market": "TWSE", "buy_amount": clean_number(row[idx["買進金額"]], int),
                           "sell_amount": clean_number(row[idx["賣出金額"]], int),
                           "net_amount": clean_number(row[idx["買賣差額"]], int)}
     return list(rows.values())
@@ -653,18 +653,56 @@
     return parse_insti_amount(data, d)
 
 
+# 上櫃 insti/summary 的單位名稱（去掉前面的全形空白與「*」）→ 代碼；「外資及陸資合計」「自營商合計」不存（避免重複）
+TPEX_AMOUNT_UNIT = {"外資及陸資(不含自營商)": "foreign", "外資自營商": "foreign_dealer", "投信": "trust",
+                    "自營商(自行買賣)": "dealer_self", "自營商(避險)": "dealer_hedge", "三大法人合計": "total"}
+
+
+def parse_tpex_insti_amount(data: dict, d: date) -> list:
+    """
+    上櫃 insti/summary 回應 → 與 parse_insti_amount 同形的 6 列（market = TPEx，元）。
+    休市、stat 不是 ok、回應日期不是 d、欄位不符或 6 個單位不齊 → []（不寫入）。
+    「三大法人合計」不含外資自營商（官方 notes），與上市「合計」口徑相同。
+    """
+    if str(data.get("stat", "")).lower() != "ok" or data.get("date") not in (None, f"{d:%Y%m%d}"):
+        return []
+    need = ("單位名稱", "買進金額(元)", "賣出金額(元)", "買賣超(元)")
+    for table in data.get("tables", []):
+        idx = {f: i for i, f in enumerate(table.get("fields", []))}
+        if not set(need) <= idx.keys():
+            continue
+        rows = {}
+        for row in table.get("data", []):
+            if len(row) <= max(idx[f] for f in need):
+                continue
+            unit = TPEX_AMOUNT_UNIT.get(str(row[idx["單位名稱"]]).strip().rstrip("*"))
+            if unit:
+                rows[unit] = {"trade_date": d.isoformat(), "market": "TPEx", "unit": unit,
+                              "buy_amount": clean_number(row[idx["買進金額(元)"]], int),
+                              "sell_amount": clean_number(row[idx["賣出金額(元)"]], int),
+                              "net_amount": clean_number(row[idx["買賣超(元)"]], int)}
+        return list(rows.values()) if len(rows) == len(TPEX_AMOUNT_UNIT) else []
+    return []
+
+
+def fetch_tpex_insti_amount(d: date) -> list:
+    data = request("POST", f"{TPEX}/insti/summary", data={"date": f"{d:%Y/%m/%d}", "response": "json"})
+    return parse_tpex_insti_amount(data, d)
+
+
 def merge_insti_amount(cursor, rows: list):
+    """rows 每列都要有 market（TWSE／TPEx）；同一天、同一市場、同一單位重複寫入 = 更新。"""
     cursor.execute("""
         MERGE insti_amount AS t
         USING OPENJSON(?) WITH (
-            trade_date DATE, unit NVARCHAR(20), buy_amount BIGINT, sell_amount BIGINT, net_amount BIGINT
+            trade_date DATE, market NVARCHAR(10), unit NVARCHAR(20), buy_amount BIGINT, sell_amount BIGINT, net_amount BIGINT
         ) AS s
-        ON t.trade_date = s.trade_date AND t.unit = s.unit
+        ON t.trade_date = s.trade_date AND t.market = s.market AND t.unit = s.unit
         WHEN MATCHED THEN UPDATE SET
             buy_amount = s.buy_amount, sell_amount = s.sell_amount, net_amount = s.net_amount
         WHEN NOT MATCHED THEN
-            INSERT (trade_date, unit, buy_amount, sell_amount, net_amount)
-            VALUES (s.trade_date, s.unit, s.buy_amount, s.sell_amount, s.net_amount);
+            INSERT (trade_date, market, unit, buy_amount, sell_amount, net_amount)
+            VALUES (s.trade_date, s.market, s.unit, s.buy_amount, s.sell_amount, s.net_amount);
     """, db.to_json(rows))
 
 
@@ -789,7 +827,7 @@
         _save(lambda cur: (merge_margin(cur, d, stocks, "stock"), etfs and merge_margin(cur, d, etfs, "etf"),
                            merge_margin_market(cur, d, market, total)))
         return len(stocks)
-    amount = fetch_twse_insti_amount(d)
+    amount = (fetch_tpex_insti_amount if market == "TPEx" else fetch_twse_insti_amount)(d)    # "amount" = 上市、"amount.TPEx" = 上櫃
     if amount:
         _save(merge_insti_amount, amount)
     return len(amount)
@@ -805,8 +843,8 @@
     written, errors, cache = {}, {}, {}
     for key in keys:
         dataset, _, market = key.partition(".")
-        if dataset in ("pe", "insti", MARGIN, "breadth") and written.get(f"prices.{market}") == 0:
-            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數不可能先有，不發請求
+        if dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT) and written.get(f"prices.{market}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數、上櫃法人金額不可能先有，不發請求
         if dataset == "pe" and f"prices.{market}" in errors:
             continue                # 本益比只寫入有行情列的股票
         try:
diff -ru orig/twstock/collectors/history.py proj/twstock/collectors/history.py
--- orig/twstock/collectors/history.py	2026-11-05 21:33:55
+++ proj/twstock/collectors/history.py	2026-11-05 21:38:00
@@ -18,7 +18,7 @@
 
 # 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
 SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
-                   "index.TAIEX": 4, "amount": 4, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
+                   "index.TAIEX": 4, "amount": 4, "amount.TPEx": 3.2, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
                    **{k: 3.2 for k in HOLDINGS_KEYS}}
 SHARED = {"etf.TWSE": "prices.TWSE", "etf.TPEx": "prices.TPEx"}   # 同一天也要抓行情時共用回應，不另計時
 SECONDS_PER_MONTH = 3.2
diff -ru orig/twstock/collectors/revenue.py proj/twstock/collectors/revenue.py
--- orig/twstock/collectors/revenue.py	2026-11-05 21:33:55
+++ proj/twstock/collectors/revenue.py	2026-11-05 21:38:00
@@ -53,9 +53,7 @@
 
 
 def revenue_month_for(d: date):
-    """每月 10 日前各公司營收才公布完；10 日以後才收上個月的營收。"""
-    if d.day < 10:
-        return None
+    """d 所在月份的上一個月（第 9 輪：月初起就收已公布的公司，不再等 10 日；何時停由 make_plan 的 98% 判斷）。"""
     return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)
 
 
diff -ru orig/twstock/db.py proj/twstock/db.py
--- orig/twstock/db.py	2026-11-05 21:33:55
+++ proj/twstock/db.py	2026-11-05 21:37:30
@@ -232,21 +232,31 @@
         CONSTRAINT UQ_price_events UNIQUE (stock_id, event_date, source)
     )
     """,
-    # 上市三大法人買賣金額（證交所 BFI82U，單位：元；含 ETF 等全部證券）
+    # 三大法人買賣金額（單位：元；含 ETF 等全部證券）：上市證交所 BFI82U、上櫃櫃買 insti/summary（第 9 輪加 market）
     """
     IF OBJECT_ID('insti_amount') IS NULL
     CREATE TABLE insti_amount (
         id          INT IDENTITY(1,1) PRIMARY KEY,
         trade_date  DATE          NOT NULL,
+        market      NVARCHAR(10)  NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE'
+                                  CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx')),
         unit        NVARCHAR(20)  NOT NULL,   -- foreign 外資及陸資(不含外資自營商) / foreign_dealer 外資自營商 /
                                               -- dealer_self 自營商(自行買賣) / dealer_hedge 自營商(避險) / trust 投信 / total 合計
         buy_amount  BIGINT        NULL,
         sell_amount BIGINT        NULL,
         net_amount  BIGINT        NULL,
         created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
-        CONSTRAINT UQ_insti_amount UNIQUE (trade_date, unit)
+        CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)
     )
     """,
+    # 第 9 輪遷移（既有資料庫）：加 market（既有列 = TWSE）→ 刪舊唯一鍵 → 建新唯一鍵；每一步都先判斷，可重複執行
+    "IF COL_LENGTH('insti_amount', 'market') IS NULL "
+    "ALTER TABLE insti_amount ADD market NVARCHAR(10) NOT NULL CONSTRAINT DF_insti_amount_market DEFAULT 'TWSE' "
+    "CONSTRAINT CK_insti_amount_market CHECK (market IN ('TWSE','TPEx'))",
+    "IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount' AND parent_object_id = OBJECT_ID('insti_amount')) "
+    "ALTER TABLE insti_amount DROP CONSTRAINT UQ_insti_amount",
+    "IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount_market' AND parent_object_id = OBJECT_ID('insti_amount')) "
+    "ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)",
     # 收集執行紀錄（時間為台灣時間，由 Python 傳入；容器的 GETDATE() 是 UTC，不可使用）
     """
     IF OBJECT_ID('collect_runs') IS NULL
diff -ru orig/twstock/export.py proj/twstock/export.py
--- orig/twstock/export.py	2026-11-05 21:33:55
+++ proj/twstock/export.py	2026-11-05 21:48:15
@@ -11,6 +11,7 @@
 """
 import json
 import os
+import statistics
 import time
 from bisect import bisect_left
 from collections import Counter, defaultdict
@@ -44,7 +45,10 @@
 NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
-               "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt")
+               "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp")
+VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
+VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
+VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
 _TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
           (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
 
@@ -195,6 +199,14 @@
     return None
 
 
+def amount_by_market(rows):
+    """F9-1：rows = [(日期, 市場, 單位, 買賣差額)] → {"TWSE": {日期: {單位: 差額}}, "TPEx": {…}}；insti_official 只用 TWSE。"""
+    out = {"TWSE": defaultdict(dict), "TPEx": defaultdict(dict)}
+    for d, m, unit, net in rows:
+        out[m][d][unit] = net
+    return out
+
+
 def _insti_official(amount):
     """A2：amount = {日期: {單位: 買賣差額(元)}}；有「合計」的最後一天為資料日。外資 = 外資及陸資（外資自營商已含在自營商）。"""
     days = [d for d in sorted(amount) if amount[d].get("total") is not None]
@@ -209,6 +221,82 @@
             "t": [yi(amount[d]["total"]) for d in recent], "fs": streak(foreign)}
 
 
+# ─── 估值的一年位置（第 9 輪 F9-4，A10＋B7）────────────────────
+def position(series, today):
+    """位置 % = series 中 ≤ today 的筆數 ÷ 筆數 × 100（series 含 today 當天）；series 空或 today 為 None → None。"""
+    if today is None or not series:
+        return None
+    return sum(v <= today for v in series) / len(series) * 100
+
+
+def market_valuation(rows, days):
+    """
+    A10：rows = [(日期, 市場, 本益比, 淨值比, 殖利率)]（float 或 None）；days = 窗口日期（舊到新）。
+    每天、分市場取中位數：本益比、淨值比只計入 > 0，殖利率計入非 null（含 0）。
+    回傳 {市場: {d, from, days, n, pe, pb, dy, s, sf}}；pe／pb／dy = {v 中位數, p 位置 %（1 位）, lo, hi}；
+    s = 最近 VAL_SPARK 天本益比中位數，sf = s 的第一天。
+    """
+    per = defaultdict(lambda: defaultdict(lambda: ([], [], [])))
+    window = set(days)
+    for d, m, pe, pb, dy in rows:
+        if d not in window:
+            continue
+        b = per[m][d]
+        if pe is not None and pe > 0:
+            b[0].append(pe)
+        if pb is not None and pb > 0:
+            b[1].append(pb)
+        if dy is not None:
+            b[2].append(dy)
+    out = {}
+    for m, by_day in per.items():
+        ds = [d for d in days if by_day.get(d) and by_day[d][0]]
+        if not ds:
+            continue
+        r = {"d": str(ds[-1]), "from": str(ds[0]), "days": len(ds), "n": len(by_day[ds[-1]][0])}
+        for i, k in enumerate(("pe", "pb", "dy")):
+            s = [statistics.median(by_day[d][i]) for d in ds if by_day[d][i]]
+            v = statistics.median(by_day[ds[-1]][i]) if by_day[ds[-1]][i] else None
+            r[k] = None if v is None else {"v": round(v, 2), "p": round(position(s, v), 1), "lo": round(min(s), 2), "hi": round(max(s), 2)}
+        r["s"], r["sf"] = [round(statistics.median(by_day[d][0]), 2) for d in ds[-VAL_SPARK:]], str(ds[-VAL_SPARK:][0])
+        out[m] = r
+    return out
+
+
+def stock_valuation(series, today):
+    """
+    B7：series = {"pe"|"pb"|"dy": [窗口內 > 0 的值]}；today = {"pe", "pb", "dy": 窗口最後一天的值（可為 None）}。
+    今天值 None 或 ≤ 0（虧損、無股利）或有效天數 < VAL_MIN → 不輸出該欄。回傳 {欄: [位置 %（整數）, lo, hi]}；全部不輸出 → None。
+    """
+    out = {}
+    for k in ("pe", "pb", "dy"):
+        s, v = series.get(k, []), today.get(k)
+        if v is None or v <= 0 or len(s) < VAL_MIN:
+            continue
+        out[k] = [round(position(s, v)), round(min(s), 2), round(max(s), 2)]
+    return out or None
+
+
+def _load_valuation(cur):
+    """讀窗口內的 stock_fundamentals（約 47 萬列）→ (市場估值, {代號: 個股估值}, 窗口最後一天)。"""
+    days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {VAL_DAYS} trade_date FROM stock_fundamentals ORDER BY trade_date DESC")][::-1]
+    if not days:
+        return None, {}, None
+    f = lambda x: None if x is None else float(x)
+    mrows, series, today = [], defaultdict(lambda: {"pe": [], "pb": [], "dy": []}), {}
+    for d, m, code, pe, pb, dy in cur.execute("""
+        SELECT f.trade_date, s.market_type, s.stock_code, f.pe_ratio, f.pb_ratio, f.dividend_yield
+        FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id WHERE f.trade_date BETWEEN ? AND ?""", days[0], days[-1]):
+        pe, pb, dy = f(pe), f(pb), f(dy)
+        mrows.append((d, m, pe, pb, dy))
+        for k, v in (("pe", pe), ("pb", pb), ("dy", dy)):
+            if v is not None and v > 0:
+                series[code][k].append(v)
+        if d == days[-1]:
+            today[code] = {"pe": pe, "pb": pb, "dy": dy}
+    return market_valuation(mrows, days) or None, {c: stock_valuation(series[c], today.get(c, {})) for c in series}, days[-1]
+
+
 # ─── 融資融券（B2＋A4）與 ETF（E1）────────────────────────
 def usage(balance, limit):
     """融資（券）使用率 %：餘額 ÷ 限額，截斷到小數 2 位（與櫃買官方欄位一致）；限額 0 或空 → None。"""
@@ -238,17 +326,18 @@
     return round(sum(n * c for n, c in items if c is not None) / amount_k * 100, 2), cov
 
 
-def stock_margin(rows: dict, mdate, d5):
+def stock_margin(rows: dict, mdate, d5, conv=()):
     """
     個股 JSON 的 margin。rows：{日期: (融資前日, 融資餘額, 融資限額, 融券前日, 融券餘額, 註記)}；
     mdate：該市場最新融資融券日；d5：往前第 5 個融資融券日（不足 6 天為 None）。該股當天沒有列 → None（無信用交易）。
+    conv：margin_conv 的換算紀錄；m5 以換算後的 5 日前餘額計算（第 9 輪 P23，與 screen_margin 相同）。
     """
     r = rows.get(mdate)
     if r is None:
         return None
     mp, mb, ml, sp, sb, nt = r
     old = rows.get(d5) if d5 else None
-    out = {"d": str(mdate), "mb": mb, "m1": mb - mp, "m5": mb - old[1] if old else None,
+    out = {"d": str(mdate), "mb": mb, "m1": mb - mp, "m5": round(mb - old[1] * conv_k(conv, d5)) if old else None,
            "sb": sb, "s1": sb - sp, "sr": short_ratio(sb, mb), "mu": usage(mb, ml)}
     if nt:
         out["nt"] = nt
@@ -287,12 +376,12 @@
 
 def screen_margin(rows, mdate, d5, conv, market):
     """C3／F8-3 的融資融券欄位（張、%）；5 日增減以換算後的 5 日前餘額計算。該市場沒有資料或該股不在清單 → 全部 None。"""
-    r = stock_margin(rows, mdate, d5) if mdate else None
+    r = stock_margin(rows, mdate, d5, conv) if mdate else None
     if r is None:
         return dict.fromkeys(("mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt"))
     old = rows.get(d5) if d5 else None
     k = conv_k(conv, d5) if old else 1.0
-    return {"mb": r["mb"], "m1": r["m1"], "m5": round(r["mb"] - old[1] * k) if old else None,
+    return {"mb": r["mb"], "m1": r["m1"], "m5": r["m5"],
             "sb": r["sb"], "s1": r["s1"], "s5": round(r["sb"] - old[4] * k) if old else None,
             "sr": r["sr"], "mu": r["mu"], "mnt": (r.get("nt") or None) if market == "TWSE" else None}
 
@@ -765,9 +854,7 @@
     for code, d, c, ch in cur.execute(
             "SELECT index_code, trade_date, close_price, change FROM market_index ORDER BY index_code, trade_date"):
         index_rows[code].append((d, c, ch))
-    amount = defaultdict(dict)
-    for d, unit, net in cur.execute("SELECT trade_date, unit, net_amount FROM insti_amount"):
-        amount[d][unit] = net
+    amount = amount_by_market(cur.execute("SELECT trade_date, market, unit, net_amount FROM insti_amount"))
     alerts = defaultdict(list)
     for code, kind, ann, start, end, reason, measure in cur.execute("""
         SELECT s.stock_code, a.alert_type, a.announce_date, a.start_date, a.end_date, a.reason, a.measure
@@ -792,6 +879,7 @@
     # 寬度輸出 BREADTH_DAYS 天，前面多 60 天給 MA60
     b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
     status = build_status(cur, latest_date, now)
+    valuation, stock_val, val_date = _load_valuation(cur)      # F9-4
     conn.close()
     mlast = {m: ds[-1] for m, ds in mdates.items()}
     m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
@@ -862,9 +950,11 @@
             "fund": dict(zip(("pe", "pb", "dy"), map(_f, fund[code][:3])), date=str(fund[code][3]))
                     if code in fund else None,
             **({"capchg": cap} if cap else {}),
+            # F9-4：估值一年位置；股本變動（cap）時官方值可能尚未調整，不輸出；只有窗口最後一天有官方值的股票才有
+            **({"val": {"d": str(val_date), **stock_val[code]}} if stock_val.get(code) and not cap else {}),
             **({"alerts": alerts[code]} if code in alerts else {}),
             # 該市場有融資融券資料時才有 margin；null = 不在信用交易清單（無信用交易）
-            **({"margin": stock_margin(mper.get(code, {}), mlast[info["market"]], m5[info["market"]])}
+            **({"margin": stock_margin(mrows, mlast[info["market"]], m5[info["market"]], conv)}
                if info["market"] in mlast else {}),
             **({"active": active[code]} if code in active else {}),
             **({"mg": mg} if mg else {}),
@@ -944,7 +1034,8 @@
         screen[code] = {**price_stats(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))],
                                       tv, b_days, idx_close[mkt]),
                         **revenue_stats(rev_rows), "cap": int(cap is not None),
-                        **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt)}
+                        **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt),
+                        "pbp": (stock_val.get(code) or {}).get("pb", [None])[0]}     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
 
     industries = defaultdict(list)
     for code in snapshot:
@@ -966,7 +1057,9 @@
         "dates": replay_dates,
         "market": {k: {**v, "turnover": round(v["turnover"], 1)} for k, v in market.items()},
         "insti": {k: round(v, 1) for k, v in insti_total.items()},
-        "insti_official": _insti_official(amount),
+        "insti_official": _insti_official(amount["TWSE"]),
+        "insti_official_tpex": _insti_official(amount["TPEx"]),      # 第 9 輪 F9-1：上櫃官方（結構同 insti_official）
+        "valuation": valuation,                                      # 第 9 輪 F9-4：市場估值一年位置
         "insti_otc": {k: round(v, 1) for k, v in insti_otc.items()},
         "index": {code: {"date": str(rows[-1][0]), "c": _f(rows[-1][1]), "ch": _f(rows[-1][2]),
                          "p": _f(_pct(rows[-1][1], rows[-1][2])), "from": str(rows[-INDEX_DAYS:][0][0]),
diff -ru orig/twstock/health.py proj/twstock/health.py
--- orig/twstock/health.py	2026-11-05 21:33:55
+++ proj/twstock/health.py	2026-11-05 21:38:53
@@ -35,12 +35,15 @@
             "00982A": Fund("399", 0, None, "群益"), "00992A": Fund("500", 0, date(2025, 12, 30), "群益"),
             "00415A": Fund("504", 0, date(2026, 10, 20), "群益"), "00997A": Fund("502", 1, date(2026, 4, 14), "群益")}
 BREADTH_FROM = date(2026, 11, 3)        # 官方漲跌家數不補歷史，從這天開始收集
+AMOUNT_TPEX_FROM = date(2026, 7, 31)    # 上櫃官方法人金額（第 9 輪）：和上市 insti_amount 同一個起點
+REVENUE_DONE_RATIO = 0.98               # 月營收：該月家數 ≥ 前一月 × 98% 視為公布完成（catchup 共用）
+REVENUE_DUE_DAY = 10                    # 月營收法定公布期限：每月 10 日
 
 SPECS = (
     Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
     Spec("pe.TWSE", "上市本益比", 800, True), Spec("pe.TPEx", "上櫃本益比", 650, True),
     Spec("insti.TWSE", "上市法人", 800, False), Spec("insti.TPEx", "上櫃法人", 550, False),
-    Spec("amount", "上市法人金額", 6, False),
+    Spec("amount", "上市法人金額", 6, False), Spec("amount.TPEx", "上櫃法人金額", 6, False, AMOUNT_TPEX_FROM),
     Spec("index.TAIEX", "加權指數", 1, False), Spec("index.TPEX", "櫃買指數", 1, False),
     Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
     Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
@@ -85,7 +88,8 @@
     for d, market, n in cur.execute("SELECT trade_date, market, COUNT(*) FROM market_breadth WHERE trade_date BETWEEN ? AND ? "
                                     "GROUP BY trade_date, market", start, end).fetchall():
         snap[f"breadth.{market}"][d] = Row(n)
-    for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE trade_date BETWEEN ? AND ? GROUP BY trade_date"),
+    for key, sql in (("amount", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE market = 'TWSE' AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
+                     ("amount.TPEx", "SELECT trade_date, COUNT(*) FROM insti_amount WHERE market = 'TPEx' AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
                      # 只看日盤：夜盤的日期是歸屬日，不代表該日資料已齊
                      ("futures", "SELECT trade_date, COUNT(*) FROM futures_daily_prices WHERE commodity_id = 'TX' AND session = 'DAY' "
                                  "AND trade_date BETWEEN ? AND ? GROUP BY trade_date"),
@@ -308,8 +312,28 @@
     return f"👉 請執行 python3 -m twstock history --start {bad[0]}，再執行 python3 -m twstock collect --catch-up"
 
 
-def check_report(days, snap, now, state, closed, adhoc=(), schedule=None) -> tuple:
-    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）。"""
+def revenue_status(today: date, counts: dict, revenue_on, closed) -> tuple:
+    """
+    月營收一行（第 9 輪 B15）：(狀態, 文字)。counts = {(年, 月): 家數}；revenue_on = 最後一次成功收集營收的日期。
+    ✅ 該月家數 ≥ 前一月 × 98%；⏳ 未達且今天 ≤ 10 日（公布期間），或已過 10 日但 revenue_on 是今天或前一個交易日；
+    ❌ 其餘（已過 10 日、收集停了）。月份 = 今天的上一個月（與 collectors.revenue.revenue_month_for 相同）。
+    """
+    y, m = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
+    prev = counts.get((y - 1, 12) if m == 1 else (y, m - 1), 0)
+    n = counts.get((y, m), 0)
+    head = f"月營收 {y}/{m:02d}：已收 {n:,} 家" + (f"（前一月 {prev:,} 家的 {n / prev:.0%}）" if prev else "")
+    if n and n >= prev * REVENUE_DONE_RATIO:
+        return OK, f"{head}，✅ 已齊"
+    if today.day <= REVENUE_DUE_DAY:
+        return PENDING, f"{head}，⏳ 公布期間（每月 {REVENUE_DUE_DAY} 日前）"
+    before = trading_days(today - timedelta(days=30), today - timedelta(days=1), closed)
+    if revenue_on and (revenue_on >= today or (before and revenue_on >= before[-1])):
+        return PENDING, f"{head}，⏳ 晚交公司陸續補進（最後收集 {revenue_on:%m/%d}）"
+    return ABNORMAL, f"{head}，最後一次收集營收 {revenue_on or '尚無紀錄'}"
+
+
+def check_report(days, snap, now, state, closed, adhoc=(), schedule=None, revenue=None) -> tuple:
+    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）；revenue = 各月營收家數（None 不印營收一行）。"""
     items, med = evaluate(days, snap, now), medians(snap)
     out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）",
            f"🕘 最後一次收集：{last_run_line(state.get('last_run'))}"]
@@ -339,19 +363,30 @@
                                                     for label, d, r in gaps))
     alerts = state.get("alerts_at")
     out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
+    rev = revenue_status(now.date(), revenue, state.get("revenue_on"), closed) if revenue is not None else None
+    if rev:
+        out.append(rev[1] if rev[0] != ABNORMAL else f"{rev[1]}，❌ 異常")
     lines = problem_lines(items, state.get("last_run"))
     # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
     stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
     if stale:
         lines.insert(0, f"❌ 處置／注意股：最後成功 {alerts.date()}，端點只有近幾日，請盡快執行 collect --catch-up")
+    if rev and rev[0] == ABNORMAL:
+        lines.append(f"❌ {rev[1]}：已過 {REVENUE_DUE_DAY} 日仍未收齊，收集可能停了")
     abnormal = sum(ln.startswith("❌") for ln in lines)
     out += ["", *lines] if lines else []
     out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
     if abnormal:
-        out.append(suggest(items, days, bool(stale)))
+        out.append(suggest(items, days, bool(stale) or bool(rev and rev[0] == ABNORMAL)))
     return "\n".join(out), (1 if abnormal else 0)
 
 
+def revenue_counts(cur) -> dict:
+    """{(年, 月): 家數}；SQL 與 collectors.catchup._revenue_counts 相同。"""
+    return {(y, m): n for y, m, n in cur.execute(
+        "SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month").fetchall()}
+
+
 def run_check(n: int, now: datetime) -> int:
     from . import db
     conn = db.connect()
@@ -362,11 +397,12 @@
         # 至少載入 MEDIAN_DAYS 個交易日，--days 小於 20 時中位數才有意義
         start = due_days(now, max(n, MEDIAN_DAYS), closed)[0]
         snap, state = load_snapshot(cur, start, days[-1]), load_state(cur)
+        revenue = revenue_counts(cur)
         adhoc = [r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc' AND holiday_date BETWEEN ? AND ? "
                                            "ORDER BY holiday_date", start, days[-1]).fetchall()]
     finally:
         conn.close()
-    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status())
+    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status(), revenue)
     print(text)
     return rc
 
```

## 附錄 D：前端差異（`site/app.js`、`site/stock.js`）

```diff
--- orig/site/app.js	2026-11-05 21:33:55
+++ proj/site/app.js	2026-11-05 21:49:19
@@ -157,6 +157,7 @@
       ${instiCard(L)}
       ${marginCard(L)}
       ${breadthCard(L)}
+      ${valCard(L)}
     </section>
 
     ${futuresHTML(L.futures)}
@@ -286,10 +287,27 @@
     </div>`;
 }
 
-// 三大法人卡：上市用證交所官方金額（A2），上櫃另列估算值；尚無官方資料時維持第 1 輪估算卡
-function instiCard(L) {
-  const O = L.insti_official, X = L.insti_otc, I = L.insti;
+// 估值位置卡（第 9 輪 F9-4，A10）：上市、上櫃股票的官方本益比、淨值比、殖利率中位數在近一年的位置
+function valCard(L) {
+  const V = L.valuation;
+  if (!V || !(V.TWSE || V.TPEx)) return '';
+  const pos = x => !x ? '--' : x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
+  const row = (x, name) => !x ? '' : `<div class="s num">${name}　本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）　殖利率 <b>${x.dy ? fmt(x.dy.v, 2) + '%' : '--'}</b>（${pos(x.dy)}）</div>`;
+  const T = V.TWSE || V.TPEx;
+  return `<div class="card stat idx">
+      <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
+      ${row(V.TWSE, '上市')}${row(V.TPEx, '上櫃')}
+      ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
+      <div class="s">一年位置 = 近 ${T.days} 個交易日（${md(T.from)} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號</div>
+    </div>`;
+}
+
+// 三大法人卡：上市（A2）、上櫃（第 9 輪 F9-1）都用官方金額；上櫃官方還沒有任何資料時退回估算一行；上市也沒有時維持第 1 輪估算卡
+function instiCard(L) {
+  const O = L.insti_official, P = L.insti_official_tpex, X = L.insti_otc, I = L.insti;
   const yi1 = v => v == null ? '--' : sgn(v, 1) + '億';
+  const parts = x => `外資 <span class="${cls(x.foreign)}">${yi1(x.foreign)}</span>　投信 <span class="${cls(x.trust)}">${yi1(x.trust)}</span>　自營 <span class="${cls(x.dealer)}">${yi1(x.dealer)}</span>`;
+  const stk = s => s > 0 ? `連買 ${s} 日` : s < 0 ? `連賣 ${-s} 日` : '當日持平';
   if (!O) return `<div class="card stat insti"><div class="l">三大法人（${md(L.flow_date)}）</div>
       <div class="v num ${cls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
       <div class="s num">外資 <span class="${cls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${cls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${cls(I.dealer)}">${yi(I.dealer)}</span></div>
@@ -298,12 +316,15 @@
   return `<div class="card stat idx insti">
       <div class="l">三大法人　上市，官方，含 ETF<span class="muted">　${md(O.date)}${stale ? '（尚未更新）' : ''}</span></div>
       <div class="v num ${cls(O.total)}">${yi1(O.total)}</div>
-      <div class="s num">外資 <span class="${cls(O.foreign)}">${yi1(O.foreign)}</span>　投信 <span class="${cls(O.trust)}">${yi1(O.trust)}</span>　自營 <span class="${cls(O.dealer)}">${yi1(O.dealer)}</span></div>
-      <div class="s">官方含 ETF 與權證避險，與下方估算口徑不同</div>
+      <div class="s num">${parts(O)}</div>
       ${minibars(O.f)}
-      <div class="s">外資近 ${O.f.length} 日（${md(O.d[0])}～${md(O.d.at(-1))}）<b class="${cls(fs)}">${fs > 0 ? `連買 ${fs} 日` : fs < 0 ? `連賣 ${-fs} 日` : '當日持平'}</b></div>
-      ${X ? `<div class="s num">上櫃估算（${md(L.flow_date)}）：外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
-      <div class="s">上櫃為張數 × 收盤估算、不含 ETF，不可與上市官方值相加</div>` : ''}
+      <div class="s">外資近 ${O.f.length} 日（${md(O.d[0])}～${md(O.d.at(-1))}）<b class="${cls(fs)}">${stk(fs)}</b></div>
+      ${P ? `<div class="s num"><b>上櫃</b>（官方，${md(P.date)}${P.date < L.date ? '，尚未更新' : ''}）合計 <span class="${cls(P.total)}">${yi1(P.total)}</span>　${parts(P)}</div>
+      ${minibars(P.f)}
+      <div class="s">上櫃外資近 ${P.f.length} 日（${md(P.d[0])}～${md(P.d.at(-1))}）<b class="${cls(P.fs)}">${stk(P.fs)}</b></div>`
+      : X ? `<div class="s num">上櫃估算（${md(L.flow_date)}）：外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
+      <div class="s">上櫃官方金額尚無資料，暫以張數 × 收盤估算、不含 ETF，不可與上市官方值相加</div>` : ''}
+      <div class="s">官方金額含 ETF 與權證避險，外資不含外資自營商（已計入自營）；上市、上櫃同一天時可相加。下方法人買超／賣超表為張數 × 收盤估算、不含 ETF，口徑不同</div>
     </div>`;
 }
 
@@ -756,6 +777,8 @@
 }
 // 營收欄名的月份：檔數最多的營收月份（YYYYMM）
 const revMonth = () => Object.entries(App.screen?.rmd || {}).sort((a, b) => b[1] - a[1])[0]?.[0];
+// 第 9 輪 F9-2：營收月份混雜（兩個以上月份，且最多的月份不到 98%）→ 資料日一列加公布期間說明
+const revMixed = S => { const n = Object.values(S.rmd || {}), t = n.reduce((a, b) => a + b, 0); return n.length > 1 && Math.max(...n) < t * 0.98; };
 
 // 結果表的動態欄：[欄名, 取值, 格式, 預設方向（1 遞增）]
 const spct = v => v == null ? '--' : sgn(v) + '%';
@@ -778,6 +801,7 @@
   ry: ['營收年增', x => x.ry, (v, x) => spct(v) + (x.rm && String(x.rm) !== revMonth() ? `<span class="muted small">（${x.rm % 100}月）</span>` : '')],
   rc: ['累計年增', x => x.rc, spct], rh: ['營收新高(年)', x => x.rh, int0], r3: ['連3月年增', x => x.r3, v => v === 1 ? '✓' : '--'],
   pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
+  pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
 };
 const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
 // 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動}；sort 有值時欄名可點排序
@@ -789,7 +813,7 @@
     list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
       <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.tv, 1)}億</td>` +
       cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
-        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
+        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
     '</tbody></table></div>';
 }
 
@@ -837,6 +861,8 @@
   { id: 'pe', g: '基本面', label: '0 < 本益比 ≤ {v}', opts: [10, 15, 20], def: 15, val: true, f: (x, v, st) => isNum(x.pe) && x.pe > 0 && x.pe <= v && valGuard(x, st), cols: ['pe'] },
   { id: 'dy', g: '基本面', label: '殖利率 ≥ {v}%', opts: [3, 4, 5, 6], def: 5, val: true, f: (x, v, st) => isNum(x.dy) && x.dy >= v && valGuard(x, st), cols: ['dy'] },
   { id: 'pb', g: '基本面', label: '淨值比 ≤ {v}', opts: [1, 1.5, 2], def: 1, val: true, f: (x, v, st) => isNum(x.pb) && x.pb > 0 && x.pb <= v && valGuard(x, st), cols: ['pb'] },
+  { id: 'pbp', g: '基本面', label: '淨值比一年位置 ≤ {v}%', opts: [10, 20, 30], def: 20, val: true, title: '近 242 個交易日中，淨值比小於或等於今天的天數比例',
+    f: (x, v, st) => isNum(x.pbp) && x.pbp <= v && valGuard(x, st), cols: ['pb', 'pbp'] },
   { id: 'mk', g: '排除', label: '只看 {v}', opts: [[1, '上市'], [2, '上櫃']], def: 1, f: (x, v) => x.m === (v === 1 ? 'TWSE' : 'TPEx') },
   { id: 'xd', g: '排除', label: '排除處置股（含即將處置）', sw: true, f: x => !x.dsp },
   { id: 'xn', g: '排除', label: '排除今日無成交', sw: true, f: x => !x.nt },
@@ -916,18 +942,18 @@
     const chip = ([id, name], ref) => `<button class="chip${ref ? ' ref' : ''}${st.ps === id ? ' on' : ''}" data-ps="${id}"${ref ? ' title="風險檢查，不是買進訊號"' : ''}>${name}</button>`;
     $('#view').innerHTML = `<section class="sec">
       <div class="sec-h">${modeSeg('screen')}</div>
-      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}</div>
+      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}${revMixed(S) ? '（每月 1～10 日為公布期間，各股月份不同）' : ''}</div>
       <div style="margin-top:8px">${notes}</div>
       <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.slice(0, 7).map(p => chip(p)).join('')}
         <span class="muted small">參考：</span>${SCREEN_PRESETS.slice(7).map(p => chip(p, true)).join('')}</div>
       <details class="scr-panel card"${open ? ' open' : ''}><summary>條件（已選 ${conds.length} 個）
-        <button class="chip" id="scrClear">清除</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
+        <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
         ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
       </details>
       <div class="sec-h" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
       <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
         : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
-      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收以各股最新公布的月份計算，每月 1～10 日新舊月份混雜。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
+      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
     const changed = () => { delete st.ps; save(); draw(); };
     onModeSeg();
     $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
@@ -953,7 +979,7 @@
     }));
     const det = $('#view details.scr-panel');
     det.addEventListener('toggle', () => { open = det.open; });
-    $('#scrClear').addEventListener('click', e => { e.preventDefault(); st = { o: 'tv' }; save(); draw(); });
+    $('#scrClear').addEventListener('click', e => { e.preventDefault(); st = { ...SCREEN_DEFAULT }; save(); draw(); });   // P23：回到預設（保留共同排除）
     $('#scrCopy').addEventListener('click', e => {
       e.preventDefault();
       const b = e.currentTarget;
@@ -1088,7 +1114,7 @@
         H.out.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}</td><td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td></tr>`).join('') +
         '</tbody></table></div>' : ''}
       <div class="muted small" style="margin-top:6px">資料來源：${esc(H.trust || '統一')}投信每日申購買回清單。台股為張、海外為股；權重為占基金淨資產 %，權重變化為百分點。
-        本基金為現金申購買回：申購進來的資金由經理人買進股票，所以<b>申購多的日子加碼會偏多</b>、贖回多的日子減碼會偏多。${S.u1 == null ? '' : `今天單位數 1 日 ${sgn(S.u1)}%，張數增幅接近這個比例的持股，多半是跟著申購買進；明顯超過的才比較像經理人的判斷。`}權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。</div></section>`;
+        本基金為現金申購買回：申購進來的資金由經理人買進股票，所以<b>申購多的日子加碼會偏多</b>、贖回多的日子減碼會偏多。${S.u1 == null ? '' : `${S.d === App.latest.date ? '今天' : md(S.d) + ' '}單位數 1 日 ${sgn(S.u1)}%，張數增幅接近這個比例的持股，多半是跟著申購買進；明顯超過的才比較像經理人的判斷。`}權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。</div></section>`;
   onSeg('holdSeg', v => { localStore('holdSort', null, v); renderHoldings(code); });
   $('#view').addEventListener('click', onRowClick);
 }
--- orig/site/stock.js	2026-11-05 21:33:55
+++ proj/site/stock.js	2026-11-05 21:49:19
@@ -38,6 +38,12 @@
   const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
   // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
   const fundSub = v => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', capSub].filter(Boolean).join('；');
+  // 第 9 輪 F9-4（B7）：估值一年位置；股本變動、虧損、無股利、新上市時匯出沒有該欄
+  const VAL = data.val;
+  const valSub = (k, v) => { const x = VAL?.[k]; if (!x || v == null) return '';
+    const [p, lo, hi] = x, f = n => fmt(n, 2) + (k === 'dy' ? '%' : '');
+    return `一年位置 ${v <= lo ? '最低' : v >= hi ? '最高' : p + '%'}（${f(lo)}～${f(hi)}）`; };
+  const subs = (...a) => a.filter(Boolean).join('<br>');
   const watching = App.watch.has(code);
   const fd = md(App.latest.flow_date);
   const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
@@ -92,14 +98,15 @@
 
     <section class="sec metrics">
       ${[['開盤', pfmt(P.o[last])], ['最高', pfmt(P.h[last]), 'up'], ['最低', pfmt(P.l[last]), 'dn'], ['昨收', pfmt(prev)],
-         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)], ['股價淨值比', fmt(fund.pb, 2)],
-         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', fundSub(fund.dy)],
+         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', valSub('pb', fund.pb)],
+         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))],
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          ['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
          ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
+    ${VAL ? `<div class="muted small val-note">一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比位置也反映獲利變化：獲利下降時本益比會升高，請一併看淨值比。</div>` : ''}
     ${acHTML}
 
     <section class="sec card">
```

## 附錄 E：舊測試修改（`tests/test_iter03.py`）

```diff
--- orig/tests/test_iter03.py	2026-11-05 21:33:55
+++ proj/tests/test_iter03.py	2026-11-05 21:39:12
@@ -100,7 +100,7 @@
 
 def _full_snapshot(days, skip=()):
     ok = {"prices.TWSE": Row(1086), "prices.TPEx": Row(889), "pe.TWSE": Row(1082, 870, 1082, 1082),
-          "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6),
+          "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6), "amount.TPEx": Row(6),
           "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9),
           "etf.TWSE": Row(250), "etf.TPEx": Row(120), "margin.TWSE": Row(1100), "margin.TPEx": Row(900),   # 第 4 輪
           "breadth.TWSE": Row(1), "breadth.TPEx": Row(1), **{f"holdings.{c}": Row(50) for c in health.HOLDINGS}}   # 第 5 輪
@@ -360,7 +360,8 @@
 OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
 ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown",
           "MI_MARGN", "margin/balance", "highlight", "GetPCF",     # 第 5 輪：GetPCF 的日期是持股日
-          "etf/buyback")                                            # 第 7 輪群益：和 GetPCF 共用已公布的持股日（down 才用得到）
+          "etf/buyback",                                            # 第 7 輪群益：和 GetPCF 共用已公布的持股日（down 才用得到）
+          "insti/summary")                                          # 第 9 輪：上櫃官方法人金額
 # 第 4 輪：行情回應含 ETF 列（另有權證、TDR 等其他證券，兩邊都不可寫入）；融資融券回應含股票與 ETF
 TWSE_ETFS = [f"00{n:03d}" for n in range(100, 350)]          # 250 檔，如 00100
 TPEX_ETFS = [f"00{n:03d}B" for n in range(700, 820)]         # 120 檔，如 00700B
@@ -415,7 +416,7 @@
                         ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                         ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi),
                         ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn), ("highlight", self._hl), ("GetPCF", self._pcf),
-                        ("etf/buyback", self._cap)):
+                        ("etf/buyback", self._cap), ("insti/summary", self._tpex_amount)):
             if key in url:
                 return fn(form)
         return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})
@@ -493,6 +494,13 @@
         names = ["自營商(自行買賣)", "自營商(避險)", "投信", "外資及陸資(不含外資自營商)", "外資自營商", "合計"]
         return Resp({"stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"], "data": [[n, "1", "1", "0"] for n in names]})
 
+    def _tpex_amount(self, form):                                   # 第 9 輪
+        if self._no("insti/summary", form):
+            return Resp({"stat": "ok", "date": f"{self._date(form):%Y%m%d}", "tables": [{"fields": [], "data": []}]})
+        names = ["外資及陸資合計", "　外資及陸資(不含自營商)", "　外資自營商", "投信", "自營商合計", "　自營商(自行買賣)", "　自營商(避險)", "三大法人合計*"]
+        return Resp({"stat": "ok", "date": f"{self._date(form):%Y%m%d}", "tables": [
+            {"fields": ["單位名稱", "買進金額(元)", "賣出金額(元)", "買賣超(元)"], "data": [[n, "1", "1", "0"] for n in names]}]})
+
     def _empty_tables(self, fields):
         return Resp({"stat": "ok", "tables": [{"fields": fields, "data": []}]})
 
@@ -587,7 +595,8 @@
             for r in rows:
                 self.rows[f"index.{r['index_code']}"][date.fromisoformat(r["trade_date"])] = Row(1)
         elif table == "insti_amount":
-            self.rows["amount"][date.fromisoformat(rows[0]["trade_date"])] = Row(len(rows))
+            key = "amount" if rows[0]["market"] == "TWSE" else "amount.TPEx"      # 第 9 輪
+            self.rows[key][date.fromisoformat(rows[0]["trade_date"])] = Row(len(rows))
         elif table == "futures_daily_prices":
             for d in {r["trade_date"] for r in rows}:
                 self.rows["futures"][date.fromisoformat(d)] = Row(sum(r["trade_date"] == d for r in rows))
```

## 附錄 F：`tests/test_iter09.py`（新檔，全文）

```python
"""
第 09 輪純邏輯測試（不連網、不連資料庫）：
F9-1 上櫃官方三大法人金額（insti/summary 解析、分市場寫入與讀取、資料集鍵、check、改鍵 DDL）＋ QA-05（main 攔截 pyodbc.Error）；
F9-2 月營收提前收集（revenue_month_for、make_plan、只有標題列的 CSV、check 的營收一行、一個月的請求量）；
F9-3 個股 margin.m5 換算（寶雅 5904）；
F9-4 估值一年位置（position、market_valuation、stock_valuation）。
數值以 2026-11-05 的官方回應與資料庫為範例（上櫃法人金額、10 月營收家數）。

  python3 tests/test_iter09.py      （也相容 pytest）
"""
import contextlib
import io
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import catchup, daily, history, revenue  # noqa: E402
from twstock.health import Row  # noqa: E402

D, T, CLOSED = t3.D, t3.T, t3.CLOSED

# 2026-11-05 上櫃 insti/summary 的原始回應（分析師 r9/insti_summary_20261105.json，notes 省略）
TPEX_1105 = {"stat": "ok", "date": "20261105", "tables": [{
    "title": "三大法人買賣金額彙總表", "date": "115/11/05", "fields": ["單位名稱", "買進金額(元)", "賣出金額(元)", "買賣超(元)"],
    "data": [["外資及陸資合計", "68,076,212,954", "69,660,322,744", "-1,584,109,790"],
             ["　外資及陸資(不含自營商)", "68,076,212,954", "69,660,322,744", "-1,584,109,790"],
             ["　外資自營商", "0", "0", "0"],
             ["投信", "4,007,623,069", "5,103,111,498", "-1,095,488,429"],
             ["自營商合計", "4,320,336,889", "5,490,900,232", "-1,170,563,343"],
             ["　自營商(自行買賣)", "1,702,055,844", "1,952,825,490", "-250,769,646"],
             ["　自營商(避險)", "2,618,281,045", "3,538,074,742", "-919,793,697"],
             ["三大法人合計*", "76,404,172,912", "80,254,334,474", "-3,850,161,562"]]}]}


# ─── F9-1：上櫃官方三大法人金額 ─────────────────────────
def test_f91_parse_tpex_amount():
    r = {x["unit"]: x for x in daily.parse_tpex_insti_amount(TPEX_1105, D(11, 5))}
    assert set(r) == {"foreign", "foreign_dealer", "trust", "dealer_self", "dealer_hedge", "total"}     # 兩個「合計」列不存
    assert all(x["market"] == "TPEx" and x["trade_date"] == "2026-11-05" for x in r.values())
    assert r["foreign"]["net_amount"] == -1584109790 and r["trust"]["net_amount"] == -1095488429
    assert r["dealer_self"]["net_amount"] == -250769646 and r["dealer_hedge"]["net_amount"] == -919793697
    assert r["total"]["net_amount"] == -3850161562 and r["total"]["buy_amount"] == 76404172912
    # 合計 = 外資（不含自營商）＋投信＋自營（自行＋避險）；外資自營商已含在自營商，不另加（和上市同口徑）
    assert sum(r[k]["net_amount"] for k in ("foreign", "trust", "dealer_self", "dealer_hedge")) == r["total"]["net_amount"]
    bad = lambda **kw: {**TPEX_1105, **kw}
    assert daily.parse_tpex_insti_amount(bad(stat="很抱歉，查無資料"), D(11, 5)) == []
    assert daily.parse_tpex_insti_amount(TPEX_1105, D(11, 4)) == []                      # 回應日期不是 d
    assert daily.parse_tpex_insti_amount(bad(tables=[]), D(11, 5)) == []                 # 休市：沒有表
    t = dict(TPEX_1105["tables"][0], fields=["單位名稱", "買進金額", "賣出金額", "買賣超"])
    assert daily.parse_tpex_insti_amount(bad(tables=[t]), D(11, 5)) == []                # 欄位改名
    t = dict(TPEX_1105["tables"][0], data=TPEX_1105["tables"][0]["data"][:-1])
    assert daily.parse_tpex_insti_amount(bad(tables=[t]), D(11, 5)) == []                # 6 個單位不齊


def test_f91_twse_rows_have_market():
    rows = daily.parse_insti_amount({
        "stat": "OK", "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"],
        "data": [["外資及陸資(不含外資自營商)", "1", "2", "-1"], ["合計", "1", "2", "-1"]]}, D(10, 30))
    assert {x["market"] for x in rows} == {"TWSE"} and {x["unit"] for x in rows} == {"foreign", "total"}


def test_f91_merge_sql_has_market():
    class Cur:
        sql = None

        def execute(self, sql, *p):
            Cur.sql, Cur.params = sql, p
    daily.merge_insti_amount(Cur(), daily.parse_tpex_insti_amount(TPEX_1105, D(11, 5)))
    assert "t.market = s.market" in Cur.sql and "INSERT (trade_date, market, unit" in Cur.sql
    assert '"market": "TPEx"' in Cur.params[0]


def test_f91_amount_by_market():
    rows = [(D(11, 5), "TWSE", "foreign", -102460621838), (D(11, 5), "TWSE", "total", -123390000000),
            (D(11, 5), "TPEx", "foreign", -1584109790), (D(11, 5), "TPEx", "total", -3850161562)]
    a = export.amount_by_market(rows)
    o = export._insti_official(a["TWSE"])
    assert o["foreign"] == -1024.6 and o["date"] == "2026-11-05"                         # 同一天、同一單位：上市不被上櫃覆蓋
    p = export._insti_official(a["TPEx"])
    assert p["foreign"] == -15.8 and p["total"] == -38.5
    assert export._insti_official(export.amount_by_market([])["TPEx"]) is None           # 還沒補抓：上櫃為 null


def test_f91_keys_and_spec():
    assert daily.DAY_KEYS.index("amount.TPEx") == daily.DAY_KEYS.index("amount") + 1
    assert daily.DATASET_KEYS[daily.AMOUNT] == ("amount", "amount.TPEx")
    assert health.SPEC["amount.TPEx"].since == D(7, 31) and health.SPEC["amount.TPEx"].min_rows == 6
    assert health.SPEC["amount"].since is None and health.SPEC["amount"].label == "上市法人金額"     # 上市一列不變
    assert history.SECONDS_PER_KEY["amount.TPEx"] == 3.2


def test_f91_collect_waits_for_tpex_prices():
    w = t3.World(D(11, 4))
    w.publish(D(11, 5), "dailyQuotes", "insti/summary")                 # 上櫃行情、上櫃法人金額都還沒有
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TPEx", "amount", "amount.TPEx"))
    assert written["prices.TPEx"] == 0 and "amount.TPEx" not in written and not errors
    assert t3._hit(w, "insti/summary") == [] and len(t3._hit(w, "BFI82U")) == 1            # 上市照舊不等行情
    w.published["dailyQuotes"].add(D(11, 5))
    w.published["insti/summary"].add(D(11, 5))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TPEx", "amount.TPEx"))
    assert written["amount.TPEx"] == 6 and w.rows["amount.TPEx"][D(11, 5)] == Row(6) and not errors
    assert w.rows["amount"][D(11, 5)] == Row(6)                                             # 上市列仍是 6，不是 12


def test_f91_history_only_amount_fills_tpex():
    w = t3.World(D(10, 30))
    for d in (D(10, 28), D(10, 29), D(10, 30)):
        w.rows["amount.TPEx"].pop(d)
        w.publish(d)
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        ok = history.run_history(D(10, 27), D(10, 30), datasets=("amount",), revenue=False)
    assert ok and len(t3._hit(w, "insti/summary")) == 3 and t3._hit(w, "BFI82U") == []     # 上市已齊：不重抓
    assert all(w.rows["amount.TPEx"][d] == Row(6) for d in (D(10, 28), D(10, 29), D(10, 30)))


def test_f91_check_rows():
    now = T(11, 5, 23)
    days = health.due_days(now, 20, CLOSED)
    snap = t3._full_snapshot(days, skip={("amount.TPEx", D(11, 4))})
    text, rc = health.check_report(days, snap, now, {"alerts_at": None, "revenue_on": None}, CLOSED)
    assert rc == 1 and "上櫃法人金額：缺 2026-11-04" in text
    line = next(ln for ln in text.splitlines() if ln.startswith("上市法人金額"))
    assert "      6      6" in line and "正常" in line                                       # 上市筆數、中位數仍為 6
    # 7/31 以前不判缺
    now = T(8, 5, 23)
    days = health.due_days(now, 10, CLOSED)
    snap = t3._full_snapshot(days, skip={("amount.TPEx", d) for d in days if d < D(7, 31)})
    items = [i for i in health.evaluate(days, snap, now) if i.key == "amount.TPEx"]
    assert {i.date for i in items} == {d for d in days if d >= D(7, 31)} and all(i.status == health.OK for i in items)


def test_f91_ddl_repeatable():
    ddl = "\n".join(db.DDL)
    i_add = ddl.index("IF COL_LENGTH('insti_amount', 'market') IS NULL")
    i_drop = ddl.index("ALTER TABLE insti_amount DROP CONSTRAINT UQ_insti_amount")
    i_new = ddl.index("ALTER TABLE insti_amount ADD CONSTRAINT UQ_insti_amount_market UNIQUE (trade_date, market, unit)")
    assert ddl.index("CREATE TABLE insti_amount") < i_add < i_drop < i_new                # 先加欄位、再刪舊鍵、最後建新鍵
    assert "IF EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount'" in ddl
    assert "IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'UQ_insti_amount_market'" in ddl
    assert "DEFAULT 'TWSE'" in ddl and "CONSTRAINT UQ_insti_amount UNIQUE (trade_date, unit)" not in ddl


def test_qa05_main_db_error():
    err = pyodbc.OperationalError("08001", "[08001] [Microsoft][ODBC Driver 18 for SQL Server]Login timeout expired (0) (SQLDriverConnect)")
    for argv, target in ((["export"], "twstock.export.export_all"),
                         (["history", "--start", "2026-10-30", "--end", "2026-10-30", "--only", "pe"], "twstock.db.acquire_lock")):
        buf = io.StringIO()
        with mock.patch(target, side_effect=err), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = cli.main(argv)
        assert rc == 2 and "連不上資料庫" in buf.getvalue() and "Traceback" not in buf.getvalue()


# ─── F9-2：月營收提前收集 ───────────────────────────────
def test_f92_revenue_month_for():
    for d in (D(11, 1), D(11, 5), D(11, 10), D(11, 30)):
        assert revenue.revenue_month_for(d) == (2026, 10)
    assert revenue.revenue_month_for(date(2027, 1, 3)) == (2026, 12)


STATE = {"alerts_at": datetime(2026, 11, 5, 19), "events_to": D(11, 5), "revenue_on": D(11, 4), "collected_at": None}


def _plan(now, counts, **st):
    days = health.due_days(now, 10, CLOSED)
    return catchup.make_plan(now, 10, t3._full_snapshot(days), dict(STATE, **st), CLOSED, counts)["revenue"]


def test_f92_make_plan():
    sep = {(2026, 8): 1983, (2026, 9): 1980}
    assert _plan(T(11, 5), sep) == [(2026, 10)]                                         # 10 月 0 家
    assert _plan(T(11, 5), {**sep, (2026, 10): 287}) == [(2026, 10)]                    # 287 < 1,940
    assert _plan(T(11, 5), {**sep, (2026, 10): 1945}) == []                             # ≥ 98%
    assert _plan(T(11, 5), {**sep, (2026, 10): 287}, revenue_on=D(11, 5)) == []         # 今天已收過
    assert _plan(T(11, 2), {**sep, (2026, 10): 0}) == [(2026, 10)]                      # 範圍含 10/30、11/02：9 月已齊，只排 10 月
    assert _plan(T(11, 2), {(2026, 8): 1983, (2026, 9): 1500}) == [(2026, 9), (2026, 10)]   # 上月沒齊：兩個月份分別判斷
    plan = catchup.plan_for_date(D(11, 2), T(11, 2), False)
    assert plan["revenue"] == [(2026, 10)]                                              # collect --date 月初也收上個月


def test_f92_header_only_csv():
    header = "出表日期,資料年月,公司代號,公司名稱,產業別,營業收入-當月營收,營業收入-上月營收,營業收入-去年當月營收," \
             "營業收入-上月比較增減(%),營業收入-去年同月增減(%),累計營業收入-當月累計營收,累計營業收入-去年累計營收,累計營業收入-前期比較增減(%),備註\r\n"
    resp = mock.Mock(content=("﻿" + header).encode("utf-8"))
    openapi = [{"資料年月": "11509", "公司代號": "2330"}]                                   # OpenAPI 仍是 9 月
    with mock.patch.object(revenue, "request", side_effect=[openapi, resp]):
        assert revenue.fetch_monthly_revenue("TWSE", 2026, 11) == {}
    # 0 家也算成功：revenue_on 記為當天，不是錯誤
    plan = {"by_date": [], "futures": None, "futures_oi": None, "tpex_months": [], "alerts": False, "events": None,
            "revenue": [(2026, 10)]}
    with mock.patch.object(catchup, "collect_monthly_revenue", lambda y, m: 0), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(11, 1, 17, 30))
    assert errors == {} and undated == {"revenue": "2026-11-01"}


def _rev(now, n10, revenue_on, n9=1980):
    return health.revenue_status(now.date(), {(2026, 9): n9, (2026, 10): n10}, revenue_on, CLOSED)


def test_f92_check_revenue():
    st, txt = _rev(T(11, 5), 287, D(11, 5))
    assert st == health.PENDING and txt == "月營收 2026/10：已收 287 家（前一月 1,980 家的 14%），⏳ 公布期間（每月 10 日前）"
    assert _rev(T(11, 2), 0, None)[0] == health.PENDING                                 # 月初 0 家、還沒收過
    assert _rev(T(11, 10), 1500, None)[0] == health.PENDING                             # 10 日當天仍是公布期間
    assert _rev(T(11, 12), 1945, D(11, 12))[0] == health.OK
    assert _rev(T(11, 13), 1500, D(11, 12))[0] == health.PENDING                        # 前一個交易日有收
    assert _rev(T(11, 16), 1500, D(11, 13))[0] == health.PENDING                        # 週一：前一個交易日是週五
    st, txt = _rev(T(11, 13), 1500, D(11, 9))
    assert st == health.ABNORMAL and "最後一次收集營收 2026-11-09" in txt
    assert health.revenue_status(date(2027, 1, 3), {(2026, 11): 1980, (2026, 12): 10}, None, CLOSED)[1].startswith("月營收 2026/12")
    # check_report：⏳ 不計入異常；❌ 計入並附建議指令
    now = T(11, 13, 23)
    days = health.due_days(now, 20, CLOSED)
    full = t3._full_snapshot(days)
    counts = {(2026, 9): 1980, (2026, 10): 1500}
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "revenue_on": D(11, 12)}, CLOSED, revenue=counts)
    assert rc == 0 and "⏳ 晚交公司陸續補進" in text and "無異常" in text
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "revenue_on": D(11, 9)}, CLOSED, revenue=counts)
    assert rc == 1 and "異常 1 項" in text and "collect --catch-up" in text
    text, rc = health.check_report(days, full, T(11, 5, 23), {"alerts_at": None, "revenue_on": None}, CLOSED,
                                   revenue={(2026, 9): 1980, (2026, 10): 287})
    assert rc == 0 and "公布期間" in text
    assert "月營收" not in health.check_report(days, full, now, {"alerts_at": None}, CLOSED)[0]   # 舊呼叫方式不印


def test_f92_month_requests():
    """一個完整月份（11/01～11/30，每天 18:00 跑一次 catch-up）：只在未達 98% 的日子排入營收，每天最多一次（2 市場 × 2 個請求）。"""
    published = lambda day: min(1980, 52 if day <= 4 else 287 if day == 5 else 287 + (day - 5) * 300)   # 前一晚收到的家數
    planned = []
    for day in range(1, 31):
        now = T(11, day)
        counts = {(2026, 8): 1983, (2026, 9): 1980, (2026, 10): published(day - 1) if day > 1 else 0}
        got = _plan(now, counts, revenue_on=now.date() - timedelta(days=1))
        assert got in ([], [(2026, 10)])
        if got:
            planned.append(day)
        assert _plan(now, counts, revenue_on=now.date()) == []                         # 同一天第二次不排
    # 11/01 是週日：評估範圍（交易日）都在 10 月，月份只有 9 月（已齊）→ 從 11/02（第一個交易日）開始；11/12 起已達 1,980
    assert planned == list(range(2, 12)) and len(planned) * 4 == 40


# ─── F9-3：個股 margin.m5 換算 ──────────────────────────
def test_f93_stock_margin_conv():
    # 寶雅 5904：8/10 面額 10 元改 1 元（上櫃反推「調」事件，參考價 72、前收 720）；官方 8/10 前日餘額 5,940 = 8/7 594 × 10
    ds = [D(8, 4), D(8, 5), D(8, 6), D(8, 7), D(8, 10), D(8, 11)]
    rows = {d: (594, 594, 0, 0, 0, None) for d in ds[:4]}
    rows[D(8, 10)] = (5940, 5935, 0, 0, 0, None)
    rows[D(8, 11)] = (5935, 5930, 0, 0, 0, None)
    ev = [{"d": "2026-08-10", "t": "調", "p": 720.0, "r": 72.0}]
    conv = export.margin_conv(rows, ev)
    assert conv == [{"d": "2026-08-10", "k": 10.0, "t": "調"}]
    m = export.stock_margin(rows, D(8, 11), D(8, 4), conv)
    assert m["m5"] == 5930 - 5940 == export.screen_margin(rows, D(8, 11), D(8, 4), conv, "TPEx")["m5"]
    assert export.stock_margin(rows, D(8, 11), D(8, 4))["m5"] == 5930 - 594          # 不傳 conv：舊行為（原始相減）
    assert export.stock_margin(rows, D(8, 11), D(8, 10), conv)["m5"] == 5930 - 5935    # 基期在換算之後：不乘係數


# ─── F9-4：估值一年位置 ─────────────────────────────────
def test_f94_position():
    assert export.position([1, 2, 3, 4], 1) == 25.0 and export.position([1, 2, 3, 4], 4) == 100.0
    assert export.position([5, 5, 5], 5) == 100.0                                       # 全部相同 → 100%
    assert export.position([], 5) is None and export.position([1, 2], None) is None


def test_f94_market_valuation():
    days = [D(11, 3), D(11, 4), D(11, 5)]
    rows = []
    for i, d in enumerate(days):
        rows += [(d, "TWSE", 10.0 + i, 1.0, 0.0), (d, "TWSE", 20.0 - i, 2.0, 2.0), (d, "TWSE", None, -1.0, 4.0),   # 虧損：pe null
                 (d, "TWSE", 0.0, 3.0, 6.0)]                                                                     # pe 0 不計入
    rows.append((D(11, 2), "TWSE", 99.0, 9.0, 9.0))                                       # 窗口外
    v = export.market_valuation(rows, days)["TWSE"]
    assert v["d"] == "2026-11-05" and v["from"] == "2026-11-03" and v["days"] == 3 and v["n"] == 2
    assert v["pe"] == {"v": 15.0, "p": 100.0, "lo": 15.0, "hi": 15.0}                     # 中位數每天都是 15
    assert v["pb"] == {"v": 2.0, "p": 100.0, "lo": 2.0, "hi": 2.0}                        # 淨值比 ≤ 0 不計入
    assert v["dy"] == {"v": 3.0, "p": 100.0, "lo": 3.0, "hi": 3.0}                        # 殖利率 0 計入
    assert v["s"] == [15.0, 15.0, 15.0] and v["sf"] == "2026-11-03"
    rows2 = [(d, "TPEx", p, 1.0, 1.0) for d, p in zip(days, (30.0, 20.0, 10.0))]
    t = export.market_valuation(rows2, days)["TPEx"]
    assert t["pe"]["p"] == 33.3 and t["pe"]["lo"] == 10.0 and t["pe"]["hi"] == 30.0      # 一年最低：1/3
    assert export.market_valuation([], days) == {}


def test_f94_stock_valuation():
    n = export.VAL_MIN
    s = {"pe": [10.0 + i for i in range(n)], "pb": [1.0] * n, "dy": [3.0] * (n - 1)}
    v = export.stock_valuation(s, {"pe": 10.0 + n - 1, "pb": 1.0, "dy": 3.0})
    assert v == {"pe": [100, 10.0, 10.0 + n - 1], "pb": [100, 1.0, 1.0]}                 # 殖利率有效天數不足 → 不輸出
    assert export.stock_valuation(s, {"pe": None, "pb": 1.0, "dy": 0.0}) == {"pb": [100, 1.0, 1.0]}   # 虧損、無股利
    assert export.stock_valuation(s, {"pe": 10.0}) == {"pe": [1, 10.0, 10.0 + n - 1]}   # 一年最低：1/120 → 1%
    assert export.stock_valuation({}, {"pe": 10.0}) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

## 附錄 G：`logs/iter09_compare.py`（新檔，取代 `iter08_compare.py` 用於本輪）

```python
# 用法：python3 logs/iter09_compare.py 基線資料夾 site/data [--keep-new] —— 隔離比對（第 9 輪，取代 iter08_compare.py）
# 除了第 9 輪指定的新鍵與「時間」欄位以外必須完全相同；比對 latest.json、screen.json、stocks/*.json、etfs/*.json。
# 新鍵：latest.json 的 insti_official_tpex、valuation、status.datasets 中 k = amount.TPEx 的一項；stocks/*.json 的 val；screen.json 的 pbp。
# margin.m5：只在 mg.k 有最近 5 個交易日內的換算時允許不同（P23），列出代號；其他不同一律算失敗。
# insti_official 另外逐欄比對（必須只來自上市）。--keep-new：不剔除新鍵（反證用，應判定不同）。相同印「✅ 相同」rc=0，否則 rc=1。
import json, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
KEEP = "--keep-new" in sys.argv
NEW_LATEST = set() if KEEP else {"insti_official_tpex", "valuation"}
NEW_STATUS_K = set() if KEEP else {"amount.TPEx"}
NEW_STOCK = set() if KEEP else {"val"}
NEW_SCREEN = set() if KEEP else {"pbp"}
TIME_LATEST, TIME_STATUS = {"updated_at"}, {"exported_at", "collected_at"}
bad, m5_conv = [], []
drop = lambda d, keys: {k: v for k, v in d.items() if k not in keys}
load = lambda p: json.loads(p.read_text(encoding="utf-8"))


def cmp_latest(A, B):
    B = drop(B, NEW_LATEST)
    if set(A) != set(B):
        bad.append(f"latest.json 鍵不同：{sorted(set(A) ^ set(B))}")
    for k in set(A) & set(B):
        if k in TIME_LATEST:
            continue
        x, y = A[k], B[k]
        if k == "status":
            x, y = drop(x, TIME_STATUS), drop(y, TIME_STATUS)
            y = {**y, "datasets": [i for i in y["datasets"] if i["k"] not in NEW_STATUS_K]}
        if x != y:
            bad.append(f"latest.json {k}")


def cmp_stock(f, x, y):
    y = drop(y, NEW_STOCK)
    if x == y:
        return
    mx, my = x.get("margin"), y.get("margin")
    if mx and my and drop(x, {"margin"}) == drop(y, {"margin"}) and drop(mx, {"m5"}) == drop(my, {"m5"}):
        recent = set(y["prices"]["d"][-5:])
        if any(c["d"] in recent for c in (y.get("mg") or {}).get("k", [])):
            m5_conv.append(f"{f[:-5]}（{mx['m5']} → {my['m5']}）")
            return
    bad.append(f"stocks/{f}")


LA, LB = load(a / "latest.json"), load(b / "latest.json")
cmp_latest(LA, LB)
if LA.get("insti_official") != LB.get("insti_official"):
    bad.append("insti_official 的值改變（必須只來自上市列）")
SA, SB = load(a / "screen.json"), load(b / "screen.json")
if SA != drop(SB, NEW_SCREEN):
    bad.append("screen.json")
n = {}
for sub in ("stocks", "etfs"):
    fa = {f.name for f in (a / sub).glob("*.json")}
    fb = {f.name for f in (b / sub).glob("*.json")}
    if fa != fb:
        bad.append(f"{sub} 檔案不同：少 {sorted(fa - fb)[:5]} 多 {sorted(fb - fa)[:5]}")
    for f in sorted(fa & fb):
        x, y = load(a / sub / f), load(b / sub / f)
        if sub == "stocks":
            cmp_stock(f, x, y)
        elif x != y:
            bad.append(f"{sub}/{f}")
    n[sub] = len(fa)
print(f"比對 latest.json、screen.json、stocks {n['stocks']} 檔、etfs {n['etfs']} 檔（略過 {sorted(TIME_LATEST)}、status.{sorted(TIME_STATUS)}"
      + ("" if KEEP else "；剔除新鍵 insti_official_tpex、valuation、status 的 amount.TPEx、stocks 的 val、screen 的 pbp") + "）")
if m5_conv:
    print(f"ℹ️  margin.m5 因換算不同 {len(m5_conv)} 檔（允許）：" + "、".join(m5_conv[:20]))
if bad:
    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
    sys.exit(1)
print("✅ 相同")
```

## 附錄 H：`logs/iter09_recalc.py`（新檔，QA 獨立重算）

```python
# 用法：python3 logs/iter09_recalc.py [資料夾，預設 site/data] —— 第 9 輪 QA 獨立重算（只讀資料庫，不寫入）
# 1. 法人金額：以 SQL 從 insti_amount 分市場重算最新一天與 20 日外資序列，比對 latest.json 的 insti_official（上市）、insti_official_tpex（上櫃）。
# 2. 市場估值：以 SQL（PERCENTILE_CONT）重算窗口內每日中位數與位置，比對 latest.json 的 valuation。
# 3. 個股估值：以 SQL 重算每檔的位置與區間，比對 stocks/*.json 的 val（cap = 1 的股票必須沒有 val）與 screen.json 的 pbp。
# 4. margin.m5：stocks/*.json 與 screen.json 逐檔一致。5. 月營收各月份家數（check 的營收一行用）。
# 聚合（中位數、計數、區間）全部在 SQL；最後的百分比與四捨五入用和匯出相同的 Python 式子。全部相同印「✅ 相同」rc=0，否則列出不同 rc=1。
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from twstock.db import connect  # noqa: E402

base = Path(sys.argv[1] if len(sys.argv) > 1 else "site/data")
L = json.loads((base / "latest.json").read_text(encoding="utf-8"))
S = json.loads((base / "screen.json").read_text(encoding="utf-8"))
cur = connect().cursor()
bad = []

# 1. 法人金額（億，1 位）
for m, key in (("TWSE", "insti_official"), ("TPEx", "insti_official_tpex")):
    rows = cur.execute("""
        SELECT TOP 20 trade_date, SUM(CASE WHEN unit = 'foreign' THEN net_amount END), SUM(CASE WHEN unit = 'trust' THEN net_amount END),
               SUM(CASE WHEN unit IN ('dealer_self', 'dealer_hedge') THEN net_amount END), SUM(CASE WHEN unit = 'total' THEN net_amount END)
        FROM insti_amount WHERE market = ? GROUP BY trade_date HAVING SUM(CASE WHEN unit = 'total' THEN 1 END) = 1
        ORDER BY trade_date DESC""", m).fetchall()[::-1]
    O = L.get(key)
    if not rows:
        if O is not None:
            bad.append(f"{key} 應為 null")
        continue
    yi = lambda v: round((v or 0) / 1e8, 1)
    d, f, t, dl, tot = rows[-1]
    want = {"date": str(d), "foreign": yi(f), "trust": yi(t), "dealer": yi(dl), "total": yi(tot),
            "d": [str(r[0]) for r in rows], "f": [yi(r[1]) for r in rows], "t": [yi(r[4]) for r in rows]}
    got = {k: O.get(k) for k in want} if O else None
    print(f"{m} {d}：外資 {want['foreign']}、投信 {want['trust']}、自營 {want['dealer']}、合計 {want['total']} 億")
    if got != want:
        bad.append(f"{key}：{ {k: (got or {}).get(k) for k in want if (got or {}).get(k) != want[k]} }")

# 2. 市場估值
WIN = "SELECT DISTINCT TOP 242 trade_date FROM stock_fundamentals ORDER BY trade_date DESC"
first, last = cur.execute(f"SELECT MIN(trade_date), MAX(trade_date) FROM ({WIN}) w").fetchone()
for col, cond in (("pe", "f.pe_ratio > 0"), ("pb", "f.pb_ratio > 0"), ("dy", "f.dividend_yield IS NOT NULL")):
    src = {"pe": "f.pe_ratio", "pb": "f.pb_ratio", "dy": "f.dividend_yield"}[col]
    rows = cur.execute(f"""
        WITH m AS (
            SELECT DISTINCT f.trade_date, s.market_type,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {src}) OVER (PARTITION BY f.trade_date, s.market_type) AS med,
                   COUNT(*) OVER (PARTITION BY f.trade_date, s.market_type) AS n
            FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
            WHERE {cond} AND f.trade_date BETWEEN ? AND ?)
        SELECT m.market_type, m.med, m.n, (SELECT MIN(med) FROM m x WHERE x.market_type = m.market_type),
               (SELECT MAX(med) FROM m x WHERE x.market_type = m.market_type),
               (SELECT COUNT(*) FROM m x WHERE x.market_type = m.market_type AND x.med <= m.med),
               (SELECT COUNT(*) FROM m x WHERE x.market_type = m.market_type)
        FROM m WHERE m.trade_date = ?""", first, last, last).fetchall()
    for mk, med, n, lo, hi, le, days in rows:
        V = ((L.get("valuation") or {}).get(mk) or {}).get(col) or {}
        want = {"v": round(med, 2), "p": round(le / days * 100, 1), "lo": round(lo, 2), "hi": round(hi, 2)}   # 四捨五入方式與匯出相同
        print(f"{mk} {col} {last}：中位數 {want['v']}（{want['lo']}～{want['hi']}；位置 {want['p']}%）" + (f"，計入 {n} 檔" if col == "pe" else ""))
        if V != want:
            bad.append(f"valuation.{mk}.{col}：網站 {V}，SQL {want}")
        if col == "pe" and L["valuation"][mk]["n"] != n:
            bad.append(f"valuation.{mk}.n：網站 {L['valuation'][mk]['n']}，SQL {n}")

# 3. 個股估值（窗口內 > 0 的值；今天值 > 0、有效天數 ≥ 120）
want = {}
for col in ("pe_ratio", "pb_ratio", "dividend_yield"):
    k = {"pe_ratio": "pe", "pb_ratio": "pb", "dividend_yield": "dy"}[col]
    for code, n, le, lo, hi in cur.execute(f"""
        SELECT s.stock_code, COUNT(*), SUM(CASE WHEN f.{col} <= t.{col} THEN 1 ELSE 0 END), MIN(f.{col}), MAX(f.{col})
        FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
        JOIN stock_fundamentals t ON t.stock_id = f.stock_id AND t.trade_date = ? AND t.{col} > 0
        WHERE f.trade_date BETWEEN ? AND ? AND f.{col} > 0 GROUP BY s.stock_code HAVING COUNT(*) >= 120""", last, first, last):
        want.setdefault(code, {})[k] = [round(le / n * 100), round(float(lo), 2), round(float(hi), 2)]
pbp = dict(zip(S["codes"], S.get("pbp", [])))
n_val = n_cap = 0
for f in sorted((base / "stocks").glob("*.json")):
    J = json.loads(f.read_text(encoding="utf-8"))
    code, val = J["code"], J.get("val")
    if J.get("capchg"):
        n_cap += 1
        if val:
            bad.append(f"{code} 股本變動卻有 val")
        continue
    w = want.get(code)
    got = {k: v for k, v in (val or {}).items() if k != "d"} or None
    if got != w:
        bad.append(f"{code} val：網站 {got}，SQL {w}")
    n_val += bool(val)
    if code in pbp and pbp[code] != (w or {}).get("pb", [None])[0]:
        bad.append(f"{code} pbp：screen {pbp[code]}，SQL {(w or {}).get('pb')}")
print(f"個股估值：有 val {n_val} 檔、股本變動不輸出 {n_cap} 檔（窗口 {first}～{last}）")
for code in ("2330", "2317", "2412", "2603", "5314"):
    print(f"  {code}：{want.get(code)}")

# 4. margin.m5 一致
m5 = dict(zip(S["codes"], S["m5"]))
diff = []
for f in (base / "stocks").glob("*.json"):
    J = json.loads(f.read_text(encoding="utf-8"))
    if J.get("margin") and J["code"] in m5 and J["margin"]["m5"] != m5[J["code"]]:
        diff.append(J["code"])
print(f"margin.m5 與 screen.json 不同：{len(diff)} 檔 {diff[:10]}")
if diff:
    bad.append("margin.m5 不一致：" + "、".join(diff[:10]))

# 5. 月營收家數
rev = cur.execute("SELECT TOP 3 revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month "
                  "ORDER BY revenue_year DESC, revenue_month DESC").fetchall()
print("月營收家數（最近 3 個月）：" + "、".join(f"{y}/{m:02d} {n:,} 家" for y, m, n in rev) + f"；screen.json rmd = {S['rmd']}")

if bad:
    print(f"❌ 不同 {len(bad)} 處：\n  " + "\n  ".join(bad[:30]))
    sys.exit(1)
print("✅ 相同")
```
