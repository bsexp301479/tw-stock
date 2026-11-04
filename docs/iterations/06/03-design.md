# 第 06 輪｜System Analyst：設計文件

- 撰寫日期：2026-11-04（週三）晚間
- 輸入：
  - `02-pm.md` 的本輪範圍：F6-1、F6-2、S9，編號沿用 PM。
  - 另參考 `01-analyst.md`（QA-01 根因、判斷規則表）與第 5 輪 `03-design.md`（格式比照）。
  - 使用者決定：QA-01 第一優先、QA-02 一併處理、**D11 = 加 S9 `backup`**、「進 SA」。
- 依據：
  - 閱讀了 `twstock/{__main__,config,db,health,tradingcal}.py`、`collectors/{holdings,daily,history,catchup}.py`、`tests/test_iter03.py`（`World`）、`tests/test_iter05.py`、README、`docker-compose.yml`、`.env.example`。
  - 資料庫只做唯讀查詢，沒有執行 `setup-db`。唯一的寫入動作是 `BACKUP … COPY_ONLY`，寫到 scratchpad（S9 實測），不影響備份鏈。
  - **沒有發出外部請求**（0 次）。改用分析師 11/04 21:05 保存的 6 份完整 `GetPCF` 回應，加上第 5 輪 PG 診斷的 10/21 回應形狀。
- **所有設計都已在專案外、不含 `.env` 的暫存副本做成原型並實際跑過**：
  - 測試：`test_iter01`～`test_iter06` 全部通過。`test_iter06.py` 有 16 個測試。
    - 另外做了 4 個「突變」反證：分別拿掉 `today ≥ post`、A 的 `PostDate` 比對、寫明細時刪 gap、B 的金額檢查。每一個都會讓 `test_iter06` 失敗。
  - **8 個已知日期（唯讀模擬，附錄 B-1）**：
    - 用真實資料庫的缺漏清單、6 份真實回應與 10/21 的回應形狀，跑原型的 `parse_pcf`，8 筆全部判成正確的 A／B。
    - 把結果注入原型的 `check`：rc=0。注入 `history --start 2025-10-30 --only holdings`：「待抓 0 天」，外部請求 0 次。
  - **隔離（F6-1 驗收 #6）**：同一份資料庫，用原型加上注入的 8 筆 gap 匯出，再以新的 `logs/iter06_compare.py` 和正式網站 11/04 21:04 的匯出比對。結果「✅ 相同」：`latest.json`、`stocks` 1,999 檔、`etfs` 4 檔都相同。
    - 反例：改 `breadth`、`status.collected_src`、`etfs/00988A.json` 各一處，工具回報 3 處並列出鍵名，rc=1（F6-2 驗收 #2）。
  - **S9 實測**：原型的 `backup --out <scratchpad>` 成功，`TwStock_20261104_2117.bak`（之後改成檔名到秒，見發現 3）。
    - 大小 83,398,656 B（79.5 MB），耗時 5.7 秒。
    - `msdb.dbo.backupset` 的 `is_copy_only = 1`，`RESTORE VERIFYONLY` 通過。
    - 容器內的暫存檔已刪除。容器內與 `../_backups/` 原有的 3 份備份，大小與時間都不變。
    - 改成檔名到秒後，連跑兩次產生 `…_212601.bak`、`…_212607.bak`，都是 rc=0。
  - **專案程式、資料庫內容、排程都沒有修改。**
- 本文件只描述設計：
  - 附錄 C 是原型對現有程式的完整 diff，附錄 D 是完整的 `tests/test_iter06.py`，附錄 E 是 PG 用的 `logs/iter06_compare.py`，**都可以直接套用**。
  - 寫法可以改，但**函式名稱、資料表、判斷式、輸出訊息請照本文件**，`test_iter06.py` 與 QA 會照著驗。

> **影響設計的實測發現（PM 文件沒有預期到）**
> 1. **情況 A 的回應就是「前一份清單」，已逐筆證實。**
>    - 5 份 A 回應的明細列數（52、38、46、47、36）與資料庫中 `src_date` 那天已存的筆數完全相同（附錄 B-1）。
>    - 所以把 A 記成「這天沒有清單」、不複製明細，是正確的（PM 禁止複製）。
> 2. **情況 B 有「公布當晚還沒寫完明細」的可能，不能和真正的 B 區分。**
>    - 7/8 的 B 回應是事後查的。實際收集時，投信可能先寫 `NAV`、稍後才寫明細。
>    - 對策：**B 只在「今天 ≥ 要求的生效日」時成立**；在這之前一律當成「尚未公布」，下一次收集會再查。
>    - 代價：臺股臨時休市前一日的那一晚（例如 10/21 晚上），`check` 會照第 5 輪規則顯示「尚未公布」，22:00 後顯示異常。到生效日的收集時改記 B，異常消失。這種情況一年約 1～2 次，可以接受（第八節）。
>    - A 不受影響：A 的回應是完整的清單，持股日卻不同，沒有「還沒寫完」的問題，所以收到就記。11/26 感恩節在 11/27 17:30 收集時就會記成 A，**不會出現異常**（mock 1）。
> 3. **PM S9 驗收 #2「立刻再執行一次會產生另一個檔名」，檔名要到秒。**
>    - PM 的範例 `TwStock_20261104_2130.bak` 只到分，一分鐘內重跑會撞名。
>    - 本設計改成 `TwStock_YYYYMMDD_HHMMSS.bak`。一次備份約 6 秒，所以連續執行一定不同名；同名時照樣報錯、不覆寫。
> 4. **8 個已知日期用「重抓」處理，正好 8 次請求**（不是 PM 估計的 ≤ 10 次）：`history` 只請求缺的「檔 × 日」。
>    - 不選離線標記的原因：10/21 兩筆沒有保存原始回應，離線標記需要另寫一支直接寫資料庫的腳本；重抓則走的是正式程式的路徑。
> 5. **`history` 處理這 8 天時，結尾的「ℹ️ 無資料（…）」會列出這 8 天**，因為它們沒有寫入明細。
>    - 但逐日訊息會清楚標示「來源無持股明細（不算缺）」，重跑則是「待抓 0 天」。
>    - 這是既有訊息的措辭問題，不影響判斷，本輪不改（第八節）。

---

## 〇、變更總覽

### 檔案 × 項目對照表

| 檔案 | F6-1 來源無明細不算缺 | F6-2 比對工具 | S9 backup |
|---|---|---|---|
| `twstock/db.py` | 新表 `etf_holding_gaps`；`setup_database` 的列表 | | |
| `twstock/collectors/holdings.py` | `Gap`、`GAP_REASON`、`parse_pcf(data, d, post=None, today=None)`、`fetch_holdings` 傳入生效日與今天、`merge_holdings` 一併刪 gap、`merge_gap`；docstring | | |
| `twstock/collectors/daily.py` | `_collect_key` 持股分支記 gap；`collect_for_date` 的「官方尚無資料」排除 gap，另印一行 | | |
| `twstock/health.py` | `Row` 加 `gap`；`load_snapshot` 讀 gap；`assess` 遇 gap 為齊全；`check_report` 的涵蓋數與「不算缺」一行 | | |
| `twstock/backup.py`（新檔） | | | `BACKUP_DIR`、`find_container`、`backup`、`run` |
| `twstock/__main__.py` | | | `cmd_backup`、子指令 `backup --out --direct`、docstring |
| `logs/iter06_compare.py`（新檔，不進版本控制） | | 附錄 E | |
| `tests/test_iter06.py`（新檔） | 附錄 D | 同左 | 同左 |
| `README.md`、`.env.example` | 第七節 | | 第七節 |

**不需要修改**：`history.py`、`catchup.py`（都透過 `load_snapshot`、`missing_keys`、`assess` 自動略過 gap）、`export.py`、`site/`（不讀 gap 表；隔離已驗證）、`tests/test_iter01～05.py`（`test_iter06` 以 `World` 子類別擴充，不改 `test_iter03`）。

**工作量**：

| 項目 | 程式 | 測試 |
|---|---|---|
| 新增（附錄 C） | 185 行（含新檔 `backup.py` 92 行） | `test_iter06.py` 485 行 |
| 刪改 | 11 行 | 0 |
| 工具、README、`.env.example` | `iter06_compare.py` 46 行；README 約 20 行；`.env.example` 2 行 | — |

- 合計約 750 行。程式約 250 行，和 PM 估計的 210 行相近。測試比 PM 估計的 190 行多出約 300 行。
- 多出的部分是 6 個流程情境（mock 1～4、S9 的 docker／資料庫情境）。每個情境都用假的 HTTP、資料庫與 docker 跑完整路徑，不影響時程。
- **不需要刪減範圍**。

### 建議實作順序

| 步驟 | 內容 | 驗證 |
|---|---|---|
| 0 | 套用附錄 C 的 `twstock/backup.py` 與 `__main__.py`（只有這兩檔），再執行 `python3 -m twstock backup 2>&1 \| tee logs/iter06_backup.log; echo rc=$?` | **S9 #1、#7**：`../_backups/TwStock_2026…bak` 大於 75 MB，印出「✅ 備份完成並通過 RESTORE VERIFYONLY」，rc=0；既有 3 份大小與時間不變（附錄 B-4） |
| 1 | **隔離基線**（舊的匯出邏輯）：`python3 -m twstock export`，接著 `mkdir -p logs/iter06_before && cp site/data/latest.json logs/iter06_before/ && cp -R site/data/stocks site/data/etfs logs/iter06_before/` | 檔案存在 |
| 2 | **check 基線**：`python3 -m twstock check 2>&1 \| tee logs/iter06_check_before.log; echo rc=$?` | rc=1，只有 00411A、00988A 的 10/21 |
| 3 | 套用其餘程式（`db.py`、`holdings.py`、`daily.py`、`health.py`）→ `python3 -m twstock setup-db` 執行兩次 | 兩次都不報錯；`etf_holding_gaps` 存在且是空的；既有表筆數不變（附錄 B-3） |
| 4 | 套用 `tests/test_iter06.py`、附錄 E 的 `logs/iter06_compare.py`；`.env.example` | `test_iter01`～`06` 全過 |
| 5 | **標記 8 個已知日期**：`python3 -m twstock history --start 2025-10-30 --only holdings 2>&1 \| tee logs/iter06_history.log` | 「待抓 7 天」（10/21 一天 2 檔）、共 8 次 `GetPCF`；逐日出現「ℹ️  來源無持股明細（不算缺）」（第一節 F6-1-6） |
| 6 | 同一指令再跑一次 | **F6-1 #2**：「待抓 0 天」，0 次請求 |
| 7 | `python3 -m twstock check 2>&1 \| tee logs/iter06_check_after.log; echo rc=$?`；附錄 B-1、B-2 的 SQL | **F6-1 #1、#4**：rc=0；8 列原因正確；這 8 天沒有明細 |
| 8 | `python3 -m twstock collect --catch-up`（資料齊全時） | **F6-1 #3**：不發 `GetPCF`。若當天新資料已公布，只發當天 4 檔的 `GetPCF` |
| 9 | **隔離比對**：`python3 -m twstock export && python3 logs/iter06_compare.py logs/iter06_before site/data` | **F6-1 #6、F6-2 #1**：「✅ 相同」。步驟 8 若寫入新資料，資料日會不同，見第八節 |
| 10 | S9 其餘驗收：連跑兩次 `backup --out /tmp/…`（或任一暫存資料夾）、附錄 B-4 SQL | S9 #2、#3、#6 |
| 11 | README、`.env.example`（第七節） | 第七節清單 |

> - **步驟 0 一定要在改表之前**（PM 相依性）。只套用 `backup.py`、`__main__.py` 時，其他程式還是舊的，可以正常執行。
> - 步驟 1 到步驟 9 之間，除了步驟 5～6 的 `history` 與步驟 8 的 `collect --catch-up`，不要執行其他收集。
> - 如果步驟 8 有寫入 11/05 的新資料（例如在隔天 17:30 後執行），步驟 9 的資料日會不同，必然判定「不同」。這時請改在步驟 8 之前先做步驟 9，或把步驟 8 移到最後。

