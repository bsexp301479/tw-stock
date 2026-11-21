# 第 42 輪｜SA：設計

- 撰寫日期：2026-11-22（週日）；網站資料日 2026-11-20（週五）。
- 依據：
  - `42/01-analyst.md`：F42-1～F42-7、R40～R42。
  - `42/02-pm.md`：驗收 1～26；文末「使用者決定」：D103 = A、D104 = A、D104-1 = A、D104-2 = A、D105／D108 = B（小卡在分頁鈕之下、總覽內容第一個區塊）、D106 排下一輪、D107 = A、D109 = A（舊測試 0 行）、D110 = A（證交稅依商品細分）、PM 自行決定七項照用。
- 做法：
  - scratchpad 建 `r42sa/base`、`r42sa/proj`（`rsync`，排除 `.git`、`.env`、`_backups`、`_archive`），在 `proj` 實作與寫測試。
  - 產出 `42/03-design.diff`（904 行，路徑前綴 `a/`、`b/`）。另把 `base` 複製成 `verify` 套用 diff，與 `proj` 逐檔比對相同；`verify` 內 `tests/test_iter*.py` 42 個全部通過。
  - 正式專案 `git apply --check docs/iterations/42/03-design.diff` 通過。
- 守則：
  - 資料庫 0 次、專案程式的外部請求 0 次、`export` 0 次；沒有讀、印、複製 `.env`。D110 查證只用網頁搜尋與讀取官方網頁。
  - 瀏覽器只在 `verify` 用 8002 起 `serve` 看畫面，看完已關閉（`lsof -i :8002` 無輸出；伺服器 404 只有 `favicon.ico`）；沒有碰 8000、8001。該來源的 localStorage 開始時只有 `tw.todayTab=ov`，結束時已還原成只有這一鍵；視窗已設回 desktop，分頁已關。
  - 正式專案只新增 `docs/iterations/42/03-design.md`、`03-design.diff`。

---

## 重點摘要

- **持股**（F42-1）：`app.js` 新增一組小函式，讀寫只在 `holdLoad`／`holdSave`；計算是純函式 `holdCalc(L, codes, H, fee, today)`，出售**呼叫** `tools.js` 的 `tlSell`（`tlLot` 拆整股零股、`tlFee`、證交稅捨去都在裡面），不複製算法。自選頁與今日小卡共用 `holdCalc`＋`holdSum`，數字一定相同。
- **焦點不遺失**：輸入框 `change` 時只改數字儲存格（第 2、3 欄的顯示文字 `.h-v`、第 5～8 欄、`tfoot`、說明、全部持股一行），輸入框本身不重畫。瀏覽器實測：填入 → 焦點在股數 → 改值後焦點移到平均成本仍在 → 存檔後焦點仍在。
- **舊測試 0 行改動**：新函式只在 `wc === 'hold'`（`HV` 不為 null）時呼叫；`etfWatchTable` 內只用既有名稱（舊測試單獨執行它）。預設「資金」欄組輸出和改動前逐字相同，只多一顆「持股」鈕（比對方法見第七節）。
- **`tools.js` 0 行改動**（sha1 前 8 碼仍為 `05638786`）。
- **PM 範例 1～7 全部相符**（範例 7 以反證方式驗證：債券 ETF 改用 0.1% 時證交稅 26、未實現 −1,413、−5.14%）；隨機 200 組和 Python 整數參考實作逐分相同，前 24 組另和平均成本工具 `tlAcOut` 的出售手續費、證交稅相同。
- **D110 查證**：存託憑證 0.1%、只有「被動式、非槓桿反向」債券 ETF 停徵至 2026/12/31，和 PM 假設相同；另外發現**延長 10 年的修法 11/11 已過立法院初審、尚未三讀**，提出 D111（第九節）。
- 行數：`app.js` ＋134／−9、`stock.js` ＋21／−5、`app.css` ＋4、`index.html` ±3；測試 `test_iter42.py` ＋567（16 個測試）；文件 README ＋2、`docs/iterations/README.md` ＋1。程式合計約 ＋159（PM 估 201、上限 263）；測試 567 行超過 PM 估計 300（上限 390 以 × 1.3 計），但在一個工作階段上限 580 內（多在隨機比對、DOM 替身與 14 個反證）。

---

## 一、D110 查證（2026-11-22 查證）

| 項目 | 查證結果 | 來源 |
|---|---|---|
| 股票 | 千分之三（證券交易稅條例第 2 條第 1 款「公司發行之股票及表明股票權利之證書或憑證」） | 財政部主管法規共用系統「證券交易稅條例」（修正日期 114-01-02）<https://law-out.mof.gov.tw/LawContent.aspx?id=FL006079> |
| ETF、受益憑證、受益證券 | 千分之一（第 2 條第 2 款「公司債及其他經政府核准之有價證券」） | 同上 |
| 臺灣存託憑證（TDR，本站 4 檔：9103、9105、9110、9136，名稱 `-DR` 結尾） | 千分之一，依第 2 條第 2 款（財政部 81.11.19 台財稅第 811672688 號函） | 財政部稅務入口網「轉讓臺灣存託憑證的證券交易稅稅率是多少？」<https://www.etax.nat.gov.tw/etwmain/tax-info/understanding/tax-q-and-a/national/securities-transaction-tax/filing/LeJ1WWV>；函釋 <https://law-out.mof.gov.tw/LawContent.aspx?id=GL008599> |
| 債券 ETF 停徵 | 第 2 條之 1 第 2 項：106-01-01 起至 **115-12-31（2026/12/31）** 暫停徵收「債券指數股票型基金」受益憑證，**不含槓桿型、反向型**；公司債、金融債同期限 | 證券交易稅條例第 2 條之 1（同上網址） |
| 停徵延長（未生效） | 行政院 2026-10-01 通過修正草案：延長至 2036-12-31，並自 2027-01-01 起納入主動式債券 ETF；立法院財委會 2026-11-11 初審通過，**尚未三讀** | 經濟日報 <https://money.udn.com/money/story/5607/9871939>、<https://money.udn.com/money/story/7307/9871598>；聯合新聞網 <https://udn.com/news/story/7243/9788824>（新聞，非法規；三讀後要再查總統公布日） |
| 現股當沖 0.15% | 第 2 條之 2，至 2027-12-31（持股表不用） | 同上法規 |

