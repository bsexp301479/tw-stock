# 第 24 輪｜PG 開發紀錄：股利與填息、ETF 除息入表、收集紀錄

- 作業日期：2026-11-16（週一）22:49～23:05（台灣時間）。
- 依據：`24/03-design.md` 第十二節（第 3 項依協調者調整）、附錄 A、附錄 B；`24/02-pm.md` 3-1～3-3。
- 結果：**全部步驟完成，沒有失敗、沒有重試**。外部請求 12 次；資料庫寫入只有 `backup`、`setup-db` 兩次、`events` 回補一次。

---

## 一、開工前提

| # | 前提 | 結果 |
|---|---|---|
| 1 | 使用者確認 11/16 晚上 `collect --catch-up` 與 `check` 正常 | ✅ 協調者轉達：使用者回報 22:46 結束、全部齊全；`check` 無異常；同意現在作業，作業期間不收集 |
| 2 | 日期 11/17 起或第 1 項已確認 | ✅ 第 1 項已確認 |
| 3 | HEAD／`git status` | ⚠️ 設計寫的 `a739f23` 已不成立：HEAD 是 `004c456`（之後 commit 了第 25～28 輪，只改 `site/`、`tests/`）。`git status` 只有未追蹤的 `docs/iterations/24/` 與 3 個 fixture。依協調者指示改成「先在 scratchpad 副本驗證」（第四節） |
| 4 | 沒有進行中的收集 | ✅ 22:49 查 `collect_runs`：最大 `run_id` 18（`catch-up`，22:45:06～22:46:35，`ok`，匯出 25.3 秒），`finished_at` 為 NULL 0 列。作業結束時仍是 18、0 列 |

---

## 二、基線（步驟 1）

- 資料日 **2026-11-16**；`collect_runs` 最大 18；`stocks/` 2,000 個檔（設計基線 1,999，11/16 多 1 檔）。
- `price_events` 各來源／類型：`TWT49U` 息 827、權 69、權息 62；`TPEX_EX` 息 606、權 67、權息 48；`TWTAUU` 減 21；`TWTB8U` 面 3（共 1,703，含 11/16 的 2 筆）。
- `python3 logs/iter24_db.py base`：`(1701, -936250043)`，**和設計 11/14 實測相同**。
- 腳本：附錄 B 存成 `logs/iter24_cmp.py`、`logs/iter24_db.py`（和 SA 的 `sa24/cmp.py`、`sa24/iter24_db.py` 逐位元組相同）。
- `logs/iter24_before/`：要改的 12 個檔原檔；`price_events.json`（全表 1,703 列，不含新欄，`dump_events.py` 只 SELECT）。
- `logs/iter24_base/`：`site/data` 複製（run 18 收集時匯出，之後 `collect_runs` 沒有變，直接當基線）。
- 舊程式匯出計時（PM 上限的比較基準）：在工作目錄用舊程式 `export` 一次 **25.6 秒**（real 25.90）；輸出和 `logs/iter24_base` 比較：2,375 個檔，除了 `latest.json` 的 `status.exported_at` 之外 0 個不同。

## 三、備份（步驟 2）

- 時間：**2026-11-16 22:50:06～22:50:15**（早於任何資料庫寫入；第一次 `setup-db` 是 22:52:59）。
- 檔案：`/Users/wudongliang/ClaudeWorkSpace/_backups/TwStock_20261116_225006.bak`，**108,691,456 bytes（103.7 MB）**，`RESTORE VERIFYONLY` 通過。

---

## 四、scratchpad 副本驗證（步驟 3，取代設計第十二節第 3 項）

- 副本：`rsync -a --exclude .env --exclude .git --exclude site/data --exclude logs --exclude _archive` 複製兩份到 scratchpad `pg24/proj`（套用）、`pg24/orig`（舊檔，反向驗證用）。兩份都沒有 `.env`。
- 附錄 A 從 03-design 第 490～1609 行抽出，和 SA 的 `sa24/a_code.diff` **逐位元組相同**。3 個 fixture 和 `sa24/proj/tests/fixtures/` 相同。

