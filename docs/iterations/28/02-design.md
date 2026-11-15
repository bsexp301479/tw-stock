# 第 28 輪｜UI/UX 設計師：第 27 輪剩餘項目（籌碼時間序列、返回位置、泡泡清單）

- 撰寫日期：2026-11-15（週日）
- 依據：
  - `28/01-analyst.md`：第十一節優先順序（8 項）、第十節限制、第九節「不建議改動」、U28-01～05。
  - `27/02-design.md`（格式、測試鎖定避開表、附錄 diff 做法）、`27/04-qa.md` 第九節（Plotly 直書軸標題字元會旋轉）。
  - `24/03-design.md` 附錄 A：第 24 輪待套用的 diff（`app.css`、`stock.js`、`index.html`，另有 `twstock/` 與 `tests/test_iter24.py`）。
  - 協調者已採用分析師 U28-04 的建議：籌碼圖用「張」、卡片維持「億（估算）」，圖與卡的標題都寫單位，同一張圖不混用。
- 原型作業：
  - scratchpad `ux28d/` 建兩份副本：`orig`（目前工作目錄，含未 commit 的泡泡圖 Y 軸箭頭修正；`app.css?v=39f292f5`、`app.js?v=3a2f69e2`、`stock.js?v=51cc333a`）、`proj`（本設計）。兩份都**不含 `.env`**、`.git`。
  - `proj` 的 diff 就是附錄 A（`site/` 與 `tests/`，不含 `site/data`），**PG 可以直接套用**；新測試全文在附錄 B。
  - 8001 預覽 `proj`（`python3 -u -m twstock serve --port 8001 --no-browser`），每次改檔重算 `?v=`，開頁前用 `fetch(…, {cache:'reload'})` 強制重新驗證，確認載入的 `?v=` 與 `proj/site/index.html` 相同才量測。8000 沒有碰。
  - 結束時已 `pkill -f "twstock serve --port 8001"`，`lsof -iTCP:8001 -sTCP:LISTEN` 無輸出；localStorage 刪除本次產生的 `tw.group`、`tw.focus`、`tw.rank2`，`tw.todayTab`、`tw.stockTab` 還原為分析師記錄的原值 `ov`、`k`（`tw.theme` 測完即刪）；視窗已恢復 desktop。
  - 沒有執行 `collect`、`history`、`export`、`setup-db`，沒有 DB 寫入，沒有修改專案程式與測試、沒有 commit。**本文件是唯一寫進專案的檔案。**
- 編號：本輪設計項目用 **D28-01～D28-08**。
- 用詞：照舊不用「買進、賣出、反彈、見底、買點、超賣、超買、推薦、強勢股、飆股、勝率、建議（投資）、低估、高估」；新文案只描述資料（`test_iter28.test_no_advice_words` 檢查本輪新增的行與新函式，「借券賣出」是官方資料欄名，扣除後再比對）。

---

## 〇、結論摘要

| 項目 | 結果 |
|---|---|
| 本輪範圍 | D28-01～08，涵蓋分析師第十一節**全部 8 項**：U25-07／U25-13／U27-26（籌碼）、O-2、U28-01、U27-20（含 U28-05）、O-4、U28-02、U28-03、O-5、U27-02 其餘 |
| 不放本輪 | 分析師標「不做」：U25-22、U25-35 色點、O-1；標「延後」：U27-31、U25-32、新訊號依面向排序；另見 2-1 |
| 需使用者決定 | 6 項（第五節），本輪都先上建議預設 |
| 變更量 | `app.css` ＋8／−1、`app.js` ＋62／−17、`stock.js` ＋102／−21、`index.html` ＋3／−3：**程式＋CSS 新增 172 行、刪除 39 行**（不含 `?v=`） |
| 舊測試 | **改 4 個檔、6 行**（`test_iter12:83`、`test_iter13:48`、`test_iter22:178、179`、`test_iter27:98、125`），只換字面、保留原意圖，理由見 4-2 |
| 新測試 | `tests/test_iter28.py` 10 個測試（239 行）。`proj` 執行 `test_iter01～23、25～28` **全部通過**，`node --check` 通過；用 `orig` 跑 `test_iter28`：9 個功能測試全部失敗、`test_no_advice_words` 通過（反向驗證成立） |
| 和第 24 輪 | **先 28 後 24（建議）**：第 24 輪 `app.css`、`stock.js`、`twstock/`、`tests/` 都乾淨套用，只有 `index.html` 的 `?v=` 衝突；合併後 `test_iter01～28`（含 `test_iter24`）全部通過。先 24 後 28：第 28 輪 `app.css` 檔尾 1 段要手動貼（見 4-4） |
| 資料口徑 | 不新增欄位、不改 `site/data`、不改 `twstock/`。籌碼圖只把既有每日序列（`insti.f/t/dl`、`mg.mb/sb/lb`、`prices`）在前端累加或直接畫 |

---

## 一、設計原則與風格方向

### 1-1 延續既有視覺語言

- 圓角卡片、膠囊分段鈕（`segHTML`）、紅漲綠跌、第 25 輪色彩 token、第 26 輪深淺色切換都不動。**不新增色彩 token**。
- 新元件都由既有元件組成：
  - 籌碼分組小卡用走勢分頁的 `.metrics.kv`（無縫格線，卡片間用細線分隔），不再是一張張浮起的卡片。
  - 圖表標籤沿用 `.ch-label`＋`.lg` 色塊圖例；線色沿用 `INVESTORS`（外資、投信、自營）與融資 `#1C7ED6`、借券 `#E8590C`（和走勢分頁同色，同一個東西在全站同一種顏色）。
  - 泡泡清單用 `.tbl`＋`td.nm` 兩行名稱欄；象限字用既有象限色（漲潮 `--up`、輪動 `--amber`、觀望 `--blue`、退潮 `--dn`）。
- 圖表沿用 Lightweight Charts 4.2.0、Plotly 2.35.2，不加函式庫。新圖沒有直書軸標題（第 27 輪 Y 軸箭頭的教訓），單位寫在圖上方的 `.ch-label` 文字。

### 1-2 本輪主軸：「看得出趨勢」與「回得去原處」

| 類型 | 項目 | 原則 |
|---|---|---|
| 看不出趨勢 | 籌碼分頁只有卡片（U25-07、13、U27-26） | 數字（最新值）和圖（區間變化）放在同一組、同一屏；圖用資料原生單位（張） |
| 讀錯 | 期貨表「-1,29」（O-2）、刻度只露半截（U28-03）、提示框正值沒有「+」（O-5） | 畫面上看到的數字必須完整、帶正負號 |
| 回不去 | 返回列表回到頂端（U28-01）、手機泡泡要往返捲動（U27-20） | 返回＝回到剛才的位置；在原地展開，不捲走 |
| 太佔位 | K 線和成交量被隔開（O-4）、融資融券標題區比圖高（U28-02） | 相關的圖相鄰；說明文字縮短，細節放 `title` |

### 1-3 不改的東西

第 25～27 輪與分析師第九節「不建議改動」全部保留，本輪特別避開：

- 泡泡圖 Y 軸未 commit 的箭頭修正（`'← 偏流出　…　偏流入 →'`）。
- 第 27 輪 D27-05 的 `#/today`、`#/rank` 網址補正（`history.replaceState(null, …)` 字面不動）。
- 走勢分頁的法人、融資融券子圖：保留、不收合、不搬到籌碼分頁（D28-06 只縮標題區與刻度）。
- `hlTag` 輸出、新訊號手機第二列、第一欄固定、`tw.*` 鍵名。**本輪不新增任何 localStorage 鍵**。

---

## 二、本輪範圍（D28-xx）

| D28 | 對應分析師 | 內容 | 檔案 | 新增行數（約） |
|---|---|---|---|---|
| D28-01 | U25-07、U25-13、U27-26、U28-04（第 1 名） | 籌碼分頁：圖表區間 20／60／120／全部（預設 60）；「法人買賣超」組（4 卡＋收盤小面板＋外資／投信／自營區間累計）、「信用交易」組（4 卡＋融資餘額圖）、「借券賣出」組（2 卡＋借券餘額圖＋說明）；日期只寫在組標題 | stock、css | 72 |
| D28-02 | O-2（第 2 名） | 375 期貨未平倉表欄距 6px → 4px（原本的 5px 規則被後面的 `.tbl` 蓋掉），「增減」不再被切 | css | 1 |
| D28-03 | U28-01（第 3 名） | 瀏覽器返回／前進時還原該頁的捲動位置；點連結進新頁才到頂端 | app | 12 |
| D28-04 | U27-20、U28-05（第 4 名） | 泡泡圖手機（≤720）加「圖｜清單」，預設清單；每列族群、象限、近5日、日均差、漲跌、成交；點列在下方展開成分股，不捲走 | app、css | 40 |
| D28-05 | O-4（第 5 名） | 手機關鍵數字列移到成交量圖之後（K 線與成交量相鄰）；最後一列不留空格 | stock、css | 2 |
| D28-06 | U28-02、U28-03（第 6 名） | 融資融券標題區：說明改 `title`、圖例只列目前的線＋券資比（130 → 60px）；法人子圖刻度上下對稱＋留邊；各圖刻度文字放不下就不畫（不會只露半截） | stock、css | 9 |
| D28-07 | O-5（第 7 名） | 泡泡提示框：customdata 先格式化（正值帶「+」、近 5 日和泡泡上同一種小數位） | app | 3 |
| D28-08 | U27-02 其餘（第 8 名） | `#/stock/代號/錯分頁`、ETF 的 `fund` 補成實際分頁；`#/watch/x`、`#/bubble/x` 去掉多餘的段；`#/etf/非 ETF` 改「找不到」 | app、stock | 4 |
| 合計 | 8 名全部 | | | **約 172 行**（另刪 39 行；`index.html` 的 `?v=` 3 行另計） |

### 2-1 不放本輪的項目與理由

| 項目 | 理由 |
|---|---|
| U25-22 子圖收合、U25-35 面向色點、O-1 編輯 ✕ 寬度 | 分析師標「不做」（第四、五、七節）。U28-02 縮標題區已省下 70px |
| U27-31 排行列尾 ☆ | 分析師標「延後」；D28-03 修好返回位置後，「點進去 ☆ 再返回」只多一步 |
| U25-32 圖表骨架、未知路由提示元件 | 分析師標「延後」；D28-08 只做網址補正與文案 |
| 新訊號標籤依面向排序 | 分析師標「延後」 |
| 法人 20 日卡（`n20`） | 分析師寫「可加」。加了法人組變 5 張卡，手機 2＋2＋1 留空格；60 日區間累計圖已能回答「1～3 個月加碼或減碼」。列入第五節 |
| 泡泡清單表頭點選排序、清單模式回放 | 分析師寫「不是必要」「可以不提供」。清單固定依近 5 日由大到小，只顯示最新一天 |
| U28-05 手機泡泡大小 | 分析師建議做清單後不必再調泡泡；清單直接顯示成交額 |
| 外資持股比率、集保分散、分點、融資維持率序列、個股法人官方金額序列、借券占股本序列 | 需要新資料（分析師第一節「需新資料」），列入第五節給 PM |

---

## 三、各項規格

> 量測環境：8001 預覽 `proj`；內建瀏覽器仿真 375×812（mobile preset）、1024×800，色調用 `resize_window colorScheme` 切換；對比依 WCAG 2.x，背景色由元素往上疊算（含半透明），方法同第 27 輪 7-2。圖表內文字（刻度、十字線標籤、圖例）都有截圖放大檢查實際字形。「原本」數值取自分析師附錄或本輪在 `orig` 實測。資料日 2026-11-13。

### D28-01 籌碼分頁：分組小卡＋時間序列（U25-07、U25-13、U27-26、U28-04）

**版面（由上而下）**

```
[走勢｜籌碼｜基本面]
圖表區間 [20 日｜60 日｜120 日｜全部]                ← 一個控制，下方 4 張圖共用
┌ 法人買賣超　11/13，億，估算（張數 × 收盤） ───────────┐
│ 法人1日｜法人5日｜外資5日｜投信5日（.kv，桌面一列、手機 2×2） │
│ 收盤（還原）　11/13　收 2,350           ← 64px 小面板   │
│ 區間累計買賣超（張，未還原；從區間第一天起加總）           │
│ ━外資 -262,814（當日 -2,618） ━投信 … ━自營 …          │
│ （三條線＋0 虛線）                       ← 150px       │
└─────────────────────────────────────────┘
┌ 信用交易　11/13 ───────────────────────────────┐
│ 融資餘額｜融券餘額｜券資比｜融資使用率                    │
│ 融資餘額（張）　11/13 ━融資 32,376　融券 50　券資比 0.15% │
│ （融資餘額線）                           ← 110px       │
└─────────────────────────────────────────┘
┌ 借券賣出　11/13，晚上 8 點半以後更新 ──────────────────┐
│ 借券賣出餘額｜借券占股本                               │
│ 借券賣出餘額（張）　11/13 ━借券賣出 23,826  ← 110px     │
│ 借券賣出包含避險、套利…不等於看空…占股本以目前發行股數計算。 │
└─────────────────────────────────────────┘
[主動 ETF 持有]（不變）
```

**規則**

- 單位：卡片維持「億，估算」，寫在法人組標題（站內同一寫法：今日頁「11/13，億，估算，不含 ETF」）；圖一律「張」，寫在每張圖的 `.ch-label`。同一張圖不混用。
- 日期：每組標題寫一次（法人用 `flow_date`、信用用 `margin.d`、借券用 `sbl.d`），卡片內的「11/13」「至 11/13」「資料 11/13」拿掉（原本 10 張卡寫 10 次）。卡片副字只留 1 日／5 日增減、連續天數、融券倍數、停資停券註記。
- 區間：預設 60 個交易日；20／60／120／全部（約 252）。放在分頁鈕下方一列「圖表區間」，明示是給圖用的（卡片永遠是最新值）。**不存 localStorage**，只在這次瀏覽記住（模組變數 `chipN`），所以切深淺色、換股票時保留，重新整理回 60。
- 法人圖：
  - 收盤小面板（64px，還原價；ETF 沒有法人組，所以也沒有這張）和累計圖（150px）上下分開，**不用雙 Y 軸**；兩張右側刻度同寬（`minimumWidth: 76`），時間軸對齊。
  - 累計 = 從區間第一天起逐日加總；缺值的那天不畫點、不補 0。0 軸畫虛線（`createPriceLine`，不顯示標籤）。
  - 圖例：每條線「累計」用紅綠數字、「（當日 ±N）」用 `--text2`。最新一天法人尚未公布時，圖例改顯示最近有資料的那天並寫出日期（同走勢分頁法人圖例的規則）。