### 本站代號對應（`latest.json` 11/20 全量盤點）

| 類別 | 規則 | 檔數 | 試算稅率 | 和法規 |
|---|---|---|---|---|
| 股票 | `stocks` 且名稱不是 `-DR` 結尾 | 1,982 | 0.3% | 相符 |
| 存託憑證 | `stocks` 且名稱 `-DR` 結尾（`stocks` 代號全部是 4 碼數字，沒有受益證券） | 4 | 0.1% | 相符 |
| 債券 ETF | `etfs.rows` 代號 `B` 結尾 | 102（名稱都不是正 2／反 1） | 0（`tlTax('b')`，到期只提醒） | 相符 |
| 主動式債券 ETF | 代號 `D` 結尾 | 8 | 0.1% | 相符（現行法不在停徵範圍；若修法三讀，2027 起停徵 → D111） |
| 槓桿、反向債券 ETF | `00680L`、`00681R`、`00688L`、`00689R` | 4 | 0.1% | 相符（法條排除槓桿、反向） |
| `00687C`（國泰 20 年美債的美元交易線） | `C` 結尾，不是 `B` | 1 | 0.1% | 查不到官方對外幣交易線的明確說明，依 PM 提示「以較高稅率試算」 |
| 平衡型 `T` 結尾、期貨 `U`、雙幣 `K` 等其他 ETF | 其他 | — | 0.1% | 相符 |

- 結論：PM 的 D110 = A 規則（股票 0.3%、`-DR` 0.1%、ETF 0.1%、代號 `B` 結尾 0）和現行法規一致，照用。說明 3 的停徵期限不寫死，取 `tlTax('b').until`（`tools.js` 的 `TL_RULES`），將來改 `TL_RULES` 時說明自動跟著改。

---

## 二、`site/app.js`

### 2-1 新函式一覽（都在 `etfWatchTable` 之後、「資料新鮮度」之前；`EX_TIP`、`etfPct` 在 `ETF_DIV_NOTE` 之前）

| 名稱 | 用途 |
|---|---|
| `EX_TIP`、`etfPct(r, d)` | F42-7：ETF 漲跌欄。`r.c != null && r.p == null && r.dvd === d` → `<td class="num flat" title="EX_TIP">除息</td>`；否則同舊式（`c == null` 無成交、其他 `sgn(p)%`）。ETF 列表、今日小卡用 |
| `holdLoad()` | 讀 `tw.hold`、驗證、移除連動、必要時寫回（2-3） |
| `holdSave(H)` | 寫入後讀回比對，回傳是否成功 |
| `holdKind(c, x, e)` | D110：`e ? (/B$/ → 'b' : 'e') : (/-DR$/.test(名稱) → 'e' : 's')` |
| `holdCalc(L, codes, H, fee, today)` | 純函式：回傳 `{ f, today, s: {rows, sum}, e: {rows, sum}, all }`（2-4） |
| `holdSum(rows)` | 合計：只算有持股且有收盤的列；今日損益是 null 的列不加、計 `k` |
| `holdView()` | `holdCalc(App.latest, [...App.watch], holdLoad(), localStore('fee', null), tlToday())`；自選頁與今日小卡都用它 |
| `holdY`、`holdP`、`holdTd` | 金額（分 → 帶正負號的元，`tlS`）、報酬率、上色儲存格 |
| `holdQ`、`holdK`、`holdIn` | 第 2、3 欄顯示文字（或「填入」鈕）、輸入框 |
| `holdTds(x)` | 第 5～8 欄 |
| `holdFoot(S)`、`holdAll(V)`、`holdCap(V, L)` | 合計列、全部持股一行、表上方說明 |
| `holdTable(T, e, V)` | 持股表（股票 `data-h="s"`、ETF `data-h="e"`） |
| `holdWire(sec)`、`holdEdit(sec, c)` | 「填入」、輸入框 `change`（2-6） |
| `holdLine(V, L)` | 今日小卡的持股一行＋小字 |
| `watchToday(L, rows)` | F42-2 小卡（第四節） |

- 名稱刻意不用 `hold` 單字以外的舊名：`holdTag`（第 7 輪 ETF 持股標籤）不改；新函式全用 `hold` 開頭＋大寫字母。

### 2-2 接線（改動的既有行）