---

## F6-1. 來源無持股清單／無明細不算缺（優先 1，QA-01）

### F6-1-1 對應驗收條件

| PM 驗收 | 設計 | 測試／驗證 |
|---|---|---|
| #1 check rc=0；8 天有紀錄且原因正確 | `etf_holding_gaps` 表；`assess` 遇 gap 為齊全 | 附錄 B-1 SQL；唯讀模擬 rc=0 |
| #2 history 重跑待抓 0 天、0 請求 | `missing_keys` → `assess` 自動略過 | `test_f61_m2_typhoon_history`；唯讀模擬 |
| #3 catch-up 齊全時持股 0 請求 | 同上 | `test_f61_m1_thanksgiving`、`test_f61_m2_typhoon_history` |
| #4 這 8 天沒有明細；前後持股日筆數不變 | gap 只寫 `etf_holding_gaps`，不碰 `etf_holdings`／`etf_holding_summary` | 附錄 B-2、B-3 |
| #5 mock 1～6 | 第 F6-1-5 節 | `test_iter06.py` |
| #6 網站隔離 | `export.py` 不讀 gap 表 | 唯讀模擬「✅ 相同」 |
| #7 README | 第七節 | QA 核對 |

### F6-1-2 判斷規則（`holdings.parse_pcf`，附錄 C）

`parse_pcf(data, d, post=None, today=None)`：

- `d` 是要求的持股日。
- `post` 是要求的生效日，也就是請求參數 `date` 換成西元。
- `today` 是執行當天，由 `fetch_holdings` 傳入 `date.today()`。

依序判斷：

| # | 條件 | 結果 | 真實回應的關鍵欄位 |
|---|---|---|---|
| 0 | 不是 dict，或缺 `pcf`／`asset` | `SchemaError`（第 5 輪） | — |
| 1 | `asset` 為空，**且** `NAV` 存在、`NAV.Amount` > 0、`NAV.TranDate` = d、`NAV.PostDate` = post、`today ≥ post` | **`Gap("B", d, post, NAV.Amount)`** | 00988A 7/8：`TranDate /Date(1783440000000)/`（07/08）、`PostDate /Date(1783872000000)/`（07/13）、`Amount 59853545462`、`asset []` |
| 2 | `asset` 為空（其他情況） | `None`：尚未公布（第 5 輪） | 尚未公布：`TranDate`、`PostDate` 都是 `/Date(-62135596800000)/`（西元 1 年），`Amount 0` |
| 3 | 沒有 `NAV` | `SchemaError`（第 5 輪） | — |
| 4 | `NAV.TranDate` ≠ d，**且** `NAV.PostDate` = post | **`Gap("A", NAV.TranDate, post, None)`** | 00988A 2025-11-27 → 參數 `114/12/01`：`TranDate` 11/26、`PostDate` 12/01，明細 52 列 |
| 5 | `NAV.TranDate` ≠ d（其他情況） | `None`：不寫入（第 5 輪；例如 `PostDate` 也不同的舊清單） | — |
| 6 | 其他 | `(彙總, 明細列)`：寫入（第 5 輪，不變） | — |

- **A' 也落在 #4**：00988A 2/10 → 參數 `115/02/23`，回應 `TranDate` 是 02/11，比要求日晚。`src_date` 記 02/11，那天的明細已另外存好（46 列）。
- **不給 `post` 時**（第 5 輪的呼叫方式），永遠不會回傳 `Gap`，行為和第 5 輪完全相同。`test_iter05` 不需要修改。
- **「尚未公布」不會落入 A 或 B**（PM 風險 1）：
  - 它的 `PostDate` 是西元 1 年，不會等於 post，所以進不了 #4。
  - 它的 `Amount` 是 0、`TranDate` 也不等於 d，所以進不了 #1。
  - 測試以第 5 輪的真實格式 `PCF_EMPTY` 驗證，另外加上 `pcf` 為空的版本。
- **「回應前一持股日、生效日也不同」**（第 5 輪 `_stale` 情境）落在 #5，維持「尚未公布」（mock 4）。
- **規則不限跨境 ETF**：國內 ETF 遇到 B 一樣成立（`test_f61_parse_unpublished_and_normal`、mock 3）。

`Gap = namedtuple("Gap", "reason src_date post_date nav")`

`GAP_REASON = {"A": "投信當日無持股清單", "B": "投信只公布彙總、沒有明細"}`

### F6-1-3 紀錄方式：另建表 `etf_holding_gaps`（附錄 C 的 `db.py`）

```sql
CREATE TABLE etf_holding_gaps (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
    hold_date   DATE           NOT NULL,
    reason      CHAR(1)        NOT NULL CHECK (reason IN ('A','B')),
    src_date    DATE           NOT NULL,  -- 回應的持股日（A 為前一個海外交易日；B 等於 hold_date）
    post_date   DATE           NOT NULL,  -- 清單生效日（請求參數）
    nav         DECIMAL(20,2)  NULL,      -- B 的彙總淨資產（元）
    created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
    CONSTRAINT UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)
)
```

**比較（PM 第五節第 2 點）**：

| 做法 | 優點 | 缺點 | 結論 |
|---|---|---|---|
| `etf_holding_summary` 加 `gap_reason` 欄位，寫一列只有彙總的資料 | 少一張表 | `export._load_holdings`、`holding_table` 以 summary 的日期當持股日序列。gap 列會變成「有日期、沒有明細」，1 日增減會拿它當基準而算錯，`n_stocks` 等 NOT NULL 欄位也沒有值可填。要改 `export.py`，隔離就不成立 | 不採用 |
| **另建 `etf_holding_gaps`** | `export.py`、網站完全不動（隔離已驗證）；之後拿到明細也容易清掉 | 多一張表 | **採用** |

- **寫入**：`merge_gap(cursor, code, d, gap)` 以 MERGE 寫入，可以重複執行。`etfs` 沒有這檔時回傳 False，和 `merge_holdings` 相同。
- **之後真的拿到明細**（例如投信補發）：`merge_holdings` 寫明細前，會先執行 `DELETE FROM etf_holding_gaps WHERE etf_id = ? AND hold_date = ?`，不會同時有明細又有 gap。
- **不複製前一天的明細**（PM 禁止）：gap 只寫在 `etf_holding_gaps`。

### F6-1-4 讀取與略過（`health.py`、`daily.py`）

- `Row = namedtuple("Row", "n pe pb dy gap", defaults=(0, 0, 0, 0, None))`
- **`load_snapshot`** 多一個查詢：

  ```sql
  SELECT g.hold_date, e.etf_code, g.reason FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id
  WHERE g.hold_date BETWEEN ? AND ?
  ```

  查到的結果以 `snap["holdings.代號"].setdefault(d, Row(gap=reason))` 放入：已經有明細的日期以明細為準。
- **`assess`**：`row.gap` 有值時回傳 None（齊全）。所以以下函式都自動把 gap 當成齊全，**不必修改**：
  - `evaluate`、`missing_keys`：`history` 與 `--catch-up` 的待抓清單。
  - `dataset_status`：網站狀態。
  - `all_missing_days`。
- **`medians`** 本來就只取 `n > 0` 的日期，gap 的 0 不會拉低中位數（`test_f61_health`）。
- **`_collect_key`**（`daily.py`）：`fetch_holdings` 回傳 `Gap` 時：
  - 呼叫 `_save(merge_gap, …)` 寫入。
  - 記到 `cache["gaps"]`。
  - 回傳 0，表示沒有寫入明細列。
- **`collect_for_date`**：
  - 「官方尚無資料」那一行排除 gap。
  - 另外印一行：`  ℹ️  來源無持股明細（不算缺）：holdings.00411A（投信當日無持股清單）、holdings.00988A（投信當日無持股清單）`

### F6-1-5 邊界情況與 mock（PM #5，`test_iter06.py`）

| # | 情境 | 預期 | 測試 |
|---|---|---|---|
| 1 | 情況 A，用 5 份真實回應的片段 | `Gap("A", 回應持股日, 生效日, None)`；生效日對不上或沒給生效日時為 None | `test_f61_parse_a` |
| 1 流程 | **2026-11-26 感恩節**：11/27 17:30 `--catch-up` | rc=0，印「來源無持股明細（不算缺）：holdings.00411A（投信當日無持股清單）、holdings.00988A（…）」，不印「官方尚無資料」或「缺」；`etf_holding_gaps` 寫入 `("A", 11/25, 11/30, None)`；22:30 重跑 rc=0，不通知，`GetPCF` 0 次 | `test_f61_m1_thanksgiving` |
| 2 | 情況 B，用 00988A 7/8 真實回應 | 生效日當天或之後：`Gap("B", 7/8, 7/13, 59853545462)`；生效日前、持股日不同、生效日不同、金額 0：None | `test_f61_parse_b` |
| 2 流程 | 10/21 兩檔以 `history` 重抓 | 2 次請求、記 B；重跑「待抓 0 天」0 次；`--catch-up` 也 0 次 | `test_f61_m2_typhoon_history` |
| 3 | 尚未公布（西元 1 年、金額 0） | None，給了生效日也一樣 | `test_f61_parse_unpublished_and_normal` |
| 3 流程 | 回應前一持股日、生效日也不同（第 5 輪 `_stale`） | 22:30 rc=1「❌ 00981A持股：缺 2026-11-04」，不記 gap，與第 5 輪相同 | `test_f61_m4_unpublished_unchanged` |
| 4 | 已公布、有明細 | 與第 5 輪相同；`test_iter05` 全過 | `test_f61_parse_unpublished_and_normal`、`test_iter05` |
| 5 | 國內 ETF 遇到 B | 解析成 `Gap("B", …)`；流程中 11/04 晚上（生效日前）為「⏳ 尚未公布」，11/05 收集時記 B、rc=0、不通知 | `test_f61_parse_unpublished_and_normal`、`test_f61_m3_b_before_post` |
| 6 | 回應欄位不符 | 仍是 `SchemaError`／`PARSE_ERRORS`，只影響該檔（第 5 輪 `test_e2_m4` 照常通過） | `test_f61_parse_unpublished_and_normal` |
| — | 寫明細時刪除 gap；`etfs` 沒有該檔 | `DELETE FROM etf_holding_gaps …` 有執行；`merge_gap` 回傳 False | `test_f61_merge` |
| — | `check` 呈現、網站狀態 | 見 F6-1-6 | `test_f61_health` |

### F6-1-6 `check` 與網站呈現

- **`check`**（PM 第五節第 4 點）：採用「正常，另列一行」。
  - **涵蓋**欄把 gap 算進去，例如 `00988A持股  19/19`。
  - 表格下方另列一行。這一行**只在 20 日視窗內有 gap 時**出現：
    ```
    ℹ️  投信沒有持股明細（不算缺）：00411A持股 2026-10-21（只有彙總）、00988A持股 2026-10-21（只有彙總）
    ```
  - rc 不受影響。唯讀模擬時，11/04 23:00 是 rc=0，「結果：無異常」。
- **網站**：
  - `dataset_status` 把 gap 視為齊全，最新持股日的狀態是 `ok`。
  - 持股頁、個股卡的數字不變（隔離已驗證）。
  - **SA 決定不加註「某日海外休市」的文字**（PM 讓 SA 判斷）。理由：
    - 1 日增減本來就以前一個有明細的持股日為準。
    - 加文字要改 `export.py` 與 `app.js`，隔離就不成立，也增加 11/26 前上線的風險。
    - 留在待辦（第八節）。

### F6-1-7 8 個已知日期的處理（PM 第五節第 3 點）

- **重抓**：`python3 -m twstock history --start 2025-10-30 --only holdings`（建議順序步驟 5）。
  - 只請求缺的「檔 × 日」，**共 8 次 `GetPCF`**，每次間隔 3 秒，約 30 秒。
  - 外部請求一律經過 `fetch.request`，有節流。
