# 第 10 輪｜System Analyst：設計規格

- 撰寫日期：2026-11-06
- 輸入：`10/01-analyst.md`、`10/02-pm.md`（範圍 F10-1～F10-3；**使用者已決定 D17 = B，D18 依預設 A**）、`09/03-design.md`（格式）。
- 依據：現行程式 `twstock/`（`__main__.py`、`db.py`、`export.py`、`health.py`、`fetch.py`、`collectors/revenue.py`、`daily.py`、`history.py`、`catchup.py`）、`site/app.js`、`site/stock.js`、`site/app.css`、README、`tests/test_iter01～09.py`、`logs/iter09_compare.py`、`logs/iter09_recalc.py`。
- 開工前確認（PM 第五節第 1 點）：**3 次外部請求**，全部經過 `twstock/fetch.request(..., isolated=True)`，不重試；原始回應存在 scratchpad `r10/sa/`（結果見 1-2）。分析師的原始回應 `r10/raw/t163sb04_sii_115_02.html` 優先使用，沒有重抓。
- 原型驗證（全部在 scratchpad，不寫專案資料庫、不改專案程式）：
  - 把 `twstock/`、`site/`、`tests/`、`scripts/`、`data/`、`logs/iter09_*` 複製成 `orig/`（基線）與 `proj/`（原型），在 `proj/` 實作本文全部修改。差異見附錄 C～E。
  - `test_iter01～10` 在原型上全部通過。反證：`test_iter10.py` 放到舊程式上匯入即失敗（沒有 `collectors/financials.py`）；舊程式在「上市行情 0 列」時仍會呼叫 BFI82U 1 次。
  - 匯出：以真實資料庫**唯讀**連線執行原型的 `export_all`（寫到 scratchpad）。`quarterly_financials` 還不存在，`--sim` 改以 4 份 mopsov 真實回應（115Q2 上市、上櫃，115Q3 上市，113Q1 上市）加上**合成**的其餘季別注入 `_load_financials`，沒有寫入資料庫。
  - 隔離比對（附錄 G `iter10_compare.py`）判定「✅ 相同」，`--keep-new` 判定不同（反證）。SQL 獨立重算（附錄 H `iter10_recalc.py`）以 sqlite 裝入同一份模擬資料執行，判定「✅ 相同」；竄改 1 檔 `fin` 與 1 檔 `screen.ey` 後判定 4 處不同（反證）。
  - 前端：原型匯出＋原型 `site/` 以 **8001** 埠預覽，375 px 檢查 `#/stock/2408`、`2303`、`2881`、`1805`（負 EPS）、`#/rank/screen`、今日頁；沒有水平捲動，主控台沒有錯誤。
  - **DDL 與 MERGE 沒有在任何資料庫上執行過**（不可寫入專案資料庫），交給 PG 依第四節步驟 4、5 驗證。
- 實測發現：
  1. **個體報表的淨利**：115Q2 上市有 74 家「淨利（淨損）歸屬於母公司業主」是 `--`（沒有子公司），本期淨利就是歸屬母公司的淨利，改取「本期淨利（淨損）」或「本期稅後淨利（淨損）」。EPS 不受影響。
  2. **上櫃只有 2 張表**（115Q2：證券 7、一般業 889，共 896 家），表頭與上市完全相同；115Q2 上市＋上櫃合計 **1,984** 家。
  3. **115Q3 上市 11/06 23:14 已有 231 家**（銀行 1、一般業 230），比當天 OpenAPI 的 158 家多；158 家的 EPS 全部一致，南亞科 2408 為 **49.28**。台積電 2330、富邦金 2881 尚未公布。
  4. **113 年欄名和 115 年相同**，只有保險業不同：113 年（IFRS 17 之前）有「營業收入」「營業成本」「營業利益」，EPS 欄名是「基本每股盈餘（元）」；仍可依表頭特徵辨識為保險業（1-3）。
  5. **截止日以 mopsov 註 1 核對**：Q2 的銀行、證券、保險截止日也是 **8/31**（不是 8/14）。因此「只看金控」不夠，提前結束與 `check` 一律改看「金融業（金控、銀行、證券、保險）」（第十二節 #1）。
  6. 4 份回應的公司代號全部在 `stocks` 裡，市場別也一致（上市回應的公司都是 `TWSE`，上櫃都是 `TPEx`）。
  7. `stock_fundamentals.eps` 全部是 NULL（0 列有值），README 註明「未使用」。
  8. 匯出 18.5 秒 → 18.5～18.9 秒（模擬資料，`quarterly_financials` 約 2.2 萬列，讀取不到 0.5 秒）。

---

## 〇、變更總覽

| 檔案 | F10-1 季 EPS 收集、`check`、季報卡 | F10-2 選股、今日頁 | F10-3 小修 | 原型行數（+/−，約） |
|---|---|---|---|---|
| `twstock/db.py` | 新表 `quarterly_financials`、setup 訊息 | | | +23 / −1 |
| `twstock/collectors/financials.py`（新） | 解析、抓取、MERGE、收集一季 | | | 129 行 |
| `twstock/collectors/catchup.py` | `make_plan`、`plan_for_date` 排入季報；`execute_plan` 收集並記 `financials_on` | | | +23 / −12 |
| `twstock/collectors/history.py` | `--only financials`：`fin_quarters`、`run_financials` | | | +44 / −1 |
| `twstock/collectors/daily.py` | | | 上市 `amount` 行情保護 | +3 / −2 |
| `twstock/health.py` | 窗口、截止日、`fin_done`、`financials_status`、`financial_counts`、`check_report(financials=)` | | | +81 / −6 |
| `twstock/export.py` | `fin_single`、`fin_yoy`、`fin_margin`、`fin_e4`、`fin_stock`、`_load_financials`、`stocks` 的 `fin` | `fin_screen`、`fqd`、`fin_progress` | | +96 / −6 |
| `twstock/__main__.py` | docstring、`--only` 的 `choices`、說明 | | | +7 / −5 |
| `site/stock.js` | 季報卡、獲利說明一行 | | 估值說明定稿、淨值比卡日期 | +36 / −4 |
| `site/app.js` | | 選股欄與條件、預設組合、季別混雜、今日頁一行 | | +29 / −8 |
| `site/app.css` | 季報柱狀圖 | | | +8 |
| `tests/test_iter03.py`、`test_iter08.py` | 假資料庫補季報家數；`fqd` | | | +3、+1 / −1 |
| `tests/test_iter10.py`（新）、`tests/fixtures/`（新，4 檔） | ✓ | ✓ | ✓ | 370 行；75 KB |
| `logs/iter10_compare.py`、`logs/iter10_recalc.py`（新） | ✓ | ✓ | ✓ | 54、120 行 |
| README | ✓ | ✓ | （不需要） | 見第十節 |

- 合計：程式約 +350 行（PM 估約 390），測試約 320 行。
- **外部請求**：SA 3 次（已完成）；PG 補抓 **22 次**；日常只在季報窗口內每天最多 2 次。

### 建議實作順序（細節見第四節）

| 步驟 | 內容 | 驗證 | 失敗時 |
|---|---|---|---|
| 0 | `backup` | 記錄指令、時間、檔名、大小 | 停，不改任何程式 |
| 1 | 舊程式 `export` → `logs/iter10_before/`；既有表列數快照 | 檔案存在；列數存檔 | 停 |
| 2 | F10-3（`daily.py`、`stock.js` 的淨值比卡與說明文字） | `test_iter01～09` 全過 | 修到過為止 |
| 3 | F10-1、F10-2 全部程式與測試（**只跑 mock，不連資料庫**） | `test_iter01～10` 全過 | 修到過為止，不往下 |
| 4 | `setup-db` 兩次（建新表） | 4-2 SQL：新表存在、既有表列數不變 | 停，交使用者決定是否還原 |
| 5 | `history --start 2024-01-01 --only financials`（補抓 22 次） | 計畫 22 次；每季每市場家數；重跑 0 次 | 停，保留紀錄 |
| 6 | `export` → `iter10_compare` → `iter10_recalc` → `check` | 兩個工具都「✅ 相同」；`check` 季報一行 | 停，不更新網站 |
| 7 | README、`__main__.py`；8001 埠預覽 | 375 px、主控台 | 修到過為止 |

---

## 一、資料來源與解析（F10-1）

### 1-1 端點與參數

- `POST https://mopsov.twse.com.tw/mops/web/ajax_t163sb04`（舊版公開資訊觀測站「綜合損益表彙總」）。
- 表單參數：`encodeURIComponent=1`、`step=1`、`firstin=1`、`off=1`、`isQuery=Y`、`TYPEK=sii`（上市）或 `otc`（上櫃）、`year=民國年`（西元 − 1911）、`season=01～04`（`04` = 全年）。
- 經過 `fetch.request("POST", URL, expect_json=False, data=…)`：mopsov 主機已有節流（3 秒），和月營收共用。回應以 UTF-8 解碼（`errors="replace"`）。
- 一個回應 = 一個市場、一季、全部業別（每個業別一張 `<table class='hasBorder'>`）。金額是**年初至今累計**，單位千元；EPS 單位元。數字有千分位逗號，空值是 `--`（`fetch.clean_number` 已處理）。
- 新檔 `twstock/collectors/financials.py`（全文見附錄 C）：`parse_financials(text)`、`fetch_financials(market, year, quarter)`、`merge_financials(cursor, year, quarter, rows, first_seen)`、`collect_financials(year, quarter, first_seen=None, markets=("TWSE","TPEx"))`。

### 1-2 開工前確認（3 次請求，2026-11-06）

| 時間 | 請求 | 狀態 | 大小 | 結果 |
|---|---|---|---|---|
| 23:14:33 | `otc` 115 `02` | 200 | 1,337,493 B | 上櫃格式和上市相同；只有 2 張表（證券 7、一般業 889），共 **896** 家（PM 預期 850～900） |
| 23:14:34 | `sii` 115 `03` | 200 | 358,016 B | **231** 家（銀行 1、一般業 230），多於 OpenAPI 158 家；158 家 EPS 全部相同；2408 = **49.28** |
| 23:14:36 | `sii` 113 `01` | 200 | 1,536,766 B | 1,026 家；欄名和 115 年相同，只有保險業不同（見實測發現 #4） |

- 原始回應：scratchpad `r10/sa/t163sb04_otc_115_02.html`、`t163sb04_sii_115_03.html`、`t163sb04_sii_113_01.html`；紀錄 `r10/sa/probe_sa.log`。
- #2 沒有落後 OpenAPI，不需要回報 PM。

### 1-3 業別辨識（依表頭特徵，不依賴表的順序）

由上往下取第一個「需要的欄全部存在」的業別；6 種都認不出 → `SchemaError`。

| `industry_tbl` | 業別 | 辨識欄（全部要有） | 115Q2 上市家數 | 備註 |
|---|---|---|---|---|
| `ci` | 一般業 | 營業毛利（毛損）淨額 | 1,053 | 上櫃 889 |
| `fh` | 金控 | 淨收益 | 13 | 也有「利息淨收益」，所以排在銀行之前 |
| `basi` | 銀行 | 利息淨收益 | 10 | |
| `bd` | 證券 | 收益、支出及費用 | 3 | 上櫃 7 |
| `ins` | 保險 | 繼續營業單位稅前純益（純損） | 5 | 113 年也有營業收入，但沒有「營業毛利（毛損）淨額」，不會被認成一般業 |
| `mim` | 其他 | 收入、支出 | 4 | |

- 115Q2 上市完整檔（`r10/raw/t163sb04_sii_115_02.html`）原型解析為 1,088 家，各業別家數和 PM 驗收 #3 相同。
- 「金融業」= `fh`、`basi`、`bd`、`ins`（`FIN_TBLS`）：沒有毛利；提前結束收集要等金融業收齊。115Q2 金融業共 38 家（上市 31、上櫃 7）。

### 1-4 欄位對應

| 欄 | 來源欄（依序取第一個存在的） | 沒有時 |
|---|---|---|
| `revenue` | 營業收入 → 淨收益（金控）→ 收益（證券）→ 收入（其他） | NULL：銀行沒有合計欄；115 年起保險沒有收入欄。**不自行加總** |
| `gross_profit` | 營業毛利（毛損）淨額 | NULL：只有一般業有 |
| `op_income` | 營業利益（損失）→ 營業利益 | NULL：金控、銀行、其他 |
| `net_income` | 「淨利」開頭、「歸屬於母公司業主」結尾的欄；值是 `--` 時改取「本期淨利（淨損）」或「本期稅後淨利（淨損）」 | NULL |
| `eps` | 「基本每股盈餘」開頭的欄（保險業 115 年沒有「（元）」） | 欄不存在 → `SchemaError` |

- 必要欄：「公司代號」（表頭原文是「公司<br>代號」，去掉標籤後比對）、「基本每股盈餘…」、「淨利…歸屬於母公司業主」。缺任一 → `SchemaError`，**整個回應都不寫入**。
- 欄數和表頭不同的列、分頁重複的表頭列（第一格是「公司代號」）略過。

### 1-5 年度與季別

- 資料庫一律用**西元年**（`fin_year`），`fin_quarter` 1～4；請求時才換成民國年、`season=0Q`。
- Q4 = `season=04` 的**全年累計**（年報）。Q4 的窗口在次年 1/15～4/07，季別是「前一年 Q4」。

### 1-6 上市與上櫃的差異

| 項目 | 上市 | 上櫃 |
|---|---|---|
| `TYPEK` | `sii` | `otc` |
| 表數（115Q2） | 6 | 2（證券、一般業） |
| 表頭 | 相同 | 相同 |
| 市場別 | 不從回應判斷，以 `stocks.market_type` 為準（家數、`fin_progress` 都用 `stocks` 的市場別） | 同左 |

### 1-7 錯誤與 0 家

| 回應 | 行為 |
|---|---|
| 沒有任何 `hasBorder` 表，但有「上市（上櫃）公司…資料」的 `<h2>` 標題或「查無」字樣 | 回傳 `{}`（0 家，還沒有公司公布），**不是錯誤** |
| 沒有表、內容含 `SECURITY`（封鎖頁，沿用 `revenue.py` 的判斷） | `FetchError` |
| 沒有表、也不是上面兩種 | `SchemaError` |
| 有表，但認不出業別或缺必要欄 | `SchemaError`，不寫入 |
| HTTP 錯誤、逾時 | 由 `fetch.request` 照現行規則處理 |

- 「無資料頁」的實際格式**沒有實測到**（3 次請求都有資料）。若 PG 或使用者日後遇到 0 家卻丟 `SchemaError`，把回應存檔交給 SA，補一個判斷字串即可（不影響已寫入的資料）。

### 1-8 單季相減、年增與比率（匯出時計算；個股與選股共用同一組函式）

| 項目 | 定義 | null 規則 |
|---|---|---|
| 單季（營收、毛利、營益、淨利、EPS） | Q1 = Q1 累計；Q2～Q4 = 本季累計 − **同年**上一季累計（Q4 = 全年 − Q3 累計） | 上一季缺 → 該季**全部欄** null（不以累計頂替）；某欄任一邊 NULL → 該欄 null |
| 單季 EPS 年增 % | (本季單季 − 去年同季單季) ÷ 去年同季單季 × 100 | 去年同季 ≤ 0 或缺 → null（畫面：本季 > 0 寫「轉盈」，其餘 `--`） |
| 累計 EPS 年增 % | 同上，用累計 | 同上 |
| 毛利率、營益率 % | 單季毛利（營益）÷ 單季營收 × 100 | 單季營收 ≤ 0 或缺 → null；金融業沒有毛利 → null |
| 毛利率年增（百分點） | 本季毛利率 − 去年同季毛利率 | 任一 null → null |
| 近 4 季 EPS | Q1～Q3：本季累計 + 去年 Q4 累計 − 去年同季累計；Q4：全年累計 | 四項（Q4 為一項）缺一 → null |
| 一年前的近 4 季 | 同上，往前推一年 | 同上 |
| 創 N 季新高（`eh`） | 最新一季單季 EPS **嚴格高於**之前連續幾季的單季 EPS（遇到缺季或不高於就停） | 最新一季單季 EPS null → 0 |

- **數值**：EPS 在資料庫是 `DECIMAL(10,2)`，讀出為 `Decimal`，相減不會有浮點誤差（例如 49.28 − 23.38 = 25.90）；輸出時轉成 2 位小數。百分比用 `Decimal` 計算後 **ROUND_HALF_UP** 到 1 位（`_r1`），不用 Python `round`（PM 第五節第 4 點：避免 17.575 → 17.57 的情況）。毛利率年增 = 兩個 1 位小數相減後取 1 位。
- 口徑：期中有增資或減資時，相減的單季 EPS 和公司公告的單季 EPS 會有小差異（加權股數不同），畫面口徑說明寫明。

### 1-9 缺季與重編（更正）

- **缺季**：季報卡的近 8 季只列有累計值的季別；某季缺 → 該季不出現；它的下一季因為「上一季缺」單季為 null（柱狀圖畫灰色空柱、數字 `--`）。近 4 季 EPS 缺任一項為 null，「獲利說明一行」不出現。
- **新上市**：只有上市後的季別；第一季因為上一季缺而單季 null，近 4 季 null。不會用累計頂替。
- **更正（重編）**：日常收集在窗口內每天重抓整季，MERGE 只在值不同時更新（`updated_at`），`first_seen` 不動。窗口外的更正用 `history --start … --only financials --force` 重抓（每季 2 次）。去年的累計值被更正時，今年的年增與近 4 季在下一次匯出自動跟著變（不存單季值的理由）。
- **已知限制**：`collect --catch-up` 判斷「有沒有新資料要匯出」只看各表 `COUNT(*)`，只有更正、沒有新增公司的那一次不會觸發匯出；下一次有新資料或手動 `export` 時才更新網站。不另外處理（第十二節 #12）。

---

## 二、資料表 DDL（F10-1）

加在 `db.py` 的 `TABLES` 清單、索引之前（原型 diff 見附錄 C）：

```sql
IF OBJECT_ID('quarterly_financials') IS NULL
CREATE TABLE quarterly_financials (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
    fin_year      INT            NOT NULL,
    fin_quarter   TINYINT        NOT NULL CHECK (fin_quarter BETWEEN 1 AND 4),
    industry_tbl  NVARCHAR(10)   NOT NULL CHECK (industry_tbl IN ('ci','fh','basi','bd','ins','mim')),
    revenue       BIGINT         NULL,
    gross_profit  BIGINT         NULL,
    op_income     BIGINT         NULL,
    net_income    BIGINT         NULL,
    eps           DECIMAL(10,2)  NULL,
    first_seen    DATE           NULL,
    created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
    updated_at    DATETIME       NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)
)
```

- **可重複執行**：`IF OBJECT_ID(...) IS NULL`；第二次執行不做任何事。不改任何既有表。
- **唯一鍵** `(stock_id, fin_year, fin_quarter)` 同時是查詢用的索引；表約 2.2 萬列（11 季 × 1,984 家），**不另建索引**。
- **存累計值**，不存單季值（1-8）。金額 `BIGINT` 千元（台積電全年營收約 3.8 兆元 = 38 億千元，`INT` 不夠）。
- `first_seen`：日常收集（`collect --catch-up`、`collect`、`collect --date`）第一次寫入該列的日期；**補抓寫入 NULL**；MERGE 更新時不動。
- `setup-db` 結束訊息在 `market_breadth` 之後加 `quarterly_financials`（字串仍以 `"etf_holding_gaps")` 結尾，`test_iter06` 有檢查）。
- **MERGE**（`merge_financials`）：`OPENJSON` 傳入整個回應 → `JOIN stocks`（只寫 `stocks` 已有的股票）→ 已有且任一欄不同（`EXISTS (SELECT s… EXCEPT SELECT t…)`，NULL 也能正確比較）才 UPDATE 並寫 `updated_at`；沒有就 INSERT（含 `first_seen`）。回傳新增＋更正的列數。`stocks` 沒有的公司由 `collect_financials` 印出家數與前 5 個代號。
- **回滾**：本輪只新增一張表，PG **不執行**任何還原或 `DROP`。需要時由使用者從 `../_backups/` 還原，或只刪除新表（PM 第六節使用者自行執行 #6）。

---

## 三、收集（F10-1）

### 3-1 窗口與截止日（`health.FIN_WINDOW`、`FIN_DUE`，mopsov 註 1 已核對）

| 季別 | 窗口（季底後第 15 天～金融業截止 + 7 天） | 一般業截止 | 金融業截止（取最晚的金控） | 銀行、證券、保險 | 一般業截止後第一個交易日（2026） | 金融業截止後第一個交易日（2026） |
|---|---|---|---|---|---|---|
| Q1 | 4/15～6/06 | 5/15 | 5/30 | 5/15 | 2027：5/17 | 2027：5/31 |
| Q2 | 7/15～9/07 | 8/14 | 8/31 | **8/31**（PM 表寫 8/31，正確） | 8/17 | 9/01 |
| **Q3** | **10/15～12/06** | **11/14（週六）** | **11/29（週日）** | 11/14 | **11/16** | **11/30** |
| Q4（年報） | 次年 1/15～4/07 | 3/31 | 3/31 | 3/31 | 2027：4/01 | 2027：4/01 |

- 「截止日後的第一個交易日」= **嚴格在截止日之後**的第一個交易日（11/14 → 11/16，11/29 → 11/30，3/31 → 4/01），用交易日曆計算（`fin_due`）。
- `fin_quarter_for(d)`：d 在某季窗口內 → `(年, 季)`；窗口外 → None。1/15～4/07 → `(d.year − 1, 4)`。
- `fin_latest_quarter(d)`（`check` 用）：窗口內 → 該季；窗口外 → 往回找最近一個窗口的季別，並標示「不在窗口內」。

### 3-2 收齊條件（`health.fin_done`，提前結束與 `check` ✅ 共用）

`counts = {(年, 季): (總家數, 金融業家數)}`，由 `financial_counts(cur)` 一次 SQL 取得（上市＋上櫃合計）。收齊 = 下面兩條都成立：

1. 總家數 > 0、上一季總家數 > 0，且總家數 ≥ 上一季 × **98%**（上一季沒有資料時**不算齊**：繼續收到窗口結束）；而且
2. 金融業家數 ≥ 上一季金融業家數，**或**今天已過「金融業截止日後的第一個交易日」。

- PM 寫「金控」；本設計改成「金融業」（第十二節 #1）：Q2 的銀行、證券、保險截止日也是 8/31，只看金控會在 8/31 前就因 98% 加金控偶然齊而停止。Q3、Q1 金融業和金控截止日不同時，取最晚的金控截止日，結果只會更晚停，不會漏。

### 3-3 收集路徑

