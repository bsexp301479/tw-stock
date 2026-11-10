# 第 21 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-10（週二）晚上
- 依據：
  - `03-design.md`：第七節步驟、附錄 A 的 diff 與 `tests/test_iter21.py` 全文。
  - `02-pm.md`：範圍與驗收。
  - 使用者回覆「進 PG」。開始前第 20 輪已依使用者指示 commit 並推送（`ed7bf1c`）。
- 本輪項目：F21-1 **完成**。照附錄 A 原樣套用，**和設計沒有不同**。
- 資料日 **2026-11-10**；`collect_runs` 最大 `run_id` 從頭到尾都是 **15**，沒有進行中的收集。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - **外部請求 0 次、資料庫寫入 0 次**；只有唯讀 SELECT（`collect_runs`）與 `export` 兩次。
  - `export` 只寫 `site/data/`：基線一次、新程式一次。
  - 沒有執行 `collect`、`history`、`setup-db`、`backup`、還原。
  - 8001 測完已關閉；沒有碰 8000。
  - 瀏覽器已恢復桌面大小與淺色。8001 的 localStorage 預覽前沒有任何鍵；預覽時新增的 `tw.hlmin` 已刪除。

---

## 一、修改的檔案與行數

| 檔案 | ＋／−（`git diff --numstat`） | 內容 |
|---|---|---|
| `twstock/export.py` | ＋73／−3 | `HL_DAYS`、`HL_REV_DAYS`；`highlights()`、`highlight_revenue()`、`highlight_active()`；月營收查詢多取 `created_at`；`latest.json` 每檔股票的 `hl` |
| `site/app.js` | ＋32／−3 | 路由 `#/rank/hl`；模式切換「排行／選股／新訊號」；`HL_KINDS`、`hlTag`、`hlDims`、`renderHl` |
| `site/app.css` | ＋1／−0 | 標籤欄換行、靠左 |
| `README.md` | ＋2／−1 | 網站一覽加「近期新訊號」；新增說明段 |
| `tests/test_iter21.py`（新） | 175 行 | 7 個測試 |

- 程式＋README **＋108／−7**，和設計相同（PM 估約 115，上限 160）。
- 基線副本：`logs/iter21_before/`（`export.py`、`app.js`、`app.css`、`README.md`）。
- `site/data` 基線：`logs/iter21_base/`（基線程式 `export` 後複製）。
- 新增的工作腳本（`logs/` 在 `.gitignore` 中）：
  - `logs/iter21_cmp.py`：SA 的 `cmp.py`。
  - `logs/iter21_consistency.py`：當天事件對照 `screen.json`，並統計清單檔數。

---

## 二、執行步驟與結果

### 步驟 1：基線

- `collect_runs` 最大 15、`finished_at` 為 NULL 的列 0；`daily_prices` 最新 11/10。
- 複製基線檔案。
- 基線 `export`：24.7 秒，`latest.json` 729 KB（`logs/iter21_export_base.log`）。
- 把 `site/data` 複製到 `logs/iter21_base/`（45 MB）。

### 步驟 2：套用

- 從 `03-design.md` 取出附錄 A：
  - diff：`patch -p1 --dry-run` 通過後正式套用 4 個檔。
  - 測試：取第一個（也是唯一一個）python 區塊。
- 套用後 `export.py`、`app.js`、`app.css`、`README.md`、`tests/test_iter21.py` 和 SA 原型**逐字相同**。

### 步驟 3～4：測試、反證

| 項目 | 結果 |
|---|---|
| `node --check` | `app.js` 通過 |
| `test_iter01`～`21` | **21 個全部通過**（`logs/iter21_tests.log`）；舊測試沒有改 |
| 反證 | 暫存副本（scratchpad `r21/pg_contrast`，不含 `.env`）放 `logs/iter21_before/` 的 4 個檔，跑 `test_iter21` → 失敗（`export` 沒有 `highlights`；`logs/iter21_contrast.log`） ✅ |

### 步驟 5～6：匯出、比對

