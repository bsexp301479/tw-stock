# 第 11 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-07（週六）凌晨
- 依據：
  - `03-design.md`：第四節的步驟與停止條件、第十三節的提醒、附錄 C 的原型差異。
  - `02-pm.md`：範圍與驗收。
  - 使用者對 SA 的回覆「照建議，進 PG」：接受第十二節的 5 點調整，包含 `stocks/` 上限放寬為 2.5 MB。
- 本輪項目：F11-3（第 10 輪收尾小修）、F11-1（借券收集、股數、`check`、個股圖與指標卡）、F11-2（借券排行、今日頁一行、選股條件）。**全部完成**，沒有用到延後順序。
- 程式來源：
  - 套用前先確認專案檔案和 SA 的基線 `orig/` 逐檔相同（`diff -rq` 無差異）。
  - 所有程式檔、測試檔、fixture 4 檔、`logs/iter11_compare.py` 都直接複製原型 `proj/`，所以和附錄 C 逐位元組相同。
  - F11-3 的 3 處是先手動套用並驗證，之後被原型檔覆蓋；兩者內容相同。
  - 和設計不同的地方有 3 處，見第三節：比對工具多剔除 1 項、README 文字由 PG 撰寫、新增唯讀 SQL 工具。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，沒有讀出或印出帳密；沒有動、也沒有執行 `_archive/`。
  - 只執行允許的寫入：
    - `backup`
    - `setup-db`（兩次）
    - 手動 `update_industry`（一次）
    - `history --only sbl`（試補 5 天、補全部、重跑各一次）
    - `export`（改前、改後各一次）
  - 另外執行了唯讀的 `check` 與 SQL 核對。
  - 沒有執行 `collect`、`revenue`。
  - 對外請求：
    - 試補 10 次、補全部 484 次，都經過 `fetch.request`；重跑 0 次。
    - `update_industry` 2 次，使用既有端點。
  - 沒有執行還原，沒有刪除既有備份。沒有安裝排程，沒有改系統或 Docker 設定。
  - 預覽用 8001 埠，結束時已關閉；8000 埠（使用者的伺服器）沒有動。

> **結論**
> - 備份 `TwStock_20261107_005526.bak`（86,654,976 B，RESTORE VERIFYONLY 通過），早於任何程式修改（00:56:37）。
> - 建表：`setup-db` 兩次都 rc=0。既有 25 張表的列數和 `stocks` 既有欄位的 checksum 前後完全相同，只多了 `sbl_trades`、`etf_sbl` 兩張表。
> - 股數：2330 = 25,932,370,067、2408 = 3,450,205,894；11/06 有收盤的 1,964 檔中 NULL 為 0。
> - 補抓：247 天 × 2 市場，共 494 次請求（試補 10 次＋全部 484 次）。全部補抓耗時 14 分 26 秒。
>   - 寫入股票 455,930 列（上市 259,333、上櫃 196,597）、ETF 81,575 列。
>   - 重跑「待抓 0 天」。
> - 公式不符 4 列，都是停止買賣（備註含「!」）時官方直接把餘額歸零，照存（第二節步驟 5）。
> - PM 的數字驗收全部相符（附錄 A 的 SQL 結果）。
> - 匯出時間 19.7 → 21.0 秒（+1.3 秒，上限 +3 秒）。
> - 大小（上限都沒有超過）：
>
>   | 檔案 | 增加 | 上限 |
>   |---|---|---|
>   | `stocks/` | 2,142,117 B（2.04 MiB） | 2.5 MB（SA 調整） |
>   | `screen.json` | 30.2 KB | 40 KB |
>   | `latest.json` | 251 B | 1 KB |
>
> - compare「✅ 相同」；`--keep-new` 判定不同（1,889 處）。
> - `test_iter01`～`11` 全部通過。`check` rc=0，借券兩行都是 20/20 ✅。
> - 8001 預覽：375 px 各頁 `scrollWidth` 都是 375，主控台沒有錯誤。

---

## 一、修改的檔案與行數

行數是用 SA 的基線 `orig/`（和修改前的專案相同）與修改後的檔案，以 `wc -l` 與 `diff` 計算。

