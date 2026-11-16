# 第 30 輪｜UI/UX 設計師：全站體檢（U30-01～12）

- 撰寫日期：2026-11-17（週二）
- 依據：`30/01-analyst.md`（U30-01～12）；使用者 11/17「照建議，進設計師」。
- 做法：
  - 在 scratchpad 副本做原型：`orig` 是專案原樣，`proj` 是修改後；`site/data` 連到專案資料，**沒有 `export`，沒有寫資料庫**。
  - 在 8001 實測 375／1024、淺／深。測完已關閉 8001，瀏覽器恢復桌面大小與淺色，localStorage 恢復成 `{"tw.todayTab":"ov"}`。
  - 專案的 `site/`、`tests/` **都沒有動**。本文件附錄 A 是完整 diff，由 PG 套用。
- 守則：沒有碰 8000、`.env`、`_archive/`；沒有安裝排程；沒有外部請求；沒有 commit。

---

## 〇、結論摘要

| 項目 | 結果 |
|---|---|
| 本輪範圍 | D30-01～12，對應分析師 **U30-01～12 全部** |
| 不放本輪 | 分析師第六節「不建議改動」全部保留；期貨分頁只記錄、不改 |
| 需使用者決定 | **舊測試 2 行**（第五節），其他都照分析師建議預設 |
| 變更量 | `app.css` ＋20／−0、`app.js` ＋80／−51、`stock.js` ＋10／−4、`index.html` ＋3／−3（`?v=`） |
| 舊測試 | **改 2 個檔、各 1 行**：`test_iter14:94`、`test_iter27:153`。只換字面，原意圖保留（理由見 4-2） |
| 新測試 | `tests/test_iter30.py`：8 個測試，162 行 |
| 測試結果 | `proj` 執行 `test_iter01～30` **30 個全部通過**；`node --check` 通過 |
| 反向驗證 | 用 `orig` 跑 `test_iter30`：**8 個全部失敗**。`test_no_advice_words` 失敗是因為取不到新函式 `mxTbl` |
| 套用檢查 | 附錄 A 對專案現況 `patch -p1 --dry-run`：7 個檔都乾淨套用 |
| 和第 29 輪階段二 | `03-design-B.diff` 會在 `stock.js`、`index.html` 的 `?v=` 衝突。依使用者決定，階段二時由 PG 以當時程式重做 B diff（見 4-4） |
| 資料口徑 | 不新增欄位，不改 `site/data`、`twstock/`。**不新增 localStorage 鍵** |

---

## 一、設計原則與風格方向

### 1-1 延續既有視覺語言

- 以下都不動：
  - 圓角卡片、膠囊分段鈕（`segHTML`）、紅漲綠跌。
  - 第 25 輪色彩 token、第 26 輪深淺色。
  - 第 27 輪長表格表頭跟頂欄（`stickHeads`）。
- **不新增色彩 token**。新樣式只用 `--bg`、`--text2`、`--blue`、`--line` 等既有變數。
- 新元件由既有元件組成：
  - 小表 `table.mx` 沿用 `.num` 數字字型、表格線色。
  - 「顯示全部」用既有 `.chip`。
  - 分頁列沿用 `.page-tabs`＋`segHTML`。

### 1-2 本輪主軸：「同類資訊同一種排法」與「長的東西先收起來」

| 類型 | 項目 | 原則 |
|---|---|---|
| 找不到 | U30-01 分頁列、U30-06 象限、U30-09 第一屏 | 常用的控制項固定在看得到的地方；點了要直接看到結果 |
| 讀不順 | U30-03、05、07、12 | 同一種資訊（指標 × 上市／上櫃）用表格對齊，不寫成段落 |
| 太長 | U30-04、U30-08、U30-11 | 先顯示前段，留一顆「顯示全部」；不用頁內捲動框 |
| 誤導 | U30-10 | 顏色跟著畫面上的數字：顯示 0 就是灰色 |
| 太窄 | U30-02 | 手機清單用滿螢幕寬 |

### 1-3 不改的東西

- 分析師第六節「不建議改動」全部保留：
  - 籌碼分頁（第 29 輪剛改，也是 B diff 的範圍）。
  - 期貨分頁、泡泡圖本體、`hlTag` 文字。
  - 第 28 輪的返回位置、`tw.*` 鍵名。
- 為了減少階段二 B diff 重做的量，**`buildChip`、籌碼分頁一行都沒動**。`stock.js` 只改頁首、分頁列、基本面卡片的 class。

---

## 二、本輪範圍（D30-xx）

| D30 | 對應 | 內容 | 檔案 |
|---|---|---|---|
| D30-01 | U30-01 | 個股頁分頁列 sticky，貼在頂欄下。固定時右側顯示名稱與價格。在固定狀態換分頁，新分頁從分頁列下方開始 | stock、app（`stickHeads`）、css |
| D30-02 | U30-02 | 手機搜尋清單左右各留 8px、全寬；名稱單行、超出用省略號 | app、css |
| D30-03 | U30-03 | 「信用估值」的信用交易卡、估值卡改成「指標 × 上市／上櫃」小表 | app、css |
| D30-04 | U30-04 | ETF 列表預設 50 檔＋「顯示全部 N 檔」；有篩選字時搜尋全部 | app |
| D30-05 | U30-05 | 市場寬度卡同樣改小表 | app |
| D30-06 | U30-06 | 資金象限四格各自是連結；進泡泡清單時標示該象限、捲到第一列 | app、css |
| D30-07 | U30-07 | 「差一次」改成一檔一列，和同區其他清單同一格式 | app、css |
| D30-08 | U30-08 | 手機泡泡清單展開的成分股不再是內捲動框：前 10 檔＋「顯示全部」 | app、css |
| D30-09 | U30-09 | 手機頁首新訊號只顯示第 1 個＋「+N」，點了展開 | stock、css |
| D30-10 | U30-10 | 顯示「0億」時用灰色 | app、stock |
| D30-11 | U30-11 | 排行頁種類下拉選單併入快捷列同一行，手機可橫捲 | app、css |
| D30-12 | U30-12 | 基本面估值 3 張卡在手機排成一列；股利表縮小內距 | stock、css |

### 2-1 不放本輪的項目與理由

- 期貨分頁：分析師只記錄、不列問題。
- 改頁首資訊的內容（例如新訊號排序）：屬於內容調整，不是版面調整，本輪只做收合。
- 搜尋清單的鍵盤操作：分析師沒有列，原本就可以用。

---

## 三、各項規格

> 實測：8001，資料日 2026-11-16。數字是 375 淺色，另外註明的除外。

### D30-01 個股頁分頁列固定（U30-01）

- **改前**：「走勢／籌碼／基本面」在 y=377，頁高 2,551～2,853px。在頁底要換分頁得捲回頂端。
- **改後**：
  - 分頁列 `position:sticky; top:var(--top-h)`，背景 `--bg`，`z-index:15`（低於頂欄）。
  - 捲過頁首後（IntersectionObserver 觀察 `.s-head`）加上 `.stuck`，右側出現 `.pt-nm`：「名稱 收盤 漲跌%」，顏色跟漲跌。這樣固定時仍看得出是哪一檔。
  - **固定狀態換分頁**：點擊時先記下 `App.ptStuck`，重畫後捲到「分頁列頂 − 頂欄高」。新分頁的內容從分頁列下方開始，不會停在新分頁的中間。在頂端換分頁時不捲動。
  - `stickHeads` 的起點取「頂欄底」和「分頁列底」的較大值，長表格的表頭會貼在分頁列下方，不會互相蓋住。
- 實測：
  - 375 在頁底換分頁：分頁列停在 y=55，新內容緊接在下面；圖表沒有重複建立。
  - 1024 深色 2421 信用分頁：分頁列固定，沒有橫捲。
- 實作要點：
  - IntersectionObserver 在瀏覽器窗格隱藏時不觸發，所以「是否固定」在點擊當下用 `getBoundingClientRect` 計算，不依賴 `.stuck`。
  - 量分頁列位置時，暫時設成 `position:static`。否則 sticky 狀態下量到的是固定後的位置，會差 16px。
  - 保留 `window.disposeStockCharts(); window.renderStock(code);` 字面（`test_iter12:104` 鎖定）。

### D30-02 手機搜尋清單（U30-02）

- **改前**：清單寬 263px，「中信成長高股息」折成 4 行，每列 80～100px，一屏只看到 5～6 筆。
- **改後**：
  - ≤720px 時 `.search{position:static}`，清單 `left:8px; right:8px`，以頂欄為基準，全寬。
  - 名稱放進 `.qn`，單行、超出用省略號。
- 實測：清單 359px 寬，每列 40px，「中信」12 筆一屏全部看到。1024 不變。

### D30-03 「信用估值」改小表（U30-03）

- **改前**：信用交易卡約 14 行文字，數字夾在句中；估值卡也是段落。
- **改後**：新增 `mxTbl(cols, rows)`，產生「指標 × 上市／上櫃」小表。
  - 欄：空白、上市、上櫃。資料日舊於當天時，欄名後加「（MM/DD）」。
  - 指標名下面可以加一行小字 `s2(...)`（11px、`--text2`）。
  - 信用交易：融資、融券、券資比、融資維持率（自算）、融資金額（官方，含 ETF）、借券賣出餘額（看排行 →）。
    - 「融券的 N 倍」換到同格的下一行。
    - 表下保留一句說明：「借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新」。
  - 估值：本益比、淨值比、殖利率（一年位置，越高 = 殖利率相對越高）、加權本益比（市值加權）。
    - `wpeLine` 改成只回傳說明；新增 `wpeRow` 回傳表格列。
- 版面：
  - 指標欄 `white-space:nowrap; width:1%`，小字可換行、最小 7em。
  - 第一版指標名會一字一行，表格寬 364 > 341 會溢出，所以加了這兩條規則。
- 實測：信用分頁 `scrollWidth = 375`，沒有橫捲。
  - 頁高 1,381 → 1,598，多 217px。
  - **取捨**：換來的是上市、上櫃的數字上下對齊，可以直接比較。

### D30-04 ETF 列表預設 50 檔（U30-04）

- **改前**：364 檔全列，375 頁高 27,177px。
- **改後**：
  - `const ETF_N = 50;`。超過 50 檔時，表下有按鈕「顯示全部 364 檔」，展開後變成「只顯示前 50 檔」。
  - 篩選框有字時搜尋全部 364 檔，並隱藏按鈕。
  - 展開狀態 `App.etfAll` 只在記憶體，不新增鍵。
- 實測：
  - 頁高 27,177 → 4,452。
  - 篩選「0050」找到 1 檔。
  - 「顯示全部」後是 364 列。

