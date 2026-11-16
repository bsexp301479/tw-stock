# 第 29 輪｜System Analyst：設計

- 撰寫日期：2026-11-16（週一）深夜～11-17
- 依據：
  - `29/01-analyst.md`、`29/02-pm.md`（D38 = A、兩階段、驗收 15 條、D39-1～5）。
  - 使用者回覆「照建議，進 SA」。
  - 現行程式：`site/stock.js`（`buildChip`、`renderStock` 籌碼分頁）、`twstock/collectors/daily.py`、`db.py`、`health.py`、`history.py`、`__main__.py`、`export.py`。
  - 舊測試：`tests/test_iter01`～`28`；第 11 輪加借券的做法（`11/03-design.md` 第 9-2 節）。
- 守則：
  - **外部請求 3 次**：證交所 1、櫃買 2，都經過 `fetch.request(..., isolated=True)`，不重試。PM 上限 3 次。
  - **資料庫 0 次寫入**，只有唯讀 SELECT。
  - 沒有動 `.env`：副本不含 `.env`，也沒有讀出帳密。
  - 沒有動 `_archive/`；沒有執行 `collect`、`history`、`setup-db`、`backup`、`export`。
  - 專案工作目錄的程式**沒有改**；原型都在 scratchpad `r29/`。對專案只做過 `patch --dry-run`。
  - 8001 測完已關閉，沒有碰 8000。瀏覽器已恢復桌面大小與淺色；8001 的 localStorage 已清空，預覽時新增的是 `tw.stockTab`。
- 產出：

  | 檔案 | 內容 |
  |---|---|
  | `docs/iterations/29/03-design-A.diff` | **附錄 A：階段一**（F29-1～3），284 行，相對目前專案 |
  | `docs/iterations/29/03-design-B.diff` | **附錄 B：階段二**（F29-4），749 行，相對「套用 A 之後」 |
  | `logs/iter29_probe_twse.json`、`iter29_probe_tpex.json`、`iter29_probe_tpex_hist.json` | 3 次實測的原始回應（`logs/` 在 `.gitignore` 中） |

---

## 一、結論

1. **階段一（F29-1～3）**：
   - 改動只在 `site/`：程式 +28／−14。
   - 加 `test_iter29`（階段一部分）。
   - 改 `test_iter28` 的 16 行（D39-1）。
   - 原型在 2421、0050 的 375、1024 寬，深淺色都正常。
2. **階段二（F29-4）**：
   - 來源實測**兩個市場都可用**。
   - 櫃買已確認可以查歷史（2025-10-30 有資料）。
   - 證交所 `MI_QFIIS` 依日期查詢，**歷史日期沒有實測**（請求數已用完）。PG 回補前先試補 1 天確認。
   - 程式 +116／−14，加在 `daily.py`、`db.py`、`health.py`、`history.py`、`__main__.py`、`export.py`、`stock.js`、README。
   - 要改 `test_iter03` 的共用模擬環境：+22／−4，比照第 11 輪，也是 D39-1。
3. **兩階段都在完整副本上驗證過**：
   - 套用後 `test_iter01`～`29` **29 個全部通過**。
   - 反證：舊程式＋新測試會失敗。
4. **D39-4 定案**：照畫每日柱。375 寬時「全部」約 255 根柱仍看得到，不改週合計。
5. **需要使用者同意（D39-1）**：
   - `test_iter28` 16 行（階段一）。
   - `test_iter03` 4 處（階段二）。
   - 見第五節。

---

## 二、階段一：法人圖（F29-1～3）

### 2-1 畫面

籌碼分頁「法人買賣超」組，由上到下：

1. 卡片：法人1日、法人5日、外資5日、投信5日。不變。
2. 收盤小面板（`cpC`，64 px）。不變。
3. **法人切換**（新，`#chipInv`）：外資／投信／自營／合計。
   - 預設外資。
   - `let chipI = 'f'`，只在這次瀏覽記住，不存 localStorage（和 `chipN` 相同）。
4. **每日買賣超柱**（`ciC`，120 px）：
   - 標題「每日買賣超（張，未還原）」。
   - 柱色用 `--up`／`--dn`：買超紅、賣超綠，跟著深淺色。
   - 0 軸虛線。
   - 圖例「外資 −207」。
