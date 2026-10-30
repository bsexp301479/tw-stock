# 第 01 輪｜Programmer：實作紀錄

- 撰寫日期：2026-10-30
- 依據：`03-design.md`（實作依據）、`02-pm.md`（範圍與驗收條件）
- 本輪項目：P1、P3、P7、A1、P2、P4、B8、P5、B10，全部完成。依設計「建議實作順序」執行：先背景補抓營收 → 前端誤導修正 → A1 → P2／P5 → B8 → B10 → 測試、匯出、自測。
- 未 commit、未 push、未動 `.env`。

> **使用者需先執行一次 `python3 -m twstock setup-db`**（本輪新增 `market_index`、`stock_alerts` 兩張表；`export` 會查這兩張表，沒建表會失敗）。本機資料庫我已執行過兩次，皆成功。

---

## 一、各項目修改內容

### P1 法人資料標示日期
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `site/app.js` | 新增 `flowNote()`（放在 `md` 之後） | `date ≠ flow_date` 時回傳「法人資料尚未更新：收盤、漲跌為 MM/DD，法人欄位為 MM/DD」提示 |
| `site/app.js` | `renderToday()` | 法人買超／賣超表頭「當日，億」→「`${md(flow_date)}`，億」；兩表的 `<section>` 前插入 `flowNote()` |
| `site/app.js` | `stockTable()` | 表格前加 `flowNote()` 與 `.tbl-cap` 說明（1 日：「法人欄位為 10/28 當日買賣超（億）」；5 日：「法人欄位為截至 10/28 的近 5 日累計（億）」），排行與自選共用 |
| `site/app.js` | `showGroup()` | `#gMeta` 末尾加「　法人 10/28」 |
| `site/stock.js` | `renderStock()` 指標卡 | `metrics` 元素擴充為 `[標籤, 值, class, 副標]`；法人1日副標「10/28」，法人5日／外資5日／投信5日副標「至 10/28」 |
| `site/app.css` | | 新增 `.flow-note`、`.tbl-cap` |

### P3 預測模型降級為「籌碼因子觀察」
| 檔案 | 函式 | 修改 |
|---|---|---|
| `site/app.js` | `oiHTML()` | `beat = acc > baseline` 提到 `if (FC)` 外；原內容拆成 `head`（大字、上漲機率）、`factors`、`bt`（回測、最近 10 次、模型說明）。`!beat` 時只顯示說明行＋因子，`head`＋`bt` 收進預設摺疊的 `<details class="fc-more">`（summary「模型回測（實驗性，未勝過基準）」）；卡片標題依狀態為「籌碼因子觀察」／「大盤漲跌預測」；因子說明文字依狀態切換 |
| `site/app.css` | | 新增 `.fc-more` 三條 |

### P7 排行流動性門檻＋說明文字
| 檔案 | 函式 | 修改 |
|---|---|---|
| `site/app.js` | `renderRank()` | 新增 `minTv = localStore('rtv', '0.5')`、`#tvSel` 選單（不限／0.5／1／5 億，放在 `rankSel` 前）、篩選條件 `(s.tv ?? 0) >= Number(minTv)`、change 事件存 `tw.rtv`；說明文字換成設計定稿（含 P4「不含 ETF」） |

### P4 成交額與法人金額註明口徑
| 檔案 | 函式 | 修改 |
|---|---|---|
| `site/app.js` | `renderToday()` 的 `mk()` | 上市／上櫃成交額卡加「一般股票，不含 ETF」 |
| `site/app.js` | `renderToday()` 三大法人卡 | 加「估算：買賣超張數 × 收盤價，不含 ETF」 |

