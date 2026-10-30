# 第 02 輪｜Programmer：實作紀錄

- 撰寫日期：2026-10-30
- 依據：`03-design.md`（實作依據，含附錄 B 測試）、`02-pm.md`（範圍、驗收條件、範圍變更紀錄）
- 本輪項目：B1-核心、P14、P16、P13、A2、P15，全部完成；README（R1～R10）與 `__main__.py`（M1～M6）已同步更新。依設計「建議實作順序」執行：建表 → 事件收集器與補抓 → A2 收集與補抓（背景）→ `export.py` → `stock.js`／`app.js`／`app.css` → README／docstring → 匯出、測試、自測。
- 未 commit、未 push、未動 `.env`、未重新執行 `collect`。測試用埠 8001 已關閉。

> **使用者需先執行一次 `python3 -m twstock setup-db`**（本輪新增 `price_events`、`insti_amount`；`export` 會查這兩張表，沒建表會失敗）。本機資料庫我已執行兩次，皆成功。

---

## 一、各項目修改內容

### B1-核心 還原價格與事件標記
| 檔案 | 函式／位置 | 修改 |
|---|---|---|
| `twstock/db.py` | `DDL`、`setup_database()` | 新表 `price_events`（放在 `stock_alerts` 之後、索引之前，DDL 照設計）；完成訊息加 `price_events`、`insti_amount` |
| `twstock/collectors/alerts.py` | `roc_date()` | 先把「年／月」換成 `/`、去掉「日」，支援 `115年09月02日`；docstring 更新 |
| `twstock/collectors/events.py`（新檔） | `EVENT_TYPES`、`CHUNK_DAYS`、`LOOKBACK_DAYS`、`_SOURCES`、`parse_events()`、`fetch_events()`、`collect_events()` | 照設計全文：四個端點（TWT49U、TWTAUU、TWTB8U、櫃買 exDailyQ）、半年一段、全部抓完才 MERGE、只寫入 `stocks` 已有的代號 |
| `twstock/__main__.py` | `cmd_collect()`、新增 `cmd_events()`、子指令 `events` | `collect` 在處置／注意股之後呼叫 `collect_events(d − 7 天, d)`（`except FetchError` 印 ⚠️ 繼續）；`events --start --end` 失敗印 ❌ 回傳 1 |
| `twstock/export.py` | 常數 `ADJ_MIN/ADJ_MAX`、`_SRC_RANK`；新增 `_price_events()`、`_adj_factors()`；`export_all()` | 載入 `price_events`；個股迴圈產生 `ev`、`af`；個股 JSON 加 `ev`（放在 `prices` 之後）；`h52`／`l52` 改為還原價並 `_f` 到 0.01；匯出最後印「📌 還原事件 N 筆（上櫃反推 M 筆）」、係數超出範圍警告、未對到事件警告 |
| `site/stock.js` | 新增 `adjFactors()`、`EV_LABEL`；`aggregate(data, mode, adj)` | 還原開高低收與漲跌、`pc` 用原始價、`rel`、`ev`；週／月合併事件 |
| 同上 | `renderStock()` | `adjSeg`「還原／原始」切換（`localStore('kadj')`、`title` 說明）；`draw()` 集中重畫（K 線隨切換、訊號固定還原）；52 週副標「還原權值」／「自 YYYY/MM/DD，還原」；成交量、法人標籤加「未還原」 |
| 同上 | `buildCharts()` | `kSer.setMarkers()` 事件標記；`showLegend()` 改用 `raw[i].pc`、加事件內容與「相對 MM/DD 收盤」、不比價 title 改字；刪除末尾的 `renderSignals()` 呼叫 |
| `site/app.css` | | `.ev-note` |

### P14 漲跌三分支
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | 新增 `_changes()`、`_side()`；`export_all()` | 取代原本 `chs` 迴圈；`latest` 的 `ch`／`p` 與漲跌家數改用 `chs[-1]`；分支 2 輸出 `rel`。`daily[...]["pct"]` 未動（依設計） |
| `site/app.js` | `pctCell` | 有 `rel` 時加 `.rel` 與 tooltip「相對 MM/DD 收盤（前一交易日無成交）」 |
| `site/stock.js` | `renderStock()` 標頭 | 漲跌後加「相對 MM/DD 收盤（前一交易日無成交）」 |
| `site/app.css` | | `.rel` |

