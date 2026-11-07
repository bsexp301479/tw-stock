# 第 12 輪｜System Analyst：設計規格

- 依據：`12/01-analyst.md`、`12/02-pm.md`（F12-1～F12-4）。
- 作法：在 scratchpad 建立專案副本（`orig`＝目前程式、`proj`＝本設計；**不含 `.env`**），以唯讀方式模擬匯出（`export_all` 只執行 SELECT，輸出到 scratchpad，不寫 `site/data`）。
- 本文所有數字都來自這次模擬匯出（資料日 2026-11-06）；附錄 A 是完整 diff，PG 可以直接套用。
- 本輪 **0 個外部請求、0 個資料庫寫入、沒有 DDL、不改收集程式、不改 `__main__.py`**。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（＋／−） |
|---|---|---|---|
| F12-1 P26 | `site/stock.js` | 融資融券圖單位文字加「右側刻度只適用融資」 | 2／1 |
| F12-2 | `twstock/export.py` | `market_wpe()`；`_load_valuation` 多讀收盤、算加權本益比 | 約 40 |
| F12-2 | `site/app.js` | 估值卡 `wpeLine()` | 約 13 |
| F12-3 | `twstock/export.py` | `_load_etf_sbl()`；`etf_block` 加 `lb`、`l1`；`latest.json` 的 `sbl_etf` | 約 20 |
| F12-3 | `site/app.js` | 今日頁 `etfSblLine()`；ETF 頁兩欄、三個排序、說明 | 約 15 |
| F12-4 | `twstock/export.py` | `cap_turnover()`；個股 `mt`；`screen.json` 的 `mc`、`to` | 約 20 |
| F12-4 | `site/app.js`、`site/stock.js` | 週轉率排行、選股兩欄兩條件、個股頁兩張卡 | 約 15 |
| 測試 | `tests/test_iter12.py`（新） | 7 個測試 | 98 |
| 比對 | `logs/iter12_compare.py`（新） | 由 `iter11_compare.py` 改 | 66 |
| 文件 | `README.md` | 第十節 | 約 10 |

合計（不含 README）：＋298／−23，PM 估計約 165 行（程式＋畫面），本設計程式＋畫面約 155 行，其餘是測試與比對工具。

### 建議實作順序

同 PM 第四節「相依性」：基線 → F12-1 → F12-2 → F12-3 → F12-4 → README → 測試 → `export` → 比對 → 8001 預覽。

---

## 一、F12-1 借券線刻度說明（P26）

- **決定：用文字，不加左側刻度。**
  - 理由：左側刻度要再占一欄寬度，375 px 下圖會變窄；而借券、融券本來就各自縮放（為了不被融資壓平），給借券刻度但融券沒有，反而不一致。
- `site/stock.js` 融資融券圖的 `#gUnit` 文字，在原本的單位說明後加：
  - `　右側刻度只適用融資；融券、借券各自縮放，數值看圖例`
- 不改圖表設定，所以融券線仍然不被壓平（PM 驗收 #1）。
- 原型確認：`#/stock/2330` 顯示「（張；面額變更、減資前的餘額依官方換算）　右側刻度只適用融資；融券、借券各自縮放，數值看圖例」。

---

## 二、F12-2 加權本益比（A10-延伸）

### 2-1 算法 `market_wpe(rows, days)`（`export.py`，放在 `market_valuation` 後）

- `rows = [(日期, 市場, 代號, 本益比, 市值)]`；`days` = 既有中位數的窗口日期（舊到新，同 `market_valuation`）。
- 市值 = 收盤 × `stocks.shares`（目前股數），收盤取 `daily_prices` 同一天的 `close_price`。
- 每市場每天：
  - **全部市值** = 有市值（> 0）的股票市值合計（覆蓋率的分母）。
  - **計入市值**、**Σ 市值 ÷ 本益比**：只計本益比 > 0（0、負、NULL 都不計）。
  - 加權本益比 = 計入市值 ÷ Σ（市值 ÷ 本益比）。
- 某天沒有任何計入的股票 → 那天跳過（不當成 0）；某市場整個窗口都沒有 → 不輸出該市場（不報錯）。
- 輸出（今天＝窗口最後一個有值的日子）：

| 鍵 | 意義 | 小數 |
|---|---|---|
| `v` | 今天加權本益比 | 2 |
| `p` | 一年位置 %（定義同中位數：≤ 今天的天數 ÷ 天數） | 1 |
| `lo`、`hi` | 一年最低、最高 | 2 |
| `cov` | 計入市值 ÷ 全部市值 % | 1 |
| `t` | `[市值最大的計入股票代號, 占計入市值 %]` | 1 |

- `t` 用「最大市值的股票」而不寫死 2330：上市是 2330（43.2%）；上櫃是 5274（6.0%），上櫃不顯示。

### 2-2 讀取（共用既有一年本益比讀取，不再多讀一次）

- `_load_valuation(cur, shares=None)`：既有 SQL 加
  `LEFT JOIN daily_prices p ON p.stock_id = f.stock_id AND p.trade_date = f.trade_date`，多選 `p.close_price`。
- 同一個迴圈組 `wrows`（`shares` 有值且收盤有值才算市值），最後 `mv[m]["wpe"] = market_wpe(...)[m]`（有才放）。
- `export_all` 改成 `_load_valuation(cur, shares)`（`shares` 是第 11 輪既有的 `{代號: 股數}`）。

### 2-3 `latest.json` 位置

- `valuation.TWSE.wpe`、`valuation.TPEx.wpe`（在既有物件裡加一個鍵，不改既有鍵）。
- 模擬結果（11/06）：

| 市場 | `v` | `p` | `lo`～`hi` | `cov` | `t` |
|---|---|---|---|---|---|
| 上市 | 20.21 | 4.5 | 19.41～30.93 | 98.6 | 2330, 43.2 |
| 上櫃 | 16.54 | 0.4 | 16.54～34.66 | **93.4** | 5274, 6.0 |

- **和 PM 的差異：上櫃覆蓋率 93.4%（PM 93.2%）。**
  - 原因：覆蓋率的分母只含「當天有官方本益比資料列（`stock_fundamentals`）」的股票；上櫃有 5 檔有收盤、有股數，但當天沒有本益比資料列，不在分母。PM 的 93.2% 是用「全部有收盤的股票」當分母。
  - SA 決定採 93.4%：分母和分子來自同一份資料列，口徑一致；差 0.2 點不影響解讀。**QA 驗收請用 93.4%**（SQL 見第七節）。

### 2-4 畫面：今日頁估值卡 `wpeLine(V)`（`site/app.js`）

- 位置：上市、上櫃中位數兩行之後、迷你圖之前。
- 第一行（`num`）：`加權本益比（市值加權）　上市 20.21（一年位置 4.5%）　上櫃 16.54（一年最低）`
  - 今天 ≤ 最低顯示「一年最低」、≥ 最高顯示「一年最高」，否則「一年位置 N%」（同既有中位數）。
- 第二行（說明，定稿）：
  > 加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大（最大的 台積電 占上市 43.2%）；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字
