# 第 51 輪｜System Analyst：設計

- 撰寫日期：2026-11-26（週四，實測於 22:58 台北時間）；資料日 2026-11-26（`latest.json` `date` = 2026-11-26）。
- 依據：`51/01-analyst.md`（R80～R87、Q51-1～Q51-7）、`51/02-pm.md`（二之一逐字規格、二之二資料契約、驗收 39 條；D191～D203 全 A；PM 自行決定 19 點全照 PM）。
- 產出：本檔＋`51/03-design.diff`（1,020 行；在專案根目錄 `git apply --check docs/iterations/51/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive --exclude logs` 把專案複製到 scratchpad `sa51/`（**副本沒有 `.env`**）。另複製一份不含 `site/data` 的原始副本 `sa51o/` 當基準。
  - `logs/iter04_raw_MI_INDEX_20261103.json` 單獨複製進 `sa51/logs/`，給原型驗完整列數。
  - diff 用 `diff -u --label a/… --label b/…` 對專案現有檔案逐檔產生，新檔對 `/dev/null`。
  - 另把 HEAD 用 `git archive` 解到 `sa51c/` 再 `git apply`，結果和 `sa51/` 逐 byte 相同。在 `sa51c/`（沒有 `logs/`）跑 `test_iter51` 也通過，原檔驗證那段會自動略過。
  - 改前 `tests/test_iter01～50` 全過。改後 `test_iter01～51` **51 個檔全過**，在兩種資料下各跑一次：「匯出前資料」（`sa51/`，`site/data` 為專案現況的複本）與「副本 export 後資料」（`sa51e/`）。
  - 副本 export（第七節）：只借專案 `config.py` 把連線設定載入行程內環境變數（**沒有讀、印、複製 `.env`**），import 的是副本的 `twstock`（`SITE_DATA_DIR` 已確認在副本內）。DB 連線包一層：`execute` 拒絕 INSERT／UPDATE／DELETE／MERGE／EXEC／CREATE／ALTER／DROP，`commit()` 直接拋錯；`twse_index` 的兩個查詢改回假資料（資料表還不存在）。`fetch._SESSION.request` 換成拋錯，確保 0 外部請求。
  - 資料庫：只有唯讀 SELECT（`OBJECT_ID('twse_index')` = NULL、上市 `stocks.industry` 分佈、TAIEX 2025-10-30 收盤與筆數、`INFORMATION_SCHEMA.TABLES` = 31）。
  - 外部請求：**3 次**（第六節），都經 `twstock.fetch.request`。
  - 預覽：副本 `sa51e/` 在 8001 跑 `twstock serve`，看完已關（`lsof -i :8001`、`:8002` 沒有輸出）。8000 沒碰；localStorage 已恢復為 `{"tw.todayTab":"ov","tw.stockTab":"k"}`，視窗已設回 preset desktop。
  - 專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（diff 的 +／−）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `twstock/db.py` | 16／1 | `DDL` 在 `market_index` 之後新增 `twse_index`（15 行）；`setup-db` 訊息改 1 行（第五節差異 2） |
| `twstock/collectors/daily.py` | 77／0 | `TWSE_INDEX_TABLES`、`parse_twse_indices`（`parse_taiex` 之後）；`merge_twse_index`（`merge_market_index` 之後）；`_save_twse_indices`（`_quotes` 之前）；`_collect_key` 附掛 2 行 |
| `twstock/collectors/history.py` | 2／0 | D202：`--force` 時多印 1 行 |
| `twstock/__main__.py` | 1／0 | `history` 說明 1 行（PM 逐字） |
| `twstock/export.py` | 73／0 | `ixr_export`、`ixr_perf`、`SX_SKIP`、`SX_ALIAS`、`sx_export`、`_load_twse_index`（都在 `ix_export` 之後、`stock_perf` 之前）；讀表 2 行；寫 `ixr.json` 1 行；`latest.sx`／`latest.ixr` 5 行；📌 6 行 |
| `site/app.js` | 21／0 | `sxCard`（`flowNote` 之後，17 行）；`body.flow` 1 行；監聽 3 行 |
| `site/stock.js` | 2／1 | `perfHTML` 新增 1 行；表格結尾那行插入 `${xr}` |
| `site/compare.js` | 10／4 | `renderCompare` 內新增 4 行；改 4 行（圖例、表格列、說明行、十字線），新東西都接在既有字串之後；畫線 1 行 |
| `site/index.html` | 3／3 | `app.js`、`stock.js`、`compare.js` 的 `?v=` |
| `README.md` | 2／0 | 測試指令 1 行、第 51 輪一段 |
| `docs/iterations/README.md` | 1／0 | 第 51 輪一行（PG／QA 之後補） |
| `tests/test_iter51.py`（新） | 577／0 | 18 個測試、23 個反證 |
| `tests/test_iter49.py`、`tests/test_iter50.py` | 各 1／1 | D200 同意的 2 行（第四節） |

- 程式合計 **+205／−9**（上限約 770）；新測試 577 行（上限約 580）。
- 0 變更：`app.css`、`tools.js`、`help.js`、`health.py`、`catchup.py`、`fetch.py`、`backup.py`、`parse_taiex`、`stock_perf`、`period_return`、`index_return`、`ix_export`、`etf_export`、`etf_perf`、`compare.js` 純函式（都由新測試以 sha1 鎖住）。

## 二、程式設計

### 2-1 新表（`db.py:204～219`）

