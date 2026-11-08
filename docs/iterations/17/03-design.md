# 第 17 輪｜System Analyst：設計規格

- 依據：`17/01-analyst.md`、`17/02-pm.md`（F17-1、F17-2；使用者已決定 D26 = B；不急的決定依 PM 建議：名稱旁不加小標、顯示「差一次」）。
- 作法（比照第 13～16 輪）：
  - 在 scratchpad `r17/` 建立兩份專案副本：`orig` = 目前程式（第 16 輪，541e861）、`proj` = 本設計。兩份都**不含 `.env`**、`_archive`、`logs`、`.git`；另補上 `scripts/` 與 `data/`（`test_iter03` 會讀）。
  - 唯讀模擬匯出：在 `proj` 執行 `export`，只執行 SELECT，輸出寫到 `proj/site/data`（scratchpad），**沒有寫專案的 `site/data`**。帳密由腳本以 setdefault 讀專案 `.env` 到環境變數，沒有印出或複製 `.env`。
  - 回測與分析腳本（唯讀 SQL）：scratchpad `r17/q1_rule.py`～`q4_backtest.py`，輸出在同名 `.txt`。
  - 預覽：8001 提供 `proj/site/`，量測 375 × 812（淺色、深色）。結束後已關閉 8001，沒有碰 8000；瀏覽器已恢復桌面大小、淺色。
  - 測試與反證：
    - `proj` 上跑 `test_iter01`～`17` 全部通過。
    - 本輪前的程式跑 `test_iter17` 失敗（上市注意丟 `FetchError` 時整批中斷）。
  - 附錄 A 的 diff 已用 `patch -p1 --dry-run` 確認可乾淨套用到目前專案。
- 本文數字來自唯讀 SQL 與模擬匯出（**資料日 2026-11-06**，`collect_runs` 最大 `run_id` = 13）。
- **外部請求 0 次、資料庫寫入 0 次、沒有 DDL**。收集端只改 `collectors/alerts.py`；`catchup.py`、`health.py` 不動。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（diff） |
|---|---|---|---|
| F17-1 | `twstock/collectors/alerts.py` | `fetch_alerts`：上市注意失敗只略過並印警告；`alert_summary(rows, days_label=False)`；`collect_alerts` 用 `days_label=True` | ＋13／−6 |
| F17-2 | `twstock/export.py` | `clauses()`、`watch_counts()`、`alert_watch()`、`COUNT_DOWN`、`WATCH_RULES`；新查詢（近 30 個交易日、注意與原因）；`latest.json` 的 `alerts.w` | ＋57 |
| F17-2 | `site/app.js` | `watchGrp(W, S)`；清單第 4 組「接近處置（推算）」 | ＋14／−1 |
| F17-2 | `site/app.css` | `.al-near` | ＋1 |
| 文件 | `README.md`、`twstock/__main__.py` | 第十一節 | ＋2／−2、＋1／−1 |
| 測試 | `tests/test_iter17.py`（新） | 8 個測試 | 140 |

- 程式＋README 約 ＋88 行。PM 估約 80 行、上限約 95 行，在上限內。
- 建議實作順序：F17-1 → F17-2 匯出（解析 → 規則 → 新鍵）→ 畫面 → 文件與測試。

---

## 一、F17-1 收集端小修

### 1-1 輸出標「近 30 天」

- 第一行改成「🚨 處置 上市 a／上櫃 b 筆、注意 上市 c（近 30 天）／上櫃 d 筆（未在股票清單的代號不寫入）」。
- **作法：`alert_summary` 加參數 `days_label`，預設 `False`；只有 `collect_alerts` 傳 `True`。**
  - 理由：`test_iter16` 的 `test_fetch_alerts_market_and_dedup` 逐字比對 `alert_summary(rows)` 的第一行，`test_alert_summary_zero_warning` 檢查 `len(out) == 1`。
  - PM 建議的「放在新的一行」會讓 `len(out)` 變成 2，舊斷言失敗；加參數則舊斷言完全不動，實際收集輸出仍是新格式（PM 驗收 #4）。
  - 新斷言在 `test_iter17` 的 `test_summary_days_label`：`days_label=True` 有「（近 30 天）」、預設沒有、`collect_alerts` 的輸出有。
- 0 筆提醒的文字不變。

### 1-2 失敗隔離

- `fetch_alerts` 用 `try／except FetchError` 包住 `fetch_twse_notice`：
  - 失敗時印「⚠️ 上市注意股抓取失敗，本次略過（其他來源照常寫入；下次收集會補最近 30 天）：錯誤訊息」，上市注意當成 0 筆，繼續抓 `_SOURCES` 4 個 OpenAPI 來源。
  - 這時 `alert_summary` 也會印「⚠️ 上市注意股最近 30 天 0 筆」，兩行同時出現，屬預期（第一行說原因，第二行是既有的 0 筆提醒）。
- **只接 `FetchError`**：
  - `fetch.request` 的網路錯誤、HTTP 錯誤、非 JSON、重試用盡都丟 `FetchError`；回應 `stat` 不是 OK 在第 16 輪已視為 0 筆，不丟錯。
  - 其他例外（例如程式錯誤）照舊往外丟，不會被吞掉。
- `_SOURCES` 任何一個丟錯：維持整批不寫（`test_openapi_failure_still_all_or_nothing`）。
- **主機已標記失敗的情況**：`request` 對同一次執行中重試用盡的主機（`_dead_hosts`）會立刻丟 `FetchError`。如果當晚日線已因 `www.twse.com.tw` 失敗，上市注意會立刻略過，不會再等重試，上櫃仍照寫。
- **`collect_alerts` 的回傳與 `alerts_at`**：
  - 只有上市注意失敗時，`collect_alerts` 正常回傳（筆數不含上市注意），`catchup._guard` 視為成功，`health` 的 `alerts_at` 會更新，當晚不再重抓。
  - 這是 PM 要的行為：上市注意每次查最近 30 天並 `MERGE`，下次收集成功就會補上。**連續失敗超過 30 天才會漏資料**；漏收期間的「已達條件」會少算（只會少、不會多）。
