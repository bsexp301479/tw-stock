# 第 01 輪｜System Analyst：設計文件

- 撰寫日期：2026-10-30
- 輸入：`02-pm.md` 本輪範圍 P1、P3、P7、A1、P2、P4、B8、P5、B10（沿用 PM 編號）
- 依據：閱讀 `twstock/collectors/*.py`、`db.py`、`export.py`、`__main__.py`、`fetch.py`、`site/app.js`、`stock.js`、`app.css`；查詢資料庫；2026-10-30 透過 `fetch.request` 實測 9 個端點各 1 次（見附錄 A）。
- 本文件只描述設計，不含程式修改。程式碼片段是給 Programmer 的規格，命名與寫法比照既有程式；細節可調整，但**欄位名稱、資料表、判斷式、畫面文案**請照本文件，QA 會照著驗。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | P1 | P3 | P7 | A1 | P2 | P4 | B8 | P5 | B10 |
|---|---|---|---|---|---|---|---|---|---|
| `twstock/db.py` | | | | 新表 `market_index` | | | | | 新表 `stock_alerts` |
| `twstock/collectors/daily.py` | | | | `parse_taiex`、`fetch_tpex_index`、`collect_tpex_index`、`merge_market_index`；`fetch_twse_daily` 改回傳 tuple；`collect_for_date` 支援 `INDEX` | | | | | |
| `twstock/collectors/history.py` | | | | `INDEX` 資料集（補抓入口） | | | | | |
| `twstock/collectors/alerts.py`（新檔） | | | | | | | | | 收集處置／注意股 |
| `twstock/__main__.py` | | | | `cmd_collect` 加呼叫；`history --only` 加 `index` | | | | | `cmd_collect` 加呼叫 |
| `twstock/export.py` | | | | `latest.index` | `latest.hl_from`、`stocks.*.hf` | | `revenue` 48 筆＋累計年增＋新高 | `prices.ch` | `stocks.*.dsp/ntc`、個股 `alerts` |
| `site/app.js` | 今日／排行／自選／泡泡圖 | `oiHTML()` | `renderRank()` | 今日頁指數卡＋走勢線 | | 今日頁卡片、排行說明 | | | 表格名稱旁小標記 |
| `site/stock.js` | 指標卡日期 | | | | 指標卡標籤 | | `renderRevenue()` 改寫 | `aggregate()`、`showLegend()` | 標頭 tags |
| `site/app.css` | `.flow-note` | `.fc-more` | | `.idx`、`.spark` | | | 移除 `.rev*`，加 `.hi` | | `.al`、`.pill.al-*` |
| `tests/test_iter01.py`（新檔） | | | | 正負號解析 | | | 累計年增、新高 | | 民國日期、警示解析、有效判斷 |

### 建議實作順序

依 PM 優先順序，但把「不需改程式、耗時」的補抓提前在背景執行，並把同一檔案的修改放在一起：

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 0 | **先在背景跑 B8 營收補抓**（不需改程式，約 8 分鐘，指令見 B8-4）。 | 結束後 `monthly_revenue` 最早月份為 2023/01 |
| 1 | P1、P3、P7、P4：只動 `app.js`、`app.css`、`stock.js`（指標卡日期）。 | T-P1-*、T-P3-*、T-P7-*、T-P4-1 |
| 2 | A1：`db.py` → `setup-db` → `daily.py`、`history.py`、`__main__.py` → `export.py` → `app.js`。B8 補抓結束後，再跑加權指數補抓（約 11 分鐘）。 | T-A1-* |
| 3 | P2、P5：`export.py`、`stock.js`。 | T-P2-*、T-P5-* |
| 4 | B8：`export.py`、`stock.js`、`app.css`。 | T-B8-* |
| 5 | B10：`db.py` → `setup-db` → `alerts.py`、`__main__.py` → `export.py` → `app.js`、`stock.js`、`app.css`。 | T-B10-* |
| 6 | `tests/test_iter01.py`，`python3 -m twstock export`，`serve --port 8001` 自測，關閉伺服器。 | 全部 T-* |

> 工作量評估：B10 與 P5 都不需延到第 2 輪。P5 是匯出一個陣列＋前端 10 行；B10 是一個約 80 行的新收集器＋前端標記，資料量小、無需補抓。

### 共通約定

- 日期一律以 `YYYY-MM-DD` 字串匯出；畫面用 `app.js` 既有的 `md()`（`2026-10-29` → `10/29`）。本輪新增的日期都**帶自己的日期欄位**，不與 `date`（行情日）、`flow_date`（法人日）混用。
- 「資料日」= `latest.json` 的 `date`（匯出時 `daily_prices` 的最大日期，Python 端為 `latest_date`）。
- 前端新函式放在使用它的檔案；`stock.js` 可以直接用 `app.js` 的全域函式（`md`、`fmt`、`sgn`、`cls`、`esc`、`css`），比照現況。
- 新的收集步驟失敗一律 `except FetchError` 印 `⚠️` 後繼續，不影響已寫入的當日行情（比照 `cmd_collect` 對期貨的處理）。解析一律用 `row.get()`，欄位缺漏時略過該列，不丟 `KeyError`。

---

## P1. 法人資料標示日期

### P1-1 對應驗收條件
1. 以目前資料（`date=2026-10-29`、`flow_date=2026-10-28`）開今日頁，「法人買超」「法人賣超」表頭顯示「10/28」，且看得到「法人資料尚未更新」提示。
2. 排行頁、自選頁、個股頁的法人欄位或指標卡都看得到「10/28」。
3. `flow_date` 改成與 `date` 相同時，提示行不出現，表頭日期顯示同一天。

### P1-2 資料來源
不需新資料。使用 `latest.json` 既有的 `date`、`flow_date`。

### P1-3 資料庫／P1-4 收集流程／P1-5 匯出
無變更。

### P1-6 畫面

新增 `app.js` 函式（放在 `md` 定義之後）：

```js
// 法人資料比行情晚公布時的提示；兩者同日回傳空字串
function flowNote() {
  const L = App.latest;
  return L.flow_date === L.date ? ''
    : `<div class="flow-note">法人資料尚未更新：收盤、漲跌為 ${md(L.date)}，法人欄位為 ${md(L.flow_date)}</div>`;
}
```

所有顯示法人數字的位置與標示方式：

| 位置 | 現況 | 修改後 |
|---|---|---|
| 今日頁「三大法人」卡 | 標題已有 `（10/28）` | 不變（P4 另加口徑說明） |
| 今日頁「法人買超」「法人賣超」表 | 表頭右側 `當日，億` | 改為 `${md(L.flow_date)}，億` → 「10/28，億」；兩表所在 `<section>` **之前**插入 `${flowNote()}` |
| 排行頁、自選頁表格（`stockTable()`） | 無日期 | 表格上方（`tbl-wrap` 之前）先放 `flowNote()`，再放一行說明（見下） |
| 泡泡圖成分股表（`showGroup()`） | 無日期 | `#gMeta` 末尾加 `　法人 ${md(flow_date)}` |
| 個股頁指標卡：法人1日、法人5日、外資5日、投信5日 | 無日期 | 卡片內加副標 `<div class="s">`：法人1日 → 「10/28」；三張 5 日卡 → 「至 10/28」 |
| 個股頁 K 線下方法人資訊列 | 已有落後日期邏輯 | 不變 |

`stockTable()` 表格上方的說明文字（`span` 為 `'1'` 或 `'5'`）：

- 1 日：`法人欄位為 10/28 當日買賣超（億）`
- 5 日：`法人欄位為截至 10/28 的近 5 日累計（億）`

HTML：`<div class="muted small tbl-cap">…</div>`。

個股頁指標卡：把 `metrics` 陣列元素擴充為 `[標籤, 值, class, 副標]`，渲染時 `副標` 存在才輸出 `<div class="s">${副標}</div>`（P2 也用到）。

CSS（`app.css`）：

```css
.flow-note{font-size:12px;padding:6px 10px;border-radius:8px;background:var(--q-rot);border-left:3px solid var(--amber);margin:0 0 8px}
.tbl-cap{margin-bottom:6px}
```

今日頁的 `flowNote()` 直接輸出在法人表的 `<section class="sec grid g2">` 之前，不另包容器。

- 桌機：提示是一整行橫條。手機 375px：文字自動換成 2 行，不需特別處理。
- 無資料：`flow_date` 一定存在（`export_all` 沒有法人日會直接中止），不需處理缺值。

### P1-7 邊界情況
- `date === flow_date`（法人已更新）：不顯示提示，表頭與說明顯示同一天。
- 個股沒有法人資料（`n1` 不存在）：值顯示 `--`，副標日期照常顯示。
- 休市日不影響：兩個日期都來自資料庫。

### P1-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P1-1 | 開 `http://localhost:8001/#/today`，Console 執行：`[...document.querySelectorAll('.sec-h .muted.small')].map(e=>e.textContent).filter(t=>t.includes('億'))` | 含兩個 `"10/28，億"`；`document.querySelector('.flow-note').textContent.includes('法人資料尚未更新')` 為 `true` |
| T-P1-2 | 開 `#/rank` 與 `#/watch`（先把 2330 加入自選） | `document.querySelector('.tbl-cap').textContent.includes('10/28')` 為 `true`；`.flow-note` 存在 |
| T-P1-3 | 開 `#/stock/2330` | `[...document.querySelectorAll('.metrics .stat')].filter(e=>/法人1日|法人5日|外資5日|投信5日/.test(e.querySelector('.l').textContent)).every(e=>e.textContent.includes('10/28'))` 為 `true` |
| T-P1-4 | 開 `#/bubble`，點任一泡泡 | `#gMeta` 文字含「法人 10/28」 |
| T-P1-5 | 今日頁 Console：`App.latest.flow_date = App.latest.date; renderToday()`；再 `location.hash='#/rank'` | 兩頁都沒有 `.flow-note`；今日頁表頭為「10/29，億」，排行說明為「10/29」 |

---

## P3. 預測模型降級為「籌碼因子觀察」

### P3-1 對應驗收條件
1. 目前資料下卡片標題為「籌碼因子觀察」，初始狀態找不到「偏多」「偏空」「中性」與「上漲機率」數字。
2. 展開摺疊區後看得到命中率 52.9%、基準 54.4%。
3. `forecast.backtest.acc` 改成大於 `baseline` 後，恢復原本大字與機率呈現。

### P3-2～P3-5
不需新資料；不改 `analysis/forecast.py`、不改匯出。

### P3-6 畫面（`app.js` `oiHTML()`）

判斷式沿用現有變數：`const beat = B.acc > B.baseline;`。**模型未勝過基準 ⇔ `!beat`（即 `acc <= baseline`）**。

把現有 `fc` 拆成三段字串：

