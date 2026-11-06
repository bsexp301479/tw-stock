# 第 10 輪｜Programmer：實作紀錄

- 撰寫日期：2026-11-06（週五）深夜
- 依據：
  - `03-design.md`：主要依據。第四節是實作順序與停止條件，第十三節是給 PG 的提醒，附錄 A～H 是預期值、原型差異、`test_iter10.py`、fixture、compare 與 recalc 工具。
  - `02-pm.md`：範圍與驗收。範圍變更紀錄最後幾筆：D17 = B、D18 = A，並接受 SA 的 14 點調整。
- 本輪項目：F10-1（季 EPS 收集、`check` 一行、個股季報卡）、F10-2（選股欄與條件、今日頁一行）、F10-3（第 9 輪收尾小修），**全部完成**，沒有用到延後順序。
- 程式來源：
  - 附錄 C、D、E 用程式從 `03-design.md` 取出，套到修改前的副本，結果和專案檔案**逐位元組相同**（13 個檔）。
  - 附錄 F-1、G、H 取出後和 `tests/test_iter10.py`、`logs/iter10_compare.py`、`logs/iter10_recalc.py` 逐字相同。
  - fixture 用附錄 F-2 的 `make_fixture.py`（放在 scratchpad，沒有放進專案）從 `r10/raw/`、`r10/sa/` 的原始回應重產，和 SA 的 `sa10/fixtures/` 4 檔完全相同（`diff -r` 無差異）。沒有手改。
  - 和設計不同的只有 README 的文字（設計第十節只列段落，文字由 PG 撰寫）。
- 守則：
  - 沒有 commit、push。
  - 沒有動 `.env`，也沒有讀出或印出帳密。沒有動、也沒有執行 `_archive/`。
  - 只執行允許的寫入：`backup`、`setup-db`（兩次）、`history --start 2024-01-01 --only financials`（含重跑一次）、`export`（改前、改後各一次）。另外執行了唯讀的 `check`（設計第四節步驟 6）。
  - 沒有執行 `collect`、`revenue`。對外請求只有補抓的 22 次，都經過 `fetch.request`；重跑 0 次。
  - 步驟 3（改程式）到步驟 4（`setup-db`）之間沒有執行 `export`、`check`、`collect`。
  - 沒有執行還原，沒有刪除既有備份。沒有安裝排程，沒有改系統或 Docker 設定。
  - 預覽用 8001 埠，結束時已關閉；8000 埠沒有動。

> **結論**
> - 備份 `TwStock_20261106_234606.bak`（85,909,504 B），早於任何程式修改。
> - 建表：`setup-db` 兩次都不報錯；既有 24 張表的列數前後完全相同，只多一列 `quarterly_financials`。
> - 補抓：22 次請求，耗時 64 秒，寫入 19,926 列；`first_seen` 全部 NULL；重跑「待抓 0 次」。
> - 匯出 18.5 → 18.9 秒（+0.4 秒，上限 +3 秒）。
> - compare「✅ 相同」；`--keep-new` 判定不同（1,988 處）。recalc「✅ 相同」。
> - PM 的數字驗收全部相符，只有 2408 近 4 季 EPS 52.86 超出 PM 估計 50.7 ±3%；依設計以 SQL 為準（第三節 3-2）。
> - `test_iter01`～`10` 全部通過。8001 預覽：主控台沒有程式錯誤；375 px 各頁 `scrollWidth` 都是 375。

---

## 一、修改的檔案與行數

專案沒有 git。行數用修改前的副本（scratchpad `pg10/orig/`）和修改後的檔案，以 `wc -l` 與 `diff` 計算。