- 範圍外：`catchup.py`、`health.py` 的 `errors` 與回傳碼不改；所以只有上市注意失敗時，`collect` 的結束碼仍是成功，只能從那行 ⚠️ 看出來（第七節）。

---

## 二、F17-2 注意累計預警（規則 B）

### 2-1 款別解析 `clauses(reason)`

- 正規表示式：`第([一二三四五六七八九十]{1,3})款`。中文數字：「一」～「九」，「十」= 10，「十三」= 13，「二十」= 20（目前沒有）。
- 回傳 `(款別集合, 第一款是否為跌幅)`：
  - 一筆可有多款（例如第一款＋第三款＋第四款）。
  - 「第一款是否為跌幅」：取「第一款」之前、上一個「款」之後的那一段文字，含「跌幅」即是。
    - 早期寫法取前 40 字會誤判（第一款的描述常超過 40 字），已改成按「款」切段。
  - 解析不到款別：空集合，**該筆不計入**任何規則。
- `stock_alerts` 目前所有注意列（上市 10/12 起、上櫃 10/28 起）全部解析得到款別，解析不到 0 筆（`q2_clause.txt`）。上市原因用全形括號「﹝第一款﹞」，上櫃用「(第一款)」，正規表示式都適用。

### 2-2 規則與計數 `watch_counts(notes, days)`

- `days`：資料日往前 30 個交易日（含資料日），來自 `daily_prices` 的 `DISTINCT TOP 30 trade_date`，舊到新。用交易日序列，休市日自然跳過。
- `notes`：某檔 `{公告日: clauses(reason)}`。
- 回傳 4 個數字，對應 `WATCH_RULES`：

| # | 計數 | 已達條件 | 差一次 | 條件文字 |
|---|---|---|---|---|
| 1 | 第一款，從資料日往回連續幾個交易日 | ≥ 3 | = 2 | 「第一款連 N 日」 |
| 2 | 第 1～8 款任一，從資料日往回連續幾日 | ≥ 5 | = 4 | 「第 1～8 款連 N 日」 |
| 3 | 第 1～8 款，最近 10 個交易日幾次 | ≥ 6 | = 5 | 「10 日內 N 次」 |
| 4 | 第 1～8 款，最近 30 個交易日幾次 | ≥ 12 | = 11 | 「30 日內 N 次」 |

- 一天最多算一次（同一天多款仍是 1 次）。
- 第九款以後（第十款週轉率、第十三款當沖比率等）**不計**。依據：證交所處置作業要點的累計條件只算第 1～8 款；分析師列為「10 日內 5 次」的 6456，它 6 筆注意全是第十款、第十三款，所以不在預警中。
- **`COUNT_DOWN = True`（Q17-1 開關）**：
  - `True`：第一款跌幅也算「第一款連續」。這是 PM 指定的預設（計入跌幅）。
  - `False`：第一款只有漲幅才算 #1；跌幅的那天仍算第 1～8 款（#2～#4）。
  - 11/06 用 `False` 時，2360、3532 都不成立，已達條件為 0 檔（這兩檔第一款的 3 天裡有跌幅）。
  - 11/09 後看 2360、3532 是否被處置來決定；不成立時只要改這一個常數（PM 範圍變更紀錄第 2 列）。

### 2-3 兩級與排除 `alert_watch(notes, days, skip)`

- 「已達條件」：任一規則達到。條件文字列出所有達到的規則，用「、」連接。
- 「差一次」：沒有任何規則達到，但至少一條差 1。條件文字列出差 1 的規則。
- `skip` = 目前有處置紀錄的股票（`alerts` 中 `t == "disposal"`，含處置中與即將處置）→ 不列。
- 排序：已達條件在前，同級依代號。
- **歷史不足**（PM 交給 SA）：**不標示、照算**。
  - 沒有紀錄的日子當成沒列注意，只會少算，不會誤報。
  - 上市注意 10/12 起、上櫃 10/28 起；11/06 時上櫃只有 8 個交易日，「30 日內 12 次」不可能成立，「10 日內 6 次」也只差 2 天，影響很小。
  - 標「歷史不足」需要每個市場的起點常數，還要在畫面多一種狀態，效益小；上櫃 11/10 後就有完整 10 日。
  - README 寫明「注意紀錄起點之前不足的天數不補，只會少算」。
  - `test_watch_counts_and_rules` 有斷言：只有 2 天紀錄時計數為 `[0, 2, 2, 2]`，不列。

### 2-4 匯出 `latest.json` 的 `alerts.w`

- 新查詢（和第 16 輪的 `alerts` 查詢分開，因為那個只取「有效」的注意）：

```sql
SELECT DISTINCT TOP 30 trade_date FROM daily_prices WHERE trade_date <= ? ORDER BY trade_date DESC   -- 再反轉成舊到新

SELECT s.stock_code, a.announce_date, a.reason
FROM stock_alerts a JOIN stocks s ON s.stock_id = a.stock_id
WHERE a.alert_type = 'notice' AND a.announce_date >= ? AND a.announce_date <= ?    -- watch_days[0]、資料日
```

- 格式：`[[代號, 1 已達條件／0 差一次, 條件文字], ...]`。
- 寫在 `latest` 字典建好之後：`latest["alerts"]["w"] = alert_watch(...)`。
  - 理由：`test_iter16` 逐字檢查 `export.py` 裡有 `"alerts": alert_board(alerts),`，所以這行不動。
- 11/06 結果（12 檔，400 B）：

| 級別 | 代號 | 條件 |
|---|---|---|
| 已達條件 | 2360 致茂、3532 台勝科（上市） | 第一款連 3 日 |
| 差一次 | 2455（上市） | 第一款連 2 日、10 日內 5 次 |
| 差一次 | 3189、4919、5284、6451（上市）；3455、4542、6217、6488（上櫃） | 第一款連 2 日 |
| 差一次 | 6672（上市） | 10 日內 5 次 |

- 和分析師、PM 參照的差異：
  - 第一款連 2 的 9 檔完全相同。
  - 6456 不在「差一次」：原因是第十款、第十三款（2-2）。
  - 6672 是新增的「10 日內 5 次」：分析師的表只看了上市「10 日 5 次」的部分組合，`q1_rule.txt` 的「符合任一且未處置」本來就有 6672。

