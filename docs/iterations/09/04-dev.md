# 第 09 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-05（週四）深夜
- 依據：
  - `03-design.md`：主要依據。第三節是實作順序，附錄 C～E 是程式差異，附錄 F 是 `test_iter09.py`，附錄 G、H 是 compare 與 recalc 工具。
  - `02-pm.md`：範圍與驗收。範圍變更紀錄最後幾筆：D15 = B、D16 = B（QA-05 併入 F9-1），並接受 SA 的 12 點調整。
- 本輪項目：F9-1（上櫃官方三大法人金額）＋QA-05、F9-2（月營收提前收集）、F9-3（第 8 輪收尾小修）、F9-4（估值一年位置），全部完成。
  - SA 建議一併做的三項（選股 `pbp`、今日頁 60 日迷你圖、上櫃外資 20 日迷你圖）**都有做**，沒有用到 PM 的延後順序。
- 程式來源：
  - 附錄 C、D、E 用程式從 `03-design.md` 取出，以 `patch -p1` 套用，全部乾淨套上，沒有衝突。
  - 附錄 F、G、H 用程式取出成 `tests/test_iter09.py`、`logs/iter09_compare.py`、`logs/iter09_recalc.py`，內容和設計相同。
  - 和設計不同的只有第三節列的 1 處前端文字，以及 README、`__main__.py` 的說明文字。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，也沒有讀出或印出帳密。沒有動 `_archive/`。
  - 只執行允許的寫入：`backup`、`setup-db`（兩次）、`history --start 2026-07-31 --only amount`、`export`。
  - 沒有執行 `collect`、`revenue`，也沒有另外抓 10 月營收。對外請求只有補抓的 65 次，都經過 `fetch.request`。
  - 「改查詢」到「改表」之間沒有執行 `export`、`check`、`collect`。
  - 沒有執行還原，沒有刪除既有備份。沒有安裝排程，沒有改系統或 Docker 設定。
  - 預覽用 8001 埠，結束時已關閉；8000 埠沒有動。
  - QA-05 只用 mock 驗證，沒有停掉資料庫容器。

> **結論**
> - 備份 `TwStock_20261105_220059.bak`（85,716,992 B），早於任何程式修改。
> - 改表：`setup-db` 兩次都不報錯；上市 390 列改表前後 `diff` 完全相同。
> - 補抓：上櫃 65 天 × 6 列，請求 65 次，耗時 3 分 13 秒；日期集合和上市相同；11/05 六列和附錄 A-1 完全相同。
> - 匯出 16.7 → 19.0 秒（+2.3 秒，上限 +5 秒）。
> - compare「✅ 相同」（`margin.m5` 0 檔不同）；`--keep-new` 判定不同（1,904 處）。recalc「✅ 相同」。
> - `test_iter01`～`09` 全部通過（`test_iter09` 19 個測試）。
> - 8001 預覽：主控台 0 則訊息；375 px 各頁 `scrollWidth` 都是 375。

---

## 一、修改的檔案與行數

專案沒有 git。行數用修改前的副本（scratchpad）和修改後的 `wc -l` 與 `diff` 計算。