| 位置 | 改前 → 改後 |
|---|---|
| `renderToday` `body.ov` | `` ov: `${sumStrip(L)}… `` → `` ov: `${tab === 'ov' ? watchToday(L, rows) : ''}${sumStrip(L)}… ``（D108 = B；指數卡、分頁鈕兩句不改） |
| `renderToday` 監聽 | 加 `$('#view .w-hold')?.addEventListener('click', () => { App.watchCols = 'hold'; });`（連結本身跳 `#/watch`） |
| `renderEtf` 漲跌欄 | `<td class="num ${cls(r.ch)}">${r.c == null ? '無成交' : sgn(r.p) + '%'}</td>` → `${etfPct(r, App.latest.date)}` |
| `renderWatch` `wc` | `App.screen === null ? 'flow' : …` → `App.screen === null && list.length ? 'flow' : …`（只有 ETF 時不受 `screen.json` 影響） |
| `renderWatch` 新增一行 | `const HV = wc === 'hold' && (list.length \|\| etfs.length) ? holdView() : null;` |
| `renderWatch` 欄位組 | 有股票：尾端加 `['hold', '持股']`；只有 ETF：`segHTML('wcolSeg', [['flow', '行情'], ['hold', '持股']], HV ? 'hold' : 'flow')`；`screen.json` 不存在且有股票照舊「表現、基本面資料尚未產生」 |
| `renderWatch` 股票卡 | `list.length ? HV ? holdCap(HV, App.latest) + holdTable(HV.s, false, HV) : wc === 'flow' ? …`（持股時不呼叫 `stockTable`，所以沒有 1 日／5 日；不呼叫 `watchColTable`，所以不載入 `screen.json`） |
| `renderWatch` ETF 卡 | `HV ? (list.length ? '' : holdCap(HV, App.latest)) + holdTable(HV.e, true, HV) : etfWatchTable(etfs)`（說明只寫一次，只有 ETF 時放 ETF 表上方） |
| `renderWatch` 監聽 | `watchGestures(...)` 之後加 `if (HV) holdWire($('#view .watch'));` |
| `etfWatchTable` | 見第五節 |

- `onRowClick`、`route`、`watchGestures`、`stockTable`、`shareWatch`、`saveWatchOrder`、`divHTML`、`tagFold` 一字不改。

### 2-3 儲存 `tw.hold`（R40）

```js
function holdLoad() {
  const raw = localStore('hold', null), H = {}, keep = c => App.watch.has(c) || (App.watchUndo || []).includes(c);
  let o = null;
  try { o = JSON.parse(raw); } catch (e) { /* 壞值當作沒有存 */ }
  if (o && typeof o === 'object' && !Array.isArray(o)) Object.keys(o).forEach(c => { const v = o[c];
    if (/^[0-9A-Z]{4,6}$/.test(c) && keep(c) && Array.isArray(v) && v.length === 2 && v.every(Number.isSafeInteger) && v[0] >= 1 && v[0] < 1e12 && v[1] >= 1 && v[1] < 1e14) H[c] = v; });
  if (raw != null && JSON.stringify(H) !== raw) holdSave(H);
  return H;
}
```

- 格式 `{"代號": [股數, 平均成本（分）]}`，例 `{"1538":[2000,800],"2330":[1350,151235]}`。
  - 註：JS 物件的數字代號會依數值排序寫出（`1538` 在 `2330` 前），不影響讀取；畫面順序依自選。
- 驗證不符的筆丟掉；整串不是物件 → `{}`。有任何筆被丟掉時寫回（沒有存過就不寫）。
- **移除連動（R40）**：`keep(c)` = 在自選裡，或在 `App.watchUndo`（這次可復原的移除前清單）裡。
  - 按「✕」：`onRowClick` 設 `App.watchUndo = 移除前清單` 後重畫 → 持股表不顯示該列，但 `tw.hold` 仍保留 → 按「復原」後回來。
  - 不在可復原狀態（`route` 離開自選頁時把 `watchUndo` 清成 null、已按復原、或又移除了另一檔使 `watchUndo` 換成新清單）時，下一次 `holdLoad`（自選頁持股、今日總覽小卡、編輯存檔）刪掉並寫回。
  - 個股頁「★ 已加入自選」取消：當時 `watchUndo` 為 null（`route` 已清），下一次讀取就刪。
  - 所以**不需要改 `onRowClick`、`route`**。
- `holdSave`：`localStore('hold', null, s)` 後 `localStore('hold', null) === s`，不同時回傳 false（私密視窗、封鎖網站資料）。
- 只有 `holdLoad`、`holdSave`、`holdView` 用 `localStore`（鍵 `hold`、`fee`）；`renderWatch` 等第 32 輪限定的函式仍只有 `rspan`。`App.watchCols` 不寫 localStorage。

### 2-4 計算（R41；金額「分」BigInt、手續費與證交稅「元」）

```js
function holdCalc(L, codes, H, fee, today) {
  const f = tlFeePref(fee), o = { dz: Math.round(f.d * 100), m: +f.m, mo: 1 }, R = (L.etfs && L.etfs.rows) || {};
  const row = (c, x, e) => { const h = H[c], P = x.c == null ? null : Math.round(x.c * 100);
    if (!h || P == null) return { c, x, e, h, dt: h && '無成交' };
    const kd = holdKind(c, x, e), S = tlSell(P, h[0], Object.assign({ r: tlTax(kd, false, today).r }, o)), T = BigInt(h[0]) * BigInt(h[1]);
    const dt = e ? (x.p == null && x.dvd === L.date ? '除息' : x.ch == null ? '--' : '') : x.nt ? '無成交' : x.ch == null ? '--' : '';
    return { c, x, e, h, kd, v: S.sa, T, u: S.net - T, f: S.f, tx: S.x, dt, d: dt ? null : BigInt(Math.round(x.ch * 100)) * BigInt(h[0]) }; };
  …
}
```

