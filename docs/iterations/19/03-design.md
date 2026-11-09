# 第 19 輪｜System Analyst：設計規格

- 依據：`19/01-analyst.md`、`19/02-pm.md`（F19-1、F19-2；使用者已決定 D28 = A；不急的確認 D28-1～4 照 PM 預設：PG 執行 `backup`／`setup-db`／回補、純現增標記「現增」、「權息」含現增標記不變、沒有現增的「權」圖例「除權（配股）」）。
- 作法（比照第 13～18 輪）：
  - 在 scratchpad `sa19/` 建立兩份專案副本：`orig` = 目前程式（第 18 輪，d810bdb）、`proj` = 本設計。兩份都**不含 `.env`**、`.git`、`logs`、`_archive`、`site/data`。
  - 資料來源與分類：用分析師留下的原始回應（`r19/raw/twt49u_2026.json`、`r19/raw/exdailyq_1y.json`、`q2421/`），**沒有再打外部請求**。
  - 唯讀查 DB：`price_events` 的列數、來源、日期範圍；`COL_LENGTH('price_events','div_ref')` 目前為 NULL（欄位不存在）。沒有印出或複製帳密。
  - 前端驗算：`sa19/a5_js.js` 用 node 執行 `proj/site/stock.js` 逐字取出的 `adjFactors`、`aggregate`、`barChange`、`evName`、`evMark`，在目前 `site/data/stocks/*.json`（11/09 匯出）上計算。
  - 預覽：8001 提供 `proj/site/`（資料是 `site/data` 的 scratchpad 複本，只對 2421、6669、8112、3189 手動加 `k`），375 寬看 2421 週 K（原始）。結束後已關閉 8001、清掉 `tw.kmode`、`tw.kadj`、恢復桌面大小；沒有碰 8000。
  - 測試與反證：`proj` 上 `test_iter01`～`19` 全部通過；`orig` 跑 `test_iter19` 失敗（`parse_events` 沒有 `div_ref`）。附錄 A 的 diff 已用 `patch -p1 --dry-run` 確認可乾淨套用到目前專案。
- 本文數字：分類來自原始回應（上市 2026/01～10、上櫃 2025/11～2026/10）；週／月 K 來自 11/09 的匯出（`collect_runs` 最大 `run_id` = 14）。
- **外部請求 0 次、資料庫寫入 0 次、沒有 DDL、沒有執行 `collect`／`history`／`export`**。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（diff） |
|---|---|---|---|
| F19-1 | `twstock/db.py` | `setup-db` 加一條 `IF COL_LENGTH(...) IS NULL ALTER TABLE price_events ADD div_ref` | ＋2 |
| F19-1 | `twstock/collectors/events.py` | `_SOURCES` 每個來源多第 7 項（減除股利參考價欄名或 `None`）；`parse_events` 選用欄位；MERGE 多一欄 | ＋16／−12 |
| F19-1 | `twstock/export.py` | `rights_kind()`；讀 `div_ref`；`_price_events` 帶 `k`；`ev` 輸出 `k`（有值才有） | ＋18／−8 |
| F19-1、F19-2 | `site/stock.js` | `evName`、`evMark`、`CASH_INC_TIP`；`barChange()`；標記、圖例第一欄、事件行、漲跌 `title`；股本變動註記；還原鈕說明 | ＋24／−11 |
| 文件 | `README.md` | `setup-db` 欄位清單、`events` 指令說明、個股價格段 | ＋3／−2 |
| 測試 | `tests/test_iter19.py`（新）＋ `tests/fixtures/twt49u_rights_mini.json`、`exdailyq_rights_mini.json`（新） | 7 個測試 | 165（fixture 125 行，約 29 KB） |

- 程式＋README **＋63／−33**，PM 估約 70、上限約 90。
- `__main__.py` **不用改**（`events --start` 既有，見第四節）。
- 建議實作順序見第九節。

---

## 一、資料來源與欄位

### 1-1 證交所 `TWT49U`（除權除息計算結果表）

- 端點：`GET https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate=YYYYMMDD&endDate=YYYYMMDD&response=json`（每晚本來就抓）。
- 回應 `fields`（15 欄，2421 2026/02/24 實例）：

| 索引 | 欄名 | 2421 2026/02/24 |
|---|---|---|
| 0 | 資料日期 | 115年02月24日 |
| 1 | 股票代號 | 2421 |
| 3 | 除權息前收盤價 | 147.00 |
| 4 | 除權息參考價 | 145.96 |
| 6 | 權/息 | 權 |
| 9 | 開盤競價基準 | 147.00 |
| **10** | **減除股利參考價** | **147.00** |

- **取值位置：以欄名「減除股利參考價」在 `fields` 中找索引**（目前是第 10 欄），不寫死索引。值是字串、2 位小數、可能有千分位（「2,614.99」），用既有的 `clean_number` 解析。
- 官方公式（回應的 `formula`）：
  - 除權息參考價 = (前收 − 息值 + 現增認購價 × 現增配股率) ÷ (1 + 無償配股率 + 現增配股率)
  - **減除股利參考價 = (前收 − 息值) ÷ (1 + 無償配股率)**：只扣股利，不含現增。
- 2026/01～10 的 927 列一般股票：每一列都有值、都是 2 位小數。

### 1-2 櫃買 `bulletin/exDailyQ`（除權除息計算結果表）

- 端點：`POST https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ`（每晚本來就抓），`tables` 中含「代號」欄的那一張表。
- **欄名同樣是「減除股利參考價」**（第 12 欄）。同一張表另有「現金股利」「每仟股無償配股」「現金增資股數」「現金增資認購價」等明細，**本輪不存**，只拿來當測試真值。
- 1 年 713 列一般股票：每一列都有值、都是 2 位小數。

### 1-3 減資 `TWTAUU`、面額變更 `TWTB8U`

- 沒有這一欄，`div_ref` 存 NULL。

### 1-4 解析（`events.py`）

- `_SOURCES` 每個來源多第 7 項：`TWT49U`、`TPEX_EX` 為 `"減除股利參考價"`，`TWTAUU`、`TWTB8U` 為 `None`。
- `parse_events`：
  - 必要欄位（原本 5 個）的判斷**不變**：缺了照舊回傳 `[]`。
  - 「減除股利參考價」是**選用欄位**：`fields` 找不到、該列比欄位短、值無法解析（`--`、空白）或為 0 → 該筆**不帶 `div_ref` 鍵**，其他欄位照常寫入，不拋例外。
  - 有值時 dict 多 `"div_ref": 147.0`。沒有值時**不放這個鍵**（而不是放 `None`），理由：`test_iter02` 用完整 dict 比對舊格式，不放鍵就不用改舊測試；`OPENJSON ... WITH (div_ref DECIMAL(10,2))` 對缺少的屬性回傳 NULL，寫入結果相同。

---

## 二、分類規則與邊界（F19-1）

### 2-1 規則 `export.rights_kind(t, p, r, dr)`

| 條件（依序判斷） | 回傳 | 意義 |
|---|---|---|
| `t` 不是「權」「權息」 | `None` | 息、減、面、調都不分類 |
| `dr` 為 NULL 或 0 | `None` | 舊資料、欄位缺失 |
| `|r − p| < 0.005`（參考價 = 前收） | `None` | 無法分辨 |
| `dr > p + 0.005`（高於前收） | `None` | 資料異常（公式上 `dr ≤ p`） |
| `|dr − r| < 0.005` | `"s"` | 沒有現增（配股；「權息」為配股＋配息） |
| `|dr − p| < 0.005` | `"c"` | 只有現增（沒有股利） |
| 其他 | `"sc"` | 股利＋現增 |

- **容差 0.005 元**：三個值在官方與資料庫都是 2 位小數（`DECIMAL(10,2)`），差值是 0.01 的倍數，0.005 等於「相等」，同時吸收浮點誤差；高價股（6669 的 7,800）和低價股一樣適用。原始回應中 1,640 列沒有任何一列落在 0.005～0.02 之間（`sa19/a1_edges.txt`），不會因容差誤判。
- 先判斷 `s` 再判斷 `c`：兩者同時成立只會在 `r = p`，已在前一步排除。
- `"sc"` 不要求 `dr` 介於 `r`、`p` 之間：認購價高於市價時參考價可能高於 `dr`，但仍是「股利＋現增」。

### 2-2 驗證（`sa19/a6_kind.py`，原型的 `parse_events` ＋ `rights_kind`）

| 來源 | 類型 | `s` | `c` | `sc` | 合計 |
|---|---|---|---|---|---|
| 上市 `TWT49U`（2026/01～10） | 權 | 18 | **40** | 0 | 58 |
| | 權息 | 53 | 0 | 6 | 59 |
| 上櫃 `TPEX_EX`（2025/11～2026/10） | 權 | 17 | **47** | 0 | 64 |
| | 權息 | 43 | 0 | 5 | 48 |
| 合計 | | 131 | **87** | 11 | 229 |

- 和分析師的表**完全相同**。「息」1,411 列全部 `None`。
- **櫃買真值**：以「現金增資股數 > 0」「每仟股無償配股 > 0」「現金股利 > 0」推出預期（只有現增 → `c`；有現增且有股利 → `sc`；沒有現增 → `s`），**112／112 一致**。
- 驗收樣本：

