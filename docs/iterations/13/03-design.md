# 第 13 輪｜System Analyst：設計規格

- 依據：`13/01-analyst.md`、`13/02-pm.md`（F13-1～F13-5）。
- 作法：
  - 在 scratchpad 建立兩份副本：`orig` 是目前程式，`proj` 是本設計。兩份都**不含 `.env`**，`site/data` 用符號連結指向專案的匯出檔（唯讀）。
  - 兩份在 8001 同時提供（`/orig/site/`、`/proj/site/`）。用同一支量測腳本（附錄 B）在 375 × 812 與 1024 × 768 下量測改前、改後。
  - 另外把整個專案（排除 `.env`、`_archive`、`site/data`、`logs`、`.git`）複製一份，蓋上 `proj` 的檔案，跑 `test_iter01`～`13`。
- 本文所有數字都來自這次量測（資料日 2026-11-06）。附錄 A 是完整 diff，PG 可以直接套用（已用 `patch -p1 --dry-run` 確認可乾淨套用到目前專案）。
- 本輪 **0 個外部請求、0 個資料庫寫入、不跑 `export`、不改 `twstock/`**。量測前後 `site/data` 的雜湊相同。

---

## 〇、變更總覽

| 編號 | 檔案 | 內容 | 行數（＋／−） |
|---|---|---|---|
| F13-1 | `site/app.css` | 第一欄 `sticky`；ETF 表手機把「持股」標籤換行 | 3／0 |
| F13-1 | `site/app.js` | `keyCol()`、`STOCK_KEYS`、`rankKeyCol()`；排行、選股、ETF 三處呼叫；ETF 表加 `etf-tbl` | 約 14／1 |
| F13-2 | `site/stock.js` | 走勢分頁拿掉開盤、最高、最低、昨收、成交量五張卡；頁首加一行「開高低昨收量」；週轉率副標 | 約 4／5 |
| F13-3 | `site/app.js`、`site/stock.js`、`site/app.css` | `noteHTML()`；今日頁 4 處、個股頁 4 處改用它；「單位數 1 日」收進 `<details>`；CSS 6 行 | 約 20／13 |
| F13-4 | `site/app.js` | 家數分組 `nowrap`；共同說明只出一次；`indexCard(x, name, full)` | 約 6／4 |
| F13-5 | `site/app.js`、`site/app.css` | 錢流前 5 與「顯示全部」；期貨表手機隱藏兩欄；自選空白頁；頁首 `nowrap` | 約 10／4 |
| 測試 | `tests/test_iter13.py`（新） | 5 個測試 | 107 |
| 文件 | `README.md` | `site/` 一列加一句 | 1／1 |

- 合計：`app.js` ＋36／−18、`stock.js` ＋7／−7、`app.css` ＋14、README ＋1／−1、測試 107 行。
- 程式＋CSS＋README 約 **58 行新增**。PM 估計約 109 行；PM 估得較多，是因為原本預期 ETF 表與法人排行要逐表改欄序，實際用一個共用的 DOM 搬欄函式就解決了（第一節）。

### 建議實作順序

同 PM 第四節「相依性」：
1. `site/data` 雜湊與基線副本。
2. 套用附錄 A。
3. `node --check`；`test_iter01`～`13`。
4. 8001 預覽與量測（附錄 B）。
5. 再算一次雜湊。

---

## 一、F13-1 表格固定第一欄＋排序欄移到第 2 欄

### 1-1 固定第一欄（`app.css`）

```css
.tbl th:first-child,.tbl td:first-child{position:sticky;left:0;z-index:1;background:var(--card);box-shadow:inset -1px 0 0 var(--border)}
@media (max-width:520px){.etf-tbl td.nm .pill{display:table;margin:2px 0 0}}
```

- 所有 `.tbl` 都套用。背景用 `var(--card)`，深淺色主題自動跟著換。
- hover：既有 `.tbl tr[data-code]:hover td{background:var(--card2)}` 的權重（0,2,2）高於新規則（0,2,1），所以第一欄 hover 時也會變色，不會透出底下的欄。
- `box-shadow` 是第一欄右側的分隔線，捲動時看得出邊界。
- ETF 表的名稱欄在手機最寬（例如「主動中信台灣收益 00406A 上市 持股尚未支援」約 300 px），排序欄塞不進第一屏。所以只有 ETF 表把「持股」標籤換到第二行。
  - 只影響有標籤的列。
  - ETF 頁長從 17.0 屏變成 17.8 屏，見第八節。

### 1-2 排序欄移到第 2 欄（`app.js`）

- 決定 **一律前移**（不分手機、桌面）：
  - 桌面本來就看得到全部欄，排序欄在名稱旁邊反而更清楚。
  - 不用處理視窗寬度改變時重排。
- 做法：表格照舊產生，畫好之後用 `keyCol(i)` 把第 i 欄整欄搬到第 2 欄（`insertBefore`）。
  - `th` 上的 `data-k`、事件監聽都跟著元素移動，所以選股表點欄名排序不受影響。
  - `colspan` 的「無」列只有一格，`cells.length > i` 不成立，會略過。

```js
function keyCol(i) {
  const t = $('#view table.tbl');
  if (t && i > 1) for (const tr of t.rows) if (tr.cells.length > i) tr.insertBefore(tr.cells[i], tr.cells[1]);
}
const STOCK_KEYS = ['', 'c', 'p', 'tv', 'f', 't', 'd', 'n', 'fs', 'ts', 's'];
const rankKeyCol = (by, field, src, byAmt) => !src ? STOCK_KEYS.indexOf(/^[ftdn][15]$/.test(field) ? field[0] : field)
  : src === 'm' ? { m: byAmt ? 6 : 5, mr: 7, s: 8, sr: 9, mu: 10 }[by.replace(/[+-]$/, '')]
  : src === 'l' ? { 'l+': 6, lp: 7 }[by] : 4;
```

| 頁面 | 表格 | 排序欄位置來源 |
|---|---|---|
| 排行（法人、價量、連買） | `stockTable` | `STOCK_KEYS`：外資 1／5 日 → 4，法人 → 7，連買 → 8～10，成交額 → 3，漲跌 → 2 |
| 排行（融資融券） | `marginTable` | 融資張數 5、估算金額 6、增加率 7、融券 8、券資比 9、使用率 10 |
| 排行（借券） | `sblTable` | 借券賣出增加（依估算金額）6、占股本 7 |
| 排行（`screen.json` 類） | `screenTable` | 固定 4（`RANK_COLS[by][0]` 就是排序欄） |
| 選股 | `screenTable` | `th.sort[data-k=目前排序]` 的 `cellIndex` |
| ETF | ETF 表 | `{ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }` |
| 自選 | `stockTable` | 不搬（沒有排序） |

- **欄序與對照表綁在一起**：`test_iter13` 逐字檢查四張表的表頭字串，並用 node 對每個 `RANKS` 算出位置和上表比對。以後有人改欄序，測試會失敗，提醒要一起改 `rankKeyCol`。

### 1-3 量測（375 px，排序欄是否完整在可視範圍內）

| 頁面 | 改前 | 改後 |
|---|---|---|
| `#/rank` 週轉率、成交額、法人、外資、外資連、量比、殖利率 | 全部看不到 | ✅ |
| `#/rank` 漲跌 | ✅（本來就在第 3 欄） | ✅ |
| `#/rank` 融資（金額、張數）、增加率、融券、券資比、使用率 | 全部看不到 | ✅ |
| `#/rank` 借券賣出增加、占股本 | 看不到 | ✅ |
| `#/rank` 營收年增 | 看不到 | ⚠️ 差 17 px（第八節） |
| `#/rank/screen`（預設依成交額） | 看不到 | ✅ |
| `#/etf` 成交額、漲幅、融資、融券、借券增減、借券餘額 | 6 種都看不到 | ✅ 6／6 |

- 選股：點「漲跌」→ 由大到小 9.96、7.34、3.98…；再點一次 → 由小到大 −9.98、−9.94…；點「成交額」→ 263.3、171.5、129.9…。排序欄都在第 2 欄。
- 深色主題（`#/rank` 週轉率）與淺色主題（`#/etf` 捲到右側）截圖確認：第一欄背景不透明、分隔線可見。

---

## 二、F13-2 個股走勢分頁

- 走勢分頁的卡改成 **4 張**：52 週高（或區間高）、52 週低（或區間低）、市值、週轉率（`...mtCards]` 不變）。
- 開、高、低、**昨收**、量改成頁首（股價標題卡）內的一行：`開 2,020　高 2,195　低 2,020　昨收 2,240　量 110,715 張`。
  - 每一組都 `nowrap`，高紅、低綠。
  - 數值和本輪前的卡片相同，來源都是 `P.o[last]` 等。所以不受 K 線週線、月線與游標位置影響（PM 的限制）。
  - 頁首在三個分頁都會顯示這一行。籌碼、基本面分頁約多 20 px，換來任何分頁都看得到當天行情。