### 2-5 畫面（`app.js` `watchGrp(W, S)`）

- 位置：清單的「處置中」之後、「今日注意」之前（PM 建議放「今日注意」之前）。
- 組名：「接近處置（推算）　已達條件 N 檔、差一次 M 檔」。
- 已達條件：每檔一行（沿用 `.al-row`），名稱、代號・市場，右邊「已達條件」，第二行是條件文字（`.al-why`）。點整行進個股頁。
- 差一次：**只用一行**列名稱連結（「差一次：精材、⋯」），滑鼠停留顯示條件。
  - 理由：11/06 差一次 10 檔，逐檔一行會讓清單卡增加約 0.8 屏，超過 PM 的 0.5 屏上限。
  - 手機沒有滑鼠停留，條件要點進個股頁看（個股頁頁首本來就有注意原因）。
- 都沒有時顯示「無」。
- 組下說明句：「依注意款別推算（第一款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準」。
- **名稱旁不加小標**（PM 傾向不加）：已有「注」標記，再加一個「近」容易和官方標記混淆。
- 舊的 `latest.json` 沒有 `alerts.w`：`watchGrp` 回傳空字串（網站先更新、資料後更新時不報錯）。
- **選股不加條件**：`app.js` 只有清單用到 `A.w`（`test_site_source` 斷言）。

### 2-6 量測（SA 原型，375 × 812）

| 項目 | 結果 | PM 上限 |
|---|---|---|
| 清單卡高度（預設，注意 10 檔） | 1,157 px → 1,376 px，**+0.27 屏** | ≤ 0.5 屏 |
| 水平捲動 | 無（`scrollWidth` 375） | — |
| 深淺色 | 都可讀；差一次連結沿用文字色 | — |
| `latest.json` | +400 B | ≤ 3 KB |
| 匯出時間 | 23.5～23.7 秒（第 16 輪 QA 23.7 秒） | +≤ 2 秒 |

---

## 三、回測（`q4_backtest.py`，用 `alert_watch` 對歷史日期執行）

### 3-1 上市處置 4 次（PM 驗收 #1）

| 公告日 | 股票 | 規則 B | 條件 |
|---|---|---|---|
| 10/29 | 2466 | ✅ 已達條件 | 第一款連 3 日 |
| 10/29 | 4526 | ✅ 已達條件 | 第一款連 3 日 |
| 11/03 | 2466 | ✅ 已達條件（計算時不排除處置中） | 第一款連 6 日、第 1～8 款連 6 日、10 日內 6 次 |
| 11/04 | 6213 | ✅ 已達條件 | 10 日內 6 次 |

- 4/4 命中。2466 在 11/03 本身已在處置中，實際畫面不會列（排除規則），回測時暫時不排除才能驗證規則。
- 上櫃處置：上櫃注意 10/28 才開始，10/28 之後的上櫃處置前不足 3 日紀錄，本輪不回測（PM 範圍外）。

### 3-2 3167 反例（PM 驗收 #2）

- **11/06 不在預警中** ✅（回測顯示 11/03 起每天都不在已達條件或差一次）。
- 但回測期間它曾經成立：10/19（第 1～8 款連 5 日，全是第六款）、10/28（10 日內 6 次），之後沒有被處置。

### 3-3 上市誤報率（10/26～11/06）

- 已達條件且未處置的「股票日」5 次，其中 3 日內公告處置 2 次（2466、4526）。
- 沒被處置的 3 次：2424（10/27、10/28，10 日內 6 次）、3167（10/28）。
- 可能原因（本輪 0 請求，無法查證）：
  - 這兩檔在 10/21 之前可能被處置過；處置結束後的一段期間，官方計數可能重新起算。我們的處置紀錄從 10/21 開始，看不到更早的處置。
  - 第六款（本益比、股價淨值比）等款別在官方實務上可能另有門檻。
- 結論：規則 B **適合當「推算」提示，不適合當官方判斷**。畫面已用「推算」與說明句表達。建議待辦 B10-延伸c（12 月以後）加入：用證交所網站處置查詢補 10/21 前的處置歷史後，再算命中率。

---

## 四、匯出 JSON 欄位變更

| 檔案 | 鍵 | 變更 |
|---|---|---|
| `latest.json` | `alerts.w` | **新增**（2-4） |
| 其他 | — | 不變 |

- SA 原型比對：去掉 `alerts.w` 後，`latest.json` 所有鍵（`updated_at`、`status` 除外）逐值相同；`stocks/*.json` 0 檔不同；`screen.json` 相同。

---

## 五、隔離比對 `logs/iter17_compare.py`

- 由 `logs/iter16_compare.py` 改，比較 `logs/iter17_base/`（本輪前程式的匯出）與新程式匯出。
- 只允許：`latest.json` 多 `alerts.w`。其他所有檔、所有鍵逐值相同（`status.exported_at` 等時間欄位除外）。
- 兩次匯出前後都記 `collect_runs` 最大 `run_id` 與資料日；若中間使用者收集了，重做基線。
- 結果寫進 `logs/iter17_compare.log`。

---

## 六、重算 `logs/iter17_recalc.py`（唯讀 SQL）

**不 import `export`**，自己寫款別解析與規則，獨立驗算：

1. 資料日已達條件、差一次 = `alerts.w`（代號、級別、條件文字）。
2. 回測 4 次上市處置（3-1）：計算時不排除處置中。
3. 3167 在資料日不在 `alerts.w`。
4. `alerts.w` 的代號和 `alerts.d`（處置中、即將處置）沒有交集；8099、6213 不在 `alerts.w`。
5. 款別解析：近 30 個交易日的注意，解析不到款別的筆數（11/06 為 0）。
6. 用 `COUNT_DOWN = False` 的寫法重算資料日，印出結果，供 Q17-1 參考（11/06 為 0 檔已達條件）。

---

## 七、邊界情況

