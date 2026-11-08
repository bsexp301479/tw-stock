# 第 17 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-08（週日）
- 依據：
  - `03-design.md`：第十二節步驟、附錄 A 的 diff。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「照建議，進 PG」：接受設計第十四節的 6 點調整：
    - 「近 30 天」用 `days_label` 參數。
    - 歷史不足不標示。
    - 只計第 1～8 款。
    - 差一次只列一行。
    - 名稱旁不加小標。
    - QA 加 Q17-1 確認項。
- 本輪項目：F17-1、F17-2 **全部完成**，沒有用到延後順序；照附錄 A 原樣套用，**沒有和設計不同的地方**。
- 資料日 **2026-11-06**；`collect_runs` 最大 `run_id` 從頭到尾都是 **13**，沒有進行中的收集；`stock_alerts` 460 列不變。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**（只有唯讀 SELECT）。
  - 匯出 2 次：基線、新程式。
  - 沒有執行 `collect`、`history`、`setup-db`、`backup`、還原。
  - 8001 測完已關閉；沒有碰 8000。瀏覽器已恢復桌面大小與淺色。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/collectors/alerts.py` | ＋13／−6 | `fetch_alerts` 上市注意失敗只略過；`alert_summary(rows, days_label=False)`；`collect_alerts` 用 `days_label=True` |
| `twstock/export.py` | ＋57 | `clauses`、`watch_counts`、`alert_watch`、`COUNT_DOWN`、`WATCH_RULES`；近 30 交易日注意查詢；`latest["alerts"]["w"]` |
| `site/app.js` | ＋14／−1 | `watchGrp(W, S)`；清單第 4 組 |
| `site/app.css` | ＋1 | `.al-near` |
| `README.md` | ＋2／−2 | 處置／注意股段、`site/` 一列 |
| `twstock/__main__.py` | ＋1／−1 | `export` 說明 |
| `tests/test_iter17.py`（新） | 140 行 | 8 個測試 |

- 程式＋README ＋88／−10，在 PM 上限約 95 行內。
- 基線副本：`logs/iter17_before/`（`alerts.py`、`export.py`、`app.js`、`app.css`）。
- 新增的工作腳本：
  - `logs/iter17_compare.py`（43 行）：隔離比對，只允許 `alerts.w`；`--keep-new` 反證。
  - `logs/iter17_recalc.py`（84 行）：唯讀重算，**不 import `export`**，款別解析與規則 B 另寫一份。

---

## 二、執行步驟與結果

### 步驟 1～2：基線

- `collect_runs` 最大 13、`finished_at` 為 NULL 的列 0、資料日 11/06、`stock_alerts` 460 列。
- 本輪前程式 `export`：23.6 秒，`latest.json` 732 KB（`logs/iter17_export_before.log`）→ `site/data` 複製到 `logs/iter17_base/`。

### 步驟 3：套用與測試

- `patch -p1 --dry-run` 通過後正式套用，7 個檔案。
- `node --check`：`app.js`、`stock.js` 通過。
- `test_iter01`～`17`：**17 個全部通過**（`logs/iter17_tests.log`），舊測試沒改。
- **反證**：暫存副本（scratchpad，不含 `.env`）放 `logs/iter17_before/` 的 4 個檔跑 `test_iter17` → 在 `test_twse_notice_failure_isolated` 丟 `FetchError`，失敗 ✅（`logs/iter17_contrast.log`）。

### 步驟 4～5：新程式匯出、比對、重算

- 新程式 `export`：**23.1 秒**（基線 23.6 秒，沒有增加；`logs/iter17_export_after.log`）。前後 `run_id` 13、資料日 11/06。
- 比對 `logs/iter17_compare.py logs/iter17_base site/data`（`logs/iter17_compare.log`）：
  - `stocks` 1,999 檔、`etfs` 8 檔、`etfp` 363 檔、`screen.json` 全部相同。
  - `latest.json` 只多 `alerts.w`：12 檔（已達條件 2、差一次 10），**400 B**；`latest.json` 750,040 → 750,445 B。
  - **✅ 相同（只有允許的差異）**。
  - `--keep-new` 反證：判定 `latest.json alerts` 不同，rc = 1 ✅。
- 重算 `logs/iter17_recalc.py site/data`（`logs/iter17_recalc.log`），**全部符合**：

| # | 項目 | 結果 |
|---|---|---|
| ① | 11/06 `alerts.w` = 獨立計算（代號、級別、條件文字逐字） | ✅ 12 檔；已達條件 2360、3532 |
| ② | 回測 4 次上市處置 | ✅ 2466 10/29、4526 10/29（第一款連 3 日）、2466 11/03（第一款連 6 日等）、6213 11/04（10 日內 6 次） |
| ③ | 3167 不在 11/06 預警 | ✅ |
| ④ | 和處置清單沒有交集；8099、6213 不在 | ✅（處置 9 檔） |
| ⑤ | 解析不到款別的注意 | ✅ 0 筆 |
| ⑥ | `COUNT_DOWN = False` 時 11/06 已達條件 | 0 檔（供 Q17-1 參考） |
| ⑦ | 預警代號都在 `latest.stocks` | ✅ |

### 步驟 6：8001 預覽（`site/`，真實匯出資料）

| 項目 | 結果 |
|---|---|
| 組順序 | 即將處置 0、處置中 9、**接近處置（推算）已達條件 2 檔、差一次 10 檔**、今日注意 62 |
| 已達條件 | 致茂、台勝科各一行，右邊「已達條件」、第二行「第一款連 3 日」；背景透明（沒有撞到 `.al-r`） |
| 差一次 | 一行：全新、景碩、由田、科嶠、新唐、jpp-KY、中探針、訊芯-KY、環球晶、騰輝電子-KY；`title` 是條件（例：全新「第一款連 2 日、10 日內 5 次」） |
| 點擊 | 真實點擊台勝科 → `#/stock/3532`；返回 → `#/today`，清單仍在 |
| 375 × 812 | `scrollWidth` 375，沒有水平捲動；清單卡 **1,376 px**（第 16 輪 1,157 px，+0.27 屏，上限 0.5） |
| 深色、淺色 | 截圖都可讀；差一次連結淺色 `rgb(27,27,27)` |
| 1024 寬 | 沒有水平捲動，4 組都在 |
| 假資料 | `w: []` → 組名「已達條件 0 檔、差一次 0 檔」＋「無」；沒有 `w` → 不顯示第 4 組，其他 3 組照舊；條件文字含 `<b>x</b>"` 以文字顯示，沒有變成 HTML |
| 選股 | `SCREEN_CONDS` 沒有預警條件 |

