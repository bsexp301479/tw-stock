# 第 23 輪｜System Analyst：F23-1 近期表現、F23-2 稅後淨利率、F23-3 版本參數、F23-4 小修 5 項設計

- 撰寫日期：2026-11-14（週六）
- 依據：
  - `23/02-pm.md`：範圍、驗收條件、第五節 5-2 的 18 項舊斷言、第六節提示、D35 預設。
  - `23/01-analyst.md`：口徑、實例、做法評估。
  - 使用者決定：範圍 F23-1、F23-2、F23-3、F23-4a～e；**D34-1～D34-14 = A**；**D35-1～D35-6 照 PM 預設**。
- 原型作業：
  - 在 scratchpad 的 `sa23/` 建兩份專案副本：
    - `orig` = 目前工作目錄（`59fe6ea`，除了 `docs/iterations/23/` 沒有變更）。
    - `proj` = 本設計。
    - 兩份都**不含 `.env`**、`_archive`、`logs`、`.git`；`site/data` 由各自的 `export` 產生。
  - 唯讀模擬匯出：`orig`、`proj` 各執行一次 `export`，只執行 SELECT，輸出寫到各自的 `site/data`（scratchpad）。
    - **沒有寫專案的 `site/data`。**
    - 帳密由 `sa23/dbenv.py` 以 setdefault 把專案 `.env` 讀進環境變數，沒有印出或複製 `.env`。
  - 8001 預覽：在 `proj` 執行 `python3 -m twstock serve --port 8001 --no-browser`（同時驗證 `Cache-Control`），結束時已關閉；8000 沒有碰。
    - 預覽前 localStorage 沒有任何鍵；預覽時新增的 `tw.kmode`、`tw.stockTab`，以及暫時寫入的 `tw.watch`（`0050`、`00981A`；`2330`、`0050`）都已刪除，**結束時 0 個鍵**。
    - 改前、改後對照：預覽期間把 `orig` 的 4 個網站檔暫放在 `proj/site/old/`（`data` 用符號連結），看完已刪除。
    - 視窗已恢復 desktop 大小，分頁已關閉。
  - **外部請求 0 次、資料庫寫入 0 次**。前後查 `collect_runs`：最大 17，沒有進行中的收集。
  - 沒有修改專案程式，沒有 commit。
- 基線：資料日 **2026-11-13（週五）**；`latest.stocks` 1,985 檔；`stocks/` 1,999 個檔。

---

## 〇、變更總覽

| 檔案 | 內容 | ＋／− |
|---|---|---|
| `twstock/export.py` | `PF_DAYS`；抽出 `period_return`、`index_return`（`price_stats` 改呼叫它們，參數、回傳不變）；新增 `stock_perf`；`fin_stock` 加 `nm`；`p_days`；個股檔加 `pf` | ＋43／−8 |
| `twstock/__main__.py` | `cmd_serve` 的 `Handler` 在 `end_headers` 加 `Cache-Control: no-cache` | ＋7／−1 |
| `site/stock.js` | `PF_NAME`、`perfHTML`；走勢分頁插入近期表現；季報卡「稅後淨利率」與說明一句；週／月 K 標記 `mkPos`；「近期新訊號 →」 | ＋22／−4 |
| `site/app.js` | `streakTxt` 30 加「+」；新訊號表名稱格加 `hl-sub`；自選頁只有 ETF 時合併標題 | ＋5／−4 |
| `site/app.css` | `.hl-sub`、`.pf-tbl` 與 ≤ 480 px 規則 | ＋2 |
| `site/index.html` | 3 個引用加 `?v=` | ＋3／−3 |
| `README.md` | `serve` 一行、近期表現一段、季報卡一句、網站更新與快取一段 | ＋4／−2 |
| `tests/test_iter20.py`、`tests/test_iter22.py` | PM 5-2 第 1、2 項，各改 1 行 | ＋2／−2 |
| `tests/test_iter23.py`（新） | 14 個測試 | 353 行 |

- 程式＋README **＋86／−22**（PM 估約 80，上限 95）。
- 不動：`collectors/`、`catchup.py`、`health.py`、資料表。
- 輸出：
  - `latest.json`、`screen.json`、`etfp/`、`etfs/` 和改前**逐位元組相同**。
  - `stocks/` 只多 `pf` 和 `fin.nm`；刪掉這兩個鍵後**逐位元組相同**。

---

## 一、F23-1 個股頁近期表現

### 1-1 口徑

| 項目 | 規則 |
|---|---|
| 本股報酬 | `period_return(d_, adj, lc, b)` = 最後成交的還原收盤 `lc` ÷ 基準日 `b`（含）以前最後一個有成交的還原收盤 − 1。`b` 是 None、早於該股第一個資料列、或之前沒有成交 → None。**這段就是原本 `price_stats` 迴圈內的寫法，原樣抽出**，`price_stats` 改呼叫它 |
| 指數報酬 | `index_return(idx, b, last)` = 資料日收盤 ÷ 基準日收盤 − 1；任一天沒有指數 → None。也是 `price_stats` 原寫法抽出。上市用 `TAIEX`，上櫃用 `TPEX`（`idx_close[市場]`，選股也用它） |
| 差距 | 本股 − 指數，**用未四捨五入的值相減**，再四捨五入到 2 位（同 `rs20`、`rs60`）。所以 `pf` 要另存差距：2330 52 週 62.94 − 56.52 = 6.42，但正確值是 **6.41** |
| 5／20／60／120 日 | 基準日 = `days[-1-N]`，`days` = **完整交易日序列** `p_days` |
| 今年以來 `y` | 基準日 = `days` 中早於「資料日當年 1/1」的最後一天（`bisect_left`）。11/13 是 2025-12-31 |
| 52 週 `w` | 基準日 = `days` 中 ≤ `w52_start`（資料日 − 365 天）的最後一天（`bisect_right`），和 52 週高低的起點同一天。11/13 是 2025-11-13 |
| 上市以來 `s` | 6 個區間中**任一個本股是 None** 時才加；基準日 = 該股第一個**有成交**的日子，報酬從那天收盤起算。上市寫「上市以來」、上櫃寫「上櫃以來」 |

- **完整交易日序列**：`p_days = sorted({r[0] for rows in prices.values() for r in rows})`。
  - `prices` 就是 `daily_prices` 全部列（inner join `stocks`，每列都有對應），所以等於 `SELECT DISTINCT trade_date FROM daily_prices`，不另外打 SQL。
  - `b_days` 不動（市場寬度、新訊號照舊用 120 天）。原型確認 `p_days[-120:] == b_days`：5／20／60 日的基準日兩邊相同，所以和選股逐值相同。
  - 只用 `b_days` 時 120 日的 `len(days) > 120` 不成立 → None（`test_perf_full` 有這個反例）。
- **指數不含股息**：加權、櫃買指數是價格指數；個股還原價含股息。長區間的差距偏向個股，大約差期間的殖利率（2330 今年以來約 1.35 個百分點）。畫面短句直接寫出（D34-2 = A）。
- **事件日剛好是基準日（6488）**：`_adj_factors` 事件當天與之後的係數是 1，所以基準是 2025-12-31 的實際收盤，那次除息不算進今年。不需要特別處理，`test_perf_event_and_year` 驗證。
- **區間內沒有成交（4406）**：照算（D35-2）。最後成交 11/05 早於 5 日基準日 11/06，`base` = 11/05 收盤 = `lc`，5 日 = 0.00%；指數照算到 11/13，差距 = −12.63。和 `screen.json` 的 `r5` = 0.0 相同。
- **停牌、下市**：最後一列不是資料日，或從沒有成交 → **不輸出 `pf`**，條件和 `latest.stocks` 相同（`d_[-1] == latest_date and any(c)`）。
  - 個股檔在 `if d_[-1] != latest_date: continue` 之前寫，所以條件寫在 `pf` 那一行。
- **ETF**：`etfp/` 由 `etf_export` 產生，不經過這段，沒有 `pf`（D34-5）。

### 1-2 為什麼只加「上市以來」不判斷是否真的新上市（D35-5 抽查）

- 80 檔第一個成交日晚於 52 週基準日（和 PM 相同）。資料庫 `stocks.listed_date` **1,999 筆全是 NULL**，本站沒有上市日。
- 抽查結果：
  - 多數是新上市（櫃）：上市股第一天官方漲跌都是 0（不比價）；上櫃股第一天漲跌相對承銷價（例 7828 +932）。
  - 可能不是新上市的：
    - 3718 中光電投控（9/03 起；轉換控股，舊歷史在 5371）。
    - 7819 精誠金融（5/27 起；推測是分割新設）。
    - **8291 尚茂**（2/25 起）：第一天只成交 15 張，低於它自己的成交量中位數 29 張；80 檔中只有這一檔。推測是復牌，**本站無法確認（0 請求）**。
- 判斷方式沒有可靠的資料，寫死例外代號又會過時。所以本設計**不另做判斷**，改在收合說明寫：
  > 上市以來從本站第一個成交日 YYYY-MM-DD 的收盤起算，不是承銷價（本站日線從 2025-10-30 起，復牌或轉換為控股公司的股票也從第一個成交日起算）。
- 這是對 D35-5 的調整（第十節第 2 項）。

### 1-3 匯出：`stocks/{代號}.json` 的 `pf`

```json
"pf": [[5, "2026-11-06", 7.2, 10.01, -2.81], [20, "2026-10-14", -21.64, -10.18, -11.46], [60, "2026-08-14", -8.22, -4.66, -3.56],
       [120, "2026-05-20", -3.11, 9.13, -12.25], ["y", "2025-12-31", -13.06, 50.79, -63.86], ["w", "2025-11-13", -24.17, 56.52, -80.69]]
```

- 每列 `[區間, 基準日, 本股 %, 指數 %, 差距（百分點）]`；區間是 `5`、`20`、`60`、`120`、`"y"`、`"w"`，必要時最後加 `"s"`。
- 本股算不出時，本股、指數、差距**三個都是 null**（畫面三格都寫「--」）。
- 本股有值、但基準日沒有指數時：指數、差距是 null，本股照列（目前資料不會發生）。
- 放在個股檔最後一個鍵（`act` 之後），刪掉後檔案和改前逐位元組相同。

### 1-4 11/13 原型結果（`sa23/cmp.py`，附錄 B）

| 股票 | 結果 | PM 驗收 |
|---|---|---|
| 2421 | 見 1-3，欄名「加權指數」 | #1 全部相同 |
| 2330 | 5 日 +10.07／+10.01／+0.06；20 日 −5.62／−10.18／+4.56；60 日 −1.59／−4.66／+3.07；120 日 +8.16／+9.13／−0.97；今年以來 +52.96／+50.79／+2.17；52 週 +62.94／+56.52／**+6.41** | #2 相同 |
| 6488 | 欄名「櫃買指數」；5 日 +23.05／+12.63／+10.42 … 今年以來 **+55.77／+23.95**／+31.82；52 週 +63.79／+31.54／+32.25 | #3 相同 |
| 6947 | 5 日 −1.45／+10.01／−11.46；20 日 −10.53／−10.18／−0.35；60 日 −14.68／−4.66／−10.02；120 日、今年以來、52 週「--」；「上市以來 07/23 起」**−21.42／−2.62／−18.80** | #4 相同（日期格式見第十節第 3 項） |
| 7827 | 120 日「--」；上市以來（05/29 起）−12.77／−2.36／−10.41 | #5 相同 |
| 3454、6747、3714、1808 | 沒有 `pf`、沒有區塊、不留空白（8001 確認 3454） | #6 相同；14 檔都沒有 |
| 4406 | 表頭「至 11/13，本股最後成交 11/05」；5 日 0.00%／+12.63%／−12.63 | #7 相同 |
| 全市場 | `pf` 的 5／20／60 日 = `r5`、`r20`、`r60`；20／60 日差距 = `rs20`、`rs60`：**1,985 檔 0 差異** | #8 |
| 檔數 | 有 `pf` 1,985 = `latest.stocks`；本股缺值：5 日 0、20 日 8、60 日 14、120 日 28、今年以來 58、52 週 80；「上市以來」列 80 | #9 全部相同 |
| ETF | `#/stock/0050`、`#/stock/00981A` 沒有區塊；`etfp/` 逐位元組相同 | #10 |

---

## 二、F23-2 季報卡稅後淨利率

### 2-1 口徑