### 4-1 `patch -p1 --dry-run --verbose`（Apple patch 2.0-12u11）

| 檔案 | hunk 結果 |
|---|---|
| `README.md` | 4 個，全部原位 |
| `site/app.css` | 1 個，**fuzz 1、offset 54 行**（後文那一行 `@media (max-width:480px){…hl-sub…}` 第 27 輪改過） |
| `site/index.html` | **1 個 reject**（`?v=` 三行第 25～28 輪都改過） |
| `site/stock.js` | 5 個：#1、#2 原位；#3 offset 24、#4 offset 6、#5 offset 23；**沒有 fuzz** |
| `tests/test_iter24.py`（新） | 原位 |
| `twstock/` 8 個檔 | 全部原位，沒有 offset、fuzz |

### 4-2 合併內容

- `site/app.css`：fuzz 後的位置檢查過，`.dv-tbl` 那一行插在第 23 輪 `.hl-sub{display:none}table.pf-tbl…` 那一行之後、第 27 輪 `@media (max-width:480px)` 之前（第 320 行），和設計意圖相同（第 23 輪那一行之後）。之後第 28 輪的 CSS 沒有 `.tbl th`／`.tbl td` 的左右內距規則會蓋掉 `.dv-tbl`（8001 實測 375 寬表格 309 px，見第九節）。
- `site/stock.js`：
  - 股利卡插入點（hunk #3）：第 27 輪把基本面分頁改成 `tab === 'fund' ? … : …`，卡片仍落在月營收／季報 grid section 的 `</section>` 之後、同一個 `tab === 'fund'` 分支裡，和設計意圖相同。
  - `inst.net`（#4）、圖例 `合計${mode === '日' ? '' : '（每日相加）'}`（#5）：`mode` 在第 28 輪的 `showLegend` 裡仍是同一個變數。
  - 第 28 輪籌碼分頁的累計圖沒有用 `inst.net`，沒有改（設計沒有列）。
- `site/index.html`：reject 的 hunk 只有 `?v=`。依 `tests/test_iter23.py` 的 `test_version_hash`（`sha1` 前 8 碼）對**合併後**的檔案重算，只改這兩行：
  - `app.css?v=7faadef3` → **`app.css?v=141ea2d8`**
  - `stock.js?v=2d561731` → **`stock.js?v=fd99de3d`**
  - `app.js?v=656083f0` 不變（`app.js` 沒改）。
  - 設計寫的 `8ff7e8b4`、`0a8a6929` 是以 `a739f23` 為基準，不適用。
- 其他檔案和附錄 A 完全相同。`git diff --stat`：12 個檔 **＋202／−46**（和設計一致）。

### 4-3 副本測試

- `tests/test_iter01`～`28` 逐檔執行：**全部通過**（`test_iter24` 16 個 `ok`；第 25～28 輪 6／5／14／12 個 ✅）。不需要為第 25～28 輪做任何額外修改。
- `node --check site/app.js`、`node --check site/stock.js`（node v14.17.1）：通過。
- 反向驗證：`orig` 副本（舊檔）放入新的 `test_iter24.py` 與 fixture，用逐一執行的小程式（每個測試各自 try）跑：**16 個全部失敗**（`parse_events_all`、`dividends` 不存在，`KeyError: 'events'`、`'events_at'`，QA-03 `AssertionError: 17`，其他字面斷言失敗）。

---

## 五、套用到工作目錄與 `setup-db`（步驟 4）