- **昨收也移出卡片**（和 PM「保留昨收卡」不同，見第十三節）：只拿掉 4 張時，2408 的 K 線頂端是 818 px，仍超過 812。
- 週轉率卡副標：資料日和收盤日相同時，不再重複寫日期（`11/06，`），讓副標在手機上一行放得下。不同日時照舊寫日期。

| 量測 | 改前 | 改後 |
|---|---|---|
| 375 px `#/stock/2330` K 線 `canvas` 頂端 | 1,009 px | **789 px** |
| 375 px `#/stock/2408` | 1,038 px | **800 px** |
| 1024 px `#/stock/2330` | 610 px | 502 px；4 張卡排成 **1 列** |
| 上市未滿 52 週（1623） | 區間高／區間低 | 不變 |

---

## 三、F13-3 說明收合

### 3-1 共用函式與樣式

```js
const noteHTML = (short, full) => `<details class="note"><summary>${short}<i>說明</i></summary><div>${full}</div></details>`;
```

- `summary` 是可見的短句，後面接藍色「說明 ▾」。展開後顯示 `full`，箭頭變 ▴。
- `full` 是本輪前的原文，**逐字相同**，只是移進 `<details>`。
- `details`／`summary` 是原生元素，可以用 Tab、Enter 操作。

### 3-2 逐處定稿

| 位置 | 可見短句（不收合） | 收合的原文 |
|---|---|---|
| 今日・信用交易卡 | 維持率為本站自算、非官方；140% 是經驗值，不是官方門檻 | 「維持率 = Σ(…)…」與「參考（經驗值，非官方門檻）…」兩段（合成一個 `details`） |
| 今日・信用交易卡 ETF 借券 | ETF 借券賣出多為造市、套利與避險，不等於看空 | 原文（含「例如價格高於淨值時…」）。**分析師清單外追加**，見第十三節 |
| 今日・估值卡 一年位置 | 股票中位數，不是加權指數本益比；只是位置，不是買賣訊號 | 「一年位置 = 近 N 個交易日…」151 字 |
| 今日・估值卡 加權本益比 | 大型股影響大（最大的 台積電 占上市 43.2%）；本站計算，不是證交所公布的數字 | 「加權本益比 = 市值合計 ÷ …」 |
| 今日・主動 ETF（今日頁與彙總頁共用 `unitsLine`） | 「單位數增加 = 淨申購…不全是看好」維持原樣可見 | 「單位數 1 日：00981A +1.50%…」那一長串數字，收進「各檔單位數 1 日 展開」 |
| 個股・基本面 一年位置 | 獲利大增時本益比會落到一年低點，位置低不代表股價便宜 | 「一年位置 = 近 242 個交易日中…」 |
| 個股・季報卡 | 單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異 | 「單季 = 本季累計 − …」191 字 |
| 個股・月營收（今年 vs 去年） | 柱：2026 年（藍）、2025 年（灰）同月營收 | 原文 |
| 個股・主動 ETF 持有 | 張數增減包含申購贖回的影響，不一定代表看好 | 原文（含權重說明） |

- 防誤讀句全部在可見短句內：
  - 不等於看空 ×2。
  - 不是買賣訊號。
  - 不是證交所公布的數字。
  - 不是官方門檻。
  - 不一定代表看好。
  - 位置低不代表股價便宜。
  - 「借券賣出含避險、套利，不等於看空」那一行本來就短，維持原樣。
- 「估算」都在卡片標題或欄名（例如「億，估算」），不受影響。
- 沒動的段落（80 字以下或不在清單內）：
  - 市場寬度分母（98 字，在總覽分頁）。
  - 個股「近 4 季 EPS 一年前…」（finUp，88 字，本身就是防誤讀句）。
  - 借券占股本說明（77 字，含「不等於看空」）。
  - 主動 ETF「只含統一、群益…」（67 字）。

### 3-3 量測（375 px，附錄 B 的定義）

- 說明文字 = 可見的 `.s:not(.num)`、`.muted.small`、`.note summary`、`.val-note`，去掉巢狀重複。
- 比例 = 說明文字字數 ÷ `#view` 可見文字字數，不計空白。收合中的 `<details>` 內容不算可見。

| 頁面 | 改前（屏／說明比例） | 改後 |
|---|---|---|
| 今日・信用估值 | 1.92／**49.0%** | **1.65／31.6%** |
| 今日・總覽 | 1.49／37.0% | 1.45／33.8% |
| 今日・法人資金 | 4.00／18.1% | 3.70／19.5% |
| 個股・籌碼 | 2.08／43.2% | 2.07／41.6% |
| 個股・基本面 | 3.02／54.9% | 2.85／40.7% |

- 信用估值分頁沒有達到 PM 的 ≤ 20%、≤ 1.6 屏（第十三節說明與建議的驗收值）。
- 剩下可見的「說明」主要是：
  - 防誤讀短句（必須可見）。
  - 兩張迷你圖的圖說（「上市股票融資增減（張），近 20 日…」「上市本益比中位數，近 60 個交易日…」）。
  - 季報進度一行。
  - 「看排行 →」「ETF 頁 →」連結。
- 這套定義下，改前是 49.0%，和分析師當時的 46% 定義略不同。本表前後用同一支腳本量測。

---

## 四、F13-4 今日頁指數與成交額卡

1. 成交額卡的家數一行改成 4 個 `<span class="nw">`（漲（停）、跌（停）、平、未成交）。375 px 下不再出現「未成／交」「跌／733」。
2. 「家數為官方（股票）；成交額為網站自算，不含 ETF」移出卡片，放在兩張卡下方。用 `muted small span-all`，和第 12 輪三大法人下方的共同說明同一個寫法。
   - 只要上市或上櫃任一有官方家數就顯示。
   - 沒有官方家數的那張卡仍顯示原本的「一般股票，不含 ETF；官方家數尚未取得，顯示自算」。
3. `indexCard(x, name, full = true)`：非總覽分頁傳 `false`，省略迷你圖下方「近 60 個交易日 −x%」一行。
   - 每張卡約省 18 px。
   - 法人資金分頁從 4.00 屏降到 3.70 屏；這一項加上錢流收合，合計省約 240 px。

---

## 五、F13-5 小修

| # | 做法 | 結果 |
|---|---|---|
| 1 | 錢流流入、流出預設各 **5** 個。超過 5 個時，在「錢從哪裡流出」標題右側放 `chip`「顯示全部」，點了變 8 個，按鈕變「只顯示前 5」。狀態放在 `App.flowAll`（這次瀏覽有效，不存 localStorage）。切換「今天／近 5 日」時**維持**目前的狀態 | 5／5 → 8／8；切換天數後仍 8／8；再按回 5／5 |
| 2 | 手機（≤ 520 px）隱藏期貨表第 6、7 欄（約當大台、它的增減），並把儲存格左右留白改成 5 px。下方的圖就是「約當大台淨未平倉」，資訊沒有消失 | 表寬 455 → 309 px（= 可視寬），不用橫向捲動；桌面不變 |
| 3 | 「打開任一檔個股，按名稱旁的『☆ 加入自選』。」 | — |
| 4 | `#dateBar` 改用 `innerHTML`，三段各自 `nowrap`（日期都經過 `esc`）。「（依資料寫入時間）」後綴保留在第三段 | 375 px 分成「資料日…　法人資料…」與「更新於 2026-11-06 22:49」兩行，不在日期中間斷行；桌面一行 |

---

## 六、量測腳本與結果總表

- 腳本在附錄 B：`__m13(排序欄名稱)` 量測單頁，`__drive13()` 依序切換頁面與 localStorage 偏好，回傳全部結果。
- 只讀畫面，只改 `tw.*` 偏好，跑完會把偏好設回預設。
- 用法：在 8001 開好網站，把附錄 B 的兩段程式貼進瀏覽器主控台（或 javascript tool）執行 `await __drive13()`。整輪約 60 秒；工具有逾時限制時，用 `.then(r => window.__r = r)` 背景執行，再分次讀 `window.__r`。

| 量測（375 × 812） | 改前 | 改後 | PM 驗收 |
|---|---|---|---|
| 排序欄可見（17 種排行＋選股＋ETF 6 種） | 1／24 | 23／24（營收年增差 17 px） | 列出的頁面全部 ✅ |
| 個股 K 線頂端 2330／2408 | 1,009／1,038 | 789／800 | < 812 ✅ |
| 信用估值 說明比例／頁長 | 49.0%／1.92 | 31.6%／1.65 | ≤ 20%／≤ 1.6 ❌（第十三節） |
| 期貨表寬／可視寬 | 455／309 | 309／309 | 不需橫向捲動 ✅ |
| 整頁水平捲動 | 無 | 無 | ✅ |
| 主控台錯誤 | 只有 `favicon.ico` 404 | 同左 | ✅ |

---

## 七、QA 清單

