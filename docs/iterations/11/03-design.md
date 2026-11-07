# 第 11 輪｜System Analyst：設計規格

- 撰寫日期：2026-11-07
- 輸入：`11/01-analyst.md`、`11/02-pm.md`（範圍 F11-3、F11-1、F11-2；**使用者已決定 D19 = B14，D20 依預設 A**）、`10/03-design.md`（格式）。
- 依據：現行程式 `twstock/`（`__main__.py`、`db.py`、`export.py`、`health.py`、`fetch.py`、`collectors/daily.py`、`history.py`、`industry.py`、`catchup.py`）、`site/app.js`、`site/stock.js`、README、`tests/test_iter01～10.py`、`logs/iter10_compare.py`。
- 開工前確認（PM 第五節）：**2 次外部請求**，都經過 `twstock/fetch.request(..., isolated=True)`，不重試，查的是 11/07（星期六）上市、上櫃各 1 次，用來確認休市日的回應格式（結果見 1-3）。11/06、2025-10-30 的回應沿用分析師存在 scratchpad `r11/raw/` 的原始回應，沒有重抓。
- 原型驗證（全部在 scratchpad 進行，不寫專案資料庫，也不改專案程式）：
  - 把 `twstock/`、`site/`（不含 `site/data`）、`tests/`、`scripts/`、`data/`、README、`logs/iter10_compare.py` 複製成 `orig/`（基線）和 `proj/`（原型），**沒有複製 `.env`**。本文所有修改都在 `proj/` 實作，差異見附錄 C。
  - `test_iter01～11` 在原型上全部通過（附錄 B）。`node --check site/app.js site/stock.js` 通過。
  - 解析與匯出計算：用 11/06、2025-10-30 的真實完整回應跑原型的 `parse_sbl`、`sbl_mismatch`、`stock_sbl`、`lots`。數字和 PM 驗收 #4 完全一致（附錄 A）。
  - **沒有做的事**：
    - DDL 與 MERGE 沒有在任何資料庫上執行過，因為不可寫入專案資料庫。交給 PG 依第四節驗證。
    - 沒有以資料庫唯讀連線做模擬匯出，也沒有在 8001 埠預覽畫面，因為 `sbl_trades` 還不存在，注入模擬資料的效益低。匯出時間、畫面（375 px、三條線）都由 PG 在補抓後實測，QA 再驗。
- 實測發現：
  1. **公式全部成立**：11/06 上市、上櫃共 2,242 列，「前日餘額 ＋ 當日賣出 − 當日還券 ＋ 當日調整 ＝ 當日餘額」全部成立。不符合時照存並印警告（PM 傾向）。
  2. **休市與尚未公布的回應**：兩個端點在休市日都回 `stat` 正常、**日期等於請求日期**、資料 0 列。分析師也觀察到，20:30 前上市回應的是前一個交易日的資料（日期不是請求日期）。所以兩種情況用同一條規則：**回應日期 ≠ 請求日期，或沒有資料列 → 0 筆，視為尚未公布**。
  3. **股票列數**：11/06 上市回應的股票列有 1,064 檔，比分析師說的「有行情 1,062 檔」多 2 檔，但借券餘額合計相同（13,177,246 張；多出的 2 檔餘額是 0）。今日頁合計一律用 `sbl_trades` 當天全部股票列，不另外篩選有行情（第十二節 #3）。
  4. **數值範圍**：單檔餘額最大的是上市 3481（約 7.9 億股，INT 上限的 37%），限額最大的是 00406A（2,139 萬股）。PM 原本擔心可能超過 INT，實際沒有，但仍然一律用 BIGINT 留餘裕。上市「合計」列是 182 億股，只拿來驗算，不存。
  5. **`stocks/` 大小估計約 +2.17 MB**，超過 PM 上限 2 MB 約 8%（6-1、第十二節 #1）。`screen.json` 約 +26 KB，`latest.json` 約 +0.1 KB，都在上限內。

---

## 〇、變更總覽

| 編號 | 項目 | 檔案 | 資料庫 | 外部請求 |
|---|---|---|---|---|
| F11-3 | 季報卡口徑說明一句、選股毛利率欄季別小字 | `site/stock.js`、`site/app.js` | 否 | 0 |
| F11-1 | 借券賣出收集、股數、`check` 兩行、個股圖第三條線、指標卡 | `db.py`、`collectors/daily.py`、`industry.py`、`history.py`、`health.py`、`__main__.py`、`export.py`、`site/stock.js`、README | 新表 `sbl_trades`、`etf_sbl`；`stocks` 加 `shares` | 每天 2 次；補抓約 490 次 |
| F11-2 | 借券排行 2 種、今日頁一行、選股條件 2 個 | `export.py`、`site/app.js`、README | 否 | 0 |

### 建議實作順序（細節見第四節）

1. F11-3（只改前端，約 10 行）→ 執行 `test_iter10`、`test_iter11` 的 F11-3 部分。
2. 備份 → `setup-db` 兩次 → 手動跑一次 `update_industry`（寫入股數）。
3. F11-1 收集 → 試補 5 天 → SQL 核對 → 補全部 → 重跑一次，確認 0 次請求。
4. F11-1、F11-2 匯出與前端 → 隔離比對（`iter11_compare.py`）→ 8001 埠預覽 → 關閉。
5. README、`__main__.py`。

---

## 一、資料來源與解析（F11-1）

### 1-1 端點

| 市場 | 方法與網址 | 參數 | 資料位置 |
|---|---|---|---|
| 上市 | `GET https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U` | `date=YYYYMMDD&response=json` | 最上層 `fields`、`data`、`groups`、`date`（YYYYMMDD）、`stat`（"OK"） |
| 上櫃 | `POST https://www.tpex.org.tw/www/zh-tw/margin/sbl` | `date=YYYY/MM/DD`、`response=json` | `tables[0].fields`、`tables[0].data`；最上層 `date`（YYYYMMDD）、`stat`（"ok"） |

- 兩個端點都經過 `fetch.request`（既有的節流與 `_dead_hosts`）。`fetch_sbl(d, market)` 每市場 1 次請求。
- 單位都是**股**；資料庫存股，匯出時才換成張（6-1）。

### 1-2 欄位對應（依位置取值，並逐欄核對欄名）

| 位置 | 上市欄名 | 上櫃欄名 | 欄位 |
|---|---|---|---|
| 0 | 代號 | 股票代號 | `stock_code` |
| 8 | 前日餘額 | 前日餘額 | `sbl_prev` |
| 9 | 當日賣出 | 當日賣出 | `sbl_sell` |
| 10 | 當日還券 | 當日還券 | `sbl_return` |
| 11 | 當日調整 | 當日調整數額 | `sbl_adjust` |
| 12 | 當日餘額 | 當日餘額 | `sbl_balance` |
| 13 | 次一營業日可限額 | 次一營業日可借券賣出限額 | `sbl_limit` |
| 14 | 備註 | 備註 | `note`（原文，去空白，空字串為 NULL） |

- 位置 1～7（名稱、融券 6 欄）不讀；融券已在 `margin_trades` 裡（PM 範圍外）。
- 上市另外核對 `groups` 的前 3 組：`股票(2)`、`融券(6)`、`借券賣出(6)`。這是因為上市的「前日餘額」「當日賣出」等欄名在融券和借券各出現一次，只看欄名分不出是哪一組。
- 任一位置的欄名不符，或上市的 `groups` 不符 → 丟出 `SchemaError("TWT93U 欄位不符：12:當日餘額…")`，不寫入。比照融資融券，由 `_collect_key` 的既有例外處理記為錯誤。

### 1-3 尚未公布、休市、合計列

| 情況 | 回應 | `parse_sbl` |
|---|---|---|
| 正常 | `stat` OK、`date` = d、有資料列 | 回傳所有代號非空的列 |
| 20:30 前 | `date` = 前一個交易日 | `[]`（尚未公布） |
| 休市（11/07 實測） | `stat` OK、`date` = d、0 列 | `[]` |
| `stat` 不是 OK／ok | — | `[]` |
| 上市最後一列「合計」 | 代號是空字串 | 略過 |
| 資料列少於 15 欄 | — | 略過 |

- `stat` 判斷不分大小寫（上市是 `OK`，上櫃是 `ok`）。
- 「`date` ≠ d」的判斷放在解析器，所以 catch-up 與 history 都適用。

### 1-4 股票／ETF 分流（`_collect_key` 的 `SBL` 分支）

- 股票：`is_valid_stock_code`（4～5 碼純數字，不以 00、06 開頭）→ `sbl_trades`。
- ETF：`is_etf_code` → `etf_sbl`。
- 其他（`2887I` 特別股、`912000` TDR、受益證券等）不寫入。
- 沒有股票列 → 回傳 0（尚未公布）。
- MERGE 時 `JOIN stocks`／`JOIN etfs`，只寫入已有的代號，比照 `merge_margin`。

### 1-5 公式驗算 `sbl_mismatch(rows)`

- 回傳不符合「`prev + sell − return + adjust = balance`」的代號；NULL 當 0。
- 有不符時印 `⚠️ sbl.TWSE 有 N 檔不符「前日 + 賣出 − 還券 + 調整 = 餘額」（照存）：代號…`，照存、不中斷（PM 驗收 #3）。

---

## 二、資料表 DDL（F11-1）

`db.py` 的 `SCHEMA` 新增 3 段，都可以重複執行：

```sql
IF OBJECT_ID('sbl_trades') IS NULL
CREATE TABLE sbl_trades (
    id           BIGINT IDENTITY(1,1) PRIMARY KEY,
    stock_id     INT           NOT NULL REFERENCES stocks(stock_id),
    trade_date   DATE          NOT NULL,
    sbl_prev     BIGINT        NOT NULL,   -- 前日餘額
    sbl_sell     BIGINT        NULL,       -- 當日賣出
    sbl_return   BIGINT        NULL,       -- 當日還券
    sbl_adjust   BIGINT        NULL,       -- 當日調整
    sbl_balance  BIGINT        NOT NULL,   -- 當日餘額
    sbl_limit    BIGINT        NULL,       -- 次一營業日可借券賣出限額
    note         NVARCHAR(20)  NULL,       -- 備註原文
    created_at   DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_sbl_trades UNIQUE (stock_id, trade_date)
)
-- etf_sbl：相同欄位，etf_id INT NOT NULL REFERENCES etfs(etf_id)，CONSTRAINT UQ_etf_sbl UNIQUE (etf_id, trade_date)
IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL
-- 加上索引 IX_sbl_trades_date (trade_date)（給 check 的每日計數與匯出用），寫法比照 margin_trades
```

- 股票與 ETF 分表，比照 `margin_trades`／`etf_margin`。這樣排行、今日頁合計、`check` 都不用多寫一個類別條件。
- `stocks.shares`：目前發行股數（股），由 `update_industry` 寫入。**不保留歷史股數**。
- `setup-db` 的完成訊息中，表名清單加入 `sbl_trades、etf_sbl（第 11 輪另加 stocks.shares）`。結尾仍是 `etf_holding_gaps")`，`test_iter06` 的斷言不用改。

---

## 三、收集（F11-1）

### 3-1 資料集與順序

| 項目 | 設計 |
|---|---|
| 資料集名 | `sbl`；鍵 `sbl.TWSE`、`sbl.TPEx`（`daily.DATASET_KEYS["sbl"]`） |
| `DAY_KEYS` 順序 | `… margin.TWSE、margin.TPEx、`**`sbl.TWSE、sbl.TPEx`**`、breadth.TWSE …`（D20 = A：放在信用交易之後） |
| 行情保護 | `SBL` 加進 `_collect_key` 的保護清單：同市場行情 0 列 → 不發請求 |
| `ALL_DATASETS` | **不加**：`history` 不指定 `--only` 時不補借券，避免一次多出 490 次請求。只有 `--only sbl` 才補 |
| `SECONDS_PER_KEY` | `sbl.TWSE: 4`、`sbl.TPEx: 3.2`（比照融資融券） |
| `health.SPECS` | `Spec("sbl.TWSE", "上市借券", 800, False)`、`Spec("sbl.TPEx", "上櫃借券", 550, False)`；`_MARKET_SQL["sbl"]` 數 `sbl_trades` 當天各市場的列數 |
| `__main__.py` | `--only` 的 `choices` 加 `"sbl"`；說明「sbl = 借券賣出」；docstring 加範例 |

- 門檻 800／550：11/06 上市 1,064、上櫃 815 檔，大約抓 75%，比照融資融券的門檻寫法。

### 3-2 公布時間（PM：20:30 前視為尚未公布）

- 解析器回傳 `[]` → `_collect_key` 回傳 0 → `check` 依既有的 `health.DEADLINE`（22:00）判斷：22:00 前是「⏳ 尚未公布」，之後是「❌ 異常」。
- 排程 17:30、19:30 抓不到（正常，標示尚未公布），21:45 抓得到第一版，22:30 那次已經齊了就不會再抓（catch-up 只補缺的）。
- **第二次更新（22:30，加入次日轉上市的股票）不另外重抓**：
  - 只差少數轉市場的股票。
  - 下一個交易日的「前日餘額」會自然接上連續性。
  - 個股圖對缺的那一天顯示 null（斷線一格），可以接受（第八節）。

### 3-3 股數（`collectors/industry.py`）

- `update_industry` 原本就抓 t187ap03_L（上市）與 mopsfin_t187ap03_O（上櫃），本輪一併取股數：
  - 上市：`已發行普通股數或TDR原股發行股數`
  - 上櫃：`IssueShares`
  - 用 `clean_number(n, int) or None` 解析（含逗號；空字串、0 視為 None）。
- UPDATE 改成：

  ```sql
  SET industry = j.industry, shares = ISNULL(j.shares, st.shares)
  WHERE ISNULL(st.industry, '') <> j.industry OR (j.shares IS NOT NULL AND ISNULL(st.shares, -1) <> j.shares)
  ```

  - 這樣空值不會蓋掉既有股數，只更新有變動的列。
  - 訊息改成「產業別、股數：更新 N 檔」。
- 0 個新請求。
- `update_industry` 只在當次有寫入行情時執行（`catchup.py` 第 140 行，**不改**）。PG 上線時用下面這行手動執行一次（第四節步驟 3）：

  ```bash
  python3 -u -c "from twstock.collectors.industry import update_industry; update_industry()"
  ```

  之後每個交易日都會自然更新。

### 3-4 請求量

| 情境 | 請求 |
|---|---|
| 每個交易日 | 上市 1 ＋ 上櫃 1；齊了就不再抓 |
| 補抓 2025-10-30～11/06 | 約 245 天 × 2 ≈ 490 次，約 245 × 7.2 秒 ≈ 30 分鐘 |
| 重跑補抓 | 0 次（只補 `sbl_trades` 當天沒有列的日期） |

---

## 四、PG 實作與資料操作步驟（含驗證與停止條件）

1. **F11-3**：套用附錄 C 的 `stock.js` 口徑說明與 `app.js` 的 `gm`、`gmy` 兩行。
   - 驗證：`test_iter11.py` 的 `test_f11_site`。
   - 停止條件：`iter10_compare.py` 判定匯出檔有任何不同（F11-3 不應改匯出）。