| 檔案 | 內容 | 行數（改前 → 改後；+／−） |
|---|---|---|
| `twstock/collectors/financials.py`（新） | `parse_financials`、`fetch_financials`、`merge_financials`、`collect_financials` | 129 |
| `twstock/db.py` | 新表 `quarterly_financials`、setup 訊息 | 489 → 511（+23／−1） |
| `twstock/collectors/catchup.py` | `make_plan`、`plan_for_date` 排入季報；`execute_plan` 記 `financials_on`；`_undated_counts` | 336 → 347（+23／−12） |
| `twstock/collectors/history.py` | `fin_quarters`、`load_fin_have`、`run_financials`；`--only financials` | 123 → 173（+51／−1） |
| `twstock/collectors/daily.py` | F10-3：上市 `amount` 行情保護 | 867 → 868（+3／−2） |
| `twstock/health.py` | 窗口、截止日、`fin_done`、`financials_status`、`financial_counts`、`check_report(financials=)` | 457 → 546（+95／−6） |
| `twstock/export.py` | `fin_single`、`fin_yoy`、`fin_margin`、`fin_e4`、`fin_stock`、`fin_screen`、`fin_progress`、`_load_financials`；`fin`、`fqd`、`fin_progress` | 1,110 → 1,218（+114／−6） |
| `twstock/__main__.py` | docstring、`--only` 的 `choices` 與說明 | 256 → 258（+7／−5） |
| `site/stock.js` | F10-3 估值說明與淨值比卡日期；季報卡、獲利說明一行 | 454 → 487（+37／−4） |
| `site/app.js` | 選股欄、5 個條件、預設與參考組合、季別混雜、頁尾；今日頁一行 | 1,200 → 1,222（+30／−8） |
| `site/app.css` | 季報柱狀圖、獲利說明一行 | 217 → 225（+8） |
| `README.md` | 見下 | 156 → 165（+18／−9，多為長段落改寫） |
| `tests/test_iter03.py`、`tests/test_iter08.py` | 附錄 E | +3；+1／−1 |
| `tests/test_iter10.py`（新） | 附錄 F-1，20 個測試 | 370 |
| `tests/fixtures/`（新，4 檔） | mopsov 回應精簡版 | 74,898 B |
| `logs/iter10_compare.py`、`logs/iter10_recalc.py`（新，工具） | 附錄 G、H | 54、120 |

- 程式（含網站，不含測試、工具、README）+520／−45，淨增約 475 行。設計第〇節寫「約 +350 行」，但同一表各檔的原型行數加總也約 +480（`health.py` 設計寫 +81、實際 +95；`export.py` 設計寫 +96、實際 +114；`history.py` +44 → +51），程式內容和附錄逐位元組相同，差異只是設計估算時的計數。

### README、`__main__.py`（設計第十節）

- README：
  - 專案結構：`collectors/` 加 `financials` 季報；`site/` 加季報卡；`tests/` 加 `test_iter10.py`。
  - 安裝「新增資料表」：加第 10 輪的 `quarterly_financials`。
  - 日常使用：`collect --catch-up` 加「季報窗口內每天抓一次季報」；加 `history --start 2024-01-01 --only financials` 範例與說明；加 `python3 tests/test_iter10.py`。
  - 條件選股：預設改 8 組（加「財報優於去年」）、參考改 3 組（加「本益比低但 EPS 下滑」）；5 個季報條件；`screen.json` 新欄 `eq`、`ey`、`e4`、`gm`、`gmy`、`fq`、`eh`、`fqd`；季別混雜標示。
  - 今日頁估值位置卡：`fin_progress` 與季報一行。
  - 個股頁估值位置：拿掉「請一併看淨值比」，改寫為新說明；淨值比卡資料日。
  - 資料完整性：`check` 季報一行的 5 種狀態，ℹ️ 不計異常。
  - 新增「季報」注意事項（月營收之後）：資料來源、累計值與單季相減、窗口與截止日、收齊條件、每天最多 2 次、`financials_on`、`first_seen` 與補抓、`--no-revenue` 不影響、更正與已知限制、`stock_fundamentals.eps` 未使用、`stocks/{代號}.json` 的 `fin` 欄位、獲利說明一行的門檻與文字。
  - README 原本沒有「上市法人金額不受行情保護」的敘述，F10-3 不需要改 README。
- `__main__.py`：照附錄 C（docstring 的 `collect`、`collect --catch-up`、`export` 加季報、加 `history --only financials` 範例；`--only` 的 `choices` 加 `financials`，`test_iter05` 檢查的 `"margin", "holdings"]` 結尾保留）。沒有新子指令、新旗標。

---

## 二、各步驟的執行結果（台灣時間 2026-11-06）

### 步驟 0：備份

