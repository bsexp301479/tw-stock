# 第 07 輪｜System Analyst：設計文件

- 撰寫日期：2026-11-04（週三）晚間
- 輸入：
  - `02-pm.md` 的本輪範圍：F7-1、F7-2，編號沿用 PM。
  - 另外參考 `01-analyst.md`（群益端點、欄位對照）和第 6 輪 `03-design.md`（格式比照）。
  - 使用者決定：**D12 = A**（群益 4 檔＋彙總排行）、**D13 = A**（明細沒有市值時存 NULL），以及「進 SA」。
- 依據：
  - 閱讀的程式：
    - `twstock/{health,fetch,export,config,__main__}.py`
    - `collectors/{holdings,daily,history}.py`
    - `site/{app,stock}.js`
    - `tests/test_iter03.py`（`World`）、`tests/test_iter05.py`、`tests/test_iter06.py`
    - README
  - 資料庫只做唯讀查詢，沒有執行 `setup-db`，沒有任何寫入。
  - **外部請求 7 次**（附錄 A）：PM 第四節列的「PG 實作前抽樣」改由 SA 先做，結果寫進設計。PG 不需要再抽樣。
- **所有設計都已經在專案外、不含 `.env` 的暫存副本做成原型並實際跑過**：
  - **測試**：`test_iter01`～`test_iter07` 全部通過。`test_iter07.py` 有 12 個測試。
    - 另做了 5 個「突變」反證，每一個都會讓 `test_iter07` 失敗：
      - Gap B 拿掉 `today ≥ post`。
      - Gap A 拿掉生效日比對。
      - `code 400` 不檢查訊息。
      - 彙總排行不排除未更新的 ETF。
      - 不標示新進、出清。
  - **解析真實回應**：
    - 分析師和 SA 保存的 9 份群益回應用原型的 `parse_capital` 全部解析正確。
      - 00982A 三個持股日的檔數、2330 股數都和分析師抽樣相同。
      - 00997A 的海外代號正確，例如 `CRWD US`。
      - `code 400` 判為尚未公布。
  - **隔離（F7-1 #6、F7-2 #6）**：
    - 用同一份資料庫，以原型匯出，再用新的 `logs/iter07_compare.py` 和正式網站 11/04 21:32 的匯出比對。
    - 結果「✅ 相同」：`latest.json`、`stocks` 1,999 檔、`etfs` 4 檔都相同。
    - 只多出新鍵：`latest.json` 的 `active_rank`、`etfs/*.json` 的 `trust`。
    - 也多出群益 4 個資料集的狀態列。
  - **畫面**：原型網站用 8001 埠預覽，結束後已關閉。
    - 彙總頁 `#/etf/active` 在桌面版正常顯示（真實資料是統一 4 檔）。
    - 375 px 沒有整頁水平捲動，表格在卡片內捲動，和既有頁面相同。
    - 今日頁的小卡正常顯示。
    - 點列內的 ETF 代號會進持股頁，不會被整列的個股連結蓋掉。
    - 持股頁的來源文字正確。
  - **專案程式、資料庫內容、排程都沒有修改。**
- 本文件只描述設計：
  - 附錄 C 是原型對現有程式的完整 diff。
  - 附錄 D 是完整的 `tests/test_iter07.py`。
  - 附錄 E 是 PG 用的 `logs/iter07_compare.py`。
  - 這三份**都可以直接套用**。寫法可以改，但**函式名稱、鍵名、判斷式、輸出訊息請照本文件**，`test_iter07.py` 與 QA 會照著驗。

> **影響設計的實測發現（PM 文件沒有預期到）**
> 1. **00997A 的 delay = 1，已經證實。**
>    - 最新一期：生效日 11/05，持股日 11/03。
>    - 第一天：生效日 4/16，持股日 4/14，也就是上市日當天就有持股。
>    - 國內 3 檔在上市日或資料窗口起點都抽樣成功：
>      - 00982A：10/30。
>      - 00992A：12/30。
>      - 00415A：10/20。
> 2. **群益在臺股臨時休市前一日有完整明細，不會出現 Gap B。**
>    - 00982A 持股日 7/9：生效日 7/13，54 檔。
>    - 00982A 持股日 10/22：生效日 10/27，57 檔。
>    - 這和統一不同（統一是只有彙總）。Gap B 的判斷照樣保留，以防萬一，但補歷史時預期 0 筆。
> 3. **補歷史是 596 次，不是 PM 估計的 610 次**：
>    - 00982A：245 次。
>    - 00992A：203 次。
>    - 00997A：138 次。
>    - 00415A：10 次（10/23 颱風休市）。
>    - 經過 3 秒節流，約 32 分鐘。
> 4. **舊測試有 3 處把「持股 4 檔」寫死**，HOLDINGS 變成 8 檔之後會失敗。需要最小修改（第三節），這是本輪唯一動到舊測試的地方：
>    - `test_iter03` 狀態 JSON 的長度上限 1500：改成依資料集數計算。
>    - `test_iter05` 的 `keys[-6:]`：改成依 HKEYS 長度計算。
>    - `test_iter05` 的「8/26 每檔都有」：排除 8/26 之後才上市的 00415A。
>    - 另外，`test_iter03` 的假網站 `World` 要加上群益端點，否則所有收集流程測試都會收到「欄位不符」。
> 5. **彙總排行的金額要在四捨五入之前過濾和排序**。
>    - 原型第一版先四捨五入到 0.01 億，結果 1 張 10 元的加碼變成 0 而消失。
>    - `test_f72_edges` 抓到這個問題，已經修正。
> 6. **權重不放寬，`DECIMAL(7,2)` 不改**（PM 第五節第 4 點）：
>    - 統一原本就是 2 位小數。
>    - 網站只顯示 2 位。
>    - 群益在寫入前四捨五入到 2 位，股票權重合計則用 4 位原值加總後再四捨五入。
>    - **本輪沒有任何資料表變更**。PG 仍要在補歷史之前用 `backup` 備份一次。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | F7-1 群益收集 | F7-2 彙總排行 | 附錄 |
|---|---|---|---|
| `twstock/health.py` | `Fund` namedtuple，`HOLDINGS` 加 4 檔與投信；`SPECS` 改用欄位名稱 | | C |
| `twstock/fetch.py` | `MIN_INTERVAL` 加 `www.capitalfund.com.tw` 3.0 秒 | | C |
| `twstock/collectors/holdings.py` | `CAP_URL`、`CAP_NONE`、`cap_date`、`parse_capital`；`fetch_holdings` 依投信分派 | | C |
| `twstock/export.py` | `holding_export` 加 `trust` | `ACTIVE_TOP`、`active_rank`；`latest.json` 加 `active_rank` | C |
| `site/app.js` | 持股頁來源文字、未支援提示 | `#/etf/active`、`renderActive`、今日頁 `activeCard`、ETF 頁連結 | C |
| `site/stock.js` | 「主動 ETF 持有」說明文字 | | C |
| `twstock/__main__.py`、README | 說明文字 | README 新增一條 | C |
| `tests/test_iter03.py`、`tests/test_iter05.py` | 假網站加群益；3 處寫死 4 檔的地方改成依數量 | | C |
| `tests/test_iter07.py`（新檔） | 10 個測試 | 2 個測試 | D |
| `logs/iter07_compare.py`（新檔，不進版本控制） | 排除 `trust` 與新資料集 | 排除 `active_rank` | E |

| 項目 | 程式（含 README） | 測試 |
|---|---|---|
| F7-1 | 約 115（holdings 45、health 11、export 4、fetch 1、site 文字、README） | 舊測試 +23；新 10 個測試約 150 |
| F7-2 | 約 110（export 55、app.js 45、README） | 新 2 個測試約 55 |
| **合計** | **約 225 行**（PM 估 400，因為沒有改表，畫面也只用既有樣式） | **約 250 行** |

### 建議實作順序

| # | 步驟 | 驗證 |
|---|---|---|
| 1 | `python3 -m twstock backup`（改程式、補歷史之前） | rc=0，`04-dev.md` 記錄檔名與大小 |
| 2 | 匯出基線：把目前的 `site/data` 複製到 `logs/iter07_before/` | — |
| 3 | 套用附錄 C（health、fetch、holdings、export、`__main__`、README、site、`test_iter03`、`test_iter05`） | `test_iter01`～`06` 全過 |
| 4 | 套用附錄 D `tests/test_iter07.py`、附錄 E `logs/iter07_compare.py` | `test_iter07` 全過 |
| 5 | **隔離比對**（補歷史之前）：`python3 -m twstock export && python3 logs/iter07_compare.py logs/iter07_before site/data` | 「✅ 相同」（F7-1 #6、F7-2 #6） |
| 6 | 補歷史：`python3 -m twstock history --start 2025-10-30 --only holdings` | 約 596 次請求、約 32 分鐘；記錄實際請求數與耗時 |
| 7 | `python3 -m twstock check` | rc=0（F7-1 #1） |
| 8 | 附錄 B 的 SQL | B-1～B-4 都和預期值相同 |
| 9 | 重跑步驟 6 的指令 | 「待抓 0 天」、請求 0 次（F7-1 #3） |
| 10 | `python3 -m twstock export`，用 8001 埠預覽（結束時關閉） | F7-1 #8、F7-2 #1～#4、#7 |

- 第 5 步只能在補歷史之前做。補歷史之後，`etfs` 會多 4 個檔案、`stocks/*.json` 的 `active` 會多出群益，這是預期的差異。
- 第 6 步若在 17:30 之後執行，11/05 起每晚的 `collect` 會自然接手，不需要另外處理。

---

## F7-1. 群益投信持股收集（優先 1，E2-3）

### F7-1-1 對應驗收條件

| PM 驗收 | 設計的對應 | 驗證 |
|---|---|---|
| #1 `check` rc=0 | `HOLDINGS` 加 4 檔，沿用第 5、6 輪的 `health` 流程 | 實作順序第 7 步 |
| #2 抽查 3 個持股日 | 附錄 B-2 | QA |
| #3 重跑 0 請求 | `history` 只請求缺的「檔 × 日」（第 5 輪） | 第 9 步；`test_f71_history_since_and_rerun` |
| #4 日常收集 +4 次 | 4 個新資料集各 1 次；資料齊全時 0 次 | `test_f71_collect_published` |
| #5 00997A delay | **SA 已抽樣**：delay = 1（附錄 A #1、#7） | `test_f71_config`、`test_f71_date_and_dispatch` |
| #6 統一 4 檔不受影響 | 統一的 `parse_pcf`、請求參數都沒有改；隔離比對 | `test_iter05`、`test_iter06` 全過；第 5 步 |
| #7 mock 1～6 | 第 F7-1-5 節 | `test_iter07` |
| #8 網站 | 持股頁、個股卡、ETF 清單沿用既有程式，只改來源文字 | 第 10 步 |
| #9 README、`--help` | 第四節 | QA 逐條核對 |

### F7-1-2 設定：`health.HOLDINGS`

```python
Fund = namedtuple("Fund", "fund delay since trust")
HOLDINGS = {"00981A": Fund("49YTW", 0, None, "統一"), ...,                          # 統一 4 檔不變，只多投信欄位
            "00982A": Fund("399", 0, None, "群益"), "00992A": Fund("500", 0, date(2025, 12, 30), "群益"),
            "00415A": Fund("504", 0, date(2026, 10, 20), "群益"), "00997A": Fund("502", 1, date(2026, 4, 14), "群益")}
```

- `fund`：投信的基金代碼。統一是 `49YTW`；群益是 `fundNo`，例如 `399`。
  - 寫成常數，不在收集時呼叫 `etf/items`（PM 範圍外）。
- `since`：沿用第 5 輪的定義，`etf_daily` 最早一筆。2025-10-30 之前上市的填 None。
  - 00982A 在資料窗口之前就上市了，所以是 None。
- 用 namedtuple 是因為原本有 3 個地方用 `(_, delay, since)` 解構，加欄位後會失敗。現在一律改用欄位名稱。
  - 統一 4 檔的順序和值不變，所以 `SPECS`、`DAY_KEYS` 的前段順序也不變。
  - 群益接在後面：00982A、00992A、00415A、00997A。

### F7-1-3 請求：`holdings.fetch_holdings`

| 投信 | 請求 |
|---|---|
| 統一（不變） | `POST GetPCF {"fundCode": "49YTW", "date": "115/11/05", "specificDate": true}` |
| 群益 | `POST https://www.capitalfund.com.tw/CFWeb/api/etf/buyback {"fundId": "399", "date": cap_date(生效日)}` |

- `cap_date(post)` = 生效日前一天的 `T16:00:00.000Z`。
  - 這就是官網送出的 JavaScript `Date`（台灣時間 0 點）的 ISO 字串。
  - 例如生效日 2026-06-02 → `"2026-06-01T16:00:00.000Z"`。
  - 附錄 A #2～#6 都用這個格式取得正確的那一天。
- 生效日沿用 `post_date(d, delay, closed)`。
- 一律經過 `fetch.request`，沿用節流（3 秒）、退避重試與 `_dead_hosts`。
  - 群益主機失敗時，只有群益 4 檔失敗（`test_f71_collect_errors_only_that_source`）。
- 標頭沿用 `fetch.py` 既有的 Session，**不加任何標頭**。

### F7-1-4 判斷規則（`holdings.parse_capital`，附錄 C）