5. **區間累計小面板**（新，`cuC`，72 px）：
   - 細線，顏色是 `--text2`，比柱子淡。
   - 標題「區間累計（張，自 10/16 起加總）」，起算日隨區間更新。跨年時寫年份，例如「自 2025/10/30 起加總」。
   - 圖例「累計 −3,153」。
6. **讀法說明**（新）：「累計線的高度取決於起算日，看斜率不看高度；最近每天的買賣看上方柱狀圖。」
7. 區間切換 `#chipSeg`：預設由 60 日改成 **20 日**（F29-3），選項不變。

### 2-2 共用行為

- 十字線：收盤、每日柱、累計、融資、借券五張圖同步。
- 圖例：最新一天法人還沒有時，顯示最近有資料的那天，並寫日期（同第 28 輪）。
- 切換法人或區間：`buildChip` 重畫，`disposeKCharts` 先釋放舊圖（同第 28 輪）。
- `onSeg('chipInv', …)` 和 `chipSeg` 一樣，每次 `renderStock` 對新產生的元素綁一次，不會累加。

### 2-3 為什麼這樣設計

- **不用雙 Y 軸**：第 28 輪原則。柱和累計的量級差很多，放同一張圖不是壓扁柱，就是要第二個 Y 軸。所以累計放獨立小面板。
- **一次一種法人**：三種法人的柱疊在一起會太亂。PM D39-3 預設外資。
- **合計**：用個股 JSON 的 `insti.n`（第 24 輪官方合計）；舊 JSON 沒有 `n` 時三者相加（`aggregate` 原本的寫法）。

### 2-4 原型驗證（8001，`r29/proj/site`＋真實 `site/data`）

| 項目 | 結果 |
|---|---|
| 2421，1024 深色，20 日 | 柱、累計、切換都顯示；外資 20 日累計 −3,153（和分析師相同）；起算日 10/16 |
| 2421，375 深色，全部 | 柱很細但看得到 2026 年初、8 月底的大買；起算日「2025/10/30」（修正前只寫「10/30」）；`scrollWidth = 375` |
| 2421，375 淺色，切「合計」 | 圖例「合計 −236」、累計 −3,533；`scrollWidth = 375` |
| 0050（ETF），375 | 沒有法人組與切換，只有融資、借券兩張圖 |
| 主控台 | 0 個錯誤 |

### 2-5 改動（附錄 A：`03-design-A.diff`）

| 檔案 | ＋／− | 內容 |
|---|---|---|
| `site/stock.js` | ＋24／−11 | 新增 `CHIP_I`、`chipI`；`chipN = '20'`；法人組 HTML（切換、兩個圖、說明）；`onSeg('chipInv')`；`buildChip` 法人段改成柱＋累計 |
| `site/app.css` | ＋1／−1 | `.chip-inv{margin:8px 0 0}` |
| `site/index.html` | ＋2／−2 | `app.css?v=d654f1a6`、`stock.js?v=01859664` |
| `README.md` | ＋1／−1 | 「個股法人」一段加第 29 輪說明 |
| `tests/test_iter28.py` | ＋16／−16 | 見第五節（D39-1） |
| `tests/test_iter29.py`（新） | 70 行 | 階段一的 3 個測試 |

- 不需要 `export`：個股 JSON 已有 `insti.f／t／dl／n`。

---

## 三、階段二：外資及陸資持股（F29-4）

### 3-1 來源實測（3 次請求，2026-11-16 23 點左右）

| # | 請求 | 結果 |
|---|---|---|
| 1 | `GET https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20261116&selectType=ALLBUT0999&response=json` | `stat: OK`、`date: 20261116`、1,373 列，**含 ETF**；欄位 12 個；單位股；比率是數字（例 36.16） |
| 2 | `POST https://www.tpex.org.tw/www/zh-tw/insti/qfii`，`date=2026/11/16&response=json` | `stat: ok`、`date: 20261116`、`tables[0]` 899 列；第 0 欄是排行、第 1 欄是代號；比率是字串（例 `87.85%`）；注記「本表資料每日於18:00及22:00更新」 |
| 3 | 同 2，`date=2025/10/30` | 861 列、`date: 20251030`，**櫃買可以查歷史** |

