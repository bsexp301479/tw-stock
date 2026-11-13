# 第 22 輪｜System Analyst：F22-10、F22-11、F22-1、F22-12 設計

- 撰寫日期：2026-11-14（週六）
- 依據：
  - `22/02-pm.md`：範圍、各項驗收條件、第六節提示、D33 預設。
  - `22/01-analyst.md`：Q22-1、F22-1、F21-延伸a／b 的情境。
  - 使用者決定：**D32 = A**；接受 PM 範圍（F22-10、F22-11、F22-1、F22-12）；**D33 全部照 PM 預設**：
    - D33-1：EPS 併入「營收」面向，畫面改稱「基本面」。
    - D33-2：年增門檻 ≥ 50%。
    - D33-3：窗口 20 個交易日。
    - D33-4：標籤放頁首。
    - D33-5：融券不列連續天數。
    - D33-6：MACD 用六種寫法。
- 原型作業：
  - 在 scratchpad 的 `sa22/` 建立兩份專案副本：
    - `orig` = 目前工作目錄（`9fc6136`，乾淨）。
    - `proj` = 本設計。
    - 兩份都**不含 `.env`**、`_archive`、`logs`、`.git`、`site/data`。
  - 唯讀模擬匯出：`orig`、`proj` 各執行一次 `export`，只執行 SELECT，輸出寫到各自的 `site/data`（scratchpad）。
    - **沒有寫專案的 `site/data`。**
    - 帳密由 `sa22/dbenv.py` 以 setdefault 讀專案 `.env` 到環境變數，沒有印出或複製 `.env`。
  - 8001 預覽 `sa22/proj/site`（`python3 -m http.server 8001 --bind 127.0.0.1`），結束時已關閉；8000 沒有碰。
    - 預覽前 localStorage 沒有任何鍵；預覽時新增的 `tw.stockTab` 已刪除。
    - 瀏覽器已恢復桌面大小。
  - **外部請求 0 次、資料庫寫入 0 次**。前後查 `collect_runs`：最大 17，沒有進行中的收集。
  - 沒有修改專案程式，沒有 commit。
- 基線：資料日 **2026-11-13（週五）**；季報 2026Q3 收到 1,859 家。

---

## 〇、變更總覽

| 檔案 | 內容 | ＋／− |
|---|---|---|
| `twstock/export.py` | `HL_EPS_YOY`、`HL_EPS_BASE`；`highlight_eps()`；`_load_financials` 多讀 `created_at`，多回傳收錄日；`fq_all`；`hl` 併入 EPS 事件 | ＋36／−7 |
| `site/app.js` | `HL_KINDS` 加 `et`、`eg`，營收面向改稱「基本面」；`hlTag` 加季別；說明句；`epsTurn`；選股條件「單季 EPS 轉盈」；結果欄 `eb` | ＋11／−5 |
| `site/stock.js` | `macdBar`；`runTxt`、`balStreak`；籌碼卡副行；頁首 `HL` 標籤 | ＋25／−5 |
| `site/app.css` | `.s-hl` | ＋1 |
| `README.md` | 4 段各加一句（個股法人、條件選股、近期新訊號、還原價／技術面） | ＋4／−4 |
| `tests/test_iter22.py`（新） | 9 個測試 | 223 行 |

- 程式＋README **＋77／−21**。PM 估約 70，上限 85。
- 不動：`collectors/`、`catchup.py`、`health.py`、`__main__.py`。
- 輸出：`screen.json`、`stocks/`、`etfp/`、`etfs/` 和改前**逐位元組相同**；`latest.json` 只有 `hl` 多出 `et`、`eg`。

---

## 一、F22-10（Q22-1）MACD 柱用詞

### 1-1 規則

`renderSignals` 的 MACD 柱那一項改用 `macdBar(昨, 今)` 產生文字。**歸類照舊**：`hist[今] > hist[昨]` 放偏多欄，否則放偏空欄。

| 昨 a → 今 b | 條件 | 文字 | 歸類（不變） |
|---|---|---|---|
| 相同 | `b === a` | MACD 柱持平 | 偏空（舊程式持平也是偏空） |
| 上升 | `a < 0 且 b > 0` | MACD 柱由負翻正 | 偏多 |
| 上升 | `b > 0`（含 a = 0） | MACD 正柱加長 | 偏多 |
| 上升 | 其他（b ≤ 0，含 b = 0） | MACD 負柱縮短 | 偏多 |
| 下降 | `a > 0 且 b < 0` | MACD 柱由正翻負 | 偏空 |
| 下降 | `b < 0`（含 a = 0） | MACD 負柱加長 | 偏空 |
| 下降 | 其他（b ≥ 0，含 b = 0） | MACD 正柱縮短 | 偏空 |

- 柱值剛好為 0：負 → 0 寫「負柱縮短」、正 → 0 寫「正柱縮短」；0 → 正寫「正柱加長」、0 → 負寫「負柱加長」。
- 持平只有價格完全不動時才會出現。11/13 全市場沒有。
- 日、週、月 K 共用 `renderSignals`，一起改。月 K 目前全部不足 35 根，沒有 MACD 這一項。

### 1-2 全市場前後對照（`sa22/macd_run.js`、`macd_cmp.py`，附錄 B）

- 方法：用 `orig`、`proj` 的 `stock.js` 原檔，在 node 執行 `aggregate(data, m, true)` 與 `renderSignals`，跑 `proj/site/data/stocks` 全部 1,999 檔的日、週、月 K。
- 結果：
  - **「偏多／偏空／中性：N 多 N 空」與每一項的歸類 0 差異**；MACD 柱以外的 5 項文字 0 差異。
  - 日線有 MACD 判讀 1,987 檔（另 12 檔不足 35 根），和 PM 完全相同：

    | 舊 → 新 | 檔數 |
    |---|---|
    | 柱放大 → **負柱縮短** | 1,239 |
    | 柱縮小 → **負柱加長** | 191 |
    | 柱放大 → 由負翻正 | 170 |
    | 柱放大 → 正柱加長 | 291 |
    | 柱縮小 → 由正翻負 | 24 |
    | 柱縮小 → 正柱縮短 | 72 |

  - 週線有 MACD 判讀 1,945 檔：負柱加長 921、負柱縮短 481、正柱縮短 210、正柱加長 192、由正翻負 94、由負翻正 47。
  - 實例（日線）：2421「偏空：1 多 5 空」，偏多欄是「MACD 負柱縮短」；1235 正柱加長、1416 正柱縮短、1102 負柱加長、1326 由負翻正、3147 由正翻負、2330 正柱加長。2421 週 K 是「MACD 負柱加長」。

---

## 二、F22-11（F21-延伸b）EPS 事件與選股「單季 EPS 轉盈」

### 2-1 事件定義（`highlight_eps`）

| 種類 | 條件 | 附加值 | 標籤 |
|---|---|---|---|
| `et` | 本季單季 EPS > 0，且去年同季 ≤ 0 | 季別 YYYYQQ | 「26Q3 EPS 轉盈」 |
| `eg` | `fin_yoy` ≥ 50（`HL_EPS_YOY`），且去年同季 ≥ 0.1 元（`HL_EPS_BASE`） | 季別 | 「26Q3 EPS 年增 ≥ 50%」 |

- 單季、年增用既有的 `fin_single`、`fin_yoy`，和季報卡、選股的 `eq`、`ey`、`eb` 同一套。
- 邊界：
  - 年增剛好 +50.0% 算（≥，和選股 `scrGe` 相同）。
  - 去年同季剛好 0.10 元**不算基期低**：前端 `epsLow` 是 `b < 0.1`。Python 用 `_f(base) >= 0.1` 比較，避免 `Decimal('0.10') < 0.1`（浮點 0.1 略大於 0.1）造成不一致。
- 四捨五入：EPS 是 `DECIMAL(10,2)`，累計相減後仍是精確的 2 位小數，`eq`、`eb` 的四捨五入不改變值。所以畫面用 `eq > 0 && eb ≤ 0` 判斷轉盈，和匯出端用未四捨五入的值判斷，結果相同。
- **只看全市場最新季別**：`fq_all = max(季報資料表全部的 (年, 季))`，目前是 2026Q3。
  - 該股沒有這一季（多為金融業，最新季還是 Q2）→ 不產生事件。
  - 不用 `fin_progress`：它在收集窗口外會回傳 None。
- 每檔股票最多 1 個 EPS 事件。轉盈的股票年增是 None，所以兩種事件互斥。

### 2-2 日期

1. 收錄日 = `first_seen`；`first_seen` 是 NULL（`history` 補抓）時改用 `created_at`。
   - `created_at` 是資料庫的 `GETDATE()`，**是 UTC**：本次查詢時 `GETDATE()` = 11/13 16:52，本機是 11/14 00:52。
   - 所以加 8 小時再取日期：`(created_at + timedelta(hours=8)).date()`。
2. **補抓防呆**：只對 `first_seen` 為 NULL 的列；收錄日晚於「該季金融業截止日」（`fin_due_dates()[-1]`，Q3 = 11/29）5 天以上時，改用截止日。
   - 只看 NULL：季報表有補抓標記（`first_seen` NULL）。日常收集到的晚申報公司是真的新資料，不壓回截止日。營收表沒有這個標記，所以第 21 輪對全部列套用。
   - 用金融業截止日：一般業、金融業取較晚的一天，只把明顯晚於所有業別期限的補抓視為補抓，1 行就能完成。
   - 目前資料：2026Q3 的 404 家補抓列 `created_at` 是 11/06，早於截止日，**照收錄日 11/06**（中鋼的轉盈因此成立）。2026Q1、Q2 的補抓列已經被「只看最新季別」排除，就算沒有排除，也會被壓回 5／8 月的截止日。
3. **對齊交易日**：取 `b_days`（`daily_prices` 的交易日，最後一天 = 資料日）中「≤ 收錄日」的最後一天。
   - `first_seen` = 11/14（週六，run 17 在午夜後執行）→ 11/13。
   - `b_days` 最後一天就是資料日，所以這一步同時做到「和資料日取較早」。
4. 窗口：對齊後的日期 ≥ `b_days[-20]`（`HL_REV_DAYS`，和營收相同）。11/13 的窗口從 10/15 起（資料庫實際的第 20 個交易日；測試用的週一～五曆是 10/19）。

### 2-3 匯出

- `latest.json` 的 `stocks[代號].hl` 多兩種：`["et", "2026-11-12", 202603]`、`["eg", "2026-11-13", 202603]`。
  - 串接順序：價量、法人 → 營收 → **EPS** → 主動 ETF，再依日期穩定排序。
  - 同一天時 EPS 排在營收之後，既有事件的相對順序不變。
- 事件代碼 `et`、`eg` 不和 `screen.json` 的 `eq`、`ey`、`eb`、`e4`、`eh` 撞名。選股條件 id 也用 `et`：同一個意思（轉盈），網址 `?et=1`。
- `screen.json` 不加鍵：轉盈用既有的 `eq`、`eb`。
- `_load_financials` 改成回傳 4 個值。前 3 個（`fin`、`meta`、`counts`）不變，`meta` 的 `first_seen` 照舊給季報卡用。第 4 個是 `{代號: {(年, 季): (first_seen, created_at)}}`。只有 `export_all` 一個呼叫處。

### 2-4 新訊號頁

- `HL_KINDS`：
  - `rv` 的面向由「營收」改成「基本面」。
  - 新增 `et: ['基本面', 'EPS 轉盈']`、`eg: ['基本面', 'EPS 年增 ≥ 50%']`。
  - `hlDims` 不改：營收、EPS 同屬一個面向。
- `hlTag`：`et`、`eg` 前面加「26Q3 」（季別取附加值）。
- 說明句改為：

  > 列出最近 5 個交易日（營收、EPS 為最近 20 個交易日）在價量、法人、基本面（營收、EPS）、主動 ETF 四個面向新出現的事件；……營收創新高 = 單月營收創新高且年增 ≥ 30%；EPS 只看全市場最新一季的單季 EPS：轉盈 = 去年同季 ≤ 0、本季 > 0，年增 ≥ 50% 不含去年同季 < 0.1 元（基期低）。營收、EPS 日期為本站首次收錄日（不一定是公司公布日，財報季會集中出現）；……只描述發生了什麼，不代表之後的走勢。

### 2-5 選股「單季 EPS 轉盈」

- 基本面組加開關 `{ id: 'et', label: '單季 EPS 轉盈', sw: true, f: epsTurn, cols: ['eq', 'eb'] }`。
- `epsTurn = x => isNum(x.eq) && isNum(x.eb) && x.eb <= 0 && x.eq > 0`。
- 和既有的 `ey` 一樣，看各股自己的最新季，季別不同時加小字。
- **結果欄改為「單季 EPS、去年同季 EPS」**（新增 `SCR_COLS.eb`），不用 PM 建議的 `eq`、`ey`。
  - 原因：結果表在值為 null 時一律寫 `--`，不呼叫格式函式（`app.js` 第 1037 行）。轉盈股票的 `ey` 都是 null，`ey` 欄會整欄 `--`。
  - 原型第一版改了 `ey` 的格式函式，預覽時發現無效，所以改成顯示去年同季 EPS。
- 用獨立開關，不放進 `ey` 的選項：`ey` 是 ≥ 門檻的數值條件，轉盈不是數值。

### 2-6 11/13 原型結果

| 項目 | 結果 | PM |
|---|---|---|
| 1301 台塑 | `et` 11/12 | 同 |
| 1101 台泥 | `et` 11/12 | 同 |
| **2002 中鋼** | `et` **11/06**（`first_seen` NULL，用 `created_at`） | 同 |
| 2330 台積電 | `rv` 11/10、`eg` **11/13**（`first_seen` 11/14 → 11/13） | 同 |
| 2603 長榮、1303 南亞 | `eg` 11/12 | 同 |
| 2421 建準 | 沒有 `hl` | 同 |
| 轉盈檔數 | 資料庫 128 家；在 `latest.stocks` 的 **126**，其中 21 家靠 `created_at` | 同 |
| 1808 潤隆、3714 富采 | 不在 `latest.stocks`：最後日線 11/11、11/04，11/13 沒有資料列（停牌），本來就不列 | 說明 |
| 年增檔數 | **381** | 378 |
| 選股轉盈 | `screen.json` 中 `eq > 0` 且 `eb ≤ 0` = **151**（預覽「符合 151 檔」）；同時有 `ey` 數值的 0 檔 | 同 |
| 日期 | EPS 事件 11/06 135、11/09 26、11/10 45、11/12 202、11/13 99；沒有 11/14；季別全部 202603 | 同 |
| 新訊號（篩選後） | 面向 ≥ 3：17 → **36**；≥ 2：120 → **199** | 同 |
| 有 `hl` 的股票 | 878 → **1,094**（只有 EPS 事件的 216） | 約 1,093／215 |