- 名稱由 `latest.stocks[代號].n` 取得，取不到就顯示代號。
- 兩個市場都沒有 `wpe` → 整段不出現。
- **不加迷你圖第二條線**：加權本益比和中位數差約 5 點，同一張迷你圖兩條線會把中位數的起伏壓平；60 日只看位置數字已足夠。
- 既有說明「不是加權指數本益比」保留：它描述的是上面的中位數，仍然正確。

---

## 三、F12-3 ETF 借券

### 3-1 匯出

- `_load_etf_sbl(cur)`：讀 `etf_sbl`＋`etfs`，**各市場**取自己的最新借券日。
  - 回傳 `(日期 {市場: 日期}, {代號: (前日餘額, 餘額)}（股）, by_m {市場: {代號: (日期, 前日, 餘額)}})`。
- `etf_block(latest, margin_rows, sbl_rows=None)`：有借券列的 ETF 加 `lb`＝`lots(餘額)`、`l1`＝`lots(餘額 − 前日)`（張）；沒有借券列 → 不輸出這兩鍵（畫面顯示 `--`）。舊的兩參數呼叫結果不變。
- `latest.json` 新鍵 `sbl_etf`：`{TWSE|TPEx: market_sbl([日期], {日期: [(前日, 餘額)…]})}` → `{d, lb, l1, n}`。
  - 沿用第 11 輪 `market_sbl`：**先合計股數再換成張**，所以合計 ≠ 各檔張數相加（差在四捨五入）。
- 模擬結果（11/06）：

| 項目 | 借券餘額（張） | 1 日（張） |
|---|---|---|
| 00685L | 724,546 | +19,578 |
| 00631L | 434,701 | +5,812 |
| 0050 | 261,795 | +7,030 |
| 00919 | 230,269 | +21,128 |
| 上市合計（240 檔） | 5,040,282 | +188,565 |
| 上櫃合計（117 檔） | 419,845 | −12,245 |

- ETF 列表 363 檔中 357 檔有借券；1 日增加最多的是 009816（+49,033）。

### 3-2 今日頁信用交易卡 `etfSblLine(L.sbl_etf)`

- **口徑調整（SA 決定）**：既有「ETF 另計」一行只有上市 ETF 的融資融券。借券另起一行，**上市、上櫃分開寫明**，不和融資融券那行合併。
  - 理由：上櫃 ETF 借券 42 萬張（約占 8%），只寫上市會漏；分開標示市場就不會和上一行的口徑混淆。
- 顯示：`ETF 借券賣出　上市 504 萬張 +188,565　上櫃 42.0 萬張 -12,245　ETF 頁 →`
  - 萬張：≥ 100 萬張取整數，否則 1 位小數；滑鼠移上去顯示完整張數。1 日增減用張（同第 11 輪的股票借券行）。
- 說明（定稿）：
  > ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空
- `sbl_etf` 不存在 → 兩行都不出現。

### 3-3 ETF 頁 `#/etf`

- 表格最後加兩欄「借券餘額」「借券增減」（張；沒有值顯示 `--`；增減用既有的紅綠 `lots()` 格式）。
- 排序加三項：借券增加（`l1` 由大到小）、借券減少（`l1` 由小到大）、借券餘額（`lb` 由大到小）。沿用既有 `ETF_SORT` 的「`+`／`-` 字尾」規則，null 排最後。
- 說明文字加：「借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。」
- 原型確認：依借券餘額排序，第一列 00685L 724,546／+19,578；市場篩選照常。

---

## 四、F12-4 市值與週轉率（B11）

### 4-1 匯出

- `cap_turnover(close, volume, shares)` → `(市值 億元 1 位, 週轉率 % 2 位)`。
  - 沒有股數（NULL 或 0）→ `(None, None)`；沒有收盤 → 市值 None；成交量 None → 週轉率 None。
- 每檔股票：
  - 收盤用**最後一個非空收盤**；成交量只在最後一筆就是全市場最新資料日時才用（今天沒成交的股票週轉率 = null，不用舊日資料）。
  - 個股 JSON 加 `"mt": {"d": 日期, "mc": 市值, "to": 週轉率}`（`mc` 有值才加）。
  - `screen.json` 加 `mc`、`to` 兩欄（`SCREEN_KEYS` 加 `"mc", "to"`）。**沒有使用 `cap`**（`cap` 仍是 90 天股本變動旗標）。
- 模擬結果（11/06）：

| 項目 | 值 |
|---|---|
| 2330 | 市值 553,656.1 億、週轉率 0.43% |
| 2454 | 市值 54,407.9 億 |
| 6148／2468 | 週轉率 92.22%／62.45% |
| `screen.json` | 1,983 檔有 `mc`；週轉率 ≥ 5% 有 37 檔、≥ 10% 有 17 檔 |
| 沒有 `mt` 的個股 | 9 檔（沒有股數，例如 2867 三商壽） |

### 4-2 個股頁（`site/stock.js`）

- 指標卡在「投信5日」之後、融資融券卡之前加兩張：
  - **市值**：≥ 1 萬億顯示「55.37 兆」，≥ 100 億取整數「N 億」，否則 1 位小數；小字「收盤 × 目前發行股數」。
  - **週轉率**：`0.43%`；小字「11/06，成交股數 ÷ 目前發行股數」。
- 沒有 `mt`（沒有股數）→ 兩張卡都顯示 `--`，小字「沒有發行股數資料」（PM 驗收 #4；原型以 2867 確認）。

### 4-3 排行

- `RANKS` 加 `['to', '週轉率', 'to', -1, 'x']`，放在「價量」組最後；欄位 `RANK_COLS.to = ['to', 'mc']`（週轉率、市值）。
- **成交額門檻沿用既有排行設定（預設 ≥ 0.5 億）**，不另外設：門檻本來就是為了排除冷門股，週轉率極端值多半出在冷門小型股，正好需要它。
- 排行說明尾端加：「週轉率 = 今日成交股數 ÷ 目前發行股數，市值 = 收盤 × 目前發行股數；增資、減資前後可能失真。」
- 原型確認：`#/rank/to` 前三名 6148（92.22%）、2468（62.45%）、6925（41.90%）。

### 4-4 選股

- 欄位 `SCR_COLS`：`mc` 市值（`N億`，0 位）、`to` 週轉率（`N.NN%`）；兩欄都不上紅綠色。
- 條件（「流動性」組，接在 20 日均成交額之後）：

| id | 文字 | 選項 | 預設 | 說明（滑鼠移上去） |
|---|---|---|---|---|
| `mc` | 市值 ≥ {v} 億 | 50、100、500、1000 | 100 | 收盤 × 目前發行股數 |
| `to` | 週轉率 ≥ {v}% | 1、3、5、10 | 3 | 今日成交股數 ÷ 目前發行股數；增資、減資前後可能失真 |

- null 一律不符合（沿用 `scrGe`）。網址帶 `mc=`、`to=` 可還原；「重設」沿用既有邏輯（新條件不在預設中，不殘留）。
- 原型確認：`#/rank/screen?mc=100&to=3` 列出 68 檔，和直接用 `screen.json` 計算的檔數相同。

---

## 五、匯出大小與時間