---

## 三、和設計的差異

無。附錄 A 原樣套用；預覽與設計第二節 2-6 的量測相同（1,376 px、400 B）。

---

## 四、給 QA 的提醒

- 比對資料夾：`logs/iter17_base/`（本輪前程式）、`site/data`（新程式）。資料庫沒有變，兩次匯出前後 `run_id` 都是 13。
- 反證：`logs/iter17_before/` 的 4 個檔放到暫存副本跑 `test_iter17`，應該失敗。
- 重算腳本不 import `export`；QA 若要再獨立一次，可以只用 SQL＋自己的解析。
- **不要**為了驗證 F17-1 的失敗隔離去打 `www.twse.com.tw` 或模擬封鎖；`test_iter17` 已涵蓋。
- `test_iter03`、`04`、`05`、`06`、`07`、`11` 的輸出仍有「⚠️ 上市注意股最近 30 天 0 筆」，屬預期（同第 16 輪）。
- **11/09 起使用者每晚收集**，會用新的 `alerts.py`：
  - 收集輸出變成「注意 上市 c（近 30 天）／上櫃 d 筆」。
  - QA 期間若資料日變了：`alerts.w` 以當時重算為準；並請順便看 2360、3532 是否出現處置（Q17-1，設計第八節第 7 點）。
- 本輪尚未 commit；修改在工作目錄（`git status`：6 個修改檔、`tests/test_iter17.py`、`docs/iterations/17/`；`logs/` 在 `.gitignore` 中，`logs/iter17_*` 不會進 git）。