| # | 回應 | 判定 | 實際回應 |
|---|---|---|---|
| 1 | 不是 dict，或沒有 `code` | `SchemaError("群益 buyback 回應缺少 code")` | — |
| 2 | `code 400` 且 `message` 含「沒有查詢到」 | `None`：尚未公布 | 附錄 A：分析師 #13、#14（11/06、11/01 週日）；`{"code":400,"data":null,"message":"沒有查詢到該條件的數據"}` |
| 3 | 其他 `code`（含訊息不同的 400）、`data` 不是 dict、缺 `pcf`／`stocks`、`pcf` 是空的 | `SchemaError("群益 buyback 回應 code N：訊息")` | — |
| 4 | `date2` ≠ d，且 `date1` = 要求的生效日 | **Gap A**（`src_date` = `date2`） | 用 00997A 最新回應配錯 delay 時就是這個情況（`test_f71_parse_gaps`） |
| 5 | `date2` ≠ d，`date1` ≠ 生效日 | `None` | — |
| 6 | `date2` = d，`stocks` 為空，`date1` = 生效日，`nav > 0`，今天 ≥ 生效日 | **Gap B**（`nav` = `pcf.nav`） | 本次未遇到（發現 2） |
| 7 | 同 6，但今天 < 生效日，或 `nav` 是 0 | `None`：可能只是還沒寫完 | 第 6 輪發現 2 的規則 |
| 8 | `futures` 不是空的 | `SchemaError("群益 buyback 有期貨部位，欄位尚未對應")` | 本次 9 份都是空的 |
| 9 | 其他 | 寫入 | 附錄 A 各次 |

- **`code 400` 一律當成「尚未公布」，不區分非交易日**：
  - 收集和補歷史只會請求 `tradingcal` 算出的生效日，不會刻意請求非交易日。
  - 如果 `tradingcal` 漏了臨時休市日，該日會一直「尚未公布」，22:00 後在 `check` 顯示「❌ 00982A持股：缺 …」，和統一一樣會浮現，不會悄悄漏掉。
  - 使用者用 `update-calendar` 補上休市日後，就會自動消失。這是第 3 輪既有的機制。
- **只有「沒有查詢到」的 400 才算尚未公布**（PM 風險 2）：
  - 參數格式錯誤、來源壞掉時，訊息不同，會判成欄位不符，當天就報錯，不用等到 22:00。
- **期貨用報錯而不是略過**：
  - 群益國內 ETF 目前沒有期貨，欄位名稱也還不知道。
  - 如果悄悄略過，彙總的期貨口數會是錯的 0。
  - 報錯的話，`check` 會立刻顯示，而且來源可以指定日期，修好後用 `history` 就能補回，資料不會遺失。
- **群益不經過第 6 輪的 Gap A 情境也正確**：國內 3 檔不受海外休市影響。00997A 遇到美國假日時，預期會出現 A，判斷式和統一相同。

### F7-1-5 欄位對應（D13 = A）

| 資料表欄位 | 群益 | 說明 |
|---|---|---|
| `etf_holding_summary.hold_date` | d（= `pcf.date2`） | |
| `post_date` | `pcf.date1` | |
| `nav` | `pcf.nav` | 元 |
| `units` | `int(pcf.totUnit)` | |
| `nav_unit` | `pcf.pUnit` | |
| `n_stocks` | `len(stocks)` | |
| `stock_weight` | 4 位原值加總後 `round(…, 2)` | 00982A 11/04 = 96.51 |
| `futures_lots`、`futures_amount` | 0、0 | 有期貨時報錯（規則 8） |
| `edited_at` | NULL | 群益沒有 |
| `etf_holdings.asset_type` | `"ST"` | |
| `code`、`name` | `stocNo`、`stocName`（strip） | 海外是 `CRWD US` 這種格式，和統一相同 |
| `month` | `""` | |
| `shares` | `int(share)` | 股 |
| `amount` | **NULL** | D13 = A |
| `weight` | `round(weight, 2)` | `DECIMAL(7,2)` 不改（發現 6） |
| `currency` | `""` | 沒有市值，幣別無意義；群益只給基金幣別（TWD），沒有逐檔幣別 |

- `assets`（現金、保證金、應收付）、`bonds`、`rps`、`characteristics` 都不存。

### F7-1-6 mock（PM #7 → `test_iter07.py`）

| PM # | 測試 |
|---|---|
| 1 已公布 | `test_f71_parse_published`（真實片段：`amount` 是 None、權重 8.31、跨境 `CRWD US`） |
| 2 `code 400` | `test_f71_parse_unpublished_and_schema`；流程用 `test_f71_collect_unpublished`（17:30「⏳ 尚未公布」、22:30「❌ 缺」） |
| 3 Gap A | `test_f71_parse_gaps` |
| 4 Gap B | `test_f71_parse_gaps`（今天 < 生效日、`nav` = 0 都是 None） |
| 5 欄位不符 | `test_f71_parse_unpublished_and_schema`（6 種形狀＋期貨）；流程用 `test_f71_collect_errors_only_that_source`（群益主機失敗、單檔 code 500，統一與其他群益照常） |
| 6 日期參數 | `test_f71_date_and_dispatch`（6/2、1/1 跨年；00997A 持股日 11/03 → 送出 11/04T16；統一參數不變） |
| 另 | `test_f71_config`、`test_f71_collect_published`（重跑不再請求）、`test_f71_history_since_and_rerun`（00415A 從 10/20 開始；10/22 → 生效日 10/27）、`test_f71_export_trust` |

### F7-1-7 網站

- 不需要新卡片：
  - 持股頁 `#/etf/{代號}`、個股頁「主動 ETF 持有」、ETF 清單的「持股」標籤，都依 `latest.json.holdings` 自動涵蓋群益 4 檔。
- `etfs/{代號}.json` 加 `trust`（「統一」／「群益」）：
  - 持股頁註腳改成「資料來源：{trust}投信每日申購買回清單」。
  - 統一的頁面文字不變。
- 未支援提示改成「目前支援統一、群益投信 8 檔主動 ETF」；個股卡說明改成「目前只含統一、群益投信 8 檔主動 ETF」。
- 群益沒有期貨，持股頁的「期貨」卡會顯示「無」，這是既有寫法。

---

## F7-2. 主動型 ETF 彙總排行（優先 2，E2-延伸）

### F7-2-1 對應驗收條件

| PM 驗收 | 設計 | 驗證 |
|---|---|---|
| #1 頁面三個區塊與持股日 | `renderActive`：頁首列出持股日，加上合計加碼、合計減碼、最多檔持有 | 第 10 步 |
| #2 手算核對 | 附錄 B-5 | QA |
| #3 新進／出清 | `e[].new`／`e[].out` | `test_f72_rank` |
| #4 持股日落後 | 規則 2 | `test_f72_rank`（00403A 停在 11/03 → `stale`） |
| #5 mock | 第 F7-2-4 節 | `test_iter07` |
| #6 隔離 | 新鍵 `active_rank` | 第 5 步 |
| #7 375 px | 全寬卡片，表格在 `tbl-wrap` 內捲動 | SA 已在原型確認 |
| #8 8001 | — | PG、QA |

### F7-2-2 規則（`export.active_rank`）

1. **範圍**：`latest.json.holdings` 的 ETF，只算台股（`stocks` 表裡有的代號）。海外股票與期貨不列入。
2. **每檔用自己的最新持股日**：
   - 依 delay 分組，例如國內 delay 0、跨境 delay 1，各組取最新持股日。
   - **最新持股日比同組舊的 ETF 不列入**，放進 `stale`，頁首顯示「未更新：00403A（停在 11/03）」。
   - 這樣，當天某檔還沒收到時，舊的增減不會混進今天的合計。
   - 只有整組都落後時（例如跨境 3 檔都沒收到），才會用舊資料，但頁首一樣列出各檔持股日。
3. **張數**：和持股頁 `holding_table` 相同，每檔都是「股 ÷ 1000 四捨五入」，所以可以用 `etfs/*.json` 的 `d1` 手算核對。
4. **1 日增減**：每檔的「最新 − 前一持股日」（沒持有算 0）。
   - 前一日沒有、最新有 → `new`。
   - 前一日有、最新沒有 → `out`。
   - 張數不變的 ETF 不列在 `e`。
   - **只有一個持股日的 ETF**（剛上市）不列入加減碼，只計入最多檔持有。
5. **5 日增減** `l5`：有第前 5 個持股日的 ETF 才加總；全部都沒有時是 null（畫面顯示「--」）。
6. **估算金額** `a`（億）：Σ 各 ETF「張數增減 × 1000 × 該 ETF 持股日的收盤」÷ 1e8。
   - 收盤取 `last_close`，也就是無成交時用最近收盤，和維持率相同。
   - 有任何一檔 ETF 的收盤是 None → 這檔股票不進加減碼排行。
   - **排序與過濾用未四捨五入的值**（發現 5），輸出時再四捨五入到 2 位。
   - 這是匯出時的計算，**不寫進資料庫**，符合 D13。
7. **排序**：
   - 加碼：`a > 0`，大到小。
   - 減碼：`a < 0`，小到大。
   - 同值時依代號排序。
   - 各取 `ACTIVE_TOP = 20` 名。
   - 選金額而不是權重變化的理由：權重變化含股價漲跌，而且不同規模的 ETF 權重不能相加。
8. **最多檔持有** `held`：
   - 最新持股日有持有的 ETF 數 `k`，越多越前面。
   - 同 `k` 時，用估算市值 `v` = Σ 張 × 1000 × 收盤 ÷ 1e8 排序，大到小。
   - 取 20 名，列出各 ETF 的權重。

### F7-2-3 輸出：`latest.json.active_rank`

```json
{"etfs": [{"c": "00981A", "t": "統一", "d": "2026-11-04"}, …], "stale": [{"c": "00403A", "t": "統一", "d": "2026-11-03"}],
 "buy":  [{"c": "2330", "n": "台積電", "a": 20.45, "l1": 905, "l5": 2423, "e": [{"e": "00403A", "d1": 100}, {"e": "00981A", "d1": 805}]}],
 "sell": [{"c": "3211", "n": "順達", "a": -0.41, "l1": -150, "l5": -150, "e": [{"e": "00403A", "d1": -150}]}],
 "held": [{"c": "3017", "n": "奇鋐", "k": 4, "l": 9644, "v": 272.7, "e": [{"e": "00403A", "w": 5.61}, …]}]}
```

- 以上是原型用真實資料庫（統一 4 檔）匯出的實際值，大小 3.9 KB。8 檔時估計不到 6 KB。
- `holdings` 是空的時候，值是 `null`，網站不顯示任何主動 ETF 彙總。
- 放進 `latest.json` 而不是另開一個檔案的原因：今日頁的小卡也要用，資料量小，可以省一次請求。

### F7-2-4 mock（PM #5 → `test_iter07.py`）

| 情境 | 測試 |
|---|---|
| 合計、排序、`a`、`l1`、`l5`、`e` | `test_f72_rank`：2330 = +200（00981A）−100（00982A）+50（00988A 新進）＝ +150 張、1.5 億；5 日只有 00981A 有，所以是 +200 |
| 新進／出清 | `test_f72_rank`（00988A 新進、00981A 出清 2454） |
| 持股日不一致 | `test_f72_rank`：00988A（跨境 11/03）列入；00403A（國內停在 11/03）→ `stale` |
| 沒有收盤 | `test_f72_rank`：1101 不進加減碼，但會進 `held`（`v` = 0） |
| 只有 1 檔 ETF 有資料 | `test_f72_edges` |
| 只有一個持股日 | `test_f72_rank`：00415A 只進 `held` |
| 小額不會被四捨五入吃掉、前 20 名上限 | `test_f72_edges` |

### F7-2-5 畫面（`site/app.js`）

- **路由**：`#/etf/active`，在 `routes.etf` 判斷 `code === 'active'`。上方的「ETF」分頁會亮起；ETF 代號不會是 `active`。
- **進入點**：
  - 今日頁最下方的小卡「主動 ETF 一起買了什麼」：加碼、減碼各 5 名，加上「完整排行 →」。
  - ETF 頁標題旁的標籤「主動 ETF 彙總」。
- **彙總頁**由上而下：
  1. 頁首：檔數、各檔持股日，以及未更新的 ETF。
  2. 合計加碼。
  3. 合計減碼。
  4. 最多檔持有。
  5. 註腳：估算方式、「新」「清」的意思。
- 合計加碼、合計減碼的欄位：股票、估算金額（億）、1 日張數、5 日張數、參與 ETF（張數增減）。
- 最多檔持有的欄位：股票、檔數、合計張數、估算市值、各 ETF 權重。
- 三個表都用全寬卡片：
  - 原型第一版把加碼、減碼左右並排，「參與 ETF」欄在桌面被截斷，所以改成上下排列。
  - 375 px 時表格在 `tbl-wrap` 內捲動，整頁不會水平捲動。
- **點擊**：
  - 點列 → 個股頁。
  - 點列內的 ETF 代號 → 持股頁。
  - 用自己的 click handler，碰到 `<a>` 時不呼叫 `onRowClick`。`onRowClick` 本身不改，所以不影響其他頁。
- **標示「估算」**：小卡標題旁寫「億，估算」，彙總頁的註腳寫出估算方式（PM 風險 5）。
- 只用既有的 CSS class（`sec`、`card`、`tbl`、`g2`、`al-new`、`pill hold`），`app.css` 不改。

---

## 三、舊測試的修改（附錄 C）