- 指令：`python3 -u -m twstock backup`，開始 23:46:06，耗時 7.1 秒。
- 輸出：`✅ 備份完成並通過 RESTORE VERIFYONLY：…/_backups/TwStock_20261106_234606.bak（81.9 MB）`
- 檔案大小 85,909,504 B，和前一次（11/05，85,716,992 B）同一數量級。
- 第一個程式修改（`daily.py`）在 23:46:57，晚於備份。

### 步驟 1：基線

- 舊程式 `python3 -u -m twstock export`：`⏱️ 匯出耗時 18.5 秒`（`time` 18.8 秒），紀錄 `logs/iter10_export_before.log`。
- `site/data/` 複製到 `logs/iter10_before/`（36 MB）。
- 既有表列數快照 `logs/iter10_rows_before.txt`（24 張表；例如 `stocks` 1,999、`daily_prices` 483,314、`monthly_revenue` 88,315）。
- `SELECT OBJECT_ID('quarterly_financials')` → NULL。

### 步驟 2：F10-3

- 改 `collectors/daily.py`（附錄 C 的 3 行）後 `test_iter01`～`09` 全部通過。`stock.js` 的淨值比卡與說明文字和 F10-1 一起在步驟 3 套上（同一個檔的同一段差異）。

### 步驟 3：程式與測試（只跑 mock）

- 套上附錄 C、D、E 全部差異，新增 `financials.py`、`test_iter10.py`、fixture 4 檔、`iter10_compare.py`、`iter10_recalc.py`。
- `test_iter01`～`10` 全部通過（每檔最後一行都是「全部通過」）。
- 115Q2 上市完整檔一行驗證（設計第十二節 #11，不連網、不連資料庫）：
  ```
  python3 -c "from twstock.collectors.financials import parse_financials as p; d=p(open('…/r10/raw/t163sb04_sii_115_02.html',encoding='utf-8').read()); import collections; print(len(d), collections.Counter(v['industry_tbl'] for v in d.values()))"
  1088 Counter({'ci': 1053, 'fh': 13, 'basi': 10, 'ins': 5, 'mim': 4, 'bd': 3})
  ```
  和 PM 驗收 F10-1 #3 相同（一般業 1,053、金控 13、銀行 10、保險 5、證券 3、其他 4）。

### 步驟 4：建表

- `python3 -u -m twstock setup-db` 兩次（23:47:36），兩次 rc=0，訊息都含 `quarterly_financials`，紀錄 `logs/iter10_setupdb.log`。
- `SELECT COUNT(*) FROM quarterly_financials` → 0。
- `sys.key_constraints`：`PK__quarterl__3213E83F21749F43`（PRIMARY_KEY）、`UQ_quarterly_financials`（UNIQUE）。
- 列數查詢存成 `logs/iter10_rows_after_ddl.txt`，和改前 `diff` 只差一行 `> quarterly_financials 0`。

### 步驟 5：補抓

- 指令：`python3 -u -m twstock history --start 2024-01-01 --only financials`，23:47:42 開始，23:48:46 結束，**64 秒**（預估 1.6 分鐘），rc=0。紀錄 `logs/iter10_history_financials.log`。
- 計畫：`📑 季報：待抓 22 次（季別 × 市場）`，符合預期。**22 次請求**，沒有封鎖、沒有欄位不符；沒有任何「略過 N 家（stocks 沒有）」。
- 每季每市場家數（SQL，`seen` = `first_seen` 不是 NULL 的列數）：

  | 季別 | 上市 | 上市金融業 | 上櫃 | 上櫃金融業 | seen |
  |---|---|---|---|---|---|
  | 2024Q1 | 1,026 | 31 | 832 | 7 | 0 |
  | 2024Q2 | 1,075 | 31 | 887 | 7 | 0 |
  | 2024Q3 | 1,043 | 31 | 846 | 7 | 0 |
  | 2024Q4 | 1,088 | 31 | 896 | 7 | 0 |
  | 2025Q1 | 1,060 | 31 | 870 | 7 | 0 |
  | 2025Q2 | 1,086 | 31 | 896 | 7 | 0 |
  | 2025Q3 | 1,080 | 31 | 887 | 7 | 0 |
  | 2025Q4 | 1,088 | 31 | 896 | 7 | 0 |
  | 2026Q1 | 1,086 | 31 | 896 | 7 | 0 |
  | 2026Q2 | **1,088** | **31** | **896** | **7** | 0 |
  | 2026Q3 | 231 | 1 | 173 | 2 | 0 |

  - 22 列；`seen` 全部 0。2026Q2 上市 1,088（金融業 31）、上櫃 896（金融業 7），2024Q1 上市 1,026，和設計相同。
  - 停止條件「任一季別 < 上一季 90%（115Q3 除外）」：最低的是 2024Q3 上櫃 846 ÷ 887 = 95%，沒有觸發。
  - 2024Q4、2025Q4、2026Q2 上市都是 1,088、上櫃都是 896，曾懷疑回應重複；以 SQL 確認同一家公司各季數值不同（例如 2408 累計 EPS 2024Q4 −1.64、2025Q4 2.13、2026Q2 23.38），是真實家數剛好相同。