| 股票 | 事件 | 前收 → 參考價 | 減除股利參考價 | `k` |
|---|---|---|---|---|
| 2421 建準 | 2026/02/24 權 | 147.00 → 145.96 | 147.00 | `c` |
| 3189 景碩 | 2026/01/26 權 | 214.00 → 204.83 | 214.00 | `c` |
| 6669 緯穎 | 2026/09/02 權 | 7,800.00 → 2,614.99 | 2,614.99 | `s` |
| 8112 至上 | 2026/07/06 權息 | 92.90 → 87.53 | 89.09 | `sc` |
| 5284、7610、1529、2464、2614 | 上市 權息 | — | 介於中間 | `sc` |
| 2421 建準 | 2026/06/10 息 | 160.00 → 154.75 | 154.75 | 不輸出 |

### 2-3 各類事件的處理

| 事件 | `div_ref` | `k` | 畫面 |
|---|---|---|---|
| 權息（除權除息） | 有值 | `s`／`sc`（理論上可能 `c`） | `s`：照舊；`c`／`sc`：圖例「除權息（含現金增資）」 |
| 權（只有除權） | 有值 | `s`／`c`／`sc` | 見第六節 |
| 息 | 有值（= 參考價） | 不輸出 | 照舊 |
| 減資 `TWTAUU`、面額變更 `TWTB8U` | NULL | 不輸出 | 照舊 |
| 上櫃反推「調」 | 沒有（不存表） | 不輸出 | 照舊 |
| 欄位缺失、回補前的舊資料 | NULL | 不輸出 | 「除權」「除權息」照舊 |
| 同一資料列有兩筆官方事件 | — | 只帶被採用那一筆的 `k` | `_price_events` 原本就只採一筆（`_SRC_RANK`） |

---

## 三、DDL 與 setup-db

- `twstock/db.py` 的建表清單，在第 11 輪 `stocks.shares` 那一條之後加：

```sql
IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE price_events ADD div_ref DECIMAL(10,2) NULL
```

- 型別和 `prev_close`、`ref_price` 相同；可為 NULL、沒有預設值，既有列加欄後都是 NULL。
- **可重複執行**：欄位已存在時 `COL_LENGTH` 不是 NULL，什麼都不做。
- `CREATE TABLE price_events` 本身**不改**：新資料庫先建表、再由這一條加欄，結果相同（比照第 11 輪）。
- MERGE（`collect_events`）：
  - `OPENJSON ... WITH` 多 `div_ref DECIMAL(10,2)`。
  - `WHEN MATCHED`：多 `div_ref = COALESCE(s.div_ref, t.div_ref)`。官方欄名暫時找不到時，不清掉已存的值；`prev_close`、`ref_price`、`event_type` 的更新方式不變。
  - `WHEN NOT MATCHED`：`INSERT` 多 `div_ref`。
- **注意**：新程式的 `export` 會 `SELECT e.div_ref`，`collect_events` 會寫 `div_ref`。套用程式後到 `setup-db` 之前，`export`、事件收集都會失敗（事件收集有 `_guard` 隔離，`export` 沒有）。所以 PG 要**改完程式立刻 `setup-db`**，中間不要讓使用者收集（第九節）；README 的「新增資料表請再執行 `setup-db`」清單加上這一欄。

---

## 四、回補指令

- 查 `twstock/__main__.py`：
  - 第 18 行說明、第 110 行 `cmd_events`、第 214～217 行 `sub.add_parser("events")`：`--start`（必填）、`--end`（預設今天）。
  - `cmd_events` 呼叫 `collect_events(start, end)`；`FetchError` 時印「稍後用同樣的指令重跑即可（MERGE 覆寫，不會重複）」並回傳 1。
  - **不需要新指令，也不需要改 `__main__.py`**。
- 指令：

```bash
python3 -m twstock events --start 2025-10-30
```

- 起日 2025-10-30：資料庫 `price_events` 最早事件日就是 2025-10-30（1,699 筆，最新 11/06），和日線起日相同。
- **請求數 = 段數 × 4 個端點**。`CHUNK_DAYS = 183`：
  - 第 1 段 2025-10-30～2026-04-30；第 2 段 2026-05-01～2026-10-30；第 3 段 2026-10-31～執行當天。
  - 執行日在 2027-04-30 前都是 3 段，**共 12 次**（`TWT49U`、`TWTAUU`、`TWTB8U`、`exDailyQ` 各 3 次）。
  - 全部經過 `fetch.request`（有節流）。中途失敗時整批不寫入（`collect_events` 四個端點全部抓完才寫），重跑一次，總計 ≤ 24 次。
- 回補後預期：
  - `TWT49U`、`TPEX_EX` 來源的「權」「權息」`div_ref` 非 NULL 比例 ≈ 100%（只要官方回應有這筆）；`TWTAUU`、`TWTB8U` 全部 NULL。
  - 列數：MERGE 只新增資料庫沒有的事件；回補到執行日時，若 11/07 之後有新事件，會多幾列（逐筆記錄）。
  - **既有欄位可能被官方修正值覆寫**（PM 風險 2）：用 SQL 比對逐筆記錄，不自行還原。
- 每晚的 `collect --catch-up`：事件本來就每晚往回查 7 天，新欄位**日常請求 0 次新增**。

---

## 五、匯出 JSON 的欄位變更

| 檔案 | 鍵 | 變更 |
|---|---|---|
| `stocks/{代號}.json` | `ev[].k` | **新增**：只在「權」「權息」且 `rights_kind` 有值時出現，值為 `"s"`、`"c"`、`"sc"` |
| `stocks/{代號}.json` | `ev[]` 的 `d`、`t`、`p`、`r` | 不變（含順序） |
| `stocks/{代號}.json` | `capchg` | 不變（不加 `k`；前端用 `ev` 查） |
| `latest.json`、`screen.json`、`etfp/*.json`、其他 | — | **逐值不變**（`k` 不進還原係數、漲跌、選股） |

- 輸出：`{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e}`。`_price_events` 內部的 dict 只在有分類時才帶 `k`，所以沒有分類的事件輸出和改版前逐字相同。
- 規模：11/09 的「權」134、「權息」110，回補後約 230 筆多 `"k":"…"`（約 8 字元），總計增加約 2 KB，匯出時間不受影響（多讀一欄）。

---

## 六、前端畫面（`site/stock.js`）

### 6-1 文字對照

新增兩個函式（放在 `EV_LABEL` 下方）：

```js
const evName = e => e.t === '權' && e.k ? `除權（${{ s: '配股', c: '現金增資', sc: '配股＋現金增資' }[e.k]}）`
  : e.t === '權息' && /c/.test(e.k || '') ? '除權息（含現金增資）' : EV_LABEL[e.t];
const evMark = e => e.t === '權' && e.k === 'c' ? '現增' : e.t;
const CASH_INC_TIP = '現金增資除權：股東可依持股比例出錢認購新股（不是無償配股），參考價依認購價計算';
```

| `t` | `k` | 圖例（`evName`） | 標記（`evMark`） | 事件行 `title` |
|---|---|---|---|---|
| 權 | `s` | 除權（配股） | 權 | — |
| 權 | `c` | **除權（現金增資）** | **現增** | `CASH_INC_TIP` |
| 權 | `sc` | 除權（配股＋現金增資） | 權 | `CASH_INC_TIP` |
| 權息 | `s` | 除權息 | 權息 | — |
| 權息 | `c`／`sc` | **除權息（含現金增資）** | 權息 | `CASH_INC_TIP` |
| 權、權息 | 沒有 | 除權／除權息（照舊） | 權／權息 | — |
| 息、減、面、調 | — | 照舊 | 照舊 | 「調」照舊 |

- 「權 + `sc`」在目前資料 0 筆，但公式上可能（配股＋現增、沒有配息），所以給文字。
- 說明文字只描述「現金增資是什麼、參考價怎麼算」，沒有「建議」「應認購」「稀釋」等字（測試檢查）。

### 6-2 `EV_LABEL` 的四個使用處

| 位置（目前行號） | 用途 | 改法 |
|---|---|---|
| 第 47 行 `capSub` | 本益比、殖利率卡的股本變動註記 | 改用 `evName`：以 `cap.d` 在 `data.ev` 找到同一筆，帶到 `k`（例：「1/26 除權（現金增資），官方值可能尚未調整」）；找不到時用 `cap`（照舊） |
| 第 337 行 K 線標記 | 圖上文字 | 改用 `evMark`（＋週／月加日期，6-3） |
| 第 378 行 融資融券圖的換算標記 | 「除權 已換算」 | **不改**：這是官方融資餘額換算紀錄（`mg.k`），沒有 `k`；現增也會換算股數，寫「除權」不算錯 |
| 第 433 行 圖例事件行 | 「除權　前收…」 | 改用 `evName`；`k` 含 `c` 時加 `title="${CASH_INC_TIP}"` |

- 還原鈕（`#adjSeg` 的 `title`，第 178 行）：「還原：依除權息、減資、面額變更調整歷史價格**（現金增資除權也依官方參考價調整）**，最新收盤不變。…」

### 6-3 週／月 K 的標記文字與日期（F19-2）

- 標記（`buildCharts`，第 336 行）：

```js
const mdn = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;
... text: [...new Set(r.ev.map(e => (mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)))].join('・')
```