### A1 加權／櫃買指數卡＋近 60 日走勢線
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/db.py` | `DDL`、`setup_database()` | 新表 `market_index`（DDL 照設計）；完成訊息加上新表名稱 |
| `twstock/collectors/daily.py` | 常數 | `TPEX_OPENAPI`；`PRICES, INSTI, INDEX`（`ALL_DATASETS` 不變） |
| 同上 | 新增 `parse_taiex(data, d)` | 從 MI_INDEX「價格指數(臺灣證券交易所)」表以名稱找「發行量加權股價指數」，正負號取自「漲跌(+/-)」欄 |
| 同上 | `fetch_twse_daily(d)` | 改回傳 `(個股列表, 加權指數 dict 或 None)`，休市 `([], None)`；個股解析不變 |
| 同上 | 新增 `fetch_tpex_index()`、`merge_market_index()`、`collect_tpex_index()` | 照設計 |
| 同上 | `collect_for_date()` | 拆 tuple；PRICES 時一併寫入加權指數（找不到指數表時印 ⚠️，個股照寫）；新增 `elif INDEX in datasets` 只補指數；同一交易內 `merge_market_index`，維持一次 commit |
| `twstock/collectors/history.py` | `_TABLE`、新增 `_FILTER`、`SECONDS_PER_DAY`、`dates_in_db()` | `INDEX → market_index`，判斷已有日期時只看 `index_code = 'TAIEX'`；每日 4 秒 |
| `twstock/__main__.py` | `cmd_collect()`、`history --only` | 期貨區塊後呼叫 `collect_tpex_index()`（`except FetchError` 印 ⚠️ 繼續）；`--only` 加 `index` |
| `twstock/export.py` | 常數 `INDEX_DAYS = 60`、`export_all()` | 查 `market_index`，`latest.index.{TAIEX,TPEX}` = `date/c/ch/p/from/s`（無資料的指數不輸出該鍵） |
| `site/app.js` | 新增 `spark()`、`indexCard()`；`renderToday()` | 今日頁最上方一列兩張指數卡；原成交額／法人三張卡移到第二列 |
| `site/app.css` | | 新增 `.idx .spark` |

### P2 「52 週高／低」改為實際區間
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | `export_all()` | `db_first` = 全市場最早日線；`latest.hl_from`（未滿 52 週 = `db_first`，滿了為 `null`）；個股第一筆日線晚於 `max(db_first, w52_start)` 時加 `stocks.{代號}.hf`。`h52`／`l52` 計算不變 |
| `site/stock.js` | `renderStock()` 指標卡 | `hlFrom = s?.hf ?? App.latest.hl_from`；有值時標籤「區間高／區間低」＋副標「自 YYYY/MM/DD」，否則「52週高／52週低」 |

### B8 月營收 3 年走勢、累計年增、創新高
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | 新增 `_revenue_rows(rows)`、常數 `REVENUE_MONTHS = 36` | 以資料庫**全部月份**計算累計年增（索引 5）與新高年數 N（索引 6），再截取最近 36 筆匯出 |
| `site/stock.js` | `renderRevenue()` 改寫、新增 `drawRevenue()` | Plotly 雙軸圖（最近 36 個月柱＋累計年增折線，右軸 %）＋最近 12 個月表格（年月、營收、月增、年增、累計年增，新高月份 ★，`title`「近 N 年新高」）；卡片標題說明文字改寫 |
| `site/stock.js` | `window.disposeStockCharts` | 離開個股頁時 `Plotly.purge('revC')`（見「與設計的差異」第 2 點） |
| `site/app.css` | | 刪除孤立的 `.rev`、`.rev .col`、`.rev .b` 與其 520px media query；新增 `.hi` |

### P5 K 線資訊列改用官方漲跌（僅日線）
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | `export_all()` 個股迴圈 | 計算 `prices.ch`：官方漲跌；上市且 `change = 0` 但收盤 ≠ 前一筆有成交收盤 → `null`（不比價）；無成交日 `null` |
| `site/stock.js` | `aggregate()` | 每列加 `ch`（一字線列為 `null`） |
| `site/stock.js` | `buildCharts()` 內 `showLegend()` | 日線：漲跌 = `raw[i].ch`、漲跌幅 = `ch ÷ (收盤 − ch)`，`null` 顯示灰色「不比價」（滑鼠提示說明）；週／月線維持舊算法 |

### B10 處置／注意股警示
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/db.py` | `DDL` | 新表 `stock_alerts`（DDL 照設計） |
| `twstock/collectors/alerts.py`（新檔） | `roc_date`、`roc_period`、`parse_alert`、`fetch_alerts`、`collect_alerts` | 照設計（4 個端點全部抓完才寫入、`JOIN stocks` 排除非 `stocks` 表代號） |
| `twstock/__main__.py` | `cmd_collect()` | 櫃買指數之後呼叫 `collect_alerts()`（在 `if traded:` 內，`except FetchError` 印 ⚠️ 繼續） |
| `twstock/export.py` | 新增 `_alert_status()`；`export_all()` | 以 `latest_date` 判斷有效警示；`latest.json` 個股加 `dsp`（有效處置 [起, 迄]，多筆取起日最早）、`ntc: 1`；個股 JSON 加 `alerts` 明細（`t/a/s/e/r/m`） |
| `site/app.js` | 新增 `alertBadge()`；`renderToday()` 的 `rows`、`stockTable()` | 名稱旁紅「處」／橘「注」小標記，`title` 為狀態 |
| `site/stock.js` | `renderStock()` 標頭 tags | 市場別 pill 前插入「處置中（至 MM/DD）」／「即將處置（MM/DD 起）」／「注意」，`title` 為起訖、原因、措施 |
| `site/app.css` | | 新增 `.al`、`.al-d`、`.al-n`、`.pill.al-d`、`.pill.al-n` |

