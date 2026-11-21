# 第 41 輪｜SA：設計

- 撰寫日期：2026-11-21（週六）
- 依據：
  - `41/01-analyst.md`：R35～R39、範例 1～3。
  - `41/02-pm.md`：F41-1、F41-2，驗收 1～24；文末「使用者決定」：D91～D100 全部 A、PM 自行決定的七項照用、D95 = A（只改 `tests/test_iter39.py:344` 一行）。
- 做法：
  - scratchpad 建 `r41sa/base`、`r41sa/proj`（`rsync`，排除 `.git`、`.env`、`_backups`、`_archive`），在 `proj` 實作與寫測試。
  - 產出 `41/03-design.diff`（720 行，路徑前綴 `a/`、`b/`）。另把 `base` 複製成 `verify` 套用 diff，與 `proj` 逐檔比對相同；`verify` 內 `tests/test_iter*.py` 全部通過（含新的 `test_iter41`）。
  - 正式專案 `git apply --check docs/iterations/41/03-design.diff` 通過。
- 守則：
  - 資料庫 0 次、外部請求 0 次、`export` 0 次；沒有讀、印、複製 `.env`。
  - 瀏覽器只在 `verify` 用 8002 起 `serve` 量版面，看完已關閉（`lsof -i :8002` 無輸出；伺服器 404 只有 `favicon.ico`）；沒有碰 8000、8001。瀏覽器已恢復 desktop、淺色，分頁已關。
  - 正式專案只新增 `docs/iterations/41/03-design.md`、`03-design.diff`。

---

## 重點摘要

- 新分頁 `#/tools/ac`「平均成本（多筆合計）」：`tools.js` 新增 8 個函式（4 個純計算＋2 個小工具＋表單＋結果），`TL`、`TL_TABS`、`TL_VIEW` 各加一項，`tlLoad` 加 3 行。**被鎖雜湊的 11 個函式、`tlFeePref`、`tlCompound` 一字不改**；其他既有函式也不改（`test_iter41` 另把 23 個既有函式合併鎖一個雜湊）。
- 計算全部用整數：金額 `BigInt`（分），手續費、證交稅（元）每一份各自捨去；平均成交價、平均成本用 `⌊(2X + N) ÷ 2N⌋` 四捨五入到分。PM 範例 1～5（含 3'）每一格都相符；200 組隨機和 Python `Fraction` 參考實作、從平均成本下方 50 檔逐檔往上的暴力兩平解完全相同。
- **更正 PM 的浮點例子**：node 的 `(27410 / 400).toFixed(2)` 是 `68.53`（68.525 的浮點值略大於 68.525），不會出錯。會出錯的是 `1.005` 這類（`(1005 / 1000).toFixed(2)` = `1.00`）。反證「平均成本改用浮點四捨五入」改用 1.01 × 500＋1 × 500（平均 1.005 → 應為 1.01）擋下，範例 2 的 68.53 仍列入檢查。
- 增刪列不改 `tlDraw`：用既有 `data-g` 按鈕機制（`data-g="r"` 新增、`data-g="x"` 刪除），刪除在 `tlAcForm` 開頭處理。`tlDraw` 模板先呼叫表單函式、再呼叫結果函式，所以結果區用的是移動後的資料（測試以 node 模擬點擊驗證）。
- **D101（新決策，diff 已依 A 製作）**：5 個分頁在 375／320 寬放不下一行；`tlDraw` 每次整頁重畫，分頁列的橫捲位置會回到最左，選了「除權息」後看不到被選的分頁（驗收 16 做不到，且 `tlDraw` 被鎖）。建議 520px 以下把工具頁分頁列換成兩行（CSS 1 行，只作用在 `#toolTabSeg`）。
- 舊測試只改 `tests/test_iter39.py:344` 一行（D95）。新測試 `tests/test_iter41.py` 13 個、486 行。
- 行數：`tools.js` ＋110／−4、`app.js` ±1、`app.css` ＋3、`index.html` ±3；測試 ＋486（新）、±1（`test_iter39`）；文件 README ＋2、`docs/iterations/README.md` ＋1。

---

## 一、規則（沿用，不新增規則編號）