- 單季稅後淨利率 = `fin_margin(s[3], s[0])`：`fin_single` 相減後的單季淨利（`net_income`，歸屬母公司業主）÷ 單季營收，ROUND_HALF_UP 到 1 位。
  - 營收 ≤ 0 或 NULL、淨利 NULL、上一季缺（單季為 None）→ null。
  - 極端值照實（D34-8 = A）：3521 型 −41,186.5%。
- 只有一般業（D34-7 = A）：`fin.t == "ci"` 才輸出。

### 2-2 匯出：`fin.nm`（D35-1）

- `fin_stock` 回傳多一個鍵 `nm` = 和 `q` 等長、逐季對齊的淨利率陣列。
  - 例 2421：`"nm": [11.3, 11.3, 8.0, 14.1, 12.7, 12.9, 12.7, 14.6]`。
- **非一般業不輸出這個鍵**（PM 留給 SA 定）：檔案小，畫面用「有沒有 `nm`」判斷。
- `q` 的列、`c` 都不變（`test_iter10` 第 167～169 行、`test_iter15` 第 39 行照舊通過）。

### 2-3 畫面

- `renderFin` 在營益率之後加卡：「稅後淨利率 14.6%」，副行「去年同季 14.1%」。
  - 條件 `F.t === 'ci' && F.nm`：舊 JSON（沒有 `nm`）和金融業都不顯示。
  - 去年同季：`F.nm[Q.indexOf(base)]`，`base` 不在近 8 季內 → `--`。
  - 一般業但最新一季是 null（8 檔）→ 卡片寫「--」（PM 建議）。
- 說明（收合內文）在「金融業沒有毛利率。」後面加一句：
  > 稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。

  原有句子逐字保留；仍是同一個 `noteHTML` 字面呼叫，數量不變。

### 2-4 11/13 原型結果

| 股票 | 結果 | PM |
|---|---|---|
| 2421 | 14.6%（去年同季 14.1%）；1024 寬 3＋3 排 | #1 |
| 2330 | 51.1%（45.7%） | #2 |
| 6488 | 10.1%（13.6%）；`nm` 中 26Q2 是 24.8% | #3 |
| 6947 | 26Q2 18.2%，去年同季「--」（尚未收錄 26Q3） | #4 |
| 2881、2801 | 沒有卡（3 張卡） | #5 |
| 檔數 | 一般業有 `nm` 1,944 檔（含停牌 5 檔）；全部 1,944 檔最新一季有值 1,936、null 8、超過 ±100% 88；其中在 `latest.stocks` 的 1,939 檔有值 **1,931**、null 8、超過 ±100% 87（QA 後更正，見 `05-qa.md` 第七節） | #7：PM 約 1,939 指的是一般業檔數 |

---

## 三、F23-3 版本參數與 `serve` 快取標頭

### 3-1 雜湊

- 演算法：**檔案位元組的 SHA-1，取前 8 個十六進位字元**。
  - QA 驗算：`shasum site/app.js | cut -c1-8`（macOS 內建，預設 SHA-1）。
  - 只看檔案內容，和時間、git 無關；同一份內容在任何機器都得到同一個值。
- `index.html` 第 9、12、13 行：`app.css?v=xxxxxxxx`、`app.js?v=xxxxxxxx`、`stock.js?v=xxxxxxxx`。CDN 兩行不動。
- 原型的值（PG 套用附錄 A 後必然相同，因為內容相同）：`app.css` `52d5a6c7`、`app.js` `b1f56347`、`stock.js` `aaba2021`。

### 3-2 誰更新 `index.html`：評估

| 做法 | 內容 | 簡單 | 不會忘 | 結論 |
|---|---|---|---|---|
| **A 手動＋測試（採用）** | PG 改完 js／css 後，照測試失敗訊息印出的 3 行貼上 | 0 行執行期程式 | `test_iter23.test_version_hash` 每輪必跑，不一致就失敗並印出正確的 3 行 | **最簡單**；QA 第一步也是跑測試，漏改一定會被擋 |
| B `export` 時寫入 | 每次匯出算雜湊並改寫 `index.html` | 約 10 行 | PG 改程式後不一定會匯出；每晚排程會去寫受版控的檔 | 不採用（PM 範圍外；`export` 責任擴大） |
| C 另一個指令（如 `twstock stamp`） | 指令算雜湊並改寫 | 約 10 行＋說明 | 一樣要記得執行，仍然需要測試來擋 | 不採用：多一個指令，沒有比 A 更不會忘 |
| D `serve` 回應時動態替換 | `serve` 讀 `index.html` 時代入雜湊 | 約 10 行 | 不用記 | 不採用：只對 `serve` 有效；而 `serve` 加了 `no-cache` 後本來就會拿到新檔，反而是其他主機需要的版本參數會失效 |
| E 測試自動改寫檔案 | 不一致時測試直接寫回 | 約 3 行 | 不用記 | 不採用：測試修改原始碼不合預期，QA 跑測試也會改到檔 |

- 補充：**`no-cache` 才是本機的主要保護**。即使漏改版本參數，`serve` 也會讓瀏覽器每次確認，`Last-Modified` 變了就回 200。版本參數是給日後換靜態主機時用，也讓 QA 能從網址看出載入的是哪一版。
- 測試失敗訊息（原樣）：

  ```
  AssertionError: site/index.html 的版本參數和檔案內容不符（改了 js／css 要更新），請把這 3 行換成：
  <link rel="stylesheet" href="app.css?v=52d5a6c7">
  <script src="app.js?v=b1f56347" defer></script>
  <script src="stock.js?v=aaba2021" defer></script>
  ```

### 3-3 `serve` 加 `Cache-Control: no-cache`（D35-6：所有回應）

- 寫法：在 `cmd_serve` 內定義 `Handler(SimpleHTTPRequestHandler)`，覆寫 `end_headers`，先 `send_header("Cache-Control", "no-cache")` 再呼叫父類別。
  - 200、304、404 都會帶這個標頭。
  - Python 3.13 的 `send_head` 已處理 `If-Modified-Since`，檔案沒改回 304。
  - 埠被占用的提示、`--no-browser`、`handle_error` 不變。
- 8001 實測：
  - `curl -sI /`、`/data/latest.json` 都有 `Cache-Control: no-cache`。
  - `If-Modified-Since: <Last-Modified>` 的 `/app.js?v=…` 回 **304**。
  - 瀏覽器：第一次載入後改 `app.css`（加 `.pf-tbl` 寬度上限）並更新 `?v=`，**一般重新整理**：
    - `app.css?v=52d5a6c7` `transferSize` 18,543（新檔）。
    - `app.js`、`stock.js` 伺服器紀錄 **304**（`transferSize` 300）。
    - `index.html` 200。

---

## 四、F23-4 小修 5 項

| # | 改法 | 原型結果 |
|---|---|---|
| **4a** 375 寬新訊號標籤 | 名稱格多一個 `<div class="hl-sub">`（同一串 `hlTag`），標籤欄照舊輸出。CSS：平常 `.hl-sub{display:none}`；`@media (max-width:480px)` 時隱藏 `th.hl-th`、`td.hl-tags`，顯示 `.hl-sub`（`white-space:normal`），並把 `.tbl .nm span` 的灰色小字改回標籤樣式 | 375 深色：標籤在名稱下方每行一個，整個可讀，0 個超出名稱格；「投信 5 日買超 ≥ 成交額 5%」較長，日期換到下一行。**表格 421 px**（容器 309 px，仍要橫捲，但小於改前 577 px）。1024：標籤欄照舊、`.hl-sub` 不顯示。每列只看得到一次 |
| **4b** 週／月 K 標記 | `const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' }`，事件標記與 ETF `gx` 都用 `...mkPos`（D35-3）。文字式子不動 | 375 深色截圖比較見下。**有改善，採用 A** |
| **4c** 自選頁只有 ETF | 只有 ETF 時：標題 `<h2>自選 ETF</h2>`，說明「存在這個瀏覽器裡，換裝置不會同步。當日行情；成交量為張、成交額為億元」，下面直接接 ETF 表，不輸出第二個 `sec-h`。其他三種情況的 HTML 不變（`<h2>自選</h2>`、`<h2>ETF</h2>` 字面留在 `stk` 分支） | 375 深色：只有一個標題，兩句說明都看得到；股票＋ETF 仍是兩個標題 |
| **4d** 排行「買30」 | `streakTxt`：`Math.abs(v) >= 30` 時加「+」 | 自選表 2330「投信連」寫「買30+」；排行、選股用同一個函式；排序用數值，不變 |
| **4e** 「近期新訊號 →」 | `<a class="muted small" href="#/rank/hl">近期新訊號 →</a>`，和「看排行 →」同寫法 | 3661（375 深色）：連結 rgb(167,167,167)、12 px，標籤 rgb(236,236,236)，看得出差別 |

- 4b 截圖（`sa23/shots/`）：
  - 2421 週 K：
    - 改前：「2/24 現增」被相鄰 K 棒蓋住大半，「6/10 息」被 K 棒實體壓住。
    - 改後：「2/24 現增」完整；「6/10 息」只有一根細上影線穿過。
  - 6186 週 K：
    - 改前：「8/6 息」「8/26 現增」都和下跌的 K 棒重疊。
    - 改後：「8/6 息」完整；「8/26 現增」的「8/」被一根 K 棒實體壓到一小部分。
  - 日 K 位置不變。

---

## 五、匯出 JSON 的變更

| 檔案 | 變更 | 大小 |
|---|---|---|
| `stocks/{代號}.json` | 1,985 檔加 `pf`；一般業 1,944 檔的 `fin` 加 `nm` | 36,187,469 → 36,728,446 bytes（**＋528.3 KB**，＋1.5%；`pf` 約 442 KB、`nm` 約 86 KB；每檔約＋273 bytes） |
| `latest.json`、`screen.json`、`etfp/`、`etfs/` | 不變（逐位元組相同） | — |

- PM 估 `stocks/` 約＋240 KB（每檔 120 bytes）；實際較大，因為多存了基準日與差距（第十節第 1 項）。個股頁一次只載入一個檔，影響可忽略。
- 匯出時間：`orig` 25.0 秒、`proj` 25.2 秒（PM 上限＋3 秒）。
- 比對腳本 `sa23/cmp.py`（附錄 B）結果：
  - 檔案清單相同（2,373 個）；`stocks/`、`latest.json` 以外 0 檔不同；`latest.json` 去掉 `updated_at`、`status` 後相同（實際也逐位元組相同）。
  - `stocks/` 刪掉 `pf`、`nm` 後以 `_write` 的格式重新輸出：0 檔不同。
  - `pf` 和選股 0 差異；有 `pf` = `latest.stocks`；14 檔沒有 `pf`。

---

## 六、畫面（8001，`proj`）

| 頁面 | 375 深色 | 375 淺色 | 1024 淺色 |
|---|---|---|---|
| 2421 走勢 | 近期表現在 MACD 卡之後、技術面訊號之前；表 309 px、`scrollWidth` 375 | — | 表寬上限 560 px（`table.pf-tbl{max-width:560px}`，避免四欄拉到 958 px） |
| 6947 走勢 | 7 列，「上市以來」下一行小字「07/23 起」；收合說明展開可讀 | 同左，`scrollWidth` 375 | — |
| 4406、6488 | 櫃買指數欄；4406 表頭寫最後成交日；`scrollWidth` 375 | — | — |
| 3454、0050、00981A | 沒有近期表現區塊 | — | — |
| 2421、2330、6488、6947 基本面 | — | — | 季報卡 6 張，3＋3 排 |
| 2881、2801 基本面 | — | — | 3 張卡，沒有稅後淨利率 |
| 新訊號 `#/rank/hl` | 見 4a | — | 標籤欄照舊 |
| 自選（只有 ETF） | 見 4c | — | — |
| 3661 頁首 | 見 4e | — | — |

- 主控台 0 錯誤。
- 深淺色只用既有的色票（`--up`、`--dn`、`--text2`），沒有新增顏色。

---

## 七、邊界情況