| 檔案 | 內容 | 行數（改前 → 改後；+／−） |
|---|---|---|
| `twstock/db.py` | `insti_amount` 加 `market`、新唯一鍵；3 條可重複執行的遷移 DDL | 479 → 489（+12／−2） |
| `twstock/collectors/daily.py` | 鍵 `amount.TPEx`、`TPEX_AMOUNT_UNIT`、`parse_tpex_insti_amount`、`fetch_tpex_insti_amount`；MERGE 加 market；上市解析加 `market`；上櫃行情保護 | 829 → 867（+48／−10） |
| `twstock/collectors/history.py` | `SECONDS_PER_KEY["amount.TPEx"] = 3.2` | 123 → 123（+1／−1） |
| `twstock/collectors/revenue.py` | `revenue_month_for` 一律回上個月 | 112 → 110（+1／−3） |
| `twstock/collectors/catchup.py` | `REVENUE_DONE_RATIO` 改由 `health` import | 337 → 336（+1／−2） |
| `twstock/health.py` | `Spec amount.TPEx`；`load_snapshot` 分市場；`revenue_status`、`revenue_counts`；`check_report(revenue=)` | 421 → 457（+42／−6） |
| `twstock/export.py` | `amount_by_market`、`insti_official_tpex`；`stock_margin(conv)`；`position`、`market_valuation`、`stock_valuation`、`_load_valuation`、`valuation`、`val`、`pbp` | 1,017 → 1,110（+104／−11） |
| `twstock/__main__.py` | `main()` 攔截 `pyodbc.Error`（回傳 2）；docstring 與 `--only` 的說明 | 251 → 256（+9／−4） |
| `site/app.js` | `valCard`；`instiCard` 上櫃官方一行與迷你圖；`revMixed` 與頁尾；「重設」；持股頁日期；選股 `pbp` | 1,174 → 1,200（+40／−14） |
| `site/stock.js` | 三張指標卡的一年位置與說明 | 447 → 454（+9／−2） |
| `README.md` | 第二節 | 152 → 156（+14／−10，多為長段落改寫） |
| `tests/test_iter03.py` | 附錄 E（fixture 補 `amount.TPEx`、`insti/summary`） | 1,290 → 1,299（+13／−4） |
| `tests/test_iter09.py`（新） | 附錄 F，19 個測試 | 309 |
| `logs/iter09_compare.py`、`logs/iter09_recalc.py`（新，工具） | 附錄 G、H | 75、115 |

- 程式（含網站，不含測試、工具、README）+259／−55，淨增約 204 行。和設計第〇節的原型行數一致（`app.js` 設計寫 +40，實際另有 14 行是同一行改寫）。

### README、`__main__.py`（設計第九節）

- README：
  - 第 3、15 行：三大法人買賣金額改為「上市、上櫃」。
  - 測試清單（表格與指令區）：加 `tests/test_iter09.py`。
  - `setup-db` 段落：第 9 輪 `insti_amount` 加 `market`、唯一鍵改 `(trade_date, market, unit)`、可重複執行、先 `backup`、改表後不可再執行舊版程式。
  - 指令區：`collect` 說明的三大法人金額（上市、上櫃）；`--only amount` 說明；`export` 行加「history、export 連不上資料庫時印一行說明並回傳 2」。
  - 選股：月份混雜說明、新條件「淨值比一年位置 ≤ N%」、「重設」回到預設。README 原本沒有「清除」字樣。
  - 三大法人卡：上櫃改為官方值（`insti_official_tpex`），沒有資料時才退回估算；`insti_amount` 以 `market` 區分。
  - 新增兩段：今日頁估值位置卡（`valuation`，含口徑）、個股頁估值位置（`val`，含不顯示的條件）。
  - 新增一段月營收收集時點（從每月第一個交易日開始，達前一月 98% 為止）。README 原本沒有「每月 10 日以後」的敘述，所以是新增，不是改寫。
  - 資料完整性：回傳碼 2 補上 `history`、`export`；第 9 輪的「上櫃法人金額」一列與「月營收」一行（✅／⏳／❌ 條件）。
- `__main__.py`：
  - docstring 的 `collect` 說明：三大法人金額（上市、上櫃）。
  - docstring 的 `--only amount` 範例、`--only` 的 help（附錄 C 已改），`choices` 不變。
  - `main()` 攔截 `pyodbc.Error`（附錄 C）。
  - docstring 沒有提到營收時點，所以不需要改。

---

## 二、各步驟的執行結果（台灣時間 2026-11-05）