- 預期 8 列見附錄 B-1。00988A 10/21 的 `nav` 以 PG 實際取得的值為準：SA 沒有那份回應，只要求 > 0。
- 執行期間逐日印「ℹ️  來源無持股明細（不算缺）」。結尾的「ℹ️ 無資料（…）」也會列出這 8 天（發現 5），屬於預期現象。

---

## F6-2. 隔離比對工具（優先 1，QA-02）

- **新檔 `logs/iter06_compare.py`**（附錄 E，`logs/` 不進版本控制）：取代 `iter05_compare.py`。
- 用法：`python3 logs/iter06_compare.py 基線資料夾 site/data`
- 規則：
  - 比對 `latest.json`、`stocks/*.json`、**`etfs/*.json`**。
  - 略過 `updated_at`、`status.exported_at`、`status.collected_at`。其他鍵（包括 `status.collected_src`、`status.datasets`）都要相同。
  - `NEW_LATEST`、`NEW_STOCK`、`NEW_STATUS` 是之後各輪排除新增鍵用的；本輪都是空集合。
  - 輸出：相同時印「✅ 相同」，rc=0；不同時印「❌ 不同 N 處：鍵名或檔名…」，rc=1（最多列 20 處）。
- 驗收：

| PM 驗收 | 驗證 |
|---|---|
| #1 中間有 `collect --catch-up` 仍判定相同 | 第 5 輪 QA-02 的原因是 `updated_at`、`collected_at` 變動，現在都略過。實測：原型匯出與正式網站 21:04 的匯出（`exported_at` 不同）判定相同 |
| #2 刻意改既有鍵會判定不同並指出鍵名 | 實測：改 3 處，印出「❌ 不同 3 處：latest.json status.collected_src、latest.json breadth、etfs/00988A.json」，rc=1；`test_f62_compare` |

---

## S9. `backup` 指令（優先 2）

### S9-1 對應驗收條件

| PM 驗收 | 設計 | 測試／驗證 |
|---|---|---|
| #1 新檔 > 75 MB、VERIFYONLY 通過、rc=0、既有 3 份不變 | S9-2 | SA 實測 79.5 MB；PG 步驟 0 |
| #2 連跑不覆寫；同名衝突報錯 | 檔名到秒；`FileExistsError` | `test_s9_ok_and_cleanup`；SA 連跑兩次實測 |
| #3 `--out` | `run(out_dir)` | SA 實測（scratchpad） |
| #4 容器不存在／Docker 沒在跑：訊息、rc≠0、無 Traceback | `run` 的例外處理 | `test_s9_docker_problems` |
| #5 資料庫連不上 rc=2 | `cmd_backup` 攔截 `pyodbc.Error` | `test_s9_direct_and_db_errors` |
| #6 `is_copy_only = 1` | `WITH COPY_ONLY` | 附錄 B-4；SA 實測 True |
| #7 PG 用這個指令備份 | 建議順序步驟 0 | `04-dev.md` |
| #8 README、docstring、`--help` | 第七節；`__main__.py` | `test_s9_cli` |
| #9 QA 不還原 | 程式裡沒有 `RESTORE DATABASE` | `test_s9_cli` 檢查原始碼 |

### S9-2 流程（`twstock/backup.py`，附錄 C）

1. **檔名**是 `{DB_NAME}_{YYYYMMDD_HHMMSS}.bak`，路徑是 `--out`，沒給時用 `BACKUP_DIR = 專案上一層/_backups`。
   - 主機上已有同名檔 → `❌ … 已存在，不覆寫（稍後再執行，或用 --out 指定其他資料夾）`，rc=1。
   - 這時**不連資料庫、不呼叫 docker**。
2. **找容器**（沒加 `--direct` 時）：
   - `.env` 有 `DB_CONTAINER` 時用它。
   - 否則執行 `docker ps --filter publish=<DB_SERVER 的埠號> --format {{.Names}}`，必須**剛好 1 個**。
   - 使用者的 `MySqlServer`、compose 的 `twstock-mssql` 都發布 1433，所以兩種環境都不用設定。
   - 接著用 `docker inspect -f {{.State.Running}}` 確認容器正在執行。**先確認、再備份**，避免備份寫進容器後才發現複製不出來。
3. 以 **autocommit** 連線，因為 `BACKUP` 不能在交易中執行：
   - 執行 `BACKUP DATABASE [TwStock] TO DISK = N'/var/opt/mssql/data/<檔名>' WITH COPY_ONLY, INIT, COMPRESSION`。
   - 錯誤訊息含 `COMPRESSION` 時（例如 Express 版），印「ℹ️  這個版本不支援壓縮備份，改用不壓縮」，再執行一次不壓縮的版本。
   - 其他錯誤照常拋出（PM 風險 5）。
   - 每個語句都會讀完所有結果集（`nextset`），否則 pyodbc 會在備份還沒完成時就返回。
4. 執行 `RESTORE VERIFYONLY FROM DISK = N'…'`：**只驗證、不還原**。
5. 執行 `docker cp 容器:路徑 主機路徑`，接著 `docker exec 容器 rm -f 路徑`。**只刪除這次自己產生的暫存檔**，容器內原有的 3 份不動。
6. 印出 `✅ 備份完成並通過 RESTORE VERIFYONLY：<路徑>（79.5 MB）`，rc=0。

**`--direct`**：SQL Server 不在 Docker 裡時使用，例如 Windows 本機安裝（PM 第五節第 5 點）。

- 由 SQL Server 直接寫到 `--out`，完全不呼叫 docker。
- `--out` 必須是 **SQL Server 那台機器**上、服務帳號可以寫入的資料夾。
- 這一點寫在 `--help` 與 README。

### S9-3 錯誤訊息（都沒有 Traceback）

| 情況 | 訊息 | rc |
|---|---|---|
| 同名檔已存在 | `❌ <路徑> 已存在，不覆寫（稍後再執行，或用 --out 指定其他資料夾）` | 1 |
| 沒有 docker 指令 | `❌ 找不到 docker 指令；SQL Server 不在 Docker 裡時請改用 --direct` | 1 |
| 找不到或找到多個容器 | `❌ 找不到唯一一個發布 1433 埠的 Docker 容器（找到 N 個）；請在 .env 設定 DB_CONTAINER=容器名稱，SQL Server 不在 Docker 裡時改用 --direct` | 1 |
| 容器沒有在執行 | `❌ 容器 MySqlServer 沒有在執行` | 1 |
| docker 子指令失敗（daemon 沒開、cp 失敗等） | `❌ docker <子指令> 失敗（Docker 是否已啟動？）：<stderr 前 200 字>` | 1 |
| 資料庫連不上，或 BACKUP、VERIFYONLY 失敗 | `❌ 連不上資料庫或備份失敗（請確認 Docker 與容器已啟動）：<訊息第一行>` | 2 |

### S9-4 其他決定

- **Windows**：
  - Docker Desktop 的情況和 Mac 相同。
  - 本機安裝的 SQL Server 用 `--direct --out D:\backups`。
- **雙擊腳本（`scripts/mac`、`scripts/windows`）**：**不加**。只有一個指令，README 寫清楚即可；也避免使用者誤以為是排程。
- **`.env.example`**：加上 `DB_CONTAINER` 的註解範例（選填，第七節）。
- 範圍外：不做自動刪除、`restore` 指令、排程、上傳。容器內第 3～5 輪的 3 份 `.bak` **不清**，沿用 PM 第六節第 4 點，由使用者決定。

---

## 七、README 與其他文件修改清單

### README（PG 依清單修改，QA 逐條核對）

| # | 位置 | 修改 |
|---|---|---|
| 1 | 第 21 行「`tests/`」 | 加上 `python3 tests/test_iter06.py` |
| 2 | 第 40 行「新增資料表」 | 加上「，第 6 輪的 `etf_holding_gaps`」 |
| 3 | 「日常使用」程式碼區塊，`python -m twstock setup-db` 那一行之前 | 加上：`python -m twstock backup                         # 備份資料庫到專案上一層的 _backups/（COPY_ONLY＋RESTORE VERIFYONLY；只新增不覆寫；--out 指定資料夾）` |
| 4 | 同一區塊的測試列 | 加上：`python3 tests/test_iter06.py                     # 第 6 輪測試` |
| 5 | 第 116 行「主動型 ETF 持股」最後 | 加上：「**海外休市日**（跨境 ETF 當天沒有持股清單，例如美國感恩節）與**臺股臨時休市前一個交易日**（投信只公布彙總、沒有明細）會記在 `etf_holding_gaps`，`check` 視為正常並另列一行，不再請求；持股頁與 1 日增減以前一個有明細的持股日為準。臨時休市前一日的明細在生效日之前都當成尚未公布，所以當晚 22:00 後可能先顯示異常，隔天收集後自動消失。」 |
| 6 | 第 118 行「資料完整性」最後 | 加上：「第 6 輪：主動 ETF 持股遇到投信確定沒有明細的日期（見『主動型 ETF 持股』），算齊全，涵蓋數含這些日期，`check` 另列『投信沒有持股明細（不算缺）』。」 |
| 7 | **新增段落「## 備份與還原」**（放在「日常使用」之後） | 見下方範本 |

**第 7 項的段落範本**：

````markdown
## 備份與還原

資料庫在容器裡，`docker rm` 會一起刪掉。處置／注意股歷史、主動 ETF 持股都無法完整重抓，請定期備份。

```bash
python -m twstock backup                    # 存到專案上一層的 _backups/TwStock_YYYYMMDD_HHMMSS.bak
python -m twstock backup --out ~/Desktop    # 指定資料夾
python -m twstock backup --direct --out D:\backups   # SQL Server 不在 Docker 裡（例如 Windows 本機安裝）：由 SQL Server 直接寫到該資料夾
```

- 使用 `COPY_ONLY`（不影響其他備份），備份後以 `RESTORE VERIFYONLY` 驗證（只驗證、不還原）；檔名含日期時間，只新增、不覆寫，舊備份不會自動刪除，請自行整理（每份約 80 MB）。
- 容器：自動找發布 `DB_SERVER` 埠號的容器（`MySqlServer`、`twstock-mssql` 都適用）；找到多個或名稱特殊時在 `.env` 設定 `DB_CONTAINER=容器名稱`。
- 建議時機：更新程式或補抓歷史之前、每週一次。要定期自動備份，可自行把這個指令加進排程。
- 回傳碼：0 = 成功；1 = 檔名已存在或 Docker 問題；2 = 連不上資料庫或備份失敗。

**還原（沒有提供指令，請手動執行；會覆蓋現有資料，請先停用排程並確認備份檔正確）**：

1. `docker cp _backups/TwStock_….bak MySqlServer:/var/opt/mssql/data/restore.bak`
2. 用 SQL 工具連到 `master` 執行 `RESTORE DATABASE [TwStock] FROM DISK = N'/var/opt/mssql/data/restore.bak' WITH REPLACE`
3. 執行 `python -m twstock check` 確認資料
````

### `.env.example`

在最後加上兩行：

```
# 選填：備份用的容器名稱（不設定時自動找發布 DB_SERVER 埠號的容器）
# DB_CONTAINER=MySqlServer
```

### `twstock/__main__.py`（附錄 C 的 diff 已包含）

- docstring 加一行：`python -m twstock backup [--out 資料夾]            備份資料庫（COPY_ONLY＋RESTORE VERIFYONLY），預設存到專案上一層的 _backups/`
- 子指令 `backup`：
  - help：「備份資料庫（COPY_ONLY，備份後 RESTORE VERIFYONLY 驗證；只新增不覆寫）」
  - `--out`、`--direct`。

---

## 八、給 PG、QA 的提醒

### PG

- **順序**：
  - 先只套用 `backup.py`、`__main__.py`，用新指令備份（步驟 0）。
  - 然後才套用 `db.py` 並執行 `setup-db`。
  - `04-dev.md` 要記錄備份指令的完整輸出。