| 情況 | 行為 |
|---|---|
| 120 日需要第 121 天 | 用完整交易日序列 `p_days`；`b_days`（120 天）只給寬度與新訊號 |
| 新上市（基準日早於第一個成交日） | 該區間三格「--」，最後加「上市以來／上櫃以來（MM/DD 起）」 |
| 第一個資料列沒有成交 | 「上市以來」從第一個**有成交**的日子起算 |
| 基準日剛好是第一個成交日 | 照算（例 7827 若剛好 5/20 上市，120 日有值） |
| 今天無成交 | 用最後成交收盤；表頭「本股最後成交 MM/DD」；指數照算到資料日 |
| 最後成交日 ≤ 基準日 | 照算 0.00%（D35-2，和選股相同） |
| 事件日剛好是基準日 | 基準 = 當天實際收盤（係數 1） |
| 跨年：1 月第一個交易日 | 今年以來 = 1 日報酬（基準 = 前一年最後一個交易日）；元旦休市不影響 |
| 全市場資料不到 52 週 | 52 週全部「--」，每檔都會有「上市以來」列。目前資料已滿 52 週，之後只會更長，不會再發生 |
| 基準日沒有指數 | 指數、差距「--」，本股照列 |
| 停牌、下市 | 沒有 `pf`，不顯示 |
| 復牌、轉換控股公司 | 視同新上市，從本站第一個成交日起算（1-2） |
| ETF | 沒有 `pf`，不顯示 |
| 舊 `stock.js` 讀新 JSON | 忽略 `pf`、`nm`，不出錯 |
| 新 `stock.js` 讀舊 JSON | 沒有 `pf` 不顯示區塊；沒有 `nm` 不顯示淨利率卡 |
| 淨利率：營收 ≤ 0、NULL；淨利 NULL；上一季缺 | null →「--」 |
| 淨利率：金融、其他業 | 沒有 `nm`，不顯示 |
| 淨利率極端值 | 照實顯示（全部一般業 88 檔、`latest.stocks` 內 87 檔超過 ±100%） |
| `streakTxt` | 30／−30 →「買30+」「賣30+」；29、−3 照舊；0、undefined →「--」 |
| 日 K 標記 | 位置不變 |
| 只有 ETF 的自選 | 一個標題「自選 ETF」 |
| 版本參數不一致 | `test_iter23` 失敗並印出正確的 3 行；`serve` 仍因 `no-cache` 拿到新檔 |
| 使用者的 8000 是舊程序 | 要重新啟動才會送 `no-cache`；第一次開新版時強制重新整理一次 |

---

## 八、測試（`tests/test_iter23.py`，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_perf_full` | 6 個區間的基準日（120 日 = `days[-121]`、今年以來 12/31、52 週 11/13）；沒有「上市以來」；只給 120 天時 120 日算不出、給 121 天才算得出；`export_all` 用 `p_days` |
| `test_perf_new_listing` | 6947 型（三格「--」＋「上市以來」）；7827 型（基準早 1 天「--」、剛好當天有值）；前幾列無成交 |
| `test_perf_no_trade_and_index` | 4406 型 0%；用最後成交收盤；基準日沒有指數；**差距用未四捨五入的值**（10.004 − 5.006 → 5.0，不是 4.99） |
| `test_perf_event_and_year` | 6488 型（除息日 = 基準日，18.75% 不是 25%）；新年第一個交易日的今年以來 = 1 日報酬；資料不到 52 週 |
| `test_perf_same_as_screen` | 有無成交與兩次事件的序列：`pf` 和 `price_stats`（用 120 天的 `b_days`）的 `r5`～`rs60` 相同；`price_stats` 呼叫共用函式；`pf` 不在 `SCREEN_KEYS` |
| `test_perf_export_source` | 停牌不輸出的條件、位置；`etf_export` 沒有 `pf` |
| `test_net_margin` | 2421 型 14.6%／14.1%；5 種非一般業沒有 `nm`；極端值、營收 0、營收 NULL、淨利 NULL、上一季缺；`q`、`c` 不變 |
| `test_perf_html` | node 執行 `perfHTML`：欄名、顏色、「--」、上市／上櫃以來、最後成交日、說明短句與起算日；插入位置 |
| `test_fin_card` | node 執行 `renderFin`：卡片順序（營益率之後）、舊 JSON、金融業、null、去年同季不在近 8 季；說明原句與新句 |
| `test_small_fixes` | `streakTxt` 6 例；`mkPos`；「近期新訊號 →」；新訊號名稱格與 CSS |
| `test_watch_etf_only` | node 執行 `renderWatch`：只有 ETF 一個標題、兩句說明；股票＋ETF 照舊 |
| `test_version_hash` | 3 個 `?v=` 等於 SHA-1 前 8 碼，失敗印出正確的 3 行；每個檔只引用一次；CDN 照舊 |
| `test_serve_cache` | 在 127.0.0.1 的**系統配發空埠**啟動 `twstock serve`（不用 8000、8001）：`/`、`/app.js?v=` 有 `Cache-Control: no-cache`、內容相同；`If-Modified-Since` 回 304；結束時關閉 |
| `test_no_advice_words` | 本輪新文字（`perfHTML`、`streakTxt`、淨利率、標記、頁首、新訊號區段、`renderWatch`、README 第 23 輪 4 段）不含 29 個詞（第 22 輪 17 個＋本輪 12 個） |

- 結果：
  - `proj` 的 `test_iter01`～`23` **23 個全部通過**；舊的 `test_no_advice_words`（第 18、21、22 輪）也通過。
  - 舊測試只改 PM 5-2 第 1、2 項的 2 行。
- 反證：
  - 舊程式（`orig`＋新測試檔）跑 `test_iter23`：**14 個測試全部失敗**。
  - 突變（`proj` 改一處），每一種都失敗（`sa23/mut.py`）：

    | 改動 | 失敗的測試 |
    |---|---|
    | 差距用四捨五入後的值 | `test_perf_no_trade_and_index` |
    | 120 日用 `b_days` | `test_perf_full` |
    | 不加「上市以來」 | `test_perf_new_listing`、`test_perf_event_and_year` |
    | 今年以來基準錯一天 | `test_perf_full`、`test_perf_event_and_year` |
    | 停牌也輸出 | `test_perf_export_source` |
    | 淨利率不分業別 | `test_net_margin` |
    | 淨利率用營益 | `test_net_margin` |
    | 「買30」沒有＋ | `test_small_fixes`、`test_watch_etf_only`、`test_version_hash` |
    | js 改了沒更新雜湊 | `test_version_hash` |
    | 沒有 `Cache-Control` | `test_serve_cache` |
    | 週 K 仍在下方 | `test_small_fixes`、`test_version_hash` |
    | 只有 ETF 時兩個標題 | `test_watch_etf_only`、`test_version_hash` |
    | 淨利率去年同季錯位 | `test_fin_card`、`test_version_hash` |

- node：本機 v14.17.1，沒有 `Array.prototype.at`。測試在執行的 JS 前補 `.at`（`renderFin` 原本就用 `.at`）。
- `test_serve_cache` 約 1 秒；只連 127.0.0.1，不連外。

### 8-1 PM 5-2 的 18 項舊斷言

| # | 位置 | 處理 |
|---|---|---|
| 1 | `test_iter22.py` 第 184 行 | **改這一行**：字面換成 `<a class="muted small" href="#/rank/hl">近期新訊號 →</a>`，同一行其餘不動 |
| 2 | `test_iter20.py` 第 79 行 | **改這一行**：`assert ("<h2>自選 ETF</h2>" if k == "etf" else "<h2>自選</h2>") in o[k]`，另外三種照舊 |
| 3 | `test_iter20.py` 第 25 行 | 避開：`'<h2>自選</h2>'`、`<h2>ETF</h2>` 字面留在 `stk` 分支 |
| 4 | `test_iter20.py` 第 85～87 行 | 避開：只有 ETF 時不輸出 `spanSeg`、股票表 |
| 5 | `test_iter10.py` 第 167 行 | 避開：`nm` 是新鍵，`q` 不變 |
| 6 | `test_iter10.py` 第 169 行、`test_iter15.py` 第 39 行 | 避開：`nm` 不放進 `c` |
| 7 | `test_iter13.py` 第 81 行 | 避開：近期表現的 `noteHTML(short, full)` 用變數；淨利率說明併入既有呼叫的內文；字面呼叫仍是 8 個 |
| 8 | `test_iter13.py` 第 65 行 | 避開：原句逐字保留，新句加在「金融業沒有毛利率。」之後 |
| 9 | `test_iter13.py` 第 48～49 行 | 避開：近期表現在 K 線卡之後，不在統計卡區段 |
| 10 | `test_iter13.py` 第 14 行 | 避開：不動 sticky 規則，另加 `@media` |
| 11 | `test_iter21.py` 第 113 行 | 避開：原規則保留，另加一行 |
| 12 | `test_iter21.py` 第 164～169 行 | 避開：`<tr data-code="…">` 不加屬性；標籤同時在名稱格與標籤欄，`in` 斷言照樣通過 |
| 13 | `test_iter21.py` 第 107～112 行、`test_iter22.py` 第 206～216 行 | 避開：新文字沒有禁用詞（已跑過） |
| 14 | `test_iter19.py` 第 151 行 | 避開：只改 `position`、`shape`，文字式子不動 |
| 15 | `test_iter08.py` 第 100 行、`test_iter21.py` 第 101 行 | 避開：`price_stats` 參數、回傳不變；`highlights` 不動 |
| 16 | `test_iter08.py` 第 176 行 | 避開：`pf` 不進 `screen.json` |
| 17 | `test_iter15.py` 第 83 行 | 避開：ETF 不加 `pf` |
| 18 | `test_iter20.py` 第 60 行 | 避開：`streakTxt` 仍是頂層 `const` 一行，以 `;` 結尾；註解放在上一行 |

---

## 九、PG 實作順序

1. **基線**：
   - 記錄資料日、`collect_runs` 最大 `run_id`，確認沒有進行中的收集（`finished_at` 為 NULL 的列 0）。
   - 複製 `export.py`、`__main__.py`、`app.js`、`stock.js`、`app.css`、`index.html`、`README.md`、`tests/test_iter20.py`、`tests/test_iter22.py` 到 `logs/iter23_before/`。
   - 把專案 `site/data` 複製到 `logs/iter23_base/`。
     - 建議先用基線程式 `export` 一次再複製，讓兩邊只差新程式。
     - 若 `collect_runs` 已大於 17（使用者收集過），照這個做法即可：基線和新匯出用同一份資料庫。
     - 注意：專案 `site/data/etfp/00662.json` 是舊檔（目前的匯出不會產生）。用基線程式重新匯出時不會刪它，兩邊都有，比對不受影響。
2. **套用**：附錄 A 的 diff，先 `patch -p1 --dry-run`，再正式套用；新增 `tests/test_iter23.py`。
   - 本 SA 已在 scratchpad 的專案副本驗證：可以套用，套用後 9 個檔和原型逐位元組相同，`test_iter01`～`23` 全部通過。
3. **測試**：
   - `node --check site/app.js site/stock.js`。
   - `test_iter01`～`23` 全部通過。
   - **之後只要再改 js／css，就要照 `test_iter23` 的失敗訊息更新 `index.html`**（上線步驟 3）。照附錄 A 原樣套用時不需要另外改。
4. **反證**：用暫存副本（不含 `.env`）放 `logs/iter23_before/` 的檔案跑 `test_iter23` → 14 個應全部失敗。
5. **匯出**：新程式 `python3 -u -m twstock export` 一次，記錄耗時與 `stocks/` 大小。
6. **比對**：把附錄 B 的 `cmp.py` 存成 `logs/iter23_cmp.py`，執行 `python3 logs/iter23_cmp.py logs/iter23_base site/data`，應回傳 0。只讀檔案。
7. **8001 預覽**：
   - `python3 -m twstock serve --port 8001 --no-browser`；`curl -sI` 看 `Cache-Control`。
   - 375 深色、1024 淺色：2421、2330、6488、6947、4406、3454、3661、2881、0050，以及 `#/rank/hl`、`#/watch`（暫時寫入 `tw.watch`）。
   - 結束時刪除預覽新增的 localStorage 鍵，關閉 8001。
- **允許的寫入**：只有 `export`（1～2 次，寫 `site/data/`）。不執行 `collect`、`history`、`setup-db`、`backup`、還原。
- **PG 每輪的固定步驟（寫進 04-dev，也給之後各輪）**：改了 `app.js`、`stock.js`、`app.css` 任何一個 → 跑 `test_iter23` → 照失敗訊息更新 `index.html` 的 3 行 → 再跑一次。
- 行數預估：程式＋README **＋86／−22**（PM 約 80、上限 95）；測試 353 行（PM 估 150～200，超出的是 node 執行與 `serve` 本機請求；在一個工作階段 580 行以內）；舊測試 2 行。

---

## 十、對 PM 的調整

1. **`pf` 每列多存差距**：`[區間, 基準日, 本股, 指數, 差距]`。
   - 原因：差距要用未四捨五入的值相減，前端用兩個四捨五入後的值相減會差 0.01（2330 52 週 6.42 ≠ 6.41），驗收 #8 就不會 0 差異。
   - 影響：`stocks/` ＋528 KB（PM 估約 240 KB）。