2. **備份**：`python3 -m twstock backup`，在 `04-dev.md` 記錄時間、檔名、大小。必須早於任何程式修改與 `setup-db`（PM F11-1 驗收 #1）。
3. **建表與股數**：
   - 套用 `db.py` → 記錄各表列數 → `setup-db` 執行兩次（第二次不報錯）→ 再記錄列數 → 比對，必須完全相同。
   - 套用 `industry.py` → 手動執行 `update_industry` 一次。
   - SQL 核對：2330 = 25,932,370,067、2408 = 3,450,205,894；11/06 有收盤的股票 `shares IS NULL` 不超過 1%。
   - 停止條件：任何既有表的列數改變，或 `industry` 欄有變成 NULL 的列。
4. **收集程式**：套用 `daily.py`、`health.py`、`history.py`、`__main__.py`，以及舊測試的修改（`test_iter03.py`、`test_iter05.py`）和新測試。
   - 驗證：`test_iter01～11` 全部通過。
5. **試補 5 天**：

   ```bash
   python3 -u -m twstock history --start 2026-10-31 --only sbl 2>&1 | tee logs/iter11_sbl_try.log
   ```

   - 應該是 10 次請求。
   - 用附錄 A-1 的 SQL 核對 11/06 的 4 檔、上市合計、上櫃合計。
   - 停止條件：任一數字不符，或出現公式不符的警告。
6. **補全部**：

   ```bash
   python3 -u -m twstock history --start 2025-10-30 --only sbl 2>&1 | tee logs/iter11_sbl_history.log
   ```

   - 記錄請求次數、耗時、每市場的天數與筆數。
   - 核對 2025-10-30 的 3 檔（附錄 A-1）。
   - 再執行一次 → 0 次請求。
7. **匯出與前端**：套用 `export.py`、`app.js`、`stock.js`、`logs/iter11_compare.py`。
   - 先在改前匯出到暫存資料夾作為基線，再改後匯出。
   - `python3 logs/iter11_compare.py 基線 site/data` 必須判定「✅ 相同」；`--keep-new` 必須判定不同（反證）。
   - 記錄新鍵大小與匯出時間（不超過 +3 秒）。
8. **畫面**：`serve --port 8001 --no-browser`，在 375 px 和桌面檢查第七節列出的頁面，結束後關閉 8001。
9. **文件**：README、`__main__.py`（第十節）。

---

## 五、F11-3 第 10 輪收尾小修

### 5-1 季報卡口徑說明（`site/stock.js`，文字定稿）

在既有的口徑說明之後加一句：

> 官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。

所有股票都顯示（不只 2408）。

### 5-2 選股毛利率欄季別小字（`site/app.js`）

`SCR_COLS` 的 `gm`、`gmy` 改成和 `eq` 一樣，在數字後面接 `finTag(x)`：

```js
gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)],
```

- `finTag` 原本就是「該列季別 ≠ 欄名季別才加小字」，所以季別相同的列不會有小字（PM F11-3 驗收 #2）。
- 不改匯出，也不改 README（README 沒有寫季報口徑的段落）。

---

## 六、匯出 JSON 欄位與大小（F11-1、F11-2）

### 6-1 `stocks/{代號}.json`

1. **`mg.lb`**：和 `mg.mb`、`mg.sb` 同一組日期（`prices.d`），值是借券賣出餘額（張），沒有資料的日期是 `null`。
   - 該股有借券列時才加。
   - **只有借券、沒有融資融券的股票不畫圖**：`mg` 仍然是 `None`，但下面的 `sbl` 鍵照樣輸出。
2. **`sbl`**（最新一日；該股在**該市場最新借券日**沒有列 → 不輸出這個鍵）：

   | 鍵 | 意義 | 規則 |
   |---|---|---|
   | `d` | 資料日 | 該市場最新借券日 |
   | `lb` | 餘額（張） | `lots(sbl_balance)` |
   | `l1` | 1 日增減（張） | `lots(balance − prev)`，用官方「前日餘額」，不用前一列 |
   | `l5` | 5 日增減（張） | `lots(balance − 5 個借券日前的餘額 × k)`。k 是融資融券的面額變更換算（`conv_k`）；沒有 5 日前資料 → `null` |
   | `lp` | 占股本 % | `round(balance ÷ shares × 100, 2)`；`shares` 為 NULL 或 0 → 不輸出 |
   | `lx` | 借券 ÷ 融券（倍） | `round(balance ÷ (融券餘額張 × 1000), 1)`；融券 0 或沒有 → 不輸出 |
   | `nt` | 備註 | 有才輸出 |

- 張數換算 `lots()`：**四捨五入到整數張，正負對稱（half away from zero）**，例如 499 股 → 0、500 股 → 1、−500 股 → −1、−1,500 股 → −2。
- 例子（2330，11/06）：`{"d":"2026-11-06","lb":20183,"l1":1770,"l5":…,"lp":0.08,"lx":269.1}`。
- **大小估計**：
  - 以 11/06 與 2025-10-30 兩天的真實餘額估平均字數，每檔 `lb` 序列約 247 天 × 4.3 字 ≈ 1.07 KB，加上 `sbl` 約 75 B。
  - 1,879 檔共約 **2.17 MB**（目前 `stocks/` 是 33.3 MB，增加約 6.5%）。
  - 超過 PM 上限 2 MB 約 8%，見第十二節 #1。

### 6-2 `screen.json`

- `SCREEN_KEYS` 加 `lb`、`l1`、`l5`、`lp`（意義同 6-1；沒有資料是 `null`）。
- `head` 加 `sd`：`{"TWSE": "2026-11-06", "TPEx": "2026-11-06"}`，各市場的借券資料日。
- 估計增加約 26 KB（上限 40 KB）。
- 排行與選股在前端計算估算金額：`la1`／`la5` = `l1`／`l5` × 1000 × 收盤 ÷ 1e8（億），不另外匯出。

### 6-3 `latest.json` 的 `sbl`

```json
"sbl": {"TWSE": {"d": "2026-11-06", "lb": 13177246, "l1": 169983, "n": 1064},
        "TPEx": {"d": "2026-11-06", "lb": 1769466, "l1": 15063, "n": 815}}
```

- 股票口徑（不含 ETF），統計 `sbl_trades` 該市場最新日的全部列。
- 張數是**先加總股數再換算**，不是逐檔換算後再加總；`l1` 是股數相減後再換算，所以上市是 169,983 張，不是「13,177,246 − 13,007,262 = 169,984」（相差 1 張是四捨五入，QA 用 SQL 要同樣先減後除）。
- 沒有任何借券資料 → 不輸出這個鍵。約 0.1 KB。

### 6-4 載入與匯出時間

- `_load_sbl` 一次查詢讀出 `sbl_trades` 全部列（約 1,879 × 245 ≈ 46 萬列，和 `margin_trades` 同量級）。
- PG 實測匯出時間，上限是 +3 秒。
- 如果超過，改成只讀 `trade_date >= prices.d[0]` 的列，並在 `04-dev.md` 記錄。

---

## 七、畫面規格

### 7-1 個股頁 `#/stock/{代號}`

1. **融資融券圖第三條線**（`mg.lb` 存在時）：
   - 「借券賣出」：顏色 `#E8590C`、虛線（`lineStyle: 2`），**獨立的價格座標軸** `priceScaleId: 'lb'`，並設定 `scaleMargins`。
   - 這樣融券線（2330 只有 75 張）不會被借券（2 萬張）壓平。
   - 圖例加「借券」；圖標題從「融資／融券餘額」變成「融資／融券／借券賣出餘額」。
   - 週線、月線的彙總也包含 `lb`（取期間最後一個有值的餘額，和 `mb`、`sb` 相同）。
   - 面額變更時，用 `gk` 換算的方式和 `mb`、`sb` 相同（`mgAt` 統一用 `sc()`）。
2. **指標卡**（`sbl` 存在時，接在融資融券指標卡之後；沒有 `sbl` 就不顯示、也不報錯）：
   - 「借券賣出餘額」：`lb` 張，下面一行是 1 日 `l1`、5 日 `l5`。
   - 「借券占股本」：`lp`%，下面一行是「融券的 `lx` 倍」與資料日。沒有 `lp` 就顯示 `--`。
3. **說明文字（定稿）**：

   > 借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本以目前發行股數計算。借券資料晚上 8 點半以後才更新。

### 7-2 排行 `#/rank/l+`、`#/rank/lp`

- `RANKS` 加兩項：
  - `['l+', '借券賣出增加', 'la*', -1, 'l']`：依估算金額排序，1 日／5 日切換。
  - `['lp', '借券占股本', 'lp', -1, 'l']`
- `RANK_GROUPS` 加一組 `['借券', ['l+', 'lp']]`。
- 資料來源是 `screen.json`（`src === 'l'`），成交額門檻、不含 ETF 都和融資融券排行相同。
- 表格欄位：股票、收盤、漲跌、5 日漲跌、借券餘額、借券 1 日／5 日、估算（億）、占股本、融券餘額、成交額。
- 頁尾說明（定稿）：

  > 借券資料日：上市 MM/DD、上櫃 MM/DD。估算金額 = 借券賣出增減張數 × 1,000 × 收盤，是估算。借券賣出含避險、套利（ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本 = 借券賣出餘額 ÷ 目前發行股數（不是當時股數）。資料晚上 8 點半以後才更新。不含 ETF。

### 7-3 今日頁信用交易卡一行（`sblLine`）

- 寫法：「借券賣出餘額　上市 **1,318** 萬張 +169,983　（融券的 127 倍）　上櫃 **177** 萬張 +15,063（融券的 N 倍）　看排行 →」。
  - 萬張的小數位：100 萬張以上取整數，以下取 1 位。滑鼠移上去顯示完整張數。
- 倍數 = 該市場 `sbl.lb` ÷ 信用交易卡的融券合計 `margin.{市場}.sb`（同樣是股票口徑、張）。
- 借券資料日和信用交易卡的資料日不同時，在後面加「（MM/DD）」。
- 第二行說明：「借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新」。

### 7-4 選股 `#/rank/screen`

- `SCREEN_CONDS` 在「信用」組加兩個條件：
  - `lp`：「借券占股本 ≥ {v}%」，選項 3／5／8，預設 5，顯示欄 `lb`、`lp`。
  - `l5`：「借券 5 日增加 ≥ {v} 張」，選項 500／1,000／5,000，預設 1,000，顯示欄 `lb`、`l5`。
- `null` 一律不符合（`scrGe` 原本就是這樣）。
- 網址分享與「重設」沿用既有機制。
- `SCR_COLS` 加 `lb`、`l5`、`lp`；`lb`、`lp` 不上色。

---

## 八、邊界情況總表

| # | 情況 | 處理 |
|---|---|---|
| 1 | 20:30 前（回應是前一個交易日） | 0 筆、不寫入；22:00 前是「尚未公布」 |
| 2 | 休市日 | catch-up、history 本來就不排休市日；即使請求了，也是 0 筆 |
| 3 | 當天行情 0 列 | 不發借券請求（行情保護） |
| 4 | 欄名或 `groups` 改變 | `SchemaError`，不寫入，記為錯誤 |
| 5 | 公式不符 | 照存，印警告 |
| 6 | 代號不在 `stocks`／`etfs` | MERGE 時 JOIN 不到，不寫入 |
| 7 | 特別股、TDR、受益證券 | 不寫入 |
| 8 | 22:30 第二版才出現的股票 | 不重抓；下一天補上，圖上缺一格 |
| 9 | `shares` 為 NULL | 不輸出 `lp`；選股的 `lp` 條件不符合；占股本排行不出現 |
| 10 | 融券 0 | 不輸出 `lx`；指標卡不顯示倍數 |
| 11 | 5 日前沒有借券資料（剛補抓、新上市） | `l5` = null |
| 12 | 面額變更 | 5 日前餘額 × k（同融資融券的 `conv_k`）；圖用 `gk` 換算 |
| 13 | 只有借券、沒有融資融券 | 不畫圖（`mg` 為 None），但有 `sbl` 指標卡 |
| 14 | 借券日和行情日不同（行情已更新、借券還沒） | 指標卡、排行頁尾、今日頁一行都標示借券的資料日 |
| 15 | 負數張數（餘額減少） | `lots` 正負對稱四捨五入 |
| 16 | 某個市場完全沒有借券資料 | `latest.sbl` 只有另一個市場；`screen.head.sd` 缺該市場，頁尾顯示 `--` |

---

## 九、測試

### 9-1 `tests/test_iter11.py`（新檔，全文見附錄 C）

- 不連網、不連資料庫，`python3 tests/test_iter11.py`，相容 pytest。共 11 個測試：

  | 測試 | 內容 |
  |---|---|
  | `test_f111_parse_twse` | 上市 fixture 8 列（合計列略過）；2330、2408 的完整值；股票 4 檔、ETF 2 檔，`2887I`、`912000` 兩邊都不是；公式全部成立 |
  | `test_f111_parse_tpex` | 上櫃 6 列；`006201` 的完整值 |
  | `test_f111_not_published_and_schema` | 日期不符、休市、`stat` 不是 OK → `[]`；欄名、`groups`、上櫃欄名不符 → `SchemaError`；竄改餘額 → `sbl_mismatch` 抓到 |
  | `test_f111_ddl_and_keys` | DDL 原始碼、`DATASET_KEYS`、`ALL_DATASETS` 不含 sbl、`DAY_KEYS` 順序、`SPEC` 門檻、`SECONDS_PER_KEY`、`__main__.py` |
  | `test_f111_collect` | World 寫入 1,100／900 筆、兩張表各 MERGE 2 次、各 1 次請求；行情 0 列 → 0 次借券請求；上櫃尚未公布 → 0 筆、不是錯誤 |
  | `test_f111_before_2030` | 回應日期是前一個交易日 → 0 筆、不寫入、不是錯誤 |
  | `test_f111_catchup_and_history` | 21:00 是「尚未公布」，22:40 只補 TWT93U 1 次；`history --only sbl` 3 天 × 2 次，不抓行情；重跑 0 次請求 |
  | `test_f111_shares` | `update_industry` 解析股數（含逗號、空字串 → None），SQL 有 `ISNULL(j.shares, st.shares)` |
  | `test_f112_export_calc` | `lots` 的正負對稱；`stock_sbl` 2330（`lp` 0.08、`lx` 269.1）、沒有股數或融券、不是最新日、面額換算；`market_sbl`；`margin_series` 的 `lb` |
  | `test_f112_export_source` | `screen.head.sd`、`latest.sbl` 的寫法 |
  | `test_f11_site` | 說明文字、`priceScaleId: 'lb'`、`RANKS`、`SCREEN_CONDS`、F11-3 兩點 |

- fixture（`tests/fixtures/`，官方原始回應的精簡版，欄位不變）：
  - `twt93u_20261106_mini.json`（00400A、0050、1538、2303、2330、2408、2887I、912000、合計）
  - `sbl_tpex_20261106_mini.json`（00411A、006201、3064、3066、3071、3073）
  - `twt93u_20261107_holiday.json`、`sbl_tpex_20261107_holiday.json`（11/07 實測）