1. `python3 -I tests/test_iter13.py` 與 `test_iter01`～`12` 全部通過。另外拿本輪前的 `app.js` 跑 `test_iter13` 應該失敗（反證）。
2. 附錄 B 的 `__drive13()` 在 375 × 812 跑一次，和第六節的表比對。
3. 選股：點兩個欄名（漲跌、成交額），各點兩次，確認排序方向與排序欄位置。
4. 深色、淺色各截一張：`#/rank`（週轉率）捲到最右；`#/etf` 捲到中間。
5. `<details>` 逐字：
   - 本輪前的原文已列在 `test_iter13.FULL`。
   - 再用瀏覽器點開今日頁信用估值分頁的 4 個「說明」，比對文字和本輪前畫面相同。
   - 第 12 輪的原文可從 git `HEAD` 版本的 `app.js` 取得。
6. 鍵盤：Tab 到「說明」、按 Enter 能展開與收合。
7. 個股：
   - 2330、2408 的頁首行數值，等於 `stocks/{code}.json` 的 `prices` 最後一天（o、h、l、v）與前一天收盤。
   - 1623 顯示「區間高／低」。
   - 2867 的市值、週轉率是 `--`。
8. 錢流：
   - 預設 5／5。
   - 「顯示全部」後 8／8。
   - 切換「今天／近 5 日」後狀態維持。
   - 流入、流出都不超過 5 個時，不出現按鈕。可用 mock 或 fixture 確認。
9. 官方家數：
   - 把 `latest.json` 副本的 `breadth.*.o` 拿掉（mock），兩張卡顯示自算家數與原說明，共同說明不出現。
   - 只拿掉其中一個市場時，共同說明仍出現一次。
10. 桌面 1024 px：個股 4 張卡一列；今日頁、排行、ETF 外觀沒有錯位。
11. `site/data` 雜湊前後相同。

---

## 八、邊界情況

| 情況 | 行為 |
|---|---|
| 營收年增排行（`ry`） | 排序欄已在第 2 欄，但有些股票的值帶月份標記（例如「+25.30%（8 月）」），欄寬 143 px，375 px 下右緣超出 17 px。不在 PM 的驗收清單；名稱欄已固定，往右滑一點即可。若要完全放進去，要改營收欄的格式，列入待辦 |
| ETF 頁變長 | 有「持股」標籤的列變兩行，17.0 → 17.8 屏。換來 6 種排序都在第一屏看得到 |
| 沒有成交的股票 | 頁首那一行用和原本卡片相同的值（`pfmt(null)` 顯示 `--`），行為不變 |
| `screen.json` 不存在 | 需要它的排行本來就不出現；`stockTable` 類排行照常搬欄 |
| 排行結果 0 筆 | 沒有表格，`keyCol` 不做事 |
| 錢流某邊為 0 個 | 原本的「沒有淨流入的板塊」照舊；按鈕只在任一邊超過 5 個時出現 |
| `details` 在信用交易卡（`.stat` 內） | 區塊元素，展開後卡片變高；左右並排（`g2`）時，另一張卡不受影響 |
| 主動 ETF 彙總頁 | 共用 `unitsLine`，「單位數 1 日」也收合，和今日頁一致 |

---

## 九、測試 `tests/test_iter13.py`（新檔，全文見附錄 A）

| 測試 | 內容 |
|---|---|
| `test_f13_1_sticky_and_key_column` | 固定欄 CSS；`keyCol` 與三處呼叫；四張表的表頭字串（鎖住欄序）；用 node 對每個 `RANKS`（1 日、5 日、融資金額／張數）算 `rankKeyCol`，和對照表比對 |
| `test_f13_2_stock_k_cards` | 走勢分頁清單沒有開盤、成交量、昨收；`...mtCards]`、區間高低保留；頁首行有昨收與量；週轉率副標條件 |
| `test_f13_3_notes` | `noteHTML` 定義與 CSS；11 段原文逐字存在；8 個短句含 6 種防誤讀句；沒收合的兩句仍在 |
| `test_f13_4_index_cards` | 共同說明在 `app.js` 只出現 1 次；`nw`；`indexCard` 的 `full`；自算說明保留 |
| `test_f13_5_small_fixes` | `flowAll`；期貨表 CSS；自選文字（`app.js` 不再有「右上角」）；`dateBar` |

- 結果：`proj` 上 `test_iter01`～`13` 全部通過。本輪前的程式跑 `test_iter13` 會失敗（反證）。
- 舊測試的既有斷言**沒有修改**。`test_iter12` 的 `"...mtCards]"`、分頁與左右版面斷言都仍成立。

---

## 十、README 修改清單（`__main__.py` 不用改）

- 第 20 行 `site/` 一列的最後加一句「第 13 輪：…」，內容是固定欄、排序欄、說明收合、頁首開高低、錢流前 5。全文見附錄 A。

---

## 十一、PG 實作步驟

1. 記錄 `site/data` 的雜湊：
   ```bash
   find site/data -type f | sort | xargs shasum | shasum
   ```
   複製 `site/app.js`、`stock.js`、`app.css` 到 `logs/iter13_before/`，給 QA 比對原文。
2. `patch -p1 --dry-run < r13.diff`，再正式套用（附錄 A 存成檔案）。
3. `node --check site/app.js site/stock.js`。
4. `test_iter01`～`13`。
5. 8001 提供 `site/`。375 × 812 跑附錄 B，與第六節比對，結果寫進 `04-dev.md`。另外截桌面一張。
6. 關閉 8001。
7. 再算一次雜湊，和步驟 1 比對。若中間使用者有收集資料，在 `04-dev.md` 註明。
- **不執行** `export`、`collect` 等任何寫入。

---

## 十二、延後順序（沿用 PM）

1. F13-5 #1（錢流收合）。
2. F13-3 個股頁的 4 處。
- 實際工作量遠低於估計，預期不需要延後。

---

## 十三、對 PM 範圍的調整（不改 02-pm.md）

1. **F13-3 信用估值分頁的驗收值**：
   - PM 訂 ≤ 20%、≤ 1.6 屏；設計做到 31.6%、1.65 屏（改前 49.0%、1.92 屏）。
   - 要再降，只能收合迷你圖圖說、季報進度、防誤讀短句。前者是圖表的必要標示，後者是 PM 規定必須可見。
   - **建議驗收改為：說明比例 ≤ 35% 且比改前少 15 個百分點以上；頁長 ≤ 1.7 屏。**
   - 需要使用者或 PM 確認。不同意時，可以再收合季報進度一行（約降到 27%）。
2. **F13-2 昨收也移出卡片**：PM 寫「卡片留昨收」，但只留昨收時 2408 的 K 線頂端是 818 px（> 812）。昨收改放在頁首那一行，資訊沒有減少。
3. **F13-2 頁首行在三個分頁都顯示**：放在頁首卡，不只走勢分頁。籌碼、基本面分頁約多 20 px。
4. **F13-5 #2 期貨表**：PM 寫隱藏「約當大台」欄。但它後面的「增減」是約當大台的增減，只隱藏一欄會讓表頭出現兩個意義不同的「增減」。所以兩欄一起隱藏，並縮小留白（只在手機）。
5. **F13-3 多收合一處**：ETF 借券說明（44 字，可見短句保留「不等於看空」）。這樣信用估值分頁才能從 33.1% 降到 31.6%。
6. **F13-2 週轉率卡副標**：資料日等於收盤日時不寫日期（第 12 輪文字的小調整），讓卡片一行放得下。
7. **F13-1 一律前移**（PM 交給 SA 決定）。
8. **工作量**：約 58 行，低於 PM 的 109 行（第〇節）。

---

## 十四、給 PG、QA 的提醒

- 本輪的 `site/data` 是 11/06 的資料。若 PG、QA 執行時使用者已收集新的一天，數字（例如 K 線頂端）可能差幾 px。原因是標籤數、股名長度會改變版面，所以驗收用 PM 的門檻，不用本文的精確值。
- `rankKeyCol` 的位置和表頭欄序綁在一起：以後任何一輪改這四張表的欄序，都要一起改它，`test_iter13` 會提醒。
- 埠 8001 測完關閉；不要碰 8000。不要動 `.env`、不要 commit、不要執行還原、不要安裝排程。

---

## 附錄 B：量測腳本（唯讀；PG、QA 共用）