- **年增 381 和 PM 的 378 差 3 檔**：2108、3515、9945 年增**剛好 +50.0%**。本設計照 PM 寫的「≥ 50%」，也和選股 `scrGe` 一致，所以列入。PM 的數字推測是用「> 50」算的。
- 檔數 1,094 和 216 也多 1 檔，同樣來自這 3 檔。

---

## 三、F22-1 個股頁連續天數

### 3-1 口徑

| 卡片 | 來源 | 算法 |
|---|---|---|
| 法人1日 | `latest.json` 的 `s` | 直接讀，不重算（金額，`streak(金額[-30:])`） |
| 外資5日 | `fs` | 同上 |
| 投信5日 | `ts` | 同上 |
| 融資餘額 | 個股 JSON `mg.mb` | `balStreak`：逐日增減的連續同向天數 |
| 借券賣出餘額 | `mg.lb` | 同上 |

- `balStreak(G, D, key, to)`：
  - 換算：每天的餘額乘上「該日之後所有官方換算 `mg.k`」，再 `Math.round`。和 `aggregate` 的 `gk`、還原模式的融資融券圖相同。
  - 範圍：只取 `D[i] ≤ to`；`to` 是該卡的資料日（融資 `MG.d`、借券 `SL.d`）。
  - 最多看 31 個餘額（30 個增減），和匯出的 `streak(…[-30:])` 上限一致。
  - 中斷：增減 0 或任一天缺值（null）。
- 顯示規則 `runTxt(n, 增字, 減字)`：
  - |n| < 2 不寫（含 0、undefined）。
  - |n| ≥ 30 寫「30 日以上」，否則寫「N 日」。
  - 例：「連買 3 日」「連賣 25 日」「連增 5 日」「連買 30 日以上」。

### 3-2 版面

- 卡片副行用既有的 `subs()` 換行，加在原本那一行下面：
  - 法人1日：「11/13<br>連賣 3 日」。
  - 外資5日、投信5日：「至 11/13<br>連賣 3 日」。
  - 融資餘額：「1日 +19　5日 +179<br>連增 5 日」。
  - 借券賣出餘額：「1日 +23　5日 +215<br>連增 13 日」。
- 法人5日卡不加：`s` 放在法人1日卡。
- ETF 頁：法人卡本來就沒有；融資、借券卡用 `!E &&` 擋掉，不加。
- 文字用卡片副行的灰色，不另上色。

### 3-3 11/13 全市場驗算（`sa22/streak_run.js`，附錄 B；直接執行 `proj/site/stock.js` 的函式）

| | ≥ 3（連買／連增） | ≤ −3（連賣／連減） | PM |
|---|---|---|---|
| 法人 `s` | 329 | 254 | 同 |
| 外資 `fs` | 306 | 260 | 同 |
| 投信 `ts` | 129 | 24 | 同 |
| 融資 | 180 | 201 | 同（PM 是未套用 `mg.k` 的估算） |
| 借券 | 445 | 66 | 同 |

- 實例：

  | 股票 | 結果 |
  |---|---|
  | 2421 | 法人連賣 3 日、外資連賣 3 日、投信不寫、融資連增 5 日、借券連增 13 日 |
  | 2330 | 法人不寫（`s = 1`）、外資連賣 2 日、投信連買 30 日以上 |
  | 2454 | 投信連買 23 日、法人連買 3 日 |
  | 2308 | 法人連賣 25 日 |
  | 2908 | 融資連增 22 日 |
  | 3013 | 融資連減 15 日 |
  | 2883 | 借券連增 22 日 |

  全部和 PM 相同。「30 日以上」全市場只有 2330 投信。
- `mg.k` 16 檔：1563、2601、3086、3152、3356、4174、4747、5904、6129、6176、6949、8103、8422、8932、8937、9927。
  - 最晚的換算日是 2601 的 10/05。
  - 11/13 這 16 檔的連續區間都沒有跨過換算日（最長是 8422 借券 15 日）。
  - 跨過換算日的情況由 `test_streak` 驗證：不換算時只有 1 日，換算後 4 日。

---

## 四、F22-12（F21-延伸a）個股頁新訊號標籤

- 位置：頁首 `.tags`（族群標籤）下方、開高低一行上方，三個分頁都看得到。
- 結構：

  ```html
  <div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>{hlTag…}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>
  ```

- 文字共用 `app.js` 的 `hlTag`，順序同 `hl`（依日期）。不套用清單篩選（20 日均額、處置、無成交）。
- 相容：
  - `const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];`
  - 新 `stock.js` 配舊 `app.js` 時：
    - 沒有 `hlTag`（第 21 輪以前）→ 不顯示。
    - 有 `hlTag`、但不認得 `et`、`eg`（第 21 輪）→ 只列認得的種類，不出錯。
  - 新 `app.js` 配舊 `stock.js`：頁首沒有標籤，不出錯。
  - ETF：`s` 是 `etfs.rows` 的列，沒有 `hl`，不顯示。
- 說明句不收合，而是常駐一行灰字。
  - 原因：`test_iter13` 斷言 `noteHTML('…'` 字面呼叫剛好 8 處，舊測試不改斷言。
  - 這一行短，375 寬時接在標籤後面換行即可。
- 沒有事件：整塊不輸出，不留空白（2421）。
- CSS：`.s-hl{margin-top:6px}.s-hl>a{margin-right:8px;white-space:nowrap}`；標籤沿用第 21 輪的全域 `.hl-tag`。
- 原型預覽（8001）：

  | 檔位 | 版面 | 結果 |
  |---|---|---|
  | 3661 | 375 深色 | **7 個標籤**（多了「26Q3 EPS 年增 ≥ 50% 11/12」），換 4 行；`scrollWidth = 375` |
  | 2330 | 1024 淺色 | 「10 月營收創新高 11/10」「26Q3 EPS 年增 ≥ 50% 11/13」一行 |
  | 1301 | — | 只有「26Q3 EPS 轉盈 11/12」 |
  | 2421 | — | 沒有區塊 |
  | 0050 | — | 沒有區塊 |

  主控台 0 錯誤。

---

## 五、匯出 JSON 的變更

| 檔案 | 變更 | 大小 |
|---|---|---|
| `latest.json` | `stocks[代號].hl` 多 `et` 126 個、`eg` 381 個事件；216 檔新增 `hl` 鍵；其他鍵、其他事件不變 | 778,057 → 793,258 bytes（**＋15.2 KB**，＋2.0%） |
| `screen.json` | 不變（逐位元組相同） | — |
| `stocks/`、`etfp/`、`etfs/` | 不變（逐位元組相同） | — |

- 比對腳本 `sa22/cmp.py`（附錄 B）：
  - 檔案清單相同（2,373 個）。
  - `latest.json` 以外 0 檔不同。
  - `latest.json` 刪掉 `et`、`eg` 事件（刪完空的 `hl` 刪鍵），兩邊再去掉 `updated_at`、`status` 後**逐值相同**。
- 匯出時間：`orig` 25.4 秒、`proj` 25.4 秒（`highlight_eps` 每檔只算一次）。PM 驗收 #9 的上限是＋5 秒。

---

## 六、邊界情況

| 情況 | 行為 |
|---|---|
| 連續天數回看上限 30 日 | 法人照匯出 `streak(…[-30:])`；融資、借券同樣最多 30 個增減；畫面寫「30 日以上」 |
| 融資、借券資料日早於行情日 | 算到 `MG.d`、`SL.d`；卡片已寫資料日 |
| 不在融資清單（`MG === null`） | 「無信用交易」卡照舊，沒有天數 |
| 沒有借券（`sbl` 不存在） | 沒有借券卡 |
| 只有 1 天資料、新上市 | `balStreak` = 0，不寫 |
| 中間缺值、增減 0 | 中斷 |
| 面額變更、減資 | 依 `mg.k` 換算後再比較 |
| `latest.json` 沒有 `fs`、`ts`（沒有法人資料） | `runTxt(undefined)` = ''，不寫 |
| ETF 頁 | 不加連續天數、不顯示新訊號標籤、沒有技術面訊號（不變） |
| MACD 不足 35 根（含全部月 K） | 照舊不列 MACD 兩項 |
| 柱值相同、剛好 0 | 見 1-1 |
| 去年同季缺、本季缺、上一季缺（單季為 None） | 不產生 EPS 事件 |
| 最新季還是 Q2（金融業） | 不產生 EPS 事件；選股轉盈照各股自己的最新季（Q2 有 25 檔） |
| `first_seen` 是週六、週日 | 對齊到前一個交易日 |
| `created_at` 跨 UTC 午夜（台灣 08:00 前） | 加 8 小時後的台灣日期 |
| 補抓晚於金融業截止日 5 天以上 | 用截止日（只對 `first_seen` NULL） |
| **季報 11/16 前持續增加** | 每晚收集後的 `export` 會出現新的 `et`、`eg`，日期是收錄日；11/14 是週六，一般業截止可能順延到 11/16，11/16 晚上收到的會記成 11/16（或午夜後的 11/17 → 對齊 11/17 前的最後交易日）。金融業到 11/29。驗收數字以匯出當時為準，實例的值不會變 |
| 下一季開始收錄（全市場最新季改變） | 舊季別的事件立即消失。只有 Q4（3/31 截止）與隔年 Q1 早申報的 4 月會重疊（20 個交易日窗口），屬可接受；其他季沒有重疊 |
| 舊 `app.js` 配新 `latest.json` | 第 21 輪的 `hlTag` 碰到 `et`、`eg` 會讀 `HL_KINDS[k][1]` 而出錯，**新訊號頁空白到強制重新整理為止**。舊程式無法修正，列入待上線確認。個股頁不受影響（見第四節） |

---

## 七、測試（`tests/test_iter22.py`，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_eps_kinds` | 轉盈（含去年同季 0）、年增 68.7%、剛好 50.0%、基期剛好 0.10 算、0.05 不算、+23.5% 不算、仍虧損、衰退、去年同季缺、該股沒有最新季別（Q2）、`seen` 為 None |
| `test_eps_dates` | COALESCE（中鋼型 11/06）、**UTC 11/09 17:00 → 11/10**、台灣週六 → 週五、`first_seen` 11/14 → 11/13、窗口邊界 10/19 與 10/18（週日 → 10/16 窗口外）、交易日不足 20 天、補抓 12/20 → 截止日（窗口外）、截止日＋4 天照收錄日、日常收集的晚申報照收錄日 |
| `test_load_financials` | 假 cursor：SQL 多讀 `created_at`；前 3 個回傳值不變；第 4 個是收錄日 |
| `test_export_source` | 常數、`fq_all`、串接位置、UTC 轉換 |
| `test_macd_words` | node 執行 `macdBar`：6 種情況＋持平＋0 邊界；執行真正的 `renderSignals`：「負柱縮短」在偏多欄；`stock.js` 沒有「柱放大／柱縮小」；歸類式不變 |
| `test_streak` | node 執行 `runTxt`、`balStreak`：30 日以上、1 日不寫、undefined、上限 30、只算到 `to`、0 與缺值中斷、**跨換算日（4 日；不換算 1 日）**、沒有資料 |
| `test_stock_source` | 四張卡的副行、ETF 擋掉、`HL` 相容寫法、頁首位置、CSS |
| `test_app_hl` | node 執行 `hlTag`（四種文字）、`hlDims`（營收＋EPS = 1 個面向）、`epsTurn`（6 例）；選股條件與 `eb` 欄、說明句 |
| `test_no_advice_words` | 本輪新文字（`macdBar`、`runTxt`、`balStreak`、頁首兩行、新訊號區段、`epsTurn`、`et` 條件、README 4 段的第 22 輪部分）不含 17 個詞（第 21 輪的 11 個＋利多、利空、看多、看空、轉強、轉弱）；官方名稱「借券賣出」先去掉再檢查 |

- 結果：
  - `proj` 的 `test_iter01`～`22` **22 個全部通過**；`test_iter18`、`test_iter21` 的 `test_no_advice_words` 也通過。
  - 舊測試沒有改任何斷言。
- 反證：
  - 舊程式（`orig`）跑 `test_iter22`：**9 個測試全部失敗**（沒有 `highlight_eps`、`_load_financials` 回傳 3 個值、`stock.js` 沒有 `macdBar`、`runTxt` 等）。
  - 突變（`proj` 改一處，跑 `test_iter22`），每一種都失敗：

    | 改動 | 失敗的測試 |
    |---|---|
    | 不轉 UTC | `test_eps_dates` |
    | 拿掉補抓防呆 | `test_eps_dates` |
    | 基期改成 > 0.1 | `test_eps_kinds` |
    | 不對齊週六 | `test_eps_dates` |
    | 融資不換算 `mg.k` | `test_streak` |
    | 30 日不寫「以上」 | `test_streak` |
    | MACD 舊用詞 | `test_macd_words` |
    | 營收、EPS 分成兩個面向 | `test_app_hl` |

- node：本機 v14.17.1（沒有 `Array.prototype.at`）。測試抽出的函式都沒用到 `.at`；附錄 B 的 `macd_run.js` 自己補 `.at`。

---

## 八、PG 實作順序

1. **基線**：
   - 記錄資料日、`collect_runs` 最大 `run_id`，確認沒有進行中的收集（`finished_at` 為 NULL 的列 0）。
   - 複製 `export.py`、`app.js`、`stock.js`、`app.css`、`README.md` 到 `logs/iter22_before/`。
   - 把專案 `site/data` 複製到 `logs/iter22_base/`。
     - 建議先用基線程式 `export` 一次再複製，讓兩邊只差新程式。
     - 若使用者已經在 11/14 之後收集，資料庫可能比 run 17 新。
