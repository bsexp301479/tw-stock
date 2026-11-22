# 第 46 輪｜System Analyst：設計

- 撰寫日期：2026-11-22（週日）；資料日 2026-11-20（週五）。
- 依據：`46/01-analyst.md`（R51～R58、D134～D143）、`46/02-pm.md`（F46-1～F46-4、畫面文字逐字定稿、驗收 29 條；PM 自行決定 9 點使用者全部同意，含「D138 兩條件只查上櫃」與「尾碼提示含 B／L／R／U」）。
- 產出：本檔＋`46/03-design.diff`（628 行，可直接 `git apply`；在專案目錄 `git apply --check docs/iterations/46/03-design.diff` 已通過）。
- 做法：
  - `rsync -a --exclude .git --exclude .env --exclude _backups --exclude _archive` 把專案複製到 scratchpad `r46sa/proj`（**副本沒有 `.env`**），`git init` 並 commit 當基準；所有修改在副本完成，diff 由副本 `git diff` 產生（新檔用 `git add -N`）。
  - 先讀 `export_all` 的呼叫鏈確認**匯出不寫資料庫**（只有 SELECT；`health.write_run`／`finish_run`、`tradingcal.update_calendar`／`add_adhoc` 都不在匯出路徑），才在副本執行匯出：scratchpad 的小程式先用專案 `twstock/config.py` 的 `_load_env` 載入連線設定（沒有讀出或印出內容），再匯入副本的 `twstock`、確認 `SITE_DATA_DIR` 在副本內，呼叫 `export_all()`。只寫副本的 `site/data`（28.2 秒）。
  - 匯出前把副本的 `site/data/etfp/`、`latest.json` 複製到 `r46sa/before/` 當逐位元組比對的基準。
  - 副本跑 `tests/test_iter01～46` 共 46 個檔，**全部通過**；舊測試改 0 行。
  - 畫面：副本目錄背景起 `python3 -u -m twstock serve --port 8001 --no-browser`，內建瀏覽器開 `http://127.0.0.1:8001`，320／375／1024 寬、淺色／深色。結束時 localStorage 設回 `{"tw.todayTab":"ov","tw.stockTab":"k"}`、視窗 desktop／淺色、`pkill -f "twstock serve --port 8001"`（exit 144），8001 沒有 LISTEN。
- 守則：沒有讀、印、複製 `.env`；資料庫只有匯出的 SELECT；沒有外部請求、沒有 `collect`、沒有用 8000、沒有執行 `_archive/`；專案目錄只新增本檔與 `03-design.diff`。

---

## 一、改了哪些檔（`git diff --numstat`）

| 檔案 | 加／減 | 內容 |
|---|---|---|
| `twstock/export.py` | 33／0 | `EPF_KEYS` 常數、新純函式 `etf_perf`（放在 `etf_gaps` 之後）、ETF 迴圈接 `epf`／列表四欄、`etfs.ix` |
| `site/stock.js` | 11／6 | `perfHTML` 加第 4 個參數 `etf = false`（ETF 版文字、尾碼提示）；`renderStock` 多一行呼叫 |
| `site/app.js` | 32／6 | `ETF_SORT` 多一行 4 種排序；`EPF_COLS`、`ETF_PF_NOTE`、`etfPerfHTML`；`renderEtf` 的「行情／表現」欄組 |
| `site/index.html` | 2／2 | `app.js`、`stock.js` 的 `?v=` |
| `tests/test_iter46.py`（新） | 390／0 | 8 個測試、21 個反證 |
| `README.md` | 2／0 | 第 46 輪說明一段、測試指令一行 |
| `docs/iterations/README.md` | 1／0 | 第 46 輪一行 |

- 程式合計 76 行加、12 行減（PM 估約 75 行）；測試 390 行（估約 200 行；上限約 580 行）。`app.css` **不改**（見第四節差異 1）。
- `index.html` 的 `?v=`（和 `shasum` 前 8 碼相同）：

  | 檔案 | `?v=` |
  |---|---|
  | `app.css` | 7f4315c2（不變） |
  | `app.js` | **45ded7be**（原 c7bb2119） |
  | `stock.js` | **2cb335d6**（原 c2c7d916） |
  | `tools.js` | 64e7360f（不變） |
  | `help.js` | 55e93876（不變） |

