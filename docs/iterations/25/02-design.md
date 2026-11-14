# 第 25 輪｜UI/UX 設計師：版面與風格調整（投資工具化）

- 撰寫日期：2026-11-14（週六）
- 依據：
  - `25/01-analyst.md`：U25-01～35、前 10 名、第四節「不建議改動」、第五節限制。
  - `README.md`（`docs/iterations/`）的規範。
  - `24/03-design.md` 附錄 A：第 24 輪待套用的 diff（`stock.js`、`app.css`、`index.html`）。
- 原型作業：
  - scratchpad `ux25/` 建兩份副本：`orig`（目前工作目錄）、`proj`（本設計）。兩份都**不含 `.env`**、`.git`、`logs`；`site/data` 用符號連結指向專案的 `site/data`（唯讀，未寫入）。
  - `proj` 的 diff 就是本文件附錄 A，**PG 可以直接套用**（見第六節）。
  - 8001 預覽：
    - 先後由 `proj`、`orig` 執行 `serve --port 8001 --no-browser`。每次開頁前用 `fetch(…, {cache:'reload'})` 強制重新驗證，確認載入的 `?v=` 和該副本的 `index.html` 相同才量測。
    - 用完已 `pkill -f "twstock serve --port 8001"`，確認埠已釋放；8000（PID 42150）沒有碰。
    - localStorage、sessionStorage 已清除（0 個鍵），視窗恢復 desktop，分頁已關閉。
  - **外部請求 0 次**（瀏覽器載入 `index.html` 原有的 jsDelivr 圖表函式庫除外）、**DB 寫入 0 次**；沒有執行 `collect`、`history`、`export`。
  - 沒有修改專案程式、沒有 commit。本文件是唯一寫進專案的檔案。
- 編號：本輪設計項目用 **D25-01～D25-16**。
- 用詞照舊不用「買進、賣出、反彈、見底、買點、超賣、超買、推薦、強勢股、飆股、勝率、利多、利空、看多、看空、轉強、轉弱」，也不用第 23 輪加列的「跑贏、領先、落後…」等詞。

---

## 〇、結論摘要

| 項目 | 結果 |
|---|---|
| 本輪範圍 | D25-01～16，涵蓋前 10 名全部（U25-04、01、18、26、09、33、24、02、06、10），加上 U25-03、20、27、28、08（部分）、25（部分）、19（部分）、17、12、32（部分）、23 |
| 變更量 | `app.css` ＋45／−12、`app.js` ＋59／−26、`stock.js` ＋21／−12、`index.html` ＋3／−3：**程式＋CSS 共 175 行**（目標 300，上限 400） |
| 舊測試 | **0 行需要修改**。`test_iter01`～`23` 在 `proj` 全部通過 |
| 和第 24 輪 | 先套 24 再套 25、先套 25 再套 24，`app.css`、`app.js`、`stock.js` 都能 `patch` 乾淨套用；**只有 `index.html` 的 `?v=` 一定衝突**（重算即可）。兩輪合併後 `test_iter01`～`24` 全部通過 |
| 資料口徑 | 數字、四捨五入、單位、排序定義都不變；新增的摘要列與關鍵數字列只搬移既有欄位，口徑寫在標籤 |

實測（`orig` → `proj`，K 線主圖 `#kC` 頂端 y，px）：

| 頁面 | 1024×800 | 375×812 |
|---|---|---|
| 2330 | 529 → **495** | 858 → **561** |
| 8299 | 606 → **495** | 985 → **586** |
| 2421 | 577 → **468** | 850 → **478** |
| 0050（ETF） | 520 → **471** | 697 → **504** |
| 今日「總覽」頁高 | 1,827 → **977** | 2,268 → **1,545** |

- 375 寬：主圖 320px，第一屏可視到 y=758（底部選單 54px）。2330 露出 197px（62%），8299 露出 172px（54%），都達到分析師「至少露出一半」。
- 1024 寬：分析師希望 K 線頂端 ≤ 約 300px。實測要做到 300，必須拿掉頁首的標籤、新訊號或開高低其中之一（都含防誤讀或口徑），所以本輪不追 300，改成「主圖頂端 ≤ 500，而且頁首多了 7 個關鍵數字」。理由見 D25-05。

---

## 一、設計原則與風格方向

### 1-1 「投資工具感」的具體化

只用通行慣例，不參考或複製特定網站的版型、配色或品牌。延續本站既有元素：圓角卡片、膠囊分段鈕、品牌三圓圖示、紅漲綠跌。

| 原則 | 本輪做法 |
|---|---|
| 資訊密度 | 重點數字集中成「列」：今日頁的大盤摘要列（D25-03）、個股頁的關鍵數字列（D25-05）。用 1px 格線分隔小格，不再一個數字一張卡 |
| 數字等寬 | `.tbl`、`.kleg`（十字線讀值）、`.stat`、`.sum` 全部 `font-variant-numeric: tabular-nums`，捲動或移動十字線時數字不跳動 |
| 千分位 | 沿用 `fmt()`／`pfmt()`，不改格式函式 |
| 紅漲綠跌一致 | 所有 `.stat .s` 的漲跌色修好（D25-02）；MACD 柱改紅綠（D25-16） |
| 層級 | 指數 26px > 統計卡 20px > 關鍵數字 16px > 摘要列 17px（數字）／12px（標籤）。分段鈕選取改反白（D25-10） |
| 色彩語意 | `--up` 漲／買超／增加；`--dn` 跌／賣超／減少；`--flat` 平盤、無成交；`--amber` 注意、輪動；`--blue` 連結、說明、事件標記；`--violet` 股本變動。語意不變，只調亮度 |
| 深淺色 | 兩種模式都量對比。新增 `--on-fill`（色塊上的字色）：淺色白字、深色近黑字，讓「處」「注」等小色塊兩種模式都 ≥ 4.5:1 |
| 觸控 | 手機上分段鈕、chip、下拉 ≥ 34px，個股分頁 ≥ 38px，勾選框 18px（D25-12） |

### 1-2 色彩 token（D25-01）

測試鎖定的 `--bg`、`--card`、`--card2`、`--text`、`--text2` **不動**（`test_iter15` 第 104、105 行的字面照舊成立）。

淺色模式（`:root`）：

| token | 原值 | 新值 | 白 `#fff` | `--card2` | `--bg` | 用途 |
|---|---|---|---|---|---|---|
| `--text3` | `#999` | `#6d6d6d` | 2.85 → **5.17** | **4.83** | **4.62** | 頁尾、載入、底部選單未選 |
| `--up` | `#d64545` | `#cc3333` | 4.38 → **5.14** | **4.79** | **4.58** | 漲、買超 |
| `--dn` | `#30a46c` | `#247b51` | 3.16 → **5.21** | **4.86** | **4.66** | 跌、賣超 |
| `--flat` | `#8a8a8a` | `#6d6d6d` | 3.45 → **5.17** | **4.83** | **4.62** | 平盤、無成交 |
| `--amber` | `#e8a33d` | `#976112` | 2.16 → **5.21** | **4.86** | **4.65** | 注意、輪動 |
| `--blue` | `#3b82d6` | `#286dbf` | 3.93 → **5.21** | **4.86** | **4.65** | 連結、說明 |
| `--violet` | `#7f77dd` | `#6b62d6` | 3.76 → **4.84** | 4.51 | 4.32 | 只當色塊底（「股本變動」白字 4.84） |
| `--on-fill`（新） | — | `#fff` | — | — | — | 色塊上的字：`--up` 上 5.14、`--amber` 上 5.21、`--blue` 上 5.21 |

深色模式（兩個深色區塊都要改，否則會沿用淺色的新值）：

| token | 原值 | 新值 | `--card` | `--card2` | `--bg` |
|---|---|---|---|---|---|
| `--text3` | `#6f6f6f` | `#888` | 3.53 → **5.01** | **4.61** | **5.41** |
| `--amber` | （沿用淺色 `#e8a33d`） | 明寫 `#e8a33d` | 8.23 | 7.57 | 8.89 |
| `--blue` | （沿用淺色 `#3b82d6`） | `#488bd9` | 4.52 → **5.05** | **4.64** | **5.45** |
| `--violet` | （沿用淺色） | 明寫 `#7f77dd` | 4.72 | 4.34 | 5.10 |
| `--on-fill`（新） | — | `#111` | `--up` 上 5.68、`--amber` 上 8.76、`--blue` 上 5.37、`--violet` 上 5.02 |

- 深色的 `--up`（5.34）、`--dn`（7.58）、`--flat`（5.14）原本就及格，不動。
- 淺色值是用 WCAG 2.x 相對亮度公式算的（`ux25/contrast.py`）；深色值是 8001 實頁用 `getComputedStyle` 取色後算的。
- 影響範圍：K 線、成交量、迷你圖、法人柱等用 `css('--up')` 的圖，淺色模式的紅綠會略深；品牌圖示（頂欄 SVG 用 `var(--up)`、`var(--amber)`、`var(--dn)`）同步略深，favicon 是寫死的色碼不變。
- 小色塊（`.al`）字色改用 `--on-fill`：原本深色模式白字在琥珀底上只有 2.16。
- `★ 已加入自選`（`.star.on`）字色改用 `--on-fill`：淺色琥珀變深後，原本的 `#1b1b1b` 只剩 3.31。

---

## 二、本輪範圍（D25-xx）

| 編號 | 內容 | 對應 | 檔案 | 行數（＋／−） |
|---|---|---|---|---|
| D25-01 | 色彩 token 對比、`--on-fill`、表格與統計數字等寬 | U25-18、34 | css | 6／4 |
| D25-02 | 指數卡漲跌行同色、指數 26px | U25-02 | css、app.js | 3／2 |
| D25-03 | 今日「總覽」大盤摘要列（6 格，點了切分頁） | U25-01 | app.js、css | 16／1 |
| D25-04 | 處置／注意清單預設收合，摘要列顯示檔數 | U25-03 | app.js、css | 7／3 |
| D25-05 | 個股頁首壓縮：名稱與價格同列、標籤收合「+N」、關鍵數字列（加本益比、殖利率、法人 5 日）併進頁首 | U25-04、05、23 | stock.js、css | 15／5 |
| D25-06 | 手機表格名稱欄兩行、內距 6px | U25-26 | css | 3／0 |
| D25-07 | 長表格（≥ 25 列）固定表頭 | U25-24 | css | 3／0 |
| D25-08 | 分頁寫入網址（今日、個股、排行代號）；換股票從「走勢」開始 | U25-06 | app.js、stock.js | 10／6 |
| D25-09 | 自選頁移除（✕）＋復原、自選股的近期新訊號與處置／注意 | U25-33（部分） | app.js、css | 14／4 |
| D25-10 | 分段鈕選取反白；「錢流去哪」寫出期間 | U25-20 | css、app.js | 2／2 |
| D25-11 | 搜尋：名稱開頭優先、同組依成交額；無結果提示；下拉加收盤與漲跌 | U25-10 | app.js、css | 9／4 |
| D25-12 | 手機觸控尺寸、日期列一行、隱藏「拖曳平移、滾輪縮放」、K 線工具列與圖例緊湊 | U25-27、28、22（部分） | css、兩個 js | 7／2 |
| D25-13 | 排行常用 7 種 chip（其餘照舊在下拉） | U25-08（部分） | app.js、css | 3／0 |
| D25-14 | 選股點預設後收合條件面板 | U25-09 | app.js | 1／1 |
| D25-15 | ETF 列表名稱／代號篩選框 | U25-25（部分） | app.js | 6／0 |
| D25-16 | 小修：MACD 柱紅綠、圖表座標 11px、`.pill` 12px、`.al` 11px、代號改 `--text2`、市場寬度與信用卡「標籤＋數字」不斷行、找不到股票時給出路 | U25-19（部分）、17、12、32（部分） | 三個檔 | 8／8 |

- 行數是 `diff -u` 的 ＋／− 行：程式＋CSS 合計 ＋125／−50＝175 行（另有 `index.html` ＋3／−3），其中 `stock.js` 只有 33 行。各列行數為概估，加總以附錄 A 為準。
- 以上都**只改呈現**；搜尋排序、分頁網址、自選移除屬於功能邏輯，評估見 2-1。

### 2-1 牽涉功能邏輯的項目評估

| 項目 | 本輪 | 理由 |
|---|---|---|
| 自選頁移除（D25-09） | **做** | 只操作既有的 `tw.watch`（Set 的順序保留），有「復原」，離開自選頁才清掉復原；鍵名不變，不會遺失使用者資料 |
| 自選排序、分組 | 待辦 | 要決定互動（拖曳或上下鈕）與手機上的位置；名稱欄在手機只有 84～124px，再放兩顆鈕會擠掉漲跌 |
| 自選「今日事件」 | **做（獨立卡）** | 放在表格下方一張卡，列出有 `hl`（近期新訊號）、`dsp`、`ntc` 的自選股。不放進表格欄：手機名稱欄太窄，原型試過放在名稱下方，每列變成 6～8 行 |
| 分頁寫入網址（D25-08） | **做** | 用 `history.replaceState` 改網址，不新增瀏覽紀錄（上一頁仍回到上一個頁面，不在分頁間來回）；`localStorage` 鍵名不變 |
| 排行代號留在網址 | **做** | 第 8 輪的 `#/rank/{代號}` 本來就能用，只是讀完就改回 `#/rank`；現在保留，可分享 |
| 搜尋相關度（D25-11） | **做** | 只改候選順序：代號開頭 → 名稱開頭 → 名稱包含，後兩組依 `tv`（成交額）排序；股票仍在 ETF 前，最多 12 筆 |
| 表頭點排序（排行） | 待辦 | 排行前 50 名的選法是口徑；只在 50 列內重排會讓「漲幅排行」被重排成別的順序，需 PM 決定 |
| 漲停、跌停標示 | 待辦 | 需要漲跌停價（新口徑），請 PM 決定是否用官方資料或近似 |