2. **套用**：附錄 A 的 diff，先 `patch -p1 --dry-run`，再正式套用；新增 `tests/test_iter22.py`。
   - 本 SA 已在 scratchpad 的專案副本驗證可以套用，套用後和原型逐位元組相同。
3. **測試**：
   - `node --check site/app.js site/stock.js`。
   - `test_iter01`～`22` 全部通過。
4. **反證**：用暫存副本（不含 `.env`）放 `logs/iter22_before/` 的檔案跑 `test_iter22` → 應失敗。
5. **匯出**：新程式 `python3 -u -m twstock export` 一次，記錄耗時與 `latest.json` 大小。
6. **比對**：
   - 把附錄 B 的 `cmp.py` 存成 `logs/iter22_cmp.py`，執行 `python3 logs/iter22_cmp.py logs/iter22_base site/data`，應回傳 0。
   - MACD：`macd_run.js` 用基線與新的 `stock.js` 各跑一次，再用 `macd_cmp.py` 比對 → 0 差異。
   - 連續天數：`streak_run.js` 看分佈與實例。
   - 這些腳本都只讀 `site/data`。
7. **8001 預覽**：
   - 用 `python3 -m twstock serve --port 8001 --no-browser`。
   - 375 深色、1024 淺色；2421、2330、3661、1301，以及新訊號頁、`#/rank/screen?et=1`、0050。
   - 結束時刪除預覽新增的 localStorage 鍵，關閉 8001。
- **允許的寫入**：只有 `export`（1～2 次，寫 `site/data/`）。不執行 `collect`、`history`、`setup-db`、`backup`、還原。
- 行數預估：程式＋README **＋77／−21**（PM 約 70、上限 85）；測試 223 行。

---

## 九、給 QA 的提醒

1. **EPS 獨立驗算**：
   - 不要 import `highlight_eps`。
   - 自己查 `quarterly_financials`（2026Q3、2025Q3、兩年的 Q2）的 `eps`、`first_seen`、`created_at`，依第二節重算，和 `latest.json` 逐檔比對。
   - 注意 `created_at` 是 UTC；年增是 `fin_yoy` 四捨五入到 1 位後再和 50 比較；基期用 ≥ 0.1。
2. **季報還在增加**：
   - 和本文件的差異應該都能用「新收錄的公司」解釋：日期 = 新的收錄日。
   - 11/16 若有順延的一般業季報，`eg`、`et` 會增加。
3. **MACD**：用附錄 B 的腳本或自寫腳本，以網站函式重算；多空結論 0 差異是硬條件。
4. **連續天數**：
   - 法人天數要和 `latest.json` 0 差異。
   - 融資、借券用個股 JSON 自己重算，要套用 `mg.k`，算到 `margin.d`、`sbl.d`。
5. **快取**：舊 `app.js` 配新資料時新訊號頁會出錯（第六節最後一列），強制重新整理後應正常。驗收時請用強制重新整理後的狀態。
6. 預覽前後記錄 localStorage 的鍵。

---

## 十、驗收對照（PM 第二節）

| 項目 | # | 設計／原型 |
|---|---|---|
| F22-10 | 1 | 2421 偏多欄「MACD 負柱縮短」 |
| F22-10 | 2 | 六檔全部相同 |
| F22-10 | 3 | 1,987 檔分佈相同 |
| F22-10 | 4 | 0 差異 |
| F22-10 | 5 | 週 K 同一規則（2421 週 K「負柱加長」）；月 K 沒有 MACD |
| F22-10 | 6 | `test_iter22.test_no_advice_words` |
| F22-11 | 1、2 | 全部相同 |
| F22-11 | 3 | 126（21 家靠 `created_at`）；2 家不在 `latest` 的原因見 2-6 |
| F22-11 | 4 | **381**（差 3 檔見 2-6） |
| F22-11 | 5 | 151、0 檔同時有 `ey` |
| F22-11 | 6 | 只有交易日、≤ 11/13、只有 202603 |
| F22-11 | 7 | 36／199 |
| F22-11 | 8 | 第五節 |
| F22-11 | 9 | ＋0 秒 |
| F22-1 | 1～3 | 全部相同 |
| F22-1 | 4 | 直接讀 `s`、`fs`、`ts`，0 差異 |
| F22-1 | 5 | 分佈全部相同 |
| F22-1 | 6 | 16 檔都沒有跨換算日；跨的情況有單元測試 |
| F22-1 | 7 | 第六節 |
| F22-1 | 8 | 375 深色 `scrollWidth = 375`、1024 淺色、主控台 0 錯誤 |
| F22-12 | 1 | **7 個標籤**（多 EPS 一個，見第十一節） |
| F22-12 | 2、3 | 相同 |
| F22-12 | 4 | 878 → 1,094 |
| F22-12 | 5 | 375 換行、`scrollWidth = 375` |
| F22-12 | 6 | `typeof hlTag` 與 `HL_KINDS` 過濾；反方向舊 `app.js` 的新訊號頁見第六節 |

---

## 十一、對 PM 的調整

1. **選股「單季 EPS 轉盈」的結果欄改為「單季 EPS、去年同季 EPS」**（新增 `SCR_COLS.eb`）。
   - 原因：結果表遇到 null 一律寫 `--`，轉盈股票的 `ey` 全是 null。
2. **年增事件 381 檔**（PM 378）：
   - 照 PM 文字的「≥ 50%」，和選股 `scrGe` 一致。
   - 差的 3 檔（2108、3515、9945）剛好 +50.0%。
   - 去年同季剛好 0.10 元不算基期低（同前端 `epsLow`）。
3. **3661 世芯-KY 是 7 個標籤**：PM 驗收 F22-12 #1 列 6 個，加了 EPS 事件後多「26Q3 EPS 年增 ≥ 50% 11/12」，排在 11/12 的法人事件之後。
4. **補抓防呆**：只對 `first_seen` 為 NULL 的列，門檻用「金融業截止日＋5 天」，超過改用截止日（理由見 2-2）。
5. **「全市場最新季別」用季報表最大的 (年, 季)**，不用 `fin_progress`（窗口外是 None）。
   - 已知限制：4 月 Q4 和 Q1 早申報會重疊，Q1 一出現，Q4 事件就提前消失。
6. **融資、借券連續天數也以 30 日為上限**：PM 沒有規定，本設計和法人用同一條顯示規則，README 一句話說完。
7. **MACD 補「柱持平」**：柱值相同時寫「MACD 柱持平」，照舊歸偏空。PM 要求 0 與相等由 SA 定義，見 1-1。
8. **個股頁說明句常駐、不收合**：`test_iter13` 鎖了 `noteHTML` 字面呼叫數。
9. **待上線確認加一條**：
   - 更新後第一次開排行頁「新訊號」若空白或出錯，強制重新整理即可（舊 `app.js` 不認得 `et`、`eg`）。
   - 個股頁沒有標籤或卡片沒有連續天數時，也一樣強制重新整理。
10. 其他照 PM。

---

## 附錄 A：完整 diff（`orig` → `proj`；新測試檔全文在後）

- 驗證：
  - 在 scratchpad 複製專案目前的 `twstock/`、`site/`（不含 `data`）、`README.md`、`tests/`。
  - `patch -p1 --dry-run` 通過後正式套用，5 個檔和原型逐位元組相同。
  - 再放入 `test_iter22.py`，結果「全部通過」。

```diff
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -47,6 +47,7 @@
 BREADTH_DAYS = 60              # 市場寬度走勢天數
 NH_DAYS = (240, 120, 60, 20)    # C3：創 N 日新高／新低的 N（由大到小，取符合的最大 N）
 HL_DAYS, HL_REV_DAYS = 5, 20     # 第 21 輪 F21-1：近期新訊號看最近 5 個交易日；營收看最近 20 個交易日
+HL_EPS_YOY, HL_EPS_BASE = 50, 0.1   # 第 22 輪 F22-11：EPS 年增事件門檻（%）；去年同季 < 0.1 元為基期低（同前端 EPS_BASE），不產生事件
 CONV_MIN = 0.1                  # 融資融券換算：|k − 1| ≥ 10% 才視為官方已換算
 SCREEN_KEYS = ("a20", "vr", "r5", "r20", "r60", "rs20", "rs60", "b20", "b60", "nh", "nl",
                "rm", "ry", "rc", "rh", "r3", "cap", "mb", "m1", "m5", "sb", "s1", "s5", "sr", "mu", "mnt", "pbp",
@@ -1104,6 +1105,30 @@
     return out
 
 
+def highlight_eps(cum, seen, fq, days):
+    """
+    第 22 輪 F22-11：EPS 事件 [[種類, 日期, 季別]]；只看全市場最新季別 fq（該股沒有這一季 → 不產生）。
+      et 單季 EPS 轉盈：去年同季 ≤ 0、本季 > 0（同季報卡、選股「轉盈」）；
+      eg 單季 EPS 年增 ≥ HL_EPS_YOY%：fin_yoy 達標且去年同季 ≥ HL_EPS_BASE（基期低不產生，同選股 epsLow）。
+    seen = (first_seen, created_at)：日期 = first_seen，NULL（補抓）時用 created_at（資料庫 GETDATE() 是 UTC，＋8 小時取日期）；
+    補抓且晚於該季最晚截止日（金融業）5 天以上 → 改用截止日；再對齊到 ≤ 該日的最後一個交易日 days（午夜後收集的 first_seen 可能是週六），
+    在最近 HL_REV_DAYS 個交易日內才列。
+    """
+    if fq not in cum or not seen or len(days) < HL_REV_DAYS:
+        return []
+    s, b = fin_single(cum, *fq), fin_single(cum, fq[0] - 1, fq[1])
+    v, base = s[4], b and b[4]
+    if v is None or base is None:
+        return []
+    kind = "et" if base <= 0 < v else "eg" if (fin_yoy(v, base) or 0) >= HL_EPS_YOY and _f(base) >= HL_EPS_BASE else None
+    fs, ca = seen
+    d, due = fs or (ca + timedelta(hours=8)).date(), date.fromisoformat(fin_due_dates(fq[0] * 100 + fq[1])[-1])
+    if fs is None and d > due + timedelta(days=5):
+        d = due
+    i = bisect_right(days, d) - 1
+    return [[kind, str(days[i]), fq[0] * 100 + fq[1]]] if kind and i >= 0 and days[i] >= days[-HL_REV_DAYS] else []
+
+
 # ─── 第 10 輪 B5：季報（資料庫存累計值，這裡相減成單季；個股與選股共用）──────
 def _r1(a, b):
     """a ÷ b × 100，四捨五入（ROUND_HALF_UP）到 1 位小數。"""
@@ -1223,17 +1248,19 @@
 
 
 def _load_financials(cur) -> tuple:
-    """({代號: {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}}, {代號: (最新一季業別, 最新一季 first_seen)}, {(年, 季, 市場): 家數})。"""
-    fin, meta, counts = defaultdict(dict), {}, Counter()
-    for code, mkt, y, q, tbl, *vals, seen in cur.execute("""
+    """({代號: {(年, 季): (營收, 毛利, 營益, 淨利, EPS)}}, {代號: (最新一季業別, 最新一季 first_seen)}, {(年, 季, 市場): 家數},
+    第 22 輪：{代號: {(年, 季): (first_seen, created_at)}})。"""
+    fin, meta, counts, seen_at = defaultdict(dict), {}, Counter(), defaultdict(dict)
+    for code, mkt, y, q, tbl, *vals, seen, created in cur.execute("""
         SELECT s.stock_code, s.market_type, f.fin_year, f.fin_quarter, f.industry_tbl,
-               f.revenue, f.gross_profit, f.op_income, f.net_income, f.eps, f.first_seen
+               f.revenue, f.gross_profit, f.op_income, f.net_income, f.eps, f.first_seen, f.created_at
         FROM quarterly_financials f JOIN stocks s ON s.stock_id = f.stock_id
         ORDER BY s.stock_code, f.fin_year, f.fin_quarter"""):
         fin[code][(y, q)] = tuple(vals)
         meta[code] = (tbl, seen)
         counts[(y, q, mkt)] += 1
-    return fin, meta, counts
+        seen_at[code][(y, q)] = (seen, created)
+    return fin, meta, counts, seen_at
 
 
 def screen_build(rows, head):
@@ -1435,7 +1462,7 @@
     b_days = [r[0] for r in cur.execute(f"SELECT DISTINCT TOP {BREADTH_DAYS + 60} trade_date FROM daily_prices ORDER BY trade_date DESC")][::-1]
     status = build_status(cur, latest_date, now)
     valuation, stock_val, val_date = _load_valuation(cur, shares)      # F9-4；第 12 輪加 wpe
-    fin, fin_meta, fin_counts = _load_financials(cur)          # 第 10 輪 B5
+    fin, fin_meta, fin_counts, fin_seen = _load_financials(cur)   # 第 10 輪 B5；第 22 輪加收錄日
     sdates, srecent, sper = _load_sbl(cur)                     # 第 11 輪 B14
     edates, esbl, esbl_m = _load_etf_sbl(cur)                  # 第 12 輪 ETF 借券
     closed = load_closed(cur)                                  # 第 14 輪 F14-3：結算日推算用的休市日
@@ -1459,6 +1486,7 @@
     active = stock_active(holdings, tw)
     act_lots = active_trust(holdings, tw, dates[-1])            # B16（第 8 輪 F8-1）
     hl_act = highlight_active(holdings, tw, b_days[-HL_DAYS])   # 第 21 輪 F21-1
+    fq_all = max(((y, q) for y, q, _ in fin_counts), default=None)   # 第 22 輪 F22-11：全市場最新季別
     idx_close = {m: {d: c for d, c, _ in index_rows.get(code, []) if c is not None}
                  for m, code in (("TWSE", "TAIEX"), ("TPEx", "TPEX"))}
     screen = {}           # 條件選股：{代號: SCREEN_KEYS 欄位}
@@ -1581,7 +1609,8 @@
         hl = sorted(highlights(d_, [float(c[i]) * af[i] if c[i] is not None else None for i in range(len(d_))], tv,
                                [None if c[i] is None else _pct(c[i], chs[i]) for i in range(len(d_))],
                                net_value, t_value, b_days, dates, idx_close[info["market"]])
-                    + highlight_revenue(rev_rows, rev_seen.get(code, {}), b_days[-HL_REV_DAYS]) + hl_act.get(code, []),
+                    + highlight_revenue(rev_rows, rev_seen.get(code, {}), b_days[-HL_REV_DAYS])
+                    + highlight_eps(fin.get(code, {}), fin_seen[code].get(fq_all), fq_all, b_days) + hl_act.get(code, []),
                     key=lambda e: e[1])
         # 52 週高低用還原價（B1）
         w52 = [(float(h[i]) * af[i], float(l[i]) * af[i]) for i in range(len(d_))
--- a/site/app.js
+++ b/site/app.js
@@ -909,9 +909,11 @@
 }
 
 // ─── 第 21 輪 F21-1：近期新訊號（latest.json stocks[代號].hl；20 日均額取 screen.json）──────────
+// 第 22 輪 F22-11：營收面向改稱「基本面」，加 EPS 事件 et、eg（附加值為季別，標籤前加「26Q3」）
 const HL_KINDS = { nh: ['價量', '60 日新高帶量'], vu: ['價量', '量比 ≥ 2 漲 ≥ 3%'], s3: ['法人', '法人連買 3 日'], t3: ['法人', '投信連買 3 日'],
-  t5: ['法人', '投信 5 日買超 ≥ 成交額 5%'], rv: ['營收', '營收年增 ≥ 30% 創新高'], ae: ['主動ETF', '主動 ETF 新增'] };
-const hlTag = ([k, d, x]) => `<span class="hl-tag">${k === 'rv' ? `${x % 100} 月營收創新高` : k === 'ae' ? `${x} 新增` : HL_KINDS[k][1]} <i>${md(d)}</i></span>`;
+  t5: ['法人', '投信 5 日買超 ≥ 成交額 5%'], rv: ['基本面', '營收年增 ≥ 30% 創新高'], et: ['基本面', 'EPS 轉盈'], eg: ['基本面', 'EPS 年增 ≥ 50%'], ae: ['主動ETF', '主動 ETF 新增'] };
+const hlTag = ([k, d, x]) => `<span class="hl-tag">${k === 'rv' ? `${x % 100} 月營收創新高` : k === 'ae' ? `${x} 新增`
+  : (k === 'et' || k === 'eg' ? `${String(x).slice(2, 4)}Q${x % 100} ` : '') + HL_KINDS[k][1]} <i>${md(d)}</i></span>`;
 const hlDims = x => new Set(x.hl.map(e => HL_KINDS[e[0]]?.[0]).filter(Boolean)).size;
 async function renderHl() {
   const S = await loadScreen(), min = localStore('hlmin', '3');
@@ -929,9 +931,10 @@
             <td class="nm"><b>${esc(x.n)}</b>${alertBadge(x)}<span>${x.code} ${esc(x.i)}</span></td>
             <td class="num">${n}</td><td class="hl-tags">${x.hl.map(hlTag).join('')}</td>
             <td class="num ${cls(x.p)}">${pfmt(x.c)}</td>${pctCell(x)}<td class="num">${fmt(x.a20, 1)}億</td></tr>`).join('') + '</tbody></table></div>'}</div>