- `head`：現有 `<div class="fc-head">`（大字 `FC.view`、「下一交易日上漲機率 xx%」、「依 MM/DD 收盤後未平倉」）。
- `factors`：現有 `<div class="fc-factors">…</div>`，其中說明文字依狀態：
  - `beat`：維持「長條往右 = 推升上漲機率，往左 = 壓低」
  - `!beat`：改為「長條往右 = 對隔日上漲有利，往左 = 不利」（不可出現「上漲機率」四字）
- `bt`：現有 `fc-bt`（回測文字）＋`fc-recent`（最近 10 次）＋模型說明那一行。

組合：

```js
fc = beat ? head + factors + bt
  : `<div class="muted small" style="margin-bottom:8px">依 ${md(FC.date)} 收盤後期貨法人未平倉，各因子相對近 60 日的方向與強弱</div>
     ${factors}
     <details class="fc-more"><summary>模型回測（實驗性，未勝過基準）</summary>${head}${bt}</details>`;
```

卡片標題：`<h2>${FC && !beat ? '籌碼因子觀察' : '大盤漲跌預測'}</h2>`（`FC` 為 null 時維持原標題與「期貨法人資料不足，無法預測」）。`beat` 需要在組標題前算好（把 `B`、`beat` 提到 `if (FC)` 之外，或另以變數保存標題）。

`<details>` 預設不加 `open`，即預設摺疊。

CSS：

```css
.fc-more{margin-top:6px}
.fc-more summary{cursor:pointer;font-size:12px;color:var(--text2);padding:4px 0}
.fc-more[open] summary{margin-bottom:8px}
```

- 桌機：維持 `g2` 右欄。手機：`g2` 變單欄，摺疊區寬度 100%，無需特別處理。

### P3-7 邊界情況
- `FC` 為 null：維持原狀。
- `acc === baseline`：視為未勝過（降級）。
- `FC.recent` 為空：摺疊區內「最近 10 次」只剩標籤，與現況相同。

### P3-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P3-1 | 開今日頁，Console：`const v=$('#view').cloneNode(true); v.querySelectorAll('details').forEach(d=>d.remove()); [/偏多|偏空|中性|上漲機率/.test(v.textContent), $('.fc-more').open, [...document.querySelectorAll('h2')].some(h=>h.textContent==='籌碼因子觀察')]` | `[false, false, true]` |
| T-P3-2 | 點「模型回測（實驗性，未勝過基準）」展開 | 看得到「命中率 52.9%」「基準 54.4%」、大字「中性」與「上漲機率 54.9%」；`$('.fc-more').open === true` |
| T-P3-3 | Console：`App.latest.forecast.backtest.acc = 0.6; renderToday()` | 標題為「大盤漲跌預測」；`$('.fc-more') === null`；`$('.fc-view')` 可見；說明文字為「長條往右 = 推升上漲機率，往左 = 壓低」 |
| T-P3-4 | Console：`App.latest.forecast.backtest.acc = App.latest.forecast.backtest.baseline; renderToday()` | 與 T-P3-1 相同（相等視為未勝過） |

---

## P7. 排行流動性門檻＋修正說明文字

### P7-1 對應驗收條件
1. 漲幅排行、門檻預設 0.5 億時，前 50 名成交額皆 ≥ 0.5 億；5245 智晶、8291 尚茂不在榜上（兩檔 10/29 成交額 0.04 億）。
2. 門檻切到「不限」，結果與修改前一致。
3. 重新整理後門檻保留。
4. 說明文字不再有「同時改變排序」。

### P7-2～P7-5
不需新資料，使用 `latest.json` 各股 `tv`（億）。

### P7-6 畫面（`app.js` `renderRank()`）

- 新增 `const minTv = localStore('rtv', '0.5');`（字串，`'0'`、`'0.5'`、`'1'`、`'5'`）。
- 篩選條件加上 `&& (s.tv ?? 0) >= Number(minTv)`，套用到所有排行種類（含法人、連買、漲跌幅、成交額）。`'0'` 時 `0 >= 0` 恆真，結果與修改前完全相同。
- 選單放在 `rankSel` 之前：

```js
<select id="tvSel" class="sel" aria-label="成交額門檻">${[['0', '成交額不限'], ['0.5', '成交額 ≥ 0.5 億'], ['1', '成交額 ≥ 1 億'], ['5', '成交額 ≥ 5 億']]
  .map(([v, t]) => `<option value="${v}"${v === minTv ? ' selected' : ''}>${t}</option>`).join('')}</select>
```

- 事件：`$('#tvSel').addEventListener('change', e => { localStore('rtv', null, e.target.value); renderRank(); });`
- 自選頁不套用（`renderWatch()` 不變）。
- 說明文字定稿（取代現有 `<div class="muted small" …>` 內容，含 P4 的「不含 ETF」）：

> 金額 = 買賣超張數 × 當日收盤，不含 ETF。成交額門檻以資料日成交額篩選，套用到所有排行。「1日／5日」只切換法人、外資、投信、自營買賣超排行與表格法人欄位的天數；漲幅、跌幅、成交額與連買排行不受影響。連買為連續買超天數，天數相同時以近 5 日金額排序。

- 手機 375px：`.sec-h` 已是 `flex-wrap:wrap`，選單會換行，不需改 CSS。

### P7-7 邊界情況
- 今日無成交（`nt`）：`tv` 為 0，門檻非「不限」時自然排除。
- `tv` 為 null：以 0 處理。
- 篩選後不足 50 檔：顯示實際筆數；0 筆時表格只有表頭（與現況一致）。
- `localStore` 讀不到（私密視窗）：回傳預設 `'0.5'`。

### P7-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P7-1 | `#/rank`，排行選「漲幅」，門檻保持預設 | Console：`[...document.querySelectorAll('tr[data-code]')].map(r=>r.dataset.code)` 不含 `'5245'`、`'8291'`；`[...document.querySelectorAll('tr[data-code]')].every(r=>App.latest.stocks[r.dataset.code].tv>=0.5)` 為 `true`；`$('#tvSel').value==='0.5'` |
| T-P7-2 | 門檻切「成交額不限」 | 列出的代號順序等於：`Object.entries(App.latest.stocks).filter(([,s])=>s.p!=null).sort((a,b)=>b[1].p-a[1].p).slice(0,50).map(x=>x[0])`（修改前的邏輯；同漲幅時順序可能不同，比對集合即可） |
| T-P7-3 | 選「≥ 1 億」後重新整理 | `$('#tvSel').value==='1'`；`localStorage.getItem('tw.rtv')==='1'` |
| T-P7-4 | 讀排行頁說明 | 不含「同時改變排序」；含「不含 ETF」與「漲幅、跌幅、成交額與連買排行不受影響」 |
| T-P7-5 | 門檻 0.5 億時切「外資連買」「成交額」「跌幅」 | 每一列成交額欄 ≥ 0.5 億 |

---

## A1. 加權指數／櫃買指數卡片＋近 60 日走勢線

### A1-1 對應驗收條件
1. 加權指數 10/29 收盤 46,368.33、漲跌 −667.25、−1.42%。
2. 櫃買指數 10/29 收盤 387.37、漲跌 −7.24、約 −1.83%。
3. 加權走勢線 60 點、最後一點 = 當日收盤；櫃買走勢線涵蓋 10/01 起並標示起始日。
4. 交易日執行 `collect`，指數表新增當日資料，網站自動更新。
5. 模擬 `tpex_index` 失敗，當日行情與法人照常寫入，櫃買卡片顯示「--」，整頁不壞。
6. 重複 `setup-db` 不報錯。

### A1-2 資料來源（2026-10-30 實測）

**加權指數：`MI_INDEX`（`fetch_twse_daily` 已在呼叫，不增加請求）**

- `GET https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?response=json&date=YYYYMMDD&type=ALLBUT0999`
- 回應 `tables[]` 中，`title` 含 `價格指數(臺灣證券交易所)` 的表（實際 title：`115年10月29日 價格指數(臺灣證券交易所)`）。
- `fields`：`['指數', '收盤指數', '漲跌(+/-)', '漲跌點數', '漲跌百分比(%)', '特殊處理註記']`
- 目標列：`指數 == '發行量加權股價指數'`（該表第 2 列；第 1 列是寶島指數，**不可用列序**）。實測：`['發行量加權股價指數', '46,368.33', "<p style ='color:green'>-</p>", '667.25', '-1.42', '']`
- 取欄：`收盤指數`→close；`漲跌點數`（絕對值）＋`漲跌(+/-)` 含 `-` 則取負 → change。漲跌幅不存，匯出時以 `_pct(close, change)` 計算（−667.25 ÷ 47,035.58 = −1.4186% → −1.42，與官方一致）。
- 指數沒有開高低，存 NULL。

**加權指數歷史：仍用 `MI_INDEX` 逐日（決定）**

- `rwd/zh/indicesReport/MI_5MINS_HIST?response=json&date=20261001` 實測**單次失敗**：回應不是 JSON（`Expecting value`，同時段 `MI_INDEX` 正常，推測路徑錯誤而非被封鎖）。依規定未重試。
- 改用 `MI_INDEX` 逐日補抓：好處是與每日收集**共用同一個解析函式**，不必再寫一套解析與漲跌計算；代價是 168 次請求（約 11 分鐘），可中斷重跑。若下一輪要做 A1-延伸（指數日 K 需要開高低），再驗證 `rwd/zh/TAIEX/MI_5MINS_HIST`（推測的正確路徑，**未驗證**）。

**櫃買指數：`tpex_index`**

- `GET https://www.tpex.org.tw/openapi/v1/tpex_index`（無參數）
- 回應：JSON 陣列，只含**本月**每日資料，實測 18 筆（20261001～20261029）：`{"Date": "20261029", "Open": "396.40", "High": "397.17", "Low": "385.26", "Close": "387.37", "Change": "-7.24"}`
- `Change` 本身帶正負號。漲跌幅匯出時計算：−7.24 ÷ 394.61 = −1.83%。

### A1-3 資料庫（`db.py` 的 `DDL` 清單，放在 `industry_chains` 之後、索引之前）

```sql
-- 大盤指數每日收盤（TAIEX 取自 MI_INDEX，沒有開高低；TPEX 取自櫃買 OpenAPI）
IF OBJECT_ID('market_index') IS NULL
CREATE TABLE market_index (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    index_code  NVARCHAR(10)  NOT NULL,   -- TAIEX 加權指數 / TPEX 櫃買指數
    trade_date  DATE          NOT NULL,
    open_price  DECIMAL(10,2) NULL,
    high_price  DECIMAL(10,2) NULL,
    low_price   DECIMAL(10,2) NULL,
    close_price DECIMAL(10,2) NOT NULL,
    change      DECIMAL(10,2) NULL,
    created_at  DATETIME      NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_market_index UNIQUE (index_code, trade_date)
)
```