---

## 三、各項規格

> 斷點：375（手機）、768（平板）、1024（桌面）。CSS 既有斷點 480／520／720／900 沿用；本輪新增的規則用 ≤ 720（手機版面）、≤ 520（窄表格）、≥ 768（頁首同列）。
> 「改後」的完整程式見附錄 A；以下寫位置、版面、數值、互動與驗收。

### D25-01 色彩 token 與等寬數字

- 位置：`app.css` 第 2～31 行的三個 token 區塊；`.stat .s` 之後新增一行。
- 數值：見 1-2。新增：

```css
.tbl,.kleg,.stat,.sum{font-variant-numeric:tabular-nums}
```

- `.al` 改 `font-size:11px;line-height:16px;padding:0 4px;color:var(--on-fill)`；`.star.on` 改 `color:var(--on-fill)`。
- 驗收：
  - 淺色：`--text3`、`--up`、`--dn`、`--flat`、`--amber`、`--blue` 在 `--card`、`--card2` 上都 ≥ 4.5:1（量法見 7-3）。
  - 深色：`--text3`、`--blue` 在 `--card`、`--card2` 上 ≥ 4.5:1，其他 token 不低於改前。
  - `--on-fill` 在 `--up`、`--amber`、`--blue` 上，兩種模式都 ≥ 4.5:1。
  - `test_iter15` 的 token 字面斷言照舊通過。

### D25-02 指數卡

- 位置：`indexCard()` 兩個 `return` 的外層類別加 `ix`（`card stat idx ix`）；`app.css` 新增：

```css
.stat .up{color:var(--up)}.stat .dn{color:var(--dn)}.stat .flat{color:var(--flat)}
.ix .v{font-size:26px;line-height:1.2}
```

- 原因：`.stat .s` 和 `.up` 權重衝突，`.stat .s` 的灰色勝出。新規則和 `.stat .s` 同權重、寫在後面，所以所有 `.stat .s.up`（指數、三大法人、信用卡）都恢復漲跌色。
- 改前／改後：

```
改前                         改後
加權指數 11/13               加權指數 11/13
43,675.12  (紅, 20px)        43,675.12  (紅, 26px)
▲ 583.25 (+1.35%)  (灰)      ▲ 583.25 (+1.35%)  (紅)
```

- 驗收：`.ix .s` 的第一行顏色等於 `--up`（漲）或 `--dn`（跌）；`.ix .v` 字級 26px。實測深色 `rgb(239,91,91)`、淺色 `rgb(204,51,51)`。

### D25-03 今日「總覽」大盤摘要列

- 位置：`app.js` 新增 `sumStrip(L)`（放在 `TODAY_TABS` 之前）；`body.ov` 最前面輸出 `${sumStrip(L)}`。
- 內容（只用 `latest.json` 現有欄位，數字格式和各分頁卡片相同）：

| 格 | 數字 | 小字 | 點擊 |
|---|---|---|---|
| 三大法人 上市 | `insti_official.total`，`sgn(v,1)億` | `外資 ±x億・官方，含 ETF` | `#/today/flow` |
| 三大法人 上櫃 | `insti_official_tpex.total` | 同上 | `#/today/flow` |
| 外資台指期淨額 | `futures_oi.inv[外資].net`，口 | `增減 ±n・大台`（和期貨法人表「淨額」「增減」同欄） | `#/today/fut` |
| 期現貨價差 | `futures.sp[最後]`，`sgn(v)` 點 | 正價差／逆價差／平價 | `#/today/fut` |
| 融資 上市 | `margin.TWSE.m1`，張 | `±p%・股票，不含 ETF` | `#/today/credit` |
| 融資 上櫃 | `margin.TWSE` 換成 `TPEx` | 同上 | `#/today/credit` |

- 資料日和 `L.date` 不同時，標籤後加「（11/12）」。沒有資料的格不輸出；全部沒有就不輸出整列。
- 版面：

```
1024（一列 6 格，每格 ≈165px，格線 1px）
┌────────────┬────────────┬────────────┬───────────┬────────────┬────────────┐
│三大法人 上市│三大法人 上櫃│外資台指期淨額│期現貨價差 │融資 上市    │融資 上櫃    │
│+452.7億     │+37.6億      │-100,870 口  │+158.88 點 │+40,113 張   │+15,159 張   │
│外資 +288.4億・官方，含 ETF │增減 -1,297・大台│正價差 │+0.67%・股票，不含 ETF│     │
└────────────┴────────────┴────────────┴───────────┴────────────┴────────────┘
375：兩欄三列（每格 ≈171×86）
```

- CSS：`.sum` 為 `grid; repeat(auto-fit,minmax(150px,1fr))`，外框 `--border` 圓角；格線用 `box-shadow: inset -1px -1px 0 var(--border)`（不用 `gap` 透底，避免奇數格時露出色塊）。標籤與小字 12px `--text2`，數字 17px／600，顏色依正負（`cls`）。
- 位置在分頁鈕下方、成交額卡上方。
- 驗收：
  - 1024 寬：`.sum` 一列，高 ≤ 110px（實測 99.5）。
  - 375 寬：`.sum` 兩欄，頁面 `scrollWidth` = 375。
  - 點「外資台指期淨額」後網址 `#/today/fut`、分頁鈕「期貨」為選取。
  - 數字和對應分頁卡片一致（上市法人 = 法人資金分頁的上市卡；淨額 = 期貨法人表外資「淨額」；融資 = 信用卡上市的張數）。

### D25-04 處置／注意清單收合

- 位置：`alertBoard()` 外層改成 `<section class="sec card"><details class="al-box">`，標題列變成 `<summary class="sec-h">`；「注意顯示全部」鈕移到展開區第一行。`renderToday()` 加一行，用 `App.alOpen` 記住展開狀態（按「注意顯示全部」重畫時不會收起來）。
- 摘要列：`處置／注意股　11/13　即將處置 0　處置中 5　今日注意 48　展開 ▾`（展開後「收合 ▴」，`--blue` 12px）。
- 「接近處置（推算）」的檔數不放在摘要列：`test_iter17` 鎖定 `A.w` 在 `app.js` 只能出現 1 次。展開後照舊顯示。
- 驗收：
  - 預設收合；1024 總覽頁高 ≤ 1,000（實測 977），375 ≤ 1,600（實測 1,545）。
  - 展開後內容、「點股票看完整原因」、每列連結和改前相同；按「注意顯示全部」後仍是展開。

### D25-05 個股頁首壓縮與關鍵數字列

- 位置：`stock.js`
  - 頁首名稱、價格兩個 `<div>` 加類別 `s-nm`、`s-px`；≥ 768 時兩者 `inline-block`，排在同一列。
  - 新增 `tagFold(t)`：產業鏈與概念股標籤只顯示前 2 個，其餘收進 `<span class="tag-rest" hidden>`，前面放 `<button class="pill more" id="tagMore">+N</button>`，點了展開並移除按鈕。「上市／上櫃」「產業」「處置／注意」「持股 →」不收。
  - 走勢分頁的指標卡區塊加類別 `kv`（`metrics kv`），陣列在 52 週高低之後、`...mtCards` 之前加 3 格（ETF 不加）：
    - `['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)]`
    - `['殖利率', …, fundSub(fund.dy)]`
    - `['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd]`
    - `fundSub` 已含「官方未提供」「資料 11/13」與股本變動註記「…官方值可能尚未調整」，防誤讀照舊可見。
  - `if (tab !== 'k') return;` 之後把 `.kv` 搬到：
    - 寬度 ≥ 721：頁首卡內 `.s-head` 下方（頁首成為「報價＋關鍵數字」一張卡）。
    - 手機：K 線卡下方（近期表現之前），讓主圖先進第一屏。
- `app.css`：

```css
.metrics.kv{grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.kv .card{border:0;border-radius:0;padding:6px 10px}.kv .s{font-size:11px;line-height:1.35}
.s-head+.kv{margin:8px 0 0}.sec.page-tabs{margin:10px 0 0}
@media (min-width:768px){.s-nm,.s-px{display:inline-block;vertical-align:baseline;margin-right:14px}}
.tag-rest:not([hidden]){display:contents}.pill.more{cursor:pointer;color:var(--blue)}
/* ≤ 720 */ .s-head{position:relative}.s-head .star{position:absolute;top:0;right:0;padding:4px 10px;font-size:13px}.s-nm{padding-right:112px}
/* ≤ 720 */ .metrics.kv{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))}
```

- 改前／改後（1024，8299）：

```
改前                                         改後
┌ 群聯 8299                    [☆ 加入自選]┐ ┌ 群聯 8299  1,640 ▲5 (+0.31%)  [★ 已加入自選]┐
│ 1,640 ▲5 (+0.31%)                        │ │ 上櫃 半導體 半導體›記憶體控制IC 半導體›IC模組 +6  11/13 收盤│
│ 上櫃 半導體 [7 個產業鏈] 記憶體  11/13 收盤│ │ 近期新訊號 → 10 月營收創新高 11/06 …        │
│ （標籤兩～三行）                           │ │ 開 1,715 高 1,740 低 1,635 昨收 1,635 量 3,227 張│
│ 近期新訊號 → …                            │ │┌52週高┬52週低┬本益比┬殖利率┬法人5日┬市值┬週轉率┐│
│ 開 … 量 …                                 │ ││2,859 │987.25│4.74 │1.41%│-10.4億│3,627億│1.46%││
└──────────────────────────────────────────┘ │└──────┴──────┴─────┴─────┴──────┴──────┴─────┘│
[走勢][籌碼][基本面]                          └──────────────────────────────────────────────┘
┌52週高┐┌52週低┐┌市值┐┌週轉率┐（一整列卡片）  [走勢][籌碼][基本面]
┌ K 線卡 ┐ 主圖 y=606                          ┌ K 線卡 ┐ 主圖 y=495
```

- 375 寬：頁首「☆ 加入自選」固定在卡片右上角，不再自成一列；名稱列右側留 112px；關鍵數字列移到 K 線卡下方，3 欄。
- 為什麼不追 1024「K 線頂端 ≤ 300」：
  - 頁首最少要有名稱價格（40）、標籤（28）、新訊號與防誤讀短句（22～42）、開高低（18），加上卡片內距、分頁鈕（40）、K 線工具列（32）與圖例（18），主圖頂端最低約 400。
  - 再壓就得移除防誤讀短句或口徑小字。本輪改成 1024×800 時主圖頂端 ≤ 500，同時多了本益比、殖利率、法人 5 日 3 個數字。
- 已知限制：關鍵數字列的位置在畫面產生時決定。在同一頁把視窗從桌面拉窄（或反過來）不會即時搬移，換頁或切分頁後就正確。
- 驗收：
  - 1024×800：2330、8299 的 `#kC` 頂端 ≤ 500（實測 495、495），2421 ≤ 480（468），0050 ≤ 480（471）。
  - 375×812：2330 `#kC` 頂端 ≤ 600（561），8299 ≤ 600（586），2421、0050 ≤ 520（478、504）。
  - 1024：`.kv` 一列 7 格（ETF 2 格），在 `.s-head` 之後、同一張卡內；375：`.kv` 在 K 線卡之後。
  - 8299 頁首標籤只有 1 個「+6」按鈕；點了後標籤共 10 個，按鈕消失。
  - 兩種寬度 `scrollWidth` = 視窗寬。
  - 本益比格的小字和「基本面」分頁本益比卡的資料日、股本變動註記相同。

### D25-06 手機表格名稱欄

- 位置：`app.css` `@media (max-width:520px)`：

```css
.tbl th,.tbl td{padding:8px 6px}
.tbl td.nm{white-space:normal;min-width:84px;max-width:124px}.tbl td.nm>span{display:block;margin-left:0}
```

- 改前／改後（375，ETF 列表，依成交額）：

```
改前：| 元大台灣50 0050 上市 持股 (209px) | 成交額 |…漲跌被切
改後：| 元大台灣50   | 成交額 | 收盤 | 漲跌 | 成交量 …
      | 0050 上市    |
```

- `.tbl td:first-child` 的 sticky（`test_iter13`）不動；第 13 輪 `keyCol` 把排序欄移到第 2 欄照舊。
- 驗收（375，`.tbl-wrap` 右緣 x=342）：
  - ETF 列表（成交額排序）、排行（法人買超、漲幅）、自選、新訊號、今日法人買超表：「漲跌」欄 `th` 右緣 ≤ 342，`scrollWidth` = 375。
  - 實測：ETF 311、排行 294、漲幅 185、自選 225、新訊號 278、法人買超 267。
  - 名稱欄寬 84～124px（實測 84～102）。