| 時間 | 設計步驟 | 指令 | 結果 | 紀錄 |
|---|---|---|---|---|
| 22:00:58～22:01:06 | 0 | `python3 -u -m twstock backup` | ✅ 通過 `RESTORE VERIFYONLY`：`../_backups/TwStock_20261105_220059.bak`，**85,716,992 B**（程式印 81.7 MB），約 8 秒 | — |
| 22:01 | 1 | 原始程式副本存到 scratchpad（算行數用） | — | — |
| 22:01 | 1 | 舊程式 `python3 -u -m twstock export` | rc=0，**匯出耗時 16.7 秒**（`time` real 17.0 秒） | `logs/iter09_export_before.log` |
| 22:01 | 1 | 複製 `site/data` → `logs/iter09_before/` | `latest.json`、`screen.json`、`stocks/`、`etfs/` | — |
| 22:01 | 1 | 唯讀 SQL 快照 | 鍵 `PK__insti_am__…`、`UQ_insti_amount`；390 列，2026-07-31～2026-11-05 | `logs/iter09_snapshot_before.log`、`logs/iter09_amount_before.csv` |
| 22:01～22:02 | 2 | 套用附錄 C、D、E；取出附錄 F、G、H；`test_iter01`～`09` | 全部通過 | — |
| 22:02:26 | 3 | `python3 -u -m twstock setup-db` × 2 | 兩次都只印「資料庫已確認存在」「資料表已確認」，不報錯 | `logs/iter09_setupdb.log` |
| 22:02 | 3 | 唯讀 SQL 檢查 | 見下 | `logs/iter09_step3_sql.log` |
| 22:02:55～22:06:08 | 4 | `python3 -u -m twstock history --start 2026-07-31 --only amount` | 計畫「待抓 65 天；`amount.TPEx`：65 天」，沒有列 `amount`（0 天）；65 天都「寫入 6 筆」；「✅ 成功：65 天」 | `logs/iter09_history_amount.log` |
| 22:06 | 4 | 唯讀 SQL 檢查 | 見下 | `logs/iter09_step4_sql.log` |
| 22:06 | 5 | 新程式 `python3 -u -m twstock export` | rc=0，**匯出耗時 19.0 秒**（`time` real 19.3 秒），`latest.json 715 KB` | `logs/iter09_export_after.log` |
| 22:06 | 5 | `python3 logs/iter09_compare.py logs/iter09_before site/data` | **「✅ 相同」**，rc=0；沒有 `margin.m5` 換算差異 | `logs/iter09_compare.log` |
| 22:06 | 5 | 同上加 `--keep-new`（反證） | rc=1，「❌ 不同 1904 處：latest.json 鍵不同：['insti_official_tpex', 'valuation']、latest.json status、screen.json、stocks/1101.json…」 | `logs/iter09_compare_keepnew.log` |
| 22:07 | 5 | `python3 -u logs/iter09_recalc.py` | **「✅ 相同」**，rc=0 | `logs/iter09_recalc.log` |
| 22:07 | 5 | `python3 -u -m twstock check` | rc=0，「結果：無異常」 | `logs/iter09_check.log` |
| 22:07～ | 6 | README、`__main__.py`、8001 預覽 | 第四節 | `logs/iter09_serve8001.log` |
| 最後 | — | `test_iter01`～`09` | 9 支都「全部通過」 | `logs/iter09_tests.log` |

- 執行前先用唯讀腳本模擬步驟 4 的計畫：`amount` 0 天、`amount.TPEx` 65 天，交易日 65 天。確認後才執行補抓。
- 步驟 2 到步驟 3 之間沒有執行 `export`、`check`、`collect`。資料日從頭到尾都是 2026-11-05。
- 補抓沒有用到 `prices`，所以不會觸發月營收（`history` 只在 `prices` 被選時收營收）。
- 匯出後只改了一行前端文字（第三節），不影響 JSON，`site/data` 就是 22:06 那一次的結果。

### 步驟 3：改表後的 SQL 檢查