- 2026Q2 上市業別：`ci` 1,053、`fh` 13、`basi` 10、`ins` 5、`bd` 3、`mim` 4（和設計相同）。
- **重跑一次**：`📑 季報：待抓 0 次`，0.28 秒，0 個請求（`logs/iter10_history_financials_rerun.log`）。
- 補抓後列數 `logs/iter10_rows_after_history.txt`：和改前 `diff` 只差 `> quarterly_financials 19926`，既有表都沒有變。

### 步驟 6：匯出、比對、重算、check

- `python3 -u -m twstock export`：`⏱️ 匯出耗時 18.9 秒`（`time` 19.2 秒），改前 18.5 秒，**+0.4 秒**（上限 +3 秒）。紀錄 `logs/iter10_export_after.log`。
- `python3 logs/iter10_compare.py logs/iter10_before site/data`（`logs/iter10_compare.log`）：
  ```
  ℹ️  新鍵大小：stocks 的 fin 1986 檔共 699 KB；screen.json 新欄 66.8 KB；latest.json fin_progress 69 B
  ✅ 相同
  ```
  - `--keep-new`（反證）：`❌ 不同 1988 處`（`logs/iter10_compare_keepnew.log`）。
- 大小：

  | 項目 | 改前 | 改後 | 增加 | 上限 |
  |---|---|---|---|---|
  | `stocks/` 實際位元組 | 32,465,695 | 33,181,018 | +715,323 B（約 699 KB） | 1 MB |
  | `screen.json` | 253,337 | 321,760 | +68,423 B（66.8 KB） | 70 KB（SA 第十二節 #2） |
  | `latest.json` | 731,281 | 731,366 | +85 B | 1 KB |

- `python3 logs/iter10_recalc.py`（`logs/iter10_recalc.log`）：
  ```
  比對 stocks 的 fin 1986 檔、screen 1983 檔（有季報 1979 檔）
  單季 EPS 年增 ≥ 0%：823 檔
  單季 EPS 年增 ≥ 20%：694 檔
  單季 EPS 年增 ≥ 50%：556 檔
  ✅ 相同
  ```
- `python3 -m twstock check`（唯讀，`logs/iter10_check.log`）：rc=0，`結果：無異常`；季報一行：
  ```
  第 3 季財報 2026Q3：已收 404 家（前一季 1,984 家的 20%），金融業 3／38 家，⏳ 公布期間（一般業 11/14、金融業 11/29 截止）
  ```
  404 = 231 + 173，等於步驟 5 SQL 的當季合計。
- `latest.json` 的 `fin_progress`：`{"q": 202603, "n": {"TWSE": 231, "TPEx": 173}, "p": {"TWSE": 1088, "TPEx": 896}}`，和 SQL 分市場 `COUNT(*)` 相同。
- `screen.json` 的 `fqd`：`{"202603": 404, "202602": 1575}`。

### 驗收數字（以真實資料 SQL 重算）

設計第九節 9-3 #2 的 SQL（紀錄 `logs/iter10_sql_numbers.txt`、`logs/iter10_sql_e4.txt`）。近 4 季、一年前近 4 季用 9-3 的 JOIN 公式，年增用 SQL 相減的單季值計算。