- 用副本驗證過的檔案覆蓋工作目錄（先確認工作目錄的 12 個檔和 `orig` 副本相同），逐檔 `cmp` 和 `proj` 相同。
- ⚠️ 過程中一次失誤：第一次的 shell 迴圈（zsh 不會把字串變數拆成多個字）只複製了 `tests/test_iter24.py`，**當時的 `setup-db` 兩次（22:52:59）是舊程式執行的**；舊 DDL 全部是 `IF` 開頭、可重複執行，資料庫沒有變化（`schema` 檢查：`etf_events` 不存在、3 欄 None、checksum 相同）。改用陣列重新複製後再執行正式的兩次：
- **新程式 `setup-db` 第 1 次 22:53:07、第 2 次 22:53:08**，兩次都成功、第二次不報錯；清單有「`etf_events`（第 24 輪另加 price_events 股利欄）」，最後仍是 `etf_holding_gaps`。
- `python3 logs/iter24_db.py schema`：`etf_events` 存在 True；`div_total`、`div_cash`、`stock_div` 的 `COL_LENGTH` 都是 9；checksum `(1701, -936250043)` 和 `base` 相同。
- 舊程式相容（設計第十三節第 8 點，靜態確認）：
  - 舊 `events.py` 第 91 行：`INSERT (stock_id, event_date, event_type, prev_close, ref_price, div_ref, source)`。
  - 舊 `export.py` 第 1481 行：`SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source, e.div_ref`。
  - 都列出欄位名稱；新欄位允許 NULL、`etf_events` 是獨立的表，所以舊程式不受影響。

## 六、回補（步驟 5）

- 指令：`python3 -u -m twstock events --start 2025-10-30`（以 `runpy` 執行同一個指令，結束時多印 `fetch.request_count()`；請求全部經由 `twstock/fetch.py` 的 `request`）。紀錄：`logs/iter24_events.log`。
- 22:53:32～22:54:04（32 秒），exit 0，**沒有重試**。
- **對外請求 12 次**（2025-10-30～2026-11-16，3 段 × 4 端點）。
- 輸出：`📌 除權息／減資／面額變更事件：股票 1703 筆、ETF 1151 筆（2025-10-30 ～ 2026-11-16）`。
- 回補後總筆數：`price_events` 1,703（和回補前相同，只補金額）、`etf_events` 1,151。
- 11/14 之後的新列（`fill` 不算，另外列出）：
  - 股票：`3714` 11/16 減（`TWTAUU`，無金額）、`5475` 11/16 權（`TPEX_EX`，`div_total` 6.1239、`div_cash` 0、`stock_div` 0）。
  - ETF 13 筆，都是 11/16 的息：上市 `00775B` 0.35、`00936` 0.16、`00951` 2.0、`00962` 0.08；上櫃 `00844B` 0.41、`00867B` 0.41、`00942B` 0.062、`00970B` 0.05、`009806` 0.4、`009807` 0.6、`00980B` 0.047、`00988B` 0.148、`00989B` 0.066。

## 七、匯出（步驟 6）

- `python3 -u -m twstock export`（紀錄：`logs/iter24_export.log`）：**25.5 秒**（real 25.84）；舊程式同條件 25.6 秒 → **差 −0.1 秒**（PM 上限 ＋3 秒以內 ✅）。
- 大小：`site/data` 全部 43,135,706 → 45,128,710 bytes；`stocks/` 36,862,409 → **38,855,413（＋1,993,004，約 ＋1.9 MB）**；`dv` 約 110.8 KB、`insti.n` 約 1,832.1 KB。
- 還原事件 1,732 筆（上櫃反推 31 筆）；「找不到除權息事件 4 筆」警告和改前相同。

## 八、比對與檢查（步驟 7、8）

### 8-1 `python3 logs/iter24_db.py fill`（`logs/iter24_fill.log`）

| 項目 | 結果 | 預期（設計第十一節） |
|---|---|---|
| checksum（≤ 11/13） | `(1701, -936250043)` | 和 base 相同 ✅ |
| `TWT49U` | 958 筆，`div_total` 958、`div_cash` 827、`stock_div` 0；息 827 中相等 827 | 相同 ✅ |
| `TPEX_EX` | 720 筆，`div_total` 720、`div_cash` 720、`stock_div` 720；息 606 | 相同 ✅ |
| 上市權／權息有 `div_cash` | 0 | 0 ✅ |
| `TWTAUU`、`TWTB8U` 有金額 | 0（20、3 筆） | 0 ✅ |
| `etf_events`（≤ 11/14） | `TPEX_EX` 630 筆／106 檔／有金額 630／息 630；`TWT49U` 508／113／508／508 | 相同 ✅ |
| ETF 在 `stocks`、市場別不符 | 0、0 | ✅ |
| 實例 | 2330 5.000011／6.000035／6.000035／7.000001；2421 息 5.24042、權 `div_total` 1.038318；5511 權息 16.223647／3.6／198.87165021；6488 2.0、5.7；6703 息 4.8、權 10.636365／0／100.00000916 | 和設計第四節相同 ✅ |
| `insti.n` 對資料庫 | 2,000 檔、495,230 列，**不同 0 列** | 0 ✅ |