| 規則 | 內容 | 實作 |
|---|---|---|
| R35 | 總成本 = Σ 成交金額 ＋ Σ 買入手續費；平均成本 = 總成本 ÷ 總股數；平均成交價 = Σ 成交金額 ÷ 總股數 | `tlAvg` |
| R36、D93 | 股數拆成整股 `q − q mod 1000` 與零股 `q mod 1000`，股數 0 的那份不計 | `tlLot` |
| R1、R2、R37、D92 | 每份 `tlFee(價格 × 股數, 折扣千分之, 該份最低值)`；整股用 `m`、零股用 `mo` | `tlAvg`、`tlSell` |
| R38 | 全部出售也拆兩份；證交稅每份 `⌊金額（分）× 稅率萬分之 ÷ 10^6⌋`（同 `tlTrade` 的 `tax`），稅率 `tlTax(k, false, today).r` | `tlSell` |
| R39 | 未實現損益 = 以目前價格出售淨額 − 總成本；報酬率 = ÷ 總成本 | `tlAcOut` |

---

## 二、程式設計（`site/tools.js`）

### 2-1 狀態與接線

```js
const TL_TABS = [['dt', '交易成本'], ['ac', '平均成本'], ['cp', '複利'], ['pl', '股票質借'], ['dv', '除權息']];   // D94
TL.ac = { k: 's', r: '3', p0: '', n0: '', p1: '', n1: '', p2: '', n2: '', mo: '1', cur: '' }   // d、m 不放初值
TL_VIEW.ac = ['平均成本（多筆合計）', tlAcForm, tlAcOut]
```

- `tlDraw` 既有模板自動給 `tl-form tl-ac`、`tl-out tl-oac`、`TL_FOOT`＋「本站不提供投資建議。」。
- D97：`tlAcForm` 開頭 `if (st.d == null) Object.assign(st, { d: TL.dt.d, m: TL.dt.m });`。`renderTools` 已在 `tlDraw` 之前用 `tlFeePref` 讀好 `TL.dt`，所以第一次顯示時拿到的是 `tw.fee` 或交易成本頁目前的值。之後兩頁各自獨立；`tlDraw` 的 `localStore` 只在 `tab === 'dt'`，本頁修改不存。
- 檔頭第 1 行註解加「第 41 輪 #/tools/ac 平均成本」。

### 2-2 純計算函式（node 可直接呼叫；`o = { dz, m, mo, r }`）

| 函式 | 輸入 → 輸出 |
|---|---|
| `tlLot(q, m, mo)` | `[[整股股數, m], [零股股數, mo]]`，去掉股數 0 的那份 |
| `tlAvg(rows, o)` | `rows = [[筆, 價格分, 股數]]` → `{ fee: 每筆各份手續費, A, F, T, N, avg, cost }`；`A`、`T` 為 `BigInt`（分） |
| `tlSell(p, N, o)` | 全部 N 股以 p 出售 → `{ sa, f: [整股, 零股] 手續費, x: [整股, 零股] 證交稅, net }`；`sa`、`net` 為 `BigInt` |
| `tlAcBreak(B, o, e)` | `{ th, p0, p, k, net }`；找不到時 `p: null` |

- 精確度：
  - 價格經 `tlC` 為 < 10^14 分的整數，股數經 `tlNum` < 10^12；每份金額都用 `BigInt(p) * BigInt(q)` 算，Σ 也是 `BigInt`，所以合計、捨去、四捨五入、淨損益比較**在任何合法輸入下都精確**（不只 2^53 以內）。
  - 手續費、證交稅轉回 `Number`（元），超過 9 × 10^15 元才會失真；畫面上的 `Number(A) / 100` 只影響超大金額的顯示。
- 平均（D100）：`half = X => Number((2n * X + n) / (2n * n))`，`n = BigInt(N)`。
- 兩平可成交值：
  1. `c = ⌈T ÷ N⌉`（整數進位到分）；`u = tlTick(c, e)`；`p0 = c % u ? c + u − c % u : c`。
     - 級距邊界本身都是上一級距單位的倍數，所以進位後一定是可成交價。例：範例 4 平均成本 99.81 → 99.9（下一檔 100、再下一檔 100.5）。
  2. 從 `p0` 起逐檔 `tlNext`，第一個 `tlSell(p).net − T ≥ 0` 的價位；最多 2,000 檔（含 `p0`），`k` 從 0 起算。
  3. 低於平均成本的價位出售淨額一定小於總成本，所以起點不會漏掉答案。
  4. 不照抄 `tlBreak` 的迴圈（變數、終止條件都不同；`tlBreak` 是 `i <= 2000`）。