```sql
IF OBJECT_ID('twse_index') IS NULL
CREATE TABLE twse_index (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    trade_date  DATE          NOT NULL,
    kind        CHAR(1)       NOT NULL,   -- P = 價格指數(臺灣證券交易所)、R = 報酬指數(臺灣證券交易所)
    seq         SMALLINT      NOT NULL,   -- 官方表的列順序（0 起；匯出依這欄排，不依 id）
    index_name  NVARCHAR(40)  NOT NULL,
    close_price DECIMAL(12,2) NOT NULL,
    change      DECIMAL(12,2) NULL,
    created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_twse_index UNIQUE (trade_date, kind, index_name)
)
```

- **加了 `seq`**（PM 二之十授權「確認不了就加」）。理由有兩個：
  - SQL Server 不確定 `MERGE … USING OPENJSON` 插入時 IDENTITY 依來源順序遞增（MERGE 不能帶 ORDER BY）。
  - 同一天重抓時 MERGE 只 UPDATE、不改 `id`；若官方之後在表中間插入新列，新列的 `id` 會排在最後。
  
  因為不能寫 DB 實測，所以直接加欄。`seq` = 官方 `data` 陣列的索引，略過的列也占號，只用來排序。
- `setup-db` 訊息：`… share_distribution（第 43 輪）、twse_index（第 51 輪）、etf_holding_gaps")`。插在 `etf_holding_gaps` 之前，因為 `test_iter06.py:143` 鎖了 `etf_holding_gaps")` 這個結尾；第 43 輪也是這樣插。
- `market_index` 那段一字不改（sha1 `848829684373`）。

### 2-2 解析（`daily.py:63～97`）

- `TWSE_INDEX_TABLES = (("P", "價格指數(臺灣證券交易所)", "指數", "類股指數"), ("R", "報酬指數(臺灣證券交易所)", "報酬指數", "報酬指數"))`：kind、表名、第一欄名、⚠️ 用字。
- `parse_twse_indices(data, d) -> {"P": 列或 None, "R": 列或 None}`：規則完全照 PM B-1。
  - 找表：title **包含**表名即可。
  - 必要欄缺任一個 → 該表為 None。
  - 列太短、收盤是 None 或 ≤ 0、名稱空白或超過 40 字 → 略過該列。
  - 同表同名：只留第一個有效列。
  - 正負號：`漲跌(+/-)` 欄含 `-` 就取負。
  - `特殊處理註記`：有這欄才讀，沒有時為空字串。
  - 列的欄位：`trade_date, kind, seq, index_name, close_price, change, note`；`note` 只供 ℹ️，不寫進 DB。
- `parse_taiex` 不改（sha1 `0607285b4af3`）。

### 2-3 寫入與附掛（`daily.py:792～804`、`:937～960`、`:994～995`）

- `merge_twse_index`：`MERGE twse_index … ON trade_date, kind, index_name`；`WHEN MATCHED THEN UPDATE SET seq, close_price, change`；`WHEN NOT MATCHED THEN INSERT`。P、R 兩張一次 `_save`。
- `_save_twse_indices(d, cache)` 的流程：
  1. `cache["tidx"]` 旗標：同一次 `collect_for_date` 只做一次（PM 9）。
  2. 解析後，任一表為 None → 印 PM 逐字的 ⚠️（P／R 各一句）。
  3. 有非空註記 → 印 ℹ️：最多列 3 個，超過時寫 `…等 N 個`。
  4. 有列 → `_save`。
  5. 例外分兩段攔截：
     - `db.pyodbc.Error` → `⚠️  twse_index 寫入失敗（請確認已執行 setup-db）：{str(e) 第一行前 120 字}`。
     - `PARSE_ERRORS` → `⚠️  MI_INDEX 證交所指數表解析失敗，類股指數與報酬指數未寫入（個股與加權指數照常）：{e 前 120 字}`（第五節差異 4）。
- **`pyodbc` 的取得方式：用 `db.pyodbc.Error`**（同 `backup.py:62`）。`daily.py` 不新增 import。
- 附掛：`_collect_key` 的 `elif rows: print("⚠️ MI_INDEX 找不到加權指數表")` 之後、`if key == "index.TAIEX": return …` 之前新增 2 行：
  ```python
          if rows:
              _save_twse_indices(d, cache)                # 第 51 輪 F51-2：同一份回應寫證交所類股、報酬指數（失敗只 ⚠️；同一次只寫一次）
  ```
  既有行一字不改。休市（`stat` 非 OK）時 `rows = []`，不會經過。
- `DAY_KEYS`、`DATASET_KEYS`、`health.SPECS`、`SECONDS_PER_KEY`、`SHARED` 不變（sha1 `a4d473ff047f`）。

### 2-4 history 與說明（D202）

- `history.py:174～175`：在既有「等 30 分鐘以上……自動跳過。」提示（第 172～173 行）之後加：
  ```python
          if force:                                       # 第 51 輪 D202：--force 時上一句不成立（重跑會從 --start 重抓）
              print(f"   這次有 --force：重跑會從頭重抓，請改用 --start {blocked_at} 接續。")
  ```
- `__main__.py:11`：PM 逐字一行。

### 2-5 匯出（`export.py`）