- MERGE 鍵：`(index_code, trade_date)`。
- `setup_database()` 最後的 print 清單加上 `market_index`（B10 再加 `stock_alerts`）。
- 唯一鍵已涵蓋查詢需求，不另建索引。

### A1-4 收集流程

**`daily.py`**

1. 常數：`PRICES, INSTI, INDEX = "prices", "insti", "index"`；`ALL_DATASETS = (PRICES, INSTI)` **不變**（INDEX 只在補抓指數時單獨指定；抓 PRICES 時加權指數會一併寫入）。
2. 新增純函式（可單獨測試）：

```python
def parse_taiex(data: dict, d: date):
    """MI_INDEX 回應中的發行量加權股價指數；找不到回傳 None。"""
    for table in data.get("tables", []):
        if "價格指數(臺灣證券交易所)" not in (table.get("title") or ""):
            continue
        idx = {f: i for i, f in enumerate(table.get("fields", []))}
        for row in table.get("data", []):
            if str(row[idx["指數"]]).strip() != "發行量加權股價指數":
                continue
            # 漲跌點數是絕對值，正負號在「漲跌(+/-)」欄（HTML 片段），與個股相同
            change = clean_number(row[idx["漲跌點數"]])
            if change is not None and "-" in str(row[idx["漲跌(+/-)"]]):
                change = -change
            close = clean_number(row[idx["收盤指數"]])
            return {"index_code": "TAIEX", "trade_date": d.isoformat(),
                    "close_price": close, "change": change} if close is not None else None
    return None
```

3. `fetch_twse_daily(d)` 改為回傳 `(個股列表, 加權指數 dict 或 None)`；休市回傳 `([], None)`。原本的個股解析內容不變，只是在 `stat == "OK"` 後多算 `taiex = parse_taiex(data, d)`，最後 `return results, taiex`。docstring 改為「上市每日收盤行情與加權指數；休市回傳 ([], None)」。
4. `merge_market_index(cursor, rows)`：比照 `merge_futures` 寫法，`OPENJSON(?) WITH (index_code NVARCHAR(10), trade_date DATE, open_price DECIMAL(10,2), high_price DECIMAL(10,2), low_price DECIMAL(10,2), close_price DECIMAL(10,2), change DECIMAL(10,2))`，`ON t.index_code = s.index_code AND t.trade_date = s.trade_date`，MATCHED 更新五個數值欄，NOT MATCHED 新增。
5. `collect_for_date(d, datasets)`：

```python
taiex = None
if PRICES in datasets:
    for market, fetch_q, fetch_pe in (...):          # 原迴圈
        rows = fetch_q(d)
        if market == "TWSE":
            rows, taiex = rows                       # 上市行情與加權指數來自同一個 MI_INDEX 回應
        ...（原邏輯不變）
elif INDEX in datasets:
    _, taiex = fetch_twse_daily(d)                   # 只補指數：同一個請求，個股列不寫入
    if taiex is None:
        print("  ℹ️  無加權指數（休市或尚未公布），略過此日")
        return False
if taiex:
    counts["加權指數"] = 1
...
# 寫入區（同一個交易內）：
if taiex:
    merge_market_index(cursor, [taiex])
```

   - PRICES 有抓到個股但 `taiex is None`（表名改版）：印 `⚠️  MI_INDEX 找不到加權指數表`，個股照常寫入。
   - 維持「全部抓完才連資料庫、一次 commit」。

6. 櫃買指數：

```python
TPEX_OPENAPI = "https://www.tpex.org.tw/openapi/v1"

def fetch_tpex_index() -> list:
    """櫃買指數：OpenAPI 只提供本月每日開高低收（Date 為西元 YYYYMMDD）。"""
    data = request("GET", f"{TPEX_OPENAPI}/tpex_index")
    if not isinstance(data, list):
        raise FetchError("櫃買指數回應格式不符")
    rows = []
    for r in data:
        ds, close = str(r.get("Date") or ""), clean_number(r.get("Close"))
        if close is None or not (ds.isdigit() and len(ds) == 8):
            continue
        rows.append({"index_code": "TPEX", "trade_date": f"{ds[:4]}-{ds[4:6]}-{ds[6:]}",
                     "open_price": clean_number(r.get("Open")), "high_price": clean_number(r.get("High")),
                     "low_price": clean_number(r.get("Low")), "close_price": close,
                     "change": clean_number(r.get("Change"))})
    return rows

def collect_tpex_index() -> int:
    """寫入本月全部日期（MERGE，可重複執行）。"""
    rows = fetch_tpex_index()
    if rows:
        conn = db.connect()
        try:
            merge_market_index(conn.cursor(), rows)
            conn.commit()
        finally:
            conn.close()
    print(f"  📈 櫃買指數：{len(rows)} 天")
    return len(rows)
```

**`__main__.py` `cmd_collect`**：在期貨 `try` 區塊之後、產業鏈之前加：

```python
try:
    collect_tpex_index()
except FetchError as e:
    print(f"  ⚠️  櫃買指數抓取失敗：{e}")
```

並在函式開頭 import `collect_tpex_index`。加權指數不需另外呼叫（`collect_for_date` 已寫入）。

**`history.py`（補抓入口）**

- `from .daily import ALL_DATASETS, INDEX, INSTI, PRICES, collect_for_date`
- `_TABLE[INDEX] = "market_index"`；新增 `_FILTER = {INDEX: "AND index_code = 'TAIEX'"}`，`dates_in_db` 的 SQL 改為 `f"... WHERE trade_date BETWEEN ? AND ? {_FILTER.get(dataset, '')}"`（否則櫃買 10 月的資料會讓 10 月的加權指數被誤判為已有）。
- `SECONDS_PER_DAY[INDEX] = 4`。
- `__main__.py` 的 `history --only` 選項改為 `choices=["prices", "insti", "index"]`，說明改為「只抓指定資料集（index = 只補加權指數）」。

**補抓指令與時間**（B8 補抓結束後再執行；PM 要求兩個補抓不要同時跑）：

```bash
python3 -m twstock history --start 2026-02-23 --end 2026-10-29 --only index
```

- 168 個交易日 × 約 4 秒 ≈ **11 分鐘**（`www.twse.com.tw` 節流 3.5 秒＋回應時間）。
- 中途被封：程式印「在 YYYY-MM-DD 停止」，等 30 分鐘以上用同一指令重跑，已寫入的日期會跳過。
- 櫃買指數：只能補本月（執行一次 `collect` 或 `python3 -c "from twstock.collectors.daily import collect_tpex_index; collect_tpex_index()"`）。

每日 `collect` 增加的時間：櫃買指數 1 次請求（約 3 秒）；加權指數 0 次。

### A1-5 匯出（`export.py`）

常數 `INDEX_DAYS = 60`。在 `conn.close()` 前查詢：

```python
index_rows = defaultdict(list)
for code, d, c, ch in cur.execute(
        "SELECT index_code, trade_date, close_price, change FROM market_index ORDER BY index_code, trade_date"):
    index_rows[code].append((d, c, ch))
```

組成 `latest["index"]`（放在 `"insti"` 之後）：

| 欄位 | 型別 | 單位 | 範例 | 說明 |
|---|---|---|---|---|
| `index` | object | | | 鍵為 `TAIEX`、`TPEX`；某指數沒有資料時**該鍵不存在** |
| `index.X.date` | string | 日期 | `"2026-10-29"` | 該指數最新一筆的日期（可能早於 `date`） |
| `index.X.c` | number | 點 | `46368.33` | 收盤 |
| `index.X.ch` | number\|null | 點 | `-667.25` | 漲跌 |
| `index.X.p` | number\|null | % | `-1.42` | `_f(_pct(c, ch))` |
| `index.X.from` | string | 日期 | `"2026-07-31"` | 走勢線第一點日期 |
| `index.X.s` | number[] | 點 | `[…, 46368.33]` | 最近至多 60 筆收盤，舊到新 |

範例（補抓後）：

```json
"index":{"TAIEX":{"date":"2026-10-29","c":46368.33,"ch":-667.25,"p":-1.42,"from":"2026-07-31","s":[…60 筆…]},
         "TPEX":{"date":"2026-10-29","c":387.37,"ch":-7.24,"p":-1.83,"from":"2026-10-01","s":[…18 筆…]}}
```

大小：每個指數約 0.6 KB，合計約 **+1.2 KB**（latest.json 664 KB → +0.2%）。走勢線不需互動，所以不匯出每日日期。

### A1-6 畫面（`app.js` 今日頁）

位置：`renderToday()` 的第一個 `<section>` **之前**新增一列：

```html
<section class="sec grid g-stats">${indexCard(L.index?.TAIEX, '加權指數')}${indexCard(L.index?.TPEX, '櫃買指數')}</section>
```

原「上市／上櫃成交額＋三大法人」三張卡留在第二列（與 PM 相依性建議一致）。

```js
function spark(vals) {
  // 迷你走勢線：不需互動，以 SVG 折線畫在 100×34 的座標內
  if (!vals || vals.length < 2) return '';
  const lo = Math.min(...vals), hi = Math.max(...vals), n = vals.length;
  const pts = vals.map((v, i) => `${(i / (n - 1) * 100).toFixed(2)},${(hi > lo ? 2 + (hi - v) / (hi - lo) * 30 : 17).toFixed(2)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="var(--${vals.at(-1) >= vals[0] ? 'up' : 'dn'})" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
}