- 日 K：「權」「現增」「息」（不加日期，和改版前相同；「現增」除外）。
- 週／月 K：「2/24 現增」「9/2 權」；同一根多筆用「・」合併，例：4155 週 K 2026-10-19「10/19 減・10/20 息」、6186 月 K 2026-08「8/6 息・8/26 權」。
- **日期是 `ev[].d`**，也就是事件生效的資料列日期（官方事件日當天或之後第一個交易日），和日 K 標記位置、圖例事件行一致。官方事件日是休市日時，寫的是生效日。
- 月 K 不縮寫：每檔一年只有 1～3 筆事件，月 K 一年 12 根，不會擠；375 寬實測 2421 週 K「2/24 現增」「6/10 息」可讀、`scrollWidth` = 375。

### 6-4 圖例第一欄：「當週」「月」

```js
`<span><b>${mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]}</b></span>`
```

- 週 K：「2026-02-23 當週」（`T[i]` 是該週星期一）。
- 月 K：「2026-02 月」（原本是「2026-02-01」，看起來像 2/1 的事件）。
- 日 K：照舊「2026-02-24」。
- 事件行照舊在週／月寫 `MM/DD`（「02/24 除權（現金增資）　前收 147　參考價 145.96」）。

### 6-5 原始價週／月 K 的漲跌（Q19-3）

把漲跌計算抽成頂層函式 `barChange(raw, i, mode, adj)`（方便測試），回傳 `[漲跌, 漲跌幅 %, 係數 f]`：

| 情況 | 漲跌 | 漲跌幅 |
|---|---|---|
| 日 K | `raw[i].ch`（匯出的官方口徑，照舊） | `raw[i].pc`（照舊） |
| 週／月 K 且 `gx`（ETF 推測調整） | `null` → 「不比價」（照舊） | — |
| 週／月 K 第一根 | 0（照舊） | 0 |
| 週／月 K、**還原** | `C[i] − C[i−1]`（`f = 1`，照舊） | `÷ C[i−1]` |
| 週／月 K、**原始** | `C[i] − C[i−1] × f`，`f = Π（r ÷ p）`（該根所有 `ev`） | `÷ (C[i−1] × f)` |

- **漲跌幅和還原價完全相同**：還原係數 `F` 的定義是「之後所有事件比值的乘積」，相鄰兩根的 `F[i−1] ÷ F[i]` 正好是本根事件比值的乘積。全市場 129,192 根週／月 K（其中 3,442 根含事件）逐根比對，**原始（新）與還原的漲跌幅 0 根不同**（`sa19/a4_invariant.txt`、`a5_js.txt`）；沒有事件的 125,750 根原始價漲跌和改版前逐值相同。
- 「調」（上櫃反推）一樣套用：`ev` 有 `p`、`r`，和還原價用的是同一組值。
- 漲跌那一格在 `f ≠ 1` 時加 `title="期間含除權息等事件：前一根收盤先乘上參考價 ÷ 前收再相減"`。
- 不用升降單位取整（日 K 的 `_tick_round`）：週／月 K 要和還原價的漲跌幅一致，取整會造成兩種模式差幾個基點。
- **6669、2421、6949、8422 實際數值驗算**（11/09 匯出、`sa19/a3_bars.txt` 與 `a5_js.txt` 兩套獨立計算相同）：

| 股票 | K 棒（原始） | 前一根收 | 本根收 | 事件 | f | 改版前 | **改版後** | 還原的漲跌幅 |
|---|---|---|---|---|---|---|---|---|
| 6669 | 週 2026-08-31 當週 | 7,200 | 2,565 | 9/2 權 7,800 → 2,614.99 | 0.335255 | −4,635（−64.38%） | **+151.16（+6.26%）** | +6.26% |
| 6669 | 月 2026-09 | 7,095 | 2,090 | 同上 | 0.335255 | −5,005（−70.54%） | **−288.64（−12.13%）** | −12.13% |
| 2421 | 週 2026-02-23 當週 | 144.5 | 152.5 | 2/24 權（現增）147 → 145.96 | 0.992925 | +8.00（+5.54%） | **+9.02（+6.29%）** | +6.29% |
| 2421 | 週 2026-06-08 當週 | 161.5 | 144.0 | 6/10 息 160 → 154.75 | 0.967187 | −17.50（−10.84%） | **−12.20（−7.81%）** | −7.81% |
| 2421 | 月 2026-06 | 159.0 | 142.0 | 同上 | 0.967187 | −17.00（−10.69%） | **−11.78（−7.66%）** | −7.66% |
| 6949 | 週 2026-09-07 當週 | 1,490 | 53.0 | 9/7 面 1,490 → 74.5 | 0.05 | −1,437（−96.44%） | **−21.50（−28.86%）** | −28.86% |
| 6949 | 月 2026-09 | 1,490 | 50.6 | 同上 | 0.05 | −1,439.4（−96.60%） | **−23.90（−32.08%）** | −32.08% |
| 8422 | 週 2025-11-17 當週 | 250 | 22.2 | 11/17 面 250 → 25 | 0.1 | −227.8（−91.12%） | **−2.80（−11.20%）** | −11.20% |
| 8422 | 月 2025-11 | 241.5 | 24.5 | 同上 | 0.1 | −217（−89.86%） | **+0.35（+1.45%）** | +1.45% |
| 4155（多事件） | 週 2026-10-19 當週 | 14.2 | 16.8 | 10/19 減 14.2 → 14.68、10/20 息 16.1 → 15.8 | 1.014539 | +2.60（+18.31%） | **+2.39（+16.61%）** | +16.61% |
| 6186（多事件） | 月 2026-08 | 41.65 | 32.0 | 8/6 息 42.45 → 37.44、8/26 權 33.65 → 32.92 | 0.862845 | −9.65（−23.17%） | **−3.94（−10.96%）** | −10.96% |

- 6949 2026-09 月 K：9/1～9/4 停止買賣（一字線），前一根是 8 月收盤 1,490；事件在 9/7 恢復買賣，比值 0.05 套在 9 月那一根。
- 6669 的 −12.13%（月）、6949 的 −28.86%（週）是真實的價格變化（除權後股價下跌），不是假跌。
- 6669 2026-08-31 當週為什麼和事件的前收不同：前一根（8/28 收）7,200，事件前收是 9/1 收 7,800；公式用比值，所以 9/1 的漲幅也算在本根，正確。

---

## 七、邊界情況

| 情況 | 行為 |
|---|---|
| 官方改欄名、少了「減除股利參考價」 | `parse_events` 照常回傳事件，不帶 `div_ref`；MERGE 不清掉已存的值；畫面退回「除權」 |
| 值為 `--`、空白、0、列太短 | 同上 |
| 必要欄位（日期、代號、前收、參考價、權/息）缺 | 照舊回傳 `[]`（不變） |
| 回補前的舊資料（`div_ref` NULL） | 不輸出 `k`，畫面照舊 |
| `setup-db` 前跑新程式 | `export` 失敗（`div_ref` 不存在）；事件收集失敗但由 `_guard` 隔離。PG 改完程式立刻 `setup-db`（第三、九節） |
| 新程式寫入、使用者執行舊程式 | 舊程式不讀 `div_ref`，不受影響 |
| 參考價 = 前收的「權」 | 不分類 |
| `dr` 高於前收 | 不分類（資料異常） |
| 現增認購價剛好等於減除股利參考價 | 參考價 = `dr`，判為 `s`（無法從這一欄分辨；公式限制，機率極低） |
| 「權息」只有配息＋現增（沒有配股） | `sc`，圖例「除權息（含現金增資）」，不寫「配股」（上櫃 5 筆都是這種） |
| 同一資料列兩筆官方事件 | 照舊只採一筆（`_SRC_RANK`），`k` 跟著那一筆 |
| 週／月 K 含多筆事件 | 標記「・」合併、每筆寫日期；漲跌的比值相乘 |
| 週／月 K 第一根含事件 | 漲跌 0（照舊，沒有前一根） |
| 前一根是一字線（整週停止買賣，例 6949 9/1～9/4） | 一字線收盤 = 停止前收盤；本根的比值照常套用 |
| 事件落在無成交日（3531 6/9、2947 3/26、2949 7/30） | `ev` 照舊掛在該列，同一根之後有成交，比值算在同一根；目前資料沒有「事件在整根無成交的那一根」的情況。若將來出現，那一根顯示一字線、下一根的漲跌少乘一個比值（和還原的漲跌幅會不同）；QA 的全市場比對會抓到 |
| ETF 頁 | 沒有 `ev`，`f = 1`；`gx` 照舊「不比價」 |
| 還原模式 | `f = 1`，漲跌逐值不變 |
| 原始價的 MACD／KD／RSI、均線 | 不在範圍內，照舊用原始收盤（跨事件會跳），README 已寫技術面以還原價為準 |
| 舊的 `stocks/*.json`（沒有 `k`） | 畫面照舊；網站先更新、資料後更新也不報錯 |

---

## 八、測試案例

### 8-1 `tests/test_iter19.py`（新檔，全文見附錄 A；不連網、不連資料庫）