| 股票 | 115Q2 累計 | 115Q3 累計 | Q3 單季 EPS | 去年同季單季 | 單季年增（SQL） | Q3 單季毛利率 | 毛利率年增 | 近 4 季 | 一年前近 4 季 | 匯出 JSON |
|---|---|---|---|---|---|---|---|---|---|---|
| 南亞科 2408 | 23.38 | 49.28 | **25.90** | 0.50 | +5,080.0% | **85.7%** | +67.2 點 | **52.86** | **−1.96** | 相同 |
| 聯電 2303 | 4.68 | 6.00 | **1.32** | 1.20 | +10.0% | **34.0%** | +4.2 點 | **6.80** | **3.22** | 相同 |
| 台光電 2383 | 42.46 | 82.92 | **40.46** | 11.20 | +261.25%（JSON 261.3） | **37.7%** | +7.6 點 | 93.36 | 38.90 | 相同 |
| 大立光 3008 | 82.35 | 121.98 | **39.63** | 53.05 | −25.3% | **42.2%** | −5.0 點 | 172.33 | 174.07 | 相同 |
| 卜蜂 1215 | 3.24 | 5.47 | 2.23 | 2.99 | −25.4% | 19.2% | −3.0 點 | 7.92 | 10.22 | 相同 |
| 台積電 2330 | 49.33 | 未公布 | 最新一季 Q2：27.25 | 15.36 | +77.4% | Q2 67.7% | +9.1 點 | 86.28 | 56.31 | 相同 |
| 富邦金 2881 | 6.67 | 未公布 | 最新一季 Q2：4.27 | 0.49 | +771.4% | 無（`gm` null） | null | 11.55 | 8.29 | 相同 |
| 中華電 2412 | 2.68 | 未公布 | 最新一季 Q2：1.38 | 1.31 | +5.3% | Q2 37.5% | −0.9 點 | 5.10 | 4.89 | 相同 |

- **卜蜂 1215 Q3 單季營收 7,464,783 千元** = 21,866,426 − 14,401,643，SQL `monthly_revenue` 7～9 月合計也是 **7,464,783**。
- 台光電年增：(40.46 − 11.20) ÷ 11.20 = 261.25%，匯出用 `ROUND_HALF_UP` 得 261.3（設計 1-8）；Python `round` 會得 261.2，這正是設計要避免的情況。
- PM 參考值的比較：
  - 2303 近 4 季 6.80（PM 約 6.77，+0.4%）、一年前 3.22（PM 約 3.20，+0.6%），在 ±3% 內。
  - **2408 近 4 季 52.86，PM 估約 50.7（343.5 ÷ 6.77），差 +4.3%，超出 ±3%**；一年前 −1.96 ≤ 0 符合。PM 的值是由官方本益比反推，官方本益比使用的 EPS 口徑不一定和「累計相減」相同；依 PM 驗收 F10-1 #5 與設計 9-3 #2「不同時以 SQL 為準」，`stocks/2408.json` 的 `e4`、`e4p` 等於 SQL 值，判定相符。交給 QA 確認。
- 中華電 2412：5.10 < 1.5 × 4.89 = 7.34，不出現獲利說明一行（畫面已確認）。
- 南亞科 2408 去年同季單季 0.50 > 0，所以單季年增有值（+5,080.0%）；累計年增 null（去年 1～9 月累計 −1.45 ≤ 0，畫面寫 `--`）。

---

## 三、與設計不同的地方

- **程式、測試、工具、fixture：沒有差異**（逐位元組比對，見開頭）。
- README 文字由 PG 依第十節撰寫（設計只列段落）。
- 步驟 2 只先改 `daily.py`；`stock.js` 的 F10-3 部分和 F10-1 在同一段差異內，於步驟 3 一起套上。最終結果相同。
- 行數比設計第〇節的總計多（見第一節說明），是設計估算的計數差異，內容相同。
- 沒有延後任何項目。

---

## 四、畫面檢查（8001，正式資料；結束時已關閉）

- 指令：`python3 -m twstock serve --port 8001 --no-browser`；用 Claude 內建瀏覽器開 `http://localhost:8001`，以 375 × 812 檢查，每頁量 `document.documentElement.scrollWidth`。結束時停止伺服器，確認 8001 沒有在監聽。