- 信用、借券圖：一張圖一條線、右側刻度就是那條線（延續 D27-07）。融券太小（2330 只有 50 張），只放在融資圖例的數字。有面額變更、減資事件（`mg.k`）時，標籤加「面額變更、減資前依官方換算」，沒有就不寫。
- 互動：四張圖十字線同步、圖例跟著變；**不能拖曳、縮放**（`handleScroll/handleScale: false`），區間只由分段鈕決定，手機上下捲頁不會被圖吃掉。
- 釋放：籌碼圖放進 `charts` 陣列，`disposeStockCharts`／`disposeKCharts` 一併釋放；切區間先釋放再重建（實測重建後畫面上的圖表數維持 4）。
- 深淺色：切換時 `redrawKeepScroll → route()` 整頁重畫，顏色在畫圖當下取 token；實測切換前後捲動位置都是 1100、區間維持 120 日。
- 版面：`.chip-g .kv` 桌面 `grid-auto-flow:column`（一組一列，不再 8＋2）；≤520 兩欄；只有一張卡（ETF 借券）時佔滿一列。

**量測**

| 項目 | 375 淺 | 375 深 | 1024 淺 | 1024 深 |
|---|---|---|---|---|
| 2330 頁高（原本 1,975） | 2,708 | 同左 | 1,914 | 同左 |
| 三組高度（2330） | 523／351／344 | 同左 | 407／275／308 | 同左 |
| 每組卡片列數 | 2（2×2）、2、1 | 同左 | 1、1、1 | 同左 |
| 0050（ETF）組數／圖數 | 2 組／2 張；頁高 1,241 | 同左 | 2 組；頁高 1,004 | 同左 |
| 8299、2421 頁高 | 2,240、1,835 | 同左 | — | — |
| `scrollWidth` | 375 | 375 | 1024 | 1024 |
| 組標題副字、圖標籤、圖例「當日」 | 6.39 | 7.38 | 6.39 | 7.38 |
| 圖例紅／綠數字 | 5.14／5.21 | 5.34／5.34 | 同 375 | 同 375 |
| 「圖表區間」字 | 5.70（底 `--bg`） | 7.97 | 同左 | 同左 |
| 圖表刻度文字（canvas，`--text2`） | 6.39 | 7.38 | 6.39 | 7.38 |

- 數值核對：2330 切「20 日」，圖例外資 **-206,526**、投信 **+49,235**，和分析師附錄相同；60 日外資 -262,814。
- 8299 的「外資5日 -12.1億、連買 3 日」：圖例與 20 日累計線直接看出前兩天大量減碼、後三天小量加碼。
- 截圖放大：刻度、十字線日期標籤（「2026/10/29」）、價格標籤（深底白字）字形正常；0050 借券圖原本最上面「280,000」只露下半，加 `entireTextOnly` 後不畫半截字。
- **線條（非文字）對比**：外資 `#4C6EF5` 4.32／4.11、自營 `#AE3EC9` 4.85／3.66、融資 `#1C7ED6` 4.20／4.23、借券 `#E8590C` 3.58／4.96（淺／深）；**投信 `#F08C00` 淺色只有 2.48**（< 3:1）。這是走勢分頁法人子圖既有的顏色，本輪依「不新增色彩」沿用，用 2px 線寬與圖例數字補足；是否調色列入第五節。

### D28-02 期貨未平倉表 375 不橫捲（O-2）

- 原因：`@media (max-width:520px){… .oi-tbl th,.oi-tbl td{padding:8px 5px}}`（第 13 輪）在檔案中排在 `@media (max-width:520px){ .tbl th,.tbl td{padding:8px 6px} }` 之前，權重相同，被後者蓋掉，實際是 6px。表寬由數字決定（`107,056`、`-100,870`），表頭不是瓶頸（實測把表頭改兩行，表寬仍是 321，已撤回）。
- 做法：第 28 輪區塊加 `@media (max-width:520px){table.oi-tbl th,table.oi-tbl td{padding:8px 4px}}`（權重較高）。原本的 5px 規則不動（`test_iter13` 鎖定同一行的 `nth-child(n+6)`）。

| 量測 | 原本 | 375 淺／深 | 1024 |
|---|---|---|---|
| 表寬／框寬 | 321／309 | **309／309**（自然寬度 301） | 457／457（不變，≥521 照舊 6px） |
| 增減欄 | 「-1,29」「+1,02」「-2,58」 | 「-1,297」「+1,022」「-2,584」完整（放大截圖確認） | 不變 |

- 已知限制：寬度 360 的手機框寬 294，仍會橫捲約 7px（本輪只量 375，和分析師一致）。

### D28-03 返回時還原捲動位置（U28-01）

**做法**

- 每一筆瀏覽紀錄在 `history.state.k` 有自己的鍵（新紀錄的 state 是 `null`）。`route()`：
  1. 開始時讀 `k = history.state?.k`，把 `scrollKey` 設成 `null`（換頁中內容變短造成的捲動不記）。
  2. 畫完後 `scrollTo(0, k && scrollAt[k] || 0)`：返回／前進到看過的頁 → 還原；新頁 → 頂端。
  3. `scrollKey = k || Date.now() + Math.random()`，必要時 `history.replaceState({ k }, '')`（不帶網址，保留各頁補正後的網址；D27-05 的 `replaceState(null, …)` 在渲染中執行，之後才蓋上鍵，所以不衝突）。
- `scroll` 監聽（passive）把 `scrollY` 記到 `scrollAt[scrollKey]`。`history.scrollRestoration = 'manual'`：內容是重畫的，瀏覽器自己還原會被 `route()` 蓋掉。
- 只存在記憶體，重新整理後回到頂端。第 26 輪 `redrawKeepScroll` 不變（同一筆紀錄重畫，位置一樣）。

**量測（375 淺）**

| 情境 | 結果 |
|---|---|
| 排行 `#/rank/n+` 捲到 1,576 → 點 5274 → 返回 | 個股頁 scrollY 0；返回後 **1,576**（原本 0） |
| 再「前進」到 5274 → 再返回 | 0 → 1,576 |
| 泡泡清單展開「塑膠」、捲到 700 → 點成分股南亞 → 返回 | **700**，「塑膠」仍展開 |
| 籌碼分頁捲到 1,100 → 切深色 → 切淺色 | 1,100、1,100（第 26 輪行為不變） |
| 點底部選單到另一頁 | 0 |

- 已知限制：個股頁切「走勢／籌碼」用 `history.replaceState(null, …)`（第 25 輪既有，`test_iter12` 鎖定字面附近），那一筆紀錄的鍵會被清掉，之後返回到那一頁從頂端開始。影響小，不在本輪處理。

### D28-04 泡泡圖手機「圖｜清單」（U27-20、U28-05）

**規格**

- 只有 ≤720 顯示 `[圖｜清單]`（`#bvSeg`，放在 `[類股｜產業鏈｜概念股]` 前面）；預設**清單**（理由：手機 34 顆泡泡只有 12 顆有標籤，大小也看不出差別）。選擇存在 `App.bubbleView`，只在這次瀏覽記住，不新增 localStorage 鍵（第五節）。桌面完全不變。
- 清單模式：標題「板塊資金」，副字「近 5 日法人淨流入由大到小」；不畫 Plotly，也不顯示明細卡與回放說明（象限說明卡保留）。
- 表格（`.bl-tbl`，最新一天，依近 5 日由大到小；最新一天沒有值的族群不列）：

| 欄 | 內容 | 來源 |
|---|---|---|
| 類股／產業鏈／概念股（依分段鈕） | 第一行名稱（不截斷，可換行）；第二行象限字，用象限色 | `name`、`quadrant` |
| 近5日 | `yi()`，例「+201億」 | `frames[k][0]` |
| 日均差 | `sgn(v, 1)`，例「+30.7」 | `frames[k][1]` |
| 漲跌 | 例「+4.16%」 | `frames[k][2]` |
| 成交 | 整數億，例「3,728」 | `frames[k][3]` |

- 表上方一行說明欄位與單位：「近5日 = 近 5 日法人累計（億）；日均差 = 近 5 日日均 − 20 日日均（億/天），正 = 偏流入；成交 = 成交額（億）。點一列看成分股」。
- 點一列：在該列下方插入 `tr.bl-x`（跨 5 欄），內容是原本明細卡的同一份資料（`groupMeta`＋`groupRows`，抽成共用函式），外框 `.panel-list`（最高 420px，自己捲動）；再點同一列收合；點另一列換展開。重畫後用 `scrollBy` 把**點的那一列留在原位**（上方有展開的列收合時不會跳走）。
- 從今日頁點族群長條（`[data-group]`）：設定 `App.blOpen` 並在 `route()` 捲到頂之後，用 `requestAnimationFrame` 把該列捲到表頭下方（`scroll-margin-top: top-h + 44px`）。
- 內層表格：`.bl-x .tbl-wrap{width:0;min-width:100%}` 讓展開的成分股表不撐寬清單（原本會把「成交」欄擠出畫面），自己橫捲；`.panel-list{--th-y:0px}` 加上 `stickHeads()` 排除 `.panel-list`，避免第 27 輪的表頭位移套到內層捲動框（明細卡原本也有同樣的風險）。

**量測**

| 項目 | 375 淺 | 375 深 | 1024 |
|---|---|---|---|
| 表寬／框寬 | 309／309（類股、產業鏈、概念股皆同） | 同左 | 不顯示清單 |
| 列高 | 類股平均 53、最高 53；產業鏈平均 54、最高 73；概念股 53 | 同左 | — |
| 清單卡高度 | 類股 1,927、產業鏈 2,212、概念股 867 | 同左 | — |
| 展開「塑膠」 | 點的列位置不變（415 → 415）；內層表 299 寬、內容 309（橫捲 10px）；高 420 | 同左 | — |
| 從今日點「通信網路」 | 該列頂端 99（= 頂欄 55＋表頭 44），已展開 | — | 照舊開明細卡 |
| 象限字對比（最低） | 漲潮 4.79（展開列 `--card2` 底）、其他 5.21 | 漲潮 4.91、觀望 5.05、退潮 5.34、輪動 8.23 | — |
| 數字欄最低對比 | 4.79 | 4.91 | — |
| 切「圖」 | 泡泡與明細卡出現；返回後仍是「圖」 | 同左 | `#bvSeg` 不存在 |
| `scrollWidth` | 375 | 375 | 1024 |

### D28-05 手機 K 線與成交量相鄰（O-4）

- 手機關鍵數字列由 `$('#kC').after(…)` 改 `$('#vC').after(…)`（K 線 → 量 → 數字列 → 法人…）；CSS `#kC+.kv` 改 `#vC+.kv`，加兩條最後一列補滿：`:last-child:nth-child(3n+1)` 跨 3 欄、`(3n+2)` 跨 2 欄。桌面不變（數字列在頁首卡）。

| 量測（375） | 原本 | 本輪 |
|---|---|---|
| K 線頂端（2330／8299／2421／0050） | 561／586／478／504 | 561／586／478／504（不變） |
| K 線底 → 成交量頂 | 286 | **28** |
| 數字列高 | 250（2330 等） | 235（7 格：3＋3＋1 跨滿；「週轉率」副字一行） |
| 0050 數字列 | 2 格＋1 空格 | 2 格（1/3＋2/3，不留空格） |

### D28-06 融資融券標題區、法人子圖刻度（U28-02、U28-03）

- 融資融券標題區（`.ch-label.mg-l`）：
  - 「餘額」和單位合成 `#gUnit`：「餘額（張）」；換算說明「面額變更、減資前的餘額依官方換算」移到 `title`。原始價模式照舊「餘額（張，官方原始）」。
  - 圖例只列目前選的線（融資／融券／借券）＋券資比（選借券時不列券資比），其他數字在籌碼分頁看。
  - `align-items:center`，「餘額（張）」和分段鈕垂直置中；`.ch-label{row-gap:2px}`（全站子圖標籤換行時不再留 12px）。
- 法人子圖：`autoscaleInfoProvider: symScale`，刻度以 0 為中心上下對稱；`scaleMargins` 上下各 0.1。
- 所有走勢圖與籌碼圖的右側刻度加 `entireTextOnly: true`：放不下的刻度文字不畫，不會只露半截。

| 量測（375） | 原本 | 本輪（淺／深相同） |
|---|---|---|
| 融資融券標題區（股票／ETF） | 130／100 | **60／60** |
| 法人子圖標題區 | 48 | 38 |
| 2330 法人子圖刻度 | 「40K」只露下半 | 40K／0／-40K 完整（放大截圖） |
| 8299 法人子圖刻度 | 只有 0、-4K | **4K／0／-4K** |
| 8299 融資子圖最上面刻度 | 「15K」只露下半 | 不畫半截字，顯示 12.5K、10K |
| 2330 走勢分頁頁高 | 2,682 | 2,578 |

- 取捨：對稱刻度時，正負差很多的股票（2330 外資大量賣超）正值柱子會比較矮，但這正是兩邊量級的真實比例（分析師 U28-03 要的「和負值比較」）。若使用者偏好原本的自動刻度，只要拿掉 `autoscaleInfoProvider`（第五節）。

### D28-07 泡泡圖提示框格式（O-5）