- 理論值 `th = T ÷ N ÷ (1 − 1425 × dz ÷ 10^9 − r ÷ 10^4)`（浮點，只顯示 2 位）。

### 2-3 結果（`tlAcOut(st, I, today)`）

- 列數 `tlAcN(st)`：`tlNum(st.r, 0)`，> 10 → 10，< 1 或不是整數 → 3。
- 驗證：依 PM 二之一表格的順序與逐字訊息。
  - 逐列：價格、股數都空白 → 略過；否則依序檢查價格（空白／不合法）、股數（空白／不合法）。
  - 全部空白 → 「請至少填一筆價格與股數」；之後檢查折扣、整股最低、零股最低、目前價格。
  - 折扣訊息用 PM 改字版，`DMSG` 全文仍只出現 1 次。
- 有訊息時：`tlMsg(msg) + 說明`，沒有結果表與明細。
- 結果表 15 行與 PM 表格逐字相同：
  - 第 8 行小字為「平均成本進位到 X，再上漲 k 檔」或「平均成本進位到 X 即打平」；找不到時寫「2,000 檔內仍未打平」。
  - 第 9 行在找到時才出現；第 10～15 行在目前價格有填時才出現。
  - 第 10 行在 `cur === tlC(String(I.c))` 時加「MM/DD 收盤，不是即時價」。
  - 第 12、13 行在整股、零股都有時加「整股 a＋零股 b」小字。
- 明細：`tlNote(['每筆明細'])`＋`.tbl-wrap` 包住的 `table.tbl`（筆、價格 `pfmt`、股數 `fmt`、手續費 `a＋b` 或單一數字），數字欄加 `num`。
  - 手續費用 `.map(v => fmt(v))`；不可寫 `.map(fmt)`，否則索引會被當成小數位。
- 說明（驗證失敗時也顯示）：PM 第 1～6 則逐字；第 1 則不合法的值寫 `--`；第 6 則只在有 `I.ex` 時出現。沒有寫零股提示全文 `ODD`。

### 2-4 表單與增刪列（`tlAcForm(st)`）

```
<div class="tl-segs">tlSeg('k', 股票／ETF／債券 ETF)</div>
<div class="tl-f tl-rows" data-g="x">
  <span></span><span>價格（元）</span><span>股數</span><span></span>            ← 欄名一次
  <span>1</span><input data-k="p0" inputmode="decimal" … aria-label="第 1 筆價格">
  <input data-k="n0" inputmode="numeric" … aria-label="第 1 筆股數">
  <button class="chip" data-v="0" aria-label="刪除第 1 筆">刪除</button>      ← 只剩 1 列時改成 <span></span>
  …
</div>
<div class="tl-segs" data-g="r"><button class="chip" data-v="{r+1}">＋ 新增一筆</button></div>   ← 10 列時不出現
tlIn('d', '手續費折扣（折）', …, '不打折 = 10') ＋ tlIn('m', '整股最低手續費（元）') ＋ tlIn('mo', '零股最低手續費（元）') ＋ tlIn('cur', '目前價格（元）', …, '選填')
```

- `tlDraw` 的 `click`：`b.closest('[data-g]')` 找最近的 `data-g`，按鈕 → `st[g] = data-v` → `tlDraw(tab)` 整頁重畫。
- `tlDraw` 的 `input`：`st[data-k] = value`，只重畫結果區，游標不跳。
- `tlDraw` 模板是 `` `…${form(st, I)}…${draw()}…` ``，表單先算、結果後算。`tlAcForm` 每次執行的步驟：
  1. 沒有 `d` 時取交易成本頁的值（D97）。
  2. `r = tlAcN(st)`；若有 `st.x`，而且 `r ≥ 2`、`0 ≤ x < r`：第 x＋1～r−1 列的 `p`、`n` 往前移一列，`r` 減 1。
  3. `delete st.x`（範圍外的刪除也一樣刪掉，不處理）。
  4. `st.r = String(r)`（`'11'` → `'10'`、`'0'`／`'abc'` → `'3'`）。
  5. 第 r～9 列的 `p`、`n` 一律設為空白。
     - 刪除後原最後一列被清掉；新增的列一定是空白，不會帶出被刪掉的值。