| 測試 | 驗什麼 | 對應 PM 驗收 |
|---|---|---|
| `test_parse_div_ref` | fixture 的 2421、6669、8112 取到 `div_ref`；櫃買 114 筆都有；欄名改掉時事件數不變且沒有 `div_ref`；`--`、空白、0、列太短；`TWTAUU`、`TWTB8U` 不分類；MERGE 有新欄與 `COALESCE` | F19-1 #3、#7 |
| `test_rights_kind` | 2421、3189 → `c`；6669 → `s`；8112、2614 → `sc`；息、NULL、參考價 = 前收、`dr` 高於前收 → `None`；容差邊界 | F19-1 #3 |
| `test_tpex_truth` | 櫃買 112 筆以明細欄位為真值，112／112 | F19-1 #5 |
| `test_price_events_k` | `_price_events` 帶 `k`；沒有分類時 dict 和改版前相同；匯出讀 `div_ref`、輸出 `k` | F19-1 #8 |
| `test_setup_db` | `COL_LENGTH` 判斷後才 `ALTER`（可重複執行） | F19-1 #1 |
| `test_js_bar_change_and_labels` | node 執行 `stock.js` 逐字取出的 `adjFactors`、`aggregate`、`barChange`、`evName`、`evMark`：單一事件（原始 +5／+10%，不是 −45）、還原的漲跌幅相同、月 K、日 K 不變、`gx` 不比價、第一根 0、多事件比值相乘；8 種文字、4 種標記（沒有 node 時略過） | F19-2 #9、F19-1 #6 |
| `test_stock_page_source` | 用 `barChange`、舊公式已移除；圖例「當週」「月」；週／月標記加日期、日 K 不加；事件行用 `evName`、有 `CASH_INC_TIP`；股本變動註記；還原鈕說明；說明文字沒有建議性字眼 | F19-2 #1～#3、共通規則 7 |

- fixture（從分析師原始回應精簡，欄位不變）：
  - `tests/fixtures/twt49u_rights_mini.json`：2421（2/24 權、6/10 息）、3189、6669、8112、2614，6 列。
  - `tests/fixtures/exdailyq_rights_mini.json`：1 年內一般股票全部「除權」「除權息」112 列＋「除息」2 列＋ETF 00950B 1 列。
  - 產生腳本：scratchpad `sa19/a7_fixtures.py`；成品在 `sa19/proj/tests/fixtures/`，PG 直接複製即可。

### 8-2 比對腳本：需要（比照第 14～18 輪的 base／compare）

本輪動到收集器與資料表，PM 已要求三支腳本，SA 定內容：

1. **`logs/iter19_compare.py`**（由 `iter18_compare.py` 改）：比較 `logs/iter19_base/`（舊程式、回補前）與新程式匯出。
   - `stocks/*.json`：剔除 `ev[].k` 後逐值相同；`k` 只出現在 `t` 為「權」「權息」的事件、值只有 `s`／`c`／`sc`。
   - `latest.json`（除 `updated_at`、`status`）、`screen.json`、`etfp/*.json`、其他檔：完全相同。
   - `--keep-new` 反證：不剔除 `k` 時應判定不同。
   - **注意**：回補可能新增 11/07 之後的事件或官方修正既有值，會讓 `ev`、`prices.ch`、還原相關值不同。比對時若有差異，對照 `iter19_dbcheck.py` 的列數變化逐筆說明；沒有變化時應完全相同。
2. **`logs/iter19_dbcheck.py`**（唯讀 SQL）：
   - 讀 `logs/iter19_before/price_events.json`（加欄前匯出的全表：`stock_id, event_date, event_type, prev_close, ref_price, source`），和目前的表逐列比對：列數、既有欄位逐值相同；新增或改變的列逐筆列出。
   - `setup-db` 後（回補前）：`div_ref` 全部 NULL、列數不變。
   - 回補後：各 `source` × `event_type` 的 `div_ref` 非 NULL 比例（`TWT49U`、`TPEX_EX` 的權、權息 ≥ 95%，缺的逐筆列出；`TWTAUU`、`TWTB8U` 為 0%）。
3. **`logs/iter19_recalc.py`**（**不 import `export`**，自己寫分類與週／月聚合）：
   - 唯讀 SQL 讀 `price_events`（含 `div_ref`），重算全部「權」「權息」的分類，和 `stocks/*.json` 的 `ev[].k` 逐筆相同；三類筆數（預期 `c` ≥ 87、`sc` ≥ 11、合計約 240，差異逐筆說明）。
   - 第 2-2 節樣本表的 `k`。
   - 第 6-5 節表格每一列的原始價漲跌與漲跌幅（小數 2 位）；全市場週／月 K「原始（新）＝還原」漲跌幅（0 根不同，作法同 `sa19/a4_invariant.py`）。
- 另外 PG 執行 node 驗算（`sa19/a5_js.js` 放到 `logs/iter19_js.js`），用新程式的 `stock.js` 在新匯出上算第 6-5 節的表與全市場比對。

---

## 九、PG 實作順序

固定順序（沿用 PM 第一節，補上 SA 的細節）：

1. **`python3 -m twstock backup`**：記錄時間、檔名、大小（早於任何程式修改）。
2. 記錄資料日、`collect_runs` 最大 `run_id`、確認沒有進行中的收集；`price_events` 列數與各 `source`、`event_type` 筆數；匯出 `price_events` 全表到 `logs/iter19_before/price_events.json`；複製 `events.py`、`db.py`、`export.py`、`stock.js` 到 `logs/iter19_before/`。
3. 基線 `export`（舊程式、舊資料）→ `logs/iter19_base/`。
4. 先放測試：`tests/test_iter19.py` 與兩個 fixture；確認舊程式跑 `test_iter19` 失敗。
5. 套用附錄 A（`patch -p1 --dry-run` 後正式套用）；`node --check site/stock.js`；`test_iter01`～`19` 全部通過。
6. **立刻 `python3 -m twstock setup-db` 兩次**（第二次不報錯）；`iter19_dbcheck.py`：只多一欄、全部 NULL、列數與既有欄位不變。
7. **回補 `python3 -m twstock events --start 2025-10-30`**：12 次請求（失敗重跑一次，≤ 24）；記錄輸出的筆數與實際請求數；`iter19_dbcheck.py`。
8. 新程式 `export`（記錄耗時）；`iter19_compare.py`、`iter19_recalc.py`、`iter19_js.js`。
9. 8001 預覽（375、1024，深淺色）：2421 日 K 2/24「現增」與圖例 `title`；6669 日 K 9/2「權」「除權（配股）」；8112 日 K「除權息（含現金增資）」；2421 6/10「息」照舊；2421、6669 週 K 標記與圖例「當週」、原始價漲跌；6669 月 K「2026-09 月」；4155 週 K 兩筆事件；ETF 頁照舊。結束時關閉 8001、清掉 `tw.kmode`、`tw.kadj`、恢復視窗大小。
10. README（附錄 A 已含）；`04-dev.md` 記錄每一步的 `run_id`、請求數、行數。

- **允許的寫入**：`backup`、`setup-db` 兩次、回補一次（失敗重跑一次）、`export`（基線、新程式各一次）。不執行 `collect`、`history`、還原。
- 步驟 5 到 6 之間不要停：新程式在 `setup-db` 前跑 `export` 會失敗。若使用者在 PG 期間收集了，記錄 `run_id`，比對分開說明。
- **PG 預估**：程式＋README 約 65 行（原型 ＋63／−33）、測試 165 行＋fixture；三支比對腳本約 130 行。

---

## 十、對 PM 的調整

1. **`title` 文字改一點**：PM 的「…參考價依認購價計算，不是配股」放在「權 + `sc`（配股＋現增）」時自相矛盾。改為「現金增資除權：股東可依持股比例出錢認購新股（不是無償配股），參考價依認購價計算」，`c`、`sc` 共用。
2. **多一種文字「除權（配股＋現金增資）」**：PM 表沒有「權 + 股利＋現增」，目前 0 筆，但公式上可能，SA 補上。
3. **沒有現增的「權」也輸出 `k = "s"`**：D28-4 要寫「除權（配股）」，前端必須分辨「確定沒有現增」與「不知道（NULL）」，所以 `s` 要輸出。
4. **MERGE 用 `COALESCE`**：PM 寫「MERGE 多更新這一欄」；SA 改為缺值時保留已存的值，避免官方暫時改欄名時清掉回補的結果。
5. **`parse_events` 沒有值時不放 `div_ref` 鍵**：讓 `test_iter02` 不必修改（PM 共通規則「舊測試不改」的慣例）。
6. **漲跌不取整**：週／月 K 原始價漲跌用未取整的比值，漲跌幅和還原價完全一致；日 K 照舊用取整後的參考價（官方口徑）。
7. **漲跌那一格加 `title`**：說明「前一根收盤先乘上參考價 ÷ 前收」，PM 沒有要求，1 行。
8. **月 K 圖例由「2026-02-01」改「2026-02 月」、標記不縮寫**：375 寬實測可讀，PM 允許的縮寫不需要。
9. **第 378 行（融資融券換算標記）不套用分類**：那是官方換算紀錄，不是事件本身。
10. **PM 驗收 F19-2 #5 的日期與數值**：6949 面額變更 2026-09-07（週 K 2026-09-07 當週 −28.86%、月 K 2026-09 −32.08%）；8422 面額變更 2025-11-17（週 K −11.20%、月 K +1.45%）。PM 寫「不再是 −90% 以上」可以達成。
11. **同一根多筆的樣本**：週 K 只有 4155 2026-10-19（減＋息）；月 K 有 6186 2026-08、4155 2026-10 等 5 檔。
12. **`setup-db` 必須緊接在套用程式之後**：PM 的順序（改程式 → `setup-db`）可行，但中間有空檔時新程式的 `export` 會失敗；第九節第 5、6 步要連著做。