- customdata 改成先格式化的字串：`[名稱, amount(近5日), sgn(日均差, 1)+'億/天', sgn(漲跌)+'%', fmt(成交)+'億']`；hovertemplate 只用 `%{customdata[n]}`，不再有 `:+.1f` 等 Plotly basic 不認得的格式。
- 「近5日」用泡泡上同一個 `amount()`（≥10 取整、<10 一位小數）。
- 實測（1024 深，「半導體」）：提示框「近5日 **-4.3億**」（泡泡上也是 -4.3億）、「5日日均−20日日均 **+286.7億/天**」、「漲跌 **+3.81%**」、「成交 3,728億」；主控台沒有 `bad format` 警告。

### D28-08 未知分頁與非 ETF 代號（U27-02 其餘）

| 網址 | 原本 | 本輪（375、1024 相同） |
|---|---|---|
| `#/stock/2330/abc` | 顯示上次分頁、網址不變 | 補成 `#/stock/2330/k`（實際顯示的分頁） |
| `#/stock/0050/fund` | 顯示走勢、網址不變 | 補成 `#/stock/0050/k` |
| `#/stock/2330`（沒有分頁） | — | 不補（第 25 輪 D25-08：同一檔回到上次分頁，刻意保留） |
| `#/watch/abc`、`#/bubble/x` | 網址不變 | 補成 `#/watch`、`#/bubble` |
| `#/etf/zzz` | 「zzz 的持股資料尚未支援（目前支援…）」、分頁標題「zzz 持股」 | 「找不到 zzz 的資料。可用上方搜尋框查代號或名稱，或回 ETF 列表」；分頁標題「ETF｜台股資金流」 |
| `#/etf/0050`（不是主動 ETF） | 轉到 `#/stock/0050` | 不變 |
| `#/stock/9999` | 找不到頁 | 不變 |

- 補正用 `history.replaceState(history.state, …)`，保留 D28-03 的捲動鍵。

---

## 四、不能破壞的事項

### 4-1 已確認

- 375／1024 × 淺／深：今日期貨、泡泡圖（清單／圖）、排行、個股走勢與籌碼（2330、2421、8299、0050）`scrollWidth` 等於視窗寬。
- 主控台：唯一錯誤是測試 `#/stock/9999` 時的 404（既有行為，顯示「找不到」頁）。
- 第 26 輪切換深淺色：籌碼圖、泡泡清單都重畫並保留捲動位置。
- 桌面版泡泡圖、明細卡、走勢分頁頁首數字列不變。

### 4-2 避開的測試鎖定

| 鎖定 | 出處 | 本設計怎麼避開 |
|---|---|---|
| `if (tab !== 'k') return;`、`window.disposeStockCharts(); window.renderStock(code);`、`STOCK_TABS` | `test_iter12:102～104` | 籌碼圖在 `if (tab !== 'k') return;` 之前呼叫，字面不動 |
| `const ic = $('#iC') ? mk('iC', false) : null;` | `test_iter15:98` | 不動，對稱刻度另起一行 |
| `lb: [LB, '#E8590C']`、`for (const k of ['mb', 'sb', 'lb'])` | `test_iter11:225` | 不動 |
| `segHTML('mgSeg'`、`mgView` 行為 | `test_iter12:82`、`test_iter27.test_margin_single_series` | 不動；圖例改用既有的 `mgView(G)` |
| `[mc, oSer, oVal]` | `test_iter18:99` | 不動（籌碼圖用自己的 `anchors`） |
| `!E && runTxt(balStreak(…))` 兩行 | `test_iter22:180、181` | 不動 |
| `noteHTML` 字面呼叫數 | `test_iter13`、第 24 輪 `test_iter24`（== 8） | 本輪不新增 `noteHTML`；借券說明維持純文字 |
| `.oi-tbl th:nth-child(n+6),…{display:none}` | `test_iter13:100` | 該行不動；新規則另寫在第 28 輪區塊 |
| `history.replaceState(null, '', '#/today/' + t0)`、`'#/rank/' + by` | `test_iter27:108、110` | 不動；捲動鍵在渲染後才蓋上 |
| `stickHeads` 的 node 測試 | `test_iter27.test_long_table_page_scroll` | 只改選擇器（加 `:not(.panel-list)`），測試用假的 `querySelectorAll`，照樣通過 |
| `redrawKeepScroll`、`setupTheme` | `test_iter26.test_toggle_flow` | 不動 |
| `'id="mC"' < perfHTML < 'id="sigTitle"'` | `test_iter23:216` | 走勢分頁區塊不動 |
| `holdTag` 輸出 | `test_iter05:422` | 不動（D28-08 只改 `renderHoldings` 找不到時的文案） |
| node 14 | 測試在 node 執行的函式 | 新程式不用 `.at()`、`replaceAll`（`buildChip` 的日期用 `split/join`） |

**非改不可的舊測試（4 個檔、6 行）**：

| 檔案：行 | 原本 | 改成 | 理由 |
|---|---|---|---|
| `test_iter12.py:83` | `"...mgCards, ...slCards]" in js` | `"cardsHTML(cards)" in js and "mgCards, data.mg ?" in js and "slCards, data.mg?.lb ?" in js` | 信用、借券卡改成各自一組（`chipSec`），不再展開成同一個陣列；原意圖「信用卡在籌碼分頁」保留 |
| `test_iter13.py:48` | 切片 `"${(tab === 'k' ? ["` 到 `": tab === 'chip' ?"` | 切片 `"${cardsHTML(tab === 'k' ? ["` 到 `"\n        : [['本益比'"` | 籌碼分頁不再走同一個三元式；仍檢查走勢分頁卡片不含開盤、成交量、昨收，含 `...mtCards]` |
| `test_iter22.py:178` | `"subs(fd, runTxt(s?.s, '買', '賣'))" in STK` | `"['法人1日', yi(s?.n1), cls(s?.n1), runTxt(s?.s, '買', '賣')]" in STK` | 日期移到組標題（D28-01）；仍檢查法人連買／連賣天數寫在法人1日卡 |
| `test_iter22.py:179` | `subs('至 ' + fd, runTxt(s?.fs …))`、`ts` 同 | `['外資5日', …, runTxt(s?.fs, '買', '賣')]`、`['投信5日', …, runTxt(s?.ts, '買', '賣')]` | 同上 |
| `test_iter27.py:98` | `"5日日均−20日日均 %{customdata[2]:+.1f}億/天" in APP` | `"5日日均−20日日均 %{customdata[2]}<br>" in APP` | D28-07 先格式化；仍禁止「加速度」舊文案 |
| `test_iter27.py:125` | `"$('#kC').after(" in STK and "#kC+.kv{" in CSS` | `"$('#vC').after(" in STK and "#vC+.kv{" in CSS` | D28-05 改到成交量之後；仍檢查手機數字列在主圖區內 |

### 4-3 `index.html` 的 `?v=`

| 套用情境 | `app.css` | `app.js` | `stock.js` |
|---|---|---|---|
| 原本（目前工作目錄） | `39f292f5` | `3a2f69e2` | `51cc333a` |
| 只套第 28 輪（附錄 A） | `7b2bc0df` | `528d35a6` | `2d561731` |
| 第 28 輪＋第 24 輪附錄 A（全部） | `9c05d8ff` | `528d35a6` | `fd99de3d` |

- PG 實際套用後若有差異，以 `test_iter23.test_version_hash` 失敗時印出的 3 行為準。

### 4-4 與第 24 輪的衝突點

已在 scratchpad 副本用 `patch -p1` 實測（第 24 輪 diff 取自 `24/03-design.md` 附錄 A 全部 13 個檔）：

| 順序 | `app.css` | `stock.js` | `app.js` | `index.html` | 測試 |
|---|---|---|---|---|---|
| **先 28 後 24（建議）** | 第 24 輪 1 段乾淨套用 | 第 24 輪 5 段乾淨套用 | 第 24 輪不改 | `?v=` 衝突，重算（4-3） | `test_iter01～28` 全部通過（`test_iter24` 每項 ok） |
| 先 24 後 28 | 第 28 輪 2 段中 1 段失敗：檔尾新增的 7 行（第 24 輪在檔尾前插了 `table.dv-tbl` 一行，前後文對不上）。手動把附錄 A 該段的 7 行貼到檔尾即可 | 乾淨套用 | 乾淨套用 | 第 28 輪的 `?v=` 套得上，但要依合併後內容重算 | 同上 |

- 內容上沒有互相依賴：
  - 第 24 輪的 `NET_TIP`（走勢分頁法人圖例「合計」）、`divHTML`（基本面分頁股利表）、`aggregate` 的 `inst.net = I.n?.[i] ?? …` 都不碰本輪修改的程式段；D28-06 的融資融券圖例就在第 24 輪法人圖例的下一段，patch 實測前後文不衝突。
  - 籌碼累計圖只用 `f`、`t`、`dl` 三個序列，不畫「合計」，所以第 24 輪改用官方合計後，不會出現「三條線相加 ≠ 合計」差 1～2 張的情形。
  - 第 24 輪新測試沒有引用本輪改動的字面（已 grep `subs(`、`'資料 '`、`gLegend`、`gUnit`、`kC`、`customdata`、`oi-tbl`、`scrollTo`）；`noteHTML` 字面數仍是 8。

---

## 五、需使用者決定

| 編號 | 項目 | 選項 | 建議預設 | 本輪做法 |
|---|---|---|---|---|
| U27-20 | 泡泡圖手機預設檢視 | A 清單（本輪）；B 圖；C 記住上次（要新增 `tw.bview` 鍵） | **A**：手機泡泡已無法辨識類股 | A，選擇只在這次瀏覽記住 |
| U25-07 | 籌碼圖區間要不要跨次記住 | A 每次 60 日（本輪）；B 記住（新增 `tw.chipN`） | **A**：分析師建議每次 60 日，不新增鍵 | A（同一次瀏覽內保留） |
| 新增 | 投信線色淺色對比 2.48（`#F08C00`，走勢分頁法人子圖同色） | A 維持（全站一致，靠 2px 線寬與圖例數字）；B 淺色主題改深一點的橘（例如 `#C86F00`，約 3.4），走勢與籌碼一起改 | **A 本輪**，下一輪若做全站圖表配色再一起處理 | A |
| U28-03 | 法人子圖刻度 | A 上下對稱（本輪）；B 自動刻度＋只留上緣邊距 | **A**：正負兩側都有刻度，量級可比 | A；改 B 只要拿掉 `autoscaleInfoProvider: symScale` |
| 分析師第一節 | 法人 20 日卡（`n20` 已匯出） | A 不加（本輪）；B 加在法人組（手機 2＋2＋1） | **A**：60 日累計圖已涵蓋 | A |
| 分析師第一節 | 需新資料的籌碼序列：外資持股比率、集保分散、分點、融資維持率序列、個股法人官方金額序列、借券占股本歷史序列 | 由 PM 評估資料來源與收集頻率 | 先做外資持股比率（官方每日公布、和本輪法人圖同一組） | 不動 |

- U28-04（圖用張、卡用億）協調者已採用，本輪照做，不再列為待決。

---

## 六、給 PG 的實作順序與行數

建議直接套用附錄 A（`patch -p1`，路徑前綴 `orig/`、`proj/` 改成 `a/`、`b/`），再新增附錄 B 的 `tests/test_iter28.py`。若要逐項手寫，順序如下（每步跑一次全部測試）：

| 步驟 | 項目 | 行數 | 驗證 |
|---|---|---|---|
| 1 | D28-02 期貨表欄距（CSS 1 行） | 1 | `test_iter13`、`test_iter28.test_oi_table_padding`；375 量表寬 = 框寬 |
| 2 | D28-07 泡泡提示框 | 3 | 改 `test_iter27:98`；`test_iter28.test_bubble_source` |
| 3 | D28-08 網址補正、`#/etf` 找不到 | 4 | `test_iter28.test_unknown_routes` |
| 4 | D28-03 返回位置（`route()`、`init`） | 12 | `test_iter26`、`test_iter27`、`test_iter28.test_route_scroll_restore`；375 排行實測 |
| 5 | D28-05 數字列位置 | 2 | 改 `test_iter27:125`；375 量 K 底 → 量頂 = 28 |
| 6 | D28-06 標題區、對稱刻度、`entireTextOnly` | 9 | `test_iter11`、`12`、`15`、`test_iter28.test_k_tab_layout`、`test_margin_legend_node`；放大截圖看刻度 |
| 7 | D28-01 籌碼分頁（`cardsHTML`、`chipSec`、`buildChip`、CSS） | 72 | 改 `test_iter12:83`、`test_iter13:48`、`test_iter22:178、179`；`test_iter28.test_chip_groups_source`、`test_chip_charts_node` |
| 8 | D28-04 泡泡清單（`bubbleList`、`groupMeta`、`groupRows`、CSS、`stickHeads` 選擇器） | 40 | `test_iter27.test_long_table_page_scroll`、`test_iter28.test_bubble_list_node`、`test_bubble_source` |
| 9 | `?v=` 重算 | 3 | `test_iter23.test_version_hash` |
| 合計 | | **約 172 行新增、39 行刪除；舊測試 6 行** | `for f in tests/test_iter*.py; do python3 $f; done` 全部通過；`node --check site/app.js site/stock.js` |

注意：

- node 是 v14，測試會在 node 執行 `buildChip`、`aggregate`、`route`、`bubbleList`、`groupRows`、`symScale`、融資融券圖例區段；不要在這些地方用 `.at()`、`replaceAll`。
- 本輪**不新增 localStorage 鍵**（`chipN`、`App.bubbleView`、`App.blOpen` 都只在記憶體）。
- `buildChip` 一定要把圖放進 `charts`（`disposeKCharts` 才會釋放）；切區間時它自己先 `disposeKCharts()`。

---

## 七、給 QA 的驗證清單

### 7-1 前置