## 二、程式設計

### 2-1 `twstock/export.py`

- 常數（`PF_DAYS` 下一行）：`EPF_KEYS = {20: "r20", 60: "r60", "y": "ry", "w": "rw"}`（`epf` 的區間 → `latest.json` ETF 列的鍵）。
- `etf_perf(rows, market, events, days, idx, w52_start)`（純函式，放在 `etf_gaps` 之後、`_num` 之前，也就是 `def etf_export` 之前；`test_iter23:134` 的區段外）：
  1. `rows` = `_load_etf_hist` 的一檔（`(日期, 開, 高, 低, 收, 量, 官方漲跌)`），`events` = `_load_etf_events` 的一檔。
  2. 事件：官方除息表每筆 → `{"d": 日期物件, "t": "息", "p": float(前收), "r": float(參考價), "src": "etf"}`；上市 `etf_gaps` 中**不在除息表**的日子 → `{"d", "t": "調", "p": float(c[i-1]), "r": round(float(c[i]) - float(ch[i]), 2), "src": "gap"}`（上櫃 `etf_gaps` 本來就回 `[]`）。
  3. `_price_events(d_, c, ch, "TWSE", ev)`（**固定傳 TWSE**，不做上櫃反推）→ `_adj_factors` → 還原收盤 `float(c[i]) * af[i]`（無成交 `None`）→ `stock_perf(d_, adj, days, idx, w52_start)`。
  4. 回傳 `None`：從沒成交；或 `market == "TPEx"` 且（有一天「`c[i]`、`c[i-1]` 有值、`ch[i]` 空、日期不在除息表」，或相鄰兩個有成交的還原收盤 `abs(後 ÷ 前 − 1) > 0.30`）（D138，PM 二之七第 1 點：只查上櫃）。
- `export_all`：
  - `edv = {}` 下一行 `eix = {}`。
  - ETF 迴圈在 `E["sh"] = …` 的 `if` 之後、`_write(p, E)` 之前：
    ```
                if (epf := etf_perf(epx[code], m, eev.get(code, ()), p_days, idx_close["TWSE"], w52_start)) is not None:
                    E["epf"] = epf                                 # 第 46 輪 F46-1：近期表現（含息；放在最後；沒有就不輸出）
    ```
  - `edv[code] = etf_div_row(…)` 那一行不動，下面 5 行：`epf` 的 `20`、`60`、`"y"`、`"w"` 列，本檔 % 有值 → `edv[code]["r20"…]`（放在配息四欄之後，`etf_block` 的 `r.update(div_rows…)` 自動合併）；指數 % 有值 → `eix.setdefault(區間, 值)`（取第一個有值的檔，PM 二之八「不要只取第一檔」）。
  - `latest` 組好後、`alerts.w` 之前：`if latest["etfs"] and eix: latest["etfs"]["ix"] = {str(k): eix[k] for k in EPF_KEYS if k in eix}`（鍵順序固定 `"20"、"60"、"y"、"w"`）。
- `etf_export`（雜湊仍 `711fa2b7790c`）、`etf_block`、`stock_perf`、`_price_events`、`_adj_factors` 都**不改**；原始碼 `sh_etf` 仍 3 次。
- 迴圈變數 `k, _, r, i, _` 在 `export_all` 後面沒有再用到（已查）。

### 2-2 `site/stock.js`

- `function perfHTML(pf, mkt, nt, etf = false)`：`etf` 為假時輸出**逐字不變**；ETF 版傳代號字串（PM 二之七第 3 點）。
  - `ix = mkt === 'TWSE' || etf ? '加權指數' : '櫃買指數'`；`ls` 仍依市場（上市以來／上櫃以來）。
  - `short`、`full` 用三元運算另取 ETF 版文字（和 PM 二之一逐字相同）；股票版字串留在原處。短句仍是變數，`noteHTML` 字面呼叫仍 8 個（`test_iter13`）。
  - `tip`：`{B, L, U}[etf.slice(-1).replace('R', 'L')]`，有值時在 `sec-h` 之後輸出 `<div class="muted small">提示</div>`；股票與沒有對應尾碼的 ETF 輸出空字串。
  - `me = etf ? '本檔' : '本股'`：表頭與「最後成交」。
  - 新程式沒有 `.at(`、`replaceAll`、`||=`、`&&=`、`??=`（`perfHTML` 在 node 14 跑測試）。