### D30-05 市場寬度卡改小表（U30-05）

- **改前**：「MA60 13.8%」換到第二行，看不出是上市還是上櫃。
- **改後**：同 D30-03 的 `mxTbl`。列是站上 MA20（前日）、站上 MA60、20 日新高、20 日新低、量能；欄是上市、上櫃。
- 實測：表高 191px，總覽頁高 1,589 → 1,710。

### D30-06 資金象限各自連結（U30-06）

- **改前**：四格都連到 `#/bubble`，點「觀望 1」進去還要自己在 34 列裡找。
- **改後**：
  - 每格是 `<a class="quad q-X" href="#/bubble" data-q="X">`。點擊時記下 `App.blQ`。
  - `renderBubble` 把它轉成 `App.blHit`（用一次就清掉）。
  - 泡泡清單中該象限的列加 `.q-hit`，第一欄左側有藍色內框；表上方顯示「已標示「觀望」1 個」，並捲到第一列。
  - 網址不變，不新增路由。
- 實測：點「觀望」→ 標示「電子零組件」並捲到該列。

### D30-07 「差一次」一檔一列（U30-07）

- **改前**：15 檔串成一段文字，連結高 14px，名稱跨行斷開。
- **改後**：
  - 先放小標「差一次：」，下面每檔一列 `a.al-row`。
  - 左邊是名稱與「目前 第 1 款連 2 日」，右邊是「差 1 次」。
  - 「第一款」統一寫成「第 1 款」，註腳也一起改。
- 實測：15 列，每列 50px，和同區其他清單一致。

### D30-08 泡泡清單展開成分股（U30-08）

- **改前**：內框 420／1,786px，手機上內外兩層捲動互搶，最後一列被切半。
- **改後**：
  - 展開區 `.panel-list` 不限高。
  - 超過 10 檔時只顯示前 10 檔，下方按鈕「顯示全部 210 檔」／「只顯示前 10 檔」。
  - 用 CSS `:has([data-blall="1"])` 控制顯示。`panel-list` 標記不變，因為 `test_iter28:188` 鎖定。
  - 展開別的類股時恢復成前 10 檔。
- 實測：展開半導體是 10 列＋按鈕，沒有內捲動。

### D30-09 頁首新訊號（U30-09）

- **改前**：頁首 262px，新訊號兩行加一句免責約 70px，K 線從 y=561 開始。
- **改後**：
  - ≤520px 且新訊號超過 1 個時，只顯示第 1 個與「+N」按鈕，免責句也先隱藏。
  - 點「+N」展開全部（加 `.open`）。
  - 1024 不變；`hlTag` 輸出不變。
- 實測：頁首 262 → 221，K 線頂端 561 → 532。

### D30-10 顯示 0 不上色（U30-10）

- **改前**：「農業科技 0億」是紅色；成分股「法人1日 0億」也是紅色。
- **改後**：
  - `app.js` 在 `yi` 同一行宣告 `ycls = n => cls(n != null && Math.abs(n) < 0.05 ? 0 : n)`。和 `yi` 同一個 `const`，是因為測試 20／23／28 用 `_grab` 取 `yi`。
  - 全部 14 處 `cls(X)}">${yi(X)}` 改成 `ycls(X)}">${yi(X)}`。
  - `stock.js` `cardsHTML`：值是「0億」時用 `flat`。inCards 保留 `cls(...)`，因為 `test_iter22:178、179` 鎖定。
- 顏色跟著畫面上的數字；數字本身不變。

### D30-11 排行控制項（U30-11）

- **改前**：種類下拉選單和 7 個快捷鈕分兩塊，表格從 y=364 開始。
- **改後**：`#rankSel` 移到 `.rk-q` 最前面，和快捷鈕同一行。≤720px 不換行、可橫捲。
- 實測：表格頂端 364 → 282。

### D30-12 基本面卡片與股利表（U30-12）

- **改前**：估值 3 張卡排成 2＋1，留一個空格；「填息」欄折 3 行。
- **改後**：
  - 基本面分頁 `.metrics` 加 `.m3`，≤520px 一列 3 張，卡片內距 8px。
  - 股利表左右內距 4px，不加 `nowrap`，因為「尚未填息」等長文字加了會溢出。
- 實測：3 張卡同一列，高 172px；股利表 309px 放得下，每列 70 → 53px。

---

## 四、不能破壞的事項

### 4-1 已確認

- `test_iter01～30` 全部通過。
- 375／1024、淺／深都沒有橫捲。
- 主控台沒有錯誤。
- 切換分頁、深淺色時圖表不重複建立。
- 用詞：新增的程式行與新函式沒有禁用詞（`test_iter30.test_no_advice_words` 檢查）。

### 4-2 避開的測試鎖定

| 測試 | 鎖定的內容 | 本輪做法 |
|---|---|---|
| `test_iter12:85` | `wpeLine` | 保留函式名，只回傳說明；表格列另寫 `wpeRow` |
| `test_iter12:104` | `window.disposeStockCharts(); window.renderStock(code);` | 字面保留，捲動用 `App.ptStuck` 旗標 |
| `test_iter14:93` | 「一年位置，越高 = 殖利率相對越高」 | 原句搬到小表的小字 |
| `test_iter20／23／28` | `_grab('yi')` | `ycls` 和 `yi` 寫在同一個 `const` |
| `test_iter22:178、179` | inCards 的 `cls(...)` | 不動 inCards，改在 `cardsHTML` 判斷 |
| `test_iter28:188` | `panel-list` 標記 | 標記不動，用 CSS `:has` 控制 |
| **`test_iter14:94`** | 本益比、淨值比的段落文字 | **避不開**：段落改成表格，字面一定會變。改成檢查表格列，意圖（兩個指標與一年位置都在）不變 |
| **`test_iter27:153`** | `台揚<span class="muted">（第一款連 2 日）</span>` | **避不開**：D30-07 改成一檔一列，並統一寫「第 1 款」。改成檢查新列的連結與理由，意圖（理由直接顯示）不變 |

### 4-3 `index.html` 的 `?v=`

| 檔 | 改前 | 改後 |
|---|---|---|
| `app.css` | 專案現值 | `a69df04b` |
| `app.js` | 專案現值 | `895b2037` |
| `stock.js` | 專案現值 | `41db19b1` |

- PG 若有手動調整，要重新算 sha1 前 8 碼；`test_iter23` 會檢查。

### 4-4 與第 29 輪階段二的衝突點

- B diff 動到 `stock.js`（`buildChip`、籌碼分頁）和 `index.html` 的 `?v=`。
- 本輪 `stock.js` 的改動在頁首、分頁列、`cardsHTML`、基本面 `.metrics`，**沒有碰 `buildChip`**。所以預期只有行號位移與 `?v=` 衝突。
- 依使用者決定：階段二時由 PG 以當時程式重做 B diff，重算 `?v=`，再跑 `test_iter01～30`（加上階段二新增的測試）。

---

## 五、需使用者決定

| 編號 | 項目 | 選項 | 建議 |
|---|---|---|---|
| 1 | `test_iter14:94` 改字面 | A 改成檢查小表列（本輪）；B 不改，D30-03 估值卡維持段落 | **A** |
| 2 | `test_iter27:153` 改字面 | A 改成檢查一檔一列（本輪）；B 不改，D30-07 維持段落 | **A** |

改前與改後：

```python
# test_iter14:94 改前
    assert "本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）" in APP   # 本益比、淨值比不變
# test_iter14:94 改後
    assert "['本益比', ...c(x => `<b>${fmt(x.pe?.v, 2)}</b>${s2(pos(x.pe))}`)], ['淨值比', ...c(x => `<b>${fmt(x.pb?.v, 2)}</b>${s2(pos(x.pb))}`)]" in APP   # 本益比、淨值比不變（第 30 輪 D30-03 改成小表）

# test_iter27:153 改前
        assert '<a href="#/stock/2314">台揚<span class="muted">（第一款連 2 日）</span></a>' in o   # 差一次的理由直接顯示
# test_iter27:153 改後
        assert '<a class="al-row" href="#/stock/2314"><div class="al-l"><b>台揚</b>' in o and '目前 第 1 款連 2 日</div>' in o   # 差一次的理由直接顯示（第 30 輪 D30-07：一檔一列）
```

- 其他設計選擇照分析師建議預設，不另外列：
  - ETF 預設 50 檔。
  - 泡泡成分股前 10 檔。
  - 新訊號手機只顯示 1 個。
  - 展開狀態都不記住。

---

## 六、給 PG 的實作順序

建議直接套用附錄 A：

```bash
cd tw-stock && patch -p1 < docs/iterations/30/02-design.diff
```

- 路徑前綴是 `orig/`、`proj/`，`-p1` 會去掉。
- 附錄 A 已經包含新檔 `tests/test_iter30.py`。

若要逐項手寫，順序如下，每步跑一次全部測試：

| 步驟 | 項目 | 驗證 |
|---|---|---|
| 1 | D30-10 `ycls`（app 14 處、stock `cardsHTML`） | `test_iter20／22／23／28`、`test_iter30.test_zero_color` |
| 2 | D30-02 搜尋清單 | `test_iter30.test_search_list`；375 量清單寬 |
| 3 | D30-03、05 `mxTbl`、`s2`、`marginCard`、`sblLine`、`breadthCard`、`valCard`、`wpeRow` | 改 `test_iter14:94`；`test_iter12`、`test_iter30.test_today_tables_node`；375 `scrollWidth` |
| 4 | D30-06、07 象限連結、差一次 | 改 `test_iter27:153`；`test_iter30.test_quads_and_near_node` |
| 5 | D30-08 泡泡成分股 | `test_iter28`、`test_iter30.test_bubble_list_node` |
| 6 | D30-04、11 ETF、排行 | `test_iter30.test_etf_and_rank_source` |
| 7 | D30-01、09、12 個股頁（stock、`stickHeads`） | `test_iter12`、`test_iter30.test_stock_page_source`；375 頁底換分頁 |
| 8 | CSS 檔尾一段、`?v=` 重算 | `test_iter23` |
| 合計 | 程式＋CSS ＋110／−55，舊測試 2 行，新測試 162 行 | `for f in tests/test_iter*.py; do python3 $f; done`；`node --check site/app.js site/stock.js` |

注意：

- node 是 v14：在 node 執行的函式（`marginCard`、`valCard`、`bubbleList` 等）不要用 `.at()`、`replaceAll`。
  - `valCard` 原本就有 `replaceAll`，測試用 polyfill 處理，**不要為此改程式**。
- 本輪**不新增 localStorage 鍵**：`App.etfAll`、`App.blAll`、`App.blQ`、`App.blHit`、`App.ptStuck` 都只在記憶體。
- 不需要 `export`，`site/data` 不變。