### D25-07 長表格固定表頭

- 位置：`app.css`：

```css
.tbl thead th{position:sticky;top:0;z-index:2;background:var(--card)}.tbl thead th:first-child{z-index:3}
.tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100vh - 140px);overflow:auto}
/* ≤ 720 */ .tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100dvh - 170px)}
```

- 做法：`overflow-x:auto` 的外層會讓「相對視窗」的 sticky 失效，所以 25 列以上的表格（ETF 列表、排行、選股、新訊號、主動 ETF 持股）改成表格自己的捲動區，表頭固定在捲動區頂端。左上角名稱欄同時固定左、上（z-index 3）。24 列以下的表格高度不變，沒有內部捲動。
- 不用 JS；`:has()` 支援 Chrome 105+、Safari 15.4+、Firefox 121+。
- 取捨：滑鼠或手指在表格上時先捲表格，到底才捲頁面（資料表格的通行做法）。
- 驗收：
  - ETF 列表在表格內捲到底（`scrollTop` 最大），`th` 的 `getBoundingClientRect().top` 等於 `.tbl-wrap` 的 top。
  - 375：ETF `.tbl-wrap` 的 `max-height` = `100dvh − 170`（812 時 642px）；1024：`100vh − 140`（660px）。
  - 今日法人買超表（10 列）的 `max-height` 為 `none`。

### D25-08 分頁寫入網址

- 位置：
  - `route()`：`const [, page = 'today', arg, sub] = …`，呼叫 `routes[page](arg, sub)`；`routes.stock` 改成 `(code, sub) => window.renderStock(code, sub)`。
  - `renderToday(t)`：`t` 是合法分頁就寫入 `todayTab`。分頁鈕：`history.replaceState(null, '', '#/today/' + v)`。
  - `renderStock(code, sub)`：
    - `sub` 合法：寫入 `stockTab`。
    - 沒有 `sub`，且 `code` 和上一次（`App.stockCode`）不同：寫入 `'k'`（換股票從走勢開始）。
    - 分頁鈕：`replaceState` 成 `#/stock/{code}/{v}`。
  - `renderRank(arg)`：不再把網址改回 `#/rank`。下拉、常用 chip 都用 `location.hash = '#/rank/' + 代號`。
- 測試鎖定的字面（`pageTab('todayTab', TODAY_TABS)`、`pageTab('stockTab', STOCK_TABS)`、`disposeFuturesChart(); renderToday();`、`window.disposeStockCharts(); window.renderStock(code);`）都保留。
- 驗收：
  - 個股頁點「籌碼」→ 網址 `#/stock/8299/chip`；再進 `#/stock/2330` → 停在「走勢」。
  - 直接開 `#/stock/2330/fund` → 基本面；`#/stock/0050/fund` → 走勢（ETF 沒有基本面）。
  - 直接開 `#/today/fut` → 期貨分頁；`#/rank/p+` → 下拉為「漲幅」、chip「漲幅」為選取，重新整理後相同。
  - `#/rank`（沒有代號）→ 上次選的排行（`tw.rank2`）。

### D25-09 自選頁：移除、復原、近期事件

- 位置：
  - `stockTable(list, span, rm)`：`rm` 為 true（只有 `renderWatch` 傳）時，名稱格最前面加 `<button class="wx" data-unwatch="代號" title="從自選移除" aria-label="從自選移除">✕</button>`。
  - `etfWatchTable` 同樣加 ✕。
  - `onRowClick`：先處理 `[data-unwatch]`（先備份 `App.watchUndo = [...App.watch]`，再刪除、`saveWatch()`、重畫）與 `#watchUndo`（還原整個 Set，順序不變）。
  - `onEtfRow`：`closest('a,button')` 時不進 ETF 頁。
  - `renderWatch`：
    - 有 `App.watchUndo` 時，最上方一行 `.flow-note`「已從自選移除 建準　[復原]」。
    - 股票表下方加一張卡「近期新訊號、處置／注意」：只列有 `hl`、`dsp`、`ntc` 的自選股；每檔一行 `al-row`，內容是名稱＋`alertBadge`＋`hlTag` 標籤。
    - 小字「只描述發生了什麼，不代表之後的走勢」。
  - `route()`：離開自選頁時清掉 `App.watchUndo`。
- `.wx`：24×24 圓鈕，`float:right`，`--text2`，hover 變 `--up`。
- 版面（375）：

```
自選  存在這個瀏覽器裡，換裝置不會同步         [1日][5日]
┌ 股票      │ 收盤 │ 漲跌 │ 成交額 │ 外資1日 …┐
│ 台積電 (✕)│2,350│+0.43%│733.3億│-61.5億  │
│ 2330 半導體│                                │
└───────────┴──────────────────────────────────┘
┌ 近期新訊號、處置／注意  只描述發生了什麼，不代表之後的走勢 ┐
│ 台積電　10 月營收創新高 11/10  26Q3 EPS 年增 ≥ 50% 11/13  │
│ 群聯　10 月營收創新高 11/06 …                             │
└──────────────────────────────────────────────────────────┘
```

- 驗收：
  - 點建準的 ✕：`tw.watch` 少 2421，出現「已從自選移除 建準」；點「復原」後 `tw.watch` 和移除前**相同順序**，提示消失。
  - 點 ETF 列的 ✕ 不會進 ETF 頁，網址仍是 `#/watch`。
  - 換到其他頁再回來，不再顯示復原提示。
  - 沒有任何事件時不顯示事件卡。

### D25-10 分段鈕選取狀態、錢流期間

- `.seg button.on{background:var(--text);color:var(--bg)}`：和頂部主選單 `.tabs a.on` 同樣反白；適用所有分段鈕（分頁、日週月、還原原始、1日／5日、市場）。
- 「錢流去哪」標題旁小字改成 `${今天｜近 5 日}，估算，不含 ETF`。
- 驗收：淺色、深色下，選取鈕背景＝`--text`、字＝`--bg`（對比和 `--text` 對 `--bg` 相同，淺色 15.6:1）；錢流卡小字含目前期間。

### D25-11 搜尋

- `pick`：代號開頭（照代號順序）→ 名稱開頭（依成交額）→ 名稱包含（依成交額）。股票在前、ETF 在後，最多 12 筆。
- 下拉每列：`代號 名稱 … 產業 收盤 ±x.xx%`。收盤與漲跌用 `.px num` 加漲跌色；≤ 720 隱藏產業（`.ind`）。
- 無結果：`<div class="qnone">找不到「xxx」，可輸入代號或名稱的一部分</div>`；按 Enter 沒有反應。
- 驗收：
  - 輸入「鴻」，第一筆 2317 鴻海（實測依序 2317 鴻海、7769 鴻勁、2354 鴻準、6913 鴻呈）。
  - 輸入「zzzz」，下拉顯示提示（`hidden` 為 false）。
  - 輸入「2330」第一筆仍是 2330。

### D25-12 手機觸控與首屏

- `@media (max-width:720px)`：
  - `.seg button`、`.chip`、`.sel` 的 `min-height:34px`；`.page-tabs .seg button` 38px；選股勾選框 18×18。
  - `.hint{display:none}`：個股與期貨卡的「拖曳平移、滾輪縮放」加 `hint` 類別，手機不顯示。
  - `.datebar` 改成一行，可橫向捲動、隱藏捲軸。
  - `.sec-h .seg button{padding:4px 9px}`：日週月、還原原始、回到最新排成一列。
  - `.kleg{font-size:11px;gap:2px 8px}`：十字線讀值縮成 3 行。
- 驗收（375）：
  - `.page-tabs` 按鈕高 ≥ 38、其他分段鈕 ≥ 34（實測 38、38）；選股勾選框 18px。
  - 日期列高 ≤ 20px（實測 18）。
  - 個股頁「回到最新」和日週月在同一列（`#latestBtn` 的 top 和 `#kSeg` 相差 < 10px）。

### D25-13 排行常用 chip

- 位置：`renderRank` 的表格卡片上方加 `.rk-q`：法人買超、外資買超、投信買超、漲幅、跌幅、成交額、融資增加（`avail` 沒有的不顯示）。點了 `location.hash = '#/rank/代號'`。下拉 30 種照舊。
- 驗收：目前排行若在 7 種內，chip 為選取（反白）；點「漲幅」網址為 `#/rank/p+`。

### D25-14 選股：預設收合面板

- 位置：`renderScreen` 的預設 chip 點擊處加 `open = false;`。
- 結果：桌面版點預設後條件面板收合，「符合 N 檔」緊接在預設鈕下方。
- 驗收：375、1024 點「投信認養」後，`details.scr-panel` 的 `open` 為 false，「符合 26 檔」的 `h2` 頂端 ≤ 600（1024 實測 453，改前 1,645）。手動打開面板改條件時不會自動收合。

### D25-15 ETF 列表篩選

- 位置：`renderEtf` 標題列加 `<input id="etfQ" class="sel" type="search" placeholder="篩選代號或名稱">`。輸入時只把不符合的列設 `hidden`，不重畫。值存在 `App.etfQ`，換排序、市場後保留。
- 驗收：輸入「高股息」只剩名稱含高股息的列；清空後 364 列。排序與市場切換後篩選仍有效。
- 類型篩選（市值型、債券、槓桿反向）需要新的分類欄位，列入待辦給 PM。

### D25-16 小修

| 項目 | 位置 | 改後 |
|---|---|---|
| MACD 柱 | `stock.js` `buildCharts` MACD 分支 | `(v >= 0 ? UP : DN) + 'a6'`（和成交量柱同樣紅綠帶透明）；DIF、DEA 線色不變 |
| 圖表座標字 | `stock.js` `mk()` `fontSize` | 10 → 11 |
| 小字 | `app.css` | `.pill` 11 → 12px；`.tbl .nm .pill` 10 → 11px；`.al` 10 → 11px；表格代號 `.tbl .nm span` 顏色 `--text3` → `--text2`（字級維持 11px，見下方說明） |
| 不斷行 | `breadthCard`、`marginCard` 的列 | 每個「標籤＋數字」包 `<span class="nw">`（估值卡的列被 `test_iter14` 鎖定，不動） |
| 找不到股票 | `renderStock` 的 `catch` | 「找不到 9999 的資料。可用上方搜尋框查代號或名稱，或回今日」（連到 `#/today`） |

- 表格代號維持 11px 的原因：原型改成 12px 時，1024 寬 ETF 列表寬 962px，超過容器 958px，會出現橫向捲軸。改成 `--text2`（6.39:1）已經解決看不清的問題。

---

## 四、不能破壞的事項

### 4-1 已確認

| 項目 | 結果 |
|---|---|
| `twstock/` | 0 個檔變更 |
| 資料口徑、數字 | 0 個計算改變。摘要列、關鍵數字列、自選事件卡只讀 `latest.json`／`stocks/*.json` 現有欄位，格式函式（`fmt`、`pfmt`、`sgn`、`yi`）不變 |
| 防誤讀短句 | 都可見：「官方，含 ETF」「股票，不含 ETF」「只描述發生了什麼，不代表之後的走勢」（自選事件卡、頁首）、本益比格的股本變動註記、`noteHTML` 短句 8 個不變（`test_iter13`） |
| 用詞 | 新文字：大盤摘要、移除、復原、找不到、篩選代號或名稱、正價差、逆價差、近期新訊號、處置／注意；`test_no_advice_words`（18、21、22、23）全部通過 |
| localStorage 鍵 | 不新增、不改名；`tw.watch` 格式不變 |
| 圖表函式庫 | 版本不變；K 線 attribution logo 保留 |
| 測試 | `test_iter01`～`23` 在 `proj` 全部通過；**舊斷言 0 行修改** |
| `index.html` | `?v=` 3 行更新（見 4-3） |

### 4-2 避開的測試鎖定（實作時不要「順手」改掉）

| 鎖定 | 出處 | 本設計怎麼避開 |
|---|---|---|
| `${(tab === 'k' ? [` … `: tab === 'chip' ?` 片段要含 `...mtCards]`、`區間高`／`52週高` | `test_iter13` f13_2 | 新格放在 `...mtCards` 之前；搬移用 DOM（`after`），不改模板結構 |
| `renderWatch` 在 node 裡只帶部分函式執行 | `test_iter20`、`23` | 事件卡的 `hlTag`、`HL_KINDS` 只在有 `hl` 時才求值，測試資料沒有 `hl`；移除鈕的處理放在 `onRowClick`（測試以空函式代替）；只用 `$('#view').addEventListener` 委派 |
| `etfWatchTable` 輸出含 `<td class="num">11.02億</td>`、`data-etf=` 出現 3 次 | `test_iter20` | ✕ 用 `data-unwatch`，不加 `data-etf` |
| `A.w` 在 `app.js` 只出現 1 次 | `test_iter17` | 摘要列不顯示接近處置檔數 |
| 估值卡列的字面 | `test_iter14` 第 94 行 | 不加 `.nw` |
| `hlTag` 的輸出字串 | `test_iter22` | 不改 `hlTag`（U25-35 面向色點列入待辦） |
| `.tbl th:first-child,.tbl td:first-child{position:sticky;left:0;` | `test_iter13` | 不動，另加 `thead th` 的規則 |
| `table.pf-tbl{max-width:560px}` 等第 21～23 輪 CSS 片段 | `test_iter21`、`23` | 不動 |
| token 字面 | `test_iter15` | 只改 `--text3` 之後的值 |