| 情況 | 行為 |
|---|---|
| 上市注意（證交所網站）失敗 | 印 ⚠️ 失敗行＋0 筆提醒；上櫃處置、注意與上市處置照常寫入；`alerts_at` 更新；下次收集補 30 天 |
| OpenAPI 任一來源失敗 | 整批不寫（同第 1 輪），記在 `errors["alerts"]` |
| `www.twse.com.tw` 已在本次執行標記失敗 | 上市注意立刻略過（不再等重試） |
| 原因解析不到款別 | 該筆不計入 |
| 同一天多款 | 算 1 次 |
| 只有第九款以後 | 不計（例：6456） |
| 公告日不是交易日（理論上不會） | 不在 `days` 裡，不計入 |
| 處置中、即將處置 | 不列 |
| 處置結束後 | 照常計算；舊的注意仍在 30 日窗內，可能馬上又出現在預警中（官方是否重新起算未知，見 3-3） |
| 歷史不足 | 照算、只會少算（2-3） |
| 預警為空 | `alerts.w = []`，組內顯示「無」 |
| 舊 `latest.json` 沒有 `w` | `watchGrp` 回傳空字串 |
| `daily_prices` 少於 30 個交易日 | `days` 較短，照算 |

---

## 八、QA 清單與 SQL

1. `git diff --stat`：`twstock/collectors/` 下只有 `alerts.py`；`twstock/` 另有 `export.py`、`__main__.py`；`catchup.py`、`health.py` 沒動。
2. 測試：`test_iter01`～`17` 全部通過，舊測試沒改；拿本輪前的程式跑 `test_iter17` 應失敗（反證）。
3. 重算（第六節）全部符合；比對（第五節）只多 `alerts.w`。
4. 網站（8001，375 px 與 1024 px，深淺色）：
   - 第 4 組在「處置中」與「今日注意」之間，組名的檔數 = `alerts.w`。
   - 已達條件點進個股頁、返回鍵回今日頁；差一次的連結可點、`title` 是條件。
   - 用假資料呼叫 `alertBoard`：`w` 為空顯示「無」；沒有 `w` 時不顯示第 4 組。
   - 375 px 沒有水平捲動；清單卡增加 ≤ 0.5 屏。
5. 選股沒有新條件（`SCREEN_CONDS` 不變）。
6. `latest.json` 增加 ≤ 3 KB；匯出時間增加 ≤ 2 秒。
7. **Q17-1**：若 QA 時資料日已是 11/09 以後，查 2360、3532 是否出現處置，依結果判斷 `COUNT_DOWN`（不成立時由使用者決定是否改成 `False`）。

---

## 九、測試 `tests/test_iter17.py`（新檔，全文見附錄 A）

| 測試 | 驗什麼 | 對應 PM 驗收 |
|---|---|---|
| `test_twse_notice_failure_isolated` | 上市注意丟 `FetchError`：上櫃 8099 仍寫入；輸出有警告行 | F17-1 #1 |
| `test_openapi_failure_still_all_or_nothing` | OpenAPI 回傳格式錯：丟錯、0 筆寫入 | F17-1 #2 |
| `test_summary_days_label` | 「近 30 天」只在 `days_label=True`；`collect_alerts` 輸出有 | F17-1 #3 |
| `test_clauses` | 跌幅第一款、多款、第十款～第十三款、沒有款別、`None` | F17-2 #5 |
| `test_watch_counts_and_rules` | 第一款連 3、中斷、10 日 6 次、連 5、30 日 12 次、第十三款不計、處置中不列、歷史不足 | F17-2 #4、#5 |
| `test_count_down_switch` | `COUNT_DOWN` 兩種值 | Q17-1 |
| `test_watch_sort` | 已達條件在前、同級依代號 | — |
| `test_site_source` | 畫面組名、說明句、`.al-near`、匯出寫法、選股沒用 `w` | F17-2 #6 |

- 不連網、不連資料庫：用 `patched()` 暫時換掉 `alerts` 模組的 `fetch_twse_notice`、`request`、`write_alerts`；交易日用假的日期序列（只看順序，所以「跨休市日」等於序列裡沒有那天）。

---

## 十、延後順序（沿用 PM）

PM 的延後順序是「小標 → 差一次組」。小標已決定不做；差一次組已在原型完成且在高度上限內，建議不延後。

---

## 十一、README 與 `__main__.py` 修改清單（全文見附錄 A）

- `README.md` 處置／注意股段：收集輸出「（近 30 天）」、上市注意失敗只略過。
- `README.md` `site/` 一列：`alerts.w` 格式、規則 B 四個條件、兩級、處置中不列、解析不到不計、歷史不足只會少算、「推算，以官方公告為準」、`COUNT_DOWN`、選股不提供。
- `__main__.py` 的 `export` 說明：「處置／注意股清單與接近處置推算」。

---

## 十二、PG 實作步驟

1. 記錄資料日、`collect_runs` 最大 `run_id`，確認沒有進行中的收集。把 `alerts.py`、`export.py`、`app.js`、`app.css` 複製到 `logs/iter17_before/`。
2. 基線 `export`，把 `site/data` 複製到 `logs/iter17_base/`。
3. 套用附錄 A（`patch -p1 --dry-run` 後正式套用）；`node --check site/app.js`；`test_iter01`～`17`。
4. 新程式 `export`。
5. 比對（第五節）、重算（第六節）。
6. 8001 預覽：375 px 與 1024 px，深淺色。結束後關閉 8001，恢復視窗大小。
- **允許的寫入**：只有 `export` 兩次（基線、新程式）。不執行 `collect`、`history`、`setup-db`、`backup`、還原。
- **請求：0 次**。F17-1 的失敗隔離只用單元測試驗，不要為了驗證去打證交所網站。

---

## 十三、測量摘要（SA 原型）

| 項目 | 結果 |
|---|---|
| 外部請求、資料庫寫入 | 0、0 |
| 程式＋README | 約 ＋88 行（PM 估 80、上限約 95） |
| `alerts.w`（11/06） | 12 檔（已達條件 2、差一次 10），400 B |
| 匯出耗時 | 23.5～23.7 秒 |
| 清單卡高度（375，預設） | +0.27 屏 |
| 回測 | 上市處置 4/4；3167 在 11/06 不列；上市已達條件 5 次中 2 次 3 日內處置 |
| 測試 | `proj` 的 `test_iter01`～`17` 全過；`orig` 跑 `test_iter17` 失敗 |