| 路徑 | 何時排入季報 | 請求數 | `first_seen` |
|---|---|---|---|
| `collect --catch-up`（`make_plan`） | 今天在窗口內、`financials_on` ≠ 今天、`fin_done` 不成立 | 上市、上櫃各 1 次（共 2） | 今天 |
| `collect`、`collect --date D`（`plan_for_date`） | D 在窗口內、D 不是行事曆休市日、`fin_done`（以今天判斷）不成立；**不看** `financials_on`（和其他資料集「該日全部重抓」一致） | 2 | 今天 |
| `history --only financials --start S [--end E] [--force]` | 季底日落在 S～E、而且季底 + 15 天 ≤ 今天的季別；已有的（季、市場）略過，`--force` 才重抓 | 每季每市場 1 次 | NULL |

- `execute_plan`：`plan["financials"]` 有值時呼叫 `collect_financials(年, 季, 今天)`（經 `_guard`）。**成功**（含 0 家）→ `collect_runs.detail.undated["financials"] = 今天`；同一天的下一次 `--catch-up` 不再抓。**失敗** → `errors["financials"]`，該次結果記異常（`undated_errors` 加 `financials`），`financials_on` 不更新，下一次收集會再試。
- `load_state` 由最近 200 筆執行紀錄取 `financials_on`（比照 `revenue_on`）。
- `_undated_counts` 加 `quarterly_financials`：季報有新增時算「有新資料」，會觸發匯出。
- `--no-revenue` **不影響**季報（不新增旗標，第十二節 #6）。
- 補抓遇 `FetchError`（封鎖）或欄位不符（`PARSE_ERRORS`）→ 停止並印「在 2025Q3 TPEx 停止：…」與「建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的季別會自動跳過」，回傳 False（`history` 的 rc 和現行相同）。
- `history` 沒有 `--only` 時**不抓**季報（`financials` 不在 `ALL_DATASETS`）；`--only financials prices` 這種混用會先補季報、再照常補行情。

### 3-4 請求量

| 項目 | 次數 |
|---|---|
| SA 開工前確認 | 3（已完成） |
| PG 補抓 `history --start 2024-01-01 --only financials`（11/06～11/13 執行） | 113Q1～115Q3 共 11 季 × 2 市場 = **22**（約 1.7 分鐘，`SECONDS_PER_QUARTER = 4.5`）；重跑 0 |
| 日常（窗口內） | 每天第一次成功的 `--catch-up` 2 次；收齊後 0 |
| 日常（窗口外） | 0 |
| 115Q3 剩餘窗口（使用者恢復收集後～12/06） | 最多約 2 × 天數；預期 12/01（金融業齊）後 0 |
| 全年上限 | 4 個窗口約 53＋55＋53＋83 天，每天最多 2 次；實際約在截止後 1～3 天收齊而停止，約 200 次 |

- 測試 `test_f101_window_requests`：模擬 Q3 窗口 10/15 起 45 天、家數一直未齊，每天 2 次、共 90 次；達收齊條件後 0 次。

### 3-5 `check` 的季報一行（`health.financials_status`，純函式）

印在月營收一行之後。文字定稿：

```
第 3 季財報 2026Q3：已收 281 家（前一季 1,950 家的 14%），金融業 0／38 家，⏳ 公布期間（一般業 11/14、金融業 11/29 截止）
```

- 季別名稱：Q1～Q3「第 N 季財報」，Q4「年報」；截止日相同時只寫「（03/31 截止）」。
- 上一季 0 家時不印「（前一季…）」；上一季金融業 0 家時不印「金融業…」。

| 狀態 | 條件（依序判斷） | 結尾文字 | 計入異常 |
|---|---|---|---|
| ✅ | `fin_done` 成立 | `，✅ 已齊` | 否 |
| ℹ️（狀態字串 `"info"`） | 今天不在窗口內（顯示最近一個窗口的季別），未齊 | `，ℹ️ 收集期間已結束（12/06），不再收集` | **否，rc 不變** |
| ⏳ 公布期間 | 今天 ≤ 一般業截止後第一個交易日；或總家數已達 98%（只差金融業）且今天 ≤ 金融業截止後第一個交易日 | `，⏳ 公布期間（一般業 11/14、金融業 11/29 截止）` | 否 |
| ⏳ 晚交 | `financials_on` 是今天或前一個交易日 | `，⏳ 晚交公司陸續補進（最後收集 11/16）` | 否 |
| ❌ | 其餘（已過截止、未齊、收集停了） | `，最後一次收集季報 2026-11-12，❌ 異常`，問題清單加 `❌ …：已過申報截止日仍未收齊，收集可能停了`，並印建議指令 `👉 請執行 python3 -m twstock collect --catch-up` | **是，rc = 1** |

- `check_report(..., revenue=None, financials=None)`：`financials` 是 `None` 時不印這一行（舊測試相容）。`run_check` 傳入 `financial_counts(cur)`。
- PM 驗收 #8 五個情境的輸出見附錄 A-4。

---

## 四、PG 實作與資料操作步驟（含驗證與停止條件）

> 本輪 PG 被允許的寫入動作只有：`backup`、`setup-db`、`history --start 2024-01-01 --only financials`、`export`。**不執行** `collect`、`revenue`、其他 `history`。所有 SQL 都是唯讀查詢。每一步的輸出貼進 `04-dev.md`。8000 埠是使用者的伺服器，預覽用 8001。

**步驟 0：備份**
- `python3 -m twstock backup`；記錄指令、開始時間、`../_backups/` 的檔名與大小（應和上次備份同一數量級）。
- 必須早於任何程式修改與 `setup-db`。失敗或檔案大小明顯偏小 → **停**，回報使用者。

**步驟 1：基線**
- 舊程式 `python3 -m twstock export`，記錄耗時（SA 實測 18.5 秒）；把 `site/data/` 複製到 `logs/iter10_before/`。
- 既有表列數快照（存成 `logs/iter10_rows_before.txt`）：
  ```sql
  SELECT t.name, SUM(p.rows) AS n FROM sys.tables t
  JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
  GROUP BY t.name ORDER BY t.name;
  ```
- 確認新表還不存在：`SELECT OBJECT_ID('quarterly_financials');` → NULL。不是 NULL → 停，回報 SA。

**步驟 2：F10-3**
- 依附錄 C 改 `collectors/daily.py`（1 行）；依附錄 D 改 `site/stock.js` 的 `fundSub` 與淨值比卡（說明文字可先寫完整版，「請對照下方季報卡…」半句只在有 `fin` 時出現，F10-1 完成前不會顯示）。
- 驗證：`test_iter01～09` 全過。

**步驟 3：F10-1、F10-2 程式與測試（不連資料庫）**
- 新增 `twstock/collectors/financials.py`；改 `db.py`、`catchup.py`、`history.py`、`health.py`、`export.py`、`__main__.py`（附錄 C）；改 `site/stock.js`、`app.js`、`app.css`（附錄 D）；改 `tests/test_iter03.py`、`test_iter08.py`（附錄 E）；新增 `tests/test_iter10.py` 與 `tests/fixtures/` 4 檔（附錄 F，fixture 用 scratchpad `sa10/fixtures/` 的檔案直接複製，或用附錄 F-2 的指令從原始回應重新產生）。
- 驗證：`for f in tests/test_iter*.py; do python3 $f || break; done` 全過（10 個檔）。
- **此步到步驟 4 之間不可執行 `export`、`check`、`collect`**：新程式會查詢不存在的 `quarterly_financials` 而失敗。

**步驟 4：建表**
- `python3 -m twstock setup-db` 執行**兩次**，兩次都不報錯，訊息含 `quarterly_financials`。
- 驗證 SQL：
  ```sql
  SELECT COUNT(*) FROM quarterly_financials;                                                  -- 0
  SELECT name FROM sys.key_constraints WHERE parent_object_id = OBJECT_ID('quarterly_financials');  -- PK 與 UQ_quarterly_financials
  ```
  再執行步驟 1 的列數查詢，除了多一列 `quarterly_financials 0` 以外和 `iter10_rows_before.txt` 完全相同（`diff`）。
- 任何一項不符 → **停**，不執行步驟 5；回報使用者，由使用者決定是否還原。

**步驟 5：補抓**
- `python3 -m twstock history --start 2024-01-01 --only financials`。
- 先看印出的計畫：`📑 季報：待抓 22 次（季別 × 市場）；⏱️ 預估約 1.6 分鐘`。不是 22 次 → 中斷（Ctrl+C），回報 SA。
- 每次印一行，例如 `📑 TWSE 2026Q2：回應 1,088 家，新增或更正 1,088 家`；有「略過 N 家（stocks 沒有：…）」時記錄下來（下市公司屬正常）。
- 驗證 SQL：
  ```sql
  SELECT f.fin_year, f.fin_quarter, s.market_type, COUNT(*) AS n,
         SUM(CASE WHEN f.industry_tbl IN ('fh','basi','bd','ins') THEN 1 ELSE 0 END) AS fin_n,
         SUM(CASE WHEN f.first_seen IS NOT NULL THEN 1 ELSE 0 END) AS seen
  FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
  GROUP BY f.fin_year, f.fin_quarter, s.market_type ORDER BY 1, 2, 3;
  ```
  - 22 列（11 季 × 2 市場）；`seen` 全部 0。
  - 2026Q2：TWSE 1,088（金融業 31）、TPEx 896（金融業 7）。2024Q1 TWSE 約 1,026。2026Q3 TWSE ≥ 231、TPEx ≥ 0（依執行日而定）。
  - 其餘季別上市約 1,000～1,090、上櫃約 800～900；任一季別 < 上一季的 90% 且不是 115Q3 → 停，回報 SA（可能是解析漏表）。
  ```sql
  SELECT industry_tbl, COUNT(*) FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
  WHERE fin_year = 2026 AND fin_quarter = 2 AND s.market_type = 'TWSE' GROUP BY industry_tbl;   -- ci 1053、fh 13、basi 10、ins 5、bd 3、mim 4
  ```
- **重跑一次**同一指令 → 計畫「待抓 0 次」、0 個請求。
- 中途停止（封鎖或欄位不符）→ **停**，記錄訊息；封鎖時 30 分鐘後重跑一次（只補缺的），仍失敗 → 回報；欄位不符 → 回報 SA，不要改解析器硬過。
- 記錄請求次數（22）、耗時。

**步驟 6：匯出與比對**
- `python3 -m twstock export`，記錄耗時（預期和基線差 < 1 秒，上限 +3 秒）。
- `python3 logs/iter10_compare.py logs/iter10_before site/data` → 「✅ 相同」，並記錄印出的新鍵大小（stocks 的 `fin` 預期約 0.7 MB，上限 1 MB；screen 新欄約 65 KB；`fin_progress` < 100 B）。`--keep-new` → 判定不同（反證）。
- `python3 logs/iter10_recalc.py` → 「✅ 相同」。
- 附錄 A-1 的數字以 SQL（第九節 9-3 #2）逐一核對。
- `python3 -m twstock check` → 季報一行出現；11/06～11/16 應為 `⏳ 公布期間`；回傳碼不因季報而變成 1。
- 任一不符 → 停，不更新網站，回報。

**步驟 7：文件與預覽**
- README、`__main__.py` 依第十節。
- 8001 埠預覽（`python3 -m http.server 8001 --directory site` 或專案的預覽方式，不用 8000）：375 px 檢查第七節列出的頁面；主控台無錯誤；結束後關閉 8001。

---

## 五、F10-3 第 9 輪收尾小修

### 5-1 估值說明（`site/stock.js`，文字定稿）

有 `val` 的股票，在指標卡下方：

> 一年位置 = 近 242 個交易日中，官方值小於或等於今天的天數比例（資料 11/06）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。**請對照下方季報卡的近 4 季 EPS 與一年前比較。**

- 粗體半句只在該股有 `fin`（季報卡）時出現；沒有 `fin` 時整句不顯示。
- 拿掉舊的「請一併看淨值比」。
- 驗收（PM F10-3 #1）：`#/stock/2408` 與 `#/stock/2330` 都看得到「獲利大增」與「不代表股價便宜」。

### 5-2 淨值比卡的資料日

- `fundSub(v, cap = true)` 加第二個參數；淨值比卡用 `subs(fundSub(fund.pb, false), valSub('pb', fund.pb))`：顯示「資料 11/06」，**不顯示**股本變動註記（cap 股 5314 的「股本變動」字樣照舊只在本益比、殖利率卡）。值為空時一樣顯示「官方未提供」。

### 5-3 上市 `amount` 行情保護（`collectors/daily.py`，1 行）

```python
if dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT) and written.get(f"prices.{market or 'TWSE'}") == 0:
    continue
```

- `"amount".partition(".")` 的 market 是空字串 → 視為 `TWSE`；**資料集鍵名不改**（`collect_runs.detail`、`history --only amount` 照舊）。
- 行為：

| 情況 | 改前 | 改後 |
|---|---|---|
| `prices.TWSE` 寫入 0 列（臨時休市、行情延遲） | 發 BFI82U 1 次（通常 0 列或錯誤） | **不發**，`written` 沒有 `amount` |
| `prices.TWSE` > 0 | 發 1 次，寫 6 列 | 相同 |
| `prices.TWSE` 抓取失敗（例外，`written` 沒有這個鍵） | 發 1 次 | **相同**（照舊發請求：`written.get(...)` 是 None，不等於 0） |
| `prices.TWSE` 不在本次的鍵（`history --only amount`） | 發 | 相同（沒有 `prices` 鍵，不受影響） |
| 上櫃 `amount.TPEx` | 已有保護 | 相同 |

- 對既有行為的影響：只有「同一次收集裡上市行情確定 0 列」時少 1 次請求。`collect --catch-up` 在這種日子本來就會在之後補抓 amount（`amount` 屬於當日鍵，下次行情有了才會齊），所以不會漏資料。
- 隔離比對：`test_f103_twse_amount_waits_for_prices` 用 mock 比對 4 種情況（0 列、6 列、例外、`--only amount`）；`history --only amount`、`collect --date` 的上市寫入結果和改前相同（同一 fixture 寫入的 6 列逐欄相同）。網站輸出不受影響（compare 判定相同）。
- README 沒有「上市法人金額不受行情保護」的敘述，不需要改。

---

## 六、匯出 JSON 欄位與大小（F10-1、F10-2）

### 6-1 `stocks/{代號}.json` 的 `fin`（沒有任何季報資料的股票**不輸出**這個鍵）

```json
"fin": {"t": "ci",
        "q": [[202504, 1.23, null, 30.1, 12.0, 52000000], …, [202603, 25.9, 257.2, 85.7, 80.0, 133648966]],
        "c": {"e": 49.28, "ey": 53.3, "fs": "2026-11-06"},
        "e4": 62.41, "e4p": 43.9}
```

| 鍵 | 說明 | 單位、小數 |
|---|---|---|
| `t` | 最新一季的 `industry_tbl` | — |
| `q` | 近 8 個季別中有累計值的季別（舊到新）：`[季別 YYYYQQ, 單季 EPS, 單季 EPS 年增 %, 毛利率 %, 營益率 %, 單季營收]` | 元 2 位；% 1 位；營收千元整數；null 規則見 1-8 |
| `c.e`、`c.ey` | 最新一季累計 EPS、累計 EPS 年增 % | 2 位、1 位 |
| `c.fs` | 最新一季的 `first_seen`（`YYYY-MM-DD`）；NULL（補抓）時**不輸出** | — |
| `e4`、`e4p` | 近 4 季 EPS、一年前的近 4 季 EPS | 2 位；null 可能 |

- 上例為原型模擬資料（115Q2、115Q3 是真實值，其餘季別是合成值，所以 `e4`、`e4p` 和 PM 表不同）。
- 大小：模擬 1,984 檔 × 8 季合計 **約 700 KB**（`stocks/` 實際位元組 +717 KB，PM 上限 1 MB）。

### 6-2 `screen.json`

| 鍵 | 說明 |
|---|---|
| `eq` | 最新一季單季 EPS（元，2 位） |
| `ey` | 單季 EPS 年增 %（1 位；去年同季 ≤ 0 → null） |
| `e4` | 近 4 季 EPS |
| `gm` | 最新一季單季毛利率 %（金融業 null） |
| `gmy` | 毛利率年增（百分點，1 位） |
| `fq` | 最新季別（YYYYQQ，例如 202603） |
| `eh` | 單季 EPS 創幾季新高（整數） |
| `fqd` | 各季別檔數 `{"202603": 231, "202602": 1747}`（依季別新到舊，比照 `rmd`） |

- 沒有季報的股票各欄 null（`fqd` 不計）。
- 大小：+**65.3 KB**（253 → 320 KB）；PM 上限 60 KB，建議放寬到 70 KB（第十二節 #2）。若要壓回 60 KB 以下，可拿掉 `e4` 以外的一欄，但會少一個條件，SA 不建議。

### 6-3 `latest.json` 的 `fin_progress`

```json
"fin_progress": {"q": 202603, "n": {"TWSE": 231, "TPEx": 0}, "p": {"TWSE": 1088, "TPEx": 896}}
```

- 資料日在某季窗口內、而且該季（上市＋上櫃）已有資料時才有值；否則 `null`。
- 家數以 `stocks.market_type` 分市場（`COUNT(*)`，和 QA SQL 相同）。
- 大小 67 B。

### 6-4 匯出時間

- 新增一次 SQL（`quarterly_financials JOIN stocks`，約 2.2 萬列）與純 Python 計算。原型 18.5 → 18.5～18.9 秒。

---

## 七、畫面規格

### 7-1 個股頁 `#/stock/{代號}`

**季報卡**（在「月營收／技術面訊號」那一列下方，獨立一張卡；沒有 `fin` → 整張不出現、不報錯）：

- 標題列：`季報`＋小字 `2026 Q3｜本站收錄 11/06｜一般業`（沒有 `fs` 不顯示「本站收錄」；業別：一般業、金控、銀行、證券、保險、其他）。
- 數字卡（沿用 `.metrics` 樣式，375 px 兩欄；以 2408 為例，年增與近 4 季的數字是示意）：

| 卡 | 數字 | 小字 |
|---|---|---|
| 單季 EPS | 25.90（依年增上紅綠色） | `年增 +257.2%`；去年同季 ≤ 0 且本季 > 0 → `年增 轉盈`；其餘 null → `年增 --` |
| 累計 EPS | 49.28 | `1～9 月，年增 +53.3%`（Q4 寫「全年」） |
| 毛利率 | 85.7% | `去年同季 xx.x%`（**只有一般業**有這張卡） |
| 營益率 | 80.0% | `去年同季 …`（最新一季營益率不是 null 才有這張卡；金控、銀行沒有） |
| 近 4 季 EPS | 62.41 | `一年前 43.90` |

- 柱狀圖（純 HTML，不用圖表庫）：近 8 季（實際有幾季畫幾季）單季 EPS；柱頂寫數字；0 軸一條線；負值往下；紅 = 年增 ≥ 0，綠 = 年增 < 0，灰 = 年增 null（去年同季虧損或沒有資料），單季 null → 空柱、數字 `--`。滑鼠提示：`2026 Q3 單季 EPS 25.90，年增 +257.2%`。底下季別 `26Q3`。
- 口徑說明（小字）：「單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。金融業沒有毛利率。」沒有 `fs` 時加「『本站收錄』日期只有每日收集時才記錄，補抓的季別不顯示。」

**估值旁的獲利說明一行**（在估值說明正下方；不延後）：

- 門檻：`e4 > 0` 且（`e4p ≤ 0` 或 `e4 ≥ 1.5 × e4p`）；`e4` 或 `e4p` 為 null → 不顯示。
- 文字：「近 4 季 EPS 一年前 3.20 元 → 現在 6.77 元（2.1 倍）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。」一年前 ≤ 0 時括號寫「轉盈」。
- PM 原句「本益比低主要來自獲利增加」是因果判斷，本設計改為說明機制（第十二節 #3），仍含「獲利增加」字樣，符合 F10-1 #9。
- 不依本益比位置決定是否顯示（沒有 `val` 的股票也可以顯示），因為「獲利大增 → 本益比下降」對所有股票都成立。

### 7-2 選股頁 `#/rank/screen`

- 新條件（「基本面」組，放在既有估值條件之後）：

| id | 標籤 | 選項（預設） | 判斷 | 顯示欄 |
|---|---|---|---|---|
| `ey` | 單季 EPS 年增 ≥ {v}% | 0、20、50（20） | `ey ≥ v` | `eq`、`ey` |
| `gmy` | 毛利率年增 ≥ {v} 百分點 | 0、1、3（0） | `gmy ≥ v` | `gm`、`gmy` |
| `e4` | 近 4 季 EPS > 0 | 開關 | `e4 > 0` | `e4` |
| `eh` | 單季 EPS 創 {v} 季新高 | 4、8（4） | `eh ≥ v` | `eq`、`eh` |
| `ed` | 單季 EPS 比去年同季下滑 | 開關 | `ey < 0` | `eq`、`ey` |

- null 一律不符合（沒有季報、年增基期 ≤ 0、金融業的毛利率）。
- 預設組合加「財報優於去年」：`ey=20&gmy=0&tv=0.5`（排在第 8）。參考組合加「本益比低但 EPS 下滑」：`pe=15&ed=1&tv=0.5`（`r3`）。預設與參考改用 id 第一個字是否為 `r` 分組（原本是 `slice(0, 7)`）。
- 欄名：`單季EPS（Q3）`、`EPS年增（Q3）`（依 `fqd` 檔數最多的季別）；季別不同的列在數字後加小字 `（Q2）`。`毛利率`、`EPS新高(季)` 不上漲跌色。
- 資料日一行加「｜季報 Q3 231 檔、Q2 1,747 檔」；季別混雜時（沿用 `revMixed` 規則：沒有任何季別 ≥ 98%）加「（財報公布期間，各股季別不同）」。
- 網址：新條件和既有條件一樣寫進 hash、可還原；「重設」回預設（新條件不殘留）。
- 頁尾說明加一句季報口徑（最新一季、單季由累計相減、季別可能不同）。

### 7-3 今日頁

- 估值位置卡下方一行（`fin_progress` 不是 null 才出現）：「第 3 季財報已收：上市 231、上櫃 0 家（前一季 1,088、896 家）；本益比中位數會隨 EPS 更新而變動」。Q4 寫「2026 年報已收…」。
- **不加**「近 5 日 K 家」（第十二節 #4）。

### 7-4 空資料與缺季

| 情況 | 畫面 |
|---|---|
| 沒有任何季報（新上市、ETF 頁） | 沒有季報卡、沒有獲利說明一行；估值說明不出現「請對照下方季報卡」 |
| 只有 1 季 | 柱狀圖 1 根；單季可能 null（Q2～Q4 開始）→ `--`；近 4 季 `--` |
| 最新一季上一季缺 | 單季 EPS `--`，年增 `--`；累計 EPS 照常 |
| 去年同季虧損、本季獲利 | 年增 `轉盈`、灰色柱 |
| 本季虧損 | 負值柱往下，數字 `-0.07`（`#/stock/1805` 已預覽） |
| 金控、銀行 | 沒有毛利率卡、沒有營益率卡（`#/stock/2881` 已預覽） |
| 窗口外、或當季 0 家 | 今日頁沒有季報一行 |
| `screen.json` 沒有 `fqd`（舊檔） | 資料日一行「季報 --」，條件照常（全部不符合） |