### 9-2 舊測試修改

- `test_iter03.py`：
  - `_full_snapshot` 加 `sbl.TWSE` Row(1100)、`sbl.TPEx` Row(900)。
  - `ALL_EP` 加 `TWT93U`、`margin/sbl`。
  - `World.http` 把兩個端點導到 `_sbl`：未公布時回應「日期 = 請求日、0 列」。
  - `apply_merge` 認得 `sbl_trades`。
  - 沒有這些修改，`test_iter03／04／05／07／09／10` 會因為 `KeyError 'sbl.TWSE'` 或沒有路由而失敗。
- `test_iter05.py`：`choices` 字串斷言改成 `'"margin", "holdings", "sbl"]'`。

### 9-3 QA 清單與 SQL（PG 也用來核對試補）

```sql
-- PM F11-1 驗收 #4：11/06 四檔
SELECT s.stock_code, x.sbl_prev, x.sbl_balance, x.sbl_balance - x.sbl_prev AS d1
FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id
WHERE x.trade_date = '2026-11-06' AND s.stock_code IN ('2330', '2408', '2303');
SELECT e.etf_code, x.sbl_balance, x.sbl_balance - x.sbl_prev FROM etf_sbl x JOIN etfs e ON e.etf_id = x.etf_id
WHERE x.trade_date = '2026-11-06' AND e.etf_code = '0050';
-- 市場合計（今日頁）：張 = ROUND(SUM(股) / 1000)
SELECT s.market_type, COUNT(*), SUM(x.sbl_balance), SUM(x.sbl_prev)
FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id WHERE x.trade_date = '2026-11-06' GROUP BY s.market_type;
-- 占股本前 5
SELECT TOP 5 s.stock_code, x.sbl_balance * 100.0 / s.shares AS pct
FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id
WHERE x.trade_date = '2026-11-06' AND s.shares > 0 ORDER BY pct DESC;
-- 公式（應為 0 列）
SELECT COUNT(*) FROM sbl_trades
WHERE sbl_prev + ISNULL(sbl_sell, 0) - ISNULL(sbl_return, 0) + ISNULL(sbl_adjust, 0) <> sbl_balance;
-- 每市場天數與筆數（補抓紀錄）
SELECT s.market_type, COUNT(DISTINCT x.trade_date), COUNT(*)
FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id GROUP BY s.market_type;
```

- 選股兩個條件的檔數：用上面的資料與 `screen.json` 的共同排除獨立計算（PM F11-2 驗收 #4）。
- 隔離比對：`logs/iter11_compare.py`（附錄 C）。剔除的新鍵是 `latest.sbl`、`stocks.sbl`、`stocks.mg.lb`、`screen.sd`、`lb`、`l1`、`l5`、`lp`。

---

## 十、README 與 `__main__.py` 修改清單

### README

- 資料表：`sbl_trades`、`etf_sbl`（單位股、6 欄＋備註）、`stocks.shares`（目前股數，不保留歷史）。
- 收集：`sbl.TWSE`、`sbl.TPEx` 放在信用交易之後；**借券資料晚上 8 點半以後才有**；22:30 的第二版不重抓。
- 補抓：

  ```bash
  python3 -u -m twstock history --start 2025-10-30 --only sbl
  ```

  約 490 次請求、30 分鐘；不指定 `--only` 時不補借券。
- `check`：多「上市借券」「上櫃借券」兩行。
- 匯出：`stocks/{代號}.json` 的 `sbl`、`mg.lb`；`latest.json` 的 `sbl`；`screen.json` 的 `lb`、`l1`、`l5`、`lp`、`head.sd`。
- 網站功能：個股融資融券圖第三條線、借券指標卡、借券排行 2 種、今日頁一行、選股條件 2 個；「不等於看空」的說明。
- 「現有資料」一段加「借券賣出（2025-10-30 起）」。

### `__main__.py`

- `--only` 的 `choices` 加 `"sbl"`，說明加「sbl = 借券賣出」。
- docstring 加：`history --start 2025-10-30 --only sbl  只補借券賣出（上市、上櫃各 1 個請求／天；晚上 8 點半後才有當天資料）`。

---

## 十一、延後順序（沿用 PM）

如果 PG 時間不夠，依序延後：

1. 選股條件
2. 今日頁一行
3. 占股本排行

F11-1 全部（收集、股數、圖、指標卡）與 F11-3 不延後。

---

## 十二、對 PM 範圍的調整建議（不改 02-pm.md）

1. **`stocks/` 上限 2 MB → 2.5 MB**：
   - 估計 +2.17 MB，主要來自 247 天的 `lb` 序列。
   - 如果要壓到 2 MB 以下，只能縮短序列（例如只放 120 天），但這樣 2408「一年前從約 11,140 張升到約 96,099 張」（F11-1 驗收 #9）就看不到了。
   - 建議放寬上限，不縮短序列。PG 以實測為準；實測超過 2.5 MB 時停下來回報。
2. **略過筆數不在每晚收集時印出**：
   - PM 要求「略過的筆數要印出來」。但 MERGE 是 `JOIN stocks`，要另外查一次才知道略過多少筆。融資融券也沒有印。
   - 改由 PG 在試補與補抓後，用 SQL 比對「回應的股票列數」與「寫入列數」，記在 `04-dev.md`；QA 再驗。
3. **今日頁合計不篩選有行情**：
   - 統計 `sbl_trades` 當天全部列。11/06 上市 1,064 檔，比有行情的 1,062 檔多 2 檔，但合計相同。
   - PM F11-2 驗收 #3 的 SQL 改成同一口徑（9-3）。
4. **`history` 不指定 `--only` 時不補借券**（3-1）：避免日後補其他資料集時意外多出數百次請求。
5. **`update_industry` 不改觸發條件**：上線時手動執行一次（3-3），之後每個有行情的晚上都會更新。

---

## 十三、給 PG、QA 的提醒

- 資料庫存**股**，匯出、畫面一律用**張**；比對數字時注意單位。
- `parse_sbl` 的「日期 ≠ d → []」是尚未公布的唯一判斷；不要再加時間判斷。
- 原型的 DDL 與 MERGE **沒有在資料庫上執行過**；第四節步驟 3、5 是第一次。
- 匯出時間與畫面沒有在原型上實測（見開頭「沒有做的事」）。
- 8001 埠用完要關；不要動 `.env`；不要安裝排程。

---

## 附錄 A：預期值

### A-1 個股與市場（11/06，原型解析真實完整回應）

| 項目 | 前日餘額（股） | 餘額（股） | 1 日（股） | 匯出 `lb`／`l1`（張） |
|---|---|---|---|---|
| 2330 | 18,412,514 | 20,182,514 | +1,770,000 | 20,183／1,770；`lp` 0.08、`lx` 269.1（融券 75 張） |
| 2408 | 96,809,884 | 96,098,884 | −711,000 | 96,099／−711 |
| 2303 | — | 128,740,952 | +3,648,000 | 128,741／3,648 |
| 0050（`etf_sbl`） | — | 261,795,000 | +7,030,000 | ETF，不進個股匯出 |
| 上市股票合計（1,064 檔） | 13,007,262 張 | 13,177,246 張 | +169,983 張（股數相減後換算） | `latest.sbl.TWSE` |
| 上櫃股票合計（815 檔） | 1,754,403 張 | 1,769,466 張 | +15,063 張 | `latest.sbl.TPEx` |

- 2025-10-30：2408 為 11,139,714 股、2303 為 933,973,589 股、2330 為 7,616,753 股。
- 上市「合計」列：18,225,069,614 股（不存，只拿來驗算）。

### A-2 大小估計

| 檔案 | 估計 | 上限 |
|---|---|---|
| `stocks/` | +2.17 MB（1,879 檔） | 2 MB（建議 2.5 MB） |
| `screen.json` | +26 KB | 40 KB |
| `latest.json` | +0.1 KB | 1 KB |

---

## 附錄 B：原型的驗證方式（供 PG 重現，不需照做）

```bash
# scratchpad r11/proto/proj
for i in 01 02 03 04 05 06 07 08 09 10 11; do python3 -u tests/test_iter$i.py; done   # 全部「全部通過」
node --check site/app.js && node --check site/stock.js
```

- 解析與大小估計是用 `r11/raw/` 的 11/06、2025-10-30 完整回應，加上 t187ap03_L／O，以原型函式計算。

---

## 附錄 C：原型完整差異（`diff -ruN orig proj`）

```diff
diff -ruN -x __pycache__ -x *.pyc orig/logs/iter11_compare.py proj/logs/iter11_compare.py
--- orig/logs/iter11_compare.py	1970-01-01 08:00:00
+++ proj/logs/iter11_compare.py	2026-11-07 00:50:27
@@ -0,0 +1,63 @@
+# 用法：python3 logs/iter11_compare.py 基線資料夾 site/data [--keep-new] —— 隔離比對（第 11 輪，取代 iter10_compare.py）
+# 除了第 11 輪指定的新鍵與「時間」欄位以外必須完全相同；比對 latest.json、screen.json、stocks/*.json、etfs/*.json。
+# 新鍵：latest.json 的 sbl；stocks/*.json 的 sbl 與 mg.lb；screen.json 的 sd、lb、l1、l5、lp。
+# 另外印出新鍵的大小（stocks 的 sbl＋mg.lb 合計、screen 新欄合計、latest 的 sbl）。
+# --keep-new：不剔除新鍵（反證用，應判定不同）。相同印「✅ 相同」rc=0，否則 rc=1。
+import json, sys
+from pathlib import Path
+a, b = Path(sys.argv[1]), Path(sys.argv[2])
+KEEP = "--keep-new" in sys.argv
+NEW_LATEST = set() if KEEP else {"sbl"}
+NEW_STOCK = set() if KEEP else {"sbl"}
+NEW_SCREEN = set() if KEEP else {"sd", "lb", "l1", "l5", "lp"}
+TIME_LATEST, TIME_STATUS = {"updated_at"}, {"exported_at", "collected_at"}
+bad = []
+drop = lambda d, keys: {k: v for k, v in d.items() if k not in keys}
+load = lambda p: json.loads(p.read_text(encoding="utf-8"))
+size = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode())
+
+
+def strip_stock(y):
+    y = drop(y, NEW_STOCK)
+    if not KEEP and isinstance(y.get("mg"), dict) and "lb" in y["mg"]:
+        y = {**y, "mg": drop(y["mg"], {"lb"})}
+    return y
+
+
+LA, LB = load(a / "latest.json"), load(b / "latest.json")
+LB2 = drop(LB, NEW_LATEST)
+if set(LA) != set(LB2):
+    bad.append(f"latest.json 鍵不同：{sorted(set(LA) ^ set(LB2))}")
+for k in set(LA) & set(LB2):
+    if k in TIME_LATEST:
+        continue
+    x, y = (drop(LA[k], TIME_STATUS), drop(LB2[k], TIME_STATUS)) if k == "status" else (LA[k], LB2[k])
+    if x != y:
+        bad.append(f"latest.json {k}")
+SA, SB = load(a / "screen.json"), load(b / "screen.json")
+if SA != drop(SB, NEW_SCREEN):
+    bad.append("screen.json")
+n, new_bytes, new_n = {}, 0, 0
+for sub in ("stocks", "etfs"):
+    fa = {f.name for f in (a / sub).glob("*.json")}
+    fb = {f.name for f in (b / sub).glob("*.json")}
+    if fa != fb:
+        bad.append(f"{sub} 檔案不同：少 {sorted(fa - fb)[:5]} 多 {sorted(fb - fa)[:5]}")
+    for f in sorted(fa & fb):
+        x, y = load(a / sub / f), load(b / sub / f)
+        if sub == "stocks" and ("sbl" in y or "lb" in (y.get("mg") or {})):
+            new_bytes += (size(y["sbl"]) + len(',"sbl":') if "sbl" in y else 0) \
+                + (size(y["mg"]["lb"]) + len(',"lb":') if "lb" in (y.get("mg") or {}) else 0)
+            new_n += 1
+        if x != (strip_stock(y) if sub == "stocks" else y):
+            bad.append(f"{sub}/{f}")
+    n[sub] = len(fa)
+print(f"比對 latest.json、screen.json、stocks {n['stocks']} 檔、etfs {n['etfs']} 檔（略過 {sorted(TIME_LATEST)}、status.{sorted(TIME_STATUS)}"
+      + ("" if KEEP else "；剔除新鍵 latest 的 sbl、stocks 的 sbl 與 mg.lb、screen 的 sd、lb、l1、l5、lp") + "）")
+scr = sum(size(SB[k]) + len(k) + 4 for k in ("sd", "lb", "l1", "l5", "lp") if k in SB)
+print(f"ℹ️  新鍵大小：stocks 的 sbl＋mg.lb {new_n} 檔共 {new_bytes / 1024:.0f} KB；screen.json 新欄 {scr / 1024:.1f} KB；"
+      f"latest.json sbl {size(LB['sbl']) if 'sbl' in LB else 0} B")
+if bad:
+    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
+    sys.exit(1)
+print("✅ 相同")
diff -ruN -x __pycache__ -x *.pyc orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-06 23:47:12
+++ proj/site/app.js	2026-11-07 00:46:18
@@ -265,6 +265,7 @@
       ${row(T, '上市')}${row(O, '上櫃')}
       <div class="s num">融資維持率（自算）上市 ${mr(T)}　上櫃 ${mr(O)}</div>
       <div class="s num">融資金額（官方，含 ETF）上市 ${amt(T)}　上櫃 ${amt(O)}</div>
+      ${sblLine(L)}
       ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
       ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
       <div class="s">維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
@@ -272,6 +273,17 @@
     </div>`;
 }
 