-      <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收為最近 20 個交易日）在價量、法人、營收、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
-        「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%。
-        營收日期為本站首次收錄日（不一定是公司公布日）；主動 ETF 只涵蓋有持股資料的 ${Object.keys(L.holdings || {}).length} 檔。只描述發生了什麼，不代表之後的走勢。</div></section>`;
+      <div class="muted small" style="margin-top:6px">列出最近 5 個交易日（營收、EPS 為最近 20 個交易日）在價量、法人、基本面（營收、EPS）、主動 ETF 四個面向新出現的事件；同一面向有多個事件只算 1 個面向。
+        「新出現」= 當天符合、前一個交易日不符合，口徑和選股條件相同；60 日新高帶量 = 創 60 日以上新高且量比 ≥ 1.5；營收創新高 = 單月營收創新高且年增 ≥ 30%；
+        EPS 只看全市場最新一季的單季 EPS：轉盈 = 去年同季 ≤ 0、本季 > 0，年增 ≥ 50% 不含去年同季 < 0.1 元（基期低）。
+        營收、EPS 日期為本站首次收錄日（不一定是公司公布日，財報季會集中出現）；主動 ETF 只涵蓋有持股資料的 ${Object.keys(L.holdings || {}).length} 檔。只描述發生了什麼，不代表之後的走勢。</div></section>`;
   onModeSeg();
   if (S) onSeg('hlSeg', v => { localStore('hlmin', null, v); renderHl(); });
   $('#view').addEventListener('click', onRowClick);
@@ -978,6 +981,7 @@
 const REV_BASE = 10000, EPS_BASE = 0.1;
 const revLow = x => isNum(x.ry) && isNum(x.rb) && x.rb < REV_BASE;
 const epsLow = (v, b) => isNum(v) && isNum(b) && b < EPS_BASE;
+const epsTurn = x => isNum(x.eq) && isNum(x.eb) && x.eb <= 0 && x.eq > 0;   // 第 22 輪 F22-11：單季 EPS 轉盈（同季報卡；ey 為 null）
 // 營收年增排行表下一行：比欄名月份舊而未列入的檔數（市場、成交額門檻同排行）與基期低的定義
 function revNote(inMkt, minTv) {
   const M = revMonth(), n = M ? screenRows().filter(x => isNum(x.ry) && x.rm < M && inMkt(x) && (x.tv ?? 0) >= minTv).length : 0;
@@ -1009,6 +1013,7 @@
   pe: ['本益比', x => x.pe, v => fmt(v, 2), 1], dy: ['殖利率', x => x.dy, spct], pb: ['淨值比', x => x.pb, v => fmt(v, 2), 1],
   pbp: ['淨值比位置', x => x.pbp, v => fmt(v) + '%', 1],
   eq: ['單季EPS', x => x.eq, (v, x) => fmt(v, 2) + finTag(x)], ey: ['EPS年增', x => x.ey, (v, x) => epsLow(v, x.eb) ? `基期低${finTag(x)}<span class="sub2">去年同季 ${fmt(x.eb, 2)} 元</span>` : spct(v) + finTag(x)],
+  eb: ['去年同季EPS', x => x.eb, (v, x) => fmt(v, 2) + finTag(x)],   // 第 22 輪 F22-11：「單季 EPS 轉盈」的對照欄（年增無法計算）
   e4: ['近4季EPS', x => x.e4, v => fmt(v, 2)], gm: ['毛利率', x => x.gm, (v, x) => fmt(v, 1) + '%' + finTag(x)],
   gmy: ['毛利率年增', x => x.gmy, (v, x) => sgn(v, 1) + '點' + finTag(x)], eh: ['EPS新高(季)', x => x.eh, int0],
   mc: ['市值', x => x.mc, v => fmt(v, 0) + '億'], to: ['週轉率', x => x.to, v => fmt(v, 2) + '%'],   // 第 12 輪 B11
@@ -1096,6 +1101,7 @@
   { id: 'e4', g: '基本面', label: '近 4 季 EPS > 0', sw: true, f: scrPos('e4'), cols: ['e4'] },
   { id: 'eh', g: '基本面', label: '單季 EPS 創 {v} 季新高', opts: [4, 8], def: 4, f: scrGe('eh'), cols: ['eq', 'eh'], title: '最新一季單季 EPS 高於之前連續 N 季' },
   { id: 'ed', g: '基本面', label: '單季 EPS 比去年同季下滑', sw: true, f: x => isNum(x.ey) && x.ey < 0, cols: ['eq', 'ey'] },
+  { id: 'et', g: '基本面', label: '單季 EPS 轉盈', sw: true, f: epsTurn, cols: ['eq', 'eb'], title: '最新一季單季 EPS > 0，去年同季 ≤ 0（年增無法計算）' },
   { id: 'pe', g: '基本面', label: '0 < 本益比 ≤ {v}', opts: [10, 15, 20], def: 15, val: true, f: (x, v, st) => isNum(x.pe) && x.pe > 0 && x.pe <= v && valGuard(x, st), cols: ['pe'] },
   { id: 'dy', g: '基本面', label: '殖利率 ≥ {v}%', opts: [3, 4, 5, 6], def: 5, val: true, f: (x, v, st) => isNum(x.dy) && x.dy >= v && valGuard(x, st), cols: ['dy'] },
   { id: 'pb', g: '基本面', label: '淨值比 ≤ {v}', opts: [1, 1.5, 2], def: 1, val: true, f: (x, v, st) => isNum(x.pb) && x.pb > 0 && x.pb <= v && valGuard(x, st), cols: ['pb'] },
--- a/site/stock.js
+++ b/site/stock.js
@@ -14,6 +14,20 @@
 };
 
 const MARGIN_NOTE = { O: '停止融資', X: '停止融券', '@': '融資分配', '%': '融券分配', '!': '停止買賣' };   // 上市註記
+// 第 22 輪 F22-1：連續天數的文字；|n| < 2 不寫，30 = 最多看 30 日（匯出 streak 的上限）→「30 日以上」
+const runTxt = (n, up, dn) => Math.abs(n || 0) < 2 ? '' : `連${n > 0 ? up : dn} ${Math.abs(n) >= 30 ? '30 日以上' : Math.abs(n) + ' 日'}`;
+// 融資、借券餘額的連續增減天數（張；面額變更、減資依官方換算 mg.k，同還原模式的融資融券圖）；算到 to（該卡資料日），最多 30 日，增減 0 或缺值中斷
+function balStreak(G, D, key, to) {
+  const a = G?.[key], gk = d => (G.k || []).reduce((p, x) => x.d > d ? p * x.k : p, 1);
+  const v = (a || []).map((x, i) => x == null ? null : Math.round(x * gk(D[i]))).filter((_, i) => D[i] <= to).slice(-31);
+  let n = 0;
+  for (let i = v.length - 1; i > 0; i--) {
+    const x = v[i] == null || v[i - 1] == null ? 0 : v[i] - v[i - 1];
+    if (!x || (n && (x > 0) !== (n > 0))) break;
+    n += x > 0 ? 1 : -1;
+  }
+  return n;
+}
 
 const STOCK_TABS = [['k', '走勢'], ['chip', '籌碼'], ['fund', '基本面']];
 const ETF_TABS = STOCK_TABS.slice(0, 2);       // 第 15 輪 F15-2：ETF 個股頁沒有基本面
@@ -58,6 +72,8 @@
   const F = data.fin;
   const finUp = F && isNum(F.e4) && isNum(F.e4p) && F.e4 > 0 && (F.e4p <= 0 || F.e4 >= F.e4p * 1.5);
   const watching = App.watch.has(code);
+  // 第 22 輪 F22-12：這檔的近期新訊號（文字共用 app.js 的 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列；ETF 沒有 hl）
+  const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];
   const tab0 = pageTab('stockTab', STOCK_TABS), tab = E && tab0 === 'fund' ? 'k' : tab0;   // 分頁：走勢／籌碼／基本面（頁首永遠顯示）；第 15 輪：ETF 沒有基本面
   const fd = md(App.latest.flow_date);
   // 第 15 輪：ETF 的 52 週高低由原始價計算（和匯出端 h52 同樣取資料日往前 365 天）
@@ -69,7 +85,7 @@
   const MG = data.margin;
   const mgNote = MG?.nt && data.market === 'TWSE' ? [...MG.nt].map(ch => MARGIN_NOTE[ch]).filter(Boolean).join('、') : '';
   const mgCards = MG === undefined ? [] : MG === null ? [['信用交易', '無信用交易', 'flat', '不在融資融券清單']]