2. **D35-5「上市以來」不另做例外判斷**：本站沒有上市日（`listed_date` 全部 NULL），0 請求無法確認是否復牌。改在收合說明寫明「復牌或轉換為控股公司的股票也從第一個成交日起算」。抽查疑似非新上市的有 3718、7819、8291（1-2）。
3. **文字格式**：
   - 上櫃股寫「上櫃以來」。
   - 日期用站內的 `md`（「07/23 起」，PM 寫「7/23 起」）。
   - 「起」放在第二行小字。
   - 表頭寫「至 11/13，本股最後成交 11/05」。
4. **F23-4a 仍要橫捲**：375 寬表格 421 px（容器 309 px），小於改前 577 px。名稱欄 189 px 加上面向、收盤、漲跌、20 日均額四欄就超過容器；要完全不捲動得再隱藏欄位，屬於 PM 的範圍外（其他欄位寬度）。
5. **1024 寬近期表現表加寬度上限 560 px**（1 個 CSS 宣告）：不加時四欄會拉到 958 px，數字離區間名稱太遠。
6. **非一般業不輸出 `nm` 鍵**（PM 留給 SA）。
7. **測試 353 行**，超過 PM 估計的 150～200 行（理由見第九節）。
8. 版本參數的更新方式維持 PM 的 A（手動＋測試），評估見 3-2。
9. 其他照 PM。

---

## 十一、給 QA 的提醒

1. **近期表現獨立驗算**：
   - 不要 import `stock_perf`。
   - 用 `stocks/{代號}.json` 的 `prices`＋`ev` 自己做還原（事件當天與之後係數 1），指數查 `market_index`。
   - 基準日：完整交易日 `days[-1-N]`；今年以來 = 前一年最後交易日；52 週 = 資料日 − 365 天以前的最後交易日。
   - 差距用未四捨五入的值相減。
2. **全市場和選股 0 差異**是硬條件（`cmp.py`）。
3. **淨利率**：自己查 `quarterly_financials` 的 `revenue`、`net_income` 相減，ROUND_HALF_UP 到 1 位；只有 `ci`。
4. **雜湊**：先跑 `test_iter23`，再用 `shasum` 自己算；在暫存副本改一個字元，測試應失敗並印出 3 行。
5. **快取**：只用 8001 驗證；8000 是使用者的舊程序，不碰。
6. 預覽前後記錄 localStorage 的鍵；暫時寫入的 `tw.watch` 要恢復。

---

## 十二、驗收對照（PM 第二節）

| 項目 | # | 設計／原型 |
|---|---|---|
| F23-1 | 1～5 | 全部相同（1-4）；6947 日期格式「07/23 起」 |
| F23-1 | 6 | 14 檔沒有 `pf`；3454 沒有區塊 |
| F23-1 | 7 | 4406 表頭與 0.00% |
| F23-1 | 8 | 1,985 檔 0 差異 |
| F23-1 | 9 | 0／8／14／28／58／80 |
| F23-1 | 10 | 0050、00981A 沒有區塊；`etfp/` 相同 |
| F23-1 | 11 | `test_perf_*` 6 個測試 |
| F23-1 | 12 | 375 `scrollWidth` 375；1024；深淺色；主控台 0 錯誤 |
| F23-1 | 13 | `test_no_advice_words` |
| F23-1 | 14 | ＋0.2 秒；＋528 KB（第十節第 1 項） |
| F23-2 | 1～5 | 全部相同（2-4） |
| F23-2 | 6 | 1024 3＋3；375、深淺色 |
| F23-2 | 7 | `latest.stocks` 內 1,931（另 8 檔 null）；一般業 1,939（全部 1,944 檔為 1,936） |
| F23-2 | 8 | 有／沒有 `nm` 都不出錯（`test_fin_card`） |
| F23-3 | 1、2 | `test_version_hash`；突變反證 |
| F23-3 | 3～6 | 3-3 實測 |
| F23-3 | 7 | `cmd_serve` 其他部分不變 |
| F23-3 | 8 | 只用 8001 與測試的系統配發埠 |
| F23-4a～e | — | 第四節；4a 表格 421 px（第十節第 4 項） |

---

## 十三、使用者自行執行（照 PM 第七節）

1. PG `export`、QA 通過之後，**重新啟動 8000 的 `serve`**（原本的終端機 Ctrl+C，再執行 `python3 -m twstock serve`），`no-cache` 才會生效。
2. 重新啟動後第一次開網站，**強制重新整理最後一次**；之後一般重新整理即可。
3. 照常每晚 `collect --catch-up`；11/16 可能還有順延的季報，近期表現與淨利率會跟著更新。
4. 本輪完成後決定是否 commit。

---

## 附錄 A：完整 diff（`orig` → `proj`；新測試檔全文在後）

- 驗證：
  - 在 scratchpad 另外複製專案目前的 `twstock/`、`site/`（不含 `data`）、`README.md`、`tests/`、`scripts/`、`data/concepts.csv`（不含 `.env`）。
  - `patch -p1 --dry-run` 通過後正式套用，9 個檔和原型逐位元組相同；放入 `test_iter23.py` 後，`test_iter01`～`23` 全部通過。
  - 2026-11-14 再對專案目前的工作目錄執行 `patch -p1 --dry-run`（不寫檔）：9 個檔都可套用，沒有 offset 或 fuzz。

```diff
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -48,6 +48,7 @@
 NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
 HL_DAYS, HL_REV_DAYS = 5, 20     # 第 21 輪 F21-1：近期新訊號看最近 5 個交易日；營收看最近 20 個交易日
 HL_EPS_YOY, HL_EPS_BASE = 50, 0.1   # 第 22 輪 F22-11：EPS 年增事件門檻（%）；去年同季 < 0.1 元為基期低（同前端 EPS_BASE），不產生事件
+PF_DAYS = (5, 20, 60, 120)       # 第 23 輪 F23-1：個股頁近期表現的 N 日區間（另有今年以來 y、52 週 w、上市以來 s）
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
@@ -967,14 +968,10 @@
     out["vr"] = _f(yi[-1] / (sum(prior) / 20)) if len(prior) == 20 and sum(prior) > 0 else None
     raw = {}
     for n in (5, 20, 60):
-        b = days[-1 - n] if len(days) > n else None
-        base = next((a for d, a in zip(reversed(d_), reversed(adj)) if d <= b and a is not None), None) \
-            if b is not None and d_[0] <= b else None
-        raw[n] = (lc / base - 1) * 100 if base and lc else None
+        raw[n] = period_return(d_, adj, lc, days[-1 - n] if len(days) > n else None)
         out[f"r{n}"] = _f(raw[n])
     for n in (20, 60):
-        b = days[-1 - n] if len(days) > n else None
-        ir = (float(idx[days[-1]]) / float(idx[b]) - 1) * 100 if b in idx and days[-1] in idx else None
+        ir = index_return(idx, days[-1 - n] if len(days) > n else None, days[-1])
         out[f"rs{n}"] = _f(raw[n] - ir) if raw[n] is not None and ir is not None else None
     for n in (20, 60):
         out[f"b{n}"] = _f((lc / (sum(px[-n:]) / n) - 1) * 100) if len(px) >= n else None
@@ -983,6 +980,39 @@
     return out
 
 
+def period_return(d_, adj, lc, b):
+    """還原報酬 %（未四捨五入）= 最後成交的還原收盤 lc ÷ 基準日 b（含）以前最後一個有成交的還原收盤 − 1；
+    b 是 None、早於第一個資料列或之前沒有成交 → None。選股 r5／r20／r60 與個股頁近期表現共用（第 23 輪抽出）。"""
+    base = next((a for d, a in zip(reversed(d_), reversed(adj)) if d <= b and a is not None), None) \
+        if b is not None and d_[0] <= b else None
+    return (lc / base - 1) * 100 if base and lc else None
+
+
+def index_return(idx, b, last):
+    """指數報酬 %（未四捨五入）= last 收盤 ÷ 基準日 b 收盤 − 1；任一天沒有指數 → None。"""
+    return (float(idx[last]) / float(idx[b]) - 1) * 100 if b in idx and last in idx else None
+
+
+def stock_perf(d_, adj, days, idx, w52_start):
+    """
+    第 23 輪 F23-1：stocks/{代號}.json 的 pf = [[區間, 基準日, 本股 %, 指數 %, 差距（百分點）]]，用法同 price_stats（days 要完整的交易日序列）。
+    區間：PF_DAYS（基準日 days[-1-N]，同選股）、"y" 今年以來（前一年最後一個交易日）、"w" 52 週（w52_start 以前最後一個交易日，同 52 週高低）；
+    本股算不出（新上市）時三個值都是 None，並在最後加 "s"：從第一個成交日的收盤起算（上市以來，不是承銷價）。
+    差距用未四捨五入的值相減，和選股 rs20、rs60 相同。
+    """
+    px = [(d, a) for d, a in zip(d_, adj) if a is not None]
+    lc, last = px[-1][1], days[-1]
+    y, w = bisect_left(days, date(last.year, 1, 1)), bisect_right(days, w52_start)
+    bases = [(n, days[-1 - n] if len(days) > n else None) for n in PF_DAYS] + [("y", days[y - 1] if y else None), ("w", days[w - 1] if w else None)]
+
+    def row(k, b):
+        r = period_return(d_, adj, lc, b)
+        i = index_return(idx, b, last) if r is not None else None
+        return [k, b and str(b), _f(r), _f(i), _f(r - i) if i is not None else None]
+    out = [row(k, b) for k, b in bases]
+    return out + [row("s", px[0][0])] if any(r[2] is None for r in out) else out
+
+
 # 第 18 輪 F18-2：KD(9,3,3)、RSI(14)。和 site/stock.js 的 calcKD、calcRSI 同一套公式（改一邊要改另一邊）
 KD_N, RSI_N = 9, 14
 
@@ -1176,16 +1206,17 @@
     for _ in range(FIN_QUARTERS):
         keys.append(k)
         k = prev_quarter(*k)
-    rows = []
+    rows, nm = [], []
     for yy, qq in reversed(keys):
         if (yy, qq) not in cum:
             continue
         s, b = fin_single(cum, yy, qq), fin_single(cum, yy - 1, qq)
         rows.append([yy * 100 + qq, _f(s[4]), fin_yoy(s[4], b and b[4]), fin_margin(s[1], s[0]), fin_margin(s[2], s[0]), s[0],
                      _f(b and b[4])])   # 第 10 輪 QA-01：去年同季單季 EPS（前 4 季的去年同季不在 q 內，畫面靠它判斷「轉盈」）
+        nm.append(fin_margin(s[3], s[0]))   # 第 23 輪 F23-2：稅後淨利率 = 單季歸屬母公司淨利 ÷ 單季營收
     e, eb = cum[(y, q)][4], cum.get((y - 1, q), (None,) * 5)[4]
     return {"t": tbl, "q": rows, "c": {"e": _f(e), "ey": fin_yoy(e, eb), **({"fs": str(seen)} if seen else {})},
-            "e4": _f(fin_e4(cum, y, q)), "e4p": _f(fin_e4(cum, y - 1, q))}
+            "e4": _f(fin_e4(cum, y, q)), "e4p": _f(fin_e4(cum, y - 1, q)), **({"nm": nm} if tbl == "ci" else {})}   # nm 和 q 逐季對齊，只有一般業
 
 
 def fin_screen(cum: dict) -> dict:
@@ -1460,6 +1491,7 @@
     official_breadth = _load_breadth(cur, latest_date)
     # 寬度輸出 BREADTH_DAYS 天，前面多 60 天給 MA60
     b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
+    p_days = sorted({r[0] for rows in prices.values() for r in rows})   # 第 23 輪 F23-1：完整交易日序列（b_days 只有 120 天，120 日要第 121 天）
     status = build_status(cur, latest_date, now)
     valuation, stock_val, val_date = _load_valuation(cur, shares)      # F9-4；第 12 輪加 wpe
     fin, fin_meta, fin_counts, fin_seen = _load_financials(cur)   # 第 10 輪 B5；第 22 輪加收錄日
@@ -1562,6 +1594,9 @@
             **({"mt": {"d": str(latest_date), "mc": mc, "to": to}} if mc is not None else {}),   # 第 12 輪 B11
             **({"mg": mg} if mg else {}),
             **({"act": act} if act else {}),
+            # 第 23 輪 F23-1：近期表現；最後一列不是資料日（停牌、下市）或從沒成交 → 不輸出（同 latest.stocks）
+            **({"pf": stock_perf(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], p_days,
+                                 idx_close[info["market"]], w52_start)} if d_[-1] == latest_date and any(x is not None for x in c) else {}),
         })
         # 市場寬度：還原收盤（無成交日不列入）、成交額
         b_series[info["market"]].append({d_[i]: float(c[i]) * af[i] for i in range(len(d_)) if d_[i] >= b_from and c[i] is not None})
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -136,7 +136,13 @@
                 return
             super().handle_error(request, client_address)
 
-    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_DIR))
+    class Handler(http.server.SimpleHTTPRequestHandler):
+        def end_headers(self):
+            # 第 23 輪 F23-3：瀏覽器每次都向伺服器確認（沒改的檔回 304），更新程式後一般重新整理就生效
+            self.send_header("Cache-Control", "no-cache")
+            super().end_headers()
+
+    handler = functools.partial(Handler, directory=str(SITE_DIR))
     url = f"http://localhost:{args.port}/"
     try:
         httpd = Server(("127.0.0.1", args.port), handler)
--- a/site/app.js
+++ b/site/app.js
@@ -799,7 +799,8 @@
 // screen.json 排行的額外篩選與表格欄位
 const RANK_FILTER = { ry: x => !(x.rm < revMonth()), nh: x => x.nh > 0, dy: x => isNum(x.pe) && x.pe > 0 && x.cap !== 1, pe: x => x.pe > 0 && x.cap !== 1, sr: x => isNum(x.mb) && x.mb >= MARGIN_BASE };
 const RANK_COLS = { vr: ['vr'], nh: ['nh'], rs20: ['rs20'], ry: ['ry'], dy: ['dy', 'pe', 'pb'], pe: ['pe', 'pb', 'dy'], to: ['to', 'mc'] };
-const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) : '--';
+// 第 23 輪 F23-4d：匯出的連續天數最多看 30 日（streak(…[-30:])），30 寫「買30+」「賣30+」
+const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) + (Math.abs(v) >= 30 ? '+' : '') : '--';
 const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']], v);
 const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'rank' ? '#/rank' : '#/rank/' + v; });
 
@@ -928,7 +929,7 @@
         : !list.length ? '<div class="empty">目前沒有符合的股票。</div>'
         : `<div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>面向</th><th class="hl-th">近期新訊號</th><th>收盤</th><th>漲跌</th><th>20日均額</th></tr></thead><tbody>` +
           list.map(([x, n]) => `<tr data-code="${x.code}">