- 手續費設定：`tlFeePref(localStore('fee'))`（壞值回 10 折、20 元，同交易成本頁）；零股最低固定 1 元。
- 市值 `v` = `tlSell(...).sa` = P × q；未實現 `u` = 出售淨額 − 總成本；報酬率 `holdP` = `tlS(Number(U) / Number(T) × 100, 2) + '%'`（四捨五入為 0 時不帶負號）。
- 今日損益 `d` = `Math.round(ch × 100) × q`；股票無成交（`nt`）→「無成交」、ETF 今天除息 →「除息」、`ch` 為 null → `--`，這些列 `d = null`，合計不加並計 `k`。
- ETF 今天無成交（`c == null`）：`v` 不存在，第 4～8 欄 `--`（今日損益「無成交」），不計入合計。
- 金額顯示：市值 `tlY(Number(v))`、其他 `holdY`（有角分 2 位小數、否則整數）。金額 < 2^53 分時逐分正確（隨機測試最大約 1.7 × 10^15 分）；更大時只轉 Number 顯示，不會 NaN。

### 2-5 持股表 HTML（每列）

```html
<tr data-code="2330">                                     <!-- ETF 表是 data-etf，拖曳排序、onEtfRow 照舊 -->
  <td class="nm h-nm">{wCtl(c)}<b>台積電</b>{alertBadge}<span>2330 半導體</span></td>   <!-- ETF：<span>0056 上市</span> -->
  <td class="num"><span class="h-v">1,350</span><input class="h-in" data-hq="2330" inputmode="numeric" autocomplete="off" placeholder="股數" aria-label="台積電 股數" value="1350"></td>
  <td class="num"><span class="h-v">1,512.35</span><input class="h-in" data-hc="2330" inputmode="decimal" autocomplete="off" placeholder="平均成本" aria-label="台積電 平均成本" value="1512.35"></td>
  <td class="num">2,000</td>                              <!-- 股票無成交：7.24<span class="sub2">最後成交 11/09</span> -->
  <td class="num">2,700,000</td><td class="num dn">-135,000</td><td class="num up">+647,919.50</td><td class="num up">+31.73%</td>
</tr>
```

- 沒有持股：`.h-v` 內是 `<button class="chip h-fill" data-hfill="2330">填入</button>`、平均成本 `--`、第 5～8 欄 `--`；輸入框 value 空白。
- 平均成本的 value 用整數組字（`Math.floor(k / 100) + '.' + 補 0 的兩位`），不用浮點 `toFixed`。
- 名稱格寫成 `<td class="nm h-nm">${wCtl(x.c)}`，不出現 `test_iter25` 計數的兩個字面。
- 表尾 `<tfoot>`：`<td class="nm"><b>合計</b><span>N 檔</span></td>`＋3 格空白＋市值、今日損益（＋`<span class="sub2">不含 k 檔</span>`）、未實現、報酬率。
- 表下方：`<div class="h-msg" role="status"></div>`；ETF 表再加 `<div class="small h-all">全部持股（股票＋ETF）　市值 X 元　今日損益 Y 元　未實現損益 Z 元（W%）</div>`（兩張表都有合計時才有文字；Y、Z、W 上色）。
- 說明（`<div class="muted small tbl-cap h-cap">`，每則一個 `<div>`）：PM 二之一第 1～5 則逐字；第 3 則用 D110 = A 文字，期限取 `tlTax('b').until`；第 4 則只在有債券 ETF 持股且 `today > until`；第 5 則只在有 `dsp` 的持股。兩張表都沒有持股時第一則是「還沒有填持股。…」。

### 2-6 輸入、存檔、焦點

- `holdWire(sec)`（`sec` = `#view .watch`，每次重畫都是新元素，不累積監聽；`null` 時直接返回）：
  - `click`（冒泡）：目標在 `[data-hfill]` 內 → `stopPropagation()`（`#view` 上的 `onRowClick` 不會收到，不進個股頁；ETF 列的 `onEtfRow` 本來就略過 button）→ `App.watchEdit = true`、`sec.classList.add('editing')`、`#watchEdit` 文字改「完成」→ 該列股數輸入框 `focus()`。
  - `change`：目標有 `data-hq`／`data-hc` → `holdEdit(sec, 代號)`。
- 編輯模式既有的 capture 監聽（`watchGestures`）會擋下 tbody 內的 click，但輸入框的焦點在 pointerdown 就取得，實測可正常點選、輸入、Tab。
- `holdEdit(sec, c)`：
  1. 讀同列兩格 `trim()`：`q = tlNum(a, 0)`、`k = tlC(b)`。
  2. 訊息（PM 驗證表逐字，`{名}` = `名稱 代號`）：只填一格 → 「請同時填…」；股數不是 > 0 → 「股數請填正整數」；平均成本不是 > 0 → 「平均成本請填…」。
  3. 不合法的那一格 `aria-invalid="true"`，合法的移除屬性；有訊息時不存（保留已存的值）。
  4. 合法：兩格都有 → `H[c] = [q, k]`；兩格都空 → `delete H[c]`；`holdSave` 失敗時加一行「這個瀏覽器無法儲存持股…」。
  5. 訊息放在該表下方 `.h-msg`，每列一行 `<div data-m="代號">`，該列改對後移除。
  6. 重算 `holdView()`，逐列只改：兩個 `.h-v` 的 innerHTML、刪掉第 5 格以後再插入 `holdTds`；`tFoot.innerHTML`；`.h-cap` 的 outerHTML；`.h-all` 的 innerHTML。輸入框不動，所以 Tab 換格、存檔後焦點都在。