---

## 十四、對 PM 範圍的調整建議（不改 `02-pm.md`）

1. **「近 30 天」用參數 `days_label`，不放新的一行**：放新的一行會讓 `test_iter16` 的 `len(out) == 1` 失敗；用參數則舊斷言不動，實際輸出仍有標示（1-1）。
2. **歷史不足不標示、照算**（2-3）：只會少算、不會誤報；上櫃 11/10 後就有完整 10 日。
3. **只計第 1～8 款**：PM 寫「第 1～8 款」，SA 照做並寫明理由；結果和分析師參照差 1 檔（6456 不列、6672 新增，2-4）。
4. **差一次只列一行名稱**：逐檔一行會超過 0.5 屏上限（2-5）。
5. **名稱旁不加小標**：同 PM 傾向。
6. **新增 QA 項目**：資料日已到 11/09 以後時，順便確認 Q17-1（第八節第 7 點）。

---

## 十五、給 PG、QA 的提醒

- 11/09（週一）起使用者每晚收集。新的 `alerts.py` 一旦套用，當晚的收集輸出就有「（近 30 天）」；`alerts.w` 在下次 `export` 後出現。
- 比對前後都要記 `collect_runs`，避免混入使用者的新資料日。
- `test_iter06` 等舊測試的模擬網站沒有證交所網站來源，輸出會多「⚠️ 上市注意股最近 30 天 0 筆」，屬預期（同第 16 輪）。
- 證交所網站 `www.twse.com.tw` 的間隔是 3.5 秒，**不要**為了驗證失敗隔離去打它或模擬封鎖；單元測試已涵蓋。
- 3-3 的誤報率只是 2 週的觀察，不要寫進畫面。
- 本輪尚未 commit；是否 commit 由使用者決定。

---

## 附錄 A：完整 diff（`orig` → `proj`，含新測試檔）