- **`history` 標記 8 天時，不要加 `--force`**：`--force` 會把 4 檔一年的持股全部重抓，約 650 次請求。
- 標記中斷或被限流時，等 30 分鐘以上再用同一指令重跑；已經記錄的日期不會再請求。
- `logs/iter06_compare.py` 在 `logs/`，不進版本控制；比對基線在 `logs/iter06_before/`。
- **步驟 8、9 的順序**：在隔天 17:30 後執行時，`collect --catch-up` 會寫入新的資料日，比對必然不同。這時先比對再收集。
- 不要動 `.env`（只改 `.env.example`）；不要 commit；不要執行還原；不要刪除容器內或 `_backups/` 既有的備份；測試伺服器用 8001，結束時關閉（本輪沒有前端變更，應該用不到）。

### QA

- **反例**（PM 風險 1）：
  - 用第 5 輪 SA 附錄 A 的「尚未公布」回應，以及 `PCF_EMPTY`，確認不會判成 A 或 B（`test_f61_parse_unpublished_and_normal`）。
  - 若要額外抽樣，請一律經過 `fetch.request(isolated=True)`，不重試，並把次數寫進 `05-qa.md`。
- **已知、可接受**：
  1. 臨時休市前一日的 B，在當晚 22:00 後到生效日收集之前，會顯示異常（發現 2）。
  2. 標記執行時，`history` 結尾的「無資料」會列出 gap 日期（發現 5）。
  3. 若投信某天真的在公布前先回傳「生效日相同、持股日不同」的清單，會被誤判成 A，而且不會再重抓。目前 6 份真實回應與第 5 輪的未公布回應都沒有這種格式。發生時的復原方式：
     ```sql
     DELETE g FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id WHERE e.etf_code = '00988A' AND g.hold_date = '2026-11-26'
     ```
     再執行 `history --start 該日 --end 該日 --only holdings`。這個方式寫在本節，**不放 README**，因為是開發者操作。
- **S9**：
  - 只用 `RESTORE VERIFYONLY` 驗證，**不執行任何還原**。
  - 自己產生的備份請用 `--out` 指定暫存資料夾。驗收結束後，暫存資料夾的檔案可以刪除；`../_backups/` 既有的檔案不要刪除。
  - Docker 異常的情境只用 mock，**不要真的停掉容器**。
- **11/26 期限**：QA 要在 11/26 前完成。若 QA 發現缺陷，修正也要在期限內上線。

### 待辦（本輪不做）

- 持股頁註明「某日投信沒有持股清單」（F6-1-6）。
- `history` 結尾「無資料」排除 gap（發現 5）。

---

## 九、使用者決定事項

本輪沒有新的待決事項。SA 在 PM 授權範圍內定案的項目如下，使用者如果有不同意見，請在進 PG 前提出：

| # | 項目 | SA 定案 |
|---|---|---|
| 1 | gap 的紀錄方式 | 另建 `etf_holding_gaps`（F6-1-3） |
| 2 | `check` 呈現 | 正常，涵蓋數含 gap，另列一行（F6-1-6） |
| 3 | 持股頁是否加註 | 不加，列入待辦 |
| 4 | 8 個已知日期 | 重抓，共 8 次請求 |
| 5 | 備份檔名 | 到秒：`TwStock_YYYYMMDD_HHMMSS.bak` |
| 6 | 容器名稱 | `.env` 選填 `DB_CONTAINER`，否則自動偵測發布埠號的容器 |
| 7 | 不在 Docker 時 | `--direct` |
| 8 | 雙擊備份腳本 | 不加 |

---

## 附錄 A：資料來源紀錄

- **SA 階段外部請求 0 次。**
- 使用的回應：
  - 分析師 2026-11-04 21:05 以 `fetch.request(isolated=True)` 取得的 6 份完整 `GetPCF` 回應（`01-analyst.md` 第六節 #1～#6），存在工作階段 scratchpad。
  - 第 5 輪 PG 的 10/21 診斷（`05/04-dev.md`）：`NAV` 4,684,340,379、`TranDate` 10/21、`PostDate` 10/27、`asset: []`。
  - 第 5 輪 SA 的「尚未公布」格式（`05/03-design.md` 附錄 A）。

| 回應 | `NAV.TranDate` | `NAV.PostDate` | `NAV.Amount` | 明細列數 | 原型判定 |
|---|---|---|---|---|---|
| 00988A 參數 `114/12/01` | `/Date(1764086400000)/` = 2025-11-26 | `/Date(1764518400000)/` = 2025-12-01 | 9,230,516,712 | 52 | A，src 11/26 |
| 00988A `115/01/21` | 01-16 | 01-21 | 8,435,860,750 | 38 | A，src 01/16 |
| 00988A `115/02/23` | 02-11 | 02-23 | 10,792,838,238 | 46 | A，src 02/11 |
| 00988A `115/05/27` | 05-22 | 05-27 | 40,138,747,381 | 47 | A，src 05/22 |
| 00988A `115/07/13` | 07-08 | 07-13 | 59,853,545,462 | **0** | B |
| 00411A `115/09/09` | 09-04 | 09-09 | 6,233,471,648 | 36 | A，src 09/04 |

`/Date(毫秒)/` 是 UTC 16:00，換算成台灣時間是隔天 00:00（第 5 輪 `ez_date`）。

---

## 附錄 B：預期值與 QA 用 SQL（全部唯讀）

### B-1. `etf_holding_gaps`（F6-1 #1）

```sql
SELECT e.etf_code, g.hold_date, g.reason, g.src_date, g.post_date, g.nav
FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id
ORDER BY g.hold_date, e.etf_code;
```

| etf_code | hold_date | reason | src_date | post_date | nav |
|---|---|---|---|---|---|
| 00988A | 2025-11-27 | A | 2025-11-26 | 2025-12-01 | NULL |
| 00988A | 2026-01-19 | A | 2026-01-16 | 2026-01-21 | NULL |
| 00988A | 2026-02-10 | A | 2026-02-11 | 2026-02-23 | NULL |
| 00988A | 2026-05-25 | A | 2026-05-22 | 2026-05-27 | NULL |
| 00988A | 2026-07-08 | B | 2026-07-08 | 2026-07-13 | 59853545462.00 |
| 00411A | 2026-09-07 | A | 2026-09-04 | 2026-09-09 | NULL |
| 00411A | 2026-10-21 | B | 2026-10-21 | 2026-10-27 | 4684340379.00 |
| 00988A | 2026-10-21 | B | 2026-10-21 | 2026-10-27 | > 0（以實際回應為準） |

- 共 8 列。這是唯讀模擬的結果，`post_date` 用的是資料庫的休市表。
- **A 的 `src_date` 都已存有明細，筆數與回應相同**：

```sql
SELECT e.etf_code, g.hold_date, g.src_date,
       (SELECT COUNT(*) FROM etf_holdings h WHERE h.etf_id = g.etf_id AND h.hold_date = g.src_date) AS src_rows
FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id WHERE g.reason = 'A' ORDER BY g.hold_date;
-- 預期 src_rows：52、38、46、47、36
```

### B-2. gap 日期沒有明細（F6-1 #4）

```sql
SELECT COUNT(*) FROM etf_holdings h JOIN etf_holding_gaps g ON g.etf_id = h.etf_id AND g.hold_date = h.hold_date;          -- 0
SELECT COUNT(*) FROM etf_holding_summary s JOIN etf_holding_gaps g ON g.etf_id = s.etf_id AND g.hold_date = s.hold_date;   -- 0
```

### B-3. 既有持股筆數不變（F6-1 #4；setup-db 前後、標記前後都相同）

```sql
SELECT e.etf_code, COUNT(DISTINCT s.hold_date) AS days, MIN(s.hold_date) AS first_day, MAX(s.hold_date) AS last_day,
       (SELECT COUNT(*) FROM etf_holdings h WHERE h.etf_id = e.etf_id) AS rows
FROM etfs e JOIN etf_holding_summary s ON s.etf_id = e.etf_id GROUP BY e.etf_id, e.etf_code ORDER BY e.etf_code;
```

2026-11-04 21:30 的值（SA 唯讀查詢）：

| etf_code | days | first_day | last_day | rows |
|---|---|---|---|---|
| 00403A | 120 | 2026-05-12 | 2026-11-04 | 6,014 |
| 00411A | 43 | 2026-08-26 | 2026-11-03 | 1,420 |
| 00981A | 245 | 2025-10-30 | 2026-11-04 | 12,482 |
| 00988A | 234 | 2025-11-05 | 2026-11-03 | 10,609 |

PG 執行步驟 8 時若收到新的持股日，只有 `last_day`、`days`、`rows` 會增加，其他不變。

### B-4. 備份（S9 #1、#6）

```sql
SELECT TOP 3 b.backup_finish_date, b.is_copy_only, b.compressed_backup_size, m.physical_device_name
FROM msdb.dbo.backupset b JOIN msdb.dbo.backupmediafamily m ON m.media_set_id = b.media_set_id
WHERE b.database_name = 'TwStock' ORDER BY b.backup_finish_date DESC;
-- 最新一筆：is_copy_only = 1，physical_device_name = /var/opt/mssql/data/TwStock_2026…bak
```

- SA 實測（13:17 UTC = 21:17 台灣時間）：`is_copy_only = True`，`compressed_backup_size` 83,383,778，`backup_size` 303,136,768。
- 主機檔案 83,398,656 B。
- `msdb` 的時間是 UTC；第 3、4 輪的手動備份 `is_copy_only = False`，第 5 輪是 True。
- 既有備份（不可變動）：

| 位置 | 檔案 | 大小 | 修改時間 |
|---|---|---|---|
| `../_backups/` | `TwStock_before_round3.bak` | 54,378,496 | 10/31 12:16 |
| 同上 | `TwStock_before_round4.bak` | 56,651,776 | 11/03 21:26 |
| 同上 | `TwStock_before_round5.bak` | 81,129,472 | 11/03 23:52 |
| 容器 `/var/opt/mssql/data/` | 同名 3 份 | 同上 | 同上（容器時間為 UTC） |

`docker exec MySqlServer ls -l /var/opt/mssql/data/` 執行後，`.bak` 只應該有這 3 份。新的備份不應該留在容器內。

---

## 附錄 C：原型對現有程式的完整 diff（已通過 `test_iter01`～`06`）

- 包含新檔 `twstock/backup.py`，以及 `__main__.py`、`db.py`、`collectors/holdings.py`、`collectors/daily.py`、`health.py` 的修改。
- 不包含 README 與 `.env.example`（第七節）。
- 基準是目前專案的程式（第 5 輪 PG 完成後）。