| 檔案 | 內容 | 行數（改前 → 改後；+／−） |
|---|---|---|
| `twstock/db.py` | 新表 `sbl_trades`、`etf_sbl`、索引；`stocks.shares`；setup 訊息 | 511 → 551（+41／−1） |
| `twstock/collectors/daily.py` | `SBL`、`DAY_KEYS`、`parse_sbl`、`sbl_mismatch`、`fetch_sbl`、`merge_sbl`、`_collect_key` 分支、行情保護 | 868 → 957（+97／−8） |
| `twstock/collectors/industry.py` | 股數解析與 UPDATE | 39 → 41（+11／−9） |
| `twstock/collectors/history.py` | `SECONDS_PER_KEY` | 173 → 174（+1） |
| `twstock/health.py` | 兩個 `Spec`、`_MARKET_SQL["sbl"]` | 546 → 548（+2） |
| `twstock/export.py` | `lots`、`stock_sbl`、`market_sbl`、`_load_sbl`、`margin_series` 的 `lb`；`sbl`、`sd`、screen 新欄 | 1,219 → 1,286（+74／−7） |
| `twstock/__main__.py` | docstring、`--only` 的 `choices` 與說明 | 258 → 259（+3／−2） |
| `site/stock.js` | F11-3 口徑說明；借券指標卡、圖第三條線、圖例、週月彙總 | 487 → 500（+21／−8） |
| `site/app.js` | F11-3 `gm`、`gmy`；`sblLine`、排行 2 種、`sblTable`、選股條件與欄 | 1,222 → 1,256（+39／−5） |
| `README.md` | 見下 | 165 → 167（+7／−5，多為長段落改寫） |
| `tests/test_iter03.py`、`tests/test_iter05.py` | 設計 9-2 | +22／−4；+1／−1 |
| `tests/test_iter11.py`（新） | 11 個測試 | 240 |
| `tests/fixtures/`（新，4 檔） | TWT93U、margin/sbl 精簡版與休市回應 | 3,802 B |
| `logs/iter11_compare.py`（新，工具） | 設計附錄 C＋PG 補 2 行 | 65 |
| `logs/iter11_sql_check.py`（新，唯讀工具） | 設計 9-3 的 SQL | 25 |

### README（設計第十節）

- 模組表：`daily` 加「借券賣出」，`industry` 改成「產業別與發行股數」；網站說明加借券排行、借券賣出圖與指標卡。
- 「新增資料表」一段加第 11 輪的 `sbl_trades`、`etf_sbl`、`stocks.shares`。
- 指令範例加 `history --start 2025-10-30 --only sbl`（約 490 次、30 分鐘；不指定 `--only` 時不補借券）。
- 選股段落加借券條件 2 個、`screen.json` 新欄與 `head.sd`，以及毛利率欄的季別小字（F11-3）。
- 新增「借券賣出」一段，內容包括：
  - 來源、單位（股）、張數換算
  - 晚上 8 點半以後才有、尚未公布的判斷、第二版不重抓
  - 公式不符時照存
  - `check` 兩行、`stocks.shares`（只存目前股數）
  - 個股圖與指標卡、`stocks/{代號}.json` 的 `sbl`
  - 排行、今日頁一行與 `latest.json` 的 `sbl`
  - 「不等於看空」的說明
- 資料完整性一段加「第 11 輪：新增上市／上櫃借券 2 個資料集（下限上市 800、上櫃 550 檔）」。
- 實際補抓 14 分鐘，比 README 寫的「30 分鐘」快。README 保留 SA 的保守估計，沒有改。

### `__main__.py`

照附錄 C：

- `--only` 的 `choices` 加 `"sbl"`，說明加「sbl = 借券賣出」。
- docstring 加 `history --start 2025-10-30 --only sbl` 範例。

沒有新增子指令或旗標。

---

## 二、執行步驟與結果

### 步驟 1：備份與基線

- `python3 -u -m twstock backup`（00:55:26）：`TwStock_20261107_005526.bak`，86,654,976 B，RESTORE VERIFYONLY 通過。紀錄在 `logs/iter11_backup.log`。
- 既有表列數與 `stocks` checksum：`logs/iter11_rows_before.txt`，25 張表，例如 `stocks` 1,999、`daily_prices` 483,314、`margin_trades` 451,418；checksum 1053038702。
- 舊程式 `export`：`⏱️ 匯出耗時 19.7 秒`（`time` 20.0 秒），紀錄在 `logs/iter11_export_before.log`。
- `site/data/` 複製到 `logs/iter11_before/` 作為比對基線。改前 `stocks/` 合計 33,261,643 B、`screen.json` 321,760 B、`latest.json` 731,366 B。