- `tlAcV(st, k)`：讀不到的欄位視為空白字串（`p3`～`p9` 需要時才有）。

### 2-5 `?c=` 帶入（`tlLoad`，只新增 3 行）

改前：

```js
  TL.code = code; TL.info = null;
  if (!code) return;
  …
  Object.assign(TL.pl, { p1: c, p2: '' });
  TL.cp.y = …
```

改後：

```js
  TL.code = code; TL.info = null;
  for (let i = 0; i < 10; i++) TL.ac['p' + i] = TL.ac['n' + i] = '';                   // 第 41 輪 F41-2：換代號清空平均成本各列與目前價格（D98 = A）
  Object.assign(TL.ac, { r: '3', cur: '' });
  if (!code) return;
  …
  Object.assign(TL.pl, { p1: c, p2: '' });
  Object.assign(TL.ac, { cur: c, k: E ? 'e' : 's' });                                // 第 41 輪：目前價格 = 最新收盤
  TL.cp.y = …
```

- `tlLoad` 只在代號改變時執行，所以：
  - 同代號切分頁、從個股頁回來：列內容保留。
  - 換代號、拿掉代號、代號找不到：列與目前價格清空。
- 不改 `TL.ac.d`、`m`、`mo`。其他四個分頁的帶入值不變（`test_iter34`、`38`、`39`、`40` 的帶入測試照過）。
- 沒有用 `??`、`?.`、`.at(`、`parseFloat(`。
- `Object.assign(TL.dv, o, { p: c, k: E ? 'e' : 's' });` 仍只出現 1 次（新行開頭是 `TL.ac`）。

### 2-6 與舊反證字串的比對（`count == 1`）

| 測試 | 字串 | 新程式 |
|---|---|---|
| `test_iter38` MUTANTS | `DMSG`、`ODD`、`tlRow(rev ? '兩平買價上限…`、`" fill="none" ${G[j][4]}`、`s += \`<polyline points=`、`fmt(o ? Math.round…`、`fin = …`、`  if (A) G.push(`、`[P].concat(R.map(x => x[1]))`、`!dt && n > 0 && n % 1000 && m === TL_RULES.minFee`、`out.push(\`${rd ? '下一交易日' : ''}漲停` | 都沒有複製（折扣訊息改字、不寫零股提示） |
| `test_iter39` MUTANTS | `return tw && !S ? num / den :`、`cash >= 20000n ?`、`Object.assign(TL.dv, o, { p: c, k: E ? 'e' : 's' });`、`y1: '', cost: '' }, h = [];` 等 15 組 | 沒有複製 |
| `test_iter40` JS_MUTANTS | `  if (n.sr) return [false,`、`  if (n.c == null) return [false,`、`ex: d.nx ? d.nx[0].d : (d.dv` 等 | 沒有複製 |
| `test_iter34` | `TOOLS.count("斷頭") == 1`、`"單筆金額" not in TOOLS`、`localStore` 鍵只有 `fee` | 維持 |
| `test_iter38` 其他 | `fill="` 只能是 `none`、不可有 `<text`／`--up`／`--dn`、`"0～10 折" not in src`、`tlCompound(` 3 次 | 維持 |

- 用詞：`tools.js` 全文（含註解）通過 `test_iter34` 詞表、`test_iter38` `ADVICE`，以及本輪不用詞（攤平、加碼、解套、回本、套牢、停損、停利、目標價、獲利了結）。新 CSS 行（含 `tl-`）也一起掃。

---

## 三、`site/app.js`（1 行）

```js
  if (tl && !['dt', 'ac', 'cp', 'pl', 'dv'].includes(tl[1])) history.replaceState(history.state, '', '#/tools/dt' + (tl[2] || ''));
```

## 四、`site/app.css`（新增 3 行，接在第 39 輪 `.tl-odv` 那行之後；第 366～370 行不動）