- 「完成」照舊由 `watchGestures` 切換 class；非編輯模式由 CSS 顯示 `.h-v`（最新值）。

### 2-7 用詞、隱私

- 畫面用「買入」「出售」；說明 2 的連結 `#/tools/ac` 所在行含 `tools`，`test_iter34` 會掃，已確認不含禁用詞。
- 新函式沒有 `fetch(`、`XMLHttpRequest`、`console.log`、`location`、`history`、`sendBeacon`、`localStorage`（`test_iter42` 檢查）；`shareWatch` 不改（`test_iter42` 以 node 執行，網址只有代號）；`twstock/` 沒有任何 `tw.hold`。

---

## 三、F42-3、F42-4、F42-6（`site/stock.js`）

### 3-1 族群標籤

```js
const GRP_NM = { industry: '類股', concept: '概念股' };
function grpTag(gk, gn, txt, t0 = '') {
  const c = gk === 'chain' ? 'pill chain' : 'pill';
  if (!(App.latest.groups && App.latest.groups[gk] || []).some(g => g.name === gn)) return `<span class="${c}"${t0 ? ` title="${t0}"` : ''}>${txt}</span>`;
  return `<a class="${c} grp" href="#/bubble" data-gk="${gk}" data-gn="${esc(gn)}" title="${gk === 'chain' ? `${t0}（點了看泡泡圖「${esc(gn)}」整條產業鏈）` : `看泡泡圖「${esc(gn)}」${GRP_NM[gk]}`}">${txt}</a>`;
}
```

- 頁頭：產業 `${E ? '<span class="pill">ETF</span>' : grpTag('industry', data.industry, esc(data.industry))}`；產業鏈 `grpTag('chain', chain, 原顯示文字, 原 title)`；概念股 `grpTag('concept', c, esc(c))`。名稱不在 `groups` 時輸出和改動前逐字相同的 `<span>`。
- 監聽（`#tagMore` 那行之後；`.tags` 含「+N」摺疊的 `.tag-rest`，摺疊內的標籤也有效）：

```js
$('#view .tags').addEventListener('click', e => { const a = e.target.closest('a[data-gk]');
  if (a) { setGroup(a.dataset.gk); localStore('focus', null, a.dataset.gn); Object.assign(App, { blOpen: a.dataset.gn, blAll: false, blJump: 1 }); } });
```

- 不用 `data-group`、不經 `onRowClick`；`tagFold` 不改（`test_iter25` 執行它）。
- 實測：手機 2454「IC設計」→ `#/bubble`、`tw.group = concept`、`tw.focus = IC設計`、清單該列展開且在畫面內；桌面「半導體」→ 明細卡標題「半導體」、分組類股。

### 3-2 ETF 頁頭數字卡

```js
const etfCards = E => [...E.dvc ? [['近一年配息', E.dvc.toLocaleString('zh-TW', { maximumFractionDigits: 4 }) + ' 元', '', '每單位，近 365 天合計'],
    ['配息率', E.c > 0 ? fmt(E.dvc / E.c * 100, 2) + '%' : '--', '', E.c > 0 ? '近一年配息 ÷ 今日收盤；股價下跌時會變高' : '今天無成交'],
    ['最近除息', E.dvd ? md(E.dvd) : '--', '', E.dvd ? (E.dvn != null ? E.dvn + ' 天填息' : E.dvx ? '中斷' : '未填息') : '']] : [],
  ['成交額', E.tv == null ? '--' : fmt(E.tv, 2) + ' 億', '', '當日']];
```

- 放在 `cardsHTML` 之前（頂層，測試可單獨執行）；插入點 `const mtCards = E ? etfCards(E) : [['市值', …`（股票頁不變；`...mtCards]` 字面保留，`test_iter13`）。
- 含「配息率」的行都不含「殖利率」（`test_iter36`、`test_iter42` 掃描）。
- 實測 0056：近一年配息 4.936 元、配息率 11.14%、最近除息 10/22 未填息、成交額 84.74 億（共 6 張）；00632R：52 週高、低、成交額 3 張。

### 3-3 河流圖（D109 = A）

- `renderBand` 的 `ex` 陣列第一項：`k === 'pe' ? '本卡的 EPS 由官方本益比反推（收盤 ÷ 本益比），和季報卡的近 4 季 EPS（財報累計相減）算法不同，數字可能略有差異。' : ''`，緊接在「收盤 = …」說明列之後；不用 `noteHTML`；`BAND_NM`、季報卡不改，`test_iter37` 照過。

---

## 四、F42-2 今日小卡（D108 = B）

- `watchToday(L, rows)`：`rows` 是 `renderToday` 內既有的列函式，**股票列直接沿用**（新程式沒有 `ycls(`）；ETF 列 `<tr data-code="代號">`＋名稱、收盤、`etfPct`、法人 `--`（點列由 `onRowClick` 進 `#/stock/代號`，沒有新增 `onEtfRow` 監聽）。
- 結構：標題列「我的自選｜MM/DD 收盤（法人日期不同時「、法人 MM/DD」）｜全部 →」、4 欄表（依自選順序前 5 個認得的代號）、`holdLine`、訊號一行、說明一行（PM 逐字）。
- 訊號 a = 自選股票中 `hl` 有 `HL_KINDS` 認得種類的檔數；b = 有 `dsp` 或 `ntc` 的檔數（全部自選，不只前 5 檔）。
- 持股一行用 `holdView().all`，和自選頁「全部持股」同一個函式（測試比對逐字相同）。
- 量測（375 × 812、`verify`、11 檔自選含 5 檔持股）：分頁鈕上緣 278px、小卡上緣 338px、第 1 列下緣 485px，底部選單上緣 758px → 第一屏看得到標題與前 2～3 列。D108 = A 時小卡會在分頁鈕位置（約 278px）開始，只差約 60px。
- 1024 寬：小卡寬 992px，和分頁鈕同寬（不在 `g-stats` 格線內）。