```diff
--- a/twstock/collectors/alerts.py
+++ b/twstock/collectors/alerts.py
@@ -91,8 +91,14 @@
 
 
 def fetch_alerts() -> list:
-    """5 個來源全部抓完才回傳；每筆加上 market 供輸出分市場。"""
-    rows = [dict(a, market="TWSE") for a in fetch_twse_notice(date.today())]
+    """5 個來源全部抓完才回傳；每筆加上 market 供輸出分市場。
+    上市注意（證交所網站）失敗只略過它並印警告，其他 4 個來源照常（第 17 輪 F17-1：每次查 30 天，下次收集會補上）；
+    OpenAPI 4 個來源任一失敗仍整批不寫。"""
+    try:
+        rows = [dict(a, market="TWSE") for a in fetch_twse_notice(date.today())]
+    except FetchError as e:
+        print(f"  ⚠️ 上市注意股抓取失敗，本次略過（其他來源照常寫入；下次收集會補最近 {NOTICE_DAYS} 天）：{e}")
+        rows = []
     for url, kind, *fields in _SOURCES:
         data = request("GET", url)
         if not isinstance(data, list):
@@ -103,12 +109,13 @@
     return list({(a["stock_code"], a["alert_type"], a["announce_date"]): a for a in rows}.values())
 
 
-def alert_summary(rows) -> list:
-    """收集輸出：分市場筆數；某個來源 0 筆時加一行提醒（只提醒，不算失敗）。"""
+def alert_summary(rows, days_label=False) -> list:
+    """收集輸出：分市場筆數；某個來源 0 筆時加一行提醒（只提醒，不算失敗）。
+    days_label：上市注意數字後加「（近 30 天）」（第 17 輪 F17-1；collect_alerts 用，預設關閉讓輸出格式相容）。"""
     n = {(m, k): sum(a["market"] == m and a["alert_type"] == k for a in rows)
          for m in ("TWSE", "TPEx") for k in ("disposal", "notice")}
     out = [f"  🚨 處置 上市 {n['TWSE', 'disposal']}／上櫃 {n['TPEx', 'disposal']} 筆、"
-           f"注意 上市 {n['TWSE', 'notice']}／上櫃 {n['TPEx', 'notice']} 筆（未在股票清單的代號不寫入）"]
+           f"注意 上市 {n['TWSE', 'notice']}{f'（近 {NOTICE_DAYS} 天）' if days_label else ''}／上櫃 {n['TPEx', 'notice']} 筆（未在股票清單的代號不寫入）"]
     if n["TWSE", "notice"] == 0:
         out.append(f"  ⚠️ 上市注意股最近 {NOTICE_DAYS} 天 0 筆，來源可能異常，請檢查")
     if n["TPEx", "notice"] == 0:
@@ -147,5 +154,5 @@
     """5 個來源全部抓完才寫入。"""
     rows = fetch_alerts()
     write_alerts(rows)
-    print("\n".join(alert_summary(rows)))
+    print("\n".join(alert_summary(rows, days_label=True)))
     return len(rows)
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -12,6 +12,7 @@
 """
 import json
 import os
+import re
 import statistics
 import time
 from bisect import bisect_left
@@ -139,6 +140,52 @@
     return {"d": sorted(d, key=lambda x: (x[2], x[0])), "n": sorted(n)}
 
 
+# 第 17 輪 F17-2：注意累計預警（依注意款別推算，不是官方判斷）
+_CLAUSE = re.compile(r"第([一二三四五六七八九十]{1,3})款")
+_CN = {c: i for i, c in enumerate("一二三四五六七八九", 1)}
+COUNT_DOWN = True          # 第一款跌幅也算「第一款連 3 日」（Q17-1：11/09 後依 2360、3532 是否被處置確認）
+WATCH_RULES = ((3, "第一款連 {} 日"), (5, "第 1～8 款連 {} 日"), (6, "10 日內 {} 次"), (12, "30 日內 {} 次"))
+
+
+def clauses(reason):
+    """注意原因 →（款別集合, 第一款是否為跌幅）；「第十三款」→ 13。解析不到為空集合（不計入）。"""
+    out = set()
+    for t in _CLAUSE.findall(reason or ""):
+        tens, _, ones = t.rpartition("十")
+        out.add((_CN.get(tens, 1) * 10 if "十" in t else 0) + _CN.get(ones, 0))
+    return out, 1 in out and "跌幅" in (reason or "").split("第一款")[0].rsplit("款", 1)[-1]   # 第一款那一段的文字
+
+
+def watch_counts(notes, days):
+    """notes：{日期: (款別, 第一款跌幅)}；days：交易日（舊到新，最後一天 = 資料日）→ [第一款連, 1～8 款連, 10 日, 30 日]。"""
+    def ok1(k):
+        return k is not None and 1 in k[0] and (COUNT_DOWN or not k[1])
+
+    def ok8(k):
+        return k is not None and bool(k[0] & set(range(1, 9)))
+
+    def run(ok):
+        n = 0
+        while n < len(days) and ok(notes.get(days[-1 - n])):
+            n += 1
+        return n
+    return [run(ok1), run(ok8), sum(ok8(notes.get(d)) for d in days[-10:]), sum(ok8(notes.get(d)) for d in days[-30:])]
+
+
+def alert_watch(notes, days, skip):
+    """[[代號, 1 = 已達條件／0 = 差一次, 條件文字]]：已達條件在前、同級依代號；skip（處置中、即將處置）不列。"""
+    out = []
+    for code, n in notes.items():
+        if code in skip:
+            continue
+        c = watch_counts(n, days)
+        hit = [t.format(x) for x, (need, t) in zip(c, WATCH_RULES) if x >= need]
+        near = [t.format(x) for x, (need, t) in zip(c, WATCH_RULES) if x == need - 1]
+        if hit or near:
+            out.append([code, 1 if hit else 0, "、".join(hit or near)])
+    return sorted(out, key=lambda x: (-x[1], x[0]))
+
+
 def _price_events(d_, c, ch, market, official):
     """
     個股的價格調整事件（舊到新）：[{i, d, t, p, r}]。i = 生效的資料列索引（事件日當天或之後第一列），
@@ -1238,6 +1285,13 @@
         if _alert_status(kind, ann, start, end, latest_date):
             alerts[code].append({"t": kind, "a": str(ann), "s": start and str(start), "e": end and str(end),
                                  "r": reason, "m": measure})
+    watch_days = [r[0] for r in cur.execute(
+        "SELECT DISTINCT TOP 30 trade_date FROM daily_prices WHERE trade_date <= ? ORDER BY trade_date DESC", latest_date)][::-1]
+    watch_notes = defaultdict(dict)
+    for code, ann, reason in cur.execute("""
+        SELECT s.stock_code, a.announce_date, a.reason FROM stock_alerts a JOIN stocks s ON s.stock_id = a.stock_id
+        WHERE a.alert_type = 'notice' AND a.announce_date >= ? AND a.announce_date <= ?""", watch_days[0], latest_date):
+        watch_notes[code][ann] = clauses(reason)
     events = defaultdict(list)
     for code, d, t, p, r, src in cur.execute("""
         SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
@@ -1497,6 +1551,9 @@
         "alerts": alert_board(alerts),                          # 第 16 輪 F16-3：今日頁處置／注意清單
         "stocks": snapshot,
     }
+    # 第 17 輪 F17-2：注意累計預警（推算）；處置中、即將處置不列
+    latest["alerts"]["w"] = alert_watch(watch_notes, watch_days,
+                                        {c for c, v in alerts.items() if any(a["t"] == "disposal" for a in v)})
     # screen.json 在 latest.json 之前寫：中途失敗時前端比對 d／fd 會顯示不同步
     S = screen_build(screen, {"d": str(latest_date), "fd": str(dates[-1]), "md": {m: str(d) for m, d in mlast.items()},
                               "sd": {m: str(d) for m, d in slast.items()}})
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -16,7 +16,7 @@
   python -m twstock history --start 2024-01-01 --only financials  只補季報（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
-  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/、etfp/；含季報、期現貨價差與下次結算日、營收與 EPS 基期、ETF 個股頁、處置／注意股清單）
+  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/、etfp/；含季報、期現貨價差與下次結算日、營收與 EPS 基期、ETF 個股頁、處置／注意股清單與接近處置推算）
   python -m twstock serve                            本機預覽網站 http://localhost:8000
   python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
   python -m twstock chains                           更新產業鏈族群（櫃買產業價值鏈平台）
--- a/site/app.js
+++ b/site/app.js
@@ -326,11 +326,24 @@
   const grp = (t, list, n = list.length) => `<div class="al-grp"><h3>${t}　<span class="muted small">${n} 檔</span></h3>${list.join('') || '<div class="muted small">無</div>'}</div>`;
   return `<section class="sec card">
       <div class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}</span><span class="sp"></span>${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}</div>
