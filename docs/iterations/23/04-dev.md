# 第 23 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-14（週六）
- 依據：
  - `03-design.md`：第九節步驟、附錄 A 的 diff 與 `tests/test_iter23.py` 全文、附錄 B 的 `cmp.py`。以 SA 為準，含第十節「對 PM 的調整」。
  - `02-pm.md`：範圍與驗收。
  - 使用者決定：接受 SA 的設計與調整；D34、D35 照預設。
- 本輪項目：F23-1 近期表現、F23-2 稅後淨利率、F23-3 版本參數與 `serve` 快取標頭、F23-4a～e 小修 **完成**。照附錄 A 套用，**只有 1 處和設計不同**（第三節）。
- 資料日 **2026-11-13**；`collect_runs` 最大 `run_id` 從頭到尾都是 **17**，`finished_at` 為 NULL 的列 0（開始、新程式匯出前、匯出後、結束各查一次）。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**：只有唯讀 SELECT（`collect_runs`、`daily_prices` 最大日期）與 `export` 兩次。
  - `export` 只寫 `site/data/`：基線程式一次、新程式一次。
  - 沒有執行 `collect`、`history`、`events`、`setup-db`、`backup`、還原；沒有安裝排程。
  - 8001 測完已關閉；8000（使用者的程序，PID 不變）沒有碰，也沒有重新啟動。
  - 瀏覽器：預覽前 localStorage 0 個鍵；預覽時新增的 `tw.stockTab`、`tw.rank2`、`tw.kmode` 與暫時寫入的 `tw.watch` 都已清除，**結束時 0 個鍵**。視窗已恢復 desktop，分頁已關閉。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/export.py` | ＋43／−8 | `PF_DAYS`；從 `price_stats` 抽出 `period_return`、`index_return`（參數、回傳不變）；`stock_perf`；`fin_stock` 加 `nm`；`p_days`；個股檔加 `pf` |
| `twstock/__main__.py` | ＋7／−1 | `cmd_serve` 的 `Handler` 在 `end_headers` 加 `Cache-Control: no-cache`（`serve` 說明行在 README，`__main__.py` 的 `--help` 文字沒有需要改的地方） |
| `site/stock.js` | ＋22／−4 | `PF_NAME`、`perfHTML`；走勢分頁插入近期表現；季報卡「稅後淨利率」與說明一句；週／月 K 標記 `mkPos`；「近期新訊號 →」 |
| `site/app.js` | ＋5／−4 | `streakTxt` 30 加「+」；新訊號表名稱格加 `hl-sub`；自選頁只有 ETF 時合併標題 |
| `site/app.css` | ＋2／−0 | `.hl-sub`、`.pf-tbl` 與 ≤ 480 px 規則 |
| `site/index.html` | ＋3／−3 | 3 個引用加 `?v=` |
| `README.md` | ＋4／−2 | `serve` 一行、近期表現一段、季報卡一句、網站更新與快取一段 |
| `tests/test_iter20.py` | ＋1／−1 | PM 5-2 第 2 項（見下） |
| `tests/test_iter22.py` | ＋1／−1 | PM 5-2 第 1 項（見下） |
| `tests/test_iter23.py`（新） | 353 行 | 14 個測試 |

- `git diff --stat`：9 個檔，**88 insertions(+)、24 deletions(-)**。扣掉 2 個舊測試檔，程式＋README **＋86／−22**，和設計第〇節相同（PM 估約 80，上限 95）。
- 舊斷言只改 2 行（D35-4）：

  | 檔案 | 改前 | 改後 | 原因 |
  |---|---|---|---|
  | `tests/test_iter22.py` 第 184 行 | `` assert '${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join(\'\')}' in STK `` | 同一行，字面換成 `<a class="muted small" href="#/rank/hl">近期新訊號 →</a>` | F23-4e 改的正是這個連結（D34-14 = A） |
  | `tests/test_iter20.py` 第 79 行 | `assert "<h2>自選</h2>" in o[k]` | `assert ("<h2>自選 ETF</h2>" if k == "etf" else "<h2>自選</h2>") in o[k]` | F23-4c 只有 ETF 時合併成「自選 ETF」（D34-12 = A）；另外三種照舊 |

- 基線副本：`logs/iter23_before/`（`export.py`、`__main__.py`、`app.js`、`stock.js`、`app.css`、`index.html`、`README.md`、`test_iter20.py`、`test_iter22.py`）。
- `site/data` 基線：`logs/iter23_base/`（**改程式之前**用基線程式 `export` 後複製，2,374 個檔、45 MB）。
- 新增的工作檔（`logs/` 在 `.gitignore` 中）：`logs/iter23_cmp.py`（附錄 B 原樣）、`iter23_export_base.log`、`iter23_export_new.log`、`iter23_tests.log`、`iter23_contrast.log`、`iter23_cmp.log`、`iter23_spot.log`、`iter23_cache.log`、`iter23_serve.log`。

---

## 二、執行步驟與結果

### 步驟 1：基線

- `collect_runs` 最大 17，沒有進行中的收集；`daily_prices` 最新 11/13。
- 複製基線檔案到 `logs/iter23_before/`。
- 基線 `export`：**25.5 秒**（`logs/iter23_export_base.log`），之後把 `site/data` 複製到 `logs/iter23_base/`。

### 步驟 2：套用

- 從 `03-design.md` 取出附錄 A：diff（第 463～770 行）、測試（第 776～1128 行）、`cmp.py`（第 1140～1198 行）。
- `patch -p1 --dry-run`：9 個檔都可套用，沒有 offset、fuzz；正式套用，沒有 `.orig`、`.rej`。
- 套用後 3 個雜湊和設計 3-1 相同（`52d5a6c7`、`b1f56347`、`aaba2021`）。
- 接著做第三節的 1 處修改（`stock.js` 不用 `.at()`），`stock.js` 的雜湊變成 **`a3b1a5c6`**，已更新 `index.html` 第 13 行。

### 步驟 3：測試、反證

| 項目 | 結果 |
|---|---|
| `node --check` | `site/app.js`、`site/stock.js` 通過（node v14.17.1）。本輪新增的程式行沒有 `.at(` |
| `test_iter01`～`23` | **23 個全部通過**（`logs/iter23_tests.log`）；舊測試只改上表 2 行 |
| 雜湊 | `index.html` 的 3 個 `?v=` = `shasum` 前 8 碼：`app.css` `52d5a6c7`、`app.js` `b1f56347`、`stock.js` `a3b1a5c6`（最終檔案，之後沒有再改 js／css） |
| 反證（舊檔） | 暫存副本（scratchpad `pg23/contrast`，不含 `.env`、`site/data`）放 `logs/iter23_before/` 的 7 個檔：<br>• 直接跑 `test_iter23` → 第一個測試就失敗（`export` 沒有 `stock_perf`）<br>• 逐一執行 14 個測試 → **14／14 失敗**（`logs/iter23_contrast.log`） |
| 反證（雜湊） | 新程式的暫存副本在 `app.js` 尾端加一行、不更新 `index.html` → `test_version_hash` 失敗，訊息印出正確的 3 行（`app.js?v=7819f96e`），和設計 3-2 的格式相同 |

### 步驟 4～5：匯出、比對

| 項目 | 結果 |
|---|---|
| 新程式 `export` | **25.5 秒**（基線 25.5 秒，＋0.0 秒；PM 上限＋3 秒）（`logs/iter23_export_new.log`） |
| `cmp.py`（`logs/iter23_cmp.log`） | **回傳 0**：<br>• 檔案清單相同（2,374 個）<br>• `stocks/`、`latest.json` 以外 **0 檔不同**（`screen.json`、`etfp/`、`etfs/` 等逐位元組相同）<br>• `latest.json` 去掉 `updated_at`、`status` 後逐值相同<br>• `stocks/` 刪掉 `pf`、`fin.nm` 後以 `_write` 格式重新輸出：**0 檔不同**<br>• 有 `pf` 1,985 檔 = `latest.stocks`；14 檔沒有 `pf`<br>• 本股缺值：5 日 0、20 日 8、60 日 14、120 日 28、今年以來 58、52 週 80；「上市以來」列 80<br>• `nm` 最新一季有值 1,936，格式不符 0 |
| `latest.json` 逐位元組 | 只差 `status.exported_at`（匯出時刻 11:07:43 → 11:09:24），其他逐值相同；這是每次匯出都會變的欄位，`cmp.py` 依設計排除 |
| `pf` 和 `screen.json` | `cmp.py` 0 差異；另外用獨立腳本再比一次：1,985 檔的 5／20／60 日本股 = `r5`／`r20`／`r60`，20／60 日差距 = `rs20`／`rs60`，**0 差異**（`logs/iter23_spot.log`） |
| `stocks/` 大小 | 36,187,469 → 36,728,446 bytes（**＋528.3 KB**，每檔＋273 bytes），和設計第五節相同 |
| 實例（`logs/iter23_spot.log`） | 2421、2330、6488、6947、7827、4406 的 `pf` 和設計 1-3、1-4 逐值相同（2330 52 週差距 6.41；6947「上市以來」2026-07-23 −21.42／−2.62／−18.80；7827 2026-05-29 −12.77／−2.36／−10.41；4406 5 日 0.0／12.63／−12.63）。3454 沒有 `pf`。<br>`nm`：2421 最後 14.6、去年同季 14.1；2330 51.1／45.7；6488 10.1／13.6（26Q2 24.8）；6947 最後一季 26Q2 18.2；2881（`fh`）、2801（`basi`）沒有 `nm` |

- 匯出前後 `run_id` 都是 17，基線和新匯出用同一份資料；季報沒有新增，所以和設計的數字完全相同。

### 步驟 6：8001 預覽（專案 `site/`，真實資料）

- `python3 -m twstock serve --port 8001 --no-browser` 背景執行，結束時關閉。
- 瀏覽器載入的是新程式：`app.css?v=52d5a6c7`、`app.js?v=b1f56347`、`stock.js?v=a3b1a5c6`。

**快取（`logs/iter23_cache.log`）**

| 項目 | 結果 |
|---|---|
| `curl -sI` | `/`、`/app.js?v=…`、`/stock.js?v=…`、`/app.css?v=…`、`/data/latest.json`、404 的 `/nope` 都有 `Cache-Control: no-cache` |
| 304 | 帶 `If-Modified-Since: <Last-Modified>` 的 `/app.js?v=b1f56347`、`/data/latest.json` 回 **304** |
| 帶參數的內容 | `/app.js?v=b1f56347` 回 200，內容和 `site/app.js` 逐位元組相同 |
| 瀏覽器一般重新整理 | `app.css`、`app.js`、`stock.js`、`latest.json`、`stocks/2421.json` 都是 `transferSize` 300（304），伺服器紀錄同樣是 304 |
| 伺服器紀錄 | 沒有 Traceback；404 只有 `favicon.ico`（既有）與測試用的 `/nope` |

**近期表現（走勢分頁）**

| 股票 | 結果 |
|---|---|
| 2421 | 在 K 線（MACD 子圖）卡之後、「技術面訊號」之前；欄名「加權指數」；6 列數字同驗收 #1，漲紅跌綠；表下短句「還原價（含股息）；指數不含股息，長區間的差距會偏向個股」＋「說明」收合 |
| 2330 | 6 列同驗收 #2（52 週 +6.41） |
| 6488 | 欄名「櫃買指數」；今年以來 +55.77%／+23.95%／+31.82 |
| 6947 | 120 日、今年以來、52 週三格「--」；第 7 列「上市以來」下一行小字「07/23 起」−21.42%／−2.62%／−18.80；收合說明展開含「上市以來從本站第一個成交日 2026-07-23 的收盤起算，不是承銷價…」與「今年以來從 2025-12-31」「52 週從 2025-11-13」 |
| 4406 | 表頭「至 11/13，本股最後成交 11/05」；5 日 0.00%／+12.63%／−12.63 |
| 3454（停牌） | 沒有區塊，不留空白 |
| 0050、00981A（ETF） | 沒有區塊 |
| 寬度 | 375：表 309 px、`scrollWidth` 375；1024：表 560 px（上限）、`scrollWidth` 1024 |

**稅後淨利率（基本面分頁）**

| 股票 | 結果 |
|---|---|
| 2421 | 「稅後淨利率 14.6%／去年同季 14.1%」，在營益率之後；1024 寬 6 張卡 **3＋3 排** |
| 2330 | 51.1%／去年同季 45.7%；3＋3 排 |
| 6947 | 18.2%／去年同季 --；3＋3 排 |
| 2881（金控） | 3 張卡，沒有稅後淨利率 |
| 說明 | 收合內文有「稅後淨利率（只有一般業）= 單季歸屬母公司業主的淨利 ÷ 單季營收，不含非控制權益；部分網站用合併總淨利，數字會不同。」 |

**小修 5 項（375 深色、375 淺色、1024 深色、1024 淺色都看過；淺色背景 rgb(243,242,238)、深色 rgb(14,15,17)）**

| 項目 | 375（深／淺） | 1024（深／淺） |
|---|---|---|
| 4a 新訊號 `#/rank/hl` | 標籤欄隱藏，標籤在名稱格下方每行一個，「投信 5 日買超 ≥ 成交額 5% 11/12」整個可讀（日期換行）；36 列每列只看得到一次；0 個標籤超出名稱格；表格 **421 px**（容器 309 px，仍要橫捲，小於改前 577 px，同設計第十節第 4 項） | 有標籤欄、名稱格下方沒有標籤；每列只看得到一次 |
| 4b 週／月 K 標記 | 2421 週 K：「2/24 現增」「6/10 息」在 K 棒上方、向下箭頭，文字完整 | 2421 週 K、月 K 在上方；6186 週 K「8/6 息」「8/26 現增」在上方。日 K 照舊（目前視窗內沒有事件；程式日 K 仍是 `belowBar`＋`arrowUp`，`test_small_fixes` 驗證） |
| 4c 自選只有 ETF（`0050`、`00981A`） | 只有一個標題「自選 ETF」，兩句說明都看得到，下面直接接 ETF 表，沒有 1 日／5 日 | 同左；股票＋ETF 仍是「自選」＋「ETF」兩個標題，只有股票、沒有自選都和改前相同 |
| 4d「買30+」 | 1 日排行「投信連買」2330「買30+」，排序照舊（2330、4958 買25、2454 買23…）；選股 `ts=3` 的「投信連」欄、自選表都是「買30+」 | 同左 |
| 4e「近期新訊號 →」 | 3661 頁首 `class="muted small"`：深色 rgb(167,167,167)、淺色 rgb(95,95,95)，12 px，標籤是 rgb(236,236,236)／rgb(27,27,27)，看得出差別；**真實點擊**後到 `#/rank/hl`；2421 沒有這一列 | 同左 |

- 主控台：錯誤攔截器整段操作 **0 個錯誤**；`read_console_messages` 0 筆錯誤。
- 所有檢查頁面 375 寬 `scrollWidth` = 375（新訊號表格在 `.tbl-wrap` 內橫捲，頁面本身不捲）。

---

## 三、和設計的差異

1. **`stock.js` 稅後淨利率卡不用 `.at()`**（唯一的程式差異）：
   - 設計：`pc1(F.nm.at(-1))`。
   - 實作：`pc1(F.nm[F.nm.length - 1])`，結果相同。
   - 原因：使用者指示本機 node v14 不能用 `.at()`；第 22 輪起新增的程式行也不用 `.at(`。
   - 影響：`stock.js` 雜湊由設計的 `aaba2021` 變成 **`a3b1a5c6`**，已更新 `index.html`，`test_iter23` 通過。行數不變。
2. **檔案數 2,374（設計 2,373）**：和第 22 輪相同，是 `site/data/etfp/00662.json` 舊檔（目前的匯出不會產生也不會刪）。基線和新輸出都有、內容相同，不影響比對。
3. 其餘（輸出、檔數、大小、匯出時間、畫面）都和設計第一～六節相同。

---

## 四、PG 每輪的固定步驟（給之後各輪）

- 改了 `site/app.js`、`site/stock.js`、`site/app.css` 任何一個：
  1. 跑 `python3 tests/test_iter23.py`。
  2. 照失敗訊息更新 `site/index.html` 的 3 行（或自己算 `shasum site/xxx | cut -c1-8`）。
  3. 再跑一次，通過才算完成。
- 本輪最終值：`app.css?v=52d5a6c7`、`app.js?v=b1f56347`、`stock.js?v=a3b1a5c6`。

---

## 五、給 QA 的提醒

1. **基線**：改前程式 `logs/iter23_before/`；改前資料 `logs/iter23_base/`（run 17）。若 QA 期間使用者收集過（`run_id` > 17），請用 `logs/iter23_before/` 的程式另外匯出比對。
2. **比對腳本**：`python3 logs/iter23_cmp.py logs/iter23_base site/data`（附錄 B 原樣）。
3. **雜湊**：`stock.js` 是 `a3b1a5c6`，不是設計寫的 `aaba2021`（第三節第 1 項）。
4. **反證**：`test_iter23` 的執行器遇到第一個失敗就停；逐一執行的結果見 `logs/iter23_contrast.log`。
5. **8000**：使用者的程序還是 11/03 啟動的舊程序，**沒有 `no-cache`**；要等使用者重新啟動（設計第十三節）。QA 只用 8001 驗證。
6. 本輪尚未 commit。`git status`：修改 9 個檔，新增 `tests/test_iter23.py`、`docs/iterations/23/`。