```diff
diff --git a/twstock/__main__.py b/twstock/__main__.py
index 703d9ef..c7641e3 100644
--- a/twstock/__main__.py
+++ b/twstock/__main__.py
@@ -19,6 +19,7 @@
   python -m twstock futures --start 2025-01-01       台指期日 K 與期貨三大法人未平倉
   python -m twstock chains                           更新產業鏈族群（櫃買產業價值鏈平台）
   python -m twstock chanlun 2330                     纏論結構圖（output/chanlun_2330.svg）
+  python -m twstock backup [--out 資料夾]            備份資料庫（COPY_ONLY＋RESTORE VERIFYONLY），預設存到專案上一層的 _backups/
 """
 import argparse
 import sys
@@ -72,6 +73,16 @@ def cmd_check(args):
         return 2
 
 
+def cmd_backup(args):
+    from .backup import run
+    import pyodbc
+    try:
+        return run(args.out, args.direct)
+    except pyodbc.Error as e:
+        print(f"❌ 連不上資料庫或備份失敗（請確認 Docker 與容器已啟動）：{str(e).splitlines()[0][:200]}")
+        return 2
+
+
 def cmd_history(args):
     from .collectors.daily import ALL_DATASETS
     from .collectors.history import run_history
@@ -227,6 +238,11 @@ def main(argv=None):
     s.add_argument("--days", type=int, default=130)
     s.set_defaults(fn=cmd_chanlun)
 
+    s = sub.add_parser("backup", help="備份資料庫（COPY_ONLY，備份後 RESTORE VERIFYONLY 驗證；只新增不覆寫）")
+    s.add_argument("--out", help="輸出資料夾，預設專案上一層的 _backups/")
+    s.add_argument("--direct", action="store_true", help="SQL Server 不在 Docker 裡時：由 SQL Server 直接寫到 --out")
+    s.set_defaults(fn=cmd_backup)
+
     args = p.parse_args(argv)
     return args.fn(args) or 0
 
diff --git a/twstock/backup.py b/twstock/backup.py
new file mode 100644
index 0000000..0f8b947
--- /dev/null
+++ b/twstock/backup.py
@@ -0,0 +1,92 @@
+"""
+資料庫備份（第 6 輪 S9）：BACKUP DATABASE … COPY_ONLY → RESTORE VERIFYONLY → docker cp 到主機。
+
+COPY_ONLY 不影響其他備份鏈；檔名含日期時間（到秒）、只新增不覆寫；不提供還原指令（還原步驟見 README）。
+容器名稱：.env 的 DB_CONTAINER，沒有時找發布 DB_SERVER 埠號的容器（使用者的 MySqlServer、compose 的 twstock-mssql 都適用）。
+SQL Server 不在 Docker 裡時用 --direct：由 SQL Server 直接寫到 --out（服務帳號要有該資料夾的寫入權限）。
+"""
+import os
+import subprocess
+from datetime import datetime
+from pathlib import Path
+
+from .config import DB_CONFIG, ROOT
+
+BACKUP_DIR = ROOT.parent / "_backups"        # 專案上一層，與第 3～5 輪手動備份同一處（不進 repo）
+CONTAINER_DIR = "/var/opt/mssql/data"
+
+
+def _docker(*args) -> str:
+    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout.strip()
+
+
+def find_container() -> str:
+    """DB_CONTAINER 優先；否則找發布 SQL Server 埠號的執行中容器。找不到 → RuntimeError。"""
+    name = os.environ.get("DB_CONTAINER")
+    if not name:
+        port = DB_CONFIG["server"].rpartition(",")[2] if "," in DB_CONFIG["server"] else "1433"
+        names = _docker("ps", "--filter", f"publish={port}", "--format", "{{.Names}}").split()
+        if len(names) != 1:
+            raise RuntimeError(f"找不到唯一一個發布 {port} 埠的 Docker 容器（找到 {len(names)} 個）；"
+                               "請在 .env 設定 DB_CONTAINER=容器名稱，SQL Server 不在 Docker 裡時改用 --direct")
+        name = names[0]
+    # 先確認容器在跑，避免備份寫進容器後才發現複製不出來
+    if _docker("inspect", "-f", "{{.State.Running}}", name) != "true":
+        raise RuntimeError(f"容器 {name} 沒有在執行")
+    return name
+
+
+def _run_sql(cur, sql: str):
+    cur.execute(sql)
+    while cur.nextset():            # BACKUP／RESTORE 的進度訊息是多個結果集，要讀完才算執行完
+        pass
+
+
+def backup(out_dir: Path, direct=False, now=None) -> Path:
+    """備份並驗證，回傳主機上的檔案路徑。同名檔已存在 → FileExistsError；Docker 問題 → RuntimeError。"""
+    from . import db
+    name = f"{DB_CONFIG['database']}_{(now or datetime.now()):%Y%m%d_%H%M%S}.bak"
+    dest = Path(out_dir).resolve() / name
+    if dest.exists():
+        raise FileExistsError(f"{dest} 已存在，不覆寫（稍後再執行，或用 --out 指定其他資料夾）")
+    container = None if direct else find_container()
+    dest.parent.mkdir(parents=True, exist_ok=True)
+    disk = str(dest) if direct else f"{CONTAINER_DIR}/{name}"
+    conn = db.connect(autocommit=True)          # BACKUP 不能在交易中執行
+    try:
+        cur = conn.cursor()
+        sql = f"BACKUP DATABASE [{DB_CONFIG['database']}] TO DISK = N'{disk}' WITH COPY_ONLY, INIT"
+        try:
+            _run_sql(cur, sql + ", COMPRESSION")
+        except db.pyodbc.Error as e:
+            if "COMPRESSION" not in str(e).upper():
+                raise
+            print("ℹ️  這個版本不支援壓縮備份，改用不壓縮")
+            _run_sql(cur, sql)
+        _run_sql(cur, f"RESTORE VERIFYONLY FROM DISK = N'{disk}'")      # 只驗證、不還原
+    finally:
+        conn.close()
+    if not direct:
+        _docker("cp", f"{container}:{disk}", str(dest))
+        _docker("exec", container, "rm", "-f", disk)                     # 只刪這次自己產生的暫存檔
+    return dest
+
+
+def run(out_dir=None, direct=False) -> int:
+    out_dir = Path(out_dir) if out_dir else BACKUP_DIR
+    try:
+        path = backup(out_dir, direct)
+    except FileExistsError as e:
+        print(f"❌ {e}")
+        return 1
+    except FileNotFoundError:
+        print("❌ 找不到 docker 指令；SQL Server 不在 Docker 裡時請改用 --direct")
+        return 1
+    except subprocess.CalledProcessError as e:
+        print(f"❌ docker {e.cmd[1]} 失敗（Docker 是否已啟動？）：{(e.stderr or '').strip()[:200]}")
+        return 1
+    except RuntimeError as e:
+        print(f"❌ {e}")
+        return 1
+    print(f"✅ 備份完成並通過 RESTORE VERIFYONLY：{path}（{path.stat().st_size / 1048576:.1f} MB）")
+    return 0
diff --git a/twstock/collectors/daily.py b/twstock/collectors/daily.py
index 4233e27..3eb1e43 100644
--- a/twstock/collectors/daily.py
+++ b/twstock/collectors/daily.py
@@ -11,7 +11,7 @@ from .. import db
 from ..fetch import FetchError, SchemaError, clean_number, is_etf_code, is_valid_stock_code, request
 from ..health import HOLDINGS
 from ..tradingcal import load_closed
-from .holdings import fetch_holdings, merge_holdings
+from .holdings import GAP_REASON, Gap, fetch_holdings, merge_gap, merge_holdings
 
 TWSE = "https://www.twse.com.tw/rwd/zh"
 TPEX = "https://www.tpex.org.tw/www/zh-tw"
@@ -769,6 +769,10 @@ def _collect_key(key: str, d: date, cache: dict) -> int:
             finally:
                 conn.close()
         got = fetch_holdings(market, d, cache["closed"])
+        if isinstance(got, Gap):                        # 投信確定沒有這天的明細：記下來，不算缺、不再請求
+            _save(merge_gap, market, d, got)
+            cache.setdefault("gaps", {})[key] = got
+            return 0
         if not got:
             return 0                                    # 尚未公布，或回應的持股日不是 d
         summary, rows = got
@@ -810,12 +814,15 @@ def collect_for_date(d: date, keys=DAY_KEYS) -> tuple:
         except (FetchError, *PARSE_ERRORS) as e:
             errors[key] = e
             print(f"  ⚠️  {key} 失敗：{e}")
+    gaps = cache.get("gaps", {})
     done = "、".join(f"{k} {v} 筆" for k, v in written.items() if v)
-    none = "、".join(k for k, v in written.items() if not v)
+    none = "、".join(k for k, v in written.items() if not v and k not in gaps)
     if done:
         print(f"  ✅ 寫入：{done}")
     if none:
         print(f"  ℹ️  官方尚無資料：{none}")
+    if gaps:
+        print("  ℹ️  來源無持股明細（不算缺）：" + "、".join(f"{k}（{GAP_REASON[g.reason]}）" for k, g in gaps.items()))
     return written, errors
 
 
diff --git a/twstock/collectors/holdings.py b/twstock/collectors/holdings.py
index 5f6b76a..1a89563 100644
--- a/twstock/collectors/holdings.py
+++ b/twstock/collectors/holdings.py
@@ -4,7 +4,12 @@
 日期語意：參數 date 是清單「生效日」= 持股公布日的下一個交易日；回應的 TranDate 才是持股日。
 國內 ETF 當天公布當天的持股（生效日 = 持股日後第 1 個交易日）；跨境 ETF 落後 1 天（第 2 個交易日）。
 資料表以持股日為準；回應的 TranDate 與要求的持股日不同（尚未公布、連假）一律不寫入。
+第 6 輪：投信確定沒有這天的明細時記成 Gap（etf_holding_gaps），不算缺、不再請求：
+  A：清單已公布（PostDate = 要求的生效日），持股日卻是別天 → 這天沒有持股清單（海外休市、春節前）
+  B：彙總的持股日就是這天，明細卻是空的 → 只有彙總（臺股臨時休市前一日）；公布當晚可能只是還沒寫完，到生效日才確定
+尚未公布的回應 pcf 日期都是西元 1 年、金額 0，不會落入 A、B。
 """
+from collections import namedtuple
 from datetime import date, datetime, timedelta
 
 from .. import db
@@ -13,6 +18,8 @@ from ..health import HOLDINGS
 from ..tradingcal import trading_days
 
 URL = "https://www.ezmoney.com.tw/ETF/Transaction/GetPCF"
+Gap = namedtuple("Gap", "reason src_date post_date nav")
+GAP_REASON = {"A": "投信當日無持股清單", "B": "投信只公布彙總、沒有明細"}
 _EPOCH = datetime(1970, 1, 1) + timedelta(hours=8)      # /Date(毫秒)/ 是 UTC，換成台灣時間
 
 
@@ -32,16 +39,25 @@ def post_date(d: date, delay: int, closed) -> date:
     return trading_days(d + timedelta(days=1), d + timedelta(days=40), closed)[delay]
 
 
-def parse_pcf(data: dict, d: date):
-    """GetPCF 回應 → (彙總, 明細列)；尚未公布或持股日不是 d 回傳 None。欄位不符 → SchemaError。"""
+def parse_pcf(data: dict, d: date, post: date = None, today: date = None):
+    """
+    GetPCF 回應 → (彙總, 明細列)；尚未公布或持股日不是 d 回傳 None；投信確定沒有 d 的明細回傳 Gap
+    （要給 post = 要求的生效日才判斷；B 另外要 today ≥ post）。欄位不符 → SchemaError。
+    """
     if not isinstance(data, dict) or not {"pcf", "asset"} <= data.keys():
         raise SchemaError("GetPCF 回應缺少 pcf 或 asset")
+    pcf = {p["PCFCode"]: p for p in data["pcf"]}
+    nav = pcf.get("NAV")
     if not data["asset"]:
+        if (nav and post and today and today >= post and nav["Amount"]
+                and ez_date(nav["TranDate"]) == d and ez_date(nav["PostDate"]) == post):
+            return Gap("B", d, post, nav["Amount"])
         return None                                     # 尚未公布：pcf 全是 0、asset 為空
-    pcf = {p["PCFCode"]: p for p in data["pcf"]}
-    if "NAV" not in pcf:
+    if nav is None:
         raise SchemaError("GetPCF 的 pcf 缺少 NAV")
-    if ez_date(pcf["NAV"]["TranDate"]) != d:
+    if ez_date(nav["TranDate"]) != d:
+        if post and ez_date(nav["PostDate"]) == post:
+            return Gap("A", ez_date(nav["TranDate"]), post, None)
         return None
     rows, edited = [], None
     for a in data["asset"]:
@@ -68,7 +84,7 @@ def fetch_holdings(code: str, d: date, closed):
     fund, delay, _ = HOLDINGS[code]
     post = post_date(d, delay, closed)
     data = request("POST", URL, json={"fundCode": fund, "date": f"{post.year - 1911}/{post:%m/%d}", "specificDate": True})
-    return parse_pcf(data, d)
+    return parse_pcf(data, d, post, date.today())
 
 
 def merge_holdings(cursor, code: str, summary: dict, rows: list) -> bool:
@@ -78,6 +94,7 @@ def merge_holdings(cursor, code: str, summary: dict, rows: list) -> bool:
         return False
     etf_id, d = row[0], summary["hold_date"]
     cursor.execute("DELETE FROM etf_holdings WHERE etf_id = ? AND hold_date = ?", etf_id, d)
+    cursor.execute("DELETE FROM etf_holding_gaps WHERE etf_id = ? AND hold_date = ?", etf_id, d)
     cursor.execute("""
         INSERT INTO etf_holdings (etf_id, hold_date, asset_type, code, month, name, shares, amount, weight, currency)
         SELECT ?, ?, asset_type, code, month, name, shares, amount, weight, currency FROM OPENJSON(?) WITH (
@@ -100,3 +117,18 @@ def merge_holdings(cursor, code: str, summary: dict, rows: list) -> bool:
                     s.futures_amount, s.edited_at);
     """, db.to_json([summary]), etf_id, etf_id)
     return True
+
+
+def merge_gap(cursor, code: str, d: date, gap: Gap) -> bool:
+    """記下投信確定沒有明細的持股日（可重複執行）。etfs 沒有這檔回傳 False。"""
+    row = cursor.execute("SELECT etf_id FROM etfs WHERE etf_code = ?", code).fetchone()
+    if not row:
+        return False
+    cursor.execute("""
+        MERGE etf_holding_gaps AS t
+        USING (SELECT ? AS etf_id, ? AS hold_date) AS s ON t.etf_id = s.etf_id AND t.hold_date = s.hold_date
+        WHEN MATCHED THEN UPDATE SET reason = ?, src_date = ?, post_date = ?, nav = ?
+        WHEN NOT MATCHED THEN INSERT (etf_id, hold_date, reason, src_date, post_date, nav) VALUES (?, ?, ?, ?, ?, ?);
+    """, row[0], d, gap.reason, gap.src_date, gap.post_date, gap.nav,
+        row[0], d, gap.reason, gap.src_date, gap.post_date, gap.nav)
+    return True
diff --git a/twstock/db.py b/twstock/db.py
index eb579f2..fd3ebed 100644
--- a/twstock/db.py
+++ b/twstock/db.py
@@ -423,6 +423,21 @@ DDL = [
         CONSTRAINT UQ_market_breadth UNIQUE (trade_date, market)
     )
     """,
+    # 投信確定沒有持股明細的持股日（第 6 輪）：A 當日無持股清單（海外休市等）、B 只有彙總沒有明細（臺股臨時休市前一日）
+    """
+    IF OBJECT_ID('etf_holding_gaps') IS NULL
+    CREATE TABLE etf_holding_gaps (
+        id          INT IDENTITY(1,1) PRIMARY KEY,
+        etf_id      INT            NOT NULL REFERENCES etfs(etf_id),
+        hold_date   DATE           NOT NULL,
+        reason      CHAR(1)        NOT NULL CHECK (reason IN ('A','B')),
+        src_date    DATE           NOT NULL,  -- 回應的持股日（A 為前一個海外交易日；B 等於 hold_date）
+        post_date   DATE           NOT NULL,  -- 清單生效日（請求參數）
+        nav         DECIMAL(20,2)  NULL,      -- B 的彙總淨資產（元）
+        created_at  DATETIME       NOT NULL DEFAULT GETDATE(),
+        CONSTRAINT UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)
+    )
+    """,
     # 索引
     "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_daily_prices_date') "
     "CREATE INDEX IX_daily_prices_date ON daily_prices(trade_date)",
@@ -460,4 +475,5 @@ def setup_database():
     print("✅ 資料表已確認：stocks、daily_prices、monthly_revenue、stock_fundamentals、"
           "institutional_trades、futures_daily_prices、futures_institutional、industry_chains、"
           "market_index、stock_alerts、price_events、insti_amount、collect_runs、market_holidays、"
-          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth")
+          "etfs、etf_daily、margin_trades、etf_margin、margin_market、etf_holdings、etf_holding_summary、market_breadth、"
+          "etf_holding_gaps")
diff --git a/twstock/health.py b/twstock/health.py
index 014dcb0..ea9832e 100644
--- a/twstock/health.py
+++ b/twstock/health.py
@@ -22,7 +22,7 @@ ALERTS_SETTLED = time(19, 0)    # 處置／注意股當日公告大致底定的
 COUNT_RATIO, FILL_MIN, MEDIAN_DAYS = 0.8, 0.5, 20
 OK, PENDING, ABNORMAL = "ok", "pending", "abnormal"
 
-Row = namedtuple("Row", "n pe pb dy", defaults=(0, 0, 0, 0))
+Row = namedtuple("Row", "n pe pb dy gap", defaults=(0, 0, 0, 0, None))     # gap：投信確定沒有明細（A／B），算齊全
 Spec = namedtuple("Spec", "key label min_rows fills since delay", defaults=(None, 0))
 Item = namedtuple("Item", "key label date status n reason")
 FILLS = (("pe", "本益比"), ("pb", "淨值比"), ("dy", "殖利率"))
@@ -75,6 +75,10 @@ def load_snapshot(cur, start: date, end: date) -> dict:
                                   start, end).fetchall():
         if f"holdings.{code}" in snap:
             snap[f"holdings.{code}"][d] = Row(n)
+    for d, code, reason in cur.execute("SELECT g.hold_date, e.etf_code, g.reason FROM etf_holding_gaps g JOIN etfs e ON e.etf_id = g.etf_id "
+                                       "WHERE g.hold_date BETWEEN ? AND ?", start, end).fetchall():
+        if f"holdings.{code}" in snap:
+            snap[f"holdings.{code}"].setdefault(d, Row(gap=reason))
     for d, market, n in cur.execute("SELECT trade_date, market, COUNT(*) FROM market_breadth WHERE trade_date BETWEEN ? AND ? "
                                     "GROUP BY trade_date, market", start, end).fetchall():
         snap[f"breadth.{market}"][d] = Row(n)
@@ -99,6 +103,8 @@ def medians(snap: dict) -> dict:
 
 def assess(spec: Spec, row: Row, median: float):
     """齊全回傳 None；否則回傳 (種類, 說明)。種類：none 無資料 / count 筆數偏低 / fill:欄位 填充率偏低。"""
+    if row.gap:
+        return None                     # 來源確定沒有：不算缺
     if not row.n:
         return ("none", "無資料")
     need = max(spec.min_rows, median * COUNT_RATIO)
@@ -312,6 +318,7 @@ def check_report(days, snap, now, state, closed, adhoc=(), schedule=None) -> tup
         out.append("ℹ️  臨時休市（自動判定，判定錯誤可用 collect --date 復原）：" + "、".join(map(str, adhoc)))
     out.append(f"\n{'資料集':<8}{'涵蓋':>7}{'最新日':>12}{'筆數':>7}{'中位數':>7}  本益比/淨值比/殖利率  狀態")
     mark = {OK: "✅ 正常", PENDING: "⏳ 尚未公布", ABNORMAL: "❌ 異常"}
+    gaps = []
     for spec in SPECS:
         mine = [i for i in items if i.key == spec.key]
         have = [i for i in mine if i.n]
@@ -321,8 +328,12 @@ def check_report(days, snap, now, state, closed, adhoc=(), schedule=None) -> tup
             r = snap[spec.key][last.date]
             fill = f"{r.pe / r.n:.0%} / {r.pb / r.n:.0%} / {r.dy / r.n:.0%}"
         worst = outcome(mine)
-        out.append(f"{spec.label:<8}{len(have):>4}/{len(mine):<3}{str(last.date) if last else '--':>12}"
+        gaps += [(spec.label, i.date, snap[spec.key][i.date].gap) for i in mine if snap[spec.key].get(i.date, Row()).gap]
+        out.append(f"{spec.label:<8}{len(have) + sum(g[0] == spec.label for g in gaps):>4}/{len(mine):<3}{str(last.date) if last else '--':>12}"
                    f"{last.n if last else 0:>7,}{med[spec.key]:>7,.0f}  {fill:<20}  {mark[worst]}")
+    if gaps:
+        out.append("ℹ️  投信沒有持股明細（不算缺）：" + "、".join(f"{label} {d}（{'無持股清單' if r == 'A' else '只有彙總'}）"
+                                                    for label, d, r in gaps))
     alerts = state.get("alerts_at")
     out.append(f"\n處置／注意股最後成功：{alerts:%Y-%m-%d %H:%M}" if alerts else "\n處置／注意股最後成功：尚無執行紀錄")
     lines = problem_lines(items, state.get("last_run"))
```