### 步驟 2：F11-3

- 改 `site/stock.js` 的口徑說明一句，以及 `site/app.js` 的 `gm`、`gmy` 兩行（文字和設計 5-1、5-2 相同）。`node --check` 通過。
- 第一個程式修改在備份之後（00:56 起）。
- 匯出不受影響，最後的 compare 也涵蓋這一點（F11-3 沒有新鍵）。

### 步驟 3：程式、建表、股數

- 00:56:37 套用全部程式與測試；`test_iter01`～`11` 全部通過（`logs/iter11_tests.log`）。
- `setup-db` 兩次都 rc=0，訊息含 `sbl_trades、etf_sbl（第 11 輪另加 stocks.shares）`（`logs/iter11_setupdb.log`）。
- 和改前的列數 `diff` 只多兩行：`> etf_sbl 0`、`> sbl_trades 0`；checksum 不變（`logs/iter11_rows_after_ddl.txt`）。
- 條件約束：兩張表各有 PK 與 `UQ_sbl_trades`／`UQ_etf_sbl`；索引 `IX_sbl_trades_date`；`stocks.shares` 是 `bigint`、可為 NULL。
- 手動執行 `update_industry`：「產業別、股數：更新 1990 檔」。
  - 2330、2408 的股數和 PM 相同。
  - 11/06 有收盤的 1,964 檔，`shares` NULL 為 0。
  - `stocks` 既有欄位（含 `industry`）的 checksum 不變。
  - 紀錄在 `logs/iter11_shares.txt`。

### 步驟 4：試補 5 天

- 指令：`history --start 2026-10-31 --only sbl`。
  - 交易日 11/02～11/06，共 10 次請求，14.9 秒。
  - 每天寫入上市 1,063～1,064、上櫃 815 檔（`logs/iter11_sbl_try.log`）。
- SQL 核對（`logs/iter11_sql_try.txt`）：11/06 四檔、兩個市場的合計、占股本前 5 名都和 PM 驗收 #4、F11-2 #2 相同，公式不符 0 列。
- **略過筆數**（設計第十二節 #2）：每天的「寫入（解析出的股票列數）」和資料表中的列數完全相同，略過 0 筆。

### 步驟 5：補全部

- 指令：`history --start 2025-10-30 --only sbl`。
  - 00:57:43～01:12:09，14 分 26 秒，242 天 × 2 = 484 次請求。
  - 「✅ 成功：242 天」，rc=0（`logs/iter11_sbl_history.log`）。
- 公式不符警告 4 次，各 1 檔（`logs/iter11_sbl_mismatch.txt`）。全部都是「前日有餘額、當日賣出／還券／調整都是 0、當日餘額 0」，備註含 `!`（停止買賣）：

  | 代號 | 日期 | 前日餘額（股） | 備註 |
  |---|---|---|---|
  | 3454 | 2026-03-19 | 4,000 | `XV!` |
  | 1589 | 2026-04-07 | 2,498,426 | `X!` |
  | 8105 | 2026-08-19 | 7,982,000 | `X!` |
  | 2323 | 2026-10-01 | 109,000 | `V!` |

  依設計照存。圖上這幾天餘額會落到 0。
- 重跑同一指令：「待抓 0 天」，0 次請求（`logs/iter11_sbl_history_rerun.log`）。
- 每市場 247 天（2025-10-30～2026-11-06）：上市 259,333 列、上櫃 196,597 列；ETF 247 天 81,575 列（`logs/iter11_sql_numbers.txt`）。
- 補抓後列數 `diff`：只多 `> etf_sbl 81575`、`> sbl_trades 455930`，既有表不變（`logs/iter11_rows_after_history.txt`）。

### 步驟 6：`check`（唯讀）

- rc=0，「結果：無異常」。
- 「上市借券 20/20 2026-11-06 1,064 ✅ 正常」「上櫃借券 20/20 2026-11-06 815 ✅ 正常」，排在融資融券之後（`logs/iter11_check.log`）。

### 步驟 7：匯出與隔離比對

