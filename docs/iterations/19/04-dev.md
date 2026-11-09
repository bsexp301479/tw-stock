# 第 19 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-09（週一）深夜
- 依據：
  - `03-design.md`：第九節步驟、附錄 A 的 diff。
  - `02-pm.md`：範圍與驗收。
  - 使用者決定：接受 SA 的設計與第十節的 12 點調整；D28-1～4 照預設，由 PG 執行 `backup`、`setup-db`、回補。
- 本輪項目：F19-1、F19-2 **全部完成**。附錄 A 原樣套用：`README.md`、`site/stock.js`、`events.py`、`db.py`、`export.py`、測試檔與 2 個 fixture 和 SA 原型（scratchpad `sa19/proj/`）逐位元組相同。
- 和設計唯一的不同：`__main__.py` 的說明多改 1 行（使用者要求同步更新，見第三節）。
- 資料日 **2026-11-09**；`collect_runs` 最大 `run_id` 從頭到尾都是 **14**（共 13 列），沒有進行中的收集，也沒有安裝排程（`launchctl`、`crontab` 都查不到）。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；從 scratchpad 只複製測試檔與 fixture，沒有複製 `.env`。
  - 沒有執行 `collect`、`history`、`_archive/`、還原；沒有刪除舊備份。
  - **外部請求 12 次**，全部經過 `fetch.request`（回補，上限 24 次）。
  - 資料庫寫入：`backup` 1 次、`setup-db` 2 次、回補 1 次、`export` 2 次（基線、新程式）。
  - 8001 測完已關閉；沒有碰 8000。預覽時設定的 `tw.kmode`、`tw.kadj` 已刪除（預覽前沒有任何 `tw.` 鍵），視窗已恢復桌面大小。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/collectors/events.py` | ＋16／−12 | `_SOURCES` 第 7 項（減除股利參考價欄名）；`parse_events` 選用欄位 `div_ref`；MERGE 多一欄（`COALESCE`） |
| `twstock/db.py` | ＋2 | `IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE ... ADD div_ref DECIMAL(10,2) NULL` |
| `twstock/export.py` | ＋20／−8 | `rights_kind()`；讀 `e.div_ref`；`_price_events` 帶 `k`；`ev` 輸出 `k`（有值才有） |
| `site/stock.js` | ＋25／−11 | `evName`、`evMark`、`CASH_INC_TIP`；`barChange()`；標記、圖例「當週」「月」、事件行、漲跌 `title`；股本變動註記；還原鈕說明 |
| `README.md` | ＋3／−3 | `setup-db` 欄位清單、`events` 指令說明、個股價格段 |
| `twstock/__main__.py` | ＋1／−1 | `events` 說明行 |
| `tests/test_iter19.py`（新） | 165 行 | 7 個測試 |
| `tests/fixtures/twt49u_rights_mini.json`、`exdailyq_rights_mini.json`（新） | 8＋117 行 | 官方回應精簡版 |

- `git diff --stat`：**6 個檔，＋67／−35**（程式＋README 不含 `__main__.py` 為 ＋66／−34）。
  - 設計寫 ＋63／−33，是 `diff -ruN` 的計算口徑；內容和原型逐位元組相同。
  - PM 估約 70、上限約 90，在範圍內。
- 基線副本：`logs/iter19_before/`（`events.py`、`db.py`、`export.py`、`stock.js`、`price_events.json` 全表 1,699 列、`snapshot.log`）。
- 新增的工作腳本（`logs/` 在 `.gitignore` 中）：
  - `logs/iter19_snapshot.py`（20 行）：改表前唯讀快照，匯出 `price_events` 全表。
  - `logs/iter19_dbcheck.py`（54 行）：唯讀 SQL 比對；`--after` 檢查回補後的 `div_ref` 比例。
  - `logs/iter19_compare.py`（54 行）：隔離比對，只允許 `stocks/*.json` 的 `ev[].k`；`--keep-new` 反證。
  - `logs/iter19_recalc.py`（104 行）：唯讀重算，**不 import `export`**，自己寫分類與週／月聚合。
  - `logs/iter19_js.js`：SA 的 `a5_js.js`，只改第 1 行註解。

---

## 二、執行步驟與結果

### 步驟 1：備份

- 22:26:06 `python3 -u -m twstock backup`：產生 **`../_backups/TwStock_20261109_222606.bak`（101.7 MB）**，RESTORE VERIFYONLY 通過。早於任何程式修改。

### 步驟 2～3：現況與基線

- `logs/iter19_before/snapshot.log`：
  - 資料日 11/09；`run_id` 14（21:26:57～21:28:23 完成）；`finished_at` NULL 0 列。
  - `price_events` 1,699 筆（2025-10-30～2026-11-06）；`div_ref` 欄不存在。
  - 各來源與類型：`TPEX_EX` 息 605／權 65／權息 48；`TWT49U` 息 827／權 69／權息 62；`TWTAUU` 減 20；`TWTB8U` 面 3。
- 基線 `export`（舊程式、舊資料）：24.9 秒（`logs/iter19_export_before.log`）。`site/data` 複製到 `logs/iter19_base/`。

### 步驟 4：先放測試

- 從 scratchpad `sa19/proj/tests/` 複製 `test_iter19.py` 與 2 個 fixture；測試檔和附錄 A 逐字相同。
- 舊程式跑 `test_iter19` → **失敗 ✅**：`parse_events` 沒有 `div_ref`（`logs/iter19_contrast.log`）。

### 步驟 5～6：套用程式，立刻 `setup-db` 兩次

- 附錄 A 去掉測試檔那一段（已放入），`patch -p1 --dry-run` 通過後正式套用 5 個檔，沒有 `.orig`／`.rej`。
- `node --check site/stock.js`、`site/app.js` 通過。
- 緊接著 `setup-db` 兩次都成功，第二次沒有報錯（可重複執行）。
- `iter19_dbcheck.py`（`logs/iter19_dbcheck_setup.log`）：
  - `div_ref` 為 `decimal(10,2)`、可為 NULL。
  - 列數 1,699 → 1,699；新增 0、消失 0、既有欄位改變 0。
  - `div_ref` 全部 NULL。
  - **✅ 全部符合**。

### 步驟 7：回補

- 指令以 `__main__.py` 為準：`events --start 2025-10-30`。
  - 用 `main(['events', '--start', '2025-10-30'])` 執行，結果和 `python3 -u -m twstock events --start 2025-10-30` 相同；另外印出 `fetch.request_count()`。
- 22:28:11 開始，耗時 34.1 秒，rc 0（`logs/iter19_backfill.log`）。
- 輸出「除權息／減資／面額變更事件：1699 筆（2025-10-30 ～ 2026-11-09）」。
- **請求 12 次**（3 段 × 4 個端點，沒有失敗、沒有重試），等於設計的預估。
- `collect_runs`：回補前後都是最大 `run_id` 14、13 列。`events` 指令不寫執行紀錄，這段期間也沒有其他收集。
- `iter19_dbcheck.py --after`（`logs/iter19_dbcheck_after.log`）：
  - 列數 1,699 → 1,699；新增 0、消失 0、**既有欄位改變 0**：官方沒有修正值，也沒有 11/07 之後的新事件。
  - `div_ref` 非 NULL 的比例：

    | 來源 | 類型 | 有值 |
    |---|---|---|
    | `TWT49U` | 息 | 827／827 |
    | `TWT49U` | 權 | 69／69 |
    | `TWT49U` | 權息 | 62／62 |
    | `TPEX_EX` | 息 | 605／605 |
    | `TPEX_EX` | 權 | 65／65 |
    | `TPEX_EX` | 權息 | 48／48 |
    | `TWTAUU` | 減 | 0／20 |
    | `TWTB8U` | 面 | 0／3 |

  - `div_ref` 高於前收的列：0。
  - **✅ 全部符合**。

### 步驟 8：新程式匯出、比對、重算

- 新程式 `export`：**25.0 秒**（基線 24.9 秒，多 0.1 秒；`logs/iter19_export_after.log`）。
- 比對 `iter19_compare.py logs/iter19_base site/data`（`logs/iter19_compare.log`）：
  - `stocks` 1,999 檔、`etfs` 8 檔、`etfp` 363 檔、`latest.json`、`screen.json` 都相同。
  - 剔除 `ev[].k` 後逐值相同。
  - `k` 只出現在「權」「權息」，值只有 `s`／`c`／`sc`。
  - 分類：**權 c 96、權 s 38、權息 s 99、權息 sc 11，合計 244 筆、230 檔**。
  - `stocks/` 合計 +1,963 B。
  - **✅ 相同（只有允許的差異）**。
  - **`--keep-new` 反證**：判定 230 個 `stocks` 檔不同，rc = 1 ✅（`logs/iter19_compare_keepnew.log`）。
- 重算 `iter19_recalc.py site/data`（`logs/iter19_recalc.log`），**全部符合**：

| # | 項目 | 結果 |
|---|---|---|
| ① | 資料庫自己分類，和 `ev[].k` 逐筆比對 | ✅ 0 筆不同；有分類筆數相同（244）。資料庫的「權」「權息」全部在匯出裡 |
| ① | `c ≥ 87`、`sc ≥ 11` | ✅ c 96、sc 11 |
| ② | 2-2 節樣本 | ✅ 2421 2/24 `c`、3189 1/26 `c`、6669 9/2 `s`、8112 7/6 `sc`、5284／7610／1529／2464／2614 權息 `sc`、2421 6/10 息沒有 `k` |
| ③ | 6-5 節 11 列的原始價漲跌與漲跌幅 | ✅ 和設計逐列相同；每列都等於還原的漲跌幅 |
| ④ | 全市場週／月 K | ✅ 129,192 根（含事件 3,442 根）：原始（新）和還原的漲跌幅 0 根不同 |

- c 96 比分析師的 87 多 9 筆：87 是「可對照官方的 122 筆」；資料庫的「權」是 134 筆，範圍包含 2025-11～12 的上市事件。重算和匯出逐筆一致，不是錯誤。
- node 驗算 `node logs/iter19_js.js site/stock.js site/data`（`logs/iter19_js.log`）：
  - 和 SA 的 `a5_js.txt` 只差 2 行：6186 月 K 2026-08 的 8/26 事件，現在顯示「現增｜除權（現金增資）」。
  - 原因：SA 的資料沒有 `k`，回補後資料庫判為 `c`。漲跌（−3.94、−10.96%）相同。
  - 全市場一致：「bars 129192 raw≠adj pct 0 no-ev bars unchanged 125750」。

### 步驟 9：測試

- `test_iter01`～`test_iter19`：**19 個全部通過**（`logs/iter19_tests.log`），舊測試沒改。
- `node --check`：`stock.js`、`app.js` 通過（node v14.17.1）。
- 本輪新增的程式沒有 `.at(`；`stock.js` 原有的 `.at(` 只在瀏覽器執行，不在測試取出的函式內。

### 步驟 10：8001 預覽（`site/`，真實匯出資料）

- 先用 `fetch(..., {cache:'reload'})` 刷新 `stock.js`、`app.js`、`app.css`、`index.html` 與資料檔，再重新整理。確認頁面載入的 `stock.js` 含 `barChange`、還原鈕 `title` 是新文字。

| 項目 | 結果 |
|---|---|
| 2421 週 K（原始）標記 | 2026-02-23 那根「**2/24 現增**」，2026-06-08 那根「6/10 息」 |
| 2421 週 K 02/23 圖例 | 「**2026-02-23 當週**　開 147　高 155.5　低 144　收 152.5　**+9.02 (+6.29%)**　02/24 除權（現金增資）　前收 147　參考價 145.96」 |
| 2421 漲跌 `title` | 「期間含除權息等事件：前一根收盤先乘上參考價 ÷ 前收再相減」 |
| 2421 事件行 `title` | `CASH_INC_TIP`：「現金增資除權：股東可依持股比例出錢認購新股（不是無償配股），參考價依認購價計算」 |
| 6669 週 K 08/31（原始） | 「2026-08-31 當週…收 2,565　**+151.16 (+6.26%)**　09/02 除權（配股）　前收 7,800　參考價 2,614.99」；標記「9/2 權」（改版前 −4,635（−64.38%）） |
| 6669 月 K（原始），真實點擊「月」 | 「**2026-09 月**…收 2,090　**−288.64 (−12.13%)**　09/02 除權（配股）…」；最新一根「2026-11 月」；標記「9/2 權」「6/22 息」 |
| 375 寬（2421 週 K 原始） | `scrollWidth` = 375，沒有水平捲動；圖例「2026-11-09 當週」換行正常；標記「2/24 現增」「6/10 息」都看得到 |
| 主控台錯誤 | 0 |

- 觀察（不影響驗收，沒有改）：桌面與 375 寬時，「2/24 現增」的文字有一部分壓在旁邊的 K 棒上。這是 Lightweight Charts 標記文字的畫法，日 K 原本的「權」也一樣；文字仍然看得出來。
- 沒有重驗的項目：8112 日 K、4155 週 K、ETF 頁、深淺色切換。設計第九節列了這些，但使用者這次指定的檢查不含它們；node 驗算已涵蓋 8112、4155 的文字與數值。

---

## 三、和設計的差異

1. **`__main__.py` 多改 1 行**（設計第四節寫「不用改」）：
   - 使用者要求同步更新 `__main__.py` 的說明，所以只把模組說明的 `events` 一行改為「補抓除權息／減資／面額變更事件（還原價格用；第 19 輪起另存減除股利參考價，分辨配股與現金增資）」。
   - `argparse` 的 `help` 與指令行為都沒有改。
   - `db.py` 的 `setup-db` 輸出（「第 11 輪另加 stocks.shares」）沒有加上 `div_ref`：設計沒有要求，README 已列這一欄。
2. **測試檔不經 `patch` 套用**：步驟 4 先放測試，所以第 5 步套用時從附錄 A 去掉測試檔那一段。結果和附錄 A 相同。
3. **c 的筆數是 96**（設計預期 ≥ 87）：原因見步驟 8，符合設計的條件。

除上述之外沒有差異。比對、重算、node 驗算的數字和設計第 2-2、6-5 節相同。

---

## 四、給 QA 的提醒

- 比對資料夾：
  - `logs/iter19_base/`：舊程式、回補前。
  - `site/data`：新程式、回補後。
  - 兩次匯出前後 `run_id` 都是 14。
- 回補沒有改變既有欄位：`iter19_dbcheck.py --after` 的「既有欄位改變 0」。所以除了 `k`，`ev`、`prices.ch` 都沒有變。
- 反證方式：
  - `logs/iter19_before/` 的 4 個程式檔放到暫存副本（不含 `.env`）跑 `test_iter19`，應該失敗。
  - `iter19_compare.py --keep-new` 應該 rc = 1。
- 舊程式相容：舊程式不讀 `div_ref`，資料庫加欄後仍可執行（設計第七節）。
- 若之後要還原資料庫：備份檔 `../_backups/TwStock_20261109_222606.bak`。還原由使用者自行執行。
- 使用者每晚收集後會自動 `export`，之後的匯出都會有 `k`。
- 更新後第一次開個股頁若還是舊圖例（沒有「當週」），強制重新整理即可（瀏覽器快取 `stock.js`）。
- 本輪尚未 commit。`git status`：
  - 修改 6 個檔。
  - 新增 `tests/test_iter19.py` 與 2 個 fixture、`docs/iterations/19/`。