- `renderStock`：`${data.pf ? perfHTML(…) : ''}` 那一行**下一行**加 `${E && data.epf ? perfHTML(data.epf, data.market, noTrade ? P.d[lt] : null, data.code) : ''}`；K 線卡之後、配息卡之前。股票沒有 `epf`、ETF 沒有 `pf`，兩行互不影響。
- 股票版輸出：`test_iter46` 用 `test_iter23` 的 4 組輸入，對改前的 `perfHTML`（副本基準 commit）算出輸出雜湊 `c2dc8dcf8799`，改後相同；`perfHTML(…, false)` 與不傳也相同。

### 2-3 `site/app.js`

- `ETF_SORT`：在 `['dvr', '配息率', -1], ['dva', '最近除息', 1]];` 那一行**之前另起一行**加 4 項（文字照 PM），由高到低；缺值排最後（原排序規則）。
- 新增（`ETF_N` 之後、`renderEtf` 之前，所以不在 `test_iter20:35` 取的 `renderEtf` 區段內）：
  - `EPF_COLS = [['r20', '20', '20 日'], ['r60', '60', '60 日'], ['ry', 'y', '今年以來'], ['rw', 'w', '52 週']]`（列的鍵、`ix` 的鍵、表頭）。
  - `ETF_PF_NOTE`：表現表頁尾「共 N 檔。」之後的文字（和 PM 二之一逐字相同）。
  - `etfPerfHTML(list, ix)`：上方「加權指數同期：…（價格指數，不含股息）」一行（`ix` 沒有或某區間缺值就略過該段；全缺不輸出）＋表現表（`class="tbl etf-tbl"`，名稱欄和行情表相同含 `holdTag`；收盤 `r.c == null` → `無成交`；數字欄 `sgn(v) + '%'`、缺值 `--`）。
- `renderEtf`：
  - `hasPf` = 任一列有 `r20`／`r60`／`ry`／`rw`；`perf = hasPf && App.etfCols === 'perf'`（只記在這次瀏覽，不寫 localStorage；預設「行情」）。
  - 標題列抽成 `head`、「顯示全部」鈕抽成 `more`（兩個欄組共用）；`hasPf` 時排序選單之後加 `segHTML('etfColSeg', [['flow', '行情'], ['perf', '表現']], …)`。
  - 排序選單：`hasPf` 為假（舊 `latest.json`）時不列 4 種含息排序。
  - `perf` 時畫表現表與 `共 ${list.length} 檔。${ETF_PF_NOTE}`；否則原本的行情表模板（表頭、各列、頁尾字面不動，`股票口徑的融資融券。${ETF_DIV_NOTE}</div></section>\`;` 仍在最後）。
  - `keyCol`：`if (perf) keyCol({ r20: 2, r60: 3, ry: 4, rw: 5 }[f]); else { 原本兩行 }`（原本兩行字面保留、只加縮排，`test_iter13:18`、`test_iter36:171` 照舊通過）；預設排序 `tv` 不會移動表現表的欄，行情表選新排序時欄位不移動。
  - 篩選框、「顯示全部」、點列進 ETF 頁：兩個欄組共用原程式（都是 `tr[data-etf]`、名稱在第 0 欄）。
- 用 node 把改前、改後的 `renderEtf`（`$`、`keyCol` 等換成假物件）各跑一次比對 `innerHTML`：
  - 舊 `latest.json`（`r46sa/before/`）：改後**逐字等於**改前。
  - 新 `latest.json`、「行情」：改後 = 改前＋排序選單 4 個 `<option>`＋欄組切換，其餘逐字相同。

## 三、測試設計（`tests/test_iter46.py`，不連網、不連資料庫）

