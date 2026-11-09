# 第 18 輪｜System Analyst：設計規格

- 依據：`18/01-analyst.md`、`18/02-pm.md`（F18-1、F18-2；使用者已決定 D27 = A；不急的確認依 PM 建議：子圖預設 MACD、資料不足時寫「資料不足」不隱藏）。
- 作法（比照第 13～17 輪）：
  - 在 scratchpad `r18/` 建立兩份專案副本：`orig` = 目前程式（第 17 輪，28e43ad）、`proj` = 本設計。兩份都**不含 `.env`**、`_archive`、`logs`、`.git`。
  - 唯讀模擬匯出：`orig`、`proj` 各執行一次 `export`，只執行 SELECT，輸出寫到各自的 `site/data`（scratchpad），**沒有寫專案的 `site/data`**。帳密由 `r18/run_export.py` 以 setdefault 讀專案 `.env` 到環境變數，沒有印出或複製 `.env`。
  - 前後端一致性：`r18/q3_js_vs_py.js` 用 node 執行 `proj/site/stock.js` 逐字取出的 `adjFactors`、`aggregate`、`calcKD`、`calcRSI`，對每一檔股票的個股 JSON 計算最後一根，和 `screen.json` 比對。
  - 預覽：8001 提供 `proj/site/`，量測 375 × 812（深色、淺色）與 1024 寬。結束後已關閉 8001，沒有碰 8000；瀏覽器已恢復桌面大小、淺色。
  - 測試與反證：
    - `proj` 上跑 `test_iter01`～`18` 全部通過。
    - 本輪前的程式跑 `test_iter18` 失敗（`export` 沒有 `calc_kd`）。
  - 附錄 A 的 diff 已用 `patch -p1 --dry-run` 確認可乾淨套用到目前專案。
- 本文數字來自模擬匯出（**資料日 2026-11-06**，`collect_runs` 最大 `run_id` = 13）。
- **外部請求 0 次、資料庫寫入 0 次、沒有 DDL**。不改 `twstock/collectors/`、`__main__.py`。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（diff） |
|---|---|---|---|
| F18-2 | `twstock/export.py` | `KD_N`、`RSI_N`、`calc_kd()`、`calc_rsi()`、`osc_stats()`；`SCREEN_KEYS` 加 `k`、`kx`、`rsi`；`screen[code]` 加 `**osc_stats(...)` | ＋56／−2 |
| F18-1 | `site/stock.js` | `OSC_OPTS`、`calcKD()`、`calcRSI()`；子圖 MACD／KD／RSI 切換（`#oscSeg`、`#oscLeg`、`localStore('osc')`）；`buildCharts` 多兩個參數；十字線同步改用目前子圖；`oscLine()`：技術面卡動能一行；說明句 | ＋63／−12 |
| F18-2 | `site/app.js` | `SCREEN_CONDS` 加 `kx`、`rl`、`ru`（新「技術」組）；`SCREEN_GROUPS` 加「技術」；`SCR_COLS` 加 `k`、`rsi`；`oscShare()`：全市場比例一行；選股說明句加 KD、RSI | ＋18／−2 |
| F18-1 | `site/app.css` | `.osc-line` | ＋1 |
| 文件 | `README.md` | 個股價格段、選股段 | ＋2／−2 |
| 測試 | `tests/test_iter18.py`（新） | 9 個測試 | 132 |

- 程式＋README **＋140／−18**。PM 估約 115、上限約 135，**超過上限 5 行**。差在註解與 docstring（`export.py` 有 12 行是公式說明與「改一邊要改另一邊」的提醒），刪了不划算，見第十四節第 1 點。
- 建議實作順序：匯出 `calc_kd`、`calc_rsi`（先寫測試）→ `stock.js` 的 `calcKD`、`calcRSI` → 技術面卡 → 子圖切換 → 選股 → README。

---

## 一、公式（前端與匯出同一套）

### 1-1 KD(9,3,3) — `calc_kd(h, l, c)`／`calcKD(H, L, C)`

1. 前 8 根（索引 0～7）K、D 為空。
2. 第 9 根起：`RSV = (收 − 最近 9 根最低) ÷ (最近 9 根最高 − 最近 9 根最低) × 100`；最高 = 最低時 RSV = 50。
3. `K = 2/3 × 前 K + 1/3 × RSV`、`D = 2/3 × 前 D + 1/3 × K`；第一次計算時前 K、前 D = 50。
4. 今日黃金交叉：`前 K ≤ 前 D` 且 `K > D`；死亡交叉：`前 K ≥ 前 D` 且 `K < D`（死亡交叉只在個股頁顯示）。

### 1-2 RSI(14) — `calc_rsi(c)`／`calcRSI(C)`

1. 前 14 根（索引 0～13）為空。
2. 第 1～14 個漲跌：漲幅、跌幅各自平均（÷ 14）。
3. 之後 Wilder 平滑：`平均漲 = (前值 × 13 + 本次漲) ÷ 14`，跌同理。
4. `RSI = 100 − 100 ÷ (1 + 平均漲 ÷ 平均跌)`；平均跌 = 0 時 100；平均漲、跌都是 0 時 50。

### 1-3 輸入序列（和個股頁 K 線相同）

- **還原價**：每列的開高低收乘上 `_adj_factors` 的係數（和 `stock.js` 的 `adjFactors` 相同）。
- **成交判斷**：開、收都有值才算成交（`stock.js` `aggregate` 的條件）。
- **無成交日**：上市後的無成交日以前一個還原收盤畫一字線（高 = 低 = 收），**一起計算**。這和個股頁 K 線、MACD 的作法一致。
- **上市前的空值**：略過。
- **週、月 K**（個股頁）：用 `aggregate` 合併後的高低收計算，和日線一樣的公式。
- **選股**：只算日線最後一根；今天無成交（開或收為空）→ `k`、`kx`、`rsi` 都是 `null`（不符合任何條件）。

### 1-4 一致性驗證（`q3_js_vs_py.js`）

- 1,983 檔：**1,964 檔逐值相同**（`k`、`kx`、`rsi` 四捨五入到小數 1 位），**0 檔不同**；19 檔今天無成交或沒有資料，兩邊都是 `null`。
- 單元測試另外用 60 根的人造資料，直接以 node 執行 `stock.js` 的 `calcKD`、`calcRSI`，和 Python 逐根比對（`test_js_matches_python`）。

---

## 二、F18-1 個股頁

### 2-1 子圖切換

- K 線下方原本的 MACD 子圖標題列改成：`[MACD｜KD｜RSI]` 切換鈕＋圖例。
  - MACD：「MACD (12, 26, 9)」＋DIF、DEA 圖例（和現在相同）。
  - KD：「KD (9, 3, 3)」＋K（藍）、D（橘）；虛線 20、80，值標在右側刻度。
  - RSI：「RSI (14)」＋RSI（紫）；虛線 30、70。
- 預設 MACD；選擇存在 `localStore('osc')`，重新整理後保留。
- 切換時呼叫既有的 `draw()`：整組圖重建，十字線與拖曳同步沿用現有機制；`anchors` 的最後一項改成「目前子圖的主線」（原本固定是 DIF）。
- 日／週／月、還原／原始切換時子圖跟著重算（子圖跟 K 線用同一份資料，所以「原始」時 KD、RSI 也是原始價；技術面卡一律還原，和均線訊號相同）。
- **ETF 頁**：不顯示切換鈕，固定 MACD，標題仍是「MACD (12, 26, 9)，原始價」。
- 子圖高度不變（120 px）。

### 2-2 技術面卡

- 原本 6 項標籤、「偏多／偏空：N 多 M 空」、`SIG_MIN`、`MACD_MIN` **完全不變**。
- 標籤下方加一行（`.osc-line`）：
  - 「**動能（不計入多空）**　K 16.7／D 16.1（K 低於 20），今日黃金交叉；RSI 19.6（低於 30）」（2330，11/06）。
  - K < 20 標「（K 低於 20）」、K > 80 標「（K 高於 80）」；RSI < 30 標「（低於 30）」、> 70 標「（高於 70）」。
  - 不足 9 根：「KD 資料不足（需 9 根）」；不足 15 根：「RSI 資料不足（需 15 根）」。
- 說明句加：「KD、RSI 在急漲急跌時會長時間停在高檔或低檔，交叉也會反覆出現，不計入多空。」
- 「資料不足，無法判讀」的情況（新股）也顯示動能一行。
- **文字規則**：只寫數值、區間與交叉；**連「超賣」「超買」都不用**（比 PM 的規則更嚴，見第十四節第 3 點），測試會檢查。

### 2-3 量測（SA 原型）