---

## 七、給 QA 的驗證清單

### 7-1 前置

1. 8001 啟動後，對 `/`、`app.css`、`app.js`、`stock.js` 執行 `await fetch(url,{cache:'reload'})`，再重新整理。確認 `?v=` 與 4-3 相同。
2. 開始前記下 localStorage；結束時還原（目前是 `{"tw.todayTab":"ov"}`）。本輪不新增鍵。
3. 尺寸 375×812、1024×800，淺／深。結束時 preset desktop、淺色，並關閉 8001。
4. 瀏覽器窗格隱藏時 IntersectionObserver 不觸發，`.pt-nm` 可能不出現。驗收 D30-01 時要讓窗格顯示。

### 7-2 逐頁清單（每頁 × 375／1024 × 淺／深）

| 頁面 | 檢查 | 量測方法 | 期望值 |
|---|---|---|---|
| 全部頁 | 不橫捲 | `document.documentElement.scrollWidth` | = 視窗寬 |
| 個股 2421 走勢（375） | 第一屏 | `#kC` 頂＋scrollY；頁首高 | 532；221 |
| 個股 2421 走勢（375） | 新訊號 | `.s-hl` 可見的 `.hl-tag` 數；點 `#hlMore` | 1 個＋「+N」；點了全部出現 |
| 個股（375） | 分頁列固定 | 捲到頁底，`.page-tabs` 頂 | = 頂欄高（約 55），右側有名稱與價格 |
| 個股（375） | 固定狀態換分頁 | 頁底點「籌碼」 | 分頁列仍在 55，籌碼內容從分頁列下方開始；`charts` 不重複 |
| 個股（375） | 頂端換分頁 | scrollY 0 點分頁 | scrollY 仍是 0 |
| 個股 基本面（375） | 估值卡 | `.metrics.m3 .card` 的 top 去重數 | 1 列 |
| 個股 基本面（375） | 股利表 | 表寬 vs 框寬 | 不超過框寬；「填息」欄 ≤ 2 行 |
| 搜尋（375） | 清單 | 輸入「中信」，量 `.qlist` 寬、列高 | 359、40；12 筆一屏 |
| 搜尋（1024） | 不變 | 同上 | 和改前相同 |
| 今日 信用估值 | 小表 | `table.mx` 數量、列名 | 信用：融資～借券賣出餘額 6 列；估值：4 列 |
| 今日 信用估值（375） | 對齊 | 指標名不一字一行；`scrollWidth` | 375 |
| 今日 總覽 | 市場寬度 | `table.mx` 列名 | 5 列，欄是上市、上櫃 |
| 今日 總覽 | 象限 | 點「觀望」 | 泡泡清單有 `tr.q-hit`、「已標示」字樣，並捲到該列 |
| 今日 總覽 | 差一次 | `.al-near ~ .al-row` | 一檔一列、「目前 第 1 款連 N 日」「差 1 次」 |
| 泡泡清單（375） | 0 不上色 | 找顯示「0億」的格 | class 是 `flat` |
| 泡泡清單（375） | 成分股 | 展開半導體 | 10 列＋「顯示全部 N 檔」，沒有內捲動；點了全部出現 |
| ETF | 預設 | `tbody tr` 可見數；頁高 | 50；375 約 4,452 |
| ETF | 篩選 | 輸入「0050」 | 1 列，按鈕隱藏 |
| 排行（375） | 控制項 | 表格頂端 | 282；選單與快捷鈕同一行 |
| 長表格 | 表頭 | 排行、ETF 捲動 | 表頭貼在頂欄下，個股頁時貼在分頁列下 |
| 主控台 | 錯誤 | `read_console_messages onlyErrors` | 0 個 |

### 7-3 回歸

- 第 28 輪：從排行、泡泡清單進個股再返回，捲動位置還原。
- 第 29 輪：籌碼分頁法人圖的切換、區間不受影響。
- 第 26 輪：每頁切換深淺色，小表、分頁列背景顏色跟著變。

---

## 附錄 A：完整 diff（`orig` → `proj`；`site/` 與 `tests/`，不含 `site/data`）

同內容另存為 `docs/iterations/30/02-design.diff`，可直接 `patch -p1`。

```diff
diff -ruN -x data -x __pycache__ orig/site/app.css proj/site/app.css
--- orig/site/app.css	2026-11-17 00:11:20
+++ proj/site/app.css	2026-11-17 00:52:19
@@ -327,3 +327,23 @@
 .bl-tbl tr[data-bl]{cursor:pointer}.bl-tbl tr.on>td{background:var(--card2)}.bl-tbl tr{scroll-margin-top:calc(var(--top-h,56px) + 44px)}.bl-tbl td.nm i{font-style:normal}   /* D28-04 泡泡清單 */
 .bl-x>td{text-align:left;white-space:normal;padding:2px 0 10px}.bl-x .tbl-wrap{width:0;min-width:100%}.panel-list{--th-y:0px}   /* 展開的成分股表不撐寬外層清單，自己橫捲 */
 @media (max-width:520px){.bl-x table.tbl{font-size:12px}.bl-x table.tbl th,.bl-x table.tbl td{padding-left:4px;padding-right:4px}}@media (max-width:380px){table.bl-tbl>*>tr>*{padding-left:4px;padding-right:4px}.bl-x table.tbl th,.bl-x table.tbl td{padding-left:3px;padding-right:3px}}   /* QA28-02：手機展開的成分股表、360 寬清單數字完整不被切 */
+/* 第 30 輪 UI/UX 全站體檢 */
+.page-tabs.pt-stick{position:sticky;top:var(--top-h,56px);z-index:15;display:flex;align-items:center;gap:10px;background:var(--bg);padding:4px 0;margin:6px 0 0}   /* D30-01 */
+.pt-nm{display:none;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}.pt-stick.stuck .pt-nm{display:block}
+.pt-stick.stuck{box-shadow:0 1px 0 var(--border)}
+.qlist a{align-items:center}.qn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}   /* D30-02 */
+@media (max-width:720px){.search{position:static}.qlist{left:8px;right:8px;top:calc(100% + 4px)}}
+table.mx{width:100%;border-collapse:collapse;margin:6px 0 2px;font-size:13px}   /* D30-03、05 */
+.mx th,.mx td{padding:5px 4px;border-bottom:1px solid var(--border);text-align:right;vertical-align:top;font-weight:400}
+.mx thead th{color:var(--text2);font-size:12px;padding-top:0}.mx tbody th{text-align:left;color:var(--text2);font-size:12px}.mx tr:last-child>*{border-bottom:0}
+.mx .s2{font-size:11px;color:var(--text2)}.mx .s2 a{color:inherit}.mx .up{color:var(--up)}.mx .dn{color:var(--dn)}.mx .flat{color:var(--flat)}
+.etf-tbl td.nm b{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}   /* D30-04 */
+a.quad{display:block;color:inherit;text-decoration:none}   /* D30-06 */
+.bl-tbl tr.q-hit>td:first-child{box-shadow:inset 3px 0 0 var(--blue)}.bl-hit{margin:0 0 6px}
+.al-near{line-height:1.5}   /* D30-07 */
+.bl-x .panel-list{max-height:none}.bl-x:not(:has([data-blall="1"])) .panel-list tbody tr:nth-child(n+11){display:none}.bl-x .chip{margin-top:6px}   /* D30-08 */
+.hl-more{display:none}   /* D30-09 */
+@media (max-width:520px){.hl-more{display:inline-block}.s-hl:not(.open) .hl-tag~.hl-tag,.s-hl:has(.hl-more):not(.open)>span.muted{display:none}.s-hl.open .hl-more{display:none}}
+.rk-q #rankSel{flex:none}@media (max-width:720px){.rk-q{flex-wrap:nowrap;overflow-x:auto;padding-bottom:2px}.rk-q .chip{flex:none;white-space:nowrap}}   /* D30-11 */
+@media (max-width:520px){.metrics.m3{grid-template-columns:repeat(3,minmax(0,1fr))}.metrics.m3 .card{padding:8px}table.dv-tbl th,table.dv-tbl td{padding-left:4px;padding-right:4px}}   /* D30-12 */
+.mx tbody th{white-space:nowrap;width:1%}.mx tbody th .s2{white-space:normal;min-width:7em}
diff -ruN -x data -x __pycache__ orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-15 21:05:55
+++ proj/site/app.js	2026-11-17 00:50:46
@@ -29,7 +29,8 @@
 const pctCell = s => s.nt ? `<td class="flat small" title="最後成交 ${s.nt}">無成交</td>`
   : `<td class="num ${cls(s.p)}${s.rel ? ' rel' : ''}"${s.rel ? ` title="相對 ${md(s.rel)} 收盤（前一交易日無成交）"` : ''}>${sgn(s.p)}%</td>`;
 // 不到 0.05 億四捨五入後是 0，避免顯示「-0.0億」
-const yi = n => n == null ? '--' : Math.abs(n) < 0.05 ? '0億' : sgn(n, Math.abs(n) >= 100 ? 0 : 1) + '億';
+// 第 30 輪 D30-10：ycls 是 yi 數字的漲跌色，顯示「0億」時為灰色（顏色跟著顯示的數字）
+const yi = n => n == null ? '--' : Math.abs(n) < 0.05 ? '0億' : sgn(n, Math.abs(n) >= 100 ? 0 : 1) + '億', ycls = n => cls(n != null && Math.abs(n) < 0.05 ? 0 : n);
 const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
 
 async function getJSON(url) {
@@ -105,7 +106,7 @@
 // 第 27 輪 D27-01：25 列以上的表格不再關在固定高度的捲動框裡（整頁捲動，不會被畫面底部或底部選單擋住）。
 // .tbl-wrap 要保留橫向捲動，CSS sticky 只能貼在框內，所以捲動時把表頭位移到頂欄下方（--th-y，最多到表格最後兩列）
 function stickHeads() {
-  const top = $('.top').getBoundingClientRect().bottom;
+  const top = Math.max($('.top').getBoundingClientRect().bottom, $('#view .pt-stick')?.getBoundingClientRect().bottom ?? 0);   // 第 30 輪 D30-01
   [...document.querySelectorAll('#view .tbl-wrap:not(.panel-list)')].filter(w => w.querySelector('tbody tr:nth-child(25)'))
     .map(w => [w, w.getBoundingClientRect(), w.querySelector('thead')?.offsetHeight || 0])
     .forEach(([w, r, h]) => w.style.setProperty('--th-y', Math.max(0, Math.min(top - r.top, r.height - 2 * h)) + 'px'));
@@ -118,7 +119,7 @@
   const go = code => { list.hidden = true; input.value = ''; input.blur(); location.hash = '#/stock/' + code; };
   const draw = () => {
     list.innerHTML = hits.map(([c, s], i) =>
-      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span>${esc(s.n)}<span class="muted small ind" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span>` +
+      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span><span class="qn">${esc(s.n)}</span><span class="muted small ind" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span>` +
       `<span class="px num ${cls(s.p)}">${pfmt(s.c)}${s.p == null ? '' : ' ' + sgn(s.p) + '%'}</span>` +
       `<span class="qstar${App.watch.has(c) ? ' on' : ''}" role="button" data-w="${c}" title="${App.watch.has(c) ? '從自選移除' : '加入自選'}">${App.watch.has(c) ? '★' : '☆'}</span></a>`).join('') ||   // D27-09
       (input.value.trim() && App.latest ? `<div class="qnone">找不到「${esc(input.value.trim())}」，可輸入代號或名稱的一部分</div>` : '');   // 第 25 輪 D25-11
@@ -192,11 +193,11 @@
   const bar = (g, color) => `<div class="bar-row" data-group="${esc(g.name)}">
       <span class="nm">${esc(g.name)}</span>
       <span class="bar-track"><span class="bar-fill" style="width:${Math.abs(g[key]) / maxAbs * 100}%;background:${color}"></span></span>