---

## 五、F42-5／F42-7 自選 ETF 表

- `etfWatchTable` 在 `test_iter20／23／27／32／33` 中以固定函式清單單獨執行，所以**只用既有名稱**（`fmt`、`md`、`cls`、`sgn`、`App`），不呼叫 `etfPct`／`etfDiv`：
  - 漲跌欄寫成同一個條件的行內運算式（tooltip 文字同 `EX_TIP`）。
  - 3 個新欄：近一年配息 `r.dvc.toLocaleString(... 4 位)`、配息率 `r.dvc > 0 && r.c > 0 ? fmt(r.dvc / r.c * 100, 2) + '%' : '--'`（同 `etfDiv` 的 `dvr`）、最近除息 `md(dvd)`＋填息狀態 `sub2`（和 ETF 列表同一個字面）。
  - 表下方 `<div class="muted small h-note">配息率 = 近一年配息 ÷ 今日收盤，股價下跌時會變高；最近除息的第二行是填息狀態，算法同 ETF 列表。</div>`。
- 代價：「除息」條件在 `etfPct` 與 `etfWatchTable` 各寫一次（反證兩處都測）。
- 舊假資料沒有 `dvc`、`dvd` → 三欄 `--`；`test_iter20:28` 的前 5 欄表頭、`test_iter23:285` 的 ETF-only 說明 span 不變。

---

## 六、`site/app.css`（4 行，全文）

```css
.watch:not(.editing) .h-in,.watch.editing .h-v{display:none}.h-in{width:88px;box-sizing:border-box;padding:4px 8px;border:1px solid var(--border2);border-radius:6px;background:var(--card);color:var(--text);font-size:16px;text-align:right;font-variant-numeric:tabular-nums;outline:none}.h-in:focus{border-color:var(--blue)}.h-in[aria-invalid="true"]{border-color:var(--up)}   /* 第 42 輪 F42-1：持股輸入框（編輯模式才顯示；16px 手機不放大） */
.h-tbl tfoot td{border-bottom:0;border-top:2px solid var(--border);font-weight:500}.h-msg:not(:empty){color:var(--amber);font-size:13px;margin-top:6px}.h-all{margin-top:8px;line-height:1.7}.h-note{margin-top:6px}   /* 第 42 輪：持股合計列、輸入訊息、全部持股、自選 ETF 表說明 */
.w-hold{display:block;margin-top:8px;line-height:1.7}.w-ev-l{display:block;margin-top:6px;color:var(--blue)}.w-today>.muted.small{margin-top:4px}   /* 第 42 輪 F42-2：今日頁我的自選 */
a.pill.grp{cursor:pointer}a.pill.grp:hover,a.pill.grp:focus-visible{border-color:var(--blue);outline:none}   /* 第 42 輪 F42-3：可點的族群標籤（文字顏色不變） */
```

- 只用既有色票；深色下輸入框是 `--card`（#17181b）底、`--text`（#ececec）字，對比遠大於 4.5:1。
- 輸入框 88px、字級 16px（實測 `getComputedStyle` 16px、寬 88px）；「填入」是 `.chip`，≤ 720px 已由既有規則 `min-height:34px`。
- 持股表 8 欄在 `.tbl-wrap` 內左右捲動；實測 1024／375／320 × 淺／深的今日總覽、自選持股（含編輯模式、11 檔）、ETF 個股頁、個股頁標籤列、泡泡清單，`scrollWidth === innerWidth`。
- 沒有 `tl-` 開頭的 class，註解只寫「第 42 輪」。

---

## 七、舊測試（0 行改動）

### 7-1 node 單獨執行環境

| 舊測試 | 執行的函式 | 假 `App` | 新程式走的路徑 |
|---|---|---|---|
| `test_iter20:test_render_watch`、`test_iter23:test_watch_etf_only`、`test_iter27:test_watch_event_card` | 21～22 個固定名稱（含 `renderWatch`、`etfWatchTable`） | `{ latest, watch }`，`screen`、`watchCols` 為 undefined | `wc = 'flow'`、`HV = null`：不呼叫任何新函式；`etfWatchTable` 只用既有名稱；只有 ETF 時多輸出「行情｜持股」欄位組，`$('#wcolSeg')` 的替身有 `addEventListener`，`onSeg` 正常 |
| `test_iter32`、`test_iter33` | 40 個名稱 | 另有 `screen`、`watchCols`（flow／perf／fund） | 同上，`HV = null`；`screen === null` 且有股票時照舊沒有 `wcolSeg` |
| `test_iter25` | `onRowClick`、`saveWatchOrder`、`wCtl`、`tagFold` | — | 都不改 |
| `test_iter28／32／34／39／41` | `route` | — | 不改 |
| `test_iter37` | `renderBand` 等 7 個 | `mk()` | `ex` 多一項，只用字串，不需新名稱 |

- **預設資金欄組逐字比對**：用 `test_iter32` 的 `_js` 架構，分別載入 `base` 與 `proj` 的 `app.js`，跑 `run(['2330','2317','6666'], {screen})`、`perf`、`fund`、`screen: null` 四組；差異只有欄位組多了 `<button data-v="hold" class="">持股</button>`，表格與其他內容逐字相同（`screen: null` 那組完全相同）。