| 位置 | 內容 |
|---|---|
| `:1240` `ixr_export(days, ixr)` | `{"d": [...], "TAIEXR": [_f(ixr.get(d))]}`，鍵順序 `d`、`TAIEXR` |
| `:1245` `ixr_perf(days, ixr, w52_start)` | 基準日寫法和 `stock_perf` 那一行相同（`PF_DAYS` 的 `days[-1-N]`、`y`、`w`）；值 = `_f(index_return(ixr, b, last))`；沒有 `s` |
| `:1253` `SX_SKIP`、`SX_ALIAS` | 5 個排除名稱；`{"電腦及週邊設備": "電腦及週邊"}` |
| `:1257` `sx_export(sxp, days, last, industries)` | 回傳 `(sx 或 None, 官方對不到, 本站對不到)`，細節見下 |
| `:1283` `_load_twse_index(cur)` | `OBJECT_ID` 為 NULL → None；否則讀 `(kind='R' AND 名稱='發行量加權股價報酬指數') OR (kind='P' AND 名稱 LIKE '%類指數')`，`ORDER BY trade_date, kind, seq` → `(ixr_close, sxp)` |
| `:1763～1764` | 讀 `market_index` 之後：`tx = _load_twse_index(cur)`；`ixr_close, sxp = tx or ({}, {})`（在 `conn.close()` 之前） |
| `:1853` | 寫 `ix.json` 那行之後：`_write(SITE_DATA_DIR / "ixr.json", ixr_export(p_days, ixr_close))`。資料表不存在時也寫，內容全部 null（PM 13） |
| `:2102～2106` | `latest["alerts"]["w"]` 之後、`S = screen_build(` 之前：`sx`（有才輸出）、`ixr`（`latest_date in ixr_close` 才輸出，`d` = 資料日） |
| `:2121～2126` | 📌：放在「📌 ETF 個股」那行之後（第五節差異 3） |

`sx_export` 的規則：
- `sx.d` 取 `sxp` 中 ≤ `last` 的最後一天。
- `b5`／`b20` 取 `days`（= `p_days`）中 `sx.d` 往前第 5、20 個交易日；不足時為 None。
- 5／20 日 % 只看基準日那天有沒有同名列，沒有就是 None，不拿前後日子補（R84）。
- 列入條件：名稱不在 `SX_SKIP`，且「去掉 `類指數`、再經 `SX_ALIAS` 對照」後的名稱在 `industries` 裡。
- `industries` = 匯出時 `stocks` 中 `market == "TWSE"` 的產業別。既有寫法把 NULL 轉成「其他」，而「其他」本來就是官方類股之一，所以結果不受影響（第五節差異 9）。
- 對不到的官方名稱依官方順序列出；本站對不到的產業別排序後列出。

📌 訊息（逐字）：
- `  📌 證交所指數 2026-11-26：類股 32 類；加權報酬指數 261／261 天`
- 有對不到的類股時，下一行：`  📌 類股名稱對不到：官方 半導體業；本站 --`
- 資料表不存在：`  📌 證交所指數：尚未建立 twse_index（請執行 setup-db），類股指數與含息線不輸出`
- 有表但沒有任何 P 列：`  📌 證交所指數 --：類股 0 類；加權報酬指數 0／261 天`

### 2-6 前端

- **`app.js` `sxCard(L)`（`:310～326`）**：照 PM A-2～A-4 逐字。
  - 排序：先依值比較，同值依官方序號；`null` 不論方向都排最後。
  - `App.sxSort` 預設 `{k: 'p', d: -1}`。
  - `slice(0, App.sxAll ? 全部 : 10)`。
  - 短句、全文用變數（`noteHTML` 字面呼叫仍是 8 個）。
  - 只用 `fmt`、`sgn`、`cls`、`md`、`noteHTML`（PM 驗收 28 的取出清單），所以名稱沒有經過 `esc`（第五節差異 8）。
  - 監聽（`:268～270`）：`#sxMore` 1 行；`.sx th.sort` 點擊 2 行（同一欄 → 反向，換欄 → 由高到低），不寫 localStorage。
- **`stock.js` `perfHTML`**：
  - `:46` 新增 `const X = App.latest.ixr, xr = …`。條件：`X.d === App.latest.date && (mkt === 'TWSE' || etf)`；文字照 PM C 逐字。
  - `:50`（原 `:49`）表格結尾插入 `${xr}`。
  - 沒有 `latest.ixr` 時 `xr = ''`，輸出不變（`STOCK_SHA`、`test_iter46` 的 ETF 版、`test_iter23` 全過）。
- **`compare.js` `renderCompare`**：
  - `:99～102` 新增 4 行：
    - `ixr`：只有在 `X` 存在時才讀 `data/ixr.json`，`catch → null`。
    - `miss`：長度或最後一天不同 → 起點日；否則找 `[X.b, X.end]` 中第一個沒有值的日子。
    - `XR = cmpLine(ix.d, ix.d, ixr.TAIEXR, X.b)`。
    - `ring` 是區域常數。
  - 改 4 行，新東西都接在既有字串後面，沒有 `ixr.json` 時 HTML 和改前逐字相同：
    - `:123` 圖例第三個 span。
    - `:126` 表格最後一列。
    - `:127`「表格依加入順序……（--）。</div>」之後接說明句或「沒有資料」一句。
    - `:155～156` 十字線（那天沒有值時寫 `含息 <b>--</b>`）。
  - `:172` 新增：`if (XR) add(XR, css('--text2'), 1, 2)`，畫在加權虛線之後、各檔實線之前。
  - 純函式 0 行改動（sha1 `1dccb16dabca`）。