- 涵蓋率：11/16 有行情的 1,988 檔股票**全部**在兩個來源中。
  - 上市沒對到的 280 列都是 ETF 等非股票。
  - 上櫃只有 `8349A`（特別股）沒對到。
- 證交所歷史：沒有實測（請求數上限）。
  - 證交所 `rwd` 報表都以 `date` 查歷史，預期可以。
  - **PG 回補前先試補 1 天（2 次請求）確認**；若證交所不能查歷史，上市只從上線日開始累積（PM 風險 3 已接受）。
- 欄位對照（`QFII_POS`，位置 → 欄名；不符就 `SchemaError`）：

  | 存入欄位 | 上市欄位（位置） | 上櫃欄位（位置） |
  |---|---|---|
  | 代號 | 證券代號（0） | 代號（1） |
  | `issued` 發行股數 | 發行股數（3） | 發行股數(A)（3） |
  | `fh_shares` 持有股數 | 全體外資及陸資持有股數（5） | 僑外資及陸資持有股數(C)（5） |
  | `avail_ratio` 尚可投資比率 | 外資及陸資尚可投資比率（6） | 僑外資及陸資尚可投資比率(D=B/A)（6） |
  | `fh_ratio` 持股比率 | 全體外資及陸資持股比率（7） | 僑外資及陸資持股比率(E=C/A)（7） |
  | `limit_ratio` 投資上限 | 外資及陸資共用法令投資上限比率（8） | 法令投資上限比率(F)（8） |

### 3-2 資料表 `foreign_holdings`（`db.py` 的 `DDL`，`setup-db` 建立）

```sql
IF OBJECT_ID('foreign_holdings') IS NULL
CREATE TABLE foreign_holdings (
    id           BIGINT IDENTITY(1,1) PRIMARY KEY,
    stock_id     INT           NOT NULL REFERENCES stocks(stock_id),
    trade_date   DATE          NOT NULL,
    issued       BIGINT        NULL,      -- 發行股數
    fh_shares    BIGINT        NULL,      -- 外資及陸資持有股數
    fh_ratio     DECIMAL(6,2)  NOT NULL,  -- 外資及陸資持股比率 %
    avail_ratio  DECIMAL(6,2)  NULL,      -- 尚可投資比率 %
    limit_ratio  DECIMAL(6,2)  NULL,      -- 法令投資上限比率 %
    created_at   DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_foreign_holdings UNIQUE (stock_id, trade_date)
)
-- 索引 IX_foreign_holdings_date ON foreign_holdings(trade_date)
```

- 只新增表，不改既有表。`setup-db` 可重複執行。
- 完成訊息加 `foreign_holdings（第 29 輪）`，放在 `etf_holding_gaps` 前面，因為 `test_iter06` 斷言結尾。
- 大小：約 2,000 檔 × 253 天 ≈ 50 萬列。

### 3-3 收集（`daily.py`）

- 資料集 `QFII = "qfii"`：
  - `DATASET_KEYS["qfii"] = ("qfii.TWSE", "qfii.TPEx")`。
  - **不在 `ALL_DATASETS`**：`history` 不指定 `--only` 時不補，同借券。
- `DAY_KEYS`：插在 `sbl.TPEx` 之後、`breadth.TWSE` 之前。
  - 每晚多 2 次請求。
  - 排在證交所其他請求之後：萬一證交所連續失敗、主機被標記，只影響後面的 `breadth.TWSE`。`breadth.TWSE` 用快取的 `MI_INDEX`，不發請求。
- `parse_qfii(data, d, market)`：
  - `stat` 不是 OK、回應日期不是 `d`、沒有資料列 → `[]`，算「尚未公布」，不是錯誤。
  - 欄位不符 → `SchemaError`，只影響這個鍵。
  - 比率去掉 `%`。