---

## 十一、給 PG、QA 的提醒

- 本機 node 是 v14，沒有 `Array.prototype.at`；測試只取出不用 `.at` 的函式，驗算腳本已補 polyfill，**不要**改網站程式。
- 回補後若 `ev`、`prices.ch` 因官方修正而變，屬資料變動，不是程式錯誤；`iter19_dbcheck.py` 要能逐筆說明。
- 使用者每晚收集後會自動 `export`：程式套用、`setup-db` 完成後，之後的匯出就有 `k`。
- 本輪尚未 commit；是否 commit 由使用者決定。
- 原型與驗算腳本（scratchpad `sa19/`）：`a1_edges`（邊界）、`a3_bars`（獨立週／月重算）、`a4_invariant`（原始＝還原）、`a5_js.js`（node 驗算）、`a6_kind`（分類與櫃買真值）、`a7_fixtures`（產生 fixture）、`a9_code.diff`（附錄 A）。

---

## 附錄 A：完整 diff（`orig` → `proj`，含新測試檔；fixture 另見 scratchpad `sa19/proj/tests/fixtures/`）

```diff
diff -ruN a/README.md b/README.md
--- a/README.md	2026-11-09 21:14:56
+++ b/README.md	2026-11-09 22:20:13
@@ -37,7 +37,7 @@
    - Mac：`bash scripts/mac/setup.sh`
    - Windows：雙擊 `scripts\windows\setup.bat`
 
-更新程式後若有新增資料表（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`，第 3 輪的 `collect_runs`、`market_holidays`，第 4 輪的 `etfs`、`etf_daily`、`margin_trades`、`etf_margin`、`margin_market`，第 5 輪的 `etf_holdings`、`etf_holding_summary`、`market_breadth`，第 6 輪的 `etf_holding_gaps`，第 10 輪的 `quarterly_financials`，第 11 輪的 `sbl_trades`、`etf_sbl` 與 `stocks.shares` 欄），請再執行一次 `python -m twstock setup-db`（可重複執行，不影響既有資料），否則 `collect`、`check`、`export` 會失敗。第 9 輪：`insti_amount` 加 `market` 欄（既有列為 `TWSE`），唯一鍵改成 `(trade_date, market, unit)`；`setup-db` 可重複執行，改表前請先 `backup`，改表後不可再執行舊版程式。
+更新程式後若有新增資料表（例如第 1 輪的 `market_index`、`stock_alerts`，第 2 輪的 `price_events`、`insti_amount`，第 3 輪的 `collect_runs`、`market_holidays`，第 4 輪的 `etfs`、`etf_daily`、`margin_trades`、`etf_margin`、`margin_market`，第 5 輪的 `etf_holdings`、`etf_holding_summary`、`market_breadth`，第 6 輪的 `etf_holding_gaps`，第 10 輪的 `quarterly_financials`，第 11 輪的 `sbl_trades`、`etf_sbl` 與 `stocks.shares` 欄，第 19 輪的 `price_events.div_ref` 欄），請再執行一次 `python -m twstock setup-db`（可重複執行，不影響既有資料），否則 `collect`、`check`、`export` 會失敗。第 9 輪：`insti_amount` 加 `market` 欄（既有列為 `TWSE`），唯一鍵改成 `(trade_date, market, unit)`；`setup-db` 可重複執行，改表前請先 `backup`，改表後不可再執行舊版程式。
 
 ## 日常使用
 
@@ -59,7 +59,7 @@
 python -m twstock history --start 2026-07-31 --only amount  # 只補三大法人買賣金額（上市、上櫃；已有的市場自動略過；每市場一天一個請求）
 python -m twstock history --start 2024-01-01 --only financials   # 只補季報（季底日在範圍內、窗口已開始的季別；每季上市、上櫃各 1 個請求；已有的季別自動略過，--force 重抓；約 22 次、2 分鐘）
 python -m twstock history --start 2025-10-30 --only sbl   # 只補借券賣出（上市、上櫃各 1 個請求／天；晚上 8 點半後才有當天資料；一年約 490 次、30 分鐘）；不指定 --only 時不補借券
-python -m twstock events --start 2025-10-30      # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑）
+python -m twstock events --start 2025-10-30      # 補抓除權息／減資／面額變更事件（約 1 分鐘，可重跑；每半年一段 × 4 個端點，這個區間 12 次請求。第 19 輪 setup-db 後執行一次，補齊減除股利參考價）
 python -m twstock revenue --year 2026 --month 9 --force     # 重抓某月營收
 python -m twstock futures --start 2020-01-01     # 補抓台指期日 K 與期貨三大法人未平倉（--commodity MTX 可抓小台）
 python -m twstock chains                         # 立即更新產業鏈族群（collect 每 30 天會自動更新）
@@ -136,7 +136,7 @@
 - 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
 - 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。第 17 輪：收集輸出的上市注意數字標「（近 30 天）」；證交所網站（上市注意）抓取失敗時只略過上市注意並印警告，上櫃與上市處置照常寫入（下次收集會補最近 30 天）；OpenAPI 4 個來源任一失敗仍整批不寫。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
-- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。
+- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。現金增資除權也依官方參考價調整。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 19 輪：除權事件依官方「減除股利參考價」（只扣股利、不扣現金增資，存在 `price_events.div_ref`；減資、面額變更沒有這一欄）分類，匯出 `ev[].k`：等於參考價 `s`（沒有現增，圖例「除權（配股）」）、等於前收 `c`（只有現增，標記「現增」、圖例「除權（現金增資）」）、其他 `sc`（股利＋現增，「權息」圖例「除權息（含現金增資）」）；容差 0.005 元，只對「權」「權息」，沒有值時照舊寫「除權」。週／月 K 的事件標記寫事件日（例如「2/24 現增」「6/10 息・6/24 權」），圖例第一欄寫「2026-02-23 當週」「2026-02 月」；「原始」價的週／月 K 那一根含事件時，前一根收盤先乘上每筆事件的參考價 ÷ 前收再相減，漲跌幅和「還原」相同（6669 週 K 2026-08-31 由 −64.38% 改為 +6.26%）。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
 - 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
 - 月營收：第 9 輪起從每月第一個交易日開始，`collect --catch-up` 每天第一次成功收集時抓已公布的公司（只補資料庫還沒有的公司，同一天只抓一次），直到該月家數達前一月的 98% 為止（約 10～12 日），之後到月底 0 個請求；`collect --date`、`history` 也收前一個月。月初官方檔案只有標題列時寫入 0 家，不是錯誤。
diff -ruN a/site/stock.js b/site/stock.js
--- a/site/stock.js	2026-11-09 21:14:56
+++ b/site/stock.js	2026-11-09 22:17:56
@@ -44,7 +44,7 @@
   const adjMode = localStore('kadj', '還原');
   const fund = data.fund || {};
   // P16：股本變動事件 90 天內，本益比與殖利率加註