### 2-7 `index.html`（`?v=` = `shasum` 前 8 碼）

| 檔案 | `?v=` |
|---|---|
| `app.js` | **a837955f**（原 692538e8） |
| `stock.js` | **e41e8ece**（原 e527a385） |
| `compare.js` | **f7e0bca5**（原 1c11197d） |
| `app.css`、`tools.js`、`help.js` | ce1417aa、0a050889、a5a5a7e8（不變） |

`https://` 仍是 2 個，`<script>` 順序不變。PG 套用後若有任何一字不同，`?v=` 要重算。

## 三、測試設計（`tests/test_iter51.py`，不連網、不連資料庫）

- 沿用的 helper：`test_iter03.World`（子類別把 MI_INDEX 第 0 張換成樣本、記下 `twse_index` 的 MERGE、可讓 MERGE 丟錯）、`test_iter34._grab`／`_node`、`test_iter48.DOM`（換掉 `getJSON` 與 `css`，另加假的 `LightweightCharts`，接住 `subscribeCrosshairMove` 的回呼）、`test_iter46.PF`／`check_card`。
- 用詞清單 = `test_iter48.ADVICE` ∪ {強, 弱, 名次}。
- 樣本內嵌：11/03 價格指數 40 列（加權、37 個「類指數」、2 個槓桿反向）＋報酬指數 4 列＋同名不同值的跨市場、臺灣指數公司表。
- `logs/` 有原檔時另驗 56／47 列，以及 32 類漲跌 % 等於官方百分比欄。
- 各檢查函式都接受原始碼字串；Python 函式從原始碼取出後，在模組名稱空間的複本執行。

| 測試 | 內容 | 驗收 |
|---|---|---|
| `test_parse` | 樣本 P 40、R 4 列，PM 的 6 組數值，`seq` 連號，跨市場與臺灣指數公司不收；原檔 56／47、32 類 % = 官方；`parse_taiex` sha1 | 1、3 |
| `test_abnormal` | 表名只差日期前綴、列太短、收盤空白／`--`／0、名稱空白／41 字、同名、`<p>-</p>`／`+`／空字串正負號；P 第一欄改名 → P None、R 照常（反之亦然）；沒有註記欄 | 2 |
| `test_once` | 假世界跑一天 `DAY_KEYS`：MERGE 1 次（44 列）、MI_INDEX 請求 1 次、回傳值、沒有 ⚠️；只跑 `index.TAIEX` → 1 次；原假世界 → R ⚠️ 1 行；P 表沒有加權列 → 加權 ⚠️ 照舊、新表照寫；MERGE SQL 字串 | 4、5、9 |
| `test_errors` | `pyodbc.Error`、`TypeError`（R 表 `data` 是 null）、`SchemaError`、`KeyError`：`written`、`errors` 和不丟錯時相同，個股 1100 筆、加權照寫，⚠️ 逐字，沒有 Traceback | 6 |
| `test_closed_and_notes` | 休市 → 沒有 MERGE、沒有新訊息；註記 2 列 → ℹ️ 逐字、5 列 → `…等 5 個`；資料集鍵 sha1；DDL 欄位、`market_index` sha1 與位置；`setup-db` 訊息 | 7、8、10、11 |
| `test_history_hint` | D202 兩行的位置；`__main__` 說明逐字 | 32 |
| `test_sx` | 32 列、官方順序、排除 5 個、`電腦及週邊設備`、PM 的 6 個 %；改名 → 31 列＋兩邊名稱；25 天假資料的 `b5`、`b20` 與值；基準日缺列 → None；10 天 → `b20` None；`sx.d` 早一天；空 → None | 12～15 |
| `test_ixr` | PM 驗收 16 的 JSON 字串逐字；`ixr_perf` 基準日 = `stock_perf`，值 = `index_return`，缺值 None，沒有 `s` | 16、17 |
| `test_wiring` | 📌 三種情況執行後逐字；`ixr.json` 緊接在 `ix.json` 之後；`ix_export(` 2 次；`sx`／`ixr` 在 `alerts.w` 之後、`screen_build` 之前；讀表在 `conn.close()` 之前；6 個既有函式 sha1 | 15、18、19 |
| `test_load` | 資料表不存在 → None；R／P 分開、保持順序 | 15 |
| `test_sx_card` | node 跑 `sxCard`：預設前 10 列（PM 清單）、全部 32 列、由低到高前 3 列、鋼鐵／橡膠兩個方向都依官方順序、5 日排序 null 在最後、表頭 ▼／▲、漲跌欄逐字、`--` 不帶 `%`、沒有 `data-code`、短句全文逐字（有／沒有括號日期）、（尚未更新）、沒有 `sx` → `''`；`body.flow` 那一行的位置、`noteHTML` 字面 8 個、監聽逐字、沒有 localStorage | 20～22、28 |
| `test_cmp` | 假 DOM＋假圖表：圖例三個 span、表格列數字 = `cmpLine` 統計、說明句位置、線設定 `[--text2, 1, 2]` 排在第 2、十字線最後一項；起點、終點缺值與長度不同 → 不畫並寫日期；中間缺值 → `含息 <b>--</b>`；沒有 `ixr.json` → 沒有新東西；純函式 sha1 | 23～25 |
| `test_perf` | 上市股票、上櫃 ETF、上市 ETF 有追加行（逐字含 `title`、位置）；上櫃股票、`ixr.d` 不同、沒有 `ixr` → 沒有；`test_iter46.check_card` 仍通過 | 26 |
| `test_words_node14` | 新字串（`sxCard`、含第 51 輪／`ixr`／`twse_index` 等字樣的行、新函式全文、README 段落）不含用詞清單；比較頁新行不含「差距」；不含 `.at(` 等 | 27、28 |
| `test_version_and_docs` | 6 個 `?v=` = sha1、3 個不變值、舊值已不在、`https://` 2 個、`<script>` 順序、README 指令與段落關鍵字、不含「第 23 輪」、`docs/iterations/README.md` | 29、32 |
| `test_site_data` | 已匯出時：`ixr.json` 的 `d` = `ix.json`、≤ 8 KB、`sx.d` = `ixr.d` = 資料日、`ixr.pf` 基準日 = 2330 `pf`、`b5`／`b20` = 2330 的 5／20 日基準日、32 列、每個區間 = `TAIEXR` 手算、11/03 = 100144.27；沒匯出時印一行略過 | 35、36 |
| `test_contrast` | 23 個反證 | 反證 |