### 7-2 字面計數

| 斷言 | 結果 |
|---|---|
| `test_iter30:48` `APP.count("ycls(") == 14` | 14（新程式沒有 `ycls(`） |
| `test_iter14:117` `note-dup` 3／2 | 3／2 |
| `test_iter20:30` `addEventListener('click', onEtfRow)` == 2 | 2 |
| `test_iter25:88` `rm ? wCtl(c) : ''`、`<td class="nm">${wCtl(c)}` 各 1 | 各 1（持股表用 `<td class="nm h-nm">${wCtl(x.c)}`） |
| `test_iter13:77` `noteHTML(` 字面短句 | 新程式沒有 `noteHTML(` |
| `test_iter39:443` `SEARCH_MUTANTS` | 搜尋程式未動，各 1 |
| `test_iter32:117～121` | `renderWatch` 等只有 `localStore('rspan'`；`App.watchCols = v; renderWatch();` 保留 |
| `test_iter36`／`test_iter34`／`test_iter35`／`test_iter27` 的掃描行 | 含「配息率」「tools」「第 3x 輪」等的新行沒有詞表裡的詞 |
| 各輪 `?v=` | `index.html` 3 行改成 sha1 前 8 碼：`app.css?v=d039dc67 → 55349eb3`、`app.js?v=e571fb7b → fedbd59a`、`stock.js?v=00d41238 → d7c03cdc`；`tools.js?v=05638786` 不變 |

---

## 八、新測試 `tests/test_iter42.py`（16 個，567 行）

| 測試 | 內容（驗收編號） |
|---|---|
| `test_examples` | PM 範例 1～6：各檔出售手續費、證交稅、第 5～8 欄逐字；股票／ETF 合計列、全部持股一行、今日小卡持股一行逐字（1、4、6） |
| `test_random_200` | 隨機 200 組（股票、ETF、債券 ETF、`-DR` 各 50；整股／零股／混合；折扣 0.01～10、整股最低 0～50、收盤 0.01～9,999.99、股數 1～10^9）和 Python 整數參考實作逐分比對手續費、證交稅、市值、今日損益、未實現、報酬率；前 24 組另和 `tlAcOut` 的出售手續費、證交稅相同（2） |
| `test_fee_and_tax_kind` | `tw.fee` 6 折 30 元、5 種壞值回 10 折 20 元；說明 1 的折數與最低值；股票 0.3%、`-DR` 0.1%、ETF 0.1%、`B` 結尾 0；`today = 2027-01-05` 時說明 4 出現且稅率仍 0；沒有債券 ETF 不提醒（5、6） |
| `test_inputs` | DOM 替身執行 `holdEdit`：股數 0、1.5、-3、abc、1e3、10^12；成本 0、-1、1.234、abc；只填一格；`' 1,350 '`、`' 7 '` 可接受；不合法時 `tw.hold` 不變、`aria-invalid`；成功後該列兩個 `.h-v`、第 5～8 欄、`tfoot`、說明更新；兩格清空刪除並回到「填入」；寫入失敗訊息（7、8、9） |
| `test_storage_and_remove_link` | 好的不重寫、沒存不寫；5 種整串壞值；壞筆與不在自選的代號丟掉並寫回；7 種壞值、邊界值；可復原時保留、復原後照舊、離開後刪除（9、10） |
| `test_fill_button` | 「填入」：進編輯模式、按鈕變「完成」、焦點在該列股數、`stopPropagation` 一次（8） |
| `test_privacy` | node 執行 `shareWatch`：網址只有代號；新函式沒有 `fetch(` 等；`localStore` 鍵只有 `hold`、`fee`；`twstock/` 沒有 `tw.hold`；第 32 輪限制照舊（11） |
| `test_col_sets_and_tables` | `test_iter32` 架構＋新函式＋整個 `tools.js`：有股票 4 個欄位組；`screen.json` 不存在照舊；持股不載入 `screen.json`、沒有 1 日／5 日、兩張表、說明一次；空狀態；輸入框屬性與預填值；`最後成交 11/09`；只有 ETF 時「行情｜持股」、說明在 ETF 表上方；ETF 無成交列 4～8 欄與不計入合計；欄位組不寫 localStorage（12、13） |
| `test_today_card` | 取 `renderToday` 內 `rows` 原文執行 `watchToday`：沒有自選不顯示；前 5 個認得的代號依序混排；ETF 列「除息」與 `--`；持股一行和 `holdAll` 數字相同；「不含…2 檔」；訊號 a、b 口徑；「共 8 檔，顯示前 5 檔」；法人日期；D108 = B 原始碼位置與指數卡、分頁鈕原句（14） |
| `test_group_tags` | 三種標籤 HTML 逐字；不在 `groups` 時和舊 `<span>` 相同；執行監聽：`App.group`、`tw.group`、`tw.focus`、`blOpen`、`blAll`、`blJump`；「+N」摺疊內是 `<a>`；CSS（15） |
| `test_etf` | `etfCards` 四種情況（含今天無成交）；配息率用今日收盤（同 `etfDiv`）；自選 ETF 表 8 欄、3 新欄、除息、無成交、說明；`etfPct` 四種情況；含「配息率」的行沒有「殖利率」（16、17、19） |
| `test_band_note` | 沿用 `test_iter37` 的替身：本益比河流圖有說明且在說明列之後、淨值比沒有（18） |
| `test_call_not_copy_and_counts` | `holdCalc` 呼叫 `tlSell`／`tlTax`／`tlFeePref`、沒有 `1425`／`1000000n`／`tlLot`；第七節字面計數；四個 `?v=`；`tools.js` sha1 `05638786`；`https://` 2 處（3、23） |
| `test_no_advice_words` | 新函式全文＋含「第 42 輪」的行＋README 第 42 輪段落不含 PM 二之十三全部禁用詞（22） |
| `test_css_and_docs` | 4 行 CSS、沒有寫死色碼、沒有其他輪次字樣；README、`docs/iterations/README.md`（20 的靜態部分、23） |
| `test_contrast` | 14 個反證（下表），每個都由斷言擋下（不是 node 錯誤）（25） |