### 測試
- 新增 `tests/test_iter01.py`（不連網、不連資料庫，可直接執行或 pytest）：`test_parse_taiex`、`test_revenue_rows`、`test_roc_date`、`test_parse_alert`（樣本取自 2026-10-30 實測回應片段）、`test_alert_status`。執行結果：全部通過。

---

## 二、執行過的指令與補抓結果

| 指令 | 結果 |
|---|---|
| `python3 -m twstock revenue --year Y --month M`（2023/01～2025/12 迴圈，背景執行，log：`logs/backfill_revenue_2023_2025.log`） | 36 個月全部成功，**耗時 150 秒**（遠少於預估 8 分鐘），**無限流、無失敗**。每月上市 1,039～1,088 家、上櫃 845～895 家。補完後 `monthly_revenue` 共 87,667 筆，最早 202301；2023/01～2025/12 每月 1,881～1,983 家（2026 年各月 1,978～1,991） |
| `python3 -m twstock setup-db` ×2 | 兩次皆成功，建立 `market_index`、`stock_alerts` |
| `python3 -m twstock history --start 2026-02-23 --end 2026-10-29 --only index`（營收補抓結束後才啟動，背景執行，log：`logs/backfill_index_taiex.log`） | 168 個交易日全部成功（2026-02-23～10-29），**耗時約 9 分 50 秒**（12:12:11～12:22:01），**無退避重試、無失敗、無「無資料」日**。T-A1-2：10/29 收 46,368.33、漲跌 −667.25；T-A1-3：TAIEX 168 筆 = `daily_prices` 交易日數 168 |
| `collect_tpex_index()`、`collect_alerts()`（單獨執行一次，log：`logs/collect_tpex_index_alerts.log`） | 櫃買指數 18 天（2026-10-01～10-29）；處置 13 筆、注意 40 筆，6.3 秒 |
| 為了寫測試樣本，另以 `fetch.request` 各打 1 次 `punish`、`notice`、`tpex_disposal_information` | 成功；上市注意仍為全空佔位資料 |
| `python3 tests/test_iter01.py` | 全部通過 |
| `python3 -m twstock export` | 成功（約 12 秒）：資料日 2026-10-29，個股 1,996 檔，latest.json 651 KB；補抓完成後再匯出一次作為最終版本 |
| `python3 -m py_compile`（`twstock/**/*.py`、`tests/test_iter01.py`）、`node --check site/app.js site/stock.js` | 皆通過 |
| `python3 -m twstock serve --port 8001 --no-browser`（背景） | 自測完成後已關閉 |