### 反證清單（副本逐一確認：全部由檢查回傳 False 擋下，沒有一個是靠例外）

| # | 改壞方式 | 擋下的檢查 |
|---|---|---|
| 1 | R 表用「指數」定位 | `check_parse` |
| 2 | 不去重 | `check_abnormal` |
| 3 | 收盤 ≤ 0 不略過 | `check_abnormal` |
| 4 | 不設旗標（寫兩次） | `check_once` |
| 5 | 新表放到 `if taiex` 裡 | `check_once`（P 表沒有加權列的樣本） |
| 6 | 不攔 `pyodbc.Error` | `check_errors` |
| 7 | 不攔解析錯誤 | `check_errors` |
| 8 | 寫死 32 類（固定名單） | `check_sx` |
| 9 | 不做名稱對照（電腦及週邊設備） | `check_sx` |
| 10 | 不排除合併類 | `check_sx` |
| 11 | 5／20 日用前一天補 | `check_sx` |
| 12 | `ixr.pf` 基準日差一天 | `check_ixr` |
| 13 | 函式名用 `ix_export2(` | `check_wiring` |
| 14 | 訊息缺值寫 0 | `check_wiring` |
| 15 | `sgn(null) + '%'`（出現 `--%`） | `check_sx_card` |
| 16 | null 不排最後 | `check_sx_card` |
| 17 | 同值反過來排 | `check_sx_card` |
| 18 | 比較頁起點缺值仍畫線 | `check_cmp` |
| 19 | 長度不同也畫 | `check_cmp` |
| 20 | 十字線缺值寫數字 | `check_cmp` |
| 21 | `perfHTML` 引用新的頂層常數 | `check_perf`（node `ReferenceError`） |
| 22 | 上櫃股票也加 | `check_perf` |
| 23 | 比較頁新字串混入用詞清單中的詞 | `check_words` |

- 說明：
  - 第 17 項：node 的 `Array.prototype.sort` 是穩定排序，所以「拿掉同值比較」本身擋不下（結果相同）。反證改成「同值反過來排」。
  - 第 13 項：`ix_export2(` 不含 `ix_export(` 子字串，`test_iter48` 的「出現 2 次」擋不下；由 `def ixr_export(` 出現 1 次擋下。
- 驗收 33、34、37～39 要實際資料、瀏覽器或 PG 執行紀錄，不放進測試（第七、八節）。

## 四、舊測試

| 檔案:行 | 改前 | 改後 |
|---|---|---|
| `tests/test_iter49.py:261` | `    for s in ("help.js?v=a5a5a7e8", "compare.js?v=1c11197d"):` | `    for s in ("help.js?v=a5a5a7e8",):` |
| `tests/test_iter50.py:376` | `    for s in ("app.css?v=ce1417aa", "tools.js?v=0a050889", "help.js?v=a5a5a7e8", "compare.js?v=1c11197d"):` | `    for s in ("app.css?v=ce1417aa", "tools.js?v=0a050889", "help.js?v=a5a5a7e8"):` |

- 只改這 2 行（D200）；`app.css` 沒改，所以 `app.css` 的版本鎖保留。其他舊測試 0 行。
- 原型過程中碰到的兩個舊測試鎖，都改用不動舊測試的寫法避開：
  - `test_iter06.py:143` 鎖 `etf_holding_gaps")` → 表名改插在它前面。
  - `test_iter50.py:100～111` 會執行「📌 還原事件」到「📌 ETF 個股」之間的程式並比對輸出 → 新 📌 改放在「ETF 個股」之後。
- PM 疑慮：
  - 「假世界 MI_INDEX 沒有報酬指數表」：每次假收集確實多印 1 行 R 的 ⚠️，但 50 個舊測試全過，沒有測試斷言「沒有 ⚠️」。
  - `test_iter04.py:369`（請求順序）、`:277～278`（`merges` 集合）也通過。後者的情境是只補 ETF，不經過新表那一段。

## 五、和 PM 規格的差異（逐點）