| 頁面 | 結果 |
|---|---|
| `#/stock/2408` | 季報卡「2026 Q3｜一般業」：單季 EPS 25.90（年增 +5,080.0%）、累計 49.28（1～9 月，年增 --）、毛利率 85.7%（去年同季 18.5%）、營益率 80.0%、近 4 季 52.86（一年前 −1.96）；柱狀圖 8 季 24Q4～26Q3；口徑說明含「補抓的季別不顯示」。獲利說明一行「近 4 季 EPS 一年前 -1.96 元 → 現在 52.86 元（轉盈）：…位置低不代表股價便宜…」。估值說明含「獲利大增」「不代表股價便宜」與「請對照下方季報卡…」。本益比、淨值比、殖利率三張卡都有「資料 11/06」。scrollWidth 375 |
| `#/stock/2303` | 季報卡 Q3：1.32（+10.0%）、毛利率 34.0%、近 4 季 6.80（一年前 3.22）；獲利說明一行「（2.1 倍）」。375 |
| `#/stock/2330` | 季報卡「2026 Q2」（最新一季是 Q2）：27.25（+77.4%）、1～6 月 49.33、毛利率 67.7%、近 4 季 86.28（一年前 56.31）；86.28 ≥ 1.5 × 56.31 = 84.47，所以出現獲利說明一行「（1.5 倍）」。375 |
| `#/stock/2881` | 季報卡「2026 Q2｜金控」：沒有毛利率卡、沒有營益率卡；EPS 4.27、累計 6.67、近 4 季 11.55；沒有獲利說明一行。375 |
| `#/stock/2412` | 季報卡 Q2；沒有獲利說明一行。375 |
| `#/stock/6806`（沒有季報的股票） | 沒有季報卡、沒有獲利說明一行，不報錯。375 |
| `#/stock/5314` | 本益比、殖利率卡有「08/14 除權，官方值可能尚未調整」；淨值比卡只有「資料 11/06」。 |
| `#/rank/screen` | 資料日一行「…｜季報 Q3 404 檔、Q2 1,575 檔（財報公布期間，各股季別不同）」；預設 8 組（含「財報優於去年」）、參考 3 組（含「本益比低但 EPS 下滑」）；頁尾有季報口徑說明。375 |
| `#/rank/screen?tv=0.5&ey=20&gmy=0`（財報優於去年） | 符合 241 檔；欄名「單季EPS（Q2）」「EPS年增（Q2）」「毛利率」「毛利率年增」；Q3 的列加小字，例如「台光電 2383 … 40.46（Q3） +261.30%（Q3） 37.7% +7.6點」；網址帶條件可還原。375 |
| 今日頁 `#/` | 估值位置卡下方「第 3 季財報已收：上市 231、上櫃 173 家（前一季 1,088、896 家）；本益比中位數會隨 EPS 更新而變動」。375 |

- 主控台：只有 1 則 `404`，是我測試時開了 `#/stock/0050`（ETF 不在 `stocks/`，本輪之前就是這樣），**沒有程式錯誤**。
- 沒有逐一點選畫面上的新條件下拉與開關、「重設」、「複製條件連結」（以網址帶條件確認可還原；新條件的 hash 寫入與重設由既有共用程式處理）。季別混雜的 mock `screen.json`（`fqd = {"202603":300,"202602":1600}`）沒有在畫面上測，交給 QA（設計 9-3 #6）。

---

## 五、測試結果

```
for f in tests/test_iter*.py; do python3 $f; done
```

| 檔案 | 結果 |
|---|---|
| `test_iter01`～`test_iter09` | 全部通過（`test_iter03`、`test_iter08` 依附錄 E 修改） |
| `test_iter10`（新，20 個測試） | 全部通過 |

紀錄 `logs/iter10_tests.log`。

---

## 六、給 QA 的提醒

1. 2408 近 4 季 EPS 52.86 超出 PM 估計 ±3%，依設計以 SQL 為準（見第二節）。
2. 補抓的列 `first_seen` 全部是 NULL，所以畫面目前都不會出現「本站收錄」；要等使用者恢復每晚 `collect --catch-up` 後，新公布的公司才會有。
3. 115Q3 是 11/06 23:48 補抓當下的資料（上市 231、上櫃 173 家）；QA 時若使用者還沒恢復收集，數字不會變。
4. D18 = A：**QA 完成前請使用者不要恢復 `collect --catch-up`**。
5. 本輪新增的工具與紀錄：`logs/iter10_compare.py`、`logs/iter10_recalc.py`、`logs/iter10_before/`、`logs/iter10_rows_*.txt`、`logs/iter10_*.log`、`logs/iter10_sql_*.txt`。