```css
.tl-f.tl-rows{grid-column:1/-1;display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1fr) auto;gap:6px 8px;align-items:center}   /* 第 41 輪：平均成本每列（列號、價格、股數、刪除） */
@media (max-width:520px){.tl-oac .tl-kv,.tl-oac .tl-kv tbody{display:block}.tl-oac .tl-kv tr{display:flex;flex-wrap:wrap;justify-content:space-between;column-gap:12px;border-bottom:1px solid var(--border)}.tl-oac .tl-kv th,.tl-oac .tl-kv td{border-bottom:0}.tl-oac .tl-kv td{flex:1 1 auto;white-space:nowrap}.tl-oac .tl-kv td .small{white-space:normal}}   /* 第 41 輪：平均成本結果表窄螢幕整列換行，小字可換行 */
@media (max-width:520px){#toolTabSeg{flex-wrap:wrap;border-radius:18px}}   /* 第 41 輪 D101：工具頁 5 個分頁在窄螢幕換成兩行（重畫後分頁列會捲回最左，後面的分頁看不到） */
```

- 多列區塊：
  - `.tl-f` 原本是直向 flex，`.tl-f.tl-rows` 覆寫成 4 欄 grid，並跨滿整個表單。
  - 輸入框沿用 `.tl-f input`（16px、寬 100%），欄名沿用 `.tl-f` 的 12px 灰字。
- 320 寬實測（`verify`，8002）：
  - 卡片內寬 256px；列號約 8～14px＋刪除鈕約 46px＋間距 24px，兩個輸入框各 **88px**（PM 要求 ≥ 80）。
  - 刪除鈕、新增鈕高度 34px；輸入框字級 16px。
- 第 8 行小字「平均成本進位到 2,505，再上漲 3 檔」約 200px，td 換到下一行後佔滿 256px；`.small{white-space:normal}` 讓更長的字串也能換行。
- 分頁列（D101）實測：
  - 改前 5 個分頁共 402px，320 寬列寬 288px。
  - 改後：320、375 寬都是兩行（交易成本／平均成本／複利、股票質借／除權息，高 82px），1024 寬一行（39px）。
- 版面驗收（`document.documentElement.scrollWidth === innerWidth`）：
  - 320（深色）：10 列全滿＋目前價格、買價 1,005 × 1,000（兩平 ≥ 1,000）、未實現損益為負、驗證訊息，都是 320。
  - 375（淺色）、1024（深色）：`ac`、`dt`、`dv` 三個分頁都等於視窗寬。

## 五、`site/index.html`

- `app.css?v=d039dc67`、`app.js?v=e571fb7b`、`tools.js?v=05638786`（修改後檔案 sha1 前 8 碼）。
- `stock.js?v=00d41238` 不變。

---

## 六、測試 `tests/test_iter41.py`（13 個，486 行）