1. **新表加 `seq SMALLINT NOT NULL`**，匯出依 `seq` 排序，不依 `id`（理由見 2-1；PM 二之十授權）。MERGE 遇到已有的列時也更新 `seq`。
2. **`setup-db` 訊息改既有 1 行**：表名插在 `etf_holding_gaps` 之前，不是加在最後（`test_iter06.py:143`）。
3. **匯出 📌 放在「📌 ETF 個股」那一行之後**，不是緊接「📌 收在漲停」之後（`test_iter50.check_snapshot` 會執行那一段並逐字比對輸出）。仍在「收在漲停」之後。
4. **解析錯誤另有一句 ⚠️**：PM 只定了「找不到表」與「寫入失敗」兩種。`PARSE_ERRORS` 印 `⚠️  MI_INDEX 證交所指數表解析失敗，類股指數與報酬指數未寫入（個股與加權指數照常）：{錯誤}`；`pyodbc.Error` 照 PM 逐字。`pyodbc` 用 `db.pyodbc`，不新增 import。
5. **有表但沒有 P 列時**的 📌 寫 `證交所指數 --：類股 0 類；加權報酬指數 0／N 天`（PM 沒有規定）。
6. **`compare.js` 改 4 個既有行**：PM「接在既有字串之後」只能改同一行才做得到。說明句接在「表格依加入順序……」那一行的結尾，沒有新增一行，這樣沒有 `ixr.json` 時輸出逐字相同。`ixr.json` 只在有比較對象（`X`）時才讀，比 PM 少讀一次。
7. **`stock.js` 改 1 個既有行**（表格結尾插入 `${xr}`）；`short`、`full`、表頭、呼叫行不動。
8. **`sxCard` 的名稱沒有經過 `esc`**：PM 驗收 28 規定只取 `fmt`、`sgn`、`cls`、`md`、`noteHTML`。名稱來自證交所，且已限定為能對到本站產業別的 32 類（不含 `<`、`&`）。
9. **本站產業別集合沿用 `stocks` dict（NULL 已轉成「其他」）**：「其他」本來就是官方類股之一，結果和「不含 null」相同。
10. **D202 是 2 行**（`if force:` ＋ `print`），PM 估 1 行。
11. **監聽 3 行**（PM 估 2 行）：排序點擊需要 `querySelectorAll` 迴圈。
12. **新測試 577 行**（PM 估 330～380，上限約 580）：多出的是假圖表的十字線、四種錯誤情境、23 個反證。
13. 其餘文字、位置、條件、鍵名、格式都和 PM 二之一、二之二逐字相同。

## 六、第 51 輪實測（D199：3 次，都經 `twstock.fetch.request`）

- 執行前 `pgrep -fl twstock` 只有使用者的 `twstock serve`（8000）；22:58 避開了 22:30 排程前後 20 分鐘。
- 全部用 `request(…, expect_json=False, isolated=True)`：失敗不重試，每個網址最多送出 1 次。
- `request_count()` 前後差：1＋1＋1 = **3 次**。
- 原始回應只存在 scratchpad `sa51raw/`（`mi_20251030.bin`、`tpex_swagger.bin`、`tpex_reward_index.bin`），專案目錄沒有。解析用 `python3 -I`。

### 6-1 上市 MI_INDEX 最舊日（Q51-1）

- 請求：`GET https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date=20251030&type=ALLBUT0999`。
- 結果：22:58:06，HTTP 200，`application/json;charset=UTF-8`，237,370 bytes，`stat` = OK，`date` = 20251030。

| 項目 | 2025-10-30 | 2026-11-03 樣本 |
|---|---|---|
| 表數 | 10 | 10 |
| 第 0 張 | `114年10月30日 價格指數(臺灣證券交易所)` 56 列 | `115年11月03日 …` 56 列 |
| 第 3 張 | `報酬指數(臺灣證券交易所)` 47 列 | 47 列 |
| 欄名 | P：`指數、收盤指數、漲跌(+/-)、漲跌點數、漲跌百分比(%)、特殊處理註記`；R 第一欄 `報酬指數` | 相同 |
| 名稱與順序 | 兩張表的名稱集合、順序和 11/03 **完全相同** | — |
| 類股 | 「類指數」結尾去掉 5 個合併／綜合類 = **32** | 32 |
| 特殊處理註記 | 全部空字串 | 全部空字串 |
| 其他表列數 | 跨市場 50／51、臺灣指數公司 33／32、行情 1,319 列（只記錄，不用） | 46／47、36／35、1,390 |
| 加權 | 28,287.53、−7.21（= DB `market_index` 該日） | 43,307.54 |
| 加權報酬 | **64,273.28**、−16.37（−0.03%） | 100,144.27 |
| 名稱最長 | 15 字 | 15 字 |

- 結論：結構一致，不必停下回報；回補可以直接跑。2025-10-30 → 2026-11-03 加權報酬指數 +55.81%，加權價格指數 +53.10%。

### 6-2 櫃買（D191、Q51-3；只記錄，不建表、不寫程式）

| # | 請求 | 結果 |
|---|---|---|
| 2 | `GET https://www.tpex.org.tw/openapi/swagger.json`（OpenAPI 目錄，用來找端點，不猜網址） | 22:58:25，HTTP 200，`application/json`，476,923 bytes；`servers` = `https://www.tpex.org.tw/openapi/v1`，225 個路徑 |
| 3 | `GET https://www.tpex.org.tw/openapi/v1/tpex_reward_index`（目錄中的「櫃買指數與報酬指數之收市指數」） | 22:58:46，HTTP 200，`application/json`，1,389 bytes |