---

## 八、邊界情況總表

| # | 情況 | 處理 | 測試 |
|---|---|---|---|
| 1 | 窗口第 1、2 天 0 家 | 回 `{}`、不丟例外、`financials_on` 記今天 | `test_f101_zero_rows_is_success` |
| 2 | 封鎖頁 | `FetchError`；補抓停止；日常記 `errors["financials"]` | `test_f101_parse_errors` |
| 3 | 欄名改變、缺必要欄 | `SchemaError`，整個回應不寫 | 同上 |
| 4 | 個體報表淨利 `--` | 改取本期淨利 | `test_f101_parse_industries`（2207 等） |
| 5 | 保險業 EPS 欄名沒有「（元）」；113 年保險業有營業收入 | 前綴比對；仍辨識為 `ins` | `test_f101_parse_industries`、`parse_old_and_otc` |
| 6 | `stocks` 沒有的公司 | JOIN 不寫入、印略過家數 | `test_f101_merge_and_ddl` |
| 7 | 同一列重複寫入、值相同 | 不更新（`EXCEPT`），`first_seen` 不變 | 同上（SQL 字串檢查）；PG 步驟 5 重跑 0 次 |
| 8 | 公司更正累計值 | MERGE 更新、`updated_at`；匯出自動重算 | 1-9 |
| 9 | Q4 用全年 − Q3 | `fin_single` | `test_f101_single_rules` |
| 10 | 上一季缺 | 單季全部 null | 同上 |
| 11 | 去年同季 ≤ 0 | 年增 null；畫面「轉盈」 | 同上、預覽 |
| 12 | 近 4 季缺一項 | null，獲利說明不出現 | `test_f101_e4` |
| 13 | 截止日週末 | 交易日曆取下一個交易日 | `test_f101_check`（11/16） |
| 14 | 上一季沒有資料（第一次上線前沒補抓） | `fin_done` 不成立，收到窗口結束 | `test_f101_make_plan` |
| 15 | 跨年 Q4 | 1/15～4/07 → 前一年 Q4 | `test_f101_windows` |
| 16 | 同一天第二次 `--catch-up` | 不排入 | `test_f101_make_plan` |
| 17 | `collect --date` 休市日 | 不收季報 | `test_f101_make_plan` |
| 18 | 只差金融業、已過一般業截止 | ⏳ 到金融業截止後第一個交易日 | `test_f101_check` |
| 19 | 窗口外未齊 | ℹ️，不計異常 | 同上 |
| 20 | 季報收集失敗 | 該次記異常；下一次再試 | `execute_plan` 沿用 `_guard` |
| 21 | 上市行情 0 列 | 不發 BFI82U | `test_f103_twse_amount_waits_for_prices` |
| 22 | 匯出時 `quarterly_financials` 不存在 | 失敗（須先 `setup-db`，README 已寫明新增資料表要執行 `setup-db`） | — |
| 23 | 季別混雜 | `fqd`、欄名用最多的季別、列加小字 | `test_f102_screen_fields`、預覽 |

---

## 九、測試

### 9-1 `tests/test_iter10.py`（新檔，全文見附錄 F；不連網、不連資料庫，`python3 tests/test_iter10.py`，相容 pytest）

| 測試 | 對應驗收 |
|---|---|
| `test_f101_parse_industries` | F10-1 #3：6 種業別；2408 EPS 23.38、營收 131,636,005、毛利 98,935,333；2330 49.33；2881 6.67、毛利 NULL；保險業 EPS；個體報表淨利 |
| `test_f101_parse_old_and_otc` | 113Q1 欄名、113 年保險業；上櫃 2 張表 |
| `test_f101_parse_errors` | 封鎖頁、缺「公司代號」、缺「基本每股盈餘」、只有標題、無資料頁 |
| `test_f101_fetch_params` | POST 參數（民國年、`season=03`、`TYPEK`） |
| `test_f101_merge_and_ddl` | DDL 可重複執行的寫法、唯一鍵；MERGE 的 JOIN stocks、EXCEPT、`first_seen` 只在 INSERT |
| `test_f101_single_rules` | F10-1 #6：Q1、Q4、上一季缺、去年同季 ≤ 0 |
| `test_f101_e4` | 近 4 季公式、Q4、缺一項 |
| `test_f101_numbers_1106` | F10-1 #5：2408 25.90／85.7%、2303 1.32／34.0%、2383 40.46／37.7%、3008 39.63／42.2%、1215 單季營收 7,464,783 |
| `test_f101_fin_stock` | `fin` 結構；補抓列沒有 `fs` |
| `test_f101_windows` | F10-1 #7：10/14 不排入、10/15 與 12/06 排入 115Q3、12/07 不排入、2027-01-15 排入 115Q4 |
| `test_f101_make_plan` | 同一天不重抓；11/20 98.5%、金融業 0 → 排入；12/01 金融業齊 → 不排入；`plan_for_date` |
| `test_f101_window_requests` | 完整窗口每天最多 2 次、收齊後 0 次 |
| `test_f101_zero_rows_is_success` | 0 家記 `financials_on` |
| `test_f101_load_state` | `financials_on` 讀取 |
| `test_f101_check` | F10-1 #8 五個情境（含 rc） |
| `test_f101_history_quarters` | `history --only financials` 的季別換算（2024-01-01～11/06 = 11 季；10/14 時不含 115Q3）、重跑全部跳過、只補缺的、全新 22 次且 `first_seen` 為 NULL、封鎖與欄位不符時停止 |
| `test_f102_screen_fields` | F10-2 #1：`eq`、`ey`、`gm`、`gmy`、`fq`、`eh`、`fqd`；2881 `gm` null |
| `test_f102_progress` | `fin_progress` 窗口內外、0 家 |
| `test_f103_twse_amount_waits_for_prices` | F10-3 #3 四種情況 |
| `test_f103_site_text` | F10-3 #1、#2：原始碼檢查說明文字與 `fundSub(fund.pb, false)` |

### 9-2 舊測試修改（附錄 E）

- `tests/test_iter03.py`：`World` 加 `self.fin`（每季 1,984 家、金融業 38 家，2024～2027 全部季別都「已齊」），`FakeCursor` 加 `"fin_year, fin_quarter, COUNT"` 分支。理由：舊測試的 `make_plan`／`plan_for_date` 現在會查季報家數；給「已齊」讓舊情境不多出季報請求（不改舊測試的預期）。
- `tests/test_iter08.py`：`screen.json` 鍵集合的預期加 `"fqd"`。

### 9-3 QA 清單與 SQL

1. `test_iter01～10` 全部通過；`test_iter10.py` 放到舊程式上失敗（反證）。
2. **數字**（F10-1 #5、F10-2 #1；之後的資料日一律以 SQL 獨立重算為準）：
   ```sql
   -- 個股各季累計、單季（SQL 自行相減）、毛利率
   SELECT s.stock_code, c.fin_year, c.fin_quarter, c.industry_tbl, c.eps,
          CASE WHEN c.fin_quarter = 1 THEN c.eps ELSE c.eps - p.eps END AS q_eps,
          CASE WHEN c.fin_quarter = 1 THEN c.revenue ELSE c.revenue - p.revenue END AS q_rev,
          CAST(100.0 * (CASE WHEN c.fin_quarter = 1 THEN c.gross_profit ELSE c.gross_profit - p.gross_profit END)
               / NULLIF(CASE WHEN c.fin_quarter = 1 THEN c.revenue ELSE c.revenue - p.revenue END, 0) AS DECIMAL(6,1)) AS gm,
          c.first_seen
   FROM quarterly_financials c JOIN stocks s ON s.stock_id = c.stock_id
   LEFT JOIN quarterly_financials p ON p.stock_id = c.stock_id AND p.fin_year = c.fin_year AND p.fin_quarter = c.fin_quarter - 1
   WHERE s.stock_code IN ('2408','2303','2383','3008','1215','2881','2330','2412') AND c.fin_year >= 2025
   ORDER BY s.stock_code, c.fin_year, c.fin_quarter;
   -- 近 4 季與一年前（2408 例）
   SELECT c.eps + y4.eps - cb.eps AS e4, cb.eps + y8.eps - cbb.eps AS e4p
   FROM quarterly_financials c JOIN stocks s ON s.stock_id = c.stock_id AND s.stock_code = '2408'
   JOIN quarterly_financials y4  ON y4.stock_id = c.stock_id AND y4.fin_year = c.fin_year - 1 AND y4.fin_quarter = 4
   JOIN quarterly_financials cb  ON cb.stock_id = c.stock_id AND cb.fin_year = c.fin_year - 1 AND cb.fin_quarter = c.fin_quarter
   JOIN quarterly_financials y8  ON y8.stock_id = c.stock_id AND y8.fin_year = c.fin_year - 2 AND y8.fin_quarter = 4
   JOIN quarterly_financials cbb ON cbb.stock_id = c.stock_id AND cbb.fin_year = c.fin_year - 2 AND cbb.fin_quarter = c.fin_quarter
   WHERE c.fin_year = 2026 AND c.fin_quarter = 3;
   -- 卜蜂 1215 Q3 單季營收 = 月營收 7～9 月合計
   SELECT SUM(m.revenue) FROM monthly_revenue m JOIN stocks s ON s.stock_id = m.stock_id
   WHERE s.stock_code = '1215' AND m.revenue_year = 2026 AND m.revenue_month BETWEEN 7 AND 9;   -- 7,464,783
   ```
   - PM 表的參考值：2408 近 4 季約 50.7（343.5 ÷ 6.77，容許 ±3%）、一年前 ≤ 0；2303 近 4 季約 6.77、一年前約 3.20（容許 ±3%）。不同時以 SQL 為準，並確認 `stocks/2408.json` 的 `e4`、`e4p` 等於 SQL 值。
3. **條件**（F10-2 #2）：`python3 logs/iter10_recalc.py` 會印「單季 EPS 年增 ≥ 0／20／50%」的檔數並和 `screen.json` 比對；選股頁設定同一條件、成交額門檻設為 0 時，「符合 N 檔」應等於該數字扣除共同排除（處置股、今日無成交）。
4. **補抓**（F10-1 #4）：第四節步驟 5 的 SQL；`first_seen` 全部 NULL；重跑 0 次。
5. **`check`**（F10-1 #8）：mock 由測試涵蓋；實機 `check` 的季報一行數字等於步驟 5 SQL 的當季合計。
6. **畫面**（F10-1 #9、F10-2 #3～#5、#8）：第七節；`#/stock/2412` 以 SQL 確認 `e4 < 1.5 × e4p` 時不出現獲利說明一行。季別混雜用 mock `screen.json`（`fqd = {"202603":300,"202602":1600}`）檢查欄名、小字、說明；改成只有一個季別時說明消失。
7. **大小與時間**（F10-1 #10、F10-2 #6）：compare 印出的新鍵大小；`export` 耗時。
8. **網站隔離**（F10-1 #11、F10-2 #7、F10-3 #4）：`iter10_compare.py` 「✅ 相同」。
9. **今日頁**（F10-2 #5）：`fin_progress.n` 等於
   ```sql
   SELECT s.market_type, COUNT(*) FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
   WHERE f.fin_year = 2026 AND f.fin_quarter = 3 GROUP BY s.market_type;
   ```
10. **F10-3**：`#/stock/2408` 三張卡都有「資料 MM/DD」；`#/stock/5314` 股本變動字樣只在本益比、殖利率卡；說明文字含「獲利大增」「不代表股價便宜」。

---

## 十、README 與 `__main__.py` 修改清單

### README

| 段落 | 修改 |
|---|---|
| 專案結構 `twstock/collectors/` | 加「`financials` 季報（綜合損益表彙總）」 |
| 專案結構 `tests/` | 加 `python3 tests/test_iter10.py` |
| 安裝「新增資料表」一段 | 加「第 10 輪的 `quarterly_financials`」 |
| 日常使用指令區 | 加 `python -m twstock history --start 2024-01-01 --only financials   # 只補季報（季底日在範圍內、窗口已開始的季別；每季上市、上櫃各 1 個請求；已有的季別自動略過，--force 重抓；約 22 次、2 分鐘）`；加 `python3 tests/test_iter10.py`；`collect --catch-up` 說明加「季報窗口內每天抓一次季報」 |
| 注意事項（新增一條：季報） | 資料來源 mopsov `ajax_t163sb04`；累計值、單季相減規則、Q4 = 全年 − Q3；收集窗口與截止日表（3-1）；收齊條件（98%＋金融業）；每天最多 2 次請求；`financials_on`；補抓的列沒有「本站收錄」；`--no-revenue` 不影響季報；`stock_fundamentals.eps` 未使用（官方本益比已含 EPS 資訊） |
| 注意事項「資料完整性」或 `check` | 加季報一行的 5 種狀態（3-5），ℹ️ 不計異常 |
| 注意事項：個股頁 | 季報卡、獲利說明一行的門檻與文字；`stocks/{代號}.json` 的 `fin` 欄位（6-1）；估值說明改寫、淨值比卡資料日 |
| 注意事項「條件選股」 | 加季報條件 5 個、預設「財報優於去年」、參考「本益比低但 EPS 下滑」（預設改為 8 組、參考 3 組）；`screen.json` 的 `eq`、`ey`、`e4`、`gm`、`gmy`、`fq`、`eh`、`fqd`；季別混雜的標示 |
| 注意事項：今日頁估值位置卡 | 加 `latest.json` 的 `fin_progress` 與季報一行 |

### `__main__.py`

- docstring：加 `history --start 2024-01-01 --only financials` 範例；`collect`、`collect --catch-up`、`export` 的說明加「季報」。
- `history --only` 的 `choices` 加 `"financials"`（放在 `"tpex_index"` 之後，保留 `test_iter05` 檢查的 `"margin", "holdings"]` 結尾）；help 加「financials = 季報（季底日在 --start～--end 的季別）」。
- 沒有新子指令、沒有新旗標。

---

## 十一、延後順序（沿用 PM 第一節）

PG 進度落後時依序延後（不必回頭問 PM），延後項目記在 `04-dev.md` 並回到待辦：

1. F10-2 今日頁估值卡的「財報公布進度」一行（`finLine`、`fin_progress`）。
2. F10-2 條件「單季 EPS 創 N 季新高」（`eh`）與參考組合「本益比低但 EPS 下滑」（`ed`、`r3`）。
3. F10-2 其餘選股欄、條件與預設組合「財報優於去年」。
4. F10-1 個股季報卡的柱狀圖（保留數字卡與口徑說明）。

- **不延後**：`backup`、新表、解析器、收集窗口與排程、補抓、`check` 一行、匯出的單季相減、季報卡的數字、估值旁的獲利說明一行、F10-3 全部。
- 延後時的對應：延後 1 → `export.py` 不輸出 `fin_progress`，compare 的 `NEW_LATEST` 改為空集合；延後 2 → 拿掉 `eh` 欄與 `SCREEN_KEYS` 的 `eh`，compare 與 recalc 同步拿掉；延後 3 → `screen.json` 不加任何季報欄，compare 的 `NEW_SCREEN` 改為空集合，recalc 的第 3、4 段 screen 部分略過；延後 4 → 刪 `renderFin` 的柱狀圖與 `.fin-bars` CSS。

---

## 十二、對 PM 範圍的調整建議（不改 02-pm.md）

| # | PM 原文 | 建議 | 理由 |
|---|---|---|---|
| 1 | 提前結束與 `check` 的第 2 條看「金控」 | 改看「**金融業**（金控、銀行、證券、保險）」，截止日取金控 | mopsov 註 1：Q2 的銀行、證券、保險也是 8/31 截止；只看金控可能在其他金融業還沒齊時就停止。結果只會更晚停 |
| 2 | `screen.json` 增加 ≤ 60 KB | 放寬為 ≤ **70 KB** | 7 欄 × 約 2,000 檔實測 65.3 KB；PM 列的 7 個欄位都需要 |
| 3 | 獲利說明一行「本益比低主要來自獲利增加」 | 改為「本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱」 | 原句是因果結論；股價也可能同時下跌。新句說明機制、仍含「獲利增加」，符合 F10-1 #9 |
| 4 | 今日頁是否加「近 5 日 K 家」 | **不加** | 補抓列沒有 `first_seen`，上線前幾天會嚴重偏少；家數本身已足夠 |
| 5 | 淨值比卡的股本變動註記 | 不加（照舊只在本益比、殖利率卡） | 淨值比不受 EPS、股利口徑影響 |
| 6 | `--no-revenue` 是否也略過季報 | **不略過**，不新增旗標 | 季報每天最多 2 次；新增旗標要改 README 與測試，沒有需求 |
| 7 | 補抓指令形式 | `history --only financials --start 2024-01-01`：季底日落在範圍內、季底 + 15 天 ≤ 今天的季別 | PM 傾向；日期換算規則寫在 3-3 |
| 8 | 「各季別檔數（比照 `rmd`）」 | 鍵名 `fqd`；`test_iter08` 的鍵集合改一行 | 舊測試檢查 `screen.json` 鍵集合 |
| 9 | `stock_fundamentals.eps` 是否註明未使用 | README 註明「未使用」 | 全部 NULL |
| 10 | F10-1 #5 表「毛利率（上半年 → Q3 單季）」 | 季報卡與柱狀圖的每一季都是**單季**毛利率；Q2 那一季顯示的是 Q2 單季（= 上半年累計 − Q1 累計），不是 PM 表的上半年 75.2% | 所有季別一律單季，口徑一致。驗收以 Q3 單季（2408 85.7% 等）為準；Q2 單季以 SQL 為準 |
| 11 | F10-1 #3「115Q2 上市完整檔 1,088 家」 | 測試只用精簡 fixture；完整檔由 PG 一行指令驗證：`python3 -c "from twstock.collectors.financials import parse_financials as p; d=p(open('…/r10/raw/t163sb04_sii_115_02.html',encoding='utf-8').read()); import collections; print(len(d), collections.Counter(v['industry_tbl'] for v in d.values()))"` | PM 要求測試不讀 scratchpad 路徑；原型已驗證 1,088 家與各業別家數 |
| 12 | （未提及） | 只有更正、沒有新增的收集不會觸發匯出（1-9），列為已知限制，不處理 | 改「有新資料」的判斷會影響所有資料集，不在範圍 |
| 13 | （未提及）無資料頁格式 | 依 `<h2>` 標題或「查無」判斷為 0 家；未實測 | 3 次請求都有資料；遇到時補判斷字串即可 |
| 14 | F10-1 #7「11/20、總家數 98.5%、金控 0 家 → 仍排入」 | 依 #1 改讀為「金融業 0 家」 | 測試照此寫 |

---

## 十三、給 PG、QA 的提醒

1. **順序**：第四節步驟 3 到步驟 4 之間不可執行 `export`、`check`、`collect`（新表還不存在）。
2. 補抓的 115Q3 只有執行當下已公布的公司，`first_seen` 是 NULL；之後由使用者每晚 `collect --catch-up` 補上（新增的公司有「本站收錄」日期）。
3. D18 = A：本輪 QA 完成前使用者不恢復收集；115Q3 由 PG 的補抓與之後的日常收集補上，資料不漏。
4. fixture 是原始 HTML 的精簡版（表頭、註 1 原樣，每張表只留指定公司），**不要手改**；要重產用附錄 F-2 的 `make_fixture.py`。
5. 匯出的 `fin` 數字和 PM 表不同時，先用 9-3 #2 的 SQL 確認資料庫的累計值；PM 表是 11/06 的值，公司可能已更正。
6. 不要用 Python `round` 計算百分比（用 `_r1`）；不要把 EPS 轉 float 後再相減。
7. 8001 預覽結束後關閉；不要用 8000。不 commit、不動 `.env`、不執行 `_archive/`。

---

## 附錄 A：預期值

### A-1 個股（11/06；115Q2、115Q3 為 mopsov 真實值）

| 股票 | 業別 | 115Q2 累計 EPS | 115Q3 累計 EPS | Q3 單季 EPS | Q3 單季 EPS 年增 | 上半年累計毛利率（PM 表）→ **Q3 單季**毛利率 | Q3 單季營收（千元） |
|---|---|---|---|---|---|---|---|
| 南亞科 2408 | ci | 23.38 | 49.28 | **25.90** | 以 SQL 為準（去年同季 ≤ 0 時 null） | 75.2% → **85.7%** | 133,648,966 |
| 聯電 2303 | ci | 4.68 | 6.00 | **1.32** | 以 SQL 為準 | 30.9% → **34.0%** | 74,239,117 |
| 台光電 2383 | ci | 42.46 | 82.92 | **40.46** | 以 SQL 為準 | 32.0% → **37.7%** | 60,884,539 |
| 大立光 3008 | ci | 82.35 | 121.98 | **39.63** | 以 SQL 為準 | 49.4% → **42.2%** | 15,650,820 |
| 卜蜂 1215 | ci | — | — | 2.23 | 以 SQL 為準 | 18.3% → 19.2% | **7,464,783**（= 21,866,426 − 14,401,643） |
| 台積電 2330 | ci | 49.33 | 未公布 | null（最新一季 Q2） | — | — | — |
| 富邦金 2881 | fh | 6.67 | 未公布 | null（最新一季 Q2） | — | 無（`gm` null） | — |

- 原型模擬匯出中的「年增」「近 4 季」使用合成的 2024～2025 季別，不能當驗收值；以 SQL 為準。

### A-2 解析（115Q2 上市完整檔）

- 1,088 家：ci 1,053、fh 13、basi 10、ins 5、bd 3、mim 4；淨利改取本期淨利的 74 家。
- 2408：營業收入 131,636,005、毛利 98,935,333、EPS 23.38；2330：49.33；2881：6.67、`gross_profit` NULL、`revenue` = 淨收益。

### A-3 匯出大小（模擬資料）

| 項目 | 基線 | 原型 | 增加 |
|---|---|---|---|
| `stocks/` 實際位元組 | 32,465,695 | 33,183,004 | +717 KB（`fin` 1,984 檔約 700 KB） |
| `screen.json` | 253,337 | 320,214 | +65.3 KB |
| `latest.json` | 731,281 | 731,364 | +83 B（`fin_progress` 67 B） |
| 匯出耗時 | 18.5 秒 | 18.5～18.9 秒 | < 0.5 秒 |

### A-4 `check` 季報一行（PM F10-1 #8，上一季 1,950 家、金融業 38 家）