### 匯出檔大小

| 檔案 | 修改前 | 修改後 | 變化 |
|---|---|---|---|
| `site/data/latest.json` | 664,139 B | 666,423 B | +2,284 B（+0.3%） |
| `site/data/stocks/*.json` 合計（1,996 檔） | 17,044,186 B | 20,707,487 B | +3,663,301 B（+21.5%；`du` 顯示 23 MB 為磁碟區塊大小） |

- 其中 P5 的 `ch` 陣列約 +9.5%（`T-P5-7` 腳本實算 0.0947，≤ 15%）；其餘主要是 B8 營收由 9 筆變 36 筆並多 2 欄。
- 營收改匯出 36 筆（設計為 48 筆），比 48 筆版本省約 0.7 MB（設計估算）。

---

## 三、自我驗證（8001，資料日 2026-10-29）

以 python 讀 JSON、瀏覽器 Console 操作驗證，結果如下：

| 測試 | 結果 |
|---|---|
| T-P1-1～5 | 表頭「10/28，億」×2、提示行存在；排行 `.tbl-cap`「法人欄位為 10/28 當日買賣超（億）」；個股 4 張卡含「10/28」；泡泡圖 `#gMeta`「…法人 10/28」；把 `flow_date` 改成 `date` 後提示消失、表頭與說明皆為 10/29 |
| T-P3-1～4 | 初始 `[false, false, true]`；展開後看得到 52.9%、54.4%、上漲機率；`acc=0.6` 恢復「大盤漲跌預測」與大字；`acc=baseline` 仍降級 |
| T-P7-1～5 | 預設 0.5 億、50 筆皆 ≥ 0.5 億、不含 5245／8291；「不限」與修改前集合一致；選 1 億重新整理後保留（`tw.rtv='1'`）；說明文字符合 |
| T-P4-1 | 3 張卡含「不含 ETF」 |
| T-A1-4 | 印 `ok`：TAIEX 46,368.33／−667.25／−1.42%，60 點、最後一點 = 收盤、`from` 2026-07-31；TPEX 387.37／−7.24／−1.83%，`from` 2026-10-01。今日頁兩張卡數值相同，走勢線分別 60、18 點，櫃買底行「資料自 10/01 起（18 個交易日）」 |
| T-A1-8 | 刪 `index.TPEX` → 櫃買卡「-- 暫無資料」；刪整個 `index` → 兩張卡都是「--」，頁面正常 |
| T-A1-9 | `setup-db` 連跑兩次無誤 |
| T-A1-10 | 375×812 下兩張指數卡並排，數字與漲跌不溢出 |
| T-P2-1～5 | 2330「區間高 2,590／區間低 1,760　自 2026/02/23」；7811「自 2026/03/25」；`hl_from=null` 後變回「52週高／52週低」無副標；`hf` 共 46 檔、2330 無 `hf` |
| T-B8-3／4 | 2330 2026/09 累計年增 **41.11**、5274 **77.73**、8299 **290.92**，與官方完全一致 |
| T-B8-5 | 2330 圖 36 個月、第二條線 `yaxis='y2'`；表格 12 列，第一列「2026/09 5,119 -0.57% +54.65% +41.11%」 |
| T-B8-6 | 7818（營收自 2025/01 起）2025 年各月累計年增「--」，圖 21 個月，Console 無錯誤 |
| T-B8-7 | 2330 ★：2025/04、2025/10（近 2 年）、2026/01、03、05～08（近 3 年），每個 ★ 都高於所有更早月份 |
| T-P5-2／3／4 | 3152 日線 2026/06/30「-35.5 (-9.86%)」；2317 2026/07/02「不比價」；2330 10/29「-10 (-0.41%)」；週線仍為舊算法 |
| T-P5-5／6／7 | 0 筆；`len(ch)==len(d)` 全部成立；增量比 0.0947 |
| T-B10-1～3 | 單元測試通過 |
| T-B10-5／6 | 4577「即將處置（10/30 起）」＋「注意」，tooltip 含「連續5個營業日」與「約每2分鐘撮合一次、預收款券」；3287「處置中（至 10/29）」 |
| T-B10-7 | `dsp` 13 檔：2466、3287、3354、3441、4526、4542、4577、5205、5475、6751、6925、8358、8437；不含 071804；全部迄日 ≥ 資料日 |
| T-B10-8 | 排行（成交額）中 4526 名稱旁「處」（title「即將處置（10/30 起）」）、3374「注」 |
| 個股頁切換日／週／月 | 月營收圖保留（見差異第 2 點） |

