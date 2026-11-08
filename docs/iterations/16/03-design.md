# 第 16 輪｜System Analyst：設計規格

- 依據：`16/01-analyst.md`、`16/02-pm.md`（F16-1～F16-3；使用者已決定 D25 = B；不急的決定依 PM 建議：清單放總覽分頁最下方、注意組預設 10 檔；回補方式見第十四節調整建議 1）。
- 作法（比照第 13～15 輪）：
  - 在 scratchpad `r16/` 建立兩份專案副本：`orig` = 目前程式、`proj` = 本設計。兩份都**不含 `.env`**、`_archive`、`logs`、`.git`。
  - 唯讀模擬匯出：在 `proj` 執行 `export`。它只執行 SELECT，輸出寫到 `proj/site/data`（scratchpad），**沒有寫專案的 `site/data`**。帳密由模擬腳本以 setdefault 讀 `.env` 到環境變數，沒有印出或複製 `.env`。
  - 預覽：8001 提供 `proj/site/`，量測 375 × 812（深色）與 1024 寬。結束後已關閉 8001，沒有碰 8000。
  - **上市注意股是模擬注入**：資料庫目前沒有上市注意股，所以預覽前把查證回應中 11/06 的 36 筆（都在 `stocks` 表）寫進 scratchpad 的 `latest.json`。只用於版面量測，沒有寫資料庫。
  - 測試與反證：
    - `proj` 上跑 `test_iter01`～`16` 全部通過；`orig` 上跑 `test_iter01`～`15` 也全部通過。副本要先補上 `scripts/` 與 `data/`，`test_iter03` 會讀 `scripts/mac/install_schedule.sh`。
    - 本輪前的程式跑 `test_iter16` 失敗（`roc_date("115.11.05")` 是 None）。
  - 附錄 A 的 diff 已用 `patch -p1 --dry-run` 確認可乾淨套用到目前專案。
- 本文數字都來自唯讀 SQL、模擬匯出與查證回應（**資料日 2026-11-06**，`collect_runs` 最大 `run_id` = 13）。
- **外部請求 3 次**（PM 上限 5 次）：
  - 都是查證，經 `twstock/fetch.py` 的 `request`，沒有另加 header（D6）。
  - 原始回應在 scratchpad `r16/raw/p1.json`、`p2.json`、`p3.json`。
- **0 個資料庫寫入、沒有 DDL**。收集端只改 `collectors/alerts.py`；`catchup.py`、`health.py`、`tradingcal.py` 不動。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（diff） |
|---|---|---|---|
| F16-1 | `twstock/collectors/alerts.py` | `TWSE_NOTICE`、`NOTICE_DAYS`；`roc_date` 支援 `115.11.05`；`parse_alert` 去掉 HTML 標籤；`parse_twse_notice()`、`fetch_twse_notice()`；`fetch_alerts` 加上市注意與 `market`；`alert_summary()`（分市場輸出與 0 筆提醒）；`collect_alerts` 拆出 `write_alerts()` | ＋53／−11 |
| F16-2 | `twstock/export.py` | `disposal_span()`；`latest.json` 的 `dsp` 改用它 | ＋7／−3 |
| F16-3 | `twstock/export.py` | `_short()`、`alert_board()`；`latest.json` 新鍵 `alerts` | ＋25 |
| F16-3 | `site/app.js` | `alertBoard(L)`；總覽分頁加清單；「注意顯示全部」按鈕（`App.alertAll`） | ＋22 |
| F16-3 | `site/app.css` | `.al-grp`、`.al-row`、`.al-l`、`.al-r` | ＋3 |
| 文件 | `README.md`、`twstock/__main__.py` | 第十一節 | ＋2／−2、＋2／−2 |
| 測試 | `tests/test_iter16.py`（新） | 8 個測試 | 131 |

- 程式＋README 約 ＋112 行。PM 估約 98 行、上限 140 行，在上限內。
- 主要差在 `alerts.py`：因為 `test_iter01` 會把 `_SOURCES` 拆成 4 組使用，新來源不能放進 `_SOURCES`，只能另寫一個函式（第一節 1-3）。

### 建議實作順序

同 PM 相依性：F16-2 → F16-1（解析 → 輸出 → dry-run → 回補一次）→ F16-3 → 文件與測試。細節見第十二節。

---

## 一、F16-1 上市注意股

### 1-1 查證結果（3 次請求）

| # | 請求 | 結果 |
|---|---|---|
| p1 | `GET https://www.twse.com.tw/rwd/zh/announcement/notice`，`startDate=20261021`、`endDate=20261106` | `stat: "OK"`、`total: 216`、`data` 216 列（一次回傳全部，**沒有分頁**） |
| p2 | 同上，`20261001`～`20261106`（37 天） | `stat: "OK"`、479 列。**超過 30 天的區間可以查**，10/01 起每天都有 |
| p3 | 同上，`20261107`～`20261108`（休市） | `stat: "OK"`、`data: []`、`total: 0`。**休市不是錯誤，是空清單** |

- 完整參數：`querytype=1&stockNo=&selectType=&proceType=&startDate=YYYYMMDD&endDate=YYYYMMDD&sortKind=STKNO&response=json`。
- `fields`：`["編號","證券代號","證券名稱","累計次數","注意交易資訊","日期","收盤價","本益比"]`。
- 欄位說明：
  - `日期`：民國年用點分隔，例如 `115.11.05`。現有 `roc_date` 不支援這種寫法，要補。
  - `注意交易資訊`：可能含 HTML，例如 `<font color='#FF0000'>﹝第十三款﹞</font>`，要去掉標籤。
  - `累計次數`：同一檔在**查詢區間內**的次數，每一列都一樣，**不是**當天的累計次數。本輪不使用（B10-延伸b 可以自己數）。
  - 同一檔同一天只有一列（p1：182 個 (代號, 日期) 組合 = 182 列有效列）。
  - 包含權證（例如 `040609`），由 `is_valid_stock_code` 過濾。216 列中有效 182 列。

### 1-2 反證（用 p1，對照分析師與 PM 的驗收）

| 檢查 | 結果 |
|---|---|
| 6213 在 10/21～11/04 的注意 | 10/22、10/27、10/28、10/29、10/30、11/02、11/04 共 **7 次**（≥ 6 ✅；另有 11/05 一次）。和 11/04 處置原因「十個營業日內已有六個營業日」一致 |
| 2466 處置公告 10/29 前的連續 3 日 | 10/27、10/28、10/29 ✅ |
| 4526 處置公告 10/29 前的連續 3 日 | 10/27、10/28、10/29 ✅ |
| 11/06 上市注意 | **36 檔**（全部在 `stocks` 表） |
| 分析師 1-3 節的 13 檔（6 日漲跌 > 32%） | **10 檔**在 11/06 清單（≥ 一半 ✅）。不在的是 2467、6213、2351；條款一還要和大盤比較，6213 當天已在處置中 |
| 逐日上市注意（有效列） | 10/21 10、10/22 14、10/27 18、10/28 16、10/29 10、10/30 10、11/02 12、11/03 9、11/04 23、11/05 24、11/06 36，合計 182 |