| 項目 | 結果 |
|---|---|
| 2330（11/06，日線） | K 16.7、D 16.1、黃金交叉、RSI 19.6；原本 6 項 0 多 6 空不變 |
| 2330（週線） | K 30.3／D 47.8；RSI 39.7 |
| 375 寬：子圖標題列 | MACD 62 px（切換鈕＋圖例換兩行）、KD／RSI 32 px；原本只有一行文字約 18 px，**MACD 時約 +44 px** |
| 375 寬：技術面卡 | 多一行文字（約 +20 px） |
| 水平捲動 | 375、1024 都沒有 |
| 重新整理 | 保留上次選的子圖 |
| ETF（0056） | 沒有切換鈕、沒有技術面卡；標題「MACD (12, 26, 9)，原始價」 |
| 主控台錯誤 | 0 |

---

## 三、F18-2 選股

### 3-1 匯出：`screen.json` 新欄

| 鍵 | 內容 | 11/06 |
|---|---|---|
| `k` | K 值（小數 1 位） | 1,962 檔有值、21 檔 `null` |
| `kx` | 今日 KD 黃金交叉 1／否 0（`null` = 根數不足或今天無成交） | 437 檔為 1 |
| `rsi` | RSI(14)（小數 1 位） | — |

- `screen.json` 396,944 → 420,622 B（**+23.7 KB**，上限 50 KB）。
- 匯出時間 24.5 → 24.9 秒（+0.4 秒，上限 2 秒）。

### 3-2 條件（新「技術」組，放在「價量」之後）

| id | 條件 | 選項（預設） | 判斷 | 11/06 單獨符合 |
|---|---|---|---|---|
| `kx` | KD 黃金交叉（K < {v}） | 20、30、50（20） | `kx === 1 && k < v` | 220 檔 |
| `rl` | RSI(14) ≤ {v} | 20、30（30） | `rsi ≤ v` | 1,017 檔 |
| `ru` | RSI(14) ≥ {v} | 70、80（70） | `rsi ≥ v` | 8 檔 |

- id 用 `ru` 而不是 `rh`：`rh` 已是「營收創新高」。
- 新組名「技術」：條件放「價量」會讓那組太長（已有 12 條），而且 KD、RSI 和報酬、新高屬性不同。
- 結果欄：`k`（「K值」）、`rsi`（「RSI」），可點欄名排序。
- 網址分享沿用 `scrQuery`（例：`#/rank/screen?kx=20&rl=30`），已驗證重新整理後條件保留。
- **不加預設組合**（`SCREEN_PRESETS` 不變，測試檢查）。

### 3-3 全市場比例 `oscShare()`

- 選了任一技術條件時，「符合 N 檔」上方一行（沿用 `.flow-note` 樣式）：
  > 今日全市場：KD 黃金交叉（K < 20） 220 檔（11.2%）、RSI(14) ≤ 30 1,017 檔（51.8%）。KD、RSI 在急漲急跌時會大量同時出現；比例比平常高很多時，多半是整體市場的波動，不是個股訊號
- 檔數 = 各條件的「單獨」檔數（`renderScreen` 既有的 `cnt`）；分母 = `screen.json` 中 `k` 或 `rsi` 有值的股票（11/06 為 1,964）。
- 沒選技術條件時不顯示。
- 「平常的比例」沒有放進畫面：要匯出歷史統計，超出本輪範圍；分析師的參考值（近 120 日中位數：低檔黃金交叉 0.9%、RSI < 30 為 2.8%）留在 `01-analyst.md`；README 只寫 11/06 的例子。

---

## 四、匯出 JSON 欄位變更

| 檔案 | 鍵 | 變更 |
|---|---|---|
| `screen.json` | `k`、`kx`、`rsi` | **新增**（第三節） |
| 其他 | — | 不變 |

- SA 原型比對：`screen.json` 只多 3 個鍵，其他鍵逐值相同；`latest.json` 除 `updated_at`、`status` 外相同；`stocks/*.json` 0 檔不同。

---

## 五、隔離比對 `logs/iter18_compare.py`

- 由 `logs/iter17_compare.py` 改，比較 `logs/iter18_base/`（本輪前程式）與新程式匯出。
- 只允許：`screen.json` 多 `k`、`kx`、`rsi`。其他所有檔、所有鍵逐值相同（時間欄位除外）。
- `--keep-new` 反證：不剔除新鍵，應判定不同。
- 兩次匯出前後都記 `collect_runs` 最大 `run_id` 與資料日。

---

## 六、重算 `logs/iter18_recalc.py`

**不 import `export` 的計算函式**，自己寫 KD、RSI 與還原：

1. 用唯讀 SQL 讀日線與 `stocks/*.json` 的 `ev`（還原事件），獨立計算每檔 11/06 的 K、交叉、RSI，和 `screen.json` 逐檔比對（小數 1 位）。
2. 三個條件的檔數：`kx` 且 K < 20、RSI ≤ 30、RSI ≥ 70。
3. 2330：K、D、RSI 與第二節的值。
4. 今天無成交的股票：三個鍵都是 `null`。
- 另外 PG 執行 `q3_js_vs_py.js` 的同一套 node 比對（放到 `logs/iter18_js_vs_py.js`），確認個股頁與 `screen.json` 一致。

---

## 七、邊界情況

| 情況 | 行為 |
|---|---|
| 最高 = 最低（9 根都一樣的價格） | RSV = 50 |
| 不到 9 根 | K、D 空；個股頁「KD 資料不足（需 9 根）」；選股 `null` |
| 不到 15 根 | RSI 空；「RSI 資料不足（需 15 根）」；選股 `null` |
| 只漲沒跌 | RSI = 100 |
| 不漲不跌 | RSI = 50 |
| 中間無成交日 | 以前一個收盤畫一字線一起算（同 K 線） |
| 今天無成交 | 選股 `null`；個股頁沿用 P6，以最後有成交的那根判讀 |
| 除權息 | 還原價，除息日不會有假的跳動（2330 9/16 除息） |
| 個股頁切到「原始」 | 子圖用原始價（跟 K 線一致）；技術面卡仍用還原價 |
| ETF | 沒有 KD、RSI |
| 舊 `screen.json` 沒有新欄 | 條件全部不符合（`undefined` 不是數字），不報錯；「今日全市場」分母 0 時顯示「--%」 |
| `localStore` 不能用（私密視窗） | 每次都是 MACD |

---

## 八、QA 清單

1. `git diff --stat`：只有 `twstock/export.py`、`site/stock.js`、`site/app.js`、`site/app.css`、`README.md`；`twstock/collectors/` 沒動。
2. 測試：`test_iter01`～`18` 全部通過，舊測試沒改；本輪前的程式跑 `test_iter18` 應失敗。
3. 比對（第五節）只多 3 個鍵；重算（第六節）全部符合；node 比對 0 檔不同。
4. 個股頁（8001，375 與 1024，深淺色）：
   - 2330：技術面卡的動能一行與值；原本 6 項不變（抽 3 檔和改版前比對）。
   - 子圖 MACD／KD／RSI 切換、重新整理保留、日週月與還原原始切換後重算、十字線同步。
   - 至少 1 檔新上市（不足 15 根）顯示「資料不足」。
   - ETF 頁沒有切換鈕。
5. 選股：三個條件的單獨檔數；「今日全市場」一行的數字；網址分享；沒選技術條件時不顯示那一行；排序欄 K 值、RSI。
6. 文字：個股頁、選股的新文字沒有「買進」「賣出」「反彈」「見底」「買點」「超賣」「超買」。
7. `screen.json` 增加 ≤ 50 KB；匯出時間增加 ≤ 2 秒。

---

## 九、測試 `tests/test_iter18.py`（新檔，全文見附錄 A）

| 測試 | 驗什麼 | 對應 PM 驗收 |
|---|---|---|
| `test_kd_formula` | 最高 = 最低、收在最高、收在最低（手算值） | F18-1 #7 |
| `test_rsi_formula` | 只漲、只跌、不漲不跌、根數不足、一漲一跌的 Wilder 平滑 | F18-1 #7 |
| `test_osc_stats` | 今天無成交 `null`、還原係數、中間無成交一字線、上市前空值、根數不足 | F18-2 #6 |
| `test_js_matches_python` | node 執行 `stock.js` 的 `calcKD`、`calcRSI`，和 Python 逐根相同（沒有 node 時略過） | F18-2 #6 |
| `test_screen_keys` | `SCREEN_KEYS` 有新鍵；匯出有呼叫 `osc_stats` | F18-2 #5 |
| `test_stock_page_source` | 切換鈕、預設 MACD、ETF 只有 MACD、十字線同步、參考線、原 6 項不變、動能一行、資料不足 | F18-1 #3～#5 |
| `test_no_advice_words` | 新文字沒有建議性字眼 | 共通規則 6 |
| `test_screen_source` | 技術組、3 個條件與選項、全市場比例與分母、結果欄、不加預設組合 | F18-2 #3、#4 |