- `_collect_key`：
  - 只留 `is_valid_stock_code` 的代號（ETF、特別股略過）。
  - `merge_qfii` 用 MERGE 寫入 `stocks` 已有的股票；同一天重抓就覆寫。
  - 回傳股票檔數，0 = 尚未公布。
- 同市場行情還沒有時不發請求（加進 `collect_for_date` 的保護清單）。
- 容錯：沿用 `collect_for_date`。這個鍵失敗只記警告、進 `errors`，其他資料照常寫入，有新資料就照常匯出。
  - `collect_runs` 的 `outcome` 照第 24 輪規則：有錯誤就是 `abnormal`。
- 公布時間：`check` 用統一的 22:00 分界（之前沒有資料算「尚未公布」，之後算異常）。

### 3-4 `check`、`history`、指令

- `health.SPECS` 加兩行：
  - `Spec("qfii.TWSE", "上市外資持股", 800, False)`。
  - `Spec("qfii.TPEx", "上櫃外資持股", 650, False)`。
  - 11/16 實際股票檔數：1,093、898。
- `_MARKET_SQL["qfii"]`：計數查 `foreign_holdings`。
- `history.SECONDS_PER_KEY`：`qfii.TWSE` 4 秒、`qfii.TPEx` 3.2 秒。
  - 回補 253 天約 **506 次請求、約 30 分鐘**。
- `__main__.py`：
  - `--only` 加 `qfii`，放在 `margin` 前面。選項順序沒有意義，這樣 `test_iter05`、`test_iter11` 的字串斷言不用改。
  - 說明與範例加一行。

### 3-5 匯出（`export.py`）

- `_load_qfii(cur)` → `{代號: {日期: 持股比率}}`。
- 個股 JSON 加 `fh`：和 `prices.d` 對齊的比率陣列，沒有資料為 `null`。沒有任何資料的股票不輸出這個鍵。
- 估計：回補後每檔約 +1.5 KB，`site/data/stocks` 合計約 +3 MB；`export` 時間 +1～2 秒（一個 SELECT）。
- `latest.json`、`screen.json` 不變。

### 3-6 畫面（`stock.js`）

- 法人組卡片加第 5 張「外資持股比率」：
  - 數值：最近有資料那天的比率 `36.10%`。
  - 副行：`5日 +0.28　20日 +0.81（百分點）`。
  - 資料日不是法人資料日時，第二行寫日期。
  - 沒有 `fh` 的股票（含 ETF）不顯示。
- 讀法說明下方加「外資及陸資持股比率（%，以當日發行股數為分母，增資、減資時會跳動）」小面板（`fhC`，90 px）：
  - 一條線，獨立 Y 軸，不用雙 Y 軸。
  - 和其他圖十字線同步。
  - 圖例「外資持股 36.10%」。
- 用假資料預覽：
  - 只在 8001 預覽伺服器的記憶體裡給 2421 加 120 天假序列，不寫檔。
  - 1024 淺色、375 深色正常，`scrollWidth = 375`。
  - 375 寬時卡片變成 2 欄 3 列，第 5 張的「（百分點）」會換行。
- 真實資料的預覽留給 PG 回補後做。

### 3-7 改動（附錄 B：`03-design-B.diff`，套在 A 之後）

| 檔案 | ＋／− |
|---|---|
| `twstock/collectors/daily.py` | ＋67／−5 |
| `twstock/db.py` | ＋19／−1 |
| `twstock/health.py` | ＋2 |
| `twstock/collectors/history.py` | ＋1／−1 |
| `twstock/__main__.py` | ＋3／−2 |
| `twstock/export.py` | ＋8 |
| `site/stock.js` | ＋12／−2 |
| `site/index.html` | ＋1／−1（`stock.js?v=c99579fb`） |
| `README.md` | ＋3／−1（新資料表、`history` 範例、資料說明一段） |
| `tests/test_iter03.py` | ＋22／−4（第五節，D39-1） |
| `tests/test_iter29.py` | ＋94／−1（加階段二的 7 個測試） |
| `tests/fixtures/mi_qfiis_20261116_mini.json`、`insti_qfii_20261116_mini.json`（新） | 實測回應的精簡版：上市 6 列（含 0050、00400A）、上櫃 4 列（含 8349A） |