- 10/23、10/26 沒有任何注意股。上櫃（`stock_alerts`）也一樣，是休市日。

### 1-3 程式設計（`collectors/alerts.py`）

1. **保留 `_SOURCES` 的 4 個來源不動**：
   - 包含 OpenAPI `announcement/notice`。
   - 理由：`test_iter01` 的 `test_parse_alert` 用 `twse_d, twse_n, tpex_d, tpex_n = (s[1:] for s in _SOURCES)` 拆成 4 組，拿掉會讓舊測試失敗（PM 不允許改舊斷言）。
   - OpenAPI `notice` 繼續回傳佔位列時沒有作用；哪天恢復了也只是重複（第 4 點去重）。
   - 代價：每天 +1 次請求（PM 表格寫「每天 +1；若取代則 ±0」，本設計是 +1）。
2. **新來源**：
   - `TWSE_NOTICE = (網址, "notice", "證券代號", "日期", None, "注意交易資訊", None)`，格式同 `_SOURCES` 的一列，可以直接傳給 `parse_alert`。
   - `fetch_twse_notice(end, days=NOTICE_DAYS)`：查 `end − 30 天`～`end`，1 次請求。
   - `parse_twse_notice(data)`：
     - 把每列 `dict(zip(fields, row))` 交給 `parse_alert`。
     - 回應不是 dict，或 `data` 不是 list → `FetchError`（整批不寫，同現有行為）。
     - `stat` 不是 `"OK"`（例如「很抱歉，沒有符合條件的資料!」）→ 回傳 `[]`，交給 0 筆提醒。
       - 理由 1：證交所其他 rwd 端點沒有資料時常回這種 `stat`。
       - 理由 2：舊測試（`test_iter03`、`04`、`05`、`06`、`07`、`11`）的模擬網站對未知網址回 `{"stat": "沒有資料"}`。若當成錯誤，舊測試的 `alerts` 會失敗。
       - 封鎖頁是 HTML，`request` 本來就會丟錯，不受影響。
3. **每天查最近 30 天，不另做回補指令**：
   - 每天收集都查最近 30 天，用 `MERGE` 寫入（鍵是 (stock_id, alert_type, announce_date)，重跑不會重複）。漏收 30 天內的日子，下次收集就會自動補上。
   - 所以「可重跑的回補」就是平常的收集，**不需要新指令或新參數**（第十四節調整建議 1）。
   - p2 證實 37 天的區間可查；30 天約 400 列、120～140 KB。
   - `end` 用 `date.today()`。午夜後的 catch-up 仍涵蓋前一天。
4. **`fetch_alerts`**：
   - 先上市注意（新來源），再跑 `_SOURCES` 的 4 個；每筆加 `market`（`"TWSE"`／`"TPEx"`，依網址判斷）。
   - 最後依 (代號, 類型, 公告日) 去重，同現有程式；後來的覆蓋前面的，所以 OpenAPI 恢復時以 OpenAPI 為準。
   - `market` 只用於輸出，`MERGE` 的 `OPENJSON ... WITH` 只取列出的欄位，會忽略它。
5. **`parse_alert` 去掉 HTML 標籤**：`_TAG.sub("", text)`。
   - 對現有 4 個來源：資料庫 154 筆注意、21 筆處置的 `reason`、`measure` 都不含 `<`（唯讀 SQL 確認），既有列不會因此改變。
6. **`roc_date`**：先把 `.` 換成 `/`。`events.py` 也會呼叫它，但它的日期沒有點，不受影響（`test_iter03` 的事件測試通過）。
7. **`alert_summary(rows)`**（收集輸出，取代原本的一行）：
   - 第一行：`  🚨 處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆（未在股票清單的代號不寫入）`。
     - 筆數是「回應中有效的列數」，上市注意是 30 天的總數（例如 11/06 收集約 180）。
   - 上市注意 0 筆 → 加一行 `⚠️ 上市注意股最近 30 天 0 筆，來源可能異常，請檢查`。30 天內一定有交易日，所以 0 筆一定是異常。
   - 上櫃注意 0 筆 → 加一行 `⚠️ 上櫃注意股 0 筆：若今天是交易日，請留意來源是否異常`。上櫃 OpenAPI 只有近幾日，週末也可能有資料，所以寫成提醒。
   - **只印，不算失敗**：不改 `catchup.py` 的 `errors`、`health.py`、回傳碼（PM 第二節 F16-1 #5）。
8. **`write_alerts(rows)`**：從 `collect_alerts` 拆出 `MERGE`，內容逐字不變，讓 PG 的一次性回補可以只寫上市注意（第十二節步驟 4）。

### 1-4 每天的請求數

| 來源 | 本輪前 | 本輪 |
|---|---|---|
| 證交所 OpenAPI punish、notice | 2 | 2 |
| 櫃買 OpenAPI 處置、注意 | 2 | 2 |
| 證交所網站注意股查詢 | 0 | **1**（`www.twse.com.tw`，`fetch.py` 間隔 3.5 秒） |

- catch-up 每個交易日最多抓 `alerts` 兩次（15:00 後、19:00 後），所以每天最多 +2 次。

---

## 二、F16-2 重疊處置合併區間

- `export.disposal_span(items)`：只看 `t == "disposal"` 的有效段，回傳 `[min(起日), max(迄日)]`，沒有處置時回傳 None。
- `latest.json`：`"dsp": disposal_span(alerts[code])`（取代 `min([s, e])`）。
- 「即將處置」：網站仍用 `dsp[0] > 資料日` 判斷。`dsp[0]` 仍是最早起日，所以語意不變：只要有一段已經開始，就是「處置中」。
- 11/06 模擬匯出：
  - 8099 `dsp` = **["2026-11-02", "2026-11-11"]**（本輪前 ["2026-11-02", "2026-11-06"]）。
  - 其他 8 檔逐值不變（`dsp` 共 9 檔）。
- 兩段不重疊（中間隔幾天）時，合併會把空檔也算成處置中。目前資料中不存在這種情況：第二段都是「30 日內再次處置」，接在第一段後面或重疊。若出現，最多讓提示的迄日寫晚的那一段，不會漏掉風險。這是刻意的保守做法。

---

## 三、F16-3 今日頁處置／注意清單

### 3-1 匯出：`latest.json` 新鍵 `alerts`

```json
"alerts": {
  "d": [["8099", "2026-11-02", "2026-11-11", "約每2分鐘撮合一次、預收款券", "連續3個營業日達本中心「公布注意交易資訊」標準，且最近30個營業日內曾發布處置"], ...],
  "n": [["1569", "最近六個營業日(自當日之前一個營業日起)之當日沖銷成交量占總成交量比率達76.94%，當日之前一個營業日當日沖銷成交量占…"], ...]
}
```

- 來源：匯出現有的 `alerts` dict（已依 `_alert_status` 過濾成有效處置與當天注意）。不新增 SQL。
- `d`（處置，含即將）：
  - 每檔一列：[代號, 最早起日, 最晚迄日（同 `disposal_span`）, 措施, 原因]。
  - 措施、原因取**公告日最晚**的那段。
  - 依迄日、代號排序。