| 日期 | 本季 | 最後收集 | 輸出 | rc |
|---|---|---|---|---|
| 11/06 | 281、金融業 0 | — | `第 3 季財報 2026Q3：已收 281 家（前一季 1,950 家的 14%），金融業 0／38 家，⏳ 公布期間（一般業 11/14、金融業 11/29 截止）` | 0 |
| 11/16 | 1,800 | — | `…已收 1,800 家（前一季 1,950 家的 92%），金融業 5／38 家，⏳ 公布期間（…）` | 0 |
| 11/17 | 1,900 | 11/16 | `…已收 1,900 家（…97%），金融業 5／38 家，⏳ 晚交公司陸續補進（最後收集 11/16）` | 0 |
| 11/17 | 1,900 | 11/12 | `…已收 1,900 家（…97%），金融業 5／38 家，最後一次收集季報 2026-11-12，❌ 異常`＋問題行＋`👉 請執行 python3 -m twstock collect --catch-up` | 1 |
| 11/20 | 1,920、金融業 20 | 11/20 | `…（…98%），金融業 20／38 家，⏳ 公布期間（一般業 11/14、金融業 11/29 截止）` | 0 |
| 12/01 | 1,920、金融業 38 | 12/01 | `…（…98%），金融業 38／38 家，✅ 已齊` | 0 |
| 12/10 | 1,900、金融業 38 | — | `…（…97%），金融業 38／38 家，ℹ️ 收集期間已結束（12/06），不再收集` | 0 |
| 2027-02-01 | Q4 100 | — | `年報 2026Q4：已收 100 家（前一季 1,950 家的 5%），金融業 0／38 家，⏳ 公布期間（03/31 截止）` | 0 |

---

## 附錄 B：原型的驗證方式（供 PG 重現，不需照做）

- scratchpad `sa10/orig/`、`sa10/proj/`：`twstock/`、`site/`、`tests/`、`scripts/`、`data/`、README、`logs/iter09_*` 的副本（**不含 `.env`**）。附錄 C～F 為 `diff -ruN orig proj` 的結果（排除 `__pycache__`、`site/data`、fixture）。
- 匯出：`sa10/run_export.py orig|proj [--sim]`。載入專案 `twstock/config.py` 只為了讀 `.env` 到環境變數（不複製 `.env`），以唯讀查詢呼叫 `export_all`，輸出到 scratchpad 的 `site/data`。`--sim` 取代 `_load_financials`：115Q2（上市＋上櫃）、115Q3 上市、113Q1 上市用真實回應，其餘季別以 115Q2 半年值 ÷ 2 × 隨機係數（0.6～1.4，seed 10）合成；2408、2303 的 115Q3 給 `first_seen = 2026-11-06`。
- recalc：`sa10/recalc_harness.py` 把同一份模擬資料裝進 sqlite（EPS 以「分」存整數、查詢結果換回 `Decimal`，模擬 SQL Server 的精確小數），把 `twstock.db.connect` 換成 sqlite 後執行 `logs/iter10_recalc.py`。
- 結果：compare「✅ 相同」、`--keep-new` 判定 1,986 處不同；recalc「✅ 相同」（比對 `fin` 1,984 檔、screen 1,983 檔），竄改後判定 4 處不同；`test_iter01～10` 全過。
- 預覽：`python3 -m http.server 8001 --bind 127.0.0.1 --directory proj/site`，375 px。已關閉。

## 附錄 C：後端程式差異（`diff -ruN orig/twstock proj/twstock`；`collectors/financials.py` 為新檔全文）