---

## 附錄 D：`tests/test_iter06.py`（完整）

```python
"""
第 06 輪純邏輯測試（不連網、不連資料庫、不跳通知、不安裝排程、不呼叫 docker）：
F6-1 投信確定沒有持股明細的日期不算缺（QA-01）；F6-2 隔離比對工具（QA-02）；S9 backup 指令。
假的官方網站與資料庫沿用 test_iter03 的 World（以子類別加上 etf_holding_gaps，不改 test_iter03）。

  python3 tests/test_iter06.py      （也相容 pytest）
"""
import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_iter03 as t3  # noqa: E402
import test_iter05 as t5  # noqa: E402
from twstock import __main__ as cli  # noqa: E402
from twstock import backup, db, health, tradingcal  # noqa: E402
from twstock.collectors import daily, history, holdings  # noqa: E402
from twstock.collectors.holdings import Gap  # noqa: E402
from twstock.health import Row  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D, T, World, CLOSED = t3.D, t3.T, t3.World, t3.CLOSED
CROSS = ("00411A", "00988A")


def _y(m, d):
    return date(2025, m, d)


# ─── 實際回應的片段（2026-11-04 21:05 分析師經 fetch.request(isolated=True) 取得，只留 NAV 與第一列明細、未改值）────
def _a(tran, post, nav, detail):
    return {"pcf": [{"PCFCode": "NAV", "TranDate": tran, "PostDate": post, "Amount": nav}], "fund": {},
            "asset": [{"AssetCode": "GD", "Details": []}, {"AssetCode": "ST", "Details": [
                {"TranDate": tran, "AssetCode": "ST", "MoneyType": "USD", "MTH": "", **detail}]}]}


A_1127 = _a("/Date(1764086400000)/", "/Date(1764518400000)/", 9230516712.0,   # 00988A，115 前 → 114/12/01；持股日 11/26
            {"DetailCode": "GOOGL US", "DetailName": "ALPHABET INC-CL A(Alphabet公司)", "Share": 48100, "Amount": 15389595.0,
             "NavRate": 5.23, "EditTime": "/Date(1764229008000)/"})
A_0119 = _a("/Date(1768492800000)/", "/Date(1768924800000)/", 8435860750.0,   # 00988A 115/01/21；持股日 01/16
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 58000, "Amount": 21039500.0,
             "NavRate": 7.87, "EditTime": "/Date(1768808165000)/"})
A_0210 = _a("/Date(1770739200000)/", "/Date(1771776000000)/", 10792838238.0,  # 00988A 115/02/23；持股日 02/11（比要求日晚）
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 61000, "Amount": 25030740.0,
             "NavRate": 7.29, "EditTime": "/Date(1770881692000)/"})
A_0525 = _a("/Date(1779379200000)/", "/Date(1779811200000)/", 40138747381.0,  # 00988A 115/05/27；持股日 05/22
            {"DetailCode": "MU US", "DetailName": "MICRON TECHNOLOGY INC", "Share": 78500, "Amount": 58953500.0,
             "NavRate": 4.63, "EditTime": "/Date(1779697824000)/"})
A_0907 = _a("/Date(1788451200000)/", "/Date(1788883200000)/", 6233471648.0,   # 00411A 115/09/09；持股日 09/04
            {"DetailCode": "BE US", "DetailName": "BLOOM ENERGY CORP- A", "Share": 47354, "Amount": 11974405.98,
             "NavRate": 6.08, "EditTime": "/Date(1788769768000)/"})
B_0708 = {"pcf": [{"PCFCode": "NAV", "TranDate": "/Date(1783440000000)/", "PostDate": "/Date(1783872000000)/",   # 00988A 115/07/13
                   "Amount": 59853545462.0}], "fund": {}, "asset": []}                                          # 只有彙總
REAL_A = ((A_1127, _y(11, 27), _y(12, 1), _y(11, 26)), (A_0119, D(1, 19), D(1, 21), D(1, 16)),
          (A_0210, D(2, 10), D(2, 23), D(2, 11)), (A_0525, D(5, 25), D(5, 27), D(5, 22)), (A_0907, D(9, 7), D(9, 9), D(9, 4)))


# ─── F6-1：解析 ─────────────────────────────────────────
def test_f61_dates():
    """要求的生效日 = 第 5 輪 post_date（跨境 delay 1）；10/21、7/8 的下一個生效日跳過颱風臨時休市日。"""
    for _, d, post, _ in REAL_A:
        assert holdings.post_date(d, 1, CLOSED) == post, d
    assert holdings.post_date(D(7, 8), 1, CLOSED) == D(7, 13) and holdings.post_date(D(10, 21), 1, CLOSED) == D(10, 27)
    assert {D(7, 10), D(10, 23)} <= set(tradingcal.AD_HOC)


def test_f61_parse_a():
    for data, d, post, src in REAL_A:
        assert holdings.parse_pcf(data, d, post, D(11, 4)) == Gap("A", src, post, None), d
        assert holdings.parse_pcf(data, d) is None                       # 沒給生效日：維持第 5 輪行為
        assert holdings.parse_pcf(data, d, post + timedelta(days=1), D(11, 4)) is None   # 生效日對不上：當成未公布
    # 回應的持股日就是要求日：照常寫入（Gap 只在持股日不同時出現）
    s, rows = holdings.parse_pcf(A_1127, _y(11, 26), _y(12, 1), D(11, 4))
    assert s["hold_date"] == "2025-11-26" and rows[0]["code"] == "GOOGL US"


def test_f61_parse_b():
    post = D(7, 13)
    assert holdings.parse_pcf(B_0708, D(7, 8), post, D(11, 4)) == Gap("B", D(7, 8), post, 59853545462.0)
    assert holdings.parse_pcf(B_0708, D(7, 8), post, post) == Gap("B", D(7, 8), post, 59853545462.0)   # 生效日當天
    assert holdings.parse_pcf(B_0708, D(7, 8), post, D(7, 12)) is None   # 生效日之前：可能還沒寫完明細，當成未公布
    assert holdings.parse_pcf(B_0708, D(7, 8)) is None
    assert holdings.parse_pcf(B_0708, D(7, 7), post, D(11, 4)) is None  # 持股日不是 d
    assert holdings.parse_pcf(B_0708, D(7, 8), D(7, 14), D(11, 4)) is None
    zero = {**B_0708, "pcf": [{**B_0708["pcf"][0], "Amount": 0}]}
    assert holdings.parse_pcf(zero, D(7, 8), post, D(11, 4)) is None


def test_f61_parse_unpublished_and_normal():
    # 尚未公布（西元 1 年、金額 0）：給了生效日也不會變成 Gap
    assert holdings.parse_pcf(t5.PCF_EMPTY, D(11, 4), D(11, 5), D(11, 30)) is None
    assert holdings.parse_pcf({**t5.PCF_EMPTY, "pcf": []}, D(11, 4), D(11, 5), D(11, 30)) is None
    s, rows = holdings.parse_pcf(t5.PCF_1103, D(11, 3), D(11, 4), D(11, 4))     # 一般已公布
    assert s["n_stocks"] == 3 and len(rows) == 4
    # 國內 ETF 也適用 B（規則不限跨境）
    b = {**t5.PCF_1103, "asset": []}
    assert holdings.parse_pcf(b, D(11, 3), D(11, 4), D(11, 4)) == Gap("B", D(11, 3), D(11, 4), 254413288263.0)
    # 欄位不符仍是 SchemaError
    for bad in ({"pcf": []}, {**t5.PCF_1103, "pcf": [{"PCFCode": "P_UNIT", "TranDate": "x", "PostDate": "x", "Amount": 1}]}):
        try:
            holdings.parse_pcf(bad, D(11, 3), D(11, 4), D(11, 4))
            raise AssertionError(bad)
        except daily.PARSE_ERRORS:
            pass


class _Cur:
    def __init__(self, etf=True):
        self.sql, self.etf = [], etf

    def execute(self, sql, *p):
        self.sql.append((" ".join(sql.split()), p))
        self.one = (7,) if self.etf else None
        return self

    def fetchone(self):
        return self.one


def test_f61_merge():
    c = _Cur()
    g = Gap("A", D(11, 25), D(11, 30), None)
    assert holdings.merge_gap(c, "00988A", D(11, 26), g)
    sql, p = c.sql[1]
    assert sql.startswith("MERGE etf_holding_gaps AS t") and p == (7, D(11, 26), "A", D(11, 25), D(11, 30), None) * 2
    assert not holdings.merge_gap(_Cur(etf=False), "00988A", D(11, 26), g)
    # 之後真的拿到明細：寫明細時一併刪掉 gap 紀錄
    c = _Cur()
    s, rows = holdings.parse_pcf(t5.PCF_1103, D(11, 3))
    holdings.merge_holdings(c, "00981A", s, rows)
    assert ("DELETE FROM etf_holding_gaps WHERE etf_id = ? AND hold_date = ?", (7, "2026-11-03")) in c.sql
    src = (ROOT / "twstock/db.py").read_text(encoding="utf-8")
    assert "IF OBJECT_ID('etf_holding_gaps') IS NULL" in src and "UQ_etf_holding_gaps UNIQUE (etf_id, hold_date)" in src
    assert "CHECK (reason IN ('A','B'))" in src and "etf_holding_gaps\")" in src


# ─── F6-1：健康檢查 ─────────────────────────────────────
def test_f61_health():
    spec = health.SPEC["holdings.00988A"]
    assert health.assess(spec, Row(gap="A"), 50) is None and health.assess(spec, Row(gap="B"), 50) is None
    assert health.assess(spec, Row(), 50) == ("none", "無資料")
    days = tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED)
    snap = t3._full_snapshot(days)
    for c in CROSS:
        snap[f"holdings.{c}"][D(10, 21)] = Row(gap="B")
    snap["holdings.00988A"][D(10, 13)] = Row(gap="A")
    items = health.evaluate(days, snap, T(11, 4, 23))
    assert [i for i in items if i.status != health.OK] == []
    med = health.medians(snap)
    assert med["holdings.00988A"] == 50                                            # gap 的 0 不拉低中位數
    assert health.missing_keys(D(10, 21), tuple(f"holdings.{c}" for c in CROSS), snap, med) == ()
    out, rc = health.check_report(days, snap, T(11, 4, 23), {}, CLOSED)
    assert rc == 0, out
    assert ("ℹ️  投信沒有持股明細（不算缺）：00411A持股 2026-10-21（只有彙總）、00988A持股 2026-10-13（無持股清單）、"
            "00988A持股 2026-10-21（只有彙總）") in out
    line = next(x for x in out.splitlines() if x.startswith("00988A持股"))
    assert f"{len(days) - 1}/{len(days) - 1}" in line.replace(" ", "")            # 涵蓋含 gap（跨境少最後一天）
    # 網站狀態：目標日是 gap → 正常
    snap["holdings.00411A"][D(11, 3)] = Row(gap="A")
    st = {x["k"]: x for x in health.dataset_status(snap, D(11, 4), T(11, 4, 23), CLOSED)}
    assert st["holdings.00411A"]["s"] == health.OK and "m" not in st["holdings.00411A"]
    # 沒有 gap 時第 5 輪行為不變
    snap = t3._full_snapshot(days, skip={("holdings.00411A", D(10, 21))})
    out, rc = health.check_report(days, snap, T(11, 4, 23), {}, CLOSED)
    assert rc == 1 and "不算缺" not in out


# ─── F6-1：收集流程（假的 HTTP 與資料庫）─────────────────
class World6(World):
    """gaps = {(基金代碼, 持股日): ("A", 回應持股日) 或 ("B",)}；etf_holding_gaps 的 MERGE 寫成 Row(gap=原因)。"""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.gaps, self.gap_rows = {}, {}

    def _pcf(self, form):
        y, m, dd = form["date"].split("/")
        post = date(int(y) + 1911, int(m), int(dd))
        hold = t5._hold(form)
        g = self.gaps.get((form["fundCode"], hold))
        if not g or hold not in self.published["GetPCF"]:
            return super()._pcf(form)
        if g[0] == "B":
            return t3.Resp({"pcf": [{"PCFCode": "NAV", "TranDate": f"{hold}T00:00:00", "PostDate": f"{post}T00:00:00", "Amount": 1e9}],
                            "fund": {}, "asset": []})
        src = g[1]
        r = super()._pcf(form)
        stocks = [{"TranDate": f"{src}T00:00:00", "DetailCode": "AAPL US", "DetailName": "APPLE", "Share": 1.0, "Amount": 1.0,
                   "NavRate": 1.0, "MoneyType": "USD", "MTH": "", "EditTime": f"{hold}T16:30:00"}]
        r.data["pcf"][0].update(TranDate=f"{src}T00:00:00", PostDate=f"{post}T00:00:00")
        r.data["asset"] = [{"AssetCode": "ST", "Details": stocks}]
        return r

    def apply_merge(self, table, sql, params):
        if table != "etf_holding_gaps":
            return super().apply_merge(table, sql, params)
        self.merges.append(table)
        code, d = params[0], params[1]                    # FakeCursor：etf_id 就是 ETF 代號
        self.gap_rows[(code, d)] = params[2:6]
        self.rows[f"holdings.{code}"][d] = Row(gap=params[2])


class _Today(date):
    value = None

    @classmethod
    def today(cls):
        return cls.value


@contextlib.contextmanager
def _today(d):
    _Today.value = d
    with mock.patch.object(holdings, "date", _Today):
        yield


def test_f61_m1_thanksgiving():
    """2026-11-26 美國感恩節（情況 A）：11/27 晚上收集即記錄，不算缺、不通知；重跑 0 請求。"""
    w = World6(D(11, 26))
    for c in CROSS:
        del w.rows[f"holdings.{c}"][D(11, 26)]
    w.published["GetPCF"].add(D(11, 26))
    w.gaps = {("61YTW", D(11, 26)): ("A", D(11, 25)), ("64YTW", D(11, 26)): ("A", D(11, 25))}
    w.publish(D(11, 27))
    with _today(D(11, 27)):
        rc, out = t3.run_world(w, T(11, 27, 17, 30))
    assert rc == 0 and "Traceback" not in out, out
    assert "ℹ️  來源無持股明細（不算缺）：holdings.00411A（投信當日無持股清單）、holdings.00988A（投信當日無持股清單）" in out
    assert "官方尚無資料：holdings.00411A" not in out and "缺 2026-11-26" not in out
    assert w.gap_rows[("00988A", D(11, 26))] == ("A", date(2026, 11, 25), D(11, 30), None)
    assert w.rows["holdings.00988A"][D(11, 26)] == Row(gap="A") and w.rows["holdings.00981A"][D(11, 27)].n == 50
    hits = len(t5._pcf_hits(w))
    with _today(D(11, 27)):
        rc, out = t3.run_world(w, T(11, 27, 22, 30))
    assert rc == 0 and w.notices == [] and len(t5._pcf_hits(w)) == hits         # 22:00 後也不異常；不再請求


def test_f61_m2_typhoon_history():
    """10/21（情況 B）以 history --only holdings 重抓：記錄 B；重跑待抓 0 天、0 請求。"""
    w = World6(D(11, 4))
    for c in CROSS:
        del w.rows[f"holdings.{c}"][D(10, 21)]
    w.published["GetPCF"].update(tradingcal.trading_days(D(10, 1), D(11, 4), CLOSED))
    w.gaps = {("61YTW", D(10, 21)): ("B",), ("64YTW", D(10, 21)): ("B",)}
    with _today(D(11, 4)):
        ok, out = t5._history(w, D(10, 20), D(10, 22))
    assert ok and "Traceback" not in out, out
    assert len(t5._pcf_hits(w)) == 2 and "待抓 1 天" in out
    assert w.gap_rows[("00411A", D(10, 21))] == ("B", D(10, 21), D(10, 27), 1e9)
    with _today(D(11, 4)):
        ok, out = t5._history(w, D(10, 20), D(10, 22))
    assert ok and "待抓 0 天" in out and len(t5._pcf_hits(w)) == 2
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 23), days=20)                          # catch-up 也不再請求
    assert rc == 0 and len(t5._pcf_hits(w)) == 2


def test_f61_m3_b_before_post():
    """國內 ETF 情況 B：公布當晚（生效日之前）先當尚未公布；生效日起記成 B，不再算缺。"""
    w = World6(D(11, 3))
    w.publish(D(11, 4))
    w.gaps = {("49YTW", D(11, 4)): ("B",)}
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 17, 30))
    assert rc == 0 and "⏳ 00981A持股：2026-11-04 尚未公布" in out and ("49YTW", D(11, 4)) not in w.gap_rows
    assert ("00981A", D(11, 4)) not in w.gap_rows
    w.publish(D(11, 5))
    with _today(D(11, 5)):
        rc, out = t3.run_world(w, T(11, 5, 17, 30))
    assert rc == 0 and "holdings.00981A（投信只公布彙總、沒有明細）" in out, out
    assert w.gap_rows[("00981A", D(11, 4))] == ("B", D(11, 4), D(11, 5), 1e9) and w.notices == []


def test_f61_m4_unpublished_unchanged():
    """回應前一持股日、生效日也不同（第 5 輪 _stale）：仍是尚未公布，22:00 後異常；不記 gap。"""
    w = World6(D(11, 3))
    w.publish(D(11, 4), "GetPCF")
    t5._stale(w)
    with _today(D(11, 4)):
        rc, out = t3.run_world(w, T(11, 4, 22, 30))
    assert rc == 1 and "❌ 00981A持股：缺 2026-11-04" in out and w.gap_rows == {}


# ─── F6-2：隔離比對工具 ─────────────────────────────────
def _compare(a, b):
    r = subprocess.run([sys.executable, str(ROOT / "logs/iter06_compare.py"), str(a), str(b)], capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout


def test_f62_compare():
    if not (ROOT / "logs/iter06_compare.py").exists():                       # logs/ 不在版本控制
        print("  （略過：logs/iter06_compare.py 不存在）")
        return
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp, "a"), Path(tmp, "b")
        for x, at in ((a, "2026-11-04T21:04:00+08:00"), (b, "2026-11-05T09:00:00+08:00")):
            (x / "stocks").mkdir(parents=True)
            (x / "etfs").mkdir()
            (x / "latest.json").write_text(json.dumps({"updated_at": at, "date": "2026-11-04", "status": {
                "exported_at": at, "collected_at": at, "collected_src": "run", "datasets": [{"k": "prices.TWSE", "s": "ok"}]}}))
            (x / "stocks/2330.json").write_text(json.dumps({"c": "2330", "p": [1, 2]}))
            (x / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-04"}}))
        rc, out = _compare(a, b)
        assert rc == 0 and "✅ 相同" in out and "etfs 1 檔" in out, out
        (b / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-03"}}))
        rc, out = _compare(a, b)
        assert rc == 1 and "etfs/00981A.json" in out
        (b / "etfs/00981A.json").write_text(json.dumps({"sum": {"d": "2026-11-04"}}))
        L = json.loads((b / "latest.json").read_text())
        L["status"]["collected_src"] = "schedule"
        (b / "latest.json").write_text(json.dumps(L))
        rc, out = _compare(a, b)
        assert rc == 1 and "status.collected_src" in out


# ─── S9：backup ────────────────────────────────────────
class _Docker:
    """假的 docker：記錄指令；ps／inspect 的回應可設定；cp 在主機建立檔案。"""

    def __init__(self, ps="MySqlServer", running="true", fail=None, missing=False):
        self.calls, self.ps, self.running, self.fail, self.missing = [], ps, running, fail, missing

    def __call__(self, cmd, capture_output=True, text=True, check=True):
        if self.missing:
            raise FileNotFoundError("docker")
        self.calls.append(cmd[1:])
        if self.fail == cmd[1]:
            raise subprocess.CalledProcessError(1, cmd, "", "Error response from daemon: boom")
        out = {"ps": self.ps, "inspect": self.running}.get(cmd[1], "")
        if cmd[1] == "cp":
            Path(cmd[3]).write_bytes(b"x" * 1048576)
        return subprocess.CompletedProcess(cmd, 0, out + "\n", "")


class _SqlCur:
    def __init__(self, log, no_compress):
        self.log, self.no_compress = log, no_compress

    def execute(self, sql):
        self.log.append(sql)
        if self.no_compress and "COMPRESSION" in sql:
            raise db.pyodbc.Error("42000", "BACKUP DATABASE WITH COMPRESSION is not supported on Express Edition")
        return self

    def nextset(self):
        return False


class _SqlConn:
    def __init__(self, log, no_compress=False):
        self.log, self.no_compress, self.closed = log, no_compress, False

    def cursor(self):
        return _SqlCur(self.log, self.no_compress)

    def close(self):
        self.closed = True


@contextlib.contextmanager
def _bk(docker=None, no_compress=False, env=None, connect_error=None):
    sql, conns = [], []

    def connect(autocommit=False):
        assert autocommit                                   # BACKUP 不能在交易中執行
        if connect_error:
            raise connect_error
        conns.append(_SqlConn(sql, no_compress))
        return conns[-1]
    with mock.patch.object(backup.subprocess, "run", docker or _Docker()), mock.patch.object(db, "connect", connect), \
            mock.patch.dict(backup.os.environ, env or {}, clear=False), \
            mock.patch.dict(backup.DB_CONFIG, {"server": "localhost,1433", "database": "TwStock"}):
        if not env:
            backup.os.environ.pop("DB_CONTAINER", None)
        yield sql, conns


def _run(out_dir, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = backup.run(out_dir, kw.pop("direct", False))
    return rc, buf.getvalue()


NOW = datetime(2026, 11, 5, 7, 30)


def test_s9_ok_and_cleanup():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker()
        with _bk(dk) as (sql, conns):
            rc, out = _run(Path(tmp, "sub"))
        f = Path(tmp, "sub", "TwStock_20261105_073000.bak")
        assert rc == 0 and f.exists() and "✅ 備份完成並通過 RESTORE VERIFYONLY" in out and "（1.0 MB）" in out, out
        disk = "/var/opt/mssql/data/TwStock_20261105_073000.bak"
        assert sql == [f"BACKUP DATABASE [TwStock] TO DISK = N'{disk}' WITH COPY_ONLY, INIT, COMPRESSION",
                       f"RESTORE VERIFYONLY FROM DISK = N'{disk}'"]
        assert all("RESTORE DATABASE" not in s for s in sql) and conns[0].closed
        assert dk.calls == [["ps", "--filter", "publish=1433", "--format", "{{.Names}}"],
                            ["inspect", "-f", "{{.State.Running}}", "MySqlServer"],
                            ["cp", f"MySqlServer:{disk}", str(f.resolve())],
                            ["exec", "MySqlServer", "rm", "-f", disk]]          # 只刪這次自己的暫存檔
        # 同一秒再跑（mock）：不覆寫、不連資料庫、不呼叫 docker
        dk = _Docker()
        with _bk(dk) as (sql, conns):
            rc, out = _run(Path(tmp, "sub"))
        assert rc == 1 and "已存在，不覆寫" in out and sql == [] and dk.calls == [] and f.stat().st_size == 1048576


def test_s9_no_compression_and_env_container():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker()
        with _bk(dk, no_compress=True, env={"DB_CONTAINER": "twstock-mssql"}) as (sql, _):
            rc, out = _run(tmp)
        assert rc == 0 and "不支援壓縮備份，改用不壓縮" in out
        assert sql[1].endswith("WITH COPY_ONLY, INIT") and sql[2].startswith("RESTORE VERIFYONLY")
        assert dk.calls[0] == ["inspect", "-f", "{{.State.Running}}", "twstock-mssql"]        # 有 DB_CONTAINER 就不找 ps


def test_s9_docker_problems():
    cases = ((dict(missing=True), "找不到 docker 指令"), (dict(ps=""), "找到 0 個"), (dict(ps="a\nb"), "找到 2 個"),
             (dict(running="false"), "容器 MySqlServer 沒有在執行"), (dict(fail="ps"), "docker ps 失敗"))
    for kw, msg in cases:
        with tempfile.TemporaryDirectory() as tmp:
            dk = _Docker(**kw)
            with _bk(dk) as (sql, _):
                rc, out = _run(tmp)
            assert rc == 1 and msg in out and "Traceback" not in out and sql == [] and not list(Path(tmp).iterdir()), (kw, out)
    # cp 失敗：備份已在容器內，訊息指出 docker cp
    with tempfile.TemporaryDirectory() as tmp:
        dk = _Docker(fail="cp")
        with _bk(dk) as (sql, _):
            rc, out = _run(tmp)
        assert rc == 1 and "docker cp 失敗" in out and len(sql) == 2


def test_s9_direct_and_db_errors():
    with tempfile.TemporaryDirectory() as tmp, mock.patch.object(backup, "datetime", mock.Mock(now=lambda: NOW)):
        dk = _Docker(missing=True)                                      # --direct 完全不用 docker
        with _bk(dk) as (sql, _):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                path = backup.backup(Path(tmp), direct=True, now=NOW)
        assert sql[0] == f"BACKUP DATABASE [TwStock] TO DISK = N'{path}' WITH COPY_ONLY, INIT, COMPRESSION"
        # 資料庫連不上：rc=2、沒有 Traceback
        with _bk(_Docker(), connect_error=db.pyodbc.OperationalError("08001", "Login timeout expired")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cli.cmd_backup(argparse.Namespace(out=tmp, direct=False))
        assert rc == 2 and "連不上資料庫或備份失敗" in buf.getvalue() and "Traceback" not in buf.getvalue()
        # 壓縮以外的錯誤不吞掉
        with _bk(_Docker()) as (sql, _):
            with mock.patch.object(_SqlCur, "execute", side_effect=db.pyodbc.Error("42000", "permission denied")):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = cli.cmd_backup(argparse.Namespace(out=Path(tmp, "x"), direct=False))
        assert rc == 2 and "permission denied" in buf.getvalue()


def test_s9_cli():
    p = mock.patch.object(cli, "cmd_backup", lambda a: (a.out, a.direct))
    with p:
        assert cli.main(["backup", "--out", "x"]) == ("x", False) and cli.main(["backup", "--direct"]) == (None, True)
    assert backup.BACKUP_DIR == ROOT.parent / "_backups"
    assert "python -m twstock backup" in (cli.__doc__ or "")
    src = (ROOT / "twstock/backup.py").read_text(encoding="utf-8")
    assert "RESTORE DATABASE" not in src and "COPY_ONLY" in src and "rm\", \"-f\", disk" in src


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("全部通過")
```

---

## 附錄 E：PG 用 `logs/` 小工具

### E-1. `logs/iter06_compare.py`（隔離比對，取代 `iter05_compare.py`）

```python
# 用法：python3 logs/iter06_compare.py 基線資料夾 site/data —— 隔離比對（第 6 輪 F6-2，取代 iter05_compare.py）
# 除了 NEW_* 列的新增鍵與「時間」欄位（匯出時間、收集時間、更新於）以外必須完全相同；比對 latest.json、stocks/*.json、etfs/*.json。
# 相同印「✅ 相同」rc=0；不同列出鍵名或檔名 rc=1。
import json, sys
from pathlib import Path
a, b = Path(sys.argv[1]), Path(sys.argv[2])
NEW_LATEST, NEW_STOCK, NEW_STATUS = set(), set(), set()      # 本輪沒有新增鍵；之後各輪在這裡加
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
for sub, new in (("stocks", NEW_STOCK), ("etfs", set())):
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