function indexCard(x, name) {
  if (!x) return `<div class="card stat idx"><div class="l">${name}</div><div class="v num">--</div><div class="s">暫無資料</div></div>`;
  const stale = x.date < App.latest.date;
  return `<div class="card stat idx">
      <div class="l">${name}<span class="muted">　${md(x.date)}${stale ? '（尚未更新）' : ''}</span></div>
      <div class="v num ${cls(x.ch)}">${fmt(x.c, 2)}</div>
      <div class="s num ${cls(x.ch)}">${x.ch > 0 ? '▲' : x.ch < 0 ? '▼' : ''} ${fmt(Math.abs(x.ch ?? 0), 2)} (${sgn(x.p)}%)</div>
      ${spark(x.s)}
      <div class="s">${x.s.length >= 60 ? '近 60 個交易日收盤' : `資料自 ${md(x.from)} 起（${x.s.length} 個交易日）`}</div>
    </div>`;
}
```

畫面文案：

| 狀態 | 顯示 |
|---|---|
| 正常 | 「加權指數　10/29」／大字「46,368.33」／「▼ 667.25 (-1.42%)」／走勢線／「近 60 個交易日收盤」 |
| 櫃買資料不足 60 日 | 底行「資料自 10/01 起（18 個交易日）」 |
| 指數日期早於資料日 | 標題列「櫃買指數　10/28（尚未更新）」 |
| 無資料 | 大字「--」，副標「暫無資料」 |

走勢線顏色：最後一點 ≥ 第一點用 `--up`（紅），否則 `--dn`（綠），與網站漲紅跌綠一致。

CSS：

```css
.idx .spark{display:block;width:100%;height:36px;margin:6px 0 2px}
```

- 桌機：兩張卡各佔一半（`g-stats` 的 `auto-fit` 自動處理）。
- 手機 375px：內容寬 343px，`minmax(150px,1fr)` 會排成兩欄各約 166px；大字「46,368.33」20px 約 100px、漲跌行約 115px，皆放得下，不需另寫 media query。

### A1-7 邊界情況

| 情況 | 處理 |
|---|---|
| 休市日 | `collect_for_date` 回傳 False，`cmd_collect` 不會呼叫櫃買指數。`history` 依 `HOLIDAYS` 跳過。 |
| MI_INDEX 尚未公布（`stat != OK`） | 回傳 `([], None)`，與現行「上市無資料，略過此日」相同。 |
| MI_INDEX 改版找不到指數表 | `taiex=None`，個股照寫，印警告；卡片顯示前一日並標「（尚未更新）」。 |
| `tpex_index` 18:30 時尚未更新到當日 | 寫入已有的日期；卡片顯示前一日＋「（尚未更新）」；隔天收集時 MERGE 會補上。**月底最後一個交易日若當天沒抓到，次月端點只給新月份，該日會永久缺漏**，走勢線少一點，不影響其他功能（列入已知限制）。 |
| `tpex_index` 回 HTML／被限流 | `request` 退避重試後丟 `FetchError`，`cmd_collect` 印警告繼續；當日行情、法人已在 `collect_for_date` 內 commit。 |
| `tpex_index` 回空陣列或欄位空白 | 略過該列；0 筆時不連資料庫。 |
| 指數平盤 | `漲跌(+/-)` 為空白，change = 0，顯示「0.00 (0.00%)」灰色。 |
| `collect --date` 補過去日期 | 櫃買仍抓本月（無害）。 |

### A1-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-A1-1 | `python3 tests/test_iter01.py` | `test_parse_taiex` 通過：用附錄 A 的實測片段，`close_price == 46368.33`、`change == -667.25`；把正負號欄換成 `<p style ='color:red'>+</p>` 得 `+667.25`；點數 `0.00`、正負號 `<p> </p>` 得 `0`；`tables` 沒有價格指數表時回傳 `None` |
| T-A1-2 | 補抓後 SQL：`SELECT close_price, change FROM market_index WHERE index_code='TAIEX' AND trade_date='2026-10-29'` | `46368.33, -667.25` |
| T-A1-3 | SQL：`SELECT COUNT(*) FROM market_index WHERE index_code='TAIEX' AND trade_date BETWEEN '2026-02-23' AND '2026-10-29'` | 168（與 `daily_prices` 的交易日數相同：`SELECT COUNT(DISTINCT trade_date) FROM daily_prices WHERE trade_date <= '2026-10-29'`） |
| T-A1-4 | `python3 -c "import json;x=json.load(open('site/data/latest.json'))['index'];t,o=x['TAIEX'],x['TPEX'];assert (t['c'],t['ch'],t['p'])==(46368.33,-667.25,-1.42);assert (o['c'],o['ch'],o['p'])==(387.37,-7.24,-1.83);assert len(t['s'])==60 and t['s'][-1]==t['c'];assert o['from']<='2026-10-01' and o['s'][-1]==o['c'];print('ok')"` | 印 `ok`（資料日仍為 10/29 時） |
| T-A1-5 | 開今日頁 | 第一列兩張卡：「加權指數　10/29」46,368.33、▼ 667.25 (-1.42%)；「櫃買指數　10/29」387.37、▼ 7.24 (-1.83%)；櫃買底行「資料自 10/01 起（18 個交易日）」。Console：`document.querySelectorAll('.idx .spark polyline')[0].getAttribute('points').split(' ').length === 60` |
| T-A1-6 | 下一個交易日 18:30 後執行 `python3 -m twstock collect` | 輸出含「加權指數 1 筆」與「📈 櫃買指數：N 天」；`SELECT MAX(trade_date) FROM market_index GROUP BY index_code` 兩者皆為當日；重新整理今日頁，兩張卡日期為當日 |
| T-A1-7 | 模擬櫃買失敗：`python3 -c "import twstock.collectors.daily as d; from twstock.fetch import FetchError; d.collect_tpex_index=lambda: (_ for _ in ()).throw(FetchError('模擬失敗')); from twstock.__main__ import main; main(['collect','--date','2026-10-29','--no-revenue'])"` | 輸出依序有「✅ 寫入：TWSE … 筆」、「⚠️  櫃買指數抓取失敗：模擬失敗」、「✅ 匯出完成」；`SELECT COUNT(*) FROM daily_prices WHERE trade_date='2026-10-29'` 與執行前相同（約 1,99x 筆，MERGE 不會重複） |
| T-A1-8 | 今日頁 Console：`delete App.latest.index.TPEX; renderToday()`；再 `delete App.latest.index; renderToday()` | 櫃買卡片顯示「--」「暫無資料」，其餘區塊正常；刪掉整個 `index` 時兩張卡都是「--」，頁面不報錯 |
| T-A1-9 | 連續執行 `python3 -m twstock setup-db` 兩次 | 兩次都成功，無錯誤；`SELECT OBJECT_ID('market_index')` 不為 NULL |
| T-A1-10 | 手機寬度（DevTools 375×812）開今日頁 | 兩張指數卡並排，數字與漲跌不換行、不溢出 |

---

## P2. 「52 週高／低」改為實際區間

### P2-1 對應驗收條件
1. 2330 個股頁看不到「52週」，看到「區間高／區間低」與「自 2026/02/23」。
2. 數值與修改前相同。
3. 日後資料滿 1 年時自動改回「52週」。

### P2-2～P2-4
不需新資料、不改資料表與收集。

### P2-5 匯出（`export.py`）

計算基準（決定）：**以「資料日 − 365 天」為 52 週起點 `w52_start`（現有變數），比較「資料庫最早日線日期」與「個股自己的第一筆日線日期」**。新上市股票各自計算。

```python
db_first = min(rows[0][0] for rows in prices.values())   # 全市場最早日線（目前 2026-02-23）
...
latest["hl_from"] = str(db_first) if db_first > w52_start else None
# 每檔：個股第一筆日線晚於「全市場起點」與「52 週起點」兩者時，才另外標示
first = d_[0]
**({"hf": str(first)} if first > max(db_first, w52_start) else {}),
```

| 欄位 | 位置 | 型別 | 範例 | 說明 |
|---|---|---|---|---|
| `hl_from` | latest.json 頂層 | string\|null | `"2026-02-23"` | 全市場資料未滿 52 週時 = 最早日線日期；滿 52 週時為 `null` |
| `hf` | `stocks.{代號}` | string（可省略） | `"2026-03-25"` | 該股票第一筆日線晚於全市場起點時才有（目前 46 檔，例如 7811） |

高低點數值計算（`h52`、`l52`）**不變**。大小：`hl_from` 25 B＋`hf` 約 46 × 18 B ≈ **+0.9 KB**。

### P2-6 畫面（`stock.js` 指標卡）

```js
const hlFrom = s?.hf ?? App.latest.hl_from;          // null → 已滿 52 週
const hlSub = hlFrom ? '自 ' + hlFrom.replaceAll('-', '/') : '';
// metrics 陣列中原本的兩項改為：
[hlFrom ? '區間高' : '52週高', pfmt(s?.h52), '', hlSub], [hlFrom ? '區間低' : '52週低', pfmt(s?.l52), '', hlSub],
```

- 文案：標籤「區間高」「區間低」，副標「自 2026/02/23」（新上市股為自己的日期，例如「自 2026/03/25」）。
- 滿 52 週：標籤「52週高」「52週低」，無副標。
- 無資料（`s` 不存在，例如今天停牌）：數值 `--`；`hlFrom` 退回 `App.latest.hl_from`。

### P2-7 邊界情況
- 新上市股票資料只有數天：`hf` 為上市日，標籤「區間高」。
- 日後補抓到 1 年以上：`db_first <= w52_start` → `hl_from = null`；在 `w52_start` 之後才上市的股票仍有 `hf`，顯示「區間高　自 上市日」。
- 第一筆日線無成交（開高低收為 null）：`hf` 仍以第一筆資料列日期標示，差距最多數天，可接受。

### P2-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P2-1 | 開 `#/stock/2330` | Console：`!$('.metrics').textContent.includes('52週') && $('.metrics').textContent.includes('區間高') && $('.metrics').textContent.includes('自 2026/02/23')` 為 `true` |
| T-P2-2 | 比對數值 | 區間高 2,590、區間低 1,760（與修改前 `h52`、`l52` 相同） |
| T-P2-3 | 開 `#/stock/7811` | 副標為「自 2026/03/25」 |
| T-P2-4 | 2330 頁 Console：`App.latest.hl_from = null; renderStock('2330')` | 標籤變回「52週高／52週低」，無副標（模擬資料滿 1 年） |
| T-P2-5 | `python3 -c "import json,datetime as t;L=json.load(open('site/data/latest.json'));assert L['hl_from']=='2026-02-23';assert L['stocks']['7811']['hf']=='2026-03-25';assert 'hf' not in L['stocks']['2330'];print('ok')"` | 印 `ok` |

---

## P4. 成交額與法人金額註明口徑

### P4-1 對應驗收條件
今日頁三張卡與排行頁說明都看得到口徑說明；數值不變。

### P4-2～P4-5
無資料變更。

### P4-6 畫面（`app.js`）

| 位置 | 新增文案 | 實作 |
|---|---|---|
| 今日頁「上市成交額」「上櫃成交額」卡（`mk()`） | `一般股票，不含 ETF` | 在漲跌家數那行之後加 `<div class="s">一般股票，不含 ETF</div>` |
| 今日頁「三大法人（10/28）」卡 | `估算：買賣超張數 × 收盤價，不含 ETF` | 在外資／投信／自營那行之後加 `<div class="s">估算：買賣超張數 × 收盤價，不含 ETF</div>` |
| 排行頁說明 | 「不含 ETF」 | 見 P7 定稿文字 |

手機：`.s` 為 12px，文字約 17 字，在 166px 寬卡片會換成 2 行，可接受。

### P4-7 邊界情況
無。

### P4-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P4-1 | 今日頁 Console：`[...document.querySelectorAll('.g-stats .stat')].map(e=>e.textContent).filter(t=>/不含 ETF/.test(t)).length` | `3`（上市、上櫃、三大法人） |
| T-P4-2 | 比對卡片數值與修改前截圖 | 成交額、漲跌家數、法人金額完全相同 |

---

## B8. 月營收 3 年走勢、累計年增、創新高標記