-      <span class="val num ${cls(g[key])}">${yi(g[key])}</span></div>`;
+      <span class="val num ${ycls(g[key])}">${yi(g[key])}</span></div>`;
   const rows = list => list.map(([c, s]) => `<tr data-code="${c}">
       <td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>${c}</span></td>
       <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
-      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');
+      <td class="num ${ycls(s.n1)}">${yi(s.n1)}</td></tr>`).join('');
 
   // 分頁：指數卡永遠顯示，其餘依分頁只輸出該頁的區塊（圖表不會畫在隱藏的容器裡）
   const tab = pageTab('todayTab', TODAY_TABS);
@@ -210,9 +211,9 @@
 
     <section class="sec">
       <div class="sec-h"><h2>資金象限</h2><span class="sp"></span>${groupSeg()}</div>
-      <a class="quads" href="#/bubble">
-        ${QUADS.map(([q, d]) => `<div class="quad q-${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></div>`).join('')}
-      </a>
+      <div class="quads">
+        ${QUADS.map(([q, d]) => `<a class="quad q-${q}" href="#/bubble" data-q="${q}"><div class="t">${q}</div><div class="n num">${counts[q]}</div><div class="d">${d}</div></a>`).join('')}
+      </div>
     </section>
     ${alertBoard(L)}`,
     credit: `<section class="sec grid ${marginCard(L) && valCard(L) ? 'g2' : 'g-one'}">${marginCard(L)}${valCard(L)}</section>`,   // 信用交易、估值左右並排
@@ -243,6 +244,7 @@
     ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
     ${body[tab]}`;
 
+  $('#view .quads')?.addEventListener('click', e => { App.blQ = e.target.closest('[data-q]')?.dataset.q; });   // 第 30 輪 D30-06
   onSeg('todayTabSeg', v => { localStore('todayTab', null, App.todayTab = v); history.replaceState(null, '', '#/today/' + v); disposeFuturesChart(); renderToday(); });
   if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
@@ -327,6 +329,10 @@
     '</svg>';
 }
 
+// 第 30 輪 D30-03：今日頁信用、寬度、估值卡的上市／上櫃數字改成「指標 × 市場」小表（數字與口徑不變，只改排版）
+const mxTbl = (cols, rows) => `<table class="mx num"><thead><tr><th></th>${cols.map(c => `<th>${c}</th>`).join('')}</tr></thead><tbody>` +
+  rows.filter(Boolean).map(([l, ...v]) => `<tr><th>${l}</th>${v.map(x => `<td>${x}</td>`).join('')}</tr>`).join('') + '</tbody></table>';
+const s2 = t => `<div class="s2">${t}</div>`;
 // 信用交易卡（B2＋A4）：頭條為股票口徑（不含 ETF）；官方含 ETF 只列融資金額；ETF 另計一行；官方融資、融券張數不顯示
 function marginCard(L) {
   const M = L.margin;
@@ -334,18 +340,23 @@
   const T = M.TWSE, O = M.TPEx, d = [T?.d, O?.d].filter(Boolean).sort().at(-1);
   const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, 1)}</b> 萬張`;
   const lots = n => `<span class="${cls(n)}">${sgn(n, 0)}</span>`;
-  const row = (x, name) => !x ? '' : `<div class="s num">${name}　<span class="nw">融資 ${wan(x.mb)} ${lots(x.m1)}（${sgn(x.mp)}%）</span>　<span class="nw">融券 ${wan(x.sb)} ${lots(x.s1)}</span>　<span class="nw">券資比 ${fmt(x.sr, 2)}%</span>${x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : ''}</div>`;
-  const mr = x => !x ? '--' : x.mr == null ? '資料不足' : `${fmt(x.mr, 1)}%（前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}）`;
-  const amt = x => !x ? '--' : `${fmt(x.amt, 1)} 億 <span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`;
+  const c = f => [T, O].map(x => !x ? '--' : f(x));
+  const col = (x, name) => name + (x && x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : '');
+  const mr = x => x.mr == null ? '資料不足' : `<b>${fmt(x.mr, 1)}%</b>${s2(`前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}`)}`;
+  const amt = x => `${fmt(x.amt, 1)} 億${s2(`<span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`)}`;
   const E = T?.etf;
   // P22：依上市股票口徑 1 日變動較大的一邊，連到融資融券排行
   const X = T || O, rk = !X ? '' : Math.abs(X.sp ?? 0) >= Math.abs(X.mp ?? 0) ? (X.sp < 0 ? 's-' : 's+') : (X.mp < 0 ? 'm-' : 'm+');
   return `<div class="card stat idx margin">
       <div class="l">信用交易 ${md(d)}（股票，不含 ETF）${d < L.date ? '<span class="muted">（尚未更新）</span>' : ''}${rk ? `　<a class="muted small" href="#/rank/${rk}">看排行 →</a>` : ''}</div>
-      ${row(T, '上市')}${row(O, '上櫃')}
-      <div class="s num">融資維持率（自算）上市 ${mr(T)}　上櫃 ${mr(O)}</div>
-      <div class="s num">融資金額（官方，含 ETF）上市 ${amt(T)}　上櫃 ${amt(O)}</div>
-      ${sblLine(L)}
+      ${mxTbl([col(T, '上市'), col(O, '上櫃')], [
+        ['融資', ...c(x => `${wan(x.mb)}${s2(`${lots(x.m1)}（${sgn(x.mp)}%）`)}`)],
+        ['融券', ...c(x => `${wan(x.sb)}${s2(lots(x.s1))}`)],
+        ['券資比', ...c(x => `${fmt(x.sr, 2)}%`)],
+        ['融資維持率' + s2('自算'), ...c(mr)],
+        ['融資金額' + s2('官方，含 ETF'), ...c(amt)],
+        sblLine(L)])}
+      ${L.sbl ? '<div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>' : ''}
       ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
       ${etfSblLine(L.sbl_etf)}
       ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
@@ -355,14 +366,13 @@
 }
 
 // 第 11 輪 B14：借券賣出餘額（股票口徑，張）與融券的倍數；倍數用同一市場信用交易卡的融券合計