- 程式＋README 兩階段合計約 **＋144／−28**（PM 估約 200、上限 270）。
- 測試：`test_iter29` 164 行；舊測試 `test_iter28` 16 行、`test_iter03` ＋22／−4。

---

## 四、風險與限制

1. **櫃買 22:00 第二次更新不重抓**：
   - 排程 17:30、19:30、21:45 收到的是 18:00 版，22:30 那次已經有資料就不會再抓。
   - 18:00 版和 22:00 版差多少不知道。比照第 11 輪借券「22:30 第二版不重抓」，先接受並寫進 README。
   - 若上線後發現差異大，再加「22:00 前寫入的上櫃資料，隔天重抓」（約 10 行）。
2. **證交所歷史未實測**：PG 回補前先試 1 天。
3. **證交所主機標記**：外資持股若連續失敗、證交所被標記為失敗主機，同一次執行後面的證交所請求不會再發（`fetch` 原本的保護）。外資持股排在證交所請求的最後，所以影響最小。
4. **發行股數是官方申報值**：增資、減資前後比率會跳動，畫面已說明。
5. **時機**：PG 改 `collectors/` 要等使用者回報 11/19 第 24 輪確認正常（PM 第一節）。

---

## 五、需要使用者同意：D39-1 舊測試的修改

### 階段一：`tests/test_iter28.py`（16 行，改前 → 改後）

| 行 | 改前 | 改後 | 原因 |
|---|---|---|---|
| 46 | `let chipN = '60';` | `let chipN = '20';` | F29-3 預設 20 日（「不新增 localStorage 鍵」保留） |
| 48 | 圖標題 `區間累計買賣超（張，未還原；從區間第一天起加總）`, `'ciC', 150` | `每日買賣超（張，未還原）`, `'ciC', 120` | F29-1 主圖改每日柱 |
| 58 | 取出的函式 | 多取 `CHIP_I` | `buildChip` 用到 |
| 59 | `chipN = 'all'` | 加 `chipI = 'f'` | 同上 |
| 63 | 模擬圖表只有 `addLineSeries` | 加 `addHistogramSeries` | 主圖改柱狀 |
| 71 | 圖的代號 cp／ci／cm／cl | 加 `cu`（累計小面板） | 多一張圖 |
| 73～74 | `cum` 取 `ci` 的三條線 | 取 `ci` 的柱、`cu` 的線；多存 `cuCL` 圖例 | 同上 |
| 76 | 十字線檢查第 3 張是融資（`created[2]`） | `created[3]` | 多一張圖，順序後移 |
| 79 | 切 2 日後看 `ci` 的累計 | 看 `cu` 的累計 | 同上 |
| 86～87 | 4 張圖；三條累計 `[[10,-10,20,25,null],[1,2,3,4,null],[0,0,0,-2,null]]` | 5 張圖；柱 `[10,-20,30,5,null]`、累計 `[10,-10,20,25,null]` | 外資的每日柱與累計（數字同一組資料） |
| 90～91 | 圖例「外資 +25（當日 +5）」「自營 -2」 | 「外資 +5」「累計 +25」 | 圖例改成每日為主、累計在小面板 |
| 96 | 滑鼠移到第 2 天：「外資 -10（當日 -20）」 | 「外資 -20」 | 同上 |
| 98 | 切 2 日：「外資 +5」 | 「累計 +5」 | 同上 |

- 保留不改的斷言：
  - `CHIP_N` 選項、不新增 localStorage 鍵。
  - 卡片、信用與借券組、`disposeStockCharts`、CSS。
  - 0 軸、融資與借券的數值與圖例、十字線同步、ETF 只有兩張圖。
  - 用詞檢查。
- 新行為（切換法人、合計、起算日跨年）另由 `test_iter29` 測。

### 階段二：`tests/test_iter03.py`（共用的模擬環境 `World`，＋22／−4）

比照第 11 輪加借券時的做法：