---

## 十、延後順序（沿用 PM）

PM 的延後順序是「RSI ≥ 條件 → RSI 子圖」。原型都已完成，建議不延後。

---

## 十一、README 修改清單（全文見附錄 A）

- 個股價格段：子圖切換、KD／RSI 公式、無成交日、參考線、動能一行不計入多空、資料不足、前後端同一套公式的提醒。
- 選股段：七組、技術條件 3 個、`screen.json` 新欄、全市場比例與 11/06 的例子、不提供預設組合。
- `__main__.py` 不改（`export` 說明已寫「含選股用的 screen.json」）。

---

## 十二、PG 實作步驟

1. 記錄資料日、`collect_runs` 最大 `run_id`，確認沒有進行中的收集。把 `export.py`、`stock.js`、`app.js`、`app.css` 複製到 `logs/iter18_before/`。
2. 基線 `export`，把 `site/data` 複製到 `logs/iter18_base/`。
3. 套用附錄 A（`patch -p1 --dry-run` 後正式套用）；`node --check`；`test_iter01`～`18`。
4. 新程式 `export`。
5. 比對（第五節）、重算（第六節）、node 比對。
6. 8001 預覽：375 px 與 1024 px，深淺色。結束後關閉 8001，恢復視窗大小。
- **允許的寫入**：只有 `export` 兩次（基線、新程式）。不執行 `collect`、`history`、`setup-db`、`backup`、還原。
- **請求：0 次**。

---

## 十三、測量摘要（SA 原型）

| 項目 | 結果 |
|---|---|
| 外部請求、資料庫寫入 | 0、0 |
| 程式＋README | ＋140／−18（PM 估 115、上限約 135） |
| `screen.json` | +23.7 KB |
| 匯出耗時 | 24.5 → 24.9 秒 |
| 前後端一致 | 1,964 檔相同、0 檔不同 |
| 11/06 條件檔數 | KD 黃金交叉（K < 20）220、RSI ≤ 30 1,017、RSI ≥ 70 8 |
| 測試 | `proj` 的 `test_iter01`～`18` 全過；`orig` 跑 `test_iter18` 失敗 |

- 和分析師的差異：分析師用原始價、排除近 30 根有事件的 70 檔，得到低檔黃金交叉 206、RSI < 30 972；本設計用還原價、納入全部，所以是 220、1,017（RSI 用 ≤）。

---

## 十四、對 PM 範圍的調整建議（不改 `02-pm.md`）

1. **行數超過上限 5 行**（＋140，上限約 135）：
   - 多出來的是註解與 docstring（公式說明、「改一邊要改另一邊」），對之後維護兩套公式有用。
   - 功能沒有超出範圍，建議接受。
2. **選股條件放新的「技術」組**（PM 交給 SA）：理由見 3-2。
3. **文字規則更嚴**：PM 允許「超賣」「超買」和數值一起出現；SA 建議完全不用，只寫「低於 30」「高於 70」。理由：這兩個詞本身就帶有「該反轉」的暗示，在 11/06 這種一半股票 RSI < 30 的日子會誤導。
4. **子圖圖例不寫「虛線 20、80」**：375 寬時會讓標題列多換一行；參考線的值已標在右側刻度。
5. **「平常的比例」不放畫面**：需要匯出歷史統計（第 3-3 節），列入待辦 B12-延伸。
6. **id `ru`**：避免和既有 `rh`（營收創新高）衝突。

---

## 十五、給 PG、QA 的提醒

- 使用者每晚收集後會自動 `export`。新程式一旦套用，下一次匯出的 `screen.json` 就有新欄；網站先更新、資料後更新時，技術條件全部不符合，不報錯。
- 比對前後都要記 `collect_runs`，避免混入使用者的新資料日（11/09 收集後資料日會變成 11/09，檔數以當時重算為準）。
- 本機 node 是 v14，沒有 `Array.prototype.at`。網站在瀏覽器正常；node 比對腳本裡已補一行 polyfill，**不要**改網站程式。
- 本輪尚未 commit；是否 commit 由使用者決定。

---

## 附錄 A：完整 diff（`orig` → `proj`，含新測試檔）