| 項目 | 增加 | PM 上限 |
|---|---|---|
| `latest.json` | +6,348 B（`sbl_etf` 118 B、`wpe` 153 B、ETF `lb`／`l1` 6,066 B） | 15 KB |
| `screen.json` | +20,211 B（19.7 KB） | 25 KB |
| `stocks/*.json` 的 `mt` | 1,990 檔共 86 KB（每檔約 44 B） | — |
| 匯出時間 | 21.1 → 21.8 秒（+0.7 秒；同一機器連續執行） | +2 秒 |

---

## 六、網站隔離比對 `logs/iter12_compare.py`

- 由 `iter11_compare.py` 改寫；剔除本輪新鍵：
  - `latest.json`：`sbl_etf`、`valuation.*.wpe`、`etfs.rows.*.lb`／`l1`。
  - `stocks/*.json`：`mt`。
  - `screen.json`：`mc`、`to`。
- 時間欄位照舊略過。`status.datasets` 本輪不變，所以拿掉第 11 輪的 `sbl.*` 特例。
- 模擬結果：
  - 正常模式：`✅ 相同`（latest、screen、stocks 1,999 檔、etfs 8 檔）。
  - `--keep-new`：判定不同 1,994 處（反證有效）。

---

## 七、QA 清單與 SQL

QA 依 PM 驗收條件逐項做；以下補充 SQL 口徑（全部唯讀）。

1. **加權本益比**（11/06）：

   ```sql
   SELECT s.market_type,
          ROUND(SUM(CASE WHEN f.pe_ratio > 0 THEN p.close_price * s.shares END)
              / SUM(CASE WHEN f.pe_ratio > 0 THEN p.close_price * s.shares / f.pe_ratio END), 2) AS wpe,
          ROUND(100.0 * SUM(CASE WHEN f.pe_ratio > 0 THEN p.close_price * s.shares END)
              / SUM(p.close_price * s.shares), 1) AS cov
   FROM stock_fundamentals f
   JOIN stocks s ON s.stock_id = f.stock_id
   JOIN daily_prices p ON p.stock_id = f.stock_id AND p.trade_date = f.trade_date
   WHERE f.trade_date = '2026-11-06' AND s.shares > 0 AND p.close_price IS NOT NULL
   GROUP BY s.market_type;
   ```

   - SA 已用這段 SQL 唯讀執行確認：上市 20.21／98.6、上櫃 16.54／93.4，和模擬匯出相同。
   - 預期：上市 20.21／98.6、上櫃 16.54／93.4。位置與範圍：對窗口 242 天各算一次，取最低、最高與位置。
2. **ETF 借券**：`etf_sbl` 各市場最新日，`SUM(sbl_balance)`、`SUM(sbl_balance − sbl_prev)` 先合計股數再除以 1,000 四捨五入。
3. **市值、週轉率**：`close_price × shares / 1e8`、`volume / shares × 100`，資料日 11/06。
4. **畫面**：375 px 檢查今日頁（估值卡、信用交易卡）、`#/etf`、`#/stock/2330`、`#/stock/2408`、`#/stock/2867`（`--`）、`#/rank/to`、選股兩個條件；沒有水平捲動，主控台沒有錯誤（`favicon.ico` 404 是既有現象，不算）。

---

## 八、邊界情況

| 情況 | 處理 |
|---|---|
| 股票本益比 0、負、NULL | 不計入加權本益比（仍計入覆蓋率分母） |
| 股票沒有股數或沒有收盤 | 不計入加權本益比的任何部分；`mc`、`to` 為 null；個股頁 `--` |
| 某天某市場全部虧損 | 那天跳過 |
| 某市場沒有任何本益比資料 | 不輸出該市場 `wpe`；兩市場都沒有 → 估值卡不顯示加權那兩行 |
| 今天沒有成交 | 週轉率 null（不用舊日的成交量）；市值用最後一個收盤 |
| ETF 沒有借券資料 | ETF 頁 `--`；不影響合計 |
| `etf_sbl` 是空表 | `sbl_etf` 不輸出；今日頁兩行不出現；ETF 頁兩欄全為 `--` |
| 上市、上櫃借券日不同 | 各自用自己的最新日，`sbl_etf.*.d` 各自標示 |
| 增資、減資前後 | 市值、週轉率、歷史加權本益比都用目前股數，會有誤差；說明文字已寫明 |

---

## 九、測試 `tests/test_iter12.py`（新檔，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_f122_wpe_formula` | 公式；本益比 NULL／0／負不計入但計入覆蓋率；沒有市值完全不算；最大權重 |
| `test_f122_wpe_position_and_markets` | 位置、範圍、兩市場；窗口外略過；沒有資料、全部虧損 → 不輸出；某天全部虧損跳過 |
| `test_f122_wpe_export_source` | 讀取有 JOIN 收盤、寫入 `wpe` |
| `test_f123_etf_block` | `lb`、`l1` 張數；沒有借券列不輸出；舊呼叫相容；合計先加股數 |
| `test_f123_export_source` | `_load_etf_sbl`、`sbl_etf` |
| `test_f124_cap_turnover` | 2330 的實際數字；沒有股數／收盤／成交量；`SCREEN_KEYS` |
| `test_f12_site` | P26 文字、個股頁卡片與 `--`、估值卡、ETF 兩行、ETF 頁欄位與排序、排行、選股條件、不上色清單 |

- 原型上 `test_iter01`～`test_iter12` 全部通過；舊測試不用改。

---

## 十、README 修改清單（`__main__.py` 不用改）

第十節「注意事項」：

1. **今日頁估值位置卡**（第 132 行附近）：加一段「第 12 輪：加權本益比（市值加權）……」，內容同 2-1 算法、2-4 說明，並註明 `valuation.*.wpe` 的鍵。
2. **條件選股**（第 130 行）：加「第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億）、`to` 週轉率（%），沒有股數為 null」；句末排行列舉加「週轉率」。
3. **借券賣出**（第 155 行）：加「ETF 借券：`latest.json` 的 `sbl_etf`（上市、上櫃合計）、ETF 頁借券兩欄；今日頁信用交易卡另一行」。
4. **ETF**（第 157 行）：ETF 頁欄位加借券餘額、借券增減與三個排序。
5. **個股頁**：加市值、週轉率卡（`stocks/{代號}.json` 的 `mt`），以及融資融券圖「右側刻度只適用融資」。

---

## 十一、PG 實作與資料操作步驟

1. **基線**：用目前程式（套用 diff 前）`python3 -u -m twstock export`，把 `site/data` 複製到 `logs/iter12_before/`。這是本輪唯一允許的寫入動作。
2. 套用附錄 A 的 diff（`export.py`、`app.js`、`stock.js`、兩個新檔）。
3. `node --check site/app.js site/stock.js`；`test_iter01`～`test_iter12` 全部通過。
4. 修改 README（第十節）。
5. `python3 -u -m twstock export`；`python3 logs/iter12_compare.py logs/iter12_before site/data` → `✅ 相同`；加 `--keep-new` → 判定不同。
6. 數字核對：第二～四節的表格（2330、2454、6148、2468、ETF 4 檔、合計、加權本益比、≥ 5%／≥ 10% 檔數）。
7. 8001 預覽（375 px），結束時關掉；不要用 8000。

**停止條件**：比對不相同、或任一數字和本文不同時，先停下回報，不要自行調整口徑。若 PG 執行時資料日已經不是 11/06（使用者每晚收集），數字以 SQL 重算為準，並在 `04-dev.md` 記錄資料日。

