# 第 16 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-08（週日）
- 依據：
  - `03-design.md`：第十二節步驟、附錄 A 的 diff。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「照建議，進 PG」：接受設計第十四節的 6 點調整，包括：
    - 不做回補指令。
    - 保留 OpenAPI `notice`，每天 +1 次請求。
    - 回補起日改為「今天 − 30 天」。
    - 不顯示剩餘交易日。
- 本輪項目：F16-1～F16-3 **全部完成**，沒有用到延後順序。
- 資料日 **2026-11-06**；`collect_runs` 最大 `run_id` 從頭到尾都是 **13**，沒有進行中的收集。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **資料庫寫入只有一次回補**（`write_alerts`，只寫上市注意股 285 列）。
  - 匯出 3 次：基線、回補前新程式、回補後新程式。
  - 沒有執行 `collect`、`history`、`setup-db`、`backup`、還原。
  - **外部請求 1 次**（回補，`www.twse.com.tw`，經 `fetch.request`）。
  - 8001 測完已關閉；沒有碰 8000。瀏覽器已恢復桌面大小與淺色。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/collectors/alerts.py` | ＋53／−11 | `TWSE_NOTICE`、`NOTICE_DAYS`、`_TAG`；`roc_date` 支援點分隔；`parse_alert` 去 HTML；`parse_twse_notice`、`fetch_twse_notice`；`fetch_alerts` 加上市注意與 `market`；`alert_summary`；拆出 `write_alerts` |
| `twstock/export.py` | ＋30／−3 | `disposal_span`、`_short`、`alert_board`；`dsp` 改合併區間；`latest.json` 新鍵 `alerts` |
| `site/app.js` | ＋22／−1 | `alertBoard(L)`；總覽分頁加清單；`#alMore` 切換 |
| `site/app.css` | ＋3 | `.al-grp`、`.al-row`、`.al-l`、`.al-why` |
| `README.md` | ＋2／−2 | 處置／注意股來源段、`site/` 一列 |
| `twstock/__main__.py` | ＋2／−2 | `collect`、`export` 說明 |
| `tests/test_iter16.py`（新） | 134 行 | 8 個測試 |

- 程式＋README 約 ＋112／−21，在 PM 上限 140 行內。
- 基線副本：`logs/iter16_before/`（`alerts.py`、`export.py`、`app.js`、`app.css`）。
- 新增的工作腳本：
  - `logs/iter16_dump_alerts.py`：唯讀匯出 `stock_alerts`。
  - `logs/iter16_backfill.py`：回補，可 dry-run。
  - `logs/iter16_compare.py`：`pre`／`post` 兩種比對。
  - `logs/iter16_recalc.py`：唯讀重算。

---

## 二、執行步驟與結果

### 步驟 1～2：基線

- `collect_runs` 最大 13、沒有 `finished_at` 為 NULL 的列、資料日 11/06、`stock_alerts` 175 列。
- 基線匯出 24.7 秒（`logs/iter16_export_before.log`），`site/data` → `logs/iter16_base/`。
- `stock_alerts` 全表 → `logs/iter16_alerts_before.json`（175 列）。

### 步驟 3：套用與測試

- 從 `03-design.md` 附錄 A 取出 diff，和 SA 的 `r16.diff` **逐位元組相同**。
- `patch --dry-run` 後套用，7 個檔案乾淨套用，沒有 `.orig`、`.rej`。套用後和 SA 原型 `proj/` 逐檔相同。
- `node --check site/app.js` 通過；`test_iter01`～`16` **全部通過**（`logs/iter16_tests.log`，16 個「全部通過」）。舊測試沒有修改。

### 步驟 3b：回補前比對（設計第五節第 1 次）