- 目錄中和指數相關的端點有 21 個：`tpex_index`（櫃買指數歷史：Date、Open、High、Low、Close、Change）、`tpex_reward_index`、`tpex50_index`、`tphd_index`、`tpcgi_reward_index` 等主題指數。
- **目錄中沒有上櫃類股指數的端點**。含「類股」字樣的只有外資持股比例、成交價量比重、營收、EPS，不是指數。
- `tpex_reward_index` 的內容：
  - 19 筆，欄位 `Date`（民國 `1151102`）、`TPExIndex`（櫃買指數）、`TPExTotalReturnIndex`（**櫃買報酬指數**），全部字串。
  - 範圍 1151102～1151126，只有**本月**；沒有日期參數，不能查歷史。
  - 例：1151126 櫃買 289.84、報酬 539.21。
- 結論（寫進 F51-延伸a）：
  - 櫃買報酬指數可以每天收（1 次請求／天，回應帶當月全部日子，晚一點收也補得到當月）。
  - 歷史回補要另找來源（例如櫃買網站的月查詢頁，本輪沒有發請求）。
  - 上櫃類股指數在 OpenAPI 找不到。

## 七、原型實測紀錄

### 7-1 副本 export（`sa51e/`，假資料注入）

- `twse_index` 注入 9,918 列假資料：
  - 2025-10-30 用 6-1 的真實回應，2026-11-03 用 `logs/` 樣本，兩天都是真值。
  - 其他 259 天：類股 = 11/03 收盤 × 加權比例；報酬指數 = 加權 × 兩端比值的線性插值。
  - **以下數字只用來驗證程式路徑，不是實際值。**
- 匯出 35.9 秒，0 外部請求、0 寫入。訊息：
  ```
    📌 ETF 個股 368 檔，5.0 MB（etfp/，原始價）
    📌 證交所指數 2026-11-26：類股 32 類；加權報酬指數 261／261 天
  ```
- 和專案現有 `site/data` 比：
  - 只多 `ixr.json`（5,839 bytes，≤ 8 KB）。
  - `latest.json` 只多 `sx`、`ixr` 兩鍵，順序在 `nx` 之後；另有 `status.exported_at` 不同。大小 816,967 → 818,587 bytes（**+1,620**）。
  - 其他檔逐 byte 相同。
- `latest.ixr.pf` 的基準日 = 2330 `pf`：5 日 2026-11-19、20 日 2026-10-29、60 日 2026-08-27、120 日 2026-06-02、今年以來 2025-12-31、52 週 2025-11-26。`sx.b5`／`b20` = 2026-11-19／2026-10-29。
- 比較頁 2330,0050 52 週：含息線 +45.18% = `ixr.pf` 52 週 +45.18%（同一組基準日）。
- 匯出後 `test_iter01～51` 全過，`test_iter51.test_site_data` 有實際執行。

### 7-2 畫面（8001，副本資料；驗收 37 的部分項目）

| 頁面 | 寬度 | 結果 |
|---|---|---|
| `#/today/flow` | 1024 | 類股表 10 列＋「顯示全部」；表寬 958；`scrollWidth = innerWidth`；點「顯示全部」→ 32 列、鈕變「只顯示前 10」；點「漲跌」→ `漲跌 ▲`；localStorage 只有既有的 `tw.todayTab` |
| 同上 | 375 | 表格 339 px、`.tbl-wrap` 309 px → **表格內橫捲**（20 日欄要捲才看得到）；整頁 `scrollWidth` 375 = `innerWidth`；標題列 34 px（鈕同一行） |
| 同上 | 320 | 表格 339、`.tbl-wrap` 254 → 表格內橫捲；整頁 320 = `innerWidth`；標題列 67 px（鈕換到下一行） |
| `#/compare/2330,0050/w` | 1024 深色 | 點線看得出來，和灰虛線分得開；表格多一列；十字線 `加權 +42.84% 含息 +45.18%`；說明句出現；整頁沒有溢出 |
| `#/compare/2330,0050/20` | 1024 淺色 | 點線看得出來、和虛線分得開 |
| `#/stock/2330`、`#/stock/0050` | 1024 | 追加行出現：`加權報酬指數（含息）同期：5 日 +1.92%、20 日 -15.45%、60 日 -14.50%、120 日 -13.36%、今年以來 +37.17%、52 週 +45.18%`（假資料） |
| `#/stock/6488`（上櫃） | 1024 | 沒有追加行 |
| 主控台 | — | 0 錯誤 |

- 375 寬時表格內需要橫捲 → **D204**。
- 其餘寬度與深淺色組合留給 QA。

### 7-3 原型中確認的 PM 疑慮

- 官方順序：不依 `id`，改存 `seq`（第五節差異 1）。
- 新表錯誤攔截：4 種例外都只印 ⚠️，`written`、`errors` 不變（`test_errors`）。
- 假世界多印 ⚠️：見第四節。

## 八、PG 階段

### 8-1 套用

1. `git apply docs/iterations/51/03-design.diff`。
2. `shasum site/app.js site/stock.js site/compare.js` 前 8 碼應為 `a837955f`、`e41e8ece`、`f7e0bca5`（和 `index.html` 相同）。
3. `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done` 沒有輸出（這時 `test_iter51` 會印「尚未用第 51 輪匯出或尚未回補，略過實際資料」）。
4. 套用到 `setup-db` 之間若剛好遇到排程，收集會印一行 `⚠️  twse_index 寫入失敗（請確認已執行 setup-db）`，個股與加權照常寫入。所以套用後要盡快進行 8-2。

### 8-2 上線步驟（**每一步寫 DB 前停下，向使用者說明並取得同意**，D192）