```diff
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -49,7 +49,7 @@
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
-               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp", "mc", "to", "rb", "eb")
+               "eq", "ey", "e4", "gm", "gmy", "fq", "eh", "lb", "l1", "l5", "lp", "mc", "to", "rb", "eb", "k", "kx", "rsi")
 VAL_DAYS = 242                  # F9-4：估值一年位置的窗口 = 最近 242 個有官方本益比資料的交易日
 VAL_MIN = 120                   # 個股窗口內有效天數少於此值不算位置（新上市）
 VAL_SPARK = 60                  # 今日頁本益比中位數迷你圖天數
@@ -967,7 +967,60 @@
         out[f"b{n}"] = _f((lc / (sum(px[-n:]) / n) - 1) * 100) if len(px) >= n else None
     out["nh"] = next((n for n in NH_DAYS if traded and len(px) > n and px[-1] > max(px[-n - 1:-1])), 0)
     out["nl"] = next((n for n in NH_DAYS if traded and len(px) > n and px[-1] < min(px[-n - 1:-1])), 0)
+    return out
+
+
+# 第 18 輪 F18-2：KD(9,3,3)、RSI(14)。和 site/stock.js 的 calcKD、calcRSI 同一套公式（改一邊要改另一邊）
+KD_N, RSI_N = 9, 14
+
+
+def calc_kd(h, l, c, n=KD_N):
+    """K、D 序列：RSV = (收 − n 日最低) ÷ (n 日最高 − n 日最低) × 100（最高 = 最低時 50）；K = 2/3 前 K + 1/3 RSV、D 同理，起始 50。前 n − 1 根為 None。"""
+    K, D, ks, ds = 50.0, 50.0, [], []
+    for i in range(len(c)):
+        if i < n - 1:
+            ks.append(None); ds.append(None); continue
+        hh, ll = max(h[i - n + 1:i + 1]), min(l[i - n + 1:i + 1])
+        rsv = 50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100
+        K = K * 2 / 3 + rsv / 3
+        D = D * 2 / 3 + K / 3
+        ks.append(K); ds.append(D)
+    return ks, ds
+
+
+def calc_rsi(c, n=RSI_N):
+    """RSI（Wilder）：第 n 根（索引 n）起，先用前 n 個漲跌的平均，之後 (前值 × (n − 1) + 本次) ÷ n；沒有跌時 100、沒有漲跌時 50。"""
+    out = [None] * len(c)
+    if len(c) <= n:
+        return out
+    up = dn = 0.0
+    for i in range(1, len(c)):
+        u, d = max(c[i] - c[i - 1], 0.0), max(c[i - 1] - c[i], 0.0)
+        if i <= n:
+            up += u / n; dn += d / n
+        else:
+            up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n
+        if i >= n:
+            out[i] = 50.0 if up == dn == 0 else 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
     return out
+
+
+def osc_stats(o, h, l, c, af):
+    """screen.json 的 k（K 值）、kx（今日 KD 黃金交叉 1／否 0）、rsi；還原價，同個股頁 K 線：
+    開、收都有值才算成交；上市後的無成交日以前一個還原收盤畫一字線（高 = 低 = 收）；今天無成交 → 全部 None。"""
+    H, L, C, prev = [], [], [], None
+    for i in range(len(c)):
+        if c[i] is not None and o[i] is not None:
+            k = af[i]
+            H.append(float(h[i]) * k); L.append(float(l[i]) * k); C.append(float(c[i]) * k); prev = C[-1]
+        elif prev is not None:
+            H.append(prev); L.append(prev); C.append(prev)
+    if c[-1] is None or o[-1] is None or not C:
+        return {"k": None, "kx": None, "rsi": None}
+    ks, ds = calc_kd(H, L, C)
+    r = calc_rsi(C)
+    k1 = ks[-1] is not None and ks[-2] is not None if len(ks) > 1 else False
+    return {"k": _f(ks[-1], 1), "kx": int(ks[-2] <= ds[-2] and ks[-1] > ds[-1]) if k1 else None, "rsi": _f(r[-1], 1)}
 
 
 def revenue_stats(rows):
@@ -1485,7 +1538,8 @@
                         **fin_screen(fin.get(code)),                                  # 第 10 輪 B5
                         **{k: (sbl or {}).get(k) for k in ("lb", "l1", "l5", "lp")},   # 第 11 輪 B14
                         "mc": mc, "to": to,                                               # 第 12 輪 B11
-                        "rb": rev_base(rev_rows), "eb": fin_base(fin.get(code))}          # 第 14 輪 F14-1、F14-2：基期
+                        "rb": rev_base(rev_rows), "eb": fin_base(fin.get(code)),         # 第 14 輪 F14-1、F14-2：基期
+                        **osc_stats(o, h, l, c, af)}                                      # 第 18 輪 F18-2：KD、RSI
 
     industries = defaultdict(list)
     for code in snapshot:
--- a/site/stock.js
+++ b/site/stock.js
@@ -159,8 +159,7 @@
       <div id="iC" class="chart-box" style="height:90px"></div>`}
       ${data.mg ? `<div class="ch-label">融資／融券${data.mg.lb ? '／借券賣出' : ''}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
       <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
-      <div class="ch-label">MACD (12, 26, 9)${E ? '，原始價' : ''}
-        <span class="lg"><i style="background:#378ADD"></i>DIF</span><span class="lg"><i style="background:#EF9F27"></i>DEA</span></div>
+      <div class="ch-label">${E ? '' : segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))}<span id="oscLeg" style="display:contents"></span></div>
       <div id="mC" class="chart-box" style="height:120px"></div>
     </section>
 
@@ -180,10 +179,11 @@
   // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
   const draw = () => {
     const m = localStore('kmode', '日'), adj = !E && localStore('kadj', '還原') === '還原';   // ETF 一律原始價、沒有技術面訊號
-    buildCharts(aggregate(data, m, adj), m, data.mg, adj);
+    buildCharts(aggregate(data, m, adj), m, data.mg, adj, E ? 'MACD' : localStore('osc', 'MACD'), E);   // 第 18 輪 F18-1：子圖 MACD／KD／RSI
     if (!E) renderSignals(aggregate(data, m, true), m);
   };
   onSeg('kSeg', m => { localStore('kmode', null, m); document.querySelectorAll('#kSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === m)); draw(); });
+  if (!E) onSeg('oscSeg', v => { localStore('osc', null, v); document.querySelectorAll('#oscSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
   if (!E) onSeg('adjSeg', v => { localStore('kadj', null, v); document.querySelectorAll('#adjSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); draw(); });
   $('#latestBtn').addEventListener('click', () => { syncLeader = charts[0]; charts[0]?.timeScale().scrollToRealTime(); });
   CHART_IDS.filter(id => $('#' + id)).forEach((id, idx) => ['mouseenter', 'pointerdown', 'touchstart', 'wheel'].forEach(t =>
@@ -267,7 +267,32 @@
   return { dif, dea, hist: dif.map((v, i) => v - dea[i]) };
 }
 
-function buildCharts(raw, mode, G, adj) {
+// 第 18 輪 F18-1：KD(9,3,3)、RSI(14)。和 twstock/export.py 的 calc_kd、calc_rsi 同一套公式（改一邊要改另一邊）
+const OSC_OPTS = [['MACD', 'MACD'], ['KD', 'KD'], ['RSI', 'RSI']];
+function calcKD(H, L, C, n = 9) {
+  let K = 50, D = 50;
+  const k = [], d = [];
+  C.forEach((c, i) => {
+    if (i < n - 1) { k.push(null); d.push(null); return; }
+    const hh = Math.max(...H.slice(i - n + 1, i + 1)), ll = Math.min(...L.slice(i - n + 1, i + 1));
+    const rsv = hh === ll ? 50 : (c - ll) / (hh - ll) * 100;
+    K = K * 2 / 3 + rsv / 3; D = D * 2 / 3 + K / 3;
+    k.push(K); d.push(D);
+  });
+  return { k, d };
+}
+function calcRSI(C, n = 14) {
+  const out = C.map(() => null);
+  let up = 0, dn = 0;
+  for (let i = 1; i < C.length; i++) {
+    const u = Math.max(C[i] - C[i - 1], 0), d = Math.max(C[i - 1] - C[i], 0);
+    if (i <= n) { up += u / n; dn += d / n; } else { up = (up * (n - 1) + u) / n; dn = (dn * (n - 1) + d) / n; }
+    if (i >= n) out[i] = up === 0 && dn === 0 ? 50 : dn === 0 ? 100 : 100 - 100 / (1 + up / dn);
+  }
+  return out;
+}
+
+function buildCharts(raw, mode, G, adj, osc = 'MACD', E = null) {
   disposeKCharts();
   if (!raw.length || !window.LightweightCharts) return;
   const LC = window.LightweightCharts;
@@ -356,11 +381,27 @@
   }
 
   const mc = mk('mC', true);
-  const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
-  const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
-  hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: v >= 0 ? 'rgba(55,138,221,.65)' : 'rgba(213,90,48,.65)' })));
-  const difSer = line(mc, dif, '#378ADD', macdFmt);
-  line(mc, dea, '#EF9F27', macdFmt);
+  const lg = (c, t) => `<span class="lg"><i style="background:${c}"></i>${t}</span>`;
+  let oSer, oVal;
+  if (osc === 'KD' || osc === 'RSI') {   // 第 18 輪 F18-1：KD 20／80、RSI 30／70 參考線
+    const f1 = { type: 'price', precision: 1, minMove: 0.1 };
+    const { k, d } = calcKD(H, L, C), rsi = calcRSI(C);
+    const [vals, refs] = osc === 'KD' ? [k, [20, 80]] : [rsi, [30, 70]];
+    oSer = line(mc, vals, osc === 'KD' ? '#378ADD' : '#7F77DD', f1);
+    if (osc === 'KD') line(mc, d, '#EF9F27', f1);
+    refs.forEach(p => oSer.createPriceLine({ price: p, color: text2, lineWidth: 1, lineStyle: 2, axisLabelVisible: true }));
+    oVal = i => vals[i];
+    $('#oscLeg').innerHTML = osc === 'KD' ? `KD (9, 3, 3)${lg('#378ADD', 'K')}${lg('#EF9F27', 'D')}`
+      : `RSI (14)${lg('#7F77DD', 'RSI')}`;   // 參考線的值標在右側刻度
+  } else {
+    const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
+    const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
+    hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: v >= 0 ? 'rgba(55,138,221,.65)' : 'rgba(213,90,48,.65)' })));
+    oSer = line(mc, dif, '#378ADD', macdFmt);
+    line(mc, dea, '#EF9F27', macdFmt);
+    oVal = i => dif[i];
+    $('#oscLeg').innerHTML = `MACD (12, 26, 9)${E ? '，原始價' : ''}${lg('#378ADD', 'DIF')}${lg('#EF9F27', 'DEA')}`;
+  }
 
   charts = [kc, vc, ...(ic ? [ic] : []), ...(gc ? [gc] : []), mc];   // 順序與 CHART_IDS 中存在的圖一致
 
@@ -372,7 +413,7 @@
   }));
 
   // 十字線同步 + 上方資訊列
-  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], ...(ic ? [[ic, iSer, i => N[i]]] : []), ...(gc ? [[gc, mbSer, i => MB[i]]] : []), [mc, difSer, i => dif[i]]];
+  const anchors = [[kc, kSer, i => C[i]], [vc, vSer, i => V[i]], ...(ic ? [[ic, iSer, i => N[i]]] : []), ...(gc ? [[gc, mbSer, i => MB[i]]] : []), [mc, oSer, oVal]];
   const legend = $('#kLegend');
   const showLegend = i => {
     // 日線用匯出的漲跌（事件日相對參考價、前一日無成交相對最後成交）；找不到事件的不比價日為 null。週／月線用前一根收盤
@@ -441,6 +482,7 @@
   let n = rows.length;
   while (n > 0 && rows[n - 1].nt) n--;          // 最後一根無成交的一字線不納入判讀
   const C = rows.slice(0, n).map(r => r.c), i = n - 1, c = C[i];
+  const { k, d } = calcKD(rows.slice(0, n).map(r => r.h), rows.slice(0, n).map(r => r.l), C), rsi = calcRSI(C);   // 第 18 輪 F18-1
   const ma5 = calcMA(C, 5), ma20 = calcMA(C, 20), ma60 = calcMA(C, 60);
   const bull = [], bear = [];
   const chk = (ok, yes, no) => (ok ? bull : bear).push(ok ? yes : no);
@@ -454,9 +496,9 @@
     chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
   }
   const total = bull.length + bear.length, lean = bull.length > bear.length ? 'bull' : bull.length < bear.length ? 'bear' : '';
-  const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>`;
+  const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>` + oscLine(k, d, rsi, i);
   const note = (n < rows.length && n ? `最後一根（${md(rows.at(-1).d)}）無成交，以 ${md(rows[i].d)} 判讀。` : '') +
-    '依均線與 MACD 機械判讀（還原價格），僅供參考。';
+    '依均線與 MACD 機械判讀（還原價格），僅供參考。KD、RSI 在急漲急跌時會長時間停在高檔或低檔，交叉也會反覆出現，不計入多空。';
   $('#sigBox').innerHTML = total < SIG_MIN
     ? `<div class="signal"><div style="font-weight:600;margin-bottom:6px">資料不足，無法判讀</div>${tags}
         <div class="muted small" style="margin-top:8px">${period}只有 ${n} 根 K 棒，有效訊號 ${total} 項（至少需 ${SIG_MIN} 項；MACD 需 ${MACD_MIN} 根以上）。${note}</div></div>`
@@ -465,6 +507,15 @@
         ${tags}<div class="muted small" style="margin-top:8px">${note}</div></div>`;
 }
 