### 8-2 `python3 logs/iter24_cmp.py logs/iter24_base site/data`（`logs/iter24_cmp.log`）：**回傳 0**

- 檔案數 2,375；`stocks/`、`latest.json` 以外不同 0；`latest.json`（去掉 `updated_at`、`status`）相同。
- `stocks/` 刪掉 `dv`、`insti.n` 後不同 0，`dv` 和 `ev` 不一致 0。
- `dv`：息 1,432、權息 110、權 38，合計 **1,580**；已填息 994、尚未填息 528、不再比較 20、配股 38（設計 11/13 為 992／530，11/16 多兩天收盤，有 2 筆由尚未填息變成已填息；合計與類型相同）。
- `insti.n`：比較 465,905 列，`n ≠ f+t+dl` 33,764 列（7.2%），最大差 1 張；資料日 11/16 有 172 檔。
- 測試跑完後再執行一次 cmp：結果相同（測試沒有動到 `site/data`）。

### 8-3 `python3 -m twstock check`（唯讀，`logs/iter24_check.log`）

- 事件一行：**`除權息事件最後成功：至 2026-11-16（2026-11-16 22:46）`**。
  - 這一行讀的是 run 18（舊程式的收集）的紀錄，舊紀錄沒有筆數，所以只寫日期（設計第九節第 15 項、第十三節第 7 點）；回補的筆數看第六節的輸出。
- 其他行和改前相同；**結果：無異常**，rc 0。

---

## 九、工作目錄測試與 `?v=`（步驟 9）

- `tests/test_iter01`～`28` 逐檔執行：**全部通過**（`logs/iter24_tests.log`）；`node --check` 兩個檔通過。
- 最終 `index.html`：`app.css?v=141ea2d8`、`app.js?v=656083f0`、`stock.js?v=fd99de3d`；`test_iter23` 的 `test_version_hash` 通過。

## 十、8001 冒煙（步驟 10）

- 專案目錄背景執行 `python3 -u -m twstock serve --port 8001 --no-browser`；內建瀏覽器先 `fetch(…, {cache:'reload'})` 5 個檔再 `location.reload()`；實際載入 `app.js?v=656083f0`、`stock.js?v=fd99de3d`、`app.css?v=141ea2d8`。**8000 沒有碰**（使用者的 8000 仍在監聽）。
- 開始前 localStorage：`tw.todayTab=ov`、`tw.stockTab=k`。

| 寬度／色系 | 股票 | 表格寬 | 容器寬 | 頁面 `scrollWidth` |
|---|---|---|---|---|
| 375 淺色 | 2421、2330、6488、6669、8112、6703、5511 | 309 | 309（容器 `scrollWidth` 309） | 375 |
| 375 淺色 | 1213（沒有紀錄：「2025-10-30 起沒有除權息紀錄」） | — | — | 375 |
| 375 深色 | 6703（截圖確認，`--text2` 小字可讀） | 309 | 309 | 375 |
| 1024 淺色 | 上面 7 檔 | 720 | 958 | 1024 |
| 1024 淺色 | 1213 | — | — | 1024 |
| 1024 深色 | 2330（截圖確認） | 720 | 958 | 1024 |