-      ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])), A.n.length)}
+      ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${watchGrp(A.w, S)}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])), A.n.length)}
       <div class="muted small">依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因</div>
     </section>`;
 }
 
+// 第 17 輪 F17-2：接近處置（依注意款別推算）；已達條件逐檔一行，差一次只列名稱（提示是條件）
+function watchGrp(W, S) {
+  if (!W) return '';
+  const hit = W.filter(x => x[1]), near = W.filter(x => !x[1]);
+  const nm = c => esc(S[c]?.n || c);
+  return `<div class="al-grp"><h3>接近處置（推算）　<span class="muted small">已達條件 ${hit.length} 檔、差一次 ${near.length} 檔</span></h3>
+      ${hit.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${S[x[0]]?.m === 'TWSE' ? '上市' : '上櫃'}</span><span class="sp"></span><span class="small">已達條件</span></div>
+        <div class="muted small al-why">${esc(x[2])}</div></a>`).join('')}
+      ${near.length ? `<div class="al-near small"><span class="muted">差一次：</span>${near.map(x => `<a href="#/stock/${x[0]}" title="${esc(x[2])}">${nm(x[0])}</a>`).join('、')}</div>` : ''}
+      ${W.length ? '' : '<div class="muted small">無</div>'}
+      <div class="muted small">依注意款別推算（第一款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準</div></div>`;
+}
+
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
 function breadthCard(L) {
   const B = L.breadth;
--- a/site/app.css
+++ b/site/app.css
@@ -214,6 +214,7 @@
 .pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
 .al-grp{margin-top:8px}.al-grp h3{font-size:13px;margin:0 0 4px}                 /* 第 16 輪 F16-3 */
 .al-row{display:block;padding:5px 0;border-top:1px solid var(--border);color:inherit;text-decoration:none}
+.al-near{padding:5px 0;border-top:1px solid var(--border);line-height:1.7}.al-near a{color:inherit}       /* 第 17 輪 F17-2 */
 .al-l{display:flex;align-items:baseline;gap:6px}.al-l .sp{flex:1}.al-why{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .al-new{background:var(--blue)}                                  /* E2-4：新建倉 */
 .pill.hold{margin-left:6px;border-color:var(--blue);color:var(--blue)}
--- a/README.md
+++ b/README.md
@@ -17,7 +17,7 @@
 | `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
 | `twstock/export.py` | 匯出 `site/data/latest.json`、`screen.json`（條件選股與排行擴充用）、`stocks/{代號}.json`、`etfs/{代號}.json`、`etfp/{代號}.json`（第 15 輪 ETF 個股頁） |
 | `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
-| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延。第 16 輪：今日頁「總覽」最下方加處置／注意股清單（即將處置、處置中、今日注意三組；`latest.json` 的 `alerts`：`d` = [代號, 起日, 迄日, 措施, 原因]、`n` = [代號, 原因]，原因只取第一句、最多 60 字，完整原因在個股頁），注意組預設 10 檔可按「注意顯示全部」；同一檔多段處置重疊時，`dsp` 與清單合併為 [最早起日, 最晚迄日] |
+| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延。第 16 輪：今日頁「總覽」最下方加處置／注意股清單（即將處置、處置中、今日注意三組；`latest.json` 的 `alerts`：`d` = [代號, 起日, 迄日, 措施, 原因]、`n` = [代號, 原因]，原因只取第一句、最多 60 字，完整原因在個股頁），注意組預設 10 檔可按「注意顯示全部」；同一檔多段處置重疊時，`dsp` 與清單合併為 [最早起日, 最晚迄日]。第 17 輪：清單加「接近處置（推算）」組（`latest.json` 的 `alerts.w` = [代號, 1 已達條件／0 差一次, 條件文字]），依注意原因的「第 N 款」推算：第一款（6 日累積漲跌幅）連 3 個交易日，或第 1～8 款連 5 日、10 個交易日內 6 次、30 個交易日內 12 次為「已達條件」，再 1 次即達為「差一次」；處置中、即將處置的股票不列；原因解析不到款別的那筆不計入。注意紀錄起點（上市 2026-10-12、上櫃 10-28）之前不足的天數不補，只會少算。只是推算，是否處置以官方公告為準；`export.COUNT_DOWN` = False 時第一款的跌幅不計入「第一款連續」。選股不提供此條件 |
 | `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`、`python3 tests/test_iter08.py`、`python3 tests/test_iter09.py`、`python3 tests/test_iter10.py` |
 | `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
 | `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
@@ -134,7 +134,7 @@
 - 個股頁估值位置（第 9 輪，`stocks/{代號}.json` 的 `val`：`{d, pe|pb|dy: [位置 %, 一年最低, 一年最高]}`）：本益比、淨值比、殖利率指標卡加「一年位置 N%（最低～最高）」，窗口同上，只計入大於 0 的官方值（殖利率 0 = 不配息，不算位置）。今天值為空或 ≤ 0（虧損、無股利）、窗口內有效天數少於 120 天（新上市），或 90 天內股本變動（官方值可能尚未調整）時不顯示。估值說明（第 10 輪改寫）：本益比 = 股價 ÷ 近 4 季 EPS；獲利下降時本益比會升高，獲利大增時本益比（淨值比也可能）會落到一年低點（例如景氣循環股在獲利高峰），不代表股價便宜；有季報卡時加「請對照下方季報卡的近 4 季 EPS 與一年前比較」。淨值比卡也標「資料 MM/DD」（股本變動註記照舊只在本益比、殖利率卡）。第 12 輪：個股頁指標卡加「市值」（≥ 1 萬億顯示兆）與「週轉率」（`stocks/{代號}.json` 的 `mt`：`{d, mc 億元, to %}`，目前股數計算；沒有股數的股票沒有 `mt`，兩張卡顯示 `--`）。
 - 今日頁法人買超／賣超表與錢流標示「估算，不含 ETF」；三大法人卡的官方值含 ETF 與權證避險，兩者口徑不同。
 - 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
-- 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。
+- 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。第 17 輪：收集輸出的上市注意數字標「（近 30 天）」；證交所網站（上市注意）抓取失敗時只略過上市注意並印警告，上櫃與上市處置照常寫入（下次收集會補最近 30 天）；OpenAPI 4 個來源任一失敗仍整批不寫。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
 - 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。日線未滿一年時顯示「區間高／低」與起始日。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
--- a/tests/test_iter17.py
+++ b/tests/test_iter17.py
@@ -0,0 +1,140 @@
+"""第 17 輪（不連網、不連資料庫）：F17-1 收集輸出「近 30 天」、上市注意失敗不拖累其他來源；
+F17-2 注意累計預警（款別解析、規則 B、差一次、處置中不列）。"""
+import sys
+from contextlib import contextmanager, redirect_stdout
+from datetime import date, timedelta
+from io import StringIO
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+sys.path.insert(0, str(ROOT))
+from twstock import export  # noqa: E402
+from twstock.collectors import alerts  # noqa: E402
+from twstock.fetch import FetchError  # noqa: E402
+
+APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
+
+
+@contextmanager
+def patched(**kw):
+    """暫時換掉 alerts 模組的函式（不連網、不連資料庫）。"""
+    old = {k: getattr(alerts, k) for k in kw}
+    for k, v in kw.items():
+        setattr(alerts, k, v)
+    try:
+        yield
+    finally:
+        for k, v in old.items():
+            setattr(alerts, k, v)
+
+
+TPEX_N = [{"SecuritiesCompanyCode": "8099", "Date": "1151106", "TradingInformation": "第一款"}]
+
+
+def _openapi(m, url, **kw):
+    return TPEX_N if "tpex_trading_warning" in url else []
+
+
+def test_twse_notice_failure_isolated():
+    def boom(end, days=30):
+        raise FetchError("www.twse.com.tw 連續失敗")
+    written, buf = [], StringIO()
+    with patched(fetch_twse_notice=boom, request=_openapi, write_alerts=written.extend), redirect_stdout(buf):
+        n = alerts.collect_alerts()
+    assert n == 1 and [a["stock_code"] for a in written] == ["8099"]          # 上櫃照寫
+    out = buf.getvalue()
+    assert "上市注意股抓取失敗，本次略過" in out and "下次收集會補最近 30 天" in out
+
+
+def test_openapi_failure_still_all_or_nothing():
+    def bad(m, url, **kw):
+        return {"oops": 1} if "punish" in url else []
+    written = []
+    with patched(fetch_twse_notice=lambda end, days=30: [], request=bad, write_alerts=written.extend):
+        try:
+            alerts.collect_alerts()
+            raise AssertionError("應丟 FetchError")
+        except FetchError:
+            pass
+    assert written == []
+
+
+def test_summary_days_label():
+    rows = [{"market": "TWSE", "alert_type": "notice"}, {"market": "TPEx", "alert_type": "notice"}]
+    assert "注意 上市 1（近 30 天）／上櫃 1 筆" in alerts.alert_summary(rows, days_label=True)[0]
+    assert "注意 上市 1／上櫃 1 筆" in alerts.alert_summary(rows)[0]                 # 預設不變（第 16 輪格式）
+    buf = StringIO()
+    with patched(fetch_alerts=lambda: rows, write_alerts=lambda r: None), redirect_stdout(buf):
+        alerts.collect_alerts()
+    assert "（近 30 天）" in buf.getvalue()
+
+
+def test_clauses():
+    assert export.clauses("最近六個營業日累積收盤價跌幅達45.70%。且價差達550.00元﹝第一款﹞。") == ({1}, True)
+    assert export.clauses("漲幅達33.07%﹝第一款﹞。且成交量﹝第三款﹞。且週轉率﹝第四款﹞。") == ({1, 3, 4}, False)
+    assert export.clauses("當沖比率﹝第十三款﹞。另跌幅達30%﹝第一款﹞") == ({1, 13}, True)
+    assert export.clauses("(第十款)") == ({10}, False) and export.clauses("第十一款") == ({11}, False)
+    assert export.clauses("本益比﹝第六款﹞") == ({6}, False)
+    assert export.clauses("沒有款別") == (set(), False) and export.clauses(None) == (set(), False)
+
+
+D = [date(2026, 10, 1) + timedelta(days=i) for i in range(40)]      # 假的交易日序列（只看順序）
+C1, C1D, C6, C13 = ({1}, False), ({1}, True), ({6}, False), ({13}, False)
+
+
+def test_watch_counts_and_rules():
+    days = D[:30]
+    n = {days[-1]: C1, days[-2]: C1, days[-3]: C1}
+    assert export.watch_counts(n, days) == [3, 3, 3, 3]
+    assert export.alert_watch({"2466": n}, days, set()) == [["2466", 1, "第一款連 3 日"]]
+    n = {days[-1]: C1, days[-2]: C1, days[-4]: C1}                                   # 中間斷一天
+    assert export.watch_counts(n, days)[:2] == [2, 2]
+    assert export.alert_watch({"x": n}, days, set()) == [["x", 0, "第一款連 2 日"]]
+    six = {days[-i]: C6 for i in (1, 2, 4, 6, 8, 10)}                                 # 10 日內 6 次（第六款）
+    assert export.alert_watch({"6213": six}, days, set()) == [["6213", 1, "10 日內 6 次"]]
+    five = {days[-i]: C6 for i in (1, 2, 3, 4, 5)}
+    assert export.alert_watch({"y": five}, days, set())[0][1:] == [1, "第 1～8 款連 5 日"]
+    twelve = {days[-i]: C6 for i in range(1, 30, 2)[:12]}                              # 30 日內 12 次、不連續
+    assert export.alert_watch({"z": twelve}, days, set())[0][2] == "30 日內 12 次"
+    only13 = {d: C13 for d in days}                                                     # 第十三款不計
+    assert export.alert_watch({"w": only13}, days, set()) == []
+    assert export.alert_watch({"8099": n}, days, {"8099"}) == []                        # 處置中不列
+    short = {days[-1]: C6, days[-2]: C6}                                               # 歷史不足（例如上櫃 10/28 起）：沒紀錄的日子當成沒注意，只會少算
+    assert export.watch_counts(short, days) == [0, 2, 2, 2] and export.alert_watch({"v": short}, days, set()) == []
+
+
+def test_count_down_switch():
+    days = D[:30]
+    n = {days[-1]: C1D, days[-2]: C1D, days[-3]: C1D}
+    assert export.alert_watch({"2360": n}, days, set())[0][1] == 1
+    old, export.COUNT_DOWN = export.COUNT_DOWN, False
+    try:
+        assert export.alert_watch({"2360": n}, days, set()) == []                       # 跌幅不算第一款連續；1～8 款只連 3
+        assert export.watch_counts(n, days) == [0, 3, 3, 3]
+    finally:
+        export.COUNT_DOWN = old
+
+
+def test_watch_sort():
+    days = D[:30]
+    hit = {days[-1]: C1, days[-2]: C1, days[-3]: C1}
+    near = {days[-1]: C1, days[-2]: C1}
+    assert [x[0] for x in export.alert_watch({"9999": hit, "1111": near, "2222": hit}, days, set())] == ["2222", "9999", "1111"]
+
+
+def test_site_source():
+    assert "function watchGrp(W, S)" in APP and "${watchGrp(A.w, S)}" in APP
+    assert "接近處置（推算）" in APP and "是否處置以官方公告為準" in APP and "差一次：" in APP
+    assert ".al-near{" in CSS
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert 'latest["alerts"]["w"] = alert_watch(watch_notes, watch_days,' in src and "COUNT_DOWN = True" in src
+    assert APP.count("A.w") == 1 and "alerts.w" not in APP  # 只有今日清單用到；選股不加預警條件
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
```