1. 8001 啟動後，主控台 `await fetch('/app.js',{cache:'reload'})`（`/`、`app.css`、`app.js`、`stock.js` 都要），重新整理，確認 `document.scripts` 與 stylesheet 的 `?v=` 與 4-3 表相同。
2. 開始前記下 localStorage 的 `tw.*` 鍵；結束時還原。本輪不新增鍵（`tw.focus`、`tw.group`、`tw.rank2`、`tw.stockTab`、`tw.todayTab` 是既有鍵，操作中會被寫入）。
3. 尺寸：`resize_window` mobile（375×812）、1024×800；色調 `colorScheme: 'light'／'dark'`。結束時 preset desktop。
4. 量測工具同第 27 輪 7-2（`rgb`、`Lm`、`bgOf`、`CR`、`crEl`）。

### 7-2 逐頁清單（每頁 × 375／1024 × 淺／深）

| 頁面 | 檢查 | 量測方法 | 期望值 |
|---|---|---|---|
| 全部頁 | 不橫捲 | `document.documentElement.scrollWidth` | = 視窗寬 |
| 個股籌碼 2330 | 分組 | `.chip-g h2` | 法人買賣超、信用交易、借券賣出 |
| 個股籌碼 | 日期只寫一次 | `.chip-g .kv .s` 文字 | 不含「11/13」「至」「資料」 |
| 個股籌碼 | 單位 | 法人組 `.sec-h .muted`；累計圖 `.ch-label` | 「11/13，億，估算（張數 × 收盤）」；「區間累計買賣超（張，未還原；…）」 |
| 個股籌碼（1024） | 一組一列 | 每組 `.kv .card` 的 top 去重數 | 1、1、1 |
| 個股籌碼（375） | 兩欄 | 同上 | 2、2、1；ETF 借券一張卡佔滿 |
| 個股籌碼 | 區間 | 點「20 日」 | `#ciCL` 外資 -206,526、投信 +49,235（2330）；`charts.length` = 4 |
| 個股籌碼 | 十字線 | 滑過累計圖 | 收盤面板與融資、借券圖同步出現十字線；四個圖例同一天 |
| 個股籌碼 | 拖曳 | 在圖上左右拖、滾輪 | 圖不移動、不縮放；375 上下滑動頁面正常捲動 |
| 個股籌碼 | 刻度 | 放大截圖右側刻度、十字線標籤 | 沒有只露半截的字；0 軸虛線 |
| 個股籌碼 | 對比 | `crEl` | 淺：文字 ≥ 6.39、紅綠 5.14／5.21；深：7.38、5.34 |
| 個股籌碼 | 深淺色 | 切 120 日、捲到 1,100，切換色調 | 圖重畫、仍是 120 日、scrollY 1,100 |
| 個股籌碼 0050 | ETF | 組數、`charts.length` | 2 組（信用、借券）、2 張圖；沒有收盤面板 |
| 個股走勢（375） | K 線位置 | `#kC` 頂端＋scrollY | 2330 561、8299 586、2421 478、0050 504 |
| 個股走勢（375） | K 線與量相鄰 | `#vC` 頂 − `#kC` 底 | 28 |
| 個股走勢（375） | 數字列 | `.metrics.kv` 位置與高 | 在 `#vC` 之後；2330 高 235，「週轉率」跨 3 欄 |
| 個股走勢 | 融資融券標題區 | `.mg-l` 高 | 375：60（股票、ETF）；1024：32 |
| 個股走勢 | 融資融券圖例 | 切融資／融券／借券 | 只列目前那條線＋券資比（借券時沒有券資比）；`#gUnit` 的 `title` 是換算說明（還原時） |
| 個股走勢 8299 | 法人子圖刻度 | 放大截圖 | 4K／0／-4K |
| 個股走勢 8299 | 融資子圖頂端 | 放大截圖 | 沒有半截「15K」 |
| 今日期貨（375） | 未平倉表 | `.oi-tbl` 寬 vs `.tbl-wrap` `clientWidth`；放大截圖 | 309 = 309；「-1,297」「+1,022」「-2,584」完整 |
| 今日期貨（1024） | 未平倉表 | 同上 | 457 = 457 |
| 泡泡圖（375） | 預設 | `#bvSeg .on`、`#blBox` | 「清單」、有清單、沒有 `#bubble` |
| 泡泡圖（375） | 欄位 | `.bl-tbl thead th` | 類股、近5日、日均差、漲跌、成交；切產業鏈、概念股第一欄跟著變 |
| 泡泡圖（375） | 寬度 | `.bl-tbl` 寬 vs 框寬 | 309 = 309（三種分組） |
| 泡泡圖（375） | 展開 | 點「塑膠」 | 下方出現成分股（最高 420、自己捲動），點的列位置不變；再點收合 |
| 泡泡圖（375） | 從今日進來 | 今日「法人資金」點一個族群長條 | 該列展開、頂端 = 頂欄＋44 |
| 泡泡圖（375） | 對比 | 象限字、數字 | 淺 ≥ 4.79、深 ≥ 4.91 |
| 泡泡圖（375） | 切「圖」 | 點「圖」→ 換頁 → 返回 | 泡泡與明細卡；返回後仍是「圖」 |
| 泡泡圖（1024） | 桌面不變 | `#bvSeg` | 不存在；泡泡、明細卡照舊 |
| 泡泡圖（1024） | 提示框 | `Plotly.Fx.hover` 半導體，讀 `.hoverlayer` | 「近5日 -4.3億」「+286.7億/天」「+3.81%」「3,728億」；主控台無 `bad format` |
| 返回位置 | 排行 | `#/rank/n+` 捲到 1,576 → 點一檔 → `history.back()` | 個股頁 0；返回 1,576；前進 0 |
| 返回位置 | 泡泡清單 | 展開一列、捲到 700 → 點成分股 → 返回 | 700，仍展開 |
| 網址 | D28-08 表 | 逐一開啟 | 見 D28-08 表 |
| 主控台 | 錯誤 | `read_console_messages onlyErrors` | 只有測 `#/stock/9999` 時的 404 |

### 7-3 回歸

- 第 27 輪 QA 清單中「表頭跟頂欄」（D27-01）：排行、ETF 長表格照舊；泡泡明細卡的內層表頭不再位移（`panel-list` 已排除）。
- 第 26 輪：每一頁切換深淺色，籌碼圖、泡泡清單的顏色跟著變，捲動位置不變。
- 第 27 輪第九節：泡泡圖 Y 軸放大截圖，底端「偏流出 ↓」、頂端「偏流入 ↑」（本輪未動）。

---

## 附錄 A：完整 diff（`orig` → `proj`；`site/` 與 `tests/`，不含 `site/data`；新測試檔全文見附錄 B）


### A-1 `site/`

```diff
diff -ruN -x data -x __pycache__ orig/site/app.css proj/site/app.css
--- orig/site/app.css	2026-11-15 15:46:48
+++ proj/site/app.css	2026-11-15 20:20:23
@@ -289,7 +289,7 @@
 .scr-panel>summary{position:sticky;top:var(--top-h,56px);z-index:4;background:var(--card);margin:-6px -16px 0;padding:8px 16px;border-radius:var(--radius)}   /* D27-03 */
 .scr-panel[open]>summary{border-bottom:1px solid var(--border)}.scr-go{color:var(--blue);border-color:var(--blue)}
 .scr-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;font-weight:400}.scr-panel[open] .scr-tags{display:none}
-#kC+.kv{margin:8px 0 4px;grid-template-columns:repeat(3,minmax(0,1fr))}                                                                                    /* D27-06 手機關鍵數字列在 K 線下方 */
+#vC+.kv{margin:8px 0 4px;grid-template-columns:repeat(3,minmax(0,1fr))}#vC+.kv .card:last-child:nth-child(3n+1){grid-column:span 3}#vC+.kv .card:last-child:nth-child(3n+2){grid-column:span 2}   /* D27-06；第 28 輪 D28-05 手機關鍵數字列在成交量下方，最後一列不留空格 */
 .qstar{cursor:pointer;padding:0 2px 0 8px;color:var(--text2);font-size:16px;line-height:1}.qstar.on{color:var(--amber)}   /* D27-09 */
 @media (min-width:521px){.oi-tbl th,.oi-tbl td{padding-left:6px;padding-right:6px}}.tbl .nm .pill.muted{border-color:transparent;background:none;padding:0}   /* D27-10 */
 @media (max-width:720px){
@@ -318,3 +318,10 @@
 .tbl td.hl-tags,.tbl th.hl-th{white-space:normal;min-width:12em;text-align:left}.hl-tag{display:inline-block;margin:1px 8px 1px 0;font-size:12px}.hl-tag i{font-style:normal;color:var(--text2)}   /* 第 21 輪 F21-1 */
 .hl-sub{display:none}table.pf-tbl{max-width:560px}.pf-tbl td span{display:block;color:var(--text2);font-size:11px}   /* 第 23 輪 F23-4a、F23-1 */
 @media (max-width:480px){.tbl th.hl-th,.tbl td.hl-tags{display:none}.tbl tr.hl-sub{display:table-row}.tbl tr:has(+.hl-sub) td{border-bottom:0;padding-bottom:2px}.tbl tr.hl-sub td{padding-top:0;white-space:normal;box-shadow:none}.hl-sub .hl-tag{white-space:nowrap}}   /* 第 27 輪 D27-02 */
+/* ─── 第 28 輪（D28-xx）────────────────────────── */
+.chip-rng{display:flex;align-items:center;gap:8px;margin:10px 0 0}.chip-g .kv{grid-template-columns:none;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);margin-bottom:4px}   /* D28-01 籌碼分組：寬螢幕一組一列 */
+@media (max-width:520px){.chip-g .kv{grid-auto-flow:row;grid-template-columns:repeat(2,minmax(0,1fr))}.chip-g .kv .card:only-child{grid-column:1/-1}}
+.ch-label{row-gap:2px}.mg-l{align-items:center}                                                                                         /* D28-06 子圖標題區換行不留 12px 空白 */
+@media (max-width:520px){table.oi-tbl th,table.oi-tbl td{padding:8px 4px}table.bl-tbl>*>tr>*{padding-left:5px;padding-right:5px}}   /* D28-02 375 寬「增減」最後一位數不被切（表 321 → 301，框 309）；原本的 5px 被後面的 .tbl 6px 蓋掉 */
+.bl-tbl tr[data-bl]{cursor:pointer}.bl-tbl tr.on>td{background:var(--card2)}.bl-tbl tr{scroll-margin-top:calc(var(--top-h,56px) + 44px)}.bl-tbl td.nm i{font-style:normal}   /* D28-04 泡泡清單 */
+.bl-x>td{text-align:left;white-space:normal;padding:2px 0 10px}.bl-x .tbl-wrap{width:0;min-width:100%}.panel-list{--th-y:0px}   /* 展開的成分股表不撐寬外層清單，自己橫捲 */
diff -ruN -x data -x __pycache__ orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-15 19:51:05
+++ proj/site/app.js	2026-11-15 20:23:22
@@ -66,8 +66,15 @@
   stock: (code, sub) => window.renderStock(code, sub),   // 第 25 輪 D25-08：#/stock/代號/分頁
 };
 
+// 第 28 輪 D28-03：瀏覽器「返回／前進」回到看過的頁面時還原捲動位置；點連結進新頁才回到頂端。
+// 每一筆瀏覽紀錄在 history.state.k 有自己的鍵（新紀錄的 state 是 null），捲動時記下位置
+const scrollAt = {};
+let scrollKey = null;
 async function route() {
   const [, page = 'today', arg, sub] = location.hash.split('/');
+  const k = history.state?.k;
+  scrollKey = null;                                                     // 換頁中（內容長度改變）的捲動不記
+  if ((page === 'watch' || page === 'bubble') && arg) history.replaceState(history.state, '', '#/' + page);   // D28-08：這兩頁沒有子頁
   if (page !== 'watch') App.watchUndo = App.watchEdit = null;   // 離開自選頁：清掉復原、結束編輯
   // 第 27 輪 D27-10：瀏覽器分頁標題帶頁面名稱（個股頁由 renderStock 換成「名稱 代號」）
   document.title = ({ today: '今日', bubble: '泡泡圖', rank: { hl: '新訊號', screen: '選股' }[String(arg).split('?')[0]] || '排行',
@@ -83,14 +90,16 @@
     console.error(e);
     view.innerHTML = `<div class="empty">載入失敗：${esc(e.message)}</div>`;
   }
-  window.scrollTo(0, 0);
+  window.scrollTo(0, k && scrollAt[k] || 0);
+  scrollKey = k || Date.now() + Math.random();
+  if (history.state?.k !== scrollKey) history.replaceState({ k: scrollKey }, '');   // 不帶網址：保留各頁補正後的網址
 }
 
 // 第 27 輪 D27-01：25 列以上的表格不再關在固定高度的捲動框裡（整頁捲動，不會被畫面底部或底部選單擋住）。
 // .tbl-wrap 要保留橫向捲動，CSS sticky 只能貼在框內，所以捲動時把表頭位移到頂欄下方（--th-y，最多到表格最後兩列）
 function stickHeads() {
   const top = $('.top').getBoundingClientRect().bottom;
-  [...document.querySelectorAll('#view .tbl-wrap')].filter(w => w.querySelector('tbody tr:nth-child(25)'))
+  [...document.querySelectorAll('#view .tbl-wrap:not(.panel-list)')].filter(w => w.querySelector('tbody tr:nth-child(25)'))
     .map(w => [w, w.getBoundingClientRect(), w.querySelector('thead')?.offsetHeight || 0])
     .forEach(([w, r, h]) => w.style.setProperty('--th-y', Math.max(0, Math.min(top - r.top, r.height - 2 * h)) + 'px'));
 }
@@ -666,36 +675,65 @@
   const tr = e.target.closest('tr[data-code]');
   if (tr) { location.hash = '#/stock/' + tr.dataset.code; return; }
   const g = e.target.closest('[data-group]');
-  if (g) { localStore('focus', null, g.dataset.group); location.hash = '#/bubble'; }
+  if (g) { localStore('focus', null, g.dataset.group); App.blOpen = g.dataset.group; App.blJump = 1; location.hash = '#/bubble'; }   // D28-04：手機清單展開這一列
 }
 
 // ─── 泡泡圖 ─────────────────────────────────────────────
 const SYMLOG_C = 1;   // 對稱對數軸的線性區間（億），讓大小差很多的板塊能放在同一張圖
 const symlog = v => Math.sign(v) * Math.log10(1 + Math.abs(v) / SYMLOG_C);
 
+// 第 28 輪 D28-04：手機（≤720）加「圖｜清單」，預設清單（手機泡泡太小、標籤互相遮住，大小也看不出差別）；選擇只在這次瀏覽記住。
+// 清單每列一個族群（最新一天，近 5 日由大到小），點一列在下方展開成分股，不捲走；再點收合
+function bubbleList(groups) {
+  const L = App.latest, k = L.dates.length - 1, open = App.blOpen;
+  const QC = { 漲潮: 'var(--up)', 輪動: 'var(--amber)', 觀望: 'var(--blue)', 退潮: 'var(--dn)' };
+  return `<div class="muted small tbl-cap">資料日 ${md(L.dates[k])}。近5日 = 近 5 日法人累計（億）；日均差 = 近 5 日日均 − 20 日日均（億/天），正 = 偏流入；成交 = 成交額（億）。點一列看成分股</div>
+    <div class="tbl-wrap"><table class="tbl bl-tbl"><thead><tr><th>${{ industry: '類股', chain: '產業鏈', concept: '概念股' }[App.group]}</th><th>近5日</th><th>日均差</th><th>漲跌</th><th>成交</th></tr></thead><tbody>` +
+    groups.filter(g => g.frames[k]).sort((a, b) => b.frames[k][0] - a.frames[k][0]).map(g => { const [n5, dv, ch, tv] = g.frames[k];
+      return `<tr data-bl="${esc(g.name)}"${g.name === open ? ' class="on"' : ''}><td class="nm"><b>${esc(g.name)}</b><span><i style="color:${QC[g.quadrant]}">${g.quadrant}</i></span></td>
+        <td class="num ${cls(n5)}">${yi(n5)}</td><td class="num ${cls(dv)}">${sgn(dv, 1)}</td><td class="num ${cls(ch)}">${sgn(ch)}%</td><td class="num">${fmt(tv)}</td></tr>` +
+        (g.name === open ? `<tr class="bl-x"><td colspan="5"><div class="muted small">${groupMeta(g)}</div><div class="tbl-wrap panel-list"><table class="tbl">${groupRows(g)}</table></div></td></tr>` : ''); }).join('') +
+    '</tbody></table></div>';
+}
+
 function renderBubble() {
   const L = App.latest, groups = L.groups[App.group];
   const focus = localStore('focus', '');
+  const mob = matchMedia('(max-width:720px)').matches, list = mob && App.bubbleView !== 'chart';
   $('#view').innerHTML = `
     <section class="sec">