### B8-1 對應驗收條件
1. `monthly_revenue` 最早為 2023/01，2023/01～2025/12 每月公司數與 2026 年同一量級（約 1,700～2,000）。
2. 2330 月營收卡顯示 36 個月柱狀圖＋累計年增折線；2026/09 累計年增與公開資訊觀測站差 ≤ 0.1 個百分點；另驗 1 檔上櫃股。
3. 缺前一年資料的股票，累計年增顯示「--」且不報錯。
4. 標「★」月份的營收確實是最高值；文字為「近 N 年新高」。

### B8-2 資料來源
- 補抓沿用既有 `collect_monthly_revenue()`：歷史月份走 `https://mopsov.twse.com.tw/nas/t21/{sii|otc}/t21sc03_{民國年}_{月}.csv`（每市場每月 1 次），之前會先打一次 OpenAPI 確認是不是最新月份。
- 驗收用官方累計年增（2026-10-30 實測 OpenAPI `t187ap05_L`、`mopsfin_t187ap05_O`，欄位 `累計營業收入-前期比較增減(%)`，資料年月 11509）：

| 代號 | 市場 | 2026/01～09 累計營收（千元） | 去年同期（千元） | 官方累計年增 |
|---|---|---|---|---|
| 2330 台積電 | 上市 | 3,898,726,974 | 2,762,963,851 | **41.11%** |
| 5274 信驊 | 上櫃 | 11,804,447 | 6,641,749 | **77.73%** |
| 8299 群聯（備用） | 上櫃 | 194,931,541 | 49,865,433 | 290.92% |

### B8-3 資料庫
無變更（不存官方累計欄位，PM 已排除）。

### B8-4 收集流程（一次性補抓，不改程式）

```bash
for y in 2023 2024 2025; do
  for m in $(seq 1 12); do
    python3 -m twstock revenue --year $y --month $m || break 2
  done
done
```

- 每月：OpenAPI 上市 1 次（1 秒節流）＋mopsov 上市 1 次（3 秒）＋OpenAPI 上櫃 1 次（3 秒）＋mopsov 上櫃 1 次（3 秒）≈ 12～15 秒；36 個月約 **8 分鐘**。
- 被封鎖時 `revenue` 指令丟 `FetchError`（traceback、非 0 結束碼）→ 迴圈中止；重跑同一段迴圈，已有的公司會印「營收已齊全，略過」。
- 只寫入 `stocks` 表已有的股票；已下市公司不會補到（PM 已接受）。

### B8-5 匯出（`export.py`）

計算放在**匯出端**（以資料庫全部月份計算，前端只負責呈現）。新增純函式：

```python
REVENUE_MONTHS = 48   # 個股 JSON 匯出的月營收筆數

def _revenue_rows(rows):
    """
    rows: 某股票 [[年, 月, 營收(千元), 月增%, 年增%], ...]（舊到新、資料庫全部月份）
    回傳每列再加兩欄：
      累計年增%：當年 1 月～該月合計 ÷ 前一年同期合計 − 1；兩段任一月份缺資料或去年合計 ≤ 0 → None
      新高年數 N：該月營收 > 之前所有月份，且之前至少已有 24 個月資料時 = 資料涵蓋的整年數；否則 0
    """
    by_month = {(y, m): rev for y, m, rev, *_ in rows}
    first = rows[0][0] * 12 + rows[0][1] if rows else 0
    out, peak = [], None
    for y, m, rev, mom, yoy in rows:
        cur = [by_month.get((y, k)) for k in range(1, m + 1)]
        prev = [by_month.get((y - 1, k)) for k in range(1, m + 1)]
        cum = None
        if None not in cur and None not in prev and sum(prev) > 0:
            cum = round((sum(cur) / sum(prev) - 1) * 100, 2)
        months = y * 12 + m - first + 1                  # 資料涵蓋月數（含當月）
        hi = months // 12 if peak is not None and months > 24 and rev > peak else 0
        peak = rev if peak is None else max(peak, rev)
        out.append([y, m, rev, mom, yoy, cum, hi])
    return out
```

個股 JSON：`"revenue": _revenue_rows(revenue.get(code, []))[-REVENUE_MONTHS:]`

| 索引 | 名稱 | 型別 | 單位 | 範例（2330 2026/09） |
|---|---|---|---|---|
| 0 | 年 | int | | `2026` |
| 1 | 月 | int | | `9` |
| 2 | 營收 | int | 千元 | `511857399` |
| 3 | 月增 | number\|null | % | `-0.57` |
| 4 | 年增 | number\|null | % | `54.65` |
| 5 | **累計年增（新）** | number\|null | % | `41.11` |
| 6 | **新高年數 N（新）** | int | 年；0 = 非新高 | `0` 或 `3` |

「新高」定義（SA 定稿）：**該月營收高於資料庫中該股票所有更早月份**（創新高的那一刻），且之前至少已有 24 個月資料；N = 資料涵蓋月數 ÷ 12 取整（2023/01 起到 2026/09 為 45 個月 → N = 3，畫面寫「近 3 年新高」）。不以「全期最高」定義，原因見文末「PM 範圍調整建議」第 2 點。

大小評估（以 2026-10-30 的檔案實算）：個股 JSON 目前合計 **17.0 MB（17,044,186 bytes；`du` 顯示 21 MB 是磁碟區塊大小）**；營收由 9 筆增為 45 筆並多 2 欄，約 **+3.1 MB（+18%）**。

### B8-6 畫面（`stock.js` 月營收卡）

卡片標題列：`<h2>月營收</h2><span class="muted small">柱：營收（億），紅／綠 = 年增正／負；線：累計年增（%，右軸）</span>`。版面維持與「技術面訊號」並排的 `g2`。

`renderRevenue(rows)` 改寫為「圖＋表」：

```js
function renderRevenue(rows) {
  const box = $('#revBox');
  if (!rows.length) { box.innerHTML = '<div class="empty">沒有月營收資料</div>'; return; }
  const ym = r => `${r[0]}/${String(r[1]).padStart(2, '0')}`;
  const amt = v => fmt(v / 1e5, v >= 1e7 ? 0 : v >= 1e5 ? 1 : 2);        // 千元 → 億
  const pc = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v) + '%'}</td>`;
  box.innerHTML = `<div id="revC" style="height:220px"></div>
    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>年月</th><th>營收（億）</th><th>月增</th><th>年增</th><th>累計年增</th></tr></thead><tbody>` +
    rows.slice(-12).reverse().map(r => `<tr><td>${ym(r)}</td>
      <td class="num">${amt(r[2])}${r[6] ? `<span class="hi" title="近 ${r[6]} 年新高">★</span>` : ''}</td>${pc(r[3])}${pc(r[4])}${pc(r[5])}</tr>`).join('') +
    `</tbody></table></div>
    <div class="muted small" style="margin-top:6px">★ 近 N 年新高：營收高於之前所有月份（N 依資料涵蓋年數計算）。累計年增 = 當年 1 月至該月合計 ÷ 去年同期 − 1。</div>`;
  drawRevenue(rows.slice(-36), ym);
}
```

表格中有 ★ 的那格，`title` 為「近 3 年新高」（N 依該月計算）。

圖表用頁面已載入的 Plotly（雙軸最直接；Lightweight Charts 會被 `charts` 同步機制牽動）：

```js
function drawRevenue(rows, ym) {
  if (!window.Plotly) { $('#revC').innerHTML = '<div class="empty">圖表元件載入失敗，請檢查網路後重新整理</div>'; return; }
  const x = rows.map(ym), text2 = css('--text2'), grid = css('--border');
  Plotly.newPlot('revC', [
    { type: 'bar', x, y: rows.map(r => r[2] / 1e5), name: '營收',
      marker: { color: rows.map(r => css(r[4] == null ? '--flat' : r[4] >= 0 ? '--up' : '--dn')) },
      hovertemplate: '營收 %{y:,.2f} 億<extra></extra>' },
    { type: 'scatter', mode: 'lines+markers', x, y: rows.map(r => r[5]), yaxis: 'y2', name: '累計年增',
      line: { color: '#378ADD', width: 2 }, marker: { size: 4 }, connectgaps: false,
      hovertemplate: '累計年增 %{y:+.2f}%<extra></extra>' },
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { size: 10, color: text2 },
    margin: { l: 44, r: 48, t: 8, b: 28 }, showlegend: false, hovermode: 'x unified', dragmode: false,
    xaxis: { type: 'category', tickvals: x.filter(s => /\/(01|07)$/.test(s)), fixedrange: true },
    yaxis: { gridcolor: grid, fixedrange: true, rangemode: 'tozero' },
    yaxis2: { overlaying: 'y', side: 'right', ticksuffix: '%', showgrid: false, zeroline: true, zerolinecolor: grid, fixedrange: true },
  }, { responsive: true, displayModeBar: false });
}
```

離開頁面時釋放：`window.disposeStockCharts` 加上 `if (window.Plotly && $('#revC')) Plotly.purge('revC');`。

CSS：刪除不再使用的 `.rev`、`.rev .col`、`.rev .b` 與其 520px media query（本輪改寫造成的孤立樣式）；新增 `.hi{color:var(--amber);margin-left:4px}`。

- 桌機：半寬卡（約 540px），36 根柱每根約 13px；表格 5 欄。
- 手機 375px：卡片全寬 343px，柱寬約 7px 仍可辨識；x 軸只標 1 月與 7 月（6 個刻度）；表格約 270px 寬，不需橫向捲動。
- 無資料：「沒有月營收資料」（不畫圖）。資料少於 36 個月：畫現有的月份。

### B8-7 邊界情況

| 情況 | 處理 |
|---|---|
| 2025 年才上市（缺前一年） | 累計年增 `null` → 表格「--」、折線斷開（`connectgaps:false`） |
| 前一年同期中間缺一個月 | `null`（不可用不完整月份計算） |
| 去年同期合計為 0 或負 | `null` |
| 年增 `null`（官方未提供） | 柱為灰色 `--flat` |
| 資料不足 24 個月 | 不標 ★ |
| 營收月份尚未公布 | 不寫入，最新一列仍是上個月 |
| 補抓中途被封 | 重跑迴圈即可續補 |

### B8-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-B8-1 | SQL：`SELECT revenue_year*100+revenue_month ym, COUNT(*) FROM monthly_revenue GROUP BY revenue_year*100+revenue_month ORDER BY ym` | 第一列 `202301`；202301～202512 共 36 列，每列 1,700～2,000 之間（2026 年各月為 1,978～1,991） |
| T-B8-2 | `python3 tests/test_iter01.py` 的 `test_revenue_rows` | 以人造資料驗證：(a) 前一年完整 → 累計年增 = 手算值；(b) 前一年缺 1 個月 → `None`；(c) 第 25 個月營收創新高 → N = 2；第 24 個月創新高 → 0；(d) 不是新高 → 0 |
| T-B8-3 | `python3 -c "import json;r={x[0]*100+x[1]:x for x in json.load(open('site/data/stocks/2330.json'))['revenue']};assert abs(r[202609][5]-41.11)<=0.1;print(r[202609])"` | 通過（官方 41.11%） |
| T-B8-4 | 同上，代號 `5274`，比對 `77.73` | 通過（上櫃） |
| T-B8-5 | 開 `#/stock/2330` | Console：`document.getElementById('revC').data[0].x.length === 36` 且 `document.getElementById('revC').data[1].yaxis === 'y2'`；表格 12 列，第一列為「2026/09」，累計年增欄「+41.11%」左右 |
| T-B8-6 | 找 2025 年才上市的股票：`SELECT s.stock_code FROM monthly_revenue m JOIN stocks s ON s.stock_id=m.stock_id GROUP BY s.stock_code HAVING MIN(m.revenue_year*100+m.revenue_month) >= 202501`，任取一檔開個股頁 | 累計年增欄（缺前一年的月份）為「--」，Console 無錯誤 |
| T-B8-7 | 驗證 ★：`python3 -c "import json;R=json.load(open('site/data/stocks/2330.json'))['revenue'];[print(r[:2],r[6]) for i,r in enumerate(R) if r[6] and not all(r[2]>x[2] for x in R[:i])]"` | 不印任何列（每個 ★ 的營收都高於所有更早月份）；畫面 ★ 的 `title` 為「近 N 年新高」 |
| T-B8-8 | 個股 JSON 總大小：`python3 -c "import glob,os;print(sum(os.path.getsize(f) for f in glob.glob('site/data/stocks/*.json')))"` | 約 21.7 MB（基準 17,044,186；B8 約 +18%、P5 約 +9.5%，見 P5-5） |