---

## 十二、延後順序（沿用 PM）

時間不夠時依序延後：F12-4 選股條件 → F12-4 週轉率排行 → F12-3 今日頁 ETF 一行。F12-1、F12-2 全部、F12-3 ETF 頁欄位、F12-4 個股頁卡片不延後。

---

## 十三、對 PM 範圍的調整（不改 02-pm.md）

1. 上櫃加權本益比覆蓋率驗收值改為 **93.4%**（2-3）。
2. 今日頁 ETF 借券另起一行，上市、上櫃都顯示並標明市場（3-2）；既有 ETF 融資融券那行不變。
3. ETF 頁欄名用「借券增減」（PM 寫「借券 1 日」），和既有「融資增減」「融券增減」一致；排序多一個「借券餘額」。
4. 加權本益比的權重欄（`t`）用「計入股票中市值最大的一檔」，上市就是台積電；上櫃不顯示。
5. 不加迷你圖第二條線（2-4）。
6. 沒有找證交所官方大盤本益比（0 請求）；仍留在待辦第 9 項。

---

## 十四、給 PG、QA 的提醒

- 不要動 `.env`；不要安裝排程或改系統設定；8000 是使用者的伺服器，測試用 8001 並在結束時關掉。
- 本輪只允許 `export`；不執行 `collect`、`history`、`setup-db`、`backup`、`update_industry`、還原。
- 第 11 輪尚未 commit：本輪的修改會疊在同一個工作目錄，PG 不要 commit。
- `python3 -u` 執行長指令；不要印出資料庫帳密。

---

## 附錄 A：完整 diff（`diff -ruN -x __pycache__ orig proj`）

```diff
diff -ruN -x __pycache__ orig/logs/iter12_compare.py proj/logs/iter12_compare.py
--- orig/logs/iter12_compare.py	1970-01-01 08:00:00
+++ proj/logs/iter12_compare.py	2026-11-07 23:01:31
@@ -0,0 +1,66 @@
+# 用法：python3 logs/iter12_compare.py 基線資料夾 site/data [--keep-new] —— 隔離比對（第 12 輪，取代 iter11_compare.py）
+# 除了第 12 輪指定的新鍵與「時間」欄位以外必須完全相同；比對 latest.json、screen.json、stocks/*.json、etfs/*.json。
+# 新鍵：latest.json 的 sbl_etf、valuation.TWSE／TPEx 的 wpe、etfs.rows.*.lb、l1；stocks/*.json 的 mt；screen.json 的 mc、to。
+# 另外印出新鍵的大小。--keep-new：不剔除新鍵（反證用，應判定不同）。相同印「✅ 相同」rc=0，否則 rc=1。
+import json, sys
+from pathlib import Path
+a, b = Path(sys.argv[1]), Path(sys.argv[2])
+KEEP = "--keep-new" in sys.argv
+NEW_LATEST = set() if KEEP else {"sbl_etf"}
+NEW_STOCK = set() if KEEP else {"mt"}
+NEW_SCREEN = set() if KEEP else {"mc", "to"}
+TIME_LATEST, TIME_STATUS = {"updated_at"}, {"exported_at", "collected_at"}
+bad = []
+drop = lambda d, keys: {k: v for k, v in d.items() if k not in keys}
+load = lambda p: json.loads(p.read_text(encoding="utf-8"))
+size = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode())
+
+
+def strip_latest(k, y):
+    if KEEP or not isinstance(y, dict):
+        return y
+    if k == "valuation":
+        return {m: drop(v, {"wpe"}) if isinstance(v, dict) else v for m, v in y.items()}
+    if k == "etfs" and isinstance(y.get("rows"), dict):
+        return {**y, "rows": {c: drop(r, {"lb", "l1"}) for c, r in y["rows"].items()}}
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
+    x, y = (drop(LA[k], TIME_STATUS), drop(LB2[k], TIME_STATUS)) if k == "status" else (LA[k], strip_latest(k, LB2[k]))
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
+        if sub == "stocks" and "mt" in y:
+            new_bytes += size(y["mt"]) + len(',"mt":')
+            new_n += 1
+        if x != (drop(y, NEW_STOCK) if sub == "stocks" else y):
+            bad.append(f"{sub}/{f}")
+    n[sub] = len(fa)
+print(f"比對 latest.json、screen.json、stocks {n['stocks']} 檔、etfs {n['etfs']} 檔（略過 {sorted(TIME_LATEST)}、status.{sorted(TIME_STATUS)}"
+      + ("" if KEEP else "；剔除新鍵 latest 的 sbl_etf、valuation.*.wpe、etfs.rows.*.lb／l1、stocks 的 mt、screen 的 mc、to") + "）")
+scr = sum(size(SB[k]) + len(k) + 4 for k in ("mc", "to") if k in SB)
+wpe = sum(size(v["wpe"]) + len(',"wpe":') for v in (LB.get("valuation") or {}).values() if isinstance(v, dict) and "wpe" in v)
+etf = size(LB.get("etfs")) - size(strip_latest("etfs", LB.get("etfs"))) if not KEEP and LB.get("etfs") else 0
+print(f"ℹ️  新鍵大小：stocks 的 mt {new_n} 檔共 {new_bytes / 1024:.0f} KB；screen.json 新欄 {scr / 1024:.1f} KB；"
+      f"latest.json sbl_etf {size(LB['sbl_etf']) if 'sbl_etf' in LB else 0} B、wpe {wpe} B、etfs 的 lb／l1 {etf} B")
+if bad:
+    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
+    sys.exit(1)
+print("✅ 相同")
diff -ruN -x __pycache__ orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-07 00:56:37
+++ proj/site/app.js	2026-11-07 22:59:37
@@ -267,6 +267,7 @@
       <div class="s num">融資金額（官方，含 ETF）上市 ${amt(T)}　上櫃 ${amt(O)}</div>
       ${sblLine(L)}
       ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
+      ${etfSblLine(L.sbl_etf)}
       ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
       <div class="s">維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
       <div class="s">參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。</div>
@@ -284,6 +285,15 @@
       <div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>`;
 }
 