```diff
diff -ruN -x __pycache__ -x *.pyc orig/twstock/__main__.py proj/twstock/__main__.py
--- orig/twstock/__main__.py	2026-11-05 22:07:47
+++ proj/twstock/__main__.py	2026-11-06 23:25:10
@@ -2,8 +2,8 @@
 台股資料收集與網站產生工具（Mac / Windows 通用）
 
   python -m twstock setup-db                         建立資料庫與資料表
-  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額（上市、上櫃））並匯出網站資料
-  python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行），有新資料才匯出；排程用這個
+  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額（上市、上櫃）；季報收集期間另收季報）並匯出網站資料
+  python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行；季報收集期間每天收一次季報），有新資料才匯出；排程用這個
   python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）：開頭列最後一次收集與排程狀態，有異常時印建議指令並回傳 1
   python -m twstock history --start 2026-01-01       補抓歷史（行情、本益比、法人、ETF、融資融券；只補缺的，可中斷重跑）
   python -m twstock history --start 2025-10-30 --only pe      只補本益比／淨值比／殖利率
@@ -12,9 +12,10 @@
   python -m twstock history --start 2026-07-31 --only amount  只補三大法人買賣金額（上市、上櫃；已有的市場自動略過）
   python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
   python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過）
+  python -m twstock history --start 2024-01-01 --only financials  只補季報（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
-  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/）
+  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/；含季報）
   python -m twstock serve                            本機預覽網站 http://localhost:8000
   python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
   python -m twstock chains                           更新產業鏈族群（櫃買產業價值鏈平台）
@@ -193,9 +194,10 @@
     s = sub.add_parser("history", help="補抓歷史資料")
     s.add_argument("--start", type=_date, required=True)
     s.add_argument("--end", type=_date, help="預設今天")
-    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "etf", "margin", "holdings"],
+    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "financials", "etf", "margin", "holdings"],
                    help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
-                        "amount = 上市、上櫃三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股）；"
+                        "amount = 上市、上櫃三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股，"
+                        "financials = 季報（季底日在 --start～--end 的季別））；"
                         "預設 prices pe insti etf margin")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
     s.add_argument("--no-revenue", action="store_true")
Binary files orig/twstock/__pycache__/__init__.cpython-313.pyc and proj/twstock/__pycache__/__init__.cpython-313.pyc differ
Binary files orig/twstock/__pycache__/config.cpython-313.pyc and proj/twstock/__pycache__/config.cpython-313.pyc differ
Binary files orig/twstock/__pycache__/db.cpython-313.pyc and proj/twstock/__pycache__/db.cpython-313.pyc differ
Binary files orig/twstock/__pycache__/fetch.cpython-313.pyc and proj/twstock/__pycache__/fetch.cpython-313.pyc differ
Binary files orig/twstock/collectors/__pycache__/__init__.cpython-313.pyc and proj/twstock/collectors/__pycache__/__init__.cpython-313.pyc differ
Binary files orig/twstock/collectors/__pycache__/financials.cpython-313.pyc and proj/twstock/collectors/__pycache__/financials.cpython-313.pyc differ
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/catchup.py proj/twstock/collectors/catchup.py
--- orig/twstock/collectors/catchup.py	2026-11-05 22:02:04
+++ proj/twstock/collectors/catchup.py	2026-11-06 23:37:00
@@ -14,13 +14,15 @@
 from .. import db, fetch, health
 from ..config import DB_CONFIG, SITE_DATA_DIR, tw_now
 from ..fetch import FetchError
-from ..health import REVENUE_DONE_RATIO, Row, due_days, evaluate, load_snapshot, load_state, medians, missing_keys
+from ..health import (REVENUE_DONE_RATIO, Row, due_days, evaluate, fin_done, fin_quarter_for, financial_counts, load_snapshot, load_state,
+                      medians, missing_keys)
 from ..tradingcal import (add_adhoc, is_adhoc_closure, is_trading_day, load_closed, remove_adhoc, trading_days,
                           update_calendar, warn_uncovered)
 from .alerts import collect_alerts
 from .chains import chains_age_days, update_chains
 from .daily import DAY_KEYS, PARSE_ERRORS, collect_for_date, collect_tpex_index
 from .events import LOOKBACK_DAYS, collect_events
+from .financials import collect_financials
 from .futures import collect_futures, collect_futures_institutional
 from .industry import update_industry
 from .revenue import collect_monthly_revenue, revenue_month_for
@@ -34,15 +36,15 @@
     return d.year, d.month
 
 
-def make_plan(now: datetime, n: int, snap: dict, state: dict, closed: set, revenue_counts=None) -> dict:
+def make_plan(now: datetime, n: int, snap: dict, state: dict, closed: set, revenue_counts=None, fin_counts=None) -> dict:
     """
     純函式：輸入現在時間、資料現況、執行紀錄、日曆；輸出待抓清單（不連網、不連資料庫）。
     days：評估範圍；by_date：[(日期, 鍵)]；tpex_months；futures、futures_oi：(起, 迄)；alerts：bool；
-    events：(起, 迄)；revenue：[(年, 月)]。
+    events：(起, 迄)；revenue：[(年, 月)]；financials：(年, 季) 或 None（第 10 輪：今天在季報窗口內、今天還沒收過、還沒收齊）。
     """
     days = due_days(now, n, closed)
     plan = {"days": days, "by_date": [], "tpex_months": [], "futures": None, "futures_oi": None,
-            "alerts": False, "events": None, "revenue": []}
+            "alerts": False, "events": None, "revenue": [], "financials": None}
     if not days:
         return plan
     med = medians(snap)
@@ -71,25 +73,31 @@
             prev = (y - 1, 12) if m == 1 else (y, m - 1)
             if revenue_counts.get((y, m), 0) < revenue_counts.get(prev, 0) * REVENUE_DONE_RATIO or not revenue_counts.get((y, m)):
                 plan["revenue"].append((y, m))
+    fq = fin_quarter_for(now.date())
+    if fq and fin_counts is not None and state.get("financials_on") != now.date() and not fin_done(fin_counts, *fq, now.date(), closed):
+        plan["financials"] = fq
     return plan
 
 
-def plan_for_date(d: date, now: datetime, closed_by_calendar: bool) -> dict:
-    """collect --date：該日全部重抓；行事曆上的休市日只處理沒有日期的資料。"""
+def plan_for_date(d: date, now: datetime, closed_by_calendar: bool, fin_counts=None, closed=()) -> dict:
+    """collect --date：該日全部重抓；行事曆上的休市日只處理沒有日期的資料。季報：d 在收集窗口內、該季還沒收齊才收（與 catch-up 相同的 98% 規則）。"""
     plan = {"days": [] if closed_by_calendar else [d], "by_date": [] if closed_by_calendar else [(d, DAY_KEYS)],
             "tpex_months": [] if closed_by_calendar else [month_key(d)],
             "futures": None if closed_by_calendar else (d, d), "futures_oi": None if closed_by_calendar else (d, d),
             "alerts": not closed_by_calendar, "events": None if closed_by_calendar else (d - timedelta(days=LOOKBACK_DAYS), d),
-            "revenue": []}
+            "revenue": [], "financials": None}
     month = revenue_month_for(d)
     if month and not closed_by_calendar:
         plan["revenue"] = [month]
+    fq = fin_quarter_for(d)
+    if fq and not closed_by_calendar and fin_counts is not None and not fin_done(fin_counts, *fq, now.date(), closed):
+        plan["financials"] = fq                        # 第 10 輪
     return plan
 
 
 def plan_is_empty(plan: dict) -> bool:
     return not (plan["by_date"] or plan["tpex_months"] or plan["futures"] or plan["futures_oi"]
-                or plan["alerts"] or plan["events"] or plan["revenue"])
+                or plan["alerts"] or plan["events"] or plan["revenue"] or plan.get("financials"))
 
 
 def _guard(key, errors, fn, *args):
@@ -126,6 +134,8 @@
     if plan["revenue"] and not no_revenue:
         if all([_guard("revenue", errors, collect_monthly_revenue, y, m) for y, m in plan["revenue"]]):
             undated["revenue"] = str(now.date())
+    if plan.get("financials") and _guard("financials", errors, collect_financials, *plan["financials"], now.date()):
+        undated["financials"] = str(now.date())     # 0 家（窗口剛開始）也算成功：同一天不再抓
     if wrote_prices:        # 新股票要有產業別；產業鏈 30 天更新一次
         _guard("industry", errors, update_industry)
         age = chains_age_days()
@@ -135,7 +145,8 @@
 
 
 def _undated_counts(cur) -> tuple:
-    return tuple(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("stock_alerts", "price_events", "monthly_revenue"))
+    return tuple(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
+                 for t in ("stock_alerts", "price_events", "monthly_revenue", "quarterly_financials"))
 
 
 def _revenue_counts(cur) -> dict:
@@ -233,9 +244,9 @@
             is_closed = not is_trading_day(date_, closed_for_run)
             if is_closed:
                 print(f"ℹ️  {date_} 休市，不發行情請求")
-            plan = plan_for_date(date_, now, is_closed)
+            plan = plan_for_date(date_, now, is_closed, financial_counts(cur), closed)
         else:
-            plan = make_plan(now, days, before, state, closed, _revenue_counts(cur))
+            plan = make_plan(now, days, before, state, closed, _revenue_counts(cur), financial_counts(cur))
     finally:
         conn.close()
 
@@ -273,7 +284,7 @@
         changed = any(before[k] != after[k] for k in before) or _undated_counts(cur) != undated_before
         items = evaluate(day_list, after, now, errors)
         result = health.outcome(items)
-        undated_errors = [k for k in errors if k in ("alerts", "events", "revenue", "industry", "chains")]
+        undated_errors = [k for k in errors if k in ("alerts", "events", "revenue", "financials", "industry", "chains")]
         if undated_errors:
             result = health.ABNORMAL
     finally:
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/daily.py proj/twstock/collectors/daily.py
--- orig/twstock/collectors/daily.py	2026-11-05 22:02:04
+++ proj/twstock/collectors/daily.py	2026-11-06 23:22:59
@@ -843,8 +843,9 @@
     written, errors, cache = {}, {}, {}
     for key in keys:
         dataset, _, market = key.partition(".")
-        if dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT) and written.get(f"prices.{market}") == 0:
-            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數、上櫃法人金額不可能先有，不發請求
+        # "amount"（上市法人金額）partition 後市場是空字串：視為 TWSE（第 10 輪 P24；鍵名不改）
+        if dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT) and written.get(f"prices.{market or 'TWSE'}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數、法人金額不可能先有，不發請求
         if dataset == "pe" and f"prices.{market}" in errors:
             continue                # 本益比只寫入有行情列的股票
         try:
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/financials.py proj/twstock/collectors/financials.py
--- orig/twstock/collectors/financials.py	1970-01-01 08:00:00
+++ proj/twstock/collectors/financials.py	2026-11-06 23:36:47
@@ -0,0 +1,129 @@
+"""
+季報（第 10 輪 B5）：公開資訊觀測站舊版「綜合損益表彙總」mopsov ajax_t163sb04。
+一個回應 = 一個市場、一季、全部業別（一般業、金控、銀行、證券、保險、其他各一張表），金額為「年初至今累計」（千元）。
+資料庫只存累計值；單季值在匯出時相減（export.fin_single），公司更正累計值時不會留下不一致。
+"""
+import html
+import re
+
+from .. import db
+from ..fetch import FetchError, SchemaError, clean_number, request
+
+URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"
+TYPEK = {"TWSE": "sii", "TPEx": "otc"}
+# 業別表：依表頭特徵辨識（不依賴表的順序），由上往下取第一個符合的
+TABLES = (("ci", ("營業毛利（毛損）淨額",)),                 # 一般業
+          ("fh", ("淨收益",)),                              # 金控（也有利息淨收益，所以排在銀行之前）
+          ("basi", ("利息淨收益",)),                         # 銀行
+          ("bd", ("收益", "支出及費用")),                     # 證券
+          ("ins", ("繼續營業單位稅前純益（純損）",)),          # 保險（113 年有營業收入、115 年 IFRS 17 後沒有）
+          ("mim", ("收入", "支出")))                          # 其他
+FIN_TBLS = ("fh", "basi", "bd", "ins")                       # 金融業：沒有毛利；提前結束收集要等金融業齊
+REVENUE = ("營業收入", "淨收益", "收益", "收入")             # 第一個存在的欄；銀行沒有合計欄、115 年起保險沒有收入欄 → NULL
+OP_INCOME = ("營業利益（損失）", "營業利益")                 # 證券、保險、一般業才有
+GROSS = "營業毛利（毛損）淨額"
+# 沒有子公司（個體報表）的公司「淨利歸屬於母公司業主」是 --，本期淨利就是歸屬於母公司的淨利（115Q2 上市 74 家）
+NET_ALONE = ("本期淨利（淨損）", "本期稅後淨利（淨損）")
+
+
+def _cells(tr: str) -> list:
+    return [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("\xa0", "").strip()
+            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
+
+
+def _col(idx: dict, names) -> int | None:
+    return next((idx[n] for n in names if n in idx), None)
+
+
+def parse_financials(text: str) -> dict:
+    """
+    {代號: {industry_tbl, revenue, gross_profit, op_income, net_income, eps}}（千元、元）。
+    表內只有標題列或還沒有任何公司公布 → {}；封鎖頁 → FetchError；
+    認不出業別、缺公司代號／基本每股盈餘／淨利歸屬於母公司業主欄 → SchemaError（整個回應都不寫入）。
+    """
+    tables = re.findall(r"<table class='hasBorder'.*?</table>", text, re.S)
+    if not tables:
+        if re.search(r"<h2>(上市|上櫃)公司.*?資料</h2>", text) or "查無" in text:
+            return {}                                       # 認得的頁面、還沒有公司公布
+        if "SECURITY" in text.upper():
+            raise FetchError("mopsov 回傳安全性封鎖頁面")
+        raise SchemaError("mopsov 綜合損益表彙總：回應沒有表格")
+    out = {}
+    for tb in tables:
+        rows = re.findall(r"<tr.*?</tr>", tb, re.S)
+        head = _cells(rows[0]) if rows else []
+        idx = {h: i for i, h in enumerate(head)}
+        tbl = next((t for t, need in TABLES if all(n in idx for n in need)), None)
+        eps = next((i for h, i in idx.items() if h.startswith("基本每股盈餘")), None)     # 保險業沒有「（元）」
+        ni = next((i for h, i in idx.items() if h.startswith("淨利") and h.endswith("歸屬於母公司業主")), None)
+        if tbl is None or "公司代號" not in idx or eps is None or ni is None:
+            raise SchemaError(f"mopsov 綜合損益表彙總：表頭不符（{'、'.join(head[:4])}…）")
+        rev, op, gp, alone = _col(idx, REVENUE), _col(idx, OP_INCOME), idx.get(GROSS), _col(idx, NET_ALONE)
+        num = lambda c, i: clean_number(c[i], int) if i is not None else None
+        for tr in rows[1:]:
+            c = _cells(tr)
+            if len(c) != len(head) or c[0] == "公司代號":
+                continue                                    # 分頁重複的表頭
+            out[c[idx["公司代號"]]] = {"industry_tbl": tbl, "revenue": num(c, rev), "gross_profit": num(c, gp),
+                                       "op_income": num(c, op), "net_income": num(c, ni) if num(c, ni) is not None else num(c, alone),
+                                       "eps": clean_number(c[eps])}
+    return out
+
+
+def fetch_financials(market: str, year: int, quarter: int) -> dict:
+    """year：西元年；quarter：1～4（4 = 全年）。"""
+    resp = request("POST", URL, expect_json=False, data={
+        "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1", "isQuery": "Y",
+        "TYPEK": TYPEK[market], "year": str(year - 1911), "season": f"{quarter:02d}"})
+    return parse_financials(resp.content.decode("utf-8", errors="replace"))
+
+
+def merge_financials(cursor, year: int, quarter: int, rows: list, first_seen) -> int:
+    """
+    MERGE 覆寫（更正財報）；只有值不同才更新、記 updated_at。first_seen 只在新增時寫入（補抓為 NULL），更新時不動。
+    只寫入 stocks 已有的股票（JOIN）。回傳新增＋更正的列數。
+    """
+    cursor.execute("""
+        MERGE quarterly_financials AS t
+        USING (
+            SELECT st.stock_id, j.*
+            FROM OPENJSON(?) WITH (
+                stock_code NVARCHAR(10), industry_tbl NVARCHAR(10), revenue BIGINT, gross_profit BIGINT,
+                op_income BIGINT, net_income BIGINT, eps DECIMAL(10,2)
+            ) AS j
+            JOIN stocks st ON st.stock_code = j.stock_code
+        ) AS s
+        ON t.stock_id = s.stock_id AND t.fin_year = ? AND t.fin_quarter = ?
+        WHEN MATCHED AND EXISTS (SELECT s.industry_tbl, s.revenue, s.gross_profit, s.op_income, s.net_income, s.eps
+                                 EXCEPT SELECT t.industry_tbl, t.revenue, t.gross_profit, t.op_income, t.net_income, t.eps)
+            THEN UPDATE SET industry_tbl = s.industry_tbl, revenue = s.revenue, gross_profit = s.gross_profit,
+                            op_income = s.op_income, net_income = s.net_income, eps = s.eps, updated_at = GETDATE()
+        WHEN NOT MATCHED THEN
+            INSERT (stock_id, fin_year, fin_quarter, industry_tbl, revenue, gross_profit, op_income, net_income, eps, first_seen)
+            VALUES (s.stock_id, ?, ?, s.industry_tbl, s.revenue, s.gross_profit, s.op_income, s.net_income, s.eps, ?);
+    """, db.to_json(rows), year, quarter, year, quarter, first_seen)
+    return cursor.rowcount
+
+
+def collect_financials(year: int, quarter: int, first_seen=None, markets=("TWSE", "TPEx")) -> int:
+    """
+    抓取並寫入一季（每個市場 1 個請求）。first_seen：日常收集傳今天、補抓傳 None。
+    回傳回應家數（含 stocks 沒有的公司；0 = 還沒有公司公布，不是錯誤）。
+    """
+    total = 0
+    for market in markets:
+        got = fetch_financials(market, year, quarter)
+        rows = [{"stock_code": c, **r} for c, r in got.items()]
+        conn = db.connect()
+        try:
+            cur = conn.cursor()
+            known = {r[0] for r in cur.execute("SELECT stock_code FROM stocks").fetchall()}
+            skipped = sorted(c for c in got if c not in known)
+            changed = merge_financials(cur, year, quarter, rows, first_seen) if rows else 0
+            conn.commit()
+        finally:
+            conn.close()
+        print(f"    📑 {market} {year}Q{quarter}：回應 {len(got)} 家，新增或更正 {changed} 家"
+              + (f"，略過 {len(skipped)} 家（stocks 沒有：{'、'.join(skipped[:5])}{'…' if len(skipped) > 5 else ''}）" if skipped else ""))
+        total += len(got)
+    return total
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/history.py proj/twstock/collectors/history.py
--- orig/twstock/collectors/history.py	2026-11-05 22:02:04
+++ proj/twstock/collectors/history.py	2026-11-06 23:22:38
@@ -5,7 +5,7 @@
 加 force=True 則已存在的日期也重新抓取並覆寫。
 """
 import time
-from datetime import date
+from datetime import date, timedelta
 
 from .. import db
 from ..config import tw_now
@@ -14,8 +14,12 @@
 from ..tradingcal import HOLIDAYS, is_trading_day, load_closed, trading_days  # noqa: F401（沿用的對外名稱）
 from .daily import (ALL_DATASETS, DATASET_KEYS, DAY_KEYS, HOLDINGS_KEYS, INDEX, PARSE_ERRORS, PRICES, TPEX_INDEX,  # noqa: F401
                     collect_for_date, collect_tpex_index)
+from .financials import collect_financials
 from .revenue import collect_monthly_revenue, revenue_month_for
 
+FINANCIALS = "financials"       # history --only financials：季報（第 10 輪），不在預設資料集
+SECONDS_PER_QUARTER = 4.5       # mopsov 節流 3 秒＋約 1.6 MB 回應
+
 # 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
 SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
                    "index.TAIEX": 4, "amount": 4, "amount.TPEx": 3.2, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
@@ -40,9 +44,55 @@
     return sum(SECONDS_PER_KEY[k] for k in keys if SHARED.get(k) not in keys)
 
 
+def fin_quarters(start: date, end: date, today: date) -> list:
+    """季底日落在 start～end、而且收集窗口已開始（季底 + 15 天 ≤ today）的季別 [(年, 季)]，舊到新。"""
+    out = []
+    for y in range(start.year, end.year + 1):
+        for q in range(1, 5):
+            qe = date(y, 12, 31) if q == 4 else date(y, q * 3 + 1, 1) - timedelta(days=1)
+            if start <= qe <= end and qe + timedelta(days=15) <= today:
+                out.append((y, q))
+    return out
+
+
+def load_fin_have() -> set:
+    """資料庫已有的 (年, 季, 市場)。"""
+    conn = db.connect()
+    try:
+        return {tuple(r) for r in conn.cursor().execute(
+            "SELECT DISTINCT q.fin_year, q.fin_quarter, s.market_type FROM quarterly_financials q "
+            "JOIN stocks s ON s.stock_id = q.stock_id").fetchall()}
+    finally:
+        conn.close()
+
+
+def run_financials(start: date, end: date, force=False) -> tuple:
+    """季報補抓：每季每市場 1 個請求；已有的 (季, 市場) 略過（force 才重抓）；first_seen 一律 NULL。回傳 (完成, 錯誤說明)。"""
+    have = set() if force else load_fin_have()
+    todo = [(y, q, m) for y, q in fin_quarters(start, end, tw_now().date()) for m in ("TWSE", "TPEx") if (y, q, m) not in have]
+    print(f"\n📑 季報：待抓 {len(todo)} 次（季別 × 市場）；⏱️  預估約 {len(todo) * SECONDS_PER_QUARTER / 60:.1f} 分鐘")
+    for y, q, m in todo:
+        try:
+            collect_financials(y, q, None, (m,))
+        except FetchError as e:
+            return False, f"在 {y}Q{q} {m} 停止：疑似被限流封鎖（{e}）"
+        except PARSE_ERRORS as e:
+            return False, f"在 {y}Q{q} {m} 停止：官方欄位不符（{e}），需要修改程式"
+    return True, ""
+
+
 def run_history(start: date, end: date, datasets=ALL_DATASETS, force=False,
                 revenue=True, delay=0.0) -> bool:
     """回傳 True = 全部完成；False = 中途疑似被封鎖或欄位不符而停止。"""
+    if FINANCIALS in datasets:      # 季報不依交易日；只有 --only financials 時才抓
+        ok, why = run_financials(start, end, force)
+        if not ok:
+            print(f"❌ {why}\n   建議等 30 分鐘以上，再用同樣的指令重跑；已寫入的季別會自動跳過。")
+            return False
+        datasets = tuple(ds for ds in datasets if ds != FINANCIALS)
+        if not datasets:
+            print("🎉 補抓完成！")
+            return True
     closed, snap, med = load_status(start, end)
     days = trading_days(start, end, closed)
     wanted = {k for ds in datasets if ds != TPEX_INDEX for k in DATASET_KEYS[ds]}
diff -ruN -x __pycache__ -x *.pyc orig/twstock/db.py proj/twstock/db.py
--- orig/twstock/db.py	2026-11-05 22:02:04
+++ proj/twstock/db.py	2026-11-06 23:24:33
@@ -448,6 +448,28 @@
         CONSTRAINT UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)
     )
     """,
+    # 季報（第 10 輪 B5）：mopsov 綜合損益表彙總的「年初至今累計」（千元、元），單季在匯出時相減；
+    # industry_tbl = 解析自哪一張表（ci 一般業、fh 金控、basi 銀行、bd 證券、ins 保險、mim 其他）；
+    # first_seen = 日常收集第一次收到的日期（補抓寫入為 NULL，更新時不動）
+    """
+    IF OBJECT_ID('quarterly_financials') IS NULL
+    CREATE TABLE quarterly_financials (
+        id            INT IDENTITY(1,1) PRIMARY KEY,
+        stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
+        fin_year      INT            NOT NULL,
+        fin_quarter   TINYINT        NOT NULL CHECK (fin_quarter BETWEEN 1 AND 4),
+        industry_tbl  NVARCHAR(10)   NOT NULL CHECK (industry_tbl IN ('ci','fh','basi','bd','ins','mim')),
+        revenue       BIGINT         NULL,
+        gross_profit  BIGINT         NULL,
+        op_income     BIGINT         NULL,
+        net_income    BIGINT         NULL,
+        eps           DECIMAL(10,2)  NULL,
+        first_seen    DATE           NULL,
+        created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
+        updated_at    DATETIME       NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)
+    )
+    """,
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -485,5 +507,5 @@
     print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
           "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
-          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、"
+          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、quarterly_financials、"
           "etf_holding_gaps")
diff -ruN -x __pycache__ -x *.pyc orig/twstock/export.py proj/twstock/export.py
--- orig/twstock/export.py	2026-11-05 22:02:04
+++ proj/twstock/export.py	2026-11-06 23:23:52
@@ -6,7 +6,7 @@
                      已支援持股的主動 ETF（holdings）、市場寬度（breadth）
   screen.json        條件選股與排行擴充：每檔股票的價量、營收、融資融券欄位（欄式，和 latest.json stocks 合併使用）
   stocks/{代號}.json 個股：完整日線、法人買賣超、月營收、本益比、所屬產業鏈、最新融資融券、主動 ETF 持有（active）、
-                     融資融券序列（mg）、投信買超中的主動 ETF（act）
+                     融資融券序列（mg）、投信買超中的主動 ETF（act）、季報（fin，第 10 輪）
   etfs/{代號}.json   主動 ETF 持股：近 HOLD_DAYS 個持股日的張數與權重、最新一天的增減
 """
 import json
@@ -22,7 +22,7 @@
 from .analysis.flow import LONG, group_flows, load_concepts, streak
 from .analysis.forecast import build_forecast, load_oi
 from .config import SITE_DATA_DIR, tw_now
-from .health import HOLDINGS, build_status
+from .health import HOLDINGS, build_status, fin_quarter_for, prev_quarter
 
 REPLAY = 20                    # 泡泡圖回放天數
 FUTURES_DAYS = 500             # 首頁台指期日 K 匯出天數
@@ -45,10 +45,12 @@
 NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
-               "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp")
+               "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
+               "eq", "ey", "e4", "gm", "gmy", "fq", "eh")
 VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
 VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
 VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
+FIN_QUARTERS = 8                # 第 10 輪 B5：個股季報卡的季數
 _TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
           (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
 
@@ -723,11 +725,112 @@
     return {"rm": y * 100 + m, "ry": yoy, "rc": cum, "rh": hi, "r3": int(r3)}
 
 
+# ─── 第 10 輪 B5：季報（資料庫存累計值，這裡相減成單季；個股與選股共用）──────
+def _r1(a, b):
+    """a ÷ b × 100，四捨五入（ROUND_HALF_UP）到 1 位小數。"""
+    return float((Decimal(a) * 100 / Decimal(b)).quantize(Decimal("0.1"), ROUND_HALF_UP))
+
+
+def fin_single(cum: dict, y: int, q: int):
+    """
+    單季 [營收, 毛利, 營益, 淨利, EPS]：Q1 = 累計；Q2～Q4 = 本季累計 − 上一季累計（Q4 = 全年 − Q3 累計）。
+    cum = {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}；該季沒有 → None；上一季沒有或該欄 NULL → 該欄 None（不以累計頂替）。
+    """
+    cur = cum.get((y, q))
+    if cur is None:
+        return None
+    prev = None if q == 1 else cum.get((y, q - 1))
+    if q == 1:
+        return list(cur)
+    return [a - b if prev is not None and a is not None and b is not None else None for a, b in zip(cur, prev or (None,) * 5)]
+
+
+def fin_yoy(v, base):
+    """年增 %：去年同期 ≤ 0 或任一缺 → None（畫面寫「轉盈」等）。"""
+    return None if v is None or base is None or base <= 0 else _r1(v - base, base)
+
+
+def fin_margin(x, rev):
+    """毛利率、營益率 %：單季營收 ≤ 0 或缺 → None。"""
+    return None if x is None or rev is None or rev <= 0 else _r1(x, rev)
+
+
+def fin_e4(cum: dict, y: int, q: int):
+    """近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計（四項缺一 → None）；Q4 = 全年。"""
+    if q == 4:
+        return cum[(y, 4)][4] if (y, 4) in cum else None
+    xs = [cum.get(k, (None,) * 5)[4] for k in ((y, q), (y - 1, 4), (y - 1, q))]
+    return None if None in xs else xs[0] + xs[1] - xs[2]
+
+
+def fin_stock(cum: dict, tbl: str, seen):
+    """stocks/{代號}.json 的 fin；沒有任何季報 → None。q：近 8 季（有累計值的季別，舊到新）[季別, 單季 EPS, EPS 年增, 毛利率, 營益率, 單季營收]。"""
+    if not cum:
+        return None
+    y, q = max(cum)
+    keys, k = [], (y, q)
+    for _ in range(FIN_QUARTERS):
+        keys.append(k)
+        k = prev_quarter(*k)
+    rows = []
+    for yy, qq in reversed(keys):
+        if (yy, qq) not in cum:
+            continue
+        s, b = fin_single(cum, yy, qq), fin_single(cum, yy - 1, qq)
+        rows.append([yy * 100 + qq, _f(s[4]), fin_yoy(s[4], b and b[4]), fin_margin(s[1], s[0]), fin_margin(s[2], s[0]), s[0]])
+    e, eb = cum[(y, q)][4], cum.get((y - 1, q), (None,) * 5)[4]
+    return {"t": tbl, "q": rows, "c": {"e": _f(e), "ey": fin_yoy(e, eb), **({"fs": str(seen)} if seen else {})},
+            "e4": _f(fin_e4(cum, y, q)), "e4p": _f(fin_e4(cum, y - 1, q))}
+
+
+def fin_screen(cum: dict) -> dict:
+    """screen.json 的季報欄（最新一季）：eq 單季 EPS、ey 年增 %、e4 近 4 季、gm 毛利率、gmy 毛利率年增（百分點）、fq 季別、eh 創 N 季新高。"""
+    if not cum:
+        return dict.fromkeys(("eq", "ey", "e4", "gm", "gmy", "fq", "eh"))
+    y, q = max(cum)
+    s, b = fin_single(cum, y, q), fin_single(cum, y - 1, q)
+    gm, gmb = fin_margin(s[1], s[0]), b and fin_margin(b[1], b[0])
+    eh, k = 0, prev_quarter(y, q)          # 單季 EPS 高於之前連續 eh 季
+    while s[4] is not None and (p := fin_single(cum, *k)) and p[4] is not None and p[4] < s[4]:
+        eh += 1
+        k = prev_quarter(*k)
+    return {"eq": _f(s[4]), "ey": fin_yoy(s[4], b and b[4]), "e4": _f(fin_e4(cum, y, q)), "gm": gm,
+            "gmy": _f(gm - gmb, 1) if gm is not None and gmb is not None else None, "fq": y * 100 + q, "eh": eh}
+
+
+def fin_progress(counts: dict, d):
+    """今日頁一行：資料日在季報窗口內、當季已有資料時 {q, n: {市場: 家數}, p: {市場: 前一季家數}}；否則 None。"""
+    fq = fin_quarter_for(d)
+    if not fq:
+        return None
+    n = {m: counts.get((*fq, m), 0) for m in ("TWSE", "TPEx")}
+    if not any(n.values()):
+        return None
+    pq = prev_quarter(*fq)
+    return {"q": fq[0] * 100 + fq[1], "n": n, "p": {m: counts.get((*pq, m), 0) for m in ("TWSE", "TPEx")}}
+
+
+def _load_financials(cur) -> tuple:
+    """({代號: {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}}, {代號: (最新一季業別, 最新一季 first_seen)}, {(年, 季, 市場): 家數})。"""
+    fin, meta, counts = defaultdict(dict), {}, Counter()
+    for code, mkt, y, q, tbl, *vals, seen in cur.execute("""
+        SELECT s.stock_code, s.market_type, f.fin_year, f.fin_quarter, f.industry_tbl,
+               f.revenue, f.gross_profit, f.op_income, f.net_income, f.eps, f.first_seen
+        FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
+        ORDER BY s.stock_code, f.fin_year, f.fin_quarter"""):
+        fin[code][(y, q)] = tuple(vals)
+        meta[code] = (tbl, seen)
+        counts[(y, q, mkt)] += 1
+    return fin, meta, counts
+
+
 def screen_build(rows, head):
     """screen.json：欄式。rows：{代號: {SCREEN_KEYS…}}（依代號排序）；head：d、fd、md。rmd = 各營收月份的檔數。"""
     codes = sorted(rows)
     rmd = Counter(rows[c]["rm"] for c in codes if rows[c]["rm"] is not None)
-    return {**head, "rmd": {str(k): v for k, v in sorted(rmd.items(), reverse=True)}, "codes": codes,
+    fqd = Counter(rows[c]["fq"] for c in codes if rows[c].get("fq") is not None)        # 第 10 輪：各季報季別的檔數
+    return {**head, "rmd": {str(k): v for k, v in sorted(rmd.items(), reverse=True)},
+            "fqd": {str(k): v for k, v in sorted(fqd.items(), reverse=True)}, "codes": codes,
             **{k: [rows[c][k] for c in codes] for k in SCREEN_KEYS}}
 
 
@@ -880,6 +983,7 @@
     b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
     status = build_status(cur, latest_date, now)
     valuation, stock_val, val_date = _load_valuation(cur)      # F9-4
+    fin, fin_meta, fin_counts = _load_financials(cur)          # 第 10 輪 B5
     conn.close()
     mlast = {m: ds[-1] for m, ds in mdates.items()}
     m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
@@ -947,6 +1051,7 @@
                       "t": [round(x / 1000) if x is not None else None for x in tn],
                       "dl": [round(x / 1000) if x is not None else None for x in dn]},
             "revenue": rev_rows[-REVENUE_MONTHS:],
+            **({"fin": fb} if (fb := fin_stock(fin.get(code), *fin_meta.get(code, (None, None)))) else {}),   # 第 10 輪 B5
             "fund": dict(zip(("pe", "pb", "dy"), map(_f, fund[code][:3])), date=str(fund[code][3]))
                     if code in fund else None,
             **({"capchg": cap} if cap else {}),
@@ -1035,7 +1140,8 @@
                                       tv, b_days, idx_close[mkt]),
                         **revenue_stats(rev_rows), "cap": int(cap is not None),
                         **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt),
-                        "pbp": (stock_val.get(code) or {}).get("pb", [None])[0]}     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
+                        "pbp": (stock_val.get(code) or {}).get("pb", [None])[0],     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
+                        **fin_screen(fin.get(code))}                                  # 第 10 輪 B5
 
     industries = defaultdict(list)
     for code in snapshot:
@@ -1060,6 +1166,7 @@
         "insti_official": _insti_official(amount["TWSE"]),
         "insti_official_tpex": _insti_official(amount["TPEx"]),      # 第 9 輪 F9-1：上櫃官方（結構同 insti_official）
         "valuation": valuation,                                      # 第 9 輪 F9-4：市場估值一年位置
+        "fin_progress": fin_progress(fin_counts, latest_date),       # 第 10 輪 B5：季報公布進度（窗口外 null）
         "insti_otc": {k: round(v, 1) for k, v in insti_otc.items()},
         "index": {code: {"date": str(rows[-1][0]), "c": _f(rows[-1][1]), "ch": _f(rows[-1][2]),
                          "p": _f(_pct(rows[-1][1], rows[-1][2])), "from": str(rows[-INDEX_DAYS:][0][0]),
@@ -1091,7 +1198,8 @@
     _write(SITE_DATA_DIR / "latest.json", latest)
     size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
     print(f"  📌 screen.json {(SITE_DATA_DIR / 'screen.json').stat().st_size / 1024:.0f} KB（營收月份 " +
-          "、".join(f"{k[:4]}/{k[4:]} {v:,} 檔" for k, v in S["rmd"].items()) + "）")
+          "、".join(f"{k[:4]}/{k[4:]} {v:,} 檔" for k, v in S["rmd"].items()) + "；季報 " +
+          ("、".join(f"{k[:4]}Q{k[5]} {v:,} 檔" for k, v in S["fqd"].items()) or "無") + "）")
     print(f"  📌 還原事件 {n_ev} 筆（上櫃反推 {n_inferred} 筆）")
     if bad_all:
         print(f"⚠️  還原係數超出 {ADJ_MIN}～{ADJ_MAX}，未採用 {len(bad_all)} 筆：" +
diff -ruN -x __pycache__ -x *.pyc orig/twstock/health.py proj/twstock/health.py
--- orig/twstock/health.py	2026-11-05 22:02:04
+++ proj/twstock/health.py	2026-11-06 23:22:19
@@ -38,6 +38,11 @@
 AMOUNT_TPEX_FROM = date(2026, 7, 31)    # 上櫃官方法人金額（第 9 輪）：和上市 insti_amount 同一個起點
 REVENUE_DONE_RATIO = 0.98               # 月營收：該月家數 ≥ 前一月 × 98% 視為公布完成（catchup 共用）
 REVENUE_DUE_DAY = 10                    # 月營收法定公布期限：每月 10 日
+# 季報（第 10 輪 B5）：收集窗口 = 季底後第 15 天起，到「金融業截止日 + 7 天」；Q4（年報）窗口在次年。月、日
+FIN_WINDOW = {1: ((4, 15), (6, 6)), 2: ((7, 15), (9, 7)), 3: ((10, 15), (12, 6)), 4: ((1, 15), (4, 7))}
+# 申報期限（mopsov 註 1）：(一般業, 金融業)。金融業 = 金控、銀行、證券、保險，取最晚的金控；Q2 的銀行、證券、保險也是 8/31
+FIN_DUE = {1: ((5, 15), (5, 30)), 2: ((8, 14), (8, 31)), 3: ((11, 14), (11, 29)), 4: ((3, 31), (3, 31))}
+FIN_DONE_RATIO = 0.98                   # 季報：總家數 ≥ 上一季 × 98%，且金融業家數 ≥ 上一季（或已過金融業截止日）視為齊
 
 SPECS = (
     Spec("prices.TWSE", "上市行情", 800, False), Spec("prices.TPEx", "上櫃行情", 650, False),
@@ -219,10 +224,10 @@
 # ─── 執行紀錄 ─────────────────────────────────────────────
 def load_state(cur) -> dict:
     """
-    由最近 200 筆執行紀錄整理：處置注意股、事件、營收最後成功的時間，最後一次有新資料的時間，
+    由最近 200 筆執行紀錄整理：處置注意股、事件、營收、季報（financials_on）最後成功的時間，最後一次有新資料的時間，
     與最後一次收集（last_run：時間、指令、有無新資料）。
     """
-    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "collected_at": None, "last_run": None}
+    state = {"alerts_at": None, "events_to": None, "revenue_on": None, "financials_on": None, "collected_at": None, "last_run": None}
     for finished, new_data, detail, *extra in cur.execute(
             "SELECT TOP 200 finished_at, new_data, detail, command FROM collect_runs ORDER BY run_id DESC").fetchall():
         if state["last_run"] is None:
@@ -236,6 +241,8 @@
             state["events_to"] = date.fromisoformat(und["events_to"])
         if und.get("revenue") and state["revenue_on"] is None:
             state["revenue_on"] = date.fromisoformat(und["revenue"])
+        if und.get("financials") and state["financials_on"] is None:
+            state["financials_on"] = date.fromisoformat(und["financials"])
     return state
 
 
@@ -332,8 +339,77 @@
     return ABNORMAL, f"{head}，最後一次收集營收 {revenue_on or '尚無紀錄'}"
 
 
-def check_report(days, snap, now, state, closed, adhoc=(), schedule=None, revenue=None) -> tuple:
-    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）；revenue = 各月營收家數（None 不印營收一行）。"""
+def fin_quarter_for(d: date):
+    """d 落在哪一季的收集窗口：(西元年, 季)；窗口外 None。Q4 窗口（1/15～4/07）的季別是前一年 Q4。"""
+    for q, ((m1, d1), (m2, d2)) in FIN_WINDOW.items():
+        if (m1, d1) <= (d.month, d.day) <= (m2, d2):
+            return (d.year - 1, 4) if q == 4 else (d.year, q)
+    return None
+
+
+def fin_latest_quarter(d: date) -> tuple:
+    """check 顯示的季別：窗口內 → 該季；窗口外 → 最近一個已結束窗口的季別。回傳 (年, 季, 是否在窗口內)。"""
+    for back in range(0, 400):
+        x = d - timedelta(days=back)
+        q = fin_quarter_for(x)
+        if q:
+            return (*q, back == 0)
+    raise ValueError(d)
+
+
+def prev_quarter(y: int, q: int) -> tuple:
+    return (y - 1, 4) if q == 1 else (y, q - 1)
+
+
+def fin_due(y: int, q: int, closed) -> tuple:
+    """(一般業截止日, 金融業截止日, 一般業截止後第一個交易日, 金融業截止後第一個交易日)。Q4 的截止日在次年。"""
+    yy = y + 1 if q == 4 else y
+    gen, fin = (date(yy, *md) for md in FIN_DUE[q])
+    after = lambda d: trading_days(d + timedelta(days=1), d + timedelta(days=30), closed)[0]
+    return gen, fin, after(gen), after(fin)
+
+
+def fin_done(counts: dict, y: int, q: int, today: date, closed) -> bool:
+    """
+    季報收齊（提前結束收集與 check ✅ 共用）。counts = {(年, 季): (總家數, 金融業家數)}。
+    1. 總家數 > 0 且 ≥ 上一季 × 98%（上一季沒有資料時不算齊：繼續收到窗口結束）；而且
+    2. 金融業家數 ≥ 上一季，或今天已過金融業截止日後的第一個交易日。
+    """
+    n, nf = counts.get((y, q), (0, 0))
+    pn, pf = counts.get(prev_quarter(y, q), (0, 0))
+    return bool(n and pn and n >= pn * FIN_DONE_RATIO and (nf >= pf or today > fin_due(y, q, closed)[3]))
+
+
+def financials_status(today: date, counts: dict, fin_on, closed) -> tuple:
+    """
+    季報一行（第 10 輪 B5）：(狀態, 文字)。✅ fin_done；ℹ️ 窗口外未齊（不計異常）；窗口內未齊：
+    ⏳ 今天 ≤ 一般業截止後第一個交易日，或只差金融業且今天 ≤ 金融業截止後第一個交易日；
+    ⏳ 晚交：fin_on（最後一次成功收集季報的日期）是今天或前一個交易日；❌ 其餘（收集停了）。
+    """
+    y, q, inside = fin_latest_quarter(today)
+    n, nf = counts.get((y, q), (0, 0))
+    pn, pf = counts.get(prev_quarter(y, q), (0, 0))
+    gen, fin, gen_td, fin_td = fin_due(y, q, closed)
+    name = "年報" if q == 4 else f"第 {q} 季財報"
+    head = (f"{name} {y}Q{q}：已收 {n:,} 家" + (f"（前一季 {pn:,} 家的 {n / pn:.0%}）" if pn else "")
+            + (f"，金融業 {nf}／{pf} 家" if pf else ""))
+    if fin_done(counts, y, q, today, closed):
+        return OK, f"{head}，✅ 已齊"
+    if not inside:
+        end = date(y + 1 if q == 4 else y, *FIN_WINDOW[q][1])
+        return "info", f"{head}，ℹ️ 收集期間已結束（{end:%m/%d}），不再收集"
+    if today <= gen_td or (pn and n >= pn * FIN_DONE_RATIO and today <= fin_td):
+        due = f"{gen:%m/%d} 截止" if gen == fin else f"一般業 {gen:%m/%d}、金融業 {fin:%m/%d} 截止"
+        return PENDING, f"{head}，⏳ 公布期間（{due}）"
+    before = trading_days(today - timedelta(days=30), today - timedelta(days=1), closed)
+    if fin_on and (fin_on >= today or (before and fin_on >= before[-1])):
+        return PENDING, f"{head}，⏳ 晚交公司陸續補進（最後收集 {fin_on:%m/%d}）"
+    return ABNORMAL, f"{head}，最後一次收集季報 {fin_on or '尚無紀錄'}"
+
+
+def check_report(days, snap, now, state, closed, adhoc=(), schedule=None, revenue=None, financials=None) -> tuple:
+    """回傳 (輸出文字, 回傳碼)。純函式：不連資料庫、不發請求；schedule 由呼叫端傳入（schedule_status()）；revenue = 各月營收家數（None 不印營收一行）；
+    financials = 各季季報家數 {(年, 季): (總家數, 金融業家數)}（None 不印季報一行）。"""
     items, med = evaluate(days, snap, now), medians(snap)
     out = [f"📋 資料完整性檢查：近 {len(days)} 個交易日 {days[0]} ～ {days[-1]}（現在 {now:%Y-%m-%d %H:%M}，台灣時間）",
            f"🕘 最後一次收集：{last_run_line(state.get('last_run'))}"]
@@ -366,6 +442,9 @@
     rev = revenue_status(now.date(), revenue, state.get("revenue_on"), closed) if revenue is not None else None
     if rev:
         out.append(rev[1] if rev[0] != ABNORMAL else f"{rev[1]}，❌ 異常")
+    fin = financials_status(now.date(), financials, state.get("financials_on"), closed) if financials is not None else None
+    if fin:
+        out.append(fin[1] if fin[0] != ABNORMAL else f"{fin[1]}，❌ 異常")
     lines = problem_lines(items, state.get("last_run"))
     # 處置／注意股端點只有近幾日，錯過無法回補：落後 2 個交易日以上算異常；沒有紀錄不算（還沒跑過）
     stale = alerts and len(trading_days(alerts.date() + timedelta(days=1), days[-1], closed)) >= 2
@@ -373,11 +452,13 @@
         lines.insert(0, f"❌ 處置／注意股：最後成功 {alerts.date()}，端點只有近幾日，請盡快執行 collect --catch-up")
     if rev and rev[0] == ABNORMAL:
         lines.append(f"❌ {rev[1]}：已過 {REVENUE_DUE_DAY} 日仍未收齊，收集可能停了")
+    if fin and fin[0] == ABNORMAL:
+        lines.append(f"❌ {fin[1]}：已過申報截止日仍未收齊，收集可能停了")
     abnormal = sum(ln.startswith("❌") for ln in lines)
     out += ["", *lines] if lines else []
     out.append(f"\n結果：異常 {abnormal} 項" if abnormal else "\n結果：無異常")
     if abnormal:
-        out.append(suggest(items, days, bool(stale) or bool(rev and rev[0] == ABNORMAL)))
+        out.append(suggest(items, days, bool(stale) or bool(rev and rev[0] == ABNORMAL) or bool(fin and fin[0] == ABNORMAL)))
     return "\n".join(out), (1 if abnormal else 0)
 
 
@@ -387,6 +468,13 @@
         "SELECT revenue_year, revenue_month, COUNT(*) FROM monthly_revenue GROUP BY revenue_year, revenue_month").fetchall()}
 
 
+def financial_counts(cur) -> dict:
+    """{(年, 季): (總家數, 金融業家數)}；catchup 與 check 共用。"""
+    return {(y, q): (n, nf) for y, q, n, nf in cur.execute(
+        "SELECT fin_year, fin_quarter, COUNT(*), SUM(CASE WHEN industry_tbl IN ('fh','basi','bd','ins') THEN 1 ELSE 0 END) "
+        "FROM quarterly_financials GROUP BY fin_year, fin_quarter").fetchall()}
+
+
 def run_check(n: int, now: datetime) -> int:
     from . import db
     conn = db.connect()
@@ -398,11 +486,12 @@
         start = due_days(now, max(n, MEDIAN_DAYS), closed)[0]
         snap, state = load_snapshot(cur, start, days[-1]), load_state(cur)
         revenue = revenue_counts(cur)
+        financials = financial_counts(cur)
         adhoc = [r[0] for r in cur.execute("SELECT holiday_date FROM market_holidays WHERE source = 'adhoc' AND holiday_date BETWEEN ? AND ? "
                                            "ORDER BY holiday_date", start, days[-1]).fetchall()]
     finally:
         conn.close()
-    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status(), revenue)
+    text, rc = check_report(days, snap, now, state, closed, adhoc, schedule_status(), revenue, financials)
     print(text)
     return rc
 
```