-      <div class="sec-h"><h2>板塊資金泡泡圖</h2><span class="muted small">X：近 5 日法人淨流入　Y：近 5 日日均比 20 日日均偏流入或偏流出　大小：成交額　顏色：漲跌幅</span>
-        <span class="sp"></span>${groupSeg()}</div>
-      <div class="card" style="padding:6px"><div id="bubble"></div></div>
+      <div class="sec-h"><h2>板塊資金${list ? '' : '泡泡圖'}</h2><span class="muted small">${list ? '近 5 日法人淨流入由大到小' : 'X：近 5 日法人淨流入　Y：近 5 日日均比 20 日日均偏流入或偏流出　大小：成交額　顏色：漲跌幅'}</span>
+        <span class="sp"></span>${mob ? segHTML('bvSeg', [['chart', '圖'], ['list', '清單']], list ? 'list' : 'chart') : ''}${groupSeg()}</div>
+      ${list ? `<div class="card" id="blBox">${bubbleList(groups)}</div>` : '<div class="card" style="padding:6px"><div id="bubble"></div></div>'}
     </section>
     <section class="sec grid g2">
-      <div class="card"><div class="sec-h"><h2 id="gTitle">點泡泡看成分股</h2><span class="sp"></span><span id="gMeta" class="muted small"></span></div>
-        <div class="tbl-wrap panel-list"><table class="tbl" id="gTable"></table></div></div>
+      ${list ? '' : `<div class="card"><div class="sec-h"><h2 id="gTitle">點泡泡看成分股</h2><span class="sp"></span><span id="gMeta" class="muted small"></span></div>
+        <div class="tbl-wrap panel-list"><table class="tbl" id="gTable"></table></div></div>`}
       <div class="card"><div class="sec-h"><h2>象限說明</h2></div>
         <div class="small" style="line-height:1.9">
           <div><b class="up">漲潮</b>：近 5 日淨流入，而且比 20 日平均更積極 → 資金正在加速進場</div>
           <div><b style="color:var(--amber)">輪動</b>：仍是淨流入，但力道比過去弱 → 可能接近尾聲、資金轉往他處</div>
           <div><b style="color:var(--blue)">觀望</b>：仍是淨流出，但賣壓比過去小 → 可能止跌、留意回流</div>
           <div><b class="dn">退潮</b>：淨流出且賣壓加大 → 資金正在撤出</div>
-          <div class="muted" style="margin-top:6px">按圖下方 ▶ 可回放近 ${L.dates.length} 個交易日的變化；軸為對稱對數刻度。</div>
+          ${list ? '' : `<div class="muted" style="margin-top:6px">按圖下方 ▶ 可回放近 ${L.dates.length} 個交易日的變化；軸為對稱對數刻度。</div>`}
         </div></div>
     </section>`;
   onSeg('grpSeg', v => { setGroup(v); renderBubble(); });
   $('#view').addEventListener('click', onRowClick);
+  if (mob) onSeg('bvSeg', v => { App.bubbleView = v; if (window.Plotly && $('#bubble')) Plotly.purge('bubble'); renderBubble(); });
+  if (list) {
+    $('#blBox').addEventListener('click', e => {
+      const tr = e.target.closest('tr[data-bl]');
+      if (!tr) return;
+      const name = tr.dataset.bl, y0 = tr.getBoundingClientRect().top;
+      App.blOpen = App.blOpen === name ? null : name;
+      if (App.blOpen) localStore('focus', null, name);
+      $('#blBox').innerHTML = bubbleList(groups);
+      window.scrollBy(0, $(`#blBox tr[data-bl="${CSS.escape(name)}"]`).getBoundingClientRect().top - y0);   // 點的那一列留在原位（上方收合時不跳走）
+    });
+    if (App.blJump) { App.blJump = 0; requestAnimationFrame(() => $('#blBox tr.on')?.scrollIntoView()); }   // 從今日頁點族群進來：捲到展開的那一列（route() 捲到頂端之後）
+    return;
+  }
   drawBubble(groups, L.dates);
   showGroup(groups.find(g => g.name === focus) || groups[0]);
 }
@@ -758,9 +796,10 @@
       ids: gs.map(g => g.name),
       x: xs, y: ys,
       text: lab.text, textposition: 'middle center',
-      customdata: gs.map(g => [g.name, ...g.frames[k]]),
+      // 第 28 輪 D28-07：Plotly basic 的 d3-format 不認得 +.1f（會顯示原始數字、正值沒有 +），先格式化成字串；近 5 日和泡泡上的字同一種小數位
+      customdata: gs.map(g => { const f = g.frames[k]; return [g.name, amount(f[0]), sgn(f[1], 1) + '億/天', sgn(f[2]) + '%', fmt(f[3]) + '億']; }),
       textfont: { size: lab.font, color: '#fff' },
-      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]:+.1f}億<br>5日日均−20日日均 %{customdata[2]:+.1f}億/天<br>漲跌 %{customdata[3]:+.2f}%<br>成交 %{customdata[4]:,.0f}億<extra></extra>',
+      hovertemplate: '<b>%{customdata[0]}</b><br>近5日 %{customdata[1]}<br>5日日均−20日日均 %{customdata[2]}<br>漲跌 %{customdata[3]}<br>成交 %{customdata[4]}<extra></extra>',
       marker: {
         size: d, sizemode: 'diameter',
         color: gs.map(g => g.frames[k][2]), cmin: -4, cmax: 4,
@@ -816,17 +855,21 @@
   });
 }
 