- 卡片內容（375）：
  - 2421：2026/06/10｜5.2404｜--｜160｜08/28 第 56 個交易日（2/24 現增不列）。
  - 2330：4 列，最新在上；03/17 為「當天」；12/11 → 12/26 第 11 個交易日。
  - 6488：07/16 5.7 尚未填息「還差 903.00 元，+156.50%」（11/16 收盤，設計 11/13 為 850.00 元）；12/31 2 → 01/05 第 3 個交易日。
  - 6669：09/02 除權｜--｜有｜7,800｜--；06/22 144.3915 → 07/02 第 9 個交易日。
  - 8112：07/06 除權息｜--｜--｜92.9｜08/11 第 26 個交易日。
  - 6703：07/16 除權｜--｜100.00｜117｜--；03/26 4.8｜不再比較「07/16 配股後」。
  - 5511：07/09 除權息｜3.6｜198.87｜79.7｜尚未填息「還差 8.40 元，+11.78%」。
- 卡片都在月營收／季報 grid 之後（`previousElementSibling` 是 `.grid`）。
- ETF：ETF 列表頁 `scrollWidth` 1024；0056 個股頁只有「走勢／籌碼」分頁、沒有股利卡。
- 2330 走勢分頁法人圖例：日 K「外資 −8,466；投信 −2,303；自營 +3,086；合計 −7,684」（三者相加 −7,683，差 1 張，用官方合計），「合計」有 `title`；週 K 顯示「合計（每日相加）」。
- 主控台錯誤 0、警告 0。
- 收尾：刪除新增的 `tw.kmode`，localStorage 恢復為 `tw.todayTab=ov`、`tw.stockTab=k`；視窗恢復 preset desktop；`pkill -f "twstock serve --port 8001"` 後 `lsof -iTCP:8001 -sTCP:LISTEN` 0 列。

---

## 十一、與設計的差異

1. **基準 commit**：設計以 `a739f23` 為基準，實際是 `004c456`；`app.css` fuzz 1、`stock.js` 3 個 hunk 有 offset、`index.html` reject，合併內容見 4-2。
2. **`?v=`**：`app.css?v=141ea2d8`、`stock.js?v=fd99de3d`（設計的 `8ff7e8b4`、`0a8a6929` 不適用）。
3. **`setup-db` 多跑兩次舊程式**（見第五節），沒有任何資料庫變化；新程式的兩次照設計執行。
4. **回補區間** 2025-10-30～2026-11-16（作業在 11/16 晚上，設計假設 11/17 起），請求數同樣 12 次。
5. 數字以 11/16 資料日為準：`stocks/` 2,000 檔、四類 994／528／20／38、`insti.n` 差 1 張 33,764 列、11/16 有 172 檔；類型與合計 1,580 和設計相同。
6. 程式內容和附錄 A 相同，沒有額外修改；測試 0 行修改。

## 十二、給 QA 的注意事項

1. 數字以 PG 匯出當時（資料日 **2026-11-16**、run 18、匯出 22:54）為準；`site/data` 之後若有新的收集會變。
2. 基線：`logs/iter24_base/`（改前 `site/data`）、`logs/iter24_before/`（12 個原檔、`price_events.json`）。反證可用 `logs/iter24_before/` 的原檔放到暫存副本。
3. `check` 的事件一行目前只有日期（run 18 是舊程式寫的紀錄）；**使用者套用後第一晚的收集**才會有「股票 n 筆、ETF m 筆（含往回 7 天重查）」，請在那之後確認和收集輸出相同。
4. 第一晚之後 2～3 晚看 `collect_runs.export_seconds`：只在有新資料或補匯出時有值（F24-7 驗收 #10）。
5. 11/16 新的 15 筆事件（第六節）不在 `fill` 的 ≤ 11/14 範圍，獨立驗算時請另外處理。
6. `5475` 11/16 上櫃「權」：`div_cash` 0、`stock_div` 0、`div_total` 6.1239（可能是現增），可順便看分類與 `dv` 是否不列。
7. 8000 是使用者的伺服器，不要碰；第 23 輪起 `?v=` 會讓一般重新整理就拿到新程式。
8. 沒有 commit；`git status` 為 12 個修改檔＋未追蹤 `docs/iterations/24/`、`tests/test_iter24.py`、3 個 fixture。