| 測試 | 內容 | 對應驗收 |
|---|---|---|
| `test_etf_perf`（`check_perf`） | 自造 1 年交易日：上市除息（漲跌 0、在除息表）→ 0%，且等於 `stock_perf` 直接算；上市推測分割（漲跌 +0.5）→ 52 週 +2.5%；上櫃除息（漲跌空、在除息表）→ 照常；同資料不在除息表 → `None`；上櫃「收盤 − 漲跌 ≠ 前收」不反推 → +1%；+31%：上櫃 `None`、上市照常、+29% 不擋；從沒成交 `None`；新上市最後加 `s` | 8 |
| `test_wiring`（`check_wiring`） | `etf_gaps` < `etf_perf` < `etf_export`；`etf_export`～`_load_holdings` 沒有 `pf`；`sh_etf` 3 次；`E["epf"]` 只出現 1 次且在 `E["sh"]` 之後、`_write` 之前；對照固定 `idx_close["TWSE"]`；列表欄在 `etf_div_row` 之後；`ix` 在 `latest` 組好之後；`etf_export` 雜湊 `711fa2b7790c`；`epf` 不進 `screen.json` | 10 |
| `test_site_data` | 讀實際 `site/data`（沒有 `etfs.ix` 時略過）：每檔 `epf` 格式、列表四欄 = `epf` 第 3 欄（缺值不輸出、在最後）、指數欄 = `ix`；資料日是 2026-11-20 時：0050、0056、00878、00679B、0052 逐位相同，009833、00991A、00674R、00631L、00775B、00986B 邊界值，`ix`、0050 列四欄、367 檔都有 | 1～7、11、12 |
| `test_card`（`check_card`） | node 跑 `perfHTML`：股票版雜湊 `c2dc8dcf8799`；9 檔 ETF 版的標題、表頭（上櫃也是加權指數）、短句、完整說明（和 `02-pm.md` 的程式碼區塊逐字比對，含有／沒有 `s` 列）、尾碼提示（B、L、R、U 有；數字、K 沒有）、上市以來／上櫃以來、本檔最後成交；呼叫那一行的位置、`noteHTML` 字面 8 個、node 14 語法 | 14～17、23 |
| `test_list`（`check_list`） | 新排序那一行在 `dvr` 行之前；`keyCol` 分欄組；欄組不寫 localStorage；舊資料不列新排序；node 跑 `etfPerfHTML`：頁尾和 PM 表格逐字比對、加權同期一行（全有／部分／沒有）、表頭、0050 列 `-21.91%`…`+39.20%`、缺值 `--`、無成交、排序（高到低、缺值最後）；頁尾沒有「自選」 | 18～21 |
| `test_words`（`check_words`） | `perfHTML`、`ETF_PF_NOTE`、`etfPerfHTML`、`ETF_SORT`、README 第 46 輪那一行不含任務的禁用詞與 `test_iter41`／`test_iter42`／`test_iter23` 的詞（「借券賣出」除外） | 22 |
| `test_version_and_docs` | 5 個 `?v=` = sha1 前 8 碼；README 測試指令與第 46 輪段落（不含「第 23 輪」）；`docs/iterations/README.md` 有第 46 輪 | 26 |
| `test_contrast` | 21 個反證（下表），每個都要讓對應檢查失敗 | 反證 |

反證（把原始碼改壞，確認測試擋得下）：上櫃不防呆、防呆也套用上市、啟用上櫃反推、不採用推測調整、防呆門檻改 40%、`epf` 放在 `_write` 之後、對照用各市場指數、ETF 表頭寫櫃買指數、拿掉尾碼提示、R 尾碼沒有提示、ETF 標題右側寫本股、股票版輸出改變、ETF 版用承銷價、表現表套用行情 `keyCol`、欄組寫入 localStorage、舊資料也列新排序、缺值顯示 0、無成交顯示 `--`、新排序插在 `dvr` 那一行、頁尾和 PM 不同、用詞。