-            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
+            <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span><div class="hl-sub">${x.hl.map(hlTag).join('')}</div></td>
             <td class="num">${n}</td><td class="hl-tags">${x.hl.map(hlTag).join('')}</td>
             <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>`).join('') + '</tbody></table></div>'}</div>
       <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收、EPS 為最近 20 個交易日）在價量、法人、基本面（營收、EPS）、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
@@ -1389,10 +1390,10 @@
   const etfs = [...App.watch].filter(c => !S[c] && R[c]).map(c => [c, R[c]]);     // 第 20 輪 F20-1：自選的 ETF 另列一張表
   const stk = list.length || !etfs.length;                                         // 只有 ETF 時不顯示股票表與 1 日／5 日
   $('#view').innerHTML = `<section class="sec">
-      <div class="sec-h"><h2>自選</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span><span class="sp"></span>${stk ? spanSeg(span) : ''}</div>
+      <div class="sec-h">${stk ? '<h2>自選</h2>' : '<h2>自選 ETF</h2>'}<span class="muted small">存在這個瀏覽器裡，換裝置不會同步${stk ? '' : '。當日行情；成交量為張、成交額為億元'}</span><span class="sp"></span>${stk ? spanSeg(span) : ''}</div>
       ${stk ? `<div class="card">${list.length ? stockTable(list, span)
         : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」。</div>'}</div>` : ''}
-      ${etfs.length ? `<div class="sec-h" style="margin-top:12px"><h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>
+      ${etfs.length ? `${stk ? '<div class="sec-h" style="margin-top:12px"><h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>' : ''}
       <div class="card">${etfWatchTable(etfs)}</div>` : ''}</section>`;
   if (stk) onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
   $('#view').addEventListener('click', onRowClick);
--- a/site/stock.js
+++ b/site/stock.js
@@ -27,6 +27,21 @@
     n += x > 0 ? 1 : -1;
   }
   return n;
+}
+
+// 第 23 輪 F23-1：近期表現（匯出端 pf = [[區間, 基準日, 本股 %, 指數 %, 差距]]，和選股 5／20／60 日報酬、相對強度同一套）；停牌、ETF 沒有 pf。nt = 本股最後成交日（今天無成交時）
+const PF_NAME = { 5: '5 日', 20: '20 日', 60: '60 日', 120: '120 日', y: '今年以來', w: '52 週' };
+function perfHTML(pf, mkt, nt) {
+  const ix = mkt === 'TWSE' ? '加權指數' : '櫃買指數', ls = mkt === 'TWSE' ? '上市以來' : '上櫃以來', at = k => pf.find(r => r[0] === k)?.[1];
+  const td = (v, u) => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v) + u}</td>`;
+  const short = '還原價（含股息）；指數不含股息，長區間的差距會偏向個股';      // 短句用變數：test_iter13 數 noteHTML 字面呼叫
+  const full = `差距 = 本股 − ${ix}（百分點）。本股用還原收盤（除權息、減資、現金增資依官方參考價調整，和 K 線、52 週高低、選股相同），今天無成交時用最後成交的收盤；${ix}是價格指數，不含股息，所以區間越長，差距越偏向本股（大約是期間的殖利率）。` +
+    `N 日 = 從往前第 N 個交易日的收盤起算，5、20、60 日和選股的 5／20／60 日報酬、20／60 日相對強度相同；今年以來從 ${at('y')} 收盤起算；52 週從 ${at('w')} 收盤起算。` +
+    `「--」= 基準日時本站還沒有這檔的成交${at('s') ? `；${ls}從本站第一個成交日 ${at('s')} 的收盤起算，不是承銷價（本站日線從 2025-10-30 起，復牌或轉換為控股公司的股票也從第一個成交日起算）` : ''}。`;
+  return `<section class="sec card"><div class="sec-h"><h2>近期表現</h2><span class="muted small">至 ${md(App.latest.date)}${nt ? `，本股最後成交 ${md(nt)}` : ''}</span></div>
+    <div class="tbl-wrap"><table class="tbl pf-tbl"><thead><tr><th>區間</th><th>本股</th><th>${ix}</th><th>差距</th></tr></thead><tbody>` +
+    pf.map(([k, b, s, i, g]) => `<tr><td>${k === 's' ? `${ls}<span>${md(b)} 起</span>` : PF_NAME[k]}</td>${td(s, '%')}${td(i, '%')}${td(g, '')}</tr>`).join('') +
+    `</tbody></table></div><div class="muted small" style="margin-top:6px">${noteHTML(short, full)}</div></section>`;
 }
 
 const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];
@@ -134,7 +149,7 @@
             <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
             ${E && E.m === 'TPEx' ? '<span class="muted small">上櫃 ETF 的漲跌可能含除息，本站無法辨識除息日</span>' : ''}
           </div>
-          ${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>` : ''}
+          ${HL.length ? `<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>` : ''}
           <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
         </div>
         <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
@@ -180,6 +195,7 @@
       <div id="mC" class="chart-box" style="height:120px"></div>
     </section>
 
+    ${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}
     ${E ? '' : '<section class="sec card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></section>'}`}`;
 
   onSeg('stockTabSeg', v => { localStore('stockTab', null, v); window.disposeStockCharts(); window.renderStock(code); });
@@ -366,9 +382,10 @@
     ...(NT[i] ? { color: FLAT, borderColor: FLAT, wickColor: FLAT } : {}) })));
   // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字，第 19 輪 F19-2：週／月線寫事件日「M/D 類型」
   const mdn = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;
-  kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp',
+  const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' };   // 第 23 輪 F23-4b：週／月 K 標記在 K 棒上方
+  kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], ...mkPos,
     color: css('--blue'), text: [...new Set(r.ev.map(e => (mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)))].join('・') }]
-    : r.gx ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp', color: css('--text2'), text: r.gx }] : []));   // 第 15 輪：ETF 推測的價格調整日
+    : r.gx ? [{ time: T[i], ...mkPos, color: css('--text2'), text: r.gx }] : []));   // 第 15 輪：ETF 推測的價格調整日
   line(kc, ma5, '#888780'); line(kc, ma20, '#EF9F27'); line(kc, ma60, '#7F77DD');
 
   const vc = mk('vC', false);
@@ -566,6 +583,7 @@
     ['累計 EPS', fmt(F.c.e, 2), '', `${q === 4 ? '全年' : `1～${q * 3} 月`}，年增 ${cy}`],
     ...(F.t === 'ci' ? [['毛利率', pc1(L[3]), '', `去年同季 ${pc1(base?.[3])}`]] : []),
     ...(L[4] != null ? [['營益率', pc1(L[4]), '', `去年同季 ${pc1(base?.[4])}`]] : []),