- 新程式 `export`：`⏱️ 匯出耗時 21.0 秒`（`time` 21.3 秒），+1.3 秒（`logs/iter11_export_after.log`）。
- `iter11_compare.py logs/iter11_before site/data`：「✅ 相同」，rc=0（`logs/iter11_compare.log`）。
  - 新鍵大小：stocks 的 `sbl`＋`mg.lb` 共 1,886 檔、2,092 KB；screen 新欄 30.2 KB；latest 的 `sbl` 120 B。
- `--keep-new`：rc=1，「不同 1,889 處」（反證）。
- 實際檔案大小：`stocks/` +2,142,117 B、`screen.json` +30,951 B、`latest.json` +251 B。
- 匯出內容抽查：
  - `latest.sbl` = 上市 `{lb 13177246, l1 169983, n 1064}`、上櫃 `{lb 1769466, l1 15063, n 815}`。
  - 2330 `sbl` = `{lb 20183, l1 1770, l5 3995, lp 0.08, lx 269.1}`，`mg.lb` 第一天 7,617、最後一天 20,183。
  - 2408 `mg.lb` 第一天 11,140、最後一天 96,099，`lp` 2.79。
  - `screen.sd` = 兩個市場都是 2026-11-06。

### 步驟 8：畫面（8001，375 px）

| 頁面 | 結果 |
|---|---|
| `#/stock/2330` | 指標卡「借券賣出餘額 20,183 張、1日 +1,770　5日 +3,995」「借券占股本 0.08%、融券的 269.1 倍　資料 11/06」；說明含「不等於看空」；圖標題「融資／融券／借券賣出餘額」，圖例「借券 20,183」。截圖確認三條線都看得到，融券線（75 張）沒有被壓平。F11-3 的口徑說明句有出現 |
| `#/stock/1341`（沒有借券資料） | 沒有借券卡，沒有錯誤 |
| `#/rank/l+` | 前 3 名：台積電 +37.8 億、鴻海 +17.0 億、大立光 +15.7 億（PM F11-2 #1：37.79／16.99／15.74）；頁尾含「不等於看空」 |
| `#/rank/lp` | 技嘉 10.20%、友達 10.00%、京元電子 10.00% |
| 今日頁 | 「借券賣出餘額　上市 1,318 萬張 +169,983（融券的 127 倍）　上櫃 177 萬張 +15,063（融券的 60 倍）　看排行 →」與說明一行 |
| `#/rank/screen` | 勾選「借券占股本 ≥ 5%」後網址帶 `lp=5`，符合 150 檔（`screen.json` 中 `lp ≥ 5` 有 151 檔，差 1 檔應是共同排除，留給 QA 用 SQL 確認）；「借券 5 日增加 ≥ 張」條件存在（`l5 ≥ 1000` 有 117 檔） |

- 每一頁的 `scrollWidth` 都是 375；主控台沒有錯誤。
- 結束後關閉 8001（`lsof` 確認），8000 埠照常。

---

## 三、和設計的差異

1. **`logs/iter11_compare.py` 多剔除 `status.datasets` 的 `sbl.TWSE`、`sbl.TPEx` 兩項。**
   - 第一次比對判定「`latest.json status` 不同」。逐項比對後確認，唯一差異是 `status.datasets` 多了兩個借券資料集（`health.SPECS` 新增項目的自然結果，其他項完全相同）。
   - 設計的比對工具漏了這一項。PG 加了 2 行剔除，並在檔頭註明「PG 補」。
   - `--keep-new` 時不剔除，所以反證仍然成立。
2. **新增 `logs/iter11_sql_check.py`**（唯讀）：把設計 9-3 的 SQL 寫成工具，方便 QA 重跑；沒有新增其他查詢。
3. **README 文字**由 PG 撰寫（設計第十節只列段落）。

除此之外，程式和附錄 C 完全相同。

---

## 四、給 QA 的提醒

- 選股「借券占股本 ≥ 5%」符合 150 檔、`screen.json` 原始 151 檔，請用 SQL 加共同排除（處置、今日無成交、股本變動）確認差的那 1 檔（PM F11-2 #4）。
- 公式不符的 4 列是官方資料本身（停止買賣），不是解析錯誤。
- **待上線確認**（需要使用者恢復每晚執行 `collect --catch-up`）：
  - 20:30 前的收集，借券顯示「尚未公布」。
  - 21:45 之後寫入當天資料。
  - 同一晚再執行時，不會再抓借券。
- `docs/iterations/README.md` 的「專案現況」還沒有更新借券的內容，建議在 QA 完成後一起更新。