## 附錄 D：前端差異（`site/app.js`、`site/stock.js`、`site/app.css`）

```diff
--- orig/site/app.js	2026-11-05 22:28:48
+++ proj/site/app.js	2026-11-06 23:27:22
@@ -298,8 +298,16 @@
       <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
       ${row(V.TWSE, '上市')}${row(V.TPEx, '上櫃')}
       ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
+      ${finLine(L.fin_progress)}
       <div class="s">一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號</div>
     </div>`;
+}
+
+// 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
+function finLine(P) {
+  if (!P) return '';
+  const q = P.q % 100, name = q === 4 ? `${Math.floor(P.q / 100)} 年報` : `第 ${q} 季財報`;
+  return `<div class="s">${name}已收：上市 ${fmt(P.n.TWSE)}、上櫃 ${fmt(P.n.TPEx)} 家（前一季 ${fmt(P.p.TWSE)}、${fmt(P.p.TPEx)} 家）；本益比中位數會隨 EPS 更新而變動</div>`;
 }
 
 // 三大法人卡：上市（A2）、上櫃（第 9 輪 F9-1）都用官方金額；上櫃官方還沒有任何資料時退回估算一行；上市也沒有時維持第 1 輪估算卡
@@ -779,6 +787,10 @@
 const revMonth = () => Object.entries(App.screen?.rmd || {}).sort((a, b) => b[1] - a[1])[0]?.[0];
 // 第 9 輪 F9-2：營收月份混雜（兩個以上月份，且最多的月份不到 98%）→ 資料日一列加公布期間說明
 const revMixed = S => { const n = Object.values(S.rmd || {}), t = n.reduce((a, b) => a + b, 0); return n.length > 1 && Math.max(...n) < t * 0.98; };
+// 第 10 輪 B5：季報季別（YYYYQQ，例如 202603）同營收月份的做法：欄名用檔數最多的季別，季別不同的列加小字
+const finQ = () => Object.entries(App.screen?.fqd || {}).sort((a, b) => b[1] - a[1])[0]?.[0];
+const finMixed = S => revMixed({ rmd: S.fqd });
+const finTag = x => x.fq && String(x.fq) !== finQ() ? `<span class="muted small">（Q${x.fq % 100}）</span>` : '';
 
 // 結果表的動態欄：[欄名, 取值, 格式, 預設方向（1 遞增）]
 const spct = v => v == null ? '--' : sgn(v) + '%';
@@ -802,18 +814,21 @@
   rc: ['累計年增', x => x.rc, spct], rh: ['營收新高(年)', x => x.rh, int0], r3: ['連3月年增', x => x.r3, v => v === 1 ? '✓' : '--'],
   pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
   pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
+  eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => spct(v) + finTag(x)],
+  e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, v => fmt(v, 1) + '%'],
+  gmy: ['毛利率年增', x => x.gmy, v => sgn(v, 1) + '點'], eh: ['EPS新高(季)', x => x.eh, int0],
 };
 const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
 // 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動}；sort 有值時欄名可點排序
 function screenTable(list, cols, o = {}) {
-  const head = k => { const c = SCR_COLS[k], M = revMonth();
-    return k === 'ry' && M ? `營收年增（${Number(M.slice(4))} 月）` : c[0]; };
+  const head = k => { const c = SCR_COLS[k], M = revMonth(), Fq = finQ();
+    return k === 'ry' && M ? `營收年增（${Number(M.slice(4))} 月）` : (k === 'eq' || k === 'ey') && Fq ? `${c[0]}（Q${Number(Fq.slice(4))}）` : c[0]; };
   const th = (k, t) => o.sort ? `<th class="sort" data-k="${k}">${t}</th>` : `<th>${t}</th>`;
   return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th>${th('p', '漲跌')}${th('tv', '成交額')}${cols.map(k => th(k, head(k))).join('')}</tr></thead><tbody>` +
     list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
       <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.tv, 1)}億</td>` +
       cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
-        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
+        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
     '</tbody></table></div>';
 }
 
@@ -858,6 +873,12 @@
   { id: 'rc', g: '基本面', label: '累計年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('rc'), cols: ['rc'] },
   { id: 'rh', g: '基本面', label: '營收創新高', sw: true, f: scrPos('rh'), cols: ['rh'] },
   { id: 'r3', g: '基本面', label: '連續 3 個月年增', sw: true, f: x => x.r3 === 1, cols: ['r3'] },
+  // 第 10 輪 B5：季報（最新一季；null = 沒有季報、去年同季虧損、金融業的毛利率 → 不符合）
+  { id: 'ey', g: '基本面', label: '單季 EPS 年增 ≥ {v}%', opts: [0, 20, 50], def: 20, f: scrGe('ey'), cols: ['eq', 'ey'], title: '最新一季單季 EPS 比去年同季；去年同季虧損或為 0 時不計算' },
+  { id: 'gmy', g: '基本面', label: '毛利率年增 ≥ {v} 百分點', opts: [0, 1, 3], def: 0, f: scrGe('gmy'), cols: ['gm', 'gmy'], title: '單季毛利率比去年同季；金融業沒有毛利率，不列入' },
+  { id: 'e4', g: '基本面', label: '近 4 季 EPS > 0', sw: true, f: scrPos('e4'), cols: ['e4'] },
+  { id: 'eh', g: '基本面', label: '單季 EPS 創 {v} 季新高', opts: [4, 8], def: 4, f: scrGe('eh'), cols: ['eq', 'eh'], title: '最新一季單季 EPS 高於之前連續 N 季' },
+  { id: 'ed', g: '基本面', label: '單季 EPS 比去年同季下滑', sw: true, f: x => isNum(x.ey) && x.ey < 0, cols: ['eq', 'ey'] },
   { id: 'pe', g: '基本面', label: '0 < 本益比 ≤ {v}', opts: [10, 15, 20], def: 15, val: true, f: (x, v, st) => isNum(x.pe) && x.pe > 0 && x.pe <= v && valGuard(x, st), cols: ['pe'] },
   { id: 'dy', g: '基本面', label: '殖利率 ≥ {v}%', opts: [3, 4, 5, 6], def: 5, val: true, f: (x, v, st) => isNum(x.dy) && x.dy >= v && valGuard(x, st), cols: ['dy'] },
   { id: 'pb', g: '基本面', label: '淨值比 ≤ {v}', opts: [1, 1.5, 2], def: 1, val: true, f: (x, v, st) => isNum(x.pb) && x.pb > 0 && x.pb <= v && valGuard(x, st), cols: ['pb'] },
@@ -875,7 +896,8 @@
 const SCREEN_PRESETS = [
   ['1', '法人連買＋營收創新高', 's=3&rh=1&tv=0.5'], ['2', '投信認養', 'ts=3&t5=1&t5r=5&tv=0.5'], ['3', '帶量突破', 'nh=60&vr=1.5&tv=1'],
   ['4', '多頭排列＋相對強勢', 'ma=3&rs20=0&f5=1&tv=3'], ['5', '價值高息', 'pe=15&dy=5&tv=0.5'], ['6', '營收高成長', 'ry=30&rc=30&rh=1&tv=1'],
-  ['7', '籌碼換手', 'n5r=3&m5d=2&ma=1&tv=0.5'], ['r1', '融資追價', 'm5u=10&r5=10&tv=0.5'], ['r2', '軋空觀察', 'sr=20&ma=1&tv=0.5'],
+  ['7', '籌碼換手', 'n5r=3&m5d=2&ma=1&tv=0.5'], ['8', '財報優於去年', 'ey=20&gmy=0&tv=0.5'],
+  ['r1', '融資追價', 'm5u=10&r5=10&tv=0.5'], ['r2', '軋空觀察', 'sr=20&ma=1&tv=0.5'], ['r3', '本益比低但 EPS 下滑', 'pe=15&ed=1&tv=0.5'],
 ];
 const SCREEN_DEFAULT = { xd: 1, xn: 1, xc: 1, o: 'tv' };
 // 條件狀態 = {條件 id: 門檻, o: 排序欄, od: 'a' 遞增／'d' 遞減（省略 = 預設方向）, ps: 套用中的預設}
@@ -942,10 +964,10 @@
     const chip = ([id, name], ref) => `<button class="chip${ref ? ' ref' : ''}${st.ps === id ? ' on' : ''}" data-ps="${id}"${ref ? ' title="風險檢查，不是買進訊號"' : ''}>${name}</button>`;
     $('#view').innerHTML = `<section class="sec">
       <div class="sec-h">${modeSeg('screen')}</div>
-      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}${revMixed(S) ? '（每月 1～10 日為公布期間，各股月份不同）' : ''}</div>
+      <div class="muted small">行情 ${md(S.d)}｜法人 ${md(S.fd)}｜融資融券 上市 ${mdx(S.md.TWSE)}、上櫃 ${mdx(S.md.TPEx)}｜營收 ${Object.entries(S.rmd).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${mon(k)} ${fmt(n)} 檔`).join('、') || '--'}${revMixed(S) ? '（每月 1～10 日為公布期間，各股月份不同）' : ''}｜季報 ${Object.entries(S.fqd || {}).sort((a, b) => b[0].localeCompare(a[0])).map(([k, n]) => `${k.slice(0, 4) === S.d.slice(0, 4) ? '' : k.slice(0, 4) + ' '}Q${Number(k.slice(4))} ${fmt(n)} 檔`).join('、') || '--'}${finMixed(S) ? '（財報公布期間，各股季別不同）' : ''}</div>
       <div style="margin-top:8px">${notes}</div>
-      <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.slice(0, 7).map(p => chip(p)).join('')}
-        <span class="muted small">參考：</span>${SCREEN_PRESETS.slice(7).map(p => chip(p, true)).join('')}</div>
+      <div class="sec-h" style="margin:8px 0 0;gap:6px"><span class="muted small">預設：</span>${SCREEN_PRESETS.filter(p => p[0][0] !== 'r').map(p => chip(p)).join('')}
+        <span class="muted small">參考：</span>${SCREEN_PRESETS.filter(p => p[0][0] === 'r').map(p => chip(p, true)).join('')}</div>
       <details class="scr-panel card"${open ? ' open' : ''}><summary>條件（已選 ${conds.length} 個）
         <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
         ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
@@ -953,7 +975,7 @@
       <div class="sec-h" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
       <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
         : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
-      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
+      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
     const changed = () => { delete st.ps; save(); draw(); };
     onModeSeg();
     $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
--- orig/site/stock.js	2026-11-05 22:02:04
+++ proj/site/stock.js	2026-11-06 23:27:22
@@ -37,13 +37,17 @@
   // P16：股本變動事件 90 天內，本益比與殖利率加註
   const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
   // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
-  const fundSub = v => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', capSub].filter(Boolean).join('；');
+  // 第 10 輪 P24：淨值比卡也標資料日（cap = false：股本變動註記照舊只在本益比、殖利率卡）
+  const fundSub = (v, cap = true) => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', cap ? capSub : ''].filter(Boolean).join('；');
   // 第 9 輪 F9-4（B7）：估值一年位置；股本變動、虧損、無股利、新上市時匯出沒有該欄
   const VAL = data.val;
   const valSub = (k, v) => { const x = VAL?.[k]; if (!x || v == null) return '';
     const [p, lo, hi] = x, f = n => fmt(n, 2) + (k === 'dy' ? '%' : '');
     return `一年位置 ${v <= lo ? '最低' : v >= hi ? '最高' : p + '%'}（${f(lo)}～${f(hi)}）`; };
   const subs = (...a) => a.filter(Boolean).join('<br>');
+  // 第 10 輪 B5：季報（沒有任何季報的股票沒有 fin）；近 4 季 EPS 明顯高於一年前（一年前 ≤ 0 且現在 > 0，或 ≥ 1.5 倍）時加獲利說明一行
+  const F = data.fin;
+  const finUp = F && isNum(F.e4) && isNum(F.e4p) && F.e4 > 0 && (F.e4p <= 0 || F.e4 >= F.e4p * 1.5);
   const watching = App.watch.has(code);
   const fd = md(App.latest.flow_date);
   const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
@@ -98,7 +102,7 @@
 
     <section class="sec metrics">
       ${[['開盤', pfmt(P.o[last])], ['最高', pfmt(P.h[last]), 'up'], ['最低', pfmt(P.l[last]), 'dn'], ['昨收', pfmt(prev)],
-         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', valSub('pb', fund.pb)],
+         ['成交量', fmt(P.v[last]) + ' 張'], ['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
          ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))],
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
@@ -106,7 +110,8 @@
          ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
-    ${VAL ? `<div class="muted small val-note">一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比位置也反映獲利變化：獲利下降時本益比會升高，請一併看淨值比。</div>` : ''}
+    ${VAL ? `<div class="muted small val-note">一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}</div>` : ''}
+    ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
     ${acHTML}
 
     <section class="sec card">
@@ -132,7 +137,8 @@
     <section class="sec grid g2">
       <div class="card"><div class="sec-h"><h2>月營收</h2><span class="muted small">柱：營收（億），紅／綠 = 年增正／負；線：累計年增（%，右軸）</span></div><div id="revBox"></div></div>
       <div class="card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></div>
-    </section>`;
+    </section>
+    ${F ? `<section class="sec card"><div class="sec-h"><h2>季報</h2><span class="muted small">${qName(F.q.at(-1)[0])}${F.c.fs ? `｜本站收錄 ${md(F.c.fs)}` : ''}｜${FIN_TBL[F.t] || ''}</span></div><div id="finBox"></div></section>` : ''}`;
 
   $('#starBtn').addEventListener('click', () => {
     App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
@@ -155,6 +161,7 @@
     $('#' + id).addEventListener(t, () => { syncLeader = charts[idx]; }, { passive: true })));
 
   renderRevenue(data.revenue);
+  if (F) renderFin(F);
   draw();
 };
 
@@ -417,6 +424,32 @@
         ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
 }
 