### P16 股本變動註記
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/export.py` | 常數 `CAP_TYPES`、`CAP_DAYS`；新增 `_cap_event()` | 個股 JSON 在 `fund` 之後加 `capchg`（符合才輸出） |
| `site/stock.js` | `renderStock()` 指標卡 | 本益比、殖利率副標 `capSub`（「09/02 除權，官方值可能尚未調整」） |

### P13 技術訊號
| 檔案 | 函式 | 修改 |
|---|---|---|
| `site/stock.js` | 常數 `SIG_MIN`、`MACD_MIN`；`renderSignals(rows, mode)` 改寫；模板 `<h2 id="sigTitle">` | 標題加週期、去掉尾端無成交、MACD 需 ≥ 35 根、有效訊號 < 3 顯示「資料不足，無法判讀」（中性樣式）；由 `draw()` 以還原價呼叫 |

### A2 官方三大法人金額
| 檔案 | 函式 | 修改 |
|---|---|---|
| `twstock/db.py` | `DDL` | 新表 `insti_amount` |
| `twstock/collectors/daily.py` | 常數 `AMOUNT`；新增 `_amount_unit()`、`parse_insti_amount()`、`fetch_twse_insti_amount()`、`merge_insti_amount()`；`collect_for_date()` | `ALL_DATASETS` 不變；`AMOUNT` 在同一交易內 MERGE；只抓 `AMOUNT` 且無資料時印「ℹ️ 無三大法人買賣金額…」回傳 False |
| `twstock/collectors/history.py` | import、`_TABLE`、`SECONDS_PER_DAY` | `AMOUNT → insti_amount`，每日 4 秒 |
| `twstock/__main__.py` | `cmd_collect()`、`history --only` | `collect` 在事件之前呼叫 `collect_for_date(d, (AMOUNT,))`（`except FetchError` 印 ⚠️）；`--only` 加 `amount` 與 help |
| `twstock/export.py` | 常數 `INSTI_DAYS`；新增 `_insti_official()`；`export_all()` | 讀 `insti_amount`；`latest.insti_official`、`latest.insti_otc`（上櫃估算，迴圈內與 `insti_total` 同段累加）；`insti` 保留 |
| `site/app.js` | 新增 `minibars()`、`instiCard()`；`renderToday()` | 原三大法人卡換成 `instiCard(L)`；無官方資料時顯示第 1 輪估算卡 |
| `site/app.css` | | `@media (max-width:520px){.g-stats .insti{grid-column:1/-1}}` |

### P15 指數卡 60 日漲跌幅
| 檔案 | 函式 | 修改 |
|---|---|---|
| `site/app.js` | `indexCard()` | 底行改為「近 60 個交易日 +x.x%」／「自 MM/DD 起 ±x.x%（N 個交易日）」，顏色與走勢線一致；`s` 少於 2 點不顯示 |

### README／`__main__.py`
- README：R1～R10 全部依設計第七節文字修改（R6、R7 取代舊說明；R8 放在 R7 後；R9 放在「個股法人…估算值」後；R10 放在最後一條之前）。
- `__main__.py`：M1（collect 括號）、M2（`--only amount` 行）、M3（`events` 行）、M4（`choices`／help）、M5（`events` 子指令）、M6（`collect` 兩個 `try`、import `timedelta`）。`python3 -m twstock --help` 看得到 `events`，`history --help` 的 `--only` 有 `amount`。

### 測試
- `tests/test_iter02.py`（新檔）：**直接採用設計附錄 B 原文，未修改**。8 個測試全部通過，沒有發現斷言與設計公式不一致之處。

---

## 二、執行過的指令與結果

| 指令 | 結果 |
|---|---|
| `python3 -m twstock setup-db` ×2 | 兩次皆成功；`OBJECT_ID('price_events')`、`OBJECT_ID('insti_amount')` 都有值 |
| `python3 -m twstock events --start 2025-10-30 --end 2026-10-30`（背景，`logs/iter02_events.log`） | **1,694 筆，約 40 秒，8 次請求，0 次失敗／重試**。來源：TWT49U 955、TPEX_EX 716、TWTAUU 20、TWTB8U 3。腳本 A `ok`（TWT49U 8～9 月 208 筆） |
| 同上重跑（`logs/iter02_events_rerun.log`） | 1,694 筆、18 秒；表內仍 1,694 筆、8～9 月仍 208 筆（MERGE 不重複） |
| `python3 -m twstock history --start 2026-07-31 --end 2026-10-30 --only amount`（背景，`logs/iter02_amount.log`） | **61 天全部成功，366 列，3 分 31 秒（23:15:39～23:19:10），0 次失敗／限流** |
| 同上重跑（`logs/iter02_amount_rerun.log`） | 「待抓 0 天」 |
| `python3 -m twstock export`（`logs/iter02_export.log`） | 約 15 秒；「📌 還原事件 1721 筆（上櫃反推 29 筆）」；沒有係數超出範圍的事件；「⚠️ 上市官方漲跌 0、收盤 ≠ 前收，但找不到除權息／減資事件 **2 筆**：1435 2026-06-18、8105 2026-08-27」 |
| `python3 tests/test_iter01.py`、`python3 tests/test_iter02.py` | 皆「全部通過」 |
| `python3 -m py_compile twstock/*.py twstock/collectors/*.py twstock/analysis/*.py`；`node --check site/app.js site/stock.js` | 皆通過 |
| `python3 -m twstock serve --port 8001 --no-browser`（背景） | 以 python 腳本與內建瀏覽器自測後已停止，8001 無監聽 |

### B1 驗收 9：未對到事件 2 筆的原因
與設計預估相同：1435（前一資料列 4/28 → 6/18）與 8105（8/18 → 8/27）都是**停止買賣後恢復交易**，中間沒有資料列，前一列有成交，不是除權息；維持「不比價」、漲跌家數算平盤。設計附錄 A 提到的 10 月 18 筆未對到，補抓 10 月 TWT49U 後已全部對到。

### 檔案大小
| 檔案 | 修改前 | 修改後 | 增減 |
|---|---|---|---|
| `latest.json` | 671,210 bytes | 673,566 bytes | +2,356（+0.35%；`insti_official`、`insti_otc`、5 檔 `rel`、`h52`／`l52` 還原後小數位變多） |
| 個股 JSON 合計（1,999 檔） | 28,220,699 bytes | 28,320,851 bytes | **+100,152（+0.35%）**，腳本 E 印 `99964 0.0035`；≤ 5% |

> 匯出訊息的「latest.json 658 KB」是 bytes ÷ 1024；修改前同口徑為 655 KB（設計寫的 671 KB 是 ÷ 1000）。

---

## 三、驗收範例實際數值（2026-10-30 資料）

| 項目 | 實際值 | 設計預期 |
|---|---|---|
| 6669 52 週高／低 | 2,875（副標「還原權值」）／1,071.94；事件 6/22 息 5,130→4,985.6、9/2 權 7,800→2,614.99 | 相同 |
| 6669 9/1→9/2 還原漲跌 | −0.19%（−4.99），資訊列「除權　前收 7,800　參考價 2,614.99」，K 棒下方有「權」標記 | 相同 |
| 5904 52 週高／低、事件 | 92.3／37.77；`2026-07-16息`、`2026-08-10調`；capchg `{d:2026-08-10, t:調}` | 相同 |
| 3086 52 週高／低、事件 | 47.5／20.05；`2026-04-20調`；無 capchg | 相同 |
| 2330 52 週高／低 | 2,590／1,358.31；四個除息日 2025-12-11、2026-03-17、06-11、09-16 | 相同 |
| 2330 MA60 還原／原始 | 2427.82／2431.58（差 0.15%） | 相同 |
| 2317 52 週高／低；7/02 漲跌 | 304.91／182.07；−1.82（−0.76%） | 相同 |
| T-B1-10 週／月線 | `[9.72, 33.1, 6.26, -89.03]` | 相同 |
| T-B1-11 原始模式 OHLC | `true`（與 `prices` 完全相同）；所有個股 JSON 的 d/o/h/l/c/v 與修改前逐值相同；`latest` 的 `c` 全部與修改前相同（腳本 C `ok`） | — |
| 1213／7732／8481／8487／9918 | −0.07（−0.94%）／+0.1（+0.3%）／+0.2（+0.5%）／−1.4（−2.07%）／−0.05（−0.12%），`rel` 皆 2026-10-28；1213 標頭「相對 10/28 收盤（前一交易日無成交）」、昨收 7.44；自選表 tooltip 正確 | 相同 |
| 漲跌家數 | 上市 漲 94／跌 945／平 46；上櫃 127／693／56 | 相同 |
| P16 | 6669、6949（9/7 面）、5904 有註記；2330、3086、8422 無；共 50 檔有 `capchg`（設計估約 40 檔） | 相同（檔數略多） |
| P13 2330 | 月線「資料不足，無法判讀」（1 項）；週線 5 個標籤（含 DIF、MACD 柱，無 MA60）；日線 6 個；T-P13-4 `[true, true]`；原始模式訊號卡內容與還原相同 | 相同 |
| A2 10/30 | 外資 −1,124.7 億、投信 +236.2 億、自營 −513.7 億、合計 −1,402.2 億；20 根柱（09/30～10/30）；外資「連賣 2 日」（`fs = −2`，腳本 F 也是 −2） | 相同 |
| A2 上櫃估算 | 外資 −82.6 億、投信 +40.1 億、自營 −17.5 億 | 設計表中的 `-75.2/35.0/10.1` 只是欄位範例 |
| P15 | 加權「近 60 個交易日 +4.2%」（up）；櫃買「自 10/01 起 -11.6%」（dn） | 相同 |

---

## 四、與設計文件不同之處

程式邏輯、欄位、文案都照設計，沒有刻意偏離。以下是實測與設計描述不一致的地方：

1. **T-P14-8「上市 `ch == 0` 且收盤 ≠ 前收」預期印 0，實際 22 筆**：22 筆全部是事件生效日，收盤剛好等於參考價（例：1217 2026-04-24 前收 10.3、參考價 10.05、收 10.05），分支 1 得到 0 是正確的平盤。第二段（`ch is None and c is not None`）實際 2 = N，符合預期。建議 QA 把腳本改為排除事件日。
2. **事件日漲跌與官方漲跌有 0.01～0.12 元的差異（24 筆，原本也有數值的列）**：例如 6931 2026-10-27 官方 −0.15、本系統 −0.13；4968 7/13 官方 −1.5、本系統 −1.4。原因：TWT49U／exDailyQ 的「參考價」是計算值，交易所實際的開盤參考價會依升降單位取整，官方漲跌是相對取整後的價格。設計規定分支 1 一律「收盤 − 參考價」，所以照設計實作，列為已知限制（漲跌幅差異 < 0.3 個百分點）。另有 1 筆上櫃（2949 7/31）是事件生效日當天無成交，下一個成交日改相對參考價（P14 邊界情況），也和官方不同。
3. **手機 375px K 線卡**：「日週月」「還原原始」在同一行，「回到最新」換到第二行（設計預估三組放得下一行）。沒有溢出（`scrollWidth = 375`），沒有額外修改。
4. **`__main__.py` docstring 的 `events` 行**：設計範例多一個空白，我對齊到其他行的說明欄位（純排版）。
5. **T-B1-14（腳本 D）沒有照原樣執行**：腳本 D 會重新抓 10/30 行情，與「不要重新執行 collect」的指示衝突。改用離線模擬：把行情、期貨、指數、處置、產業別、產業鏈都換成不連網的空函式，事件與金額端點丟 `FetchError`，執行 `main(['collect', '--date', '2026-10-30', '--no-revenue', '--no-export'])`。輸出依序是「⚠️ 三大法人金額抓取失敗：模擬失敗」、「⚠️ 除權息／減資事件抓取失敗，下次執行會再補：模擬失敗」，`exit=0`，沒有寫入資料庫。原始的腳本 D 留給 QA 決定是否執行。

---

## 五、已知限制

- 成交量、法人張數未還原（B1-延伸）；K 線圖標籤已註明「未還原」。
- 上櫃停牌期間有「無成交」資料列時，恢復交易當天不反推，可能漏掉減資事件（設計 B1-7）。
- 事件日漲跌用計算參考價，與官方取整後的漲跌可能差幾檔（見第四節第 2 點）。
- 板塊漲跌幅（`daily[...]["pct"]`，泡泡圖顏色）仍用官方漲跌，上市除權息日為 0（設計建議第 3 輪改）。
- 官方法人金額只補到 2026-07-31；外資連買／連賣天數以資料表全部日期計算，補滿一年需自行執行 `history --start 2025-10-30 --only amount`（約 16 分鐘）。
- 日後往前補抓日線時，須用同一區間執行 `events`（README R10）。

---

## 六、給 QA 的注意事項

1. 先確認 `setup-db` 已建表；`site/data/` 已用本輪程式重新匯出（資料日 2026-10-30）。
2. 補抓不需要再跑；若要驗「重跑不重複」，`events` 一次 8 個請求、`history --only amount` 重跑為「待抓 0 天」不打網路。兩者不要同時跑。
3. 瀏覽器測試請用埠 8001，結束時關閉；`localStorage['tw.kadj']` 測完記得切回「還原」。
4. T-P14-8 的第一段請排除事件日（見第四節第 1 點）。
5. T-B1-14 的原始腳本 D 會重新抓 10/30 行情（約 1 分鐘、多次請求），是否執行請自行判斷；我用的離線模擬方式見第四節第 5 點。
6. 腳本 B 的 `ev` 比對裡 `p` 是 `5130.0`（float），Python 判斷 `5130 == 5130.0` 成立，不影響結果。