- 反證：未實現不扣出售成本、`tlSell` 不拆整股零股（改 `tools.js` 字串）、零股最低改整股最低、ETF 用 0.3%、債券 ETF 用 0.1%（= 範例 7）、除息日今日損益當 0 計入合計、`tw.hold` 讀取不驗證、移除自選不刪持股、分享連結帶持股、族群標籤不切換分組、ETF 頁頭配息率用前一日收盤、自選 ETF 表配息率用前一日收盤、「除息」條件漏掉 `dvd === date`、只填一格當成合法。
- 所有輸出檢查 `BAD`（NaN、Infinity、∞、undefined、-0）。
- 版面（驗收 20 的實測部分）由 QA 在瀏覽器重驗；SA 已在 `verify` 實測（第六節）。

---

## 九、新決策（目前最大 D110，本輪從 D111 起）

### D111 債券 ETF 停徵延長修法（建議 A）

- 背景：現行法停徵到 2026/12/31；延長到 2036/12/31（並自 2027 起納入主動式債券 ETF）的修正草案 11/11 已過立法院財委會初審，尚未三讀。`tools.js` 的 `TL_RULES.tax.b = [0, '2026-12-31']` 被 `test_iter38`／`41` 的雜湊鎖住，本輪不能動。
- A（建議）：本輪照現行法；列入待辦，**三讀並公布後**另開一小輪改 `TL_RULES.tax.b` 的日期、加主動式債券（`D` 結尾）判斷，並更新相關舊測試雜湊（逐行請使用者同意）。在那之前若過了 2027/1/1，持股表、交易成本頁都會顯示「期限已過，請確認最新稅率」（仍以 0 試算），不會算錯已延長的稅率。
- B：本輪先在持股表說明 3 後面加「（延長修法審議中）」字樣。不建議：法案狀態會變，寫死在畫面上容易過時。

### D112 持股表說明 3 是否寫出代號規則（建議 A）

- A（建議）：照 PM 逐字「債券 ETF 停徵（至 2026/12/31）」，不加字。
- B：改成「債券 ETF（代號 B 結尾）停徵…；主動式、槓桿反向債券 ETF 與 00687C 以 0.1% 試算」。資訊較完整，但說明變長（手機多一行）；目前受影響的只有 8＋4＋1 檔，且 0.1% 是現行法正確稅率（00687C 為保守試算）。

---

## 十、風險

| 風險 | 說明 | 緩解 |
|---|---|---|
| 舊測試函式清單 | 預設路徑若碰到新名稱會 `ReferenceError` | `HV` 為 null 時不呼叫；`etfWatchTable` 只用既有名稱；42 個測試全過 |
| 焦點 | 存檔後重畫會掉焦點 | 只改數字儲存格；瀏覽器實測焦點保留 |
| 拖曳排序 | 持股表也有 `≡` | `tr` 仍是 `data-code`／`data-etf`、`tbody` 內，`saveWatchOrder` 照舊；`tfoot` 不在 `tb.rows` |
| 持股模式的 ETF 小標題 | 有股票時 ETF 表上方仍寫「當日行情；成交量為張、成交額為億元」（`test_iter23:285` 逐字斷言這個 span，不改） | 觀察項，QA 看是否需要另提 |
| 稅率將來變動 | D111 | 期限到了只提醒，不自動改 |
| 券商算法差異 | R37 | 說明寫「試算」 |
| 大金額 | > 2^53 分只要求不出 NaN | 同第 41 輪 |
| 測試行數 | 567 行，高於 PM 估計 | 在工作階段上限 580 內 |

---

## 十一、PG 套用步驟

1. 在正式專案根目錄：`git apply --check docs/iterations/42/03-design.diff`，通過後 `git apply docs/iterations/42/03-design.diff`。
   - 會改：`site/app.js`、`site/stock.js`、`site/app.css`、`site/index.html`（3 個 `?v=`）、`README.md`、`docs/iterations/README.md`；新增 `tests/test_iter42.py`。`tools.js` 與舊測試不動。
2. `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`，應沒有輸出。
3. 若之後再改任何 js／css，`test_iter23` 會印出正確的 3 行 `?v=`（`test_iter42` 另檢查 4 個）。
4. 在 8001 起 `serve`（結束時關閉）冒煙：自選頁選「持股」→「填入」→ 輸入 → Tab → 合計更新；今日總覽小卡；個股頁標籤；0056 頁頭；ETF 列表 00679B「除息」。
5. 不 commit、不 push。

## 使用者決定（2026-11-22）

- **D111 = A**：本輪照現行法（債券 ETF 停徵至 2026/12/31）；修法三讀公布後另開小輪修改期限與主動式債券判斷（屆時涉及 test_iter38／41 雜湊，逐行請使用者同意）。
- **D112 = A**：持股說明第 3 則照 PM 原字，不加註。
- 接受 `test_iter42` 567 行。