| 項目 | 結果 |
|---|---|
| 新程式 `export` | 25.5 秒（基線 24.7，＋0.8 秒）；`latest.json` 761 KB（＋32 KB）（`logs/iter21_export_new.log`） |
| 既有輸出 | `python3 logs/iter21_cmp.py logs/iter21_base site/data`（`logs/iter21_cmp.log`）：<br>• 檔案清單相同<br>• `latest.json` 以外 **0 檔不同**（`screen.json`、`stocks/`、`etfp/`、`etfs/` 逐位元組相同）<br>• `latest.json` 去掉 `hl`、`updated_at`、`status` 後相同 |
| `hl` | 931 檔、1,253 個事件；種類：`s3` 662、`rv` 189、`vu` 160、`t3` 122、`nh` 66、`t5` 49、`ae` 5。日期 11/04～11/10 |
| 和 SA 原型 | 全部股票的 `hl` 和 `r21/proj` 的輸出**完全相同** |
| 和選股一致 | `logs/iter21_consistency.py`（`logs/iter21_consistency.log`）：當天價量／法人事件 231 筆，加上全部營收事件，對照 `screen.json`、`latest.json` → **0 筆矛盾** |
| 清單 | 面向 ≥ 3：8 檔；≥ 2：94 檔 |

### 步驟 7：8001 預覽（專案 `site/`，真實資料）

| 項目 | 結果 |
|---|---|
| 1024 淺色 | 排行頁有「排行／選股／新訊號」。**真實點擊**「新訊號」→ `#/rank/hl`，8 列（創意、騰輝電子-KY、藥華藥、大甲、信邦、視陽、廣豐、天擎），標籤換行、日期灰字 |
| 門檻 | **真實點擊**「面向 ≥ 2」→ 94 列、`tw.hlmin = 2`；世芯-KY 為 2 面向，標籤「10 月營收創新高 11/10」「00992A 新增 11/10」 |
| 點列 | 切換門檻後**真實點擊**世芯-KY → `#/stock/3661`，hashchange **1 次** |
| 其他模式 | **真實點擊**「選股」→ `#/rank/screen?…`，選股頁正常；再點「排行」→ `#/rank`，排行 50 列 |
| 375 淺色、375 深色 | 頁面 `scrollWidth = 375`（沒有水平捲動）；面向、標籤在名稱旁；深色背景正常 |
| 主控台 | 錯誤攔截器整段操作 **0 個錯誤** |

---

## 三、和設計的差異

無。附錄 A 原樣套用；行數、輸出、比對結果和設計第二、五節相同（匯出時間差 0.2 秒）。

---

## 四、給 QA 的提醒

1. **基線**：
   - 改前程式：`logs/iter21_before/`。
   - 改前資料：`logs/iter21_base/`。
   - 若 QA 期間使用者又收集了（`run_id` > 15），`site/data` 會變；請改記錄 `run_id`，再用 `logs/iter21_before/` 的程式另外匯出比對。
2. **獨立驗算**：設計第八節（量比用成交額、新高嚴格大於、連買用金額、`vr`／`t5`／`a20` 先四捨五入；不要 import `highlights`）。
3. **主動 ETF**：11/10 應有 5 筆 `ae`：
   - 2891（00981A，11/05）
   - 3045（00982A，11/06）
   - 3044（00403A，11/09）
   - 4551（00981A，11/10）
   - 3661（00992A，11/10）
4. **375 寬**：
   - 名稱欄固定、標籤欄最小寬 12em，表格在卡片內橫捲（和其他排行相同）。
   - 標籤較多的列（例如視陽 6 個事件）會變高。
5. **使用者的 8000**：本輪已執行 `export`，`site/data` 已含 `hl`。
   - 若 8000 服務的是專案 `site/`，重新整理就會看到「新訊號」。
   - 若瀏覽器快取了舊的 `app.js`，要強制重新整理。
6. 本輪尚未 commit。`git status`：
   - 修改 4 個檔。
   - 新增 `tests/test_iter21.py`、`docs/iterations/21/`。