-function sblLine(L) {
+function sblLine(L) {   // 第 30 輪 D30-03：回傳信用交易小表的一列
   const B = L.sbl, M = L.margin;
-  if (!B) return '';
+  if (!B) return null;
   const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
-  const one = (x, m, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>` +
-    (M?.[m]?.sb ? `（融券的 ${fmt(x.lb / M[m].sb, 0)} 倍）` : '') + (x.d !== (M?.[m]?.d ?? x.d) ? `<span class="muted">（${md(x.d)}）</span>` : '');
-  return `<div class="s num">借券賣出餘額　${[one(B.TWSE, 'TWSE', '上市'), one(B.TPEx, 'TPEx', '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/rank/l+">看排行 →</a></div>
-      <div class="s">借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新</div>`;
+  const one = (x, m) => !x ? '--' : `${wan(x.lb)}` + s2(`<span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>` +
+    (M?.[m]?.sb ? `<br>融券的 ${fmt(x.lb / M[m].sb, 0)} 倍` : '') + (x.d !== (M?.[m]?.d ?? x.d) ? `<span class="muted">（${md(x.d)}）</span>` : ''));
+  return ['借券賣出餘額' + s2('<a class="muted" href="#/rank/l+">看排行 →</a>'), one(B.TWSE, 'TWSE'), one(B.TPEx, 'TPEx')];
 }
 
 // 第 12 輪 ETF-借券：ETF 借券賣出合計（上市、上櫃 ETF，張）；多為造市、套利與避險
@@ -398,13 +408,15 @@
 function watchGrp(W, S) {
   if (!W) return '';
   const hit = W.filter(x => x[1]), near = W.filter(x => !x[1]);
-  const nm = c => esc(S[c]?.n || c);
+  const nm = c => esc(S[c]?.n || c), why = t => esc(t.replace('第一款', '第 1 款'));   // 第 30 輪 D30-07：款別寫法統一
+  const mk = c => S[c]?.m === 'TWSE' ? '上市' : '上櫃';
   return `<div class="al-grp"><h3>接近處置（推算）　<span class="muted small">已達條件 ${hit.length} 檔、差一次 ${near.length} 檔</span></h3>
-      ${hit.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${S[x[0]]?.m === 'TWSE' ? '上市' : '上櫃'}</span><span class="sp"></span><span class="small">已達條件</span></div>
-        <div class="muted small al-why">${esc(x[2])}</div></a>`).join('')}
-      ${near.length ? `<div class="al-near small"><span class="muted">差一次：</span>${near.map(x => `<a href="#/stock/${x[0]}">${nm(x[0])}<span class="muted">（${esc(x[2])}）</span></a>`).join('、')}</div>` : ''}
+      ${hit.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${mk(x[0])}</span><span class="sp"></span><span class="small">已達條件</span></div>
+        <div class="muted small al-why">${why(x[2])}</div></a>`).join('')}
+      ${near.length ? `<div class="al-near small muted">差一次：</div>${near.map(x => `<a class="al-row" href="#/stock/${x[0]}"><div class="al-l"><b>${nm(x[0])}</b><span class="muted small">${x[0]}・${mk(x[0])}</span><span class="sp"></span><span class="small">差 1 次</span></div>
+        <div class="muted small al-why">目前 ${why(x[2])}</div></a>`).join('')}` : ''}
       ${W.length ? '' : '<div class="muted small">無</div>'}
-      <div class="muted small">依注意款別推算（第一款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準</div></div>`;
+      <div class="muted small">依注意款別推算（第 1 款連 3 日，或第 1～8 款連 5 日、10 日內 6 次、30 日內 12 次）；是否處置以官方公告為準</div></div>`;
 }
 
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
@@ -412,11 +424,13 @@
   const B = L.breadth;
   if (!B) return '';
   const pct = v => v == null ? '--' : fmt(v, 1) + '%';
-  const row = (x, name) => !x ? '' : `<div class="s num">${name}　<span class="nw">站上 MA20 <b>${pct(x.ma20)}</b>（前日 ${pct(x.s20.at(-2))}）</span>　<span class="nw">MA60 <b>${pct(x.ma60)}</b></span>　<span class="nw">20 日新高 <span class="up">${fmt(x.hi)}</span>、新低 <span class="dn">${fmt(x.lo)}</span></span>　<span class="nw">量能 <b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b></span></div>`;
   const T = B.TWSE, s = T?.s20.filter(v => v != null) || [];
+  const c = f => [T, B.TPEx].map(x => !x ? '--' : f(x));
   return `<div class="card stat idx margin">
       <div class="l">市場寬度 ${md(T?.d || B.TPEx?.d)}（自算，股票，不含 ETF）</div>
-      ${row(T, '上市')}${row(B.TPEx, '上櫃')}
+      ${mxTbl(['上市', '上櫃'], [['站上 MA20', ...c(x => `<b>${pct(x.ma20)}</b>${s2(`前日 ${pct(x.s20.at(-2))}`)}`)], ['站上 MA60', ...c(x => `<b>${pct(x.ma60)}</b>`)],
+        ['20 日新高', ...c(x => `<span class="up">${fmt(x.hi)}</span>`)], ['20 日新低', ...c(x => `<span class="dn">${fmt(x.lo)}</span>`)],
+        ['量能', ...c(x => `<b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b>`)]])}
       ${spark(s)}${s.length ? `<div class="s">上市站上 MA20 比例，近 ${s.length} 個交易日（${md(T.from)} 起）</div>` : ''}
       <div class="s">分母 = 當天有收盤、且有 20（MA60 為 60）個以上收盤的股票（上市 ${fmt(T?.n20)}、上櫃 ${fmt(B.TPEx?.n20)} 檔）；新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 成交額 ÷ 前 20 日平均</div>
     </div>`;
@@ -427,12 +441,13 @@
   const V = L.valuation;
   if (!V || !(V.TWSE || V.TPEx)) return '';
   const pos = x => !x ? '--' : x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
-  const dyPos = x => pos(x) + (x && x.v > x.lo && x.v < x.hi ? '，越高 = 殖利率相對越高' : '');     // 第 14 輪 F14-4：方向和本益比、淨值比相反
-  const row = (x, name) => !x ? '' : `<div class="s num">${name}　本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）　殖利率 <b>${x.dy ? fmt(x.dy.v, 2) + '%' : '--'}</b>（${dyPos(x.dy)}）</div>`;
   const T = V.TWSE || V.TPEx;
+  const c = f => [V.TWSE, V.TPEx].map(x => !x ? '--' : f(x));
   return `<div class="card stat idx val">
       <div class="l">估值位置（官方，股票中位數）<span class="muted">　${md(T.d)}</span></div>
-      ${row(V.TWSE, '上市')}${row(V.TPEx, '上櫃')}
+      ${mxTbl(['上市', '上櫃'], [['本益比', ...c(x => `<b>${fmt(x.pe?.v, 2)}</b>${s2(pos(x.pe))}`)], ['淨值比', ...c(x => `<b>${fmt(x.pb?.v, 2)}</b>${s2(pos(x.pb))}`)],
+        ['殖利率' + s2('一年位置，越高 = 殖利率相對越高'), ...c(x => `<b>${x.dy ? fmt(x.dy.v, 2) + '%' : '--'}</b>${s2(pos(x.dy))}`)],   // 第 14 輪 F14-4：方向和本益比、淨值比相反
+        wpeRow(V)])}
       ${wpeLine(V)}
       ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
       ${finLine(L.fin_progress)}
@@ -444,12 +459,16 @@
 function wpeLine(V) {
   const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
   if (!T && !O) return '';
-  const pos = x => x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
-  const one = (x, name) => !x ? '' : `${name} <b>${fmt(x.v, 2)}</b>（${pos(x)}）`;
   const big = T?.t ? `最大的 ${esc(App.latest.stocks?.[T.t[0]]?.n || T.t[0])} 占上市 ${fmt(T.t[1], 1)}%` : '';
-  return `<div class="s num">加權本益比（市值加權）　${[one(T, '上市'), one(O, '上櫃')].filter(Boolean).join('　')}</div>
-      <div class="note-dup">${noteHTML(`大型股影響大${big ? `（${big}）` : ''}；本站計算，不是證交所公布的數字`, `加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}</div>`;
+  return `<div class="note-dup">${noteHTML(`大型股影響大${big ? `（${big}）` : ''}；本站計算，不是證交所公布的數字`, `加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}</div>`;
 }
+function wpeRow(V) {   // 第 30 輪 D30-03：加權本益比改成估值小表的一列
+  const T = V.TWSE?.wpe, O = V.TPEx?.wpe;
+  if (!T && !O) return null;
+  const pos = x => x.v <= x.lo ? '一年最低' : x.v >= x.hi ? '一年最高' : `一年位置 ${fmt(x.p, 1)}%`;
+  const one = x => !x ? '--' : `<b>${fmt(x.v, 2)}</b>${s2(pos(x))}`;
+  return ['加權本益比' + s2('市值加權'), one(T), one(O)];
+}
 
 // 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
 function finLine(P) {
@@ -474,8 +493,8 @@
   const parts = x => `外資 <span class="${cls(x.foreign)}">${yi1(x.foreign)}</span>　投信 <span class="${cls(x.trust)}">${yi1(x.trust)}</span>　自營 <span class="${cls(x.dealer)}">${yi1(x.dealer)}</span>`;
   const stk = s => s > 0 ? `連買 ${s} 日` : s < 0 ? `連賣 ${-s} 日` : '當日持平';
   if (!O) return `<div class="card stat insti"><div class="l">三大法人（${md(L.flow_date)}）</div>
-      <div class="v num ${cls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
-      <div class="s num">外資 <span class="${cls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${cls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${cls(I.dealer)}">${yi(I.dealer)}</span></div>
+      <div class="v num ${ycls(I.foreign + I.trust + I.dealer)}">${yi(I.foreign + I.trust + I.dealer)}</div>
+      <div class="s num">外資 <span class="${ycls(I.foreign)}">${yi(I.foreign)}</span>　投信 <span class="${ycls(I.trust)}">${yi(I.trust)}</span>　自營 <span class="${ycls(I.dealer)}">${yi(I.dealer)}</span></div>
       <div class="s">估算：買賣超張數 × 收盤價，不含 ETF</div></div>`;
   const stale = O.date < L.date, fs = O.fs;
   // 上市、上櫃各一張卡（左右並排；手機上下排），共同說明放在兩張卡下方
@@ -488,7 +507,7 @@
     </div>`
     : X ? `<div class="card stat idx insti">
       <div class="l">三大法人　上櫃，估算<span class="muted">　${md(L.flow_date)}</span></div>
-      <div class="s num">外資 <span class="${cls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${cls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${cls(X.dealer)}">${yi(X.dealer)}</span></div>
+      <div class="s num">外資 <span class="${ycls(X.foreign)}">${yi(X.foreign)}</span>　投信 <span class="${ycls(X.trust)}">${yi(X.trust)}</span>　自營 <span class="${ycls(X.dealer)}">${yi(X.dealer)}</span></div>
       <div class="s">上櫃官方金額尚無資料，暫以張數 × 收盤估算、不含 ETF，不可與上市官方值相加</div>
     </div>` : '';
   return `<div class="card stat idx insti">
@@ -694,12 +713,14 @@
 function bubbleList(groups) {
   const L = App.latest, k = L.dates.length - 1, open = App.blOpen;
   const QC = { 漲潮: 'var(--up)', 輪動: 'var(--amber)', 觀望: 'var(--blue)', 退潮: 'var(--dn)' };
-  return `<div class="muted small tbl-cap">資料日 ${md(L.dates[k])}。近5日 = 近 5 日法人累計（億）；日均差 = 近 5 日日均 − 20 日日均（億/天），正 = 偏流入；成交 = 成交額（億）。點一列看成分股</div>
+  const nHit = App.blHit ? groups.filter(g => g.frames[k] && g.quadrant === App.blHit).length : 0;
+  return `${nHit ? `<div class="small bl-hit">已標示「${App.blHit}」${nHit} 個</div>` : ''}<div class="muted small tbl-cap">資料日 ${md(L.dates[k])}。近5日 = 近 5 日法人累計（億）；日均差 = 近 5 日日均 − 20 日日均（億/天），正 = 偏流入；成交 = 成交額（億）。點一列看成分股</div>
     <div class="tbl-wrap"><table class="tbl bl-tbl"><thead><tr><th>${{ industry: '類股', chain: '產業鏈', concept: '概念股' }[App.group]}</th><th>近5日</th><th>日均差</th><th>漲跌</th><th>成交</th></tr></thead><tbody>` +
     groups.filter(g => g.frames[k]).sort((a, b) => b.frames[k][0] - a.frames[k][0]).map(g => { const [n5, dv, ch, tv] = g.frames[k];
-      return `<tr data-bl="${esc(g.name)}"${g.name === open ? ' class="on"' : ''}><td class="nm"><b>${esc(g.name)}</b><span><i style="color:${QC[g.quadrant]}">${g.quadrant}</i></span></td>
-        <td class="num ${cls(n5)}">${yi(n5)}</td><td class="num ${cls(dv)}">${sgn(dv, 1)}</td><td class="num ${cls(ch)}">${sgn(ch)}%</td><td class="num">${fmt(tv)}</td></tr>` +
-        (g.name === open ? `<tr class="bl-x"><td colspan="5"><div class="muted small">${groupMeta(g)}</div><div class="tbl-wrap panel-list"><table class="tbl">${groupRows(g)}</table></div></td></tr>` : ''); }).join('') +
+      return `<tr data-bl="${esc(g.name)}"${g.name === open || g.quadrant === App.blHit ? ` class="${[g.name === open && 'on', g.quadrant === App.blHit && 'q-hit'].filter(Boolean).join(' ')}"` : ''}><td class="nm"><b>${esc(g.name)}</b><span><i style="color:${QC[g.quadrant]}">${g.quadrant}</i></span></td>
+        <td class="num ${ycls(n5)}">${yi(n5)}</td><td class="num ${cls(dv)}">${sgn(dv, 1)}</td><td class="num ${cls(ch)}">${sgn(ch)}%</td><td class="num">${fmt(tv)}</td></tr>` +
+        (g.name === open ? `<tr class="bl-x"><td colspan="5"><div class="muted small">${groupMeta(g)}</div><div class="tbl-wrap panel-list"><table class="tbl">${groupRows(g)}</table></div>` +
+          (g.codes.filter(c => L.stocks[c]).length > 10 ? `<button class="chip" data-blall="${App.blAll ? 1 : 0}">${App.blAll ? '只顯示前 10 檔' : `顯示全部 ${g.codes.filter(c => L.stocks[c]).length} 檔`}</button>` : '') + '</td></tr>' : ''); }).join('') +
     '</tbody></table></div>';
 }
 
@@ -707,6 +728,7 @@
   const L = App.latest, groups = L.groups[App.group];
   const focus = localStore('focus', '');
   const mob = matchMedia('(max-width:720px)').matches, list = mob && App.bubbleView !== 'chart';
+  App.blHit = App.blQ; App.blQ = null;                                  // D30-06：從今日頁象限進來才標示，換頁回來不標示
   $('#view').innerHTML = `
     <section class="sec">
       <div class="sec-h"><h2>板塊資金${list ? '' : '泡泡圖'}</h2><span class="muted small">${list ? '近 5 日法人淨流入由大到小' : 'X：近 5 日法人淨流入　Y：近 5 日日均比 20 日日均偏流入或偏流出　大小：成交額　顏色：漲跌幅'}</span>
@@ -730,15 +752,17 @@
   if (mob) onSeg('bvSeg', v => { App.bubbleView = v; if (window.Plotly && $('#bubble')) Plotly.purge('bubble'); renderBubble(); });
   if (list) {
     $('#blBox').addEventListener('click', e => {
+      if (e.target.closest('[data-blall]')) { App.blAll = !App.blAll; $('#blBox').innerHTML = bubbleList(groups); return; }   // D30-08
       const tr = e.target.closest('tr[data-bl]');
       if (!tr) return;
       const name = tr.dataset.bl, y0 = tr.getBoundingClientRect().top;
-      App.blOpen = App.blOpen === name ? null : name;
+      App.blOpen = App.blOpen === name ? null : name; App.blAll = false;
       if (App.blOpen) localStore('focus', null, name);
       $('#blBox').innerHTML = bubbleList(groups);
       window.scrollBy(0, $(`#blBox tr[data-bl="${CSS.escape(name)}"]`).getBoundingClientRect().top - y0);   // 點的那一列留在原位（上方收合時不跳走）
     });