-  const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${EV_LABEL[cap.t]}，官方值可能尚未調整` : '';
+  const cap = data.capchg, capSub = cap ? `${md(cap.d)} ${evName((data.ev || []).find(e => e.d === cap.d) || cap)}，官方值可能尚未調整` : '';
   // P9：本益比、殖利率卡的資料日（與 P16 註記並列）；值為空時說明是官方未提供
   // 第 10 輪 P24：淨值比卡也標資料日（cap = false：股本變動註記照舊只在本益比、殖利率卡）
   const fundSub = (v, cap = true) => [v == null && fund.date ? '官方未提供' : '', fund.date ? '資料 ' + md(fund.date) : '', cap ? capSub : ''].filter(Boolean).join('；');
@@ -175,7 +175,7 @@
   });
   if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
   if (tab !== 'k') return;
-  if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格，最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
+  if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格（現金增資除權也依官方參考價調整），最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
   // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
   const draw = () => {
     const m = localStore('kmode', '日'), adj = !E && localStore('kadj', '還原') === '還原';   // ETF 一律原始價、沒有技術面訊號
@@ -203,6 +203,11 @@
   return af;
 }
 const EV_LABEL = { '息': '除息', '權': '除權', '權息': '除權息', '減': '減資', '面': '面額變更', '調': '股本變動' };
+// 第 19 輪 F19-1：「權」「權息」依匯出的 k 細分（s 沒有現增、c 只有現增、sc 股利＋現增）；沒有 k 照舊
+const evName = e => e.t === '權' && e.k ? `除權（${{ s: '配股', c: '現金增資', sc: '配股＋現金增資' }[e.k]}）`
+  : e.t === '權息' && /c/.test(e.k || '') ? '除權息（含現金增資）' : EV_LABEL[e.t];
+const evMark = e => e.t === '權' && e.k === 'c' ? '現增' : e.t;
+const CASH_INC_TIP = '現金增資除權：股東可依持股比例出錢認購新股（不是無償配股），參考價依認購價計算';
 
 // ─── 日線 → 週線 / 月線（法人買賣超加總）；adj = 是否用還原價 ─────
 function aggregate(data, mode, adj) {
@@ -257,6 +262,16 @@
   return [...out.values()];
 }
 
+// 第 19 輪 F19-2（Q19-3）：K 棒的 [漲跌, 漲跌幅 %, 係數]。日線用匯出值；週／月線含推測調整（gx）不比價；
+// 原始價的週／月線含官方事件時，前一根收盤先乘上每筆（參考價 ÷ 前收）再相減，漲跌幅與還原價相同
+function barChange(raw, i, mode, adj) {
+  if (mode === '日') return [raw[i].ch, raw[i].pc, 1];
+  if (raw[i].gx) return [null, null, 1];
+  if (!i) return [0, 0, 1];
+  const f = adj ? 1 : raw[i].ev.reduce((a, e) => a * e.r / e.p, 1), base = raw[i - 1].c * f;
+  return [raw[i].c - base, (raw[i].c - base) / base * 100, f];
+}
+
 function calcMA(arr, p) {
   return arr.map((_, i) => i < p - 1 ? null : arr.slice(i - p + 1, i + 1).reduce((a, b) => a + b, 0) / p);
 }
@@ -332,9 +347,10 @@
   // 無成交的一字線用灰色
   kSer.setData(raw.map((r, i) => ({ time: T[i], open: O[i], high: H[i], low: L[i], close: C[i],
     ...(NT[i] ? { color: FLAT, borderColor: FLAT, wickColor: FLAT } : {}) })));
-  // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字
+  // 除權息、減資、面額變更標記（還原／原始都顯示）；週／月線同一根有多筆時合併文字，第 19 輪 F19-2：週／月線寫事件日「M/D 類型」
+  const mdn = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;
   kSer.setMarkers(raw.flatMap((r, i) => r.ev.length ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp',
-    color: css('--blue'), text: [...new Set(r.ev.map(e => e.t))].join('・') }]
+    color: css('--blue'), text: [...new Set(r.ev.map(e => (mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)))].join('・') }]
     : r.gx ? [{ time: T[i], position: 'belowBar', shape: 'arrowUp', color: css('--text2'), text: r.gx }] : []));   // 第 15 輪：ETF 推測的價格調整日
   line(kc, ma5, '#888780'); line(kc, ma20, '#EF9F27'); line(kc, ma60, '#7F77DD');
 
@@ -418,19 +434,17 @@
   const showLegend = i => {
     // 日線用匯出的漲跌（事件日相對參考價、前一日無成交相對最後成交）；找不到事件的不比價日為 null。週／月線用前一根收盤
     // 第 15 輪 QA-01：週／月線含推測價格調整（gx）的那一根不用原始價相減，改寫「不比價」，避免除息、分割被讀成下跌
-    const gxBar = mode !== '日' && raw[i].gx;
-    const chg = mode === '日' ? raw[i].ch : gxBar ? null : i ? C[i] - C[i - 1] : 0;
-    const p = mode === '日' ? raw[i].pc : i ? chg / C[i - 1] * 100 : 0;
+    const gxBar = mode !== '日' && raw[i].gx, [chg, p, f] = barChange(raw, i, mode, adj);
     const c = cls(chg);
     const ma = (label, v, color) => v == null ? '' : `<span style="color:${color}">${label} <b style="color:${color}">${pfmt(v)}</b></span>`;
-    legend.innerHTML = `<span><b>${T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
+    legend.innerHTML = `<span><b>${mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]}</b></span><span>開 <b>${pfmt(O[i])}</b></span><span>高 <b class="up">${pfmt(H[i])}</b></span>` +
       `<span>低 <b class="dn">${pfmt(L[i])}</b></span><span>收 <b class="${c}">${pfmt(C[i])}</b></span>` +
       (NT[i] ? '<span class="flat">無成交</span>'
         : chg == null ? `<span class="flat" title="${gxBar ? '期間含推測的價格調整（除息、分割等），原始價相減會失真' : '官方未提供漲跌，且找不到對應的除權息、減資、面額變更事件'}">不比價</span>`
-        : `<span class="${c}">${psgn(chg)} (${sgn(p)}%)</span>`) +
+        : `<span class="${c}"${f !== 1 ? ' title="期間含除權息等事件：前一根收盤先乘上參考價 ÷ 前收再相減"' : ''}>${psgn(chg)} (${sgn(p)}%)</span>`) +
       (mode === '日' && raw[i].rel ? `<span class="muted">相對 ${md(raw[i].rel)} 收盤</span>` : '') +
-      raw[i].ev.map(e => `<span class="ev-note"${e.t === '調' ? ' title="依櫃買官方漲跌反推的參考價調整（減資、面額變更等）"' : ''}>` +
-        `${mode === '日' ? '' : md(e.d) + ' '}${EV_LABEL[e.t]}　前收 ${pfmt(e.p)}　參考價 ${pfmt(e.r)}</span>`).join('') +
+      raw[i].ev.map(e => `<span class="ev-note"${e.t === '調' ? ' title="依櫃買官方漲跌反推的參考價調整（減資、面額變更等）"' : /c/.test(e.k || '') ? ` title="${CASH_INC_TIP}"` : ''}>` +
+        `${mode === '日' ? '' : md(e.d) + ' '}${evName(e)}　前收 ${pfmt(e.p)}　參考價 ${pfmt(e.r)}</span>`).join('') +
       (raw[i].gx ? `<span class="ev-note" title="只是推測，可能是除息、分割或合併">${mode === '日' ? '' : '期間含'}${raw[i].gx === '息?' ? '推測除息（官方不比價）' : '推測價格調整（參考價改變）'}</span>` : '') +
       `<span>量 <b>${fmt(V[i])}</b> 張</span>` +
       (N[i] != null ? `<span>法人 <b class="${cls(N[i])}">${sgn(N[i], 0)}</b> 張</span>` : '') +