| 步驟 | 指令 | 寫 DB | 說明 |
|---|---|---|---|
| 0 | `pgrep -fl twstock` | 否 | 確認沒有收集在跑；避開週一至週五 17:30、19:30、21:45、22:30 前後 20 分鐘；回補約 17.4 分鐘 |
| 1 | `python3 -u -m twstock backup` | 否（備份） | COPY_ONLY＋RESTORE VERIFYONLY；記下檔名、大小、驗證結果 |
| 2 | TAIEX 快照（唯讀，下方程式） | 否 | 存 scratchpad：261 筆（日期、收盤、漲跌） |
| 3 | `python3 -u -m twstock setup-db` | **是，要同意** | 建 `twse_index`；訊息含 `twse_index（第 51 輪）` |
| 4 | `python3 -u -m twstock history --start 2025-10-30 --end 2026-11-26 --only index --force 2>&1 \| tee logs/backfill_twse_index_51.log` | **是，要同意** | 預期開頭 `📊 交易日 261 天，待抓 261 天；⏱️  預估約 17.4 分鐘`、`   index.TAIEX：261 天`；記錄 `request_count` 差（或從 log 數 `📅`） |
| 5 | 唯讀核對（下方程式） | 否 | 驗收 33、34；D203 比對結果寫 `04-dev.md` |
| 6 | `python3 -u -m twstock export` | 否（寫 `site/data`） | 0 外部請求；預期 `📌 證交所指數 2026-11-26：類股 32 類；加權報酬指數 261／261 天`、沒有「類股名稱對不到」 |
| 7 | 全部測試再跑一次 | 否 | `test_iter51.test_site_data` 會實際核對 |

- 中斷接續（R83、D202）：畫面會印 `❌ 在 YYYY-MM-DD 停止` 與 `這次有 --force：重跑會從頭重抓，請改用 --start YYYY-MM-DD 接續。`。先回報使用者實際請求數與停下日期，再決定何時用 `--start <停下那天> --end 2026-11-26 --only index --force` 接續。
- 步驟 2 快照：
  ```python
  # scratchpad/pg51/snap.py（唯讀）
  import csv, sys; sys.path.insert(0, "<專案根目錄>")
  from twstock.db import connect
  c = connect(); rows = c.cursor().execute("SELECT trade_date, close_price, change FROM market_index WHERE index_code='TAIEX' ORDER BY trade_date").fetchall(); c.close()
  csv.writer(open(sys.argv[1], "w", newline="")).writerows([(str(d), str(p), str(ch)) for d, p, ch in rows]); print(len(rows))
  ```
- 步驟 5 核對（唯讀 SELECT）：
  - `SELECT trade_date, kind, COUNT(*) FROM twse_index GROUP BY trade_date, kind`：每天 P、R 列數的最小、最大值（預期 56／47）。
  - `kind='R' AND index_name=N'發行量加權股價報酬指數'` 的天數（預期 261）。
  - 每天「類指數」結尾的 P 列數（預期 37，去掉 5 個合併類後是 32）。
  - `market_index` TAIEX 和快照逐筆比對，列出不同的筆數、日期、新舊值（D203）。
  - 2025-10-30 的 R 應為 64,273.28（第六節）；2026-11-03 應為 100,144.27。

## 九、需要使用者決定的事項（新 D 從 D204 起）

### D204 類股指數表在 375 寬時，「20 日」欄要在表格內橫捲才看得到

- 現況：PM A-5 允許只在 `.tbl-wrap` 內橫捲，整頁不溢出，已符合。但 375 寬時表格 339 px、可見 309 px，最右邊的「20 日」欄只露出一半。
- **A（預設）**：照 PM，不改 `app.css`（`app.css?v=` 鎖保留，舊測試 0 行）。
- B：`app.css` 加 1 行，在 ≤ 400 寬縮小 `.sx` 表格的左右內距（例 `@media (max-width:400px){.sx .tbl th,.sx .tbl td{padding-left:4px;padding-right:4px}}`，數值要 PG／QA 實量）。`app.css?v=` 會變；`test_iter50.py:376` 已在 D200 同意範圍內（「改 `app.css` 時也拿掉」），另要確認 `test_iter49`～`50` 以外沒有 `app.css` 版本鎖。
- 預設 A 的理由：橫捲已經在規格允許範圍內，手機上點表頭排序的效果仍看得到；B 要再實量、多一個檔的版本變動。上線後若使用者覺得不方便再做。

## 十、疑慮

- 類股的 5／20 日與含息線數字目前是假資料。實際值要等 PG 回補、匯出後，由驗收 35、36 與 `test_site_data` 核對。
- 櫃買報酬指數 OpenAPI 只有當月：要做上櫃含息行，得先從現在開始每天收，或另找歷史來源（F51-延伸a）。
- 回補會用官方值覆寫 261 天加權指數（D203 = A）；有差異時 `ix.json`、近期表現、選股 `rs20`／`rs60` 會小幅變動。
- `docs/iterations/README.md` 第 51 輪那一行只寫到設計，PG／QA 之後補。
- 預覽時把瀏覽器分頁的配色模擬切成淺色，看比較頁淺色模式；結束時視窗已設回 desktop，配色模擬會在 app 切換主題時重新同步。

## 使用者決定（2026-11-26）

- D204：A。不改 `app.css`，375 寬時類股表在表格內橫向捲動。
- SA 與 PM 的 13 點差異全部接受。