-    if (App.blJump) { App.blJump = 0; requestAnimationFrame(() => $('#blBox tr.on')?.scrollIntoView()); }   // 從今日頁點族群進來：捲到展開的那一列（route() 捲到頂端之後）
+    if (App.blJump) { App.blJump = 0; requestAnimationFrame(() => $('#blBox tr.on')?.scrollIntoView()); }
+    else if (App.blHit) requestAnimationFrame(() => $('#blBox tr.q-hit')?.scrollIntoView());   // 從今日頁點族群進來：捲到展開的那一列（route() 捲到頂端之後）
     return;
   }
   drawBubble(groups, L.dates);
@@ -862,14 +886,14 @@
   });
 }
 
-const groupMeta = g => `<span class="pill">${g.quadrant}</span>　5日 <span class="${cls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
+const groupMeta = g => `<span class="pill">${g.quadrant}</span>　5日 <span class="${ycls(g.net_5d)}">${yi(g.net_5d)}</span>　連${g.streak >= 0 ? '買' : '賣'} ${Math.abs(g.streak)} 天　法人 ${md(App.latest.flow_date)}`;
 function groupRows(g) {   // D28-04：泡泡明細卡與手機清單展開共用
   const S = App.latest.stocks;
   const rows = g.codes.filter(c => S[c]).sort((a, b) => (S[b].n5 ?? 0) - (S[a].n5 ?? 0));
   return `<thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>法人1日</th><th>法人5日</th></tr></thead><tbody>` +
     rows.map(c => { const s = S[c]; return `<tr data-code="${c}"><td class="nm"><b>${esc(s.n)}</b><span>${c}</span></td>
       <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
-      <td class="num ${cls(s.n1)}">${yi(s.n1)}</td><td class="num ${cls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
+      <td class="num ${ycls(s.n1)}">${yi(s.n1)}</td><td class="num ${ycls(s.n5)}">${yi(s.n5)}</td></tr>`; }).join('') + '</tbody>';
 }
 function showGroup(g) {
   if (!g) return;
@@ -907,7 +931,7 @@
 
 function stockTable(list, span = '1', rm = false) {   // rm：自選頁（名稱欄加移除、排序鈕，編輯模式才顯示）
   const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
-  const amt = v => `<td class="num ${cls(v)}">${yi(v)}</td>`;
+  const amt = v => `<td class="num ${ycls(v)}">${yi(v)}</td>`;
   const fd = md(App.latest.flow_date);
   return `${flowNote()}<div class="muted small tbl-cap">${k === '5' ? `法人欄位為截至 ${fd} 的近 5 日累計（億）` : `法人欄位為 ${fd} 當日買賣超（億）`}</div>
     <div class="tbl-wrap"><table class="tbl"><thead><tr>
@@ -970,9 +994,9 @@
         ${by === 'm+' || by === 'm-' ? segHTML('munitSeg', [['amt', '估算金額'], ['lot', '張數']], unit) : ''}
         <select id="tvSel" class="sel" aria-label="成交額門檻">${[['0', '成交額不限'], ['0.5', '成交額 ≥ 0.5 億'], ['1', '成交額 ≥ 1 億'], ['5', '成交額 ≥ 5 億']]
           .map(([v, t]) => `<option value="${v}"${v === minTv ? ' selected' : ''}>${t}</option>`).join('')}</select>