+// 第 12 輪 ETF-借券：ETF 借券賣出合計（上市、上櫃 ETF，張）；多為造市、套利與避險
+function etfSblLine(B) {
+  if (!B) return '';
+  const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
+  const one = (x, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>`;
+  return `<div class="s num">ETF 借券賣出　${[one(B.TWSE, '上市'), one(B.TPEx, '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/etf">ETF 頁 →</a></div>
+      <div class="s">ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空</div>`;
+}
+
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
 function breadthCard(L) {
   const B = L.breadth;
@@ -309,12 +319,24 @@
   return `<div class="card stat idx val">
       <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
       ${row(V.TWSE, '上市')}${row(V.TPEx, '上櫃')}
+      ${wpeLine(V)}
       ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
       ${finLine(L.fin_progress)}
       <div class="s">一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號</div>
     </div>`;
 }
 
+// 第 12 輪 A10-延伸：市值加權本益比（本站以目前股數計算）；和上面的中位數並列
+function wpeLine(V) {
+  const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
+  if (!T && !O) return '';
+  const pos = x => x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
+  const one = (x, name) => !x ? '' : `${name} <b>${fmt(x.v, 2)}</b>（${pos(x)}）`;
+  const big = T?.t ? `最大的 ${esc(App.latest.stocks?.[T.t[0]]?.n || T.t[0])} 占上市 ${fmt(T.t[1], 1)}%` : '';
+  return `<div class="s num">加權本益比（市值加權）　${[one(T, '上市'), one(O, '上櫃')].filter(Boolean).join('　')}</div>
+      <div class="s">加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字</div>`;
+}
+
 // 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
 function finLine(P) {
   if (!P) return '';
@@ -667,16 +689,17 @@
   ['fs', '外資連買', 'fs', -1], ['ts', '投信連買', 'ts', -1], ['s', '法人連買', 's', -1],
   ['p+', '漲幅', 'p', -1], ['p-', '跌幅', 'p', 1], ['tv', '成交額', 'tv', -1],
   ['vr', '量比', 'vr', -1, 'x'], ['nh', '創新高（N 日）', 'nh', -1, 'x'], ['rs20', '20 日相對強勢', 'rs20', -1, 'x'],
+  ['to', '週轉率', 'to', -1, 'x'],                                                  // 第 12 輪 B11
   ['ry', '營收年增', 'ry', -1, 'x'], ['dy', '殖利率', 'dy', -1, 'v'], ['pe', '本益比最低', 'pe', 1, 'v'],
   ['m+', '融資增加', 'm*', -1, 'm'], ['m-', '融資減少', 'm*', 1, 'm'], ['mr', '融資增加率', 'mr*', -1, 'm'],
   ['s+', '融券增加', 's*', -1, 'm'], ['s-', '融券減少', 's*', 1, 'm'], ['sr', '券資比', 'sr', -1, 'm'], ['mu', '融資使用率', 'mu', -1, 'm'],
   ['l+', '借券賣出增加', 'la*', -1, 'l'], ['lp', '借券占股本', 'lp', -1, 'l'],     // 第 11 輪 B14：'l' = 借券（需要 screen.json）
 ];
-const RANK_GROUPS = [['法人', ['n+', 'n-', 'f+', 'f-', 't+', 't-', 'd+', 'd-', 'fs', 'ts', 's']], ['價量', ['p+', 'p-', 'tv', 'vr', 'nh', 'rs20']],
+const RANK_GROUPS = [['法人', ['n+', 'n-', 'f+', 'f-', 't+', 't-', 'd+', 'd-', 'fs', 'ts', 's']], ['價量', ['p+', 'p-', 'tv', 'vr', 'nh', 'rs20', 'to']],
   ['基本面', ['ry', 'dy', 'pe']], ['融資融券', ['m+', 'm-', 'mr', 's+', 's-', 'sr', 'mu']], ['借券', ['l+', 'lp']]];
 // screen.json 排行的額外篩選與表格欄位
 const RANK_FILTER = { nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
-const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'] };
+const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'], to: ['to', 'mc'] };
 const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) : '--';
 const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股']], v);
 const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'screen' ? '#/rank/screen' : '#/rank'; });
@@ -736,7 +759,7 @@
     } else table = screenTable(list, RANK_COLS[by]);
   }
   if (!foot) foot = '金額 = 買賣超張數 × 當日收盤，不含 ETF。成交額門檻以資料日成交額篩選，套用到所有排行。「1日／5日」只切換法人、外資、投信、自營買賣超排行與表格法人欄位的天數；漲幅、跌幅、成交額與連買排行不受影響。連買為連續買超天數，天數相同時以近 5 日金額排序。' +
-    (S ? '量比、創新高、相對強勢、營收、估值排行的資料日見「選股」頁；殖利率、本益比排行已排除虧損（官方本益比空白）與 90 天內股本變動的股票。' : '');
+    (S ? '量比、創新高、相對強勢、營收、估值排行的資料日見「選股」頁；殖利率、本益比排行已排除虧損（官方本益比空白）與 90 天內股本變動的股票。週轉率 = 今日成交股數 ÷ 目前發行股數，市值 = 收盤 × 目前發行股數；增資、減資前後可能失真。' : '');
   $('#view').innerHTML = `<section class="sec">
       <div class="sec-h">${modeSeg('rank')}<span class="sp"></span>
         ${segHTML('mktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
@@ -847,6 +870,7 @@
   eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => spct(v) + finTag(x)],
   e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
   gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)], eh: ['EPS新高(季)', x => x.eh, int0],
+  mc: ['市值', x => x.mc, v => fmt(v, 0) + '億'], to: ['週轉率', x => x.to, v => fmt(v, 2) + '%'],   // 第 12 輪 B11
   lb: ['借券餘額', x => x.lb, v => fmt(v)], l5: ['借券5日', x => x.l5, v => sgn(v, 0)], lp: ['借券占股本', x => x.lp, v => fmt(v, 2) + '%'],
 };
 const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
@@ -859,7 +883,7 @@
     list.map(x => `<tr data-code="${x.code}"><td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}${o.cap && x.cap === 1 ? CAP_TAG : ''}<span>${x.code} ${esc(x.i)}</span></td>
       <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.tv, 1)}億</td>` +
       cols.map(k => { const [, get, f] = SCR_COLS[k], v = get(x);
-        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh', 'lb', 'lp'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
+        return `<td class="num ${['s', 'fs', 'ts', 'nh', 'nl', 'rh', 'r3', 'vr', 'a20', 'sr', 'mu', 'pe', 'pb', 'hd', 'pbp', 'gm', 'eh', 'lb', 'lp', 'mc', 'to'].includes(k) ? '' : cls(v)}">${v == null ? '--' : f(v, x)}</td>`; }).join('') + '</tr>').join('') +
     '</tbody></table></div>';
 }
 
@@ -871,6 +895,9 @@
 const SCREEN_CONDS = [
   { id: 'tv', g: '流動性', label: '成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5, 10], def: 0.5, f: scrGe('tv') },
   { id: 'a20', g: '流動性', label: '20 日均成交額 ≥ {v} 億', opts: [0.5, 1, 3, 5], def: 1, f: scrGe('a20'), cols: ['a20'] },
+  // 第 12 輪 B11：目前股數計算；null（沒有股數）不符合
+  { id: 'mc', g: '流動性', label: '市值 ≥ {v} 億', opts: [50, 100, 500, 1000], def: 100, f: scrGe('mc'), cols: ['mc'], title: '收盤 × 目前發行股數' },
+  { id: 'to', g: '流動性', label: '週轉率 ≥ {v}%', opts: [1, 3, 5, 10], def: 3, f: scrGe('to'), cols: ['to'], title: '今日成交股數 ÷ 目前發行股數；增資、減資前後可能失真' },
   { id: 'p', g: '價量', label: '今日漲幅 ≥ {v}%', opts: 'num', def: 3, f: scrGe('p') },
   { id: 'r5', g: '價量', label: '5 日報酬 ≥ {v}%', opts: 'num', def: 10, f: scrGe('r5'), cols: ['r5'] },
   { id: 'r20', g: '價量', label: '20 日報酬 ≥ {v}%', opts: 'num', def: 10, f: scrGe('r20'), cols: ['r20'] },
@@ -1048,7 +1075,8 @@
 }
 
 // ─── ETF（E1）：與股票完全分開，不計入任何個股統計 ─────────
-const ETF_SORT = [['tv', '成交額', -1], ['p+', '漲幅', -1], ['p-', '跌幅', 1], ['m1', '融資增減', -1], ['s1', '融券增減', -1]];
+const ETF_SORT = [['tv', '成交額', -1], ['p+', '漲幅', -1], ['p-', '跌幅', 1], ['m1', '融資增減', -1], ['s1', '融券增減', -1],
+  ['l1+', '借券增加', -1], ['l1-', '借券減少', 1], ['lb', '借券餘額', -1]];     // 第 12 輪 ETF-借券
 
 function renderEtf() {
   const E = App.latest.etfs;
@@ -1068,15 +1096,16 @@
         ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
         <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
       <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
-        <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th></tr></thead><tbody>` +
+        <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th></tr></thead><tbody>` +
       list.map(([c, r]) => `<tr${App.latest.holdings?.[c] ? ` data-etf="${c}"` : ''}><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
         <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
         <td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
         <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td>
         <td class="num">${r.mb == null ? '--' : fmt(r.mb)}</td>${lots(r.m1)}
-        <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}</tr>`).join('') +
+        <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}
+        <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}</tr>`).join('') +
       `</tbody></table></div></div>
-      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
+      <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
   $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr) location.hash = '#/etf/' + tr.dataset.etf; });