### 4-3 `index.html` 的 `?v=`

| 套用情境 | `app.css` | `app.js` | `stock.js` |
|---|---|---|---|
| 只套第 25 輪（附錄 A） | `5ccf0a57` | `b059864d` | `25304c73` |
| 第 24 輪附錄 A＋第 25 輪附錄 A | `edbfbd60` | `b059864d` | `f29407b3` |

- PG 實際套用後若有任何差異，以 `test_iter23` 失敗時印出的 3 行為準。
- 預覽說明：以上雜湊是最終檔；8001 量測時 `--text3` 還是 `#707070`，最後改成 `#6d6d6d`（為了在 `--bg` 上也 ≥ 4.5:1）。版面數值不受影響。

### 4-4 與第 24 輪的衝突點

- 第 24 輪附錄 A 的 `stock.js` 有 5 段（第 5～7、44～49、173～179、257～263、490～496 行附近），`app.css` 1 段（第 263～266 行），`index.html` 1 段。
- 本設計刻意避開：
  - K 線卡的 `<section class="sec card">`（原始第 178 行）落在第 24 輪 `@@ -173,7` 的前後文內，所以**不在模板加 id**，改用 `$('#kC').closest('section')` 找卡片。
  - 第 25 輪的 CSS 區塊放在 `.mk-cards{…}` 之後（約第 254 行），**不接在檔尾**：檔尾 3 行是第 24 輪 `.dv-tbl` 插入點的前後文。
  - `fontSize: 10`（第 364 行）、MACD 色（第 449 行）、頁首模板（第 136～160 行）、分頁鈕（第 201 行）都不在第 24 輪的前後文內。
- 實測（`ux25/comb`、`t24o`、`t24p`）：

| 順序 | `app.css` | `app.js` | `stock.js` | `index.html` |
|---|---|---|---|---|
| 先 24 後 25 | 乾淨 | 乾淨 | 乾淨（位移） | 25 的 `?v=` 會衝突 |
| 先 25 後 24 | 乾淨 | — | 乾淨（位移） | 24 的 `?v=` 會衝突 |

- **唯一衝突是 `index.html` 的 `?v=`**：兩輪都改同 3 行，後套的那一輪不要套 `index.html`，直接用 4-3 表格或 `test_iter23` 的輸出重寫 3 行。
- 合併後：`test_iter01`～`24` 全部通過（`test_iter24` 16 個測試 ok）。
- 第 24 輪的股利表（`.dv-tbl`，基本面分頁）會套到本輪的固定表頭規則。列數 < 25，沒有內部捲動；`.dv-tbl` 的 5px 內距寫在本輪區塊之後，照舊生效。

---

## 五、待辦（不放本輪）

| 編號 | 項目 | 理由 |
|---|---|---|
| U25-07 | 籌碼分頁加法人、融資時間序列 | 要在籌碼分頁另建圖（Lightweight Charts）與同步，`stock.js` 改動大，且接近第 24 輪的 `buildCharts` 區塊；下一輪 |
| U25-08 | 排行表頭點排序 | 口徑：在前 50 名內重排會改變「排行」的意義，請 PM 決定 |
| U25-11 | 信用估值卡改小表格 | `valCard`、`marginCard` 列的字面被 `test_iter14` 鎖定，要改測試；本輪先用 `.nw` 處理斷行 |
| U25-13 | 籌碼小卡依主題分組 | 低；和 U25-07 一起做比較合理 |
| U25-14 | 近期表現與技術面並排 | `pf-tbl` 被 `test_iter23` 鎖定，要用外層排版；低 |
| U25-15 | 「億」固定小數位或單位移到表頭 | 影響全站十幾張表的欄寬（手機漲跌欄會再被擠），請 PM 決定規則 |
| U25-16 | 還原 52 週高低的顯示位數 | 需決定規則（比照收盤的位數或兩位）；低 |
| U25-19 | 漲停、跌停標示 | 需要漲跌停價（新口徑），請 PM 決定 |
| U25-21 | 泡泡圖重疊、色階圖例、手機清單模式 | Plotly 版面邏輯，工作量大；象限說明的文案由 PM 判斷 |
| U25-22 | 子圖收合、手機預設較短區間 | 本輪只做工具列與圖例緊湊；子圖收合牽涉同步與 `CHART_IDS`，下一輪 |
| U25-25 | ETF 類型篩選 | 需要新的分類欄位（口徑），請 PM |
| U25-29 | 指數卡各分頁高度一致 | 第 13 輪刻意設計，請 PM |
| U25-30 | 卡片標題「標題＋資料日＋單位」統一 | 牽涉大量文案位置，逐卡檢查防誤讀句；下一輪 |
| U25-31 | 名稱與代號之間加空格 | 多處模板與測試字面（如 `<span>${x.code} ${esc(x.i)}</span>`）要一起改 |
| U25-32 | 圖表骨架、未知路由提示、自選空狀態放搜尋框 | 本輪只做「找不到股票」；其餘低 |
| U25-33 | 自選排序、分組 | 見 2-1 |
| U25-35 | 新訊號標籤依面向加色點 | `hlTag` 輸出被 `test_iter22` 逐字鎖定，要改測試 |
| — | 分頁在瀏覽紀錄中來回 | 本輪用 `replaceState`（可分享、可重新整理，但上一頁不在分頁間來回）；若要 `pushState` 請 PM 決定 |

---

## 六、給 PG 的實作順序與估計行數

1. **確認基線**：工作目錄 `git status` 只有第 24 輪文件與 fixture；`test_iter01`～`23` 通過。若第 24 輪已套用，見 4-4。
2. **套用附錄 A**（建議先在不含 `.env` 的暫存副本 `patch -p1 --dry-run`）：
   - `app.css`（＋45／−12）：D25-01、02、10、16 改既有行；第 25 輪區塊插在 `.mk-cards{…}` 之後。
   - `app.js`（＋59／−26）：順序 D25-08（route）→ 11（搜尋）→ 03、04、10（今日）→ 02（指數卡）→ 16（信用、寬度 `.nw`）→ 09（`onRowClick`、`stockTable`、`renderWatch`、`etfWatchTable`、`onEtfRow`）→ 13、08（排行）→ 14（選股）→ 15（ETF）。
   - `stock.js`（＋21／−12）：`tagFold`、`renderStock(code, sub)`、找不到、分頁、頁首類別、`kv`、搬移、`hint`、`fontSize`、MACD。
3. **更新 `index.html` 的 `?v=`**：跑 `python3 tests/test_iter23.py`，照失敗訊息換 3 行（或用 4-3 的值）。
4. **跑測試**：`test_iter01`～`23`（第 24 輪已套用則到 `24`），應全部通過、**不改任何舊斷言**。
5. **README**：
   - `docs/iterations/README.md` 的「現有功能」加第 25 輪一段（摘要列、處置收合、關鍵數字列、分頁網址、自選移除與事件卡、搜尋排序、固定表頭、ETF 篩選、對比 token）。
   - 專案 `README.md` 若有網站操作說明，補「網址可帶分頁：`#/stock/2330/chip`、`#/today/fut`、`#/rank/p+`」。
   - `__main__.py` 不需要改。
6. **8001 自測**：照第七節走一次 375／1024、深淺色。結束時關 8001、清 localStorage。
7. `04-dev.md` 記錄與本文件的差異。

估計：程式＋CSS 175 行（附錄 A 原樣）。若 PG 改寫成多行格式，預估 220～260 行，仍在 300 內。

---

## 七、給 QA 的佈局驗證清單

### 7-1 前置

1. 從套用後的工作目錄（或副本，不含 `.env`）執行 `python3 -m twstock serve --port 8001 --no-browser`。**不要用 8000。**
2. 開頁後先在主控台執行下面這段，確認 3 個 `?v=` 和 `index.html` 相同。若不同，代表瀏覽器用了 304 的舊快取（見分析師文件的快取插曲），再強制重新整理一次：

```js
await Promise.all(['index.html','/','app.css','app.js','stock.js'].map(f=>fetch(f,{cache:'reload'})));
[...document.querySelectorAll('link[rel=stylesheet],script[src]')].map(e=>e.getAttribute('href')||e.getAttribute('src')).filter(x=>!x.includes('http'))
```

3. 測試前 `localStorage.clear()`。寬度用 1024×800 與 mobile（375×812）兩種，配色淺、深兩種，共 4 組。**換寬度後重新整理**（D25-05 的搬移在畫面產生時決定）。
4. 收尾：`localStorage.clear(); sessionStorage.clear()`，視窗恢復 desktop，`pkill -f "twstock serve --port 8001"`，確認埠釋放。

### 7-2 量測工具（主控台）

```js
// 不觸發整頁導航的換頁＋量測
window.M = async h => { history.replaceState(null,'',h); await route(); await new Promise(r=>setTimeout(r,600));
  const q=s=>document.querySelector(s)?.getBoundingClientRect();
  return {h, kTop:q('#kC')?.top|0, kBottom:q('#kC')?.bottom|0, kv:q('.kv')?.top|0, sw:document.documentElement.scrollWidth, vw:innerWidth}; };
// 表格：漲跌欄右緣與容器右緣
const T = () => { const w=document.querySelector('#view .tbl-wrap'), th=[...w.querySelector('tr').cells];
  return {nm:th[0].getBoundingClientRect().width|0, pctRight:th.find(c=>c.textContent==='漲跌')?.getBoundingClientRect().right|0,
          wrapRight:w.getBoundingClientRect().right|0, maxH:getComputedStyle(w).maxHeight}; };
```

### 7-3 對比計算

```js
const lum=c=>{const m=c.match(/\d+(\.\d+)?/g).slice(0,3).map(Number).map(v=>v/255).map(v=>v<=0.03928?v/12.92:((v+0.055)/1.055)**2.4);return .2126*m[0]+.7152*m[1]+.0722*m[2]};
const CR=(a,b)=>{const x=[lum(a),lum(b)].sort((p,q)=>q-p);return +((x[0]+.05)/(x[1]+.05)).toFixed(2)};
const d=document.createElement('div');document.body.append(d);const col=v=>(d.style.color=`var(${v})`,getComputedStyle(d).color);
const out={};for(const t of ['--text2','--text3','--up','--dn','--flat','--amber','--blue'])out[t]=[CR(col(t),col('--card')),CR(col(t),col('--card2'))];
out.onfill=['--up','--amber','--blue'].map(t=>CR(col('--on-fill'),col(t)));d.remove();out
```

- 淺色：每個值 ≥ 4.5（`--text2` 6.39、≥ 5.9）。
- 深色：每個值 ≥ 4.5。
- `onfill` 三個值兩種模式都 ≥ 4.5。

### 7-4 逐頁清單（每頁 × 375／1024 × 淺／深）