```js
// 第 13 輪量測（唯讀）：頁長、說明比例、整頁水平捲動、表格排序欄是否在可視範圍、K 線頂端
window.__m13 = (keyHead) => {
  const H = innerHeight, W = innerWidth, view = document.querySelector('#view');
  const n = t => (t || '').replace(/\s/g, '').length;
  const sel = '.s:not(.num), .muted.small, .note summary, .val-note';
  const els = [...view.querySelectorAll(sel)].filter(e => e.getClientRects().length);
  const top = els.filter(e => !els.some(o => o !== e && o.contains(e)));
  const note = top.reduce((a, e) => a + n(e.innerText), 0), all = n(view.innerText);
  const r = { W, H, screens: +(document.documentElement.scrollHeight / H).toFixed(2), hscroll: document.documentElement.scrollWidth > W,
    noteChars: note, allChars: all, notePct: +(note / all * 100).toFixed(1) };
  const t = view.querySelector('table.tbl');
  if (t) { const wr = t.closest('.tbl-wrap').getBoundingClientRect(), ths = [...t.rows[0].cells];
    r.tbl = { w: t.scrollWidth, wrap: Math.round(wr.width), head: ths.map(c => c.innerText.trim()).slice(0, 4).join('|') };
    if (keyHead) { const th = ths.find(c => c.innerText.trim().startsWith(keyHead));
      r.tbl.key = th ? { idx: th.cellIndex, visible: th.getBoundingClientRect().right <= wr.right + 0.5 } : null; } }
  const cv = view.querySelector('canvas');
  if (cv) r.firstCanvasTop = Math.round(cv.getBoundingClientRect().top + scrollY);
  return r;
};

// 依序切換頁面並呼叫 __m13；回傳所有量測（唯讀，只改 localStorage 的 tw.* 偏好，最後設回預設）
window.__drive13 = async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const go = async (h, ms = 700) => { location.hash = h; await wait(ms); window.scrollTo(0, 0); };
  const set = (k, v) => localStorage.setItem('tw.' + k, v);
  const out = {};
  for (const t of ['ov', 'flow', 'credit', 'fut']) { set('todayTab', t); await go('#/x'); await go('#/today', 900); out['today.' + t] = __m13(); }
  for (const c of ['2330', '2408']) { set('stockTab', 'k'); await go('#/x'); await go('#/stock/' + c, 1500); out['stock.' + c + '.k'] = __m13(); }
  for (const t of ['chip', 'fund']) { set('stockTab', t); await go('#/x'); await go('#/stock/2330', 1500); out['stock.2330.' + t] = __m13(); }
  set('rspan', '1'); set('mkt', 'all'); set('rtv', '0.5');
  const R = [['to', '週轉率'], ['tv', '成交額'], ['p+', '漲跌'], ['n+', '法人1日'], ['f+', '外資1日'], ['fs', '外資連'], ['vr', '量比'], ['dy', '殖利率'], ['ry', '營收年增'],
    ['m+', '估算（億）'], ['mr', '增加率'], ['s+', '融券1日'], ['sr', '券資比'], ['mu', '使用率'], ['l+', '估算（億）'], ['lp', '占股本']];
  set('munit', 'amt');
  for (const [k, h] of R) { set('rank2', k); await go('#/x'); await go('#/rank', 900); out['rank.' + k] = __m13(h); }
  set('munit', 'lot'); set('rank2', 'm+'); await go('#/x'); await go('#/rank', 900); out['rank.m+lot'] = __m13('融資1日'); set('munit', 'amt');
  for (const [k, h] of [['tv', '成交額'], ['p+', '漲跌'], ['m1', '融資增減'], ['s1', '融券增減'], ['l1+', '借券增減'], ['lb', '借券餘額']]) {
    set('etfSort', k); await go('#/x'); await go('#/etf', 900); out['etf.' + k] = __m13(h); }
  await go('#/rank/screen', 1200); out['screen.default'] = __m13('成交額');
  await go('#/watch'); out['watch'] = __m13();
  set('rank2', 'n+'); set('etfSort', 'tv'); set('todayTab', 'ov'); set('stockTab', 'k');
  return out;
};
```

---

## 附錄 A：完整 diff（`diff -ruN orig proj`）

```diff
diff -ruN -x d orig/README.md proj/README.md
--- orig/README.md	2026-11-08 00:02:21
+++ proj/README.md	2026-11-08 00:15:29
@@ -17,7 +17,7 @@
 | `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
 | `twstock/export.py` | 匯出 `site/data/latest.json`、`screen.json`（條件選股與排行擴充用）、`stocks/{代號}.json`、`etfs/{代號}.json` |
 | `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
-| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」 |
+| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行（含條件選股、融資融券排行、借券排行）、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有、融資融券與借券賣出圖、借券指標卡、季報卡）。今日頁指數卡下方分「總覽／法人資金／信用估值／期貨」四頁，個股頁頁首下方分「走勢／籌碼／基本面」三頁，瀏覽器會記住上次選的分頁；個股「基本面」的月營收可切換「今年 vs 去年」（逐月對照去年同月與同期累計）和「近 36 個月」。第 13 輪：表格第一欄（名稱）固定，排行、選股、ETF 表的排序欄放在名稱後的第 2 欄，手機不用橫向捲動；較長的口徑說明預設收合，點「說明」展開（防誤讀的句子保持可見）；個股頁頁首列出當天開、高、低、昨收、量，「走勢」分頁只留 52 週高低、市值、週轉率四張卡；首頁「錢流去哪」預設各顯示 5 個產業，可按「顯示全部」 |
 | `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py`、`python3 tests/test_iter07.py`、`python3 tests/test_iter08.py`、`python3 tests/test_iter09.py`、`python3 tests/test_iter10.py` |
 | `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
 | `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
diff -ruN -x d orig/site/app.css proj/site/app.css
--- orig/site/app.css	2026-11-08 00:02:21
+++ proj/site/app.css	2026-11-08 00:12:23
@@ -227,3 +227,17 @@
 .scr-c input[type=number]{width:64px;padding:2px 6px;border:1px solid var(--border);border-radius:6px;background:var(--card2);color:var(--text);font-size:12px}
 .scr-n{font-size:11px;color:var(--text3)}
 .tbl th.sort{cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}
+/* 第 13 輪 F13-1：表格第一欄固定（橫向捲動時名稱不會捲走）；ETF 表在手機把「持股」標籤放到下一行，名稱欄才不會太寬 */
+.tbl th:first-child,.tbl td:first-child{position:sticky;left:0;z-index:1;background:var(--card);box-shadow:inset -1px 0 0 var(--border)}
+@media (max-width:520px){.etf-tbl td.nm .pill{display:table;margin:2px 0 0}}
+/* F13-3：說明收合（可見的一行短句＋「說明」展開完整文字） */
+.note summary{list-style:none;cursor:pointer;font-size:12px;color:var(--text2);margin-top:2px}
+.note summary::-webkit-details-marker{display:none}
+.note summary i{font-style:normal;color:var(--blue);white-space:nowrap;margin-left:6px}
+.note summary i::after{content:' ▾'}
+.note[open] summary i::after{content:' ▴'}
+.note>div{font-size:12px;color:var(--text2);margin-top:2px}
+/* F13-4、F13-5：不在詞中間斷行；手機隱藏期貨表的約當大台兩欄（下方圖表即為約當大台） */
+.nw{white-space:nowrap}
+.s-ohlc{margin-top:4px}
+@media (max-width:520px){.oi-tbl th:nth-child(n+6),.oi-tbl td:nth-child(n+6){display:none}.oi-tbl th,.oi-tbl td{padding:8px 5px}}
diff -ruN -x d orig/site/app.js proj/site/app.js
--- orig/site/app.js	2026-11-08 00:02:21
+++ proj/site/app.js	2026-11-08 00:12:23
@@ -126,6 +126,7 @@
   const sorted = [...groups].sort((a, b) => b[key] - a[key]);
   const inflow = sorted.filter(g => g[key] > 0).slice(0, 8);
   const outflow = sorted.filter(g => g[key] < 0).reverse().slice(0, 8);
+  const nFlow = App.flowAll ? 8 : 5, flowMore = inflow.length > 5 || outflow.length > 5;   // 第 13 輪 F13-5：預設各 5 個
   const maxAbs = Math.max(1, ...groups.map(g => Math.abs(g[key])));
   const stocks = Object.entries(L.stocks).filter(([, s]) => s.n1 != null);
   const topBuy = [...stocks].sort((a, b) => b[1].n1 - a[1].n1).slice(0, 10);
@@ -136,8 +137,7 @@
     return `<div class="card stat">
       <div class="l">${label}成交額</div>
       <div class="v num">${fmt(x.turnover)}<span class="small muted"> 億</span></div>