+// ─── 第 10 輪 B5：季報卡（匯出端已把累計相減成單季；q = [季別, 單季 EPS, EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]）───
+const FIN_TBL = { ci: '一般業', fh: '金控', basi: '銀行', bd: '證券', ins: '保險', mim: '其他' };
+const qName = k => `${Math.floor(k / 100)} Q${k % 100}`;                 // 202603 → 2026 Q3
+const qShort = k => `${String(k).slice(2, 4)}Q${k % 100}`;              // 202603 → 26Q3
+function renderFin(F) {
+  const Q = F.q, L = Q.at(-1), k = L[0], q = k % 100;
+  const base = Q.find(r => r[0] === k - 100);                             // 去年同季（近 8 季內才有）
+  const ey = (v, cur, b) => v != null ? sgn(v, 1) + '%' : b != null && b <= 0 && cur > 0 ? '轉盈' : '--';
+  const pc1 = v => v == null ? '--' : fmt(v, 1) + '%';
+  const stats = [['單季 EPS', fmt(L[1], 2), cls(L[2]), `年增 ${ey(L[2], L[1], base?.[1])}`],
+    ['累計 EPS', fmt(F.c.e, 2), '', `${q === 4 ? '全年' : `1～${q * 3} 月`}，年增 ${F.c.ey == null ? '--' : sgn(F.c.ey, 1) + '%'}`],
+    ...(F.t === 'ci' ? [['毛利率', pc1(L[3]), '', `去年同季 ${pc1(base?.[3])}`]] : []),
+    ...(L[4] != null ? [['營益率', pc1(L[4]), '', `去年同季 ${pc1(base?.[4])}`]] : []),
+    ['近 4 季 EPS', fmt(F.e4, 2), '', `一年前 ${fmt(F.e4p, 2)}`]];
+  const v = Q.map(r => r[1]).filter(isNum), mx = Math.max(0, ...v), mn = Math.min(0, ...v), span = mx - mn || 1, H = 110;
+  const bar = r => { const e = r[1], c = e == null ? '' : r[2] == null ? 'flat' : r[2] >= 0 ? 'up' : 'dn';
+    const top = (mx - Math.max(e ?? 0, 0)) / span * H, h = e == null ? 0 : Math.max(Math.abs(e) / span * H, 1);
+    return `<div class="fb" title="${qName(r[0])} 單季 EPS ${fmt(e, 2)}，年增 ${ey(r[2], e, Q.find(x => x[0] === r[0] - 100)?.[1])}">
+      <div class="fb-v num">${fmt(e, 2)}</div><div class="fb-a" style="height:${H}px"><b style="top:${mx / span * H}px"></b><i class="${c}" style="top:${top}px;height:${h}px"></i></div>
+      <div class="fb-l">${qShort(r[0])}</div></div>`; };
+  $('#finBox').innerHTML = `<div class="metrics">${stats.map(([l, x, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c}" style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>
+    <div class="ch-label">近 ${Q.length} 季單季 EPS（元）；紅／綠 = 比去年同季增加／減少，灰 = 無法比較（去年同季虧損或沒有資料）</div>
+    <div class="fin-bars">${Q.map(bar).join('')}</div>
+    <div class="muted small" style="margin-top:6px">單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}</div>`;
+}
+
 function renderRevenue(rows) {
   const box = $('#revBox');
   if (!rows.length) { box.innerHTML = '<div class="empty">沒有月營收資料</div>'; return; }
--- orig/site/app.css	2026-11-05 22:28:48
+++ proj/site/app.css	2026-11-06 23:27:22
@@ -154,6 +154,14 @@
 .lg{display:inline-flex;align-items:center;gap:4px}
 .lg i{display:inline-block;width:12px;height:3px;border-radius:2px}
 .hi{color:var(--amber);margin-left:4px}
+.fin-note{color:var(--text)}                                                  /* 第 10 輪：獲利說明一行 */
+.fin-bars{display:flex;gap:4px;margin-top:4px}
+.fb{flex:1;min-width:0;text-align:center;font-size:11px;color:var(--text2)}
+.fb-a{position:relative}
+.fb-a b{position:absolute;left:0;right:0;border-top:1px solid var(--border2)}
+.fb-a i{position:absolute;left:18%;right:18%;border-radius:2px;background:var(--flat)}
+.fb-a i.up{background:var(--up)}.fb-a i.dn{background:var(--dn)}
+.fb-v{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 @media (max-width:520px){#revBox .tbl th:nth-child(3),#revBox .tbl td:nth-child(3){display:none}}   /* 手機隱藏「月增」，累計年增不需橫向捲動 */
 .signal{border-radius:var(--radius);padding:12px 14px;border:1px solid var(--border)}
 .signal.bull{background:var(--up-bg)}.signal.bear{background:var(--dn-bg)}
```

## 附錄 E：舊測試修改（`tests/test_iter03.py`、`tests/test_iter08.py`）

```diff
--- orig/tests/test_iter03.py	2026-11-05 22:02:04
+++ proj/tests/test_iter03.py	2026-11-06 23:24:33
@@ -386,6 +386,7 @@
         self.runs, self.holidays, self.exports, self.notices = [], [], 0, []
         self.run_updates = []                                   # finish_run：(outcome, export_seconds, run_id)
         self.revenue = {(2026, 8): 1980, (2026, 9): 1980}
+        self.fin = {(y, q): (1984, 38) for y in range(2024, 2028) for q in range(1, 5)}    # 第 10 輪：季報各季都已齊（不發季報請求）
         days = tradingcal.trading_days(seed_until - timedelta(days=45), seed_until, CLOSED)
         self.rows.update(_full_snapshot(days))
         if not unsettled:       # 沒有日期的資料：seed_until 當晚都已成功
@@ -649,6 +650,8 @@
             self.result = [(0,)]
         elif "revenue_year, revenue_month, COUNT" in sql:
             self.result = [(y, m, n) for (y, m), n in w.revenue.items()]
+        elif "fin_year, fin_quarter, COUNT" in sql:                 # 第 10 輪
+            self.result = [(y, q, n, nf) for (y, q), (n, nf) in w.fin.items()]
         return self
 
     def fetchone(self):
--- orig/tests/test_iter08.py	2026-11-05 00:20:37
+++ proj/tests/test_iter08.py	2026-11-06 23:24:33
@@ -173,7 +173,7 @@
     S = export.screen_build(rows, {"d": "2026-11-04", "fd": "2026-11-04", "md": {"TWSE": "2026-11-04"}})
     assert S["codes"] == ["1101", "2330", "8888", "9999"] and S["b20"] == [None, -7.38, None, None]
     assert S["rmd"] == {"202609": 2, "202608": 1} and list(S["rmd"]) == ["202609", "202608"]
-    assert set(S) == {"d", "fd", "md", "rmd", "codes", *export.SCREEN_KEYS}
+    assert set(S) == {"d", "fd", "md", "rmd", "fqd", "codes", *export.SCREEN_KEYS}      # fqd：第 10 輪
 
 
 # ─── F8-3：融資融券 ─────────────────────────────────────
```

## 附錄 F：`tests/test_iter10.py`（新檔，全文）與 fixture

### F-1 `tests/test_iter10.py`

```python
"""
第 10 輪純邏輯測試（不連網、不連資料庫）：
F10-1 季 EPS：mopsov ajax_t163sb04 解析（6 種業別、個體報表淨利、保險業 EPS 欄名、封鎖頁、欄位不符、0 家）、MERGE 與 DDL、
      單季相減（Q1、Q4、上一季缺、去年同季 ≤ 0、近 4 季）、收集窗口與排程、check 的季報一行、補抓季別；
F10-2 選股欄（eq、ey、e4、gm、gmy、fq、eh）、fqd、今日頁 fin_progress；
F10-3 上市法人金額的行情保護、淨值比卡日期與估值說明（原始碼檢查）。
fixture：tests/fixtures/t163sb04_*_mini.html（mopsov 原始回應的精簡版：表頭不變，每張表只留幾家）。數值以 2026-11-06 為準。

  python3 tests/test_iter10.py      （也相容 pytest）
"""
import contextlib
import io
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
from twstock import db, export, health  # noqa: E402
from twstock.collectors import catchup, daily, financials, history  # noqa: E402
from twstock.fetch import FetchError, SchemaError  # noqa: E402

D, T, CLOSED = t3.D, t3.T, t3.CLOSED
FIX = Path(__file__).resolve().parent / "fixtures"
ROOT = Path(__file__).resolve().parent.parent
html = lambda name: (FIX / f"t163sb04_{name}_mini.html").read_text(encoding="utf-8")
Q2, Q3 = financials.parse_financials(html("sii_115_02")), financials.parse_financials(html("sii_115_03"))


# ─── F10-1：解析 ───────────────────────────────────────
def test_f101_parse_industries():
    assert len(Q2) == 15
    tbl = {c: r["industry_tbl"] for c, r in Q2.items()}
    assert {t: sorted(c for c in tbl if tbl[c] == t) for t in set(tbl.values())} == {
        "basi": ["2801", "2820"], "bd": ["2855", "6005"], "ci": ["1215", "1342", "2303", "2330", "2408"],
        "fh": ["2881", "2882"], "ins": ["2816", "2832"], "mim": ["1409", "2207"]}
    assert Q2["2408"] == {"industry_tbl": "ci", "revenue": 131636005, "gross_profit": 98935333, "op_income": 90937560,
                          "net_income": 76251525, "eps": 23.38}
    assert Q2["2330"]["eps"] == 49.33 and Q2["1215"]["revenue"] == 14401643
    assert Q2["2881"]["eps"] == 6.67 and Q2["2881"]["gross_profit"] is None and Q2["2881"]["op_income"] is None
    assert Q2["2881"]["revenue"] == 172468262                                         # 金控：淨收益
    assert Q2["2801"]["revenue"] is None and Q2["2801"]["op_income"] is None          # 銀行：沒有合計欄
    assert Q2["6005"]["revenue"] == 19197814 and Q2["6005"]["op_income"] == 6593675   # 證券：收益、營業利益
    assert Q2["2816"]["eps"] is not None and Q2["2816"]["revenue"] is None            # 保險：EPS 欄名沒有「（元）」；IFRS 17 後沒有收入欄
    assert Q2["2820"]["net_income"] == 1436196 and Q2["1342"]["net_income"] == 318976   # 個體報表：本期淨利
    assert all(r["gross_profit"] is None for r in Q2.values() if r["industry_tbl"] != "ci")
    assert Q3["2408"]["eps"] == 49.28 and Q3["2303"]["eps"] == 6.0 and Q3["1215"]["revenue"] == 21866426


def test_f101_parse_old_and_otc():
    old = financials.parse_financials(html("sii_113_01"))
    assert old["2408"]["eps"] == -0.39 and old["2408"]["gross_profit"] == -276624
    assert old["2816"]["industry_tbl"] == "ins" and old["2816"]["revenue"] is not None   # 113 年保險業有營業收入、EPS 有「（元）」
    assert old["2881"]["industry_tbl"] == "fh" and old["2881"]["eps"] == 2.34
    otc = financials.parse_financials(html("otc_115_02"))
    assert {r["industry_tbl"] for r in otc.values()} == {"ci", "bd"} and otc["6488"]["eps"] == 11.87


def test_f101_parse_errors():
    page = html("sii_115_02")
    head = page[:page.index("<table class='hasBorder'")]
    assert financials.parse_financials(head + "</div></body></html>") == {}            # 認得的頁面、還沒有表：0 家
    only_head = financials.parse_financials(page.split("<tr class='even'>")[0] + "</table></body></html>")
    assert only_head == {}                                                             # 只有標題列：0 家
    for bad in (page.replace("基本每股盈餘", "每股盈餘"), page.replace("公司<br>代號", "代號"),
                page.replace("營業毛利（毛損）淨額", "毛利").replace("淨收益", "收益合計")):
        try:
            financials.parse_financials(bad)
            assert False, "欄位不符要丟 SchemaError"
        except SchemaError:
            pass
    for text, err in (("<html>THE REQUESTED URL WAS REJECTED. SECURITY</html>", FetchError), ("<html>其他</html>", SchemaError)):
        try:
            financials.parse_financials(text)
            assert False
        except err:
            pass


def test_f101_fetch_params():
    resp = mock.Mock(content=html("sii_115_03").encode("utf-8"))
    with mock.patch.object(financials, "request", return_value=resp) as req:
        got = financials.fetch_financials("TPEx", 2026, 3)
    assert got["2408"]["eps"] == 49.28
    args, kw = req.call_args
    assert args[:2] == ("POST", financials.URL) and kw["expect_json"] is False
    assert kw["data"]["TYPEK"] == "otc" and kw["data"]["year"] == "115" and kw["data"]["season"] == "03"


def test_f101_merge_and_ddl():
    sql = []

    class Cur:
        rowcount = 2

        def execute(self, s, *p):
            sql.append((s, p))
            return self
    n = financials.merge_financials(Cur(), 2026, 3, [{"stock_code": "2408", **Q3["2408"]}], date(2026, 11, 10))
    s, p = sql[0]
    assert n == 2 and "JOIN stocks st ON st.stock_code = j.stock_code" in s
    upd, ins = s.split("WHEN NOT MATCHED")
    assert "first_seen" not in upd and "updated_at = GETDATE()" in upd and "EXCEPT" in upd   # 更新時不動首次收錄日、值相同不更新
    assert "first_seen" in ins and p[1:] == (2026, 3, 2026, 3, date(2026, 11, 10))
    ddl = "\n".join(db.DDL)
    assert "IF OBJECT_ID('quarterly_financials') IS NULL" in ddl
    assert "CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)" in ddl
    assert "first_seen    DATE           NULL" in ddl


# ─── F10-1：單季相減 ───────────────────────────────────
def _cum(*rows):
    """(年, 季, EPS, 營收, 毛利) → cum；營益、淨利用 None。"""
    return {(y, q): (rev, gp, None, None, Decimal(str(e)) if e is not None else None) for y, q, e, rev, gp in rows}


def test_f101_single_rules():
    c = _cum((2025, 1, 1.0, 100, 30), (2025, 2, 2.5, 220, 70), (2025, 3, 4.0, 330, 100), (2025, 4, 6.0, 460, 140),
             (2026, 2, 3.0, 250, 80))
    assert export.fin_single(c, 2025, 1)[4] == Decimal("1.0")                          # Q1 = 累計
    assert export.fin_single(c, 2025, 4)[4] == Decimal("2.0") and export.fin_single(c, 2025, 4)[0] == 130   # Q4 = 全年 − Q3
    assert export.fin_single(c, 2026, 2) == [None] * 5                                  # 上一季（2026Q1）缺 → null，不以累計頂替
    assert export.fin_single(c, 2026, 1) is None
    c2 = dict(c)
    c2[(2025, 2)] = (220, None, None, None, Decimal("2.5"))
    assert export.fin_single(c2, 2025, 3)[1] is None and export.fin_single(c2, 2025, 3)[4] == Decimal("1.5")   # 該欄 NULL → 該欄 null
    assert export.fin_yoy(Decimal("1.5"), Decimal("-0.2")) is None and export.fin_yoy(Decimal("1.5"), 0) is None
    assert export.fin_yoy(Decimal("1.32"), Decimal("1.0")) == 32.0 and export.fin_yoy(None, Decimal(1)) is None
    assert export.fin_margin(5, 0) is None and export.fin_margin(None, 10) is None and export.fin_margin(1, 8) == 12.5
    assert export._r1(17575, 100000) == 17.6                                            # ROUND_HALF_UP（不是 17.5）


def test_f101_e4():
    c = _cum((2024, 3, 3.0, 1, 1), (2024, 4, 4.0, 1, 1), (2025, 3, 5.0, 1, 1), (2025, 4, 7.0, 1, 1), (2026, 3, 6.0, 1, 1))
    assert export.fin_e4(c, 2026, 3) == Decimal("8.0")          # 6 + 7 − 5
    assert export.fin_e4(c, 2025, 3) == Decimal("6.0")          # 5 + 4 − 3（一年前）
    assert export.fin_e4(c, 2025, 4) == Decimal("7.0")          # Q4 = 全年
    assert export.fin_e4(c, 2024, 3) is None                    # 四項缺一


def test_f101_numbers_1106():
    """PM 驗收 F10-1 #5（11/06 的值；QA 時以 SQL 重算為準）。"""
    rows = lambda code: (Q2[code], Q3[code])
    for code, eps, gm in (("2408", 25.90, 85.7), ("2303", 1.32, 34.0)):
        a, b = rows(code)
        c = {(2026, 2): tuple(a[k] for k in ("revenue", "gross_profit", "op_income", "net_income")) + (Decimal(str(a["eps"])),),
             (2026, 3): tuple(b[k] for k in ("revenue", "gross_profit", "op_income", "net_income")) + (Decimal(str(b["eps"])),)}
        s = export.fin_single(c, 2026, 3)
        assert float(s[4]) == eps and export.fin_margin(s[1], s[0]) == gm
    assert Q3["1215"]["revenue"] - Q2["1215"]["revenue"] == 7464783
    # 台光電、大立光（mopsov 115Q2 與 OpenAPI 115Q3 的值）
    for (r2, g2, e2), (r3, g3, e3), eps, gm in (((80342455, 25732144, "42.46"), (141226994, 48682931, "82.92"), 40.46, 37.7),
                                                 ((29208838, 14432503, "82.35"), (44859658, 21039356, "121.98"), 39.63, 42.2)):
        c = {(2026, 2): (r2, g2, None, None, Decimal(e2)), (2026, 3): (r3, g3, None, None, Decimal(e3))}
        s = export.fin_single(c, 2026, 3)
        assert float(s[4]) == eps and export.fin_margin(s[1], s[0]) == gm


def test_f101_fin_stock():
    c = _cum(*[(y, q, 1.0 * q, 100 * q, 30 * q) for y in (2024, 2025) for q in (1, 2, 3, 4)], (2026, 1, 2.0, 100, 50))
    f = export.fin_stock(c, "ci", None)
    assert [r[0] for r in f["q"]] == [202402, 202403, 202404, 202501, 202502, 202503, 202504, 202601]   # 近 8 季
    assert f["q"][-1] == [202601, 2.0, 100.0, 50.0, None, 100] and "fs" not in f["c"]  # 補抓：沒有首次收錄日
    assert f["c"] == {"e": 2.0, "ey": 100.0} and f["e4"] == 5.0 and f["e4p"] == 4.0 and f["t"] == "ci"
    assert export.fin_stock(c, "ci", date(2026, 5, 2))["c"]["fs"] == "2026-05-02"
    assert export.fin_stock({}, "ci", None) is None and export.fin_stock(None, None, None) is None
    gap = {k: v for k, v in c.items() if k != (2025, 3)}
    assert [r[0] for r in export.fin_stock(gap, "ci", None)["q"]] == [202402, 202403, 202404, 202501, 202502, 202504, 202601]
    assert export.fin_stock(gap, "ci", None)["q"][-2][1] is None                       # Q4 少了 Q3 累計 → 單季 null


# ─── F10-1：收集窗口、排程、check ──────────────────────
def test_f101_windows():
    q = health.fin_quarter_for
    assert q(D(10, 14)) is None and q(D(10, 15)) == (2026, 3) and q(D(12, 6)) == (2026, 3) and q(D(12, 7)) is None
    assert q(date(2027, 1, 15)) == (2026, 4) and q(date(2027, 4, 7)) == (2026, 4) and q(date(2027, 4, 8)) is None
    assert q(date(2027, 4, 15)) == (2027, 1) and q(date(2027, 9, 7)) == (2027, 2) and q(date(2027, 7, 14)) is None
    assert health.fin_latest_quarter(D(12, 10)) == (2026, 3, False) and health.fin_latest_quarter(D(11, 6)) == (2026, 3, True)
    assert health.fin_latest_quarter(D(10, 1)) == (2026, 2, False)
    gen, fin, gen_td, fin_td = health.fin_due(2026, 3, CLOSED)
    assert (gen, fin, gen_td, fin_td) == (D(11, 14), D(11, 29), D(11, 16), D(11, 30))   # 週六、週日 → 下一個交易日
    assert health.fin_due(2026, 4, CLOSED)[:2] == (date(2027, 3, 31), date(2027, 3, 31))


PREV = {(2026, 2): (1950, 38)}
FSTATE = {"alerts_at": datetime(2026, 11, 5, 19), "events_to": D(11, 5), "revenue_on": D(11, 5), "financials_on": None, "collected_at": None}


def _fplan(now, counts, **st):
    days = health.due_days(now, 10, CLOSED)
    return catchup.make_plan(now, 10, t3._full_snapshot(days), dict(FSTATE, **st), CLOSED, None, counts)["financials"]


def test_f101_make_plan():
    assert _fplan(T(10, 14), PREV) is None
    assert _fplan(T(10, 15), PREV) == (2026, 3) and _fplan(T(12, 6), PREV) == (2026, 3)
    assert _fplan(T(12, 7), PREV) is None and _fplan(datetime(2027, 1, 15, 18), PREV) == (2026, 4)
    assert _fplan(T(11, 10), {**PREV, (2026, 3): (900, 0)}, financials_on=D(11, 10)) is None    # 同一天只抓一次
    assert _fplan(T(11, 20), {**PREV, (2026, 3): (1921, 0)}) == (2026, 3)                      # 98.5%、金融業 0 家 → 仍排入
    assert _fplan(T(12, 1), {**PREV, (2026, 3): (1921, 38)}) is None                           # 金融業已齊 → 不排入
    assert _fplan(T(12, 1), {**PREV, (2026, 3): (1921, 30)}) is None                           # 已過金融業截止後第一個交易日（11/30）
    assert _fplan(T(11, 30), {**PREV, (2026, 3): (1921, 30)}) == (2026, 3)
    assert _fplan(T(11, 10), {(2026, 3): (900, 0)}) == (2026, 3)                               # 上一季沒有資料：不算齊
    assert catchup.make_plan(T(11, 10), 10, t3._full_snapshot(health.due_days(T(11, 10), 10, CLOSED)), FSTATE, CLOSED)["financials"] is None
    d = catchup.plan_for_date(D(11, 10), T(11, 10), False, PREV, CLOSED)
    assert d["financials"] == (2026, 3) and catchup.plan_for_date(D(12, 10), T(12, 10), False, PREV, CLOSED)["financials"] is None
    assert catchup.plan_for_date(D(11, 10), T(11, 10), True, PREV, CLOSED)["financials"] is None    # 休市日只處理沒有日期的資料


def test_f101_window_requests():
    """第 3 季窗口（10/15～12/06）每天 18:00 跑一次 catch-up：每天最多 2 個請求；收齊後 0 次。"""
    def published(day):                     # 前一晚收到的總家數、金融業家數
        n = 0 if day < D(10, 20) else min(1950, 60 + (day - D(10, 20)).days * 70)
        return n, (38 if day >= D(11, 28) else 31)
    planned, d = [], D(10, 10)
    while d <= D(12, 10):
        counts = {**PREV, (2026, 3): published(d - timedelta(days=1))}
        got = _fplan(T(d.month, d.day), counts, financials_on=d - timedelta(days=1))
        assert _fplan(T(d.month, d.day), counts, financials_on=d) is None
        if got:
            planned.append(d)
        d += timedelta(days=1)
    assert planned[0] == D(10, 15) and planned[-1] == D(11, 28) and len(planned) * 2 == 90   # 11/29 起已齊（金融業 38）


def test_f101_zero_rows_is_success():
    plan = {"by_date": [], "futures": None, "futures_oi": None, "tpex_months": [], "alerts": False, "events": None,
            "revenue": [], "financials": (2026, 3)}
    with mock.patch.object(catchup, "collect_financials", lambda y, q, seen: 0), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(10, 15))
    assert errors == {} and undated == {"financials": "2026-10-15"}
    with mock.patch.object(catchup, "collect_financials", side_effect=SchemaError("x")), contextlib.redirect_stdout(io.StringIO()):
        written, errors, undated = catchup.execute_plan(plan, T(10, 15))
    assert "financials" in errors and undated == {}


def test_f101_load_state():
    class Cur:
        def execute(self, *a):
            return self

        def fetchall(self):
            return [(datetime(2026, 11, 10, 22), 1, '{"undated": {"financials": "2026-11-10"}}', "catch-up"),
                    (datetime(2026, 11, 9, 22), 1, '{"undated": {"financials": "2026-11-09", "revenue": "2026-11-09"}}', "catch-up")]
    st = health.load_state(Cur())
    assert st["financials_on"] == D(11, 10) and st["revenue_on"] == D(11, 9)


def _fin(now, n, fin_on, nf=0):
    return health.financials_status(now.date(), {(2026, 2): (1950, 38), (2026, 3): (n, nf)}, fin_on, CLOSED)


def test_f101_check():
    st, txt = _fin(T(11, 6), 281, D(11, 6))
    assert st == health.PENDING and txt == ("第 3 季財報 2026Q3：已收 281 家（前一季 1,950 家的 14%），金融業 0／38 家，"
                                            "⏳ 公布期間（一般業 11/14、金融業 11/29 截止）")
    assert _fin(T(11, 16), 1800, D(11, 16))[0] == health.PENDING                        # 11/14 是週六
    assert _fin(T(11, 17), 1900, D(11, 16))[0] == health.PENDING and "晚交" in _fin(T(11, 17), 1900, D(11, 16))[1]
    st, txt = _fin(T(11, 17), 1900, D(11, 12))
    assert st == health.ABNORMAL and "最後一次收集季報 2026-11-12" in txt
    assert _fin(T(11, 20), 1921, D(11, 12), 30)[0] == health.PENDING                     # 只差金融業：11/30 前仍是公布期間
    assert _fin(T(12, 1), 1921, D(11, 30), 38)[0] == health.OK
    st, txt = _fin(T(12, 10), 1900, D(12, 6), 38)
    assert st == "info" and "收集期間已結束（12/06）" in txt
    assert health.financials_status(date(2027, 2, 1), {}, None, CLOSED)[1].startswith("年報 2026Q4：已收 0 家")
    now = T(11, 17, 23)
    days = health.due_days(now, 20, CLOSED)
    full = t3._full_snapshot(days)
    counts = {(2026, 2): (1950, 38), (2026, 3): (1900, 31)}
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "financials_on": D(11, 16)}, CLOSED, financials=counts)
    assert rc == 0 and "⏳ 晚交公司陸續補進" in text and "無異常" in text
    text, rc = health.check_report(days, full, now, {"alerts_at": None, "financials_on": D(11, 12)}, CLOSED, financials=counts)
    assert rc == 1 and "異常 1 項" in text and "collect --catch-up" in text and "已過申報截止日仍未收齊" in text
    text, rc = health.check_report(days, full, T(12, 10, 23), {"alerts_at": None, "financials_on": D(12, 6)}, CLOSED, financials=counts)
    assert rc == 0 and "ℹ️" in text and "無異常" in text
    assert "季財報" not in health.check_report(days, full, now, {"alerts_at": None}, CLOSED)[0]   # 舊呼叫方式不印