- `n`（今日注意）：[代號, 原因]，依代號排序。
- 原因裁短 `_short(text, 60)`：
  - 取第一個「。」之前的部分，去掉開頭的「該有價證券之交易，」（上市處置原因都以這句開頭）。
  - 超過 60 字截斷並加「…」。
  - 完整原文仍在 `stocks/{代號}.json` 的 `alerts`（不變）。
- 名稱、市場不放進清單，網站從 `latest.stocks[代號]` 的 `n`、`m` 取得，不重複。
- 大小（緊湊 JSON）：
  - 11/06 實際（只有上櫃注意）：處置 9、注意 26，**5.4 KB**。
  - 模擬補上市注意後：處置 9、注意 62，**8.9 KB**。
  - 都在 PM 上限 15 KB 內。
- 匯出耗時：模擬 23.7 秒（第 15 輪 QA 25.0 秒），沒有可量測的增加。

### 3-2 畫面（`app.js` `alertBoard(L)`，總覽分頁最下方，資金象限之後）

- 一張卡，標題「處置／注意股」＋資料日；注意超過 10 檔時右上角有「注意顯示全部／注意只顯示 10 檔」切換（`App.alertAll`，做法同 `App.flowAll`，不存瀏覽器）。
- 三組依序：
  - **即將處置**：`d` 中起日 > 資料日。
  - **處置中**：其餘的 `d`。
  - **今日注意**：`n`，預設前 10 檔。
  - 組名旁顯示「N 檔」（注意組顯示全部的檔數）；空組顯示「無」。
- 每檔兩行，整列是連到 `#/stock/{代號}` 的連結：
  - 第一行：**名稱** 代號・上市／上櫃，右側處置期間「MM/DD～MM/DD」（注意組沒有）。
  - 第二行（灰、小字、一行，超出以「…」截斷）：處置是「措施｜原因」，注意是原因。
  - 滑鼠提示（`title`）是第二行的完整文字；完整公告原文在個股頁。
- 卡片底部說明：「依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因」。
- 不顯示「剩餘交易日」：PM 交給 SA 決定。迄日已在右側，加剩餘日數要多匯出一欄，價值低。
- 名稱旁的「處」「注」小標、選股的兩個排除開關：程式不改，`dsp`、`ntc` 的值改變後自然生效（上市注意股會出現「注」）。

### 3-3 量測（SA 原型，375 × 812，模擬補上市注意後）

| 項目 | 結果 | PM 驗收 |
|---|---|---|
| 清單卡高度（預設：處置 9、注意 10） | **1,157 px = 1.42 屏** | ≤ 1.5 屏 ✅ |
| 清單卡高度（顯示全部：注意 62） | 3,757 px | —（使用者主動展開） |
| 總覽分頁整頁 | 2,348 px（第 13 輪 QA 的總覽約 1.45 屏 ≈ 1,180 px） | — |
| 整頁水平捲動 | 無（375、1024 都是 `scrollWidth` = 視窗寬） | ✅ |
| 1024 寬 | 卡片寬 992 px，高 1,139 px | — |

- 第一版原型每列 3～4 行（措施、原因各一行並換行），高度 1,625 px = 2.0 屏，超過上限，所以改成上面的兩行版。
- 深色模式截圖可讀。淺色沿用既有的 `--muted`、`--border` 變數，沒有新顏色。

---

## 四、匯出 JSON 欄位變更

| 檔案 | 鍵 | 變更 |
|---|---|---|
| `latest.json` | `alerts` | **新增**（第三節） |
| `latest.json` | `stocks.{代號}.dsp` | 值改為合併區間（11/06 只有 8099 改變） |
| `latest.json` | `stocks.{代號}.ntc` | 格式不變。F16-1 回補後，上市注意股的 `ntc` 會出現（11/06 為 36 檔） |
| `stocks/{代號}.json` | `alerts` | 格式不變。回補後上市股票會多出 `t == "notice"` 的項目 |
| 其他 | — | 不變 |

---

## 五、隔離比對 `logs/iter16_compare.py`

- 由 `logs/iter15_compare.py` 改，比較 `logs/iter16_base/`（本輪前程式、回補前資料）與新匯出。
- **要分兩次比**，才能把「程式改變」和「資料改變」分開：
  1. **回補前**：新程式匯出 vs 基線。只允許 `latest.json` 多 `alerts`、8099 的 `dsp` 改變；其他所有檔、所有鍵逐值相同（`status.exported_at` 除外）。
  2. **回補後**：新程式匯出 vs 第 1 次的新匯出。只允許：
     - 上市股票的 `stocks/{代號}.json` 的 `alerts` 多出 `t == "notice"` 項目（既有項目逐值相同）。
     - 這些股票在 `latest.json` 的 `ntc` 從無到 1。
     - `latest.json` 的 `alerts.n` 多出上市代號。
     - 其他逐值相同。上櫃股票完全相同。
- 每一次比對都要先確認 `collect_runs` 最大 `run_id` 和資料日沒變。若中間使用者收集了，重做基線（PM 第四節風險 6）。
- 結果寫進 `logs/iter16_compare.log`。

---

## 六、重算 `logs/iter16_recalc.py`（唯讀 SQL）

1. 6213、2466、4526 在 `stock_alerts` 的注意日期（對照第一節 1-2 的表）。
2. 逐日上市、上櫃注意筆數；上市逐日筆數 = 回補原始回應（`logs/iter16_backfill_raw.json`）用 `parse_twse_notice` 解析、扣掉不在 `stocks` 的代號後的逐日筆數。
3. `logs/iter16_alerts_before.json` vs 回補後：上櫃列、所有處置列逐值相同（以鍵比全部欄位）。
4. 所有有效處置的合併區間 = `latest.json` 的 `dsp`、`alerts.d` 的起迄。
5. `alerts.d` 檔數、`alerts.n` 檔數 = SQL 獨立計算；任抽 5 檔（上市、上櫃各 2 檔以上）的措施、原因和 `stocks/{代號}.json` 的 `alerts` 一致（原因比對 `_short` 之後的值）。

---

## 七、邊界情況

| 情況 | 行為 |
|---|---|
| 證交所網站封鎖（HTML） | `request` 丟錯 → 整批 `alerts` 不寫，記在 `errors["alerts"]`（同現有行為），其他資料集不受影響 |
| 回應 `stat` 不是 OK | 視為 0 筆 → 提醒一行；其他 4 個來源照常寫入 |
| 休市日（p3） | `stat: OK`、`data: []` → 30 天區間內仍有其他日子，通常不會 0 筆 |
| 權證、ETF、可轉債 | `is_valid_stock_code` 過濾 |
| 代號不在 `stocks` 表 | `MERGE` 的 `JOIN stocks` 自然略過（同現有） |
| 新來源與 OpenAPI 同一筆 | 去重，以後面的（OpenAPI）為準 |
| 同一檔兩段處置 | `dsp`、清單合併；措施、原因取最後公告的那段 |
| 清單全空 | `{"d": [], "n": []}`，三組都顯示「無」；`alerts` 鍵仍存在 |
| 舊的 `latest.json` 沒有 `alerts` | `alertBoard` 回傳空字串，總覽照舊（網站先更新、資料後更新時不報錯） |
| `S[代號]` 不存在（理論上不會） | 名稱顯示代號、市場顯示「上櫃」。`alerts` 只含 `stocks` 表的股票，而 `latest.stocks` 包含所有有日線的股票 |