+// 第 18 輪 F18-1：技術面卡「動能（不計入多空）」一行；只寫數值、區間與交叉
+function oscLine(k, d, rsi, i) {
+  const kd = k[i] == null ? 'KD 資料不足（需 9 根）'
+    : `K ${fmt(k[i], 1)}／D ${fmt(d[i], 1)}${k[i] < 20 ? '（K 低於 20）' : k[i] > 80 ? '（K 高於 80）' : ''}` +
+      (k[i - 1] == null ? '' : k[i - 1] <= d[i - 1] && k[i] > d[i] ? '，今日黃金交叉' : k[i - 1] >= d[i - 1] && k[i] < d[i] ? '，今日死亡交叉' : '');
+  const r = rsi[i] == null ? 'RSI 資料不足（需 15 根）' : `RSI ${fmt(rsi[i], 1)}${rsi[i] < 30 ? '（低於 30）' : rsi[i] > 70 ? '（高於 70）' : ''}`;
+  return `<div class="small osc-line"><b>動能（不計入多空）</b>　${kd}；${r}</div>`;
+}
+
 // ─── 第 10 輪 B5：季報卡（匯出端已把累計相減成單季；q = [季別, 單季 EPS, EPS 年增 %, 毛利率 %, 營益率 %, 單季營收（千元）]）───
 const FIN_TBL = { ci: '一般業', fh: '金控', basi: '銀行', bd: '證券', ins: '保險', mim: '其他' };
 const qName = k => `${Math.floor(k / 100)} Q${k % 100}`;                 // 202603 → 2026 Q3
--- a/site/app.js
+++ b/site/app.js
@@ -965,6 +965,7 @@
   nh: ['新高(日)', x => x.nh, int0], nl: ['新低(日)', x => x.nl, int0],
   hd: ['距52週高', x => isNum(x.h52) && x.h52 > 0 && isNum(x.c) ? (x.h52 - x.c) / x.h52 * 100 : null, v => v == null ? '--' : fmt(v, 2) + '%', 1],
   vr: ['量比', x => x.vr, v => fmt(v, 2)],
+  k: ['K值', x => x.k, v => fmt(v, 1)], rsi: ['RSI', x => x.rsi, v => fmt(v, 1)],   // 第 18 輪 F18-2
   rs20: ['20日相對', x => x.rs20, v => sgn(v)], rs60: ['60日相對', x => x.rs60, v => sgn(v)],
   s: ['法人連', x => x.s, streakTxt], fs: ['外資連', x => x.fs, streakTxt], ts: ['投信連', x => x.ts, streakTxt],
   f5: ['外資5日', x => x.f5, yi], t5: ['投信5日', x => x.t5, yi], n5: ['法人5日', x => x.n5, yi], n20: ['法人20日', x => x.n20, yi],
@@ -1032,6 +1033,11 @@
   { id: 'vr', g: '價量', label: '量比 ≥ {v} 倍', opts: [1.5, 2, 3], def: 1.5, f: scrGe('vr'), cols: ['vr'] },
   { id: 'rs20', g: '價量', label: '20 日相對大盤 > {v} 百分點', opts: 'num', def: 0, f: (x, v) => isNum(x.rs20) && x.rs20 > v, cols: ['rs20'] },
   { id: 'rs60', g: '價量', label: '60 日相對大盤 > {v} 百分點', opts: 'num', def: 0, f: (x, v) => isNum(x.rs60) && x.rs60 > v, cols: ['rs60'] },
+  // 第 18 輪 F18-2：KD(9,3,3)、RSI(14)（還原價）；急漲急跌時會大量出現，結果上方列全市場比例
+  { id: 'kx', g: '技術', label: 'KD 黃金交叉（K < {v}）', opts: [20, 30, 50], def: 20, f: (x, v) => x.kx === 1 && isNum(x.k) && x.k < v, cols: ['k'], osc: 1,
+    title: '今日 K 由下往上穿過 D，且 K 低於門檻；急跌期常一次出現上百檔' },
+  { id: 'rl', g: '技術', label: 'RSI(14) ≤ {v}', opts: [20, 30], def: 30, f: (x, v) => isNum(x.rsi) && x.rsi <= v, cols: ['rsi'], osc: 1 },
+  { id: 'ru', g: '技術', label: 'RSI(14) ≥ {v}', opts: [70, 80], def: 70, f: (x, v) => isNum(x.rsi) && x.rsi >= v, cols: ['rsi'], osc: 1 },
   { id: 's', g: '法人', label: '法人連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('s'), cols: ['s'] },
   { id: 'fs', g: '法人', label: '外資連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('fs'), cols: ['fs'] },
   { id: 'ts', g: '法人', label: '投信連買 ≥ {v} 日', opts: [3, 5, 10], def: 3, f: scrGe('ts'), cols: ['ts'] },
@@ -1073,7 +1079,7 @@
   { id: 'xc', g: '排除', label: '估值條件排除 90 天內股本變動', sw: true, f: null, n: x => x.cap === 1 },   // 不單獨篩選
   { id: 'xm', g: '排除', label: '排除停資停券（上市註記 O、X）', sw: true, f: x => !(x.mnt && /[OX]/.test(x.mnt)) },
 ];
-const SCREEN_GROUPS = ['流動性', '價量', '法人', '信用', '基本面', '排除'];
+const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];
 // [id, 按鈕, 條件]；套用時取代全部條件並加上 xd、xn、xc；r1、r2 為參考組（風險檢查）
 const SCREEN_PRESETS = [
   ['1', '法人連買＋營收創新高', 's=3&rh=1&tv=0.5'], ['2', '投信認養', 'ts=3&t5=1&t5r=5&tv=0.5'], ['3', '帶量突破', 'nh=60&vr=1.5&tv=1'],
@@ -1083,6 +1089,15 @@
 ];
 const SCREEN_DEFAULT = { xd: 1, xn: 1, xc: 1, o: 'tv' };
 // 條件狀態 = {條件 id: 門檻, o: 排序欄, od: 'a' 遞增／'d' 遞減（省略 = 預設方向）, ps: 套用中的預設}