1. `_full_snapshot`：加 `qfii.TWSE` Row(1093)、`qfii.TPEx` Row(898)（第 107 行）。
2. `ALL_EP`：加 `MI_QFIIS`、`insti/qfii`（第 366～368 行）。
3. `World.http`：兩個端點導到新的 `_qfii`（第 422～425 行）。
4. 新方法 `_qfii`：
   - 回應上市、上櫃格式。
   - 列是全部股票＋ETF＋其他證券。
   - 未公布時沒有資料列（第 546～561 行）。
5. `apply_merge` 認得 `foreign_holdings`（第 620、622 行）。

- 沒有這些修改，`test_iter03／04／05／07／09／10` 會因為 `KeyError 'qfii.TWSE'` 或沒有路由而失敗。
- **不需要改**：
  - `test_iter05`、`test_iter11` 的 `--only` 字串斷言：`qfii` 放在 `margin` 前面。
  - `test_iter06` 的 `setup-db` 訊息斷言：`foreign_holdings` 放在 `etf_holding_gaps` 前面。

---

## 六、新測試 `tests/test_iter29.py`（不連網、不連資料庫）

| 測試 | 階段 | 內容 |
|---|---|---|
| `test_chip_source` | 一 | 預設 20 日、`CHIP_I`、`chipI = 'f'`、不新增 localStorage 鍵、切換與兩個圖的標題、讀法說明、CSS |
| `test_chip_bars_node` | 一 | node 執行 `buildChip`：柱值與顏色（`--up`／`--dn`）、累計、起算日跨年寫年份、合計用官方 `n`、投信、近 2／3 日區間 |
| `test_no_advice_words` | 一（二擴充） | `CHIP_I`、`buildChip`、卡片段落沒有建議性字眼 |
| `test_fh_chart_node` | 二 | 有 `fh` 時多一張 `fhC`、缺值不補、圖例 `31.20%` |
| `test_parse_twse`、`test_parse_tpex` | 二 | fixture 解析的完整值（2421、6488）、含 ETF 由呼叫端分流、日期不符與沒有資料列 = `[]`、欄位不符 = `SchemaError` |
| `test_keys_and_ddl` | 二 | DDL、資料集鍵、`DAY_KEYS` 順序、`SPEC` 門檻、`_MARKET_SQL`、`SECONDS_PER_KEY`、`--only qfii` |
| `test_collect` | 二 | `World` 模擬：只寫股票、各 1 次請求；行情 0 列時不發請求；尚未公布 = 0 筆、不是錯誤 |
| `test_export_source` | 二 | `_load_qfii`（假 cursor）、個股 JSON 的 `fh` 寫法 |
| `test_fh_card_source` | 二 | 卡片、圖標題、`data.fh && $('#fhC')` |

- 反證：
  - 舊 `stock.js` 套階段一測試 → 失敗。
  - 只套階段一的程式、跑階段二測試 → 失敗：沒有 `fhC`。

---

## 七、PG 步驟

### 階段一（現在可以做）

1. 基線：
   - 記錄 `collect_runs` 最大 `run_id`。
   - 把 `site/stock.js`、`app.css`、`index.html`、`tests/test_iter28.py`、`README.md` 複製到 `logs/iter29_before/`。
2. **確認使用者已同意 D39-1**（`test_iter28` 那 16 行）。
3. `patch -p1 --dry-run < docs/iterations/29/03-design-A.diff`，通過後正式套用。
4. `node --check site/stock.js`；`test_iter01`～`29` 全部通過。
5. 8001 預覽，用真實資料：
   - 2421 和另外 3 檔（PM 驗收 #1：累計與近期同向一檔、投信主導一檔、上櫃一檔）。
   - 四種法人、四種區間。
   - 375、1024，深淺色。
   - 0050。
   - 主控台 0 錯誤。
   - 預覽完清除新增的 localStorage 鍵。
6. 不需要 `export`。

### 階段二（**使用者回報 11/19 第 24 輪確認正常之後**）