---

## 八、QA 清單與 SQL

1. `git diff --stat`：`twstock/collectors/` 下只有 `alerts.py`；`twstock/` 另有 `export.py`、`__main__.py`。
2. 測試：`test_iter01`～`16` 全部通過；拿本輪前的程式跑 `test_iter16` 應失敗（反證）。
3. 回補驗收（PM F16-1 #1～#3、#6）：用第六節重算 ①～③。
4. `dsp`：8099 迄日 11/11；名稱旁「處」的提示寫「處置中（至 11/11）」。
5. 網站：
   - 總覽最下方三組；處置中 9 檔（以當時資料日 SQL 為準）。
   - 點代號進個股頁，返回鍵回到今日頁總覽。
   - 「注意顯示全部」切換。
   - 375 px 沒有水平捲動；預設卡高 ≤ 1.5 屏；深淺色可讀。
6. 至少 1 檔上市股票（例如 2360 致茂，11/06 在清單）名稱旁出現「注」；選股勾「排除注意股」後不在結果中。
7. 收集輸出格式：用 `test_iter16` 的假資料驗（QA 不跑 `collect`）。
8. `latest.json` 增加 ≤ 15 KB；匯出時間增加 ≤ 3 秒。

---

## 九、測試 `tests/test_iter16.py`（新檔，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_roc_date_dot` | `115.11.05`、`1151105`、`115/11/05`、空字串 |
| `test_parse_twse_notice` | 真實樣本 3 列（權證略過、HTML 標籤去掉、`﹝第十三款﹞` 保留）；`stat` 不是 OK → `[]`；非 dict、`data` 不是 list → `FetchError` |
| `test_fetch_twse_notice_range` | 查詢參數：11/09 → `20261010`～`20261109`、`response=json` |
| `test_fetch_alerts_market_and_dedup` | 5 個來源（模擬）→ `market` 正確、OpenAPI 佔位列不寫；輸出第一行文字逐字比對 |
| `test_alert_summary_zero_warning` | 上市 0 筆、上櫃 0 筆的提醒行 |
| `test_disposal_span` | 重疊、只有一段、處置中＋即將、沒有處置 |
| `test_alert_board` | 合併、排序、措施為 None、原因去前綴與裁短、空 dict |
| `test_site_source` | 原始碼字串：`alertBoard`、`App.alertAll`、預設 10 檔、說明句、三個組名、CSS 截斷、`export.py` 的兩處呼叫 |

- 不連網、不連資料庫；用 `fake_request` 暫時替換 `alerts.request`。專案沒有 pytest，寫法同 `test_iter15`（`python3 tests/test_iter16.py`）。
- 舊測試不改。

---

## 十、延後順序（沿用 PM）

1. 注意組的原因（先只列代號、名稱）：實作只差一個參數，**原型已完成，建議不延後**。
2. 0 筆提醒（`alert_summary` 第 2、3 行）。

不延後：新來源、回補、分市場輸出、F16-2、處置組。

---

## 十一、README 與 `__main__.py` 修改清單（全文見附錄 A）

- `README.md`：
  - 「處置／注意股取自…」一段句尾加第 16 輪：證交所網站來源、最近 30 天、每天 +1 請求、分市場輸出與提醒。
  - `site/` 一列句尾加第 16 輪：今日頁清單、`alerts` 鍵格式、合併區間。
- `twstock/__main__.py`：
  - `collect` 說明：處置／注意股後面加「（上市注意股查最近 30 天）」。
  - `export` 說明：加「處置／注意股清單」。
- `docs/iterations/README.md`：QA 結束後更新現有功能與測試清單（同第 15 輪的做法）。

---

## 十二、PG 實作與資料操作步驟

1. 記錄資料日、`collect_runs` 最大 `run_id`，並確認沒有進行中的收集（`finished_at` 為 NULL 的列）。
   - 把 `alerts.py`、`export.py`、`app.js`、`app.css` 複製到 `logs/iter16_before/`。
2. 基線 `export`，把 `site/data` 複製到 `logs/iter16_base/`。
   - 唯讀 SELECT `stock_alerts` 全表 → `logs/iter16_alerts_before.json`。
3. 套用附錄 A（`patch -p1 --dry-run` 後正式套用）；`node --check`；`test_iter01`～`16`。
4. **回補（一次，1 次請求）**：
   1. 寫一支腳本 `logs/iter16_backfill.py`，帶 `--write` 才寫入。
   2. 步驟：
      - `data = request(...)`，參數同 `fetch_twse_notice(date.today())`。
      - 原始回應存 `logs/iter16_backfill_raw.json`。
      - `rows = parse_twse_notice(data)`，印逐日筆數。
      - 只有帶 `--write` 時呼叫 `write_alerts(rows)`。
   3. 先不帶 `--write` 執行（dry-run），逐日筆數寫進 `04-dev.md`。**dry-run 讀已存的原始回應，不再發請求。**
   4. 確認 10/21～11/06 的逐日筆數和第一節 1-2 的表相同，再帶 `--write` 寫入一次。
   5. 只寫上市注意，**不呼叫 `collect_alerts`**，避免重寫上櫃與處置列。
   6. 唯讀 SELECT `stock_alerts` 全表 → `logs/iter16_alerts_after.json`。
5. 新程式 `export`（回補後）。
6. 比對兩次（第五節）、重算（第六節）。
7. 8001 預覽：375 px 與 1024 px，深淺色。結束後關閉 8001，恢復視窗大小。
- **允許的寫入**：`export`（基線、新程式各一次；回補前若要做第五節第 1 次比對，可多一次），以及第 4 步的回補一次。不執行 `collect`、`history`、`setup-db`、`backup`、還原。
- **請求**：只有第 4 步 1 次。

---

## 十三、測量摘要（SA 原型）

| 項目 | 結果 |
|---|---|
| 查證請求 | 3 次（上限 5） |
| 30 天區間大小 | 約 137 KB（p2，37 天 479 列） |
| `latest.json` | +5.4 KB（只有上櫃注意）／+8.9 KB（模擬補上市後） |
| 匯出耗時 | 23.7 秒 |
| 清單卡高度（375，預設） | 1,157 px（1.42 屏） |
| 測試 | `proj` 的 `test_iter01`～`16` 全過；`orig` 跑 `test_iter16` 失敗 |

---

## 十四、對 PM 範圍的調整建議（不改 `02-pm.md`）

1. **回補不做成專案指令**：
   - 平常收集每天查最近 30 天並 `MERGE`，本身就能補 30 天內漏收的日子。PM 要的「之後漏收也能補」已由每日收集涵蓋。
   - PG 的一次性回補改用 `logs/iter16_backfill.py`（約 25 行，不算進程式行數），只寫上市注意，滿足 PM F16-1 驗收 #6。