+// 第 18 輪 F18-2：選了 KD、RSI 條件時，列今日全市場符合的檔數與比例（分母 = 有 K 或 RSI 值的股票），看得出是不是急漲急跌期
+function oscShare(conds, X, cnt, st) {
+  const cs = conds.filter(c => c.osc);
+  if (!cs.length) return '';
+  const base = X.filter(x => isNum(x.k) || isNum(x.rsi)).length;
+  return `<div class="flow-note">今日全市場：${cs.map(c => { const n = cnt(c);
+    return `${c.label.replace('{v}', fmt(st[c.id]))} ${fmt(n)} 檔（${base ? fmt(n / base * 100, 1) : '--'}%）`; }).join('、')}。` +
+    'KD、RSI 在急漲急跌時會大量同時出現；比例比平常高很多時，多半是整體市場的波動，不是個股訊號</div>';
+}
 function scrParse(q) {
   const st = {};
   for (const [k, v] of new URLSearchParams(q)) {
@@ -1154,10 +1169,11 @@
         <button class="chip" id="scrClear">重設</button> <button class="chip" id="scrCopy">複製條件連結</button></summary>
         ${SCREEN_GROUPS.map(g => `<div class="scr-grp"><b>${g}</b><div>${SCREEN_CONDS.filter(c => c.g === g).map(condHTML).join('')}</div></div>`).join('')}
       </details>
+      ${oscShare(conds, X, cnt, st)}
       <div class="sec-h" style="margin:8px 0"><h2>符合 ${fmt(hits.length)} 檔</h2>${hits.length > 100 ? `<span class="muted small">依「${oName}」排序顯示前 100 檔</span>` : ''}</div>
       <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
         : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
-      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
+      <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低、KD、RSI 都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
     keyCol($(`#view th.sort[data-k="${o}"]`)?.cellIndex);
     const changed = () => { delete st.ps; save(); draw(); };
     onModeSeg();
--- a/site/app.css
+++ b/site/app.css
@@ -214,6 +214,7 @@
 .pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
 .al-grp{margin-top:8px}.al-grp h3{font-size:13px;margin:0 0 4px}                 /* 第 16 輪 F16-3 */
 .al-row{display:block;padding:5px 0;border-top:1px solid var(--border);color:inherit;text-decoration:none}
+.osc-line{margin-top:8px}
 .al-near{padding:5px 0;border-top:1px solid var(--border);line-height:1.7}.al-near a{color:inherit}       /* 第 17 輪 F17-2 */
 .al-l{display:flex;align-items:baseline;gap:6px}.al-l .sp{flex:1}.al-why{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .al-new{background:var(--blue)}                                  /* E2-4：新建倉 */
--- a/README.md
+++ b/README.md
@@ -128,7 +128,7 @@
 - 期貨三大法人未平倉來自期交所「三大法人－區分各期貨契約」，抓大台（TXF）、小台（MXF）、微台（TMF），換算成約當大台 = 大台 + 小台/4 + 微台/20。
 - 籌碼因子觀察（大盤漲跌預測）：以外資淨未平倉水位、外資 1 日／5 日增減、投信與自營商 1 日增減（相對近 60 日標準化）做羅吉斯迴歸，預測下一交易日台指期近月日盤漲跌。網站同時顯示 walk-forward 回測命中率與「永遠猜多數方向」的基準；模型沒有勝過基準時，首頁只顯示因子方向，機率與回測收在摺疊區；僅供籌碼面參考，非投資建議。
 - 個股法人：排行可切換 1 日／5 日，提供外資、投信、自營、法人合計的買超／賣超與連買排行；金額 = 張數 × 當日收盤（估算值，與官方公布的買賣金額可能不同）。
-- 條件選股（排行頁「選股」，`#/rank/screen`）：資料來自 `site/data/screen.json`（匯出時計算，0 個外部請求），在瀏覽器合併 `latest.json` 篩選，只做 AND。條件分流動性、價量、法人、信用、基本面、排除六組，另有 8 組預設（法人連買＋營收創新高、投信認養、帶量突破、多頭排列＋相對強勢、價值高息、營收高成長、籌碼換手、財報優於去年）與 3 組參考（融資追價、軋空觀察、本益比低但 EPS 下滑）。報酬、乖離、均線、新高新低用**還原價格**；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），用成交額所以不受面額變更影響；相對大盤 = 個股報酬 − 指數報酬（上市對加權、上櫃對櫃買）。本益比、殖利率、淨值比條件**預設排除 90 天內股本變動**的股票（官方值可能尚未調整），可關閉，關閉後結果列標示「股本變動」。營收以各股最新公布的月份計算，頁面列出各月份檔數；每月 1～10 日是公布期間，各股月份不同，月份混雜時資料日一行加註說明，營收欄標出和欄名不同的月份。第 9 輪新增「淨值比一年位置 ≤ N%」（`screen.json` 的 `pbp`，見估值位置），和其他估值條件一樣預設排除股本變動。第 10 輪新增季報條件 5 個（基本面組）：單季 EPS 年增 ≥ N%、毛利率年增 ≥ N 百分點、近 4 季 EPS > 0、單季 EPS 創 N 季新高、單季 EPS 比去年同季下滑；預設「財報優於去年」= 單季 EPS 年增 ≥ 20% 且毛利率年增 ≥ 0、成交額 ≥ 0.5 億，參考「本益比低但 EPS 下滑」= 本益比 ≤ 15 且單季 EPS 下滑。`screen.json` 新欄：`eq` 最新一季單季 EPS、`ey` 單季 EPS 年增 %（去年同季 ≤ 0 為 null）、`e4` 近 4 季 EPS、`gm` 單季毛利率 %（金融業 null）、`gmy` 毛利率年增（百分點）、`fq` 最新季別（YYYYQQ）、`eh` 單季 EPS 創幾季新高、`fqd` 各季別檔數；null 一律不符合條件。各股最新一季可能不同（財報公布期間），欄名依檔數最多的季別，季別不同的列加小字季別，資料日一行列出各季別檔數，沒有任何季別 ≥ 98% 時加「財報公布期間，各股季別不同」。第 11 輪新增借券條件 2 個（信用組）：借券占股本 ≥ N%（3／5／8，預設 5）、借券 5 日增加 ≥ N 張（500／1,000／5,000，預設 1,000）；`screen.json` 新欄 `lb` 借券賣出餘額（張）、`l1`／`l5` 1 日／5 日增減（張）、`lp` 占股本 %（沒有股數為 null），`head.sd` 為各市場借券資料日。選股「毛利率」「毛利率年增」欄也和單季 EPS 一樣，季別不同的列加小字季別。「重設」回到預設（保留排除處置股、今日無成交、股本變動與預設排序），不是全部清空。條件存在瀏覽器，網址也會帶條件，可用「複製條件連結」分享。排行另加量比、創新高、20 日相對強勢、營收年增、殖利率、本益比最低（後兩者排除虧損與股本變動）。`screen.json` 不存在時這些功能不出現，既有排行照常。第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億元，收盤 × 目前發行股數）、`to` 週轉率（% = 今日成交股數 ÷ 目前發行股數，今天沒有成交為 0），沒有股數為 null，null 一律不符合。排行「價量」組加「週轉率」（欄位：週轉率、市值；成交額門檻同其他排行）。市值、週轉率都用目前股數，增資、減資前後可能失真。第 14 輪：排行「營收年增」只列營收月份 ≥ 欄名月份（檔數最多的月份）的股票，表下一行寫出未列入的檔數（市場、成交額門檻同排行）；選股的「營收年增 ≥」條件不排除舊月份。`screen.json` 新欄 `rb` 去年同月營收（千元，沒有去年同月為 null）、`eb` 最新一季的去年同季單季 EPS（元，和個股 `fin.q` 第 7 欄同一口徑）。營收年增有值且 `rb` < 10,000 千元（1,000 萬元）時，營收年增欄加「基期低」小標；單季 EPS 年增有值（去年同季 > 0）且 `eb` < 0.1 元時，EPS 年增欄改顯示「基期低」與去年同季 EPS（個股季報卡與柱狀圖提示同規則）。只標示，不排除、不改排序；去年同季 ≤ 0 照舊顯示「轉盈」。
+- 條件選股（排行頁「選股」，`#/rank/screen`）：資料來自 `site/data/screen.json`（匯出時計算，0 個外部請求），在瀏覽器合併 `latest.json` 篩選，只做 AND。條件分流動性、價量、技術、法人、信用、基本面、排除七組（技術組為第 18 輪新增），另有 8 組預設（法人連買＋營收創新高、投信認養、帶量突破、多頭排列＋相對強勢、價值高息、營收高成長、籌碼換手、財報優於去年）與 3 組參考（融資追價、軋空觀察、本益比低但 EPS 下滑）。報酬、乖離、均線、新高新低用**還原價格**；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），用成交額所以不受面額變更影響；相對大盤 = 個股報酬 − 指數報酬（上市對加權、上櫃對櫃買）。本益比、殖利率、淨值比條件**預設排除 90 天內股本變動**的股票（官方值可能尚未調整），可關閉，關閉後結果列標示「股本變動」。營收以各股最新公布的月份計算，頁面列出各月份檔數；每月 1～10 日是公布期間，各股月份不同，月份混雜時資料日一行加註說明，營收欄標出和欄名不同的月份。第 9 輪新增「淨值比一年位置 ≤ N%」（`screen.json` 的 `pbp`，見估值位置），和其他估值條件一樣預設排除股本變動。第 10 輪新增季報條件 5 個（基本面組）：單季 EPS 年增 ≥ N%、毛利率年增 ≥ N 百分點、近 4 季 EPS > 0、單季 EPS 創 N 季新高、單季 EPS 比去年同季下滑；預設「財報優於去年」= 單季 EPS 年增 ≥ 20% 且毛利率年增 ≥ 0、成交額 ≥ 0.5 億，參考「本益比低但 EPS 下滑」= 本益比 ≤ 15 且單季 EPS 下滑。`screen.json` 新欄：`eq` 最新一季單季 EPS、`ey` 單季 EPS 年增 %（去年同季 ≤ 0 為 null）、`e4` 近 4 季 EPS、`gm` 單季毛利率 %（金融業 null）、`gmy` 毛利率年增（百分點）、`fq` 最新季別（YYYYQQ）、`eh` 單季 EPS 創幾季新高、`fqd` 各季別檔數；null 一律不符合條件。各股最新一季可能不同（財報公布期間），欄名依檔數最多的季別，季別不同的列加小字季別，資料日一行列出各季別檔數，沒有任何季別 ≥ 98% 時加「財報公布期間，各股季別不同」。第 11 輪新增借券條件 2 個（信用組）：借券占股本 ≥ N%（3／5／8，預設 5）、借券 5 日增加 ≥ N 張（500／1,000／5,000，預設 1,000）；`screen.json` 新欄 `lb` 借券賣出餘額（張）、`l1`／`l5` 1 日／5 日增減（張）、`lp` 占股本 %（沒有股數為 null），`head.sd` 為各市場借券資料日。選股「毛利率」「毛利率年增」欄也和單季 EPS 一樣，季別不同的列加小字季別。「重設」回到預設（保留排除處置股、今日無成交、股本變動與預設排序），不是全部清空。條件存在瀏覽器，網址也會帶條件，可用「複製條件連結」分享。排行另加量比、創新高、20 日相對強勢、營收年增、殖利率、本益比最低（後兩者排除虧損與股本變動）。`screen.json` 不存在時這些功能不出現，既有排行照常。第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億元，收盤 × 目前發行股數）、`to` 週轉率（% = 今日成交股數 ÷ 目前發行股數，今天沒有成交為 0），沒有股數為 null，null 一律不符合。排行「價量」組加「週轉率」（欄位：週轉率、市值；成交額門檻同其他排行）。市值、週轉率都用目前股數，增資、減資前後可能失真。第 14 輪：排行「營收年增」只列營收月份 ≥ 欄名月份（檔數最多的月份）的股票，表下一行寫出未列入的檔數（市場、成交額門檻同排行）；選股的「營收年增 ≥」條件不排除舊月份。`screen.json` 新欄 `rb` 去年同月營收（千元，沒有去年同月為 null）、`eb` 最新一季的去年同季單季 EPS（元，和個股 `fin.q` 第 7 欄同一口徑）。營收年增有值且 `rb` < 10,000 千元（1,000 萬元）時，營收年增欄加「基期低」小標；單季 EPS 年增有值（去年同季 > 0）且 `eb` < 0.1 元時，EPS 年增欄改顯示「基期低」與去年同季 EPS（個股季報卡與柱狀圖提示同規則）。只標示，不排除、不改排序；去年同季 ≤ 0 照舊顯示「轉盈」。第 18 輪新增技術條件 3 個：KD 黃金交叉（K < 20／30／50，預設 20）、RSI(14) ≤ 20／30（預設 30）、RSI(14) ≥ 70／80（預設 70）；`screen.json` 新欄 `k`（K 值）、`kx`（今日 K 由下往上穿過 D 為 1，否則 0）、`rsi`，公式同個股頁，用還原價；今天無成交或根數不足為 null（不符合）。選了這些條件時，結果上方列「今日全市場」各條件的檔數與比例（分母 = 有 K 或 RSI 值的股票），因為急漲急跌時會一次出現上百檔（例：2026-11-06 KD 黃金交叉且 K < 20 有 220 檔、RSI ≤ 30 有 1,017 檔）。不提供預設組合。
 - 今日頁三大法人卡：上市為證交所 BFI82U 官方買賣金額（含 ETF；外資 = 外資及陸資，不含外資自營商，外資自營商已計入自營商），附近 20 日外資買賣超與連買／連賣天數；上櫃為櫃買 `insti/summary` 官方買賣金額（第 9 輪，2026-07-31 起；`latest.json` 的 `insti_official_tpex`，結構同 `insti_official`），另列一行（合計、外資、投信、自營）與上櫃外資 20 日迷你圖，日期早於網站資料日時標示「尚未更新」；上櫃官方尚無任何資料時才退回張數 × 收盤估算（不含 ETF）。上市、上櫃同一天時可相加，卡片不另列合計。資料表 `insti_amount` 以 `market`（`TWSE`／`TPEx`）區分市場。
 - 今日頁估值位置卡（第 9 輪，`latest.json` 的 `valuation`）：上市、上櫃股票的官方本益比、淨值比、殖利率**中位數**在近一年的位置。窗口 = 最近 242 個有官方本益比資料的交易日；中位數每天分市場計算，本益比、淨值比只計入大於 0 的股票，殖利率計入非空值（含 0）；位置 = 窗口內中位數小於或等於今天的天數 ÷ 天數；今天是窗口最低／最高時顯示「一年最低／最高」；附上市本益比中位數近 60 日迷你圖。**不是加權指數本益比**；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利；只是位置，不是買賣訊號。第 10 輪：季報窗口內、當季已有資料時，卡片下方加一行「第 3 季財報已收：上市 N、上櫃 M 家（前一季 X、Y 家）；本益比中位數會隨 EPS 更新而變動」（`latest.json` 的 `fin_progress`：`{q, n: {市場: 家數}, p: {市場: 前一季家數}}`；窗口外或當季 0 家為 null，不顯示）。第 14 輪：`fin_progress.due` = [一般業, 金融業] 申報截止日（取自 `health.FIN_DUE`，年報兩者都是 3/31，只寫一次），括號內加「一般業 11/14、金融業 11/29 截止」，資料日已過的寫「已截止」；殖利率的一年位置加「越高 = 殖利率相對越高」（方向和本益比、淨值比相反；今日頁與個股頁）。第 15 輪：截止日後面加星期（「分別是週六、週日」），截止日是週六、週日時寫「遇假日可能順延到 下週一」，「已截止」也用順延到下週一的日期判斷（例如 2026 Q3 一般業 11/14 是週六，11/16 當天仍寫「截止」，11/17 起「已截止」）；`fin_progress.due` 仍是名目日期。只處理週末，平日的國定假日不處理（網站沒有休市表）；行政程序法第 48 條規定期間末日為週六時以下週一上午為末日、週日或國定假日以次日為末日，但本站沒有查到證交所、金管會對財報申報期限的個別公告，所以寫「可能」，以官方公告為準。第 12 輪：卡片加「加權本益比（市值加權）」一行（`valuation.TWSE|TPEx.wpe`：`v` 今天值、`p` 一年位置 %、`lo`／`hi` 一年最低／最高、`cov` 計入市值占比 %、`t` [市值最大的計入股票, 占計入市值 %]）。加權本益比 = Σ 市值 ÷ Σ（市值 ÷ 官方本益比），市值 = 收盤 × `stocks.shares`（**目前股數**，歷史日期也用目前股數），只計本益比 > 0 的股票（不含虧損公司、不含 ETF）；窗口與位置定義同中位數。大型股影響大（上市台積電約占 43%），中位數反映一般股票；是本站計算，**不是證交所公布的數字**。
 - 個股頁估值位置（第 9 輪，`stocks/{代號}.json` 的 `val`：`{d, pe|pb|dy: [位置 %, 一年最低, 一年最高]}`）：本益比、淨值比、殖利率指標卡加「一年位置 N%（最低～最高）」，窗口同上，只計入大於 0 的官方值（殖利率 0 = 不配息，不算位置）。今天值為空或 ≤ 0（虧損、無股利）、窗口內有效天數少於 120 天（新上市），或 90 天內股本變動（官方值可能尚未調整）時不顯示。估值說明（第 10 輪改寫）：本益比 = 股價 ÷ 近 4 季 EPS；獲利下降時本益比會升高，獲利大增時本益比（淨值比也可能）會落到一年低點（例如景氣循環股在獲利高峰），不代表股價便宜；有季報卡時加「請對照下方季報卡的近 4 季 EPS 與一年前比較」。淨值比卡也標「資料 MM/DD」（股本變動註記照舊只在本益比、殖利率卡）。第 12 輪：個股頁指標卡加「市值」（≥ 1 萬億顯示兆）與「週轉率」（`stocks/{代號}.json` 的 `mt`：`{d, mc 億元, to %}`，目前股數計算；沒有股數的股票沒有 `mt`，兩張卡顯示 `--`）。
@@ -136,7 +136,7 @@
 - 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
 - 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。第 17 輪：收集輸出的上市注意數字標「（近 30 天）」；證交所網站（上市注意）抓取失敗時只略過上市注意並印警告，上櫃與上市處置照常寫入（下次收集會補最近 30 天）；OpenAPI 4 個來源任一失敗仍整批不寫。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
-- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。日線未滿一年時顯示「區間高／低」與起始日。
+- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
 - 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
 - 月營收：第 9 輪起從每月第一個交易日開始，`collect --catch-up` 每天第一次成功收集時抓已公布的公司（只補資料庫還沒有的公司，同一天只抓一次），直到該月家數達前一月的 98% 為止（約 10～12 日），之後到月底 0 個請求；`collect --date`、`history` 也收前一個月。月初官方檔案只有標題列時寫入 0 家，不是錯誤。
--- a/tests/test_iter18.py
+++ b/tests/test_iter18.py
@@ -0,0 +1,132 @@
+"""第 18 輪（不連網、不連資料庫）：F18-1 個股頁 KD、RSI；F18-2 選股 KD、RSI 條件與全市場比例。
+匯出端（Python）與個股頁（JS）兩套公式要一致：有 node 時直接執行 stock.js 的 calcKD、calcRSI 比對。"""
+import json
+import re
+import shutil
+import subprocess
+import sys
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+sys.path.insert(0, str(ROOT))
+from twstock import export  # noqa: E402
+
+APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
+R1 = lambda v: None if v is None else round(v, 1)
+
+
+def test_kd_formula():
+    k, d = export.calc_kd([10] * 12, [10] * 12, [10] * 12)                 # 最高 = 最低：RSV 50，K、D 維持 50
+    assert k[:8] == [None] * 8 and d[7] is None and k[8:] == [50.0] * 4 and d[8:] == [50.0] * 4
+    k, d = export.calc_kd([10] * 9, [0] * 9, [10] * 9)                     # 收在最高：RSV 100
+    assert R1(k[8]) == 66.7 and R1(d[8]) == 55.6                            # 50×2/3 + 100/3；50×2/3 + 66.67/3
+    k, d = export.calc_kd([10] * 10, [0] * 10, [10] * 9 + [0])               # 收在最低：RSV 0
+    assert R1(k[9]) == 44.4 and R1(d[9]) == 51.9
+
+
+def test_rsi_formula():
+    up = list(range(1, 17))
+    assert export.calc_rsi(up)[:14] == [None] * 14 and export.calc_rsi(up)[14:] == [100.0, 100.0]   # 只漲
+    assert export.calc_rsi(up[::-1])[14] == 0.0                                                     # 只跌
+    assert export.calc_rsi([5] * 15)[14] == 50.0                                                    # 不漲不跌
+    assert export.calc_rsi([1] * 14) == [None] * 14                                                 # 根數不足
+    c = [10, 11] * 8                                                       # 一漲一跌：前 14 次平均相等 → 50；第 15 根上漲，Wilder 平滑
+    r = export.calc_rsi(c)
+    assert r[14] == 50.0 and R1(r[15]) == round(100 - 100 / (1 + ((0.5 * 13 + 1) / 14) / (0.5 * 13 / 14)), 1)   # 第 15 根上漲
+
+
+def test_osc_stats():
+    n = 20
+    o, h, l, c = [10.0] * n, [11.0 + i % 3 for i in range(n)], [9.0] * n, [10.0 + i % 2 for i in range(n)]
+    s = export.osc_stats(o, h, l, c, [1.0] * n)
+    assert set(s) == {"k", "kx", "rsi"} and s["kx"] in (0, 1) and 0 <= s["k"] <= 100 and 0 <= s["rsi"] <= 100
+    assert export.osc_stats(o, h, l, c[:-1] + [None], [1.0] * n) == {"k": None, "kx": None, "rsi": None}   # 今天無成交
+    # 還原：係數 0.5 套到前半段的高、低、收，結果和直接給還原後的價格相同
+    af = [0.5] * 10 + [1.0] * 10
+    a = export.osc_stats(o, h, l, c, af)
+    b = export.osc_stats(o, [x * k for x, k in zip(h, af)], [x * k for x, k in zip(l, af)], [x * k for x, k in zip(c, af)], [1.0] * n)
+    assert a == b
+    # 中間無成交：以前一個收盤畫一字線（高 = 低 = 收），和直接給一字線相同；上市前的空值略過
+    c2 = c[:]; c2[12] = None
+    flat = export.osc_stats([None, None] + o, [None, None] + h[:12] + [c[11]] + h[13:], [None, None] + l[:12] + [c[11]] + l[13:],
+                            [None, None] + c[:12] + [c[11]] + c[13:], [1.0] * (n + 2))
+    assert export.osc_stats(o, h, l, c2, [1.0] * n) == flat
+    assert export.osc_stats(o[:5], h[:5], l[:5], c[:5], [1.0] * 5) == {"k": None, "kx": None, "rsi": None}   # 根數不足
+
+
+def _js(fn_names):
+    """逐字取出 stock.js 的函式原始碼。"""
+    out = []
+    for name in fn_names:
+        s = STK.index(f"function {name}(")
+        i, n = STK.index("{", s), 0
+        for j in range(i, len(STK)):
+            n += {"{": 1, "}": -1}.get(STK[j], 0)
+            if n == 0:
+                out.append(STK[s:j + 1]); break
+    return "\n".join(out)
+
+
+def test_js_matches_python():
+    node = shutil.which("node")
+    if not node:
+        print("  （沒有 node，略過 JS 比對）"); return
+    H = [10 + (i * 7) % 5 + (i % 4) * 0.3 for i in range(60)]
+    L = [x - 2 - (i % 3) * 0.5 for i, x in enumerate(H)]
+    C = [(a + b) / 2 + ((i % 5) - 2) * 0.2 for i, (a, b) in enumerate(zip(H, L))]
+    js = _js(["calcKD", "calcRSI"]) + f"\nconst H={H},L={L},C={C};const r=calcKD(H,L,C);" \
+        "console.log(JSON.stringify([r.k,r.d,calcRSI(C)]));"
+    k, d, r = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)
+    pk, pd = export.calc_kd(H, L, C)
+    pr = export.calc_rsi(C)
+    assert [R1(x) for x in k] == [R1(x) for x in pk] and [R1(x) for x in d] == [R1(x) for x in pd]
+    assert [R1(x) for x in r] == [R1(x) for x in pr]
+
+
+def test_screen_keys():
+    assert {"k", "kx", "rsi"} <= set(export.SCREEN_KEYS)
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert "**osc_stats(o, h, l, c, af)}" in src
+
+
+def test_stock_page_source():
+    assert "const OSC_OPTS = [['MACD', 'MACD'], ['KD', 'KD'], ['RSI', 'RSI']];" in STK
+    assert "segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))" in STK          # 預設 MACD
+    assert "E ? 'MACD' : localStore('osc', 'MACD'), E);" in STK                       # ETF 只有 MACD
+    assert "${E ? '' : segHTML('oscSeg'" in STK and "if (!E) onSeg('oscSeg'" in STK
+    assert "[mc, oSer, oVal]" in STK and "difSer" not in STK                          # 十字線同步跟著子圖
+    assert "osc === 'KD' ? [k, [20, 80]] : [rsi, [30, 70]]" in STK                   # 參考線
+    # 技術面卡：原本 6 項與多空判讀不變，動能一行另列
+    assert "chk(c > ma5[i], '收盤 > MA5', '收盤 < MA5');" in STK and "const total = bull.length + bear.length" in STK
+    assert "+ oscLine(k, d, rsi, i);" in STK and "動能（不計入多空）" in STK
+    assert "KD 資料不足（需 9 根）" in STK and "RSI 資料不足（需 15 根）" in STK
+    assert ".osc-line{" in CSS
+
+
+def test_no_advice_words():
+    seg = STK[STK.index("function oscLine("):STK.index("// ─── 第 10 輪 B5")] + APP[APP.index("function oscShare("):APP.index("function scrParse(")]
+    seg += "".join(re.findall(r"\{ id: '(?:kx|rl|ru)'.*?\},\n", APP, re.S))
+    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買"):
+        assert w not in seg, w
+
+
+def test_screen_source():
+    assert "const SCREEN_GROUPS = ['流動性', '價量', '技術', '法人', '信用', '基本面', '排除'];" in APP
+    for cid, opts in (("kx", "[20, 30, 50], def: 20"), ("rl", "[20, 30], def: 30"), ("ru", "[70, 80], def: 70")):
+        assert f"{{ id: '{cid}', g: '技術'" in APP and opts in APP
+    assert "x.kx === 1 && isNum(x.k) && x.k < v" in APP
+    assert "${oscShare(conds, X, cnt, st)}" in APP and "const cs = conds.filter(c => c.osc);" in APP
+    assert "X.filter(x => isNum(x.k) || isNum(x.rsi)).length" in APP                 # 分母
+    assert "k: ['K值', x => x.k" in APP and "rsi: ['RSI', x => x.rsi" in APP
+    pre = APP[APP.index("const SCREEN_PRESETS"):APP.index("const SCREEN_PRESETS") + 1200]
+    assert "kx=" not in pre and "rl=" not in pre and "ru=" not in pre               # 不加預設組合
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
```