1. 確認沒有收集在跑：`collect_runs` 沒有未完成的列，並問使用者。
2. **`python -m twstock backup`**（比照第 10、11、19 輪）。
3. **確認使用者已同意 D39-1**（`test_iter03` 4 處）。
4. 套用 `03-design-B.diff`（先 `--dry-run`）；`test_iter01`～`29` 全部通過。
5. `python -m twstock setup-db`：只新增 `foreign_holdings` 與索引。
6. 試補：

   ```bash
   python3 -u -m twstock history --start 2025-10-30 --end 2025-10-30 --only qfii
   ```

   - 2 次請求。
   - 確認上市、上櫃都有寫入，檔數合理。
   - 上市失敗或 0 筆時停下來回報，**不要**用 `--force` 或其他參數硬補。
7. 回補（D39-2 從 2025-10-30 起；D39-5 經使用者同意後由 PG 執行）：

   ```bash
   python3 -u -m twstock history --start 2025-10-30 --only qfii
   ```

   - 約 506 次請求、30 分鐘，放背景執行。
   - 記錄請求數。
8. `python -m twstock check`：外資持股兩行沒有缺口。
9. `export`：
   - 先用 `logs/iter29_before/` 的程式另外匯出一份基線，再用新程式匯出。
   - 比對：刪掉 `fh` 後 `stocks/` 和改前逐值相同；`latest.json`、`screen.json`、`etfp/`、`etfs/` 相同（PM 驗收 #11）。
   - 記錄匯出時間（PM 驗收 #15）。
10. 8001 用真實資料預覽卡片與持股比率圖。
11. 上市、上櫃各 3 檔和官方網頁人工核對（PM 驗收 #7）。

---

## 八、QA 清單與 SQL

```sql
-- 驗收 #10：每日檔數（上市約 1,090、上櫃約 900；和當日行情檔數相近）
SELECT x.trade_date, s.market_type, COUNT(*) AS n
FROM foreign_holdings x JOIN stocks s ON s.stock_id = x.stock_id
GROUP BY x.trade_date, s.market_type ORDER BY 1 DESC, 2;

-- 有行情、沒有外資持股的股票（應該只有新上市當天或官方沒列的）
SELECT d.trade_date, s.stock_code FROM daily_prices d JOIN stocks s ON s.stock_id = d.stock_id
WHERE d.trade_date = '2026-11-16' AND NOT EXISTS
  (SELECT 1 FROM foreign_holdings x WHERE x.stock_id = d.stock_id AND x.trade_date = d.trade_date);

-- 驗收 #7：比率 ≈ 持有 ÷ 發行（官方四捨五入或無條件捨去到 2 位，差距應 < 0.01）
SELECT TOP 20 s.stock_code, x.fh_ratio, CAST(x.fh_shares * 100.0 / x.issued AS DECIMAL(9,4)) AS calc
FROM foreign_holdings x JOIN stocks s ON s.stock_id = x.stock_id
WHERE x.trade_date = '2026-11-16' AND ABS(x.fh_ratio - x.fh_shares * 100.0 / x.issued) >= 0.01;

-- 驗收 #12：2421 卡片的 5 日、20 日變化（百分點）
SELECT TOP 21 x.trade_date, x.fh_ratio FROM foreign_holdings x JOIN stocks s ON s.stock_id = x.stock_id
WHERE s.stock_code = '2421' ORDER BY x.trade_date DESC;
```

- 階段一驗收 #1：個股 JSON 的 `insti.f／t／dl／n` 和柱的值逐日比對。用 8001 頁面的 `buildChip` 結果或 node 重算。

---

## 九、需要使用者決定

| # | 事項 | 狀態 |
|---|---|---|
| **D39-1** | 同意修改舊測試：`test_iter28` 16 行（階段一）、`test_iter03` 4 處（階段二），內容見第五節 | **待使用者回覆**；不同意則 F29-1、F29-3、F29-4 都無法上線 |
| D39-2 | 回補範圍 | PM 預設：從 2025-10-30 起（約 506 次請求） |
| D39-3 | 法人切換預設 | PM 預設：外資（已照做） |
| D39-4 | 120 日、全部的柱 | **SA 定案：照畫每日**（375 寬「全部」仍看得到） |
| D39-5 | 回補由誰執行 | PM 預設：PG 經使用者同意後執行 |

上線後觀察（不用現在決定）：

- 櫃買 22:00 前收集的外資持股和官方最終值是否不同（第四節風險 1）。