2. **保留 OpenAPI `notice`，每天 +1 次請求**（PM 寫「±0 或 +1」）：理由見第一節 1-3 第 1 點（不改舊測試）。
3. **回補的起日從 10/21 改為「今天 − 30 天」**（約 10/10）：
   - 和每日收集同一個函式，比只補 10/21 起多約 7 個交易日的上市注意。
   - 這些日子的上櫃資料不存在（上櫃從 10/21 起），只影響 B10-延伸b 的上市歷史，有益無害。
4. **「剩餘交易日」不顯示**（PM 交給 SA）：理由見第三節 3-2。
5. **延後順序第 1 項（注意組原因）建議取消**：原型已完成，延後反而要多寫分支。
6. **工作量**：程式＋README 約 112 行（PM 估 98、上限 140），測試 131 行。另有比對、重算、回補 3 支腳本約 150 行。

---

## 十五、給 PG、QA 的提醒

- 11/09（週一）起使用者每晚收集。新的 `alerts.py` 一旦套用，使用者當晚的收集就會寫入上市注意，並印新格式。
  - 這和 PG 的回補是同一個 `MERGE`，重複執行沒有副作用。
  - 但第五節第 2 次比對的「回補後」可能混入使用者收集的新資料日。每次匯出前後都要記 `collect_runs`。
- `test_iter06` 等舊測試的模擬網站沒有新來源，執行時輸出會多一行「⚠️ 上市注意股最近 30 天 0 筆」，屬預期，不是錯誤。
- 證交所網站 `www.twse.com.tw` 的間隔是 3.5 秒，限制比 OpenAPI 嚴。PG、QA 不要為了驗證反覆打這個網址；用 `logs/iter16_backfill_raw.json` 與 scratchpad 的 `p1.json`、`p2.json`。
- 本輪尚未 commit；是否 commit 由使用者決定。

---

## 附錄 A：完整 diff（`orig` → `proj`，含新測試檔）