| 檔案 | 修改 | 原因 |
|---|---|---|
| `test_iter03.py` `World.http` | 加 `("etf/buyback", self._cap)` | 假網站要認得群益端點，否則每個收集流程都會多出 4 個「欄位不符」 |
| `test_iter03.py` `World._cap`（新） | 生效日 → 持股日，和 `GetPCF` 共用 `published["GetPCF"]`；未公布時回 400；50 檔 | 舊測試發布某天時，群益也一起發布，所以舊測試的 rc 與訊息不變 |
| `test_iter03.py` `ALL_EP` | 加 `"etf/buyback"` | `w.down.update(ALL_EP)`（全部失敗）要包含群益 |
| `test_iter03.py` `test_dataset_status` | `< 1500` → `< 75 * len(health.SPECS)` | 原本是 21 個資料集、1277 字元，現在是 25 個、1569 字元；保留「平均每個資料集 < 75 字元」的原意 |
| `test_iter05.py` `test_e2_specs` | `keys[-6:]` → `keys[-len(HKEYS) - 2:]` | 持股從 4 檔變成 8 檔 |
| `test_iter05.py` `test_e2_m6_before_listing` | 「8/26 每檔都有」只檢查 `since ≤ 8/26` 的資料集 | 00415A 是 10/20 上市 |

- 以上修改都沒有放寬第 5、6 輪原本要驗證的行為，例如統一的請求參數、筆數、rc、訊息。

---

## 四、README 與其他文件修改清單

### README（PG 依清單修改，QA 逐條核對；原型的 diff 見附錄 C）

1. 檔案表 `collectors/`：「主動型 ETF 持股（統一投信）」→「（統一、群益投信）」。
2. 檔案表 `site/`：ETF 加上「主動 ETF 彙總」。
3. `history --only holdings` 範例的註解：「統一、群益投信 8 檔」；請求數改成「一年約 1,260 個請求、70 分鐘」。
4. 「主動型 ETF 持股」一條：
   - 加上群益的端點與 4 檔代號。
   - 註明「群益的明細只有股數與權重，**沒有市值**（資料庫存 NULL，不推算）」。
   - 國內／跨境的清單加上群益。
   - 「新增 ETF」的說明加上「投信」欄位。
5. 新增一條「主動 ETF 彙總」：位置、內容、估算方式、持股日規則、未更新的處理。

### `twstock/__main__.py`

- docstring 的 `history --only holdings` 註解改成「統一、群益投信 8 檔」。

---

## 五、給 PG、QA 的提醒

### PG

1. **先 `backup`**（實作順序第 1 步）。本輪不改表，但補歷史會寫入約 3 萬列。
2. **隔離比對（第 5 步）一定要在補歷史之前做**，基線是第 2 步複製的 `site/data`。
   - 在套用程式到補歷史之間的這段時間，`check` 與網站狀態列會出現「00982A持股近期資料不足」等 4 項異常。這是預期的，補完就會消失。
   - **不要在 17:30～22:30 排程時段中間套用**，排程目前沒有安裝，但如果使用者手動收集要避開。
3. 補歷史時，`history` 結尾的「ℹ️ 無資料」**預期是空的**：群益沒有 Gap（發現 2）。如果出現日期，請在 `04-dev.md` 列出日期、回應的 `date1`／`date2`。
4. 實際請求數與耗時記在 `04-dev.md`，預期是 596 次、約 32 分鐘。
5. `logs/iter07_compare.py`、`logs/iter07_before/` 不進版本控制，和前幾輪一樣。
6. 測試用 8001 埠，結束時關閉。不要動 `.env`、不要 commit、不要執行還原、不要安裝排程。

### QA

1. 附錄 B 的 SQL 都是唯讀。
2. **手算核對**（F7-2 #2）：附錄 B-5 的步驟。
3. 反例：
   - 把 `logs/iter07_compare.py` 的 `NEW_ETF` 清空 → 應判定「不同」並列出 `etfs/00981A.json` 等檔案。
   - 用暫存副本把 `CAP_NONE` 改成其他字 → `test_iter07` 應失敗。
4. 375 px 截圖：今日頁小卡、`#/etf/active`、群益持股頁（例如 `#/etf/00997A`，海外股為「股」）。

### 待辦（本輪不做）

- 復華、野村（第 8 輪先由分析師探查）。
- 彙總排行的歷史走勢、依產業彙總。
- 群益 `etf/items` 自動偵測新基金。
- 群益期貨欄位的對應：等第一次出現 `SchemaError` 時再依實際回應補上。

---

## 六、使用者決定事項

- 本輪沒有新的待決事項：D12、D13 都已決定。
- 設計上的取捨已經寫在本文件，列出來方便確認：
  - **權重不放寬**（發現 6）：網站只顯示 2 位，統一也是 2 位。
  - **彙總排行放在 ETF 分頁底下**（`#/etf/active`），不新增第 6 個分頁：底部導覽列在手機上已經有 5 個項目。
  - **彙總排行用估算金額排序**，並標示「估算」。

---

## 附錄 A：資料來源紀錄

- 沿用分析師 11/04 21:49～21:53 的 16 次請求（`01-analyst.md` 第六節）。
- SA 另外送出以下 **7 次**，都經過 `fetch.request(isolated=True)`，不重試；原始回應存在工作階段 scratchpad 的 `r7/probe/sa_*`。

| # | 時間 | 請求（`POST /CFWeb/api/etf/buyback`） | 結果 | 用途 |
|---|---|---|---|---|
| 1 | 21:59:48 | 502（00997A）`null` | 200；生效日 11/05、**持股日 11/03**；47 檔，例如 `CRWD US` 63,557 股 | delay = 1（發現 1） |
| 2 | 21:59:49 | 399 生效日 2026-07-13 | 200；持股日 **07/09**；54 檔 | 臨時休市前一日有明細（發現 2） |
| 3 | 21:59:49 | 399 生效日 2026-10-27 | 200；持股日 **10/22**；57 檔 | 同上 |
| 4 | 21:59:49 | 399 生效日 2025-10-31 | 200；持股日 10/30；51 檔 | 00982A 從資料窗口起點開始 |
| 5 | 21:59:49 | 500（00992A）生效日 2025-12-31 | 200；持股日 12/30；41 檔 | 00992A `since` |
| 6 | 21:59:50 | 504（00415A）生效日 2026-10-21 | 200；持股日 10/20；50 檔 | 00415A `since` |
| 7 | 22:00:05 | 502 生效日 2026-04-16 | 200；持股日 04/14；43 檔 | 00997A `since`，同時證實 delay = 1 |

- 本輪分析師加 SA 共 23 次，在 PM「≤ 10 次抽樣」之外的部分屬於分析師的端點探查。

## 附錄 B：預期值與 QA 用 SQL（全部唯讀）

### B-1. 群益 4 檔的持股日（F7-1 #1、#3）

```sql
SELECT e.etf_code, COUNT(DISTINCT h.hold_date) AS days, MIN(h.hold_date) AS first_d, MAX(h.hold_date) AS last_d
FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id
WHERE e.etf_code IN ('00982A','00992A','00415A','00997A') GROUP BY e.etf_code ORDER BY e.etf_code;
```

| etf_code | days | first_d | last_d（在 11/04 晚上補完時） |
|---|---|---|---|
| 00415A | 10 | 2026-10-20 | 2026-11-04 |
| 00982A | 245 | 2025-10-30 | 2026-11-04 |
| 00992A | 203 | 2025-12-30 | 2026-11-04 |
| 00997A | 138 | 2026-04-14 | 2026-11-03 |

- 晚於 11/04 補歷史時，`last_d` 和 `days` 會跟著增加。
- 判斷標準：`days` = `tradingcal` 在 `since`（或 2025-10-30）～`last_d` 之間的交易日數，而且 B-3 的 Gap 是 0。

### B-2. 抽查 00982A（F7-1 #2，數值來自分析師抽樣）

```sql
SELECT h.hold_date, COUNT(*) AS n, MAX(CASE WHEN h.code = '2330' THEN h.shares END) AS tsmc
FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id
WHERE e.etf_code = '00982A' AND h.hold_date IN ('2025-11-04','2026-06-01','2026-11-04') GROUP BY h.hold_date ORDER BY h.hold_date;
```

| hold_date | n | tsmc |
|---|---|---|
| 2025-11-04 | 51 | 1,082,000 |
| 2026-06-01 | 57 | 1,937,000 |
| 2026-11-04 | 57 | 1,609,000 |

### B-3. 群益欄位（D13、F7-1-5）

```sql
SELECT e.etf_code,
       SUM(CASE WHEN h.amount IS NOT NULL THEN 1 ELSE 0 END) AS has_amount,   -- 預期 0
       SUM(CASE WHEN h.currency <> '' THEN 1 ELSE 0 END)    AS has_currency, -- 預期 0
       SUM(CASE WHEN h.asset_type <> 'ST' THEN 1 ELSE 0 END) AS not_stock    -- 預期 0
FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id
WHERE e.etf_code IN ('00982A','00992A','00415A','00997A') GROUP BY e.etf_code;
SELECT COUNT(*) FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id
WHERE e.etf_code IN ('00982A','00992A','00415A','00997A');                -- 預期 0（發現 2）
SELECT e.etf_code, s.hold_date, s.post_date, s.nav, s.units, s.nav_unit, s.n_stocks, s.stock_weight, s.futures_lots, s.edited_at
FROM etf_holding_summary s JOIN etfs e ON e.etf_id = s.etf_id
WHERE e.etf_code = '00982A' AND s.hold_date = '2026-11-04';
-- 預期：post_date 2026-11-05、nav 43765013015.00、units 2292436000、nav_unit 19.0900、n_stocks 57、stock_weight 96.51、futures_lots 0、edited_at NULL
```

### B-4. 統一 4 檔不變（F7-1 #6）

```sql
SELECT e.etf_code, COUNT(*) AS n, COUNT(DISTINCT h.hold_date) AS days, SUM(h.shares) AS shares
FROM etf_holdings h JOIN etfs e ON e.etf_id = h.etf_id
WHERE e.etf_code IN ('00981A','00403A','00411A','00988A') AND h.hold_date <= '2026-11-04'
GROUP BY e.etf_code ORDER BY e.etf_code;
SELECT COUNT(*) FROM etf_holding_gaps WHERE hold_date <= '2026-11-04';   -- 預期 8（第 6 輪）
```

| etf_code | n | days | shares（SA 11/04 22:00 的唯讀查詢） |
|---|---|---|---|
| 00403A | 6,014 | 120 | 22,582,667,696 |
| 00411A | 1,420 | 43 | 59,574,766 |
| 00981A | 12,482 | 245 | 43,794,373,975 |
| 00988A | 10,609 | 234 | 2,773,343,137 |

### B-5. 彙總排行手算核對（F7-2 #2）

1. 在 `#/etf/active` 的「合計加碼」任選一列，例如 2330。記下「參與 ETF」各檔的張數增減，以及頁首各檔的持股日。
2. 對每一檔參與的 ETF，開 `site/data/etfs/{代號}.json`，找出 `rows` 中 `c = "2330"` 的 `d1`。
   - 出清的股票在 `out`，增減為 −`l`。
   - 確認 d1 與頁面相同。
3. 收盤：開 `site/data/stocks/2330.json`，在 `prices.d` 找該 ETF 的持股日，取 `prices.c`；那天沒有成交時取前一個非 null 的收盤。
4. 估算金額 = Σ(d1 × 1000 × 收盤) ÷ 1e8，四捨五入到 2 位，要等於頁面的估算金額。
5. 1 日張數 = Σ d1；5 日張數 = Σ 有 `d5` 的 ETF 的 `d5`。
6. 減碼任選一列，重複以上步驟。

## 附錄 C：原型對現有程式的完整 diff（已通過 `test_iter01`～`07`）

