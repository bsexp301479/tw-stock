# 第 20 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-10（週二）晚上
- 依據：
  - `03-design.md`：第六節步驟、附錄 A 的 diff 與 `tests/test_iter20.py` 全文。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「照建議 A，進 PG」：**D29-4 = A**，`tests/test_iter15.py` 第 99 行只刪第一段（ETF 頁沒有自選鈕），保留後兩段。
- 本輪項目：F20-1 **完成**；照附錄 A 原樣套用，**沒有和設計不同的地方**。
- 資料日 **2026-11-10**；`collect_runs` 最大 `run_id` 從頭到尾都是 **15**，沒有進行中的收集。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**（只有唯讀 SELECT 查 `collect_runs`）。
  - 沒有執行 `export`、`collect`、`history`、`setup-db`、`backup`、還原。
  - 8001 測完已關閉；沒有碰 8000。瀏覽器已恢復桌面大小與淺色；8001 的 `tw.watch` 預覽前沒有值，結束時已刪除，`tw.rspan` 也已刪除。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `site/app.js` | ＋22／−7 | `onEtfRow`（ETF 列表與自選頁共用）；`renderWatch` 分股票、ETF 兩張表；`etfWatchTable`；ETF 列表說明句刪「自選」 |
| `site/stock.js` | ＋1／−1 | 自選鈕在 ETF 頁也輸出 |
| `README.md` | ＋1／−1 | ETF 段兩處 |
| `tests/test_iter15.py` | ＋1／−1 | **D29-4 = A**：第 99 行刪掉「ETF 頁沒有自選鈕」那一段，其餘兩段不變 |
| `tests/test_iter20.py`（新） | 94 行 | 4 個測試 |

- 程式＋README **＋24／−9**，和設計相同（PM 估計約 45、上限 60）。
- 基線副本：`logs/iter20_before/`（`app.js`、`stock.js`、`README.md`、`test_iter15.py`）。
- `site/data` 雜湊：`logs/iter20_data_before.txt`（2,372 檔）。
- 新增的工作腳本：`logs/iter20_watch_compare.js`（SA 的 `q_watch_compare.js`，只改第 1 行用法說明）。

---

## 二、執行步驟與結果

### 步驟 1：基線

- `collect_runs` 最大 15、`finished_at` 為 NULL 的列 0、資料日 11/10。
- 複製基線檔案、記錄 `site/data` 雜湊。

### 步驟 2：套用

- 附錄 A 的 diff：`patch -p1 --dry-run` 通過後正式套用 3 個檔；套用後 `app.js`、`stock.js`、`README.md` 和 SA 原型逐字相同。
- `tests/test_iter20.py` 從附錄取出，和原型逐字相同（第一次取錯成第十節的 python 片段，發現後改取第二段，重新比對相同）。
- `tests/test_iter15.py` 第 99 行照設計附錄最後一段修改。

### 步驟 3～6：測試、反證、比對

| 項目 | 結果 |
|---|---|
| `node --check` | `app.js`、`stock.js` 通過 |
| `test_iter01`～`20` | **20 個全部通過**（`logs/iter20_tests.log`）；除了 D29-4 的 `test_iter15` 一處，舊測試沒改 |
| 反證 | 暫存副本（scratchpad `r20/pg_contrast`，不含 `.env`）放 `logs/iter20_before/` 的 `app.js`、`stock.js`、`README.md` 跑 `test_iter20` → `test_star_on_etf_page` 失敗 ✅（`logs/iter20_contrast.log`） |
| 股票表不變 | `node logs/iter20_watch_compare.js logs/iter20_before/app.js site/app.js site/data/latest.json`：全部 1,986 檔股票的自選卡**逐字相同**（785,067 字元），只有標題「自選股 → 自選」不同；股票 3 檔＋ETF 363 檔：ETF 列 363、「持股」連結 8、「無成交」3（`logs/iter20_watch_compare.log`） |
| `site/data` | 雜湊和步驟 1 完全相同（2,372 檔） |
| `git diff` | 不含 `twstock/` |

### 步驟 7：8001 預覽（專案 `site/`，真實資料）

| 項目 | 結果 |
|---|---|
| 主動 ETF 00981A（375 深色） | **真實點擊**「☆ 加入自選」→「★ 已加入自選」，`tw.watch = ["00981A"]`；重新整理後仍是已加入 |
| 只有 ETF | 自選頁：「自選」標題、沒有 1 日／5 日、沒有股票卡；「ETF」表 1 列（24.27、+5.25%、412,344 張、99.81 億，含「持股」連結）。另外掛錯誤攔截器從今日頁換回自選頁：**0 個錯誤** |
| 加入 2330 | **真實點擊**個股頁按鈕 → 自選頁股票表在上、ETF 表在下；375 寬頁面沒有水平捲動 |
| 1 日／5 日 | **真實點擊**「5日」→ 股票表表頭變成「外資5日…」、說明「近 5 日累計」；ETF 表表頭不變 |
| ETF 列表（1024 淺色） | 說明句變成「ETF 不計入首頁家數、成交額、類股資金流、排行與股票口徑的融資融券。」；**真實點擊** 0050 列 → `#/stock/0050`，有「☆ 加入自選」 |
| 1024 淺色自選頁 | 版面正常（截圖） |

- 主控台：一直列著一筆 `onSeg … app.js:1361` 錯誤，是 SA 預覽原型第一版時留下的舊紀錄（重新載入不會清掉）。專案目前第 1361 行不是 `onSeg`（是 ETF 卡那一行，`onSeg` 在第 1362 行且有 `if (stk)`）；本次預覽另外用錯誤攔截器實測 0 個新錯誤。
- 0056、006201 的點擊、取消、點「持股」到持股頁，SA 已用同一份程式在原型實測（`03-design.md` 第四節），本次沒有重做。

---

## 三、和設計的差異

無。附錄 A 原樣套用；行數、比對結果和設計第四節相同。

---

## 四、給 QA 的提醒

- 比對：`logs/iter20_before/app.js`（本輪前）與 `site/app.js`，用 `logs/iter20_watch_compare.js`。
- 反證：`logs/iter20_before/` 的 3 個檔放到暫存副本跑 `test_iter20`，應失敗。
- `site/data` 雜湊基線：`logs/iter20_data_before.txt`；本輪沒有 `export`，QA 也不需要。若使用者期間收集了（`run_id` > 15），雜湊會變，改記錄 `run_id` 說明。
- 預覽 8001 前先記下 `tw.watch`（本次預覽後已刪除，沒有值），結束時恢復。
- 主控台的舊錯誤紀錄見第二節說明；判斷要看行號或用錯誤攔截器。
- 本輪尚未 commit；修改在工作目錄（`git status`：4 個修改檔、`tests/test_iter20.py`、`docs/iterations/20/`；`logs/` 在 `.gitignore` 中）。