- 新程式匯出 24.3 秒，`site/data` → `logs/iter16_pre/`。
- `python3 logs/iter16_compare.py pre logs/iter16_base logs/iter16_pre` → **✅ 相同（只有允許的差異）**：
  - `dsp` 改變 1 檔：8099 `['2026-11-02', '2026-11-06']` → `['2026-11-02', '2026-11-11']`。
  - `alerts` 新鍵：`d` 9 檔、`n` 26 檔，5,368 B。
  - `stocks` 1,999、`etfs` 8、`etfp` 363 檔逐值相同；`screen.json` 相同。
- 反證 `--keep-new` → ❌ 不同（`latest.json` 鍵多 `alerts`、`latest.stocks 8099`）✅。

### 步驟 4：回補（1 次請求、寫入一次）

- `python3 logs/iter16_backfill.py --fetch`：
  - 查 115/10/09～115/11/08，原始 341 列、有效 285 列。
  - 原始回應存 `logs/iter16_backfill_raw.json`，dry-run 輸出存 `logs/iter16_backfill_dryrun.log`。
- 逐日有效筆數：

  | 日期 | 10/12 | 10/13 | 10/14 | 10/15 | 10/16 | 10/19 | 10/20 | 10/21 | 10/22 | 10/27 | 10/28 | 10/29 | 10/30 | 11/02 | 11/03 | 11/04 | 11/05 | 11/06 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 上市注意 | 13 | 16 | 18 | 16 | 15 | 13 | 12 | 10 | 14 | 18 | 16 | 10 | 10 | 12 | 9 | 23 | 24 | 36 |

  - 10/21～11/06 和設計第一節 1-2 的表**完全相同**，所以才寫入。
- 寫入前再確認一次 `collect_runs` 最大 13、沒有進行中的收集。
- `python3 logs/iter16_backfill.py --write`：「已寫入 285 列（MERGE，只含上市注意股）」。
- `stock_alerts`：175 → **460** 列（= 175 + 285，全部是新增）→ `logs/iter16_alerts_after.json`。

### 步驟 5～6：回補後匯出、比對、重算

- 新程式匯出 **23.7 秒**（基線 24.7 秒），`latest.json` 724 KB → 732 KB（`alerts` 8,799 B，PM 上限 15 KB）。
- `python3 logs/iter16_compare.py post logs/iter16_pre site/data` → **✅ 相同（只有允許的差異）**：
  - 上市股票 `alerts` 增加 36 檔（只多 `notice` 項目，既有項目不變）。
  - `ntc` 新增 36 檔；`alerts.n` 多 36 檔，全是回補的上市股票。
  - 上櫃股票完全相同。
- 反證 `--keep-new` → ❌ 不同（列出 `stocks/6672.json` 等）✅。
- `python3 logs/iter16_recalc.py site/data` → **全部符合**（`logs/iter16_recalc.log`）：

  | # | 檢查 | 結果 |
  |---|---|---|
  | ① | 6213 在 10/21～11/04 的注意 | **7 次**（10/22、10/27～10/30、11/02、11/04）≥ 6 ✅ |
  | ① | 2466、4526 在 10/27、10/28、10/29 | 都有 ✅（2466 另有 10/12～10/14） |
  | ② | 上市注意逐日筆數 = 原始回應 | 285 筆、18 天 ✅ |
  | ③ | 上櫃列、處置列逐值相同 | 175 列 ✅；新增的 285 列全是上市注意 ✅ |
  | ④ | `dsp`、`alerts.d` 起迄 = SQL 合併區間 | 9 檔，8099 [11/02, 11/11] ✅ |
  | ⑤ | `alerts.n` = SQL 當日注意 | **62 檔（上市 36、上櫃 26）** ✅；`ntc` 一致 ✅ |
  | ⑤ | 任抽 5 檔措施、原因 | 3441、3691（處置）、1416、1609（上市注意）、1569（上櫃注意）一致 ✅ |

- 回補後逐日注意（上市／上櫃）：10/28 16／20、10/29 10／18、10/30 10／16、11/02 12／17、11/03 9／12、11/04 23／24、11/05 24／21、11/06 36／26。10/27 以前只有上市（上櫃注意從 10/28 開始收）。

### 步驟 7：8001 預覽