```diff
--- a/twstock/collectors/alerts.py
+++ b/twstock/collectors/alerts.py
@@ -2,7 +2,7 @@
 處置股與注意股（證交所、櫃買 OpenAPI）。端點只提供最近的公告，每天收一次、保留歷史。
 """
 import re
-from datetime import date
+from datetime import date, timedelta
 
 from .. import db
 from ..fetch import FetchError, is_valid_stock_code, request
@@ -18,13 +18,18 @@
     ("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information", "notice",
      "SecuritiesCompanyCode", "Date", None, "TradingInformation", None),
 )
+# 第 16 輪：上市注意股另查證交所網站「公布注意交易資訊」（上面的 OpenAPI notice 第 1～15 輪實測都只回傳空白佔位列）。
+# 可指定日期區間，每天查最近 NOTICE_DAYS 天，漏收的日子會自動補上
+TWSE_NOTICE = ("https://www.twse.com.tw/rwd/zh/announcement/notice", "notice", "證券代號", "日期", None, "注意交易資訊", None)
+NOTICE_DAYS = 30
+_TAG = re.compile(r"<[^>]+>")
 _REASON = re.compile(r"處置原因：(.+?)。")
 _MATCHING = re.compile(r"約每[^，。；;()（）]{1,5}分鐘撮合一次")
 
 
 def roc_date(s):
-    """民國日期 1151029、115/10/29 或 115年10月29日 → date；空白或格式不符回傳 None。"""
-    s = str(s or "").strip().replace("年", "/").replace("月", "/").replace("日", "")
+    """民國日期 1151029、115/10/29、115.10.29 或 115年10月29日 → date；空白或格式不符回傳 None。"""
+    s = str(s or "").strip().replace("年", "/").replace("月", "/").replace("日", "").replace(".", "/")
     if "/" in s:
         parts = s.split("/")
     elif s.isdigit() and len(s) == 7:
@@ -49,7 +54,7 @@
     code, announce = str(row.get(code_f) or "").strip(), roc_date(row.get(date_f))
     if not is_valid_stock_code(code) or announce is None:
         return None
-    text = str(row.get(text_f) or "")
+    text = _TAG.sub("", str(row.get(text_f) or ""))
     item = {"stock_code": code, "alert_type": kind, "announce_date": announce.isoformat(),
             "start_date": None, "end_date": None, "reason": None, "measure": None}
     if kind == "notice":
@@ -67,20 +72,52 @@
     return item
 
 
+def parse_twse_notice(data) -> list:
+    """證交所網站注意股查詢回應（{stat, fields, data}）→ 寫入用 dict。
+    stat 不是 OK（例如「沒有符合條件的資料」）當作 0 筆，由 alert_summary 提醒；回應不是 dict 才丟 FetchError。"""
+    if not isinstance(data, dict) or not isinstance(data.get("data") or [], list):
+        raise FetchError("上市注意股回應格式不符")
+    if data.get("stat") != "OK":
+        return []
+    fields = data.get("fields") or []
+    return [a for a in (parse_alert(dict(zip(fields, r)), *TWSE_NOTICE[1:]) for r in data.get("data") or []) if a]
+
+
+def fetch_twse_notice(end: date, days: int = NOTICE_DAYS) -> list:
+    data = request("GET", TWSE_NOTICE[0], params={
+        "querytype": "1", "stockNo": "", "selectType": "", "proceType": "", "sortKind": "STKNO", "response": "json",
+        "startDate": f"{end - timedelta(days=days):%Y%m%d}", "endDate": f"{end:%Y%m%d}"})
+    return parse_twse_notice(data)
+
+
 def fetch_alerts() -> list:
-    rows = []
+    """5 個來源全部抓完才回傳；每筆加上 market 供輸出分市場。"""
+    rows = [dict(a, market="TWSE") for a in fetch_twse_notice(date.today())]
     for url, kind, *fields in _SOURCES:
         data = request("GET", url)
         if not isinstance(data, list):
             raise FetchError(f"處置／注意股回應格式不符：{url}")
-        rows += [a for a in (parse_alert(r, kind, *fields) for r in data) if a]
+        market = "TWSE" if "twse" in url else "TPEx"
+        rows += [dict(a, market=market) for a in (parse_alert(r, kind, *fields) for r in data) if a]
     # 同一檔同一天同類型只留一筆，避免 MERGE 同一列被更新兩次
     return list({(a["stock_code"], a["alert_type"], a["announce_date"]): a for a in rows}.values())
 
 
-def collect_alerts() -> int:
-    """4 個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
-    rows = fetch_alerts()
+def alert_summary(rows) -> list:
+    """收集輸出：分市場筆數；某個來源 0 筆時加一行提醒（只提醒，不算失敗）。"""
+    n = {(m, k): sum(a["market"] == m and a["alert_type"] == k for a in rows)
+         for m in ("TWSE", "TPEx") for k in ("disposal", "notice")}
+    out = [f"  🚨 處置 上市 {n['TWSE', 'disposal']}／上櫃 {n['TPEx', 'disposal']} 筆、"
+           f"注意 上市 {n['TWSE', 'notice']}／上櫃 {n['TPEx', 'notice']} 筆（未在股票清單的代號不寫入）"]
+    if n["TWSE", "notice"] == 0:
+        out.append(f"  ⚠️ 上市注意股最近 {NOTICE_DAYS} 天 0 筆，來源可能異常，請檢查")
+    if n["TPEx", "notice"] == 0:
+        out.append("  ⚠️ 上櫃注意股 0 筆：若今天是交易日，請留意來源是否異常")
+    return out
+
+
+def write_alerts(rows) -> None:
+    """MERGE 進 stock_alerts；只寫入 stocks 表已有的股票。"""
     if rows:
         conn = db.connect()
         try:
@@ -104,6 +141,11 @@
             conn.commit()
         finally:
             conn.close()
-    n = sum(a["alert_type"] == "disposal" for a in rows)
-    print(f"  🚨 處置 {n} 筆、注意 {len(rows) - n} 筆（未在股票清單的代號不寫入）")
+
+
+def collect_alerts() -> int:
+    """5 個來源全部抓完才寫入。"""
+    rows = fetch_alerts()
+    write_alerts(rows)
+    print("\n".join(alert_summary(rows)))
     return len(rows)
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -112,6 +112,33 @@
     return "notice" if announce == today else None
 
 
+def disposal_span(items):
+    """有效處置（可能多段重疊）→ [最早起日, 最晚迄日]；沒有處置回傳 None。第 16 輪 F16-2。"""
+    d = [a for a in items if a["t"] == "disposal"]
+    return [min(a["s"] for a in d), max(a["e"] for a in d)] if d else None
+
+
+def _short(text, n=60):
+    """原因只取第一句，超過 n 字裁短；完整原文在 stocks/{代號}.json 的 alerts。"""
+    t = str(text or "").split("。")[0].strip().removeprefix("該有價證券之交易，")
+    return t if len(t) <= n else t[:n] + "…"
+
+
+def alert_board(alerts):
+    """今日頁處置／注意清單（第 16 輪 F16-3）：d = [代號, 起, 迄, 措施, 原因]（依迄日、代號），
+    n = [代號, 原因]（依代號）。同一檔多段處置合併成一列，措施、原因取最後公告的那段。"""
+    d, n = [], []
+    for code, items in alerts.items():
+        span = disposal_span(items)
+        if span:
+            last = max((a for a in items if a["t"] == "disposal"), key=lambda a: a["a"])
+            d.append([code, *span, last["m"], _short(last["r"])])
+        notes = [a for a in items if a["t"] == "notice"]
+        if notes:
+            n.append([code, _short(notes[-1]["r"])])
+    return {"d": sorted(d, key=lambda x: (x[2], x[0])), "n": sorted(n)}
+
+
 def _price_events(d_, c, ch, market, official):
     """
     個股的價格調整事件（舊到新）：[{i, d, t, p, r}]。i = 生效的資料列索引（事件日當天或之後第一列），
@@ -1389,9 +1416,8 @@
             "l52": _f(min(x[1] for x in w52)) if w52 else None,
             # 個股第一筆日線晚於「全市場起點」與「52 週起點」兩者時，才另外標示高低點起算日
             **({"hf": str(d_[0])} if d_[0] > max(db_first, w52_start) else {}),
-            # 有效的處置 [起日, 迄日]（多筆取起日最早者）與資料日當天的注意股
-            **({"dsp": min([a["s"], a["e"]] for a in alerts[code] if a["t"] == "disposal")}
-               if any(a["t"] == "disposal" for a in alerts.get(code, [])) else {}),
+            # 有效的處置 [最早起日, 最晚迄日]（多段重疊時合併，第 16 輪 F16-2）與資料日當天的注意股
+            **({"dsp": disposal_span(alerts[code])} if disposal_span(alerts.get(code, [])) else {}),
             **({"ntc": 1} if any(a["t"] == "notice" for a in alerts.get(code, [])) else {}),
             **({"pe": _f(fund[code][0]), "pb": _f(fund[code][1]), "dy": _f(fund[code][2])}
                if code in fund else {}),
@@ -1468,6 +1494,7 @@
             "chain": group_flows(chains, daily, dates, REPLAY),
             "concept": group_flows(concepts, daily, dates, REPLAY),
         },
+        "alerts": alert_board(alerts),                          # 第 16 輪 F16-3：今日頁處置／注意清單
         "stocks": snapshot,
     }
     # screen.json 在 latest.json 之前寫：中途失敗時前端比對 d／fd 會顯示不同步
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -2,7 +2,7 @@
 台股資料收集與網站產生工具（Mac / Windows 通用）
 
   python -m twstock setup-db                         建立資料庫與資料表
-  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股、除權息事件、三大法人金額（上市、上櫃）；季報收集期間另收季報）並匯出網站資料
+  python -m twstock collect [--date 2026-10-28]      收集單日（全部重抓覆寫：行情、本益比、法人、月營收、指數、台指期、處置／注意股（上市注意股查最近 30 天）、除權息事件、三大法人金額（上市、上櫃）；季報收集期間另收季報）並匯出網站資料
   python -m twstock collect --catch-up [--days 10]   補齊最近 N 個交易日缺的資料（各資料集獨立判斷，可重複執行；季報收集期間每天收一次季報），有新資料才匯出；排程用這個
   python -m twstock check [--days 20]                檢查各資料集的完整性（唯讀、不連外）：開頭列最後一次收集與排程狀態，有異常時印建議指令並回傳 1
   python -m twstock history --start 2026-01-01       補抓歷史（行情、本益比、法人、ETF、融資融券；只補缺的，可中斷重跑）
@@ -16,7 +16,7 @@
   python -m twstock history --start 2024-01-01 --only financials  只補季報（季底日在範圍內的季別，每季上市、上櫃各 1 個請求；已有的季別自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
-  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/、etfp/；含季報、期現貨價差與下次結算日、營收與 EPS 基期、ETF 個股頁）
+  python -m twstock export                           從資料庫匯出網站 JSON（site/data：latest.json、screen.json、stocks/、etfs/、etfp/；含季報、期現貨價差與下次結算日、營收與 EPS 基期、ETF 個股頁、處置／注意股清單）
   python -m twstock serve                            本機預覽網站 http://localhost:8000
   python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
   python -m twstock chains                           更新產業鏈族群（櫃買產業價值鏈平台）
--- a/site/app.js
+++ b/site/app.js
@@ -164,7 +164,8 @@
       <a class="quads" href="#/bubble">
         ${QUADS.map(([q, d]) => `<div class="quad q-${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></div>`).join('')}
       </a>
-    </section>`,
+    </section>
+    ${alertBoard(L)}`,
     credit: `<section class="sec grid ${marginCard(L) && valCard(L) ? 'g2' : 'g-one'}">${marginCard(L)}${valCard(L)}</section>`,   // 信用交易、估值左右並排
     fut: fut.trim() || '<div class="empty">沒有期貨資料</div>',
   };