-      ${o ? `<div class="s num">漲 <span class="up">${fmt(o.up)}</span>（停 ${fmt(o.ul)}）　跌 <span class="dn">${fmt(o.dn)}</span>（停 ${fmt(o.dl)}）　平 <span class="flat">${fmt(o.fl)}</span>　未成交 ${fmt(o.nt)}</div>
-      <div class="s">家數為官方（股票）；成交額為網站自算，不含 ETF</div>`
+      ${o ? `<div class="s num"><span class="nw">漲 <span class="up">${fmt(o.up)}</span>（停 ${fmt(o.ul)}）</span>　<span class="nw">跌 <span class="dn">${fmt(o.dn)}</span>（停 ${fmt(o.dl)}）</span>　<span class="nw">平 <span class="flat">${fmt(o.fl)}</span></span>　<span class="nw">未成交 ${fmt(o.nt)}</span></div>`
       : `<div class="s num">漲 <span class="up">${x.up}</span>　跌 <span class="dn">${x.down}</span>　平 <span class="flat">${x.flat}</span> 家</div>
       <div class="s">一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}</div>`}
     </div>`; };
@@ -156,6 +156,7 @@
   const body = {
     ov: `<section class="sec grid g-stats g-mk">
       ${mk('TWSE', '上市')}${mk('TPEx', '上櫃')}
+      ${L.breadth?.TWSE?.o || L.breadth?.TPEx?.o ? '<div class="muted small span-all">家數為官方（股票）；成交額為網站自算，不含 ETF</div>' : ''}
       ${breadthCard(L)}
     </section>
 
@@ -172,11 +173,11 @@
     <section class="sec grid g2">
       <div class="card">
         <div class="sec-h"><h2>錢流去哪</h2><span class="muted small">估算，不含 ETF</span><span class="sp"></span>${segHTML('spanSeg', [['1', '今天'], ['5', '近 5 日']], span)}</div>
-        <div class="bars">${inflow.map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
+        <div class="bars">${inflow.slice(0, nFlow).map(g => bar(g, 'var(--up)')).join('') || '<div class="empty">沒有淨流入的板塊</div>'}</div>
       </div>
       <div class="card">
-        <div class="sec-h"><h2>錢從哪裡流出</h2></div>
-        <div class="bars">${outflow.map(g => bar(g, 'var(--dn)')).join('') || '<div class="empty">沒有淨流出的板塊</div>'}</div>
+        <div class="sec-h"><h2>錢從哪裡流出</h2><span class="sp"></span>${flowMore ? `<button class="chip" id="flowMore">${App.flowAll ? '只顯示前 5' : '顯示全部'}</button>` : ''}</div>
+        <div class="bars">${outflow.slice(0, nFlow).map(g => bar(g, 'var(--dn)')).join('') || '<div class="empty">沒有淨流出的板塊</div>'}</div>
       </div>
     </section>
 
@@ -189,13 +190,14 @@
     ${activeCard(L.active_rank)}`;
 
   $('#view').innerHTML = `
-    <section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數')}${indexCard(L.index?.TPEX, '櫃買指數')}</section>
+    <section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數', tab === 'ov')}${indexCard(L.index?.TPEX, '櫃買指數', tab === 'ov')}</section>
     ${pageTabsHTML('todayTabSeg', TODAY_TABS, tab)}
     ${body[tab]}`;
 
   onSeg('todayTabSeg', v => { localStore('todayTab', null, v); disposeFuturesChart(); renderToday(); });
   if ($('#grpSeg')) onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   if ($('#spanSeg')) onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
+  $('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });
   $('#view').addEventListener('click', onRowClick);
   if (tab === 'fut') { drawFutures(L.futures); drawOI(L.futures_oi); }
 }
@@ -236,7 +238,7 @@
     <polyline points="${pts}" fill="none" stroke="var(--${vals.at(-1) >= vals[0] ? 'up' : 'dn'})" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
 }
 
-function indexCard(x, name) {
+function indexCard(x, name, full = true) {   // full = false：省略迷你圖下方的區間漲跌（第 13 輪 F13-4，非總覽分頁）
   if (!x) return `<div class="card stat idx"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
   const stale = x.date < App.latest.date;
   return `<div class="card stat idx">
@@ -244,10 +246,13 @@
       <div class="v num ${cls(x.ch)}">${fmt(x.c, 2)}</div>
       <div class="s num ${cls(x.ch)}">${x.ch > 0 ? '▲' : x.ch < 0 ? '▼' : ''} ${fmt(Math.abs(x.ch ?? 0), 2)} (${sgn(x.p)}%)</div>
       ${spark(x.s)}
-      ${x.s.length >= 2 ? `<div class="s"><span class="${x.s.at(-1) >= x.s[0] ? 'up' : 'dn'}">${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`} ${sgn((x.s.at(-1) / x.s[0] - 1) * 100, 1)}%</span>${x.s.length < 60 ? `（${x.s.length} 個交易日）` : ''}</div>` : ''}
+      ${full && x.s.length >= 2 ? `<div class="s"><span class="${x.s.at(-1) >= x.s[0] ? 'up' : 'dn'}">${x.s.length >= 60 ? '近 60 個交易日' : `自 ${md(x.from)} 起`} ${sgn((x.s.at(-1) / x.s[0] - 1) * 100, 1)}%</span>${x.s.length < 60 ? `（${x.s.length} 個交易日）` : ''}</div>` : ''}
     </div>`;
 }
 
+// 第 13 輪 F13-3：說明收合。short = 可見的一行（防誤讀的句子放這裡）；full = 原本的完整說明（逐字保留，預設收合）
+const noteHTML = (short, full) => `<details class="note"><summary>${short}<i>說明</i></summary><div>${full}</div></details>`;
+
 // 迷你柱狀圖：正值紅（買超）、負值綠（賣超），零軸置中
 function minibars(vals) {
   if (!vals?.length) return '';
@@ -281,8 +286,8 @@
       ${E ? `<div class="s num">ETF 另計（不計入上方）：上市 ETF 融資 ${wan(E.mb)} ${lots(E.m1)}、融券 ${wan(E.sb)} ${lots(E.s1)}</div>` : ''}
       ${etfSblLine(L.sbl_etf)}
       ${T ? `${minibars(T.m20)}<div class="s">上市股票融資增減（張），近 ${T.m20.length} 日（${md(T.d20[0])}～${md(T.d20.at(-1))}）</div>` : ''}
-      <div class="s">維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
-      <div class="s">參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。</div>
+      ${noteHTML('維持率為本站自算、非官方；140% 是經驗值，不是官方門檻', `<div>維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」</div>
+      <div>參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。</div>`)}
     </div>`;
 }
 
@@ -303,7 +308,7 @@
   const wan = n => `<b title="${fmt(n)} 張">${fmt(n / 1e4, n >= 1e6 ? 0 : 1)}</b> 萬張`;
   const one = (x, name) => !x ? '' : `${name} ${wan(x.lb)} <span class="${cls(x.l1)}">${sgn(x.l1, 0)}</span>`;
   return `<div class="s num">ETF 借券賣出　${[one(B.TWSE, '上市'), one(B.TPEx, '上櫃')].filter(Boolean).join('　')}　<a class="muted small" href="#/etf">ETF 頁 →</a></div>
-      <div class="s">ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空</div>`;
+      ${noteHTML('ETF 借券賣出多為造市、套利與避險，不等於看空', 'ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空')}`;
 }
 
 // 市場寬度卡（A3＋A8）：全部為網站自算（還原收盤、股票、不含 ETF）；官方家數在成交額卡
@@ -334,7 +339,7 @@
       ${wpeLine(V)}
       ${spark(V.TWSE?.s)}${V.TWSE?.s?.length > 1 ? `<div class="s">上市本益比中位數，近 ${V.TWSE.s.length} 個交易日（${md(V.TWSE.sf)} 起）</div>` : ''}
       ${finLine(L.fin_progress)}
-      <div class="s">一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號</div>
+      ${noteHTML('股票中位數，不是加權指數本益比；只是位置，不是買賣訊號', `一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。中位數只計本益比、淨值比大於 0 的股票（上市 ${fmt(V.TWSE?.n)}、上櫃 ${fmt(V.TPEx?.n)} 檔），不是加權指數本益比；本益比用近 4 季 EPS，財報公布期間 EPS 變化也會改變位置；殖利率用去年股利。只是位置，不是買賣訊號`)}
     </div>`;
 }
 