diff -ruN -x __pycache__ orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-07 00:56:37
+++ proj/site/stock.js	2026-11-07 23:04:19
@@ -62,6 +62,10 @@
        ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
   // 第 11 輪 B14：借券賣出（張；占股本用目前股數）。sbl 不存在 = 該市場最新借券日沒有這檔
   const SL = data.sbl;
+  // 第 12 輪 B11：市值、週轉率（目前股數）
+  const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
+  const mtCards = [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
+    ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${md(MT.d)}，成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
   const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', `1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`],
     ['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]];
 
@@ -111,7 +115,7 @@
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          ['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
-         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mgCards, ...slCards]
+         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd], ...mtCards, ...mgCards, ...slCards]
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
     ${SL ? `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本以目前發行股數計算。借券資料晚上 8 點半以後才更新。</div>` : ''}
@@ -327,7 +331,8 @@
     // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
     mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
       .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
-    $('#gUnit').textContent = adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）';
+    $('#gUnit').textContent = (adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）') +
+      '　右側刻度只適用融資；融券、借券各自縮放，數值看圖例';     // 第 12 輪 P26
   }
 
   const mc = mk('mC', true);
diff -ruN -x __pycache__ orig/tests/test_iter12.py proj/tests/test_iter12.py
--- orig/tests/test_iter12.py	1970-01-01 08:00:00
+++ proj/tests/test_iter12.py	2026-11-07 23:04:25
@@ -0,0 +1,98 @@
+"""
+第 12 輪純邏輯測試（不連網、不連資料庫）：
+F12-1 P26 融資融券圖刻度說明（原始碼檢查）；
+F12-2 市值加權本益比 market_wpe（公式、虧損／0／空白排除、沒有股數、位置與區間、覆蓋率、最大權重、沒有資料不輸出）與估值卡；
+F12-3 ETF 借券 etf_block 的 lb、l1、latest.json 的 sbl_etf、今日頁與 ETF 頁；
+F12-4 市值、週轉率 cap_turnover、個股 JSON 的 mt、screen.json 的 mc、to、排行與選股（原始碼檢查）。
+
+  python3 tests/test_iter12.py      （也相容 pytest）
+"""
+import sys
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import test_iter03 as t3  # noqa: E402
+from twstock import export  # noqa: E402
+
+D = t3.D
+ROOT = Path(__file__).resolve().parent.parent
+d1, d2, d3 = D(11, 4), D(11, 5), D(11, 6)
+
+
+# ─── F12-2：市值加權本益比 ───────────────────────────────
+def test_f122_wpe_formula():
+    rows = [(d3, "TWSE", "A", 20.0, 300.0), (d3, "TWSE", "B", 10.0, 100.0),
+            (d3, "TWSE", "C", None, 50.0), (d3, "TWSE", "D", 0.0, 30.0), (d3, "TWSE", "E", -5.0, 20.0),   # 空白、0、負 → 不計入
+            (d3, "TWSE", "F", 15.0, None), (d3, "TWSE", "G", 15.0, 0.0)]                                # 沒有市值 → 全部不算
+    r = export.market_wpe(rows, [d3])["TWSE"]
+    v = 400 / (300 / 20 + 100 / 10)                                                                     # 16.0
+    assert r == {"v": round(v, 2), "p": 100.0, "lo": 16.0, "hi": 16.0, "cov": round(400 / 500 * 100, 1), "t": ["A", 75.0]}
+
+
+def test_f122_wpe_position_and_markets():
+    rows = [(d1, "TWSE", "A", 10.0, 100.0), (d2, "TWSE", "A", 20.0, 100.0), (d3, "TWSE", "A", 15.0, 100.0),
+            (d3, "TPEx", "X", 30.0, 10.0), (D(10, 1), "TWSE", "A", 99.0, 100.0)]                          # 窗口外略過
+    out = export.market_wpe(rows, [d1, d2, d3])
+    assert out["TWSE"] == {"v": 15.0, "p": round(2 / 3 * 100, 1), "lo": 10.0, "hi": 20.0, "cov": 100.0, "t": ["A", 100.0]}
+    assert out["TPEx"]["v"] == 30.0 and out["TPEx"]["p"] == 100.0
+    assert export.market_wpe([], [d3]) == {}                                                           # 沒有資料 → 不輸出
+    assert export.market_wpe([(d3, "TWSE", "A", None, 100.0)], [d3]) == {}                              # 全部虧損 → 不輸出
+    # 某天全部虧損：那天跳過，不當成 0
+    out = export.market_wpe([(d1, "TWSE", "A", 10.0, 1.0), (d2, "TWSE", "A", None, 1.0)], [d1, d2])
+    assert out["TWSE"]["v"] == 10.0 and out["TWSE"]["lo"] == out["TWSE"]["hi"] == 10.0
+
+
+def test_f122_wpe_export_source():
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert "LEFT JOIN daily_prices p ON p.stock_id" in src and 'mv[m]["wpe"]' in src
+
+
+# ─── F12-3：ETF 借券 ───────────────────────────────────
+def test_f123_etf_block():
+    latest = {"TWSE": (d3, [("0050", "元大台灣50", 60.0, 0.5, 1000000, 6e8), ("0056", "高股息", 35.0, 0, 0, 0)])}
+    e = export.etf_block(latest, {"0050": (100, 110, 5, 4)}, {"0050": (5000000, 6500400)})
+    r = e["rows"]["0050"]
+    assert r["lb"] == 6500 and r["l1"] == 1500 and r["mb"] == 110
+    assert "lb" not in e["rows"]["0056"] and "l1" not in e["rows"]["0056"]                             # 沒有借券列 → 不輸出
+    assert export.etf_block(latest, {}) == export.etf_block(latest, {}, None)                           # 舊呼叫相容
+    m = export.market_sbl([d3], {d3: [(5000000, 6500400), (1000, 0)]})
+    assert m == {"d": "2026-11-06", "lb": 6500, "l1": 1499, "n": 2}                                    # 先合計股數再換張
+
+
+def test_f123_export_source():
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert "def _load_etf_sbl(cur)" in src and '"sbl_etf"' in src
+
+
+# ─── F12-4：市值、週轉率 ───────────────────────────────
+def test_f124_cap_turnover():
+    assert export.cap_turnover(1000.0, 11094000, 25932370067) == (259323.7, 0.04)
+    assert export.cap_turnover(10.0, 5000000, 10000000) == (1.0, 50.0)
+    assert export.cap_turnover(10.0, None, 10000000) == (1.0, None)                                    # 今天沒有成交資料
+    assert export.cap_turnover(None, 5, 10) == (None, 50.0)
+    assert export.cap_turnover(10.0, 5, None) == (None, None) == export.cap_turnover(10.0, 5, 0)       # 沒有股數
+    assert set(export.SCREEN_KEYS) >= {"mc", "to"}
+
+
+# ─── 網站（原始碼檢查）───────────────────────────────────
+def test_f12_site():
+    js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+    assert "右側刻度只適用融資；融券、借券各自縮放" in js                                                    # F12-1 P26
+    assert "...mtCards, ...mgCards, ...slCards" in js and "MT?.mc == null ? '--'" in js                   # F12-4
+    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+    assert "function wpeLine(V)" in app and "${wpeLine(V)}" in app and "不是證交所公布的數字" in app            # F12-2
+    assert "function etfSblLine(B)" in app and "${etfSblLine(L.sbl_etf)}" in app and "不等於看空" in app      # F12-3
+    assert "<th>借券餘額</th><th>借券增減</th>" in app and "['l1+', '借券增加', -1]" in app
+    assert "['to', '週轉率', 'to', -1, 'x']" in app and "'rs20', 'to']]" in app and "to: ['to', 'mc']" in app
+    assert "{ id: 'mc', g: '流動性'" in app and "{ id: 'to', g: '流動性'" in app
+    assert "'lb', 'lp', 'mc', 'to'].includes(k)" in app
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
diff -ruN -x __pycache__ orig/twstock/export.py proj/twstock/export.py
--- orig/twstock/export.py	2026-11-07 00:56:37
+++ proj/twstock/export.py	2026-11-07 22:57:18
@@ -46,7 +46,7 @@
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
-               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp")
+               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp", "mc", "to")
 VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
 VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
 VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