---

## P5. 個股 K 線資訊列改用官方漲跌（僅日線）

### P5-1 對應驗收條件
1. 除權息日把游標移到該日，資訊列漲跌等於官方漲跌。
2. 一般交易日數值與修改前相同。
3. 個股 JSON 總大小增加不超過 15%。

### P5-2 資料來源（實測發現，影響設計）

`daily_prices.change` 已有，但查資料庫發現：

- **上市**的除權息等不比價日，MI_INDEX 的 `漲跌(+/-)` 是 `<p>X</p>`、`漲跌價差` 是 `0.00`（10/29 實測有 7 檔，如 2321 東訊）。資料庫存成 `change = 0`，**不是真正的漲跌**。全資料庫「收盤 − 前收 ≠ change」共 951 筆，其中 912 筆是上市且 `change = 0`。例：2317 鴻海 2026-07-02 收 239、前收 248、`change = 0.00`。
- **上櫃**的除權息日，`change` 是相對參考價的真實漲跌（例：3152 2026-06-30 收 324.5、`change = −35.5`，舊算法會顯示 +116.5）；另有 661 筆收盤有值但 `change` 為 NULL（官方欄位非數字）。

因此「直接顯示官方 `change`」在上市除權息日會顯示「0 (0.00%)」，同樣誤導。設計改為：**上市 `change = 0` 但收盤 ≠ 前一筆有成交收盤 → 視為不比價，匯出 null，畫面顯示「不比價」**（官方本身就以 X 表示不比價，沒有提供漲跌數字）。

### P5-3 資料庫／P5-4 收集流程
無變更（不改 `fetch_twse_daily` 對 X 的處理，避免新舊資料不一致；統一在匯出時判斷）。

### P5-5 匯出（`export.py`）

在每檔股票寫檔前計算：

```python
# 官方漲跌；上市「不比價」日（除權息等，漲跌欄為 X）官方價差是 0.00 而非真實漲跌 → None
chs, prev = [], None
for close, chg in zip(c, ch):
    x = _f(chg) if close is not None else None
    if x == 0 and info["market"] == "TWSE" and prev is not None and close != prev:
        x = None
    chs.append(x)
    if close is not None:
        prev = close
```

`prices` 物件新增 `"ch": chs`：

| 欄位 | 型別 | 單位 | 範例 | 說明 |
|---|---|---|---|---|
| `prices.ch` | (number\|null)[] | 元 | `[…, -10]` | 與 `prices.d` 等長；無成交日、不比價日、官方未提供時為 `null` |

大小：實算約 **+1.6 MB（+9.5%）**，符合 P5 驗收 3（≤ 15%）。`latest.json` 的 `ch`／`p` 不在本項範圍（見文末建議第 3 點）。

### P5-6 畫面（`stock.js`）

- `aggregate()`：有成交的列加 `ch: P.ch[i]`；無成交的一字線列加 `ch: null`。週／月聚合沿用第一列的 `ch`，但週月模式不使用它。
- `showLegend(i)`：

```js
const chg = mode === '日' ? raw[i].ch : i ? C[i] - C[i - 1] : 0;
const p = mode === '日' ? (chg != null && C[i] !== chg ? chg / (C[i] - chg) * 100 : null)
                        : i ? chg / C[i - 1] * 100 : 0;
const c = cls(chg);
// 漲跌那一段：
(NT[i] ? '<span class="flat">無成交</span>'
  : chg == null ? '<span class="flat" title="除權息、減資等不比價日，官方未提供漲跌">不比價</span>'
  : `<span class="${c}">${psgn(chg)} (${sgn(p)}%)</span>`)
```

  漲跌幅公式 `ch ÷ (收盤 − ch)` 與 `export.py` 的 `_pct` 一致。週／月模式維持舊算法。
- 「收」的顏色：`chg` 為 null 時 `cls(null)` → `flat`（灰）。

### P5-7 邊界情況
- 無成交日：「無成交」（不變）。
- 上市除權息日：「不比價」（灰），游標移上去有說明。
- 上櫃除權息日：顯示官方相對參考價的漲跌。
- 股票在資料庫的第一筆：沒有前收，直接用官方值；官方為 null 時顯示「不比價」。
- 上市真正平盤（收盤 = 前收、change 0）：不受影響，顯示「0 (0.00%)」。

### P5-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-P5-1 | SQL 找樣本：`WITH x AS (SELECT s.stock_code, s.market_type, d.trade_date, d.close_price, d.change, LAG(d.close_price) OVER (PARTITION BY d.stock_id ORDER BY d.trade_date) prev FROM daily_prices d JOIN stocks s ON s.stock_id=d.stock_id) SELECT TOP 20 * FROM x WHERE close_price IS NOT NULL AND prev IS NOT NULL AND change IS NOT NULL AND ABS(close_price-prev-change)>=0.01` | 有結果；含 2317 2026-07-02（上市）、3152 2026-06-30（上櫃） |
| T-P5-2 | `#/stock/3152`，日線，游標移到 2026/06/30 | 資訊列「-35.5 (-9.86%)」（官方漲跌；修改前為 +116.5） |
| T-P5-3 | `#/stock/2317`，日線，游標移到 2026/07/02 | 資訊列「不比價」（修改前為 -9 (-3.63%)） |
| T-P5-4 | `#/stock/2330` 日線最新一天（10/29） | 「-10 (-0.41%)」，與修改前相同；切到週線，資訊列仍為「本週收 − 上週收」 |
| T-P5-5 | 執行下方腳本（檢查上市股不再有「漲跌 0 但收盤 ≠ 前收」） | 印出 `0` |
| T-P5-6 | `len(ch) == len(d)`：`python3 -c "import json,glob;assert all(len((p:=json.load(open(f))['prices'])['ch'])==len(p['d']) for f in glob.glob('site/data/stocks/*.json'));print('ok')"` | `ok` |
| T-P5-7 | 只計 P5 增量：`python3 -c "import json,glob;n=sum(len(json.dumps(json.load(open(f))['prices']['ch'],separators=(',',':')))+6 for f in glob.glob('site/data/stocks/*.json'));print(n/17044186)"` | ≤ 0.15（預估約 0.095） |

T-P5-5 腳本：

```bash
python3 - <<'EOF'
import glob, json
bad = 0
for f in glob.glob("site/data/stocks/*.json"):
    s = json.load(open(f))
    if s["market"] != "TWSE":
        continue
    prev = None
    for c, ch in zip(s["prices"]["c"], s["prices"]["ch"]):
        if ch == 0 and prev is not None and c != prev:
            bad += 1
        if c is not None:
            prev = c
print(bad)
EOF
```

---

## B10. 處置／注意股警示標籤

### B10-1 對應驗收條件
1. 收集後資料表內容與 4 個端點當日回應中「一般股票」筆數一致。
2. 4577 達航科技（上櫃，處置 115/10/30～115/11/05）個股頁依資料日顯示「即將處置（10/30 起）」或「處置中（至 11/05）」，滑鼠移上看得到「連續 5 個營業日」。
3. 處置迄日早於資料日不顯示。
4. 上市注意股空白佔位資料不寫入、不報錯。
5. 兩種民國日期格式都能解析。

### B10-2 資料來源（2026-10-30 各實測 1 次，皆為 JSON 陣列、無參數）

| 來源 | 端點 | 實測筆數 | 代號欄 | 公告日欄 | 期間欄 | 長文欄（原因、措施） | 簡短原因欄 |
|---|---|---|---|---|---|---|---|
| 上市處置 | `https://openapi.twse.com.tw/v1/announcement/punish` | 3（含權證 071804） | `Code` | `Date`（`1151029`） | `DispositionPeriod`（`115/10/30～115/11/05`，全形～） | `Detail` | `ReasonsOfDisposition`（`連續三次`） |
| 上市注意 | `https://openapi.twse.com.tw/v1/announcement/notice` | 1（**佔位**：`Code:""`、`Number:"0"`、`Date:""`） | `Code` | `Date` | — | `TradingInfoForAttention` | — |
| 上櫃處置 | `https://www.tpex.org.tw/openapi/v1/tpex_disposal_information` | 11（公告日 10/21～10/29） | `SecuritiesCompanyCode` | `Date`（`1151029`） | `DispositionPeriod`（`1151030~1151105`） | `DisposalCondition` | `DispositionReasons`（`連續5個營業日`） |
| 上櫃注意 | `https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information` | 41（10/28 有 20、10/29 有 21） | `SecuritiesCompanyCode` | `Date` | — | `TradingInformation`（最長 180 字） | — |

觀察：
- 處置端點會列出近期（約 1～2 週）公告，**包含已到期**的（如 3287 處置到 10/29）；注意端點只給最近 1～2 個公告日。
- 上櫃注意含 5～6 碼代號（`54642`、`68732`、`735855`，可轉債等）；`is_valid_stock_code` 會放行 5 碼數字，但寫入時 `JOIN stocks` 會排除（`stocks` 表沒有 5 碼代號）。
- 長文中可用正規式抽出精簡內容（已對 14 筆實測樣本驗證全部命中）：
  - 原因：`處置原因：(.+?)。` → 例「連續5個營業日達本中心「公布注意交易資訊」標準」
  - 撮合頻率：`約每[^，。；;()（）]{1,5}分鐘撮合一次` → 上市「約每二分鐘撮合一次」、上櫃「約每2分鐘撮合一次」
  - 預收：長文含 `全部之買進價金` → 「預收款券」