-    : [['融資餘額', fmt(MG.mb) + ' 張', '', `1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`],
+    : [['融資餘額', fmt(MG.mb) + ' 張', '', subs(`1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`, !E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減'))],
        ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
        ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
        ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
@@ -79,7 +95,7 @@
   const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
   const mtCards = E ? [] : [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
     ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${MT.d !== P.d[last] ? md(MT.d) + '，' : ''}成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
-  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', `1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}${E ? '　資料 ' + md(SL.d) : ''}`],
+  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', subs(`1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}${E ? '　資料 ' + md(SL.d) : ''}`, !E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減'))],
     ...E ? [] : [['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]]];
 
   // E2-4：主動 ETF 持有（統一、群益投信 8 檔；沒有任何一檔持有、也沒有 act 時不顯示）
@@ -118,6 +134,7 @@
             <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
             ${E && E.m === 'TPEx' ? '<span class="muted small">上櫃 ETF 的漲跌可能含除息，本站無法辨識除息日</span>' : ''}
           </div>
+          ${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>` : ''}
           <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
         </div>
         <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
@@ -129,8 +146,8 @@
       ${(tab === 'k' ? [
          [hlFrom ? '區間高' : '52週高', pfmt(E ? eHL[0] : s?.h52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'], ...mtCards]
-        : tab === 'chip' ? [...E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
-         ['外資5日', yi(s?.f5), cls(s?.f5), '至 ' + fd], ['投信5日', yi(s?.t5), cls(s?.t5), '至 ' + fd]], ...mgCards, ...slCards]
+        : tab === 'chip' ? [...E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), subs(fd, runTxt(s?.s, '買', '賣'))], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
+         ['外資5日', yi(s?.f5), cls(s?.f5), subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))], ['投信5日', yi(s?.t5), cls(s?.t5), subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))]], ...mgCards, ...slCards]
         : [['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
          ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))]])
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
@@ -489,6 +506,9 @@
 }
 
 const SIG_MIN = 3, MACD_MIN = 35;   // 有效訊號至少 3 項才下結論；MACD 需 26 + 9 根
+// 第 22 輪 F22-10：MACD 柱依昨（a）、今（b）的正負寫看到的變化；多空照舊只看柱值升降（b > a 偏多，持平偏空）
+const macdBar = (a, b) => b === a ? 'MACD 柱持平' : b > a ? (a < 0 && b > 0 ? 'MACD 柱由負翻正' : b > 0 ? 'MACD 正柱加長' : 'MACD 負柱縮短')
+  : a > 0 && b < 0 ? 'MACD 柱由正翻負' : b < 0 ? 'MACD 負柱加長' : 'MACD 正柱縮短';
 
 function renderSignals(rows, mode) {
   const period = { '日': '日線', '週': '週線', '月': '月線' }[mode];
@@ -507,7 +527,7 @@
   if (n >= MACD_MIN) {
     const { dif, dea, hist } = calcMACD(C);
     chk(dif[i] > dea[i], 'DIF > DEA', 'DIF < DEA');
-    chk(hist[i] > hist[i - 1], 'MACD 柱放大', 'MACD 柱縮小');
+    chk(hist[i] > hist[i - 1], macdBar(hist[i - 1], hist[i]), macdBar(hist[i - 1], hist[i]));
   }
   const total = bull.length + bear.length, lean = bull.length > bear.length ? 'bull' : bull.length < bear.length ? 'bear' : '';
   const tags = `<div>${bull.map(t => `<span class="tag up">${t}</span>`).join('')}${bear.map(t => `<span class="tag dn">${t}</span>`).join('')}</div>` + oscLine(k, d, rsi, i);
--- a/site/app.css
+++ b/site/app.css
@@ -246,6 +246,7 @@
 /* F13-4、F13-5：不在詞中間斷行；手機隱藏期貨表的約當大台兩欄（下方圖表即為約當大台） */
 .nw{white-space:nowrap}
 .s-ohlc{margin-top:4px}
+.s-hl{margin-top:6px}.s-hl>a{margin-right:8px;white-space:nowrap}   /* 第 22 輪 F22-12 */
 @media (max-width:520px){.oi-tbl th:nth-child(n+6),.oi-tbl td:nth-child(n+6){display:none}.oi-tbl th,.oi-tbl td{padding:8px 5px}}
 /* 第 13 輪 QA 後修正：兩張成交額卡＋共同說明包成一組（佔 2 欄），市場寬度卡仍在同一列右側 */
 .g-mk .mk-pair{grid-column:span 2;display:flex;flex-direction:column;gap:6px}
--- a/README.md
+++ b/README.md
@@ -127,9 +127,9 @@
 - 期現貨價差（第 14 輪，`latest.json` 的 `futures.sp`、`futures.stl`）：價差 = 台指期近月**日盤**收盤 − **同一天**加權指數收盤（夜盤不比；任一邊沒有收盤的日子為 null，不補、不估；加權指數目前從 2025-10-30 起），`sp` 和 `d` 逐日對齊；正值為正價差、負值為逆價差，百分比 = 價差 ÷ 加權指數。期貨日盤 13:45 收盤、加權指數 13:30 收盤，時間不同，尾盤變化大時價差會失真。結算日由本站推算：每月第三個週三，遇休市（`market_holidays`、手寫表與臨時休市，同 `check`）順延到下一個交易日；`stl` = `{d: 下次結算日, n: 資料日之後到結算日（含）的交易日數}`，n = 0 為「今天結算」，資料日已過當月結算日時為下個月。近月沿用「當天有成交的最近月份」：結算日當天仍是到期月份，下一個交易日換月；近月和前一個交易日不同時，期貨卡標「今天換月」、價差一行註明「換月」，K 線在換月日標「換 N 月」，迷你圖（近 60 個交易日）以虛線標出換月。臨時休市在匯出後才公布、或期交所另行公告時，以官方為準。第 15 輪：推算時休市集合另加「資料日下一年的 1/1」（元旦每年休市；下一年官方休市表要到 1 月才抓得到，之前 12 月中旬到月底的「還有 N 個交易日」會多算 1 天），只在匯出端，不改 `tradingcal`、`check`。價差迷你圖的 0 軸改用 `--text2`（對卡片背景淺色 6.4 : 1、深色 7.4 : 1），換月虛線維持 `--text3`。
 - 期貨三大法人未平倉來自期交所「三大法人－區分各期貨契約」，抓大台（TXF）、小台（MXF）、微台（TMF），換算成約當大台 = 大台 + 小台/4 + 微台/20。
 - 籌碼因子觀察（大盤漲跌預測）：以外資淨未平倉水位、外資 1 日／5 日增減、投信與自營商 1 日增減（相對近 60 日標準化）做羅吉斯迴歸，預測下一交易日台指期近月日盤漲跌。網站同時顯示 walk-forward 回測命中率與「永遠猜多數方向」的基準；模型沒有勝過基準時，首頁只顯示因子方向，機率與回測收在摺疊區；僅供籌碼面參考，非投資建議。
-- 個股法人：排行可切換 1 日／5 日，提供外資、投信、自營、法人合計的買超／賣超與連買排行；金額 = 張數 × 當日收盤（估算值，與官方公布的買賣金額可能不同）。
-- 條件選股（排行頁「選股」，`#/rank/screen`）：資料來自 `site/data/screen.json`（匯出時計算，0 個外部請求），在瀏覽器合併 `latest.json` 篩選，只做 AND。條件分流動性、價量、技術、法人、信用、基本面、排除七組（技術組為第 18 輪新增），另有 8 組預設（法人連買＋營收創新高、投信認養、帶量突破、多頭排列＋相對強勢、價值高息、營收高成長、籌碼換手、財報優於去年）與 3 組參考（融資追價、軋空觀察、本益比低但 EPS 下滑）。報酬、乖離、均線、新高新低用**還原價格**；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），用成交額所以不受面額變更影響；相對大盤 = 個股報酬 − 指數報酬（上市對加權、上櫃對櫃買）。本益比、殖利率、淨值比條件**預設排除 90 天內股本變動**的股票（官方值可能尚未調整），可關閉，關閉後結果列標示「股本變動」。營收以各股最新公布的月份計算，頁面列出各月份檔數；每月 1～10 日是公布期間，各股月份不同，月份混雜時資料日一行加註說明，營收欄標出和欄名不同的月份。第 9 輪新增「淨值比一年位置 ≤ N%」（`screen.json` 的 `pbp`，見估值位置），和其他估值條件一樣預設排除股本變動。第 10 輪新增季報條件 5 個（基本面組）：單季 EPS 年增 ≥ N%、毛利率年增 ≥ N 百分點、近 4 季 EPS > 0、單季 EPS 創 N 季新高、單季 EPS 比去年同季下滑；預設「財報優於去年」= 單季 EPS 年增 ≥ 20% 且毛利率年增 ≥ 0、成交額 ≥ 0.5 億，參考「本益比低但 EPS 下滑」= 本益比 ≤ 15 且單季 EPS 下滑。`screen.json` 新欄：`eq` 最新一季單季 EPS、`ey` 單季 EPS 年增 %（去年同季 ≤ 0 為 null）、`e4` 近 4 季 EPS、`gm` 單季毛利率 %（金融業 null）、`gmy` 毛利率年增（百分點）、`fq` 最新季別（YYYYQQ）、`eh` 單季 EPS 創幾季新高、`fqd` 各季別檔數；null 一律不符合條件。各股最新一季可能不同（財報公布期間），欄名依檔數最多的季別，季別不同的列加小字季別，資料日一行列出各季別檔數，沒有任何季別 ≥ 98% 時加「財報公布期間，各股季別不同」。第 11 輪新增借券條件 2 個（信用組）：借券占股本 ≥ N%（3／5／8，預設 5）、借券 5 日增加 ≥ N 張（500／1,000／5,000，預設 1,000）；`screen.json` 新欄 `lb` 借券賣出餘額（張）、`l1`／`l5` 1 日／5 日增減（張）、`lp` 占股本 %（沒有股數為 null），`head.sd` 為各市場借券資料日。選股「毛利率」「毛利率年增」欄也和單季 EPS 一樣，季別不同的列加小字季別。「重設」回到預設（保留排除處置股、今日無成交、股本變動與預設排序），不是全部清空。條件存在瀏覽器，網址也會帶條件，可用「複製條件連結」分享。排行另加量比、創新高、20 日相對強勢、營收年增、殖利率、本益比最低（後兩者排除虧損與股本變動）。`screen.json` 不存在時這些功能不出現，既有排行照常。第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億元，收盤 × 目前發行股數）、`to` 週轉率（% = 今日成交股數 ÷ 目前發行股數，今天沒有成交為 0），沒有股數為 null，null 一律不符合。排行「價量」組加「週轉率」（欄位：週轉率、市值；成交額門檻同其他排行）。市值、週轉率都用目前股數，增資、減資前後可能失真。第 14 輪：排行「營收年增」只列營收月份 ≥ 欄名月份（檔數最多的月份）的股票，表下一行寫出未列入的檔數（市場、成交額門檻同排行）；選股的「營收年增 ≥」條件不排除舊月份。`screen.json` 新欄 `rb` 去年同月營收（千元，沒有去年同月為 null）、`eb` 最新一季的去年同季單季 EPS（元，和個股 `fin.q` 第 7 欄同一口徑）。營收年增有值且 `rb` < 10,000 千元（1,000 萬元）時，營收年增欄加「基期低」小標；單季 EPS 年增有值（去年同季 > 0）且 `eb` < 0.1 元時，EPS 年增欄改顯示「基期低」與去年同季 EPS（個股季報卡與柱狀圖提示同規則）。只標示，不排除、不改排序；去年同季 ≤ 0 照舊顯示「轉盈」。第 18 輪新增技術條件 3 個：KD 黃金交叉（K < 20／30／50，預設 20）、RSI(14) ≤ 20／30（預設 30）、RSI(14) ≥ 70／80（預設 70）；`screen.json` 新欄 `k`（K 值）、`kx`（今日 K 由下往上穿過 D 為 1，否則 0）、`rsi`，公式同個股頁，用還原價；今天無成交或根數不足為 null（不符合）。選了這些條件時，結果上方列「今日全市場」各條件的檔數與比例（分母 = 有 K 或 RSI 值的股票），因為急漲急跌時會一次出現上百檔（例：2026-11-06 KD 黃金交叉且 K < 20 有 220 檔、RSI ≤ 30 有 1,017 檔）。不提供預設組合。
-- 近期新訊號（排行頁「新訊號」，`#/rank/hl`，第 21 輪）：匯出時算出每檔股票最近 5 個交易日在四個面向「新出現」的事件，存在 `latest.json` 的 `stocks[代號].hl` = [[種類, 日期, 附加值], ...]（沒有事件的股票沒有這個鍵）。「新出現」= 當天符合、該股前一個交易日不符合，逐日用和選股相同的算法（`price_stats`、連買天數）重算。種類：價量 `nh` 創 60 日以上新高且量比 ≥ 1.5、`vu` 量比 ≥ 2 且漲幅 ≥ 3%；法人 `s3` 法人連買達 3 日、`t3` 投信連買達 3 日、`t5` 投信 5 日買超 ≥ 5 日成交額（20 日均額 × 5）的 5%（法人看法人資料日的最近 5 天）；營收 `rv` 最新一個月年增 ≥ 30% 且創新高，日期為本站首次收錄日（`monthly_revenue.created_at`，晚於次月 10 日 5 天以上視為補抓、改用次月 10 日），看最近 20 個交易日，附加值為年月；主動 ETF `ae` 有持股資料的主動 ETF 相鄰兩個持股日「前一日沒有、後一日有」（同持股頁「新」，每檔 ETF 第一個持股日不算），附加值為 ETF 代號。畫面列 20 日均成交額 ≥ 0.5 億、不含處置股與今日無成交的股票，依面向數（同一面向多個事件算 1 個）、再依 20 日均額排序，可切換面向 ≥ 3／≥ 2（記在瀏覽器 `tw.hlmin`，預設 ≥ 3）。只描述發生了什麼，不代表之後的走勢；不顯示回測數字（分析見 `docs/iterations/21/01-analyst.md`）。`screen.json` 不存在時無法取 20 日均額，頁面顯示尚未產生。
+- 個股法人：排行可切換 1 日／5 日，提供外資、投信、自營、法人合計的買超／賣超與連買排行；金額 = 張數 × 當日收盤（估算值，與官方公布的買賣金額可能不同）。第 22 輪：個股頁「籌碼」分頁的卡片副行加連續天數：法人1日、外資5日、投信5日卡寫「連買／連賣 N 日」（直接用 `latest.json` 的 `s`、`fs`、`ts`，和排行、選股同一口徑：金額、最多看 30 日），融資餘額、借券賣出餘額卡寫「連增／連減 N 日」（張，逐日增減；面額變更、減資依官方換算 `mg.k`，同還原模式的融資融券圖；算到該卡資料日，增減 0 或缺值中斷，最多看 30 日）；1 日以下不寫，30 日寫「30 日以上」。ETF 個股頁不加。
+- 條件選股（排行頁「選股」，`#/rank/screen`）：資料來自 `site/data/screen.json`（匯出時計算，0 個外部請求），在瀏覽器合併 `latest.json` 篩選，只做 AND。條件分流動性、價量、技術、法人、信用、基本面、排除七組（技術組為第 18 輪新增），另有 8 組預設（法人連買＋營收創新高、投信認養、帶量突破、多頭排列＋相對強勢、價值高息、營收高成長、籌碼換手、財報優於去年）與 3 組參考（融資追價、軋空觀察、本益比低但 EPS 下滑）。報酬、乖離、均線、新高新低用**還原價格**；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），用成交額所以不受面額變更影響；相對大盤 = 個股報酬 − 指數報酬（上市對加權、上櫃對櫃買）。本益比、殖利率、淨值比條件**預設排除 90 天內股本變動**的股票（官方值可能尚未調整），可關閉，關閉後結果列標示「股本變動」。營收以各股最新公布的月份計算，頁面列出各月份檔數；每月 1～10 日是公布期間，各股月份不同，月份混雜時資料日一行加註說明，營收欄標出和欄名不同的月份。第 9 輪新增「淨值比一年位置 ≤ N%」（`screen.json` 的 `pbp`，見估值位置），和其他估值條件一樣預設排除股本變動。第 10 輪新增季報條件 5 個（基本面組）：單季 EPS 年增 ≥ N%、毛利率年增 ≥ N 百分點、近 4 季 EPS > 0、單季 EPS 創 N 季新高、單季 EPS 比去年同季下滑；預設「財報優於去年」= 單季 EPS 年增 ≥ 20% 且毛利率年增 ≥ 0、成交額 ≥ 0.5 億，參考「本益比低但 EPS 下滑」= 本益比 ≤ 15 且單季 EPS 下滑。`screen.json` 新欄：`eq` 最新一季單季 EPS、`ey` 單季 EPS 年增 %（去年同季 ≤ 0 為 null）、`e4` 近 4 季 EPS、`gm` 單季毛利率 %（金融業 null）、`gmy` 毛利率年增（百分點）、`fq` 最新季別（YYYYQQ）、`eh` 單季 EPS 創幾季新高、`fqd` 各季別檔數；null 一律不符合條件。各股最新一季可能不同（財報公布期間），欄名依檔數最多的季別，季別不同的列加小字季別，資料日一行列出各季別檔數，沒有任何季別 ≥ 98% 時加「財報公布期間，各股季別不同」。第 11 輪新增借券條件 2 個（信用組）：借券占股本 ≥ N%（3／5／8，預設 5）、借券 5 日增加 ≥ N 張（500／1,000／5,000，預設 1,000）；`screen.json` 新欄 `lb` 借券賣出餘額（張）、`l1`／`l5` 1 日／5 日增減（張）、`lp` 占股本 %（沒有股數為 null），`head.sd` 為各市場借券資料日。選股「毛利率」「毛利率年增」欄也和單季 EPS 一樣，季別不同的列加小字季別。「重設」回到預設（保留排除處置股、今日無成交、股本變動與預設排序），不是全部清空。條件存在瀏覽器，網址也會帶條件，可用「複製條件連結」分享。排行另加量比、創新高、20 日相對強勢、營收年增、殖利率、本益比最低（後兩者排除虧損與股本變動）。`screen.json` 不存在時這些功能不出現，既有排行照常。第 12 輪新增流動性條件 2 個：市值 ≥ N 億（50／100／500／1,000，預設 100）、週轉率 ≥ N%（1／3／5／10，預設 3）；`screen.json` 新欄 `mc` 市值（億元，收盤 × 目前發行股數）、`to` 週轉率（% = 今日成交股數 ÷ 目前發行股數，今天沒有成交為 0），沒有股數為 null，null 一律不符合。排行「價量」組加「週轉率」（欄位：週轉率、市值；成交額門檻同其他排行）。市值、週轉率都用目前股數，增資、減資前後可能失真。第 14 輪：排行「營收年增」只列營收月份 ≥ 欄名月份（檔數最多的月份）的股票，表下一行寫出未列入的檔數（市場、成交額門檻同排行）；選股的「營收年增 ≥」條件不排除舊月份。`screen.json` 新欄 `rb` 去年同月營收（千元，沒有去年同月為 null）、`eb` 最新一季的去年同季單季 EPS（元，和個股 `fin.q` 第 7 欄同一口徑）。營收年增有值且 `rb` < 10,000 千元（1,000 萬元）時，營收年增欄加「基期低」小標；單季 EPS 年增有值（去年同季 > 0）且 `eb` < 0.1 元時，EPS 年增欄改顯示「基期低」與去年同季 EPS（個股季報卡與柱狀圖提示同規則）。只標示，不排除、不改排序；去年同季 ≤ 0 照舊顯示「轉盈」。第 18 輪新增技術條件 3 個：KD 黃金交叉（K < 20／30／50，預設 20）、RSI(14) ≤ 20／30（預設 30）、RSI(14) ≥ 70／80（預設 70）；`screen.json` 新欄 `k`（K 值）、`kx`（今日 K 由下往上穿過 D 為 1，否則 0）、`rsi`，公式同個股頁，用還原價；今天無成交或根數不足為 null（不符合）。選了這些條件時，結果上方列「今日全市場」各條件的檔數與比例（分母 = 有 K 或 RSI 值的股票），因為急漲急跌時會一次出現上百檔（例：2026-11-06 KD 黃金交叉且 K < 20 有 220 檔、RSI ≤ 30 有 1,017 檔）。不提供預設組合。第 22 輪新增「單季 EPS 轉盈」（基本面組，開關）：最新一季單季 EPS > 0 且去年同季（`eb`）≤ 0，和季報卡的「轉盈」相同（年增無法計算，和「單季 EPS 年增 ≥」不會同時符合）；結果欄位為單季 EPS 與去年同季 EPS。
+- 近期新訊號（排行頁「新訊號」，`#/rank/hl`，第 21 輪）：匯出時算出每檔股票最近 5 個交易日在四個面向「新出現」的事件，存在 `latest.json` 的 `stocks[代號].hl` = [[種類, 日期, 附加值], ...]（沒有事件的股票沒有這個鍵）。「新出現」= 當天符合、該股前一個交易日不符合，逐日用和選股相同的算法（`price_stats`、連買天數）重算。種類：價量 `nh` 創 60 日以上新高且量比 ≥ 1.5、`vu` 量比 ≥ 2 且漲幅 ≥ 3%；法人 `s3` 法人連買達 3 日、`t3` 投信連買達 3 日、`t5` 投信 5 日買超 ≥ 5 日成交額（20 日均額 × 5）的 5%（法人看法人資料日的最近 5 天）；營收 `rv` 最新一個月年增 ≥ 30% 且創新高，日期為本站首次收錄日（`monthly_revenue.created_at`，晚於次月 10 日 5 天以上視為補抓、改用次月 10 日），看最近 20 個交易日，附加值為年月；主動 ETF `ae` 有持股資料的主動 ETF 相鄰兩個持股日「前一日沒有、後一日有」（同持股頁「新」，每檔 ETF 第一個持股日不算），附加值為 ETF 代號。畫面列 20 日均成交額 ≥ 0.5 億、不含處置股與今日無成交的股票，依面向數（同一面向多個事件算 1 個）、再依 20 日均額排序，可切換面向 ≥ 3／≥ 2（記在瀏覽器 `tw.hlmin`，預設 ≥ 3）。只描述發生了什麼，不代表之後的走勢；不顯示回測數字（分析見 `docs/iterations/21/01-analyst.md`）。`screen.json` 不存在時無法取 20 日均額，頁面顯示尚未產生。第 22 輪：「營收」面向改稱「基本面」，加 EPS 事件 `et` 單季 EPS 轉盈（去年同季 ≤ 0、本季 > 0）與 `eg` 單季 EPS 年增 ≥ 50%（去年同季 < 0.1 元的基期低不算），附加值為季別 YYYYQQ，標籤如「26Q3 EPS 轉盈」；只看全市場最新一季（`quarterly_financials` 最大的年、季），看最近 20 個交易日，和選股 `eq`、`ey`、`eb` 同一套算法。日期為本站收錄日：`first_seen`，補抓的列（NULL）改用 `created_at`（資料庫時間是 UTC，加 8 小時取日期），補抓且晚於該季金融業截止日 5 天以上改用截止日；再對齊到該日或之前最後一個交易日（午夜後收集的 `first_seen` 可能是週六）。季報集中在 3、5、8、11 月公布，這幾個月 EPS 事件會比較多。個股頁頁首（族群標籤下方）列出這檔的全部事件（文字同新訊號頁，不套用 20 日均額與處置股篩選），沒有事件時不顯示。
 - 今日頁三大法人卡：上市為證交所 BFI82U 官方買賣金額（含 ETF；外資 = 外資及陸資，不含外資自營商，外資自營商已計入自營商），附近 20 日外資買賣超與連買／連賣天數；上櫃為櫃買 `insti/summary` 官方買賣金額（第 9 輪，2026-07-31 起；`latest.json` 的 `insti_official_tpex`，結構同 `insti_official`），另列一行（合計、外資、投信、自營）與上櫃外資 20 日迷你圖，日期早於網站資料日時標示「尚未更新」；上櫃官方尚無任何資料時才退回張數 × 收盤估算（不含 ETF）。上市、上櫃同一天時可相加，卡片不另列合計。資料表 `insti_amount` 以 `market`（`TWSE`／`TPEx`）區分市場。
 - 今日頁估值位置卡（第 9 輪，`latest.json` 的 `valuation`）：上市、上櫃股票的官方本益比、淨值比、殖利率**中位數**在近一年的位置。窗口 = 最近 242 個有官方本益比資料的交易日；中位數每天分市場計算，本益比、淨值比只計入大於 0 的股票，殖利率計入非空值（含 0）；位置 = 窗口內中位數小於或等於今天的天數 ÷ 天數；今天是窗口最低／最高時顯示「一年最低／最高」；附上市本益比中位數近 60 日迷你圖。**不是加權指數本益比**；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利；只是位置，不是買賣訊號。第 10 輪：季報窗口內、當季已有資料時，卡片下方加一行「第 3 季財報已收：上市 N、上櫃 M 家（前一季 X、Y 家）；本益比中位數會隨 EPS 更新而變動」（`latest.json` 的 `fin_progress`：`{q, n: {市場: 家數}, p: {市場: 前一季家數}}`；窗口外或當季 0 家為 null，不顯示）。第 14 輪：`fin_progress.due` = [一般業, 金融業] 申報截止日（取自 `health.FIN_DUE`，年報兩者都是 3/31，只寫一次），括號內加「一般業 11/14、金融業 11/29 截止」，資料日已過的寫「已截止」；殖利率的一年位置加「越高 = 殖利率相對越高」（方向和本益比、淨值比相反；今日頁與個股頁）。第 15 輪：截止日後面加星期（「分別是週六、週日」），截止日是週六、週日時寫「遇假日可能順延到 下週一」，「已截止」也用順延到下週一的日期判斷（例如 2026 Q3 一般業 11/14 是週六，11/16 當天仍寫「截止」，11/17 起「已截止」）；`fin_progress.due` 仍是名目日期。只處理週末，平日的國定假日不處理（網站沒有休市表）；行政程序法第 48 條規定期間末日為週六時以下週一上午為末日、週日或國定假日以次日為末日，但本站沒有查到證交所、金管會對財報申報期限的個別公告，所以寫「可能」，以官方公告為準。第 12 輪：卡片加「加權本益比（市值加權）」一行（`valuation.TWSE|TPEx.wpe`：`v` 今天值、`p` 一年位置 %、`lo`／`hi` 一年最低／最高、`cov` 計入市值占比 %、`t` [市值最大的計入股票, 占計入市值 %]）。加權本益比 = Σ 市值 ÷ Σ（市值 ÷ 官方本益比），市值 = 收盤 × `stocks.shares`（**目前股數**，歷史日期也用目前股數），只計本益比 > 0 的股票（不含虧損公司、不含 ETF）；窗口與位置定義同中位數。大型股影響大（上市台積電約占 43%），中位數反映一般股票；是本站計算，**不是證交所公布的數字**。
 - 個股頁估值位置（第 9 輪，`stocks/{代號}.json` 的 `val`：`{d, pe|pb|dy: [位置 %, 一年最低, 一年最高]}`）：本益比、淨值比、殖利率指標卡加「一年位置 N%（最低～最高）」，窗口同上，只計入大於 0 的官方值（殖利率 0 = 不配息，不算位置）。今天值為空或 ≤ 0（虧損、無股利）、窗口內有效天數少於 120 天（新上市），或 90 天內股本變動（官方值可能尚未調整）時不顯示。估值說明（第 10 輪改寫）：本益比 = 股價 ÷ 近 4 季 EPS；獲利下降時本益比會升高，獲利大增時本益比（淨值比也可能）會落到一年低點（例如景氣循環股在獲利高峰），不代表股價便宜；有季報卡時加「請對照下方季報卡的近 4 季 EPS 與一年前比較」。淨值比卡也標「資料 MM/DD」（股本變動註記照舊只在本益比、殖利率卡）。第 12 輪：個股頁指標卡加「市值」（≥ 1 萬億顯示兆）與「週轉率」（`stocks/{代號}.json` 的 `mt`：`{d, mc 億元, to %}`，目前股數計算；沒有股數的股票沒有 `mt`，兩張卡顯示 `--`）。
@@ -137,7 +137,7 @@
 - 加權指數取自證交所 MI_INDEX（與上市行情同一個請求）；櫃買指數取自櫃買 `indexInfo/inx`（月查詢，可查歷史），缺的月份由 `collect --catch-up` 或 `history --only tpex_index` 補。
 - 處置／注意股取自證交所 OpenAPI（`announcement/punish`、`announcement/notice`）與櫃買 OpenAPI（`tpex_disposal_information`、`tpex_trading_warning_information`），端點只有近幾日，錯過無法回補；`--catch-up` 每個交易日 15:00 後、19:00 後各抓一次；不在股票清單的權證、可轉債不寫入。第 16 輪：證交所 OpenAPI `announcement/notice` 實測一直只回傳空白佔位列（第 1～15 輪上市注意股 0 筆），上市注意股改查證交所網站「公布注意交易資訊」（`www.twse.com.tw/rwd/zh/announcement/notice`，每次查最近 30 天，漏收的日子下次收集會自動補上，每天多 1 個請求）；原因去掉網頁的 HTML 標籤。收集輸出分市場（「處置 上市 a／上櫃 b 筆、注意 上市 c／上櫃 d 筆」），上市注意 30 天內 0 筆、上櫃注意 0 筆時多印一行提醒（只提醒，不算失敗）。第 17 輪：收集輸出的上市注意數字標「（近 30 天）」；證交所網站（上市注意）抓取失敗時只略過上市注意並印警告，上櫃與上市處置照常寫入（下次收集會補最近 30 天）；OpenAPI 4 個來源任一失敗仍整批不寫。
 - 排行預設只列成交額 ≥ 0.5 億的股票，避免冷門股佔據；可在排行頁調整門檻。
-- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。現金增資除權也依官方參考價調整。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 19 輪：除權事件依官方「減除股利參考價」（只扣股利、不扣現金增資，存在 `price_events.div_ref`；減資、面額變更沒有這一欄）分類，匯出 `ev[].k`：等於參考價 `s`（沒有現增，圖例「除權（配股）」）、等於前收 `c`（只有現增，標記「現增」、圖例「除權（現金增資）」）、其他 `sc`（股利＋現增，「權息」圖例「除權息（含現金增資）」）；容差 0.005 元，只對「權」「權息」，沒有值時照舊寫「除權」。週／月 K 的事件標記寫事件日（例如「2/24 現增」「6/10 息・6/24 權」），圖例第一欄寫「2026-02-23 當週」「2026-02 月」；「原始」價的週／月 K 那一根含事件時，前一根收盤先乘上每筆事件的參考價 ÷ 前收再相減，漲跌幅和「還原」相同（6669 週 K 2026-08-31 由 −64.38% 改為 +6.26%）。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。
+- 個股價格預設**還原**（向後還原，最新收盤不變）：除權息、減資、面額變更以官方參考價 ÷ 事件前收盤為係數，事件之前的開高低收乘上之後所有事件係數的乘積。上市事件取自證交所 TWT49U、TWTAUU、TWTB8U，上櫃除權息取自櫃買除權除息計算結果表，上櫃減資、面額變更以「收盤 − 官方漲跌」反推。現金增資除權也依官方參考價調整。K 線可切換「原始」；52 週高低與技術面訊號一律用還原價；成交量、法人張數未還原。第 19 輪：除權事件依官方「減除股利參考價」（只扣股利、不扣現金增資，存在 `price_events.div_ref`；減資、面額變更沒有這一欄）分類，匯出 `ev[].k`：等於參考價 `s`（沒有現增，圖例「除權（配股）」）、等於前收 `c`（只有現增，標記「現增」、圖例「除權（現金增資）」）、其他 `sc`（股利＋現增，「權息」圖例「除權息（含現金增資）」）；容差 0.005 元，只對「權」「權息」，沒有值時照舊寫「除權」。週／月 K 的事件標記寫事件日（例如「2/24 現增」「6/10 息・6/24 權」），圖例第一欄寫「2026-02-23 當週」「2026-02 月」；「原始」價的週／月 K 那一根含事件時，前一根收盤先乘上每筆事件的參考價 ÷ 前收再相減，漲跌幅和「還原」相同（6669 週 K 2026-08-31 由 −64.38% 改為 +6.26%）。第 18 輪：K 線下方的子圖可切換 MACD／KD／RSI（預設 MACD，瀏覽器記住選擇；ETF 頁只有 MACD）。KD(9,3,3)：RSV = (收 − 9 日最低) ÷ (9 日最高 − 9 日最低) × 100（最高 = 最低時 50），K = 2/3 前 K + 1/3 RSV，D = 2/3 前 D + 1/3 K，起始 50；RSI(14) 用 Wilder 平滑（前 14 個漲跌先平均）；無成交日以前一個收盤畫一字線一起計算；KD 子圖虛線 20、80，RSI 虛線 30、70。技術面卡在原本 6 項下方加「動能（不計入多空）」一行（K、D、今日交叉、RSI 與區間），**不影響「偏多／偏空」**；不足 9／15 根寫「資料不足」。KD、RSI 在急漲急跌時會長時間停在低檔或高檔、交叉反覆出現，只寫數值與區間，不寫買賣建議。匯出端 `twstock/export.py` 的 `calc_kd`、`calc_rsi` 和 `site/stock.js` 的 `calcKD`、`calcRSI` 是同一套公式，改一邊要改另一邊（`tests/test_iter18.py` 會比對）。日線未滿一年時顯示「區間高／低」與起始日。第 22 輪：技術面訊號的 MACD 柱依昨、今柱值的正負寫「MACD 正柱加長／正柱縮短／負柱縮短／負柱加長／柱由負翻正／柱由正翻負」（柱值相同寫「柱持平」），偏多／偏空的歸類照舊只看柱值是否比昨天大。
 - 漲跌：除權息、減資、面額變更當天以「收盤 − 參考價」計算，參考價依升降單位四捨五入（與官方一致，例如 2,614.99 → 2,615；還原係數仍用未取整的官方值）；上市股前一交易日無成交時，以最後成交日收盤計算並標示「相對 MM/DD 收盤」；官方未提供漲跌且找不到對應事件（例如停止買賣後恢復交易）時顯示「不比價」，漲跌家數算平盤。板塊泡泡圖的漲跌幅也用這個值。
 - 除權、減資、面額變更等股本變動（參考價變動 10% 以上）後 90 天內，個股頁的本益比、殖利率會加註「官方值可能尚未調整」：官方值的 EPS、股利可能仍是舊股本的數字。本益比、殖利率卡會顯示資料日（例如「資料 10/30」）；官方沒有提供時標示「官方未提供」。
 - 月營收：第 9 輪起從每月第一個交易日開始，`collect --catch-up` 每天第一次成功收集時抓已公布的公司（只補資料庫還沒有的公司，同一天只抓一次），直到該月家數達前一月的 98% 為止（約 10～12 日），之後到月底 0 個請求；`collect --date`、`history` 也收前一個月。月初官方檔案只有標題列時寫入 0 家，不是錯誤。
```

### `tests/test_iter22.py`（新檔，全文）

```python
"""第 22 輪（不連網、不連資料庫）：F22-10 MACD 柱用詞、F22-11 EPS 事件與選股「轉盈」、F22-1 連續天數、F22-12 個股頁新訊號。
export 的 highlight_eps、_load_financials 用自造資料測邊界（UTC、週六對齊、基期、補抓、最新季別）；
有 node 時，逐字取出 stock.js、app.js 的函式執行（macdBar、renderSignals、runTxt、balStreak、hlTag、epsTurn）。"""
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from twstock import export  # noqa: E402

APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SRC = (ROOT / "twstock" / "export.py").read_text(encoding="utf-8")


def _weekdays(a, b):
    out, d = [], a
    while d <= b:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DAYS = _weekdays(date(2026, 9, 1), date(2026, 11, 13))      # 交易日（測試用：週一～五）；最後一天 11/13（週五）
FQ = (2026, 3)


def _cum(cur, base, q2=D("0")):
    """2026Q3 單季 = cur、2025Q3 單季 = base（Q2 累計 q2，Q3 累計 = q2 + 單季）。"""
    return {(2026, 2): (None,) * 4 + (q2,), (2026, 3): (None,) * 4 + (q2 + cur,),
            (2025, 2): (None,) * 4 + (D("0"),), (2025, 3): (None,) * 4 + (base,)}


def _eps(cur, base, seen, fq=FQ, days=DAYS):
    return export.highlight_eps(_cum(D(cur), D(base)), seen, fq, days)


def test_eps_kinds():
    fs = date(2026, 11, 12)
    assert _eps("0.90", "-0.10", (fs, None)) == [["et", "2026-11-12", 202603]]          # 台塑型：轉盈
    assert _eps("0.25", "0", (fs, None)) == [["et", "2026-11-12", 202603]]              # 去年同季 0 也算轉盈
    assert _eps("29.42", "17.44", (fs, None)) == [["eg", "2026-11-12", 202603]]        # +68.7%
    assert _eps("0.36", "0.24", (fs, None)) == [["eg", "2026-11-12", 202603]]          # 剛好 +50.0%（≥，同選股 scrGe）
    assert _eps("0.65", "0.10", (fs, None)) == [["eg", "2026-11-12", 202603]]          # 去年同季剛好 0.1 元不是基期低（同前端 b < 0.1）
    assert _eps("1.00", "0.05", (fs, None)) == []                                      # 基期低
    assert _eps("3.15", "2.55", (fs, None)) == []                                      # 建準型 +23.5%
    assert _eps("-0.20", "-0.50", (fs, None)) == []                                    # 仍虧損
    assert _eps("0.10", "0.20", (fs, None)) == []                                      # 衰退
    # 去年同季缺、本季缺、該股最新一季不是全市場最新季（金融業 Q2）→ 不產生
    cum = _cum(D("1"), D("0.5"))
    del cum[(2025, 3)]
    assert export.highlight_eps(cum, (fs, None), FQ, DAYS) == []
    q2_only = {k: v for k, v in _cum(D("1"), D("-1")).items() if k != (2026, 3)}
    assert export.highlight_eps(q2_only, (None, datetime(2026, 11, 6, 15, 48)), FQ, DAYS) == []
    assert export.highlight_eps(_cum(D("1"), D("-1")), None, FQ, DAYS) == []


def test_eps_dates():
    utc = lambda *a: (None, datetime(*a))                       # 補抓：first_seen NULL，created_at 為 UTC
    assert _eps("0.08", "-0.16", utc(2026, 11, 6, 15, 48)) == [["et", "2026-11-06", 202603]]    # 中鋼型：COALESCE 生效
    assert _eps("0.08", "-0.16", utc(2026, 11, 9, 17, 0)) == [["et", "2026-11-10", 202603]]     # UTC 11/09 17:00 = 台灣 11/10
    assert _eps("0.08", "-0.16", utc(2026, 11, 6, 16, 30)) == [["et", "2026-11-06", 202603]]    # 台灣 11/07（週六）→ 11/06
    assert _eps("29.42", "17.44", (date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))) == [["eg", "2026-11-13", 202603]]   # 台積電型：first_seen 週六 → 11/13
    # 窗口：最近 20 個交易日（10/19 起）
    assert DAYS[-export.HL_REV_DAYS] == date(2026, 10, 19)
    assert _eps("0.9", "-0.1", (date(2026, 10, 19), None)) == [["et", "2026-10-19", 202603]]
    assert _eps("0.9", "-0.1", (date(2026, 10, 18), None)) == []                     # 週日 → 10/16，窗口外
    assert _eps("0.9", "-0.1", (date(2026, 8, 31), None), days=DAYS[:5]) == []       # 交易日不足 20 天
    # 補抓防呆：first_seen NULL 且晚於金融業截止日（11/29）5 天以上 → 改用 11/29，對齊 11/27（週五），12/31 時在窗口外
    dec = _weekdays(date(2026, 9, 1), date(2026, 12, 31))
    assert _eps("0.9", "-0.1", utc(2026, 12, 20, 2, 0), days=dec) == []
    assert _eps("0.9", "-0.1", utc(2026, 12, 3, 2, 0), days=dec[:dec.index(date(2026, 12, 10)) + 1]) == [["et", "2026-12-03", 202603]]   # 截止日 + 4 天：照收錄日
    assert _eps("0.9", "-0.1", (date(2026, 12, 20), None), days=dec) == [["et", "2026-12-18", 202603]]   # 日常收集的晚申報：照收錄日


def test_load_financials():
    class Cur:
        def execute(self, sql):
            assert "f.eps, f.first_seen, f.created_at" in sql
            return iter([("2002", "TWSE", 2026, 2, "ci", 1, 2, 3, 4, D("0.1"), None, datetime(2026, 11, 6, 15, 48)),
                         ("2002", "TWSE", 2026, 3, "ci", 1, 2, 3, 4, D("0.18"), None, datetime(2026, 11, 6, 15, 48)),
                         ("2330", "TWSE", 2026, 3, "ci", 1, 2, 3, 4, D("50"), date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))])
    fin, meta, counts, seen = export._load_financials(Cur())
    assert fin["2002"][(2026, 3)] == (1, 2, 3, 4, D("0.18"))                           # 既有回傳不變
    assert meta == {"2002": ("ci", None), "2330": ("ci", date(2026, 11, 14))}
    assert counts[(2026, 3, "TWSE")] == 2
    assert seen["2330"][(2026, 3)] == (date(2026, 11, 14), datetime(2026, 11, 13, 16, 26))


def test_export_source():
    assert "HL_EPS_YOY, HL_EPS_BASE = 50, 0.1" in SRC
    assert "fq_all = max(((y, q) for y, q, _ in fin_counts), default=None)" in SRC          # 全市場最新季別
    assert "+ highlight_eps(fin.get(code, {}), fin_seen[code].get(fq_all), fq_all, b_days) + hl_act.get(code, [])," in SRC
    assert "(ca + timedelta(hours=8)).date()" in SRC                                         # created_at 是 UTC


def _grab(src, name):
    """取出頂層 function 或 const（const 取到去掉行尾註解後結尾為「;」的那一行）。"""
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^const {name}\b", src, re.M)
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def _node(js):
    node = shutil.which("node")
    if not node:
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


def test_macd_words():
    js = "\n".join(_grab(STK, n) for n in ("macdBar", "SIG_MIN", "calcMA", "calcMACD", "calcKD", "calcRSI", "oscLine", "renderSignals")) + \
        "\n" + "\n".join(_grab(APP, n) for n in ("fmt", "md")) + """
const box = {}, $ = s => (box[s] = box[s] || {});
const cases = [[0.32, 0.39], [0.62, 0.52], [-1.57, -1.13], [-0.26, -0.29], [-0.34, 0.03], [1.38, -0.29], [0.2, 0.2], [-0.5, 0], [0.5, 0], [0, 0.1], [0, -0.1]];
const C = [...Array(60).fill(100), ...Array.from({ length: 15 }, (_, i) => 99 - i * 2), 72, 72.5];   // 下跌後止跌：負柱縮短
const rows = C.map((c, i) => ({ d: '2026-11-' + String(i % 28 + 1).padStart(2, '0'), o: c, h: c, l: c, c, nt: false }));
const { hist } = calcMACD(C), n = C.length;
renderSignals(rows, '日');
console.log(JSON.stringify({ w: cases.map(([a, b]) => macdBar(a, b)), h: [hist[n - 2], hist[n - 1]], html: box['#sigBox'].innerHTML }));"""
    o = _node(js)
    if o is None:
        print("  （沒有 node，略過 MACD 執行）"); return
    assert o["w"] == ["MACD 正柱加長", "MACD 正柱縮短", "MACD 負柱縮短", "MACD 負柱加長", "MACD 柱由負翻正", "MACD 柱由正翻負",
                      "MACD 柱持平", "MACD 負柱縮短", "MACD 正柱縮短", "MACD 正柱加長", "MACD 負柱加長"], o["w"]
    a, b = o["h"]
    assert a < b < 0, o["h"]                                                     # 樣本本身：負柱、柱值上升
    assert '<span class="tag up">MACD 負柱縮短</span>' in o["html"] and "柱放大" not in o["html"]
    assert "MACD 柱放大" not in STK and "MACD 柱縮小" not in STK
    assert "chk(hist[i] > hist[i - 1], macdBar(hist[i - 1], hist[i]), macdBar(hist[i - 1], hist[i]));" in STK   # 多空歸類不變


def test_streak():
    js = "\n".join(_grab(STK, n) for n in ("runTxt", "balStreak")) + """
const D = Array.from({ length: 40 }, (_, i) => new Date(Date.UTC(2026, 8, 1 + i)).toISOString().slice(0, 10));
const up = D.map((_, i) => 1000 + i);
const r = {
  t: [[30, '買', '賣'], [-3, '買', '賣'], [1, '買', '賣'], [0, '買', '賣'], [undefined, '買', '賣'], [5, '增', '減'], [-31, '增', '減']].map(a => runTxt(...a)),
  cap: balStreak({ mb: up }, D, 'mb', D[39]),
  to: balStreak({ mb: up.map((v, i) => i > 35 ? 0 : v) }, D, 'mb', D[35]),
  zero: balStreak({ mb: up.map((v, i) => i === 37 ? up[36] : v) }, D, 'mb', D[39]),
  gap: balStreak({ mb: up.map((v, i) => i === 37 ? null : v) }, D, 'mb', D[39]),
  conv: balStreak({ lb: [5000, 4000, 1000, 1010, 1020, 103, 104], k: [{ d: D[5], k: 0.1 }] }, D.slice(0, 7), 'lb', D[6]),
  noConv: balStreak({ lb: [5000, 4000, 1000, 1010, 1020, 103, 104] }, D.slice(0, 7), 'lb', D[6]),
  none: [balStreak(undefined, D, 'mb', D[39]), balStreak({ mb: [1] }, D.slice(0, 1), 'mb', D[0]), balStreak({ mb: [5, 4, 3] }, D.slice(0, 3), 'lb', D[2])],
};
console.log(JSON.stringify(r));"""
    o = _node(js)
    if o is None:
        print("  （沒有 node，略過連續天數執行）"); return
    assert o["t"] == ["連買 30 日以上", "連賣 3 日", "", "", "", "連增 5 日", "連減 30 日以上"], o["t"]
    assert o["cap"] == 30                       # 最多看 30 日
    assert o["to"] == 30                        # 只算到 to（之後的 0 不影響）
    assert o["zero"] == 2 and o["gap"] == 1     # 增減 0、缺值中斷
    assert o["conv"] == 4 and o["noConv"] == 1  # 面額變更：換算前 1000、1010、1020 → 100、101、102，連增 4 日（不換算只有 1 日）
    assert o["none"] == [0, 0, 0]               # 沒有融資資料、只有 1 天、沒有借券


def test_stock_source():
    assert "subs(fd, runTxt(s?.s, '買', '賣'))" in STK
    assert "subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))" in STK and "subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))" in STK
    assert "!E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減')" in STK              # ETF 頁不加
    assert "!E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減')" in STK
    # F22-12：頁首、共用 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列
    assert "const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];" in STK
    assert '${HL.length ? `<div class="s-hl"><a class="small" href="#/rank/hl">近期新訊號</a>${HL.map(hlTag).join(\'\')}' in STK
    head = STK[STK.index('<div class="s-head">'):STK.index('id="starBtn"')]
    assert head.index('<div class="tags">') < head.index('s-hl')                    # 族群標籤下方、頁首內
    assert ".s-hl{margin-top:6px}" in CSS


def test_app_hl():
    js = "\n".join(_grab(APP, n) for n in ("md", "HL_KINDS", "hlTag", "hlDims", "isNum", "epsTurn")) + """
const tags = [['et', '2026-11-12', 202603], ['eg', '2026-11-13', 202603], ['rv', '2026-11-10', 202610], ['nh', '2026-11-13']].map(hlTag);
const t = [{ eq: 0.08, eb: -0.16 }, { eq: 0.5, eb: 0 }, { eq: 0, eb: -1 }, { eq: 1, eb: 0.01 }, { eq: 1, eb: null }, { eq: 1 }].map(epsTurn);
console.log(JSON.stringify({ tags, dims: [hlDims({ hl: [['rv', 'x'], ['et', 'x'], ['eg', 'x']] }), hlDims({ hl: [['rv', 'x'], ['s3', 'x'], ['eg', 'x']] })], t }));"""
    o = _node(js)
    if o is not None:
        assert o["tags"] == ['<span class="hl-tag">26Q3 EPS 轉盈 <i>11/12</i></span>', '<span class="hl-tag">26Q3 EPS 年增 ≥ 50% <i>11/13</i></span>',
                             '<span class="hl-tag">10 月營收創新高 <i>11/10</i></span>', '<span class="hl-tag">60 日新高帶量 <i>11/13</i></span>'], o["tags"]
        assert o["dims"] == [1, 2]                                                   # 營收、EPS 同屬「基本面」
        assert o["t"] == [True, True, False, False, False, False]
    assert "{ id: 'et', g: '基本面', label: '單季 EPS 轉盈', sw: true, f: epsTurn, cols: ['eq', 'eb']" in APP
    assert "eb: ['去年同季EPS', x => x.eb, (v, x) => fmt(v, 2) + finTag(x)]," in APP
    assert "營收、EPS 日期為本站首次收錄日" in APP


def test_no_advice_words():
    seg = "".join(_grab(STK, n) for n in ("macdBar", "runTxt", "balStreak"))
    seg += "".join(l for l in STK.splitlines() if "const HL = " in l or "s-hl" in l)
    seg += APP[APP.index("// ─── 第 21 輪 F21-1"):APP.index("// ─── 第 8 輪 F8-2")] + _grab(APP, "epsTurn")
    seg += "".join(re.findall(r"\{ id: 'et'.*?\},\n", APP, re.S))
    seg += "".join(l[l.index("第 22 輪"):] for l in README.splitlines() if "第 22 輪" in l)
    assert seg.count("第 22 輪") >= 4, seg.count("第 22 輪")                       # README 4 段都有取到
    seg = seg.replace("借券賣出", "")                                               # 官方資料名稱（借券賣出餘額），不是建議
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率",
              "利多", "利空", "看多", "看空", "轉強", "轉弱"):
        assert w not in seg, w


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_") and callable(f):
            print("==", n); f()
    print("全部通過")
```

---

## 附錄 B：比對與驗算腳本（PG、QA 可存到 `logs/`；都只讀檔案，`run_export.py` 只對資料庫做 SELECT）

### `cmp.py`

```python
"""第 22 輪比對：python3 cmp.py 基線目錄 新目錄。
1. 檔案清單相同；latest.json 以外逐位元組相同。
2. latest.json：新的去掉 hl 中的 et、eg 事件（去掉後空的 hl 刪鍵），兩邊再去掉 updated_at、status 後逐值相同。
3. 列出新增事件數、latest.json 大小。"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path
A, B = Path(sys.argv[1]), Path(sys.argv[2])
fa = {p.relative_to(A) for p in A.rglob("*") if p.is_file()}
fb = {p.relative_to(B) for p in B.rglob("*") if p.is_file()}
assert fa == fb, ("檔案清單不同", sorted(fa ^ fb)[:10])
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
diff = [str(f) for f in sorted(fa) if str(f) != "latest.json" and h(A / f) != h(B / f)]
print("檔案數", len(fa), "；latest.json 以外不同：", len(diff), diff[:10])
la, lb = (json.loads((x / "latest.json").read_text(encoding="utf-8")) for x in (A, B))
NEW = {"et", "eg"}
cnt, kinds, only = Counter(), Counter(), 0
for c, st in lb["stocks"].items():
    if "hl" in st:
        new = [e for e in st["hl"] if e[0] in NEW]
        kinds.update(e[0] for e in new)
        if new and len(new) == len(st["hl"]):
            only += 1
        st["hl"] = [e for e in st["hl"] if e[0] not in NEW]
        if not st["hl"]:
            del st["hl"]
for x in (la, lb):
    x.pop("updated_at", None); x.pop("status", None)
same = la == lb
print("latest.json 去掉 et、eg 後相同：", same, "；新增事件", dict(kinds), "；只有 EPS 事件的股票", only)
for x in (A, B):
    print(x.name, "latest.json", (x / "latest.json").stat().st_size, "bytes")
sys.exit(0 if not diff and same else 1)
```

### `macd_run.js`

```js
// 用網站的 stock.js（aggregate、renderSignals）對全部個股 JSON 判讀技術面訊號：node macd_run.js stock.js app.js stocks目錄 輸出.json
const fs = require('fs'), vm = require('vm');
const [stk, app, dir, out] = process.argv.slice(2);
if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };   // node 14
const A = fs.readFileSync(app, 'utf8');
const grab = n => A.split('\n').find(l => l.startsWith(`const ${n} =`));
const box = {};
const ctx = { window: {}, document: {}, console, box, $: s => (box[s] = box[s] || {}) };
vm.createContext(ctx);
vm.runInContext("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n" + grab('fmt') + '\n' + grab('md') + '\n' + fs.readFileSync(stk, 'utf8') + `
;globalThis.run = (data, m) => { renderSignals(aggregate(data, m, true), m); return box['#sigBox'].innerHTML; };`, ctx);
const res = {};
for (const f of fs.readdirSync(dir)) {
  const data = JSON.parse(fs.readFileSync(`${dir}/${f}`, 'utf8')), code = f.replace('.json', '');
  res[code] = {};
  for (const m of ['日', '週', '月']) {
    const h = ctx.run(data, m);
    const head = (h.match(/font-weight:600;margin-bottom:6px">([^<]*)</) || [])[1];
    const tags = [...h.matchAll(/<span class="tag (up|dn)">([^<]*)<\/span>/g)].map(x => [x[1], x[2]]);
    res[code][m] = [head, tags];
  }
}
fs.writeFileSync(out, JSON.stringify(res));
console.log('stocks', Object.keys(res).length);
```

### `macd_cmp.py`

```python
"""比對舊、新技術面訊號（macd_run.js 的輸出）：python3 macd_cmp.py 舊.json 新.json [代號…]
多空結論（「偏多：N 多 N 空」）與每一項的歸類 0 差異；只有 MACD 柱那一項的文字改變。列出新用詞分佈與實例。"""
import json, sys
from collections import Counter
o, n = (json.load(open(f, encoding="utf-8")) for f in sys.argv[1:3])
bar = lambda t: t.startswith(("MACD 柱", "MACD 正柱", "MACD 負柱"))
bad, cnt, pair = [], {m: Counter() for m in "日週月"}, Counter()
for c in o:
    for m in "日週月":
        (ho, to), (hn, tn) = o[c][m], n[c][m]
        same = ho == hn and [s for s, _ in to] == [s for s, _ in tn] and \
            [t for _, t in to if not bar(t)] == [t for _, t in tn if not bar(t)]
        if not same:
            bad.append((c, m))
        for (_, t1), (_, t2) in zip(to, tn):
            if bar(t2):
                cnt[m][t2] += 1
                pair[(m, t1, t2)] += m == "日"
print("股票", len(o), "；結論、歸類或其他項不同：", len(bad), bad[:5])
for m in "日週月":
    print(m, "有 MACD 判讀", sum(cnt[m].values()), dict(cnt[m]))
print("日線 舊 → 新", {f"{a}→{b}": v for (_, a, b), v in pair.items() if v})
for c in sys.argv[3:]:
    print(c, n[c]["日"][0], [t for _, t in n[c]["日"][1] if bar(t)], "週", [t for _, t in n[c]["週"][1] if bar(t)])
sys.exit(1 if bad else 0)
```

### `streak_run.js`

```js
// 用 stock.js 的 runTxt、balStreak 算全部個股的融資、借券連續天數，並讀 latest.json 的 s、fs、ts：node streak_run.js stock.js data目錄
const fs = require('fs'), vm = require('vm');
const [stk, dir] = process.argv.slice(2);
const ctx = { window: {}, document: {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(stk, 'utf8') + ';globalThis.f = { runTxt, balStreak };', ctx);
const { runTxt, balStreak } = ctx.f, L = JSON.parse(fs.readFileSync(`${dir}/latest.json`, 'utf8'));
const out = {}, dist = { s: [0, 0], fs: [0, 0], ts: [0, 0], mb: [0, 0], lb: [0, 0] }, conv = [];
for (const f of fs.readdirSync(`${dir}/stocks`)) {
  const d = JSON.parse(fs.readFileSync(`${dir}/stocks/${f}`, 'utf8')), c = d.code, s = L.stocks[c] || {};
  const mb = d.margin ? balStreak(d.mg, d.prices.d, 'mb', d.margin.d) : 0, lb = d.sbl ? balStreak(d.mg, d.prices.d, 'lb', d.sbl.d) : 0;
  const r = { s: s.s, fs: s.fs, ts: s.ts, mb, lb };
  for (const k in dist) { if (r[k] >= 3) dist[k][0]++; if (r[k] <= -3) dist[k][1]++; }
  if (d.mg?.k) conv.push([c, d.mg.k.map(x => x.d + '×' + x.k).join(','), mb, lb, d.margin?.d ?? null]);
  out[c] = [runTxt(s.s, '買', '賣'), runTxt(s.fs, '買', '賣'), runTxt(s.ts, '買', '賣'), runTxt(mb, '增', '減'), runTxt(lb, '增', '減')];
}
console.log('≥3／≤−3', JSON.stringify(dist));
for (const c of ['2421', '2330', '2454', '2308', '2908', '3013', '2883']) console.log(c, JSON.stringify(out[c]));
console.log('mg.k', conv.length, JSON.stringify(conv));
console.log('30 日以上', JSON.stringify(Object.entries(out).filter(([, v]) => v.some(t => t.includes('以上'))).map(([c, v]) => [c, v.filter(t => t.includes('以上'))])));
```

- 用法：
  - `python3 cmp.py 基線/site/data 新/site/data`：回傳 0 = 通過。
  - `node macd_run.js 舊stock.js 舊app.js site/data/stocks old.json`、`node macd_run.js 新stock.js 新app.js site/data/stocks new.json`，再 `python3 macd_cmp.py old.json new.json 2421 2330`：回傳 0 = 結論 0 差異。
  - `node streak_run.js site/stock.js site/data`：列出分佈、實例、`mg.k` 清單與「30 日以上」。