@@ -265,6 +265,36 @@
     return out
 
 
+def market_wpe(rows, days):
+    """
+    第 12 輪 A10-延伸：市值加權本益比 = Σ 市值 ÷ Σ（市值 ÷ 本益比），只計本益比 > 0、有市值（收盤 × 目前股數）的股票。
+    rows = [(日期, 市場, 代號, 本益比, 市值)]（float 或 None）；days = 窗口日期（舊到新，同 market_valuation）。
+    回傳 {市場: {v, p 位置 %（1 位）, lo, hi, cov 計入市值占比 %（1 位）, t: [最大市值代號, 占計入市值 %（1 位）]}}；某市場沒有資料 → 不輸出。
+    """
+    per = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0, None]))    # 全部市值、計入市值、Σ 市值÷本益比、(最大市值, 代號)
+    window = set(days)
+    for d, m, code, pe, cap in rows:
+        if d not in window or not cap or cap <= 0:
+            continue
+        b = per[m][d]
+        b[0] += cap
+        if pe is not None and pe > 0:
+            b[1] += cap
+            b[2] += cap / pe
+            if b[3] is None or cap > b[3][0]:
+                b[3] = (cap, code)
+    out = {}
+    for m, by_day in per.items():
+        ds = [d for d in days if by_day.get(d) and by_day[d][2] > 0]
+        if not ds:
+            continue
+        s = [by_day[d][1] / by_day[d][2] for d in ds]
+        b = by_day[ds[-1]]
+        out[m] = {"v": round(s[-1], 2), "p": round(position(s, s[-1]), 1), "lo": round(min(s), 2), "hi": round(max(s), 2),
+                  "cov": round(b[1] / b[0] * 100, 1), "t": [b[3][1], round(b[3][0] / b[1] * 100, 1)]}
+    return out
+
+
 def stock_valuation(series, today):
     """
     B7：series = {"pe"|"pb"|"dy": [窗口內 > 0 的值]}；today = {"pe", "pb", "dy": 窗口最後一天的值（可為 None）}。
@@ -279,24 +309,36 @@
     return out or None
 
 
-def _load_valuation(cur):
-    """讀窗口內的 stock_fundamentals（約 47 萬列）→ (市場估值, {代號: 個股估值}, 窗口最後一天)。"""
+def _load_valuation(cur, shares=None):
+    """
+    讀窗口內的 stock_fundamentals（約 47 萬列）→ (市場估值, {代號: 個股估值}, 窗口最後一天)。
+    第 12 輪：同一個查詢多讀當天收盤，乘 shares（{代號: 目前股數}）得市值，市場估值加 wpe（市值加權本益比）。
+    """
     days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {VAL_DAYS} trade_date FROM stock_fundamentals ORDER BY trade_date DESC")][::-1]
     if not days:
         return None, {}, None
     f = lambda x: None if x is None else float(x)
-    mrows, series, today = [], defaultdict(lambda: {"pe": [], "pb": [], "dy": []}), {}
-    for d, m, code, pe, pb, dy in cur.execute("""
-        SELECT f.trade_date, s.market_type, s.stock_code, f.pe_ratio, f.pb_ratio, f.dividend_yield
-        FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id WHERE f.trade_date BETWEEN ? AND ?""", days[0], days[-1]):
+    mrows, wrows, series, today = [], [], defaultdict(lambda: {"pe": [], "pb": [], "dy": []}), {}
+    shares = shares or {}
+    for d, m, code, pe, pb, dy, close in cur.execute("""
+        SELECT f.trade_date, s.market_type, s.stock_code, f.pe_ratio, f.pb_ratio, f.dividend_yield, p.close_price
+        FROM stock_fundamentals f JOIN stocks s ON s.stock_id = f.stock_id
+        LEFT JOIN daily_prices p ON p.stock_id = f.stock_id AND p.trade_date = f.trade_date
+        WHERE f.trade_date BETWEEN ? AND ?""", days[0], days[-1]):
         pe, pb, dy = f(pe), f(pb), f(dy)
         mrows.append((d, m, pe, pb, dy))
+        if close is not None and shares.get(code):
+            wrows.append((d, m, code, pe, float(close) * shares[code]))
         for k, v in (("pe", pe), ("pb", pb), ("dy", dy)):
             if v is not None and v > 0:
                 series[code][k].append(v)
         if d == days[-1]:
             today[code] = {"pe": pe, "pb": pb, "dy": dy}
-    return market_valuation(mrows, days) or None, {c: stock_valuation(series[c], today.get(c, {})) for c in series}, days[-1]
+    mv = market_valuation(mrows, days)
+    for m, w in market_wpe(wrows, days).items():          # 第 12 輪
+        if m in mv:
+            mv[m]["wpe"] = w
+    return mv or None, {c: stock_valuation(series[c], today.get(c, {})) for c in series}, days[-1]
 
 
 # ─── 融資融券（B2＋A4）與 ETF（E1）────────────────────────
@@ -403,6 +445,15 @@
     return mg
 
 
+# ─── 市值、週轉率（第 12 輪 B11；目前股數）────────────────────
+def cap_turnover(close, volume, shares):
+    """(市值 億元（1 位）, 週轉率 % = 成交股數 ÷ 股數 × 100（2 位）)；沒有股數 → (None, None)；沒有收盤 → 市值 None；成交量 None → 週轉率 None。"""
+    if not shares:
+        return None, None
+    return (None if close is None else round(float(close) * shares / YI, 1),
+            None if volume is None else round(volume / shares * 100, 2))
+
+
 # ─── 借券賣出（第 11 輪 B14；資料庫存股，匯出一律換成張）────────────
 def lots(shares):
     """股 → 張（四捨五入到整數，half-up；None 照傳）。"""
@@ -441,6 +492,19 @@
     return {"d": str(d), "lb": lots(bal), "l1": lots(bal - prev), "n": len(R)}
 
 
+def _load_etf_sbl(cur):
+    """第 12 輪：ETF 借券，各市場最新借券日 → ({市場: 日期}, {代號: (前日餘額, 餘額)}（股）)。"""
+    by_m = defaultdict(dict)
+    for code, m, d, prev, bal in cur.execute("""
+        SELECT e.etf_code, e.market_type, x.trade_date, x.sbl_prev, x.sbl_balance
+        FROM etf_sbl x JOIN etfs e ON e.etf_id = x.etf_id
+        WHERE x.trade_date = (SELECT MAX(y.trade_date) FROM etf_sbl y JOIN etfs z ON z.etf_id = y.etf_id
+                              WHERE z.market_type = e.market_type)"""):
+        by_m[m][code] = (d, prev, bal)
+    dates = {m: next(iter(v.values()))[0] for m, v in by_m.items()}
+    return dates, {c: (p, b) for v in by_m.values() for c, (_, p, b) in v.items()}, by_m
+
+
 def _load_sbl(cur):
     """(各市場借券日期（舊到新，最近 6 天）, 各市場最新日的 [(前日, 餘額)], 個股 {代號: {日期: (前日, 餘額, 限額, 備註)}}（完整歷史）)。"""
     per_stock, by_m = defaultdict(dict), defaultdict(lambda: defaultdict(list))
@@ -526,8 +590,11 @@
     return px, latest
 
 
-def etf_block(latest, margin_rows):
-    """latest.json 的 etfs。margin_rows：{代號: (融資前日, 融資餘額, 融券前日, 融券餘額)}（該市場最新融資融券日）。"""
+def etf_block(latest, margin_rows, sbl_rows=None):
+    """
+    latest.json 的 etfs。margin_rows：{代號: (融資前日, 融資餘額, 融券前日, 融券餘額)}（該市場最新融資融券日）。
+    第 12 輪：sbl_rows：{代號: (借券前日餘額, 借券餘額)}（股，該市場最新借券日）→ lb、l1（張）。
+    """
     if not latest:
         return None
     rows = {}
@@ -538,6 +605,9 @@
             mg = margin_rows.get(code)
             if mg:
                 r.update(mb=mg[1], m1=mg[1] - mg[0], sb=mg[3], s1=mg[3] - mg[2])
+            sl = (sbl_rows or {}).get(code)
+            if sl:
+                r.update(lb=lots(sl[1]), l1=lots(sl[1] - sl[0]))
             rows[code] = r
     return {"dates": {m: str(d) for m, (d, _) in latest.items()}, "rows": rows}
 
@@ -1039,9 +1109,10 @@
     # 寬度輸出 BREADTH_DAYS 天，前面多 60 天給 MA60
     b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
     status = build_status(cur, latest_date, now)
-    valuation, stock_val, val_date = _load_valuation(cur)      # F9-4
+    valuation, stock_val, val_date = _load_valuation(cur, shares)      # F9-4；第 12 輪加 wpe
     fin, fin_meta, fin_counts = _load_financials(cur)          # 第 10 輪 B5
     sdates, srecent, sper = _load_sbl(cur)                     # 第 11 輪 B14
+    edates, esbl, esbl_m = _load_etf_sbl(cur)                  # 第 12 輪 ETF 借券
     conn.close()
     mlast = {m: ds[-1] for m, ds in mdates.items()}
     m5 = {m: ds[-6] if len(ds) >= 6 else None for m, ds in mdates.items()}
@@ -1100,6 +1171,9 @@
         mk_ = info["market"]
         sbl = stock_sbl(srows, slast.get(mk_), s5.get(mk_), shares.get(code),
                         (mrows.get(slast.get(mk_)) or (None,) * 5)[4], conv)
+        # 第 12 輪 B11：最新收盤（無成交日用最後一個收盤）× 目前股數；週轉率只在最後一根是資料日時計算
+        lc = next((x for x in reversed(c) if x is not None), None)
+        mc, to = cap_turnover(lc, v[-1] if d_[-1] == latest_date else None, shares.get(code))
         act = None
         if code in act_lots and dates[-1] in d_ and tn[d_.index(dates[-1])] is not None:
             t_lots = round(tn[d_.index(dates[-1])] / 1000)
@@ -1127,6 +1201,7 @@
                if info["market"] in mlast else {}),
             **({"active": active[code]} if code in active else {}),
             **({"sbl": sbl} if sbl else {}),                                     # 第 11 輪 B14：該股最新借券日沒有列 → 不輸出
+            **({"mt": {"d": str(latest_date), "mc": mc, "to": to}} if mc is not None else {}),   # 第 12 輪 B11
             **({"mg": mg} if mg else {}),
             **({"act": act} if act else {}),
         })
@@ -1207,7 +1282,8 @@
                         **screen_margin(mrows, mlast.get(mkt), m5.get(mkt), conv, mkt),
                         "pbp": (stock_val.get(code) or {}).get("pb", [None])[0],     # F9-4：淨值比一年位置（cap 由前端估值規則排除）
                         **fin_screen(fin.get(code)),                                  # 第 10 輪 B5
-                        **{k: (sbl or {}).get(k) for k in ("lb", "l1", "l5", "lp")}}   # 第 11 輪 B14
+                        **{k: (sbl or {}).get(k) for k in ("lb", "l1", "l5", "lp")},   # 第 11 輪 B14
+                        "mc": mc, "to": to}                                               # 第 12 輪 B11
 
     industries = defaultdict(list)
     for code in snapshot:
@@ -1245,7 +1321,8 @@
         "forecast": forecast,
         "margin": margin,
         "sbl": {m: market_sbl(sdates[m], srecent[m]) for m in ("TWSE", "TPEx") if sdates.get(m)} or None,   # 第 11 輪 B14
-        "etfs": etf_block(etf_latest, etf_margin_rows),
+        "sbl_etf": {m: market_sbl([d], {d: [(p, b) for _, p, b in esbl_m[m].values()]}) for m, d in edates.items()} or None,   # 第 12 輪
+        "etfs": etf_block(etf_latest, etf_margin_rows, esbl),
         "holdings": {code: {"d": str(hd[-1]), "n": etf_names[code][0],
                             **({"u1": u} if (u := unit_change(hs, hd)) is not None else {})}
                      for code, (hd, hs, _) in holdings.items()},
```