@@ -346,7 +351,7 @@
   const one = (x, name) => !x ? '' : `${name} <b>${fmt(x.v, 2)}</b>（${pos(x)}）`;
   const big = T?.t ? `最大的 ${esc(App.latest.stocks?.[T.t[0]]?.n || T.t[0])} 占上市 ${fmt(T.t[1], 1)}%` : '';
   return `<div class="s num">加權本益比（市值加權）　${[one(T, '上市'), one(O, '上櫃')].filter(Boolean).join('　')}</div>
-      <div class="s">加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字</div>`;
+      ${noteHTML(`大型股影響大${big ? `（${big}）` : ''}；本站計算，不是證交所公布的數字`, `加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}`;
 }
 
 // 第 10 輪 B5：季報公布進度（資料日在季報收集期間、當季已有資料時才有 fin_progress）
@@ -791,6 +796,7 @@
           return rs.length ? `<optgroup label="${g}">${rs.map(r => `<option value="${r[0]}"${r[0] === by ? ' selected' : ''}>${r[1]}</option>`).join('')}</optgroup>` : ''; }).join('')}</select></div>
       <div class="card">${table}</div>
       <div class="muted small" style="margin-top:6px">${foot}</div></section>`;
+  keyCol(rankKeyCol(by, field, src, byAmt));
   $('#rankSel').addEventListener('change', e => { localStore('rank2', null, e.target.value); renderRank(); });
   $('#tvSel').addEventListener('change', e => { localStore('rtv', null, e.target.value); renderRank(); });
   onSeg('rspanSeg', v => { localStore('rspan', null, v); renderRank(); });
@@ -894,6 +900,16 @@
   lb: ['借券餘額', x => x.lb, v => fmt(v)], l5: ['借券5日', x => x.l5, v => sgn(v, 0)], lp: ['借券占股本', x => x.lp, v => fmt(v, 2) + '%'],
 };
 const CAP_TAG = '<i class="al al-c" title="90 天內有除權、減資或面額變更，官方本益比、殖利率可能尚未調整">股本變動</i>';
+// 第 13 輪 F13-1：把第 i 欄（排序欄）移到第 2 欄（名稱之後），手機不用橫向捲動就看得到；整欄移動，th 的 data-k 跟著走
+function keyCol(i) {
+  const t = $('#view table.tbl');
+  if (t && i > 1) for (const tr of t.rows) if (tr.cells.length > i) tr.insertBefore(tr.cells[i], tr.cells[1]);
+}
+// 各排行表的排序欄位置（stockTable、marginTable、sblTable 的欄序；screenTable 的排序欄固定在第 5 欄 = 4）
+const STOCK_KEYS = ['', 'c', 'p', 'tv', 'f', 't', 'd', 'n', 'fs', 'ts', 's'];
+const rankKeyCol = (by, field, src, byAmt) => !src ? STOCK_KEYS.indexOf(/^[ftdn][15]$/.test(field) ? field[0] : field)
+  : src === 'm' ? { m: byAmt ? 6 : 5, mr: 7, s: 8, sr: 9, mu: 10 }[by.replace(/[+-]$/, '')]
+  : src === 'l' ? { 'l+': 6, lp: 7 }[by] : 4;
 // 固定欄（股票｜收盤｜漲跌｜成交額）＋ cols；o = {sort: 目前排序欄, cap: 是否標示股本變動}；sort 有值時欄名可點排序
 function screenTable(list, cols, o = {}) {
   const head = k => { const c = SCR_COLS[k], M = revMonth(), Fq = finQ();
@@ -1057,6 +1073,7 @@
       <div class="card">${hits.length ? screenTable(hits.slice(0, 100), cols, { sort: o, cap: conds.some(c => c.val) })
         : '<div class="empty">沒有同時符合所有條件的股票。參考各條件的「單獨」檔數，放寬最少的那一個。</div>'}</div>
       <div class="muted small" style="margin-top:6px">篩選結果只是條件的機械比對，不是投資建議。報酬、乖離、均線、新高新低都用還原價格（除權息、減資、面額變更不會造成跳動）；量比 = 今日成交額 ÷ 前 20 個交易日平均（無成交日以 0 計），不受面額變更影響。法人金額為張數 × 收盤估算，不含 ETF；投信買超會受主動 ETF 申購影響（申購的資金會被動買進股票，個股頁「主動 ETF 持有」卡列出已收主動 ETF 占投信買超的張數）。本益比、殖利率、淨值比為官方值，90 天內有除權、減資或面額變更的股票官方值可能尚未調整，預設排除。營收條件以各股最新公布的月份判斷：每月 1～10 日是公布期間，已公布的公司當天就換成新月份，各股月份不同（營收欄會標出和欄名不同的月份）。季報條件以各股最新一季判斷：單季 EPS 由累計相減，去年同季虧損時不計算年增，金融業沒有毛利率；財報公布期間各股季別不同（欄位會標出和欄名不同的季別）。融資融券為張；融資增加率、券資比只計入融資 1,000 張以上的股票。</div></section>`;
+    keyCol($(`#view th.sort[data-k="${o}"]`)?.cellIndex);
     const changed = () => { delete st.ps; save(); draw(); };
     onModeSeg();
     $('#view').querySelectorAll('[data-ps]').forEach(b => b.addEventListener('click', () => {
@@ -1115,7 +1132,7 @@
       <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span>${App.latest.active_rank ? '<a class="pill hold" href="#/etf/active">主動 ETF 彙總</a>' : ''}<span class="sp"></span>
         ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
         <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
-      <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
+      <div class="card"><div class="tbl-wrap"><table class="tbl etf-tbl"><thead><tr>
         <th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th></tr></thead><tbody>` +
       list.map(([c, r]) => `<tr${App.latest.holdings?.[c] ? ` data-etf="${c}"` : ''}><td class="nm"><b>${esc(r.n)}</b><span>${c} ${r.m === 'TWSE' ? '上市' : '上櫃'}</span>${holdTag(c)}</td>
         <td class="num ${cls(r.ch)}">${pfmt(r.c)}</td>
@@ -1126,6 +1143,7 @@
         <td class="num">${r.lb == null ? '--' : fmt(r.lb)}</td>${lots(r.l1)}</tr>`).join('') +
       `</tbody></table></div></div>
       <div class="muted small" style="margin-top:6px">共 ${list.length} 檔。成交量為張、成交額為億元；融資融券為張，增減 = 今日餘額 − 前日餘額，「--」表示不在信用交易清單。借券為借券賣出（張，資料晚上 8 點半以後更新），多為造市、套利與避險，不等於看空。ETF 不計入首頁家數、成交額、類股資金流、排行、自選與股票口徑的融資融券。</div></section>`;
+  keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);
   $('#etfSel').addEventListener('change', e => { localStore('etfSort', null, e.target.value); renderEtf(); });
   onSeg('etfMktSeg', v => { localStore('etfMkt', null, v); renderEtf(); });
   $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr) location.hash = '#/etf/' + tr.dataset.etf; });
@@ -1150,7 +1168,7 @@
     .map(([c, h]) => `<a href="#/etf/${c}">${c}</a> <span class="${cls(h.u1)}">${h.u1 == null ? '--' : sgn(h.u1) + '%'}</span>`).join('、');
   const cur = H.filter(([, h]) => h.d === top), other = H.filter(([, h]) => h.d !== top);
   const od = [...new Set(other.map(([, h]) => md(h.d)))].join('、');
-  return `<div class="small num" style="margin-top:4px">單位數 1 日：${part(cur)}${other.length ? `；跨境（${od}）：${part(other)}` : ''}</div>
+  return `<details class="note"><summary>各檔單位數 1 日<i>展開</i></summary><div class="small num" style="margin-top:4px">單位數 1 日：${part(cur)}${other.length ? `；跨境（${od}）：${part(other)}` : ''}</div></details>
     <div class="muted small">單位數增加 = 淨申購。申購的資金會由經理人買進股票，所以多檔單位數同時增加的日子，「合計加碼」會偏多，不全是看好。</div>`;
 }
 
@@ -1230,7 +1248,7 @@
   $('#view').innerHTML = `<section class="sec">
       <div class="sec-h"><h2>自選股</h2><span class="muted small">存在這個瀏覽器裡，換裝置不會同步</span><span class="sp"></span>${spanSeg(span)}</div>
       <div class="card">${list.length ? stockTable(list, span)
-        : '<div class="empty">還沒有自選股。打開任一檔個股，按右上角「☆ 加入自選」。</div>'}</div></section>`;
+        : '<div class="empty">還沒有自選股。打開任一檔個股，按名稱旁的「☆ 加入自選」。</div>'}</div></section>`;
   onSeg('rspanSeg', v => { localStore('rspan', null, v); renderWatch(); });
   $('#view').addEventListener('click', onRowClick);
 }
@@ -1266,8 +1284,8 @@
 }
 function renderStatus() {
   const L = App.latest, when = (L.updated_at || '').slice(0, 16).replace('T', ' ');
-  $('#dateBar').textContent = `資料日 ${L.date}　法人資料 ${L.flow_date}　更新於 ${when}` +
-    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '');
+  $('#dateBar').innerHTML = `<span class="nw">資料日 ${esc(L.date)}</span>　<span class="nw">法人資料 ${esc(L.flow_date)}</span>　<span class="nw">更新於 ${esc(when)}` +
+    (L.status?.collected_src === 'db' ? '（依資料寫入時間）' : '') + '</span>';   // 第 13 輪 F13-5：每段不在中間斷行
   const lines = freshLines(L, App.now()).map(x => `<div>${esc(x)}</div>`);
   if (App.newDate) lines.push(`<div>網站資料已更新（資料日 ${md(App.newDate)}）<button id="reloadBtn">重新整理</button></div>`);
   const bar = $('#freshBar');
diff -ruN -x d orig/site/stock.js proj/site/stock.js
--- orig/site/stock.js	2026-11-08 00:02:21
+++ proj/site/stock.js	2026-11-08 00:12:23
@@ -68,7 +68,7 @@
   // 第 12 輪 B11：市值、週轉率（目前股數）
   const MT = data.mt, mcTxt = v => v >= 1e4 ? fmt(v / 1e4, 2) + ' 兆' : fmt(v, v >= 100 ? 0 : 1) + ' 億';
   const mtCards = [['市值', MT?.mc == null ? '--' : mcTxt(MT.mc), '', MT ? '收盤 × 目前發行股數' : '沒有發行股數資料'],
-    ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${md(MT.d)}，成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
+    ['週轉率', MT?.to == null ? '--' : fmt(MT.to, 2) + '%', '', MT ? `${MT.d !== P.d[last] ? md(MT.d) + '，' : ''}成交股數 ÷ 目前發行股數` : '沒有發行股數資料']];
   const slCards = !SL ? [] : [['借券賣出餘額', fmt(SL.lb) + ' 張', '', `1日 ${sgn(SL.l1, 0)}　5日 ${SL.l5 == null ? '--' : sgn(SL.l5, 0)}`],
     ['借券占股本', SL.lp == null ? '--' : fmt(SL.lp, 2) + '%', '', (SL.lx == null ? '' : `融券的 ${fmt(SL.lx, 1)} 倍　`) + '資料 ' + md(SL.d)]];
 
@@ -86,7 +86,7 @@
         <td class="num">${fmt(a.l)}</td><td class="num">${fmt(a.w, 2)}%</td>
         <td class="num ${cls(a.d1)}">${a.d1 == null ? '--' : sgn(a.d1, 0)}</td><td class="num ${cls(a.d5)}">${a.d5 == null ? '--' : sgn(a.d5, 0)}</td>
         <td class="num">${md(a.d)}</td></tr>`).join('') +