```diff
diff --git a/README.md b/README.md
index 8f543d5..589754b 100644
--- a/README.md
+++ b/README.md
@@ -12,12 +12,12 @@
 | 路徑 | 說明 |
 |---|---|
 | `twstock/fetch.py` | HTTP 請求：每個主機各自節流、被封鎖時退避重試 |
-| `twstock/collectors/` | `daily` 行情／本益比／法人／加權與櫃買指數、上市三大法人買賣金額、ETF 行情、融資融券、官方漲跌家數、`holdings` 主動型 ETF 持股（統一投信）、`alerts` 處置／注意股、`events` 除權息／減資／面額變更事件（還原價格用）、`revenue` 月營收、`industry` 產業別、`chains` 產業鏈族群、`futures` 期貨日 K 與法人未平倉、`history` 補抓歷史、`catchup` 缺什麼補什麼 |
+| `twstock/collectors/` | `daily` 行情／本益比／法人／加權與櫃買指數、上市三大法人買賣金額、ETF 行情、融資融券、官方漲跌家數、`holdings` 主動型 ETF 持股（統一、群益投信）、`alerts` 處置／注意股、`events` 除權息／減資／面額變更事件（還原價格用）、`revenue` 月營收、`industry` 產業別、`chains` 產業鏈族群、`futures` 期貨日 K 與法人未平倉、`history` 補抓歷史、`catchup` 缺什麼補什麼 |
 | `twstock/tradingcal.py` | 交易日曆（官方休市表、手寫表、臨時休市） |
 | `twstock/health.py` | 資料完整性判斷、`check`、執行紀錄、通知 |
 | `twstock/export.py` | 匯出 `site/data/latest.json` 與 `site/data/stocks/{代號}.json` |
 | `twstock/analysis/` | `flow` 資金流象限、`forecast` 依期貨法人未平倉的大盤漲跌預測、`chanlun` 纏論 |
-| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行、ETF（含主動型 ETF 持股頁）、自選、個股頁（含主動 ETF 持有） |
+| `site/` | 網站：今日（含加權與櫃買指數、台指期日 K、期貨法人未平倉、籌碼因子觀察、信用交易、市場寬度）、泡泡圖、排行、ETF（含主動型 ETF 持股頁、主動 ETF 彙總）、自選、個股頁（含主動 ETF 持有） |
 | `tests/` | 純邏輯測試（不連網、不連資料庫）：`python3 tests/test_iter01.py`、`python3 tests/test_iter02.py`、`python3 tests/test_iter03.py`、`python3 tests/test_iter04.py`、`python3 tests/test_iter05.py`、`python3 tests/test_iter06.py` |
 | `docs/iterations/` | 持續優化流程：每一輪分析師、PM、SA、PG、QA 的文件 |
 | `data/concepts.csv` | 自訂概念股（只需放產業鏈沒有的題材，如 CoWoS、矽光子） |
@@ -51,7 +51,7 @@ python -m twstock collect --date 2026-10-28      # 指定日期全部重抓覆
 python -m twstock check                          # 檢查近 20 個交易日各資料集的完整性（唯讀、不連外）；開頭列最後一次收集與排程狀態；有異常時印建議指令並回傳 1（--days 至少 1）
 python -m twstock history --start 2026-01-02     # 補抓歷史（行情、本益比、法人、ETF、融資融券），只補缺的，可中斷重跑
 python -m twstock history --start 2025-10-30 --only etf margin   # 只補 ETF 行情與融資融券（同一天 ETF 先於融資融券；一年約 976 個請求、40 分鐘）
-python -m twstock history --start 2025-10-30 --only holdings   # 只補主動型 ETF 持股（統一投信 4 檔；上市日之前自動略過；一年約 650 個請求、35 分鐘）
+python -m twstock history --start 2025-10-30 --only holdings   # 只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過；一年約 1,260 個請求、70 分鐘）
 python -m twstock history --start 2026-01-02 --only insti   # 只補法人
 python -m twstock history --start 2025-10-30 --only pe      # 只補本益比／淨值比／殖利率（--only prices 不再順帶寫入）
 python -m twstock history --start 2026-02-23 --only index   # 只補加權指數歷史（一天一個請求）
@@ -136,7 +136,8 @@ python -m twstock backup --direct --out D:\backups   # SQL Server 不在 Docker
 - 融資使用率 = 融資餘額 ÷ 限額（上市用「次一營業日限額」、上櫃用「資限額」），截斷到小數 2 位，限額 0 或空時顯示 `--`；券資比 = 融券餘額 ÷ 融資餘額。上市註記 O 停止融資、X 停止融券、@ 融資分配、% 融券分配、! 停止買賣，表示**次一營業日**的狀況，個股頁加註；上櫃備註存原文、不解讀。個股頁「無信用交易」表示該股不在融資融券清單，與融資 0 張不同。
 - 大盤融資維持率（**自算、非官方**）= Σ(融資張數 × 1,000 × 收盤) ÷ 官方融資金額，分子含股票與 ETF；當日無成交用最近一次收盤；有收盤的融資張數 ÷ 官方融資張數（涵蓋率）不足 99% 時顯示「資料不足」。
 - ETF：代號 `00` 開頭、4～6 碼、數字後最多一個英文字尾（例：0050、00878、006201、00406A、00679B）；ETN、受益證券、TDR、權證、特別股不算。ETF 存在獨立的資料表（`etfs`、`etf_daily`、`etf_margin`），`stocks` 表沒有任何 ETF。行情取自與股票同一個 `MI_INDEX`／`dailyQuotes` 回應，**每日不增加請求**；歷史需用 `history --only etf` 補抓。ETF 頁（`#/etf`）列出全部 ETF 的收盤、漲跌、成交量（張）、成交額（億）、融資融券餘額與增減（張），可依成交額、漲幅、跌幅、融資增減、融券增減排序並篩選上市／上櫃。**ETF 不計入**首頁家數與成交額、類股／產業鏈／概念股資金流與泡泡圖、排行、自選、搜尋、個股頁、法人估算、股票口徑的融資融券；只計入大盤融資維持率的分子。上市官方三大法人金額本來就含 ETF。
-- 主動型 ETF 持股：取自統一投信每日申購買回清單（`www.ezmoney.com.tw` 的 `GetPCF`，間隔 3 秒），支援 00981A、00403A、00411A、00988A；**00406A（中信）與其他投信尚未支援**，ETF 頁標示「持股尚未支援」。日期以**持股日**為準：國內 ETF（00981A、00403A）當天傍晚公布當天的持股；跨境 ETF（00411A、00988A）晚一個交易日（11/03 晚上公布的是 11/02 的持股）。單位：台股為張（股數 ÷ 1,000）、海外股票為股，海外與期貨只在 ETF 持股頁顯示原文。持股頁（`#/etf/代號`）列淨資產、每單位淨值、股票權重合計、持股檔數、期貨，以及每檔的持有張數、權重、1 日增減、1 日權重變化、5 日增減、「新」與出清；個股頁「主動 ETF 持有」卡列出持有該股的已支援 ETF。這 4 檔為現金申購買回，持股不會隨申購按比例增減：**張數增減就是經理人的買賣**；權重變化另含股價漲跌的影響。新增統一投信的主動 ETF：在 `twstock/health.py` 的 `HOLDINGS` 加一列（代號 → 基金代碼、delay、上市日），再執行 `history --start 上市日 --only holdings`。**海外休市日**（跨境 ETF 當天沒有持股清單，例如美國感恩節）與**臺股臨時休市前一個交易日**（投信只公布彙總、沒有明細）會記在 `etf_holding_gaps`，`check` 視為正常並另列一行，不再請求；持股頁與 1 日增減以前一個有明細的持股日為準。臨時休市前一日的明細在生效日之前都當成尚未公布，所以當晚 22:00 後可能先顯示異常，隔天收集後自動消失。
+- 主動型 ETF 持股：取自投信每日申購買回清單，間隔 3 秒：統一投信（`www.ezmoney.com.tw` 的 `GetPCF`）00981A、00403A、00411A、00988A；群益投信（`www.capitalfund.com.tw` 的 `CFWeb/api/etf/buyback`，第 7 輪）00982A、00992A、00415A、00997A。群益的明細只有股數與權重，**沒有市值**（資料庫存 NULL，不推算）。**00406A（中信）與其他投信尚未支援**，ETF 頁標示「持股尚未支援」。日期以**持股日**為準：國內 ETF（00981A、00403A、00982A、00992A、00415A）當天傍晚公布當天的持股；跨境 ETF（00411A、00988A、00997A）晚一個交易日（11/03 晚上公布的是 11/02 的持股）。單位：台股為張（股數 ÷ 1,000）、海外股票為股，海外與期貨只在 ETF 持股頁顯示原文。持股頁（`#/etf/代號`）列淨資產、每單位淨值、股票權重合計、持股檔數、期貨，以及每檔的持有張數、權重、1 日增減、1 日權重變化、5 日增減、「新」與出清；個股頁「主動 ETF 持有」卡列出持有該股的已支援 ETF。這 4 檔為現金申購買回，持股不會隨申購按比例增減：**張數增減就是經理人的買賣**；權重變化另含股價漲跌的影響。新增統一或群益投信的主動 ETF：在 `twstock/health.py` 的 `HOLDINGS` 加一列（代號 → 基金代碼、delay、上市日、投信），再執行 `history --start 上市日 --only holdings`。**海外休市日**（跨境 ETF 當天沒有持股清單，例如美國感恩節）與**臺股臨時休市前一個交易日**（投信只公布彙總、沒有明細）會記在 `etf_holding_gaps`，`check` 視為正常並另列一行，不再請求；持股頁與 1 日增減以前一個有明細的持股日為準。臨時休市前一日的明細在生效日之前都當成尚未公布，所以當晚 22:00 後可能先顯示異常，隔天收集後自動消失。
+- 主動 ETF 彙總（`#/etf/active`，今日頁另有加碼、減碼前 5 名小卡；第 7 輪）：把已支援持股的主動 ETF 最新一天的張數增減合計（只算台股），列出合計加碼、減碼各 20 名與被最多檔持有的 20 檔。**估算金額 = 各 ETF 張數增減 × 該 ETF 持股日收盤**（無成交用最近收盤），不是實際成交金額；沒有收盤的股票不列入加減碼排行。各 ETF 用自己的最新持股日（跨境 ETF 晚一個交易日）；某檔當天還沒收到持股（持股日比同類 ETF 舊）時不列入，頁首標示「未更新」。
 - 市場寬度：今日頁成交額卡的漲跌家數改用**官方**（股票）：上市取自與行情同一個 `MI_INDEX` 回應的「漲跌證券數合計」（不增加請求）、上櫃取自櫃買 `afterTrading/highlight`（每日 +1 請求），2026-11-03 起，歷史不補；沒有官方家數時退回網站自算並註明。**官方與網站自算的差別**：上市官方「股票」欄不含 TDR、另列「無比價」，網站自算把 TDR 算成股票、無比價依參考價算漲跌，2026-11-03 網站自算多 3 漲 3 跌（上櫃一致）。市場寬度卡為自算（股票，不含 ETF，還原收盤）：站上 MA20／MA60 = 收盤 > 含當天的 20／60 日均價的比例，分母 = 當天有收盤且有 20／60 個以上收盤的股票；20 日新高／新低 = 收盤高於／低於前 20 個收盤；量能 = 當天成交額 ÷ 前 20 個交易日平均。
 - 資料完整性：每個資料集分市場判斷。**齊全** = 筆數 ≥ max(下限, 近 20 日中位數 × 80%)，且本益比、淨值比、殖利率的非空比例都 ≥ 50%。狀態：**正常**；**尚未公布**（當天 22:00 前還沒有）；**異常**（22:00 後或隔日仍缺、抓取失敗、欄位不符）；**休市**（不列入）。`collect --catch-up` 回傳 0 = 正常、尚未公布、休市或另一個程序正在執行；1 = 有異常；2 = 連不上資料庫。第 4 輪新增上市／上櫃 ETF、上市／上櫃融資融券 4 個資料集。第 5 輪新增上市／上櫃漲跌家數（2026-11-03 起）與 4 檔主動 ETF 持股 6 個資料集；持股在 ETF 上市日之前不算缺；跨境 ETF（00411A、00988A）的持股日晚一個交易日，公布日 22:00 後仍沒有才算異常。`check` 開頭列最後一次收集（時間、指令、有無新資料）與排程狀態（只看 `~/Library/LaunchAgents/com.twstock.collect.plist` 是否存在，不呼叫 `launchctl`；非 Mac 顯示「無法判斷」）；同一交易日所有資料集都缺時合併成一行；有異常時最後印建議指令（缺口 10 天內 `collect --catch-up`、30 天內加 `--days N`、更早用 `history --start`）。網站橫幅在「可能尚未收集」後提示「請在收集資料的電腦執行 python3 -m twstock collect --catch-up」。第 6 輪：主動 ETF 持股遇到投信確定沒有明細的日期（見「主動型 ETF 持股」），算齊全，涵蓋數含這些日期，`check` 另列「投信沒有持股明細（不算缺）」。
 - 交易日曆：優先用證交所官方休市表（`market_holidays`，只有當年，30 天更新一次），抓不到時只印警告、不影響當次收集，沿用已存的官方表；沒有該年資料時用程式內的手寫表；都沒有時平日一律視為交易日並印警告，**每年年底請確認新年度的休市表**。
diff --git a/site/app.js b/site/app.js
index 8368c99..4922739 100644
--- a/site/app.js
+++ b/site/app.js
@@ -62,7 +62,7 @@ const routes = {
   bubble: renderBubble,
   rank: renderRank,
   watch: renderWatch,
-  etf: code => code ? renderHoldings(code) : renderEtf(),
+  etf: code => code === 'active' ? renderActive() : code ? renderHoldings(code) : renderEtf(),   // 第 7 輪：#/etf/active 彙總排行
   stock: code => window.renderStock(code),
 };
 
@@ -185,7 +185,8 @@ function renderToday() {
         <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topBuy)}</tbody></table></div></div>
       <div class="card"><div class="sec-h"><h2>法人賣超</h2><span class="muted small">${md(L.flow_date)}，億，估算，不含 ETF</span></div>
         <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>收盤</th><th>漲跌</th><th>買賣超</th></tr></thead><tbody>${rows(topSell)}</tbody></table></div></div>
-    </section>`;
+    </section>
+    ${activeCard(L.active_rank)}`;
 
   onSeg('grpSeg', v => { setGroup(v); renderToday(); });
   onSeg('spanSeg', v => { localStore('span', null, v); renderToday(); });