diff -ruN a/tests/test_iter19.py b/tests/test_iter19.py
--- a/tests/test_iter19.py	1970-01-01 08:00:00
+++ b/tests/test_iter19.py	2026-11-09 22:19:46
@@ -0,0 +1,165 @@
+"""第 19 輪（不連網、不連資料庫）：F19-1 除權類型（配股／現金增資）；F19-2 週／月 K 的事件標記、圖例與原始價漲跌。
+fixture：tests/fixtures/twt49u_rights_mini.json、exdailyq_rights_mini.json（官方原始回應的精簡版：欄位不變，只留幾列；
+櫃買保留 1 年內一般股票全部「除權」「除權息」112 列，明細欄位當真值）。數值以 2026-11-09 為準。"""
+import json
+import shutil
+import subprocess
+import sys
+from datetime import date
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+sys.path.insert(0, str(ROOT))
+from twstock import db, export  # noqa: E402
+from twstock.collectors.events import parse_events  # noqa: E402
+
+FIX = Path(__file__).resolve().parent / "fixtures"
+STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+SRC = (ROOT / "twstock" / "collectors" / "events.py").read_text(encoding="utf-8")
+T49 = json.loads((FIX / "twt49u_rights_mini.json").read_text(encoding="utf-8"))
+TPX = json.loads((FIX / "exdailyq_rights_mini.json").read_text(encoding="utf-8"))["tables"][0]
+num = lambda s: float(str(s).replace(",", ""))
+
+
+def test_parse_div_ref():
+    r = {(x["stock_code"], x["event_date"]): x for x in parse_events("TWT49U", T49["fields"], T49["data"])}
+    assert r[("2421", "2026-02-24")] == {"stock_code": "2421", "event_date": "2026-02-24", "event_type": "權", "prev_close": 147.0,
+                                         "ref_price": 145.96, "source": "TWT49U", "div_ref": 147.0}
+    assert r[("6669", "2026-09-02")]["div_ref"] == 2614.99 and r[("8112", "2026-07-06")]["div_ref"] == 89.09
+    tp = parse_events("TPEX_EX", TPX["fields"], TPX["data"])
+    assert len(tp) == 114 and all("div_ref" in x for x in tp)                       # 112 權／權息 + 2 息；ETF 略過
+    # 欄位缺失：少了「減除股利參考價」→ 事件照常回傳、沒有 div_ref，不拋例外
+    i = T49["fields"].index("減除股利參考價")
+    f2 = T49["fields"][:i] + ["改名"] + T49["fields"][i + 1:]
+    r2 = parse_events("TWT49U", f2, T49["data"])
+    assert len(r2) == len(r) and all("div_ref" not in x for x in r2)
+    # 值無法解析（--、空白、0）→ 沒有 div_ref；列比欄位短 → 沒有 div_ref
+    row = T49["data"][0][:]
+    for bad in ("--", "", "0.00"):
+        row[i] = bad
+        assert "div_ref" not in parse_events("TWT49U", T49["fields"], [row])[0]
+    assert "div_ref" not in parse_events("TWT49U", T49["fields"], [T49["data"][0][:i]])[0]
+    # 減資、面額變更沒有這一欄
+    assert all(x is None for x in (export.rights_kind("減", 36.0, 47.14, None), export.rights_kind("面", 1490.0, 74.5, None)))
+    # MERGE 多更新一欄；缺值時保留已存的值
+    assert "div_ref DECIMAL(10,2)" in SRC and "div_ref = COALESCE(s.div_ref, t.div_ref)" in SRC
+    assert '"div_ref":null' not in db.to_json(r2)
+
+
+def test_rights_kind():
+    k = export.rights_kind
+    assert k("權", 147.0, 145.96, 147.0) == "c"                  # 2421 2026/02/24：只有現增
+    assert k("權", 214.0, 204.83, 214.0) == "c"                  # 3189 2026/01/26
+    assert k("權", 7800.0, 2614.99, 2614.99) == "s"              # 6669 2026/09/02：配股
+    assert k("權息", 92.9, 87.53, 89.09) == "sc"                 # 8112 2026/07/06：股利＋現增
+    assert k("權息", 19.1, 16.13, 17.31) == "sc"                 # 2614 2026/10/06
+    assert k("權息", 79.5, 63.75, 63.75) == "s"
+    assert k("權", 50.0, 45.0, 47.0) == "sc"                     # 「權」也可能是配股＋現增
+    assert k("息", 160.0, 154.75, 154.75) is None                # 只對「權」「權息」
+    assert k("權", 147.0, 145.96, None) is None                  # 舊資料、欄位缺失
+    assert k("權", 100.0, 100.0, 100.0) is None                  # 參考價 = 前收：無法分辨
+    assert k("權", 100.0, 95.0, 100.01) is None                  # 減除股利參考價高於前收：資料異常
+    assert k("權", 100.0, 95.0, 100.004) == "c" and k("權", 100.0, 95.0, 95.004) == "s"   # 容差 0.005 元
+
+
+def test_tpex_truth():
+    """櫃買明細（現金增資股數、每仟股無償配股、現金股利）為真值：112／112 一致。"""
+    f = {x: i for i, x in enumerate(TPX["fields"])}
+    n = 0
+    for r in TPX["data"]:
+        t = r[f["權/息"]].strip().lstrip("除")
+        if t not in ("權", "權息"):
+            continue
+        ci, sd, cash = (num(r[f[x]] or 0) > 0 for x in ("現金增資股數", "每仟股無償配股", "現金股利"))
+        want = "c" if ci and not (sd or cash) else "sc" if ci else "s"
+        assert export.rights_kind(t, num(r[3]), num(r[4]), num(r[f["減除股利參考價"]])) == want, r[:5]
+        n += 1
+    assert n == 112
+
+
+def test_price_events_k():
+    d = [date(2026, 2, x) for x in (23, 24, 25)]
+    c, ch = (144.5, 146.0, 147.0), (0.5, 0.05, 1.0)
+    off = [{"d": d[1], "t": "權", "p": 147.0, "r": 145.96, "src": "TWT49U", "k": "c"}]
+    ev, _ = export._price_events(d, c, ch, "TWSE", off)
+    assert ev == [{"i": 1, "d": "2026-02-24", "t": "權", "p": 147.0, "r": 145.96, "k": "c"}]
+    off[0]["k"] = None                                                                  # 沒有分類：不輸出 k（和改版前相同）
+    assert export._price_events(d, c, ch, "TWSE", off)[0] == [{"i": 1, "d": "2026-02-24", "t": "權", "p": 147.0, "r": 145.96}]
+    src = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")
+    assert '{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e}' in src and "e.div_ref" in src
+
+
+def test_setup_db():
+    src = (ROOT / "twstock" / "db.py").read_text(encoding="utf-8")       # 可重複執行：先判斷欄位是否存在
+    assert "IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE price_events ADD div_ref DECIMAL(10,2) NULL" in src
+
+
+def _js(names, consts=()):
+    """逐字取出 stock.js 的函式與常數（const 改 var，讓 node -e 取得到）。"""
+    out = []
+    for name in names:
+        s = STK.index(f"function {name}(")
+        i, n = STK.index("{", s), 0
+        for j in range(i, len(STK)):
+            n += {"{": 1, "}": -1}.get(STK[j], 0)
+            if n == 0:
+                out.append(STK[s:j + 1]); break
+    for name in consts:
+        s = STK.index(f"const {name} = ")
+        out.append("var" + STK[s + 5:STK.index(";\n", s) + 1])
+    return "\n".join(out)
+
+
+def test_js_bar_change_and_labels():
+    node = shutil.which("node")
+    if not node:
+        print("  （沒有 node，略過 JS 部分）"); return
+    # 週 K：第 1 週收 100；第 2 週二除權（前收 100 → 參考價 50）、收 55；第 3 週沒有事件
+    data = {"market": "TWSE", "prices": {"d": ["2026-08-28", "2026-09-01", "2026-09-02", "2026-09-07"],
+                                         "o": [100, 100, 50, 55], "h": [100, 100, 56, 56], "l": [100, 100, 50, 54],
+                                         "c": [100, 100, 55, 55], "v": [1, 1, 1, 1], "ch": [0, 0, 5, 0]},
+            "insti": None, "ev": [{"d": "2026-09-02", "t": "權", "p": 100, "r": 50, "k": "s"}]}
+    js = _js(["adjFactors", "aggregate", "barChange"], ["EV_LABEL", "evName", "evMark"]) + f"""
+const data = {json.dumps(data)};
+const out = [];
+for (const mode of ['週', '月', '日']) for (const adj of [false, true]) {{
+  const raw = aggregate(data, mode, adj);
+  out.push([mode, adj, raw.map((r, i) => barChange(raw, i, mode, adj).map(x => x == null ? null : Math.round(x * 1e6) / 1e6))]);
+}}
+const gx = [{{ c: 10, ev: [] }}, {{ c: 9, ev: [], gx: '息?' }}];
+const multi = [{{ c: 100, ev: [] }}, {{ c: 30, ev: [{{ p: 100, r: 50 }}, {{ p: 40, r: 32 }}] }}];
+const E = (t, k) => ({{ t, k }});
+console.log(JSON.stringify({{ out, gx: barChange(gx, 1, '週', false), first: barChange(gx, 0, '週', false),
+  multi: barChange(multi, 1, '月', false).map(x => Math.round(x * 1e6) / 1e6),
+  names: [E('權', 'c'), E('權', 's'), E('權', 'sc'), E('權'), E('權息', 'sc'), E('權息', 's'), E('權息'), E('息')].map(evName),
+  marks: [E('權', 'c'), E('權', 's'), E('權息', 'sc'), E('息')].map(evMark) }}));"""
+    r = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True, timeout=30).stdout)
+    got = {(m, a): v for m, a, v in r["out"]}
+    assert got[("週", False)][1] == [55 - 100 * 0.5, 10.0, 0.5]          # 原始：55 − 100 × 50/100 = +5（+10%），不是 −45
+    assert got[("週", True)][1][1] == 10.0                                # 還原的漲跌幅相同
+    assert got[("月", False)][1] == [5.0, 10.0, 0.5] and got[("月", True)][1][1] == 10.0
+    assert got[("日", False)][2] == [5, 10, 1]                            # 日線照舊用匯出的漲跌（ch）與 aggregate 的 pc
+    assert r["gx"] == [None, None, 1] and r["first"] == [0, 0, 1]        # gx 不比價；第一根 0
+    assert r["multi"] == [30 - 100 * 0.5 * 0.8, (30 - 40) / 40 * 100, 0.4]   # 多事件：比值相乘
+    assert r["names"] == ["除權（現金增資）", "除權（配股）", "除權（配股＋現金增資）", "除權", "除權息（含現金增資）", "除權息", "除權息", "除息"]
+    assert r["marks"] == ["現增", "權", "權息", "息"]
+
+
+def test_stock_page_source():
+    assert "barChange(raw, i, mode, adj)" in STK and "C[i] - C[i - 1] : 0" not in STK
+    assert "mode === '月' ? T[i].slice(0, 7) + ' 月' : mode === '週' ? T[i] + ' 當週' : T[i]" in STK
+    assert "(mode === '日' ? '' : mdn(e.d) + ' ') + evMark(e)" in STK                 # 週／月標記「M/D 類型」，日 K 不加日期
+    assert "${evName(e)}　前收" in STK and "CASH_INC_TIP" in STK
+    assert "evName((data.ev || []).find(e => e.d === cap.d) || cap)" in STK           # 股本變動註記用同一套文字
+    assert "現金增資除權也依官方參考價調整" in STK
+    seg = STK[STK.index("const evName"):STK.index("// ─── 日線 → 週線")]
+    for w in ("建議", "應認購", "吃虧", "稀釋", "買進", "賣出"):
+        assert w not in seg, w
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
diff -ruN a/twstock/collectors/events.py b/twstock/collectors/events.py
--- a/twstock/collectors/events.py	2026-10-30 23:14:02
+++ b/twstock/collectors/events.py	2026-11-09 22:16:58
@@ -12,23 +12,25 @@
 CHUNK_DAYS = 183      # 每次查詢的日期區間（實測 TWT49U 10 個月、櫃買 1 年一次可查；保守取半年）
 LOOKBACK_DAYS = 7     # 每日 collect 往回查的天數，補抓晚公告或前幾天漏抓的事件
 