-        <select id="rankSel" class="sel">${RANK_GROUPS.map(([g, ids]) => { const rs = ids.map(id => avail.find(r => r[0] === id)).filter(Boolean);
-          return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select></div>
-      <div class="rk-q">${['n+', 'f+', 't+', 'p+', 'p-', 'tv', 'm+'].filter(id => avail.some(r => r[0] === id)).map(id => `<button class="chip${id === by ? ' on' : ''}" data-rk="${id}">${RANKS.find(r => r[0] === id)[1]}</button>`).join('')}</div>
+</div>
+      <div class="rk-q"><select id="rankSel" class="sel">${RANK_GROUPS.map(([g, ids]) => { const rs = ids.map(id => avail.find(r => r[0] === id)).filter(Boolean);
+          return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select>${['n+', 'f+', 't+', 'p+', 'p-', 'tv', 'm+'].filter(id => avail.some(r => r[0] === id)).map(id => `<button class="chip${id === by ? ' on' : ''}" data-rk="${id}">${RANKS.find(r => r[0] === id)[1]}</button>`).join('')}</div>
       <div class="card">${table}</div>
       <div class="muted small" style="margin-top:6px">${foot}</div></section>`;
   keyCol(rankKeyCol(by, field, src, byAmt));
@@ -1367,6 +1391,7 @@
 // ETF 列（tr[data-etf]）→ ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁。第 20 輪：ETF 列表與自選頁共用
 const onEtfRow = e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a,button')) location.hash = '#/stock/' + tr.dataset.etf; };
 
+const ETF_N = 50;   // 第 30 輪 D30-04：ETF 列表預設顯示的檔數（和排行一樣）
 function renderEtf() {
   const E = App.latest.etfs;
   if (!E) {
@@ -1395,13 +1420,17 @@
         <td class="num">${r.sb == null ? '--' : fmt(r.sb)}</td>${lots(r.s1)}
         <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}</tr>`).join('') +
       `</tbody></table></div></div>
+      ${list.length > ETF_N ? `<button class="chip" id="etfMore" style="margin-top:8px">${App.etfAll ? `只顯示前 ${ETF_N} 檔` : `顯示全部 ${list.length} 檔`}</button>` : ''}
       <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行與股票口徑的融資融券。</div></section>`;
   keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
   const etfQ = () => { const q = (App.etfQ = $('#etfQ').value.trim()).toLowerCase();   // 第 25 輪 D25-15：只隱藏列，不重畫
-    $('#view').querySelectorAll('tr[data-etf]').forEach(tr => { tr.hidden = !!q && !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q); }); };
+    // 第 30 輪 D30-04：沒有篩選字時只顯示前 ETF_N 檔（「顯示全部」後全列）；有篩選字時在全部 ETF 中找
+    $('#view').querySelectorAll('tr[data-etf]').forEach((tr, i) => { tr.hidden = q ? !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q) : !App.etfAll && i >= ETF_N; });
+    if ($('#etfMore')) $('#etfMore').hidden = !!q; };
   $('#etfQ').addEventListener('input', etfQ); etfQ();
+  $('#etfMore')?.addEventListener('click', () => { App.etfAll = !App.etfAll; $('#etfMore').textContent = App.etfAll ? `只顯示前 ${ETF_N} 檔` : `顯示全部 ${list.length} 檔`; etfQ(); });
   // 第 15 輪 F15-2：整列 → ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁
   $('#view').addEventListener('click', onEtfRow);
 }
diff -ruN -x data -x __pycache__ orig/site/index.html proj/site/index.html
--- orig/site/index.html	2026-11-17 00:11:20
+++ proj/site/index.html	2026-11-17 00:52:19
@@ -7,11 +7,11 @@
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
 <script>try{var t=localStorage.getItem('tw.theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>
-<link rel="stylesheet" href="app.css?v=d654f1a6">
+<link rel="stylesheet" href="app.css?v=a69df04b">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js?v=656083f0" defer></script>
-<script src="stock.js?v=01859664" defer></script>
+<script src="app.js?v=895b2037" defer></script>
+<script src="stock.js?v=41db19b1" defer></script>
 </head>
 <body>
 <header class="top">
diff -ruN -x data -x __pycache__ orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-17 00:11:20
+++ proj/site/stock.js	2026-11-17 00:49:48
@@ -82,7 +82,7 @@
 const mgView = G => { const v = localStore('mgv', 'mb'); return v === 'sb' || (v === 'lb' && G?.lb) ? v : 'mb'; };
 const tagFold = t => t.slice(0, 2).join('') + (t.length > 2 ? `<span class="tag-rest" hidden>${t.slice(2).join('')}</span><button class="pill more" id="tagMore" data-n="+${t.length - 2}">+${t.length - 2}</button>` : '');
 
-const cardsHTML = a => a.map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('');
+const cardsHTML = a => a.map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${v === '0億' ? 'flat' : c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('');
 // 第 28 輪 D28-01：籌碼分頁的圖表區間（只在這次瀏覽記住，不存 localStorage）；第 29 輪 F29-3：預設改 20 個交易日
 const CHIP_N = [['20', '20 日'], ['60', '60 日'], ['120', '120 日'], ['all', '全部']];
 let chipN = '20';
@@ -199,7 +199,7 @@
             <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
             ${E && E.m === 'TPEx' ? '<span class="muted small">上櫃 ETF 的漲跌可能含除息，本站無法辨識除息日</span>' : ''}
           </div>
-          ${HL.length ? `<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>` : ''}
+          ${HL.length ? `<div class="s-hl"><a class="muted small" href="#/rank/hl">近期新訊號 →</a>${HL.map(hlTag).join('')}<span class="muted small">只描述發生了什麼，不代表之後的走勢</span>${HL.length > 1 ? `<button class="pill more hl-more" id="hlMore">+${HL.length - 1}</button>` : ''}</div>` : ''}
           <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
         </div>
         <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
@@ -207,7 +207,7 @@
     </section>
 
     ${pageTabsHTML('stockTabSeg', E ? ETF_TABS : STOCK_TABS, tab)}
-    ${tab === 'chip' ? '' : `<section class="sec metrics${tab === 'k' ? ' kv' : ''}">
+    ${tab === 'chip' ? '' : `<section class="sec metrics${tab === 'k' ? ' kv' : ' m3'}">
       ${cardsHTML(tab === 'k' ? [
          [hlFrom ? '區間高' : '52週高', pfmt(E ? eHL[0] : s?.h52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
@@ -252,7 +252,13 @@
     ${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}
     ${E ? '' : '<section class="sec card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></section>'}`}`;
 
-  onSeg('stockTabSeg', v => { localStore('stockTab', null, v); history.replaceState(null, '', `#/stock/${code}/${v}`); window.disposeStockCharts(); window.renderStock(code); });
+  const ptab = $('#view .page-tabs'), topH = () => $('.top').offsetHeight;   // 第 30 輪 D30-01
+  ptab.classList.add('pt-stick');
+  ptab.insertAdjacentHTML('beforeend', `<span class="pt-nm">${esc(data.name)} <b class="num ${cls(change)}">${pfmt(close)}</b>${noTrade || pct == null ? '' : ` <span class="num ${cls(change)}">${sgn(pct)}%</span>`}</span>`);
+  new IntersectionObserver(([e]) => ptab.classList.toggle('stuck', !e.isIntersecting), { rootMargin: `-${topH()}px 0px 0px 0px` }).observe($('#view .s-head'));
+  if (App.ptStuck) { App.ptStuck = false; ptab.style.position = 'static'; const y = ptab.getBoundingClientRect().top + scrollY; ptab.style.position = ''; scrollTo(0, y - topH()); }   // 固定狀態換分頁：新分頁從分頁列下方開始
+  onSeg('stockTabSeg', v => { App.ptStuck = $('#view .s-head').getBoundingClientRect().bottom <= topH(); localStore('stockTab', null, v); history.replaceState(null, '', `#/stock/${code}/${v}`); window.disposeStockCharts(); window.renderStock(code); });
+  $('#hlMore')?.addEventListener('click', e => e.currentTarget.parentElement.classList.add('open'));
   $('#tagMore')?.addEventListener('click', e => { const r = $('#view .tag-rest'), b = e.currentTarget; r.hidden = !r.hidden; b.textContent = r.hidden ? b.dataset.n : '收合'; });
   $('#starBtn')?.addEventListener('click', () => {
     App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
diff -ruN -x __pycache__ orig/tests/test_iter14.py proj/tests/test_iter14.py
--- orig/tests/test_iter14.py	2026-11-08 01:19:54
+++ proj/tests/test_iter14.py	2026-11-17 00:48:20
@@ -91,7 +91,7 @@
     assert "期貨 13:45、加權指數 13:30 收盤，時間不同" in APP and "kSer.setMarkers(" in APP and "換${Number(F.m[i].slice(4))}月" in APP
     # F14-4
     assert "，越高 = 殖利率相對越高" in APP and "<br>越高 = 殖利率相對越高" in STK
-    assert "本益比 <b>${fmt(x.pe?.v, 2)}</b>（${pos(x.pe)}）　淨值比 <b>${fmt(x.pb?.v, 2)}</b>（${pos(x.pb)}）" in APP   # 本益比、淨值比不變
+    assert "['本益比', ...c(x => `<b>${fmt(x.pe?.v, 2)}</b>${s2(pos(x.pe))}`)], ['淨值比', ...c(x => `<b>${fmt(x.pb?.v, 2)}</b>${s2(pos(x.pb))}`)]" in APP   # 本益比、淨值比不變（第 30 輪 D30-03 改成小表）
     assert ".note-dup .note[open] summary{font-size:0}" in CSS and ".note-dup .note[open] summary i{font-size:12px" in CSS
     assert "dueTxt(P.due, App.latest.date)" in APP
 
diff -ruN -x __pycache__ orig/tests/test_iter27.py proj/tests/test_iter27.py
--- orig/tests/test_iter27.py	2026-11-15 20:35:07
+++ proj/tests/test_iter27.py	2026-11-17 00:48:20
@@ -150,7 +150,7 @@
     o = _node(js)
     if o is not None:
         assert "即將處置 0　處置中 1　接近處置（推算）2　今日注意 1</span>" in o, o
-        assert '<a href="#/stock/2314">台揚<span class="muted">（第一款連 2 日）</span></a>' in o   # 差一次的理由直接顯示
+        assert '<a class="al-row" href="#/stock/2314"><div class="al-l"><b>台揚</b>' in o and '目前 第 1 款連 2 日</div>' in o   # 差一次的理由直接顯示（第 30 輪 D30-07：一檔一列）
         assert 'title="第一款連 2 日"' not in o
 
 
diff -ruN -x __pycache__ orig/tests/test_iter30.py proj/tests/test_iter30.py
--- orig/tests/test_iter30.py	1970-01-01 08:00:00
+++ proj/tests/test_iter30.py	2026-11-17 00:54:21
@@ -0,0 +1,162 @@
+"""
+第 30 輪 UI/UX 全站體檢（不連網、不連資料庫；只改 site/）：
+D30-01 個股頁分頁列貼在頂欄下（帶名稱與價格），固定狀態換分頁時新分頁從分頁列下方開始；
+D30-02 手機搜尋清單全寬、名稱單行；D30-03／05 今日頁信用、估值、市場寬度改「指標 × 市場」小表；
+D30-04 ETF 列表預設 50 檔；D30-06 資金象限每格各自連結並在泡泡清單標示；D30-07 差一次一檔一列；
+D30-08 手機泡泡清單展開成分股不限高（前 10 檔＋顯示全部）；D30-09 頁首新訊號手機只顯示 1 個；
+D30-10 顯示「0億」時不上漲跌色；D30-11 排行種類選單併入快捷列；D30-12 基本面估值卡一列 3 張、股利表內距。
+有 node 時逐字取出 app.js 的函式執行（node 14 可跑）。
+
+  python3 tests/test_iter30.py      （也相容 pytest）
+"""
+import json
+import sys
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+
+import test_iter28 as t28  # noqa: E402
+
+APP, STK, CSS = t28.APP, t28.STK, t28.CSS
+G = lambda *names: "\n".join(t28._grab(APP, n) for n in names)
+AT = ("if (!Array.prototype.at) Array.prototype.at = function (i) { return this[i < 0 ? this.length + i : i]; };\n"   # node 14 沒有 .at()、replaceAll
+      "if (!String.prototype.replaceAll) String.prototype.replaceAll = function (a, b) { return this.split(a).join(b); };\n")
+
+
+# ─── D30-01、09、12：個股頁 ─────────────────────────────────
+def test_stock_page_source():
+    assert "ptab.classList.add('pt-stick');" in STK and "<span class=\"pt-nm\">${esc(data.name)}" in STK
+    assert "observe($('#view .s-head'))" in STK                                                     # 頁首捲出畫面才顯示名稱與價格
+    assert "App.ptStuck = $('#view .s-head').getBoundingClientRect().bottom <= topH();" in STK     # 換分頁前在固定狀態
+    assert "if (App.ptStuck) { App.ptStuck = false; ptab.style.position = 'static';" in STK         # 新分頁從分頁列下方開始
+    assert ".page-tabs.pt-stick{position:sticky;top:var(--top-h,56px);z-index:15;" in CSS and ".pt-stick.stuck .pt-nm{display:block}" in CSS
+    assert "$('#view .pt-stick')?.getBoundingClientRect().bottom ?? 0" in APP                        # 長表格的表頭貼在分頁列下
+    # D30-09：新訊號超過 1 個時有「+N」，手機收合時只顯示第 1 個、免責句一起收
+    assert "${HL.length > 1 ? `<button class=\"pill more hl-more\" id=\"hlMore\">+${HL.length - 1}</button>` : ''}" in STK
+    assert "$('#hlMore')?.addEventListener('click', e => e.currentTarget.parentElement.classList.add('open'));" in STK
+    assert ".s-hl:not(.open) .hl-tag~.hl-tag,.s-hl:has(.hl-more):not(.open)>span.muted{display:none}" in CSS
+    # D30-12
+    assert "<section class=\"sec metrics${tab === 'k' ? ' kv' : ' m3'}\">" in STK
+    assert ".metrics.m3{grid-template-columns:repeat(3,minmax(0,1fr))}" in CSS and "table.dv-tbl th,table.dv-tbl td{padding-left:4px;padding-right:4px}" in CSS
+
+
+def test_zero_color():
+    # D30-10：yi 顯示 0億 時顏色為灰色；個股卡片也依顯示值
+    assert ", ycls = n => cls(n != null && Math.abs(n) < 0.05 ? 0 : n);" in APP
+    assert "${v === '0億' ? 'flat' : c || ''}" in STK
+    assert "${cls(n5)}\">${yi(n5)}" not in APP and APP.count("ycls(") == 14
+    o = t28._node(t28.HELPERS + "\nconsole.log(JSON.stringify([0.04, -0.04, 0.05, -0.2, null, 0].map(v => [yi(v), ycls(v)])));")
+    if o is not None:
+        assert o == [["0億", "flat"], ["0億", "flat"], ["+0.1億", "up"], ["-0.2億", "dn"], ["--", "flat"], ["0億", "flat"]], o
+
+
+# ─── D30-02：搜尋清單 ─────────────────────────────────────
+def test_search_list():
+    assert '<span class="code">${c}</span><span class="qn">${esc(s.n)}</span>' in APP
+    assert ".qn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" in CSS
+    assert "@media (max-width:720px){.search{position:static}.qlist{left:8px;right:8px;top:calc(100% + 4px)}}" in CSS
+
+
+# ─── D30-03、05：今日頁小表 ───────────────────────────────
+L = {"date": "2026-11-16", "stocks": {"2330": {"n": "台積電"}},
+     "margin": {"TWSE": {"d": "2026-11-16", "mb": 5926000, "m1": -75214, "mp": -1.25, "sb": 126000, "s1": 5524, "sr": 2.13, "mr": 158.6, "mr0": 171.0,
+                         "amt": 5245.0, "amt1": -121.0, "sp": 4.0, "m20": [1, -2], "d20": ["2026-11-13", "2026-11-16"]},
+                "TPEx": {"d": "2026-11-13", "mb": 2011000, "m1": -32735, "mp": -1.6, "sb": 39000, "s1": 2158, "sr": 1.94, "mr": None, "mr0": None,
+                         "amt": 1677.3, "amt1": -42.9}},
+     "sbl": {"TWSE": {"d": "2026-11-16", "lb": 13310000, "l1": 21387}},
+     "breadth": {"TWSE": {"d": "2026-11-16", "ma20": 13.3, "ma60": 13.8, "hi": 25, "lo": 375, "vr": 0.87, "s20": [20.3, 13.3], "from": "2026-11-13", "n20": 1085},
+                 "TPEx": {"d": "2026-11-16", "ma20": 17.4, "ma60": 17.3, "hi": 30, "lo": 289, "vr": 0.84, "s20": [26.0, 17.4], "n20": 873}},
+     "valuation": {"TWSE": {"d": "2026-11-16", "days": 242, "from": "2025-11-14", "n": 900, "pe": {"v": 15.59, "p": 0.8, "lo": 15, "hi": 20},
+                            "pb": {"v": 1.46, "p": 0, "lo": 1.46, "hi": 2}, "dy": {"v": 2.8, "p": 60.3, "lo": 2, "hi": 3},
+                            "wpe": {"v": 19.48, "p": 1.2, "lo": 19, "hi": 25, "t": ["2330", 43.3]}},
+                   "TPEx": {"d": "2026-11-16", "n": 700, "pe": {"v": 16.81, "p": 0, "lo": 16.81, "hi": 20}, "pb": {"v": 1.77, "p": 0.8, "lo": 1.5, "hi": 2},
+                            "dy": {"v": 1.96, "p": 64.5, "lo": 1, "hi": 3}}}}
+
+
+def test_today_tables_node():
+    assert "const mxTbl = (cols, rows) => `<table class=\"mx num\">" in APP and "table.mx{width:100%;" in CSS
+    js = AT + t28.HELPERS + "\n" + G("noteHTML", "mxTbl", "s2", "spark", "minibars", "sblLine", "etfSblLine", "marginCard", "breadthCard",
+                                 "valCard", "wpeLine", "wpeRow", "finLine") + f"""
+const App = {{ latest: {json.dumps(L, ensure_ascii=False)} }};
+console.log(JSON.stringify({{ m: marginCard(App.latest), b: breadthCard(App.latest), v: valCard(App.latest) }}));"""
+    o = t28._node(js)
+    if o is None:
+        return
+    m, b, v = o["m"], o["b"], o["v"]
+    assert '<thead><tr><th></th><th>上市</th><th>上櫃<span class="muted">（11/13）</span></th></tr></thead>' in m      # 上櫃資料日較舊時寫在欄名
+    assert '<tr><th>融資</th><td><b title="5,926,000 張">592.6</b> 萬張<div class="s2"><span class="dn">-75,214</span>（-1.25%）</div></td>' in m
+    assert '<tr><th>融資維持率<div class="s2">自算</div></th><td><b>158.6%</b><div class="s2">前日 171.0%</div></td><td>資料不足</td></tr>' in m
+    assert '<tr><th>借券賣出餘額<div class="s2"><a class="muted" href="#/rank/l+">看排行 →</a></div></th>' in m and '<br>融券的 106 倍' in m
+    assert m.index('<table class="mx num">') < m.index('借券賣出含避險、套利，不等於看空')
+    assert '<tr><th>站上 MA20</th><td><b>13.3%</b><div class="s2">前日 20.3%</div></td><td><b>17.4%</b><div class="s2">前日 26.0%</div></td></tr>' in b
+    assert '<tr><th>20 日新低</th><td><span class="dn">375</span></td><td><span class="dn">289</span></td></tr>' in b
+    assert '<tr><th>本益比</th><td><b>15.59</b><div class="s2">一年位置 0.8%</div></td><td><b>16.81</b><div class="s2">一年最低</div></td></tr>' in v
+    assert '<th>殖利率<div class="s2">一年位置，越高 = 殖利率相對越高</div></th>' in v
+    assert '<tr><th>加權本益比<div class="s2">市值加權</div></th><td><b>19.48</b><div class="s2">一年位置 1.2%</div></td><td>--</td></tr>' in v
+    assert "不是證交所公布的數字" in v and v.index("加權本益比") < v.index("不是證交所公布的數字")
+
+
+# ─── D30-06、07、08：象限連結、差一次、泡泡展開 ────────────────
+def test_quads_and_near_node():
+    assert '<a class="quad q-${q}" href="#/bubble" data-q="${q}">' in APP and '<a class="quads"' not in APP
+    assert "App.blQ = e.target.closest('[data-q]')?.dataset.q;" in APP and "App.blHit = App.blQ; App.blQ = null;" in APP
+    assert "else if (App.blHit) requestAnimationFrame(() => $('#blBox tr.q-hit')?.scrollIntoView());" in APP
+    W = {"date": "2026-11-16", "stocks": {"2314": {"n": "台揚", "m": "TWSE"}, "3374": {"n": "精材", "m": "TPEx"}, "2466": {"n": "冠西電", "m": "TWSE"}},
+         "alerts": {"d": [], "n": [], "w": [["2466", 1, "第一款連 3 日、30 日內 12 次"], ["2314", 0, "第一款連 2 日"], ["3374", 0, "第 1～8 款連 4 日"]]}}
+    js = "\n".join(t28._grab(APP, n) for n in ("esc", "md", "watchGrp", "alertBoard")) + f"""
+const App = {{ alertAll: false, alOpen: true }};
+console.log(JSON.stringify(alertBoard({json.dumps(W, ensure_ascii=False)})));"""
+    o = t28._node(js)
+    if o is not None:
+        assert '<div class="al-near small muted">差一次：</div>' in o
+        assert ('<a class="al-row" href="#/stock/3374"><div class="al-l"><b>精材</b><span class="muted small">3374・上櫃</span><span class="sp"></span><span class="small">差 1 次</span></div>\n'
+                '        <div class="muted small al-why">目前 第 1～8 款連 4 日</div></a>') in o
+        assert "目前 第 1 款連 2 日" in o and "第 1 款連 3 日、30 日內 12 次" in o and "第一款" not in o
+        assert "依注意款別推算（第 1 款連 3 日" in o
+
+
+def test_bubble_list_node():
+    S = {str(1100 + i): {"n": f"股{i}", "c": 10, "p": 1, "n1": 0.01 * i, "n5": i} for i in range(12)}
+    js = AT + t28.HELPERS + "\n" + G("pctCell", "groupMeta", "groupRows", "bubbleList") + f"""
+const App = {{ group: 'industry', blOpen: 'A', blHit: '觀望', latest: {{ dates: ['2026-11-13', '2026-11-16'], flow_date: '2026-11-16', stocks: {json.dumps(S)} }} }};
+const G = [{{ name: 'A', quadrant: '漲潮', frames: [null, [5, 1, 1.5, 100]], codes: {json.dumps(list(S))}, net_5d: 5, streak: 2 }},
+  {{ name: 'B', quadrant: '觀望', frames: [null, [-3, 1, -0.5, 20]], codes: [], net_5d: -3, streak: -1 }}];
+const h1 = bubbleList(G); App.blAll = true; const h2 = bubbleList(G);
+console.log(JSON.stringify({{ h1, h2 }}));"""
+    o = t28._node(js)
+    if o is None:
+        return
+    h1, h2 = o["h1"], o["h2"]
+    assert '<div class="small bl-hit">已標示「觀望」1 個</div>' in h1 and '<tr data-bl="B" class="q-hit">' in h1 and '<tr data-bl="A" class="on">' in h1
+    assert '<div class="tbl-wrap panel-list"><table class="tbl"><thead>' in h1                       # 第 28 輪結構不變
+    assert '<button class="chip" data-blall="0">顯示全部 12 檔</button>' in h1 and '<button class="chip" data-blall="1">只顯示前 10 檔</button>' in h2
+    assert ".bl-x .panel-list{max-height:none}.bl-x:not(:has([data-blall=\"1\"])) .panel-list tbody tr:nth-child(n+11){display:none}" in CSS
+    assert "<td class=\"num flat\">0億</td>" in h1                                                    # D30-10：股0 法人1日 0
+    assert "App.blOpen = App.blOpen === name ? null : name; App.blAll = false;" in APP
+
+
+# ─── D30-04、11：ETF、排行 ────────────────────────────────
+def test_etf_and_rank_source():
+    assert "const ETF_N = 50;" in APP
+    assert "tr.hidden = q ? !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q) : !App.etfAll && i >= ETF_N;" in APP
+    assert "`顯示全部 ${list.length} 檔`" in APP and "`只顯示前 ${ETF_N} 檔`" in APP and "$('#etfMore').hidden = !!q;" in APP
+    assert ".etf-tbl td.nm b{display:-webkit-box;-webkit-line-clamp:2;" in CSS
+    assert '<div class="rk-q"><select id="rankSel" class="sel">' in APP and APP.count('id="rankSel"') == 1
+    assert ".rk-q{flex-wrap:nowrap;overflow-x:auto;" in CSS
+
+
+def test_no_advice_words():
+    seg = "\n".join(l for l in (APP + STK + CSS).splitlines() if "第 30 輪" in l or "D30-" in l)
+    seg += G("mxTbl", "marginCard", "breadthCard", "valCard", "wpeRow", "watchGrp", "bubbleList")
+    for w in ("買進", "賣出", "反彈", "見底", "買點", "超賣", "超買", "推薦", "強勢股", "飆股", "勝率", "亮點", "低估", "高估", "建議"):
+        assert w not in seg.replace("借券賣出", ""), w
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_"):
+            print("==", name)
+            fn()
+            print("✅", name)
+    print("全部通過")
```