@@ -686,7 +687,7 @@ function renderEtf() {
   const lots = v => `<td class="num ${cls(v)}">${v == null ? '--' : sgn(v, 0)}</td>`;
   const dates = Object.entries(E.dates).map(([m, d]) => `${m === 'TWSE' ? '上市' : '上櫃'} ${md(d)}`).join('　');
   $('#view').innerHTML = `<section class="sec">
-      <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span><span class="sp"></span>
+      <div class="sec-h"><h2>ETF</h2><span class="muted small">${dates}</span>${App.latest.active_rank ? '<a class="pill hold" href="#/etf/active">主動 ETF 彙總</a>' : ''}<span class="sp"></span>
         ${segHTML('etfMktSeg', [['all', '全部'], ['TWSE', '上市'], ['TPEx', '上櫃']], mkt)}
         <select id="etfSel" class="sel" aria-label="排序">${ETF_SORT.map(x => `<option value="${x[0]}"${x[0] === by ? ' selected' : ''}>${x[1]}</option>`).join('')}</select></div>
       <div class="card"><div class="tbl-wrap"><table class="tbl"><thead><tr>
@@ -704,6 +705,45 @@ function renderEtf() {
   $('#view').addEventListener('click', e => { const tr = e.target.closest('tr[data-etf]'); if (tr) location.hash = '#/etf/' + tr.dataset.etf; });
 }
 
+// ─── F7-2：主動 ETF 彙總排行 ─────────────────────────────
+const ACT_NOTE = '估算金額 = 各 ETF 張數增減 × 該 ETF 持股日收盤，不是實際成交金額；只含台股。各 ETF 用自己的最新持股日（跨境 ETF 晚一個交易日）。';
+const actDates = R => R.etfs.map(x => `${x.c} ${md(x.d)}`).join('、') +
+  (R.stale.length ? `；未更新：${R.stale.map(x => `${x.c}（停在 ${md(x.d)}）`).join('、')}` : '');
+const actEtfs = r => r.e.map(x => `<a href="#/etf/${x.e}">${x.e}</a> ${sgn(x.d1, 0)}${x.new ? '<i class="al al-new">新</i>' : x.out ? '<i class="al">清</i>' : ''}`).join('、');
+const actRows = (list, full) => list.map(r => `<tr data-code="${r.c}"><td class="nm"><b>${esc(r.n)}</b><span>${r.c}</span></td>
+    <td class="num ${cls(r.a)}">${sgn(r.a, 2)}</td><td class="num ${cls(r.l1)}">${sgn(r.l1, 0)}</td>` +
+  (full ? `<td class="num ${cls(r.l5)}">${r.l5 == null ? '--' : sgn(r.l5, 0)}</td><td class="small">${actEtfs(r)}</td>` : '') + '</tr>').join('');
+
+// 今日頁小卡：買超、賣超各 5 名
+function activeCard(R) {
+  if (!R || !R.etfs.length) return '';
+  const tbl = (t, list) => `<div class="card"><div class="sec-h"><h2>${t}</h2><span class="muted small">億，估算</span></div>
+    <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>估算金額</th><th>張數</th></tr></thead><tbody>${actRows(list.slice(0, 5)) ||
+    '<tr><td colspan="3" class="muted">無</td></tr>'}</tbody></table></div></div>`;
+  return `<section class="sec"><div class="sec-h"><h2>主動 ETF 一起買了什麼</h2><span class="muted small">${R.etfs.length} 檔合計</span>
+      <span class="sp"></span><a class="muted small" href="#/etf/active">完整排行 →</a></div>
+    <div class="grid g2">${tbl('主動 ETF 合計加碼', R.buy)}${tbl('主動 ETF 合計減碼', R.sell)}</div></section>`;
+}
+
+function renderActive() {
+  const R = App.latest.active_rank;
+  if (!R || !R.etfs.length) { $('#view').innerHTML = '<div class="empty">尚無主動 ETF 持股資料</div>'; return; }
+  const head = '<thead><tr><th>股票</th><th>估算金額（億）</th><th>1 日張數</th><th>5 日張數</th><th>參與 ETF（張數增減）</th></tr></thead>';
+  $('#view').innerHTML = `<section class="sec card">
+      <div class="sec-h"><h2>主動 ETF 彙總</h2><span class="muted small">${R.etfs.length} 檔</span><span class="sp"></span><a class="muted small" href="#/etf">← ETF 列表</a></div>
+      <div class="muted small">持股日：${actDates(R)}</div></section>
+    ${[['合計加碼', R.buy], ['合計減碼', R.sell]].map(([t, list]) => `<section class="sec card"><div class="sec-h"><h2>${t}</h2></div>
+      <div class="tbl-wrap"><table class="tbl">${head}<tbody>${actRows(list, true) || '<tr><td colspan="5" class="muted">無</td></tr>'}</tbody></table></div></section>`).join('')}
+    <section class="sec card"><div class="sec-h"><h2>最多檔持有</h2><span class="muted small">市值為估算（億）</span></div>
+      <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>檔數</th><th>合計張數</th><th>估算市值</th><th>各 ETF 權重</th></tr></thead><tbody>` +
+      R.held.map(r => `<tr data-code="${r.c}"><td class="nm"><b>${esc(r.n)}</b><span>${r.c}</span></td><td class="num">${r.k}</td>
+        <td class="num">${fmt(r.l)}</td><td class="num">${fmt(r.v, 1)}</td>
+        <td class="small">${r.e.map(x => `<a href="#/etf/${x.e}">${x.e}</a> ${fmt(x.w, 2)}%`).join('、')}</td></tr>`).join('') +
+      `</tbody></table></div>
+      <div class="muted small" style="margin-top:6px">${ACT_NOTE}標「新」= 前一持股日沒有持有，「清」= 最新持股日已出清。</div></section>`;
+  $('#view').addEventListener('click', e => { if (!e.target.closest('a')) onRowClick(e); });   // 列內的 ETF 連結不要被整列的個股連結蓋掉
+}
+
 // E2-4：已支援持股的主動 ETF 可點；其他主動型（代號 A 結尾）標示尚未支援
 const holdTag = c => App.latest.holdings?.[c] ? `<a class="pill hold" href="#/etf/${c}">持股</a>`
   : /A$/.test(c) ? '<span class="pill muted">持股尚未支援</span>' : '';
@@ -713,7 +753,7 @@ const HOLD_SORT = [['pw', '權重'], ['d1', '張數增減'], ['w1', '權重變
 async function renderHoldings(code) {
   // 不在支援清單就不請求（避免 404）
   const H = App.latest.holdings?.[code] && await getJSON(`data/etfs/${code}.json`);
-  if (!H) { $('#view').innerHTML = `<div class="empty">${esc(code)} 的持股資料尚未支援（目前只有統一投信 4 檔主動 ETF）</div>`; return; }
+  if (!H) { $('#view').innerHTML = `<div class="empty">${esc(code)} 的持股資料尚未支援（目前支援統一、群益投信 8 檔主動 ETF）</div>`; return; }
   const S = H.sum, by = localStore('holdSort', 'pw'), unit = r => r.tw ? '張' : '股';
   const rows = [...H.rows].sort((a, b) => (b[by] ?? -Infinity) - (a[by] ?? -Infinity));
   const prev = H.dates.at(-2), d5 = H.dates.length > 5 ? H.dates.at(-6) : null;
@@ -736,7 +776,7 @@ async function renderHoldings(code) {
         <div class="tbl-wrap"><table class="tbl"><thead><tr><th>股票</th><th>${md(prev)} 持有</th><th>權重</th></tr></thead><tbody>` +
         H.out.map(r => `<tr${r.tw ? ` data-code="${esc(r.c)}"` : ''}><td class="nm">${name(r)}</td><td class="num">${fmt(r.l)} ${unit(r)}</td><td class="num">${fmt(r.pw, 2)}%</td></tr>`).join('') +
         '</tbody></table></div>' : ''}
-      <div class="muted small" style="margin-top:6px">資料來源：統一投信每日申購買回清單。台股為張、海外為股；權重為占基金淨資產 %，權重變化為百分點。
+      <div class="muted small" style="margin-top:6px">資料來源：${esc(H.trust || '統一')}投信每日申購買回清單。台股為張、海外為股；權重為占基金淨資產 %，權重變化為百分點。
         本基金為現金申購買回，持股不會隨申購按比例增減：<b>張數增減就是經理人的買賣</b>；權重變化另含股價漲跌的影響（張數不變、權重也會變）。標「新」= 前一持股日沒有持有。</div></section>`;
   onSeg('holdSeg', v => { localStore('holdSort', null, v); renderHoldings(code); });
   $('#view').addEventListener('click', onRowClick);
diff --git a/site/stock.js b/site/stock.js
index 1994301..c5ce2ab 100644
--- a/site/stock.js
+++ b/site/stock.js
@@ -51,10 +51,10 @@ window.renderStock = async function (code) {
        ['券資比', MG.sr == null ? '--' : fmt(MG.sr, 2) + '%', '', '資料 ' + md(MG.d)],
        ['融資使用率', MG.mu == null ? '--' : fmt(MG.mu, 2) + '%', '', mgNote ? '次一營業日' + mgNote : '資料 ' + md(MG.d)]];
 
-  // E2-4：主動 ETF 持有（只含統一投信 4 檔；沒有任何一檔持有時不顯示）
+  // E2-4：主動 ETF 持有（統一、群益投信 8 檔；沒有任何一檔持有時不顯示）
   const AC = data.active;
   const acHTML = !AC ? '' : `<section class="sec card">
-      <div class="sec-h"><h2>主動 ETF 持有</h2><span class="muted small">目前只含統一投信 4 檔主動 ETF</span></div>
+      <div class="sec-h"><h2>主動 ETF 持有</h2><span class="muted small">目前只含統一、群益投信 8 檔主動 ETF</span></div>
       <div class="tbl-wrap"><table class="tbl"><thead><tr><th>ETF</th><th>張數</th><th>權重</th><th>1 日</th><th>5 日</th><th>持股日</th></tr></thead><tbody>` +
       AC.map(a => `<tr><td class="nm"><a href="#/etf/${a.e}"><b>${esc(App.latest.holdings?.[a.e]?.n || a.e)}</b><span>${a.e}</span></a>${a.new ? '<i class="al al-new">新</i>' : ''}</td>
         <td class="num">${fmt(a.l)}</td><td class="num">${fmt(a.w, 2)}%</td>
diff --git a/tests/test_iter03.py b/tests/test_iter03.py
index 2fff917..e9ce538 100644
--- a/tests/test_iter03.py
+++ b/tests/test_iter03.py
@@ -188,7 +188,8 @@ def test_dataset_status():
     assert st["prices.TWSE"] == {"k": "prices.TWSE", "n": "上市行情", "d": "2026-10-30", "s": "ok"}
     st = {x["k"]: x for x in health.dataset_status(snap, D(10, 30), T(10, 30, 19))}
     assert st["pe.TPEx"]["s"] == "pending" and "m" not in st["pe.TPEx"]             # 當天 22:00 前
-    assert len(json.dumps(health.dataset_status(snap, D(10, 30), T(11, 2, 18)), ensure_ascii=False)) < 1500
+    # 每個資料集平均 < 75 字元（第 7 輪：持股 8 檔後由固定 1500 改成依資料集數）
+    assert len(json.dumps(health.dataset_status(snap, D(10, 30), T(11, 2, 18)), ensure_ascii=False)) < 75 * len(health.SPECS)
 
 
 # ─── S5：交易日曆與臨時休市 ───────────────────────────────
@@ -358,7 +359,8 @@ INX_FIELDS = ["日期", "開市", "最高", "最低", "收市", "漲/跌"]
 FUT_HEAD = "交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,價差對單式委託成交量\r\n"
 OI_HEAD = "日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
 ALL_EP = ("MI_INDEX", "BWIBBU_d", "fund/T86", "BFI82U", "dailyQuotes", "peQryDate", "dailyTrade", "futDataDown", "futContractsDateDown",
-          "MI_MARGN", "margin/balance", "highlight", "GetPCF")     # 第 5 輪：GetPCF 的日期是持股日
+          "MI_MARGN", "margin/balance", "highlight", "GetPCF",     # 第 5 輪：GetPCF 的日期是持股日
+          "etf/buyback")                                            # 第 7 輪群益：和 GetPCF 共用已公布的持股日（down 才用得到）
 # 第 4 輪：行情回應含 ETF 列（另有權證、TDR 等其他證券，兩邊都不可寫入）；融資融券回應含股票與 ETF
 TWSE_ETFS = [f"00{n:03d}" for n in range(100, 350)]          # 250 檔，如 00100
 TPEX_ETFS = [f"00{n:03d}B" for n in range(700, 820)]         # 120 檔，如 00700B
@@ -412,7 +414,8 @@ class World:
         for key, fn in (("MI_INDEX", self._mi), ("BWIBBU_d", self._bwi), ("fund/T86", self._t86), ("BFI82U", self._bfi),
                         ("dailyQuotes", self._quotes), ("peQryDate", self._pe), ("dailyTrade", self._tpex_insti),
                         ("indexInfo/inx", self._inx), ("futDataDown", self._fut), ("futContractsDateDown", self._oi),
-                        ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn), ("highlight", self._hl), ("GetPCF", self._pcf)):
+                        ("MI_MARGN", self._mgn), ("margin/balance", self._tpex_mgn), ("highlight", self._hl), ("GetPCF", self._pcf),
+                        ("etf/buyback", self._cap)):
             if key in url:
                 return fn(form)
         return Resp([]) if "openapi" in url else Resp({"stat": "沒有資料", "tables": []})
@@ -459,6 +462,19 @@ class World:
         return Resp({"pcf": [{"PCFCode": "NAV", "TranDate": t, "PostDate": f"{post}T00:00:00", "Amount": 1e9}], "fund": {},
                      "asset": [{"AssetCode": "ST", "Details": stocks}, {"AssetCode": "GD", "Details": None}]})
 