---

## 四、與設計文件不同的地方及原因

1. **個股 JSON 月營收改為最近 36 筆（設計 48 筆）**：依本輪決定壓低檔案大小（設計「PM 範圍調整建議」第 4 點）。累計年增與新高仍以資料庫全部月份計算後才截取，所以 36 筆的第 1 筆（2023/10）也有正確的累計年增；圖表本來就只畫 36 個月。
2. **`buildCharts()` 改呼叫新的 `disposeKCharts()`，不再呼叫 `window.disposeStockCharts()`**：設計要求在 `disposeStockCharts` 加 `Plotly.purge('revC')`，但原本 `buildCharts()` 一開始就會呼叫 `disposeStockCharts()`，而 `renderStock()` 是先畫月營收、再 `buildCharts()`，切換日／週／月也會再呼叫 `buildCharts()` — 照原樣加入會把剛畫好的月營收圖清掉。因此把「只移除 K 線四張圖」抽成 `disposeKCharts()` 給 `buildCharts()` 用；`window.disposeStockCharts`（路由切換時呼叫）= `disposeKCharts()` + purge 月營收圖。
3. **P5、B8 依設計已採納的調整實作**：上市除權息日顯示「不比價」；新高定義為「高於之前所有月份且之前至少 24 個月資料」，N = 涵蓋月數 ÷ 12。
4. 其餘欄位名稱、資料表、判斷式、畫面文案皆照設計。另外 `collect_for_date()` 的 `MI_INDEX 找不到加權指數表` 警告只在「有個股列但沒指數」時印出（設計原意），休市不印。

---

## 五、已知限制

1. **櫃買指數只有 2026-10 月**（`tpex_index` 只給本月），走勢線顯示「資料自 10/01 起（18 個交易日）」；月底最後一個交易日若當天 18:30 端點未更新，次月就補不到（設計已列，待 A1-延伸）。
2. **加權指數只有收盤與漲跌**（無開高低），日 K 待 A1-延伸。
3. **上市除權息日在 `latest.json` 的 `ch`／`p` 仍是 0**（今日頁、排行、個股標頭顯示 0.00%，漲跌家數算平盤）— 本輪 P5 只處理 K 線資訊列，已列入 PM 待辦 P11。
4. **營收補抓只涵蓋 `stocks` 表已有的股票**，已下市公司沒有歷史營收（PM 已接受）。2023/01 為 1,881 家，比 2026 年少約 100 家，主要是當時尚未上市／上櫃。
5. **處置／注意股沒有歷史補抓**（端點只給近期公告），網站從本輪開始累積；注意股以「公告日 = 資料日」判斷，若 18:30 收集時端點仍是前一天的資料，當天不會顯示「注意」。
6. 上市處置的「預收款券」依長文是否含「全部之買進價金」判斷；部分處置（如 4526）只對單筆達 10 交易單位以上的委託預收，標籤仍顯示「預收款券」，詳細條件需看原公告。
7. 手機觸控裝置看不到 `title` tooltip（設計已接受）。