| 測試 | 內容 | 驗收 |
|---|---|---|
| `test_examples`（`check_examples`） | 範例 1～5、3' 逐格比對（含小字、明細手續費、明細欄位）；範例 5 沒有第 10～15 行 | 1、7、8 |
| `test_split` | 1,500 → `20＋7`；2,000 → `28`；500 → `7`；只有零股的出售沒有「整股＋零股」小字 | 3 |
| `test_random_fraction`（`check_random`） | 200 組（seed 41；1～10 列，整股／零股／混合，6 種折扣、4 種整股最低、3 種零股最低、3 種商品別，半數有目前價格）和 Python `Fraction` 參考實作比對：買入手續費、平均成交價、平均成本、可成交兩平（含小字的起點與檔數）、以此價出售淨損益、出售金額、未實現損益；理論值、報酬率誤差 ≤ 0.0051；兩平用「平均成本下方 50 檔、對齊升降單位後逐檔往上」的暴力解 | 2、4、15 |
| `test_half`（`check_half`） | 1.01 × 500＋1 × 500 → 平均 1.01（浮點 `toFixed` 得 1.00）；範例 2 的 68.53；價格 3 位小數擋下 | 2 |
| `test_validation` | 20 種錯誤輸入逐字訊息、沒有表格；同一列兩則；中間空白列的明細「筆」是 1、3；折扣空白顯示 `--` | 5、6 |
| `test_tax_and_notes` | 股票 300、ETF 100、債券 ETF 0；2027-01-01 債券 ETF 警示；說明 1～6 逐字 | 13、14 |
| `test_rows`（`check_rows`） | node 模擬 `tlDraw` 點擊：預設 3 列、加到 10 列鈕消失、`r` 為 `'11'`／`'0'`／`'abc'`；刪第 1 列後往前移、`p2`／`n2` 空白、`x` 不存在、結果區用移動後的資料；再新增是空白；範圍外刪除忽略；只剩 1 列沒有刪除鈕 | 9 |
| `test_fee_init_not_saved` | `TL.dt` 6 折、30 元 → 本頁初值；改本頁不呼叫 `localStore`、不改 `TL.dt`；分頁列 5 個的 HTML 與順序；標籤、class、頁尾 | 10、12、14 |
| `test_load`（`check_load`） | `?c=2330`：`cur`、`k`、其他分頁帶入不變、「11/20 收盤，不是即時價」、改價後消失、預告日「12/11 除權息，參考價另計」；同代號切分頁保留；換到 ETF、拿掉代號、找不到代號時清空 | 11 |
| `test_route` | `#/tools/ac`、`?c=`、`acx` 補成 `dt`；`app.js` 整句、`TL_TABS` 整句 | 12 |
| `test_unchanged_and_wiring` | 23 個既有函式合併雜湊 `f206966d85e5`；`?v=`；舊 CSS 三行與新 CSS 三行；「第 41 輪」CSS 行數 3；node 14 語法與 `toFixed(`；`localStore` 只有 `fee`；沒有外部請求與 `<select` | 17、18、20、21 |
| `test_no_advice_words` | `tools.js` 全文＋新 CSS 行＋範例輸出不含禁用詞；`斷頭` 1 次 | 19 |
| `test_contrast` | 10 個反證全部擋下：拆單改一筆、零股用整股最低、兩平起點用理論值、起點不進位到升降單位、平均改浮點四捨五入、刪除不往前移、刪除後不清最後一列、證交稅合計後才捨去、換代號不清列、不帶入目前價格 | 23 |

- 驗收 17 的「四個分頁輸出逐字不變」：
  - `tlDtOut`、`tlCpOut`、`tlPlOut` 與三個表單由 `test_iter39` `LOCK` 鎖住。
  - `tlDvOut`、`tlDvForm`、`tlDvLoad`、`tlNx` 等由本輪合併雜湊鎖住。
  - `tlLoad` 只多寫 `TL.ac`；四個分頁的既有輸出測試（34／38／39／40）全部照過。
- 驗收 22：`verify` 內 `for f in tests/test_iter*.py; do python3 $f …; done` 全部通過（42 個檔）。
- 驗收 24：測試不連網、不連資料庫。

## 七、舊測試修改（D95，只有這一行）

| 檔案:行 | 改前 | 改後 |
|---|---|---|
| `tests/test_iter39.py:344` | `    assert "if (tl && !['dt', 'cp', 'pl', 'dv'].includes(tl[1]))" in APP` | `    assert "if (tl && !['dt', 'ac', 'cp', 'pl', 'dv'].includes(tl[1]))" in APP` |

- 其他舊測試 0 行改動（各輪 `?v=` 斷言是讀檔算雜湊，不用改測試）。

## 八、檔案與行數

| 檔案 | ＋ | − | 說明 |
|---|---|---|---|
| `site/tools.js` | 110 | 4 | 新函式 8 個（約 100 行）、`TL`／`TL_TABS`／`TL_VIEW`／檔頭、`tlLoad` 3 行 |
| `site/app.js` | 1 | 1 | 白名單 |
| `site/app.css` | 3 | 0 | 多列 grid、結果表窄螢幕、分頁列兩行（D101） |
| `site/index.html` | 3 | 3 | `?v=` |
| **程式小計** | **117** | **8** | PM 估約 110（上限 145） |
| `tests/test_iter41.py` | 486 | 0 | 新檔（PM 估 240、上限 312；多出的是 Fraction 參考實作、畫面流程模擬與 10 個反證） |
| `tests/test_iter39.py` | 1 | 1 | D95 |
| `README.md` | 2 | 0 | 測試清單一行、工具頁第 41 輪一段 |
| `docs/iterations/README.md` | 1 | 0 | 第 41 輪一行（接在第 40 輪之後） |