+    ...(F.t === 'ci' && F.nm ? [['稅後淨利率', pc1(F.nm.at(-1)), '', `去年同季 ${pc1(F.nm[Q.indexOf(base)])}`]] : []),   // 第 23 輪 F23-2：nm 和 q 逐季對齊；舊 JSON 沒有 nm 不顯示
     ['近 4 季 EPS', fmt(F.e4, 2), '', `一年前 ${fmt(F.e4p, 2)}`]];
   const v = Q.map(r => r[1]).filter(isNum), mx = Math.max(0, ...v), mn = Math.min(0, ...v), span = mx - mn || 1, H = 110;
   const bar = r => { const e = r[1], c = e == null ? '' : r[2] == null ? 'flat' : r[2] >= 0 ? 'up' : 'dn';
@@ -576,7 +594,7 @@
   $('#finBox').innerHTML = `<div class="metrics">${stats.map(([l, x, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c}" style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>
     <div class="ch-label">近 ${Q.length} 季單季 EPS（元）；紅／綠 = 比去年同季增加／減少，灰 = 無法比較（去年同季虧損或沒有資料）</div>
     <div class="fin-bars">${Q.map(bar).join('')}</div>
-    <div class="muted small" style="margin-top:6px">${noteHTML('單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異', `單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}`)}</div>`;
+    <div class="muted small" style="margin-top:6px">${noteHTML('單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異', `單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}`)}</div>`;
 }
 
 function renderRevenue(rows) {
--- a/site/app.css
+++ b/site/app.css
@@ -262,3 +262,5 @@
 .note-dup .note[open] summary{font-size:0}
 .note-dup .note[open] summary i{font-size:12px;margin-left:0}
 .tbl td.hl-tags,.tbl th.hl-th{white-space:normal;min-width:12em;text-align:left}.hl-tag{display:inline-block;margin:1px 8px 1px 0;font-size:12px}.hl-tag i{font-style:normal;color:var(--text2)}   /* 第 21 輪 F21-1 */
+.hl-sub{display:none}table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 23 輪 F23-4a、F23-1 */
+@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}.tbl .nm .hl-sub span{color:var(--text);font-size:12px;margin:2px 8px 0 0}}
--- a/site/index.html
+++ b/site/index.html
@@ -6,11 +6,11 @@
 <title>台股資金流</title>
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
-<link rel="stylesheet" href="app.css">
+<link rel="stylesheet" href="app.css?v=52d5a6c7">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js" defer></script>
-<script src="stock.js" defer></script>
+<script src="app.js?v=b1f56347" defer></script>
+<script src="stock.js?v=aaba2021" defer></script>
 </head>
 <body>
 <header class="top">
--- a/README.md
+++ b/README.md
@@ -64,7 +64,7 @@
 python -m twstock futures --start 2020-01-01     # 補抓台指期日 K 與期貨三大法人未平倉（--commodity MTX 可抓小台）
 python -m twstock chains                         # 立即更新產業鏈族群（collect 每 30 天會自動更新）
 python -m twstock export                         # 只重新匯出網站 JSON（含選股用的 screen.json）；history、export 連不上資料庫時印一行說明並回傳 2
-python -m twstock serve                          # 本機預覽 http://localhost:8000
+python -m twstock serve                          # 本機預覽 http://localhost:8000（第 23 輪起回應都帶 Cache-Control: no-cache；改了 serve 要重新啟動才生效）
 python -m twstock chanlun 2330                   # 產生 output/chanlun_2330.svg
 python -m twstock backup                         # 備份資料庫到專案上一層的 _backups/（COPY_ONLY＋RESTORE VERIFYONLY；只新增不覆寫；--out 指定資料夾）
 python -m twstock setup-db                       # 建立／補建資料表
@@ -138,6 +138,7 @@
 - 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。第 17 輪：收集輸出的上市注意數字標「（近 30 天）」；證交所網站（上市注意）抓取失敗時只略過上市注意並印警告，上櫃與上市處置照常寫入（下次收集會補最近 30 天）；OpenAPI 4 個來源任一失敗仍整批不寫。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
 - 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。現金增資除權也依官方參考價調整。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 19 輪：除權事件依官方「減除股利參考價」（只扣股利、不扣現金增資，存在 `price_events.div_ref`；減資、面額變更沒有這一欄）分類，匯出 `ev[].k`：等於參考價 `s`（沒有現增，圖例「除權（配股）」）、等於前收 `c`（只有現增，標記「現增」、圖例「除權（現金增資）」）、其他 `sc`（股利＋現增，「權息」圖例「除權息（含現金增資）」）；容差 0.005 元，只對「權」「權息」，沒有值時照舊寫「除權」。週／月 K 的事件標記寫事件日（例如「2/24 現增」「6/10 息・6/24 權」），圖例第一欄寫「2026-02-23 當週」「2026-02 月」；「原始」價的週／月 K 那一根含事件時，前一根收盤先乘上每筆事件的參考價 ÷ 前收再相減，漲跌幅和「還原」相同（6669 週 K 2026-08-31 由 −64.38% 改為 +6.26%）。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。第 22 輪：技術面訊號的 MACD 柱依昨、今柱值的正負寫「MACD 正柱加長／正柱縮短／負柱縮短／負柱加長／柱由負翻正／柱由正翻負」（柱值相同寫「柱持平」），偏多／偏空的歸類照舊只看柱值是否比昨天大。
+- 個股頁近期表現（第 23 輪，「走勢」分頁 K 線與技術面訊號之間；`stocks/{代號}.json` 的 `pf` = [[區間, 基準日, 本股 %, 指數 %, 差距], ...]）：區間 5、20、60、120 日（基準日 = 全市場往前第 N 個交易日）、`y` 今年以來（前一年最後一個交易日）、`w` 52 週（資料日往前 365 天以前的最後一個交易日，同 52 週高低）。本股用還原收盤（含股息；今天無成交時用最後成交收盤，表頭寫最後成交日），上市比加權指數、上櫃比櫃買指數（價格指數，**不含股息**，長區間的差距會偏向個股）；差距 = 本股 − 指數（百分點）。5、20、60 日和選股的 `r5`、`r20`、`r60`、`rs20`、`rs60` 用同一個函式（`period_return`、`index_return`），數字相同。基準日時還沒有成交的區間寫「--」，並加一列 `s`「上市以來」（上櫃寫「上櫃以來」）：從本站第一個成交日的收盤起算，不是承銷價；本站日線從 2025-10-30 起，復牌或轉換為控股公司的股票也從第一個成交日算。停牌、下市（最後一列不是資料日）的股票沒有 `pf`、不顯示；ETF 頁不顯示。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
 - 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
 - 月營收：第 9 輪起從每月第一個交易日開始，`collect --catch-up` 每天第一次成功收集時抓已公布的公司（只補資料庫還沒有的公司，同一天只抓一次），直到該月家數達前一月的 98% 為止（約 10～12 日），之後到月底 0 個請求；`collect --date`、`history` 也收前一個月。月初官方檔案只有標題列時寫入 0 家，不是錯誤。
@@ -147,7 +148,7 @@
   - 收齊條件：總家數 ≥ 上一季 × 98%（上一季沒有資料時不算齊），而且金融業（金控、銀行、證券、保險）家數 ≥ 上一季，或今天已過金融業截止後的第一個交易日。
   - `first_seen`（「本站收錄」日期）只在日常收集第一次寫入時記錄；`history --only financials` 補抓的列為 NULL，畫面不顯示。公司更正累計值時 MERGE 更新、`first_seen` 不變；只有更正、沒有新增公司的那一次收集不會觸發匯出（下次有新資料或手動 `export` 時更新）。窗口外的更正用 `history --start … --only financials --force` 重抓。
   - `stock_fundamentals.eps` 未使用（全部為 NULL；官方本益比已含 EPS 資訊）。
-  - 個股頁「季報」卡（`stocks/{代號}.json` 的 `fin`，沒有任何季報的股票沒有這個鍵）：`t` 最新一季業別（`ci` 一般業、`fh` 金控、`basi` 銀行、`bd` 證券、`ins` 保險、`mim` 其他）；`q` 近 8 季（有資料的季別，舊到新）`[季別 YYYYQQ, 單季 EPS, 單季 EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]`；`c` 最新一季 `{e 累計 EPS, ey 累計 EPS 年增 %, fs 本站收錄日}`；`e4` 近 4 季 EPS（本季累計 + 去年全年 − 去年同季累計，四項缺一為 null）、`e4p` 一年前的近 4 季 EPS。年增在去年同期 ≤ 0 時為 null（畫面寫「轉盈」或 `--`）；百分比四捨五入（ROUND_HALF_UP）到 1 位。卡片顯示單季 EPS、累計 EPS、毛利率（只有一般業）、營益率（有值才顯示）、近 4 季 EPS 與一年前，以及近 8 季單季 EPS 柱狀圖（紅／綠 = 比去年同季增加／減少，灰 = 無法比較）。
+  - 個股頁「季報」卡（`stocks/{代號}.json` 的 `fin`，沒有任何季報的股票沒有這個鍵）：`t` 最新一季業別（`ci` 一般業、`fh` 金控、`basi` 銀行、`bd` 證券、`ins` 保險、`mim` 其他）；`q` 近 8 季（有資料的季別，舊到新）`[季別 YYYYQQ, 單季 EPS, 單季 EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]`；`c` 最新一季 `{e 累計 EPS, ey 累計 EPS 年增 %, fs 本站收錄日}`；`e4` 近 4 季 EPS（本季累計 + 去年全年 − 去年同季累計，四項缺一為 null）、`e4p` 一年前的近 4 季 EPS。年增在去年同期 ≤ 0 時為 null（畫面寫「轉盈」或 `--`）；百分比四捨五入（ROUND_HALF_UP）到 1 位。卡片顯示單季 EPS、累計 EPS、毛利率（只有一般業）、營益率（有值才顯示）、近 4 季 EPS 與一年前，以及近 8 季單季 EPS 柱狀圖（紅／綠 = 比去年同季增加／減少，灰 = 無法比較）。第 23 輪：一般業加 `nm` = 稅後淨利率 %（和 `q` 逐季對齊；單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益，部分網站用合併總淨利，數字會不同；極端值照實顯示），卡片排在營益率之後、副行寫去年同季；其他業別沒有 `nm`，不顯示。
   - 估值旁的獲利說明一行：近 4 季 EPS > 0，而且一年前 ≤ 0 或現在 ≥ 一年前 × 1.5 時，顯示「近 4 季 EPS 一年前 X 元 → 現在 Y 元（N 倍）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱」。
 - 台指期分 K 尚未支援。期交所只提供近 30 個交易日的逐筆成交檔，需要時可由逐筆資料合成。
 - 往前補抓日線時，請用同一區間執行 `python -m twstock events --start …`，否則補抓區段的價格不會還原。
@@ -166,4 +167,5 @@
 - 網站的「更新於」是**最後一次收集到新資料的時間**，不是匯出時間；還沒有執行紀錄時退回資料寫入時間，並標示「（依資料寫入時間）」。`history` 補抓不算。依交易日曆資料落後時（交易日 18:00 前看前一交易日，之後看當天，台灣時間），顯示橘色提示；部分資料異常時顯示局部提示。分頁回到前景時會重新檢查，有新資料會提示重新整理，不會自動跳轉。
 - 補抓舊日期（`collect --date`、`history`）不會覆蓋股票的名稱與市場別；只有最新日期的資料會更新。
 - `_archive/` 是舊腳本，**不要再執行**：它連同一個資料庫，會把上櫃殖利率覆寫成 NULL，並蓋掉名稱與市場別。目前已把 `_archive/config.py` 改名為 `config.py.disabled` 使它無法執行，請不要改回來。
+- 網站更新與快取（第 23 輪）：`site/index.html` 引用 `app.css`、`app.js`、`stock.js` 時帶 `?v=` 檔案內容 SHA-1 的前 8 碼（`shasum site/app.js | cut -c1-8`），檔案改了網址就跟著變；`python -m twstock serve` 的回應都帶 `Cache-Control: no-cache`（瀏覽器每次確認，沒改的檔回 304）。更新程式後一般重新整理即可；`serve` 要重新啟動才會送這個標頭。改了這 3 個檔要同步更新 `index.html` 的版本參數，`tests/test_iter23.py` 會檢查，不一致時印出正確的那 3 行。
 - 資料僅供研究參考，不構成投資建議。
--- a/tests/test_iter20.py
+++ b/tests/test_iter20.py
@@ -76,7 +76,7 @@
 console.log(JSON.stringify(out));"""
     o = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
     for k in o:
-        assert "<h2>自選</h2>" in o[k]
+        assert ("<h2>自選 ETF</h2>" if k == "etf" else "<h2>自選</h2>") in o[k]          # 第 23 輪 F23-4c：只有 ETF 時合併成「自選 ETF」
     b = o["both"]
     assert 'data-code="2330"' in b and b.count("data-etf=") == 3 and "9999" not in b      # 不存在的代號不顯示
     assert '<a class="pill hold" href="#/etf/00981A">持股</a>' in b and "rspanSeg" in b
--- a/tests/test_iter22.py
+++ b/tests/test_iter22.py
@@ -181,7 +181,7 @@
     assert "!E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減')" in STK
     # F22-12：頁首、共用 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列
     assert "const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];" in STK
-    assert '${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join(\'\')}' in STK
+    assert '${HL.length ? `<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>${HL.map(hlTag).join(\'\')}' in STK
     head = STK[STK.index('<div class="s-head">'):STK.index('id="starBtn"')]
     assert head.index('<div class="tags">') < head.index('s-hl')                    # 族群標籤下方、頁首內
     assert ".s-hl{margin-top:6px}" in CSS
```

### `tests/test_iter23.py`（新檔，全文）

```python
"""第 23 輪（不連網、不連資料庫）：F23-1 個股頁近期表現、F23-2 稅後淨利率、F23-3 版本參數與 serve 快取標頭、F23-4 小修 5 項。
export 的 stock_perf、fin_stock 用自造資料測邊界（120 日要第 121 天、新上市、今天無成交、事件日剛好是基準日、跨年、和選股同一套）；
有 node 時，逐字取出 stock.js、app.js 的函式執行（perfHTML、renderFin、streakTxt、renderWatch）；serve 在 127.0.0.1 的隨機埠啟動後本機請求。"""
import hashlib
import http.client
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
HTML = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
MAIN = (ROOT / "twstock" / "__main__.py").read_text(encoding="utf-8")


def _weekdays(a, b, skip=()):
    out, d = [], a
    while d <= b:
        if d.weekday() < 5 and d not in skip:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(date(2025, 10, 30), date(2026, 11, 13), skip={date(2026, 1, 1)})   # 測試用交易日：週一～五，元旦休市
W52 = DAYS[-1] - timedelta(days=365)                                                  # 2025-11-13（同匯出端 w52_start）
IDX = {d: 100.0 + i for i, d in enumerate(DAYS)}                                      # 指數每天 +1


def _pf(close, days=DAYS, idx=IDX, ev=()):
    """close：該股日線（對齊 days 的最後 len(close) 天，None = 無成交）；ev = [(列索引, 前收, 參考價)]。"""
    d_ = days[-len(close):]
    af = export._adj_factors(len(d_), [{"i": i, "p": p, "r": r} for i, p, r in ev])
    adj = [None if c is None else c * af[i] for i, c in enumerate(close)]
    return {r[0]: r for r in export.stock_perf(d_, adj, days, idx, W52)}, d_, adj


def _ir(b, last=DAYS[-1]):
    return (IDX[last] / IDX[b] - 1) * 100


# ─── F23-1：近期表現 ─────────────────────────────────────
def test_perf_full():
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.0])
    assert list(pf) == [5, 20, 60, 120, "y", "w"]                                      # 有完整歷史 → 沒有「上市以來」
    bases = {5: DAYS[-6], 20: DAYS[-21], 60: DAYS[-61], 120: DAYS[-121], "y": date(2025, 12, 31), "w": date(2025, 11, 13)}
    for k, b in bases.items():
        assert pf[k][1] == str(b), (k, pf[k])
        assert pf[k][2] == 10.0 and pf[k][3] == round(_ir(b), 2) and pf[k][4] == round(10 - _ir(b), 2), (k, pf[k])
    # 120 日要第 121 天：只給 120 天（b_days）時算不出來，所以匯出端改用完整交易日序列 p_days
    assert _pf([100.0] * 120 + [110.0], days=DAYS[-121:])[0][120][2] == 10.0
    assert _pf([100.0] * 119 + [110.0], days=DAYS[-120:])[0][120][1:] == [None, None, None, None]
    assert "p_days = sorted({r[0] for rows in prices.values() for r in rows})" in SRC
    assert "stock_perf(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], p_days," in SRC