| 檢查 | 結果 | 預期 |
|---|---|---|
| `market` 欄 | `('market', is_nullable = 0)` | 1 列、0 |
| UQ 鍵 | 只有 `UQ_insti_amount_market` | 同左 |
| 市場列數 | `TWSE 390` | 只有 TWSE 390 |
| 預設與檢查條件 | `DF_insti_amount_market`、`CK_insti_amount_market` | — |
| 上市 `trade_date, unit, buy, sell, net` 與改表前 CSV | `diff` 完全相同 | 相同 |

- DDL ③ 沒有出現「無效的資料行名稱 market」，**不需要**改成 `EXEC(...)`（設計 1-2 的風險點 1）。

### 步驟 4：補抓後的 SQL 檢查

| 檢查 | 結果 |
|---|---|
| 市場天數、列數 | `TPEx 65 天 390 列`、`TWSE 65 天 390 列` |
| 上市日期 − 上櫃日期、上櫃 − 上市 | 都是 0 列 |
| 每市場每日不是 6 列的日期 | 0 列 |
| 上櫃 11/05（元） | foreign 68,076,212,954／69,660,322,744／−1,584,109,790；foreign_dealer 0／0／0；trust 4,007,623,069／5,103,111,498／−1,095,488,429；dealer_self 1,702,055,844／1,952,825,490／−250,769,646；dealer_hedge 2,618,281,045／3,538,074,742／−919,793,697；total 76,404,172,912／80,254,334,474／−3,850,161,562。**和附錄 A-1 完全相同** |
| 上櫃 11/04 外資 | −2,240,584,579 元（−22.41 億） |
| 上市 11/05 | foreign −102,460,621,838、trust +22,594,451,141、dealer_self＋dealer_hedge −43,527,495,658、total −123,393,666,355，和改鍵前相同 |
| 上市 390 列與改表前 CSV | `diff` 完全相同 |

- **請求次數 65 次**（每天 1 次 `insti/summary`），**耗時 3 分 13 秒**（設計預估 3.5 分鐘）。沒有重試、沒有錯誤。

### 步驟 5：匯出、比對、重算

#### 匯出耗時

| | 程式印出 | `time` real |
|---|---|---|
| 改前（舊程式） | 16.7 秒 | 17.0 秒 |
| 改後 | 19.0 秒 | 19.3 秒 |

- 多 2.3 秒，在 +5 秒上限內。主要來自 `_load_valuation` 讀約 47 萬列 `stock_fundamentals`（設計實測 1.7 秒）。

#### 大小

| 檔案 | 改前 | 改後 | 差 | 上限 |
|---|---|---|---|---|
| `latest.json` | 729,860 B | 731,727 B | +1,867 B（上櫃法人 20 天＋`valuation`） | 3 KB |
| `screen.json` | 245,528 B | 250,716 B | +5,188 B（`pbp`，和設計原型相同） | 15 KB |
| `stocks/` 合計 | 32,201,468 B | 32,343,901 B | +142,433 B（1,901 檔有 `val`，和設計原型相同） | 300 KB |

#### recalc（`logs/iter09_recalc.log`）

| 項目 | 結果 |
|---|---|
| 上市 11/05 | 外資 −1,024.6、投信 +225.9、自營 −435.3、合計 −1,233.9 億 |
| 上櫃 11/05 | 外資 −15.8、投信 −11.0、自營 −11.7、合計 −38.5 億；外資連賣 6 日 |
| 上市估值 | 本益比 15.75（15.75～21.76；0.4%）、淨值比 1.53（0.4%）、殖利率 2.77%（56.6%），計入 877 檔 |
| 上櫃估值 | 本益比 17.57（17.57～25.38；0.4%）、淨值比 1.82（0.8%）、殖利率 1.95%（61.6%），計入 674 檔 |
| 個股 | 有 `val` 1,901 檔，股本變動不輸出 48 檔；窗口 2025-11-05～2026-11-05 |
| 2330／2317／2412／2603 | `pe` [16, 22.47, 34.87]／[10, 13.83, 21.95]／[100, 26.16, 31.73]／[94, 2.98, 10.88]；`pb` 30／11／100／95；`dy` 59／87／1／6 |
| 5314、6669、5904 | 沒有 `val`（cap）；`screen.json` 的 `pbp` 仍有值（5314 = 2），由前端估值規則排除 |
| 6456 | 只有 `pb` [90, 0.45, 1.22] |
| `margin.m5` | `stocks/*.json` 與 `screen.json` 不同 0 檔 |
| 月營收家數 | 2026/09 1,980、2026/08 1,983、2026/07 1,982；10 月 0 家（使用者尚未收集） |