+    def _cap(self, form):
+        """第 7 輪群益 buyback：date 是生效日（台灣 0 點的 ISO 字串）；和 GetPCF 共用「已公布的持股日」。"""
+        post = date.fromisoformat(form["date"][:10]) + timedelta(days=1)
+        delay = next(v.delay for v in health.HOLDINGS.values() if v.fund == form["fundId"])
+        hold = tradingcal.trading_days(post - timedelta(days=30), post - timedelta(days=1), CLOSED)[-1 - delay]
+        if hold not in self.published["GetPCF"]:
+            return Resp({"code": 400, "data": None, "message": "沒有查詢到該條件的數據"})
+        stocks = [{"date1": f"{post:%Y/%-m/%-d} 上午 12:00:00", "stocNo": str(c), "stocName": "名", "weight": 1.0, "share": 1000.0}
+                  for c in range(1100, 1150)]
+        return Resp({"code": 200, "message": None, "data": {
+            "pcf": {"date1": str(post), "date2": str(hold), "nav": 1e9, "totUnit": 1e8, "pUnit": 10.0},
+            "stocks": stocks, "bonds": [], "futures": [], "assets": [], "rps": [], "characteristics": []}})
+
     def _bwi(self, form):
         if self._no("BWIBBU_d", form):
             return Resp({"stat": "很抱歉，沒有符合條件的資料!"})
diff --git a/tests/test_iter05.py b/tests/test_iter05.py
index bc1db41..d87c7c1 100644
--- a/tests/test_iter05.py
+++ b/tests/test_iter05.py
@@ -155,8 +155,8 @@ def test_e2_real_file():
 # ─── E2-1：資料集（since、delay）──────────────────────────
 def test_e2_specs():
     keys = [s.key for s in health.SPECS]
-    assert keys[-6:] == ["breadth.TWSE", "breadth.TPEx", *HKEYS]
-    assert daily.DAY_KEYS[-6:] == ("breadth.TWSE", "breadth.TPEx", *HKEYS)
+    assert keys[-len(HKEYS) - 2:] == ["breadth.TWSE", "breadth.TPEx", *HKEYS]          # 第 7 輪：持股 8 檔
+    assert daily.DAY_KEYS[-len(HKEYS) - 2:] == ("breadth.TWSE", "breadth.TPEx", *HKEYS)
     assert set(daily.DAY_KEYS) | {"index.TPEX", "futures", "futures_oi"} == set(keys)
     assert daily.DATASET_KEYS["holdings"] == tuple(HKEYS) and "holdings" not in daily.ALL_DATASETS     # 只有 --only holdings 才補
     assert health.SPEC["holdings.00411A"].since == D(8, 26) and health.SPEC["holdings.00411A"].delay == 1
@@ -294,7 +294,8 @@ def test_e2_m6_before_listing():
     ok, out = _history(w, D(8, 24), D(8, 28))
     assert ok and "Traceback" not in out
     assert [_hold(f) for f in _pcf_hits(w, "64YTW")] == [D(8, 26), D(8, 27), D(8, 28)]     # 00411A 8/26 上市，之前不請求
-    assert len(_pcf_hits(w, "49YTW")) == 5 and all(D(8, 26) in w.rows[k] for k in HKEYS)
+    assert len(_pcf_hits(w, "49YTW")) == 5 and all(D(8, 26) in w.rows[k] for k in HKEYS
+                                                   if (health.SPEC[k].since or D(8, 26)) <= D(8, 26))   # 第 7 輪：00415A 10/20 上市
     ok, out = _history(w, D(8, 24), D(8, 28))
     assert ok and len(_pcf_hits(w)) == 18 and "待抓 0 天" in out             # 重跑：待抓 0 天、0 請求
 
diff --git a/twstock/__main__.py b/twstock/__main__.py
index c7641e3..4421432 100644
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -11,7 +11,7 @@
   python -m twstock history --start 2025-10-30 --only tpex_index  只補櫃買指數（一個月一個請求）
   python -m twstock history --start 2026-07-31 --only amount  只補上市三大法人買賣金額
   python -m twstock history --start 2025-10-30 --only etf margin  只補 ETF 行情與融資融券（同一天 ETF 先於融資融券）
-  python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一投信 4 檔；上市日之前自動略過）
+  python -m twstock history --start 2025-10-30 --only holdings    只補主動型 ETF 持股（統一、群益投信 8 檔；上市日之前自動略過）
   python -m twstock revenue --year 2026 --month 9    收集指定月份營收
   python -m twstock events --start 2025-10-30        補抓除權息／減資／面額變更事件（還原價格用）
   python -m twstock export                           從資料庫匯出網站 JSON（site/data）
diff --git a/twstock/collectors/holdings.py b/twstock/collectors/holdings.py
index 1a89563..3f58c2d 100644
--- a/twstock/collectors/holdings.py
+++ b/twstock/collectors/holdings.py
@@ -8,6 +8,8 @@
   A：清單已公布（PostDate = 要求的生效日），持股日卻是別天 → 這天沒有持股清單（海外休市、春節前）
   B：彙總的持股日就是這天，明細卻是空的 → 只有彙總（臺股臨時休市前一日）；公布當晚可能只是還沒寫完，到生效日才確定
 尚未公布的回應 pcf 日期都是西元 1 年、金額 0，不會落入 A、B。
+第 7 輪：群益投信 buyback（parse_capital）。日期語意相同（date1 生效日、date2 持股日）；明細只有股數與權重（沒有市值）。
+尚未公布與非交易日都回 code 400「沒有查詢到」，只請求 tradingcal 算出的生效日，所以一律當成尚未公布。
 """
 from collections import namedtuple
 from datetime import date, datetime, timedelta
@@ -18,6 +20,8 @@ from ..health import HOLDINGS
 from ..tradingcal import trading_days
 
 URL = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
+CAP_URL = "https://www.capitalfund.com.tw/CFWeb/api/etf/buyback"
+CAP_NONE = "沒有查詢到"                                   # 群益「沒有查詢到該條件的數據」：尚未公布或非交易日
 Gap = namedtuple("Gap", "reason src_date post_date nav")
 GAP_REASON = {"A": "投信當日無持股清單", "B": "投信只公布彙總、沒有明細"}
 _EPOCH = datetime(1970, 1, 1) + timedelta(hours=8)      # /Date(毫秒)/ 是 UTC，換成台灣時間
@@ -80,10 +84,48 @@ def parse_pcf(data: dict, d: date, post: date = None, today: date = None):
     return summary, rows
 
 
+def cap_date(post: date) -> str:
+    """群益的日期參數：官網送的是 JavaScript Date（台灣時間 0 點）的 ISO 字串，生效日 6/2 → '2026-06-01T16:00:00.000Z'。"""
+    return f"{post - timedelta(days=1)}T16:00:00.000Z"
+
+
+def parse_capital(data: dict, d: date, post: date, today: date = None):
+    """
+    群益 buyback 回應 → 與 parse_pcf 相同的 (彙總, 明細列)／None／Gap。
+    code 400 且訊息是「沒有查詢到」→ None（尚未公布）；其他 code、缺欄位、有期貨部位（欄位尚未對應）→ SchemaError。
+    明細沒有市值：amount 為 None、currency 為空字串；權重四捨五入到 2 位（資料表 DECIMAL(7,2)）。
+    """
+    if not isinstance(data, dict) or "code" not in data:
+        raise SchemaError("群益 buyback 回應缺少 code")
+    if data["code"] == 400 and CAP_NONE in (data.get("message") or ""):
+        return None
+    D = data.get("data")
+    if data["code"] != 200 or not isinstance(D, dict) or not {"pcf", "stocks"} <= D.keys() or not D["pcf"]:
+        raise SchemaError(f"群益 buyback 回應 code {data['code']}：{data.get('message')}")
+    p = D["pcf"]
+    hold, eff = date.fromisoformat(p["date2"][:10]), date.fromisoformat(p["date1"][:10])
+    if hold != d:
+        return Gap("A", hold, post, None) if eff == post else None
+    if not D["stocks"]:
+        if eff == post and today and today >= post and p["nav"]:
+            return Gap("B", d, post, p["nav"])
+        return None
+    if D.get("futures"):
+        raise SchemaError("群益 buyback 有期貨部位，欄位尚未對應")
+    rows = [{"asset_type": "ST", "code": str(s["stocNo"]).strip(), "month": "", "name": str(s["stocName"]).strip(),
+             "shares": int(s["share"]), "amount": None, "weight": round(s["weight"], 2), "currency": ""} for s in D["stocks"]]
+    summary = {"hold_date": d.isoformat(), "post_date": eff.isoformat(), "nav": p["nav"], "units": int(p["totUnit"]),
+               "nav_unit": p["pUnit"], "n_stocks": len(rows), "stock_weight": round(sum(s["weight"] for s in D["stocks"]), 2),
+               "futures_lots": 0, "futures_amount": 0, "edited_at": None}
+    return summary, rows
+
+
 def fetch_holdings(code: str, d: date, closed):
-    fund, delay, _ = HOLDINGS[code]
-    post = post_date(d, delay, closed)
-    data = request("POST", URL, json={"fundCode": fund, "date": f"{post.year - 1911}/{post:%m/%d}", "specificDate": True})
+    f = HOLDINGS[code]
+    post = post_date(d, f.delay, closed)
+    if f.trust == "群益":
+        return parse_capital(request("POST", CAP_URL, json={"fundId": f.fund, "date": cap_date(post)}), d, post, date.today())
+    data = request("POST", URL, json={"fundCode": f.fund, "date": f"{post.year - 1911}/{post:%m/%d}", "specificDate": True})
     return parse_pcf(data, d, post, date.today())
 
 
diff --git a/twstock/export.py b/twstock/export.py
index 566c7a3..859a156 100644
--- a/twstock/export.py
+++ b/twstock/export.py
@@ -37,6 +37,7 @@ CAP_DAYS = 90
 MARGIN_DAYS = 20               # 首頁上市股票融資增減迷你柱天數
 COVER_MIN = 99.0               # 維持率分子涵蓋的融資張數 ÷ 官方融資張數（%）低於此值不顯示
 HOLD_DAYS = 60                 # ETF 持股 JSON 的持股日數
+ACTIVE_TOP = 20                # 主動 ETF 彙總排行（第 7 輪 F7-2）各區塊的列數
 BREADTH_DAYS = 60              # 市場寬度走勢天數
 _TICKS = ((Decimal(10), Decimal("0.01")), (Decimal(50), Decimal("0.05")), (Decimal(100), Decimal("0.1")),
           (Decimal(500), Decimal("0.5")), (Decimal(1000), Decimal(1)), (Decimal("Infinity"), Decimal(5)))
@@ -393,8 +394,8 @@ def holding_export(code, dates, summary, held, tw, name, market):
     """etfs/{代號}.json。金額單位：億元；nu 每單位淨值（元）；sw 股票權重合計（%）；fl 期貨口數。"""
     nav, nu, n, sw, fl, fa = summary[dates[-1]]
     rows, out = holding_table(dates, held, tw)
-    fund, delay, _ = HOLDINGS[code]
-    return {"code": code, "n": name, "m": market, "fund": fund, "delay": delay, "dates": [str(d) for d in dates],
+    f = HOLDINGS[code]
+    return {"code": code, "n": name, "m": market, "fund": f.fund, "delay": f.delay, "trust": f.trust, "dates": [str(d) for d in dates],
             "sum": {"d": str(dates[-1]), "nav": _f(float(nav) / YI), "nu": _f(nu), "n": n, "sw": _f(sw),
                     "fl": fl, "fa": _f(float(fa) / YI)},
             "rows": rows, "out": out}
@@ -411,6 +412,61 @@ def stock_active(holdings, tw):
     return out
 
 
+def active_rank(holdings, tw, close):
+    """
+    latest.json 的 active_rank（第 7 輪 F7-2）：已收持股的主動 ETF 合計，只算台股。
+    每檔用自己的最新持股日；同一 delay 的 ETF 中最新持股日落後的（當天還沒收到）不列入，放進 stale。
+    張數與 holding_table 相同（股 ÷ 1000 四捨五入）；估算金額 a、市值 v（億）= 張 × 1000 × 該 ETF 持股日收盤
+    （無成交用最近收盤，close 回傳 None 的股票不進買賣超排行）。只有一個持股日的 ETF 只計入 held。
+    回傳 {etfs, stale: [{c, t, d}], buy, sell: [{c, n, a, l1, l5, e: [{e, d1, new|out}]}], held: [{c, n, k, l, v, e: [{e, w}]}]}。
+    """
+    newest = {}
+    for code, (dates, _, _) in holdings.items():
+        k = HOLDINGS[code].delay
+        newest[k] = max(newest.get(k, dates[-1]), dates[-1])
+    etfs, stale, names = [], [], {}
+    flow = defaultdict(lambda: {"a": 0.0, "l1": 0, "l5": None, "e": [], "px": True})
+    held_by = defaultdict(lambda: {"k": 0, "l": 0, "v": 0.0, "e": []})
+    for code, (dates, _, held) in sorted(holdings.items()):
+        last = dates[-1]
+        info = {"c": code, "t": HOLDINGS[code].trust, "d": str(last)}
+        if last != newest[HOLDINGS[code].delay]:
+            stale.append(info)
+            continue
+        etfs.append(info)
+        prev, d5 = dates[-2] if len(dates) > 1 else None, dates[-6] if len(dates) > 5 else None
+        lots = lambda c, d: round(held[d][("ST", c)][1] / 1000) if d and ("ST", c) in held[d] else 0
+        codes = {c for d in (last, prev) if d for (kind, c) in held[d] if kind == "ST" and c in tw}
+        for c in codes:
+            names.setdefault(c, (held[last].get(("ST", c)) or held[prev][("ST", c)])[0])
+            now, px = lots(c, last), close(c, last)
+            if now:
+                h = held_by[c]
+                h["k"] += 1
+                h["l"] += now
+                h["v"] += now * 1000 * px / YI if px else 0
+                h["e"].append({"e": code, "w": _f(held[last][("ST", c)][2])})
+            if not prev or now == lots(c, prev):
+                continue
+            before, f = lots(c, prev), flow[c]
+            d1 = now - before
+            f["l1"] += d1
+            if px:
+                f["a"] += d1 * 1000 * px / YI
+            else:
+                f["px"] = False
+            if d5:
+                f["l5"] = (f["l5"] or 0) + now - lots(c, d5)
+            f["e"].append({"e": code, "d1": d1, **({"new": 1} if not before else {"out": 1} if not now else {})})
+    out = lambda c, f: {"c": c, "n": names[c], "a": _f(f["a"]), "l1": f["l1"], "l5": f["l5"], "e": f["e"]}
+    ok = [(c, f) for c, f in flow.items() if f["px"]]          # 排序、過濾用未四捨五入的金額（小額加減碼不會變成 0 而消失）
+    buy = [out(c, f) for c, f in sorted((x for x in ok if x[1]["a"] > 0), key=lambda x: (-x[1]["a"], x[0]))]
+    sell = [out(c, f) for c, f in sorted((x for x in ok if x[1]["a"] < 0), key=lambda x: (x[1]["a"], x[0]))]
+    held_rows = [{"c": c, "n": names[c], "k": h["k"], "l": h["l"], "v": _f(h["v"]), "e": h["e"]} for c, h in held_by.items()]
+    held_rows.sort(key=lambda r: (-r["k"], -r["v"], r["c"]))
+    return {"etfs": etfs, "stale": stale, "buy": buy[:ACTIVE_TOP], "sell": sell[:ACTIVE_TOP], "held": held_rows[:ACTIVE_TOP]}
+
+
 def breadth_calc(series, days, turnover):
     """
     自算市場寬度。series：{市場: [每檔股票 {日期: 還原收盤}]}（只含股票）；days：交易日（舊到新，最後 BREADTH_DAYS 天輸出）；