| # | 頁面 | 量測 | 通過條件 |
|---|---|---|---|
| 1 | 全站 | `M(h).sw` | 每頁 `scrollWidth` = `innerWidth`（不水平捲動） |
| 2 | 今日 總覽 | `.ix .v` 字級、`.ix .s` 顏色 | 26px；第一個 `.s` 顏色 = `--up`／`--dn`（依漲跌） |
| 3 | 今日 總覽 | `.sum` | 1024 一列 6 格、高 ≤ 110；375 兩欄；數字和法人資金、期貨、信用估值分頁一致；點格子後網址為 `#/today/flow`／`fut`／`credit` 且分頁選取正確 |
| 4 | 今日 總覽 | `details.al-box` | 預設收合；摘要列含「即將處置 n　處置中 n　今日注意 n」；展開後按「注意顯示全部」仍展開；頁高 1024 ≤ 1,000、375 ≤ 1,600 |
| 5 | 今日 法人資金 | 錢流卡 | 小字含「今天」或「近 5 日」，和選取的鈕一致 |
| 6 | 今日 期貨 | 卡片 | 375 不顯示「拖曳平移、滾輪縮放」；1024 顯示 |
| 7 | 個股 2330、8299、2421、0050 | `M('#/stock/…')` | `kTop`：1024 ≤ 500（2330、8299）、≤ 480（2421、0050）；375 ≤ 600（2330、8299）、≤ 520（2421、0050）。1024 `.kv` 在頁首卡內（`.s-head` 的下一個兄弟）；375 在 K 線卡之後 |
| 8 | 個股 8299 | 標籤 | 只有一個「+6」；點了後標籤共 10 個、按鈕消失 |
| 9 | 個股 2330 | 關鍵數字列 | 1024 一列 7 格（52週高、52週低、本益比、殖利率、法人5日、市值、週轉率）；本益比小字和基本面分頁的資料日相同；ETF 0050 只有 2 格 |
| 10 | 個股 375 | 頁首 | 「☆ 加入自選」在卡片右上角，不自成一列；名稱不被蓋住；日週月、還原原始、回到最新同一列 |
| 11 | 個股 分頁 | 網址 | 點籌碼 → `#/stock/8299/chip`；改開 `#/stock/2330` → 走勢；開 `#/stock/2330/fund` → 基本面；重新整理後不變 |
| 12 | 個股 MACD | 柱色 | 正柱為 `--up` 帶透明、負柱為 `--dn` 帶透明（目視） |
| 13 | 個股 `#/stock/9999` | 文字 | 「找不到 9999 的資料。可用上方搜尋框…或回今日」，「回今日」可點 |
| 14 | 排行 `#/rank` | chip、網址 | 7 個常用 chip；點「漲幅」網址為 `#/rank/p+`、chip 與下拉同步；375 `T().pctRight ≤ wrapRight` |
| 15 | 排行、ETF、選股、新訊號 | 固定表頭 | `T().maxH` 為 1024 `660px`、375 `642px`；在 `.tbl-wrap` 內捲到底後 `th.top === wrap.top`；名稱欄左右捲動時仍固定 |
| 16 | 選股 | 預設 | 點「投信認養」：`details.scr-panel.open === false`，「符合 N 檔」`h2` 頂端 1024 ≤ 600、375 ≤ 600 |
| 17 | 新訊號 | 名稱欄 | 375 名稱欄寬 ≤ 124、漲跌欄可見 |
| 18 | ETF 列表 | 名稱欄、篩選 | 375 名稱欄 ≤ 124、漲跌欄右緣 ≤ 容器右緣；1024 表格 `scrollWidth ≤ clientWidth`；篩選「高股息」後只剩相符列，換排序後仍有效 |
| 19 | 自選 | 移除、復原 | 加入 2330、2421、8299、0050；✕ 建準 → 提示；復原 → `tw.watch` 順序和移除前相同；✕ 0050 不進 ETF 頁；離開再回來提示消失 |
| 20 | 自選 | 事件卡 | 只列有新訊號或處置／注意的股票，含「只描述發生了什麼，不代表之後的走勢」 |
| 21 | 搜尋 | 下拉 | 「鴻」第一筆 2317；「zzzz」顯示找不到提示；下拉有收盤與漲跌色；375 不顯示產業 |
| 22 | 手機觸控 | `getBoundingClientRect().height` | `.page-tabs` 按鈕 ≥ 38；其他 `.seg button`、`.chip`、`.sel` ≥ 34；選股勾選框 18 |
| 23 | 手機日期列 | `#dateBar` 高 | ≤ 20px，一行 |
| 24 | 深色 | 小色塊 | 「處」「注」「股本變動」「新」字色 `#111`，對比 ≥ 4.5；★ 已加入自選字色 `#111` |
| 25 | 主控台 | 錯誤 | 每頁 0 個錯誤 |

### 7-5 回歸

- 第 13 輪：排序欄移到第 2 欄、表格第一欄固定、說明收合。
- 第 16、17 輪：處置清單展開後內容與連結。
- 第 18、19 輪：MACD／KD／RSI 切換、週月 K 事件標記。
- 第 22、23 輪：頁首新訊號、近期表現、`serve` 的 `no-cache`。
- 第 24 輪（若已套用）：基本面分頁的股利與填息表在 375 寬 309px、不水平捲動。

---

## 附錄 A：完整 diff（`orig` → `proj`）

- 原型檔：scratchpad `ux25/proj/site/`。
- 套用：在專案根目錄 `sed 's#^--- orig/site/#--- a/site/#; s#^+++ proj/site/#+++ b/site/#' | patch -p1`，或手動照抄。
- 以下 4 段依序為 `app.css`、`app.js`、`stock.js`、`index.html`（`index.html` 只適用「只套第 25 輪」；和第 24 輪合併時見 4-3）。


### A-d_css `app.css`

```diff
--- orig/site/app.css	2026-11-14 11:08:24
+++ proj/site/app.css	2026-11-14 23:40:04
@@ -1,9 +1,9 @@
 *{box-sizing:border-box;margin:0;padding:0}
 :root{
   --bg:#f3f2ee;--card:#ffffff;--card2:#f8f7f3;
-  --text:#1b1b1b;--text2:#5f5f5f;--text3:#999;
+  --text:#1b1b1b;--text2:#5f5f5f;--text3:#6d6d6d;
   --border:#e3e1da;--border2:#cfcdc5;
-  --up:#d64545;--dn:#30a46c;--flat:#8a8a8a;--amber:#e8a33d;--blue:#3b82d6;--violet:#7f77dd;
+  --up:#cc3333;--dn:#247b51;--flat:#6d6d6d;--amber:#976112;--blue:#286dbf;--violet:#6b62d6;--on-fill:#fff;   /* 第 25 輪 D25-01：白底 ≥ 4.5:1 */
   --up-bg:rgba(214,69,69,.10);--dn-bg:rgba(48,164,108,.12);
   --q-rise:rgba(214,69,69,.07);--q-rot:rgba(232,163,61,.08);--q-watch:rgba(59,130,214,.07);--q-ebb:rgba(48,164,108,.07);
   --radius:10px;--shadow:0 1px 2px rgba(0,0,0,.04);
@@ -12,9 +12,9 @@
 @media (prefers-color-scheme:dark){
   :root:not([data-theme="light"]){
     --bg:#0e0f11;--card:#17181b;--card2:#1e2023;
-    --text:#ececec;--text2:#a7a7a7;--text3:#6f6f6f;
+    --text:#ececec;--text2:#a7a7a7;--text3:#888;
     --border:#2a2c30;--border2:#3a3d42;
-    --up:#ef5b5b;--dn:#3fbf7f;--flat:#8a8a8a;
+    --up:#ef5b5b;--dn:#3fbf7f;--flat:#8a8a8a;--amber:#e8a33d;--blue:#488bd9;--violet:#7f77dd;--on-fill:#111;
     --up-bg:rgba(239,91,91,.14);--dn-bg:rgba(63,191,127,.14);
     --q-rise:rgba(239,91,91,.08);--q-rot:rgba(232,163,61,.08);--q-watch:rgba(59,130,214,.09);--q-ebb:rgba(63,191,127,.08);
     color-scheme:dark;
@@ -22,9 +22,9 @@
 }
 :root[data-theme="dark"]{
   --bg:#0e0f11;--card:#17181b;--card2:#1e2023;
-  --text:#ececec;--text2:#a7a7a7;--text3:#6f6f6f;
+  --text:#ececec;--text2:#a7a7a7;--text3:#888;
   --border:#2a2c30;--border2:#3a3d42;
-  --up:#ef5b5b;--dn:#3fbf7f;--flat:#8a8a8a;
+  --up:#ef5b5b;--dn:#3fbf7f;--flat:#8a8a8a;--amber:#e8a33d;--blue:#488bd9;--violet:#7f77dd;--on-fill:#111;
   --up-bg:rgba(239,91,91,.14);--dn-bg:rgba(63,191,127,.14);
   --q-rise:rgba(239,91,91,.08);--q-rot:rgba(232,163,61,.08);--q-watch:rgba(59,130,214,.09);--q-ebb:rgba(63,191,127,.08);
   color-scheme:dark;
@@ -86,11 +86,13 @@
 .stat .l{font-size:12px;color:var(--text2)}
 .stat .v{font-size:20px;font-weight:600;margin-top:2px}
 .stat .s{font-size:12px;color:var(--text2);margin-top:2px}
+.stat .up{color:var(--up)}.stat .dn{color:var(--dn)}.stat .flat{color:var(--flat)}   /* D25-02：.stat .s 裡的漲跌色 */
+.ix .v{font-size:26px;line-height:1.2}.tbl,.kleg,.stat,.sum{font-variant-numeric:tabular-nums}
 
 /* 切換鈕 */
 .seg{display:inline-flex;background:var(--card2);border:1px solid var(--border);border-radius:999px;padding:2px}
 .seg button{border:none;background:none;padding:4px 12px;border-radius:999px;font-size:12px;color:var(--text2)}
-.seg button.on{background:var(--card);color:var(--text);box-shadow:0 1px 2px rgba(0,0,0,.12)}
+.seg button.on{background:var(--text);color:var(--bg)}   /* D25-10：和頂部選單同樣反白 */
 
 /* 四象限 */
 .quads{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@@ -123,8 +125,8 @@
 .tbl tr[data-code]:hover td{background:var(--card2)}
 .tbl tr[data-etf]{cursor:pointer}.tbl tr[data-etf]:hover td{background:var(--card2)}   /* 第 15 輪：ETF 列表整列進 ETF 個股頁 */
 .tbl .nm b{font-weight:500}
-.tbl .nm span{color:var(--text3);font-size:11px;margin-left:6px}
-.pill{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px;background:var(--card2);border:1px solid var(--border);color:var(--text2)}
+.tbl .nm span{color:var(--text2);font-size:11px;margin-left:6px}
+.pill{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;background:var(--card2);border:1px solid var(--border);color:var(--text2)}
 .pill.chain{border-color:color-mix(in srgb,var(--blue) 45%,var(--border));color:var(--text)}
 
 /* 台指期 */
@@ -143,7 +145,7 @@
 .s-price{font-size:34px;font-weight:600;line-height:1.1;margin-top:4px}
 .s-chg{font-size:16px;margin-left:8px}
 .star{margin-left:auto;border:1px solid var(--border2);background:var(--card);border-radius:999px;padding:6px 14px}
-.star.on{background:var(--amber);border-color:var(--amber);color:#1b1b1b}
+.star.on{background:var(--amber);border-color:var(--amber);color:var(--on-fill)}
 .tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
 .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px}
 .metrics .card{padding:10px 12px}
@@ -208,7 +210,7 @@
 .page-tabs{margin:12px 0 4px;overflow-x:auto}          /* 首頁、個股頁分頁 */
 .page-tabs .seg button{padding:6px 16px;font-size:14px;white-space:nowrap}
 .night-old{opacity:.7}               /* P20：前一夜盤淡化 */
-.al{display:inline-block;font-style:normal;font-size:10px;line-height:15px;padding:0 3px;border-radius:3px;margin-left:4px;color:#fff;vertical-align:1px}
+.al{display:inline-block;font-style:normal;font-size:11px;line-height:16px;padding:0 4px;border-radius:3px;margin-left:4px;color:var(--on-fill);vertical-align:1px}
 .al-d{background:var(--up)}.al-n{background:var(--amber)}
 .pill.al-d{background:var(--up-bg);border-color:var(--up);color:var(--up)}
 .pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
@@ -219,7 +221,7 @@
 .al-l{display:flex;align-items:baseline;gap:6px}.al-l .sp{flex:1}.al-why{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .al-new{background:var(--blue)}                                  /* E2-4：新建倉 */
 .pill.hold{margin-left:6px;border-color:var(--blue);color:var(--blue)}
-.tbl .nm .pill{font-size:10px;margin-left:6px}
+.tbl .nm .pill{font-size:11px;margin-left:6px}
 /* 第 8 輪 F8-2：條件選股 */
 .al-c{background:var(--violet)}                                    /* 90 天內股本變動 */
 .chip{border:1px solid var(--border2);background:var(--card);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--text)}
@@ -251,6 +253,37 @@
 /* 第 13 輪 QA 後修正：兩張成交額卡＋共同說明包成一組（佔 2 欄），市場寬度卡仍在同一列右側 */
 .g-mk .mk-pair{grid-column:span 2;display:flex;flex-direction:column;gap:6px}
 .mk-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
+/* ─── 第 25 輪（D25-xx）────────────────────────── */
+.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}   /* D25-03 大盤摘要 */
+.sum-i,.kv .card{box-shadow:inset -1px -1px 0 var(--border)}.sum-i{display:flex;flex-direction:column;gap:1px;padding:8px 12px}.sum-i:hover{background:var(--card2)}
+.sum-i .l,.sum-i .s{font-size:12px;color:var(--text2)}.sum-i b{font-size:17px;font-weight:600}
+.al-box>summary{list-style:none;cursor:pointer;margin-bottom:0}.al-box>summary::-webkit-details-marker{display:none}.al-box[open]>summary{margin-bottom:6px}   /* D25-04 */
+.al-box>summary i{font-style:normal;color:var(--blue);font-size:12px}.al-box>summary i::after{content:'展開 ▾'}.al-box[open]>summary i::after{content:'收合 ▴'}
+.tbl thead th{position:sticky;top:0;z-index:2;background:var(--card)}.tbl thead th:first-child{z-index:3}   /* D25-07 固定表頭 */
+.tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100vh - 140px);overflow:auto}
+.metrics.kv{grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}   /* D25-05 關鍵數字列 */
+.kv .card{border:0;border-radius:0;padding:6px 10px}.kv .s{font-size:11px;line-height:1.35}
+.s-head+.kv{margin:8px 0 0}.sec.page-tabs{margin:10px 0 0}
+@media (min-width:768px){.s-nm,.s-px{display:inline-block;vertical-align:baseline;margin-right:14px}}
+.tag-rest:not([hidden]){display:contents}.pill.more{cursor:pointer;color:var(--blue)}
+.qlist .px{margin-left:10px;white-space:nowrap}.qnone{padding:10px 12px;color:var(--text2);font-size:13px}   /* D25-11 */
+.wx{float:right;margin-left:6px;border:1px solid var(--border);background:var(--card);color:var(--text2);border-radius:999px;width:24px;height:24px;line-height:20px;font-size:12px}.wx:hover{color:var(--up)}   /* D25-09 自選移除 */
+.card.w-ev{margin-top:12px}.w-ev .sec-h{margin-bottom:4px}
+.rk-q{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px}
+@media (max-width:720px){
+  .seg button{min-height:34px}.page-tabs .seg button{min-height:38px}.chip,.sel{min-height:34px}.scr-c input[type=checkbox]{width:18px;height:18px}   /* D25-12 觸控 */
+  .hint{display:none}
+  .datebar{white-space:nowrap;overflow-x:auto;scrollbar-width:none}
+  .tbl-wrap:has(tbody tr:nth-child(25)){max-height:calc(100dvh - 170px)}
+  .s-head{position:relative}.s-head .star{position:absolute;top:0;right:0;padding:4px 10px;font-size:13px}.s-nm{padding-right:112px}
+  .qlist .ind{display:none}
+  .metrics.kv{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))}
+  .sec-h .seg button{padding:4px 9px}.kleg{font-size:11px;gap:2px 8px}
+}
+@media (max-width:520px){
+  .tbl th,.tbl td{padding:8px 6px}
+  .tbl td.nm{white-space:normal;min-width:84px;max-width:124px}.tbl td.nm>span{display:block;margin-left:0}   /* D25-06 名稱欄兩行 */
+}
 /* 第 14 輪 F14-1、F14-2：營收、EPS 年增欄的第二行（月份、基期低、去年同季），欄寬不被撐開 */
 .tbl .sub2{display:block;font-size:11px;line-height:1.3;color:var(--text2)}
 .al-b{background:var(--flat)}.al-r{background:var(--blue)}
```