-function showGroup(g) {
-  if (!g) return;
+const groupMeta = g => `<span class="pill">${g.quadrant}</span>　5日 <span class="${cls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
+function groupRows(g) {   // D28-04：泡泡明細卡與手機清單展開共用
   const S = App.latest.stocks;
-  $('#gTitle').textContent = g.name;
-  $('#gMeta').innerHTML = `<span class="pill">${g.quadrant}</span>　5日 <span class="${cls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
   const rows = g.codes.filter(c => S[c]).sort((a, b) => (S[b].n5 ?? 0) - (S[a].n5 ?? 0));
-  $('#gTable').innerHTML = `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
+  return `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
     rows.map(c => { const s = S[c]; return `<tr data-code="${c}"><td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
       <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
       <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
 }
+function showGroup(g) {
+  if (!g) return;
+  $('#gTitle').textContent = g.name;
+  $('#gMeta').innerHTML = groupMeta(g);
+  $('#gTable').innerHTML = groupRows(g);
+}
 
 // ─── 排行 / 自選 ────────────────────────────────────────
 // [代號, 名稱, 欄位, 排序方向, 來源]；欄位 '*' 會換成 1 或 5（依「1日 / 5日」切換）
@@ -1421,7 +1464,7 @@
   // 不在支援清單就不請求（避免 404）
   const H = App.latest.holdings?.[code] && await getJSON(`data/etfs/${code}.json`);
   if (!H && App.latest.etfs?.rows?.[code]) { location.replace('#/stock/' + code); return; }     // 第 15 輪 F15-2：沒有持股資料的 ETF 改看 ETF 個股頁
-  if (!H) { $('#view').innerHTML = `<div class="empty">${esc(code)} 的持股資料尚未支援（目前支援統一、群益投信 8 檔主動 ETF）</div>`; return; }
+  if (!H) { document.title = 'ETF｜台股資金流'; $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href="#/etf" style="color:var(--blue)">回 ETF 列表</a></div>`; return; }   // 第 28 輪 D28-08：不是 ETF 代號
   const S = H.sum, by = localStore('holdSort', 'pw'), unit = r => r.tw ? '張' : '股';
   const rows = [...H.rows].sort((a, b) => (b[by] ?? -Infinity) - (a[by] ?? -Infinity));
   const prev = H.dates.at(-2), d5 = H.dates.length > 5 ? H.dates.at(-6) : null;
@@ -1649,6 +1692,8 @@
   // 第 27 輪：頂欄高度給固定表頭、選股條件列（--top-h）；畫面重畫、捲動、改變大小時重算表頭位置（D27-01）
   const topH = () => { document.documentElement.style.setProperty('--top-h', $('.top').offsetHeight + 'px'); stickHeads(); };
   topH(); addEventListener('resize', topH); addEventListener('scroll', stickHeads, { passive: true });
+  history.scrollRestoration = 'manual';                                 // D28-03：捲動位置由 route() 還原（內容是重畫的，瀏覽器自己還原會被蓋掉）
+  addEventListener('scroll', () => { if (scrollKey) scrollAt[scrollKey] = window.scrollY; }, { passive: true });
   new MutationObserver(stickHeads).observe($('#view'), { childList: true });
   document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') recheckLatest(); });
   window.addEventListener('hashchange', route);
diff -ruN -x data -x __pycache__ orig/site/index.html proj/site/index.html
--- orig/site/index.html	2026-11-15 19:51:05
+++ proj/site/index.html	2026-11-15 20:26:29
@@ -7,11 +7,11 @@
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
 <script>try{var t=localStorage.getItem('tw.theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>
-<link rel="stylesheet" href="app.css?v=39f292f5">
+<link rel="stylesheet" href="app.css?v=7b2bc0df">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js?v=3a2f69e2" defer></script>
-<script src="stock.js?v=51cc333a" defer></script>
+<script src="app.js?v=528d35a6" defer></script>
+<script src="stock.js?v=2d561731" defer></script>
 </head>
 <body>
 <header class="top">
diff -ruN -x data -x __pycache__ orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-15 15:46:48
+++ proj/site/stock.js	2026-11-15 20:26:28
@@ -57,6 +57,11 @@
 const mgView = G => { const v = localStore('mgv', 'mb'); return v === 'sb' || (v === 'lb' && G?.lb) ? v : 'mb'; };
 const tagFold = t => t.slice(0, 2).join('') + (t.length > 2 ? `<span class="tag-rest" hidden>${t.slice(2).join('')}</span><button class="pill more" id="tagMore" data-n="+${t.length - 2}">+${t.length - 2}</button>` : '');
 
+const cardsHTML = a => a.map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('');
+// 第 28 輪 D28-01：籌碼分頁的圖表區間（預設 60 個交易日；只在這次瀏覽記住，不存 localStorage）
+const CHIP_N = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['all', '全部']];
+let chipN = '60';
+
 window.renderStock = async function (code, sub) {
   const E = !App.latest.stocks[code] && App.latest.etfs?.rows?.[code];   // 第 15 輪 F15-2：ETF 個股頁（頁首用 etfs.rows，資料 data/etfp/）
   const s = App.latest.stocks[code] || E || undefined;
@@ -99,6 +104,7 @@
   if (STOCK_TABS.some(t => t[0] === sub)) localStore('stockTab', null, sub); else if (App.stockCode !== code) localStore('stockTab', null, 'k');
   App.stockCode = code;
   const tab0 = pageTab('stockTab', STOCK_TABS), tab = E && tab0 === 'fund' ? 'k' : tab0;   // 分頁：走勢／籌碼／基本面（頁首永遠顯示）；第 15 輪：ETF 沒有基本面
+  if (sub && sub !== tab) history.replaceState(history.state, '', `#/stock/${code}/${tab}`);   // 第 28 輪 D28-08：不認得的分頁（ETF 的 fund）補成實際顯示的分頁
   const fd = md(App.latest.flow_date);
   // 第 15 輪：ETF 的 52 週高低由原始價計算（和匯出端 h52 同樣取資料日往前 365 天）
   const w0 = new Date(Date.parse(P.d[last]) - 365 * 864e5).toISOString().slice(0, 10), inW = (x, i) => x != null && P.d[i] >= w0;
@@ -111,16 +117,23 @@
   const mgCards = MG === undefined ? [] : MG === null ? [['信用交易', '無信用交易', 'flat', '不在融資融券清單']]
     : [['融資餘額', fmt(MG.mb) + ' 張', '', subs(`1日 ${sgn(MG.m1, 0)}　5日 ${MG.m5 == null ? '--' : sgn(MG.m5, 0)}`, !E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減'))],
        ['融券餘額', fmt(MG.sb) + ' 張', '', `1日 ${sgn(MG.s1, 0)}`],
-       ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
-       ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
+       ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', ''],
+       ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '']];   // 第 28 輪 D28-01：資料日寫在組標題
   // 第 11 輪 B14：借券賣出（張；占股本用目前股數）。sbl 不存在 = 該市場最新借券日沒有這檔
   const SL = data.sbl;
   // 第 12 輪 B11：市值、週轉率（目前股數）
   const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
   const mtCards = E ? [] : [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
     ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${MT.d !== P.d[last] ? md(MT.d) + '，' : ''}成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
-  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', subs(`1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}${E ? '　資料 ' + md(SL.d) : ''}`, !E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減'))],
-    ...E ? [] : [['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]]];
+  const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', subs(`1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`, !E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減'))],
+    ...E ? [] : [['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍`]]];
+  // 第 28 輪 D28-01：籌碼分頁分三組，日期寫在組標題一次；每組下方是同主題的時間序列圖（張），區間共用
+  const inCards = E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), runTxt(s?.s, '買', '賣')], ['法人5日', yi(s?.n5), cls(s?.n5), ''],
+    ['外資5日', yi(s?.f5), cls(s?.f5), runTxt(s?.fs, '買', '賣')], ['投信5日', yi(s?.t5), cls(s?.t5), runTxt(s?.ts, '買', '賣')]];
+  const chipSec = (h, note, cards, chart, foot = '') => !cards.length ? '' : `<section class="sec card chip-g"><div class="sec-h"><h2>${h}</h2><span class="muted small">${note}</span></div>
+      <div class="metrics kv">${cardsHTML(cards)}</div>${chart}${foot}</section>`;
+  const chLeg = (t, id, h) => `<div class="ch-label">${t}<span id="${id}L" style="display:contents"></span></div><div id="${id}" class="chart-box" style="height:${h}px"></div>`;
+  const GK = data.mg?.k ? '，面額變更、減資前依官方換算' : '';
 
   // E2-4：主動 ETF 持有（統一、群益投信 8 檔；沒有任何一檔持有、也沒有 act 時不顯示）
   const AC = data.active, A = data.act;
@@ -166,18 +179,19 @@
     </section>
 
     ${pageTabsHTML('stockTabSeg', E ? ETF_TABS : STOCK_TABS, tab)}
-    <section class="sec metrics${tab === 'k' ? ' kv' : ''}">
-      ${(tab === 'k' ? [
+    ${tab === 'chip' ? '' : `<section class="sec metrics${tab === 'k' ? ' kv' : ''}">
+      ${cardsHTML(tab === 'k' ? [
          [hlFrom ? '區間高' : '52週高', pfmt(E ? eHL[0] : s?.h52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
          ...E ? [] : [['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)], ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', fundSub(fund.dy)], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd]], ...mtCards]
-        : tab === 'chip' ? [...E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), subs(fd, runTxt(s?.s, '買', '賣'))], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
-         ['外資5日', yi(s?.f5), cls(s?.f5), subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))], ['投信5日', yi(s?.t5), cls(s?.t5), subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))]], ...mgCards, ...slCards]
         : [['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
-         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))]])
-        .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
-    </section>
-    ${tab === 'chip' ? `${SL ? `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。${E ? '' : '占股本以目前發行股數計算。'}借券資料晚上 8 點半以後才更新。</div>` : ''}
+         ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', subs(fundSub(fund.dy), valSub('dy', fund.dy))]])}
+    </section>`}
+    ${tab === 'chip' ? `<div class="sec chip-rng"><span class="muted small">圖表區間</span>${segHTML('chipSeg', CHIP_N, chipN)}</div>
+    ${chipSec('法人買賣超', `${fd}，億，估算（張數 × 收盤）`, inCards, chLeg(E ? '收盤（原始價）' : '收盤（還原）', 'cpC', 64) + chLeg('區間累計買賣超（張，未還原；從區間第一天起加總）', 'ciC', 150))}
+    ${chipSec('信用交易', MG ? md(MG.d) : '', mgCards, data.mg ? chLeg(`融資餘額（張${GK}）`, 'cmC', 110) : '')}
+    ${chipSec('借券賣出', SL ? `${md(SL.d)}，晚上 8 點半以後更新` : '', slCards, data.mg?.lb ? chLeg(`借券賣出餘額（張${GK}）`, 'clC', 110) : '',
+      `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。${E ? '' : '占股本以目前發行股數計算。'}</div>`)}
     ${acHTML}` : tab === 'fund' ? `${VAL ? `<div class="muted small val-note">${noteHTML('獲利大增時本益比會落到一年低點，位置低不代表股價便宜', `一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}`)}</div>` : ''}
     ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
     <section class="sec grid ${F ? 'g2' : 'g-one'}">
@@ -199,7 +213,7 @@
       <div id="vC" class="chart-box" style="height:80px"></div>
       ${E ? '' : `<div class="ch-label">三大法人買賣超（張，未還原）<span id="iLegend" style="display:contents"></span></div>
       <div id="iC" class="chart-box" style="height:90px"></div>`}
-      ${data.mg ? `<div class="ch-label">${segHTML('mgSeg', [['mb', '融資'], ['sb', '融券'], ...data.mg.lb ? [['lb', '借券賣出']] : []], mgView(data.mg))}餘額<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
+      ${data.mg ? `<div class="ch-label mg-l">${segHTML('mgSeg', [['mb', '融資'], ['sb', '融券'], ...data.mg.lb ? [['lb', '借券賣出']] : []], mgView(data.mg))}<span id="gUnit"></span><span id="gLegend" style="display:contents"></span></div>
       <div id="gC" class="chart-box" style="height:90px"></div>` : ''}
       <div class="ch-label">${E ? '' : segHTML('oscSeg', OSC_OPTS, localStore('osc', 'MACD'))}<span id="oscLeg" style="display:contents"></span></div>
       <div id="mC" class="chart-box" style="height:120px"></div>
@@ -218,9 +232,11 @@
     $('#starBtn').textContent = on ? '★ 已加入自選' : '☆ 加入自選';
   });
   if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
+  if (tab === 'chip') onSeg('chipSeg', v => { chipN = v; document.querySelectorAll('#chipSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === v)); buildChip(data, E); });
+  if (tab === 'chip') buildChip(data, E);
   if (tab !== 'k') return;
   // 第 25 輪 D25-05：關鍵數字列在寬螢幕併進頁首卡、手機放到 K 線卡下方，主圖進第一屏
-  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#kC').after($('#view .metrics.kv'));   // 第 27 輪 D27-06：手機放在 K 線正下方（原本在 4 張子圖之後）
+  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#vC').after($('#view .metrics.kv'));   // 第 27 輪 D27-06：手機放在主圖下方；第 28 輪 D28-05：改到成交量之後，K 線和成交量相鄰、十字線不斷開
   if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格（現金增資除權也依官方參考價調整），最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
   // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
   const draw = () => {
@@ -378,7 +394,7 @@
     layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 11, attributionLogo: logo },
     grid: { vertLines: { color: grid }, horzLines: { color: grid } },
     crosshair: { mode: LC.CrosshairMode.Normal },
-    rightPriceScale: { borderVisible: false, minimumWidth: 76 },   // 各圖刻度同寬，K 棒才會上下對齊
+    rightPriceScale: { borderVisible: false, minimumWidth: 76, entireTextOnly: true },   // 各圖刻度同寬，K 棒才會上下對齊；第 28 輪 D28-06：刻度文字放不下就不畫（不會只露半截）
     timeScale: { borderVisible: false, visible: timeVisible, fixLeftEdge: true, rightOffset: 3, tickMarkFormatter: tickFmt },
     localization: { locale: 'zh-TW', timeFormatter: t => ymd(t).map(pad).join('/') },
   });
@@ -412,10 +428,13 @@
 
   // 堆疊：買超與賣超各自累加，先畫最外層（合計），再畫內層蓋上去
   const ic = $('#iC') ? mk('iC', false) : null;      // 第 15 輪：ETF 頁沒有法人圖
+  // 第 28 輪 D28-06：法人子圖刻度上下對稱（0 在中間），正負兩側都有刻度；上下留邊，最上面的刻度不被切
+  const symScale = f => { const r = f(), m = r && Math.max(Math.abs(r.priceRange.minValue), Math.abs(r.priceRange.maxValue)); return m ? { ...r, priceRange: { minValue: -m, maxValue: m } } : r; };
+  ic?.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
   let iSer = null;
   for (const sign of ic ? [1, -1] : []) {
     for (let k = INVESTORS.length; k >= 1; k--) {
-      const ser = ic.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false });
+      const ser = ic.addHistogramSeries({ priceFormat: { type: 'volume' }, priceLineVisible: false, lastValueVisible: false, autoscaleInfoProvider: symScale });
       ser.setData(raw.map((r, i) => {
         if (r.net == null) return { time: T[i] };
         const v = INVESTORS.slice(0, k).reduce((a, [key]) => a + (sign * r[key] > 0 ? r[key] : 0), 0);
@@ -436,7 +455,8 @@
     // 換算事件標在包含該日期的那一根（T 中 ≤ 事件日的最後一根）
     mbSer.setMarkers((G.k || []).map(x => { let j = -1; T.forEach((t, i) => { if (t <= x.d) j = i; }); return [j, x]; }).filter(([j]) => j >= 0)
       .sort((a, b) => a[0] - b[0]).map(([j, x]) => ({ time: T[j], position: 'aboveBar', shape: 'circle', color: css('--blue'), text: EV_LABEL[x.t] + (adj ? ' 已換算' : '') })));
-    $('#gUnit').textContent = adj ? '（張；面額變更、減資前的餘額依官方換算）' : '（張，官方原始）';     // 第 12 輪 P26；D27-07 刻度即所選的線
+    $('#gUnit').textContent = adj ? '餘額（張）' : '餘額（張，官方原始）';     // 第 12 輪 P26；D27-07 刻度即所選的線；第 28 輪 D28-06：換算說明移到 title
+    $('#gUnit').title = adj ? '面額變更、減資前的餘額依官方換算' : '';
   }
 
   const mc = mk('mC', true);
@@ -503,11 +523,10 @@
     if (gc) {   // 融資融券比行情晚公布：最新一根還沒有時，改顯示最近有資料的那天
       let g = i;
       if (MB[g] == null && i === raw.length - 1) while (g > 0 && MB[g] == null) g--;
+      const gv = mgView(G);   // 第 28 輪 D28-06：只列目前那條線（＋券資比），標題區手機 ≤ 60px
       $('#gLegend').innerHTML = (g !== i && MB[g] != null ? `<span class="muted">${T[g]}</span>` : '') +
-        `<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">${fmt(MB[g])}</b></span>` +
-        `<span class="lg"><i style="background:#AE3EC9"></i>融券 <b class="num">${fmt(SB[g])}</b></span>` +
-        `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>` +
-        (G.lb ? `<span class="lg"><i style="background:#E8590C"></i>借券 <b class="num">${fmt(LB[g])}</b></span>` : '');
+        `<span class="lg"><i style="background:${GV[1]}"></i>${{ mb: '融資', sb: '融券', lb: '借券' }[gv]} <b class="num">${fmt(GV[0][g])}</b></span>` +
+        (gv === 'lb' ? '' : `<span class="lg">券資比 <b class="num">${MB[g] ? fmt(SB[g] / MB[g] * 100, 2) + '%' : '--'}</b></span>`);
     }
   };
   let crossSyncing = false;
@@ -529,6 +548,68 @@
   // 初始畫面：最近 N 根，往左拖曳可看更早的資料
   const VIEW = mode === '日' ? 90 : 60;
   kc.timeScale().setVisibleLogicalRange({ from: Math.max(0, raw.length - VIEW), to: raw.length - 1 + 3 });
+}
+
+// 第 28 輪 D28-01：籌碼分頁時間序列（張）。法人：收盤小面板＋外資／投信／自營區間累計（不用雙 Y 軸）；信用：融資餘額；借券：借券賣出餘額。
+// 區間由 #chipSeg 決定，不能拖曳縮放（避免手機捲頁時誤拖）；十字線四張圖同步，圖例顯示該日數字
+function buildChip(data, E) {
+  disposeKCharts();
+  const LC = window.LightweightCharts, all = aggregate(data, '日', !E), raw = chipN === 'all' ? all : all.slice(-chipN);
+  if (!LC || !raw.length) return;
+  const T = raw.map(r => r.d), text2 = css('--text2'), grid = css('--border'), last = raw.length - 1;
+  const dt = t => typeof t === 'string' ? t : [t.year, t.month, t.day].map(x => String(x).padStart(2, '0')).join('-');
+  const lots = { type: 'custom', minMove: 1, formatter: v => fmt(v) }, px = { type: 'custom', minMove: 0.01, formatter: pfmt };
+  const mk = (id, tv) => LC.createChart($('#' + id), {
+    autoSize: true, handleScroll: false, handleScale: false,
+    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 11, attributionLogo: false },
+    grid: { vertLines: { visible: false }, horzLines: { color: grid } },
+    rightPriceScale: { borderVisible: false, minimumWidth: 76, scaleMargins: { top: 0.12, bottom: 0.08 }, entireTextOnly: true },   // 上下留邊；刻度文字放不下就不畫（不會只露半截）
+    timeScale: { borderVisible: false, visible: tv, fixLeftEdge: true, fixRightEdge: true,
+      tickMarkFormatter: (t, type) => { const [y, m, d] = dt(t).split('-').map(Number); return type === 0 ? String(y) : type === 1 ? `${m}月` : `${m}/${d}`; } },
+    localization: { locale: 'zh-TW', timeFormatter: t => dt(t).split('-').join('/') },
+  });
+  const line = (c, vals, color, w = 2, f = lots) => { const s = c.addLineSeries({ color, lineWidth: w, priceFormat: f, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
+    s.setData(vals.map((v, i) => v == null ? { time: T[i] } : { time: T[i], value: v })); return s; };
+  const at = (a, i) => { let j = i; if (i === last) while (j > 0 && a[j] == null) j--; return j; };    // 最新一天還沒有資料時，圖例改顯示最近有資料的那天
+  const day = (i, j) => `<span><b>${T[j].slice(5).replace('-', '/')}</b></span>`;
+  const anchors = [], legs = [];
+  if ($('#cpC')) {
+    const C = raw.map(r => r.c), cp = mk('cpC', false), ci = mk('ciC', true);
+    anchors.push([cp, line(cp, C, text2, 1, px), C]);
+    const cum = INVESTORS.map(([k]) => { let a = 0; return raw.map(r => r[k] == null ? null : (a += r[k])); });
+    const ser = INVESTORS.map(([, , color], n) => line(ci, cum[n], color));
+    ser[0].createPriceLine({ price: 0, color: text2, lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
+    anchors.push([ci, ser[0], cum[0]]);
+    legs.push(i => { $('#cpCL').innerHTML = `${day(i, i)}<span>收 <b>${pfmt(C[i])}</b></span>`; },
+      i => { const j = at(cum[0], i);
+        $('#ciCL').innerHTML = (j !== i ? `<span class="muted">${T[j].slice(5).replace('-', '/')}</span>` : '') + INVESTORS.map(([k, n, color], m) =>
+          `<span class="lg"><i style="background:${color}"></i>${n} <b class="num ${cls(cum[m][j])}">${cum[m][j] == null ? '--' : sgn(cum[m][j], 0)}</b><span class="muted">（當日 ${raw[j][k] == null ? '--' : sgn(raw[j][k], 0)}）</span></span>`).join(''); });
+  }
+  if ($('#cmC')) {
+    const MB = raw.map(r => r.mb), SB = raw.map(r => r.sb), cm = mk('cmC', true);
+    anchors.push([cm, line(cm, MB, '#1C7ED6'), MB]);
+    legs.push(i => { const j = at(MB, i);
+      $('#cmCL').innerHTML = `${day(i, j)}<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">${fmt(MB[j])}</b></span><span>融券 <b class="num">${fmt(SB[j])}</b></span>` +
+        `<span>券資比 <b class="num">${MB[j] ? fmt(SB[j] / MB[j] * 100, 2) + '%' : '--'}</b></span>`; });
+  }
+  if ($('#clC')) {
+    const LB = raw.map(r => r.lb), cl = mk('clC', true);
+    anchors.push([cl, line(cl, LB, '#E8590C'), LB]);
+    legs.push(i => { const j = at(LB, i); $('#clCL').innerHTML = `${day(i, j)}<span class="lg"><i style="background:#E8590C"></i>借券賣出 <b class="num">${fmt(LB[j])}</b></span>`; });
+  }
+  charts = anchors.map(a => a[0]);            // disposeStockCharts 一併釋放
+  charts.forEach(c => c.timeScale().fitContent());
+  const show = i => legs.forEach(f => f(i));
+  let busy = false;
+  anchors.forEach(([src]) => src.subscribeCrosshairMove(p => {
+    if (busy) return;
+    busy = true;
+    const i = p.logical == null ? -1 : Math.round(p.logical), ok = p.time !== undefined && i >= 0 && i <= last;
+    anchors.forEach(([dst, ser, v]) => { if (dst === src) return; if (ok && v[i] != null) dst.setCrosshairPosition(v[i], T[i], ser); else dst.clearCrosshairPosition(); });
+    show(ok ? i : last);
+    busy = false;
+  }));
+  show(last);
 }
 
 const SIG_MIN = 3, MACD_MIN = 35;   // 有效訊號至少 3 項才下結論；MACD 需 26 + 9 根
```

### A-2 舊測試（4 個檔、6 行）

```diff
diff -ruN -x __pycache__ -x test_iter28.py orig/tests/test_iter12.py proj/tests/test_iter12.py
--- orig/tests/test_iter12.py	2026-11-15 15:46:48
+++ proj/tests/test_iter12.py	2026-11-15 20:22:25
@@ -80,7 +80,7 @@
 def test_f12_site():
     js = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
     assert "segHTML('mgSeg'" in js and "右側刻度只適用融資" not in js                                       # F12-1 P26；第 27 輪 D27-07 改成一次一條線
-    assert "...mtCards]" in js and "...mgCards, ...slCards]" in js and "MT?.mc == null ? '--'" in js        # F12-4（分頁後：市值在走勢、信用在籌碼）
+    assert "...mtCards]" in js and "cardsHTML(cards)" in js and "mgCards, data.mg ?" in js and "slCards, data.mg?.lb ?" in js and "MT?.mc == null ? '--'" in js        # F12-4（分頁後：市值在走勢、信用在籌碼）
     app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
     assert "function wpeLine(V)" in app and "${wpeLine(V)}" in app and "不是證交所公布的數字" in app            # F12-2
     assert "function etfSblLine(B)" in app and "${etfSblLine(L.sbl_etf)}" in app and "不等於看空" in app      # F12-3
diff -ruN -x __pycache__ -x test_iter28.py orig/tests/test_iter13.py proj/tests/test_iter13.py
--- orig/tests/test_iter13.py	2026-11-08 00:31:54
+++ proj/tests/test_iter13.py	2026-11-15 20:22:25
@@ -45,7 +45,7 @@
 
 
 def test_f13_2_stock_k_cards():
-    k = STK[STK.index("${(tab === 'k' ? ["):STK.index(": tab === 'chip' ?")]
+    k = STK[STK.index("${cardsHTML(tab === 'k' ? ["):STK.index("\n        : [['本益比'")]
     assert "開盤" not in k and "成交量" not in k and "昨收" not in k and "...mtCards]" in k
     assert "hlFrom ? '區間高' : '52週高'" in k and "hlFrom ? '區間低' : '52週低'" in k
     assert '<div class="s-ohlc small num muted">' in STK and "昨收 <b>${pfmt(prev)}</b>" in STK and "量 <b>${fmt(P.v[last])}</b> 張" in STK
diff -ruN -x __pycache__ -x test_iter28.py orig/tests/test_iter22.py proj/tests/test_iter22.py
--- orig/tests/test_iter22.py	2026-11-14 11:08:24
+++ proj/tests/test_iter22.py	2026-11-15 20:22:25
@@ -175,8 +175,8 @@
 
 
 def test_stock_source():
-    assert "subs(fd, runTxt(s?.s, '買', '賣'))" in STK
-    assert "subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))" in STK and "subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))" in STK
+    assert "['法人1日', yi(s?.n1), cls(s?.n1), runTxt(s?.s, '買', '賣')]" in STK                # 第 28 輪 D28-01：日期移到組標題
+    assert "['外資5日', yi(s?.f5), cls(s?.f5), runTxt(s?.fs, '買', '賣')]" in STK and "['投信5日', yi(s?.t5), cls(s?.t5), runTxt(s?.ts, '買', '賣')]" in STK
     assert "!E && runTxt(balStreak(data.mg, P.d, 'mb', MG.d), '增', '減')" in STK              # ETF 頁不加
     assert "!E && runTxt(balStreak(data.mg, P.d, 'lb', SL.d), '增', '減')" in STK
     # F22-12：頁首、共用 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列
diff -ruN -x __pycache__ -x test_iter28.py orig/tests/test_iter27.py proj/tests/test_iter27.py
--- orig/tests/test_iter27.py	2026-11-15 19:51:05
+++ proj/tests/test_iter27.py	2026-11-15 20:22:25
@@ -95,7 +95,7 @@
     # Y 軸標題由 Plotly 轉 -90° 直書，字元跟著轉：寫 ← → 畫面上才是 ↓ ↑（寫 ↓ ↑ 會變成 → ←）
     assert "'← 偏流出　近 5 日日均 − 20 日日均（億/天）　偏流入 →'" in APP and "'↓ 放緩　　加速 ↑'" not in APP and "偏流入 ↑'" not in APP
     assert "Y：近 5 日日均比 20 日日均偏流入或偏流出" in APP and "比 20 日平均加速或放緩" not in APP
-    assert "加速度 %{customdata[2]" not in APP and "5日日均−20日日均 %{customdata[2]:+.1f}億/天" in APP
+    assert "加速度 %{customdata[2]" not in APP and "5日日均−20日日均 %{customdata[2]}<br>" in APP   # 第 28 輪 D28-07：customdata 先格式化
     assert "Math.max(10, Math.min(14, v * 0.2))" in APP
     assert "opacity: isDark() ? .82 : 1" in APP
     # 淺色底不透明時，最淡的綠色泡泡上白字 ≥ 4.5
@@ -122,7 +122,7 @@
             assert _cr(on, re.search(rf"--{k}:(#[0-9a-f]{{6}})", blk).group(1)) >= 4.5, k
     assert '<span class="lg"><i style="background:${color}"></i>${label} <b>${fmt(v)}</b></span>' in APP
     assert "<b style=\"color:${color}\">" not in APP
-    assert "$('#kC').after(" in STK and "#kC+.kv{" in CSS
+    assert "$('#vC').after(" in STK and "#vC+.kv{" in CSS                  # 第 28 輪 D28-05：改到成交量之後
 
 
 def test_margin_single_series():
```

---

## 附錄 B：`tests/test_iter28.py` 全文

```python
"""第 28 輪：UI/UX 優化（不連網、不連資料庫）。
籌碼分頁分組小卡＋時間序列圖（張）、期貨未平倉表手機欄距、返回時還原捲動位置、泡泡圖手機清單、
手機關鍵數字列移到成交量之後、融資融券子圖標題區、法人子圖對稱刻度、泡泡提示框格式、未知分頁網址補正。
有 node 時逐字取出 app.js／stock.js 的函式執行（node 14 可跑：不用 .at()、replaceAll）。"""
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")


def _grab(src, name):
    m = re.search(rf"^(?:async )?function {name}\(", src, re.M)
    if m:
        i, n = src.index("{", src.index(")", m.start())), 0
        for j in range(i, len(src)):
            n += {"{": 1, "}": -1}.get(src[j], 0)
            if n == 0:
                return src[m.start():j + 1]
    m = re.search(rf"^(?:const|let) {name}\b", src, re.M)      # const／let 取到去掉行尾註解後結尾為「;」的那一行
    assert m, name
    lines = src[m.start():].splitlines()
    k = next(i for i, l in enumerate(lines) if re.sub(r"\s+//[^'`]*$", "", l).rstrip().endswith(";"))
    return "\n".join(lines[:k + 1])


def _node(js):
    node = shutil.which("node")
    if not node:
        print("  （沒有 node，略過執行）")
        return None
    return json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout)


HELPERS = "\n".join(_grab(APP, n) for n in ("esc", "fmt", "pfmt", "sgn", "cls", "yi", "md"))


# ─── D28-01：籌碼分頁分組小卡＋時間序列 ─────────────────────
def test_chip_groups_source():
    assert "const CHIP_N = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['all', '全部']];" in STK
    assert "let chipN = '60';" in STK and "localStore('chipN'" not in STK                     # 預設 60 日，不新增 localStorage 鍵
    assert "${chipSec('法人買賣超', `${fd}，億，估算（張數 × 收盤）`, inCards," in STK          # 卡片：億（估算）
    assert "chLeg('區間累計買賣超（張，未還原；從區間第一天起加總）', 'ciC', 150)" in STK        # 圖：張
    assert "${chipSec('信用交易', MG ? md(MG.d) : '', mgCards," in STK
    assert "${chipSec('借券賣出', SL ? `${md(SL.d)}，晚上 8 點半以後更新` : '', slCards," in STK
    assert "'資料 ' + md(MG.d)" not in STK and "'資料 ' + md(SL.d)" not in STK                # 日期只寫在組標題
    assert "if (tab === 'chip') buildChip(data, E);" in STK and "charts = anchors.map(a => a[0]);" in STK   # disposeStockCharts 一併釋放
    assert ".chip-g .kv{grid-template-columns:none;grid-auto-flow:column;" in CSS               # 寬螢幕一組一列
    assert "@media (max-width:520px){.chip-g .kv{grid-auto-flow:row;grid-template-columns:repeat(2,minmax(0,1fr))}" in CSS


def test_chip_charts_node():
    js = HELPERS + "\n" + "\n".join(_grab(STK, n) for n in ("INVESTORS", "disposeKCharts", "adjFactors", "aggregate", "buildChip")) + r"""
let charts = [], chipN = 'all';
const css = () => '#888', created = [], els = {};
const $ = s => s in els ? els[s] : (els[s] = { innerHTML: '' });
const window = { LightweightCharts: { createChart: (el, opt) => {
  const c = { el, opt, ser: [], addLineSeries(o) { const s = { o, setData(d) { this.data = d; }, createPriceLine(p) { this.pl = p; } }; this.ser.push(s); return s; },
    timeScale: () => ({ fitContent() {} }), subscribeCrosshairMove(f) { this.cb = f; }, setCrosshairPosition(v, t) { this.cross = [v, t]; },
    clearCrosshairPosition() { this.cross = null; }, remove() { this.removed = true; } };
  created.push(c); return c; } } };
const D = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13'];
const data = { market: 'TWSE', prices: { d: D, o: [10, 11, 12, 13, 14], h: [10, 11, 12, 13, 14], l: [10, 11, 12, 13, 14], c: [10, 11, 12, 13, 14], v: [1, 1, 1, 1, 1], ch: [0, 1, 1, 1, 1] },
  insti: { f: [10, -20, 30, 5, null], t: [1, 1, 1, 1, null], dl: [0, 0, 0, -2, null] }, mg: { mb: [100, 110, 120, 130, 140], sb: [1, 2, 3, 4, 5], lb: [50, 60, 70, null, null] }, ev: [] };
buildChip(data, false);
const all = { n: created.length, ids: created.map(c => c.el === els['#cpC'] ? 'cp' : c.el === els['#ciC'] ? 'ci' : c.el === els['#cmC'] ? 'cm' : 'cl'),
  scroll: created.map(c => c.opt.handleScroll || c.opt.handleScale), entire: created.every(c => c.opt.rightPriceScale.entireTextOnly),
  cum: created[1].ser.map(s => s.data.map(p => p.value ?? null)), zero: created[1].ser[0].pl.price,
  ci: els['#ciCL'].innerHTML, cm: els['#cmCL'].innerHTML, cl: els['#clCL'].innerHTML, cp: els['#cpCL'].innerHTML };
created[1].cb({ logical: 1, time: D[1] });
const hover = { ci: els['#ciCL'].innerHTML, cross: created[0].cross, cm: created[2].cross };
const before = created.slice();
chipN = '2'; created.length = 0; buildChip(data, false);
const two = { removed: before.every(c => c.removed), cum: created[1].ser[0].data.map(p => p.value ?? null), ci: els['#ciCL'].innerHTML };
created.length = 0; els['#cpC'] = null; chipN = 'all'; buildChip(data, true);   // ETF：沒有法人圖
console.log(JSON.stringify({ all, hover, two, etf: created.length }));"""
    o = _node(js)
    if o is None:
        return
    a = o["all"]
    assert a["n"] == 4 and a["ids"] == ["cp", "ci", "cm", "cl"] and a["scroll"] == [False] * 4 and a["entire"], a
    assert a["cum"] == [[10, -10, 20, 25, None], [1, 2, 3, 4, None], [0, 0, 0, -2, None]], a["cum"]      # 從區間第一天起加總；缺值不補
    assert a["zero"] == 0
    # 最新一天法人還沒有：圖例改顯示最近有資料的那天，並寫出日期
    assert a["ci"].startswith('<span class="muted">11/12</span>') and '外資 <b class="num up">+25</b><span class="muted">（當日 +5）</span>' in a["ci"], a["ci"]
    assert '自營 <b class="num dn">-2</b>' in a["ci"]
    assert "融資 <b class=\"num\">140</b>" in a["cm"] and "券資比 <b class=\"num\">3.57%</b>" in a["cm"] and "<b>11/13</b>" in a["cm"]
    assert "<b>11/11</b>" in a["cl"] and "借券賣出 <b class=\"num\">70</b>" in a["cl"]
    assert "收 <b>14</b>" in a["cp"]
    h = o["hover"]
    assert '外資 <b class="num dn">-10</b><span class="muted">（當日 -20）</span>' in h["ci"] and h["cross"] == [11, D1] and h["cm"] == [110, D1], h
    t = o["two"]
    assert t["removed"] and t["cum"] == [5, None] and '外資 <b class="num up">+5</b>' in t["ci"], t
    assert o["etf"] == 2                                            # ETF：只有融資、借券兩張


D1 = "2026-11-10"


# ─── D28-02：期貨未平倉表 375 不橫捲 ──────────────────────
def test_oi_table_padding():
    # 原本 ≤520 的 5px 被後面的 .tbl 6px 蓋掉（表 321 > 框 309，「增減」最後一位數被切）；提高權重改成 4px
    assert "@media (max-width:520px){table.oi-tbl th,table.oi-tbl td{padding:8px 4px}" in CSS
    assert CSS.index("table.oi-tbl th,table.oi-tbl td{padding:8px 4px}") > CSS.index("@media (max-width:520px){\n  .tbl th,.tbl td{padding:8px 6px}")


# ─── D28-03：返回時還原捲動位置 ───────────────────────────
def test_route_scroll_restore():
    assert "history.scrollRestoration = 'manual';" in APP
    assert "addEventListener('scroll', () => { if (scrollKey) scrollAt[scrollKey] = window.scrollY; }, { passive: true });" in APP
    assert "window.scrollTo(0, 0);" not in _grab(APP, "route")
    js = _grab(APP, "esc") + "\n" + _grab(APP, "scrollAt") + "\nlet scrollKey = null;\n" + _grab(APP, "route") + r"""
let hash = '', during = [];
const location = { get hash() { return hash; } };
const history = { state: null, replaceState(s, t, u) { this.state = s; if (u) hash = u; } };
const scrolls = [], window = { scrollTo: (x, y) => scrolls.push(y) };
const document = { title: '', querySelectorAll: () => [] }, $ = () => null, App = {};
const disposeFuturesChart = () => {}, renderToday = async () => {};
const page = async () => { during.push(scrollKey); };
const routes = { rank: page, stock: page, watch: page, bubble: page };
(async () => {
  hash = '#/rank/n+'; await route(); const k1 = history.state.k;
  scrollAt[scrollKey] = 1576;                                       // 捲動監聽記下的位置
  hash = '#/stock/2330'; history.state = null; await route(); const k2 = history.state.k;
  hash = '#/rank/n+'; history.state = { k: k1 }; await route();     // 返回
  hash = '#/stock/2330'; history.state = { k: k2 }; await route();  // 前進：個股頁沒捲過 → 頂端
  hash = '#/watch/abc'; history.state = null; await route(); const w = hash;
  hash = '#/bubble/x'; history.state = null; await route();
  console.log(JSON.stringify({ scrolls, during, same: k1 === k2, w, b: hash, k: typeof history.state.k }));
})();"""
    o = _node(js)
    if o is None:
        return
    assert o["scrolls"] == [0, 0, 1576, 0, 0, 0], o            # 新頁到頂端，返回還原
    assert o["during"] == [None] * 6 and o["same"] is False      # 換頁中不記錄；每筆紀錄的鍵不同
    assert o["w"] == "#/watch" and o["b"] == "#/bubble" and o["k"] == "number"


# ─── D28-04、07：泡泡圖手機清單、提示框格式 ─────────────────
def test_bubble_list_node():
    js = HELPERS + "\n" + _grab(APP, "pctCell") + "\n" + "\n".join(_grab(APP, n) for n in ("groupMeta", "groupRows", "bubbleList")) + r"""
const App = { group: 'industry', blOpen: 'B', latest: { dates: ['2026-11-12', '2026-11-13'], flow_date: '2026-11-13',
  stocks: { 1101: { n: '台泥', c: 30, p: 1.2, n1: 0.5, n5: 2 } } } };
const G = [{ name: 'B', quadrant: '退潮', frames: [null, [-3, -1, -0.5, 2000]], codes: [], net_5d: -3, streak: -2 },
  { name: 'A', quadrant: '漲潮', frames: [null, [5, 1, 1.5, 100]], codes: ['1101'], net_5d: 5, streak: 2 },
  { name: 'C', quadrant: '輪動', frames: [[1, 1, 1, 1], null], codes: [], net_5d: 1, streak: 1 }];
const h1 = bubbleList(G); App.blOpen = null; App.group = 'chain';
console.log(JSON.stringify({ h1, h2: bubbleList(G) }));"""
    o = _node(js)
    if o is None:
        return
    h = o["h1"]
    assert "<th>類股</th><th>近5日</th><th>日均差</th><th>漲跌</th><th>成交</th>" in h and "資料日 11/13" in h
    assert h.index('data-bl="A"') < h.index('data-bl="B"') and 'data-bl="C"' not in h       # 近 5 日由大到小；最新一天沒有值的不列
    assert '<td class="num up">+5.0億</td><td class="num up">+1.0</td><td class="num up">+1.50%</td><td class="num">100</td>' in h
    assert '<tr data-bl="B" class="on">' in h and '<i style="color:var(--dn)">退潮</i>' in h
    assert '<tr class="bl-x"><td colspan="5">' in h and h.index('<tr class="bl-x">') > h.index('data-bl="B"')
    assert '<div class="tbl-wrap panel-list"><table class="tbl"><thead><tr><th>股票</th>' in h
    assert "bl-x" not in o["h2"] and "<th>產業鏈</th>" in o["h2"]


def test_bubble_source():
    assert "const mob = matchMedia('(max-width:720px)').matches, list = mob && App.bubbleView !== 'chart';" in APP   # 手機預設清單
    assert "segHTML('bvSeg', [['chart', '圖'], ['list', '清單']]" in APP and "localStore('bubbleView'" not in APP
    assert "App.blOpen = g.dataset.group; App.blJump = 1;" in APP                                # 今日頁點族群：展開並捲到那一列
    assert "'#view .tbl-wrap:not(.panel-list)'" in APP and ".panel-list{--th-y:0px}" in CSS        # 內層捲動框不位移表頭
    assert ".bl-x .tbl-wrap{width:0;min-width:100%}" in CSS                                        # 展開的表不撐寬清單
    tpl = re.search(r"hovertemplate: '(<b>%\{customdata\[0\]\}.*?)'", APP).group(1)
    assert ":+" not in tpl and ":," not in tpl and "%{customdata[1]}" in tpl                       # Plotly basic 不認得 +.1f
    assert "return [g.name, amount(f[0]), sgn(f[1], 1) + '億/天', sgn(f[2]) + '%', fmt(f[3]) + '億'];" in APP   # 近 5 日和泡泡上的字同一種格式


# ─── D28-05、06：個股走勢分頁 ─────────────────────────────
def test_k_tab_layout():
    assert "else $('#vC').after($('#view .metrics.kv'));" in STK and "$('#kC').after(" not in STK
    assert "#vC+.kv .card:last-child:nth-child(3n+1){grid-column:span 3}" in CSS
    assert "$('#gUnit').textContent = adj ? '餘額（張）' : '餘額（張，官方原始）';" in STK
    assert "$('#gUnit').title = adj ? '面額變更、減資前的餘額依官方換算' : '';" in STK
    assert "mgView(data.mg))}<span id=\"gUnit\"></span>" in STK and "（張；面額變更、減資前的餘額依官方換算）" not in STK
    assert ".ch-label{row-gap:2px}.mg-l{align-items:center}" in CSS
    assert "autoscaleInfoProvider: symScale" in STK and "entireTextOnly: true" in STK
    line = next(l for l in STK.splitlines() if "const symScale = " in l).strip()
    js = line + r"""
const r = symScale(() => ({ priceRange: { minValue: -400, maxValue: 120 }, margins: { above: 1 } }));
console.log(JSON.stringify([r, symScale(() => null), symScale(() => ({ priceRange: { minValue: 0, maxValue: 0 } }))]));"""
    o = _node(js)
    if o is not None:
        assert o[0] == {"priceRange": {"minValue": -400, "maxValue": 400}, "margins": {"above": 1}}, o
        assert o[1] is None and o[2] == {"priceRange": {"minValue": 0, "maxValue": 0}}


def test_margin_legend_node():
    blk = STK[STK.index("      const gv = mgView(G);"):STK.index("    }\n  };\n  let crossSyncing")]
    js = HELPERS + "\n" + _grab(STK, "mgView") + r"""
let v = 'mb'; const localStore = () => v, els = {}, $ = s => (els[s] = els[s] || {});
const T = ['2026-11-12', '2026-11-13'], MB = [100, 200], SB = [1, 4], LB = [7, 8], G = { lb: [7, 8] }, out = [];
for (const k of ['mb', 'sb', 'lb']) { v = k; const g = 1, i = 1, GV = { mb: [MB, '#1C7ED6'], sb: [SB, '#AE3EC9'], lb: [LB, '#E8590C'] }[k];
""" + blk + r"""
  out.push($('#gLegend').innerHTML); }
console.log(JSON.stringify(out));"""
    o = _node(js)
    if o is None:
        return
    assert o[0] == '<span class="lg"><i style="background:#1C7ED6"></i>融資 <b class="num">200</b></span><span class="lg">券資比 <b class="num">2.00%</b></span>', o[0]
    assert "融券 <b class=\"num\">4</b>" in o[1] and "券資比" in o[1] and "融資" not in o[1]
    assert "借券 <b class=\"num\">8</b>" in o[2] and "券資比" not in o[2]


# ─── D28-08：未知分頁、非 ETF 代號 ─────────────────────────
def test_unknown_routes():
    assert "if (sub && sub !== tab) history.replaceState(history.state, '', `#/stock/${code}/${tab}`);" in STK
    assert "if ((page === 'watch' || page === 'bubble') && arg) history.replaceState(history.state, '', '#/' + page);" in APP
    assert "的持股資料尚未支援（目前支援統一、群益投信 8 檔主動 ETF）" not in APP
    assert "找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href=\"#/etf\"" in APP and "document.title = 'ETF｜台股資金流';" in APP


def test_no_advice_words():
    seg = "".join(l for l in APP.splitlines() + STK.splitlines() + CSS.splitlines() if "第 28 輪" in l or "D28-" in l)
    for n in ("bubbleList", "buildChip", "groupMeta"):
        if re.search(rf"^(?:const |function ){n}\b", APP + "\n" + STK, re.M):
            seg += _grab(APP if n != "buildChip" else STK, n)
    assert seg or "第 28 輪" not in APP + STK + CSS
    seg = seg.replace("借券賣出", "")                                           # 資料欄名稱（官方「借券賣出餘額」），不是用語
    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "低估", "高估", "建議"):
        assert w not in seg, w


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            print("==", name)
            fn()
            print("✅", name)
    print("全部通過")
```