def test_perf_new_listing():
    pf, d_, _ = _pf([78.5] * 76 + [61.69])                                             # 6947 型：77 個交易日
    assert [k for k in pf] == [5, 20, 60, 120, "y", "w", "s"]
    for k in (120, "y", "w"):
        assert pf[k][2:] == [None, None, None], pf[k]                                  # 上市前的區間：本股、指數、差距都是 --
    assert pf["s"] == ["s", str(d_[0]), round((61.69 / 78.5 - 1) * 100, 2), round(_ir(d_[0]), 2),
                       round((61.69 / 78.5 - 1) * 100 - _ir(d_[0]), 2)]                # 從第一個成交日的收盤起算
    assert pf[60][2] is not None
    # 7827 型：120 日的基準日早於第一個成交日 1 天 → --；剛好是第一個成交日 → 有值
    assert _pf([50.0] * 119 + [55.0])[0][120][2] is None and "s" in _pf([50.0] * 119 + [55.0])[0]
    assert _pf([50.0] * 120 + [55.0])[0][120][2] == 10.0
    # 前幾列無成交：上市以來從第一個「有成交」的日子起算
    pf, d_, _ = _pf([None, None] + [40.0] * 30 + [44.0])
    assert pf["s"][1] == str(d_[2]) and pf["s"][2] == 10.0


def test_perf_no_trade_and_index():
    close = [100.0] * (len(DAYS) - 8) + [105.0] + [None] * 7                           # 4406 型：最後成交在 5 日基準日之前
    pf, d_, adj = _pf(close)
    assert pf[5][2] == 0.0 and pf[5][3] == round(_ir(DAYS[-6]), 2) and pf[5][4] == round(-_ir(DAYS[-6]), 2)   # 照算 0%（D35-2）
    assert pf[20][2] == 5.0                                                            # 用最後成交的收盤
    idx = {d: v for d, v in IDX.items() if d != DAYS[-21]}                             # 基準日沒有指數 → 指數、差距 --，本股照列
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.0], idx=idx)
    assert pf[20][2:] == [10.0, None, None] and pf[5][3] is not None
    # 差距用未四捨五入的值相減（同 rs20）：10.004 − 5.006 = 4.998 → 5.0，不是 10.0 − 5.01 = 4.99
    idx = {**{d: 100.0 for d in DAYS}, DAYS[-1]: 105.006}
    pf, _, _ = _pf([100.0] * (len(DAYS) - 1) + [110.004], idx=idx)
    assert pf[5][2:] == [10.0, 5.01, 5.0], pf[5]


def test_perf_event_and_year():
    i = DAYS.index(date(2025, 12, 31))                                                 # 6488 型：除息日剛好是今年以來的基準日
    close = [100.0] * i + [96.0] * (len(DAYS) - i - 1) + [114.0]
    pf, _, _ = _pf(close, ev=[(i, 100.0, 95.0)])
    assert pf["y"][1] == "2025-12-31" and pf["y"][2] == 18.75                          # 基準 = 12/31 實際收盤 96（事件當天係數 1），不是 96 × 0.95
    assert pf["w"][2] == 20.0                                                          # 52 週基準在事件前：100 × 0.95 = 95
    # 跨年：新年第一個交易日的今年以來 = 1 日報酬
    days = _weekdays(date(2025, 10, 30), date(2026, 1, 2), skip={date(2026, 1, 1)})
    d_ = days
    adj = [100.0] * (len(days) - 1) + [103.0]
    pf = {r[0]: r for r in export.stock_perf(d_, adj, days, IDX, days[-1] - timedelta(days=365))}
    assert pf["y"][1] == "2025-12-31" and pf["y"][2] == 3.0 and pf["y"][3] == round((IDX[days[-1]] / IDX[days[-2]] - 1) * 100, 2)
    assert pf["w"][2] is None and "s" in pf                                            # 全市場資料不到 52 週時沒有 52 週


def test_perf_same_as_screen():
    # 和選股同一套：pf 的 5／20／60 日 = price_stats 的 r5／r20／r60（price_stats 用 b_days 的 120 天），20／60 日差距 = rs20／rs60
    close = [None if i % 17 == 5 else round(50 + 10 * ((i * 37) % 23) / 23 + i * 0.03, 2) for i in range(len(DAYS))]
    close[-1] = None                                                                   # 今天無成交
    pf, d_, adj = _pf(close, ev=[(100, 60.0, 57.5), (200, 55.0, 27.6)])
    st = export.price_stats(d_, adj, [1e8] * len(d_), DAYS[-120:], IDX)
    for n in (5, 20, 60):
        assert pf[n][2] == st[f"r{n}"], (n, pf[n], st)
    for n in (20, 60):
        assert pf[n][4] == st[f"rs{n}"], (n, pf[n], st)
    assert "raw[n] = period_return(d_, adj, lc, days[-1 - n] if len(days) > n else None)" in SRC        # price_stats 也用同一個函式
    assert "ir = index_return(idx, days[-1 - n] if len(days) > n else None, days[-1])" in SRC
    assert "pf" not in export.SCREEN_KEYS


def test_perf_export_source():
    # 停牌、下市（最後一列不是資料日）或從沒成交 → 不輸出 pf（和 latest.stocks 同條件）；ETF 的 etfp/ 不加
    assert 'idx_close[info["market"]], w52_start)} if d_[-1] == latest_date and any(x is not None for x in c) else {}),' in SRC
    assert SRC.index('"pf": stock_perf(') < SRC.index("if d_[-1] != latest_date:")
    assert "pf" not in SRC[SRC.index("def etf_export"):SRC.index("def _load_holdings")]
    assert "PF_DAYS = (5, 20, 60, 120)" in SRC


# ─── F23-2：稅後淨利率 ───────────────────────────────────
def _cum(rows):
    """rows = {(年, 季): (單季營收, 單季淨利)} → 累計值（毛利、營益用 0，EPS 用 1）。"""
    out, acc = {}, {}
    for (y, q), (rev, net) in sorted(rows.items()):
        a = acc.get(y, (0, 0)) if q > 1 else (0, 0)
        acc[y] = (None if rev is None or a[0] is None else a[0] + rev, None if net is None or a[1] is None else a[1] + net)
        out[(y, q)] = (acc[y][0], 0, 0, acc[y][1], q)
    return out


def test_net_margin():
    rows = {(2025, q): (5000000, 700000) for q in (1, 2)} | {(2025, 3): (6000000, 846000), (2025, 4): (5000000, 500000),
            (2026, 1): (5000000, 650000), (2026, 2): (5500000, 700000), (2026, 3): (6142510, 898565)}
    f = export.fin_stock(_cum(rows), "ci", None)
    assert len(f["nm"]) == len(f["q"]) == 7 and f["nm"][-1] == 14.6 and f["nm"][2] == 14.1   # 2421 型：26Q3 14.6%、去年同季 14.1%
    assert len(f["q"][-1]) == 7 and f["c"] == {"e": 3, "ey": 0.0}                     # q、c 不變
    for t in ("fh", "basi", "bd", "ins", "mim"):
        assert "nm" not in export.fin_stock(_cum(rows), t, None)                        # 只有一般業
    assert export.fin_stock(_cum({(2026, 1): (37, -15239)}), "ci", None)["nm"] == [-41186.5]   # 極端值照實（3521 型）
    assert export.fin_stock(_cum({(2026, 1): (0, 100)}), "ci", None)["nm"] == [None]           # 營收 ≤ 0
    assert export.fin_stock(_cum({(2026, 1): (None, 100)}), "ci", None)["nm"] == [None]        # 營收 NULL（銀行型）
    assert export.fin_stock(_cum({(2026, 1): (100, None)}), "ci", None)["nm"] == [None]        # 淨利 NULL
    # 上一季缺 → 單季淨利 None（不以累計頂替）
    c = _cum({(2026, 1): (100, 10), (2026, 2): (100, 20), (2026, 3): (100, 30)})
    del c[(2026, 2)]
    assert export.fin_stock(c, "ci", None)["nm"] == [10.0, None]


# ─── node：stock.js、app.js ──────────────────────────────
def _grab(src, name):
    """取出頂層 function 或 const（const 取到去掉行尾註解後結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


AT = "if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", AT + js], capture_output=True, text=True, check=True).stdout)


def test_perf_html():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "md", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("PF_NAME", "perfHTML")) + """
const App = { latest: { date: '2026-11-13' } };
const full = [[5, '2026-11-06', 7.2, 10.01, -2.81], [20, '2026-10-14', -21.64, -10.18, -11.46], [60, '2026-08-14', -8.22, -4.66, -3.56],
  [120, '2026-05-20', -3.11, 9.13, -12.25], ['y', '2025-12-31', -13.06, 50.79, -63.86], ['w', '2025-11-13', -24.17, 56.52, -80.69]];
const fresh = [[5, '2026-11-06', -1.45, 10.01, -11.46], [120, '2026-05-20', null, null, null], ['y', '2025-12-31', null, null, null],
  ['w', '2025-11-13', null, null, null], ['s', '2026-07-23', -21.42, -2.62, -18.8]];
console.log(JSON.stringify([perfHTML(full, 'TWSE', null), perfHTML(fresh, 'TWSE', null), perfHTML(full, 'TPEx', '2026-11-05'), perfHTML(fresh, 'TPEx', null)]));"""
    o = _node(js)
    if o is None:
        return
    a, b, c, d = o
    assert "<h2>近期表現</h2>" in a and "<th>區間</th><th>本股</th><th>加權指數</th><th>差距</th>" in a and "至 11/13</span>" in a
    assert '<tr><td>20 日</td><td class="num dn">-21.64%</td><td class="num dn">-10.18%</td><td class="num dn">-11.46</td></tr>' in a
    assert '<td>今年以來</td><td class="num dn">-13.06%</td><td class="num up">+50.79%</td>' in a and "上市以來" not in a
    assert "還原價（含股息）；指數不含股息，長區間的差距會偏向個股" in a and "今年以來從 2025-12-31 收盤起算；52 週從 2025-11-13 收盤起算" in a
    assert '<tr><td>120 日</td><td class="num flat">--</td><td class="num flat">--</td><td class="num flat">--</td></tr>' in b
    assert "<td>上市以來<span>07/23 起</span></td>" in b and "不是承銷價" in b and "本站第一個成交日 2026-07-23" in b
    assert "<th>櫃買指數</th>" in c and "至 11/13，本股最後成交 11/05</span>" in c and "上櫃以來<span>07/23 起</span>" in d
    # 位置：走勢分頁 K 線卡之後、技術面訊號之前；不在頂端指標卡（test_iter13 的統計卡區段）；ETF 沒有 pf
    assert "${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}" in STK
    assert STK.index('id="mC"') < STK.index("perfHTML(data.pf") < STK.index('id="sigTitle"')
    assert "table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;" in CSS


def test_fin_card():
    js = "\n".join(_grab(APP, n) for n in ("fmt", "sgn", "cls", "isNum", "REV_BASE", "epsLow", "noteHTML")) + "\n" + \
        "\n".join(_grab(STK, n) for n in ("qName", "qShort", "renderFin")) + """