- 驗收 9（拿掉 `epf` 後 367 檔逐位元組相同）、12 的「拿掉新鍵後 `latest.json` 相同」、13（大小）、24、25、27～29 由 PG／QA 實跑；SA 在副本已先做過，結果見第五節。

## 四、和 PM 規格的差異（SA 決定，請使用者確認）

1. **`app.css` 不改**：表現表沿用 `class="tbl etf-tbl"`，名稱欄的兩行截斷、持股小標換行等手機樣式直接套用，不需要新增欄寬規則；`app.css` 的 `?v=` 因此不變（PM 估 `app.css` 約 2 行、`?v=` 3 個 → 實際 0 行、2 個）。
2. **舊 `latest.json` 時排序選單不列 4 種含息排序**：PM 規格只說「舊 `latest.json` 不顯示欄組切換（畫面同改前）」；若照列 4 種新排序，選了也全是缺值，畫面和改前不同。所以跟著 `hasPf` 一起隱藏，舊資料畫面逐字同改前（已用 node 比對）。
3. **`renderEtf` 的標題列與「顯示全部」鈕抽成 `head`、`more` 兩個常數**，兩個欄組各一段模板；原因是 `test_iter36:193` 逐字鎖住行情表頁尾的結尾 `` …融資融券。${ETF_DIV_NOTE}</div></section>`; ``，無法在同一段模板裡換頁尾。行情表的 `innerHTML` 輸出不變（第二節 2-3）。
4. **「加權指數同期」那一行放在表現表的卡片上方**（`margin-bottom:6px`），不在卡片內；PM 只寫「表現表上方一行」。

## 五、核對結果

- **epf 和分析師 2.6 逐位相同**（副本匯出，資料日 2026-11-20）：0050（52 週 +39.20%）、0056（+38.48%）、00878（+52.32%，5 日 −13.23%）、00679B（+0.17%，指數欄 5 日 −17.5 = 加權）、0052（+41.52%，差距 +10.14）的 `epf` 6 列全部相同；009833 最後一列 `["s","2026-11-19",-5.05,-6.23,1.17]`、00991A `["s","2025-12-18",11.52,31.18,-19.66]`、00674R 11.44、00631L 41.73、00775B 0.92、00986B 5 日 0.0／−17.5。加權 52 週 +31.38%，`etfs.ix` = `{"20": -23.15, "60": -20.32, "y": 24.41, "w": 31.38}`，和 `stocks/2330.json` `pf` 指數欄相同。
- **367 檔都有 `epf`**（0 檔觸發 D138、0 檔從沒成交）。
- **逐位元組**：367 檔 `etfp/` 拿掉 `epf` 後以 `_write` 同格式序列化，和匯出前 **0 檔不同**；`latest.json` 拿掉 `r20`～`rw` 與 `ix` 後只有 `status.exported_at` 不同。
- `latest.json` 813,424 → 828,631 bytes（**+15.2 KB**，≤ 25 KB）；0050 列四欄 −21.91、−19.3、31.35、39.2 在 `dvc` 之後；00991A 沒有 `rw`；009833 四鍵都沒有。
- 全部測試：`tests/test_iter01～46` 46 個檔全部通過；`git diff --stat tests/` 只有新檔 `test_iter46.py`。

## 六、畫面檢查（副本 8001，內建瀏覽器）

| 頁面 | 320 | 375 | 1024 | 結果 |
|---|---|---|---|---|
| 0050 走勢分頁 | 表 254／254 | 表 309／309 | ✓ | K 線卡 → 近期表現（含息）→ 配息與填息；沒有提示行 |
| 00679B | ✓ | 表 309／309、頁寬 375 | ✓ | 債券提示一行（375 寬 1 行）；加權指數；5 日 +1.27% |
| 00631L | | ✓ | | 槓桿、反向提示 |
| 009833 | 表 254 | 表 309、8 列 | | 六列「--」＋「上市以來 11/19 起」 |
| 00986B | 表 254 | ✓ | | 標題右側「至 11/20，本檔最後成交 11/12」、債券提示 |
| 2330（股票） | | ✓ | | 仍是「近期表現」、本股 |
| `#/etf` 行情 | 頁寬 320 | 頁寬 375 | ✓ | 排序選單後多「行情｜表現」；表頭同改前 |
| `#/etf` 表現 | 表 405／254（在 `.tbl-wrap` 內捲動） | 表 405／309（同） | 全部可見 | 加權同期一行（320 寬 3 行）；0050 列 84.45、-21.91%、-19.30%、+31.35%、+39.20% |