### B10-3 資料庫（`db.py`，放在 `market_index` 之後）

```sql
-- 處置／注意股公告（保留歷史；注意股沒有起訖日）
IF OBJECT_ID('stock_alerts') IS NULL
CREATE TABLE stock_alerts (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    stock_id      INT            NOT NULL REFERENCES stocks(stock_id),
    alert_type    NVARCHAR(10)   NOT NULL CHECK (alert_type IN ('disposal','notice')),  -- 處置 / 注意
    announce_date DATE           NOT NULL,
    start_date    DATE           NULL,
    end_date      DATE           NULL,
    reason        NVARCHAR(1000) NULL,
    measure       NVARCHAR(200)  NULL,
    created_at    DATETIME       NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_stock_alerts UNIQUE (stock_id, alert_type, announce_date)
)
```

- MERGE 鍵：`(stock_id, alert_type, announce_date)`；MATCHED 更新 `start_date, end_date, reason, measure`（休市順延時官方會改迄日）。
- 用 `stock_id` 外鍵、`JOIN stocks`，比照 `merge_institutional`；權證、可轉債自然排除。

### B10-4 收集流程（新檔 `twstock/collectors/alerts.py`）

```python
"""
處置股與注意股（證交所、櫃買 OpenAPI）。端點只提供最近的公告，每天收一次、保留歷史。
"""
import re
from datetime import date

from .. import db
from ..fetch import FetchError, is_valid_stock_code, request

# (網址, 類型, 代號欄, 公告日欄, 處置期間欄, 長文欄, 簡短原因欄)
_SOURCES = (
    ("https://openapi.twse.com.tw/v1/announcement/punish", "disposal",
     "Code", "Date", "DispositionPeriod", "Detail", "ReasonsOfDisposition"),
    ("https://openapi.twse.com.tw/v1/announcement/notice", "notice",
     "Code", "Date", None, "TradingInfoForAttention", None),
    ("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", "disposal",
     "SecuritiesCompanyCode", "Date", "DispositionPeriod", "DisposalCondition", "DispositionReasons"),
    ("https://www.tpex.org.tw/openapi/v1/tpex_trading_warning_information", "notice",
     "SecuritiesCompanyCode", "Date", None, "TradingInformation", None),
)
_REASON = re.compile(r"處置原因：(.+?)。")
_MATCHING = re.compile(r"約每[^，。；;()（）]{1,5}分鐘撮合一次")


def roc_date(s):
    """民國日期 1151029 或 115/10/29 → date；空白或格式不符回傳 None。"""
    s = str(s or "").strip()
    if "/" in s:
        parts = s.split("/")
    elif s.isdigit() and len(s) == 7:
        parts = (s[:3], s[3:5], s[5:])
    else:
        return None
    try:
        y, m, d = (int(x) for x in parts)
        return date(y + 1911, m, d)
    except ValueError:
        return None


def roc_period(s):
    """處置期間「115/10/28～115/11/03」或「1151030~1151105」→ (起日, 迄日)；無法解析為 (None, None)。"""
    parts = re.split(r"[～~]", str(s or ""))
    return (roc_date(parts[0]), roc_date(parts[1])) if len(parts) == 2 else (None, None)


def parse_alert(row, kind, code_f, date_f, period_f, text_f, reason_f):
    """單筆公告 → 寫入用 dict；非一般股票、佔位資料、日期無法解析時回傳 None。"""
    code, announce = str(row.get(code_f) or "").strip(), roc_date(row.get(date_f))
    if not is_valid_stock_code(code) or announce is None:
        return None
    text = str(row.get(text_f) or "")
    item = {"stock_code": code, "alert_type": kind, "announce_date": announce.isoformat(),
            "start_date": None, "end_date": None, "reason": None, "measure": None}
    if kind == "notice":
        item["reason"] = text.strip()[:1000] or None
        return item
    start, end = roc_period(row.get(period_f))
    if start is None or end is None:
        return None
    m = _REASON.search(text)
    matching = _MATCHING.search(text)
    item.update(start_date=start.isoformat(), end_date=end.isoformat(),
                reason=(m.group(1) if m else str(row.get(reason_f) or "").strip())[:1000] or None,
                measure="、".join(x for x in (matching and matching.group(0),
                                               "預收款券" if "全部之買進價金" in text else None) if x) or None)
    return item


def fetch_alerts() -> list:
    rows = []
    for url, kind, *fields in _SOURCES:
        data = request("GET", url)
        if not isinstance(data, list):
            raise FetchError(f"處置／注意股回應格式不符：{url}")
        rows += [a for a in (parse_alert(r, kind, *fields) for r in data) if a]
    # 同一檔同一天同類型只留一筆，避免 MERGE 同一列被更新兩次
    return list({(a["stock_code"], a["alert_type"], a["announce_date"]): a for a in rows}.values())


def collect_alerts() -> int:
    """4 個端點全部抓完才寫入；只寫入 stocks 表已有的股票。"""
    rows = fetch_alerts()
    if rows:
        conn = db.connect()
        try:
            conn.cursor().execute("""
                MERGE stock_alerts AS t
                USING (
                    SELECT st.stock_id, j.*
                    FROM OPENJSON(?) WITH (
                        stock_code NVARCHAR(10), alert_type NVARCHAR(10), announce_date DATE,
                        start_date DATE, end_date DATE, reason NVARCHAR(1000), measure NVARCHAR(200)
                    ) AS j
                    JOIN stocks st ON st.stock_code = j.stock_code
                ) AS s
                ON t.stock_id = s.stock_id AND t.alert_type = s.alert_type AND t.announce_date = s.announce_date
                WHEN MATCHED THEN UPDATE SET
                    start_date = s.start_date, end_date = s.end_date, reason = s.reason, measure = s.measure
                WHEN NOT MATCHED THEN
                    INSERT (stock_id, alert_type, announce_date, start_date, end_date, reason, measure)
                    VALUES (s.stock_id, s.alert_type, s.announce_date, s.start_date, s.end_date, s.reason, s.measure);
            """, db.to_json(rows))
            conn.commit()
        finally:
            conn.close()
    n = sum(a["alert_type"] == "disposal" for a in rows)
    print(f"  🚨 處置 {n} 筆、注意 {len(rows) - n} 筆（未在股票清單的代號不寫入）")
    return len(rows)
```

`__main__.py` `cmd_collect`：在櫃買指數區塊之後加

```python
try:
    collect_alerts()
except FetchError as e:
    print(f"  ⚠️  處置／注意股抓取失敗：{e}")
```

- 只在 `traded` 為 True 時執行（放在既有 `if traded:` 區塊內）；`history` 不呼叫（端點沒有歷史）。
- 不新增 CLI 子指令；單獨執行可用 `python3 -c "from twstock.collectors.alerts import collect_alerts; collect_alerts()"`。
- 每日 `collect` 增加 4 次請求，約 8～10 秒。無需補抓。

### B10-5 匯出（`export.py`）

有效判斷（純函式，可測試）：

```python
def _alert_status(kind, announce, start, end, today):
    """處置：迄日 ≥ 資料日才有效，起日 > 資料日為「即將」；注意：公告日 = 資料日才有效。"""
    if kind == "disposal":
        if end is None or end < today:
            return None
        return "upcoming" if start and start > today else "active"
    return "notice" if announce == today else None
```

查詢（`conn.close()` 前），以 `latest_date` 為資料日：

```python
alerts = defaultdict(list)
for code, kind, ann, start, end, reason, measure in cur.execute("""
    SELECT s.stock_code, a.alert_type, a.announce_date, a.start_date, a.end_date, a.reason, a.measure
    FROM stock_alerts a JOIN stocks s ON s.stock_id = a.stock_id
    WHERE ISNULL(a.end_date, a.announce_date) >= ?
    ORDER BY a.announce_date""", latest_date):
    if _alert_status(kind, ann, start, end, latest_date):
        alerts[code].append({"t": kind, "a": str(ann), "s": start and str(start), "e": end and str(end),
                             "r": reason, "m": measure})
```

**latest.json**（`stocks.{代號}`，只有有效警示的股票才有這兩個鍵）：

| 欄位 | 型別 | 範例 | 說明 |
|---|---|---|---|
| `dsp` | [string, string] | `["2026-10-30","2026-11-05"]` | 有效處置的 [起日, 迄日]；多筆時取**起日最早**者（處置中優先於即將處置） |
| `ntc` | 1 | `1` | 資料日當天有注意公告 |

大小：以 10/29 實測（處置約 12 檔、注意約 20 檔）約 **+0.6 KB**。原因、措施長文**不放進 latest.json**。

**個股 JSON**：`**({"alerts": alerts[code]} if code in alerts else {})`

| 欄位 | 型別 | 範例 |
|---|---|---|
| `alerts[].t` | `"disposal"`\|`"notice"` | `"disposal"` |
| `alerts[].a` | 公告日 | `"2026-10-29"` |
| `alerts[].s` / `e` | 處置起／迄日（注意股為 null） | `"2026-10-30"` / `"2026-11-05"` |
| `alerts[].r` | 原因（精簡） | `"連續5個營業日達本中心「公布注意交易資訊」標準"` |
| `alerts[].m` | 措施（精簡） | `"約每2分鐘撮合一次、預收款券"` |

### B10-6 畫面

**個股頁標頭（`stock.js`）**：`tags` 中、市場別 pill 之前插入：

```js
${(data.alerts || []).map(a => a.t === 'disposal'
  ? `<span class="pill al-d" title="${esc(`處置期間 ${md(a.s)}～${md(a.e)}（${md(a.a)} 公告）\n原因：${a.r || '--'}\n措施：${a.m || '--'}`)}">${a.s > App.latest.date ? `即將處置（${md(a.s)} 起）` : `處置中（至 ${md(a.e)}）`}</span>`
  : `<span class="pill al-n" title="${esc(`${md(a.a)} 公布注意交易資訊\n${a.r || ''}`)}">注意</span>`).join('')}
```

文案：紅色「處置中（至 11/05）」／紅色「即將處置（10/30 起）」／橘色「注意」。Tooltip 範例：

```
處置期間 10/30～11/05（10/29 公告）
原因：連續5個營業日達本中心「公布注意交易資訊」標準
措施：約每2分鐘撮合一次、預收款券
```

**表格小標記（`app.js`）**：