const box = {}, $ = s => (box[s] = box[s] || {});
const q = [[202503, 2.55, 10, 31.3, 15.6, 6000000, 2.0], [202602, 2.9, 12, 32, 17, 5500000, 2.6], [202603, 3.15, 23.5, 32.7, 18.4, 6142510, 2.55]];
const F = (t, nm) => ({ t, q, c: { e: 7.93, ey: 40.4 }, e4: 10.22, e4p: 7.25, ...(nm ? { nm } : {}) });
const out = [F('ci', [14.1, 12.7, 14.6]), F('ci'), F('fh'), F('ci', [null, 12.7, null]), { ...F('ci', [12.7, 14.6]), q: q.slice(1) }]
  .map(f => { renderFin(f); return box['#finBox'].innerHTML; });
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    card = lambda h: re.findall(r'<div class="l">([^<]*)</div><div class="v num [^"]*" style="font-size:16px">([^<]*)</div><div class="s">([^<]*)</div>', h)
    a = card(o[0])
    assert [x[0] for x in a] == ["單季 EPS", "累計 EPS", "毛利率", "營益率", "稅後淨利率", "近 4 季 EPS"], a   # 營益率之後，1024 寬 3＋3
    assert a[4] == ("稅後淨利率", "14.6%", "去年同季 14.1%")
    assert "稅後淨利率" not in [x[0] for x in card(o[1])] and "稅後淨利率" not in [x[0] for x in card(o[2])]   # 舊 JSON、金融業不顯示
    assert card(o[3])[4] == ("稅後淨利率", "--", "去年同季 --")                       # 一般業但沒有值 → --
    assert card(o[4])[4] == ("稅後淨利率", "14.6%", "去年同季 --")                    # 去年同季不在近 8 季內
    assert "單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）" in o[0]
    assert "稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。" in o[0]


def test_small_fixes():
    o = _node(_grab(APP, "streakTxt") + "\nconsole.log(JSON.stringify([30, -30, 29, -3, 0, undefined].map(streakTxt)));")
    if o is not None:
        assert o == ["買30+", "賣30+", "買29", "賣3", "--", "--"], o                    # F23-4d
    assert "const streakTxt = v => v ? (v > 0 ? '買' : '賣') + Math.abs(v) + (Math.abs(v) >= 30 ? '+' : '') : '--';" in APP
    # F23-4b：日 K 照舊在下方，週／月 K 在上方；ETF 推測標記同規則；標記文字不變
    assert "const mkPos = mode === '日' ? { position: 'belowBar', shape: 'arrowUp' } : { position: 'aboveBar', shape: 'arrowDown' };" in STK
    assert STK.count("{ time: T[i], ...mkPos,") == 2 and "position: 'belowBar', shape: 'arrowUp'," not in STK
    # F23-4e：「近期新訊號 →」和站內「看排行 →」同寫法
    assert '<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>' in STK
    assert '<a class="muted small" href="#/rank/${rk}">看排行 →</a>' in APP
    # F23-4a：≤ 480 px 時標籤在名稱格下方、隱藏標籤欄；1024 照舊（hl-sub 不顯示）
    hl = APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")]
    assert "<span>${x.code} ${esc(x.i)}</span><div class=\"hl-sub\">${x.hl.map(hlTag).join('')}</div></td>" in hl
    assert '<td class="hl-tags">${x.hl.map(hlTag).join(\'\')}</td>' in hl
    assert ".hl-sub{display:none}" in CSS
    assert "@media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl td.nm .hl-sub{display:block;white-space:normal}" in CSS


def test_watch_etf_only():
    names = ["fmt", "pfmt", "sgn", "cls", "pctCell", "yi", "esc", "md", "streakTxt", "holdTag", "alertBadge",
             "segHTML", "onSeg", "flowNote", "stockTable", "spanSeg", "onEtfRow", "renderWatch", "etfWatchTable"]
    latest = {"date": "2026-11-13", "flow_date": "2026-11-13", "holdings": {"00981A": {}},
              "stocks": {"2330": {"n": "台積電", "i": "半導體", "c": 1460, "p": 1.2, "tv": 300.5, "f1": 10, "t1": 1, "d1": 0, "n1": 11, "fs": 2, "ts": 30, "s": 2}},
              "etfs": {"rows": {"0050": {"n": "元大台灣50", "m": "TWSE", "c": 70.1, "ch": 0.2, "p": 0.29, "v": 50000, "tv": 35.1},
                                "00981A": {"n": "主動統一台股增長", "m": "TWSE", "c": 15.1, "ch": 0.1, "p": 0.67, "v": 90000, "tv": 13.6}}}}
    js = "\n".join(_grab(APP, n) for n in names) + f"""
const App = {{ latest: {json.dumps(latest, ensure_ascii=False)}, watch: new Set() }};
const view = {{ innerHTML: '', addEventListener() {{}} }};
const $ = s => s === '#view' ? view : view.innerHTML.includes(`id="${{s.slice(1)}}"`) ? {{ addEventListener() {{}} }} : null;
const localStore = (k, f) => f, onRowClick = () => {{}};
const out = {{}};
for (const [k, w] of Object.entries({{ etf: ['0050', '00981A'], both: ['2330', '0050'], stock: ['2330'], none: [] }})) {{
  App.watch = new Set(w); view.innerHTML = ''; renderWatch(); out[k] = view.innerHTML;
}}
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    e = o["etf"]
    assert e.count("<h2>") == 1 and "<h2>自選 ETF</h2>" in e and "<h2>ETF</h2>" not in e                    # 只有一個標題列
    assert "存在這個瀏覽器裡，換裝置不會同步。當日行情；成交量為張、成交額為億元</span>" in e
    assert e.index("自選 ETF") < e.index('data-etf="0050"') and "rspanSeg" not in e
    assert o["both"].count("<h2>") == 2 and "<h2>自選</h2>" in o["both"] and "<h2>ETF</h2>" in o["both"]   # 股票＋ETF 照舊
    assert "<h2>自選 ETF</h2>" not in o["stock"] + o["none"] and "買30+" in o["stock"]


# ─── F23-3：版本參數、serve 快取標頭 ─────────────────────
def test_version_hash():
    v = {f: hashlib.sha1((ROOT / "site" / f).read_bytes()).hexdigest()[:8] for f in ("app.css", "app.js", "stock.js")}
    want = [f'<link rel="stylesheet" href="app.css?v={v["app.css"]}">', f'<script src="app.js?v={v["app.js"]}" defer></script>',
            f'<script src="stock.js?v={v["stock.js"]}" defer></script>']
    miss = [w for w in want if w not in HTML]
    assert not miss, "site/index.html 的版本參數和檔案內容不符（改了 js／css 要更新），請把這 3 行換成：\n" + "\n".join(want)
    assert len(re.findall(r'(?:href|src)="(?:app\.css|app\.js|stock\.js)[?"]', HTML)) == 3      # 每個檔只引用一次
    assert "plotly.js-basic-dist-min@2.35.2" in HTML and "lightweight-charts@4.2.0" in HTML     # CDN 照舊


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_serve_cache():
    assert 'self.send_header("Cache-Control", "no-cache")' in MAIN and "functools.partial(Handler, directory=str(SITE_DIR))" in MAIN
    port = _free_port()                                    # 系統配的空埠（不用 8000、8001）
    p = subprocess.Popen([sys.executable, "-m", "twstock", "serve", "--port", str(port), "--no-browser"], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        def get(path, headers=None):
            for _ in range(50):
                try:
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    c.request("GET", path, headers=headers or {})
                    r = c.getresponse()
                    return r.status, dict(r.getheaders()), r.read()
                except ConnectionRefusedError:
                    time.sleep(0.1)
            raise AssertionError("serve 沒有啟動")
        st, h, body = get("/")
        assert st == 200 and h.get("Cache-Control") == "no-cache" and b"app.js?v=" in body
        v = hashlib.sha1((ROOT / "site" / "app.js").read_bytes()).hexdigest()[:8]
        st, h, body = get(f"/app.js?v={v}")
        assert st == 200 and h.get("Cache-Control") == "no-cache" and body == (ROOT / "site" / "app.js").read_bytes()
        st, h2, _ = get("/app.js", {"If-Modified-Since": h["Last-Modified"]})
        assert st == 304 and h2.get("Cache-Control") == "no-cache"                    # 沒改的檔回 304
    finally:
        p.terminate()
        p.wait(timeout=10)


# ─── 用詞 ───────────────────────────────────────────────
def test_no_advice_words():
    seg = _grab(STK, "PF_NAME") + _grab(STK, "perfHTML") + _grab(APP, "streakTxt")
    seg += "".join(l for l in STK.splitlines() if "稅後淨利率" in l or "mkPos" in l or "s-hl" in l)
    seg += APP[APP.index("async function renderHl()"):APP.index("// ─── 第 8 輪 F8-2")] + _grab(APP, "renderWatch")
    seg += "".join(l[l.index("第 23 輪"):] for l in README.splitlines() if "第 23 輪" in l)
    assert seg.count("第 23 輪") >= 4, seg.count("第 23 輪")                        # README 4 段都有取到
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
              "利多", "利空", "看多", "看空", "轉強", "轉弱",
              "跑贏", "跑輸", "強於大盤", "弱於大盤", "贏過", "輸給", "領先", "落後", "抗跌", "超額報酬", "獲利能力佳", "惡化"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
```

---

## 附錄 B：比對腳本（PG、QA 可存成 `logs/iter23_cmp.py`；只讀檔案）

- 用法：`python3 logs/iter23_cmp.py <基線 site/data> <新 site/data>`；全部通過回傳 0，否則印出差異並回傳 1。

### `cmp.py`

```python
"""第 23 輪比對：python3 cmp.py 基線目錄 新目錄
1. 檔案清單相同；stocks/ 以外逐位元組相同（latest.json 去掉 updated_at、status 後逐值相同）。
2. stocks/：新的刪掉 pf 與 fin.nm 後，和基線逐位元組相同（_write 的格式重新輸出）。
3. pf：有 pf 的 = latest.stocks；5／20／60 日本股 = screen.json r5／r20／r60，20／60 日差距 = rs20／rs60（0 差異）；各區間缺值檔數。
4. nm：只有一般業有、和 q 等長；最新一季有值的檔數。
5. stocks/ 大小變化。"""
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
S = json.loads((B / "screen.json").read_text(encoding="utf-8"))
col = {k: dict(zip(S["codes"], S[k])) for k in ("r5", "r20", "r60", "rs20", "rs60")}
bad, has_pf, miss, kinds, nm_n, nm_bad, size = [], set(), Counter(), Counter(), 0, [], [0, 0]
for f in sorted(fa):
    if f.parts[0] != "stocks":
        continue
    a, b = (A / f).read_bytes(), (B / f).read_bytes()
    size[0] += len(a); size[1] += len(b)
    o = json.loads(b)
    pf, nm = o.pop("pf", None), (o.get("fin") or {}).pop("nm", None)
    if dump(o).encode() != a:
        bad.append(str(f))
    c = o["code"]
    if pf:
        has_pf.add(c)
        r = {x[0]: x for x in pf}
        for k, x in r.items():
            kinds[k] += 1
            miss[k] += x[2] is None
        for n in (5, 20, 60):
            if r[n][2] != col[f"r{n}"].get(c, "缺"):
                bad.append((c, f"r{n}", r[n][2], col[f"r{n}"].get(c)))
        for n in (20, 60):
            if r[n][4] != col[f"rs{n}"].get(c, "缺"):
                bad.append((c, f"rs{n}", r[n][4], col[f"rs{n}"].get(c)))
        if ("s" in r) != any(x[2] is None for x in pf):
            bad.append((c, "s"))
    if nm is not None:
        if o["fin"]["t"] != "ci" or len(nm) != len(o["fin"]["q"]):
            nm_bad.append(c)
        nm_n += nm[-1] is not None
    elif o.get("fin", {}).get("t") == "ci":
        nm_bad.append(c)
print("stocks/ 刪掉 pf、nm 後不同或 pf 和選股不同：", len(bad), bad[:5])
print("有 pf：", len(has_pf), "；= latest.stocks：", has_pf == set(lb["stocks"]), "；停牌等沒有 pf：", len(fa) and sum(1 for f in fa if f.parts[0] == "stocks") - len(has_pf))
print("各區間本股缺值：", {k: miss[k] for k in (5, 20, 60, 120, "y", "w")}, "；上市以來列：", kinds["s"])
print("nm：最新一季有值", nm_n, "；格式不符", nm_bad[:5])
print("stocks/ 大小", size[0], "→", size[1], f"（+{(size[1] - size[0]) / 1024:.1f} KB，每檔 +{(size[1] - size[0]) / max(len(has_pf), 1):.0f} bytes）")
sys.exit(0 if not other and la == lb and not bad and not nm_bad and has_pf == set(lb["stocks"]) else 1)
```