@@ -197,6 +198,7 @@
   if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
   $('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });
+  $('#alMore')?.addEventListener('click', () => { App.alertAll = !App.alertAll; renderToday(); });
   $('#view').addEventListener('click', onRowClick);
   if (tab === 'fut') { drawFutures(L.futures); drawOI(L.futures_oi); }
 }
@@ -310,6 +312,25 @@
       <div class="note-dup">${noteHTML('ETF 借券賣出多為造市、套利與避險，不等於看空', 'ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空')}</div>`;
 }
 
+// 第 16 輪 F16-3：處置／注意清單（即將處置、處置中、今日注意）；注意預設 10 檔
+function alertBoard(L) {
+  const A = L.alerts;
+  if (!A) return '';
+  // 每檔兩行：名稱、代號、市場、處置期間；措施與原因一行（超出截斷，完整內容在提示與個股頁）
+  const S = L.stocks, row = (c, span, r) => `<a class="al-row" href="#/stock/${c}" title="${esc(r)}">
+      <div class="al-l"><b>${esc(S[c]?.n || c)}</b><span class="muted small">${c}・${S[c]?.m === 'TWSE' ? '上市' : '上櫃'}</span><span class="sp"></span>${span ? `<span class="small num">${span}</span>` : ''}</div>
+      <div class="muted small al-r">${esc(r)}</div></a>`;
+  const dsp = x => row(x[0], `${md(x[1])}～${md(x[2])}`, [x[3], x[4]].filter(Boolean).join('｜'));
+  const up = A.d.filter(x => x[1] > L.date), on = A.d.filter(x => x[1] <= L.date);
+  const nShow = App.alertAll ? A.n.length : 10;
+  const grp = (t, list) => `<div class="al-grp"><h3>${t}　<span class="muted small">${list.length} 檔</span></h3>${list.join('') || '<div class="muted small">無</div>'}</div>`;
+  return `<section class="sec card">
+      <div class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}</span><span class="sp"></span>${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}</div>
+      ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])))}
+      <div class="muted small">依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因</div>
+    </section>`;
+}
+
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
 function breadthCard(L) {
   const B = L.breadth;
--- a/site/app.css
+++ b/site/app.css
@@ -212,6 +212,9 @@
 .al-d{background:var(--up)}.al-n{background:var(--amber)}
 .pill.al-d{background:var(--up-bg);border-color:var(--up);color:var(--up)}
 .pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
+.al-grp{margin-top:8px}.al-grp h3{font-size:13px;margin:0 0 4px}                 /* 第 16 輪 F16-3 */
+.al-row{display:block;padding:5px 0;border-top:1px solid var(--border);color:inherit;text-decoration:none}
+.al-l{display:flex;align-items:baseline;gap:6px}.al-l .sp{flex:1}.al-r{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .al-new{background:var(--blue)}                                  /* E2-4：新建倉 */
 .pill.hold{margin-left:6px;border-color:var(--blue);color:var(--blue)}
 .tbl .nm .pill{font-size:10px;margin-left:6px}
--- a/README.md
+++ b/README.md
@@ -17,7 +17,7 @@
 | `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
 | `twstock/export.py` | 匯出 `site/data/latest.json`、`screen.json`（條件選股與排行擴充用）、`stocks/{代號}.json`、`etfs/{代號}.json`、`etfp/{代號}.json`（第 15 輪 ETF 個股頁） |
 | `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
-| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延 |
+| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」。第 14 輪：營收年增排行只列欄名月份與更新的月份（表下列出未列入的檔數），去年同月營收不到 1,000 萬元的標「基期低」；單季 EPS 年增在去年同季 EPS 大於 0、小於 0.1 元時改顯示「基期低（去年同季 X 元）」；期貨卡加期現貨價差、下次結算日、換月標示與價差迷你圖；殖利率一年位置加方向說明；季報進度附申報截止日。第 15 輪：個股季報卡的累計 EPS 年增套用和單季相同的基期規則（去年同期 > 0 且 < 0.1 元顯示「基期低（去年同期 X 元）」，去年同期 ≤ 0 且本期 > 0 顯示「轉盈」）；ETF 可從搜尋、ETF 列表、`#/stock/{ETF 代號}` 進入 ETF 個股頁（原始價 K 線、量、融資融券與借券；見下方 ETF 一段）；期貨卡價差迷你圖的 0 軸加深；季報截止日加星期與週末順延。第 16 輪：今日頁「總覽」最下方加處置／注意股清單（即將處置、處置中、今日注意三組；`latest.json` 的 `alerts`：`d` = [代號, 起日, 迄日, 措施, 原因]、`n` = [代號, 原因]，原因只取第一句、最多 60 字，完整原因在個股頁），注意組預設 10 檔可按「注意顯示全部」；同一檔多段處置重疊時，`dsp` 與清單合併為 [最早起日, 最晚迄日] |
 | `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`、`python3 tests/test_iter08.py`、`python3 tests/test_iter09.py`、`python3 tests/test_iter10.py` |
 | `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
 | `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
@@ -134,7 +134,7 @@
 - 個股頁估值位置（第 9 輪，`stocks/{代號}.json` 的 `val`：`{d, pe|pb|dy: [位置 %, 一年最低, 一年最高]}`）：本益比、淨值比、殖利率指標卡加「一年位置 N%（最低～最高）」，窗口同上，只計入大於 0 的官方值（殖利率 0 = 不配息，不算位置）。今天值為空或 ≤ 0（虧損、無股利）、窗口內有效天數少於 120 天（新上市），或 90 天內股本變動（官方值可能尚未調整）時不顯示。估值說明（第 10 輪改寫）：本益比 = 股價 ÷ 近 4 季 EPS；獲利下降時本益比會升高，獲利大增時本益比（淨值比也可能）會落到一年低點（例如景氣循環股在獲利高峰），不代表股價便宜；有季報卡時加「請對照下方季報卡的近 4 季 EPS 與一年前比較」。淨值比卡也標「資料 MM/DD」（股本變動註記照舊只在本益比、殖利率卡）。第 12 輪：個股頁指標卡加「市值」（≥ 1 萬億顯示兆）與「週轉率」（`stocks/{代號}.json` 的 `mt`：`{d, mc 億元, to %}`，目前股數計算；沒有股數的股票沒有 `mt`，兩張卡顯示 `--`）。
 - 今日頁法人買超／賣超表與錢流標示「估算，不含 ETF」；三大法人卡的官方值含 ETF 與權證避險，兩者口徑不同。
 - 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
-- 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。
+- 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
 - 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。日線未滿一年時顯示「區間高／低」與起始日。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