-# 來源：(方法, 網址, 日期參數格式, (日期欄, 代號欄, 前收欄, 參考價欄, 類型欄), 固定類型)
+# 來源：(方法, 網址, 日期參數格式, (日期欄, 代號欄, 前收欄, 參考價欄, 類型欄), 固定類型, 減除股利參考價欄)
+# 第 19 輪：減除股利參考價是選用欄位，找不到時存 NULL，其他欄位照常寫入
 _SOURCES = {
     "TWT49U": ("GET", "https://www.twse.com.tw/rwd/zh/exRight/TWT49U", "%Y%m%d",
-               ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
+               ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權/息"), None, "減除股利參考價"),
     "TWTAUU": ("GET", "https://www.twse.com.tw/rwd/zh/reducation/TWTAUU", "%Y%m%d",
-               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "減"),
+               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "減", None),
     "TWTB8U": ("GET", "https://www.twse.com.tw/rwd/zh/change/TWTB8U", "%Y%m%d",
-               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "面"),
+               ("恢復買賣日期", "股票代號", "停止買賣前收盤價格", "恢復買賣參考價", None), "面", None),
     "TPEX_EX": ("POST", "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ", "%Y/%m/%d",
-                ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None),
+                ("除權息日期", "代號", "除權息前收盤價", "除權息參考價", "權/息"), None, "減除股利參考價"),
 }
 
 
 def parse_events(source: str, fields, rows) -> list:
-    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；欄位缺漏回傳 []。"""
-    names, fixed = _SOURCES[source][3], _SOURCES[source][4]
+    """官方事件表 → 寫入用 dict；非一般股票、日期或價格無法解析、類型不明的列略過；必要欄位缺漏回傳 []（減除股利參考價缺漏只存 None）。"""
+    names, fixed, dcol = _SOURCES[source][3:6]
     idx = {f: i for i, f in enumerate(fields or [])}
+    j = idx.get(dcol)
     need = [n for n in names if n]
     if not all(n in idx for n in need):
         return []
@@ -39,10 +41,11 @@
         code, d = str(row[idx[names[1]]]).strip(), roc_date(row[idx[names[0]]])
         prev, ref = clean_number(row[idx[names[2]]]), clean_number(row[idx[names[3]]])
         kind = fixed or str(row[idx[names[4]]]).strip().lstrip("除")     # 櫃買為「除權息」→「權息」
+        div = clean_number(row[j]) if j is not None and j < len(row) else None
         if not is_valid_stock_code(code) or d is None or not prev or not ref or kind not in EVENT_TYPES:
             continue
         out.append({"stock_code": code, "event_date": d.isoformat(), "event_type": kind,
-                    "prev_close": prev, "ref_price": ref, "source": source})
+                    "prev_close": prev, "ref_price": ref, "source": source, **({"div_ref": div} if div else {})})
     return out
 
 
@@ -76,16 +79,17 @@
                     SELECT st.stock_id, j.*
                     FROM OPENJSON(?) WITH (
                         stock_code NVARCHAR(10), event_date DATE, event_type NVARCHAR(4),
-                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), source NVARCHAR(10)
+                        prev_close DECIMAL(10,2), ref_price DECIMAL(10,2), div_ref DECIMAL(10,2), source NVARCHAR(10)
                     ) AS j
                     JOIN stocks st ON st.stock_code = j.stock_code
                 ) AS s
                 ON t.stock_id = s.stock_id AND t.event_date = s.event_date AND t.source = s.source
                 WHEN MATCHED THEN UPDATE SET
-                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price
+                    event_type = s.event_type, prev_close = s.prev_close, ref_price = s.ref_price,
+                    div_ref = COALESCE(s.div_ref, t.div_ref)     -- 欄位暫時找不到時不清掉已存的值
                 WHEN NOT MATCHED THEN
-                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, source)
-                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.source);
+                    INSERT (stock_id, event_date, event_type, prev_close, ref_price, div_ref, source)
+                    VALUES (s.stock_id, s.event_date, s.event_type, s.prev_close, s.ref_price, s.div_ref, s.source);
             """, db.to_json(rows))
             conn.commit()
         finally:
diff -ruN a/twstock/db.py b/twstock/db.py
--- a/twstock/db.py	2026-11-07 00:56:37
+++ b/twstock/db.py	2026-11-09 22:16:38
@@ -508,6 +508,8 @@
     """,
     # 第 11 輪：發行股數（update_industry 一併寫入；目前股數，不保留歷史）
     "IF COL_LENGTH('stocks', 'shares') IS NULL ALTER TABLE stocks ADD shares BIGINT NULL",
+    # 第 19 輪：減除股利參考價（只扣股利、不扣現金增資；TWT49U、TPEX_EX 才有，其他來源 NULL），分辨配股與現金增資
+    "IF COL_LENGTH('price_events', 'div_ref') IS NULL ALTER TABLE price_events ADD div_ref DECIMAL(10,2) NULL",
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
diff -ruN a/twstock/export.py b/twstock/export.py
--- a/twstock/export.py	2026-11-09 21:14:56
+++ b/twstock/export.py	2026-11-09 22:17:10
@@ -186,26 +186,37 @@
     return sorted(out, key=lambda x: (-x[1], x[0]))
 
 
+def rights_kind(t, p, r, dr):
+    """
+    F19-1：「權」「權息」依減除股利參考價 dr（只扣股利、不扣現金增資）分類；容差 0.005 元（兩者都是 2 位小數）。
+    dr = 參考價 → "s"（沒有現增）；dr = 前收 → "c"（只有現增）；其他 → "sc"（股利＋現增）。
+    其他類型、dr 空白、參考價 = 前收、dr 高於前收（資料異常）→ None（畫面照舊）。
+    """
+    if t not in ("權", "權息") or not dr or abs(r - p) < 0.005 or dr > p + 0.005:
+        return None
+    return "s" if abs(dr - r) < 0.005 else "c" if abs(dr - p) < 0.005 else "sc"
+
+
 def _price_events(d_, c, ch, market, official):
     """
     個股的價格調整事件（舊到新）：[{i, d, t, p, r}]。i = 生效的資料列索引（事件日當天或之後第一列），
-    d = 該列日期字串，t = 類型，p = 事件前收盤，r = 參考價。另回傳因係數不合理而略過的 [(日期, 係數)]。
+    d = 該列日期字串，t = 類型，p = 事件前收盤，r = 參考價，k = 除權類型（rights_kind，有值才有）。另回傳因係數不合理而略過的 [(日期, 係數)]。
     官方事件在第一筆資料之前或最後一筆之後的略過；上櫃另以「收盤 − 官方漲跌」反推（類型「調」），
     只在前一列有成交、漲跌有數值時計算，與官方事件同一列時以官方為準。
     """
     at, bad = {}, []
 
-    def add(i, t, p, r):
+    def add(i, t, p, r, k=None):
         f = r / p
         if ADJ_MIN <= f <= ADJ_MAX:
-            at[i] = {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": r}
+            at[i] = {"i": i, "d": str(d_[i]), "t": t, "p": p, "r": r, **({"k": k} if k else {})}
         else:
             bad.append((str(d_[i]), round(f, 4)))
 
     for e in sorted(official, key=lambda e: (e["d"], _SRC_RANK.get(e["src"], 1))):
         i = bisect_left(d_, e["d"])
         if 0 < i < len(d_) and i not in at:
-            add(i, e["t"], e["p"], e["r"])
+            add(i, e["t"], e["p"], e["r"], e.get("k"))
     if market == "TPEx":
         for i in range(1, len(d_)):
             if i in at or c[i] is None or c[i - 1] is None or ch[i] is None:
@@ -1346,11 +1357,12 @@
         WHERE a.alert_type = 'notice' AND a.announce_date >= ? AND a.announce_date <= ?""", watch_days[0], latest_date):
         watch_notes[code][ann] = clauses(reason)
     events = defaultdict(list)
-    for code, d, t, p, r, src in cur.execute("""
-        SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source
+    for code, d, t, p, r, src, dr in cur.execute("""
+        SELECT s.stock_code, e.event_date, e.event_type, e.prev_close, e.ref_price, e.source, e.div_ref
         FROM price_events e JOIN stocks s ON s.stock_id = e.stock_id
         ORDER BY s.stock_code, e.event_date"""):
-        events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src})
+        events[code].append({"d": d, "t": t, "p": float(p), "r": float(r), "src": src,
+                             "k": rights_kind(t, float(p), float(r), dr and float(dr))})
     mdates, mofficial, mstocks, metfs, mper = _load_margin(cur)
     first_m = min((ds[0] for ds in mdates.values()), default=latest_date)
     etf_px, etf_latest = _load_etfs(cur, first_m - timedelta(days=60))
@@ -1437,7 +1449,7 @@
             "prices": {"d": [str(x) for x in d_], "o": [_f(x) for x in o], "h": [_f(x) for x in h],
                        "l": [_f(x) for x in l], "c": [_f(x) for x in c],
                        "v": [round(x / 1000) if x else 0 for x in v], "ch": chs},   # 張
-            "ev": [{k: e[k] for k in ("d", "t", "p", "r")} for e in ev],
+            "ev": [{k: e[k] for k in ("d", "t", "p", "r", "k") if k in e} for e in ev],
             "insti": {"f": [round(x / 1000) if x is not None else None for x in fn],   # 張
                       "t": [round(x / 1000) if x is not None else None for x in tn],
                       "dl": [round(x / 1000) if x is not None else None for x in dn]},
```