- 以上和 PM 驗收表、設計附錄 A-2、A-3 的 11/05 數字全部相同。

#### `check`（`logs/iter09_check.log`）

- 「上市法人金額 20/20、筆數 6、中位數 6、✅ 正常」，「上櫃法人金額 20/20、6、6、✅ 正常」。
- 「處置／注意股最後成功：2026-11-05 21:10」之後一行：「月營收 2026/10：已收 0 家（前一月 1,980 家的 0%），⏳ 公布期間（每月 10 日前）」。
- 「結果：無異常」，rc=0。

---

## 三、與設計不同的地方

### 1. 估值位置卡的窗口起日改成完整日期

- 設計 6-3 的定稿文字是「一年位置 = 近 242 個交易日（11/05 起）」，用 `md(T.from)` 只顯示月日。
- 問題：窗口起日是 **2025**-11-05，和資料日 2026-11-05 的月日相同。只寫「11/05 起」看起來像「從今天起」，會讓人誤解。
- 處理：改成 `T.from.replaceAll('-', '/')`，顯示「近 242 個交易日（2025/11/05 起）」。只改這一處（`site/app.js` 1 行）。
- 迷你圖說明「近 60 個交易日（08/07 起）」不跨年，維持 `md`。

### 2. 迷你圖起日是 08/07，不是設計範例的 08/10

- 設計 6-2 的範例寫 `"sf": "2026-08-10"`。實際是 `2026-08-07`：最近 60 個有官方本益比的交易日從 08/07 開始。這是資料決定的，不是程式差異；recalc 不檢查 `sf`。

### 3. README 的位置與寫法

- 設計第九節用 README 的行號列出修改處。實際 README 沒有獨立的「資料表」與「匯出欄位」段落，所以：
  - `insti_amount` 的 `market` 欄寫在 `setup-db` 段落與三大法人卡段落。
  - 新匯出欄位（`insti_official_tpex`、`valuation`、`val`、`pbp`）寫在各自的功能段落裡。
- README 原本沒有「每月 10 日以後」的敘述，所以月營收收集時點是新增一段。

### 4. 其他

- DDL ③ 不需要 `EXEC(...)`（第二節步驟 3）。
- 延後項目都沒有刪除。

---

## 四、畫面檢查（8001，正式資料；結束時已關閉）

用 Claude 內建瀏覽器開啟 `http://localhost:8001`，視窗設成 375 × 812，以 `javascript_tool` 讀取 DOM 與 `App` 狀態。主控台全程 **0 則訊息**。