### A-d_app `app.js`

```diff
--- orig/site/app.js	2026-11-14 11:08:24
+++ proj/site/app.js	2026-11-14 23:35:09
@@ -63,18 +63,19 @@
   rank: arg => arg && arg.startsWith('screen') ? renderScreen(arg.slice(6)) : arg === 'hl' ? renderHl() : renderRank(arg),   // 第 8 輪：#/rank/screen 條件選股；第 21 輪：#/rank/hl 新訊號
   watch: renderWatch,
   etf: code => code === 'active' ? renderActive() : code ? renderHoldings(code) : renderEtf(),   // 第 7 輪：#/etf/active 彙總排行
-  stock: code => window.renderStock(code),
+  stock: (code, sub) => window.renderStock(code, sub),   // 第 25 輪 D25-08：#/stock/代號/分頁
 };
 
 async function route() {
-  const [, page = 'today', arg] = location.hash.split('/');
+  const [, page = 'today', arg, sub] = location.hash.split('/');
+  if (page !== 'watch') App.watchUndo = null;
   document.querySelectorAll('[data-tab]').forEach(a => a.classList.toggle('on', a.dataset.tab === page));
   const view = $('#view');
   if (window.Plotly && $('#bubble')) Plotly.purge('bubble');
   window.disposeStockCharts?.();
   disposeFuturesChart();
   try {
-    await (routes[page] || renderToday)(arg);
+    await (routes[page] || renderToday)(arg, sub);
   } catch (e) {
     console.error(e);
     view.innerHTML = `<div class="empty">載入失敗：${esc(e.message)}</div>`;
@@ -89,14 +90,19 @@
   const go = code => { list.hidden = true; input.value = ''; input.blur(); location.hash = '#/stock/' + code; };
   const draw = () => {
     list.innerHTML = hits.map(([c, s], i) =>
-      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span>${esc(s.n)}<span class="muted small" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span></a>`).join('');
-    list.hidden = !hits.length;
+      `<a href="#/stock/${c}" class="${i === active ? 'on' : ''}"><span class="code">${c}</span>${esc(s.n)}<span class="muted small ind" style="margin-left:auto">${esc(s.i ?? 'ETF')}</span>` +
+      `<span class="px num ${cls(s.p)}">${pfmt(s.c)}${s.p == null ? '' : ' ' + sgn(s.p) + '%'}</span></a>`).join('') ||
+      (input.value.trim() && App.latest ? `<div class="qnone">找不到「${esc(input.value.trim())}」，可輸入代號或名稱的一部分</div>` : '');   // 第 25 輪 D25-11
+    list.hidden = !list.innerHTML;
   };
   input.addEventListener('input', () => {
     const q = input.value.trim().toLowerCase();
     if (!q || !App.latest) { hits = []; return draw(); }
     // 第 15 輪 F15-2：股票照舊在前（代號開頭 → 名稱包含），ETF（latest.json etfs.rows）同規則接在後面
-    const pick = all => all.filter(([c]) => c.toLowerCase().startsWith(q)).concat(all.filter(([c, s]) => !c.toLowerCase().startsWith(q) && s.n.toLowerCase().includes(q)));   // 代號轉小寫：00981A
+    // 第 25 輪 D25-11：名稱開頭符合的排在名稱包含之前，兩組各依成交額由大到小
+    const byTv = (a, b) => (b[1].tv ?? 0) - (a[1].tv ?? 0), nm = s => s.n.toLowerCase();
+    const pick = all => { const rest = all.filter(([c]) => !c.toLowerCase().startsWith(q));   // 代號轉小寫：00981A
+      return all.filter(([c]) => c.toLowerCase().startsWith(q)).concat(rest.filter(([, s]) => nm(s).startsWith(q)).sort(byTv), rest.filter(([, s]) => !nm(s).startsWith(q) && nm(s).includes(q)).sort(byTv)); };
     hits = pick(Object.entries(App.latest.stocks)).concat(pick(Object.entries(App.latest.etfs?.rows || {}))).slice(0, 12);
     active = 0;
     draw();
@@ -117,8 +123,9 @@
   ['漲潮', '加速流入'], ['輪動', '流入但放緩'], ['觀望', '流出但放緩'], ['退潮', '加速流出'],
 ];
 
-function renderToday() {
+function renderToday(t) {
   const L = App.latest, groups = L.groups[App.group];
+  if (TODAY_TABS.some(x => x[0] === t)) localStore('todayTab', null, t);   // 第 25 輪 D25-08：#/today/分頁
   const span = localStore('span', '5');
   const key = span === '1' ? 'net_1d' : 'net_5d';
   const counts = Object.fromEntries(QUADS.map(([q]) => [q, groups.filter(g => g.quadrant === q).length]));
@@ -153,7 +160,7 @@
   const tab = pageTab('todayTab', TODAY_TABS);
   const fut = `${futuresHTML(L.futures)}${oiHTML(L.futures_oi, L.forecast)}`;
   const body = {
-    ov: `<section class="sec grid g-stats g-mk">
+    ov: `${sumStrip(L)}<section class="sec grid g-stats g-mk">
       <div class="mk-pair"><div class="mk-cards">${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}</div>
       ${L.breadth?.TWSE?.o || L.breadth?.TPEx?.o ? '<div class="muted small">家數為官方（股票）；成交額為網站自算，不含 ETF</div>' : ''}</div>
       ${breadthCard(L)}
@@ -172,7 +179,7 @@
   body.flow = `<section class="sec grid ${L.insti_official ? 'g2' : 'g-one'}">${instiCard(L)}</section>
     <section class="sec grid g2">
       <div class="card">
-        <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
+        <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">${span === '1' ? '今天' : '近 5 日'}，估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
         <div class="bars">${inflow.slice(0, nFlow).map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
       </div>
       <div class="card">
@@ -194,15 +201,28 @@
     ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
     ${body[tab]}`;
 
-  onSeg('todayTabSeg', v => { localStore('todayTab', null, v); disposeFuturesChart(); renderToday(); });
+  onSeg('todayTabSeg', v => { localStore('todayTab', null, v); history.replaceState(null, '', '#/today/' + v); disposeFuturesChart(); renderToday(); });
   if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
   $('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });
   $('#alMore')?.addEventListener('click', () => { App.alertAll = !App.alertAll; renderToday(); });
+  $('#view details.al-box')?.addEventListener('toggle', e => { App.alOpen = e.target.open; });
   $('#view').addEventListener('click', onRowClick);
   if (tab === 'fut') { drawFutures(L.futures); drawOI(L.futures_oi); }
 }
 
+// 第 25 輪 D25-03：總覽最上方的大盤摘要。數字和口徑沿用各分頁的卡片（官方法人、期貨法人大台淨額、價差、股票融資），點了切到該分頁
+function sumStrip(L) {
+  const O = L.insti_official, P = L.insti_official_tpex, F = L.futures, k = (F?.d?.length ?? 0) - 1, sp = F?.sp?.[k];
+  const X = L.futures_oi?.inv?.find(r => r.k === 'foreign'), M = L.margin || {}, dd = x => x && x !== L.date ? `（${md(x)}）` : '';
+  const it = (tab, l, n, v, sub) => `<a class="sum-i" href="#/today/${tab}"><span class="l">${l}</span><b class="${cls(n)}">${v}</b><span class="s">${sub}</span></a>`;
+  const ins = (x, m) => x && it('flow', `三大法人 ${m}${dd(x.date)}`, x.total, sgn(x.total, 1) + '億', `外資 ${sgn(x.foreign, 1)}億・官方，含 ETF`);
+  const mg = (x, m) => x && it('credit', `融資 ${m}${dd(x.d)}`, x.m1, sgn(x.m1, 0) + ' 張', `${sgn(x.mp)}%・股票，不含 ETF`);
+  const html = [ins(O, '上市'), ins(P, '上櫃'), X && it('fut', `外資台指期淨額${dd(L.futures_oi.date)}`, X.net, sgn(X.net, 0) + ' 口', `增減 ${sgn(X.chg, 0)}・大台`),
+    sp != null && it('fut', `期現貨價差${dd(F.d[k])}`, sp, sgn(sp) + ' 點', sp > 0 ? '正價差' : sp < 0 ? '逆價差' : '平價'), mg(M.TWSE, '上市'), mg(M.TPEx, '上櫃')].filter(Boolean).join('');
+  return html ? `<section class="sec sum">${html}</section>` : '';
+}
+
 // 首頁、個股頁的分頁（記住上次選的分頁；存的值不在清單裡就用第一個）
 const TODAY_TABS = [['ov', '總覽'], ['flow', '法人資金'], ['credit', '信用估值'], ['fut', '期貨']];
 function pageTab(key, tabs) {
@@ -240,9 +260,9 @@
 }
 
 function indexCard(x, name, full = true) {   // full = false：省略迷你圖下方的區間漲跌（第 13 輪 F13-4，非總覽分頁）
-  if (!x) return `<div class="card stat idx"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
+  if (!x) return `<div class="card stat idx ix"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
   const stale = x.date < App.latest.date;
-  return `<div class="card stat idx">
+  return `<div class="card stat idx ix">
       <div class="l">${name}<span class="muted">　${md(x.date)}${stale ? '（尚未更新）' : ''}</span></div>
       <div class="v num ${cls(x.ch)}">${fmt(x.c, 2)}</div>
       <div class="s num ${cls(x.ch)}">${x.ch > 0 ? '▲' : x.ch < 0 ? '▼' : ''} ${fmt(Math.abs(x.ch ?? 0), 2)} (${sgn(x.p)}%)</div>
@@ -272,7 +292,7 @@
   const T = M.TWSE, O = M.TPEx, d = [T?.d, O?.d].filter(Boolean).sort().at(-1);
   const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, 1)}</b> 萬張`;
   const lots = n => `<span class="${cls(n)}">${sgn(n, 0)}</span>`;
-  const row = (x, name) => !x ? '' : `<div class="s num">${name}　融資 ${wan(x.mb)} ${lots(x.m1)}（${sgn(x.mp)}%）　融券 ${wan(x.sb)} ${lots(x.s1)}　券資比 ${fmt(x.sr, 2)}%${x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : ''}</div>`;
+  const row = (x, name) => !x ? '' : `<div class="s num">${name}　<span class="nw">融資 ${wan(x.mb)} ${lots(x.m1)}（${sgn(x.mp)}%）</span>　<span class="nw">融券 ${wan(x.sb)} ${lots(x.s1)}</span>　<span class="nw">券資比 ${fmt(x.sr, 2)}%</span>${x.d < d ? `<span class="muted">（${md(x.d)}）</span>` : ''}</div>`;
   const mr = x => !x ? '--' : x.mr == null ? '資料不足' : `${fmt(x.mr, 1)}%（前日 ${x.mr0 == null ? '--' : fmt(x.mr0, 1) + '%'}）`;
   const amt = x => !x ? '--' : `${fmt(x.amt, 1)} 億 <span class="${cls(x.amt1)}">${x.amt1 > 0 ? '▲' : x.amt1 < 0 ? '▼' : ''}${fmt(Math.abs(x.amt1), 1)} 億</span>`;
   const E = T?.etf;
@@ -324,11 +344,12 @@
   const up = A.d.filter(x => x[1] > L.date), on = A.d.filter(x => x[1] <= L.date);
   const nShow = App.alertAll ? A.n.length : 10;
   const grp = (t, list, n = list.length) => `<div class="al-grp"><h3>${t}　<span class="muted small">${n} 檔</span></h3>${list.join('') || '<div class="muted small">無</div>'}</div>`;
-  return `<section class="sec card">
-      <div class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}</span><span class="sp"></span>${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}</div>
+  return `<section class="sec card"><details class="al-box"${App.alOpen ? ' open' : ''}>
+      <summary class="sec-h"><h2>處置／注意股</h2><span class="muted small">${md(L.date)}　即將處置 ${up.length}　處置中 ${on.length}　今日注意 ${A.n.length}</span><span class="sp"></span><i></i></summary>
+      ${A.n.length > 10 ? `<button class="chip" id="alMore">${App.alertAll ? '注意只顯示 10 檔' : '注意顯示全部'}</button>` : ''}
       ${grp('即將處置', up.map(dsp))}${grp('處置中', on.map(dsp))}${watchGrp(A.w, S)}${grp('今日注意', A.n.slice(0, nShow).map(x => row(x[0], '', x[1])), A.n.length)}
       <div class="muted small">依證交所、櫃買中心公告；處置期間撮合間隔較長，買賣可能需預收款券。點股票看完整原因</div>
-    </section>`;
+    </details></section>`;
 }
 
 // 第 17 輪 F17-2：接近處置（依注意款別推算）；已達條件逐檔一行，差一次只列名稱（提示是條件）
@@ -349,7 +370,7 @@
   const B = L.breadth;
   if (!B) return '';
   const pct = v => v == null ? '--' : fmt(v, 1) + '%';
-  const row = (x, name) => !x ? '' : `<div class="s num">${name}　站上 MA20 <b>${pct(x.ma20)}</b>（前日 ${pct(x.s20.at(-2))}）　MA60 <b>${pct(x.ma60)}</b>　20 日新高 <span class="up">${fmt(x.hi)}</span>、新低 <span class="dn">${fmt(x.lo)}</span>　量能 <b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b></div>`;
+  const row = (x, name) => !x ? '' : `<div class="s num">${name}　<span class="nw">站上 MA20 <b>${pct(x.ma20)}</b>（前日 ${pct(x.s20.at(-2))}）</span>　<span class="nw">MA60 <b>${pct(x.ma60)}</b></span>　<span class="nw">20 日新高 <span class="up">${fmt(x.hi)}</span>、新低 <span class="dn">${fmt(x.lo)}</span></span>　<span class="nw">量能 <b>${x.vr == null ? '--' : fmt(x.vr, 2) + ' 倍'}</b></span></div>`;
   const T = B.TWSE, s = T?.s20.filter(v => v != null) || [];
   return `<div class="card stat idx margin">
       <div class="l">市場寬度 ${md(T?.d || B.TPEx?.d)}（自算，股票，不含 ETF）</div>
@@ -454,7 +475,7 @@
   const roll = k > 0 && F.m[k] !== F.m[k - 1];                 // 第 14 輪 F14-3：近月和前一個交易日不同 = 今天換月
   return `<section class="sec card">
       <div class="sec-h"><h2>${esc(F.name)}</h2><span class="muted small">日盤・契約 ${F.m[k]}${roll ? '<i class="al al-r">今天換月</i>' : ''}</span>
-        <span class="sp"></span><span class="muted small">拖曳平移、滾輪縮放</span></div>
+        <span class="sp"></span><span class="muted small hint">拖曳平移、滾輪縮放</span></div>
       <div class="fut-head">
         <span class="s-price num ${cls(ch)}" style="font-size:26px">${fmt(c)}</span>
         <span class="s-chg num ${cls(ch)}">${ch > 0 ? '▲' : ch < 0 ? '▼' : ''} ${fmt(Math.abs(ch ?? 0))} (${sgn(pct)}%)</span>
@@ -612,6 +633,9 @@
 }
 
 function onRowClick(e) {
+  const u = e.target.closest('[data-unwatch]'), r = e.target.closest('#watchUndo');   // 第 25 輪 D25-09：自選頁移除、復原
+  if (u || r) { if (u) { App.watchUndo = [...App.watch]; App.watch.delete(u.dataset.unwatch); } else { App.watch = new Set(App.watchUndo); App.watchUndo = null; }
+    saveWatch(); return renderWatch(); }
   const tr = e.target.closest('tr[data-code]');
   if (tr) { location.hash = '#/stock/' + tr.dataset.code; return; }
   const g = e.target.closest('[data-group]');
@@ -804,7 +828,7 @@
 const modeSeg = v => segHTML('modeSeg', [['rank', '排行'], ['screen', '選股'], ['hl', '新訊號']], v);
 const onModeSeg = () => onSeg('modeSeg', v => { location.hash = v === 'rank' ? '#/rank' : '#/rank/' + v; });
 
-function stockTable(list, span = '1') {
+function stockTable(list, span = '1', rm = false) {   // rm：自選頁（名稱旁加移除鈕）
   const k = span === '5' ? '5' : '1', lbl = k === '5' ? '5日' : '1日';
   const amt = v => `<td class="num ${cls(v)}">${yi(v)}</td>`;
   const fd = md(App.latest.flow_date);
@@ -813,7 +837,7 @@
       <th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>
       <th>外資連</th><th>投信連</th><th>法人連</th></tr></thead><tbody>` +
     list.map(([c, s]) => `<tr data-code="${c}">
-      <td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>${c} ${esc(s.i)}</span></td>
+      <td class="nm">${rm ? `<button class="wx" data-unwatch="${c}" title="從自選移除" aria-label="從自選移除">✕</button>` : ''}<b>${esc(s.n)}</b>${alertBadge(s)}<span>${c} ${esc(s.i)}</span></td>
       <td class="num ${cls(s.p)}">${pfmt(s.c)}</td>${pctCell(s)}
       <td class="num">${fmt(s.tv, 1)}億</td>
       ${amt(s['f' + k])}${amt(s['t' + k])}${amt(s['d' + k])}${amt(s['n' + k])}
@@ -826,7 +850,7 @@
 
 async function renderRank(arg) {
   // 第 8 輪：#/rank/{排行代號}（例如信用交易卡的 #/rank/s-）→ 記住排行後把網址改回 #/rank
-  if (arg && RANKS.some(r => r[0] === arg)) { localStore('rank2', null, arg); history.replaceState(null, '', '#/rank'); }
+  if (arg && RANKS.some(r => r[0] === arg)) localStore('rank2', null, arg);   // 第 25 輪 D25-08：網址保留排行代號（可分享）
   const S = await loadScreen();
   const avail = RANKS.filter(r => !r[4] || S);          // screen.json 不存在時，需要它的排行不出現
   const by0 = localStore('rank2', 'n+'), mkt = localStore('mkt', 'all'), span = localStore('rspan', '1');
@@ -869,10 +893,12 @@
           .map(([v, t]) => `<option value="${v}"${v === minTv ? ' selected' : ''}>${t}</option>`).join('')}</select>
         <select id="rankSel" class="sel">${RANK_GROUPS.map(([g, ids]) => { const rs = ids.map(id => avail.find(r => r[0] === id)).filter(Boolean);
           return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select></div>
+      <div class="rk-q">${['n+', 'f+', 't+', 'p+', 'p-', 'tv', 'm+'].filter(id => avail.some(r => r[0] === id)).map(id => `<button class="chip${id === by ? ' on' : ''}" data-rk="${id}">${RANKS.find(r => r[0] === id)[1]}</button>`).join('')}</div>
       <div class="card">${table}</div>
       <div class="muted small" style="margin-top:6px">${foot}</div></section>`;
   keyCol(rankKeyCol(by, field, src, byAmt));
-  $('#rankSel').addEventListener('change', e => { localStore('rank2', null, e.target.value); renderRank(); });
+  $('#view').querySelectorAll('[data-rk]').forEach(b => b.addEventListener('click', () => { location.hash = '#/rank/' + b.dataset.rk; }));   // D25-13 常用排行
+  $('#rankSel').addEventListener('change', e => { location.hash = '#/rank/' + e.target.value; });
   $('#tvSel').addEventListener('change', e => { localStore('rtv', null, e.target.value); renderRank(); });
   onSeg('rspanSeg', v => { localStore('rspan', null, v); renderRank(); });
   onSeg('mktSeg', v => { localStore('mkt', null, v); renderRank(); });
@@ -1215,7 +1241,7 @@
     onModeSeg();
     $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
       st = { ...scrParse(SCREEN_PRESETS.find(p => p[0] === b.dataset.ps)[2]), xd: 1, xn: 1, xc: 1, o: 'tv', ps: b.dataset.ps };
-      save(); draw();
+      open = false; save(); draw();                                        // 第 25 輪 D25-14：收合條件，結果緊接在預設鈕下方
     }));
     $('#view').querySelectorAll('[data-c]').forEach(el => el.addEventListener('change', () => {
       const c = SCREEN_CONDS.find(x => x.id === el.dataset.c);
@@ -1253,7 +1279,7 @@
   ['l1+', '借券增加', -1], ['l1-', '借券減少', 1], ['lb', '借券餘額', -1]];     // 第 12 輪 ETF-借券
 
 // ETF 列（tr[data-etf]）→ ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁。第 20 輪：ETF 列表與自選頁共用
-const onEtfRow = e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a')) location.hash = '#/stock/' + tr.dataset.etf; };
+const onEtfRow = e => { const tr = e.target.closest('tr[data-etf]'); if (tr && !e.target.closest('a,button')) location.hash = '#/stock/' + tr.dataset.etf; };
 
 function renderEtf() {
   const E = App.latest.etfs;
@@ -1271,6 +1297,7 @@
   $('#view').innerHTML = `<section class="sec">
       <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span>${App.latest.active_rank ? '<a class="pill hold" href="#/etf/active">主動 ETF 彙總</a>' : ''}<span class="sp"></span>
         ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
+        <input id="etfQ" class="sel" type="search" placeholder="篩選代號或名稱" aria-label="篩選 ETF" value="${esc(App.etfQ || '')}">
         <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
       <div class="card"><div class="tbl-wrap"><table class="tbl etf-tbl"><thead><tr>
         <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th></tr></thead><tbody>` +
@@ -1286,6 +1313,9 @@
   keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
+  const etfQ = () => { const q = (App.etfQ = $('#etfQ').value.trim()).toLowerCase();   // 第 25 輪 D25-15：只隱藏列，不重畫
+    $('#view').querySelectorAll('tr[data-etf]').forEach(tr => { tr.hidden = !!q && !(tr.dataset.etf.toLowerCase() + tr.cells[0].textContent.toLowerCase()).includes(q); }); };
+  $('#etfQ').addEventListener('input', etfQ); etfQ();
   // 第 15 輪 F15-2：整列 → ETF 個股頁；列內的「持股」小標（<a>）照舊連到持股頁
   $('#view').addEventListener('click', onEtfRow);
 }
@@ -1389,10 +1419,14 @@
   const list = [...App.watch].filter(c => S[c]).map(c => [c, S[c]]);
   const etfs = [...App.watch].filter(c => !S[c] && R[c]).map(c => [c, R[c]]);     // 第 20 輪 F20-1：自選的 ETF 另列一張表
   const stk = list.length || !etfs.length;                                         // 只有 ETF 時不顯示股票表與 1 日／5 日
+  const ev = list.filter(([, s]) => s.hl || s.dsp || s.ntc);                        // 第 25 輪 D25-09：自選股的近期新訊號、處置／注意
   $('#view').innerHTML = `<section class="sec">
+      ${App.watchUndo ? `<div class="flow-note">已從自選移除 ${esc(App.watchUndo.filter(c => !App.watch.has(c)).map(c => (S[c] || R[c])?.n || c).join('、'))}　<button class="chip" id="watchUndo">復原</button></div>` : ''}
       <div class="sec-h">${stk ? '<h2>自選</h2>' : '<h2>自選 ETF</h2>'}<span class="muted small">存在這個瀏覽器裡，換裝置不會同步${stk ? '' : '。當日行情；成交量為張、成交額為億元'}</span><span class="sp"></span>${stk ? spanSeg(span) : ''}</div>
-      ${stk ? `<div class="card">${list.length ? stockTable(list, span)
+      ${stk ? `<div class="card">${list.length ? stockTable(list, span, true)
         : '<div class="empty">還沒有自選股。打開任一檔個股或 ETF，按名稱旁的「☆ 加入自選」。</div>'}</div>` : ''}
+      ${ev.length ? `<div class="card w-ev"><div class="sec-h"><h2>近期新訊號、處置／注意</h2><span class="muted small">只描述發生了什麼，不代表之後的走勢</span></div>${ev.map(([c, s]) =>
+        `<a class="al-row" href="#/stock/${c}"><b>${esc(s.n)}</b>${alertBadge(s)}　${s.hl ? s.hl.filter(e => HL_KINDS[e[0]]).map(hlTag).join('') : ''}</a>`).join('')}</div>` : ''}
       ${etfs.length ? `${stk ? '<div class="sec-h" style="margin-top:12px"><h2>ETF</h2><span class="muted small">當日行情；成交量為張、成交額為億元</span></div>' : ''}
       <div class="card">${etfWatchTable(etfs)}</div>` : ''}</section>`;
   if (stk) onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
@@ -1402,7 +1436,7 @@
 // 第 20 輪 F20-1：自選頁的 ETF 表（ETF 列表的前 4 欄，資料為 latest.etfs.rows）
 function etfWatchTable(list) {
   return '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th></tr></thead><tbody>' +
-    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
+    list.map(([c, r]) => `<tr data-etf="${c}"><td class="nm"><button class="wx" data-unwatch="${c}" title="從自選移除" aria-label="從自選移除">✕</button><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
       <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td><td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>
       <td class="num">${fmt(r.v)}</td><td class="num">${fmt(r.tv, 2)}億</td></tr>`).join('') + '</tbody></table></div>';
 }
```

### A-d_stk `stock.js`

```diff
--- orig/site/stock.js	2026-11-14 11:08:44
+++ proj/site/stock.js	2026-11-14 23:34:21
@@ -52,12 +52,15 @@
   '上市 ETF：除息等價格調整日官方漲跌為 0（不比價），本站把「收盤 − 官方漲跌」和前一日收盤不同的日子標成「息?」（官方漲跌 0）或「調?」（漲跌不是 0，多為分割），只是推測，也可能是合併或資料更正，沒有配息金額。' +
   '上櫃 ETF：官方漲跌就是收盤減前一日收盤，除息日的漲跌含除息的跌幅，本站無法辨識除息日，不標示。'); };
 
-window.renderStock = async function (code) {
+// 第 25 輪 D25-05：產業鏈、概念股標籤只顯示前 2 個，其餘收在「+N」（點了展開）
+const tagFold = t => t.slice(0, 2).join('') + (t.length > 2 ? `<button class="pill more" id="tagMore">+${t.length - 2}</button><span class="tag-rest" hidden>${t.slice(2).join('')}</span>` : '');
+
+window.renderStock = async function (code, sub) {
   const E = !App.latest.stocks[code] && App.latest.etfs?.rows?.[code];   // 第 15 輪 F15-2：ETF 個股頁（頁首用 etfs.rows，資料 data/etfp/）
   const s = App.latest.stocks[code] || E || undefined;
   let data;
   try { data = await loadStock(code, E ? 'etfp' : 'stocks'); }
-  catch (e) { $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料</div>`; return; }
+  catch (e) { $('#view').innerHTML = `<div class="empty">找不到 ${esc(code)} 的資料。可用上方搜尋框查代號或名稱，或<a href="#/today" style="color:var(--blue)">回今日</a></div>`; return; }
   const P = data.prices, n = P.d.length;
   const last = n - 1;
   // 最新一天沒成交（開高低收為 --）時，改顯示最後成交日的收盤，不算漲跌
@@ -89,6 +92,9 @@
   const watching = App.watch.has(code);
   // 第 22 輪 F22-12：這檔的近期新訊號（文字共用 app.js 的 hlTag；舊 app.js 沒有 hlTag 或不認得的種類不列；ETF 沒有 hl）
   const HL = typeof hlTag === 'function' ? (s?.hl || []).filter(e => HL_KINDS[e[0]]) : [];
+  // 第 25 輪 D25-08：網址有分頁就用網址的；換一檔股票時從「走勢」開始
+  if (STOCK_TABS.some(t => t[0] === sub)) localStore('stockTab', null, sub); else if (App.stockCode !== code) localStore('stockTab', null, 'k');
+  App.stockCode = code;
   const tab0 = pageTab('stockTab', STOCK_TABS), tab = E && tab0 === 'fund' ? 'k' : tab0;   // 分頁：走勢／籌碼／基本面（頁首永遠顯示）；第 15 輪：ETF 沒有基本面
   const fd = md(App.latest.flow_date);
   // 第 15 輪：ETF 的 52 週高低由原始價計算（和匯出端 h52 同樣取資料日往前 365 天）
@@ -133,8 +139,8 @@
     <section class="sec card">
       <div class="s-head">
         <div>
-          <div><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>
-          <div><span class="s-price num ${cls(change)}">${pfmt(close)}</span>
+          <div class="s-nm"><span class="s-name">${esc(data.name)}</span><span class="s-code">${code}</span></div>
+          <div class="s-px"><span class="s-price num ${cls(change)}">${pfmt(close)}</span>
             ${noTrade ? '<span class="s-chg flat">無成交</span>' : gxLast ? '<span class="s-chg flat" title="官方漲跌為 0、收盤和前一日收盤不同：推測是除息等價格調整">不比價（推測價格調整）</span>'
               : `<span class="s-chg num ${cls(change)}">${change > 0 ? '▲' : change < 0 ? '▼' : ''} ${pfmt(Math.abs(change ?? 0))} (${sgn(pct)}%)</span>`}
             ${!noTrade && s?.rel ? `<span class="muted small">相對 ${md(s.rel)} 收盤（前一交易日無成交）</span>` : ''}</div>
@@ -144,8 +150,8 @@
               : `<span class="pill al-n" title="${esc(`${md(a.a)} 公布注意交易資訊\n${a.r || ''}`)}">注意</span>`).join('')}
             <span class="pill">${data.market === 'TWSE' ? '上市' : '上櫃'}</span><span class="pill">${E ? 'ETF' : esc(data.industry)}</span>
             ${E && App.latest.holdings?.[code] ? `<a class="pill hold" href="#/etf/${code}">持股 →</a>` : ''}