@@ -769,6 +825,7 @@ def export_all() -> float:
         "margin": margin,
         "etfs": etf_block(etf_latest, etf_margin_rows),
         "holdings": {code: {"d": str(hd[-1]), "n": etf_names[code][0]} for code, (hd, _, _) in holdings.items()},
+        "active_rank": active_rank(holdings, tw, lambda c, d: close(c, d, False)) if holdings else None,   # 第 7 輪 F7-2
         # o：官方家數（資料日當天沒有為 null）；其餘為自算
         "breadth": {m: {"o": official_breadth.get(m), **b} for m, b in breadth_calc(b_series, b_days, b_turnover).items()},
         "groups": {
diff --git a/twstock/fetch.py b/twstock/fetch.py
index 6c9d706..31a4051 100644
--- a/twstock/fetch.py
+++ b/twstock/fetch.py
@@ -70,6 +70,7 @@ MIN_INTERVAL = {
     "www.taifex.com.tw":   3.0,
     "ic.tpex.org.tw":      2.0,
     "www.ezmoney.com.tw":  3.0,   # 統一投信（主動型 ETF 持股）
+    "www.capitalfund.com.tw": 3.0,  # 群益投信（主動型 ETF 持股，第 7 輪）
 }
 DEFAULT_INTERVAL = 3.0
 RETRY_BACKOFF = (30, 60, 120)   # 失敗後依序等待秒數，用完仍失敗就放棄
diff --git a/twstock/health.py b/twstock/health.py
index ea9832e..8f26816 100644
--- a/twstock/health.py
+++ b/twstock/health.py
@@ -24,13 +24,16 @@ OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"
 
 Row = namedtuple("Row", "n pe pb dy gap", defaults=(0, 0, 0, 0, None))     # gap：投信確定沒有明細（A／B），算齊全
 Spec = namedtuple("Spec", "key label min_rows fills since delay", defaults=(None, 0))
+Fund = namedtuple("Fund", "fund delay since trust")
 Item = namedtuple("Item", "key label date status n reason")
 FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))
 
-# 統一投信主動型 ETF（第 5 輪）：代號 → (基金代碼, 持股公布落後的交易日數, 上市日)
+# 主動型 ETF 持股（第 5 輪統一、第 7 輪群益）：代號 → Fund(投信的基金代碼, 持股公布落後的交易日數, 上市日, 投信)
 # 上市日 = etf_daily 最早一筆（2025-10-30 之前上市的填 None）；跨境 ETF 的持股日是前一個交易日
-HOLDINGS = {"00981A": ("49YTW", 0, None), "00403A": ("63YTW", 0, date(2026, 5, 12)),
-            "00411A": ("64YTW", 1, date(2026, 8, 26)), "00988A": ("61YTW", 1, date(2025, 11, 5))}
+HOLDINGS = {"00981A": Fund("49YTW", 0, None, "統一"), "00403A": Fund("63YTW", 0, date(2026, 5, 12), "統一"),
+            "00411A": Fund("64YTW", 1, date(2026, 8, 26), "統一"), "00988A": Fund("61YTW", 1, date(2025, 11, 5), "統一"),
+            "00982A": Fund("399", 0, None, "群益"), "00992A": Fund("500", 0, date(2025, 12, 30), "群益"),
+            "00415A": Fund("504", 0, date(2026, 10, 20), "群益"), "00997A": Fund("502", 1, date(2026, 4, 14), "群益")}
 BREADTH_FROM = date(2026, 11, 3)        # 官方漲跌家數不補歷史，從這天開始收集
 
 SPECS = (
@@ -43,7 +46,7 @@ SPECS = (
     Spec("etf.TWSE", "上市ETF", 150, False), Spec("etf.TPEx", "上櫃ETF", 80, False),
     Spec("margin.TWSE", "上市融資融券", 800, False), Spec("margin.TPEx", "上櫃融資融券", 550, False),
     Spec("breadth.TWSE", "上市漲跌家數", 1, False, BREADTH_FROM), Spec("breadth.TPEx", "上櫃漲跌家數", 1, False, BREADTH_FROM),
-) + tuple(Spec(f"holdings.{c}", f"{c}持股", 1, False, since, delay) for c, (_, delay, since) in HOLDINGS.items())
+) + tuple(Spec(f"holdings.{c}", f"{c}持股", 1, False, f.since, f.delay) for c, f in HOLDINGS.items())
 SPEC = {s.key: s for s in SPECS}
 
 _MARKET_SQL = {
```

## 附錄 D：`tests/test_iter07.py`（完整）

```python
"""
第 07 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程）：
F7-1 群益投信主動 ETF 持股（解析、日期參數、分派、收集流程、history）；F7-2 主動 ETF 彙總排行（export.active_rank）。
假的官方網站與資料庫沿用 test_iter03 的 World（第 7 輪在 World 加了群益 buyback：和 GetPCF 共用已公布的持股日）。

  python3 tests/test_iter07.py      （也相容 pytest）
"""
import copy
import sys
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
import test_iter05 as t5  # noqa: E402
from twstock import export, fetch, health  # noqa: E402
from twstock.collectors import holdings  # noqa: E402
from twstock.collectors.holdings import Gap  # noqa: E402
from twstock.fetch import SchemaError  # noqa: E402

D, T, World, run_world = t3.D, t3.T, t3.World, t3.run_world
CAP = ("00982A", "00992A", "00415A", "00997A")

# ─── 實際回應的片段（2026-11-04 分析師／SA 經 fetch.request(isolated=True) 取得，只刪減列數與 pcf 欄位、未改值）────
CAP_1104 = {"code": 200, "data": {"pcf": {"fundName": "群益台灣精選強棒主動式ETF基金", "date1": "2026-11-05", "date2": "2026-11-04", "nav": 43765013015.0, "totUnit": 2292436000.0, "pUnit": 19.09, "dollar": "TWD"}, "stocks": [{"date1": "2026/11/5 上午 12:00:00", "stocNo": "2330", "stocName": "台積電", "weight": 8.3087, "weightRound": 8.31, "share": 1609000.0, "shareFormat": "1,609,000", "stocEname": "TSMC", "replace": None, "smallStatus": None}, {"date1": "2026/11/5 上午 12:00:00", "stocNo": "3105", "stocName": "穩懋", "weight": 8.0807, "weightRound": 8.08, "share": 7059000.0, "shareFormat": "7,059,000", "stocEname": "Win", "replace": None, "smallStatus": None}], "bonds": [], "futures": [], "assets": [{"asDesc": "保證金", "asMoney": "TWD 33,240.00", "asEname": "Margin"}], "rps": [], "characteristics": []}, "message": None}   # 00982A 最新
CAP_997 = {"code": 200, "data": {"pcf": {"fundName": "群益美國增長主動式ETF基金", "date1": "2026-11-05", "date2": "2026-11-03", "nav": 10315579609.0, "totUnit": 1040877000.0, "pUnit": 9.91, "dollar": "TWD"}, "stocks": [{"date1": "2026/11/5 上午 12:00:00", "stocNo": "CRWD US", "stocName": "Crowdstrike控股公司", "weight": 4.9507, "weightRound": 4.95, "share": 63557.0, "shareFormat": "63,557", "stocEname": "CROWDSTRIKE HOLDINGS INC - A", "replace": None, "smallStatus": None}, {"date1": "2026/11/5 上午 12:00:00", "stocNo": "AAPL US", "stocName": "蘋果公司", "weight": 4.4136, "weightRound": 4.41, "share": 41772.0, "shareFormat": "41,772", "stocEname": "APPLE INC", "replace": None, "smallStatus": None}], "bonds": [], "futures": [], "assets": [{"asDesc": "應收付證券款", "asMoney": "KRW 5,083,081,867.00", "asEname": "Accounts Receivables\\Accounts Payables"}], "rps": [], "characteristics": []}, "message": None}   # 00997A 最新（跨境：生效日 11/05 → 持股日 11/03）
CAP_NONE = {"code": 400, "data": None, "message": "沒有查詢到該條件的數據"}   # 生效日 11/06（尚未公布）與 11/01（週日）都是這樣


# ─── F7-1：解析 ─────────────────────────────────────────
def test_f71_parse_published():
    s, rows = holdings.parse_capital(CAP_1104, D(11, 4), D(11, 5), D(11, 4))
    assert s == {"hold_date": "2026-11-04", "post_date": "2026-11-05", "nav": 43765013015.0, "units": 2292436000,
                 "nav_unit": 19.09, "n_stocks": 2, "stock_weight": 16.39, "futures_lots": 0, "futures_amount": 0, "edited_at": None}
    assert rows[0] == {"asset_type": "ST", "code": "2330", "month": "", "name": "台積電", "shares": 1609000, "amount": None,
                       "weight": 8.31, "currency": ""}                                  # D13 = A：沒有市值、不推算
    s, rows = holdings.parse_capital(CAP_997, D(11, 3), D(11, 5))                     # 跨境 delay 1
    assert s["hold_date"] == "2026-11-03" and rows[0]["code"] == "CRWD US" and rows[0]["shares"] == 63557


def test_f71_parse_unpublished_and_schema():
    assert holdings.parse_capital(CAP_NONE, D(11, 5), D(11, 6), D(11, 4)) is None
    for bad in ({"code": 400, "data": None, "message": "參數錯誤"}, {"code": 500, "data": None, "message": None},
                {"stat": "沒有資料"}, {"code": 200, "data": None, "message": None}, {"code": 200, "data": {"pcf": None, "stocks": []}},
                "<html>"):
        try:
            holdings.parse_capital(bad, D(11, 4), D(11, 5), D(11, 5))
            raise AssertionError(bad)
        except SchemaError:
            pass
    futures = copy.deepcopy(CAP_1104)
    futures["data"]["futures"] = [{"x": 1}]                                            # 期貨欄位尚未對應：不悄悄漏掉
    try:
        holdings.parse_capital(futures, D(11, 4), D(11, 5))
        raise AssertionError("futures")
    except SchemaError as e:
        assert "期貨" in str(e)


def test_f71_parse_gaps():
    # A：清單已公布（date1 = 要求的生效日），持股日卻不是 d
    assert holdings.parse_capital(CAP_997, D(11, 4), D(11, 5), D(11, 5)) == Gap("A", D(11, 3), D(11, 5), None)
    assert holdings.parse_capital(CAP_997, D(11, 4), D(11, 6), D(11, 6)) is None          # 生效日不同 → 不是這份清單
    # B：持股日是 d、只有彙總；今天 < 生效日時可能只是還沒寫完 → 仍是尚未公布
    only_sum = copy.deepcopy(CAP_1104)
    only_sum["data"]["stocks"] = []
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 5)) == Gap("B", D(11, 4), D(11, 5), 43765013015.0)
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 4)) is None
    only_sum["data"]["pcf"]["nav"] = 0
    assert holdings.parse_capital(only_sum, D(11, 4), D(11, 5), D(11, 5)) is None