```js
// 名稱旁的處置／注意小標記（latest.json 只放有效的警示）
const alertBadge = s =>
  (s.dsp ? `<i class="al al-d" title="${s.dsp[0] > App.latest.date ? `即將處置（${md(s.dsp[0])} 起）` : `處置中（至 ${md(s.dsp[1])}）`}">處</i>` : '') +
  (s.ntc ? '<i class="al al-n" title="注意股（當日公布注意交易資訊）">注</i>' : '');
```

插入位置：`<td class="nm"><b>${esc(s.n)}</b>${alertBadge(s)}<span>…</span></td>`，套用在今日頁法人買超／賣超表（`renderToday` 的 `rows`）與 `stockTable()`（排行、自選）。

CSS：

```css
.al{display:inline-block;font-style:normal;font-size:10px;line-height:15px;padding:0 3px;border-radius:3px;margin-left:4px;color:#fff;vertical-align:1px}
.al-d{background:var(--up)}.al-n{background:var(--amber)}
.pill.al-d{background:var(--up-bg);border-color:var(--up);color:var(--up)}
.pill.al-n{background:color-mix(in srgb,var(--amber) 15%,transparent);border-color:var(--amber);color:var(--amber)}
```

- 桌機：tooltip 以 `title` 呈現。手機：tags 自動換行；`title` 在觸控裝置看不到，本輪接受（標籤文字本身已含狀態與日期）。
- 無警示：不輸出任何元素。

### B10-7 邊界情況

| 情況 | 處理 |
|---|---|
| 上市注意佔位資料（`Code:""`、`Date:""`） | `is_valid_stock_code("")` 為 False → `parse_alert` 回傳 None，不寫入、不報錯 |
| 權證（071804）、可轉債（54642） | 前者被 `is_valid_stock_code` 排除；後者被 `JOIN stocks` 排除 |
| 處置迄日 < 資料日 | `_alert_status` 回傳 None，不匯出、不顯示 |
| 迄日 = 資料日 | 仍顯示「處置中（至 MM/DD）」 |
| 起日 = 資料日 | 「處置中」 |
| 起日 > 資料日（公告後次日起） | 「即將處置（MM/DD 起）」 |
| 注意公告日 ≠ 資料日（例如 18:30 前端點還是前一天） | 不顯示「注意」；歷史仍保留在資料表 |
| 收集晚於行情日（例：10/30 上午才收 10/29 的資料） | 判斷一律以 `latest_date` 為準，10/30 公告的注意股不會套到 10/29 |
| 同一檔同時處置與注意 | 兩個標籤都顯示 |
| 4 個端點任一失敗 | 整批不寫（`fetch_alerts` 丟 `FetchError`），`cmd_collect` 印警告；網站沿用上次的警示 |
| 日期格式 `115/1/5`（未補零） | `roc_date` 以 `/` 分割，可解析 |
| 假日 | `collect` 不執行到這一步 |

### B10-8 測試案例

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-B10-1 | `python3 tests/test_iter01.py` 的 `test_roc_date` | `roc_date('1151029') == date(2026,10,29)`；`roc_date('115/10/28') == date(2026,10,28)`；`roc_date('') is None`；`roc_date('1151340') is None`；`roc_period('115/10/28～115/11/03') == (date(2026,10,28), date(2026,11,3))`；`roc_period('1151030~1151105') == (date(2026,10,30), date(2026,11,5))`；`roc_period('') == (None, None)` |
| T-B10-2 | `test_parse_alert`（樣本取自附錄 A） | 上市注意佔位列 → `None`；071804 權證 → `None`；4577 → `start_date='2026-10-30'`、`end_date='2026-11-05'`、`reason` 含「連續5個營業日」、`measure=='約每2分鐘撮合一次、預收款券'`；2466 → `measure` 以「約每二分鐘撮合一次」開頭 |
| T-B10-3 | `test_alert_status`（資料日 2026-10-29） | 處置 10/30～11/05 → `'upcoming'`；處置 10/22～10/29 → `'active'`；處置 10/23～10/28 → `None`；注意公告 10/29 → `'notice'`；注意公告 10/28 → `None` |
| T-B10-4 | 執行收集後（`collect` 或單獨 `collect_alerts()`），用下列腳本比對筆數 | 兩邊集合相同 |

T-B10-4 腳本（會打 4 次 OpenAPI）：

```python
from twstock import db
from twstock.collectors.alerts import fetch_alerts
api = {(a["stock_code"], a["alert_type"], a["announce_date"]) for a in fetch_alerts()}
cur = db.connect().cursor()
codes = {r[0] for r in cur.execute("SELECT stock_code FROM stocks")}
api = {k for k in api if k[0] in codes}                       # 一般股票 = 通過 is_valid_stock_code 且在 stocks 表
dates = sorted({k[2] for k in api})
db_rows = {(r[0], r[1], str(r[2])) for r in cur.execute(f"""
    SELECT s.stock_code, a.alert_type, a.announce_date FROM stock_alerts a JOIN stocks s ON s.stock_id = a.stock_id
    WHERE a.announce_date IN ({','.join('?' * len(dates))})""", *dates)}
assert api == db_rows, (api - db_rows, db_rows - api)
print("ok", len(api))
```

| 編號 | 步驟 | 預期結果 |
|---|---|---|
| T-B10-5 | 資料日 10/29 時開 `#/stock/4577` | 標頭有紅色「即將處置（10/30 起）」；Console：`$('.pill.al-d').title.includes('連續5個營業日')` 為 `true`。資料日更新到 10/30～11/05 期間時顯示「處置中（至 11/05）」 |
| T-B10-6 | 資料日 10/29 時開 `#/stock/3287`（處置到 10/29） | 「處置中（至 10/29）」；資料日為 10/30 以後重新匯出 → 無標籤 |
| T-B10-7 | `python3 -c "import json;S=json.load(open('site/data/latest.json'))['stocks'];D=json.load(open('site/data/latest.json'))['date'];assert all(s['dsp'][1]>=D for s in S.values() if 'dsp' in s);print(sorted(c for c,s in S.items() if 'dsp' in s))"` | 不報錯；清單含 4577、2466、4526，不含 071804 |
| T-B10-8 | 開 `#/rank`（門檻選不限，排行選漲幅或成交額）找到有 `dsp` 的股票 | 名稱旁有紅色「處」，`title` 為「即將處置（10/30 起）」或「處置中（至 MM/DD）」；自選加入 4577 後自選頁同樣顯示 |
| T-B10-9 | 連續執行 `setup-db` 兩次 | 不報錯；`SELECT OBJECT_ID('stock_alerts')` 不為 NULL |

---

## 附錄 A：資料源驗證紀錄（2026-10-30，經 `fetch.request`、`RETRY_BACKOFF=()` 每個端點 1 次）

| 端點 | 結果 | 用途 |
|---|---|---|
| `www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?type=ALLBUT0999&date=20261029` | 成功；`價格指數(臺灣證券交易所)` 表第 2 列為加權指數 46,368.33、`-`、667.25、-1.42；個股表有 7 檔 `漲跌(+/-)` 為 `<p>X</p>`、價差 `0.00` | A1、P5 |
| `www.tpex.org.tw/openapi/v1/tpex_index` | 成功；18 筆，20261001～20261029；10/29 收 387.37、Change -7.24 | A1 |
| `www.twse.com.tw/rwd/zh/indicesReport/MI_5MINS_HIST?date=20261001` | **失敗**：回應非 JSON；未重試 | 不採用 |
| `openapi.twse.com.tw/v1/announcement/punish` | 成功；3 筆（071804、2466、4526） | B10 |
| `openapi.twse.com.tw/v1/announcement/notice` | 成功；1 筆全空佔位 | B10 |
| `www.tpex.org.tw/openapi/v1/tpex_disposal_information` | 成功；11 筆（含 4577 1151030~1151105） | B10 |
| `www.tpex.org.tw/openapi/v1/tpex_trading_warning_information` | 成功；41 筆（兩個公告日） | B10 |
| `openapi.twse.com.tw/v1/opendata/t187ap05_L` | 成功；1,088 筆，資料年月 11509 | B8 驗收值 |
| `www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O` | 成功；893 筆，資料年月 11509 | B8 驗收值 |

## 附錄 B：`tests/test_iter01.py` 規格

- 新增 `tests/test_iter01.py`，只用標準函式庫與專案模組，可用 `python3 tests/test_iter01.py` 直接執行（檔頭 `sys.path.insert(0, 專案根目錄)`；末尾依序呼叫所有 `test_*` 並印「全部通過」），也相容 pytest。
- 不連網、不連資料庫（`export.py` 頂層只 import `pyodbc`，不會連線）。
- 內容：`test_parse_taiex`（T-A1-1）、`test_revenue_rows`（T-B8-2）、`test_roc_date`（T-B10-1）、`test_parse_alert`（T-B10-2，樣本以 dict 寫在測試檔內，只保留必要欄位與 `Detail`／`DisposalCondition` 片段）、`test_alert_status`（T-B10-3）。
- P3 的條件切換是前端邏輯，以 T-P3-1～T-P3-4 的瀏覽器 Console 步驟驗證。

## 附錄 C：給 Programmer 的提醒

1. 新表要執行 `python3 -m twstock setup-db` 才會建立；`export` 會查 `market_index`、`stock_alerts`，**沒建表會失敗**，請在 `04-dev.md` 提醒使用者先執行。
2. 補抓順序：B8 營收（約 8 分鐘）→ 加權指數（約 11 分鐘），不要同時跑。
3. 測試用埠 8001，結束時關閉；不要動 `.env`、不要 commit。

---

## PM 範圍調整建議

1. **P5 的「官方漲跌」在上市除權息日不是真實漲跌**：證交所在不比價日給 `X` 與 `0.00`。本設計改為顯示「不比價」，P5 驗收 1 應改為「上櫃除權息日顯示官方漲跌（例 3152 6/30 −35.5）；上市除權息日顯示『不比價』而非假漲跌（例 2317 7/2）」。
2. **B8「創新高」定義**：PM 文字「該股票所有月份的最高值」若照字面（全期最高）只會有 1 個月打星，且早期月份的「近 N 年」語意不通。本設計採「高於之前所有月份、且至少有 2 年資料」，驗收 4 應改為「★ 月份的營收高於該股票所有更早月份」（T-B8-7）。
3. **待辦新增**：上市除權息日 `latest.json` 的 `ch`／`p` 同樣是 0（今日頁、排行、個股標頭顯示 0.00%，漲跌家數算成平盤），本輪不在範圍，建議併入 B1。
4. **個股 JSON 大小**：P5 +9.5%＋B8 +18%，合計約 +28%（17.0 → 約 21.7 MB）。若要壓低，可把 `REVENUE_MONTHS` 由 48 改為 36（畫面只用 36 個月，累計年增已在匯出端算好），約省 0.7 MB。
5. 櫃買指數月底最後一個交易日若當天 18:30 端點未更新，次月就抓不到（`tpex_index` 只給本月），請在 A1-延伸找歷史端點時一併解決。