-      '</tbody></table></div><div class="muted small" style="margin-top:6px">張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。</div></section>');
+      '</tbody></table></div><div class="muted small" style="margin-top:6px">' + noteHTML('張數增減包含申購贖回的影響，不一定代表看好', '張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。') + '</div></section>');
 
   $('#view').innerHTML = `
     <section class="sec card">
@@ -106,6 +106,7 @@
             ${data.concepts.map(c => `<span class="pill">${esc(c)}</span>`).join('')}
             <span class="muted small">${noTrade ? `${P.d[last]} 無成交，顯示 ${P.d[lt]} 收盤` : `${P.d[last]} 收盤`}</span>
           </div>
+          <div class="s-ohlc small num muted"><span class="nw">開 <b>${pfmt(P.o[last])}</b></span>　<span class="nw">高 <b class="up">${pfmt(P.h[last])}</b></span>　<span class="nw">低 <b class="dn">${pfmt(P.l[last])}</b></span>　<span class="nw">昨收 <b>${pfmt(prev)}</b></span>　<span class="nw">量 <b>${fmt(P.v[last])}</b> 張</span></div>
         </div>
         <button class="star ${watching ? 'on' : ''}" id="starBtn">${watching ? '★ 已加入自選' : '☆ 加入自選'}</button>
       </div>
@@ -113,8 +114,7 @@
 
     ${pageTabsHTML('stockTabSeg', STOCK_TABS, tab)}
     <section class="sec metrics">
-      ${(tab === 'k' ? [['開盤', pfmt(P.o[last])], ['最高', pfmt(P.h[last]), 'up'], ['最低', pfmt(P.l[last]), 'dn'], ['昨收', pfmt(prev)],
-         ['成交量', fmt(P.v[last]) + ' 張'],
+      ${(tab === 'k' ? [
          [hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlFrom ? hlSub + '，還原' : '還原權值'],
          [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlFrom ? hlSub + '，還原' : '還原權值'], ...mtCards]
         : tab === 'chip' ? [['法人1日', yi(s?.n1), cls(s?.n1), fd], ['法人5日', yi(s?.n5), cls(s?.n5), '至 ' + fd],
@@ -124,7 +124,7 @@
         .map(([l, v, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c || ''}" style="font-size:16px">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`).join('')}
     </section>
     ${tab === 'chip' ? `${SL ? `<div class="muted small val-note">借券賣出包含避險、套利（例如 ETF、權證、可轉債避險），不等於看空，只能當作空方部位的上限。占股本以目前發行股數計算。借券資料晚上 8 點半以後才更新。</div>` : ''}
-    ${acHTML}` : tab === 'fund' ? `${VAL ? `<div class="muted small val-note">一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}</div>` : ''}
+    ${acHTML}` : tab === 'fund' ? `${VAL ? `<div class="muted small val-note">${noteHTML('獲利大增時本益比會落到一年低點，位置低不代表股價便宜', `一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例（資料 ${md(VAL.d)}）。本益比 = 股價 ÷ 近 4 季 EPS，位置也反映獲利變化：獲利下降時本益比會升高；獲利大增時本益比（淨值比也可能）會落到一年低點，例如景氣循環股在獲利高峰，不代表股價便宜。${F ? '請對照下方季報卡的近 4 季 EPS 與一年前比較。' : ''}`)}</div>` : ''}
     ${finUp ? `<div class="small val-note fin-note">近 4 季 EPS 一年前 ${fmt(F.e4p, 2)} 元 → 現在 ${fmt(F.e4, 2)} 元（${F.e4p <= 0 ? '轉盈' : fmt(F.e4 / F.e4p, 1) + ' 倍'}）：本益比會因獲利增加而下降，位置低不代表股價便宜；請看下方季報卡的單季 EPS 是否已經轉弱。</div>` : ''}
     <section class="sec grid ${F ? 'g2' : 'g-one'}">
       <div class="card"><div class="sec-h"><h2>月營收</h2><span class="sp"></span><span id="revSegBox"></span></div><div id="revBox"></div></div>
@@ -470,7 +470,7 @@
   $('#finBox').innerHTML = `<div class="metrics">${stats.map(([l, x, c, sub]) => `<div class="card stat"><div class="l">${l}</div><div class="v num ${c}" style="font-size:16px">${x}</div><div class="s">${sub}</div></div>`).join('')}</div>
     <div class="ch-label">近 ${Q.length} 季單季 EPS（元）；紅／綠 = 比去年同季增加／減少，灰 = 無法比較（去年同季虧損或沒有資料）</div>
     <div class="fin-bars">${Q.map(bar).join('')}</div>