- 測試 486 行超過 PM 估計上限 312，但在一個工作階段上限 580 行內。

## 九、和 PM 的差異

| 項目 | PM | 設計 | 原因 |
|---|---|---|---|
| 浮點反例 | 68.525 用 `toFixed` 得 68.52 | node 得 68.53；反證改用 1.005 | 實測（第六節 `test_half`） |
| 分頁列 | 沿用 `.page-tabs` 橫捲 | 520px 以下換兩行（D101） | 重畫後橫捲位置回到最左，後面的分頁看不到；`tlDraw` 被鎖 |
| 新增鈕容器 | `<div data-g="r">` | `<div class="tl-segs" data-g="r">` | 借用 `.tl-segs` 的跨滿整列，不另加 CSS |
| 列數字串 | 讀取時轉整數 | 每次畫表單時把 `st.r` 寫回正規化後的值，並清空列數以外的欄位 | 新增的列一定空白（反證「刪除後沒清最後一列」） |
| 驗收 4 暴力解 | 從平均成本下方 50 檔起 | 同，另外先對齊到升降單位 | 不對齊時逐檔會落在不可成交的價位 |

## 十、風險

| 風險 | 說明 | 緩解 |
|---|---|---|
| 表單函式改狀態 | 刪除列依賴 `tlDraw` 模板「表單 → 結果」的順序 | `check_rows` 驗證結果區用移動後的資料；`tlDraw` 雜湊被鎖，順序不會被改 |
| 兩頁結果不同 | 交易成本頁 1,500 股一筆、本頁拆兩筆 | 說明第 5 則 |
| 理論值與可成交值 | 理論值不計最低值與捨去，可成交值可能低於理論值 | 起點用平均成本、不用理論值（反證擋下） |
| 分頁列兩行 | 375／320 寬分頁列高度從 38 變 82px | 只作用在工具頁 `#toolTabSeg`；首頁、個股頁不變 |
| 超大金額顯示 | 手續費超過 9 × 10^15 元時 `Number` 失真 | 實際不會發生；計算與比較用 `BigInt` |
| 桌機輸入框很寬 | 1024 寬每列輸入框約 400px | 不影響使用；之後若要可加 `max-width` |

## 十一、PG 套用步驟

1. 在專案根目錄：`git apply --check docs/iterations/41/03-design.diff`，再 `git apply docs/iterations/41/03-design.diff`。
2. `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`，應沒有輸出。
3. `git diff --stat tests/`：`test_iter39.py` 只有 1 行（另有新檔 `test_iter41.py`）。
4. 不需要 `setup-db`、`export`、收集。瀏覽器重新整理即可（`?v=` 已更新）。
5. 手動冒煙測試（測試用 8001，結束關掉）：
   - `#/tools/ac?c=2330`：填兩列，看目前價格小字。
   - 新增到 10 列、刪除中間一列。
   - 切到「除權息」：375 寬分頁列兩行、看得到被選的分頁。

## 十二、需要使用者決定的事項（D101 起；已 grep `docs/iterations`，目前最大 D100）

| 編號 | 問題 | 選項 | 建議 |
|---|---|---|---|
| **D101** | 工具頁 5 個分頁在 375／320 寬放不下一行，而 `tlDraw`（被鎖）每次整頁重畫，橫捲位置會回到最左，選了「除權息」後看不到被選的分頁（PM 驗收 16 做不到） | **A** 520px 以下工具頁分頁列換成兩行（CSS 1 行，只作用在 `#toolTabSeg`）；**B** 維持橫捲，在不被鎖的函式（例如 `tlDvForm`、`tlAcForm`）用 `requestAnimationFrame` 把選中的分頁捲進畫面（每個分頁都要加，寫法繞）；**C** 維持橫捲、接受看不到（驗收 16 改寫） | **A**（diff 已依 A 製作）：不動被鎖函式，320／375 實測兩行、不橫捲；1024 寬照舊一行 |

## 使用者決定（2026-11-21）

- **D101 = A**：520px 以下工具頁分頁列換成兩行（只加一行 CSS，作用於 `#toolTabSeg`）。
- 接受 `test_iter41` 486 行（超過 PM 估計上限 312，仍在工作階段上限 580 內）。