-            ${(data.chains || []).map(([chain, seg, subs]) => `<span class="pill chain" title="${esc(chain)} › ${esc(seg)}${subs.length ? '：' + esc(subs.join('、')) : ''}">${esc(chain)} › ${esc(subs.length ? subs.slice(0, 2).join('、') + (subs.length > 2 ? '…' : '') : seg)}</span>`).join('')}
-            ${(data.concepts || []).map(c => `<span class="pill">${esc(c)}</span>`).join('')}
+            ${tagFold([...(data.chains || []).map(([chain, seg, subs]) => `<span class="pill chain" title="${esc(chain)} › ${esc(seg)}${subs.length ? '：' + esc(subs.join('、')) : ''}">${esc(chain)} › ${esc(subs.length ? subs.slice(0, 2).join('、') + (subs.length > 2 ? '…' : '') : seg)}</span>`),
+            ...(data.concepts || []).map(c => `<span class="pill">${esc(c)}</span>`)])}
             <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
             ${E && E.m === 'TPEx' ? '<span class="muted small">上櫃 ETF 的漲跌可能含除息，本站無法辨識除息日</span>' : ''}
           </div>
@@ -157,10 +163,11 @@
     </section>
 
     ${pageTabsHTML('stockTabSeg', E ? ETF_TABS : STOCK_TABS, tab)}
