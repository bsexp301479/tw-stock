# 第 22 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-14（週六）凌晨
- 依據：
  - `03-design.md`：第八節步驟、附錄 A 的 diff 與 `tests/test_iter22.py` 全文、附錄 B 的比對腳本。以 SA 為準，含第十一節「對 PM 的調整」。
  - `02-pm.md`：範圍與驗收。
  - 使用者決定：接受 SA 的設計與調整；D33 全部照預設。
- 本輪項目：F22-10、F22-11、F22-1、F22-12 **完成**。照附錄 A 原樣套用，**程式和設計沒有不同**。
- 資料日 **2026-11-13**；`collect_runs` 最大 `run_id` 從頭到尾都是 **17**，`finished_at` 為 NULL 的列 0（開始、匯出前、匯出後、結束各查一次）。季報 2026Q3 1,859 家，和設計基線相同。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**；只有唯讀 SELECT（`collect_runs`、`daily_prices` 最大日期、2026Q3 家數）與 `export` 兩次。
  - `export` 只寫 `site/data/`：基線程式一次、新程式一次。
  - 沒有執行 `collect`、`history`、`events`、`setup-db`、`backup`、還原；沒有安裝排程。
  - 8001 測完已關閉；沒有碰 8000。
  - 瀏覽器已恢復 desktop 大小（色彩恢復成開始時的深色）。8001 的 localStorage 預覽前沒有任何鍵；預覽時新增的 `tw.stockTab`、`tw.kmode`、`tw.hlmin` 已刪除。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/export.py` | ＋36／−7 | `HL_EPS_YOY`、`HL_EPS_BASE`；`highlight_eps()`；`_load_financials` 多讀 `created_at`、多回傳收錄日；`fq_all`；`hl` 串接 EPS 事件 |
| `site/app.js` | ＋11／−5 | `HL_KINDS` 加 `et`、`eg`，營收面向改稱「基本面」；`hlTag` 加季別；新訊號說明句；`epsTurn`；選股「單季 EPS 轉盈」；`SCR_COLS.eb` |
| `site/stock.js` | ＋25／−5 | `runTxt`、`balStreak`；籌碼卡副行連續天數；頁首 `HL` 標籤；`macdBar` |
| `site/app.css` | ＋1／−0 | `.s-hl` |
| `README.md` | ＋4／−4 | 個股法人、條件選股、近期新訊號、還原價／技術面 4 段各加第 22 輪說明 |
| `tests/test_iter22.py`（新） | 223 行 | 9 個測試 |

- `git diff --stat`：5 個檔，**77 insertions(+)、21 deletions(-)**，和設計第〇節相同（PM 估約 70，上限 85）。
- `__main__.py` 指令說明沒有變動，不改（設計第〇節「不動」）。
- 基線副本：`logs/iter22_before/`（`export.py`、`app.js`、`stock.js`、`app.css`、`README.md`、`__main__.py`）。
- `site/data` 基線：`logs/iter22_base/`（**改程式之前**用基線程式 `export` 後複製）。
- 新增的工作腳本（`logs/` 在 `.gitignore` 中，取自附錄 B，未修改）：
  - `logs/iter22_cmp.py`、`logs/iter22_macd_run.js`、`logs/iter22_macd_cmp.py`、`logs/iter22_streak_run.js`。

---

## 二、執行步驟與結果

### 步驟 1：基線

- `collect_runs` 最大 17（11/14 00:25～00:26），沒有進行中的收集；`daily_prices` 最新 11/13。
- 複製基線檔案到 `logs/iter22_before/`。
- 基線 `export`：25.5 秒，`latest.json` 778,057 bytes（`logs/iter22_export_base.log`）。
- 把 `site/data` 複製到 `logs/iter22_base/`（45 MB，2,374 個檔）。

### 步驟 2：套用

- 從 `03-design.md` 取出附錄 A：
  - diff（第 461～729 行）：`patch -p1 --dry-run` 5 個檔都沒有 offset、fuzz，正式套用；沒有 `.orig`、`.rej`。
  - 測試（第 735～957 行）存成 `tests/test_iter22.py`（223 行）。
- 新增的程式行沒有 `.at(`（本機 node v14.17.1）。

### 步驟 3：測試、反證

| 項目 | 結果 |
|---|---|
| `node --check` | `site/app.js`、`site/stock.js` 通過 |
| `test_iter01`～`22` | **22 個全部通過**（`logs/iter22_tests.log`）；舊測試沒有改 |
| 反證 | 暫存副本（scratchpad `pg22/contrast`，不含 `.env`、`site/data`）放 `logs/iter22_before/` 的 `export.py`、`app.js`、`stock.js`、`app.css`、`README.md`：<br>• 直接跑 `test_iter22` → 第一個測試就失敗（`export` 沒有 `highlight_eps`）<br>• 逐一執行 9 個測試 → **9／9 失敗**（`logs/iter22_contrast.log`） ✅ |

### 步驟 4～5：匯出、比對

| 項目 | 結果 |
|---|---|
| 新程式 `export` | 25.3 秒（基線 25.5 秒，−0.2 秒；PM 上限＋5 秒）；`latest.json` **793,258 bytes**（＋15,201，和設計第五節相同）（`logs/iter22_export_new.log`） |
| `cmp.py`（`logs/iter22_cmp.log`） | 回傳 0：<br>• 檔案清單相同（2,374 個）<br>• `latest.json` 以外 **0 檔不同**（`screen.json`、`stocks/`、`etfp/`、`etfs/` 逐位元組相同）<br>• `latest.json` 去掉 `et`、`eg` 與 `updated_at`、`status` 後**逐值相同** |
| 新事件 | **`et` 126、`eg` 381**；只有 EPS 事件的股票 **216**；有 `hl` 的股票 878 → **1,094**。和設計 2-6 完全相同 |
| EPS 事件日期 | 11/06 135、11/09 26、11/10 45、11/12 202、11/13 99；沒有 11/14；季別全部 202603（`logs/iter22_eps_check.log`） |
| EPS 實例 | 1301、1101 `et` 11/12；2002 `et` 11/06（`created_at`）；2330 `rv` 11/10＋`eg` 11/13；2603、1303 `eg` 11/12；2421 沒有 `hl`；3661 7 個事件。全部和設計相同 |
| MACD（`logs/iter22_macd.log`） | 基線與新 `stock.js` 各跑 1,999 檔日／週／月 K：**結論、歸類、其他 5 項 0 差異**（回傳 0）。<br>日線 1,987 檔：柱放大→負柱縮短 1,239、柱縮小→負柱加長 191、柱放大→由負翻正 170、柱放大→正柱加長 291、柱縮小→由正翻負 24、柱縮小→正柱縮短 72。<br>週線 1,945 檔（負柱加長 921、負柱縮短 481、正柱縮短 210、正柱加長 192、由正翻負 94、由負翻正 47）；月線 0 檔。<br>實例：2421「偏空：1 多 5 空」負柱縮短（週 K 負柱加長）、1235 正柱加長、1416 正柱縮短、1102 負柱加長、1326 由負翻正、3147 由正翻負、2330 正柱加長 |
| 連續天數（`logs/iter22_streak.log`） | ≥ 3／≤ −3：法人 329／254、外資 306／260、投信 129／24、融資 180／201、借券 445／66。<br>2421：連賣 3、連賣 3、投信不寫、連增 5、連增 13；2330 投信「連買 30 日以上」（全市場唯一）；2454 投信 23、法人 3；2308 法人連賣 25；2908 融資連增 22；3013 融資連減 15；2883 借券連增 22。<br>`mg.k` 16 檔，清單和設計 3-3 相同。全部和設計相同 |

- 新事件檔數和設計相同，匯出當下的季報家數（2026Q3 1,859）與設計基線一樣，沒有新增季報，所以不需要重算差異。

### 步驟 6：8001 預覽（專案 `site/`，真實資料）

- `python3 -m twstock serve --port 8001 --no-browser` 背景執行；先以 `fetch(…, {cache:'reload'})` 重新取得 `app.js`、`stock.js`、`app.css`、`index.html` 與資料檔，再載入，確認 `macdBar`、`runTxt`、`epsTurn` 都存在（新程式）。
- 伺服器記錄中 404 只有 `favicon.ico`（既有）。頁面照舊從 jsDelivr 載入 Plotly、Lightweight Charts（既有行為，不是本輪新增的請求）。

| 項目 | 結果 |
|---|---|
| 2421 技術面 | 偏多欄「MACD 負柱縮短」，「偏空：1 多 5 空」；**真實點擊**「週」→ 「MACD 負柱加長」 |
| 2421 籌碼（**真實點擊**「籌碼」） | 法人1日「11/13／連賣 3 日」、外資5日「至 11/13／連賣 3 日」、投信5日不寫、融資「1日 +19　5日 +179／連增 5 日」、借券「1日 +23　5日 +215／連增 13 日」 |
| 2421 頁首 | **沒有**新訊號區塊（2421 沒有 `hl`，見第三節第 2 點），族群標籤照舊 |
| 3661 頁首 | `.s-hl` 在 `.tags` 之後、`.s-ohlc` 之前；「近期新訊號」連到 `#/rank/hl`；**7 個標籤**，順序與文字同設計（含「26Q3 EPS 年增 ≥ 50% 11/12」）；後面一行灰字說明 |
| 2330 | 頁首「10 月營收創新高 11/10」「26Q3 EPS 年增 ≥ 50% 11/13」；籌碼（**真實點擊**）法人1日不寫、外資「連賣 2 日」、投信「**連買 30 日以上**」、借券「連增 9 日」 |
| 1301 | 頁首只有「26Q3 EPS 轉盈 11/12」 |
| 0050（ETF） | 沒有新訊號區塊、卡片沒有連續天數 |
| 新訊號頁 | 排行頁**真實點擊**「新訊號」→ `#/rank/hl`：「面向 ≥ 3：36 檔；≥ 2：199 檔」；≥ 3 的 36 列中有 EPS 標籤（如世芯-KY、南亞科、台玻）；說明句含「EPS 只看全市場最新一季」「營收、EPS 日期為本站首次收錄日」。**真實點擊**「面向 ≥ 2」→ 199 列，含轉盈標籤 22 個、EPS 年增 120 個 |
| 選股 `#/rank/screen?et=1` | 「單季 EPS 轉盈」已勾選，「單獨 151」、「符合 151 檔」；結果欄「單季EPS（Q3）」「去年同季EPS」，前 100 列沒有 `--`（例：群創 0.96／0.00、麗臺 4.03／−0.43） |
| 375 深色 | 3661、2421、2330、1301、新訊號、選股 `scrollWidth = 375`；3661 頁首 7 個標籤換 4 行；背景深色正常 |
| 375 淺色 | 同一組頁面 `scrollWidth = 375`；背景淺色正常 |
| 主控台 | 錯誤攔截器整段操作 **0 個錯誤** |

---

## 三、和設計的差異

1. **程式、測試、README：無**。附錄 A 原樣套用；行數、輸出、比對結果、事件檔數、MACD 與連續天數分佈都和設計第〇、一、二、三、五節相同（匯出時間差 0.1 秒）。
2. **任務描述與設計的出入（以設計為準，未改程式）**：任務寫「2421 頁首有標籤」，但設計第四節與 PM F22-12 驗收 #2 都是「2421 沒有 `hl`，不顯示區塊」。實際 2421 的 `latest.json` 沒有 `hl`，頁首只有既有的族群標籤，沒有新訊號區塊，符合設計。
3. **檔案數 2,374（設計 2,373）**：專案 `site/data/etfp/00662.json` 是 11/10 匯出留下的舊檔，現在的 `export` 不再產生，也不刪除（既有行為）；SA 的副本沒有複製 `site/data`，所以少這個檔。基線和新輸出都有，內容相同，不影響比對，本輪不處理。

---

## 四、給 QA 的提醒

1. **基線**：
   - 改前程式：`logs/iter22_before/`；改前資料：`logs/iter22_base/`（run 17）。
   - 若 QA 期間使用者又收集（`run_id` > 17），`site/data` 與季報家數會變；請記錄 `run_id`，用 `logs/iter22_before/` 的程式另外匯出比對，EPS 事件的增加要能用新收錄的公司解釋。
2. **比對腳本**：`logs/iter22_cmp.py`、`logs/iter22_macd_run.js`、`logs/iter22_macd_cmp.py`、`logs/iter22_streak_run.js`（附錄 B 原樣），用法見設計附錄 B。
3. **反證**：`test_iter22` 的執行器遇到第一個失敗就停；逐一執行的方法見 `logs/iter22_contrast.log` 末段。
4. **快取**：使用者第一次開網站要強制重新整理（設計第六節最後一列：舊 `app.js` 配新 `latest.json` 時新訊號頁會出錯）。
5. **使用者的 8000**：本輪已執行 `export`，`site/data` 已含 `et`、`eg`。
6. 本輪尚未 commit。`git status`：
   - 修改 5 個檔（`README.md`、`site/app.css`、`site/app.js`、`site/stock.js`、`twstock/export.py`）。
   - 新增 `tests/test_iter22.py`、`docs/iterations/22/`。