+// 第 11 輪 B14：借券賣出餘額（股票口徑，張）與融券的倍數；倍數用同一市場信用交易卡的融券合計
+function sblLine(L) {
+  const B = L.sbl, M = L.margin;
+  if (!B) return '';
+  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
+  const one = (x, m, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>` +
+    (M?.[m]?.sb ? `（融券的 ${fmt(x.lb / M[m].sb, 0)} 倍）` : '') + (x.d !== (M?.[m]?.d ?? x.d) ? `<span class="muted">（${md(x.d)}）</span>` : '');
+  return `<div class="s num">借券賣出餘額　${[one(B.TWSE, 'TWSE', '上市'), one(B.TPEx, 'TPEx', '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/rank/l+">看排行 →</a></div>
+      <div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>`;
+}
+
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
 function breadthCard(L) {
   const B = L.breadth;
@@ -658,9 +670,10 @@
   ['ry', '營收年增', 'ry', -1, 'x'], ['dy', '殖利率', 'dy', -1, 'v'], ['pe', '本益比最低', 'pe', 1, 'v'],
   ['m+', '融資增加', 'm*', -1, 'm'], ['m-', '融資減少', 'm*', 1, 'm'], ['mr', '融資增加率', 'mr*', -1, 'm'],
   ['s+', '融券增加', 's*', -1, 'm'], ['s-', '融券減少', 's*', 1, 'm'], ['sr', '券資比', 'sr', -1, 'm'], ['mu', '融資使用率', 'mu', -1, 'm'],
+  ['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l'],     // 第 11 輪 B14：'l' = 借券（需要 screen.json）
 ];
 const RANK_GROUPS = [['法人', ['n+', 'n-', 'f+', 'f-', 't+', 't-', 'd+', 'd-', 'fs', 'ts', 's']], ['價量', ['p+', 'p-', 'tv', 'vr', 'nh', 'rs20']],
-  ['基本面', ['ry', 'dy', 'pe']], ['融資融券', ['m+', 'm-', 'mr', 's+', 's-', 'sr', 'mu']]];
+  ['基本面', ['ry', 'dy', 'pe']], ['融資融券', ['m+', 'm-', 'mr', 's+', 's-', 'sr', 'mu']], ['借券', ['l+', 'lp']]];
 // screen.json 排行的額外篩選與表格欄位
 const RANK_FILTER = { nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
 const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'] };
@@ -710,7 +723,11 @@
     const inMkt = x => mkt === 'all' || x.m === mkt;
     const list = screenRows().filter(x => isNum(x[field]) && (RANK_FILTER[by] || (() => true))(x) && inMkt(x) && (x.tv ?? 0) >= Number(minTv))
       .sort((a, b) => dir * (a[field] - b[field]) || (src === 'm' ? (a.code < b.code ? -1 : 1) : b.tv - a.tv)).slice(0, 50);
-    if (src === 'm') {
+    if (src === 'l') {
+      const sds = [...new Set(Object.entries(S.sd || {}).filter(([m]) => mkt === 'all' || m === mkt).map(([, d]) => md(d)))].join('、');
+      table = sblTable(list, span);
+      foot = `借券資料日：上市 ${S.sd?.TWSE ? md(S.sd.TWSE) : '--'}、上櫃 ${S.sd?.TPEx ? md(S.sd.TPEx) : '--'}（${sds || '--'}）。估算金額 = 借券賣出增減張數 × 1,000 × 收盤，是估算。借券賣出含避險、套利（ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本 = 借券賣出餘額 ÷ 目前發行股數（不是當時股數）。資料晚上 8 點半以後才更新。不含 ETF。`;
+    } else if (src === 'm') {
       const all = screenRows().filter(inMkt), cnt = (k, sg) => all.filter(x => isNum(x[k]) && sg * x[k] > 0).length;
       const mds = [...new Set(Object.entries(S.md).filter(([m]) => mkt === 'all' || m === mkt).map(([, d]) => md(d)))].join('、');
       table = `<div class="muted small tbl-cap">融資增加 ${fmt(cnt('m' + span, 1))} 家、減少 ${fmt(cnt('m' + span, -1))} 家；融券增加 ${fmt(cnt('s' + span, 1))} 家、減少 ${fmt(cnt('s' + span, -1))} 家（${span} 日，股票，融資融券 ${mds || '--'}）</div>` +
@@ -756,6 +773,18 @@
     '</tbody></table></div>';
 }
 
+// 第 11 輪 B14：借券排行的表格
+function sblTable(list, span) {
+  const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
+  return `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>借券餘額</th><th>借券${lbl}</th><th>估算（億）</th><th>占股本</th><th>融券餘額</th><th>成交額</th></tr></thead><tbody>` +
+    list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
+      <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num ${cls(x.r5)}">${isNum(x.r5) ? sgn(x.r5) + '%' : '--'}</td>
+      <td class="num">${isNum(x.lb) ? fmt(x.lb) : '--'}</td><td class="num ${cls(x['l' + k])}">${isNum(x['l' + k]) ? sgn(x['l' + k], 0) : '--'}</td>
+      <td class="num ${cls(x['la' + k])}">${isNum(x['la' + k]) ? yi(x['la' + k]) : '--'}</td><td class="num">${isNum(x.lp) ? fmt(x.lp, 2) + '%' : '--'}</td>
+      <td class="num">${isNum(x.sb) ? fmt(x.sb) : '--'}</td><td class="num">${fmt(x.tv, 1)}億</td></tr>`).join('') +
+    '</tbody></table></div>';
+}
+
 // ─── 第 8 輪 F8-2：條件選股（screen.json 與 latest.json stocks 合併）──────────
 const isNum = v => typeof v === 'number';       // null、undefined 一律不符合（null >= 0 在 JS 是 true）
 async function loadScreen() {
@@ -776,6 +805,7 @@
     const v = x['m' + n];
     x['ma' + n] = isNum(v) && isNum(x.c) ? v * 1000 * x.c / 1e8 : null;
     x['mr' + n] = isNum(v) && isNum(x.mb) && x.mb - v >= MARGIN_BASE ? v / (x.mb - v) * 100 : null;
+    x['la' + n] = isNum(x['l' + n]) && isNum(x.c) ? x['l' + n] * 1000 * x.c / 1e8 : null;   // 第 11 輪：借券增減估算金額（億）
   }
   return x;
 }
@@ -815,8 +845,9 @@
   pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
   pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
   eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => spct(v) + finTag(x)],
-  e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, v => fmt(v, 1) + '%'],
-  gmy: ['毛利率年增', x => x.gmy, v => sgn(v, 1) + '點'], eh: ['EPS新高(季)', x => x.eh, int0],
+  e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
+  gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)], eh: ['EPS新高(季)', x => x.eh, int0],
+  lb: ['借券餘額', x => x.lb, v => fmt(v)], l5: ['借券5日', x => x.l5, v => sgn(v, 0)], lp: ['借券占股本', x => x.lp, v => fmt(v, 2) + '%'],
 };
 const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
 // 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動}；sort 有值時欄名可點排序
@@ -828,7 +859,7 @@
     list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
       <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.tv, 1)}億</td>` +
       cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
-        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
+        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh', 'lb', 'lp'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
     '</tbody></table></div>';
 }
 
@@ -869,6 +900,9 @@
     f: (x, v) => { const b = m5Base(x); return isNum(b) && b >= MARGIN_BASE && x.m5 / b * 100 >= v; }, cols: ['m5', 'm5p'] },
   { id: 'sr', g: '信用', label: '券資比 ≥ {v}%（融資 ≥ 1,000 張）', opts: [10, 20, 30], def: 20, f: (x, v) => isNum(x.mb) && x.mb >= MARGIN_BASE && isNum(x.sr) && x.sr >= v, cols: ['sr'] },
   { id: 'mu', g: '信用', label: '融資使用率 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('mu'), cols: ['mu'] },
+  // 第 11 輪 B14：借券（null = 沒有借券資料或沒有股數 → 不符合）
+  { id: 'lp', g: '信用', label: '借券占股本 ≥ {v}%', opts: [3, 5, 8], def: 5, f: scrGe('lp'), cols: ['lb', 'lp'], title: '借券賣出餘額 ÷ 目前發行股數；借券含避險、套利，不等於看空' },
+  { id: 'l5', g: '信用', label: '借券 5 日增加 ≥ {v} 張', opts: [500, 1000, 5000], def: 1000, f: scrGe('l5'), cols: ['lb', 'l5'] },
   { id: 'ry', g: '基本面', label: '營收年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('ry'), cols: ['ry'] },
   { id: 'rc', g: '基本面', label: '累計年增 ≥ {v}%', opts: [20, 30, 50], def: 30, f: scrGe('rc'), cols: ['rc'] },
   { id: 'rh', g: '基本面', label: '營收創新高', sw: true, f: scrPos('rh'), cols: ['rh'] },
diff -ruN -x __pycache__ -x *.pyc orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-07 00:13:13
+++ proj/site/stock.js	2026-11-07 00:45:44
@@ -60,6 +60,10 @@
        ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
        ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
        ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
+  // 第 11 輪 B14：借券賣出（張；占股本用目前股數）。sbl 不存在 = 該市場最新借券日沒有這檔
+  const SL = data.sbl;
+  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', `1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`],
+    ['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]];
 
   // E2-4：主動 ETF 持有（統一、群益投信 8 檔；沒有任何一檔持有、也沒有 act 時不顯示）
   const AC = data.active, A = data.act;
@@ -107,9 +111,10 @@
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          ['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
-         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards]
+         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards, ...slCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
+    ${SL ? `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本以目前發行股數計算。借券資料晚上 8 點半以後才更新。</div>` : ''}
     ${VAL ? `<div class="muted small val-note">一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}</div>` : ''}
     ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
     ${acHTML}
@@ -127,7 +132,7 @@
       <div id="vC" class="chart-box" style="height:80px"></div>
       <div class="ch-label">三大法人買賣超（張，未還原）<span id="iLegend" style="display:contents"></span></div>
       <div id="iC" class="chart-box" style="height:90px"></div>
-      ${data.mg ? `<div class="ch-label">融資／融券餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
+      ${data.mg ? `<div class="ch-label">融資／融券${data.mg.lb ? '／借券賣出' : ''}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
       <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
       <div class="ch-label">MACD (12, 26, 9)
         <span class="lg"><i style="background:#378ADD"></i>DIF</span><span class="lg"><i style="background:#EF9F27"></i>DEA</span></div>
@@ -183,7 +188,8 @@
   const af = adj ? adjFactors(P.d, ev) : P.d.map(() => 1);
   // F8-3：融資融券餘額；還原時乘上該日之後所有官方換算的 k（面額變更、減資），原始為官方原值
   const gk = d => adj && G?.k ? G.k.reduce((a, x) => x.d > d ? a * x.k : a, 1) : 1;
-  const mgAt = i => G ? { mb: G.mb[i] == null ? null : Math.round(G.mb[i] * gk(P.d[i])), sb: G.sb[i] == null ? null : Math.round(G.sb[i] * gk(P.d[i])) } : { mb: null, sb: null };
+  const sc = (a, i) => a?.[i] == null ? null : Math.round(a[i] * gk(P.d[i]));
+  const mgAt = i => ({ mb: sc(G?.mb, i), sb: sc(G?.sb, i), lb: sc(G?.lb, i) });   // 第 11 輪：借券（lb）同樣依官方換算
   const evAt = Object.fromEntries(ev.map(e => [e.d, e]));
   // 無成交的日子（開高低收為 --）以前一個收盤價畫一字線，時間軸保持連續；上市前的空值略過
   const rows = [];
@@ -222,7 +228,7 @@
       g.h = Math.max(g.h, r.h); g.l = Math.min(g.l, r.l); g.c = r.c; g.v += r.v; g.ev = g.ev.concat(r.ev);
       g.nt = g.nt && r.nt;   // 整週/整月都沒成交才算一字線
       for (const k of ['f', 't', 'dl', 'net']) if (r[k] != null) g[k] = (g[k] ?? 0) + r[k];
-      for (const k of ['mb', 'sb']) if (r[k] != null) g[k] = r[k];   // 融資融券：期間最後一個有值的餘額
+      for (const k of ['mb', 'sb', 'lb']) if (r[k] != null) g[k] = r[k];   // 融資融券、借券：期間最後一個有值的餘額
     }
   }
   return [...out.values()];
@@ -302,8 +308,9 @@
     }
   }
 
-  // F8-3：融資（右軸）／融券（疊加軸、不顯示刻度）餘額；第三條序列（借券賣出餘額，B14）預留
-  const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb);
+  // F8-3：融資（右軸）／融券（疊加軸、不顯示刻度）餘額；第 11 輪 B14：借券賣出（第三個疊加軸，不顯示刻度）
+  // 三條線各自一個座標軸：借券常是融券的上百倍，同軸會把融券壓平
+  const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), LB = raw.map(r => r.lb);
   let gc = null, mbSer = null;
   if (G && $('#gC')) {
     gc = mk('gC', false);
@@ -312,6 +319,11 @@
     const sbSer = gc.addLineSeries({ color: '#AE3EC9', lineWidth: 1, priceScaleId: 'sb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
     gc.priceScale('sb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
     sbSer.setData(SB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
+    if (G.lb) {
+      const lbSer = gc.addLineSeries({ color: '#E8590C', lineWidth: 1, lineStyle: 2, priceScaleId: 'lb', priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
+      gc.priceScale('lb').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
+      lbSer.setData(LB.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v }));
+    }
     // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
     mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
       .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
@@ -368,7 +380,8 @@
       $('#gLegend').innerHTML = (g !== i && MB[g] != null ? `<span class="muted">${T[g]}</span>` : '') +
         `<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">${fmt(MB[g])}</b></span>` +
         `<span class="lg"><i style="background:#AE3EC9"></i>融券 <b class="num">${fmt(SB[g])}</b></span>` +
-        `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>`;
+        `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>` +
+        (G.lb ? `<span class="lg"><i style="background:#E8590C"></i>借券 <b class="num">${fmt(LB[g])}</b></span>` : '');
     }
   };
   let crossSyncing = false;