def test_f101_history_quarters():
    q = history.fin_quarters(date(2024, 1, 1), D(11, 6), D(11, 6))
    assert q[0] == (2024, 1) and q[-1] == (2026, 3) and len(q) == 11                       # 113Q1～115Q3
    assert history.fin_quarters(date(2024, 1, 1), D(10, 14), D(10, 14))[-1] == (2026, 2)    # 115Q3 窗口還沒開始
    calls = []
    have = {(y, qq, m) for y, qq in q for m in ("TWSE", "TPEx")}
    with mock.patch.object(history, "load_fin_have", lambda: have), mock.patch.object(history, "tw_now", lambda: T(11, 6)), \
            mock.patch.object(history, "collect_financials", lambda *a: calls.append(a)), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) and calls == []   # 重跑：全部跳過
        have.discard((2026, 3, "TPEx"))
        assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) and calls == [(2026, 3, None, ("TPEx",))]
        calls.clear()
        with mock.patch.object(history, "load_fin_have", lambda: set()):
            history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",))
        assert len(calls) == 22 and all(c[2] is None for c in calls)                     # 補抓：首次收錄日一律 NULL
    for err, word in ((FetchError("x"), "封鎖"), (SchemaError("y"), "欄位不符")):
        buf = io.StringIO()
        with mock.patch.object(history, "load_fin_have", set), mock.patch.object(history, "tw_now", lambda: T(11, 6)), \
                mock.patch.object(history, "collect_financials", side_effect=err), contextlib.redirect_stdout(buf):
            assert history.run_history(date(2024, 1, 1), D(11, 6), datasets=("financials",)) is False
        assert word in buf.getvalue()


# ─── F10-2：選股欄、今日頁 ─────────────────────────────
def test_f102_screen_fields():
    c = _cum((2025, 2, 2.0, 200, 60), (2025, 3, 3.0, 300, 90), (2026, 1, 1.0, 100, 40), (2026, 2, 2.2, 210, 84),
             (2026, 3, 4.0, 330, 132), (2025, 4, 4.5, 400, 120))
    s = export.fin_screen(c)
    assert s == {"eq": 1.8, "ey": 80.0, "e4": 5.5, "gm": 40.0, "gmy": 10.0, "fq": 202603, "eh": 4}   # eh：高於 26Q2、26Q1、25Q4、25Q3（25Q2 缺 Q1 → 停）
    assert export.fin_screen({}) == dict.fromkeys(("eq", "ey", "e4", "gm", "gmy", "fq", "eh"))
    fh = {k: (v[0], None, None, None, v[4]) for k, v in c.items()}
    assert export.fin_screen(fh)["gm"] is None and export.fin_screen(fh)["gmy"] is None          # 金融業沒有毛利率
    loss = dict(c)
    loss[(2025, 3)] = (300, 90, None, None, Decimal("1.5"))                               # 去年 Q3 單季 −0.5
    assert export.fin_screen(loss)["ey"] is None
    rows = {"1101": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202603},
            "1102": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202602},
            "1103": {**dict.fromkeys(export.SCREEN_KEYS), "rm": None, "fq": 202602}}
    assert export.screen_build(rows, {})["fqd"] == {"202603": 1, "202602": 2}


def test_f102_progress():
    counts = {(2026, 3, "TWSE"): 231, (2026, 3, "TPEx"): 50, (2026, 2, "TWSE"): 1088, (2026, 2, "TPEx"): 896}
    assert export.fin_progress(counts, D(11, 6)) == {"q": 202603, "n": {"TWSE": 231, "TPEx": 50}, "p": {"TWSE": 1088, "TPEx": 896}}
    assert export.fin_progress(counts, D(12, 10)) is None                                  # 窗口外
    assert export.fin_progress({(2026, 2, "TWSE"): 1088}, D(10, 16)) is None               # 當季 0 家


# ─── F10-3 ────────────────────────────────────────────
def test_f103_twse_amount_waits_for_prices():
    w = t3.World(D(11, 4))
    w.publish(D(11, 5), "MI_INDEX", "BFI82U")                                             # 上市行情、法人金額都還沒有
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount", "amount.TPEx"))
    assert written["prices.TWSE"] == 0 and "amount" not in written and not errors
    assert t3._hit(w, "BFI82U") == [] and len(t3._hit(w, "insti/summary")) == 1          # 上櫃照舊（上櫃有自己的保護）
    w.published["MI_INDEX"].add(D(11, 5))
    w.published["BFI82U"].add(D(11, 5))
    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount"))
    assert written["amount"] == 6 and w.rows["amount"][D(11, 5)].n == 6
    w2 = t3.World(D(11, 4))
    w2.publish(D(11, 5))
    w2.renamed.add("MI_INDEX")                                                            # 行情欄位不符（例外）→ 照舊發請求
    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
        written, errors = daily.collect_for_date(D(11, 5), ("prices.TWSE", "amount"))
    assert "prices.TWSE" in errors and written["amount"] == 6 and len(t3._hit(w2, "BFI82U")) == 1
    w3 = t3.World(D(10, 30))
    for d in (D(10, 28), D(10, 29), D(10, 30)):
        w3.rows["amount"].pop(d)
        w3.publish(d)
    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
        assert history.run_history(D(10, 27), D(10, 30), datasets=("amount",), revenue=False)
    assert len(t3._hit(w3, "BFI82U")) == 3 and t3._hit(w3, "MI_INDEX") == []               # history --only amount 不抓行情、照舊寫入


def test_f103_site_text():
    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
    assert "請一併看淨值比" not in js and "獲利大增時本益比（淨值比也可能）會落到一年低點" in js and "不代表股價便宜" in js
    assert "subs(fundSub(fund.pb, false), valSub('pb', fund.pb))" in js


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

### F-2 fixture（`tests/fixtures/`，4 檔共約 75 KB）

- 來源：分析師 `r10/raw/t163sb04_sii_115_02.html` 與 SA `r10/sa/` 的 3 份原始回應。精簡方式：保留原始 HTML 的標題與註 1、每張表的表頭原樣，只留指定公司的列（每張表至少留第一家），**不改任何字元**。
- PG 可直接複製 scratchpad `sa10/fixtures/` 的 4 檔到 `tests/fixtures/`，或用下面的腳本重產（`make_fixture.py` 放在 scratchpad，不進專案）：

```bash
python3 -I make_fixture.py r10/raw/t163sb04_sii_115_02.html tests/fixtures/t163sb04_sii_115_02_mini.html 2801 2820 2855 6005 1215 1342 2303 2330 2408 2881 2882 2816 2832 1409 2207
python3 -I make_fixture.py r10/sa/t163sb04_sii_115_03.html  tests/fixtures/t163sb04_sii_115_03_mini.html 5876 1215 2303 2408
python3 -I make_fixture.py r10/sa/t163sb04_sii_113_01.html  tests/fixtures/t163sb04_sii_113_01_mini.html 2801 2855 2408 2881 2816 2832 1409
python3 -I make_fixture.py r10/sa/t163sb04_otc_115_02.html  tests/fixtures/t163sb04_otc_115_02_mini.html 5864 6488
```

```python
# 產生 tests/fixtures/ 用的精簡回應：保留原始 HTML 的標題、註 1、每張表的表頭，只留指定公司的列（不改任何字元）
# 用法：python3 -I make_fixture.py 原始.html 輸出.html 代號1 代號2 …（每張表至少留第一家）
import re, sys
src, dst, keep = sys.argv[1], sys.argv[2], set(sys.argv[3:])
t = open(src, encoding="utf-8").read()
head = t[:t.index("<table class='hasBorder'")]
tables = re.findall(r"<table class='hasBorder'.*?</table>", t, re.S)
out = [head]
for tb in tables:
    rows = re.findall(r"<tr.*?</tr>", tb, re.S)
    body = [r for r in rows[1:] if re.search(r"<td[^>]*>\s*(\w+)\s*</td>", r).group(1) in keep] or rows[1:2]
    out.append(tb[:tb.index(rows[0])] + rows[0] + "".join(body) + "</table>")
open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n</div></body></html>\n")
print(dst, len(open(dst, encoding='utf-8').read().encode()), "B")
```

## 附錄 G：`logs/iter10_compare.py`（新檔，取代 `iter09_compare.py` 用於本輪）

```python
# 用法：python3 logs/iter10_compare.py 基線資料夾 site/data [--keep-new] —— 隔離比對（第 10 輪，取代 iter09_compare.py）
# 除了第 10 輪指定的新鍵與「時間」欄位以外必須完全相同；比對 latest.json、screen.json、stocks/*.json、etfs/*.json。
# 新鍵：latest.json 的 fin_progress；stocks/*.json 的 fin；screen.json 的 fqd、eq、ey、e4、gm、gmy、fq、eh。
# 另外印出新鍵的大小（stocks 的 fin 合計、screen 新欄合計、latest 的 fin_progress）。
# --keep-new：不剔除新鍵（反證用，應判定不同）。相同印「✅ 相同」rc=0，否則 rc=1。
import json, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
KEEP = "--keep-new" in sys.argv
NEW_LATEST = set() if KEEP else {"fin_progress"}
NEW_STOCK = set() if KEEP else {"fin"}
NEW_SCREEN = set() if KEEP else {"fqd", "eq", "ey", "e4", "gm", "gmy", "fq", "eh"}
TIME_LATEST, TIME_STATUS = {"updated_at"}, {"exported_at", "collected_at"}
bad = []
drop = lambda d, keys: {k: v for k, v in d.items() if k not in keys}
load = lambda p: json.loads(p.read_text(encoding="utf-8"))
size = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode())

LA, LB = load(a / "latest.json"), load(b / "latest.json")
LB2 = drop(LB, NEW_LATEST)
if set(LA) != set(LB2):
    bad.append(f"latest.json 鍵不同：{sorted(set(LA) ^ set(LB2))}")
for k in set(LA) & set(LB2):
    if k in TIME_LATEST:
        continue
    x, y = (drop(LA[k], TIME_STATUS), drop(LB2[k], TIME_STATUS)) if k == "status" else (LA[k], LB2[k])
    if x != y:
        bad.append(f"latest.json {k}")
SA, SB = load(a / "screen.json"), load(b / "screen.json")
if SA != drop(SB, NEW_SCREEN):
    bad.append("screen.json")
n, fin_bytes, fin_n = {}, 0, 0
for sub in ("stocks", "etfs"):
    fa = {f.name for f in (a / sub).glob("*.json")}
    fb = {f.name for f in (b / sub).glob("*.json")}
    if fa != fb:
        bad.append(f"{sub} 檔案不同：少 {sorted(fa - fb)[:5]} 多 {sorted(fb - fa)[:5]}")
    for f in sorted(fa & fb):
        x, y = load(a / sub / f), load(b / sub / f)
        if sub == "stocks" and "fin" in y:
            fin_bytes += size(y["fin"]) + len(',"fin":')
            fin_n += 1
        if x != (drop(y, NEW_STOCK) if sub == "stocks" else y):
            bad.append(f"{sub}/{f}")
    n[sub] = len(fa)
print(f"比對 latest.json、screen.json、stocks {n['stocks']} 檔、etfs {n['etfs']} 檔（略過 {sorted(TIME_LATEST)}、status.{sorted(TIME_STATUS)}"
      + ("" if KEEP else "；剔除新鍵 fin_progress、stocks 的 fin、screen 的 fqd、eq、ey、e4、gm、gmy、fq、eh") + "）")
scr = sum(size(SB[k]) + len(k) + 4 for k in ("fqd", "eq", "ey", "e4", "gm", "gmy", "fq", "eh") if k in SB)
print(f"ℹ️  新鍵大小：stocks 的 fin {fin_n} 檔共 {fin_bytes / 1024:.0f} KB；screen.json 新欄 {scr / 1024:.1f} KB；"
      f"latest.json fin_progress {size(LB.get('fin_progress')) if 'fin_progress' in LB else 0} B")
if bad:
    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
    sys.exit(1)
print("✅ 相同")
```

## 附錄 H：`logs/iter10_recalc.py`（新檔，QA 獨立重算）

```python
# 用法：python3 logs/iter10_recalc.py [資料夾，預設 site/data] —— 第 10 輪 QA 獨立重算（只讀資料庫，不寫入）
# 1. 各季分市場家數（SQL GROUP BY），比對 latest.json 的 fin_progress（季別由資料日推算窗口）。
# 2. 單季值：SQL 以「本季累計 − 同年上一季累計」自行 JOIN 算出（Q1 = 累計；上一季缺 → NULL），
#    去年同季、近 4 季（本季累計 + 去年 Q4 累計 − 去年同季累計；Q4 = 全年）也在 SQL 以 JOIN 算出。
# 3. 逐檔比對 stocks/*.json 的 fin（t、q 近 8 季、c、e4、e4p）與 screen.json 的 eq、ey、e4、gm、gmy、fq、eh，以及 fqd。
# 4. 印出「最新一季單季 EPS 年增 ≥ 0／20／50%」的檔數（SQL 計數）並與 screen.json 的 ey 計數比對。
# 減法與 JOIN 全部在 SQL；最後的百分比與四捨五入用和匯出相同的 Python 式子（ROUND_HALF_UP 到 1 位）。全部相同印「✅ 相同」rc=0，否則列出不同 rc=1。
import json, sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from twstock.db import connect  # noqa: E402
from twstock.health import fin_quarter_for  # noqa: E402  只用來由資料日推算窗口（日曆規則，不讀資料）

base = Path(sys.argv[1] if len(sys.argv) > 1 else "site/data")
L = json.loads((base / "latest.json").read_text(encoding="utf-8"))
S = json.loads((base / "screen.json").read_text(encoding="utf-8"))
cur = connect().cursor()
bad = []
r1 = lambda a, b: float((Decimal(a) * 100 / Decimal(b)).quantize(Decimal("0.1"), ROUND_HALF_UP))
yoy = lambda v, b: None if v is None or b is None or b <= 0 else r1(Decimal(str(v)) - Decimal(str(b)), Decimal(str(b)))
mg = lambda x, rev: None if x is None or rev is None or rev <= 0 else r1(x, rev)
f2 = lambda v, nd=2: None if v is None else round(float(v), nd)

# 1. 家數
counts = defaultdict(int)
for y, q, m, n in cur.execute("""
        SELECT f.fin_year, f.fin_quarter, s.market_type, COUNT(*) FROM quarterly_financials f
        JOIN stocks s ON s.stock_id = f.stock_id GROUP BY f.fin_year, f.fin_quarter, s.market_type
        ORDER BY f.fin_year, f.fin_quarter, s.market_type""").fetchall():
    counts[(y, q, m)] = n
for y, q in sorted({k[:2] for k in counts}):
    print(f"{y}Q{q}：上市 {counts[(y, q, 'TWSE')]:,}、上櫃 {counts[(y, q, 'TPEx')]:,} 家")
fq = fin_quarter_for(date.fromisoformat(L["date"]))
want = None
if fq and (counts[(*fq, "TWSE")] or counts[(*fq, "TPEx")]):
    pq = (fq[0] - 1, 4) if fq[1] == 1 else (fq[0], fq[1] - 1)
    want = {"q": fq[0] * 100 + fq[1], "n": {m: counts[(*fq, m)] for m in ("TWSE", "TPEx")},
            "p": {m: counts[(*pq, m)] for m in ("TWSE", "TPEx")}}
if L.get("fin_progress") != want:
    bad.append(f"fin_progress：{L.get('fin_progress')} ≠ {want}")

# 2. 單季、去年同季、近 4 季（SQL）
cols = ("revenue", "gross_profit", "op_income", "eps")
rows = cur.execute(f"""
    WITH sg AS (
        SELECT c.stock_id, c.fin_year, c.fin_quarter,
               {", ".join(f"CASE WHEN c.fin_quarter = 1 THEN c.{x} ELSE c.{x} - p.{x} END AS {x}" for x in cols)}
        FROM quarterly_financials c LEFT JOIN quarterly_financials p
          ON p.stock_id = c.stock_id AND p.fin_year = c.fin_year AND p.fin_quarter = c.fin_quarter - 1)
    SELECT s.stock_code, c.fin_year, c.fin_quarter, c.industry_tbl, c.first_seen, c.eps,
           g.revenue, g.gross_profit, g.op_income, g.eps,
           b.revenue, b.gross_profit, b.eps, cb.eps,
           CASE WHEN c.fin_quarter = 4 THEN c.eps ELSE c.eps + y4.eps - cb.eps END,
           CASE WHEN c.fin_quarter = 4 THEN cb.eps ELSE cb.eps + y8.eps - cbb.eps END
    FROM quarterly_financials c
    JOIN stocks s ON s.stock_id = c.stock_id
    JOIN sg g ON g.stock_id = c.stock_id AND g.fin_year = c.fin_year AND g.fin_quarter = c.fin_quarter
    LEFT JOIN sg b ON b.stock_id = c.stock_id AND b.fin_year = c.fin_year - 1 AND b.fin_quarter = c.fin_quarter
    LEFT JOIN quarterly_financials cb ON cb.stock_id = c.stock_id AND cb.fin_year = c.fin_year - 1 AND cb.fin_quarter = c.fin_quarter
    LEFT JOIN quarterly_financials y4 ON y4.stock_id = c.stock_id AND y4.fin_year = c.fin_year - 1 AND y4.fin_quarter = 4
    LEFT JOIN quarterly_financials y8 ON y8.stock_id = c.stock_id AND y8.fin_year = c.fin_year - 2 AND y8.fin_quarter = 4
    LEFT JOIN quarterly_financials cbb ON cbb.stock_id = c.stock_id AND cbb.fin_year = c.fin_year - 2 AND cbb.fin_quarter = c.fin_quarter
    ORDER BY s.stock_code, c.fin_year, c.fin_quarter""").fetchall()
per = defaultdict(list)
for r in rows:
    per[r[0]].append(r)

# 3. 逐檔比對
idx = {c: i for i, c in enumerate(S["codes"])}
fqd, n_stock = defaultdict(int), 0
for code, rs in per.items():
    (_, y, q, tbl, seen, ce, rev, gp, op, eq, brev, bgp, beq, cbe, e4, e4p) = rs[-1]
    keep = []                                    # 近 8 季：最新一季往前 8 個季別中有資料的
    for r in rs:
        if (y * 4 + q) - (r[1] * 4 + r[2]) < 8:
            keep.append([r[1] * 100 + r[2], f2(r[9]), yoy(r[9], r[12]), mg(r[7], r[6]), mg(r[8], r[6]), r[6]])
    want = {"t": tbl, "q": keep, "c": {"e": f2(ce), "ey": yoy(ce, cbe), **({"fs": str(seen)} if seen else {})},
            "e4": f2(e4), "e4p": f2(e4p)}
    p = base / "stocks" / f"{code}.json"
    got = json.loads(p.read_text(encoding="utf-8")).get("fin") if p.exists() else None
    if p.exists():
        n_stock += 1
        if got != want:
            bad.append(f"stocks/{code}.json fin")
    if code in idx:
        i = idx[code]
        gm, gmb = mg(gp, rev), mg(bgp, brev)
        eh, sing = 0, [r[9] for r in rs]         # 單季 EPS 高於之前連續幾季（季別必須連續）
        k = len(rs) - 2
        while eq is not None and k >= 0 and (rs[k + 1][1] * 4 + rs[k + 1][2]) - (rs[k][1] * 4 + rs[k][2]) == 1 \
                and sing[k] is not None and sing[k] < eq:
            eh, k = eh + 1, k - 1
        ws = {"eq": f2(eq), "ey": yoy(eq, beq), "e4": f2(e4), "gm": gm,
              "gmy": f2(gm - gmb, 1) if gm is not None and gmb is not None else None, "fq": y * 100 + q, "eh": eh}
        gs = {k2: S[k2][i] for k2 in ws}
        if gs != ws:
            bad.append(f"screen {code}：{ {k2: (gs[k2], ws[k2]) for k2 in ws if gs[k2] != ws[k2]} }")
        fqd[str(y * 100 + q)] += 1
for code in set(S["codes"]) - set(per):
    if any(S[k][idx[code]] is not None for k in ("eq", "ey", "e4", "gm", "gmy", "fq", "eh")):
        bad.append(f"screen {code} 沒有季報卻有值")
if S.get("fqd") != dict(sorted(fqd.items(), reverse=True)):
    bad.append(f"fqd：{S.get('fqd')} ≠ {dict(fqd)}")
print(f"比對 stocks 的 fin {n_stock} 檔、screen {len(S['codes'])} 檔（有季報 {sum(fqd.values())} 檔）")

# 4. 單季 EPS 年增 ≥ X% 的檔數（SQL 計數；以 screen 上的股票為母體）
ey = [v for v in S["ey"] if v is not None]
for x in (0, 20, 50):
    n_sql = sum(1 for code, rs in per.items() if code in idx and (v := yoy(rs[-1][9], rs[-1][12])) is not None and v >= x)
    print(f"單季 EPS 年增 ≥ {x}%：{n_sql} 檔")
    if n_sql != sum(1 for v in ey if v >= x):
        bad.append(f"年增 ≥ {x}% 檔數")

if bad:
    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
    sys.exit(1)
print("✅ 相同")
```