- 所有頁面 `scrollWidth = innerWidth`（320、375），淺色／深色顏色正常，主控台沒有錯誤。
- 表現表選「含息 52 週」：52 週欄移到第 2 欄，00715L +189.95% 在最前，缺值在最後；切回「行情」表頭沒有移動；排序改回成交額後切「表現」欄位不移動；篩選「00679」只剩 00679B。
- 手機寬度下表現表要橫向捲動才看到「今年以來」「52 週」欄（表在 `.tbl-wrap` 內捲動，驗收 27 不算頁面溢出；排序後該欄會移到第 2 欄），見 D144。
- 結束：localStorage `{"tw.todayTab":"ov","tw.stockTab":"k"}`（測試中寫入的 `tw.etfSort` 已清掉）、desktop／淺色、8001 沒有 LISTEN。

## 七、需要使用者決定的事項（D144 起；目前最大 D143）

### D144 ETF 列表「表現」表在手機的寬度

- 現況：表現表 6 欄在 375 寬需要 405px，比可視寬度 309px 多約 96px，「52 週」欄要在表格內橫向捲動才看得到（320 寬也是）。PM 規格預期「比行情表 14 欄窄很多」，但沒有寫一定要不捲動；驗收 27 只要求頁面本身不溢出（已符合）。
- **A：照現在（建議）**：和行情表一樣在表格內捲動；選「含息 52 週」等排序時該欄會移到第 2 欄，一眼看得到。0 行。
- B：手機（≤ 520px）隱藏「收盤」欄（`app.css` 1 行＋`?v=`）：約可省 60px，仍差約 36px，不一定能完全不捲動。
- C：手機只顯示「今年以來」「52 週」兩欄（`app.css` 1 行＋`?v=`），20／60 日要到寬螢幕或 ETF 個股頁看。
- **建議 A**：不增加 CSS 與規則，排序已解決「看最重要那一欄」的需求。

（舊測試：本輪 0 行，沒有需要使用者決定的舊測試修改。）

## 八、給 PG

1. 在專案目錄 `git apply docs/iterations/46/03-design.diff`（`--check` 已通過）。
2. 匯出前把 `site/data/etfp/` 與 `site/data/latest.json` 複製到 scratchpad（驗收 9、12 的基準），同一晚不要先跑 `collect`。
3. 跑 `for f in tests/test_iter*.py; do python3 $f >/dev/null 2>&1 || echo FAIL $f; done`：46 個檔全過（匯出前 `test_iter46.test_site_data` 會印「尚未用第 46 輪匯出，略過」）。
4. 依 D143 執行 `python3 -m twstock export`（只讀資料庫、只寫 `site/data/`），再跑一次全部測試（這次 `test_site_data` 會核對 2.6 手算例）。
5. 比對：367 檔拿掉 `epf` 後以 `json.dumps(obj, ensure_ascii=False, separators=(",", ":"))` 和備份逐位元組相同；`latest.json` 拿掉 `r20`、`r60`、`ry`、`rw` 與 `etfs.ix` 後只有 `status.exported_at` 不同；大小增加約 15 KB。
6. 8001 冒煙：`#/stock/0050`、`#/stock/00679B`、`#/stock/009833`、`#/stock/00986B`、`#/etf`（行情／表現切換、選「含息 52 週」）；結束時 localStorage 恢復、視窗 desktop、`pkill`、8001 沒有 LISTEN。
7. 名詞說明、自選 ETF 表本輪不改（D141 = C、D142 = A）；`help.js` 的 `?v=` 不變。

## 使用者決定（2026-11-22）

- D144 = A：照現在，手機在表格內橫向捲動，0 行。
- 和 PM 的 4 點差異：全部接受。
- 新測試 `test_iter46.py` 390 行：接受。