@@ -447,7 +460,7 @@
   $('#finBox').innerHTML = `<div class="metrics">${stats.map(([l, x, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c}" style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>
     <div class="ch-label">近 ${Q.length} 季單季 EPS（元）；紅／綠 = 比去年同季增加／減少，灰 = 無法比較（去年同季虧損或沒有資料）</div>
     <div class="fin-bars">${Q.map(bar).join('')}</div>
-    <div class="muted small" style="margin-top:6px">單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}</div>`;
+    <div class="muted small" style="margin-top:6px">單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}</div>`;
 }
 
 function renderRevenue(rows) {
diff -ruN -x __pycache__ -x *.pyc orig/tests/fixtures/sbl_tpex_20261106_mini.json proj/tests/fixtures/sbl_tpex_20261106_mini.json
--- orig/tests/fixtures/sbl_tpex_20261106_mini.json	1970-01-01 08:00:00
+++ proj/tests/fixtures/sbl_tpex_20261106_mini.json	2026-11-07 00:47:21
@@ -0,0 +1,133 @@
+{
+"date": "20261106",
+"stat": "ok",
+"tables": [
+{
+"title": "信用額度總量管制餘額表",
+"date": "115/11/06",
+"totalCount": 932,
+"fields": [
+"股票代號",
+"股票名稱",
+"前日餘額",
+"賣出",
+"買進",
+"現券",
+"當日餘額",
+"限額",
+"前日餘額",
+"當日賣出",
+"當日還券",
+"當日調整數額",
+"當日餘額",
+"次一營業日可借券賣出限額",
+"備註"
+],
+"notes": [],
+"data": [
+[
+"00411A",
+"主動統一前沿科技",
+"103,000",
+"0",
+"0",
+"0",
+"103,000",
+"117,394,000",
+"1,566,000",
+"0",
+"0",
+"0",
+"1,566,000",
+"436,640",
+""
+],
+[
+"006201",
+"元大富櫃50",
+"14,000",
+"3,000",
+"14,000",
+"0",
+"3,000",
+"6,986,500",
+"561,000",
+"24,000",
+"0",
+"0",
+"585,000",
+"11,173",
+""
+],
+[
+"3064",
+"泰偉",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"XV"
+],
+[
+"3066",
+"李洲",
+"3,000",
+"3,000",
+"0",
+"0",
+"6,000",
+"19,392,653",
+"413,000",
+"0",
+"0",
+"0",
+"413,000",
+"30,238",
+""
+],
+[
+"3071",
+"協禧",
+"11,000",
+"1,000",
+"0",
+"0",
+"12,000",
+"27,500,000",
+"800,000",
+"11,000",
+"0",
+"0",
+"811,000",
+"8,059",
+""
+],
+[
+"3073",
+"天方能源",
+"0",
+"0",
+"0",
+"0",
+"0",
+"9,877,757",
+"171,000",
+"0",
+"0",
+"0",
+"171,000",
+"1,165",
+""
+]
+]
+}
+]
+}
\ No newline at end of file
diff -ruN -x __pycache__ -x *.pyc orig/tests/fixtures/sbl_tpex_20261107_holiday.json proj/tests/fixtures/sbl_tpex_20261107_holiday.json
--- orig/tests/fixtures/sbl_tpex_20261107_holiday.json	1970-01-01 08:00:00
+++ proj/tests/fixtures/sbl_tpex_20261107_holiday.json	2026-11-07 00:47:21
@@ -0,0 +1,30 @@
+{
+"date": "20261107",
+"tables": [
+{
+"title": "信用額度總量管制餘額表",
+"date": "115/11/07",
+"totalCount": 0,
+"fields": [
+"股票代號",
+"股票名稱",
+"前日餘額",
+"賣出",
+"買進",
+"現券",
+"當日餘額",
+"限額",
+"前日餘額",
+"當日賣出",
+"當日還券",
+"當日調整數額",
+"當日餘額",
+"次一營業日可借券賣出限額",
+"備註"
+],
+"data": [],
+"notes": []
+}
+],
+"stat": "ok"
+}
\ No newline at end of file
diff -ruN -x __pycache__ -x *.pyc orig/tests/fixtures/twt93u_20261106_mini.json proj/tests/fixtures/twt93u_20261106_mini.json
--- orig/tests/fixtures/twt93u_20261106_mini.json	1970-01-01 08:00:00
+++ proj/tests/fixtures/twt93u_20261106_mini.json	2026-11-07 00:47:21
@@ -0,0 +1,196 @@
+{
+"stat": "OK",
+"date": "20261106",
+"title": "115年11月06日 信用額度總量管制餘額表",
+"fields": [
+"代號",
+"名稱",
+"前日餘額",
+"賣出",
+"買進",
+"現券",
+"今日餘額",
+"次一營業日限額",
+"前日餘額",
+"當日賣出",
+"當日還券",
+"當日調整",
+"當日餘額",
+"次一營業日可限額",
+"備註"
+],
+"groups": [
+{
+"title": "股票",
+"span": 2
+},
+{
+"title": "融券",
+"span": 6
+},
+{
+"title": "借券賣出",
+"span": 6
+},
+{
+"title": "",
+"span": 1
+}
+],
+"data": [
+[
+"00400A",
+"主動國泰動能高息",
+"0",
+"0",
+"0",
+"0",
+"0",
+"586,160,000",
+"58,353,000",
+"3,015,000",
+"0",
+"0",
+"61,368,000",
+"1,354,743",
+" "
+],
+[
+"0050",
+"元大台灣50",
+"304,000",
+"202,000",
+"219,000",
+"0",
+"287,000",
+"6,199,250,000",
+"254,765,000",
+"7,030,000",
+"0",
+"0",
+"261,795,000",
+"5,318,225",
+" "
+],
+[
+"1538",
+"正峰",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"XV "
+],
+[
+"2303",
+"聯電",
+"790,000",
+"1,470,000",
+"243,000",
+"0",
+"2,017,000",
+"3,142,523,474",
+"125,092,952",
+"4,972,000",
+"1,324,000",
+"0",
+"128,740,952",
+"4,719,810",
+" "
+],
+[
+"2330",
+"台積電",
+"47,000",
+"49,000",
+"21,000",
+"0",
+"75,000",
+"6,483,092,516",
+"18,412,514",
+"1,770,000",
+"0",
+"0",
+"20,182,514",
+"973,912",
+" "
+],
+[
+"2408",
+"南亞科",
+"2,985,000",
+"0",
+"1,978,000",
+"0",
+"1,007,000",
+"774,656,973",
+"96,809,884",
+"0",
+"711,000",
+"0",
+"96,098,884",
+"1,430,681",
+" "
+],
+[
+"2887I",
+"台新新光辛特",
+"0",
+"0",
+"0",
+"0",
+"0",
+"0",
+"6,884,592",
+"0",
+"355,592",
+"0",
+"6,529,000",
+"100,262",
+"Y "
+],
+[
+"912000",
+"晨訊科-DR",
+"1,000",
+"0",
+"1,000",
+"0",
+"0",
+"39,480,879",
+"1,008,000",
+"0",
+"0",
+"0",
+"1,008,000",
+"12,364",
+" "
+],
+[
+"",
+"合計",
+"277,051,000",
+"58,327,000",
+"56,554,000",
+"36,058,000",
+"242,766,000",
+"0",
+"17,866,876,765",
+"455,143,000",
+"96,950,151",
+"0",
+"18,225,069,614",
+"0",
+" "
+]
+],
+"notes": []
+}
\ No newline at end of file
diff -ruN -x __pycache__ -x *.pyc orig/tests/fixtures/twt93u_20261107_holiday.json proj/tests/fixtures/twt93u_20261107_holiday.json
--- orig/tests/fixtures/twt93u_20261107_holiday.json	1970-01-01 08:00:00
+++ proj/tests/fixtures/twt93u_20261107_holiday.json	2026-11-07 00:47:21
@@ -0,0 +1,25 @@
+{
+"stat": "OK",
+"date": "20261107",
+"title": "115年11月07日 信用額度總量管制餘額表",
+"fields": [
+"代號",
+"名稱",
+"前日餘額",
+"賣出",
+"買進",
+"現券",
+"今日餘額",
+"次一營業日限額",
+"前日餘額",
+"當日賣出",
+"當日還券",
+"當日調整",
+"當日餘額",
+"次一營業日可限額",
+"備註"
+],
+"data": [],
+"groups": [],
+"total": 0
+}
\ No newline at end of file
diff -ruN -x __pycache__ -x *.pyc orig/tests/test_iter03.py proj/tests/test_iter03.py
--- orig/tests/test_iter03.py	2026-11-06 23:47:12
+++ proj/tests/test_iter03.py	2026-11-07 00:46:53
@@ -103,6 +103,7 @@
           "pe.TPEx": Row(888, 675, 888, 888), "insti.TWSE": Row(1077), "insti.TPEx": Row(784), "amount": Row(6), "amount.TPEx": Row(6),
           "index.TAIEX": Row(1), "index.TPEX": Row(1), "futures": Row(6), "futures_oi": Row(9),
           "etf.TWSE": Row(250), "etf.TPEx": Row(120), "margin.TWSE": Row(1100), "margin.TPEx": Row(900),   # 第 4 輪
+          "sbl.TWSE": Row(1100), "sbl.TPEx": Row(900),                                                     # 第 11 輪
           "breadth.TWSE": Row(1), "breadth.TPEx": Row(1), **{f"holdings.{c}": Row(50) for c in health.HOLDINGS}}   # 第 5 輪
     return {k: {d: v for d in days if (k, d) not in skip} for k, v in ok.items()}
 
@@ -361,7 +362,8 @@
 ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown",
           "MI_MARGN", "margin/balance", "highlight", "GetPCF",     # 第 5 輪：GetPCF 的日期是持股日
           "etf/buyback",                                            # 第 7 輪群益：和 GetPCF 共用已公布的持股日（down 才用得到）
-          "insti/summary")                                          # 第 9 輪：上櫃官方法人金額
+          "insti/summary",                                          # 第 9 輪：上櫃官方法人金額
+          "TWT93U", "margin/sbl")                                   # 第 11 輪：借券賣出（上市、上櫃）
 # 第 4 輪：行情回應含 ETF 列（另有權證、TDR 等其他證券，兩邊都不可寫入）；融資融券回應含股票與 ETF
 TWSE_ETFS = [f"00{n:03d}" for n in range(100, 350)]          # 250 檔，如 00100
 TPEX_ETFS = [f"00{n:03d}B" for n in range(700, 820)]         # 120 檔，如 00700B
@@ -417,7 +419,7 @@
                         ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                         ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi),
                         ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn), ("highlight", self._hl), ("GetPCF", self._pcf),
-                        ("etf/buyback", self._cap), ("insti/summary", self._tpex_amount)):
+                        ("etf/buyback", self._cap), ("insti/summary", self._tpex_amount), ("TWT93U", self._sbl), ("margin/sbl", self._sbl)):
             if key in url:
                 return fn(form)
         return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})
@@ -523,6 +525,21 @@
                 for c in TWSE_CODES + TWSE_ETFS + OTHERS]
         return Resp({"stat": "OK", "tables": [total, {"fields": fields, "groups": MGN_GROUPS, "data": rows}]})
 
+    def _sbl(self, form):
+        """第 11 輪：TWT93U（上市，GET date=YYYYMMDD）、margin/sbl（上櫃，POST date=YYYY/MM/DD）；尚未公布 = 回應日期仍是請求日、沒有資料列。"""
+        d = self._date(form)
+        twse = "/" not in form["date"]
+        ep = "TWT93U" if twse else "margin/sbl"
+        head = ["代號" if twse else "股票代號", "名稱", "前日餘額", "賣出", "買進", "現券", "今日餘額", "次一營業日限額", "前日餘額", "當日賣出",
+                "當日還券", "當日調整" if twse else "當日調整數額", "當日餘額", "次一營業日可限額" if twse else "次一營業日可借券賣出限額", "備註"]
+        rows = [] if self._no(ep, form) else \
+            [[c, "名", "0", "0", "0", "0", "0", "1,000", "10,000", "1,000", "0", "0", "11,000", "500", " "]
+             for c in (TWSE_CODES + TWSE_ETFS + OTHERS if twse else TPEX_CODES + TPEX_ETFS)]
+        if twse:
+            return Resp({"stat": "OK", "date": f"{d:%Y%m%d}", "fields": head, "data": rows + ([["", "合計"] + ["1"] * 13] if rows else []),
+                         "groups": [{"title": "股票", "span": 2}, {"title": "融券", "span": 6}, {"title": "借券賣出", "span": 6}, {"title": "", "span": 1}] if rows else []})
+        return Resp({"date": f"{d:%Y%m%d}", "stat": "ok", "tables": [{"fields": head, "data": rows}]})
+
     def _tpex_mgn(self, form):
         if self._no("margin/balance", form):
             return self._empty_tables(TPM_FIELDS)
@@ -581,8 +598,9 @@
                 mine = [r for r in rows if r["stock_code"].endswith("B") == (mk == "TPEx")]
                 if mine:
                     self.rows[f"etf.{mk}"][pd] = Row(len(mine))
-        elif table in ("daily_prices", "stock_fundamentals", "institutional_trades", "margin_trades"):
-            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti", "margin_trades": "margin"}[table]
+        elif table in ("daily_prices", "stock_fundamentals", "institutional_trades", "margin_trades", "sbl_trades"):
+            name = {"daily_prices": "prices", "stock_fundamentals": "pe", "institutional_trades": "insti", "margin_trades": "margin",
+                    "sbl_trades": "sbl"}[table]
             for mk in ("TWSE", "TPEx"):
                 mine = [r for r in rows if market(r["stock_code"]) == mk]
                 if mine:
diff -ruN -x __pycache__ -x *.pyc orig/tests/test_iter05.py proj/tests/test_iter05.py
--- orig/tests/test_iter05.py	2026-11-04 22:13:15
+++ proj/tests/test_iter05.py	2026-11-07 00:47:07
@@ -321,7 +321,7 @@
 
 def test_e2_cli():
     src = (ROOT / "twstock/__main__.py").read_text(encoding="utf-8")
-    assert '"margin", "holdings"]' in src and "--only holdings" in src
+    assert '"margin", "holdings", "sbl"]' in src and "--only holdings" in src          # 第 11 輪：choices 最後加 sbl
 
 
 # ─── A3：官方漲跌家數 ─────────────────────────────────────
diff -ruN -x __pycache__ -x *.pyc orig/tests/test_iter11.py proj/tests/test_iter11.py
--- orig/tests/test_iter11.py	1970-01-01 08:00:00
+++ proj/tests/test_iter11.py	2026-11-07 00:51:58
@@ -0,0 +1,240 @@
+"""
+第 11 輪純邏輯測試（不連網、不連資料庫）：
+F11-1 借券賣出：TWT93U（上市）、margin/sbl（上櫃）解析（合計列、股票／ETF 分流、日期不符＝尚未公布、休市、欄位不符）、
+      官方公式驗算、DDL、收集（行情保護、尚未公布、history --only sbl）、check 的兩行、股數寫入、匯出（張數換算、占股本、倍數、5 日、序列）；
+F11-2 latest.json 的 sbl、screen.json 的 lb、l1、l5、lp、sd、排行與選股（原始碼檢查）；
+F11-3 季報口徑說明、選股毛利率欄的季別小字（原始碼檢查）。
+fixture：tests/fixtures/twt93u_2026110{6,7}_*.json、sbl_tpex_2026110{6,7}_*.json（官方原始回應的精簡版：欄位不變，只留幾列）。數值以 2026-11-06 為準。
+
+  python3 tests/test_iter11.py      （也相容 pytest）
+"""
+import contextlib
+import copy
+import io
+import json
+import sys
+from pathlib import Path
+from unittest import mock
+
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import test_iter03 as t3  # noqa: E402
+from twstock import db, export, health  # noqa: E402
+from twstock.collectors import daily, history, industry  # noqa: E402
+from twstock.fetch import SchemaError, is_etf_code, is_valid_stock_code  # noqa: E402
+
+D, T = t3.D, t3.T
+FIX = Path(__file__).resolve().parent / "fixtures"
+ROOT = Path(__file__).resolve().parent.parent
+load = lambda name: json.loads((FIX / name).read_text(encoding="utf-8"))
+TW, OT = load("twt93u_20261106_mini.json"), load("sbl_tpex_20261106_mini.json")
+N6, N7 = D(11, 6), D(11, 7)
+
+
+# ─── F11-1：解析 ───────────────────────────────────────
+def test_f111_parse_twse():
+    rows = daily.parse_sbl(TW, N6, "TWSE")
+    by = {r["stock_code"]: r for r in rows}
+    assert "" not in by and len(rows) == 8                                         # 「合計」列略過
+    assert by["2330"] == {"stock_code": "2330", "sbl_prev": 18412514, "sbl_sell": 1770000, "sbl_return": 0, "sbl_adjust": 0,
+                          "sbl_balance": 20182514, "sbl_limit": 973912, "note": None}
+    assert by["2408"]["sbl_prev"] == 96809884 and by["2408"]["sbl_return"] == 711000 and by["2408"]["sbl_balance"] == 96098884
+    assert by["2303"]["sbl_balance"] == 128740952 and by["0050"]["sbl_balance"] == 261795000
+    assert by["00400A"]["note"] is None and by["2330"]["sbl_limit"] == 973912
+    stocks = sorted(c for c in by if is_valid_stock_code(c))
+    etfs = sorted(c for c in by if is_etf_code(c))
+    assert stocks == ["1538", "2303", "2330", "2408"] and etfs == ["00400A", "0050"]          # 2887I（特別股）、912000（TDR）都不寫
+    assert daily.sbl_mismatch(rows) == []
+
+
+def test_f111_parse_tpex():
+    rows = daily.parse_sbl(OT, N6, "TPEx")
+    by = {r["stock_code"]: r for r in rows}
+    assert sorted(by) == ["00411A", "006201", "3064", "3066", "3071", "3073"]
+    assert by["00411A"]["sbl_balance"] == 1566000 and by["006201"] == {
+        "stock_code": "006201", "sbl_prev": 561000, "sbl_sell": 24000, "sbl_return": 0, "sbl_adjust": 0,
+        "sbl_balance": 585000, "sbl_limit": 11173, "note": None}
+    assert daily.sbl_mismatch(rows) == []
+
+
+def test_f111_not_published_and_schema():
+    assert daily.parse_sbl(TW, N7, "TWSE") == [] and daily.parse_sbl(OT, N7, "TPEx") == []          # 回應日期不是 d（前一個交易日的資料）
+    assert daily.parse_sbl(load("twt93u_20261107_holiday.json"), N7, "TWSE") == []                  # 休市：日期相同、沒有資料列
+    assert daily.parse_sbl(load("sbl_tpex_20261107_holiday.json"), N7, "TPEx") == []
+    assert daily.parse_sbl({**TW, "stat": "很抱歉，沒有符合條件的資料!"}, N6, "TWSE") == []
+    bad = copy.deepcopy(TW)
+    bad["fields"][12] = "今日餘額"
+    try:
+        daily.parse_sbl(bad, N6, "TWSE")
+        raise AssertionError("欄位不符要丟例外")
+    except SchemaError as e:
+        assert "12:當日餘額" in str(e)
+    bad = copy.deepcopy(TW)
+    bad["groups"][2]["title"] = "借券"
+    try:
+        daily.parse_sbl(bad, N6, "TWSE")
+        raise AssertionError("groups 不符要丟例外")
+    except SchemaError:
+        pass
+    bad = copy.deepcopy(OT)
+    bad["tables"][0]["fields"][11] = "當日調整"
+    try:
+        daily.parse_sbl(bad, N6, "TPEx")
+        raise AssertionError("上櫃欄位不符要丟例外")
+    except SchemaError:
+        pass
+    rows = daily.parse_sbl(TW, N6, "TWSE")
+    rows[0]["sbl_balance"] += 1
+    assert daily.sbl_mismatch(rows) == [rows[0]["stock_code"]]
+
+
+def test_f111_ddl_and_keys():
+    src = (ROOT / "twstock" / "db.py").read_text(encoding="utf-8")
+    for t in ("sbl_trades", "etf_sbl"):
+        assert f"IF OBJECT_ID('{t}') IS NULL" in src and f"CONSTRAINT UQ_{t} UNIQUE" in src
+    assert "IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL" in src
+    assert "sbl_limit    BIGINT" in src                                                                   # 單檔餘額最大約 7.9 億股（3481），留餘裕
+    assert daily.DATASET_KEYS["sbl"] == ("sbl.TWSE", "sbl.TPEx") and "sbl" not in daily.ALL_DATASETS       # 只有 --only sbl 才補
+    k = list(daily.DAY_KEYS)
+    assert k.index("margin.TPEx") < k.index("sbl.TWSE") < k.index("sbl.TPEx") < k.index("breadth.TWSE")
+    assert health.SPEC["sbl.TWSE"].min_rows == 800 and health.SPEC["sbl.TPEx"].min_rows == 550
+    assert set(history.SECONDS_PER_KEY) >= {"sbl.TWSE", "sbl.TPEx"}
+    main = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")
+    assert '"holdings", "sbl"]' in main and "--only sbl" in main and "sbl = 借券賣出" in main
+
+
+# ─── F11-1：收集 ───────────────────────────────────────
+def test_f111_collect():
+    w = t3.World(D(10, 30))
+    w.publish(D(11, 2))
+    with t3.env(w), contextlib.redirect_stdout(io.StringIO()):
+        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "etf.TWSE", "etf.TPEx", "sbl.TWSE", "sbl.TPEx"))
+    assert errors == {} and written["sbl.TWSE"] == 1100 and written["sbl.TPEx"] == 900
+    assert w.rows["sbl.TWSE"][D(11, 2)].n == 1100 and w.merges.count("sbl_trades") == 2 and w.merges.count("etf_sbl") == 2
+    assert len(t3._hit(w, "TWT93U")) == 1 and len(t3._hit(w, "margin/sbl")) == 1
+    # 行情 0 列（尚未公布）→ 不發借券請求；借券尚未公布（日期相同、沒有資料列）→ 0 筆、不是錯誤
+    w2 = t3.World(D(10, 30))
+    w2.publish(D(11, 2), "MI_INDEX", "TWT93U")
+    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
+        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "prices.TPEx", "sbl.TWSE", "sbl.TPEx"))
+    assert written["prices.TWSE"] == 0 and "sbl.TWSE" not in written and t3._hit(w2, "TWT93U") == []
+    w2.published["margin/sbl"].discard(D(11, 2))
+    with t3.env(w2), contextlib.redirect_stdout(io.StringIO()):
+        written, errors = daily.collect_for_date(D(11, 2), ("prices.TPEx", "sbl.TPEx"))
+    assert errors == {} and written["sbl.TPEx"] == 0
+
+
+def test_f111_before_2030():
+    """20:30 前：官方仍回應前一個交易日（日期不符）→ 0 筆、不寫入、不算失敗；之後再抓。"""
+    w = t3.World(D(10, 30))
+    w.publish(D(11, 2))
+    real = w.http
+
+    def stale(method, url, **kw):
+        r = real(method, url, **kw)
+        if "TWT93U" in url and r.data:
+            r.data = {**r.data, "date": "20261030"}
+        return r
+    with t3.env(w), mock.patch.object(t3.fetch._SESSION, "request", stale), \
+            contextlib.redirect_stdout(io.StringIO()):
+        written, errors = daily.collect_for_date(D(11, 2), ("prices.TWSE", "sbl.TWSE"))
+    assert errors == {} and written["sbl.TWSE"] == 0 and D(11, 2) not in w.rows["sbl.TWSE"]
+
+
+def test_f111_catchup_and_history():
+    # catch-up：新的一天，22:00 前借券沒有 → 尚未公布（不是異常）；22:00 後仍沒有 → 異常
+    w = t3.World(D(10, 30))
+    w.publish(t3.FIRST_DAY, "TWT93U")
+    rc, out = t3.run_world(w, T(11, 2, 21, 0))
+    assert rc == 0 and "上市借券：2026-11-02 尚未公布" in out and t3.FIRST_DAY not in w.rows["sbl.TWSE"]
+    assert w.rows["sbl.TPEx"][t3.FIRST_DAY].n == 900
+    w.published["TWT93U"].add(t3.FIRST_DAY)
+    w.requests.clear()
+    rc, out = t3.run_world(w, T(11, 2, 22, 40))
+    assert rc == 0 and [p for p in w.paths()] == ["/rwd/zh/marginTrading/TWT93U"] and w.rows["sbl.TWSE"][t3.FIRST_DAY].n == 1100
+    # history --only sbl：只抓缺的日期、不抓行情
+    w3 = t3.World(D(10, 30))
+    for d in (D(10, 28), D(10, 29), D(10, 30)):
+        w3.rows["sbl.TWSE"].pop(d)
+        w3.rows["sbl.TPEx"].pop(d)
+        w3.publish(d)
+    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
+        assert history.run_history(D(10, 27), D(10, 30), datasets=("sbl",), revenue=False)
+    assert len(t3._hit(w3, "TWT93U")) == 3 and len(t3._hit(w3, "margin/sbl")) == 3 and t3._hit(w3, "MI_INDEX", "dailyQuotes") == []
+    w3.requests.clear()
+    with t3.env(w3), contextlib.redirect_stdout(io.StringIO()):
+        assert history.run_history(D(10, 27), D(10, 30), datasets=("sbl",), revenue=False)
+    assert w3.requests == []                                                                       # 重跑 0 次請求
+
+
+def test_f111_shares():
+    L = [{"公司代號": "2330", "產業別": "24", "已發行普通股數或TDR原股發行股數": "25932370067"},
+         {"公司代號": "2408", "產業別": "24", "已發行普通股數或TDR原股發行股數": "3450205894"},
+         {"公司代號": "9999", "產業別": "24", "已發行普通股數或TDR原股發行股數": ""}]
+    O = [{"SecuritiesCompanyCode": "6488", "SecuritiesIndustryCode": "24", "IssueShares": "186,000,000"}]
+    seen = {}
+
+    class Cur:
+        rowcount = 3
+
+        def execute(self, sql, *p):
+            seen["sql"], seen["rows"] = sql, json.loads(p[0])
+
+    class Conn:
+        cursor = lambda self: Cur()
+        commit = close = lambda self: None
+    with mock.patch.object(industry, "request", side_effect=[L, O]), mock.patch.object(db, "connect", lambda: Conn()), \
+            contextlib.redirect_stdout(io.StringIO()):
+        industry.update_industry()
+    by = {r["stock_code"]: r for r in seen["rows"]}
+    assert by["2330"]["shares"] == 25932370067 and by["2408"]["shares"] == 3450205894 and by["6488"]["shares"] == 186000000
+    assert by["9999"]["shares"] is None and "ISNULL(j.shares, st.shares)" in seen["sql"]           # 空值不蓋掉既有股數
+
+
+# ─── F11-1、F11-2：匯出 ───────────────────────────────────
+def test_f112_export_calc():
+    assert [export.lots(x) for x in (20182514, 1770000, -711000, 499, 500, -500, -1500, None)] == \
+        [20183, 1770, -711, 0, 1, -1, -2, None]
+    d1, d5, d6 = D(10, 30), D(10, 31), N6
+    rows = {d1: (17000000, 17500000, 0, None), d6: (18412514, 20182514, 973912, None)}
+    r = export.stock_sbl(rows, d6, d1, 25932370067, 75)
+    assert r == {"d": "2026-11-06", "lb": 20183, "l1": 1770, "l5": 2683, "lp": 0.08, "lx": 269.1}
+    r = export.stock_sbl({d6: (96809884, 96098884, 1430681, "X")}, d6, None, None, 0)
+    assert r == {"d": "2026-11-06", "lb": 96099, "l1": -711, "l5": None, "nt": "X"}             # 沒有股數 → 沒有 lp；融券 0 → 沒有 lx
+    assert export.stock_sbl(rows, d5, None, 1, 1) is None                                       # 該市場最新借券日沒有這檔
+    conv = [{"d": "2026-11-06", "k": 0.5, "t": "面"}]                                           # 面額變更：5 日前餘額 × 0.5
+    assert export.stock_sbl(rows, d6, d1, None, None, conv)["l5"] == export.lots(20182514 - 17500000 * 0.5)
+    m = export.market_sbl([d1, d6], {d6: [(18412514, 20182514), (96809884, 96098884)]})
+    assert m == {"d": "2026-11-06", "lb": 116281, "l1": 1059, "n": 2}
+    mg = export.margin_series([d1, d5, d6], {d1: (0, 10, 0, 0, 1, None)}, [], rows)
+    assert mg == {"mb": [10, None, None], "sb": [1, None, None], "lb": [17500, None, 20183]}
+    assert "lb" not in export.margin_series([d1], {d1: (0, 10, 0, 0, 1, None)}, [], {})
+    assert export.margin_series([d1], {}, [], rows) is None                                     # 沒有融資融券：不畫圖
+    assert set(export.SCREEN_KEYS) >= {"lb", "l1", "l5", "lp"}
+
+
+def test_f112_export_source():
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert '"sd": {m: str(d) for m, d in slast.items()}' in src and '**({"sbl": sbl} if sbl else {})' in src
+    assert '"sbl": {m: market_sbl(sdates[m], srecent[m]) for m in ("TWSE", "TPEx") if sdates.get(m)} or None' in src
+
+
+# ─── 網站（原始碼檢查）───────────────────────────────────
+def test_f11_site():
+    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+    assert "不等於看空" in js and "priceScaleId: 'lb'" in js and "for (const k of ['mb', 'sb', 'lb'])" in js
+    assert "官方本益比以最新股數計算，期間有增資的公司" in js                                            # F11-3 第 1 點
+    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+    assert "['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l']" in app
+    assert "{ id: 'lp', g: '信用'" in app and "{ id: 'l5', g: '信用'" in app and "function sblLine(L)" in app
+    assert "gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)]" in app                  # F11-3 第 2 點
+    assert "gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)]" in app
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
diff -ruN -x __pycache__ -x *.pyc orig/twstock/__main__.py proj/twstock/__main__.py
--- orig/twstock/__main__.py	2026-11-06 23:47:12
+++ proj/twstock/__main__.py	2026-11-07 00:44:38
@@ -11,6 +11,7 @@
   python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
   python -m twstock history --start 2026-07-31 --only amount  只補三大法人買賣金額（上市、上櫃；已有的市場自動略過）
   python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
+  python -m twstock history --start 2025-10-30 --only sbl         只補借券賣出（上市、上櫃各 1 個請求／天；晚上 8 點半後才有當天資料）
   python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過）
   python -m twstock history --start 2024-01-01 --only financials  只補季報（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
@@ -194,9 +195,9 @@
     s = sub.add_parser("history", help="補抓歷史資料")
     s.add_argument("--start", type=_date, required=True)
     s.add_argument("--end", type=_date, help="預設今天")
-    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "financials", "etf", "margin", "holdings"],
+    s.add_argument("--only", nargs="+", choices=["prices", "pe", "insti", "index", "amount", "tpex_index", "financials", "etf", "margin", "holdings", "sbl"],
                    help="只抓指定資料集（pe = 本益比／淨值比／殖利率，index = 加權指數，tpex_index = 櫃買指數，"
-                        "amount = 上市、上櫃三大法人買賣金額，etf = ETF 行情，margin = 融資融券，holdings = 主動型 ETF 持股，"
+                        "amount = 上市、上櫃三大法人買賣金額，etf = ETF 行情，margin = 融資融券，sbl = 借券賣出，holdings = 主動型 ETF 持股，"
                         "financials = 季報（季底日在 --start～--end 的季別））；"
                         "預設 prices pe insti etf margin")
     s.add_argument("--force", action="store_true", help="已存在的日期也重抓覆寫")
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/daily.py proj/twstock/collectors/daily.py
--- orig/twstock/collectors/daily.py	2026-11-06 23:46:58
+++ proj/twstock/collectors/daily.py	2026-11-07 00:44:19
@@ -1,5 +1,5 @@
 """
-每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券、官方漲跌家數、主動 ETF 持股。
+每日資料：上市 + 上櫃的收盤行情、本益比/殖利率、三大法人買賣超、ETF 行情、融資融券、借券賣出、官方漲跌家數、主動 ETF 持股。
 
 寫入採批次：整批資料序列化成一個 JSON 參數，由 OPENJSON 展開後 MERGE；
 每張表一次資料庫往返，取代逐筆查詢/更新的上萬次往返。
@@ -18,17 +18,18 @@
 
 # history --only 的資料集名稱；INDEX = 加權指數（抓行情時會一併寫入），TPEX_INDEX = 櫃買指數（月查詢）
 PRICES, PE, INSTI, INDEX, AMOUNT, TPEX_INDEX = "prices", "pe", "insti", "index", "amount", "tpex_index"
-ETF, MARGIN, HOLDINGS_DS = "etf", "margin", "holdings"
+ETF, MARGIN, HOLDINGS_DS, SBL = "etf", "margin", "holdings", "sbl"
 ALL_DATASETS = (PRICES, PE, INSTI, ETF, MARGIN)
 HOLDINGS_KEYS = tuple(f"holdings.{c}" for c in HOLDINGS)
 # 每個資料集對應的細項（分市場），也是 collect_for_date 與 health.SPECS 共用的鍵
 DATASET_KEYS = {PRICES: ("prices.TWSE", "prices.TPEx"), PE: ("pe.TWSE", "pe.TPEx"),
                 INSTI: ("insti.TWSE", "insti.TPEx"), INDEX: ("index.TAIEX",), AMOUNT: ("amount", "amount.TPEx"),
-                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx"), HOLDINGS_DS: HOLDINGS_KEYS}
-# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券與持股（兩者都只寫入 etfs 已有的 ETF）
+                ETF: ("etf.TWSE", "etf.TPEx"), MARGIN: ("margin.TWSE", "margin.TPEx"), HOLDINGS_DS: HOLDINGS_KEYS,
+                SBL: ("sbl.TWSE", "sbl.TPEx")}
+# 一天之內的收集順序：行情先於本益比、法人；ETF 行情先於融資融券、借券與持股（都只寫入 etfs 已有的 ETF）
 # 漲跌家數不補歷史（health.BREADTH_FROM），所以不在 DATASET_KEYS；上市家數與行情共用同一個 MI_INDEX 回應
 DAY_KEYS = ("prices.TWSE", "prices.TPEx", "index.TAIEX", "etf.TWSE", "etf.TPEx", "pe.TWSE", "pe.TPEx",
-            "insti.TWSE", "insti.TPEx", "amount", "amount.TPEx", "margin.TWSE", "margin.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
+            "insti.TWSE", "insti.TPEx", "amount", "amount.TPEx", "margin.TWSE", "margin.TPEx", "sbl.TWSE", "sbl.TPEx", "breadth.TWSE", "breadth.TPEx") + HOLDINGS_KEYS
 PARSE_ERRORS = (SchemaError, KeyError, IndexError, TypeError, ValueError, AttributeError)
 
 
@@ -407,6 +408,58 @@
     return parse_tpex_margin(request("POST", f"{TPEX}/margin/balance", data={"date": f"{d:%Y/%m/%d}", "response": "json"}))
 
 
+# ─── 借券賣出（第 11 輪 B14；上市 TWT93U、上櫃 margin/sbl；股；股票、ETF、其他證券同一個回應）──
+# 兩個回應都是「融券 6 欄＋借券賣出 6 欄」，欄名重複，依位置取值；位置 → 欄名（用來驗證沒有改版）。只存借券賣出那 6 欄
+SBL_COLS = ("sbl_prev", "sbl_sell", "sbl_return", "sbl_adjust", "sbl_balance", "sbl_limit")
+SBL_POS = {"TWSE": {0: "代號", 8: "前日餘額", 9: "當日賣出", 10: "當日還券", 11: "當日調整", 12: "當日餘額", 13: "次一營業日可限額", 14: "備註"},
+           "TPEx": {0: "股票代號", 8: "前日餘額", 9: "當日賣出", 10: "當日還券", 11: "當日調整數額", 12: "當日餘額",
+                    13: "次一營業日可借券賣出限額", 14: "備註"}}
+TWSE_SBL_GROUPS = [("股票", 2), ("融券", 6), ("借券賣出", 6)]
+
+
+def parse_sbl(data: dict, d: date, market: str) -> list:
+    """
+    TWT93U（上市）／margin/sbl（上櫃）→ [{stock_code, sbl_prev…sbl_limit（股）, note}]，含股票、ETF、其他證券，由呼叫端分流。
+    回應日期不是 d（20:30 第一次更新前可能還是前一個交易日）、stat 不是 OK、沒有資料列 → []（尚未公布，不算失敗）。
+    欄位（上市另驗 groups）不符 → SchemaError。上市最後一列「合計」（代號空白）不是個股，略過。
+    """
+    if str(data.get("stat", "")).upper() != "OK" or str(data.get("date")) != f"{d:%Y%m%d}":
+        return []
+    t = data if market == "TWSE" else next(iter(data.get("tables") or []), {})
+    if not t.get("data"):
+        return []
+    fields, pos = t.get("fields") or [], SBL_POS[market]
+    bad = [f"{i}:{name}" for i, name in pos.items() if i >= len(fields) or fields[i] != name]
+    groups = [(g.get("title"), g.get("span")) for g in t.get("groups") or []][:3] if market == "TWSE" else None
+    if bad or (market == "TWSE" and groups != TWSE_SBL_GROUPS):
+        raise SchemaError(f"借券賣出（{market}）欄位不符：groups {groups}，位置 {'、'.join(bad) or '正常'}")
+    rows = []
+    for r in t["data"]:
+        code = str(r[0]).strip() if r else ""
+        if len(r) < 15 or not code:
+            continue                                    # 合計列、短列
+        row = {"stock_code": code, **{c: clean_number(r[8 + i], int) for i, c in enumerate(SBL_COLS)},
+               "note": str(r[14] or "").strip()[:20] or None}
+        if row["sbl_prev"] is not None and row["sbl_balance"] is not None:
+            rows.append(row)
+    return rows
+
+
+def sbl_mismatch(rows: list) -> list:
+    """「前日餘額 + 當日賣出 − 當日還券 + 當日調整 ≠ 當日餘額」的代號（官方公式；只印警告，照存）。"""
+    v = lambda r, c: r[c] or 0
+    return [r["stock_code"] for r in rows
+            if r["sbl_prev"] + v(r, "sbl_sell") - v(r, "sbl_return") + v(r, "sbl_adjust") != r["sbl_balance"]]
+
+
+def fetch_sbl(d: date, market: str) -> list:
+    if market == "TWSE":
+        data = request("GET", f"{TWSE}/marginTrading/TWT93U", params={"date": f"{d:%Y%m%d}", "response": "json"})
+    else:
+        data = request("POST", f"{TPEX}/margin/sbl", data={"date": f"{d:%Y/%m/%d}", "response": "json"})
+    return parse_sbl(data, d, market)
+
+
 # ─── 批次寫入 ─────────────────────────────────────────────
 def merge_stocks(cursor, rows: list, trade_date: date):
     """
@@ -573,6 +626,31 @@
     """, db.to_json(rows), trade_date, trade_date)
 
 
+_SBL_TABLE = {"stock": ("sbl_trades", "stocks", "stock_id", "stock_code"), "etf": ("etf_sbl", "etfs", "etf_id", "etf_code")}
+
+
+def merge_sbl(cursor, trade_date, rows: list, kind: str):
+    """借券賣出個股表：股票寫 sbl_trades（只寫 stocks 已有的），ETF 寫 etf_sbl（只寫 etfs 已有的）；同一天重抓 = 覆寫。"""
+    table, ref, key, code = _SBL_TABLE[kind]
+    cursor.execute(f"""
+        MERGE {table} AS t
+        USING (
+            SELECT r.{key}, j.*
+            FROM OPENJSON(?) WITH (
+                stock_code NVARCHAR(10), sbl_prev BIGINT, sbl_sell BIGINT, sbl_return BIGINT, sbl_adjust BIGINT,
+                sbl_balance BIGINT, sbl_limit BIGINT, note NVARCHAR(20)
+            ) AS j
+            JOIN {ref} r ON r.{code} = j.stock_code
+        ) AS s
+        ON t.{key} = s.{key} AND t.trade_date = ?
+        WHEN MATCHED THEN UPDATE SET
+            {", ".join(f"{c} = s.{c}" for c in SBL_COLS)}, note = s.note
+        WHEN NOT MATCHED THEN
+            INSERT ({key}, trade_date, {", ".join(SBL_COLS)}, note)
+            VALUES (s.{key}, ?, {", ".join(f"s.{c}" for c in SBL_COLS)}, s.note);
+    """, db.to_json(rows), trade_date, trade_date)
+
+
 def merge_margin_market(cursor, trade_date, market: str, total: dict):
     cursor.execute("""
         MERGE margin_market AS t
@@ -827,6 +905,17 @@
         _save(lambda cur: (merge_margin(cur, d, stocks, "stock"), etfs and merge_margin(cur, d, etfs, "etf"),
                            merge_margin_market(cur, d, market, total)))
         return len(stocks)
+    if dataset == SBL:
+        rows = fetch_sbl(d, market)
+        stocks = [r for r in rows if is_valid_stock_code(r["stock_code"])]
+        etfs = [r for r in rows if is_etf_code(r["stock_code"])]
+        if not stocks:
+            return 0                                    # 尚未公布（日期不符或沒有資料列）
+        bad = sbl_mismatch(stocks + etfs)
+        if bad:
+            print(f"  ⚠️  {key} 有 {len(bad)} 檔不符「前日 + 賣出 − 還券 + 調整 = 餘額」（照存）：{'、'.join(bad[:5])}")
+        _save(lambda cur: (merge_sbl(cur, d, stocks, "stock"), etfs and merge_sbl(cur, d, etfs, "etf")))
+        return len(stocks)
     amount = (fetch_tpex_insti_amount if market == "TPEx" else fetch_twse_insti_amount)(d)    # "amount" = 上市、"amount.TPEx" = 上櫃
     if amount:
         _save(merge_insti_amount, amount)
@@ -844,8 +933,8 @@
     for key in keys:
         dataset, _, market = key.partition(".")
         # "amount"（上市法人金額）partition 後市場是空字串：視為 TWSE（第 10 輪 P24；鍵名不改）
-        if dataset in ("pe", "insti", MARGIN, "breadth", AMOUNT) and written.get(f"prices.{market or 'TWSE'}") == 0:
-            continue                # 同市場行情還沒有：本益比、法人、融資融券、漲跌家數、法人金額不可能先有，不發請求
+        if dataset in ("pe", "insti", MARGIN, SBL, "breadth", AMOUNT) and written.get(f"prices.{market or 'TWSE'}") == 0:
+            continue                # 同市場行情還沒有：本益比、法人、融資融券、借券、漲跌家數、法人金額不可能先有，不發請求
         if dataset == "pe" and f"prices.{market}" in errors:
             continue                # 本益比只寫入有行情列的股票
         try:
@@ -865,4 +954,4 @@
     return written, errors
 
 
-__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "HOLDINGS_DS", "ALL_DATASETS"]
+__all__ = ["collect_for_date", "FetchError", "PRICES", "PE", "INSTI", "ETF", "MARGIN", "HOLDINGS_DS", "SBL", "ALL_DATASETS"]
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/history.py proj/twstock/collectors/history.py
--- orig/twstock/collectors/history.py	2026-11-06 23:47:12
+++ proj/twstock/collectors/history.py	2026-11-07 00:44:29
@@ -23,6 +23,7 @@
 # 依網站節流間隔 + 回應時間的實測值（秒，每個細項）
 SECONDS_PER_KEY = {"prices.TWSE": 4, "prices.TPEx": 4, "pe.TWSE": 4, "pe.TPEx": 3.2, "insti.TWSE": 4, "insti.TPEx": 3.2,
                    "index.TAIEX": 4, "amount": 4, "amount.TPEx": 3.2, "etf.TWSE": 4, "etf.TPEx": 1, "margin.TWSE": 4, "margin.TPEx": 0.5,
+                   "sbl.TWSE": 4, "sbl.TPEx": 3.2,
                    **{k: 3.2 for k in HOLDINGS_KEYS}}
 SHARED = {"etf.TWSE": "prices.TWSE", "etf.TPEx": "prices.TPEx"}   # 同一天也要抓行情時共用回應，不另計時
 SECONDS_PER_MONTH = 3.2
diff -ruN -x __pycache__ -x *.pyc orig/twstock/collectors/industry.py proj/twstock/collectors/industry.py
--- orig/twstock/collectors/industry.py	2026-10-29 22:53:10
+++ proj/twstock/collectors/industry.py	2026-11-07 00:45:15
@@ -1,6 +1,6 @@
-"""更新 stocks.industry：證交所 / 櫃買 OpenAPI 公司基本資料的產業別代碼 → 中文名稱。"""
+"""更新 stocks.industry 與 stocks.shares：證交所 / 櫃買 OpenAPI 公司基本資料的產業別代碼 → 中文名稱、發行股數（第 11 輪）。"""
 from .. import db
-from ..fetch import request
+from ..fetch import clean_number, request
 
 INDUSTRY = {
     "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維", "05": "電機機械",
@@ -15,25 +15,27 @@
 
 
 def update_industry() -> int:
+    """產業別與發行股數（第 11 輪，借券占股本用；目前股數，不保留歷史）一起更新；只更新有變動的列。"""
     twse = request("GET", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
     tpex = request("GET", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O")
-    pairs = [(r["公司代號"], r["產業別"]) for r in twse] + \
-            [(r["SecuritiesCompanyCode"], r["SecuritiesIndustryCode"]) for r in tpex]
-    rows = [{"stock_code": c.strip(), "industry": INDUSTRY.get(i.strip(), "其他")} for c, i in pairs]
+    triples = [(r["公司代號"], r["產業別"], r.get("已發行普通股數或TDR原股發行股數")) for r in twse] + \
+              [(r["SecuritiesCompanyCode"], r["SecuritiesIndustryCode"], r.get("IssueShares")) for r in tpex]
+    rows = [{"stock_code": c.strip(), "industry": INDUSTRY.get(i.strip(), "其他"), "shares": clean_number(n, int) or None}
+            for c, i, n in triples]
 
     conn = db.connect()
     try:
         cursor = conn.cursor()
         cursor.execute("""
-            UPDATE st SET industry = j.industry
+            UPDATE st SET industry = j.industry, shares = ISNULL(j.shares, st.shares)
             FROM stocks st
-            JOIN OPENJSON(?) WITH (stock_code NVARCHAR(10), industry NVARCHAR(50)) AS j
+            JOIN OPENJSON(?) WITH (stock_code NVARCHAR(10), industry NVARCHAR(50), shares BIGINT) AS j
               ON j.stock_code = st.stock_code
-            WHERE ISNULL(st.industry, '') <> j.industry
+            WHERE ISNULL(st.industry, '') <> j.industry OR (j.shares IS NOT NULL AND ISNULL(st.shares, -1) <> j.shares)
         """, db.to_json(rows))
         changed = cursor.rowcount
         conn.commit()
     finally:
         conn.close()
-    print(f"  🏷️  產業別：更新 {changed} 檔")
+    print(f"  🏷️  產業別、股數：更新 {changed} 檔")
     return changed
diff -ruN -x __pycache__ -x *.pyc orig/twstock/db.py proj/twstock/db.py
--- orig/twstock/db.py	2026-11-06 23:47:12
+++ proj/twstock/db.py	2026-11-07 00:51:58
@@ -470,6 +470,44 @@
         CONSTRAINT UQ_quarterly_financials UNIQUE (stock_id, fin_year, fin_quarter)
     )
     """,
+    # 借券賣出（第 11 輪 B14；股，和融資融券的張不同）：上市 TWT93U、上櫃 margin/sbl 的「借券賣出」6 欄＋備註原文；
+    # 股票 sbl_trades、ETF etf_sbl 欄位相同（比照 margin_trades／etf_margin）。單檔最大 3481 約 7.9 億股（11/06，INT 上限的 37%），一律 BIGINT 留餘裕
+    """
+    IF OBJECT_ID('sbl_trades') IS NULL
+    CREATE TABLE sbl_trades (
+        id           BIGINT IDENTITY(1,1) PRIMARY KEY,
+        stock_id     INT           NOT NULL REFERENCES stocks(stock_id),
+        trade_date   DATE          NOT NULL,
+        sbl_prev     BIGINT        NOT NULL,   -- 前日餘額
+        sbl_sell     BIGINT        NULL,       -- 當日賣出
+        sbl_return   BIGINT        NULL,       -- 當日還券
+        sbl_adjust   BIGINT        NULL,       -- 當日調整
+        sbl_balance  BIGINT        NOT NULL,   -- 當日餘額
+        sbl_limit    BIGINT        NULL,       -- 次一營業日可借券賣出限額
+        note         NVARCHAR(20)  NULL,       -- 備註原文（X 停券、V 不得借券交易…）
+        created_at   DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_sbl_trades UNIQUE (stock_id, trade_date)
+    )
+    """,
+    """
+    IF OBJECT_ID('etf_sbl') IS NULL
+    CREATE TABLE etf_sbl (
+        id           BIGINT IDENTITY(1,1) PRIMARY KEY,
+        etf_id       INT           NOT NULL REFERENCES etfs(etf_id),
+        trade_date   DATE          NOT NULL,
+        sbl_prev     BIGINT        NOT NULL,
+        sbl_sell     BIGINT        NULL,
+        sbl_return   BIGINT        NULL,
+        sbl_adjust   BIGINT        NULL,
+        sbl_balance  BIGINT        NOT NULL,
+        sbl_limit    BIGINT        NULL,
+        note         NVARCHAR(20)  NULL,
+        created_at   DATETIME      NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_sbl UNIQUE (etf_id, trade_date)
+    )
+    """,
+    # 第 11 輪：發行股數（update_industry 一併寫入；目前股數，不保留歷史）
+    "IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL",
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -483,6 +521,8 @@
     "CREATE INDEX IX_industry_chains_code ON industry_chains(stock_code)",
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_margin_trades_date') "
     "CREATE INDEX IX_margin_trades_date ON margin_trades(trade_date)",
+    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_sbl_trades_date') "
+    "CREATE INDEX IX_sbl_trades_date ON sbl_trades(trade_date)",
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_daily_date') "
     "CREATE INDEX IX_etf_daily_date ON etf_daily(trade_date)",
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_etf_holdings_code') "
@@ -508,4 +548,4 @@
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
           "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
           "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、quarterly_financials、"
-          "etf_holding_gaps")
+          "sbl_trades、etf_sbl（第 11 輪另加 stocks.shares）、etf_holding_gaps")
diff -ruN -x __pycache__ -x *.pyc orig/twstock/export.py proj/twstock/export.py
--- orig/twstock/export.py	2026-11-07 00:13:13
+++ proj/twstock/export.py	2026-11-07 00:45:24
@@ -46,7 +46,7 @@
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
-               "eq", "ey", "e4", "gm", "gmy", "fq", "eh")
+               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp")
 VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
 VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
 VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
@@ -388,16 +388,71 @@
             "sr": r["sr"], "mu": r["mu"], "mnt": (r.get("nt") or None) if market == "TWSE" else None}
 
 
-def margin_series(d_, rows, conv):
-    """個股 JSON 的 mg：與 prices.d 對齊的官方原始餘額（張），沒有資料的日期 null；k = 換算紀錄（沒有就不放）。該股沒有任何融資融券列 → None。"""
+def margin_series(d_, rows, conv, srows=None):
+    """
+    個股 JSON 的 mg：與 prices.d 對齊的官方原始餘額（張），沒有資料的日期 null；k = 換算紀錄（沒有就不放）。該股沒有任何融資融券列 → None。
+    第 11 輪 B14：srows（借券 {日期: (前日, 餘額, 限額, 備註)}，股）有資料時加 lb = 借券賣出餘額（張）；只有借券、沒有融資融券的股票不畫圖。
+    """
     if not rows:
         return None
     mg = {"mb": [rows[d][1] if d in rows else None for d in d_], "sb": [rows[d][4] if d in rows else None for d in d_]}
+    if srows:
+        mg["lb"] = [lots(srows[d][1]) if d in srows else None for d in d_]
     if conv:
         mg["k"] = conv
     return mg
 
 
+# ─── 借券賣出（第 11 輪 B14；資料庫存股，匯出一律換成張）────────────
+def lots(shares):
+    """股 → 張（四捨五入到整數，half-up；None 照傳）。"""
+    return None if shares is None else int((shares + 500) // 1000) if shares >= 0 else -int((-shares + 500) // 1000)
+
+
+def stock_sbl(rows: dict, sdate, d5, shares, short_lots, conv=()):
+    """
+    個股 JSON 的 sbl。rows：{日期: (前日餘額, 當日餘額, 限額, 備註)}（股）；sdate：該市場最新借券日；d5：往前第 5 個借券日。
+    該股當天沒有列 → None。lb 餘額、l1／l5 增減（張；5 日前餘額依融資融券的官方換算 k 調整）；
+    lp 占股本 %（2 位；shares 為 None 或 0 不輸出）；lx = 借券 ÷ 融券（1 位；融券 0 或沒有不輸出）。
+    """
+    r = rows.get(sdate) if sdate else None
+    if r is None:
+        return None
+    prev, bal, _, nt = r
+    old = rows.get(d5) if d5 else None
+    out = {"d": str(sdate), "lb": lots(bal), "l1": lots(bal - prev),
+           "l5": lots(bal - old[1] * conv_k(conv, d5)) if old else None}
+    if shares:
+        out["lp"] = round(bal / shares * 100, 2)
+    if short_lots:
+        out["lx"] = round(bal / (short_lots * 1000), 1)
+    if nt:
+        out["nt"] = nt
+    return out
+
+
+def market_sbl(sdates, rows_by_market):
+    """latest.json 的 sbl.{市場}：股票（不含 ETF）借券賣出餘額合計與 1 日增減（張）。rows_by_market：{日期: [(前日, 餘額)]}。"""
+    if not sdates:
+        return None
+    d = sdates[-1]
+    R = rows_by_market.get(d, [])
+    bal, prev = sum(r[1] for r in R), sum(r[0] for r in R)
+    return {"d": str(d), "lb": lots(bal), "l1": lots(bal - prev), "n": len(R)}
+
+
+def _load_sbl(cur):
+    """(各市場借券日期（舊到新，最近 6 天）, 各市場最新日的 [(前日, 餘額)], 個股 {代號: {日期: (前日, 餘額, 限額, 備註)}}（完整歷史）)。"""
+    per_stock, by_m = defaultdict(dict), defaultdict(lambda: defaultdict(list))
+    for code, m, d, prev, bal, lim, nt in cur.execute("""
+        SELECT s.stock_code, s.market_type, x.trade_date, x.sbl_prev, x.sbl_balance, x.sbl_limit, x.note
+        FROM sbl_trades x JOIN stocks s ON s.stock_id = x.stock_id"""):
+        per_stock[code][d] = (prev, bal, lim, nt)
+        by_m[m][d].append((prev, bal))
+    sdates = {m: sorted(ds)[-6:] for m, ds in by_m.items()}
+    return sdates, {m: {sdates[m][-1]: by_m[m][sdates[m][-1]]} for m in sdates}, per_stock
+
+
 def market_margin(dates, official, stocks, etfs, close):
     """
     一個市場的融資融券區塊（latest.json 的 margin.TWSE／margin.TPEx）。
@@ -826,7 +881,7 @@
 
 
 def screen_build(rows, head):
-    """screen.json：欄式。rows：{代號: {SCREEN_KEYS…}}（依代號排序）；head：d、fd、md。rmd = 各營收月份的檔數。"""
+    """screen.json：欄式。rows：{代號: {SCREEN_KEYS…}}（依代號排序）；head：d、fd、md、sd（第 11 輪：各市場借券資料日）。rmd = 各營收月份的檔數。"""
     codes = sorted(rows)
     rmd = Counter(rows[c]["rm"] for c in codes if rows[c]["rm"] is not None)
     fqd = Counter(rows[c]["fq"] for c in codes if rows[c].get("fq") is not None)        # 第 10 輪：各季報季別的檔數
@@ -921,6 +976,7 @@
 
     stocks = {r[0]: {"name": r[1], "market": r[2], "industry": r[3] or "其他"}
               for r in cur.execute("SELECT stock_code, stock_name, market_type, industry FROM stocks")}
+    shares = {c: n for c, n in cur.execute("SELECT stock_code, shares FROM stocks WHERE shares > 0")}     # 第 11 輪
 
     # ── 每檔股票完整日線 + 法人 ──
     prices = defaultdict(list)
@@ -985,9 +1041,12 @@
     status = build_status(cur, latest_date, now)
     valuation, stock_val, val_date = _load_valuation(cur)      # F9-4
     fin, fin_meta, fin_counts = _load_financials(cur)          # 第 10 輪 B5
+    sdates, srecent, sper = _load_sbl(cur)                     # 第 11 輪 B14
     conn.close()
     mlast = {m: ds[-1] for m, ds in mdates.items()}
     m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
+    slast = {m: ds[-1] for m, ds in sdates.items()}
+    s5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in sdates.items()}
 
     concepts = load_concepts()
     concept_of = defaultdict(list)
@@ -1036,7 +1095,11 @@
         rev_rows = _revenue_rows(revenue.get(code, []))
         mrows = mper.get(code, {})
         conv = margin_conv(mrows, ev)
-        mg = margin_series(d_, mrows, conv)
+        srows = sper.get(code, {})
+        mg = margin_series(d_, mrows, conv, srows)
+        mk_ = info["market"]
+        sbl = stock_sbl(srows, slast.get(mk_), s5.get(mk_), shares.get(code),
+                        (mrows.get(slast.get(mk_)) or (None,) * 5)[4], conv)
         act = None
         if code in act_lots and dates[-1] in d_ and tn[d_.index(dates[-1])] is not None:
             t_lots = round(tn[d_.index(dates[-1])] / 1000)
@@ -1063,6 +1126,7 @@
             **({"margin": stock_margin(mrows, mlast[info["market"]], m5[info["market"]], conv)}
                if info["market"] in mlast else {}),
             **({"active": active[code]} if code in active else {}),
+            **({"sbl": sbl} if sbl else {}),                                     # 第 11 輪 B14：該股最新借券日沒有列 → 不輸出
             **({"mg": mg} if mg else {}),
             **({"act": act} if act else {}),
         })
@@ -1142,7 +1206,8 @@
                         **revenue_stats(rev_rows), "cap": int(cap is not None),
                         **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt),
                         "pbp": (stock_val.get(code) or {}).get("pb", [None])[0],     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
-                        **fin_screen(fin.get(code))}                                  # 第 10 輪 B5
+                        **fin_screen(fin.get(code)),                                  # 第 10 輪 B5
+                        **{k: (sbl or {}).get(k) for k in ("lb", "l1", "l5", "lp")}}   # 第 11 輪 B14
 
     industries = defaultdict(list)
     for code in snapshot:
@@ -1179,6 +1244,7 @@
         "futures_oi": futures_oi,
         "forecast": forecast,
         "margin": margin,
+        "sbl": {m: market_sbl(sdates[m], srecent[m]) for m in ("TWSE", "TPEx") if sdates.get(m)} or None,   # 第 11 輪 B14
         "etfs": etf_block(etf_latest, etf_margin_rows),
         "holdings": {code: {"d": str(hd[-1]), "n": etf_names[code][0],
                             **({"u1": u} if (u := unit_change(hs, hd)) is not None else {})}
@@ -1194,7 +1260,8 @@
         "stocks": snapshot,
     }
     # screen.json 在 latest.json 之前寫：中途失敗時前端比對 d／fd 會顯示不同步
-    S = screen_build(screen, {"d": str(latest_date), "fd": str(dates[-1]), "md": {m: str(d) for m, d in mlast.items()}})
+    S = screen_build(screen, {"d": str(latest_date), "fd": str(dates[-1]), "md": {m: str(d) for m, d in mlast.items()},
+                              "sd": {m: str(d) for m, d in slast.items()}})
     _write(SITE_DATA_DIR / "screen.json", S)
     _write(SITE_DATA_DIR / "latest.json", latest)
     size = (SITE_DATA_DIR / "latest.json").stat().st_size / 1024
diff -ruN -x __pycache__ -x *.pyc orig/twstock/health.py proj/twstock/health.py
--- orig/twstock/health.py	2026-11-06 23:47:12
+++ proj/twstock/health.py	2026-11-07 00:44:29
@@ -53,6 +53,7 @@
     Spec("futures", "台指期", 1, False), Spec("futures_oi", "期貨法人", 9, False),
     Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
     Spec("margin.TWSE", "上市融資融券", 800, False), Spec("margin.TPEx", "上櫃融資融券", 550, False),
+    Spec("sbl.TWSE", "上市借券", 800, False), Spec("sbl.TPEx", "上櫃借券", 550, False),     # 第 11 輪 B14：股票檔數
     Spec("breadth.TWSE", "上市漲跌家數", 1, False, BREADTH_FROM), Spec("breadth.TPEx", "上櫃漲跌家數", 1, False, BREADTH_FROM),
 ) + tuple(Spec(f"holdings.{c}", f"{c}持股", 1, False, f.since, f.delay) for c, f in HOLDINGS.items())
 SPEC = {s.key: s for s in SPECS}
@@ -63,6 +64,7 @@
           "FROM stock_fundamentals x",
     "insti": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM institutional_trades x",
     "margin": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM margin_trades x",
+    "sbl": "SELECT x.trade_date, s.market_type, COUNT(*), 0, 0, 0 FROM sbl_trades x",
 }
 
 
```