| 頁面 | 結果 |
|---|---|
| 今日頁三大法人卡 | 「三大法人　上市，官方，含 ETF　11/05」大字 −1,233.9 億；上市一行；外資近 20 日連賣 6 日；「上櫃（官方，11/05）合計 -38.5億　外資 -15.8億　投信 -11.0億　自營 -11.7億」；上櫃外資近 20 日（10/06～11/05）連賣 6 日；口徑說明一句。**畫面上沒有「上櫃估算」** |
| 同上，mock 上櫃晚一天（`date` 改 11/04） | 「上櫃（官方，11/04，尚未更新）…」，不退回估算 |
| 同上，mock `insti_official_tpex = null` | 「上櫃估算（11/05）：外資 -12.1億…」＋「上櫃官方金額尚無資料，暫以張數 × 收盤估算…」 |
| 今日頁估值位置卡 | 「上市　本益比 15.75（一年最低）　淨值比 1.53（一年最低）　殖利率 2.77%（一年位置 56.6%）」；上櫃 17.57（一年最低）、1.82（一年最低）、1.95%（61.6%）；迷你圖「近 60 個交易日（08/07 起）」；口徑說明（窗口 2025/11/05 起、877／674 檔）。mock `valuation = null` → 整張卡不顯示 |
| 選股頁「重設」 | 按鈕文字「重設」；套預設第 1 組 31 檔 → 重設後 **1,961 檔**、hash `#/rank/screen?xd=1&xn=1&xc=1&o=tv`、5314 不在結果；清空 `localStorage` 直接開 `#/rank/screen` 也是 1,961 檔 |
| 選股頁營收月份 | 正式資料「營收 9 月 1,973 檔、8 月 5 檔」，沒有公布期間說明；mock `rmd = {202610: 285, 202609: 1693}`、6456 的 `rm = 202610` → 資料日一行加「（每月 1～10 日為公布期間，各股月份不同）」，欄名「營收年增（9 月）」，6456 那列「+30.83%（10月）」；頁尾為設計 4-4 的定稿文字 |
| `#/etf/00997A`（跨境） | 「11/04 單位數 1 日 -0.48%」，不含「今天」 |
| `#/etf/00982A` | 「今天單位數 1 日 +0.61%」 |
| `#/stock/5904` 指標卡 | 融資餘額 4,706 張「1日 +79　5日 -119」，和 `stocks/5904.json` 的 `margin.m5` 相同；本益比、殖利率卡「08/10 股本變動，官方值可能尚未調整」，沒有一年位置、沒有說明行（cap） |
| `#/stock/2603` | 本益比「一年位置 94%（2.98～10.88）」、淨值比「95%（0.67～1.06）」、殖利率「6%（5.83%～18.21%）」；說明行含「本益比位置也反映獲利變化」 |
| `#/stock/2412` | 本益比、淨值比「一年位置 最高」、殖利率「一年位置 最低」 |
| `#/stock/5314` | 沒有一年位置、沒有說明行 |
| 375 px | 今日頁、選股、兩個持股頁、四個個股頁的 `scrollWidth` 都是 375 |

### 沒有驗證的部分

- **5904 的換算窗口**：8/10 的面額變更已不在 11/05 的 5 日窗口內，正式資料看不到換算前後的差別；換算行為只由 `test_f93_stock_margin_conv`（mock）驗證。
- **QA-05**：只用 mock（`test_qa05_main_db_error`），沒有真的停掉資料庫容器。
- **F9-2 實際資料**：10 月營收 0 家，要等使用者下一次 `collect --catch-up`。`check` 的 ✅／❌ 與網站月份混雜只用 mock 驗證。
- **`test_iter09` 對舊程式的反證**：沒有重做（設計已做）。
- 沒有截圖存檔；深色模式、桌面寬度版面沒有目視檢查。

---

## 五、給 QA 的提醒

1. 本輪的 log 都在 `logs/iter09_*`。基線在 `logs/iter09_before/`（舊程式匯出），快照在 `logs/iter09_amount_before.csv`。
2. **改表後不可再執行舊版程式**（舊 MERGE 沒有 market）。
3. 資料日不是 11/05 時，以 `python3 logs/iter09_recalc.py` 的 SQL 重算為準。
4. 使用者還沒有收集 10 月營收。`check` 目前顯示「⏳ 公布期間」，11/10 以後才可能出現 ✅ 或 ❌。
5. 今日頁估值位置卡的窗口起日改成完整日期（第三節第 1 點）。
