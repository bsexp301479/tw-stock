# 第 18 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-09（週一）
- 依據：
  - `03-design.md`：第十二節步驟、附錄 A 的 diff。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「照建議，進 PG」：接受設計第十四節的 6 點調整：
    - 行數 ＋140（比上限多 5 行，主要是註解）。
    - 新「技術」組。
    - 不用「超賣」「超買」。
    - 子圖圖例不寫參考線文字。
    - 「平常的比例」不放畫面。
    - 條件 id 用 `ru`。
- 本輪項目：F18-1、F18-2 **全部完成**，沒有用到延後順序；照附錄 A 原樣套用，**沒有和設計不同的地方**。
- 資料日 **2026-11-06**；`collect_runs` 最大 `run_id` 從頭到尾都是 **13**，沒有進行中的收集。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**（只有唯讀 SELECT）。
  - 匯出 2 次：基線、新程式。
  - 沒有執行 `collect`、`history`、`setup-db`、`backup`、還原。
  - 8001 測完已關閉；沒有碰 8000。瀏覽器已恢復桌面大小與淺色，並清掉預覽時存的子圖選擇（`tw.osc`）。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/export.py` | ＋56／−2 | `calc_kd`、`calc_rsi`、`osc_stats`；`SCREEN_KEYS` 加 `k`、`kx`、`rsi` |
| `site/stock.js` | ＋63／−12 | `calcKD`、`calcRSI`、`OSC_OPTS`；子圖 MACD／KD／RSI 切換；十字線同步改用目前子圖；`oscLine` |
| `site/app.js` | ＋18／−2 | 技術組 3 個條件、`SCR_COLS` 的 `k`、`rsi`、`oscShare` |
| `site/app.css` | ＋1 | `.osc-line` |
| `README.md` | ＋2／−2 | 個股價格段、選股段 |
| `tests/test_iter18.py`（新） | 132 行 | 8 個測試 |

- 程式＋README ＋140／−18，和設計相同。
- 基線副本：`logs/iter18_before/`（`export.py`、`stock.js`、`app.js`、`app.css`）。
- 新增的工作腳本：
  - `logs/iter18_compare.py`（44 行）：隔離比對，只允許 `screen.json` 的 `k`、`kx`、`rsi`；`--keep-new` 反證。
  - `logs/iter18_recalc.py`（87 行）：唯讀重算，**不 import `export` 的計算函式**；日線從資料庫讀，還原事件讀匯出的 `ev`。
  - `logs/iter18_js_vs_py.js`：SA 的 node 比對腳本（逐字取出 `stock.js` 的 `adjFactors`、`aggregate`、`calcKD`、`calcRSI`）。

---

## 二、執行步驟與結果

### 步驟 1～2：基線

- `collect_runs` 最大 13、`finished_at` 為 NULL 的列 0、資料日 11/06。
- 本輪前程式 `export`：24.2 秒（`logs/iter18_export_before.log`）→ `site/data` 複製到 `logs/iter18_base/`。

### 步驟 3：套用與測試

- `patch -p1 --dry-run` 通過後正式套用，6 個檔案。
- `node --check`：`app.js`、`stock.js` 通過。
- `test_iter01`～`18`：**18 個全部通過**（`logs/iter18_tests.log`），舊測試沒改。
- **反證**：暫存副本（scratchpad，不含 `.env`）放 `logs/iter18_before/` 的 4 個檔跑 `test_iter18` → `export` 沒有 `calc_kd`，失敗 ✅（`logs/iter18_contrast.log`）。

### 步驟 4～5：新程式匯出、比對、重算

- 新程式 `export`：**24.9 秒**（基線 24.2 秒，+0.7 秒，上限 +2 秒；`logs/iter18_export_after.log`）。前後 `run_id` 13、資料日 11/06。
- 比對 `logs/iter18_compare.py logs/iter18_base site/data`（`logs/iter18_compare.log`）：
  - `stocks` 1,999 檔、`etfs` 8 檔、`etfp` 363 檔、`latest.json` 全部相同。
  - `screen.json` 只多 `k`、`kx`、`rsi`：`k` 有值 1,962 檔、`kx = 1` 437 檔、`rsi` 有值 1,957 檔；**396,944 → 420,622 B（+23.7 KB）**。
  - **✅ 相同（只有允許的差異）**。
  - `--keep-new` 反證：判定 `screen.json` 鍵不同，rc = 1 ✅。
- 重算 `logs/iter18_recalc.py site/data`（`logs/iter18_recalc.log`），**全部符合**：

| # | 項目 | 結果 |
|---|---|---|
| ① | 1,983 檔的 `k`、`kx`、`rsi` = 獨立計算 | ✅ 0 檔不同；今天無成交或沒有資料 19 檔 |
| ② | 條件檔數 | ✅ KD 黃金交叉（K < 20）220、RSI ≤ 30 1,017、RSI ≥ 70 8 |
| ③ | 2330 | ✅ K 16.7、D 16.1、黃金交叉、RSI 19.6 |
| ④ | 今天無成交的股票三個鍵都是 `null` | ✅ 19 檔 |

- node 比對 `logs/iter18_js_vs_py.js`（`logs/iter18_js_vs_py.log`）：**1,964 檔一致、0 檔不同**，19 檔略過（今天無成交或無資料）。

### 步驟 6：8001 預覽（`site/`，真實匯出資料）

| 項目 | 結果 |
|---|---|
| 2330 預設（清掉 `tw.osc` 後） | 子圖 MACD；技術面卡「偏空：0 多 6 空」與 6 個標籤不變；動能一行「K 16.7／D 16.1（K 低於 20），今日黃金交叉；RSI 19.6（低於 30）」 |
| 真實點擊「RSI」 | 子圖換成 RSI(14)，虛線 30、70，右側刻度標 30.0、70.0（375 深色截圖） |
| 十字線 | 滑鼠移到 RSI 子圖 → K 線圖例跟著換到 09/02，同步正常 |
| 重新整理 | 1024 寬重新開 2330，子圖仍是 RSI |
| 資料不足 | 7710（新上市，不足 15 根）：「資料不足，無法判讀」＋動能「K 45.9／D 48.6；RSI 資料不足（需 15 根）」 |
| 選股（375 淺色） | 技術組 3 條件，單獨 220、1,017、8；**真實點擊**勾選 KD 黃金交叉 → 網址 `?tv=0.5&kx=20`、「符合 76 檔」、上方「今日全市場：KD 黃金交叉（K < 20） 220 檔（11.2%）。…」、結果多「K值」欄 |
| 未選技術條件 | 沒有「今日全市場」一行 |
| 水平捲動 | 375、1024 都沒有 |
| 主控台錯誤 | 0 |

- ETF 頁（0056）在 SA 原型已驗：沒有切換鈕、沒有技術面卡；本次程式和原型相同，沒有重驗。

---

## 三、和設計的差異

無。附錄 A 原樣套用；比對、重算、node 比對的數字與設計第三、十三節相同。匯出時間 +0.7 秒（設計原型 +0.4 秒），在上限內。

---

## 四、給 QA 的提醒

- 比對資料夾：`logs/iter18_base/`（本輪前程式）、`site/data`（新程式）。資料庫沒有變，兩次匯出前後 `run_id` 都是 13。
- 反證：`logs/iter18_before/` 的 4 個檔放到暫存副本跑 `test_iter18`，應該失敗。
- node 是 v14，`logs/iter18_js_vs_py.js` 第 2 行有 `Array.prototype.at` 的 polyfill（只在腳本裡，網站不需要）。
- QA 若要再獨立一次，可以不用專案的還原係數，直接用 SQL 的 `price_events` 自己算（`iter18_recalc.py` 用的是匯出的 `ev`）。
- 抽 3 檔比對技術面卡原本 6 項：可用 `logs/iter18_before/stock.js` 放到暫存副本開 8001 對照（設計第八節第 4 點）。
- **11/09 起使用者每晚收集**，收集後會自動 `export`；資料日變了的話，條件檔數以當時重算為準。
- 本輪尚未 commit；修改在工作目錄（`git status`：5 個修改檔、`tests/test_iter18.py`、`docs/iterations/18/`；`logs/` 在 `.gitignore` 中）。