-    <section class="sec metrics">
+    <section class="sec metrics${tab === 'k' ? ' kv' : ''}">
       ${(tab === 'k' ? [
          [hlFrom ? '區間高' : '52週高', pfmt(E ? eHL[0] : s?.h52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
-         [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'], ...mtCards]
+         [hlFrom ? '區間低' : '52週低', pfmt(E ? eHL[1] : s?.l52), '', hlFrom ? hlSub + (E ? '，原始價' : '，還原') : E ? '原始價' : '還原權值'],
+         ...E ? [] : [['本益比', fmt(fund.pe, 2), '', fundSub(fund.pe)], ['殖利率', fund.dy != null ? fmt(fund.dy, 2) + '%' : '--', '', fundSub(fund.dy)], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd]], ...mtCards]
         : tab === 'chip' ? [...E ? [] : [['法人1日', yi(s?.n1), cls(s?.n1), subs(fd, runTxt(s?.s, '買', '賣'))], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
          ['外資5日', yi(s?.f5), cls(s?.f5), subs('至 ' + fd, runTxt(s?.fs, '買', '賣'))], ['投信5日', yi(s?.t5), cls(s?.t5), subs('至 ' + fd, runTxt(s?.ts, '買', '賣'))]], ...mgCards, ...slCards]
         : [['本益比', fmt(fund.pe, 2), '', subs(fundSub(fund.pe), valSub('pe', fund.pe))], ['股價淨值比', fmt(fund.pb, 2), '', subs(fundSub(fund.pb, false), valSub('pb', fund.pb))],
@@ -180,7 +187,7 @@
         ${segHTML('kSeg', [['日', '日'], ['週', '週'], ['月', '月']], mode)}
         ${E ? '' : segHTML('adjSeg', [['還原', '還原'], ['原始', '原始']], adjMode)}
         <button class="seg" id="latestBtn" style="padding:4px 12px;font-size:12px">回到最新</button>
-        <span class="sp"></span><span class="muted small">拖曳平移、滾輪縮放</span>
+        <span class="sp"></span><span class="muted small hint">拖曳平移、滾輪縮放</span>
       </div>
       ${E ? `<div class="muted small val-note">${ETF_NOTE(E.m)}</div>` : ''}
       <div class="kleg" id="kLegend"></div>
@@ -198,7 +205,8 @@
     ${data.pf ? perfHTML(data.pf, data.market, noTrade ? P.d[lt] : null) : ''}
     ${E ? '' : '<section class="sec card"><div class="sec-h"><h2 id="sigTitle">技術面訊號</h2></div><div id="sigBox"></div></section>'}`}`;
 
-  onSeg('stockTabSeg', v => { localStore('stockTab', null, v); window.disposeStockCharts(); window.renderStock(code); });
+  onSeg('stockTabSeg', v => { localStore('stockTab', null, v); history.replaceState(null, '', `#/stock/${code}/${v}`); window.disposeStockCharts(); window.renderStock(code); });
+  $('#tagMore')?.addEventListener('click', e => { $('#view .tag-rest').hidden = false; e.currentTarget.remove(); });
   $('#starBtn')?.addEventListener('click', () => {
     App.watch.has(code) ? App.watch.delete(code) : App.watch.add(code);
     saveWatch();
@@ -208,6 +216,8 @@
   });
   if (tab === 'fund') { renderRevenue(data.revenue); if (F) renderFin(F); }
   if (tab !== 'k') return;
+  // 第 25 輪 D25-05：關鍵數字列在寬螢幕併進頁首卡、手機放到 K 線卡下方，主圖進第一屏
+  if (matchMedia('(min-width:721px)').matches) $('#view .s-head').after($('#view .metrics.kv')); else $('#kC').closest('section').after($('#view .metrics.kv'));
   if (!E) $('#adjSeg').title = '還原：依除權息、減資、面額變更調整歷史價格（現金增資除權也依官方參考價調整），最新收盤不變。均線訊號與 52 週高低一律以還原價格計算';
   // 日／週／月與還原／原始切換都重畫；技術面訊號一律用還原價（P13）
   const draw = () => {
@@ -361,7 +371,7 @@
   const priceFmt = { type: 'custom', minMove: 0.01, formatter: pfmt };
   const mk = (id, timeVisible, logo = false) => LC.createChart($('#' + id), {
     autoSize: true,
-    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 10, attributionLogo: logo },
+    layout: { background: { type: 'solid', color: 'transparent' }, textColor: text2, fontSize: 11, attributionLogo: logo },
     grid: { vertLines: { color: grid }, horzLines: { color: grid } },
     crosshair: { mode: LC.CrosshairMode.Normal },
     rightPriceScale: { borderVisible: false, minimumWidth: 76 },   // 各圖刻度同寬，K 棒才會上下對齊
@@ -446,7 +456,7 @@
   } else {
     const macdFmt = { type: 'price', precision: 2, minMove: 0.01 };
     const hSer = mc.addHistogramSeries({ priceFormat: macdFmt, priceLineVisible: false, lastValueVisible: false });
-    hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: v >= 0 ? 'rgba(55,138,221,.65)' : 'rgba(213,90,48,.65)' })));
+    hSer.setData(hist.map((v, i) => ({ time: T[i], value: v, color: (v >= 0 ? UP : DN) + 'a6' })));
     oSer = line(mc, dif, '#378ADD', macdFmt);
     line(mc, dea, '#EF9F27', macdFmt);
     oVal = i => dif[i];
```

### A-d_html `index.html`

```diff
--- orig/site/index.html	2026-11-14 11:08:44
+++ proj/site/index.html	2026-11-14 23:40:04
@@ -6,11 +6,11 @@
 <title>台股資金流</title>
 <meta name="description" content="台股類股與概念股的三大法人資金流向、個股 K 線與籌碼">
 <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='11' cy='19' r='8' fill='%23d64545'/><circle cx='22' cy='12' r='6' fill='%23e8a33d'/><circle cx='23' cy='24' r='4' fill='%2330a46c'/></svg>">
-<link rel="stylesheet" href="app.css?v=52d5a6c7">
+<link rel="stylesheet" href="app.css?v=5ccf0a57">
 <script src="https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js" defer></script>
 <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js" defer></script>
-<script src="app.js?v=b1f56347" defer></script>
-<script src="stock.js?v=a3b1a5c6" defer></script>
+<script src="app.js?v=b059864d" defer></script>
+<script src="stock.js?v=25304c73" defer></script>
 </head>
 <body>
 <header class="top">
```