def test_f71_date_and_dispatch():
    assert holdings.cap_date(D(6, 2)) == "2026-06-01T16:00:00.000Z" and holdings.cap_date(date(2026, 1, 1)) == "2025-12-31T16:00:00.000Z"
    with mock.patch.object(holdings, "request", return_value=CAP_1104) as req:
        s, _ = holdings.fetch_holdings("00982A", D(11, 4), t3.CLOSED)
    assert req.call_args == mock.call("POST", holdings.CAP_URL, json={"fundId": "399", "date": "2026-11-04T16:00:00.000Z"})
    assert s["n_stocks"] == 2
    with mock.patch.object(holdings, "request", return_value=CAP_997) as req:
        holdings.fetch_holdings("00997A", D(11, 3), t3.CLOSED)                        # 跨境：持股日 11/03 → 生效日 11/05
    assert req.call_args[1]["json"] == {"fundId": "502", "date": "2026-11-04T16:00:00.000Z"}
    with mock.patch.object(holdings, "request", return_value=t5.PCF_1103) as req:
        holdings.fetch_holdings("00981A", D(11, 3), t3.CLOSED)                        # 統一不變
    assert req.call_args == mock.call("POST", holdings.URL, json={"fundCode": "49YTW", "date": "115/11/04", "specificDate": True})


def test_f71_config():
    H = health.HOLDINGS
    assert list(H)[:4] == ["00981A", "00403A", "00411A", "00988A"] and all(H[c].trust == "統一" for c in list(H)[:4])
    assert {c: (H[c].fund, H[c].delay, H[c].since, H[c].trust) for c in CAP} == {
        "00982A": ("399", 0, None, "群益"), "00992A": ("500", 0, D(12, 30).replace(year=2025), "群益"),
        "00415A": ("504", 0, D(10, 20), "群益"), "00997A": ("502", 1, D(4, 14), "群益")}
    assert health.SPEC["holdings.00997A"].delay == 1 and health.SPEC["holdings.00415A"].since == D(10, 20)
    assert fetch.MIN_INTERVAL["www.capitalfund.com.tw"] == 3.0


# ─── F7-1：收集流程（假的 HTTP 與資料庫）─────────────────
def _cap_hits(w, fund=None):
    return [f for p, f in w.requests if "etf/buyback" in p and (fund is None or f["fundId"] == fund)]


def _world_1104():
    w = World(D(11, 3))
    for c, f in health.HOLDINGS.items():
        if f.delay:
            del w.rows[f"holdings.{c}"][D(11, 3)]            # 跨境：11/03 的持股要 11/04 才公布
    w.published["GetPCF"].add(D(11, 3))
    return w


def test_f71_collect_published():
    w = _world_1104()
    w.publish(D(11, 4))
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "Traceback" not in out and len(_cap_hits(w)) == 4
    assert {(f["fundId"], f["date"]) for f in _cap_hits(w)} == {
        ("399", "2026-11-04T16:00:00.000Z"), ("500", "2026-11-04T16:00:00.000Z"), ("504", "2026-11-04T16:00:00.000Z"),
        ("502", "2026-11-04T16:00:00.000Z")}                                          # 00997A：持股日 11/03 → 生效日 11/05
    assert all(w.rows[f"holdings.{c}"][D(11, 4)].n == 50 for c in ("00982A", "00992A", "00415A"))
    assert w.rows["holdings.00997A"][D(11, 3)].n == 50 and D(11, 4) not in w.rows["holdings.00997A"]
    assert w.rows["holdings.00981A"][D(11, 4)].n == 50 and len(t5._pcf_hits(w)) == 4   # 統一照常
    rc, out = run_world(w, T(11, 4, 19, 30))
    assert rc == 0 and len(_cap_hits(w)) == 4                                         # 重跑：不再請求


def test_f71_collect_unpublished():
    w = _world_1104()
    w.publish(D(11, 4), "GetPCF")                                                     # 兩家投信都還沒公布 11/04
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00982A持股：2026-11-04 尚未公布" in out and "Traceback" not in out
    rc, out = run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00982A持股：缺 2026-11-04" in out


def test_f71_collect_errors_only_that_source():
    w = _world_1104()
    w.publish(D(11, 4))
    w.down.add("etf/buyback")                                                         # 群益主機失敗
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "Traceback" not in out and "holdings.00982A 失敗" in out
    assert w.rows["holdings.00981A"][D(11, 4)].n == 50 and w.rows["prices.TWSE"][D(11, 4)].n == 1100
    w = _world_1104()
    w.publish(D(11, 4))
    orig = w._cap
    w._cap = lambda form: t3.Resp({"code": 500, "data": None, "message": "錯誤"}) if form["fundId"] == "399" else orig(form)
    rc, out = run_world(w, T(11, 4, 17, 30))
    assert rc == 1 and "holdings.00982A 失敗：群益 buyback 回應 code 500" in out and w.rows["holdings.00992A"][D(11, 4)].n == 50


def test_f71_history_since_and_rerun():
    w = World(D(10, 16))
    w.published["GetPCF"].update(t3.tradingcal.trading_days(D(10, 19), D(10, 30), t3.CLOSED))
    ok, out = t5._history(w, D(10, 19), D(10, 22))
    assert ok and "Traceback" not in out
    hold = lambda f: date.fromisoformat(f["date"][:10])
    assert [hold(f) for f in _cap_hits(w, "504")] == [D(10, 20), D(10, 21), D(10, 26)]   # 00415A 10/20 上市；10/22 → 生效日 10/27（10/23 颱風）
    assert all(D(10, 22) in w.rows[f"holdings.{c}"] for c in ("00982A", "00992A", "00415A"))
    n = len(_cap_hits(w))
    ok, out = t5._history(w, D(10, 19), D(10, 22))
    assert ok and len(_cap_hits(w)) == n and "待抓 0 天" in out


def test_f71_export_trust():
    summary = {t5.DATES[-1]: (43765013015, 19.09, 2, 16.39, 0, 0)}
    H = export.holding_export("00982A", t5.DATES, summary, t5.HELD, t5.TW, "主動群益台灣強棒", "TWSE")
    assert H["trust"] == "群益" and H["fund"] == "399" and H["sum"]["fa"] == 0.0
    assert export.holding_export("00981A", t5.DATES, summary, t5.HELD, t5.TW, "x", "TWSE")["trust"] == "統一"


# ─── F7-2：彙總排行 ─────────────────────────────────────
def _etf(dates, table):
    """table：{代號: [各持股日的股數（None = 未持有）]}，名稱 = 代號 + '名'、權重 = 1.5。"""
    held = {d: {("ST", c): (c + "名", s[i], 1.5) for c, s in table.items() if s[i] is not None} for i, d in enumerate(dates)}
    return dates, {}, held


DAYS = t3.tradingcal.trading_days(D(10, 27), D(11, 4), t3.CLOSED)                     # 10/27～11/04 共 7 天
TWC = {"2330", "2454", "1101"}
PX = {"2330": 1000.0, "2454": 1500.0}                                                # 1101 沒有收盤


def _holdings():
    d6 = DAYS[-6:]
    return {
        "00981A": _etf(d6, {"2330": [1_000_000] * 5 + [1_200_000], "2454": [500_000] * 5 + [None],
                            "1101": [None] * 5 + [300_000], "BE US": [10_000] * 6}),
        "00982A": _etf(DAYS[-2:], {"2330": [2_000_000, 1_900_000], "2454": [400_000, 400_000]}),
        "00988A": _etf(DAYS[-3:-1], {"2330": [None, 50_000]}),                           # 跨境：持股日 11/03
        "00403A": _etf(DAYS[-3:-1], {"2330": [1_000, 999_000]}),                           # 國內但停在 11/03 → 未更新
        "00415A": _etf(DAYS[-1:], {"2330": [100_000]}),                                    # 只有一天：只計入最多檔持有
    }


def test_f72_rank():
    R = export.active_rank(_holdings(), TWC, lambda c, d: PX.get(c))
    assert R["etfs"] == [{"c": "00415A", "t": "群益", "d": "2026-11-04"}, {"c": "00981A", "t": "統一", "d": "2026-11-04"},
                         {"c": "00982A", "t": "群益", "d": "2026-11-04"}, {"c": "00988A", "t": "統一", "d": "2026-11-03"}]
    assert R["stale"] == [{"c": "00403A", "t": "統一", "d": "2026-11-03"}]
    # 2330：+200（00981A）−100（00982A）+50（00988A 新進）＝ +150 張 × 1000 元 → 1.5 億；5 日只有 00981A 有 → +200
    assert R["buy"] == [{"c": "2330", "n": "2330名", "a": 1.5, "l1": 150, "l5": 200, "e": [
        {"e": "00981A", "d1": 200}, {"e": "00982A", "d1": -100}, {"e": "00988A", "d1": 50, "new": 1}]}]
    # 2454：00981A 出清 500 張 × 1500 元 → −7.5 億；00982A 不變不列；1101 沒有收盤不進排行
    assert R["sell"] == [{"c": "2454", "n": "2454名", "a": -7.5, "l1": -500, "l5": -500, "e": [{"e": "00981A", "d1": -500, "out": 1}]}]
    assert [(r["c"], r["k"], r["l"], r["v"]) for r in R["held"]] == [("2330", 4, 3250, 32.5), ("2454", 1, 400, 6.0), ("1101", 1, 300, 0.0)]
    assert R["held"][0]["e"] == [{"e": "00415A", "w": 1.5}, {"e": "00981A", "w": 1.5}, {"e": "00982A", "w": 1.5}, {"e": "00988A", "w": 1.5}]


def test_f72_edges():
    one = {"00981A": _holdings()["00981A"]}                                            # 只有 1 檔也能顯示
    R = export.active_rank(one, TWC, lambda c, d: PX.get(c))
    assert [r["c"] for r in R["buy"]] == ["2330"] and [r["c"] for r in R["sell"]] == ["2454"] and R["stale"] == []
    many = {"00981A": _etf(DAYS[-2:], {str(1000 + i): [None, 1000 * (i + 1)] for i in range(30)})}
    R = export.active_rank(many, {str(1000 + i) for i in range(30)}, lambda c, d: 10.0)
    assert len(R["buy"]) == export.ACTIVE_TOP == 20 and R["buy"][0]["c"] == "1029" and R["sell"] == []
    assert all(r["e"][0].get("new") == 1 for r in R["buy"])


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

## 附錄 E：PG 用 `logs/` 小工具

### E-1. `logs/iter07_compare.py`（隔離比對，取代 `iter06_compare.py`）

```python
# 用法：python3 logs/iter07_compare.py 基線資料夾 site/data —— 隔離比對（第 7 輪，取代 iter06_compare.py）
# 除了 NEW_* 列的新增鍵與「時間」欄位（匯出時間、收集時間、更新於）以外必須完全相同；比對 latest.json、stocks/*.json、etfs/*.json。
# 相同印「✅ 相同」rc=0；不同列出鍵名或檔名 rc=1。
import json, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
NEW_LATEST, NEW_STOCK, NEW_ETF = {"active_rank"}, set(), {"trust"}          # 第 7 輪 F7-2、F7-1 的新增鍵
NEW_STATUS = {"holdings.00982A", "holdings.00992A", "holdings.00415A", "holdings.00997A"}   # 第 7 輪新資料集
TIME_LATEST, TIME_STATUS = {"updated_at"}, {"exported_at", "collected_at"}
bad = []


def cmp_latest(A, B):
    if set(A) ^ (set(B) - NEW_LATEST):
        bad.append(f"latest.json 鍵不同：{sorted(set(A) ^ (set(B) - NEW_LATEST))}")
    for k in set(A) & set(B):
        if k in TIME_LATEST:
            continue
        if k == "status":
            sa = {x: v for x, v in A[k].items() if x not in TIME_STATUS}
            sb = {x: v for x, v in B[k].items() if x not in TIME_STATUS}
            if sb.get("datasets") is not None:
                sb["datasets"] = [x for x in sb["datasets"] if x["k"] not in NEW_STATUS]
            for x in set(sa) | set(sb):
                if sa.get(x) != sb.get(x):
                    bad.append(f"latest.json status.{x}")
        elif A[k] != B[k]:
            bad.append(f"latest.json {k}")


cmp_latest(json.loads((a / "latest.json").read_text()), json.loads((b / "latest.json").read_text()))
n = {}
for sub, new in (("stocks", NEW_STOCK), ("etfs", NEW_ETF)):
    fa = {f.name for f in (a / sub).glob("*.json")}
    fb = {f.name for f in (b / sub).glob("*.json")}
    if fa != fb:
        bad.append(f"{sub} 檔案不同：少 {sorted(fa - fb)[:5]} 多 {sorted(fb - fa)[:5]}")
    for f in sorted(fa & fb):
        x, y = json.loads((a / sub / f).read_text()), json.loads((b / sub / f).read_text())
        if {k: v for k, v in y.items() if k not in new} != x:
            bad.append(f"{sub}/{f}")
    n[sub] = len(fa)
print(f"比對 latest.json、stocks {n['stocks']} 檔、etfs {n['etfs']} 檔（略過 {sorted(TIME_LATEST)}、status.{sorted(TIME_STATUS)}）")
if bad:
    print(f"❌ 不同 {len(bad)} 處：" + "、".join(bad[:20]))
    sys.exit(1)
print("✅ 相同")
```