-    <div class="muted small" style="margin-top:6px">單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}</div>`;
+    <div class="muted small" style="margin-top:6px">${noteHTML('單季、近 4 季 EPS 由累計相減，可能和公司公告略有差異', `單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）；期中有增資或減資時，相減的 EPS 會和公司公告的單季 EPS 略有差異。近 4 季 EPS = 本季累計 + 去年全年 − 去年同季累計。官方本益比以最新股數計算，期間有增資的公司，近 4 季 EPS 會和「股價 ÷ 本益比」有差異。金融業沒有毛利率。${F.c.fs ? '' : '「本站收錄」日期只有每日收集時才記錄，補抓的季別不顯示。'}`)}</div>`;
 }
 
 function renderRevenue(rows) {
@@ -509,7 +509,7 @@
     <div class="tbl-wrap"><table class="tbl"><thead><tr><th>月份</th><th>${Y}（億）</th><th>${Y - 1}（億）</th><th>年增</th></tr></thead><tbody>` +
     months.slice().reverse().map(m => `<tr><td>${m} 月</td><td class="num">${cur(m) ? amt(cur(m)[2]) : '--'}</td><td class="num">${prev(m) ? amt(prev(m)[2]) : '--'}</td>${pc(cur(m)?.[4] ?? null)}</tr>`).join('') +
     `<tr><td><b>累計</b></td><td class="num"><b>${amt(sc)}</b></td><td class="num">${amt(sp)}</td>${pc(cy)}</tr></tbody></table></div>
-    <div class="muted small" style="margin-top:6px">柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年 ${M + 1 <= 12 ? `${M + 1}～12 月只有去年，供參考` : '全年對照'}。年增 = 今年該月 ÷ 去年同月 − 1；累計只算兩年都有資料的月份。</div>`;
+    <div class="muted small" style="margin-top:6px">${noteHTML(`柱：${Y} 年（藍）、${Y - 1} 年（灰）同月營收`, `柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年 ${M + 1 <= 12 ? `${M + 1}～12 月只有去年，供參考` : '全年對照'}。年增 = 今年該月 ÷ 去年同月 − 1；累計只算兩年都有資料的月份。`)}</div>`;
   if (!window.Plotly) { $('#revC').innerHTML = '<div class="empty">圖表元件載入失敗，請檢查網路後重新整理</div>'; return; }
   const x = Array.from({ length: 12 }, (_, i) => `${i + 1}月`), text2 = css('--text2'), grid = css('--border');
   const ys = y => x.map((_, i) => { const r = by.get(y * 100 + i + 1); return r ? r[2] / 1e5 : null; });
diff -ruN -x d orig/tests/test_iter13.py proj/tests/test_iter13.py
--- orig/tests/test_iter13.py	1970-01-01 08:00:00
+++ proj/tests/test_iter13.py	2026-11-08 00:15:16
@@ -0,0 +1,107 @@
+"""第 13 輪（純前端，原始碼檢查；不連網、不連資料庫）：
+F13-1 表格固定第一欄＋排序欄移到第 2 欄；F13-2 個股走勢分頁去除重複卡；F13-3 說明收合（完整文字逐字保留、防誤讀句可見）；
+F13-4 指數與成交額卡；F13-5 小修四項。"""
+import json, re, shutil, subprocess
+from pathlib import Path
+
+ROOT = Path(__file__).resolve().parents[1]
+APP = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
+STK = (ROOT / "site" / "stock.js").read_text(encoding="utf-8")
+CSS = (ROOT / "site" / "app.css").read_text(encoding="utf-8")
+
+
+def test_f13_1_sticky_and_key_column():
+    assert ".tbl th:first-child,.tbl td:first-child{position:sticky;left:0;" in CSS
+    assert "function keyCol(i)" in APP and "tr.insertBefore(tr.cells[i], tr.cells[1])" in APP
+    assert "keyCol(rankKeyCol(by, field, src, byAmt));" in APP
+    assert "keyCol($(`#view th.sort[data-k=\"${o}\"]`)?.cellIndex);" in APP
+    assert "keyCol({ tv: 4, p: 2, m1: 6, s1: 8, l1: 10, lb: 9 }[f]);" in APP and 'class="tbl etf-tbl"' in APP
+    # rankKeyCol 的位置依賴各表的欄序：欄序改了這裡要一起改
+    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>成交額</th><th>外資${lbl}</th><th>投信${lbl}</th><th>自營${lbl}</th><th>法人${lbl}</th>\n      <th>外資連</th><th>投信連</th><th>法人連</th>" in APP
+    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>融資餘額</th><th>融資${lbl}</th><th>估算（億）</th>${by === 'mr' ? '<th>增加率</th>' : ''}\n      <th>融券餘額</th><th>融券${lbl}</th><th>券資比</th><th>使用率</th>" in APP
+    assert "<th>股票</th><th>收盤</th><th>漲跌</th><th>5日漲跌</th><th>借券餘額</th><th>借券${lbl}</th><th>估算（億）</th><th>占股本</th>" in APP
+    assert "<th>ETF</th><th>收盤</th><th>漲跌</th><th>成交量</th><th>成交額</th><th>融資餘額</th><th>融資增減</th><th>融券餘額</th><th>融券增減</th><th>借券餘額</th><th>借券增減</th>" in APP
+    if not shutil.which("node"):
+        print("  （略過 node 部分：沒有 node）")
+        return
+    code = APP[APP.index("const STOCK_KEYS"):APP.index("// 固定欄（股票｜收盤｜漲跌｜成交額）")]
+    ranks = APP[APP.index("const RANKS = ["):APP.index("const RANK_GROUPS")]
+    script = code + "\n" + ranks + """
+const out = {};
+for (const [by, , f, , src] of RANKS) for (const span of ['1', '5']) for (const byAmt of [false, true]) {
+  if (byAmt && !(by === 'm+' || by === 'm-')) continue;
+  const field = (byAmt ? 'ma*' : f).replace('*', span);
+  out[`${by}|${span}|${byAmt}`] = rankKeyCol(by, field, src, byAmt);
+}
+console.log(JSON.stringify(out));"""
+    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
+    exp = {'n+': 7, 'f+': 4, 't+': 5, 'd+': 6, 'fs': 8, 'ts': 9, 's': 10, 'p+': 2, 'tv': 3, 'vr': 4, 'to': 4, 'dy': 4,
+           'm+': 5, 'mr': 7, 's+': 8, 'sr': 9, 'mu': 10, 'l+': 6, 'lp': 7}
+    for k, v in got.items():
+        by, span, amt = k.split("|")
+        assert v is not None and v >= 1, k
+        if by in exp:
+            assert v == (6 if amt == "true" else exp[by]), (k, v)
+
+
+def test_f13_2_stock_k_cards():
+    k = STK[STK.index("${(tab === 'k' ? ["):STK.index(": tab === 'chip' ?")]
+    assert "開盤" not in k and "成交量" not in k and "昨收" not in k and "...mtCards]" in k
+    assert "hlFrom ? '區間高' : '52週高'" in k and "hlFrom ? '區間低' : '52週低'" in k
+    assert '<div class="s-ohlc small num muted">' in STK and "昨收 <b>${pfmt(prev)}</b>" in STK and "量 <b>${fmt(P.v[last])}</b> 張" in STK
+    assert "MT.d !== P.d[last] ? md(MT.d) + '，' : ''" in STK
+
+
+# 第 12 輪的完整說明（逐字），本輪只移進 <details>
+FULL = [
+    (APP, "維持率 = Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，股票＋ETF，自算、非官方；涵蓋率不足 99% 時顯示「資料不足」"),
+    (APP, "參考（經驗值，非官方門檻）：大盤融資維持率跌到 140% 左右時，常伴隨融資斷頭賣壓。投資人整戶擔保維持率低於 130% 會被追繳，這是官方規定。"),
+    (APP, "一年位置 = 近 ${T.days} 個交易日（${T.from.replaceAll('-', '/')} 起）中，中位數小於或等於今天的天數比例。"),
+    (APP, "殖利率用去年股利。只是位置，不是買賣訊號`)}"),
+    (APP, "加權本益比 = 市值合計 ÷ Σ（市值 ÷ 本益比），大型股影響大${big ? `（${big}）` : ''}；中位數反映一般股票。本站以目前股數計算、不含虧損公司，不是證交所公布的數字`)}"),
+    (APP, "ETF 借券賣出多為造市、套利與避險（例如價格高於淨值時借券賣出，申購後還券），不等於看空')}"),
+    (APP, "單位數 1 日：${part(cur)}"),
+    (STK, "一年位置 = 近 ${App.latest.valuation?.TWSE?.days ?? 242} 個交易日中，官方值小於或等於今天的天數比例"),
+    (STK, "單季 = 本季累計 − 上一季累計（第 4 季 = 全年 − 前三季）"),
+    (STK, "柱：${Y} 年（藍）與 ${Y - 1} 年（灰）同月營收；去年"),
+    (STK, "張數增減包含申購贖回的影響：申購多的日子，經理人會用申購資金加碼，不一定代表看好（可對照持股頁的「單位數 1 日」）。權重為占該 ETF 淨資產 %，含股價漲跌影響。')"),
+]
+
+
+def test_f13_3_notes():
+    assert "const noteHTML = (short, full) => `<details class=\"note\"><summary>${short}<i>說明</i></summary><div>${full}</div></details>`;" in APP
+    assert ".note summary{" in CSS and ".note[open] summary i::after" in CSS
+    for src, s in FULL:
+        assert s in src, s[:30]
+    # 收合後仍可見的短句：防誤讀的意思要在 summary 內
+    shorts = re.findall(r"noteHTML\((['`])(.+?)\1,", APP + STK)
+    text = " ".join(s for _, s in shorts)
+    for must in ["不是買賣訊號", "不是證交所公布的數字", "不等於看空", "不是官方門檻", "不一定代表看好", "位置低不代表股價便宜"]:
+        assert must in text, must
+    assert len(shorts) == 8, len(shorts)          # 今日頁 4（維持率兩段合一、一年位置、加權本益比、ETF 借券）＋個股頁 4；單位數 1 日另用 <details>
+    # 沒有收合的防誤讀句
+    assert "借券賣出含避險、套利，不等於看空；晚上 8 點半以後才更新" in APP
+    assert "單位數增加 = 淨申購。申購的資金會由經理人買進股票，所以多檔單位數同時增加的日子，「合計加碼」會偏多，不全是看好。" in APP
+
+
+def test_f13_4_index_cards():
+    assert APP.count("家數為官方（股票）；成交額為網站自算，不含 ETF") == 1
+    assert '<span class="nw">未成交 ${fmt(o.nt)}</span>' in APP and ".nw{white-space:nowrap}" in CSS
+    assert "function indexCard(x, name, full = true)" in APP and "${full && x.s.length >= 2 ?" in APP
+    assert "indexCard(L.index?.TAIEX, '加權指數', tab === 'ov')" in APP
+    assert "一般股票，不含 ETF${L.breadth ? '；官方家數尚未取得，顯示自算' : ''}" in APP
+
+
+def test_f13_5_small_fixes():
+    assert "const nFlow = App.flowAll ? 8 : 5" in APP and "$('#flowMore')?.addEventListener('click', () => { App.flowAll = !App.flowAll; renderToday(); });" in APP
+    assert ".oi-tbl th:nth-child(n+6),.oi-tbl td:nth-child(n+6){display:none}" in CSS
+    assert "按名稱旁的「☆ 加入自選」" in APP and "右上角" not in APP
+    assert "$('#dateBar').innerHTML = `<span class=\"nw\">資料日 ${esc(L.date)}</span>" in APP and "（依資料寫入時間）" in APP
+
+
+if __name__ == "__main__":
+    for name, fn in list(globals().items()):
+        if name.startswith("test_") and callable(fn):
+            fn()
+            print(f"✅ {name}")
+    print("全部通過")
```