| 項目 | 結果 |
|---|---|
| 總覽清單（375 × 812，淺色） | 即將處置 0 檔「無」、處置中 9 檔、今日注意 **62 檔**（預設列 10 檔）；卡高 **1,157 px = 1.42 屏**（≤ 1.5 ✅）；`scrollWidth` 375 ✅ |
| 「注意顯示全部」 | 71 列（9 + 62），按鈕變「注意只顯示 10 檔」；再按回 19 列 ✅ |
| 真實點擊大世科 8099 | 進入 `#/stock/8099`，頁首「處置中（至 11/06）」「處置中（至 11/11）」「注意」（個股頁本來就逐段列出，設計第 2 節不改）；瀏覽器返回回到 `#/today` 且清單在 ✅ |
| 名稱旁小標 | 8099「處」的提示「處置中（至 11/11）」✅；2360 致茂（上市）出現「注」✅；2330 沒有 |
| 選股「排除注意股」（`xt`） | 2360 → 排除（false），2330 → 保留（true）✅；上市有 `ntc` 的 36 檔 |
| 深色 375 | 可讀（截圖） |
| 1024 寬 | 卡高 1,139 px，`scrollWidth` 1024 ✅ |

- 伺服器紀錄只有 `favicon.ico` 404（網站本來就沒有）。
- 主控台有 2 筆 `ERR_CONNECTION_REFUSED`。來源是同一個瀏覽器分頁之前在 8001 關閉期間留下的請求，不是本輪網站程式產生的；8001 開著時沒有其他錯誤。

---

## 三、和設計的差異（預覽時發現，已修正）

1. **class 撞名 `.al-r`**：
   - 設計的第二行 class `.al-r` 和期貨卡既有的「今天換月」藍底標籤（`.al.al-r{background:var(--blue)}`，`app.css` 第 253 行）同名。
   - 結果是清單每一列第二行都變成藍底。SA 原型的截圖也有，當時誤判為文字選取。
   - 修正：改名為 `.al-why`（`app.js`、`app.css` 各 1 處），並在 `test_iter16` 加斷言：不可再用 `class="muted small al-r"`。
   - 期貨卡的 `.al-r` 不受影響。
2. **「今日注意」組名旁的檔數**：
   - 設計寫「注意組顯示全部的檔數」，原型卻顯示切片後的 10。
   - 修正：`grp(t, list, n = list.length)`，注意組傳 `A.n.length`，並加測試斷言。
- 以上兩點共 ＋3／−3 行，已包含在第一節的行數。改完後重新執行 `test_iter01`～`16`，全部通過，並在 8001 複驗。

---

## 四、給 QA 的提醒

- **資料庫已經有上市注意股**（460 列）。QA **不要重跑回補**，也不要打 `www.twse.com.tw`。要驗證就用：
  - `logs/iter16_backfill_raw.json`（原始回應）。
  - `logs/iter16_alerts_before.json`、`logs/iter16_alerts_after.json`。
  - `logs/iter16_recalc.py`（唯讀）。
- 比對資料夾：`logs/iter16_base/`（本輪前程式、回補前）、`logs/iter16_pre/`（新程式、回補前）、`site/data`（新程式、回補後）。
- 反證：拿 `logs/iter16_before/` 的 `alerts.py`、`export.py`、`app.js`、`app.css` 放到暫存副本跑 `test_iter16`，應該失敗。
- `test_iter03`、`04`、`05`、`06`、`07`、`11` 的輸出會多「⚠️ 上市注意股最近 30 天 0 筆」，因為模擬網站沒有新來源。屬預期（設計第十五節）。
- **11/09 起使用者每晚收集**，會用新的 `alerts.py`：
  - 收集輸出變成「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」，上市注意是 30 天總數，約 280 筆以上。
  - QA 期間若資料日變了，清單檔數以當時 SQL 重算為準。
- 本輪尚未 commit；修改在工作目錄（`git status`：6 個修改檔、`tests/test_iter16.py`、`docs/iterations/16/`）。