---

## 六、給 QA 的注意事項

1. 先確認已執行 `python3 -m twstock setup-db`，資料庫已含本輪補抓資料（營收 2023/01 起、加權指數 2026-02-23 起）。
2. **處置／注意資料是 2026-10-30 中午收集的**，以資料日 10/29 判斷：4577、2466、4526 為「即將處置（10/30 起）」，3287 為「處置中（至 10/29）」。若 QA 時重新執行 `collect`（資料日變成 10/30），狀態會依新資料日改變（例如 4577 變「處置中（至 11/05）」、3287 消失），屬預期。
3. T-A1-7（模擬櫃買失敗）與 T-A1-6（下一個交易日 `collect`）**未執行**：前者會真的打證交所／櫃買行情端點（與補抓同一主機，為避免限流沒有在本輪執行），後者需等下一個交易日。T-B10-4（比對 API 與資料表）會再打 4 次 OpenAPI，也留給 QA。
4. 驗 P5 時 K 線要停在「日」模式；游標要移到該日 K 棒。2317 2026/07/02 應顯示「不比價」，3152 2026/06/30 應顯示「-35.5 (-9.86%)」。
5. P3 用 Console 改 `App.latest.forecast.backtest.acc` 後要呼叫 `renderToday()`；改完記得重新整理，避免影響後續測試。
6. P7 的門檻存在 `localStorage` 的 `tw.rtv`，測「預設 0.5 億」前請先清掉。
7. `tests/test_iter01.py` 只用標準函式庫，`python3 tests/test_iter01.py` 即可執行。

---

## 七、QA 修正（對應 `05-qa.md`）

| 缺陷 | 修改 | 檔案:行號 |
|---|---|---|
| QA-01 指數表欄位改名／列太短時丟 `KeyError`／`IndexError`，整日行情不寫入 | `parse_taiex()` 先檢查 `指數、收盤指數、漲跌(+/-)、漲跌點數` 四欄都在 `fields` 內，不符就略過該表；資料列長度不足就略過該列 → 回傳 `None`。`collect_for_date()` 既有邏輯會印「⚠️  MI_INDEX 找不到加權指數表」並照常寫入個股（以 mock `request` 驗證：欄位改名時 `fetch_twse_daily` 回傳個股 1 筆、指數 `None`） | `twstock/collectors/daily.py:23-33` |
| 同上（測試） | `test_parse_taiex` 補「欄位改名 → None」「列太短 → None」兩個斷言 | `tests/test_iter01.py:39-46` |
| QA-02 375px 下月營收表格比卡片寬 | 520px 以下隱藏「月增」欄（第 3 欄），採 QA 建議 (a) | `site/app.css:153` |
| QA-03 Plotly hover 格式 `+.2f` 無效、正值沒有 + 號 | 累計年增折線加 `customdata`（`sgn()` 格式化，null 為「--」），`hovertemplate` 改用 `%{customdata}` | `site/stock.js:323-325` |

驗證（2026-10-30，未重新 collect）：
- `python3 tests/test_iter01.py` 全部通過；`py_compile`（`twstock/**/*.py`、測試檔）、`node --check site/app.js site/stock.js` 通過；`python3 -m twstock export` 成功（資料日 2026-10-29）。
- 8001 驗證後已關閉，埠 8000 沒有動：
  - 375×812 下，2330、4577 的 `#revBox .tbl-wrap` `scrollWidth` 與 `clientWidth` 都是 309（修正前 361／309），表頭為「年月、營收（億）、年增、累計年增」；桌機仍是 5 欄。
  - 滑鼠移到 2330 月營收圖，hover 顯示「累計年增 +29.95%」，Console 沒有 `bad format` 警告。
- 泡泡圖 `site/app.js` 的 `+.1f`／`+.2f` 是既有問題，QA 已註明不在本輪範圍，沒有修改。