--- a/tests/test_iter16.py
+++ b/tests/test_iter16.py
@@ -0,0 +1,131 @@
+"""第 16 輪（不連網、不連資料庫）：F16-1 上市注意股（證交所網站查詢）、分市場輸出與 0 筆提醒；
+F16-2 重疊處置合併區間；F16-3 今日頁處置／注意清單。"""
+import sys
+from contextlib import contextmanager
+from datetime import date
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
+def fake_request(fn):
+    """暫時換掉 alerts.request（不連網）。"""
+    old, alerts.request = alerts.request, fn
+    try:
+        yield
+    finally:
+        alerts.request = old
+
+
+FIELDS = ["編號", "證券代號", "證券名稱", "累計次數", "注意交易資訊", "日期", "收盤價", "本益比"]
+# 取自 2026-11-08 查詢 115/10/21～115/11/06 的真實回應（節錄）
+SAMPLE = {"stat": "OK", "fields": FIELDS, "total": 3, "data": [
+    [1, "040609", "川湖統一6A購01", "1", "最近六個營業日累積收盤價跌幅達36.06%﹝第一款﹞。", "115.11.04", "4.05", "-----"],
+    [73, "6213", "聯茂", "8", "最近六個營業日累積收盤價跌幅達33.02%。且六個營業日起迄兩個營業日收盤價價差達194.00元﹝第一款﹞。"
+     "11月04日之最近六個營業日之當日沖銷成交量占最近六個營業日總成交量比率66.17%<font color='#FF0000'>﹝第十三款﹞</font>。",
+     "115.11.05", "551.00", "85.43"],
+    [74, "2466", "冠西電", "6", "最近六個營業日累積收盤價漲幅達32.5%﹝第一款﹞。", "115.10.27", "60.10", "20.1"]]}
+
+
+def test_roc_date_dot():
+    assert alerts.roc_date("115.11.05") == date(2026, 11, 5)
+    assert alerts.roc_date("1151105") == date(2026, 11, 5) and alerts.roc_date("115/11/05") == date(2026, 11, 5)
+    assert alerts.roc_date("") is None
+
+
+def test_parse_twse_notice():
+    rows = alerts.parse_twse_notice(SAMPLE)
+    assert [(a["stock_code"], a["announce_date"]) for a in rows] == [("6213", "2026-11-05"), ("2466", "2026-10-27")]  # 權證略過
+    a = rows[0]
+    assert a["alert_type"] == "notice" and a["start_date"] is None and a["measure"] is None
+    assert "<font" not in a["reason"] and "﹝第十三款﹞" in a["reason"]
+    assert alerts.parse_twse_notice({"stat": "OK", "fields": FIELDS, "data": []}) == []   # 假日：stat OK、data 空
+    assert alerts.parse_twse_notice({"stat": "很抱歉，沒有符合條件的資料!"}) == []        # 當作 0 筆，由提醒處理
+    for bad in ([], None, "<html>", {"stat": "OK", "data": "x"}):
+        try:
+            alerts.parse_twse_notice(bad)
+            raise AssertionError(bad)
+        except FetchError:
+            pass
+
+
+def test_fetch_twse_notice_range():
+    seen = {}
+    with fake_request(lambda m, url, **kw: seen.update(url=url, **kw["params"]) or SAMPLE):
+        assert len(alerts.fetch_twse_notice(date(2026, 11, 9))) == 2
+    assert seen["url"] == alerts.TWSE_NOTICE[0]
+    assert (seen["startDate"], seen["endDate"], seen["response"]) == ("20261010", "20261109", "json")
+
+
+def test_fetch_alerts_market_and_dedup():
+    def fake(m, url, **kw):
+        if "params" in kw:
+            return SAMPLE
+        if "tpex_trading_warning" in url:
+            return [{"SecuritiesCompanyCode": "8099", "Date": "1151106", "TradingInformation": "第一款"}]
+        if url.endswith("/notice"):     # OpenAPI 上市注意：佔位列
+            return [{"Number": "0", "Code": "", "Name": "", "TradingInfoForAttention": "", "Date": ""}]
+        return []
+    with fake_request(fake):
+        rows = alerts.fetch_alerts()
+    assert sorted((a["market"], a["stock_code"]) for a in rows) == [("TPEx", "8099"), ("TWSE", "2466"), ("TWSE", "6213")]
+    out = alerts.alert_summary(rows)
+    assert out[0].strip() == "🚨 處置 上市 0／上櫃 0 筆、注意 上市 2／上櫃 1 筆（未在股票清單的代號不寫入）"
+    assert len(out) == 1
+
+
+def test_alert_summary_zero_warning():
+    out = alerts.alert_summary([{"market": "TPEx", "alert_type": "notice"}])
+    assert "注意 上市 0／上櫃 1" in out[0] and len(out) == 2 and "上市注意股最近 30 天 0 筆" in out[1]
+    out = alerts.alert_summary([])
+    assert len(out) == 3 and "上櫃注意股 0 筆" in out[2]
+
+
+def _d(a, s, e, m="約每2分鐘撮合一次", r="連續3個營業日"):
+    return {"t": "disposal", "a": a, "s": s, "e": e, "m": m, "r": r}
+
+
+def test_disposal_span():
+    two = [_d("2026-10-30", "2026-11-02", "2026-11-06"), _d("2026-11-04", "2026-11-05", "2026-11-11")]
+    assert export.disposal_span(two) == ["2026-11-02", "2026-11-11"]                       # 8099：重疊
+    assert export.disposal_span([_d("2026-11-04", "2026-11-05", "2026-11-11")]) == ["2026-11-05", "2026-11-11"]
+    up = [_d("2026-11-05", "2026-11-09", "2026-11-13"), _d("2026-10-30", "2026-11-02", "2026-11-06")]
+    assert export.disposal_span(up) == ["2026-11-02", "2026-11-13"]                        # 處置中＋即將：仍是處置中
+    assert export.disposal_span([{"t": "notice", "a": "2026-11-06"}]) is None and export.disposal_span([]) is None
+
+
+def test_alert_board():
+    al = {"8099": [_d("2026-10-30", "2026-11-02", "2026-11-06"), _d("2026-11-04", "2026-11-05", "2026-11-11", r="連續3日，且30日內曾處置。其他")],
+          "6213": [{"t": "notice", "a": "2026-11-06", "s": None, "e": None, "m": None, "r": "該有價證券之交易，" + "甲" * 70 + "。乙"}],
+          "2466": [_d("2026-11-03", "2026-11-04", "2026-11-10", m=None)],
+          "1569": [{"t": "notice", "a": "2026-11-06", "s": None, "e": None, "m": None, "r": "當沖比率"}]}
+    b = export.alert_board(al)
+    assert b["d"] == [["2466", "2026-11-04", "2026-11-10", None, "連續3個營業日"],
+                      ["8099", "2026-11-02", "2026-11-11", "約每2分鐘撮合一次", "連續3日，且30日內曾處置"]]
+    assert b["n"] == [["1569", "當沖比率"], ["6213", "甲" * 60 + "…"]]
+    assert export.alert_board({}) == {"d": [], "n": []}
+
+
+def test_site_source():
+    assert "function alertBoard(L)" in APP and "${alertBoard(L)}" in APP
+    assert "App.alertAll" in APP and "A.n.slice(0, nShow)" in APP and "nShow = App.alertAll ? A.n.length : 10" in APP
+    assert "依證交所、櫃買中心公告" in APP and "'即將處置'" in APP and "'處置中'" in APP and "'今日注意'" in APP
+    assert ".al-row" in CSS and "text-overflow:ellipsis" in CSS
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert '"dsp": disposal_span(alerts[code])' in src and '"alerts": alert_board(alerts)' in src
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
```
